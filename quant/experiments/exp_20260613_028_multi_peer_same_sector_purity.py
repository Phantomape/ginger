"""exp-20260613-028: multi-peer correlation-cluster same-sector purity.

Replay-only alpha search on one relation-quality discriminator. The prior
multi-peer correlation-cluster source (exp-20260609-014) improved late/mid but
failed old_thin drawdown. This run keeps that source fixed and admits only
candidate rows whose strongest supporting peers are mostly same-sector.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import exp_20260609_014_multi_peer_correlation_cluster_shock as base


framework = base.framework

SCRIPTS_DIR = framework.REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD
BASE_GATE4 = base.BASE_GATE4

EXPERIMENT_ID = "exp-20260613-028"
STEM = "multi_peer_same_sector_purity"
TRIAL_FAMILY = "multi_peer_correlation_cluster_edge_purity_candidate_pool"
TRIAL_VARIANT_ID = "same_sector_purity_top1_next_open_10d_v1"
CHANGED_VARIABLE = "multi_peer_correlation_cluster_same_sector_purity_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_028_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

MIN_SAME_SECTOR_TOP_SUPPORT = 3
MIN_SAME_SECTOR_TOP_SUPPORT_SHARE = 0.50

ROLLING_CORR_COMPARATOR = base.ROLLING_CORR_COMPARATOR

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.45,
    "expected_pnl_delta": 4500.0,
    "main_failure_modes": [
        "old_thin_tail_not_removed",
        "accepted_peer_shock_not_beaten",
        "sample_thinning",
        "window_regression",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "exp-20260609-014 had positive aggregate EV/PnL in late and mid but "
        "failed old_thin drawdown. Same-sector purity is a materially different "
        "edge-quality discriminator rather than a corr/support/top-N retune."
    ),
    "recorded_at": "2026-06-13T20:09:18+00:00",
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
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter computing the same multi-peer "
        "correlation-cluster candidates and the same same-sector top-support "
        "purity gate in both historical replay and daily production before any "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _passes_same_sector_purity(row: dict[str, Any]) -> bool:
    top_support = int(row.get("supporting_peer_count") or 0)
    same_sector = int(row.get("same_sector_supporting_peer_count") or 0)
    if top_support <= 0:
        return False
    return (
        same_sector >= MIN_SAME_SECTOR_TOP_SUPPORT
        and same_sector / top_support >= MIN_SAME_SECTOR_TOP_SUPPORT_SHARE
    )


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, day_contexts, scan = base._candidate_rows_for_window(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    filtered: list[dict[str, Any]] = []
    rejected = 0
    for row in candidates:
        top_support = int(row.get("supporting_peer_count") or 0)
        same_sector = int(row.get("same_sector_supporting_peer_count") or 0)
        share = same_sector / top_support if top_support else 0.0
        if not _passes_same_sector_purity(row):
            rejected += 1
            continue
        updated = dict(row)
        updated["source"] = "MULTI_PEER_SAME_SECTOR_PURITY_PAPER"
        updated["rule_version"] = RULE_VERSION
        updated["edge_purity_top_support_share"] = round(share, 6)
        updated["min_same_sector_top_support"] = MIN_SAME_SECTOR_TOP_SUPPORT
        updated["min_same_sector_top_support_share"] = (
            MIN_SAME_SECTOR_TOP_SUPPORT_SHARE
        )
        filtered.append(updated)

    filtered.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["same_sector_supporting_peer_count"]),
            -float(row["edge_purity_top_support_share"]),
            -float(row["supporting_peer_count"]),
            -float(row["avg_peer_corr_60d"]),
            row["ticker"],
        )
    )
    days_with_filtered = len({str(row["date"]) for row in filtered})
    scan.update(
        {
            "edge_purity_rule_version": RULE_VERSION,
            "min_same_sector_top_support": MIN_SAME_SECTOR_TOP_SUPPORT,
            "min_same_sector_top_support_share": MIN_SAME_SECTOR_TOP_SUPPORT_SHARE,
            "raw_supported_candidate_rows_before_purity": len(candidates),
            "purity_passed_candidate_rows": len(filtered),
            "purity_rejected_candidate_rows": rejected,
            "days_with_same_sector_purity_candidates": days_with_filtered,
        }
    )
    filtered_contexts = []
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in filtered:
        by_date.setdefault(str(row["date"]), []).append(row)
    for day, rows in sorted(by_date.items()):
        top = rows[0]
        filtered_contexts.append(
            {
                "date": day,
                "same_sector_purity_candidate_count": len(rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_same_sector_support": top["same_sector_supporting_peer_count"],
                "top_edge_purity_share": top["edge_purity_top_support_share"],
                "top_avg_peer_corr_60d": top["avg_peer_corr_60d"],
            }
        )
    return filtered, filtered_contexts, scan


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
    if aggregate["expected_value_score_delta_sum"] <= ROLLING_CORR_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append(
            "accepted_peer_shock_ev_not_beaten"
        )
    if aggregate["total_pnl_delta_sum"] <= ROLLING_CORR_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append(
            "accepted_peer_shock_pnl_not_beaten"
        )
    gate["rolling_corr_peer_shock_comparator"] = ROLLING_CORR_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_multi_peer_same_sector_purity"
        if gate["passed"]
        else "rejected_multi_peer_same_sector_purity_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "candidate_pool: if the old_thin failure in exp-20260609-014 "
                "came from cross-industry beta propagation, requiring at least "
                "three of the top six supporting peers and at least half of top "
                "support to be same-sector should preserve relation information "
                "while removing noisy laggards."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_high_order_relation_alpha",
            "new_evidence_type": "production_visible_free_ohlcv_relation_edge_purity",
            "nearby_prior_experiments": [
                "exp-20260606-025",
                "exp-20260609-014",
                "exp-20260612-014",
                "exp-20260610-022",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "rolling_corr_peer_shock_comparator": ROLLING_CORR_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, same-sector purity did not fix the multi-peer "
                "cluster failure; the edge is probably broad momentum/correlation "
                "exposure or the same-sector gate thinned useful winners. Do not "
                "answer by sweeping corr/support/top-N/hold/notional on frozen "
                "windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT relation provenance, such as "
                "customer/supplier links, named counterparty evidence, or forward "
                "replacement-value rows versus accepted relation comparators."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_same_sector_top_support": MIN_SAME_SECTOR_TOP_SUPPORT,
            "min_same_sector_top_support_share": MIN_SAME_SECTOR_TOP_SUPPORT_SHARE,
            "base_candidate_source": "multi_peer_correlation_cluster_shock_candidate_source_v1",
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool: same-sector support purity should improve the "
            "multi-peer cluster source by keeping relation-linked laggards while "
            "filtering cross-industry beta propagation."
        ),
        "2_history_check": {
            "exp-20260606-025": (
                "Accepted rolling-correlation peer shock is the comparator."
            ),
            "exp-20260609-014": (
                "Multi-peer cluster improved late/mid but failed old_thin "
                "drawdown and was rejected."
            ),
            "exp-20260612-014": (
                "Dynamic cluster breadth leadership regressed all windows; this "
                "tests edge purity on laggard transfer, not breadth leadership."
            ),
            "exp-20260610-022": (
                "Lead-lag peer underreaction failed; this uses same-day relation "
                "support with a sector-purity gate."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md canonical three windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target sample "
            ">=20 across all three windows, survival >=5%, drawdown drift <=0.5pp, "
            "concentration guard passes, and accepted rolling-corr peer-shock "
            "comparator is beaten."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260613_028_multi_peer_same_sector_purity.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "positive_replay_lead_not_promoted" if passed else "rejected"
    payload["interpretation"] = (
        "Same-sector edge purity cleared Gate 4 and beat the accepted peer-shock "
        "comparator, but remains replay-only until a shared default-off adapter "
        "reproduces historical replay and daily snapshot behavior."
        if passed
        else (
            "Same-sector edge purity did not clear Gate 4 or did not beat the "
            "accepted rolling-correlation peer-shock comparator; do not promote "
            "or keep tuning this high-order correlation family on frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The purity gate tested whether exp-20260609-014's old_thin loss was "
            "mostly cross-industry crosstalk. If it failed, same-sector support "
            "still did not isolate a durable relation edge after next-open "
            "execution and costs."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping min corr, support count, same-sector share, "
            "top-N, hold-day, cooldown, or notional thresholds on these frozen "
            "windows."
        ),
        "new_evidence_required": (
            "Need named economic relation provenance or forward displacement rows "
            "before revisiting multi-peer correlation-cluster alpha."
        ),
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Purity days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {purity_days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                purity_days=scan.get("days_with_same_sector_purity_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Multi-Peer Same-Sector Purity",
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
            "- Accepted peer-shock comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                ROLLING_CORR_COMPARATOR["expected_value_score_delta_sum"],
                ROLLING_CORR_COMPARATOR["total_pnl_delta_sum"],
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
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_high_order_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "rolling_corr_peer_shock_comparator": ROLLING_CORR_COMPARATOR,
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
                "same_sector_purity_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_same_sector_purity_candidates"),
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


def _update_ticket_and_registry(
    payload: dict[str, Any], log_record: dict[str, Any]
) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "calibration": payload["calibration"],
        "gate4": payload["gate4"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record[
            "aggregate_expected_value_delta"
        ],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    script_path = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(script_path),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(script_path): framework._sha256(script_path),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


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
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
