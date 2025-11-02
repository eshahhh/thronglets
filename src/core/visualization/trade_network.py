from dataclasses import dataclass, field
from collections import defaultdict
import json
import math

@dataclass
class TradeEdge:
    source: str
    target: str
    resource: str
    volume: float = 0.0
    count: int = 0
    avg_price: float = 0.0
    
@dataclass
class TradeNode:
    agent_id: str
    total_trades: int = 0
    total_volume: float = 0.0
    resources_traded: dict = field(default_factory=dict)
    trade_partners: set = field(default_factory=set)
    x: float = 0.0
    y: float = 0.0

class TradeNetworkVisualizer:
    def __init__(self):
        self._nodes = {}
        self._edges = {}
        self._trade_history = []
        
    def record_trade(self, buyer_id, seller_id, resource, amount, price, tick):
        if buyer_id not in self._nodes:
            self._nodes[buyer_id] = TradeNode(agent_id=buyer_id)
        if seller_id not in self._nodes:
            self._nodes[seller_id] = TradeNode(agent_id=seller_id)
            
        buyer = self._nodes[buyer_id]
        seller = self._nodes[seller_id]
        
        buyer.total_trades += 1
        seller.total_trades += 1
        buyer.total_volume += amount
        seller.total_volume += amount
        buyer.trade_partners.add(seller_id)
        seller.trade_partners.add(buyer_id)
        
        buyer.resources_traded[resource] = buyer.resources_traded.get(resource, 0) + amount
        seller.resources_traded[resource] = seller.resources_traded.get(resource, 0) + amount
        
        edge_key = f"{buyer_id}_{seller_id}_{resource}"
        rev_key = f"{seller_id}_{buyer_id}_{resource}"
        
        if edge_key in self._edges:
            edge = self._edges[edge_key]
        elif rev_key in self._edges:
            edge = self._edges[rev_key]
            edge_key = rev_key
        else:
            edge = TradeEdge(source=buyer_id, target=seller_id, resource=resource)
            self._edges[edge_key] = edge
            
        edge.volume += amount
        edge.count += 1
        edge.avg_price = ((edge.avg_price * (edge.count - 1)) + price) / edge.count
        
        self._trade_history.append({
            "tick": tick,
            "buyer": buyer_id,
            "seller": seller_id,
            "resource": resource,
            "amount": amount,
            "price": price,
        })
        
    def compute_layout(self, width=800, height=600):
        if not self._nodes:
            return
            
        n = len(self._nodes)
        nodes = list(self._nodes.values())
        
        angle_step = 2 * math.pi / n if n > 0 else 0
        cx, cy = width / 2, height / 2
        radius = min(width, height) * 0.35
        
        for i, node in enumerate(nodes):
            angle = i * angle_step
            node.x = cx + radius * math.cos(angle)
            node.y = cy + radius * math.sin(angle)
            
        for _ in range(50):
            self._force_directed_step(nodes, width, height)
            
    def _force_directed_step(self, nodes, width, height):
        k = math.sqrt((width * height) / max(len(nodes), 1)) * 0.3
        
        forces = {n.agent_id: [0.0, 0.0] for n in nodes}
        
        for i, n1 in enumerate(nodes):
            for j, n2 in enumerate(nodes):
                if i >= j:
                    continue
                dx = n1.x - n2.x
                dy = n1.y - n2.y
                dist = math.sqrt(dx*dx + dy*dy) or 0.01
                
                repel = k * k / dist
                forces[n1.agent_id][0] += (dx / dist) * repel
                forces[n1.agent_id][1] += (dy / dist) * repel
                forces[n2.agent_id][0] -= (dx / dist) * repel
                forces[n2.agent_id][1] -= (dy / dist) * repel
                
        for edge in self._edges.values():
            if edge.source not in self._nodes or edge.target not in self._nodes:
                continue
            n1 = self._nodes[edge.source]
            n2 = self._nodes[edge.target]
            dx = n2.x - n1.x
            dy = n2.y - n1.y
            dist = math.sqrt(dx*dx + dy*dy) or 0.01
            
            attract = dist * dist / k * (1 + edge.count * 0.1)
            forces[n1.agent_id][0] += (dx / dist) * attract
            forces[n1.agent_id][1] += (dy / dist) * attract
            forces[n2.agent_id][0] -= (dx / dist) * attract
            forces[n2.agent_id][1] -= (dy / dist) * attract
            
        damping = 0.3
        for node in nodes:
            fx, fy = forces[node.agent_id]
            node.x += fx * damping
            node.y += fy * damping
            node.x = max(50, min(width - 50, node.x))
            node.y = max(50, min(height - 50, node.y))
            
    def get_network_stats(self):
        if not self._nodes:
            return {"nodes": 0, "edges": 0, "density": 0, "avg_degree": 0}
            
        n = len(self._nodes)
        e = len(self._edges)
        max_edges = n * (n - 1) / 2 if n > 1 else 1
        density = e / max_edges if max_edges > 0 else 0
        
        degrees = [len(node.trade_partners) for node in self._nodes.values()]
        avg_degree = sum(degrees) / n if n > 0 else 0
        
        return {
            "nodes": n,
            "edges": e,
            "density": density,
            "avg_degree": avg_degree,
            "total_trades": sum(node.total_trades for node in self._nodes.values()) // 2,
            "total_volume": sum(node.total_volume for node in self._nodes.values()) / 2,
        }
        
    def get_top_traders(self, limit=10):
        sorted_nodes = sorted(
            self._nodes.values(),
            key=lambda n: n.total_volume,
            reverse=True
        )
        return [
            {
                "agent_id": n.agent_id,
                "total_trades": n.total_trades,
                "total_volume": n.total_volume,
                "partner_count": len(n.trade_partners),
                "top_resource": max(n.resources_traded.items(), key=lambda x: x[1])[0] if n.resources_traded else None,
            }
            for n in sorted_nodes[:limit]
        ]
        
    def get_resource_flows(self):
        flows = defaultdict(lambda: {"volume": 0, "count": 0, "avg_price": 0})
        
        for edge in self._edges.values():
            r = edge.resource
            flows[r]["volume"] += edge.volume
            flows[r]["count"] += edge.count
            
        for r, data in flows.items():
            if data["count"] > 0:
                matching_edges = [e for e in self._edges.values() if e.resource == r]
                data["avg_price"] = sum(e.avg_price * e.count for e in matching_edges) / data["count"]
                
        return dict(flows)
        
    def to_json(self):
        self.compute_layout()
        
        nodes_data = [
            {
                "id": n.agent_id,
                "x": n.x,
                "y": n.y,
                "trades": n.total_trades,
                "volume": n.total_volume,
                "partners": len(n.trade_partners),
            }
            for n in self._nodes.values()
        ]
        
        edges_data = [
            {
                "source": e.source,
                "target": e.target,
                "resource": e.resource,
                "volume": e.volume,
                "count": e.count,
                "avg_price": e.avg_price,
            }
            for e in self._edges.values()
        ]
        
        return json.dumps({
            "nodes": nodes_data,
            "edges": edges_data,
            "stats": self.get_network_stats(),
        }, indent=2)
        
    def render_ascii(self, width=60, height=30):
        if not self._nodes:
            return "No trade data to visualize"
            
        self.compute_layout(width, height)
        
        grid = [[' ' for _ in range(width)] for _ in range(height)]
        
        for edge in self._edges.values():
            if edge.source not in self._nodes or edge.target not in self._nodes:
                continue
            n1 = self._nodes[edge.source]
            n2 = self._nodes[edge.target]
            x1, y1 = int(n1.x * width / 800), int(n1.y * height / 600)
            x2, y2 = int(n2.x * width / 800), int(n2.y * height / 600)
            
            steps = max(abs(x2-x1), abs(y2-y1), 1)
            for s in range(1, steps):
                x = x1 + (x2-x1) * s // steps
                y = y1 + (y2-y1) * s // steps
                if 0 <= x < width and 0 <= y < height:
                    if grid[y][x] == ' ':
                        grid[y][x] = '·'
                        
        for node in self._nodes.values():
            x = int(node.x * width / 800)
            y = int(node.y * height / 600)
            if 0 <= x < width-1 and 0 <= y < height:
                label = node.agent_id[:2].upper()
                grid[y][x] = label[0]
                if x+1 < width:
                    grid[y][x+1] = label[1] if len(label) > 1 else ' '
                    
        lines = [''.join(row) for row in grid]
        lines.append(f"\nNodes: {len(self._nodes)} | Edges: {len(self._edges)} | Trades: {sum(e.count for e in self._edges.values())}")
        
        return '\n'.join(lines)
        
    def export_graphviz(self):
        lines = ["digraph TradeNetwork {"]
        lines.append("  rankdir=LR;")
        lines.append('  node [shape=circle, style=filled];')
        
        max_vol = max((n.total_volume for n in self._nodes.values()), default=1)
        for node in self._nodes.values():
            size = 0.5 + (node.total_volume / max_vol) * 1.5
            lines.append(f'  "{node.agent_id}" [width={size:.2f}];')
            
        max_edge = max((e.count for e in self._edges.values()), default=1)
        for edge in self._edges.values():
            weight = 1 + (edge.count / max_edge) * 4
            lines.append(f'  "{edge.source}" -> "{edge.target}" [penwidth={weight:.1f}, label="{edge.resource}"];')
            
        lines.append("}")
        return '\n'.join(lines)
