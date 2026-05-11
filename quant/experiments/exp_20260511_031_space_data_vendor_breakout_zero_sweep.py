"""exp-20260511-031: Space data-vendor breakout zero-risk sweep.

exp-20260511-019 accepted a PL/BKSY breakout risk haircut at 0.25x, but its
sweep did not include 0.0x or 0.1x. This experiment keeps the accepted
exp-20260511-021 Space stack fixed and changes one variable: the PL/BKSY
breakout_long risk scalar.
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
    _write_json,
)
from exp_20260511_018_space_data_vendor_trend_gate import (  # noqa: E402
    DATA_VENDOR_TICKERS,
)


EXPERIMENT_ID = "exp-20260511-031"
STEM = "space_data_vendor_breakout_zero_sweep"
BASE_SPACE_RISK_SCALAR = 0.75
ACCEPTED_DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.25
LAUNCH_CONNECTIVITY_TICKERS = ("RKLB", "ASTS")
LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
DATA_VENDOR_BREAKOUT_SCALARS = (0.0, 0.1, 0.25, 0.4)
MAX_DRAWDOWN_DAMAGE_VS_CORE = 0.02
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005

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


def _upsert_jsonl_record(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated: list[str] = []
    replaced = False
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            updated.append(line)
            continue
        if row.get("experiment_id") == payload["experiment_id"]:
            if not replaced:
                updated.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                replaced = True
            continue
        updated.append(line)
    if not replaced:
        updated.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _append_or_replace_section(
    path: Path,
    heading: str,
    section_text: str,
    *,
    next_heading_prefix: str,
) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if heading not in existing:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write(section_text)
        return

    start = existing.find(heading)
    line_start = existing.rfind("\n", 0, start)
    section_start = 0 if line_start == -1 else line_start + 1
    next_start = existing.find(f"\n{next_heading_prefix} ", start + len(heading))
    section_end = len(existing) if next_start == -1 else next_start + 1
    updated = existing[:section_start] + section_text.lstrip("\n") + existing[section_end:]
    path.write_text(updated, encoding="utf-8")


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    *,
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

    sizing[f"{marker}_scalar_applied"] = scalar
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
def _patched_space_stack(data_vendor_breakout_scalar: float):
    import portfolio_engine  # noqa: PLC0415

    original = portfolio_engine.size_signals
    official = {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS}
    data_vendors = {ticker.upper() for ticker in DATA_VENDOR_TICKERS}
    launch_connectivity = {ticker.upper() for ticker in LAUNCH_CONNECTIVITY_TICKERS}
    adjustments: list[dict[str, Any]] = []

    def wrapped(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            sizing = sig.get("sizing")
            if ticker not in official or not sizing:
                continue

            before_shares = int(sizing.get("shares_to_buy") or 0)
            _scale_sizing(
                sizing,
                BASE_SPACE_RISK_SCALAR,
                portfolio_value,
                marker="space_official_base_risk",
            )

            data_vendor_breakout = ticker in data_vendors and strategy == "breakout_long"
            launch_connectivity_trend = (
                ticker in launch_connectivity and strategy == "trend_long"
            )
            if data_vendor_breakout:
                _scale_sizing(
                    sizing,
                    data_vendor_breakout_scalar,
                    portfolio_value,
                    marker="space_data_vendor_breakout_risk",
                )
            if launch_connectivity_trend:
                _scale_sizing(
                    sizing,
                    LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR,
                    portfolio_value,
                    marker="space_launch_connectivity_trend_risk",
                )

            if data_vendor_breakout or launch_connectivity_trend:
                adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "marker": (
                            "data_vendor_breakout"
                            if data_vendor_breakout
                            else "launch_connectivity_trend"
                        ),
                        "data_vendor_breakout_scalar": (
                            data_vendor_breakout_scalar
                            if data_vendor_breakout
                            else None
                        ),
                        "shares_before_space_scalars": before_shares,
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
        yield adjustments
    finally:
        portfolio_engine.size_signals = original


def _run_space_variant(
    label: str,
    spec: dict[str, str],
    core_universe: list[str],
    included: list[str],
    data_vendor_breakout_scalar: float,
) -> dict[str, Any]:
    universe = sorted(set(core_universe) | set(included))
    with _patched_space_stack(data_vendor_breakout_scalar) as adjustments:
        result = _run_window(label, spec, universe, spec["candidate_snapshot"])
    result["space_stack_adjustments"] = adjustments
    return result


def _adjustment_summary(adjusted: list[dict[str, Any]]) -> dict[str, Any]:
    data_rows = [row for row in adjusted if row["marker"] == "data_vendor_breakout"]
    return {
        "adjusted_signal_count": len(adjusted),
        "data_vendor_breakout_signal_count": len(data_rows),
        "data_vendor_breakout_by_ticker": dict(
            sorted(Counter(row["ticker"] for row in data_rows).items())
        ),
        "adjusted_by_marker": dict(
            sorted(Counter(row["marker"] for row in adjusted).items())
        ),
        "sample_adjusted": adjusted[:18],
    }


def _gate(
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
    after_agg: dict[str, Any],
    delta_vs_before: dict[str, dict[str, Any]],
    delta_vs_core: dict[str, dict[str, Any]],
    data_vendor_attr: dict[str, Any],
    data_vendor_adjusted_count: int,
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
        and data_vendor_adjusted_count > 0
        and data_vendor_attr.get("trade_count", 0) > 0
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
        "data_vendor_adjusted_signal_count": data_vendor_adjusted_count,
    }


def _build_variant(
    scalar: float,
    core_universe: list[str],
    core_by_window: dict[str, dict[str, Any]],
    before_by_window: dict[str, dict[str, Any]],
    included_by_window: dict[str, list[str]],
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    data_vendor_tickers = {ticker.upper() for ticker in DATA_VENDOR_TICKERS}
    for label, spec in WINDOWS.items():
        included = included_by_window[label]
        after = _run_space_variant(label, spec, core_universe, included, scalar)
        before = before_by_window[label]
        core = core_by_window[label]
        data_vendor_trade_tickers = data_vendor_tickers & set(included)
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
                set(included),
            ),
            "after_space_trade_attribution": _space_trade_attribution(
                after["trades"],
                set(included),
            ),
            "data_vendor_trade_attribution": _space_trade_attribution(
                after["trades"],
                data_vendor_trade_tickers,
            ),
            "space_stack_adjustment": _adjustment_summary(
                after["space_stack_adjustments"]
            ),
        }

    after_metrics = {label: row["after_metrics"] for label, row in by_window.items()}
    delta_vs_before = {
        label: row["delta_vs_before"] for label, row in by_window.items()
    }
    delta_vs_core = {label: row["delta_vs_core"] for label, row in by_window.items()}
    after_agg = _aggregate(after_metrics)
    data_vendor_attr = _aggregate_space_attr(
        {
            label: {
                "space_trade_attribution": row["data_vendor_trade_attribution"]
            }
            for label, row in by_window.items()
        }
    )
    space_attr = _aggregate_space_attr(
        {
            label: {"space_trade_attribution": row["after_space_trade_attribution"]}
            for label, row in by_window.items()
        }
    )
    data_vendor_adjusted_count = sum(
        row["space_stack_adjustment"]["data_vendor_breakout_signal_count"]
        for row in by_window.values()
    )
    gate = _gate(
        core_agg,
        before_agg,
        after_agg,
        delta_vs_before,
        delta_vs_core,
        data_vendor_attr,
        data_vendor_adjusted_count,
    )
    return {
        "data_vendor_breakout_risk_scalar": scalar,
        "after_metrics": after_metrics,
        "after_aggregate": after_agg,
        "delta_metrics": {
            "aggregate_vs_before": gate["aggregate_delta_vs_before"],
            "aggregate_vs_core": gate["aggregate_delta_vs_core"],
            "by_window_vs_before": delta_vs_before,
            "by_window_vs_core": delta_vs_core,
        },
        "gate": gate,
        "data_vendor_trade_attribution": data_vendor_attr,
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
        core_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        before_by_window[label] = _run_space_variant(
            label,
            spec,
            core_universe,
            included,
            ACCEPTED_DATA_VENDOR_BREAKOUT_RISK_SCALAR,
        )

    core_metrics = {label: row["metrics"] for label, row in core_by_window.items()}
    before_metrics = {
        label: row["metrics"] for label, row in before_by_window.items()
    }
    core_agg = _aggregate(core_metrics)
    before_agg = _aggregate(before_metrics)
    variants = {
        str(scalar): _build_variant(
            scalar,
            core_universe,
            core_by_window,
            before_by_window,
            included_by_window,
            core_agg,
            before_agg,
        )
        for scalar in DATA_VENDOR_BREAKOUT_SCALARS
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
        decision = "accepted_default_off_data_vendor_breakout_0_1_scalar"
        rejection_reason = None
        interpretation = (
            "A lower PL/BKSY breakout scalar improved the accepted Space stack "
            "under the three-window gate. Promote only as default-off forward "
            "metadata because Space live slots remain zero."
        )
    else:
        decision = "rejected_data_vendor_breakout_zero_sweep"
        rejection_reason = (
            "No tested PL/BKSY breakout scalar below the accepted 0.25x cleared "
            "the three-window gate versus exp-20260511-021."
        )
        interpretation = (
            "Keep the accepted 0.25x PL/BKSY breakout haircut; do not move it "
            "to zero on this replay sample."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "risk allocation: the already accepted PL/BKSY data-vendor "
            "breakout haircut may still be too large; zero or near-zero risk "
            "could improve EV without changing Space candidate breadth."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_data_vendor_breakout_risk_scalar",
        "single_causal_variable": "space_data_vendor_breakout_risk_scalar",
        "parameters": {
            "before_hypothesis_source": "exp-20260511-021",
            "official_candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "accepted_data_vendor_breakout_risk_scalar": (
                ACCEPTED_DATA_VENDOR_BREAKOUT_RISK_SCALAR
            ),
            "accepted_launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "tested_data_vendor_breakout_risk_scalars": list(
                DATA_VENDOR_BREAKOUT_SCALARS
            ),
            "best_data_vendor_breakout_risk_scalar": best[
                "data_vendor_breakout_risk_scalar"
            ],
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "base Space risk scalar 0.75",
                "RKLB/ASTS trend 1.25x top-up",
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
            "exp-20260511-021 default-off Space stack; after changes only the "
            "PL/BKSY data-vendor breakout risk scalar."
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
                "risk allocation: test whether PL/BKSY breakout should be "
                "zero or near-zero risk rather than accepted 0.25x."
            ),
            "prior_similar_experiments": [
                "exp-20260511-019 accepted PL/BKSY breakout 0.25x over 0.5x/0.75x, but did not test 0.0x or 0.1x.",
                "exp-20260511-021 accepted RKLB/ASTS trend 1.25x on top of the PL/BKSY haircut.",
                "exp-20260511-028 rejected RKLB/ASTS breakout risk refinement, keeping this isolated to data vendors.",
            ],
            "single_causal_variable": (
                "PL/BKSY Space data-vendor breakout_long risk scalar."
            ),
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp021, improve at least "
                "2/3 EV windows without EV regression versus exp021, stay "
                "EV-positive in all windows versus core, keep drawdown damage "
                "versus core <= 2 pp and versus exp021 <= 0.5 pp, and keep "
                "survival >= 5%."
            ),
            "reproducibility": (
                "This script reruns core, exp021-equivalent before, and each "
                "PL/BKSY breakout scalar across the three fixed snapshots."
            ),
        },
        "gate_results": {
            "gate1": {
                "baseline_protocol": "docs/backtesting.md three fixed windows",
                "core_baseline_artifact": "data/backtest_results_*.json plus this experiment payload",
                "before_artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
                "known_bias": (
                    "Space candidate snapshots are frozen historical replay "
                    "copies built from a 2026-05-10 research universe; positive "
                    "results cannot directly promote production eligibility."
                ),
            },
            "gate2": {
                "rule_dependencies": [
                    "ticker",
                    "strategy",
                    "portfolio_engine.size_signals sizing payload",
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
            "data_vendor_breakout_risk_scalar": best[
                "data_vendor_breakout_risk_scalar"
            ],
            "gate": best["gate"],
            "data_vendor_trade_attribution": best[
                "data_vendor_trade_attribution"
            ],
            "space_trade_attribution": best["space_trade_attribution"],
        },
        "by_window": best["by_window"],
        "interpretation": interpretation,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Track forward Space shadow outcomes with PL/BKSY breakout at 0.1x "
            "default-off risk; do not create live slots without a separate "
            "promotion experiment."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "Space LLM/event-state soft ranking remains underpowered; this "
                "isolates a deterministic scalar with existing closed trades."
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
            "The theme ETF gate had no weak-signal coverage, mature satcom "
            "breadth was rejected, and this directly probes the strongest "
            "remaining supported Space mechanism without new ticker noise."
        ),
        "known_risks": [
            "PL/BKSY breakout evidence is still sparse.",
            "A 0.0x scalar is effectively no capital for this entry cohort and needs shared-policy parity before promotion.",
            "Candidate membership is static and selected after the historical windows.",
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
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space data-vendor breakout zero sweep",
        "",
        f"- decision: {payload['decision']}",
        f"- changed_variable: {payload['changed_variable']}",
        "- before_state: exp-20260511-021 accepted Space stack",
        f"- best_data_vendor_breakout_risk_scalar: {best['data_vendor_breakout_risk_scalar']}",
        f"- expected_value_score_delta_vs_before: {payload['expected_value_score_delta']}",
        f"- rejection_reason: {payload['rejection_reason']}",
        "",
        "## Sweep",
        "",
        "| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows | Data-vendor adjusted |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for scalar_key, row in payload["variants"].items():
        gate = row["gate"]
        lines.append(
            "| {scalar} | {gate_result} | {dev:+.4f} | {dpnl:+.2f} | "
            "{ddd:+.4f} | {evw}/3 | {adjusted} |".format(
                scalar=scalar_key,
                gate_result="pass" if gate["passed"] else "fail",
                dev=gate["aggregate_delta_vs_before"].get(
                    "expected_value_score_sum",
                    0.0,
                ),
                dpnl=gate["aggregate_delta_vs_before"].get("total_pnl_sum", 0.0),
                ddd=gate["max_drawdown_worsening_vs_core"],
                evw=gate["windows_ev_improved_vs_before"],
                adjusted=gate["data_vendor_adjusted_signal_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Data adjusted |",
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
                adjusted=row["space_stack_adjustment"][
                    "data_vendor_breakout_signal_count"
                ],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- core: {payload['core_aggregate']}",
            f"- before_exp021_stack: {payload['before_aggregate']}",
            f"- after_best: {payload['after_aggregate']}",
            f"- gate: {best['gate']}",
            f"- data_vendor_trade_attribution: {best['data_vendor_trade_attribution']}",
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


def _append_records(payload: dict[str, Any]) -> None:
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

## {EXPERIMENT_ID} Space data-vendor breakout zero sweep

- timestamp: {payload['timestamp']}
- lane: alpha_search
- decision: {payload['decision']}
- changed_variable: {payload['changed_variable']}
- best_data_vendor_breakout_risk_scalar: {payload['best_variant']['data_vendor_breakout_risk_scalar']}
- expected_value_score_delta_vs_before: {payload['expected_value_score_delta']}
- before_aggregate: {payload['before_aggregate']}
- after_aggregate: {payload['after_aggregate']}
- interpretation: {payload['interpretation']}
- production_impact: {payload['production_impact']}
- artifact: `{OUT_JSON.relative_to(REPO_ROOT)}`
"""
    _append_or_replace_section(
        CURRENT_STATE_MD,
        f"## {EXPERIMENT_ID} Space data-vendor breakout zero sweep",
        state_text,
        next_heading_prefix="##",
    )

    playbook_text = f"""

### {EXPERIMENT_ID} Space data-vendor breakout zero sweep

- Decision: {payload['decision']}.
- Tested variable: `{payload['changed_variable']}` below the accepted `0.25x` PL/BKSY breakout haircut.
- Best scalar: `{payload['best_variant']['data_vendor_breakout_risk_scalar']}`.
- Aggregate EV delta vs exp021 stack: `{payload['expected_value_score_delta']}`.
- Interpretation: {payload['interpretation']}
- Promotion rule: only change this if the shared policy constant, daily report metadata, and focused parity tests move together.
"""
    _append_or_replace_section(
        PLAYBOOK_MD,
        f"### {EXPERIMENT_ID} Space data-vendor breakout zero sweep",
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
    _append_records(payload)


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
