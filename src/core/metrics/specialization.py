from collections import defaultdict, Counter
from enum import Enum, auto
import math


class ProfessionType(Enum):
    FARMER = auto()
    GATHERER = auto()
    CRAFTER = auto()
    TRADER = auto()
    LEADER = auto()
    GENERALIST = auto()
    IDLE = auto()


class AgentProfession:
    def __init__(self, agent_id, primary_profession, secondary_profession,
                 specialization_score, action_distribution, resource_focus, confidence):
        self.agent_id = agent_id
        self.primary_profession = primary_profession
        self.secondary_profession = secondary_profession
        self.specialization_score = specialization_score
        self.action_distribution = action_distribution
        self.resource_focus = resource_focus
        self.confidence = confidence

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "primary_profession": self.primary_profession.name,
            "secondary_profession": self.secondary_profession.name if self.secondary_profession else None,
            "specialization_score": self.specialization_score,
            "action_distribution": self.action_distribution,
            "resource_focus": self.resource_focus,
            "confidence": self.confidence,
        }


class SpecializationDetector:
    def __init__(self, window_size=100):
        self.window_size = window_size

        self._action_history = defaultdict(list)
        self._resource_history = defaultdict(Counter)
        self._profession_cache = {}
        self._cluster_assignments = {}
        self._profession_history = defaultdict(list)

    def record_action(self, agent_id, tick, action_type, details):
        self._action_history[agent_id].append({
            "tick": tick,
            "action_type": action_type,
            "details": details,
        })

        if len(self._action_history[agent_id]) > self.window_size:
            self._action_history[agent_id].pop(0)

        if action_type in ("HARVEST", "CRAFT"):
            resource = details.get("resource_type") or details.get("recipe_id")
            if resource:
                self._resource_history[agent_id][resource] += 1

        self._profession_cache.pop(agent_id, None)

    def detect_profession(self, agent_id):
        if agent_id in self._profession_cache:
            return self._profession_cache[agent_id]

        actions = self._action_history.get(agent_id, [])
        if not actions:
            return None

        action_counts = Counter(a["action_type"] for a in actions)
        total_actions = sum(action_counts.values())

        if total_actions == 0:
            return None

        action_distribution = {
            action: count / total_actions
            for action, count in action_counts.items()
        }

        harvest_ratio = action_distribution.get("HARVEST", 0)
        craft_ratio = action_distribution.get("CRAFT", 0)
        trade_ratio = action_distribution.get("TRADE_PROPOSAL", 0) + action_distribution.get("ACCEPT_TRADE", 0)
        message_ratio = action_distribution.get("MESSAGE", 0)
        group_ratio = action_distribution.get("GROUP_ACTION", 0)
        idle_ratio = action_distribution.get("IDLE", 0)

        profession_scores = {
            ProfessionType.FARMER: harvest_ratio * 1.5 if self._focuses_on_food(agent_id) else 0,
            ProfessionType.GATHERER: harvest_ratio * 1.2,
            ProfessionType.CRAFTER: craft_ratio * 1.5,
            ProfessionType.TRADER: trade_ratio * 2.0,
            ProfessionType.LEADER: (group_ratio + message_ratio) * 1.5,
            ProfessionType.GENERALIST: 0.3 if self._is_generalist(action_distribution) else 0,
            ProfessionType.IDLE: idle_ratio * 0.5,
        }

        sorted_professions = sorted(
            profession_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        primary = sorted_professions[0][0]
        primary_score = sorted_professions[0][1]

        secondary = None
        if len(sorted_professions) > 1 and sorted_professions[1][1] > 0.2:
            secondary = sorted_professions[1][0]

        specialization_score = self._calculate_specialization(action_distribution)

        resource_focus = self._get_resource_focus(agent_id)

        confidence = min(1.0, primary_score / 0.5) * min(1.0, total_actions / 20)

        profession = AgentProfession(
            agent_id=agent_id,
            primary_profession=primary,
            secondary_profession=secondary,
            specialization_score=specialization_score,
            action_distribution=action_distribution,
            resource_focus=resource_focus,
            confidence=confidence,
        )

        self._profession_cache[agent_id] = profession
        return profession

    def _focuses_on_food(self, agent_id):
        resources = self._resource_history.get(agent_id, Counter())
        food_items = {"wheat", "berries", "fish", "meat", "bread", "apple", "corn"}

        food_count = sum(resources[r] for r in food_items if r in resources)
        total_count = sum(resources.values())

        return food_count / total_count > 0.5 if total_count > 0 else False

    def _is_generalist(self, action_distribution):
        if len(action_distribution) < 3:
            return False

        values = [v for v in action_distribution.values() if v > 0.05]
        if len(values) < 3:
            return False

        max_ratio = max(values)
        return max_ratio < 0.4

    def _calculate_specialization(self, action_distribution):
        if not action_distribution:
            return 0.0

        values = list(action_distribution.values())
        if not values:
            return 0.0

        max_entropy = math.log(len(values)) if len(values) > 1 else 1.0

        entropy = -sum(v * math.log(v) if v > 0 else 0 for v in values)

        specialization = 1 - (entropy / max_entropy) if max_entropy > 0 else 0
        return max(0.0, min(1.0, specialization))

    def _get_resource_focus(self, agent_id, top_n=3):
        resources = self._resource_history.get(agent_id, Counter())
        return [r for r, _ in resources.most_common(top_n)]

    def detect_all_professions(self):
        return {
            agent_id: self.detect_profession(agent_id)
            for agent_id in self._action_history.keys()
        }

    def cluster_agents(self):
        all_professions = self.detect_all_professions()

        clusters = defaultdict(list)

        for agent_id, profession in all_professions.items():
            if profession:
                clusters[profession.primary_profession].append(agent_id)

        numbered_clusters = {
            i: agents
            for i, (_, agents) in enumerate(clusters.items())
        }

        for i, agents in numbered_clusters.items():
            for agent_id in agents:
                self._cluster_assignments[agent_id] = i

        return numbered_clusters

    def get_profession_distribution(self):
        all_professions = self.detect_all_professions()

        distribution = Counter()
        for profession in all_professions.values():
            if profession:
                distribution[profession.primary_profession.name] += 1

        return dict(distribution)

    def get_specialization_metrics(self, tick):
        all_professions = self.detect_all_professions()

        specialization_scores = [
            p.specialization_score for p in all_professions.values() if p
        ]

        if not specialization_scores:
            return {
                "tick": tick,
                "agent_count": 0,
                "avg_specialization": 0,
                "profession_distribution": {},
                "diversity_index": 0,
            }

        distribution = self.get_profession_distribution()
        total = sum(distribution.values())

        diversity_index = 0.0
        if total > 0:
            proportions = [count / total for count in distribution.values()]
            diversity_index = -sum(
                p * math.log(p) if p > 0 else 0 for p in proportions
            )

        return {
            "tick": tick,
            "agent_count": len(all_professions),
            "avg_specialization": sum(specialization_scores) / len(specialization_scores),
            "profession_distribution": distribution,
            "diversity_index": diversity_index,
        }

    def record_profession_snapshot(self, tick):
        for agent_id in self._action_history.keys():
            profession = self.detect_profession(agent_id)
            if profession:
                self._profession_history[agent_id].append(
                    (tick, profession.primary_profession)
                )

    def get_profession_stability(self, agent_id):
        history = self._profession_history.get(agent_id, [])
        if len(history) < 2:
            return 1.0

        professions = [p for _, p in history]
        most_common = Counter(professions).most_common(1)

        if not most_common:
            return 1.0

        return most_common[0][1] / len(professions)

    def to_dict(self):
        all_professions = self.detect_all_professions()

        return {
            "agent_professions": {
                agent_id: p.to_dict() if p else None
                for agent_id, p in all_professions.items()
            },
            "profession_distribution": self.get_profession_distribution(),
            "clusters": self.cluster_agents(),
        }
