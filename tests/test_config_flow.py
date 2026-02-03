"""Unit tests for AG-UI Agent config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.agui_agent.const import (
    CONF_AGUI_ENDPOINT,
    CONF_BEARER_TOKEN,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def mock_conversation_setup():
    """Mock the conversation component setup to avoid dependency issues."""
    with patch(
        "homeassistant.components.conversation.async_setup",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_setup_entry():
    """Mock the async_setup_entry function."""
    with patch(
        "custom_components.agui_agent.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


async def test_form_shows_all_fields(
    hass: HomeAssistant,
    enable_custom_integrations,
) -> None:
    """Test that the config form shows all expected fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Check the schema includes all expected fields
    schema = result["data_schema"].schema
    field_names = [str(key) for key in schema]
    assert CONF_AGUI_ENDPOINT in field_names
    assert CONF_TIMEOUT in field_names
    assert CONF_BEARER_TOKEN in field_names


async def test_create_entry_without_bearer_token(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_setup_entry,
) -> None:
    """Test creating a config entry without bearer token."""
    with patch(
        "custom_components.agui_agent.config_flow.AGUIAgentFlowHandler._test_endpoint",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_AGUI_ENDPOINT: "http://localhost:8005/agent",
                CONF_TIMEOUT: 120,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "AG-UI Agent (http://localhost:8005/agent)"
    assert result["data"][CONF_AGUI_ENDPOINT] == "http://localhost:8005/agent"
    assert result["data"][CONF_TIMEOUT] == 120
    assert CONF_BEARER_TOKEN not in result["data"]


async def test_create_entry_with_bearer_token(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_setup_entry,
) -> None:
    """Test creating a config entry with bearer token."""
    with patch(
        "custom_components.agui_agent.config_flow.AGUIAgentFlowHandler._test_endpoint",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_AGUI_ENDPOINT: "http://localhost:8005/agent",
                CONF_TIMEOUT: 120,
                CONF_BEARER_TOKEN: "my-secret-token",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BEARER_TOKEN] == "my-secret-token"


async def test_bearer_token_passed_to_endpoint_test(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_setup_entry,
) -> None:
    """Test that bearer token is passed to the endpoint test."""
    with patch(
        "custom_components.agui_agent.config_flow.AGUIAgentFlowHandler._test_endpoint",
        new_callable=AsyncMock,
    ) as mock_test:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_AGUI_ENDPOINT: "http://localhost:8005/agent",
                CONF_BEARER_TOKEN: "test-token",
            },
        )

        mock_test.assert_called_once_with("http://localhost:8005/agent", "test-token")


async def test_endpoint_test_without_bearer_token(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_setup_entry,
) -> None:
    """Test endpoint test is called with None when no bearer token."""
    with patch(
        "custom_components.agui_agent.config_flow.AGUIAgentFlowHandler._test_endpoint",
        new_callable=AsyncMock,
    ) as mock_test:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_AGUI_ENDPOINT: "http://localhost:8005/agent",
            },
        )

        mock_test.assert_called_once_with("http://localhost:8005/agent", None)


async def test_default_timeout_used(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_setup_entry,
) -> None:
    """Test that default timeout is used when not specified."""
    with patch(
        "custom_components.agui_agent.config_flow.AGUIAgentFlowHandler._test_endpoint",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_AGUI_ENDPOINT: "http://localhost:8005/agent",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TIMEOUT] == DEFAULT_TIMEOUT


async def test_invalid_url_shows_error(
    hass: HomeAssistant,
    enable_custom_integrations,
) -> None:
    """Test that invalid URL shows an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_AGUI_ENDPOINT: "not-a-url",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


async def test_endpoint_strips_trailing_slash(
    hass: HomeAssistant,
    enable_custom_integrations,
    mock_setup_entry,
) -> None:
    """Test that trailing slash is stripped from endpoint."""
    with patch(
        "custom_components.agui_agent.config_flow.AGUIAgentFlowHandler._test_endpoint",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_AGUI_ENDPOINT: "http://localhost:8005/agent/",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AGUI_ENDPOINT] == "http://localhost:8005/agent"
