from dataclasses import dataclass, field
import json
import math

@dataclass
class AgentSpecialization:
    agent_id = ""
    primary_skill = ""
    skill_levels = field(default_factory=dict)
    production_history = field(default_factory=dict)
    trade_focus = field(default_factory=dict)
    cluster_id = None
    x = 0.0
    y = 0.0

@dataclass
class SpecializationCluster:
    cluster_id = 0
    primary_resource = ""
    members = field(default_factory=list)
    centroid_x = 0.0
    centroid_y = 0.0
    avg_skill_level = 0.0

class SpecializationClusterMap:
    def __init__(self):
        self._agents = {}
        self._clusters = {}
        self._resource_types = set()
        self._next_cluster_id = 0
        
    def record_production(self, agent_id, resource, amount=1):
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentSpecialization(
                agent_id=agent_id,
                primary_skill=resource,
            )
        agent = self._agents[agent_id]
        agent.production_history[resource] = agent.production_history.get(resource, 0) + amount
        agent.skill_levels[resource] = agent.skill_levels.get(resource, 0) + 0.1 * amount
        self._resource_types.add(resource)
        self._update_primary_skill(agent)
        
    def record_skill_level(self, agent_id, skill, level):
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentSpecialization(
                agent_id=agent_id,
                primary_skill=skill,
            )
        self._agents[agent_id].skill_levels[skill] = level
        self._resource_types.add(skill)
        self._update_primary_skill(self._agents[agent_id])
        
    def record_trade_focus(self, agent_id, resource, amount):
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentSpecialization(
                agent_id=agent_id,
                primary_skill=resource,
            )
        agent = self._agents[agent_id]
        agent.trade_focus[resource] = agent.trade_focus.get(resource, 0) + amount
        self._resource_types.add(resource)
        
    def _update_primary_skill(self, agent):
        if agent.skill_levels:
            agent.primary_skill = max(agent.skill_levels.items(), key=lambda x: x[1])[0]
            
    def compute_clusters(self, n_clusters=None):
        if not self._agents:
            return
            
        resources = sorted(self._resource_types)
        if not resources:
            return
            
        if n_clusters is None:
            n_clusters = min(len(resources), max(2, len(self._agents) // 3))
            
        agents = list(self._agents.values())
        
        for agent in agents:
            agent.x, agent.y = self._get_agent_position(agent, resources)
            
        self._clusters.clear()
        for i, resource in enumerate(resources[:n_clusters]):
            cluster = SpecializationCluster(
                cluster_id=i,
                primary_resource=resource,
            )
            self._clusters[i] = cluster
            
        for _ in range(10):
            for agent in agents:
                best_cluster = self._find_nearest_cluster(agent)
                if best_cluster is not None:
                    agent.cluster_id = best_cluster
                    
            for cluster in self._clusters.values():
                cluster.members.clear()
                
            for agent in agents:
                if agent.cluster_id is not None and agent.cluster_id in self._clusters:
                    self._clusters[agent.cluster_id].members.append(agent.agent_id)
                    
            self._update_centroids()
            
    def _get_agent_position(self, agent, resources):
        if len(resources) < 2:
            return (0.5, 0.5)
            
        total_skill = sum(agent.skill_levels.values()) or 1
        normalized = {r: agent.skill_levels.get(r, 0) / total_skill for r in resources}
        
        x = sum(normalized.get(r, 0) * (i + 1) / len(resources) for i, r in enumerate(resources))
        y = sum(normalized.get(r, 0) * ((i % 3) + 1) / 3 for i, r in enumerate(resources))
        
        return (x, y)
        
    def _find_nearest_cluster(self, agent):
        if not self._clusters:
            return None
            
        best_dist = float('inf')
        best_id = None
        
        for cid, cluster in self._clusters.items():
            skill_match = agent.skill_levels.get(cluster.primary_resource, 0)
            dist = -skill_match
            
            if dist < best_dist:
                best_dist = dist
                best_id = cid
                
        return best_id
        
    def _update_centroids(self):
        for cluster in self._clusters.values():
            if not cluster.members:
                continue
                
            x_sum = y_sum = skill_sum = 0
            count = 0
            
            for aid in cluster.members:
                if aid in self._agents:
                    agent = self._agents[aid]
                    x_sum += agent.x
                    y_sum += agent.y
                    skill_sum += agent.skill_levels.get(cluster.primary_resource, 0)
                    count += 1
                    
            if count > 0:
                cluster.centroid_x = x_sum / count
                cluster.centroid_y = y_sum / count
                cluster.avg_skill_level = skill_sum / count
                
    def get_cluster_summary(self):
        self.compute_clusters()
        
        return [
            {
                "cluster_id": c.cluster_id,
                "primary_resource": c.primary_resource,
                "member_count": len(c.members),
                "avg_skill_level": c.avg_skill_level,
                "top_members": c.members[:5],
            }
            for c in sorted(self._clusters.values(), key=lambda x: len(x.members), reverse=True)
        ]
        
    def get_agent_specialization(self, agent_id):
        if agent_id not in self._agents:
            return None
            
        agent = self._agents[agent_id]
        return {
            "agent_id": agent.agent_id,
            "primary_skill": agent.primary_skill,
            "skill_levels": dict(agent.skill_levels),
            "production_history": dict(agent.production_history),
            "cluster_id": agent.cluster_id,
            "cluster_resource": self._clusters[agent.cluster_id].primary_resource if agent.cluster_id in self._clusters else None,
        }
        
    def get_specialization_matrix(self):
        self.compute_clusters()
        
        matrix = {}
        for aid, agent in self._agents.items():
            matrix[aid] = {
                r: agent.skill_levels.get(r, 0)
                for r in self._resource_types
            }
        return matrix
        
    def get_diversity_index(self):
        if len(self._clusters) < 2 or not self._agents:
            return 0.0
            
        cluster_sizes = [len(c.members) for c in self._clusters.values()]
        total = sum(cluster_sizes)
        if total == 0:
            return 0.0
            
        proportions = [s / total for s in cluster_sizes if s > 0]
        shannon = -sum(p * math.log(p) for p in proportions if p > 0)
        max_shannon = math.log(len(proportions)) if proportions else 1
        
        return shannon / max_shannon if max_shannon > 0 else 0
        
    def to_json(self):
        self.compute_clusters()
        
        agents_data = [
            {
                "id": a.agent_id,
                "x": a.x,
                "y": a.y,
                "primary_skill": a.primary_skill,
                "cluster_id": a.cluster_id,
                "skills": dict(a.skill_levels),
            }
            for a in self._agents.values()
        ]
        
        clusters_data = [
            {
                "id": c.cluster_id,
                "resource": c.primary_resource,
                "centroid_x": c.centroid_x,
                "centroid_y": c.centroid_y,
                "member_count": len(c.members),
                "avg_skill": c.avg_skill_level,
            }
            for c in self._clusters.values()
        ]
        
        return json.dumps({
            "agents": agents_data,
            "clusters": clusters_data,
            "diversity_index": self.get_diversity_index(),
            "resource_types": list(self._resource_types),
        }, indent=2)
        
    def render_ascii(self, width=60, height=20):
        self.compute_clusters()
        
        if not self._agents:
            return "No specialization data to visualize"
            
        grid = [[' ' for _ in range(width)] for _ in range(height)]
        
        cluster_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        for aid, agent in self._agents.items():
            x = int(agent.x * (width - 2)) + 1
            y = int(agent.y * (height - 2)) + 1
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))
            
            if agent.cluster_id is not None and agent.cluster_id < len(cluster_chars):
                char = cluster_chars[agent.cluster_id].lower()
            else:
                char = '·'
            grid[y][x] = char
            
        for cid, cluster in self._clusters.items():
            x = int(cluster.centroid_x * (width - 2)) + 1
            y = int(cluster.centroid_y * (height - 2)) + 1
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))
            
            if cid < len(cluster_chars):
                grid[y][x] = cluster_chars[cid]
                
        lines = [f"┌{'─' * width}┐"]
        for row in grid:
            lines.append(f"│{''.join(row)}│")
        lines.append(f"└{'─' * width}┘")
        
        lines.append("\nClusters:")
        for cid, cluster in sorted(self._clusters.items()):
            char = cluster_chars[cid] if cid < len(cluster_chars) else "?"
            lines.append(f"  {char}: {cluster.primary_resource} ({len(cluster.members)} agents)")
            
        lines.append(f"\nDiversity Index: {self.get_diversity_index():.3f}")
        
        return '\n'.join(lines)
