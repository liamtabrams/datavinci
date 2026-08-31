"""Tests for datavinci.data helpers that don't need the network."""

import pytest

from datavinci.data import load_ticker


def test_load_ticker_rejects_invalid_period():
    # "20y" is not a valid yfinance period; this must fail fast with a clear
    # message BEFORE any network call (so the test needs no connection).
    pytest.importorskip("yfinance")
    with pytest.raises(ValueError, match="Invalid period"):
        load_ticker("AAPL", period="20y")
