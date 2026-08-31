# datavinci

A friendly, lightweight wrapper around **matplotlib** for plotting **time-series
and financial ticker data** — with a polished dark "trading terminal" look and
**colorblind-safe defaults**, out of the box.

`datavinci` turns fiddly recipes (candlesticks, moving averages, volume panels)
into one-line calls. Name a ticker and you get a styled chart; every function
returns a plain matplotlib `Axes`/`Figure`, so you can keep customizing with the
full matplotlib API.

![datavinci price & volume dashboard](https://raw.githubusercontent.com/liamtabrams/datavinci/main/assets/hero_dashboard.png)

> Built for the USF MSDS & AI program as a from-scratch data-visualization
> package. Starts with time series (tested against Yahoo Finance ticker data)
> and grows from there.

## Installation

```bash
pip install datavinci

# with live Yahoo Finance data loading:
pip install "datavinci[finance]"
```

## Quick start

The one-call front door — name a ticker and get a chart (fetches live data):

```python
import datavinci as dv

dv.chart("AAPL", "6mo")          # auto-detects OHLC → candlestick
dv.dashboard("AAPL", "6mo")      # stacked price + volume, one call
dv.show()                        # display (no need to import matplotlib)
```

`chart()` and `dashboard()` also accept a **file path**, a **DataFrame**, or a
**Series**, so they work fully offline too:

```python
import datavinci as dv
from datavinci.data import sample_ohlc

df = sample_ohlc(periods=120)            # synthetic OHLC+Volume, no network

dv.chart(df)                             # candlestick (auto-detected)
dv.chart(df, kind="ma", windows=(10, 30))# price + moving averages
dv.chart("prices.csv")                   # read a CSV from disk
dv.dashboard(df, save="dashboard.png")   # draw and export in one line
```

`save=` (and the standalone `dv.save(ax_or_fig, path)`) write the file with the
dark background preserved — no ugly white border.

## Themes & accessibility

Charts are **colorblind-safe by default**. The default `"colorblind"` theme uses
blue-up / red-down candles (moving "up" off the red-green confusion axis) and
draws **down candles hollow** — a redundant, hue-independent channel so gain vs.
loss is legible even in grayscale. The categorical accent palette was validated
against color-vision-deficiency separation gates.

Prefer the brighter neon look? Switch themes:

```python
dv.use_theme("terminal")     # green/red filled candles, brighter accents
dv.use_theme("colorblind")   # back to the default
dv.available_themes()        # ['colorblind', 'terminal']
```

## Aesthetic choices

The look is a dark trading-terminal theme, applied **per-Axes** — importing
`datavinci` never mutates global matplotlib `rcParams`, so your other plots keep
their normal style. Key touches:

- **Gradient backdrop** behind each axes and a **gradient fill** beneath price.
- **Subtle rim-light glow** on lines — a hint of depth, tuned back from a heavier
  neon bloom.
- **Drop-shadowed candle bodies** for a raised, 3D feel.
- **Vertical time-span grid lines** with a concise date formatter.
- **Recessive grid/spines** and **monospace price ticks** so the data leads.

| ![candlestick + volume](https://raw.githubusercontent.com/liamtabrams/datavinci/main/assets/hero_dashboard.png) | ![moving averages](https://raw.githubusercontent.com/liamtabrams/datavinci/main/assets/line_ma.png) |
| --- | --- |
| `dv.dashboard(df)` | `dv.chart(df, kind="ma")` |

## API

| Function | What it does |
| --- | --- |
| `datavinci.chart(source, period="1y", kind="auto", ...)` | One-call chart from a ticker symbol, file path, DataFrame, or Series. |
| `datavinci.dashboard(source, ...)` | Stacked price + volume dashboard (candles + optional SMAs + volume bars). |
| `datavinci.candlestick(df, ...)` | OHLC candlestick chart from a ticker DataFrame. |
| `datavinci.line(data, columns=None, ...)` | Line chart for a Series or selected DataFrame columns. |
| `datavinci.moving_average(data, windows=(20, 50), ...)` | A series plus simple moving-average overlays. |
| `datavinci.save(ax_or_fig, path)` | Save with the dark theme background preserved. |
| `datavinci.show()` | Passthrough to `matplotlib.pyplot.show`. |
| `datavinci.use_theme(name)` | Switch theme (`"colorblind"` default, or `"terminal"`). |
| `datavinci.data.sample_ohlc(...)` | Generate synthetic OHLC+Volume data (offline). |
| `datavinci.data.load_ticker(symbol, ...)` | Download OHLC data from Yahoo Finance (`[finance]` extra). |

Plotting functions accept an optional `ax=` and return the `Axes` they drew on;
`dashboard()` returns the `Figure`.

## Backtesting (educational)

datavinci includes a small, **transparent** backtester so you can test a simple
trading rule and see how it would have performed — then render a polished
performance report. It is built for **learning and visualization, not live
trading, and is not investment advice.** Backtested results never guarantee
future performance.

```python
import datavinci as dv
from datavinci.data import sample_ohlc

df = sample_ohlc(periods=400)                       # or load_ticker("AAPL", period="2y")

strat  = dv.strategies.sma_crossover(fast=20, slow=50)   # a trading rule
result = dv.backtest(df, strat, cost=0.001)              # simulate it (10 bps/trade)

print(result.summary())                             # metrics as text
fig = dv.tearsheet(result)                           # the visual report
dv.save(fig, "tearsheet.png")
```

**How the backtest works (and why you can trust it).** Given price data and a
`signal` (the position to hold each bar: `+1` long, `0` flat, `-1` short), it:

1. **Delays the signal by one bar** — `position = signal.shift(1)`. You act on a
   signal on the *next* bar, so a rule computed at today's close can't trade on
   today's move. This is the key guard against **lookahead bias** (accidentally
   using information you wouldn't have had — the #1 way backtests lie).
2. Computes asset returns `r[t] = Close[t]/Close[t-1] − 1`.
3. Strategy return before costs = `position × r`.
4. **Charges a trading cost whenever the position changes** (`cost` per unit of
   turnover) — so a strategy that trades constantly is penalized realistically.
5. Compounds the net returns into an **equity curve**, alongside a buy-&-hold
   baseline for comparison.

Everything is stored on `result.history` (a DataFrame) so you can inspect or
re-plot any column.

**Strategies** are just functions `df → signal`. Three are included, and you can
write your own:

| Strategy | Idea |
| --- | --- |
| `dv.strategies.sma_crossover(fast, slow)` | Long while the fast moving average is above the slow one (trend-following). |
| `dv.strategies.rsi_meanreversion(period, low, high)` | Buy when oversold (RSI < `low`), exit when recovered (RSI > `high`). |
| `dv.strategies.bollinger_breakout(period, num_std)` | Go long on a breakout above the upper Bollinger band. |

The `tearsheet()` report shows the metrics, the price with entry/exit markers,
the equity curve vs. buy-&-hold, and the drawdown. Metrics include total return,
CAGR, annualized volatility, Sharpe, Sortino, max drawdown, Calmar, win rate, and
exposure.

> **Beginner traps this tool guards against — but you should still know:**
> lookahead bias (handled by the one-bar delay), ignoring costs (handled by
> `cost`), and **overfitting** (tuning parameters until the past looks great —
> always sanity-check on data you didn't tune on). See `examples/backtest_demo.py`.

## Project layout

```
datavinci/
├── pyproject.toml          # setuptools packaging + metadata
├── src/datavinci/          # the importable package (src layout)
│   ├── __init__.py
│   ├── convenience.py      # chart / dashboard / save / show
│   ├── timeseries.py       # line / moving_average / candlestick
│   ├── backtest.py         # backtest / tearsheet (educational)
│   ├── strategies.py       # sma_crossover / rsi / bollinger + indicators
│   ├── data.py             # sample_ohlc / load_ticker
│   └── _theme.py           # themes, palettes, effects
├── tests/                  # pytest suite (offline, Agg backend)
├── examples/               # runnable demos
└── .github/workflows/      # CI (tests) + PyPI publish on release
```

## Development

```bash
pip install -e ".[dev]"
pytest            # run the test suite (offline)
ruff check .      # lint
python -m build   # build sdist + wheel into dist/
```

## License

MIT — see [LICENSE](LICENSE).
