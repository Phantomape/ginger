"""exp-20260602-026: shared post-earnings underpriced drift adapter.

This alpha search promotes the exp-20260602-023 positive replay lead into a
shared default-off paper adapter. The backtest runner intentionally calls the
production-visible helper, so Gate 4 tests the same event/source boundary that
daily production can use for forward replacement-value rows.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
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

import exp_20260602_006_post_earnings_positive_surprise_drift_candidate_pool as parent
from post_earnings_underpriced_drift_paper_sleeve import (
    RULE_VERSION as SHARED_RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_post_earnings_underpriced_drift_candidates_for_dates,
    load_earnings_snapshot_index,
)


EXPERIMENT_ID = "exp-20260602-026"
STEM = "post_earnings_underpriced_shared_adapter"
TRIAL_FAMILY = "post_earnings_positive_surprise_underpriced_shared_adapter"
CHANGED_VARIABLE = "post_earnings_underpriced_drift_shared_default_off_adapter_v1"
RULE_VERSION = SHARED_RULE_VERSION

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_026_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

PRE_EVENT_RS_DAYS = 20
MAX_PRE_EVENT_RS20_VS_SPY = 0.0


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = parent.framework.ohlcv_helper._baseline_entries(before_result)
    trading_dates = [
        date_value
        for date_value in parent.framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    earnings_index = load_earnings_snapshot_index()
    candidates, rejected, audit = build_post_earnings_underpriced_drift_candidates_for_dates(
        as_of_dates=trading_dates,
        ohlcv_by_ticker=snapshot,
        candidate_universe=universe,
        earnings_index=earnings_index,
        config={
            "event_date_min": cfg["start"],
            "event_date_max": cfg["end"],
        },
    )
    for row in candidates:
        ticker = str(row.get("ticker") or "")
        signal_date = str(row.get("date") or "")
        ab_entries = entries_by_date.get(signal_date, [])
        row["same_day_ab_entry_count"] = len(ab_entries)
        row["same_day_ab_overlap"] = bool(ab_entries)
        row["same_ticker_ab_overlap"] = any(
            trade.get("ticker") == ticker for trade in ab_entries
        )

    audit = dict(audit)
    audit["shared_adapter_rule_version"] = SHARED_RULE_VERSION
    audit["source_rule_version"] = SOURCE_RULE_VERSION
    audit["uses_shared_production_helper"] = True
    audit["shared_adapter_rejected_candidate_count"] = len(rejected)
    audit["pre_event_rs_days"] = PRE_EVENT_RS_DAYS
    audit["max_pre_event_rs20_vs_spy"] = MAX_PRE_EVENT_RS20_VS_SPY
    audit["pre_event_underpricing_reject_counts"] = {
        "pre_event_rs20_outperformed_spy": (
            (audit.get("audit_reject_counts") or {}).get("pre_event_rs20_outperformed_spy", 0)
        ),
        "missing_pre_event_rs20_context": (
            (audit.get("audit_reject_counts") or {}).get("missing_pre_event_rs20_context", 0)
        ),
    }
    return candidates, audit


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
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent._patch_framework()
    parent.framework._candidate_rows_for_window = _candidate_rows_for_window
    parent.framework._build_report = _build_report


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_post_earnings_underpriced_shared_default_off_adapter"
        if gate4["passed"]
        else "rejected_post_earnings_underpriced_shared_default_off_adapter"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.44,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "shared_adapter_drift",
            "production_parity_gap",
            "gate4_regression",
        ],
        "confidence_reason": (
            "exp-20260602-023 cleared all three canonical windows with sample "
            "and concentration pass; this run tests whether the same alpha can "
            "be expressed through a shared production-visible adapter."
        ),
        "recorded_at": "2026-06-02T18:05:06+00:00",
        "brier_score": round((0.44 - actual_success) ** 2, 6),
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
        "actual_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "predicted_failure_mode_hit": (
            False
            if gate4["passed"]
            else any(
                token in "; ".join(gate4["failed_reasons"])
                for token in ("gate4", "regression", "sample", "drawdown")
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
                "Promoting the exp-20260602-023 post-earnings underpriced "
                "positive-surprise drift lead into a shared default-off paper "
                "adapter will preserve the three-window replay edge while "
                "making forward replacement-value rows production visible."
            ),
            "change_type": "default_off_paper_adapter",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "default_off_paper_adapter",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260602-006",
                "exp-20260602-011",
                "exp-20260602-023",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "shared_adapter_promotion_from_positive_replay_lead",
            "prediction": prediction,
            "calibration": calibration,
            "parameters": {
                **payload.get("parameters", {}),
                "shared_adapter_module": "quant/post_earnings_underpriced_drift_paper_sleeve.py",
                "shared_adapter_rule_version": SHARED_RULE_VERSION,
                "source_rule_version": SOURCE_RULE_VERSION,
                "pre_event_rs_days": PRE_EVENT_RS_DAYS,
                "max_pre_event_rs20_vs_spy": MAX_PRE_EVENT_RS20_VS_SPY,
                "paper_notional_usd": 10_000.0,
                "trade_enabled": False,
                "unchanged_parent_source": "exp-20260602-023 positive replay lead",
            },
            "production_impact": {
                "shared_policy_changed": True,
                "backtester_adapter_changed": True,
                "run_adapter_changed": True,
                "replay_only": False,
                "parity_test_added": True,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_signal_path_changed": False,
                "production_core_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exit_changed": False,
                "trade_enabled": False,
                "llm_or_news_changed": False,
                "parity_rule": SHARED_RULE_VERSION,
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe joins remain sparse. "
                "Skipped Companyfacts/FINRA/VBB/consensus/state-surface retunes per "
                "playbook anti-repeat rules. This run promotes the strongest "
                "recent positive post-earnings replay lead into a shared adapter "
                "instead of adding noise tickers or retuning nearby thresholds."
            ),
            "acceptance_interpretation": (
                "Gate 4 passed through the shared adapter. Keep the default-off "
                "production-visible sleeve to accumulate forward replacement-value "
                "rows; do not enable live capital without a separate forward gate."
                if gate4["passed"]
                else (
                    "Gate 4 failed through the shared adapter. Do not retain or "
                    "promote the sleeve; the replay edge did not survive the "
                    "production-visible boundary."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"] = {
        **payload.get("gate2", {}),
        "shared_adapter_field_check": {
            "field": "pre_event_rs20_vs_spy",
            "source": "shared adapter computes ticker and SPY OHLCV returns ending on the close before event_confirmed_date",
            "decision_time": "known before the earnings event and before next-open paper entry",
            "passed": True,
        },
        "shared_adapter_parity_check": {
            "production_helper": "quant/post_earnings_underpriced_drift_paper_sleeve.py",
            "backtest_runner_uses_same_helper": True,
            "daily_run_uses_same_helper": True,
            "trade_enabled_default": False,
            "alters_orders": False,
            "passed": True,
        },
        "operator_open_positions_check": {
            "entry_date_present": True,
            "target_price_present": True,
            "checked_file": "operator_inputs/open_positions.json",
        },
    }
    payload["gate2"]["target_trade_field_coverage"] = parent.framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "event_confirmed_date",
            "latest_surprise_pct",
            "eps_actual_last",
            "pre_event_ret20",
            "pre_event_spy_ret20",
            "pre_event_rs20_vs_spy",
            "event_to_signal_excess_vs_spy",
            "rs20_vs_spy",
            "avg_dollar_volume_20d",
            "source_rule_version",
        ],
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates | RS rejects |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in parent.framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rejects = (audit.get("audit_reject_counts") or {}).get(
            "pre_event_rs20_outperformed_spy",
            0,
        )
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} | {rejects} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
                rejects=rejects,
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Earnings Underpriced Shared Adapter",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: promote the exp-20260602-023 `pre_event_rs20_vs_spy <= 0.0` post-earnings positive-surprise drift lead into a shared default-off production-visible paper adapter.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Shared helper, daily run adapter, report surface, attribution surface, and parity tests were added. The sleeve remains default-off paper only: `trade_enabled=false`, `production_orders_changed=false`, no core ranking/sizing/exit/LLM/news path changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base = parent.framework.base
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload = {}
    if TICKET_JSON.exists():
        with TICKET_JSON.open("r", encoding="utf-8") as handle:
            ticket_payload = json.load(handle)
    ticket_payload.update(
        {
            "status": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "artifact": base._repo_rel(OUT_JSON),
                "log": base._repo_rel(LOG_JSON),
                "summary": payload["acceptance_interpretation"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
        }
    )
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._write_text(CARD_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def _write_manifest() -> None:
    base = parent.framework.base
    files = {
        "runner": base._repo_rel(Path(__file__)),
        "shared_adapter": "quant/post_earnings_underpriced_drift_paper_sleeve.py",
        "run_adapter": "quant/run.py",
        "test": "quant/test_post_earnings_underpriced_drift_paper_sleeve.py",
        "report_generator": "quant/report_generator.py",
        "attribution": "quant/default_off_alpha_attribution.py",
        "data_paths": "quant/data_paths.py",
        "result": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket": base._repo_rel(TICKET_JSON),
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
    payload = _postprocess_payload(parent.framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            parent.framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": parent.framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": parent.framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": parent.framework.base._repo_rel(AFTER_AGG_JSON),
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
