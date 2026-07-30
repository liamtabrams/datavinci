"""Shared styling for datavinci's "pro terminal" look.

The aesthetic is a dark trading-terminal theme: a gradient backdrop, glowing
lines, drop-shadowed candles and titles, and both horizontal *and* vertical
(time-span) grid lines. Everything here operates on an existing Axes/Figure —
importing datavinci never mutates global matplotlib rcParams, so your other
plots keep their normal look.
"""

from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.patches import Polygon

# --- Surfaces -----------------------------------------------------------------
BG_TOP = "#182233"      # top of the backdrop gradient (lighter slate)
BG_BOTTOM = "#090c12"   # bottom of the backdrop gradient (near black)
FIG_BG = "#070a0f"      # figure canvas behind the axes
INK = "#e8eef6"         # primary text
INK_MUTED = "#8a97a8"   # axis ticks / secondary text
GRID = "#1d2735"        # horizontal price grid (recessive)
GRID_TIME = "#28374b"   # vertical time-span grid (a touch brighter)

# --- Themes -------------------------------------------------------------------
# A theme bundles the semantic up/down price colors, the categorical accent order,
# and whether candlesticks add a redundant *structural* channel (hollow bodies for
# down candles) so direction survives independent of hue.
#
# Two themes ship:
#   "terminal"   — the default neon look: green up / red down, bright accents.
#   "colorblind" — CVD-safe: blue up / red down (keeps the red=loss convention but
#                  moves "up" off the red-green confusion axis), the skill's
#                  validator-passing categorical order, and hollow down candles so
#                  direction reads even in grayscale.
#
# Every palette below was checked with the dataviz skill's validate_palette.js
# against datavinci's dark surfaces (see CHANGELOG / tests). Categorical order is
# the CVD-safety mechanism, so the sequences are fixed, not cosmetic — reordering
# can break adjacent-pair separation.
THEMES = {
    "terminal": {
        "up": "#26de81",      # green
        "down": "#ff4d5e",    # red
        # Cyan, amber, green, pink, violet, orange. Adjacent-pair CVD sits in the
        # 6-8 "floor" band (pink<->green dE 6.6), which is legal here because line
        # charts always carry a legend (secondary encoding). Prefer "colorblind"
        # when hue must stand alone.
        "palette": ["#38bdf8", "#fbbf24", "#34d399", "#f472b6", "#a78bfa", "#fb923c"],
        "hollow_down": False,
    },
    "colorblind": {
        "up": "#3b9dff",      # blue  (blue<->red CVD dE 24.2, vs 10.5 for green/red)
        "down": "#f2545b",    # red   (keeps the finance "loss = red" convention)
        # Skill-canonical order (blue, orange, aqua, yellow, magenta, green):
        # passes every gate (worst adjacent CVD dE 8.4) on datavinci's dark surface.
        "palette": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"],
        "hollow_down": True,
    },
}

_DEFAULT_THEME = "terminal"
_active_theme = _DEFAULT_THEME


def use_theme(name: str) -> None:
    """Switch the active chart theme for subsequent plots.

    Parameters
    ----------
    name:
        ``"terminal"`` (default neon look) or ``"colorblind"`` (CVD-safe blue/red
        candles with a redundant hollow-body channel and a validator-passing accent
        palette). Raises ``ValueError`` for an unknown name.
    """
    if name not in THEMES:
        raise ValueError(f"Unknown theme {name!r}. Available: {sorted(THEMES)}.")
    global _active_theme
    _active_theme = name


def active_theme() -> str:
    """Return the name of the currently active theme."""
    return _active_theme


def available_themes() -> list[str]:
    """Return the list of built-in theme names."""
    return sorted(THEMES)


def theme_up() -> str:
    """Up/gain color for the active theme."""
    return THEMES[_active_theme]["up"]


def theme_down() -> str:
    """Down/loss color for the active theme."""
    return THEMES[_active_theme]["down"]


def theme_palette() -> list[str]:
    """Categorical accent order for the active theme."""
    return THEMES[_active_theme]["palette"]


def theme_hollow_down() -> bool:
    """Whether the active theme draws down candles hollow (redundant channel)."""
    return THEMES[_active_theme]["hollow_down"]


# Backwards-compatible constants: the *default* theme's values. These do not track
# use_theme() at runtime — the theme_*() accessors do. Kept so external callers
# that imported the raw colors still work.
UP_COLOR = THEMES[_DEFAULT_THEME]["up"]
DOWN_COLOR = THEMES[_DEFAULT_THEME]["down"]
PALETTE = THEMES[_DEFAULT_THEME]["palette"]

_BG_CMAP = LinearSegmentedColormap.from_list("dv_backdrop", [BG_BOTTOM, BG_TOP])


# ------------------------------------------------------------------------------
# Effects
# ------------------------------------------------------------------------------
def text_shadow(offset: tuple[float, float] = (1.4, -1.4), alpha: float = 0.6):
    """Path effect giving text a soft drop shadow for a raised, 3D feel."""
    return [pe.withSimplePatchShadow(offset=offset, shadow_rgbFace="#000000", alpha=alpha)]


def glow(color: str, base_lw: float, layers: int = 4, spread: float = 2.4):
    """Path effects that wrap a line in a soft neon glow of its own color.

    Wide, faint strokes are drawn first (the halo), then the crisp line on top.
    """
    effects = [
        pe.Stroke(linewidth=base_lw + i * spread, foreground=color, alpha=0.05 * i)
        for i in range(layers, 0, -1)
    ]
    effects.append(pe.Normal())
    return effects


def gradient_backdrop(ax: Axes) -> None:
    """Fill the axes with a subtle vertical gradient, behind all data."""
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    grad = np.linspace(0, 1, 256).reshape(-1, 1)
    ax.imshow(
        grad,
        cmap=_BG_CMAP,
        aspect="auto",
        origin="lower",
        extent=(0, 1, 0, 1),
        transform=ax.transAxes,
        zorder=-100,
        interpolation="bilinear",
    )
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)


def gradient_fill(ax: Axes, x: np.ndarray, y: np.ndarray, color: str, alpha: float = 0.38) -> None:
    """Shade the area under ``y`` with a vertical color→transparent gradient."""
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    y = np.asarray(y, dtype=float)
    y_top = float(np.nanmax(y))
    y_base = ylim[0]

    band = np.empty((256, 1, 4))
    band[:, :, :3] = to_rgb(color)
    band[:, :, 3] = np.linspace(0.0, alpha, 256)[:, None]

    im = ax.imshow(
        band,
        aspect="auto",
        origin="lower",
        extent=(float(np.min(x)), float(np.max(x)), y_base, y_top),
        zorder=1,
    )
    verts = np.vstack([[x[0], y_base], np.column_stack([x, y]), [x[-1], y_base]])
    clip = Polygon(verts, closed=True, facecolor="none", edgecolor="none")
    ax.add_patch(clip)
    im.set_clip_path(clip)

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)


# ------------------------------------------------------------------------------
# Axes styling
# ------------------------------------------------------------------------------
def style_axes(
    ax: Axes,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    mono_price_ticks: bool = True,
) -> Axes:
    """Apply the datavinci pro-terminal look to ``ax`` and set optional labels."""
    fig = ax.figure
    fig.set_facecolor(FIG_BG)
    ax.set_facecolor("none")

    # Recessive horizontal (price) grid; vertical grid is added by add_time_grid.
    ax.grid(axis="y", color=GRID, linewidth=0.9, zorder=0)
    ax.set_axisbelow(True)

    # Spines: drop the box, keep a faint baseline.
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(GRID_TIME)
    ax.spines["bottom"].set_linewidth(1.0)

    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(INK_MUTED)
    if mono_price_ticks:
        for lbl in ax.get_yticklabels():
            lbl.set_fontfamily("DejaVu Sans Mono")

    if title:
        t = ax.set_title(title, fontsize=15, fontweight="bold", loc="left", color=INK, pad=12)
        t.set_path_effects(text_shadow())
    if xlabel:
        ax.set_xlabel(xlabel, color=INK_MUTED, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_MUTED, fontsize=10)

    # Backdrop last so it sits behind everything at fixed limits.
    gradient_backdrop(ax)
    return ax


def add_time_grid(ax: Axes, datetime_axis: bool) -> None:
    """Add vertical grid lines marking time spans (months/weeks as they fit)."""
    if datetime_axis:
        locator = mdates.AutoDateLocator(minticks=4, maxticks=9)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.grid(axis="x", color=GRID_TIME, linewidth=0.8, alpha=0.8, zorder=0)
    ax.set_axisbelow(True)


def style_legend(ax: Axes, **kwargs) -> None:
    """Legend styled for the dark surface."""
    leg = ax.legend(
        facecolor="#0d131d",
        edgecolor=GRID_TIME,
        framealpha=0.92,
        labelcolor=INK,
        fontsize=9,
        **kwargs,
    )
    if leg is not None:
        leg.get_frame().set_linewidth(0.8)
