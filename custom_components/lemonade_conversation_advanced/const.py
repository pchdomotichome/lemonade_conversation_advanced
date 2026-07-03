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
CONF_MAX_TOKENS = "max_tokens"
CONF_STREAMING = "streaming"
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
DEFAULT_MAX_TOKENS = 512
DEFAULT_STREAMING = True
DEFAULT_CTX_SIZE = 8192
DEFAULT_GPU_LAYERS = -1
DEFAULT_RECIPE = "llamacpp"
DEFAULT_BACKEND = "llamacpp"

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

# Tool names
TOOL_PULL_MODEL = "lemonade_pull_model"
TOOL_LOAD_MODEL = "lemonade_load_model"
TOOL_UNLOAD_MODEL = "lemonade_unload_model"
TOOL_LIST_MODELS = "lemonade_list_models"
TOOL_SYSTEM_INFO = "lemonade_system_info"
TOOL_GET_STATS = "lemonade_get_stats"
TOOL_EXECUTE_SERVICE = "execute_service"
TOOL_GET_STATE = "get_state"
TOOL_RENDER_TEMPLATE = "render_template"