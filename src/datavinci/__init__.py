"""datavinci — a friendly matplotlib wrapper for time-series and financial charts.

The package aims to turn common, fiddly matplotlib recipes (candlesticks, moving
averages, cleanly styled line charts) into one-line calls that return a normal
matplotlib ``Axes`` so you can keep customizing however you like.

Quick start
-----------
>>> import datavinci as dv
>>> from datavinci.data import sample_ohlc
>>> df = sample_ohlc(periods=120)          # synthetic OHLC data, no network needed
>>> ax = dv.candlestick(df, title="Demo")  # returns a matplotlib Axes

Charts are colorblind-safe by default (blue/red hollow candles, CVD-validated
accents). For the brighter green/red neon look, switch themes before plotting:

>>> dv.use_theme("terminal")
>>> ax = dv.candlestick(df, title="Demo")
"""

from ._theme import active_theme, available_themes, use_theme
from .timeseries import candlestick, line, moving_average

__version__ = "0.1.0"

__all__ = [
    "candlestick",
    "line",
    "moving_average",
    "use_theme",
    "active_theme",
    "available_themes",
    "__version__",
]
