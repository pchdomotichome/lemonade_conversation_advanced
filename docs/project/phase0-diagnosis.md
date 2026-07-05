# Phase 0 Diagnosis

## Baseline date

2026-07-05

## Repo

- Workdir: `/home/hermes/workspace/lemonade_conversation_advanced`
- Branch: `feat/lemonade-advanced-restart`
- Upstream baseline before branch: `main` at `v1.0.0-beta.20`

## Checks run

```bash
python3 -m compileall -q custom_components/lemonade_conversation_advanced
python3 -m json.tool custom_components/lemonade_conversation_advanced/manifest.json
python3 -m json.tool custom_components/lemonade_conversation_advanced/strings.json
python3 -m json.tool custom_components/lemonade_conversation_advanced/translations/en.json
```

Results: all passed.

## Known blockers

- `custom_components/lemonade_conversation_advanced/backends/openai_compat.py` imports missing modules:
  - `..client.LemonadeClient`
  - `..exceptions.LemonadeBackendUnavailableError`
  - `..exceptions.LemonadeError`
- `openai_compat.py` imports missing constants from `const.py`:
  - `DEFAULT_BACKEND`
  - `DEFAULT_CTX_SIZE`
  - `DEFAULT_GPU_LAYERS`
  - `SUPPORTED_BACKENDS`
  - `SUPPORTED_RECIPES`
- No tests directory exists.
- README advertises capabilities/files that are not present in the active codebase.
- Active flow appears to be `conversation.py` + `entity.py` + `config_flow.py` + `ai_task.py`; large older files remain in tree but are not wired.

## Phase 0 target

Make the repository honest and import-safe without attempting the full feature build yet.
