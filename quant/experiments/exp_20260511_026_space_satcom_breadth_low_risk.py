"""exp-20260511-026: Space mature-satcom breadth low-risk test.

This alpha-search replay tests one candidate-pool/risk variable on top of the
accepted default-off Space stack: whether a small risk budget for mature
satellite-communications operating names (IRDM/VSAT/SATS) adds durable
replacement value. GSAT stays excluded because prior attribution was negative
and the registry marks it as ungated connectivity narrative exposure.
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


EXPERIMENT_ID = "exp-20260511-026"
STEM = "space_satcom_breadth_low_risk"
BASE_SPACE_RISK_SCALAR = 0.75
DATA_VENDOR_TICKERS = ("PL", "BKSY")
DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.25
LAUNCH_CONNECTIVITY_TREND_TICKERS = ("RKLB", "ASTS")
LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
SATCOM_BREADTH_TICKERS = ("IRDM", "VSAT", "SATS")
SATCOM_BREADTH_RISK_SCALARS = (0.25, 0.5, 0.75)
EXCLUDED_SPACE_TICKERS = {
    "GSAT": "prior_static_pool_attribution_negative_and_no_official_forward_gate",
    "ARKX": "theme_beta_benchmark_not_operating_trade_candidate",
    "UFO": "theme_beta_benchmark_not_operating_trade_candidate",
    "SPCE": "quarantine_meme_dilution_execution_risk",
    "HAWK": "short_history_no_ohlcv_rows_in_frozen_snapshots",
}
MAX_DRAWDOWN_DAMAGE_VS_CORE = 0.02
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005

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
def _patched_space_stack(satcom_scalar: float):
    import portfolio_engine  # noqa: PLC0415

    original = portfolio_engine.size_signals
    official = {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS}
    data_vendors = {ticker.upper() for ticker in DATA_VENDOR_TICKERS}
    launch_connectivity = {
        ticker.upper() for ticker in LAUNCH_CONNECTIVITY_TREND_TICKERS
    }
    satcom = {ticker.upper() for ticker in SATCOM_BREADTH_TICKERS}
    adjustments: list[dict[str, Any]] = []

    def wrapped(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            sizing = sig.get("sizing")
            if not sizing:
                continue

            before_shares = int(sizing.get("shares_to_buy") or 0)
            marker: str | None = None
            if ticker in official:
                _scale_sizing(
                    sizing,
                    BASE_SPACE_RISK_SCALAR,
                    portfolio_value,
                    marker="space_official_base_risk",
                )
                if ticker in data_vendors and strategy == "breakout_long":
                    _scale_sizing(
                        sizing,
                        DATA_VENDOR_BREAKOUT_RISK_SCALAR,
                        portfolio_value,
                        marker="space_data_vendor_breakout_risk",
                    )
                    marker = "data_vendor_breakout"
                if ticker in launch_connectivity and strategy == "trend_long":
                    _scale_sizing(
                        sizing,
                        LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR,
                        portfolio_value,
                        marker="space_launch_connectivity_trend_risk",
                    )
                    marker = "launch_connectivity_trend"
            elif ticker in satcom:
                _scale_sizing(
                    sizing,
                    satcom_scalar,
                    portfolio_value,
                    marker="space_satcom_breadth_risk",
                )
                marker = "satcom_breadth"

            if marker is not None:
                adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "marker": marker,
                        "satcom_scalar": satcom_scalar if ticker in satcom else None,
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


def _adjustment_summary(adjusted: list[dict[str, Any]]) -> dict[str, Any]:
    satcom_rows = [row for row in adjusted if row["marker"] == "satcom_breadth"]
    return {
        "adjusted_signal_count": len(adjusted),
        "satcom_adjusted_signal_count": len(satcom_rows),
        "satcom_adjusted_by_ticker": {
            ticker: sum(1 for row in satcom_rows if row["ticker"] == ticker)
            for ticker in sorted({row["ticker"] for row in satcom_rows})
        },
        "sample_adjusted": adjusted[:18],
    }


def _run_space_variant(
    label: str,
    spec: dict[str, str],
    universe: list[str],
    snapshot: str,
    satcom_scalar: float,
) -> dict[str, Any]:
    with _patched_space_stack(satcom_scalar) as adjusted:
        result = _run_window(label, spec, universe, snapshot)
    result["space_stack_adjustments"] = adjusted
    return result


def _gate(
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
    after_agg: dict[str, Any],
    delta_vs_before: dict[str, dict[str, Any]],
    delta_vs_core: dict[str, dict[str, Any]],
    satcom_attr: dict[str, Any],
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
        and satcom_attr.get("trade_count", 0) > 0
        and (
            satcom_attr["single_ticker_positive_share"] is None
            or satcom_attr["single_ticker_positive_share"] <= 0.70
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


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})

    core_by_window: dict[str, dict[str, Any]] = {}
    before_by_window: dict[str, dict[str, Any]] = {}
    official_by_window: dict[str, list[str]] = {}
    satcom_by_window: dict[str, list[str]] = {}

    for label, spec in WINDOWS.items():
        snapshot_tickers = _snapshot_tickers(REPO_ROOT / spec["candidate_snapshot"])
        official = sorted(set(OFFICIAL_CATALYST_TICKERS) & snapshot_tickers)
        satcom = sorted(set(SATCOM_BREADTH_TICKERS) & snapshot_tickers)
        official_by_window[label] = official
        satcom_by_window[label] = satcom
        before_universe = sorted(set(core_universe) | set(official))
        core_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        before_by_window[label] = _run_space_variant(
            label,
            spec,
            before_universe,
            spec["candidate_snapshot"],
            satcom_scalar=0.0,
        )

    core_metrics = {label: row["metrics"] for label, row in core_by_window.items()}
    before_metrics = {
        label: row["metrics"] for label, row in before_by_window.items()
    }
    core_agg = _aggregate(core_metrics)
    before_agg = _aggregate(before_metrics)

    variants: dict[str, dict[str, Any]] = {}
    for satcom_scalar in SATCOM_BREADTH_RISK_SCALARS:
        by_window: dict[str, dict[str, Any]] = {}
        for label, spec in WINDOWS.items():
            official = official_by_window[label]
            satcom = satcom_by_window[label]
            after_universe = sorted(set(core_universe) | set(official) | set(satcom))
            after = _run_space_variant(
                label,
                spec,
                after_universe,
                spec["candidate_snapshot"],
                satcom_scalar=satcom_scalar,
            )
            before = before_by_window[label]
            core = core_by_window[label]
            space_tickers = set(official) | set(satcom)
            by_window[label] = {
                "window": spec,
                "included_official_space_tickers": official,
                "included_satcom_breadth_tickers": satcom,
                "excluded_space_tickers": EXCLUDED_SPACE_TICKERS,
                "core_metrics": core["metrics"],
                "before_metrics": before["metrics"],
                "after_metrics": after["metrics"],
                "delta_vs_core": _delta(after["metrics"], core["metrics"]),
                "delta_vs_before": _delta(after["metrics"], before["metrics"]),
                "before_space_trade_attribution": _space_trade_attribution(
                    before["trades"],
                    set(official),
                ),
                "after_space_trade_attribution": _space_trade_attribution(
                    after["trades"],
                    space_tickers,
                ),
                "satcom_trade_attribution": _space_trade_attribution(
                    after["trades"],
                    set(satcom),
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
        satcom_attr = _aggregate_space_attr(
            {
                label: {
                    "space_trade_attribution": row["satcom_trade_attribution"]
                }
                for label, row in by_window.items()
            }
        )
        after_space_attr = _aggregate_space_attr(
            {
                label: {
                    "space_trade_attribution": row["after_space_trade_attribution"]
                }
                for label, row in by_window.items()
            }
        )
        gate = _gate(
            core_agg,
            before_agg,
            after_agg,
            delta_vs_before,
            delta_vs_core,
            satcom_attr,
        )
        variants[str(satcom_scalar)] = {
            "satcom_breadth_risk_scalar": satcom_scalar,
            "after_metrics": after_metrics,
            "after_aggregate": after_agg,
            "delta_metrics": {
                "by_window_vs_before": delta_vs_before,
                "by_window_vs_core": delta_vs_core,
                "aggregate_vs_before": gate["aggregate_delta_vs_before"],
                "aggregate_vs_core": gate["aggregate_delta_vs_core"],
            },
            "gate": gate,
            "satcom_trade_attribution": satcom_attr,
            "space_trade_attribution": after_space_attr,
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
        decision = "observed_only_positive_satcom_breadth_not_promoted"
        rejection_reason = None
        interpretation = (
            "Low-risk mature-satcom breadth cleared the replay gate, but it is "
            "not promoted because candidate membership is still static and not "
            "tied to PIT official event states. Treat as a forward observation "
            "queue, not a production sizing change."
        )
    else:
        decision = "rejected_satcom_breadth_low_risk_extension"
        rejection_reason = (
            "No IRDM/VSAT/SATS risk scalar cleared the pre-registered "
            "three-window gate versus the accepted exp-20260511-021 Space "
            "forward stack."
        )
        interpretation = (
            "Space alpha should stay focused on the official-catalyst operating "
            "sleeve and the already accepted PL/BKSY and RKLB/ASTS risk "
            "refinements. Mature-satcom breadth is not strong enough to add "
            "without a future PIT event trigger."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "A bounded, low-risk mature-satcom extension (IRDM/VSAT/SATS) may "
            "add replacement value to the accepted default-off Space sleeve "
            "without repeating broad static Space pool drawdown damage."
        ),
        "change_type": "candidate_pool_risk_allocation_shadow_sweep",
        "changed_variable": "space_satcom_breadth_risk_scalar",
        "single_causal_variable": "space_satcom_breadth_risk_scalar",
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
            "satcom_breadth_tickers": list(SATCOM_BREADTH_TICKERS),
            "satcom_breadth_risk_scalars": list(SATCOM_BREADTH_RISK_SCALARS),
            "best_satcom_breadth_risk_scalar": best[
                "satcom_breadth_risk_scalar"
            ],
            "excluded_space_tickers": EXCLUDED_SPACE_TICKERS,
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "base Space risk scalar 0.75",
                "PL/BKSY breakout 0.25x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "GSAT exclusion",
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
            "exp-20260511-021 default-off Space stack; after adds only the "
            "IRDM/VSAT/SATS low-risk breadth scalar."
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
                "candidate pool / capital allocation: a limited mature-satcom "
                "extension receives a small risk scalar inside the Space replay."
            ),
            "prior_similar_experiments": [
                "exp-20260511-002 rejected broad static Space pool promotion despite positive PnL because drawdown worsened.",
                "exp-20260511-010/011 accepted official-catalyst subpool only as a default-off forward hypothesis.",
                "exp-20260511-019 accepted PL/BKSY breakout risk haircut.",
                "exp-20260511-021 accepted RKLB/ASTS trend risk top-up.",
                "No prior experiment tested IRDM/VSAT/SATS as a small-risk extension on top of exp021 while excluding GSAT.",
            ],
            "single_causal_variable": "IRDM/VSAT/SATS low-risk breadth scalar.",
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp021, improve at least "
                "2/3 EV windows without any EV-regressed window versus exp021, "
                "stay EV-positive in all windows versus core, keep drawdown "
                "damage versus core <= 2 pp and versus exp021 <= 0.5 pp, keep "
                "survival >= 5%, and avoid single-ticker concentration > 70%."
            ),
            "reproducibility": (
                "This script reruns core, exp021-equivalent before, and each "
                "IRDM/VSAT/SATS risk scalar across the three fixed snapshots."
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
                "open_position_field_audit": _open_position_field_audit(),
                "passed": _open_position_field_audit().get("passed") is True,
            },
            "gate3": {
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
            "satcom_breadth_risk_scalar": best["satcom_breadth_risk_scalar"],
            "gate": best["gate"],
            "satcom_trade_attribution": best["satcom_trade_attribution"],
            "space_trade_attribution": best["space_trade_attribution"],
        },
        "interpretation": interpretation,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "For mature satcom, require PIT official event-state triggers or "
            "forward shadow ledger evidence before re-testing production-sized "
            "candidate breadth."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited, and prior nearby Space "
            "risk/refinement tests already covered trend-only, PL/BKSY, RKLB/"
            "ASTS, non-data-vendor breakout, and remaining trend top-up. This "
            "test moves to a bounded candidate-pool question without adding "
            "unguarded noisy tickers."
        ),
        "known_risks": [
            "Candidate membership is static and selected after the historical windows.",
            "Mature satcom names may be macro/balance-sheet beta rather than event alpha.",
            "Replay-only positive evidence would still need a PIT event-state gate.",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "decision": decision,
        "best_variant": payload["best_variant"],
        "next_evidence_needed": payload["next_evidence_needed"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_records(payload)
    return payload


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space satcom breadth low-risk",
        "",
        f"- decision: {payload['decision']}",
        f"- hypothesis: {payload['hypothesis']}",
        f"- changed_variable: {payload['changed_variable']}",
        f"- best_satcom_breadth_risk_scalar: {best['satcom_breadth_risk_scalar']}",
        f"- expected_value_score_delta_vs_before: {payload['expected_value_score_delta']}",
        f"- rejection_reason: {payload['rejection_reason']}",
        "",
        "## Aggregate",
        "",
        f"- core: {payload['core_aggregate']}",
        f"- before_exp021_stack: {payload['before_aggregate']}",
        f"- after_best: {payload['after_aggregate']}",
        f"- gate: {best['gate']}",
        f"- satcom_trade_attribution: {best['satcom_trade_attribution']}",
        "",
        "## Window Deltas Vs Before",
        "",
    ]
    for label, delta in payload["delta_metrics"]["by_window_vs_before"].items():
        lines.append(f"- {label}: {delta}")
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], ensure_ascii=False, sort_keys=True),
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
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, log_record)

    state_text = f"""

## {EXPERIMENT_ID} Space satcom breadth low-risk

- timestamp: {payload['timestamp']}
- lane: alpha_search
- decision: {payload['decision']}
- changed_variable: {payload['changed_variable']}
- best_satcom_breadth_risk_scalar: {payload['best_variant']['satcom_breadth_risk_scalar']}
- expected_value_score_delta_vs_before: {payload['expected_value_score_delta']}
- before_aggregate: {payload['before_aggregate']}
- after_aggregate: {payload['after_aggregate']}
- interpretation: {payload['interpretation']}
- production_impact: {payload['production_impact']}
- artifact: `{OUT_JSON.relative_to(REPO_ROOT)}`
"""
    _append_once(CURRENT_STATE_MD, EXPERIMENT_ID, state_text)

    playbook_text = f"""

### {EXPERIMENT_ID} Space mature-satcom breadth low-risk

- Decision: {payload['decision']}.
- Tested variable: `{payload['changed_variable']}` for IRDM/VSAT/SATS, with GSAT excluded.
- Best scalar: `{payload['best_variant']['satcom_breadth_risk_scalar']}`.
- Aggregate EV delta vs exp021 stack: `{payload['expected_value_score_delta']}`.
- Interpretation: {payload['interpretation']}
- Do not retry mature-satcom breadth without PIT official event-state evidence or forward shadow-ledger support.
"""
    _append_once(PLAYBOOK_MD, EXPERIMENT_ID, playbook_text)


if __name__ == "__main__":
    result = run_experiment()
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
