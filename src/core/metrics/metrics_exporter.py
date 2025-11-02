import json
import csv
from enum import Enum
from datetime import datetime
from pathlib import Path


class ExportFormat(Enum):
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"


class MetricsExport:
    def __init__(
        self,
        tick,
        timestamp,
        price_dynamics=None,
        wealth_metrics=None,
        specialization=None,
        trade_network=None,
        reputation=None,
        institutions=None,
    ):
        self.tick = tick
        self.timestamp = timestamp
        self.price_dynamics = price_dynamics
        self.wealth_metrics = wealth_metrics
        self.specialization = specialization
        self.trade_network = trade_network
        self.reputation = reputation
        self.institutions = institutions

    def to_dict(self):
        return {
            "tick": self.tick,
            "timestamp": self.timestamp,
            "price_dynamics": self.price_dynamics,
            "wealth_metrics": self.wealth_metrics,
            "specialization": self.specialization,
            "trade_network": self.trade_network,
            "reputation": self.reputation,
            "institutions": self.institutions,
        }

    def to_flat_dict(self):
        flat = {
            "tick": self.tick,
            "timestamp": self.timestamp,
        }

        if self.price_dynamics:
            for key, value in self._flatten_dict(self.price_dynamics, "price").items():
                flat[key] = value

        if self.wealth_metrics:
            for key, value in self._flatten_dict(self.wealth_metrics, "wealth").items():
                flat[key] = value

        if self.specialization:
            for key, value in self._flatten_dict(self.specialization, "spec").items():
                flat[key] = value

        if self.trade_network:
            for key, value in self._flatten_dict(self.trade_network, "network").items():
                flat[key] = value

        if self.reputation:
            for key, value in self._flatten_dict(self.reputation, "rep").items():
                flat[key] = value

        if self.institutions:
            for key, value in self._flatten_dict(self.institutions, "inst").items():
                flat[key] = value

        return flat

    def _flatten_dict(self, d, prefix):
        items = {}
        for key, value in d.items():
            new_key = f"{prefix}_{key}"
            if isinstance(value, dict):
                items.update(self._flatten_dict(value, new_key))
            elif isinstance(value, (list, tuple)):
                if len(value) <= 5:
                    for i, v in enumerate(value):
                        if isinstance(v, (int, float, str, bool)):
                            items[f"{new_key}_{i}"] = v
                else:
                    items[f"{new_key}_count"] = len(value)
            elif isinstance(value, (int, float, str, bool)) or value is None:
                items[new_key] = value
        return items


class MetricsExporter:
    def __init__(self, output_dir):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._exports = []
        self._max_buffer = 1000

        self._json_file = None
        self._jsonl_file = None
        self._csv_file = None
        self._csv_headers_written = False

    def collect_metrics(
        self,
        tick,
        price_processor=None,
        wealth_tracker=None,
        specialization_detector=None,
        trade_network_analyzer=None,
        reputation_metrics=None,
        institution_tracker=None,
    ):
        timestamp = datetime.utcnow().isoformat()

        price_dynamics = None
        if price_processor:
            price_dynamics = {
                "volatility": price_processor.calculate_volatility(),
                "entropy": price_processor.calculate_price_entropy(),
            }

        wealth_metrics = None
        if wealth_tracker:
            snapshot = wealth_tracker.take_snapshot(tick)
            if snapshot:
                wealth_metrics = snapshot.to_dict()

        specialization = None
        if specialization_detector:
            specialization = {
                "cluster_count": specialization_detector.get_cluster_count(),
                "summary": specialization_detector.get_specialization_summary(),
            }

        trade_network = None
        if trade_network_analyzer:
            nm = trade_network_analyzer.get_network_metrics()
            trade_network = nm._asdict() if hasattr(nm, "_asdict") else {}

        reputation = None
        if reputation_metrics:
            reputation = {
                "network_trust": reputation_metrics.get_network_trust_metrics(),
                "contract_summary": reputation_metrics.get_contract_adherence_summary(),
                "dispute_frequency": reputation_metrics.get_dispute_frequency(),
            }

        institutions = None
        if institution_tracker:
            institutions = institution_tracker.get_institution_emergence_metrics(tick)

        export = MetricsExport(
            tick=tick,
            timestamp=timestamp,
            price_dynamics=price_dynamics,
            wealth_metrics=wealth_metrics,
            specialization=specialization,
            trade_network=trade_network,
            reputation=reputation,
            institutions=institutions,
        )

        self._exports.append(export)
        if len(self._exports) > self._max_buffer:
            self._exports.pop(0)

        return export

    def export_json(self, filename="metrics.json", pretty=True):
        filepath = self._output_dir / filename

        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "tick_count": len(self._exports),
            "metrics": [e.to_dict() for e in self._exports],
        }

        with open(filepath, "w") as f:
            if pretty:
                json.dump(data, f, indent=2)
            else:
                json.dump(data, f)

        self._json_file = filepath
        return filepath

    def export_jsonl(self, filename="metrics.jsonl", append=False):
        filepath = self._output_dir / filename
        mode = "a" if append else "w"

        with open(filepath, mode) as f:
            for export in self._exports:
                f.write(json.dumps(export.to_dict()) + "\n")

        self._jsonl_file = filepath
        return filepath

    def append_jsonl(self, export, filename="metrics.jsonl"):
        filepath = self._output_dir / filename

        with open(filepath, "a") as f:
            f.write(json.dumps(export.to_dict()) + "\n")

        self._jsonl_file = filepath

    def export_csv(self, filename="metrics.csv"):
        filepath = self._output_dir / filename

        if not self._exports:
            return filepath

        flat_exports = [e.to_flat_dict() for e in self._exports]

        all_keys = set()
        for flat in flat_exports:
            all_keys.update(flat.keys())

        fieldnames = sorted(all_keys)
        if "tick" in fieldnames:
            fieldnames.remove("tick")
            fieldnames.insert(0, "tick")
        if "timestamp" in fieldnames:
            fieldnames.remove("timestamp")
            fieldnames.insert(1, "timestamp")

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for flat in flat_exports:
                row = {k: flat.get(k, "") for k in fieldnames}
                writer.writerow(row)

        self._csv_file = filepath
        return filepath

    def append_csv(self, export, filename="metrics.csv"):
        filepath = self._output_dir / filename
        flat = export.to_flat_dict()
        fieldnames = sorted(flat.keys())

        if "tick" in fieldnames:
            fieldnames.remove("tick")
            fieldnames.insert(0, "tick")
        if "timestamp" in fieldnames:
            fieldnames.remove("timestamp")
            fieldnames.insert(1, "timestamp")

        file_exists = filepath.exists()

        with open(filepath, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(flat)

        self._csv_file = filepath

    def export_all(self, base_filename="metrics"):
        paths = {}
        paths["json"] = self.export_json(f"{base_filename}.json")
        paths["jsonl"] = self.export_jsonl(f"{base_filename}.jsonl")
        paths["csv"] = self.export_csv(f"{base_filename}.csv")
        return paths

    def get_export_summary(self):
        return {
            "total_exports": len(self._exports),
            "output_dir": str(self._output_dir),
            "json_file": str(self._json_file) if self._json_file else None,
            "jsonl_file": str(self._jsonl_file) if self._jsonl_file else None,
            "csv_file": str(self._csv_file) if self._csv_file else None,
            "tick_range": {
                "first": self._exports[0].tick if self._exports else None,
                "last": self._exports[-1].tick if self._exports else None,
            },
        }

    def clear_buffer(self):
        self._exports.clear()

    def get_latest_export(self):
        return self._exports[-1] if self._exports else None

    def get_exports(self, since_tick=None, limit=None):
        exports = self._exports

        if since_tick is not None:
            exports = [e for e in exports if e.tick >= since_tick]

        if limit is not None:
            exports = exports[-limit:]

        return exports
