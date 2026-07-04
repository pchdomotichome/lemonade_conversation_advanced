"""Constants for Lemonade Conversation Advanced."""

from __future__ import annotations

DOMAIN = "lemonade_conversation_advanced"
NAME = "Lemonade Conversation Advanced"
VERSION = "0.1.1"

# Configuration keys
CONF_SERVER_URL = "server_url"
CONF_API_KEY = "api_key"
CONF_DEFAULT_MODEL = "default_model"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_TOP_K = "top_k"
CONF_MAX_TOKENS = "max_tokens"
CONF_STREAMING = "streaming"
CONF_PROMPT = "prompt"
CONF_TIMEOUT = "timeout"
CONF_LLM_APIS = "llm_apis"
CONF_MODELS = "models"
CONF_AGENTS = "agents"

# Model configuration keys
CONF_MODEL_ENABLED = "enabled"
CONF_MODEL_RECIPE = "recipe"
CONF_MODEL_BACKEND = "backend"
CONF_MODEL_CTX_SIZE = "ctx_size"
CONF_MODEL_GPU_LAYERS = "gpu_layers"
CONF_MODEL_PARAMS = "params"

# Agent configuration keys
CONF_AGENT_NAME = "name"
CONF_AGENT_SYSTEM_PROMPT = "system_prompt"
CONF_AGENT_MODEL = "model"
CONF_AGENT_TOOLS = "tools"

# Defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9
DEFAULT_TOP_K = 40
DEFAULT_MAX_TOKENS = 2048
DEFAULT_STREAMING = True
DEFAULT_PROMPT = """Eres un asistente de hogar inteligente llamado Lemonade.
Tu objetivo es ayudar al usuario a controlar su hogar y responder sus preguntas.

Directrices importantes:
- Responde de manera concisa y util
- Si no estas seguro, di que no lo sabes
- Prioriza la seguridad y privacidad del usuario
- Usa un tono amigable y profesional
- Cuando controles dispositivos, confirma las acciones realizadas
"""
DEFAULT_TIMEOUT = 30
DEFAULT_CTX_SIZE = 8192
DEFAULT_GPU_LAYERS = -1
DEFAULT_RECIPE = "llamacpp"
DEFAULT_BACKEND = "llamacpp"

# Limits
MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0
MIN_TOP_P = 0.0
MAX_TOP_P = 1.0
MIN_TOP_K = 1
MAX_TOP_K = 100
MIN_MAX_TOKENS = 1
MAX_MAX_TOKENS = 32768
MIN_TIMEOUT = 5
MAX_TIMEOUT = 120

# Events
EVENT_CONVERSATION_FINISHED = f"{DOMAIN}_conversation_finished"

# Services
SERVICE_LOAD_MODEL = "load_model"
SERVICE_UNLOAD_MODEL = "unload_model"
SERVICE_PULL_MODEL = "pull_model"
SERVICE_LIST_MODELS = "list_models"
SERVICE_GET_SYSTEM_INFO = "get_system_info"
SERVICE_SET_DEFAULT_MODEL = "set_default_model"
SERVICE_QUERY_IMAGE = "query_image"
SERVICE_UPDATE_CONFIG = "update_config"

# LLM API
LLM_API_NAME = "lemonade_conversation_advanced"
LLM_API_DESCRIPTION = "Lemonade Server management and model control tools"

# Lemonade API endpoints
LEMONADE_API_PREFIX = "/api/v1"
LEMONADE_HEALTH_ENDPOINT = f"{LEMONADE_API_PREFIX}/health"
LEMONADE_MODELS_ENDPOINT = f"{LEMONADE_API_PREFIX}/models"
LEMONADE_CHAT_COMPLETIONS_ENDPOINT = f"{LEMONADE_API_PREFIX}/chat/completions"
LEMONADE_LOAD_ENDPOINT = f"{LEMONADE_API_PREFIX}/load"
LEMONADE_UNLOAD_ENDPOINT = f"{LEMONADE_API_PREFIX}/unload"
LEMONADE_PULL_ENDPOINT = f"{LEMONADE_API_PREFIX}/pull"
LEMONADE_SYSTEM_INFO_ENDPOINT = f"{LEMONADE_API_PREFIX}/system-info"
LEMONADE_STATS_ENDPOINT = f"{LEMONADE_API_PREFIX}/stats"
LEMONADE_AI_TASK_ENDPOINT = f"{LEMONADE_API_PREFIX}/ai/task"

# Timeouts
DEFAULT_TIMEOUT = 30
CONNECT_TIMEOUT = 5
STREAM_TIMEOUT = 300

# Supported backends
SUPPORTED_BACKENDS = ["llamacpp", "ryzenai", "vllm", "fastflowlm"]
SUPPORTED_RECIPES = ["llamacpp", "ryzenai", "vllm", "fastflowlm", "custom"]

# Tool names - Lemonade management
TOOL_PULL_MODEL = "lemonade_pull_model"
TOOL_LOAD_MODEL = "lemonade_load_model"
TOOL_UNLOAD_MODEL = "lemonade_unload_model"
TOOL_LIST_MODELS = "lemonade_list_models"
TOOL_SYSTEM_INFO = "lemonade_system_info"
TOOL_GET_STATS = "lemonade_get_stats"

# Tool names - HA bridge
TOOL_EXECUTE_SERVICE = "execute_service"
TOOL_GET_STATE = "get_state"
TOOL_RENDER_TEMPLATE = "render_template"

# HA LLM API
CONF_LLM_HASS_API = "llm_hass_api"
CONF_LLM_HASS_API_VALUE = "conversation"

# Conversation agent features
CONF_MAX_TOOL_ITERATIONS = "max_tool_iterations"
DEFAULT_MAX_TOOL_ITERATIONS = 10

# Streaming
STREAM_CHUNK_SIZE = 1

# Events
EVENT_CONVERSATION_STARTED = f"{DOMAIN}_conversation_started"
EVENT_CONVERSATION_ENDED = f"{DOMAIN}_conversation_ended"
EVENT_CONVERSATION_ERROR = f"{DOMAIN}_conversation_error"