"""
Execute frontend tools for AG-UI protocol integration.

This module handles tool execution when the AG-UI agent emits TOOL_CALL_* events.
Tools are executed via Home Assistant's LLM API.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)


@dataclass
class ToolExecutionContext:
    """Context required for executing tools."""

    hass: HomeAssistant
    ha_llm_api: Any  # llm.APIInstance


@dataclass
class ToolCallResult:
    """Result of a tool execution."""

    tool_call_id: str
    tool_name: str
    content: str
    status: str = "success"


async def execute_tool(
    tool_call_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
    ctx: ToolExecutionContext,
) -> ToolCallResult:
    """
    Execute a Home Assistant tool and return the result.

    Args:
        tool_call_id: Unique identifier for this tool call.
        tool_name: Name of the tool to execute.
        tool_args: Arguments to pass to the tool.
        ctx: Execution context containing HA resources.

    Returns:
        ToolCallResult with the execution result.

    """
    LOGGER.debug("Executing tool: %s(%s)", tool_name, tool_args)

    tool_input = llm.ToolInput(tool_name=tool_name, tool_args=tool_args)

    try:
        response = await ctx.ha_llm_api.async_call_tool(tool_input)
    except (HomeAssistantError, vol.Invalid) as err:
        LOGGER.warning("Tool %s failed: %s", tool_name, err)
        return ToolCallResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            content=f"Error: {err!r}",
            status="error",
        )
    except Exception as err:
        LOGGER.exception("Unexpected error executing tool %s", tool_name)
        return ToolCallResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            content=f"Error: {err!r}",
            status="error",
        )

    content_str = json.dumps(response) if not isinstance(response, str) else response
    return ToolCallResult(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        content=content_str,
        status="success",
    )
