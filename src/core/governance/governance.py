from dataclasses import dataclass, field
from enum import Enum, auto
import time
import uuid


class ProposalStatus(Enum):
    OPEN = auto()
    PASSED = auto()
    FAILED = auto()
    EXPIRED = auto()
    VETOED = auto()


class VoteType(Enum):
    SIMPLE_MAJORITY = auto()
    SUPER_MAJORITY = auto()
    UNANIMOUS = auto()
    PLURALITY = auto()
    WEIGHTED = auto()


class RuleType(Enum):
    TAX = auto()
    RESOURCE_LIMIT = auto()
    TRADE_RESTRICTION = auto()
    MEMBERSHIP = auto()
    GOVERNANCE = auto()
    CUSTOM = auto()


@dataclass
class Vote:
    voter_id: str
    vote: str
    weight: float = 1.0
    tick: int = 0

    def to_dict(self):
        return {
            "voter_id": self.voter_id,
            "vote": self.vote,
            "weight": self.weight,
            "tick": self.tick,
        }


@dataclass
class Rule:
    rule_id: str
    rule_type: RuleType
    parameters: dict
    created_tick: int
    created_by: str
    group_id: str
    is_active: bool = True

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type.name,
            "parameters": self.parameters,
            "created_tick": self.created_tick,
            "created_by": self.created_by,
            "group_id": self.group_id,
            "is_active": self.is_active,
        }

    def apply(self, context):
        result = {"applied": False, "effects": []}

        if self.rule_type == RuleType.TAX:
            tax_rate = self.parameters.get("rate", 0.0)
            item_type = self.parameters.get("item_type")

            if "trade" in context and item_type:
                trade = context["trade"]
                for item in trade.get("items", []):
                    if item.get("item_type") == item_type:
                        tax_amount = int(item.get("quantity", 0) * tax_rate)
                        result["applied"] = True
                        result["effects"].append({
                            "type": "tax",
                            "item": item_type,
                            "amount": tax_amount,
                        })

        elif self.rule_type == RuleType.RESOURCE_LIMIT:
            limit = self.parameters.get("limit", float("inf"))
            resource = self.parameters.get("resource_type")

            if "harvest" in context and resource:
                harvest = context["harvest"]
                if harvest.get("resource_type") == resource:
                    current = harvest.get("amount", 0)
                    if current > limit:
                        result["applied"] = True
                        result["effects"].append({
                            "type": "limit",
                            "resource": resource,
                            "reduced_to": limit,
                        })

        return result


@dataclass
class Proposal:
    proposal_id: str
    group_id: str
    proposer_id: str
    title: str
    description: str
    proposal_type: str
    parameters: dict
    created_tick: int
    expiry_tick: int
    status: ProposalStatus = ProposalStatus.OPEN
    vote_type: VoteType = VoteType.SIMPLE_MAJORITY
    votes: list = field(default_factory=list)
    required_threshold: float = 0.5

    def to_dict(self):
        return {
            "proposal_id": self.proposal_id,
            "group_id": self.group_id,
            "proposer_id": self.proposer_id,
            "title": self.title,
            "description": self.description,
            "proposal_type": self.proposal_type,
            "parameters": self.parameters,
            "created_tick": self.created_tick,
            "expiry_tick": self.expiry_tick,
            "status": self.status.name,
            "vote_type": self.vote_type.name,
            "votes": [v.to_dict() for v in self.votes],
            "required_threshold": self.required_threshold,
        }

    def has_voted(self, agent_id):
        return any(v.voter_id == agent_id for v in self.votes)

    def get_vote_tally(self):
        tally = {}
        for vote in self.votes:
            if vote.vote not in tally:
                tally[vote.vote] = 0.0
            tally[vote.vote] += vote.weight
        return tally

    def get_total_votes(self):
        return sum(v.weight for v in self.votes)

    def is_expired(self, current_tick):
        return current_tick > self.expiry_tick


class GovernanceSystem:
    def __init__(self, group_manager):
        self.group_manager = group_manager
        self._proposals = {}
        self._rules = {}
        self._rules_by_group = {}
        self._callbacks = []

        from ..logging.live_logger import get_live_logger
        self._logger = get_live_logger()

    def create_proposal(
        self,
        group_id,
        proposer_id,
        title,
        description,
        proposal_type,
        parameters,
        tick,
        duration_ticks=50,
        vote_type=VoteType.SIMPLE_MAJORITY,
        required_threshold=0.5,
    ):
        group = self.group_manager.get_group(group_id)
        if not group:
            return None

        if not group.is_member(proposer_id):
            return None

        proposal_id = f"proposal_{uuid.uuid4().hex[:12]}"

        proposal = Proposal(
            proposal_id=proposal_id,
            group_id=group_id,
            proposer_id=proposer_id,
            title=title,
            description=description,
            proposal_type=proposal_type,
            parameters=parameters,
            created_tick=tick,
            expiry_tick=tick + duration_ticks,
            vote_type=vote_type,
            required_threshold=required_threshold,
        )

        self._proposals[proposal_id] = proposal

        self._logger.log_governance_action(
            agent_id=proposer_id,
            tick=tick,
            action_type="PROPOSE",
            group_id=group_id,
            details={"title": title, "type": proposal_type},
        )

        return proposal

    def cast_vote(
        self,
        proposal_id,
        voter_id,
        vote,
        tick,
    ):
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False

        if proposal.status != ProposalStatus.OPEN:
            return False

        if proposal.is_expired(tick):
            proposal.status = ProposalStatus.EXPIRED
            return False

        group = self.group_manager.get_group(proposal.group_id)
        if not group:
            return False

        if not group.can_vote(voter_id):
            return False

        if proposal.has_voted(voter_id):
            for existing_vote in proposal.votes:
                if existing_vote.voter_id == voter_id:
                    existing_vote.vote = vote
                    existing_vote.tick = tick
                    break
        else:
            member = group.members.get(voter_id)
            weight = 1.0
            if proposal.vote_type == VoteType.WEIGHTED and member:
                weight = 1.0 + (member.reputation_contribution / 100.0)

            proposal.votes.append(Vote(
                voter_id=voter_id,
                vote=vote,
                weight=weight,
                tick=tick,
            ))

            if member:
                member.votes_cast += 1

        self._logger.log_governance_action(
            agent_id=voter_id,
            tick=tick,
            action_type="VOTE",
            group_id=proposal.group_id,
            details={"proposal": proposal_id[:8], "vote": vote},
        )

        return True

    def tally_proposal(self, proposal_id, tick):
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None

        if proposal.status != ProposalStatus.OPEN:
            return proposal.status

        group = self.group_manager.get_group(proposal.group_id)
        if not group:
            return None

        eligible_voters = len([m for m in group.members.values() if group.can_vote(m.agent_id)])

        tally = proposal.get_vote_tally()
        total_votes = proposal.get_total_votes()

        if proposal.vote_type == VoteType.SIMPLE_MAJORITY:
            yes_votes = tally.get("yes", 0) + tally.get("for", 0) + tally.get("approve", 0)
            no_votes = tally.get("no", 0) + tally.get("against", 0) + tally.get("reject", 0)

            if total_votes > 0:
                if yes_votes / total_votes >= proposal.required_threshold:
                    proposal.status = ProposalStatus.PASSED
                elif no_votes / total_votes > (1 - proposal.required_threshold):
                    proposal.status = ProposalStatus.FAILED

        elif proposal.vote_type == VoteType.SUPER_MAJORITY:
            yes_votes = tally.get("yes", 0) + tally.get("for", 0)
            threshold = 0.67

            if total_votes > 0 and yes_votes / total_votes >= threshold:
                proposal.status = ProposalStatus.PASSED

        elif proposal.vote_type == VoteType.UNANIMOUS:
            no_votes = tally.get("no", 0) + tally.get("against", 0)
            if no_votes > 0:
                proposal.status = ProposalStatus.FAILED
            elif total_votes >= eligible_voters:
                proposal.status = ProposalStatus.PASSED

        if proposal.is_expired(tick) and proposal.status == ProposalStatus.OPEN:
            yes_votes = tally.get("yes", 0) + tally.get("for", 0) + tally.get("approve", 0)
            if total_votes > 0 and yes_votes / total_votes >= proposal.required_threshold:
                proposal.status = ProposalStatus.PASSED
            else:
                proposal.status = ProposalStatus.EXPIRED

        if proposal.status == ProposalStatus.PASSED:
            self._execute_proposal(proposal, tick)

            self._logger.log_governance_action(
                agent_id=proposal.proposer_id,
                tick=tick,
                action_type="PROPOSAL_PASSED",
                group_id=proposal.group_id,
                details={"title": proposal.title},
            )

        return proposal.status

    def _execute_proposal(self, proposal, tick):
        if proposal.proposal_type == "add_rule":
            rule_type_str = proposal.parameters.get("rule_type", "CUSTOM")
            try:
                rule_type = RuleType[rule_type_str.upper()]
            except Exception:
                rule_type = RuleType.CUSTOM

            rule = Rule(
                rule_id=f"rule_{uuid.uuid4().hex[:8]}",
                rule_type=rule_type,
                parameters=proposal.parameters.get("rule_parameters", {}),
                created_tick=tick,
                created_by=proposal.proposer_id,
                group_id=proposal.group_id,
            )

            self._rules[rule.rule_id] = rule

            if proposal.group_id not in self._rules_by_group:
                self._rules_by_group[proposal.group_id] = []
            self._rules_by_group[proposal.group_id].append(rule.rule_id)

        elif proposal.proposal_type == "remove_rule":
            rule_id = proposal.parameters.get("rule_id")
            if rule_id and rule_id in self._rules:
                self._rules[rule_id].is_active = False

        elif proposal.proposal_type == "change_settings":
            group = self.group_manager.get_group(proposal.group_id)
            if group:
                for key, value in proposal.parameters.items():
                    if hasattr(group, key):
                        setattr(group, key, value)

        for callback in self._callbacks:
            try:
                callback("proposal_executed", proposal)
            except Exception:
                pass

    def veto_proposal(
        self,
        proposal_id,
        vetoer_id,
        tick,
    ):
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False

        if proposal.status != ProposalStatus.OPEN:
            return False

        group = self.group_manager.get_group(proposal.group_id)
        if not group:
            return False

        if vetoer_id not in group.get_leaders():
            return False

        proposal.status = ProposalStatus.VETOED

        self._logger.log_governance_action(
            agent_id=vetoer_id,
            tick=tick,
            action_type="VETO",
            group_id=proposal.group_id,
            details={"proposal": proposal_id[:8]},
        )

        return True

    def get_proposal(self, proposal_id):
        return self._proposals.get(proposal_id)

    def get_group_proposals(self, group_id, status=None):
        proposals = [p for p in self._proposals.values() if p.group_id == group_id]
        if status:
            proposals = [p for p in proposals if p.status == status]
        return proposals

    def get_group_rules(self, group_id, active_only=True):
        rule_ids = self._rules_by_group.get(group_id, [])
        rules = [self._rules[rid] for rid in rule_ids if rid in self._rules]
        if active_only:
            rules = [r for r in rules if r.is_active]
        return rules

    def apply_rules_to_action(self, group_id, action_context):
        effects = {"rules_applied": [], "total_effects": []}

        for rule in self.get_group_rules(group_id):
            result = rule.apply(action_context)
            if result["applied"]:
                effects["rules_applied"].append(rule.rule_id)
                effects["total_effects"].extend(result["effects"])

        return effects

    def check_expired_proposals(self, current_tick):
        expired = []
        for proposal in self._proposals.values():
            if proposal.status == ProposalStatus.OPEN and proposal.is_expired(current_tick):
                self.tally_proposal(proposal.proposal_id, current_tick)
                expired.append(proposal.proposal_id)
        return expired

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_stats(self):
        status_counts = {}
        for status in ProposalStatus:
            status_counts[status.name] = sum(
                1 for p in self._proposals.values() if p.status == status
            )

        return {
            "total_proposals": len(self._proposals),
            "total_rules": len(self._rules),
            "active_rules": len([r for r in self._rules.values() if r.is_active]),
            "status_counts": status_counts,
            "total_votes_cast": sum(len(p.votes) for p in self._proposals.values()),
        }
