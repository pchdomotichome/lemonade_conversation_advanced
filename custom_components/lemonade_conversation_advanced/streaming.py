"""Streaming support for Lemonade Conversation Advanced."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

from openai.types.chat import ChatCompletionChunk

_LOGGER = logging.getLogger(__name__)


@dataclass
class StreamingState:
    """State for streaming parser."""

    content_buffer: str = ""
    thinking_buffer: str = ""
    tool_call_buffers: dict[int, dict] = field(default_factory=dict)
    in_thinking: bool = False
    thinking_start_tag: str = "<think>"
    thinking_end_tag: str = "</think>"


class StreamingProcessor:
    """Process streaming chunks from OpenAI-compatible API."""

    def __init__(
        self,
        on_content: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
        on_tool_call: Callable[[int, str, str], None] | None = None,
        on_finish: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the processor."""
        self._on_content = on_content
        self._on_thinking = on_thinking
        self._on_tool_call = on_tool_call
        self._on_finish = on_finish
        self._state = StreamingState()
        self._full_content = ""
        self._full_thinking = ""
        self._tool_calls: dict[int, dict] = {}

    async def process_stream(
        self,
        stream: AsyncIterator[ChatCompletionChunk],
    ) -> StreamResult:
        """Process a streaming response and return accumulated result."""
        async for chunk in stream:
            self._process_chunk(chunk)

        # Flush any remaining buffer
        self._flush()

        return StreamResult(
            content=self._full_content,
            thinking=self._full_thinking,
            tool_calls=self._tool_calls,
            finish_reason=self._finish_reason,
        )

    def _process_chunk(self, chunk: ChatCompletionChunk) -> None:
        """Process a single chunk."""
        if not chunk.choices:
            return

        choice = chunk.choices[0]
        delta = choice.delta

        # Process content
        if delta.content:
            self._process_content(delta.content)

        # Process thinking (reasoning_content)
        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
            self._process_thinking(delta.reasoning_content)

        # Process tool calls
        if delta.tool_calls:
            self._process_tool_calls(delta.tool_calls)

        # Track finish reason
        if choice.finish_reason:
            self._finish_reason = choice.finish_reason

    def _process_content(self, content: str) -> None:
        """Process content delta, handling thinking tags."""
        i = 0
        while i < len(content):
            if self._state.in_thinking:
                # Look for end tag
                end_idx = content.find(self._state.thinking_end_tag, i)
                if end_idx != -1:
                    # Found end tag
                    self._state.thinking_buffer += content[i:end_idx]
                    self._state.in_thinking = False
                    i = end_idx + len(self._state.thinking_end_tag)
                    # Emit thinking content
                    if self._on_thinking and self._state.thinking_buffer:
                        self._on_thinking(self._state.thinking_buffer)
                    self._full_thinking += self._state.thinking_buffer
                    self._state.thinking_buffer = ""
                else:
                    # No end tag found, accumulate
                    self._state.thinking_buffer += content[i:]
                    i = len(content)
            else:
                # Look for start tag
                start_idx = content.find(self._state.thinking_start_tag, i)
                if start_idx != -1:
                    # Found start tag
                    # Emit any content before the tag
                    if start_idx > i:
                        text = content[i:start_idx]
                        self._full_content += text
                        if self._on_content:
                            self._on_content(text)
                    self._state.in_thinking = True
                    i = start_idx + len(self._state.thinking_start_tag)
                else:
                    # No start tag, emit content
                    text = content[i:]
                    self._full_content += text
                    if self._on_content:
                        self._on_content(text)
                    i = len(content)

    def _process_thinking(self, content: str) -> None:
        """Process thinking/reasoning content from API."""
        self._full_thinking += content
        if self._on_thinking:
            self._on_thinking(content)

    def _process_tool_calls(self, tool_calls: list) -> None:
        """Process tool call deltas."""
        for tc in tool_calls:
            idx = tc.index
            if idx not in self._tool_calls:
                self._tool_calls[idx] = {
                    "id": tc.id or "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }

            if tc.id:
                self._tool_calls[idx]["id"] = tc.id

            if tc.function:
                if tc.function.name:
                    self._tool_calls[idx]["function"]["name"] = tc.function.name
                if tc.function.arguments:
                    self._tool_calls[idx]["function"]["arguments"] += tc.function.arguments

            if self._on_tool_call:
                self._on_tool_call(
                    idx,
                    self._tool_calls[idx]["function"]["name"],
                    self._tool_calls[idx]["function"]["arguments"],
                )

    def _flush(self) -> None:
        """Flush any remaining buffer content."""
        if self._state.in_thinking and self._state.thinking_buffer:
            self._full_thinking += self._state.thinking_buffer
            if self._on_thinking:
                self._on_thinking(self._state.thinking_buffer)
            self._state.thinking_buffer = ""

        if self._state.content_buffer:
            self._full_content += self._state.content_buffer
            if self._on_content:
                self._on_content(self._state.content_buffer)
            self._state.content_buffer = ""


@dataclass
class StreamResult:
    """Result from streaming processing."""

    content: str = ""
    thinking: str = ""
    tool_calls: dict[int, dict] = field(default_factory=dict)
    finish_reason: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if there are tool calls."""
        return len(self.tool_calls) > 0

    @property
    def tool_calls_list(self) -> list[dict]:
        """Get tool calls as a list."""
        return [self.tool_calls[i] for i in sorted(self.tool_calls.keys())]

    @property
    def is_stop(self) -> bool:
        """Check if the stream finished with stop."""
        return self.finish_reason == "stop"

    @property
    def is_tool_call(self) -> bool:
        """Check if the stream finished with tool calls."""
        return self.finish_reason == "tool_calls"
