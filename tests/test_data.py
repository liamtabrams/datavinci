"""Tests for datavinci.data helpers that don't need the network."""

import pandas as pd
import pytest

import datavinci.data as dvdata
from datavinci.data import _period_to_start, load_ticker


def test_load_ticker_rejects_invalid_period():
    # "20y" is not a valid yfinance period; this must fail fast with a clear
    # message BEFORE any network call (so the test needs no connection).
    pytest.importorskip("yfinance")
    with pytest.raises(ValueError, match="Invalid period"):
        load_ticker("AAPL", period="20y")


def test_load_ticker_rejects_unknown_source():
    with pytest.raises(ValueError, match="Unknown source"):
        load_ticker("AAPL", source="bogus")


def test_period_to_start():
    assert _period_to_start("max") is None
    # A 5-year window should start roughly 5 years ago.
    start = pd.Timestamp(_period_to_start("5y"))
    years_ago = (pd.Timestamp.today() - start).days / 365.25
    assert 4.5 < years_ago < 5.5


def test_stooq_parses_and_sorts(monkeypatch):
    # Stooq returns newest-or-oldest-first CSV text; we sort ascending and keep OHLCV.
    fake = pd.DataFrame(
        {
            "Date": ["2020-01-03", "2020-01-02"],  # descending on purpose
            "Open": [2.0, 1.0],
            "High": [2.0, 1.0],
            "Low": [2.0, 1.0],
            "Close": [2.0, 1.0],
            "Volume": [200, 100],
        }
    )
    monkeypatch.setattr(dvdata.pd, "read_csv", lambda url: fake.copy())

    df = load_ticker("AAPL", source="stooq", start="2020-01-01")
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing          # sorted oldest-first
    assert df["Close"].iloc[0] == 1.0                # earliest row first


def test_stooq_no_data_raises(monkeypatch):
    # A bad symbol returns a frame without a Date column ("No data").
    monkeypatch.setattr(dvdata.pd, "read_csv", lambda url: pd.DataFrame({"No data": [1]}))
    with pytest.raises(ValueError, match="No Stooq data"):
        load_ticker("NOTATICKER", source="stooq")
