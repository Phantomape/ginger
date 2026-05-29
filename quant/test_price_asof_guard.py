from __future__ import annotations

from price_asof_guard import filter_prices_for_asof, latest_ohlcv_dates


def test_filter_prices_for_asof_keeps_backward_compatible_undated_maps():
    assert filter_prices_for_asof({"AAA": 10.0}, None, as_of="2026-05-05") == {
        "AAA": 10.0
    }


def test_filter_prices_for_asof_drops_stale_ticker_dates():
    prices = {"AAA": 10.0, "BBB": 20.0}
    dates = {"AAA": "2026-05-04", "BBB": "2026-05-05"}

    assert filter_prices_for_asof(prices, dates, as_of="2026-05-05") == {
        "BBB": 20.0
    }


def test_latest_ohlcv_dates_reads_list_rows():
    dates = latest_ohlcv_dates(
        {
            "AAA": [
                {"date": "2026-05-04", "close": 10.0},
                {"date": "2026-05-05", "close": 11.0},
            ]
        }
    )

    assert dates == {"AAA": "2026-05-05"}
