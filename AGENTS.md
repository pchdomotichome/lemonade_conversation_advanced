# AGENTS.md

Compact guidance for OpenCode sessions working on this repo.

## What this is
A Home Assistant custom integration: `Lemonade Conversation Advanced`. It wires
[Lemonade Server](https://lemonade-server.ai/) (local LLMs) as a HA conversation
agent with function-calling, streaming, state injection, and telemetry sensors.
All code lives under `custom_components/lemonade_conversation_advanced/`.

## Verification
- `python3 scripts/smoke_check.py` — compiles all `.py`, validates JSON
  (manifest/strings/translations), and fails on any reference to the removed
  `backends` package. Run this after edits. There is **no CI, no pytest, no
  typecheck/lint config** in the repo.
- Before pushing integrated changes, restart HA and exercise the assistant
  live (see HACS note below).

## Release / versioning — read this
- Version strings live in **two** places and must match:
  `custom_components/lemonade_conversation_advanced/manifest.json` and `hacs.json`.
- HACS treats a **higher version string as latest**. Pre-release tags like
  `v0.1.0-beta.93` sort ABOVE `v0.1.0`, so betas hide the stable release. To
  publish a new version, delete the old beta/old-version tags (local + remote)
  or HACS will keep showing the higher one.
- HACS serves a **cached zip per tag**. Re-uploading the same tag does NOT
  refresh it. Always cut a **new version number** (new tag) for a changed
  download; do not force-update an existing tag.

## Conventions that differ from defaults
- `services.yaml` is **intentionally absent** (deleted). The 10 model-management
  services it used to declare were never registered in code. Do NOT recreate it
  unless you also add the service handlers. Model control is a planned future
  feature (could reuse Lemonade's own MCP server).
- `www/` (Lovelace card) was removed; the card is deferred to a future version.
- The "Instrucciones Técnicas" field (`CONF_TECHNICAL_PROMPT`) is rendered with
  placeholders `{index}`, `{response_mode}`, `{time}`, `{date}`, `{current_area}`
  (see `_render_technical_prompt`). Behaviour tweaks go there, not as new code.
- Entity states are injected into the LLM context for read-only questions (by
  area, or by full domain when no area is named). This injection ignores the
  conversation-exposure filter on purpose — keep it that way.
- `DEFAULT_CLEAN_RESPONSES = True`: markdown is stripped from responses for TTS.
  The raw `entity_id` is never shown; names are humanized via `_pretty_entity_name`.

## Architecture pointers
- Entrypoint: `custom_components/lemonade_conversation_advanced/__init__.py`
  (`async_setup` / `async_setup_entry`).
- Conversation agent + streaming + tool loop: `conversation.py`.
- LLM tools (control actions): `llm_tools.py`. AI Task entities: `ai_task.py`.
- Telemetry sensors + coordinator: `sensor.py`, `coordinator.py`.
- Secrets/config: `const.py` (CONF_* / DEFAULT_*), `config_flow.py`.
- Translations: `translations/en.json`, `translations/es.json`, `strings.json`.
