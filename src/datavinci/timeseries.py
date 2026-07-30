"""Time-series plotting helpers built on top of matplotlib.

Every public function accepts an optional ``ax`` and returns a matplotlib
``Axes``. If you don't pass one, a new figure/axes is created for you. Because
the return value is a plain Axes, you can keep tweaking the result with the full
matplotlib API afterwards. All charts use datavinci's dark "pro terminal" theme
(see ``_theme``): a gradient backdrop, glowing lines, shadowed candles, and
vertical time-span grid lines.
"""

from __future__ import annotations

from collections.abc import Sequence

import matplotlib.dates as mdates
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes

from ._theme import (
    INK,
    add_time_grid,
    glow,
    gradient_fill,
    style_axes,
    style_legend,
    theme_down,
    theme_hollow_down,
    theme_palette,
    theme_up,
)

__all__ = ["line", "candlestick", "moving_average"]


def _new_ax(ax: Axes | None, figsize: tuple[float, float]) -> Axes:
    """Return ``ax`` if given, otherwise create a fresh figure and axes."""
    if ax is not None:
        return ax
    _, ax = plt.subplots(figsize=figsize)
    return ax


def _x_numeric(index: pd.Index) -> tuple[np.ndarray, bool]:
    """Map an index to numeric x values; report whether it is datetime-based."""
    if isinstance(index, pd.DatetimeIndex):
        return mdates.date2num(index.to_pydatetime()), True
    return np.arange(len(index), dtype=float), False


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
    fill: bool = True,
    figsize: tuple[float, float] = (11, 5),
) -> Axes:
    """Plot one or more time series as glowing line charts.

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
    fill:
        For a single series, shade the area beneath it with a gradient.

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

    pal = theme_palette()
    x, is_dt = _x_numeric(frame.index)
    for i, col in enumerate(frame.columns):
        color = pal[i % len(pal)]
        y = frame[col].to_numpy(dtype=float)
        (ln,) = ax.plot(x, y, label=str(col), color=color, linewidth=2.0, solid_capstyle="round")
        ln.set_path_effects(glow(color, base_lw=2.0))

    if is_dt:
        ax.xaxis_date()
    if fill and frame.shape[1] == 1:
        gradient_fill(ax, x, frame.iloc[:, 0].to_numpy(dtype=float), pal[0])

    style_axes(ax, title=title, xlabel=xlabel, ylabel=ylabel)
    add_time_grid(ax, is_dt)
    if legend and frame.shape[1] > 1:
        style_legend(ax, loc="best")
    return ax


def moving_average(
    data: pd.Series | pd.DataFrame,
    windows: Sequence[int] = (20, 50),
    *,
    ax: Axes | None = None,
    price_label: str = "Price",
    title: str | None = None,
    ylabel: str | None = None,
    figsize: tuple[float, float] = (11, 5),
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
    x, is_dt = _x_numeric(series.index)
    y = series.to_numpy()

    pal = theme_palette()
    # Underlying price: bright neutral ink with a gradient fill beneath.
    (price_line,) = ax.plot(x, y, label=price_label, color=INK, linewidth=1.8)
    price_line.set_path_effects(glow(INK, base_lw=1.8, layers=3))
    gradient_fill(ax, x, y, pal[0], alpha=0.28)

    for i, w in enumerate(windows):
        if w < 1:
            raise ValueError(f"Moving-average window must be >= 1, got {w}.")
        color = pal[i % len(pal)]
        sma = series.rolling(window=w, min_periods=1).mean().to_numpy()
        (ln,) = ax.plot(x, sma, label=f"SMA {w}", color=color, linewidth=2.0)
        ln.set_path_effects(glow(color, base_lw=2.0))

    if is_dt:
        ax.xaxis_date()
    style_axes(ax, title=title, ylabel=ylabel)
    add_time_grid(ax, is_dt)
    style_legend(ax, loc="best")
    return ax


def candlestick(
    df: pd.DataFrame,
    *,
    open: str = "Open",
    high: str = "High",
    low: str = "Low",
    close: str = "Close",
    ax: Axes | None = None,
    up_color: str | None = None,
    down_color: str | None = None,
    hollow_down: bool | None = None,
    width: float = 0.7,
    title: str | None = None,
    ylabel: str | None = "Price",
    figsize: tuple[float, float] = (12, 5.5),
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
        Colors for candles that closed up vs. down. Default to the active theme's
        semantic colors (see :func:`datavinci.use_theme`).
    hollow_down:
        Draw down candles as hollow outlines instead of filled bodies. This adds a
        redundant, hue-independent channel so gain/loss is legible under color-vision
        deficiency or in grayscale. Defaults to the active theme (``True`` under the
        ``"colorblind"`` theme, ``False`` otherwise).
    width:
        Candle body width. For a DatetimeIndex this is measured in days.

    Returns
    -------
    matplotlib.axes.Axes
    """
    up_color = theme_up() if up_color is None else up_color
    down_color = theme_down() if down_color is None else down_color
    hollow_down = theme_hollow_down() if hollow_down is None else hollow_down
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

    x, is_dt = _x_numeric(df.index)
    if is_dt:
        ax.xaxis_date()

    up = c >= o

    # High-low wicks, faintly glowing. Wick color still follows direction.
    wick_colors = np.where(up, up_color, down_color)
    wicks = ax.vlines(x, low_arr, h, color=wick_colors, linewidth=1.1, zorder=2)
    wicks.set_path_effects([pe.Stroke(linewidth=3.0, alpha=0.12), pe.Normal()])

    # Open-close bodies. Up candles are filled with a soft drop shadow for a raised,
    # 3D feel. Down candles are filled by default, or drawn as hollow outlines when
    # hollow_down is set — a redundant, hue-independent gain/loss channel that stays
    # legible under color-vision deficiency and in grayscale.
    bottoms = np.minimum(o, c)
    heights = np.abs(c - o)
    bars = ax.bar(x, heights, bottom=bottoms, width=width, align="center", zorder=3)
    shadow = [pe.withSimplePatchShadow(offset=(1.2, -1.2), shadow_rgbFace="#000000", alpha=0.5)]
    for patch, is_up in zip(bars.patches, up):
        if is_up:
            patch.set_facecolor(up_color)
            patch.set_edgecolor(up_color)
            patch.set_linewidth(0.6)
            patch.set_path_effects(shadow)
        elif hollow_down:
            patch.set_facecolor("none")
            patch.set_edgecolor(down_color)
            patch.set_linewidth(1.5)
        else:
            patch.set_facecolor(down_color)
            patch.set_edgecolor(down_color)
            patch.set_linewidth(0.6)
            patch.set_path_effects(shadow)

    style_axes(ax, title=title, ylabel=ylabel)
    add_time_grid(ax, is_dt)
    return ax
