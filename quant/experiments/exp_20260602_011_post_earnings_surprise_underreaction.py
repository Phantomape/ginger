"""exp-20260602-011: post-earnings surprise underreaction scout.

This alpha scout narrows the rejected exp-20260602-006 positive-surprise
candidate source with one production-visible price-reaction field:
signal-day close location must be <= 0.70. The hypothesis is that confirmed
positive EPS surprises that have not already closed near the intraday high
represent cleaner underreaction drift than high-close/euphoria rows.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260602_006_post_earnings_positive_surprise_drift_candidate_pool as parent


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-011"
STEM = "post_earnings_surprise_underreaction"
TRIAL_FAMILY = "post_earnings_positive_surprise_underreaction_candidate_pool"
CHANGED_VARIABLE = "post_earnings_positive_surprise_underreaction_close_location_cap_v1"
RULE_VERSION = "post_earnings_positive_surprise_underreaction_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_011_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

MAX_UNDERREACTION_CLOSE_LOCATION = 0.70


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = parent._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    before_count = len(candidates)
    before_days = len({row["date"] for row in candidates})
    reject_counter: Counter[str] = Counter()
    kept: list[dict[str, Any]] = []
    for row in candidates:
        close_location = row.get("close_location")
        if close_location is None:
            reject_counter["missing_close_location"] += 1
            continue
        if float(close_location) > MAX_UNDERREACTION_CLOSE_LOCATION:
            reject_counter["above_underreaction_close_location_cap"] += 1
            continue
        row = dict(row)
        row["post_earnings_underreaction_close_location_cap"] = MAX_UNDERREACTION_CLOSE_LOCATION
        row["underreaction_close_location_pass"] = True
        row["rule_version"] = RULE_VERSION
        row["strategy"] = STEM
        kept.append(row)

    audit = dict(audit)
    audit["candidate_count_before_underreaction_cap"] = before_count
    audit["candidate_days_before_underreaction_cap"] = before_days
    audit["underreaction_close_location_cap"] = MAX_UNDERREACTION_CLOSE_LOCATION
    audit["underreaction_reject_counts"] = dict(sorted(reject_counter.items()))
    audit["candidate_count"] = len(kept)
    audit["candidate_days"] = len({row["date"] for row in kept})
    audit["unique_candidate_tickers"] = len({row["ticker"] for row in kept})
    audit["rule_version"] = RULE_VERSION
    return kept, audit


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
        "positive_replay_lead_not_promoted_requires_shared_adapter_and_forward_rows"
        if gate4["passed"]
        else "rejected_post_earnings_surprise_underreaction_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.28,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "sample_too_thin",
            "late_strong_regression",
            "drawdown_drift",
            "posthoc_threshold_overfit",
        ],
        "confidence_reason": (
            "Rejected exp-20260602-006 showed high-close/euphoria rows were weak; "
            "a low-to-mid close-location cap is a distinct underreaction field but "
            "still high multiple-testing risk."
        ),
        "recorded_at": "2026-06-02T07:08:24+00:00",
        "brier_score": round((0.28 - actual_success) ** 2, 6),
    }
    calibration = {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": prediction["success_probability"],
        "brier_score": prediction["brier_score"],
        "expected_ev_delta": prediction["expected_ev_delta"],
        "actual_ev_delta": payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"],
        "expected_pnl_delta": prediction["expected_pnl_delta"],
        "actual_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "predicted_failure_mode_hit": (
            False if gate4["passed"] else any(
                token in "; ".join(gate4["failed_reasons"])
                for token in ["sample", "late_strong", "drawdown", "trade"]
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
                "Confirmed positive EPS surprises that close in the low-to-mid part "
                "of the signal-day range may represent underreaction drift and avoid "
                "the high-close/euphoria rows that hurt exp-20260602-006."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "post_earnings_continuation",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260602-003",
                "exp-20260602-004",
                "exp-20260602-006",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "production_visible_earnings_event_underreaction_price_shape_field",
            "prediction": prediction,
            "calibration": calibration,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "paper_notional_usd": parent.framework.base.BASE_NOTIONAL_USD,
                "hold_days": parent.framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": parent.framework.MAX_PAPER_TRADES_PER_DAY,
                "parent_source": "exp-20260602-006 positive-surprise snapshot-transition source",
                "max_underreaction_close_location": MAX_UNDERREACTION_CLOSE_LOCATION,
                "locked_parent_variables": {
                    "recent_signal_days_min": parent.RECENT_SIGNAL_DAYS_MIN,
                    "recent_signal_days_max": parent.RECENT_SIGNAL_DAYS_MAX,
                    "min_latest_surprise_pct": parent.MIN_LATEST_SURPRISE_PCT,
                    "min_positive_surprise_count": parent.MIN_POSITIVE_SURPRISE_COUNT,
                    "min_surprise_history_count": parent.MIN_SURPRISE_HISTORY_COUNT,
                    "min_reset_dte": parent.MIN_RESET_DTE,
                    "max_pre_reset_dte": parent.MAX_PRE_RESET_DTE,
                    "moving_average_days": parent.MOVING_AVERAGE_DAYS,
                    "relative_strength_days": parent.RELATIVE_STRENGTH_DAYS,
                    "min_avg_dollar_volume_20d": parent.MIN_AVG_DOLLAR_VOLUME_20D,
                    "min_rs20_vs_spy": parent.MIN_RS20_VS_SPY,
                    "min_event_to_signal_return": parent.MIN_EVENT_TO_SIGNAL_RETURN,
                    "min_event_to_signal_excess_vs_spy": parent.MIN_EVENT_TO_SIGNAL_EXCESS_VS_SPY,
                    "min_close_location_floor": parent.MIN_CLOSE_LOCATION,
                },
                "source_definition": [
                    "same PIT earnings snapshot transition and OHLCV drift source as exp-20260602-006",
                    "only new candidate condition: signal-day close_location <= 0.70",
                    "top-1 selected paper entry per signal date after the underreaction cap",
                ],
                "acceptance": payload["parameters"]["acceptance"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: among confirmed positive EPS-surprise "
                    "events, low-to-mid signal-day close location should identify "
                    "underreaction instead of post-earnings euphoria."
                ),
                "2_history_check": {
                    "exp-20260602-003": (
                        "Accepted explicit post-earnings continuation semantics and "
                        "set the current core baseline."
                    ),
                    "exp-20260602-004": (
                        "DTE0 reaction scout selected zero trades."
                    ),
                    "exp-20260602-006": (
                        "Broad positive-surprise drift source improved aggregate EV "
                        "but failed late_strong and drawdown; high close-location rows "
                        "were weak in its target-trade attribution."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
                    "trades across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
                    "concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_011_post_earnings_surprise_underreaction.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe joins remain sparse. "
                "Skipped Companyfacts, FINRA, VBB, consensus, state-surface, and "
                "nearby sector-residual retunes because current playbook requires "
                "forward rows or materially new fields. This uses a new production-visible "
                "post-earnings underreaction field on the rejected earnings source."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. If promoted later, this exact "
                    "field must move into a shared default-off adapter using the same "
                    "daily earnings snapshot lifecycle and OHLCV close-location field "
                    "available to production before next-open paper entry."
                ),
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "live_orders_changed": False,
            },
            "interpretation": (
                "The underreaction close-location cap cleared Gate 4 as a replay lead, "
                "but no production/shared adapter was promoted."
                if gate4["passed"]
                else (
                    "The underreaction close-location cap did not clear Gate 4. Do not "
                    "promote it or retry nearby positive-surprise close-location caps on "
                    "these frozen windows without forward rows or a richer event-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, require closed forward replacement-value rows or a richer "
                "production-visible event-quality field such as revenue/EPS mix, guidance "
                "direction, or audited filing/news tone."
            ),
            "related_files": [
                "quant/experiments/exp_20260602_011_post_earnings_surprise_underreaction.py",
                "data/experiments/exp-20260602-011/exp_20260602_011_post_earnings_surprise_underreaction.json",
                "data/experiments/exp-20260602-011/post_earnings_surprise_underreaction_before_aggregate.json",
                "data/experiments/exp-20260602-011/post_earnings_surprise_underreaction_after_aggregate.json",
                "experiments/logs/exp-20260602-011.json",
                "experiments/tickets/exp-20260602-011.json",
                "experiments/artifacts/exp-20260602-011_post_earnings_surprise_underreaction.md",
                "docs/experiment_log.jsonl",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "earnings_snapshots": {
            "source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
            "snapshots_loaded": parent.earnings_helper._EARNINGS_DATE_COUNT,
            "required_fields": [
                "days_to_earnings",
                "eps_actual_last",
                "historical_surprise_pct",
                "avg_historical_surprise_pct",
            ],
            "tickers_with_snapshot_rows": len(parent.earnings_helper._load_earnings_index()),
        },
        "ohlcv": {
            "required_field": "signal-day OHLCV high/low/close for close_location",
            "decision_time": "known after signal-day close before next-open paper entry",
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
            "close_location",
            "post_earnings_underreaction_close_location_cap",
            "event_to_signal_excess_vs_spy",
            "rs20_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates | Cap rejects |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in parent.framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rejects = audit.get("underreaction_reject_counts", {}).get(
            "above_underreaction_close_location_cap",
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
            "# exp-20260602-011 Post-Earnings Surprise Underreaction",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: require `close_location <= 0.70` on the exp-20260602-006 PIT positive-surprise drift source before daily top-1 paper selection.",
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
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
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
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Post-earnings surprise underreaction",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._write_text(CARD_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def _write_manifest() -> None:
    base = parent.framework.base
    files = {
        "runner": base._repo_rel(Path(__file__)),
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
