"""exp-20260507-019 satellite shared-capacity allocation replay.

Alpha search. The strongest current replay-positive non-core surfaces are the
default-off event overlay bundle and the default-off state-surface satellite.
This experiment changes one causal variable: allow state-surface trades to use
unused slots inside the existing three-position satellite budget, without
displacing event-bundle trades.

No production orders, core A/B signals, ranking, sizing, exits, LLM/news,
universe membership, thresholds, event source definitions, or holding periods
are changed.
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

from experiments.exp_20260504_049_default_off_event_overlay_bundle import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS as EVENT_HOLD_DAYS,
    ROUND_TRIP_COST_PCT,
    WINDOWS,
    _aggregate_delta,
    _combined_metrics,
    _core_metrics,
    _event_equity_curve,
    _gate4,
    _load_core_result,
    _load_event_trades,
)
from experiments.exp_20260507_016_state_surface_satellite_replay import (  # noqa: E402
    HOLD_DAYS as STATE_HOLD_DAYS,
    _raw_candidates as _state_raw_candidates,
    _select_trades as _select_state_trades,
)


EXP_ID = "exp-20260507-019"
STEM = "satellite_shared_capacity"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXP_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MAX_ACTIVE_SATELLITE_POSITIONS = 3
SOURCE_PRIORITY = {
    "sec_governance_procedural": 0,
    "sec_negative_reaction": 1,
    "form4_meaningful_purchase": 2,
    "state_surface_satellite": 3,
}


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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _source(row: dict[str, Any]) -> str:
    return str(row.get("source") or "unknown")


def _trade_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("ticker") or "").upper(),
        str(row.get("entry_date") or "")[:10],
        str(row.get("exit_date") or "")[:10],
    )


def _entry_date(row: dict[str, Any]) -> str:
    return str(row.get("entry_date") or "")[:10]


def _exit_date(row: dict[str, Any]) -> str:
    return str(row.get("exit_date") or "")[:10]


def _candidate_sort(row: dict[str, Any]) -> tuple[str, int, int, float, str]:
    source = _source(row)
    rank = int(row.get("rank") or 99)
    return (
        _entry_date(row),
        SOURCE_PRIORITY.get(source, 99),
        rank,
        -float(row.get("score") or 0.0),
        str(row.get("ticker") or ""),
    )


def _dedupe_ready_trades(trades: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for row in sorted(trades, key=_candidate_sort):
        key = _trade_key(row)
        existing = accepted.get(key)
        if existing is None:
            accepted[key] = row
            continue
        duplicates.append(
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "source": _source(row),
                "kept_source": _source(existing),
                "reason": "duplicate_same_ticker_entry_exit",
            }
        )
    return list(accepted.values()), duplicates


def _select_shared_capacity(
    trades: list[dict[str, Any]],
    *,
    max_active: int = MAX_ACTIVE_SATELLITE_POSITIONS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready, duplicate_skips = _dedupe_ready_trades(trades)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = list(duplicate_skips)
    active: list[dict[str, Any]] = []

    for row in sorted(ready, key=_candidate_sort):
        entry_date = _entry_date(row)
        active = [trade for trade in active if _exit_date(trade) >= entry_date]
        active_tickers = {str(trade.get("ticker") or "").upper() for trade in active}
        ticker = str(row.get("ticker") or "").upper()
        if len(active) >= max_active:
            skipped.append(
                {
                    "ticker": ticker,
                    "source": _source(row),
                    "entry_date": entry_date,
                    "reason": "shared_satellite_capacity_full",
                    "active_sources": sorted(_source(trade) for trade in active),
                    "active_tickers": sorted(active_tickers),
                }
            )
            continue
        if ticker in active_tickers:
            skipped.append(
                {
                    "ticker": ticker,
                    "source": _source(row),
                    "entry_date": entry_date,
                    "reason": "ticker_already_active_in_shared_satellite",
                    "active_sources": sorted(_source(trade) for trade in active),
                }
            )
            continue
        selected.append(row)
        active.append(row)
    return selected, skipped


def _source_summary(trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        source = _source(trade)
        row = out.setdefault(source, {"trade_count": 0, "wins": 0, "total_pnl": 0.0})
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["wins"] += int(pnl > 0)
        row["total_pnl"] += pnl
    for row in out.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["total_pnl"] = round(float(row["total_pnl"]), 2)
    return out


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    total_positive = 0.0
    for trade in trades:
        pnl = float(trade.get("pnl") or 0.0)
        if pnl <= 0:
            continue
        by_ticker[str(trade.get("ticker") or "").upper()] += pnl
        total_positive += pnl
    if total_positive <= 0 or not by_ticker:
        return None
    return round(max(by_ticker.values()) / total_positive, 4)


def _metrics_from_trades(
    result: dict[str, Any],
    trades: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    window: dict[str, str],
) -> dict[str, Any]:
    if not trades:
        return _core_metrics(result)
    curve = _event_equity_curve(
        trades,
        prices=prices,
        start=window["start"],
        end=window["end"],
    )
    return _combined_metrics(result, curve, trades)


def _gate_summary(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    delta = _aggregate_delta(before, after)
    by_window = OrderedDict((label, _gate4(before[label], after[label])) for label in WINDOWS)
    material = (
        (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
        or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
        or any(row["passes_sharpe"] for row in by_window.values())
        or any(row["passes_drawdown"] for row in by_window.values())
    )
    passed = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and material
    )
    return {
        "passed": bool(passed),
        "delta": delta,
        "by_window": by_window,
        "rule": (
            "EV first over the three canonical windows; require majority EV "
            "improvement, zero EV regressions, and one Gate 4 materiality trigger."
        ),
    }


def _build_window_payload(
    *,
    label: str,
    window: dict[str, str],
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
    event_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    state_candidates = _state_raw_candidates(
        label=label,
        window=window,
        result=result,
        prices=prices,
    )
    state_trades, state_skips = _select_state_trades(state_candidates)
    for trade in state_trades:
        trade["source"] = "state_surface_satellite"

    shared_trades, shared_skips = _select_shared_capacity([*event_trades, *state_trades])
    core = _core_metrics(result)
    event_metrics = _metrics_from_trades(result, event_trades, prices, window)
    state_metrics = _metrics_from_trades(result, state_trades, prices, window)
    shared_metrics = _metrics_from_trades(result, shared_trades, prices, window)

    return {
        "core_metrics": core,
        "event_metrics": event_metrics,
        "state_metrics": state_metrics,
        "shared_metrics": shared_metrics,
        "event_trades": event_trades,
        "state_trades": state_trades,
        "shared_trades": shared_trades,
        "state_skips": state_skips,
        "shared_skips": shared_skips,
        "summary": {
            "event_trade_count": len(event_trades),
            "event_pnl": round(sum(float(row.get("pnl") or 0.0) for row in event_trades), 2),
            "state_trade_count": len(state_trades),
            "state_pnl": round(sum(float(row.get("pnl") or 0.0) for row in state_trades), 2),
            "shared_trade_count": len(shared_trades),
            "shared_pnl": round(sum(float(row.get("pnl") or 0.0) for row in shared_trades), 2),
            "shared_source_summary": _source_summary(shared_trades),
            "shared_skip_reason_counts": dict(
                Counter(str(row.get("reason") or "unknown") for row in shared_skips)
            ),
            "state_selected_inside_shared": sum(
                1 for row in shared_trades if _source(row) == "state_surface_satellite"
            ),
        },
    }


def _trade_excerpt(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source": _source(trade),
            "ticker": trade.get("ticker"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "pnl": trade.get("pnl"),
            "net_return_pct": trade.get("net_return_pct"),
            "surface": trade.get("surface"),
            "rank": trade.get("rank"),
        }
        for trade in trades
    ]


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    event_trades_by_window, event_coverage, prices = _load_event_trades()

    per_window: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    event_metrics: dict[str, dict[str, Any]] = OrderedDict()
    state_metrics: dict[str, dict[str, Any]] = OrderedDict()
    shared_metrics: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        row = _build_window_payload(
            label=label,
            window=window,
            result=result,
            prices=prices,
            event_trades=event_trades_by_window[label],
        )
        per_window[label] = row
        core_metrics[label] = row["core_metrics"]
        event_metrics[label] = row["event_metrics"]
        state_metrics[label] = row["state_metrics"]
        shared_metrics[label] = row["shared_metrics"]

    core_gate = _gate_summary(core_metrics, shared_metrics)
    event_increment_gate = _gate_summary(event_metrics, shared_metrics)
    state_increment_gate = _gate_summary(state_metrics, shared_metrics)
    all_shared = [trade for row in per_window.values() for trade in row["shared_trades"]]
    positive_share = _single_ticker_positive_share(all_shared)

    passed = (
        event_increment_gate["passed"]
        and core_gate["passed"]
        and (positive_share is None or positive_share <= 0.50)
    )
    decision = "promising_replay_only" if passed else "rejected"
    if passed:
        decision_rationale = (
            "Promising replay-only: adding state-surface trades only when the existing "
            "event-bundle satellite budget has idle capacity improved the event-only "
            "baseline and the core baseline across the canonical windows. Live use still "
            "requires a shared default-off meta-satellite paper adapter and parity tests."
        )
        rejection_reason = None
    else:
        decision_rationale = (
            "Rejected: the shared-capacity satellite stack did not clear the pre-registered "
            "event-only incremental Gate 4 plus concentration controls. Keep event and "
            "state-surface sleeves in forward paper observation rather than combining them."
        )
        rejection_reason = decision_rationale

    compact_window = OrderedDict()
    for label, row in per_window.items():
        compact_window[label] = {
            "summary": row["summary"],
            "event_trades": _trade_excerpt(row["event_trades"]),
            "state_trades": _trade_excerpt(row["state_trades"]),
            "shared_trades": _trade_excerpt(row["shared_trades"]),
            "shared_skips_sample": row["shared_skips"][:20],
        }

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "satellite_shared_capacity_allocation_replay",
        "mechanism_family": "external_event_and_state_surface_satellite_allocation",
        "hypothesis": (
            "State-surface candidates can improve the strongest existing default-off event "
            "satellite by filling unused satellite capacity, without increasing the existing "
            "three-active-position satellite risk budget or displacing event trades."
        ),
        "alpha_hypothesis": {
            "category": "allocation/candidate_pool_combination",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking remains sample-limited, earnings/C re-enable was rejected, "
                "event source pruning and state-surface pruning were rejected, and both full "
                "event and full state-surface surfaces are the strongest replay-positive leads."
            ),
        },
        "historical_experiment_check": {
            "positive_priors": {
                "exp-20260504-049": "Full event bundle improved all three windows in replay.",
                "exp-20260507-016": "Full state-surface satellite improved all three windows in replay.",
                "exp-20260507-018": "State-surface was made default-off production-visible paper, not traded.",
            },
            "rejected_nearby": {
                "exp-20260507-012": "Event source pruning did not beat the full event bundle.",
                "exp-20260507-017": "State-surface balanced-surface pruning weakened the full surface.",
                "exp-20260507-014": "Core-platform runner exit failed.",
                "exp-20260507-011": "Earnings sleeve re-enable failed after snapshot repair.",
            },
            "why_not_simple_repeat": (
                "This does not retune either surface. It tests one portfolio allocation question: "
                "whether state-surface adds value inside the existing event satellite capacity."
            ),
            "mechanism_insight_conflict": (
                "No conflict: avoids LLM ranking, raw C sleeve, event source pruning, state-surface "
                "surface pruning, new noisy tickers, short-pressure/options overlays, and exit rewrites."
            ),
        },
        "parameters": {
            "single_causal_variable": "state-surface may fill idle slots inside the event satellite budget",
            "baseline_for_acceptance": "full_event_bundle_replay",
            "max_active_satellite_positions": MAX_ACTIVE_SATELLITE_POSITIONS,
            "source_priority": SOURCE_PRIORITY,
            "event_notional_usd": EVENT_NOTIONAL,
            "event_hold_days": EVENT_HOLD_DAYS,
            "state_surface_hold_days": STATE_HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "LLM prompt and replay",
                "news veto",
                "event source definitions",
                "state-surface scoring",
                "state-surface top-N",
                "state-surface hold days",
                "event hold days",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()
        },
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "before_metrics": event_metrics,
        "after_metrics": shared_metrics,
        "core_metrics": core_metrics,
        "state_only_metrics": state_metrics,
        "gate4": {
            "shared_vs_core": core_gate,
            "shared_vs_event_only": event_increment_gate,
            "shared_vs_state_only": state_increment_gate,
            "single_ticker_positive_share": positive_share,
            "acceptance_rule": (
                "Promotion lead requires shared-capacity stack to beat event-only and core "
                "baselines by Gate 4, with no more than 50% of positive PnL from one ticker."
            ),
        },
        "delta_metrics": {
            "shared_vs_core": core_gate["delta"],
            "shared_vs_event_only": event_increment_gate["delta"],
            "shared_vs_state_only": state_increment_gate["delta"],
        },
        "expected_value_score_delta": {
            "shared_vs_event_only": {
                label: event_increment_gate["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
            "shared_vs_core": {
                label: core_gate["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "satellite_allocation": compact_window,
        "event_coverage": event_coverage,
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
                "A shared default-off meta-satellite paper adapter consumed by run.py and a "
                "matching backtester adapter/parity test are required before any production use."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking data remains sample-limited; this tests a deterministic "
                "allocation alpha rather than weakening or expanding LLM duties."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "C/earnings raw enablement is newly rejected, LLM ranking lacks enough joined outcomes, "
            "event/state pruning just failed, runner exits failed, and broad universe expansion "
            "adds noise without governance evidence."
        ),
        "risk_of_change": (
            "The shared cap may still select correlated high-momentum names and can overstate "
            "replay alpha if treated as live capital before forward paper outcomes close."
        ),
        "next_action": (
            "If promising, build a default-off meta-satellite paper adapter before live promotion; "
            "if rejected, wait for forward outcomes from the separate event and state-surface paper sleeves."
        ),
        "related_files": [
            _repo_rel(__file__),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260507-019 Satellite Shared-Capacity Allocation",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Replay-only alpha search. Event-bundle trades keep priority; state-surface trades may use only idle slots inside the same max-3 active satellite budget.",
        "",
        "## Event Baseline To Shared Stack",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | State-in-shared | Shared trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    gate = payload["gate4"]["shared_vs_event_only"]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = gate["delta"]["by_window"][label]
        summary = payload["satellite_allocation"][label]["summary"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:,.2f} | {state_trades} | {shared_trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                state_trades=summary["state_selected_inside_shared"],
                shared_trades=summary["shared_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Shared Vs Core",
            "",
            "```json",
            json.dumps(payload["delta_metrics"]["shared_vs_core"], indent=2, sort_keys=True),
            "```",
            "",
            "## Shared Source Summary",
            "",
            "```json",
            json.dumps(
                {
                    label: payload["satellite_allocation"][label]["summary"]["shared_source_summary"]
                    for label in WINDOWS
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "Satellite shared-capacity allocation",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _markdown(payload))

    compact = {
        "experiment_id": EXP_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "core_metrics": payload["core_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
    }
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if EXPERIMENT_LOG.exists():
        existing = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        existing = [
            line
            for line in existing
            if f'"experiment_id":"{EXP_ID}"' not in line
            and f'"experiment_id": "{EXP_ID}"' not in line
        ]
    existing.append(json.dumps(_safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(existing) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXP_ID,
                    "decision": payload["decision"],
                    "shared_vs_event_only": payload["delta_metrics"]["shared_vs_event_only"],
                    "shared_vs_core": payload["delta_metrics"]["shared_vs_core"],
                    "single_ticker_positive_share": payload["gate4"]["single_ticker_positive_share"],
                    "state_selected_inside_shared": {
                        label: payload["satellite_allocation"][label]["summary"][
                            "state_selected_inside_shared"
                        ]
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
