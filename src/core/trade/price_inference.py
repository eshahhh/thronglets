from collections import defaultdict
import math

class ExchangeRate:
    def __init__(self, item_a, item_b, rate, tick, volume_a, volume_b):
        self.item_a = item_a
        self.item_b = item_b
        self.rate = rate
        self.tick = tick
        self.volume_a = volume_a
        self.volume_b = volume_b

    def to_dict(self):
        return {
            "item_a": self.item_a,
            "item_b": self.item_b,
            "rate": self.rate,
            "tick": self.tick,
            "volume_a": self.volume_a,
            "volume_b": self.volume_b,
        }


class PriceInferenceEngine:
    def __init__(self, base_item="wheat", window_size=100):
        self.base_item = base_item
        self.window_size = window_size

        self._exchange_rates = []
        self._price_matrix = defaultdict(lambda: defaultdict(list))
        self._inferred_prices = {base_item: 1.0}
        self._price_history = defaultdict(list)
        self._trade_volumes = defaultdict(int)

        from ..logging.live_logger import get_live_logger
        self._logger = get_live_logger()

    def record_trade(self, offered_items, requested_items, tick):
        new_rates = []

        for offered in offered_items:
            item_a = offered["item_type"]
            qty_a = offered["quantity"]
            self._trade_volumes[item_a] += qty_a

            for requested in requested_items:
                item_b = requested["item_type"]
                qty_b = requested["quantity"]

                rate = qty_b / qty_a if qty_a > 0 else 0

                exchange = ExchangeRate(
                    item_a=item_a,
                    item_b=item_b,
                    rate=rate,
                    tick=tick,
                    volume_a=qty_a,
                    volume_b=qty_b,
                )

                self._exchange_rates.append(exchange)
                new_rates.append(exchange)

                self._price_matrix[item_a][item_b].append(rate)
                if len(self._price_matrix[item_a][item_b]) > self.window_size:
                    self._price_matrix[item_a][item_b].pop(0)

                if rate > 0:
                    inverse_rate = 1.0 / rate
                    self._price_matrix[item_b][item_a].append(inverse_rate)
                    if len(self._price_matrix[item_b][item_a]) > self.window_size:
                        self._price_matrix[item_b][item_a].pop(0)

        for requested in requested_items:
            item_b = requested["item_type"]
            qty_b = requested["quantity"]
            self._trade_volumes[item_b] += qty_b

        self._update_inferred_prices(tick)

        return new_rates

    def _update_inferred_prices(self, tick):
        all_items = set(self._price_matrix.keys())
        for rates in self._price_matrix.values():
            all_items.update(rates.keys())

        self._inferred_prices[self.base_item] = 1.0

        changed = True
        iterations = 0
        max_iterations = len(all_items) * 2

        while changed and iterations < max_iterations:
            changed = False
            iterations += 1

            for item in all_items:
                if item == self.base_item:
                    continue

                if self.base_item in self._price_matrix[item]:
                    rates = self._price_matrix[item][self.base_item]
                    if rates:
                        avg_rate = sum(rates) / len(rates)
                        new_price = avg_rate
                        if item not in self._inferred_prices or abs(self._inferred_prices[item] - new_price) > 0.01:
                            self._inferred_prices[item] = new_price
                            changed = True
                        continue

                for known_item, known_price in list(self._inferred_prices.items()):
                    if known_item == item:
                        continue

                    if known_item in self._price_matrix[item]:
                        rates = self._price_matrix[item][known_item]
                        if rates:
                            avg_rate = sum(rates) / len(rates)
                            new_price = avg_rate * known_price

                            if item not in self._inferred_prices:
                                self._inferred_prices[item] = new_price
                                changed = True
                            else:
                                old_price = self._inferred_prices[item]
                                blended = (old_price + new_price) / 2
                                if abs(old_price - blended) > 0.01:
                                    self._inferred_prices[item] = blended
                                    changed = True

        for item, price in self._inferred_prices.items():
            self._price_history[item].append((tick, price))
            if len(self._price_history[item]) > self.window_size * 10:
                self._price_history[item].pop(0)

    def get_price(self, item):
        return self._inferred_prices.get(item, 1.0)

    def get_all_prices(self):
        return dict(self._inferred_prices)

    def get_exchange_rate(self, item_a, item_b):
        if item_a in self._price_matrix and item_b in self._price_matrix[item_a]:
            rates = self._price_matrix[item_a][item_b]
            if rates:
                return sum(rates) / len(rates)

        price_a = self._inferred_prices.get(item_a)
        price_b = self._inferred_prices.get(item_b)
        if price_a and price_b:
            return price_b / price_a

        return None

    def get_price_history(self, item, since_tick=None):
        history = self._price_history.get(item, [])
        if since_tick is not None:
            history = [(t, p) for t, p in history if t >= since_tick]
        return history

    def get_price_volatility(self, item, window=20):
        history = self._price_history.get(item, [])
        if len(history) < 2:
            return 0.0

        recent = [p for _, p in history[-window:]]
        if len(recent) < 2:
            return 0.0

        mean = sum(recent) / len(recent)
        variance = sum((p - mean) ** 2 for p in recent) / len(recent)
        return math.sqrt(variance)

    def get_price_trend(self, item, window=20):
        history = self._price_history.get(item, [])
        if len(history) < 2:
            return 0.0

        recent = [(t, p) for t, p in history[-window:]]
        if len(recent) < 2:
            return 0.0

        n = len(recent)
        sum_t = sum(t for t, _ in recent)
        sum_p = sum(p for _, p in recent)
        sum_tp = sum(t * p for t, p in recent)
        sum_t2 = sum(t * t for t, _ in recent)

        denominator = n * sum_t2 - sum_t * sum_t
        if denominator == 0:
            return 0.0

        slope = (n * sum_tp - sum_t * sum_p) / denominator
        return slope

    def calculate_price_entropy(self):
        if not self._inferred_prices:
            return 0.0

        prices = list(self._inferred_prices.values())
        if not prices:
            return 0.0

        total = sum(prices)
        if total == 0:
            return 0.0

        probabilities = [p / total for p in prices]
        entropy = -sum(p * math.log(p) if p > 0 else 0 for p in probabilities)

        return entropy

    def get_most_traded_items(self, limit=10):
        sorted_items = sorted(
            self._trade_volumes.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_items[:limit]

    def get_emerging_currency(self):
        if not self._trade_volumes:
            return None

        total_volume = sum(self._trade_volumes.values())
        if total_volume == 0:
            return None

        items_with_share = [
            (item, volume / total_volume)
            for item, volume in self._trade_volumes.items()
        ]

        items_with_share.sort(key=lambda x: x[1], reverse=True)

        if items_with_share and items_with_share[0][1] > 0.3:
            return items_with_share[0][0]

        return None

    def get_stats(self):
        return {
            "total_exchange_rates": len(self._exchange_rates),
            "tracked_items": len(self._inferred_prices),
            "trade_volumes": dict(self._trade_volumes),
            "price_entropy": self.calculate_price_entropy(),
            "emerging_currency": self.get_emerging_currency(),
        }

    def export_price_matrix(self):
        result = {}
        for item_a in self._price_matrix:
            result[item_a] = {}
            for item_b, rates in self._price_matrix[item_a].items():
                if rates:
                    result[item_a][item_b] = sum(rates) / len(rates)
        return result

    def to_dict(self):
        return {
            "base_item": self.base_item,
            "inferred_prices": self._inferred_prices,
            "price_history": {
                item: [(t, p) for t, p in history[-50:]]
                for item, history in self._price_history.items()
            },
            "trade_volumes": dict(self._trade_volumes),
        }
