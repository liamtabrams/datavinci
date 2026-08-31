"""Educational backtest demo — run a strategy and render a tearsheet.

    python examples/backtest_demo.py

Uses offline synthetic data by default (no network). To try a real ticker,
install the finance extra (`pip install "datavinci[finance]"`) and swap in the
load_ticker line below.

This is for learning and visualization only — NOT investment advice.
"""

import datavinci as dv
from datavinci.data import sample_ohlc

# --- 1. Get some price data ---------------------------------------------------
df = sample_ohlc(periods=500, seed=5)
# Real data instead (needs the [finance] extra + network):
# from datavinci.data import load_ticker
# df = load_ticker("AAPL", period="3y")

# --- 2. Pick a strategy -------------------------------------------------------
# A strategy is just a function (df -> position signal). Try swapping these:
strategy = dv.strategies.sma_crossover(fast=20, slow=50)
# strategy = dv.strategies.rsi_meanreversion(period=14, low=30, high=70)
# strategy = dv.strategies.bollinger_breakout(period=20, num_std=2)

# --- 3. Backtest it -----------------------------------------------------------
# cost=0.001 charges 10 basis points of trading cost each time we trade. The
# signal is automatically delayed one bar so we never trade on same-bar info.
result = dv.backtest(df, strategy, cost=0.001, strategy_name="SMA 20/50 crossover")

# --- 4. Look at the results ---------------------------------------------------
print(result.summary())
print("\nFirst few trades:")
print(result.trades.head().to_string(index=False))

# --- 5. Render the tearsheet --------------------------------------------------
fig = dv.tearsheet(result)
dv.save(fig, "backtest_tearsheet.png")
print("\nSaved backtest_tearsheet.png")
# dv.show()   # uncomment to pop up the window instead
