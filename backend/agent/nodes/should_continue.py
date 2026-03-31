"""
Fix 3 — Conditional edge: loop tools or proceed to responder
New file: backend/agent/nodes/should_continue.py
"""

from agent.state import AgentState


def should_continue(state: AgentState) -> str:
    """
    If there are more routes in the plan → loop back to tools.
    Otherwise → hand off to the responder.
    """
    remaining = state.get("remaining_routes", [])
    return "tools" if remaining else "responder"