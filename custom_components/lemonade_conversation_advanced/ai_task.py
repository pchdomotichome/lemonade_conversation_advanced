"""AI Task support for Lemonade Conversation Advanced.

Supports structured data generation (``ai_task.generate_data``) with three
extraction methods:

- ``none``       -> return the raw model text.
- ``structure``  -> ask the model for JSON matching the task structure
                    (via ``response_format`` json_schema) and parse it.
- ``tool``       -> expose a ``submit_response`` function whose parameters are
                    the task structure; parse the tool-call arguments.

A retry loop feeds validation/parse errors back to the model so small local
models get a chance to correct malformed output. Optional vision/attachment
support is advertised when the subentry enables it.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, override

import aiohttp
import voluptuous as vol
from voluptuous_openapi import convert as convert_to_openapi

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    AI_TASK_EXTRACTION_NONE,
    AI_TASK_EXTRACTION_STRUCTURE,
    AI_TASK_EXTRACTION_TOOL,
    CONF_AI_TASK_ENABLE_VISION,
    CONF_AI_TASK_EXTRACTION_METHOD,
    CONF_AI_TASK_RETRIES,
    CONF_MAX_TOKENS,
    CONF_MODEL_NAME,
    CONF_REQUEST_TIMEOUT,
    CONF_SYSTEM_PROMPT,
    CONF_TEMPERATURE,
    DEFAULT_AI_TASK_EXTRACTION_METHOD,
    DEFAULT_AI_TASK_RETRIES,
    DEFAULT_AI_TASK_SYSTEM_PROMPT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_TEMPERATURE,
)
from .entity import LemonadeBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task":
            continue

        async_add_entities(
            [LemonadeAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LemonadeAITaskEntity(
    ai_task.AITaskEntity,
    LemonadeBaseEntity,
):
    """Lemonade AI Task entity."""

    def __init__(self, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        features = ai_task.AITaskEntityFeature.GENERATE_DATA
        attachments_flag = getattr(
            ai_task.AITaskEntityFeature, "SUPPORT_ATTACHMENTS", None
        )
        if subentry.data.get(CONF_AI_TASK_ENABLE_VISION) and attachments_flag:
            features |= attachments_flag
        self._attr_supported_features = features

    async def _build_attachment_parts(
        self, attachments: list[Any] | None
    ) -> list[dict[str, Any]]:
        """Convert task attachments into OpenAI content parts (base64 data URLs)."""
        parts: list[dict[str, Any]] = []
        for attachment in attachments or []:
            path = getattr(attachment, "path", None)
            mime_type = getattr(attachment, "mime_type", None) or "image/jpeg"
            if not path:
                continue
            try:
                raw = await self.hass.async_add_executor_job(
                    lambda p=path: p.read_bytes()
                )
            except OSError as err:  # pragma: no cover - defensive
                _LOGGER.warning("Could not read attachment %s: %s", path, err)
                continue
            b64 = base64.b64encode(raw).decode("ascii")
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                }
            )
        return parts

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        extra_payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        """Call the Lemonade OpenAI-compatible chat endpoint once."""
        options = self.subentry.data
        server_url = self.entry.data.get("server_url", "")
        api_key = self.entry.data.get("api_key", "")

        payload: dict[str, Any] = {
            "model": options.get(CONF_MODEL_NAME, ""),
            "messages": messages,
            "temperature": options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
            "max_tokens": options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
            "stream": False,
            **extra_payload,
        }

        session = async_get_clientsession(self.hass)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with session.post(
                f"{server_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise HomeAssistantError(f"LLM error: {text}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise HomeAssistantError(f"Connection error: {err}") from err

    @override
    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        options = self.subentry.data
        system_prompt = options.get(
            CONF_SYSTEM_PROMPT, DEFAULT_AI_TASK_SYSTEM_PROMPT
        )
        timeout = float(options.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT))
        retries = max(
            0, int(options.get(CONF_AI_TASK_RETRIES, DEFAULT_AI_TASK_RETRIES))
        )
        method = options.get(
            CONF_AI_TASK_EXTRACTION_METHOD, DEFAULT_AI_TASK_EXTRACTION_METHOD
        )
        if task.structure is None:
            method = AI_TASK_EXTRACTION_NONE

        # Build extraction-method-specific request pieces and system guidance.
        extra_payload: dict[str, Any] = {}
        schema: dict[str, Any] | None = None
        if method in (AI_TASK_EXTRACTION_STRUCTURE, AI_TASK_EXTRACTION_TOOL):
            schema = convert_to_openapi(
                task.structure, custom_serializer=llm.selector_serializer
            )

        if method == AI_TASK_EXTRACTION_STRUCTURE:
            extra_payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "ai_task_result",
                    "schema": schema,
                    "strict": False,
                },
            }
            system_prompt = (
                f"{system_prompt}\n\nRespond ONLY with a single JSON object that "
                f"matches this JSON schema, with no extra text:\n"
                f"{json.dumps(schema)}"
            )
        elif method == AI_TASK_EXTRACTION_TOOL:
            extra_payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "submit_response",
                        "description": (
                            "Submit the structured response payload for the AI task."
                        ),
                        "parameters": schema,
                    },
                }
            ]
            extra_payload["tool_choice"] = {
                "type": "function",
                "function": {"name": "submit_response"},
            }

        # Build the user message (optionally multimodal).
        user_content: Any = task.instructions
        if options.get(CONF_AI_TASK_ENABLE_VISION):
            image_parts = await self._build_attachment_parts(
                getattr(task, "attachments", None)
            )
            if image_parts:
                user_content = [
                    {"type": "text", "text": task.instructions},
                    *image_parts,
                ]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            _LOGGER.debug(
                "AI Task '%s' attempt %s/%s (method=%s)",
                task.name,
                attempt + 1,
                retries + 1,
                method,
            )
            data = await self._call_llm(messages, extra_payload, timeout)
            message = data["choices"][0]["message"]
            raw_text = message.get("content") or ""

            result, err = self._extract(
                method, raw_text, message, task, chat_log
            )
            if err is None:
                return result

            last_error = err
            # Feed the error back to the model and retry.
            messages.append(
                {
                    "role": "assistant",
                    "content": raw_text,
                    **(
                        {"tool_calls": message["tool_calls"]}
                        if message.get("tool_calls")
                        else {}
                    ),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": f"Error: {err}. Please try again.",
                }
            )

        raise last_error or HomeAssistantError(
            f"AI Task '{task.name}' failed after {retries + 1} attempts"
        )

    def _extract(
        self,
        method: str,
        raw_text: str,
        message: dict[str, Any],
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> tuple[ai_task.GenDataTaskResult | None, Exception | None]:
        """Extract and validate the final result from a model response."""
        try:
            if method == AI_TASK_EXTRACTION_NONE:
                return (
                    ai_task.GenDataTaskResult(
                        conversation_id=chat_log.conversation_id,
                        data=raw_text,
                    ),
                    None,
                )

            if method == AI_TASK_EXTRACTION_STRUCTURE:
                parsed = json.loads(raw_text)
                task.structure(parsed)
                return (
                    ai_task.GenDataTaskResult(
                        conversation_id=chat_log.conversation_id,
                        data=parsed,
                    ),
                    None,
                )

            if method == AI_TASK_EXTRACTION_TOOL:
                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    return None, HomeAssistantError(
                        "Please call the submit_response function with the "
                        "structured response."
                    )
                args = tool_calls[0].get("function", {}).get("arguments", "{}")
                parsed = json.loads(args) if isinstance(args, str) else args
                task.structure(parsed)
                return (
                    ai_task.GenDataTaskResult(
                        conversation_id=chat_log.conversation_id,
                        data=parsed,
                    ),
                    None,
                )
        except json.JSONDecodeError as err:
            return None, HomeAssistantError(
                f"Please produce properly formatted JSON: {err}"
            )
        except vol.Invalid as err:
            return None, HomeAssistantError(
                f"Please address the following schema error: {err}"
            )

        return None, HomeAssistantError(f"Invalid extraction method: {method}")
