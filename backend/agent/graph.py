"""
LangGraph Agent - The core orchestration graph.
Connects Router → Tool Executor → Responder in a directed graph.
"""

import logging
from typing import Optional
from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

from agent.state import AgentState
from agent.nodes.router import route_query
from agent.nodes.tool_executor import execute_tools
from agent.nodes.responder import generate_response
from config import settings

logger = logging.getLogger(__name__)

# Module-level LLM instance (lazy initialization)
_llm_instance: Optional[BaseChatModel] = None


def get_llm() -> BaseChatModel:
    """Get or create the LLM instance based on configuration."""
    global _llm_instance

    if _llm_instance is not None:
        return _llm_instance

    config = settings.get_llm_config()
    provider = config["provider"]

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        _llm_instance = ChatOpenAI(
            model=config["model"],
            api_key=config["api_key"],
            temperature=0.3,
            max_tokens=2000,
        )
    elif provider == "openrouter":
        # OpenRouter is interoperable with OpenAI-style clients in many setups.
        # We use the ChatOpenAI wrapper but pass through a custom base URL.
        from langchain_openai import ChatOpenAI
        _llm_instance = ChatOpenAI(
            model=config["model"],
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            temperature=0.3,
            max_tokens=2000,
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        _llm_instance = ChatGroq(
            model=config["model"],
            api_key=config["api_key"],
            temperature=0.3,
            max_tokens=2000,
        )
    elif provider == "ollama":
        from langchain_community.llms import Ollama
        from langchain_community.chat_models import ChatOllama
        _llm_instance = ChatOllama(
            model=config["model"],
            base_url=config["base_url"],
            temperature=0.3,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    logger.info(f"Initialized LLM: {provider}/{config['model']}")
    return _llm_instance


def build_agent_graph() -> StateGraph:
    """
    Build the LangGraph agent workflow.

    Flow:
        START → route_query → execute_tools → generate_response → END
    """
    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("router", route_query)
    workflow.add_node("tools", execute_tools)
    workflow.add_node("responder", generate_response)

    # Define edges (linear flow)
    workflow.set_entry_point("router")
    workflow.add_edge("router", "tools")
    workflow.add_edge("tools", "responder")
    workflow.add_edge("responder", END)

    # Compile the graph
    graph = workflow.compile()
    logger.info("Agent graph compiled successfully")

    return graph


# Create the compiled agent
agent_graph = build_agent_graph()


def run_agent(
    query: str,
    session_id: str = "default",
    message_history: Optional[list] = None,
) -> dict:
    """
    Run the agent with a query.

    Returns:
        {
            "response": str,
            "tools_used": list[str],
            "route": str,
            "pii_detected": list,
            "security_threats": list,
        }
    """
    # Build initial state
    initial_state: AgentState = {
        "messages": message_history or [],
        "current_query": query,
        "route": None,
        "tool_results": None,
        "pii_detected": [],
        "security_threats": [],
        "session_id": session_id,
        "tools_used": [],
        "processing_complete": False,
    }

    try:
        # Run the graph
        final_state = agent_graph.invoke(initial_state)

        # Extract response from messages
        messages = final_state.get("messages", [])
        response = ""
        if messages:
            last_message = messages[-1]
            response = last_message.content if hasattr(last_message, "content") else str(last_message)

        return {
            "response": response,
            "tools_used": final_state.get("tools_used", []),
            "route": final_state.get("route", "unknown"),
            "pii_detected": final_state.get("pii_detected", []),
            "security_threats": final_state.get("security_threats", []),
            "messages": final_state.get("messages", []),
        }

    except Exception as e:
        logger.error(f"Agent execution error: {e}", exc_info=True)
        return {
            "response": (
                "I apologize, but I encountered an error processing your request. "
                "Please try again or rephrase your question."
            ),
            "tools_used": ["error"],
            "route": "error",
            "pii_detected": [],
            "security_threats": [],
            "messages": message_history or [],
            "error": str(e),
        }