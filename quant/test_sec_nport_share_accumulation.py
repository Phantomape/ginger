from __future__ import annotations

import gzip
import json
import sys
from copy import deepcopy
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from sec_nport_share_accumulation import (  # noqa: E402
    MAX_REPORT_GAP_DAYS,
    MIN_MATCHED_SERIES,
    MIN_REPORT_GAP_DAYS,
    NEGATIVE_SCALAR,
    NEUTRAL_SCALAR,
    POSITIVE_SCALAR,
    SPLIT_FACTOR_TOLERANCE,
    annotate_signal,
    compute_share_accumulation,
    infer_integer_split_factor,
    load_nport_rows,
)


def _report(
    series: str,
    report_date: str,
    filing_date: str,
    accession: str,
) -> dict:
    return {
        "accession": accession,
        "series_id": series,
        "report_date": report_date,
        "filing_date": filing_date,
    }


def _holding(
    series: str,
    report_date: str,
    filing_date: str,
    accession: str,
    balance: float,
    *,
    price: float = 100.0,
    ticker: str = "ABC",
) -> dict:
    return {
        **_report(series, report_date, filing_date, accession),
        "ticker": ticker,
        "balance": balance,
        "currency_value": balance * price,
    }


def _two_quarters(
    count: int = MIN_MATCHED_SERIES,
    *,
    previous_balance: float = 10.0,
    current_balance: float = 11.0,
    current_report_date: str = "2024-06-30",
) -> tuple[list[dict], list[dict]]:
    reports: list[dict] = []
    holdings: list[dict] = []
    for index in range(count):
        series = f"S{index:04d}"
        previous_accession = f"P{index:04d}"
        current_accession = f"C{index:04d}"
        reports.extend(
            [
                _report(series, "2024-03-31", "2024-05-15", previous_accession),
                _report(
                    series,
                    current_report_date,
                    "2024-08-15",
                    current_accession,
                ),
            ]
        )
        holdings.extend(
            [
                _holding(
                    series,
                    "2024-03-31",
                    "2024-05-15",
                    previous_accession,
                    previous_balance,
                ),
                _holding(
                    series,
                    current_report_date,
                    "2024-08-15",
                    current_accession,
                    current_balance,
                ),
            ]
        )
    return holdings, reports


def test_strict_pit_and_latest_amendment_as_of_action_date() -> None:
    holdings, reports = _two_quarters()
    for index in range(MIN_MATCHED_SERIES):
        series = f"S{index:04d}"
        amendment = f"A{index:04d}"
        reports.append(_report(series, "2024-06-30", "2024-08-20", amendment))
        holdings.append(
            _holding(
                series,
                "2024-06-30",
                "2024-08-20",
                amendment,
                5.0,
            )
        )
    dataset = load_nport_rows(holdings, reports)

    # Same-day filings are forbidden by the strict clock, so the original
    # current filing (11 shares) remains the latest available submission.
    same_day = compute_share_accumulation(
        dataset, action_date="2024-08-20", ticker="ABC"
    )
    assert same_day["status"] == "positive"
    assert same_day["current_sum"] == MIN_MATCHED_SERIES * 11.0

    # On the following day the amendment is public and wins for its
    # series/report-date.
    next_day = compute_share_accumulation(
        dataset, action_date="2024-08-21", ticker="ABC"
    )
    assert next_day["status"] == "negative"
    assert next_day["current_sum"] == MIN_MATCHED_SERIES * 5.0


def test_sold_to_zero_is_counted_in_union_of_continuous_reporters() -> None:
    holdings, reports = _two_quarters(current_balance=8.0)
    # Absence from a selected current accession is a real zero because the
    # all-series report table proves that the series filed that quarter.
    holdings = [
        row
        for row in holdings
        if not (
            row["accession"].startswith("C")
            and int(row["series_id"][1:]) < 10
        )
    ]
    result = compute_share_accumulation(
        load_nport_rows(holdings, reports),
        action_date="2024-08-21",
        ticker="ABC",
    )

    assert result["matched_series_count"] == MIN_MATCHED_SERIES
    assert result["sold_to_zero_series_count"] == 10
    assert result["continuous_holder_series_count"] == 10
    assert result["status"] == "negative"
    assert result["scalar"] == NEGATIVE_SCALAR


def test_report_gap_and_minimum_coverage_are_hard_gates() -> None:
    short_holdings, short_reports = _two_quarters(
        current_report_date="2024-05-31"
    )
    short = compute_share_accumulation(
        load_nport_rows(short_holdings, short_reports),
        action_date="2024-08-21",
        ticker="ABC",
    )
    assert short["reason"] == "no_pit_continuous_report_pairs"
    assert short["scalar"] == NEUTRAL_SCALAR

    holdings, reports = _two_quarters(count=MIN_MATCHED_SERIES - 1)
    insufficient = compute_share_accumulation(
        load_nport_rows(holdings, reports),
        action_date="2024-08-21",
        ticker="ABC",
    )
    assert insufficient["matched_series_count"] == MIN_MATCHED_SERIES - 1
    assert insufficient["reason"] == "insufficient_matched_series"
    assert insufficient["score"] is None
    assert insufficient["scalar"] == NEUTRAL_SCALAR
    assert insufficient["policy"] == {
        "min_matched_series": 20,
        "min_report_gap_days": MIN_REPORT_GAP_DAYS,
        "max_report_gap_days": MAX_REPORT_GAP_DAYS,
        "positive_scalar": POSITIVE_SCALAR,
        "negative_scalar": NEGATIVE_SCALAR,
        "neutral_scalar": NEUTRAL_SCALAR,
        "split_min_samples": 20,
        "split_factor_tolerance": SPLIT_FACTOR_TOLERANCE,
        "split_integer_min": 2,
        "split_integer_max": 50,
    }


def test_fixed_scalar_sign_contract() -> None:
    positive_holdings, reports = _two_quarters(current_balance=11.0)
    positive = compute_share_accumulation(
        load_nport_rows(positive_holdings, reports),
        action_date="2024-08-21",
        ticker="ABC",
    )
    assert positive["status"] == "positive"
    assert positive["scalar"] == POSITIVE_SCALAR

    negative_holdings, negative_reports = _two_quarters(current_balance=9.0)
    negative = compute_share_accumulation(
        load_nport_rows(negative_holdings, negative_reports),
        action_date="2024-08-21",
        ticker="ABC",
    )
    assert negative["status"] == "negative"
    assert negative["scalar"] == NEGATIVE_SCALAR

    flat_holdings, flat_reports = _two_quarters(current_balance=10.0)
    flat = compute_share_accumulation(
        load_nport_rows(flat_holdings, flat_reports),
        action_date="2024-08-21",
        ticker="ABC",
    )
    assert flat["status"] == "neutral"
    assert flat["scalar"] == NEUTRAL_SCALAR


def test_split_factor_uses_implied_over_frozen_adjusted_price_cross_section() -> None:
    assert infer_integer_split_factor([4.02] * 20) == 4.0
    assert infer_integer_split_factor([0.249] * 20) == 0.25
    assert infer_integer_split_factor([4.0] * 19) == 1.0
    assert infer_integer_split_factor([1.4] * 20) == 1.0

    holdings, reports = _two_quarters(
        previous_balance=10.0, current_balance=10.0
    )
    # N-PORT reports an unadjusted implied price of $100 for the first report,
    # while the frozen adjusted warehouse close is $25.  The 4-for-1 factor
    # multiplies historical balances, turning a raw-flat series negative.
    dataset = load_nport_rows(
        holdings,
        reports,
        adjusted_close_by_ticker_date={
            ("ABC", "2024-03-31"): 25.0,
            ("ABC", "2024-06-30"): 100.0,
        },
    )
    result = compute_share_accumulation(
        dataset, action_date="2024-08-21", ticker="ABC"
    )
    assert result["previous_sum_raw"] == result["current_sum_raw"]
    assert result["split_factors"]["2024-03-31"]["factor"] == 4.0
    assert result["split_factors"]["2024-03-31"]["sample_count"] == 20
    assert result["split_adjustment_applied"] is True
    assert result["status"] == "negative"


def test_directory_loader_globs_all_quarters_and_annotation_is_immutable(
    tmp_path: Path,
) -> None:
    holdings, reports = _two_quarters()
    midpoint = len(holdings) // 2
    for name, rows in (
        ("core_holdings_2024q2.json.gz", holdings[:midpoint]),
        ("core_holdings_2024q3.json.gz", holdings[midpoint:]),
        ("series_reports.json.gz", reports),
    ):
        with gzip.open(tmp_path / name, "wt", encoding="utf-8") as handle:
            json.dump(rows, handle)
    dataset = load_nport_rows(tmp_path)
    assert dataset.holding_count == len(holdings)
    assert dataset.report_count == len(reports)

    signal = {
        "ticker": "ABC",
        "entry_date": "2024-08-21",
        "notional": 123.0,
        "nested": {"unchanged": True},
    }
    before = deepcopy(signal)
    annotated = annotate_signal(signal, dataset)

    assert signal == before
    assert annotated is not signal
    assert annotated["nested"] is not signal["nested"]
    shadow = annotated["sec_nport_share_accumulation_shadow"]
    assert shadow["scalar"] == POSITIVE_SCALAR
    assert shadow["shadow_only"] is True
    assert shadow["trade_enabled"] is False
    assert shadow["alters_sizing"] is False
    assert annotated["notional"] == 123.0
