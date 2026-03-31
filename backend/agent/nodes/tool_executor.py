"""
Fix 3 — Multi-step tool executor
Replaces: backend/agent/nodes/tool_executor.py
"""

import re
import logging
from agent.state import AgentState
from agent.tools.rag_tool import search_financial_knowledge
from agent.tools.market_tool import get_stock_data, get_market_overview
from agent.tools.calculator_tool import financial_calculator
from agent.tools.compliance_tool import check_compliance

logger = logging.getLogger(__name__)

_COMMON_WORDS = {
    "I", "A", "AN", "THE", "IS", "IT", "AT", "IN", "ON", "TO", "OF",
    "OR", "AND", "FOR", "BY", "IF", "DO", "ME", "MY", "NO", "SO", "UP",
    "AM", "AS", "BE", "HE", "WE", "US", "PE", "EPS", "ROI", "ETF", "IPO", "CEO",
}


def _run_tool(route: str, query: str, tools_used: list) -> str | None:
    if route == "rag":
        tools_used.append("rag_search")
        return search_financial_knowledge.invoke(query)

    elif route == "market":
        query_lower = query.lower()
        if any(p in query_lower for p in ["overview", "market today", "how is the market", "indices"]):
            tools_used.append("market_overview")
            return get_market_overview.invoke("")
        tickers = [t for t in re.findall(r'\b([A-Z]{1,5})\b', query) if t not in _COMMON_WORDS]
        if tickers:
            results = []
            for ticker in tickers[:3]:
                results.append(get_stock_data.invoke(ticker))
                tools_used.append(f"stock_data:{ticker}")
            return "\n\n---\n\n".join(results)
        tools_used.append("market_overview")
        return get_market_overview.invoke("")

    elif route == "calculator":
        tools_used.append("calculator")
        return financial_calculator.invoke(query)

    elif route == "compliance":
        tools_used.append("compliance_check")
        return check_compliance.invoke(query)

    return None


def execute_tools(state: AgentState) -> AgentState:
    """Pop the next route from remaining_routes and execute its tool."""
    remaining = list(state.get("remaining_routes", [state.get("route", "rag")]))
    query = state.get("current_query", "")
    tools_used = list(state.get("tools_used", []))
    prior_results: list[dict] = list(state.get("all_tool_results", []))

    if not remaining:
        return {**state, "remaining_routes": [], "all_tool_results": prior_results}

    current_route = remaining.pop(0)

    try:
        result = _run_tool(current_route, query, tools_used)
    except Exception as e:
        logger.error(f"Tool execution error ({current_route}): {e}")
        result = f"[Tool error on {current_route}: {e}]"
        tools_used.append(f"error:{current_route}")

    if result:
        prior_results.append({"route": current_route, "result": result})

    return {
        **state,
        "route": current_route,
        "remaining_routes": remaining,
        "tool_results": {"route": current_route, "result": result},
        "all_tool_results": prior_results,
        "tools_used": tools_used,
    }