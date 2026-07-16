from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from datetime import date, timedelta

import pytest

from quant import pcaob_form_ap_partner_change_peer_substitution_paper_sleeve as sleeve


_HEADERS = [
    "Form Filing ID",
    "Latest Form AP Filing",
    "Amendment Previous Filing",
    "Audit Report Type",
    "Issuer Name",
    "Issuer CIK",
    "Fiscal Period End Date",
    "Engagement Partner ID",
    "Engagement Partner Other Ids",
    "Original Firm Form ID",
    "Amends Firm Form ID",
    "Filing Date",
]


def _form_row(
    filing_id: str,
    cik: str,
    fiscal_end: str,
    filing_date: str,
    partner_id: str,
    **overrides,
) -> dict[str, str]:
    row = {
        "Form Filing ID": filing_id,
        "Latest Form AP Filing": "1",
        "Amendment Previous Filing": "false",
        "Audit Report Type": sleeve.OFFICIAL_AUDIT_REPORT_TYPE,
        "Issuer Name": f"Issuer {cik}",
        "Issuer CIK": cik,
        "Fiscal Period End Date": f"{fiscal_end} 12:00:00 AM",
        "Engagement Partner ID": partner_id,
        "Engagement Partner Other Ids": "",
        "Original Firm Form ID": "",
        "Amends Firm Form ID": "",
        "Filing Date": f"{filing_date} 04:21:09 PM",
    }
    row.update(overrides)
    return row


def _archive(tmp_path, rows, *, member=sleeve.OFFICIAL_ARCHIVE_MEMBER):
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=_HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    path = tmp_path / "FirmFilings.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(member, text.getvalue().encode("utf-8-sig"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


def _weekdays(start: str, end: str) -> list[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    output: list[str] = []
    while current <= final:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _bars(volume: float, *, slope: float = 0.01) -> list[dict]:
    output = []
    for idx, day in enumerate(_weekdays("2022-12-01", "2025-04-30")):
        open_price = 100.0 + idx * slope
        close = open_price + 0.2
        output.append(
            {
                "date": day,
                "open": open_price,
                "high": close + 1.0,
                "low": open_price - 1.0,
                "close": close,
                "volume": volume,
            }
        )
    return output


def _security(ticker: str, cik: str, *, industry="Software") -> dict:
    return {
        "ticker": ticker,
        "cik": cik,
        "issuer_name": ticker,
        "sector": "Technology",
        "industry": industry,
        "warehouse_hygiene_status": "ok",
        "all_windows_status": "ok",
        "sector_status": "ok",
    }


def _windows():
    return {
        "old": {"start": "2023-01-03", "end": "2023-03-31"},
        "mid": {"start": "2024-01-02", "end": "2024-03-29"},
        "late": {"start": "2025-01-02", "end": "2025-03-31"},
    }


def _fixture_inputs(tmp_path):
    rows = [
        _form_row("1", "1001", "12/31/2023", "01/02/2024", "P1"),
        _form_row(
            "2",
            "1001",
            "12/31/2024",
            "01/02/2025",
            "P2",
            **{"Engagement Partner Other Ids": "P2A#^#P2B"},
        ),
        _form_row("3", "1002", "12/31/2023", "01/02/2024", "Q1"),
        _form_row("4", "1002", "12/31/2024", "01/02/2025", "Q2"),
    ]
    archive, digest = _archive(tmp_path, rows)
    securities = [
        _security("AAA", "1001"),
        _security("AAAZ", "1001"),
        _security("BBB", "1002"),
        _security("CCC", "1003"),
        _security("DDD", "1004"),
        _security("DDDZ", "1004"),
    ]
    bars = {
        "SPY": _bars(5_000),
        "AAA": _bars(300),
        "AAAZ": _bars(100),
        # BBB would win ADV but changes partner in the same ISO filing week.
        "BBB": _bars(2_000),
        "CCC": _bars(200),
        "DDD": _bars(800, slope=0.03),
        "DDDZ": _bars(150),
    }
    return archive, digest, securities, bars


def test_archive_hash_and_fixed_original_issuer_filters_fail_closed(tmp_path):
    valid = _form_row("1", "1001", "12/31/2024", "01/02/2025", "P1")
    rows = [
        valid,
        _form_row(
            "2",
            "1002",
            "12/31/2024",
            "01/02/2025",
            "P2",
            **{"Latest Form AP Filing": "0"},
        ),
        _form_row(
            "3",
            "1003",
            "12/31/2024",
            "01/02/2025",
            "P3",
            **{"Amendment Previous Filing": "true"},
        ),
        _form_row(
            "4",
            "1004",
            "12/31/2024",
            "01/02/2025",
            "P4",
            **{"Original Firm Form ID": "11"},
        ),
        _form_row(
            "5",
            "1005",
            "12/31/2024",
            "01/02/2025",
            "P5",
            **{"Amends Firm Form ID": "12"},
        ),
        _form_row(
            "6",
            "1006",
            "12/31/2024",
            "01/02/2025",
            "P6",
            **{"Audit Report Type": "Investment Company"},
        ),
    ]
    archive, digest = _archive(tmp_path, rows)
    filings, provenance = sleeve.load_hash_bound_pcaob_form_ap_filings(
        archive, expected_sha256=digest
    )
    assert [row["form_filing_id"] for row in filings] == ["1"]
    assert provenance["source_archive_sha256"] == digest
    assert provenance["input_row_count"] == 6
    assert provenance["filtered_row_count"] == 1
    assert sum(provenance["filter_reject_totals"].values()) == 5

    with pytest.raises(ValueError, match="archive hash mismatch"):
        sleeve.load_hash_bound_pcaob_form_ap_filings(
            archive, expected_sha256="0" * 64
        )


def test_partner_set_uses_primary_and_other_ids_and_dedups_issuer_week(tmp_path):
    rows = [
        _form_row("1", "1001", "12/31/2022", "01/02/2023", "P0"),
        _form_row("2", "1001", "12/31/2023", "01/02/2024", "P1"),
        _form_row(
            "3",
            "1001",
            "12/31/2024",
            "01/02/2025",
            "P2",
            **{"Engagement Partner Other Ids": "P2A#^#P2B"},
        ),
        # A second changing fiscal-period filing in the same issuer/week is
        # observable later and must not create another decision.
        _form_row("4", "1001", "01/01/2025", "01/03/2025", "P3"),
    ]
    archive, digest = _archive(tmp_path, rows)
    filings, _ = sleeve.load_hash_bound_pcaob_form_ap_filings(
        archive, expected_sha256=digest
    )
    events, audit = sleeve.extract_partner_change_events(filings)
    latest = next(row for row in events if row["form_filing_id"] == "3")
    assert latest["engagement_partner_ids"] == ["P2", "P2A", "P2B"]
    assert latest["prior_fiscal_period_gap_days"] == 366
    assert latest["availability_date"] == "2025-01-03"
    assert audit["duplicate_issuer_week_partner_change_event_count"] == 1
    assert len({(row["issuer_cik"], row["iso_filing_week"]) for row in events}) == len(
        events
    )


def test_exact_cik_share_class_mapping_uses_three_window_minimum(tmp_path):
    _, _, securities, bars = _fixture_inputs(tmp_path)
    universe, audit = sleeve.resolve_exact_cik_security_universe(
        security_master=securities,
        ohlcv_by_ticker=bars,
        standard_windows=_windows(),
    )
    assert universe["0000001001"]["ticker"] == "AAA"
    assert universe["0000001004"]["ticker"] == "DDD"
    assert universe["0000001001"]["share_class_candidate_count"] == 2
    assert audit["multi_share_class_cik_count"] == 2

    broken = [dict(row) for row in securities]
    broken[0]["warehouse_hygiene_status"] = "bad"
    broken[1]["all_windows_status"] = "bad"
    rejected, rejected_audit = sleeve.resolve_exact_cik_security_universe(
        security_master=broken,
        ohlcv_by_ticker=bars,
        standard_windows=_windows(),
    )
    assert "0000001001" not in rejected
    assert rejected_audit["reject_totals"]["warehouse_hygiene_status_not_ok"] == 1
    assert rejected_audit["reject_totals"]["all_windows_status_not_ok"] == 1


def test_historical_policy_excludes_same_week_change_ranks_adv_and_settles_20s(
    tmp_path,
):
    archive, digest, securities, bars = _fixture_inputs(tmp_path)
    historical = (
        sleeve.build_pcaob_form_ap_partner_change_peer_substitution_historical(
            source_zip_path=archive,
            expected_sha256=digest,
            security_master=securities,
            ohlcv_by_ticker=bars,
            standard_windows=_windows(),
        )
    )
    late = historical["windows"]["late"]
    assert late["trade_enabled"] is False
    assert late["orders"] == []
    assert len(late["trades"]) == 1  # daily top-one across the two issuer events
    trade = late["trades"][0]
    assert trade["target_ticker"] == "AAA"
    assert trade["peer_ticker"] == "DDD"
    assert "0000001002" in trade["same_week_changed_ciks_excluded"]
    assert trade["tradable_peer_count"] == 2
    assert trade["target_from_multi_share_class_cik"] is True
    assert trade["peer_from_multi_share_class_cik"] is True
    # Filing Jan 2 -> availability Jan 3 -> strictly next market open Jan 6.
    assert trade["entry_date"] == "2025-01-06"
    peer_bars = bars["DDD"]
    entry_idx = next(
        idx for idx, row in enumerate(peer_bars) if row["date"] == trade["entry_date"]
    )
    assert trade["exit_date"] == peer_bars[entry_idx + 19]["date"]
    assert trade["hold_sessions_realized"] == 20
    expected_net = (
        trade["exit_price"] / trade["entry_price"]
        - 1.0
        - sleeve.ROUND_TRIP_COST_PCT
    )
    assert trade["net_return"] == pytest.approx(expected_net, abs=1e-9)
    assert trade["pnl"] == pytest.approx(sleeve.BASE_NOTIONAL_USD * expected_net, abs=0.02)
    assert trade["entry_date"]
    assert trade["target_price"] > trade["entry_price"]
    assert trade["target_price_semantics"] == "sentinel_only_not_exit_driver"
    assert trade["target_price_is_exit_driver"] is False
    assert trade["target_price_lookback_end_date"] < trade["entry_date"]
    assert late["coverage_audit"][
        "selected_target_from_multi_share_class_cik_count"
    ] == 1
    assert late["coverage_audit"][
        "selected_peer_from_multi_share_class_cik_count"
    ] == 1
    assert historical["source_provenance"]["source_archive_sha256"] == digest
    assert historical["aggregate_coverage_audit"]["settled_trade_count"] == 1


def test_daily_snapshot_uses_same_policy_and_can_never_emit_orders(tmp_path):
    archive, digest, securities, bars = _fixture_inputs(tmp_path)
    snapshot = (
        sleeve.build_pcaob_form_ap_partner_change_peer_substitution_paper_snapshot(
            source_zip_path=archive,
            expected_sha256=digest,
            security_master=securities,
            ohlcv_by_ticker=bars,
            standard_windows=_windows(),
            as_of_date="2025-01-03",
        )
    )
    assert snapshot["candidate_count"] == 1
    assert snapshot["candidates"][0]["target_ticker"] == "AAA"
    assert snapshot["candidates"][0]["peer_ticker"] == "DDD"
    assert snapshot["enabled"] is False
    assert snapshot["paper_enabled"] is True
    assert snapshot["trade_enabled"] is False
    assert snapshot["orders"] == []
    assert snapshot["production_impact"]["alters_live_orders"] is False

