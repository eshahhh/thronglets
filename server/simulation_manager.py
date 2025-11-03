import os
import sys
import time
import random
import asyncio
import threading
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import load_configs
from core.world import LocationGraph, WorldState, CraftingRules, AgentManager
from core.actions import ActionInterpreter
from core.logging import EventLogger, EventType, SnapshotManager
from core.comm import MessageBus
from core.simulation import TickEngine, AgentActionProvider
from core.simulation.lifecycle_hooks import (
    LifecycleHookManager,
    ResourceRegenerationHook,
    NeedDecayHook,
    InventoryDecayHook,
    SnapshotHook,
    StabilityCheckHook,
    HookPhase,
)
from core.cognition import (
    LLMActionProvider,
    ModelRegistry,
    InferenceClient,
    MemorySubsystem,
    RoleInitializer,
)
from core.metrics.trade_network import TradeNetworkAnalyzer
from core.metrics.wealth_tracker import WealthTracker
from core.metrics.specialization import SpecializationDetector
from core.governance import GovernanceSystem, GroupManager


class DummyActionProvider(AgentActionProvider):
    def __init__(self, location_graph, agent_manager):
        self.location_graph = location_graph
        self.agent_manager = agent_manager
        self._rng = random.Random()

    def set_seed(self, seed):
        self._rng = random.Random(seed)

    def get_action(self, agent_id, tick):
        from core.actions.action_schema import IdleAction, MoveAction, HarvestAction

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


class SimulationManager:
    def __init__(self, config_dir=None, use_llm=False, output_dir="output"):
        self.config_dir = config_dir
        self.use_llm = use_llm
        self.output_dir = output_dir
        
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
        
        self.model_registry = None
        self.inference_client = None
        self.memory_subsystem = None
        self.role_initializer = None
        
        self.trade_analyzer = None
        self.wealth_tracker = None
        self.specialization_detector = None
        self.group_manager = None
        self.governance_system = None

        self._initialized = False
        self._running = False
        self._paused = False
        self._thread = None
        self._tick_delay = 1.0
        
        self._agent_positions = {}
        self._agent_actions = {}
        self._agent_reasoning = {}
        self._agent_names = {}
        self._agent_types = {}
        self._event_log = []
        self._max_events = 500
        
        self._callbacks = []
        self._lock = threading.Lock()

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
        
        self._compute_location_positions()

        return self

    def _compute_location_positions(self):
        locations = list(self.location_graph.nodes.keys())
        n = len(locations)
        
        center_x = 450
        center_y = 350
        radius = 280
        
        self._location_positions = {}
        for i, loc_id in enumerate(locations):
            import math
            angle = (2 * math.pi * i) / n - math.pi / 2
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            
            self._location_positions[loc_id] = {"x": x, "y": y}

    def spawn_agents(self, count=None):
        self.agent_manager = AgentManager()

        num_agents = count or self.simulation_config.initial_agent_count
        spawn_locs = self.simulation_config.spawn_locations
        if not spawn_locs:
            spawn_locs = list(self.location_graph.nodes.keys())

        rng = random.Random(self.simulation_config.random_seed)
        
        self._agent_names = {}
        self._agent_types = {}
        
        names_pool = [
            "Ada", "Basil", "Cora", "Dane", "Ella", "Finn", "Gwen", "Hugo",
            "Iris", "Joel", "Kira", "Liam", "Maya", "Noel", "Opal", "Paul",
            "Quinn", "Rosa", "Seth", "Tara", "Umar", "Vera", "Wade", "Xena",
        ]
        
        type_weights = {
            "farmer": 3,
            "trader": 2,
            "crafter": 2,
            "gatherer": 2,
            "leader": 1,
            "specialist": 1,
            "cooperator": 2,
            "opportunist": 1,
        }
        
        weighted_types = []
        for t, w in type_weights.items():
            weighted_types.extend([t] * w)

        for i in range(num_agents):
            name = names_pool[i] if i < len(names_pool) else f"Agent_{i}"
            agent_type = rng.choice(weighted_types)
            location = rng.choice(spawn_locs)
            needs = dict(self.simulation_config.starting_needs)

            agent_id = self.agent_manager.spawn_agent(
                name=name,
                location=location,
                capacity=self.simulation_config.agent_capacity,
                needs=needs,
            )
            
            self._agent_names[agent_id] = name
            self._agent_types[agent_id] = agent_type

        return self

    def setup_logging(self):
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        log_path = output_path / "events.jsonl"

        self.event_logger = EventLogger(
            output_path=str(log_path) if self.simulation_config.log_enabled else None,
            buffer_size=self.simulation_config.log_buffer_size,
            compress=False,
            auto_flush=True,
        )

        snapshot_dir = output_path / "snapshots"

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
        
        self.trade_analyzer = TradeNetworkAnalyzer()
        self.wealth_tracker = WealthTracker(self.agent_manager)
        self.specialization_detector = SpecializationDetector(window_size=100)
        self.group_manager = GroupManager(self.agent_manager)
        self.governance_system = GovernanceSystem(self.group_manager)

        if self.use_llm:
            self._setup_llm_components()
        else:
            self.action_provider = DummyActionProvider(
                location_graph=self.location_graph,
                agent_manager=self.agent_manager,
            )
            if self.simulation_config.random_seed:
                self.action_provider.set_seed(self.simulation_config.random_seed)

        return self

    def _setup_llm_components(self):
        api_key = os.getenv("API_KEY")
        base_url = os.getenv("BASE_URL")
        model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        
        if not api_key:
            raise ValueError("API_KEY environment variable not set")
        
        self.model_registry = ModelRegistry.create_single_model_registry(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            max_tokens=1024,
            temperature=0.7,
        )
        
        self.inference_client = InferenceClient(
            default_api_key=api_key,
            default_base_url=base_url,
            max_retries=3,
            retry_delay=1.0,
            timeout=60.0,
        )
        
        self.memory_subsystem = MemorySubsystem(
            short_term_capacity=50,
            distill_interval=50,
        )
        
        self.role_initializer = RoleInitializer(
            seed=self.simulation_config.random_seed
        )
        
        self.action_provider = LLMActionProvider(
            agent_manager=self.agent_manager,
            location_graph=self.location_graph,
            message_bus=self.message_bus,
            action_interpreter=self.action_interpreter,
            model_registry=self.model_registry,
            inference_client=self.inference_client,
            memory_subsystem=self.memory_subsystem,
            role_initializer=self.role_initializer,
            batch_inference=False,
        )
        
        self.action_provider.initialize_all_agents()

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
            enable_live_logging=False,
        )

        if self.simulation_config.agent_order_randomize:
            self.tick_engine.agent_order_seed = self.simulation_config.random_seed or 42

        self.hook_manager.create_engine_hooks(self.tick_engine)
        
        self.tick_engine.register_hook("after_agent_action", self._on_agent_action)
        self.tick_engine.register_hook("after_tick_complete", self._on_tick_complete)

        self._initialized = True
        return self

    def initialize(self, agent_count=None):
        return (
            self.load_configs()
            .create_world()
            .spawn_agents(count=agent_count)
            .setup_logging()
            .setup_components()
            .setup_hooks()
            .create_engine()
        )
        
    def _on_agent_action(self, engine, tick, agent_id, outcome):
        action = outcome.action
        action_type = action.action_type.name
        
        details = {}
        reasoning = ""
        
        if hasattr(action, "destination"):
            details["destination"] = action.destination
        if hasattr(action, "resource_type"):
            details["resource_type"] = action.resource_type
            details["amount"] = getattr(action, "amount", 1)
        if hasattr(action, "target_agent_id"):
            details["target"] = action.target_agent_id
        if hasattr(action, "content"):
            details["content"] = action.content[:100] if action.content else ""
        if hasattr(action, "reason"):
            reasoning = action.reason or ""
            
        if self.use_llm and hasattr(self.action_provider, "get_last_action_metadata"):
            metadata = self.action_provider.get_last_action_metadata(agent_id)
            if metadata and metadata.get("reasoning"):
                reasoning = metadata["reasoning"]
        
        with self._lock:
            self._agent_actions[agent_id] = {
                "tick": tick,
                "action_type": action_type,
                "details": details,
                "success": outcome.succeeded,
                "message": outcome.message,
            }
            self._agent_reasoning[agent_id] = reasoning
            
        self.specialization_detector.record_action(agent_id, tick, action_type, details)
        
        if action_type == "TRADE_PROPOSAL":
            offered = getattr(action, "offered_items", [])
            requested = getattr(action, "requested_items", [])
            target = getattr(action, "target_agent_id", "")
            self.trade_analyzer.record_trade(
                agent_id, target, tick, 
                [{"item_type": i.item_type, "quantity": i.quantity} for i in offered],
                [{"item_type": i.item_type, "quantity": i.quantity} for i in requested],
            )
            
        event = {
            "tick": tick,
            "agent_id": agent_id,
            "type": action_type,
            "details": details,
            "success": outcome.succeeded,
            "message": outcome.message,
            "reasoning": reasoning[:200] if reasoning else "",
            "timestamp": time.time(),
        }
        
        with self._lock:
            self._event_log.append(event)
            if len(self._event_log) > self._max_events:
                self._event_log.pop(0)
                
    def _on_tick_complete(self, engine, tick, stats):
        self.wealth_tracker.calculate_metrics(tick)
        
        for callback in self._callbacks:
            try:
                callback(self, tick, stats)
            except Exception:
                pass
    
    def add_tick_callback(self, callback):
        self._callbacks.append(callback)
        
    def remove_tick_callback(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def start(self, tick_delay=1.0):
        if not self._initialized:
            raise RuntimeError("Simulation not initialized")
        if self._running:
            return
            
        self._tick_delay = tick_delay
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
    def _run_loop(self):
        while self._running:
            if self._paused:
                time.sleep(0.1)
                continue
                
            self.tick_engine.execute_tick()
            time.sleep(self._tick_delay)
            
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
            
    def pause(self):
        self._paused = True
        
    def resume(self):
        self._paused = False
        
    def step(self):
        if not self._initialized:
            raise RuntimeError("Simulation not initialized")
        return self.tick_engine.execute_tick()
        
    def set_tick_delay(self, delay):
        self._tick_delay = max(0.1, delay)
        
    def get_state(self):
        agents = []
        for agent in self.agent_manager.list_agents():
            loc = agent.location
            pos = self._location_positions.get(loc, {"x": 450, "y": 350})
            
            jitter_x = (hash(agent.id) % 80) - 40
            jitter_y = (hash(agent.id + "y") % 80) - 40
            
            agent_type = self._agent_types.get(agent.id, "generalist")
            if self.use_llm and hasattr(self.action_provider, "_agent_types"):
                agent_type = self.action_provider._agent_types.get(agent.id, agent_type)
            
            agent_name = self._agent_names.get(agent.id, agent.name)
            display_name = f"{agent_name} ({agent_type.title()})"
            
            last_action = self._agent_actions.get(agent.id, {})
            reasoning = self._agent_reasoning.get(agent.id, "")
            
            agents.append({
                "id": agent.id,
                "name": display_name,
                "rawName": agent_name,
                "location": loc,
                "x": pos["x"] + jitter_x,
                "y": pos["y"] + jitter_y,
                "inventory": dict(agent.inventory),
                "needs": dict(agent.needs),
                "skills": dict(agent.skills),
                "capacity": agent.capacity,
                "type": agent_type,
                "lastAction": last_action,
                "reasoning": reasoning,
            })
            
        locations = []
        for loc_id, node in self.location_graph.nodes.items():
            pos = self._location_positions.get(loc_id, {"x": 450, "y": 350})
            locations.append({
                "id": loc_id,
                "name": node.name,
                "type": node.location_type,
                "x": pos["x"],
                "y": pos["y"],
                "resources": dict(node.resource_richness),
            })
            
        return {
            "tick": self.tick_engine.current_tick,
            "running": self._running and not self._paused,
            "paused": self._paused,
            "agents": agents,
            "locations": locations,
        }
        
    def get_metrics(self):
        wealth_metrics = self.wealth_tracker._metrics_history[-1] if self.wealth_tracker._metrics_history else None
        trade_metrics = self.trade_analyzer.get_network_metrics(self.tick_engine.current_tick)
        spec_metrics = self.specialization_detector.get_specialization_metrics(self.tick_engine.current_tick)
        
        agent_type_counts = defaultdict(int)
        for agent_type in self._agent_types.values():
            agent_type_counts[agent_type] += 1
        if self.use_llm and hasattr(self.action_provider, "_agent_types"):
            agent_type_counts = defaultdict(int)
            for agent_type in self.action_provider._agent_types.values():
                agent_type_counts[agent_type] += 1
            
        groups = []
        for group in self.group_manager._groups.values():
            groups.append({
                "id": group.group_id,
                "name": group.name,
                "type": group.group_type.name,
                "memberCount": group.get_member_count(),
                "treasury": dict(group.treasury),
            })
            
        return {
            "tick": self.tick_engine.current_tick,
            "agentCount": self.agent_manager.agent_count(),
            "wealth": wealth_metrics.to_dict() if wealth_metrics else {},
            "trade": trade_metrics,
            "specialization": spec_metrics,
            "agentTypes": dict(agent_type_counts),
            "groups": groups,
            "tradeVolume": self.trade_analyzer.get_trade_volume_over_time(50),
            "giniHistory": self.wealth_tracker.get_gini_history()[-50:],
        }
        
    def get_events(self, limit=100):
        with self._lock:
            return list(self._event_log[-limit:])
            
    def get_agent_detail(self, agent_id):
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return None
            
        messages = []
        inbox = self.message_bus.get_inbox(agent_id, limit=20)
        for msg in inbox:
            messages.append({
                "sender": msg.sender_id,
                "content": msg.content,
                "timestamp": msg.timestamp,
            })
            
        profession = self.specialization_detector.detect_profession(agent_id)
        
        return {
            "id": agent.id,
            "name": agent.name,
            "location": agent.location,
            "inventory": dict(agent.inventory),
            "needs": dict(agent.needs),
            "skills": dict(agent.skills),
            "capacity": agent.capacity,
            "lastAction": self._agent_actions.get(agent_id, {}),
            "reasoning": self._agent_reasoning.get(agent_id, ""),
            "messages": messages,
            "profession": profession.to_dict() if profession else None,
            "groups": [g.group_id for g in self.group_manager._groups.values() if g.is_member(agent_id)],
        }
        
    def cleanup(self):
        self.stop()
        if self.event_logger:
            self.event_logger.close()
