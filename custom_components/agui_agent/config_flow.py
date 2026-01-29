"""Config flow for AG-UI Agent."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import CONF_AGUI_ENDPOINT, CONF_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN, LOGGER


class AGUIAgentFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for AG-UI Agent."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            endpoint = user_input[CONF_AGUI_ENDPOINT].rstrip("/")

            # Validate endpoint URL format
            if not endpoint.startswith(("http://", "https://")):
                errors["base"] = "invalid_url"
            else:
                # Optional: Test endpoint connectivity
                try:
                    await self._test_endpoint(endpoint)
                except aiohttp.ClientError as ex:
                    LOGGER.warning("Failed to connect to endpoint: %s", ex)
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Unexpected error testing endpoint")
                    errors["base"] = "unknown"

            if not errors:
                # Use endpoint as unique ID to prevent duplicates
                await self.async_set_unique_id(endpoint)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"AG-UI Agent ({endpoint})",
                    data={
                        CONF_AGUI_ENDPOINT: endpoint,
                        CONF_TIMEOUT: user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AGUI_ENDPOINT): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.URL,
                        ),
                    ),
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=DEFAULT_TIMEOUT,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=600,
                            step=10,
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                },
            ),
            description_placeholders={
                "ag_ui_url": "https://github.com/ag-ui-protocol/ag-ui",
            },
            errors=errors,
        )

    async def _test_endpoint(self, endpoint: str) -> None:
        """
        Test if the endpoint is reachable.

        This performs a simple HEAD request to verify connectivity.
        The actual AG-UI protocol validation happens at runtime.
        """
        async with (
            aiohttp.ClientSession() as session,
            session.head(endpoint, timeout=aiohttp.ClientTimeout(total=10)),
        ):
            pass  # We just want to verify connectivity
