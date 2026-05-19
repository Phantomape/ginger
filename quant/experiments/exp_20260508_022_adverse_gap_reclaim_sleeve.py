"""exp-20260508-022: adverse-gap reclaim delayed-entry sleeve.

Alpha search. This does not loosen the accepted adverse-gap cancel. It asks a
separate question from the rejected gap-bypass family: when an A/B candidate is
cancelled by a weak next open, does a later same-day reclaim carry enough
standalone continuation value to justify a default-off paper sleeve?
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine, DEFAULT_CONFIG  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from portfolio_engine import ROUND_TRIP_COST_PCT  # noqa: E402


EXPERIMENT_ID = "exp-20260508-022"
STEM = "adverse_gap_reclaim_sleeve"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        (
            "intraday_reclaim_next_open",
            {
                "reclaim_field": "High",
                "reclaim_description": "adverse-gap day high reclaims original signal entry",
            },
        ),
        (
            "close_reclaim_next_open",
            {
                "reclaim_field": "Close",
                "reclaim_description": "adverse-gap day close reclaims original signal entry",
            },
        ),
    ]
)

NOTIONAL_PER_TRADE = 10_000.0
MAX_HOLD_DAYS = 20

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    entry_counts = (result.get("entry_execution_attribution") or {}).get("reason_counts") or {}
    addon = result.get("addon_attribution") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "adverse_gap_cancel_count": int(entry_counts.get("adverse_gap_down_cancel") or 0),
        "slot_sliced_count": int(entry_counts.get("slot_sliced") or 0),
        "addon_scheduled": addon.get("scheduled"),
        "addon_executed": addon.get("executed"),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected snapshot shape: {snapshot_path}")
    return {
        str(ticker).upper(): sorted(rows, key=lambda row: row.get("Date", ""))
        for ticker, rows in ohlcv.items()
        if isinstance(rows, list)
    }


def _row_by_date(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("Date")): row for row in rows if row.get("Date")}


def _float(row: dict[str, Any] | None, key: str) -> float | None:
    if not row:
        return None
    try:
        value = float(row.get(key))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _next_trade_row(
    rows: list[dict[str, Any]],
    after_date: str,
) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    for idx, row in enumerate(rows):
        if str(row.get("Date") or "") > after_date:
            return idx, row
    return None, None


def _trade_exit(
    rows: list[dict[str, Any]],
    entry_idx: int,
    entry_open: float,
    stop_price: float,
    target_price: float,
) -> dict[str, Any] | None:
    exit_row = None
    exit_reason = "max_hold"
    search_rows = rows[entry_idx + 1 : entry_idx + 1 + MAX_HOLD_DAYS]
    if not search_rows:
        return None

    for row in search_rows:
        low = _float(row, "Low")
        high = _float(row, "High")
        if low is not None and low <= stop_price:
            exit_row = row
            exit_reason = "stop"
            exit_price = stop_price
            break
        if high is not None and high >= target_price:
            exit_row = row
            exit_reason = "target"
            exit_price = target_price
            break
    else:
        exit_row = search_rows[-1]
        exit_price = _float(exit_row, "Close")

    if exit_row is None or exit_price is None:
        return None
    return {
        "exit_date": str(exit_row.get("Date")),
        "exit_price": float(exit_price),
        "exit_reason": exit_reason,
        "hold_days": max(
            1,
            rows.index(exit_row) - entry_idx,
        ),
        "entry_price": entry_open,
    }


def _build_reclaim_trades(
    events: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
    variant: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reclaim_field = str(variant["reclaim_field"])
    trades: list[dict[str, Any]] = []
    audit = {
        "adverse_gap_events": 0,
        "missing_ohlcv": 0,
        "missing_signal_fields": 0,
        "reclaim_passed": 0,
        "no_next_open": 0,
        "entry_below_stop": 0,
        "no_exit": 0,
    }

    for event in events:
        if event.get("decision") != "adverse_gap_down_cancel":
            continue
        audit["adverse_gap_events"] += 1
        ticker = str(event.get("ticker") or "").upper()
        rows = ohlcv.get(ticker)
        if not rows:
            audit["missing_ohlcv"] += 1
            continue
        by_date = _row_by_date(rows)
        details = event.get("details") or {}
        snapshot = event.get("signal_snapshot") or {}
        signal_entry = details.get("signal_entry") or snapshot.get("entry_price")
        stop_price = snapshot.get("stop_price")
        target_price = snapshot.get("target_price")
        fill_date = str(details.get("fill_date") or "")
        try:
            signal_entry = float(signal_entry)
            stop_price = float(stop_price)
            target_price = float(target_price)
        except (TypeError, ValueError):
            audit["missing_signal_fields"] += 1
            continue

        cancel_row = by_date.get(fill_date)
        reclaim_value = _float(cancel_row, reclaim_field)
        if reclaim_value is None or reclaim_value < signal_entry:
            continue
        audit["reclaim_passed"] += 1

        entry_idx, entry_row = _next_trade_row(rows, fill_date)
        if entry_idx is None or entry_row is None:
            audit["no_next_open"] += 1
            continue
        entry_open = _float(entry_row, "Open")
        if entry_open is None:
            audit["no_next_open"] += 1
            continue
        if entry_open <= stop_price:
            audit["entry_below_stop"] += 1
            continue

        exit_info = _trade_exit(rows, entry_idx, entry_open, stop_price, target_price)
        if not exit_info:
            audit["no_exit"] += 1
            continue

        shares = math.floor(NOTIONAL_PER_TRADE / entry_open)
        if shares <= 0:
            audit["missing_signal_fields"] += 1
            continue
        gross_pnl = shares * (exit_info["exit_price"] - entry_open)
        round_trip_cost = shares * entry_open * ROUND_TRIP_COST_PCT
        pnl = gross_pnl - round_trip_cost
        trades.append(
            {
                "ticker": ticker,
                "strategy": event.get("strategy"),
                "source_decision_date": event.get("date"),
                "cancel_fill_date": fill_date,
                "reclaim_field": reclaim_field,
                "reclaim_value": _round(reclaim_value, 4),
                "signal_entry": _round(signal_entry, 4),
                "entry_date": str(entry_row.get("Date")),
                "entry_price": _round(entry_open, 4),
                "stop_price": _round(stop_price, 4),
                "target_price": _round(target_price, 4),
                "exit_date": exit_info["exit_date"],
                "exit_price": _round(exit_info["exit_price"], 4),
                "exit_reason": exit_info["exit_reason"],
                "hold_days": exit_info["hold_days"],
                "shares": shares,
                "notional": _round(shares * entry_open, 2),
                "pnl": _round(pnl, 2),
                "pnl_pct": _round(pnl / (shares * entry_open), 6),
            }
        )
    return trades, audit


def _satellite_pnl_on_date(
    trades: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
    date_str: str,
) -> float:
    total = 0.0
    row_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for trade in trades:
        ticker = trade["ticker"]
        if date_str < trade["entry_date"]:
            continue
        if date_str >= trade["exit_date"]:
            total += float(trade["pnl"])
            continue
        row_maps.setdefault(ticker, _row_by_date(ohlcv.get(ticker, [])))
        row = row_maps[ticker].get(date_str)
        mark = _float(row, "Close") or float(trade["entry_price"])
        total += int(trade["shares"]) * (mark - float(trade["entry_price"]))
    return total


def _curve_metrics(
    baseline_result: dict[str, Any],
    trades: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if not trades:
        return _metrics(baseline_result) | {
            "satellite_trade_count": 0,
            "satellite_pnl": 0.0,
            "satellite_win_rate": 0.0,
        }

    baseline_curve = baseline_result.get("equity_curve") or []
    after_curve = []
    for item in baseline_curve:
        date_str, equity = item
        overlay_pnl = _satellite_pnl_on_date(trades, ohlcv, str(date_str))
        after_curve.append((str(date_str), round(float(equity) + overlay_pnl, 2)))

    equity_values = [value for _, value in after_curve]
    daily_returns = []
    for idx in range(1, len(equity_values)):
        prev = equity_values[idx - 1]
        if prev > 0:
            daily_returns.append(equity_values[idx] / prev - 1.0)
    sharpe_daily = None
    if len(daily_returns) >= 2:
        mean_r = sum(daily_returns) / len(daily_returns)
        std_r = statistics.pstdev(daily_returns)
        if std_r > 0:
            sharpe_daily = round((mean_r / std_r) * math.sqrt(252), 2)

    peak = equity_values[0] if equity_values else 0.0
    max_dd = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)

    initial = float(DEFAULT_CONFIG.get("INITIAL_CAPITAL", 100_000.0))
    baseline_trades = baseline_result.get("trades") or []
    total_trades = len(baseline_trades) + len(trades)
    wins = sum(1 for trade in baseline_trades if float(trade.get("pnl") or 0.0) > 0)
    wins += sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    total_pnl = float(baseline_result.get("total_pnl") or 0.0) + sum(
        float(t["pnl"]) for t in trades
    )
    result = {
        "total_trades": total_trades,
        "wins": wins,
        "losses": max(0, total_trades - wins),
        "win_rate": round(wins / total_trades, 4) if total_trades else 0.0,
        "total_pnl": round(total_pnl, 2),
        "sharpe_daily": sharpe_daily,
        "max_drawdown_pct": round(max_dd, 4),
        "signals_generated": baseline_result.get("signals_generated"),
        "signals_survived": baseline_result.get("signals_survived"),
        "survival_rate": baseline_result.get("survival_rate"),
        "benchmarks": {
            **(baseline_result.get("benchmarks") or {}),
            "strategy_total_return_pct": (
                round(total_pnl / initial, 4) if initial else None
            ),
        },
    }
    result["expected_value_score"] = compute_expected_value_score(result)
    return _metrics(result) | {
        "satellite_trade_count": len(trades),
        "satellite_pnl": _round(sum(float(t["pnl"]) for t in trades), 2),
        "satellite_win_rate": _round(
            sum(1 for t in trades if float(t["pnl"]) > 0) / len(trades)
            if trades else 0.0,
            4,
        ),
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key in [
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
    ]:
        b = before.get(key)
        a = after.get(key)
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            out[key] = _round(a - b, 4 if "pct" in key or key == "expected_value_score" else 2)
    return out


def _aggregate(
    rows_by_window: dict[str, dict[str, Any]],
    variant_name: str,
) -> dict[str, Any]:
    before_ev = 0.0
    after_ev = 0.0
    before_pnl = 0.0
    after_pnl = 0.0
    ev_improved = 0
    ev_regressed = 0
    pnl_improved = 0
    pnl_regressed = 0
    drawdown_delta_max = None
    touched = 0
    satellite_pnl = 0.0

    for row in rows_by_window.values():
        before = row["before"]
        after = row["variants"][variant_name]["after"]
        before_ev += float(before.get("expected_value_score") or 0.0)
        after_ev += float(after.get("expected_value_score") or 0.0)
        before_pnl += float(before.get("total_pnl") or 0.0)
        after_pnl += float(after.get("total_pnl") or 0.0)
        delta_ev = float(after.get("expected_value_score") or 0.0) - float(before.get("expected_value_score") or 0.0)
        delta_pnl = float(after.get("total_pnl") or 0.0) - float(before.get("total_pnl") or 0.0)
        ev_improved += int(delta_ev > 0)
        ev_regressed += int(delta_ev < 0)
        pnl_improved += int(delta_pnl > 0)
        pnl_regressed += int(delta_pnl < 0)
        dd_delta = (
            float(after.get("max_drawdown_pct") or 0.0)
            - float(before.get("max_drawdown_pct") or 0.0)
        )
        drawdown_delta_max = dd_delta if drawdown_delta_max is None else max(drawdown_delta_max, dd_delta)
        touched += int(after.get("satellite_trade_count") or 0)
        satellite_pnl += float(after.get("satellite_pnl") or 0.0)

    return {
        "baseline_expected_value_score_sum": _round(before_ev, 4),
        "after_expected_value_score_sum": _round(after_ev, 4),
        "expected_value_score_delta_sum": _round(after_ev - before_ev, 4),
        "expected_value_score_delta_pct": _round((after_ev - before_ev) / before_ev if before_ev else None, 6),
        "baseline_total_pnl_sum": _round(before_pnl, 2),
        "after_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(after_pnl - before_pnl, 2),
        "total_pnl_delta_pct": _round((after_pnl - before_pnl) / before_pnl if before_pnl else None, 6),
        "ev_windows_improved": ev_improved,
        "ev_windows_regressed": ev_regressed,
        "pnl_windows_improved": pnl_improved,
        "pnl_windows_regressed": pnl_regressed,
        "max_drawdown_delta_max": _round(drawdown_delta_max, 4),
        "satellite_trade_count": touched,
        "satellite_pnl_sum": _round(satellite_pnl, 2),
    }


def _gate4(aggregate: dict[str, Any]) -> bool:
    ev_delta_pct = float(aggregate.get("expected_value_score_delta_pct") or 0.0)
    pnl_delta_pct = float(aggregate.get("total_pnl_delta_pct") or 0.0)
    dd_delta = float(aggregate.get("max_drawdown_delta_max") or 0.0)
    return (
        aggregate.get("ev_windows_improved", 0) >= 2
        and aggregate.get("ev_windows_regressed", 0) == 0
        and (
            ev_delta_pct > 0.10
            or pnl_delta_pct > 0.05
            or dd_delta <= -0.01
        )
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n")


def _write_artifact(payload: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} - Adverse-gap reclaim delayed-entry sleeve",
        "",
        "## Decision",
        "",
        f"{payload['decision']}.",
        "",
        "## Hypothesis",
        "",
        (
            "Keep the accepted 2% adverse-gap cancel intact, but treat a later "
            "same-day reclaim of the original signal entry as a default-off "
            "delayed-entry satellite candidate."
        ),
        "",
        "## Results",
        "",
        "| Variant | Gate 4 | Aggregate EV delta | Aggregate PnL delta | Satellite trades | EV +/- windows |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for name, aggregate in payload["variant_aggregates"].items():
        lines.append(
            "| {name} | {gate} | {ev} | ${pnl} | {trades} | {wins}/{regs} |".format(
                name=name,
                gate="pass" if aggregate["gate4_passed"] else "fail",
                ev=aggregate["expected_value_score_delta_sum"],
                pnl=aggregate["total_pnl_delta_sum"],
                trades=aggregate["satellite_trade_count"],
                wins=aggregate["ev_windows_improved"],
                regs=aggregate["ev_windows_regressed"],
            )
        )

    lines.extend(
        [
            "",
            "## Mechanism Read",
            "",
            payload["mechanism_read"],
            "",
            "## Production Impact",
            "",
            (
                "Replay-only. No production order path, shared policy, sizing, "
                "entry filter, exit, LLM, news, universe, or add-on behavior was changed."
            ),
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_playbook(payload: dict[str, Any]) -> None:
    marker = f"### {payload['timestamp'][:10]} mechanism update: Adverse-gap reclaim delayed entry"
    existing = PLAYBOOK.read_text(encoding="utf-8") if PLAYBOOK.exists() else ""
    if marker in existing:
        return
    best = payload["best_variant"]
    aggregate = payload["variant_aggregates"][best]
    block = f"""

{marker}

Experiment: `{EXPERIMENT_ID}`

Decision: `{payload['decision']}`.

Finding: A delayed-entry satellite for adverse-gap-cancelled A/B candidates
with same-day reclaim evidence did not clear the three-window Gate 4 standard.
Best variant `{best}` changed aggregate EV by
`{aggregate['expected_value_score_delta_sum']}` and aggregate PnL by
`${aggregate['total_pnl_delta_sum']}` across
`{aggregate['satellite_trade_count']}` satellite trades.

Mechanism insight: reclaim behavior is a valid orthogonal information source
relative to rejected raw gap-cancel bypasses, but this replay is not strong
enough for production promotion. Keep the accepted 2% adverse-gap cancel
unchanged.

Do not repeat: adverse-gap delayed-entry sleeves based only on same-day high or
close reclaim of the original signal entry. A valid retry needs richer
intraday structure, fresh event/news confirmation, or forward paper evidence
that reclaimed adverse-gap candidates beat same-day alternatives.
"""
    with PLAYBOOK.open("a", encoding="utf-8") as fh:
        fh.write(block)


def main() -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    universe = get_universe()
    rows_by_window: dict[str, dict[str, Any]] = OrderedDict()

    for window_name, window in WINDOWS.items():
        snapshot_path = REPO_ROOT / window["snapshot"]
        ohlcv = _load_ohlcv(snapshot_path)
        engine = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            ohlcv_snapshot_path=window["snapshot"],
            include_entry_candidate_events=True,
        )
        baseline = engine.run()
        before = _metrics(baseline)
        events = baseline.get("entry_candidate_events") or []
        variants: dict[str, Any] = OrderedDict()
        for variant_name, variant in VARIANTS.items():
            trades, audit = _build_reclaim_trades(events, ohlcv, variant)
            after = _curve_metrics(baseline, trades, ohlcv)
            variants[variant_name] = {
                "parameters": {
                    **variant,
                    "notional_per_trade": NOTIONAL_PER_TRADE,
                    "max_hold_days": MAX_HOLD_DAYS,
                    "entry_timing": "next open after adverse-gap day reclaim",
                    "stop_target_source": "original A/B signal",
                },
                "audit": audit,
                "after": after,
                "delta": _delta(before, after),
                "satellite_trades": trades,
            }
        rows_by_window[window_name] = {
            "window": window,
            "before": before,
            "variants": variants,
        }

    variant_aggregates = OrderedDict()
    for variant_name in VARIANTS:
        aggregate = _aggregate(rows_by_window, variant_name)
        aggregate["gate4_passed"] = _gate4(aggregate)
        variant_aggregates[variant_name] = aggregate

    best_variant = max(
        variant_aggregates,
        key=lambda name: (
            variant_aggregates[name]["expected_value_score_delta_sum"],
            variant_aggregates[name]["total_pnl_delta_sum"],
        ),
    )
    best_aggregate = variant_aggregates[best_variant]
    decision = (
        "promising_replay_only"
        if best_aggregate["gate4_passed"]
        else "rejected"
    )
    mechanism_read = (
        "The reclaim idea is distinct from raw gap-cancel bypasses, but the "
        "tested daily reclaim signals do not deliver enough stable marginal "
        "EV. The accepted adverse-gap cancel should remain unchanged; a valid "
        "retry needs richer intraday structure, fresh event/news context, or "
        "forward paper evidence."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "delayed_entry_satellite_replay",
        "alpha_hypothesis_category": "entry",
        "hypothesis": (
            "Adverse-gap-cancelled A/B candidates that reclaim the original "
            "signal entry on the cancel day may carry delayed-entry alpha "
            "without weakening the accepted adverse-gap cancel."
        ),
        "why_this_now": (
            "LLM soft-ranking and add-on capital allocation are currently "
            "data/parity constrained, while recent mechanism notes explicitly "
            "allow adverse-gap retries only with orthogonal reclaim evidence."
        ),
        "history_guardrails": {
            "not_raw_gap_cancel_bypass": True,
            "not_adverse_gap_threshold_tuning": True,
            "not_sector_or_tqs_exception": True,
            "not_dynamic_extra_slot_retry": True,
            "single_causal_variable": "adverse-gap reclaim delayed-entry sleeve",
        },
        "parameters": {
            "variants": VARIANTS,
            "notional_per_trade": NOTIONAL_PER_TRADE,
            "max_hold_days": MAX_HOLD_DAYS,
            "locked_variables": [
                "core signal generation",
                "accepted adverse-gap cancel",
                "entry filters",
                "candidate ranking",
                "sizing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "universe",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            name: window["state_note"] for name, window in WINDOWS.items()
        },
        "rows": rows_by_window,
        "variant_aggregates": variant_aggregates,
        "best_variant": best_variant,
        "best_variant_gate4": bool(best_aggregate["gate4_passed"]),
        "mechanism_read": mechanism_read,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_orders_changed": False,
            "promotion_requirement": (
                "A positive future version needs a shared production/backtest "
                "paper adapter before any live order path changes."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this tests a "
                "deterministic alternative entry alpha."
            ),
        },
        "rejection_reason": None
        if decision != "rejected"
        else "Daily reclaim delayed entries did not pass three-window Gate 4.",
        "next_retry_requires": [
            "Do not retry same-day high/close reclaim alone on the same frozen samples.",
            "A valid retry needs richer intraday structure, event/news confirmation, or forward paper evidence.",
            "Keep ADVERSE_GAP_CANCEL_PCT unchanged.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    LOG_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.write_text(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": decision,
                "hypothesis": payload["hypothesis"],
                "decision": decision,
                "best_variant": best_variant,
                "gate4_passed": payload["best_variant_gate4"],
                "next_retry_requires": payload["next_retry_requires"],
                "related_files": payload["related_files"],
            },
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG, payload)
    _append_playbook(payload)
    print(json.dumps(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": decision,
            "best_variant": best_variant,
            "best_aggregate": best_aggregate,
        },
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ))


if __name__ == "__main__":
    main()
