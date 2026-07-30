"""Data helpers: generate synthetic OHLC data and (optionally) load real tickers.

``sample_ohlc`` needs no network and is used by the test suite, so the package
is always testable offline. ``load_ticker`` is a thin, lazily-imported wrapper
around yfinance for when you want real Yahoo Finance data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["sample_ohlc", "load_ticker"]


def sample_ohlc(
    periods: int = 180,
    *,
    start: str = "2023-01-01",
    freq: str = "B",
    start_price: float = 100.0,
    volatility: float = 0.02,
    seed: int | None = 0,
) -> pd.DataFrame:
    """Generate a synthetic OHLC ticker table via a geometric random walk.

    Handy for demos and tests without hitting the network. The result mirrors
    the shape of Yahoo Finance data: a ``DatetimeIndex`` and Open/High/Low/Close
    columns.

    Parameters
    ----------
    periods:
        Number of rows (trading days) to generate.
    start, freq:
        Passed to ``pandas.date_range`` for the index. ``"B"`` is business days.
    start_price:
        Price on the first day.
    volatility:
        Approximate per-step standard deviation of returns.
    seed:
        Seed for reproducibility. Pass ``None`` for fresh randomness each call.

    Returns
    -------
    pandas.DataFrame
        Columns: ``Open``, ``High``, ``Low``, ``Close``, ``Volume`` — matching the
        shape of Yahoo Finance data.
    """
    if periods < 1:
        raise ValueError(f"periods must be >= 1, got {periods}.")

    rng = np.random.default_rng(seed)
    index = pd.date_range(start=start, periods=periods, freq=freq)

    # Daily close prices as a geometric random walk.
    returns = rng.normal(loc=0.0005, scale=volatility, size=periods)
    close = start_price * np.exp(np.cumsum(returns))

    # Open near the prior close; high/low straddle the open-close range.
    prev_close = np.concatenate([[start_price], close[:-1]])
    open_ = prev_close * (1 + rng.normal(0, volatility / 2, size=periods))
    body_high = np.maximum(open_, close)
    body_low = np.minimum(open_, close)
    high = body_high * (1 + np.abs(rng.normal(0, volatility / 2, size=periods)))
    low = body_low * (1 - np.abs(rng.normal(0, volatility / 2, size=periods)))

    # Volume: a base level that swells on bigger moves, with lognormal noise so it
    # is always positive and occasionally spikes — like real turnover.
    move = np.abs(returns) / volatility  # ~1 on an average day
    volume = 1_000_000 * (0.6 + 0.8 * move) * rng.lognormal(0, 0.3, size=periods)

    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume.round().astype(int),
        },
        index=index,
    )


def load_ticker(
    symbol: str,
    *,
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Download OHLC data for ``symbol`` from Yahoo Finance.

    Requires the optional ``yfinance`` dependency::

        pip install "datavinci[finance]"

    Parameters
    ----------
    symbol:
        Ticker symbol, e.g. ``"AAPL"``.
    period:
        yfinance period string (e.g. ``"1mo"``, ``"1y"``, ``"max"``).
    interval:
        yfinance interval string (e.g. ``"1d"``, ``"1h"``).

    Returns
    -------
    pandas.DataFrame
        Standard Open/High/Low/Close/Volume columns with a DatetimeIndex.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - exercised only without extra
        raise ImportError(
            "load_ticker requires yfinance. Install it with:\n"
            '    pip install "datavinci[finance]"'
        ) from exc

    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty:
        raise ValueError(
            f"No data returned for symbol {symbol!r} (period={period!r}, "
            f"interval={interval!r}). Check the symbol and your connection."
        )
    return df
