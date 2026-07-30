"""Tests for the one-call convenience layer (chart / save / show).

Fully offline: the ticker-fetch path is exercised by monkeypatching the loader,
so no network is touched.
"""

import matplotlib

matplotlib.use("Agg")

import os  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

import datavinci as dv  # noqa: E402
import datavinci.convenience as convenience  # noqa: E402
from datavinci.data import sample_ohlc  # noqa: E402


@pytest.fixture
def ohlc():
    return sample_ohlc(periods=60, seed=42)


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


# --- source resolution --------------------------------------------------------


def test_chart_from_ohlc_dataframe_is_candlestick(ohlc):
    ax = dv.chart(ohlc)
    assert isinstance(ax, Axes)
    assert len(ax.patches) == len(ohlc)  # one candle body per row


def test_chart_from_series_is_line(ohlc):
    ax = dv.chart(ohlc["Close"])
    assert len(ax.lines) == 1


def test_chart_from_non_ohlc_dataframe_is_line(ohlc):
    ax = dv.chart(ohlc[["Open", "Close"]])
    assert len(ax.lines) == 2  # a line per column, not candles


def test_chart_ma_kind_draws_price_plus_windows(ohlc):
    ax = dv.chart(ohlc, kind="ma", windows=(5, 10))
    assert len(ax.lines) == 1 + 2  # price + one line per window


def test_chart_series_uses_name_as_title():
    s = pd.Series([1.0, 2.0, 3.0], name="Widgets")
    ax = dv.chart(s)
    assert ax.get_title(loc="left") == "Widgets"


# --- ticker path (monkeypatched, no network) ----------------------------------


def test_chart_ticker_string_fetches_and_titles(monkeypatch, ohlc):
    calls = {}

    def fake_load_ticker(symbol, *, period, interval):
        calls["args"] = (symbol, period, interval)
        return ohlc

    monkeypatch.setattr(convenience, "load_ticker", fake_load_ticker)
    ax = dv.chart("aapl", "6mo", interval="1d")

    assert calls["args"] == ("aapl", "6mo", "1d")  # period/interval forwarded
    assert ax.get_title(loc="left") == "AAPL"       # auto-titled with the symbol
    assert len(ax.patches) == len(ohlc)             # OHLC → candlestick


# --- file path ----------------------------------------------------------------


def test_chart_reads_csv_and_normalizes_columns(tmp_path, ohlc):
    # Write lowercase OHLC column names; chart() should normalize and draw candles.
    path = tmp_path / "prices.csv"
    ohlc.rename(columns=str.lower).to_csv(path)
    ax = dv.chart(str(path))
    assert len(ax.patches) == len(ohlc)


def test_looks_like_file_distinguishes_ticker_from_path():
    assert convenience._looks_like_file("prices.csv")
    assert convenience._looks_like_file("data/prices.tsv")
    assert not convenience._looks_like_file("AAPL")


# --- error handling -----------------------------------------------------------


def test_chart_candle_kind_on_series_raises(ohlc):
    with pytest.raises(ValueError):
        dv.chart(ohlc["Close"], kind="candle")


def test_chart_unknown_kind_raises(ohlc):
    with pytest.raises(ValueError):
        dv.chart(ohlc, kind="pie")


def test_chart_bad_source_type_raises():
    with pytest.raises(TypeError):
        dv.chart(12345)


# --- save ---------------------------------------------------------------------


def test_save_writes_a_nonempty_file(tmp_path, ohlc):
    ax = dv.chart(ohlc)
    out = tmp_path / "chart.png"
    returned = dv.save(ax, str(out))
    assert returned == str(out)
    assert os.path.getsize(out) > 0


def test_chart_save_kwarg_writes_file(tmp_path, ohlc):
    out = tmp_path / "inline.png"
    ax = dv.chart(ohlc, save=str(out))
    assert isinstance(ax, Axes)      # still returns the Axes
    assert os.path.getsize(out) > 0  # and wrote the file


# --- dashboard ----------------------------------------------------------------


def test_dashboard_has_two_panels_with_volume(ohlc):
    fig = dv.dashboard(ohlc, sma=(10, 20))
    assert isinstance(fig, Figure)
    assert len(fig.axes) == 2  # price + volume panels


def test_dashboard_price_panel_has_candles_and_sma(ohlc):
    fig = dv.dashboard(ohlc, sma=(10, 20))
    price_ax = fig.axes[0]
    assert len(price_ax.patches) == len(ohlc)  # one candle body per row
    assert len(price_ax.lines) == 2            # two SMA overlays


def test_dashboard_volume_bars_count(ohlc):
    fig = dv.dashboard(ohlc, sma=())
    vol_ax = fig.axes[1]
    # A volume bar per row (plus matplotlib may add container patches, so >=).
    assert len(vol_ax.patches) == len(ohlc)


def test_dashboard_without_volume_is_single_panel(ohlc):
    fig = dv.dashboard(ohlc, volume=False)
    assert len(fig.axes) == 1


def test_dashboard_drops_volume_when_column_absent(ohlc):
    # No Volume column → volume panel is silently skipped even if requested.
    fig = dv.dashboard(ohlc.drop(columns=["Volume"]), volume=True)
    assert len(fig.axes) == 1


def test_dashboard_requires_ohlc(ohlc):
    with pytest.raises(ValueError):
        dv.dashboard(ohlc[["Close"]])


def test_dashboard_save_kwarg_writes_file(tmp_path, ohlc):
    out = tmp_path / "dash.png"
    fig = dv.dashboard(ohlc, save=str(out))
    assert isinstance(fig, Figure)
    assert os.path.getsize(out) > 0
