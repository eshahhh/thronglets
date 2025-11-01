from enum import Enum, auto
import time
import uuid


class GroupType(Enum):
    GUILD = auto()
    FIRM = auto()
    COUNCIL = auto()
    COOPERATIVE = auto()
    ALLIANCE = auto()
    CUSTOM = auto()


class GroupRole(Enum):
    LEADER = auto()
    OFFICER = auto()
    MEMBER = auto()
    APPLICANT = auto()
    BANNED = auto()


class GroupMember:
    def __init__(self, agent_id, role, joined_tick, reputation_contribution=0.0, votes_cast=0):
        self.agent_id = agent_id
        self.role = role
        self.joined_tick = joined_tick
        self.reputation_contribution = reputation_contribution
        self.votes_cast = votes_cast

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "role": self.role.name,
            "joined_tick": self.joined_tick,
            "reputation_contribution": self.reputation_contribution,
            "votes_cast": self.votes_cast,
        }


class Group:
    def __init__(
        self,
        group_id,
        name,
        group_type,
        created_tick,
        founder_id,
        members=None,
        treasury=None,
        rules=None,
        purpose="",
        location_id=None,
        is_public=True,
        min_reputation=0.0,
        max_members=100,
    ):
        self.group_id = group_id
        self.name = name
        self.group_type = group_type
        self.created_tick = created_tick
        self.founder_id = founder_id
        self.members = members if members is not None else {}
        self.treasury = treasury if treasury is not None else {}
        self.rules = rules if rules is not None else []
        self.purpose = purpose
        self.location_id = location_id
        self.is_public = is_public
        self.min_reputation = min_reputation
        self.max_members = max_members

    def to_dict(self):
        return {
            "group_id": self.group_id,
            "name": self.name,
            "group_type": self.group_type.name,
            "created_tick": self.created_tick,
            "founder_id": self.founder_id,
            "members": {k: v.to_dict() for k, v in self.members.items()},
            "treasury": self.treasury,
            "rules": self.rules,
            "purpose": self.purpose,
            "location_id": self.location_id,
            "is_public": self.is_public,
            "min_reputation": self.min_reputation,
            "max_members": self.max_members,
        }

    def get_member_count(self):
        return len([m for m in self.members.values() if m.role not in (GroupRole.APPLICANT, GroupRole.BANNED)])

    def get_leaders(self):
        return [m.agent_id for m in self.members.values() if m.role == GroupRole.LEADER]

    def get_officers(self):
        return [m.agent_id for m in self.members.values() if m.role in (GroupRole.LEADER, GroupRole.OFFICER)]

    def is_member(self, agent_id):
        member = self.members.get(agent_id)
        return member is not None and member.role not in (GroupRole.APPLICANT, GroupRole.BANNED)

    def can_vote(self, agent_id):
        member = self.members.get(agent_id)
        return member is not None and member.role in (GroupRole.LEADER, GroupRole.OFFICER, GroupRole.MEMBER)


class GroupManager:
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self._groups = {}
        self._agent_groups = {}
        self._callbacks = []

        from ..logging.live_logger import get_live_logger
        self._logger = get_live_logger()

    def create_group(
        self,
        founder_id,
        name,
        group_type,
        tick,
        purpose="",
        location_id=None,
        is_public=True,
        min_reputation=0.0,
        max_members=100,
        initial_rules=None,
    ):
        founder = self.agent_manager.get_agent(founder_id)
        if not founder:
            self._logger.error(f"Founder not found: {founder_id}")
            return None

        group_id = f"group_{uuid.uuid4().hex[:12]}"

        group = Group(
            group_id=group_id,
            name=name,
            group_type=group_type,
            created_tick=tick,
            founder_id=founder_id,
            purpose=purpose,
            location_id=location_id,
            is_public=is_public,
            min_reputation=min_reputation,
            max_members=max_members,
            rules=initial_rules or [],
        )

        group.members[founder_id] = GroupMember(
            agent_id=founder_id,
            role=GroupRole.LEADER,
            joined_tick=tick,
        )

        self._groups[group_id] = group

        if founder_id not in self._agent_groups:
            self._agent_groups[founder_id] = set()
        self._agent_groups[founder_id].add(group_id)

        self._logger.log_governance_action(
            agent_id=founder_id,
            tick=tick,
            action_type="FORM_GROUP",
            group_id=group_id,
            details={"name": name, "type": group_type.name},
        )

        for callback in self._callbacks:
            try:
                callback("group_created", group)
            except Exception:
                pass

        return group

    def join_group(self, group_id, agent_id, tick, as_applicant=False):
        group = self._groups.get(group_id)
        if not group:
            return False

        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return False

        if agent_id in group.members:
            existing = group.members[agent_id]
            if existing.role == GroupRole.BANNED:
                return False
            return True

        if group.get_member_count() >= group.max_members:
            return False

        if not group.is_public and not as_applicant:
            as_applicant = True

        reputation = agent.needs.get("reputation", 50.0)
        if reputation < group.min_reputation:
            return False

        role = GroupRole.APPLICANT if as_applicant else GroupRole.MEMBER

        group.members[agent_id] = GroupMember(
            agent_id=agent_id,
            role=role,
            joined_tick=tick,
        )

        if agent_id not in self._agent_groups:
            self._agent_groups[agent_id] = set()
        self._agent_groups[agent_id].add(group_id)

        self._logger.log_governance_action(
            agent_id=agent_id,
            tick=tick,
            action_type="JOIN_GROUP" if role == GroupRole.MEMBER else "APPLY_GROUP",
            group_id=group_id,
        )

        return True

    def leave_group(self, group_id, agent_id, tick):
        group = self._groups.get(group_id)
        if not group:
            return False

        if agent_id not in group.members:
            return False

        member = group.members[agent_id]
        if member.role == GroupRole.LEADER and len(group.get_leaders()) <= 1:
            other_members = [
                m for m in group.members.values()
                if m.agent_id != agent_id and m.role == GroupRole.MEMBER
            ]
            if other_members:
                other_members[0].role = GroupRole.LEADER
            else:
                self.disband_group(group_id, agent_id, tick)
                return True

        del group.members[agent_id]

        if agent_id in self._agent_groups:
            self._agent_groups[agent_id].discard(group_id)

        self._logger.log_governance_action(
            agent_id=agent_id,
            tick=tick,
            action_type="LEAVE_GROUP",
            group_id=group_id,
        )

        return True

    def approve_member(self, group_id, approver_id, applicant_id, tick):
        group = self._groups.get(group_id)
        if not group:
            return False

        if approver_id not in group.get_officers():
            return False

        if applicant_id not in group.members:
            return False

        member = group.members[applicant_id]
        if member.role != GroupRole.APPLICANT:
            return False

        member.role = GroupRole.MEMBER

        self._logger.log_governance_action(
            agent_id=approver_id,
            tick=tick,
            action_type="APPROVE_MEMBER",
            group_id=group_id,
            details={"approved": applicant_id},
        )

        return True

    def kick_member(self, group_id, kicker_id, target_id, tick, ban=False):
        group = self._groups.get(group_id)
        if not group:
            return False

        if kicker_id not in group.get_officers():
            return False

        if target_id not in group.members:
            return False

        target_member = group.members[target_id]
        if target_member.role == GroupRole.LEADER:
            return False

        if ban:
            target_member.role = GroupRole.BANNED
        else:
            del group.members[target_id]
            if target_id in self._agent_groups:
                self._agent_groups[target_id].discard(group_id)

        self._logger.log_governance_action(
            agent_id=kicker_id,
            tick=tick,
            action_type="BAN_MEMBER" if ban else "KICK_MEMBER",
            group_id=group_id,
            details={"target": target_id},
        )

        return True

    def promote_member(self, group_id, promoter_id, target_id, new_role, tick):
        group = self._groups.get(group_id)
        if not group:
            return False

        if promoter_id not in group.get_leaders():
            return False

        if target_id not in group.members:
            return False

        target_member = group.members[target_id]
        if target_member.role in (GroupRole.APPLICANT, GroupRole.BANNED):
            return False

        target_member.role = new_role

        self._logger.log_governance_action(
            agent_id=promoter_id,
            tick=tick,
            action_type="PROMOTE_MEMBER",
            group_id=group_id,
            details={"target": target_id, "new_role": new_role.name},
        )

        return True

    def contribute_to_treasury(self, group_id, contributor_id, item_type, quantity, tick):
        group = self._groups.get(group_id)
        if not group:
            return False

        if not group.is_member(contributor_id):
            return False

        agent = self.agent_manager.get_agent(contributor_id)
        if not agent:
            return False

        if agent.inventory.get(item_type, 0) < quantity:
            return False

        self.agent_manager.update_agent_inventory(contributor_id, item_type, -quantity)

        current = group.treasury.get(item_type, 0)
        group.treasury[item_type] = current + quantity

        member = group.members[contributor_id]
        member.reputation_contribution += quantity

        self._logger.log_governance_action(
            agent_id=contributor_id,
            tick=tick,
            action_type="TREASURY_CONTRIBUTE",
            group_id=group_id,
            details={"item": item_type, "quantity": quantity},
        )

        return True

    def withdraw_from_treasury(self, group_id, withdrawer_id, recipient_id, item_type, quantity, tick):
        group = self._groups.get(group_id)
        if not group:
            return False

        if withdrawer_id not in group.get_officers():
            return False

        if group.treasury.get(item_type, 0) < quantity:
            return False

        recipient = self.agent_manager.get_agent(recipient_id)
        if not recipient:
            return False

        group.treasury[item_type] -= quantity
        if group.treasury[item_type] <= 0:
            del group.treasury[item_type]

        self.agent_manager.update_agent_inventory(recipient_id, item_type, quantity)

        self._logger.log_governance_action(
            agent_id=withdrawer_id,
            tick=tick,
            action_type="TREASURY_WITHDRAW",
            group_id=group_id,
            details={"item": item_type, "quantity": quantity, "recipient": recipient_id},
        )

        return True

    def disband_group(self, group_id, disbander_id, tick):
        group = self._groups.get(group_id)
        if not group:
            return False

        if disbander_id not in group.get_leaders():
            return False

        for member in group.members.values():
            if member.agent_id in self._agent_groups:
                self._agent_groups[member.agent_id].discard(group_id)

        del self._groups[group_id]

        self._logger.log_governance_action(
            agent_id=disbander_id,
            tick=tick,
            action_type="DISBAND_GROUP",
            group_id=group_id,
        )

        for callback in self._callbacks:
            try:
                callback("group_disbanded", {"group_id": group_id, "tick": tick})
            except Exception:
                pass

        return True

    def add_rule(self, group_id, proposer_id, rule, tick):
        group = self._groups.get(group_id)
        if not group:
            return False

        if proposer_id not in group.get_officers():
            return False

        rule["id"] = f"rule_{uuid.uuid4().hex[:8]}"
        rule["created_tick"] = tick
        rule["created_by"] = proposer_id

        group.rules.append(rule)

        self._logger.log_governance_action(
            agent_id=proposer_id,
            tick=tick,
            action_type="ADD_RULE",
            group_id=group_id,
            details={"rule_type": rule.get("type", "custom")},
        )

        return True

    def get_group(self, group_id):
        return self._groups.get(group_id)

    def get_agent_groups(self, agent_id):
        group_ids = self._agent_groups.get(agent_id, set())
        return [self._groups[gid] for gid in group_ids if gid in self._groups]

    def get_groups_by_type(self, group_type):
        return [g for g in self._groups.values() if g.group_type == group_type]

    def get_groups_at_location(self, location_id):
        return [g for g in self._groups.values() if g.location_id == location_id]

    def get_public_groups(self):
        return [g for g in self._groups.values() if g.is_public]

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_stats(self):
        type_counts = {}
        for gtype in GroupType:
            type_counts[gtype.name] = len(self.get_groups_by_type(gtype))

        total_members = sum(g.get_member_count() for g in self._groups.values())

        return {
            "total_groups": len(self._groups),
            "total_members": total_members,
            "type_counts": type_counts,
            "avg_members_per_group": total_members / len(self._groups) if self._groups else 0,
        }
