# 🧠 Lemonade Assistant Advanced for Home Assistant

[![GitHub Release](https://img.shields.io/github/release/pchdomotichome/lemonade_assistant_advanced.svg)](https://github.com/pchdomotichome/lemonade_assistant_advanced/releases)
[![License](https://img.shields.io/github/license/pchdomotichome/lemonade_assistant_advanced.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.12-blue.svg)](https://www.home-assistant.io/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> 🔧 **Integración avanzada para usar modelos locales de Lemonade Server como asistente de voz en Home Assistant**

## 📌 Descripción

**Lemonade Assistant Advanced** es una integración completa para Home Assistant que permite utilizar modelos de lenguaje grandes (LLM) locales a través de [Lemonade Server](https://lemonade-server.ai/). Esta solución combina las capacidades del servidor Lemonade con el asistente de voz de Home Assistant, creando un asistente inteligente similar a Google Home o Alexa, pero completamente local y seguro.

## 🚀 Características

- ✅ **Integración completa con Home Assistant** como conversación
- ✅ **Soporte para múltiples modelos** (GGUF, ONNX, FLM)
- ✅ **Gestión avanzada de modelos** (descargar, cargar, descargar)
- ✅ **Sistema de salud del servidor** (monitoreo en tiempo real)
- ✅ **Soporte para streaming de respuestas**
- ✅ **Configuración flexible** con temperatura, tokens máximos y más
- ✅ **Integración con asistente de voz de Home Assistant**
- ✅ **Compatibilidad con STT/TTS** (Whisper + Piper)
- ✅ **Soporte para herramientas de Home Assistant**

## 🛠️ Requisitos

- Home Assistant 2024.12 o superior
- Lemonade Server corriendo en tu red local
- Acceso a modelos compatibles (GGUF, ONNX, FLM)

## 📦 Instalación

### Opción 1: A través de HACS (recomendado)

1. En Home Assistant, ve a **Settings** → **Devices & Services** → **Integrations**
2. Haz clic en el botón **+ Add Integration**
3. Busca "Lemonade Assistant Advanced"
4. Instala la integración

### Opción 2: Manual

1. Copia el directorio `custom_components/lemonade_assistant_advanced` en tu directorio de configuración de Home Assistant
2. Reinicia Home Assistant

## ⚙️ Configuración

1. Ve a **Settings** → **Devices & Services** → **Integrations**
2. Haz clic en **+ Add Integration**
3. Busca "Lemonade Assistant Advanced"
4. Ingresa la URL del servidor Lemonade:
   - Ejemplo: `http://10.0.98.68:8000`
5. Configura los parámetros adicionales:
   - Modelo por defecto
   - Temperatura (0.0 - 2.0)
   - Máximo de tokens
   - Streaming

## 🧪 Uso Básico

Una vez configurado, el asistente responderá a comandos como:

- "¿Cuánto es 2 + 2?"
- "Enciende la luz de la sala"
- "¿Qué tiempo hace hoy?"

## 🔧 Funcionalidades Avanzadas

### 🔄 Gestión de Modelos

```yaml
# Cargar modelo específico
service: lemonade_assistant_advanced.load_model
data:
  model_name: "Llama-3.2-1B-Instruct-Hybrid"# 🧠 Lemonade Assistant Advanced for Home Assistant
```
[![GitHub Release](https://img.shields.io/github/release/pchdomotichome/lemonade_assistant_advanced.svg)](https://github.com/pchdomotichome/lemonade_assistant_advanced/releases)
[![License](https://img.shields.io/github/license/pchdomotichome/lemonade_assistant_advanced.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.12-blue.svg)](https://www.home-assistant.io/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> 🔧 **Integración avanzada para usar modelos locales de Lemonade Server como asistente de voz en Home Assistant**

## 📌 Descripción

**Lemonade Assistant Advanced** es una integración completa para Home Assistant que permite utilizar modelos de lenguaje grandes (LLM) locales a través de [Lemonade Server](https://lemonade-server.ai/). Esta solución combina las capacidades del servidor Lemonade con el asistente de voz de Home Assistant, creando un asistente inteligente similar a Google Home o Alexa, pero completamente local y seguro.

## 🚀 Características

- ✅ **Integración completa con Home Assistant** como conversación
- ✅ **Soporte para múltiples modelos** (GGUF, ONNX, FLM)
- ✅ **Gestión avanzada de modelos** (descargar, cargar, descargar)
- ✅ **Sistema de salud del servidor** (monitoreo en tiempo real)
- ✅ **Soporte para streaming de respuestas**
- ✅ **Configuración flexible** con temperatura, tokens máximos y más
- ✅ **Integración con asistente de voz de Home Assistant**
- ✅ **Compatibilidad con STT/TTS** (Whisper + Piper)
- ✅ **Soporte para herramientas de Home Assistant**

## 🛠️ Requisitos

- Home Assistant 2024.12 o superior
- Lemonade Server corriendo en tu red local
- Acceso a modelos compatibles (GGUF, ONNX, FLM)

## 📦 Instalación

### Opción 1: A través de HACS (recomendado)

1. En Home Assistant, ve a **Settings** → **Devices & Services** → **Integrations**
2. Haz clic en el botón **+ Add Integration**
3. Busca "Lemonade Assistant Advanced"
4. Instala la integración

### Opción 2: Manual

1. Copia el directorio `custom_components/lemonade_assistant_advanced` en tu directorio de configuración de Home Assistant
2. Reinicia Home Assistant

## ⚙️ Configuración

1. Ve a **Settings** → **Devices & Services** → **Integrations**
2. Haz clic en **+ Add Integration**
3. Busca "Lemonade Assistant Advanced"
4. Ingresa la URL del servidor Lemonade:
   - Ejemplo: `http://10.0.98.68:8000`
5. Configura los parámetros adicionales:
   - Modelo por defecto
   - Temperatura (0.0 - 2.0)
   - Máximo de tokens
   - Streaming

## 🧪 Uso Básico

Una vez configurado, el asistente responderá a comandos como:

- "¿Cuánto es 2 + 2?"
- "Enciende la luz de la sala"
- "¿Qué tiempo hace hoy?"

## 🔧 Funcionalidades Avanzadas

### 🔄 Gestión de Modelos

```yaml
# Cargar modelo específico
service: lemonade_assistant_advanced.load_model
data:
  model_name: "Llama-3.2-1B-Instruct-Hybrid"
```
### 📊 Monitoreo del Servidor

     El sensor muestra el estado actual del servidor y el modelo cargado.

### 🧪 Pruebas

     Asegúrate de que Lemonade Server esté corriendo en http://10.0.98.68:8000
     Verifica que los modelos estén disponibles
     Haz una prueba de conversación desde el asistente de voz

### 📷 Capturas de Pantalla
    (Sensor de estado del servidor Lemonade)
    (Sensor del modelo actualmente cargado)

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Por favor, abre un issue o envía un pull request.
## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT - mira el archivo LICENSE para detalles.
## 🧑‍💻 Desarrollador

    Desarrollado por pchdomotichome

🚀 ¡Haz tu hogar inteligente con modelos locales!