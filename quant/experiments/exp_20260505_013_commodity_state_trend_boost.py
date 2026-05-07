"""exp-20260505-013: commodity sector-state trend risk boost replay.

Alpha search. Tests one allocation variable: when Commodities are in a broad
uptrend state, should `trend_long | Commodities` entries size at a higher total
risk budget than the current accepted near-high 1.5x sleeve.

No production order path is changed by this runner. A positive result must be
promoted through shared run/backtester policy before it can affect live orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine as pe  # noqa: E402
import risk_engine as risk  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-013"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "commodity_state_trend_boost.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_commodity_state_trend_boost.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

STATE_FILTER = {
    "sector": "Commodities",
    "strategy": "trend_long",
    "min_sector_breadth_200": 0.75,
    "min_sector_avg_ret20_pct": 0.05,
}

VARIANTS = OrderedDict([
    ("commodity_state_total_2_0x", {"total_risk_multiplier": 2.0}),
    ("commodity_state_total_2_5x", {"total_risk_multiplier": 2.5}),
])

SIZING_KEY = "commodity_state_trend_risk_multiplier_applied"


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
        "entry_reason_counts": (
            result.get("entry_execution_attribution") or {}
        ).get("reason_counts") or {},
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    )
    out: dict[str, Any] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived"}:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _sector_states(features_dict: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, list[Any]]] = {}
    for ticker, features in (features_dict or {}).items():
        if not features:
            continue
        sector = risk.SECTOR_MAP.get(ticker, "Unknown")
        if sector == "Unknown":
            continue
        bucket = rows.setdefault(sector, {"above_200ma": [], "ret20": []})
        above_200ma = features.get("above_200ma")
        if above_200ma is not None:
            bucket["above_200ma"].append(bool(above_200ma))
        ret20 = features.get("momentum_20d_pct")
        if isinstance(ret20, (int, float)):
            bucket["ret20"].append(float(ret20))

    out: dict[str, dict[str, Any]] = {}
    for sector, bucket in rows.items():
        above = bucket["above_200ma"]
        ret20 = bucket["ret20"]
        out[sector] = {
            "sector_breadth_200": (
                sum(1 for item in above if item) / len(above)
                if above else None
            ),
            "sector_avg_ret20_pct": (
                sum(ret20) / len(ret20)
                if ret20 else None
            ),
            "sector_state_member_count": len(above),
        }
    return out


def _make_enrich_signals(original_enrich):
    coverage = {"feature_days_with_state": 0, "commodity_state_days": 0}

    def enrich_signals(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        states = _sector_states(features_dict or {})
        if states:
            coverage["feature_days_with_state"] += 1
        commodity_state = states.get("Commodities") or {}
        if _passes_state(commodity_state):
            coverage["commodity_state_days"] += 1
        for sig in enriched:
            state = states.get(sig.get("sector"))
            if not state:
                continue
            sig["sector_breadth_200"] = _round(state.get("sector_breadth_200"), 4)
            sig["sector_avg_ret20_pct"] = _round(state.get("sector_avg_ret20_pct"), 4)
            sig["sector_state_member_count"] = state.get("sector_state_member_count")
        return enriched

    enrich_signals.coverage = coverage  # type: ignore[attr-defined]
    return enrich_signals


def _passes_state(state: dict[str, Any]) -> bool:
    breadth = state.get("sector_breadth_200")
    avg_ret20 = state.get("sector_avg_ret20_pct")
    return (
        isinstance(breadth, (int, float))
        and isinstance(avg_ret20, (int, float))
        and breadth >= STATE_FILTER["min_sector_breadth_200"]
        and avg_ret20 >= STATE_FILTER["min_sector_avg_ret20_pct"]
    )


def _candidate_matches(sig: dict[str, Any]) -> bool:
    return (
        sig.get("strategy") == STATE_FILTER["strategy"]
        and sig.get("sector") == STATE_FILTER["sector"]
        and _passes_state({
            "sector_breadth_200": sig.get("sector_breadth_200"),
            "sector_avg_ret20_pct": sig.get("sector_avg_ret20_pct"),
        })
    )


def _resized_sizing(
    original: dict[str, Any],
    portfolio_value: float,
    entry: float,
    stop: float,
    target_risk_pct: float,
    total_risk_multiplier: float,
) -> dict[str, Any] | None:
    max_position_pct = original.get("max_position_pct_applied")
    if not isinstance(max_position_pct, (int, float)) or max_position_pct <= 0:
        max_position_pct = pe.MAX_POSITION_PCT
    new_sizing = pe.compute_position_size(
        portfolio_value,
        entry,
        stop,
        risk_pct=target_risk_pct,
        max_position_pct=max_position_pct,
    )
    if not new_sizing:
        return None
    for key, value in original.items():
        if key.endswith("_multiplier_applied") or key in {
            "base_risk_pct",
            "max_position_pct_applied",
            "trade_quality_score",
            "low_tqs_haircut_exempt_sector",
        }:
            new_sizing[key] = value
    new_sizing["base_risk_pct"] = original.get("base_risk_pct")
    new_sizing["max_position_pct_applied"] = max_position_pct
    new_sizing[SIZING_KEY] = total_risk_multiplier
    new_sizing["commodity_state_target_risk_pct"] = round(target_risk_pct, 6)
    new_sizing["commodity_state_previous_risk_pct"] = original.get("risk_pct")
    return new_sizing


def _make_size_signals(original_size_signals, total_risk_multiplier: float):
    touched: list[dict[str, Any]] = []

    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if (sizing.get("shares_to_buy") or 0) <= 0:
                continue
            if not _candidate_matches(sig):
                continue
            base_risk_pct = sizing.get("base_risk_pct")
            current_risk_pct = sizing.get("risk_pct")
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            if not all(isinstance(value, (int, float)) for value in (
                base_risk_pct,
                current_risk_pct,
                entry,
                stop,
            )):
                continue
            target_risk_pct = float(base_risk_pct) * total_risk_multiplier
            if target_risk_pct <= float(current_risk_pct):
                continue
            resized = _resized_sizing(
                sizing,
                portfolio_value,
                float(entry),
                float(stop),
                target_risk_pct,
                total_risk_multiplier,
            )
            if not resized:
                continue
            touched.append({
                "ticker": sig.get("ticker"),
                "strategy": sig.get("strategy"),
                "sector": sig.get("sector"),
                "signal_date": sig.get("signal_date") or sig.get("date"),
                "entry_price": sig.get("entry_price"),
                "stop_price": sig.get("stop_price"),
                "sector_breadth_200": sig.get("sector_breadth_200"),
                "sector_avg_ret20_pct": sig.get("sector_avg_ret20_pct"),
                "risk_pct_before": current_risk_pct,
                "risk_pct_after": resized.get("risk_pct"),
                "shares_before": sizing.get("shares_to_buy"),
                "shares_after": resized.get("shares_to_buy"),
                "position_pct_before": sizing.get("position_pct_of_portfolio"),
                "position_pct_after": resized.get("position_pct_of_portfolio"),
            })
            sig["sizing"] = resized
        return sized

    size_signals.touched = touched  # type: ignore[attr-defined]
    return size_signals


def _run_window(
    window: dict[str, str],
    variant: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    original_enrich = risk.enrich_signals
    original_size_signals = pe.size_signals
    patched_enrich = _make_enrich_signals(original_enrich)
    risk.enrich_signals = patched_enrich
    if variant is not None:
        pe.size_signals = _make_size_signals(
            original_size_signals,
            float(variant["total_risk_multiplier"]),
        )
    try:
        result = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
        touched = (
            list(getattr(pe.size_signals, "touched", []))
            if variant is not None
            else []
        )
        coverage = dict(getattr(risk.enrich_signals, "coverage", {}))
        return result, touched, coverage
    finally:
        risk.enrich_signals = original_enrich
        pe.size_signals = original_size_signals


def _run_baselines() -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline")
        result, _, coverage = _run_window(window)
        rows[label] = {
            "window": window,
            "metrics": _metrics(result),
            "state_coverage": coverage,
        }
    return rows


def _run_variant(
    name: str,
    variant: dict[str, Any],
    baselines: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        print(f"[{label}] {name}")
        after_result, touched, coverage = _run_window(window, variant)
        before = baselines[label]["metrics"]
        after = _metrics(after_result)
        delta = _delta(after, before)
        rows[label] = {
            "window": window,
            "before": before,
            "after": after,
            "delta": delta,
            "commodity_state_boost_candidate_count": len(touched),
            "commodity_state_boost_candidates": touched,
            "state_coverage": coverage,
        }
        print(
            f"[{label}] {name} EV={delta['expected_value_score']:+.4f} "
            f"PnL={delta['total_pnl']:+.2f} touched={len(touched)}"
        )
    return {"variant": variant, "rows": rows, "aggregate": _aggregate(rows)}


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline_ev = sum(row["before"]["expected_value_score"] for row in rows.values())
    baseline_pnl = sum(row["before"]["total_pnl"] for row in rows.values())
    ev_delta = sum(row["delta"]["expected_value_score"] for row in rows.values())
    pnl_delta = sum(row["delta"]["total_pnl"] for row in rows.values())
    sharpe_delta_max = max(row["delta"]["sharpe_daily"] for row in rows.values())
    drawdown_delta_min = min(row["delta"]["max_drawdown_pct"] for row in rows.values())
    drawdown_delta_max = max(row["delta"]["max_drawdown_pct"] for row in rows.values())
    trade_delta = sum(row["delta"]["trade_count"] for row in rows.values())
    win_rate_delta_min = min(row["delta"]["win_rate"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(baseline_ev, 4),
        "expected_value_score_delta_sum": _round(ev_delta, 4),
        "expected_value_score_delta_pct": _round(ev_delta / baseline_ev, 6)
        if baseline_ev else None,
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / baseline_pnl, 6)
        if baseline_pnl else None,
        "ev_windows_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "sharpe_delta_max": _round(sharpe_delta_max, 4),
        "drawdown_delta_min": _round(drawdown_delta_min, 4),
        "drawdown_delta_max": _round(drawdown_delta_max, 4),
        "trade_count_delta_sum": trade_delta,
        "win_rate_delta_min": _round(win_rate_delta_min, 4),
        "commodity_state_boost_candidate_count_sum": sum(
            row["commodity_state_boost_candidate_count"] for row in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict[str, Any]) -> bool:
    ev_pct = aggregate.get("expected_value_score_delta_pct") or 0.0
    pnl_pct = aggregate.get("total_pnl_delta_pct") or 0.0
    multi_window_ok = (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] <= 1
        and aggregate["drawdown_delta_max"] <= 0.01
    )
    material = (
        ev_pct > 0.10
        or pnl_pct > 0.05
        or aggregate["sharpe_delta_max"] > 0.10
        or aggregate["drawdown_delta_min"] < -0.01
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return bool(multi_window_ok and material)


def _best_variant(variants: OrderedDict[str, dict[str, Any]]) -> str:
    return max(
        variants,
        key=lambda name: (
            variants[name]["aggregate"]["expected_value_score_delta_sum"],
            variants[name]["aggregate"]["total_pnl_delta_sum"],
            -variants[name]["aggregate"]["drawdown_delta_max"],
        ),
    )


def _make_payload(
    baselines: OrderedDict[str, dict[str, Any]],
    variants: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    best_name = _best_variant(variants)
    best = variants[best_name]
    accepted = _gate4_passed(best["aggregate"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "hypothesis": (
            "If Commodities breadth is >=75% above 200MA and equal-weight "
            "20-day sector return is >=5%, trend_long Commodity entries may "
            "carry enough convex continuation to justify a higher total risk "
            "budget than the current accepted 1.5x near-high sleeve."
        ),
        "alpha_hypothesis": {
            "category": "资金分配 / allocation",
            "statement": (
                "Commodity trend alpha may be state-dependent: broad sector "
                "participation plus positive 20-day sector momentum should "
                "identify when increasing risk budget adds EV."
            ),
            "why_now": (
                "LLM/event ranking remains data-limited, broad universe "
                "expansion just failed, and prior state audit highlighted "
                "Commodities breadth+momentum as one of the few strong "
                "remaining non-LLM pockets."
            ),
        },
        "change_type": "alpha_search_allocation_sweep",
        "component": "quant/experiments/exp_20260505_013_commodity_state_trend_boost.py",
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260429-030": (
                    "Observation-only sector-state audit found the strongest "
                    "trend_long pocket in Commodities breadth>=75 with positive "
                    "sector momentum. This experiment turns that mechanism into "
                    "a bounded allocation replay."
                ),
                "exp-20260428-003": (
                    "Uniform Commodity target widening was rejected because it "
                    "hurt mid_weak. This run changes sizing, not exits, and only "
                    "when the sector state is broad and positive."
                ),
                "exp-20260430-032": (
                    "Gold-only target extension is already accepted. This run "
                    "does not touch target width or ticker-specific gold logic."
                ),
            },
            "mechanism_insight_check": (
                "Avoids the current no-repeat zones: no LLM soft-ranking, no "
                "event-bundle promotion, no universe expansion, no sector cap, "
                "no add-on cap, and no target-width sweep."
            ),
        },
        "parameters": {
            "single_causal_variable": (
                "total risk multiplier for trend_long Commodities under a "
                "broad positive Commodities sector state"
            ),
            "state_filter": STATE_FILTER,
            "variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "signal generation",
                "sector map",
                "entry ordering",
                "entry open cancels",
                "all exits and target widths",
                "add-ons",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {
            label: row["metrics"] for label, row in baselines.items()
        },
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            "aggregate": best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate4": {
            "passed": accepted,
            "basis": (
                "Requires material Gate 4 improvement plus multi-window stability "
                "on the three fixed backtesting.md windows."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted for trading, add a shared sector-state helper and "
                "call it from both run.py and backtester.py before changing live "
                "orders."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this tests deterministic "
                "allocation without weakening or blaming the LLM layer."
            ),
        },
        "rejection_reason": None if accepted else (
            "Commodity sector-state trend risk boost did not clear the "
            "three-window materiality and stability gate."
        ),
        "next_retry_requires": [
            "Do not retry nearby Commodity state total-risk multipliers without a new discriminator.",
            "A valid retry needs forward evidence or a non-price event/state feature explaining why extra size avoids mid/old drawdown.",
            "Any positive retry must be promoted through shared run/backtester policy before live orders change.",
        ],
        "risk_of_change": (
            "May over-concentrate commodity exposure during crowded metals/oil "
            "runs and amplify SLV-style reversals that prior Commodity sweeps "
            "identified as the main weak path."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still production-sample limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "universe_expansion": "Broad and narrow static expansions just failed.",
            "add_on_or_target_tuning": "Recent mechanism insights explicitly ban nearby sweeps without new evidence.",
        },
        "related_files": [
            "quant/experiments/exp_20260505_013_commodity_state_trend_boost.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != payload["experiment_id"]:
                kept.append(line)
    kept.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Commodity State Trend Boost",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- passed: `{payload['gate4']['passed']}`",
        f"- best_variant: `{payload['best_variant']}`",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`",
        f"- touched candidate count: `{aggregate['commodity_state_boost_candidate_count_sum']}`",
        "",
        "## Three-window Deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Touched |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        delta = row["delta"]
        lines.append(
            f"| `{label}` | {delta['expected_value_score']:+.4f} | "
            f"{delta['total_pnl']:+.2f} | {delta['sharpe_daily']:+.2f} | "
            f"{delta['max_drawdown_pct']:+.4f} | {delta['win_rate']:+.4f} | "
            f"{delta['trade_count']:+d} | {row['commodity_state_boost_candidate_count']} |"
        )
    lines.extend([
        "",
        "## Production Parity",
        "",
        "No production order path changed. A positive promotion requires a shared sector-state helper, a run.py adapter, and a parity test before live orders can change.",
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_playbook(payload: dict[str, Any]) -> None:
    marker = "## Recent mechanism insights"
    aggregate = payload["delta_metrics"]["aggregate"]
    entry = (
        "\n"
        f"- `{EXPERIMENT_ID}` ({payload['decision']}): Commodity breadth+momentum "
        "sector-state boost tested total 2.0x/2.5x risk for `trend_long | "
        f"Commodities`. Best `{payload['best_variant']}` aggregate EV delta "
        f"{aggregate['expected_value_score_delta_sum']} "
        f"({aggregate['expected_value_score_delta_pct']:.2%}), PnL delta "
        f"${aggregate['total_pnl_delta_sum']}. Do not retry nearby Commodity "
        "state risk multipliers without a new non-price discriminator or "
        "forward evidence.\n"
    )
    text = PLAYBOOK.read_text(encoding="utf-8")
    if f"`{EXPERIMENT_ID}`" in text:
        return
    if marker in text:
        text = text.replace(marker, marker + entry, 1)
    else:
        text = text + "\n" + marker + "\n" + entry
    PLAYBOOK.write_text(text, encoding="utf-8")


def main() -> int:
    import backtester as bt

    if SIZING_KEY not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (*bt.SIZING_MULTIPLIER_KEYS, SIZING_KEY)

    baselines = _run_baselines()
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, variant in VARIANTS.items():
        variants[name] = _run_variant(name, variant, baselines)

    payload = _make_payload(baselines, variants)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "decision": payload["decision"],
        "title": "Commodity state trend boost",
        "summary": f"Best {payload['best_variant']}; Gate4={payload['gate4']['passed']}",
        "best_variant": payload["best_variant"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    })
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _update_playbook(payload)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "best_variant": payload["best_variant"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
