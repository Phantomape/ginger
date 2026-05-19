"""exp-20260507-024 event price-structure allocation replay.

Alpha search. The frozen default-off event bundle is still the strongest
replay-positive non-core surface, while recent source pruning, core-pressure,
pre-entry relative-momentum, and item-code variants did not clear the marginal
gate. This experiment changes one causal variable inside the frozen bundle:
whether event trades deserve more notional when the ticker was already in a
PIT-safe medium-term uptrend before entry.

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

from experiments.exp_20260504_049_default_off_event_overlay_bundle import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
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


EXP_ID = "exp-20260507-024"
STEM = "event_price_structure"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "full_bundle",
            {
                "description": "Current frozen event bundle; 1.0x notional for all event trades.",
                "confirmed_scalar": 1.0,
                "unconfirmed_scalar": 1.0,
            },
        ),
        (
            "price_structure_125_075",
            {
                "description": "Tilt notional toward events whose pre-entry close is above SMA50 and SMA20 is above SMA50.",
                "confirmed_scalar": 1.25,
                "unconfirmed_scalar": 0.75,
            },
        ),
        (
            "price_structure_150_050",
            {
                "description": "Stronger version of the same pre-entry price-structure tilt.",
                "confirmed_scalar": 1.50,
                "unconfirmed_scalar": 0.50,
            },
        ),
        (
            "price_structure_only",
            {
                "description": "Trade only event rows with confirmed pre-entry price structure.",
                "confirmed_scalar": 1.0,
                "unconfirmed_scalar": 0.0,
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
        value = float(row.get("close") or row.get("Close"))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _idx_before(rows: list[dict[str, Any]], date_value: str) -> int | None:
    out: int | None = None
    for idx, row in enumerate(rows):
        row_date = _row_date(row)
        if row_date and row_date < date_value:
            out = idx
        if row_date >= date_value:
            break
    return out


def _preentry_structure(
    *,
    ticker: str,
    entry_date: str,
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows = prices.get(ticker) or []
    idx = _idx_before(rows, entry_date)
    if idx is None or idx < 49:
        return {
            "price_structure_available": False,
            "price_structure_confirmed": None,
            "price_structure_reason": "insufficient_50d_history",
        }

    closes: list[float] = []
    for row in rows[: idx + 1]:
        close = _row_close(row)
        if close is not None:
            closes.append(close)
    if len(closes) < 50:
        return {
            "price_structure_available": False,
            "price_structure_confirmed": None,
            "price_structure_reason": "insufficient_valid_closes",
        }

    last_close = closes[-1]
    sma20 = sum(closes[-20:]) / 20.0
    sma50 = sum(closes[-50:]) / 50.0
    confirmed = last_close > sma50 and sma20 > sma50
    return {
        "price_structure_available": True,
        "price_structure_confirmed": bool(confirmed),
        "price_structure_reason": "confirmed" if confirmed else "not_confirmed",
        "preentry_last_close": round(last_close, 6),
        "preentry_sma20": round(sma20, 6),
        "preentry_sma50": round(sma50, 6),
        "preentry_close_vs_sma50_pct": round(last_close / sma50 - 1.0, 6) if sma50 else None,
        "preentry_sma20_vs_sma50_pct": round(sma20 / sma50 - 1.0, 6) if sma50 else None,
    }


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
            rows.append(
                {
                    **trade,
                    **_preentry_structure(ticker=ticker, entry_date=entry_date, prices=prices),
                }
            )
        enriched[label] = rows
    return enriched


def _scalar_for_trade(trade: dict[str, Any], variant: dict[str, Any]) -> float:
    if not trade.get("price_structure_available"):
        return 1.0
    if bool(trade.get("price_structure_confirmed")):
        return float(variant["confirmed_scalar"])
    return float(variant["unconfirmed_scalar"])


def _scaled_trade(trade: dict[str, Any], variant_name: str, variant: dict[str, Any]) -> dict[str, Any] | None:
    scalar = _scalar_for_trade(trade, variant)
    if scalar <= 0.0:
        return None
    base_notional = float(trade.get("notional") or EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "price_structure_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
        "net_return_pct": trade.get("net_return_pct"),
    }


def _trade_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    by_source: dict[str, dict[str, Any]] = {}
    by_bucket: dict[str, dict[str, Any]] = {}
    for trade in trades:
        source = str(trade.get("source") or "unknown")
        if not trade.get("price_structure_available"):
            bucket = "missing"
        elif trade.get("price_structure_confirmed"):
            bucket = "confirmed"
        else:
            bucket = "unconfirmed"
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
        "by_price_structure_bucket": by_bucket,
        "trades": [
            {
                "source": trade.get("source"),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "notional": trade.get("notional"),
                "scalar": trade.get("price_structure_scalar"),
                "price_structure_confirmed": trade.get("price_structure_confirmed"),
                "price_structure_available": trade.get("price_structure_available"),
                "preentry_close_vs_sma50_pct": trade.get("preentry_close_vs_sma50_pct"),
                "preentry_sma20_vs_sma50_pct": trade.get("preentry_sma20_vs_sma50_pct"),
            }
            for trade in trades
        ],
    }


def _coverage(enriched: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [trade for trades in enriched.values() for trade in trades]
    available = [row for row in rows if row.get("price_structure_available")]
    bucket_counts = Counter(
        "confirmed" if row.get("price_structure_confirmed") else "unconfirmed"
        for row in available
    )
    return {
        "event_trade_count": len(rows),
        "feature_available_count": len(available),
        "feature_available_fraction": round(len(available) / len(rows), 4) if rows else None,
        "bucket_counts": dict(bucket_counts),
        "missing_feature_count": len(rows) - len(available),
        "rule": "pre-entry close > SMA50 and SMA20 > SMA50, using only closes before event entry date",
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
            curve = _event_equity_curve(
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
    decision = "promising_replay_only_price_structure_tilt" if accepted else "rejected"

    if accepted:
        rationale = (
            f"Promising replay-only: {best_variant} beat the full frozen event bundle "
            "and core baseline under the three-window Gate 4 rule. Production use "
            "would still require shared paper/live adapter parity and forward outcomes."
        )
        rejection_reason = None
        next_action = (
            "Move only this price-structure feature into a shared default-off event "
            "paper adapter, then collect forward closed outcomes before live promotion."
        )
    else:
        rationale = (
            f"Rejected: the best price-structure variant ({best_variant}) did not beat "
            "the full frozen event bundle with enough stable EV improvement and materiality."
        )
        rejection_reason = rationale
        next_action = (
            "Keep the full event bundle unchanged; do not retry nearby SMA20/SMA50 "
            "event-structure tilts without forward replacement-value evidence or a "
            "materially different event-quality discriminator."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_price_structure_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "hypothesis": (
            "Default-off event-bundle trades whose ticker is already above SMA50 "
            "with SMA20 above SMA50 before entry may have better continuation quality "
            "than event trades occurring under weaker medium-term price structure."
        ),
        "alpha_hypothesis": {
            "category": "allocation/event-quality",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking is still data-limited, earnings/C enablement failed, "
                "event source pruning, core-pressure guards, pre-entry relative momentum, "
                "and state-surface collision ranking have recent rejection evidence."
            ),
        },
        "single_causal_variable": "PIT-safe pre-entry SMA20/SMA50 price structure used only to tilt event notional",
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": "full_bundle",
            "base_event_notional_usd": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "feature_rule": "last close before entry > SMA50 and SMA20 > SMA50",
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
                "exp-20260507-022": "5d pre-entry relative-strength tilt was positive only immaterial versus full bundle.",
            },
            "why_not_simple_repeat": (
                "This does not prune sources, change event timing, alter source priority, "
                "combine state surfaces, or retune short-horizon relative momentum. It tests "
                "one medium-term price-structure quality variable across all frozen event sources."
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
            "price_structure_feature": _coverage(event_trades),
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
                "price-structure feature in run.py and backtester before any capital impact."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "LLM soft-ranking outcome joins remain sparse; this deterministic alpha test "
                "does not weaken or expand LLM responsibilities."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "C/earnings re-enable, LLM ranking, event source pruning, FD/Other item-code tweaks, "
            "state-surface pruning/combination/collision ranking, broad universe expansion, and "
            "runner exits all have recent blocker or rejection evidence."
        ),
        "risk_of_change": (
            "A price-structure tilt can underweight profitable reversal events and overweight "
            "extended moves; forward paper evidence is required before promotion."
        ),
        "next_action": next_action,
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return payload


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-024 Event Price Structure",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Replay-only alpha search. Tests whether the frozen event bundle should tilt notional toward event trades with confirmed PIT-safe SMA20/SMA50 price structure before entry.",
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
            json.dumps(payload["coverage"]["price_structure_feature"], indent=2, sort_keys=True),
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
            "title": "Event price-structure tilt",
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
        "coverage": payload["coverage"]["price_structure_feature"],
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
                    "coverage": payload["coverage"]["price_structure_feature"],
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
