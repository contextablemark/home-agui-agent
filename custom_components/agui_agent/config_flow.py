"""Config flow for AG-UI Agent."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_AGUI_ENDPOINT,
    CONF_BEARER_TOKEN,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
)


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
                bearer_token = user_input.get(CONF_BEARER_TOKEN)
                try:
                    await self._test_endpoint(endpoint, bearer_token)
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

                data = {
                    CONF_AGUI_ENDPOINT: endpoint,
                    CONF_TIMEOUT: user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                }
                if bearer_token:
                    data[CONF_BEARER_TOKEN] = bearer_token

                return self.async_create_entry(
                    title=f"AG-UI Agent ({endpoint})",
                    data=data,
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
                    vol.Optional(CONF_BEARER_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def _test_endpoint(self, endpoint: str, bearer_token: str | None) -> None:
        """
        Test if the endpoint is reachable.

        This performs a simple HEAD request to verify connectivity.
        The actual AG-UI protocol validation happens at runtime.
        """
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        async with (
            aiohttp.ClientSession() as session,
            session.head(
                endpoint, timeout=aiohttp.ClientTimeout(total=10), headers=headers
            ),
        ):
            pass  # We just want to verify connectivity
