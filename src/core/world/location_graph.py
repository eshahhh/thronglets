from dataclasses import field
from dataclasses import dataclass

@dataclass
class LocationNode:
    def __init__(self, id, name, location_type, resource_richness=None, access_cost=1.0, attributes=None):
        self.id = id
        self.name = name
        self.location_type = location_type
        self.resource_richness = resource_richness if resource_richness is not None else {}
        self.access_cost = access_cost
        self.attributes = attributes if attributes is not None else {}

@dataclass
class LocationEdge:
    def __init__(self, from_id, to_id, distance=1.0, difficulty=1.0, bidirectional=True, attributes=None):
        self.from_id = from_id
        self.to_id = to_id
        self.distance = distance
        self.difficulty = difficulty
        self.bidirectional = bidirectional
        self.attributes = attributes if attributes is not None else {}

class LocationGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self._adjacency = {}

    def add_node(self, node):
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []

    def add_edge(self, edge):
        self.edges.append(edge)
        if edge.from_id not in self._adjacency:
            self._adjacency[edge.from_id] = []
        self._adjacency[edge.from_id].append(edge.to_id)
        if edge.bidirectional:
            if edge.to_id not in self._adjacency:
                self._adjacency[edge.to_id] = []
            self._adjacency[edge.to_id].append(edge.from_id)

    def get_neighbors(self, location_id):
        return self._adjacency.get(location_id, [])

    def get_node(self, location_id):
        return self.nodes.get(location_id)

    def get_edge(self, from_id, to_id):
        for edge in self.edges:
            if edge.from_id == from_id and edge.to_id == to_id:
                return edge
            if edge.bidirectional and edge.from_id == to_id and edge.to_id == from_id:
                return edge
        return None

    def travel_cost(self, from_id, to_id):
        edge = self.get_edge(from_id, to_id)
        if edge is None:
            return float('inf')
        dest = self.get_node(to_id)
        base_cost = edge.distance * edge.difficulty
        if dest:
            base_cost *= dest.access_cost
        return base_cost

    @classmethod
    def from_config(cls, config):
        graph = cls()
        for node_data in config.get("nodes", []):
            node = LocationNode(
                id=node_data["id"],
                name=node_data.get("name", node_data["id"]),
                location_type=node_data.get("type", "generic"),
                resource_richness=node_data.get("resources", {}),
                access_cost=node_data.get("access_cost", 1.0),
                attributes=node_data.get("attributes", {}),
            )
            graph.add_node(node)
        for edge_data in config.get("edges", []):
            edge = LocationEdge(
                from_id=edge_data["from"],
                to_id=edge_data["to"],
                distance=edge_data.get("distance", 1.0),
                difficulty=edge_data.get("difficulty", 1.0),
                bidirectional=edge_data.get("bidirectional", True),
                attributes=edge_data.get("attributes", {}),
            )
            graph.add_edge(edge)
        return graph
