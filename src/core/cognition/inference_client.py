import asyncio
import os
import time

from openai import OpenAI, AsyncOpenAI

from .model_registry import ModelConfig
from ..logging import get_live_logger


class InferenceResult:
    def __init__(self, success, content, model_id, prompt_tokens=0, completion_tokens=0, total_tokens=0, latency_ms=0.0, error=None, agent_id=None, tick=None):
        self.success = success
        self.content = content
        self.model_id = model_id
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.latency_ms = latency_ms
        self.error = error
        self.agent_id = agent_id
        self.tick = tick

    def to_dict(self):
        return {
            "success": self.success,
            "content": self.content,
            "model_id": self.model_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class InferenceClient:
    def __init__(
        self,
        default_api_key=None,
        default_base_url=None,
        max_retries=3,
        retry_delay=1.0,
        timeout=60.0,
        enable_logging=True,
        live_logger=None,
    ):
        self.default_api_key = default_api_key or os.getenv("API_KEY")
        self.default_base_url = default_base_url or os.getenv("BASE_URL")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.enable_logging = enable_logging
        self._clients = {}
        self._async_clients = {}
        self._logger = live_logger if live_logger else get_live_logger()
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_latency_ms": 0.0,
        }

    def _get_client(self, model_config):
        client_key = f"{model_config.base_url}:{model_config.api_key}"
        if client_key not in self._clients:
            api_key = model_config.api_key or self.default_api_key
            base_url = model_config.base_url or self.default_base_url
            kwargs = {"api_key": api_key, "timeout": self.timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._clients[client_key] = OpenAI(**kwargs)
        return self._clients[client_key]

    def _get_async_client(self, model_config):
        client_key = f"{model_config.base_url}:{model_config.api_key}"
        if client_key not in self._async_clients:
            api_key = model_config.api_key or self.default_api_key
            base_url = model_config.base_url or self.default_base_url
            kwargs = {"api_key": api_key, "timeout": self.timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self._async_clients[client_key] = AsyncOpenAI(**kwargs)
        return self._async_clients[client_key]

    def infer(
        self,
        model_config,
        system_prompt,
        user_prompt,
        temperature=None,
        max_tokens=None,
        agent_id=None,
        tick=None,
    ):
        client = self._get_client(model_config)
        temp = temperature if temperature is not None else model_config.temperature
        tokens = max_tokens if max_tokens is not None else model_config.max_tokens
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self.enable_logging and agent_id:
            prompt_preview = user_prompt[:100].replace('\n', ' ')
            self._logger.log_llm_request(agent_id, tick or 0, model_config.model_name, prompt_preview)
        start_time = time.time()
        last_error = None
        for attempt in range(self.max_retries):
            try:
                self._stats["total_requests"] += 1
                response = client.chat.completions.create(
                    model=model_config.model_name,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                )
                latency_ms = (time.time() - start_time) * 1000
                content = response.choices[0].message.content
                usage = response.usage
                self._stats["successful_requests"] += 1
                self._stats["total_tokens"] += usage.total_tokens if usage else 0
                self._stats["total_latency_ms"] += latency_ms
                result = InferenceResult(
                    True,
                    content,
                    model_config.model_id,
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                    latency_ms=latency_ms,
                    agent_id=agent_id,
                    tick=tick,
                )
                return result
            except Exception as e:
                last_error = str(e)
                if self.enable_logging:
                    self._logger.warning(f"LLM retry {attempt+1}/{self.max_retries}: {last_error}", agent_id=agent_id, tick=tick)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        self._stats["failed_requests"] += 1
        latency_ms = (time.time() - start_time) * 1000
        if self.enable_logging and agent_id:
            self._logger.log_llm_response(agent_id, tick or 0, False, latency_ms, 0, error=last_error)
        return InferenceResult(False, "", model_config.model_id, latency_ms=latency_ms, error=last_error, agent_id=agent_id, tick=tick)

    async def infer_async(
        self,
        model_config,
        system_prompt,
        user_prompt,
        temperature=None,
        max_tokens=None,
        agent_id=None,
        tick=None,
    ):
        client = self._get_async_client(model_config)
        temp = temperature if temperature is not None else model_config.temperature
        tokens = max_tokens if max_tokens is not None else model_config.max_tokens
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self.enable_logging and agent_id:
            prompt_preview = user_prompt[:100].replace('\n', ' ')
            self._logger.log_llm_request(agent_id, tick or 0, model_config.model_name, prompt_preview)
        start_time = time.time()
        last_error = None
        for attempt in range(self.max_retries):
            try:
                self._stats["total_requests"] += 1
                response = await client.chat.completions.create(
                    model=model_config.model_name,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                )
                latency_ms = (time.time() - start_time) * 1000
                content = response.choices[0].message.content
                usage = response.usage
                self._stats["successful_requests"] += 1
                self._stats["total_tokens"] += usage.total_tokens if usage else 0
                self._stats["total_latency_ms"] += latency_ms
                return InferenceResult(
                    True,
                    content,
                    model_config.model_id,
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                    latency_ms=latency_ms,
                    agent_id=agent_id,
                    tick=tick,
                )
            except Exception as e:
                last_error = str(e)
                if self.enable_logging:
                    self._logger.warning(f"LLM async retry {attempt+1}/{self.max_retries}: {last_error}", agent_id=agent_id, tick=tick)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
        self._stats["failed_requests"] += 1
        latency_ms = (time.time() - start_time) * 1000
        if self.enable_logging and agent_id:
            self._logger.log_llm_response(agent_id, tick or 0, False, latency_ms, 0, error=last_error)
        return InferenceResult(False, "", model_config.model_id, latency_ms=latency_ms, error=last_error, agent_id=agent_id, tick=tick)

    async def infer_batch_async(self, requests):
        tasks = []
        for req in requests:
            task = self.infer_async(
                model_config=req["model_config"],
                system_prompt=req["system_prompt"],
                user_prompt=req["user_prompt"],
                temperature=req.get("temperature"),
                max_tokens=req.get("max_tokens"),
            )
            tasks.append(task)
        return await asyncio.gather(*tasks)

    def infer_batch(self, requests):
        return asyncio.run(self.infer_batch_async(requests))

    def get_stats(self):
        stats = dict(self._stats)
        if stats["successful_requests"] > 0:
            stats["avg_latency_ms"] = stats["total_latency_ms"] / stats["successful_requests"]
            stats["avg_tokens_per_request"] = stats["total_tokens"] / stats["successful_requests"]
        else:
            stats["avg_latency_ms"] = 0.0
            stats["avg_tokens_per_request"] = 0.0
        return stats

    def reset_stats(self):
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_latency_ms": 0.0,
        }
