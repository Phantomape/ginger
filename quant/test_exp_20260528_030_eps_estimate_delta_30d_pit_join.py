"""Unit tests for exp-20260528-030 PIT eps_estimate_delta_30d derivation.

Tests use synthetic earnings snapshots in a tmp dir so they do not
depend on live repo data. Coverage:

* PIT safety: the 30d lookback never reads a snapshot dated after the
  query date.
* Latest-on-or-before semantics for both the current and the prior leg.
* Percentage delta floor: near-zero priors yield None pct (not a
  spurious 100x value).
* Missing-leg statuses (no current estimate, no prior within lookback).
* Enrichment does not mutate input rows and preserves the original
  (null) field as ``*_before_repair``.
* Gate 4 acceptance bar on primary positive coverage.

No JavaScript was used.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant.experiments.exp_20260528_030_eps_estimate_delta_30d_pit_join_into_expectation_revision_watchlist_row import (  # noqa: E501
    GATE4_COVERAGE_FLOOR,
    PCT_DELTA_PRIOR_FLOOR,
    build_eps_estimate_index,
    coverage_report,
    derive_delta_30d_for_row,
    enrich_watchlist_rows,
    eps_estimate_at_pit,
    evaluate_gates,
)


def _write_snapshot(dir_: Path, yyyymmdd: str, earnings: dict[str, dict]) -> None:
    payload = {
        "schema_version": 1,
        "date": yyyymmdd,
        "timestamp": "2026-01-01T00:00:00",
        "coverage": {"tickers_total": len(earnings)},
        "earnings": earnings,
    }
    (dir_ / f"earnings_snapshot_{yyyymmdd}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


@pytest.fixture()
def snapshot_dir(tmp_path: Path) -> Path:
    d = tmp_path / "earnings_snapshots"
    d.mkdir()
    # AAPL eps_estimate timeline: 1.80 (Apr 1) -> 1.90 (Apr 25) -> 2.00 (May 10)
    _write_snapshot(d, "20260401", {"AAPL": {"eps_estimate": 1.80}})
    _write_snapshot(d, "20260425", {"AAPL": {"eps_estimate": 1.90}})
    _write_snapshot(
        d,
        "20260510",
        {"AAPL": {"eps_estimate": 2.00}, "NEWCO": {"eps_estimate": 0.50}},
    )
    # NEARZERO has a tiny prior estimate to exercise the pct floor.
    _write_snapshot(d, "20260402", {"NEARZERO": {"eps_estimate": 0.01}})
    _write_snapshot(d, "20260512", {"NEARZERO": {"eps_estimate": 0.20}})
    return d


def test_eps_estimate_at_pit_latest_on_or_before(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    val, snap = eps_estimate_at_pit("AAPL", "2026-05-01", index)
    assert val == 1.90  # Apr 25 is latest <= May 1
    assert snap == "2026-04-25"


def test_eps_estimate_at_pit_no_future_leak(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    # On Apr 20, only the Apr 1 snapshot exists.
    val, snap = eps_estimate_at_pit("AAPL", "2026-04-20", index)
    assert val == 1.80
    assert snap == "2026-04-01"


def test_eps_estimate_at_pit_unknown_ticker(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    val, snap = eps_estimate_at_pit("FAKEXYZ", "2026-05-10", index)
    assert val is None
    assert snap is None


def test_derive_delta_30d_positive_revision(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    # as_of = May 10 -> current 2.00. cutoff = Apr 10 -> prior leg uses
    # latest snapshot <= Apr 10, which is Apr 1 (1.80).
    row = {"ticker": "AAPL", "as_of_date": "2026-05-10"}
    out = derive_delta_30d_for_row(row, index)
    assert out["status"] == "ok"
    assert out["eps_estimate_at_as_of"] == 2.00
    assert out["eps_estimate_at_as_of_minus_30d"] == 1.80
    assert abs(out["eps_estimate_delta_30d"] - 0.20) < 1e-9
    assert abs(out["eps_estimate_pct_delta_30d"] - (0.20 / 1.80)) < 1e-9
    assert out["eps_estimate_at_prior_snapshot_date"] == "2026-04-01"


def test_derive_delta_30d_no_prior_within_lookback(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    # NEWCO first appears May 10; an as_of of May 10 has no snapshot
    # at-or-before Apr 10 for NEWCO.
    row = {"ticker": "NEWCO", "as_of_date": "2026-05-10"}
    out = derive_delta_30d_for_row(row, index)
    assert out["eps_estimate_at_as_of"] == 0.50
    assert out["eps_estimate_delta_30d"] is None
    assert out["status"] == "no_prior_eps_estimate_within_30d_lookback"


def test_derive_delta_30d_no_current_estimate(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    row = {"ticker": "AAPL", "as_of_date": "2026-03-01"}  # before any AAPL snapshot
    out = derive_delta_30d_for_row(row, index)
    assert out["eps_estimate_at_as_of"] is None
    assert out["status"] == "no_current_eps_estimate"


def test_derive_delta_30d_pct_floor_blocks_near_zero_prior(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    # NEARZERO prior = 0.01 (< PCT_DELTA_PRIOR_FLOOR=0.05), current = 0.20.
    # Absolute delta is still reported; pct delta must be None.
    row = {"ticker": "NEARZERO", "as_of_date": "2026-05-12"}
    out = derive_delta_30d_for_row(row, index)
    assert out["eps_estimate_at_as_of"] == 0.20
    assert out["eps_estimate_at_as_of_minus_30d"] == 0.01
    assert abs(out["eps_estimate_delta_30d"] - 0.19) < 1e-9
    assert out["eps_estimate_pct_delta_30d"] is None
    assert out["status"] == "prior_below_pct_delta_floor"
    assert PCT_DELTA_PRIOR_FLOOR == 0.05


def test_derive_delta_30d_missing_as_of(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    out = derive_delta_30d_for_row({"ticker": "AAPL", "as_of_date": ""}, index)
    assert out["status"] == "missing_as_of_date"
    assert out["eps_estimate_delta_30d"] is None


def test_enrich_does_not_mutate_input_and_preserves_before_repair(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    rows = [
        {
            "ticker": "AAPL",
            "as_of_date": "2026-05-10",
            "eps_estimate_delta_30d": None,  # original null in source artifact
            "primary_expectation_positive": True,
        }
    ]
    snapshot = json.dumps(rows, sort_keys=True)
    enriched = enrich_watchlist_rows(rows, index)
    assert abs(enriched[0]["eps_estimate_delta_30d"] - 0.20) < 1e-9
    assert enriched[0]["eps_estimate_delta_30d_before_repair"] is None
    assert enriched[0]["eps_estimate_delta_30d_lookup"]["status"] == "ok"
    # input list untouched
    assert json.dumps(rows, sort_keys=True) == snapshot


def test_coverage_and_gate4_pass(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    rows = [
        {"ticker": "AAPL", "as_of_date": "2026-05-10", "primary_expectation_positive": True},
        {"ticker": "AAPL", "as_of_date": "2026-05-09", "primary_expectation_positive": True},
    ]
    enriched = enrich_watchlist_rows(rows, index)
    cov = coverage_report(enriched)
    gates = evaluate_gates(cov)
    assert gates["gate4"]["passed"] is True
    assert (
        cov["delta_30d_coverage"]["primary_positive_rows"]["ratio"] == 1.0
    )


def test_gate4_fails_below_floor(snapshot_dir):
    index = build_eps_estimate_index(snapshot_dir)
    rows = [
        # resolves
        {"ticker": "AAPL", "as_of_date": "2026-05-10", "primary_expectation_positive": True},
        # NEWCO never resolves a 30d prior
        {"ticker": "NEWCO", "as_of_date": "2026-05-10", "primary_expectation_positive": True},
    ]
    enriched = enrich_watchlist_rows(rows, index)
    cov = coverage_report(enriched)
    gates = evaluate_gates(cov)
    assert cov["delta_30d_coverage"]["primary_positive_rows"]["ratio"] == 0.5
    assert gates["gate4"]["passed"] is False
    assert GATE4_COVERAGE_FLOOR == 0.80
