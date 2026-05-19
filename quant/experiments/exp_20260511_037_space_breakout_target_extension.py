"""exp-20260511-037: Space official-catalyst breakout target extension.

This alpha-search replay keeps the accepted exp-20260511-032 Space stack fixed
and changes one variable: the ATR target width for official-catalyst Space
``breakout_long`` entries. The hypothesis is that Space breakout winners may
need more exit convexity, while previous Space breakout work only tested risk
haircuts.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for path in (str(EXPERIMENTS_DIR), str(QUANT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from data_layer import get_universe  # noqa: E402
from exp_20260511_002_space_catalyst_static_pool_replay import (  # noqa: E402
    WINDOWS,
    _aggregate,
    _delta,
    _open_position_field_audit,
    _round,
    _snapshot_tickers,
)
from exp_20260511_009_space_static_pool_risk_scalar import (  # noqa: E402
    _run_window,
    _space_trade_attribution,
)
from exp_20260511_010_space_official_catalyst_subpool import (  # noqa: E402
    OFFICIAL_CATALYST_TICKERS,
    _aggregate_space_attr,
    _write_json,
)
from exp_20260511_032_space_trend_target_extension import (  # noqa: E402
    _append_or_replace_section,
    _patched_space_stack,
    _patched_space_trend_target,
    _upsert_jsonl_record,
)
from risk_engine import _retarget_signal_with_atr_mult  # noqa: E402


EXPERIMENT_ID = "exp-20260511-037"
STEM = "space_breakout_target_extension"
BASE_SPACE_RISK_SCALAR = 0.75
DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.1
LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
ACCEPTED_SPACE_TREND_TARGET_ATR_MULT = 5.0
SPACE_BREAKOUT_TARGET_ATR_MULTS = (4.5, 5.0, 6.0)
MAX_DRAWDOWN_DAMAGE_VS_CORE = 0.02
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = (
    REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
CURRENT_STATE_MD = REPO_ROOT / "docs" / "current_state.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"


@contextmanager
def _patched_space_breakout_target(target_mult: float, official_tickers: set[str]):
    import risk_engine  # noqa: PLC0415

    original = risk_engine.enrich_signals
    adjustments: list[dict[str, Any]] = []

    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            if ticker not in official_tickers or strategy != "breakout_long":
                continue
            atr = (features_dict.get(ticker) or {}).get("atr")
            if not atr or atr <= 0:
                continue
            old_target = sig.get("target_price")
            old_mult = sig.get("target_mult_used") or atr_target_mult
            retargeted = _retarget_signal_with_atr_mult(sig, atr, target_mult)
            retargeted["space_breakout_target_atr_mult_applied"] = target_mult
            retargeted["space_breakout_target_previous_mult"] = old_mult
            retargeted["space_breakout_target_previous_price"] = old_target
            sig.clear()
            sig.update(retargeted)
            adjustments.append(
                {
                    "ticker": ticker,
                    "strategy": strategy,
                    "target_mult": target_mult,
                    "previous_target_mult": _round(old_mult, 4),
                    "previous_target_price": _round(old_target, 4),
                    "target_price": _round(sig.get("target_price"), 4),
                    "trade_quality_score": _round(sig.get("trade_quality_score"), 4),
                    "confidence_score": _round(sig.get("confidence_score"), 4),
                }
            )
        return enriched

    risk_engine.enrich_signals = wrapped
    try:
        yield adjustments
    finally:
        risk_engine.enrich_signals = original


def _run_before_stack(
    label: str,
    spec: dict[str, str],
    universe: list[str],
) -> dict[str, Any]:
    with _patched_space_stack(DATA_VENDOR_BREAKOUT_RISK_SCALAR):
        with _patched_space_trend_target(
            ACCEPTED_SPACE_TREND_TARGET_ATR_MULT,
            {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS},
        ):
            return _run_window(label, spec, universe, spec["candidate_snapshot"])


def _run_after_variant(
    label: str,
    spec: dict[str, str],
    universe: list[str],
    target_mult: float,
) -> dict[str, Any]:
    with _patched_space_stack(DATA_VENDOR_BREAKOUT_RISK_SCALAR):
        with _patched_space_trend_target(
            ACCEPTED_SPACE_TREND_TARGET_ATR_MULT,
            {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS},
        ):
            with _patched_space_breakout_target(
                target_mult,
                {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS},
            ) as target_adjustments:
                result = _run_window(
                    label,
                    spec,
                    universe,
                    spec["candidate_snapshot"],
                )
    result["space_breakout_target_adjustments"] = target_adjustments
    return result


def _breakout_trade_attribution(
    trades: list[dict[str, Any]],
    tickers: set[str],
) -> dict[str, Any]:
    return _space_trade_attribution(
        [
            trade
            for trade in trades
            if str(trade.get("strategy") or "").lower() == "breakout_long"
        ],
        tickers,
    )


def _adjustment_summary(adjusted: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "adjusted_signal_count": len(adjusted),
        "adjusted_by_ticker": dict(
            sorted(Counter(row["ticker"] for row in adjusted).items())
        ),
        "sample_adjusted": adjusted[:18],
    }


def _gate(
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
    after_agg: dict[str, Any],
    delta_vs_before: dict[str, dict[str, Any]],
    delta_vs_core: dict[str, dict[str, Any]],
    breakout_attr: dict[str, Any],
    adjusted_signal_count: int,
) -> dict[str, Any]:
    agg_delta_vs_before = _delta(after_agg, before_agg)
    agg_delta_vs_core = _delta(after_agg, core_agg)
    ev_improved_vs_before = sum(
        1
        for delta in delta_vs_before.values()
        if delta.get("expected_value_score", 0.0) > 0
    )
    ev_regressed_vs_before = sum(
        1
        for delta in delta_vs_before.values()
        if delta.get("expected_value_score", 0.0) < 0
    )
    ev_improved_vs_core = sum(
        1
        for delta in delta_vs_core.values()
        if delta.get("expected_value_score", 0.0) > 0
    )
    max_dd_worsening_vs_core = max(
        delta.get("max_drawdown_pct", 0.0) for delta in delta_vs_core.values()
    )
    max_dd_change_vs_before = max(
        delta.get("max_drawdown_pct", 0.0) for delta in delta_vs_before.values()
    )
    passed = (
        agg_delta_vs_before.get("expected_value_score_sum", 0.0) > 0
        and agg_delta_vs_before.get("total_pnl_sum", 0.0) > 0
        and ev_improved_vs_before >= 2
        and ev_regressed_vs_before == 0
        and ev_improved_vs_core == len(WINDOWS)
        and max_dd_worsening_vs_core <= MAX_DRAWDOWN_DAMAGE_VS_CORE
        and max_dd_change_vs_before <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and after_agg.get("min_survival_rate", 0.0) >= 0.05
        and adjusted_signal_count > 0
        and breakout_attr.get("trade_count", 0) > 0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": agg_delta_vs_before,
        "aggregate_delta_vs_core": agg_delta_vs_core,
        "windows_ev_improved_vs_before": ev_improved_vs_before,
        "windows_ev_regressed_vs_before": ev_regressed_vs_before,
        "windows_ev_improved_vs_core": ev_improved_vs_core,
        "max_drawdown_worsening_vs_core": _round(max_dd_worsening_vs_core, 4),
        "max_drawdown_change_vs_before": _round(max_dd_change_vs_before, 4),
        "adjusted_signal_count": adjusted_signal_count,
    }


def _build_variant(
    target_mult: float,
    core_by_window: dict[str, dict[str, Any]],
    before_by_window: dict[str, dict[str, Any]],
    included_by_window: dict[str, list[str]],
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, spec in WINDOWS.items():
        included = included_by_window[label]
        universe = sorted(set(get_universe()) | set(included))
        after = _run_after_variant(label, spec, universe, target_mult)
        before = before_by_window[label]
        core = core_by_window[label]
        official_tickers = set(included)
        by_window[label] = {
            "window": spec,
            "included_space_tickers": included,
            "core_metrics": core["metrics"],
            "before_metrics": before["metrics"],
            "after_metrics": after["metrics"],
            "delta_vs_core": _delta(after["metrics"], core["metrics"]),
            "delta_vs_before": _delta(after["metrics"], before["metrics"]),
            "before_space_trade_attribution": _space_trade_attribution(
                before["trades"],
                official_tickers,
            ),
            "after_space_trade_attribution": _space_trade_attribution(
                after["trades"],
                official_tickers,
            ),
            "before_space_breakout_trade_attribution": _breakout_trade_attribution(
                before["trades"],
                official_tickers,
            ),
            "after_space_breakout_trade_attribution": _breakout_trade_attribution(
                after["trades"],
                official_tickers,
            ),
            "space_breakout_target_adjustment": _adjustment_summary(
                after["space_breakout_target_adjustments"]
            ),
        }

    after_metrics = {label: row["after_metrics"] for label, row in by_window.items()}
    delta_vs_before = {
        label: row["delta_vs_before"] for label, row in by_window.items()
    }
    delta_vs_core = {label: row["delta_vs_core"] for label, row in by_window.items()}
    after_agg = _aggregate(after_metrics)
    breakout_attr = _aggregate_space_attr(
        {
            label: {
                "space_trade_attribution": row[
                    "after_space_breakout_trade_attribution"
                ]
            }
            for label, row in by_window.items()
        }
    )
    space_attr = _aggregate_space_attr(
        {
            label: {
                "space_trade_attribution": row["after_space_trade_attribution"]
            }
            for label, row in by_window.items()
        }
    )
    adjusted_count = sum(
        row["space_breakout_target_adjustment"]["adjusted_signal_count"]
        for row in by_window.values()
    )
    gate = _gate(
        core_agg,
        before_agg,
        after_agg,
        delta_vs_before,
        delta_vs_core,
        breakout_attr,
        adjusted_count,
    )
    return {
        "space_breakout_target_atr_mult": target_mult,
        "after_metrics": after_metrics,
        "after_aggregate": after_agg,
        "delta_metrics": {
            "aggregate_vs_before": gate["aggregate_delta_vs_before"],
            "aggregate_vs_core": gate["aggregate_delta_vs_core"],
            "by_window_vs_before": delta_vs_before,
            "by_window_vs_core": delta_vs_core,
        },
        "gate": gate,
        "space_breakout_trade_attribution": breakout_attr,
        "space_trade_attribution": space_attr,
        "by_window": by_window,
    }


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})
    core_by_window: dict[str, dict[str, Any]] = {}
    before_by_window: dict[str, dict[str, Any]] = {}
    included_by_window: dict[str, list[str]] = {}

    for label, spec in WINDOWS.items():
        snapshot_tickers = _snapshot_tickers(REPO_ROOT / spec["candidate_snapshot"])
        included = sorted(set(OFFICIAL_CATALYST_TICKERS) & snapshot_tickers)
        included_by_window[label] = included
        space_universe = sorted(set(core_universe) | set(included))
        core_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        before_by_window[label] = _run_before_stack(label, spec, space_universe)

    core_metrics = {label: row["metrics"] for label, row in core_by_window.items()}
    before_metrics = {
        label: row["metrics"] for label, row in before_by_window.items()
    }
    core_agg = _aggregate(core_metrics)
    before_agg = _aggregate(before_metrics)

    variants = {
        str(target_mult): _build_variant(
            target_mult,
            core_by_window,
            before_by_window,
            included_by_window,
            core_agg,
            before_agg,
        )
        for target_mult in SPACE_BREAKOUT_TARGET_ATR_MULTS
    }
    passing = [row for row in variants.values() if row["gate"]["passed"]]
    if passing:
        best = max(
            passing,
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants.values(),
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )

    if best["gate"]["passed"]:
        decision = "accepted_default_off_space_breakout_target_extension"
        rejection_reason = None
        interpretation = (
            "Wider targets for official-catalyst Space breakouts improved the "
            "accepted default-off Space stack. Promotion must remain default-off "
            "metadata/helper only because live Space slots are zero."
        )
    else:
        decision = "rejected_space_breakout_target_extension"
        rejection_reason = (
            "No tested official-catalyst Space breakout target width cleared the "
            "three-window Gate 4 standard versus the accepted exp-20260511-032 "
            "Space stack."
        )
        interpretation = (
            "Space breakout convexity is not the next supported same-sample "
            "refinement. Keep the accepted trend target extension, PL/BKSY "
            "breakout haircut, and RKLB/ASTS trend top-up unchanged."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "exit alpha: official-catalyst Space breakout_long winners may be "
            "clipped by the generic 3.5 ATR target; a wider target could "
            "improve EV without adding noisy tickers or changing risk."
        ),
        "change_type": "exit_target_shadow_sweep",
        "changed_variable": "space_official_breakout_target_atr_mult",
        "single_causal_variable": "space_official_breakout_target_atr_mult",
        "parameters": {
            "before_hypothesis_source": "exp-20260511-032",
            "official_candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "data_vendor_breakout_risk_scalar": DATA_VENDOR_BREAKOUT_RISK_SCALAR,
            "launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "accepted_space_trend_target_atr_mult": (
                ACCEPTED_SPACE_TREND_TARGET_ATR_MULT
            ),
            "tested_space_breakout_target_atr_mults": list(
                SPACE_BREAKOUT_TARGET_ATR_MULTS
            ),
            "best_space_breakout_target_atr_mult": best[
                "space_breakout_target_atr_mult"
            ],
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "base Space risk scalar 0.75",
                "PL/BKSY breakout 0.1x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "official Space trend target 5 ATR",
                "core production universe",
                "signal generation",
                "entry filters",
                "ranking",
                "position sizing",
                "MAX_POSITIONS",
                "slot routing",
                "add-ons",
                "LLM/news replay",
                "live pilot slots",
            ],
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three-window fixed protocol. Core "
            "baseline uses canonical snapshots; before reproduces the accepted "
            "exp-20260511-032 Space stack; after changes only the Space "
            "official-catalyst breakout_long ATR target width."
        ),
        "core_baseline_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": best["after_metrics"],
        "delta_metrics": best["delta_metrics"],
        "expected_value_score_delta": best["gate"][
            "aggregate_delta_vs_before"
        ].get("expected_value_score_sum"),
        "core_aggregate": core_agg,
        "before_aggregate": before_agg,
        "after_aggregate": best["after_aggregate"],
        "gate_questions": {
            "alpha_hypothesis": (
                "exit: widen official-catalyst Space breakout_long ATR targets."
            ),
            "prior_similar_experiments": [
                "exp-20260511-019 accepted PL/BKSY breakout risk haircut.",
                "exp-20260511-022 rejected non-data-vendor breakout risk haircut.",
                "exp-20260511-028 rejected RKLB/ASTS breakout risk haircut.",
                "exp-20260511-032 accepted official-catalyst trend target extension.",
                "No prior Space experiment tested breakout-specific target-width exit convexity.",
            ],
            "single_causal_variable": (
                "Official-catalyst Space breakout_long target ATR multiple."
            ),
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp032, improve at least "
                "2/3 EV windows without EV regression versus exp032, stay "
                "EV-positive in all windows versus core, keep drawdown damage "
                "versus core <= 2 pp and versus exp032 <= 0.5 pp, and keep "
                "survival >= 5%."
            ),
            "reproducibility": (
                "This script reruns core, exp032-equivalent before, and each "
                "Space breakout target-width variant across the three fixed snapshots."
            ),
        },
        "gate_results": {
            "gate1": {
                "baseline_protocol": "docs/backtesting.md three fixed windows",
                "core_baseline_metrics": core_metrics,
                "before_metrics": before_metrics,
            },
            "gate2": {
                "rule_dependencies": [
                    "ticker",
                    "strategy",
                    "features_dict[ticker].atr",
                    "signal.entry_price",
                    "signal.stop_price",
                    "signal.target_price",
                    "operator_inputs/open_positions.json entry_date",
                    "operator_inputs/open_positions.json target_price",
                ],
                "open_position_field_audit": open_position_audit,
                "passed": open_position_audit.get("passed") is True,
            },
            "gate3": {
                "new_filter_added": False,
                "survival_rate_min_after": best["after_aggregate"][
                    "min_survival_rate"
                ],
                "survival_rate_floor": 0.05,
                "passed": best["after_aggregate"]["min_survival_rate"] >= 0.05,
            },
            "gate4": best["gate"],
        },
        "variants": variants,
        "best_variant": {
            "space_breakout_target_atr_mult": best[
                "space_breakout_target_atr_mult"
            ],
            "gate": best["gate"],
            "space_breakout_trade_attribution": best[
                "space_breakout_trade_attribution"
            ],
            "space_trade_attribution": best["space_trade_attribution"],
        },
        "by_window": best["by_window"],
        "interpretation": interpretation,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, do not retry nearby Space breakout target widths on "
            "the same frozen windows; wait for forward Space breakout "
            "replacement value or a genuinely new catalyst-quality field."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "Space event-state soft-ranking still lacks enough closed "
                "forward decisions; this tests deterministic breakout exit convexity."
            ),
        },
        "production_impact": {
            "shared_policy_changed": best["gate"]["passed"],
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": best["gate"]["passed"],
            "daily_report_metadata_changed": best["gate"]["passed"],
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "why_not_other_changes": (
            "LLM soft-ranking is sample-limited; broad static Space promotion, "
            "mature satcom breadth, Space theme ETF timing, and nearby breakout "
            "risk scalars were rejected. Breakout exit convexity is the remaining "
            "orthogonal deterministic Space alpha variable."
        ),
        "known_risks": [
            "Breakout target widening can turn quick winners into later stops.",
            "The Space candidate pool is still a static historical replay copy.",
            "Any positive result must become a shared default-off helper before production exposure.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return payload


def _write_artifact(payload: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} Space breakout target extension",
        "",
        f"- decision: {payload['decision']}",
        f"- changed_variable: {payload['changed_variable']}",
        "- before_state: exp-20260511-032 accepted Space stack",
        f"- best_space_breakout_target_atr_mult: {payload['best_variant']['space_breakout_target_atr_mult']}",
        f"- expected_value_score_delta_vs_before: {payload['expected_value_score_delta']}",
        f"- rejection_reason: {payload['rejection_reason']}",
        "",
        "## Sweep",
        "",
        "| Target ATR | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows | Adjusted signals |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for target_key, row in payload["variants"].items():
        gate = row["gate"]
        lines.append(
            "| {target} | {gate_result} | {dev:+.4f} | {dpnl:+.2f} | "
            "{ddd:+.4f} | {evw}/3 | {adjusted} |".format(
                target=target_key,
                gate_result="pass" if gate["passed"] else "fail",
                dev=gate["aggregate_delta_vs_before"].get(
                    "expected_value_score_sum",
                    0.0,
                ),
                dpnl=gate["aggregate_delta_vs_before"].get("total_pnl_sum", 0.0),
                ddd=gate["max_drawdown_worsening_vs_core"],
                evw=gate["windows_ev_improved_vs_before"],
                adjusted=gate["adjusted_signal_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Adjusted signals |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, row in payload["by_window"].items():
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {dev:+.4f} | "
            "{core_dev:+.4f} | {before_pnl:.2f} | {after_pnl:.2f} | {dpnl:+.2f} | "
            "{adjusted} |".format(
                label=label,
                before_ev=row["before_metrics"]["expected_value_score"],
                after_ev=row["after_metrics"]["expected_value_score"],
                dev=row["delta_vs_before"].get("expected_value_score", 0.0),
                core_dev=row["delta_vs_core"].get("expected_value_score", 0.0),
                before_pnl=row["before_metrics"]["total_pnl"],
                after_pnl=row["after_metrics"]["total_pnl"],
                dpnl=row["delta_vs_before"].get("total_pnl", 0.0),
                adjusted=row["space_breakout_target_adjustment"][
                    "adjusted_signal_count"
                ],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- core: {payload['core_aggregate']}",
            f"- before_exp032_stack: {payload['before_aggregate']}",
            f"- after_best: {payload['after_aggregate']}",
            f"- gate: {payload['best_variant']['gate']}",
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], ensure_ascii=False, sort_keys=True),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _write_records(payload: dict[str, Any]) -> None:
    log_record = {
        "timestamp": payload["timestamp"],
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
    }
    _upsert_jsonl_record(EXPERIMENT_LOG_JSONL, log_record)

    state_text = f"""

## {EXPERIMENT_ID} Space breakout target extension

- timestamp: {payload['timestamp']}
- lane: alpha_search
- decision: {payload['decision']}
- changed_variable: {payload['changed_variable']}
- best_space_breakout_target_atr_mult: {payload['best_variant']['space_breakout_target_atr_mult']}
- expected_value_score_delta_vs_before: {payload['expected_value_score_delta']}
- before_aggregate: {payload['before_aggregate']}
- after_aggregate: {payload['after_aggregate']}
- interpretation: {payload['interpretation']}
- production_impact: {payload['production_impact']}
- artifact: `{OUT_JSON.relative_to(REPO_ROOT)}`
"""
    _append_or_replace_section(
        CURRENT_STATE_MD,
        f"## {EXPERIMENT_ID} Space breakout target extension",
        state_text,
        next_heading_prefix="##",
    )

    playbook_text = f"""

### {EXPERIMENT_ID} Space breakout target extension

- Decision: {payload['decision']}.
- Tested variable: `{payload['changed_variable']}` on top of the accepted exp032 Space stack.
- Best breakout target ATR multiple: `{payload['best_variant']['space_breakout_target_atr_mult']}`.
- Aggregate EV delta vs exp032 stack: `{payload['expected_value_score_delta']}`.
- Interpretation: {payload['interpretation']}
- Anti-repeat: do not retry nearby Space breakout target widths on the same frozen windows without forward Space breakout replacement-value evidence.
"""
    _append_or_replace_section(
        PLAYBOOK_MD,
        f"### {EXPERIMENT_ID} Space breakout target extension",
        playbook_text,
        next_heading_prefix="###",
    )


def write_outputs(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "decision": payload["decision"],
        "best_variant": payload["best_variant"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "created_at": payload["timestamp"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _write_records(payload)


if __name__ == "__main__":
    result = run_experiment()
    write_outputs(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "best_variant": result["best_variant"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
