"""exp-20260513-026: Space IWM peer-leader trend target width.

Tests one lifecycle variable on top of the accepted exp-20260513-020
default-off Space stack: a wider target ATR floor for official Space
trend_long signals when IWM leads SPY and the ticker leads the official Space
peer basket. This is intentionally not a retry of the accepted exp020 risk
scalar.
"""

from __future__ import annotations

import json
import math
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from exp_20260513_020_space_iwm_peer_leader_trend_risk import (  # noqa: E402
    ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
    IWM_PEER_LEADER_TREND_RISK_SCALARS,
    OFFICIAL_SPACE_TICKERS,
    PROJECT_ROOT,
    STEM as BASE_STEM,
    WINDOWS,
    _accepted_financing_profile_gate,
    _aggregate,
    _aggregate_delta,
    _delta,
    _event_seed_profiles,
    _field_check_company_release_source,
    _field_check_government_contract_profile,
    _field_check_iwm_peer_leader_trend,
    _field_check_multi_event_depth,
    _field_check_peer_leader_state,
    _field_check_watch_liquidity_tier,
    _gate2_open_positions,
    _install_space_policy,
    _metrics,
    _run_core_baseline,
    _run_variant as _run_exp020_variant,
    _run_window,
    _safe,
    _space_trade_attribution,
    _write_json,
)
from data_layer import get_universe  # noqa: E402
from risk_engine import _retarget_signal_with_atr_mult  # noqa: E402
from space_catalyst_sleeve import (  # noqa: E402
    space_catalyst_basket_momentum_state,
    space_catalyst_iwm_relative_momentum_state,
    space_catalyst_peer_momentum_state,
)


EXPERIMENT_ID = "exp-20260513-026"
STEM = "space_iwm_peer_leader_trend_target"
ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR = 1.15
TARGET_ATR_FLOORS = (5.0, 6.0, 7.0, 8.0)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005

OUT_DIR = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = PROJECT_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = (
    PROJECT_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
ARTIFACT_MD = (
    PROJECT_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = PROJECT_ROOT / "docs" / "experiment_log.jsonl"


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
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


def _as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> Any:
    numeric = _as_float(value)
    return round(numeric, digits) if numeric is not None else None


def _target_adjustment_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, int] = {}
    by_previous_mult: dict[str, int] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "")
        previous = str(row.get("previous_target_mult"))
        by_ticker[ticker] = by_ticker.get(ticker, 0) + 1
        by_previous_mult[previous] = by_previous_mult.get(previous, 0) + 1
    return {
        "adjusted_signal_count": len(rows),
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_previous_target_mult": dict(sorted(by_previous_mult.items())),
        "sample_adjusted": rows[:12],
    }


def _field_check_target_inputs(before: dict[str, Any]) -> dict[str, Any]:
    samples = []
    counts = {"candidate_state": 0, "has_target_mult": 0, "has_atr": 0}
    for row in before["by_window"].values():
        summary = row.get("space_iwm_peer_leader_trend_adjustment") or {}
        for sample in summary.get("sample_adjusted") or []:
            counts["candidate_state"] += 1
            if sample.get("target_mult_used") is not None:
                counts["has_target_mult"] += 1
            samples.append(
                {
                    "ticker": sample.get("ticker"),
                    "strategy": sample.get("strategy"),
                    "space_iwm_relative_state": sample.get("space_iwm_relative_state"),
                    "space_peer_momentum_state": sample.get(
                        "space_peer_momentum_state"
                    ),
                    "target_mult_used": sample.get("target_mult_used"),
                    "target_price": sample.get("target_price"),
                }
            )
            if len(samples) >= 12:
                break
    return {
        "passed": counts["candidate_state"] > 0,
        "counts": counts,
        "fields": [
            "signal.target_price",
            "signal.target_mult_used",
            "features_by_ticker[ticker].atr",
            "features_by_ticker[IWM].momentum_20d_pct",
            "features_by_ticker[SPY].momentum_20d_pct",
            "features_by_ticker[official_space_ticker].momentum_20d_pct",
        ],
        "sample_candidate_state_rows": samples,
    }


@contextmanager
def _patched_iwm_peer_leader_trend_target(target_floor: float):
    import risk_engine  # noqa: PLC0415

    original = risk_engine.enrich_signals
    official_tickers = {ticker.upper() for ticker in OFFICIAL_SPACE_TICKERS}
    adjustments: list[dict[str, Any]] = []

    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        basket_state = space_catalyst_basket_momentum_state(features_dict)
        iwm_state = space_catalyst_iwm_relative_momentum_state(features_dict)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            if ticker not in official_tickers or strategy != "trend_long":
                continue
            if iwm_state.get("state") != "smallcap_leader":
                continue
            peer_state = space_catalyst_peer_momentum_state(ticker, basket_state)
            if peer_state.get("state") != "leader":
                continue
            atr = _as_float((features_dict.get(ticker) or {}).get("atr"))
            if atr is None or atr <= 0:
                continue
            previous_mult = _as_float(sig.get("target_mult_used"))
            if previous_mult is None:
                previous_mult = _as_float(atr_target_mult) or 0.0
            applied_mult = max(previous_mult, target_floor)
            if applied_mult <= previous_mult:
                continue
            previous_target = sig.get("target_price")
            retargeted = _retarget_signal_with_atr_mult(sig, atr, applied_mult)
            retargeted["space_iwm_peer_leader_trend_target_floor_applied"] = (
                target_floor
            )
            retargeted["space_iwm_peer_leader_trend_target_previous_mult"] = (
                previous_mult
            )
            retargeted["space_iwm_peer_leader_trend_target_previous_price"] = (
                previous_target
            )
            sig.clear()
            sig.update(retargeted)
            adjustments.append(
                {
                    "ticker": ticker,
                    "strategy": strategy,
                    "target_floor": target_floor,
                    "applied_target_mult": _round(applied_mult, 4),
                    "previous_target_mult": _round(previous_mult, 4),
                    "previous_target_price": _round(previous_target, 4),
                    "target_price": _round(sig.get("target_price"), 4),
                    "atr": _round(atr, 4),
                    "space_iwm_relative_state": iwm_state.get("state"),
                    "space_iwm_excess_vs_spy_20d_pct": iwm_state.get(
                        "iwm_excess_vs_spy_20d_pct"
                    ),
                    "space_peer_momentum_state": peer_state.get("state"),
                    "space_peer_excess_momentum_20d_pct": peer_state.get(
                        "excess_momentum_20d_pct"
                    ),
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


def _run_target_variant(
    name: str,
    target_floor: float,
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    installed = _install_space_policy(
        ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    with _patched_iwm_peer_leader_trend_target(target_floor) as target_adjustments:
        try:
            by_window = {}
            for label, window in WINDOWS.items():
                before_target_count = len(target_adjustments)
                result = _run_window(window, universe, "space_snapshot")
                window_adjustments = target_adjustments[before_target_count:]
                by_window[label] = {
                    "metrics": _metrics(result),
                    "space_trade_attribution": _space_trade_attribution(result),
                    "space_iwm_peer_leader_trend_target_adjustment": (
                        _target_adjustment_summary(window_adjustments)
                    ),
                }
        finally:
            from exp_20260513_020_space_iwm_peer_leader_trend_risk import (  # noqa: PLC0415
                _restore_policy,
            )

            _restore_policy(*installed["originals"])
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "space_iwm_peer_leader_trend_target_atr_floor": target_floor,
        "target_definition": (
            "official Space trend_long with IWM>SPY and peer momentum leadership; "
            "target ATR multiple floored at the tested value"
        ),
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _gate(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(variant["aggregate"], before["aggregate"])
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
    adjusted_count = sum(
        row["space_iwm_peer_leader_trend_target_adjustment"]["adjusted_signal_count"]
        for row in variant["by_window"].values()
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and variant["aggregate"]["min_survival_rate"] >= 0.05
        and variant["aggregate"]["trade_count_sum"] >= 50
        and adjusted_count > 0
        and variant["space_iwm_peer_leader_trend_target_atr_floor"] != 5.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_iwm_peer_leader_trend_target_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space IWM peer-leader trend target",
        "",
        f"- decision: `{payload['decision']}`",
        f"- best variant: `{best['variant']}`",
        f"- aggregate EV delta: `{payload['expected_value_score_delta']:+.4f}`",
        f"- aggregate PnL delta: `${payload['total_pnl_delta']:+,.2f}`",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Target adjustments |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_iwm_peer_leader_trend_target_adjustment"
        ]["adjusted_signal_count"]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{before_pnl:,.2f} | {after_pnl:,.2f} | {delta_pnl:+,.2f} | "
            "{trades} | {max_dd:.4f} | {survival:.4f} | {adjusted} |".format(
                label=label,
                before_ev=before["expected_value_score"],
                after_ev=after["expected_value_score"],
                delta_ev=delta.get("expected_value_score", 0),
                before_pnl=before["total_pnl"],
                after_pnl=after["total_pnl"],
                delta_pnl=delta.get("total_pnl", 0),
                trades=after["trade_count"],
                max_dd=after["max_drawdown_pct"],
                survival=after["survival_rate"],
                adjusted=adjusted,
            )
        )
    lines.extend(
        [
            "",
            "## Gate 2",
            "",
            json.dumps(payload["gate2"], sort_keys=True),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "best_variant": payload["best_variant"]["variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    gate2_open = _gate2_open_positions()
    if not gate2_open["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2_open}")

    source_gate = _event_seed_profiles()
    financing_gate = _accepted_financing_profile_gate()
    company_release_gate = _field_check_company_release_source()
    liquidity_gate = _field_check_watch_liquidity_tier()
    multi_event_gate = _field_check_multi_event_depth()
    government_contract_gate = _field_check_government_contract_profile()
    for name, gate in (
        ("source", source_gate),
        ("financing", financing_gate),
        ("company_release", company_release_gate),
        ("liquidity", liquidity_gate),
        ("multi_event", multi_event_gate),
        ("government_contract", government_contract_gate),
    ):
        if not gate["passed"]:
            raise RuntimeError(f"Gate 2 {name} field check failed: {gate}")

    core = _run_core_baseline()
    before = _run_exp020_variant(
        "accepted_exp020_iwm_peer_leader_trend_stack",
        ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    peer_state_gate = _field_check_peer_leader_state(before)
    iwm_peer_leader_gate = _field_check_iwm_peer_leader_trend(before)
    target_input_gate = _field_check_target_inputs(before)
    for name, gate in (
        ("peer_state", peer_state_gate),
        ("iwm_peer_leader", iwm_peer_leader_gate),
        ("target_inputs", target_input_gate),
    ):
        if not gate["passed"]:
            raise RuntimeError(f"Gate 2 {name} field check failed: {gate}")

    variants = {}
    for floor in TARGET_ATR_FLOORS:
        name = f"target_floor_{str(floor).replace('.', '_')}atr"
        variants[name] = _run_target_variant(
            name,
            floor,
            government_contract_gate,
            source_gate,
            multi_event_gate,
            liquidity_gate,
            company_release_gate,
            financing_gate,
        )
    for variant in variants.values():
        variant["gate"] = _gate(variant, before)

    best_variant = max(
        variants.values(),
        key=lambda variant: (
            variant["gate"]["passed"],
            variant["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
            variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    accepted = best_variant["gate"]["passed"]
    decision = (
        "accepted_default_off_space_iwm_peer_leader_trend_target"
        if accepted
        else "rejected_space_iwm_peer_leader_trend_target"
    )
    interpretation = (
        "The IWM-relative peer-leader Space trend target floor improved the accepted "
        "default-off Space stack under the three-window gate. Promotion must stay "
        "shared and metadata-only with live Space slots at zero."
        if accepted
        else (
            "IWM-relative peer-leader Space trends did not justify a wider target "
            "floor on top of exp-20260513-020. Keep the accepted risk-allocation "
            "helper; the next Space target work needs forward target-touch evidence."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "exit_target_shadow_sweep",
        "changed_variable": "space_iwm_peer_leader_trend_target_atr_floor",
        "single_causal_variable": (
            "target ATR floor for official Space trend_long signals when IWM leads "
            "SPY and the ticker is a Space peer momentum leader"
        ),
        "hypothesis": (
            "The accepted exp020 state may be a convex trend state rather than only "
            "a sizing state. A wider target floor could improve replacement value "
            "without adding tickers, LLM ranking, or another risk scalar."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "exit/lifecycle: widen target only for official Space trend_long "
                "signals where IWM leads SPY and the ticker leads the official "
                "Space basket."
            ),
            "2_history_check": {
                "exp-20260511-032": (
                    "Accepted broad official Space trend target width at 5 ATR. "
                    "This run does not retry broad trend target width; it tests "
                    "only the narrower exp020 IWM+peer-leader state."
                ),
                "exp-20260513-020": (
                    "Accepted 1.15x risk scalar for this state. This run keeps "
                    "that scalar fixed and changes only target geometry."
                ),
                "exp-20260513-025": (
                    "Rejected peer-leader breakout risk, so this run stays in "
                    "trend_long lifecycle instead of breakout risk."
                ),
                "llm_soft_ranking": (
                    "Skipped because the Space labeled forward set remains thin."
                ),
            },
            "3_single_causal_variable": (
                "space_iwm_peer_leader_trend_target_atr_floor. Candidate pool, risk "
                "scalars, stop logic, ranking, add-ons, LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL versus exp020 accepted stack, at least 2/3 improved EV windows, "
                "no EV-regressed window, max drawdown drift <= 0.5 pp, survival >= 5%, "
                ">=50 total trades, and nonzero target adjustments."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_026_space_iwm_peer_leader_trend_target.py"
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "accepted_before_experiment": "exp-20260513-020",
            "accepted_iwm_peer_leader_trend_risk_scalar": (
                ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR
            ),
            "tested_target_atr_floors": list(TARGET_ATR_FLOORS),
            "locked_variables": [
                "official Space candidate pool",
                "all accepted Space risk scalars",
                "accepted broad official Space trend target",
                "accepted RKLB/ASTS launch-connectivity target",
                "hard stops",
                "candidate ranking",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
            "anti_js": "No JavaScript was used.",
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
            "docs/backtesting.md canonical three fixed windows. Core uses canonical "
            "snapshots; Space variants use exp-20260510-028 augmented Space snapshots. "
            "The accepted_before variant reproduces exp-20260513-020 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. Any accepted Space change must "
                "remain default-off until forward replacement-value evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "official_customer_source_profile": source_gate,
            "peer_momentum_state": peer_state_gate,
            "iwm_peer_leader_trend_state": iwm_peer_leader_gate,
            "target_inputs": target_input_gate,
            "accepted_financing_dilution_profiles": financing_gate,
            "accepted_company_release_source_profile": company_release_gate,
            "watch_liquidity_tier_registry": liquidity_gate,
            "accepted_multi_event_depth": multi_event_gate,
            "government_contract_profile": government_contract_gate,
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "new_target_rule_tested": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"] >= 0.05,
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
            **{label: row["metrics"] for label, row in best_variant["by_window"].items()},
        },
        "delta_metrics": {
            "aggregate": best_variant["gate"]["aggregate_delta_vs_before"],
            "by_window": best_variant["gate"]["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": best_variant["gate"][
            "aggregate_delta_vs_before"
        ]["expected_value_score_sum"],
        "total_pnl_delta": best_variant["gate"]["aggregate_delta_vs_before"][
            "total_pnl_sum"
        ],
        "variants": variants,
        "best_variant": best_variant,
        "gate4": {
            "passed": accepted,
            **best_variant["gate"],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "live_slots_changed": False,
            "live_slots": 0,
            "promotion_if_accepted": (
                "Would require shared space_catalyst_sleeve target helper plus "
                "production observation metadata/tests before retention."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": "" if accepted else interpretation,
        "next_evidence_needed": (
            "Forward target-touch and replacement-value attribution for exp020 "
            "IWM+peer-leader trend signals before another target-width retry."
            if not accepted
            else "Add shared target helper and parity tests before promotion."
        ),
        "related_files": [
            f"quant/experiments/exp_20260513_026_{STEM}.py",
            f"data/experiments/{EXPERIMENT_ID}/{STEM}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{STEM}.md",
            "docs/experiment_log.jsonl",
        ],
        "llm_metrics": {"used_llm": False},
        "base_experiment_script": (
            f"quant/experiments/exp_20260513_020_{BASE_STEM}.py"
        ),
        "sweep_reference": list(IWM_PEER_LEADER_TREND_RISK_SCALARS),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, _ticket(payload))
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG_JSONL, payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
            },
            sort_keys=True,
        )
    )
