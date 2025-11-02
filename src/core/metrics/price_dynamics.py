from collections import defaultdict
import math


class PricePoint:
    def __init__(self, tick, price, volume=0):
        self.tick = tick
        self.price = price
        self.volume = volume


class PriceDynamicsProcessor:
    def __init__(self, window_size=100):
        self.window_size = window_size
        self._price_series = defaultdict(list)
        self._volatility_cache = {}
        self._trend_cache = {}
        self._last_update_tick = 0
    
    def record_price(self, item, tick, price, volume=0):
        self._price_series[item].append(PricePoint(tick, price, volume))
        
        if len(self._price_series[item]) > self.window_size * 2:
            self._price_series[item] = self._price_series[item][-self.window_size:]
        
        self._last_update_tick = tick
        self._volatility_cache.pop(item, None)
        self._trend_cache.pop(item, None)
    
    def get_price_series(self, item, since_tick=None):
        series = self._price_series.get(item, [])
        if since_tick is not None:
            series = [p for p in series if p.tick >= since_tick]
        return [(p.tick, p.price) for p in series]
    
    def get_current_price(self, item):
        series = self._price_series.get(item, [])
        return series[-1].price if series else None
    
    def calculate_volatility(self, item, window=None):
        if item in self._volatility_cache:
            return self._volatility_cache[item]
        
        series = self._price_series.get(item, [])
        if len(series) < 2:
            return 0.0
        
        window = window or self.window_size
        prices = [p.price for p in series[-window:]]
        
        if len(prices) < 2:
            return 0.0
        
        mean = sum(prices) / len(prices)
        if mean == 0:
            return 0.0
        
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        volatility = math.sqrt(variance) / mean
        
        self._volatility_cache[item] = volatility
        return volatility
    
    def calculate_trend(self, item, window=None):
        if item in self._trend_cache:
            return self._trend_cache[item]
        
        series = self._price_series.get(item, [])
        if len(series) < 2:
            return 0.0
        
        window = window or self.window_size
        points = series[-window:]
        
        if len(points) < 2:
            return 0.0
        
        n = len(points)
        sum_x = sum(range(n))
        sum_y = sum(p.price for p in points)
        sum_xy = sum(i * p.price for i, p in enumerate(points))
        sum_x2 = sum(i * i for i in range(n))
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        mean_price = sum_y / n if n > 0 else 1.0
        normalized_slope = slope / mean_price if mean_price != 0 else 0.0
        
        self._trend_cache[item] = normalized_slope
        return normalized_slope
    
    def calculate_entropy(self, items=None):
        if items is None:
            items = list(self._price_series.keys())
        
        prices = []
        for item in items:
            current = self.get_current_price(item)
            if current and current > 0:
                prices.append(current)
        
        if not prices:
            return 0.0
        
        total = sum(prices)
        probabilities = [p / total for p in prices]
        
        entropy = -sum(p * math.log(p) if p > 0 else 0 for p in probabilities)
        
        max_entropy = math.log(len(prices)) if len(prices) > 1 else 1.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
        
        return normalized_entropy
    
    def calculate_price_convergence(self):
        if len(self._price_series) < 2:
            return 0.0
        
        volatilities = [
            self.calculate_volatility(item)
            for item in self._price_series.keys()
        ]
        
        if not volatilities:
            return 0.0
        
        mean_volatility = sum(volatilities) / len(volatilities)
        
        convergence = 1.0 / (1.0 + mean_volatility)
        return convergence
    
    def calculate_moving_average(self, item, window=10):
        series = self._price_series.get(item, [])
        if len(series) < window:
            return None
        
        recent = series[-window:]
        return sum(p.price for p in recent) / len(recent)
    
    def calculate_momentum(self, item, periods=10):
        series = self._price_series.get(item, [])
        if len(series) < periods + 1:
            return None
        
        current = series[-1].price
        past = series[-periods - 1].price
        
        if past == 0:
            return None
        
        return (current - past) / past
    
    def detect_price_anomalies(self, item, threshold=2.0):
        series = self._price_series.get(item, [])
        if len(series) < 10:
            return []
        
        prices = [p.price for p in series]
        mean = sum(prices) / len(prices)
        std = math.sqrt(sum((p - mean) ** 2 for p in prices) / len(prices))
        
        if std == 0:
            return []
        
        anomalies = []
        for point in series:
            z_score = abs(point.price - mean) / std
            if z_score > threshold:
                direction = "spike" if point.price > mean else "crash"
                anomalies.append((point.tick, point.price, direction))
        
        return anomalies
    
    def get_all_metrics(self, tick):
        metrics = {
            "tick": tick,
            "items_tracked": len(self._price_series),
            "price_entropy": self.calculate_entropy(),
            "price_convergence": self.calculate_price_convergence(),
            "item_metrics": {},
        }
        
        for item in self._price_series.keys():
            current_price = self.get_current_price(item)
            metrics["item_metrics"][item] = {
                "current_price": current_price,
                "volatility": self.calculate_volatility(item),
                "trend": self.calculate_trend(item),
                "momentum": self.calculate_momentum(item),
                "ma_10": self.calculate_moving_average(item, 10),
            }
        
        return metrics
    
    def to_dict(self):
        return {
            "window_size": self.window_size,
            "items_tracked": list(self._price_series.keys()),
            "price_series": {
                item: [(p.tick, p.price, p.volume) for p in points[-50:]]
                for item, points in self._price_series.items()
            },
        }
