# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]
### Fixed
- `load_ticker` now **validates the period** (rejecting invalid strings like
  `"20y"` with a clear message), supports `start`/`end` dates for long windows,
  and **retries on transient/empty responses** — Yahoo rate-limits bursts, which
  made valid symbols intermittently fail with a misleading "possibly delisted".
- `load_ticker` gained a **`source="stooq"`** option — a free, key-free
  alternative data provider for when Yahoo throttles or yfinance breaks against
  Yahoo's API (the `Expecting value: line 1 column 1` error). `strategy_study.py`
  exposes it via `--source stooq`.
- The `finance` extra now installs **`curl_cffi>=0.15`** (and `yfinance>=0.2.40`).
  yfinance needs curl_cffi to mimic a browser's TLS fingerprint; without it Yahoo
  blocks the client and returns empty data — the actual root cause of the fetch
  failures above.
- `strategy_study.py` now fetches a real 20-year window via a `start` date
  (`--years`, default 20) instead of the invalid `period="20y"`, pauses between
  requests (`--pause`), and reports how many tickers were fetched.

### Added
- **Educational backtesting.** `datavinci.backtest(df, strategy, cost=...)` runs a
  transparent, single-asset backtest with a built-in one-bar lookahead guard and
  transaction costs, returning a `BacktestResult` (per-bar `history`, a per-trade
  log, and summary metrics: total return, CAGR, volatility, Sharpe, Sortino, max
  drawdown, Calmar, win rate, exposure). `datavinci.tearsheet(result)` renders a
  themed 4-panel report (metrics, price with trade markers, equity vs. buy-&-hold,
  drawdown). `datavinci.strategies` ships `sma_crossover`, `rsi_meanreversion`,
  `bollinger_breakout`, and `macd_crossover`, plus `rsi`, `bollinger_bands`, and
  `macd` indicator helpers. The README documents each strategy in plain English
  with a usage example. For learning/visualization only — not investment advice.
- `examples/compare_strategies.py` — a CLI script that backtests every built-in
  strategy (plus buy-&-hold) on the same data, prints a metrics comparison table,
  and saves an overlaid equity-curve chart and per-strategy tearsheets. Works
  offline by default; `--ticker AAPL` fetches real data (with graceful fallback).
- `examples/strategy_study.py` — a CLI study that runs every strategy across a
  universe of stocks (built-in ~34-name list, `--tickers`, or `--synthetic N`)
  over ~20 years and aggregates the results: median CAGR/Sharpe/drawdown, average
  win rate, and the share of stocks that beat buy-&-hold, with a summary chart and
  a per-stock CSV. Prominently documents its survivorship bias and other caveats.
- `datavinci.dashboard(source, ...)` — a stacked **price + volume** dashboard in
  one call, with candlesticks (plus optional SMA overlays) on top, direction-colored
  volume bars below, an aligned shared x-axis, and a humanized volume axis
  (`1.2M`/`850K`). Accepts the same sources as `chart()`; returns the `Figure`.
- `datavinci.chart(source, period=...)` — a one-call front door. `source` may be
  a **ticker symbol** (`"AAPL"`, fetched live from Yahoo Finance), a **file path**
  (`.csv`/`.tsv`/`.parquet`/`.json`, read offline), or a **DataFrame**/**Series**
  you already have. It auto-detects OHLC data to pick candlestick vs. line
  (override with `kind="candle"|"line"|"ma"`), auto-titles ticker charts with the
  symbol, and normalizes lowercase `open/high/low/close` column names.
- `save=` shortcut on both `chart()` and `dashboard()` — draw and write in one call
  (e.g. `dv.chart("AAPL", save="aapl.png")`).
- `sample_ohlc()` now includes a synthetic `Volume` column, matching the shape of
  Yahoo Finance data (so dashboards work offline).
- `datavinci.save(ax_or_fig, path)` — saves with the dark theme background baked
  in (no white border), with `transparent=` and `dpi=` options.
- `datavinci.show()` — a passthrough to `pyplot.show()` so you never need to
  import matplotlib directly.
- Switchable chart themes via `datavinci.use_theme(...)`, with `active_theme()`
  and `available_themes()` helpers. Two themes ship: `"colorblind"` (the default)
  and `"terminal"` (opt-in neon look).
- `"colorblind"` theme for color-vision-deficiency (CVD) safety: blue-up /
  red-down candles (keeps the finance "loss = red" convention while moving "up"
  off the red-green confusion axis — CVD ΔE 24.2 vs 10.5 for green/red), a
  validator-passing categorical accent palette, and **hollow down candles** —
  a redundant, hue-independent structural channel so gain/loss stays legible
  even in grayscale. Palettes were checked with the dataviz validator against
  datavinci's dark surfaces.
- `candlestick()` gained a `hollow_down` toggle to enable the hollow-body channel
  independently of the active theme.

### Changed
- Softened the line glow to a subtle rim-light (was a heavier neon bloom). Tunable
  via `glow()`'s new `layers`/`spread`/`alpha_step` parameters.
- New dark "pro terminal" chart theme replacing the plain matplotlib look:
  gradient backdrop, glowing lines, drop-shadowed candle bodies and titles,
  vertical time-span grid lines, gradient fill beneath price, and a
  CVD-validated categorical accent palette. Public function signatures are
  unchanged; `line()` gained a `fill` toggle.

## [0.1.0] - 2026-07-23
### Added
- Initial package scaffold (setuptools, src layout).
- `datavinci.line` — styled line charts for Series / DataFrame columns.
- `datavinci.moving_average` — a series with simple moving-average overlays.
- `datavinci.candlestick` — OHLC candlestick charts for ticker data.
- `datavinci.data.sample_ohlc` — offline synthetic OHLC generator.
- `datavinci.data.load_ticker` — optional Yahoo Finance loader (`[finance]` extra).
- Offline pytest suite, runnable Yahoo Finance demo, and GitHub Actions CI + publish workflows.
