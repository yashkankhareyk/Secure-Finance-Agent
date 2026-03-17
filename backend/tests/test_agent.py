"""Tests for the agent graph."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRouter:
    """Test query routing."""

    def test_rag_routing(self):
        from agent.nodes.router import route_query

        state = {
            "messages": [],
            "current_query": "What is asset allocation?",
            "route": None,
            "tool_results": None,
            "pii_detected": [],
            "security_threats": [],
            "session_id": "test",
            "tools_used": [],
            "processing_complete": False,
        }
        result = route_query(state)
        assert result["route"] == "rag"

    def test_market_routing(self):
        from agent.nodes.router import route_query

        state = {
            "messages": [],
            "current_query": "What is the current stock price of AAPL?",
            "route": None,
            "tool_results": None,
            "pii_detected": [],
            "security_threats": [],
            "session_id": "test",
            "tools_used": [],
            "processing_complete": False,
        }
        result = route_query(state)
        assert result["route"] == "market"

    def test_calculator_routing(self):
        from agent.nodes.router import route_query

        state = {
            "messages": [],
            "current_query": "Calculate compound interest on $10000 at 7% for 10 years",
            "route": None,
            "tool_results": None,
            "pii_detected": [],
            "security_threats": [],
            "session_id": "test",
            "tools_used": [],
            "processing_complete": False,
        }
        result = route_query(state)
        assert result["route"] == "calculator"

    def test_compliance_routing(self):
        from agent.nodes.router import route_query

        state = {
            "messages": [],
            "current_query": "What are the SEC compliance requirements?",
            "route": None,
            "tool_results": None,
            "pii_detected": [],
            "security_threats": [],
            "session_id": "test",
            "tools_used": [],
            "processing_complete": False,
        }
        result = route_query(state)
        assert result["route"] == "compliance"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])