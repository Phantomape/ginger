"""exp-20260511-022: Space non-data-vendor breakout risk sweep.

The accepted Space forward hypothesis is the official-catalyst operating
subpool at 0.75x risk, with exp-20260511-019 adding a PL/BKSY breakout-only
haircut and exp-20260511-021 adding an RKLB/ASTS trend top-up. This experiment
keeps that accepted stack fixed and changes one new variable: an extra risk
scalar for non-data-vendor Space breakout_long entries.
"""

from __future__ import annotations

import json
import math
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
    _append_jsonl_once,
    _append_once,
    _write_json,
)
from exp_20260511_018_space_data_vendor_trend_gate import (  # noqa: E402
    DATA_VENDOR_TICKERS,
)


EXPERIMENT_ID = "exp-20260511-022"
STEM = "space_non_data_vendor_breakout_risk"
BASE_SPACE_RISK_SCALAR = 0.75
DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.25
LAUNCH_CONNECTIVITY_TREND_TICKERS = ("RKLB", "ASTS")
LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
NON_DATA_VENDOR_BREAKOUT_SCALARS = (0.75, 0.5, 0.25)
MAX_DRAWDOWN_DAMAGE_VS_CORE = 0.02

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
CURRENT_STATE_MD = REPO_ROOT / "docs" / "current_state.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    marker: str,
) -> None:
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return

    new_shares = int(math.floor(old_shares * scalar))
    ratio = new_shares / old_shares if old_shares else 0.0
    old_risk_pct = float(sizing.get("risk_pct") or 0.0)
    old_risk_amount = float(
        sizing.get("risk_amount_usd") or (old_risk_pct * portfolio_value)
    )
    old_position_value = float(sizing.get("position_value_usd") or 0.0)

    sizing[f"{marker}_risk_scalar_applied"] = scalar
    sizing[f"{marker}_baseline_shares"] = old_shares
    sizing[f"{marker}_scaled_shares"] = new_shares
    sizing[f"{marker}_risk_pct_before_scalar"] = old_risk_pct
    sizing[f"{marker}_risk_amount_before_scalar"] = round(old_risk_amount, 2)
    sizing["shares_to_buy"] = new_shares
    sizing["risk_pct"] = old_risk_pct * ratio
    sizing["risk_amount_usd"] = round(old_risk_amount * ratio, 2)
    sizing["position_value_usd"] = round(old_position_value * ratio, 2)
    sizing["position_pct_of_portfolio"] = (
        round((old_position_value * ratio) / portfolio_value, 4)
        if portfolio_value
        else 0.0
    )


@contextmanager
def _patched_space_breakout_scalars(non_data_vendor_scalar: float):
    import portfolio_engine  # noqa: PLC0415

    original = portfolio_engine.size_signals
    official = {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS}
    data_vendors = {ticker.upper() for ticker in DATA_VENDOR_TICKERS}
    non_data_vendors = {
        ticker.upper()
        for ticker in OFFICIAL_CATALYST_TICKERS
        if ticker.upper() not in data_vendors
    }
    launch_connectivity = {
        ticker.upper() for ticker in LAUNCH_CONNECTIVITY_TREND_TICKERS
    }
    adjusted: list[dict[str, Any]] = []

    def wrapped(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            sizing = sig.get("sizing")
            if ticker not in official or not sizing:
                continue

            before_base = int(sizing.get("shares_to_buy") or 0)
            _scale_sizing(
                sizing,
                BASE_SPACE_RISK_SCALAR,
                portfolio_value,
                "space_official_base",
            )
            data_vendor_breakout = (
                ticker in data_vendors and strategy == "breakout_long"
            )
            launch_connectivity_trend = (
                ticker in launch_connectivity and strategy == "trend_long"
            )
            non_data_vendor_breakout = (
                ticker in non_data_vendors and strategy == "breakout_long"
            )

            if data_vendor_breakout:
                _scale_sizing(
                    sizing,
                    DATA_VENDOR_BREAKOUT_RISK_SCALAR,
                    portfolio_value,
                    "space_data_vendor_breakout",
                )
            if launch_connectivity_trend:
                _scale_sizing(
                    sizing,
                    LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR,
                    portfolio_value,
                    "space_launch_connectivity_trend",
                )
            if non_data_vendor_breakout and non_data_vendor_scalar != 1.0:
                _scale_sizing(
                    sizing,
                    non_data_vendor_scalar,
                    portfolio_value,
                    "space_non_data_vendor_breakout",
                )

            if data_vendor_breakout or launch_connectivity_trend or non_data_vendor_breakout:
                adjusted.append(
                    {
                        "ticker": ticker,
                        "cohort": (
                            "data_vendor_breakout"
                            if data_vendor_breakout
                            else "launch_connectivity_trend"
                            if launch_connectivity_trend
                            else "non_data_vendor_breakout"
                        ),
                        "strategy": strategy,
                        "entry_price": _round(sig.get("entry_price"), 4),
                        "base_space_scalar": BASE_SPACE_RISK_SCALAR,
                        "data_vendor_breakout_scalar": (
                            DATA_VENDOR_BREAKOUT_RISK_SCALAR
                            if data_vendor_breakout
                            else None
                        ),
                        "launch_connectivity_trend_scalar": (
                            LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
                            if launch_connectivity_trend
                            else None
                        ),
                        "non_data_vendor_breakout_scalar": (
                            non_data_vendor_scalar
                            if non_data_vendor_breakout
                            else None
                        ),
                        "shares_before_space_scalars": before_base,
                        "shares_after_space_scalars": int(
                            sizing.get("shares_to_buy") or 0
                        ),
                        "trade_quality_score": _round(
                            sig.get("trade_quality_score"),
                            4,
                        ),
                        "confidence_score": _round(sig.get("confidence_score"), 4),
                    }
                )
        return sized

    portfolio_engine.size_signals = wrapped
    try:
        yield adjusted
    finally:
        portfolio_engine.size_signals = original


def _run_variant(
    label: str,
    spec: dict[str, str],
    core_universe: list[str],
    included: list[str],
    non_data_vendor_scalar: float,
) -> dict[str, Any]:
    candidate_universe = sorted(set(core_universe) | set(included))
    with _patched_space_breakout_scalars(non_data_vendor_scalar) as adjusted:
        result = _run_window(
            label,
            spec,
            candidate_universe,
            spec["candidate_snapshot"],
        )
    result["space_breakout_adjustments"] = adjusted
    return result


def _adjustment_summary(adjusted: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker = Counter(row["ticker"] for row in adjusted)
    by_cohort = Counter(row["cohort"] for row in adjusted)
    return {
        "adjusted_signal_count": len(adjusted),
        "adjusted_by_ticker": dict(sorted(by_ticker.items())),
        "adjusted_by_cohort": dict(sorted(by_cohort.items())),
        "sample_adjusted": adjusted[:16],
    }


def _refinement_gate(
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
    after_agg: dict[str, Any],
    delta_vs_before: dict[str, dict[str, Any]],
    delta_vs_core: dict[str, dict[str, Any]],
    after_space_attr: dict[str, Any],
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
        and max_dd_change_vs_before <= 0.005
        and after_agg.get("min_survival_rate", 0.0) >= 0.05
        and (
            after_space_attr["single_ticker_positive_share"] is None
            or after_space_attr["single_ticker_positive_share"] <= 0.70
        )
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
    }


def _build_variant(
    scalar: float,
    core_universe: list[str],
    core_by_window: dict[str, dict[str, Any]],
    before_by_window: dict[str, dict[str, Any]],
    included_by_window: dict[str, list[str]],
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, spec in WINDOWS.items():
        included = included_by_window[label]
        after = _run_variant(label, spec, core_universe, included, scalar)
        before = before_by_window[label]
        core = core_by_window[label]
        by_window[label] = {
            "window": spec,
            "included_space_tickers": included,
            "data_vendor_tickers": sorted(set(DATA_VENDOR_TICKERS) & set(included)),
            "non_data_vendor_tickers": sorted(
                (set(OFFICIAL_CATALYST_TICKERS) - set(DATA_VENDOR_TICKERS))
                & set(included)
            ),
            "core_metrics": core["metrics"],
            "before_metrics": before["metrics"],
            "after_metrics": after["metrics"],
            "delta_vs_core": _delta(after["metrics"], core["metrics"]),
            "delta_vs_before": _delta(after["metrics"], before["metrics"]),
            "before_space_trade_attribution": _space_trade_attribution(
                before["trades"],
                set(included),
            ),
            "after_space_trade_attribution": _space_trade_attribution(
                after["trades"],
                set(included),
            ),
            "space_breakout_risk_adjustment": _adjustment_summary(
                after["space_breakout_adjustments"]
            ),
        }

    after_metrics = {label: row["after_metrics"] for label, row in by_window.items()}
    delta_vs_before = {
        label: row["delta_vs_before"] for label, row in by_window.items()
    }
    delta_vs_core = {label: row["delta_vs_core"] for label, row in by_window.items()}
    after_agg = _aggregate(after_metrics)
    after_space_attr = _aggregate_space_attr(
        {
            label: {
                "space_trade_attribution": row["after_space_trade_attribution"]
            }
            for label, row in by_window.items()
        }
    )
    return {
        "non_data_vendor_breakout_scalar": scalar,
        "by_window": by_window,
        "after_metrics": after_metrics,
        "after_aggregate": after_agg,
        "delta_vs_before": delta_vs_before,
        "delta_vs_core": delta_vs_core,
        "space_trade_attribution": after_space_attr,
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
        core_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        before_by_window[label] = _run_variant(
            label,
            spec,
            core_universe,
            included,
            non_data_vendor_scalar=1.0,
        )

    core_metrics = {label: row["metrics"] for label, row in core_by_window.items()}
    before_metrics = {
        label: row["metrics"] for label, row in before_by_window.items()
    }
    core_agg = _aggregate(core_metrics)
    before_agg = _aggregate(before_metrics)

    variants: dict[str, dict[str, Any]] = {}
    for scalar in NON_DATA_VENDOR_BREAKOUT_SCALARS:
        variant = _build_variant(
            scalar,
            core_universe,
            core_by_window,
            before_by_window,
            included_by_window,
        )
        gate = _refinement_gate(
            core_agg,
            before_agg,
            variant["after_aggregate"],
            variant["delta_vs_before"],
            variant["delta_vs_core"],
            variant["space_trade_attribution"],
        )
        variant["gate"] = gate
        variants[str(scalar)] = variant

    best = max(
        variants.values(),
        key=lambda row: (
            row["gate"]["passed"],
            row["gate"]["aggregate_delta_vs_before"].get(
                "expected_value_score_sum",
                -999.0,
            ),
            row["gate"]["aggregate_delta_vs_before"].get("total_pnl_sum", -999999.0),
        ),
    )
    delta_metrics = {
        "aggregate_vs_before": best["gate"]["aggregate_delta_vs_before"],
        "aggregate_vs_core": best["gate"]["aggregate_delta_vs_core"],
        "by_window_vs_before": best["delta_vs_before"],
        "by_window_vs_core": best["delta_vs_core"],
    }

    if best["gate"]["passed"]:
        decision = "accepted_default_off_non_data_vendor_breakout_risk_haircut"
        rejection_reason = None
        interpretation = (
            "The non-data-vendor breakout cohort has enough repeatable evidence "
            "for a default-off forward risk-scalar hypothesis, layered after the "
            "accepted PL/BKSY breakout haircut and RKLB/ASTS trend top-up."
        )
    else:
        decision = "rejected_non_data_vendor_breakout_risk_haircut"
        rejection_reason = (
            "No tested non-data-vendor breakout scalar cleared the refinement "
            "gate versus the accepted Space sleeve plus PL/BKSY breakout haircut "
            "and RKLB/ASTS trend top-up."
        )
        interpretation = (
            "Do not haircut non-data-vendor Space breakouts on this frozen "
            "sample. The accepted data-vendor haircut is not transferable to "
            "RKLB/ASTS/RDW/LUNR-style breakout entries without stronger "
            "forward evidence."
        )

    open_position_audit = _open_position_field_audit()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "lane": "alpha_search",
        "hypothesis": (
            "risk allocation: after retaining the accepted official-catalyst "
            "Space 0.75x sleeve, PL/BKSY breakout haircut, and RKLB/ASTS "
            "trend top-up, non-data-vendor Space breakout_long entries may "
            "need their own risk scalar."
        ),
        "change_type": "risk_allocation",
        "changed_variable": "extra non-data-vendor Space breakout_long risk scalar",
        "parameters": {
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "fixed_data_vendor_breakout_risk_scalar": DATA_VENDOR_BREAKOUT_RISK_SCALAR,
            "fixed_launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "launch_connectivity_trend_tickers": list(
                LAUNCH_CONNECTIVITY_TREND_TICKERS
            ),
            "tested_non_data_vendor_breakout_scalars": list(
                NON_DATA_VENDOR_BREAKOUT_SCALARS
            ),
            "official_catalyst_tickers": list(OFFICIAL_CATALYST_TICKERS),
            "data_vendor_tickers": list(DATA_VENDOR_TICKERS),
            "non_data_vendor_tickers": sorted(
                set(OFFICIAL_CATALYST_TICKERS) - set(DATA_VENDOR_TICKERS)
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md standard three-window snapshot protocol",
            "windows": WINDOWS,
            "baseline": "core universe snapshots",
            "before_hypothesis": (
                "accepted Space official-catalyst 0.75x plus fixed PL/BKSY "
                "breakout 0.25x haircut from exp-20260511-019 and fixed "
                "RKLB/ASTS trend 1.25x top-up from exp-20260511-021"
            ),
        },
        "single_causal_variable": (
            "only the non-data-vendor breakout risk scalar changes; core filters, "
            "Space official-catalyst membership, base Space scalar, and PL/BKSY "
            "breakout plus RKLB/ASTS trend scalars stay fixed"
        ),
        "baseline_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": best["after_metrics"],
        "delta_metrics": delta_metrics,
        "expected_value_score_delta": best["gate"]["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "core_aggregate": core_agg,
        "before_aggregate": before_agg,
        "after_aggregate": best["after_aggregate"],
        "gate_questions": {
            "alpha_hypothesis": (
                "risk allocation: Space hardware/network/lunar breakout entries "
                "may have a different payoff distribution than PL/BKSY data-vendor "
                "breakouts and should be tested separately."
            ),
            "prior_similar_experiments": [
                "exp-20260511-011 accepted official-catalyst Space 0.75x default-off hypothesis.",
                "exp-20260511-018 rejected PL/BKSY data-vendor trend-only deletion.",
                "exp-20260511-019 accepted a PL/BKSY breakout-only risk haircut.",
                "exp-20260511-021 accepted an RKLB/ASTS trend-only risk top-up.",
                "No prior experiment tested a non-data-vendor Space breakout-only risk scalar.",
            ],
            "single_causal_variable": (
                "extra risk scalar for non-data-vendor Space breakout_long entries."
            ),
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus the accepted Space + "
                "PL/BKSY haircut + RKLB/ASTS trend-top-up hypothesis, improve "
                "at least 2/3 EV windows versus that before state, stay "
                "EV-positive in all windows versus core, keep drawdown damage "
                "versus core <= 2 pp, survival >= 5%, and keep Space "
                "positive-contribution concentration within guard."
            ),
            "reproducibility": (
                "This script reruns core, the accepted before state, and each "
                "non-data-vendor breakout scalar across the three docs/backtesting.md snapshots."
            ),
        },
        "gate_results": {
            "gate1": {
                "core_baseline_metrics": core_metrics,
                "before_hypothesis_metrics": before_metrics,
            },
            "gate2": open_position_audit,
            "gate3": {
                "new_filter_added": False,
                "scope": (
                    "Space official-catalyst breakout sizing only; signal "
                    "survival and core filters unchanged"
                ),
                "minimum_after_survival_rate": best["after_aggregate"].get(
                    "min_survival_rate"
                ),
                "passed": best["after_aggregate"].get("min_survival_rate", 0.0)
                >= 0.05,
            },
            "gate4": best["gate"],
        },
        "space_trade_attribution": best["space_trade_attribution"],
        "variants": variants,
        "best_variant": best,
        "by_window": best["by_window"],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking still lacks enough closed-decision forward "
                "samples. This tests deterministic risk allocation in a "
                "high-value Space subsegment instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "default_off_observation_only": True,
        },
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": [
            "If accepted later, promote through shared Space sleeve metadata/helper before any live adapter can consume it.",
            "If rejected, leave RKLB/ASTS/RDW/LUNR-style breakouts at the accepted base Space scalar.",
            "Continue separating Space evidence by data-vendor breakout, non-data-vendor breakout, and trend entries.",
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
        "interpretation": interpretation,
    }
    return payload


def _write_artifacts(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Space non-data-vendor breakout risk",
        "status": payload["decision"],
        "lane": "alpha_search",
        "single_causal_variable": payload["single_causal_variable"],
        "result": {
            "decision": payload["decision"],
            "best_scalar": payload["best_variant"][
                "non_data_vendor_breakout_scalar"
            ],
            "aggregate_ev_delta_vs_before": payload["delta_metrics"][
                "aggregate_vs_before"
            ].get("expected_value_score_sum"),
            "aggregate_pnl_delta_vs_before": payload["delta_metrics"][
                "aggregate_vs_before"
            ].get("total_pnl_sum"),
            "gate_passed": payload["gate_results"]["gate4"]["passed"],
        },
        "next_steps": payload["next_evidence_needed"],
        "created_at": payload["timestamp"],
    }
    _write_json(TICKET_JSON, ticket)
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    lines = [
        f"# {EXPERIMENT_ID} Space Non-Data-Vendor Breakout Risk",
        "",
        f"Decision: `{payload['decision']}`.",
        "Fixed before state: official-catalyst Space `0.75x` plus PL/BKSY "
        "`breakout_long` `0.25x` haircut plus RKLB/ASTS `trend_long` "
        "`1.25x` top-up.",
        f"Best non-data-vendor breakout scalar: `{payload['best_variant']['non_data_vendor_breakout_scalar']}`.",
        "",
        "## Sweep",
        "",
        "| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for scalar_key, row in payload["variants"].items():
        gate = row["gate"]
        lines.append(
            "| {scalar} | {gate_result} | {dev:+.4f} | {dpnl:+.2f} | {ddd:+.4f} | {evw}/3 |".format(
                scalar=scalar_key,
                gate_result="pass" if gate["passed"] else "fail",
                dev=gate["aggregate_delta_vs_before"].get(
                    "expected_value_score_sum",
                    0.0,
                ),
                dpnl=gate["aggregate_delta_vs_before"].get("total_pnl_sum", 0.0),
                ddd=gate["max_drawdown_worsening_vs_core"],
                evw=gate["windows_ev_improved_vs_before"],
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
                adjusted=row["space_breakout_risk_adjustment"][
                    "adjusted_signal_count"
                ],
            )
        )
    lines.extend(
        [
            "",
            "Gate 4: `{}`.".format(
                "passed" if payload["gate_results"]["gate4"]["passed"] else "failed"
            ),
            "",
            "Interpretation: " + payload["interpretation"],
            "",
            "Production impact: replay-only alpha search; no shared policy, "
            "run adapter, order, ranking, signal generation, or live sizing "
            "behavior changed.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")

    state_note = (
        f"\nLatest Space non-data-vendor breakout risk refinement: `{EXPERIMENT_ID}` "
        "swept an extra scalar for RKLB/ASTS/RDW/LUNR-style `breakout_long` "
        "entries while keeping the accepted PL/BKSY breakout haircut and "
        "RKLB/ASTS trend top-up fixed. "
        f"The best scalar was `{payload['best_variant']['non_data_vendor_breakout_scalar']}` "
        f"with decision `{payload['decision']}`: aggregate EV delta versus the "
        f"accepted Space + PL/BKSY haircut + RKLB/ASTS trend before state "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}`, "
        f"aggregate PnL delta `$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}`.\n"
    )
    _append_once(
        CURRENT_STATE_MD,
        f"Latest Space non-data-vendor breakout risk refinement: `{EXPERIMENT_ID}`",
        state_note,
    )

    playbook_note = (
        "\n### 2026-05-11 mechanism update: Space non-data-vendor breakout risk\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: after fixing the accepted PL/BKSY breakout haircut at `0.25x` "
        "and RKLB/ASTS trend top-up at `1.25x`, sweeping a separate "
        "RKLB/ASTS/RDW/LUNR-style breakout scalar produced "
        f"best scalar `{payload['best_variant']['non_data_vendor_breakout_scalar']}` "
        "with aggregate EV delta "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}` "
        f"and PnL `$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}` "
        "versus the accepted before state.\n\n"
        "Mechanism insight: do not transfer the data-vendor breakout haircut to "
        "non-data-vendor Space breakouts unless the cohort clears the same "
        "three-window EV/risk gate. Keep these cohorts separate in future "
        "risk-allocation searches.\n"
    )
    _append_once(
        PLAYBOOK_MD,
        "### 2026-05-11 mechanism update: Space non-data-vendor breakout risk",
        playbook_note,
    )


def main() -> None:
    payload = run_experiment()
    _write_artifacts(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "best_scalar": payload["best_variant"][
                    "non_data_vendor_breakout_scalar"
                ],
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
                "aggregate_delta_vs_before": payload["delta_metrics"][
                    "aggregate_vs_before"
                ],
                "aggregate_delta_vs_core": payload["delta_metrics"][
                    "aggregate_vs_core"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
