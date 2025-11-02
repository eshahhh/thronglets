from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum


class DisputeType(Enum):
    CONTRACT_BREACH = "contract_breach"
    TRADE_DISPUTE = "trade_dispute"
    PAYMENT_DISPUTE = "payment_dispute"
    QUALITY_DISPUTE = "quality_dispute"
    DELIVERY_DISPUTE = "delivery_dispute"


class DisputeOutcome(Enum):
    PENDING = "pending"
    RESOLVED_FAVOR_INITIATOR = "resolved_favor_initiator"
    RESOLVED_FAVOR_DEFENDANT = "resolved_favor_defendant"
    SETTLED = "settled"
    ABANDONED = "abandoned"


@dataclass
class Dispute:
    dispute_id: str
    tick: int
    initiator_id: str
    defendant_id: str
    dispute_type: DisputeType
    amount_contested: float = 0.0
    description: str = ""
    outcome: DisputeOutcome = DisputeOutcome.PENDING
    resolved_tick: int = None

    def to_dict(self):
        return {
            "dispute_id": self.dispute_id,
            "tick": self.tick,
            "initiator_id": self.initiator_id,
            "defendant_id": self.defendant_id,
            "dispute_type": self.dispute_type.value,
            "amount_contested": self.amount_contested,
            "description": self.description,
            "outcome": self.outcome.value,
            "resolved_tick": self.resolved_tick,
        }


@dataclass
class ReputationScore:
    agent_id: str
    trust_score: float = 0.5
    contract_adherence_rate: float = 1.0
    trade_reliability: float = 1.0
    dispute_ratio: float = 0.0
    total_trades: int = 0
    contracts_fulfilled: int = 0
    contracts_breached: int = 0
    disputes_initiated: int = 0
    disputes_against: int = 0
    disputes_lost: int = 0

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "trust_score": self.trust_score,
            "contract_adherence_rate": self.contract_adherence_rate,
            "trade_reliability": self.trade_reliability,
            "dispute_ratio": self.dispute_ratio,
            "total_trades": self.total_trades,
            "contracts_fulfilled": self.contracts_fulfilled,
            "contracts_breached": self.contracts_breached,
            "disputes_initiated": self.disputes_initiated,
            "disputes_against": self.disputes_against,
            "disputes_lost": self.disputes_lost,
        }


class ReputationMetrics:
    def __init__(self):
        self._agent_scores = {}
        self._disputes = {}
        self._trade_history = defaultdict(list)
        self._contract_history = defaultdict(list)
        self._trust_updates = []
        self._max_history = 1000
        self._dispute_counter = 0

    def _get_or_create_score(self, agent_id):
        if agent_id not in self._agent_scores:
            self._agent_scores[agent_id] = ReputationScore(agent_id=agent_id)
        return self._agent_scores[agent_id]

    def record_trade(
        self,
        tick,
        agent_id,
        partner_id,
        successful,
        value=0.0,
    ):
        score = self._get_or_create_score(agent_id)
        score.total_trades += 1

        self._trade_history[agent_id].append({
            "tick": tick,
            "partner_id": partner_id,
            "successful": successful,
            "value": value,
        })

        if len(self._trade_history[agent_id]) > self._max_history:
            self._trade_history[agent_id].pop(0)

        self._update_trade_reliability(agent_id)
        self._update_trust_score(agent_id, tick)

    def record_contract_outcome(
        self,
        tick,
        agent_id,
        contract_id,
        fulfilled,
    ):
        score = self._get_or_create_score(agent_id)

        if fulfilled:
            score.contracts_fulfilled += 1
        else:
            score.contracts_breached += 1

        self._contract_history[agent_id].append({
            "tick": tick,
            "contract_id": contract_id,
            "fulfilled": fulfilled,
        })

        if len(self._contract_history[agent_id]) > self._max_history:
            self._contract_history[agent_id].pop(0)

        self._update_contract_adherence(agent_id)
        self._update_trust_score(agent_id, tick)

    def create_dispute(
        self,
        tick,
        initiator_id,
        defendant_id,
        dispute_type,
        amount_contested=0.0,
        description="",
    ):
        self._dispute_counter += 1
        dispute_id = f"dispute_{self._dispute_counter}"

        dispute = Dispute(
            dispute_id=dispute_id,
            tick=tick,
            initiator_id=initiator_id,
            defendant_id=defendant_id,
            dispute_type=dispute_type,
            amount_contested=amount_contested,
            description=description,
        )

        self._disputes[dispute_id] = dispute

        initiator_score = self._get_or_create_score(initiator_id)
        initiator_score.disputes_initiated += 1

        defendant_score = self._get_or_create_score(defendant_id)
        defendant_score.disputes_against += 1

        self._update_dispute_ratio(initiator_id)
        self._update_dispute_ratio(defendant_id)

        return dispute

    def resolve_dispute(
        self,
        dispute_id,
        outcome,
        tick,
    ):
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return None

        dispute.outcome = outcome
        dispute.resolved_tick = tick

        if outcome == DisputeOutcome.RESOLVED_FAVOR_INITIATOR:
            defendant_score = self._get_or_create_score(dispute.defendant_id)
            defendant_score.disputes_lost += 1
            self._update_trust_score(dispute.defendant_id, tick, penalty=-0.1)
        elif outcome == DisputeOutcome.RESOLVED_FAVOR_DEFENDANT:
            initiator_score = self._get_or_create_score(dispute.initiator_id)
            initiator_score.disputes_lost += 1
            self._update_trust_score(dispute.initiator_id, tick, penalty=-0.05)

        return dispute

    def _update_trade_reliability(self, agent_id):
        history = self._trade_history.get(agent_id, [])
        if not history:
            return

        successful = sum(1 for t in history if t["successful"])
        score = self._get_or_create_score(agent_id)
        score.trade_reliability = successful / len(history)

    def _update_contract_adherence(self, agent_id):
        score = self._get_or_create_score(agent_id)
        total = score.contracts_fulfilled + score.contracts_breached
        if total > 0:
            score.contract_adherence_rate = score.contracts_fulfilled / total

    def _update_dispute_ratio(self, agent_id):
        score = self._get_or_create_score(agent_id)
        total_interactions = score.total_trades + score.contracts_fulfilled + score.contracts_breached
        if total_interactions > 0:
            total_disputes = score.disputes_initiated + score.disputes_against
            score.dispute_ratio = total_disputes / total_interactions

    def _update_trust_score(
        self,
        agent_id,
        tick,
        penalty=0.0,
    ):
        score = self._get_or_create_score(agent_id)

        trade_weight = 0.3
        contract_weight = 0.4
        dispute_weight = 0.3

        trust = (
            score.trade_reliability * trade_weight +
            score.contract_adherence_rate * contract_weight +
            (1.0 - min(1.0, score.dispute_ratio * 5)) * dispute_weight +
            penalty
        )

        old_trust = score.trust_score
        score.trust_score = max(0.0, min(1.0, trust))

        self._trust_updates.append({
            "tick": tick,
            "agent_id": agent_id,
            "old_trust": old_trust,
            "new_trust": score.trust_score,
            "penalty": penalty,
        })

        if len(self._trust_updates) > self._max_history:
            self._trust_updates.pop(0)

    def get_agent_reputation(self, agent_id):
        return self._agent_scores.get(agent_id)

    def get_trust_score(self, agent_id):
        score = self._agent_scores.get(agent_id)
        return score.trust_score if score else 0.5

    def get_dispute_frequency(
        self,
        since_tick=None,
    ):
        disputes = list(self._disputes.values())
        if since_tick is not None:
            disputes = [d for d in disputes if d.tick >= since_tick]

        type_counts = defaultdict(int)
        for d in disputes:
            type_counts[d.dispute_type.value] += 1

        outcome_counts = defaultdict(int)
        for d in disputes:
            outcome_counts[d.outcome.value] += 1

        return {
            "total_disputes": len(disputes),
            "by_type": dict(type_counts),
            "by_outcome": dict(outcome_counts),
        }

    def get_most_trusted_agents(self, limit=10):
        sorted_scores = sorted(
            self._agent_scores.values(),
            key=lambda s: s.trust_score,
            reverse=True,
        )
        return sorted_scores[:limit]

    def get_least_trusted_agents(self, limit=10):
        sorted_scores = sorted(
            self._agent_scores.values(),
            key=lambda s: s.trust_score,
        )
        return sorted_scores[:limit]

    def get_contract_adherence_summary(self):
        if not self._agent_scores:
            return {
                "avg_adherence": 1.0,
                "total_fulfilled": 0,
                "total_breached": 0,
            }

        total_fulfilled = sum(s.contracts_fulfilled for s in self._agent_scores.values())
        total_breached = sum(s.contracts_breached for s in self._agent_scores.values())

        adherence_rates = [s.contract_adherence_rate for s in self._agent_scores.values()]
        avg_adherence = sum(adherence_rates) / len(adherence_rates) if adherence_rates else 1.0

        return {
            "avg_adherence": avg_adherence,
            "total_fulfilled": total_fulfilled,
            "total_breached": total_breached,
        }

    def get_network_trust_metrics(self):
        if not self._agent_scores:
            return {
                "avg_trust": 0.5,
                "trust_variance": 0.0,
                "high_trust_agents": 0,
                "low_trust_agents": 0,
            }

        trusts = [s.trust_score for s in self._agent_scores.values()]
        avg_trust = sum(trusts) / len(trusts)

        variance = sum((t - avg_trust) ** 2 for t in trusts) / len(trusts)

        high_trust = sum(1 for t in trusts if t >= 0.8)
        low_trust = sum(1 for t in trusts if t <= 0.3)

        return {
            "avg_trust": avg_trust,
            "trust_variance": variance,
            "high_trust_agents": high_trust,
            "low_trust_agents": low_trust,
            "total_agents": len(trusts),
        }

    def to_dict(self):
        return {
            "agent_scores": {
                aid: score.to_dict()
                for aid, score in self._agent_scores.items()
            },
            "dispute_frequency": self.get_dispute_frequency(),
            "contract_summary": self.get_contract_adherence_summary(),
            "network_trust": self.get_network_trust_metrics(),
        }
