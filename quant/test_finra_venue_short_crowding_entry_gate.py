from __future__ import annotations

from copy import deepcopy
import json

import pytest

from quant.finra_venue_short_crowding_entry_gate import (
    FinraVenueShortCrowdingEntryAdmissionPolicy,
    FinraVenueShortCrowdingGateError,
    build_daily_entry_admission_snapshot,
    build_finra_venue_short_crowding_exclusion_index,
    load_revision_safe_short_interest_rows,
)


SESSIONS = ["2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10"]


def _venue_rows() -> tuple[list[dict], list[dict]]:
    shares = {"A": (80, 20), "B": (60, 40), "C": (40, 60), "D": (20, 80)}
    ats = []
    otc = []
    for ticker, (ats_qty, otc_qty) in shares.items():
        common = {
            "ticker": ticker,
            "week_start_date": "2024-12-16",
            "published_date": "2025-01-06",
            "tier": "T1",
        }
        ats.append({**common, "ats_share_quantity": ats_qty})
        otc.append({**common, "otc_share_quantity": otc_qty})
    # This ETF-like row is denied before medians even though it would qualify.
    common = {
        "ticker": "SPY",
        "week_start_date": "2024-12-16",
        "published_date": "2025-01-06",
        "tier": "T1",
    }
    ats.append({**common, "ats_share_quantity": 99})
    otc.append({**common, "otc_share_quantity": 1})
    return ats, otc


def _short_rows() -> list[dict]:
    values = {
        "A": (5.0, 10.0),
        "B": (4.0, -2.0),
        "C": (2.0, 8.0),
        "D": (1.0, 5.0),
        "SPY": (20.0, 20.0),
    }
    return [
        {
            "ticker": ticker,
            "publication_date": "2025-01-07",
            "settlement_date": "2024-12-31",
            "days_to_cover": dtc,
            "short_interest_change_pct": change,
            "pit_safe": True,
        }
        for ticker, (dtc, change) in values.items()
    ]


def _index():
    ats, otc = _venue_rows()
    return build_finra_venue_short_crowding_exclusion_index(
        ats, otc, _short_rows(), SESSIONS
    )


def test_fixed_joint_rule_uses_strict_prior_day_and_exact_medians():
    index = _index()

    # On the SI publication date itself, the strict-prior-day rule cannot use it.
    assert index["by_signal_day"]["2025-01-07"] == []
    assert index["state_by_signal_day"]["2025-01-07"]["status"] == "uncovered_no_prior_release"

    state = index["state_by_signal_day"]["2025-01-08"]
    assert state["venue_share_median"] == pytest.approx(0.5)
    assert state["days_to_cover_median"] == pytest.approx(3.0)
    assert index["coverage_by_signal_day"]["2025-01-08"] == ["A", "B", "C", "D"]
    assert index["by_signal_day"]["2025-01-08"] == ["A"]
    assert "SPY" not in index["coverage_by_signal_day"]["2025-01-08"]


def test_policy_fails_open_and_applies_exclusion_only_to_next_fill():
    index = _index()
    resolver = FinraVenueShortCrowdingEntryAdmissionPolicy(
        ["A", "B", "C", "SPY", "MISSING"],
        index,
        trading_sessions=SESSIONS,
        source_hash=index["source_hash"],
    )

    result = resolver.resolve("2025-01-08")
    assert result["provenance"]["entry_session"] == "2025-01-09"
    assert result["provenance"]["excluded_tickers"] == ["A"]
    assert result["tickers"] == ["B", "C", "MISSING", "SPY"]
    assert result["provenance"]["coverage_status"] == "partial"
    assert result["provenance"]["missing_tickers"] == ["MISSING", "SPY"]
    assert result["reason"] == "next_session_joint_crowding_entry_exclusion"

    same_day = resolver.resolve("2025-01-07")
    assert same_day["tickers"] == ["A", "B", "C", "MISSING", "SPY"]
    assert same_day["reason"].startswith("fail_open_")

    denied = resolver.evaluate(
        signal_date="2025-01-08", ticker="A", fill_date="2025-01-09"
    )
    assert denied["admit"] is False
    assert denied["status"] == "denied"

    delayed = resolver.evaluate(
        signal_date="2025-01-08", ticker="A", fill_date="2025-01-10"
    )
    assert delayed["admit"] is True
    assert delayed["status"] == "admitted_not_strict_next_session"

    no_next = resolver.resolve("2025-01-10")
    assert no_next["tickers"] == ["A", "B", "C", "MISSING", "SPY"]
    assert no_next["provenance"]["excluded_tickers"] == []
    assert no_next["provenance"]["coverage_status"] == (
        "unknown_no_next_trading_session"
    )


def test_latest_global_release_does_not_forward_fill_a_missing_ticker():
    ats, otc = _venue_rows()
    rows = _short_rows()
    # A was present in an older release, but is absent from the latest global
    # release.  It must not be filled ticker-by-ticker from the older row.
    rows.append(
        {
            "ticker": "A",
            "publication_date": "2025-01-02",
            "settlement_date": "2024-12-20",
            "days_to_cover": 9.0,
            "short_interest_change_pct": 20.0,
            "pit_safe": True,
        }
    )
    rows = [row for row in rows if not (row["ticker"] == "A" and row["publication_date"] == "2025-01-07")]
    index = build_finra_venue_short_crowding_exclusion_index(ats, otc, rows, SESSIONS)

    assert "A" not in index["coverage_by_signal_day"]["2025-01-08"]
    assert "A" not in index["by_signal_day"]["2025-01-08"]


def test_daily_snapshot_has_exact_resolver_parity_and_is_default_off():
    ats, otc = _venue_rows()
    index = build_finra_venue_short_crowding_exclusion_index(
        ats, otc, _short_rows(), SESSIONS
    )
    resolver = FinraVenueShortCrowdingEntryAdmissionPolicy(
        ["A", "B", "C", "D"], index, trading_sessions=SESSIONS
    )
    resolved = resolver.resolve("2025-01-08")
    snapshot = build_daily_entry_admission_snapshot(
        ats, otc, _short_rows(), "2025-01-08", SESSIONS, ["A", "B", "C", "D"]
    )

    assert snapshot["eligible_tickers"] == resolved["tickers"]
    assert snapshot["excluded_tickers_for_next_session"] == ["A"]
    assert snapshot["resolver_snapshot_hash"] == resolved["snapshot_sha256"]
    assert snapshot["membership_hash"] == resolved["membership_hash"]
    assert snapshot["trade_enabled"] is False
    assert snapshot["alters_live_orders"] is False
    assert snapshot["alters_signal_generation"] is False


def test_hash_bound_index_rejects_mutation():
    index = _index()
    tampered = deepcopy(index)
    tampered["by_signal_day"]["2025-01-08"] = []
    with pytest.raises(FinraVenueShortCrowdingGateError, match="hash mismatch"):
        FinraVenueShortCrowdingEntryAdmissionPolicy(
            ["A", "B"], tampered, trading_sessions=SESSIONS
        )


def test_latest_raw_release_clocks_prevent_silent_fallback():
    ats, otc = _venue_rows()
    ats.append(
        {
            "ticker": "A",
            "week_start_date": "2024-12-23",
            "published_date": "2025-01-09",
            "tier": "T1",
            "ats_share_quantity": 50,
        }
    )
    index = build_finra_venue_short_crowding_exclusion_index(
        ats, otc, _short_rows(), SESSIONS
    )
    assert index["state_by_signal_day"]["2025-01-10"]["status"] == (
        "uncovered_latest_venue_release_mismatch"
    )
    assert index["by_signal_day"]["2025-01-10"] == []

    ats, otc = _venue_rows()
    invalid_latest_short = _short_rows() + [
        {
            "ticker": "A",
            "publication_date": "2025-01-09",
            "usable_trade_date": "not-a-date",
            "settlement_date": "2025-01-02",
            "days_to_cover": 10,
            "short_interest_change_pct": 10,
            "pit_safe": True,
        }
    ]
    index = build_finra_venue_short_crowding_exclusion_index(
        ats, otc, invalid_latest_short, SESSIONS
    )
    assert index["state_by_signal_day"]["2025-01-10"]["status"] == (
        "uncovered_unusable_latest_short_interest_release"
    )


def test_conflicting_duplicate_exact_keys_are_rejected():
    ats, otc = _venue_rows()
    duplicate = deepcopy(ats[0])
    duplicate["ats_share_quantity"] += 1
    with pytest.raises(FinraVenueShortCrowdingGateError, match="conflicting duplicate"):
        build_finra_venue_short_crowding_exclusion_index(
            [*ats, duplicate], otc, _short_rows(), SESSIONS
        )


def test_usable_clock_and_source_identity_are_hash_bound():
    ats, otc = _venue_rows()
    base = build_finra_venue_short_crowding_exclusion_index(
        ats,
        otc,
        _short_rows(),
        SESSIONS,
        source_identities={"ats_manifest_sha256": "a"},
    )
    changed_rows = deepcopy(_short_rows())
    for row in changed_rows:
        row["usable_trade_date"] = "2025-01-08"
    changed_clock = build_finra_venue_short_crowding_exclusion_index(
        ats,
        otc,
        changed_rows,
        SESSIONS,
        source_identities={"ats_manifest_sha256": "a"},
    )
    changed_manifest = build_finra_venue_short_crowding_exclusion_index(
        ats,
        otc,
        _short_rows(),
        SESSIONS,
        source_identities={"ats_manifest_sha256": "b"},
    )
    assert changed_clock["source_hash"] != base["source_hash"]
    assert changed_manifest["source_hash"] != base["source_hash"]


def test_raw_revision_flags_are_attached_and_fail_closed(tmp_path):
    normalized = tmp_path / "rows.json"
    raw_dir = tmp_path / "source_cache"
    raw_dir.mkdir()
    rows = _short_rows()[:2]
    normalized.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    (raw_dir / "shrt20241231.csv").write_text(
        "symbolCode|settlementDate|revisionFlag\n"
        f"{rows[0]['ticker']}|2024-12-31|R\n"
        f"{rows[1]['ticker']}|2024-12-31|\n",
        encoding="utf-8",
    )

    attached, audit = load_revision_safe_short_interest_rows(
        normalized, raw_dir
    )
    assert attached[0]["revision_flag"] == "R"
    assert attached[0]["pit_safe"] is False
    assert attached[0]["as_published_vintage_available"] is False
    assert attached[1]["revision_flag"] is None
    assert attached[1]["pit_safe"] is True
    assert audit["revised_normalized_row_count"] == 1
    assert audit["all_normalized_rows_raw_matched"] is True

    ats, otc = _venue_rows()
    index = build_finra_venue_short_crowding_exclusion_index(
        ats, otc, attached, SESSIONS
    )
    assert index["invalid_row_counts"]["short_interest"] == 1


def test_revision_loader_rejects_missing_raw_provenance(tmp_path):
    normalized = tmp_path / "rows.json"
    raw_dir = tmp_path / "source_cache"
    raw_dir.mkdir()
    normalized.write_text(
        json.dumps({"rows": _short_rows()[:1]}), encoding="utf-8"
    )
    (raw_dir / "shrt20241231.csv").write_text(
        "symbolCode|settlementDate|revisionFlag\n"
        "OTHER|2024-12-31|\n",
        encoding="utf-8",
    )
    with pytest.raises(
        FinraVenueShortCrowdingGateError,
        match="lack raw provenance",
    ):
        load_revision_safe_short_interest_rows(normalized, raw_dir)
