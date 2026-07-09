"""Lemonade API client with reliable streaming and retry logic."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.llm import ToolInput

_LOGGER = logging.getLogger(__name__)


class LemonadeConnectionError(Exception):
    """Connection to Lemonade server failed."""


class LemonadeAuthError(Exception):
    """Authentication with Lemonade server failed."""


class LemonadeAPIError(Exception):
    """Lemonade server returned an error response."""


class LemonadeAPIClient:
    """Reliable HTTP client for Lemonade Server API.

    - Connection pooling via shared aiohttp session
    - True streaming: line-by-line SSE parsing (async for line in response.content)
    - Retry with exponential backoff on initial connection failure
    - Configurable timeouts per operation type
    """

    def __init__(
        self,
        hass: HomeAssistant,
        server_url: str,
        api_key: str = "",
        *,
        request_timeout: float = 120.0,
        connect_timeout: float = 15.0,
        max_retries: int = 2,
        retry_backoff: float = 2.0,
    ) -> None:
        self._hass = hass
        self._server_url = server_url.rstrip("/")
        self._api_key = api_key
        self._request_timeout = request_timeout
        self._connect_timeout = connect_timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._session: aiohttp.ClientSession | None = None

    @property
    def server_url(self) -> str:
        return self._server_url

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = async_get_clientsession(self._hass)
        return self._session

    def _build_headers(
        self, extra: dict[str, str] | None = None
    ) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if extra:
            headers.update(extra)
        return headers

    def _get_timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(
            total=self._request_timeout,
            connect=self._connect_timeout,
        )

    # ------------------------------------------------------------------ #
    #  Health check                                                        #
    # ------------------------------------------------------------------ #

    async def health_check(self) -> bool:
        """Ping the Lemonade health endpoint."""
        session = await self._get_session()
        headers = self._build_headers()
        try:
            async with session.get(
                f"{self._server_url}/v1/health",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                ok = resp.status < 400
                if not ok:
                    _LOGGER.warning("Health check returned HTTP %d", resp.status)
                return ok
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Health check failed: %s", err)
            return False

    # ------------------------------------------------------------------ #
    #  Non-streaming chat completion                                       #
    # ------------------------------------------------------------------ #

    async def chat_completions(
        self,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Non-streaming chat completion.

        Raises LemonadeConnectionError, LemonadeAuthError, LemonadeAPIError.
        """
        session = await self._get_session()
        req_headers = self._build_headers(headers)
        timeout = self._get_timeout()

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with session.post(
                    f"{self._server_url}/v1/chat/completions",
                    json=payload,
                    headers=req_headers,
                    timeout=timeout,
                ) as resp:
                    if resp.status == 401:
                        raise LemonadeAuthError("Invalid API key")
                    if resp.status >= 400:
                        text = await resp.text()
                        raise LemonadeAPIError(
                            f"HTTP {resp.status}: {text[:500]}"
                        )
                    return await resp.json()

            except (LemonadeAuthError, LemonadeAPIError):
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                last_error = err
                if attempt < self._max_retries:
                    wait = min(
                        self._retry_backoff * (2**attempt), 30.0
                    )
                    _LOGGER.warning(
                        "Non-streaming attempt %d/%d failed: %s. "
                        "Retrying in %.1fs",
                        attempt + 1, self._max_retries + 1, err, wait,
                    )
                    await asyncio.sleep(wait)
                    continue

        raise LemonadeConnectionError(
            f"Non-streaming failed after {self._max_retries + 1} attempts: "
            f"{last_error}"
        )

    # ------------------------------------------------------------------ #
    #  Streaming chat completion                                           #
    # ------------------------------------------------------------------ #

    async def chat_completions_stream(
        self,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream chat completion via SSE, yielding deltas line by line.

        Retries the *initial* connection up to ``max_retries`` times.
        Once the first delta has been yielded (i.e. the LLM has started
        responding), any connection drop propagates immediately to the
        caller — no mid-stream retry.

        Each yielded dict follows the OpenAI delta format:
          ``{"content": "..."}``
          ``{"thinking_content": "..."}``
          ``{"tool_calls": [ToolInput(...)]}``

        Raises LemonadeConnectionError, LemonadeAuthError, LemonadeAPIError.
        """
        session = await self._get_session()
        req_headers = self._build_headers(headers)
        timeout = self._get_timeout()

        yielded_any = False
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                async with session.post(
                    f"{self._server_url}/v1/chat/completions",
                    json=payload,
                    headers=req_headers,
                    timeout=timeout,
                ) as resp:
                    if resp.status == 401:
                        raise LemonadeAuthError("Invalid API key")
                    if resp.status >= 400:
                        text = await resp.text()
                        raise LemonadeAPIError(
                            f"HTTP {resp.status}: {text[:500]}"
                        )

                    _LOGGER.debug(
                        "Streaming connection established (attempt %d)",
                        attempt + 1,
                    )
                    async for delta in self._iter_sse(resp):
                        yielded_any = True
                        yield delta

                    # Clean exit — stream finished normally
                    return

            except (LemonadeAuthError, LemonadeAPIError):
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                last_error = err
                # Do NOT retry if we've already yielded deltas (mid-stream
                # drop) — the caller should fall back to non-streaming.
                if yielded_any:
                    raise LemonadeConnectionError(
                        f"Stream dropped after receiving data: {err}"
                    ) from err
                if attempt < self._max_retries:
                    wait = min(
                        self._retry_backoff * (2**attempt), 30.0
                    )
                    _LOGGER.warning(
                        "Stream attempt %d/%d failed: %s. "
                        "Retrying in %.1fs",
                        attempt + 1, self._max_retries + 1, err, wait,
                    )
                    await asyncio.sleep(wait)
                    continue

        raise LemonadeConnectionError(
            f"Stream failed after {self._max_retries + 1} attempts: "
            f"{last_error}"
        )

    # ------------------------------------------------------------------ #
    #  SSE parser — true streaming, line by line                           #
    # ------------------------------------------------------------------ #

    async def _iter_sse(
        self,
        response: aiohttp.ClientResponse,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Parse raw SSE bytes into OpenAI-format deltas in real time.

        Handles both OpenAI SSE (``data: {...}``) and Ollama JSON-per-line
        formats. Yields dicts compatible with
        ``ChatLog.async_add_delta_content_stream``.

        Thinking tags (``<nik...k>``, ``<|thought|>...<|/thought|>``)
        are stripped from content; the content delta before them is
        yielded immediately for low-latency streaming.
        """
        content_buf = ""
        tc_accum: dict[int, dict[str, Any]] = {}
        in_thinking = False
        thinking_tag_buffer = ""

        while True:
            line_bytes = await response.content.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")

            if not line:
                continue

            # --- OpenAI SSE: "data: {...}" or "data: [DONE]" ---
            if line.startswith("data: "):
                if line == "data: [DONE]":
                    _LOGGER.debug("SSE [DONE] received")
                    break
                try:
                    data = json.loads(line[6:])
                except ValueError as exc:
                    _LOGGER.warning("Failed to parse SSE: %s", exc)
                    continue
                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta", {})

            # --- Ollama format: raw JSON per line ---
            elif line.startswith("{"):
                try:
                    data = json.loads(line)
                except ValueError as exc:
                    _LOGGER.warning("Failed to parse JSON line: %s", exc)
                    continue
                if data.get("done"):
                    _LOGGER.debug("Ollama done marker received")
                    break
                delta = data.get("message", {})
                if "content" in data and not delta:
                    delta = {"content": data["content"]}
            else:
                _LOGGER.debug("Ignoring non-SSE line: %s", line[:100])
                continue

            if not delta:
                continue

            _LOGGER.debug("SSE delta: %s", delta)

            # --- content with thinking-tag handling ---
            raw_content = delta.get("content") or ""
            if raw_content:
                content_buf += raw_content
                for d in self._process_content_buf(
                    content_buf, in_thinking, thinking_tag_buffer
                ):
                    if isinstance(d, tuple):
                        content_buf, in_thinking, thinking_tag_buffer = d
                    else:
                        yield d

            # --- reasoning / thinking content (separate field) ---
            rc_field = (
                delta.get("reasoning_content")
                or delta.get("thinking_content")
                or ""
            )
            if rc_field:
                yield {"thinking_content": rc_field}

            # --- tool call deltas ---
            for tc_delta in delta.get("tool_calls") or []:
                idx = tc_delta.get("index", 0)
                if idx not in tc_accum:
                    tc_accum[idx] = {}
                entry = tc_accum[idx]
                if "id" in tc_delta:
                    entry["id"] = tc_delta["id"]
                func = tc_delta.get("function", {})
                if "name" in func:
                    entry["name"] = func["name"]
                if "arguments" in func:
                    entry["args_str"] = (
                        entry.get("args_str", "") + func["arguments"]
                    )

        # --- flush remaining content ---
        if content_buf and not in_thinking:
            yield {"content": content_buf}

        # --- yield accumulated tool calls ---
        for idx in sorted(tc_accum):
            tc = tc_accum[idx]
            if "id" in tc and "name" in tc and "args_str" in tc:
                try:
                    args = json.loads(tc["args_str"])
                except (json.JSONDecodeError, ValueError):
                    args = {}
                yield {
                    "tool_calls": [
                        ToolInput(
                            tool_name=tc["name"],
                            tool_args=args,
                            id=tc["id"],
                        )
                    ]
                }

    @staticmethod
    def _process_content_buf(
        content_buf: str,
        in_thinking: bool,
        thinking_tag_buffer: str,
    ) -> list[dict[str, Any] | tuple[str, bool, str]]:
        """Process content buffer, splitting on think-tag boundaries.

        Returns a mixed list of:
        - dicts (content deltas to yield)
        - tuples (updated state: buf, in_thinking, tag_buf)
        """
        results: list[dict[str, Any] | tuple[str, bool, str]] = []
        while content_buf:
            if in_thinking:
                end_tag = (
                    "</nik>"
                    if thinking_tag_buffer == "<nik"
                    else "<|/thought|>"
                )
                end_idx = content_buf.find(end_tag)
                if end_idx == -1:
                    break
                thinking_tag_buffer = ""
                content_buf = content_buf[end_idx + len(end_tag) :]
                in_thinking = False
                continue

            think_idx = content_buf.find("<nik")
            alt_idx = content_buf.find("<|thought|>")
            candidates = [idx for idx in (think_idx, alt_idx) if idx != -1]
            if not candidates:
                if content_buf:
                    results.append({"content": content_buf})
                content_buf = ""
                break

            next_idx = min(candidates)
            if next_idx > 0:
                results.append({"content": content_buf[:next_idx]})

            if think_idx != -1 and think_idx == next_idx:
                thinking_tag_buffer = "<nik"
                content_buf = content_buf[next_idx + 4 :]
            else:
                thinking_tag_buffer = "<|thought|>"
                content_buf = content_buf[next_idx + len("<|thought|>") :]
            in_thinking = True

        results.append((content_buf, in_thinking, thinking_tag_buffer))
        return results

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
