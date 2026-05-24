"""exp-20260524-027: broad-market candidate-breadth gate.

Alpha search for the default-off broad-market leadership paper sleeve.

The accepted broad-market price-floor pool, rank profile, low-extension,
high-volatility, and trend-persistence scalars stay fixed. This run changes
one causal variable: a production-computable decision-day candidate breadth
gate. If too few all-market leadership candidates pass the fixed profile on a
decision day, the default-off paper sleeve skips new entries for that day.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260524-027"
EXPERIMENT_SLUG = "broad_market_candidate_breadth_gate"
BASELINE_EXPERIMENT_ID = "exp-20260520-004"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"
REFERENCE_EXPERIMENT_ID = "exp-20260524-024"
MECHANISM_FAMILY = "broad_market_participation_quality"
TRIAL_FAMILY = "broad_market_candidate_breadth_selection_gate"
CHANGED_VARIABLE = "broad_market_day_candidate_count_breadth_gate"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260519-037",
    "exp-20260520-002",
    "exp-20260520-003",
    "exp-20260520-004",
    "exp-20260523-006",
    "exp-20260524-023",
    "exp-20260524-024",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
import exp_20260524_023_broad_market_correlation_crowding as corr  # noqa: E402
from broad_market_paper_sleeve import (  # noqa: E402
    backtest_trade_from_feature,
    build_broad_market_feature,
    candidate_passes_profile,
)


WINDOWS = p35.WINDOWS
PROFILE_CONFIG = dict(corr.PROFILE_CONFIG)
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / BASELINE_EXPERIMENT_ID
    / "broad_market_trend_persistence_notional.json"
)
CONTROL_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / CONTROL_EXPERIMENT_ID
    / "broad_market_shared_paper_adapter.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BREADTH_GATE_SWEEP: OrderedDict[str, dict[str, int | None]] = OrderedDict(
    [
        ("baseline_no_candidate_breadth_gate", {"min_day_candidate_count": None}),
        ("candidate_count_gte_10", {"min_day_candidate_count": 10}),
        ("candidate_count_gte_15", {"min_day_candidate_count": 15}),
        ("candidate_count_gte_20", {"min_day_candidate_count": 20}),
        ("candidate_count_gte_25", {"min_day_candidate_count": 25}),
        ("candidate_count_gte_30", {"min_day_candidate_count": 30}),
        ("candidate_count_gte_40", {"min_day_candidate_count": 40}),
    ]
)

MIN_CHANGED_TRADES = 4
MIN_CHANGED_WINDOWS = 2
MIN_EV_IMPROVED_WINDOWS = 3
MIN_RELATIVE_EV_IMPROVEMENT = 0.10


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rank_key(row: dict[str, Any]) -> tuple[float, float, float, str]:
    return (
        float(row["score"]),
        float(row["ret20_excess_spy"]),
        float(row["volume_ratio_20"]),
        str(row["ticker"]),
    )


def _select_rows_for_window(
    *,
    label: str,
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    min_day_candidate_count: int | None,
) -> dict[str, Any]:
    spec = WINDOWS[label]
    days = p35._trading_days(prices, spec["start"], spec["end"])
    spy_rows = prices.get("SPY") or []
    spy_index = indexes.get("SPY") or {}
    active: list[dict[str, str]] = []
    selected_rows: list[dict[str, Any]] = []
    blocked_days: list[dict[str, Any]] = []
    daily_candidate_counts: OrderedDict[str, int] = OrderedDict()

    for day in days:
        active = [row for row in active if row["exit_date"] > day]
        capacity = int(PROFILE_CONFIG["max_active_positions"]) - len(active)
        if capacity <= 0:
            continue

        active_tickers = {row["ticker"] for row in active}
        features: list[dict[str, Any]] = []
        for ticker in candidate_tickers:
            if ticker in active_tickers:
                continue
            rows = prices.get(ticker) or []
            idx = (indexes.get(ticker) or {}).get(day)
            if idx is None:
                continue
            feature = build_broad_market_feature(
                ticker=ticker,
                rows=rows,
                idx=idx,
                spy_rows=spy_rows,
                spy_index=spy_index,
            )
            if feature and candidate_passes_profile(feature, PROFILE_CONFIG):
                features.append(feature)

        ranked = sorted(features, key=_rank_key, reverse=True)
        day_candidate_count = len(ranked)
        daily_candidate_counts[day] = day_candidate_count
        if (
            min_day_candidate_count is not None
            and day_candidate_count < int(min_day_candidate_count)
        ):
            blocked_days.append(
                {
                    "window": label,
                    "decision_date": day,
                    "day_candidate_count": day_candidate_count,
                    "min_day_candidate_count": min_day_candidate_count,
                    "active_count": len(active),
                    "capacity": capacity,
                    "top_candidates": [
                        {
                            "ticker": str(row["ticker"]),
                            "score": row.get("score"),
                            "ret20_excess_spy": row.get("ret20_excess_spy"),
                            "ret60": row.get("ret60"),
                            "near_high_60": row.get("near_high_60"),
                        }
                        for row in ranked[:5]
                    ],
                }
            )
            continue

        daily_slots = min(int(PROFILE_CONFIG["daily_entry_slots"]), capacity)
        selected_count = 0
        for queue_rank, feature in enumerate(ranked, start=1):
            if selected_count >= daily_slots:
                break
            selected_count += 1
            selected_rank = selected_count
            annotated = dict(feature)
            annotated["candidate_breadth_gate_applied"] = (
                min_day_candidate_count is not None
            )
            annotated["day_candidate_count"] = day_candidate_count
            annotated["min_day_candidate_count"] = min_day_candidate_count
            annotated["candidate_queue_rank"] = queue_rank
            selected_rows.append(
                {
                    "window": label,
                    "rank": selected_rank,
                    "feature": annotated,
                }
            )
            trade = backtest_trade_from_feature(
                feature=annotated,
                prices_by_ticker=prices,
                window_end=spec["end"],
                rank=selected_rank,
                config=PROFILE_CONFIG,
            )
            if trade is None:
                continue
            active.append({"ticker": trade["ticker"], "exit_date": trade["exit_date"]})
            active_tickers.add(trade["ticker"])

    return {
        "selected_rows": selected_rows,
        "blocked_days": blocked_days,
        "daily_candidate_counts": daily_candidate_counts,
    }


def _variant_trades(
    *,
    selected_rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    label: str,
) -> list[dict[str, Any]]:
    spec = WINDOWS[label]
    trades: list[dict[str, Any]] = []
    for row in selected_rows:
        trade = backtest_trade_from_feature(
            feature=row["feature"],
            prices_by_ticker=prices,
            window_end=spec["end"],
            rank=int(row["rank"]),
            config=PROFILE_CONFIG,
        )
        if trade is None:
            continue
        trade["window"] = label
        trade["candidate_breadth_gate_applied"] = row["feature"].get(
            "candidate_breadth_gate_applied"
        )
        trade["day_candidate_count"] = row["feature"].get("day_candidate_count")
        trade["min_day_candidate_count"] = row["feature"].get("min_day_candidate_count")
        trade["candidate_queue_rank"] = row["feature"].get("candidate_queue_rank")
        trades.append(trade)
    return trades


def _trade_key(trade: dict[str, Any]) -> tuple[str, str, str]:
    return (str(trade["window"]), str(trade["decision_date"]), str(trade["ticker"]))


def _trade_rows(trades: list[dict[str, Any]], *, limit: int = 60) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in sorted(trades, key=lambda row: (row["entry_date"], row["ticker"]))[:limit]:
        rows.append(
            {
                "ticker": trade["ticker"],
                "window": trade["window"],
                "decision_date": trade["decision_date"],
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "pnl": trade["pnl"],
                "net_return_pct": trade["net_return_pct"],
                "rank": trade["rank"],
                "candidate_queue_rank": trade.get("candidate_queue_rank"),
                "score": trade["score"],
                "ret20_excess_spy": trade["ret20_excess_spy"],
                "ret5": trade.get("ret5"),
                "ret60": trade["ret60"],
                "volume_ratio_20": trade["volume_ratio_20"],
                "near_high_60": trade["near_high_60"],
                "realized_volatility_20": trade.get("realized_volatility_20"),
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "notional": trade.get("notional"),
                "day_candidate_count": trade.get("day_candidate_count"),
                "min_day_candidate_count": trade.get("min_day_candidate_count"),
                "candidate_breadth_gate_applied": trade.get(
                    "candidate_breadth_gate_applied"
                ),
            }
        )
    return rows


def _window_sleeve_summary(
    trades: list[dict[str, Any]],
    scout: dict[str, Any],
    blocked_days: list[dict[str, Any]],
) -> dict[str, Any]:
    base = p35._window_sleeve_summary(trades, scout)
    daily_counts = scout["daily_candidate_counts"]
    nonzero_counts = [count for count in daily_counts.values() if count > 0]
    base["breadth_blocked_day_count"] = len(blocked_days)
    base["breadth_blocked_days_sample"] = blocked_days[:20]
    base["candidate_count_distribution"] = {
        "days_observed": len(daily_counts),
        "signal_days": len(nonzero_counts),
        "min": min(nonzero_counts) if nonzero_counts else None,
        "max": max(nonzero_counts) if nonzero_counts else None,
        "avg": round(sum(nonzero_counts) / len(nonzero_counts), 4)
        if nonzero_counts
        else None,
    }
    base["sample_trades"] = _trade_rows(trades, limit=25)
    return base


def _variant_payload(
    *,
    variant_name: str,
    min_day_candidate_count: int | None,
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    identity_keys: set[tuple[str, str, str]] | None,
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    all_blocked_days: list[dict[str, Any]] = []

    for label, spec in WINDOWS.items():
        selected = _select_rows_for_window(
            label=label,
            candidate_tickers=candidate_tickers,
            prices=prices,
            indexes=indexes,
            min_day_candidate_count=min_day_candidate_count,
        )
        trades = _variant_trades(
            selected_rows=selected["selected_rows"],
            prices=prices,
            label=label,
        )
        blocked_days = selected["blocked_days"]
        all_trades.extend(trades)
        all_blocked_days.extend(blocked_days)
        curve = p35._event_equity_curve(
            trades=trades,
            prices=prices,
            start=spec["start"],
            end=spec["end"],
        )
        after_metrics[label] = p35._metrics_from_overlay(
            baseline_metrics=control_metrics[label],
            event_curve=curve,
            event_trades=trades,
        )
        sleeve[label] = _window_sleeve_summary(
            trades,
            {
                "trades": trades,
                "candidate_signal_days": sum(
                    1 for count in selected["daily_candidate_counts"].values() if count > 0
                ),
                "candidate_signal_count": sum(
                    selected["daily_candidate_counts"].values()
                ),
                "max_daily_candidate_count": max(
                    selected["daily_candidate_counts"].values() or [0]
                ),
                "daily_candidate_counts": selected["daily_candidate_counts"],
            },
            blocked_days,
        )

    keys = {_trade_key(row) for row in all_trades}
    if identity_keys is None:
        changed_count = 0
        changed_windows: list[str] = []
        removed_count = 0
        added_count = 0
    else:
        removed_keys = identity_keys - keys
        added_keys = keys - identity_keys
        changed_keys = removed_keys | added_keys
        changed_count = len(changed_keys)
        changed_windows = sorted({key[0] for key in changed_keys})
        removed_count = len(removed_keys)
        added_count = len(added_keys)

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = p35._single_ticker_positive_share(all_trades)
    top5_share = p35._top5_positive_share(all_trades)
    relative_ev_improvement = float(delta["aggregate_ev_delta_pct"] or 0.0)
    sample_guard_passed = len(all_trades) >= p35.MIN_SELECTED_TRADES
    changed_guard_passed = (
        changed_count >= MIN_CHANGED_TRADES and len(changed_windows) >= MIN_CHANGED_WINDOWS
    )
    window_guard_passed = selected_windows >= p35.MIN_SELECTED_WINDOWS
    concentration_guard_passed = (
        (single_share is None or single_share <= p35.MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (top5_share is None or top5_share <= p35.MAX_TOP5_POSITIVE_SHARE)
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= p35.MAX_DRAWDOWN_WORSE
    materiality_guard_passed = relative_ev_improvement >= MIN_RELATIVE_EV_IMPROVEMENT
    gate4_passed = bool(
        variant_name != "baseline_no_candidate_breadth_gate"
        and delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and delta["windows_pnl_regressed"] == 0
        and sample_guard_passed
        and changed_guard_passed
        and window_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
        and materiality_guard_passed
    )
    return {
        "variant_name": variant_name,
        "min_day_candidate_count": min_day_candidate_count,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "selected_windows": selected_windows,
        "selected_trades_sample": _trade_rows(all_trades, limit=60),
        "trade_keys": keys,
        "changed_trade_count": changed_count,
        "changed_windows": changed_windows,
        "removed_trade_count": removed_count,
        "added_trade_count": added_count,
        "breadth_blocked_day_count": len(all_blocked_days),
        "breadth_blocked_windows": sorted({row["window"] for row in all_blocked_days}),
        "breadth_blocked_days_sample": all_blocked_days[:25],
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta": delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
            "relative_ev_improvement": relative_ev_improvement,
            "minimum_relative_ev_improvement": MIN_RELATIVE_EV_IMPROVEMENT,
            "materiality_guard_passed": materiality_guard_passed,
            "windows_ev_improved": delta["windows_ev_improved"],
            "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
            "windows_ev_regressed": delta["windows_ev_regressed"],
            "windows_pnl_regressed": delta["windows_pnl_regressed"],
            "selected_trade_count": len(all_trades),
            "minimum_selected_trades": p35.MIN_SELECTED_TRADES,
            "selected_windows": selected_windows,
            "minimum_selected_windows": p35.MIN_SELECTED_WINDOWS,
            "sample_guard_passed": sample_guard_passed,
            "changed_trade_count": changed_count,
            "minimum_changed_trades": MIN_CHANGED_TRADES,
            "changed_windows": changed_windows,
            "minimum_changed_windows": MIN_CHANGED_WINDOWS,
            "changed_guard_passed": changed_guard_passed,
            "breadth_blocked_day_count": len(all_blocked_days),
            "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
            "max_drawdown_worse_guardrail": p35.MAX_DRAWDOWN_WORSE,
            "drawdown_guard_passed": drawdown_guard_passed,
            "single_ticker_positive_share": single_share,
            "max_single_ticker_positive_share": p35.MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "top5_positive_share": top5_share,
            "max_top5_positive_share": p35.MAX_TOP5_POSITIVE_SHARE,
            "concentration_guard_passed": concentration_guard_passed,
        },
    }


def _choose_selected(variants: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in variants if row["gate4"]["passed"]]
    if accepted:
        return max(
            accepted,
            key=lambda row: (
                row["delta_metrics"]["aggregate_ev_delta"],
                row["delta_metrics"]["aggregate_pnl_delta"],
            ),
        )
    changed = [
        row
        for row in variants
        if row["variant_name"] != "baseline_no_candidate_breadth_gate"
    ]
    return max(
        changed or variants,
        key=lambda row: (
            row["delta_metrics"]["aggregate_ev_delta"],
            row["delta_metrics"]["aggregate_pnl_delta"],
            row["gate4"]["windows_ev_improved"],
            -row["gate4"]["windows_ev_regressed"],
        ),
    )


def _sweep_summary(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "variant_name": row["variant_name"],
            "min_day_candidate_count": row["min_day_candidate_count"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "changed_trade_count": row["changed_trade_count"],
            "changed_windows": row["changed_windows"],
            "removed_trade_count": row["removed_trade_count"],
            "added_trade_count": row["added_trade_count"],
            "breadth_blocked_day_count": row["breadth_blocked_day_count"],
            "aggregate_ev_delta": row["delta_metrics"]["aggregate_ev_delta"],
            "relative_ev_improvement": row["gate4"]["relative_ev_improvement"],
            "aggregate_pnl_delta": row["delta_metrics"]["aggregate_pnl_delta"],
            "windows_ev_improved": row["gate4"]["windows_ev_improved"],
            "windows_ev_regressed": row["gate4"]["windows_ev_regressed"],
            "windows_pnl_regressed": row["gate4"]["windows_pnl_regressed"],
            "max_drawdown_worse_max": row["gate4"]["max_drawdown_worse_max"],
            "single_ticker_positive_share": row["single_ticker_positive_share"],
            "top5_positive_share": row["top5_positive_share"],
            "materiality_guard_passed": row["gate4"]["materiality_guard_passed"],
        }
        for row in variants
    ]


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Candidate-Breadth Gate",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single causal variable: minimum same-day broad-market candidate count "
            "before the default-off paper sleeve opens new entries."
        ),
        "",
        "## Trial Accounting",
        "",
        f"- mechanism_family: `{payload['mechanism_family']}`",
        f"- trial_family: `{payload['trial_family']}`",
        f"- changed_variable: `{payload['changed_variable']}`",
        f"- prior_trial_count: `{payload['prior_trial_count']}`",
        f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
        f"- new_evidence_type: `{payload['new_evidence_type']}`",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Min Count | Trades | Changed | Blocked Days | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {gate} | {min_count} | {trades} | {changed} | {blocked} | {ev:+.4f} | {rel:+.2%} | ${pnl:+,.2f} | {wi} | {wr} | {dd:+.4%} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["passed"] else "FAIL",
                min_count=row["min_day_candidate_count"]
                if row["min_day_candidate_count"] is not None
                else "none",
                trades=row["selected_trade_count"],
                changed=row["changed_trade_count"],
                blocked=row["breadth_blocked_day_count"],
                ev=float(row["aggregate_ev_delta"] or 0.0),
                rel=float(row["relative_ev_improvement"] or 0.0),
                pnl=float(row["aggregate_pnl_delta"] or 0.0),
                wi=row["windows_ev_improved"],
                wr=row["windows_ev_regressed"],
                dd=float(row["max_drawdown_worse_max"] or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Evidence",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
            )
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }


def build_payload() -> dict[str, Any]:
    if not BASELINE_JSON.exists():
        raise RuntimeError(f"Missing baseline artifact: {_repo_rel(BASELINE_JSON)}")
    if not CONTROL_JSON.exists():
        raise RuntimeError(f"Missing control artifact: {_repo_rel(CONTROL_JSON)}")

    gate2 = p35._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = _json_load(BASELINE_JSON)
    control_payload = _json_load(CONTROL_JSON)
    expected_decision = "accepted_default_off_broad_market_trend_persistence_notional"
    if baseline_payload.get("decision") != expected_decision:
        raise RuntimeError(f"Unexpected baseline decision: {baseline_payload.get('decision')}")

    control_metrics = control_payload["before_metrics"]
    before_metrics = baseline_payload["after_metrics"]
    warehouse = p35._warehouse_audit()
    candidate_universe = baseline_payload["candidate_universe"]
    frozen_tickers = list(candidate_universe["tickers"])
    prices = p35._load_price_rows(frozen_tickers)
    indexes = p35._index_by_date(prices)

    identity_values = BREADTH_GATE_SWEEP["baseline_no_candidate_breadth_gate"]
    identity = _variant_payload(
        variant_name="baseline_no_candidate_breadth_gate",
        min_day_candidate_count=identity_values["min_day_candidate_count"],
        control_metrics=control_metrics,
        before_metrics=before_metrics,
        candidate_tickers=frozen_tickers,
        prices=prices,
        indexes=indexes,
        identity_keys=None,
    )
    identity_keys = set(identity["trade_keys"])
    variants = [identity]
    variants.extend(
        _variant_payload(
            variant_name=name,
            min_day_candidate_count=values["min_day_candidate_count"],
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            candidate_tickers=frozen_tickers,
            prices=prices,
            indexes=indexes,
            identity_keys=identity_keys,
        )
        for name, values in BREADTH_GATE_SWEEP.items()
        if name != "baseline_no_candidate_breadth_gate"
    )

    identity_control = {
        "passed": (
            abs(float(identity["delta_metrics"]["aggregate_ev_delta"])) < 1e-9
            and abs(float(identity["delta_metrics"]["aggregate_pnl_delta"])) < 0.01
            and abs(float(identity["gate4"]["max_drawdown_worse_max"])) < 1e-9
        ),
        "variant_name": identity["variant_name"],
        "aggregate_ev_delta_vs_accepted_artifact": identity["delta_metrics"][
            "aggregate_ev_delta"
        ],
        "aggregate_pnl_delta_vs_accepted_artifact": identity["delta_metrics"][
            "aggregate_pnl_delta"
        ],
        "max_drawdown_worse_max_vs_accepted_artifact": identity["gate4"][
            "max_drawdown_worse_max"
        ],
    }

    selected = _choose_selected(variants)
    selected["gate4"]["identity_control_passed"] = identity_control["passed"]
    if not identity_control["passed"]:
        selected["gate4"]["passed"] = False
    accepted = selected["gate4"]["passed"]
    decision = (
        "accepted_default_off_broad_market_candidate_breadth_gate"
        if accepted
        else "rejected_broad_market_candidate_breadth_gate"
    )
    status = "accepted" if accepted else "rejected"
    aggregate_before = p35._aggregate(before_metrics)
    aggregate_after = p35._aggregate(selected["after_metrics"])
    gate3 = {
        "signals_generated": {
            label: before_metrics[label].get("signals_generated") for label in WINDOWS
        },
        "signals_survived": {
            label: before_metrics[label].get("signals_survived") for label in WINDOWS
        },
        "survival_rate": {
            label: before_metrics[label].get("survival_rate") for label in WINDOWS
        },
        "survival_rate_min": aggregate_before["survival_rate_min"],
        "passed": aggregate_before["survival_rate_min"] >= 0.05,
        "note": "No core filter was added; broad-market sleeve remains default-off paper only.",
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "parity_test_added": False,
        "live_order_path_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }
    for row in variants:
        row.pop("trade_keys", None)

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Broad-market leadership paper candidates may work best when the "
            "same-day opportunity set is broad enough to show real market "
            "participation. A minimum candidate-count gate may avoid thin, "
            "idiosyncratic leadership days without adding noisy tickers."
        ),
        "change_type": "default_off_paper_candidate_selection",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": selected["variant_name"],
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": len(NEARBY_PRIOR_EXPERIMENTS),
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_production_visible_market_participation_field",
        "single_causal_variable": (
            "minimum same-day count of fixed-profile broad-market candidates "
            "required before opening new default-off paper entries"
        ),
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "reference_experiment_id": REFERENCE_EXPERIMENT_ID,
            "selected_variant": selected["variant_name"],
            "selected_min_day_candidate_count": selected["min_day_candidate_count"],
            "minimum_relative_ev_improvement": MIN_RELATIVE_EV_IMPROVEMENT,
            "minimum_changed_trades": MIN_CHANGED_TRADES,
            "minimum_changed_windows": MIN_CHANGED_WINDOWS,
            "sweep": BREADTH_GATE_SWEEP,
            "profile_config": {
                key: PROFILE_CONFIG[key]
                for key in (
                    "ret20_excess_spy_min",
                    "ret60_min",
                    "near_high_60_min",
                    "volume_ratio_20_min",
                    "decision_close_price_min",
                    "paper_notional_usd",
                    "rank_notional_multipliers",
                    "low_extension_ret5_max",
                    "low_extension_notional_scalar",
                    "high_volatility_20_min",
                    "high_volatility_notional_scalar",
                    "trend_persistence_positive_day_ratio_20_min",
                    "trend_persistence_notional_scalar",
                    "max_active_positions",
                    "daily_entry_slots",
                    "hold_days",
                )
            },
            "candidate_count": candidate_universe.get("candidate_count"),
            "excluded_count": candidate_universe.get("excluded_count"),
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"]} for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260520-004 trend-persistence broad-market adapter is the before "
            "state; after state applies a same-day candidate-breadth entry gate."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(BASELINE_JSON),
            "control_artifact": _repo_rel(CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
        },
        "gate2": gate2,
        "gate3": gate3,
        "identity_control": identity_control,
        "gate4": selected["gate4"],
        "before_metrics": before_metrics,
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "expected_value_score_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_ev_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "total_pnl_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_pnl_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["total_pnl"]
                for label in WINDOWS
            },
        },
        "sweep_summary": _sweep_summary(variants),
        "selected_variant": {
            "variant_name": selected["variant_name"],
            "min_day_candidate_count": selected["min_day_candidate_count"],
            "selected_trade_count": selected["selected_trade_count"],
            "changed_trade_count": selected["changed_trade_count"],
            "changed_windows": selected["changed_windows"],
            "removed_trade_count": selected["removed_trade_count"],
            "added_trade_count": selected["added_trade_count"],
            "breadth_blocked_day_count": selected["breadth_blocked_day_count"],
            "breadth_blocked_windows": selected["breadth_blocked_windows"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "selected_trades_sample": selected["selected_trades_sample"],
            "breadth_blocked_days_sample": selected["breadth_blocked_days_sample"],
        },
        "broad_market_sleeve": selected["broad_market_sleeve"],
        "candidate_universe": candidate_universe,
        "warehouse_audit": warehouse,
        "llm_metrics": {
            "changed": False,
            "reason": "This run avoids sparse LLM soft-ranking and does not alter LLM prompts or decisions.",
        },
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate_pool/ranking: same-day candidate breadth can identify "
                "when broad-market leadership is broad participation rather than "
                "isolated idiosyncratic momentum."
            ),
            "2_past_similar_experiments": (
                "Broad-market price-floor, rank-notional, low-extension, "
                "high-volatility, trend-persistence, score-gap, correlation "
                "crowding, and return-path cluster fields were tested. Candidate "
                "breadth gating has not been formalized for this sleeve."
            ),
            "3_single_variable": (
                "Only min_day_candidate_count changes; universe, eligibility "
                "profile, rank profile, accepted notional scalars, hold, slots, "
                "and candidate source stay fixed."
            ),
            "4_acceptance": (
                "Gate 4 requires positive aggregate EV/PnL, all 3 windows "
                "EV-positive, no EV/PnL regression windows, >=4 changed trades "
                "across >=2 windows, concentration guard, <=0.5pp drawdown "
                "worsening, identity control, and >=10% aggregate EV improvement "
                "because this is a frozen-sample broad-market selection retune."
            ),
            "5_reproducibility": (
                "Script, JSON artifact, log, ticket, markdown artifact, and JSONL "
                "identify windows, parameters, selected/blocked examples, and metrics."
            ),
        },
        "interpretation": (
            "Candidate breadth is a production-visible market-participation proxy. "
            "Because this still changes frozen broad-market paper selection, no "
            "shared adapter is changed unless the strict materiality gate clears."
        ),
        "rejection_reason": None
        if accepted
        else "Candidate-breadth gating did not clear the strict three-window broad-market materiality gate.",
        "next_evidence_needed": (
            "If forward broad-market paper rows show thin-breadth days driving "
            "losses, retest with live ledger replacement-value evidence before "
            "enabling any shared selection rule."
        ),
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
            "baseline": _repo_rel(BASELINE_JSON),
            "control": _repo_rel(CONTROL_JSON),
        },
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
    }
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(json.dumps(_safe(payload["sweep_summary"]), indent=2, sort_keys=True))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "selected_variant": payload["selected_variant"]["variant_name"],
                    "gate4": payload["gate4"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "output": payload["related_files"]["output"],
                    "anti_js": payload["parameters"]["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
