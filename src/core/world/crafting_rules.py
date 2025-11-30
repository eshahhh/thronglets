from dataclasses import dataclass, field


@dataclass
class Recipe:
    id: str
    name: str
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    time_cost: float = 1.0
    skill_requirements: dict = field(default_factory=dict)
    tool_requirements: list = field(default_factory=list)
    skill_bonuses: dict = field(default_factory=dict)


class CraftingRules:
    def __init__(self):
        self.recipes = {}

    def register(self, recipe):
        self.recipes[recipe.id] = recipe

    def get_recipe(self, recipe_id):
        return self.recipes.get(recipe_id)

    def can_craft(self, recipe_id, inventory, skills=None):
        recipe = self.get_recipe(recipe_id)
        if recipe is None:
            return False, "recipe not found"

        for item_id, required in recipe.inputs.items():
            have = inventory.get(item_id, 0)
            if have < required:
                return False, f"need {required} {item_id}, have {have}"

        for tool_id in recipe.tool_requirements:
            if inventory.get(tool_id, 0) < 1:
                return False, f"missing tool: {tool_id}"

        skills = skills or {}
        for skill_id, min_level in recipe.skill_requirements.items():
            if skills.get(skill_id, 0) < min_level:
                return False, f"need {skill_id} level {min_level}"

        return True, "ok"

    def craft(self, recipe_id, inventory, skills=None):
        recipe = self.get_recipe(recipe_id)
        new_inventory = dict(inventory)

        for item_id, amount in recipe.inputs.items():
            new_inventory[item_id] = new_inventory.get(item_id, 0) - amount
            if new_inventory[item_id] <= 0:
                del new_inventory[item_id]

        efficiency = 1.0
        skills = skills or {}
        for skill_id, bonus in recipe.skill_bonuses.items():
            skill_level = skills.get(skill_id, 0)
            efficiency += skill_level * bonus

        for item_id, base_amount in recipe.outputs.items():
            produced = int(base_amount * efficiency)
            new_inventory[item_id] = new_inventory.get(item_id, 0) + max(1, produced)

        time_spent = recipe.time_cost / max(0.1, efficiency)

        return new_inventory, time_spent

    def list_craftable(self, inventory, skills=None):
        return [
            recipe_id
            for recipe_id in self.recipes
            if self.can_craft(recipe_id, inventory, skills)[0]
        ]

    @classmethod
    def from_config(cls, config):
        rules = cls()

        for recipe_data in config.get("recipes", []):
            recipe = Recipe(
                id=recipe_data["id"],
                name=recipe_data.get("name", recipe_data["id"]),
                inputs=recipe_data.get("inputs", {}),
                outputs=recipe_data.get("outputs", {}),
                time_cost=recipe_data.get("time_cost", 1.0),
                skill_requirements=recipe_data.get("skill_requirements", {}),
                tool_requirements=recipe_data.get("tool_requirements", []),
                skill_bonuses=recipe_data.get("skill_bonuses", {}),
            )
            rules.register(recipe)

        return rules
