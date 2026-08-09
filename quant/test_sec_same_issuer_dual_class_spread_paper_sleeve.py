"""Focused contracts for the exp-20260718-007 shared paper helper."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import date, timedelta

import pytest

from sec_same_issuer_dual_class_spread_paper_sleeve import (
    ADVERSE_LOG_SPREAD_STOP,
    FROZEN_ECONOMIC_WHITELIST_SHA256,
    FROZEN_IDENTITY_PAIRS,
    FROZEN_IDENTITY_WHITELIST_SHA256,
    FROZEN_PAIRS,
    FROZEN_PROVENANCE_POLICY_SHA256,
    HALF_TRADE_COST_RATE,
    INITIAL_CASH_USD,
    LEG_NOTIONAL_CAP_USD,
    MAX_ENTRY_DOLLAR_IMBALANCE,
    RULE_VERSION,
    SAME_PAIR_COOLDOWN_SESSIONS,
    SHORT_CARRY_ANNUAL_RATE,
    FrozenIdentityError,
    assert_frozen_sec_identities,
    build_sec_same_issuer_dual_class_spread_paper_snapshot,
    compute_strict_prior_pair_signal,
    parse_sec_company_tickers,
    replay_sec_same_issuer_dual_class_spread_sleeve,
    size_whole_share_pair_entry,
)


def _business_dates(count: int) -> list[str]:
    result: list[str] = []
    current = date(2024, 1, 2)
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _sec_payload(*, extra_same_cik: bool = False) -> dict[str, dict]:
    rows: list[dict] = []
    for pair in FROZEN_IDENTITY_PAIRS:
        rows.extend(
            [
                {
                    "cik_str": pair["cik"],
                    "ticker": pair["left_ticker"],
                    "title": f"{pair['pair_id']} left",
                },
                {
                    "cik_str": pair["cik"],
                    "ticker": pair["right_ticker"],
                    "title": f"{pair['pair_id']} right",
                },
            ]
        )
    if extra_same_cik:
        rows.append({"cik_str": 1652044, "ticker": "GOOGX", "title": "not admitted"})
    rows.append({"cik_str": 9999999, "ticker": "OTHER", "title": "unrelated"})
    return {str(index): row for index, row in enumerate(rows)}


def _bars(
    dates: list[str],
    close_prices: list[float],
    open_prices: list[float] | None = None,
) -> list[dict]:
    opens = open_prices or close_prices
    return [
        {
            "Date": day,
            "Open": open_price,
            "High": max(open_price, close_price),
            "Low": min(open_price, close_price),
            "Close": close_price,
        }
        for day, open_price, close_price in zip(dates, opens, close_prices)
    ]


def _base_market(count: int = 145) -> tuple[list[str], dict[str, list[dict]]]:
    dates = _business_dates(count)
    payload: dict[str, list[dict]] = {}
    for pair_index, pair in enumerate(FROZEN_IDENTITY_PAIRS):
        base = 70.0 + pair_index * 10.0
        values = [base] * count
        payload[pair["left_ticker"]] = _bars(dates, values)
        payload[pair["right_ticker"]] = _bars(dates, values)
    return dates, payload


def _spread_history(count: int) -> list[float]:
    spreads = [0.25]  # deliberately excluded from the exactly-120 prior window
    spreads.extend(0.0005 * ((index % 5) - 2) for index in range(1, 121))
    spreads.extend([0.0] * max(0, count - len(spreads)))
    return spreads[:count]


def _set_pair_spreads(
    market: dict[str, list[dict]],
    pair_id: str,
    dates: list[str],
    close_spreads: list[float],
    *,
    open_spreads: list[float] | None = None,
    right_price: float = 100.0,
) -> None:
    pair = next(row for row in FROZEN_IDENTITY_PAIRS if row["pair_id"] == pair_id)
    opens = open_spreads or close_spreads
    market[pair["left_ticker"]] = _bars(
        dates,
        [right_price * math.exp(value) for value in close_spreads],
        [right_price * math.exp(value) for value in opens],
    )
    market[pair["right_ticker"]] = _bars(
        dates, [right_price] * len(dates), [right_price] * len(dates)
    )


def _exit_market(kind: str) -> tuple[list[str], dict[str, list[dict]], int]:
    dates, market = _base_market()
    close_spreads = _spread_history(len(dates))
    open_spreads = list(close_spreads)
    signal_index = 121
    entry_index = signal_index + 1
    close_spreads[signal_index] = 0.03
    open_spreads[signal_index] = 0.03
    open_spreads[entry_index] = 0.03
    if kind == "convergence":
        close_spreads[entry_index] = 0.0
        exit_index = entry_index
    elif kind == "stop":
        close_spreads[entry_index] = 0.03
        close_spreads[entry_index + 1] = 0.03 + ADVERSE_LOG_SPREAD_STOP + 0.002
        open_spreads[entry_index + 1] = close_spreads[entry_index]
        exit_index = entry_index + 1
    elif kind == "timeout":
        for index in range(entry_index, entry_index + 10):
            close_spreads[index] = 0.03
            open_spreads[index] = 0.03
        exit_index = entry_index + 9
    else:  # pragma: no cover - test helper misuse
        raise AssertionError(kind)
    _set_pair_spreads(
        market,
        "FOX/FOXA",
        dates,
        close_spreads,
        open_spreads=open_spreads,
    )
    return dates, market, exit_index


def test_raw_sec_json_is_one_to_many_but_admission_is_exact_and_hashed():
    payload = _sec_payload(extra_same_cik=True)
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    parsed = parse_sec_company_tickers(raw)
    assert parsed["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert {"GOOG", "GOOGL", "GOOGX"}.issubset(
        set(parsed["cik_to_tickers"]["1652044"])
    )

    identity = assert_frozen_sec_identities(raw)
    assert identity["whitelist_sha256"] == FROZEN_ECONOMIC_WHITELIST_SHA256
    assert identity["identity_whitelist_sha256"] == FROZEN_IDENTITY_WHITELIST_SHA256
    assert identity["provenance_policy_sha256"] == FROZEN_PROVENANCE_POLICY_SHA256
    assert identity["identity_candidate_count"] == 6
    assert identity["admitted_pair_count"] == 5
    assert identity["auto_admission_enabled"] is False
    assert identity["ignored_same_cik_tickers"] == {"GOOG/GOOGL": ["GOOGX"]}
    assert {row["pair_id"] for row in identity["admitted_pairs"]} == {
        row["pair_id"] for row in FROZEN_PAIRS
    }
    assert [row["pair_id"] for row in identity["excluded_identity_candidates"]] == [
        "GOOG/GOOGL"
    ]
    assert identity["excluded_identity_candidates"][0]["data_provenance_admitted"] is False
    assert "one batch/vintage" in identity["excluded_identity_candidates"][0][
        "reopen_condition"
    ]

    bad = copy.deepcopy(payload)
    goog_row = next(row for row in bad.values() if row["ticker"] == "GOOG")
    goog_row["cik_str"] = 1
    with pytest.raises(FrozenIdentityError, match="mismatched"):
        assert_frozen_sec_identities(bad)


def test_signal_audits_excluded_goog_with_strict_prior_stats_but_never_admits_it():
    dates, market = _base_market(124)
    spreads = _spread_history(len(dates))
    signal_index = 121
    spreads[signal_index] = 0.03
    spreads[signal_index + 1] = -0.40  # future value must not enter the anchor
    _set_pair_spreads(market, "GOOG/GOOGL", dates, spreads)

    signal = compute_strict_prior_pair_signal(
        "GOOG/GOOGL", dates[signal_index], market
    )
    expected_prior = spreads[1:121]
    assert signal["statistical_entry_threshold_pass"] is True
    assert signal["data_provenance_admitted"] is False
    assert signal["eligible"] is False
    assert signal["reason"] == "data_provenance_not_admitted"
    assert "one batch/vintage" in signal["data_provenance_reopen_condition"]
    assert signal["prior_observation_count"] == 120
    assert signal["prior_first_date"] == dates[1]
    assert signal["prior_last_date"] == dates[120]
    assert signal["frozen_anchor_log_ratio"] == pytest.approx(
        sorted(expected_prior)[len(expected_prior) // 2 - 1 : len(expected_prior) // 2 + 1][0]
        / 2
        + sorted(expected_prior)[len(expected_prior) // 2]
        / 2
    )
    assert signal["signal_robust_z"] > 2.5
    assert signal["long_ticker"] == "GOOGL"
    assert signal["short_ticker"] == "GOOG"

    changed = copy.deepcopy(market)
    changed["GOOG"][signal_index + 1]["Close"] *= 100.0
    unchanged = compute_strict_prior_pair_signal(
        "GOOG/GOOGL", dates[signal_index], changed
    )
    assert unchanged["frozen_anchor_log_ratio"] == pytest.approx(
        signal["frozen_anchor_log_ratio"]
    )
    assert unchanged["signal_robust_z"] == pytest.approx(signal["signal_robust_z"])


def test_excluded_goog_threshold_hit_is_audited_but_ineligible_in_replay_and_daily():
    dates, market = _base_market(125)
    spreads = _spread_history(len(dates))
    spreads[121] = 0.03
    spreads[122] = 0.03
    _set_pair_spreads(market, "GOOG/GOOGL", dates, spreads)

    daily = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[121],
        sec_payload=_sec_payload(),
        sec_as_of=dates[121],
        ohlcv_by_ticker=market,
    )
    goog_daily = next(
        row for row in daily["signal_rows"] if row["pair_id"] == "GOOG/GOOGL"
    )
    assert goog_daily["statistical_entry_threshold_pass"] is True
    assert goog_daily["data_provenance_admitted"] is False
    assert goog_daily["eligible"] is False
    assert daily["selected_signal"] is None
    assert daily["state"]["pending_pair"] is None

    replay = replay_sec_same_issuer_dual_class_spread_sleeve(
        _sec_payload(), market, dates[121], dates[122]
    )
    goog_replay = next(
        row
        for row in replay["daily_snapshots"][0]["signal_rows"]
        if row["pair_id"] == "GOOG/GOOGL"
    )
    assert goog_replay["statistical_entry_threshold_pass"] is True
    assert goog_replay["eligible"] is False
    assert replay["trades"] == []
    assert replay["state"]["pending_pair"] is None
    assert replay["summary"]["audit"]["data_provenance_excluded_threshold_signals"] >= 1

    poisoned_state = copy.deepcopy(daily["state"])
    poisoned_state["pending_pair"] = goog_daily
    refused = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[122],
        sec_payload=_sec_payload(),
        sec_as_of=dates[122],
        ohlcv_by_ticker=market,
        state=poisoned_state,
    )
    assert refused["status"] == "refused"
    assert refused["reason"] == "state_contains_data_provenance_ineligible_pair"


def test_whole_share_sizing_preserves_cash_collateral_gross_and_imbalance():
    sized = size_whole_share_pair_entry(
        long_open=120.0,
        short_open=175.0,
        available_cash_usd=INITIAL_CASH_USD,
    )
    assert sized["status"] == "fundable"
    assert isinstance(sized["long_shares"], int)
    assert isinstance(sized["short_shares"], int)
    assert sized["long_entry_notional_usd"] <= LEG_NOTIONAL_CAP_USD
    assert sized["short_entry_notional_usd"] <= LEG_NOTIONAL_CAP_USD
    assert sized["entry_required_cash_usd"] <= INITIAL_CASH_USD
    assert sized["cash_remaining_after_entry_usd"] >= 0.0
    assert sized["short_proceeds_reused_usd"] == 0.0
    assert sized["entry_dollar_imbalance"] <= MAX_ENTRY_DOLLAR_IMBALANCE
    assert sized["entry_trade_cost_usd"] == pytest.approx(
        HALF_TRADE_COST_RATE
        * (sized["long_entry_notional_usd"] + sized["short_entry_notional_usd"])
    )

    rejected = size_whole_share_pair_entry(
        long_open=4_900.0,
        short_open=3_000.0,
        available_cash_usd=INITIAL_CASH_USD,
    )
    assert rejected["status"] == "rejected"
    assert rejected["reason"] == "whole_share_cash_or_imbalance_constraint"


@pytest.mark.parametrize(
    ("kind", "expected_reason"),
    [
        ("convergence", "spread_converged"),
        ("stop", "adverse_spread_stop"),
        ("timeout", "max_hold_timeout"),
    ],
)
def test_replay_convergence_stop_timeout_and_exact_cost_carry(kind: str, expected_reason: str):
    dates, market, exit_index = _exit_market(kind)
    result = replay_sec_same_issuer_dual_class_spread_sleeve(
        _sec_payload(), market, dates[121], dates[exit_index]
    )
    assert len(result["trades"]) == 1
    trade = result["trades"][0]
    assert trade["exit_reason"] == expected_reason
    assert trade["held_sessions"] == ({"convergence": 1, "stop": 2, "timeout": 10}[kind])
    assert trade["total_trade_cost_usd"] == pytest.approx(
        trade["entry_trade_cost_usd"] + trade["exit_trade_cost_usd"]
    )
    inclusive_days = (
        date.fromisoformat(trade["exit_date"])
        - date.fromisoformat(trade["entry_date"])
    ).days + 1
    assert trade["short_carry_calendar_days_inclusive"] == inclusive_days
    assert trade["short_carry_usd"] == pytest.approx(
        trade["short_entry_notional_usd"]
        * SHORT_CARRY_ANNUAL_RATE
        * inclusive_days
        / 365.0
    )
    assert trade["net_pnl_usd"] == pytest.approx(
        trade["gross_pnl_usd"]
        - trade["total_trade_cost_usd"]
        - trade["short_carry_usd"]
    )
    assert trade["entry_marked_gross_lte_account_cap"] is True
    assert trade["cash_nonnegative_after_entry"] is True
    assert result["summary"]["cash_nonnegative"] is True
    assert result["summary"]["open_or_pending_invariant_passed"] is True
    assert result["summary"]["entry_marked_gross_limit_passed"] is True


def test_free_close_arbitration_occupied_discard_and_post_exit_cooldown():
    dates, market = _base_market(145)
    nws_spreads = _spread_history(len(dates))
    fox_spreads = _spread_history(len(dates))
    for spreads in (nws_spreads, fox_spreads):
        spreads[121] = 0.03
        spreads[122] = 0.0
        for index in range(123, 134):
            spreads[index] = 0.03
    nws_opens = list(nws_spreads)
    fox_opens = list(fox_spreads)
    nws_opens[122] = fox_opens[122] = 0.03
    _set_pair_spreads(
        market, "NWS/NWSA", dates, nws_spreads, open_spreads=nws_opens
    )
    _set_pair_spreads(market, "FOX/FOXA", dates, fox_spreads, open_spreads=fox_opens)

    first = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[121],
        sec_payload=_sec_payload(),
        sec_as_of=dates[121],
        ohlcv_by_ticker=market,
    )
    # Equal |z| is broken by ascending pair_id: FOX/FOXA before NWS/NWSA.
    assert first["selected_signal"]["pair_id"] == "FOX/FOXA"
    assert first["state_summary"]["pending_pair_count"] == 1
    goog_audit = next(
        row for row in first["signal_rows"] if row["pair_id"] == "GOOG/GOOGL"
    )
    assert goog_audit["data_provenance_admitted"] is False
    assert goog_audit["eligible"] is False
    provenance = first["price_provenance_contract"]
    assert provenance["economic_admitted_pair_count"] == 5
    assert provenance["excluded_pair_ids"] == ["GOOG/GOOGL"]
    assert provenance["z_zg_cold_panel_caveat"]["data_provenance_admitted"] is True
    assert provenance["z_zg_cold_panel_caveat"]["panel_requirement"] == (
        "hash_bound_exp_local_cold_panel"
    )

    second = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[122],
        sec_payload=_sec_payload(),
        sec_as_of=dates[122],
        ohlcv_by_ticker=market,
        state=first["state"],
    )
    assert second["entered_pair"]["pair_id"] == "FOX/FOXA"
    assert second["exited_pair"]["exit_reason"] == "spread_converged"
    assert second["state_summary"]["open_pair_count"] == 0

    state = second["state"]
    selected_by_day: dict[str, dict | None] = {}
    snapshots: dict[str, dict] = {}
    for index in range(123, 134):
        snapshot = build_sec_same_issuer_dual_class_spread_paper_snapshot(
            as_of=dates[index],
            sec_payload=_sec_payload(),
            sec_as_of=dates[index],
            ohlcv_by_ticker=market,
            state=state,
        )
        state = snapshot["state"]
        selected_by_day[dates[index]] = snapshot["selected_signal"]
        snapshots[dates[index]] = snapshot

    # NWS is free to win arbitration, while FOX is blocked for ten complete
    # sessions after its exit and becomes eligible on the following session.
    assert selected_by_day[dates[123]]["pair_id"] == "NWS/NWSA"
    occupied = snapshots[dates[124]]
    assert occupied["state_summary"]["open_pair_count"] == 1
    assert occupied["selected_signal"] is None
    assert {
        row.get("disposition")
        for row in occupied["signal_rows"]
        if row.get("eligible")
    } == {"discarded_open_or_pending"}
    # FOX's ten complete cooldown sessions are 123..132; it may be considered
    # again on 133 (whether selected depends on the still-open NWS trade).
    assert SAME_PAIR_COOLDOWN_SESSIONS == 10
    fox_132 = next(
        row for row in snapshots[dates[132]]["signal_rows"] if row["pair_id"] == "FOX/FOXA"
    )
    assert fox_132.get("same_pair_cooldown_pass") in {False, None}


def test_stale_as_of_and_stale_sec_identity_refuse_without_losing_contract():
    dates, market, _ = _exit_market("timeout")
    first = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[121],
        sec_payload=_sec_payload(),
        sec_as_of=dates[121],
        ohlcv_by_ticker=market,
    )
    skipped = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[123],
        sec_payload=_sec_payload(),
        sec_as_of=dates[123],
        ohlcv_by_ticker=market,
        state=first["state"],
    )
    assert skipped["status"] == "refused"
    assert skipped["reason"] == "stale_as_of_refused"

    stale_sec = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[122],
        sec_payload=_sec_payload(),
        sec_as_of=dates[121],
        ohlcv_by_ticker=market,
        state=first["state"],
    )
    assert stale_sec["status"] == "refused"
    assert stale_sec["reason"] == "stale_sec_identity_as_of"
    for snapshot in (skipped, stale_sec):
        contract = snapshot["execution_sizing_contract"]
        assert contract["paper_notional_is_evidence_only"] is True
        assert contract["experiment_notional_usd"] is None
        assert contract["live_ready"] is False
        assert contract["trade_enabled"] is False
        assert contract["maximum_entry_dollar_imbalance"] == MAX_ENTRY_DOLLAR_IMBALANCE
        assert snapshot["production_impact"]["trade_enabled"] is False


def test_replay_window_boundary_cancels_pending_and_force_closes_open():
    dates, market, _ = _exit_market("timeout")
    pending = replay_sec_same_issuer_dual_class_spread_sleeve(
        _sec_payload(), market, dates[121], dates[121]
    )
    assert pending["state"]["pending_pair"] is None
    assert pending["summary"]["audit"]["pending_cancelled_window_end"] == 1
    assert pending["trades"] == []

    open_result = replay_sec_same_issuer_dual_class_spread_sleeve(
        _sec_payload(), market, dates[121], dates[122]
    )
    assert len(open_result["trades"]) == 1
    trade = open_result["trades"][0]
    assert trade["exit_reason"] == "window_end_force_close"
    assert trade["exit_trade_cost_usd"] > 0
    assert trade["short_carry_usd"] > 0
    assert open_result["state"]["open_pair"] is None
    assert open_result["summary"]["audit"]["exit_window_end_force_close"] == 1
    assert open_result["daily_equity"][-1]["gross_exposure_usd"] == 0.0
    assert open_result["selection_contract"] == {
        "maximum_open_or_pending_pairs": 1,
        "free_close_ranking": ["descending_abs_robust_z", "ascending_pair_id"],
        "pairs_scheduled_per_free_close": 1,
        "occupied_signal_action": "discard_without_queue",
        "entry_timing": "strict_next_common_session_open",
    }
    assert open_result["cooldown_contract"]["complete_common_sessions_blocked_after_exit"] == 10
    assert open_result["cooldown_contract"]["eligible_session_offset_after_exit"] == 11


def test_replay_flags_missing_exact_open_pair_mark_in_summary():
    dates, market, _ = _exit_market("timeout")
    market["FOX"] = [
        row for row in market["FOX"] if row["Date"] != dates[123]
    ]
    result = replay_sec_same_issuer_dual_class_spread_sleeve(
        _sec_payload(), market, dates[121], dates[124]
    )
    assert result["summary"]["missing_exact_open_pair_mark_count"] == 1
    assert result["summary"]["exact_open_pair_marks_passed"] is False


def test_daily_optional_persistence_is_idempotent(tmp_path):
    dates, market, _ = _exit_market("timeout")
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshots.jsonl"
    pair_path = tmp_path / "pairs.jsonl"
    first = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[121],
        sec_payload=_sec_payload(),
        sec_as_of=dates[121],
        ohlcv_by_ticker=market,
        persist=True,
        state_path=state_path,
        snapshot_ledger_path=snapshot_path,
        pair_ledger_path=pair_path,
    )
    assert first["status"] == "ready"
    assert first["snapshot_ledger_merge"]["appended"] == 1
    assert first["pair_ledger_merge"]["appended"] == 1
    assert state_path.exists() and snapshot_path.exists() and pair_path.exists()

    duplicate = build_sec_same_issuer_dual_class_spread_paper_snapshot(
        as_of=dates[121],
        sec_payload=_sec_payload(),
        sec_as_of=dates[121],
        ohlcv_by_ticker=market,
        persist=True,
        state_path=state_path,
        snapshot_ledger_path=snapshot_path,
        pair_ledger_path=pair_path,
    )
    assert duplicate["status"] == "idempotent"
    assert duplicate["execution_sizing_contract"]["trade_enabled"] is False


def test_replay_and_sequential_daily_state_have_trade_equity_and_rule_parity():
    dates, market, exit_index = _exit_market("convergence")
    end_index = exit_index + 3
    replay = replay_sec_same_issuer_dual_class_spread_sleeve(
        _sec_payload(), market, dates[121], dates[end_index]
    )

    state = None
    snapshots: list[dict] = []
    for index in range(121, end_index + 1):
        snapshot = build_sec_same_issuer_dual_class_spread_paper_snapshot(
            as_of=dates[index],
            sec_payload=_sec_payload(),
            sec_as_of=dates[index],
            ohlcv_by_ticker=market,
            state=state,
        )
        assert snapshot["status"] == "ready"
        assert snapshot["rule_version"] == RULE_VERSION
        state = snapshot["state"]
        snapshots.append(snapshot)

    assert state is not None
    assert replay["trades"] == state["closed_pairs"]
    assert replay["state"]["cash_usd"] == pytest.approx(state["cash_usd"])
    assert replay["daily_equity"] == state["equity_curve"]
    assert replay["summary"]["signals_generated"] == state["audit"]["signals_generated"]
    assert all(snapshot["trade_enabled"] is False for snapshot in snapshots)
    assert replay["trade_enabled"] is False
