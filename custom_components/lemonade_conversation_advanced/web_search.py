"""Local, self-hosted web search via SearXNG for Lemonade Conversation Advanced."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.json import JsonObjectType

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)


async def async_searxng_search(
    hass: HomeAssistant,
    base_url: str,
    query: str,
    *,
    engines: str = "",
    max_results: int = 5,
) -> dict[str, Any]:
    """Query a local SearXNG instance and return normalized results.

    Uses the JSON output format (``format=json``) exposed by SearXNG.
    The instance must have ``json`` enabled under ``search.formats`` in
    its ``settings.yml``.
    """
    base_url = (base_url or "").rstrip("/")
    if not base_url:
        return {"error": "searxng_not_configured", "results": []}

    params: dict[str, str] = {"q": query, "format": "json"}
    if engines:
        params["engines"] = engines

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{base_url}/search",
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status >= 400:
                return {
                    "error": f"http_{resp.status}",
                    "error_text": f"SearXNG returned HTTP {resp.status}",
                    "results": [],
                }
            data = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.warning("SearXNG search failed: %s", err)
        return {"error": "connection_error", "error_text": str(err), "results": []}

    raw_results = data.get("results", []) or []
    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        }
        for r in raw_results[: max(1, max_results)]
    ]

    answer = ""
    answers = data.get("answers") or []
    if answers:
        answer = answers[0] if isinstance(answers[0], str) else str(answers[0])

    return {
        "query": query,
        "answer": answer,
        "results": results,
        "count": len(results),
    }


class WebSearchTool(llm.Tool):
    """Search the web via a local SearXNG instance."""

    name = "web_search"
    description = (
        "Search the web for up-to-date or general-knowledge information "
        "that is not available from Home Assistant entities (news, facts, "
        "weather forecasts, definitions, etc.). Returns a list of results "
        "with title, url and a content snippet."
    )
    parameters = vol.Schema(
        {
            vol.Required("query"): str,
        }
    )

    def __init__(
        self,
        base_url: str,
        *,
        engines: str = "",
        max_results: int = 5,
    ) -> None:
        """Store the SearXNG configuration for this tool instance."""
        self._base_url = base_url
        self._engines = engines
        self._max_results = max_results

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        query = tool_input.tool_args["query"]
        _LOGGER.debug("web_search via SearXNG: %s", query)
        return await async_searxng_search(
            hass,
            self._base_url,
            query,
            engines=self._engines,
            max_results=self._max_results,
        )
