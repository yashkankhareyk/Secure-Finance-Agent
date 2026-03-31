"""
Agent Graph - Lazy initialization + Neon PostgreSQL connection pool.
Replaces: backend/agent/graph.py

CHANGED:
- build_agent_graph() is no longer called at import time.
- agent_graph is built lazily on first use via get_agent_graph().
- DB connection pool is only created when the graph is first needed.
- Call initialize_agent() explicitly from main.py lifespan() for
  eager startup (recommended) or let it initialize on first request.
"""

import logging
from typing import Optional

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

from agent.state import AgentState
from agent.nodes.router import route_query
from agent.nodes.tool_executor import execute_tools
from agent.nodes.responder import generate_response
from agent.nodes.should_continue import should_continue
from config import settings

logger = logging.getLogger(__name__)

# --- Module-level singletons (populated lazily) ---
_llm_instance: Optional[BaseChatModel] = None
_agent_graph = None  # Built on first use or explicit initialize_agent() call


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def get_llm() -> BaseChatModel:
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


# ---------------------------------------------------------------------------
# Checkpointer — Neon PostgreSQL via ConnectionPool, MemorySaver fallback
# ---------------------------------------------------------------------------

def _build_checkpointer():
    """
    Neon PostgreSQL checkpointer using ConnectionPool.
    ConnectionPool handles reconnections automatically when Neon
    closes idle connections — fixes 'the connection is closed' error.
    Falls back to MemorySaver (no SQLite anywhere).
    """
    db_url = settings.DATABASE_URL

    if not db_url:
        logger.warning("DATABASE_URL not set — falling back to MemorySaver")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    # Neon requires postgresql:// (not asyncpg) and sslmode=require
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "sslmode" not in sync_url:
        sync_url += ("&" if "?" in sync_url else "?") + "sslmode=require"

    try:
        from psycopg_pool import ConnectionPool
        from langgraph.checkpoint.postgres import PostgresSaver

        pool = ConnectionPool(
            conninfo=sync_url,
            min_size=1,
            max_size=5,
            reconnect_timeout=30,
            kwargs={"autocommit": True},  # Required by PostgresSaver
        )

        cp = PostgresSaver(pool)
        cp.setup()  # Creates checkpoint tables in Neon if not present
        logger.info("Using Neon PostgreSQL checkpointer (ConnectionPool)")
        return cp

    except ImportError as e:
        logger.warning(
            f"Missing package: {e}. "
            "Run: pip install 'psycopg[binary]' psycopg-pool langgraph-checkpoint-postgres"
        )
    except Exception as e:
        logger.error(f"Neon PostgreSQL checkpointer failed: {e}")

    logger.warning("Falling back to MemorySaver — no persistence across restarts")
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _build_agent_graph():
    """Build and compile the LangGraph workflow. Called once."""
    workflow = StateGraph(AgentState)

    workflow.add_node("router", route_query)
    workflow.add_node("tools", execute_tools)
    workflow.add_node("responder", generate_response)

    workflow.set_entry_point("router")
    workflow.add_edge("router", "tools")

    workflow.add_conditional_edges(
        "tools",
        should_continue,
        {"tools": "tools", "responder": "responder"},
    )
    workflow.add_edge("responder", END)

    checkpointer = _build_checkpointer()
    graph = workflow.compile(checkpointer=checkpointer)

    cp_type = type(checkpointer).__name__
    logger.info(f"Agent graph compiled with checkpointer: {cp_type}")
    return graph


def get_agent_graph():
    """
    Return the compiled agent graph, building it on first call (lazy init).
    Thread-safe for single-process servers (uvicorn default).
    """
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = _build_agent_graph()
    return _agent_graph


def initialize_agent():
    """
    Eagerly initialize the agent graph.
    Call this from main.py lifespan() so startup errors surface immediately
    rather than on the first request.
    """
    get_agent_graph()
    logger.info("Agent graph initialized successfully")


# ---------------------------------------------------------------------------
# Public run function
# ---------------------------------------------------------------------------

def run_agent(
    query: str,
    session_id: str = "default",
    message_history: Optional[list] = None,
) -> dict:
    initial_state: AgentState = {
        "messages": message_history or [],
        "current_query": query,
        "route": None,
        "remaining_routes": [],
        "tool_results": None,
        "all_tool_results": [],
        "pii_detected": [],
        "security_threats": [],
        "session_id": session_id,
        "tools_used": [],
        "processing_complete": False,
    }

    run_config = {"configurable": {"thread_id": session_id}}

    try:
        final_state = get_agent_graph().invoke(initial_state, config=run_config)
        messages = final_state.get("messages", [])
        response = ""
        if messages:
            last = messages[-1]
            response = last.content if hasattr(last, "content") else str(last)
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
            "response": "I encountered an error processing your request. Please try again.",
            "tools_used": ["error"],
            "route": "error",
            "pii_detected": [],
            "security_threats": [],
            "messages": message_history or [],
            "error": str(e),
        }