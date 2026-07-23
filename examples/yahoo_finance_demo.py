"""End-to-end demo: plot a Yahoo Finance ticker with datavinci.

Run it with real data (needs the finance extra: ``pip install "datavinci[finance]"``)::

    python examples/yahoo_finance_demo.py AAPL

Or with no network / no arguments, it falls back to synthetic sample data so the
demo always produces a chart.
"""

import sys

import matplotlib.pyplot as plt

import datavinci as dv
from datavinci.data import load_ticker, sample_ohlc


def get_data(symbol: str | None):
    if symbol is None:
        print("No symbol given — using synthetic sample data.")
        return "SAMPLE", sample_ohlc(periods=180)
    try:
        print(f"Downloading {symbol} from Yahoo Finance...")
        return symbol, load_ticker(symbol, period="6mo")
    except Exception as exc:  # network down, bad symbol, or yfinance missing
        print(f"Could not load {symbol} ({exc}). Falling back to sample data.")
        return "SAMPLE", sample_ohlc(periods=180)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else None
    label, df = get_data(symbol)

    fig, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

    dv.candlestick(df, ax=ax_top, title=f"{label} — Candlestick")
    dv.moving_average(df["Close"], windows=(20, 50), ax=ax_bottom, title=f"{label} — Close + SMAs")

    fig.tight_layout()
    out = "datavinci_demo.png"
    fig.savefig(out, dpi=120)
    print(f"Saved chart to {out}")


if __name__ == "__main__":
    main()
