from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod


class ActionType(Enum):
    MOVE = auto()
    HARVEST = auto()
    CRAFT = auto()
    MESSAGE = auto()
    TRADE_PROPOSAL = auto()
    ACCEPT_TRADE = auto()
    GROUP_ACTION = auto()
    IDLE = auto()


@dataclass
class BaseAction(ABC):
    agent_id: str
    action_type: ActionType
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    @abstractmethod
    def validate(self):
        pass


@dataclass
class MoveAction(BaseAction):
    action_type: ActionType = field(default=ActionType.MOVE, init=False)
    destination: str = ""

    def validate(self):
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.destination:
            errors.append("destination is required for MOVE action")
        return errors


@dataclass
class HarvestAction(BaseAction):
    action_type: ActionType = field(default=ActionType.HARVEST, init=False)
    resource_type: str = ""
    amount: int = 1

    def validate(self):
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.resource_type:
            errors.append("resource_type is required for HARVEST action")
        if self.amount <= 0:
            errors.append("amount must be positive for HARVEST action")
        return errors


@dataclass
class CraftAction(BaseAction):
    action_type: ActionType = field(default=ActionType.CRAFT, init=False)
    recipe_id: str = ""
    quantity: int = 1

    def validate(self):
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.recipe_id:
            errors.append("recipe_id is required for CRAFT action")
        if self.quantity <= 0:
            errors.append("quantity must be positive for CRAFT action")
        return errors


@dataclass
class MessageAction(BaseAction):
    action_type: ActionType = field(default=ActionType.MESSAGE, init=False)
    recipient_id: str = None
    channel: str = "direct"
    content: str = ""
    location_id: str = None
    group_id: str = None

    def validate(self):
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.content:
            errors.append("content is required for MESSAGE action")
        valid_channels = ("direct", "location", "global", "broadcast", "group", "trade", "governance")
        if self.channel not in valid_channels:
            errors.append(f"invalid channel '{self.channel}' for MESSAGE action")
        if self.channel == "direct" and not self.recipient_id:
            errors.append("recipient_id is required for direct MESSAGE")
        return errors


@dataclass
class TradeItem:
    item_type: str
    quantity: int


@dataclass
class TradeProposalAction(BaseAction):
    action_type: ActionType = field(default=ActionType.TRADE_PROPOSAL, init=False)
    target_agent_id: str = ""
    offered_items: list = field(default_factory=list)
    requested_items: list = field(default_factory=list)
    proposal_id: str = ""

    def validate(self):
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.target_agent_id:
            errors.append("target_agent_id is required for TRADE_PROPOSAL")
        if self.agent_id == self.target_agent_id:
            errors.append("cannot trade with self")
        if not self.offered_items and not self.requested_items:
            errors.append("trade must include offered or requested items")
        for item in self.offered_items:
            if item.quantity <= 0:
                errors.append(f"offered item quantity must be positive: {item.item_type}")
        for item in self.requested_items:
            if item.quantity <= 0:
                errors.append(f"requested item quantity must be positive: {item.item_type}")
        return errors


@dataclass
class AcceptTradeAction(BaseAction):
    action_type: ActionType = field(default=ActionType.ACCEPT_TRADE, init=False)
    proposal_id: str = ""
    accept: bool = True

    def validate(self):
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.proposal_id:
            errors.append("proposal_id is required for ACCEPT_TRADE")
        return errors


class GroupActionType(Enum):
    FORM_GROUP = auto()
    JOIN_GROUP = auto()
    LEAVE_GROUP = auto()
    VOTE = auto()
    PROPOSE_RULE = auto()


@dataclass
class GroupAction(BaseAction):
    action_type: ActionType = field(default=ActionType.GROUP_ACTION, init=False)
    group_action_type: GroupActionType = GroupActionType.FORM_GROUP
    group_id: str = None
    payload: dict = field(default_factory=dict)

    def validate(self):
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        if self.group_action_type != GroupActionType.FORM_GROUP and not self.group_id:
            errors.append("group_id required for group operations (except FORM_GROUP)")
        return errors


@dataclass
class IdleAction(BaseAction):
    action_type: ActionType = field(default=ActionType.IDLE, init=False)
    reason: str = ""

    def validate(self):
        errors = []
        if not self.agent_id:
            errors.append("agent_id is required")
        return errors


class ActionValidator:
    @staticmethod
    def validate_action(action):
        return action.validate()

    @staticmethod
    def is_valid(action):
        return len(action.validate()) == 0


class ActionFactory:
    _action_classes = {
        ActionType.MOVE: MoveAction,
        ActionType.HARVEST: HarvestAction,
        ActionType.CRAFT: CraftAction,
        ActionType.MESSAGE: MessageAction,
        ActionType.TRADE_PROPOSAL: TradeProposalAction,
        ActionType.ACCEPT_TRADE: AcceptTradeAction,
        ActionType.GROUP_ACTION: GroupAction,
        ActionType.IDLE: IdleAction,
    }

    @classmethod
    def from_dict(cls, data):
        action_type_str = data.get("action_type")
        if not action_type_str:
            raise ValueError("action_type is required")

        try:
            if isinstance(action_type_str, ActionType):
                action_type = action_type_str
            else:
                action_type = ActionType[action_type_str.upper()]
        except KeyError:
            raise ValueError(f"Invalid action_type: {action_type_str}")

        action_class = cls._action_classes.get(action_type)
        if not action_class:
            raise ValueError(f"No handler for action_type: {action_type}")

        kwargs = {
            "agent_id": data.get("agent_id", ""),
            "timestamp": data.get("timestamp", 0.0),
            "metadata": data.get("metadata", {}),
        }

        if action_type == ActionType.MOVE:
            kwargs["destination"] = data.get("destination", "")

        elif action_type == ActionType.HARVEST:
            kwargs["resource_type"] = data.get("resource_type", "")
            kwargs["amount"] = data.get("amount", 1)

        elif action_type == ActionType.CRAFT:
            kwargs["recipe_id"] = data.get("recipe_id", "")
            kwargs["quantity"] = data.get("quantity", 1)

        elif action_type == ActionType.MESSAGE:
            kwargs["recipient_id"] = data.get("recipient_id")
            channel = data.get("channel", "direct")
            if channel == "broadcast":
                channel = "location"
            kwargs["channel"] = channel
            kwargs["content"] = data.get("content", "")
            kwargs["location_id"] = data.get("location_id")
            kwargs["group_id"] = data.get("group_id")

        elif action_type == ActionType.TRADE_PROPOSAL:
            kwargs["target_agent_id"] = data.get("target_agent_id", "")
            kwargs["proposal_id"] = data.get("proposal_id", "")
            offered = data.get("offered_items", [])
            requested = data.get("requested_items", [])
            kwargs["offered_items"] = [
                TradeItem(item_type=i.get("item_type", ""), quantity=i.get("quantity", 0))
                for i in offered
            ]
            kwargs["requested_items"] = [
                TradeItem(item_type=i.get("item_type", ""), quantity=i.get("quantity", 0))
                for i in requested
            ]

        elif action_type == ActionType.ACCEPT_TRADE:
            kwargs["proposal_id"] = data.get("proposal_id", "")
            kwargs["accept"] = data.get("accept", True)

        elif action_type == ActionType.GROUP_ACTION:
            group_action_str = data.get("group_action_type", "FORM_GROUP")
            try:
                kwargs["group_action_type"] = GroupActionType[group_action_str.upper()]
            except KeyError:
                kwargs["group_action_type"] = GroupActionType.FORM_GROUP
            kwargs["group_id"] = data.get("group_id")
            kwargs["payload"] = data.get("payload", {})

        elif action_type == ActionType.IDLE:
            kwargs["reason"] = data.get("reason", "")

        return action_class(**kwargs)
