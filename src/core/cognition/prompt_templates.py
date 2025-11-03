from string import Template

class PromptTemplates:
    SYSTEM_PROMPT = """You are an agent in a barter economy simulation. Survive by managing needs, gathering resources, and trading.

RULES:
- Use only resources in your inventory
- Move to adjacent locations only
- Trade with agents at same location
- Needs decrease each tick - reach 0 = penalties
- No currency - barter only

PERSONA: $persona

GOALS: $goals

RECENT MEMORY: $memory_summary
"""

    ACTION_INSTRUCTION = """Choose ONE action based on your situation.

ACTIONS:
$available_actions

RESPOND WITH JSON ONLY:
{"reasoning": "why", "action": {"action_type": "TYPE", ...params}}

EXAMPLES:
Harvest: {"reasoning": "need food", "action": {"action_type": "HARVEST", "resource_type": "wheat", "amount": 5}}
Move: {"reasoning": "find traders", "action": {"action_type": "MOVE", "destination": "village_square"}}
Message: {"reasoning": "offer trade", "action": {"action_type": "MESSAGE", "recipient_id": "agent_2", "channel": "direct", "content": "Trade wheat for wood?"}}
Trade: {"reasoning": "need wood", "action": {"action_type": "TRADE_PROPOSAL", "target_agent_id": "agent_3", "offered_items": [{"item_type": "wheat", "quantity": 5}], "requested_items": [{"item_type": "wood", "quantity": 3}]}}
Accept: {"reasoning": "good deal", "action": {"action_type": "ACCEPT_TRADE", "proposal_id": "trade_123", "accept": true}}
Idle: {"reasoning": "waiting", "action": {"action_type": "IDLE", "reason": "waiting for response"}}

SITUATION:
$observation

$movement_hint

JSON only, no extra text."""

    NEGOTIATION_PROMPT = """You are negotiating with $other_agent_name.

CONVERSATION HISTORY:
$conversation_history

YOUR POSITION:
- You have: $your_inventory
- You need: $your_needs
- Your goal in this negotiation: $negotiation_goal

THEIR LAST MESSAGE:
$last_message

Respond naturally as if speaking to them. Be strategic but not deceptive. Build reputation through fair dealing.
Keep your response concise (1-3 sentences)."""

    REFLECTION_PROMPT = """Review your recent actions and outcomes:

RECENT HISTORY:
$recent_actions

CURRENT STATE:
- Needs: $current_needs
- Inventory: $current_inventory
- Reputation changes: $reputation_changes

Reflect on:
1. What worked well?
2. What should you do differently?
3. Who should you ally with or avoid?
4. What resources should you prioritize?

Provide a brief strategic summary (2-4 sentences) for future decision-making."""

    @classmethod
    def build_system_prompt(
        cls,
        persona="A practical survivor focused on meeting basic needs.",
        goals="Survive by maintaining food and shelter. Build positive reputation through fair trade.",
        memory_summary="No significant memories yet.",
    ):
        template = Template(cls.SYSTEM_PROMPT)
        return template.substitute(
            persona=persona,
            goals=goals,
            memory_summary=memory_summary,
        )

    @classmethod
    def build_action_prompt(
        cls,
        observation,
        available_actions,
        movement_hint="",
    ):
        template = Template(cls.ACTION_INSTRUCTION)
        return template.substitute(
            observation=observation,
            available_actions=available_actions,
            movement_hint=movement_hint,
        )

    @classmethod
    def build_negotiation_prompt(
        cls,
        other_agent_name,
        conversation_history,
        your_inventory,
        your_needs,
        negotiation_goal,
        last_message,
    ):
        template = Template(cls.NEGOTIATION_PROMPT)
        return template.substitute(
            other_agent_name=other_agent_name,
            conversation_history=conversation_history,
            your_inventory=your_inventory,
            your_needs=your_needs,
            negotiation_goal=negotiation_goal,
            last_message=last_message,
        )

    @classmethod
    def build_reflection_prompt(
        cls,
        recent_actions,
        current_needs,
        current_inventory,
        reputation_changes,
    ):
        template = Template(cls.REFLECTION_PROMPT)
        return template.substitute(
            recent_actions=recent_actions,
            current_needs=current_needs,
            current_inventory=current_inventory,
            reputation_changes=reputation_changes,
        )

    @classmethod
    def format_available_actions(cls, actions):
        lines = []
        for action in actions:
            line = f"- {action['type']}: {action['description']}"
            if "valid_destinations" in action:
                line += f" [destinations: {', '.join(action['valid_destinations'][:5])}]"
            if "available_resources" in action:
                resources = action['available_resources'][:5]
                line += f" [resources: {', '.join(resources)}]"
            if "nearby_agents" in action:
                agents = action['nearby_agents'][:3]
                line += f" [agents: {', '.join(agents)}]"
            if "pending_proposals" in action:
                proposals = action['pending_proposals'][:3]
                line += f" [proposals: {', '.join(proposals)}]"
            lines.append(line)
        return "\n".join(lines)
    
    @classmethod
    def get_movement_hint(cls, has_nearby_agents, inventory_size, most_urgent_need):
        hints = []
        
        if not has_nearby_agents:
            hints.append("No agents nearby - consider MOVING to find trading partners!")
        
        if inventory_size > 50:
            hints.append("Full inventory - seek others to trade excess resources.")
        
        if most_urgent_need == "reputation" and not has_nearby_agents:
            hints.append("Reputation is low - move to locations with other agents to trade and build reputation.")
        
        return " ".join(hints) if hints else ""
