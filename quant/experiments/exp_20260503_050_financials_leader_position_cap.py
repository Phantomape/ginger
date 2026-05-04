"""exp-20260503-050 Financials sector-leader position cap.

Alpha search. The accepted Financials sector-leader trend sleeve already has a
2.5x risk budget. This tests one different causal variable: whether that
accepted sleeve is clipped by the global 40% initial-position cap. Entries,
exits, filters, ranking, risk multipliers, add-ons, LLM/news replay, and the
rest of sizing remain locked.
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

import backtester as bt  # noqa: E402
import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260503-050"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "financials_leader_position_cap.json"
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

BASELINE_CAP = 0.40
TESTED_CAPS = OrderedDict([
    ("financials_leader_cap_45pct", 0.45),
    ("financials_leader_cap_50pct", 0.50),
])
CAP_MULTIPLIER_KEY = "financials_sector_leader_position_cap_applied"

_state = {
    "position_cap": BASELINE_CAP,
    "leader_signals_seen": 0,
    "leader_signals_resized": 0,
}


def _is_financials_leader(sig: dict, sizing: dict) -> bool:
    return (
        sig.get("strategy") == "trend_long"
        and sig.get("sector") == "Financials"
        and sig.get("financials_sector_leader") is True
        and sizing.get("financials_sector_leader_risk_multiplier_applied", 1.0) != 1.0
    )


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
    position_cap = float(_state.get("position_cap") or BASELINE_CAP)
    if position_cap == BASELINE_CAP:
        return sized

    for sig in sized:
        sizing = sig.get("sizing") or {}
        if not _is_financials_leader(sig, sizing):
            continue
        _state["leader_signals_seen"] += 1

        entry = sig.get("entry_price")
        stop = sig.get("stop_price")
        risk = sizing.get("risk_pct")
        if entry is None or stop is None or risk is None:
            continue

        resized = pe.compute_position_size(
            portfolio_value,
            entry,
            stop,
            risk_pct=float(risk),
            max_position_pct=position_cap,
        )
        if not resized:
            continue
        if resized["shares_to_buy"] <= sizing.get("shares_to_buy", 0):
            continue

        merged = {**resized}
        for key, value in sizing.items():
            if key not in merged:
                merged[key] = value
        merged["max_position_pct_before_financials_leader_cap"] = sizing.get(
            "max_position_pct_applied"
        )
        merged["max_position_pct_applied"] = position_cap
        merged[CAP_MULTIPLIER_KEY] = position_cap
        merged["financials_sector_leader_position_cap_resized"] = True
        sig["sizing"] = merged
        _state["leader_signals_resized"] += 1
    return sized


def _install_patches():
    global _original_size_signals, _original_sizing_multiplier_keys
    _original_size_signals = pe.size_signals
    _original_sizing_multiplier_keys = bt.SIZING_MULTIPLIER_KEYS
    pe.size_signals = _patched_size_signals
    if CAP_MULTIPLIER_KEY not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (
            *bt.SIZING_MULTIPLIER_KEYS,
            CAP_MULTIPLIER_KEY,
        )


def _remove_patches():
    pe.size_signals = _original_size_signals
    bt.SIZING_MULTIPLIER_KEYS = _original_sizing_multiplier_keys


def _run_window(universe: list[str], cfg: dict, position_cap: float) -> dict:
    _state["position_cap"] = position_cap
    _state["leader_signals_seen"] = 0
    _state["leader_signals_resized"] = 0
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return {"metrics": _metrics(result), "trades": result.get("trades", [])}


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    leader_trade_count = 0
    leader_trade_pnl = 0.0
    cap_trade_count = 0
    cap_trade_pnl = 0.0
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        pnl = float(trade.get("pnl") or 0.0)
        if multipliers.get("financials_sector_leader_risk_multiplier_applied"):
            leader_trade_count += 1
            leader_trade_pnl += pnl
        if multipliers.get(CAP_MULTIPLIER_KEY):
            cap_trade_count += 1
            cap_trade_pnl += pnl
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "leader_signals_seen": _state["leader_signals_seen"],
        "leader_signals_resized": _state["leader_signals_resized"],
        "leader_trade_count": leader_trade_count,
        "leader_trade_pnl": round(leader_trade_pnl, 2),
        "cap_trade_count": cap_trade_count,
        "cap_trade_pnl": round(cap_trade_pnl, 2),
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


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    total_pnl_delta = round(sum(d["total_pnl"] for d in deltas.values()), 2)
    baseline_ev = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(sum(d["expected_value_score"] for d in deltas.values()), 6)
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_expected_value_score_sum": baseline_ev,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6) if baseline_total_pnl else None,
        "ev_windows_improved": sum(1 for d in deltas.values() if d["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for d in deltas.values() if d["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for d in deltas.values() if d["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for d in deltas.values() if d["total_pnl"] < 0),
        "max_drawdown_delta_max": max(d["max_drawdown_pct"] for d in deltas.values()),
        "trade_count_delta_sum": sum(d["trade_count"] for d in deltas.values()),
        "win_rate_delta_min": min(d["win_rate"] for d in deltas.values()),
        "sharpe_daily_delta_max": max(d["sharpe_daily"] for d in deltas.values()),
        "leader_signals_resized_delta_sum": sum(
            d["leader_signals_resized"] for d in deltas.values()
        ),
        "cap_trade_count_delta_sum": sum(d["cap_trade_count"] for d in deltas.values()),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.10:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    _install_patches()
    try:
        baseline = OrderedDict()
        for label, cfg in WINDOWS.items():
            baseline[label] = _run_window(universe, cfg, BASELINE_CAP)
            m = baseline[label]["metrics"]
            print(
                f"[{label} baseline] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} leader_trades={m['leader_trade_count']}"
            )

        variants = OrderedDict()
        for variant, cap in TESTED_CAPS.items():
            rows = OrderedDict()
            for label, cfg in WINDOWS.items():
                rows[label] = _run_window(universe, cfg, cap)
                m = rows[label]["metrics"]
                print(
                    f"[{label} {variant}] EV={m['expected_value_score']} "
                    f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                    f"cap_resized={m['leader_signals_resized']} "
                    f"cap_trades={m['cap_trade_count']}"
                )
            aggregate = _aggregate(baseline, rows)
            variants[variant] = {
                "position_cap": cap,
                "rows": rows,
                "aggregate": aggregate,
                "passes_gate4": _passes_gate4(aggregate),
            }
    finally:
        _remove_patches()

    best_variant, best = max(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["ev_windows_improved"],
            -item[1]["aggregate"]["ev_windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    accepted = best["passes_gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_financials_sector_leader_position_cap",
        "hypothesis": (
            "The accepted trend_long Financials sector-leader sleeve may be "
            "position-cap constrained after its 2.5x risk budget. A narrow "
            "higher initial-position cap may improve capital allocation without "
            "changing entries, exits, filters, rankings, or risk multipliers."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking data remains too thin, and Form 4 "
            "near-entry overlap was sparse, so this tests a deterministic "
            "already-accepted sleeve instead."
        ),
        "parameters": {
            "single_causal_variable": "trend_long Financials sector-leader initial position cap",
            "baseline_cap": BASELINE_CAP,
            "tested_caps": dict(TESTED_CAPS),
            "leader_definition": (
                "shared signal field financials_sector_leader == true, already "
                "used by the accepted 2.5x Financials leader risk policy"
            ),
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "accepted trend_long Financials sector-leader 2.5x risk budget",
                "all risk multipliers",
                "global MAX_POSITION_PCT for non-Financials-leader signals",
                "MAX_POSITIONS",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits",
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
            name: {label: variant["rows"][label]["metrics"] for label in WINDOWS}
            for name, variant in variants.items()
        },
        "delta_metrics": {
            name: variant["aggregate"] for name, variant in variants.items()
        },
        "best_variant": best_variant,
        "best_variant_gate4": accepted,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add a shared constant and size_signals branch in "
                "quant/portfolio_engine.py; run.py and backtester.py both call "
                "that shared policy."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this alpha search "
                "uses replayable deterministic fields."
            ),
        },
        "history_guardrails": {
            "builds_on_exp_20260501_006": True,
            "not_financials_leader_multiplier_retry": True,
            "not_financials_leader_target_retry": True,
            "not_global_position_cap_retry": True,
            "why_not_simple_repeat": (
                "This does not change the accepted 2.5x Financials leader risk "
                "multiplier or the rejected target-width family. It tests only "
                "whether that already-accepted sleeve is cap-bound."
            ),
        },
        "rejection_reason": None if accepted else (
            "No Financials sector-leader position-cap variant passed fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby Financials leader cap scalars without forward concentration evidence.",
            "A valid retry needs a materially different lifecycle or event discriminator.",
            "Any positive promotion must be implemented through shared production/backtest sizing policy.",
        ],
        "related_files": [
            "quant/experiments/exp_20260503_050_financials_leader_position_cap.py",
            "data/experiments/exp-20260503-050/financials_leader_position_cap.json",
            "docs/experiments/logs/exp-20260503-050.json",
            "docs/experiments/tickets/exp-20260503-050.json",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Financials leader position cap",
        "summary": (
            f"Best {payload['best_variant']} "
            f"Gate4={payload['best_variant_gate4']}"
        ),
        "best_variant": payload["best_variant"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "production_impact": payload["production_impact"],
    }, indent=2), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "best_gate4": payload["best_variant_gate4"],
        "best_delta": payload["delta_metrics"][payload["best_variant"]],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
