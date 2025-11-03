import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass
class AgentCooldown:
    consecutive_errors: int = 0
    last_request_time: float = 0.0
    last_error_time: float = 0.0
    cooldown_until: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0

    @property
    def is_on_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    @property
    def remaining_cooldown(self) -> float:
        remaining = self.cooldown_until - time.time()
        return max(0.0, remaining)


class RateLimiter:
    BASE_COOLDOWN = 5.0
    MAX_COOLDOWN = 120.0
    BACKOFF_MULTIPLIER = 2.0

    MIN_REQUEST_INTERVAL = 0.5
    GLOBAL_MIN_INTERVAL = 0.1

    CONSECUTIVE_ERROR_THRESHOLD = 3
    REQUESTS_BEFORE_MANDATORY_REST = 5

    def __init__(
        self,
        base_cooldown: float = 5.0,
        max_cooldown: float = 120.0,
        min_request_interval: float = 0.5,
        global_min_interval: float = 0.1,
        enable_mandatory_rest: bool = True,
        mandatory_rest_interval: int = 5,
    ):
        self.base_cooldown = base_cooldown
        self.max_cooldown = max_cooldown
        self.min_request_interval = min_request_interval
        self.global_min_interval = global_min_interval
        self.enable_mandatory_rest = enable_mandatory_rest
        self.mandatory_rest_interval = mandatory_rest_interval

        self._agent_cooldowns: Dict[str, AgentCooldown] = defaultdict(AgentCooldown)
        self._last_global_request: float = 0.0
        self._resting_agents: Set[str] = set()
        self._current_tick: int = 0

        self._is_night: bool = False
        self._night_start_tick: int = 0
        self._night_duration_ticks: int = 5
        self._error_count_this_tick: int = 0
        self._error_threshold_for_night: int = 3

    def set_tick(self, tick: int) -> None:
        if tick != self._current_tick:
            self._current_tick = tick
            self._error_count_this_tick = 0

            if self._is_night and tick >= self._night_start_tick + self._night_duration_ticks:
                self._is_night = False
                self._resting_agents.clear()

    def is_night_mode(self) -> bool:
        return self._is_night

    def trigger_night_mode(self, duration_ticks: int = 5) -> None:
        self._is_night = True
        self._night_start_tick = self._current_tick
        self._night_duration_ticks = duration_ticks
        self._resting_agents.clear()

    def can_make_request(self, agent_id: str) -> tuple[bool, str]:
        cooldown = self._agent_cooldowns[agent_id]
        current_time = time.time()

        if self._is_night:
            return False, f"Night mode active (rest period). {self._night_start_tick + self._night_duration_ticks - self._current_tick} ticks remaining."

        if cooldown.is_on_cooldown:
            return False, f"Rate limited. Cooldown: {cooldown.remaining_cooldown:.1f}s remaining"

        if agent_id in self._resting_agents:
            return False, "Mandatory rest period (preventing API overload)"

        time_since_last = current_time - cooldown.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            return False, f"Too soon since last request. Wait {wait_time:.2f}s"

        time_since_global = current_time - self._last_global_request
        if time_since_global < self.global_min_interval:
            wait_time = self.global_min_interval - time_since_global
            return False, f"Global rate limit. Wait {wait_time:.2f}s"

        return True, ""

    def record_request_start(self, agent_id: str) -> None:
        current_time = time.time()
        cooldown = self._agent_cooldowns[agent_id]
        cooldown.last_request_time = current_time
        cooldown.total_requests += 1
        self._last_global_request = current_time

    def record_request_success(self, agent_id: str) -> None:
        cooldown = self._agent_cooldowns[agent_id]
        cooldown.consecutive_errors = 0
        cooldown.successful_requests += 1

        if self.enable_mandatory_rest:
            if cooldown.successful_requests % self.mandatory_rest_interval == 0:
                self._resting_agents.add(agent_id)

    def record_request_error(self, agent_id: str, error_message: str = "") -> float:
        current_time = time.time()
        cooldown = self._agent_cooldowns[agent_id]
        cooldown.consecutive_errors += 1
        cooldown.last_error_time = current_time
        self._error_count_this_tick += 1

        backoff_power = min(cooldown.consecutive_errors - 1, 5)
        cooldown_duration = self.base_cooldown * (self.BACKOFF_MULTIPLIER ** backoff_power)
        cooldown_duration = min(cooldown_duration, self.max_cooldown)

        if "rate" in error_message.lower() or "too many" in error_message.lower():
            cooldown_duration *= 2

        cooldown.cooldown_until = current_time + cooldown_duration

        if self._error_count_this_tick >= self._error_threshold_for_night:
            self.trigger_night_mode()

        return cooldown_duration

    def clear_rest(self, agent_id: str) -> None:
        self._resting_agents.discard(agent_id)

    def clear_all_rests(self) -> None:
        self._resting_agents.clear()

    def reset_agent(self, agent_id: str) -> None:
        self._agent_cooldowns[agent_id] = AgentCooldown()
        self._resting_agents.discard(agent_id)

    def reset_all(self) -> None:
        self._agent_cooldowns.clear()
        self._resting_agents.clear()
        self._last_global_request = 0.0
        self._is_night = False
        self._error_count_this_tick = 0

    def get_agent_status(self, agent_id: str) -> dict:
        cooldown = self._agent_cooldowns[agent_id]
        return {
            "agent_id": agent_id,
            "consecutive_errors": cooldown.consecutive_errors,
            "is_on_cooldown": cooldown.is_on_cooldown,
            "remaining_cooldown": cooldown.remaining_cooldown,
            "is_resting": agent_id in self._resting_agents,
            "total_requests": cooldown.total_requests,
            "successful_requests": cooldown.successful_requests,
        }

    def get_global_status(self) -> dict:
        agents_on_cooldown = sum(1 for c in self._agent_cooldowns.values() if c.is_on_cooldown)
        return {
            "is_night_mode": self._is_night,
            "night_ticks_remaining": max(0, self._night_start_tick + self._night_duration_ticks - self._current_tick) if self._is_night else 0,
            "agents_on_cooldown": agents_on_cooldown,
            "agents_resting": len(self._resting_agents),
            "total_agents_tracked": len(self._agent_cooldowns),
            "errors_this_tick": self._error_count_this_tick,
        }

    def get_wait_time(self, agent_id: str) -> float:
        can_request, _ = self.can_make_request(agent_id)
        if can_request:
            return 0.0

        cooldown = self._agent_cooldowns[agent_id]
        current_time = time.time()

        waits = []

        if cooldown.is_on_cooldown:
            waits.append(cooldown.remaining_cooldown)

        time_since_last = current_time - cooldown.last_request_time
        if time_since_last < self.min_request_interval:
            waits.append(self.min_request_interval - time_since_last)

        time_since_global = current_time - self._last_global_request
        if time_since_global < self.global_min_interval:
            waits.append(self.global_min_interval - time_since_global)

        return max(waits) if waits else 0.0
