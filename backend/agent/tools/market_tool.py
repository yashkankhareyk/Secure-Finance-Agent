"""
Market Data Tool - Fetches real-time stock/market data using yfinance (FREE).

CHANGED:
- Per-symbol TTL cache (60s for stocks, 5min for indices) avoids hammering Yahoo.
- Exponential backoff with jitter on transient errors (connection reset, timeout).
- Request throttling: minimum gap between yfinance calls to avoid rate-limiting.
- All network errors are caught and return a clean user-facing message.
"""

import time
import random
import logging
from threading import Lock
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simple in-process TTL cache
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, Any]] = {}  # key -> (expires_at, value)
_cache_lock = Lock()

_STOCK_TTL = 60          # seconds — individual stock data
_INDEX_TTL = 300         # seconds — market overview indices
_MIN_REQUEST_GAP = 0.5   # seconds — minimum time between yfinance calls
_last_request_time: float = 0.0
_request_lock = Lock()


def _cache_get(key: str) -> Any | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() < entry[0]:
            return entry[1]
        return None


def _cache_set(key: str, value: Any, ttl: int):
    with _cache_lock:
        _cache[key] = (time.time() + ttl, value)


def _throttle():
    """Ensure minimum gap between outbound yfinance requests."""
    global _last_request_time
    with _request_lock:
        gap = time.time() - _last_request_time
        if gap < _MIN_REQUEST_GAP:
            time.sleep(_MIN_REQUEST_GAP - gap)
        _last_request_time = time.time()


def _fetch_with_backoff(fn, max_retries: int = 3):
    """
    Call fn() with exponential backoff + jitter on transient failures.
    Retries on ConnectionError, TimeoutError, and OSError (connection reset).
    """
    delay = 1.0
    for attempt in range(max_retries):
        try:
            _throttle()
            return fn()
        except (ConnectionError, TimeoutError, OSError) as e:
            if attempt == max_retries - 1:
                raise
            sleep_time = delay + random.uniform(0, 0.5)
            logger.warning(
                f"yfinance transient error (attempt {attempt + 1}/{max_retries}): "
                f"{e} — retrying in {sleep_time:.1f}s"
            )
            time.sleep(sleep_time)
            delay *= 2  # exponential backoff
    return None  # unreachable but satisfies type checkers


def _safe_get(info: dict, key: str, default="N/A"):
    """Safely get a value from dict, treating None as missing."""
    val = info.get(key, default)
    return val if val is not None else default


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

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
    symbol = symbol.upper().strip()
    cache_key = f"stock:{symbol}"

    cached = _cache_get(cache_key)
    if cached:
        logger.debug(f"Cache hit for {symbol}")
        return cached

    try:
        import yfinance as yf

        def _fetch():
            ticker = yf.Ticker(symbol)
            return ticker.info

        info = _fetch_with_backoff(_fetch)

        if not info or info.get("regularMarketPrice") is None:
            # Fallback to fast_info
            try:
                def _fetch_fast():
                    import yfinance as yf
                    return yf.Ticker(symbol).fast_info

                fast = _fetch_with_backoff(_fetch_fast)
                result = (
                    f"**{symbol}**\n"
                    f"- Last Price: ${fast.get('lastPrice', 'N/A')}\n"
                    f"- Market Cap: ${fast.get('marketCap', 'N/A'):,.0f}\n"
                    f"- 52-Week Range: Not available\n"
                    f"\n*Limited data available for this symbol.*"
                )
                _cache_set(cache_key, result, _STOCK_TTL)
                return result
            except Exception:
                return f"Could not find data for symbol '{symbol}'. Please verify the ticker symbol."

        current_price = _safe_get(info, "regularMarketPrice")
        prev_close = _safe_get(info, "previousClose")

        change_str = ""
        if isinstance(current_price, (int, float)) and isinstance(prev_close, (int, float)):
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
            direction = "📈" if change >= 0 else "📉"
            change_str = f"{direction} Change: ${change:+.2f} ({change_pct:+.2f}%)"

        result = f"""**{_safe_get(info, 'longName', symbol)}** ({symbol})

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
        _cache_set(cache_key, result, _STOCK_TTL)
        return result

    except (ConnectionError, TimeoutError, OSError) as e:
        logger.error(f"Network error fetching {symbol} after retries: {e}")
        return (
            f"Unable to fetch data for '{symbol}' due to a network issue. "
            "Please try again in a moment."
        )
    except Exception as e:
        logger.error(f"Market data error for {symbol}: {e}")
        return f"Error fetching data for '{symbol}': {str(e)}. Please check the ticker symbol."


@tool
def get_market_overview() -> str:
    cache_key = "market:overview"
    cached = _cache_get(cache_key)
    if cached:
        logger.debug("Cache hit for market overview")
        return cached

    try:
        import yfinance as yf

        indices = {
            "^GSPC": "S&P 500",
            "^DJI":  "Dow Jones",
            "^IXIC": "NASDAQ",
            "^RUT":  "Russell 2000",
            "^VIX":  "VIX (Volatility)",
        }

        results = ["## 📊 Market Overview\n"]
        successful_fetches = 0   # ← track how many succeeded

        for symbol, name in indices.items():
            try:
                def _fetch(sym=symbol):
                    return yf.Ticker(sym).history(period="2d")

                hist = _fetch_with_backoff(_fetch)

                if len(hist) >= 2:
                    current    = hist["Close"].iloc[-1]
                    previous   = hist["Close"].iloc[-2]
                    change     = current - previous
                    change_pct = (change / previous) * 100
                    direction  = "🟢" if change >= 0 else "🔴"
                    results.append(
                        f"{direction} **{name}**: {current:,.2f} ({change_pct:+.2f}%)"
                    )
                    successful_fetches += 1   # ← count success
                elif len(hist) == 1:
                    current = hist["Close"].iloc[-1]
                    results.append(f"⚪ **{name}**: {current:,.2f}")
                    successful_fetches += 1
                else:
                    results.append(f"⚪ **{name}**: Data unavailable")

            except (ConnectionError, TimeoutError, OSError) as e:
                results.append(f"⚪ **{name}**: Temporarily unavailable")
                logger.warning(f"Network error fetching {name}: {e}")
            except Exception as e:
                results.append(f"⚪ **{name}**: Data unavailable")
                logger.warning(f"Failed to fetch {name}: {e}")

        result = "\n".join(results)

        # ✅ Only cache if at least some data came back successfully
        if successful_fetches > 0:
            _cache_set(cache_key, result, _INDEX_TTL)
        else:
            logger.warning("All market fetches failed — not caching empty result")

        return result

    except Exception as e:
        logger.error(f"Market overview error: {e}")
        return "Unable to fetch market data at this time. Please try again later."
