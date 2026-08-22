import json

import pytest

import scripts.build_reopen_readiness as readiness


def _write_estimate_revision_readiness(
    root,
    *,
    independent=115,
    mapped=115,
    conflicts=0,
    h5=0,
    h10=0,
    h20=0,
):
    path = (
        root
        / "data"
        / "non_ohlcv"
        / "estimate_revision_readiness_latest.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "surface_id": "analyst_estimate_revision_forward_decisions",
        "independent_decisions": independent,
        "mapped_ticker_count": mapped,
        "actual_cash_conflict_decisions": conflicts,
        "settled_independent_decisions_by_horizon": {
            "h5": h5,
            "h10": h10,
            "h20": h20,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_drawdown_state(root, rows):
    folder = (
        root
        / "data"
        / "paper_sleeves"
        / "core_drawdown_flow_put_stabilization"
    )
    folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "pending_entries": [],
                "open_positions": [],
                "closed_positions": rows,
                "skipped_entries": [],
            }
        ),
        encoding="utf-8",
    )
    return folder


def _write_drawdown_snapshots(folder, *, generated=100, survived=10):
    payload = {
        "asof_date": "2026-07-23",
        "stage_counts": {
            "price_stabilized": generated,
            "options_complete": survived,
        },
    }
    (folder / "snapshots.jsonl").write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )


def _write_intraday_outcomes(root, rows, *, date_tag="20260724"):
    folder = (
        root
        / "data"
        / "daily"
        / "intraday"
        / "backtests"
        / "outcome_ledgers"
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"intraday_triage_outcomes_{date_tag}.jsonl"
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _write_form4_forward_state(root, *, fail_closed=False, closed=25, high=8, share=0.2):
    folder = root / "data" / "non_ohlcv" / "form4_sale_overhang_forward"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "state.json"
    path.write_text(
        json.dumps(
            {
                "status": "ok" if not fail_closed else "failed_stale_candidate_producer",
                "health": {
                    "status": "ok_fresh_inputs" if not fail_closed else "failed_stale_input",
                    "fail_closed": fail_closed,
                    "reasons": [] if not fail_closed else ["candidate_producer_stale"],
                },
                "forward_reopen_progress": {
                    "closed_forward_rows_current": closed,
                    "high_sale_overhang_closed_forward_rows_current": high,
                    "replacement_value_complete_closed_rows_current": closed,
                    "unique_tickers_closed_forward_rows": 10 if closed else 0,
                    "max_single_ticker_closed_forward_row_share": share if closed else None,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_prediction_market_snapshot(root, date_tag, items):
    folder = (
        root
        / "data"
        / "non_ohlcv"
        / "prediction_market_event_observer"
        / "daily"
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"prediction_market_event_observer_{date_tag}.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def _write_prediction_market_outcomes(root, rows, *, date_tag="20260803"):
    folder = (
        root
        / "data"
        / "non_ohlcv"
        / "prediction_market_event_observer"
        / "outcome_ledgers"
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"prediction_market_event_observer_outcomes_{date_tag}.jsonl"
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _prediction_item(market, query, probability):
    return {
        "provider_market_id": market,
        "prediction_market_query_id": query,
        "yes_probability": probability,
    }


def _prediction_settlement(
    market,
    ticker,
    observed_date,
    query,
    *,
    status="settled",
):
    return {
        "provider_market_id": market,
        "candidate_ticker": ticker,
        "observed_date": observed_date,
        "prediction_market_query_id": query,
        "horizon_trading_days": 10,
        "outcome_status": status,
        "exit_date": "2026-08-03" if status == "settled" else None,
    }


def _write_massive_readiness_inputs(
    root,
    settlement_rows,
    *,
    summary_count,
    status="ok",
    alert=False,
):
    folder = root / "data" / "non_ohlcv" / "massive_dividend_restart_forward"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "settlement_ledger.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in settlement_rows),
        encoding="utf-8",
    )
    summary = {
        "scope": "default_off_massive_dividend_restart_forward_settlement",
        "source_experiment": "exp-20260803-002",
        "target_gap_variant": "restart_after_observed_gap",
        "reopen_required_settled_decisions": 30,
        "observer_only": True,
        "trade_enabled": False,
        "status": status,
        "alert": alert,
        "settled_restart_decision_count": summary_count,
        "reopen_progress": {
            "required": 30,
            "settled_restart_decisions": summary_count,
        },
    }
    (folder / "latest_settlement_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    return folder


def test_form4_forward_readiness_is_zero_before_prospective_state_exists(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_form4_sale_overhang_forward()

    assert lane["status"] == "not_ready"
    assert lane["counters"]["closed_forward_rows"] == 0
    assert lane["counters"]["observer_health_fail_closed"] is True
    assert lane["checks"]["observer_health_ok"] is False


def test_form4_forward_readiness_requires_healthy_producer(
    monkeypatch,
    tmp_path,
):
    _write_form4_forward_state(tmp_path, fail_closed=True)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_form4_sale_overhang_forward()

    assert lane["counters"]["closed_forward_rows"] == 25
    assert lane["checks"]["closed_forward_rows_at_least_25"] is True
    assert lane["checks"]["observer_health_ok"] is False
    assert lane["status"] == "not_ready"


def test_form4_forward_readiness_accepts_only_complete_diverse_healthy_rows(
    monkeypatch,
    tmp_path,
):
    _write_form4_forward_state(tmp_path)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_form4_sale_overhang_forward()

    assert all(lane["checks"].values())
    assert lane["status"] == "ready"


def _intraday_next_close_row(
    index,
    *,
    status="closed",
    horizon_time="2026-07-24 15:55:00",
    decision_timestamp="2026-07-23 13:05:00",
    final_action="HOLD_ONLY",
):
    return {
        "outcome_rule_version": "intraday_triage_counterfactual_outcome_v2",
        "observation_id": f"observation-{index:03d}",
        "ticker": f"T{index:03d}",
        "primary_ticker_day_decision": True,
        "horizon": "next_close",
        "status": status,
        "execution_time": f"2026-07-23 13:{index % 60:02d}:00-{index:03d}",
        "decision_timestamp": decision_timestamp,
        "horizon_time": horizon_time,
        "final_action": final_action,
    }


def test_intraday_close_readiness_excludes_partial_session_and_duplicates(
    monkeypatch,
    tmp_path,
):
    # Mirror the 20260724 shape: 118 effective rows, of which 106 were labelled
    # closed, but 12 used the partial 13:05 target-session bar.  Nineteen raw
    # retry rows share an economic cohort and cannot add independent evidence.
    completed = [_intraday_next_close_row(index) for index in range(94)]
    partial = [
        _intraday_next_close_row(index, horizon_time="2026-07-24 13:05:00")
        for index in range(94, 106)
    ]
    pending = [
        _intraday_next_close_row(
            index,
            status="pending_horizon_bar",
            horizon_time=None,
        )
        for index in range(106, 118)
    ]
    duplicates = []
    for index in range(19):
        duplicate = dict(completed[index])
        duplicate["observation_id"] = f"earlier-retry-{index:03d}"
        duplicate["decision_timestamp"] = "2026-07-23 12:55:00"
        duplicates.append(duplicate)
    _write_intraday_outcomes(
        tmp_path,
        completed + partial + pending + duplicates,
    )
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_intraday_triage_completed_close_settlement()

    assert lane["counters"] == {
        "raw_primary_next_close_rows": 137,
        "effective_next_close_rows": 118,
        "raw_closed_next_close_rows": 125,
        "effective_closed_next_close_rows": 106,
        "raw_strict_completed_next_close_settlements": 113,
        "strict_effective_next_close_settlements": 94,
        "duplicate_economic_rows_excluded": 19,
        "incomplete_closed_effective_rows_excluded": 12,
        "strict_effective_next_close_reduce_risk_settlements": 0,
        "first_half_strict_effective_next_close_reduce_risk_settlements": 0,
        "second_half_strict_effective_next_close_reduce_risk_settlements": 0,
    }
    assert lane["thresholds"] == {
        "strict_effective_next_close_settlements": 100,
        "strict_effective_next_close_reduce_risk_settlements": 48,
        "first_half_strict_effective_next_close_reduce_risk_settlements": 12,
        "second_half_strict_effective_next_close_reduce_risk_settlements": 12,
    }
    assert lane["status"] == "not_ready"


def test_intraday_close_readiness_requires_twenty_active_reductions(
    monkeypatch,
    tmp_path,
):
    rows = [
        _intraday_next_close_row(
            index,
            final_action=(
                "REDUCE_RISK"
                if index in {*range(5), *range(50, 55)}
                else "HOLD_ONLY"
            ),
        )
        for index in range(100)
    ]
    _write_intraday_outcomes(
        tmp_path,
        rows,
    )
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_intraday_triage_completed_close_settlement()

    assert lane["counters"]["strict_effective_next_close_settlements"] == 100
    assert (
        lane["counters"][
            "strict_effective_next_close_reduce_risk_settlements"
        ]
        == 10
    )
    assert lane["status"] == "not_ready"


def test_intraday_close_readiness_accepts_balanced_active_action_power(
    monkeypatch,
    tmp_path,
):
    # exp-20260730-003 consumed the 20/5/5 bar and rejected; ready now requires
    # the declared 48/12/12 bar.  The chronological sort interleaves indices by
    # execution minute (m, 60+m), so the first half is {0..24} | {60..84}.
    rows = [
        _intraday_next_close_row(
            index,
            final_action=(
                "REDUCE_RISK"
                if index in {*range(24), *range(25, 49)}
                else "HOLD_ONLY"
            ),
        )
        for index in range(100)
    ]
    _write_intraday_outcomes(tmp_path, rows)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_intraday_triage_completed_close_settlement()

    assert lane["counters"]["strict_effective_next_close_settlements"] == 100
    assert (
        lane["counters"][
            "strict_effective_next_close_reduce_risk_settlements"
        ]
        == 48
    )
    assert (
        lane["counters"][
            "first_half_strict_effective_next_close_reduce_risk_settlements"
        ]
        == 24
    )
    assert (
        lane["counters"][
            "second_half_strict_effective_next_close_reduce_risk_settlements"
        ]
        == 24
    )
    assert lane["status"] == "ready"


def test_intraday_close_readiness_requires_chronological_balance(
    monkeypatch,
    tmp_path,
):
    rows = [
        _intraday_next_close_row(
            index,
            final_action=(
                "REDUCE_RISK"
                if index in {*range(29), *range(60, 79)}
                else "HOLD_ONLY"
            ),
        )
        for index in range(100)
    ]
    _write_intraday_outcomes(tmp_path, rows)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_intraday_triage_completed_close_settlement()

    assert (
        lane["counters"][
            "strict_effective_next_close_reduce_risk_settlements"
        ]
        == 48
    )
    assert (
        lane["counters"][
            "first_half_strict_effective_next_close_reduce_risk_settlements"
        ]
        == 44
    )
    assert (
        lane["counters"][
            "second_half_strict_effective_next_close_reduce_risk_settlements"
        ]
        == 4
    )
    assert lane["status"] == "not_ready"


def test_intraday_close_readiness_requires_final_action(monkeypatch, tmp_path):
    row = _intraday_next_close_row(0)
    row.pop("final_action")
    _write_intraday_outcomes(tmp_path, [row])
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match="non-empty final_action"):
        readiness.lane_intraday_triage_completed_close_settlement()


def test_intraday_close_readiness_rejects_legacy_rule(monkeypatch, tmp_path):
    row = _intraday_next_close_row(0)
    row["outcome_rule_version"] = "intraday_triage_counterfactual_outcome_v1"
    _write_intraday_outcomes(tmp_path, [row])
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match="requires one canonical v2"):
        readiness.lane_intraday_triage_completed_close_settlement()


def test_intraday_close_readiness_requires_exact_1555_bar(monkeypatch, tmp_path):
    _write_intraday_outcomes(
        tmp_path,
        [_intraday_next_close_row(0, horizon_time="2026-07-24 15:56:00")],
    )
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_intraday_triage_completed_close_settlement()

    assert lane["counters"]["strict_effective_next_close_settlements"] == 0
    assert lane["status"] == "not_ready"


def test_phase2_estimate_revision_maps_canonical_counters(monkeypatch, tmp_path):
    _write_estimate_revision_readiness(tmp_path)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_phase2_estimate_revision()

    assert lane["counters"] == {
        "qualified_nonflat_decisions": 115,
        "mapped_tickers": 115,
        "actual_cash_conflicts": 0,
        "settled_h5": 0,
        "settled_h10": 0,
        "settled_h20": 0,
    }
    assert lane["status"] == "not_ready"
    assert lane["counter_source"] == (
        "data/non_ohlcv/estimate_revision_readiness_latest.json"
    )


def test_phase2_estimate_revision_requires_every_reopen_bar(monkeypatch, tmp_path):
    _write_estimate_revision_readiness(
        tmp_path,
        independent=30,
        mapped=10,
        conflicts=10,
        h5=30,
        h10=30,
        h20=30,
    )
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_phase2_estimate_revision()

    assert lane["status"] == "ready"


@pytest.mark.parametrize(
    "field,value",
    [
        ("independent_decisions", True),
        ("mapped_ticker_count", -1),
        ("actual_cash_conflict_decisions", "10"),
    ],
)
def test_phase2_estimate_revision_rejects_malformed_counts(
    monkeypatch,
    tmp_path,
    field,
    value,
):
    path = _write_estimate_revision_readiness(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match=field):
        readiness.lane_phase2_estimate_revision()


def test_phase2_estimate_revision_missing_input_fails_closed_in_build(
    monkeypatch,
    tmp_path,
):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(
        readiness,
        "OUTPUT_PATH",
        str(tmp_path / "data" / "reopen_readiness.json"),
    )
    monkeypatch.setattr(
        readiness,
        "LANES",
        {"phase2_estimate_revision": readiness.lane_phase2_estimate_revision},
    )

    result = readiness.build()

    lane = result["lanes"][0]
    assert lane["status"] == "error"
    assert lane["counters"] == {}
    assert "FileNotFoundError" in lane["note"]


def test_core_drawdown_missing_state_is_truthful_zero_and_fail_closed(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_core_drawdown_flow_put_stabilization()

    assert lane["counters"]["independent_closed_decisions"] == 0
    assert lane["counters"]["independent_selected_decisions"] == 0
    assert lane["counters"]["survival_rate"] is None
    assert lane["checks"]["independent_closed_decisions_at_least_20"] is False
    assert lane["checks"]["survival_rate_at_least_5pct"] is None
    assert (
        lane["checks"][
            "positive_net_replacement_value_both_chronological_halves"
        ]
        is None
    )
    assert lane["status"] == "not_ready"
    assert "truthful forward closed count is 0" in lane["note"]
    assert "Retrospective exp-20260723-004 folds" in lane["note"]


def test_core_drawdown_secondary_checks_derive_from_forward_state(
    monkeypatch,
    tmp_path,
):
    closed = [
        {
            "decision_id": f"decision-{index:02d}",
            "ticker": f"T{index % 5}",
            "entry_date": f"2026-06-{index + 1:02d}",
            "exit_date": f"2026-07-{index + 1:02d}",
            "evaluation_window": "first" if index < 10 else "second",
            "pnl": 1.0,
        }
        for index in range(20)
    ]
    folder = _write_drawdown_state(tmp_path, closed)
    _write_drawdown_snapshots(folder, generated=100, survived=10)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_core_drawdown_flow_put_stabilization()

    assert lane["counters"]["independent_closed_decisions"] == 20
    assert lane["counters"]["survival_rate"] == 0.1
    assert lane["counters"]["first_half_net_replacement_value_usd"] == 10.0
    assert lane["counters"]["second_half_net_replacement_value_usd"] == 10.0
    assert lane["counters"]["max_single_ticker_positive_pnl_share"] == 0.2
    assert (
        lane["counters"]["minimum_selected_decisions_per_evaluation_window"]
        == 10
    )
    assert (
        lane["counters"]["minimum_settled_decisions_per_evaluation_window"]
        == 10
    )
    assert all(value is True for value in lane["checks"].values())
    assert lane["status"] == "ready"


def test_core_drawdown_window_density_stays_unknown_without_explicit_labels(
    monkeypatch,
    tmp_path,
):
    closed = [
        {
            "decision_id": f"decision-{index:02d}",
            "ticker": f"T{index % 5}",
            "entry_date": f"2026-06-{index + 1:02d}",
            "exit_date": f"2026-07-{index + 1:02d}",
            "pnl": 1.0,
        }
        for index in range(20)
    ]
    folder = _write_drawdown_state(tmp_path, closed)
    _write_drawdown_snapshots(folder, generated=100, survived=10)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_core_drawdown_flow_put_stabilization()

    assert (
        lane["checks"][
            "at_least_5_selected_and_5_settled_per_evaluation_window"
        ]
        is None
    )
    assert lane["status"] == "not_ready"


def test_prediction_market_postfix_counts_first_seen_and_dedupes_query_overlap(
    monkeypatch,
    tmp_path,
):
    _write_prediction_market_snapshot(
        tmp_path,
        "20260717",
        [_prediction_item("old-market", "q-old", 0.50)],
    )
    _write_prediction_market_snapshot(
        tmp_path,
        "20260718",
        [
            _prediction_item("old-market", "q-old", 0.60),
            _prediction_item("market-1", "q-1", 0.10),
            _prediction_item("market-2", "q-2", 0.20),
            _prediction_item("market-3", "q-3", 0.30),
        ],
    )
    _write_prediction_market_snapshot(
        tmp_path,
        "20260719",
        [
            _prediction_item("market-1", "q-1", 0.11),
            _prediction_item("market-2", "q-2", 0.30),
            _prediction_item("market-3", "q-3", 0.30),
        ],
    )
    _write_prediction_market_outcomes(
        tmp_path,
        [
            _prediction_settlement(
                "old-market", "OLD", "2026-07-18", "q-old"
            ),
            _prediction_settlement(
                "market-1", "AAA", "2026-07-19", "q-1"
            ),
            # Same economic decision returned by a second query cannot inflate
            # readiness or query breadth.
            _prediction_settlement(
                "market-1", "AAA", "2026-07-19", "q-overlap"
            ),
            _prediction_settlement(
                "market-2", "BBB", "2026-07-19", "q-2"
            ),
            _prediction_settlement(
                "market-3",
                "CCC",
                "2026-07-19",
                "q-3",
                status="unsettled_horizon",
            ),
        ],
    )
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_prediction_market_postfix()

    assert lane["counters"] == {
        "postfix_observation_rows": 6,
        "postfix_unique_markets": 3,
        "raw_settled_candidate_rows": 3,
        "unique_settled_candidates": 2,
        "duplicate_candidate_rows_excluded": 1,
        "decision_date_count": 1,
        "query_group_count": 2,
        "top_ticker_share": 0.5,
        "top_query_share": 0.5,
        "markets_with_any_probability_change": 2,
        "markets_with_any_5pp_move": 1,
    }
    assert lane["thresholds"] == {
        "unique_settled_candidates": 60,
        "decision_date_count": 10,
        "query_group_count": 3,
        "top_ticker_share_max": 0.15,
        "top_query_share_max": 0.5,
        "markets_with_any_probability_change": 20,
        "markets_with_any_5pp_move": 10,
    }
    assert lane["status"] == "not_ready"


def test_prediction_market_postfix_requires_every_frozen_bar(
    monkeypatch,
    tmp_path,
):
    initial = [
        _prediction_item(f"market-{index:02d}", f"q-{index % 3}", 0.20)
        for index in range(60)
    ]
    changed = [
        _prediction_item(
            f"market-{index:02d}",
            f"q-{index % 3}",
            0.30 if index < 10 else 0.21,
        )
        for index in range(20)
    ]
    _write_prediction_market_snapshot(tmp_path, "20260718", initial)
    _write_prediction_market_snapshot(tmp_path, "20260719", changed)
    outcomes = [
        _prediction_settlement(
            f"market-{index:02d}",
            f"T{index % 10}",
            f"2026-07-{19 + index % 10:02d}",
            f"q-{index % 3}",
        )
        for index in range(60)
    ]
    _write_prediction_market_outcomes(tmp_path, outcomes)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_prediction_market_postfix()

    assert lane["counters"]["unique_settled_candidates"] == 60
    assert lane["counters"]["decision_date_count"] == 10
    assert lane["counters"]["query_group_count"] == 3
    assert lane["counters"]["top_ticker_share"] == 0.1
    assert lane["counters"]["top_query_share"] <= 0.5
    assert lane["counters"]["markets_with_any_probability_change"] == 20
    assert lane["counters"]["markets_with_any_5pp_move"] == 10
    assert all(lane["checks"].values())
    assert lane["status"] == "ready"


def test_prediction_market_postfix_missing_inputs_fail_closed_in_build(
    monkeypatch,
    tmp_path,
):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(
        readiness,
        "OUTPUT_PATH",
        str(tmp_path / "data" / "reopen_readiness.json"),
    )
    monkeypatch.setattr(
        readiness,
        "LANES",
        {"prediction_market_postfix": readiness.lane_prediction_market_postfix},
    )

    result = readiness.build()

    lane = result["lanes"][0]
    assert lane["status"] == "error"
    assert "FileNotFoundError" in lane["note"]


def test_prediction_market_postfix_rejects_pre_first_seen_and_normalizes_identity(
    monkeypatch,
    tmp_path,
):
    _write_prediction_market_snapshot(
        tmp_path,
        "20260801",
        [_prediction_item("late-market", "q", 0.40)],
    )
    rows = [
        _prediction_settlement(
            "late-market", "AAA", "2026-07-30", "q"
        ),
        _prediction_settlement(
            "late-market", " AAA ", "2026-08-01", " Q "
        ),
        _prediction_settlement(
            "late-market", "AAA", "2026-08-01", "q"
        ),
    ]
    _write_prediction_market_outcomes(tmp_path, rows)
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_prediction_market_postfix()

    assert lane["counters"]["raw_settled_candidate_rows"] == 2
    assert lane["counters"]["unique_settled_candidates"] == 1
    assert lane["counters"]["duplicate_candidate_rows_excluded"] == 1
    assert lane["counters"]["decision_date_count"] == 1
    assert lane["counters"]["query_group_count"] == 1
    assert lane["counters"]["top_ticker_share"] == 1.0

    malformed = list(rows)
    malformed.append(
        _prediction_settlement(
            "late-market", "BBB", "2026-8-01", "q"
        )
    )
    _write_prediction_market_outcomes(tmp_path, malformed)

    with pytest.raises(ValueError, match="invalid observed_date"):
        readiness.lane_prediction_market_postfix()


def _massive_settlement(decision_key, *, settled=True, variant="restart_after_observed_gap"):
    return {
        "record_type": "settlement",
        "decision_key": decision_key,
        "settled": settled,
        "gap_variant": variant,
    }


def test_massive_dividend_restart_zero_is_registered_and_not_ready(
    monkeypatch,
    tmp_path,
):
    _write_massive_readiness_inputs(
        tmp_path,
        [{"record_type": "date_resolution", "declaration_date": "2026-07-01"}],
        summary_count=0,
    )
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_massive_dividend_restart_forward()

    assert lane["counters"]["settled_restart_decisions"] == 0
    assert lane["checks"]["producer_health_ok"] is True
    assert lane["checks"]["summary_ledger_counts_aligned"] is True
    assert lane["status"] == "not_ready"
    assert (
        readiness.LANES["massive_dividend_restart_forward"]
        is readiness.lane_massive_dividend_restart_forward
    )


def test_massive_dividend_restart_dedupes_and_requires_healthy_alignment(
    monkeypatch,
    tmp_path,
):
    settlements = [
        _massive_settlement(f"decision-{index:02d}") for index in range(30)
    ]
    settlements.extend(
        [
            _massive_settlement("decision-00"),
            _massive_settlement(
                "other-variant",
                variant="no_prior_positive_in_provider_history",
            ),
            _massive_settlement("voided-restart", settled=False),
        ]
    )
    _write_massive_readiness_inputs(
        tmp_path,
        settlements,
        summary_count=30,
    )
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_massive_dividend_restart_forward()

    assert lane["counters"]["settled_restart_decisions"] == 30
    assert lane["counters"]["duplicate_settlement_events_excluded"] == 1
    assert all(lane["checks"].values())
    assert lane["status"] == "ready"

    summary_path = (
        tmp_path
        / "data"
        / "non_ohlcv"
        / "massive_dividend_restart_forward"
        / "latest_settlement_summary.json"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["settled_restart_decision_count"] = 29
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    misaligned = readiness.lane_massive_dividend_restart_forward()
    assert misaligned["checks"]["summary_ledger_counts_aligned"] is False
    assert misaligned["status"] == "not_ready"

    summary["settled_restart_decision_count"] = 30
    summary["reopen_progress"]["settled_restart_decisions"] = 29
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    progress_misaligned = readiness.lane_massive_dividend_restart_forward()
    assert progress_misaligned["checks"]["summary_ledger_counts_aligned"] is False
    assert progress_misaligned["status"] == "not_ready"

    summary["reopen_progress"]["settled_restart_decisions"] = 30
    summary["reopen_progress"]["required"] = 29
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    wrong_required = readiness.lane_massive_dividend_restart_forward()
    assert wrong_required["checks"]["frozen_contract_identity_ok"] is False
    assert wrong_required["status"] == "not_ready"

    summary["reopen_progress"] = []
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="reopen_progress must be an object"):
        readiness.lane_massive_dividend_restart_forward()

    summary["reopen_progress"] = {
        "required": 30,
        "settled_restart_decisions": 30,
    }
    summary["status"] = "error"
    summary["alert"] = True
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    unhealthy = readiness.lane_massive_dividend_restart_forward()
    assert unhealthy["checks"]["producer_health_ok"] is False
    assert unhealthy["status"] == "not_ready"


def test_massive_dividend_restart_missing_inputs_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(readiness, "REPO_ROOT", str(tmp_path))

    lane = readiness.lane_massive_dividend_restart_forward()

    assert lane["counters"]["settled_restart_decisions"] == 0
    assert lane["checks"]["settlement_ledger_exists"] is False
    assert lane["checks"]["settlement_summary_exists"] is False
    assert lane["status"] == "not_ready"
