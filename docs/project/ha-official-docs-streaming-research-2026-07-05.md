# Home Assistant official docs research — streaming + LLM API notes

Date: 2026-07-05
Sources:
- https://developers.home-assistant.io/docs/core/entity/conversation/
- https://developers.home-assistant.io/docs/core/llm/
- https://developers.home-assistant.io/docs/development_index/

## Key findings for lemonade_conversation_advanced

### 1. ConversationEntity docs do NOT document a custom visible-streaming callback
Official Conversation entity docs describe:
- properties like `supported_languages`
- supported feature `CONTROL`
- main request handler: `_async_handle_message(user_input, chat_log) -> ConversationResult`
- optional warmup hook: `async_prepare(language=None)`

Important note from docs:
- HA used to promote `async_process`; now `_async_handle_message` is the recommended method because HA automatically includes the `ChatLog`.
- The official docs page does **not** expose a separate documented method for UI-visible token streaming from a custom conversation entity.

Implication:
- Our earlier assumption that there was a straightforward documented entity-level streaming handler to override is not confirmed by the official docs page.
- `_attr_supports_streaming = True` alone is not enough to produce progressive UI output in our current integration path.

### 2. ChatLog streaming is documented as part of LLM/tool orchestration
The official LLM API docs show the recommended pattern:
- call `await chat_log.async_provide_llm_data(...)`
- format `chat_log.llm_api.tools` for the target LLM
- send request to LLM
- feed response stream into `chat_log.async_add_delta_content_stream(...)`
- loop while `chat_log.unresponded_tool_results`
- finally build `IntentResponse` from `chat_log.content`

This matches what we already do conceptually.

Implication:
- `chat_log.async_add_delta_content_stream(...)` is officially documented for tool-capable LLM orchestration.
- But the docs example still ends by returning a final `ConversationResult`, which suggests ChatLog streaming is primarily an internal conversation/tool state mechanism, not guaranteed frontend token-by-token rendering by itself.

### 3. Therefore the current lack of visible progressive output is likely not a parser issue
Beta testing results from the user:
- beta.2 and beta.3 still render the answer non-progressively in HA UI
- reasoning, normal chat, and services all work
- beta.3 seemed slower, consistent with more internal processing but no visible streaming payoff

Implication:
- More parser tweaks are unlikely to fix UI-visible progressive output.
- Need to inspect HA core code paths beyond the high-level docs to determine whether visible streaming depends on a different assist/voice pipeline path, websocket event flow, or frontend-specific handling.

### 4. Official LLM API guidance for Phase 2 is very relevant
The docs provide two solid extension patterns:

#### A. Contributing tools via `<integration>/llm.py`
An integration can expose tools without owning a full custom API by implementing:
- `async_get_tools(hass, llm_context) -> llm.LLMTools`

This hook is lazily discovered by the `llm` integration per request.

#### B. Creating a full custom API
Implement an `llm.API` subclass and register it with:
- `unreg = llm.async_register_api(hass, MyAPI(...))`
- `entry.async_on_unload(unreg)`

This is useful when the integration wants its own API identity and prompt.

### 5. Tool implementation rules from official docs
Official tool requirements:
- subclass `llm.Tool`
- implement `async_call(...)`
- return JSON-serializable dict data
- raise `HomeAssistantError` for failures
- arguments are validated through the voluptuous schema

This is the preferred direction for Lemonade Phase 2 control tools.

## Project decisions updated from research

1. Stop assuming there is a documented custom conversation-entity method that directly enables visible token streaming in UI.
2. Treat current `ChatLog` streaming work as correct for tool orchestration, but not proven sufficient for frontend progressive rendering.
3. Before more streaming patches, inspect HA core implementation around Assist/Conversation delivery path rather than only developer docs.
4. For Phase 2, prefer official LLM tool patterns (`llm.py` contribution hook or `llm.API` registration) instead of reviving legacy orphan MCP-style code.

## Suggested next technical step
Investigate HA core source (not just docs) for:
- where `ConversationEntity._attr_supports_streaming` is consumed
- whether visible progressive output is limited to specific Assist pipeline paths
- whether frontend/live token rendering needs a different event-based API than the standard conversation result path
