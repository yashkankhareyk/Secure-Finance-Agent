"""
Responder Node - Generates the final response using the LLM.
Combines tool results with the conversation context.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from agent.state import AgentState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional financial advisory AI assistant. Your role is to provide
helpful, accurate, and compliant financial information and analysis.

IMPORTANT RULES:
1. You are NOT a licensed financial advisor. Always clarify this.
2. Never make specific buy/sell recommendations for individual securities.
3. Always consider the user's risk tolerance and investment horizon.
4. Provide balanced perspectives - mention both risks and opportunities.
5. Use data and facts from the provided tool results when available.
6. If you don't have enough information, ask clarifying questions.
7. Never guarantee returns or make promises about investment performance.
8. Reference relevant regulations when discussing compliance topics.
9. Protect user privacy - never ask for or store personal financial details.
10. Format responses clearly with headings, bullet points, and tables when appropriate.

When tool results are provided, integrate them naturally into your response.
When no tool results are available, use your general financial knowledge.

Always be professional, educational, and helpful."""


def generate_response(state: AgentState) -> AgentState:
    """Generate the final response using the LLM."""
    from agent.graph import get_llm

    llm = get_llm()
    query = state.get("current_query", "")
    tool_results = state.get("tool_results", {})
    messages = list(state.get("messages", []))

    # Build the context message
    context_parts = [f"User Query: {query}"]

    if tool_results and tool_results.get("result"):
        route = tool_results.get("route", "unknown")
        result = tool_results["result"]
        context_parts.append(f"\nTool Used: {route}")
        context_parts.append(f"\nTool Results:\n{result}")

    context = "\n".join(context_parts)

    # Build message list for LLM
    llm_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
    ]

    # Add conversation history (last 10 messages for context window management)
    history = messages[-10:] if len(messages) > 10 else messages

    # Add the current turn
    llm_messages.append(
        HumanMessage(content=context)
    )

    try:
        response = llm.invoke(llm_messages)
        response_text = response.content

    except Exception as e:
        logger.error(f"LLM response generation error: {e}")
        response_text = (
            "I apologize, but I'm having trouble generating a response right now. "
            "Please try again in a moment. If you have specific financial questions, "
            "I'm here to help with investment information, market data, calculations, "
            "and compliance guidance."
        )

    # Add the response to messages
    new_messages = messages + [
        HumanMessage(content=query),
        AIMessage(content=response_text),
    ]

    return {
        **state,
        "messages": new_messages,
        "processing_complete": True,
    }