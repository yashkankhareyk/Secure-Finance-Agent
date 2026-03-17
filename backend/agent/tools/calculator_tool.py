"""
Financial Calculator Tool - Performs financial calculations safely.
Uses a restricted Python execution environment.
"""

import math
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# Safe math functions available for calculations
SAFE_MATH = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval(expression: str) -> float:
    """
    Safely evaluate a mathematical expression.
    Only allows basic math operations - no code execution.
    """
    # Block dangerous operations
    forbidden = [
        "import", "exec", "eval", "compile", "open", "file",
        "os.", "sys.", "subprocess", "__", "getattr", "setattr",
        "delattr", "globals", "locals", "dir", "vars",
        "input", "print", "exit", "quit",
    ]

    expr_lower = expression.lower()
    for word in forbidden:
        if word in expr_lower:
            raise ValueError(f"Forbidden operation: {word}")

    # Only allow safe builtins
    try:
        result = eval(expression, {"__builtins__": {}}, SAFE_MATH)
        return float(result)
    except Exception as e:
        raise ValueError(f"Calculation error: {str(e)}")


@tool
def financial_calculator(calculation_request: str) -> str:
    """
    Perform financial calculations including:
    - Compound interest
    - Loan payments
    - Investment returns
    - Portfolio metrics
    - Retirement projections

    Use this tool when the user needs specific financial calculations.

    Args:
        calculation_request: Description of the calculation needed,
            including all numbers and parameters.
    """
    try:
        # Parse common financial calculation types
        request_lower = calculation_request.lower()

        # Try to extract numbers from the request
        import re
        numbers = re.findall(r"[\d,]+\.?\d*", calculation_request)
        numbers = [float(n.replace(",", "")) for n in numbers]

        results = []

        # Compound Interest
        if any(term in request_lower for term in ["compound interest", "future value", "fv"]):
            if len(numbers) >= 3:
                principal = numbers[0]
                rate = numbers[1] / 100 if numbers[1] > 1 else numbers[1]
                years = numbers[2]
                compounds_per_year = numbers[3] if len(numbers) > 3 else 12

                fv = principal * (1 + rate / compounds_per_year) ** (compounds_per_year * years)
                interest_earned = fv - principal

                results.append(f"""
## 💰 Compound Interest Calculation

| Parameter | Value |
|-----------|-------|
| Principal | ${principal:,.2f} |
| Annual Rate | {rate:.2%} |
| Time Period | {years:.0f} years |
| Compounding | {compounds_per_year:.0f}x per year |
| **Future Value** | **${fv:,.2f}** |
| Interest Earned | ${interest_earned:,.2f} |
| Total Return | {(interest_earned/principal)*100:.1f}% |
""")
            else:
                results.append("Need at least: principal amount, annual rate (%), and years.")

        # Monthly Loan/Mortgage Payment
        elif any(term in request_lower for term in ["loan", "mortgage", "monthly payment", "pmt"]):
            if len(numbers) >= 3:
                principal = numbers[0]
                annual_rate = numbers[1] / 100 if numbers[1] > 1 else numbers[1]
                years = numbers[2]
                monthly_rate = annual_rate / 12
                num_payments = int(years * 12)

                if monthly_rate > 0:
                    payment = principal * (monthly_rate * (1 + monthly_rate)**num_payments) / \
                              ((1 + monthly_rate)**num_payments - 1)
                else:
                    payment = principal / num_payments

                total_paid = payment * num_payments
                total_interest = total_paid - principal

                results.append(f"""
## 🏠 Loan Payment Calculation

| Parameter | Value |
|-----------|-------|
| Loan Amount | ${principal:,.2f} |
| Annual Rate | {annual_rate:.2%} |
| Loan Term | {years:.0f} years |
| **Monthly Payment** | **${payment:,.2f}** |
| Total Paid | ${total_paid:,.2f} |
| Total Interest | ${total_interest:,.2f} |
| Interest/Principal Ratio | {(total_interest/principal)*100:.1f}% |
""")
            else:
                results.append("Need: loan amount, annual rate (%), and term (years).")

        # Investment Return / CAGR
        elif any(term in request_lower for term in ["return", "cagr", "growth", "annualized"]):
            if len(numbers) >= 3:
                initial = numbers[0]
                final = numbers[1]
                years = numbers[2]

                if initial > 0 and years > 0:
                    total_return = (final - initial) / initial
                    cagr = (final / initial) ** (1 / years) - 1

                    results.append(f"""
## 📈 Investment Return Analysis

| Metric | Value |
|--------|-------|
| Initial Investment | ${initial:,.2f} |
| Final Value | ${final:,.2f} |
| Time Period | {years:.1f} years |
| Total Return | {total_return:.2%} |
| **CAGR** | **{cagr:.2%}** |
| Profit/Loss | ${final - initial:,.2f} |
""")
            else:
                results.append("Need: initial value, final value, and years.")

        # Retirement savings needed
        elif any(term in request_lower for term in ["retirement", "retire", "savings needed"]):
            if len(numbers) >= 2:
                annual_expense = numbers[0]
                years_in_retirement = numbers[1] if len(numbers) > 1 else 30
                withdrawal_rate = numbers[2] / 100 if len(numbers) > 2 else 0.04

                needed = annual_expense / withdrawal_rate

                results.append(f"""
## 🎯 Retirement Savings Target

| Parameter | Value |
|-----------|-------|
| Annual Expenses | ${annual_expense:,.2f} |
| Years in Retirement | {years_in_retirement:.0f} |
| Safe Withdrawal Rate | {withdrawal_rate:.1%} |
| **Savings Needed** | **${needed:,.2f}** |

*Based on the {withdrawal_rate:.0%} rule. Adjust for inflation and personal circumstances.*
""")
            else:
                results.append("Need at least: annual expenses in retirement.")

        # Generic calculation
        else:
            # Try to evaluate as a math expression
            try:
                # Look for a mathematical expression in the request
                math_expr = re.search(r"[\d\s\+\-\*\/\(\)\.\,\^]+", calculation_request)
                if math_expr:
                    expr = math_expr.group().strip().replace("^", "**").replace(",", "")
                    result = _safe_eval(expr)
                    results.append(f"**Calculation:** `{math_expr.group().strip()}`\n**Result:** {result:,.4f}")
                else:
                    results.append(
                        "I can calculate:\n"
                        "- **Compound Interest**: Give me principal, rate, and years\n"
                        "- **Loan Payments**: Give me loan amount, rate, and term\n"
                        "- **Investment Returns**: Give me initial value, final value, and years\n"
                        "- **Retirement Target**: Give me annual expenses\n"
                        "- **Math expressions**: e.g., '1000 * 1.07 ^ 10'\n\n"
                        "Please provide the numbers and what type of calculation you need."
                    )
            except ValueError as e:
                results.append(f"Calculation error: {str(e)}")

        return "\n".join(results) if results else "Please provide more details for the calculation."

    except Exception as e:
        logger.error(f"Calculator error: {e}")
        return f"Calculation error: {str(e)}. Please check your inputs."