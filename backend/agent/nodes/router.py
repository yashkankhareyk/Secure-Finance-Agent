"""
Router Node - Determines which tool(s) the agent should use
based on the user's query.
"""

import logging
from agent.state import AgentState
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

# Route definitions
ROUTES = {
    "rag": {
        "description": "Search financial knowledge base",
        "keywords": [
            "what is", "explain", "how does", "tell me about",
            "definition", "strategy", "allocation", "retirement",
            "planning", "diversification", "risk management",
            "fundamentals", "basics", "guide", "learn",
            "fiduciary", "regulation", "compliance", "sec",
            "ira", "401k", "roth", "tax", "bond", "etf",
        ],
    },
    "market": {
        "description": "Get real-time market/stock data",
        "keywords": [
            "stock", "price", "ticker", "market", "nasdaq",
            "s&p", "dow", "share", "trading", "quote",
            "performance", "today", "current", "live",
            "aapl", "googl", "msft", "amzn", "tsla",
            "index", "indices", "overview", "how is the market",
        ],
    },
    "calculator": {
        "description": "Perform financial calculations",
        "keywords": [
            "calculate", "computation", "how much", "what would",
            "interest", "compound", "payment", "mortgage", "loan",
            "return", "cagr", "roi", "yield", "project",
            "if i invest", "how long", "how many years",
            "monthly payment", "future value", "present value",
        ],
    },
    "compliance": {
        "description": "Check regulatory compliance",
        "keywords": [
            "compliance", "regulation", "legal", "allowed",
            "prohibited", "sec rule", "finra", "fiduciary",
            "suitability", "disclosure", "is it legal",
            "can i", "rules about", "requirement",
        ],
    },
}


def route_query(state: AgentState) -> AgentState:
    """
    Analyze the query and determine which tool to route to.
    Uses keyword matching for fast, deterministic routing.
    Falls back to 'general' for conversational queries.
    """
    query = state.get("current_query", "")
    query_lower = query.lower()

    # Score each route
    scores = {}
    for route_name, route_info in ROUTES.items():
        score = sum(1 for kw in route_info["keywords"] if kw in query_lower)
        scores[route_name] = score

    # Get the highest scoring route
    if scores:
        best_route = max(scores, key=scores.get)
        best_score = scores[best_route]

        if best_score > 0:
            selected_route = best_route
        else:
            selected_route = "general"
    else:
        selected_route = "general"

    # Special case: if query mentions a ticker symbol pattern (1-5 uppercase letters)
    import re
    if re.search(r'\b[A-Z]{1,5}\b', query) and selected_route == "general":
        # Could be a stock ticker
        if any(word in query_lower for word in ["price", "stock", "how is", "what about"]):
            selected_route = "market"

    # Special case: market overview queries
    if any(phrase in query_lower for phrase in [
        "market overview", "how is the market", "market today",
        "market doing", "markets today"
    ]):
        selected_route = "market"

    logger.info(f"Routed query to: {selected_route} (scores: {scores})")

    return {
        **state,
        "route": selected_route,
    }