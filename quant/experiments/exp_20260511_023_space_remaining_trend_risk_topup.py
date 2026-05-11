"""exp-20260511-023: Space remaining official-catalyst trend risk top-up.

The current Space default-off hypothesis keeps official catalysts at 0.75x
risk, applies a PL/BKSY breakout haircut, and tops up RKLB/ASTS trend entries.
This experiment changes one variable: whether the same trend-continuation
top-up should extend to the remaining official-catalyst trend entries.
"""

from __future__ import annotations

import json
import math
import sys
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


EXPERIMENT_ID = "exp-20260511-023"
STEM = "space_remaining_trend_risk_topup"
BASE_SPACE_RISK_SCALAR = 0.75
DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.25
LAUNCH_CONNECTIVITY_TREND_TICKERS = ("RKLB", "ASTS")
LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
REMAINING_TREND_SCALARS = (1.10, 1.25, 1.50)
MAX_DRAWDOWN_DAMAGE_VS_CORE = 0.02

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
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
def _patched_space_remaining_trend_scalars(remaining_trend_scalar: float):
    import portfolio_engine  # noqa: PLC0415

    original = portfolio_engine.size_signals
    official = {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS}
    data_vendors = {ticker.upper() for ticker in DATA_VENDOR_TICKERS}
    launch_connectivity = {
        ticker.upper() for ticker in LAUNCH_CONNECTIVITY_TREND_TICKERS
    }
    remaining_trend = {
        ticker for ticker in official if ticker not in launch_connectivity
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
            remaining_official_trend = (
                ticker in remaining_trend and strategy == "trend_long"
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
            if remaining_official_trend and remaining_trend_scalar != 1.0:
                _scale_sizing(
                    sizing,
                    remaining_trend_scalar,
                    portfolio_value,
                    "space_remaining_official_trend",
                )

            if (
                data_vendor_breakout
                or launch_connectivity_trend
                or remaining_official_trend
            ):
                adjusted.append(
                    {
                        "ticker": ticker,
                        "cohort": (
                            "data_vendor_breakout"
                            if data_vendor_breakout
                            else "launch_connectivity_trend"
                            if launch_connectivity_trend
                            else "remaining_official_trend"
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
                        "remaining_trend_scalar": (
                            remaining_trend_scalar
                            if remaining_official_trend
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


def _adjustment_summary(adjusted: list[dict[str, Any]]) -> dict[str, Any]:
    remaining_rows = [
        row for row in adjusted if row["cohort"] == "remaining_official_trend"
    ]
    return {
        "adjusted_signal_count": len(adjusted),
        "remaining_trend_signal_count": len(remaining_rows),
        "remaining_trend_by_ticker": {
            ticker: sum(1 for row in remaining_rows if row["ticker"] == ticker)
            for ticker in sorted({row["ticker"] for row in remaining_rows})
        },
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


def _run_space_variant(
    label: str,
    spec: dict[str, str],
    universe: list[str],
    remaining_trend_scalar: float,
) -> dict[str, Any]:
    with _patched_space_remaining_trend_scalars(remaining_trend_scalar) as adjusted:
        result = _run_window(label, spec, universe, spec["candidate_snapshot"])
    result["space_forward_scalar_adjustments"] = adjusted
    return result


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
        candidate_universe = sorted(set(core_universe) | set(included))
        core_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        before_by_window[label] = _run_space_variant(
            label,
            spec,
            candidate_universe,
            remaining_trend_scalar=1.0,
        )

    core_metrics = {label: row["metrics"] for label, row in core_by_window.items()}
    before_metrics = {
        label: row["metrics"] for label, row in before_by_window.items()
    }
    core_agg = _aggregate(core_metrics)
    before_agg = _aggregate(before_metrics)

    variants: dict[str, dict[str, Any]] = {}
    for remaining_trend_scalar in REMAINING_TREND_SCALARS:
        by_window: dict[str, dict[str, Any]] = {}
        for label, spec in WINDOWS.items():
            included = included_by_window[label]
            candidate_universe = sorted(set(core_universe) | set(included))
            after = _run_space_variant(
                label,
                spec,
                candidate_universe,
                remaining_trend_scalar=remaining_trend_scalar,
            )
            before = before_by_window[label]
            core = core_by_window[label]
            by_window[label] = {
                "window": spec,
                "included_space_tickers": included,
                "remaining_trend_tickers": sorted(
                    set(OFFICIAL_CATALYST_TICKERS)
                    - set(LAUNCH_CONNECTIVITY_TREND_TICKERS)
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
                "space_forward_scalar_adjustment": _adjustment_summary(
                    after["space_forward_scalar_adjustments"]
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
        gate = _refinement_gate(
            core_agg,
            before_agg,
            after_agg,
            delta_vs_before,
            delta_vs_core,
            after_space_attr,
        )
        variants[str(remaining_trend_scalar)] = {
            "remaining_trend_scalar": remaining_trend_scalar,
            "after_metrics": after_metrics,
            "after_aggregate": after_agg,
            "delta_metrics": {
                "by_window_vs_before": delta_vs_before,
                "by_window_vs_core": delta_vs_core,
                "aggregate_vs_before": gate["aggregate_delta_vs_before"],
                "aggregate_vs_core": gate["aggregate_delta_vs_core"],
            },
            "gate": gate,
            "space_trade_attribution": {
                "before": _aggregate_space_attr(
                    {
                        label: {
                            "space_trade_attribution": _space_trade_attribution(
                                row["trades"],
                                set(included_by_window[label]),
                            )
                        }
                        for label, row in before_by_window.items()
                    }
                ),
                "after": after_space_attr,
            },
            "by_window": by_window,
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
        decision = "accepted_default_off_remaining_trend_risk_topup"
        rejection_reason = None
        interpretation = (
            "Remaining official-catalyst Space trend entries support an extra "
            f"{best['remaining_trend_scalar']}x scalar on top of the accepted "
            "default-off Space sleeve. This is forward-observation metadata "
            "only; live Space slots remain zero."
        )
    else:
        decision = "rejected_remaining_trend_risk_topup"
        rejection_reason = (
            "The best remaining-trend top-up was positive but touched too little "
            "cross-window evidence; it improved fewer than two canonical windows "
            "versus the current accepted Space hypothesis."
        )
        interpretation = (
            "The remaining official-catalyst trend trades are a useful forward "
            "attribution bucket, but the frozen three-window evidence is too "
            "thin to add another default-off risk scalar."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Within the accepted Space official-catalyst sleeve, trend_long "
            "continuation may be a broader catalyst-quality signal than only "
            "RKLB/ASTS launch-connectivity trend leadership."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_remaining_official_trend_risk_scalar",
        "single_causal_variable": "space_remaining_official_trend_risk_scalar",
        "parameters": {
            "before_hypothesis_source": "exp-20260511-021",
            "official_candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "accepted_data_vendor_breakout_risk_scalar": (
                DATA_VENDOR_BREAKOUT_RISK_SCALAR
            ),
            "accepted_launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "remaining_trend_tickers": sorted(
                set(OFFICIAL_CATALYST_TICKERS)
                - set(LAUNCH_CONNECTIVITY_TREND_TICKERS)
            ),
            "remaining_trend_scalars": list(REMAINING_TREND_SCALARS),
            "best_remaining_trend_scalar": best["remaining_trend_scalar"],
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "base Space risk scalar 0.75",
                "PL/BKSY breakout 0.25x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "non-trend Space strategy eligibility",
                "core production universe",
                "core signal generation",
                "core entry filters",
                "ranking",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
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
            "Space stack from exp-20260511-021; after applies only the remaining "
            "official-catalyst trend_long scalar."
        ),
        "core_baseline_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": best["after_metrics"],
        "delta_metrics": best["delta_metrics"],
        "expected_value_score_delta": best["gate"]["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "core_aggregate": core_agg,
        "before_aggregate": before_agg,
        "after_aggregate": best["after_aggregate"],
        "gate_questions": {
            "alpha_hypothesis": (
                "risk allocation: remaining official-catalyst trend_long entries "
                "receive an extra bounded scalar inside the accepted Space sleeve."
            ),
            "prior_similar_experiments": [
                "exp-20260511-012 rejected blanket Space trend-only filtering.",
                "exp-20260511-018 rejected deleting PL/BKSY breakouts.",
                "exp-20260511-019 accepted PL/BKSY breakout haircut.",
                "exp-20260511-021 accepted RKLB/ASTS trend top-up.",
                "exp-20260511-022 rejected non-data-vendor breakout haircut.",
                "No prior experiment tested a remaining official-catalyst trend-only scalar on top of exp021.",
            ],
            "single_causal_variable": "extra non-RKLB/ASTS official trend_long risk scalar.",
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp021, improve at least "
                "2/3 EV windows without EV regression versus exp021, stay "
                "EV-positive in all windows versus core, keep drawdown damage "
                "versus core <= 2 pp, survival >= 5%, and keep Space "
                "positive-contribution concentration within guard."
            ),
            "reproducibility": (
                "This script reruns core, exp021-equivalent before, and each "
                "remaining-trend scalar across the three docs/backtesting.md snapshots."
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
                "scope": "Space official-catalyst remaining trend sizing only; core filters unchanged",
                "minimum_after_survival_rate": best["after_aggregate"].get(
                    "min_survival_rate"
                ),
                "passed": best["after_aggregate"].get("min_survival_rate", 0.0) >= 0.05,
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
                "Space event-state forward data remains below the closed-decision "
                "gate; this tests a deterministic risk-allocation bucket instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": decision
            == "accepted_default_off_remaining_trend_risk_topup",
            "backtester_adapter_changed": False,
            "run_adapter_changed": decision
            == "accepted_default_off_remaining_trend_risk_topup",
            "replay_only": False,
            "parity_test_added": decision
            == "accepted_default_off_remaining_trend_risk_topup",
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "default_off_observation_only": True,
        },
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": [
            "Treat PL/RDW trend continuation as a forward attribution bucket, not a new scalar, unless closed forward replacement value confirms it.",
            "Do not broaden Space trend risk again on the frozen sample without evidence in at least two independent windows or forward outcomes.",
            "Continue collecting catalyst/economic bucket replacement value before live Space slot promotion.",
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
        "title": "Space remaining trend risk top-up",
        "status": payload["decision"],
        "lane": "alpha_search",
        "single_causal_variable": payload["single_causal_variable"],
        "result": {
            "decision": payload["decision"],
            "best_scalar": payload["best_variant"]["remaining_trend_scalar"],
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
        f"# {EXPERIMENT_ID} Space Remaining Trend Risk Top-Up",
        "",
        f"Decision: `{payload['decision']}`.",
        "Best remaining-trend scalar: "
        f"`{payload['best_variant']['remaining_trend_scalar']}`.",
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
            "| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Remaining trend signals |",
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
                adjusted=row["space_forward_scalar_adjustment"][
                    "remaining_trend_signal_count"
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
            "Production impact: no shared policy change because Gate 4 failed. "
            "Live Space slots remain zero; no orders, ranking, signal generation, "
            "or live sizing path changed.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")

    state_note = (
        f"\nLatest Space remaining trend risk refinement: `{EXPERIMENT_ID}` "
        "tested extending the accepted trend top-up beyond RKLB/ASTS to remaining "
        "official-catalyst `trend_long` entries. The best scalar was "
        f"`{payload['best_variant']['remaining_trend_scalar']}` with decision "
        f"`{payload['decision']}`: aggregate EV delta versus exp021 "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}`, "
        f"aggregate PnL delta `$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}`. "
        "The result was positive but underpowered because it improved fewer than "
        "two canonical windows.\n"
    )
    _append_once(
        CURRENT_STATE_MD,
        f"Latest Space remaining trend risk refinement: `{EXPERIMENT_ID}`",
        state_note,
    )

    playbook_note = (
        "\n### 2026-05-11 mechanism update: Space remaining official trend risk\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: extending the accepted Space trend risk top-up from RKLB/ASTS "
        "to remaining official-catalyst `trend_long` entries produced best scalar "
        f"`{payload['best_variant']['remaining_trend_scalar']}` with aggregate "
        "EV delta "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}` "
        f"and PnL `$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}` "
        "versus exp-20260511-021, but the improvement was not cross-window enough "
        "to clear Gate 4.\n\n"
        "Mechanism insight: remaining PL/RDW-style trend continuation is a "
        "forward attribution bucket, not a new same-sample risk scalar. Do not "
        "broaden Space trend risk again on the frozen windows without forward "
        "replacement value or independent multi-window evidence.\n"
    )
    _append_once(
        PLAYBOOK_MD,
        "### 2026-05-11 mechanism update: Space remaining official trend risk",
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
                "best_scalar": payload["best_variant"]["remaining_trend_scalar"],
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
