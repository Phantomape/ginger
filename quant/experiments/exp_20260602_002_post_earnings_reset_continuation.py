"""exp-20260602-002: post-earnings reset continuation scout.

Lane: alpha_search.

This isolates the profitable behavior that was previously hidden inside the
calendar-DTE compatibility baseline: after a same-day earnings event, roll DTE
to the next future earnings date for next-open continuation evaluation instead
of treating the just-released event as pre-earnings risk for the whole day.

No JavaScript was used.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260602-002"
STEM = "exp_20260602_002_post_earnings_reset_continuation"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
JSONL = ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

CURRENT_PIT_BASELINE = {
    "late_strong": {
        "expected_value_score": 4.1082,
        "total_pnl": 100_203.06,
        "trade_count": 18,
        "signals_generated": 43,
        "signals_survived": 35,
        "survival_rate": 0.8140,
        "max_drawdown_pct": 0.0665,
    },
    "mid_weak": {
        "expected_value_score": 2.1405,
        "total_pnl": 78_119.38,
        "trade_count": 20,
        "signals_generated": 48,
        "signals_survived": 38,
        "survival_rate": 0.7917,
        "max_drawdown_pct": 0.1119,
    },
    "old_thin": {
        "expected_value_score": 0.1109,
        "total_pnl": 14_216.17,
        "trade_count": 20,
        "signals_generated": 47,
        "signals_survived": 44,
        "survival_rate": 0.9362,
        "max_drawdown_pct": 0.1409,
    },
}

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "parity_test_added": False,
    "replay_only": True,
    "trade_enabled": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "alters_orders": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return str(value)[:10]
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_output(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return (proc.stdout or proc.stderr or "").strip()


def _post_earnings_reset_earnings_dict_for(self, today, calendar_dates, ticker=None):
    """Production-style DTE reset after an earnings date has arrived.

    Current backtester fallback uses `calendar_date >= today`, so exact-day
    earnings remains DTE=0. Production `data_layer.get_earnings_data` uses the
    next row with `_earnings_date > as_of_date`. This scout tests that single
    causal variable while preserving PIT snapshot EPS/surprise fields.
    """
    today_date = today.date() if hasattr(today, "date") else today
    today_str = (
        today_date.strftime("%Y%m%d")
        if hasattr(today_date, "strftime")
        else str(today_date).replace("-", "")
    )
    future = [d for d in calendar_dates if d > today_date]
    base = {
        "next_earnings_date": None,
        "days_to_earnings": None,
        "eps_estimate": None,
        "eps_actual_last": None,
        "historical_surprise_pct": [],
        "avg_historical_surprise_pct": None,
    }
    if future:
        nxt = future[0]
        try:
            dte = int(np.busday_count(today_date, nxt))
        except Exception:
            dte = None
        base["next_earnings_date"] = str(nxt)
        base["days_to_earnings"] = dte

    if ticker and self._earnings_snapshots:
        candidates = [d for d in self._earnings_snapshots if d <= today_str]
        if candidates:
            snap_date = max(candidates)
            snap = self._earnings_snapshots[snap_date].get(ticker, {})
            snap_next = None
            if snap.get("next_earnings_date"):
                try:
                    snap_next = pd.Timestamp(snap["next_earnings_date"]).date()
                except Exception:
                    snap_next = None
            if snap_next is not None and snap_next > today_date:
                base["next_earnings_date"] = str(snap_next)
                try:
                    base["days_to_earnings"] = int(
                        np.busday_count(today_date, snap_next)
                    )
                except Exception:
                    base["days_to_earnings"] = None
            if snap.get("eps_estimate") is not None:
                base["eps_estimate"] = snap["eps_estimate"]
            if snap.get("eps_actual_last") is not None:
                base["eps_actual_last"] = snap["eps_actual_last"]
            if snap.get("avg_historical_surprise_pct") is not None:
                base["avg_historical_surprise_pct"] = snap[
                    "avg_historical_surprise_pct"
                ]
            if snap.get("historical_surprise_pct"):
                base["historical_surprise_pct"] = snap["historical_surprise_pct"]
    return base


def _metric_row(result: dict[str, Any]) -> dict[str, Any]:
    result["expected_value_score"] = compute_expected_value_score(result)
    return {
        "expected_value_score": round(float(result.get("expected_value_score") or 0.0), 4),
        "total_pnl": round(float(result.get("total_pnl") or 0.0), 2),
        "strategy_total_return_pct": round(
            float((result.get("benchmarks") or {}).get("strategy_total_return_pct") or 0.0),
            4,
        ),
        "sharpe_daily": round(float(result.get("sharpe_daily") or 0.0), 4),
        "max_drawdown_pct": round(float(result.get("max_drawdown_pct") or 0.0), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": round(float(result.get("survival_rate") or 0.0), 4),
        "win_rate": round(float(result.get("win_rate") or 0.0), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": round(float(result.get("tail_loss_share") or 0.0), 4),
        "worst_trade_pct": round(float(result.get("worst_trade_pct") or 0.0), 4),
    }


def _trade_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in result.get("trades", []) or []:
        rows.append(
            {
                "entry_date": str(trade.get("entry_date"))[:10],
                "exit_date": str(trade.get("exit_date"))[:10],
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "pnl": round(float(trade.get("pnl") or 0.0), 2),
                "sector": trade.get("sector"),
            }
        )
    return rows


def _trade_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("entry_date")),
        str(row.get("ticker")),
        str(row.get("strategy")),
    )


def _entered_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        event
        for event in (result.get("entry_candidate_events") or [])
        if event.get("decision") == "entered"
    ]


def _nearest_signal_event(
    trade: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, Any] | None:
    ticker = str(trade.get("ticker"))
    strategy = str(trade.get("strategy"))
    entry = pd.Timestamp(trade["entry_date"]).date()
    matches = []
    for event in events:
        if str(event.get("ticker")) != ticker or str(event.get("strategy")) != strategy:
            continue
        event_date = pd.Timestamp(event["date"]).date()
        delta = (entry - event_date).days
        if 0 <= delta <= 5:
            matches.append((delta, event_date, event))
    if not matches:
        return None
    matches.sort(key=lambda row: (row[0], row[1]))
    return matches[0][2]


def _dte_for(
    engine: BacktestEngine,
    calendar_dates: list[Any],
    ticker: str,
    signal_date: str,
    *,
    reset: bool,
) -> dict[str, Any]:
    method = (
        _post_earnings_reset_earnings_dict_for
        if reset
        else BacktestEngine._earnings_dict_for
    )
    data = method(engine, pd.Timestamp(signal_date), calendar_dates, ticker=ticker)
    return {
        "next_earnings_date": data.get("next_earnings_date"),
        "days_to_earnings": data.get("days_to_earnings"),
        "avg_historical_surprise_pct": data.get("avg_historical_surprise_pct"),
        "eps_actual_last_available": data.get("eps_actual_last") is not None,
        "eps_estimate_available": data.get("eps_estimate") is not None,
    }


def _run_variant(*, post_earnings_reset: bool) -> dict[str, dict[str, Any]]:
    universe = get_universe()
    config = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}
    rows: dict[str, dict[str, Any]] = {}
    original = BacktestEngine._earnings_dict_for
    if post_earnings_reset:
        BacktestEngine._earnings_dict_for = _post_earnings_reset_earnings_dict_for
    try:
        for label, spec in WINDOWS.items():
            engine = BacktestEngine(
                universe=universe,
                start=spec["start"],
                end=spec["end"],
                config=config,
                replay_llm=False,
                replay_news=False,
                ohlcv_snapshot_path=spec["snapshot"],
                include_oracle_diagnostics=False,
                include_entry_candidate_events=True,
            )
            result = engine.run()
            if "error" in result:
                rows[label] = {"error": result["error"]}
                continue
            rows[label] = {
                "metrics": _metric_row(result),
                "trades": _trade_rows(result),
                "entry_decision_counts": dict(
                    Counter(
                        event.get("decision")
                        for event in (result.get("entry_candidate_events") or [])
                    )
                ),
                "entered_events": _entered_events(result),
            }
    finally:
        BacktestEngine._earnings_dict_for = original
    return rows


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            sum(float((row.get("metrics") or {}).get("expected_value_score") or 0.0) for row in rows.values()),
            4,
        ),
        "total_pnl": round(
            sum(float((row.get("metrics") or {}).get("total_pnl") or 0.0) for row in rows.values()),
            2,
        ),
        "trade_count": sum(int((row.get("metrics") or {}).get("trade_count") or 0) for row in rows.values()),
        "signals_generated": sum(
            int((row.get("metrics") or {}).get("signals_generated") or 0)
            for row in rows.values()
        ),
        "signals_survived": sum(
            int((row.get("metrics") or {}).get("signals_survived") or 0)
            for row in rows.values()
        ),
        "max_drawdown_pct": round(
            max(float((row.get("metrics") or {}).get("max_drawdown_pct") or 0.0) for row in rows.values()),
            4,
        ),
        "min_survival_rate": round(
            min(float((row.get("metrics") or {}).get("survival_rate") or 0.0) for row in rows.values()),
            4,
        ),
    }


def _compare(
    current_rows: dict[str, dict[str, Any]],
    reset_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    for label in WINDOWS:
        before = current_rows[label]["metrics"]
        after = reset_rows[label]["metrics"]
        old_trades = reset_rows[label]["trades"]
        cur_trades = current_rows[label]["trades"]
        old_map = {_trade_key(row): row for row in old_trades}
        cur_map = {_trade_key(row): row for row in cur_trades}
        old_only = [old_map[key] for key in sorted(set(old_map) - set(cur_map))]
        cur_only = [cur_map[key] for key in sorted(set(cur_map) - set(old_map))]
        common_delta = round(
            sum(old_map[key]["pnl"] - cur_map[key]["pnl"] for key in set(old_map) & set(cur_map)),
            2,
        )
        by_window[label] = {
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    after["expected_value_score"] - before["expected_value_score"], 4
                ),
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 2),
                "trade_count": int(after["trade_count"] or 0) - int(before["trade_count"] or 0),
                "signals_generated": int(after["signals_generated"] or 0)
                - int(before["signals_generated"] or 0),
                "signals_survived": int(after["signals_survived"] or 0)
                - int(before["signals_survived"] or 0),
                "max_drawdown_pct": round(
                    after["max_drawdown_pct"] - before["max_drawdown_pct"], 4
                ),
            },
            "post_reset_only_trade_count": len(old_only),
            "post_reset_only_pnl": round(sum(row["pnl"] for row in old_only), 2),
            "current_only_trade_count": len(cur_only),
            "current_only_pnl": round(sum(row["pnl"] for row in cur_only), 2),
            "common_trade_pnl_delta": common_delta,
            "post_reset_only_trades": old_only,
            "current_only_trades": cur_only,
        }

    before_agg = _aggregate(current_rows)
    after_agg = _aggregate(reset_rows)
    return {
        "aggregate": {
            "before": before_agg,
            "after": after_agg,
            "delta": {
                "expected_value_score": round(
                    after_agg["expected_value_score"] - before_agg["expected_value_score"],
                    4,
                ),
                "expected_value_score_pct": round(
                    (
                        (after_agg["expected_value_score"] - before_agg["expected_value_score"])
                        / before_agg["expected_value_score"]
                    )
                    if before_agg["expected_value_score"]
                    else 0.0,
                    6,
                ),
                "total_pnl": round(after_agg["total_pnl"] - before_agg["total_pnl"], 2),
                "total_pnl_pct": round(
                    ((after_agg["total_pnl"] - before_agg["total_pnl"]) / before_agg["total_pnl"])
                    if before_agg["total_pnl"]
                    else 0.0,
                    6,
                ),
                "trade_count": after_agg["trade_count"] - before_agg["trade_count"],
                "signals_generated": after_agg["signals_generated"]
                - before_agg["signals_generated"],
                "signals_survived": after_agg["signals_survived"]
                - before_agg["signals_survived"],
                "max_drawdown_pct": round(
                    after_agg["max_drawdown_pct"] - before_agg["max_drawdown_pct"],
                    4,
                ),
            },
        },
        "by_window": by_window,
    }


def _event_reset_attribution(
    reset_rows: dict[str, dict[str, Any]],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    universe = get_universe()
    rows: list[dict[str, Any]] = []
    pnl_by_window: dict[str, float] = {}
    for label, spec in WINDOWS.items():
        engine = BacktestEngine(
            universe=universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=spec["snapshot"],
            include_oracle_diagnostics=False,
        )
        calendar = engine._download_earnings_calendar()
        events = reset_rows[label]["entered_events"]
        for trade in comparison["by_window"][label]["post_reset_only_trades"]:
            signal_event = _nearest_signal_event(trade, events)
            if not signal_event:
                continue
            ticker = str(trade["ticker"])
            signal_date = str(signal_event["date"])
            current_dte = _dte_for(
                engine,
                calendar.get(ticker, []),
                ticker,
                signal_date,
                reset=False,
            )
            reset_dte = _dte_for(
                engine,
                calendar.get(ticker, []),
                ticker,
                signal_date,
                reset=True,
            )
            is_exact_day_reset = (
                current_dte.get("days_to_earnings") == 0
                and (reset_dte.get("days_to_earnings") or 0) >= 4
            )
            row = {
                "window": label,
                "signal_date": signal_date,
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "ticker": ticker,
                "strategy": trade["strategy"],
                "pnl": trade["pnl"],
                "current_pit_dte": current_dte,
                "post_reset_dte": reset_dte,
                "exact_day_reset": bool(is_exact_day_reset),
            }
            rows.append(row)
            if is_exact_day_reset:
                pnl_by_window[label] = pnl_by_window.get(label, 0.0) + trade["pnl"]

    exact_rows = [row for row in rows if row["exact_day_reset"]]
    return {
        "post_reset_only_rows": rows,
        "exact_day_reset_trade_count": len(exact_rows),
        "exact_day_reset_pnl": round(sum(row["pnl"] for row in exact_rows), 2),
        "exact_day_reset_pnl_by_window": {
            key: round(value, 2) for key, value in sorted(pnl_by_window.items())
        },
        "exact_day_reset_tickers": sorted({row["ticker"] for row in exact_rows}),
    }


def _gate2() -> dict[str, Any]:
    path = ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"passed": False, "reason": "missing open_positions.json"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    positions = payload.get("positions", []) if isinstance(payload, dict) else []
    missing = []
    for pos in positions:
        ticker = pos.get("ticker", "UNKNOWN")
        for field in ("entry_date", "target_price"):
            if pos.get(field) in (None, ""):
                missing.append({"ticker": ticker, "field": field})
    return {
        "passed": not missing,
        "path": _repo_rel(path),
        "position_count": len(positions),
        "missing_required_fields": missing,
    }


def _decision(comparison: dict[str, Any], event_attr: dict[str, Any]) -> dict[str, Any]:
    agg_delta = comparison["aggregate"]["delta"]
    ev_windows = [
        label
        for label, row in comparison["by_window"].items()
        if row["delta"]["expected_value_score"] > 0
    ]
    pnl_windows = [
        label for label, row in comparison["by_window"].items() if row["delta"]["total_pnl"] > 0
    ]
    min_survival = comparison["aggregate"]["after"]["min_survival_rate"]
    aggregate_passed = (
        agg_delta["expected_value_score"] > 0
        and agg_delta["expected_value_score_pct"] > 0.10
        and agg_delta["total_pnl"] > 0
        and min_survival >= 0.05
    )
    event_timing_promotable = False
    if aggregate_passed and event_attr["exact_day_reset_trade_count"] >= 5:
        status = "positive_replay_lead_requires_explicit_event_timing"
        decision = "observed_only_post_earnings_continuation_alpha_lead"
    else:
        status = "rejected_post_earnings_reset_continuation"
        decision = "rejected"
    return {
        "status": status,
        "decision": decision,
        "aggregate_passed": aggregate_passed,
        "promotable_now": event_timing_promotable,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "requires_explicit_event_timing_fields": True,
        "requires_shared_policy_before_promotion": True,
        "rationale": (
            "Strong aggregate replay lead, but promotion must wait for explicit "
            "pre-earnings versus post-earnings event timing fields; do not retain "
            "the implicit DTE side effect as production policy."
            if aggregate_passed
            else "Aggregate replay gate did not pass."
        ),
    }


def _append_jsonl(payload: dict[str, Any]) -> None:
    JSONL.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if JSONL.exists() and needle in JSONL.read_text(encoding="utf-8"):
        return
    row = {
        "accepted": False,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "decision": payload["decision"],
        "status": payload["status"],
        "before_metrics": payload["comparison"]["aggregate"]["before"],
        "after_metrics": payload["comparison"]["aggregate"]["after"],
        "delta_metrics": payload["comparison"]["aggregate"]["delta"],
        "event_reset_attribution": payload["event_reset_attribution"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "prediction": payload.get("prediction"),
        "calibration": payload.get("calibration"),
        "anti_js": payload["anti_js"],
        "rejection_reason": payload.get("rejection_reason"),
        "next_retry_requires": payload["next_retry_requires"],
    }
    with JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(row), sort_keys=True) + "\n")


def _update_ticket(payload: dict[str, Any]) -> None:
    if not TICKET_JSON.exists():
        return
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "aggregate_delta": payload["comparison"]["aggregate"]["delta"],
        "exact_day_reset_trade_count": payload["event_reset_attribution"][
            "exact_day_reset_trade_count"
        ],
        "exact_day_reset_pnl": payload["event_reset_attribution"][
            "exact_day_reset_pnl"
        ],
    }
    _write_json(TICKET_JSON, ticket)


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["comparison"]
    event_attr = payload["event_reset_attribution"]
    lines = [
        f"# {EXPERIMENT_ID} post-earnings reset continuation",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Aggregate EV delta: `{comp['aggregate']['delta']['expected_value_score']}`",
        f"- Aggregate PnL delta: `${comp['aggregate']['delta']['total_pnl']:,.2f}`",
        f"- Exact-day reset PnL: `${event_attr['exact_day_reset_pnl']:,.2f}`",
        f"- Exact-day reset trades: `{event_attr['exact_day_reset_trade_count']}`",
        "",
        "## Window Results",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | reset-only PnL |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in comp["by_window"].items():
        lines.append(
            "| {label} | {before:.4f} | {after:.4f} | {delta:+.4f} | ${pnl:+,.2f} | ${reset_pnl:+,.2f} |".format(
                label=label,
                before=row["before"]["expected_value_score"],
                after=row["after"]["expected_value_score"],
                delta=row["delta"]["expected_value_score"],
                pnl=row["delta"]["total_pnl"],
                reset_pnl=row["post_reset_only_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["gate4"]["rationale"],
            "",
            "The replay lead should be implemented, if at all, as an explicit",
            "`post_earnings_continuation` event-timing policy. It should not be",
            "hidden inside a broad DTE semantic rollback.",
            "",
            "No live/default orders, core ranking, sizing, exits, LLM/news, or",
            "watchlists changed.",
        ]
    )
    CARD_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = _utc_now()
    current_rows = _run_variant(post_earnings_reset=False)
    reset_rows = _run_variant(post_earnings_reset=True)
    comparison = _compare(current_rows, reset_rows)
    event_attr = _event_reset_attribution(reset_rows, comparison)
    gate2 = _gate2()
    gate4 = _decision(comparison, event_attr)
    prediction = {
        "success_probability": 0.55,
        "expected_ev_delta": 1.5,
        "expected_pnl_delta": 42_000.0,
        "main_failure_modes": [
            "old_thin_only_edge",
            "event_timing_not_production_safe",
            "late_strong_regression",
            "ambiguous_pre_vs_post_market_timing",
        ],
        "confidence_reason": (
            "Pre-scout trade attribution showed exact-day earnings reset trades "
            "drove the old-vs-current DTE gap."
        ),
    }
    actual_success = 1 if gate4["status"].startswith("positive") else 0
    calibration = {
        "predicted_success_probability": prediction["success_probability"],
        "actual_success": actual_success,
        "actual_ev_delta": comparison["aggregate"]["delta"]["expected_value_score"],
        "actual_pnl_delta": comparison["aggregate"]["delta"]["total_pnl"],
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": (
            ["requires_explicit_event_timing_fields"]
            if actual_success
            else ["aggregate_gate_failed"]
        ),
        "predicted_failure_mode_hit": bool(actual_success),
        "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 4),
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "hypothesis": (
            "Core trend/breakout signals immediately after an earnings event may "
            "contain a production-visible post-earnings continuation edge that "
            "was previously hidden inside calendar-DTE semantics."
        ),
        "change_type": "post_earnings_continuation_alpha_scout",
        "mechanism_family": "post_earnings_continuation",
        "trial_family": "post_earnings_reset_continuation",
        "trial_variant_id": "production_style_next_future_earnings_dte",
        "single_causal_variable": (
            "production-style next-future-earnings DTE after same-day earnings event"
        ),
        "changed_variable": (
            "same-day earnings reset DTE for post-earnings continuation candidates"
        ),
        "status": gate4["status"],
        "decision": gate4["decision"],
        "comparison": comparison,
        "event_reset_attribution": event_attr,
        "gate1": {
            "baseline_artifact": "data/experiments/exp-20260601-025/exp_20260601_025_pit_dte_baseline_protocol.json",
            "baseline_metrics": CURRENT_PIT_BASELINE,
            "passed": True,
        },
        "gate2": gate2,
        "gate3": {
            "new_filter_added": False,
            "passed": comparison["aggregate"]["after"]["min_survival_rate"] >= 0.05,
            "min_survival_rate": comparison["aggregate"]["after"]["min_survival_rate"],
        },
        "gate4": gate4,
        "prediction": prediction,
        "calibration": calibration,
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
        "next_retry_requires": [
            "Add explicit PIT-safe fields for pre_earnings_risk, post_earnings_continuation, days_since_earnings, and next_future_earnings_dte.",
            "Resolve same-day before-open versus after-close earnings timing before any production promotion.",
            "Promote only through shared run/backtester policy and parity tests; do not use a broad DTE rollback.",
        ],
        "rejection_reason": (
            None
            if gate4["status"].startswith("positive")
            else gate4["rationale"]
        ),
        "git": {
            "head": _git_output(["rev-parse", "--short", "HEAD"]),
            "dirty_status_count": len(_git_output(["status", "--short"]).splitlines()),
        },
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_card(payload)
    _update_ticket(payload)
    _append_jsonl(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "aggregate_delta": comparison["aggregate"]["delta"],
                "exact_day_reset_trade_count": event_attr["exact_day_reset_trade_count"],
                "exact_day_reset_pnl": event_attr["exact_day_reset_pnl"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
