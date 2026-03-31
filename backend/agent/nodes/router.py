"""
Fix 3 — Multi-tool router
Replaces: backend/agent/nodes/router.py
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

# Patterns where multiple tools are almost always needed
MULTI_TOOL_PATTERNS = [
    (["market", "rag"],       ["price", "what", "why", "explain", "good", "reasonable", "valuation"]),
    (["calculator", "rag"],   ["calculate", "compound", "loan", "how much", "what is", "explain"]),
    (["compliance", "rag"],   ["legal", "regulation", "allowed", "what is", "explain"]),
    (["market", "compliance"],["stock", "trading", "investment", "legal", "allowed"]),
]


def _score_routes(query_lower: str) -> dict[str, int]:
    return {
        route: sum(1 for kw in keywords if kw in query_lower)
        for route, keywords in ROUTE_KEYWORDS.items()
    }


def _has_ticker(query: str) -> bool:
    return bool(re.search(r'\b[A-Z]{2,5}\b', query))


def route_query(state: AgentState) -> AgentState:
    """Build an ordered multi-tool execution plan for this query."""
    query = state.get("current_query", "")
    query_lower = query.lower()
    scores = _score_routes(query_lower)

    ranked = sorted(
        [(route, score) for route, score in scores.items() if score > 0],
        key=lambda x: x[1],
        reverse=True,
    )
    primary_routes = [r for r, _ in ranked]

    if _has_ticker(query) and "market" not in primary_routes:
        primary_routes.insert(0, "market")

    # Check multi-tool pattern boosts
    for combo, trigger_words in MULTI_TOOL_PATTERNS:
        trigger_hits = sum(1 for w in trigger_words if w in query_lower)
        if trigger_hits >= 2:
            merged = list(dict.fromkeys(combo + primary_routes))
            primary_routes = merged[:3]
            break

    if not primary_routes:
        primary_routes = ["rag"]

    primary_routes = primary_routes[:3]  # max 3 tools per query

    logger.info(f"Multi-tool plan: {primary_routes} (scores: {scores})")

    return {
        **state,
        "route": primary_routes[0],
        "remaining_routes": primary_routes,
    }