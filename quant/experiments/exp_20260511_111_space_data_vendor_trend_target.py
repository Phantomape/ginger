"""exp-20260511-111: Space data-vendor trend target width.

Tests whether PL/BKSY data-vendor trend_long signals deserve a wider target
inside the accepted default-off Space stack. Everything else stays locked:
official candidate pool, base risk, PL/BKSY breakout haircut, RKLB/ASTS trend
risk and target, ranking, add-ons, LLM/news replay, and live slots.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ID = "exp-20260511-111"
STEM = "space_data_vendor_trend_target"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
EXPERIMENT_DIR = PROJECT_ROOT / "quant" / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402
import risk_engine  # noqa: E402

from exp_20260511_110_space_breakout_stop_width import (  # noqa: E402
    BASE_SPACE_RISK_SCALAR,
    DATA_VENDOR_BREAKOUT_RISK_SCALAR,
    DATA_VENDOR_TICKERS,
    LAUNCH_CONNECTIVITY_TICKERS,
    LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR,
    LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT,
    OFFICIAL_SPACE_TICKERS,
    WINDOWS,
    _aggregate,
    _aggregate_delta,
    _delta,
    _gate2_open_positions,
    _metrics,
    _round,
    _restop_signal_with_atr_mult,
    _safe,
    _space_trade_attribution,
    _write_json,
)


logging.basicConfig(level=logging.WARNING)

BASE_SPACE_TREND_TARGET_ATR_MULT = 5.0

VARIANTS = {
    "accepted_exp105_stack": {
        "description": (
            "accepted exp-20260511-105 semantics: PL/BKSY trend_long keeps "
            "the broad official Space 5 ATR target"
        ),
        "data_vendor_trend_target_atr_mult": 5.0,
    },
    "data_vendor_trend_target_6_0": {
        "description": (
            "only PL/BKSY data-vendor trend_long signals use a 6 ATR target; "
            "all accepted Space risk scalars and other targets remain locked"
        ),
        "data_vendor_trend_target_atr_mult": 6.0,
    },
    "data_vendor_trend_target_7_0": {
        "description": (
            "only PL/BKSY data-vendor trend_long signals use a 7 ATR target; "
            "all accepted Space risk scalars and other targets remain locked"
        ),
        "data_vendor_trend_target_atr_mult": 7.0,
    },
}


def _append_jsonl_once(path: Path, payload: dict) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _install_space_policy(data_vendor_trend_target_mult: float):
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals

    def enrich_wrapper(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        adjusted = []
        for signal in enriched:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            features = features_dict.get(ticker) or {}
            atr = features.get("atr")
            if ticker in OFFICIAL_SPACE_TICKERS and strategy == "trend_long" and atr:
                target_mult = BASE_SPACE_TREND_TARGET_ATR_MULT
                if ticker in LAUNCH_CONNECTIVITY_TICKERS:
                    target_mult = LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
                if ticker in DATA_VENDOR_TICKERS:
                    target_mult = data_vendor_trend_target_mult
                updated = risk_engine._retarget_signal_with_atr_mult(
                    signal,
                    atr,
                    target_mult,
                )
                updated["space_trend_target_scope"] = (
                    "data_vendor_trend_target_test"
                    if ticker in DATA_VENDOR_TICKERS
                    else "accepted_exp105_target_semantics"
                )
                updated["space_trend_target_atr_mult"] = target_mult
                adjusted.append(updated)
            elif (
                ticker in OFFICIAL_SPACE_TICKERS
                and strategy == "breakout_long"
                and atr
            ):
                updated = _restop_signal_with_atr_mult(signal, float(atr), 1.5)
                updated["space_breakout_stop_scope"] = (
                    "accepted_exp105_stop_semantics"
                )
                adjusted.append(updated)
            else:
                adjusted.append(signal)
        return adjusted

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = original_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in OFFICIAL_SPACE_TICKERS and sizing:
                scalar = BASE_SPACE_RISK_SCALAR
                if ticker in DATA_VENDOR_TICKERS and strategy == "breakout_long":
                    scalar *= DATA_VENDOR_BREAKOUT_RISK_SCALAR
                if (
                    ticker in LAUNCH_CONNECTIVITY_TICKERS
                    and strategy == "trend_long"
                ):
                    scalar *= LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
                old_shares = int(sizing.get("shares_to_buy") or 0)
                new_shares = int(math.floor(old_shares * scalar))
                entry = float(signal.get("entry_price") or sizing.get("entry_price") or 0)
                net_risk = float(sizing.get("net_risk_per_share") or 0)
                sizing["space_base_risk_scalar_applied"] = BASE_SPACE_RISK_SCALAR
                sizing["space_extra_risk_scalar_applied"] = _round(
                    scalar / BASE_SPACE_RISK_SCALAR,
                    6,
                )
                sizing["space_effective_risk_scalar_applied"] = _round(scalar, 6)
                sizing["space_shares_before_scalar"] = old_shares
                sizing["shares_to_buy"] = new_shares
                sizing["position_value_usd"] = _round(new_shares * entry, 2)
                sizing["position_pct_of_portfolio"] = _round(
                    (new_shares * entry) / portfolio_value
                    if portfolio_value else 0,
                    4,
                )
                sizing["risk_amount_usd"] = _round(new_shares * net_risk, 2)
                sizing["risk_pct"] = (
                    (new_shares * net_risk) / portfolio_value
                    if portfolio_value else 0
                )
                signal = {**signal, "sizing": sizing}
            out.append(signal)
        return out

    risk_engine.enrich_signals = enrich_wrapper
    portfolio_engine.size_signals = size_wrapper
    return original_enrich, original_size


def _restore_policy(original_enrich, original_size):
    risk_engine.enrich_signals = original_enrich
    portfolio_engine.size_signals = original_size


def _run_window(window: dict, universe: list[str], snapshot_key: str) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(PROJECT_ROOT / window[snapshot_key]),
        config={"REPLAY_PARTIAL_REDUCES": True, "REGIME_AWARE_EXIT": True},
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _run_core_baseline() -> dict:
    universe = get_universe()
    by_window = {}
    for label, window in WINDOWS.items():
        result = _run_window(window, universe, "core_snapshot")
        by_window[label] = _metrics(result)
    return {"by_window": by_window, "aggregate": _aggregate(by_window)}


def _run_variant(name: str, target_mult: float) -> dict:
    core_universe = get_universe()
    universe = sorted(set(core_universe) | set(OFFICIAL_SPACE_TICKERS))
    original_enrich, original_size = _install_space_policy(target_mult)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
            }
    finally:
        _restore_policy(original_enrich, original_size)
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "data_vendor_trend_target_atr_mult": target_mult,
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _gate(variant: dict, before: dict, core: dict) -> dict:
    aggregate_delta = _aggregate_delta(variant["aggregate"], before["aggregate"])
    aggregate_delta_vs_core = _aggregate_delta(variant["aggregate"], core["aggregate"])
    by_window_delta = {
        label: _delta(row["metrics"], before["by_window"][label]["metrics"])
        for label, row in variant["by_window"].items()
    }
    windows_ev_improved = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) > 0
    )
    windows_ev_regressed = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) < 0
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and aggregate_delta["max_drawdown_pct_max"] <= 0.005
        and variant["aggregate"]["min_survival_rate"] >= 0.05
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
    }


def _ticket(payload: dict) -> dict:
    best = payload["best_variant"]
    gate = best["gate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Space data-vendor trend target",
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "best_variant": best["variant"],
        "expected_value_score_delta_vs_before": gate[
            "aggregate_delta_vs_before"
        ]["expected_value_score_sum"],
        "gate4": gate,
        "artifact": str(
            Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
        ),
    }


def _artifact_markdown(payload: dict) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space Data-Vendor Trend Target",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Single variable: PL/BKSY trend_long target ATR multiple inside the "
        "default-off official Space sleeve.",
        "",
        "| Variant | Window | EV | EV delta vs accepted | PnL delta vs accepted | Trades | Max DD | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    before = payload["before_variant"]
    for variant in payload["variants"].values():
        gate = variant["gate"]
        for label, row in variant["by_window"].items():
            metrics = row["metrics"]
            delta = gate["by_window_delta_vs_before"][label]
            lines.append(
                "| "
                f"{variant['variant']} | {label} | "
                f"{metrics['expected_value_score']:.4f} | "
                f"{delta.get('expected_value_score', 0):+.4f} | "
                f"{delta.get('total_pnl', 0):+,.2f} | "
                f"{metrics['trade_count']} | "
                f"{metrics['max_drawdown_pct']:.4f} | "
                f"{metrics['survival_rate']:.4f} |"
            )
    best_delta = best["gate"]["aggregate_delta_vs_before"]
    lines.extend(
        [
            "",
            "## Best Variant",
            "",
            f"- Best variant: `{best['variant']}`",
            f"- Aggregate EV delta vs accepted: `{best_delta['expected_value_score_sum']:+.4f}`",
            f"- Aggregate PnL delta vs accepted: `${best_delta['total_pnl_sum']:+,.2f}`",
            f"- Gate 4 passed: `{best['gate']['passed']}`",
            "",
            "## Interpretation",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Default-off Space metadata experiment. Live Space slots remain zero; "
            "no core production orders, ranking, sizing, or signal generation changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def run() -> dict:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    core = _run_core_baseline()
    variants = {}
    for name, spec in VARIANTS.items():
        variant = _run_variant(name, spec["data_vendor_trend_target_atr_mult"])
        variant["description"] = spec["description"]
        variants[name] = variant

    before = variants["accepted_exp105_stack"]
    for variant in variants.values():
        variant["gate"] = _gate(variant, before, core)

    candidates = [
        variant
        for name, variant in variants.items()
        if name != "accepted_exp105_stack"
    ]
    best_variant = max(
        candidates,
        key=lambda variant: (
            variant["gate"]["passed"],
            variant["gate"]["aggregate_delta_vs_before"][
                "expected_value_score_sum"
            ],
            variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    accepted = best_variant["gate"]["passed"]
    decision = (
        "accepted_default_off_data_vendor_trend_target_extension"
        if accepted
        else "rejected_data_vendor_trend_target_extension"
    )
    decision_rationale = (
        "PL/BKSY data-vendor trend target widening improved the accepted "
        "exp-105 Space stack in at least two windows without drawdown or "
        "survival damage."
        if accepted
        else (
            "PL/BKSY data-vendor trend target widening did not beat the "
            "accepted exp-105 Space stack under the three-window gate. The "
            "current evidence supports keeping data-vendor trend targets at "
            "the broad 5 ATR official Space setting."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "exit_target_shadow_sweep",
        "changed_variable": "space_data_vendor_trend_target_atr_mult",
        "single_causal_variable": (
            "target ATR multiple for PL/BKSY data-vendor trend_long signals "
            "inside the default-off official Space sleeve"
        ),
        "hypothesis": (
            "PL/BKSY data-vendor trend_long winners may benefit from the same "
            "bucket-specific lifecycle convexity that improved RKLB/ASTS "
            "trend targets, while breakout risk haircuts and all other Space "
            "semantics stay fixed."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "exit/capital lifecycle alpha: widen only PL/BKSY data-vendor "
                "trend_long targets inside the accepted Space stack."
            ),
            "2_history_check": {
                "exp-20260511-018": (
                    "Deleting PL/BKSY breakouts by trend-only gating was rejected."
                ),
                "exp-20260511-031": (
                    "PL/BKSY breakout risk haircut to 0.1x was accepted."
                ),
                "exp-20260511-038": (
                    "Excluding data-vendor trend from the broad 5 ATR target "
                    "was rejected."
                ),
                "exp-20260511-109": (
                    "PL/BKSY data-vendor trend risk scalar helped only old_thin "
                    "and was rejected."
                ),
                "exp-20260511-110": (
                    "Space breakout stop widening was rejected; this is not a "
                    "breakout geometry retry."
                ),
            },
            "3_single_causal_variable": (
                "space_data_vendor_trend_target_atr_mult; no candidate pool, "
                "risk scalar, ranking, add-on, or LLM boundary changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive "
                "aggregate EV/PnL, EV improvement in at least 2/3 windows with "
                "no EV-regressed window, drawdown max delta <= 0.5 pp, and "
                "survival >= 5%."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-105 Space stack, and "
                "the target variants across the three canonical snapshots."
            ),
        },
        "historical_experiment_check": {
            "exp-20260511-105": (
                "Accepted RKLB/ASTS launch-connectivity 7 ATR trend target."
            ),
            "exp-20260511-106": (
                "Rejected LUNR/RDW lunar/manufacturing 7 ATR trend target."
            ),
            "exp-20260511-109": (
                "Rejected PL/BKSY trend risk scalar; any data-vendor retry "
                "must not be a risk-scalar retune."
            ),
        },
        "parameters": {
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "data_vendor_breakout_risk_scalar": DATA_VENDOR_BREAKOUT_RISK_SCALAR,
            "launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "base_space_trend_target_atr_mult": BASE_SPACE_TREND_TARGET_ATR_MULT,
            "launch_connectivity_trend_target_atr_mult": (
                LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
            ),
            "tested_data_vendor_trend_target_atr_mult": [5.0, 6.0, 7.0],
            "best_data_vendor_trend_target_atr_mult": best_variant[
                "data_vendor_trend_target_atr_mult"
            ],
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "data_vendor_tickers": list(DATA_VENDOR_TICKERS),
            "locked_variables": [
                "official Space candidate pool",
                "base Space risk scalar",
                "PL/BKSY breakout 0.1x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "RKLB/ASTS trend 7 ATR target",
                "core production universe",
                "core signal generation",
                "core entry filters",
                "ranking",
                "MAX_POSITIONS",
                "slot routing",
                "exits except tested target",
                "add-ons",
                "LLM/news replay",
                "live pilot slots",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["space_snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Core uses "
            "canonical snapshots; Space variants use the same exp-20260510-028 "
            "augmented snapshots. The accepted_before variant reproduces "
            "exp-20260511-105 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies "
                "built from a 2026-05-10 research universe; accepted changes "
                "remain default-off metadata until forward evidence matures."
            ),
        },
        "gate2": gate2,
        "gate3": {
            "new_core_filter_added": False,
            "min_survival_rate": before["aggregate"]["min_survival_rate"],
            "passed": before["aggregate"]["min_survival_rate"] >= 0.05,
        },
        "core_baseline_metrics": core["by_window"],
        "core_aggregate": core["aggregate"],
        "before_variant": before,
        "before_metrics": {
            "aggregate": before["aggregate"],
            **{label: row["metrics"] for label, row in before["by_window"].items()},
        },
        "after_metrics": {
            "aggregate": best_variant["aggregate"],
            **{
                label: row["metrics"]
                for label, row in best_variant["by_window"].items()
            },
        },
        "delta_metrics": {
            "aggregate": best_variant["gate"]["aggregate_delta_vs_before"],
            "by_window": best_variant["gate"]["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": best_variant["gate"][
            "aggregate_delta_vs_before"
        ]["expected_value_score_sum"],
        "gate_results": best_variant["gate"],
        "gate4": best_variant["gate"],
        "variants": variants,
        "best_variant": best_variant,
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space forward event ledger still lacks enough mature closed "
                "decisions; this run uses deterministic OHLCV lifecycle replay."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": True,
            "parity_test_added": accepted,
            "daily_report_metadata_changed": accepted,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if accepted else decision_rationale,
        "next_evidence_needed": (
            "If rejected, do not retry nearby PL/BKSY trend target widths on "
            "the same frozen snapshots; future data-vendor Space work needs "
            "forward replacement value or a genuinely new catalyst-quality field."
        ),
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            f"data/experiments/{EXPERIMENT_ID}/{STEM}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{STEM}.md",
            "docs/experiment_log.jsonl",
        ],
    }

    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / f"{STEM}.json"
    log_path = PROJECT_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        PROJECT_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        PROJECT_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{STEM}.md"
    )
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(PROJECT_ROOT / "docs" / "experiment_log.jsonl", payload)
    return payload


def main() -> int:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "best_variant": payload["best_variant"]["variant"],
                "best_gate": payload["best_variant"]["gate"],
                "artifact": f"data/experiments/{EXPERIMENT_ID}/{STEM}.json",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
