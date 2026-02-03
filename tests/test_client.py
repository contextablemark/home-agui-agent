"""Unit tests for AG-UI client module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ag_ui.core import (
    EventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)

from custom_components.agui_agent.client import (
    _EVENT_TYPE_MAP,
    AGUIClient,
    PendingToolCall,
    _convert_to_agui_messages,
)
from custom_components.agui_agent.tool_executor import (
    ToolCallResult,
    ToolExecutionContext,
)


class TestPendingToolCall:
    """Tests for PendingToolCall dataclass."""

    def test_empty_args(self) -> None:
        """Test get_args with no accumulated chunks."""
        pending = PendingToolCall(tool_call_id="tc-1", tool_name="test_tool")
        assert pending.get_args() == {}

    def test_valid_json_args(self) -> None:
        """Test get_args with valid JSON."""
        pending = PendingToolCall(tool_call_id="tc-1", tool_name="test_tool")
        pending.args_chunks.append('{"name": "test", ')
        pending.args_chunks.append('"value": 42}')
        assert pending.get_args() == {"name": "test", "value": 42}

    def test_invalid_json_args(self) -> None:
        """Test get_args with invalid JSON returns empty dict."""
        pending = PendingToolCall(tool_call_id="tc-1", tool_name="test_tool")
        pending.args_chunks.append("{invalid json")
        assert pending.get_args() == {}


class TestConvertToAGUIMessages:
    """Tests for _convert_to_agui_messages function."""

    def test_empty_messages(self) -> None:
        """Test conversion of empty message list."""
        result = _convert_to_agui_messages([])
        assert result == []

    def test_user_message(self) -> None:
        """Test conversion of user message."""
        messages = [{"role": "user", "content": "Hello", "id": "msg-1"}]
        result = _convert_to_agui_messages(messages)
        assert len(result) == 1
        assert result[0].role == "user"
        assert result[0].content == "Hello"
        assert result[0].id == "msg-1"

    def test_assistant_message(self) -> None:
        """Test conversion of assistant message."""
        messages = [{"role": "assistant", "content": "Hi there", "id": "msg-2"}]
        result = _convert_to_agui_messages(messages)
        assert len(result) == 1
        assert result[0].role == "assistant"
        assert result[0].content == "Hi there"

    def test_tool_message(self) -> None:
        """Test conversion of tool message."""
        messages = [
            {
                "role": "tool",
                "content": '{"result": "ok"}',
                "id": "msg-3",
                "tool_call_id": "tc-1",
            }
        ]
        result = _convert_to_agui_messages(messages)
        assert len(result) == 1
        assert result[0].role == "tool"
        assert result[0].tool_call_id == "tc-1"

    def test_mixed_messages(self) -> None:
        """Test conversion of mixed message types."""
        messages = [
            {"role": "user", "content": "Turn on the light", "id": "msg-1"},
            {"role": "assistant", "content": "I'll do that", "id": "msg-2"},
            {"role": "tool", "content": "done", "id": "msg-3", "tool_call_id": "tc-1"},
        ]
        result = _convert_to_agui_messages(messages)
        assert len(result) == 3
        assert result[0].role == "user"
        assert result[1].role == "assistant"
        assert result[2].role == "tool"

    def test_system_message_converted(self) -> None:
        """Test that system messages are converted to AG-UI SystemMessage."""
        from ag_ui.core import SystemMessage

        messages = [{"role": "system", "content": "System prompt", "id": "sys-1"}]
        result = _convert_to_agui_messages(messages)
        assert len(result) == 1
        assert isinstance(result[0], SystemMessage)
        assert result[0].role == "system"
        assert result[0].content == "System prompt"

    def test_unknown_role_ignored(self) -> None:
        """Test that unknown roles are ignored."""
        messages = [{"role": "unknown_role", "content": "Some content", "id": "unk-1"}]
        result = _convert_to_agui_messages(messages)
        assert result == []


class TestEventTypeMap:
    """Tests for the event type mapping."""

    def test_all_common_events_mapped(self) -> None:
        """Test that common event types are mapped."""
        expected_types = [
            EventType.RUN_STARTED,
            EventType.RUN_FINISHED,
            EventType.RUN_ERROR,
            EventType.TEXT_MESSAGE_START,
            EventType.TEXT_MESSAGE_CONTENT,
            EventType.TEXT_MESSAGE_END,
            EventType.TOOL_CALL_START,
            EventType.TOOL_CALL_ARGS,
            EventType.TOOL_CALL_END,
            EventType.TOOL_CALL_RESULT,
        ]
        for event_type in expected_types:
            assert event_type in _EVENT_TYPE_MAP


class TestAGUIClientInit:
    """Tests for AGUIClient initialization."""

    def test_default_bearer_token_is_none(self) -> None:
        """Test that bearer_token defaults to None."""
        client = AGUIClient(endpoint="http://example.com")
        assert client._bearer_token is None

    def test_bearer_token_is_stored(self) -> None:
        """Test that bearer_token is stored when provided."""
        token = "my-secret-token"  # noqa: S105
        client = AGUIClient(endpoint="http://example.com", bearer_token=token)
        assert client._bearer_token == token

    def test_timeout_is_set(self) -> None:
        """Test that timeout is properly configured."""
        client = AGUIClient(endpoint="http://example.com", timeout=60)
        assert client._timeout.total == 60


class TestAGUIClientSSEParsing:
    """Tests for SSE stream parsing."""

    def test_parse_sse_event_text_content(self) -> None:
        """Test parsing a TEXT_MESSAGE_CONTENT event."""
        client = AGUIClient(endpoint="http://example.com")
        data = json.dumps(
            {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg-1", "delta": "Hello"}
        )
        event = client._parse_sse_event("TEXT_MESSAGE_CONTENT", data)

        assert event is not None
        assert isinstance(event, TextMessageContentEvent)
        assert event.delta == "Hello"
        assert event.message_id == "msg-1"

    def test_parse_sse_event_tool_call_start(self) -> None:
        """Test parsing a TOOL_CALL_START event."""
        client = AGUIClient(endpoint="http://example.com")
        data = json.dumps(
            {
                "type": "TOOL_CALL_START",
                "toolCallId": "tc-1",
                "toolCallName": "HassTurnOn",
            }
        )
        event = client._parse_sse_event("TOOL_CALL_START", data)

        assert event is not None
        assert isinstance(event, ToolCallStartEvent)
        assert event.tool_call_id == "tc-1"
        assert event.tool_call_name == "HassTurnOn"

    def test_parse_sse_event_run_error(self) -> None:
        """Test parsing a RUN_ERROR event."""
        client = AGUIClient(endpoint="http://example.com")
        data = json.dumps({"type": "RUN_ERROR", "message": "Something went wrong"})
        event = client._parse_sse_event("RUN_ERROR", data)

        assert event is not None
        assert isinstance(event, RunErrorEvent)
        assert event.message == "Something went wrong"

    def test_parse_sse_event_invalid_json(self) -> None:
        """Test parsing with invalid JSON returns None."""
        client = AGUIClient(endpoint="http://example.com")
        event = client._parse_sse_event("TEXT_MESSAGE_CONTENT", "{invalid")
        assert event is None

    def test_parse_sse_event_unknown_type(self) -> None:
        """Test parsing unknown event type returns None."""
        client = AGUIClient(endpoint="http://example.com")
        data = json.dumps({"type": "CUSTOM_EVENT", "data": "value"})
        # Unknown event types are logged and return None
        event = client._parse_sse_event("CUSTOM_EVENT", data)
        assert event is None

    @pytest.mark.asyncio
    async def test_parse_sse_stream(self) -> None:
        """Test parsing a complete SSE stream."""
        client = AGUIClient(endpoint="http://example.com")

        # Simulate SSE stream bytes - include required threadId field
        sse_lines = [
            b"event: RUN_STARTED\n",
            b'data: {"type": "RUN_STARTED", "runId": "run-1", "threadId": "thread-1"}\n',
            b"\n",
            b"event: TEXT_MESSAGE_CONTENT\n",
            b'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg-1", "delta": "Hi"}\n',
            b"\n",
            b"event: RUN_FINISHED\n",
            b'data: {"type": "RUN_FINISHED", "runId": "run-1", "threadId": "thread-1"}\n',
            b"\n",
        ]

        # Create async iterator from lines
        async def async_iter():
            for line in sse_lines:
                yield line

        mock_content = AsyncMock()
        mock_content.__aiter__ = lambda _self: async_iter()

        events = []
        async for event in client._parse_sse_stream(mock_content):
            events.append(event)

        assert len(events) == 3
        assert isinstance(events[0], RunStartedEvent)
        assert isinstance(events[1], TextMessageContentEvent)
        assert events[1].delta == "Hi"
        assert isinstance(events[2], RunFinishedEvent)


class TestAGUIClientEventProcessing:
    """Tests for event processing and tool execution."""

    @pytest.fixture
    def mock_tool_ctx(self) -> ToolExecutionContext:
        """Create a mock tool execution context."""
        return ToolExecutionContext(
            hass=MagicMock(),
            ha_llm_api=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_process_text_message_content(
        self, mock_tool_ctx: ToolExecutionContext
    ) -> None:
        """Test processing TEXT_MESSAGE_CONTENT accumulates text."""
        client = AGUIClient(endpoint="http://example.com")
        response_chunks: list[str] = []
        tool_results: list[ToolCallResult] = []
        messages: list[dict[str, Any]] = []

        event = TextMessageContentEvent(
            type=EventType.TEXT_MESSAGE_CONTENT,
            message_id="msg-1",
            delta="Hello ",
        )

        await client._process_event(
            event=event,
            response_chunks=response_chunks,
            tool_results=tool_results,
            current_messages=messages,
            tool_ctx=mock_tool_ctx,
        )

        assert response_chunks == ["Hello "]

    @pytest.mark.asyncio
    async def test_process_tool_call_flow(
        self, mock_tool_ctx: ToolExecutionContext
    ) -> None:
        """Test complete tool call flow: start -> args -> end."""
        client = AGUIClient(endpoint="http://example.com")
        response_chunks: list[str] = []
        tool_results: list[ToolCallResult] = []
        messages: list[dict[str, Any]] = []

        # Mock execute_tool
        with patch("custom_components.agui_agent.client.execute_tool") as mock_execute:
            mock_execute.return_value = ToolCallResult(
                tool_call_id="tc-1",
                tool_name="HassTurnOn",
                content='{"success": true}',
                status="success",
            )

            # Process TOOL_CALL_START (use snake_case for Pydantic model)
            start_event = ToolCallStartEvent(
                type=EventType.TOOL_CALL_START,
                tool_call_id="tc-1",
                tool_call_name="HassTurnOn",
            )
            await client._process_event(
                event=start_event,
                response_chunks=response_chunks,
                tool_results=tool_results,
                current_messages=messages,
                tool_ctx=mock_tool_ctx,
            )

            # Verify tool call is pending
            assert "tc-1" in client._pending_tool_calls
            assert client._pending_tool_calls["tc-1"].tool_name == "HassTurnOn"

            # Process TOOL_CALL_ARGS
            args_event = ToolCallArgsEvent(
                type=EventType.TOOL_CALL_ARGS,
                tool_call_id="tc-1",
                delta='{"domain": ["light"]}',
            )
            await client._process_event(
                event=args_event,
                response_chunks=response_chunks,
                tool_results=tool_results,
                current_messages=messages,
                tool_ctx=mock_tool_ctx,
            )

            # Verify args accumulated
            assert client._pending_tool_calls["tc-1"].args_chunks == [
                '{"domain": ["light"]}'
            ]

            # Process TOOL_CALL_END
            end_event = ToolCallEndEvent(
                type=EventType.TOOL_CALL_END,
                tool_call_id="tc-1",
            )
            await client._process_event(
                event=end_event,
                response_chunks=response_chunks,
                tool_results=tool_results,
                current_messages=messages,
                tool_ctx=mock_tool_ctx,
            )

            # Verify tool was executed
            mock_execute.assert_called_once()
            assert len(tool_results) == 1
            assert tool_results[0].tool_name == "HassTurnOn"

            # Verify tool result added to messages
            assert len(messages) == 1
            assert messages[0]["role"] == "tool"
            assert messages[0]["tool_call_id"] == "tc-1"

            # Verify pending tool call was removed
            assert "tc-1" not in client._pending_tool_calls


class TestAGUIClientRemoteSSE:
    """Tests for remote SSE endpoint handling."""

    @pytest.fixture
    def mock_tool_ctx(self) -> ToolExecutionContext:
        """Create a mock tool execution context."""
        return ToolExecutionContext(
            hass=MagicMock(),
            ha_llm_api=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_fetch_remote_events_includes_bearer_token(self) -> None:
        """Test that Authorization header is added when bearer_token is set."""
        token = "test-token-123"  # noqa: S105
        client = AGUIClient(endpoint="http://example.com/agent", bearer_token=token)

        sse_lines = [
            b"event: RUN_FINISHED\n",
            b'data: {"type": "RUN_FINISHED", "runId": "run-1", "threadId": "t1"}\n',
            b"\n",
        ]

        async def async_iter():
            for line in sse_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.content.__aiter__ = lambda _self: async_iter()

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MagicMock())
        mock_session.post.return_value.__aenter__ = AsyncMock(
            return_value=mock_response
        )
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)

            from ag_ui.core import RunAgentInput

            run_input = RunAgentInput(
                thread_id="t1",
                run_id="r1",
                messages=[],
                tools=[],
                context=[],
                state={},
                forwarded_props={},
            )

            events = []
            async for event in client._fetch_remote_events(run_input):
                events.append(event)

            # Verify the post was called with Authorization header
            mock_session.post.assert_called_once()
            call_kwargs = mock_session.post.call_args[1]
            assert "headers" in call_kwargs
            assert call_kwargs["headers"]["Authorization"] == f"Bearer {token}"

    @pytest.mark.asyncio
    async def test_fetch_remote_events_no_auth_header_without_token(self) -> None:
        """Test that no Authorization header is added when bearer_token is None."""
        client = AGUIClient(endpoint="http://example.com/agent")

        sse_lines = [
            b"event: RUN_FINISHED\n",
            b'data: {"type": "RUN_FINISHED", "runId": "run-1", "threadId": "t1"}\n',
            b"\n",
        ]

        async def async_iter():
            for line in sse_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.content.__aiter__ = lambda _self: async_iter()

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MagicMock())
        mock_session.post.return_value.__aenter__ = AsyncMock(
            return_value=mock_response
        )
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)

            from ag_ui.core import RunAgentInput

            run_input = RunAgentInput(
                thread_id="t1",
                run_id="r1",
                messages=[],
                tools=[],
                context=[],
                state={},
                forwarded_props={},
            )

            events = []
            async for event in client._fetch_remote_events(run_input):
                events.append(event)

            # Verify the post was called without Authorization header
            mock_session.post.assert_called_once()
            call_kwargs = mock_session.post.call_args[1]
            assert "headers" in call_kwargs
            assert "Authorization" not in call_kwargs["headers"]

    @pytest.mark.asyncio
    async def test_fetch_remote_events_success(self) -> None:
        """Test successful remote SSE fetch."""
        client = AGUIClient(endpoint="http://example.com/agent")

        sse_lines = [
            b"event: RUN_STARTED\n",
            b'data: {"type": "RUN_STARTED", "runId": "run-1", "threadId": "t1"}\n',
            b"\n",
            b"event: TEXT_MESSAGE_CONTENT\n",
            b'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg-1", "delta": "Test"}\n',
            b"\n",
            b"event: RUN_FINISHED\n",
            b'data: {"type": "RUN_FINISHED", "runId": "run-1", "threadId": "t1"}\n',
            b"\n",
        ]

        async def async_iter():
            for line in sse_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.content.__aiter__ = lambda _self: async_iter()

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MagicMock())
        mock_session.post.return_value.__aenter__ = AsyncMock(
            return_value=mock_response
        )
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)

            from ag_ui.core import RunAgentInput

            # Note: Using RunAgentInput directly requires List[Context], not dict
            run_input = RunAgentInput(
                thread_id="t1",
                run_id="r1",
                messages=[],
                tools=[],
                context=[],  # raw AG-UI type requires list
                state={},
                forwarded_props={},
            )

            events = []
            async for event in client._fetch_remote_events(run_input):
                events.append(event)

            assert len(events) == 3
            assert isinstance(events[0], RunStartedEvent)
            assert isinstance(events[1], TextMessageContentEvent)
            assert isinstance(events[2], RunFinishedEvent)

    @pytest.mark.asyncio
    async def test_fetch_remote_events_http_error(self) -> None:
        """Test handling of HTTP error response."""
        client = AGUIClient(endpoint="http://example.com/agent")

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MagicMock())
        mock_session.post.return_value.__aenter__ = AsyncMock(
            return_value=mock_response
        )
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_client_session.return_value.__aexit__ = AsyncMock(return_value=None)

            from ag_ui.core import RunAgentInput

            # Note: Using RunAgentInput directly requires List[Context], not dict
            run_input = RunAgentInput(
                thread_id="t1",
                run_id="r1",
                messages=[],
                tools=[],
                context=[],  # raw AG-UI type requires list
                state={},
                forwarded_props={},
            )

            events = []
            async for event in client._fetch_remote_events(run_input):
                events.append(event)

            assert len(events) == 1
            assert isinstance(events[0], RunErrorEvent)
            assert "500" in events[0].message

    @pytest.mark.asyncio
    async def test_fetch_remote_events_connection_error(self) -> None:
        """Test handling of connection error."""
        import aiohttp

        client = AGUIClient(endpoint="http://example.com/agent")

        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_client_session.return_value.__aenter__ = AsyncMock(
                side_effect=aiohttp.ClientError("Connection refused")
            )

            from ag_ui.core import RunAgentInput

            # Note: Using RunAgentInput directly requires List[Context], not dict
            run_input = RunAgentInput(
                thread_id="t1",
                run_id="r1",
                messages=[],
                tools=[],
                context=[],  # raw AG-UI type requires list
                state={},
                forwarded_props={},
            )

            events = []
            async for event in client._fetch_remote_events(run_input):
                events.append(event)

            assert len(events) == 1
            assert isinstance(events[0], RunErrorEvent)
            assert "Connection" in events[0].message


class TestAGUIClientToolExecutionLoop:
    """Tests for the tool execution loop in AGUIClient.run()."""

    @pytest.fixture
    def mock_tool_ctx(self) -> ToolExecutionContext:
        """Create a mock tool execution context."""
        return ToolExecutionContext(
            hass=MagicMock(),
            ha_llm_api=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_run_no_tools_single_iteration(
        self, mock_tool_ctx: ToolExecutionContext
    ) -> None:
        """Test that run() completes in one iteration when no tools are called."""
        client = AGUIClient(endpoint="http://example.com/agent")
        call_count = 0

        async def mock_fetch_events(_run_input):
            nonlocal call_count
            call_count += 1
            # Yield text response only (no tool calls)
            yield RunStartedEvent(
                type=EventType.RUN_STARTED, run_id="r1", thread_id="t1"
            )
            yield TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT, message_id="m1", delta="Hello!"
            )
            yield RunFinishedEvent(
                type=EventType.RUN_FINISHED, run_id="r1", thread_id="t1"
            )

        with patch.object(client, "_fetch_remote_events", mock_fetch_events):
            result = await client.run(
                thread_id="t1",
                run_id="r1",
                messages=[{"role": "user", "content": "Hi", "id": "u1"}],
                tools=[],
                context={},
                tool_ctx=mock_tool_ctx,
            )

        assert call_count == 1
        assert result.response_text == "Hello!"
        assert len(result.tool_results) == 0

    @pytest.mark.asyncio
    async def test_run_with_tool_calls_loops(
        self, mock_tool_ctx: ToolExecutionContext
    ) -> None:
        """Test that run() loops when tools are executed, sending results back."""
        from ag_ui.core import Tool

        client = AGUIClient(endpoint="http://example.com/agent")
        call_count = 0

        async def mock_fetch_events(_run_input):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: agent requests a tool
                yield RunStartedEvent(
                    type=EventType.RUN_STARTED, run_id="r1", thread_id="t1"
                )
                yield ToolCallStartEvent(
                    type=EventType.TOOL_CALL_START,
                    tool_call_id="tc-1",
                    tool_call_name="HassTurnOn",
                )
                yield ToolCallArgsEvent(
                    type=EventType.TOOL_CALL_ARGS,
                    tool_call_id="tc-1",
                    delta='{"entity_id": "light.kitchen"}',
                )
                yield ToolCallEndEvent(
                    type=EventType.TOOL_CALL_END, tool_call_id="tc-1"
                )
                yield RunFinishedEvent(
                    type=EventType.RUN_FINISHED, run_id="r1", thread_id="t1"
                )
            else:
                # Second call: agent receives tool result and responds
                yield RunStartedEvent(
                    type=EventType.RUN_STARTED, run_id="r1", thread_id="t1"
                )
                yield TextMessageContentEvent(
                    type=EventType.TEXT_MESSAGE_CONTENT,
                    message_id="m1",
                    delta="I turned on the kitchen light.",
                )
                yield RunFinishedEvent(
                    type=EventType.RUN_FINISHED, run_id="r1", thread_id="t1"
                )

        with (
            patch.object(client, "_fetch_remote_events", mock_fetch_events),
            patch("custom_components.agui_agent.client.execute_tool") as mock_execute,
        ):
            mock_execute.return_value = ToolCallResult(
                tool_call_id="tc-1",
                tool_name="HassTurnOn",
                content='{"success": true}',
                status="success",
            )

            result = await client.run(
                thread_id="t1",
                run_id="r1",
                messages=[
                    {"role": "user", "content": "Turn on the kitchen light", "id": "u1"}
                ],
                tools=[
                    Tool(
                        name="HassTurnOn",
                        description="Turn on a device",
                        parameters={"type": "object", "properties": {}},
                    )
                ],
                context={},
                tool_ctx=mock_tool_ctx,
            )

        # Should have made 2 calls: first for tool request, second after tool result
        assert call_count == 2
        assert result.response_text == "I turned on the kitchen light."
        assert len(result.tool_results) == 1
        assert result.tool_results[0].tool_name == "HassTurnOn"

    @pytest.mark.asyncio
    async def test_run_includes_tool_result_in_second_request(
        self, mock_tool_ctx: ToolExecutionContext
    ) -> None:
        """Test that tool results are included in messages for subsequent requests."""
        from ag_ui.core import Tool

        client = AGUIClient(endpoint="http://example.com/agent")
        captured_run_inputs = []

        async def mock_fetch_events(run_input):
            captured_run_inputs.append(run_input)

            if len(captured_run_inputs) == 1:
                # First call: request tool
                yield ToolCallStartEvent(
                    type=EventType.TOOL_CALL_START,
                    tool_call_id="tc-1",
                    tool_call_name="HassGetState",
                )
                yield ToolCallArgsEvent(
                    type=EventType.TOOL_CALL_ARGS,
                    tool_call_id="tc-1",
                    delta='{"entity_id": "sensor.temp"}',
                )
                yield ToolCallEndEvent(
                    type=EventType.TOOL_CALL_END, tool_call_id="tc-1"
                )
            else:
                # Second call: respond with text
                yield TextMessageContentEvent(
                    type=EventType.TEXT_MESSAGE_CONTENT,
                    message_id="m1",
                    delta="Temperature is 72°F",
                )

        with (
            patch.object(client, "_fetch_remote_events", mock_fetch_events),
            patch("custom_components.agui_agent.client.execute_tool") as mock_execute,
        ):
            mock_execute.return_value = ToolCallResult(
                tool_call_id="tc-1",
                tool_name="HassGetState",
                content='{"state": "72"}',
                status="success",
            )

            await client.run(
                thread_id="t1",
                run_id="r1",
                messages=[{"role": "user", "content": "What's the temp?", "id": "u1"}],
                tools=[
                    Tool(
                        name="HassGetState",
                        description="Get entity state",
                        parameters={"type": "object", "properties": {}},
                    )
                ],
                context={},
                tool_ctx=mock_tool_ctx,
            )

        # Verify second request includes tool result
        assert len(captured_run_inputs) == 2
        second_request = captured_run_inputs[1]
        # Find the tool message in the second request
        tool_messages = [m for m in second_request.messages if m.role == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0].tool_call_id == "tc-1"
        assert '{"state": "72"}' in tool_messages[0].content

    @pytest.mark.asyncio
    async def test_run_max_iterations_prevents_infinite_loop(
        self, mock_tool_ctx: ToolExecutionContext
    ) -> None:
        """Test that run() stops after max_iterations to prevent infinite loops."""
        from ag_ui.core import Tool

        client = AGUIClient(endpoint="http://example.com/agent")
        call_count = 0

        async def mock_fetch_events(_run_input):
            nonlocal call_count
            call_count += 1
            # Always request another tool (would loop forever without limit)
            yield ToolCallStartEvent(
                type=EventType.TOOL_CALL_START,
                tool_call_id=f"tc-{call_count}",
                tool_call_name="SomeTool",
            )
            yield ToolCallEndEvent(
                type=EventType.TOOL_CALL_END, tool_call_id=f"tc-{call_count}"
            )

        with (
            patch.object(client, "_fetch_remote_events", mock_fetch_events),
            patch("custom_components.agui_agent.client.execute_tool") as mock_execute,
        ):
            mock_execute.return_value = ToolCallResult(
                tool_call_id="tc-1",
                tool_name="SomeTool",
                content="result",
                status="success",
            )

            result = await client.run(
                thread_id="t1",
                run_id="r1",
                messages=[],
                tools=[
                    Tool(
                        name="SomeTool",
                        description="A tool",
                        parameters={"type": "object", "properties": {}},
                    )
                ],
                context={},
                tool_ctx=mock_tool_ctx,
            )

        # Should stop at max_iterations (10)
        assert call_count == 10
        assert len(result.tool_results) == 10
