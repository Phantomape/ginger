from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_layer import get_earnings_data  # noqa: E402


def test_earnings_dates_preserves_estimate_source_and_event_identity() -> None:
    index = pd.to_datetime(["2026-08-06T16:00:00-04:00"])
    dates = pd.DataFrame(
        {
            "EPS Estimate": [0.58],
            "Reported EPS": [None],
            "Fiscal Quarter": ["Q2 2026"],
        },
        index=index,
    )

    row = get_earnings_data("DDOG", as_of=date(2026, 7, 21), dates_df=dates)

    assert row["eps_estimate"] == 0.58
    assert row["eps_estimate_source"] == "yfinance.get_earnings_dates.EPS Estimate"
    assert row["eps_estimate_event_date"] == "2026-08-06"
    assert row["eps_estimate_fiscal_period"] == "Q2 2026"


def test_info_fallback_is_source_labeled_but_not_fabricated_as_event_vintage() -> None:
    row = get_earnings_data(
        "DDOG",
        as_of=None,
        dates_df=pd.DataFrame(),
        calendar=None,
        info={"forwardEps": 1.25},
    )

    assert row["eps_estimate"] == 1.25
    assert row["eps_estimate_source"] == "yfinance.info.forwardEps"
    assert row.get("eps_estimate_event_date") is None
