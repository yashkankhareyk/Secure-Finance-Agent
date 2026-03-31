"""
Fix 3 — Multi-Step Tool Chaining
Replaces: backend/agent/nodes/tool_executor.py  AND  backend/agent/nodes/router.py
AND adds:  backend/agent/nodes/should_continue.py

The original agent picks ONE tool and stops.
This fix allows the agent to chain tools:
    e.g. "What is the P/E of AAPL and is that a reasonable valuation?"
         → market_tool (get AAPL data) → rag_tool (explain P/E valuation) → responder

How it works:
  • router.py now returns a *list* of intended routes (multi-tool plan)
  • tool_executor.py iterates through remaining_routes, pops one per invocation
  • should_continue.py is a conditional edge: if remaining_routes is non-empty → loop
    back to tool_executor, otherwise → responder

Wire the new conditional edge in graph.py (see bottom of this file).
"""

# ════════════════════════════════════════════════════════════════════
# FILE 1 of 3:  backend/agent/nodes/router.py  (REPLACE original)
# ════════════════════════════════════════════════════════════════════

ROUTER_CODE = '''
"""
Router Node — now returns a priority-ordered list of routes (multi-tool plan).
"""

import re
import logging
from agent.state import AgentState

logger = logging.getLogger(__name__)

ROUTE_KEYWORDS = {
    "market": [
        "stock", "price", "ticker", "market", "nasdaq", "s&p", "dow",
        "share", "trading", "quote", "today", "current", "live", "index",
        "aapl", "googl", "msft", "amzn", "tsla", "how is the market",
    ],
    "calculator": [
        "calculate", "how much", "what would", "interest", "compound",
        "payment", "mortgage", "loan", "return", "cagr", "roi", "yield",
        "if i invest", "monthly payment", "future value", "present value",
    ],
    "compliance": [
        "compliance", "regulation", "legal", "allowed", "prohibited",
        "sec rule", "finra", "fiduciary", "suitability", "disclosure",
        "is it legal", "can i legally", "rules about",
    ],
    "rag": [
        "what is", "explain", "how does", "tell me about", "definition",
        "strategy", "allocation", "retirement", "planning", "diversification",
        "risk management", "fundamentals", "guide", "learn", "ira", "401k",
        "roth", "tax", "bond", "etf", "should i", "recommend",
    ],
}

# Combinations that always benefit from multiple tools
MULTI_TOOL_PATTERNS = [
    # stock question + explanation → market + rag
    (["market", "rag"],  ["price", "what", "why", "explain", "good", "reasonable", "valuation"]),
    # calculation + explanation → calculator + rag
    (["calculator", "rag"], ["calculate", "compound", "loan", "how much", "what is", "explain"]),
    # compliance + rag context
    (["compliance", "rag"], ["legal", "regulation", "allowed", "what is", "explain"]),
    # market data + compliance check
    (["market", "compliance"], ["stock", "trading", "investment", "legal", "allowed"]),
]


def _score_routes(query_lower: str) -> dict[str, int]:
    scores = {}
    for route, keywords in ROUTE_KEYWORDS.items():
        scores[route] = sum(1 for kw in keywords if kw in query_lower)
    return scores


def _has_ticker(query: str) -> bool:
    return bool(re.search(r"\\b[A-Z]{1,5}\\b", query))


def route_query(state: AgentState) -> AgentState:
    """
    Analyse query and build an ordered list of tools to invoke.
    Stored in state["remaining_routes"] (new field).
    """
    query = state.get("current_query", "")
    query_lower = query.lower()
    scores = _score_routes(query_lower)

    # Build ranked list of routes with score > 0
    ranked = sorted(
        [(route, score) for route, score in scores.items() if score > 0],
        key=lambda x: x[1],
        reverse=True,
    )
    primary_routes = [r for r, _ in ranked]

    # Override: explicit ticker always adds market to front
    if _has_ticker(query) and "market" not in primary_routes:
        primary_routes.insert(0, "market")

    # Check multi-tool pattern boosts
    for combo, trigger_words in MULTI_TOOL_PATTERNS:
        trigger_hits = sum(1 for w in trigger_words if w in query_lower)
        if trigger_hits >= 2:
            # Ensure both routes are present in order
            merged = list(dict.fromkeys(combo + primary_routes))  # combo first, deduped
            primary_routes = merged[:3]   # cap at 3 tools per query
            break

    # Fallback
    if not primary_routes:
        primary_routes = ["rag"]   # RAG as sensible default for finance questions

    # Cap at 3 to avoid runaway chaining
    primary_routes = primary_routes[:3]

    logger.info(f"Multi-tool plan: {primary_routes} (scores: {scores})")

    return {
        **state,
        "route": primary_routes[0],            # keep for backward compat
        "remaining_routes": primary_routes,    # full plan
    }
'''

# ════════════════════════════════════════════════════════════════════
# FILE 2 of 3:  backend/agent/nodes/tool_executor.py  (REPLACE original)
# ════════════════════════════════════════════════════════════════════

TOOL_EXECUTOR_CODE = '''
"""
Tool Executor Node — pops one route from remaining_routes and executes it.
Accumulates results across multiple invocations.
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
        result = search_financial_knowledge.invoke(query)
        tools_used.append("rag_search")
        return result

    elif route == "market":
        query_lower = query.lower()
        if any(p in query_lower for p in ["overview", "market today", "how is the market", "indices"]):
            tools_used.append("market_overview")
            return get_market_overview.invoke("")
        else:
            tickers = [t for t in re.findall(r"\\b([A-Z]{1,5})\\b", query) if t not in _COMMON_WORDS]
            if tickers:
                results = []
                for ticker in tickers[:3]:
                    results.append(get_stock_data.invoke(ticker))
                    tools_used.append(f"stock_data:{ticker}")
                return "\\n\\n---\\n\\n".join(results)
            else:
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

    # Accumulated results from previous tool calls (if chaining)
    prior_results: list[dict] = list(state.get("all_tool_results", []))

    if not remaining:
        return {**state, "remaining_routes": [], "all_tool_results": prior_results}

    # Pop the first route
    current_route = remaining.pop(0)

    try:
        result = _run_tool(current_route, query, tools_used)
    except Exception as e:
        logger.error(f"Tool execution error ({current_route}): {e}")
        result = f"[Tool error on {current_route}: {e}]"
        tools_used.append(f"error:{current_route}")

    if result:
        prior_results.append({"route": current_route, "result": result})

    # Keep backward-compat tool_results pointing to the latest result
    latest_tool_results = {"route": current_route, "result": result}

    return {
        **state,
        "route": current_route,
        "remaining_routes": remaining,
        "tool_results": latest_tool_results,
        "all_tool_results": prior_results,
        "tools_used": tools_used,
    }
'''

# ════════════════════════════════════════════════════════════════════
# FILE 3 of 3:  backend/agent/nodes/should_continue.py  (NEW FILE)
# ════════════════════════════════════════════════════════════════════

SHOULD_CONTINUE_CODE = '''
"""
Conditional edge function for the LangGraph multi-tool loop.
"""

from agent.state import AgentState


def should_continue(state: AgentState) -> str:
    """
    Returns "tools" if there are more routes to execute,
    otherwise "responder" to generate the final answer.
    """
    remaining = state.get("remaining_routes", [])
    return "tools" if remaining else "responder"
'''

# ════════════════════════════════════════════════════════════════════
# GRAPH WIRING — replace build_agent_graph() in graph.py with this:
# ════════════════════════════════════════════════════════════════════

GRAPH_WIRING_SNIPPET = '''
# In graph.py — replace build_agent_graph():

from agent.nodes.should_continue import should_continue

def build_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("router", route_query)
    workflow.add_node("tools", execute_tools)
    workflow.add_node("responder", generate_response)

    workflow.set_entry_point("router")
    workflow.add_edge("router", "tools")

    # ← CHANGED: conditional loop instead of fixed edge
    workflow.add_conditional_edges(
        "tools",
        should_continue,
        {"tools": "tools", "responder": "responder"},
    )
    workflow.add_edge("responder", END)

    checkpointer = _build_checkpointer()
    graph = workflow.compile(checkpointer=checkpointer) if checkpointer else workflow.compile()
    return graph
'''

# ════════════════════════════════════════════════════════════════════
# UPDATED STATE — add remaining_routes and all_tool_results fields
# ════════════════════════════════════════════════════════════════════

STATE_ADDITION = '''
# In agent/state.py — add these two fields to AgentState:

    # Multi-tool chaining (Fix 3)
    remaining_routes: list[str]      # routes still to be executed this turn
    all_tool_results: list[dict]     # accumulated results from all tools this turn
'''

# ════════════════════════════════════════════════════════════════════
# UPDATED RESPONDER — use all_tool_results instead of tool_results
# ════════════════════════════════════════════════════════════════════

RESPONDER_SNIPPET = '''
# In responder.py — replace the context_parts block:

    all_results = state.get("all_tool_results") or []
    if not all_results:
        # Backward compat: single tool_results
        tr = state.get("tool_results", {})
        if tr and tr.get("result"):
            all_results = [tr]

    if all_results:
        context_parts.append("\\nTool Results:")
        for item in all_results:
            context_parts.append(f"\\n[{item[\'route\'].upper()}]\\n{item[\'result\']}")
'''


if __name__ == "__main__":
    print("Fix 3 code snippets. See comments above for which file each belongs to.")
    print("\\n--- router.py ---")
    print(ROUTER_CODE)
    print("\\n--- tool_executor.py ---")
    print(TOOL_EXECUTOR_CODE)
    print("\\n--- should_continue.py ---")
    print(SHOULD_CONTINUE_CODE)