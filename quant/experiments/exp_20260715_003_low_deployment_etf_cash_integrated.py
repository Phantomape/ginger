"""exp-20260715-003: cash-only low-deployment ETF portfolio replay."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from low_deployment_etf_overlay import replay_low_deployment_etf_cash_substitute_trades
from sharpe_inference import build_backtest_sharpe_inference

EXPERIMENT_ID = "exp-20260715-003"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260715_003_low_deployment_etf_cash_integrated.json"
BASELINE_RUNNER = QUANT / "experiments" / "exp_20260712_015_post_mtm_gate1_baseline.py"
BASELINE_SUMMARY = ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
INITIAL_CAPITAL = 100_000.0
OVERLAY_NOTIONAL = 10_000.0
EPS = 1e-9


def _load_baseline_module():
    spec = importlib.util.spec_from_file_location("exp_20260712_015_baseline", BASELINE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load active baseline runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _rows(df) -> list[dict[str, Any]]:
    out = []
    for idx, row in df.iterrows():
        out.append({
            "date": str(idx.date()),
            "open": float(row["Open"].item() if hasattr(row["Open"], "item") else row["Open"]),
            "close": float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"]),
        })
    return out


def _metric_projection(result: dict[str, Any]) -> dict[str, Any]:
    strategy_return = result.get("strategy_total_return_pct")
    if strategy_return is None:
        strategy_return = (result.get("benchmarks") or {}).get("strategy_total_return_pct")
    return {
        "expected_value_score": float(result.get("expected_value_score") or 0.0),
        "total_pnl": float(result.get("total_pnl") or 0.0),
        "strategy_total_return_pct": float(strategy_return or 0.0),
        "sharpe_daily": float(result.get("sharpe_daily") or 0.0),
        "max_drawdown_pct": float(result.get("max_drawdown_pct") or 0.0),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": float(result.get("survival_rate") or 0.0),
    }


def _overlay_value_on(day: str, trade: dict[str, Any], rows_by_ticker: dict[str, list[dict[str, Any]]]) -> float:
    if day < trade["entry_date"]:
        return 0.0
    if day >= trade["exit_date"]:
        return float(trade["pnl"])
    close_by_date = {row["date"]: float(row["close"]) for row in rows_by_ticker[trade["ticker"]]}
    close = close_by_date.get(day)
    if close is None:
        return 0.0
    return OVERLAY_NOTIONAL * (close / float(trade["entry_price"]) - 1.0)


def _active_core_entry_basis(result: dict[str, Any], day: str) -> float:
    total = 0.0
    for trade in result.get("trades") or []:
        if trade.get("strategy") not in {"trend_long", "breakout_long"}:
            continue
        if str(trade.get("entry_date"))[:10] <= day <= str(trade.get("exit_date"))[:10]:
            total += float(trade.get("entry_price") or 0.0) * float(trade.get("shares") or 0.0)
    return total


def _integrate(core: dict[str, Any], trades: list[dict[str, Any]], rows_by_ticker: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], dict[str, Any]]:
    curve = []
    cash_violations = []
    for day, core_equity in core.get("equity_curve") or []:
        overlay_pnl = sum(_overlay_value_on(str(day), trade, rows_by_ticker) for trade in trades)
        curve.append((str(day), round(float(core_equity) + overlay_pnl, 2)))
        open_overlay = [t for t in trades if t["entry_date"] <= str(day) < t["exit_date"]]
        if open_overlay:
            core_basis = _active_core_entry_basis(core, str(day))
            if core_basis + OVERLAY_NOTIONAL > float(core_equity) + 0.01:
                cash_violations.append({"date": str(day), "core_entry_basis": round(core_basis, 2), "core_equity": float(core_equity)})

    inference = build_backtest_sharpe_inference(curve, periods_per_year=252, return_basis="strategy_equity_return", risk_free_assumption="zero")
    sharpe = float(inference.get("annualized_sharpe") or 0.0)
    ret = curve[-1][1] / INITIAL_CAPITAL - 1.0
    peak = 0.0
    max_dd = 0.0
    for _, value in curve:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)
    overlay_pnl = round(sum(float(t["pnl"]) for t in trades), 2)
    result = {
        "expected_value_score": round(ret * sharpe, 4),
        "strategy_total_return_pct": round(ret, 6),
        "sharpe_daily": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 6),
        "total_pnl": round(float(core.get("total_pnl") or 0.0) + overlay_pnl, 2),
        "total_trades": int(core.get("total_trades") or 0) + len(trades),
        "signals_generated": int(core.get("signals_generated") or 0),
        "signals_survived": int(core.get("signals_survived") or 0),
        "survival_rate": float(core.get("survival_rate") or 0.0),
        "sharpe_inference": inference,
    }
    audit = {
        "overlay_trade_count": len(trades),
        "overlay_pnl": overlay_pnl,
        "cash_violations": cash_violations,
        "no_leverage_no_displacement_passed": not cash_violations,
    }
    return result, audit


def main() -> None:
    ticket = json.loads(TICKET.read_text(encoding="utf-8"))
    summary = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    baseline = _load_baseline_module()
    frozen = baseline._load_or_capture_frozen_inputs(False)
    summary_by_label = {row["label"]: row for row in summary["windows"]}
    windows = OrderedDict()
    all_overlay_trades = []

    for spec in baseline.WINDOWS:
        label = spec["label"]
        print(f"[{label}] frozen post-MTM replay")
        core, identity = baseline._run_window(spec, frozen)
        engine = baseline.BacktestEngine(
            list(frozen["behavior"]["universe"]), start=spec["start"], end=spec["end"],
            config=baseline.RUN_CONFIG, ohlcv_warehouse_path=str(baseline.WAREHOUSE),
            ohlcv_warehouse_snapshot_source=spec["snapshot"], replay_llm=False,
            replay_news=False, include_pilot_sleeve=False, require_non_ohlcv=False,
            include_oracle_diagnostics=False,
        )
        ohlcv = engine._download_data()
        rows_by_ticker = {ticker: _rows(ohlcv[ticker]) for ticker in ["QQQ", "SPY", "IWM", "GLD", "SLV"] if ticker in ohlcv}
        overlay_trades, replay_audit = replay_low_deployment_etf_cash_substitute_trades(
            core_backtest_result=core, ohlcv_by_ticker=rows_by_ticker,
            config={"fallback_paper_notional_usd": OVERLAY_NOTIONAL},
        )
        after, cash_audit = _integrate(core, overlay_trades, rows_by_ticker)
        before = _metric_projection(core)
        after_m = _metric_projection(after)
        delta = {key: round(after_m[key] - before[key], 9) for key in before}
        ref = summary_by_label[label]
        identity_passed = (
            abs(before["expected_value_score"] - float(ref["expected_value_score"])) <= 5e-5
            and abs(before["total_pnl"] - float(ref["total_pnl"])) <= 0.01
            and before["trade_count"] == int(ref["trade_count"])
            and identity.get("trade_rows_sha256") == ref.get("trade_rows_sha256")
        )
        windows[label] = {
            "before": before, "after": after_m, "delta": delta,
            "gate1_identity_passed": identity_passed,
            "replay_audit": replay_audit, "cash_audit": cash_audit,
            "overlay_trades": overlay_trades,
        }
        all_overlay_trades.extend(overlay_trades)

    agg_before_ev = sum(row["before"]["expected_value_score"] for row in windows.values())
    agg_after_ev = sum(row["after"]["expected_value_score"] for row in windows.values())
    agg = {
        "before_ev": round(agg_before_ev, 4), "after_ev": round(agg_after_ev, 4),
        "ev_delta": round(agg_after_ev - agg_before_ev, 4),
        "ev_delta_pct": round((agg_after_ev / agg_before_ev - 1.0), 6),
        "pnl_delta": round(sum(row["delta"]["total_pnl"] for row in windows.values()), 2),
        "ev_improved_windows": sum(row["delta"]["expected_value_score"] > EPS for row in windows.values()),
        "pnl_improved_windows": sum(row["delta"]["total_pnl"] > 0.005 for row in windows.values()),
        "worst_drawdown_drift": max(row["delta"]["max_drawdown_pct"] for row in windows.values()),
        "overlay_trade_count": len(all_overlay_trades),
    }
    positive = Counter()
    for trade in all_overlay_trades:
        if float(trade["pnl"]) > 0:
            positive[trade["ticker"]] += float(trade["pnl"])
    positive_total = sum(positive.values())
    max_share = max(positive.values(), default=0.0) / positive_total if positive_total else 1.0
    hhi = sum((value / positive_total) ** 2 for value in positive.values()) if positive_total else 1.0
    concentration = {"positive_pnl_by_ticker": dict(positive), "max_single_ticker_share": round(max_share, 6), "hhi": round(hhi, 6)}
    failed = []
    if not all(row["gate1_identity_passed"] for row in windows.values()): failed.append("gate1_identity_failed")
    if agg["ev_delta_pct"] <= 0.10: failed.append("aggregate_ev_improvement_not_above_10pct")
    if agg["pnl_delta"] <= 0: failed.append("aggregate_pnl_not_positive")
    if agg["ev_improved_windows"] < 2: failed.append("fewer_than_two_ev_improved_windows")
    if any(row["delta"]["expected_value_score"] < -EPS for row in windows.values()): failed.append("window_ev_regression")
    if any(row["delta"]["total_pnl"] < -0.005 for row in windows.values()): failed.append("window_pnl_regression")
    if agg["worst_drawdown_drift"] > 0.005: failed.append("drawdown_drift_too_high")
    if min(row["after"]["survival_rate"] for row in windows.values()) < 0.05: failed.append("survival_below_5pct")
    if any(not row["cash_audit"]["no_leverage_no_displacement_passed"] for row in windows.values()): failed.append("cash_only_no_displacement_failed")
    if max_share > 0.5: failed.append("single_ticker_concentration_failed")
    if hhi > 0.35: failed.append("hhi_concentration_failed")
    accepted = not failed
    payload = {
        "experiment_id": EXPERIMENT_ID, "status": "accepted" if accepted else "rejected",
        "decision": "accepted_cash_only_low_deployment_etf_10pct" if accepted else "rejected_cash_only_low_deployment_etf_10pct",
        "hypothesis": ticket["hypothesis"], "parameters": {"overlay_notional_usd": OVERLAY_NOTIONAL, "initial_capital_usd": INITIAL_CAPITAL, "capital_fraction": 0.10},
        "gate1": {"passed": all(row["gate1_identity_passed"] for row in windows.values()), "baseline": str(BASELINE_SUMMARY.relative_to(ROOT))},
        "gate2": {"passed": not any(row["cash_audit"]["cash_violations"] for row in windows.values()), "entry_date": "present", "target_price": "core baseline present", "daily_cash_proxy": "failed: the current core backtester has no explicit cash debit/reservation ledger, and reconstructed active entry basis plus overlay notional exceeds contemporaneous equity on some dates"},
        "gate3": {"passed": min(row["after"]["survival_rate"] for row in windows.values()) >= 0.05},
        "gate4": {"passed": accepted, "failed_reasons": failed, "acceptance_rule": ticket["acceptance_rule"]},
        "aggregate": agg, "concentration": concentration, "windows": windows,
        "production_impact": "experiment-only; no live orders, run.py, core policy, or paper ledger changed",
        "reproduction": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260715_003_low_deployment_etf_cash_integrated.py",
    }
    _atomic_json(OUT_JSON, payload)
    print(json.dumps({"decision": payload["decision"], "aggregate": agg, "failed": failed, "concentration": concentration}, indent=2))


if __name__ == "__main__":
    main()
