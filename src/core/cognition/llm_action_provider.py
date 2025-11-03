import asyncio
import time

from ..simulation import AgentActionProvider
from ..actions import BaseAction, IdleAction
from .cognition_interface import CognitionInterface
from .observation_builder import ObservationBuilder
from .model_registry import ModelRegistry
from .inference_client import InferenceClient
from .action_parser import ActionOutputParser
from .memory import MemorySubsystem
from .role_initializer import RoleInitializer
from .rate_limiter import RateLimiter


class LLMActionProvider(AgentActionProvider):
    def __init__(
        self,
        agent_manager,
        location_graph,
        message_bus,
        action_interpreter,
        model_registry,
        inference_client,
        memory_subsystem=None,
        role_initializer=None,
        batch_inference=False,
        live_logger=None,
        rate_limiter=None,
        inter_agent_delay=0.5,
    ):
        self.agent_manager = agent_manager
        self.location_graph = location_graph
        self.message_bus = message_bus
        self.action_interpreter = action_interpreter
        self.model_registry = model_registry
        self.inference_client = inference_client
        self.memory_subsystem = memory_subsystem or MemorySubsystem()
        self.role_initializer = role_initializer or RoleInitializer()
        self.batch_inference = batch_inference
        self.live_logger = live_logger
        self.inter_agent_delay = inter_agent_delay  # Delay between agent requests
        
        # Rate limiter for managing LLM request frequency
        self.rate_limiter = rate_limiter or RateLimiter(
            base_cooldown=5.0,
            max_cooldown=120.0,
            min_request_interval=0.5,
            global_min_interval=0.2,
            enable_mandatory_rest=True,
            mandatory_rest_interval=10,
        )

        self.observation_builder = ObservationBuilder(
            agent_manager=agent_manager,
            location_graph=location_graph,
            message_bus=message_bus,
            action_interpreter=action_interpreter,
        )

        self.action_parser = ActionOutputParser(strict_validation=True)

        self.cognition = CognitionInterface(
            observation_builder=self.observation_builder,
            model_registry=model_registry,
            inference_client=inference_client,
            memory_subsystem=self.memory_subsystem,
            action_parser=self.action_parser,
            live_logger=live_logger,
        )

        self._agent_types = {}
        self._agent_roles = {}
        self._action_metadata = {}
        self._initialized_agents = set()
        self._current_tick = 0

    def initialize_agent(
        self,
        agent_id,
        archetype=None,
        persona=None,
        goals=None,
    ):
        if archetype:
            role_data = self.role_initializer.initialize_agent(
                agent_id=agent_id,
                archetype=archetype,
            )
            self.cognition.set_persona(agent_id, role_data["persona"])
            self.cognition.set_goals(agent_id, role_data["goals"])
            self._agent_types[agent_id] = role_data["archetype"]
        else:
            if persona:
                self.cognition.set_persona(agent_id, persona)
            if goals:
                self.cognition.set_goals(agent_id, goals)

        self._initialized_agents.add(agent_id)

    def initialize_all_agents(
        self,
        archetype_distribution=None,
    ):
        agent_ids = self.agent_manager.list_agent_ids()

        for i, agent_id in enumerate(agent_ids):
            if agent_id in self._initialized_agents:
                continue

            role_data = self.role_initializer.initialize_agent(
                agent_id=agent_id,
                archetype_weights=archetype_distribution,
            )

            self.cognition.set_persona(agent_id, role_data["persona"])
            self.cognition.set_goals(agent_id, role_data["goals"])
            self._agent_types[agent_id] = role_data["archetype"]
            self._initialized_agents.add(agent_id)

    def set_agent_role(self, agent_id, role):
        self._agent_roles[agent_id] = role

    def set_tick(self, tick):
        self._current_tick = tick
        self.rate_limiter.set_tick(tick)

    def is_night_mode(self):
        return self.rate_limiter.is_night_mode()

    def get_action(self, agent_id, tick):
        if agent_id not in self._initialized_agents:
            self.initialize_agent(agent_id)
        
        self.set_tick(tick)
        
        can_request, reason = self.rate_limiter.can_make_request(agent_id)
        if not can_request:
            if self.live_logger:
                self.live_logger.info(f"Agent {agent_id} rate limited: {reason}", agent_id=agent_id, tick=tick)
            
            # this is NOT an error (intentional throttling)
            action = IdleAction(agent_id=agent_id, reason=f"Resting: {reason}")
            self._action_metadata[agent_id] = {
                "success": True,  # This is successful behavior, not an error
                "rate_limited": True,
                "reason": reason,
                "is_rest": True,
            }
            return action
        
        self.rate_limiter.record_request_start(agent_id)
        
        if self.inter_agent_delay > 0:
            time.sleep(self.inter_agent_delay)

        action, metadata = self.cognition.choose_action(
            agent_id=agent_id,
            tick=tick,
            agent_type=self._agent_types.get(agent_id),
            role=self._agent_roles.get(agent_id),
        )
        
        if metadata.get("success", False):
            self.rate_limiter.record_request_success(agent_id)
        else:
            error_msg = metadata.get("error", "")
            cooldown = self.rate_limiter.record_request_error(agent_id, error_msg)
            if self.live_logger:
                self.live_logger.warning(
                    f"LLM error for {agent_id}, cooldown {cooldown:.1f}s: {error_msg}",
                    agent_id=agent_id,
                    tick=tick
                )
            metadata["llm_error"] = True
            metadata["cooldown_applied"] = cooldown

        self._action_metadata[agent_id] = metadata

        return action

    def get_actions_batch(self, agent_ids, tick):
        self.set_tick(tick)
        
        for agent_id in agent_ids:
            if agent_id not in self._initialized_agents:
                self.initialize_agent(agent_id)

        if not self.batch_inference:
            return {aid: self.get_action(aid, tick) for aid in agent_ids}

        return self._get_actions_batch_async(agent_ids, tick)

    def _get_actions_batch_async(
        self,
        agent_ids,
        tick,
    ):
        from .prompt_templates import PromptTemplates

        requests = []
        observations = {}

        for agent_id in agent_ids:
            observation = self.observation_builder.build_observation(agent_id, tick)
            observations[agent_id] = observation

            if "error" in observation:
                continue

            memory_summary = self.memory_subsystem.get_memory_summary(agent_id)
            persona = self.cognition.get_persona(agent_id)
            goals = self.cognition.get_goals(agent_id)

            system_prompt = PromptTemplates.build_system_prompt(
                persona=persona,
                goals=goals,
                memory_summary=memory_summary,
            )

            observation_text = self.observation_builder.observation_to_text(observation)
            available_actions_text = PromptTemplates.format_available_actions(
                observation.get("available_actions", [])
            )

            user_prompt = PromptTemplates.build_action_prompt(
                observation=observation_text,
                available_actions=available_actions_text,
            )

            model_config = self.model_registry.get_model_for_agent(
                agent_id=agent_id,
                agent_type=self._agent_types.get(agent_id),
                role=self._agent_roles.get(agent_id),
            )

            requests.append({
                "agent_id": agent_id,
                "model_config": model_config,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            })

        if not requests:
            return {aid: IdleAction(agent_id=aid, reason="No valid observation") for aid in agent_ids}

        results = asyncio.run(self._run_batch_inference(requests))

        actions = {}
        for i, req in enumerate(requests):
            agent_id = req["agent_id"]
            result = results[i]

            if result.success:
                action, reasoning = self.action_parser.parse(
                    llm_output=result.content,
                    agent_id=agent_id,
                    observation=observations[agent_id],
                )
                self._action_metadata[agent_id] = {
                    "success": True,
                    "reasoning": reasoning,
                    "model_id": result.model_id,
                    "tokens": result.total_tokens,
                    "latency_ms": result.latency_ms,
                }
            else:
                action = IdleAction(agent_id=agent_id, reason=f"LLM error: {result.error}")
                self._action_metadata[agent_id] = {
                    "success": False,
                    "error": result.error,
                }

            actions[agent_id] = action

        for agent_id in agent_ids:
            if agent_id not in actions:
                actions[agent_id] = IdleAction(agent_id=agent_id, reason="Batch processing skipped")

        return actions

    async def _run_batch_inference(self, requests):
        inference_requests = [
            {
                "model_config": req["model_config"],
                "system_prompt": req["system_prompt"],
                "user_prompt": req["user_prompt"],
            }
            for req in requests
        ]
        return await self.inference_client.infer_batch_async(inference_requests)

    def record_action_outcome(
        self,
        agent_id,
        tick,
        action,
        success,
        details=None,
    ):
        self.cognition.record_action_outcome(agent_id, tick, action, success, details)

    def get_last_action_metadata(self, agent_id):
        return self._action_metadata.get(agent_id)

    def get_cognition_stats(self):
        return self.cognition.get_stats()

    def get_inference_stats(self):
        return self.inference_client.get_stats()

    def get_rate_limiter_status(self):
        return self.rate_limiter.get_global_status()

    def get_agent_rate_status(self, agent_id):
        return self.rate_limiter.get_agent_status(agent_id)

    def trigger_night_mode(self, duration_ticks=5):
        self.rate_limiter.trigger_night_mode(duration_ticks)

    def reset_stats(self):
        self.cognition.reset_stats()
        self.inference_client.reset_stats()
        self.rate_limiter.reset_all()
