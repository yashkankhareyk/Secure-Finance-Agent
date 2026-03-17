"""Tests for agent tools."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCalculatorTool:
    """Test financial calculator."""

    def test_compound_interest(self):
        from agent.tools.calculator_tool import financial_calculator

        result = financial_calculator.invoke(
            "Calculate compound interest on 10000 at 7% for 10 years"
        )
        assert "Future Value" in result
        assert "$" in result

    def test_loan_payment(self):
        from agent.tools.calculator_tool import financial_calculator

        result = financial_calculator.invoke(
            "What is the monthly mortgage payment for a 300000 loan at 6.5% for 30 years"
        )
        assert "Monthly Payment" in result

    def test_retirement(self):
        from agent.tools.calculator_tool import financial_calculator

        result = financial_calculator.invoke(
            "How much do I need for retirement with 50000 annual expenses"
        )
        assert "Savings Needed" in result


class TestComplianceTool:
    """Test compliance checker."""

    def test_clean_content(self):
        from agent.tools.compliance_tool import check_compliance

        result = check_compliance.invoke("Diversification is important for managing risk.")
        assert "PASSED" in result

    def test_prohibited_claim(self):
        from agent.tools.compliance_tool import check_compliance

        result = check_compliance.invoke("This is a guaranteed returns investment with no risk.")
        assert "PROHIBITED" in result

    def test_disclaimer_needed(self):
        from agent.tools.compliance_tool import check_compliance

        result = check_compliance.invoke("I recommend buying this stock for tax benefits.")
        assert "DISCLAIMER" in result


class TestMarketTool:
    """Test market data tool."""

    def test_stock_data(self):
        from agent.tools.market_tool import get_stock_data

        result = get_stock_data.invoke("AAPL")
        assert "AAPL" in result or "Apple" in result

    def test_invalid_ticker(self):
        from agent.tools.market_tool import get_stock_data

        result = get_stock_data.invoke("INVALIDTICKER123")
        assert "error" in result.lower() or "could not" in result.lower()

    def test_market_overview(self):
        from agent.tools.market_tool import get_market_overview

        result = get_market_overview.invoke("")
        assert "Market Overview" in result or "S&P" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])