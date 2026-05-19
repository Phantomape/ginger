"""exp-20260507-022 event pre-entry relative momentum allocation replay.

Alpha search. The default-off event bundle remains the strongest replay-positive
external alpha surface, but nearby source pruning, core-pressure guards, and
small SEC item-code semantics have already failed materiality. This experiment
changes one causal variable inside the frozen bundle: whether event trades with
positive PIT-safe 5-trading-day pre-entry return versus SPY deserve more event
notional than trades without that pre-entry confirmation.

No core entries, ranking, sizing, exits, universe membership, event sources,
event thresholds, holding periods, LLM/news behavior, or production orders are
changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments.exp_20260504_034_form4_satellite_overlay import (  # noqa: E402
    INITIAL_CAPITAL,
    _close_on_or_before,
    _combined_metrics,
    _core_metrics,
    _delta,
    _gate4,
    _trading_days,
)
from experiments.exp_20260504_049_default_off_event_overlay_bundle import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    ROUND_TRIP_COST_PCT,
    WINDOWS,
    _aggregate_delta,
    _load_core_result,
    _load_event_trades,
)


EXP_ID = "exp-20260507-022"
STEM = "event_preentry_relative_momentum"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

LOOKBACK_DAYS = 5

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "Current frozen event bundle; 1.0x notional for all event trades.",
                "confirmed_scalar": 1.0,
                "unconfirmed_scalar": 1.0,
                "threshold": None,
            },
        ),
        (
            "preentry_rs_positive_125_075",
            {
                "description": "Tilt notional toward event trades with positive 5d pre-entry return vs SPY.",
                "confirmed_scalar": 1.25,
                "unconfirmed_scalar": 0.75,
                "threshold": 0.0,
            },
        ),
        (
            "preentry_rs_positive_150_050",
            {
                "description": "Stronger version of the same positive 5d pre-entry relative-strength tilt.",
                "confirmed_scalar": 1.50,
                "unconfirmed_scalar": 0.50,
                "threshold": 0.0,
            },
        ),
        (
            "preentry_rs_2pct_150_050",
            {
                "description": "Require at least +2pp 5d excess return for the higher event notional.",
                "confirmed_scalar": 1.50,
                "unconfirmed_scalar": 0.50,
                "threshold": 0.02,
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
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("Date") or "")[:10]


def _row_close(row: dict[str, Any]) -> float | None:
    try:
        return float(row.get("close") or row.get("Close"))
    except (TypeError, ValueError):
        return None


def _idx_before(rows: list[dict[str, Any]], date_value: str) -> int | None:
    out: int | None = None
    for idx, row in enumerate(rows):
        row_date = _row_date(row)
        if row_date and row_date < date_value:
            out = idx
        if row_date >= date_value:
            break
    return out


def _preentry_excess_return(
    *,
    ticker: str,
    entry_date: str,
    prices: dict[str, list[dict[str, Any]]],
    lookback_days: int = LOOKBACK_DAYS,
) -> float | None:
    rows = prices.get(ticker) or []
    spy_rows = prices.get("SPY") or []
    ticker_idx = _idx_before(rows, entry_date)
    spy_idx = _idx_before(spy_rows, entry_date)
    if (
        ticker_idx is None
        or spy_idx is None
        or ticker_idx - lookback_days < 0
        or spy_idx - lookback_days < 0
    ):
        return None

    ticker_start = _row_close(rows[ticker_idx - lookback_days])
    ticker_end = _row_close(rows[ticker_idx])
    spy_start = _row_close(spy_rows[spy_idx - lookback_days])
    spy_end = _row_close(spy_rows[spy_idx])
    if not ticker_start or not ticker_end or not spy_start or not spy_end:
        return None
    return (ticker_end / ticker_start - 1.0) - (spy_end / spy_start - 1.0)


def _scalar_for_trade(trade: dict[str, Any], variant: dict[str, Any]) -> float:
    threshold = variant.get("threshold")
    if threshold is None:
        return float(variant["confirmed_scalar"])
    excess = trade.get("preentry_excess_return_5d")
    if excess is None:
        return 1.0
    if float(excess) >= float(threshold):
        return float(variant["confirmed_scalar"])
    return float(variant["unconfirmed_scalar"])


def _scaled_trade(trade: dict[str, Any], variant_name: str, variant: dict[str, Any]) -> dict[str, Any] | None:
    scalar = _scalar_for_trade(trade, variant)
    if scalar <= 0.0:
        return None
    base_notional = float(trade.get("notional") or EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    scaled = {
        **trade,
        "variant": variant_name,
        "preentry_relative_momentum_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
        "net_return_pct": trade.get("net_return_pct"),
    }
    return scaled


def _scaled_event_equity_curve(
    trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    from collections import defaultdict

    days = _trading_days(prices, start, end)
    entries_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exits_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        entries_by_day[str(trade["entry_date"])].append(trade)
        exits_by_day[str(trade["exit_date"])].append(trade)

    cash = INITIAL_CAPITAL
    active: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    for day in days:
        for trade in entries_by_day.get(day, []):
            cash -= float(trade.get("notional") or 0.0)
            active.append(trade)

        exiting = exits_by_day.get(day, [])
        for trade in exiting:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is None:
                continue
            notional = float(trade.get("notional") or 0.0)
            cash += float(trade["shares"]) * close - notional * ROUND_TRIP_COST_PCT
        if exiting:
            exit_keys = {
                (trade["ticker"], trade["entry_date"], trade["exit_date"], trade.get("variant"))
                for trade in exiting
            }
            active = [
                trade
                for trade in active
                if (trade["ticker"], trade["entry_date"], trade["exit_date"], trade.get("variant"))
                not in exit_keys
            ]

        market_value = 0.0
        for trade in active:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is not None:
                market_value += float(trade["shares"]) * close
        equity = cash + market_value
        curve.append(
            {
                "date": day,
                "event_equity": round(equity, 2),
                "event_pnl": round(equity - INITIAL_CAPITAL, 2),
                "active_event_positions": len(active),
            }
        )
    return curve


def _enrich_event_trades(
    by_window: dict[str, list[dict[str, Any]]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    enriched: dict[str, list[dict[str, Any]]] = OrderedDict()
    for label, trades in by_window.items():
        rows: list[dict[str, Any]] = []
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            entry_date = str(trade.get("entry_date") or "")[:10]
            excess = _preentry_excess_return(
                ticker=ticker,
                entry_date=entry_date,
                prices=prices,
            )
            rows.append(
                {
                    **trade,
                    "preentry_lookback_days": LOOKBACK_DAYS,
                    "preentry_excess_return_5d": round(excess, 6) if excess is not None else None,
                    "preentry_feature_available": excess is not None,
                }
            )
        enriched[label] = rows
    return enriched


def _trade_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    by_source: dict[str, dict[str, Any]] = {}
    by_bucket: dict[str, dict[str, Any]] = {}
    for trade in trades:
        source = str(trade.get("source") or "unknown")
        bucket = "missing"
        excess = trade.get("preentry_excess_return_5d")
        if excess is not None:
            bucket = "confirmed" if float(excess) >= 0.0 else "unconfirmed"
        for key, target in ((source, by_source), (bucket, by_bucket)):
            row = target.setdefault(
                key,
                {"trade_count": 0, "wins": 0, "total_pnl": 0.0, "total_notional": 0.0},
            )
            pnl = float(trade.get("pnl") or 0.0)
            row["trade_count"] += 1
            row["wins"] += int(pnl > 0)
            row["total_pnl"] += pnl
            row["total_notional"] += float(trade.get("notional") or EVENT_NOTIONAL)
    for target in (by_source, by_bucket):
        for row in target.values():
            count = int(row["trade_count"])
            row["win_rate"] = round(row["wins"] / count, 4) if count else None
            row["total_pnl"] = round(float(row["total_pnl"]), 2)
            row["total_notional"] = round(float(row["total_notional"]), 2)
    return {
        "trade_count": len(trades),
        "total_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
        "total_notional": round(sum(float(trade.get("notional") or EVENT_NOTIONAL) for trade in trades), 2),
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "by_source": by_source,
        "by_preentry_bucket": by_bucket,
        "trades": [
            {
                "source": trade.get("source"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "notional": trade.get("notional"),
                "scalar": trade.get("preentry_relative_momentum_scalar"),
                "preentry_excess_return_5d": trade.get("preentry_excess_return_5d"),
            }
            for trade in trades
        ],
    }


def _coverage(enriched: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [trade for trades in enriched.values() for trade in trades]
    available = [row for row in rows if row.get("preentry_feature_available")]
    bucket_counts = Counter(
        "confirmed" if float(row.get("preentry_excess_return_5d") or 0.0) >= 0.0 else "unconfirmed"
        for row in available
    )
    return {
        "lookback_days": LOOKBACK_DAYS,
        "event_trade_count": len(rows),
        "feature_available_count": len(available),
        "feature_available_fraction": round(len(available) / len(rows), 4) if rows else None,
        "preentry_bucket_counts": dict(bucket_counts),
        "missing_feature_count": len(rows) - len(available),
    }


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
            "EV first over the three canonical backtesting.md windows; require "
            "majority-window EV improvement, zero EV regression, and one Gate 4 materiality trigger."
        ),
    }


def _best_variant_name(gates: dict[str, dict[str, Any]]) -> str:
    names = [name for name in VARIANTS if name != "full_bundle"]
    return max(
        names,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
        ),
    )


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = _load_event_trades()
    event_trades = _enrich_event_trades(raw_event_trades, prices)

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        core_metrics[label] = _core_metrics(result)

        for name, variant in VARIANTS.items():
            scaled = [
                row
                for row in (
                    _scaled_trade(trade, name, variant)
                    for trade in event_trades[label]
                )
                if row is not None
            ]
            curve = _scaled_event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = _combined_metrics(result, curve, scaled)
            variant_events[name][label] = _trade_summary(scaled)

    full_metrics = variant_metrics["full_bundle"]
    core_gates = OrderedDict(
        (name, _gate_summary(core_metrics, variant_metrics[name]))
        for name in VARIANTS
    )
    full_gates = OrderedDict(
        (name, _gate_summary(full_metrics, variant_metrics[name]))
        for name in VARIANTS
        if name != "full_bundle"
    )
    best_variant = _best_variant_name(full_gates)
    best_gate = full_gates[best_variant]
    accepted = bool(best_gate["passed"] and core_gates[best_variant]["passed"])
    decision = "promising_replay_only_preentry_momentum_tilt" if accepted else "rejected"

    if accepted:
        rationale = (
            f"Promising replay-only: {best_variant} beat the full frozen event bundle "
            "and core baseline under the three-window Gate 4 rule. Production use "
            "would still require a shared default-off event adapter and forward paper outcomes."
        )
        rejection_reason = None
        next_action = (
            "Move only the accepted pre-entry momentum tilt into a shared default-off "
            "paper adapter, then collect forward closed outcomes before live promotion."
        )
    else:
        rationale = (
            f"Rejected: the best pre-entry momentum tilt ({best_variant}) did not beat "
            "the full frozen event bundle with enough stable EV improvement and materiality."
        )
        rejection_reason = rationale
        next_action = (
            "Keep the full event bundle unchanged; do not retry nearby 5d pre-entry "
            "relative-momentum scalars without forward event replacement-value evidence."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_preentry_relative_momentum_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "hypothesis": (
            "Default-off event-bundle trades with positive PIT-safe 5-trading-day "
            "pre-entry return versus SPY may deserve more event notional than "
            "unconfirmed trades because the market is already rewarding the event setup."
        ),
        "alpha_hypothesis": {
            "category": "allocation/event-quality",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking is still data-limited, earnings/C enablement failed, "
                "event source pruning and core-pressure guards just failed, and the full "
                "event bundle remains the strongest replay-positive alpha surface."
            ),
        },
        "single_causal_variable": "5-trading-day pre-entry return versus SPY used only to tilt event notional",
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": "full_bundle",
            "lookback_days": LOOKBACK_DAYS,
            "base_event_notional_usd": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "event source definitions",
                "event source thresholds",
                "event holding period",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()
        },
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "historical_experiment_check": {
            "similar_positive_priors": {
                "exp-20260504-049": "Full frozen default-off event bundle improved all three canonical windows.",
                "exp-20260507-016": "State surface satellite is separately promising but should not be combined with event bundle until forward evidence closes.",
            },
            "nearby_rejected": {
                "exp-20260505-031": "One-day event follow-through delay regressed all windows.",
                "exp-20260507-012": "Event source pruning did not beat the full bundle.",
                "exp-20260507-019": "Event+state shared-capacity combination failed versus event-only.",
                "exp-20260507-020": "FD/Other item-code semantics was positive but immaterial.",
                "exp-20260507-021": "Core-pressure event guard was positive only immaterial versus full bundle.",
            },
            "why_not_simple_repeat": (
                "This does not prune event sources, change event timing, alter source priority, "
                "combine state surfaces, or tune SEC text. It tests one PIT-safe price-confirmation "
                "allocation variable across all frozen event sources."
            ),
            "mechanism_insight_conflict": (
                "No conflict with recent do-not-repeat zones: no LLM ranking, no raw earnings/C, "
                "no broad universe growth, no source subset permutation, no core slot/capacity change."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            "full_event_bundle": full_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_core": core_gates,
            "variant_vs_full_bundle": full_gates,
        },
        "expected_value_score_delta": {
            "best_variant_vs_full_bundle": {
                label: best_gate["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
            "best_variant_vs_core": {
                label: core_gates[best_variant]["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "best_variant": best_variant,
        "event_selection": variant_events,
        "coverage": {
            "source_coverage": source_coverage,
            "preentry_feature": _coverage(event_trades),
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
                "A shared default-off event paper/live adapter must compute the same PIT-safe "
                "pre-entry relative momentum feature in run.py and backtester before any capital impact."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking outcome joins remain sparse; this tests a deterministic "
                "event-allocation alpha lead instead of weakening or expanding LLM responsibilities."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "C/earnings re-enable, LLM ranking, event source pruning, FD/Other item-code tweaks, "
            "state-surface pruning/combination, broad universe expansion, and runner exits all have "
            "recent blocker or rejection evidence."
        ),
        "risk_of_change": (
            "A pre-entry momentum tilt can underweight profitable mean-reversion event trades and "
            "overweight already-extended moves; forward paper evidence is required before promotion."
        ),
        "next_action": next_action,
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-022 Event Pre-Entry Relative Momentum",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Replay-only alpha search. Tests whether the frozen event bundle should tilt notional toward event trades with stronger PIT-safe pre-entry relative momentum.",
        "",
        "## Best Variant Vs Full Bundle",
        "",
        "| Window | Full EV | Variant EV | Delta EV | Full PnL | Variant PnL | Delta PnL | Event trades | Event PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_full_bundle"][best]
    for label in WINDOWS:
        before = payload["before_metrics"]["full_event_bundle"][label]
        after = payload["after_metrics"][best][label]
        delta = gate["delta"]["by_window"][label]
        selected = payload["event_selection"][best][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${epnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=selected["trade_count"],
                epnl=selected["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Variant Summary",
            "",
            "| Variant | EV Sum Vs Full | PnL Delta Vs Full | Windows EV Improved | Windows EV Regressed | Passed |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for name, row in payload["delta_metrics"]["variant_vs_full_bundle"].items():
        delta = row["delta"]
        lines.append(
            "| {name} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {passed} |".format(
                name=name,
                ev=delta["aggregate_ev_delta"],
                pnl=delta["aggregate_pnl_delta"],
                wi=delta["windows_ev_improved"],
                wr=delta["windows_ev_regressed"],
                passed=row["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            "```json",
            json.dumps(payload["coverage"]["preentry_feature"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "No production universe, ranking, sizing, exits, LLM, news, or order path changed.",
            "",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines))


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "Event pre-entry relative momentum",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_report(payload)

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
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "best_variant": payload["best_variant"],
        "coverage": payload["coverage"]["preentry_feature"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
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


def main() -> int:
    payload = build_payload()
    persist(payload)
    best = payload["best_variant"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXP_ID,
                    "decision": payload["decision"],
                    "best_variant": best,
                    "best_variant_vs_full_bundle": payload["delta_metrics"]["variant_vs_full_bundle"][best]["delta"],
                    "best_variant_vs_core": payload["delta_metrics"]["variant_vs_core"][best]["delta"],
                    "coverage": payload["coverage"]["preentry_feature"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
