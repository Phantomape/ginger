"""exp-20260510-018: effective slot accounting scout.

Observed-only alpha scout. Prior experiments rejected global MAX_POSITIONS
expansion and simple state-gated sixth slots. This narrower run asks whether
the candidates actually blocked by slot scarcity show enough replacement value
to justify a future shared effective-slot accounting policy.

No production path, ranking, sizing, exits, LLM/news, or backtester execution
logic is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from oracle_diagnostics import (  # noqa: E402
    _as_float,
    _earnings_for_candidate,
    _entry_row_index,
    _entry_timing_tags,
    _ticker_rows,
)


EXPERIMENT_ID = "exp-20260510-018"
STEM = "effective_slot_accounting_scout"

SLOT_DECISIONS = ("slot_sliced", "scarce_slot_breakout_deferred")
CORE_STRATEGIES = ("trend_long", "breakout_long")
NOTIONAL_USD = 10_000.0
HOLD_DAYS = 20

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "candidate_events": (
                    "data/experiments/exp-20260510-018/"
                    "entry_candidate_events_late_strong.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "candidate_events": (
                    "data/experiments/exp-20260510-018/"
                    "entry_candidate_events_mid_weak.json"
                ),
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "candidate_events": (
                    "data/experiments/exp-20260510-018/"
                    "entry_candidate_events_old_thin.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

BASELINE = {
    "late_strong": {
        "expected_value_score": 4.2340,
        "sharpe_daily": 4.50,
        "max_drawdown_pct": 0.0548,
        "total_pnl": 94086.91,
        "strategy_total_return_pct": 0.9409,
        "win_rate": 0.7895,
        "total_trades": 19,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.6689,
        "sharpe_daily": 2.70,
        "max_drawdown_pct": 0.0941,
        "total_pnl": 61813.40,
        "strategy_total_return_pct": 0.6181,
        "win_rate": 0.5238,
        "total_trades": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3853,
        "sharpe_daily": 1.35,
        "max_drawdown_pct": 0.0815,
        "total_pnl": 28544.11,
        "strategy_total_return_pct": 0.2854,
        "win_rate": 0.4091,
        "total_trades": 22,
        "signals_generated": 60,
        "signals_survived": 55,
        "survival_rate": 0.9167,
    },
}


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _replace_jsonl_record(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if record.get("experiment_id") != EXPERIMENT_ID:
                kept.append(line)
    kept.append(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _normalize_date(raw_date: Any) -> str | None:
    if raw_date is None:
        return None
    text = str(raw_date)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _load_earnings_for_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for event in events:
        date_str = _normalize_date(event.get("date") or event.get("signal_date"))
        if not date_str or date_str in out:
            continue
        path = REPO_ROOT / "data" / f"earnings_snapshot_{date_str.replace('-', '')}.json"
        if not path.exists():
            out[date_str] = {}
            continue
        payload = _load_json(path)
        earnings = payload.get("earnings") if isinstance(payload, dict) else {}
        out[date_str] = earnings if isinstance(earnings, dict) else {}
    return out


def _strategy_priority(row: dict[str, Any]) -> int:
    if row.get("strategy") == "trend_long":
        return 0
    return 1


def _event_rows(window_name: str, spec: dict[str, Any]) -> dict[str, Any]:
    snapshot = _load_json(REPO_ROOT / spec["snapshot"])
    payload = _load_json(REPO_ROOT / spec["candidate_events"])
    raw_events = payload.get("candidate_events") or []
    rows_by_ticker = _ticker_rows(snapshot)
    spy_rows = rows_by_ticker.get("SPY")
    earnings_by_date = _load_earnings_for_events(raw_events)

    out: list[dict[str, Any]] = []
    for order, event in enumerate(raw_events):
        decision = event.get("decision") or "unknown"
        strategy = event.get("strategy")
        if decision not in SLOT_DECISIONS or strategy not in CORE_STRATEGIES:
            continue
        signal_date = _normalize_date(event.get("date") or event.get("signal_date"))
        ticker = (event.get("ticker") or "").upper()
        if not signal_date or not ticker:
            continue
        rows = rows_by_ticker.get(ticker)
        if not rows:
            continue

        signal_idx = None
        for idx, row in enumerate(rows):
            if row.get("Date") == signal_date:
                signal_idx = idx
                break
        entry_idx = _entry_row_index(rows, signal_date, event.get("details"))
        if signal_idx is None or entry_idx is None:
            continue

        forward = rows[entry_idx : entry_idx + HOLD_DAYS]
        if not forward:
            continue
        entry_open = _as_float(forward[0].get("Open"))
        exit_close = _as_float(forward[-1].get("Close"))
        if not entry_open or exit_close is None:
            continue

        shares = int(NOTIONAL_USD // (entry_open * (1 + ROUND_TRIP_COST_PCT)))
        if shares <= 0:
            continue
        entry_price = entry_open * (1 + ROUND_TRIP_COST_PCT)
        exit_price = exit_close * (1 - ROUND_TRIP_COST_PCT)
        pnl = (exit_price - entry_price) * shares
        invested = entry_price * shares
        highs = [_as_float(row.get("High")) for row in forward]
        lows = [_as_float(row.get("Low")) for row in forward]
        highs = [value for value in highs if value is not None]
        lows = [value for value in lows if value is not None]

        earnings = _earnings_for_candidate(earnings_by_date, signal_date, ticker)
        tags, timing_metrics = _entry_timing_tags(
            rows,
            signal_idx,
            spy_rows,
            signal_date,
            earnings,
        )
        snapshot_signal = event.get("signal_snapshot") or {}
        available_slots = event.get("available_slots_at_entry_loop")
        min_effective_slots_needed = 1
        unlock_path = "one_extra_slot_proxy"
        if decision == "scarce_slot_breakout_deferred":
            min_effective_slots_needed = 2
            unlock_path = "requires_slots_gt_defer_threshold"

        out.append(
            {
                "window": window_name,
                "event_order": order,
                "signal_date": signal_date,
                "entry_date": forward[0].get("Date"),
                "exit_date": forward[-1].get("Date"),
                "ticker": ticker,
                "strategy": strategy,
                "decision": decision,
                "candidate_rank": event.get("candidate_rank"),
                "available_slots_at_entry_loop": available_slots,
                "min_effective_slots_needed": min_effective_slots_needed,
                "unlock_path": unlock_path,
                "sector": snapshot_signal.get("sector", "Unknown"),
                "confidence_score": snapshot_signal.get("confidence_score"),
                "trade_quality_score": snapshot_signal.get("trade_quality_score"),
                "tags": tags,
                "timing_metrics": timing_metrics,
                "entry_open": _round(entry_open, 4),
                "exit_close": _round(exit_close, 4),
                "shares": shares,
                "notional_usd": _round(invested, 2),
                "pnl": _round(pnl, 2),
                "return_pct": _round(pnl / invested, 6) if invested else None,
                "mfe_pct": _round((max(highs) / entry_open) - 1, 6) if highs else None,
                "mae_pct": _round((min(lows) / entry_open) - 1, 6) if lows else None,
            }
        )
    return {
        "window": window_name,
        "window_spec": spec,
        "entry_execution_attribution": payload.get("entry_execution_attribution") or {},
        "slot_missed_rows": out,
        "slot_missed_stats": _stats(out),
        "reason_counts": (
            (payload.get("entry_execution_attribution") or {}).get("reason_counts")
            or {}
        ),
    }


def _positive_share_by_key(rows: list[dict[str, Any]], key: str) -> float | None:
    pnl_by_key: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        pnl_by_key[str(row.get(key) or "")] += float(row.get("pnl") or 0.0)
    positive_values = [value for value in pnl_by_key.values() if value > 0]
    if not positive_values:
        return None
    return max(positive_values) / sum(positive_values)


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "avg_pnl": None,
            "avg_return_pct": None,
            "candidate_count": 0,
            "decision_counts": {},
            "max_single_ticker_positive_share": None,
            "median_return_pct": None,
            "pnl_by_decision": {},
            "pnl_by_strategy": {},
            "pnl_by_ticker": {},
            "total_pnl": 0.0,
            "win_rate": None,
            "windows_present": 0,
        }

    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    returns = [float(row.get("return_pct") or 0.0) for row in rows]
    decision_counts: Counter[str] = Counter(
        str(row.get("decision") or "unknown") for row in rows
    )

    def grouped_pnl(key: str) -> dict[str, Any]:
        grouped: defaultdict[str, float] = defaultdict(float)
        for row in rows:
            grouped[str(row.get(key) or "")] += float(row.get("pnl") or 0.0)
        return {name: _round(value, 2) for name, value in sorted(grouped.items())}

    return {
        "avg_pnl": _round(sum(pnls) / len(pnls), 2),
        "avg_return_pct": _round(sum(returns) / len(returns), 6),
        "candidate_count": len(rows),
        "decision_counts": dict(sorted(decision_counts.items())),
        "max_single_ticker_positive_share": _round(
            _positive_share_by_key(rows, "ticker"),
            4,
        ),
        "median_return_pct": _round(median(returns), 6),
        "pnl_by_decision": grouped_pnl("decision"),
        "pnl_by_strategy": grouped_pnl("strategy"),
        "pnl_by_ticker": grouped_pnl("ticker"),
        "total_pnl": _round(sum(pnls), 2),
        "win_rate": _round(sum(1 for value in pnls if value > 0) / len(pnls), 4),
        "windows_present": len({str(row.get("window") or "") for row in rows}),
    }


def _first_per_day(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("window")), str(row.get("signal_date")))
        sort_key = (
            _strategy_priority(row),
            row.get("candidate_rank") if row.get("candidate_rank") is not None else 999,
            row.get("event_order") or 0,
        )
        old = best.get(key)
        if old is None:
            best[key] = row
            continue
        old_sort = (
            _strategy_priority(old),
            old.get("candidate_rank") if old.get("candidate_rank") is not None else 999,
            old.get("event_order") or 0,
        )
        if sort_key < old_sort:
            best[key] = row
    return [best[key] for key in sorted(best)]


def _aggregate(by_window: OrderedDict[str, Any]) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    for window in by_window.values():
        all_rows.extend(window["slot_missed_rows"])

    one_extra_rows = [
        row for row in all_rows if row.get("decision") == "slot_sliced"
    ]
    breakout_unlock_rows = [
        row
        for row in all_rows
        if row.get("decision") == "scarce_slot_breakout_deferred"
    ]
    primary_stats = _stats(all_rows)
    primary_positive_windows = sum(
        1 for window in by_window.values() if window["slot_missed_stats"]["total_pnl"] > 0
    )
    first_per_day = _first_per_day(all_rows)
    first_one_extra_per_day = _first_per_day(one_extra_rows)
    first_breakout_per_day = _first_per_day(breakout_unlock_rows)

    deterministic_slices = OrderedDict(
        [
            ("all_slot_missed_upper_bound", _stats(all_rows)),
            ("first_slot_missed_per_day", _stats(first_per_day)),
            ("one_extra_slot_slice_slot_sliced_only", _stats(first_one_extra_per_day)),
            ("breakout_release_slice_requires_slots_gt_1", _stats(first_breakout_per_day)),
        ]
    )

    gate_failures = []
    if primary_stats["candidate_count"] < 8:
        gate_failures.append("slot_missed_candidate_count_lt_8")
    if (primary_stats.get("total_pnl") or 0) <= 0:
        gate_failures.append("all_slot_missed_total_pnl_not_positive")
    if (primary_stats.get("win_rate") or 0) < 0.5:
        gate_failures.append("all_slot_missed_win_rate_lt_50pct")
    if (
        primary_stats.get("max_single_ticker_positive_share") is not None
        and primary_stats["max_single_ticker_positive_share"] > 0.5
    ):
        gate_failures.append("single_ticker_positive_share_gt_50pct")
    if primary_positive_windows < 2:
        gate_failures.append("positive_windows_lt_2")

    feasible_positive = any(
        (slice_stats.get("total_pnl") or 0) > 0
        and (slice_stats.get("candidate_count") or 0) >= 4
        for name, slice_stats in deterministic_slices.items()
        if name != "all_slot_missed_upper_bound"
    )
    if not feasible_positive:
        gate_failures.append("no_deterministic_capacity_slice_positive_with_min_count")

    return {
        "primary_observed_slice": "all_slot_missed_upper_bound",
        "all_slot_missed_stats": primary_stats,
        "deterministic_slices": deterministic_slices,
        "positive_windows": primary_positive_windows,
        "gate_passed": not gate_failures,
        "gate_failures": gate_failures,
        "rows": {
            "all_slot_missed": all_rows,
            "first_slot_missed_per_day": first_per_day,
            "one_extra_slot_slice_slot_sliced_only": first_one_extra_per_day,
            "breakout_release_slice_requires_slots_gt_1": first_breakout_per_day,
        },
    }


def _live_slot_snapshot() -> dict[str, Any]:
    path = REPO_ROOT / "data" / "quant_signals_20260508.json"
    if not path.exists():
        return {"status": "missing", "path": _repo_rel(path)}
    payload = _load_json(path)
    heat = payload.get("portfolio_heat") or {}
    plan = (
        payload.get("entry_execution_plan")
        or payload.get("entry_plan")
        or {}
    )
    return {
        "status": "loaded",
        "path": _repo_rel(path),
        "generated_at": payload.get("generated_at"),
        "portfolio_heat_pct": heat.get("portfolio_heat_pct"),
        "max_heat_pct": heat.get("max_heat_pct"),
        "can_add_new_positions": heat.get("can_add_new_positions"),
        "position_count_in_heat_breakdown": len(heat.get("position_breakdown") or []),
        "entry_plan": {
            "active_positions": plan.get("active_positions"),
            "max_positions": plan.get("max_positions"),
            "available_slots": plan.get("available_slots"),
            "signals_before_entry_plan": plan.get("signals_before_entry_plan"),
            "signals_after_deferral": plan.get("signals_after_deferral"),
            "signals_after_entry_plan": plan.get("signals_after_entry_plan"),
            "defer_breakout_when_slots_lte": plan.get("defer_breakout_when_slots_lte"),
            "deferred_breakout_signals": plan.get("deferred_breakout_signals") or [],
            "slot_sliced_signals": plan.get("slot_sliced_signals") or [],
        },
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    agg = payload["aggregate"]
    primary = agg["all_slot_missed_stats"]
    slices = agg["deterministic_slices"]
    lines = [
        f"# {EXPERIMENT_ID} Effective Slot Accounting Scout",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- all slot-missed count: {primary['candidate_count']}",
        f"- all slot-missed PnL: {primary['total_pnl']}",
        f"- all slot-missed win rate: {primary['win_rate']}",
        f"- positive windows: {agg['positive_windows']}",
        f"- single ticker positive share: {primary['max_single_ticker_positive_share']}",
        f"- gate failures: {', '.join(agg['gate_failures']) or 'none'}",
        "",
        "## Deterministic Slices",
        "",
    ]
    for name, stats in slices.items():
        lines.append(
            "- "
            f"{name}: count={stats['candidate_count']}, "
            f"pnl={stats['total_pnl']}, "
            f"win_rate={stats['win_rate']}, "
            f"tickers={stats['pnl_by_ticker']}"
        )
    lines.extend(["", "## By Window", ""])
    for name, window in payload["by_window"].items():
        stats = window["slot_missed_stats"]
        lines.append(
            "- "
            f"{name}: count={stats['candidate_count']}, "
            f"pnl={stats['total_pnl']}, "
            f"win_rate={stats['win_rate']}, "
            f"reasons={window['reason_counts']}"
        )
    live = payload["live_20260508_slot_snapshot"]
    lines.extend(
        [
            "",
            "## Live 2026-05-08 Context",
            "",
            "- "
            f"active_positions={live.get('entry_plan', {}).get('active_positions')}, "
            f"max_positions={live.get('entry_plan', {}).get('max_positions')}, "
            f"available_slots={live.get('entry_plan', {}).get('available_slots')}, "
            f"heat={live.get('portfolio_heat_pct')}, "
            f"can_add_new_positions={live.get('can_add_new_positions')}",
            "- "
            f"deferred_breakouts={live.get('entry_plan', {}).get('deferred_breakout_signals')}",
            "",
            "## Notes",
            "",
            "- Observed-only fixed-notional replacement-value scout.",
            "- Does not change production signals, sizing, orders, ranking, exits, prompts, or core slots.",
            "- `scarce_slot_breakout_deferred` rows require slots greater than the current breakout defer threshold, not just one extra nominal slot.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _write_playbook_update(payload: dict[str, Any]) -> None:
    agg = payload["aggregate"]
    primary = agg["all_slot_missed_stats"]
    first = agg["deterministic_slices"]["first_slot_missed_per_day"]
    one_extra = agg["deterministic_slices"]["one_extra_slot_slice_slot_sliced_only"]
    breakout = agg["deterministic_slices"][
        "breakout_release_slice_requires_slots_gt_1"
    ]
    section = f"""

### 2026-05-10 mechanism update: Effective slot accounting scout

Experiment: `{EXPERIMENT_ID}`

Decision: `{payload['decision']}`.

Finding: raw slot scarcity is a real execution bottleneck, but the historical
replacement-value evidence is not clean enough to justify changing core slot
accounting yet. The tested single variable was observed-only fixed-notional
20-trading-day replacement value for candidates that already survived the
current entry path but were blocked by `slot_sliced` or
`scarce_slot_breakout_deferred`. Global `MAX_POSITIONS`, heat, sizing, ranking,
signals, exits, LLM/news, add-ons, and production orders stayed unchanged.

All slot-missed rows: count `{primary['candidate_count']}`, PnL
`${primary['total_pnl']}`, win rate `{primary['win_rate']}`, positive windows
`{agg['positive_windows']}`, single-ticker positive share
`{primary['max_single_ticker_positive_share']}`. First missed row per day:
count `{first['candidate_count']}`, PnL `${first['total_pnl']}`. Pure one-extra
slot rows (`slot_sliced` only): count `{one_extra['candidate_count']}`, PnL
`${one_extra['total_pnl']}`. Breakout rows that require effective slots above
the one-slot defer threshold: count `{breakout['candidate_count']}`, PnL
`${breakout['total_pnl']}`.

Mechanism insight: the user's 2026-05-08 MU case is structurally important
because heat allowed new risk while raw slot count blocked the core entry plan.
However, because `DEFER_BREAKOUT_WHEN_SLOTS_LTE=1` is active, a breakout does
not become executable merely by creating one nominal slot; the effective slot
accounting policy would need to release enough capacity for `available_slots >
1` or explicitly change scarce-slot breakout routing, which is a separate
causal variable.

Do not repeat: global `MAX_POSITIONS` sweeps, simple sixth-slot gates, or
nearby scarce-slot threshold retunes. A valid retry needs a shared effective
slot accounting design that is exposure/risk based, production-visible in
`run.py`, and evaluated by full portfolio replay with drawdown and tail-risk
impact.
"""
    text = PLAYBOOK.read_text(encoding="utf-8") if PLAYBOOK.exists() else ""
    marker = "\n### 2026-05-10 mechanism update: Effective slot accounting scout"
    start = text.find(marker)
    if start != -1:
        next_start = text.find("\n### ", start + len(marker))
        if next_start == -1:
            text = text[:start].rstrip() + "\n"
        else:
            text = text[:start].rstrip() + "\n" + text[next_start:].lstrip("\n")
    PLAYBOOK.write_text(text.rstrip() + section, encoding="utf-8")


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["decision"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": "capital_allocation / entry_slot_accounting",
        "change_type": "observed_only_fixed_notional_slot_missed_value_scout",
        "mechanism_family": "effective_core_slot_accounting",
        "single_causal_variable": (
            "slot_missed_candidate_fixed_notional_20d_replacement_value"
        ),
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "before_metrics": payload["baseline_metrics"],
        "after_metrics": payload["baseline_metrics"],
        "observed_metrics": {
            "all_slot_missed_stats": payload["aggregate"]["all_slot_missed_stats"],
            "deterministic_slices": payload["aggregate"]["deterministic_slices"],
            "positive_windows": payload["aggregate"]["positive_windows"],
            "gate_passed": payload["aggregate"]["gate_passed"],
            "gate_failures": payload["aggregate"]["gate_failures"],
        },
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": payload.get("rejection_reason"),
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "live_20260508_slot_snapshot": payload["live_20260508_slot_snapshot"],
    }


def main() -> None:
    by_window = OrderedDict(
        (name, _event_rows(name, spec)) for name, spec in WINDOWS.items()
    )
    aggregate = _aggregate(by_window)
    decision = (
        "promising_observed_only_needs_full_replay"
        if aggregate["gate_passed"]
        else "rejected"
    )
    rejection_reason = None
    if not aggregate["gate_passed"]:
        rejection_reason = (
            "Effective slot accounting scout failed the preregistered observed "
            "replacement-value gate: "
            f"{', '.join(aggregate['gate_failures'])}."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "hypothesis": (
            "If raw MAX_POSITIONS is miscounting low-heat diversified holdings as "
            "fully scarce core slots, then candidates blocked by slot_sliced or "
            "scarce_slot_breakout_deferred should show positive replacement value."
        ),
        "decision": decision,
        "rejection_reason": rejection_reason,
        "parameters": {
            "slot_decisions": SLOT_DECISIONS,
            "core_strategies": CORE_STRATEGIES,
            "notional_usd": NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "promotion_gate": {
                "slot_missed_candidate_count": ">= 8",
                "all_slot_missed_total_pnl": "> 0",
                "all_slot_missed_win_rate": ">= 50%",
                "single_ticker_positive_contribution": "<= 50%",
                "positive_windows": ">= 2",
                "deterministic_capacity_slice": "at least one non-upper-bound slice positive with count >= 4",
            },
            "locked_variables": [
                "MAX_POSITIONS",
                "DEFER_BREAKOUT_WHEN_SLOTS_LTE",
                "MAX_PORTFOLIO_HEAT",
                "MAX_POSITION_PCT",
                "signal generation",
                "candidate ranking",
                "sizing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "production orders",
            ],
        },
        "history_check": {
            "exp-20260427-014": (
                "Global MAX_POSITIONS 4/6/7 sweep was rejected; this run does "
                "not change global slots."
            ),
            "exp-20260429-001": (
                "Post-sizing global slot sweep still rejected MAX_POSITIONS "
                "changes; this run only measures blocked-candidate value."
            ),
            "exp-20260429-003": (
                "State-gated sixth slot rejected; this run does not add a "
                "sixth-slot gate."
            ),
            "exp-20260429-006": (
                "Index-dispersion extra slot rejected and exposed harness risk; "
                "this run requires real candidate PnL, not unchanged-trade EV."
            ),
            "exp-20260427-019": (
                "One-slot breakout deferral was accepted as scarce-slot routing; "
                "breakout rows here are separated because they require slots > 1."
            ),
        },
        "baseline_metrics": BASELINE,
        "by_window": by_window,
        "aggregate": aggregate,
        "live_20260508_slot_snapshot": _live_slot_snapshot(),
        "gate4": {
            "passed": None,
            "basis": (
                "Observed-only fixed-notional replacement-value scout; no "
                "portfolio path changed, so canonical before/after metrics are "
                "unchanged."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "production_impact": "none; observed-only experiment script",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "next_retry_requires": [
            "If the observed scout is positive, implement a shared effective-slot accounting adapter in production_parity.py and use it from both run.py and backtester.py.",
            "Full replay must preserve heat cap, avoid slot backfill hindsight, and report drawdown/tail-risk impact.",
            "Do not retry global MAX_POSITIONS or one-variable scarce breakout threshold changes from this result.",
        ],
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(Path(__file__)),
            "data/experiments/exp-20260510-018/entry_candidate_events_late_strong.json",
            "data/experiments/exp-20260510-018/entry_candidate_events_mid_weak.json",
            "data/experiments/exp-20260510-018/entry_candidate_events_old_thin.json",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "hypothesis": payload["hypothesis"],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "artifact": _repo_rel(OUT_JSON),
        "next_retry_requires": payload["next_retry_requires"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _replace_jsonl_record(EXPERIMENT_LOG, _log_record(payload))
    _write_playbook_update(payload)

    print(json.dumps(payload["aggregate"], indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
