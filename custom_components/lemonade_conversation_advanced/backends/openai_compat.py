"""OpenAI-compatible backend for Lemonade Server."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam
from openai.types.chat.chat_completion import ChatCompletion

from ..client import LemonadeClient
from ..const import (
    DEFAULT_BACKEND,
    DEFAULT_CTX_SIZE,
    DEFAULT_GPU_LAYERS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    SUPPORTED_BACKENDS,
    SUPPORTED_RECIPES,
)
from ..exceptions import LemonadeBackendUnavailableError, LemonadeError

_LOGGER = logging.getLogger(__name__)


class LemonadeOpenAICompatBackend:
    """OpenAI-compatible backend for Lemonade Server."""

    def __init__(self, client: LemonadeClient):
        """Initialize the backend."""
        self.client = client
        self._attr_supports_streaming = True
        self._attr_supports_function_calling = True
        self._attr_supports_vision = True
        self._attr_supports_structured_output = True

    @property
    def name(self) -> str:
        """Return backend name."""
        return "openai_compat"

    @property
    def supports_streaming(self) -> bool:
        """Return whether streaming is supported."""
        return self._attr_supports_streaming

    @property
    def supports_function_calling(self) -> bool:
        """Return whether function calling is supported."""
        return self._attr_supports_function_calling

    @property
    def supports_vision(self) -> bool:
        """Return whether vision is supported."""
        return self._attr_supports_vision

    @property
    def supports_structured_output(self) -> bool:
        """Return whether structured output is supported."""
        return self._attr_supports_structured_output

    async def validate_connection(self) -> bool:
        """Validate connection to Lemonade Server."""
        try:
            await self.client.health_check()
            return True
        except LemonadeError:
            return False

    async def list_models(self, show_all: bool = False) -> List[Dict[str, Any]]:
        """List available models."""
        models = await self.client.list_models(show_all=show_all)
        return [
            {
                "id": m.id,
                "object": m.object,
                "owned_by": m.owned_by,
                "checkpoint": m.checkpoint,
                "recipe": m.recipe,
                "size": m.size,
                "downloaded": m.downloaded,
                "labels": m.labels,
                "max_context_window": m.max_context_window,
            }
            for m in models
        ]

    async def pull_model(
        self,
        model_name: str,
        checkpoint: Optional[str] = None,
        recipe: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pull/download a model."""
        return await self.client.pull_model(
            model_name=model_name,
            checkpoint=checkpoint,
            recipe=recipe,
        )

    async def load_model(
        self,
        model_name: str,
        ctx_size: Optional[int] = None,
        gpu_layers: Optional[int] = None,
        backend: Optional[str] = None,
        recipe_options: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Load a model into memory."""
        return await self.client.load_model(
            model_name=model_name,
            ctx_size=ctx_size or DEFAULT_CTX_SIZE,
            gpu_layers=gpu_layers if gpu_layers is not None else DEFAULT_GPU_LAYERS,
            backend=backend or DEFAULT_BACKEND,
            recipe_options=recipe_options,
        )

    async def unload_model(self, model_name: str) -> Dict[str, Any]:
        """Unload a model from memory."""
        return await self.client.unload_model(model_name)

    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        sys_info = await self.client.get_system_info()
        return {
            "hardware": sys_info.hardware,
            "backends": sys_info.backends,
            "loaded_models": [
                {
                    "model_name": m.model_name,
                    "backend": m.backend,
                    "ctx_size": m.ctx_size,
                    "gpu_layers": m.gpu_layers,
                    "memory_usage_mb": m.memory_usage_mb,
                    "device": m.device,
                }
                for m in sys_info.loaded_models
            ],
            "max_loaded_models": sys_info.max_loaded_models,
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = await self.client.get_stats()
        return {
            "model": stats.model,
            "prompt_tokens": stats.prompt_tokens,
            "completion_tokens": stats.completion_tokens,
            "total_tokens": stats.total_tokens,
            "prompt_eval_rate": stats.prompt_eval_rate,
            "eval_rate": stats.eval_rate,
            "total_time_ms": stats.total_time_ms,
            "load_time_ms": stats.load_time_ms,
        }

    async def chat_completion(
        self,
        model: str,
        messages: List[ChatCompletionMessageParam],
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = 0.9,
        top_k: int = 40,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
        timeout: int = 30,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ChatCompletion | AsyncIterator[ChatCompletionChunk]:
        """Get chat completion from Lemonade Server."""
        extra_kwargs = {"timeout": timeout}
        if top_p != 1.0:
            extra_kwargs["top_p"] = top_p
        if top_k:
            extra_kwargs["top_k"] = top_k
        extra_kwargs.update(kwargs)

        if stream:
            return self._stream_chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                **extra_kwargs,
            )
        return await self.client.openai_chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            tools=tools,
            tool_choice=tool_choice,
            **extra_kwargs,
        )

    async def _stream_chat_completion(
        self,
        model: str,
        messages: List[ChatCompletionMessageParam],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Stream chat completion using OpenAI client."""
        stream = await self.client.openai_stream_chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )
        async for chunk in stream:
            yield chunk

    async def health_check(self) -> Dict[str, Any]:
        """Health check."""
        return await self.client.health_check()

    @classmethod
    def get_supported_backends(cls) -> List[str]:
        """Get list of supported backends."""
        return SUPPORTED_BACKENDS.copy()

    @classmethod
    def get_supported_recipes(cls) -> List[str]:
        """Get list of supported recipes."""
        return SUPPORTED_RECIPES.copy()


BACKEND_REGISTRY = {
    "openai_compat": LemonadeOpenAICompatBackend,
}


def get_backend_class(backend_name: str) -> type:
    """Get backend class by name."""
    if backend_name not in BACKEND_REGISTRY:
        raise LemonadeBackendUnavailableError(backend_name)
    return BACKEND_REGISTRY[backend_name]


def register_backend(name: str, backend_class: type) -> None:
    """Register a new backend."""
    BACKEND_REGISTRY[name] = backend_class
