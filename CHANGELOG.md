# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-07-23
### Added
- Initial package scaffold (setuptools, src layout).
- `datavinci.line` — styled line charts for Series / DataFrame columns.
- `datavinci.moving_average` — a series with simple moving-average overlays.
- `datavinci.candlestick` — OHLC candlestick charts for ticker data.
- `datavinci.data.sample_ohlc` — offline synthetic OHLC generator.
- `datavinci.data.load_ticker` — optional Yahoo Finance loader (`[finance]` extra).
- Offline pytest suite, runnable Yahoo Finance demo, and GitHub Actions CI + publish workflows.
