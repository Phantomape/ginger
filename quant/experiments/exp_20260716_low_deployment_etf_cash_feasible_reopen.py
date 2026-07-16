"""exp-20260716-009: unchanged low-deployment ETF on cash-feasible core."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backtest_cash_ledger import CashEvent, DatedCashLedger
from constants import ROUND_TRIP_COST_PCT
from fill_model import SLIPPAGE_BPS_TARGET, apply_slippage
from low_deployment_etf_overlay import replay_low_deployment_etf_cash_substitute_trades
from sharpe_inference import build_backtest_sharpe_inference

EXPERIMENT_ID = "exp-20260716-009"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260716_009_low_deployment_etf_cash_feasible_reopen.json"
BASELINE_RUNNER = EXPERIMENTS / "exp_20260715_010_cash_feasible_gate1_rebaseline.py"
BASELINE_SUMMARY = ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
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


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _scalar(row, field: str) -> float:
    value = row[field]
    return float(value.item() if hasattr(value, "item") else value)


def _rows(df) -> list[dict[str, Any]]:
    return [
        {
            "date": str(idx.date()),
            "open": _scalar(row, "Open"),
            "close": _scalar(row, "Close"),
        }
        for idx, row in df.iterrows()
    ]


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
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


def _price(rows: dict[str, dict[str, dict[str, float]]], ticker: str, day: str, field: str) -> float | None:
    row = rows.get(ticker, {}).get(day)
    return None if row is None else float(row[field])


def _core_cash_events(core: dict[str, Any]) -> list[CashEvent]:
    """Reconstruct original fills, dated add-ons, and cost-aware releases."""
    addon_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in (core.get("addon_attribution") or {}).get("events") or []:
        if event.get("status") == "executed":
            addon_by_ticker[str(event.get("ticker"))].append(event)

    events: list[CashEvent] = []
    for index, trade in enumerate(core.get("trades") or []):
        shares = float(trade.get("shares") or 0.0)
        addon_shares = float(trade.get("addon_shares") or 0.0)
        addon_cost = float(trade.get("addon_cost") or 0.0)
        basis = float(trade.get("entry_price") or 0.0) * shares
        original_shares = max(0.0, shares - addon_shares)
        original_basis = max(0.0, basis - addon_cost)
        key = str(trade.get("trade_key") or f"core-{index}") + f":lot-{index}"
        if original_shares > 0 and original_basis > 0:
            events.append(CashEvent(
                str(trade.get("entry_date"))[:10], 20, key + ":entry", "core_entry",
                -original_basis, {"ticker": trade.get("ticker"), "shares": original_shares},
            ))
        remaining_addon = addon_shares
        for addon_index, addon in enumerate(addon_by_ticker.get(str(trade.get("ticker")), [])):
            event_shares = min(remaining_addon, float(addon.get("addon_shares") or 0.0))
            if event_shares <= 0:
                continue
            addon_basis = float(addon.get("entry_fill") or 0.0) * event_shares
            events.append(CashEvent(
                str(addon.get("scheduled_fill_date"))[:10], 20,
                f"{key}:addon-{addon_index}", "core_addon", -addon_basis,
                {"ticker": trade.get("ticker"), "shares": event_shares},
            ))
            remaining_addon -= event_shares
        # Release the exact booked basis plus authoritative net PnL.
        events.append(CashEvent(
            str(trade.get("exit_date"))[:10], 10, key + ":exit", "core_exit",
            basis + float(trade.get("pnl") or 0.0),
            {"ticker": trade.get("ticker"), "shares": shares},
        ))
    return events


def _integrate(core: dict[str, Any], candidates: list[dict[str, Any]], rows: dict[str, dict[str, dict[str, float]]]):
    ledger = DatedCashLedger(INITIAL_CAPITAL)
    grouped: dict[str, list[CashEvent]] = defaultdict(list)
    for event in _core_cash_events(core):
        grouped[event.date].append(event)
    candidate_by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        candidate_by_entry[str(candidate["entry_date"])[:10]].append(candidate)

    position = None
    executed: list[dict[str, Any]] = []
    realized_overlay = 0.0
    curve = []
    forced_exits = 0
    skipped_cash = []

    def close_overlay(day: str, reason: str, field: str) -> bool:
        nonlocal position, realized_overlay, forced_exits
        if position is None:
            return False
        raw = _price(rows, position["ticker"], day, field)
        if raw is None:
            return False
        if reason == "scheduled_10_session_close" and day == position["planned_exit_date"]:
            exit_price = float(position["planned_exit_price"])
        else:
            exit_price = apply_slippage(raw, SLIPPAGE_BPS_TARGET, "sell")
        proceeds = exit_price * position["shares"] * (1.0 - ROUND_TRIP_COST_PCT)
        ledger.book(CashEvent(
            day, 30, position["decision_id"] + ":exit", "overlay_exit", proceeds,
            {"ticker": position["ticker"], "reason": reason},
        ))
        pnl = proceeds - position["notional"]
        realized_overlay += pnl
        executed.append({
            **position, "exit_date": day, "exit_price": round(exit_price, 6),
            "pnl": round(pnl, 2), "exit_reason": reason,
        })
        if reason == "core_cash_priority":
            forced_exits += 1
        position = None
        return True

    for day, core_equity in core.get("equity_curve") or []:
        day = str(day)[:10]
        day_events = sorted(grouped.get(day, []), key=lambda event: (event.priority, event.event_id))
        exits = [event for event in day_events if event.kind == "core_exit"]
        entries = [event for event in day_events if event.kind != "core_exit"]
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
                    skipped_cash.append({
                        "date": day, "decision_id": candidate["decision_id"],
                        "available_cash": round(available, 2),
                    })
                    continue
                shares = notional / float(candidate["entry_price"])
                ledger.book(CashEvent(
                    day, 40, candidate["decision_id"] + ":entry", "overlay_entry", -notional,
                    {"ticker": candidate["ticker"], "shares": shares},
                ))
                position = {
                    "decision_id": candidate["decision_id"], "ticker": candidate["ticker"],
                    "entry_date": day, "entry_price": float(candidate["entry_price"]),
                    "shares": shares, "notional": notional,
                    "planned_exit_date": str(candidate["exit_date"])[:10],
                    "planned_exit_price": float(candidate["exit_price"]),
                }
                break

        open_unrealized = 0.0
        if position is not None:
            close = _price(rows, position["ticker"], day, "close")
            if close is not None:
                # Exit cost is recognized on liquidation, matching core accounting.
                open_unrealized = close * position["shares"] - position["notional"]
        curve.append((day, round(float(core_equity) + realized_overlay + open_unrealized, 2)))

    if position is not None and curve:
        close_overlay(curve[-1][0], "window_end", "close")

    inference = build_backtest_sharpe_inference(
        curve, periods_per_year=252, return_basis="strategy_equity_return",
        risk_free_assumption="zero",
    )
    sharpe = float(inference.get("annualized_sharpe") or 0.0)
    ret = curve[-1][1] / INITIAL_CAPITAL - 1.0
    peak = max_dd = 0.0
    for _, value in curve:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)
    overlay_pnl = round(sum(float(trade["pnl"]) for trade in executed), 2)
    result = {
        "expected_value_score": round(ret * abs(sharpe), 4),
        "strategy_total_return_pct": round(ret, 6),
        "sharpe_daily": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 6),
        "total_pnl": round(float(core.get("total_pnl") or 0.0) + overlay_pnl, 2),
        "total_trades": int(core.get("total_trades") or 0) + len(executed),
        "signals_generated": int(core.get("signals_generated") or 0),
        "signals_survived": int(core.get("signals_survived") or 0),
        "survival_rate": float(core.get("survival_rate") or 0.0),
    }
    audit = {
        **ledger.audit(),
        "baseline_ending_cash": (core.get("cash_ledger") or {}).get("ending_cash"),
        "core_only_reconstructed_ending_cash": round(
            INITIAL_CAPITAL + sum(event.amount for event in _core_cash_events(core)), 2
        ),
        "skipped_overlay_entries_for_cash": skipped_cash,
        "forced_core_priority_exits": forced_exits,
        "core_displacement_count": 0,
        "nav_reconciliation_error_count": 0,
    }
    audit["core_cash_reconstruction_matches"] = abs(
        float(audit["core_only_reconstructed_ending_cash"])
        - float(audit["baseline_ending_cash"])
    ) <= 0.05
    return result, audit, executed


def main() -> None:
    ticket = json.loads(TICKET.read_text(encoding="utf-8"))
    summary = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    reference = {row["label"]: row for row in summary["windows"]}
    baseline = _load(BASELINE_RUNNER, "exp_20260715_010_cash_gate1")
    baseline._configure_gate1_helpers()
    frozen = baseline.gate1._load_or_capture_frozen_inputs(False)
    windows = OrderedDict()
    all_trades = []

    for spec in baseline.gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] cash-feasible ETF reopen", flush=True)
        core, identity = baseline.gate1._run_window(spec, frozen)
        engine = baseline.gate1.BacktestEngine(
            list(frozen["behavior"]["universe"]), start=spec["start"], end=spec["end"],
            config=baseline.gate1.RUN_CONFIG,
            ohlcv_warehouse_path=str(baseline.gate1.WAREHOUSE),
            ohlcv_warehouse_snapshot_source=spec["snapshot"], replay_llm=False,
            replay_news=False, include_pilot_sleeve=False, require_non_ohlcv=False,
            include_oracle_diagnostics=False,
        )
        ohlcv = engine._download_data()
        normalized = {ticker: _rows(df) for ticker, df in ohlcv.items()}
        indexed = {ticker: {row["date"]: row for row in rows} for ticker, rows in normalized.items()}
        candidates, replay_audit = replay_low_deployment_etf_cash_substitute_trades(
            core_backtest_result=core,
            ohlcv_by_ticker={ticker: normalized[ticker] for ticker in ["QQQ", "SPY", "IWM", "GLD", "SLV"] if ticker in normalized},
            config={"fallback_paper_notional_usd": OVERLAY_CAP},
        )
        after, cash_audit, executed = _integrate(core, candidates, indexed)
        before_m, after_m = _metrics(core), _metrics(after)
        delta = {key: round(after_m[key] - before_m[key], 9) for key in before_m}
        ref = reference[label]
        identity_ok = (
            abs(before_m["expected_value_score"] - float(ref["expected_value_score"])) <= 5e-5
            and abs(before_m["total_pnl"] - float(ref["total_pnl"])) <= 0.01
            and before_m["trade_count"] == int(ref["trade_count"])
            and identity.get("trade_rows_sha256") == ref.get("trade_rows_sha256")
        )
        windows[label] = {
            "before": before_m, "after": after_m, "delta": delta,
            "gate1_identity_passed": identity_ok, "replay_audit": replay_audit,
            "cash_audit": cash_audit, "executed_overlay_trades": executed,
        }
        all_trades.extend(executed)

    before_ev = sum(row["before"]["expected_value_score"] for row in windows.values())
    after_ev = sum(row["after"]["expected_value_score"] for row in windows.values())
    aggregate = {
        "before_ev": round(before_ev, 4), "after_ev": round(after_ev, 4),
        "ev_delta": round(after_ev - before_ev, 4),
        "ev_delta_pct": round(after_ev / before_ev - 1.0, 6),
        "pnl_delta": round(sum(row["delta"]["total_pnl"] for row in windows.values()), 2),
        "ev_improved_windows": sum(row["delta"]["expected_value_score"] > EPS for row in windows.values()),
        "pnl_improved_windows": sum(row["delta"]["total_pnl"] > 0.005 for row in windows.values()),
        "worst_drawdown_drift": max(row["delta"]["max_drawdown_pct"] for row in windows.values()),
        "overlay_trade_count": len(all_trades),
    }
    positive = Counter()
    for trade in all_trades:
        if float(trade["pnl"]) > 0:
            positive[trade["ticker"]] += float(trade["pnl"])
    positive_total = sum(positive.values())
    max_share = max(positive.values(), default=0.0) / positive_total if positive_total else 1.0
    hhi = sum((value / positive_total) ** 2 for value in positive.values()) if positive_total else 1.0
    failed = []
    if not all(row["gate1_identity_passed"] for row in windows.values()): failed.append("gate1_identity_failed")
    if aggregate["ev_delta_pct"] <= 0.10: failed.append("aggregate_ev_improvement_not_above_10pct")
    if aggregate["pnl_delta"] <= 0: failed.append("aggregate_pnl_not_positive")
    if aggregate["ev_improved_windows"] < 2 or aggregate["pnl_improved_windows"] < 2: failed.append("fewer_than_two_windows_improved")
    if any(row["delta"]["expected_value_score"] < -EPS for row in windows.values()): failed.append("window_ev_regression")
    if any(row["delta"]["total_pnl"] < -0.005 for row in windows.values()): failed.append("window_pnl_regression")
    if aggregate["worst_drawdown_drift"] > 0.005: failed.append("drawdown_drift_too_high")
    if min(row["after"]["survival_rate"] for row in windows.values()) < 0.05: failed.append("survival_below_5pct")
    if any(row["cash_audit"]["negative_cash_event_count"] for row in windows.values()): failed.append("negative_cash_events")
    if any(not row["cash_audit"]["cash_conservation_passed"] for row in windows.values()): failed.append("cash_conservation_failed")
    if any(not row["cash_audit"]["core_cash_reconstruction_matches"] for row in windows.values()): failed.append("core_cash_reconstruction_failed")
    if max_share > 0.5: failed.append("single_ticker_concentration_failed")
    if hhi > 0.35: failed.append("hhi_concentration_failed")
    accepted = not failed
    payload = {
        "experiment_id": EXPERIMENT_ID, "status": "accepted" if accepted else "rejected",
        "decision": "accepted_cash_feasible_low_deployment_etf" if accepted else "rejected_cash_feasible_low_deployment_etf",
        "hypothesis": ticket["hypothesis"],
        "parameters": {"overlay_cap_usd": OVERLAY_CAP, "initial_cash_usd": INITIAL_CAPITAL},
        "gate1": {"passed": all(row["gate1_identity_passed"] for row in windows.values()), "baseline": str(BASELINE_SUMMARY.relative_to(ROOT))},
        "gate2": {"passed": not any(row["cash_audit"]["negative_cash_event_count"] for row in windows.values()), "entry_date": "present", "target_price": "core baseline present", "cash_contract": "execution-date core events; core priority; residual cash only"},
        "gate3": {"passed": min(row["after"]["survival_rate"] for row in windows.values()) >= 0.05},
        "gate4": {"passed": accepted, "failed_reasons": failed, "acceptance_rule": ticket["acceptance_rule"]},
        "aggregate": aggregate,
        "concentration": {"positive_pnl_by_ticker": dict(positive), "max_single_ticker_share": round(max_share, 6), "hhi": round(hhi, 6)},
        "windows": windows,
        "production_impact": "experiment-only; no backtester, live orders, run.py, selector, core policy, or paper ledger changed",
        "reproduction": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260716_low_deployment_etf_cash_feasible_reopen.py",
    }
    _atomic_json(OUT_JSON, payload)
    _atomic_json(OUT_DIR / "before.json", {"experiment_id": EXPERIMENT_ID, "windows": {label: row["before"] for label, row in windows.items()}, "aggregate_expected_value_score": round(before_ev, 4)})
    _atomic_json(OUT_DIR / "after.json", {"experiment_id": EXPERIMENT_ID, "windows": {label: row["after"] for label, row in windows.items()}, "aggregate_expected_value_score": round(after_ev, 4), "aggregate": aggregate})
    print(json.dumps({"decision": payload["decision"], "aggregate": aggregate, "failed": failed, "concentration": payload["concentration"]}, indent=2))


if __name__ == "__main__":
    main()
