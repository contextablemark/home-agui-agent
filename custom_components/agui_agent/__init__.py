"""
AG-UI Agent integration for Home Assistant.

This integration connects Home Assistant to remote AG-UI compatible agent backends,
enabling framework-agnostic AI agent communication for smart home control.

For more details about AG-UI protocol, please refer to:
https://github.com/ag-ui-protocol/ag-ui
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import (
    CONF_AGUI_ENDPOINT,
    CONF_BEARER_TOKEN,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
)

__all__ = ["DOMAIN", "AGUIAgentConfigEntry", "AGUIAgentData"]

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.CONVERSATION]


@dataclass
class AGUIAgentData:
    """Runtime data for AG-UI Agent integration."""

    endpoint: str
    timeout: int
    bearer_token: str | None


type AGUIAgentConfigEntry = ConfigEntry[AGUIAgentData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AGUIAgentConfigEntry,
) -> bool:
    """Set up AG-UI Agent from a config entry."""
    LOGGER.info(
        "Setting up AG-UI Agent with endpoint: %s", entry.data[CONF_AGUI_ENDPOINT]
    )

    entry.runtime_data = AGUIAgentData(
        endpoint=entry.data[CONF_AGUI_ENDPOINT],
        timeout=entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        bearer_token=entry.data.get(CONF_BEARER_TOKEN),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AGUIAgentConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: AGUIAgentConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
