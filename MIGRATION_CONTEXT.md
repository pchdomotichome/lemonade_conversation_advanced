# Contexto de migración — Lemonade Conversation Advanced

## Estado actual (beta.37, branch `feat/lemonade-advanced-restart`)

Archivos fuente en `/config/custom_components/lemonade_conversation_advanced/` (o `custom_components/` dentro del config de HA).

Último tag: `v0.1.0-beta.36` (próximo: `v0.1.0-beta.37`)
— https://github.com/pchdomotichome/lemonade_conversation_advanced

---

## Integración: qué hace

Agente de conversación (Assist) que conecta HA con un LLM externo (servidor Lemonade local en `server_url`). El usuario habla en lenguaje natural, el LLM decide qué tools de HA llamar para responder/actuar.

### Pipeline:
1. Usuario envía texto → `conversation.lemonade_*` entity
2. `_async_prepare_chat_log` → prepara prompt inicial (system + tools via `async_provide_llm_data`)
3. Inyecta **IndexManager** (índice estructural del hogar: áreas, entidades, dispositivos)
4. Inyecta instrucción: "no llamar GetLiveContext"
5. **RAG** opcional: busca entidades relevantes por keyword matching (token overlap) y agrega sus estados al prompt
6. Loop de tool calls (hasta `max_iterations`, default 10):
   - Envía mensajes al servidor Lemonade (`/v1/chat/completions`)
   - Stream: parsea SSE (OpenAI + Ollama format)
   - Tool calls: las ejecuta via `chat_log.async_add_delta_content_stream` (que llama `chat_log.llm_api.async_call_tool`)
   - Si el LLM vuelve a pedir tool → continúa loop
   - Si responde texto → devuelve resultado
   - Fallback a non-streaming en errores de conexión

---

## Archivos clave

### `__init__.py`
- Registra `LemonadeLLMAPI(llm.API)` con id = DOMAIN
- `async_get_api_instance`: llama `local_async_get_tools` → devuelve `llm.APIInstance(tools=list[llm.Tool])`
- Crea `IndexManager` y `RAGIndex` en `hass.data[DOMAIN]`

⚠️ **IMPORTANTE:** `LLM API` en la UI de la entidad de conversación debe estar configurado como **"Lemonade Conversation Advanced"** (no "Assist"). Si está en "Assist", fallbackea al pipeline default de HA con 20 tools.

### `api.py` (NUEVO en beta.37)
- `LemonadeAPIClient`: cliente HTTP dedicado para el servidor Lemonade.
- **True streaming**: parsea SSE línea por línea via `response.content.readline()` (en vez de buffer-then-parse).
- **Retry con backoff**: reintenta la conexión inicial hasta `max_retries` veces con backoff exponencial. No reintenta mid-stream para evitar duplicación de contenido.
- **Excepciones tipadas**: `LemonadeConnectionError`, `LemonadeAuthError`, `LemonadeAPIError`.
- Métodos: `chat_completions_stream()`, `chat_completions()`, `health_check()`.
- Timeouts configurables: `request_timeout`, `connect_timeout`.
- `_iter_sse()`: parser SSE, soporta OpenAI y Ollama formats, incluyendo tags de pensamiento.

### `conversation.py`
- `LemonadeConversationEntity` extiende `conversation.ConversationEntity`
- `_async_prepare_chat_log`: llama `async_provide_llm_data`, inyecta IndexManager + GetLiveContext suppression
- `_async_handle_chat_log`: loop de tool calls, streaming SSE, RAG injection
- Usa `LemonadeAPIClient` en vez de HTTP calls inline.
- `_build_messages`: serializa ChatLog a formato OpenAI

### `llm_tools.py`
6 tools nativas de HA, sin `GetLiveContext`:
- `get_entity_state(entity_id)` — obtiene estado completo de una entidad
- `turn_on_entity(entity_id)` — enciende
- `turn_off_entity(entity_id)` — apaga
- `toggle_entity(entity_id)` — toggle
- `set_entity_value(entity_id, value, attribute)` — brightness/temperature/position/volume/humidity
- `get_entities_in_area(area)` — busca por area_id + fallback por nombre/alias/entity_id

**Problema conocido:** Algunas entidades `switch_as_x` no heredan el área. FIX en beta.35-36: fallback busca entidades cuyo nombre, entity_id, o aliases contengan el nombre del área.

### `rag.py`
- `RAGIndex`: cache en disco de entidades (entity_id, domain, name, area, aliases)
- `query(user_prompt, top_k)` → token overlap matching
- Se refresca ante cambios en entity registry
- Cache en `{config_dir}/lemonade_rag_cache/entity_index.json`

### `index_manager.py`
- `IndexManager`: escanea device registry + entity registry + area registry
- Construye índice estructural del hogar
- Inyectado como SystemContent en cada request

### `entity.py`
- `LemonadeBaseEntity`: clase base, lee config de `subentry.data`

### `const.py`
- DOMAIN, CONF_*, defaults

---

## Config entry (subentry type "conversation")
Campos en options:
- `model_name` — default "qwen3.5-4b-mtp"
- `temperature` — default 0.7
- `max_tokens` — default 2048
- `max_iterations` — default 10 (límite de tool calls loop)
- `CONF_LLM_HASS_API` — debe ser "lemonade_conversation_advanced" (nuestro DOMAIN)
- `CONF_PROMPT` — instrucciones del sistema
- `enable_rag` — bool, default True
- `rag_top_k` — default 12
- `server_url` — URL del servidor Lemonade
- `api_key` — opcional

---

## Issues conocidos / por resolver

### 1. Streaming: primera iteración OK, posteriores fallan
- **Problema (parcialmente resuelto en beta.37):** `api.py` ahora usa true streaming línea por línea via `response.content.readline()`, con retry en la conexión inicial.
- **Problema persistente:** Si el stream falla mid-stream (después de haberse recibido contenido), la reconexión no se intenta para evitar duplicación. Se cae al fallback non-streaming. Esto puede causar latencia adicional en tool-call loops largos.
- **Posible fix futuro:** implementar mid-stream recovery con replay del último delta, o usar WebSocket en vez de SSE si Lemonade lo soporta.

### 2. Sin API Client dedicado
- **Problema:** las llamadas HTTP están inline en `conversation.py`. Sin manejo de errores tipado, sin session management robusto.
- **Fix:** extraer a `api.py` con clase `LemonadeAPIClient`, excepciones tipadas (`ConnectionError`, `AuthError`, `APIError`), retry con backoff, timeout configurable.
- **Código de referencia:** `lemonade_assist/api.py` (tiene buena base: excepciones, headers, session management).

### 3. Sin sensores de monitoreo del servidor
- **Problema:** no hay visibilidad del estado del servidor Lemonade (modelo cargado, VRAM, tokens/s, health).
- **Fix:** agregar `Platform.SENSOR` con `DataUpdateCoordinator` (health cada 10s, stats cada 30s).
- **Sensores sugeridos:** server_status, loaded_model, vram_used, vram_total, gpu_usage, tokens_per_second, active_backend, context_size, last_error, total_requests, total_tokens_in/out.

### 4. Sin servicios de gestión
- **Problema:** no hay servicios expuestos (solo las tools del LLM). No se puede load/unload/pull modelos desde automations.
- **Solución:** agregar `services.yaml` con load_model, unload_model, refresh_indexes, test_connection, generate_content, get_stats.

### 5. Sin eventos de integración
- **Problema:** no se disparan eventos cuando cambia el estado del servidor (modelo cargado/descargado, health change).
- **Solución:** eventos `{DOMAIN}_model_loaded`, `{DOMAIN}_model_unloaded`, `{DOMAIN}_health_changed` para automaciones reactivas.

### 6. IndexManager no se actualiza en caliente
- **Problema:** se construye al arrancar. No se refresca si cambian dispositivos/entidades/áreas.
- **Fix:** conectar a eventos `entity_registry_updated`, `device_registry_updated`, `area_registry_updated`.

### 7. RAG no elimina tool calls redundantes
- **Problema:** RAG inyecta estados de entidades en el prompt pero el LLM igual puede llamar `get_entity_state` para esas mismas entidades.
- **Fix:** el prompt debe decir explícitamente "ya tenés los estados de estas entidades, no llames get_entity_state para ellas".

### 8. Sin soporte para server management tools
- **Problema:** el LLM no puede auto-gestionar el servidor (cambiar modelo, ajustar context_size, etc.)
- **Fix:** agregar tools opcionales: `lemonade_load_model`, `lemonade_unload_model`, `lemonade_list_models`, `lemonade_get_server_stats`.

---

## Lemonade Server v10.10.0 — Novedades relevantes

Lanzado 08 Jul 2026. Ver: https://github.com/lemonade-sdk/lemonade/releases/tag/v10.10.0

### Lo que impacta en la integración

| Feature | Relevancia |
|---------|-----------|
| **MCP Server** (v10.8) | Lemonade ahora expone MCP. Se podría conectar HA vía MCP en vez de REST. Alternativa interesante. |
| **Suspend inhibitor** | Mantiene la PC despierta mientras corre inferencia. Relevante si HA está en el mismo equipo. |
| **Model files endpoint** `GET /v1/models/{id}/files` | Útil para mostrar archivos del modelo en la UI de configuración. |
| **RoutingPolicyEngine** | Enrutamiento inteligente entre backends. No impacta directamente pero mejora estabilidad. |
| **Client disconnect handling fix** | Lemonade v10.10.0 incluye fix para `handle client disconnects in responses telemetry` — relevante para nuestro problema de desconexiones. |
| **Audio generation** (ThinkSound + ACE-Step) | Si HA integra media, podría usarse. Baja prioridad ahora. |
| **vLLM ROCm reliability** | Mejora compatibilidad con GPUs AMD. |

### MCP Server de Lemonade (v10.8+)
Lemonade ahora puede funcionar como MCP server estándar. Documentación: https://github.com/lemonade-sdk/lemonade/blob/main/docs/api/mcp.md
- Cualquier cliente MCP (Claude Desktop, Cursor, etc.) puede interactuar con Lemonade
- Expone tools para chat, audio transcription, image generation
- **Potencial:** en el futuro, HA podría conectar Lemonade vía MCP en vez de REST/OpenAI API

---

## Lemonade Server como Add-on de HA

Actualmente no existe un add-on oficial de Lemonade Server para HA Supervisor. Habría que crearlo.
- Sería un add-on que instala y gestiona `lemond` dentro de HA
- Puerto default: 13305 (cambiado en v10.1.0, antes era 1234)
- API Key vía env vars: `LEMONADE_API_KEY`, `LEMONADE_ADMIN_API_KEY`
- Config via `config.json` en `/var/lib/lemonade/.cache/lemonade/config.json` (Linux systemd)
- La integración `lemonade_conversation_advanced` apunta a este servidor

Si te interesa, se puede crear un add-on aparte que:
1. Instale `lemond` en el contenedor Supervisor
2. Exponga Ingress para la GUI de Lemonade
3. Configure auto-arranque y API key
4. Se integre naturalmente con la conversación entity

---

## Prioridades de mejora

| Prio | Cambio | Impacto | Estado |
|------|--------|---------|--------|
| 🔴 | **API client dedicado + true streaming** | Mantenibilidad, errores, retry, latencia | ✅ beta.37 |
| 🔴 | **Sensores + coordinators** | Visibilidad del servidor | ⏳ pendiente |
| 🟡 | **Servicios de gestión** | Automations |
| 🟡 | **Eventos de integración** | Automations reactivas |
| 🟡 | **IndexManager hot-reload** | Consistencia de datos |
| 🟢 | **Server management tools** | Auto-gestión del LLM |
| 🟢 | **Add-on Lemonade para HA** | Despliegue integrado |

---

## Releases publicadas
| Versión | Cambio |
|---------|--------|
| beta.22-28 | Error handling, streaming, tool execution, RAG |
| beta.29 | RAG reemplazado por keyword local (sin HTTP) |
| beta.30 | SystemContent injectado (async_add_system_content no existe en HA) |
| beta.31 | RAGIndex reusado desde hass.data |
| beta.32 | IndexManager conectado |
| beta.33 | Instrucción "no llamar GetLiveContext" + debug |
| beta.34 | FIX: llm.LLMTools → list[llm.Tool] (no existe en esta HA) |
| beta.35 | get_entities_in_area fallback por nombre/entity_id |
| beta.36 | get_entities_in_area fallback también por aliases |
| beta.37 | api.py: LemonadeAPIClient con true streaming, retry backoff, excepciones tipadas; refactor conversation.py |

---

## Tags git
```
v0.1.0-beta.22  ..  v0.1.0-beta.36
```
Próximo tag: `v0.1.0-beta.37`
Branch: `feat/lemonade-advanced-restart`
Remote: `origin` → `github.com/pchdomotichome/lemonade_conversation_advanced`

---

## Para probar ahora
1. Confirmar que `LLM API` esté en "Lemonade Conversation Advanced"
2. Preguntar "hay alguna luz encendida en el comedor?" con beta.36
3. Ver pipeline log en HA → debe mostrar tool calls a `get_entities_in_area` con las 4 luces
4. Verificar que el modelo las consulte y responda correctamente
