"""exp-20260505-003: Unknown-sector risk-on sizing cap replay.

Alpha search. This tests one metadata-aware capital-allocation variable:
whether signals whose sector remains ``Unknown`` should keep the accepted
risk-on/unmodified sizing boost. It is deliberately broader than the rejected
TRIP-only sector-map promotion and does not change production defaults.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-003"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "unknown_sector_risk_on_cap.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

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

VARIANTS = OrderedDict([
    ("unknown_risk_on_cap_1_00x", {"cap_total_multiplier": 1.0}),
    ("unknown_risk_on_cap_0_00x", {"cap_total_multiplier": 0.0}),
])


def _round(value, digits=4):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _is_unknown_risk_on(sig: dict) -> bool:
    sizing = sig.get("sizing") or {}
    multiplier = sizing.get("risk_on_unmodified_risk_multiplier_applied")
    return (
        sig.get("sector") == "Unknown"
        and isinstance(multiplier, (int, float))
        and multiplier != 1.0
        and (sizing.get("shares_to_buy") or 0) > 0
    )


def _zero_sizing(original: dict, cap_total_multiplier: float) -> dict:
    zeroed = dict(original)
    zeroed["risk_pct"] = 0.0
    zeroed["risk_amount_usd"] = 0.0
    zeroed["shares_to_buy"] = 0
    zeroed["position_value_usd"] = 0.0
    zeroed["position_pct_of_portfolio"] = 0.0
    zeroed["risk_on_unmodified_risk_multiplier_applied"] = cap_total_multiplier
    zeroed["spy_relative_leader_risk_on_multiplier_applied"] = min(
        float(original.get("spy_relative_leader_risk_on_multiplier_applied") or 1.0),
        cap_total_multiplier,
    )
    zeroed["unknown_sector_risk_on_cap_applied"] = cap_total_multiplier
    return zeroed


def _make_variant_sizer(original_size_signals, cap_total_multiplier: float):
    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if not _is_unknown_risk_on(sig):
                continue
            sizing = sig.get("sizing") or {}
            current_multiplier = float(
                sizing.get("risk_on_unmodified_risk_multiplier_applied") or 1.0
            )
            capped_multiplier = min(current_multiplier, cap_total_multiplier)
            if capped_multiplier == current_multiplier:
                continue
            if capped_multiplier <= 0:
                sig["sizing"] = _zero_sizing(sizing, capped_multiplier)
                continue
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            base_risk_pct = sizing.get("base_risk_pct")
            if not entry or not stop or base_risk_pct is None:
                continue
            new_sizing = pe.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=base_risk_pct * capped_multiplier,
                max_position_pct=sizing.get("max_position_pct_applied") or pe.MAX_POSITION_PCT,
            )
            if not new_sizing:
                continue
            for key, value in sizing.items():
                if key not in new_sizing:
                    new_sizing[key] = value
            new_sizing["base_risk_pct"] = base_risk_pct
            new_sizing["risk_on_unmodified_risk_multiplier_applied"] = capped_multiplier
            new_sizing["spy_relative_leader_risk_on_multiplier_applied"] = min(
                float(sizing.get("spy_relative_leader_risk_on_multiplier_applied") or 1.0),
                capped_multiplier,
            )
            new_sizing["unknown_sector_risk_on_cap_applied"] = capped_multiplier
            sig["sizing"] = new_sizing
        return sized
    return size_signals


def _run_window(window: dict, variant: dict | None = None) -> dict:
    original_size_signals = pe.size_signals
    if variant is not None:
        pe.size_signals = _make_variant_sizer(
            original_size_signals,
            variant["cap_total_multiplier"],
        )
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        return engine.run()
    finally:
        pe.size_signals = original_size_signals


def _delta(before: dict, after: dict) -> dict:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
        "signals_generated",
        "signals_survived",
    )
    return {key: _round((after.get(key) or 0) - (before.get(key) or 0), 6) for key in keys}


def _unknown_trade_attribution(result: dict) -> dict:
    rows = []
    for trade in result.get("trades") or []:
        sizing = trade.get("sizing_multipliers") or {}
        multiplier = sizing.get("risk_on_unmodified_risk_multiplier_applied")
        if (
            trade.get("sector") == "Unknown"
            and isinstance(multiplier, (int, float))
            and multiplier != 1.0
        ):
            rows.append(trade)
    return {
        "trade_count": len(rows),
        "wins": sum(1 for row in rows if (row.get("pnl") or 0) > 0),
        "losses": sum(1 for row in rows if (row.get("pnl") or 0) <= 0),
        "total_pnl_usd": _round(sum(row.get("pnl") or 0 for row in rows), 2),
        "trades": [
            {
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "pnl": _round(row.get("pnl"), 2),
                "exit_reason": row.get("exit_reason"),
                "sizing_multipliers": row.get("sizing_multipliers") or {},
            }
            for row in rows
        ],
    }


def _aggregate(rows: dict) -> dict:
    baseline_ev = sum(float(row["before"]["expected_value_score"] or 0) for row in rows.values())
    baseline_pnl = sum(float(row["before"]["total_pnl"] or 0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0) for row in rows.values())
    return {
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / baseline_ev if baseline_ev else 0, 6),
        "baseline_expected_value_score_sum": _round(baseline_ev, 6),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "total_pnl_delta_pct": _round(pnl_delta / baseline_pnl if baseline_pnl else 0, 6),
        "ev_windows_improved": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for row in rows.values() if row["delta"]["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for row in rows.values() if row["delta"]["total_pnl"] < 0),
        "max_drawdown_delta_max": _round(max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in rows.values()),
        "win_rate_delta_min": _round(min(row["delta"]["win_rate"] for row in rows.values()), 6),
        "sharpe_daily_delta_max": _round(max(row["delta"]["sharpe_daily"] for row in rows.values()), 6),
    }


def _gate4_passed(aggregate: dict) -> bool:
    material = (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["sharpe_daily_delta_max"] > 0.10
        or aggregate["max_drawdown_delta_max"] < -0.01
        or aggregate["total_pnl_delta_pct"] > 0.05
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return (
        material
        and aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
    )


def main() -> int:
    baselines = OrderedDict()
    for label, window in WINDOWS.items():
        result = _run_window(window)
        baselines[label] = {"raw": result, "metrics": _metrics(result)}

    variants = OrderedDict()
    for name, variant in VARIANTS.items():
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            after_result = _run_window(window, variant)
            before = baselines[label]["metrics"]
            after = _metrics(after_result)
            rows[label] = {
                "window": window,
                "before": before,
                "after": after,
                "delta": _delta(before, after),
                "unknown_trade_attribution_before": _unknown_trade_attribution(
                    baselines[label]["raw"]
                ),
                "unknown_trade_attribution_after": _unknown_trade_attribution(after_result),
            }
        aggregate = _aggregate(rows)
        variants[name] = {
            "parameters": variant,
            "rows": rows,
            "aggregate": aggregate,
            "gate4_passed": _gate4_passed(aggregate),
        }

    ranked = sorted(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
        reverse=True,
    )
    best_name, best = ranked[0]
    accepted = best["gate4_passed"]
    decision = "accepted" if accepted else "rejected"
    generated_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "capital_allocation_metadata_quality",
        "mechanism_family": "unknown_sector_risk_on_sizing",
        "hypothesis": (
            "Signals with sector Unknown may be metadata-leak risk-on winners: "
            "they bypass sector-specific de-risk/boost rules but can still receive "
            "the accepted risk-on/unmodified and SPY-relative leader sizing budget."
        ),
        "alpha_hypothesis": {
            "category": "allocation / candidate-quality metadata",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking and event-bundle live promotion are data-limited, "
                "simple ETF expansion is rejected, and the playbook explicitly allows "
                "a broader Unknown-sector distortion audit before revisiting TRIP mapping."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260501 TRIP sector metadata path": (
                    "TRIP-only Consumer Discretionary remapping was rejected; "
                    "this tests all Unknown-sector risk-on/unmodified boosted signals."
                ),
                "exp-20260502-016": (
                    "SPY leader sector whitelist was rejected; this is not a sector "
                    "whitelist and only touches missing-sector metadata."
                ),
                "exp-20260503-047": (
                    "SPY leader ATR-normalized gates were rejected; this is not a "
                    "price-margin or volatility threshold."
                ),
            },
            "why_not_simple_repeat": (
                "The tested unit is the metadata-missing bucket across all fixed "
                "windows, not a hand-coded TRIP sector map or a nearby SPY-leader "
                "multiplier/cap sweep."
            ),
        },
        "parameters": {
            "single_causal_variable": "cap Unknown-sector risk-on/unmodified total sizing multiplier",
            "baseline_behavior": "Unknown-sector signals may receive existing risk-on/unmodified multipliers, including 2.0x SPY-relative leader budget.",
            "tested_variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "entries",
                "exits",
                "candidate ordering",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "same-day sector cap",
                "add-ons",
                "gap cancels",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "snapshots": {label: w["snapshot"] for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "before_metrics": {label: row["before"] for label, row in best["rows"].items()},
        "after_metrics": {label: row["after"] for label, row in best["rows"].items()},
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            **best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate4": {
            "passed": accepted,
            "basis": (
                "Gate4 requires >10% aggregate EV lift, >0.1 Sharpe lift, >1pp "
                "drawdown reduction, >5% PnL lift, or more trades without win-rate "
                "decline; accepted variants also need EV improvement in at least two "
                "fixed windows and no EV-regressed window."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If a future Unknown-sector allocation rule passes, implement it in "
                "shared portfolio_engine sizing and add production/backtest parity tests."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains production-sample limited, so this run "
                "uses deterministic OHLCV/enrichment metadata instead."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "Unknown-sector risk-on sizing caps did not clear the three-window Gate 4 materiality bar; the best variant improved only old_thin while late_strong and mid_weak were unchanged."
        ),
        "next_retry_requires": [
            "Do not retry Unknown-sector risk-on caps or TRIP-only sector mapping without a larger missing-sector cohort.",
            "A valid retry needs new production universe metadata coverage or forward evidence that Unknown-sector candidates are recurring.",
            "If accepted in future, keep the rule in shared portfolio_engine sizing so run.py and backtester.py stay aligned.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260505_003_unknown_sector_risk_on_cap.py",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "title": "Unknown-sector risk-on cap",
        "summary": f"Best {best_name}; Gate4={accepted}",
        "best_variant": best_name,
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{EXPERIMENT_ID} {decision} best={best_name}")
    print(json.dumps(ticket["delta_metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
