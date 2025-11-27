from .agent_state import AgentState

class AgentManager:
    def __init__(self):
        self._agents = {}
        self._next_id = 0

    def _generate_id(self):
        agent_id = f"agent_{self._next_id}"
        self._next_id += 1
        return agent_id

    def spawn_agent(
        self,
        name,
        location="",
        inventory=None,
        capacity=100,
        needs=None,
        skills=None,
        reputation=None,
        random_seed=0,
        attributes=None,
        agent_id=None,
    ):
        if agent_id is None:
            agent_id = self._generate_id()
        elif agent_id in self._agents:
            raise ValueError(f"Agent with ID '{agent_id}' already exists")

        agent = AgentState(
            id=agent_id,
            name=name,
            location=location,
            inventory=inventory,
            capacity=capacity,
            needs=needs,
            skills=skills,
            reputation=reputation,
            random_seed=random_seed,
            attributes=attributes,
        )

        self._agents[agent_id] = agent
        return agent

    def get_agent(self, agent_id):
        return self._agents.get(agent_id)

    def get_agent_or_raise(self, agent_id):
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Agent with ID '{agent_id}' not found")
        return agent

    def remove_agent(self, agent_id):
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def list_agents(self):
        return list(self._agents.values())

    def list_agent_ids(self):
        return list(self._agents.keys())

    def get_agents_at_location(self, location_id):
        return [a for a in self._agents.values() if a.location == location_id]

    def update_agent_location(self, agent_id, new_location):
        agent = self.get_agent_or_raise(agent_id)
        agent.location = new_location

    def update_agent_inventory(
        self, agent_id, item, delta
    ):
        agent = self.get_agent_or_raise(agent_id)
        current = agent.inventory.get(item, 0)
        new_count = current + delta

        if new_count < 0:
            return False

        if delta > 0 and agent.inventory_space < delta:
            return False

        if new_count == 0:
            agent.inventory.pop(item, None)
        else:
            agent.inventory[item] = new_count

        return True

    def update_agent_need(
        self, agent_id, need, value
    ):
        agent = self.get_agent_or_raise(agent_id)
        agent.needs[need] = max(0.0, min(100.0, value))

    def update_agent_skill(
        self, agent_id, skill, delta
    ):
        agent = self.get_agent_or_raise(agent_id)
        current = agent.skills.get(skill, 0.0)
        agent.skills[skill] = max(0.0, current + delta)

    def agent_count(self):
        return len(self._agents)

    def clear(self):
        self._agents.clear()
        self._next_id = 0
