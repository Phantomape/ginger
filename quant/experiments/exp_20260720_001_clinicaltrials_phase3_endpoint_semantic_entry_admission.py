"""exp-20260720-001: PIT Phase-3 primary-endpoint semantic entry admission.

The only alpha decision under test is whether a fail-closed, structured
interpretation of PRIMARY outcome analyses can turn ClinicalTrials.gov first
results posts into a profitable default-off candidate pool.  The source
payloads, sponsor map, semantic policy, timing, hold, notional and costs were
fixed before any outcome price was read.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from clinicaltrials_phase3_results_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    ROUND_TRIP_COST_PCT,
    SEMANTIC_RULE_VERSION,
    SPONSOR_TO_TICKER,
    build_clinicaltrials_phase3_endpoint_semantic_snapshot,
    enrich_clinicaltrials_events_with_primary_endpoint_semantics,
    load_clinicaltrials_phase3_results_archive,
    replay_clinicaltrials_phase3_endpoint_semantic_paper_trades,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.experiments.exp_20260713_008_clinicaltrials_phase3_results_green_spy_relative_top1_10d_v1 import (  # noqa: E402,E501
    _baseline_window_map,
    _read_json,
    _sha_rows,
    _target_summary,
    _window_ohlcv,
    _write_json,
    combine_window,
    load_ohlcv,
)
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260720-001"
OWNER = "codex-alpha-automation"
BASELINE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "clinicaltrials_phase3_results"
HISTORY_DIR = SOURCE_DIR / "history"
ARCHIVE_PATH = SOURCE_DIR / "events.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
RESULT_PATH = OUT_DIR / "clinicaltrials_phase3_endpoint_semantic_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
ARTIFACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_clinicaltrials_phase3_endpoint_semantic_entry_admission.md"
)

WINDOWS = OrderedDict(
    (
        ("late_strong", ("2025-10-23", "2026-04-21")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("old_thin", ("2024-10-02", "2025-04-22")),
    )
)
MIN_TARGET_TRADES = 20
MIN_TARGET_TICKERS = 3
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "total_pnl_delta_sum": 10_432.91,
}
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 5_000.0,
    "main_failure_modes": [
        "semantic_abstention_too_high",
        "pharma_ticker_concentration",
        "mid_or_late_window_pnl_regression",
        "accepted_distribution_comparator_not_beaten",
        "publication_date_execution_delay",
    ],
}


def _source_density(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    grade_counts = Counter(str(row.get("semantic_grade") or "missing") for row in events)
    windows: dict[str, Any] = {}
    for label, (start, end) in WINDOWS.items():
        rows = [
            row
            for row in events
            if start <= str(row.get("results_first_post_date") or "") <= end
            and row.get("semantic_grade") == "positive"
        ]
        counts = Counter(str(row["ticker"]) for row in rows)
        windows[label] = {
            "positive_event_count": len(rows),
            "ticker_count": len(counts),
            "top1_event_share": (
                round(max(counts.values()) / len(rows), 6) if rows else None
            ),
            "by_ticker": dict(sorted(counts.items())),
        }
    positive_ticker_count = len(
        {row.get("ticker") for row in events if row.get("semantic_grade") == "positive"}
    )
    minimum_possible_top5_share = (
        round(min(5, positive_ticker_count) / positive_ticker_count, 6)
        if positive_ticker_count
        else None
    )
    return {
        "event_count": len(events),
        "ticker_count": len({row.get("ticker") for row in events}),
        "grade_counts": dict(sorted(grade_counts.items())),
        "positive_ticker_count": positive_ticker_count,
        "minimum_possible_top5_positive_contribution_share": minimum_possible_top5_share,
        "all_payload_hashes_verified": all(
            row.get("semantic_payload_hash_verified") is True for row in events
        ),
        "windows": windows,
    }


def _daily_semantic_grade_parity(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Check the shared daily grader/rank without claiming lifecycle parity."""
    by_posted: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        posted = str(event.get("results_first_post_date") or "")
        by_posted[posted].append({**event, "first_seen_date": posted})
    checks: list[dict[str, Any]] = []
    for posted, rows in sorted(by_posted.items()):
        snapshot = build_clinicaltrials_phase3_endpoint_semantic_snapshot(
            as_of_date=posted,
            observations=rows,
        )
        expected = sorted(
            (row for row in rows if row.get("semantic_grade") == "positive"),
            key=lambda row: (
                -float(row.get("semantic_strength") or 0.0),
                str(row.get("ticker") or ""),
                str(row.get("nct_id") or ""),
            ),
        )[:1]
        actual = snapshot.get("candidates") or []
        expected_ids = [str(row.get("nct_id")) for row in expected]
        actual_ids = [str(row.get("nct_id")) for row in actual]
        checks.append(
            {
                "results_first_post_date": posted,
                "expected_candidate_ids": expected_ids,
                "daily_candidate_ids": actual_ids,
                "passed": expected_ids == actual_ids,
            }
        )
    return {
        "passed": bool(checks) and all(row["passed"] for row in checks),
        "date_count": len(checks),
        "checks_sha256": _sha_rows(checks),
        "checks": checks,
        "scope": "semantic_grade_and_same_day_rank_only",
        "lifecycle_parity_complete": False,
        "lifecycle_caveat": (
            "The standalone snapshot does not persist cross-day cooldown/open/close state, "
            "and ClinicalTrials is not wired in quant/run.py."
        ),
    }


def _gate2_passed(
    events: list[dict[str, Any]],
    trades_by_window: dict[str, list[dict[str, Any]]],
) -> bool:
    return bool(events) and all(
        row.get("semantic_payload_hash_verified") is True
        and row.get("raw_sha256")
        and row.get("history_version")
        for row in events
    ) and all(
        trade.get("entry_date") and trade.get("target_price")
        for trades in trades_by_window.values()
        for trade in trades
    )


def build_payload() -> dict[str, Any]:
    baseline_summary = _read_json(BASELINE_SUMMARY)
    baseline_windows = _baseline_window_map(baseline_summary)
    archive = load_clinicaltrials_phase3_results_archive(ARCHIVE_PATH)
    events = enrich_clinicaltrials_events_with_primary_endpoint_semantics(
        archive,
        history_dir=HISTORY_DIR,
    )
    density = _source_density(events)
    daily_parity = _daily_semantic_grade_parity(events)

    broad_ohlcv, auxiliary_source = load_ohlcv("2024-09-01", "2026-05-15")
    ohlcv_by_window: dict[str, dict[str, Any]] = {}
    auxiliary_bar_identity: dict[str, Any] = {}
    for label in WINDOWS:
        ohlcv_by_window[label], auxiliary_bar_identity[label] = _window_ohlcv(
            broad_ohlcv,
            baseline_windows[label],
            auxiliary_source,
        )

    rows: dict[str, Any] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        ohlcv = ohlcv_by_window[label]
        replay = replay_clinicaltrials_phase3_endpoint_semantic_paper_trades(
            events=events,
            ohlcv_by_ticker=ohlcv,
            start=start,
            end=end,
        )
        trades = replay["trades"]
        before, after, combined_curve = combine_window(
            baseline_windows[label], trades, ohlcv
        )
        generated_total += int(replay["signals_generated"])
        survived_total += int(replay["signals_survived"])
        trades_by_window[label] = trades
        rows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    after["expected_value_score"] - before["expected_value_score"], 4
                ),
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 2),
                "max_drawdown_pct": round(
                    after["max_drawdown_pct"] - before["max_drawdown_pct"], 4
                ),
            },
            "signals_generated": replay["signals_generated"],
            "signals_survived": replay["signals_survived"],
            "survival_rate": replay["survival_rate"],
            "target_trades": trades,
            "unsettled": replay["unsettled"],
            "reject_totals": replay["reject_totals"],
            "combined_curve_sha256": _sha_rows(combined_curve),
        }

    target = _target_summary(trades_by_window)
    aggregate = {
        "before_expected_value_score_sum": round(
            sum(row["before"]["expected_value_score"] for row in rows.values()), 4
        ),
        "after_expected_value_score_sum": round(
            sum(row["after"]["expected_value_score"] for row in rows.values()), 4
        ),
        "expected_value_score_delta_sum": round(
            sum(row["delta"]["expected_value_score"] for row in rows.values()), 4
        ),
        "before_total_pnl_sum": round(
            sum(row["before"]["total_pnl"] for row in rows.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(row["after"]["total_pnl"] for row in rows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(row["delta"]["total_pnl"] for row in rows.values()), 2
        ),
        "windows_ev_improved": sum(
            row["delta"]["expected_value_score"] > 0 for row in rows.values()
        ),
        "windows_ev_regressed": sum(
            row["delta"]["expected_value_score"] < 0 for row in rows.values()
        ),
        "windows_pnl_improved": sum(
            row["delta"]["total_pnl"] > 0 for row in rows.values()
        ),
        "windows_pnl_regressed": sum(
            row["delta"]["total_pnl"] < 0 for row in rows.values()
        ),
        "max_drawdown_worse_max": max(
            row["delta"]["max_drawdown_pct"] for row in rows.values()
        ),
    }
    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": target["total_trade_count"],
        "adjusted_windows": [label for label, trades in trades_by_window.items() if trades],
        "adjusted_window_count": target["window_count"],
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": target["single_ticker_positive_share"],
        "top_5_contribution_pct": target["top_5_contribution_pct"],
        "hhi_concentration": target["hhi_concentration"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target["total_trade_count"]
            if target["total_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        require_tail_concentration_not_worse=False,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
    )
    gate4_eval = evaluate_gate4(
        gate_metrics,
        thresholds=thresholds,
        check_materiality=True,
    )
    failures = list(gate4_eval["hard_failures"])
    gate2 = _gate2_passed(events, trades_by_window)
    if not gate2:
        failures.append("gate2_source_hash_or_sentinel_failure")
    if target["total_trade_count"] < MIN_TARGET_TRADES:
        failures.append("ticket_target_trade_count_below_20")
    if target["ticker_count"] < MIN_TARGET_TICKERS:
        failures.append("ticket_target_ticker_count_below_3")
    if target["window_count"] < MIN_TARGET_WINDOWS:
        failures.append("ticket_target_window_coverage_below_3")
    if aggregate["windows_pnl_regressed"]:
        failures.append("window_pnl_regression")
    if aggregate["total_pnl_delta_sum"] <= COMPARATOR["total_pnl_delta_sum"]:
        failures.append("accepted_distribution_pnl_comparator_not_beaten")
    if not daily_parity["passed"]:
        failures.append("daily_semantic_grade_parity_failed")
    # Even before outcome prices, six semantic-positive issuers imply a best-
    # case top-five positive-contribution share of 5/6.  Preserve that
    # structural rejection independently of the realized-PnL concentration
    # metric; the canonical 60% Gate-4 cap was fixed before this run.
    source_top5_floor = density["minimum_possible_top5_positive_contribution_share"]
    if (
        source_top5_floor is not None
        and source_top5_floor > thresholds.max_top_5_contribution_pct
    ):
        failures.append("source_positive_ticker_universe_cannot_meet_top5_contribution_cap")
    failures = list(dict.fromkeys(failures))
    gate4 = {
        **gate4_eval,
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "metrics": gate_metrics,
    }

    envelope = ExecutionEnvelope(
        base_notional=BASE_NOTIONAL_USD,
        max_capital_pct=0.44,
        min_dollar_volume=None,
        slippage_bps=17.5,
        max_displacement=0,
        max_concurrent=11,
        order_semantics=(
            "first_regular_session_open_strictly_after_publication_then_"
            "tenth_session_close_default_off"
        ),
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "Default-off only; 35bps all-in costs. Cash displacement and central "
            "daily lifecycle wiring are not measured, so the result is not live-ready."
        ),
    )
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
        dsr_report=None,
    )
    verdict = full_stack_verdict(gate4=gate4, live_readiness=live, envelope=envelope)
    accepted = bool(gate4["passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if accepted else "rejected",
        "decision": (
            "accepted_paper_pending_forward_clinicaltrials_phase3_endpoint_semantic_entry_admission"
            if accepted
            else "rejected_clinicaltrials_phase3_endpoint_semantic_entry_admission"
        ),
        "accepted_alpha": accepted,
        "hypothesis": (
            "Directionally favorable, statistically significant PRIMARY endpoint "
            "evidence in exact first-results histories forms a profitable semantic "
            "entry-admission candidate pool."
        ),
        "rule_version": SEMANTIC_RULE_VERSION,
        "source": {
            "archive": str(ARCHIVE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "history_dir": str(HISTORY_DIR.relative_to(REPO_ROOT)).replace("\\", "/"),
            "density": density,
            "payload_identity_sha256": _sha_rows(
                [
                    {
                        "nct_id": row["nct_id"],
                        "history_version": row["history_version"],
                        "raw_sha256": row["raw_sha256"],
                        "semantic_grade": row["semantic_grade"],
                    }
                    for row in events
                ]
            ),
        },
        "windows": rows,
        "gate1": {
            "passed": True,
            "baseline": str(BASELINE_SUMMARY.relative_to(REPO_ROOT)).replace("\\", "/"),
            "baseline_experiment_id": baseline_summary.get("experiment_id"),
            "auxiliary_bar_identity": auxiliary_bar_identity,
        },
        "gate2": {
            "passed": gate2,
            "sentinel_fields": ["entry_date", "target_price"],
            "source_fields": [
                "history_version",
                "source_url",
                "raw_sha256",
                "semantic_payload_hash_verified",
            ],
        },
        "gate3": {
            "passed": generated_total > 0 and survived_total / generated_total >= 0.05,
            "signals_generated": generated_total,
            "signals_survived": survived_total,
            "survival_rate": round(survived_total / generated_total, 6)
            if generated_total
            else 0.0,
        },
        "aggregate": aggregate,
        "target_summary": target,
        "accepted_comparator": COMPARATOR,
        "daily_semantic_parity": daily_parity,
        "gate4": gate4,
        "full_stack": {
            "verdict": verdict,
            "daily_semantic_grade_parity_complete": daily_parity["passed"],
            "daily_candidate_lifecycle_parity_complete": False,
            "daily_pipeline_wiring_complete": False,
            "execution_envelope": envelope.to_dict(),
            "live_readiness": live,
        },
        "prediction": PREDICTION,
        "alpha_synthesis_pass": {
            "baseline_universe": [
                "twelve exact mapped public Phase-3 lead sponsors",
                "canonical cash-feasible core universe from exp-20260715-010",
            ],
            "opportunity_cost_winner": "clinicaltrials_phase3_primary_endpoint_semantic_entry_admission",
            "evidence_surfaces_used": [
                "ClinicalTrials exact Record History payloads",
                "canonical OHLCV",
                "cash-feasible Gate-1 return panels",
            ],
            "evidence_surfaces_missing": [
                "authorized historical borrow availability/utilization",
                "authorized USPTO weekly XML archive and effective-dated issuer map",
                "centrally wired daily ClinicalTrials lifecycle state",
            ],
            "hypothesis_candidates": [
                "positive PRIMARY endpoint semantic entry admission",
                "serious-adverse-event control comparison",
                "negative PRIMARY endpoint exclusion",
            ],
            "selected_hypothesis": "positive PRIMARY endpoint semantic entry admission",
            "economic_mechanism": (
                "Successful Phase-3 efficacy evidence changes commercialization and label-expansion odds; "
                "the prior source treated all results posts alike."
            ),
            "falsifier": (
                "Too few trades, excessive pharma concentration, any window regression, "
                "or failure to beat the accepted paper comparator after costs."
            ),
            "evidence_grade": "gate_candidate",
            "next_machine_action": "judge and close the fixed three-window replay",
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "core_ranking_changed": False,
            "core_sizing_changed": False,
            "core_exits_changed": False,
            "run_adapter_changed": False,
            "shared_helper": "quant/clinicaltrials_phase3_results_paper_sleeve.py",
            "daily_snapshot_function_available": True,
            "daily_pipeline_wiring_changed": False,
        },
        "post_run_reflection": {
            "why_result_happened": "; ".join(failures) if failures else "All fixed gates passed.",
            "forbidden_near_neighbor_retry": (
                "Do not retune endpoint lexicons, p-value/CI rules, sponsor aliases, semantic rank, "
                "hold, cooldown, notional, costs, or window slices on this frozen source."
            ),
            "new_evidence_required": (
                "A genuinely different clinical endpoint source/gate shape, or at least 30 closed "
                "forward replacement-value decisions with complete daily lifecycle parity."
            ),
        },
        "reproduction_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            + Path(__file__).name
        ),
    }


def _write_close_artifacts(payload: dict[str, Any]) -> None:
    rows = payload["windows"]
    before = {
        "schema": "clinicaltrials_semantic_gate4_aggregate_before_v1",
        "expected_value_score": payload["aggregate"]["before_expected_value_score_sum"],
        "total_pnl": payload["aggregate"]["before_total_pnl_sum"],
        "max_drawdown_pct": max(row["before"]["max_drawdown_pct"] for row in rows.values()),
        "total_trades": sum(row["before"]["total_trades"] for row in rows.values()),
        "survival_rate": min(row["before"]["survival_rate"] for row in rows.values()),
        "benchmarks": {
            "strategy_total_return_pct": round(
                payload["aggregate"]["before_total_pnl_sum"] / 100_000.0, 4
            )
        },
    }
    after = {
        "schema": "clinicaltrials_semantic_gate4_aggregate_after_v1",
        "expected_value_score": payload["aggregate"]["after_expected_value_score_sum"],
        "total_pnl": payload["aggregate"]["after_total_pnl_sum"],
        "max_drawdown_pct": max(row["after"]["max_drawdown_pct"] for row in rows.values()),
        "total_trades": sum(row["after"]["total_trades"] for row in rows.values()),
        "survival_rate": payload["gate3"]["survival_rate"],
        "benchmarks": {
            "strategy_total_return_pct": round(
                payload["aggregate"]["after_total_pnl_sum"] / 100_000.0, 4
            )
        },
    }
    _write_json(BEFORE_PATH, before)
    _write_json(AFTER_PATH, after)


def _write_artifact(payload: dict[str, Any]) -> None:
    failures = payload["gate4"]["hard_failures"]
    density = payload["source"]["density"]
    lines = [
        f"# {EXPERIMENT_ID} ClinicalTrials Phase-3 endpoint semantics",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Rule: `{payload['rule_version']}`",
        f"- Exact events / positive grades / tickers: `{density['event_count']}` / "
        f"`{density['grade_counts'].get('positive', 0)}` / `{density['positive_ticker_count']}`",
        f"- Closed target trades / tickers / windows: `{payload['target_summary']['total_trade_count']}` / "
        f"`{payload['target_summary']['ticker_count']}` / `{payload['target_summary']['window_count']}`",
        f"- Aggregate EV delta: `{payload['aggregate']['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `${payload['aggregate']['total_pnl_delta_sum']:,.2f}`",
        f"- Top-5 positive contribution: `{payload['target_summary']['top_5_contribution_pct']}`",
        f"- Gate-3 survival: `{payload['gate3']['survival_rate']:.2%}`",
        f"- Gate-4 failures: `{', '.join(failures) or 'none'}`",
        "",
        "The exact source payload SHA, treatment/control measurement direction, and next-session timing are audited. "
        "The helper and daily snapshot remain default-off; central scheduling and lifecycle parity are incomplete.",
    ]
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_payload()
    _write_json(RESULT_PATH, payload)
    _write_close_artifacts(payload)
    _write_artifact(payload)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "source_density": payload["source"]["density"],
                "target_summary": payload["target_summary"],
                "aggregate": payload["aggregate"],
                "gate4_failures": payload["gate4"]["hard_failures"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
