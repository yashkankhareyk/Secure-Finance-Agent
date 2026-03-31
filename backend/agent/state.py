"""
Fix 3 — Updated AgentState
Replaces: backend/agent/state.py
Adds: remaining_routes, all_tool_results
"""

from typing import Annotated, TypedDict, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State that flows through the LangGraph agent."""

    # Chat messages
    messages: Annotated[list[BaseMessage], add_messages]

    # Current query (sanitized)
    current_query: str

    # Primary route for this invocation (backward compat)
    route: Optional[str]

    # Fix 3: ordered list of remaining tools to call this turn
    remaining_routes: list[str]

    # Single tool result (backward compat, latest tool only)
    tool_results: Optional[dict]

    # Fix 3: accumulated results from ALL tools called this turn
    all_tool_results: list[dict]

    # Security metadata
    pii_detected: list[dict]
    security_threats: list[dict]

    # Session tracking
    session_id: str

    # Processing metadata
    tools_used: list[str]
    processing_complete: bool