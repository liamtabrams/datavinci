"""Tests for datavinci. Uses the non-interactive Agg backend so no display is
needed, and synthetic data so the suite runs fully offline."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

import datavinci as dv  # noqa: E402
from datavinci.data import sample_ohlc  # noqa: E402


@pytest.fixture
def ohlc():
    return sample_ohlc(periods=60, seed=42)


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


@pytest.fixture(autouse=True)
def _reset_theme():
    # Theme is global state; keep tests independent of each other's switches.
    yield
    dv.use_theme("colorblind")


def _two_candles():
    """A minimal frame with one up row (row 0) and one down row (row 1)."""
    idx = pd.to_datetime(["2020-01-01", "2020-01-02"])
    return pd.DataFrame(
        {"Open": [10.0, 20.0], "High": [16.0, 21.0], "Low": [9.0, 14.0], "Close": [15.0, 15.0]},
        index=idx,
    )


def test_version_is_string():
    assert isinstance(dv.__version__, str)
    assert dv.__version__.count(".") >= 2


def test_sample_ohlc_shape_and_columns():
    df = sample_ohlc(periods=50, seed=1)
    assert len(df) == 50
    assert list(df.columns) == ["Open", "High", "Low", "Close"]
    assert isinstance(df.index, pd.DatetimeIndex)


def test_sample_ohlc_high_low_invariants(ohlc):
    # High should be the max and Low the min of the OHLC row.
    assert (ohlc["High"] >= ohlc[["Open", "Close"]].max(axis=1)).all()
    assert (ohlc["Low"] <= ohlc[["Open", "Close"]].min(axis=1)).all()


def test_sample_ohlc_is_reproducible():
    pd.testing.assert_frame_equal(sample_ohlc(periods=30, seed=7), sample_ohlc(periods=30, seed=7))


def test_line_from_series_returns_axes(ohlc):
    ax = dv.line(ohlc["Close"], title="Close")
    assert isinstance(ax, Axes)
    assert len(ax.lines) == 1


def test_line_from_dataframe_multiple_columns(ohlc):
    ax = dv.line(ohlc, columns=["Open", "Close"])
    assert len(ax.lines) == 2


def test_line_missing_column_raises(ohlc):
    with pytest.raises(KeyError):
        dv.line(ohlc, columns=["Nope"])


def test_moving_average_draws_price_plus_windows(ohlc):
    ax = dv.moving_average(ohlc["Close"], windows=(5, 10, 20))
    # One raw-price line plus one line per window.
    assert len(ax.lines) == 1 + 3


def test_moving_average_rejects_bad_window(ohlc):
    with pytest.raises(ValueError):
        dv.moving_average(ohlc["Close"], windows=(0,))


def test_candlestick_returns_axes(ohlc):
    ax = dv.candlestick(ohlc, title="Demo")
    assert isinstance(ax, Axes)
    # One bar per row for the bodies.
    assert len(ax.patches) == len(ohlc)


def test_candlestick_missing_columns_raises(ohlc):
    with pytest.raises(KeyError):
        dv.candlestick(ohlc.drop(columns=["High"]))


def test_candlestick_empty_raises():
    empty = pd.DataFrame(columns=["Open", "High", "Low", "Close"])
    with pytest.raises(ValueError):
        dv.candlestick(empty)


# --- Theme system -------------------------------------------------------------


def test_available_themes_includes_builtins():
    themes = dv.available_themes()
    assert "terminal" in themes
    assert "colorblind" in themes


def test_default_active_theme_is_colorblind():
    assert dv.active_theme() == "colorblind"


def test_use_theme_unknown_raises():
    with pytest.raises(ValueError):
        dv.use_theme("does-not-exist")


def test_use_theme_switches_candle_up_color():
    df = _two_candles()
    dv.use_theme("terminal")
    up_terminal = tuple(dv.candlestick(df).patches[0].get_facecolor())
    dv.use_theme("colorblind")
    up_colorblind = tuple(dv.candlestick(df).patches[0].get_facecolor())
    assert up_terminal != up_colorblind


def test_colorblind_theme_draws_down_candles_hollow():
    dv.use_theme("colorblind")
    ax = dv.candlestick(_two_candles())
    up_patch, down_patch = ax.patches[0], ax.patches[1]
    assert up_patch.get_facecolor()[3] == 1.0   # up body is filled
    assert down_patch.get_facecolor()[3] == 0.0  # down body is a hollow outline


def test_terminal_theme_fills_both_candles():
    dv.use_theme("terminal")
    ax = dv.candlestick(_two_candles())
    assert ax.patches[0].get_facecolor()[3] == 1.0
    assert ax.patches[1].get_facecolor()[3] == 1.0


def test_hollow_down_override_is_independent_of_theme():
    # Explicit arg wins even under the filled default theme.
    dv.use_theme("terminal")
    ax = dv.candlestick(_two_candles(), hollow_down=True)
    assert ax.patches[1].get_facecolor()[3] == 0.0


def test_line_palette_follows_active_theme(ohlc):
    dv.use_theme("terminal")
    color_terminal = dv.line(ohlc["Close"]).lines[0].get_color()
    dv.use_theme("colorblind")
    color_colorblind = dv.line(ohlc["Close"]).lines[0].get_color()
    assert color_terminal != color_colorblind
