from dataclasses import dataclass, field
from collections import defaultdict
import math


@dataclass
class WealthSnapshot:
    tick: int
    agent_id: str
    total_wealth: float
    inventory_value: float
    need_satisfaction: float


@dataclass
class WealthMetrics:
    tick: int
    total_wealth: float
    mean_wealth: float
    median_wealth: float
    gini_coefficient: float
    top_10_percent_share: float
    bottom_50_percent_share: float
    wealth_mobility: float
    
    def to_dict(self):
        return {
            "tick": self.tick,
            "total_wealth": self.total_wealth,
            "mean_wealth": self.mean_wealth,
            "median_wealth": self.median_wealth,
            "gini_coefficient": self.gini_coefficient,
            "top_10_percent_share": self.top_10_percent_share,
            "bottom_50_percent_share": self.bottom_50_percent_share,
            "wealth_mobility": self.wealth_mobility,
        }


class WealthTracker:
    def __init__(self, agent_manager, price_engine=None):
        self.agent_manager = agent_manager
        self.price_engine = price_engine
        
        self._wealth_history = defaultdict(list)
        self._metrics_history = []
        self._rank_history = defaultdict(list)
        self._max_history = 1000
    
    def set_price_engine(self, price_engine):
        self.price_engine = price_engine
    
    def calculate_agent_wealth(self, agent_id):
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return 0.0
        
        total_wealth = 0.0
        
        for item, quantity in agent.inventory.items():
            if self.price_engine:
                price = self.price_engine.get_price(item)
            else:
                price = 1.0
            total_wealth += quantity * price
        
        need_value = sum(agent.needs.values()) / len(agent.needs) if agent.needs else 0
        total_wealth += need_value * 0.1
        
        return total_wealth
    
    def snapshot_all_agents(self, tick):
        for agent in self.agent_manager.list_agents():
            wealth = self.calculate_agent_wealth(agent.id)
            
            inventory_value = sum(
                qty * (self.price_engine.get_price(item) if self.price_engine else 1.0)
                for item, qty in agent.inventory.items()
            )
            
            need_satisfaction = (
                sum(agent.needs.values()) / len(agent.needs) / 100.0
                if agent.needs else 0.0
            )
            
            snapshot = WealthSnapshot(
                tick=tick,
                agent_id=agent.id,
                total_wealth=wealth,
                inventory_value=inventory_value,
                need_satisfaction=need_satisfaction,
            )
            
            self._wealth_history[agent.id].append(snapshot)
            
            if len(self._wealth_history[agent.id]) > self._max_history:
                self._wealth_history[agent.id].pop(0)
    
    def calculate_gini_coefficient(self, wealth_values):
        if not wealth_values:
            return 0.0
        
        sorted_wealth = sorted(wealth_values)
        n = len(sorted_wealth)
        
        if n == 0 or sum(sorted_wealth) == 0:
            return 0.0
        
        cumulative_wealth = 0
        cumulative_sum = 0
        
        for i, w in enumerate(sorted_wealth):
            cumulative_wealth += (i + 1) * w
            cumulative_sum += w
        
        gini = (2 * cumulative_wealth) / (n * cumulative_sum) - (n + 1) / n
        
        return max(0.0, min(1.0, gini))
    
    def calculate_metrics(self, tick):
        self.snapshot_all_agents(tick)
        
        wealth_values = []
        for agent in self.agent_manager.list_agents():
            wealth_values.append(self.calculate_agent_wealth(agent.id))
        
        if not wealth_values:
            return WealthMetrics(
                tick=tick,
                total_wealth=0.0,
                mean_wealth=0.0,
                median_wealth=0.0,
                gini_coefficient=0.0,
                top_10_percent_share=0.0,
                bottom_50_percent_share=0.0,
                wealth_mobility=0.0,
            )
        
        sorted_wealth = sorted(wealth_values)
        n = len(sorted_wealth)
        total_wealth = sum(sorted_wealth)
        mean_wealth = total_wealth / n
        
        if n % 2 == 0:
            median_wealth = (sorted_wealth[n // 2 - 1] + sorted_wealth[n // 2]) / 2
        else:
            median_wealth = sorted_wealth[n // 2]
        
        gini = self.calculate_gini_coefficient(wealth_values)
        
        top_10_count = max(1, n // 10)
        top_10_wealth = sum(sorted_wealth[-top_10_count:])
        top_10_share = top_10_wealth / total_wealth if total_wealth > 0 else 0.0
        
        bottom_50_count = n // 2
        bottom_50_wealth = sum(sorted_wealth[:bottom_50_count])
        bottom_50_share = bottom_50_wealth / total_wealth if total_wealth > 0 else 0.0
        
        wealth_mobility = self._calculate_mobility(tick)
        
        agents_sorted = sorted(
            self.agent_manager.list_agents(),
            key=lambda a: self.calculate_agent_wealth(a.id),
            reverse=True,
        )
        for rank, agent in enumerate(agents_sorted):
            self._rank_history[agent.id].append((tick, rank + 1))
            if len(self._rank_history[agent.id]) > self._max_history:
                self._rank_history[agent.id].pop(0)
        
        metrics = WealthMetrics(
            tick=tick,
            total_wealth=total_wealth,
            mean_wealth=mean_wealth,
            median_wealth=median_wealth,
            gini_coefficient=gini,
            top_10_percent_share=top_10_share,
            bottom_50_percent_share=bottom_50_share,
            wealth_mobility=wealth_mobility,
        )
        
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > self._max_history:
            self._metrics_history.pop(0)
        
        return metrics
    
    def _calculate_mobility(self, current_tick, lookback=50):
        if not self._rank_history:
            return 0.0
        
        rank_changes = []
        
        for agent_id, history in self._rank_history.items():
            if len(history) < 2:
                continue
            
            old_entries = [h for h in history if h[0] <= current_tick - lookback]
            if not old_entries:
                continue
            
            old_rank = old_entries[-1][1]
            current_rank = history[-1][1]
            
            rank_changes.append(abs(current_rank - old_rank))
        
        if not rank_changes:
            return 0.0
        
        n = len(self.agent_manager.list_agents())
        max_change = n - 1 if n > 1 else 1
        
        avg_change = sum(rank_changes) / len(rank_changes)
        mobility = avg_change / max_change
        
        return min(1.0, mobility)
    
    def get_agent_wealth_history(self, agent_id, since_tick=None):
        history = self._wealth_history.get(agent_id, [])
        if since_tick is not None:
            history = [s for s in history if s.tick >= since_tick]
        return [(s.tick, s.total_wealth) for s in history]
    
    def get_metrics_history(self, since_tick=None):
        history = self._metrics_history
        if since_tick is not None:
            history = [m for m in history if m.tick >= since_tick]
        return history
    
    def get_wealth_distribution(self, tick=None):
        return {
            agent.id: self.calculate_agent_wealth(agent.id)
            for agent in self.agent_manager.list_agents()
        }
    
    def get_wealth_quintiles(self):
        agents_sorted = sorted(
            self.agent_manager.list_agents(),
            key=lambda a: self.calculate_agent_wealth(a.id),
        )
        
        n = len(agents_sorted)
        quintile_size = n // 5
        
        quintiles = {
            "q1_poorest": [],
            "q2": [],
            "q3": [],
            "q4": [],
            "q5_richest": [],
        }
        
        for i, agent in enumerate(agents_sorted):
            if i < quintile_size:
                quintiles["q1_poorest"].append(agent.id)
            elif i < quintile_size * 2:
                quintiles["q2"].append(agent.id)
            elif i < quintile_size * 3:
                quintiles["q3"].append(agent.id)
            elif i < quintile_size * 4:
                quintiles["q4"].append(agent.id)
            else:
                quintiles["q5_richest"].append(agent.id)
        
        return quintiles
    
    def get_gini_history(self):
        return [(m.tick, m.gini_coefficient) for m in self._metrics_history]
    
    def to_dict(self):
        current_metrics = self._metrics_history[-1] if self._metrics_history else None
        
        return {
            "current_metrics": current_metrics.to_dict() if current_metrics else None,
            "gini_history": self.get_gini_history()[-50:],
            "wealth_distribution": self.get_wealth_distribution(),
        }
