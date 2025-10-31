from string import Template

class PromptTemplates:
    SYSTEM_PROMPT = """You are an autonomous agent in a simulated economy. You must survive and thrive by managing your needs (food, shelter, reputation), gathering resources, crafting goods, and trading with other agents.

CORE RULES:
1. You can only use resources you actually have in your inventory
2. You can only move to adjacent locations
3. You can only trade with agents at the same location
4. Your needs decrease over time - if any need reaches 0, you suffer penalties
5. There is NO currency - all trade is barter
6. You can form alliances, groups, and informal agreements

YOUR PERSONA:
$persona

YOUR GOALS:
$goals

YOUR MEMORY:
$memory_summary
"""

    ACTION_INSTRUCTION = """Based on your current situation, choose ONE action to take.

AVAILABLE ACTIONS:
$available_actions

RESPOND WITH JSON ONLY in this exact format:
{
    "reasoning": "Brief explanation of why you chose this action",
    "action": {
        "action_type": "ACTION_TYPE",
        ... action parameters ...
    }
}

EXAMPLES:

To harvest resources:
{
    "reasoning": "I need food and there's wheat available here",
    "action": {
        "action_type": "HARVEST",
        "resource_type": "wheat",
        "amount": 5
    }
}

To move locations:
{
    "reasoning": "The forest has more wood which I need for crafting",
    "action": {
        "action_type": "MOVE",
        "destination": "forest_1"
    }
}

To send a message:
{
    "reasoning": "I want to ask agent_2 if they want to trade",
    "action": {
        "action_type": "MESSAGE",
        "recipient_id": "agent_2",
        "channel": "direct",
        "content": "Hello! I have extra wheat. Would you trade some wood for it?"
    }
}

To propose a trade:
{
    "reasoning": "agent_3 has wood and I have excess wheat",
    "action": {
        "action_type": "TRADE_PROPOSAL",
        "target_agent_id": "agent_3",
        "offered_items": [{"item_type": "wheat", "quantity": 10}],
        "requested_items": [{"item_type": "wood", "quantity": 5}]
    }
}

To accept a trade:
{
    "reasoning": "This trade gives me resources I need",
    "action": {
        "action_type": "ACCEPT_TRADE",
        "proposal_id": "trade_123",
        "accept": true
    }
}

To craft items:
{
    "reasoning": "I have the materials to make bread",
    "action": {
        "action_type": "CRAFT",
        "recipe_id": "bread",
        "quantity": 2
    }
}

To do nothing:
{
    "reasoning": "I'm waiting for a trade response",
    "action": {
        "action_type": "IDLE",
        "reason": "Waiting for trade response"
    }
}

To form a group:
{
    "reasoning": "I want to create a farming cooperative",
    "action": {
        "action_type": "GROUP_ACTION",
        "group_action_type": "FORM_GROUP",
        "payload": {"name": "Farmers Guild", "purpose": "Cooperative farming"}
    }
}

YOUR CURRENT SITUATION:
$observation

Remember: You can only use what you have. Think strategically about your long-term survival.
Respond with valid JSON only. No additional text."""

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
    ):
        template = Template(cls.ACTION_INSTRUCTION)
        return template.substitute(
            observation=observation,
            available_actions=available_actions,
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
            lines.append(f"- {action['type']}: {action['description']}")
            if "valid_destinations" in action:
                lines.append(f"    Valid destinations: {action['valid_destinations']}")
            if "available_resources" in action:
                lines.append(f"    Available resources: {action['available_resources']}")
            if "nearby_agents" in action:
                lines.append(f"    Nearby agents: {action['nearby_agents']}")
            if "pending_proposals" in action:
                lines.append(f"    Pending proposals: {action['pending_proposals']}")
        return "\n".join(lines)
