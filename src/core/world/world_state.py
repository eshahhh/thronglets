class WorldState:
    def __init__(self, tick=0, locations=None, resource_nodes=None, agents=None, config=None):
        self.tick = tick
        self.locations = {} if locations is None else locations
        self.resource_nodes = {} if resource_nodes is None else resource_nodes
        self.agents = {} if agents is None else agents
        self.config = {} if config is None else config

    def next_tick(self):
        return WorldState(
            self.tick + 1,
            dict(self.locations),
            dict(self.resource_nodes),
            dict(self.agents),
            self.config,
        )

    def to_dict(self):
        return {
            "tick": self.tick,
            "locations": self.locations,
            "resource_nodes": self.resource_nodes,
            "agents": self.agents,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            tick=data.get("tick", 0),
            locations=data.get("locations", {}),
            resource_nodes=data.get("resource_nodes", {}),
            agents=data.get("agents", {}),
            config=data.get("config", {}),
        )
