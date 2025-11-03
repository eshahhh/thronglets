import time

from ..actions import BaseAction, IdleAction
from .observation_builder import ObservationBuilder
from .prompt_templates import PromptTemplates
from .model_registry import ModelRegistry, ModelConfig
from .inference_client import InferenceClient, InferenceResult
from .action_parser import ActionOutputParser
from .memory import MemorySubsystem
from ..logging import get_live_logger


class CognitionInterface:
    def __init__(
        self,
        observation_builder,
        model_registry,
        inference_client,
        memory_subsystem,
        action_parser=None,
        enable_logging=True,
        live_logger=None,
    ):
        self.observation_builder = observation_builder
        self.model_registry = model_registry
        self.inference_client = inference_client
        self.memory_subsystem = memory_subsystem
        self.action_parser = action_parser or ActionOutputParser(strict_validation=True)
        self.enable_logging = enable_logging
        self._logger = live_logger if live_logger else get_live_logger()
        
        self._agent_personas = {}
        self._agent_goals = {}
        self._stats = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "fallback_decisions": 0,
            "total_latency_ms": 0.0,
        }

    def set_persona(self, agent_id, persona):
        self._agent_personas[agent_id] = persona

    def set_goals(self, agent_id, goals):
        self._agent_goals[agent_id] = goals

    def get_persona(self, agent_id):
        return self._agent_personas.get(agent_id, "A practical survivor focused on meeting basic needs.")

    def get_goals(self, agent_id):
        return self._agent_goals.get(agent_id, "Survive by maintaining food and shelter. Build positive reputation through fair trade.")

    def choose_action(
        self,
        agent_id,
        tick,
        agent_type=None,
        role=None,
    ):
        start_time = time.time()
        self._stats["total_decisions"] += 1
        
        observation = self.observation_builder.build_observation(agent_id, tick)
        
        if "error" in observation:
            return IdleAction(agent_id=agent_id, reason=observation["error"]), {
                "success": False,
                "error": observation["error"],
            }
        
        if self.memory_subsystem.should_distill(agent_id, tick):
            self.memory_subsystem.distill_memories(agent_id, tick)
        
        memory_summary = self.memory_subsystem.get_memory_summary(agent_id)
        
        persona = self.get_persona(agent_id)
        goals = self.get_goals(agent_id)
        
        system_prompt = PromptTemplates.build_system_prompt(
            persona=persona,
            goals=goals,
            memory_summary=memory_summary,
        )
        
        observation_text = self.observation_builder.observation_to_text(observation)
        available_actions_text = PromptTemplates.format_available_actions(
            observation.get("available_actions", [])
        )
        
        has_nearby_agents = len(observation.get("nearby_agents", [])) > 0
        inventory_size = sum(observation.get("self", {}).get("inventory", {}).values())
        most_urgent_need = observation.get("self", {}).get("most_urgent_need", "")
        movement_hint = PromptTemplates.get_movement_hint(
            has_nearby_agents=has_nearby_agents,
            inventory_size=inventory_size,
            most_urgent_need=most_urgent_need,
        )
        
        user_prompt = PromptTemplates.build_action_prompt(
            observation=observation_text,
            available_actions=available_actions_text,
            movement_hint=movement_hint,
        )
        
        model_config = self.model_registry.get_model_for_agent(
            agent_id=agent_id,
            agent_type=agent_type,
            role=role,
        )
        
        result = self.inference_client.infer(
            model_config=model_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            agent_id=agent_id,
            tick=tick,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        self._stats["total_latency_ms"] += latency_ms
        
        if result.success:
            action, reasoning = self.action_parser.parse(
                llm_output=result.content,
                agent_id=agent_id,
                observation=observation,
            )
            
            if action.action_type.name != "IDLE" or "fallback" not in (reasoning or "").lower():
                self._stats["successful_decisions"] += 1
            else:
                self._stats["fallback_decisions"] += 1
            
            if self.enable_logging:
                self._logger.log_llm_response(
                    agent_id=agent_id,
                    tick=tick,
                    success=True,
                    latency_ms=latency_ms,
                    tokens=result.total_tokens,
                    action_type=action.action_type.name,
                    reasoning=reasoning or "",
                )
                self._logger.log_full_llm_exchange(
                    agent_id=agent_id,
                    tick=tick,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_response=result.content,
                    parsed_action={"action": action.action_type.name, "reasoning": reasoning},
                    latency_ms=latency_ms,
                    tokens=result.total_tokens,
                )
            
            metadata = {
                "success": True,
                "reasoning": reasoning,
                "model_id": result.model_id,
                "tokens": result.total_tokens,
                "latency_ms": latency_ms,
                "parse_errors": self.action_parser.get_parse_errors(),
            }
        else:
            action = IdleAction(agent_id=agent_id, reason=f"LLM error: {result.error}")
            self._stats["fallback_decisions"] += 1
            
            if self.enable_logging:
                self._logger.log_llm_response(
                    agent_id=agent_id,
                    tick=tick,
                    success=False,
                    latency_ms=latency_ms,
                    tokens=0,
                    error=result.error,
                )
            
            metadata = {
                "success": False,
                "error": result.error,
                "model_id": result.model_id,
                "latency_ms": latency_ms,
            }
        
        return action, metadata

    def record_action_outcome(
        self,
        agent_id,
        tick,
        action,
        success,
        details=None,
    ):
        self.memory_subsystem.record_action(
            agent_id=agent_id,
            tick=tick,
            action_type=action.action_type.name,
            details=details or {},
            success=success,
        )

    def record_message_received(
        self,
        agent_id,
        tick,
        sender_id,
        content,
    ):
        self.memory_subsystem.record_message_received(agent_id, tick, sender_id, content)

    def record_trade_outcome(
        self,
        agent_id,
        tick,
        other_agent,
        offered,
        received,
        success,
    ):
        self.memory_subsystem.record_trade(agent_id, tick, other_agent, offered, received, success)

    def get_stats(self):
        stats = dict(self._stats)
        if stats["total_decisions"] > 0:
            stats["success_rate"] = stats["successful_decisions"] / stats["total_decisions"]
            stats["fallback_rate"] = stats["fallback_decisions"] / stats["total_decisions"]
            stats["avg_latency_ms"] = stats["total_latency_ms"] / stats["total_decisions"]
        else:
            stats["success_rate"] = 0.0
            stats["fallback_rate"] = 0.0
            stats["avg_latency_ms"] = 0.0
        return stats

    def reset_stats(self):
        self._stats = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "fallback_decisions": 0,
            "total_latency_ms": 0.0,
        }
