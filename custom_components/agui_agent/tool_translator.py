"""Translate Home Assistant LLM tools to AG-UI Tool format."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ag_ui.core import Tool
from voluptuous_openapi import convert

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from homeassistant.helpers import llm


def translate_tool(
    tool: llm.Tool,
    custom_serializer: Callable[[Any], Any] | None = None,
) -> Tool:
    """
    Convert a Home Assistant LLM tool to AG-UI Tool format.

    Args:
        tool: Home Assistant LLM tool instance.
        custom_serializer: Optional custom serializer for voluptuous schema conversion.

    Returns:
        AG-UI Tool with name, description, and JSON Schema parameters.

    """
    # Convert voluptuous schema to JSON Schema format
    parameters = convert(tool.parameters, custom_serializer=custom_serializer)

    return Tool(
        name=tool.name,
        description=tool.description or "",
        parameters=parameters,
    )


def translate_tools(
    tools: Iterable[llm.Tool],
    custom_serializer: Callable[[Any], Any] | None = None,
) -> list[Tool]:
    """
    Convert multiple Home Assistant LLM tools to AG-UI Tool format.

    Args:
        tools: Iterable of Home Assistant LLM tool instances.
        custom_serializer: Optional custom serializer for voluptuous schema conversion.

    Returns:
        List of AG-UI Tools.

    """
    return [translate_tool(tool, custom_serializer) for tool in tools]
