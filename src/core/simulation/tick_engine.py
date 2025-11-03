import time
from enum import Enum, auto

from ..actions.action_interpreter import ActionInterpreter, ActionOutcome
from ..actions.action_schema import BaseAction as Action, IdleAction
from ..agents import AgentManager
from ..logging.event_logger import EventLogger, EventType
from ..logging.live_logger import get_live_logger


class TickPhase(Enum):
    PRE_TICK = auto()
    AGENT_ACTIONS = auto()
    WORLD_UPDATE = auto()
    POST_TICK = auto()


class TickStats:
    def __init__(self, tick, duration_ms, agents_processed, actions_executed, actions_succeeded, actions_failed, events_logged=0, llm_errors=0, agents_resting=0):
        self.tick = tick
        self.duration_ms = duration_ms
        self.agents_processed = agents_processed
        self.actions_executed = actions_executed
        self.actions_succeeded = actions_succeeded
        self.actions_failed = actions_failed
        self.events_logged = events_logged
        self.llm_errors = llm_errors
        self.agents_resting = agents_resting

    def to_dict(self):
        return {
            "tick": self.tick,
            "duration_ms": self.duration_ms,
            "agents_processed": self.agents_processed,
            "actions_executed": self.actions_executed,
            "actions_succeeded": self.actions_succeeded,
            "actions_failed": self.actions_failed,
            "events_logged": self.events_logged,
            "llm_errors": self.llm_errors,
            "agents_resting": self.agents_resting,
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
    def __init__(self, world_state, agent_manager, action_interpreter, event_logger=None, action_provider=None, enable_live_logging=True, live_logger=None, tick_delay=0.0, min_tick_duration=1.0):
        self.world_state = world_state
        self.agent_manager = agent_manager
        self.action_interpreter = action_interpreter
        self.event_logger = event_logger
        self.action_provider = action_provider or AgentActionProvider()
        self.enable_live_logging = enable_live_logging
        self._live_logger = live_logger if live_logger else get_live_logger()
        
        self.tick_delay = tick_delay
        self.min_tick_duration = min_tick_duration

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
            "after_tick_complete": [],
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
        llm_errors = 0
        agents_resting = 0

        if self.event_logger:
            self.event_logger.log_tick(self._current_tick, tick_start, is_start=True)

        self._invoke_hooks("before_tick", self, self._current_tick)

        self._process_scheduled_events()

        agent_order = self._get_agent_order()
        
        if self.enable_live_logging:
            self._live_logger.log_tick_start(self._current_tick, len(agent_order))

        for agent_id in agent_order:
            self._invoke_hooks("before_agent_action", self, self._current_tick, agent_id)

            action = self.action_provider.get_action(agent_id, self._current_tick)
            action.timestamp = time.time()
            
            metadata = None
            if hasattr(self.action_provider, 'get_last_action_metadata'):
                metadata = self.action_provider.get_last_action_metadata(agent_id)
            
            is_rest = metadata.get("is_rest", False) if metadata else False
            is_llm_error = metadata.get("llm_error", False) if metadata else False
            
            if is_rest:
                agents_resting += 1
            
            if is_llm_error:
                llm_errors += 1
            
            if self.enable_live_logging:
                action_details = self._get_action_details(action)
                if is_rest:
                    action_details['rest'] = True
                if is_llm_error:
                    action_details['llm_error'] = True
                self._live_logger.log_action_execute(
                    agent_id=agent_id,
                    tick=self._current_tick,
                    action_type=action.action_type.name,
                    details=action_details,
                )

            outcome = self.action_interpreter.execute(action)
            actions_executed += 1

            if is_llm_error:
                actions_failed += 1
            elif outcome.succeeded:
                actions_succeeded += 1
            else:
                actions_failed += 1
            
            if self.enable_live_logging:
                self._live_logger.log_action_result(
                    agent_id=agent_id,
                    tick=self._current_tick,
                    action_type=action.action_type.name,
                    success=outcome.succeeded and not is_llm_error,
                    message=outcome.message,
                )

            self._log_action_outcome(action, outcome, is_llm_error=is_llm_error)

            self._invoke_hooks("after_agent_action", self, self._current_tick, agent_id, outcome)

        self._apply_world_updates()

        self._invoke_hooks("after_tick", self, self._current_tick)

        tick_end = time.time()
        duration_ms = (tick_end - tick_start) * 1000
        
        min_duration_ms = self.min_tick_duration * 1000
        if duration_ms < min_duration_ms:
            sleep_time = (min_duration_ms - duration_ms) / 1000
            time.sleep(sleep_time)
            tick_end = time.time()
            duration_ms = (tick_end - tick_start) * 1000

        stats = TickStats(
            self._current_tick,
            duration_ms,
            len(agent_order),
            actions_executed,
            actions_succeeded,
            actions_failed,
            llm_errors=llm_errors,
            agents_resting=agents_resting,
        )
        
        if self.enable_live_logging:
            self._live_logger.log_tick_end(
                tick=self._current_tick,
                duration_ms=duration_ms,
                actions_executed=actions_executed,
                actions_succeeded=actions_succeeded,
            )

        if self.event_logger:
            self.event_logger.log_tick(
                self._current_tick, tick_end, is_start=False, stats=stats.to_dict()
            )

        self._tick_history.append(stats)
        if len(self._tick_history) > self._max_history:
            self._tick_history.pop(0)

        self._invoke_hooks("after_tick_complete", self, self._current_tick, stats)

        self._current_tick += 1

        return stats
    
    def _get_action_details(self, action) -> dict:
        details = {}
        if hasattr(action, 'destination'):
            details['dest'] = action.destination
        if hasattr(action, 'resource_type'):
            details['resource'] = action.resource_type
            if hasattr(action, 'amount'):
                details['amt'] = action.amount
        if hasattr(action, 'target_agent_id'):
            details['target'] = action.target_agent_id
        if hasattr(action, 'recipe_id'):
            details['recipe'] = action.recipe_id
        if hasattr(action, 'recipient_id') and action.recipient_id:
            details['recipient'] = action.recipient_id
        if hasattr(action, 'content') and action.content:
            details['msg'] = action.content[:30] + '...' if len(action.content) > 30 else action.content
        if hasattr(action, 'reason') and action.reason:
            details['reason'] = action.reason[:30] + '...' if len(action.reason) > 30 else action.reason
        return details

    def _log_action_outcome(self, action, outcome, is_llm_error=False):
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
        
        if is_llm_error:
            result_name = "LLM_ERROR"
        else:
            result_name = outcome.result.name

        self.event_logger.log(
            event_type=event_type,
            tick=self._current_tick,
            timestamp=action.timestamp,
            agent_id=action.agent_id,
            data={
                "result": result_name,
                "message": outcome.message,
                "state_changes": outcome.state_changes,
                "is_llm_error": is_llm_error,
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
                
                if self.tick_delay > 0:
                    time.sleep(self.tick_delay)

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
