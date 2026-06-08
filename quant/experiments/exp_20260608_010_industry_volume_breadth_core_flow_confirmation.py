"""exp-20260608-010: core-flow confirmed industry volume-breadth repair.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable on top of exp-20260607-014: admit industry
volume-breadth laggard repair candidates only when the signal date already has
core A/B entry flow, while excluding same-ticker core overlap so the paper row
tests independent replacement value.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import exp_20260607_014_industry_volume_breadth_laggard_repair as previous


framework = previous.previous.base.framework

EXPERIMENT_ID = "exp-20260608-010"
STEM = "industry_volume_breadth_core_flow_confirmation"
TRIAL_FAMILY = "industry_volume_breadth_core_flow_confirmed_candidate_pool"
TRIAL_VARIANT_ID = "same_day_core_flow_nonoverlap_top1_10d_v1"
CHANGED_VARIABLE = "industry_volume_breadth_core_flow_confirmed_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_010_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SCRIPT_PATH = Path(__file__)

CORE_FLOW_CONFIRMATION_REQUIRED = True
EXCLUDE_SAME_TICKER_CORE_OVERLAP = True

PREDICTION = {
    "success_probability": 0.19,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "volume_chase_noise",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_laggard_repair_near_neighbor",
    ],
    "confidence_reason": (
        "exp-20260607-014 rejected the raw volume-breadth repair source; "
        "exp-20260608-007/008 showed same-day core-flow confirmation can "
        "rescue a relation alpha. This tests whether core-flow is an "
        "orthogonal production-visible discriminator, not a threshold retune."
    ),
    "recorded_at": "2026-06-08T09:06:03Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "live_realism_evaluated": False,
    "live_ready": False,
    "activation_envelope": {
        "intended_notional": "replay-only default-off paper at fixed $4,000 notional",
        "capital_cap": "no live capital; positive replay would require shared helper and later activation envelope",
        "liquidity_slippage_model": (
            "historical replay uses price >= $10, ADV20 >= $50M, next-open "
            "entry, target-side sell slippage, and round-trip cost"
        ),
        "portfolio_displacement": "paper overlay versus cash/core baseline only; no live displacement",
        "kill_switch": "not evaluated for live; future activation requires forward replacement-value and drawdown/concentration gates",
        "order_semantics": "no orders emitted",
    },
    "parity_note": (
        "This experiment changes no production code. A positive replay would "
        "require a shared default-off adapter that computes the same fixed "
        "industry volume-breadth laggard repair source, same-day core A/B "
        "flow confirmation, same-ticker overlap exclusion, next-open paper "
        "entry, 10-trading-day exit, costs, cooldown, and concentration "
        "controls in both replay and daily production before any report "
        "queue, paper ledger, candidate priority, sizing, watchlist, or order "
        "surface could change."
    ),
}

BASE_CANDIDATE_ROWS_FOR_WINDOW = previous._candidate_rows_for_window
BASE_GATE4 = previous._gate4
BASE_BUILD_PAYLOAD = previous._build_payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, contexts, scan = BASE_CANDIDATE_ROWS_FOR_WINDOW(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    raw_count = len(candidates)
    same_day_count = sum(1 for row in candidates if row.get("same_day_ab_overlap"))
    same_ticker_overlap_count = sum(
        1 for row in candidates if row.get("same_ticker_ab_overlap")
    )

    filtered: list[dict[str, Any]] = []
    filtered_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_core_flow_count = 0
    same_ticker_excluded_count = 0

    for row in candidates:
        confirmation = {
            "required": CORE_FLOW_CONFIRMATION_REQUIRED,
            "same_day_ab_entry_count": int(row.get("same_day_ab_entry_count") or 0),
            "same_day_ab_overlap": bool(row.get("same_day_ab_overlap")),
            "same_ticker_core_overlap": bool(row.get("same_ticker_ab_overlap")),
            "same_ticker_core_overlap_excluded": EXCLUDE_SAME_TICKER_CORE_OVERLAP,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
            "rule_version": RULE_VERSION,
        }
        row["core_flow_confirmation"] = confirmation
        row["rule_version"] = RULE_VERSION
        if not row.get("same_day_ab_overlap"):
            row["filter_reason"] = "missing_same_day_core_ab_flow"
            missing_core_flow_count += 1
            continue
        if EXCLUDE_SAME_TICKER_CORE_OVERLAP and row.get("same_ticker_ab_overlap"):
            row["filter_reason"] = "same_ticker_core_overlap_excluded"
            same_ticker_excluded_count += 1
            continue
        filtered.append(row)
        filtered_by_date[str(row["date"])].append(row)

    for context in contexts:
        signal_date = str(context.get("date") or "")
        day_rows = filtered_by_date.get(signal_date, [])
        context["core_flow_confirmation_required"] = CORE_FLOW_CONFIRMATION_REQUIRED
        context["same_ticker_core_overlap_excluded"] = EXCLUDE_SAME_TICKER_CORE_OVERLAP
        context["raw_candidate_count_before_core_flow_filter"] = context.get(
            "raw_candidate_count",
            0,
        )
        context["raw_candidate_count_after_core_flow_filter"] = len(day_rows)
        context["raw_candidate_count"] = len(day_rows)
        if day_rows:
            top = day_rows[0]
            context["top_candidate_after_core_flow"] = top["ticker"]
            context["top_score_after_core_flow"] = top["candidate_score"]
            context["top_group_key_after_core_flow"] = top["candidate_group_key"]

    scan.update(
        {
            "rule_version": RULE_VERSION,
            "base_rule_version": previous.CHANGED_VARIABLE,
            "core_flow_confirmation_required": CORE_FLOW_CONFIRMATION_REQUIRED,
            "same_ticker_core_overlap_excluded": EXCLUDE_SAME_TICKER_CORE_OVERLAP,
            "raw_candidates_before_core_flow_filter": raw_count,
            "raw_candidates_with_same_day_core_flow": same_day_count,
            "raw_candidates_with_same_ticker_core_overlap": same_ticker_overlap_count,
            "raw_candidates_missing_core_flow": missing_core_flow_count,
            "raw_candidates_excluded_same_ticker_core_overlap": (
                same_ticker_excluded_count
            ),
            "raw_candidates_after_core_flow_filter": len(filtered),
            "core_flow_confirmed_dates": len(filtered_by_date),
        }
    )
    return filtered, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_industry_volume_breadth_core_flow_confirmed"
        if gate["passed"]
        else "rejected_industry_volume_breadth_core_flow_confirmed_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    gate4 = payload["gate4"]
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted = bool(gate4["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Industry volume-breadth laggard repair may become cleaner "
                "when same-day core A/B flow confirms equity risk acceptance "
                "and same-ticker core overlap is excluded."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "production_visible_core_flow_confirmation",
            "nearby_prior_experiments": [
                "exp-20260607-014",
                "exp-20260608-007",
                "exp-20260608-008",
                "exp-20260608-009",
            ],
            "prior_trial_count": 2,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "decision": gate4["decision"],
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The core-flow confirmed industry volume-breadth source "
                "cleared Gate 4 as a replay-only/default-off lead. No "
                "production surface was promoted."
                if accepted
                else (
                    "The core-flow confirmed industry volume-breadth source "
                    "did not clear Gate 4. Do not promote it or respond by "
                    "tuning the same volume-breadth, core-flow, overlap, "
                    "top-N, hold-day, cooldown, or notional thresholds on "
                    "these frozen windows."
                )
            ),
            "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
            "negative_reflection": (
                "If rejected, the likely reason is that core-flow confirmation "
                "still leaves the volume-breadth laggard repair source too "
                "close to crowded momentum/volume chase, or it removes too "
                "many winners to keep replacement value material."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "Core-flow confirmation isolated enough risk-accepted "
                    "industry repair days to preserve the source's winners "
                    "without breaching window, drawdown, or concentration "
                    "guards."
                    if accepted
                    else (
                        "Core-flow confirmation was not sufficient to turn "
                        "industry volume-breadth laggard repair into robust "
                        "replacement value. It either thinned the sample, "
                        "kept volume-chase noise, or failed in old_thin after "
                        "costs and next-open execution."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping same-day core-flow count, "
                    "same-ticker overlap handling, group volume-breadth "
                    "thresholds, high-volume positive fraction, candidate "
                    "volume ratio, signal-day repair, lag, close-location, "
                    "hold-day, top-N, cooldown, or paper notional thresholds "
                    "on the frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT relation evidence, "
                    "such as forward default-off replacement rows, peer "
                    "taxonomy quality, supplier/customer links, borrow/option "
                    "flow, or industry earnings/revision propagation."
                ),
            },
            "next_evidence_needed": (
                "A positive replay lead still needs shared default-off helper "
                "promotion before forward observation. A rejected result "
                "requires orthogonal PIT evidence before retrying nearby "
                "volume-breadth relation variants."
            ),
            "related_files": [
                _repo_rel(SCRIPT_PATH),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
            ],
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "base_candidate_source": "industry_volume_breadth_laggard_repair_candidate_source_v1",
            "core_flow_confirmation_required": CORE_FLOW_CONFIRMATION_REQUIRED,
            "same_ticker_core_overlap_excluded": EXCLUDE_SAME_TICKER_CORE_OVERLAP,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior close history for the fixed exp-20260607-014 industry "
        "volume-breadth laggard repair source and same-day baseline core A/B "
        "entry flow from the before-result artifact. Same-ticker core overlap "
        "is excluded. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: industry volume-breadth laggard repair may "
            "need same-day core A/B flow to confirm that the market is already "
            "accepting related equity risk, while same-ticker overlap is "
            "excluded to avoid duplicating core entries."
        ),
        "2_history_check": {
            "exp-20260607-014": (
                "Rejected raw industry volume-breadth laggard repair because "
                "Gate 4 failed; this does not retune its thresholds."
            ),
            "exp-20260608-007/008": (
                "Same-day core-flow confirmation rescued industry stable "
                "leadership and then reproduced through a shared helper."
            ),
            "exp-20260608-009": (
                "Cross-helper consensus failed with thin/concentrated sample; "
                "this tests one source-specific confirmation, not helper "
                "consensus."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
            "must improve, no window may regress EV/PnL, target sample must "
            "be >=20 across all 3 windows, survival must stay >=5%, drawdown "
            "drift <=0.5pp, and concentration guard must pass. A positive "
            "replay remains only a lead until shared helper parity exists."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_010_industry_volume_breadth_core_flow_confirmation.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The source is additive "
        "default-off paper, so core signals generated/survived are unchanged "
        "from baseline."
    )
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    for field in (
        "baseline same-day core A/B entries by signal date",
        "same-day core A/B ticker for same-ticker overlap exclusion",
    ):
        if field not in runtime_fields:
            runtime_fields.append(field)
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Core-flow raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=scan.get("raw_candidates_after_core_flow_filter", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry Volume-Breadth Core-Flow Confirmation",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, "
                "run adapter, backtester adapter, production watchlist, "
                "order path, core entry, ranking, sizing, or exit behavior "
                "changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"][
                    "by_window"
                ][label]["total_pnl"],
                "core_flow_raw_candidates": payload["context_scan_by_window"][
                    label
                ].get("raw_candidates_after_core_flow_filter"),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(SCRIPT_PATH),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(SCRIPT_PATH): framework._sha256(SCRIPT_PATH),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch() -> None:
    previous.EXPERIMENT_ID = EXPERIMENT_ID
    previous.STEM = STEM
    previous.TRIAL_FAMILY = TRIAL_FAMILY
    previous.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    previous.CHANGED_VARIABLE = CHANGED_VARIABLE
    previous.RULE_VERSION = RULE_VERSION
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.MANIFEST_JSON = MANIFEST_JSON
    previous.EXPERIMENT_LOG = EXPERIMENT_LOG
    previous.REGISTRY_JSON = REGISTRY_JSON
    previous.SCRIPT_PATH = SCRIPT_PATH
    previous.PREDICTION = PREDICTION
    previous.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    previous._candidate_rows_for_window = _candidate_rows_for_window
    previous._gate4 = _gate4
    previous._build_payload = _build_payload
    previous._build_card = _build_card
    previous._build_log_record = _build_log_record
    previous._write_manifest = _write_manifest


def main() -> None:
    _patch()
    previous.main()


if __name__ == "__main__":
    main()
