"""
Market Data Tool - Fetches real-time stock/market data using yfinance (FREE).
"""

import logging
from datetime import datetime, timedelta
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _safe_get(info: dict, key: str, default="N/A"):
    """Safely get a value from dict."""
    val = info.get(key, default)
    return val if val is not None else default


@tool
def get_stock_data(symbol: str) -> str:
    """
    Get current stock price, key metrics, and recent performance for a given stock symbol.

    Use this tool when the user asks about:
    - Current stock prices
    - Company financial metrics (P/E ratio, market cap, etc.)
    - Stock performance
    - Dividend information

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'MSFT')
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol.upper().strip())
        info = ticker.info

        if not info or info.get("regularMarketPrice") is None:
            # Try fast_info as fallback
            try:
                fast = ticker.fast_info
                return (
                    f"**{symbol.upper()}**\n"
                    f"- Last Price: ${fast.get('lastPrice', 'N/A')}\n"
                    f"- Market Cap: ${fast.get('marketCap', 'N/A'):,.0f}\n"
                    f"- 52-Week Range: Not available\n"
                    f"\n*Limited data available for this symbol.*"
                )
            except Exception:
                return f"Could not find data for symbol '{symbol}'. Please verify the ticker symbol."

        # Build comprehensive response
        current_price = _safe_get(info, "regularMarketPrice")
        prev_close = _safe_get(info, "previousClose")

        # Calculate change
        change_str = ""
        if isinstance(current_price, (int, float)) and isinstance(prev_close, (int, float)):
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
            direction = "📈" if change >= 0 else "📉"
            change_str = f"{direction} Change: ${change:+.2f} ({change_pct:+.2f}%)"

        result = f"""**{_safe_get(info, 'longName', symbol.upper())}** ({symbol.upper()})

**Current Price:** ${current_price}
{change_str}

**Key Metrics:**
- Market Cap: ${_safe_get(info, 'marketCap', 0):,.0f}
- P/E Ratio (Trailing): {_safe_get(info, 'trailingPE')}
- P/E Ratio (Forward): {_safe_get(info, 'forwardPE')}
- EPS (Trailing): ${_safe_get(info, 'trailingEps')}
- Beta: {_safe_get(info, 'beta')}

**Dividend:**
- Dividend Yield: {_safe_get(info, 'dividendYield', 0):.2%}
- Dividend Rate: ${_safe_get(info, 'dividendRate', 0)}

**52-Week Range:**
- Low: ${_safe_get(info, 'fiftyTwoWeekLow')}
- High: ${_safe_get(info, 'fiftyTwoWeekHigh')}
- 50-Day Average: ${_safe_get(info, 'fiftyDayAverage')}
- 200-Day Average: ${_safe_get(info, 'twoHundredDayAverage')}

**Volume:**
- Current Volume: {_safe_get(info, 'volume', 0):,.0f}
- Avg Volume: {_safe_get(info, 'averageVolume', 0):,.0f}

**Sector:** {_safe_get(info, 'sector')}
**Industry:** {_safe_get(info, 'industry')}
"""
        return result

    except Exception as e:
        logger.error(f"Market data error for {symbol}: {e}")
        return f"Error fetching data for '{symbol}': {str(e)}. Please check the ticker symbol."


@tool
def get_market_overview() -> str:
    """
    Get an overview of major market indices and their current performance.

    Use this tool when the user asks about:
    - Overall market performance
    - Market conditions
    - How the market is doing today
    - Index performance (S&P 500, Dow, Nasdaq)
    """
    try:
        import yfinance as yf

        indices = {
            "^GSPC": "S&P 500",
            "^DJI": "Dow Jones",
            "^IXIC": "NASDAQ",
            "^RUT": "Russell 2000",
            "^VIX": "VIX (Volatility)",
        }

        results = ["## 📊 Market Overview\n"]

        for symbol, name in indices.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2d")

                if len(hist) >= 2:
                    current = hist["Close"].iloc[-1]
                    previous = hist["Close"].iloc[-2]
                    change = current - previous
                    change_pct = (change / previous) * 100
                    direction = "🟢" if change >= 0 else "🔴"

                    results.append(
                        f"{direction} **{name}**: {current:,.2f} "
                        f"({change_pct:+.2f}%)"
                    )
                elif len(hist) == 1:
                    current = hist["Close"].iloc[-1]
                    results.append(f"⚪ **{name}**: {current:,.2f}")
            except Exception as e:
                results.append(f"⚪ **{name}**: Data unavailable")
                logger.warning(f"Failed to fetch {name}: {e}")

        return "\n".join(results)

    except Exception as e:
        logger.error(f"Market overview error: {e}")
        return "Unable to fetch market data at this time. Please try again later."