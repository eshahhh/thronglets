class ObservationBuilder:
    def __init__(self, agent_manager, location_graph, message_bus, action_interpreter):
        self.agent_manager = agent_manager
        self.location_graph = location_graph
        self.message_bus = message_bus
        self.action_interpreter = action_interpreter

    def build_observation(self, agent_id, tick):
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}

        observation = {
            "tick": tick,
            "self": self._build_self_state(agent),
            "location": self._build_location_info(agent),
            "nearby_agents": self._build_nearby_agents(agent),
            "messages": self._build_messages(agent_id),
            "pending_trades": self._build_pending_trades(agent_id),
            "available_actions": self._build_available_actions(agent),
        }

        return observation

    def _build_self_state(self, agent):
        return {
            "id": agent.id,
            "name": agent.name,
            "inventory": dict(agent.inventory),
            "inventory_space": agent.inventory_space,
            "capacity": agent.capacity,
            "needs": dict(agent.needs),
            "most_urgent_need": agent.most_urgent_need,
            "skills": dict(agent.skills),
            "reputation": dict(agent.reputation),
        }

    def _build_location_info(self, agent):
        location_id = agent.location
        if not location_id:
            return {"id": None, "resources": {}, "neighbors": []}

        node = self.location_graph.get_node(location_id)
        if not node:
            return {"id": location_id, "resources": {}, "neighbors": []}

        neighbors = self.location_graph.get_neighbors(location_id)
        neighbor_info = []
        for neighbor_id in neighbors:
            neighbor_node = self.location_graph.get_node(neighbor_id)
            travel_cost = self.location_graph.travel_cost(location_id, neighbor_id)
            neighbor_info.append({
                "id": neighbor_id,
                "name": neighbor_node.name if neighbor_node else neighbor_id,
                "type": neighbor_node.location_type if neighbor_node else "unknown",
                "travel_cost": travel_cost,
            })

        return {
            "id": location_id,
            "name": node.name,
            "type": node.location_type,
            "resources": dict(node.resource_richness),
            "access_cost": node.access_cost,
            "neighbors": neighbor_info,
        }

    def _build_nearby_agents(self, agent):
        if not agent.location:
            return []

        agents_at_location = self.agent_manager.get_agents_at_location(agent.location)
        nearby = []

        for other in agents_at_location:
            if other.id == agent.id:
                continue
            nearby.append({
                "id": other.id,
                "name": other.name,
                "reputation": agent.reputation.get(other.id, 0.0),
            })

        return nearby

    def _build_messages(self, agent_id):
        inbox = self.message_bus.get_inbox(agent_id, unread_only=True, limit=10)

        direct_messages = []
        for msg in inbox:
            direct_messages.append({
                "id": msg.id,
                "from": msg.sender_id,
                "content": msg.content,
                "timestamp": msg.timestamp,
            })

        agent = self.agent_manager.get_agent(agent_id)
        location_messages = []
        if agent and agent.location:
            loc_msgs = self.message_bus.get_location_messages(agent.location, limit=5)
            for msg in loc_msgs:
                if msg.sender_id != agent_id:
                    location_messages.append({
                        "id": msg.id,
                        "from": msg.sender_id,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                    })

        return {
            "direct": direct_messages,
            "location": location_messages,
        }

    def _build_pending_trades(self, agent_id):
        trades = self.action_interpreter.get_pending_trades_for_agent(agent_id)
        result = []

        for trade in trades:
            is_proposer = trade["proposer_id"] == agent_id
            result.append({
                "proposal_id": trade["proposal_id"],
                "is_proposer": is_proposer,
                "other_party": trade["target_id"] if is_proposer else trade["proposer_id"],
                "offered_items": trade["offered_items"],
                "requested_items": trade["requested_items"],
            })

        return result

    def _build_available_actions(self, agent):
        actions = [
            {
                "type": "IDLE",
                "description": "Do nothing this turn",
                "parameters": ["reason"],
            },
            {
                "type": "MESSAGE",
                "description": "Send a message to another agent or broadcast",
                "parameters": ["recipient_id", "channel", "content"],
                "channels": ["direct", "location", "global"],
            },
        ]

        if agent.location:
            location = self.location_graph.get_node(agent.location)
            if location:
                neighbors = self.location_graph.get_neighbors(agent.location)
                if neighbors:
                    actions.append({
                        "type": "MOVE",
                        "description": "Move to an adjacent location",
                        "parameters": ["destination"],
                        "valid_destinations": neighbors,
                    })

                if location.resource_richness:
                    actions.append({
                        "type": "HARVEST",
                        "description": "Gather resources from current location",
                        "parameters": ["resource_type", "amount"],
                        "available_resources": list(location.resource_richness.keys()),
                    })

        if agent.inventory:
            actions.append({
                "type": "CRAFT",
                "description": "Craft items using resources in inventory",
                "parameters": ["recipe_id", "quantity"],
            })

        nearby_agents = self._build_nearby_agents(agent)
        if nearby_agents:
            actions.append({
                "type": "TRADE_PROPOSAL",
                "description": "Propose a trade with a nearby agent",
                "parameters": ["target_agent_id", "offered_items", "requested_items"],
                "nearby_agents": [a["id"] for a in nearby_agents],
            })

        pending_trades = self._build_pending_trades(agent.id)
        incoming_trades = [t for t in pending_trades if not t["is_proposer"]]
        if incoming_trades:
            actions.append({
                "type": "ACCEPT_TRADE",
                "description": "Accept or reject a pending trade proposal",
                "parameters": ["proposal_id", "accept"],
                "pending_proposals": [t["proposal_id"] for t in incoming_trades],
            })

        actions.append({
            "type": "GROUP_ACTION",
            "description": "Form, join, or leave a group; propose rules or vote",
            "parameters": ["group_action_type", "group_id", "payload"],
            "group_action_types": ["FORM_GROUP", "JOIN_GROUP", "LEAVE_GROUP", "VOTE", "PROPOSE_RULE"],
        })

        return actions

    def observation_to_text(self, observation):
        lines = []
        lines.append(f"=== TICK {observation['tick']} ===\n")

        self_state = observation["self"]
        lines.append("YOUR STATE:")
        lines.append(f"  Name: {self_state['name']} (ID: {self_state['id']})")
        lines.append(f"  Inventory ({self_state['inventory_space']} slots free): {self_state['inventory'] or 'empty'}")
        lines.append(f"  Needs: {self_state['needs']}")
        lines.append(f"  Most Urgent Need: {self_state['most_urgent_need']}")
        lines.append(f"  Skills: {self_state['skills'] or 'none'}")
        lines.append("")

        loc = observation["location"]
        if loc["id"]:
            lines.append("CURRENT LOCATION:")
            lines.append(f"  {loc['name']} ({loc['type']})")
            lines.append(f"  Resources available: {loc['resources'] or 'none'}")
            lines.append("  Nearby locations:")
            for neighbor in loc["neighbors"]:
                lines.append(f"    - {neighbor['name']} (travel cost: {neighbor['travel_cost']:.1f})")
            lines.append("")

        nearby = observation["nearby_agents"]
        if nearby:
            lines.append("NEARBY AGENTS:")
            for agent in nearby:
                lines.append(f"  - {agent['name']} (ID: {agent['id']})")
            lines.append("")

        messages = observation["messages"]
        if messages["direct"] or messages["location"]:
            lines.append("MESSAGES:")
            for msg in messages["direct"]:
                lines.append(f"  [DIRECT from {msg['from']}]: {msg['content']}")
            for msg in messages["location"]:
                lines.append(f"  [LOCAL from {msg['from']}]: {msg['content']}")
            lines.append("")

        trades = observation["pending_trades"]
        if trades:
            lines.append("PENDING TRADES:")
            for trade in trades:
                if trade["is_proposer"]:
                    lines.append(f"  [OUTGOING to {trade['other_party']}] ID: {trade['proposal_id']}")
                else:
                    lines.append(f"  [INCOMING from {trade['other_party']}] ID: {trade['proposal_id']}")
                    lines.append(f"    They offer: {trade['offered_items']}")
                    lines.append(f"    They want: {trade['requested_items']}")
            lines.append("")

        return "\n".join(lines)
