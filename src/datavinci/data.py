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
    start: str | None = None,
    end: str | None = None,
    retries: int = 3,
    source: str = "yahoo",
) -> pd.DataFrame:
    """Download OHLC data for ``symbol`` from Yahoo Finance or Stooq.

    Requires the optional dependencies::

        pip install "datavinci[finance]"

    Parameters
    ----------
    symbol:
        Ticker symbol, e.g. ``"AAPL"``.
    period:
        Period string. Must be one of ``1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y,
        ytd, max`` — note there is **no** ``20y``; for longer windows pass
        ``start=`` (e.g. ``start="2005-01-01"``) or ``period="max"``. Ignored when
        ``start`` is given.
    interval:
        Bar interval (e.g. ``"1d"``). Only ``"1d"`` is supported by the Stooq source.
    start, end:
        Optional ``YYYY-MM-DD`` date range. When ``start`` is given it takes
        precedence over ``period`` — the reliable way to get many years.
    retries:
        How many times to retry a request that fails or comes back empty. Yahoo
        rate-limits bursts of requests, so a valid symbol can transiently return
        no data (yfinance then wrongly reports "possibly delisted"); retrying with
        a short backoff fixes that.
    source:
        ``"yahoo"`` (default, via yfinance) or ``"stooq"``. **Stooq** is a good,
        key-free alternative when Yahoo is throttling or yfinance is broken against
        Yahoo's API (the classic ``Expecting value: line 1 column 1`` error); it
        serves daily US data via a simple CSV endpoint and needs no extra package.

    Returns
    -------
    pandas.DataFrame
        Standard Open/High/Low/Close/Volume columns with a DatetimeIndex.
    """
    valid_periods = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
    if start is None and period not in valid_periods:
        raise ValueError(
            f"Invalid period {period!r}. Valid periods are {sorted(valid_periods)}. "
            "For a longer window (e.g. 20 years), pass start='YYYY-MM-DD' or period='max'."
        )

    if source == "stooq":
        return _load_stooq(symbol, start=start, end=end, period=period)
    if source != "yahoo":
        raise ValueError(f"Unknown source {source!r}. Use 'yahoo' or 'stooq'.")

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - exercised only without extra
        raise ImportError(
            "load_ticker requires yfinance. Install it with:\n"
            '    pip install "datavinci[finance]"'
        ) from exc

    import time

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(symbol)
            if start is not None:
                df = ticker.history(start=start, end=end, interval=interval)
            else:
                df = ticker.history(period=period, interval=interval)
            if not df.empty:
                return df
            last_error = ValueError("empty response")
        except Exception as exc:  # transient network / rate-limit errors
            last_error = exc
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))  # simple backoff between attempts

    raise ValueError(
        f"No data returned for symbol {symbol!r} after {retries} attempts "
        f"(period={period!r}, start={start!r}, interval={interval!r}). This is often "
        f"Yahoo rate-limiting or an outdated yfinance (try `pip install -U yfinance`), "
        f"not a bad symbol. You can also switch data source: load_ticker(..., "
        f'source="stooq"). Last error: {last_error}'
    )


def _period_to_start(period: str) -> str | None:
    """Approximate a start date for a period string (for the Stooq source)."""
    if period in (None, "max"):
        return None
    unit = period[-1] if period[-2:] != "mo" else "mo"
    try:
        num = int(period[: -len(unit)] or 0)
    except ValueError:
        return None
    today = pd.Timestamp.today().normalize()
    offset = {
        "d": pd.Timedelta(days=num),
        "mo": pd.DateOffset(months=num),
        "y": pd.DateOffset(years=num),
    }.get(unit)
    return None if offset is None else (today - offset).strftime("%Y-%m-%d")


def _load_stooq(
    symbol: str, *, start: str | None, end: str | None, period: str
) -> pd.DataFrame:
    """Fetch daily OHLC data from Stooq's free CSV endpoint (no API key).

    Stooq expects US tickers suffixed with ``.us`` (e.g. ``aapl.us``) and returns a
    CSV with Date/Open/High/Low/Close/Volume, oldest first once sorted.
    """
    s = symbol.lower()
    if "." not in s:
        s += ".us"  # Stooq's convention for US-listed symbols
    if start is None:
        start = _period_to_start(period)

    url = f"https://stooq.com/q/d/l/?s={s}&i=d"
    if start:
        url += f"&d1={start.replace('-', '')}"
    if end:
        url += f"&d2={end.replace('-', '')}"

    df = pd.read_csv(url)
    # A bad symbol / empty range returns a one-cell "No data" frame, not OHLC.
    if df.empty or "Date" not in df.columns:
        raise ValueError(
            f"No Stooq data for {symbol!r} (requested {s}). Check the symbol; Stooq "
            "covers US stocks and major markets, daily bars only."
        )
    df.index = pd.to_datetime(df["Date"])
    df.index.name = None
    df = df.sort_index()
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    return df[cols]
