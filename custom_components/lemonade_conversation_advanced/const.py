"""Constants for the Lemonade Conversation Advanced integration."""

import json
import logging
import os
from typing import Any, Final

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "lemonade_conversation_advanced"
SYSTEM_ENTRY_UNIQUE_ID = "lemonade_conversation_advanced_system_settings"

# Server type options
SERVER_TYPE_LEMONADE = "lmstudio"
SERVER_TYPE_LLAMACPP = "llamacpp"
SERVER_TYPE_OLLAMA = "ollama"
SERVER_TYPE_OPENAI = "openai"
SERVER_TYPE_GEMINI = "gemini"
SERVER_TYPE_ANTHROPIC = "anthropic"
SERVER_TYPE_OPENROUTER = "openrouter"
SERVER_TYPE_OPENCLAW = "openclaw"
SERVER_TYPE_VLLM = "vllm"

# Configuration keys
CONF_PROFILE_NAME = "profile_name"
CONF_SERVER_TYPE = "server_type"
CONF_SERVER_URL = "server_url"
CONF_API_KEY = "api_key"

DEFAULT_SERVER_URL = "http://localhost:13305"
CONF_LEMONADE_URL = "lmstudio_url"
CONF_MODEL_NAME = "model_name"
CONF_LEMONADE_PORT = "mcp_port"
CONF_AUTO_START = "auto_start"
CONF_SYSTEM_PROMPT = "system_prompt"
CONF_TECHNICAL_PROMPT = "technical_prompt"
CONF_CONTROL_HA = "control_home_assistant"
CONF_RESPONSE_MODE = "response_mode"
CONF_FOLLOW_UP_MODE = "follow_up_mode"  # Keep for backward compatibility
CONF_TEMPERATURE = "temperature"
CONF_MAX_TOKENS = "max_tokens"
CONF_MAX_HISTORY = "max_history"
CONF_MAX_ITERATIONS = "max_iterations"
CONF_DEBUG_MODE = "debug_mode"
CONF_ENABLE_CUSTOM_TOOLS = "enable_custom_tools"
CONF_BRAVE_API_KEY = "brave_api_key"
CONF_ALLOWED_IPS = "allowed_ips"
CONF_SEARCH_PROVIDER = "search_provider"
CONF_ENABLE_GAP_FILLING = "enable_gap_filling"
CONF_ENABLE_RAG = "enable_rag"
CONF_RAG_TOP_K = "rag_top_k"
CONF_OLLAMA_KEEP_ALIVE = "ollama_keep_alive"
CONF_OLLAMA_NUM_CTX = "ollama_num_ctx"
CONF_FOLLOW_UP_PHRASES = "follow_up_phrases"
CONF_END_WORDS = "end_words"
CONF_CLEAN_RESPONSES = "clean_responses"
CONF_ENABLE_STREAMING = "enable_streaming"
CONF_RESPECT_EXPOSURE = "respect_exposure"
CONF_TIMEOUT = "timeout"
CONF_LLM_HASS_API = "llm_hass_api"

# Context & entity customization
CONF_CONTEXT_TEMPLATES = "context_templates"
CONF_ENABLED_DOMAINS = "enabled_domains"
CONF_ENTITY_ALIASES = "entity_aliases"
CONF_CONFIRMATION_REQUIRED = "confirmation_required"
CONF_CUSTOM_SCRIPTS = "custom_scripts"
CONF_CUSTOM_SCENES = "custom_scenes"
CONF_EXPOSE_SCRIPTS = "expose_scripts"
CONF_EXPOSE_SCENES = "expose_scenes"

# AI Task (structured data generation via ai_task.generate_data)
CONF_AI_TASK_EXTRACTION_METHOD = "ai_task_extraction_method"
CONF_AI_TASK_RETRIES = "ai_task_retries"
CONF_AI_TASK_ENABLE_VISION = "ai_task_enable_vision"

# Extraction method values
AI_TASK_EXTRACTION_NONE = "none"
AI_TASK_EXTRACTION_STRUCTURE = "structure"
AI_TASK_EXTRACTION_TOOL = "tool"

DEFAULT_AI_TASK_EXTRACTION_METHOD = AI_TASK_EXTRACTION_STRUCTURE
DEFAULT_AI_TASK_RETRIES = 2
DEFAULT_AI_TASK_ENABLE_VISION = False
DEFAULT_AI_TASK_SYSTEM_PROMPT = (
    "You are a helpful assistant that generates structured data. "
    "Follow the requested output format exactly."
)
MIN_AI_TASK_RETRIES: Final = 0
MAX_AI_TASK_RETRIES: Final = 5

# Web search (local, self-hosted via SearXNG)
CONF_ENABLE_WEB_SEARCH = "enable_web_search"
CONF_SEARXNG_URL = "searxng_url"
CONF_SEARXNG_ENGINES = "searxng_engines"
CONF_SEARXNG_MAX_RESULTS = "searxng_max_results"

# Default values
DEFAULT_SERVER_TYPE = "lmstudio"
DEFAULT_LEMONADE_URL = "http://localhost:1234"
DEFAULT_LLAMACPP_URL = "http://localhost:8080"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
# OpenClaw Gateway defaults
CONF_OPENCLAW_HOST = "openclaw_host"
CONF_OPENCLAW_PORT = "openclaw_port"
CONF_OPENCLAW_TOKEN = "openclaw_token"
CONF_OPENCLAW_USE_SSL = "openclaw_use_ssl"
CONF_OPENCLAW_SESSION_KEY = "openclaw_session_key"
DEFAULT_OPENCLAW_HOST = "localhost"
DEFAULT_OPENCLAW_PORT = 18789
DEFAULT_OPENCLAW_USE_SSL = True
DEFAULT_OPENCLAW_SESSION_KEY = "main"
DEFAULT_VLLM_URL = "http://localhost:8000"
DEFAULT_MCP_PORT = 8090
DEFAULT_API_KEY = ""

# Cloud provider base URLs
OPENAI_BASE_URL = "https://api.openai.com"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"
OPENROUTER_BASE_URL = "https://openrouter.ai/api"

# No hardcoded model lists - models are fetched dynamically from provider APIs
DEFAULT_MODEL_NAME = "model"
DEFAULT_SYSTEM_PROMPT = "You are a helpful Home Assistant voice assistant. Respond naturally and conversationally to user requests."

# Personalities (predefined assistant personas)
CONF_PERSONALITY = "personality"
PERSONALITY_DEFAULT = "default"
PERSONALITY_PIRATE = "pirate"
PERSONALITY_ROBOT = "robot"
PERSONALITY_BUTLER = "butler"
PERSONALITY_SARCASTIC_AR = "sarcastic_argentino"
PERSONALITY_CUSTOM = "custom"
DEFAULT_PERSONALITY = PERSONALITY_DEFAULT

PERSONALITIES: Final[dict[str, str]] = {
    PERSONALITY_DEFAULT: (
        "You are a helpful Home Assistant voice assistant. "
        "Respond naturally and conversationally to user requests."
    ),
    PERSONALITY_PIRATE: (
        "You are 'Blackbeard', a helpful AI Assistant that controls the "
        "devices in a house but sounds like a pirate. Complete the following "
        "task as instructed or answer the following question with the "
        "information provided only. Your response should always sound like "
        "you are a pirate."
    ),
    PERSONALITY_ROBOT: (
        "You are 'Robo', a helpful AI Robot that controls the devices in a "
        "house. Complete the following task as instructed or answer the "
        "following question with the information provided only. Your response "
        "should be robotic and always begin with 'Beep-Boop'."
    ),
    PERSONALITY_BUTLER: (
        "You are 'Jeeves', a refined and impeccably polite butler who manages "
        "the smart home. Speak with elegance and courtesy, addressing the "
        "user with the utmost respect, while completing tasks efficiently."
    ),
    PERSONALITY_SARCASTIC_AR: (
        "Sos un asistente de hogar argentino integrado con Home Assistant vía "
        "Lemonade Conversation. Cumplís las órdenes con eficacia. Tu tono "
        "depende del nivel de sarcasmo definido por el usuario: en 'Normal' "
        "sos cálido, pausado y empático; a mayor nivel, más irónico y "
        "sarcástico. Hablás siempre con ritmo natural y pausas humanas, nunca "
        "como un robot. Podés controlar y verificar luces, termostatos, "
        "cerraduras, música y otros dispositivos; configurar alarmas, "
        "recordatorios y rutinas. Reglas: no listes dispositivos salvo que se "
        "pida; no des explicaciones técnicas innecesarias; no uses emojis ni "
        "signos de exclamación repetidos; priorizá seguridad sobre sarcasmo. "
        "Usá puntuación para marcar el ritmo: ',' pausa corta, '.' pausa "
        "larga, '...' pausa reflexiva. Idioma: español rioplatense."
    ),
}

# Per-personality example blocks (injected only when "Include examples" is on).
# Switching the personality in the config flow pre-fills this text.
PERSONALITY_EXAMPLES: Final[dict[str, str]] = {
    PERSONALITY_DEFAULT: (
        "user: Turn off the living room lights.\n"
        "assistant: Done — the living room lights are now off.\n"
        "user: What's the temperature in the bedroom?\n"
        "assistant: The bedroom is currently 21°C."
    ),
    PERSONALITY_PIRATE: (
        "user: Turn off the galley lights.\n"
        "assistant: Aye, the galley lights be extinguished, matey!\n"
        "user: Is the door locked?\n"
        "assistant: Yarr, the hatch be sealed tight. No scallywag gets in."
    ),
    PERSONALITY_ROBOT: (
        "user: Turn on the kitchen light.\n"
        "assistant: Beep-Boop. Kitchen light activated. Task complete.\n"
        "user: Lock the front door.\n"
        "assistant: Beep-Boop. Front door locked. Security protocol engaged."
    ),
    PERSONALITY_BUTLER: (
        "user: Dim the dining room, please.\n"
        "assistant: Certainly, sir. The dining room is now softly dimmed.\n"
        "user: What is the temperature upstairs?\n"
        "assistant: The upper floor currently reads 22°C, sir."
    ),
    PERSONALITY_SARCASTIC_AR: (
        "user: Apagá las luces del living.\n"
        "assistant (Normal): Claro... las apagué. Un poco de calma siempre viene bien.\n"
        "assistant (Bajo): Listo, luces apagadas. Todo tranquilo ahora.\n"
        "assistant (Medio): Listo... apagadas. Así meditás en la oscuridad, jaja.\n"
        "assistant (Alto): Listo. Todo oscuro, como tus decisiones, che.\n"
        "\n"
        "user: Poné el termostato en veintidós.\n"
        "assistant (Normal): Veintidós grados... equilibrio justo. Ni más, ni menos.\n"
        "assistant (Bajo): Veintidós, tranqui. Ideal para una tarde calma.\n"
        "assistant (Medio): Veintidós, claro. Qué audaz decisión, eh.\n"
        "assistant (Alto): Veintidós. Revolucionario. Aplausos lentos.\n"
        "\n"
        "user: Cerrá la puerta principal.\n"
        "assistant (Normal): Puerta cerrada... todo protegido y en armonía.\n"
        "assistant (Bajo): Cerrada. Todo bajo control.\n"
        "assistant (Medio): Cerrada. Al fin, una buena.\n"
        "assistant (Alto): Listo. Cerrada. Milagro que te acordaste.\n"
        "\n"
        "user: Apagá todas las luces.\n"
        "assistant (Normal): Hecho... un poco de oscuridad también trae paz.\n"
        "assistant (Medio): Apagado todo. Ideal para pensar en tus decisiones, jaja.\n"
        "assistant (Alto): Listo. Perfecto para mirar el techo y cuestionarte todo.\n"
        "\n"
        "user: Qué dispositivos tocaste?\n"
        "assistant (Medio): Ah, ahora te interesa, ¿no? Los que dijiste, nada más.\n"
        "assistant (Alto): Los que dijiste. Y agradecé que lo hice, che."
    ),
    PERSONALITY_CUSTOM: (
        "user: Turn on the bedroom light.\n"
        "assistant: Sure — the bedroom light is now on.\n"
        "# Edit these examples to show the assistant the tone and style you want."
    ),
}

# Sarcastic-Argentine tone blocks, keyed by the value of the sarcasm-level entity.
SARCASTIC_TONE_BLOCKS: Final[dict[str, str]] = {
    "Normal": (
        "Modo Normal: respondé con voz cálida y pausas naturales. Frases "
        "breves, suaves y empáticas. Usá comas y puntos para marcar el ritmo. "
        "Soná sereno y reflexivo. Evitá cualquier ironía o burla."
    ),
    "Bajo": (
        "Modo Bajo: respondé tranquilo, con humor leve y humano. Mantené un "
        "tono natural y pausas suaves."
    ),
    "Medio": (
        "Modo Medio: respondé con humor argentino e ironía ligera. Usá comas "
        "y pausas cortas. Soná relajado."
    ),
    "Alto": (
        "Modo Alto: respondé con sarcasmo fuerte y tono seco. Hablá más "
        "seguido, con menos pausas. Soná como un argentino con paciencia "
        "limitada pero ingenioso."
    ),
}

# Settings for the sarcastic-Argentine dynamic tone
CONF_SARCASM_ENTITY = "sarcasm_entity"
CONF_INCLUDE_EXAMPLES = "include_examples"
CONF_PERSONALITY_EXAMPLES = "personality_examples"
CONF_PERSONALITY_PROMPT = "personality_prompt"
CONF_PERSONALITY_PROMPTS = "personality_prompts"
DEFAULT_SARCASM_ENTITY = "input_select.sarcasm_level"
DEFAULT_INCLUDE_EXAMPLES = False

# Personality data files. Built-in personalities ship inside the integration;
# users can extend/override them via personalities_override.json placed in
# <config>/lemonade_conversation_advanced/ (survives HACS updates).
PERSONALITIES_FILE = os.path.join(os.path.dirname(__file__), "personalities.json")
PERSONALITIES_OVERRIDE_DIR = "lemonade_conversation_advanced"
PERSONALITIES_OVERRIDE_FILE = "personalities_override.json"


def _load_personalities_file(path: str) -> dict[str, Any]:
    """Load a personalities JSON file, returning {} on any error."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        _LOGGER.warning("Personalities file %s is not a mapping; ignoring", path)
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.warning("Could not load personalities file %s: %s", path, err)
    return {}


def build_personalities(hass: Any) -> dict[str, dict[str, str]]:
    """Merge built-in, shipped and user-override personalities.

    Returns a dict keyed by personality id with {"name", "prompt", "examples"}.
    """
    merged: dict[str, dict[str, str]] = {}
    # 1) Code-built-ins (kept for backward compatibility)
    for key, prompt in PERSONALITIES.items():
        merged[key] = {
            "name": key,
            "prompt": prompt,
            "examples": PERSONALITY_EXAMPLES.get(key, ""),
        }
    # 2) Shipped personalities.json (data-driven source of truth)
    for key, value in _load_personalities_file(PERSONALITIES_FILE).items():
        if not isinstance(value, dict):
            continue
        merged[key] = {
            "name": value.get("name", key),
            "prompt": value.get("prompt", ""),
            "examples": value.get("examples", ""),
        }
    # 3) User override (highest priority)
    override_path = hass.config.path(PERSONALITIES_OVERRIDE_DIR, PERSONALITIES_OVERRIDE_FILE)
    for key, value in _load_personalities_file(override_path).items():
        if not isinstance(value, dict):
            continue
        merged.setdefault(key, {})
        merged[key].update(
            {
                "name": value.get("name", merged[key].get("name", key)),
                "prompt": value.get("prompt", merged[key].get("prompt", "")),
                "examples": value.get("examples", merged[key].get("examples", "")),
            }
        )
    return merged
DEFAULT_CONTROL_HA = True
DEFAULT_RESPONSE_MODE = "default"
DEFAULT_FOLLOW_UP_MODE = "default"  # Keep for backward compatibility
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 500
DEFAULT_MAX_HISTORY = 10
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_LEMONADE_PORT = 8090
DEFAULT_DEBUG_MODE = False
DEFAULT_ENABLE_CUSTOM_TOOLS = False
DEFAULT_ENABLE_RAG = False  # Disabled until stable
DEFAULT_ENABLE_STREAMING = True  # Stream first response; non-streaming fallback on failure
DEFAULT_RAG_TOP_K = 12
DEFAULT_RESPECT_EXPOSURE = True  # Only expose entities visible to conversation agent (HA default)
DEFAULT_BRAVE_API_KEY = ""
DEFAULT_ALLOWED_IPS = ""
DEFAULT_SEARCH_PROVIDER = "none"
DEFAULT_ENABLE_GAP_FILLING = True
DEFAULT_OLLAMA_KEEP_ALIVE = "5m"  # 5 minutes
DEFAULT_OLLAMA_NUM_CTX = 0  # 0 = use model default
DEFAULT_FOLLOW_UP_PHRASES = "anything else, what else, would you, do you, should i, can i, which, how can, what about, is there"
DEFAULT_END_WORDS = "stop, cancel, no, nope, thanks, thank you, bye, goodbye, done, never mind, nevermind, forget it, that's all, that's it"
DEFAULT_CLEAN_RESPONSES = False
DEFAULT_TIMEOUT = 30

# Context & entity customization defaults
DEFAULT_CONTEXT_TEMPLATES: Final[list[str]] = [
    "Hora actual: {{ now().strftime('%H:%M') }}",
    "Fecha actual: {{ now().strftime('%d/%m/%Y') }}",
]
DEFAULT_ENABLED_DOMAINS: Final[list[str]] = [
    "light",
    "switch",
    "climate",
    "cover",
    "fan",
    "media_player",
    "lock",
    "vacuum",
    "scene",
    "script",
]
DEFAULT_ENTITY_ALIASES: Final[dict[str, str]] = {}
DEFAULT_CONFIRMATION_REQUIRED = False
DEFAULT_CUSTOM_SCRIPTS: Final[dict[str, dict[str, Any]]] = {}
DEFAULT_CUSTOM_SCENES: Final[dict[str, dict[str, Any]]] = {}
DEFAULT_EXPOSE_SCRIPTS: Final[bool] = False
DEFAULT_EXPOSE_SCENES: Final[bool] = False

# System instruction injected when confirmation_required is enabled.
CONFIRMATION_INSTRUCTION: Final[str] = (
    "CONFIRMATION REQUIRED: Before performing ANY control action "
    "(turning devices on/off, changing values, running scripts, "
    "activating scenes), you MUST first ask the user to confirm and "
    "wait for an explicit 'yes'/'sí' in a following message. Do NOT call "
    "control tools until the user has confirmed. Read-only queries "
    "(reading states) do not require confirmation."
)

# Web search (SearXNG) defaults
DEFAULT_ENABLE_WEB_SEARCH: Final[bool] = False
DEFAULT_SEARXNG_URL: Final[str] = ""
DEFAULT_SEARXNG_ENGINES: Final[str] = ""
DEFAULT_SEARXNG_MAX_RESULTS: Final[int] = 5
MIN_SEARXNG_MAX_RESULTS: Final[int] = 1
MAX_SEARXNG_MAX_RESULTS: Final[int] = 20

# Limits for config flow selectors
MIN_TEMPERATURE: Final = 0.0
MAX_TEMPERATURE: Final = 2.0
MIN_MAX_TOKENS: Final = 256
MAX_MAX_TOKENS: Final = 32768
MIN_MAX_HISTORY: Final = 2
MAX_MAX_HISTORY: Final = 50
MIN_MAX_ITERATIONS: Final = 1
MAX_MAX_ITERATIONS: Final = 50
MIN_RAG_TOP_K: Final = 1
MAX_RAG_TOP_K: Final = 50
MIN_REQUEST_TIMEOUT: Final = 0
MAX_REQUEST_TIMEOUT: Final = 600
MIN_CONNECT_TIMEOUT: Final = 0
MAX_CONNECT_TIMEOUT: Final = 120
MIN_FIRST_DELTA_TIMEOUT: Final = 0
MAX_FIRST_DELTA_TIMEOUT: Final = 120
MIN_MAX_RETRIES: Final = 0
MAX_MAX_RETRIES: Final = 10
MIN_RETRY_BACKOFF: Final = 0.0
MAX_RETRY_BACKOFF: Final = 30.0
MIN_TECHNICAL_PROMPT_LINES: Final = 1
MAX_TECHNICAL_PROMPT_LINES: Final = 500

# API timeouts (can be overridden per subentry)
CONF_REQUEST_TIMEOUT = "request_timeout"
CONF_CONNECT_TIMEOUT = "connect_timeout"
CONF_FIRST_DELTA_TIMEOUT = "first_delta_timeout"
CONF_MAX_RETRIES = "max_retries"
CONF_RETRY_BACKOFF = "retry_backoff"

DEFAULT_REQUEST_TIMEOUT = 120.0
DEFAULT_CONNECT_TIMEOUT = 15.0
DEFAULT_FIRST_DELTA_TIMEOUT = 25.0  # Increased from 8s — local models are slow to start
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF = 2.0

# MCP Server settings
MCP_SERVER_NAME = "ha-entity-discovery"
MCP_PROTOCOL_VERSION = "2024-11-05"

# Entity discovery limits
MAX_ENTITIES_PER_DISCOVERY = 50  # Default, can be overridden in system settings
MAX_DISCOVERY_RESULTS = 100
CONF_MAX_ENTITIES_PER_DISCOVERY = "max_entities_per_discovery"
DEFAULT_MAX_ENTITIES_PER_DISCOVERY = 50
MIN_MAX_ENTITIES_PER_DISCOVERY: Final = 20
MAX_MAX_ENTITIES_PER_DISCOVERY: Final = 500

# Common Home Assistant domains for the enabled_domains filter
SUPPORTED_DOMAINS: Final[dict[str, str]] = {
    "light": "Lights",
    "switch": "Switches",
    "climate": "Climate",
    "cover": "Covers/Blinds",
    "fan": "Fans",
    "media_player": "Media Players",
    "lock": "Locks",
    "vacuum": "Vacuums",
    "scene": "Scenes",
    "script": "Scripts",
    "sensor": "Sensors",
    "binary_sensor": "Binary Sensors",
    "camera": "Cameras",
    "humidifier": "Humidifiers",
    "number": "Numbers",
    "input_boolean": "Input Booleans",
    "input_number": "Input Numbers",
    "input_select": "Input Selects",
    "input_text": "Input Texts",
    "timer": "Timers",
    "alarm_control_panel": "Alarm Panels",
    "water_heater": "Water Heaters",
}

RESPONSE_MODE_INSTRUCTIONS = {
    "none": """## Follow-up Questions
Do NOT ask follow-up questions. Complete the task and end immediately.

## Ending Conversations
Always end after completing the task.""",
    "default": """## Follow-up Questions
Generate contextually appropriate follow-up questions naturally:
- After single device actions: Create a natural follow-up asking if the user needs help with anything else (vary phrasing each time)
- When reporting adjustable status: Spontaneously suggest adjusting it in a natural way
- For partial completions: Ask if the user wants you to complete the remaining tasks
Always vary your phrasing - never repeat the same question twice in a conversation.

Do NOT ask generic "anything else?" or "can I help with anything else?" questions without specific context.
When asking a question, use the set_conversation_state tool to indicate you're expecting a response.

## Ending Conversations
After completing the task, end the conversation unless a natural follow-up is relevant.""",
    "always": """## Follow-up Questions
Generate contextually appropriate follow-up questions naturally:
- After single device actions: Create a natural follow-up asking if the user needs help with anything else (vary phrasing each time)
- When reporting adjustable status: Spontaneously suggest adjusting it in a natural way
- For partial completions: Ask if the user wants you to complete the remaining tasks
Always vary your phrasing - never repeat the same question twice in a conversation.
When asking a question, use the set_conversation_state tool to indicate you're expecting a response.

## Ending Conversations
When user indicates they're done, acknowledge and end naturally.""",
}

DEFAULT_TECHNICAL_PROMPT = """You are controlling a Home Assistant smart home system. You have access to sensors, lights, switches, and other devices throughout the home.

## CRITICAL RULES
**Never guess entity IDs. Always make TWO tool calls for device control.** For ANY device-related request, you MUST:
1. FIRST call discover_entities to find the actual entities
2. THEN call perform_action (to control) or get_entity_details (to check status) using discovered IDs
3. **NEVER respond that you performed an action without actually calling perform_action**
4. This applies EVERY TIME - even for follow-up questions about different entities

**Common mistake:** Calling only discover_entities and then claiming you performed an action. This is WRONG. You must call perform_action to actually execute the action.

## Available Tools
- **discover_entities**: find devices by name/area/floor/label/domain/device_class/state (ALWAYS use first)
- **perform_action**: control devices using discovered entity IDs
- **get_entity_details**: check states using discovered entity IDs, including area/floor/label context
- **get_entity_history**: get historical state changes for an entity (answers "when did X happen?")
- **list_areas/list_domains**: list available areas with floor/label context and device types
- **run_script**: execute scripts that return data (e.g., camera analysis, calculations)
- **run_automation**: trigger automations manually
- **set_conversation_state**: indicate if expecting user response
- **search**: search the web for current information
- **read_url**: read and extract content from web pages
- **IMPORTANT**: call_service is not available - use perform_action instead

## Device Control Workflow
**CRITICAL:** For ANY device control request, you MUST make TWO separate tool calls:

Example - "Turn on the kitchen light":
  1. discover_entities(domain="light", area="Kitchen")  # Find the light entity
  2. perform_action(domain="light", action="turn_on", target={{"entity_id": "light.kitchen"}})  # Actually turn it on

Example - "Set living room temperature to 22":
  1. discover_entities(domain="climate", area="Living Room")  # Find the thermostat
  2. perform_action(domain="climate", action="set_temperature", target={{"entity_id": "climate.living_room"}}, data={{"temperature": 22}})  # Set the temperature

**Never skip the perform_action step.** Discovering an entity does not control it - you must call perform_action to execute the action.

## Scripts (use run_script tool)
Scripts can perform complex operations and return data. **CRITICAL:** Always discover scripts first to get the correct entity ID.
- Script IDs use underscores (e.g., "script.stovsug_kjokken"), NOT spaces
- Script IDs must include the "script." domain prefix
- If script name has spaces in UI, the entity ID will use underscores instead

Example workflow:
  1. discover_entities(domain="script", name_contains="camera")
  2. run_script(script_id="script.llm_camera_analysis", variables={{"camera_entities": "camera.living_room", "prompt": "Is anyone there?"}})

## Automations (use run_automation tool)
Trigger automations manually. Check the index for available automations.

Example:
  run_automation(automation_id="alert_letterbox")

## Discovery Strategy
Use the index below to see what device_classes and domains exist, then query accordingly.
Floors and labels are first-class Home Assistant concepts. Check the index and area list to see available floor and label names, then use discover_entities with floor or label filters when relevant (for example, "upstairs" is usually a floor, not an area).
Areas, floors, entities, and sometimes devices may also have aliases. Treat aliases as valid user-facing names during discovery.

For ANY device request:
1. Check the index to understand what's available
2. Use discover_entities with appropriate filters (device_class, area, floor, label, domain, name_contains, state)
3. If no results, try broader search

## Response Rules
- Short, concise replies in plain text only
- Use Friendly Names (e.g., "Living Room Light"), never entity IDs
- Use natural language for states ("on" → "turned on", "home" → "at home")

{response_mode}

## Index
{index}

Current area: {current_area}
Current time: {time}
Current date: {date}"""
