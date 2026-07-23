"""Time-series plotting helpers built on top of matplotlib.

Every public function accepts an optional ``ax`` and returns a matplotlib
``Axes``. If you don't pass one, a new figure/axes is created for you. Because
the return value is a plain Axes, you can keep tweaking the result with the full
matplotlib API afterwards.
"""

from __future__ import annotations

from collections.abc import Sequence

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes

from ._theme import DOWN_COLOR, PALETTE, UP_COLOR, style_axes

__all__ = ["line", "candlestick", "moving_average"]


def _new_ax(ax: Axes | None, figsize: tuple[float, float]) -> Axes:
    """Return ``ax`` if given, otherwise create a fresh figure and axes."""
    if ax is not None:
        return ax
    _, ax = plt.subplots(figsize=figsize)
    return ax


def _as_series(data: pd.Series | pd.DataFrame, name: str = "value") -> pd.Series:
    """Coerce a 1-column DataFrame or Series into a Series."""
    if isinstance(data, pd.Series):
        return data
    if isinstance(data, pd.DataFrame):
        if data.shape[1] != 1:
            raise ValueError(
                f"Expected a Series or single-column DataFrame, got "
                f"{data.shape[1]} columns. Select a column first."
            )
        return data.iloc[:, 0]
    raise TypeError(f"Expected a pandas Series or DataFrame, got {type(data).__name__}.")


def line(
    data: pd.Series | pd.DataFrame,
    columns: Sequence[str] | None = None,
    *,
    ax: Axes | None = None,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    legend: bool = True,
    figsize: tuple[float, float] = (10, 5),
) -> Axes:
    """Plot one or more time series as clean line charts.

    Parameters
    ----------
    data:
        A pandas Series, or a DataFrame whose index is the time axis.
    columns:
        For a DataFrame, the subset of columns to draw. Defaults to all columns.
    ax:
        An existing Axes to draw on. A new one is created if omitted.
    title, xlabel, ylabel:
        Optional labels.
    legend:
        Whether to show a legend (only meaningful for multiple series).

    Returns
    -------
    matplotlib.axes.Axes
    """
    ax = _new_ax(ax, figsize)

    if isinstance(data, pd.Series):
        frame = data.to_frame(name=data.name if data.name is not None else "value")
    else:
        frame = data

    if columns is not None:
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            raise KeyError(f"Columns not found in data: {missing}")
        frame = frame[list(columns)]

    for i, col in enumerate(frame.columns):
        ax.plot(
            frame.index,
            frame[col].to_numpy(dtype=float),
            label=str(col),
            color=PALETTE[i % len(PALETTE)],
            linewidth=1.6,
        )

    style_axes(ax, title=title, xlabel=xlabel, ylabel=ylabel)
    if legend and frame.shape[1] > 1:
        ax.legend(frameon=False)
    return ax


def moving_average(
    data: pd.Series | pd.DataFrame,
    windows: Sequence[int] = (20, 50),
    *,
    ax: Axes | None = None,
    price_label: str = "Price",
    title: str | None = None,
    ylabel: str | None = None,
    figsize: tuple[float, float] = (10, 5),
) -> Axes:
    """Plot a series together with one or more simple moving averages (SMA).

    Parameters
    ----------
    data:
        The underlying series (e.g. a closing-price column).
    windows:
        Rolling-window lengths, in observations, for each SMA line.
    price_label:
        Legend label for the raw series.

    Returns
    -------
    matplotlib.axes.Axes
    """
    ax = _new_ax(ax, figsize)
    series = _as_series(data).astype(float)

    ax.plot(series.index, series.to_numpy(), label=price_label, color="#333333", linewidth=1.3)
    for i, w in enumerate(windows):
        if w < 1:
            raise ValueError(f"Moving-average window must be >= 1, got {w}.")
        sma = series.rolling(window=w, min_periods=1).mean()
        ax.plot(
            sma.index,
            sma.to_numpy(),
            label=f"SMA {w}",
            color=PALETTE[i % len(PALETTE)],
            linewidth=1.6,
        )

    style_axes(ax, title=title, ylabel=ylabel)
    ax.legend(frameon=False)
    return ax


def candlestick(
    df: pd.DataFrame,
    *,
    open: str = "Open",
    high: str = "High",
    low: str = "Low",
    close: str = "Close",
    ax: Axes | None = None,
    up_color: str = UP_COLOR,
    down_color: str = DOWN_COLOR,
    width: float = 0.6,
    title: str | None = None,
    ylabel: str | None = "Price",
    figsize: tuple[float, float] = (11, 5),
) -> Axes:
    """Draw an OHLC candlestick chart from a DataFrame of ticker data.

    The DataFrame index is used as the x-axis. A ``DatetimeIndex`` is rendered
    as proper dates; any other index is treated as evenly spaced categories.

    Parameters
    ----------
    df:
        Table containing open/high/low/close columns.
    open, high, low, close:
        Column names for each OHLC field.
    up_color, down_color:
        Colors for candles that closed up vs. down.
    width:
        Candle body width. For a DatetimeIndex this is measured in days.

    Returns
    -------
    matplotlib.axes.Axes
    """
    required = {open, high, low, close}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing OHLC columns: {sorted(missing)}")
    if len(df) == 0:
        raise ValueError("Cannot draw a candlestick chart from an empty DataFrame.")

    ax = _new_ax(ax, figsize)

    o = df[open].to_numpy(dtype=float)
    h = df[high].to_numpy(dtype=float)
    low_arr = df[low].to_numpy(dtype=float)
    c = df[close].to_numpy(dtype=float)

    if isinstance(df.index, pd.DatetimeIndex):
        x = mdates.date2num(df.index.to_pydatetime())
        ax.xaxis_date()
    else:
        x = np.arange(len(df), dtype=float)

    up = c >= o
    colors = np.where(up, up_color, down_color)

    # High-low wicks.
    ax.vlines(x, low_arr, h, color=colors, linewidth=1.0, zorder=2)

    # Open-close bodies. A zero-height (doji) body still shows via the wick.
    bottoms = np.minimum(o, c)
    heights = np.abs(c - o)
    ax.bar(
        x,
        heights,
        bottom=bottoms,
        width=width,
        color=colors,
        edgecolor=colors,
        align="center",
        zorder=3,
    )

    style_axes(ax, title=title, ylabel=ylabel)
    if isinstance(df.index, pd.DatetimeIndex):
        ax.figure.autofmt_xdate()
    return ax
