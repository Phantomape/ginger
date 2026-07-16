from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from datetime import date, timedelta

import pytest

from quant import faers_serious_share_improvement_paper_sleeve as sleeve


DEMO_FIELDS = [
    "primaryid",
    "caseid",
    "caseversion",
    "i_f_code",
    "mfr_sndr",
]
OUTC_FIELDS = ["primaryid", "caseid", "outc_cod"]


def _write_archive(path, demo_rows, outc_rows, quarter):
    demo = io.StringIO(newline="")
    writer = csv.DictWriter(demo, fieldnames=DEMO_FIELDS, delimiter="$")
    writer.writeheader()
    writer.writerows(demo_rows)
    outc = io.StringIO(newline="")
    writer = csv.DictWriter(outc, fieldnames=OUTC_FIELDS, delimiter="$")
    writer.writeheader()
    writer.writerows(outc_rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(f"ASCII/DEMO{quarter.upper()}.txt", demo.getvalue().encode("latin1"))
        bundle.writestr(f"ASCII/OUTC{quarter.upper()}.txt", outc.getvalue().encode("latin1"))


def _case_rows(quarter, sender, prefix, count, serious_count):
    demo_rows = []
    outc_rows = []
    for index in range(count):
        caseid = f"{quarter}-{prefix}-case-{index}"
        primaryid = f"{quarter}-{prefix}-primary-{index}"
        demo_rows.append(
            {
                "primaryid": primaryid,
                "caseid": caseid,
                "caseversion": "2" if index == 0 else "1",
                "i_f_code": "I",
                "mfr_sndr": sender,
            }
        )
        if index == 0:
            # An older initial version and a newer follow-up must not inflate or
            # replace the selected latest *initial* case record.
            demo_rows.insert(
                0,
                {
                    "primaryid": f"{primaryid}-old",
                    "caseid": caseid,
                    "caseversion": "1",
                    "i_f_code": "I",
                    "mfr_sndr": sender,
                },
            )
            demo_rows.append(
                {
                    "primaryid": f"{primaryid}-followup",
                    "caseid": caseid,
                    "caseversion": "9",
                    "i_f_code": "F",
                    "mfr_sndr": sender,
                }
            )
        if index < serious_count:
            outc_rows.append(
                {"primaryid": primaryid, "caseid": caseid, "outc_cod": "HO"}
            )
    return demo_rows, outc_rows


def _source_fixture(tmp_path):
    raw_dir = tmp_path / "faers"
    raw_dir.mkdir()
    # AAA improves each quarter. BBB is stable and therefore never selected.
    aaa_serious = [80, 70, 60, 50, 40, 30, 20]
    hashes = {}
    for quarter, serious in zip(sleeve.QUARTERS, aaa_serious):
        demo_a, outc_a = _case_rows(quarter, "Alpha Healthcare Inc", "a", 100, serious)
        demo_b, outc_b = _case_rows(quarter, "Beta Pharma Corp", "b", 100, 50)
        # The ambiguous short sender is always ignored, even if it looks close
        # to a listed issuer elsewhere in the map.
        demo_v, outc_v = _case_rows(quarter, "VERTEX", "v", 1, 1)
        path = raw_dir / f"faers_ascii_{quarter}.zip"
        _write_archive(path, demo_a + demo_b + demo_v, outc_a + outc_b + outc_v, quarter)
        hashes[quarter] = hashlib.sha256(path.read_bytes()).hexdigest()
    issuer_index = {
        "Alpha Healthcare Inc.": "AAA",
        "Beta Pharma Corp.": "BBB",
        "Vertex Pharmaceuticals Inc.": "VRTX",
    }
    return raw_dir, hashes, issuer_index


def _weekdays(start, end):
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    output = []
    while current <= final:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _bars(calendar, slope=0.03):
    rows = []
    for index, day in enumerate(calendar):
        open_price = 50.0 + index * slope
        rows.append(
            {
                "date": day,
                "open": open_price,
                "high": open_price + 1.0,
                "low": open_price - 1.0,
                "close": open_price + 0.25,
                "volume": 1_000_000,
            }
        )
    return rows


def _windows():
    return {
        "old_thin": {"start": "2024-10-01", "end": "2025-03-31"},
        "mid_weak": {"start": "2025-04-01", "end": "2025-09-30"},
        "late_strong": {"start": "2025-10-01", "end": "2026-03-31"},
    }


def test_hash_bound_parser_deduplicates_initial_case_version_and_fails_vertex_closed(
    tmp_path,
):
    raw_dir, hashes, issuer_index = _source_fixture(tmp_path)
    quarterly, provenance = sleeve.load_hash_bound_faers_quarters(
        raw_dir, hashes, issuer_index
    )
    assert quarterly["2024q2"]["AAA"] == {
        "initial_cases": 100,
        "serious_cases": 80,
        "serious_share": 0.8,
    }
    assert "VRTX" not in quarterly["2024q2"]
    first_audit = provenance["files"][0]["parse_audit"]
    assert first_audit["latest_initial_case_count"] == 201
    assert first_audit["mapped_initial_case_count"] == 200
    assert first_audit["short_vertex_fail_closed_case_count"] == 1
    assert provenance["quarter_count"] == 7
    assert provenance["short_vertex_fail_closed"] is True

    broken = dict(hashes)
    broken["2025q4"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch for 2025q4"):
        sleeve.load_hash_bound_faers_quarters(raw_dir, broken, issuer_index)
    with pytest.raises(ValueError, match="VERTEX must remain fail-closed"):
        sleeve.load_hash_bound_faers_quarters(
            raw_dir, hashes, {**issuer_index, "VERTEX": "VRTX"}
        )


def test_fixed_policy_ranks_only_negative_delta_caps_ten_and_preserves_budget():
    prior = {}
    current = {}
    for index in range(12):
        ticker = f"T{index:02d}"
        prior[ticker] = {"initial_cases": 100, "serious_share": 0.8}
        current[ticker] = {
            "initial_cases": 100,
            "serious_share": 0.79 - index * 0.01,
        }
    selected, audit = sleeve.build_quarterly_candidates(
        {"2024q2": prior, "2024q3": current}
    )
    rows = selected["2024q3"]
    assert len(rows) == 10
    assert [row["ticker"] for row in rows[:2]] == ["T11", "T10"]
    assert {row["ticker"] for row in rows}.isdisjoint({"T00", "T01"})
    assert sum(row["notional_usd"] for row in rows) == sleeve.EVENT_NOTIONAL_USD
    assert [row["selection_rank"] for row in rows] == list(range(1, 11))
    assert audit["2024q3"]["eligible_adjacent_pair_count"] == 12
    assert audit["2024q3"]["selected_count"] == 10
    assert all(row["trade_enabled"] is False for row in rows)


def test_historical_replay_uses_entry_open_and_entry_index_plus_19_close(tmp_path):
    raw_dir, hashes, issuer_index = _source_fixture(tmp_path)
    calendar = _weekdays("2024-09-02", "2026-04-30")
    bars = {"AAA": _bars(calendar), "BBB": _bars(calendar, slope=0.01)}
    result = sleeve.build_historical_replay(
        raw_dir,
        hashes,
        issuer_index,
        bars,
        _windows(),
        calendar,
    )
    assert result["trade_enabled"] is False
    assert result["orders"] == []
    assert result["aggregate_coverage"]["selected_count"] == 6
    assert result["aggregate_coverage"]["settled_trade_count"] == 6
    assert result["aggregate_coverage"]["window_selected_counts"] == {
        "old_thin": 2,
        "mid_weak": 2,
        "late_strong": 2,
    }

    trade = result["windows"]["late_strong"]["trades"][0]
    assert trade["quarter"] == "2025q3"
    assert trade["entry_date"] == sleeve.RELEASE_EFFECTIVE_SESSION["2025q3"]
    entry_index = calendar.index(trade["entry_date"])
    assert trade["exit_date"] == calendar[entry_index + 19]
    assert trade["hold_sessions_realized"] == 20
    expected_net = (
        trade["exit_price"] / trade["entry_price"]
        - 1.0
        - sleeve.ROUND_TRIP_COST_PCT
    )
    assert trade["net_return"] == pytest.approx(expected_net, abs=1e-9)
    assert trade["pnl"] == pytest.approx(
        trade["notional_usd"] * expected_net, abs=0.01
    )
    assert trade["entry_date"]
    assert trade["target_price"] > trade["entry_price"]
    assert trade["target_price_is_exit_driver"] is False
    assert trade["target_price_lookback_end_date"] < trade["entry_date"]
    assert result["windows"]["late_strong"]["coverage"][
        "settled_sentinel_contract_passed"
    ]
    assert result["source_provenance"]["quarter_count"] == 7


def test_missing_selected_bar_is_unsettled_and_never_replaced(tmp_path):
    raw_dir, hashes, issuer_index = _source_fixture(tmp_path)
    calendar = _weekdays("2024-09-02", "2026-04-30")
    result = sleeve.build_historical_replay(
        raw_dir,
        hashes,
        issuer_index,
        {"BBB": _bars(calendar)},
        _windows(),
        calendar,
    )
    late = result["windows"]["late_strong"]
    assert len(late["selected"]) == 2
    assert len(late["trades"]) == 0
    assert len(late["unsettled"]) == 2
    assert {row["ticker"] for row in late["unsettled"]} == {"AAA"}
    assert late["coverage"]["unsettled_reason_totals"] == {
        "missing_entry_open": 2
    }
    assert late["orders"] == []


def test_default_off_snapshot_shares_selection_and_exposes_no_outcome_or_order(
    tmp_path,
):
    raw_dir, hashes, issuer_index = _source_fixture(tmp_path)
    calendar = _weekdays("2024-09-02", "2026-04-30")
    bars = {"AAA": _bars(calendar), "BBB": _bars(calendar, slope=0.01)}
    snapshot = sleeve.build_paper_snapshot(
        raw_dir,
        hashes,
        issuer_index,
        bars,
        "2026-01-28",
        calendar,
    )
    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]
    assert candidate["quarter"] == "2025q4"
    assert candidate["ticker"] == "AAA"
    assert candidate["entry_date"] == "2026-01-28"
    assert candidate["target_price"] > candidate["entry_price"]
    assert candidate["paper_status"] == "open"
    assert snapshot["paper_positions"] == snapshot["candidates"]
    assert snapshot["pending_entries"] == []
    assert snapshot["enabled"] is False
    assert snapshot["paper_enabled"] is True
    assert snapshot["trade_enabled"] is False
    assert snapshot["orders"] == []
    assert snapshot["production_impact"]["alters_live_orders"] is False
    assert all(
        key not in candidate
        for key in ("exit_price", "gross_return", "net_return", "pnl")
    )

