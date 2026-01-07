# AG-UI Agent for Home Assistant

A Home Assistant custom integration that connects to remote [AG-UI Protocol](https://github.com/ag-ui-protocol/ag-ui) compatible AI agents, enabling framework-agnostic smart home control.

## Overview

AG-UI Agent provides a **framework-agnostic abstraction layer** that enables integration of various agentic frameworks into the Home Assistant smart home environment. The AG-UI protocol serves as a standardized event-driven streaming interface between *any* AG-UI compatible agent backend and Home Assistant's frontend tool execution layer.

**Key Benefits:**
- **Framework Agnostic**: Connect to any AG-UI-compatible agent backend
- **Standardized Protocol**: Any AG-UI-compatible agent works with the same client code
- **Frontend Tool Execution**: Home Assistant retains control of tool execution (security, validation)
- **Remote Agent Support**: Connect to agents running anywhere via SSE endpoints
- **Future-Proof**: As new agent frameworks emerge, they can be integrated via AG-UI adapters

**Why AG-UI?**

The AG-UI protocol was designed specifically for connecting AI agents to user interfaces while keeping tool execution on the frontend. This separation is critical for Home Assistant because:
1. Tools need access to the HA runtime (entity states, service calls, user context)
2. Security-sensitive operations require frontend validation
3. Local tool execution avoids sending HA credentials to remote agents

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Home Assistant (Frontend)                           │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                   AGUIAgentConversationEntity                         │ │
│  │  • Owns Home Assistant context (entities, services, user)             │ │
│  │  • Executes ALL tools locally via HA LLM API                          │ │
│  │  • Translates HA tools to AG-UI format                                │ │
│  └────────────────────────────┬──────────────────────────────────────────┘ │
│                               │                                             │
│  ┌────────────────────────────▼──────────────────────────────────────────┐ │
│  │                         AGUIClient                                     │ │
│  │  • Framework-agnostic event processor                                 │ │
│  │  • Handles AG-UI protocol (RUN_*, TEXT_*, TOOL_CALL_* events)        │ │
│  │  • Works identically with ANY AG-UI-compatible backend               │ │
│  └────────────────────────────┬──────────────────────────────────────────┘ │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────────────┐
          │                     │                             │
          ▼                     ▼                             ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐
│  LangGraph Agent    │  │   CrewAI Agent      │  │  Custom Agent Server    │
│                     │  │                     │  │                         │
│  ag_ui_langgraph    │  │  ag_ui_crewai       │  │  Your AG-UI server      │
│  adapter            │  │  adapter            │  │                         │
└─────────────────────┘  └─────────────────────┘  └─────────────────────────┘
```

**The AGUIClient doesn't know or care which framework powers the agent.** It only understands AG-UI events.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Find "AG-UI Agent" and install it
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/agui_agent` directory to your Home Assistant `config/custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services → Add Integration
2. Search for "AG-UI Agent"
3. Enter your AG-UI endpoint URL (e.g., `http://your-agent-server:8005/agent`)
4. Configure timeout settings as needed

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `agui_endpoint` | string | *required* | AG-UI agent endpoint URL |
| `timeout` | int | `120` | Request timeout in seconds |

## Compatible Agent Backends

AG-UI Agent works with any backend that implements the AG-UI protocol:

- **[LangGraph](https://langchain-ai.github.io/langgraph/)** via [ag-ui-langgraph](https://pypi.org/project/ag-ui-langgraph/)
- **[CrewAI](https://www.crewai.com/)** via AG-UI adapter
- **[Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/)** via AG-UI adapter
- **Custom agents** - implement the AG-UI SSE protocol

### What the Agent Backend Must Provide

Any AG-UI-compatible agent backend must:
1. Accept `RunAgentInput` (messages, tools, context) via POST request
2. Emit events via SSE stream following the AG-UI protocol
3. Request tool calls via `TOOL_CALL_*` events (not execute them)
4. Handle tool results injected by the frontend

The [AG-UI Protocol specification](https://github.com/ag-ui-protocol/ag-ui) defines the complete event schema.

## AG-UI Event Flow

### Typical Conversation Turn

```
1. User: "Turn on the kitchen light"

2. AGUIClient sends RunAgentInput:
   {
     "thread_id": "01HXY...",
     "messages": [{"role": "user", "content": "Turn on..."}],
     "tools": [{"name": "HassTurnOn", ...}],
     "context": {"user_id": "...", "language": "en"}
   }

3. Agent emits events via SSE:
   → RUN_STARTED
   → TEXT_MESSAGE_START (messageId: "msg-1")
   → TEXT_MESSAGE_CONTENT (delta: "I'll turn on the kitchen light.")
   → TEXT_MESSAGE_END
   → TOOL_CALL_START (toolCallId: "tc-1", toolCallName: "HassTurnOn")
   → TOOL_CALL_ARGS (delta: '{"domain": ["light"], "name": "Kitchen"}')
   → TOOL_CALL_END
   → RUN_FINISHED

4. AGUIClient:
   - Accumulates text: "I'll turn on the kitchen light."
   - On TOOL_CALL_END, executes HassTurnOn via HA LLM API
   - Returns ConversationResult with speech response
```

## Debugging

### Enable Debug Logging

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.agui_agent: debug
```

### Key Log Messages

```
DEBUG - Tool call started: HassTurnOn (tc-1)
DEBUG - Tool HassTurnOn executed: success
DEBUG - Text message ended
DEBUG - Agent run finished
```

### Common Issues

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| No response | Agent endpoint unreachable | Check URL and network connectivity |
| Timeout errors | Agent taking too long | Increase timeout setting |
| Tool not found | Tool not in HA LLM API | Verify tool is available in Home Assistant |
| Connection refused | Agent server not running | Start your AG-UI agent server |

## Version Information

- **AG-UI Protocol**: >= 0.1.10
- **Home Assistant**: 2025.2+
- **Python**: 3.13.2+

## References

- [AG-UI Protocol Specification](https://github.com/ag-ui-protocol/ag-ui)
- [Home Assistant Conversation Integration](https://developers.home-assistant.io/docs/intent_conversation)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
