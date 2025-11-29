import json
import gzip
import os
from datetime import datetime
from enum import Enum, auto
from pathlib import Path


class EventType(Enum):
    AGENT_SPAWN = auto()
    AGENT_MOVE = auto()
    AGENT_HARVEST = auto()
    AGENT_CRAFT = auto()
    AGENT_TRADE_PROPOSE = auto()
    AGENT_TRADE_ACCEPT = auto()
    AGENT_TRADE_REJECT = auto()
    AGENT_MESSAGE = auto()
    AGENT_GROUP_ACTION = auto()
    AGENT_IDLE = auto()
    AGENT_DEATH = auto()
    RESOURCE_REGEN = auto()
    RESOURCE_DEPLETED = auto()
    TICK_START = auto()
    TICK_END = auto()
    SIMULATION_START = auto()
    SIMULATION_END = auto()
    WARMUP_START = auto()
    WARMUP_END = auto()
    SNAPSHOT = auto()
    ERROR = auto()
    WARNING = auto()
    INFO = auto()


class Event:
    def __init__(self, event_type, tick, timestamp, data=None, agent_id=None, location_id=None):
        self.event_type = event_type
        self.tick = tick
        self.timestamp = timestamp
        self.data = data or {}
        self.agent_id = agent_id
        self.location_id = location_id

    def to_dict(self):
        return {
            "event_type": self.event_type.name,
            "tick": self.tick,
            "timestamp": self.timestamp,
            "data": self.data,
            "agent_id": self.agent_id,
            "location_id": self.location_id,
        }

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data):
        return cls(
            event_type=EventType[data["event_type"]],
            tick=data["tick"],
            timestamp=data["timestamp"],
            data=data.get("data", {}),
            agent_id=data.get("agent_id"),
            location_id=data.get("location_id"),
        )


class EventLogger:
    def __init__(self, output_path=None, buffer_size=1000, compress=False, auto_flush=True):
        self._buffer = []
        self._buffer_size = buffer_size
        self._auto_flush = auto_flush
        self._compress = compress
        self._output_path = Path(output_path) if output_path else None
        self._file_handle = None
        self._event_count = 0
        self._memory_store = []
        self._store_in_memory = True
        if self._output_path:
            self._open_file()

    def _open_file(self):
        if self._output_path is None:
            return
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        if self._compress:
            path = self._output_path.with_suffix(self._output_path.suffix + ".gz")
            self._file_handle = gzip.open(path, "wt", encoding="utf-8")
        else:
            self._file_handle = open(self._output_path, "w", encoding="utf-8")

    def log(self, event_type, tick, timestamp, data=None, agent_id=None, location_id=None):
        event = Event(
            event_type=event_type,
            tick=tick,
            timestamp=timestamp,
            data=data or {},
            agent_id=agent_id,
            location_id=location_id,
        )
        self._buffer.append(event)
        self._event_count += 1
        if self._store_in_memory:
            self._memory_store.append(event)
        if self._auto_flush and len(self._buffer) >= self._buffer_size:
            self.flush()
        return event

    def log_agent_move(self, tick, timestamp, agent_id, from_location, to_location, travel_cost=0.0):
        return self.log(
            event_type=EventType.AGENT_MOVE,
            tick=tick,
            timestamp=timestamp,
            agent_id=agent_id,
            location_id=to_location,
            data={
                "from_location": from_location,
                "to_location": to_location,
                "travel_cost": travel_cost,
            },
        )

    def log_agent_harvest(self, tick, timestamp, agent_id, location_id, resource_type, amount):
        return self.log(
            event_type=EventType.AGENT_HARVEST,
            tick=tick,
            timestamp=timestamp,
            agent_id=agent_id,
            location_id=location_id,
            data={
                "resource_type": resource_type,
                "amount": amount,
            },
        )

    def log_agent_craft(self, tick, timestamp, agent_id, recipe_id, quantity, inputs, outputs):
        return self.log(
            event_type=EventType.AGENT_CRAFT,
            tick=tick,
            timestamp=timestamp,
            agent_id=agent_id,
            data={
                "recipe_id": recipe_id,
                "quantity": quantity,
                "inputs": inputs,
                "outputs": outputs,
            },
        )

    def log_trade(self, tick, timestamp, event_type, proposer_id, target_id, proposal_id, offered_items=None, requested_items=None):
        return self.log(
            event_type=event_type,
            tick=tick,
            timestamp=timestamp,
            agent_id=proposer_id,
            data={
                "proposer_id": proposer_id,
                "target_id": target_id,
                "proposal_id": proposal_id,
                "offered_items": offered_items or [],
                "requested_items": requested_items or [],
            },
        )

    def log_message(self, tick, timestamp, sender_id, recipient_id, channel, content_hash=None):
        return self.log(
            event_type=EventType.AGENT_MESSAGE,
            tick=tick,
            timestamp=timestamp,
            agent_id=sender_id,
            data={
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "channel": channel,
                "content_hash": content_hash,
            },
        )

    def log_tick(self, tick, timestamp, is_start, stats=None):
        return self.log(
            event_type=EventType.TICK_START if is_start else EventType.TICK_END,
            tick=tick,
            timestamp=timestamp,
            data=stats or {},
        )

    def log_simulation_event(self, event_type, tick, timestamp, data=None):
        return self.log(
            event_type=event_type,
            tick=tick,
            timestamp=timestamp,
            data=data or {},
        )

    def flush(self):
        if self._file_handle and self._buffer:
            for event in self._buffer:
                self._file_handle.write(event.to_json() + "\n")
            self._file_handle.flush()
        self._buffer.clear()

    def close(self):
        self.flush()
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def get_events(self, event_type=None, agent_id=None, location_id=None, tick_start=None, tick_end=None):
        events = self._memory_store
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        if agent_id is not None:
            events = [e for e in events if e.agent_id == agent_id]
        if location_id is not None:
            events = [e for e in events if e.location_id == location_id]
        if tick_start is not None:
            events = [e for e in events if e.tick >= tick_start]
        if tick_end is not None:
            events = [e for e in events if e.tick <= tick_end]
        return events

    def get_event_count(self):
        return self._event_count

    def get_events_by_tick(self, tick):
        return [e for e in self._memory_store if e.tick == tick]

    def disable_memory_store(self):
        self._store_in_memory = False
        self._memory_store.clear()

    def enable_memory_store(self):
        self._store_in_memory = True

    def export_to_jsonl(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for event in self._memory_store:
                f.write(event.to_json() + "\n")
        return len(self._memory_store)

    @staticmethod
    def load_from_jsonl(path):
        path = Path(path)
        events = []
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    events.append(Event.from_dict(data))
        return events

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class StateSnapshot:
    def __init__(self, tick, timestamp, world_state=None, agents=None, resources=None, metrics=None):
        self.tick = tick
        self.timestamp = timestamp
        self.world_state = world_state or {}
        self.agents = agents or []
        self.resources = resources or {}
        self.metrics = metrics or {}
        self.metadata = {
            "snapshot_time": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

    def to_dict(self):
        return {
            "tick": self.tick,
            "timestamp": self.timestamp,
            "world_state": self.world_state,
            "agents": self.agents,
            "resources": self.resources,
            "metrics": self.metrics,
            "metadata": self.metadata,
        }

    def to_json(self, indent=None):
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data):
        snapshot = cls(
            tick=data["tick"],
            timestamp=data["timestamp"],
            world_state=data.get("world_state", {}),
            agents=data.get("agents", []),
            resources=data.get("resources", {}),
            metrics=data.get("metrics", {}),
        )
        snapshot.metadata = data.get("metadata", {})
        return snapshot

    def save(self, path, compress=False):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if compress:
            path = path.with_suffix(path.suffix + ".gz")
            with gzip.open(path, "wt", encoding="utf-8") as f:
                f.write(self.to_json())
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.to_json(indent=2))

    @classmethod
    def load(cls, path):
        path = Path(path)
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class SnapshotManager:
    def __init__(self, output_dir, snapshot_interval=100, compress=True, max_snapshots=None):
        self.output_dir = Path(output_dir)
        self.snapshot_interval = snapshot_interval
        self.compress = compress
        self.max_snapshots = max_snapshots
        self._snapshots = []
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def should_snapshot(self, tick):
        return tick % self.snapshot_interval == 0

    def take_snapshot(self, tick, timestamp, world_state=None, agents=None, resources=None, metrics=None):
        snapshot = StateSnapshot(
            tick=tick,
            timestamp=timestamp,
            world_state=world_state,
            agents=agents,
            resources=resources,
            metrics=metrics,
        )
        filename = f"snapshot_tick_{tick:08d}.json"
        filepath = self.output_dir / filename
        snapshot.save(filepath, compress=self.compress)
        actual_path = str(filepath) + (".gz" if self.compress else "")
        self._snapshots.append(actual_path)
        if self.max_snapshots and len(self._snapshots) > self.max_snapshots:
            old_path = self._snapshots.pop(0)
            try:
                os.remove(old_path)
            except OSError:
                pass
        return snapshot

    def list_snapshots(self):
        return list(self._snapshots)

    def load_latest(self):
        if not self._snapshots:
            return None
        return StateSnapshot.load(self._snapshots[-1])

    def load_by_tick(self, tick):
        filename = f"snapshot_tick_{tick:08d}.json"
        if self.compress:
            filename += ".gz"
        filepath = self.output_dir / filename
        if filepath.exists():
            return StateSnapshot.load(filepath)
        return None
