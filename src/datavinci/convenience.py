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

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from ._theme import (
    add_time_grid,
    glow,
    style_axes,
    style_legend,
    theme_down,
    theme_palette,
    theme_up,
)
from .data import load_ticker
from .timeseries import _x_numeric, candlestick, line, moving_average

__all__ = ["chart", "dashboard", "save", "show"]

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
    save: str | None = None,
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
    save:
        If given, also write the chart to this path (via :func:`save`, so the dark
        background is preserved) before returning.
    **kwargs:
        Forwarded to the underlying plot function (``candlestick`` / ``line`` /
        ``moving_average``).

    Returns
    -------
    matplotlib.axes.Axes

    Examples
    --------
    >>> import datavinci as dv
    >>> dv.chart("AAPL", "6mo")                     # live candles           # doctest: +SKIP
    >>> dv.chart("AAPL", save="aapl.png")           # fetch, draw, and save  # doctest: +SKIP
    >>> dv.chart("prices.csv", kind="line")         # from a file            # doctest: +SKIP
    >>> dv.chart(my_df)                             # data you already have  # doctest: +SKIP
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
        ax = candlestick(data, ax=ax, title=title, **kwargs)
    elif kind == "ma":
        ax = moving_average(_close_series(data), windows=windows, ax=ax, title=title, **kwargs)
    else:
        ax = line(data, ax=ax, title=title, **kwargs)

    if save is not None:
        _save_fig(ax, save)
    return ax


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


# Private alias so chart(..., save=...) can call the module function even though
# its `save` parameter shadows the name locally.
_save_fig = save


def show() -> None:
    """Display all open figures. A thin passthrough to ``matplotlib.pyplot.show``
    so you don't have to import matplotlib just to see your chart."""
    import matplotlib.pyplot as plt

    plt.show()


def _human_volume(value: float, _pos=None) -> str:
    """Format a volume tick as e.g. 1.2M / 850K for a compact y-axis."""
    value = float(value)
    for unit in ("", "K", "M", "B"):
        if abs(value) < 1000:
            return f"{value:.0f}{unit}" if unit else f"{value:.0f}"
        value /= 1000
    return f"{value:.0f}T"


def _has_column(df: pd.DataFrame, name: str) -> str | None:
    """Return the actual column matching ``name`` case-insensitively, or None."""
    for col in df.columns:
        if isinstance(col, str) and col.lower() == name.lower():
            return col
    return None


def dashboard(
    source: str | pd.DataFrame,
    period: str = "1y",
    *,
    interval: str = "1d",
    sma: Sequence[int] = (20, 50),
    volume: bool = True,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 8),
    height_ratios: tuple[float, float] = (3, 1),
    save: str | None = None,
) -> Figure:
    """Build a stacked price + volume dashboard from a ticker, file, or DataFrame.

    The top panel is a candlestick chart (optionally with moving-average overlays);
    the bottom panel is a volume bar chart colored by up/down day. The two panels
    share an aligned x-axis. Everything uses the active theme.

    Parameters
    ----------
    source:
        A ticker symbol (fetched live), a file path, or an OHLC DataFrame — same
        rules as :func:`chart`. Must resolve to OHLC data.
    period, interval:
        yfinance strings, used only when ``source`` is a ticker symbol.
    sma:
        Moving-average windows to overlay on the price panel. Pass ``()`` for none.
    volume:
        Show the volume panel. Silently ignored if the data has no ``Volume``
        column (the result is then a single price panel).
    title:
        Title for the price panel. Ticker sources default to their symbol.
    figsize, height_ratios:
        Overall figure size and the price:volume panel height ratio.
    save:
        If given, also write the figure to this path (dark background preserved).

    Returns
    -------
    matplotlib.figure.Figure
        The figure containing the panels. Pass it to :func:`save`, or grab
        ``fig.axes`` to customize further.

    Examples
    --------
    >>> import datavinci as dv
    >>> dv.dashboard("AAPL", "6mo")                 # doctest: +SKIP
    >>> dv.dashboard("AAPL", save="aapl.png")       # doctest: +SKIP
    """
    import matplotlib.pyplot as plt

    data, inferred_title = _resolve_source(source, period, interval)
    if title is None:
        title = inferred_title
    if not (isinstance(data, pd.DataFrame) and _has_ohlc(data)):
        raise ValueError(
            "dashboard() needs OHLC data (Open/High/Low/Close). Use chart() for a "
            "plain line series."
        )

    vol_col = _has_column(data, "Volume") if volume else None
    show_volume = vol_col is not None

    if show_volume:
        fig, (ax_price, ax_vol) = plt.subplots(
            2, 1, sharex=True, figsize=figsize,
            gridspec_kw={"height_ratios": list(height_ratios), "hspace": 0.08},
        )
    else:
        fig, ax_price = plt.subplots(figsize=figsize)
        ax_vol = None

    # --- Price panel: candles + optional SMA overlays -------------------------
    candlestick(data, ax=ax_price, title=title)

    x, is_dt = _x_numeric(data.index)
    if sma:
        pal = theme_palette()
        close = data["Close"].astype(float)
        for i, w in enumerate(sma):
            if w < 1:
                raise ValueError(f"Moving-average window must be >= 1, got {w}.")
            color = pal[i % len(pal)]
            sma_vals = close.rolling(window=w, min_periods=1).mean().to_numpy()
            (ln,) = ax_price.plot(x, sma_vals, color=color, linewidth=1.6, label=f"SMA {w}")
            ln.set_path_effects(glow(color, base_lw=1.6, layers=3))
        style_legend(ax_price, loc="best")

    # --- Volume panel ---------------------------------------------------------
    if show_volume:
        o = data["Open"].to_numpy(dtype=float)
        c = data["Close"].to_numpy(dtype=float)
        up = c >= o
        colors = np.where(up, theme_up(), theme_down())
        ax_vol.bar(x, data[vol_col].to_numpy(dtype=float), width=0.7, color=colors, align="center")
        if is_dt:
            ax_vol.xaxis_date()
        style_axes(ax_vol, ylabel="Volume")
        add_time_grid(ax_vol, is_dt)
        ax_vol.yaxis.set_major_formatter(FuncFormatter(_human_volume))
        # Keep the date labels only on the bottom (shared) axis.
        ax_price.tick_params(labelbottom=False)

    if save is not None:
        _save_fig(fig, save)
    return fig
