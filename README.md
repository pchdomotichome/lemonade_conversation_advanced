# 🧠 Lemonade Conversation Advanced for Home Assistant

[![GitHub Release](https://img.shields.io/github/release/pchdomotichome/lemonade_conversation_advanced.svg)](https://github.com/pchdomotichome/lemonade_conversation_advanced/releases)
[![License](https://img.shields.io/github/license/pchdomotichome/lemonade_conversation_advanced.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2025.7+-blue.svg)](https://www.home-assistant.io/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

> 🔧 **Integración avanzada para usar Lemonade Server como asistente de conversación en Home Assistant**

## 📌 Descripción

**Lemonade Conversation Advanced** es una integración completa para Home Assistant que permite utilizar modelos de lenguaje grandes (LLM) locales a través de [Lemonade Server](https://lemonade-server.ai/). Combina las capacidades del servidor Lemonade con el asistente de voz de Home Assistant, creando un asistente inteligente similar a Google Home o Alexa, pero completamente local, privado y personalizable.

## 🚀 Características

- ✅ **Integración nativa** como agente de conversación en Home Assistant
- ✅ **Gestión completa de modelos** (pull, load, unload, list) desde HA
- ✅ **Custom LLM API** con 6 tools Lemonade-specific para que el LLM gestione sus propios modelos
- ✅ **Sensors de hardware** en tiempo real (VRAM, NPU, GPU, modelo cargado, health)
- ✅ **Function calling nativo** OpenAI-compatible para control de Home Assistant
- ✅ **Streaming responses** para voice pipeline fluido
- ✅ **AI Task entities** nativas (theme generator, entity extractor, summarizer, intent classifier)
- ✅ **Multi-model support** con subentries (diferentes modelos para diferentes tareas)
- ✅ **Multi-backend** (llama.cpp, RyzenAI NPU, vLLM, FastFlowLM)
- ✅ **Configuración via UI** completa (Config Flow + Options Flow)
- ✅ **Servicios personalizados** (12+ servicios para gestión total)
- ✅ **Compatible con Wyoming** (STT/TTS) para pipeline de voz completo

## 🛠️ Requisitos

- Home Assistant 2025.7 o superior
- Lemonade Server 10.x corriendo en tu red local
- Acceso a modelos compatibles (GGUF, ONNX, FLM)
- Python 3.12+

## 📦 Instalación

### Opción 1: A través de HACS (Recomendado)

1. En Home Assistant, ve a **Settings** → **Devices & Services** → **Integrations**
2. Haz clic en el botón **+ Add Integration**
3. Busca **"Lemonade Conversation Advanced"**
4. Instala la integración

### Opción 2: Manual

1. Copia el directorio `custom_components/lemonade_conversation_advanced` en tu directorio de configuración de Home Assistant (`config/custom_components/`)
2. Reinicia Home Assistant

## ⚙️ Configuración

1. Ve a **Settings** → **Devices & Services** → **Integrations**
2. Haz clic en **+ Add Integration**
3. Busca **"Lemonade Conversation Advanced"**
4. **Paso 1 - Conexión**: Ingresa la URL del servidor Lemonade:
   - Ejemplo: `http://10.0.98.218:13305`
   - API Key (opcional si Lemonade tiene auth habilitado)
5. **Paso 2 - Modelo**: Selecciona un modelo de los disponibles
6. **Paso 3 - Parámetros**: Configura temperatura, max tokens, streaming

## 🔧 Funcionalidades Avanzadas

### 🔄 Gestión de Modelos (via Services o LLM Tools)

```yaml
# Cargar modelo específico
service: lemonade_conversation_advanced.load_model
data:
  model_name: "user.Llama-3.2-1B-Instruct-GGUF"
  ctx_size: 8192
  gpu_layers: -1
  backend: "llamacpp"

# Descargar modelo del registry
service: lemonade_conversation_advanced.pull_model
data:
  model_name: "user.Dolphin3.0-Llama3.2-3B-GGUF"
  checkpoint: "main"
  recipe: "llamacpp"

# Listar todos los modelos
service: lemonade_conversation_advanced.list_models
data:
  show_all: true
```

### 🤖 Tools LLM (el LLM puede auto-gestionarse)

El LLM tiene acceso a estas tools nativas:
- `lemonade_pull_model` - Descargar modelos
- `lemonade_load_model` - Cargar modelos en memoria
- `lemonade_unload_model` - Descargar modelos de memoria
- `lemonade_list_models` - Listar modelos disponibles
- `lemonade_system_info` - Info de hardware, backends, modelos cargados
- `lemonade_get_stats` - Estadísticas de performance

### 📊 Sensors Disponibles

| Sensor | Descripción |
|--------|-------------|
| `sensor.lemonade_health` | Estado del servidor (healthy/unhealthy) |
| `sensor.lemonade_loaded_model` | Modelo actualmente cargado |
| `sensor.lemonade_vram_usage` | Uso de VRAM en MB |
| `sensor.lemonade_npu_usage` | Uso de NPU (0-100%) |
| `sensor.lemonade_model_count` | Modelos descargados/cargados |
| `sensor.lemonade_gpu_usage` | Uso de GPU |
| `sensor.lemonade_inference_speed` | Velocidad de inferencia (tokens/s) |

### 🎯 AI Task Entities

- `ai_task.lemonade_theme_generator` - Generar temas YAML
- `ai_task.lemonade_extract_entities` - Extraer entidades de texto
- `ai_task.lemonade_summarize` - Resumir texto
- `ai_task.lemonade_classify_intent` - Clasificar intención HA

## 🏗️ Arquitectura

```
custom_components/lemonade_conversation_advanced/
├── __init__.py                 # Entry point, backend registry
├── manifest.json               # Metadatos HA
├── const.py                    # Constantes y defaults
├── config_flow.py              # Config Flow + Options Flow (3 steps)
├── conversation.py             # ConversationAgent (streaming + tools)
├── ai_task.py                  # AI Task entities (4 tasks)
├── sensor.py                   # 7 Sensors con Coordinator
├── llm_api.py                  # Custom LLM API (6 tools)
├── client.py                   # LemonadeClient (aiohttp + AsyncOpenAI)
├── backends/
│   ├── __init__.py
│   └── openai_compat.py        # Backend OpenAI-compatible
├── services.py                 # Service handlers
├── services.yaml               # Definiciones de servicios
├── utils.py                    # Streaming parser, thinking blocks
├── exceptions.py               # Excepciones tipadas
└── translations/
    └── en.json                 # Strings UI
```

## 🔗 Integración con Voice Pipeline

Compatible con Wyoming para pipeline de voz completo:

- **STT**: faster-whisper via Wyoming
- **TTS**: Piper via Wyoming
- **VAD**: Silero VAD
- **Barge-in**: Cancelar TTS si usuario habla

## 🧪 Testing

```bash
# Ejecutar tests
pytest custom_components/lemonade_conversation_advanced/tests/

# Coverage
pytest --cov=custom_components.lemonade_conversation_advanced
```

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feat/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'feat: agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feat/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT - mira el archivo [LICENSE](LICENSE) para detalles.

## 🧑‍💻 Desarrollador

Desarrollado por [pchdomotichome](https://github.com/pchdomotichome)

---

## 🙏 Agradecimientos

- [Lemonade Server](https://lemonade-server.ai/) por el servidor de inferencia increíble
- [extended_openai_conversation](https://github.com/jekalmin/extended_openai_conversation) por patterns de function calling
- [home-llm](https://github.com/acon96/home-llm) por arquitectura multi-backend y streaming
- [hass-agent-llm](https://github.com/aradlein/hass-agent-llm) por memory system y dual-LLM
- [ai_agent_ha](https://github.com/sbenodiz/ai_agent_ha) por dashboard/automation generation

---

🚀 **¡Haz tu hogar inteligente con modelos locales!**