"""exp-20260609-015: persistent revision overlay on accepted revision helper.

Alpha search, replay-only replacement-value test. This starts from the
accepted revision+surprise+low-extension shared helper and adds exactly one
decision requirement: the selected paper candidate must have a PIT-safe
``estimate_revision_ledger`` row with both 7d and 30d EPS estimate deltas
positive. The result must beat the accepted exp-20260609-011 adapter, not just
the core baseline, before it has any replacement value.

No production code, shared helper, live/default orders, ranking, sizing, exits,
LLM/news path, watchlist, or run.py behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
for _path in (ROOT / "quant", ROOT / "quant" / "experiments"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import exp_20260601_010_gap_up_hold_high_close_candidate_pool as framework  # noqa: E402
import revision_surprise_low_extension_paper_sleeve as sleeve  # noqa: E402


EXPERIMENT_ID = "exp-20260609-015"
STEM = "persistent_revision_surprise_overlay"
TRIAL_FAMILY = "analyst_revision_surprise_persistence_candidate_pool"
TRIAL_VARIANT_ID = "persistent_7d_30d_revision_overlay_v1"
CHANGED_VARIABLE = "persistent_7d_30d_eps_revision_overlay_on_accepted_revision_candidate_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = float(sleeve.DEFAULT_CONFIG["paper_notional_usd"])
HOLD_DAYS = int(sleeve.DEFAULT_CONFIG["hold_days"])
MAX_PAPER_TRADES_PER_DAY = int(sleeve.DEFAULT_CONFIG["daily_entry_slots"])

MIN_PRICE = float(sleeve.DEFAULT_CONFIG["min_price"])
MIN_AVG_DOLLAR_VOLUME_20 = float(sleeve.DEFAULT_CONFIG["min_avg_dollar_volume_20d"])
MIN_VOLUME_RATIO_20 = float(sleeve.DEFAULT_CONFIG["min_volume_ratio_20d"])
MIN_CLOSE_LOCATION = float(sleeve.DEFAULT_CONFIG["min_close_location"])
MIN_RET20_EXCESS_SPY = float(sleeve.DEFAULT_CONFIG["min_ret20_excess_spy"])
MAX_RET20_EXCESS_SPY = float(sleeve.DEFAULT_CONFIG["max_ret20_excess_spy"])

MIN_EPS_DELTA_7D = 0.0
MIN_EPS_DELTA_30D = 0.0
MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

ACCEPTED_COMPARATOR_JSON = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260609-011"
    / "revision_surprise_low_extension_shared_adapter.json"
)

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
LEDGER_DIR = ROOT / "data" / "non_ohlcv"

_ORIGINAL_BUILD_PAYLOAD = framework._build_payload
_ORIGINAL_ARTIFACT = framework._artifact
_LEDGER_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_PRICE = MIN_PRICE
    framework.MIN_AVG_DOLLAR_VOLUME_20 = MIN_AVG_DOLLAR_VOLUME_20
    framework.MIN_VOLUME_RATIO_20 = MIN_VOLUME_RATIO_20
    framework.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    framework.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_JSON = BEFORE_JSON
    framework.AFTER_JSON = AFTER_JSON
    framework.LOG_JSON = LOG_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.CARD_MD = CARD_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_payload = _build_payload
    framework._artifact = _artifact


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _load_ledger_for_date(as_of: str) -> dict[str, dict[str, Any]]:
    date_key = str(as_of)[:10]
    if date_key in _LEDGER_CACHE:
        return _LEDGER_CACHE[date_key]
    path = LEDGER_DIR / f"estimate_revision_ledger_{date_key.replace('-', '')}.jsonl"
    rows: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                rows[ticker] = row
    _LEDGER_CACHE[date_key] = rows
    return rows


def _persistence_reject_reason(row: dict[str, Any] | None) -> str | None:
    if row is None:
        return "missing_estimate_revision_ledger_row"
    if not row.get("pit_safe_flag"):
        return "ledger_row_not_pit_safe"
    if not row.get("estimate_revision_usable"):
        return "ledger_row_not_revision_usable"
    delta_7d = _float(row.get("eps_estimate_delta_7d"))
    delta_30d = _float(row.get("eps_estimate_delta_30d"))
    if delta_7d is None:
        return "missing_eps_estimate_delta_7d"
    if delta_30d is None:
        return "missing_eps_estimate_delta_30d"
    if delta_7d <= MIN_EPS_DELTA_7D:
        return "non_positive_eps_estimate_delta_7d"
    if delta_30d <= MIN_EPS_DELTA_30D:
        return "non_positive_eps_estimate_delta_30d"
    return None


def _ledger_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of_date": row.get("as_of_date"),
        "next_earnings_date": row.get("next_earnings_date"),
        "fiscal_period": row.get("fiscal_period"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
        "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
        "revision_direction_prev": row.get("revision_direction_prev"),
        "same_event_history_count": row.get("same_event_history_count"),
        "pit_safe_flag": row.get("pit_safe_flag"),
        "estimate_revision_usable": row.get("estimate_revision_usable"),
        "pit_caveat": row.get("pit_caveat"),
        "source_snapshot_path": row.get("source_snapshot_path"),
        "prior_snapshot_date": row.get("prior_snapshot_date"),
    }


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if "SPY" not in frames:
        raise RuntimeError("SPY is required for revision surprise persistence replay")
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])
    signal_dates = [str(idx.date()) for idx in frames["SPY"].loc[start:end].index]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates, contexts, scan = sleeve.build_revision_surprise_low_extension_candidate_rows(
        ohlcv_by_ticker=frames,
        dates=signal_dates,
        core_entries_by_date=core_entries,
        config=sleeve.DEFAULT_CONFIG,
        require_future_bars=True,
    )
    accepted_selected, accepted_rejected = sleeve.select_revision_surprise_low_extension_signal_rows(
        candidates=candidates,
        config=sleeve.DEFAULT_CONFIG,
    )

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    ledger_pass_counts: Counter[str] = Counter()
    blocked_examples: list[dict[str, Any]] = []

    for row in accepted_selected:
        date_key = str(row.get("date") or row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        ledger_row = _load_ledger_for_date(date_key).get(ticker)
        reason = _persistence_reject_reason(ledger_row)
        if reason is not None:
            reject_counts[reason] += 1
            rejected_row = {**row, "filter_reason": reason}
            if ledger_row:
                rejected_row["estimate_revision_ledger"] = _ledger_summary(ledger_row)
            rejected.append(rejected_row)
            if len(blocked_examples) < 25:
                blocked_examples.append(
                    {
                        "ticker": ticker,
                        "date": date_key,
                        "reject_reason": reason,
                        "accepted_helper_score": row.get("score"),
                        "ret20_excess_spy": row.get("ret20_excess_spy"),
                        "eps_estimate_revision_20d_pct": row.get(
                            "eps_estimate_revision_20d_pct"
                        ),
                        "ledger": _ledger_summary(ledger_row) if ledger_row else None,
                    }
                )
            continue

        assert ledger_row is not None
        ledger_pass_counts["persistent_7d_30d_positive_passed"] += 1
        updated = {
            **row,
            "rule_version": RULE_VERSION,
            "source_rule_version": sleeve.RULE_VERSION,
            "persistent_revision_overlay_passed": True,
            "eps_estimate_delta_7d": ledger_row.get("eps_estimate_delta_7d"),
            "eps_estimate_delta_30d": ledger_row.get("eps_estimate_delta_30d"),
            "eps_estimate_delta_prev": ledger_row.get("eps_estimate_delta_prev"),
            "revision_direction_prev": ledger_row.get("revision_direction_prev"),
            "same_event_history_count": ledger_row.get("same_event_history_count"),
            "estimate_revision_ledger": _ledger_summary(ledger_row),
            "trade_enabled": False,
            "alters_orders": False,
        }
        kept.append(updated)

    tail_rejects = Counter(
        str(row.get("filter_reason") or "unknown")
        for row in accepted_rejected
        if str(row.get("filter_reason") or "").startswith("ret20")
        or str(row.get("filter_reason") or "") == "missing_ret20_excess_spy"
    )
    diagnostics = {
        "raw_pass_counts": scan.get("raw_pass_counts", {}),
        "revision_reject_counts": scan.get("revision_reject_counts", {}),
        "revision_source": scan.get("revision_source"),
        "revision_source_caveat": scan.get("revision_source_caveat"),
        "raw_candidate_count": scan.get("raw_candidate_count", 0),
        "candidate_day_count": scan.get("candidate_day_count", 0),
        "contexts": contexts[:25],
        "accepted_helper_selected_count": len(accepted_selected),
        "accepted_helper_rejected_count": len(accepted_rejected),
        "kept_selected_count": len(kept),
        "persistent_revision_overlay": {
            "policy": (
                "Accepted helper selected top1 must also have PIT-safe "
                "estimate_revision_ledger eps_estimate_delta_7d > 0 and "
                "eps_estimate_delta_30d > 0; no backup substitution."
            ),
            "ledger_dir": framework._repo_rel(LEDGER_DIR),
            "min_eps_delta_7d": MIN_EPS_DELTA_7D,
            "min_eps_delta_30d": MIN_EPS_DELTA_30D,
            "accepted_helper_selected_count": len(accepted_selected),
            "kept_selected_count": len(kept),
            "blocked_selected_count": len(accepted_selected) - len(kept),
            "reject_counts": dict(sorted(reject_counts.items())),
            "pass_counts": dict(sorted(ledger_pass_counts.items())),
            "blocked_examples": blocked_examples,
        },
        "low_extension_tail_gate": {
            "max_ret20_excess_spy": MAX_RET20_EXCESS_SPY,
            "policy": "accepted helper selected-top1 gate; no backup substitution",
            "prior_raw_candidate_count": len(candidates),
            "accepted_helper_selected_count": len(accepted_selected),
            "accepted_helper_rejected_count": len(accepted_rejected),
            "tail_reject_counts": dict(sorted(tail_rejects.items())),
        },
        "production_parity_guard": {
            "replay_only": True,
            "shared_helper_unchanged": True,
            "daily_snapshot_unchanged": True,
            "promotion_requires_shared_helper": True,
        },
    }
    return kept, diagnostics


def _accepted_comparator() -> dict[str, Any]:
    if not ACCEPTED_COMPARATOR_JSON.exists():
        return {"available": False, "path": framework._repo_rel(ACCEPTED_COMPARATOR_JSON)}
    payload = json.loads(ACCEPTED_COMPARATOR_JSON.read_text(encoding="utf-8"))
    return {
        "available": True,
        "path": framework._repo_rel(ACCEPTED_COMPARATOR_JSON),
        "experiment_id": payload.get("experiment_id"),
        "decision": payload.get("decision"),
        "aggregate": payload.get("aggregate") or {},
        "after_metrics": payload.get("after_metrics") or {},
    }


def _comparator_gate(payload: dict[str, Any]) -> dict[str, Any]:
    comparator = _accepted_comparator()
    if not comparator.get("available"):
        return {
            "passed": False,
            "failed_reasons": ["accepted_comparator_missing"],
            "comparator": comparator,
        }
    agg = payload["aggregate"]
    comp_agg = comparator["aggregate"]
    reasons: list[str] = []
    if agg["after_expected_value_score_sum"] <= float(
        comp_agg.get("after_expected_value_score_sum") or 0.0
    ):
        reasons.append("accepted_adapter_aggregate_ev_not_beaten")
    if agg["after_total_pnl_sum"] <= float(comp_agg.get("after_total_pnl_sum") or 0.0):
        reasons.append("accepted_adapter_aggregate_pnl_not_beaten")

    window_details: dict[str, Any] = {}
    for label, after in payload["after_metrics"].items():
        comp_after = (comparator["after_metrics"] or {}).get(label) or {}
        ev_delta = float(after.get("expected_value_score") or 0.0) - float(
            comp_after.get("expected_value_score") or 0.0
        )
        pnl_delta = float(after.get("total_pnl") or 0.0) - float(
            comp_after.get("total_pnl") or 0.0
        )
        window_details[label] = {
            "after_expected_value_score": after.get("expected_value_score"),
            "accepted_after_expected_value_score": comp_after.get("expected_value_score"),
            "ev_delta_vs_accepted": framework._round(ev_delta, 6),
            "after_total_pnl": after.get("total_pnl"),
            "accepted_after_total_pnl": comp_after.get("total_pnl"),
            "pnl_delta_vs_accepted": framework._round(pnl_delta, 2),
        }
        if ev_delta < 0:
            reasons.append(f"{label}_ev_below_accepted_adapter")
        if pnl_delta < 0:
            reasons.append(f"{label}_pnl_below_accepted_adapter")

    return {
        "passed": not reasons,
        "failed_reasons": reasons,
        "comparator": comparator,
        "window_details": window_details,
        "aggregate_delta_vs_accepted": {
            "expected_value_score": framework._round(
                agg["after_expected_value_score_sum"]
                - float(comp_agg.get("after_expected_value_score_sum") or 0.0),
                6,
            ),
            "total_pnl": framework._round(
                agg["after_total_pnl_sum"] - float(comp_agg.get("after_total_pnl_sum") or 0.0),
                2,
            ),
        },
    }


def _build_payload() -> dict[str, Any]:
    payload = _ORIGINAL_BUILD_PAYLOAD()
    numeric_core_passed = bool(payload["gate4"].get("passed"))
    comparator_gate = _comparator_gate(payload)
    accepted = numeric_core_passed and bool(comparator_gate.get("passed"))
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_persistence_adapter"
        if accepted
        else "rejected_persistent_revision_surprise_overlay"
    )
    if accepted:
        rationale = (
            "The persistent 7d/30d revision overlay beat both the core baseline "
            "and accepted exp-20260609-011 comparator, but it remains replay-only "
            "until the same overlay is implemented in a shared daily/historical "
            "helper with forward default-off observation."
        )
    else:
        rationale = (
            "The 7d/30d persistent revision overlay did not show replacement "
            "value over the accepted revision+surprise+low-extension adapter. "
            "No production or shared policy behavior is retained."
        )

    actual_success = 1 if accepted else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]

    failed = list(payload["gate4"].get("failed_gates") or [])
    failed.extend(comparator_gate.get("failed_reasons") or [])
    failed = sorted(dict.fromkeys(failed))
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "rejected" if not accepted else "positive_lead",
            "decision": decision,
            "accepted": False,
            "hypothesis": (
                "Accepted revision+surprise+low-extension candidates should have "
                "higher replacement value when analyst expectation drift is "
                "persistent across both 7d and 30d PIT EPS estimate deltas."
            ),
            "change_type": "default_off_paper_candidate_pool_replay_overlay",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "analyst_revision_expectation_trajectory",
            "prior_trial_count": 6,
            "nearby_prior_experiments": [
                "exp-20260528-030",
                "exp-20260529-007",
                "exp-20260604-029",
                "exp-20260606-016",
                "exp-20260608-011",
                "exp-20260609-011",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "pit_estimate_revision_ledger_persistence_overlay",
            "interpretation": rationale,
            "rejection_reason": None if accepted else "; ".join(failed),
            "prediction": {
                "success_probability": 0.18,
                "expected_ev_delta": 0.08,
                "expected_pnl_delta": 1200.0,
                "main_failure_modes": [
                    "sample_too_thin",
                    "accepted_adapter_not_beaten",
                    "old_thin_regression",
                    "persistence_field_proxy_overlap",
                    "complexity_without_replacement_value",
                ],
                "confidence_reason": (
                    "The revision lane is strongest and exp-20260609-011 is "
                    "accepted, but prior revision magnitude/persistence studies "
                    "were mixed; this run requires PIT ledger persistence to beat "
                    "the accepted helper, not merely add another filter."
                ),
                "recorded_at": "2026-06-09T14:06:50+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.18 - actual_success) ** 2, 6),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Start from exp-20260609-011 accepted shared helper selected "
                "top1 rows, then require the matching estimate_revision_ledger "
                "row to be PIT-safe, revision usable, eps_estimate_delta_7d > 0, "
                "and eps_estimate_delta_30d > 0. No backup candidate is selected."
            ),
            "min_eps_delta_7d": MIN_EPS_DELTA_7D,
            "min_eps_delta_30d": MIN_EPS_DELTA_30D,
            "selection_policy": "accepted_helper_selected_top1_overlay_no_backup_substitution",
            "acceptance_addendum": (
                "Must beat accepted exp-20260609-011 after aggregate EV/PnL and "
                "not regress any canonical window versus that accepted adapter."
            ),
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / analyst-revision persistence: simultaneous positive "
            "7d and 30d PIT EPS estimate deltas should identify sustained "
            "expectation drift rather than one-off noisy snapshot changes."
        ),
        "2_history_check": {
            "exp-20260528-030": (
                "Added PIT 30d estimate revision derivation; proves field can be "
                "computed but did not itself prove alpha."
            ),
            "exp-20260529-007": (
                "Revision magnitude attribution found mixed axes and warned "
                "against simple magnitude mining."
            ),
            "exp-20260604-029": (
                "Raw revision velocity was positive but proxy-grade and failed "
                "old_thin robustness."
            ),
            "exp-20260609-011": (
                "Accepted shared default-off revision+surprise+low-extension "
                "adapter; this run must beat it to justify added complexity."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows versus core baseline "
            "plus an accepted-comparator gate against exp-20260609-011; positive "
            "results cannot be promoted without shared daily/historical parity."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_015_persistent_revision_surprise_overlay.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate4"].update(
        {
            "passed": accepted,
            "numeric_core_gate_passed": numeric_core_passed,
            "accepted_comparator_gate": comparator_gate,
            "decision": decision,
            "rationale": rationale,
            "failed_gates": failed,
            "requires_shared_adapter_before_promotion": accepted,
        }
    )
    payload["production_impact"].update(
        {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_data_fetch_changed": False,
            "accepted_helper_unchanged": True,
            "requires_shared_adapter_before_promotion": accepted,
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "trade_enabled": False,
        "replay_only": True,
        "accepted_shared_helper_unchanged": True,
        "historical_replay_uses_accepted_helper_then_local_overlay": True,
        "daily_snapshot_uses_overlay": False,
        "promotion_requires_shared_helper": True,
        "parity_note": (
            "No production/backtest mismatch is introduced because the overlay "
            "is rejected/replay-only and changes no production or shared daily "
            "path. A future positive promotion would need a shared helper using "
            "the same estimate_revision_ledger semantics."
        ),
    }
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The overlay asks for persistent 7d and 30d revision evidence after "
            "the accepted helper has already required a strong 20-snapshot EPS "
            "revision, positive surprise history, and a low-extension breakout. "
            "If it underperforms the accepted adapter, the added ledger condition "
            "is mostly redundant or overfilters scarce good entries instead of "
            "adding independent replacement value."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep 7d/30d delta thresholds, require only one horizon, "
            "relax PIT safety, add backup substitution, or retune accepted helper "
            "revision/surprise/ret20/DTE/volume thresholds on the same frozen "
            "sample."
        ),
        "new_evidence_required": (
            "A retry needs materially new analyst-estimate evidence, such as "
            "analyst-count trajectory, vendor-grade revision provenance, or "
            "forward default-off rows showing that persistent revision names "
            "replace accepted helper losers rather than just reduce sample size."
        ),
        "outcome_interpretation": rationale,
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    text = _ORIGINAL_ARTIFACT(payload).replace(
        "Gap-Up Hold High-Close Candidate Pool",
        "Persistent Revision Surprise Overlay",
    )
    comparator = payload["gate4"]["accepted_comparator_gate"]
    return (
        text
        + "\n## Persistent Revision Overlay\n\n"
        + "- source: existing `estimate_revision_ledger_YYYYMMDD.jsonl` rows\n"
        + "- rule: `pit_safe_flag && estimate_revision_usable && "
        + "eps_estimate_delta_7d > 0 && eps_estimate_delta_30d > 0`\n"
        + "- policy: accepted helper selected top1 only; no backup substitution.\n"
        + "- production parity: replay-only and rejected unless it beats the "
        + "accepted shared helper; no production/default path changed.\n\n"
        + "## Accepted Comparator Gate\n\n"
        + f"- comparator: `{comparator['comparator'].get('path')}`\n"
        + f"- aggregate EV delta vs accepted: "
        + f"`{comparator['aggregate_delta_vs_accepted']['expected_value_score']}`\n"
        + f"- aggregate PnL delta vs accepted: "
        + f"`{comparator['aggregate_delta_vs_accepted']['total_pnl']}`\n"
        + f"- failed comparator reasons: "
        + f"`{', '.join(comparator['failed_reasons']) or 'none'}`\n"
    )


def _patch_card_status(payload: dict[str, Any]) -> None:
    if not CARD_MD.exists():
        return
    text = CARD_MD.read_text(encoding="utf-8")
    text = text.replace('status: "proposed"', f'status: "{payload["status"]}"', 1)
    text = text.replace("- Status: `proposed`", f"- Status: `{payload['status']}`", 1)
    text = text.replace("- Why did the result happen? TODO", f"- Why did the result happen? {payload['post_run_reflection']['why_result_happened']}")
    text = text.replace("- Which near-neighbor retry is now forbidden? TODO", f"- Which near-neighbor retry is now forbidden? {payload['post_run_reflection']['forbidden_near_neighbor_retry']}")
    text = text.replace("- What new evidence would justify a retry? TODO", f"- What new evidence would justify a retry? {payload['post_run_reflection']['new_evidence_required']}")
    text = text.replace("- Decision: TODO", f"- Decision: {payload['decision']}")
    text = text.replace("- Before artifact: TODO", f"- Before artifact: {framework._repo_rel(BEFORE_JSON)}")
    text = text.replace("- After artifact: TODO", f"- After artifact: {framework._repo_rel(AFTER_JSON)}")
    text = text.replace("- Main blocker or acceptance basis: TODO", f"- Main blocker or acceptance basis: {payload['interpretation']}")
    text = text.replace("- Next retry requires: TODO", f"- Next retry requires: {payload['post_run_reflection']['new_evidence_required']}")
    CARD_MD.write_text(text, encoding="utf-8")


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _patch_framework()
    payload = framework.run(output)
    _patch_card_status(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": framework._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
