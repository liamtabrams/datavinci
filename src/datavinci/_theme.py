"""Small, shared styling helpers so every datavinci chart looks consistent.

Kept intentionally lightweight: we tweak an existing Axes rather than mutating
global matplotlib rcParams, so importing datavinci never changes the look of a
user's other (non-datavinci) plots.
"""

from __future__ import annotations

from matplotlib.axes import Axes

# A compact, colorblind-friendly categorical palette used when a chart needs to
# draw several series. Swap these for your own brand colors as the library grows.
PALETTE = [
    "#4c78a8",  # blue
    "#f58518",  # orange
    "#54a24b",  # green
    "#e45756",  # red
    "#72b7b2",  # teal
    "#b279a2",  # purple
]

# Semantic colors for up/down price candles (green up, red down).
UP_COLOR = "#26a69a"
DOWN_COLOR = "#ef5350"


def style_axes(
    ax: Axes,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    grid: bool = True,
) -> Axes:
    """Apply datavinci's default look to ``ax`` and set optional labels.

    Removes the top/right spines, adds a light horizontal grid, and sets any
    labels that were provided. Returns the same Axes for convenient chaining.
    """
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid:
        ax.grid(axis="y", color="#dddddd", linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", loc="left")
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    return ax
