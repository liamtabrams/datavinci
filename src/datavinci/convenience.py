"""One-call convenience layer: turn a ticker symbol, file, DataFrame, or Series
straight into a styled chart, plus small helpers for saving and showing.

The star is :func:`chart`. ``chart("AAPL")`` fetches real Yahoo Finance data and
draws it; ``chart("prices.csv")`` reads a file; ``chart(df)`` / ``chart(series)``
use data you already have — no network, no extra dependencies. Everything returns
a plain matplotlib ``Axes``, exactly like the lower-level plot functions.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .data import load_ticker
from .timeseries import candlestick, line, moving_average

__all__ = ["chart", "save", "show"]

# File extensions we know how to read directly. A string source with one of these
# suffixes (or that exists on disk) is treated as a file rather than a ticker.
_FILE_SUFFIXES = (".csv", ".tsv", ".parquet", ".json")

_OHLC = ("open", "high", "low", "close")


def _looks_like_file(source: str) -> bool:
    """Decide whether a string source is a file path vs. a ticker symbol."""
    lowered = source.lower()
    if lowered.endswith(_FILE_SUFFIXES):
        return True
    # A path separator or an existing file is a strong file signal; a bare token
    # like "AAPL" is treated as a ticker.
    return os.sep in source or "/" in source or os.path.exists(source)


def _read_file(path: str) -> pd.DataFrame:
    """Read a CSV/TSV/parquet/JSON file into a DataFrame with a datetime index."""
    lowered = path.lower()
    if lowered.endswith(".parquet"):
        return pd.read_parquet(path)
    if lowered.endswith(".json"):
        return pd.read_json(path)
    sep = "\t" if lowered.endswith(".tsv") else ","
    # Assume the first column is the date/index; fall back gracefully if not.
    df = pd.read_csv(path, sep=sep, index_col=0)
    try:
        df.index = pd.to_datetime(df.index)
    except (ValueError, TypeError):
        pass  # Non-datetime index is fine; charts treat it as categories.
    return df


def _normalize_ohlc_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename case-insensitive open/high/low/close columns to the canonical form.

    Real-world CSVs use ``open`` or ``OPEN``; :func:`candlestick` expects
    ``Open``/``High``/``Low``/``Close``. This makes both just work without copying
    the frame unless a rename is actually needed.
    """
    canonical = {"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    rename = {
        col: canonical[col.lower()]
        for col in df.columns
        if isinstance(col, str) and col.lower() in canonical and col != canonical[col.lower()]
    }
    return df.rename(columns=rename) if rename else df


def _has_ohlc(df: pd.DataFrame) -> bool:
    """True if the frame carries all four OHLC columns (case-insensitive)."""
    lowered = {c.lower() for c in df.columns if isinstance(c, str)}
    return all(field in lowered for field in _OHLC)


def _resolve_source(
    source: str | pd.DataFrame | pd.Series,
    period: str,
    interval: str,
) -> tuple[pd.DataFrame | pd.Series, str | None]:
    """Turn any accepted source into (data, inferred_title)."""
    if isinstance(source, pd.Series):
        name = None if source.name is None else str(source.name)
        return source, name
    if isinstance(source, pd.DataFrame):
        return _normalize_ohlc_columns(source), None
    if isinstance(source, str):
        if _looks_like_file(source):
            return _normalize_ohlc_columns(_read_file(source)), None
        # Bare token → ticker symbol. Fetch live and title it with the symbol.
        return _normalize_ohlc_columns(load_ticker(source, period=period, interval=interval)), (
            source.upper()
        )
    raise TypeError(
        "chart() source must be a ticker string, file path, pandas DataFrame, or "
        f"Series — got {type(source).__name__}."
    )


def _resolve_kind(kind: str, data: pd.DataFrame | pd.Series) -> str:
    """Normalize the requested chart kind, resolving 'auto' from the data shape."""
    aliases = {"candlestick": "candle", "ohlc": "candle", "sma": "ma", "movingaverage": "ma"}
    kind = aliases.get(kind.lower(), kind.lower())
    if kind == "auto":
        # OHLC frame → candlestick; anything else → line.
        if isinstance(data, pd.DataFrame) and _has_ohlc(data):
            return "candle"
        return "line"
    if kind not in ("candle", "line", "ma"):
        raise ValueError(
            f"Unknown kind {kind!r}. Use 'auto', 'candle', 'line', or 'ma'."
        )
    return kind


def _close_series(data: pd.DataFrame | pd.Series) -> pd.Series:
    """Extract a single price series (the Close column for OHLC frames)."""
    if isinstance(data, pd.Series):
        return data
    if _has_ohlc(data):
        # _normalize_ohlc_columns has already run, so "Close" is present.
        return data["Close"]
    if data.shape[1] == 1:
        return data.iloc[:, 0]
    raise ValueError(
        "kind='ma' needs a single price series; got a DataFrame with columns "
        f"{list(data.columns)}. Select one column first."
    )


def chart(
    source: str | pd.DataFrame | pd.Series,
    period: str = "1y",
    *,
    kind: str = "auto",
    interval: str = "1d",
    windows: Sequence[int] = (20, 50),
    ax: Axes | None = None,
    title: str | None = None,
    **kwargs,
) -> Axes:
    """Draw a styled chart from a ticker symbol, file, DataFrame, or Series.

    This is the one-call front door to datavinci. It figures out where the data
    comes from, picks a sensible chart type, and applies the active theme.

    Parameters
    ----------
    source:
        One of:

        * A **ticker symbol** like ``"AAPL"`` — fetched live from Yahoo Finance
          (needs network and the ``[finance]`` extra).
        * A **file path** ending in ``.csv``/``.tsv``/``.parquet``/``.json`` — read
          from disk, no network.
        * A **pandas DataFrame** or **Series** you already have.
    period, interval:
        yfinance period/interval strings, used only when ``source`` is a ticker
        symbol (e.g. ``"6mo"``, ``"1d"``).
    kind:
        ``"auto"`` (default) picks candlestick for OHLC data and a line chart
        otherwise. Force it with ``"candle"``, ``"line"``, or ``"ma"`` (price +
        moving averages). ``"candlestick"``/``"ohlc"``/``"sma"`` are accepted aliases.
    windows:
        Moving-average windows, used only when ``kind="ma"``.
    ax, title:
        Optional Axes to draw on and an explicit title. If ``title`` is omitted, a
        ticker source is titled with its symbol.
    **kwargs:
        Forwarded to the underlying plot function (``candlestick`` / ``line`` /
        ``moving_average``).

    Returns
    -------
    matplotlib.axes.Axes

    Examples
    --------
    >>> import datavinci as dv
    >>> dv.chart("AAPL", "6mo")                 # live candles, one line  # doctest: +SKIP
    >>> dv.chart("prices.csv", kind="line")     # from a file            # doctest: +SKIP
    >>> dv.chart(my_df)                         # data you already have  # doctest: +SKIP
    """
    data, inferred_title = _resolve_source(source, period, interval)
    if title is None:
        title = inferred_title
    kind = _resolve_kind(kind, data)

    if kind == "candle":
        if not (isinstance(data, pd.DataFrame) and _has_ohlc(data)):
            raise ValueError(
                "kind='candle' needs OHLC columns (Open/High/Low/Close); the source "
                "doesn't have them. Try kind='line'."
            )
        return candlestick(data, ax=ax, title=title, **kwargs)
    if kind == "ma":
        return moving_average(_close_series(data), windows=windows, ax=ax, title=title, **kwargs)
    return line(data, ax=ax, title=title, **kwargs)


def save(target: Axes | Figure, path: str, *, dpi: int = 110, transparent: bool = False) -> str:
    """Save a chart to ``path`` with the dark theme background preserved.

    matplotlib's default ``savefig`` uses a white canvas, which frames datavinci's
    dark charts in an ugly white border. This helper saves with the figure's own
    face color so exports match what you see.

    Parameters
    ----------
    target:
        An ``Axes`` (as returned by every plot function) or a ``Figure``.
    path:
        Output file path; the extension chooses the format (``.png``, ``.svg``, …).
    dpi:
        Resolution for raster formats.
    transparent:
        If ``True``, save with a transparent background instead of the dark canvas.

    Returns
    -------
    str
        The ``path`` written, for convenience.
    """
    fig = target.figure if isinstance(target, Axes) else target
    fig.savefig(
        path,
        dpi=dpi,
        facecolor="none" if transparent else fig.get_facecolor(),
        bbox_inches="tight",
        transparent=transparent,
    )
    return path


def show() -> None:
    """Display all open figures. A thin passthrough to ``matplotlib.pyplot.show``
    so you don't have to import matplotlib just to see your chart."""
    import matplotlib.pyplot as plt

    plt.show()
