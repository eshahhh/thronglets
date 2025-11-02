from collections import defaultdict
import json
import time

class TimeSeriesPoint:
    def __init__(self, tick, timestamp, value, metadata=None):
        self.tick = tick
        self.timestamp = timestamp
        self.value = value
        self.metadata = metadata or {}

class TimeSeries:
    def __init__(self, name, max_points=10000):
        self.name = name
        self.points = []
        self.max_points = max_points
        
    def add(self, tick, value, metadata=None):
        point = TimeSeriesPoint(
            tick=tick,
            timestamp=time.time(),
            value=value,
            metadata=metadata or {},
        )
        self.points.append(point)
        if len(self.points) > self.max_points:
            self.points = self.points[-self.max_points:]
            
    def get_range(self, start_tick, end_tick):
        return [p for p in self.points if start_tick <= p.tick <= end_tick]
        
    def get_latest(self, n=100):
        return self.points[-n:]
        
    def get_stats(self):
        if not self.points:
            return {"min": 0, "max": 0, "avg": 0, "latest": 0}
        values = [p.value for p in self.points]
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1],
            "count": len(values),
        }
        
    def to_json(self):
        return [
            {"tick": p.tick, "value": p.value, "metadata": p.metadata}
            for p in self.points
        ]

class WealthPriceDashboard:
    def __init__(self):
        self._agent_wealth = {}
        self._resource_prices = {}
        self._gini_coefficient = TimeSeries("gini")
        self._total_wealth = TimeSeries("total_wealth")
        self._trade_volume = TimeSeries("trade_volume")
        self._price_history = defaultdict(list)
        
    def record_agent_wealth(self, agent_id, tick, wealth, breakdown=None):
        if agent_id not in self._agent_wealth:
            self._agent_wealth[agent_id] = TimeSeries(f"wealth_{agent_id}")
        self._agent_wealth[agent_id].add(tick, wealth, breakdown)
        
    def record_resource_price(self, resource, tick, price, volume=0):
        if resource not in self._resource_prices:
            self._resource_prices[resource] = TimeSeries(f"price_{resource}")
        self._resource_prices[resource].add(tick, price, {"volume": volume})
        self._price_history[resource].append({"tick": tick, "price": price, "volume": volume})
        
    def record_gini(self, tick, gini):
        self._gini_coefficient.add(tick, gini)
        
    def record_total_wealth(self, tick, total):
        self._total_wealth.add(tick, total)
        
    def record_trade_volume(self, tick, volume):
        self._trade_volume.add(tick, volume)
        
    def compute_wealth_distribution(self, tick=None):
        if tick is None:
            latest_wealth = {
                aid: series.points[-1].value if series.points else 0
                for aid, series in self._agent_wealth.items()
            }
        else:
            latest_wealth = {}
            for aid, series in self._agent_wealth.items():
                for p in reversed(series.points):
                    if p.tick <= tick:
                        latest_wealth[aid] = p.value
                        break
                        
        if not latest_wealth:
            return {"quintiles": [], "gini": 0, "median": 0, "mean": 0}
            
        values = sorted(latest_wealth.values())
        n = len(values)
        
        quintile_size = n // 5 or 1
        quintiles = []
        for i in range(5):
            start = i * quintile_size
            end = (i + 1) * quintile_size if i < 4 else n
            qvalues = values[start:end]
            quintiles.append({
                "quintile": i + 1,
                "min": min(qvalues) if qvalues else 0,
                "max": max(qvalues) if qvalues else 0,
                "avg": sum(qvalues) / len(qvalues) if qvalues else 0,
                "share": sum(qvalues) / sum(values) if values else 0,
            })
            
        gini = self._calculate_gini(values)
        median = values[n // 2] if values else 0
        mean = sum(values) / n if values else 0
        
        return {
            "quintiles": quintiles,
            "gini": gini,
            "median": median,
            "mean": mean,
            "total": sum(values),
            "agent_count": n,
        }
        
    def _calculate_gini(self, values):
        if not values or len(values) < 2:
            return 0
        sorted_values = sorted(values)
        n = len(sorted_values)
        cumsum = sum((i + 1) * v for i, v in enumerate(sorted_values))
        return (2 * cumsum) / (n * sum(sorted_values)) - (n + 1) / n
        
    def get_price_trends(self):
        trends = {}
        for resource, series in self._resource_prices.items():
            if len(series.points) < 2:
                trends[resource] = {"trend": 0, "volatility": 0, "latest": 0}
                continue
                
            values = [p.value for p in series.points]
            recent = values[-min(20, len(values)):]
            
            if len(recent) > 1:
                trend = (recent[-1] - recent[0]) / recent[0] if recent[0] != 0 else 0
                mean = sum(recent) / len(recent)
                variance = sum((v - mean) ** 2 for v in recent) / len(recent)
                volatility = variance ** 0.5 / mean if mean != 0 else 0
            else:
                trend = 0
                volatility = 0
                
            trends[resource] = {
                "trend": trend,
                "volatility": volatility,
                "latest": values[-1] if values else 0,
                "high": max(values) if values else 0,
                "low": min(values) if values else 0,
            }
        return trends
        
    def get_top_wealthy(self, limit=10):
        latest_wealth = []
        for aid, series in self._agent_wealth.items():
            if series.points:
                latest_wealth.append({
                    "agent_id": aid,
                    "wealth": series.points[-1].value,
                    "breakdown": series.points[-1].metadata or {},
                })
        return sorted(latest_wealth, key=lambda x: x["wealth"], reverse=True)[:limit]
        
    def get_dashboard_data(self, tick_range=100):
        latest_tick = max(
            (s.points[-1].tick for s in self._resource_prices.values() if s.points),
            default=0
        )
        start_tick = max(0, latest_tick - tick_range)
        
        return {
            "wealth_distribution": self.compute_wealth_distribution(),
            "price_trends": self.get_price_trends(),
            "top_wealthy": self.get_top_wealthy(10),
            "gini_history": self._gini_coefficient.to_json()[-tick_range:],
            "total_wealth_history": self._total_wealth.to_json()[-tick_range:],
            "trade_volume_history": self._trade_volume.to_json()[-tick_range:],
            "resource_prices": {
                r: series.to_json()[-tick_range:]
                for r, series in self._resource_prices.items()
            },
        }
        
    def to_json(self):
        return json.dumps(self.get_dashboard_data(), indent=2)
        
    def render_ascii_chart(self, resource=None, width=60, height=15):
        if resource and resource in self._resource_prices:
            series = self._resource_prices[resource]
            title = f"Price: {resource}"
        elif self._total_wealth.points:
            series = self._total_wealth
            title = "Total Wealth"
        else:
            return "No data to display"
            
        if not series.points:
            return f"No data for {title}"
            
        values = [p.value for p in series.get_latest(width)]
        if not values:
            return f"No data for {title}"
            
        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val or 1
        
        chart = [[' ' for _ in range(width)] for _ in range(height)]
        
        for i, val in enumerate(values):
            y = int((val - min_val) / range_val * (height - 1))
            y = height - 1 - y
            if 0 <= y < height and i < width:
                chart[y][i] = '█'
                for fill_y in range(y + 1, height):
                    chart[fill_y][i] = '▒'
                    
        lines = [f"┌{'─' * width}┐ {title}"]
        lines.append(f"│{max_val:>{width-2}.2f}│")
        for row in chart:
            lines.append(f"│{''.join(row)}│")
        lines.append(f"│{min_val:>{width-2}.2f}│")
        lines.append(f"└{'─' * width}┘")
        
        return '\n'.join(lines)
        
    def export_csv(self, filepath):
        import csv
        
        all_ticks = set()
        for series in self._resource_prices.values():
            all_ticks.update(p.tick for p in series.points)
            
        ticks = sorted(all_ticks)
        resources = sorted(self._resource_prices.keys())
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['tick'] + resources + ['gini', 'total_wealth'])
            
            for tick in ticks:
                row = [tick]
                for r in resources:
                    series = self._resource_prices[r]
                    val = next((p.value for p in series.points if p.tick == tick), '')
                    row.append(val)
                    
                gini = next((p.value for p in self._gini_coefficient.points if p.tick == tick), '')
                total = next((p.value for p in self._total_wealth.points if p.tick == tick), '')
                row.extend([gini, total])
                writer.writerow(row)
