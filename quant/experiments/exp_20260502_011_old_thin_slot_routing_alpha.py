"""exp-20260502-011 old_thin slot-routing alpha replay.

Alpha search. The old_thin oracle points at missed APP / PLTR / TSLA / SPOT
style opportunities when entry slots were scarce. This experiment keeps global
MAX_POSITIONS unchanged and tests one replay-only allocation variable:
can a point-in-time leadership score let a skipped/deferred strong candidate
replace the weakest same-day planned entry without harming other windows?
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260502-011"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "old_thin_slot_routing_alpha.json"
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

CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "REPLAY_PARTIAL_REDUCES": True,
}

HORIZONS = (5, 10, 20)
WATCHLIST = {"APP", "PLTR", "TSLA", "SPOT"}


def _num(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


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


def _median(values):
    values = [float(v) for v in values if v is not None]
    if not values:
        return None
    return round(statistics.median(values), 4)


def _avg(values):
    values = [float(v) for v in values if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "entry_reason_counts": (
            result.get("entry_execution_attribution") or {}
        ).get("reason_counts", {}),
        "by_strategy": result.get("by_strategy", {}),
    }


def _load_snapshot(path: str) -> dict:
    payload = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
    out = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        clean = []
        for row in rows:
            clean.append({
                "Date": str(row.get("Date")),
                "Open": _num(row.get("Open")),
                "High": _num(row.get("High")),
                "Low": _num(row.get("Low")),
                "Close": _num(row.get("Close")),
                "Volume": _num(row.get("Volume")),
            })
        out[ticker.upper()] = sorted(clean, key=lambda row: row["Date"])
    return out


def _row_index_on_or_after(rows: list[dict], date_str: str):
    for idx, row in enumerate(rows):
        if row["Date"] >= date_str:
            return idx
    return None


def _row_index_on_or_before(rows: list[dict], date_str: str):
    hit = None
    for idx, row in enumerate(rows):
        if row["Date"] <= date_str:
            hit = idx
        else:
            break
    return hit


def _forward_returns(snapshot: dict, ticker: str, date_str: str) -> dict:
    rows = snapshot.get((ticker or "").upper()) or []
    start_idx = _row_index_on_or_after(rows, date_str)
    if start_idx is None:
        return {f"forward_return_{h}d": None for h in HORIZONS}
    start_close = rows[start_idx].get("Close")
    out = {}
    for horizon in HORIZONS:
        end_idx = min(start_idx + horizon, len(rows) - 1)
        end_close = rows[end_idx].get("Close")
        value = None
        if start_close and end_close:
            value = (end_close / start_close) - 1.0
        out[f"forward_return_{horizon}d"] = _round(value, 6)
    return out


def _active_positions_on_date(trades: list[dict], snapshot: dict, date_str: str) -> list[dict]:
    active = []
    for trade in trades or []:
        entry_date = trade.get("entry_date")
        exit_date = trade.get("exit_date")
        if not entry_date or not exit_date:
            continue
        if not (entry_date <= date_str < exit_date):
            continue
        ticker = (trade.get("ticker") or "").upper()
        rows = snapshot.get(ticker) or []
        row_idx = _row_index_on_or_before(rows, date_str)
        close = rows[row_idx]["Close"] if row_idx is not None else None
        entry = _num(trade.get("entry_price"), None)
        stop = _num(trade.get("stop_price"), None)
        target = _num(trade.get("target_price"), None)
        unrealized_pct = None
        distance_to_target_pct = None
        distance_to_stop_pct = None
        if close and entry:
            unrealized_pct = (close / entry) - 1.0
        if close and target:
            distance_to_target_pct = (target / close) - 1.0
        if close and stop:
            distance_to_stop_pct = (close / stop) - 1.0
        active.append({
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "entry_date": entry_date,
            "exit_date": exit_date,
            "shares": trade.get("shares"),
            "entry_price": _round(entry, 4),
            "close_on_skip_date": _round(close, 4),
            "unrealized_pct": _round(unrealized_pct, 6),
            "distance_to_target_pct": _round(distance_to_target_pct, 6),
            "distance_to_stop_pct": _round(distance_to_stop_pct, 6),
            "final_pnl": _round(trade.get("pnl"), 2),
            "final_exit_reason": trade.get("exit_reason"),
        })
    return active


def _patched_entry_summary(original):
    def summarize(events):
        summary = original(events)
        skipped = [event for event in events or [] if event.get("decision") != "entered"]
        skipped.sort(
            key=lambda event: (
                event.get("date") or "",
                event.get("candidate_rank")
                if event.get("candidate_rank") is not None else 999999,
                event.get("ticker") or "",
            )
        )
        summary["all_skips"] = skipped
        summary.setdefault("notes", []).append(
            "all_skips is experiment-only audit detail from exp-20260502-011."
        )
        return summary

    return summarize


def _signal_conditions(sig: dict) -> dict:
    conditions = sig.get("conditions_met")
    return conditions if isinstance(conditions, dict) else {}


def _normal_rs(value):
    value = _num(value, 0.0)
    if abs(value) > 2:
        value = value / 100.0
    return max(-0.25, min(0.35, value))


def _normal_pct_from_high(value):
    value = _num(value, -0.35)
    if value > 2 or value < -2:
        value = value / 100.0
    value = max(-0.35, min(0.10, value))
    return max(0.0, 1.0 + (value / 0.35))


def _signal_leadership_score(sig: dict) -> float:
    conditions = _signal_conditions(sig)
    tqs = _num(sig.get("trade_quality_score"), 0.0)
    confidence = _num(sig.get("confidence_score"), 0.0)
    rs = _normal_rs(
        sig.get("rs_vs_spy")
        or sig.get("relative_strength_vs_spy")
        or conditions.get("rs_vs_spy")
        or conditions.get("relative_strength_vs_spy")
    )
    pct_from_high = _normal_pct_from_high(
        sig.get("pct_from_52w_high")
        or conditions.get("pct_from_52w_high")
    )
    volume_ratio = _num(
        sig.get("volume_ratio")
        or sig.get("volume_spike_ratio")
        or conditions.get("volume_ratio")
        or conditions.get("volume_spike_ratio"),
        1.0,
    )
    volume_component = max(0.0, min(volume_ratio - 1.0, 2.0)) / 2.0
    rs_component = max(0.0, min(rs, 0.25)) / 0.25
    strategy_bonus = 0.10 if sig.get("strategy") == "breakout_long" else 0.0
    return round(
        1.60 * tqs
        + 1.00 * confidence
        + 0.60 * rs_component
        + 0.50 * pct_from_high
        + 0.30 * volume_component
        + strategy_bonus,
        6,
    )


def _entry_gap_risk_ok(sig: dict) -> bool:
    entry = _num(sig.get("entry_price"), None)
    stop = _num(sig.get("stop_price"), None)
    if entry is None or stop is None or entry <= 5 or stop <= 0:
        return False
    if stop >= entry:
        return False
    initial_risk = (entry - stop) / entry
    return initial_risk <= 0.12


def _sig_id(sig: dict):
    return (
        (sig.get("ticker") or "").upper(),
        sig.get("strategy"),
        _round(sig.get("entry_price"), 4),
    )


def _with_insertion_marker(sig: dict, insertion: dict) -> dict:
    out = dict(sig)
    out["scarce_slot_strong_candidate_inserted"] = insertion
    sizing = dict(out.get("sizing") or {})
    sizing["scarce_slot_strong_candidate_inserted_multiplier_applied"] = 1.0
    out["sizing"] = sizing
    return out


def _patched_plan_entry_candidates(original, state):
    def patched(signals, *args, **kwargs):
        planned, plan = original(signals, *args, **kwargs)
        slots = int(plan.get("available_slots") or 0)
        if slots > 1 or not planned:
            return planned, plan

        planned_ids = {_sig_id(sig) for sig in planned}
        source_by_id = {}
        candidates = []
        for sig in plan.get("slot_sliced_signals") or []:
            source_by_id[_sig_id(sig)] = "slot_sliced"
            candidates.append(sig)

        input_lookup = {}
        for sig in signals or []:
            input_lookup[((sig.get("ticker") or "").upper(), sig.get("strategy"))] = sig
        for deferred in plan.get("deferred_breakout_signals") or []:
            key = ((deferred.get("ticker") or "").upper(), deferred.get("strategy"))
            sig = input_lookup.get(key) or dict(deferred)
            source_by_id[_sig_id(sig)] = "scarce_slot_breakout_deferred"
            candidates.append(sig)

        candidates = [
            sig for sig in candidates
            if _sig_id(sig) not in planned_ids and _entry_gap_risk_ok(sig)
        ]
        if not candidates:
            return planned, plan

        best = max(candidates, key=_signal_leadership_score)
        weakest = min(planned, key=_signal_leadership_score)
        best_score = _signal_leadership_score(best)
        weakest_score = _signal_leadership_score(weakest)
        if best_score <= weakest_score:
            return planned, plan

        insertion = {
            "ticker": (best.get("ticker") or "").upper(),
            "strategy": best.get("strategy"),
            "source": source_by_id.get(_sig_id(best), "unknown"),
            "leadership_score": best_score,
            "displaced_ticker": (weakest.get("ticker") or "").upper(),
            "displaced_strategy": weakest.get("strategy"),
            "displaced_leadership_score": weakest_score,
            "score_advantage": round(best_score - weakest_score, 6),
            "available_slots": slots,
        }
        state.setdefault("insertions", []).append(insertion)

        replacement = []
        replaced = False
        for sig in planned:
            if not replaced and _sig_id(sig) == _sig_id(weakest):
                replacement.append(_with_insertion_marker(best, insertion))
                replaced = True
            else:
                replacement.append(sig)

        best_id = _sig_id(best)
        plan = dict(plan)
        plan["slot_sliced_signals"] = [
            sig for sig in plan.get("slot_sliced_signals") or []
            if _sig_id(sig) != best_id
        ] + [weakest]
        plan["deferred_breakout_signals"] = [
            sig for sig in plan.get("deferred_breakout_signals") or []
            if ((sig.get("ticker") or "").upper(), sig.get("strategy"))
            != ((best.get("ticker") or "").upper(), best.get("strategy"))
        ]
        plan.setdefault("strong_candidate_insertions", []).append(insertion)
        plan["signals_after_entry_plan"] = len(replacement)
        return replacement, plan

    return patched


def _run_backtest(window: dict, use_h1_replay: bool = False) -> tuple[dict, dict]:
    state = {"insertions": []}
    original_summary = bt._summarize_entry_decision_events
    original_plan = bt.plan_entry_candidates
    bt._summarize_entry_decision_events = _patched_entry_summary(original_summary)
    if use_h1_replay:
        bt.plan_entry_candidates = _patched_plan_entry_candidates(original_plan, state)
    try:
        engine = BacktestEngine(
            get_universe(),
            start=window["start"],
            end=window["end"],
            config=CONFIG,
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        )
        result = engine.run()
    finally:
        bt._summarize_entry_decision_events = original_summary
        bt.plan_entry_candidates = original_plan
    return result, state


def _audit_skips(result: dict, snapshot: dict) -> dict:
    entry = result.get("entry_execution_attribution") or {}
    skips = entry.get("all_skips") or entry.get("sample_skips") or []
    rows = []
    reason_returns = {}
    trades = result.get("trades") or []
    for event in skips:
        ticker = (event.get("ticker") or "").upper()
        date_str = event.get("date")
        forward = _forward_returns(snapshot, ticker, date_str)
        active = _active_positions_on_date(trades, snapshot, date_str)
        row = {
            "date": date_str,
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "decision": event.get("decision"),
            "candidate_rank": event.get("candidate_rank"),
            "available_slots": event.get("available_slots_at_entry_loop"),
            "active_position_count": len(active),
            "active_positions": active,
            **forward,
        }
        rows.append(row)
        reason_returns.setdefault(event.get("decision"), []).append(
            forward.get("forward_return_20d")
        )

    by_reason = {}
    for reason, values in reason_returns.items():
        values = [value for value in values if value is not None]
        by_reason[reason or "unknown"] = {
            "count": len(values),
            "avg_forward_return_20d": _avg(values),
            "median_forward_return_20d": _median(values),
            "best_forward_return_20d": _round(max(values), 6) if values else None,
            "worst_forward_return_20d": _round(min(values), 6) if values else None,
        }

    top_rows = sorted(
        rows,
        key=lambda row: (
            row.get("forward_return_20d")
            if row.get("forward_return_20d") is not None else -999.0
        ),
        reverse=True,
    )[:20]
    watchlist_rows = [
        row for row in rows
        if row.get("ticker") in WATCHLIST
    ]
    return {
        "skip_count": len(rows),
        "reason_counts": entry.get("reason_counts", {}),
        "by_reason_forward_20d": by_reason,
        "top_skipped_forward_20d": top_rows,
        "watchlist_skips": watchlist_rows,
    }


def _mfe_giveback_observation(result: dict, snapshot: dict) -> dict:
    rows = []
    for trade in result.get("trades") or []:
        ticker = (trade.get("ticker") or "").upper()
        entry_date = trade.get("entry_date")
        exit_date = trade.get("exit_date")
        entry = _num(trade.get("entry_price"), None)
        shares = _num(trade.get("shares"), 0)
        if not ticker or not entry_date or not exit_date or not entry or shares <= 0:
            continue
        ticker_rows = snapshot.get(ticker) or []
        start_idx = _row_index_on_or_after(ticker_rows, entry_date)
        end_idx = _row_index_on_or_before(ticker_rows, exit_date)
        if start_idx is None or end_idx is None or end_idx < start_idx:
            continue
        window_rows = ticker_rows[start_idx:end_idx + 1]
        best_high = max(row["High"] for row in window_rows if row.get("High"))
        worst_low = min(row["Low"] for row in window_rows if row.get("Low"))
        mfe_pct = (best_high / entry) - 1.0 if best_high else None
        mae_pct = (worst_low / entry) - 1.0 if worst_low else None
        mfe_dollars = ((best_high - entry) * shares) if best_high else None
        actual_pnl = _num(trade.get("pnl"), 0.0)
        giveback_vs_mfe = mfe_dollars - actual_pnl if mfe_dollars is not None else None
        row = {
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "entry_date": entry_date,
            "exit_date": exit_date,
            "exit_reason": trade.get("exit_reason"),
            "entry_price": _round(entry, 4),
            "best_high": _round(best_high, 4),
            "worst_low": _round(worst_low, 4),
            "mfe_pct": _round(mfe_pct, 6),
            "mae_pct": _round(mae_pct, 6),
            "actual_pnl": _round(actual_pnl, 2),
            "mfe_dollars": _round(mfe_dollars, 2),
            "giveback_vs_mfe": _round(giveback_vs_mfe, 2),
        }
        rows.append(row)

    stopped_after_positive_mfe = [
        row for row in rows
        if (row.get("actual_pnl") or 0) < 0
        and (row.get("mfe_dollars") or 0) > 0
    ]
    stopped_after_positive_mfe.sort(
        key=lambda row: row.get("giveback_vs_mfe") or 0.0,
        reverse=True,
    )
    return {
        "trade_count": len(rows),
        "loss_after_positive_mfe_count": len(stopped_after_positive_mfe),
        "loss_after_positive_mfe_giveback": _round(
            sum(row.get("giveback_vs_mfe") or 0.0 for row in stopped_after_positive_mfe),
            2,
        ),
        "top_loss_after_positive_mfe": stopped_after_positive_mfe[:15],
        "notes": [
            "Observation only: no exit rule changed in this experiment.",
            "MFE uses intratrade high from entry_date through exit_date inclusive.",
        ],
    }


def _variant_extra(result: dict, state: dict) -> dict:
    insertion_keys = {
        (item.get("ticker"), item.get("strategy"))
        for item in state.get("insertions") or []
    }
    inserted_trades = []
    matched_candidate_trades = []
    for trade in result.get("trades") or []:
        multipliers = trade.get("sizing_multipliers") or {}
        if multipliers.get("scarce_slot_strong_candidate_inserted_multiplier_applied"):
            inserted_trades.append({
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": _round(trade.get("pnl"), 2),
            })
        key = ((trade.get("ticker") or "").upper(), trade.get("strategy"))
        if key in insertion_keys:
            matched_candidate_trades.append({
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": _round(trade.get("pnl"), 2),
            })
    return {
        "h1_insertions_seen": len(state.get("insertions") or []),
        "h1_entered_trades": len(inserted_trades),
        "h1_entered_pnl": _round(sum(row["pnl"] or 0.0 for row in inserted_trades), 2),
        "h1_insertions": state.get("insertions") or [],
        "h1_inserted_trades": inserted_trades,
        "h1_matched_candidate_trades_proxy": matched_candidate_trades,
        "h1_matched_candidate_pnl_proxy": _round(
            sum(row["pnl"] or 0.0 for row in matched_candidate_trades),
            2,
        ),
        "h1_outcome_marker_note": (
            "Inserted candidate signals are not part of the backtester sizing "
            "multiplier whitelist, so h1_entered_trades can be zero even when "
            "the replay changed entries. h1_matched_candidate_trades_proxy "
            "matches by ticker/strategy for diagnosis only."
        ),
    }


def _aggregate(metrics_by_window: dict) -> dict:
    ev_values = [
        metrics.get("expected_value_score")
        for metrics in metrics_by_window.values()
        if metrics.get("expected_value_score") is not None
    ]
    return {
        "expected_value_score_sum": _round(sum(ev_values), 4),
        "total_pnl_sum": _round(
            sum(_num(metrics.get("total_pnl"), 0.0) for metrics in metrics_by_window.values()),
            2,
        ),
        "trade_count_sum": int(
            sum(_num(metrics.get("trade_count"), 0.0) for metrics in metrics_by_window.values())
        ),
    }


def _delta_metrics(base: dict, replay: dict) -> dict:
    by_window = {}
    ev_improved = 0
    ev_regressed = 0
    for label in WINDOWS:
        b = base[label]["metrics"]
        r = replay[label]["metrics"]
        delta = {
            "expected_value_score_delta": _round(
                _num(r.get("expected_value_score")) - _num(b.get("expected_value_score")),
                4,
            ),
            "total_pnl_delta": _round(
                _num(r.get("total_pnl")) - _num(b.get("total_pnl")),
                2,
            ),
            "sharpe_daily_delta": _round(
                _num(r.get("sharpe_daily")) - _num(b.get("sharpe_daily")),
                4,
            ),
            "max_drawdown_pct_delta": _round(
                _num(r.get("max_drawdown_pct")) - _num(b.get("max_drawdown_pct")),
                4,
            ),
            "win_rate_delta": _round(
                _num(r.get("win_rate")) - _num(b.get("win_rate")),
                4,
            ),
            "trade_count_delta": int(
                _num(r.get("trade_count")) - _num(b.get("trade_count"))
            ),
        }
        if delta["expected_value_score_delta"] > 0:
            ev_improved += 1
        if delta["expected_value_score_delta"] < 0:
            ev_regressed += 1
        by_window[label] = delta
    base_agg = _aggregate({label: base[label]["metrics"] for label in WINDOWS})
    replay_agg = _aggregate({label: replay[label]["metrics"] for label in WINDOWS})
    agg = {
        "baseline": base_agg,
        "h1_replay": replay_agg,
        "aggregate_ev_delta": _round(
            replay_agg["expected_value_score_sum"] - base_agg["expected_value_score_sum"],
            4,
        ),
        "aggregate_pnl_delta": _round(
            replay_agg["total_pnl_sum"] - base_agg["total_pnl_sum"],
            2,
        ),
        "windows_ev_improved": ev_improved,
        "windows_ev_regressed": ev_regressed,
        "by_window": by_window,
    }
    old_ok = by_window["old_thin"]["expected_value_score_delta"] > 0
    aggregate_ok = agg["aggregate_ev_delta"] > 0 and agg["aggregate_pnl_delta"] > 0
    stable_ok = ev_improved >= 2 and by_window["late_strong"]["expected_value_score_delta"] >= -0.05
    drawdown_ok = by_window["mid_weak"]["max_drawdown_pct_delta"] <= 0.01
    agg["gate4_pass"] = bool(old_ok and aggregate_ok and stable_ok and drawdown_ok)
    return agg


def build_payload() -> dict:
    baseline = {}
    h1_replay = {}
    audits = {}
    mfe = {}
    snapshots = {
        label: _load_snapshot(window["snapshot"])
        for label, window in WINDOWS.items()
    }

    for label, window in WINDOWS.items():
        result, state = _run_backtest(window, use_h1_replay=False)
        baseline[label] = {
            "window": window,
            "metrics": _metrics(result),
        }
        audits[label] = _audit_skips(result, snapshots[label])
        mfe[label] = _mfe_giveback_observation(result, snapshots[label])

        replay_result, replay_state = _run_backtest(window, use_h1_replay=True)
        h1_replay[label] = {
            "window": window,
            "metrics": _metrics(replay_result),
            "replay_extra": _variant_extra(replay_result, replay_state),
        }

    delta = _delta_metrics(baseline, h1_replay)
    accepted = bool(delta.get("gate4_pass"))
    status = "accepted_for_production_review" if accepted else "rejected"
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": status,
        "mode": "alpha_search_replay_only",
        "alpha_hypothesis": (
            "Strong candidates in old_thin were over-deferred or slot-sliced under "
            "scarce entry capacity; PIT slot-routing leadership can recover alpha "
            "without increasing global MAX_POSITIONS."
        ),
        "change_type": "entry_position_allocation_replay",
        "single_causal_variable": (
            "When available core slots are 0-1, allow a skipped/deferred candidate "
            "from slot_sliced or scarce_slot_breakout_deferred to replace the weakest "
            "same-day planned entry only if its PIT leadership score is higher."
        ),
        "h1_replay_policy": {
            "name": "scarce_slot_strong_candidate_insertion",
            "global_max_positions_changed": False,
            "replacement_only": True,
            "eligible_skip_reasons": [
                "slot_sliced",
                "scarce_slot_breakout_deferred",
            ],
            "leadership_score_inputs": [
                "trade_quality_score",
                "confidence_score",
                "rs_vs_spy or relative_strength_vs_spy",
                "pct_from_52w_high",
                "volume_ratio or volume_spike_ratio",
                "strategy breakout bonus",
            ],
            "rejected_if": [
                "entry/stop missing",
                "entry <= 5",
                "stop >= entry",
                "initial risk > 12%",
                "candidate score does not beat weakest planned score",
            ],
        },
        "h2_observation": {
            "name": "old_thin_mfe_giveback_protection_observation_only",
            "exit_logic_changed": False,
            "purpose": (
                "Measure loss trades that first had positive MFE, without changing "
                "late_strong or mid_weak target/exit behavior."
            ),
        },
        "windows": WINDOWS,
        "baseline": baseline,
        "opportunity_displacement_audit": audits,
        "mfe_giveback_observation": mfe,
        "h1_replay": h1_replay,
        "delta_metrics": delta,
        "acceptance_rule": (
            "old_thin EV improves, aggregate EV/PnL improves, at least 2/3 windows "
            "improve, late_strong EV does not drop more than 0.05, and mid_weak "
            "drawdown does not increase by more than 1pp."
        ),
        "best_variant_gate4": accepted,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, move the replacement policy into a shared production "
                "helper and expose the same audit fields in run.py/backtester.py."
            ),
        },
        "guardrails": {
            "not_global_max_positions_sweep": True,
            "not_gap_cancel_loosen": True,
            "not_late_mid_exit_change": True,
            "not_single_bad_trade_filter": True,
            "why_not_repeat_old_failures": (
                "This does not test simple slot count, simple sector cap, simple "
                "rank threshold, or market-regime allowlist; it tests replacement "
                "against the weakest same-day planned entry using richer PIT signal "
                "quality fields."
            ),
        },
        "decision": "accepted" if accepted else "rejected",
        "rejection_reason": None if accepted else (
            "H1 slot-routing replay did not satisfy multi-window Gate 4; keep current "
            "production entry planning and use the audit/MFE outputs for the next "
            "mechanism search."
        ),
        "next_action": (
            "Promote through shared production parity module, then rerun standard "
            "three-window backtests."
            if accepted else
            "Do not productionize H1. Use the audit to design a stricter point-in-time "
            "displacement rule or continue with H2 observation-only exit research."
        ),
        "related_files": [
            "quant/experiments/exp_20260502_011_old_thin_slot_routing_alpha.py",
            "data/experiments/exp-20260502-011/old_thin_slot_routing_alpha.json",
            "docs/experiments/logs/exp-20260502-011.json",
            "docs/experiments/tickets/exp-20260502-011.json",
        ],
        "experiment_log_jsonl_note": (
            "Not appended in this run because docs/experiment_log.jsonl already has "
            "unrelated unstaged changes; the structured log and ticket are written "
            "as standalone artifacts to avoid mixing worktree ownership."
        ),
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Old thin slot-routing alpha replay",
        "summary": payload["alpha_hypothesis"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "delta_metrics": payload["delta_metrics"],
        "next_action": payload["next_action"],
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "delta_metrics": payload["delta_metrics"],
        "artifact": str(OUT_JSON),
        "log": str(LOG_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
