"""Utilities for Lemonade Conversation Advanced."""

from __future__ import annotations

import re
from typing import Any, AsyncIterator, Dict, List, Optional

from openai.types.chat import ChatCompletionChunk


def strip_thinking_blocks(text: str) -> str:
    """Strip thinking blocks from model output."""
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"【.*?】", "", text, flags=re.DOTALL)
    text = re.sub(r"<<.*?>>", "", text, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class StreamingParser:
    """State machine for parsing streaming responses."""

    def __init__(self, thinking_start: str = "<think>", thinking_end: str = "</think>"):
        """Initialize parser."""
        self.thinking_start = thinking_start
        self.thinking_end = thinking_end
        self.state = "SPEECH"
        self.buffer = ""
        self.thinking_buffer = ""
        self.tool_call_buffer = ""

    def parse_chunk(self, chunk: ChatCompletionChunk) -> List[Dict[str, Any]]:
        """Parse a streaming chunk."""
        events = []
        if not chunk.choices:
            return events
        choice = chunk.choices[0]
        delta = choice.delta
        if delta.content:
            events.extend(self._parse_content(delta.content))
        if delta.tool_calls:
            events.extend(self._parse_tool_calls(delta.tool_calls))
        if choice.finish_reason:
            events.append({"type": "finish", "reason": choice.finish_reason})
        return events

    def _parse_content(self, content: str) -> List[Dict[str, Any]]:
        """Parse content delta."""
        events = []
        i = 0
        while i < len(content):
            if self.state == "SPEECH":
                if content[i:].startswith(self.thinking_start):
                    if self.buffer:
                        events.append({"type": "speech", "content": self.buffer})
                        self.buffer = ""
                    self.state = "THINKING"
                    i += len(self.thinking_start)
                else:
                    self.buffer += content[i]
                    i += 1
            elif self.state == "THINKING":
                if content[i:].startswith(self.thinking_end):
                    if self.thinking_buffer:
                        events.append({"type": "thinking", "content": self.thinking_buffer})
                        self.thinking_buffer = ""
                    self.state = "SPEECH"
                    i += len(self.thinking_end)
                else:
                    self.thinking_buffer += content[i]
                    i += 1
        return events

    def _parse_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Parse tool call deltas."""
        events = []
        for tool_call in tool_calls:
            if tool_call.index is not None:
                events.append({"type": "tool_call_start", "index": tool_call.index, "id": tool_call.id})
            if tool_call.function and tool_call.function.arguments:
                events.append({"type": "tool_call_delta", "index": tool_call.index, "arguments": tool_call.function.arguments})
        return events

    def flush(self) -> List[Dict[str, Any]]:
        """Flush buffers."""
        events = []
        if self.buffer:
            events.append({"type": "speech", "content": self.buffer})
            self.buffer = ""
        if self.thinking_buffer:
            events.append({"type": "thinking", "content": self.thinking_buffer})
            self.thinking_buffer = ""
        return events


async def parse_streaming_response(stream: AsyncIterator[ChatCompletionChunk]) -> AsyncIterator[Dict[str, Any]]:
    """Parse streaming response into events."""
    parser = StreamingParser()
    async for chunk in stream:
        for event in parser.parse_chunk(chunk):
            yield event
    for event in parser.flush():
        yield event


def format_url(base_url: str, path: str) -> str:
    """Format URL properly."""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def parse_model_name(model_name: str) -> Dict[str, Optional[str]]:
    """Parse model name into components."""
    parts = model_name.split(".", 1)
    if len(parts) != 2:
        return {"namespace": None, "name": model_name, "quantization": None}
    namespace, rest = parts
    quant_match = re.search(r"-(GGUF|GPTQ|AWQ|EXL2|QLORA)$", rest, re.IGNORECASE)
    if quant_match:
        return {"namespace": namespace, "name": rest[:quant_match.start()], "quantization": quant_match.group(1).upper()}
    return {"namespace": namespace, "name": rest, "quantization": None}
