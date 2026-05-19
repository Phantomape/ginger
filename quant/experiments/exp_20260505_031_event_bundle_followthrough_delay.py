"""exp-20260505-031 event bundle follow-through delayed-entry replay.

Alpha search, not bug repair. The accepted core stack is left untouched. This
replays the frozen default-off event overlay bundle from exp-20260504-049 and
tests one entry-quality discriminator:

    keep an event only if the original event entry day closes positive and
    outperforms SPY, then enter on the next trading day's open.

The intent is to check whether event candidates need immediate price
confirmation before satellite capital is allocated. The experiment is replay
only and must not change production orders unless it passes the three-window
standard and later gets a shared policy adapter.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
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
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_equity_curve,
    _gate4,
)
from experiments.exp_20260504_049_default_off_event_overlay_bundle import (  # noqa: E402
    HOLD_DAYS,
    WINDOWS,
    _aggregate_delta,
    _load_event_trades,
)


EXP_ID = "exp-20260505-031"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "event_bundle_followthrough_delay.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / "exp-20260505-031_event_bundle_followthrough_delay.md"
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _index_by_date(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if str(row.get("date") or "") == date_value:
            return idx
    return None


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


def _close_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx <= 0 or idx >= len(rows):
        return None
    previous_close = _float_or_none(rows[idx - 1].get("close"))
    close = _float_or_none(rows[idx].get("close"))
    if previous_close is None or close is None or previous_close <= 0:
        return None
    return close / previous_close - 1.0


def _delayed_followthrough_trade(
    trade: dict[str, Any],
    *,
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = str(trade.get("entry_date") or "")[:10]
    exit_date = str(trade.get("exit_date") or "")[:10]
    rows = prices.get(ticker) or []
    spy_rows = prices.get("SPY") or []
    entry_idx = _index_by_date(rows, entry_date)
    exit_idx = _index_by_date(rows, exit_date)
    spy_idx = _index_by_date(spy_rows, entry_date)
    if entry_idx is None or exit_idx is None or spy_idx is None:
        return None, {
            "ticker": ticker,
            "entry_date": entry_date,
            "source": trade.get("source"),
            "reason": "missing_original_or_spy_day",
        }

    ticker_return = _close_return(rows, entry_idx)
    spy_return = _close_return(spy_rows, spy_idx)
    if ticker_return is None or spy_return is None:
        return None, {
            "ticker": ticker,
            "entry_date": entry_date,
            "source": trade.get("source"),
            "reason": "missing_followthrough_close",
        }

    excess_return = ticker_return - spy_return
    if ticker_return <= 0.0 or excess_return <= 0.0:
        return None, {
            "ticker": ticker,
            "entry_date": entry_date,
            "source": trade.get("source"),
            "reason": "failed_positive_spy_relative_followthrough",
            "ticker_day_return": round(ticker_return, 6),
            "spy_day_return": round(spy_return, 6),
            "excess_day_return": round(excess_return, 6),
            "original_pnl": trade.get("pnl"),
        }

    delayed_entry_idx = entry_idx + 1
    hold_span = max(exit_idx - entry_idx, 1)
    delayed_exit_idx = delayed_entry_idx + hold_span
    if delayed_exit_idx >= len(rows):
        return None, {
            "ticker": ticker,
            "entry_date": entry_date,
            "source": trade.get("source"),
            "reason": "missing_delayed_exit_price",
        }

    delayed_entry = rows[delayed_entry_idx]
    delayed_exit = rows[delayed_exit_idx]
    entry_open = _float_or_none(delayed_entry.get("open"))
    exit_close = _float_or_none(delayed_exit.get("close"))
    if entry_open is None or exit_close is None or entry_open <= 0:
        return None, {
            "ticker": ticker,
            "entry_date": entry_date,
            "source": trade.get("source"),
            "reason": "missing_delayed_open_or_close",
        }

    shares = EVENT_NOTIONAL / entry_open
    pnl = shares * exit_close - EVENT_NOTIONAL - EVENT_NOTIONAL * ROUND_TRIP_COST_PCT
    delayed = {
        **trade,
        "entry_date": str(delayed_entry["date"])[:10],
        "exit_date": str(delayed_exit["date"])[:10],
        "entry_open": round(entry_open, 6),
        "exit_close": round(exit_close, 6),
        "shares": shares,
        "notional": EVENT_NOTIONAL,
        "pnl": round(pnl, 2),
        "net_return_pct": round(pnl / EVENT_NOTIONAL, 6),
        "original_entry_date": entry_date,
        "original_exit_date": exit_date,
        "original_pnl": trade.get("pnl"),
        "followthrough_rule": "positive_absolute_and_spy_relative_day1",
        "ticker_day_return": round(ticker_return, 6),
        "spy_day_return": round(spy_return, 6),
        "excess_day_return": round(excess_return, 6),
    }
    return delayed, {
        "ticker": ticker,
        "entry_date": entry_date,
        "source": trade.get("source"),
        "reason": "selected",
        "ticker_day_return": round(ticker_return, 6),
        "spy_day_return": round(spy_return, 6),
        "excess_day_return": round(excess_return, 6),
        "original_pnl": trade.get("pnl"),
        "delayed_pnl": round(pnl, 2),
    }


def _build_variant_trades(
    event_trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for trade in event_trades:
        delayed, row = _delayed_followthrough_trade(trade, prices=prices)
        audit.append(row)
        if delayed is not None:
            selected.append(delayed)
    selected.sort(
        key=lambda row: (
            str(row.get("entry_date") or ""),
            str(row.get("source") or ""),
            str(row.get("ticker") or ""),
        )
    )
    return selected, audit


def _event_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0.0)
    pnl = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
    by_source: dict[str, dict[str, Any]] = OrderedDict()
    for trade in trades:
        source = str(trade.get("source") or "unknown")
        row = by_source.setdefault(source, {"trade_count": 0, "wins": 0, "pnl": 0.0})
        row["trade_count"] += 1
        row["wins"] += int(float(trade.get("pnl") or 0.0) > 0.0)
        row["pnl"] += float(trade.get("pnl") or 0.0)
    for row in by_source.values():
        count = int(row["trade_count"] or 0)
        row["pnl"] = round(float(row["pnl"] or 0.0), 2)
        row["win_rate"] = round(float(row["wins"]) / count, 4) if count else None
    return {
        "trade_count": len(trades),
        "winning_trades": wins,
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "pnl": pnl,
        "by_source": by_source,
    }


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260505-031 Event Bundle Follow-Through Delay",
        "",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        f"- timestamp: `{payload['timestamp']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Bundle EV | Variant EV | Delta EV | Bundle PnL | Variant PnL | Delta PnL | Bundle events | Variant events |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        base_events = payload["event_baseline"][label]
        variant_events = payload["event_variant"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:,.2f} | {bt} / ${bepnl:,.2f} | {at} / ${aepnl:,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bt=base_events["trade_count"],
                bepnl=base_events["pnl"],
                at=variant_events["trade_count"],
                aepnl=variant_events["pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Do Not Repeat",
            "",
            payload["next_action"],
            "",
        ]
    )
    _write_text(AUDIT_MD, "\n".join(lines) + "\n")


def main() -> int:
    event_trades_by_window, coverage, prices = _load_event_trades()
    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    per_window: dict[str, dict[str, Any]] = OrderedDict()
    event_baseline: dict[str, dict[str, Any]] = OrderedDict()
    event_variant: dict[str, dict[str, Any]] = OrderedDict()
    gate4_by_window: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        core_result = _load_core_result(window)
        baseline_trades = event_trades_by_window[label]
        variant_trades, audit = _build_variant_trades(baseline_trades, prices=prices)
        baseline_curve = _event_equity_curve(
            baseline_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        variant_curve = _event_equity_curve(
            variant_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _combined_metrics(core_result, baseline_curve, baseline_trades)
        after_metrics[label] = _combined_metrics(core_result, variant_curve, variant_trades)
        gate4_by_window[label] = _gate4(before_metrics[label], after_metrics[label])
        event_baseline[label] = _event_summary(baseline_trades)
        event_variant[label] = _event_summary(variant_trades)
        per_window[label] = {
            "start": window["start"],
            "end": window["end"],
            "state_note": window["state_note"],
            "core_metrics": _core_metrics(core_result),
            "baseline_event_trades": [
                {
                    "source": trade.get("source"),
                    "ticker": trade.get("ticker"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl": trade.get("pnl"),
                }
                for trade in baseline_trades
            ],
            "variant_event_trades": [
                {
                    "source": trade.get("source"),
                    "ticker": trade.get("ticker"),
                    "original_entry_date": trade.get("original_entry_date"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "original_pnl": trade.get("original_pnl"),
                    "pnl": trade.get("pnl"),
                    "ticker_day_return": trade.get("ticker_day_return"),
                    "spy_day_return": trade.get("spy_day_return"),
                    "excess_day_return": trade.get("excess_day_return"),
                }
                for trade in variant_trades
            ],
            "followthrough_audit": audit,
        }

    delta = _aggregate_delta(before_metrics, after_metrics)
    ev_improved = int(delta["windows_ev_improved"])
    ev_regressed = int(delta["windows_ev_regressed"])
    pnl_improved = int(delta["windows_pnl_improved"])
    pnl_regressed = int(delta["windows_pnl_regressed"])
    passed = (
        ev_improved >= 2
        and ev_regressed == 0
        and (
            (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
            or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
            or any(row["passes_sharpe"] for row in gate4_by_window.values())
            or any(row["passes_drawdown"] for row in gate4_by_window.values())
        )
    )
    decision = "accepted_replay_only_candidate" if passed else "rejected"
    if passed:
        rationale = (
            "Accepted only as a replay candidate: the delayed follow-through entry improved the majority of windows "
            "without EV regression. Production would still require a shared event policy adapter before any live order path."
        )
        next_action = (
            "Do not place live trades from this script. Next step would be a shared replay/production event-entry policy adapter."
        )
    else:
        rationale = (
            "Rejected: adding one-day positive and SPY-relative follow-through before event-bundle entry regressed EV or PnL "
            "in all three canonical windows. The rule filtered some winning event trades and did not improve the older thin tape either."
        )
        next_action = (
            "Do not retry nearby one-day follow-through or delayed-entry gates on the same frozen event bundle without new forward outcomes "
            "or a materially richer semantic event-quality discriminator."
        )

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_bundle_entry_quality_discriminator",
        "mechanism_family": "external_event_satellite_overlay",
        "hypothesis": (
            "Frozen event-bundle candidates that first close positive and outperform SPY on the original event entry day "
            "may be cleaner satellite entries if entered on the next trading day's open."
        ),
        "alpha_hypothesis": {
            "category": "entry",
            "entry_exit_ranking_or_allocation": "event-sleeve delayed entry",
            "why_this_now": (
                "LLM soft-ranking, options/borrow, Form 4 current snapshot, broad universe expansion, and simple core ranking surfaces "
                "are data-limited or recently rejected. The event bundle remains the strongest alpha surface, but needs a non-threshold "
                "quality discriminator before any promotion discussion."
            ),
        },
        "single_causal_variable": (
            "Require original event entry day positive absolute and SPY-relative follow-through, then enter next trading day."
        ),
        "parameters": {
            "followthrough_threshold": "ticker_close_to_close_return_day1 > 0 and ticker_return_day1 > SPY_return_day1",
            "entry_timing": "next_trading_day_open_after_original_event_entry_day",
            "hold_span": "preserve original event trade date span",
            "event_notional_usd": EVENT_NOTIONAL,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "hold_days_reference": HOLD_DAYS,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "LLM prompt and replay",
                "news veto",
                "event source thresholds",
                "event source caps",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "similar_experiments": {
                "exp-20260504-049": "Default-off event overlay bundle was the strongest replay-only surface.",
                "exp-20260505-004": "FD-source event bundle variant rejected; source retunes are not enough.",
                "exp-20260505-025": "Event bundle direction remained promising but forward evidence is required.",
                "exp-20260505-029": "Post-news continuation shadow was blocked by insufficient aligned samples.",
                "exp-20260505-030": "SEC leadership item-code semantic discriminator rejected.",
            },
            "why_not_simple_repeat": (
                "This is not a source, threshold, notional, cap, or holding-period sweep. It tests a price-confirmed delayed-entry mechanism."
            ),
            "mechanism_insight_guardrails": [
                "No same-sample event source threshold retune.",
                "No event notional/cap promotion.",
                "No LLM soft-ranking because aligned replay samples remain insufficient.",
                "No broad noisy universe expansion.",
            ],
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "gate4": {
            "by_window": gate4_by_window,
            "aggregate": {
                "windows_ev_improved": ev_improved,
                "windows_ev_regressed": ev_regressed,
                "windows_pnl_improved": pnl_improved,
                "windows_pnl_regressed": pnl_regressed,
            },
        },
        "event_baseline": event_baseline,
        "event_variant": event_variant,
        "per_window": per_window,
        "coverage": coverage,
        "production_impact": {
            "production_impact": "replay_only",
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_backtest_consistency": (
                "No live or backtest production policy changed. Positive promotion would require shared policy before implementation."
            ),
        },
        "llm_attribution": {
            "llm_changed": False,
            "llm_replay_coverage_used": False,
            "note": "This run does not weaken or bypass LLM. LLM soft-ranking remained data-limited, so the alpha search pivoted to event entry quality.",
        },
        "decision_rationale": rationale,
        "next_action": next_action,
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "Event bundle follow-through delay",
            "status": decision,
            "lane": "alpha_search",
            "created_at": timestamp,
            "completed_at": timestamp,
            "result": {
                "decision": decision,
                "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
                "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
                "audit_report": str(AUDIT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
                "aggregate_delta": delta,
                "next_action": next_action,
            },
        },
    )
    _write_report(payload)
    print(json.dumps(_safe({
        "experiment_id": EXP_ID,
        "decision": decision,
        "aggregate_delta": delta,
        "event_baseline": event_baseline,
        "event_variant": event_variant,
    }), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
