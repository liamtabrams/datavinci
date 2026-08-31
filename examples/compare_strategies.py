"""Compare every built-in trading strategy on historical data.

Runs all of datavinci's canned strategies (SMA crossover, RSI mean-reversion,
Bollinger breakout, MACD crossover) plus a buy-&-hold baseline through the
backtester on the *same* price series, then:

  * prints a side-by-side metrics table, and
  * saves an equity-curve comparison chart and each strategy's tearsheet.

Usage
-----
Offline, with synthetic data (always works, no network, no extra installs)::

    python examples/compare_strategies.py

On a real ticker (needs ``pip install "datavinci[finance]"`` and a network
connection; falls back to synthetic data if that isn't available)::

    python examples/compare_strategies.py --ticker AAPL --period 5y

Other options::

    --cost 0.001     transaction cost per trade (fraction; 0.001 = 10 bps)
    --outdir out     where to write the PNGs (default: ./strategy_comparison)
    --no-plots       just print the table, don't render/save any images
    --show           pop up the charts interactively instead of only saving

This is an educational tool for learning and visualization — NOT investment
advice. Backtested results never guarantee future performance, and it is easy to
make any strategy look good by testing it on data you cherry-picked.
"""

from __future__ import annotations

import argparse
import sys

# Choose a headless plotting backend BEFORE importing datavinci (which imports
# matplotlib), unless the user asked to display windows with --show.
import matplotlib

if "--show" not in sys.argv:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import datavinci as dv  # noqa: E402
from datavinci._theme import (  # noqa: E402  (internal helpers, fine for an in-repo example)
    INK,
    add_time_grid,
    glow,
    style_axes,
    style_legend,
    theme_palette,
)
from datavinci.data import sample_ohlc  # noqa: E402
from datavinci.timeseries import _x_numeric  # noqa: E402


def build_strategies() -> dict:
    """The strategies to compare, as {label: strategy function}."""
    return {
        "SMA crossover": dv.strategies.sma_crossover(fast=20, slow=50),
        "RSI mean-reversion": dv.strategies.rsi_meanreversion(period=14, low=30, high=70),
        "Bollinger breakout": dv.strategies.bollinger_breakout(period=20, num_std=2),
        "MACD crossover": dv.strategies.macd_crossover(fast=12, slow=26, signal=9),
        # Buy & hold: always long. The baseline every strategy is measured against.
        "Buy & hold": lambda df: pd.Series(1.0, index=df.index),
    }


def load_data(ticker: str | None, period: str, interval: str) -> tuple[pd.DataFrame, str]:
    """Load price data. Try a real ticker if asked; otherwise synthetic data.

    Falls back to synthetic data (with a printed note) if the ticker can't be
    fetched — e.g. yfinance isn't installed or there's no network — so the script
    always runs.
    """
    if ticker:
        try:
            from datavinci.data import load_ticker

            df = load_ticker(ticker, period=period, interval=interval)
            return df, ticker.upper()
        except Exception as exc:  # ImportError, network error, bad symbol, ...
            print(f"! Could not load {ticker!r} ({exc}).")
            print("  Falling back to synthetic data.\n")
    # ~3 years of business days of reproducible synthetic OHLC data.
    return sample_ohlc(periods=750, seed=14), "SYNTHETIC"


def run_comparison(df: pd.DataFrame, cost: float) -> tuple[pd.DataFrame, dict]:
    """Backtest every strategy on ``df`` and collect their metrics.

    Returns
    -------
    (table, results):
        ``table`` is a DataFrame of headline metrics, one row per strategy.
        ``results`` maps each label to its full :class:`~datavinci.BacktestResult`.
    """
    results: dict = {}
    rows = []
    for label, strat in build_strategies().items():
        result = dv.backtest(df, strat, cost=cost, strategy_name=label)
        results[label] = result
        m = result.metrics
        rows.append(
            {
                "Strategy": label,
                "Total return": m["Total return"],
                "CAGR": m["CAGR"],
                "Sharpe": m["Sharpe"],
                "Max drawdown": m["Max drawdown"],
                "Win rate": m["Win rate"],
                "Trades": int(m["Trades"]),
            }
        )
    table = pd.DataFrame(rows).set_index("Strategy")
    return table, results


def format_table(table: pd.DataFrame) -> str:
    """Format the metrics table for printing (percentages, 2-dp Sharpe)."""
    disp = pd.DataFrame(index=table.index)
    # Gains/losses get a +/- sign; magnitudes (drawdown, win rate) print unsigned.
    for col in ("Total return", "CAGR"):
        disp[col] = table[col].map(lambda v: "n/a" if pd.isna(v) else f"{v * 100:+.1f}%")
    for col in ("Max drawdown", "Win rate"):
        disp[col] = table[col].map(lambda v: "n/a" if pd.isna(v) else f"{v * 100:.1f}%")
    disp["Sharpe"] = table["Sharpe"].map(lambda v: "n/a" if pd.isna(v) else f"{v:.2f}")
    disp["Trades"] = table["Trades"]
    return disp.to_string()


def plot_equity_comparison(results: dict, label: str, outpath: str) -> None:
    """Overlay every strategy's equity curve on one themed chart and save it."""
    fig, ax = plt.subplots(figsize=(12, 6))
    x = None
    palette = theme_palette()
    color_i = 0
    for name, result in results.items():
        h = result.history
        if x is None:
            x, is_dt = _x_numeric(h.index)
        if name == "Buy & hold":
            # Draw the baseline as a dashed neutral line, not a palette color.
            ax.plot(x, h["equity"].to_numpy(), color=INK, linewidth=1.4,
                    linestyle="--", label=name)
        else:
            color = palette[color_i % len(palette)]
            color_i += 1
            (ln,) = ax.plot(x, h["equity"].to_numpy(), color=color, linewidth=2.0, label=name)
            ln.set_path_effects(glow(color, base_lw=2.0))
    if is_dt:
        ax.xaxis_date()
    style_axes(ax, title=f"Strategy comparison — growth of $1 ({label})", ylabel="Equity (×)")
    add_time_grid(ax, is_dt)
    style_legend(ax, loc="best")
    dv.save(fig, outpath)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare datavinci's built-in strategies.")
    parser.add_argument("--ticker", help="Real ticker to fetch (needs [finance] extra + network).")
    parser.add_argument("--period", default="5y", help="yfinance period for --ticker (default 5y).")
    parser.add_argument("--interval", default="1d", help="yfinance interval for --ticker.")
    parser.add_argument("--cost", type=float, default=0.001, help="Cost per trade (default 0.001).")
    parser.add_argument("--outdir", default="strategy_comparison", help="Output dir for PNGs.")
    parser.add_argument("--no-plots", action="store_true", help="Only print the table.")
    parser.add_argument("--show", action="store_true", help="Display charts, don't only save.")
    args = parser.parse_args(argv)

    df, label = load_data(args.ticker, args.period, args.interval)
    print(f"Data: {label}  ({len(df)} bars, {df.index[0].date()} → {df.index[-1].date()})")
    print(f"Transaction cost: {args.cost * 100:.2f}% per trade\n")

    table, results = run_comparison(df, args.cost)
    print(format_table(table))

    # Highlight the best strategy by Sharpe ratio (risk-adjusted return).
    ranked = table["Sharpe"].dropna().sort_values(ascending=False)
    if not ranked.empty:
        print(f"\nBest risk-adjusted (Sharpe): {ranked.index[0]} ({ranked.iloc[0]:.2f})")
    print("\nReminder: educational only — past performance is not indicative of future results.")

    if args.no_plots:
        return

    import os

    os.makedirs(args.outdir, exist_ok=True)
    # One overlaid equity-curve comparison...
    plot_equity_comparison(results, label, os.path.join(args.outdir, "equity_comparison.png"))
    # ...and an individual tearsheet per strategy (skip the buy-&-hold baseline).
    for name, result in results.items():
        if name == "Buy & hold":
            continue
        slug = name.lower().replace(" ", "_").replace("-", "_")
        dv.save(dv.tearsheet(result), os.path.join(args.outdir, f"tearsheet_{slug}.png"))
    print(f"\nSaved comparison chart and tearsheets to {args.outdir}/")

    if args.show:
        dv.show()


if __name__ == "__main__":
    main()
