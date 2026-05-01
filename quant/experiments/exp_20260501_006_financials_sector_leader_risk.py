"""exp-20260501-006 Financials trend sector-leader risk budget.

Alpha search. The accepted trend_long Financials 1.5x sleeve is positive, but
the playbook blocks nearby scalar increases without a stricter discriminator.
This replay tests one causal variable: whether Financials trend signals whose
20-day return is above their sector's equal-weight 20-day return deserve a
higher risk budget. Entries, exits, ranking, filters, slots, heat, add-ons,
LLM/news replay, and the rest of sizing remain locked.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260501-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "financials_sector_leader_risk.json"
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

BASELINE_MULTIPLIER = 1.5
TESTED_MULTIPLIERS = OrderedDict([
    ("leader_2_0x", 2.0),
    ("leader_2_5x", 2.5),
])

_state = {
    "sim_dates": [],
    "sim_index": -1,
    "today_str": None,
    "leader_map": {},
    "target_multiplier": BASELINE_MULTIPLIER,
    "leader_signals_seen": 0,
    "leader_signals_resized": 0,
}


def _load_snapshot(snapshot_relpath: str) -> dict[str, pd.DataFrame]:
    payload = json.loads((REPO_ROOT / snapshot_relpath).read_text(encoding="utf-8"))
    out = {}
    for ticker, rows in payload["ohlcv"].items():
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        out[ticker] = df[["Open", "High", "Low", "Close", "Volume"]]
    return out


def _ret20(df: pd.DataFrame, today: pd.Timestamp) -> float | None:
    if today not in df.index:
        return None
    pos = df.index.get_loc(today)
    if isinstance(pos, slice) or pos < 20:
        return None
    start = float(df.iloc[pos - 20]["Close"])
    end = float(df.iloc[pos]["Close"])
    if start <= 0:
        return None
    return end / start - 1.0


def _compute_financials_leaders(cfg: dict) -> tuple[dict[str, set[str]], list[str]]:
    ohlcv = _load_snapshot(cfg["snapshot"])
    spy_dates = ohlcv["SPY"].loc[cfg["start"]:cfg["end"]].index
    leader_map: dict[str, set[str]] = {}
    financials = [
        ticker for ticker in ohlcv
        if SECTOR_MAP.get(ticker) == "Financials"
    ]
    for today in spy_dates:
        returns = {}
        for ticker in financials:
            ret = _ret20(ohlcv[ticker], today)
            if ret is not None:
                returns[ticker] = ret
        if not returns:
            continue
        sector_avg = sum(returns.values()) / len(returns)
        leaders = {
            ticker for ticker, ret in returns.items()
            if ret > sector_avg
        }
        leader_map[str(today.date())] = leaders
    return leader_map, [str(day.date()) for day in spy_dates]


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    leader_trade_count = 0
    leader_trade_pnl = 0.0
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        if multipliers.get("financials_sector_leader_risk_multiplier_applied"):
            leader_trade_count += 1
            leader_trade_pnl += float(trade.get("pnl") or 0.0)
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


def _patched_compute_portfolio_heat(open_positions, current_prices, portfolio_value, features_dict=None):
    _state["sim_index"] += 1
    idx = _state["sim_index"]
    if 0 <= idx < len(_state["sim_dates"]):
        _state["today_str"] = _state["sim_dates"][idx]
    return _original_compute_portfolio_heat(
        open_positions,
        current_prices,
        portfolio_value,
        features_dict=features_dict,
    )


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
    target_multiplier = _state.get("target_multiplier", BASELINE_MULTIPLIER)
    if target_multiplier == BASELINE_MULTIPLIER:
        return sized

    today_str = _state.get("today_str")
    leaders = (_state.get("leader_map") or {}).get(today_str, set())
    if not leaders:
        return sized

    scale = target_multiplier / BASELINE_MULTIPLIER
    for sig in sized:
        if (
            sig.get("strategy") == "trend_long"
            and sig.get("sector") == "Financials"
            and sig.get("ticker") in leaders
        ):
            _state["leader_signals_seen"] += 1
            sizing = sig.get("sizing") or {}
            if not sizing:
                continue
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            new_risk_pct = float(sizing.get("risk_pct") or 0.0) * scale
            new_sizing = pe.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=new_risk_pct,
            )
            if not new_sizing:
                continue
            for key, value in sizing.items():
                if key not in new_sizing:
                    new_sizing[key] = value
            new_sizing["financials_sector_leader_risk_multiplier_applied"] = (
                target_multiplier
            )
            sig["sizing"] = new_sizing
            _state["leader_signals_resized"] += 1
    return sized


def _install_patches():
    global _original_compute_portfolio_heat, _original_size_signals
    _original_compute_portfolio_heat = pe.compute_portfolio_heat
    _original_size_signals = pe.size_signals
    pe.compute_portfolio_heat = _patched_compute_portfolio_heat
    pe.size_signals = _patched_size_signals


def _remove_patches():
    pe.compute_portfolio_heat = _original_compute_portfolio_heat
    pe.size_signals = _original_size_signals


def _run_window(universe: list[str], cfg: dict, multiplier: float) -> dict:
    leader_map, sim_dates = _compute_financials_leaders(cfg)
    _state["sim_dates"] = sim_dates
    _state["sim_index"] = -1
    _state["today_str"] = None
    _state["leader_map"] = leader_map
    _state["target_multiplier"] = multiplier
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
            baseline[label] = _run_window(universe, cfg, BASELINE_MULTIPLIER)
            m = baseline[label]["metrics"]
            print(
                f"[{label} baseline] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']}"
            )

        variants = OrderedDict()
        for variant, multiplier in TESTED_MULTIPLIERS.items():
            rows = OrderedDict()
            for label, cfg in WINDOWS.items():
                rows[label] = _run_window(universe, cfg, multiplier)
                m = rows[label]["metrics"]
                print(
                    f"[{label} {variant}] EV={m['expected_value_score']} "
                    f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                    f"leader_resized={m['leader_signals_resized']}"
                )
            aggregate = _aggregate(baseline, rows)
            variants[variant] = {
                "multiplier": multiplier,
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
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_financials_sector_leader_risk",
        "hypothesis": (
            "The accepted trend_long Financials 1.5x sleeve may have a stronger "
            "sub-pocket when the ticker is outperforming its own sector over 20 "
            "trading days; that stricter discriminator may justify more risk "
            "without repeating a broad Financials scalar sweep."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking data remains too thin, so this tests "
            "a deterministic sector-relative allocation signal that can be "
            "computed in production and replay."
        ),
        "parameters": {
            "single_causal_variable": "trend_long Financials sector-leader risk multiplier",
            "baseline_multiplier": BASELINE_MULTIPLIER,
            "tested_multipliers": dict(TESTED_MULTIPLIERS),
            "sector_leader_definition": (
                "ticker 20-day close return > equal-weight Financials sector "
                "20-day close return on the signal day"
            ),
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "accepted trend_long Financials baseline 1.5x for non-leaders",
                "all other sizing multipliers",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits including gold 8ATR target",
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
                "If accepted, implement the sector-relative feature in shared "
                "portfolio policy and expose the same computation to run.py."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking is still sample-limited; this is an alternate "
                "deterministic alpha search."
            ),
        },
        "history_guardrails": {
            "not_broad_financials_multiplier_retry": True,
            "builds_on_exp_20260429_015": True,
            "builds_on_exp_20260429_030_sector_relative_audit": True,
            "not_sector_priority_ordering": True,
            "why_not_simple_repeat": (
                "The broad Financials 1.5x boost is already accepted and the "
                "playbook blocks nearby scalar increases. This test adds a "
                "sector-relative leader discriminator and keeps non-leaders at "
                "the accepted baseline."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "No Financials sector-leader risk variant passed fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby Financials sector-leader multipliers without forward evidence.",
            "A valid retry needs event/news context or a materially different sector-relative feature.",
            "If a future variant is accepted, implement it in shared production/backtest policy before promotion.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_006_financials_sector_leader_risk.py",
            "data/experiments/exp-20260501-006/financials_sector_leader_risk.json",
            "docs/experiments/logs/exp-20260501-006.json",
            "docs/experiments/tickets/exp-20260501-006.json",
        ],
    }
    return payload


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
        "title": "Financials sector-leader risk",
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
