"""exp-20260502-014 MFE-giveback SMA protection replay.

Default-off alpha experiment. It tests whether a path-aware lifecycle exit can
protect trades that first build meaningful MFE, then give back most of it while
closing below a short moving average. This is intentionally not a simple
breakeven stop retry: the trigger requires both prior favorable excursion and
fresh short-term path weakness.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260502-014"
OUT_DIR = os.path.join(REPO_ROOT, "data", "experiments", EXPERIMENT_ID)
OUT_JSON = os.path.join(OUT_DIR, "mfe_giveback_sma_exit.json")
LOG_JSON = os.path.join(REPO_ROOT, "docs", "experiments", "logs", f"{EXPERIMENT_ID}.json")
TICKET_JSON = os.path.join(REPO_ROOT, "docs", "experiments", "tickets", f"{EXPERIMENT_ID}.json")
EXPERIMENT_LOG = os.path.join(REPO_ROOT, "docs", "experiment_log.jsonl")

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape with lower win rate",
    }),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
INITIAL_CAPITAL = 100_000.0

VARIANTS = OrderedDict([
    ("mfe_05_giveback_60_sma5", {
        "min_mfe_pct": 0.05,
        "min_giveback_fraction": 0.60,
        "sma_days": 5,
    }),
    ("mfe_07_giveback_50_sma5", {
        "min_mfe_pct": 0.07,
        "min_giveback_fraction": 0.50,
        "sma_days": 5,
    }),
])


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _append_jsonl(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _date(row: dict) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def _value(row: dict, key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _load_snapshot(snapshot_path: str) -> dict[str, list[dict]]:
    payload = _load_json(os.path.join(REPO_ROOT, snapshot_path))
    return payload.get("ohlcv", payload)


def _trade_rows(snapshot: dict[str, list[dict]], trade: dict) -> list[dict]:
    rows = sorted(snapshot.get(trade.get("ticker"), []) or [], key=_date)
    entry = trade.get("entry_date")
    exit_ = trade.get("exit_date")
    return [row for row in rows if entry <= _date(row) <= exit_]


def _sma(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def _trigger(rows: list[dict], trade: dict, params: dict) -> dict | None:
    entry = trade.get("entry_price")
    if not isinstance(entry, (int, float)) or entry <= 0 or len(rows) < params["sma_days"] + 1:
        return None

    max_high = None
    closes: list[float] = []
    for idx, row in enumerate(rows[:-1]):
        high = _value(row, "High")
        close = _value(row, "Close")
        if high is not None:
            max_high = high if max_high is None else max(max_high, high)
        if close is None or max_high is None:
            continue
        closes.append(close)
        sma = _sma(closes, params["sma_days"])
        if sma is None:
            continue
        running_mfe = (max_high / entry) - 1.0
        close_return = (close / entry) - 1.0
        if running_mfe <= 0:
            continue
        giveback = (running_mfe - close_return) / running_mfe
        if (
            running_mfe >= params["min_mfe_pct"]
            and giveback >= params["min_giveback_fraction"]
            and close < sma
        ):
            next_row = rows[idx + 1]
            raw_open = _value(next_row, "Open")
            if raw_open is None:
                return None
            return {
                "trigger_date": _date(row),
                "exit_date": _date(next_row),
                "exit_raw_price": raw_open,
                "exit_price": apply_slippage(raw_open, SLIPPAGE_BPS_TARGET, "sell"),
                "running_mfe_pct": running_mfe,
                "close_return_pct": close_return,
                "giveback_fraction": giveback,
                "sma": sma,
                "close": close,
            }
    return None


def _replayed_trade(trade: dict, trigger: dict | None) -> tuple[dict, dict | None]:
    if not trigger:
        return dict(trade), None
    entry = trade.get("entry_price")
    shares = trade.get("shares")
    if not isinstance(entry, (int, float)) or not isinstance(shares, int):
        return dict(trade), None
    exit_price = trigger["exit_price"]
    new_pnl = (exit_price - entry) * shares - exit_price * ROUND_TRIP_COST_PCT * shares
    old_pnl = float(trade.get("pnl") or 0.0)
    replayed = dict(trade)
    replayed.update({
        "exit_date": trigger["exit_date"],
        "exit_price": round(exit_price, 2),
        "exit_raw_price": round(trigger["exit_raw_price"], 4),
        "exit_reason": "exp_mfe_giveback_sma_exit",
        "pnl": round(new_pnl, 2),
        "pnl_pct_net": round(((exit_price - entry) / entry) - ROUND_TRIP_COST_PCT, 6),
    })
    return replayed, {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "original_exit_date": trade.get("exit_date"),
        "original_exit_reason": trade.get("exit_reason"),
        "trigger_date": trigger["trigger_date"],
        "replay_exit_date": trigger["exit_date"],
        "running_mfe_pct": round(trigger["running_mfe_pct"], 6),
        "close_return_pct": round(trigger["close_return_pct"], 6),
        "giveback_fraction": round(trigger["giveback_fraction"], 6),
        "old_pnl": round(old_pnl, 2),
        "new_pnl": round(new_pnl, 2),
        "pnl_delta": round(new_pnl - old_pnl, 2),
        "winner_truncated": old_pnl > 0 and new_pnl < old_pnl,
    }


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def _metrics_from_trades(before: dict, trades: list[dict]) -> dict:
    total_pnl = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
    wins = sum(1 for trade in trades if (trade.get("pnl") or 0.0) > 0)
    total = len(trades)
    after = dict(before)
    after.update({
        "trades": trades,
        "total_trades": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate": round(wins / total, 4) if total else 0.0,
        "total_pnl": total_pnl,
        "benchmarks": {
            **(before.get("benchmarks") or {}),
            "strategy_total_return_pct": round(total_pnl / INITIAL_CAPITAL, 4),
        },
    })
    after["expected_value_score"] = compute_expected_value_score(after)
    return after


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key in before:
        a = after.get(key)
        b = before.get(key)
        out[key] = round((a or 0.0) - (b or 0.0), 6) if isinstance(a, (int, float)) or isinstance(b, (int, float)) else None
    return out


def _run_baseline(label: str, cfg: dict, universe: list[str]) -> tuple[dict, dict[str, list[dict]]]:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result, _load_snapshot(cfg["snapshot"])


def _run_variant(label: str, cfg: dict, baseline: dict, snapshot: dict[str, list[dict]], params: dict) -> dict:
    replayed = []
    events = []
    for trade in baseline.get("trades", []):
        rows = _trade_rows(snapshot, trade)
        trigger = _trigger(rows, trade, params)
        new_trade, event = _replayed_trade(trade, trigger)
        replayed.append(new_trade)
        if event:
            events.append(event)
    after = _metrics_from_trades(baseline, replayed)
    before_metrics = _metrics(baseline)
    after_metrics = _metrics(after)
    return {
        "window": {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "market_regime_summary": cfg["regime"],
        },
        "before": before_metrics,
        "after": after_metrics,
        "delta": _delta(after_metrics, before_metrics),
        "trigger_count": len(events),
        "winner_truncation_count": sum(1 for event in events if event["winner_truncated"]),
        "winner_truncation_pnl_delta": round(
            sum(event["pnl_delta"] for event in events if event["winner_truncated"]),
            2,
        ),
        "loser_improvement_pnl_delta": round(
            sum(event["pnl_delta"] for event in events if not event["winner_truncated"]),
            2,
        ),
        "events": events,
    }


def _aggregate(rows: dict[str, dict]) -> dict:
    baseline_ev = sum(row["before"]["expected_value_score"] or 0.0 for row in rows.values())
    variant_ev = sum(row["after"]["expected_value_score"] or 0.0 for row in rows.values())
    baseline_pnl = sum(row["before"]["total_pnl"] or 0.0 for row in rows.values())
    variant_pnl = sum(row["after"]["total_pnl"] or 0.0 for row in rows.values())
    return {
        "baseline_ev_sum": round(baseline_ev, 4),
        "variant_ev_sum": round(variant_ev, 4),
        "aggregate_ev_delta": round(variant_ev - baseline_ev, 4),
        "aggregate_ev_delta_pct": round((variant_ev - baseline_ev) / baseline_ev, 6) if baseline_ev else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "variant_pnl_sum": round(variant_pnl, 2),
        "aggregate_pnl_delta": round(variant_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((variant_pnl - baseline_pnl) / baseline_pnl, 6) if baseline_pnl else None,
        "windows_ev_improved": sum(1 for row in rows.values() if (row["delta"]["expected_value_score"] or 0.0) > 0),
        "windows_ev_regressed": sum(1 for row in rows.values() if (row["delta"]["expected_value_score"] or 0.0) < 0),
        "windows_pnl_improved": sum(1 for row in rows.values() if (row["delta"]["total_pnl"] or 0.0) > 0),
        "max_drawdown_delta_max": max((row["delta"]["max_drawdown_pct"] or 0.0) for row in rows.values()),
        "trigger_count": sum(row["trigger_count"] for row in rows.values()),
        "winner_truncation_count": sum(row["winner_truncation_count"] for row in rows.values()),
        "winner_truncation_pnl_delta": round(sum(row["winner_truncation_pnl_delta"] for row in rows.values()), 2),
        "loser_improvement_pnl_delta": round(sum(row["loser_improvement_pnl_delta"] for row in rows.values()), 2),
    }


def _gate4(aggregate: dict) -> bool:
    return (
        aggregate["windows_ev_improved"] >= 2
        and aggregate["windows_ev_regressed"] == 0
        and (
            (aggregate["aggregate_ev_delta_pct"] or 0.0) > 0.10
            or (aggregate["aggregate_pnl_delta_pct"] or 0.0) > 0.05
        )
    )


def _best_variant(variants: dict[str, dict]) -> str:
    def key(item: tuple[str, dict]) -> tuple[float, float]:
        agg = item[1]["aggregate"]
        return (agg["aggregate_ev_delta"], agg["aggregate_pnl_delta"])
    return max(variants.items(), key=key)[0]


def _compact_window(row: dict) -> dict:
    return {
        "before": row["before"],
        "after": row["after"],
        "delta": row["delta"],
        "trigger_count": row["trigger_count"],
        "winner_truncation_count": row["winner_truncation_count"],
    }


def main() -> int:
    universe = get_universe()
    baselines = {
        label: _run_baseline(label, cfg, universe)
        for label, cfg in WINDOWS.items()
    }
    variants = OrderedDict()
    for variant_name, params in VARIANTS.items():
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            baseline, snapshot = baselines[label]
            rows[label] = _run_variant(label, cfg, baseline, snapshot, params)
        aggregate = _aggregate(rows)
        aggregate["gate4_pass"] = _gate4(aggregate)
        variants[variant_name] = {
            "parameters": params,
            "rows": rows,
            "aggregate": aggregate,
        }
        print(
            f"{variant_name}: EV {aggregate['aggregate_ev_delta']:+.4f} "
            f"PnL {aggregate['aggregate_pnl_delta']:+.2f} "
            f"triggers={aggregate['trigger_count']} gate4={aggregate['gate4_pass']}"
        )

    best = _best_variant(variants)
    best_agg = variants[best]["aggregate"]
    decision = "accepted_candidate" if best_agg["gate4_pass"] else "rejected"
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": decision,
        "decision": "accepted" if decision == "accepted_candidate" else "rejected",
        "lane": "alpha_search",
        "alpha_hypothesis": (
            "A path-aware MFE-giveback trigger can protect trades that first prove "
            "they can move, then lose momentum, without repeating the rejected "
            "simple breakeven stop."
        ),
        "change_type": "exit_lifecycle_replay",
        "single_causal_variable": "MFE-giveback plus SMA breakdown protective exit trigger",
        "parameters": {
            "tested_variants": VARIANTS,
            "execution": "next available open after trigger close, target-side sell slippage",
            "default_off": True,
            "best_variant": best,
        },
        "date_range": {
            label: f"{cfg['start']} -> {cfg['end']}"
            for label, cfg in WINDOWS.items()
        },
        "market_regime_summary": {
            label: cfg["regime"]
            for label, cfg in WINDOWS.items()
        },
        "variants": variants,
        "best_variant": best,
        "best_variant_gate4": best_agg["gate4_pass"],
        "gate4_basis": (
            "Promotion requires EV improvement in at least 2/3 windows, no EV-regressed "
            "window, and >10% aggregate EV or >5% aggregate PnL improvement."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_behavior_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Production-aligned LLM outcome joins remain too sparse; this tests "
                "deterministic lifecycle context instead."
            ),
        },
        "history_guardrails": {
            "not_simple_breakeven_retry": (
                "Trigger requires meaningful MFE, giveback, and close below SMA, unlike "
                "exp-20260502-011 simple breakeven stop."
            ),
            "not_price_only_early_exit": (
                "Trigger requires prior MFE before weakness, unlike rejected day-5/day-10 "
                "weak-hold exits."
            ),
        },
        "rejection_reason": (
            None if best_agg["gate4_pass"]
            else "No tested MFE-giveback SMA protective exit passed the multi-window Gate 4 robustness bar."
        ),
        "next_retry_requires": [
            "Do not retry nearby MFE/giveback/SMA thresholds without event/news or stronger lifecycle evidence.",
            "A valid retry should explain winner collateral before promoting an executable shared exit.",
        ],
        "related_files": [
            os.path.relpath(OUT_JSON, REPO_ROOT),
            os.path.relpath(LOG_JSON, REPO_ROOT),
            os.path.relpath(TICKET_JSON, REPO_ROOT),
        ],
    }

    _write_json(OUT_JSON, artifact)
    _write_json(LOG_JSON, artifact)

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": artifact["generated_at"],
        "status": "rejected" if not best_agg["gate4_pass"] else "accepted_candidate",
        "title": "MFE-giveback SMA exit replay",
        "summary": artifact["alpha_hypothesis"],
        "best_variant": best,
        "best_variant_gate4": best_agg["gate4_pass"],
        "delta_metrics": {
            "baseline": {
                "expected_value_score_sum": best_agg["baseline_ev_sum"],
                "total_pnl_sum": best_agg["baseline_pnl_sum"],
            },
            "variant": {
                "expected_value_score_sum": best_agg["variant_ev_sum"],
                "total_pnl_sum": best_agg["variant_pnl_sum"],
            },
            **best_agg,
            "by_window": {
                label: _compact_window(row)
                for label, row in variants[best]["rows"].items()
            },
        },
        "next_action": (
            "Promote only after implementing this as shared production/backtest policy."
            if best_agg["gate4_pass"]
            else "Keep exit policy unchanged; do not retry nearby thresholds without new evidence."
        ),
        "log_file": os.path.relpath(LOG_JSON, REPO_ROOT),
    }
    _write_json(TICKET_JSON, ticket)

    log_row = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": artifact["generated_at"],
        "status": "accepted" if best_agg["gate4_pass"] else "rejected",
        "decision": "accepted" if best_agg["gate4_pass"] else "rejected",
        "hypothesis": artifact["alpha_hypothesis"],
        "change_summary": "Default-off replay of MFE-giveback plus SMA protective exit.",
        "change_type": artifact["change_type"],
        "component": "quant/exp_20260502_014_mfe_giveback_sma_exit.py",
        "parameters": artifact["parameters"],
        "date_range": artifact["date_range"],
        "market_regime_summary": artifact["market_regime_summary"],
        "before_metrics": ticket["delta_metrics"]["baseline"],
        "after_metrics": ticket["delta_metrics"]["variant"],
        "delta_metrics": best_agg,
        "llm_metrics": artifact["llm_metrics"],
        "production_impact": artifact["production_impact"],
        "rejection_reason": artifact["rejection_reason"],
        "next_retry_requires": artifact["next_retry_requires"],
        "related_files": artifact["related_files"],
    }
    _append_jsonl(EXPERIMENT_LOG, log_row)

    print(f"best={best} decision={artifact['decision']} wrote={OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
