class AgentState:
    def __init__(self, id, name, location="", inventory=None, capacity=100,
                 needs=None, skills=None, reputation=None, random_seed=0,
                 attributes=None):
        self.id = id
        self.name = name
        self.location = location
        self.inventory = {} if inventory is None else inventory
        self.capacity = capacity
        self.needs = {
            "food": 100.0,
            "shelter": 100.0,
            "reputation": 50.0,
        } if needs is None else needs
        self.skills = {} if skills is None else skills
        self.reputation = {} if reputation is None else reputation
        self.random_seed = random_seed
        self.attributes = {} if attributes is None else attributes

    @property
    def inventory_count(self):
        return sum(self.inventory.values())

    @property
    def inventory_space(self):
        return self.capacity - self.inventory_count

    @property
    def most_urgent_need(self):
        if not self.needs:
            return ""
        return min(self.needs, key=lambda k: self.needs[k])
