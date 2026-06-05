"""exp-20260605-020: SEC after-hours 8-K Item 5.02 leadership pool.

This alpha search tests one replay-only/default-off paper candidate source:
after-hours SEC 8-K Item 5.02 leadership-change filings whose first usable
trading day confirms prior trend/RS quality. The entry is delayed until the
next open after that close is known.

No production adapter, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260605_019_sec_after_hours_8k_trend_candidate_pool as base


EXP_ID = "exp-20260605-020"
STEM = "sec_after_hours_5_02_leadership_candidate_pool"
TRIAL_FAMILY = "sec_after_hours_5_02_leadership_candidate_pool"
TRIAL_VARIANT_ID = "sec_after_hours_5_02_leadership_top1_delayed_entry_v1"
CHANGED_VARIABLE = "sec_after_hours_8k_item_5_02_leadership_trend_candidate_source_v1"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_020_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"

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
    "parity_note": (
        "This runner changes no production code. It uses only historical "
        "PIT-safe SEC filing feature rows, observed accepted_datetime timing, "
        "first usable trading-day OHLCV available after the close, and a "
        "delayed next-open paper entry. A positive result would still require "
        "a separate shared default-off SEC Item 5.02 leadership adapter and "
        "parity tests before any report queue, candidate priority, or order "
        "surface could change."
    ),
}


def _apply_config() -> None:
    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_JSON = BEFORE_JSON
    base.AFTER_JSON = AFTER_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.ARTIFACT_MD = ARTIFACT_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.INCLUDED_ITEM_CODES = frozenset({"5.02"})
    base.EXCLUDED_ITEM_PREFIXES = ("2.02", "2.03", "3.02", "4.01")
    base.__file__ = __file__
    base._gate4 = _leadership_gate4
    base._write_artifact = _write_artifact


def _leadership_gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate = _ORIGINAL_GATE4(aggregate_comparison, results, target_summary)
    if gate["passed"]:
        gate["decision"] = "positive_replay_lead_not_promoted_requires_shared_sec_5_02_adapter"
        gate["status"] = "observed_only"
        gate["rationale"] = (
            "The after-hours SEC Item 5.02 leadership-change source improved "
            "all canonical windows and passed sample, drawdown, survival, and "
            "concentration guards. It remains replay-only until a shared "
            "default-off adapter and parity tests are implemented."
        )
    else:
        gate["decision"] = "rejected_sec_after_hours_5_02_leadership_candidate_pool"
        gate["status"] = "rejected"
        gate["rationale"] = (
            "One or more Gate 4 checks failed, so this after-hours SEC "
            "Item 5.02 leadership-change candidate source is not retained or "
            "promoted."
        )
    return gate


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    payload["experiment_id"] = EXP_ID
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["rule_version"] = CHANGED_VARIABLE
    payload["status"] = gate4["status"]
    payload["decision"] = gate4["decision"]
    payload["preflight"] = {
        "alpha_hypothesis": (
            "After-hours SEC 8-K Item 5.02 leadership-change filings with "
            "prior trend and relative-strength confirmation may add a "
            "PIT-safe default-off paper candidate source without expanding "
            "the core universe noisily."
        ),
        "category": "entry_candidate_pool",
        "playbook_alignment": (
            "Uses a free, production-visible SEC item field and tests a "
            "distinct filing-event candidate-pool source instead of LLM "
            "soft-ranking, Companyfacts peer retunes, FTD/FINRA retunes, "
            "post-earnings support stack retunes, or broad OHLCV-only pattern "
            "mining."
        ),
        "nearby_prior_experiments": {
            "exp-20260605-018": "Rejected operational 8-K quiet absorption; this run changes the event family to leadership-change Item 5.02.",
            "exp-20260605-019": "Rejected after-hours operational 8-K trend; this run keeps timing/trend mechanics but changes only the SEC item family.",
            "exp-20260605-006": "Rejected SEC business-development source-span direct issuer events.",
            "exp-20260503-051": "Historical leadership-change event attribution existed, but not this after-hours delayed-entry Item 5.02 candidate source.",
        },
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": base.MIN_TARGET_TRADES,
            "minimum_target_windows": base.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": base.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": base.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": base.MAX_POSITIVE_HHI,
        },
    }
    payload["parameters"]["included_item_codes"] = ["5.02"]
    payload["parameters"]["excluded_item_prefixes"] = list(base.EXCLUDED_ITEM_PREFIXES)
    payload["parameters"]["sec_item_family"] = "8-K Item 5.02 leadership_change"
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["next_action"] = (
        "If positive, build a shared default-off SEC Item 5.02 leadership "
        "adapter with after-hours timing, delayed-entry semantics, and parity "
        "tests before promotion."
        if gate4["passed"]
        else "Do not retune nearby SEC Item 5.02 after-hours timing, trend/RS, "
        "or delayed-entry thresholds on this frozen sample; pivot to a "
        "different free-data candidate-pool mechanism or forward replacement rows."
    )
    return payload


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC After-Hours Item 5.02 Leadership Candidate Pool",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        base._window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Rule",
            "",
            (
                "Select PIT-safe SEC 8-K feature rows with Item 5.02, exclude "
                "earnings, financing, and auditor-change co-items, require "
                "`accepted_datetime` at or after 20:00, require first usable "
                f"trading-day close-location >= {base.MIN_SIGNAL_CLOSE_LOCATION}, "
                "and require nonnegative 20-day excess return versus SPY. "
                "Entry is delayed to the next open after that close is known."
            ),
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_020_sec_after_hours_5_02_leadership_candidate_pool.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    _apply_config()
    return _customize_payload(base.build_payload())


def main() -> int:
    _apply_config()
    payload = _customize_payload(base.build_payload())
    base.persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


_ORIGINAL_GATE4 = base._gate4


if __name__ == "__main__":
    raise SystemExit(main())
