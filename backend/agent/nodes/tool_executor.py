"""
Tool Executor Node - Executes the selected tool based on routing decision.
"""

import logging
from agent.state import AgentState
from agent.tools.rag_tool import search_financial_knowledge
from agent.tools.market_tool import get_stock_data, get_market_overview
from agent.tools.calculator_tool import financial_calculator
from agent.tools.compliance_tool import check_compliance

logger = logging.getLogger(__name__)


def execute_tools(state: AgentState) -> AgentState:
    """Execute the appropriate tool based on the routing decision."""
    route = state.get("route", "general")
    query = state.get("current_query", "")
    tools_used = list(state.get("tools_used", []))

    tool_result = None

    try:
        if route == "rag":
            tool_result = search_financial_knowledge.invoke(query)
            tools_used.append("rag_search")

        elif route == "market":
            # Determine if it's a specific stock or market overview
            query_lower = query.lower()

            if any(phrase in query_lower for phrase in [
                "overview", "market today", "how is the market",
                "market doing", "all markets", "indices"
            ]):
                tool_result = get_market_overview.invoke("")
                tools_used.append("market_overview")
            else:
                # Extract ticker symbol
                import re
                # Look for explicit tickers (uppercase, 1-5 chars)
                tickers = re.findall(r'\b([A-Z]{1,5})\b', query)
                # Filter out common English words
                common_words = {
                    "I", "A", "AN", "THE", "IS", "IT", "AT", "IN",
                    "ON", "TO", "OF", "OR", "AND", "FOR", "BY",
                    "IF", "DO", "ME", "MY", "NO", "SO", "UP",
                    "AM", "AS", "BE", "HE", "WE", "US",
                    "PE", "EPS", "ROI", "ETF", "IPO", "CEO",
                }
                tickers = [t for t in tickers if t not in common_words]

                if tickers:
                    results = []
                    for ticker in tickers[:3]:  # Max 3 tickers
                        result = get_stock_data.invoke(ticker)
                        results.append(result)
                        tools_used.append(f"stock_data:{ticker}")
                    tool_result = "\n\n---\n\n".join(results)
                else:
                    tool_result = get_market_overview.invoke("")
                    tools_used.append("market_overview")

        elif route == "calculator":
            tool_result = financial_calculator.invoke(query)
            tools_used.append("calculator")

        elif route == "compliance":
            tool_result = check_compliance.invoke(query)
            tools_used.append("compliance_check")

        else:  # general
            # For general queries, try RAG first for context
            rag_result = search_financial_knowledge.invoke(query)
            if "No relevant information found" not in rag_result:
                tool_result = rag_result
                tools_used.append("rag_search")
            else:
                tool_result = None
                tools_used.append("general_knowledge")

    except Exception as e:
        logger.error(f"Tool execution error ({route}): {e}")
        tool_result = f"I encountered an issue while processing your request. Let me provide general guidance instead."
        tools_used.append(f"error:{route}")

    return {
        **state,
        "tool_results": {"route": route, "result": tool_result},
        "tools_used": tools_used,
    }