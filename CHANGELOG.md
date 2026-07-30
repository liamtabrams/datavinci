# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]
### Added
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
