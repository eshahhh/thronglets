import yaml
from pathlib import Path


class ConfigLoader:
    def __init__(self, config_dir=None):
        if config_dir is None:
            self.config_dir = Path(__file__).parent.parent.parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

    def _load_yaml(self, filename):
        filepath = self.config_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_world(self, filename="world.yaml"):
        return self._load_yaml(filename)

    def load_simulation(self, filename="simulation.yaml"):
        return self._load_yaml(filename)

    def load_resources(self, filename="resources.yaml"):
        return self._load_yaml(filename)

    def load_agents(self, filename="agents.yaml"):
        return self._load_yaml(filename)

    def load_all(self):
        return {
            "world": self.load_world(),
            "simulation": self.load_simulation(),
            "resources": self.load_resources(),
            "agents": self.load_agents(),
        }


class WorldConfig:
    def __init__(self, raw_config):
        self.locations = raw_config.get("locations", [])
        self.edges = raw_config.get("edges", [])

    def get_location_ids(self):
        return [loc["id"] for loc in self.locations]

    def get_location(self, location_id):
        for loc in self.locations:
            if loc["id"] == location_id:
                return loc
        return None

    def to_location_graph_config(self):
        nodes = []
        for loc in self.locations:
            nodes.append({
                "id": loc["id"],
                "name": loc.get("name", loc["id"]),
                "type": loc.get("type", "generic"),
                "resources": loc.get("resources", {}),
                "access_cost": loc.get("access_cost", 1.0),
                "attributes": loc.get("attributes", {}),
            })

        edges = []
        for edge in self.edges:
            edges.append({
                "from": edge["from"],
                "to": edge["to"],
                "distance": edge.get("distance", 1.0),
                "difficulty": edge.get("difficulty", 1.0),
                "bidirectional": edge.get("bidirectional", True),
                "attributes": edge.get("attributes", {}),
            })

        return {"nodes": nodes, "edges": edges}


class SimulationConfig:
    def __init__(self, raw_config):
        self.tick_rate = raw_config.get("tick_rate", 1.0)
        self.termination = raw_config.get("termination", {})
        self.warmup = raw_config.get("warmup", {})
        self.snapshots = raw_config.get("snapshots", {})
        self.logging = raw_config.get("logging", {})
        self.agent_settings = raw_config.get("agent_settings", {})
        self.need_decay = raw_config.get("need_decay", {})
        self.hooks = raw_config.get("hooks", {})
        self.random_seed = raw_config.get("random_seed")
        self.agent_order_randomize = raw_config.get("agent_order_randomize", True)

    @property
    def max_ticks(self):
        return self.termination.get("max_ticks", 10000)

    @property
    def min_agents(self):
        return self.termination.get("min_agents", 1)

    @property
    def warmup_enabled(self):
        return self.warmup.get("enabled", False)

    @property
    def warmup_ticks(self):
        return self.warmup.get("ticks", 0)

    @property
    def snapshot_enabled(self):
        return self.snapshots.get("enabled", True)

    @property
    def snapshot_interval(self):
        return self.snapshots.get("interval", 100)

    @property
    def snapshot_compress(self):
        return self.snapshots.get("compress", True)

    @property
    def snapshot_output_dir(self):
        return self.snapshots.get("output_dir", "output/snapshots")

    @property
    def log_enabled(self):
        return self.logging.get("enabled", True)

    @property
    def log_output_path(self):
        return self.logging.get("output_path", "output/events.jsonl")

    @property
    def log_buffer_size(self):
        return self.logging.get("buffer_size", 1000)

    @property
    def initial_agent_count(self):
        return self.agent_settings.get("initial_count", 100)

    @property
    def agent_capacity(self):
        return self.agent_settings.get("capacity", 100)

    @property
    def starting_needs(self):
        return self.agent_settings.get("starting_needs", {
            "food": 100.0,
            "shelter": 100.0,
            "reputation": 50.0,
        })

    @property
    def spawn_locations(self):
        return self.agent_settings.get("spawn_locations", [])

    @property
    def agent_name_prefix(self):
        return self.agent_settings.get("name_prefix", "Agent")


class ResourceConfig:
    def __init__(self, raw_config):
        self.resources = {r["id"]: r for r in raw_config.get("resources", [])}
        self.regeneration = raw_config.get("regeneration", {})
        self.recipes = raw_config.get("recipes", [])
        self.consumption = raw_config.get("consumption", {})

    def get_resource(self, resource_id):
        return self.resources.get(resource_id)

    def get_regen_rate(self, resource_id):
        return self.regeneration.get("rates", {}).get(resource_id, 0.0)

    def get_regen_cap(self, resource_id):
        return self.regeneration.get("caps", {}).get(resource_id, float("inf"))

    def get_all_regen_rates(self):
        return self.regeneration.get("rates", {})

    def get_all_regen_caps(self):
        return self.regeneration.get("caps", {})

    def to_crafting_rules_config(self):
        return {"recipes": self.recipes}

    def get_food_items(self):
        return self.consumption.get("food_items", [])

    def get_shelter_items(self):
        return self.consumption.get("shelter_items", [])

    def get_decay_items(self):
        return {r["id"]: r.get("decay_rate", 0.0) 
                for r in self.resources.values() 
                if r.get("decay_rate", 0.0) > 0}


class AgentConfig:
    def __init__(self, raw_config):
        self.defaults = raw_config.get("defaults", {})
        self.spawn = raw_config.get("spawn", {})
        self.archetypes = raw_config.get("archetypes", [])
        self.behavior = raw_config.get("behavior", {})

    @property
    def default_capacity(self):
        return self.defaults.get("capacity", 100)

    @property
    def default_needs(self):
        return self.defaults.get("starting_needs", {
            "food": 100.0,
            "shelter": 100.0,
            "reputation": 50.0,
        })

    @property
    def default_skills(self):
        return self.defaults.get("starting_skills", {})

    @property
    def default_inventory(self):
        return self.defaults.get("starting_inventory", {})

    @property
    def spawn_count(self):
        return self.spawn.get("count", 100)

    @property
    def spawn_locations(self):
        return self.spawn.get("locations", [])

    @property
    def spawn_distribution(self):
        return self.spawn.get("distribution", "random")

    @property
    def name_prefix(self):
        return self.spawn.get("name_prefix", "Agent")

    def get_archetype(self, archetype_id):
        for archetype in self.archetypes:
            if archetype.get("id") == archetype_id:
                return archetype
        return None

    def get_archetype_weights(self):
        return [(a["id"], a.get("weight", 1)) for a in self.archetypes]

    @property
    def hunger_threshold(self):
        return self.behavior.get("hunger_threshold", 30)

    @property
    def shelter_threshold(self):
        return self.behavior.get("shelter_threshold", 20)

    @property
    def trade_willingness(self):
        return self.behavior.get("trade_willingness", 0.5)


def load_configs(config_dir=None):
    loader = ConfigLoader(config_dir)
    raw = loader.load_all()
    return {
        "world": WorldConfig(raw["world"]),
        "simulation": SimulationConfig(raw["simulation"]),
        "resources": ResourceConfig(raw["resources"]),
        "agents": AgentConfig(raw["agents"]),
    }
