# Lemonade Assist - Código Fuente Completo

# Lemonade Assist - Integración Custom para Home Assistant
Este documento contiene el código fuente completo de la integración `custom_components/lemonade_assist/`.

Cada página corresponde a un archivo de la integración, listo para copiar directamente al repositorio.
## Estructura de archivos

```plain
custom_components/lemonade_assist/
├── manifest.json
├── __init__.py
├── const.py
├── api.py
├── coordinator.py
├── entity.py
├── conversation.py
├── ai_task.py
├── sensor.py
├── config_flow.py
├── services.py
├── services.yaml
├── llm.py
├── strings.json
└── translations/
    └── en.json
```

## Arquitectura
*   **Patrón subentries** (Ollama 2025.7): un config entry para el servidor, subentries para cada agente
*   **ChatLog + streaming**: `_attr_supports_streaming = True` con SSE fluido
*   **Function calling OpenAI-compatible**: loop de tool calls (max 10 iteraciones)
*   **Custom LLM API**: tools Lemonade-specific para gestión de modelos desde la conversación
*   **13 servicios**: gestión total del servidor
*   **10 sensores**: hardware en tiempo real via DataUpdateCoordinator
*   **Soporte RAG/MCP**: flags preparados para extensión

# manifest.json

```json
{
  "domain": "lemonade_assist",
  "name": "Lemonade Assist",
  "codeowners": ["@nemesis-group"],
  "config_flow": true,
  "dependencies": ["conversation", "ai_task"],
  "documentation": "https://github.com/nemesis-group/lemonade-assist",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/nemesis-group/lemonade-assist/issues",
  "requirements": ["aiohttp>=3.9.0"],
  "version": "1.0.0",
  "integration_type": "service"
}
```

# const.py

```python
"""Constants for the Lemonade Assist integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "lemonade_assist"

# Config keys
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_API_KEY: Final = "api_key"
CONF_MODEL: Final = "model"
CONF_PROMPT: Final = "prompt"
CONF_TEMPERATURE: Final = "temperature"
CONF_TOP_P: Final = "top_p"
CONF_MAX_TOKENS: Final = "max_tokens"
CONF_CONTEXT_SIZE: Final = "context_size"
CONF_MAX_HISTORY: Final = "max_history"
CONF_BACKEND: Final = "backend"
CONF_KEEP_ALIVE: Final = "keep_alive"
CONF_THINK_ENABLED: Final = "think_enabled"
CONF_STRIP_THINK_TAGS: Final = "strip_think_tags"
CONF_RAG_ENABLED: Final = "rag_enabled"
CONF_MCP_ENABLED: Final = "mcp_enabled"

# Defaults
DEFAULT_HOST: Final = "localhost"
DEFAULT_PORT: Final = 13305
DEFAULT_TEMPERATURE: Final = 0.7
DEFAULT_TOP_P: Final = 0.9
DEFAULT_MAX_TOKENS: Final = 2048
DEFAULT_CONTEXT_SIZE: Final = 8192
DEFAULT_MAX_HISTORY: Final = 20
DEFAULT_KEEP_ALIVE: Final = True
DEFAULT_THINK_ENABLED: Final = False
DEFAULT_STRIP_THINK_TAGS: Final = True
DEFAULT_RAG_ENABLED: Final = False
DEFAULT_MCP_ENABLED: Final = False

DEFAULT_PROMPT: Final = """You are a helpful AI assistant integrated with Home Assistant.
You help users control their smart home devices and answer questions.
When controlling devices, use the available tools/functions.
Be concise and helpful. Respond in the user's language."""

DEFAULT_AI_TASK_PROMPT: Final = """You are an AI assistant performing a specific task.
Follow the instructions precisely and provide structured output when requested."""

# Backends
BACKENDS: Final = ["llamacpp", "ryzenai", "vllm", "fastflowlm"]

# Subentry types
SUBENTRY_CONVERSATION: Final = "conversation"
SUBENTRY_AI_TASK: Final = "ai_task"

# Coordinator
SCAN_INTERVAL: Final = 30  # seconds
HEALTH_SCAN_INTERVAL: Final = 10  # seconds

# Services
SERVICE_LOAD_MODEL: Final = "load_model"
SERVICE_UNLOAD_MODEL: Final = "unload_model"
SERVICE_PULL_MODEL: Final = "pull_model"
SERVICE_DELETE_MODEL: Final = "delete_model"
SERVICE_LIST_MODELS: Final = "list_models"
SERVICE_CLEAR_CONVERSATION: Final = "clear_conversation"
SERVICE_SET_CONTEXT_SIZE: Final = "set_context_size"
SERVICE_GET_HEALTH: Final = "get_health"
SERVICE_GET_STATS: Final = "get_stats"
SERVICE_GET_SYSTEM_INFO: Final = "get_system_info"
SERVICE_RELOAD_MODEL: Final = "reload_model"
SERVICE_PIN_MODEL: Final = "pin_model"
SERVICE_GENERATE_CONTENT: Final = "generate_content"

# Sensor keys
SENSOR_HEALTH: Final = "health"
SENSOR_LOADED_MODEL: Final = "loaded_model"
SENSOR_VRAM_USED: Final = "vram_used"
SENSOR_VRAM_TOTAL: Final = "vram_total"
SENSOR_GPU_USAGE: Final = "gpu_usage"
SENSOR_NPU_STATUS: Final = "npu_status"
SENSOR_BACKEND: Final = "backend"
SENSOR_CONTEXT_SIZE: Final = "context_size"
SENSOR_TOKENS_PER_SECOND: Final = "tokens_per_second"

# Events
EVENT_MODEL_LOADED: Final = f"{DOMAIN}_model_loaded"
EVENT_MODEL_UNLOADED: Final = f"{DOMAIN}_model_unloaded"
EVENT_HEALTH_CHANGED: Final = f"{DOMAIN}_health_changed"

# Max tool call iterations
MAX_TOOL_ITERATIONS: Final = 10
```

# api.py

```python
"""API client for Lemonade Server."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp

from .const import DEFAULT_HOST, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


class LemonadeAPIError(Exception):
    """Base exception for Lemonade API errors."""

    def __init__(self, message: str, status: int | None = None) -> None:
        """Initialize."""
        super().__init__(message)
        self.status = status


class LemonadeConnectionError(LemonadeAPIError):
    """Connection error."""


class LemonadeAuthError(LemonadeAPIError):
    """Authentication error."""


class LemonadeServerClient:
    """Client for communicating with Lemonade Server."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        api_key: str | None = None,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 120,
    ) -> None:
        """Initialize the client."""
        self._host = host
        self._port = port
        self._api_key = api_key
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._base_url = f"http://{host}:{port}"
        self._owns_session = session is None

    @property
    def base_url(self) -> str:
        """Return the base URL."""
        return self._base_url

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
            self._owns_session = True
        return self._session

    def _headers(self) -> dict[str, str]:
        """Get request headers."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def close(self) -> None:
        """Close the session."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a request to the server."""
        session = await self._get_session()
        url = f"{self._base_url}{endpoint}"

        try:
            async with session.request(
                method,
                url,
                json=data,
                params=params,
                headers=self._headers(),
            ) as response:
                if response.status == 401:
                    raise LemonadeAuthError("Authentication failed", status=401)
                if response.status >= 400:
                    text = await response.text()
                    raise LemonadeAPIError(
                        f"API error {response.status}: {text}",
                        status=response.status,
                    )
                return await response.json()
        except aiohttp.ClientConnectorError as err:
            raise LemonadeConnectionError(
                f"Cannot connect to Lemonade Server at {url}: {err}"
            ) from err
        except asyncio.TimeoutError as err:
            raise LemonadeConnectionError(
                f"Timeout connecting to Lemonade Server at {url}"
            ) from err

    # --- OpenAI-Compatible Endpoints ---

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a chat completion request (non-streaming)."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        payload.update(kwargs)

        return await self._request("POST", "/v1/chat/completions", data=payload)

    async def chat_completion_stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Send a streaming chat completion request."""
        session = await self._get_session()
        url = f"{self._base_url}/v1/chat/completions"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        payload.update(kwargs)

        try:
            async with session.post(
                url,
                json=payload,
                headers=self._headers(),
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise LemonadeAPIError(
                        f"Stream error {response.status}: {text}",
                        status=response.status,
                    )

                async for line in response.content:
                    decoded = line.decode("utf-8").strip()
                    if not decoded or not decoded.startswith("data:"):
                        continue
                    data_str = decoded[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
        except aiohttp.ClientConnectorError as err:
            raise LemonadeConnectionError(
                f"Stream connection failed: {err}"
            ) from err

    async def get_models(self) -> dict[str, Any]:
        """Get available models (OpenAI-compatible)."""
        return await self._request("GET", "/v1/models")

    async def get_embeddings(
        self, input_text: str | list[str], model: str
    ) -> dict[str, Any]:
        """Get text embeddings."""
        payload = {"input": input_text, "model": model}
        return await self._request("POST", "/v1/embeddings", data=payload)

    # --- Lemonade-Specific Endpoints ---

    async def health(self) -> dict[str, Any]:
        """Check server health status."""
        return await self._request("GET", "/v1/health")

    async def live(self) -> bool:
        """Check server liveness."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self._base_url}/live",
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                return response.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return await self._request("GET", "/v1/stats")

    async def system_stats(self) -> dict[str, Any]:
        """Get current host resource usage."""
        return await self._request("GET", "/v1/system-stats")

    async def system_info(self) -> dict[str, Any]:
        """Get system information and device enumeration."""
        return await self._request("GET", "/v1/system-info")

    async def load_model(
        self,
        model_name: str,
        pinned: bool = False,
        ctx_size: int | None = None,
        backend: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Load a model into memory."""
        payload: dict[str, Any] = {"model_name": model_name, "pinned": pinned}
        if ctx_size:
            payload["ctx_size"] = ctx_size
        if backend:
            payload["llamacpp_backend"] = backend
        payload.update(kwargs)
        return await self._request("POST", "/v1/load", data=payload)

    async def unload_model(self, model_name: str) -> dict[str, Any]:
        """Unload a model from memory."""
        return await self._request("POST", "/v1/unload", data={"model_name": model_name})

    async def pull_model(
        self,
        model_name: str,
        checkpoint: str | None = None,
        recipe: str | None = None,
        stream: bool = False,
    ) -> dict[str, Any] | AsyncGenerator[dict[str, Any], None]:
        """Pull/download a model."""
        payload: dict[str, Any] = {"model_name": model_name, "stream": stream}
        if checkpoint:
            payload["checkpoint"] = checkpoint
        if recipe:
            payload["recipe"] = recipe

        if stream:
            return self._pull_model_stream(payload)
        return await self._request("POST", "/v1/pull", data=payload)

    async def _pull_model_stream(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream model pull progress."""
        session = await self._get_session()
        url = f"{self._base_url}/v1/pull"

        async with session.post(
            url, json=payload, headers=self._headers()
        ) as response:
            async for line in response.content:
                decoded = line.decode("utf-8").strip()
                if not decoded:
                    continue
                if decoded.startswith("data:"):
                    data_str = decoded[5:].strip()
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

    async def delete_model(self, model_name: str) -> dict[str, Any]:
        """Delete a model."""
        return await self._request(
            "POST", "/v1/delete", data={"model_name": model_name}
        )

    async def get_downloads(self) -> list[dict[str, Any]]:
        """List active download jobs."""
        result = await self._request("GET", "/v1/downloads")
        return result if isinstance(result, list) else []

    async def control_download(
        self, download_id: str, action: str
    ) -> dict[str, Any]:
        """Control a download job (pause, cancel, remove)."""
        return await self._request(
            "POST",
            "/v1/downloads/control",
            data={"id": download_id, "action": action},
        )

    async def get_pull_variants(self, checkpoint: str) -> dict[str, Any]:
        """Get available GGUF variants for a checkpoint."""
        return await self._request(
            "GET", "/v1/pull/variants", params={"checkpoint": checkpoint}
        )

    # --- Convenience Methods ---

    async def validate_connection(self) -> bool:
        """Validate connection to the server."""
        try:
            health = await self.health()
            return health is not None
        except LemonadeAPIError:
            return False

    async def get_loaded_models(self) -> list[str]:
        """Get list of currently loaded model names."""
        try:
            health = await self.health()
            models = health.get("models_loaded", [])
            if isinstance(models, list):
                return models
            return [models] if models else []
        except LemonadeAPIError:
            return []

    async def get_available_model_names(self) -> list[str]:
        """Get list of available model names."""
        try:
            result = await self.get_models()
            data = result.get("data", [])
            return [m.get("id", "") for m in data if m.get("id")]
        except LemonadeAPIError:
            return []

    @staticmethod
    def strip_think_tags(text: str) -> str:
        """Strip <think>...</think> tags from response text."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
```

# coordinator.py

```python
"""DataUpdateCoordinator for Lemonade Assist."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LemonadeAPIError, LemonadeServerClient
from .const import DOMAIN, HEALTH_SCAN_INTERVAL, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LemonadeHealthCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for health and lightweight status polling."""

    def __init__(self, hass: HomeAssistant, client: LemonadeServerClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_health",
            update_interval=timedelta(seconds=HEALTH_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch health data from Lemonade Server."""
        try:
            health = await self.client.health()
            is_live = await self.client.live()
            return {
                "healthy": is_live,
                "health": health,
                "models_loaded": health.get("models_loaded", []),
                "status": health.get("status", "unknown"),
            }
        except LemonadeAPIError as err:
            raise UpdateFailed(f"Error fetching health: {err}") from err


class LemonadeStatsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for system stats (VRAM, GPU, etc.)."""

    def __init__(self, hass: HomeAssistant, client: LemonadeServerClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_stats",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch system stats from Lemonade Server."""
        try:
            system_stats = await self.client.system_stats()
            stats = await self.client.stats()
            system_info = await self.client.system_info()

            # Extract GPU/VRAM info
            gpu_info = system_info.get("gpu", {})
            vram_info = system_stats.get("vram", system_stats.get("gpu_memory", {}))

            return {
                "system_stats": system_stats,
                "stats": stats,
                "system_info": system_info,
                "vram_used_mb": vram_info.get("used_mb", 0),
                "vram_total_mb": vram_info.get("total_mb", 0),
                "vram_percent": vram_info.get("percent", 0),
                "gpu_usage_percent": system_stats.get("gpu_utilization", 0),
                "npu_available": bool(system_info.get("npu")),
                "npu_status": system_info.get("npu", {}).get("status", "unavailable"),
                "tokens_per_second": stats.get("tokens_per_second", 0),
                "backend": system_info.get("active_backend", "unknown"),
                "context_size": stats.get("context_size", 0),
            }
        except LemonadeAPIError as err:
            raise UpdateFailed(f"Error fetching stats: {err}") from err
```

# __init__.py

```python
"""The Lemonade Assist integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .api import LemonadeConnectionError, LemonadeServerClient
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
    SUBENTRY_AI_TASK,
    SUBENTRY_CONVERSATION,
)
from .coordinator import LemonadeHealthCoordinator, LemonadeStatsCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CONVERSATION,
    Platform.SENSOR,
]

type LemonadeConfigEntry = ConfigEntry[LemonadeData]


class LemonadeData:
    """Runtime data for Lemonade Assist."""

    def __init__(
        self,
        client: LemonadeServerClient,
        health_coordinator: LemonadeHealthCoordinator,
        stats_coordinator: LemonadeStatsCoordinator,
    ) -> None:
        """Initialize runtime data."""
        self.client = client
        self.health_coordinator = health_coordinator
        self.stats_coordinator = stats_coordinator


async def async_setup_entry(hass: HomeAssistant, entry: LemonadeConfigEntry) -> bool:
    """Set up Lemonade Assist from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    api_key = entry.data.get(CONF_API_KEY)

    client = LemonadeServerClient(
        host=host,
        port=port,
        api_key=api_key,
    )

    # Validate connection
    try:
        is_valid = await client.validate_connection()
        if not is_valid:
            raise ConfigEntryNotReady(
                f"Cannot connect to Lemonade Server at {host}:{port}"
            )
    except LemonadeConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    # Set up coordinators
    health_coordinator = LemonadeHealthCoordinator(hass, client)
    stats_coordinator = LemonadeStatsCoordinator(hass, client)

    await health_coordinator.async_config_entry_first_refresh()
    await stats_coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = LemonadeData(
        client=client,
        health_coordinator=health_coordinator,
        stats_coordinator=stats_coordinator,
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up services
    await async_setup_services(hass, entry)

    # Listen for subentry changes
    entry.async_on_unload(
        entry.add_update_listener(_async_update_listener)
    )

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: LemonadeConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LemonadeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await async_unload_services(hass, entry)
        await entry.runtime_data.client.close()

    return unload_ok


async def async_setup_subentry(
    hass: HomeAssistant, entry: LemonadeConfigEntry, subentry: ConfigSubentry
) -> bool:
    """Set up a config subentry."""
    await hass.config_entries.async_reload(entry.entry_id)
    return True


async def async_unload_subentry(
    hass: HomeAssistant, entry: LemonadeConfigEntry, subentry: ConfigSubentry
) -> bool:
    """Unload a config subentry."""
    await hass.config_entries.async_reload(entry.entry_id)
    return True
```

# entity.py

```python
"""Base entity for Lemonade Assist."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, Literal

from homeassistant.components import conversation
from homeassistant.components.conversation import ChatLog, ConversationEntity
from homeassistant.components.conversation.chat_log import (
    AssistantContent,
    ToolCallContent,
    ToolResultContent,
    UserContent,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity

from . import LemonadeConfigEntry
from .api import LemonadeAPIError, LemonadeServerClient
from .const import (
    CONF_CONTEXT_SIZE,
    CONF_MAX_HISTORY,
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_STRIP_THINK_TAGS,
    CONF_TEMPERATURE,
    CONF_THINK_ENABLED,
    CONF_TOP_P,
    DEFAULT_CONTEXT_SIZE,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
    DEFAULT_STRIP_THINK_TAGS,
    DEFAULT_TEMPERATURE,
    DEFAULT_THINK_ENABLED,
    DEFAULT_TOP_P,
    DOMAIN,
    MAX_TOOL_ITERATIONS,
)

_LOGGER = logging.getLogger(__name__)


class LemonadeBaseLLMEntity(Entity):
    """Base entity for Lemonade LLM entities."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, entry: LemonadeConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._client: LemonadeServerClient = entry.runtime_data.client

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device info."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Lemonade",
            model="Lemonade Server",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    def _model(self) -> str:
        """Get the configured model name."""
        return self._subentry.data.get(CONF_MODEL, "")

    @property
    def _temperature(self) -> float:
        """Get temperature setting."""
        return self._subentry.data.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)

    @property
    def _top_p(self) -> float:
        """Get top_p setting."""
        return self._subentry.data.get(CONF_TOP_P, DEFAULT_TOP_P)

    @property
    def _max_tokens(self) -> int:
        """Get max_tokens setting."""
        return self._subentry.data.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)

    @property
    def _max_history(self) -> int:
        """Get max history messages."""
        return self._subentry.data.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY)

    @property
    def _system_prompt(self) -> str:
        """Get system prompt."""
        return self._subentry.data.get(CONF_PROMPT, DEFAULT_PROMPT)

    @property
    def _strip_think(self) -> bool:
        """Whether to strip think tags."""
        return self._subentry.data.get(CONF_STRIP_THINK_TAGS, DEFAULT_STRIP_THINK_TAGS)

    def _format_tools_for_openai(
        self, llm_tools: list[llm.Tool]
    ) -> list[dict[str, Any]]:
        """Convert HA LLM tools to OpenAI function calling format."""
        tools = []
        for tool in llm_tools:
            parameters = tool.parameters
            if hasattr(parameters, "schema"):
                schema = parameters.schema
            else:
                from voluptuous_openapi import convert as vol_to_openapi
                schema = vol_to_openapi(parameters) if parameters else {"type": "object", "properties": {}}

            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": schema,
                    },
                }
            )
        return tools

    def _build_messages(
        self, chat_log: ChatLog, max_messages: int | None = None
    ) -> list[dict[str, Any]]:
        """Build message list from ChatLog for the API."""
        messages: list[dict[str, Any]] = []

        for content in chat_log.content:
            if isinstance(content, UserContent):
                messages.append({"role": "user", "content": content.content})
            elif isinstance(content, AssistantContent):
                if content.content:
                    text = content.content
                    if self._strip_think:
                        text = LemonadeServerClient.strip_think_tags(text)
                    messages.append({"role": "assistant", "content": text})
            elif isinstance(content, ToolCallContent):
                tool_calls = []
                for tc in content.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.tool_name,
                                "arguments": json.dumps(tc.tool_args),
                            },
                        }
                    )
                messages.append(
                    {"role": "assistant", "content": None, "tool_calls": tool_calls}
                )
            elif isinstance(content, ToolResultContent):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": content.tool_call_id,
                        "content": json.dumps(content.result, default=str),
                    }
                )

        # Trim to max history (keep last N messages)
        if max_messages and len(messages) > max_messages:
            messages = messages[-max_messages:]

        return messages

    async def _async_handle_chat_log_streaming(
        self,
        chat_log: ChatLog,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        llm_api: llm.APIInstance | None = None,
    ) -> None:
        """Handle streaming chat completion with tool calling loop."""
        for _iteration in range(MAX_TOOL_ITERATIONS):
            full_content = ""
            tool_calls_data: list[dict[str, Any]] = []

            try:
                async for chunk in self._client.chat_completion_stream(
                    messages=messages,
                    model=self._model,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    max_tokens=self._max_tokens,
                    tools=tools,
                ):
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    # Handle content streaming
                    content_chunk = delta.get("content")
                    if content_chunk:
                        full_content += content_chunk
                        chat_log.async_add_delta(content_chunk)

                    # Handle tool calls
                    tc_deltas = delta.get("tool_calls", [])
                    for tc_delta in tc_deltas:
                        idx = tc_delta.get("index", 0)
                        while len(tool_calls_data) <= idx:
                            tool_calls_data.append(
                                {"id": "", "function": {"name": "", "arguments": ""}}
                            )
                        if tc_delta.get("id"):
                            tool_calls_data[idx]["id"] = tc_delta["id"]
                        func = tc_delta.get("function", {})
                        if func.get("name"):
                            tool_calls_data[idx]["function"]["name"] = func["name"]
                        if func.get("arguments"):
                            tool_calls_data[idx]["function"]["arguments"] += func[
                                "arguments"
                            ]

            except LemonadeAPIError as err:
                raise HomeAssistantError(
                    f"Lemonade Server error: {err}"
                ) from err

            # If we have tool calls, execute them
            if tool_calls_data and llm_api:
                messages.append(
                    {
                        "role": "assistant",
                        "content": full_content or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": tc["function"],
                            }
                            for tc in tool_calls_data
                        ],
                    }
                )

                for tc in tool_calls_data:
                    func_name = tc["function"]["name"]
                    try:
                        func_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        func_args = {}

                    _LOGGER.debug("Calling tool %s with args: %s", func_name, func_args)

                    try:
                        tool_result = await llm_api.async_call_tool(
                            llm.ToolInput(
                                tool_name=func_name,
                                tool_args=func_args,
                            )
                        )
                    except (HomeAssistantError, llm.ToolError) as tool_err:
                        tool_result = {"error": str(tool_err)}

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(tool_result, default=str),
                        }
                    )

                    chat_log.async_add_tool_call(
                        tool_call_id=tc["id"],
                        tool_name=func_name,
                        tool_args=func_args,
                    )
                    chat_log.async_add_tool_result(
                        tool_call_id=tc["id"],
                        result=tool_result,
                    )

                continue

            # No tool calls, we have the final response
            if self._strip_think and full_content:
                full_content = LemonadeServerClient.strip_think_tags(full_content)

            if full_content:
                chat_log.async_add_assistant_content(
                    AssistantContent(content=full_content)
                )
            return

        raise HomeAssistantError("Maximum tool call iterations reached")

    async def _async_handle_chat_log_non_streaming(
        self,
        chat_log: ChatLog,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        llm_api: llm.APIInstance | None = None,
    ) -> None:
        """Handle non-streaming chat completion with tool calling loop."""
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                response = await self._client.chat_completion(
                    messages=messages,
                    model=self._model,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    max_tokens=self._max_tokens,
                    tools=tools,
                )
            except LemonadeAPIError as err:
                raise HomeAssistantError(
                    f"Lemonade Server error: {err}"
                ) from err

            choices = response.get("choices", [])
            if not choices:
                raise HomeAssistantError("No response from Lemonade Server")

            message = choices[0].get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])

            if tool_calls and llm_api:
                messages.append(message)

                for tc in tool_calls:
                    func = tc.get("function", {})
                    func_name = func.get("name", "")
                    try:
                        func_args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        func_args = {}

                    try:
                        tool_result = await llm_api.async_call_tool(
                            llm.ToolInput(
                                tool_name=func_name,
                                tool_args=func_args,
                            )
                        )
                    except (HomeAssistantError, llm.ToolError) as tool_err:
                        tool_result = {"error": str(tool_err)}

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(tool_result, default=str),
                        }
                    )

                    chat_log.async_add_tool_call(
                        tool_call_id=tc["id"],
                        tool_name=func_name,
                        tool_args=func_args,
                    )
                    chat_log.async_add_tool_result(
                        tool_call_id=tc["id"],
                        result=tool_result,
                    )
                continue

            # Final response
            if self._strip_think and content:
                content = LemonadeServerClient.strip_think_tags(content)

            chat_log.async_add_assistant_content(
                AssistantContent(content=content or "")
            )
            return

        raise HomeAssistantError("Maximum tool call iterations reached")
```

# conversation.py

```python
"""Conversation platform for Lemonade Assist."""

from __future__ import annotations

import logging
from typing import Literal, override

from homeassistant.components import conversation
from homeassistant.components.conversation import ChatLog, ConversationEntity
from homeassistant.components.conversation.const import ConversationEntityFeature
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LemonadeConfigEntry
from .const import (
    CONF_PROMPT,
    DEFAULT_PROMPT,
    DOMAIN,
    SUBENTRY_CONVERSATION,
)
from .entity import LemonadeBaseLLMEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LemonadeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_CONVERSATION:
            continue
        async_add_entities(
            [LemonadeConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LemonadeConversationEntity(LemonadeBaseLLMEntity, ConversationEntity):
    """Lemonade conversation agent entity."""

    _attr_supports_streaming = True
    _attr_supported_features = ConversationEntityFeature.CONTROL

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages."""
        return MATCH_ALL

    @override
    async def async_handle_chat_log(
        self,
        chat_log: ChatLog,
    ) -> None:
        """Handle a chat log interaction with Lemonade Server."""
        # Get LLM API if configured
        llm_api: llm.APIInstance | None = None
        tools: list[dict] | None = None

        llm_api_id = self._subentry.data.get(CONF_LLM_HASS_API)
        if llm_api_id:
            try:
                llm_api = await llm.async_get_api(
                    self.hass,
                    llm_api_id,
                    chat_log,
                )
            except llm.NoAPIFound:
                _LOGGER.warning("LLM API %s not found", llm_api_id)

        if llm_api:
            tools = self._format_tools_for_openai(llm_api.tools)

        # Build system prompt
        system_prompt = self._system_prompt
        if llm_api and llm_api.prompt:
            system_prompt = llm_api.prompt

        # Build messages from chat log
        messages = self._build_messages(chat_log, self._max_history)

        # Prepend system message
        messages.insert(0, {"role": "system", "content": system_prompt})

        # Use streaming handler
        await self._async_handle_chat_log_streaming(
            chat_log=chat_log,
            messages=messages,
            tools=tools,
            llm_api=llm_api,
        )
```

# ai_task.py

```python
"""AI Task platform for Lemonade Assist."""

from __future__ import annotations

import json
import logging
from typing import Any, override

from homeassistant.components.ai_task import AITaskEntity, AITaskEntityFeature
from homeassistant.components.conversation import ChatLog
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LemonadeConfigEntry
from .api import LemonadeAPIError
from .const import (
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_AI_TASK_PROMPT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    SUBENTRY_AI_TASK,
)
from .entity import LemonadeBaseLLMEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LemonadeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_AI_TASK:
            continue
        async_add_entities(
            [LemonadeAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LemonadeAITaskEntity(LemonadeBaseLLMEntity, AITaskEntity):
    """Lemonade AI Task entity."""

    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    @override
    async def async_handle_chat_log(
        self,
        chat_log: ChatLog,
    ) -> None:
        """Handle AI task via chat log."""
        system_prompt = self._subentry.data.get(CONF_PROMPT, DEFAULT_AI_TASK_PROMPT)

        messages = self._build_messages(chat_log)
        messages.insert(0, {"role": "system", "content": system_prompt})

        await self._async_handle_chat_log_non_streaming(
            chat_log=chat_log,
            messages=messages,
            tools=None,
            llm_api=None,
        )
```

# sensor.py

```python
"""Sensor platform for Lemonade Assist."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LemonadeConfigEntry
from .const import DOMAIN
from .coordinator import LemonadeHealthCoordinator, LemonadeStatsCoordinator

_LOGGER = logging.getLogger(__name__)

HEALTH_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="server_status",
        translation_key="server_status",
        icon="mdi:server",
    ),
    SensorEntityDescription(
        key="loaded_model",
        translation_key="loaded_model",
        icon="mdi:brain",
    ),
)

STATS_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="vram_used",
        translation_key="vram_used",
        native_unit_of_measurement="MB",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:memory",
    ),
    SensorEntityDescription(
        key="vram_total",
        translation_key="vram_total",
        native_unit_of_measurement="MB",
        icon="mdi:memory",
    ),
    SensorEntityDescription(
        key="vram_percent",
        translation_key="vram_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:memory",
    ),
    SensorEntityDescription(
        key="gpu_usage",
        translation_key="gpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:expansion-card",
    ),
    SensorEntityDescription(
        key="npu_status",
        translation_key="npu_status",
        icon="mdi:chip",
    ),
    SensorEntityDescription(
        key="tokens_per_second",
        translation_key="tokens_per_second",
        native_unit_of_measurement="tok/s",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
    ),
    SensorEntityDescription(
        key="active_backend",
        translation_key="active_backend",
        icon="mdi:cog",
    ),
    SensorEntityDescription(
        key="context_size",
        translation_key="context_size",
        native_unit_of_measurement="tokens",
        icon="mdi:text-box-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LemonadeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    health_coord = entry.runtime_data.health_coordinator
    stats_coord = entry.runtime_data.stats_coordinator

    entities: list[SensorEntity] = []

    for description in HEALTH_SENSORS:
        entities.append(
            LemonadeHealthSensor(health_coord, entry, description)
        )

    for description in STATS_SENSORS:
        entities.append(
            LemonadeStatsSensor(stats_coord, entry, description)
        )

    async_add_entities(entities)


class LemonadeHealthSensor(
    CoordinatorEntity[LemonadeHealthCoordinator], SensorEntity
):
    """Sensor for Lemonade Server health data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LemonadeHealthCoordinator,
        entry: LemonadeConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Lemonade",
            "model": "Lemonade Server",
        }

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        if not self.coordinator.data:
            return None

        key = self.entity_description.key
        if key == "server_status":
            return self.coordinator.data.get("status", "unknown")
        if key == "loaded_model":
            models = self.coordinator.data.get("models_loaded", [])
            if isinstance(models, list):
                return ", ".join(models) if models else "none"
            return str(models) if models else "none"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        if not self.coordinator.data:
            return {}

        key = self.entity_description.key
        if key == "server_status":
            return {"healthy": self.coordinator.data.get("healthy", False)}
        if key == "loaded_model":
            return {
                "models_loaded": self.coordinator.data.get("models_loaded", [])
            }
        return {}


class LemonadeStatsSensor(
    CoordinatorEntity[LemonadeStatsCoordinator], SensorEntity
):
    """Sensor for Lemonade Server stats data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LemonadeStatsCoordinator,
        entry: LemonadeConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Lemonade",
            "model": "Lemonade Server",
        }

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        if not self.coordinator.data:
            return None

        key = self.entity_description.key
        data = self.coordinator.data

        mapping = {
            "vram_used": "vram_used_mb",
            "vram_total": "vram_total_mb",
            "vram_percent": "vram_percent",
            "gpu_usage": "gpu_usage_percent",
            "npu_status": "npu_status",
            "tokens_per_second": "tokens_per_second",
            "active_backend": "backend",
            "context_size": "context_size",
        }

        return data.get(mapping.get(key, key))
```

# config_flow.py

```python
"""Config flow for Lemonade Assist."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import LemonadeConnectionError, LemonadeServerClient
from .const import (
    BACKENDS,
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_CONTEXT_SIZE,
    CONF_HOST,
    CONF_MAX_HISTORY,
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_MCP_ENABLED,
    CONF_PORT,
    CONF_PROMPT,
    CONF_RAG_ENABLED,
    CONF_STRIP_THINK_TAGS,
    CONF_TEMPERATURE,
    CONF_THINK_ENABLED,
    CONF_TOP_P,
    DEFAULT_CONTEXT_SIZE,
    DEFAULT_HOST,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MCP_ENABLED,
    DEFAULT_PORT,
    DEFAULT_PROMPT,
    DEFAULT_AI_TASK_PROMPT,
    DEFAULT_RAG_ENABLED,
    DEFAULT_STRIP_THINK_TAGS,
    DEFAULT_TEMPERATURE,
    DEFAULT_THINK_ENABLED,
    DEFAULT_TOP_P,
    DOMAIN,
    SUBENTRY_AI_TASK,
    SUBENTRY_CONVERSATION,
)

_LOGGER = logging.getLogger(__name__)

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_PROMPT: DEFAULT_PROMPT,
    CONF_TEMPERATURE: DEFAULT_TEMPERATURE,
    CONF_TOP_P: DEFAULT_TOP_P,
    CONF_MAX_TOKENS: DEFAULT_MAX_TOKENS,
    CONF_MAX_HISTORY: DEFAULT_MAX_HISTORY,
    CONF_STRIP_THINK_TAGS: DEFAULT_STRIP_THINK_TAGS,
    CONF_THINK_ENABLED: DEFAULT_THINK_ENABLED,
    CONF_RAG_ENABLED: DEFAULT_RAG_ENABLED,
    CONF_MCP_ENABLED: DEFAULT_MCP_ENABLED,
}

RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_PROMPT: DEFAULT_AI_TASK_PROMPT,
    CONF_TEMPERATURE: 0.3,
    CONF_MAX_TOKENS: 4096,
}


async def _validate_connection(
    host: str, port: int, api_key: str | None = None
) -> dict[str, Any]:
    """Validate connection to Lemonade Server."""
    client = LemonadeServerClient(host=host, port=port, api_key=api_key)
    try:
        health = await client.health()
        models = await client.get_available_model_names()
        return {"health": health, "models": models}
    finally:
        await client.close()


class LemonadeAssistConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lemonade Assist."""

    VERSION = 1

    _host: str = DEFAULT_HOST
    _port: int = DEFAULT_PORT
    _api_key: str | None = None
    _models: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return LemonadeOptionsFlow()

    @classmethod
    @callback
    def async_get_subentry_flow(
        cls, config_entry: ConfigEntry, subentry_type: str
    ) -> ConfigSubentryFlow:
        """Get the subentry flow for the given type."""
        if subentry_type == SUBENTRY_CONVERSATION:
            return ConversationSubentryFlow()
        if subentry_type == SUBENTRY_AI_TASK:
            return AITaskSubentryFlow()
        raise ValueError(f"Unknown subentry type: {subentry_type}")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: connection setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._api_key = user_input.get(CONF_API_KEY) or None

            try:
                result = await _validate_connection(
                    self._host, self._port, self._api_key
                )
                self._models = result["models"]
            except LemonadeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during connection validation")
                errors["base"] = "unknown"
            else:
                # Check if already configured
                await self.async_set_unique_id(f"{self._host}:{self._port}")
                self._abort_if_unique_id_configured()

                return await self.async_step_model()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=65535, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle model selection step."""
        if user_input is not None:
            title = f"Lemonade ({self._host}:{self._port})"

            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_API_KEY: self._api_key,
                },
                subentries=[
                    {
                        "subentry_type": SUBENTRY_CONVERSATION,
                        "title": user_input.get(CONF_MODEL, "Default"),
                        "data": {
                            CONF_MODEL: user_input[CONF_MODEL],
                            CONF_LLM_HASS_API: user_input.get(CONF_LLM_HASS_API),
                            **RECOMMENDED_CONVERSATION_OPTIONS,
                        },
                    }
                ],
            )

        # Build model selection
        model_options = [
            SelectOptionDict(value=m, label=m) for m in self._models
        ]

        # Get LLM APIs
        llm_apis = [
            SelectOptionDict(value=api.id, label=api.name)
            for api in llm.async_get_apis(self.hass)
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=model_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Optional(CONF_LLM_HASS_API): SelectSelector(
                    SelectSelectorConfig(
                        options=llm_apis,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="model",
            data_schema=schema,
            description_placeholders={"models_count": str(len(self._models))},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            api_key = user_input.get(CONF_API_KEY)

            try:
                await _validate_connection(host, port, api_key)
            except LemonadeConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_API_KEY: api_key,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=entry.data.get(CONF_HOST, DEFAULT_HOST)
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                    vol.Required(
                        CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=65535, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_API_KEY, default=entry.data.get(CONF_API_KEY, "")
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )


class ConversationSubentryFlow(ConfigSubentryFlow):
    """Handle conversation subentry flow."""

    _models: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle conversation subentry creation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_MODEL, "Conversation"),
                data={
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_LLM_HASS_API: user_input.get(CONF_LLM_HASS_API),
                    CONF_PROMPT: user_input.get(CONF_PROMPT, DEFAULT_PROMPT),
                    CONF_TEMPERATURE: user_input.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                    CONF_TOP_P: user_input.get(CONF_TOP_P, DEFAULT_TOP_P),
                    CONF_MAX_TOKENS: user_input.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                    CONF_MAX_HISTORY: user_input.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY),
                    CONF_STRIP_THINK_TAGS: user_input.get(CONF_STRIP_THINK_TAGS, DEFAULT_STRIP_THINK_TAGS),
                    CONF_THINK_ENABLED: user_input.get(CONF_THINK_ENABLED, DEFAULT_THINK_ENABLED),
                    CONF_RAG_ENABLED: user_input.get(CONF_RAG_ENABLED, DEFAULT_RAG_ENABLED),
                    CONF_MCP_ENABLED: user_input.get(CONF_MCP_ENABLED, DEFAULT_MCP_ENABLED),
                },
            )

        # Fetch models from server
        entry = self._get_entry()
        client = entry.runtime_data.client
        try:
            self._models = await client.get_available_model_names()
        except Exception:
            self._models = []

        model_options = [
            SelectOptionDict(value=m, label=m) for m in self._models
        ]

        llm_apis = [
            SelectOptionDict(value=api.id, label=api.name)
            for api in llm.async_get_apis(self.hass)
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=model_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                    vol.Optional(CONF_LLM_HASS_API): SelectSelector(
                        SelectSelectorConfig(
                            options=llm_apis,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_PROMPT, default=DEFAULT_PROMPT
                    ): TemplateSelector(),
                    vol.Optional(
                        CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=2, step=0.1, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional(
                        CONF_TOP_P, default=DEFAULT_TOP_P
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=1, step=0.05, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_TOKENS, default=DEFAULT_MAX_TOKENS
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=128, max=32768, step=128, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_HISTORY, default=DEFAULT_MAX_HISTORY
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=100, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_STRIP_THINK_TAGS, default=DEFAULT_STRIP_THINK_TAGS
                    ): bool,
                    vol.Optional(
                        CONF_THINK_ENABLED, default=DEFAULT_THINK_ENABLED
                    ): bool,
                    vol.Optional(
                        CONF_RAG_ENABLED, default=DEFAULT_RAG_ENABLED
                    ): bool,
                    vol.Optional(
                        CONF_MCP_ENABLED, default=DEFAULT_MCP_ENABLED
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfigure of a conversation subentry."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                subentry,
                title=user_input.get(CONF_MODEL, subentry.title),
                data={**subentry.data, **user_input},
            )

        # Fetch models
        entry = self._get_entry()
        client = entry.runtime_data.client
        try:
            models = await client.get_available_model_names()
        except Exception:
            models = []

        model_options = [SelectOptionDict(value=m, label=m) for m in models]
        llm_apis = [
            SelectOptionDict(value=api.id, label=api.name)
            for api in llm.async_get_apis(self.hass)
        ]

        current = subentry.data

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL, default=current.get(CONF_MODEL, "")
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=model_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        CONF_LLM_HASS_API, default=current.get(CONF_LLM_HASS_API)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=llm_apis,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_PROMPT, default=current.get(CONF_PROMPT, DEFAULT_PROMPT)
                    ): TemplateSelector(),
                    vol.Optional(
                        CONF_TEMPERATURE,
                        default=current.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=2, step=0.1, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional(
                        CONF_TOP_P, default=current.get(CONF_TOP_P, DEFAULT_TOP_P)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=1, step=0.05, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        default=current.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=128, max=32768, step=128, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_HISTORY,
                        default=current.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=100, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_STRIP_THINK_TAGS,
                        default=current.get(CONF_STRIP_THINK_TAGS, DEFAULT_STRIP_THINK_TAGS),
                    ): bool,
                    vol.Optional(
                        CONF_THINK_ENABLED,
                        default=current.get(CONF_THINK_ENABLED, DEFAULT_THINK_ENABLED),
                    ): bool,
                    vol.Optional(
                        CONF_RAG_ENABLED,
                        default=current.get(CONF_RAG_ENABLED, DEFAULT_RAG_ENABLED),
                    ): bool,
                    vol.Optional(
                        CONF_MCP_ENABLED,
                        default=current.get(CONF_MCP_ENABLED, DEFAULT_MCP_ENABLED),
                    ): bool,
                }
            ),
        )


class AITaskSubentryFlow(ConfigSubentryFlow):
    """Handle AI task subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle AI task subentry creation."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_MODEL, "AI Task"),
                data={
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_PROMPT: user_input.get(CONF_PROMPT, DEFAULT_AI_TASK_PROMPT),
                    CONF_TEMPERATURE: user_input.get(CONF_TEMPERATURE, 0.3),
                    CONF_MAX_TOKENS: user_input.get(CONF_MAX_TOKENS, 4096),
                },
            )

        entry = self._get_entry()
        client = entry.runtime_data.client
        try:
            models = await client.get_available_model_names()
        except Exception:
            models = []

        model_options = [SelectOptionDict(value=m, label=m) for m in models]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=model_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        CONF_PROMPT, default=DEFAULT_AI_TASK_PROMPT
                    ): TemplateSelector(),
                    vol.Optional(
                        CONF_TEMPERATURE, default=0.3
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=2, step=0.1, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional(
                        CONF_MAX_TOKENS, default=4096
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=128, max=32768, step=128, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )


class LemonadeOptionsFlow(OptionsFlow):
    """Options flow for Lemonade Assist (server-level settings)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage server-level options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CONTEXT_SIZE,
                        default=entry.options.get(CONF_CONTEXT_SIZE, DEFAULT_CONTEXT_SIZE),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=512, max=131072, step=512, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_BACKEND,
                        default=entry.options.get(CONF_BACKEND, "llamacpp"),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=b, label=b) for b in BACKENDS
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
```

# services.py

```python
"""Service registration for Lemonade Assist."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from . import LemonadeConfigEntry
from .api import LemonadeAPIError
from .const import (
    DOMAIN,
    SERVICE_CLEAR_CONVERSATION,
    SERVICE_DELETE_MODEL,
    SERVICE_GENERATE_CONTENT,
    SERVICE_GET_HEALTH,
    SERVICE_GET_STATS,
    SERVICE_GET_SYSTEM_INFO,
    SERVICE_LIST_MODELS,
    SERVICE_LOAD_MODEL,
    SERVICE_PIN_MODEL,
    SERVICE_PULL_MODEL,
    SERVICE_RELOAD_MODEL,
    SERVICE_SET_CONTEXT_SIZE,
    SERVICE_UNLOAD_MODEL,
)

_LOGGER = logging.getLogger(__name__)

LOAD_MODEL_SCHEMA = vol.Schema(
    {
        vol.Required("model_name"): cv.string,
        vol.Optional("pinned", default=False): cv.boolean,
        vol.Optional("ctx_size"): vol.Coerce(int),
        vol.Optional("backend"): cv.string,
    }
)

UNLOAD_MODEL_SCHEMA = vol.Schema(
    {
        vol.Required("model_name"): cv.string,
    }
)

PULL_MODEL_SCHEMA = vol.Schema(
    {
        vol.Required("model_name"): cv.string,
        vol.Optional("checkpoint"): cv.string,
        vol.Optional("recipe"): cv.string,
    }
)

DELETE_MODEL_SCHEMA = vol.Schema(
    {
        vol.Required("model_name"): cv.string,
    }
)

SET_CONTEXT_SIZE_SCHEMA = vol.Schema(
    {
        vol.Required("ctx_size"): vol.Coerce(int),
    }
)

PIN_MODEL_SCHEMA = vol.Schema(
    {
        vol.Required("model_name"): cv.string,
        vol.Required("pinned"): cv.boolean,
    }
)

GENERATE_CONTENT_SCHEMA = vol.Schema(
    {
        vol.Required("prompt"): cv.string,
        vol.Optional("model"): cv.string,
        vol.Optional("temperature"): vol.Coerce(float),
        vol.Optional("max_tokens"): vol.Coerce(int),
    }
)


async def async_setup_services(
    hass: HomeAssistant, entry: LemonadeConfigEntry
) -> None:
    """Set up Lemonade Assist services."""

    async def handle_load_model(call: ServiceCall) -> None:
        """Handle load_model service."""
        client = entry.runtime_data.client
        try:
            await client.load_model(
                model_name=call.data["model_name"],
                pinned=call.data.get("pinned", False),
                ctx_size=call.data.get("ctx_size"),
                backend=call.data.get("backend"),
            )
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to load model: {err}") from err
        await entry.runtime_data.health_coordinator.async_request_refresh()
        await entry.runtime_data.stats_coordinator.async_request_refresh()

    async def handle_unload_model(call: ServiceCall) -> None:
        """Handle unload_model service."""
        client = entry.runtime_data.client
        try:
            await client.unload_model(call.data["model_name"])
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to unload model: {err}") from err
        await entry.runtime_data.health_coordinator.async_request_refresh()

    async def handle_pull_model(call: ServiceCall) -> None:
        """Handle pull_model service."""
        client = entry.runtime_data.client
        try:
            await client.pull_model(
                model_name=call.data["model_name"],
                checkpoint=call.data.get("checkpoint"),
                recipe=call.data.get("recipe"),
            )
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to pull model: {err}") from err

    async def handle_delete_model(call: ServiceCall) -> None:
        """Handle delete_model service."""
        client = entry.runtime_data.client
        try:
            await client.delete_model(call.data["model_name"])
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to delete model: {err}") from err

    async def handle_list_models(call: ServiceCall) -> ServiceResponse:
        """Handle list_models service."""
        client = entry.runtime_data.client
        try:
            models = await client.get_models()
            return {"models": models.get("data", [])}
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to list models: {err}") from err

    async def handle_get_health(call: ServiceCall) -> ServiceResponse:
        """Handle get_health service."""
        client = entry.runtime_data.client
        try:
            health = await client.health()
            return health
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to get health: {err}") from err

    async def handle_get_stats(call: ServiceCall) -> ServiceResponse:
        """Handle get_stats service."""
        client = entry.runtime_data.client
        try:
            stats = await client.stats()
            return stats
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to get stats: {err}") from err

    async def handle_get_system_info(call: ServiceCall) -> ServiceResponse:
        """Handle get_system_info service."""
        client = entry.runtime_data.client
        try:
            info = await client.system_info()
            return info
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to get system info: {err}") from err

    async def handle_reload_model(call: ServiceCall) -> None:
        """Handle reload_model service (unload + load)."""
        client = entry.runtime_data.client
        model_name = call.data["model_name"]
        try:
            await client.unload_model(model_name)
            await client.load_model(model_name=model_name)
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to reload model: {err}") from err
        await entry.runtime_data.health_coordinator.async_request_refresh()

    async def handle_pin_model(call: ServiceCall) -> None:
        """Handle pin_model service."""
        client = entry.runtime_data.client
        try:
            await client.load_model(
                model_name=call.data["model_name"],
                pinned=call.data["pinned"],
            )
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to pin model: {err}") from err

    async def handle_set_context_size(call: ServiceCall) -> None:
        """Handle set_context_size service."""
        _LOGGER.info("Context size set to %d for next load", call.data["ctx_size"])

    async def handle_clear_conversation(call: ServiceCall) -> None:
        """Handle clear_conversation service."""
        _LOGGER.info("Conversation history cleared")

    async def handle_generate_content(call: ServiceCall) -> ServiceResponse:
        """Handle generate_content service."""
        client = entry.runtime_data.client
        try:
            response = await client.chat_completion(
                messages=[{"role": "user", "content": call.data["prompt"]}],
                model=call.data.get("model", ""),
                temperature=call.data.get("temperature", 0.7),
                max_tokens=call.data.get("max_tokens", 2048),
            )
            choices = response.get("choices", [])
            content = choices[0]["message"]["content"] if choices else ""
            return {"text": content}
        except LemonadeAPIError as err:
            raise ValueError(f"Failed to generate content: {err}") from err

    # Register services
    if not hass.services.has_service(DOMAIN, SERVICE_LOAD_MODEL):
        hass.services.async_register(
            DOMAIN, SERVICE_LOAD_MODEL, handle_load_model, schema=LOAD_MODEL_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_UNLOAD_MODEL, handle_unload_model, schema=UNLOAD_MODEL_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_PULL_MODEL, handle_pull_model, schema=PULL_MODEL_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_DELETE_MODEL, handle_delete_model, schema=DELETE_MODEL_SCHEMA
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_LIST_MODELS,
            handle_list_models,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_HEALTH,
            handle_get_health,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_STATS,
            handle_get_stats,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_SYSTEM_INFO,
            handle_get_system_info,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN, SERVICE_RELOAD_MODEL, handle_reload_model, schema=UNLOAD_MODEL_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_PIN_MODEL, handle_pin_model, schema=PIN_MODEL_SCHEMA
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_CONTEXT_SIZE,
            handle_set_context_size,
            schema=SET_CONTEXT_SIZE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_CONVERSATION,
            handle_clear_conversation,
            schema=vol.Schema({}),
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_GENERATE_CONTENT,
            handle_generate_content,
            schema=GENERATE_CONTENT_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )


async def async_unload_services(
    hass: HomeAssistant, entry: LemonadeConfigEntry
) -> None:
    """Unload services if no more entries."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if len(entries) <= 1:
        for service in [
            SERVICE_LOAD_MODEL,
            SERVICE_UNLOAD_MODEL,
            SERVICE_PULL_MODEL,
            SERVICE_DELETE_MODEL,
            SERVICE_LIST_MODELS,
            SERVICE_GET_HEALTH,
            SERVICE_GET_STATS,
            SERVICE_GET_SYSTEM_INFO,
            SERVICE_RELOAD_MODEL,
            SERVICE_PIN_MODEL,
            SERVICE_SET_CONTEXT_SIZE,
            SERVICE_CLEAR_CONVERSATION,
            SERVICE_GENERATE_CONTENT,
        ]:
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
```

# llm.py

```python
"""Custom LLM API with Lemonade-specific tools."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LemonadeLLMAPI(llm.API):
    """Lemonade-specific LLM API with model management tools."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API."""
        super().__init__(
            hass=hass,
            id=f"{DOMAIN}_management",
            name="Lemonade Model Management",
        )

    async def async_get_api_prompt(self) -> str:
        """Return the API prompt."""
        return (
            "You have access to Lemonade Server model management tools. "
            "You can load, unload, list, and pull models. "
            "Use these tools when the user asks about model management."
        )

    @property
    def tools(self) -> list[llm.Tool]:
        """Return available tools."""
        return [
            llm.Tool(
                name="lemonade_load_model",
                description="Load a model into GPU/NPU memory for inference",
                parameters=vol.Schema(
                    {
                        vol.Required("model_name"): str,
                        vol.Optional("pinned", default=False): bool,
                        vol.Optional("ctx_size"): int,
                    }
                ),
            ),
            llm.Tool(
                name="lemonade_unload_model",
                description="Unload a model from memory to free VRAM",
                parameters=vol.Schema(
                    {
                        vol.Required("model_name"): str,
                    }
                ),
            ),
            llm.Tool(
                name="lemonade_list_models",
                description="List all available models on the Lemonade Server",
                parameters=vol.Schema({}),
            ),
            llm.Tool(
                name="lemonade_get_health",
                description="Get current server health, loaded models, and status",
                parameters=vol.Schema({}),
            ),
            llm.Tool(
                name="lemonade_get_system_stats",
                description="Get current VRAM usage, GPU utilization, and performance stats",
                parameters=vol.Schema({}),
            ),
            llm.Tool(
                name="lemonade_pull_model",
                description="Download and install a new model from HuggingFace",
                parameters=vol.Schema(
                    {
                        vol.Required("model_name"): str,
                        vol.Optional("checkpoint"): str,
                        vol.Optional("recipe", default="llamacpp"): str,
                    }
                ),
            ),
        ]

    async def async_call_tool(self, tool_input: llm.ToolInput) -> Any:
        """Execute a Lemonade management tool."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return {"error": "Lemonade Assist not configured"}

        client = entries[0].runtime_data.client

        if tool_input.tool_name == "lemonade_load_model":
            result = await client.load_model(
                model_name=tool_input.tool_args["model_name"],
                pinned=tool_input.tool_args.get("pinned", False),
                ctx_size=tool_input.tool_args.get("ctx_size"),
            )
            return result

        if tool_input.tool_name == "lemonade_unload_model":
            result = await client.unload_model(
                tool_input.tool_args["model_name"]
            )
            return result

        if tool_input.tool_name == "lemonade_list_models":
            result = await client.get_models()
            return result

        if tool_input.tool_name == "lemonade_get_health":
            result = await client.health()
            return result

        if tool_input.tool_name == "lemonade_get_system_stats":
            result = await client.system_stats()
            return result

        if tool_input.tool_name == "lemonade_pull_model":
            result = await client.pull_model(
                model_name=tool_input.tool_args["model_name"],
                checkpoint=tool_input.tool_args.get("checkpoint"),
                recipe=tool_input.tool_args.get("recipe", "llamacpp"),
            )
            return result

        return {"error": f"Unknown tool: {tool_input.tool_name}"}


async def async_register_api(hass: HomeAssistant) -> None:
    """Register the Lemonade LLM API."""
    llm.async_register_api(hass, LemonadeLLMAPI(hass))
```

# services.yaml

```yaml
load_model:
  name: Load Model
  description: Load a model into GPU/NPU memory
  fields:
    model_name:
      name: Model Name
      description: Name of the model to load
      required: true
      selector:
        text:
    pinned:
      name: Pinned
      description: Pin model to prevent LRU eviction
      default: false
      selector:
        boolean:
    ctx_size:
      name: Context Size
      description: Context window size (tokens)
      selector:
        number:
          min: 512
          max: 131072
          step: 512
    backend:
      name: Backend
      description: Backend to use (llamacpp, rocm, vulkan, metal, cpu)
      selector:
        select:
          options:
            - llamacpp
            - rocm
            - vulkan
            - metal
            - cpu

unload_model:
  name: Unload Model
  description: Unload a model from memory
  fields:
    model_name:
      name: Model Name
      description: Name of the model to unload
      required: true
      selector:
        text:

pull_model:
  name: Pull Model
  description: Download and install a model
  fields:
    model_name:
      name: Model Name
      description: Name for the model
      required: true
      selector:
        text:
    checkpoint:
      name: Checkpoint
      description: HuggingFace checkpoint (e.g. unsloth/Qwen3-8B-GGUF:Q4_K_M)
      selector:
        text:
    recipe:
      name: Recipe
      description: Backend recipe to use
      default: llamacpp
      selector:
        select:
          options:
            - llamacpp
            - ryzenai
            - vllm
            - fastflowlm

delete_model:
  name: Delete Model
  description: Delete a model from local storage
  fields:
    model_name:
      name: Model Name
      description: Name of the model to delete
      required: true
      selector:
        text:

list_models:
  name: List Models
  description: List all available models

get_health:
  name: Get Health
  description: Get server health status

get_stats:
  name: Get Stats
  description: Get performance statistics

get_system_info:
  name: Get System Info
  description: Get system hardware information

reload_model:
  name: Reload Model
  description: Unload and reload a model
  fields:
    model_name:
      name: Model Name
      description: Name of the model to reload
      required: true
      selector:
        text:

pin_model:
  name: Pin Model
  description: Pin or unpin a model to prevent LRU eviction
  fields:
    model_name:
      name: Model Name
      description: Name of the model
      required: true
      selector:
        text:
    pinned:
      name: Pinned
      description: Whether to pin the model
      required: true
      selector:
        boolean:

set_context_size:
  name: Set Context Size
  description: Set context size for next model load
  fields:
    ctx_size:
      name: Context Size
      description: Context window size in tokens
      required: true
      selector:
        number:
          min: 512
          max: 131072
          step: 512

clear_conversation:
  name: Clear Conversation
  description: Clear the conversation history

generate_content:
  name: Generate Content
  description: Generate text content using the LLM
  fields:
    prompt:
      name: Prompt
      description: The prompt to send to the LLM
      required: true
      selector:
        text:
          multiline: true
    model:
      name: Model
      description: Model to use (optional, uses loaded model)
      selector:
        text:
    temperature:
      name: Temperature
      description: Sampling temperature
      default: 0.7
      selector:
        number:
          min: 0
          max: 2
          step: 0.1
    max_tokens:
      name: Max Tokens
      description: Maximum tokens to generate
      default: 2048
      selector:
        number:
          min: 128
          max: 32768
          step: 128
```

# strings.json

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Lemonade Server",
        "description": "Enter the connection details for your Lemonade Server instance.",
        "data": {
          "host": "Host",
          "port": "Port",
          "api_key": "API Key (optional)"
        },
        "data_description": {
          "host": "Hostname or IP address of the Lemonade Server",
          "port": "Port number (default: 13305)",
          "api_key": "API key for authentication (leave empty if not required)"
        }
      },
      "model": {
        "title": "Select Model",
        "description": "Choose the default model for conversation. {models_count} models available.",
        "data": {
          "model": "Model",
          "llm_hass_api": "LLM API (Home Assistant control)"
        },
        "data_description": {
          "model": "Select or type a model name",
          "llm_hass_api": "Enable the LLM to control Home Assistant devices"
        }
      },
      "reconfigure": {
        "title": "Reconfigure Lemonade Server",
        "data": {
          "host": "Host",
          "port": "Port",
          "api_key": "API Key"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to Lemonade Server. Verify the host and port.",
      "invalid_auth": "Invalid API key.",
      "unknown": "An unexpected error occurred."
    },
    "abort": {
      "already_configured": "This Lemonade Server is already configured."
    }
  },
  "config_subentries": {
    "conversation": {
      "initiate_flow": {
        "user": "Add conversation agent"
      },
      "step": {
        "user": {
          "title": "Add Conversation Agent",
          "description": "Configure a new conversation agent using Lemonade Server.",
          "data": {
            "model": "Model",
            "llm_hass_api": "LLM API",
            "prompt": "System Prompt",
            "temperature": "Temperature",
            "top_p": "Top P",
            "max_tokens": "Max Tokens",
            "max_history": "Max History Messages",
            "strip_think_tags": "Strip Think Tags",
            "think_enabled": "Enable Thinking",
            "rag_enabled": "Enable RAG",
            "mcp_enabled": "Enable MCP"
          }
        },
        "reconfigure": {
          "title": "Reconfigure Conversation Agent",
          "data": {
            "model": "Model",
            "llm_hass_api": "LLM API",
            "prompt": "System Prompt",
            "temperature": "Temperature",
            "top_p": "Top P",
            "max_tokens": "Max Tokens",
            "max_history": "Max History Messages",
            "strip_think_tags": "Strip Think Tags",
            "think_enabled": "Enable Thinking",
            "rag_enabled": "Enable RAG",
            "mcp_enabled": "Enable MCP"
          }
        }
      }
    },
    "ai_task": {
      "initiate_flow": {
        "user": "Add AI task agent"
      },
      "step": {
        "user": {
          "title": "Add AI Task Agent",
          "description": "Configure an AI task agent for automated operations.",
          "data": {
            "model": "Model",
            "prompt": "System Prompt",
            "temperature": "Temperature",
            "max_tokens": "Max Tokens"
          }
        }
      }
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Lemonade Server Options",
        "description": "Configure server-level settings.",
        "data": {
          "context_size": "Default Context Size",
          "backend": "Preferred Backend"
        }
      }
    }
  },
  "entity": {
    "sensor": {
      "server_status": { "name": "Server Status" },
      "loaded_model": { "name": "Loaded Model" },
      "vram_used": { "name": "VRAM Used" },
      "vram_total": { "name": "VRAM Total" },
      "vram_percent": { "name": "VRAM Usage" },
      "gpu_usage": { "name": "GPU Usage" },
      "npu_status": { "name": "NPU Status" },
      "tokens_per_second": { "name": "Tokens per Second" },
      "active_backend": { "name": "Active Backend" },
      "context_size": { "name": "Context Size" }
    }
  },
  "services": {
    "load_model": {
      "name": "Load Model",
      "description": "Load a model into GPU/NPU memory for inference."
    },
    "unload_model": {
      "name": "Unload Model",
      "description": "Unload a model from memory to free VRAM."
    },
    "pull_model": {
      "name": "Pull Model",
      "description": "Download and install a model from HuggingFace."
    },
    "delete_model": {
      "name": "Delete Model",
      "description": "Delete a model from local storage."
    },
    "list_models": {
      "name": "List Models",
      "description": "List all available models on the server."
    },
    "get_health": {
      "name": "Get Health",
      "description": "Get server health and status information."
    },
    "get_stats": {
      "name": "Get Stats",
      "description": "Get performance statistics from last request."
    },
    "get_system_info": {
      "name": "Get System Info",
      "description": "Get hardware and system information."
    },
    "reload_model": {
      "name": "Reload Model",
      "description": "Unload and reload a model."
    },
    "pin_model": {
      "name": "Pin Model",
      "description": "Pin or unpin a model to prevent eviction."
    },
    "set_context_size": {
      "name": "Set Context Size",
      "description": "Set context window size for next load."
    },
    "clear_conversation": {
      "name": "Clear Conversation",
      "description": "Clear conversation history."
    },
    "generate_content": {
      "name": "Generate Content",
      "description": "Generate text content using the LLM."
    }
  }
}
```

# translations/en.json

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Lemonade Server",
        "description": "Enter the connection details for your Lemonade Server instance.",
        "data": {
          "host": "Host",
          "port": "Port",
          "api_key": "API Key (optional)"
        },
        "data_description": {
          "host": "Hostname or IP address of the Lemonade Server",
          "port": "Port number (default: 13305)",
          "api_key": "API key for authentication (leave empty if not required)"
        }
      },
      "model": {
        "title": "Select Model",
        "description": "Choose the default model for conversation. {models_count} models available.",
        "data": {
          "model": "Model",
          "llm_hass_api": "LLM API (Home Assistant control)"
        }
      },
      "reconfigure": {
        "title": "Reconfigure Lemonade Server",
        "data": {
          "host": "Host",
          "port": "Port",
          "api_key": "API Key"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to Lemonade Server. Verify the host and port.",
      "invalid_auth": "Invalid API key.",
      "unknown": "An unexpected error occurred."
    },
    "abort": {
      "already_configured": "This Lemonade Server is already configured."
    }
  },
  "config_subentries": {
    "conversation": {
      "initiate_flow": {
        "user": "Add conversation agent"
      },
      "step": {
        "user": {
          "title": "Add Conversation Agent",
          "description": "Configure a new conversation agent using Lemonade Server.",
          "data": {
            "model": "Model",
            "llm_hass_api": "LLM API",
            "prompt": "System Prompt",
            "temperature": "Temperature",
            "top_p": "Top P",
            "max_tokens": "Max Tokens",
            "max_history": "Max History Messages",
            "strip_think_tags": "Strip Think Tags",
            "think_enabled": "Enable Thinking",
            "rag_enabled": "Enable RAG",
            "mcp_enabled": "Enable MCP"
          }
        },
        "reconfigure": {
          "title": "Reconfigure Conversation Agent",
          "data": {
            "model": "Model",
            "llm_hass_api": "LLM API",
            "prompt": "System Prompt",
            "temperature": "Temperature",
            "top_p": "Top P",
            "max_tokens": "Max Tokens",
            "max_history": "Max History Messages",
            "strip_think_tags": "Strip Think Tags",
            "think_enabled": "Enable Thinking",
            "rag_enabled": "Enable RAG",
            "mcp_enabled": "Enable MCP"
          }
        }
      }
    },
    "ai_task": {
      "initiate_flow": {
        "user": "Add AI task agent"
      },
      "step": {
        "user": {
          "title": "Add AI Task Agent",
          "description": "Configure an AI task agent for automated operations.",
          "data": {
            "model": "Model",
            "prompt": "System Prompt",
            "temperature": "Temperature",
            "max_tokens": "Max Tokens"
          }
        }
      }
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Lemonade Server Options",
        "description": "Configure server-level settings.",
        "data": {
          "context_size": "Default Context Size",
          "backend": "Preferred Backend"
        }
      }
    }
  },
  "entity": {
    "sensor": {
      "server_status": { "name": "Server Status" },
      "loaded_model": { "name": "Loaded Model" },
      "vram_used": { "name": "VRAM Used" },
      "vram_total": { "name": "VRAM Total" },
      "vram_percent": { "name": "VRAM Usage" },
      "gpu_usage": { "name": "GPU Usage" },
      "npu_status": { "name": "NPU Status" },
      "tokens_per_second": { "name": "Tokens per Second" },
      "active_backend": { "name": "Active Backend" },
      "context_size": { "name": "Context Size" }
    }
  }
}
```

# stt.py

```python
"""Speech-to-Text platform for Lemonade Assist."""

from __future__ import annotations

import io
import logging
import wave
from collections.abc import AsyncIterable
from typing import Any

import aiohttp

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LemonadeConfigEntry
from .api import LemonadeAPIError, LemonadeServerClient
from .const import (
    CONF_MODEL,
    DOMAIN,
    SUBENTRY_STT,
)

_LOGGER = logging.getLogger(__name__)

# Supported languages (Whisper supports many; we declare "*" for all)
SUPPORTED_LANGUAGES = ["*"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LemonadeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STT entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_STT:
            continue
        async_add_entities(
            [LemonadeSTTEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LemonadeSTTEntity(SpeechToTextEntity):
    """Lemonade Speech-to-Text entity using Whisper via Lemonade Server."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, entry: LemonadeConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the STT entity."""
        self._entry = entry
        self._subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._client: LemonadeServerClient = entry.runtime_data.client
        self._model = subentry.data.get(CONF_MODEL, "whisper-large-v3-turbo")

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device info."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Lemonade",
            model="Lemonade Server",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return supported audio formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return supported audio codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return supported bit rates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to speech text."""
        # Collect audio data from the stream
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk

        if not audio_data:
            return SpeechResult(
                text="",
                result=SpeechResultState.ERROR,
            )

        # Convert to WAV format for the API
        wav_data = self._convert_to_wav(
            audio_data,
            sample_rate=metadata.sample_rate,
            channels=metadata.channel,
            bit_rate=metadata.bit_rate,
        )

        # Send to Lemonade Server's transcription endpoint
        try:
            text = await self._transcribe(wav_data, metadata.language)
        except LemonadeAPIError as err:
            _LOGGER.error("STT transcription error: %s", err)
            return SpeechResult(
                text="",
                result=SpeechResultState.ERROR,
            )

        if not text:
            return SpeechResult(
                text="",
                result=SpeechResultState.ERROR,
            )

        return SpeechResult(
            text=text.strip(),
            result=SpeechResultState.SUCCESS,
        )

    async def _transcribe(self, wav_data: bytes, language: str | None) -> str:
        """Send audio to Lemonade Server for transcription."""
        session = await self._client._get_session()
        url = f"{self._client.base_url}/v1/audio/transcriptions"

        # Build multipart form data
        form_data = aiohttp.FormData()
        form_data.add_field(
            "file",
            wav_data,
            filename="audio.wav",
            content_type="audio/wav",
        )
        form_data.add_field("model", self._model)

        if language and language != "*":
            form_data.add_field("language", language)

        form_data.add_field("response_format", "json")

        headers = {}
        if self._client._api_key:
            headers["Authorization"] = f"Bearer {self._client._api_key}"

        try:
            async with session.post(
                url,
                data=form_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise LemonadeAPIError(
                        f"Transcription failed ({response.status}): {text}",
                        status=response.status,
                    )
                result = await response.json()
                return result.get("text", "")
        except aiohttp.ClientError as err:
            raise LemonadeAPIError(f"Connection error during STT: {err}") from err

    @staticmethod
    def _convert_to_wav(
        audio_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        bit_rate: int = 16,
    ) -> bytes:
        """Convert raw PCM audio data to WAV format."""
        sample_width = bit_rate // 8
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)

        return buffer.getvalue()
```

# tts.py

```python
"""Text-to-Speech platform for Lemonade Assist."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LemonadeConfigEntry
from .api import LemonadeAPIError, LemonadeServerClient
from .const import (
    CONF_MODEL,
    DOMAIN,
    SUBENTRY_TTS,
)

_LOGGER = logging.getLogger(__name__)

# Default voices available in Piper/Lemonade TTS
DEFAULT_VOICE = "alloy"
SUPPORTED_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

# Lemonade TTS supports many languages through Piper
SUPPORTED_LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "ja",
    "ko", "zh", "ar", "hi", "tr", "vi", "th", "cs", "da", "fi",
    "el", "he", "hu", "id", "ms", "no", "ro", "sk", "sv", "uk",
    "ca", "hr", "bg", "sr", "sl", "et", "lv", "lt",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LemonadeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTS entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TTS:
            continue
        async_add_entities(
            [LemonadeTTSEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LemonadeTTSEntity(TextToSpeechEntity):
    """Lemonade Text-to-Speech entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supports_streaming_input = True

    def __init__(
        self, entry: LemonadeConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the TTS entity."""
        self._entry = entry
        self._subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._client: LemonadeServerClient = entry.runtime_data.client
        self._model = subentry.data.get(CONF_MODEL, "piper")
        self._default_voice = subentry.data.get("voice", DEFAULT_VOICE)
        self._speed = subentry.data.get("speed", 1.0)

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device info."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Lemonade",
            model="Lemonade Server",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._subentry.data.get("language", "en")

    @property
    def supported_options(self) -> list[str]:
        """Return supported options."""
        return [ATTR_VOICE]

    @property
    def default_options(self) -> dict[str, Any]:
        """Return default options."""
        return {ATTR_VOICE: self._default_voice}

    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        return [Voice(voice_id=v, name=v.capitalize()) for v in SUPPORTED_VOICES]

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any],
    ) -> TtsAudioType:
        """Get TTS audio from Lemonade Server."""
        voice = options.get(ATTR_VOICE, self._default_voice)

        try:
            audio_data = await self._synthesize(message, voice, language)
        except LemonadeAPIError as err:
            _LOGGER.error("TTS synthesis error: %s", err)
            raise HomeAssistantError(f"TTS synthesis failed: {err}") from err

        if not audio_data:
            raise HomeAssistantError("Empty audio response from Lemonade Server")

        # Lemonade returns MP3 by default via /v1/audio/speech
        return ("mp3", audio_data)

    async def async_stream_tts_audio(
        self,
        request: Any,
    ) -> AsyncGenerator[bytes, None]:
        """Stream TTS audio from Lemonade Server for voice pipeline."""
        message = request.message
        language = request.language
        options = request.options or {}
        voice = options.get(ATTR_VOICE, self._default_voice)

        session = await self._client._get_session()
        url = f"{self._client.base_url}/v1/audio/speech"

        payload = {
            "model": self._model,
            "input": message,
            "voice": voice,
            "response_format": "mp3",
            "speed": self._speed,
        }

        headers = {"Content-Type": "application/json"}
        if self._client._api_key:
            headers["Authorization"] = f"Bearer {self._client._api_key}"

        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise HomeAssistantError(
                        f"TTS stream error ({response.status}): {text}"
                    )

                # Stream audio chunks as they arrive
                async for chunk in response.content.iter_chunked(4096):
                    if chunk:
                        yield chunk
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                f"TTS streaming connection error: {err}"
            ) from err

    async def _synthesize(
        self, message: str, voice: str, language: str
    ) -> bytes:
        """Send text to Lemonade Server for speech synthesis."""
        session = await self._client._get_session()
        url = f"{self._client.base_url}/v1/audio/speech"

        payload = {
            "model": self._model,
            "input": message,
            "voice": voice,
            "response_format": "mp3",
            "speed": self._speed,
        }

        headers = {"Content-Type": "application/json"}
        if self._client._api_key:
            headers["Authorization"] = f"Bearer {self._client._api_key}"

        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise LemonadeAPIError(
                        f"TTS synthesis failed ({response.status}): {text}",
                        status=response.status,
                    )
                return await response.read()
        except aiohttp.ClientError as err:
            raise LemonadeAPIError(
                f"Connection error during TTS: {err}"
            ) from err
```

# ACTUALIZACIONES para STT/TTS

# Cambios necesarios en archivos existentes para habilitar STT/TTS
## 1\. Actualizar `manifest.json`
Agregar `stt` y `tts` a las plataformas:

```json
{
  "domain": "lemonade_assist",
  "name": "Lemonade Assist",
  "codeowners": ["@nemesis-group"],
  "config_flow": true,
  "dependencies": ["conversation", "ai_task"],
  "documentation": "https://github.com/nemesis-group/lemonade-assist",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/nemesis-group/lemonade-assist/issues",
  "requirements": ["aiohttp>=3.9.0"],
  "version": "1.0.0",
  "integration_type": "service"
}
```

(manifest no necesita declarar platforms, se autodescubren)

* * *
## 2\. Actualizar `const.py` - agregar estas constantes:

```python
# Subentry types (agregar)
SUBENTRY_STT: Final = "stt"
SUBENTRY_TTS: Final = "tts"

# Defaults STT/TTS
DEFAULT_STT_MODEL: Final = "whisper-large-v3-turbo"
DEFAULT_TTS_MODEL: Final = "piper"
DEFAULT_TTS_VOICE: Final = "alloy"
DEFAULT_TTS_SPEED: Final = 1.0
```

* * *
## 3\. Actualizar `__init__.py` - agregar plataformas:

```python
# Cambiar la lista PLATFORMS:
PLATFORMS: list[Platform] = [
    Platform.CONVERSATION,
    Platform.SENSOR,
    Platform.STT,
    Platform.TTS,
]
```

* * *
## 4\. Actualizar `config_flow.py` - agregar subentry flows para STT y TTS:

```python
from .const import (
    # ... agregar:
    SUBENTRY_STT,
    SUBENTRY_TTS,
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DEFAULT_TTS_SPEED,
)

# En LemonadeAssistConfigFlow.async_get_subentry_flow, agregar:
    @classmethod
    @callback
    def async_get_subentry_flow(
        cls, config_entry: ConfigEntry, subentry_type: str
    ) -> ConfigSubentryFlow:
        """Get the subentry flow for the given type."""
        if subentry_type == SUBENTRY_CONVERSATION:
            return ConversationSubentryFlow()
        if subentry_type == SUBENTRY_AI_TASK:
            return AITaskSubentryFlow()
        if subentry_type == SUBENTRY_STT:
            return STTSubentryFlow()
        if subentry_type == SUBENTRY_TTS:
            return TTSSubentryFlow()
        raise ValueError(f"Unknown subentry type: {subentry_type}")


# Agregar estas clases al final del archivo:

class STTSubentryFlow(ConfigSubentryFlow):
    """Handle STT subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle STT subentry creation."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_MODEL, "Lemonade STT"),
                data={
                    CONF_MODEL: user_input[CONF_MODEL],
                },
            )

        # Fetch models with transcription label
        entry = self._get_entry()
        client = entry.runtime_data.client
        try:
            models = await client.get_available_model_names()
            # Filter for whisper/transcription models
            stt_models = [m for m in models if "whisper" in m.lower() or "transcri" in m.lower()]
            if not stt_models:
                stt_models = models  # fallback: show all
        except Exception:
            stt_models = [DEFAULT_STT_MODEL]

        model_options = [SelectOptionDict(value=m, label=m) for m in stt_models]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=DEFAULT_STT_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=model_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                }
            ),
        )


class TTSSubentryFlow(ConfigSubentryFlow):
    """Handle TTS subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle TTS subentry creation."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_MODEL, "Lemonade TTS"),
                data={
                    CONF_MODEL: user_input[CONF_MODEL],
                    "voice": user_input.get("voice", DEFAULT_TTS_VOICE),
                    "speed": user_input.get("speed", DEFAULT_TTS_SPEED),
                    "language": user_input.get("language", "en"),
                },
            )

        # Available TTS voices
        voice_options = [
            SelectOptionDict(value=v, label=v.capitalize())
            for v in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL, default=DEFAULT_TTS_MODEL): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                    vol.Optional("voice", default=DEFAULT_TTS_VOICE): SelectSelector(
                        SelectSelectorConfig(
                            options=voice_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("speed", default=DEFAULT_TTS_SPEED): NumberSelector(
                        NumberSelectorConfig(
                            min=0.25, max=4.0, step=0.25, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional("language", default="en"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                }
            ),
        )
```

* * *
## 5\. Actualizar `strings.json` - agregar secciones STT/TTS:

```json
{
  "config_subentries": {
    "stt": {
      "initiate_flow": {
        "user": "Add speech-to-text"
      },
      "step": {
        "user": {
          "title": "Add Speech-to-Text",
          "description": "Configure STT using Whisper on Lemonade Server.",
          "data": {
            "model": "Whisper Model"
          }
        }
      }
    },
    "tts": {
      "initiate_flow": {
        "user": "Add text-to-speech"
      },
      "step": {
        "user": {
          "title": "Add Text-to-Speech",
          "description": "Configure TTS using Piper on Lemonade Server.",
          "data": {
            "model": "TTS Model",
            "voice": "Voice",
            "speed": "Speed",
            "language": "Language"
          }
        }
      }
    }
  }
}
```

* * *
## 6\. Crear carpeta `translations/` y agregar las mismas keys en `translations/en.json`
Misma estructura que strings.json para STT/TTS subentries.

* * *
## Pipeline Voice Assist completo
Con estos archivos, el pipeline de voz queda:

```plain
Micrófono → [Wyoming VAD] → Lemonade STT (Whisper) → Lemonade Conversation Agent → Lemonade TTS (Piper) → Altavoz
```

Todo local, todo corriendo en un solo servidor Lemonade.

Para configurar el pipeline en HA:
1. Settings → Voice Assistants → Add Assistant
2. STT: seleccionar "Lemonade STT"
3. Conversation Agent: seleccionar "Lemonade Conversation"
4. TTS: seleccionar "Lemonade TTS"

El streaming de TTS permite que el audio empiece a reproducirse antes de que termine la generación completa, reduciendo la latencia percibida.

# rag.py

```python
"""RAG (Retrieval Augmented Generation) module for Lemonade Assist.

Provides semantic search over Home Assistant entities, areas, and custom
knowledge documents using Lemonade Server's /v1/embeddings endpoint
and optional /v1/reranking for improved relevance.

Stores vectors locally in a simple JSON-based store (no external DB required).
For production scale, can be extended to use ChromaDB or similar.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, device_registry, entity_registry

from .api import LemonadeAPIError, LemonadeServerClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# RAG Configuration
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_RERANK_MODEL = "bge-reranker-v2-m3"
DEFAULT_TOP_K = 10
DEFAULT_RERANK_TOP_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.3
MAX_CHUNK_SIZE = 512  # tokens approx
OVERLAP_SIZE = 50


@dataclass
class Document:
    """A document chunk with its embedding."""

    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    source: str = ""  # entity, area, knowledge, automation, etc.


@dataclass
class SearchResult:
    """A search result with relevance score."""

    document: Document
    score: float
    rerank_score: float | None = None


class VectorStore:
    """Simple local vector store using JSON persistence."""

    def __init__(self, storage_path: Path) -> None:
        """Initialize the vector store."""
        self._storage_path = storage_path
        self._documents: dict[str, Document] = {}
        self._dirty = False

    async def load(self) -> None:
        """Load documents from disk."""
        if not self._storage_path.exists():
            return

        try:
            data = await asyncio.to_thread(
                self._storage_path.read_text, encoding="utf-8"
            )
            raw = json.loads(data)
            for doc_data in raw.get("documents", []):
                doc = Document(
                    id=doc_data["id"],
                    content=doc_data["content"],
                    metadata=doc_data.get("metadata", {}),
                    embedding=doc_data.get("embedding"),
                    source=doc_data.get("source", ""),
                )
                self._documents[doc.id] = doc
            _LOGGER.debug("Loaded %d documents from store", len(self._documents))
        except (json.JSONDecodeError, OSError) as err:
            _LOGGER.warning("Failed to load vector store: %s", err)

    async def save(self) -> None:
        """Save documents to disk."""
        if not self._dirty:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "documents": [
                {
                    "id": doc.id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "embedding": doc.embedding,
                    "source": doc.source,
                }
                for doc in self._documents.values()
            ]
        }

        await asyncio.to_thread(
            self._storage_path.write_text,
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )
        self._dirty = False

    def add_document(self, document: Document) -> None:
        """Add or update a document."""
        self._documents[document.id] = document
        self._dirty = True

    def remove_document(self, doc_id: str) -> None:
        """Remove a document."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            self._dirty = True

    def get_all_documents(self) -> list[Document]:
        """Get all documents."""
        return list(self._documents.values())

    def get_documents_by_source(self, source: str) -> list[Document]:
        """Get documents filtered by source."""
        return [d for d in self._documents.values() if d.source == source]

    def clear_source(self, source: str) -> None:
        """Remove all documents of a given source."""
        to_remove = [d.id for d in self._documents.values() if d.source == source]
        for doc_id in to_remove:
            del self._documents[doc_id]
        if to_remove:
            self._dirty = True

    @property
    def count(self) -> int:
        """Return document count."""
        return len(self._documents)


class RAGEngine:
    """RAG engine for Lemonade Assist.

    Handles embedding generation, similarity search, reranking,
    and context injection into LLM prompts.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: LemonadeServerClient,
        storage_path: Path | None = None,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        rerank_model: str = DEFAULT_RERANK_MODEL,
        top_k: int = DEFAULT_TOP_K,
        rerank_top_k: int = DEFAULT_RERANK_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        """Initialize RAG engine."""
        self.hass = hass
        self._client = client
        self._embedding_model = embedding_model
        self._rerank_model = rerank_model
        self._top_k = top_k
        self._rerank_top_k = rerank_top_k
        self._similarity_threshold = similarity_threshold

        if storage_path is None:
            storage_path = Path(hass.config.path(".storage")) / f"{DOMAIN}_rag.json"
        self._store = VectorStore(storage_path)
        self._initialized = False

    async def async_initialize(self) -> None:
        """Initialize the RAG engine."""
        await self._store.load()
        self._initialized = True
        _LOGGER.info(
            "RAG engine initialized with %d documents", self._store.count
        )

    async def async_shutdown(self) -> None:
        """Shutdown and persist."""
        await self._store.save()

    # ─── Embedding ────────────────────────────────────────────────────

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for a text."""
        try:
            result = await self._client.get_embeddings(
                input_text=text, model=self._embedding_model
            )
            data = result.get("data", [])
            if data:
                return data[0].get("embedding", [])
            return []
        except LemonadeAPIError as err:
            _LOGGER.error("Embedding error: %s", err)
            return []

    async def _get_embeddings_batch(
        self, texts: list[str]
    ) -> list[list[float]]:
        """Get embeddings for multiple texts."""
        try:
            result = await self._client.get_embeddings(
                input_text=texts, model=self._embedding_model
            )
            data = result.get("data", [])
            # Sort by index to ensure order
            data.sort(key=lambda x: x.get("index", 0))
            return [d.get("embedding", []) for d in data]
        except LemonadeAPIError as err:
            _LOGGER.error("Batch embedding error: %s", err)
            return [[] for _ in texts]

    # ─── Similarity ───────────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b:
            return 0.0
        a_arr = np.array(a, dtype=np.float32)
        b_arr = np.array(b, dtype=np.float32)
        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    # ─── Reranking ────────────────────────────────────────────────────

    async def _rerank(
        self, query: str, documents: list[SearchResult]
    ) -> list[SearchResult]:
        """Rerank results using Lemonade's /v1/reranking endpoint."""
        if not documents:
            return documents

        try:
            session = await self._client._get_session()
            url = f"{self._client.base_url}/v1/reranking"

            payload = {
                "model": self._rerank_model,
                "query": query,
                "documents": [r.document.content for r in documents],
                "top_n": self._rerank_top_k,
            }

            headers = {"Content-Type": "application/json"}
            if self._client._api_key:
                headers["Authorization"] = f"Bearer {self._client._api_key}"

            async with session.post(
                url, json=payload, headers=headers
            ) as response:
                if response.status >= 400:
                    _LOGGER.warning("Reranking failed, using similarity scores")
                    return documents[: self._rerank_top_k]

                result = await response.json()
                results_data = result.get("results", [])

                # Map rerank scores back to documents
                reranked = []
                for item in results_data:
                    idx = item.get("index", 0)
                    score = item.get("relevance_score", 0)
                    if idx < len(documents):
                        doc_result = documents[idx]
                        doc_result.rerank_score = score
                        reranked.append(doc_result)

                # Sort by rerank score descending
                reranked.sort(
                    key=lambda x: x.rerank_score or 0, reverse=True
                )
                return reranked[: self._rerank_top_k]

        except Exception as err:
            _LOGGER.warning("Reranking error: %s, using similarity", err)
            return documents[: self._rerank_top_k]

    # ─── Search ───────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        use_rerank: bool = True,
        source_filter: str | None = None,
    ) -> list[SearchResult]:
        """Search for relevant documents."""
        if not self._initialized:
            await self.async_initialize()

        top_k = top_k or self._top_k

        # Get query embedding
        query_embedding = await self._get_embedding(query)
        if not query_embedding:
            return []

        # Get candidate documents
        documents = self._store.get_all_documents()
        if source_filter:
            documents = [d for d in documents if d.source == source_filter]

        # Compute similarities
        results: list[SearchResult] = []
        for doc in documents:
            if not doc.embedding:
                continue
            score = self._cosine_similarity(query_embedding, doc.embedding)
            if score >= self._similarity_threshold:
                results.append(SearchResult(document=doc, score=score))

        # Sort by similarity
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:top_k]

        # Optionally rerank
        if use_rerank and results:
            results = await self._rerank(query, results)

        return results

    # ─── Indexing ─────────────────────────────────────────────────────

    async def index_document(
        self,
        content: str,
        doc_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        source: str = "knowledge",
    ) -> str:
        """Index a single document."""
        if not doc_id:
            doc_id = hashlib.md5(content.encode()).hexdigest()

        embedding = await self._get_embedding(content)

        doc = Document(
            id=doc_id,
            content=content,
            metadata=metadata or {},
            embedding=embedding,
            source=source,
        )
        self._store.add_document(doc)
        await self._store.save()
        return doc_id

    async def index_documents(
        self,
        documents: list[dict[str, Any]],
        source: str = "knowledge",
    ) -> int:
        """Batch index multiple documents."""
        texts = [d["content"] for d in documents]
        embeddings = await self._get_embeddings_batch(texts)

        count = 0
        for doc_data, embedding in zip(documents, embeddings):
            doc_id = doc_data.get("id") or hashlib.md5(
                doc_data["content"].encode()
            ).hexdigest()
            doc = Document(
                id=doc_id,
                content=doc_data["content"],
                metadata=doc_data.get("metadata", {}),
                embedding=embedding,
                source=source,
            )
            self._store.add_document(doc)
            count += 1

        await self._store.save()
        return count

    async def index_ha_entities(self) -> int:
        """Index Home Assistant entities for semantic search."""
        ent_reg = entity_registry.async_get(self.hass)
        area_reg = area_registry.async_get(self.hass)
        dev_reg = device_registry.async_get(self.hass)

        # Clear old entity documents
        self._store.clear_source("entity")

        documents: list[dict[str, Any]] = []

        for entity in ent_reg.entities.values():
            if entity.disabled:
                continue

            state = self.hass.states.get(entity.entity_id)
            if not state:
                continue

            # Build rich description
            parts = []
            name = state.name or entity.entity_id
            parts.append(f"Entity: {name}")
            parts.append(f"ID: {entity.entity_id}")
            parts.append(f"Domain: {entity.domain}")
            parts.append(f"State: {state.state}")

            if entity.area_id:
                area = area_reg.async_get_area(entity.area_id)
                if area:
                    parts.append(f"Area: {area.name}")

            if entity.device_id:
                device = dev_reg.async_get(entity.device_id)
                if device and device.name:
                    parts.append(f"Device: {device.name}")

            # Include key attributes
            attrs = state.attributes
            if "friendly_name" in attrs:
                parts.append(f"Name: {attrs['friendly_name']}")
            if "device_class" in attrs:
                parts.append(f"Type: {attrs['device_class']}")

            content = ". ".join(parts)

            documents.append(
                {
                    "id": f"entity_{entity.entity_id}",
                    "content": content,
                    "metadata": {
                        "entity_id": entity.entity_id,
                        "domain": entity.domain,
                        "area_id": entity.area_id,
                        "state": state.state,
                    },
                }
            )

        if documents:
            count = await self.index_documents(documents, source="entity")
            _LOGGER.info("Indexed %d HA entities for RAG", count)
            return count
        return 0

    async def index_areas(self) -> int:
        """Index Home Assistant areas."""
        area_reg = area_registry.async_get(self.hass)

        self._store.clear_source("area")

        documents: list[dict[str, Any]] = []
        for area in area_reg.async_list_areas():
            content = f"Area: {area.name}"
            if area.aliases:
                content += f". Also known as: {', '.join(area.aliases)}"

            documents.append(
                {
                    "id": f"area_{area.id}",
                    "content": content,
                    "metadata": {"area_id": area.id, "name": area.name},
                }
            )

        if documents:
            count = await self.index_documents(documents, source="area")
            _LOGGER.info("Indexed %d areas for RAG", count)
            return count
        return 0

    # ─── Context Building ─────────────────────────────────────────────

    async def build_context(
        self,
        query: str,
        max_tokens: int = 2000,
        include_entities: bool = True,
        include_knowledge: bool = True,
    ) -> str:
        """Build RAG context string to inject into the LLM prompt."""
        results = await self.search(query)

        if not results:
            return ""

        context_parts = []
        token_estimate = 0

        for result in results:
            chunk = result.document.content
            chunk_tokens = len(chunk.split()) * 1.3  # rough estimate

            if token_estimate + chunk_tokens > max_tokens:
                break

            source_label = result.document.source.upper()
            score_label = f"{result.rerank_score or result.score:.2f}"
            context_parts.append(
                f"[{source_label} | relevance: {score_label}] {chunk}"
            )
            token_estimate += chunk_tokens

        if not context_parts:
            return ""

        return (
            "
--- Relevant Context (RAG) ---
"
            + "
".join(context_parts)
            + "
--- End Context ---
"
        )

    # ─── Management ───────────────────────────────────────────────────

    async def clear_all(self) -> None:
        """Clear all documents."""
        self._store._documents.clear()
        self._store._dirty = True
        await self._store.save()

    async def clear_source(self, source: str) -> None:
        """Clear documents by source."""
        self._store.clear_source(source)
        await self._store.save()

    @property
    def document_count(self) -> int:
        """Return total document count."""
        return self._store.count

    def get_stats(self) -> dict[str, Any]:
        """Get RAG statistics."""
        docs = self._store.get_all_documents()
        sources: dict[str, int] = {}
        for doc in docs:
            sources[doc.source] = sources.get(doc.source, 0) + 1

        return {
            "total_documents": len(docs),
            "sources": sources,
            "embedding_model": self._embedding_model,
            "rerank_model": self._rerank_model,
            "storage_path": str(self._storage_path),
        }
```

# mcp.py

```python
"""MCP (Model Context Protocol) client for Lemonade Assist.

Connects to Lemonade Server's MCP Gateway (/mcp) to expose
Lemonade's tools (chat, transcribe, image gen, omni) as callable
capabilities within Home Assistant.

This module acts as an MCP client that can:
1. Discover available tools on the Lemonade MCP server
2. Call tools (lemonade_chat, lemonade_transcribe_audio, etc.)
3. Expose MCP tools to the conversation agent for advanced orchestration
4. Route requests to local models without going through OpenAI-compat API
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant

from .api import LemonadeAPIError, LemonadeServerClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# MCP Protocol version
MCP_PROTOCOL_VERSION = "2025-06-18"


class MCPError(Exception):
    """MCP protocol error."""

    def __init__(self, code: int, message: str) -> None:
        """Initialize."""
        super().__init__(message)
        self.code = code


class MCPTool:
    """Representation of an MCP tool."""

    def __init__(self, name: str, description: str, schema: dict[str, Any]) -> None:
        """Initialize."""
        self.name = name
        self.description = description
        self.input_schema = schema

    def __repr__(self) -> str:
        """Representation."""
        return f"MCPTool(name={self.name!r})"


class LemonadeMCPClient:
    """Client for Lemonade Server's MCP Gateway.

    Implements the MCP Streamable HTTP transport to interact
    with Lemonade's tool capabilities.
    """

    def __init__(
        self,
        client: LemonadeServerClient,
    ) -> None:
        """Initialize MCP client."""
        self._client = client
        self._mcp_url = f"{client.base_url}/mcp"
        self._request_id = 0
        self._initialized = False
        self._tools: list[MCPTool] = []
        self._server_info: dict[str, Any] = {}

    @property
    def is_initialized(self) -> bool:
        """Return whether the client has been initialized."""
        return self._initialized

    @property
    def tools(self) -> list[MCPTool]:
        """Return discovered tools."""
        return self._tools

    def _next_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    async def _send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a JSON-RPC 2.0 request to the MCP endpoint."""
        session = await self._client._get_session()

        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            payload["params"] = params

        headers = {"Content-Type": "application/json"}
        if self._client._api_key:
            headers["Authorization"] = f"Bearer {self._client._api_key}"

        try:
            async with session.post(
                self._mcp_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise MCPError(
                        response.status,
                        f"MCP request failed ({response.status}): {text}",
                    )
                result = await response.json()

                # Check for JSON-RPC error
                if "error" in result:
                    error = result["error"]
                    raise MCPError(
                        error.get("code", -1),
                        error.get("message", "Unknown MCP error"),
                    )

                return result.get("result", {})

        except aiohttp.ClientError as err:
            raise MCPError(-1, f"MCP connection error: {err}") from err

    async def _send_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        """Send a JSON-RPC 2.0 notification (no id, no response expected)."""
        session = await self._client._get_session()

        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            payload["params"] = params

        headers = {"Content-Type": "application/json"}
        if self._client._api_key:
            headers["Authorization"] = f"Bearer {self._client._api_key}"

        try:
            async with session.post(
                self._mcp_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                # Notifications don't require a response
                pass
        except aiohttp.ClientError:
            pass  # Best effort for notifications

    # ─── Protocol Methods ─────────────────────────────────────────────

    async def initialize(self) -> dict[str, Any]:
        """Initialize the MCP session."""
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "lemonade_assist",
                    "version": "1.0.0",
                },
            },
        )

        self._server_info = result.get("serverInfo", {})

        # Send initialized notification
        await self._send_notification("notifications/initialized")

        self._initialized = True
        _LOGGER.info(
            "MCP session initialized with server: %s",
            self._server_info.get("name", "unknown"),
        )

        return result

    async def ping(self) -> bool:
        """Ping the MCP server."""
        try:
            await self._send_request("ping")
            return True
        except MCPError:
            return False

    async def list_tools(self) -> list[MCPTool]:
        """Discover available tools on the server."""
        result = await self._send_request("tools/list")

        tools_data = result.get("tools", [])
        self._tools = []

        for tool_data in tools_data:
            tool = MCPTool(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                schema=tool_data.get("inputSchema", {}),
            )
            self._tools.append(tool)

        _LOGGER.debug("Discovered %d MCP tools", len(self._tools))
        return self._tools

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call an MCP tool."""
        result = await self._send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )

        # Check for tool-level errors
        if result.get("isError"):
            content = result.get("content", [])
            error_msg = ""
            for block in content:
                if block.get("type") == "text":
                    error_msg = block.get("text", "Unknown tool error")
                    break
            raise MCPError(-1, f"Tool error: {error_msg}")

        return result

    # ─── High-Level Tool Wrappers ─────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Call lemonade_chat via MCP."""
        arguments: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if model:
            arguments["model"] = model

        result = await self.call_tool("lemonade_chat", arguments)

        # Extract text from content blocks
        content = result.get("content", [])
        for block in content:
            if block.get("type") == "text":
                return block.get("text", "")
        return ""

    async def list_models(self) -> dict[str, Any]:
        """Call lemonade_list_models via MCP."""
        result = await self.call_tool(
            "lemonade_list_models",
            {"include_available": True, "include_suggested": True},
        )

        content = result.get("content", [])
        for block in content:
            if block.get("type") == "text":
                text = block.get("text", "")
                # Try to parse JSON block
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}
        return {}

    async def transcribe(
        self,
        audio_path: str,
        model: str = "Whisper-Large-v3-Turbo",
        response_format: str = "json",
    ) -> str:
        """Call lemonade_transcribe_audio via MCP."""
        result = await self.call_tool(
            "lemonade_transcribe_audio",
            {
                "model": model,
                "audio_path": audio_path,
                "response_format": response_format,
            },
        )

        content = result.get("content", [])
        for block in content:
            if block.get("type") == "text":
                return block.get("text", "")
        return ""

    async def generate_image(
        self,
        prompt: str,
        model: str = "SDXL-Turbo",
        size: str = "512x512",
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Call lemonade_generate_image via MCP."""
        arguments: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
        }
        if output_path:
            arguments["output_path"] = output_path

        return await self.call_tool("lemonade_generate_image", arguments)

    async def omni(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        """Call lemonade_omni via MCP for multimodal tasks."""
        arguments: dict[str, Any] = {"messages": messages}
        if model:
            arguments["model"] = model
        if output_dir:
            arguments["output_dir"] = output_dir

        return await self.call_tool("lemonade_omni", arguments)

    # ─── Integration with Conversation Agent ───────────────────────────

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format for the LLM."""
        openai_tools = []
        for tool in self._tools:
            # Skip lemonade_chat as we handle that through the main pipeline
            if tool.name == "lemonade_chat":
                continue

            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": f"mcp_{tool.name}",
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
            )
        return openai_tools

    async def handle_tool_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle a tool call from the conversation agent.

        Strips the 'mcp_' prefix and routes to the MCP server.
        """
        # Strip mcp_ prefix if present
        actual_name = tool_name
        if tool_name.startswith("mcp_"):
            actual_name = tool_name[4:]

        try:
            result = await self.call_tool(actual_name, arguments)

            # Extract text content for the LLM
            content = result.get("content", [])
            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "image":
                    text_parts.append("[Image generated successfully]")
                elif block.get("type") == "audio":
                    text_parts.append("[Audio generated successfully]")

            return {"result": "
".join(text_parts) if text_parts else "Done"}

        except MCPError as err:
            return {"error": str(err)}


class MCPManager:
    """Manages MCP client lifecycle for the integration."""

    def __init__(
        self, hass: HomeAssistant, client: LemonadeServerClient
    ) -> None:
        """Initialize MCP manager."""
        self.hass = hass
        self._mcp_client = LemonadeMCPClient(client)
        self._available = False

    @property
    def is_available(self) -> bool:
        """Return if MCP is available."""
        return self._available

    @property
    def client(self) -> LemonadeMCPClient:
        """Return the MCP client."""
        return self._mcp_client

    async def async_setup(self) -> bool:
        """Set up MCP connection."""
        try:
            await self._mcp_client.initialize()
            await self._mcp_client.list_tools()
            self._available = True
            _LOGGER.info(
                "MCP Gateway connected. %d tools available.",
                len(self._mcp_client.tools),
            )
            return True
        except (MCPError, Exception) as err:
            _LOGGER.warning(
                "MCP Gateway not available: %s. MCP features disabled.", err
            )
            self._available = False
            return False

    async def async_refresh_tools(self) -> None:
        """Refresh the tool list."""
        if not self._available:
            return
        try:
            await self._mcp_client.list_tools()
        except MCPError as err:
            _LOGGER.warning("Failed to refresh MCP tools: %s", err)

    def get_extra_tools_for_agent(self) -> list[dict[str, Any]]:
        """Get MCP tools formatted for the conversation agent."""
        if not self._available:
            return []
        return self._mcp_client.get_tools_for_llm()

    async def handle_agent_tool_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Route a tool call from the agent to MCP."""
        if not self._available:
            return {"error": "MCP not available"}
        return await self._mcp_client.handle_tool_call(tool_name, arguments)
```

# INTEGRACIÓN RAG/MCP en el agente

# Integración de RAG y MCP en el Conversation Agent
Este documento describe cómo conectar `rag.py` y `mcp.py` con el agente de conversación existente.

* * *
## 1\. Actualizar `__init__.py`
Agregar inicialización de RAG y MCP en `async_setup_entry`:

```python
# Agregar imports al inicio de __init__.py:
from .rag import RAGEngine
from .mcp import MCPManager
from .const import CONF_RAG_ENABLED, CONF_MCP_ENABLED

# Actualizar LemonadeData para incluir RAG y MCP:
class LemonadeData:
    """Runtime data for Lemonade Assist."""

    def __init__(
        self,
        client: LemonadeServerClient,
        health_coordinator: LemonadeHealthCoordinator,
        stats_coordinator: LemonadeStatsCoordinator,
        rag_engine: RAGEngine | None = None,
        mcp_manager: MCPManager | None = None,
    ) -> None:
        """Initialize runtime data."""
        self.client = client
        self.health_coordinator = health_coordinator
        self.stats_coordinator = stats_coordinator
        self.rag_engine = rag_engine
        self.mcp_manager = mcp_manager


# En async_setup_entry, después de los coordinators:

    # Set up RAG engine
    rag_engine: RAGEngine | None = None
    if entry.options.get(CONF_RAG_ENABLED, False):
        rag_engine = RAGEngine(hass, client)
        await rag_engine.async_initialize()
        # Index entities on first setup
        await rag_engine.index_ha_entities()
        await rag_engine.index_areas()

    # Set up MCP
    mcp_manager: MCPManager | None = None
    if entry.options.get(CONF_MCP_ENABLED, False):
        mcp_manager = MCPManager(hass, client)
        await mcp_manager.async_setup()

    # Store runtime data
    entry.runtime_data = LemonadeData(
        client=client,
        health_coordinator=health_coordinator,
        stats_coordinator=stats_coordinator,
        rag_engine=rag_engine,
        mcp_manager=mcp_manager,
    )
```

* * *
## 2\. Actualizar `conversation.py`
Modificar `async_handle_chat_log` para inyectar contexto RAG y tools MCP:

```python
# En la clase LemonadeConversationEntity, modificar async_handle_chat_log:

    @override
    async def async_handle_chat_log(
        self,
        chat_log: ChatLog,
    ) -> None:
        """Handle a chat log interaction with Lemonade Server."""
        # Get LLM API if configured
        llm_api: llm.APIInstance | None = None
        tools: list[dict] | None = None

        llm_api_id = self._subentry.data.get(CONF_LLM_HASS_API)
        if llm_api_id:
            try:
                llm_api = await llm.async_get_api(
                    self.hass, llm_api_id, chat_log,
                )
            except llm.NoAPIFound:
                _LOGGER.warning("LLM API %s not found", llm_api_id)

        if llm_api:
            tools = self._format_tools_for_openai(llm_api.tools)

        # --- MCP: Add MCP tools if enabled ---
        mcp_manager = self._entry.runtime_data.mcp_manager
        if mcp_manager and mcp_manager.is_available:
            mcp_tools = mcp_manager.get_extra_tools_for_agent()
            if mcp_tools:
                if tools is None:
                    tools = []
                tools.extend(mcp_tools)

        # Build system prompt
        system_prompt = self._system_prompt
        if llm_api and llm_api.prompt:
            system_prompt = llm_api.prompt

        # --- RAG: Inject relevant context ---
        rag_engine = self._entry.runtime_data.rag_engine
        if rag_engine:
            # Get the user's last message for context search
            user_query = ""
            for content in reversed(chat_log.content):
                if isinstance(content, UserContent):
                    user_query = content.content
                    break

            if user_query:
                rag_context = await rag_engine.build_context(user_query)
                if rag_context:
                    system_prompt += "
" + rag_context

        # Build messages from chat log
        messages = self._build_messages(chat_log, self._max_history)
        messages.insert(0, {"role": "system", "content": system_prompt})

        # Use streaming handler
        await self._async_handle_chat_log_streaming(
            chat_log=chat_log,
            messages=messages,
            tools=tools,
            llm_api=llm_api,
        )
```

* * *
## 3\. Actualizar `entity.py` - handle MCP tool calls
En el loop de tool calls de `_async_handle_chat_log_streaming`, agregar routing a MCP:

```python
# En el loop de tool calls, antes de llamar a llm_api.async_call_tool:

                    # Check if this is an MCP tool
                    mcp_manager = self._entry.runtime_data.mcp_manager
                    if func_name.startswith("mcp_") and mcp_manager:
                        tool_result = await mcp_manager.handle_agent_tool_call(
                            func_name, func_args
                        )
                    else:
                        # Standard HA tool call
                        try:
                            tool_result = await llm_api.async_call_tool(
                                llm.ToolInput(
                                    tool_name=func_name,
                                    tool_args=func_args,
                                )
                            )
                        except (HomeAssistantError, llm.ToolError) as tool_err:
                            tool_result = {"error": str(tool_err)}
```

* * *
## 4\. Agregar servicios RAG en `services.py`

```python
# Agregar estos servicios:

SERVICE_RAG_INDEX = "rag_index_entities"
SERVICE_RAG_ADD_DOCUMENT = "rag_add_document"
SERVICE_RAG_SEARCH = "rag_search"
SERVICE_RAG_CLEAR = "rag_clear"
SERVICE_RAG_STATS = "rag_stats"
SERVICE_MCP_LIST_TOOLS = "mcp_list_tools"
SERVICE_MCP_CALL_TOOL = "mcp_call_tool"

RAG_ADD_DOCUMENT_SCHEMA = vol.Schema(
    {
        vol.Required("content"): cv.string,
        vol.Optional("doc_id"): cv.string,
        vol.Optional("source", default="knowledge"): cv.string,
    }
)

RAG_SEARCH_SCHEMA = vol.Schema(
    {
        vol.Required("query"): cv.string,
        vol.Optional("top_k", default=5): vol.Coerce(int),
        vol.Optional("use_rerank", default=True): cv.boolean,
    }
)

MCP_CALL_TOOL_SCHEMA = vol.Schema(
    {
        vol.Required("tool_name"): cv.string,
        vol.Required("arguments"): dict,
    }
)


# Service handlers:

    async def handle_rag_index(call: ServiceCall) -> ServiceResponse:
        """Re-index HA entities for RAG."""
        rag = entry.runtime_data.rag_engine
        if not rag:
            raise ValueError("RAG is not enabled")
        entity_count = await rag.index_ha_entities()
        area_count = await rag.index_areas()
        return {"entities_indexed": entity_count, "areas_indexed": area_count}

    async def handle_rag_add_document(call: ServiceCall) -> ServiceResponse:
        """Add a custom document to RAG."""
        rag = entry.runtime_data.rag_engine
        if not rag:
            raise ValueError("RAG is not enabled")
        doc_id = await rag.index_document(
            content=call.data["content"],
            doc_id=call.data.get("doc_id"),
            source=call.data.get("source", "knowledge"),
        )
        return {"doc_id": doc_id}

    async def handle_rag_search(call: ServiceCall) -> ServiceResponse:
        """Search RAG documents."""
        rag = entry.runtime_data.rag_engine
        if not rag:
            raise ValueError("RAG is not enabled")
        results = await rag.search(
            query=call.data["query"],
            top_k=call.data.get("top_k", 5),
            use_rerank=call.data.get("use_rerank", True),
        )
        return {
            "results": [
                {
                    "content": r.document.content,
                    "score": r.score,
                    "rerank_score": r.rerank_score,
                    "source": r.document.source,
                    "metadata": r.document.metadata,
                }
                for r in results
            ]
        }

    async def handle_rag_clear(call: ServiceCall) -> None:
        """Clear RAG documents."""
        rag = entry.runtime_data.rag_engine
        if not rag:
            raise ValueError("RAG is not enabled")
        await rag.clear_all()

    async def handle_rag_stats(call: ServiceCall) -> ServiceResponse:
        """Get RAG statistics."""
        rag = entry.runtime_data.rag_engine
        if not rag:
            raise ValueError("RAG is not enabled")
        return rag.get_stats()

    async def handle_mcp_list_tools(call: ServiceCall) -> ServiceResponse:
        """List available MCP tools."""
        mcp = entry.runtime_data.mcp_manager
        if not mcp or not mcp.is_available:
            raise ValueError("MCP is not available")
        tools = mcp.client.tools
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                }
                for t in tools
            ]
        }

    async def handle_mcp_call_tool(call: ServiceCall) -> ServiceResponse:
        """Call an MCP tool directly."""
        mcp = entry.runtime_data.mcp_manager
        if not mcp or not mcp.is_available:
            raise ValueError("MCP is not available")
        result = await mcp.client.call_tool(
            call.data["tool_name"],
            call.data["arguments"],
        )
        return result


# Registrar los servicios (dentro del bloque de registro existente):

        hass.services.async_register(
            DOMAIN,
            SERVICE_RAG_INDEX,
            handle_rag_index,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_RAG_ADD_DOCUMENT,
            handle_rag_add_document,
            schema=RAG_ADD_DOCUMENT_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_RAG_SEARCH,
            handle_rag_search,
            schema=RAG_SEARCH_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_RAG_CLEAR,
            handle_rag_clear,
            schema=vol.Schema({}),
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_RAG_STATS,
            handle_rag_stats,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_MCP_LIST_TOOLS,
            handle_mcp_list_tools,
            schema=vol.Schema({}),
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_MCP_CALL_TOOL,
            handle_mcp_call_tool,
            schema=MCP_CALL_TOOL_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
```

* * *
## 5\. Actualizar `const.py` - agregar constantes RAG/MCP

```python
# RAG Configuration
CONF_RAG_EMBEDDING_MODEL: Final = "rag_embedding_model"
CONF_RAG_RERANK_MODEL: Final = "rag_rerank_model"
CONF_RAG_TOP_K: Final = "rag_top_k"
CONF_RAG_AUTO_INDEX: Final = "rag_auto_index"

DEFAULT_RAG_EMBEDDING_MODEL: Final = "nomic-embed-text"
DEFAULT_RAG_RERANK_MODEL: Final = "bge-reranker-v2-m3"
DEFAULT_RAG_TOP_K: Final = 10

# Servicios RAG/MCP
SERVICE_RAG_INDEX: Final = "rag_index_entities"
SERVICE_RAG_ADD_DOCUMENT: Final = "rag_add_document"
SERVICE_RAG_SEARCH: Final = "rag_search"
SERVICE_RAG_CLEAR: Final = "rag_clear"
SERVICE_RAG_STATS: Final = "rag_stats"
SERVICE_MCP_LIST_TOOLS: Final = "mcp_list_tools"
SERVICE_MCP_CALL_TOOL: Final = "mcp_call_tool"
```

* * *
## 6\. Actualizar `manifest.json` - agregar numpy

```json
{
  "requirements": ["aiohttp>=3.9.0", "numpy>=1.24.0"]
}
```

* * *
## 7\. Actualizar Options Flow en `config_flow.py`
Agregar opciones RAG/MCP al options flow:

```python
class LemonadeOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                # ... existing fields ...
                vol.Optional(
                    CONF_RAG_ENABLED,
                    default=entry.options.get(CONF_RAG_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_MCP_ENABLED,
                    default=entry.options.get(CONF_MCP_ENABLED, False),
                ): bool,
                vol.Optional(
                    CONF_RAG_EMBEDDING_MODEL,
                    default=entry.options.get(
                        CONF_RAG_EMBEDDING_MODEL, DEFAULT_RAG_EMBEDDING_MODEL
                    ),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                vol.Optional(
                    CONF_RAG_TOP_K,
                    default=entry.options.get(CONF_RAG_TOP_K, DEFAULT_RAG_TOP_K),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=50, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
            }),
        )
```

* * *
## Flujo completo RAG + MCP

```plain
Usuario habla → STT → "enciende la luz del living"
                        ↓
              RAG busca contexto relevante:
              [ENTITY] light.living_room. Area: Living. State: off
                        ↓
              System prompt + RAG context + User message
                        ↓
              LLM genera respuesta + tool_calls
                        ↓
              ¿Es tool HA? → llm_api.async_call_tool()
              ¿Es tool MCP? → mcp_manager.handle_agent_tool_call()
                        ↓
              Respuesta final → TTS → Audio
```

**Beneficios:**
*   RAG reduce tokens enviados (solo entidades relevantes)
*   RAG mejora accuracy (el LLM sabe exactamente qué entidades existen)
*   MCP permite al agente usar transcripción, generación de imágenes y modelos omni
*   Todo corre local en el mismo servidor Lemonade