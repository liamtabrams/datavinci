"""A small, transparent, single-asset backtester plus a performance *tearsheet*.

This is intentionally simple and fully vectorized so you can read every line and
trust the numbers. It is for **education and visualization** — not live trading,
and not investment advice. Backtested performance never guarantees future results.

The model
---------
Given regularly-spaced OHLC data and a ``signal`` (the target position per bar,
from a :mod:`datavinci.strategies` factory or your own function), the backtester:

1. **Applies a one-bar delay** so you can't look into the future::

       position = signal.shift(1)

   You act on a signal on the *next* bar, so a rule computed at today's close can
   only affect tomorrow's return. This is the single most important guard against
   *lookahead bias* — accidentally trading on information you wouldn't have had yet.

2. **Computes the asset's simple returns**::

       r[t] = Close[t] / Close[t-1] - 1

3. **Strategy return before costs** is the position times the asset return::

       gross[t] = position[t] * r[t]

4. **Subtracts trading costs whenever the position changes**. Turnover is the size
   of the change, and cost is charged on it::

       turnover[t] = |position[t] - position[t-1]|
       net[t]      = gross[t] - cost * turnover[t]

   So ``cost=0.001`` (10 basis points) is charged once to open a position, again to
   close it, and twice to flip from long to short.

5. **Compounds net returns into an equity curve** starting at 1.0, and does the
   same for a plain buy-&-hold baseline for comparison::

       equity[t] = product(1 + net[0..t])

Everything is stored on :attr:`BacktestResult.history` so you can inspect the
columns or re-plot them yourself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ._theme import (
    INK,
    add_time_grid,
    style_axes,
    style_legend,
    theme_down,
    theme_palette,
    theme_up,
)
from .strategies import Strategy
from .timeseries import _x_numeric

__all__ = ["backtest", "tearsheet", "BacktestResult"]

# Metrics expressed as fractions that should be shown as percentages.
_PERCENT_METRICS = frozenset(
    {
        "Total return",
        "CAGR",
        "Ann. volatility",
        "Max drawdown",
        "Win rate",
        "Exposure",
        "Buy & hold return",
    }
)
# Percent metrics where a leading +/- sign is meaningful (gains/losses). The rest
# (volatility, drawdown, win rate, exposure) are magnitudes and print unsigned.
_SIGNED_METRICS = frozenset({"Total return", "CAGR", "Buy & hold return"})
# Metrics that are plain ratios (no % sign).
_RATIO_METRICS = frozenset({"Sharpe", "Sortino", "Calmar"})


def _close(df: pd.DataFrame) -> pd.Series:
    """Return the closing-price series, matching the column case-insensitively."""
    for col in df.columns:
        if isinstance(col, str) and col.lower() == "close":
            return df[col].astype(float)
    raise KeyError("backtest() needs a 'Close' column in the DataFrame.")


def _infer_periods_per_year(index: pd.Index) -> int:
    """Guess how many bars make up a year, for annualizing returns.

    Uses the median spacing of a DatetimeIndex: ~daily -> 252 trading days,
    ~weekly -> 52, ~monthly -> 12. Falls back to 252 (daily) for anything else,
    including a non-datetime index. Pass ``periods_per_year=`` to override.
    """
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 3:
        return 252
    med_days = index.to_series().diff().dropna().median() / pd.Timedelta(days=1)
    if med_days <= 1.5:
        return 252  # daily bars are conventionally annualized by trading days
    if med_days <= 8:
        return 52  # weekly
    if med_days <= 45:
        return 12  # monthly
    return 1


@dataclass
class BacktestResult:
    """The output of :func:`backtest` — data, per-trade log, and summary metrics.

    Attributes
    ----------
    history:
        Per-bar DataFrame with columns ``price``, ``signal``, ``position``,
        ``asset_return``, ``gross_return``, ``net_return``, ``equity``,
        ``buyhold`` and ``drawdown``.
    trades:
        One row per completed trade: ``entry``, ``exit``, ``direction`` (+1/-1),
        ``return`` (net, fractional), and ``bars`` held.
    metrics:
        Dict of headline numbers (see :meth:`summary`).
    cost:
        The per-unit-turnover cost used.
    periods_per_year:
        The annualization factor used for CAGR / volatility / Sharpe.
    strategy_name:
        A label for plots and printouts.
    """

    history: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float]
    cost: float
    periods_per_year: int
    strategy_name: str = "strategy"
    _percent: frozenset = field(default=_PERCENT_METRICS, repr=False)

    def summary(self) -> str:
        """Return a human-readable, aligned block of the headline metrics."""
        lines = [f"Backtest: {self.strategy_name}"]
        for name, value in self.metrics.items():
            lines.append(f"  {name:<18} {_format_metric(name, value)}")
        return "\n".join(lines)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return self.summary()


def _format_metric(name: str, value: float) -> str:
    """Format a metric value: percents with %, ratios to 2 dp, counts as ints."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    if name in _PERCENT_METRICS:
        # Signed for gains/losses; unsigned magnitude for vol/drawdown/win/exposure.
        return f"{value * 100:+.2f}%" if name in _SIGNED_METRICS else f"{value * 100:.2f}%"
    if name in _RATIO_METRICS:
        return f"{value:.2f}"
    if name == "Trades":
        return f"{int(value)}"
    return f"{value:.2f}"


def _extract_trades(
    index: pd.Index, position: np.ndarray, net_return: np.ndarray
) -> pd.DataFrame:
    """Group the per-bar series into discrete trades (contiguous holding runs).

    A trade is a maximal run of the same non-zero position. Its return is the
    compounded net strategy return over the run — the exact same ``net_return``
    that builds the equity curve — so per-trade P&L is consistent with equity.
    """
    rows = []
    n = len(position)
    t = 0
    while t < n:
        if position[t] == 0:
            t += 1
            continue
        direction = position[t]
        start = t
        # Extend while the position stays identical.
        while t < n and position[t] == direction:
            t += 1
        end = t - 1  # inclusive last bar of the run
        # Compound the net returns earned across the run.
        run = net_return[start : end + 1]
        trade_return = float(np.prod(1.0 + run) - 1.0)
        rows.append(
            {
                "entry": index[start],
                "exit": index[end],
                "direction": int(direction),
                "return": trade_return,
                "bars": end - start + 1,
            }
        )
    return pd.DataFrame(rows, columns=["entry", "exit", "direction", "return", "bars"])


def _compute_metrics(
    net: pd.Series,
    equity: pd.Series,
    buyhold: pd.Series,
    drawdown: pd.Series,
    position: pd.Series,
    trades: pd.DataFrame,
    periods_per_year: int,
) -> dict[str, float]:
    """Compute the headline performance metrics from the per-bar series."""
    n = len(net)
    final = float(equity.iloc[-1])

    total_return = final - 1.0
    # CAGR: the constant annual growth rate that would produce `final` over n bars.
    cagr = final ** (periods_per_year / n) - 1.0 if final > 0 and n > 0 else float("nan")

    ann_vol = float(net.std(ddof=0)) * np.sqrt(periods_per_year)
    ann_ret = float(net.mean()) * periods_per_year
    sharpe = ann_ret / ann_vol if ann_vol > 0 else float("nan")

    downside = net[net < 0]
    downside_dev = float(downside.std(ddof=0)) * np.sqrt(periods_per_year)
    sortino = ann_ret / downside_dev if downside_dev > 0 else float("nan")

    max_dd = float(drawdown.min())  # most-negative point of the underwater curve
    calmar = cagr / abs(max_dd) if max_dd < 0 and not np.isnan(cagr) else float("nan")

    win_rate = float((trades["return"] > 0).mean()) if len(trades) else float("nan")
    exposure = float((position != 0).mean())  # fraction of time holding a position

    return {
        "Total return": total_return,
        "CAGR": cagr,
        "Ann. volatility": ann_vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max drawdown": max_dd,
        "Calmar": calmar,
        "Win rate": win_rate,
        "Trades": float(len(trades)),
        "Exposure": exposure,
        "Buy & hold return": float(buyhold.iloc[-1]) - 1.0,
    }


def backtest(
    df: pd.DataFrame,
    strategy: Strategy | pd.Series,
    *,
    cost: float = 0.001,
    periods_per_year: int | None = None,
    strategy_name: str | None = None,
) -> BacktestResult:
    """Run a simple, honest, single-asset backtest.

    Parameters
    ----------
    df:
        OHLC data with a ``Close`` column and (ideally) a DatetimeIndex.
    strategy:
        Either a strategy function from :mod:`datavinci.strategies` (which takes
        ``df`` and returns a target-position Series), or a pre-computed position
        Series aligned to ``df`` (values in ``{-1, 0, 1}``).
    cost:
        Transaction cost per unit of turnover, as a fraction. ``0.001`` = 10 bps,
        charged each time the position changes (open, close, or flip). Set ``0`` to
        ignore costs (not realistic for anything that trades often).
    periods_per_year:
        Annualization factor for CAGR/volatility/Sharpe. Inferred from the index
        spacing if omitted (daily -> 252).
    strategy_name:
        Label used in the tearsheet and printouts.

    Returns
    -------
    BacktestResult

    Notes
    -----
    The signal is delayed one bar (``position = signal.shift(1)``) so the backtest
    cannot trade on information from the same bar that produced the signal. See the
    module docstring for the full model.

    This is an educational tool, not investment advice.
    """
    price = _close(df)
    if len(price) < 2:
        raise ValueError("Need at least 2 rows of price data to backtest.")

    # 1. Get the target-position signal (call the strategy, or use the Series).
    signal = strategy(df) if callable(strategy) else strategy
    signal = pd.Series(signal, index=df.index).astype(float).fillna(0.0)

    # 1a. THE LOOKAHEAD GUARD: act on the signal on the *next* bar.
    position = signal.shift(1).fillna(0.0)

    # 2. Asset simple returns.
    asset_return = price.pct_change().fillna(0.0)

    # 3. Strategy return before costs.
    gross_return = position * asset_return

    # 4. Costs whenever the position changes (turnover), then net return.
    turnover = position.diff().abs().fillna(position.abs())  # first bar: |pos[0]-0|
    net_return = gross_return - cost * turnover

    # 5. Equity curves (start at 1.0) for the strategy and a buy-&-hold baseline.
    equity = (1.0 + net_return).cumprod()
    buyhold = (1.0 + asset_return).cumprod()

    # Underwater / drawdown curve: how far below the running peak we are.
    drawdown = equity / equity.cummax() - 1.0

    history = pd.DataFrame(
        {
            "price": price,
            "signal": signal,
            "position": position,
            "asset_return": asset_return,
            "gross_return": gross_return,
            "net_return": net_return,
            "equity": equity,
            "buyhold": buyhold,
            "drawdown": drawdown,
        }
    )

    ppy = periods_per_year or _infer_periods_per_year(df.index)
    trades = _extract_trades(df.index, position.to_numpy(), net_return.to_numpy())
    metrics = _compute_metrics(net_return, equity, buyhold, drawdown, position, trades, ppy)

    return BacktestResult(
        history=history,
        trades=trades,
        metrics=metrics,
        cost=cost,
        periods_per_year=ppy,
        strategy_name=strategy_name or getattr(strategy, "__name__", "strategy"),
    )


def tearsheet(result: BacktestResult, *, figsize: tuple[float, float] = (12, 10)):
    """Render a performance tearsheet for a :class:`BacktestResult`.

    Four stacked, x-aligned panels using the active datavinci theme:

    1. **Metrics** — a text panel of the headline numbers.
    2. **Price with trade markers** — entries (▲) and exits (▼).
    3. **Equity curve** — strategy vs. buy-&-hold, both starting at 1.0.
    4. **Drawdown** — the underwater curve (how far below the prior peak).

    Returns the matplotlib ``Figure`` (pass it to :func:`datavinci.save`).
    """
    import matplotlib.pyplot as plt

    h = result.history
    x, is_dt = _x_numeric(h.index)
    pal = theme_palette()
    up, down = theme_up(), theme_down()

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(
        4, 1, height_ratios=[1.1, 2.2, 1.8, 1.2], hspace=0.35
    )
    ax_metrics = fig.add_subplot(gs[0])
    ax_price = fig.add_subplot(gs[1])
    ax_equity = fig.add_subplot(gs[2], sharex=ax_price)
    ax_dd = fig.add_subplot(gs[3], sharex=ax_price)

    # --- Panel 1: metrics as text -------------------------------------------
    ax_metrics.axis("off")
    ax_metrics.set_title(
        f"{result.strategy_name}  —  backtest tearsheet",
        fontsize=15, fontweight="bold", loc="left", color=INK, pad=10,
    )
    items = list(result.metrics.items())
    # Lay the metrics out in three columns of key: value pairs.
    ncol = 3
    per_col = -(-len(items) // ncol)  # ceil
    for c in range(ncol):
        chunk = items[c * per_col : (c + 1) * per_col]
        lines = [f"{name:<18}{_format_metric(name, val)}" for name, val in chunk]
        ax_metrics.text(
            0.02 + c / ncol, 0.75, "\n".join(lines),
            transform=ax_metrics.transAxes, va="top", ha="left",
            family="DejaVu Sans Mono", fontsize=9.5, color=INK,
        )

    # --- Panel 2: price + trade markers -------------------------------------
    (price_line,) = ax_price.plot(x, h["price"].to_numpy(), color=INK, linewidth=1.4)
    if not result.trades.empty:
        pos_of = pd.Series(x, index=h.index)
        for _, tr in result.trades.iterrows():
            xe, xx = pos_of.loc[tr["entry"]], pos_of.loc[tr["exit"]]
            ye = float(h.loc[tr["entry"], "price"])
            yx = float(h.loc[tr["exit"], "price"])
            # Entry: up-triangle in the up-color; exit: down-triangle in down-color.
            ax_price.scatter([xe], [ye], marker="^", s=55, color=up, zorder=5, edgecolor="none")
            ax_price.scatter([xx], [yx], marker="v", s=55, color=down, zorder=5, edgecolor="none")
    if is_dt:
        ax_price.xaxis_date()
    style_axes(ax_price, title="Price & trades", ylabel="Price")
    add_time_grid(ax_price, is_dt)
    ax_price.tick_params(labelbottom=False)

    # --- Panel 3: equity vs buy & hold --------------------------------------
    (eq_line,) = ax_equity.plot(x, h["equity"].to_numpy(), color=pal[0], linewidth=2.0,
                                label=f"{result.strategy_name} (net)")
    ax_equity.plot(x, h["buyhold"].to_numpy(), color=INK, linewidth=1.4,
                   linestyle="--", label="Buy & hold")
    if is_dt:
        ax_equity.xaxis_date()
    style_axes(ax_equity, title="Growth of $1", ylabel="Equity (×)")
    add_time_grid(ax_equity, is_dt)
    style_legend(ax_equity, loc="best")
    ax_equity.tick_params(labelbottom=False)

    # --- Panel 4: drawdown (underwater) -------------------------------------
    dd = h["drawdown"].to_numpy() * 100.0
    ax_dd.fill_between(x, dd, 0.0, color=down, alpha=0.35, zorder=2)
    ax_dd.plot(x, dd, color=down, linewidth=1.2, zorder=3)
    if is_dt:
        ax_dd.xaxis_date()
    style_axes(ax_dd, title="Drawdown", ylabel="% from peak")
    add_time_grid(ax_dd, is_dt)

    return fig
