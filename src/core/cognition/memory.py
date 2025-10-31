import time
from collections import deque


class MemoryEntry:
    def __init__(self, tick, timestamp, entry_type, content, importance=1.0):
        self.tick = tick
        self.timestamp = timestamp
        self.entry_type = entry_type
        self.content = content
        self.importance = importance

    def to_dict(self):
        return {
            "tick": self.tick,
            "timestamp": self.timestamp,
            "entry_type": self.entry_type,
            "content": self.content,
            "importance": self.importance,
        }


class ShortTermMemory:
    def __init__(self, max_entries=50):
        self.max_entries = max_entries
        self._entries = deque(maxlen=max_entries)

    def add(self, tick, entry_type, content, importance=1.0):
        entry = MemoryEntry(
            tick=tick,
            timestamp=time.time(),
            entry_type=entry_type,
            content=content,
            importance=importance,
        )
        self._entries.append(entry)

    def add_action(self, tick, action_type, details, success):
        self.add(
            tick=tick,
            entry_type="action",
            content={
                "action_type": action_type,
                "details": details,
                "success": success,
            },
            importance=1.5 if success else 1.0,
        )

    def add_message_received(self, tick, sender_id, content):
        self.add(
            tick=tick,
            entry_type="message_received",
            content={"sender_id": sender_id, "content": content},
            importance=1.2,
        )

    def add_message_sent(self, tick, recipient_id, content):
        self.add(
            tick=tick,
            entry_type="message_sent",
            content={"recipient_id": recipient_id, "content": content},
        )

    def add_trade(self, tick, other_agent, offered, received, success):
        self.add(
            tick=tick,
            entry_type="trade",
            content={
                "other_agent": other_agent,
                "offered": offered,
                "received": received,
                "success": success,
            },
            importance=2.0 if success else 1.0,
        )

    def add_observation(self, tick, key_observations):
        self.add(
            tick=tick,
            entry_type="observation",
            content=key_observations,
            importance=0.5,
        )

    def get_recent(self, count=10):
        entries = list(self._entries)
        return entries[-count:]

    def get_by_type(self, entry_type, count=10):
        filtered = [e for e in self._entries if e.entry_type == entry_type]
        return filtered[-count:]

    def get_since_tick(self, tick):
        return [e for e in self._entries if e.tick >= tick]

    def summarize(self, max_items=5):
        recent = self.get_recent(max_items)
        if not recent:
            return "No recent memories."

        lines = []
        for entry in recent:
            if entry.entry_type == "action":
                status = "succeeded" if entry.content.get("success") else "failed"
                lines.append(f"Tick {entry.tick}: {entry.content['action_type']} {status}")
            elif entry.entry_type == "message_received":
                lines.append(f"Tick {entry.tick}: Received message from {entry.content['sender_id']}")
            elif entry.entry_type == "message_sent":
                lines.append(f"Tick {entry.tick}: Sent message to {entry.content['recipient_id']}")
            elif entry.entry_type == "trade":
                status = "completed" if entry.content.get("success") else "failed"
                lines.append(f"Tick {entry.tick}: Trade with {entry.content['other_agent']} {status}")

        return "\n".join(lines)

    def clear(self):
        self._entries.clear()

    def __len__(self):
        return len(self._entries)


class LongTermGoal:
    def __init__(self, goal_id, description, priority=1.0, created_tick=0, progress=0.0, completed=False):
        self.goal_id = goal_id
        self.description = description
        self.priority = priority
        self.created_tick = created_tick
        self.progress = progress
        self.completed = completed


class LongTermMemory:
    def __init__(self):
        self._goals = {}
        self._alliances = {}
        self._enemies = {}
        self._preferences = {}
        self._strategic_notes = []
        self._trade_history = {}
        self._reputation_memory = {}

    def add_goal(self, goal_id, description, priority=1.0, tick=0):
        self._goals[goal_id] = LongTermGoal(
            goal_id=goal_id,
            description=description,
            priority=priority,
            created_tick=tick,
        )

    def update_goal_progress(self, goal_id, progress):
        if goal_id in self._goals:
            self._goals[goal_id].progress = min(1.0, max(0.0, progress))
            if self._goals[goal_id].progress >= 1.0:
                self._goals[goal_id].completed = True

    def complete_goal(self, goal_id):
        if goal_id in self._goals:
            self._goals[goal_id].completed = True
            self._goals[goal_id].progress = 1.0

    def get_active_goals(self):
        return [g for g in self._goals.values() if not g.completed]

    def update_alliance(self, agent_id, delta):
        current = self._alliances.get(agent_id, 0.0)
        new_value = max(-1.0, min(1.0, current + delta))

        if new_value > 0.1:
            self._alliances[agent_id] = new_value
            self._enemies.pop(agent_id, None)
        elif new_value < -0.1:
            self._enemies[agent_id] = abs(new_value)
            self._alliances.pop(agent_id, None)
        else:
            self._alliances.pop(agent_id, None)
            self._enemies.pop(agent_id, None)

    def get_allies(self, min_strength=0.3):
        return {k: v for k, v in self._alliances.items() if v >= min_strength}

    def get_enemies(self, min_strength=0.3):
        return {k: v for k, v in self._enemies.items() if v >= min_strength}

    def set_preference(self, key, value):
        self._preferences[key] = value

    def get_preference(self, key, default=None):
        return self._preferences.get(key, default)

    def add_strategic_note(self, tick, note, category="general"):
        self._strategic_notes.append({
            "tick": tick,
            "note": note,
            "category": category,
            "timestamp": time.time(),
        })
        if len(self._strategic_notes) > 100:
            self._strategic_notes = self._strategic_notes[-100:]

    def record_trade(self, agent_id, tick, offered, received, fair):
        if agent_id not in self._trade_history:
            self._trade_history[agent_id] = []

        self._trade_history[agent_id].append({
            "tick": tick,
            "offered": offered,
            "received": received,
            "fair": fair,
        })

        if fair:
            self.update_alliance(agent_id, 0.1)
        else:
            self.update_alliance(agent_id, -0.15)

    def get_trade_history(self, agent_id):
        return self._trade_history.get(agent_id, [])

    def record_reputation_event(self, agent_id, tick, event, impact):
        if agent_id not in self._reputation_memory:
            self._reputation_memory[agent_id] = []

        self._reputation_memory[agent_id].append({
            "tick": tick,
            "event": event,
            "impact": impact,
        })

    def summarize(self):
        lines = []

        active_goals = self.get_active_goals()
        if active_goals:
            lines.append("CURRENT GOALS:")
            for goal in sorted(active_goals, key=lambda g: -g.priority)[:3]:
                lines.append(f"  - {goal.description} (priority: {goal.priority:.1f}, progress: {goal.progress*100:.0f}%)")

        allies = self.get_allies()
        if allies:
            lines.append("ALLIES:")
            for agent_id, strength in sorted(allies.items(), key=lambda x: -x[1])[:3]:
                lines.append(f"  - {agent_id} (trust: {strength:.2f})")

        enemies = self.get_enemies()
        if enemies:
            lines.append("AVOID:")
            for agent_id, strength in sorted(enemies.items(), key=lambda x: -x[1])[:3]:
                lines.append(f"  - {agent_id} (distrust: {strength:.2f})")

        recent_notes = self._strategic_notes[-3:] if self._strategic_notes else []
        if recent_notes:
            lines.append("STRATEGIC NOTES:")
            for note in recent_notes:
                lines.append(f"  - {note['note']}")

        return "\n".join(lines) if lines else "No long-term memories."

    def to_dict(self):
        return {
            "goals": {k: {"description": v.description, "priority": v.priority, "progress": v.progress, "completed": v.completed}
                      for k, v in self._goals.items()},
            "alliances": dict(self._alliances),
            "enemies": dict(self._enemies),
            "preferences": dict(self._preferences),
            "strategic_notes": self._strategic_notes[-20:],
        }


class MemorySubsystem:
    def __init__(self, short_term_capacity=50, distill_interval=50):
        self._short_term = {}
        self._long_term = {}
        self.short_term_capacity = short_term_capacity
        self.distill_interval = distill_interval
        self._last_distill_tick = {}

    def get_short_term(self, agent_id):
        if agent_id not in self._short_term:
            self._short_term[agent_id] = ShortTermMemory(self.short_term_capacity)
        return self._short_term[agent_id]

    def get_long_term(self, agent_id):
        if agent_id not in self._long_term:
            self._long_term[agent_id] = LongTermMemory()
        return self._long_term[agent_id]

    def record_action(self, agent_id, tick, action_type, details, success):
        self.get_short_term(agent_id).add_action(tick, action_type, details, success)

    def record_message_received(self, agent_id, tick, sender_id, content):
        self.get_short_term(agent_id).add_message_received(tick, sender_id, content)

    def record_message_sent(self, agent_id, tick, recipient_id, content):
        self.get_short_term(agent_id).add_message_sent(tick, recipient_id, content)

    def record_trade(self, agent_id, tick, other_agent, offered, received, success):
        self.get_short_term(agent_id).add_trade(tick, other_agent, offered, received, success)
        if success:
            fair = self._evaluate_trade_fairness(offered, received)
            self.get_long_term(agent_id).record_trade(other_agent, tick, offered, received, fair)

    def _evaluate_trade_fairness(self, offered, received):
        offered_value = sum(item[1] if isinstance(item, (list, tuple)) else item.get("quantity", 1) for item in offered)
        received_value = sum(item[1] if isinstance(item, (list, tuple)) else item.get("quantity", 1) for item in received)

        if offered_value == 0 and received_value == 0:
            return True
        if offered_value == 0 or received_value == 0:
            return False

        ratio = received_value / offered_value
        return 0.5 <= ratio <= 2.0

    def should_distill(self, agent_id, current_tick):
        last_tick = self._last_distill_tick.get(agent_id, 0)
        return current_tick - last_tick >= self.distill_interval

    def distill_memories(self, agent_id, current_tick):
        short_term = self.get_short_term(agent_id)
        long_term = self.get_long_term(agent_id)

        since_last = self._last_distill_tick.get(agent_id, 0)
        entries = short_term.get_since_tick(since_last)

        trade_partners = {}
        for entry in entries:
            if entry.entry_type == "trade":
                partner = entry.content.get("other_agent")
                if partner:
                    if partner not in trade_partners:
                        trade_partners[partner] = {"success": 0, "fail": 0}
                    if entry.content.get("success"):
                        trade_partners[partner]["success"] += 1
                    else:
                        trade_partners[partner]["fail"] += 1

        for partner, stats in trade_partners.items():
            if stats["success"] > stats["fail"]:
                long_term.update_alliance(partner, 0.1)
            elif stats["fail"] > stats["success"]:
                long_term.update_alliance(partner, -0.1)

        self._last_distill_tick[agent_id] = current_tick

    def get_memory_summary(self, agent_id, max_short_term=5):
        short_term = self.get_short_term(agent_id)
        long_term = self.get_long_term(agent_id)

        lines = []

        lt_summary = long_term.summarize()
        if lt_summary and lt_summary != "No long-term memories.":
            lines.append("=== LONG-TERM MEMORY ===")
            lines.append(lt_summary)
            lines.append("")

        st_summary = short_term.summarize(max_short_term)
        if st_summary and st_summary != "No recent memories.":
            lines.append("=== RECENT EVENTS ===")
            lines.append(st_summary)

        return "\n".join(lines) if lines else "No memories yet."

    def clear_agent_memory(self, agent_id):
        if agent_id in self._short_term:
            del self._short_term[agent_id]
        if agent_id in self._long_term:
            del self._long_term[agent_id]
        if agent_id in self._last_distill_tick:
            del self._last_distill_tick[agent_id]

    def clear_all(self):
        self._short_term.clear()
        self._long_term.clear()
        self._last_distill_tick.clear()
