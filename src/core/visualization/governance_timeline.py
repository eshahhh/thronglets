from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict
import json
import time

class GovernanceEventType(Enum):
    GROUP_FORMED = auto()
    GROUP_DISSOLVED = auto()
    MEMBER_JOINED = auto()
    MEMBER_LEFT = auto()
    RULE_PROPOSED = auto()
    RULE_PASSED = auto()
    RULE_REJECTED = auto()
    RULE_ENFORCED = auto()
    VOTE_CAST = auto()
    LEADER_ELECTED = auto()
    LEADER_REMOVED = auto()
    CONFLICT_STARTED = auto()
    CONFLICT_RESOLVED = auto()
    RESOURCE_SHARED = auto()
    PUNISHMENT_APPLIED = auto()

@dataclass
class GovernanceEvent:
    tick: int
    timestamp: float
    event_type: GovernanceEventType
    group_id: str | None
    agent_id: str | None
    target_id: str | None = None
    rule_id: str | None = None
    details: dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "tick": self.tick,
            "timestamp": self.timestamp,
            "event_type": self.event_type.name,
            "group_id": self.group_id,
            "agent_id": self.agent_id,
            "target_id": self.target_id,
            "rule_id": self.rule_id,
            "details": self.details,
        }

@dataclass
class GroupTimeline:
    group_id: str
    name: str
    formed_tick: int
    dissolved_tick: int | None = None
    events: list[GovernanceEvent] = field(default_factory=list)
    member_history: list[dict] = field(default_factory=list)
    rule_history: list[dict] = field(default_factory=list)
    peak_membership: int = 0
    total_votes: int = 0
    rules_passed: int = 0
    rules_rejected: int = 0

class GovernanceTimeline:
    def __init__(self):
        self._events = []
        self._groups = {}
        self._agent_affiliations = defaultdict(list)
        self._rule_registry = {}
        
    def record_group_formed(self, tick, group_id, founder_id, name=None, initial_members=None):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.GROUP_FORMED,
            group_id=group_id,
            agent_id=founder_id,
            details={
                "name": name or group_id,
                "initial_members": initial_members or [founder_id],
            }
        )
        self._events.append(event)
        
        self._groups[group_id] = GroupTimeline(
            group_id=group_id,
            name=name or group_id,
            formed_tick=tick,
        )
        self._groups[group_id].events.append(event)
        self._groups[group_id].member_history.append({
            "tick": tick,
            "action": "formed",
            "members": initial_members or [founder_id],
        })
        self._groups[group_id].peak_membership = len(initial_members) if initial_members else 1
        
        for member in (initial_members or [founder_id]):
            self._agent_affiliations[member].append({
                "tick": tick,
                "group_id": group_id,
                "action": "joined",
            })
            
    def record_group_dissolved(self, tick, group_id, reason=None):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.GROUP_DISSOLVED,
            group_id=group_id,
            agent_id=None,
            details={"reason": reason},
        )
        self._events.append(event)
        
        if group_id in self._groups:
            self._groups[group_id].dissolved_tick = tick
            self._groups[group_id].events.append(event)
            
    def record_member_joined(self, tick, group_id, agent_id, invited_by=None):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.MEMBER_JOINED,
            group_id=group_id,
            agent_id=agent_id,
            details={"invited_by": invited_by},
        )
        self._events.append(event)
        
        if group_id in self._groups:
            group = self._groups[group_id]
            group.events.append(event)
            current_count = len(set(
                m["members"][-1] if isinstance(m["members"], list) else 0
                for m in group.member_history
            )) + 1
            group.peak_membership = max(group.peak_membership, current_count)
            group.member_history.append({
                "tick": tick,
                "action": "joined",
                "agent_id": agent_id,
            })
            
        self._agent_affiliations[agent_id].append({
            "tick": tick,
            "group_id": group_id,
            "action": "joined",
        })
        
    def record_member_left(self, tick, group_id, agent_id, reason=None):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.MEMBER_LEFT,
            group_id=group_id,
            agent_id=agent_id,
            details={"reason": reason},
        )
        self._events.append(event)
        
        if group_id in self._groups:
            self._groups[group_id].events.append(event)
            self._groups[group_id].member_history.append({
                "tick": tick,
                "action": "left",
                "agent_id": agent_id,
            })
            
        self._agent_affiliations[agent_id].append({
            "tick": tick,
            "group_id": group_id,
            "action": "left",
        })
        
    def record_rule_proposed(self, tick, group_id, proposer_id, rule_id, rule_type, description):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.RULE_PROPOSED,
            group_id=group_id,
            agent_id=proposer_id,
            rule_id=rule_id,
            details={
                "rule_type": rule_type,
                "description": description,
            },
        )
        self._events.append(event)
        
        self._rule_registry[rule_id] = {
            "group_id": group_id,
            "proposer_id": proposer_id,
            "proposed_tick": tick,
            "rule_type": rule_type,
            "description": description,
            "status": "proposed",
            "votes_for": 0,
            "votes_against": 0,
        }
        
        if group_id in self._groups:
            self._groups[group_id].events.append(event)
            self._groups[group_id].rule_history.append({
                "tick": tick,
                "rule_id": rule_id,
                "action": "proposed",
            })
            
    def record_vote(self, tick, group_id, voter_id, rule_id, vote):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.VOTE_CAST,
            group_id=group_id,
            agent_id=voter_id,
            rule_id=rule_id,
            details={"vote": "for" if vote else "against"},
        )
        self._events.append(event)
        
        if rule_id in self._rule_registry:
            if vote:
                self._rule_registry[rule_id]["votes_for"] += 1
            else:
                self._rule_registry[rule_id]["votes_against"] += 1
                
        if group_id in self._groups:
            self._groups[group_id].events.append(event)
            self._groups[group_id].total_votes += 1
            
    def record_rule_passed(self, tick, group_id, rule_id, final_votes=None):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.RULE_PASSED,
            group_id=group_id,
            agent_id=None,
            rule_id=rule_id,
            details={"final_votes": final_votes or {}},
        )
        self._events.append(event)
        
        if rule_id in self._rule_registry:
            self._rule_registry[rule_id]["status"] = "passed"
            self._rule_registry[rule_id]["passed_tick"] = tick
            
        if group_id in self._groups:
            self._groups[group_id].events.append(event)
            self._groups[group_id].rules_passed += 1
            self._groups[group_id].rule_history.append({
                "tick": tick,
                "rule_id": rule_id,
                "action": "passed",
            })
            
    def record_rule_rejected(self, tick, group_id, rule_id, final_votes=None):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.RULE_REJECTED,
            group_id=group_id,
            agent_id=None,
            rule_id=rule_id,
            details={"final_votes": final_votes or {}},
        )
        self._events.append(event)
        
        if rule_id in self._rule_registry:
            self._rule_registry[rule_id]["status"] = "rejected"
            
        if group_id in self._groups:
            self._groups[group_id].events.append(event)
            self._groups[group_id].rules_rejected += 1
            self._groups[group_id].rule_history.append({
                "tick": tick,
                "rule_id": rule_id,
                "action": "rejected",
            })
            
    def record_leader_elected(self, tick, group_id, leader_id, votes=0):
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=GovernanceEventType.LEADER_ELECTED,
            group_id=group_id,
            agent_id=leader_id,
            details={"votes_received": votes},
        )
        self._events.append(event)
        
        if group_id in self._groups:
            self._groups[group_id].events.append(event)
            
    def record_conflict(self, tick, group_id, party_a, party_b, resolved=False, resolution=None):
        event_type = GovernanceEventType.CONFLICT_RESOLVED if resolved else GovernanceEventType.CONFLICT_STARTED
        event = GovernanceEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=event_type,
            group_id=group_id,
            agent_id=party_a,
            target_id=party_b,
            details={"resolution": resolution} if resolved else {},
        )
        self._events.append(event)
        
        if group_id in self._groups:
            self._groups[group_id].events.append(event)
            
    def get_timeline(self, start_tick=0, end_tick=None):
        events = self._events
        if end_tick is not None:
            events = [e for e in events if start_tick <= e.tick <= end_tick]
        else:
            events = [e for e in events if e.tick >= start_tick]
        return [e.to_dict() for e in events]
        
    def get_group_timeline(self, group_id):
        if group_id not in self._groups:
            return None
            
        group = self._groups[group_id]
        return {
            "group_id": group.group_id,
            "name": group.name,
            "formed_tick": group.formed_tick,
            "dissolved_tick": group.dissolved_tick,
            "active": group.dissolved_tick is None,
            "peak_membership": group.peak_membership,
            "total_votes": group.total_votes,
            "rules_passed": group.rules_passed,
            "rules_rejected": group.rules_rejected,
            "events": [e.to_dict() for e in group.events],
        }
        
    def get_agent_history(self, agent_id):
        return self._agent_affiliations.get(agent_id, [])
        
    def get_rule_status(self, rule_id):
        return self._rule_registry.get(rule_id)
        
    def get_active_groups(self, tick=None):
        results = []
        for gid, group in self._groups.items():
            if group.dissolved_tick is None:
                if tick is None or group.formed_tick <= tick:
                    results.append({
                        "group_id": gid,
                        "name": group.name,
                        "formed_tick": group.formed_tick,
                        "peak_membership": group.peak_membership,
                    })
        return results
        
    def get_governance_stats(self):
        total_groups = len(self._groups)
        active_groups = sum(1 for g in self._groups.values() if g.dissolved_tick is None)
        total_events = len(self._events)
        
        event_counts = defaultdict(int)
        for event in self._events:
            event_counts[event.event_type.name] += 1
            
        return {
            "total_groups": total_groups,
            "active_groups": active_groups,
            "dissolved_groups": total_groups - active_groups,
            "total_events": total_events,
            "total_rules": len(self._rule_registry),
            "rules_passed": sum(1 for r in self._rule_registry.values() if r["status"] == "passed"),
            "rules_rejected": sum(1 for r in self._rule_registry.values() if r["status"] == "rejected"),
            "event_breakdown": dict(event_counts),
        }
        
    def to_json(self):
        return json.dumps({
            "events": [e.to_dict() for e in self._events],
            "groups": {gid: self.get_group_timeline(gid) for gid in self._groups},
            "rules": self._rule_registry,
            "stats": self.get_governance_stats(),
        }, indent=2)
        
    def render_ascii_timeline(self, width=80):
        if not self._events:
            return "No governance events recorded"
            
        min_tick = min(e.tick for e in self._events)
        max_tick = max(e.tick for e in self._events)
        tick_range = max_tick - min_tick or 1
        
        lines = ["Governance Timeline", "=" * width]
        
        for group in sorted(self._groups.values(), key=lambda g: g.formed_tick):
            start_pos = int((group.formed_tick - min_tick) / tick_range * (width - 20))
            end_pos = width - 10 if group.dissolved_tick is None else int((group.dissolved_tick - min_tick) / tick_range * (width - 20))
            
            bar = " " * start_pos + "├" + "─" * (end_pos - start_pos - 1)
            if group.dissolved_tick is None:
                bar += "→"
            else:
                bar += "┤"
                
            lines.append(f"{group.name[:10]:<10} {bar}")
            
            event_markers = ""
            for event in group.events:
                pos = int((event.tick - min_tick) / tick_range * (width - 20))
                marker = {
                    GovernanceEventType.RULE_PASSED: "R",
                    GovernanceEventType.LEADER_ELECTED: "L",
                    GovernanceEventType.MEMBER_JOINED: "+",
                    GovernanceEventType.MEMBER_LEFT: "-",
                    GovernanceEventType.CONFLICT_STARTED: "!",
                }.get(event.event_type, "·")
                event_markers = event_markers[:pos] + marker + event_markers[pos+1:]
                
            if event_markers.strip():
                lines.append(f"{'':10} {event_markers}")
                
        lines.append("─" * width)
        lines.append(f"Tick: {min_tick:<10} {'':>{width-30}} {max_tick}")
        
        lines.append("\nLegend: R=Rule Passed, L=Leader Elected, +=Join, -=Leave, !=Conflict")
        
        stats = self.get_governance_stats()
        lines.append(f"\nGroups: {stats['total_groups']} (active: {stats['active_groups']}) | Rules: {stats['rules_passed']} passed, {stats['rules_rejected']} rejected")
        
        return '\n'.join(lines)
