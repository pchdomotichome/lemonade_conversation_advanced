"""Service handlers for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .backends.openai_compat import LemonadeOpenAICompatBackend
from .const import (
    CONF_API_KEY,
    CONF_DEFAULT_MODEL,
    CONF_MAX_TOKENS,
    CONF_SERVER_URL,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    DOMAIN,
)
from .exceptions import LemonadeError

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up services for Lemonade Conversation Advanced."""

    def get_backend(call: ServiceCall) -> LemonadeOpenAICompatBackend:
        entry_id = call.data.get("config_entry_id", entry.entry_id)
        if entry_id not in hass.data.get(DOMAIN, {}):
            raise HomeAssistantError(f"Config entry {entry_id} not found")
        return hass.data[DOMAIN][entry_id]["backend"]

    async def load_model(call: ServiceCall) -> ServiceResponse:
        """Load a model into memory."""
        try:
            result = await get_backend(call).load_model(
                model_name=call.data["model_name"],
                ctx_size=call.data.get("ctx_size"),
                gpu_layers=call.data.get("gpu_layers"),
                backend=call.data.get("backend"),
            )
            return {"result": result}
        except LemonadeError as err:
            raise HomeAssistantError(f"Failed to load model: {err}") from err

    async def unload_model(call: ServiceCall) -> ServiceResponse:
        """Unload a model from memory."""
        try:
            result = await get_backend(call).unload_model(call.data["model_name"])
            return {"result": result}
        except LemonadeError as err:
            raise HomeAssistantError(f"Failed to unload model: {err}") from err

    async def pull_model(call: ServiceCall) -> ServiceResponse:
        """Pull/download a model."""
        try:
            result = await get_backend(call).pull_model(
                model_name=call.data["model_name"],
                checkpoint=call.data.get("checkpoint"),
                recipe=call.data.get("recipe"),
            )
            return {"result": result}
        except LemonadeError as err:
            raise HomeAssistantError(f"Failed to pull model: {err}") from err

    async def list_models(call: ServiceCall) -> ServiceResponse:
        """List available models."""
        try:
            models = await get_backend(call).list_models(show_all=call.data.get("show_all", False))
            return {"models": models}
        except LemonadeError as err:
            raise HomeAssistantError(f"Failed to list models: {err}") from err

    async def get_system_info(call: ServiceCall) -> ServiceResponse:
        """Get system information."""
        try:
            return {"system_info": await get_backend(call).get_system_info()}
        except LemonadeError as err:
            raise HomeAssistantError(f"Failed to get system info: {err}") from err

    async def get_stats(call: ServiceCall) -> ServiceResponse:
        """Get performance statistics."""
        try:
            return {"stats": await get_backend(call).get_stats()}
        except LemonadeError as err:
            raise HomeAssistantError(f"Failed to get stats: {err}") from err

    async def set_default_model(call: ServiceCall) -> ServiceResponse:
        """Set default model for conversation."""
        model_name = call.data["model_name"]
        new_options = dict(entry.options)
        new_options[CONF_DEFAULT_MODEL] = model_name
        hass.config_entries.async_update_entry(entry, options=new_options)
        return {"success": True, "model": model_name}

    async def query_image(call: ServiceCall) -> ServiceResponse:
        """Analyze an image with a vision-capable model."""
        backend = get_backend(call)
        model = call.data.get("model") or entry.options.get(CONF_DEFAULT_MODEL)
        if not model:
            raise HomeAssistantError("No model specified and no default model configured")
        messages = [
            {"role": "system", "content": "You are a helpful vision assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": call.data["prompt"]},
                    {"type": "image_url", "image_url": {"url": call.data["image_url"]}},
                ],
            },
        ]
        response = await backend.chat_completion(model=model, messages=messages, temperature=0.3, max_tokens=1024)
        content = response.choices[0].message.content if response.choices else ""
        return {"response": content, "model": model}

    async def update_config(call: ServiceCall) -> ServiceResponse:
        """Update integration configuration at runtime."""
        new_data = dict(entry.data)
        new_options = dict(entry.options)
        for key, target in [
            (CONF_SERVER_URL, new_data),
            (CONF_API_KEY, new_data),
            (CONF_DEFAULT_MODEL, new_options),
            (CONF_TEMPERATURE, new_options),
            (CONF_MAX_TOKENS, new_options),
            (CONF_STREAMING, new_options),
        ]:
            if key in call.data:
                target[key] = call.data[key]
        hass.config_entries.async_update_entry(entry, data=new_data, options=new_options)
        await hass.config_entries.async_reload(entry.entry_id)
        return {"success": True, "message": "Configuration updated"}

    service_schema_with_entry = {vol.Required("config_entry_id"): cv.string}

    hass.services.async_register(
        DOMAIN,
        "load_model",
        load_model,
        schema=vol.Schema({**service_schema_with_entry, vol.Required("model_name"): cv.string, vol.Optional("ctx_size"): vol.Coerce(int), vol.Optional("gpu_layers"): vol.Coerce(int), vol.Optional("backend"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "unload_model",
        unload_model,
        schema=vol.Schema({**service_schema_with_entry, vol.Required("model_name"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "pull_model",
        pull_model,
        schema=vol.Schema({**service_schema_with_entry, vol.Required("model_name"): cv.string, vol.Optional("checkpoint"): cv.string, vol.Optional("recipe"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "list_models",
        list_models,
        schema=vol.Schema({**service_schema_with_entry, vol.Optional("show_all", default=False): cv.boolean}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(DOMAIN, "get_system_info", get_system_info, schema=vol.Schema(service_schema_with_entry), supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "get_stats", get_stats, schema=vol.Schema(service_schema_with_entry), supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "set_default_model", set_default_model, schema=vol.Schema({**service_schema_with_entry, vol.Required("model_name"): cv.string}), supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "query_image", query_image, schema=vol.Schema({**service_schema_with_entry, vol.Required("image_url"): cv.string, vol.Required("prompt"): cv.string, vol.Optional("model"): cv.string}), supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "update_config", update_config, schema=vol.Schema({**service_schema_with_entry, vol.Optional(CONF_SERVER_URL): cv.string, vol.Optional(CONF_API_KEY): cv.string, vol.Optional(CONF_DEFAULT_MODEL): cv.string, vol.Optional(CONF_TEMPERATURE): vol.Coerce(float), vol.Optional(CONF_MAX_TOKENS): vol.Coerce(int), vol.Optional(CONF_STREAMING): cv.boolean}), supports_response=SupportsResponse.ONLY)

    _LOGGER.info("Lemonade Conversation Advanced services registered")


async def async_unload_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload services."""
    for service in [
        "load_model",
        "unload_model",
        "pull_model",
        "list_models",
        "get_system_info",
        "get_stats",
        "set_default_model",
        "query_image",
        "update_config",
    ]:
        hass.services.async_remove(DOMAIN, service)
    _LOGGER.info("Lemonade Conversation Advanced services unloaded")
