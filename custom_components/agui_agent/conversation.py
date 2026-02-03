"""Conversation entity for AG-UI Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import conversation
from homeassistant.components.conversation import AbstractConversationAgent
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, llm
from homeassistant.util import ulid

from .client import AGUIClient, AGUIClientResult
from .const import DOMAIN, LOGGER
from .tool_executor import ToolExecutionContext
from .tool_translator import translate_tools

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import AGUIAgentConfigEntry


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: AGUIAgentConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entity for AG-UI Agent."""
    agent = AGUIAgentConversationEntity(config_entry)
    async_add_entities([agent])
    LOGGER.info("AG-UI Agent conversation entity set up")


class AGUIAgentConversationEntity(
    conversation.ConversationEntity, AbstractConversationAgent
):
    """Conversation entity that communicates with remote AG-UI agents."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: AGUIAgentConfigEntry) -> None:
        """Initialize the conversation entity."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._client = AGUIClient(
            endpoint=entry.runtime_data.endpoint,
            timeout=entry.runtime_data.timeout,
            bearer_token=entry.runtime_data.bearer_token,
        )
        # Conversation state per thread
        self._conversation_history: dict[str, list[dict[str, Any]]] = {}

    @property
    def supported_languages(self) -> list[str] | str:
        """Return supported languages."""
        return "*"

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a conversation turn."""
        LOGGER.debug(
            "Processing conversation input: %s (conversation_id: %s)",
            user_input.text[:100],
            user_input.conversation_id,
        )

        # Get or create conversation ID
        conversation_id = user_input.conversation_id or ulid.ulid_now()

        # Get conversation history for this thread
        messages = self._conversation_history.get(conversation_id, [])

        # Get Home Assistant LLM API
        llm_context = llm.LLMContext(
            platform=DOMAIN,
            context=user_input.context,
            language=user_input.language or "en",
            assistant=conversation.DOMAIN,
            device_id=user_input.device_id,
        )
        try:
            llm_api = await llm.async_get_api(
                self.hass,
                llm.LLM_API_ASSIST,
                llm_context,
            )
        except HomeAssistantError:
            LOGGER.exception("Error getting LLM API")
            return _error_response(
                conversation_id,
                "Error getting LLM API. Please check your configuration.",
            )

        # Get available tools from Home Assistant
        ha_tools = llm_api.tools
        agui_tools = translate_tools(ha_tools)

        # Add user message to history
        messages.append(
            {
                "role": "user",
                "content": user_input.text,
                "id": ulid.ulid_now(),
            }
        )

        # Create tool execution context
        tool_ctx = ToolExecutionContext(
            hass=self.hass,
            ha_llm_api=llm_api,
        )

        # Build context for the agent
        context = {
            "user_id": user_input.context.user_id if user_input.context else "",
            "language": user_input.language or "en",
        }

        # Run the agent
        try:
            result: AGUIClientResult = await self._client.run(
                thread_id=conversation_id,
                run_id=ulid.ulid_now(),
                messages=messages,
                tools=agui_tools,
                context=context,
                tool_ctx=tool_ctx,
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Error running AG-UI agent")
            return _error_response(
                conversation_id,
                f"Error communicating with AG-UI agent: {err}",
            )

        # Update conversation history
        if result.response_text:
            messages.append(
                {
                    "role": "assistant",
                    "content": result.response_text,
                    "id": ulid.ulid_now(),
                }
            )

        # Store updated history
        self._conversation_history[conversation_id] = result.messages

        # Build response
        LOGGER.debug(
            "Building response with text (%d chars): %s",
            len(result.response_text) if result.response_text else 0,
            result.response_text[:200] if result.response_text else "(empty)",
        )
        response = intent.IntentResponse(language=user_input.language or "en")
        response.async_set_speech(result.response_text)

        return conversation.ConversationResult(
            response=response,
            conversation_id=conversation_id,
        )


def _error_response(
    conversation_id: str,
    error_message: str,
) -> conversation.ConversationResult:
    """Create an error response."""
    response = intent.IntentResponse(language="en")
    response.async_set_error(
        intent.IntentResponseErrorCode.UNKNOWN,
        error_message,
    )
    return conversation.ConversationResult(
        response=response,
        conversation_id=conversation_id,
    )
