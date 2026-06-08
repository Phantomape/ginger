"""exp-20260608-020: core-flow confirmed compression breakout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable on top of the accepted narrow-range compression
breakout source: admit compression breakout candidates only when the signal
date already has core A/B entry flow, while excluding same-ticker core overlap
so the paper row tests independent replacement value.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import exp_20260608_012_narrow_range_compression_breakout as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260608-020"
STEM = "compression_core_flow_confirmation"
TRIAL_FAMILY = "narrow_range_compression_core_flow_confirmation"
TRIAL_VARIANT_ID = "compression_core_flow_nonoverlap_top1_10d_v1"
CHANGED_VARIABLE = "narrow_range_compression_core_flow_confirmed_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CORE_FLOW_CONFIRMATION_REQUIRED = True
EXCLUDE_SAME_TICKER_CORE_OVERLAP = True

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "core_flow_filter_removes_winners",
        "window_regression",
        "drawdown_drift",
        "compression_edge_not_conditioned_on_core_flow",
    ],
    "confidence_reason": (
        "exp-20260608-012/013 accepted the narrow-range compression breakout "
        "source and shared helper. exp-20260608-007/008 showed same-day "
        "core-flow confirmation can rescue a relation source. Risk is that "
        "the overlay thins the 44-trade compression sample or simply selects "
        "dates where the core stack already captured the edge."
    ),
    "recorded_at": "2026-06-08T17:06:31+00:00",
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
    "parity_note": (
        "This experiment changes no production code. A positive result is a "
        "replay lead only unless a shared default-off adapter exposes the same "
        "compression source, same-day core A/B flow confirmation, same-ticker "
        "core-overlap exclusion, next-open paper entry, 10-trading-day exit, "
        "costs, cooldown, and concentration controls in both replay and daily "
        "production."
    ),
}

BASE_CANDIDATE_ROWS_FOR_WINDOW = previous._candidate_rows_for_window
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
            context["top_range_expansion_after_core_flow"] = top[
                "candidate_range_expansion_ratio"
            ]

    scan.update(
        {
            "rule_version": RULE_VERSION,
            "base_rule_version": previous.RULE_VERSION,
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
    gate = previous._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_compression_core_flow_confirmed"
        if gate["passed"]
        else "rejected_compression_core_flow_confirmed_candidate_pool"
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
                "Narrow-range compression breakout candidates may be cleaner "
                "when same-day core A/B entry flow confirms actionable equity "
                "risk and same-ticker core overlap is excluded."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": "production_visible_core_flow_confirmation",
            "nearby_prior_experiments": [
                "exp-20260608-012",
                "exp-20260608-013",
                "exp-20260608-007",
                "exp-20260608-008",
                "exp-20260608-016",
                "exp-20260608-017",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "decision": gate4["decision"],
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The compression core-flow source cleared Gate 4 as a "
                "replay-only/default-off lead. No production surface was "
                "promoted, so there is no production/backtest mismatch."
                if accepted
                else (
                    "The compression core-flow source did not clear Gate 4. "
                    "Do not promote it or respond by tuning compression, "
                    "core-flow, top-N, hold-day, cooldown, or notional on the "
                    "frozen windows."
                )
            ),
            "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
            "negative_reflection": (
                "If rejected, the likely reason is that same-day core flow "
                "thins the accepted compression source too far, removes "
                "independent winners, or confirms dates where the core stack "
                "already captured the cleanest opportunity."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "Core-flow confirmation preserved enough compression "
                    "breakout rows to improve all canonical windows while "
                    "excluding same-ticker core overlap. This remains a "
                    "replay lead only because the shared compression helper "
                    "does not yet expose the core-flow overlay."
                    if accepted
                    else (
                        "Core-flow confirmation was not a sufficient "
                        "incremental discriminator for narrow-range "
                        "compression breakouts. It likely removed useful "
                        "independent candidates or selected risk-on dates "
                        "where the accepted core stack already owned the "
                        "highest-quality edge."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping same-day core-flow requirements, "
                    "same-ticker overlap handling, compression lookback, "
                    "range-expansion ratio, volume, close-location, ret5/ret20, "
                    "top-N, hold-day, cooldown, or paper notional thresholds "
                    "on these frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT catalyst/flow "
                    "provenance, closed forward replacement-value rows, or a "
                    "shared-helper implementation that reproduces a positive "
                    "lead without production/backtest drift."
                ),
            },
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter path and parity tests before forward observation. "
                "Live activation would require closed forward replacement "
                "rows and a separate activation-envelope Gate 1-4."
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
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
            "base_candidate_source": previous.CHANGED_VARIABLE,
            "core_flow_confirmation_required": CORE_FLOW_CONFIRMATION_REQUIRED,
            "same_ticker_core_overlap_excluded": EXCLUDE_SAME_TICKER_CORE_OVERLAP,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior close history for the accepted compression breakout source and "
        "same-day baseline core A/B entry flow from the before-result artifact. "
        "Same-ticker core overlap is excluded. Paper entry is next available "
        "open with existing entry slippage; exit is the close 10 trading days "
        "after the signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: compression-to-expansion with volume and a "
            "high close may be cleaner when same-day core A/B flow confirms "
            "the market is already accepting stock risk, while same-ticker "
            "core overlap is excluded to avoid duplicating core entries."
        ),
        "2_history_check": {
            "exp-20260608-012/013": (
                "Accepted compression breakout replay/shared helper: aggregate "
                "EV +0.1608, PnL +$2,248.98, 44 target trades, all windows "
                "improved, no drawdown worsening."
            ),
            "exp-20260608-007/008": (
                "Core-flow confirmation helped an industry relation source "
                "reproduce as a shared default-off adapter."
            ),
            "exp-20260608-016/017": (
                "Nearby accumulation-base and quiet-absorption OHLCV variants "
                "were rejected; this run does not retune those thresholds."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
            "must improve, no window may regress EV/PnL, target sample must be "
            ">=20 across all 3 windows, survival must stay >=5%, drawdown drift "
            "<=0.5pp, and concentration guard must pass. A positive replay "
            "still requires shared adapter parity before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_020_compression_core_flow_confirmation.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
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
            f"# {EXPERIMENT_ID} Compression Core-Flow Confirmation",
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
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
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
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
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
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
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


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(framework._safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4


def main() -> None:
    _patch_framework()
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
