"""The Lemonade Conversation Advanced integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import llm

from .const import DOMAIN, CONF_SERVER_URL, CONF_API_KEY
from .index_manager import IndexManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CONVERSATION, Platform.AI_TASK]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Lemonade Conversation Advanced integration."""
    hass.data.setdefault(DOMAIN, {})

    # Create shared IndexManager
    index_manager = IndexManager(hass)
    await index_manager.start()
    hass.data[DOMAIN]["index_manager"] = index_manager

    # Register LLM tools platform
    llm.async_register_api(hass, LemonadeLLMAPI(hass))

    return True


class LemonadeLLMAPI(llm.API):
    """LLM API for Lemonade Conversation Advanced."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API."""
        super().__init__(hass=hass, id=DOMAIN, name="Lemonade Conversation Advanced")

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        """Return the instance of the API."""
        # Get tools from our platform
        from .llm import async_get_tools

        tools_result = await async_get_tools(self.hass, llm_context, DOMAIN)
        if tools_result is None:
            return llm.APIInstance(
                api=self,
                api_prompt="Lemonade Conversation Advanced tools",
                llm_context=llm_context,
                tools=[],
            )

        return llm.APIInstance(
            api=self,
            api_prompt="Lemonade Conversation Advanced tools",
            llm_context=llm_context,
            tools=tools_result.tools,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lemonade Conversation Advanced from a config entry."""
    _LOGGER.debug("Setting up entry: %s", entry.entry_id)

    server_url = entry.data.get(CONF_SERVER_URL, "")
    api_key = entry.data.get(CONF_API_KEY, "")

    # Validate connection
    import aiohttp
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with session.get(
            f"{server_url}/v1/health",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status >= 400:
                raise ConfigEntryNotReady(f"HTTP {resp.status}")
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(f"Cannot connect to {server_url}: {err}") from err

    # Store entry data
    hass.data[DOMAIN][entry.entry_id] = {
        "server_url": server_url,
        "api_key": api_key,
    }

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Lemonade Conversation Advanced setup complete")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
