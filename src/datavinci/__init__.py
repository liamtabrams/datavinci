"""datavinci — a friendly matplotlib wrapper for time-series and financial charts.

The package aims to turn common, fiddly matplotlib recipes (candlesticks, moving
averages, cleanly styled line charts) into one-line calls that return a normal
matplotlib ``Axes`` so you can keep customizing however you like.

Quick start
-----------
The one-call front door — name a ticker and get a chart (fetches live data):

>>> import datavinci as dv
>>> ax = dv.chart("AAPL", "6mo")           # doctest: +SKIP

``chart`` also accepts a file path, a DataFrame, or a Series, so it works fully
offline too. The lower-level ``candlestick`` / ``line`` / ``moving_average``
functions are still there when you want direct control:

>>> from datavinci.data import sample_ohlc
>>> df = sample_ohlc(periods=120)          # synthetic OHLC data, no network needed
>>> ax = dv.candlestick(df, title="Demo")  # returns a matplotlib Axes
>>> dv.save(ax, "demo.png")                # doctest: +SKIP

Charts are colorblind-safe by default (blue/red hollow candles, CVD-validated
accents). For the brighter green/red neon look, switch themes before plotting:

>>> dv.use_theme("terminal")
>>> ax = dv.candlestick(df, title="Demo")
"""

from ._theme import active_theme, available_themes, use_theme
from .convenience import chart, dashboard, save, show
from .timeseries import candlestick, line, moving_average

__version__ = "0.1.0"

__all__ = [
    "chart",
    "dashboard",
    "save",
    "show",
    "candlestick",
    "line",
    "moving_average",
    "use_theme",
    "active_theme",
    "available_themes",
    "__version__",
]
