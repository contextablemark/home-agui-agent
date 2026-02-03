"""Constants for AG-UI Agent."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "agui_agent"

# Configuration keys
CONF_AGUI_ENDPOINT = "agui_endpoint"
CONF_TIMEOUT = "timeout"
CONF_BEARER_TOKEN = "bearer_token"  # noqa: S105

# Defaults
DEFAULT_TIMEOUT = 120
