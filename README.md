# datavinci

A friendly, lightweight wrapper around **matplotlib** for plotting **time-series
and financial ticker data**. `datavinci` turns fiddly recipes — candlesticks,
moving averages, cleanly styled line charts — into one-line calls that return a
plain matplotlib `Axes`, so you can keep customizing with the full matplotlib API.

> Built for the USF MSDS & AI program as a from-scratch data-visualization
> package intended for PyPI. Starting with time series (tested against Yahoo
> Finance ticker data) and growing from there.

## Installation

From source (development):

```bash
pip install -e ".[dev]"
```

Once published to PyPI:

```bash
pip install datavinci
# with Yahoo Finance data loading:
pip install "datavinci[finance]"
```

## Quick start

```python
import datavinci as dv
from datavinci.data import sample_ohlc

# Synthetic OHLC data — no network required.
df = sample_ohlc(periods=120)

# Candlestick chart (returns a matplotlib Axes).
ax = dv.candlestick(df, title="Demo ticker")

# Closing price with 20- and 50-period moving averages.
ax = dv.moving_average(df["Close"], windows=(20, 50), title="Close + SMAs")

# One or more series as clean line charts.
ax = dv.line(df, columns=["Open", "Close"], title="Open vs Close")
```

### With real Yahoo Finance data

```python
from datavinci.data import load_ticker
import datavinci as dv

df = load_ticker("AAPL", period="6mo")   # requires: pip install "datavinci[finance]"
dv.candlestick(df, title="AAPL — 6 months")
```

See [`examples/yahoo_finance_demo.py`](examples/yahoo_finance_demo.py) for a full
runnable script.

## API

| Function | What it does |
| --- | --- |
| `datavinci.line(data, columns=None, ...)` | Line chart for a Series or selected DataFrame columns. |
| `datavinci.moving_average(data, windows=(20, 50), ...)` | A series plus simple moving-average overlays. |
| `datavinci.candlestick(df, ...)` | OHLC candlestick chart from a ticker DataFrame. |
| `datavinci.data.sample_ohlc(...)` | Generate synthetic OHLC data (offline). |
| `datavinci.data.load_ticker(symbol, ...)` | Download OHLC data from Yahoo Finance. |

Every plotting function accepts an optional `ax=` and returns the `Axes` it drew on.

## Project layout

```
datavinci/
├── pyproject.toml          # setuptools packaging + metadata
├── src/datavinci/          # the importable package (src layout)
│   ├── __init__.py
│   ├── timeseries.py       # line / moving_average / candlestick
│   ├── data.py             # sample_ohlc / load_ticker
│   └── _theme.py           # shared styling + palette
├── tests/                  # pytest suite (offline, Agg backend)
├── examples/               # runnable demos
└── .github/workflows/      # CI (tests) + PyPI publish on release
```

## Development

```bash
pip install -e ".[dev]"
pytest            # run the test suite
ruff check .      # lint
python -m build   # build sdist + wheel into dist/
```

## Publishing to PyPI

1. Bump `__version__` in `src/datavinci/__init__.py`.
2. Build: `python -m build`
3. Upload: `python -m twine upload dist/*`

The included GitHub Actions workflow (`.github/workflows/publish.yml`) can do
this automatically when you create a GitHub Release — see the notes at the top of
that file for configuring PyPI Trusted Publishing.

## License

MIT — see [LICENSE](LICENSE).
