# Prompt Maestro — Lemonade Conversation Advanced (desde 0)

Copia del tirón esto en opencode para que construya la integración completa.

---

## Contexto

Necesito crear una integración custom de Home Assistant desde cero llamada `lemonade_conversation_advanced`. Debe ser un agente de conversación (Assist) que conecta HA con un servidor LLM externo compatible con API OpenAI (ej: servidor Lemonade local, Ollama, vLLM, OpenAI directo).

Requisitos generales:
- **Branch** `feat/lemonade-advanced-restart`
- **Remote** `origin` → `github.com/pchdomotichome/lemonade_conversation_advanced`
- **Tags semver**: `v1.0.0-alpha.1` para primera release
- **Cada feature completa se publica como prerelease** con `gh release create`
- **HA version target**: core 2026.7+ (API estable)

## Estructura de archivos a crear

```
custom_components/lemonade_conversation_advanced/
├── __init__.py          # Setup, LLM API registration, lifecycle
├── manifest.json
├── config_flow.py       # Config + options flow con tabs
├── const.py             # Constantes, defaults, DOMAIN
├── conversation.py      # Entidad de conversación + streaming loop
├── llm_tools.py         # 6 tools HA nativas
├── api.py               # Cliente HTTP para servidor LLM
├── rag.py               # RAG local (keyword matching)
├── index_manager.py     # Índice estructural del hogar
├── entity.py            # Base entity
├── sensor.py            # Sensores de monitoreo
├── number.py            # Números configurables
├── switch.py            # Switches de features
├── select.py            # Selectores
├── services.yaml        # Servicios expuestos
├── strings.json         # Traducciones EN
├── translations/
│   └── es.json          # Traducciones ES
└── diagnostics.py       # Diagnóstico de integración
```

---

## ESPECIFICACIÓN COMPLETA

### 1. `manifest.json`

```json
{
  "domain": "lemonade_conversation_advanced",
  "name": "Lemonade Conversation Advanced",
  "version": "1.0.0-alpha.1",
  "config_flow": true,
  "documentation": "https://github.com/pchdomotichome/lemonade_conversation_advanced",
  "issue_tracker": "https://github.com/pchdomotichome/lemonade_conversation_advanced/issues",
  "requirements": [
    "voluptuous_openapi>=0.1.0"
  ],
  "dependencies": ["conversation"],
  "after_dependencies": ["intent", "assist_pipeline"],
  "iot_class": "local_polling",
  "codeowners": ["@pchdomotichome"],
  "config_flow": {
    "tabs": ["server", "model", "features", "monitoring"]
  }
}
```

### 2. `const.py` — Constantes

- DOMAIN = "lemonade_conversation_advanced"
- CONF_SERVER_URL: str, default "http://localhost:1234"
- CONF_API_KEY: str, default ""
- CONF_MODEL_NAME: str, default "qwen3.5-4b-mtp"
- CONF_TEMPERATURE: float, [0.0, 2.0], default 0.7
- CONF_MAX_TOKENS: int, [64, 32768], default 2048
- CONF_MAX_ITERATIONS: int, [1, 50], default 10
- CONF_TIMEOUT: int, [10, 300], default 60 segundos
- CONF_ENABLE_RAG: bool, default True
- CONF_RAG_TOP_K: int, [1, 50], default 12
- CONF_ENABLE_INDEX_MANAGER: bool, default True
- CONF_ENABLE_MONITORING: bool, default True
- CONF_PROMPT_TEMPLATE: str, default instrucción del sistema
- CONF_LLM_HASS_API: str, default DOMAIN
- DEFAULT_PROMPT: instrucción completa (en español e inglés según locale)

### 3. `config_flow.py` — Config Flow con tabs

Debe tener UN SOLO tipo de subentry: "conversation". Con tabs:

**Tab 1: "Servidor"**
- server_url (str, input)
- api_key (str, password, opcional)
- timeout (int, [10-300])
- Botón "Probar conexión" → llama al endpoint /v1/models del servidor y muestra resultado

**Tab 2: "Modelo"**
- model_name (str, dropdown rellenable desde /v1/models del servidor)
- temperature (float slider, [0.0-2.0], step 0.05)
- max_tokens (int slider, [64-32768])
- max_iterations (int, [1-50])

**Tab 3: "Funcionalidades"**
- enable_rag (boolean)
- rag_top_k (int, [1-50], visible solo si enable_rag)
- enable_index_manager (boolean)
- enable_monitoring (boolean)
- LLM HASS API (select: DOMAIN o "none")

**Tab 4: "Prompt"**
- prompt_template (textarea multilinea, default instrucción)
- Botón "Restaurar default"

Implementar `async_step_*` para cada tab con `CONFIG_SUBENTRY_USER` como step inicial. Usar `voluptuous` para schemas.

### 4. `__init__.py` — Setup y LLM API

```python
async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    # Crear LemonadeLLMAPI y registrarlo
    llm.async_register_api(hass, LemonadeLLMAPI(hass))
    # Forward setup a plataformas
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

PLATFORMS = [Platform.CONVERSATION, Platform.SENSOR, Platform.NUMBER, Platform.SWITCH, Platform.SELECT]

**LemonadeLLMAPI(llm.API):**
- id = DOMAIN
- name = "Lemonade Conversation Advanced"
- `async_get_api_instance(llm_context)`:
  - Lee config del subentry correspondiente
  - Obtiene tools via `async_get_tools(hass, llm_context, DOMAIN)`
  - Devuelve `llm.APIInstance(api=self, api_prompt=..., llm_context=..., tools=..., custom_serializer=...)`

**IndexManager + RAGIndex** se crean en `async_setup_entry` y se almacenan en `hass.data[DOMAIN]`.

Escuchar eventos del registry para refrescar índices:
- `entity_registry_updated`
- `device_registry_updated`
- `area_registry_updated`

### 5. `conversation.py` — La pieza central

**Clase: LemonadeConversationEntity**
- Extiende `conversation.ConversationEntity` + `LemonadeBaseEntity`
- `_attr_supported_features`: CONTROL si CONF_LLM_HASS_API está configurado (nuestro DOMAIN)
- `_attr_supports_streaming = True`

**Método: `_async_prepare_chat_log`**
1. Llama `chat_log.async_provide_llm_data(llm_context, api_id, prompt, extra_system_prompt)`
2. Inyecta IndexManager como `SystemContent` (índice estructural del hogar)
3. Inyecta instrucción: no llamar GetLiveContext, los estados ya están disponibles via tools
4. Log de debug del contenido inyectado

**Método: `_async_handle_chat_log`** — loop principal
```
for iteration in range(max_iterations):
    1. Build messages desde ChatLog -> formato OpenAI
    2. RAG (si enable_rag): keyword match sobre user prompt, inyecta SystemContent con estados de entidades relevantes
    3. Build payload con messages + tools definitions (OpenAI function calling format)
    4. Intentar streaming (SSE):
       a. POST a {server_url}/v1/chat/completions con stream=True
       b. Parsear SSE con _iter_sse_deltas()
       c. Alimentar chat_log.async_add_delta_content_stream()
       d. Si unresponded_tool_results -> continue (nueva iteración)
       e. Si no -> break (respuesta final)
    5. Fallback non-streaming en errores de conexión
    6. Si max_iterations excedido -> error
```

**Método: `_iter_sse_deltas`** — Parser SSE
- Manejar formato OpenAI: `data: {...}` y `data: [DONE]`
- Manejar formato Ollama: JSON por línea con `done: true`
- Extraer `content`, `reasoning_content`/`thinking_content`
- Extraer `tool_calls` con id, function.name, function.arguments
- Tags de thinking: `<nik>...</nik>` y `<|thought|>...</|thought|>`
- Yield dicts compatibles con AssistantContentDeltaDict
- Al final, yield accumulated tool_calls como ToolInput

**Método: `async_process`** — Entry point
- Simplemente `return await super().async_process(user_input)` (deja que HA maneje el streaming)

### 6. `llm_tools.py` — 6 tools HA nativas

SIN GetLiveContext. Cada tool es una subclase de `llm.Tool` con:
- `name`, `description`, `parameters` (vol.Schema)
- `async def async_call(self, hass, tool_input, llm_context) -> JsonObjectType`
- Devolver resultados claros, manejar errores gracefulmente

**Tools:**
1. `get_entity_state(entity_id)` — hass.states.get + attributes
2. `turn_on_entity(entity_id)` — service call homeassistant.turn_on
3. `turn_off_entity(entity_id)` — service call homeassistant.turn_off
4. `toggle_entity(entity_id)` — service call homeassistant.toggle
5. `set_entity_value(entity_id, value, attribute)` — brightness, temp, position, volume, humidity
6. `get_entities_in_area(area)` — entity registry por area_id + fallback por nombre/alias/entity_id que contenga el nombre del área

**`async_get_tools(hass, llm_context, api_id) -> list[llm.Tool] | None`**:
- Si api_id != DOMAIN return None
- Retorna lista de instancias de tools (NO llm.LLMTools — no existe en HA 2026.7+)

### 7. `api.py` — Cliente HTTP para servidor LLM

Clase `LemonadeAPIClient`:
- Constructor: session, server_url, api_key, timeout
- `async list_models() -> list[str]`: GET /v1/models, extrae model IDs
- `async chat_completion(payload, stream) -> AsyncGenerator[dict]`: POST /v1/chat/completions
- `async test_connection() -> bool`: GET /v1/models, verifica reachability
- Manejo de errores: timeouts, HTTP errors, JSON parse errors
- Retry con backoff exponencial (1s, 2s, 4s) para errores transitorios

### 8. `rag.py` — RAG local sin dependencias externas

Clase `RAGIndex`:
- No usa HTTP, no usa embeddings.
- Cache en disco: `{config_dir}/lemonade_rag_cache/entity_index.json`
- `_entries`: lista de dicts {entity_id, domain, name, area, aliases[], name_tokens[], entity_id_tokens[], area_tokens[], alias_tokens[], combined_text}

**Métodos:**
- `load()` / `save()` — persistencia a disco
- `refresh(hass)` — escanea entity registry, tokeniza nombres, guarda
- `query(user_text, top_k=12) -> list[dict]`:
  1. Tokenizar user_text en palabras lowercase
  2. Para cada entry, calcular overlap de tokens con combined_text
  3. Ordenar por score descendente
  4. Devolver top_k
- Indexar con `nltk` no está disponible, usar split simple por espacios y puntuación

### 9. `index_manager.py` — Índice estructural

Clase `IndexManager`:
- `async get_index() -> dict`: 
  - Areas: todas las áreas con sus ids, nombres, aliases
  - Entity registry por área: entidades agrupadas por area_id
  - Dispositivos por área: devices agrupados por area_id
  - Estadísticas: count de entidades, domains, áreas
- Cachear y refrescar ante eventos de registry
- Método `async handle_registry_change(event)` conectado a event bus

### 10. `entity.py` — Base

Clase `LemonadeBaseEntity`:
- Constructor: recibe ConfigEntry + ConfigSubentry
- `_entry`, `_subentry`, `subentry.data` para options
- `entity_id` compuesto: `{DOMAIN}.{subentry.subentry_id}_{name}`
- `unique_id`: combinación de entry.entry_id + subentry.subentry_id

### 11. `sensor.py` — Monitoreo

Sensores creados por cada subentry si enable_monitoring:
- `sensor.{name}_last_token_count` — tokens de última respuesta
- `sensor.{name}_last_response_time` — tiempo de última respuesta (ms)
- `sensor.{name}_total_requests` — total de requests acumulados
- `sensor.{name}_total_tokens_in` — total input tokens
- `sensor.{name}_total_tokens_out` — total output tokens
- `sensor.{name}_last_error` — texto del último error (o "none")
- `sensor.{name}_status` — "online" / "offline" / "error"
- `sensor.{name}_iteration_count` — iteraciones del último loop

Atributos: state_class=total_increasing o measurement, unit_of_measurement según corresponda.

### 12. `number.py` — Parámetros editables desde UI

- `number.{name}_temperature` — override de temperature (0.0-2.0)
- `number.{name}_max_tokens` — override de max_tokens (64-32768)
- Sincronizar con config entry options

### 13. `switch.py` — Feature toggles

- `switch.{name}_enable_rag` — enable/disable RAG
- `switch.{name}_enable_streaming` — enable/disable streaming (forzar non-streaming)
- `switch.{name}_enable_monitoring` — pausar sensores de monitoreo

### 14. `select.py` — Selectores

- `select.{name}_model` — dropdown seleccionable (rellenable desde servidor)
- `select.{name}_llm_api` — "Lemonade Conversation Advanced" o "none"

### 15. `services.yaml`

```yaml
test_connection:
  description: Probar conexión con el servidor LLM
  fields:
    config_entry_id:
      description: ID del config entry
      required: true
      selector:
        config_entry:
          integration: lemonade_conversation_advanced

refresh_indexes:
  description: Forzar refresco de índices (RAG + IndexManager)
  fields:
    config_entry_id:
      required: true
      selector:
        config_entry:
          integration: lemonade_conversation_advanced
```

### 16. `diagnostics.py`

Implementar `async_get_config_entry_diagnostics`:
- Config entry data + options
- Subentry data
- Estado de sensores de monitoreo
- Lista de entidades creadas
- RAG stats (entradas en índice, tamaño de caché)
- Últimos errores (últimos 10)
- Versión de la integración

### 17. Traducciones

`strings.json` (EN) + `translations/es.json` (ES):
- Títulos de tabs
- Labels de campos
- Descripciones
- Errores de validación
- Estados de sensores

---

## PRINCIPIOS DE DISEÑO

1. **Sin dependencias HTTP externas** — RAG es local, tools son nativas. Solo el LLM requiere HTTP.
2. **6 tools, no 20** — Al usar nuestro propio `LemonadeLLMAPI` con solo las tools que definimos, reducimos tokens de prompt ~50%.
3. **Prompt caching** — El IndexManager y prompt del sistema se mantienen estables entre requests.
4. **Fallback robusto** — Streaming → non-streaming → error claro.
5. **Monitoreo nativo** — Sensores HA para todo, no logs que nadie lee.
6. **Config desde UI** — Todos los parámetros editables desde entities (number, switch, select) sin tocar YAML.
7. **Reset automático**: cada conversación nueva empieza con un chat_log fresco.
8. **Sin archivos YAML** — Todo configurable desde config flow y entities.

---

## CHECKLIST DE PUBLICACIÓN

Cada vez que completes un bloque funcional:
1. `git add -A`
2. `git commit -m "feat: descripción (v1.0.0-alpha.N)"`
3. `git tag v1.0.0-alpha.N`
4. `git push origin feat/lemonade-advanced-restart`
5. `git push origin v1.0.0-alpha.N`
6. `gh release create v1.0.0-alpha.N --title "v1.0.0-alpha.N" --notes "..." --prerelease`

---

## ORDEN DE CONSTRUCCIÓN RECOMENDADO

1. `manifest.json` + `const.py` + strings de traducción
2. `entity.py` (base) + `__init__.py` (setup + LLM API)
3. `config_flow.py` (config flow completo con tabs)
4. `llm_tools.py` (6 tools)
5. `api.py` (cliente HTTP)
6. `conversation.py` (entity + streaming loop)
7. `index_manager.py`
8. `rag.py`
9. `sensor.py`, `number.py`, `switch.py`, `select.py`
10. `services.yaml` + `diagnostics.py`
11. Probar end-to-end con servidor Lemonade local
12. Publicar alpha.1

---

## PRUEBA MÍNIMA POST-CONSTRUCCIÓN

1. Recargar integraciones, agregar Lemonade desde UI
2. Configurar tabs: server URL, modelo, features
3. Ir a Asistente → cambiar LLM API a "Lemonade Conversation Advanced"
4. Preguntar: "hay alguna luz encendida en el comedor?"
5. Verificar pipeline log en HA:
   - Sin errores de AttributeError/ImportError
   - Tool calls correctas (get_entities_in_area → get_entity_state para cada luz)
   - Streaming funcionando (tokens aparecen uno a uno)
   - Sensores de monitoreo actualizados
