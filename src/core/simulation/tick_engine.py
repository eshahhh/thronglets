import time
from enum import Enum, auto

from ..actions.action_interpreter import ActionInterpreter, ActionOutcome
from ..actions.action_schema import Action, IdleAction
from ..agents.agent_manager import AgentManager
from ..logging.event_logger import EventLogger, EventType


class TickPhase(Enum):
    PRE_TICK = auto()
    AGENT_ACTIONS = auto()
    WORLD_UPDATE = auto()
    POST_TICK = auto()


class TickStats:
    def __init__(self, tick, duration_ms, agents_processed, actions_executed, actions_succeeded, actions_failed, events_logged=0):
        self.tick = tick
        self.duration_ms = duration_ms
        self.agents_processed = agents_processed
        self.actions_executed = actions_executed
        self.actions_succeeded = actions_succeeded
        self.actions_failed = actions_failed
        self.events_logged = events_logged

    def to_dict(self):
        return {
            "tick": self.tick,
            "duration_ms": self.duration_ms,
            "agents_processed": self.agents_processed,
            "actions_executed": self.actions_executed,
            "actions_succeeded": self.actions_succeeded,
            "actions_failed": self.actions_failed,
            "events_logged": self.events_logged,
        }


class ScheduledEvent:
    def __init__(self, tick, callback, name="", recurring=False, interval=0):
        self.tick = tick
        self.callback = callback
        self.name = name
        self.recurring = recurring
        self.interval = interval


class AgentActionProvider:
    def get_action(self, agent_id, tick):
        return IdleAction(agent_id=agent_id, reason="No cognition layer active")

    def get_actions_batch(self, agent_ids, tick):
        return {aid: self.get_action(aid, tick) for aid in agent_ids}


class TickEngine:
    def __init__(self, world_state, agent_manager, action_interpreter, event_logger=None, action_provider=None):
        self.world_state = world_state
        self.agent_manager = agent_manager
        self.action_interpreter = action_interpreter
        self.event_logger = event_logger
        self.action_provider = action_provider or AgentActionProvider()

        self._current_tick = 0
        self._running = False
        self._paused = False

        self._scheduled_events = []

        self._hooks = {
            "before_tick": [],
            "after_tick": [],
            "before_agent_action": [],
            "after_agent_action": [],
            "world_update": [],
        }

        self._tick_history = []
        self._max_history = 1000

        self.agent_order_seed = None
        self.process_agents_parallel = False

    @property
    def current_tick(self):
        return self._current_tick

    @property
    def is_running(self):
        return self._running

    def register_hook(self, hook_name, callback):
        if hook_name not in self._hooks:
            raise ValueError(f"Unknown hook: {hook_name}")
        self._hooks[hook_name].append(callback)

    def unregister_hook(self, hook_name, callback):
        if hook_name in self._hooks and callback in self._hooks[hook_name]:
            self._hooks[hook_name].remove(callback)
            return True
        return False

    def _invoke_hooks(self, hook_name, *args, **kwargs):
        for callback in self._hooks.get(hook_name, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                if self.event_logger:
                    self.event_logger.log(
                        EventType.ERROR,
                        self._current_tick,
                        time.time(),
                        data={"hook": hook_name, "error": str(e)},
                    )

    def schedule_event(self, tick, callback, name="", recurring=False, interval=0):
        event = ScheduledEvent(tick, callback, name=name, recurring=recurring, interval=interval)
        self._scheduled_events.append(event)
        return event

    def cancel_event(self, event):
        if event in self._scheduled_events:
            self._scheduled_events.remove(event)
            return True
        return False

    def _process_scheduled_events(self):
        events_to_process = [e for e in self._scheduled_events if e.tick == self._current_tick]

        for event in events_to_process:
            try:
                event.callback(self, self._current_tick)
            except Exception as e:
                if self.event_logger:
                    self.event_logger.log(
                        EventType.ERROR,
                        self._current_tick,
                        time.time(),
                        data={"scheduled_event": event.name, "error": str(e)},
                    )

            if event.recurring and event.interval > 0:
                event.tick = self._current_tick + event.interval
            else:
                self._scheduled_events.remove(event)

    def _get_agent_order(self):
        agent_ids = self.agent_manager.list_agent_ids()

        if self.agent_order_seed is not None:
            import random
            rng = random.Random(self.agent_order_seed + self._current_tick)
            rng.shuffle(agent_ids)
        else:
            agent_ids.sort()

        return agent_ids

    def _apply_world_updates(self):
        self._invoke_hooks("world_update", self, self._current_tick)

    def _decay_agent_needs(self, decay_rates=None):
        if decay_rates is None:
            decay_rates = {
                "food": 1.0,
                "shelter": 0.5,
            }

        for agent in self.agent_manager.list_agents():
            for need, rate in decay_rates.items():
                if need in agent.needs:
                    current = agent.needs[need]
                    agent.needs[need] = max(0.0, current - rate)

    def execute_tick(self):
        tick_start = time.time()
        actions_executed = 0
        actions_succeeded = 0
        actions_failed = 0

        if self.event_logger:
            self.event_logger.log_tick(self._current_tick, tick_start, is_start=True)

        self._invoke_hooks("before_tick", self, self._current_tick)

        self._process_scheduled_events()

        agent_order = self._get_agent_order()

        for agent_id in agent_order:
            self._invoke_hooks("before_agent_action", self, self._current_tick, agent_id)

            action = self.action_provider.get_action(agent_id, self._current_tick)
            action.timestamp = time.time()

            outcome = self.action_interpreter.execute(action)
            actions_executed += 1

            if outcome.succeeded:
                actions_succeeded += 1
            else:
                actions_failed += 1

            self._log_action_outcome(action, outcome)

            self._invoke_hooks("after_agent_action", self, self._current_tick, agent_id, outcome)

        self._apply_world_updates()

        self._invoke_hooks("after_tick", self, self._current_tick)

        tick_end = time.time()
        duration_ms = (tick_end - tick_start) * 1000

        stats = TickStats(
            self._current_tick,
            duration_ms,
            len(agent_order),
            actions_executed,
            actions_succeeded,
            actions_failed,
        )

        if self.event_logger:
            self.event_logger.log_tick(
                self._current_tick, tick_end, is_start=False, stats=stats.to_dict()
            )

        self._tick_history.append(stats)
        if len(self._tick_history) > self._max_history:
            self._tick_history.pop(0)

        self._current_tick += 1

        return stats

    def _log_action_outcome(self, action, outcome):
        if not self.event_logger:
            return

        event_type_map = {
            "MOVE": EventType.AGENT_MOVE,
            "HARVEST": EventType.AGENT_HARVEST,
            "CRAFT": EventType.AGENT_CRAFT,
            "MESSAGE": EventType.AGENT_MESSAGE,
            "TRADE_PROPOSAL": EventType.AGENT_TRADE_PROPOSE,
            "ACCEPT_TRADE": EventType.AGENT_TRADE_ACCEPT,
            "GROUP_ACTION": EventType.AGENT_GROUP_ACTION,
            "IDLE": EventType.AGENT_IDLE,
        }

        event_type = event_type_map.get(action.action_type.name, EventType.INFO)

        self.event_logger.log(
            event_type=event_type,
            tick=self._current_tick,
            timestamp=action.timestamp,
            agent_id=action.agent_id,
            data={
                "result": outcome.result.name,
                "message": outcome.message,
                "state_changes": outcome.state_changes,
            },
        )

    def run(self, num_ticks=None, stop_condition=None):
        self._running = True
        stats_list = []
        ticks_run = 0

        try:
            while self._running:
                if self._paused:
                    time.sleep(0.01)
                    continue

                if num_ticks is not None and ticks_run >= num_ticks:
                    break

                if stop_condition and stop_condition(self):
                    break

                stats = self.execute_tick()
                stats_list.append(stats)
                ticks_run += 1

        finally:
            self._running = False

        return stats_list

    def stop(self):
        self._running = False

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def reset(self, tick=0):
        self._current_tick = tick
        self._tick_history.clear()
        self._scheduled_events.clear()

    def get_tick_stats(self, tick):
        for stats in self._tick_history:
            if stats.tick == tick:
                return stats
        return None

    def get_recent_stats(self, count=10):
        return self._tick_history[-count:]

    def get_average_tick_duration(self):
        if not self._tick_history:
            return 0.0
        return sum(s.duration_ms for s in self._tick_history) / len(self._tick_history)
