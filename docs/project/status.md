# Lemonade Conversation Advanced — Project Status

## 2026-07-05 Kickoff

Hermes toma ownership técnico del proyecto. OpenCode queda disponible como coder delegado bajo directivas puntuales.

## Repo

- Path: `/home/hermes/workspace/lemonade_conversation_advanced`
- Remote: `https://github.com/pchdomotichome/lemonade_conversation_advanced.git`
- Branch de trabajo: `feat/lemonade-advanced-restart`
- Baseline observado: `main` en `v1.0.0-beta.20` antes de crear la rama.

## Source Material

- `/home/hermes/workspace/lemonade_analysis_roadmap.md`
- `/home/hermes/workspace/lemonade_conversation_analysis.md`
- `/mnt/wiki/concepts/lemonade-conversation-advanced-repo-analysis.md`
- `/mnt/wiki/concepts/lemonade-conversation-advanced-spec.md`
- `/mnt/wiki/concepts/lemonade-implementation-quickstart.md`

## Phase 0 Complete — 2026-07-05

### Changes made

1. **Removed `backends/` package**
   - `backends/__init__.py` and `backends/openai_compat.py` were dead code (233 LOC).
   - Not imported by any active code path (`__init__.py`, `conversation.py`, `config_flow.py`, `entity.py`, `ai_task.py`).
   - Contained broken imports (`..client.LemonadeClient`, `..exceptions.*`, missing `const` names).
   - Diagnostics documented in `phase0-diagnosis.md` and `opencode-phase0-report.md`.

2. **Added `scripts/smoke_check.py`**
   - Validates compileall, JSON, and import consistency in CI-like fashion.
   - Run with: `python3 scripts/smoke_check.py`

3. **Verified baseline**
   - `python -m compileall -q custom_components/lemonade_conversation_advanced` — passes.
   - All JSON files (manifest, strings, translations) valid.
   - Active import tree is honest: no dangling references to removed modules.

### Next steps

Phase 1 will focus on conversation core: ChatLog API pattern, tool-calling loop, streaming, multi-turn memory, and unit tests.

## Phase 1a Complete — 2026-07-05

### Changes made

**Implemented non-streaming tool calling loop in `_async_handle_chat_log`** (`conversation.py`):

1. **Tool calling loop with max 5 iterations**:
   - After LLM response, if `tool_calls` present, iterate through each tool call.
   - Add `AssistantContent` with `ToolCall` objects to chat_log.
   - Execute each tool via `chat_log.async_call_tool(...)` — runs the actual HA/llm_api functions.
   - Loop repeats with updated chat_log (now containing `ToolResultContent`).
   - When LLM returns no `tool_calls`, add final `AssistantContent` without tools and break.

2. **Real tool execution**: Removed fabrication of `ToolResultContent` from tool arguments. Tools now execute via `chat_log.async_call_tool`.

3. **Error handling**: Uses `HomeAssistantError` for LLM and connection errors (consistent with prior fixes).

4. **Pattern reference**: HA core `google_generative_ai_conversation/entity.py:_async_handle_chat_log`.

### Verification

```bash
$ python3 scripts/smoke_check.py
--- compileall ---
OK
--- JSON validation ---
  OK: custom_components/lemonade_conversation_advanced/manifest.json
  OK: custom_components/lemonade_conversation_advanced/strings.json
  OK: custom_components/lemonade_conversation_advanced/translations/en.json
--- Import consistency ---

PASS: smoke check OK
```

### Next steps (Phase 1b)

- Implement streaming responses (`stream: True`) with `chat_log.async_add_delta_content_stream`.
- Handle `thinking_content` blocks (HA 2026.4+).
- Add unit tests for conversation flow.

## Initial Direction

1. Diagnóstico real del repo actual antes de borrar/refactorizar.
2. Baseline verificable con compile/tests.
3. Fase 0: limpieza y reparación mínima.
4. Fase 1: conversation core con ChatLog, tool loop, streaming y tests.
5. Documentación continua en repo + wiki.
