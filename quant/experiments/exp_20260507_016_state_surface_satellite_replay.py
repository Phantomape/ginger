"""exp-20260507-016 state-aware surface satellite replay.

Alpha search follow-up to exp-20260507-005. The prior run found a
non-overlapping state-aware candidate surface, but only measured forward
returns. This run tests one executable replay policy: a bounded independent
satellite sleeve that buys the top three non-overlapping production-universe
surface candidates after the decision close and holds for 20 trading days.

No production strategy code, live order path, core ranking, sizing, exits,
universe membership, LLM, or news logic is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    EVENT_NOTIONAL,
    INITIAL_CAPITAL,
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _gate4,
    _load_price_map,
)
from experiments.exp_20260507_005_state_aware_shadow_alpha_surface import (  # noqa: E402
    INDEX_TICKERS,
    _ab_events,
    _load_ohlcv,
    _score_candidates_for_date,
    _state_for_date,
)


EXP_ID = "exp-20260507-016"
STEM = "state_surface_satellite_replay"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HOLD_DAYS = 20
DAILY_CANDIDATE_COUNT = 3
MAX_ACTIVE_SURFACE_POSITIONS = 3

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


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _next_index_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if str(row.get("date") or "") > date_value:
            return idx
    return None


def _candidate_trade(
    candidate: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    decision_date = str(candidate.get("date") or "")[:10]
    rows = prices.get(ticker) or []
    entry_idx = _next_index_after(rows, decision_date)
    if entry_idx is None:
        return {**candidate, "status": "missing_next_entry_price"}
    exit_idx = entry_idx + HOLD_DAYS
    if exit_idx >= len(rows):
        return {**candidate, "status": "missing_exit_price"}
    entry = rows[entry_idx]
    exit_row = rows[exit_idx]
    entry_open = entry.get("open")
    exit_close = exit_row.get("close")
    if not entry_open or not exit_close:
        return {**candidate, "status": "missing_open_or_close"}

    gross_return = float(exit_close) / float(entry_open) - 1.0
    net_return = gross_return - ROUND_TRIP_COST_PCT
    shares = EVENT_NOTIONAL / float(entry_open)
    return {
        **candidate,
        "source": "state_surface_satellite",
        "status": "price_ready",
        "decision_date": decision_date,
        "entry_date": str(entry["date"]),
        "exit_date": str(exit_row["date"]),
        "entry_open": round(float(entry_open), 6),
        "exit_close": round(float(exit_close), 6),
        "gross_return_pct": round(gross_return, 6),
        "net_return_pct": round(net_return, 6),
        "notional": EVENT_NOTIONAL,
        "shares": shares,
        "pnl": round(EVENT_NOTIONAL * net_return, 2),
    }


def _load_core_result(window: dict[str, str]) -> dict[str, Any]:
    result = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def _raw_candidates(
    *,
    label: str,
    window: dict[str, str],
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    ohlcv = _load_ohlcv(REPO_ROOT / window["snapshot"])
    production_universe = sorted(
        ticker
        for ticker in {str(t).upper() for t in get_universe()}
        if ticker not in INDEX_TICKERS and ticker in ohlcv
    )
    ab = _ab_events(result)
    spy_dates = [
        str(row.get("Date") or "")
        for row in ohlcv.get("SPY", [])
        if window["start"] <= str(row.get("Date") or "") <= window["end"]
    ]

    out: list[dict[str, Any]] = []
    for date_str in spy_dates:
        state = _state_for_date(ohlcv, production_universe, date_str)
        ranked = _score_candidates_for_date(ohlcv, production_universe, date_str, state)
        for rank, candidate in enumerate(ranked[:DAILY_CANDIDATE_COUNT], start=1):
            ticker = str(candidate["ticker"]).upper()
            key = (date_str, ticker)
            candidate.update(
                {
                    "window": label,
                    "rank": rank,
                    "overlap_ab_entered": key in ab["entered"],
                    "overlap_ab_candidate": key in ab["all_candidates"],
                    "scarce_slot_pressure_date": date_str in ab["pressure_dates"],
                }
            )
            if candidate["overlap_ab_candidate"]:
                continue
            out.append(_candidate_trade(candidate, prices))
    return out


def _select_trades(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready = [row for row in candidates if row.get("status") == "price_ready"]
    ready.sort(
        key=lambda row: (
            str(row.get("decision_date") or row.get("date") or ""),
            int(row.get("rank") or 99),
            -float(row.get("score") or 0.0),
            str(row.get("ticker") or ""),
        )
    )

    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = [
        {
            "ticker": row.get("ticker"),
            "decision_date": row.get("date"),
            "reason": row.get("status"),
        }
        for row in candidates
        if row.get("status") != "price_ready"
    ]
    active: list[dict[str, Any]] = []
    for row in ready:
        entry_date = str(row["entry_date"])
        active = [trade for trade in active if str(trade["exit_date"]) >= entry_date]
        active_tickers = {str(trade.get("ticker") or "").upper() for trade in active}
        if len(active) >= MAX_ACTIVE_SURFACE_POSITIONS:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "decision_date": row.get("decision_date"),
                    "entry_date": entry_date,
                    "reason": "surface_sleeve_capacity_full",
                    "active_tickers": sorted(active_tickers),
                }
            )
            continue
        if str(row.get("ticker") or "").upper() in active_tickers:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "decision_date": row.get("decision_date"),
                    "entry_date": entry_date,
                    "reason": "ticker_already_active",
                    "active_tickers": sorted(active_tickers),
                }
            )
            continue
        selected.append(row)
        active.append(row)
    return selected, skipped


def _surface_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        surface = str(trade.get("surface") or "unknown")
        row = out.setdefault(surface, {"trade_count": 0, "wins": 0, "total_pnl": 0.0})
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["wins"] += int(pnl > 0)
        row["total_pnl"] += pnl
    for row in out.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["total_pnl"] = round(float(row["total_pnl"]), 2)
    return out


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _delta(before[label], after[label])) for label in WINDOWS)
    baseline_ev = sum(float(before[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    after_ev = sum(float(after[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    baseline_pnl = sum(float(before[label]["total_pnl"] or 0.0) for label in WINDOWS)
    after_pnl = sum(float(after[label]["total_pnl"] or 0.0) for label in WINDOWS)
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - baseline_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - baseline_ev) / baseline_ev, 6)
        if baseline_ev
        else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - baseline_pnl) / baseline_pnl, 6)
        if baseline_pnl
        else None,
        "windows_ev_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0)
            > (before[label].get("expected_value_score") or 0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0)
            < (before[label].get("expected_value_score") or 0)
        ),
        "windows_pnl_improved": sum(
            1 for label in WINDOWS if (after[label].get("total_pnl") or 0) > (before[label].get("total_pnl") or 0)
        ),
        "windows_pnl_regressed": sum(
            1 for label in WINDOWS if (after[label].get("total_pnl") or 0) < (before[label].get("total_pnl") or 0)
        ),
    }


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [trade for trade in trades if float(trade.get("pnl") or 0.0) > 0]
    total_positive = sum(float(trade.get("pnl") or 0.0) for trade in positive)
    if total_positive <= 0:
        return None
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for trade in positive:
        by_ticker[str(trade.get("ticker") or "").upper()] += float(trade.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 4) if by_ticker else None


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-016 State Surface Satellite Replay",
        "",
        "Replay-only alpha search. Core A/B entries, ranking, sizing, exits, LLM, news, and production orders are unchanged.",
        "",
        "## Three-window result",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Sleeve trades | Sleeve PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:,.2f} | {trades} | ${epnl:,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=sleeve["selected_trade_count"],
                epnl=sleeve["selected_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Surface Contribution",
            "",
            "```json",
            json.dumps(payload["surface_contribution"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    _write_text(AUDIT_MD, "\n".join(lines))


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = {
        "experiment_id": EXP_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
    }
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line
            and f'"experiment_id": "{EXP_ID}"' not in line
        ]
    lines.append(json.dumps(_safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prices = _load_price_map()
    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    per_window: dict[str, dict[str, Any]] = OrderedDict()
    surface_contribution: dict[str, Any] = OrderedDict()
    core_results: dict[str, dict[str, Any]] = {}

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_results[label] = result
        candidates = _raw_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )
        selected, skipped = _select_trades(candidates)
        event_curve = _event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _core_metrics(result)
        after_metrics[label] = _combined_metrics(result, event_curve, selected)
        surface_summary = _surface_summary(selected)
        surface_contribution[label] = surface_summary
        per_window[label] = {
            "raw_candidate_count": len(candidates),
            "price_ready_candidate_count": sum(1 for row in candidates if row.get("status") == "price_ready"),
            "selected_trade_count": len(selected),
            "selected_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in selected), 2),
            "selected_win_rate": round(
                sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0) / len(selected),
                4,
            )
            if selected
            else None,
            "surface_summary": surface_summary,
            "skipped_reason_counts": dict(Counter(str(row.get("reason") or "unknown") for row in skipped)),
            "selected_trades": [
                {
                    "ticker": trade.get("ticker"),
                    "surface": trade.get("surface"),
                    "decision_date": trade.get("decision_date"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "rank": trade.get("rank"),
                    "score": trade.get("score"),
                    "pnl": trade.get("pnl"),
                    "net_return_pct": trade.get("net_return_pct"),
                }
                for trade in selected
            ],
        }

    delta = _aggregate_delta(before_metrics, after_metrics)
    gate4_by_window = OrderedDict(
        (label, _gate4(before_metrics[label], after_metrics[label])) for label in WINDOWS
    )
    all_selected = [
        trade
        for window_payload in per_window.values()
        for trade in window_payload["selected_trades"]
    ]
    positive_share = _single_ticker_positive_share(all_selected)

    material = (
        (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
        or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
        or any(row["passes_sharpe"] for row in gate4_by_window.values())
        or any(row["passes_drawdown"] for row in gate4_by_window.values())
    )
    passed_without_regression = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and material
        and (positive_share is None or positive_share <= 0.50)
    )
    decision = "promising_replay_only" if passed_without_regression else "rejected"
    decision_rationale = (
        "Promising replay-only: the state-aware surface satellite improved the majority of canonical windows without EV regression. It remains replay-only; production use requires a shared run.py/backtester.py adapter and parity tests."
        if passed_without_regression
        else "Rejected: the state-aware surface satellite did not clear the three-window Gate 4 standard without EV regression, materiality, and concentration controls."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_satellite_replay",
        "mechanism_family": "state_aware_candidate_pool_extension",
        "hypothesis": (
            "The state-aware non-overlapping candidate surface from exp-20260507-005 can be converted into a bounded satellite sleeve that improves EV across the three canonical windows without changing core A/B logic."
        ),
        "alpha_hypothesis": {
            "category": "entry/allocation",
            "why_this_now": (
                "LLM soft-ranking is sample-limited, SEC/earnings directional fields are incomplete, event bundle source pruning just failed, and the state surface is the strongest remaining observed non-overlap alpha lead."
            ),
        },
        "historical_experiment_check": {
            "similar_experiments": {
                "exp-20260507-005": "Observed-only state surface found 1136 non-overlap candidates and positive aggregate 20d forward returns, but no executable policy.",
                "exp-20260506-030": "Observed event/state shadow universe was not promotable because comparable replacement value was sparse and not positive in all windows.",
                "exp-20260505-011/020": "Consumer-platform broad universe promotion/gate rejected; this run adds no ticker and restricts to production universe names.",
                "exp-20260507-012/015": "Event overlay full bundle remains stronger than source pruning; SEC negative text severity rejected.",
            },
            "mechanism_no_go_check": [
                "No LLM/prompt change.",
                "No SEC text phrase tuning.",
                "No broad ETF or noisy ticker expansion.",
                "No core slot increase, ranking change, threshold tune, or exit change.",
                "No production order change from replay evidence.",
            ],
            "why_not_simple_repeat": (
                "The prior state-surface run was observed-only. This run tests one executable replay policy with next-open entry, fixed hold, bounded capital, and current core baseline metrics."
            ),
        },
        "parameters": {
            "single_causal_variable": "bounded state-aware surface satellite sleeve",
            "decision_timing": "score after decision-date close; enter next trading day open",
            "candidate_source": "production universe only, excluding SPY/QQQ/IWM and existing same-day core candidates",
            "daily_candidate_count": DAILY_CANDIDATE_COUNT,
            "max_active_surface_positions": MAX_ACTIVE_SURFACE_POSITIONS,
            "hold_days": HOLD_DAYS,
            "event_notional_usd": EVENT_NOTIONAL,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe files",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk sizing",
                "position slots",
                "gap cancels",
                "add-ons",
                "exits",
                "LLM/news replay",
                "earnings strategy",
                "production orders",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "gate4": {
            "rule": "EV first; require majority-window EV improvement, zero EV regressions, material EV/PnL/Sharpe/DD improvement, and <=50% single-ticker positive contribution.",
            "by_window": gate4_by_window,
            "passed_without_regression": passed_without_regression,
            "single_ticker_positive_share": positive_share,
        },
        "surface_sleeve": per_window,
        "surface_contribution": surface_contribution,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"] for label in WINDOWS
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_positive": (
                "A shared state-surface policy adapter consumed by both run.py and backtester.py plus parity tests is required before production use."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking outcome data remains sample-limited; this tests a non-LLM alpha lead instead of weakening LLM.",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if passed_without_regression else decision_rationale,
        "why_not_other_attractive_points": (
            "Event source pruning and SEC negative text severity were just rejected, runner exits failed Gate 4, SEC/earnings directional filing fields are missing, and LLM soft-ranking still lacks enough replay coverage."
        ),
        "risk_of_change": (
            "The surface can over-select already-hot momentum names and may crowd into correlated leaders; the replay blocks live promotion until a shared adapter and parity tests exist."
        ),
        "next_action": (
            "If promising, implement a default-off shared state-surface paper adapter; if rejected, do not retry nearby top-N/cap/hold parameters without new forward evidence."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(AUDIT_MD),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "State surface satellite replay",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "related_log": _repo_rel(LOG_JSON),
            "artifact": _repo_rel(OUT_JSON),
        },
    )
    _write_report(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "delta_metrics": payload["delta_metrics"],
                    "gate4": payload["gate4"],
                    "surface_trades": {
                        label: payload["surface_sleeve"][label]["selected_trade_count"]
                        for label in WINDOWS
                    },
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
