# Plan: Lemonade Conversation Advanced Restart

## Goal

Poner en marcha `pchdomotichome/lemonade_conversation_advanced` como integración Home Assistant robusta para Lemonade Server, con Hermes como director técnico y OpenCode como coder delegado bajo instrucciones concretas.

## Ground Rules

- Repo principal: `/home/hermes/workspace/lemonade_conversation_advanced`.
- Branch: `feat/lemonade-advanced-restart`.
- Hermes mantiene ownership de arquitectura, decisiones, pruebas, documentación y verificación.
- OpenCode puede implementar tareas acotadas, pero Hermes verifica diff, tests y estado real antes de reportar éxito.
- No tocar Home Assistant real ni publicar releases sin instrucción explícita.
- Priorizar compatibilidad HACS y workflow repo-based.

## Inputs

- `/home/hermes/workspace/lemonade_analysis_roadmap.md`
- `/home/hermes/workspace/lemonade_conversation_analysis.md`
- Wiki: `/mnt/wiki/concepts/lemonade-conversation-advanced-*`
- Lemonade Server esperado: `http://10.0.98.218:13305`

## Current Hypotheses

- El repo actual en `lemonade_conversation_advanced` es más nuevo que algunos análisis previos.
- Hay otra copia vieja en `lemonade_conversation_advanced_repo`; no usar como fuente principal salvo comparación histórica.
- La prioridad inicial es diagnóstico reproducible antes de borrar/refactorizar.

## Phases

### Phase 0 — Baseline and repair

1. [ ] Capturar estructura, imports, manifest, versioning y estado de tests.
2. [ ] Ejecutar checks reproducibles: compileall, pytest si existe, import sanity estático.
3. [ ] Comparar análisis previos contra estado actual y actualizar roadmap.
4. [ ] Identificar código muerto/roto real, no asumir por docs viejos.
5. [ ] Hacer cambios mínimos para dejar baseline verde.

### Phase 1 — Conversation core

1. [ ] Implementar/validar ChatLog API pattern moderno.
2. [ ] Implementar tool-calling loop real.
3. [ ] Streaming incremental compatible voice pipeline.
4. [ ] Multi-turn memory vía ChatLog.
5. [ ] Tests unitarios de conversation flow.

### Phase 2 — Config/options and HACS polish

1. [ ] Config flow y options flow alineados con HA 2025/2026.
2. [ ] Traducciones sincronizadas.
3. [ ] Manifest/version/hacs correctos.
4. [ ] README honesto: solo features reales.

### Phase 3 — Advanced capabilities

1. [ ] Smart entity discovery / MCP opcional.
2. [ ] AI Task entities reales.
3. [ ] RAG/embeddings Lemonade si conviene.
4. [ ] Sensores/servicios maduros.

## Verification Commands

```bash
python -m compileall custom_components/lemonade_conversation_advanced
pytest -q
python -m json.tool custom_components/lemonade_conversation_advanced/manifest.json
```

## Documentation Targets

- `docs/project/status.md`
- `docs/project/decisions.md`
- `/mnt/wiki/projects/lab/lemonade-conversation-advanced.md`
- `/mnt/wiki/log.md`
