from enum import Enum, auto

from .action_schema import (
    BaseAction as Action,
    ActionType,
    MoveAction,
    HarvestAction,
    CraftAction,
    MessageAction,
    TradeProposalAction,
    AcceptTradeAction,
    GroupAction,
    IdleAction,
    ActionValidator,
)


class ActionResult(Enum):
    SUCCESS = auto()
    FAILURE = auto()
    PARTIAL = auto()
    INVALID = auto()


class ActionOutcome:
    def __init__(self, result, action, message="", state_changes=None, side_effects=None):
        self.result = result
        self.action = action
        self.message = message
        self.state_changes = state_changes if state_changes is not None else {}
        self.side_effects = side_effects if side_effects is not None else []

    @property
    def succeeded(self):
        return self.result in (ActionResult.SUCCESS, ActionResult.PARTIAL)


class ActionInterpreter:
    def __init__(self, world_state, agent_manager, location_graph, crafting_rules=None):
        self.world_state = world_state
        self.agent_manager = agent_manager
        self.location_graph = location_graph
        self.crafting_rules = crafting_rules or {}
        self._pending_trades = {}
        self._handlers = {
            ActionType.MOVE: self._handle_move,
            ActionType.HARVEST: self._handle_harvest,
            ActionType.CRAFT: self._handle_craft,
            ActionType.MESSAGE: self._handle_message,
            ActionType.TRADE_PROPOSAL: self._handle_trade_proposal,
            ActionType.ACCEPT_TRADE: self._handle_accept_trade,
            ActionType.GROUP_ACTION: self._handle_group_action,
            ActionType.IDLE: self._handle_idle,
        }

    def execute(self, action):
        errors = ActionValidator.validate_action(action)
        if errors:
            return ActionOutcome(
                result=ActionResult.INVALID,
                action=action,
                message=f"Validation errors: {'; '.join(errors)}",
            )

        handler = self._handlers.get(action.action_type)
        if not handler:
            return ActionOutcome(
                result=ActionResult.INVALID,
                action=action,
                message=f"No handler for action type: {action.action_type}",
            )

        try:
            return handler(action)
        except Exception as e:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Handler error: {str(e)}",
            )

    def execute_batch(self, actions):
        return [self.execute(action) for action in actions]

    def _handle_move(self, action):
        agent = self.agent_manager.get_agent(action.agent_id)
        if not agent:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Agent not found: {action.agent_id}",
            )

        current_location = agent.location
        destination = action.destination

        dest_node = self.location_graph.get_node(destination)
        if not dest_node:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Destination not found: {destination}",
            )

        if current_location and current_location != destination:
            neighbors = self.location_graph.get_neighbors(current_location)
            if destination not in neighbors:
                return ActionOutcome(
                    result=ActionResult.FAILURE,
                    action=action,
                    message=f"No path from {current_location} to {destination}",
                )

            travel_cost = self.location_graph.travel_cost(current_location, destination)
            if travel_cost == float('inf'):
                return ActionOutcome(
                    result=ActionResult.FAILURE,
                    action=action,
                    message=f"Path blocked from {current_location} to {destination}",
                )

        old_location = agent.location
        self.agent_manager.update_agent_location(action.agent_id, destination)

        return ActionOutcome(
            result=ActionResult.SUCCESS,
            action=action,
            message=f"Moved from {old_location} to {destination}",
            state_changes={
                "agent_id": action.agent_id,
                "old_location": old_location,
                "new_location": destination,
            },
        )

    def _handle_harvest(self, action):
        agent = self.agent_manager.get_agent(action.agent_id)
        if not agent:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Agent not found: {action.agent_id}",
            )

        location = self.location_graph.get_node(agent.location)
        if not location:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Agent not at valid location",
            )

        resource_richness = location.resource_richness.get(action.resource_type, 0)
        if resource_richness <= 0:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Resource '{action.resource_type}' not available at {location.name}",
            )

        if agent.inventory_space < action.amount:
            actual_amount = agent.inventory_space
            if actual_amount <= 0:
                return ActionOutcome(
                    result=ActionResult.FAILURE,
                    action=action,
                    message="Inventory full",
                )
        else:
            actual_amount = min(action.amount, resource_richness)

        success = self.agent_manager.update_agent_inventory(
            action.agent_id, action.resource_type, actual_amount
        )
        
        if not success:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message="Failed to update inventory",
            )

        result_type = ActionResult.SUCCESS if actual_amount == action.amount else ActionResult.PARTIAL

        return ActionOutcome(
            result=result_type,
            action=action,
            message=f"Harvested {actual_amount} {action.resource_type}",
            state_changes={
                "agent_id": action.agent_id,
                "resource_type": action.resource_type,
                "amount_harvested": actual_amount,
                "location": agent.location,
            },
        )

    def _handle_craft(self, action):
        agent = self.agent_manager.get_agent(action.agent_id)
        if not agent:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Agent not found: {action.agent_id}",
            )

        recipe = self.crafting_rules.get(action.recipe_id)
        if not recipe:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Unknown recipe: {action.recipe_id}",
            )

        inputs = recipe.get("inputs", {})
        outputs = recipe.get("outputs", {})

        for item, count in inputs.items():
            required = count * action.quantity
            if agent.inventory.get(item, 0) < required:
                return ActionOutcome(
                    result=ActionResult.FAILURE,
                    action=action,
                    message=f"Insufficient {item}: need {required}, have {agent.inventory.get(item, 0)}",
                )

        total_output = sum(c * action.quantity for c in outputs.values())
        total_input = sum(c * action.quantity for c in inputs.values())
        net_change = total_output - total_input

        if net_change > 0 and agent.inventory_space < net_change:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message="Insufficient inventory space for crafted items",
            )

        for item, count in inputs.items():
            self.agent_manager.update_agent_inventory(
                action.agent_id, item, -(count * action.quantity)
            )

        for item, count in outputs.items():
            self.agent_manager.update_agent_inventory(
                action.agent_id, item, count * action.quantity
            )

        skill_gain = recipe.get("skill_gain", {})
        for skill, gain in skill_gain.items():
            self.agent_manager.update_agent_skill(action.agent_id, skill, gain * action.quantity)

        return ActionOutcome(
            result=ActionResult.SUCCESS,
            action=action,
            message=f"Crafted {action.quantity}x {action.recipe_id}",
            state_changes={
                "agent_id": action.agent_id,
                "recipe_id": action.recipe_id,
                "quantity": action.quantity,
                "inputs_consumed": {k: v * action.quantity for k, v in inputs.items()},
                "outputs_produced": {k: v * action.quantity for k, v in outputs.items()},
            },
        )

    def _handle_message(self, action):
        agent = self.agent_manager.get_agent(action.agent_id)
        if not agent:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Agent not found: {action.agent_id}",
            )

        if action.channel == "direct" and action.recipient_id:
            recipient = self.agent_manager.get_agent(action.recipient_id)
            if not recipient:
                return ActionOutcome(
                    result=ActionResult.FAILURE,
                    action=action,
                    message=f"Recipient not found: {action.recipient_id}",
                )

        return ActionOutcome(
            result=ActionResult.SUCCESS,
            action=action,
            message=f"Message queued ({action.channel})",
            side_effects=[{
                "type": "message",
                "sender_id": action.agent_id,
                "recipient_id": action.recipient_id,
                "channel": action.channel,
                "content": action.content,
                "sender_location": agent.location,
            }],
        )

    def _handle_trade_proposal(self, action):
        agent = self.agent_manager.get_agent(action.agent_id)
        if not agent:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Agent not found: {action.agent_id}",
            )

        target = self.agent_manager.get_agent(action.target_agent_id)
        if not target:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Target agent not found: {action.target_agent_id}",
            )

        for item in action.offered_items:
            if agent.inventory.get(item.item_type, 0) < item.quantity:
                return ActionOutcome(
                    result=ActionResult.FAILURE,
                    action=action,
                    message=f"Insufficient {item.item_type} to offer",
                )

        self._pending_trades[action.proposal_id] = {
            "proposer_id": action.agent_id,
            "target_id": action.target_agent_id,
            "offered_items": [(i.item_type, i.quantity) for i in action.offered_items],
            "requested_items": [(i.item_type, i.quantity) for i in action.requested_items],
            "timestamp": action.timestamp,
        }

        return ActionOutcome(
            result=ActionResult.SUCCESS,
            action=action,
            message=f"Trade proposal created: {action.proposal_id}",
            side_effects=[{
                "type": "trade_proposal",
                "proposal_id": action.proposal_id,
                "proposer_id": action.agent_id,
                "target_id": action.target_agent_id,
            }],
        )

    def _handle_accept_trade(self, action):
        proposal = self._pending_trades.get(action.proposal_id)
        if not proposal:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Trade proposal not found: {action.proposal_id}",
            )

        if action.agent_id != proposal["target_id"]:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message="Only the target can respond to this trade",
            )

        if not action.accept:
            del self._pending_trades[action.proposal_id]
            return ActionOutcome(
                result=ActionResult.SUCCESS,
                action=action,
                message="Trade rejected",
            )

        proposer = self.agent_manager.get_agent(proposal["proposer_id"])
        target = self.agent_manager.get_agent(proposal["target_id"])

        if not proposer or not target:
            del self._pending_trades[action.proposal_id]
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message="One or both trade parties no longer exist",
            )

        for item_type, quantity in proposal["offered_items"]:
            if proposer.inventory.get(item_type, 0) < quantity:
                del self._pending_trades[action.proposal_id]
                return ActionOutcome(
                    result=ActionResult.FAILURE,
                    action=action,
                    message=f"Proposer no longer has sufficient {item_type}",
                )

        for item_type, quantity in proposal["requested_items"]:
            if target.inventory.get(item_type, 0) < quantity:
                del self._pending_trades[action.proposal_id]
                return ActionOutcome(
                    result=ActionResult.FAILURE,
                    action=action,
                    message=f"Target no longer has sufficient {item_type}",
                )

        for item_type, quantity in proposal["offered_items"]:
            self.agent_manager.update_agent_inventory(proposal["proposer_id"], item_type, -quantity)
            self.agent_manager.update_agent_inventory(proposal["target_id"], item_type, quantity)

        for item_type, quantity in proposal["requested_items"]:
            self.agent_manager.update_agent_inventory(proposal["target_id"], item_type, -quantity)
            self.agent_manager.update_agent_inventory(proposal["proposer_id"], item_type, quantity)

        del self._pending_trades[action.proposal_id]

        return ActionOutcome(
            result=ActionResult.SUCCESS,
            action=action,
            message="Trade completed",
            state_changes={
                "proposal_id": action.proposal_id,
                "proposer_id": proposal["proposer_id"],
                "target_id": proposal["target_id"],
                "items_exchanged": {
                    "proposer_gave": proposal["offered_items"],
                    "target_gave": proposal["requested_items"],
                },
            },
        )

    def _handle_group_action(self, action):
        agent = self.agent_manager.get_agent(action.agent_id)
        if not agent:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Agent not found: {action.agent_id}",
            )

        return ActionOutcome(
            result=ActionResult.SUCCESS,
            action=action,
            message=f"Group action queued: {action.group_action_type.name}",
            side_effects=[{
                "type": "group_action",
                "agent_id": action.agent_id,
                "group_action_type": action.group_action_type.name,
                "group_id": action.group_id,
                "payload": action.payload,
            }],
        )

    def _handle_idle(self, action):
        agent = self.agent_manager.get_agent(action.agent_id)
        if not agent:
            return ActionOutcome(
                result=ActionResult.FAILURE,
                action=action,
                message=f"Agent not found: {action.agent_id}",
            )

        return ActionOutcome(
            result=ActionResult.SUCCESS,
            action=action,
            message=f"Agent idle: {action.reason}" if action.reason else "Agent idle",
        )

    def get_pending_trades_for_agent(self, agent_id):
        return [
            {"proposal_id": pid, **data}
            for pid, data in self._pending_trades.items()
            if data["proposer_id"] == agent_id or data["target_id"] == agent_id
        ]

    def cancel_pending_trade(self, proposal_id):
        if proposal_id in self._pending_trades:
            del self._pending_trades[proposal_id]
            return True
        return False

    def clear_expired_trades(self, current_time, max_age=100.0):
        expired = [
            pid for pid, data in self._pending_trades.items()
            if current_time - data.get("timestamp", 0) > max_age
        ]
        for pid in expired:
            del self._pending_trades[pid]
        return len(expired)
