from dataclasses import dataclass, field
from enum import Enum, auto
import time
import uuid


class TradeStatus(Enum):
    PENDING = auto()
    ACCEPTED = auto()
    REJECTED = auto()
    COUNTER_OFFERED = auto()
    EXPIRED = auto()
    CANCELLED = auto()
    EXECUTED = auto()


@dataclass
class TradeItem:
    item_type: str
    quantity: int

    def to_dict(self):
        return {"item_type": self.item_type, "quantity": self.quantity}

    @classmethod
    def from_dict(cls, data):
        return cls(item_type=data["item_type"], quantity=data["quantity"])


@dataclass
class TradeCondition:
    condition_type: str
    parameters: dict = field(default_factory=dict)

    def to_dict(self):
        return {"condition_type": self.condition_type, "parameters": self.parameters}


@dataclass
class TradeProposal:
    proposal_id: str
    proposer_id: str
    target_id: str
    offered_items: list
    requested_items: list
    timestamp: float
    status: TradeStatus = TradeStatus.PENDING
    conditions: list = field(default_factory=list)
    expiry_ticks: int = 10
    created_tick: int = 0
    counter_proposal_id: str = None
    reputation_stake: float = 0.0
    message: str = ""

    def to_dict(self):
        return {
            "proposal_id": self.proposal_id,
            "proposer_id": self.proposer_id,
            "target_id": self.target_id,
            "offered_items": [i.to_dict() for i in self.offered_items],
            "requested_items": [i.to_dict() for i in self.requested_items],
            "timestamp": self.timestamp,
            "status": self.status.name,
            "conditions": [c.to_dict() for c in self.conditions],
            "expiry_ticks": self.expiry_ticks,
            "created_tick": self.created_tick,
            "counter_proposal_id": self.counter_proposal_id,
            "reputation_stake": self.reputation_stake,
            "message": self.message,
        }

    def is_expired(self, current_tick):
        return current_tick > self.created_tick + self.expiry_ticks

    def get_offered_value(self, price_matrix=None):
        if price_matrix is None:
            return sum(item.quantity for item in self.offered_items)
        return sum(
            item.quantity * price_matrix.get(item.item_type, 1.0)
            for item in self.offered_items
        )

    def get_requested_value(self, price_matrix=None):
        if price_matrix is None:
            return sum(item.quantity for item in self.requested_items)
        return sum(
            item.quantity * price_matrix.get(item.item_type, 1.0)
            for item in self.requested_items
        )


class TradeManager:
    def __init__(self, agent_manager, max_pending_per_agent=10):
        self.agent_manager = agent_manager
        self.max_pending_per_agent = max_pending_per_agent
        self._proposals = {}
        self._proposals_by_agent = {}
        self._trade_history = []
        self._callbacks = []

        from ..logging.live_logger import get_live_logger
        self._logger = get_live_logger()

    def create_proposal(
        self,
        proposer_id,
        target_id,
        offered_items,
        requested_items,
        tick,
        conditions=None,
        expiry_ticks=10,
        reputation_stake=0.0,
        message="",
    ):
        if proposer_id == target_id:
            return None, "Cannot trade with self"

        proposer = self.agent_manager.get_agent(proposer_id)
        if not proposer:
            return None, f"Proposer not found: {proposer_id}"

        target = self.agent_manager.get_agent(target_id)
        if not target:
            return None, f"Target not found: {target_id}"

        pending_count = len(self.get_pending_proposals_by_agent(proposer_id))
        if pending_count >= self.max_pending_per_agent:
            return None, f"Too many pending proposals: {pending_count}"

        for item_data in offered_items:
            item_type = item_data.get("item_type", "")
            quantity = item_data.get("quantity", 0)
            if proposer.inventory.get(item_type, 0) < quantity:
                return None, f"Insufficient {item_type}: have {proposer.inventory.get(item_type, 0)}, need {quantity}"

        proposal_id = f"trade_{uuid.uuid4().hex[:12]}"

        proposal = TradeProposal(
            proposal_id=proposal_id,
            proposer_id=proposer_id,
            target_id=target_id,
            offered_items=[TradeItem(**i) for i in offered_items],
            requested_items=[TradeItem(**i) for i in requested_items],
            timestamp=time.time(),
            status=TradeStatus.PENDING,
            conditions=[TradeCondition(**c) for c in (conditions or [])],
            expiry_ticks=expiry_ticks,
            created_tick=tick,
            reputation_stake=reputation_stake,
            message=message,
        )

        self._proposals[proposal_id] = proposal

        if proposer_id not in self._proposals_by_agent:
            self._proposals_by_agent[proposer_id] = []
        self._proposals_by_agent[proposer_id].append(proposal_id)

        if target_id not in self._proposals_by_agent:
            self._proposals_by_agent[target_id] = []
        self._proposals_by_agent[target_id].append(proposal_id)

        self._logger.log_trade_proposal(
            proposer_id=proposer_id,
            target_id=target_id,
            tick=tick,
            offered=[(i.item_type, i.quantity) for i in proposal.offered_items],
            requested=[(i.item_type, i.quantity) for i in proposal.requested_items],
            proposal_id=proposal_id,
        )

        return proposal, None

    def accept_proposal(self, proposal_id, accepter_id, tick):
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False, f"Proposal not found: {proposal_id}"

        if proposal.status != TradeStatus.PENDING:
            return False, f"Proposal not pending: {proposal.status.name}"

        if accepter_id != proposal.target_id:
            return False, "Only target can accept proposal"

        if proposal.is_expired(tick):
            proposal.status = TradeStatus.EXPIRED
            return False, "Proposal expired"

        proposer = self.agent_manager.get_agent(proposal.proposer_id)
        target = self.agent_manager.get_agent(proposal.target_id)

        if not proposer or not target:
            return False, "One or both parties no longer exist"

        for item in proposal.offered_items:
            if proposer.inventory.get(item.item_type, 0) < item.quantity:
                proposal.status = TradeStatus.CANCELLED
                return False, f"Proposer no longer has sufficient {item.item_type}"

        for item in proposal.requested_items:
            if target.inventory.get(item.item_type, 0) < item.quantity:
                return False, f"Target has insufficient {item.item_type}"

        for item in proposal.offered_items:
            self.agent_manager.update_agent_inventory(
                proposal.proposer_id, item.item_type, -item.quantity
            )
            self.agent_manager.update_agent_inventory(
                proposal.target_id, item.item_type, item.quantity
            )

        for item in proposal.requested_items:
            self.agent_manager.update_agent_inventory(
                proposal.target_id, item.item_type, -item.quantity
            )
            self.agent_manager.update_agent_inventory(
                proposal.proposer_id, item.item_type, item.quantity
            )

        proposal.status = TradeStatus.EXECUTED

        self._trade_history.append({
            "proposal_id": proposal_id,
            "proposer_id": proposal.proposer_id,
            "target_id": proposal.target_id,
            "offered_items": [i.to_dict() for i in proposal.offered_items],
            "requested_items": [i.to_dict() for i in proposal.requested_items],
            "tick": tick,
            "timestamp": time.time(),
        })

        self._logger.log_trade_complete(
            proposer_id=proposal.proposer_id,
            target_id=proposal.target_id,
            tick=tick,
            accepted=True,
            proposal_id=proposal_id,
        )

        for callback in self._callbacks:
            try:
                callback("trade_executed", proposal)
            except Exception:
                pass

        return True, "Trade executed successfully"

    def reject_proposal(self, proposal_id, rejecter_id, tick, reason=""):
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False, f"Proposal not found: {proposal_id}"

        if proposal.status != TradeStatus.PENDING:
            return False, f"Proposal not pending: {proposal.status.name}"

        if rejecter_id != proposal.target_id:
            return False, "Only target can reject proposal"

        proposal.status = TradeStatus.REJECTED

        self._logger.log_trade_complete(
            proposer_id=proposal.proposer_id,
            target_id=proposal.target_id,
            tick=tick,
            accepted=False,
            proposal_id=proposal_id,
        )

        return True, "Trade rejected"

    def counter_offer(
        self,
        original_proposal_id,
        counter_offerer_id,
        new_offered_items,
        new_requested_items,
        tick,
    ):
        original = self._proposals.get(original_proposal_id)
        if not original:
            return None, f"Original proposal not found: {original_proposal_id}"

        if counter_offerer_id != original.target_id:
            return None, "Only target can counter-offer"

        original.status = TradeStatus.COUNTER_OFFERED

        counter_proposal, error = self.create_proposal(
            proposer_id=counter_offerer_id,
            target_id=original.proposer_id,
            offered_items=new_offered_items,
            requested_items=new_requested_items,
            tick=tick,
        )

        if counter_proposal:
            counter_proposal.counter_proposal_id = original_proposal_id

        return counter_proposal, error

    def cancel_proposal(self, proposal_id, canceller_id):
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False, f"Proposal not found: {proposal_id}"

        if canceller_id != proposal.proposer_id:
            return False, "Only proposer can cancel"

        if proposal.status != TradeStatus.PENDING:
            return False, f"Cannot cancel: {proposal.status.name}"

        proposal.status = TradeStatus.CANCELLED
        return True, "Proposal cancelled"

    def get_proposal(self, proposal_id):
        return self._proposals.get(proposal_id)

    def get_pending_proposals_for_target(self, agent_id):
        return [
            self._proposals[pid]
            for pid in self._proposals_by_agent.get(agent_id, [])
            if pid in self._proposals
            and self._proposals[pid].target_id == agent_id
            and self._proposals[pid].status == TradeStatus.PENDING
        ]

    def get_pending_proposals_by_agent(self, agent_id):
        return [
            self._proposals[pid]
            for pid in self._proposals_by_agent.get(agent_id, [])
            if pid in self._proposals
            and self._proposals[pid].proposer_id == agent_id
            and self._proposals[pid].status == TradeStatus.PENDING
        ]

    def get_all_pending_for_agent(self, agent_id):
        return [
            self._proposals[pid]
            for pid in self._proposals_by_agent.get(agent_id, [])
            if pid in self._proposals
            and self._proposals[pid].status == TradeStatus.PENDING
        ]

    def expire_old_proposals(self, current_tick):
        expired_count = 0
        for proposal in self._proposals.values():
            if proposal.status == TradeStatus.PENDING and proposal.is_expired(current_tick):
                proposal.status = TradeStatus.EXPIRED
                expired_count += 1
        return expired_count

    def get_trade_history(self, agent_id=None, since_tick=None):
        history = self._trade_history

        if agent_id:
            history = [
                h for h in history
                if h["proposer_id"] == agent_id or h["target_id"] == agent_id
            ]

        if since_tick is not None:
            history = [h for h in history if h["tick"] >= since_tick]

        return history

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_stats(self):
        status_counts = {}
        for status in TradeStatus:
            status_counts[status.name] = sum(
                1 for p in self._proposals.values() if p.status == status
            )

        return {
            "total_proposals": len(self._proposals),
            "executed_trades": len(self._trade_history),
            "status_counts": status_counts,
        }
