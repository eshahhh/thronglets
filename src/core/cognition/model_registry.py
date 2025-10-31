class ModelConfig:
    def __init__(self, model_id, model_name, base_url=None, api_key=None, max_tokens=1024, temperature=0.7, tier="standard", capabilities=None):
        self.model_id = model_id
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.tier = tier
        self.capabilities = list(capabilities) if capabilities is not None else []

    def to_dict(self):
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "tier": self.tier,
            "capabilities": self.capabilities,
        }


class ModelRegistry:
    def __init__(self):
        self._models = {}
        self._tier_assignments = {}
        self._role_assignments = {}
        self._default_model = None

    def register_model(self, config):
        self._models[config.model_id] = config
        if self._default_model is None:
            self._default_model = config.model_id

    def get_model(self, model_id):
        return self._models.get(model_id)

    def set_default_model(self, model_id):
        if model_id not in self._models:
            raise ValueError(f"Model {model_id} not registered")
        self._default_model = model_id

    def get_default_model(self):
        if self._default_model:
            return self._models.get(self._default_model)
        return None

    def assign_tier(self, agent_type, model_id):
        if model_id not in self._models:
            raise ValueError(f"Model {model_id} not registered")
        self._tier_assignments[agent_type] = model_id

    def assign_role(self, role, model_id):
        if model_id not in self._models:
            raise ValueError(f"Model {model_id} not registered")
        self._role_assignments[role] = model_id

    def get_model_for_agent(self, agent_id, agent_type=None, role=None, skill_level=0.0):
        if role and role in self._role_assignments:
            return self._models[self._role_assignments[role]]

        if agent_type and agent_type in self._tier_assignments:
            return self._models[self._tier_assignments[agent_type]]

        if skill_level > 0.8:
            elite_models = [m for m in self._models.values() if m.tier == "elite"]
            if elite_models:
                return elite_models[0]

        return self.get_default_model()

    def list_models(self):
        return list(self._models.values())

    def list_model_ids(self):
        return list(self._models.keys())

    @classmethod
    def from_config(cls, config, api_key=None, base_url=None):
        registry = cls()

        for model_data in config.get("models", []):
            model_config = ModelConfig(
                model_id=model_data["id"],
                model_name=model_data["name"],
                base_url=model_data.get("base_url", base_url),
                api_key=model_data.get("api_key", api_key),
                max_tokens=model_data.get("max_tokens", 1024),
                temperature=model_data.get("temperature", 0.7),
                tier=model_data.get("tier", "standard"),
                capabilities=model_data.get("capabilities", []),
            )
            registry.register_model(model_config)

        if "default" in config:
            registry.set_default_model(config["default"])

        for tier, model_id in config.get("tier_assignments", {}).items():
            registry.assign_tier(tier, model_id)

        for role, model_id in config.get("role_assignments", {}).items():
            registry.assign_role(role, model_id)

        return registry

    @classmethod
    def create_single_model_registry(cls, model_name, api_key, base_url=None, max_tokens=1024, temperature=0.7):
        registry = cls()
        config = ModelConfig(
            model_id="default",
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
            tier="standard",
            capabilities=["action", "negotiation", "reflection"],
        )
        registry.register_model(config)
        return registry
