"""Unit tests for AG-UI tool executor module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.agui_agent.tool_executor import (
    ToolCallResult,
    ToolExecutionContext,
    execute_tool,
)


class TestToolExecutionContext:
    """Tests for ToolExecutionContext dataclass."""

    def test_basic_context(self) -> None:
        """Test creating a basic context."""
        ctx = ToolExecutionContext(
            hass=MagicMock(),
            ha_llm_api=MagicMock(),
        )
        assert ctx.hass is not None
        assert ctx.ha_llm_api is not None


class TestExecuteTool:
    """Tests for execute_tool function."""

    @pytest.fixture
    def mock_ha_api(self) -> MagicMock:
        """Create a mock HA LLM API."""
        api = MagicMock()
        api.async_call_tool = AsyncMock(return_value={"success": True})
        return api

    @pytest.fixture
    def base_ctx(self, mock_ha_api: MagicMock) -> ToolExecutionContext:
        """Create a base tool execution context."""
        return ToolExecutionContext(
            hass=MagicMock(),
            ha_llm_api=mock_ha_api,
        )

    @pytest.mark.asyncio
    async def test_execute_ha_tool_success(
        self, base_ctx: ToolExecutionContext
    ) -> None:
        """Test executing an HA intent tool successfully."""
        result = await execute_tool(
            tool_call_id="tc-1",
            tool_name="HassTurnOn",
            tool_args={"domain": ["light"], "name": "Kitchen Light"},
            ctx=base_ctx,
        )

        assert isinstance(result, ToolCallResult)
        assert result.tool_call_id == "tc-1"
        assert result.tool_name == "HassTurnOn"
        assert result.status == "success"
        base_ctx.ha_llm_api.async_call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_returns_json(
        self, base_ctx: ToolExecutionContext
    ) -> None:
        """Test that dict results are JSON serialized."""
        result = await execute_tool(
            tool_call_id="tc-1",
            tool_name="HassTurnOn",
            tool_args={"domain": ["light"]},
            ctx=base_ctx,
        )

        # Result should be JSON string
        assert '"success"' in result.content

    @pytest.mark.asyncio
    async def test_execute_tool_string_result(
        self, base_ctx: ToolExecutionContext
    ) -> None:
        """Test that string results are passed through."""
        base_ctx.ha_llm_api.async_call_tool = AsyncMock(return_value="Light turned on")

        result = await execute_tool(
            tool_call_id="tc-1",
            tool_name="HassTurnOn",
            tool_args={"domain": ["light"]},
            ctx=base_ctx,
        )

        assert result.content == "Light turned on"

    @pytest.mark.asyncio
    async def test_execute_tool_ha_error(self, base_ctx: ToolExecutionContext) -> None:
        """Test handling of HomeAssistantError."""
        base_ctx.ha_llm_api.async_call_tool = AsyncMock(
            side_effect=HomeAssistantError("Device not found")
        )

        result = await execute_tool(
            tool_call_id="tc-1",
            tool_name="HassTurnOn",
            tool_args={"domain": ["light"]},
            ctx=base_ctx,
        )

        assert result.status == "error"
        assert "Error" in result.content
        assert "Device not found" in result.content

    @pytest.mark.asyncio
    async def test_execute_tool_unexpected_error(
        self, base_ctx: ToolExecutionContext
    ) -> None:
        """Test handling of unexpected errors."""
        base_ctx.ha_llm_api.async_call_tool = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        result = await execute_tool(
            tool_call_id="tc-1",
            tool_name="HassTurnOn",
            tool_args={"domain": ["light"]},
            ctx=base_ctx,
        )

        assert result.status == "error"
        assert "Error" in result.content


class TestToolCallResult:
    """Tests for ToolCallResult dataclass."""

    def test_default_status(self) -> None:
        """Test default status is success."""
        result = ToolCallResult(
            tool_call_id="tc-1",
            tool_name="test",
            content="result",
        )
        assert result.status == "success"

    def test_error_status(self) -> None:
        """Test error status."""
        result = ToolCallResult(
            tool_call_id="tc-1",
            tool_name="test",
            content="Error occurred",
            status="error",
        )
        assert result.status == "error"

    def test_all_fields(self) -> None:
        """Test all fields are stored correctly."""
        result = ToolCallResult(
            tool_call_id="tc-123",
            tool_name="MyTool",
            content="Tool output",
            status="success",
        )
        assert result.tool_call_id == "tc-123"
        assert result.tool_name == "MyTool"
        assert result.content == "Tool output"
        assert result.status == "success"
