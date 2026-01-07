# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AG-UI Agent is a Home Assistant custom integration that connects to remote AG-UI Protocol compatible AI agent backends. It provides a framework-agnostic abstraction layer enabling any AG-UI-compatible agent (LangGraph, CrewAI, Google ADK, custom) to control Home Assistant via standardized event-driven streaming.

**Key Concept**: The AG-UI protocol keeps tool execution on the frontend (Home Assistant), while the agent backend only requests tool calls via events. This separation ensures HA retains control over security-sensitive operations.

## Development Commands

```bash
# Lint (run before PRs)
ruff check .

# Run tests
pytest tests/ -v

# Format code
ruff format .
```

Testing uses pytest with `pytest-homeassistant-custom-component`. Tests are in `tests/`.

## Architecture

### Directory Structure

```
custom_components/agui_agent/
├── __init__.py          # Entry setup, AGUIAgentData dataclass
├── const.py             # DOMAIN, configuration constants
├── config_flow.py       # Configuration UI for endpoint URL
├── conversation.py      # ConversationEntity - HA conversation integration
├── client.py            # AGUIClient - SSE client, event processor
├── tool_executor.py     # Execute HA tools from TOOL_CALL_* events
└── tool_translator.py   # Convert HA LLM tools to AG-UI Tool format

tests/
├── conftest.py          # Shared fixtures
├── test_client.py       # SSE parsing, event processing, remote fetch
├── test_tool_executor.py # HA tool execution
└── test_tool_translator.py # Tool format conversion
```

### Event Flow

1. **User speaks** → `AGUIAgentConversationEntity.async_process()`
2. **Translate tools** → HA LLM tools converted to AG-UI `Tool` format
3. **AGUIClient.run()** → POST `RunAgentInput` to remote endpoint
4. **Process SSE stream** → Parse events: `RUN_STARTED`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`, `RUN_FINISHED`
5. **Execute tools locally** → On `TOOL_CALL_END`, execute via `ha_llm_api.async_call_tool()`
6. **Return response** → `ConversationResult` with accumulated text

### Key Classes

- **`AGUIClient`** (`client.py`) - Framework-agnostic SSE client. Sends `RunAgentInput`, processes event stream, accumulates text responses, triggers tool execution on `TOOL_CALL_END`.

- **`AGUIAgentConversationEntity`** (`conversation.py`) - Home Assistant conversation entity. Gets HA LLM API, translates tools, runs client, returns `ConversationResult`.

- **`ToolExecutionContext`** (`tool_executor.py`) - Minimal context for tool execution (hass, ha_llm_api).

- **`translate_tools()`** (`tool_translator.py`) - Converts HA `llm.Tool` to AG-UI `Tool` using `voluptuous-openapi` for JSON Schema.

### AG-UI Event Types Handled

| Event | Action |
|-------|--------|
| `RUN_STARTED` | Log run start |
| `TEXT_MESSAGE_CONTENT` | Accumulate response text |
| `TOOL_CALL_START` | Create pending tool call |
| `TOOL_CALL_ARGS` | Accumulate JSON args |
| `TOOL_CALL_END` | Execute tool via HA LLM API |
| `RUN_FINISHED` | Complete processing |
| `RUN_ERROR` | Log error |

## Key Dependencies

From `manifest.json`:
- `ag-ui-core>=0.1.10` - AG-UI protocol types
- `voluptuous-openapi>=0.0.5` - Schema conversion

HA dependencies: `conversation`

**Not included** (unlike Home Generative Agent): langchain, langgraph, psycopg

## Configuration

Single config entry with:
- `agui_endpoint` (required) - URL of AG-UI agent endpoint
- `timeout` (default: 120) - Request timeout in seconds

## Lint Configuration

Ruff is configured in `.ruff.toml` with `ALL` rules enabled. Test files have relaxed rules for asserts, private member access, magic values, etc.
