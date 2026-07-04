"""Lemonade Client - HTTP client for Lemonade Server API."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

import aiohttp
from openai import AsyncOpenAI

from .const import (
    CONNECT_TIMEOUT,
    DEFAULT_TIMEOUT,
    LEMONADE_API_PREFIX,
    LEMONADE_CHAT_COMPLETIONS_ENDPOINT,
    LEMONADE_HEALTH_ENDPOINT,
    LEMONADE_LOAD_ENDPOINT,
    LEMONADE_MODELS_ENDPOINT,
    LEMONADE_PULL_ENDPOINT,
    LEMONADE_STATS_ENDPOINT,
    LEMONADE_SYSTEM_INFO_ENDPOINT,
    LEMONADE_UNLOAD_ENDPOINT,
)
from .exceptions import (
    LemonadeAPIError,
    LemonadeBackendUnavailableError,
    LemonadeConnectionError,
    LemonadeError,
    LemonadeInvalidRequestError,
    LemonadeModelNotFoundError,
    LemonadeModelNotLoadedError,
    LemonadeNPUBusyError,
    LemonadeOutOfMemoryError,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a model."""

    id: str
    object: str = "model"
    owned_by: str = "user"
    checkpoint: Optional[str] = None
    recipe: Optional[str] = None
    size: Optional[int] = None
    downloaded: bool = False
    labels: Optional[List[str]] = None
    max_context_window: Optional[int] = None


@dataclass
class LoadedModelInfo:
    """Information about a loaded model."""

    model_name: str
    backend: str
    ctx_size: int
    gpu_layers: int
    memory_usage_mb: int
    device: str


@dataclass
class SystemInfo:
    """System information from Lemonade Server."""

    hardware: Dict[str, Any]
    backends: Dict[str, Any]
    loaded_models: List[LoadedModelInfo]
    max_loaded_models: Dict[str, int]


@dataclass
class Stats:
    """Performance statistics from last request."""

    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_eval_rate: float
    eval_rate: float
    total_time_ms: int
    load_time_ms: int


class LemonadeClient:
    """HTTP client for Lemonade Server API."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """Initialize the client."""
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout, connect=CONNECT_TIMEOUT)
        self._session: Optional[aiohttp.ClientSession] = None
        self._openai_client = AsyncOpenAI(
            base_url=f"{base_url.rstrip('/')}{LEMONADE_API_PREFIX}",
            api_key=api_key or "not-needed",
            timeout=DEFAULT_TIMEOUT,
        )

    @property
    def openai_client(self) -> AsyncOpenAI:
        """Return AsyncOpenAI client."""
        return self._openai_client

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(headers=headers, timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close all sessions."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._openai_client:
            await self._openai_client.close()

    def _handle_error(self, status: int, data: dict) -> LemonadeError:
        """Convert API error to LemonadeError."""
        error_data = data.get("error", {})
        message = error_data.get("message", "Unknown error")
        model_name = error_data.get("model_name") or error_data.get("model")

        if status == 404:
            if "model" in message.lower() and model_name:
                return LemonadeModelNotFoundError(model_name)
            return LemonadeAPIError(message, status, data)
        if status == 400:
            if "not loaded" in message.lower() and model_name:
                return LemonadeModelNotLoadedError(model_name)
            if "npu" in message.lower() and "busy" in message.lower():
                return LemonadeNPUBusyError(model_name)
            if "out of memory" in message.lower() or "oom" in message.lower():
                return LemonadeOutOfMemoryError()
            if "backend" in message.lower():
                backend = error_data.get("backend", message)
                return LemonadeBackendUnavailableError(backend)
            return LemonadeInvalidRequestError(message)
        return LemonadeAPIError(message, status, data)

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Make HTTP request to Lemonade Server."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with session.request(method, url, json=json_data, params=params) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = {"error": {"message": await resp.text()}}

                if resp.status >= 400:
                    raise self._handle_error(resp.status, data)

                return data
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error to Lemonade Server: %s", err)
            raise LemonadeConnectionError(f"Failed to connect to Lemonade Server: {err}") from err
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout connecting to Lemonade Server: %s", err)
            raise LemonadeConnectionError("Connection timeout") from err

    async def health_check(self) -> dict:
        """Check server health."""
        return await self._request("GET", LEMONADE_HEALTH_ENDPOINT)

    async def get_system_info(self) -> SystemInfo:
        """Get system information."""
        data = await self._request("GET", LEMONADE_SYSTEM_INFO_ENDPOINT)
        loaded_models = [
            LoadedModelInfo(
                model_name=model.get("model_name", ""),
                backend=model.get("backend", ""),
                ctx_size=model.get("ctx_size", 0),
                gpu_layers=model.get("gpu_layers", 0),
                memory_usage_mb=model.get("memory_usage_mb", 0),
                device=model.get("device", ""),
            )
            for model in data.get("loaded_models", [])
        ]
        return SystemInfo(
            hardware=data.get("hardware", {}),
            backends=data.get("backends", {}),
            loaded_models=loaded_models,
            max_loaded_models=data.get("max_loaded_models", {}),
        )

    async def get_stats(self) -> Stats:
        """Get performance statistics."""
        data = await self._request("GET", LEMONADE_STATS_ENDPOINT)
        last_req = data.get("last_request", {})
        return Stats(
            model=last_req.get("model", ""),
            prompt_tokens=last_req.get("prompt_tokens", 0),
            completion_tokens=last_req.get("completion_tokens", 0),
            total_tokens=last_req.get("total_tokens", 0),
            prompt_eval_rate=last_req.get("prompt_eval_rate", 0.0),
            eval_rate=last_req.get("eval_rate", 0.0),
            total_time_ms=last_req.get("total_time_ms", 0),
            load_time_ms=last_req.get("load_time_ms", 0),
        )

    async def list_models(self, show_all: bool = False) -> List[ModelInfo]:
        """List available models."""
        params = {"show_all": "true"} if show_all else {}
        data = await self._request("GET", LEMONADE_MODELS_ENDPOINT, params=params)
        return [
            ModelInfo(
                id=model.get("id", ""),
                object=model.get("object", "model"),
                owned_by=model.get("owned_by", "user"),
                checkpoint=model.get("checkpoint"),
                recipe=model.get("recipe"),
                size=model.get("size"),
                downloaded=model.get("downloaded", False),
                labels=model.get("labels"),
                max_context_window=model.get("max_context_window"),
            )
            for model in data.get("data", [])
        ]

    async def pull_model(
        self,
        model_name: str,
        checkpoint: Optional[str] = None,
        recipe: Optional[str] = None,
    ) -> dict:
        """Pull/download a model."""
        payload = {"model_name": model_name}
        if checkpoint:
            payload["checkpoint"] = checkpoint
        if recipe:
            payload["recipe"] = recipe
        return await self._request("POST", LEMONADE_PULL_ENDPOINT, json_data=payload)

    async def load_model(
        self,
        model_name: str,
        ctx_size: Optional[int] = None,
        gpu_layers: Optional[int] = None,
        backend: Optional[str] = None,
        recipe_options: Optional[dict] = None,
    ) -> dict:
        """Load a model into memory."""
        payload = {"model_name": model_name}
        if ctx_size:
            payload["ctx_size"] = ctx_size
        if gpu_layers is not None:
            payload["gpu_layers"] = gpu_layers
        if backend:
            payload["backend"] = backend
        if recipe_options:
            payload["recipe_options"] = recipe_options
        return await self._request("POST", LEMONADE_LOAD_ENDPOINT, json_data=payload)

    async def unload_model(self, model_name: str) -> dict:
        """Unload a model from memory."""
        return await self._request(
            "POST", LEMONADE_UNLOAD_ENDPOINT, json_data={"model_name": model_name}
        )

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> dict | AsyncIterator[dict]:
        """Get chat completion from Lemonade Server."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        if stream:
            return self._stream_chat_completion(payload)
        return await self._request("POST", LEMONADE_CHAT_COMPLETIONS_ENDPOINT, json_data=payload)

    async def _stream_chat_completion(self, payload: dict) -> AsyncIterator[dict]:
        """Stream chat completion via SSE."""
        session = await self._get_session()
        url = f"{self.base_url}{LEMONADE_CHAT_COMPLETIONS_ENDPOINT}"
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status >= 400:
                    data = await resp.json()
                    raise self._handle_error(resp.status, data)
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            yield json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
        except aiohttp.ClientError as err:
            _LOGGER.error("Streaming error: %s", err)
            raise LemonadeConnectionError(f"Streaming failed: {err}") from err

    async def openai_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ):
        """Use AsyncOpenAI client for chat completion."""
        try:
            return await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs,
            )
        except TypeError as err:
            if "extra_body" in str(err):
                kwargs.pop("extra_body", None)
                return await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    tools=tools,
                    tool_choice=tool_choice,
                    **kwargs,
                )
            raise

    async def openai_stream_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ):
        """Stream chat completion using OpenAI client."""
        try:
            stream = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs,
            )
        except TypeError as err:
            if "extra_body" in str(err):
                kwargs.pop("extra_body", None)
                stream = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    tools=tools,
                    tool_choice=tool_choice,
                    **kwargs,
                )
            else:
                raise
        async for chunk in stream:
            yield chunk
