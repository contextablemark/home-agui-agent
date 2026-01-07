"""Unit tests for AG-UI tool translator module."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from ag_ui.core import Tool

from custom_components.agui_agent.tool_translator import (
    translate_tool,
    translate_tools,
)


class MockHATool:
    """Mock Home Assistant LLM Tool for testing."""

    def __init__(
        self,
        name: str,
        description: str | None = None,
        parameters: vol.Schema | None = None,
    ) -> None:
        """Initialize mock tool."""
        self.name = name
        self.description = description
        self.parameters = parameters or vol.Schema({})


class TestTranslateTool:
    """Tests for translate_tool function."""

    def test_simple_tool(self) -> None:
        """Test translating a simple tool with no parameters."""
        ha_tool = MockHATool(
            name="HassTurnOn",
            description="Turn on a device",
            parameters=vol.Schema({}),
        )

        result = translate_tool(ha_tool)

        assert isinstance(result, Tool)
        assert result.name == "HassTurnOn"
        assert result.description == "Turn on a device"
        assert result.parameters is not None

    def test_tool_with_parameters(self) -> None:
        """Test translating a tool with parameters."""
        ha_tool = MockHATool(
            name="HassTurnOn",
            description="Turn on a device",
            parameters=vol.Schema(
                {
                    vol.Required("domain"): str,
                    vol.Optional("name"): str,
                }
            ),
        )

        result = translate_tool(ha_tool)

        assert isinstance(result, Tool)
        assert result.name == "HassTurnOn"
        # Parameters should be converted to JSON Schema format
        assert "properties" in result.parameters or "type" in result.parameters

    def test_tool_without_description(self) -> None:
        """Test translating a tool without description."""
        ha_tool = MockHATool(
            name="TestTool",
            description=None,
            parameters=vol.Schema({}),
        )

        result = translate_tool(ha_tool)

        assert result.name == "TestTool"
        assert result.description == ""

    def test_tool_with_complex_parameters(self) -> None:
        """Test translating a tool with complex parameters."""
        ha_tool = MockHATool(
            name="ComplexTool",
            description="A complex tool",
            parameters=vol.Schema(
                {
                    vol.Required("domain"): vol.All(str, vol.Length(min=1)),
                    vol.Optional("entities", default=[]): [str],
                    vol.Optional("brightness"): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=255)
                    ),
                }
            ),
        )

        result = translate_tool(ha_tool)

        assert isinstance(result, Tool)
        assert result.name == "ComplexTool"

    def test_tool_with_custom_serializer(self) -> None:
        """Test translating a tool with custom serializer."""

        def custom_serializer(value: Any) -> Any:
            """Custom serializer for special types."""
            if hasattr(value, "__name__"):
                return {"type": "custom", "name": value.__name__}
            return value

        ha_tool = MockHATool(
            name="CustomTool",
            description="Tool with custom types",
            parameters=vol.Schema({}),
        )

        result = translate_tool(ha_tool, custom_serializer=custom_serializer)

        assert isinstance(result, Tool)
        assert result.name == "CustomTool"


class TestTranslateTools:
    """Tests for translate_tools function."""

    def test_empty_list(self) -> None:
        """Test translating empty tool list."""
        result = translate_tools([])
        assert result == []

    def test_single_tool(self) -> None:
        """Test translating single tool."""
        ha_tools = [
            MockHATool(name="Tool1", description="First tool"),
        ]

        result = translate_tools(ha_tools)

        assert len(result) == 1
        assert result[0].name == "Tool1"

    def test_multiple_tools(self) -> None:
        """Test translating multiple tools."""
        ha_tools = [
            MockHATool(name="Tool1", description="First tool"),
            MockHATool(name="Tool2", description="Second tool"),
            MockHATool(name="Tool3", description="Third tool"),
        ]

        result = translate_tools(ha_tools)

        assert len(result) == 3
        assert result[0].name == "Tool1"
        assert result[1].name == "Tool2"
        assert result[2].name == "Tool3"

    def test_with_custom_serializer(self) -> None:
        """Test translating tools with custom serializer."""

        def custom_serializer(value: Any) -> Any:
            return value

        ha_tools = [
            MockHATool(name="Tool1"),
            MockHATool(name="Tool2"),
        ]

        result = translate_tools(ha_tools, custom_serializer=custom_serializer)

        assert len(result) == 2

    def test_preserves_order(self) -> None:
        """Test that tool order is preserved."""
        ha_tools = [
            MockHATool(name="A"),
            MockHATool(name="B"),
            MockHATool(name="C"),
        ]

        result = translate_tools(ha_tools)

        assert [t.name for t in result] == ["A", "B", "C"]

    def test_iterable_input(self) -> None:
        """Test that any iterable works, not just lists."""

        def tool_generator():
            yield MockHATool(name="Gen1")
            yield MockHATool(name="Gen2")

        result = translate_tools(tool_generator())

        assert len(result) == 2
        assert result[0].name == "Gen1"
        assert result[1].name == "Gen2"


class TestToolOutputFormat:
    """Tests for the AG-UI Tool output format."""

    def test_tool_has_required_fields(self) -> None:
        """Test that translated tool has all required AG-UI fields."""
        ha_tool = MockHATool(
            name="TestTool",
            description="A test tool",
            parameters=vol.Schema({vol.Required("arg"): str}),
        )

        result = translate_tool(ha_tool)

        # AG-UI Tool should have these fields
        assert hasattr(result, "name")
        assert hasattr(result, "description")
        assert hasattr(result, "parameters")

    def test_parameters_are_json_schema(self) -> None:
        """Test that parameters are in JSON Schema format."""
        ha_tool = MockHATool(
            name="TestTool",
            parameters=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Optional("count"): int,
                }
            ),
        )

        result = translate_tool(ha_tool)

        # Should be a dict (JSON Schema format)
        assert isinstance(result.parameters, dict)
