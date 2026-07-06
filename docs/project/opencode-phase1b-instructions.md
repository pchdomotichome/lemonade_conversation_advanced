# Phase 1b Instructions — Streaming + Thinking Blocks

**Coder: MiMo Code** (no OpenCode)

## Context
- Working dir: `/home/hermes/workspace/lemonade_conversation_advanced`
- Branch: `feat/lemonade-advanced-restart` (tracking `origin/main`)
- File to modify: `custom_components/lemonade_conversation_advanced/conversation.py`
- Smoke test: `python3 scripts/smoke_check.py` (must pass after)

## Task 1: Streaming support
- Set `stream=True` in the API payload
- Call `await chat_log.async_add_delta_content_stream(content, agent_id=self.entity_id)` for each delta
- Add `chat_log.async_add_assistant_content(ConversationResult(...))` at the end
- Handle `aiohttp.ClientError` and timeouts during streaming
- Keep `max_iterations=5` guard

## Task 2: Thinking content blocks
- Detect `` or `thinking_content` in the LLM response
- Process thinking blocks per HA core `google_generative_ai_conversation` pattern
- Add to chat_log as `AssistantContent` with content from thinking blocks

## Task 3: Error handling
- Network timeout recovery (retry once)
- Invalid response format → fallback to non-streaming

## Commit
- `feat: add streaming responses and thinking content blocks`
- Smoke check must pass

## Commands
```bash
mimo run 'Phase 1b: streaming + thinking blocks in conversation.py. Read docs/project/opencode-phase1b-instructions.md for context.' --dir /home/hermes/workspace/lemonade_conversation_advanced
```
