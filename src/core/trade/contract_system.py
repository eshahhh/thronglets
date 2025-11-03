from dataclasses import dataclass, field
from enum import Enum, auto
import time
import uuid


class ContractStatus(Enum):
    DRAFT = auto()
    ACTIVE = auto()
    FULFILLED = auto()
    BREACHED = auto()
    EXPIRED = auto()
    CANCELLED = auto()


class ObligationType(Enum):
    DELIVER_ITEM = auto()
    PAYMENT = auto()
    SERVICE = auto()
    RECURRING = auto()
    CUSTOM = auto()


@dataclass
class ContractObligation:
    obligation_id: str
    obligor_id: str
    obligation_type: ObligationType
    parameters: dict
    due_tick: int
    fulfilled: bool = False
    fulfilled_tick: int = None

    def to_dict(self):
        return {
            "obligation_id": self.obligation_id,
            "obligor_id": self.obligor_id,
            "obligation_type": self.obligation_type.name,
            "parameters": self.parameters,
            "due_tick": self.due_tick,
            "fulfilled": self.fulfilled,
            "fulfilled_tick": self.fulfilled_tick,
        }


@dataclass
class Contract:
    contract_id: str
    parties: list
    obligations: list
    created_tick: int
    expiry_tick: int
    status: ContractStatus = ContractStatus.DRAFT
    reputation_stakes: dict = field(default_factory=dict)
    terms: str = ""
    witnesses: list = field(default_factory=list)
    breach_penalty: float = 10.0

    def to_dict(self):
        return {
            "contract_id": self.contract_id,
            "parties": self.parties,
            "obligations": [o.to_dict() for o in self.obligations],
            "created_tick": self.created_tick,
            "expiry_tick": self.expiry_tick,
            "status": self.status.name,
            "reputation_stakes": self.reputation_stakes,
            "terms": self.terms,
            "witnesses": self.witnesses,
            "breach_penalty": self.breach_penalty,
        }

    def get_unfulfilled_obligations(self):
        return [o for o in self.obligations if not o.fulfilled]

    def get_overdue_obligations(self, current_tick):
        return [
            o for o in self.obligations
            if not o.fulfilled and o.due_tick < current_tick
        ]

    def is_all_fulfilled(self):
        return all(o.fulfilled for o in self.obligations)


class ContractManager:
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self._contracts = {}
        self._contracts_by_agent = {}
        self._breach_history = []
        self._callbacks = []

        from ..logging.live_logger import get_live_logger
        self._logger = get_live_logger()

    def create_contract(
        self,
        parties,
        obligations,
        created_tick,
        duration_ticks,
        reputation_stakes=None,
        terms="",
        witnesses=None,
        breach_penalty=10.0,
    ):
        for party_id in parties:
            if not self.agent_manager.get_agent(party_id):
                self._logger.error(f"Contract party not found: {party_id}")
                return None

        contract_id = f"contract_{uuid.uuid4().hex[:12]}"

        parsed_obligations = []
        for i, obl_data in enumerate(obligations):
            obl = ContractObligation(
                obligation_id=f"{contract_id}_obl_{i}",
                obligor_id=obl_data.get("obligor_id", ""),
                obligation_type=ObligationType[obl_data.get("type", "CUSTOM").upper()],
                parameters=obl_data.get("parameters", {}),
                due_tick=obl_data.get("due_tick", created_tick + duration_ticks),
            )
            parsed_obligations.append(obl)

        contract = Contract(
            contract_id=contract_id,
            parties=parties,
            obligations=parsed_obligations,
            created_tick=created_tick,
            expiry_tick=created_tick + duration_ticks,
            status=ContractStatus.DRAFT,
            reputation_stakes=reputation_stakes or {},
            terms=terms,
            witnesses=witnesses or [],
            breach_penalty=breach_penalty,
        )

        self._contracts[contract_id] = contract

        for party_id in parties:
            if party_id not in self._contracts_by_agent:
                self._contracts_by_agent[party_id] = []
            self._contracts_by_agent[party_id].append(contract_id)

        self._logger.governance(
            f"Contract created: {contract_id[:8]}",
            extra={"parties": parties, "obligations": len(obligations)},
            tick=created_tick,
        )

        return contract

    def activate_contract(self, contract_id, tick):
        contract = self._contracts.get(contract_id)
        if not contract:
            return False

        if contract.status != ContractStatus.DRAFT:
            return False

        contract.status = ContractStatus.ACTIVE

        self._logger.governance(
            f"Contract activated: {contract_id[:8]}",
            tick=tick,
        )

        return True

    def fulfill_obligation(
        self,
        contract_id,
        obligation_id,
        fulfiller_id,
        tick,
    ):
        contract = self._contracts.get(contract_id)
        if not contract:
            return False

        if contract.status != ContractStatus.ACTIVE:
            return False

        obligation = next(
            (o for o in contract.obligations if o.obligation_id == obligation_id),
            None,
        )
        if not obligation:
            return False

        if obligation.obligor_id != fulfiller_id:
            return False

        if obligation.fulfilled:
            return False

        obligation.fulfilled = True
        obligation.fulfilled_tick = tick

        self._logger.governance(
            f"Obligation fulfilled: {obligation_id[:8]}",
            agent_id=fulfiller_id,
            tick=tick,
        )

        if contract.is_all_fulfilled():
            contract.status = ContractStatus.FULFILLED
            self._logger.governance(
                f"Contract fulfilled: {contract_id[:8]}",
                tick=tick,
            )

            for callback in self._callbacks:
                try:
                    callback("contract_fulfilled", contract)
                except Exception:
                    pass

        return True

    def check_breaches(self, current_tick):
        breaches = []

        for contract in self._contracts.values():
            if contract.status != ContractStatus.ACTIVE:
                continue

            overdue = contract.get_overdue_obligations(current_tick)

            for obligation in overdue:
                breach = {
                    "contract_id": contract.contract_id,
                    "obligation_id": obligation.obligation_id,
                    "obligor_id": obligation.obligor_id,
                    "due_tick": obligation.due_tick,
                    "detected_tick": current_tick,
                    "penalty": contract.breach_penalty,
                }

                breaches.append(breach)
                self._breach_history.append(breach)

                contract.status = ContractStatus.BREACHED

                self._apply_breach_penalty(obligation.obligor_id, contract.breach_penalty)

                self._logger.warning(
                    f"Contract breach: {contract.contract_id[:8]}",
                    agent_id=obligation.obligor_id,
                    tick=current_tick,
                    extra={"penalty": contract.breach_penalty},
                )

                for callback in self._callbacks:
                    try:
                        callback("contract_breach", breach)
                    except Exception:
                        pass

        return breaches

    def _apply_breach_penalty(self, agent_id, penalty):
        agent = self.agent_manager.get_agent(agent_id)
        if agent and "reputation" in agent.needs:
            current = agent.needs.get("reputation", 50.0)
            agent.needs["reputation"] = max(0.0, current - penalty)

    def expire_contracts(self, current_tick):
        expired_count = 0

        for contract in self._contracts.values():
            if contract.status == ContractStatus.ACTIVE:
                if current_tick > contract.expiry_tick:
                    if not contract.is_all_fulfilled():
                        contract.status = ContractStatus.EXPIRED
                        expired_count += 1

        return expired_count

    def cancel_contract(self, contract_id, canceller_id, tick):
        contract = self._contracts.get(contract_id)
        if not contract:
            return False

        if canceller_id not in contract.parties:
            return False

        if contract.status not in (ContractStatus.DRAFT, ContractStatus.ACTIVE):
            return False

        contract.status = ContractStatus.CANCELLED

        self._logger.governance(
            f"Contract cancelled: {contract_id[:8]}",
            agent_id=canceller_id,
            tick=tick,
        )

        return True

    def get_contract(self, contract_id):
        return self._contracts.get(contract_id)

    def get_agent_contracts(
        self,
        agent_id,
        status=None,
    ):
        contract_ids = self._contracts_by_agent.get(agent_id, [])
        contracts = [self._contracts[cid] for cid in contract_ids if cid in self._contracts]

        if status:
            contracts = [c for c in contracts if c.status == status]

        return contracts

    def get_agent_obligations(
        self,
        agent_id,
        unfulfilled_only=True,
    ):
        result = []

        contracts = self.get_agent_contracts(agent_id, ContractStatus.ACTIVE)

        for contract in contracts:
            for obligation in contract.obligations:
                if obligation.obligor_id == agent_id:
                    if not unfulfilled_only or not obligation.fulfilled:
                        result.append((contract, obligation))

        return result

    def get_breach_history(
        self,
        agent_id=None,
    ):
        history = self._breach_history

        if agent_id:
            history = [b for b in history if b["obligor_id"] == agent_id]

        return history

    def get_agent_trust_score(self, agent_id):
        contracts = self.get_agent_contracts(agent_id)

        if not contracts:
            return 1.0

        fulfilled = sum(1 for c in contracts if c.status == ContractStatus.FULFILLED)
        breached = sum(1 for c in contracts if c.status == ContractStatus.BREACHED)
        total = fulfilled + breached

        if total == 0:
            return 1.0

        return fulfilled / total

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def get_stats(self):
        status_counts = {}
        for status in ContractStatus:
            status_counts[status.name] = sum(
                1 for c in self._contracts.values() if c.status == status
            )

        return {
            "total_contracts": len(self._contracts),
            "total_breaches": len(self._breach_history),
            "status_counts": status_counts,
        }
