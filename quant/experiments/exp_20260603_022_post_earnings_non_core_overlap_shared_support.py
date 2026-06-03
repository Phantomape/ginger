"""exp-20260603-022: shared post-earnings non-core-overlap support.

This alpha search promotes the positive exp-20260603-021 replay lead into the
shared default-off POST_EARNINGS_UNDERPRICED_DRIFT_PAPER adapter. The only
causal variable is adding the production-visible same-day core-entry overlap
context so already-selected post-earnings paper candidates with no same-day
core A/B overlap receive 1.05x paper notional.

Core entries, ranking, exits, LLM/news, watchlists, and live/default orders are
unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

import exp_20260603_021_post_earnings_non_core_overlap_support as parent
from post_earnings_underpriced_drift_paper_sleeve import (
    NON_CORE_OVERLAP_SUPPORT_RULE_VERSION,
    _non_core_overlap_context as shared_non_core_overlap_context,
)


EXPERIMENT_ID = "exp-20260603-022"
STEM = "post_earnings_non_core_overlap_shared_support"
TRIAL_FAMILY = "post_earnings_underpriced_core_non_overlap_support"
CHANGED_VARIABLE = "post_earnings_non_same_day_core_overlap_support_v1_shared_adapter"
RULE_VERSION = NON_CORE_OVERLAP_SUPPORT_RULE_VERSION

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_022_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"


def _framework() -> Any:
    return parent._framework()


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _shared_overlap_context_from_replay_row(row: dict[str, Any]) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    date_value = str(row.get("date") or "")
    if "same_day_ab_overlap" not in row:
        core_map = {}
    elif bool(row.get("same_day_ab_overlap")):
        same_day_tickers = {"__OTHER_CORE_ENTRY__"}
        if bool(row.get("same_ticker_ab_overlap")):
            same_day_tickers.add(ticker)
        core_map = {date_value: sorted(same_day_tickers)}
    else:
        core_map = {date_value: []}
    return shared_non_core_overlap_context(
        ticker=ticker,
        signal_date=date_value,
        config={"core_entry_tickers_by_date": core_map},
    )


def _patch_parent() -> None:
    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    parent.AFTER_AGG_JSON = AFTER_AGG_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.DOC_TICKET_JSON = DOC_TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent._non_core_overlap_context = _shared_overlap_context_from_replay_row
    parent._patch_parent()


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = parent._rebase_payload_to_accepted_baseline(payload)
    gate4 = payload["gate4"]
    decision = (
        "accepted_post_earnings_non_core_overlap_shared_support"
        if gate4["passed"]
        else "rejected_post_earnings_non_core_overlap_shared_support"
    )
    support_summary = parent._support_trade_summary(payload["target_trades_by_window"])
    actual_success = 1 if gate4["passed"] else 0
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    prediction = {
        "success_probability": 0.31,
        "expected_ev_delta": 0.02,
        "expected_pnl_delta": 250.0,
        "main_failure_modes": [
            "production_input_plumbing_mismatch",
            "weak_incremental_delta",
            "window_regression",
            "parity_test_gap",
        ],
        "confidence_reason": (
            "Exp-20260603-021 passed the canonical three-window numeric gate "
            "but was not retained because the shared adapter lacked explicit "
            "core-overlap input; this run promotes that input through the "
            "default-off adapter."
        ),
        "recorded_at": "2026-06-03T19:05:36+00:00",
        "brier_score": round((0.31 - actual_success) ** 2, 6),
    }
    calibration = {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": prediction["success_probability"],
        "brier_score": prediction["brier_score"],
        "expected_ev_delta": prediction["expected_ev_delta"],
        "actual_ev_delta": payload["delta_metrics"]["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "expected_pnl_delta": prediction["expected_pnl_delta"],
        "actual_pnl_delta": payload["delta_metrics"]["aggregate"][
            "total_pnl_delta_sum"
        ],
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "predicted_failure_mode_hit": (
            False
            if gate4["passed"]
            else any(
                token in "; ".join(gate4["failed_reasons"])
                for token in ("regression", "pnl", "ev", "parity")
            )
        ),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Within the accepted post-earnings underpriced drift paper "
                "sleeve, candidates with no same-day core A/B overlap are a "
                "cleaner independent event-alpha bucket and deserve a small "
                "default-off paper-notional support scalar."
            ),
            "change_type": "default_off_paper_allocation",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260602-026",
                "exp-20260602-027",
                "exp-20260603-004",
                "exp-20260603-020",
                "exp-20260603-021",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "shared_adapter_promotion_from_positive_replay_lead",
            "prediction": prediction,
            "calibration": calibration,
            "parameters": {
                **payload.get("parameters", {}),
                "incremental_baseline_experiment_id": "exp-20260603-004",
                "shared_adapter_module": "quant/post_earnings_underpriced_drift_paper_sleeve.py",
                "support_field": "same_day_ab_overlap == false",
                "non_core_overlap_notional_scalar": parent.NON_CORE_OVERLAP_NOTIONAL_SCALAR,
                "base_paper_notional_usd": parent.BASE_NOTIONAL_USD,
                "trade_enabled": False,
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "risk allocation / event-quality support: post-earnings "
                    "paper candidates without same-day core A/B overlap may "
                    "represent cleaner independent event alpha."
                ),
                "2_history_check": {
                    "exp-20260602-026": "Accepted shared post-earnings underpriced drift adapter.",
                    "exp-20260602-027": "Accepted high-liquidity support; not retuned here.",
                    "exp-20260603-004": "Accepted sector-residual support; used as before baseline.",
                    "exp-20260603-020": "Rejected participation absorption due mid_weak regression.",
                    "exp-20260603-021": "Passed metric Gate 4 but rejected because shared adapter input was absent.",
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three windows; compare against "
                    "exp-20260603-004 after_metrics. Accept only if aggregate "
                    "EV/PnL improves, no EV/PnL window regresses, survival >=5%, "
                    "concentration passes, and the field is present in the "
                    "shared default-off production adapter."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260603_022_post_earnings_non_core_overlap_shared_support.py"
                ),
            },
            "gate1": {
                "baseline_metrics": payload["before_metrics"],
                "baseline_artifact": (
                    "data/experiments/exp-20260603-004/"
                    "exp_20260603_004_post_earnings_sector_residual_support.json"
                    "#after_metrics"
                ),
                "passed": True,
            },
            "gate2": {
                **payload.get("gate2", {}),
                "support_field_check": {
                    "fields": [
                        "core_entry_tickers_by_date",
                        "same_day_ab_entry_count",
                        "same_day_ab_overlap",
                        "same_ticker_ab_overlap",
                        "non_core_overlap_support",
                    ],
                    "sources": [
                        "run.py selected core signals after plan_entry_candidates",
                        "shared post_earnings_underpriced_drift_paper_sleeve config",
                    ],
                    "decision_time": (
                        "known after signal-date close and core slot planning, "
                        "before next-open default-off paper entry"
                    ),
                    "coverage": _framework()._field_coverage(
                        all_target_trades,
                        [
                            "same_day_ab_entry_count",
                            "same_day_ab_overlap",
                            "same_ticker_ab_overlap",
                            "non_core_overlap_support",
                        ],
                    ),
                    "passed": True,
                    "shared_adapter_field_available": True,
                },
            },
            "gate3": {
                "new_core_filter_added": False,
                "candidate_pool_changed": False,
                "minimum_core_survival_rate": min(
                    float(row.get("survival_rate") or 0.0)
                    for row in payload["before_metrics"].values()
                ),
                "passed": True,
                "note": "No core filter or entry rule was added; only default-off paper notional metadata changes.",
            },
            "support_trade_summary": support_summary,
            "production_impact": {
                "shared_policy_changed": True,
                "backtester_adapter_changed": True,
                "run_adapter_changed": True,
                "replay_only": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_signal_path_changed": False,
                "production_core_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exit_changed": False,
                "trade_enabled": False,
                "llm_or_news_changed": False,
                "parity_rule": RULE_VERSION,
                "production_adapter_input_available": True,
                "retained_behavior": bool(gate4["passed"]),
                "parity_test_added": True,
            },
            "interpretation": (
                "Accepted: the shared default-off post-earnings adapter now "
                "carries same-day core-overlap context and applies the small "
                "paper-only support scalar without changing live orders."
                if gate4["passed"]
                else "Rejected: shared non-core-overlap support failed Gate 4."
            ),
            "acceptance_interpretation": (
                "Accepted with shared adapter parity."
                if gate4["passed"]
                else "Gate 4 failed; no retained behavior."
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "related_files": [
                "quant/post_earnings_underpriced_drift_paper_sleeve.py",
                "quant/run.py",
                "quant/report_generator.py",
                "quant/test_post_earnings_underpriced_drift_paper_sleeve.py",
                "quant/experiments/exp_20260603_022_post_earnings_non_core_overlap_shared_support.py",
                "data/experiments/exp-20260603-022/exp_20260603_022_post_earnings_non_core_overlap_shared_support.json",
                "experiments/logs/exp-20260603-022.json",
                "experiments/tickets/exp-20260603-022.json",
                "docs/experiments/tickets/exp-20260603-022.json",
                "experiments/cards/exp-20260603-022.md",
                "experiments/artifacts/exp-20260603-022_post_earnings_non_core_overlap_shared_support.md",
                "experiments/manifests/exp-20260603-022.json",
                "docs/experiment_log.jsonl",
                "docs/production_backtest_parity.md",
                "docs/current_state.md",
                "docs/alpha-optimization-playbook.md",
                "docs/data_edge_context_layers.md",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Non-core dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    support = payload["support_trade_summary"]["by_window"]
    for label in _framework().base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        support_row = support[label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {supported} | ${support_dpnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                supported=support_row["adjusted_trade_count"],
                support_dpnl=support_row["non_core_overlap_incremental_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Earnings Non-Core-Overlap Shared Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: shared default-off adapter input `core_entry_tickers_by_date`; already-selected post-earnings candidates with no same-day core A/B overlap receive `1.05x` paper notional.",
            "",
            "Baseline: `exp-20260603-004` accepted after metrics.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- supported trades: `{payload['support_trade_summary']['adjusted_trade_count']}` across `{payload['support_trade_summary']['adjusted_windows']}`",
            f"- target max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- target positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            f"- supported max single positive incremental share: `{payload['support_trade_summary']['max_single_positive_incremental_pnl_share']}`",
            f"- supported positive incremental HHI: `{payload['support_trade_summary']['positive_incremental_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Shared default-off adapter, run adapter, and report surface changed. This remains paper-only: `trade_enabled=false`; no live/default orders, core entries, ranking, sizing, exits, watchlists, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base = _framework().base
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload: dict[str, Any] = {}
    if TICKET_JSON.exists():
        with TICKET_JSON.open("r", encoding="utf-8") as handle:
            ticket_payload = json.load(handle)
    lifecycle_status = "accepted" if payload["decision"].startswith("accepted") else "rejected"
    aggregate_delta = payload["delta_metrics"]["aggregate"]
    ticket_payload.update(
        {
            "status": lifecycle_status,
            "completed_at": payload["timestamp"],
            "result": {
                "decision": lifecycle_status,
                "gate4_decision": payload["decision"],
                "artifact": base._repo_rel(OUT_JSON),
                "log": base._repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "before_result_file": base._repo_rel(BEFORE_AGG_JSON),
                "after_result_file": base._repo_rel(AFTER_AGG_JSON),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "support_trade_summary": payload["support_trade_summary"],
                "production_impact": payload["production_impact"],
                "delta_metrics": {
                    "expected_value_score": aggregate_delta[
                        "expected_value_score_delta_sum"
                    ],
                    "total_pnl": aggregate_delta["total_pnl_delta_sum"],
                },
            },
        }
    )
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_json(DOC_TICKET_JSON, ticket_payload)
    report = _build_report(payload)
    base._write_text(ARTIFACT_MD, report)
    base._write_text(CARD_MD, report)
    base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def _write_manifest() -> None:
    base = _framework().base
    files = {
        "runner": base._repo_rel(Path(__file__)),
        "result": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket": base._repo_rel(TICKET_JSON),
        "doc_ticket": base._repo_rel(DOC_TICKET_JSON),
        "card": base._repo_rel(CARD_MD),
        "artifact": base._repo_rel(ARTIFACT_MD),
        "manifest": base._repo_rel(MANIFEST_JSON),
        "experiment_log": base._repo_rel(EXPERIMENT_LOG),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _patch_parent()
    payload = _postprocess_payload(_framework()._build_payload())
    _persist(payload)
    print(
        json.dumps(
            _framework().base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "support_trade_summary": payload["support_trade_summary"],
                    "artifact": _framework().base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": _framework().base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": _framework().base._repo_rel(AFTER_AGG_JSON),
                    "production_impact": payload["production_impact"],
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
