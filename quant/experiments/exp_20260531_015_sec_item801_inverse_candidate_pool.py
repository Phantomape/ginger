"""exp-20260531-015: SEC Item 8.01 inverse paper candidate pool.

This alpha search tests one free SEC structured-data edge: PIT-safe 8-K
Item 8.01 filings that also pass the existing liquid OHLCV reaction context
from exp-20260529-015, but the paper trade is inverse because the hardened
Item-family attribution in exp-20260530-002 found Item 8.01 forward drift to
be negative.

Replay-only/default-off paper. No production orders, core ranking, sizing,
exits, LLM/news, shared policy, or watchlist behavior changes. No JavaScript is
used.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260529_015_sec_fd_other_8k_positive_reaction_candidate_pool as prev


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-015"
STEM = "sec_item801_inverse_candidate_pool"
TRIAL_FAMILY = "sec_item801_adverse_drift_inverse_candidate_pool"
CHANGED_VARIABLE = "sec_item801_adverse_drift_inverse_candidate_source_v1"
RULE_VERSION = "sec_item801_positive_reaction_inverse_paper_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_015_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

TARGET_ITEM_CODES = {"8.01"}
EXCLUDED_ITEM_CODES = {
    "1.01",
    "2.02",
    "2.03",
    "3.02",
    "3.03",
    "5.01",
    "5.02",
    "5.03",
    "5.07",
    "7.01",
}
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

_LONG_SELECTOR = None


def _patch_framework() -> None:
    global _LONG_SELECTOR
    prev.EXPERIMENT_ID = EXPERIMENT_ID
    prev.STEM = STEM
    prev.TRIAL_FAMILY = TRIAL_FAMILY
    prev.CHANGED_VARIABLE = CHANGED_VARIABLE
    prev.RULE_VERSION = RULE_VERSION
    prev.OUT_DIR = OUT_DIR
    prev.OUT_JSON = OUT_JSON
    prev.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    prev.AFTER_AGG_JSON = AFTER_AGG_JSON
    prev.LOG_JSON = LOG_JSON
    prev.TICKET_JSON = TICKET_JSON
    prev.CARD_MD = CARD_MD
    prev.ARTIFACT_MD = ARTIFACT_MD
    prev.EXPERIMENT_LOG = EXPERIMENT_LOG
    prev.TARGET_ITEM_CODES = TARGET_ITEM_CODES
    prev.EXCLUDED_ITEM_CODES = EXCLUDED_ITEM_CODES
    prev.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    prev.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    prev._SEC_FD_OTHER_EVENTS_CACHE = None
    prev._patch_framework()
    _LONG_SELECTOR = prev.framework._select_paper_trades
    prev.framework._select_paper_trades = _select_inverse_paper_trades


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _select_inverse_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if _LONG_SELECTOR is None:
        raise RuntimeError("long paper selector not configured")
    long_trades, filtered = _LONG_SELECTOR(snapshot, candidates)
    inverse_trades: list[dict[str, Any]] = []
    base = prev.framework.base
    for trade in long_trades:
        entry_raw = _float(trade.get("entry_raw_open"))
        exit_raw = _float(trade.get("exit_raw_close"))
        if entry_raw is None or exit_raw is None or entry_raw <= 0.0 or exit_raw <= 0.0:
            filtered.append({**trade, "filter_reason": "missing_inverse_entry_or_cover_price"})
            continue
        short_entry = base.apply_slippage(entry_raw, base.SLIPPAGE_BPS_TARGET, "sell")
        cover_price = base.apply_entry_fill(exit_raw)
        pnl_pct_net = (short_entry / cover_price) - 1.0 - base.ROUND_TRIP_COST_PCT
        pnl = base.BASE_NOTIONAL_USD * pnl_pct_net
        inverse_trades.append(
            {
                **trade,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "paper_direction": "inverse_short_proxy",
                "long_side_pnl_reference": trade.get("pnl"),
                "long_side_pnl_pct_reference": trade.get("pnl_pct_net"),
                "entry_price": base._round(short_entry, 4),
                "exit_price": base._round(cover_price, 4),
                "pnl_pct_net": base._round(pnl_pct_net, 6),
                "pnl": base._round(pnl, 2),
                "borrow_cost_mode": "not_modeled",
                "short_activation_blocker": "borrow_locate_and_gap_risk_not_modeled",
                "known_at": "after_sec_8k_item801_usable_trade_date_close_before_next_open_inverse_paper_entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    return inverse_trades, filtered


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = prev._postprocess_payload(payload)
    gate4 = payload["gate4"]
    accepted = bool(gate4.get("passed"))
    decision = (
        "accepted_replay_only_sec_item801_inverse_candidate_pool"
        if accepted
        else "rejected_sec_item801_inverse_candidate_pool"
    )
    actual_success = 1 if accepted else 0
    prediction = {
        "success_probability": 0.28,
        "expected_ev_delta": 0.10,
        "expected_pnl_delta": 2500.0,
        "main_failure_modes": [
            "short_side_borrow_unmodeled",
            "window_regression",
            "thin_sample",
            "concentration_failed",
        ],
        "confidence_reason": (
            "exp-20260530-002 found robust negative Item 8.01 drift and "
            "exp-20260529-015 rejected the adjacent positive-reaction long "
            "source. This is still modest probability because the inverse side "
            "does not model borrow/locate costs."
        ),
        "recorded_at": "2026-05-31T15:08:42+00:00",
        "brier_score": round((0.28 - actual_success) ** 2, 6),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "SEC 8-K Item 8.01 adverse-drift events may form a replay-only "
                "inverse paper candidate pool when filtered by PIT-safe filing "
                "metadata and liquid OHLCV context."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260530-002",
                "exp-20260529-015",
                "exp-20260529-019",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "free_sec_structured_event_family_negative_drift_candidate_source",
            "prediction": prediction,
            "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Do not activate inverse/short behavior without borrow, locate, "
                "gap-risk, and forward replacement-value evidence. If rejected, "
                "do not retry nearby Item 8.01 reaction thresholds on these "
                "windows without filing-body subtype data."
            ),
            "interpretation": (
                "The Item 8.01 inverse paper source cleared replay Gate 4, but "
                "it remains default-off and activation-blocked by missing short "
                "borrow/locate modeling."
                if accepted
                else (
                    "The Item 8.01 inverse paper source did not clear Gate 4. "
                    "Do not promote it or retry nearby Item 8.01 reaction/RS "
                    "thresholds on this frozen sample without filing-body subtype "
                    "or forward replacement-value evidence."
                )
            ),
            "short_side_cost_model": {
                "borrow_costs_modeled": False,
                "locate_availability_modeled": False,
                "activation_blocker": "short_borrow_locate_and_gap_risk_not_modeled",
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay attribution remains "
                "sparse. Skipped alpha_score, peer-shock, FINRA, VBB/VCP, "
                "Companyfacts, and state-surface retunes per recent failed or "
                "frozen evidence. This run tests one structured SEC Item 8.01 "
                "inverse candidate-source variable only."
            ),
        }
    )
    payload["parameters"].update(
        {
            "target_item_codes": sorted(TARGET_ITEM_CODES),
            "excluded_item_codes": sorted(EXCLUDED_ITEM_CODES),
            "paper_direction": "inverse_short_proxy",
            "borrow_costs_modeled": False,
            "source_definition": [
                "SEC filing event has form_base/form_type 8-K",
                "event row must have pit_safe_flag true and usable_trade_date",
                "amended 8-K rows are excluded",
                "item codes must include 8.01 and must not include 7.01 or other excluded material item codes",
                "ticker must have exact signal-date OHLCV in the fixed snapshot",
                "close must be above the prior 50-day moving average",
                "20-day return must beat SPY by at least 0 percentage points",
                "20-day average dollar volume must be at least USD 20 million",
                "signal-day ticker-minus-SPY return must be nonnegative",
                "signal-day close location must be at least 0.55",
                "paper trade direction is inverse short proxy, top-1 selected per signal date",
            ],
        }
    )
    payload["production_impact"].update(
        {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "Even if replay-positive, this requires a shared default-off "
                "paper adapter plus borrow/locate, gap-risk, and parity tests "
                "before any live or default behavior changes."
            ),
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "parity_note": (
            "No production code path is changed. A future promotion would need a "
            "shared SEC Item 8.01 default-off paper/inverse adapter and explicit "
            "short-cost handling; this experiment is not a production rule."
        ),
    }
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / risk allocation: the robust negative Item 8.01 "
            "event-family drift may be harvestable only as an inverse paper "
            "candidate, not as a long continuation source."
        ),
        "2_history_check": {
            "exp-20260530-002": (
                "Hardened read-only attribution found Item 8.01 negative 10d "
                "drift that survived drop-top-ticker and first-event-per-ticker "
                "controls."
            ),
            "exp-20260529-015": (
                "FD/Other 7.01/8.01 positive-reaction long source regressed all "
                "three windows. This run isolates 8.01 and flips paper direction."
            ),
            "exp-20260529-019": (
                "Item 5.02 direct long source failed and was not reused."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "no EV/PnL-regressed window; target sample and concentration pass; "
            "drawdown drift <=0.5pp; survival >=5%. Any positive result remains "
            "activation-blocked by short cost/locate modeling."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260531_015_sec_item801_inverse_candidate_pool.py"
        ),
    }
    payload["related_files"] = [
        prev.framework.base._repo_rel(Path(__file__)),
        prev.framework.base._repo_rel(OUT_JSON),
        prev.framework.base._repo_rel(BEFORE_AGG_JSON),
        prev.framework.base._repo_rel(AFTER_AGG_JSON),
        prev.framework.base._repo_rel(LOG_JSON),
        prev.framework.base._repo_rel(TICKET_JSON),
        prev.framework.base._repo_rel(CARD_MD),
        prev.framework.base._repo_rel(ARTIFACT_MD),
        prev.framework.base._repo_rel(EXPERIMENT_LOG),
        prev.framework.base._repo_rel(prev.SEC_EVENTS_FILE),
    ]
    payload["anti_js"] = "No JavaScript was used."
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Inverse trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prev.framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
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
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            "# exp-20260531-015 SEC Item 8.01 Inverse Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: PIT-safe SEC 8-K Item 8.01 positive-reaction events are isolated and evaluated as a default-off inverse paper candidate pool.",
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
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.",
            "",
            "Short borrow, locate, and gap-risk costs are not modeled, so any positive replay result is not live-activation evidence.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base = prev.framework.base
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC Item 8.01 inverse candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    base._write_json(TICKET_JSON, ticket_payload)
    report = _build_report(payload)
    base._write_text(ARTIFACT_MD, report)
    base._write_text(CARD_MD, report)
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(prev.framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            prev.framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": prev.framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": prev.framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": prev.framework.base._repo_rel(AFTER_AGG_JSON),
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
