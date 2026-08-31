"""Canned trading strategies (and the indicators behind them) for use with
:func:`datavinci.backtest`.

A **strategy** here is simply a function that takes an OHLC ``DataFrame`` and
returns a ``signal`` Series — the position you want to *hold* on each bar, using
only information available up to and including that bar's close:

    +1  = long   (you profit if the price rises)
     0  = flat   (no position)
    -1  = short  (you profit if the price falls)

The canned strategies below are **long/flat only** (they emit 0 or 1) to keep
things beginner-safe; you can always write your own function that returns -1.

.. important::
   A strategy must **not** peek at the future. Compute the signal from data up to
   the current bar's close and nothing later. :func:`datavinci.backtest` then
   applies a **one-bar delay** — you trade on the *next* bar — so a signal decided
   at today's close can only affect tomorrow's return. That delay is what makes a
   backtest honest; see the ``backtest`` docstring.

Each function below is a *factory*: you configure the parameters once and get back
a reusable strategy function.

    strat = dv.strategies.sma_crossover(fast=20, slow=50)
    result = dv.backtest(df, strat)
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

# A strategy maps an OHLC frame to a per-bar target position Series.
Strategy = Callable[[pd.DataFrame], pd.Series]

__all__ = [
    "sma_crossover",
    "rsi_meanreversion",
    "bollinger_breakout",
    "rsi",
    "bollinger_bands",
]


def _close(df: pd.DataFrame) -> pd.Series:
    """Return the closing-price series, finding the column case-insensitively."""
    for col in df.columns:
        if isinstance(col, str) and col.lower() == "close":
            return df[col].astype(float)
    raise KeyError("Strategy needs a 'Close' column in the DataFrame.")


# ---------------------------------------------------------------------------
# Indicators (also exported — handy on their own)
# ---------------------------------------------------------------------------
def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's), 0–100.

    RSI measures how one-sided recent moves have been. Values near 70+ are often
    called "overbought" and near 30- "oversold". Computed with Wilder's smoothing
    (an exponential moving average of gains vs. losses).
    """
    delta = close.astype(float).diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder smoothing == EMA with alpha = 1/period.
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def bollinger_bands(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands: (middle, upper, lower).

    The middle band is a simple moving average; the upper/lower bands sit
    ``num_std`` rolling standard deviations above/below it. Price poking outside a
    band signals an unusually large move relative to recent volatility.
    """
    close = close.astype(float)
    mid = close.rolling(period, min_periods=period).mean()
    sd = close.rolling(period, min_periods=period).std()
    upper = mid + num_std * sd
    lower = mid - num_std * sd
    return mid, upper, lower


# ---------------------------------------------------------------------------
# Strategy factories
# ---------------------------------------------------------------------------
def sma_crossover(fast: int = 20, slow: int = 50) -> Strategy:
    """Trend-following: be long while the fast SMA is above the slow SMA.

    A classic momentum rule. When the short-term average crosses above the
    long-term average, the trend is deemed "up" and we hold a long position;
    otherwise we sit flat.

    Parameters
    ----------
    fast, slow:
        Lengths of the fast and slow simple moving averages (``fast < slow``).
    """
    if fast >= slow:
        raise ValueError(f"fast ({fast}) must be smaller than slow ({slow}).")

    def strategy(df: pd.DataFrame) -> pd.Series:
        close = _close(df)
        fast_ma = close.rolling(fast, min_periods=fast).mean()
        slow_ma = close.rolling(slow, min_periods=slow).mean()
        # 1 while fast is above slow, else 0. NaNs (warm-up period) -> flat.
        return (fast_ma > slow_ma).astype(float).where(fast_ma.notna() & slow_ma.notna(), 0.0)

    return strategy


def rsi_meanreversion(period: int = 14, low: float = 30.0, high: float = 70.0) -> Strategy:
    """Mean-reversion: buy oversold dips, exit when no longer oversold.

    Go long when RSI drops below ``low`` (the market looks oversold), and return to
    flat once RSI climbs back above ``high``. Between those thresholds the previous
    position is held.

    Parameters
    ----------
    period:
        RSI lookback.
    low, high:
        Entry (oversold) and exit thresholds on the 0–100 RSI scale.
    """

    def strategy(df: pd.DataFrame) -> pd.Series:
        r = rsi(_close(df), period)
        # +1 when oversold, 0 when overbought, hold previous value in between.
        raw = np.where(r < low, 1.0, np.where(r > high, 0.0, np.nan))
        return pd.Series(raw, index=df.index).ffill().fillna(0.0)

    return strategy


def bollinger_breakout(period: int = 20, num_std: float = 2.0) -> Strategy:
    """Breakout: go long when price breaks above the upper band.

    Enter long when the close pushes above the upper Bollinger band (an unusually
    strong up-move), and exit back to flat when the close falls below the middle
    band (the moving average).

    Parameters
    ----------
    period, num_std:
        Bollinger band settings (see :func:`bollinger_bands`).
    """

    def strategy(df: pd.DataFrame) -> pd.Series:
        close = _close(df)
        mid, upper, _lower = bollinger_bands(close, period, num_std)
        # Enter on a break above the upper band; exit when back below the middle.
        raw = np.where(close > upper, 1.0, np.where(close < mid, 0.0, np.nan))
        return pd.Series(raw, index=df.index).ffill().fillna(0.0)

    return strategy
