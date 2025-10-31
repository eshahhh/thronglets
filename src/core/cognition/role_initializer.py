import random


class PersonaTemplate:
    def __init__(self, name, description, traits, preferred_skills, temperament, risk_tolerance, social_tendency):
        self.name = name
        self.description = description
        self.traits = traits
        self.preferred_skills = preferred_skills
        self.temperament = temperament
        self.risk_tolerance = risk_tolerance
        self.social_tendency = social_tendency


class RoleInitializer:
    ARCHETYPES = {
        "farmer": PersonaTemplate(
            name="Farmer",
            description="A hardworking individual focused on sustainable food production",
            traits=["patient", "practical", "community-minded"],
            preferred_skills=["farming", "harvesting", "cultivation"],
            temperament="steady",
            risk_tolerance=0.3,
            social_tendency=0.6,
        ),
        "trader": PersonaTemplate(
            name="Trader",
            description="A shrewd negotiator who thrives on exchange and bargaining",
            traits=["persuasive", "calculating", "opportunistic"],
            preferred_skills=["negotiation", "appraisal", "logistics"],
            temperament="dynamic",
            risk_tolerance=0.7,
            social_tendency=0.9,
        ),
        "crafter": PersonaTemplate(
            name="Crafter",
            description="A skilled artisan who transforms raw materials into valuable goods",
            traits=["meticulous", "creative", "independent"],
            preferred_skills=["crafting", "building", "repair"],
            temperament="focused",
            risk_tolerance=0.4,
            social_tendency=0.5,
        ),
        "gatherer": PersonaTemplate(
            name="Gatherer",
            description="An explorer who excels at finding and collecting resources",
            traits=["observant", "resourceful", "adaptable"],
            preferred_skills=["foraging", "exploration", "survival"],
            temperament="wandering",
            risk_tolerance=0.5,
            social_tendency=0.4,
        ),
        "leader": PersonaTemplate(
            name="Leader",
            description="A charismatic individual who organizes groups and builds institutions",
            traits=["charismatic", "strategic", "diplomatic"],
            preferred_skills=["leadership", "negotiation", "planning"],
            temperament="ambitious",
            risk_tolerance=0.6,
            social_tendency=1.0,
        ),
        "specialist": PersonaTemplate(
            name="Specialist",
            description="An expert focused on mastering a single domain",
            traits=["dedicated", "perfectionist", "knowledgeable"],
            preferred_skills=["expertise", "research", "efficiency"],
            temperament="methodical",
            risk_tolerance=0.2,
            social_tendency=0.3,
        ),
        "opportunist": PersonaTemplate(
            name="Opportunist",
            description="A flexible agent who adapts to whatever situation is most profitable",
            traits=["flexible", "cunning", "self-interested"],
            preferred_skills=["adaptation", "assessment", "timing"],
            temperament="reactive",
            risk_tolerance=0.8,
            social_tendency=0.7,
        ),
        "cooperator": PersonaTemplate(
            name="Cooperator",
            description="A community-focused individual who prioritizes collective welfare",
            traits=["altruistic", "trustworthy", "collaborative"],
            preferred_skills=["teamwork", "communication", "mediation"],
            temperament="harmonious",
            risk_tolerance=0.4,
            social_tendency=0.95,
        ),
    }

    NAMES_POOL = [
        "Ada", "Basil", "Cora", "Dane", "Ella", "Finn", "Gwen", "Hugo",
        "Iris", "Joel", "Kira", "Liam", "Maya", "Noel", "Opal", "Paul",
        "Quinn", "Rosa", "Seth", "Tara", "Umar", "Vera", "Wade", "Xena",
        "Yuri", "Zara", "Arlo", "Beth", "Cole", "Dawn", "Evan", "Faye",
    ]

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._name_index = 0

    def set_seed(self, seed):
        self._rng = random.Random(seed)

    def _generate_name(self, prefix=""):
        if self._name_index < len(self.NAMES_POOL):
            name = self.NAMES_POOL[self._name_index]
            self._name_index += 1
        else:
            name = f"Agent_{self._name_index}"
            self._name_index += 1

        if prefix:
            return f"{prefix}_{name}"
        return name

    def _select_archetype(self, weights=None):
        archetypes = list(self.ARCHETYPES.keys())

        if weights:
            w = [weights.get(a, 1.0) for a in archetypes]
        else:
            w = [1.0] * len(archetypes)

        total = sum(w)
        w = [x / total for x in w]

        selected = self._rng.choices(archetypes, weights=w, k=1)[0]
        return self.ARCHETYPES[selected]

    def _generate_skills(self, archetype, skill_variance=0.3):
        skills = {}

        for skill in archetype.preferred_skills:
            base = 0.4 + self._rng.random() * 0.4
            variance = (self._rng.random() - 0.5) * skill_variance
            skills[skill] = max(0.1, min(1.0, base + variance))

        all_skills = ["farming", "crafting", "negotiation", "foraging", "building", "leadership"]
        for skill in all_skills:
            if skill not in skills:
                if self._rng.random() < 0.3:
                    skills[skill] = self._rng.random() * 0.3

        return skills

    def _generate_needs(self, variance=0.2):
        base_needs = {
            "food": 100.0,
            "shelter": 100.0,
            "reputation": 50.0,
        }

        for need in base_needs:
            adjustment = (self._rng.random() - 0.5) * variance * base_needs[need]
            base_needs[need] = max(0.0, min(100.0, base_needs[need] + adjustment))

        return base_needs

    def _generate_persona_text(self, archetype, traits_variance=0.2):
        base_traits = list(archetype.traits)

        extra_traits = ["cautious", "bold", "friendly", "reserved", "curious", "traditional"]
        if self._rng.random() < traits_variance:
            extra = self._rng.choice(extra_traits)
            base_traits.append(extra)

        traits_text = ", ".join(base_traits)

        persona = f"{archetype.description}. "
        persona += f"Personality traits: {traits_text}. "
        persona += f"Temperament: {archetype.temperament}. "
        persona += f"Risk tolerance: {'high' if archetype.risk_tolerance > 0.6 else 'moderate' if archetype.risk_tolerance > 0.3 else 'low'}. "
        persona += f"Social tendency: {'highly social' if archetype.social_tendency > 0.7 else 'moderately social' if archetype.social_tendency > 0.4 else 'prefers solitude'}."

        return persona

    def _generate_goals_text(self, archetype):
        base_goals = ["Survive by maintaining food and shelter needs."]

        if archetype.social_tendency > 0.7:
            base_goals.append("Build positive relationships and reputation through fair dealings.")

        if "trader" in archetype.name.lower() or archetype.risk_tolerance > 0.6:
            base_goals.append("Accumulate resources through strategic trading.")

        if "crafter" in archetype.name.lower():
            base_goals.append("Master crafting skills and produce valuable goods.")

        if "leader" in archetype.name.lower():
            base_goals.append("Form or join groups to achieve collective goals.")

        if archetype.risk_tolerance < 0.4:
            base_goals.append("Maintain stable resource reserves for security.")

        return " ".join(base_goals)

    def initialize_agent(self, agent_id=None, archetype=None, archetype_weights=None, name_prefix=""):
        if archetype and archetype in self.ARCHETYPES:
            selected_archetype = self.ARCHETYPES[archetype]
        else:
            selected_archetype = self._select_archetype(archetype_weights)

        name = self._generate_name(name_prefix)

        skills = self._generate_skills(selected_archetype)
        needs = self._generate_needs()
        persona = self._generate_persona_text(selected_archetype)
        goals = self._generate_goals_text(selected_archetype)

        return {
            "agent_id": agent_id,
            "name": name,
            "archetype": selected_archetype.name,
            "skills": skills,
            "needs": needs,
            "persona": persona,
            "goals": goals,
            "attributes": {
                "risk_tolerance": selected_archetype.risk_tolerance,
                "social_tendency": selected_archetype.social_tendency,
                "temperament": selected_archetype.temperament,
            },
        }

    def initialize_population(self, count, archetype_distribution=None, id_prefix="agent"):
        agents = []

        for i in range(count):
            agent_id = f"{id_prefix}_{i}"
            agent_data = self.initialize_agent(
                agent_id=agent_id,
                archetype_weights=archetype_distribution,
            )
            agents.append(agent_data)

        return agents

    def get_archetype_names(self):
        return list(self.ARCHETYPES.keys())

    def get_archetype(self, name):
        return self.ARCHETYPES.get(name)

    def reset(self):
        self._name_index = 0
