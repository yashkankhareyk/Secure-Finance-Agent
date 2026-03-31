"""
Fix 3 — Updated Responder
Replaces: backend/agent/nodes/responder.py
Uses all_tool_results so the LLM sees context from every tool called this turn.
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

When multiple tool results are provided, synthesize them into a coherent, unified answer.
Always be professional, educational, and helpful."""


def generate_response(state: AgentState) -> AgentState:
    """Generate the final response using the LLM with all accumulated tool results."""
    from agent.graph import get_llm

    llm = get_llm()
    query = state.get("current_query", "")
    messages = list(state.get("messages", []))

    # ── Build context from ALL tool results (Fix 3) ───────────────────────────
    all_results: list[dict] = state.get("all_tool_results") or []

    # Backward compat: if all_tool_results is empty, fall back to tool_results
    if not all_results:
        tr = state.get("tool_results", {})
        if tr and tr.get("result"):
            all_results = [tr]

    context_parts = [f"User Query: {query}"]

    if all_results:
        context_parts.append("\nTool Results:")
        for item in all_results:
            route_label = item.get("route", "unknown").upper()
            result_text = item.get("result", "")
            context_parts.append(f"\n[{route_label}]\n{result_text}")
    # ─────────────────────────────────────────────────────────────────────────

    context = "\n".join(context_parts)

    llm_messages = [SystemMessage(content=SYSTEM_PROMPT)]

    # Conversation history (last 10 turns)
    history = messages[-10:] if len(messages) > 10 else messages
    llm_messages.extend(history)
    llm_messages.append(HumanMessage(content=context))

    try:
        response = llm.invoke(llm_messages)
        response_text = response.content
    except Exception as e:
        logger.error(f"LLM response generation error: {e}")
        response_text = (
            "I apologize, but I'm having trouble generating a response right now. "
            "Please try again in a moment."
        )

    new_messages = messages + [
        HumanMessage(content=query),
        AIMessage(content=response_text),
    ]

    return {
        **state,
        "messages": new_messages,
        "processing_complete": True,
    }