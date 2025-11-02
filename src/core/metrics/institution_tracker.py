from collections import defaultdict


class InstitutionSnapshot:
    def __init__(self, tick, groups_count, groups_by_type, total_members, avg_group_size,
                 governance_actions, proposals_passed, proposals_failed, contracts_active, contracts_breached):
        self.tick = tick
        self.groups_count = groups_count
        self.groups_by_type = groups_by_type
        self.total_members = total_members
        self.avg_group_size = avg_group_size
        self.governance_actions = governance_actions
        self.proposals_passed = proposals_passed
        self.proposals_failed = proposals_failed
        self.contracts_active = contracts_active
        self.contracts_breached = contracts_breached

    def to_dict(self):
        return {
            "tick": self.tick,
            "groups_count": self.groups_count,
            "groups_by_type": self.groups_by_type,
            "total_members": self.total_members,
            "avg_group_size": self.avg_group_size,
            "governance_actions": self.governance_actions,
            "proposals_passed": self.proposals_passed,
            "proposals_failed": self.proposals_failed,
            "contracts_active": self.contracts_active,
            "contracts_breached": self.contracts_breached,
        }


class InstitutionTracker:
    def __init__(self):
        self._governance_actions = []
        self._institution_snapshots = []
        self._group_lifecycles = {}
        self._max_history = 1000

    def record_governance_action(self, tick, action_type, agent_id, group_id=None, details=None):
        self._governance_actions.append({
            "tick": tick,
            "action_type": action_type,
            "agent_id": agent_id,
            "group_id": group_id,
            "details": details or {},
        })

        if len(self._governance_actions) > self._max_history:
            self._governance_actions.pop(0)

    def record_group_created(self, group_id, tick, founder_id, group_type):
        self._group_lifecycles[group_id] = {
            "created_tick": tick,
            "founder_id": founder_id,
            "group_type": group_type,
            "disbanded_tick": None,
            "peak_membership": 1,
            "member_history": [(tick, 1)],
        }

    def record_membership_change(self, group_id, tick, new_count):
        if group_id in self._group_lifecycles:
            lifecycle = self._group_lifecycles[group_id]
            lifecycle["member_history"].append((tick, new_count))
            lifecycle["peak_membership"] = max(lifecycle["peak_membership"], new_count)

    def record_group_disbanded(self, group_id, tick):
        if group_id in self._group_lifecycles:
            self._group_lifecycles[group_id]["disbanded_tick"] = tick

    def take_snapshot(self, tick, group_manager=None, governance_system=None, contract_manager=None):
        groups_count = 0
        groups_by_type = {}
        total_members = 0

        if group_manager:
            stats = group_manager.get_stats()
            groups_count = stats.get("total_groups", 0)
            groups_by_type = stats.get("type_counts", {})
            total_members = stats.get("total_members", 0)

        avg_group_size = total_members / groups_count if groups_count > 0 else 0.0

        governance_actions = len([
            a for a in self._governance_actions
            if a["tick"] == tick
        ])

        proposals_passed = 0
        proposals_failed = 0
        if governance_system:
            stats = governance_system.get_stats()
            proposals_passed = stats.get("status_counts", {}).get("PASSED", 0)
            proposals_failed = stats.get("status_counts", {}).get("FAILED", 0)

        contracts_active = 0
        contracts_breached = 0
        if contract_manager:
            stats = contract_manager.get_stats()
            contracts_active = stats.get("status_counts", {}).get("ACTIVE", 0)
            contracts_breached = stats.get("total_breaches", 0)

        snapshot = InstitutionSnapshot(
            tick=tick,
            groups_count=groups_count,
            groups_by_type=groups_by_type,
            total_members=total_members,
            avg_group_size=avg_group_size,
            governance_actions=governance_actions,
            proposals_passed=proposals_passed,
            proposals_failed=proposals_failed,
            contracts_active=contracts_active,
            contracts_breached=contracts_breached,
        )

        self._institution_snapshots.append(snapshot)
        if len(self._institution_snapshots) > self._max_history:
            self._institution_snapshots.pop(0)

        return snapshot

    def get_snapshot_history(self, since_tick=None):
        history = self._institution_snapshots
        if since_tick is not None:
            history = [s for s in history if s.tick >= since_tick]
        return history

    def get_governance_actions(self, since_tick=None, action_type=None):
        actions = self._governance_actions

        if since_tick is not None:
            actions = [a for a in actions if a["tick"] >= since_tick]

        if action_type is not None:
            actions = [a for a in actions if a["action_type"] == action_type]

        return actions

    def get_group_lifespan(self, group_id):
        lifecycle = self._group_lifecycles.get(group_id)
        if not lifecycle:
            return None

        if lifecycle["disbanded_tick"]:
            return lifecycle["disbanded_tick"] - lifecycle["created_tick"]

        return None

    def get_institution_emergence_metrics(self, tick):
        current_groups = len([
            g for g in self._group_lifecycles.values()
            if g["disbanded_tick"] is None or g["disbanded_tick"] > tick
        ])

        lifespans = []
        for lifecycle in self._group_lifecycles.values():
            if lifecycle["disbanded_tick"]:
                lifespan = lifecycle["disbanded_tick"] - lifecycle["created_tick"]
                lifespans.append(lifespan)

        avg_lifespan = sum(lifespans) / len(lifespans) if lifespans else 0.0

        type_counts = defaultdict(int)
        for lifecycle in self._group_lifecycles.values():
            if lifecycle["disbanded_tick"] is None or lifecycle["disbanded_tick"] > tick:
                type_counts[lifecycle["group_type"]] += 1

        governance_velocity = len([
            a for a in self._governance_actions
            if tick - 50 <= a["tick"] <= tick
        ])

        return {
            "tick": tick,
            "active_groups": current_groups,
            "total_groups_ever": len(self._group_lifecycles),
            "avg_group_lifespan": avg_lifespan,
            "groups_by_type": dict(type_counts),
            "governance_velocity": governance_velocity,
            "institution_score": self._calculate_institution_score(tick),
        }

    def _calculate_institution_score(self, tick):
        active_groups = len([
            g for g in self._group_lifecycles.values()
            if g["disbanded_tick"] is None or g["disbanded_tick"] > tick
        ])

        group_score = min(1.0, active_groups / 10)

        recent_actions = len([
            a for a in self._governance_actions
            if tick - 100 <= a["tick"] <= tick
        ])
        governance_score = min(1.0, recent_actions / 50)

        stable_groups = sum(
            1 for g in self._group_lifecycles.values()
            if (g["disbanded_tick"] is None or g["disbanded_tick"] > tick)
            and tick - g["created_tick"] > 100
        )
        stability_score = min(1.0, stable_groups / 5)

        institution_score = (
            group_score * 0.3 +
            governance_score * 0.3 +
            stability_score * 0.4
        )

        return institution_score

    def to_dict(self):
        current_snapshot = (
            self._institution_snapshots[-1].to_dict()
            if self._institution_snapshots else None
        )

        return {
            "current_snapshot": current_snapshot,
            "total_governance_actions": len(self._governance_actions),
            "total_groups_tracked": len(self._group_lifecycles),
        }
