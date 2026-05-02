"""exp-20260502-023: SPY-relative leader target floor replay.

Alpha search. Test one lifecycle variable: whether 20-day SPY-relative leaders
are being clipped by the current regime-aware target width. This does not change
entries, candidate ordering, sizing, add-ons, slot rules, LLM/news replay, or
the accepted SPY-relative leader risk/cap/add-on policies.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260502-023"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "spy_leader_target_floor.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

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
    ("spy_leader_target_floor_5_0atr", 5.0),
    ("spy_leader_target_floor_6_0atr", 6.0),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    trades = result.get("trades", [])
    leader_trades = [
        trade for trade in trades
        if (trade.get("sizing_multipliers") or {}).get(
            "spy_relative_leader_risk_on_multiplier_applied", 1.0
        ) > 1.0
        or trade.get("spy_relative_leader") is True
    ]
    leader_targets = [
        trade for trade in leader_trades
        if trade.get("exit_reason") == "target"
    ]
    adjusted = [
        trade for trade in trades
        if trade.get("spy_leader_target_floor_applied") is not None
    ]
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "leader_trade_count": len(leader_trades),
        "leader_target_exit_count": len(leader_targets),
        "adjusted_trade_count": len(adjusted),
        "adjusted_pnl": round(sum(float(t.get("pnl") or 0.0) for t in adjusted), 2),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _run_window(universe: list[str], cfg: dict) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _install_target_floor(target_floor: float | None):
    original = risk_engine.enrich_signals

    if target_floor is None:
        return original

    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        adjusted = []
        for sig in enriched:
            ticker = sig.get("ticker")
            features = features_dict.get(ticker) or {}
            atr = features.get("atr")
            current_mult = sig.get("target_mult_used") or atr_target_mult
            if (
                sig.get("spy_relative_leader") is True
                and atr
                and (current_mult is None or current_mult < target_floor)
            ):
                sig = risk_engine._retarget_signal_with_atr_mult(
                    sig,
                    atr,
                    target_floor,
                )
                sig["spy_leader_target_floor_applied"] = target_floor
            adjusted.append(sig)
        return adjusted

    risk_engine.enrich_signals = wrapped
    return original


def _run_variant(universe: list[str], target_floor: float | None) -> OrderedDict:
    original = _install_target_floor(target_floor)
    try:
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            result = _run_window(universe, cfg)
            rows[label] = {
                "metrics": _metrics(result),
                "trades": result.get("trades", []),
            }
            m = rows[label]["metrics"]
            print(
                f"[{label}] spy_leader_target_floor={target_floor or 'baseline'} "
                f"EV={m['expected_value_score']} PnL={m['total_pnl']} "
                f"SharpeD={m['sharpe_daily']} DD={m['max_drawdown_pct']} "
                f"leader_trades={m['leader_trade_count']} adjusted={m['adjusted_trade_count']}"
            )
        return rows
    finally:
        risk_engine.enrich_signals = original


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS),
        2,
    )
    total_pnl_delta = round(
        sum(deltas[label]["total_pnl"] for label in WINDOWS),
        2,
    )
    ev_base = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(
        sum(deltas[label]["expected_value_score"] for label in WINDOWS),
        6,
    )
    return {
        "by_window": deltas,
        "baseline_expected_value_score_sum": ev_base,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / ev_base, 6) if ev_base else None,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_sum": total_pnl_delta,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6)
        if baseline_total_pnl else None,
        "ev_windows_improved": sum(
            1 for label in WINDOWS if deltas[label]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for label in WINDOWS if deltas[label]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for label in WINDOWS if deltas[label]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for label in WINDOWS if deltas[label]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": max(
            deltas[label]["max_drawdown_pct"] for label in WINDOWS
        ),
        "trade_count_delta_sum": sum(deltas[label]["trade_count"] for label in WINDOWS),
        "win_rate_delta_min": min(deltas[label]["win_rate"] for label in WINDOWS),
        "sharpe_daily_delta_max": max(
            deltas[label]["sharpe_daily"] for label in WINDOWS
        ),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.1:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    baseline = _run_variant(universe, None)
    variants = OrderedDict()
    aggregates = OrderedDict()
    for variant_name, target_floor in VARIANTS.items():
        rows = _run_variant(universe, target_floor)
        variants[variant_name] = rows
        aggregates[variant_name] = _aggregate(baseline, rows)

    best_variant = max(
        aggregates,
        key=lambda name: (
            aggregates[name]["expected_value_score_delta_sum"],
            aggregates[name]["total_pnl_delta_sum"],
        ),
    )
    accepted = _passes_gate4(aggregates[best_variant])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "exit_lifecycle_spy_relative_leader_target_floor",
        "hypothesis": (
            "SPY-relative leaders may still be lifecycle-clipped by the current "
            "regime-aware target width; applying a target floor only to 20-day "
            "ticker-vs-SPY leaders may improve winner capture without changing "
            "entry selection or capital allocation."
        ),
        "alpha_hypothesis_category": "exit_lifecycle",
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking remains blocked by sparse production-aligned "
            "outcome joins, so this run tests a deterministic replayable "
            "lifecycle variable instead."
        ),
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "notes": (
                "This uses the accepted SPY-relative leader discriminator but "
                "does not retest risk multipliers, initial cap, add-on cap, "
                "sector confirmation, absolute momentum floors, or second add-ons."
            ),
        },
        "parameters": {
            "single_causal_variable": "SPY-relative leader ATR target floor",
            "baseline": "accepted_stack",
            "tested_target_floors": dict(VARIANTS),
            "best_variant": best_variant,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all sizing constants",
                "SPY-relative leader risk budget",
                "SPY-relative leader initial position cap",
                "follow-through add-on trigger and caps",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            variant: {
                label: rows[label]["metrics"] for label in WINDOWS
            }
            for variant, rows in variants.items()
        },
        "delta_metrics": aggregates,
        "best_variant": best_variant,
        "best_variant_gate4": accepted,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If promoted, implement as constants.py + risk_engine.py shared "
                "target policy so run.py and backtester.py consume the same logic."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "gate4_passed": accepted,
        "gate4_basis": (
            "Accepted only if the best variant improves EV in at least two "
            "windows without EV regression and passes one standard Gate 4 "
            "materiality criterion."
        ),
        "rejection_reason": None if accepted else (
            "No tested SPY-relative leader target floor passed Gate 4 across "
            "the three canonical fixed windows."
        ),
        "next_retry_requires": [
            "Do not retry nearby SPY-relative leader target floors without event/news or lifecycle evidence.",
            "A valid retry needs a discriminator for which leaders deserve extra target room.",
            "Any promoted target policy must stay in shared risk policy for production/backtest parity.",
        ],
        "related_files": [
            "quant/experiments/exp_20260502_023_spy_leader_target_floor.py",
            "data/experiments/exp-20260502-023/spy_leader_target_floor.json",
            "docs/experiments/logs/exp-20260502-023.json",
            "docs/experiments/tickets/exp-20260502-023.json",
            "docs/experiment_log.jsonl",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "SPY leader target floor",
        "summary": (
            f"{payload['best_variant']} Gate4="
            f"{payload['best_variant_gate4']}"
        ),
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "production_impact": payload["production_impact"],
    }, indent=2) + "\n", encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "artifact": str(OUT_JSON),
        "log": str(LOG_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
