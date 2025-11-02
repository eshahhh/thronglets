from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class TradeEdge:
    source = ""
    target = ""
    weight = 1
    total_volume = 0.0
    items_traded = field(default_factory=dict)
    first_trade_tick = 0
    last_trade_tick = 0

    def to_dict(self):
        return {
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "total_volume": self.total_volume,
            "items_traded": self.items_traded,
            "first_trade_tick": self.first_trade_tick,
            "last_trade_tick": self.last_trade_tick,
        }


@dataclass
class TradeGraph:
    nodes = set()
    edges = dict()

    def get_degree(self, node):
        count = 0
        for (s, t) in self.edges.keys():
            if s == node or t == node:
                count += 1
        return count

    def get_neighbors(self, node):
        neighbors = set()
        for (s, t) in self.edges.keys():
            if s == node:
                neighbors.add(t)
            elif t == node:
                neighbors.add(s)
        return neighbors

    def get_edge(self, source, target):
        return self.edges.get((source, target)) or self.edges.get((target, source))


class TradeNetworkAnalyzer:
    def __init__(self):
        self._edges = {}
        self._nodes = set()
        self._trade_history = []

        self._centrality_cache = {}
        self._community_cache = {}
        self._last_analysis_tick = -1

    def record_trade(
        self,
        proposer_id,
        target_id,
        tick,
        offered_items,
        requested_items,
        value=0.0,
    ):
        self._nodes.add(proposer_id)
        self._nodes.add(target_id)

        edge_key = tuple(sorted([proposer_id, target_id]))

        if edge_key not in self._edges:
            self._edges[edge_key] = TradeEdge(
                source=edge_key[0],
                target=edge_key[1],
                first_trade_tick=tick,
            )

        edge = self._edges[edge_key]
        edge.weight += 1
        edge.total_volume += value
        edge.last_trade_tick = tick

        for item in offered_items + requested_items:
            item_type = item.get("item_type", "")
            quantity = item.get("quantity", 0)
            edge.items_traded[item_type] = edge.items_traded.get(item_type, 0) + quantity

        self._trade_history.append({
            "tick": tick,
            "proposer": proposer_id,
            "target": target_id,
            "value": value,
        })

        self._centrality_cache.clear()
        self._community_cache.clear()

    def get_graph(self):
        return TradeGraph(
            nodes=self._nodes.copy(),
            edges=dict(self._edges),
        )

    def calculate_degree_centrality(self):
        if "degree" in self._centrality_cache:
            return self._centrality_cache["degree"]

        n = len(self._nodes)
        if n <= 1:
            return {node: 0.0 for node in self._nodes}

        centrality = {}
        for node in self._nodes:
            degree = sum(
                1 for (s, t) in self._edges.keys()
                if s == node or t == node
            )
            centrality[node] = degree / (n - 1)

        self._centrality_cache["degree"] = centrality
        return centrality

    def calculate_weighted_degree_centrality(self):
        if "weighted_degree" in self._centrality_cache:
            return self._centrality_cache["weighted_degree"]

        weighted = defaultdict(float)

        for edge in self._edges.values():
            weighted[edge.source] += edge.weight
            weighted[edge.target] += edge.weight

        max_weight = max(weighted.values()) if weighted else 1.0

        centrality = {
            node: weighted.get(node, 0) / max_weight
            for node in self._nodes
        }

        self._centrality_cache["weighted_degree"] = centrality
        return centrality

    def calculate_betweenness_centrality(self):
        if "betweenness" in self._centrality_cache:
            return self._centrality_cache["betweenness"]

        n = len(self._nodes)
        if n <= 2:
            return {node: 0.0 for node in self._nodes}

        betweenness = {node: 0.0 for node in self._nodes}
        nodes_list = list(self._nodes)

        def get_neighbors(node):
            neighbors = set()
            for (s, t) in self._edges.keys():
                if s == node:
                    neighbors.add(t)
                elif t == node:
                    neighbors.add(s)
            return neighbors

        for source in nodes_list:
            dist = {source: 0}
            pred = defaultdict(list)
            sigma = defaultdict(float)
            sigma[source] = 1.0

            queue = [source]
            stack = []

            while queue:
                v = queue.pop(0)
                stack.append(v)

                for w in get_neighbors(v):
                    if w not in dist:
                        dist[w] = dist[v] + 1
                        queue.append(w)

                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        pred[w].append(v)

            delta = defaultdict(float)

            while stack:
                w = stack.pop()
                for v in pred[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                if w != source:
                    betweenness[w] += delta[w]

        norm = 2.0 / ((n - 1) * (n - 2)) if n > 2 else 1.0
        betweenness = {node: val * norm for node, val in betweenness.items()}

        self._centrality_cache["betweenness"] = betweenness
        return betweenness

    def detect_communities(self):
        if self._community_cache:
            return self._community_cache

        community = {node: i for i, node in enumerate(self._nodes)}

        def get_neighbors(node):
            neighbors = set()
            for (s, t) in self._edges.keys():
                if s == node:
                    neighbors.add(t)
                elif t == node:
                    neighbors.add(s)
            return neighbors

        for _ in range(10):
            changed = False
            for node in self._nodes:
                neighbors = get_neighbors(node)
                if not neighbors:
                    continue

                community_counts = defaultdict(int)
                for neighbor in neighbors:
                    edge = self._edges.get(tuple(sorted([node, neighbor])))
                    weight = edge.weight if edge else 1
                    community_counts[community[neighbor]] += weight

                if community_counts:
                    best_community = max(community_counts, key=community_counts.get)
                    if best_community != community[node]:
                        community[node] = best_community
                        changed = True

            if not changed:
                break

        unique_communities = sorted(set(community.values()))
        community_map = {old: new for new, old in enumerate(unique_communities)}
        community = {node: community_map[c] for node, c in community.items()}

        self._community_cache = community
        return community

    def get_community_structure(self):
        communities = self.detect_communities()

        structure = defaultdict(list)
        for node, community_id in communities.items():
            structure[community_id].append(node)

        return dict(structure)

    def calculate_clustering_coefficient(self, node):
        neighbors = set()
        for (s, t) in self._edges.keys():
            if s == node:
                neighbors.add(t)
            elif t == node:
                neighbors.add(s)

        k = len(neighbors)
        if k < 2:
            return 0.0

        neighbor_edges = 0
        neighbors_list = list(neighbors)
        for i, n1 in enumerate(neighbors_list):
            for n2 in neighbors_list[i + 1:]:
                edge_key = tuple(sorted([n1, n2]))
                if edge_key in self._edges:
                    neighbor_edges += 1

        max_edges = k * (k - 1) / 2
        return neighbor_edges / max_edges if max_edges > 0 else 0.0

    def get_network_metrics(self, tick):
        n = len(self._nodes)
        m = len(self._edges)

        max_edges = n * (n - 1) / 2 if n > 1 else 1
        density = m / max_edges if max_edges > 0 else 0.0

        clustering_coeffs = [
            self.calculate_clustering_coefficient(node)
            for node in self._nodes
        ]
        avg_clustering = (
            sum(clustering_coeffs) / len(clustering_coeffs)
            if clustering_coeffs else 0.0
        )

        degree_centrality = self.calculate_degree_centrality()
        degree_values = list(degree_centrality.values())
        avg_degree = sum(degree_values) / len(degree_values) if degree_values else 0.0

        communities = self.detect_communities()
        num_communities = len(set(communities.values()))

        return {
            "tick": tick,
            "num_nodes": n,
            "num_edges": m,
            "density": density,
            "avg_clustering": avg_clustering,
            "avg_degree": avg_degree,
            "num_communities": num_communities,
        }

    def get_top_traders(self, limit=10):
        weighted_centrality = self.calculate_weighted_degree_centrality()
        sorted_traders = sorted(
            weighted_centrality.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_traders[:limit]

    def get_trade_volume_over_time(self, window=50):
        if not self._trade_history:
            return []

        volume_by_tick = defaultdict(int)
        for trade in self._trade_history:
            volume_by_tick[trade["tick"]] += 1

        ticks = sorted(volume_by_tick.keys())
        if not ticks:
            return []

        return [(t, volume_by_tick[t]) for t in ticks[-window:]]

    def to_dict(self):
        return {
            "num_nodes": len(self._nodes),
            "num_edges": len(self._edges),
            "edges": [e.to_dict() for e in self._edges.values()],
            "degree_centrality": self.calculate_degree_centrality(),
            "communities": self.detect_communities(),
        }
