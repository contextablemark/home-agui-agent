"""
AG-UI client for Home Assistant.

This module handles AG-UI protocol communication with remote agents.
It sends RunAgentInput, processes the event stream, and handles frontend tool execution.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import aiohttp
from ag_ui.core import (
    AssistantMessage,
    BaseEvent,
    Context,
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateDeltaEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    SystemMessage,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    Tool,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    UserMessage,
)
from ag_ui.core import (
    ToolMessage as AGUIToolMessage,
)
from pydantic import ValidationError

from .tool_executor import ToolCallResult, ToolExecutionContext, execute_tool

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Mapping from EventType to Pydantic event class for deserialization
_EVENT_TYPE_MAP: dict[EventType, type[BaseEvent]] = {
    EventType.RUN_STARTED: RunStartedEvent,
    EventType.RUN_FINISHED: RunFinishedEvent,
    EventType.RUN_ERROR: RunErrorEvent,
    EventType.TEXT_MESSAGE_START: TextMessageStartEvent,
    EventType.TEXT_MESSAGE_CONTENT: TextMessageContentEvent,
    EventType.TEXT_MESSAGE_END: TextMessageEndEvent,
    EventType.TOOL_CALL_START: ToolCallStartEvent,
    EventType.TOOL_CALL_ARGS: ToolCallArgsEvent,
    EventType.TOOL_CALL_END: ToolCallEndEvent,
    EventType.TOOL_CALL_RESULT: ToolCallResultEvent,
    EventType.STATE_SNAPSHOT: StateSnapshotEvent,
    EventType.STATE_DELTA: StateDeltaEvent,
    EventType.STEP_STARTED: StepStartedEvent,
    EventType.STEP_FINISHED: StepFinishedEvent,
}

LOGGER = logging.getLogger(__name__)


@dataclass
class PendingToolCall:
    """Tracks a tool call in progress (accumulating arguments)."""

    tool_call_id: str
    tool_name: str
    args_chunks: list[str] = field(default_factory=list)

    def get_args(self) -> dict[str, Any]:
        """Parse accumulated argument chunks into a dict."""
        args_str = "".join(self.args_chunks)
        if not args_str:
            return {}
        try:
            return json.loads(args_str)
        except json.JSONDecodeError:
            LOGGER.warning("Failed to parse tool args: %s", args_str)
            return {}


@dataclass
class AGUIClientResult:
    """Result of an AG-UI conversation turn."""

    response_text: str
    """The text response from the agent."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    """Updated messages list including tool results for next turn."""

    tool_results: list[ToolCallResult] = field(default_factory=list)
    """Tool execution results from this turn."""


class AGUIClient:
    """
    Client for communicating with remote AG-UI agents.

    This client handles:
    - Sending RunAgentInput to remote agents via SSE
    - Processing the event stream
    - Executing frontend tools when TOOL_CALL_* events are received
    - Accumulating text responses
    """

    def __init__(
        self,
        endpoint: str,
        timeout: int = 120,
    ) -> None:
        """
        Initialize the AG-UI client.

        Args:
            endpoint: URL of the remote AG-UI agent endpoint.
            timeout: Request timeout in seconds (default: 120).

        """
        self._endpoint = endpoint
        self._timeout = aiohttp.ClientTimeout(total=timeout, connect=30)
        self._pending_tool_calls: dict[str, PendingToolCall] = {}

    async def run(  # noqa: PLR0913
        self,
        thread_id: str,
        run_id: str,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        context: dict[str, Any],
        tool_ctx: ToolExecutionContext,
        forwarded_props: dict[str, Any] | None = None,
    ) -> AGUIClientResult:
        """
        Run a conversation turn with the remote agent.

        Args:
            thread_id: Conversation thread identifier.
            run_id: Unique run identifier.
            messages: Conversation messages in AG-UI format.
            tools: Available frontend tools.
            context: Additional context for the agent.
            tool_ctx: Context for executing tools.
            forwarded_props: Config options passed to the agent.

        Returns:
            AGUIClientResult with response and any tool results.

        """
        self._pending_tool_calls.clear()
        response_chunks: list[str] = []
        tool_results: list[ToolCallResult] = []
        current_messages = list(messages)

        # Convert messages to AG-UI message objects
        agui_messages = _convert_to_agui_messages(current_messages)

        # Convert context dict to list of Context objects
        context_list = [
            Context(description=str(k), value=str(v)) for k, v in context.items()
        ]

        # Create RunAgentInput
        run_input = RunAgentInput(
            thread_id=thread_id,
            run_id=run_id,
            messages=agui_messages,
            tools=tools,
            context=context_list,
            state={},
            forwarded_props=forwarded_props or {},
        )

        # Process events from remote agent
        async for event in self._fetch_remote_events(run_input):
            await self._process_event(
                event=event,
                response_chunks=response_chunks,
                tool_results=tool_results,
                current_messages=current_messages,
                tool_ctx=tool_ctx,
            )

        return AGUIClientResult(
            response_text="".join(response_chunks),
            messages=current_messages,
            tool_results=tool_results,
        )

    async def _fetch_remote_events(
        self, run_input: RunAgentInput
    ) -> AsyncIterator[BaseEvent]:
        """
        Fetch events from a remote AG-UI endpoint via SSE.

        Connects to the remote endpoint, sends RunAgentInput as JSON POST body,
        and parses the SSE stream into BaseEvent objects.

        Args:
            run_input: The RunAgentInput to send.

        Yields:
            BaseEvent objects parsed from SSE stream.

        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        # Serialize RunAgentInput to JSON
        payload = run_input.model_dump(mode="json")

        try:
            async with (
                aiohttp.ClientSession(timeout=self._timeout) as session,
                session.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                ) as response,
            ):
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    LOGGER.error(
                        "Remote AG-UI endpoint returned %d: %s",
                        response.status,
                        error_text[:500],
                    )
                    yield RunErrorEvent(
                        type=EventType.RUN_ERROR,
                        message=f"Remote endpoint error: {response.status}",
                    )
                    return

                # Parse SSE stream
                async for event in self._parse_sse_stream(response.content):
                    yield event

        except aiohttp.ClientError as err:
            LOGGER.exception("Failed to connect to remote AG-UI endpoint")
            yield RunErrorEvent(
                type=EventType.RUN_ERROR,
                message=f"Connection error: {err!r}",
            )

    async def _parse_sse_stream(
        self, content: aiohttp.StreamReader
    ) -> AsyncIterator[BaseEvent]:
        """
        Parse an SSE stream into AG-UI events.

        SSE format:
            event: <EventType>
            data: <JSON payload>
            <blank line>

        Args:
            content: aiohttp StreamReader for the response body.

        Yields:
            BaseEvent objects parsed from the stream.

        """
        event_type: str | None = None
        data_lines: list[str] = []

        async for line_bytes in content:
            line = line_bytes.decode("utf-8").rstrip("\r\n")

            if line.startswith("event:"):
                # New event type
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                # Accumulate data (can span multiple lines)
                data_lines.append(line[5:].strip())
            elif line == "":
                # Blank line = end of event
                if event_type and data_lines:
                    event = self._parse_sse_event(event_type, "\n".join(data_lines))
                    if event:
                        yield event
                # Reset for next event
                event_type = None
                data_lines = []

    def _parse_sse_event(self, event_type_str: str, data: str) -> BaseEvent | None:
        """
        Parse a single SSE event into a BaseEvent.

        Args:
            event_type_str: The event type string from SSE.
            data: The JSON data payload.

        Returns:
            Parsed BaseEvent or None if parsing failed.

        """
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            LOGGER.warning("Failed to parse SSE data as JSON: %s", data[:200])
            return None

        # Determine event type
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            LOGGER.debug("Unknown event type: %s, skipping", event_type_str)
            # Unknown event types are skipped
            return None

        # Get the appropriate event class
        event_class = _EVENT_TYPE_MAP.get(event_type, BaseEvent)

        try:
            return event_class.model_validate(payload)
        except ValidationError as err:
            LOGGER.warning(
                "Failed to validate event %s: %s (payload: %s)",
                event_type_str,
                err,
                str(payload)[:200],
            )
            return None

    async def _process_event(  # noqa: PLR0912
        self,
        event: BaseEvent,
        response_chunks: list[str],
        tool_results: list[ToolCallResult],
        current_messages: list[dict[str, Any]],
        tool_ctx: ToolExecutionContext,
    ) -> None:
        """
        Process a single AG-UI event.

        Args:
            event: The event to process.
            response_chunks: List to accumulate text response chunks.
            tool_results: List to accumulate tool results.
            current_messages: Messages list to update with tool results.
            tool_ctx: Context for executing tools.

        """
        event_type = event.type

        if event_type == EventType.TEXT_MESSAGE_START:
            LOGGER.debug("Text message started: %s", event)

        elif event_type == EventType.TEXT_MESSAGE_CONTENT:
            if isinstance(event, TextMessageContentEvent):
                response_chunks.append(event.delta)

        elif event_type == EventType.TEXT_MESSAGE_END:
            LOGGER.debug("Text message ended")

        elif event_type == EventType.TOOL_CALL_START:
            if isinstance(event, ToolCallStartEvent):
                self._pending_tool_calls[event.tool_call_id] = PendingToolCall(
                    tool_call_id=event.tool_call_id,
                    tool_name=event.tool_call_name,
                )
                LOGGER.debug(
                    "Tool call started: %s (%s)",
                    event.tool_call_name,
                    event.tool_call_id,
                )

        elif event_type == EventType.TOOL_CALL_ARGS:
            if isinstance(event, ToolCallArgsEvent):
                pending = self._pending_tool_calls.get(event.tool_call_id)
                if pending:
                    pending.args_chunks.append(event.delta)

        elif event_type == EventType.TOOL_CALL_END:
            if isinstance(event, ToolCallEndEvent):
                pending = self._pending_tool_calls.pop(event.tool_call_id, None)
                if pending:
                    # Execute the frontend tool
                    result = await execute_tool(
                        tool_call_id=pending.tool_call_id,
                        tool_name=pending.tool_name,
                        tool_args=pending.get_args(),
                        ctx=tool_ctx,
                    )
                    tool_results.append(result)

                    # Add tool result to messages for next turn
                    current_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": result.tool_call_id,
                            "content": result.content,
                        }
                    )

                    LOGGER.debug(
                        "Tool %s executed: %s",
                        pending.tool_name,
                        result.status,
                    )

        elif event_type == EventType.TOOL_CALL_RESULT:
            # This is for backend tools (agent-internal execution)
            if isinstance(event, ToolCallResultEvent):
                LOGGER.debug(
                    "Tool result from agent: %s = %s",
                    event.tool_call_id,
                    event.content[:100] if event.content else "",
                )

        elif event_type == EventType.RUN_STARTED:
            LOGGER.debug("Agent run started")

        elif event_type == EventType.RUN_FINISHED:
            LOGGER.debug("Agent run finished")

        elif event_type == EventType.RUN_ERROR:
            LOGGER.error("Agent run error: %s", event)

        else:
            LOGGER.debug("Unhandled event type: %s", event_type)


def _convert_to_agui_messages(
    messages: list[dict[str, Any]],
) -> list[SystemMessage | UserMessage | AssistantMessage | AGUIToolMessage]:
    """
    Convert message dicts to AG-UI message objects.

    Args:
        messages: List of message dictionaries.

    Returns:
        List of AG-UI message objects.

    """
    result: list[SystemMessage | UserMessage | AssistantMessage | AGUIToolMessage] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        msg_id = msg.get("id", "")

        if role == "system":
            result.append(SystemMessage(id=msg_id, role="system", content=content))
        elif role == "user":
            result.append(UserMessage(id=msg_id, role="user", content=content))
        elif role == "assistant":
            result.append(
                AssistantMessage(id=msg_id, role="assistant", content=content)
            )
        elif role == "tool":
            result.append(
                AGUIToolMessage(
                    id=msg_id,
                    role="tool",
                    toolCallId=msg.get("tool_call_id", ""),
                    content=content,
                )
            )

    return result
