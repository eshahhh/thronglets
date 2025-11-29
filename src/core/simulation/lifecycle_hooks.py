from abc import ABC, abstractmethod
import time
from enum import Enum, auto


class HookPhase(Enum):
    WARMUP_START = auto()
    WARMUP_END = auto()
    BEFORE_TICK = auto()
    AFTER_TICK = auto()
    BEFORE_AGENT_ACTION = auto()
    AFTER_AGENT_ACTION = auto()
    WORLD_UPDATE = auto()
    SIMULATION_START = auto()
    SIMULATION_END = auto()
    SNAPSHOT = auto()


class HookResult:
    def __init__(self, success, hook_name, phase, duration_ms, error=None, data=None):
        self.success = success
        self.hook_name = hook_name
        self.phase = phase
        self.duration_ms = duration_ms
        self.error = error
        self.data = data if data is not None else {}


class LifecycleHook(ABC):
    def __init__(self, name="", priority=0):
        self.name = name or self.__class__.__name__
        self.priority = priority
        self.enabled = True
        self._execution_count = 0
        self._total_duration_ms = 0.0

    @abstractmethod
    def execute(self, engine, tick, **kwargs):
        pass

    def __call__(self, engine, tick, **kwargs):
        if not self.enabled:
            return HookResult(
                True,
                self.name,
                HookPhase.BEFORE_TICK,
                0.0,
                data={"skipped": True},
            )

        start = time.time()
        try:
            result = self.execute(engine, tick, **kwargs)
            self._execution_count += 1
            self._total_duration_ms += result.duration_ms
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            return HookResult(
                False,
                self.name,
                HookPhase.BEFORE_TICK,
                duration,
                error=str(e),
            )

    @property
    def average_duration_ms(self):
        if self._execution_count == 0:
            return 0.0
        return self._total_duration_ms / self._execution_count


class ResourceRegenerationHook(LifecycleHook):
    def __init__(self, regen_rates=None, max_resources=None, name="ResourceRegeneration"):
        super().__init__(name=name)
        self.regen_rates = regen_rates or {}
        self.max_resources = max_resources or {}

    def execute(self, engine, tick, **kwargs):
        start = time.time()
        resources_regenerated = 0

        location_graph = engine.action_interpreter.location_graph

        for node_id, node in location_graph.nodes.items():
            for resource_type, rate in self.regen_rates.items():
                current = node.resource_richness.get(resource_type, 0)
                max_val = self.max_resources.get(resource_type, float("inf"))
                if current < max_val:
                    new_val = min(current + rate, max_val)
                    node.resource_richness[resource_type] = new_val
                    resources_regenerated += 1

        duration = (time.time() - start) * 1000
        return HookResult(
            True,
            self.name,
            HookPhase.WORLD_UPDATE,
            duration,
            data={"resources_regenerated": resources_regenerated},
        )


class NeedDecayHook(LifecycleHook):
    def __init__(self, decay_rates=None, name="NeedDecay"):
        super().__init__(name=name)
        self.decay_rates = decay_rates or {"food": 1.0, "shelter": 0.5}

    def execute(self, engine, tick, **kwargs):
        start = time.time()
        agents_processed = 0

        for agent in engine.agent_manager.list_agents():
            for need, rate in self.decay_rates.items():
                if need in agent.needs:
                    current = agent.needs[need]
                    agent.needs[need] = max(0.0, current - rate)
            agents_processed += 1

        duration = (time.time() - start) * 1000
        return HookResult(
            True,
            self.name,
            HookPhase.AFTER_TICK,
            duration,
            data={"agents_processed": agents_processed},
        )


class InventoryDecayHook(LifecycleHook):
    def __init__(self, decay_items=None, name="InventoryDecay"):
        super().__init__(name=name)
        self.decay_items = decay_items or {}

    def execute(self, engine, tick, **kwargs):
        start = time.time()
        items_decayed = 0

        import random

        for agent in engine.agent_manager.list_agents():
            for item_type, decay_chance in self.decay_items.items():
                if item_type in agent.inventory:
                    count = agent.inventory[item_type]
                    decayed = sum(1 for _ in range(count) if random.random() < decay_chance)
                    if decayed > 0:
                        new_count = count - decayed
                        if new_count <= 0:
                            del agent.inventory[item_type]
                        else:
                            agent.inventory[item_type] = new_count
                        items_decayed += decayed

        duration = (time.time() - start) * 1000
        return HookResult(
            True,
            self.name,
            HookPhase.AFTER_TICK,
            duration,
            data={"items_decayed": items_decayed},
        )


class SnapshotHook(LifecycleHook):
    def __init__(self, snapshot_manager, interval=100, name="Snapshot"):
        super().__init__(name=name)
        self.snapshot_manager = snapshot_manager
        self.interval = interval

    def execute(self, engine, tick, **kwargs):
        start = time.time()

        if tick % self.interval != 0:
            return HookResult(
                True,
                self.name,
                HookPhase.SNAPSHOT,
                0.0,
                data={"skipped": True},
            )

        agents = [
            {
                "id": a.id,
                "name": a.name,
                "location": a.location,
                "inventory": a.inventory,
                "needs": a.needs,
                "skills": a.skills,
            }
            for a in engine.agent_manager.list_agents()
        ]

        self.snapshot_manager.take_snapshot(tick=tick, timestamp=time.time(), agents=agents)

        duration = (time.time() - start) * 1000
        return HookResult(
            True,
            self.name,
            HookPhase.SNAPSHOT,
            duration,
            data={"snapshot_taken": True},
        )


class StabilityCheckHook(LifecycleHook):
    def __init__(self, min_agents=1, max_tick_duration_ms=10000.0, name="StabilityCheck"):
        super().__init__(name=name)
        self.min_agents = min_agents
        self.max_tick_duration_ms = max_tick_duration_ms
        self.warnings = []

    def execute(self, engine, tick, **kwargs):
        start = time.time()
        self.warnings.clear()
        stable = True

        agent_count = engine.agent_manager.agent_count()
        if agent_count < self.min_agents:
            self.warnings.append(f"Agent count ({agent_count}) below minimum ({self.min_agents})")
            stable = False

        avg_duration = engine.get_average_tick_duration()
        if avg_duration > self.max_tick_duration_ms:
            self.warnings.append(f"Average tick duration ({avg_duration:.1f}ms) exceeds limit")

        critical_agents = 0
        for agent in engine.agent_manager.list_agents():
            for need, value in agent.needs.items():
                if value <= 0:
                    critical_agents += 1
                    break

        if critical_agents > 0:
            self.warnings.append(f"{critical_agents} agents have critical needs (<=0)")

        duration = (time.time() - start) * 1000
        return HookResult(
            stable,
            self.name,
            HookPhase.AFTER_TICK,
            duration,
            data={
                "stable": stable,
                "warnings": self.warnings,
                "agent_count": agent_count,
                "critical_agents": critical_agents,
            },
        )


class LifecycleHookManager:
    def __init__(self):
        self._hooks = {phase: [] for phase in HookPhase}
        self._execution_history = []
        self._max_history = 1000

    def register(self, phase, hook):
        self._hooks[phase].append(hook)
        self._hooks[phase].sort(key=lambda h: -h.priority)

    def unregister(self, phase, hook):
        if hook in self._hooks[phase]:
            self._hooks[phase].remove(hook)
            return True
        return False

    def execute_phase(self, phase, engine, tick, **kwargs):
        results = []
        for hook in self._hooks[phase]:
            result = hook(engine, tick, **kwargs)
            result.phase = phase
            results.append(result)
            self._execution_history.append(result)

        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]

        return results

    def get_hooks(self, phase):
        return list(self._hooks[phase])

    def clear_phase(self, phase):
        self._hooks[phase].clear()

    def clear_all(self):
        for phase in HookPhase:
            self._hooks[phase].clear()

    def get_execution_history(self, phase=None, limit=100):
        history = self._execution_history
        if phase is not None:
            history = [r for r in history if r.phase == phase]
        return history[-limit:]

    def create_engine_hooks(self, engine):
        def before_tick_wrapper(eng, tick):
            self.execute_phase(HookPhase.BEFORE_TICK, eng, tick)

        def after_tick_wrapper(eng, tick):
            self.execute_phase(HookPhase.AFTER_TICK, eng, tick)

        def world_update_wrapper(eng, tick):
            self.execute_phase(HookPhase.WORLD_UPDATE, eng, tick)

        engine.register_hook("before_tick", before_tick_wrapper)
        engine.register_hook("after_tick", after_tick_wrapper)
        engine.register_hook("world_update", world_update_wrapper)


class SimulationLifecycle:
    def __init__(self, engine, hook_manager=None):
        self.engine = engine
        self.hook_manager = hook_manager or LifecycleHookManager()
        self._warmup_complete = False
        self._simulation_started = False
        self._simulation_ended = False

    def warmup(self, num_ticks=0, setup_fn=None):
        self.hook_manager.execute_phase(HookPhase.WARMUP_START, self.engine, self.engine.current_tick)

        if setup_fn:
            setup_fn(self.engine)

        if num_ticks > 0:
            self.engine.run(num_ticks=num_ticks)

        self.hook_manager.execute_phase(HookPhase.WARMUP_END, self.engine, self.engine.current_tick)
        self._warmup_complete = True

    def start(self):
        self.hook_manager.execute_phase(HookPhase.SIMULATION_START, self.engine, self.engine.current_tick)
        self._simulation_started = True

    def end(self):
        self.hook_manager.execute_phase(HookPhase.SIMULATION_END, self.engine, self.engine.current_tick)
        self._simulation_ended = True

    def run_simulation(self, warmup_ticks=0, main_ticks=None, stop_condition=None):
        self.warmup(num_ticks=warmup_ticks)
        self.start()
        try:
            stats = self.engine.run(num_ticks=main_ticks, stop_condition=stop_condition)
        finally:
            self.end()
        return stats

    @property
    def is_warmup_complete(self):
        return self._warmup_complete

    @property
    def is_running(self):
        return self._simulation_started and not self._simulation_ended
