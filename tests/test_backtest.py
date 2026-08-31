"""Tests for the educational backtester and tearsheet. Fully offline (Agg backend,
synthetic data). Several tests hand-compute expected values so they double as a
readable spec of the backtest math.
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

import datavinci as dv  # noqa: E402
from datavinci.data import sample_ohlc  # noqa: E402


@pytest.fixture
def ohlc():
    return sample_ohlc(periods=300, seed=5)


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


def _frame(prices):
    """Minimal OHLC frame from a list of closes (Open=Close for simplicity)."""
    idx = pd.date_range("2023-01-02", periods=len(prices), freq="B")
    p = pd.Series(prices, index=idx, dtype=float)
    return pd.DataFrame({"Open": p, "High": p, "Low": p, "Close": p})


# --- the core math (hand-computed) -------------------------------------------


def test_always_long_equals_buyhold_without_costs():
    # A strategy that is always long, with zero cost, must match buy-&-hold
    # (aside from the first bar, which no strategy can trade on).
    df = _frame([100, 110, 99, 99, 120])
    always_long = pd.Series(1.0, index=df.index)
    r = dv.backtest(df, always_long, cost=0.0)
    assert np.isclose(r.history["equity"].iloc[-1], r.history["buyhold"].iloc[-1])


def test_hand_computed_equity_curve():
    # prices: 100 -> 110 -> 99 ; always long, no cost.
    # returns:   nan, +10%, -10%   (99/110 - 1 = -0.10)
    # position (signal shifted by 1): 0, 1, 1
    # net:       0, +0.10, -0.10
    # equity:    1.0, 1.10, 0.99
    df = _frame([100, 110, 99])
    r = dv.backtest(df, pd.Series(1.0, index=df.index), cost=0.0)
    np.testing.assert_allclose(r.history["equity"].to_numpy(), [1.0, 1.10, 0.99])
    assert np.isclose(r.metrics["Total return"], -0.01)


def test_lookahead_guard_shifts_the_signal():
    # position must equal the signal shifted one bar (you act on the NEXT bar).
    df = _frame([10, 11, 12, 13, 14])
    signal = pd.Series([0, 1, 1, 0, 1], index=df.index, dtype=float)
    r = dv.backtest(df, signal, cost=0.0)
    expected = signal.shift(1).fillna(0.0)
    np.testing.assert_allclose(r.history["position"].to_numpy(), expected.to_numpy())


def test_cost_charged_per_round_trip():
    # Flat prices, so the only thing that moves equity is trading cost. We enter
    # once and exit once (a round trip), so cost is charged exactly twice.
    df = _frame([100, 100, 100, 100])
    signal = pd.Series([0, 1, 0, 0], index=df.index, dtype=float)  # in then out
    free = dv.backtest(df, signal, cost=0.0).history["equity"].iloc[-1]
    charged = dv.backtest(df, signal, cost=0.01).history["equity"].iloc[-1]
    assert np.isclose(free, 1.0)               # no cost, flat price -> unchanged
    assert np.isclose(charged, (1 - 0.01) ** 2)  # entry + exit = two cost hits
    assert charged < free


# --- metrics & trades ---------------------------------------------------------


def test_metrics_present_and_drawdown_nonpositive(ohlc):
    r = dv.backtest(ohlc, dv.strategies.sma_crossover(10, 30))
    for key in ("Total return", "CAGR", "Sharpe", "Max drawdown", "Win rate", "Trades"):
        assert key in r.metrics
    dd = r.history["drawdown"]
    assert (dd <= 1e-9).all()          # drawdown is never positive
    assert (dd >= -1.0 - 1e-9).all()   # and never worse than -100%


def test_win_rate_in_range_and_trades_match(ohlc):
    r = dv.backtest(ohlc, dv.strategies.sma_crossover(10, 30))
    assert 0.0 <= r.metrics["Win rate"] <= 1.0
    assert r.metrics["Trades"] == len(r.trades)


def test_backtest_requires_close_column():
    df = _frame([1, 2, 3]).drop(columns=["Close"])
    with pytest.raises(KeyError):
        dv.backtest(df, pd.Series(1.0, index=df.index))


def test_backtest_needs_two_rows():
    df = _frame([100])
    with pytest.raises(ValueError):
        dv.backtest(df, pd.Series(1.0, index=df.index))


# --- strategies ---------------------------------------------------------------


def test_sma_crossover_signal_is_binary(ohlc):
    sig = dv.strategies.sma_crossover(10, 30)(ohlc)
    assert set(np.unique(sig.dropna())) <= {0.0, 1.0}
    assert len(sig) == len(ohlc)


def test_sma_crossover_rejects_bad_windows():
    with pytest.raises(ValueError):
        dv.strategies.sma_crossover(fast=50, slow=20)


def test_rsi_bounds(ohlc):
    r = dv.strategies.rsi(ohlc["Close"], 14).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_all_canned_strategies_run(ohlc):
    for strat in (
        dv.strategies.sma_crossover(10, 30),
        dv.strategies.rsi_meanreversion(),
        dv.strategies.bollinger_breakout(),
    ):
        r = dv.backtest(ohlc, strat)
        assert "Total return" in r.metrics


# --- tearsheet ----------------------------------------------------------------


def test_tearsheet_returns_figure_with_four_panels(ohlc):
    r = dv.backtest(ohlc, dv.strategies.sma_crossover(10, 30), strategy_name="test")
    fig = dv.tearsheet(r)
    assert isinstance(fig, Figure)
    assert len(fig.axes) == 4  # metrics, price, equity, drawdown
