import json
import re

from ..actions import (
    ActionFactory,
    ActionType,
    BaseAction,
    IdleAction,
    TradeItem,
)


class ActionOutputParser:
    VALID_ACTION_TYPES = {
        "MOVE", "HARVEST", "CRAFT", "MESSAGE",
        "TRADE_PROPOSAL", "ACCEPT_TRADE", "GROUP_ACTION", "IDLE"
    }

    def __init__(self, strict_validation=True):
        self.strict_validation = strict_validation
        self._parse_errors = []

    def parse(self, llm_output, agent_id, observation):
        self._parse_errors = []
        
        try:
            parsed = self._extract_json(llm_output)
            if parsed is None:
                return self._fallback_idle(agent_id, "Failed to parse JSON from LLM output")
            
            action_data = parsed.get("action", parsed)
            
            if "action_type" not in action_data:
                return self._fallback_idle(agent_id, "No action_type in response")
            
            action_type = action_data["action_type"].upper()
            if action_type not in self.VALID_ACTION_TYPES:
                return self._fallback_idle(agent_id, f"Invalid action_type: {action_type}")
            
            if self.strict_validation:
                validation_error = self._validate_action(action_data, observation)
                if validation_error:
                    return self._fallback_idle(agent_id, validation_error)
            
            action_data["agent_id"] = agent_id
            
            if action_type == "TRADE_PROPOSAL":
                action_data = self._normalize_trade_proposal(action_data)
            
            action = ActionFactory.from_dict(action_data)
            reasoning = parsed.get("reasoning", "")
            
            return action, reasoning
            
        except Exception as e:
            return self._fallback_idle(agent_id, f"Parse error: {str(e)}")

    def _extract_json(self, text):
        text = text.strip()
        
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        json_patterns = [
            r'\{[^{}]*\{[^{}]*\}[^{}]*\}',
            r'\{[^{}]*\}',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, dict) and ("action" in parsed or "action_type" in parsed):
                        return parsed
                except json.JSONDecodeError:
                    continue
        
        return None

    def _validate_action(self, action_data, observation):
        action_type = action_data["action_type"].upper()
        available_actions = observation.get("available_actions", [])
        action_info = next((a for a in available_actions if a["type"] == action_type), None)
        
        if action_info is None and action_type not in ("IDLE",):
            return f"Action {action_type} not available"
        
        if action_type == "MOVE":
            destination = action_data.get("destination")
            if action_info and "valid_destinations" in action_info:
                if destination not in action_info["valid_destinations"]:
                    return f"Invalid destination: {destination}"
        
        elif action_type == "HARVEST":
            resource = action_data.get("resource_type")
            if action_info and "available_resources" in action_info:
                if resource not in action_info["available_resources"]:
                    return f"Resource not available: {resource}"
            
            amount = action_data.get("amount", 1)
            inventory_space = observation.get("self", {}).get("inventory_space", 0)
            if amount > inventory_space:
                action_data["amount"] = inventory_space
        
        elif action_type == "TRADE_PROPOSAL":
            inventory = observation.get("self", {}).get("inventory", {})
            offered = action_data.get("offered_items", [])
            
            for item in offered:
                item_type = item.get("item_type", "")
                quantity = item.get("quantity", 0)
                if inventory.get(item_type, 0) < quantity:
                    return f"Insufficient {item_type} to offer"
            
            target = action_data.get("target_agent_id")
            if action_info and "nearby_agents" in action_info:
                if target not in action_info["nearby_agents"]:
                    return f"Target agent not nearby: {target}"
        
        elif action_type == "ACCEPT_TRADE":
            proposal_id = action_data.get("proposal_id")
            if action_info and "pending_proposals" in action_info:
                if proposal_id not in action_info["pending_proposals"]:
                    return f"Invalid proposal: {proposal_id}"
        
        return None

    def _normalize_trade_proposal(self, action_data):
        import uuid
        
        if not action_data.get("proposal_id"):
            action_data["proposal_id"] = f"trade_{uuid.uuid4().hex[:8]}"
        
        offered = action_data.get("offered_items", [])
        normalized_offered = []
        for item in offered:
            if isinstance(item, dict):
                normalized_offered.append({
                    "item_type": item.get("item_type", ""),
                    "quantity": item.get("quantity", 1),
                })
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                normalized_offered.append({
                    "item_type": str(item[0]),
                    "quantity": int(item[1]),
                })
        action_data["offered_items"] = normalized_offered
        
        requested = action_data.get("requested_items", [])
        normalized_requested = []
        for item in requested:
            if isinstance(item, dict):
                normalized_requested.append({
                    "item_type": item.get("item_type", ""),
                    "quantity": item.get("quantity", 1),
                })
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                normalized_requested.append({
                    "item_type": str(item[0]),
                    "quantity": int(item[1]),
                })
        action_data["requested_items"] = normalized_requested
        
        return action_data

    def _fallback_idle(self, agent_id, reason):
        self._parse_errors.append(reason)
        return IdleAction(agent_id=agent_id, reason=f"Parse fallback: {reason}"), reason

    def get_parse_errors(self):
        return list(self._parse_errors)

    def clear_errors(self):
        self._parse_errors = []
