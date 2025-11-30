import time
import random
from pathlib import Path

from ..config import load_configs, WorldConfig, SimulationConfig, ResourceConfig
from ..world.location_graph import LocationGraph
from ..world.world_state import WorldState
from ..world.crafting_rules import CraftingRules
from ..agents.agent_manager import AgentManager
from ..actions.action_interpreter import ActionInterpreter
from ..logging.event_logger import EventLogger, EventType, SnapshotManager
from ..comm.message_bus import MessageBus
from .tick_engine import TickEngine, AgentActionProvider
from .lifecycle_hooks import (
    LifecycleHookManager,
    ResourceRegenerationHook,
    NeedDecayHook,
    InventoryDecayHook,
    SnapshotHook,
    StabilityCheckHook,
    HookPhase,
)


class DummyActionProvider(AgentActionProvider):
    def __init__(self, location_graph, agent_manager):
        self.location_graph = location_graph
        self.agent_manager = agent_manager
        self._rng = random.Random()

    def set_seed(self, seed):
        self._rng = random.Random(seed)

    def get_action(self, agent_id, tick):
        from ..actions.action_schema import IdleAction, MoveAction, HarvestAction

        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return IdleAction(agent_id=agent_id, reason="Agent not found")

        action_roll = self._rng.random()

        if action_roll < 0.3:
            neighbors = self.location_graph.get_neighbors(agent.location)
            if neighbors:
                destination = self._rng.choice(neighbors)
                return MoveAction(agent_id=agent_id, destination=destination)

        elif action_roll < 0.7:
            location = self.location_graph.get_node(agent.location)
            if location and location.resource_richness:
                available = [r for r, amt in location.resource_richness.items() if amt > 0]
                if available:
                    resource = self._rng.choice(available)
                    return HarvestAction(agent_id=agent_id, resource_type=resource, amount=1)

        return IdleAction(agent_id=agent_id, reason="No action chosen")


class SimulationResult:
    def __init__(self):
        self.tick_stats = []
        self.final_tick = 0
        self.total_duration_ms = 0.0
        self.agents_final = []
        self.world_state_final = None
        self.metrics = {}

    def add_tick_stats(self, stats):
        self.tick_stats.append(stats)

    def finalize(self, world_state, agents, duration_ms):
        self.world_state_final = world_state
        self.agents_final = agents
        self.total_duration_ms = duration_ms
        if self.tick_stats:
            self.final_tick = self.tick_stats[-1].tick

    def compute_metrics(self):
        total_inventory = 0
        total_needs = 0.0
        agent_count = len(self.agents_final)

        for agent in self.agents_final:
            if hasattr(agent, "inventory"):
                total_inventory += sum(agent.inventory.values())
            if hasattr(agent, "needs"):
                total_needs += sum(agent.needs.values())

        self.metrics["agent_count"] = agent_count
        self.metrics["total_inventory"] = total_inventory
        self.metrics["avg_inventory"] = total_inventory / agent_count if agent_count > 0 else 0
        self.metrics["total_needs"] = total_needs
        self.metrics["avg_needs"] = total_needs / agent_count if agent_count > 0 else 0
        self.metrics["ticks_executed"] = len(self.tick_stats)
        self.metrics["avg_tick_ms"] = (
            sum(s.duration_ms for s in self.tick_stats) / len(self.tick_stats)
            if self.tick_stats else 0
        )

        return self.metrics

    def to_dict(self):
        return {
            "final_tick": self.final_tick,
            "total_duration_ms": self.total_duration_ms,
            "metrics": self.metrics,
            "tick_count": len(self.tick_stats),
        }


class SimulationAssembly:
    def __init__(self, config_dir=None):
        self.config_dir = config_dir
        self.world_config = None
        self.simulation_config = None
        self.resource_config = None

        self.location_graph = None
        self.world_state = None
        self.crafting_rules = None
        self.agent_manager = None
        self.action_interpreter = None
        self.event_logger = None
        self.message_bus = None
        self.tick_engine = None
        self.snapshot_manager = None
        self.hook_manager = None
        self.action_provider = None

        self._initialized = False

    def load_configs(self):
        configs = load_configs(self.config_dir)
        self.world_config = configs["world"]
        self.simulation_config = configs["simulation"]
        self.resource_config = configs["resources"]
        return self

    def create_world(self):
        graph_config = self.world_config.to_location_graph_config()
        self.location_graph = LocationGraph.from_config(graph_config)

        self.world_state = WorldState(
            tick=0,
            locations={loc["id"]: loc for loc in self.world_config.locations},
            resource_nodes={},
            agents={},
            config={
                "tick_rate": self.simulation_config.tick_rate,
                "max_ticks": self.simulation_config.max_ticks,
            },
        )

        crafting_config = self.resource_config.to_crafting_rules_config()
        self.crafting_rules = CraftingRules.from_config(crafting_config)

        return self

    def spawn_agents(self, count=None):
        self.agent_manager = AgentManager()

        num_agents = count or self.simulation_config.initial_agent_count
        spawn_locs = self.simulation_config.spawn_locations
        if not spawn_locs:
            spawn_locs = list(self.location_graph.nodes.keys())

        rng = random.Random(self.simulation_config.random_seed)

        for i in range(num_agents):
            name = f"{self.simulation_config.agent_name_prefix}_{i}"
            location = rng.choice(spawn_locs)
            needs = dict(self.simulation_config.starting_needs)

            self.agent_manager.spawn_agent(
                name=name,
                location=location,
                capacity=self.simulation_config.agent_capacity,
                needs=needs,
            )

        return self

    def setup_logging(self, output_dir=None):
        if output_dir:
            log_path = Path(output_dir) / "events.jsonl"
        else:
            log_path = Path(self.simulation_config.log_output_path)

        log_path.parent.mkdir(parents=True, exist_ok=True)

        self.event_logger = EventLogger(
            output_path=str(log_path) if self.simulation_config.log_enabled else None,
            buffer_size=self.simulation_config.log_buffer_size,
            compress=False,
            auto_flush=True,
        )

        if output_dir:
            snapshot_dir = Path(output_dir) / "snapshots"
        else:
            snapshot_dir = Path(self.simulation_config.snapshot_output_dir)

        if self.simulation_config.snapshot_enabled:
            self.snapshot_manager = SnapshotManager(
                output_dir=str(snapshot_dir),
                snapshot_interval=self.simulation_config.snapshot_interval,
                compress=self.simulation_config.snapshot_compress,
            )

        return self

    def setup_components(self):
        self.message_bus = MessageBus()

        crafting_dict = {}
        for recipe in self.resource_config.recipes:
            crafting_dict[recipe["id"]] = {
                "inputs": recipe.get("inputs", {}),
                "outputs": recipe.get("outputs", {}),
                "skill_gain": recipe.get("skill_bonuses", {}),
            }

        self.action_interpreter = ActionInterpreter(
            world_state=self.world_state,
            agent_manager=self.agent_manager,
            location_graph=self.location_graph,
            crafting_rules=crafting_dict,
        )

        self.action_provider = DummyActionProvider(
            location_graph=self.location_graph,
            agent_manager=self.agent_manager,
        )
        if self.simulation_config.random_seed:
            self.action_provider.set_seed(self.simulation_config.random_seed)

        return self

    def setup_hooks(self):
        self.hook_manager = LifecycleHookManager()

        hook_cfg = self.simulation_config.hooks

        if hook_cfg.get("resource_regeneration", {}).get("enabled", True):
            regen_hook = ResourceRegenerationHook(
                regen_rates=self.resource_config.get_all_regen_rates(),
                max_resources=self.resource_config.get_all_regen_caps(),
            )
            regen_hook.priority = hook_cfg.get("resource_regeneration", {}).get("priority", 10)
            self.hook_manager.register(HookPhase.WORLD_UPDATE, regen_hook)

        if hook_cfg.get("need_decay", {}).get("enabled", True):
            decay_hook = NeedDecayHook(decay_rates=self.simulation_config.need_decay)
            decay_hook.priority = hook_cfg.get("need_decay", {}).get("priority", 5)
            self.hook_manager.register(HookPhase.AFTER_TICK, decay_hook)

        decay_items = self.resource_config.get_decay_items()
        if decay_items:
            inv_decay_hook = InventoryDecayHook(decay_items=decay_items)
            self.hook_manager.register(HookPhase.AFTER_TICK, inv_decay_hook)

        if hook_cfg.get("stability_check", {}).get("enabled", True):
            stability_cfg = hook_cfg.get("stability_check", {})
            stability_hook = StabilityCheckHook(
                min_agents=stability_cfg.get("min_agents", 1),
                max_tick_duration_ms=stability_cfg.get("max_tick_duration_ms", 10000.0),
            )
            stability_hook.priority = stability_cfg.get("priority", 1)
            self.hook_manager.register(HookPhase.AFTER_TICK, stability_hook)

        if self.snapshot_manager:
            snapshot_hook = SnapshotHook(
                snapshot_manager=self.snapshot_manager,
                interval=self.simulation_config.snapshot_interval,
            )
            self.hook_manager.register(HookPhase.AFTER_TICK, snapshot_hook)

        return self

    def create_engine(self):
        self.tick_engine = TickEngine(
            world_state=self.world_state,
            agent_manager=self.agent_manager,
            action_interpreter=self.action_interpreter,
            event_logger=self.event_logger,
            action_provider=self.action_provider,
        )

        if self.simulation_config.agent_order_randomize:
            self.tick_engine.agent_order_seed = self.simulation_config.random_seed or 42

        self.hook_manager.create_engine_hooks(self.tick_engine)

        self._initialized = True
        return self

    def initialize(self, output_dir=None, agent_count=None):
        return (
            self.load_configs()
            .create_world()
            .spawn_agents(count=agent_count)
            .setup_logging(output_dir=output_dir)
            .setup_components()
            .setup_hooks()
            .create_engine()
        )

    def run_silently(self, num_ticks=None, stop_condition=None):
        if not self._initialized:
            raise RuntimeError("Simulation not initialized. Call initialize() first.")

        num_ticks = num_ticks or self.simulation_config.max_ticks

        start_time = time.time()

        self.event_logger.log_simulation_event(
            EventType.SIMULATION_START,
            tick=0,
            timestamp=start_time,
            data={"max_ticks": num_ticks},
        )

        def combined_stop_condition(engine):
            if engine.agent_manager.agent_count() < self.simulation_config.min_agents:
                return True
            if stop_condition and stop_condition(engine):
                return True
            return False

        tick_stats = self.tick_engine.run(
            num_ticks=num_ticks,
            stop_condition=combined_stop_condition,
        )

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000

        self.event_logger.log_simulation_event(
            EventType.SIMULATION_END,
            tick=self.tick_engine.current_tick,
            timestamp=end_time,
            data={"ticks_run": len(tick_stats)},
        )

        result = SimulationResult()
        for stats in tick_stats:
            result.add_tick_stats(stats)

        agents = self.agent_manager.list_agents()
        result.finalize(self.world_state, agents, duration_ms)
        result.compute_metrics()

        return result

    def export_snapshot(self, output_path=None):
        if not self._initialized:
            raise RuntimeError("Simulation not initialized.")

        if self.snapshot_manager:
            agents_data = [
                {
                    "id": a.id,
                    "name": a.name,
                    "location": a.location,
                    "inventory": a.inventory,
                    "needs": a.needs,
                    "skills": a.skills,
                }
                for a in self.agent_manager.list_agents()
            ]

            return self.snapshot_manager.take_snapshot(
                tick=self.tick_engine.current_tick,
                timestamp=time.time(),
                agents=agents_data,
                world_state=self.world_state.to_dict(),
            )
        return None

    def cleanup(self):
        if self.event_logger:
            self.event_logger.close()


def run_silently(config_dir=None, output_dir=None, num_ticks=None, agent_count=None):
    assembly = SimulationAssembly(config_dir=config_dir)
    try:
        assembly.initialize(output_dir=output_dir, agent_count=agent_count)
        result = assembly.run_silently(num_ticks=num_ticks)
        assembly.export_snapshot()
        return result
    finally:
        assembly.cleanup()
