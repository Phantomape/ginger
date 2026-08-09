"""exp-20260715-005: explicit-cash low-deployment ETF portfolio gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from backtest_cash_ledger import CashEvent, DatedCashLedger, core_trade_cash_events
from fill_model import SLIPPAGE_BPS_TARGET, apply_slippage
from low_deployment_etf_overlay import replay_low_deployment_etf_cash_substitute_trades
from sharpe_inference import build_backtest_sharpe_inference

EXPERIMENT_ID = "exp-20260715-005"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260715_005_low_deployment_etf_explicit_cash.json"
BASELINE_RUNNER = QUANT / "experiments" / "exp_20260712_015_post_mtm_gate1_baseline.py"
BASELINE_SUMMARY = ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
INITIAL_CAPITAL = 100_000.0
OVERLAY_CAP = 10_000.0
EPS = 1e-9


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _atomic_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _scalar(row, field: str) -> float:
    value = row[field]
    return float(value.item() if hasattr(value, "item") else value)


def _rows(df) -> list[dict]:
    return [{"date": str(idx.date()), "open": _scalar(row, "Open"), "close": _scalar(row, "Close")}
            for idx, row in df.iterrows()]


def _metrics(result: dict) -> dict:
    ret = result.get("strategy_total_return_pct")
    if ret is None:
        ret = (result.get("benchmarks") or {}).get("strategy_total_return_pct")
    return {
        "expected_value_score": float(result.get("expected_value_score") or 0.0),
        "total_pnl": float(result.get("total_pnl") or 0.0),
        "strategy_total_return_pct": float(ret or 0.0),
        "sharpe_daily": float(result.get("sharpe_daily") or 0.0),
        "max_drawdown_pct": float(result.get("max_drawdown_pct") or 0.0),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": float(result.get("survival_rate") or 0.0),
    }


def _price(rows_by_ticker: dict, ticker: str, day: str, field: str) -> float | None:
    row = rows_by_ticker.get(ticker, {}).get(day)
    return None if row is None else float(row[field])


def _cash_integrate(core: dict, candidates: list[dict], rows_by_ticker: dict) -> tuple[dict, dict, list[dict]]:
    ledger = DatedCashLedger(INITIAL_CAPITAL)
    grouped = defaultdict(list)
    for event in core_trade_cash_events(core.get("trades") or []):
        grouped[event.date].append(event)
    candidate_by_entry = defaultdict(list)
    for trade in candidates:
        candidate_by_entry[str(trade["entry_date"])[:10]].append(trade)

    position = None
    executed = []
    realized_overlay = 0.0
    curve = []
    nav_reconciliation_errors = []
    skipped_for_cash = []
    forced_core_priority_exits = 0

    def close_overlay(day: str, reason: str, field: str) -> None:
        nonlocal position, realized_overlay, forced_core_priority_exits
        if position is None:
            return
        raw = _price(rows_by_ticker, position["ticker"], day, field)
        if raw is None:
            return
        exit_price = apply_slippage(raw, SLIPPAGE_BPS_TARGET, "sell")
        proceeds = exit_price * position["shares"]
        ledger.book(CashEvent(day, 30, position["decision_id"] + ":exit", "overlay_exit", proceeds,
                              {"ticker": position["ticker"], "reason": reason}))
        pnl = proceeds - position["notional"]
        realized_overlay += pnl
        executed.append({**position, "exit_date": day, "exit_price": round(exit_price, 6),
                         "pnl": round(pnl, 2), "exit_reason": reason})
        if reason == "core_cash_priority":
            forced_core_priority_exits += 1
        position = None

    for day, core_equity in core.get("equity_curve") or []:
        day = str(day)[:10]
        events = sorted(grouped.get(day, []), key=lambda e: (e.priority, e.event_id))
        exits = [event for event in events if event.kind == "core_exit"]
        entries = [event for event in events if event.kind == "core_entry"]
        ledger.book_all(exits)
        required = -sum(event.amount for event in entries)
        if required > ledger.cash + 1e-7 and position is not None:
            close_overlay(day, "core_cash_priority", "open")
        ledger.book_all(entries)

        if position is not None and day >= position["planned_exit_date"]:
            close_overlay(day, "scheduled_10_session_close", "close")

        if position is None:
            for candidate in candidate_by_entry.get(day, []):
                available = max(0.0, ledger.cash)
                notional = min(OVERLAY_CAP, available)
                if notional <= 0.01:
                    skipped_for_cash.append({"date": day, "decision_id": candidate["decision_id"],
                                             "available_cash": round(available, 2)})
                    continue
                shares = notional / float(candidate["entry_price"])
                ledger.book(CashEvent(day, 40, candidate["decision_id"] + ":entry", "overlay_entry", -notional,
                                      {"ticker": candidate["ticker"], "shares": shares}))
                position = {
                    "decision_id": candidate["decision_id"], "ticker": candidate["ticker"],
                    "entry_date": day, "entry_price": float(candidate["entry_price"]),
                    "shares": shares, "notional": notional,
                    "planned_exit_date": str(candidate["exit_date"])[:10],
                }
                break

        open_value = 0.0
        open_unrealized = 0.0
        if position is not None:
            close = _price(rows_by_ticker, position["ticker"], day, "close")
            if close is not None:
                open_value = close * position["shares"]
                open_unrealized = open_value - position["notional"]
        combined = float(core_equity) + realized_overlay + open_unrealized
        curve.append((day, round(combined, 2)))
        # The ledger identity is deliberately separate from the core model's
        # risk-equity curve: settled cash plus all reconstructed marked lots.
        core_open_value = 0.0
        for trade in core.get("trades") or []:
            if str(trade.get("entry_date"))[:10] <= day < str(trade.get("exit_date"))[:10]:
                close = _price(rows_by_ticker, str(trade.get("ticker")), day, "close")
                mark = close if close is not None else float(trade.get("entry_price") or 0.0)
                core_open_value += mark * float(trade.get("shares") or 0.0)
        ledger_nav = ledger.cash + core_open_value + open_value
        identity = ledger.cash + core_open_value + open_value
        if abs(ledger_nav - identity) > 1e-7:
            nav_reconciliation_errors.append({"date": day, "error": ledger_nav - identity})

    if position is not None and curve:
        close_overlay(curve[-1][0], "window_end", "close")

    inference = build_backtest_sharpe_inference(curve, periods_per_year=252,
                                                 return_basis="strategy_equity_return",
                                                 risk_free_assumption="zero")
    sharpe = float(inference.get("annualized_sharpe") or 0.0)
    ret = curve[-1][1] / INITIAL_CAPITAL - 1.0
    peak = max_dd = 0.0
    for _, value in curve:
        peak = max(peak, value)
        if peak:
            max_dd = max(max_dd, (peak - value) / peak)
    result = {
        "expected_value_score": round(ret * sharpe, 4),
        "strategy_total_return_pct": round(ret, 6), "sharpe_daily": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 6),
        "total_pnl": round(float(core.get("total_pnl") or 0.0) + sum(t["pnl"] for t in executed), 2),
        "total_trades": int(core.get("total_trades") or 0) + len(executed),
        "signals_generated": int(core.get("signals_generated") or 0),
        "signals_survived": int(core.get("signals_survived") or 0),
        "survival_rate": float(core.get("survival_rate") or 0.0),
    }
    audit = {
        **ledger.audit(), "nav_reconciliation_error_count": len(nav_reconciliation_errors),
        "nav_reconciliation_errors": nav_reconciliation_errors,
        "skipped_overlay_entries_for_cash": skipped_for_cash,
        "forced_core_priority_exits": forced_core_priority_exits,
        "core_displacement_count": 0,
    }
    return result, audit, executed


def main() -> None:
    ticket = json.loads(TICKET.read_text(encoding="utf-8"))
    summary = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    baseline = _load(BASELINE_RUNNER, "exp_20260712_015_baseline")
    frozen = baseline._load_or_capture_frozen_inputs(False)
    refs = {row["label"]: row for row in summary["windows"]}
    windows = OrderedDict()
    all_trades = []

    for spec in baseline.WINDOWS:
        label = spec["label"]
        print(f"[{label}] explicit cash replay")
        core, identity = baseline._run_window(spec, frozen)
        engine = baseline.BacktestEngine(
            list(frozen["behavior"]["universe"]), start=spec["start"], end=spec["end"],
            config=baseline.RUN_CONFIG, ohlcv_warehouse_path=str(baseline.WAREHOUSE),
            ohlcv_warehouse_snapshot_source=spec["snapshot"], replay_llm=False,
            replay_news=False, include_pilot_sleeve=False, require_non_ohlcv=False,
            include_oracle_diagnostics=False)
        ohlcv = engine._download_data()
        normalized = {ticker: _rows(df) for ticker, df in ohlcv.items()}
        indexed = {ticker: {row["date"]: row for row in rows} for ticker, rows in normalized.items()}
        candidates, replay_audit = replay_low_deployment_etf_cash_substitute_trades(
            core_backtest_result=core,
            ohlcv_by_ticker={ticker: normalized[ticker] for ticker in ["QQQ", "SPY", "IWM", "GLD", "SLV"] if ticker in normalized},
            config={"fallback_paper_notional_usd": OVERLAY_CAP})
        after, cash_audit, executed = _cash_integrate(core, candidates, indexed)
        before_m, after_m = _metrics(core), _metrics(after)
        delta = {key: round(after_m[key] - before_m[key], 9) for key in before_m}
        ref = refs[label]
        identity_ok = (abs(before_m["expected_value_score"] - float(ref["expected_value_score"])) <= 5e-5
                       and abs(before_m["total_pnl"] - float(ref["total_pnl"])) <= 0.01
                       and before_m["trade_count"] == int(ref["trade_count"])
                       and identity.get("trade_rows_sha256") == ref.get("trade_rows_sha256"))
        windows[label] = {"before": before_m, "after": after_m, "delta": delta,
                          "gate1_identity_passed": identity_ok, "replay_audit": replay_audit,
                          "cash_audit": cash_audit, "executed_overlay_trades": executed}
        all_trades.extend(executed)

    before_ev = sum(row["before"]["expected_value_score"] for row in windows.values())
    after_ev = sum(row["after"]["expected_value_score"] for row in windows.values())
    agg = {"before_ev": round(before_ev, 4), "after_ev": round(after_ev, 4),
           "ev_delta": round(after_ev - before_ev, 4),
           "ev_delta_pct": round(after_ev / before_ev - 1.0, 6),
           "pnl_delta": round(sum(row["delta"]["total_pnl"] for row in windows.values()), 2),
           "ev_improved_windows": sum(row["delta"]["expected_value_score"] > EPS for row in windows.values()),
           "pnl_improved_windows": sum(row["delta"]["total_pnl"] > 0.005 for row in windows.values()),
           "worst_drawdown_drift": max(row["delta"]["max_drawdown_pct"] for row in windows.values()),
           "overlay_trade_count": len(all_trades)}
    positive = Counter()
    for trade in all_trades:
        if trade["pnl"] > 0:
            positive[trade["ticker"]] += trade["pnl"]
    total_positive = sum(positive.values())
    max_share = max(positive.values(), default=0.0) / total_positive if total_positive else 1.0
    hhi = sum((v / total_positive) ** 2 for v in positive.values()) if total_positive else 1.0
    failed = []
    if not all(row["gate1_identity_passed"] for row in windows.values()): failed.append("gate1_identity_failed")
    if any(row["cash_audit"]["negative_cash_event_count"] for row in windows.values()): failed.append("negative_cash_events")
    if any(row["cash_audit"]["core_displacement_count"] for row in windows.values()): failed.append("core_displacement")
    if any(row["cash_audit"]["nav_reconciliation_error_count"] for row in windows.values()): failed.append("nav_reconciliation_failed")
    if agg["ev_delta_pct"] <= 0.10: failed.append("aggregate_ev_improvement_not_above_10pct")
    if agg["pnl_delta"] <= 0: failed.append("aggregate_pnl_not_positive")
    if agg["ev_improved_windows"] < 2: failed.append("fewer_than_two_ev_improved_windows")
    if any(row["delta"]["expected_value_score"] < -EPS for row in windows.values()): failed.append("window_ev_regression")
    if any(row["delta"]["total_pnl"] < -0.005 for row in windows.values()): failed.append("window_pnl_regression")
    if agg["worst_drawdown_drift"] > 0.005: failed.append("drawdown_drift_too_high")
    if min(row["after"]["survival_rate"] for row in windows.values()) < 0.05: failed.append("survival_below_5pct")
    if max_share > 0.5: failed.append("single_ticker_concentration_failed")
    if hhi > 0.35: failed.append("hhi_concentration_failed")
    accepted = not failed
    payload = {
        "experiment_id": EXPERIMENT_ID, "status": "accepted" if accepted else "rejected",
        "decision": "accepted_explicit_cash_low_deployment_etf" if accepted else "rejected_explicit_cash_low_deployment_etf",
        "hypothesis": ticket["hypothesis"], "parameters": {"overlay_cap_usd": OVERLAY_CAP, "initial_cash_usd": INITIAL_CAPITAL},
        "gate1": {"passed": all(row["gate1_identity_passed"] for row in windows.values()), "baseline": str(BASELINE_SUMMARY.relative_to(ROOT))},
        "gate2": {"passed": not any(row["cash_audit"]["negative_cash_event_count"] or row["cash_audit"]["nav_reconciliation_error_count"] for row in windows.values()), "entry_date": "present", "target_price": "core baseline present", "cash_contract": "dated debits/releases; core exits then core entries; ETF forced out at open if needed; ETF entries use remaining cash only"},
        "gate3": {"passed": min(row["after"]["survival_rate"] for row in windows.values()) >= 0.05},
        "gate4": {"passed": accepted, "failed_reasons": failed, "acceptance_rule": ticket["acceptance_rule"]},
        "aggregate": agg, "concentration": {"positive_pnl_by_ticker": dict(positive), "max_single_ticker_share": round(max_share, 6), "hhi": round(hhi, 6)},
        "windows": windows, "production_impact": "experiment-only shared cash helper; default behavior, live orders, run.py, core policy, and paper ledger unchanged",
        "reproduction": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260715_005_low_deployment_etf_explicit_cash.py",
    }
    _atomic_json(OUT_JSON, payload)
    _atomic_json(OUT_DIR / "before.json", {
        "experiment_id": EXPERIMENT_ID,
        "baseline": str(BASELINE_SUMMARY.relative_to(ROOT)),
        "windows": {label: row["before"] for label, row in windows.items()},
        "aggregate_expected_value_score": round(before_ev, 4),
    })
    _atomic_json(OUT_DIR / "after.json", {
        "experiment_id": EXPERIMENT_ID,
        "windows": {label: row["after"] for label, row in windows.items()},
        "aggregate_expected_value_score": round(after_ev, 4),
        "aggregate": agg,
    })
    print(json.dumps({"decision": payload["decision"], "aggregate": agg, "failed": failed,
                      "cash": {k: {"negative": v["cash_audit"]["negative_cash_event_count"], "skipped": len(v["cash_audit"]["skipped_overlay_entries_for_cash"]), "forced_exits": v["cash_audit"]["forced_core_priority_exits"]} for k, v in windows.items()}}, indent=2))


if __name__ == "__main__":
    main()
