"""Study: how do the built-in strategies perform across many stocks over ~20 years?

Backtests every built-in strategy (SMA crossover, RSI mean-reversion, Bollinger
breakout, MACD crossover) on a universe of stocks, then aggregates the results so
you can see how each strategy does *in general* — not just on one cherry-picked
chart. For each strategy it reports, across the universe:

  * median CAGR, Sharpe, and max drawdown,
  * average win rate, and
  * the share of stocks where the strategy BEAT buy-&-hold.

Usage
-----
Real data — a built-in ~30-stock universe, last 20 years (needs
``pip install "datavinci[finance]"`` and network)::

    python examples/strategy_study.py

Your own tickers::

    python examples/strategy_study.py --tickers AAPL MSFT KO JPM XOM --period 20y

Offline (synthetic universe — for testing the script with no network)::

    python examples/strategy_study.py --synthetic 30

Outputs a printed summary table, a `per_stock.csv` with every result, and a
summary chart. Add `--no-plots` to skip images.

⚠️  IMPORTANT — read before trusting any number this prints
----------------------------------------------------------
This is an educational tool, NOT investment advice, and the built-in universe has
serious biases you must keep in mind:

  * **Survivorship bias.** The default list is well-known companies that exist
    *today*. Firms that went bankrupt or were delisted over the last 20 years are
    missing, which flatters every result (both the strategies and buy-&-hold).
  * **In-sample / overfitting.** These strategy parameters are common defaults,
    but any rule tested on history you already know is optimistic.
  * **No slippage, taxes, or realistic fills.** Only a simple per-trade cost.

Real, unbiased strategy research controls for all of this. Treat the output as a
learning exercise in *comparing* rules, not as evidence any of them makes money.
"""

from __future__ import annotations

import argparse
import sys

import matplotlib

if "--show" not in sys.argv:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import datavinci as dv  # noqa: E402
from datavinci._theme import INK, add_time_grid, style_axes, theme_palette  # noqa: E402
from datavinci.data import sample_ohlc  # noqa: E402

# A default universe of ~34 large, long-listed US names (all trading 20 years ago).
# NOTE: this is survivorship-biased — see the module docstring.
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "JNJ", "JPM", "XOM", "PG", "KO", "PEP", "WMT", "HD",
    "DIS", "MCD", "CVX", "IBM", "INTC", "CSCO", "ORCL", "GE", "CAT", "BA",
    "MMM", "WFC", "C", "T", "VZ", "PFE", "MRK", "ABT", "NKE", "COST",
    "TGT", "UNH", "AXP", "GS",
]

# The strategies under study (label -> factory). Buy-&-hold is the baseline.
STRATEGIES = {
    "SMA crossover": lambda: dv.strategies.sma_crossover(50, 200),
    "RSI mean-reversion": lambda: dv.strategies.rsi_meanreversion(14, 30, 70),
    "Bollinger breakout": lambda: dv.strategies.bollinger_breakout(20, 2),
    "MACD crossover": lambda: dv.strategies.macd_crossover(12, 26, 9),
}


def synthetic_universe(n: int, bars: int) -> dict[str, pd.DataFrame]:
    """Build an offline universe of ``n`` synthetic stocks (for testing only)."""
    rng = np.random.default_rng(0)
    data = {}
    for i in range(n):
        vol = float(rng.uniform(0.012, 0.030))  # vary volatility across names
        data[f"SYN{i + 1:02d}"] = sample_ohlc(periods=bars, seed=i, volatility=vol)
    return data


def load_universe(
    tickers: list[str], period: str, interval: str, min_bars: int
) -> dict[str, pd.DataFrame]:
    """Fetch real price data for each ticker, skipping any that fail or are short."""
    from datavinci.data import load_ticker

    data = {}
    for sym in tickers:
        try:
            df = load_ticker(sym, period=period, interval=interval)
        except Exception as exc:  # network error, bad symbol, delisted, ...
            print(f"  ! skipping {sym}: {exc}")
            continue
        if len(df) < min_bars:
            print(f"  ! skipping {sym}: only {len(df)} bars (< {min_bars})")
            continue
        data[sym] = df
    return data


def run_study(data: dict[str, pd.DataFrame], cost: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Backtest every strategy on every stock; return (summary, per_stock) tables.

    ``per_stock`` has one row per (strategy, ticker). ``summary`` aggregates it to
    one row per strategy.
    """
    rows = []
    for ticker, df in data.items():
        # Buy-&-hold total return for this stock, to measure "beat the market".
        bh = dv.backtest(df, lambda d: pd.Series(1.0, index=d.index), cost=cost)
        bh_return = bh.metrics["Total return"]
        for label, make in STRATEGIES.items():
            r = dv.backtest(df, make(), cost=cost, strategy_name=label)
            m = r.metrics
            rows.append(
                {
                    "strategy": label,
                    "ticker": ticker,
                    "total_return": m["Total return"],
                    "cagr": m["CAGR"],
                    "sharpe": m["Sharpe"],
                    "max_drawdown": m["Max drawdown"],
                    "win_rate": m["Win rate"],
                    "trades": m["Trades"],
                    "beat_buyhold": m["Total return"] > bh_return,
                }
            )
    per_stock = pd.DataFrame(rows)

    # Aggregate across stocks, per strategy. Medians resist outliers better than means.
    summary = (
        per_stock.groupby("strategy")
        .agg(
            stocks=("ticker", "nunique"),
            median_cagr=("cagr", "median"),
            median_sharpe=("sharpe", "median"),
            median_max_dd=("max_drawdown", "median"),
            avg_win_rate=("win_rate", "mean"),
            pct_beat_buyhold=("beat_buyhold", "mean"),
            pct_profitable=("total_return", lambda s: float((s > 0).mean())),
        )
        # Keep the strategy order stable rather than alphabetical.
        .reindex(list(STRATEGIES))
    )
    return summary, per_stock


def format_summary(summary: pd.DataFrame) -> str:
    """Format the aggregate summary table for printing."""
    disp = pd.DataFrame(index=summary.index)
    disp["stocks"] = summary["stocks"].astype(int)
    disp["med CAGR"] = summary["median_cagr"].map(lambda v: f"{v * 100:+.1f}%")
    disp["med Sharpe"] = summary["median_sharpe"].map(lambda v: f"{v:.2f}")
    disp["med maxDD"] = summary["median_max_dd"].map(lambda v: f"{v * 100:.1f}%")
    disp["avg win"] = summary["avg_win_rate"].map(lambda v: f"{v * 100:.0f}%")
    disp["beat B&H"] = summary["pct_beat_buyhold"].map(lambda v: f"{v * 100:.0f}%")
    disp["profitable"] = summary["pct_profitable"].map(lambda v: f"{v * 100:.0f}%")
    return disp.to_string()


def plot_summary(summary: pd.DataFrame, n_stocks: int, outpath: str) -> None:
    """Two bar charts: % of stocks that beat buy-&-hold, and median Sharpe."""
    labels = list(summary.index)
    colors = [theme_palette()[i % len(theme_palette())] for i in range(len(labels))]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ax1.barh(labels, summary["pct_beat_buyhold"] * 100, color=colors)
    ax1.axvline(50, color=INK, linewidth=1.0, linestyle="--", alpha=0.6)  # 50% reference
    style_axes(ax1, title=f"% of {n_stocks} stocks that beat buy-&-hold", xlabel="%")
    add_time_grid(ax1, False)
    ax1.invert_yaxis()

    ax2.barh(labels, summary["median_sharpe"], color=colors)
    ax2.axvline(0, color=INK, linewidth=1.0, alpha=0.6)
    style_axes(ax2, title="Median Sharpe ratio", xlabel="Sharpe")
    add_time_grid(ax2, False)
    ax2.invert_yaxis()

    fig.suptitle("Strategy study — aggregate results", color=INK, fontsize=15,
                 fontweight="bold", x=0.02, ha="left")
    fig.tight_layout()
    dv.save(fig, outpath)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Study strategies across many stocks.")
    parser.add_argument("--tickers", nargs="+", help="Tickers to use (default: built-in ~34).")
    parser.add_argument("--period", default="20y", help="History length (default 20y).")
    parser.add_argument("--interval", default="1d", help="Bar interval (default 1d).")
    parser.add_argument("--synthetic", type=int, metavar="N", help="Use N synthetic stocks.")
    parser.add_argument("--bars", type=int, default=5040, help="Synthetic history length (~20y).")
    parser.add_argument("--min-bars", type=int, default=252, help="Skip stocks shorter than this.")
    parser.add_argument("--cost", type=float, default=0.001, help="Cost per trade (default 0.001).")
    parser.add_argument("--outdir", default="strategy_study", help="Output dir.")
    parser.add_argument("--no-plots", action="store_true", help="Only print / write CSV.")
    parser.add_argument("--show", action="store_true", help="Display the chart too.")
    args = parser.parse_args(argv)

    # --- Load the universe ----------------------------------------------------
    if args.synthetic:
        print(f"Building a synthetic universe of {args.synthetic} stocks ({args.bars} bars)...")
        data = synthetic_universe(args.synthetic, args.bars)
    else:
        tickers = args.tickers or DEFAULT_UNIVERSE
        print(f"Fetching {len(tickers)} tickers, period={args.period} (this can take a minute)...")
        data = load_universe(tickers, args.period, args.interval, args.min_bars)
        if not data:
            print("\nNo data could be fetched (no network, or yfinance not installed?).")
            print("Try the offline mode:  python examples/strategy_study.py --synthetic 30")
            return

    print(f"Studying {len(data)} stocks across {len(STRATEGIES)} strategies...\n")

    # --- Run and report -------------------------------------------------------
    summary, per_stock = run_study(data, args.cost)
    print(format_summary(summary))

    best = summary["pct_beat_buyhold"].idxmax()
    print(
        f"\nMost often beat buy-&-hold: {best} "
        f"({summary.loc[best, 'pct_beat_buyhold'] * 100:.0f}% of stocks)."
    )
    print(
        "\nReminder: survivorship-biased universe + in-sample parameters — this is a\n"
        "learning exercise in comparing rules, NOT evidence any of them makes money."
    )

    # --- Save artifacts -------------------------------------------------------
    import os

    os.makedirs(args.outdir, exist_ok=True)
    per_stock.to_csv(os.path.join(args.outdir, "per_stock.csv"), index=False)
    summary.to_csv(os.path.join(args.outdir, "summary.csv"))
    if not args.no_plots:
        plot_summary(summary, len(data), os.path.join(args.outdir, "study_summary.png"))
    print(f"\nSaved results to {args.outdir}/ (per_stock.csv, summary.csv, study_summary.png)")

    if args.show:
        dv.show()


if __name__ == "__main__":
    main()
