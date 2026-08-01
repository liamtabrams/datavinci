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

## Project layout

```
datavinci/
├── pyproject.toml          # setuptools packaging + metadata
├── src/datavinci/          # the importable package (src layout)
│   ├── __init__.py
│   ├── convenience.py      # chart / dashboard / save / show
│   ├── timeseries.py       # line / moving_average / candlestick
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
