"""
Agent state definition for LangGraph.
Defines the data structure that flows through the agent graph.
"""

from typing import Annotated, TypedDict, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State that flows through the LangGraph agent."""

    # Chat messages (LangGraph handles message accumulation)
    messages: Annotated[list[BaseMessage], add_messages]

    # Current query (sanitized)
    current_query: str

    # Router decision
    route: Optional[str]  # "rag", "market", "calculator", "compliance", "general"

    # Tool results
    tool_results: Optional[dict]

    # Security metadata
    pii_detected: list[dict]
    security_threats: list[dict]

    # Session tracking
    session_id: str

    # Processing metadata
    tools_used: list[str]
    processing_complete: bool