"""exp-20260524-007: core breadth-alignment component top-up scout.

Alpha search. Tests one causal variable: a cap-aware 1.05x post-sizing
top-up for already-qualified non-ETF/non-Commodity core signals whose
entry-day cross-sectional ranking surface has low/balanced breadth alignment.

This is experiment-only. If it ever passes Gate 4, the component exposure and
sizing rule must move into shared production/backtest modules before any
order path changes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260523_013_core_canonical_leadership_risk_topup as base
import exp_20260524_003_core_relative_strength_component_band_topup as ranking_base


EXPERIMENT_ID = "exp-20260524-007"
STEM = "core_breadth_alignment_component_topup"
MULTIPLIER_KEY = "breadth_alignment_low_topup_applied"

BREADTH_ALIGNMENT_COMPONENT_MAX = 0.69
TOPUP_MULTIPLIER = 1.05

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                kept.append(line)
    kept.append(json.dumps(record, sort_keys=True, ensure_ascii=False))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        rank_map = ranking_base._ranking_context(features_dict or {})
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            rank_row = rank_map.get(ticker) or {}
            components = rank_row.get("alpha_score_components") or {}
            breadth_alignment = base._safe_float(components.get("breadth_alignment"))
            sector = sig.get("sector") or base.re.SECTOR_MAP.get(ticker, "Unknown")
            sig["alpha_score"] = rank_row.get("alpha_score")
            sig["alpha_score_components"] = components
            sig["alpha_score_rank_pct"] = rank_row.get("alpha_score_rank_pct")
            sig["alpha_score_bucket"] = rank_row.get("alpha_score_bucket")
            sig["breadth_alignment_component"] = breadth_alignment
            sig["breadth_alignment_low_state"] = (
                sig.get("strategy") in base.TARGET_STRATEGIES
                and sector not in base.EXCLUDED_SECTORS
                and breadth_alignment is not None
                and breadth_alignment <= BREADTH_ALIGNMENT_COMPONENT_MAX
            )
        return enriched

    return wrapped


def _apply_topup_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("breadth_alignment_low_state") is not True:
        return sig, None

    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return sig, None

    entry = base._safe_float(sizing.get("entry_price") or sig.get("entry_price"))
    portfolio_value = base._safe_float(sizing.get("portfolio_value_usd"))
    net_risk_per_share = base._safe_float(sizing.get("net_risk_per_share"))
    if not entry or not portfolio_value or not net_risk_per_share:
        return sig, None

    cap_pct = base._safe_float(
        sizing.get("max_position_pct_applied"),
        base.MAX_POSITION_PCT,
    )
    desired_shares = max(old_shares, int(math.floor(old_shares * multiplier)))
    cap_shares = int(math.floor((portfolio_value * cap_pct) / entry))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= old_shares:
        return sig, None

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    sizing["breadth_alignment_low_state"] = True
    sizing["breadth_alignment_component"] = sig.get("breadth_alignment_component")
    sizing["breadth_alignment_component_max"] = BREADTH_ALIGNMENT_COMPONENT_MAX
    sizing["breadth_alignment_low_baseline_shares"] = old_shares
    sizing["breadth_alignment_low_desired_shares"] = desired_shares
    sizing["breadth_alignment_low_cap_shares"] = cap_shares
    sizing["breadth_alignment_low_new_shares"] = new_shares
    sizing[MULTIPLIER_KEY] = multiplier
    sig = {**sig, "sizing": sizing}

    record = {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "baseline_shares": old_shares,
        "desired_shares": desired_shares,
        "cap_shares": cap_shares,
        "new_shares": new_shares,
        "multiplier": multiplier,
        "breadth_alignment_component": sig.get("breadth_alignment_component"),
        "alpha_score": sig.get("alpha_score"),
        "alpha_score_bucket": sig.get("alpha_score_bucket"),
        "alpha_score_rank_pct": sig.get("alpha_score_rank_pct"),
        "alpha_score_components": sig.get("alpha_score_components"),
        "trade_quality_score": sig.get("trade_quality_score"),
        "confidence_score": sig.get("confidence_score"),
        "existing_sizing_multipliers": {
            key: value
            for key, value in sizing.items()
            if key.endswith("_applied")
            and value not in (None, 1.0)
            and key != MULTIPLIER_KEY
        },
    }
    return sig, record


def _artifact(payload: dict[str, Any]) -> str:
    gate = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Gate 1-4",
        f"- Baseline EV: `{payload['before_metrics']['aggregate']['expected_value_score_sum']}`",
        f"- After EV: `{payload['after_metrics']['aggregate']['expected_value_score_sum']}`",
        f"- EV delta: `{payload['delta_metrics']['aggregate']['expected_value_score_sum']}`",
        f"- PnL delta: `${payload['delta_metrics']['aggregate']['total_pnl_sum']:,.2f}`",
        f"- Adjusted signals: `{gate['adjusted_signal_count']}`",
        f"- Changed trades: `{gate['changed_trade_count']}`",
        f"- EV-regressed windows: `{gate['regressed_windows']}`",
        f"- Max single-ticker positive share: `{gate['concentration']['max_single_positive_ticker_share']}`",
        f"- Gate 4 passed: `{gate['passed']}`",
        "",
        "## Window Deltas",
        "| window | EV | PnL | DD | survival |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, row in payload["delta_metrics"]["windows"].items():
        lines.append(
            f"| {label} | {row.get('expected_value_score')} | {row.get('total_pnl')} | {row.get('max_drawdown_pct')} | {row.get('survival_rate')} |"
        )
    lines.extend(
        [
            "",
            "## Closeout",
            payload["rejection_reason"],
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    original_multiplier_key = base.MULTIPLIER_KEY
    original_enrich_wrapper = base._make_enrich_wrapper
    original_apply = base._apply_topup_to_sizing
    original_variants = base.VARIANTS

    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._apply_topup_to_sizing = _apply_topup_to_sizing
    base.VARIANTS = {STEM: {"multiplier": TOPUP_MULTIPLIER}}
    try:
        field_check = base.field_helper._open_position_field_check()
        baseline_results = base._run_baseline()
        before_metrics = {
            label: base.core_helper._metrics(result)
            for label, result in baseline_results.items()
        }
        after_results, adjustments = base._run_variant(TOPUP_MULTIPLIER)
        after_metrics = {
            label: base.core_helper._metrics(result)
            for label, result in after_results.items()
        }
        gate4 = base.gate_helper._gate4(baseline_results, after_results, adjustments)
    finally:
        base.MULTIPLIER_KEY = original_multiplier_key
        base._make_enrich_wrapper = original_enrich_wrapper
        base._apply_topup_to_sizing = original_apply
        base.VARIANTS = original_variants

    delta_windows = {
        label: base.core_helper._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    passed = bool(gate4["passed"])
    decision = (
        "candidate_passed_requires_shared_policy_promotion"
        if passed
        else "rejected_failed_gate4"
    )
    rejection_reason = None
    if not passed:
        if not gate4["concentration"]["passed"]:
            rejection_reason = (
                "Best variant failed concentration guard: the positive "
                "incremental PnL was dominated by one ticker, so the component "
                "state is not production-promotable on this sample."
            )
        elif gate4["regressed_windows"]:
            rejection_reason = "Best variant failed Gate 4 due fixed-window EV regression."
        else:
            rejection_reason = "Best variant failed Gate 4 materiality/sample guard."

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Entry-day breadth_alignment from the production-computable "
            "cross-sectional ranking surface may identify already-qualified "
            "core stock signals that are supported without being over-crowded. "
            "A small cap-aware top-up tests that allocation edge without "
            "changing entries, exits, ranking, universe, news, or LLM logic."
        ),
        "change_summary": (
            "Experiment-only 1.05x post-sizing top-up for non-ETF/"
            "non-Commodity core signals with breadth_alignment <= 0.69."
        ),
        "change_type": "capital_allocation",
        "mechanism_family": "core_cross_sectional_ranking_component_allocation",
        "trial_family": "core_breadth_alignment_component_topup",
        "trial_variant_id": "breadth_alignment_low_topup_1050",
        "changed_variable": "breadth_alignment_low_post_sizing_multiplier",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260523-012",
            "exp-20260523-015",
            "exp-20260524-003",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_ranking_component_field",
        "component": (
            "quant/cross_sectional_ranking_surface.py, "
            "quant/market_state_bundle.py, quant/risk_engine.py, "
            "quant/portfolio_engine.py"
        ),
        "parameters": {
            "breadth_alignment_component_max": BREADTH_ALIGNMENT_COMPONENT_MAX,
            "target_strategies": sorted(base.TARGET_STRATEGIES),
            "excluded_sectors": sorted(base.EXCLUDED_SECTORS),
            "baseline_multiplier": 1.0,
            "selected_multiplier": TOPUP_MULTIPLIER,
        },
        "date_range": {
            "protocol": "docs/backtesting.md standard_three_window",
            "windows": {
                label: {
                    "start": window["start"],
                    "end": window["end"],
                    "snapshot": window["snapshot"],
                    "state_note": window["state_note"],
                }
                for label, window in base.WINDOWS.items()
            },
        },
        "before_metrics": {
            "windows": before_metrics,
            "aggregate": base.core_helper._aggregate(before_metrics),
        },
        "after_metrics": {
            "windows": after_metrics,
            "aggregate": base.core_helper._aggregate(after_metrics),
        },
        "delta_metrics": {
            "windows": delta_windows,
            "aggregate": base.core_helper._aggregate_delta(after_metrics, before_metrics),
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md standard three non-overlapping windows",
            "baseline_artifact": str(OUT_JSON),
            "baseline_metrics_readable": True,
        },
        "gate2": {
            "field_check": field_check,
            "rule_dependencies": [
                "OHLCV features through signal day",
                "market_state_bundle",
                "cross_sectional_ranking_surface rows",
                "alpha_score_components.breadth_alignment",
                "sector",
                "strategy",
                "sizing.shares_to_buy",
                "sizing.entry_price",
                "sizing.portfolio_value_usd",
                "sizing.net_risk_per_share",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "survival_rate_min_before": base.core_helper._aggregate(before_metrics)[
                "survival_rate_min"
            ],
            "survival_rate_min_after": base.core_helper._aggregate(after_metrics)[
                "survival_rate_min"
            ],
            "signals_generated_sum_before": base.core_helper._aggregate(before_metrics)[
                "signals_generated_sum"
            ],
            "signals_survived_sum_before": base.core_helper._aggregate(before_metrics)[
                "signals_survived_sum"
            ],
            "signals_generated_sum_after": base.core_helper._aggregate(after_metrics)[
                "signals_generated_sum"
            ],
            "signals_survived_sum_after": base.core_helper._aggregate(after_metrics)[
                "signals_survived_sum"
            ],
        },
        "gate4": gate4,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_accepted": (
                "Move breadth_alignment component exposure and sizing policy "
                "into shared daily context/risk/portfolio modules with parity "
                "tests, then rerun the same three-window protocol."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "risk allocation: low/balanced breadth_alignment may mark "
                "less crowded already-qualified core entries."
            ),
            "2_history_check": (
                "exp-20260523-012 created PIT component coverage; "
                "exp-20260523-015 rejected top-level alpha_score; "
                "exp-20260524-003 rejected relative_strength component band."
            ),
            "3_single_causal_variable": (
                "post-sizing multiplier for breadth_alignment <= 0.69"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md canonical three-window Gate 1-4; require "
                "positive aggregate EV/PnL, no risk/survival deterioration, "
                "adequate sample, and concentration guard pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260524_007_core_breadth_alignment_component_topup.py"
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry adjacent breadth-alignment component multipliers on the frozen sample without new forward evidence or a different component interaction.",
            "If breadth context is revisited, first seek replacement-value or concentration evidence rather than another raw component scalar.",
        ],
        "related_files": [
            "quant/experiments/exp_20260524_007_core_breadth_alignment_component_topup.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
    }

    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "aggregate_delta": result["delta_metrics"]["aggregate"],
                "gate4_passed": result["gate4"]["passed"],
                "artifact": str(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )
