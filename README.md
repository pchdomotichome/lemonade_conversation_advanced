# 🧠 Lemonade Conversation Advanced para Home Assistant

[![GitHub Release](https://img.shields.io/github/release/pchdomotichome/lemonade_conversation_advanced.svg)](https://github.com/pchdomotichome/lemonade_conversation_advanced/releases)
[![License](https://img.shields.io/github/license/pchdomotichome/lemonade_conversation_advanced.svg)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

> 🔧 **Integración avanzada para usar Lemonade Server como asistente de conversación en Home Assistant**

## 📌 Descripción

**Lemonade Conversation Advanced** es una integración para Home Assistant que usa
[Lemonade Server](https://lemonade-server.ai/) (modelos locales, GGUF/ONNX) como
agente de conversación con function-calling nativo. Permite controlar y consultar
dispositivos de tu hogar por voz o texto, con respuestas fluidas vía streaming.

## 🚀 Características

- ✅ Agente de conversación nativo de Home Assistant (compatible con Voice Pipeline)
- ✅ **Inyección de estados en contexto**: ante preguntas como *"¿hay luces prendidas?"*, el asistente recibe el estado real de las entidades y responde sin tener que llamar tools
- ✅ **Tools LLM** para controlar dispositivos: `get_entity_state`, `turn_on_entity`, `turn_off_entity`, `toggle_entity`, `set_entity_value`, `get_entities_in_area`, `run_script`, `activate_scene`, `web_search`
- ✅ **Instrucciones técnicas** configurables (campo *Instrucciones Técnicas*) para ajustar el comportamiento sin tocar código
- ✅ **Niveles de personalidad/sarcasmo** seleccionables (Predeterminada, Pirata, Robot, Mayordomo, Sarcástico Argentino, Personalizada)
- ✅ **Streaming** para pipelines de voz fluidos
- ✅ **Telemetría** del servidor Lemonade (sensores de hardware y performance)
- ✅ **AI Task entities** (tema generator, extractor de entidades, resumen, clasificador de intención)
- ✅ **RAG local** opcional para recuperar entidades por palabras clave
- ✅ Multi-modelo vía subentries (distintos modelos por tarea)
- ✅ Configuración completa por UI (Config Flow + Options Flow)

## 🛠️ Requisitos

- Home Assistant 2025.7 o superior
- [Lemonade Server](https://lemonade-server.ai/) corriendo en tu red local (accesible por HTTP)
- Un modelo compatible cargado en Lemonade Server (GGUF, ONNX, FLM)
- Conexión de red entre HA y el servidor Lemonade

## 📦 Instalación

### Opción 1: HACS (Recomendado)

1. Añade este repo como **Custom Repository** en HACS (categoría *Integration*):
   `https://github.com/pchdomotichome/lemonade_conversation_advanced`
2. Busca **Lemonade Conversation Advanced** e instálala.
3. Reinicia Home Assistant.

### Opción 2: Manual

1. Copia `custom_components/lemonade_conversation_advanced` a
   `config/custom_components/` de tu Home Assistant.
2. Reinicia Home Assistant.

## ⚙️ Configuración

1. **Settings → Devices & Services → Integrations → + Add Integration**.
2. Busca **Lemonade Conversation Advanced**.
3. **Paso 1 – Conexión**: URL del servidor (ej. `http://10.0.98.218:13305`) y
   API Key opcional (si Lemonade tiene auth).
4. **Paso 2 – Modelo**: elige el modelo por defecto y parámetros (temperatura,
   max tokens, streaming, timeout).
5. **Subentries (asistentes)**: desde *Configure* en la integración podés crear
   uno o más asistentes (*conversation subentries*), cada uno con su propio
   modelo, personalidad, idioma y comportamiento.

> Para usar el asistente por voz, asignalo en
> **Settings → Voice Assistants → (tu asistente) → Conversation agent**.

## 🎯 Cómo responde a preguntas (inyección de estados)

Cuando preguntás algo sobre dispositivos, la integración inyecta automáticamente
el estado actual de las entidades relevantes en el contexto del modelo:

- Si nombrás un **área** (ej. *"¿qué luces hay en el comedor?"*), se inyectan las
  entidades de esa área.
- Si preguntás por un **dominio sin área** (ej. *"¿hay alguna luz encendida?"*),
  se inyectan **todas** las entidades de ese dominio (aunque no estén expuestas
  al agente de conversación), para que el modelo responda con la verdad.

El modelo cita el **nombre amigable** de la entidad (no el `entity_id`), y las
respuestas se limpian de formato markdown para que el TTS lea natural.

## 🔧 Instrucciones Técnicas (comportamiento configurable)

El campo **Instrucciones Técnicas** del asistente permite cambiar el comportamiento
del modelo sin editar código. Soporta placeholders que se rellenan en runtime:

| Placeholder | Contenido |
|-------------|-----------|
| `{index}` | Índice compacto de áreas y dominios del hogar |
| `{response_mode}` | Reglas de follow-up según el modo configurado |
| `{time}` / `{date}` | Hora y fecha actuales |
| `{current_area}` | Área actual (si la provee HA) |

Por defecto trae instrucciones que: describen las tools disponibles, indican que
para lectura use los estados inyectados (sin llamar tools), y que para control
use los `entity_id` mostrados. Podés reemplazarlo por tu propio texto.

## 🤖 Tools LLM disponibles

El asistente puede controlar y consultar HA por sí solo:

| Tool | Acción |
|------|--------|
| `get_entity_state` | Estado actual de una entidad |
| `turn_on_entity` / `turn_off_entity` / `toggle_entity` | Encender/apagar/alternar |
| `set_entity_value` | Fijar valor (brillo, temperatura, volumen…) |
| `get_entities_in_area` | Listar entidades de un área |
| `run_script` / `activate_scene` | Ejecutar script / escena |
| `web_search` | Búsqueda web (si está habilitada) |

## 📊 Sensores de telemetría

Por cada servidor Lemonade se crea un juego de sensores (se actualizan cada
`scan_interval`, default 30 s):

| Sensor | Describe |
|--------|----------|
| `sensor.lemonade_server_version` | Versión de Lemonade Server |
| `sensor.lemonade_model_loaded` | Último modelo accedido (atributo `loaded_models` con la lista) |
| `sensor.lemonade_cpu_percent` / `_gpu_percent` / `_npu_percent` | Uso CPU/GPU/NPU (%) |
| `sensor.lemonade_memory_gb` / `_vram_gb` | RAM y VRAM usadas (GiB) |
| `sensor.lemonade_ttft_avg` | Tiempo medio al primer token (s) |
| `sensor.lemonade_tps_avg` | Tokens por segundo medios |
| `sensor.lemonade_last_input_tokens` / `_last_output_tokens` | Tokens de la última request |

Los valores que el hardware no expone (p. ej. NPU sin NPU) quedan `unknown`.

## 🧩 AI Task entities

- `ai_task.lemonade_theme_generator` — genera temas YAML
- `ai_task.lemonade_extract_entities` — extrae entidades de un texto
- `ai_task.lemonade_summarize` — resume texto
- `ai_task.lemonade_classify_intent` — clasifica la intención de un comando HA

## 🔗 Voice Pipeline

Compatible con el pipeline de voz de HA (STT + TTS + VAD). Recomendado:
Whisper/faster-whisper para STT y Piper para TTS vía Wyoming.

## 🧪 Verificación rápida

```bash
python3 scripts/smoke_check.py
```

Valida sintaxis, JSON de manifest/strings/translations y archivos esperados.

## 🤝 Contribuciones

1. Fork el repositorio
2. Crea una rama (`git checkout -b feat/nueva-funcionalidad`)
3. Commit (`git commit -m 'feat: ...'`)
4. Push y abre un Pull Request

## 📄 Licencia

MIT — ver [LICENSE](LICENSE).

## 🧑‍💻 Autor

[pchdomotichome](https://github.com/pchdomotichome)

---

🚀 **¡Haz tu hogar inteligente con modelos locales!**
