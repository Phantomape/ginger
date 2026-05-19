"""exp-20260519-009: state-surface top-3 near-high breadth notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
when at least two of the top three state-surface candidates are close to their
own 60-day highs, treat queue breadth as healthier and apply a bounded top-3
rank-notional profile.

Core entries, exits, candidate eligibility, queue ranking, hold days, active
capacity, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260519_006_state_surface_rank2_near_high_support_notional as prev


EXPERIMENT_ID = "exp-20260519-009"
EXPERIMENT_SLUG = "state_surface_top3_near_high_breadth_notional"

REPO_ROOT = prev.REPO_ROOT
WINDOWS = prev.WINDOWS
BASELINE_VARIANT = "accepted_rank3_near_high_support_notional"
MIN_SELECTED_TRADES = prev.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 9
MIN_ADJUSTED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = prev.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = prev.MAX_SINGLE_TICKER_POSITIVE_SHARE
RULE_VERSION = "state_surface_top3_near_high_breadth_rank_notional_v1"

CORE_HELPERS = prev.CORE_HELPERS
CONCENTRATION_HELPERS = prev.CONCENTRATION_HELPERS

TOP3_NEAR_HIGH_BREADTH_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "near_high_min": None,
                "min_top3_count": None,
                "profile": None,
                "aggression_order": 0,
                "description": "accepted stack through rank-3 near-high support",
            },
        ),
        (
            "top3_near_high_count2_ge_0975_balanced",
            {
                "near_high_min": 0.975,
                "min_top3_count": 2,
                "profile": [1.80, 1.55, 1.25, 0.675, 0.35],
                "aggression_order": 1,
                "description": "balanced top-three support when at least two front candidates are within 2.5% of 60-day highs",
            },
        ),
        (
            "top3_near_high_count2_ge_0975_rank1_heavy",
            {
                "near_high_min": 0.975,
                "min_top3_count": 2,
                "profile": [2.00, 1.45, 1.15, 0.675, 0.35],
                "aggression_order": 2,
                "description": "rank-1-heavy top-three support when at least two front candidates are within 2.5% of 60-day highs",
            },
        ),
        (
            "top3_near_high_count2_ge_098_balanced",
            {
                "near_high_min": 0.98,
                "min_top3_count": 2,
                "profile": [1.80, 1.55, 1.25, 0.675, 0.35],
                "aggression_order": 3,
                "description": "balanced top-three support when at least two front candidates are within 2% of 60-day highs",
            },
        ),
        (
            "top3_near_high_count3_ge_0975_balanced",
            {
                "near_high_min": 0.975,
                "min_top3_count": 3,
                "profile": [1.80, 1.55, 1.25, 0.675, 0.35],
                "aggression_order": 4,
                "description": "balanced top-three support only when all top-three candidates are within 2.5% of 60-day highs",
            },
        ),
        (
            "top3_near_high_count2_ge_0970_conservative",
            {
                "near_high_min": 0.970,
                "min_top3_count": 2,
                "profile": [1.70, 1.45, 1.20, 0.675, 0.35],
                "aggression_order": 5,
                "description": "wider but conservative top-three support when at least two front candidates are within 3% of 60-day highs",
            },
        ),
    ]
)

OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") != payload["experiment_id"]:
                rows.append(line)
    rows.append(json.dumps(_safe(payload), sort_keys=True))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _float(value: Any) -> float | None:
    return prev._float(value)


def _accepted_rank3_support_trades(
    *,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return prev._accepted_rank3_support_trades(
        core_results=core_results,
        prices=prices,
    )


def _metrics_for_trades(
    *,
    trades: list[dict[str, Any]],
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    return prev._metrics_for_trades(
        trades=trades,
        core_results=core_results,
        prices=prices,
    )


def _sector(trade: dict[str, Any]) -> str:
    return prev._sector(trade)


def _profile_multiplier(profile: list[float], rank: Any) -> float:
    try:
        queue_rank = int(rank)
    except (TypeError, ValueError):
        queue_rank = 1
    queue_rank = max(queue_rank, 1)
    if queue_rank > len(profile):
        return float(profile[-1])
    return float(profile[queue_rank - 1])


def _base_event_notional(row: dict[str, Any]) -> float:
    notional = _float(row.get("notional"))
    multiplier = _float(row.get("rank_notional_multiplier"))
    if notional is not None and multiplier is not None and multiplier > 0:
        return round(notional / multiplier, 2)
    return 10_000.0


def _profile_name(near_high_min: float, min_top3_count: int) -> str:
    threshold = str(round(float(near_high_min), 6)).rstrip("0").rstrip(".")
    return (
        "top3_near_high_count"
        f"{int(min_top3_count)}_ge_{threshold.replace('.', 'p')}"
    )


def _top3_near_high_context(
    trades: list[dict[str, Any]],
    *,
    threshold: float | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trade in trades:
        grouped.setdefault(
            (
                str(trade.get("window") or ""),
                str(trade.get("decision_date") or "")[:10],
            ),
            [],
        ).append(trade)

    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, rows in grouped.items():
        ranked = sorted(rows, key=lambda row: int(row.get("queue_rank") or 999))
        top3 = ranked[:3]
        values = [
            _float((row.get("features") or {}).get("near_high_60"))
            for row in top3
        ]
        count = (
            sum(1 for value in values if value is not None and value >= threshold)
            if threshold is not None
            else 0
        )
        out[key] = {
            "top3_near_high_values": values,
            "top3_near_high_count": count,
            "top3_sample_size": len(top3),
        }
    return out


def _apply_top3_near_high_breadth_profile(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    threshold = _float(variant.get("near_high_min"))
    min_top3_count = variant.get("min_top3_count")
    try:
        min_count = int(min_top3_count)
    except (TypeError, ValueError):
        min_count = 0
    profile = variant.get("profile")
    context = _top3_near_high_context(trades, threshold=threshold)
    adjusted: list[dict[str, Any]] = []

    for trade in trades:
        row = dict(trade)
        features = dict(row.get("features") or {})
        row["features"] = features
        key = (
            str(row.get("window") or ""),
            str(row.get("decision_date") or "")[:10],
        )
        ctx = context.get(key) or {}
        queue_rank = int(row.get("queue_rank") or row.get("rank") or 999)
        applies = (
            variant_name != BASELINE_VARIANT
            and threshold is not None
            and min_count > 0
            and isinstance(profile, list)
            and queue_rank <= 3
            and int(ctx.get("top3_near_high_count") or 0) >= min_count
        )

        row["top3_near_high_breadth_variant"] = variant_name
        row["top3_near_high_breadth_rule_version"] = RULE_VERSION
        row["top3_near_high_breadth_min"] = threshold
        row["top3_near_high_breadth_min_count"] = min_count or None
        row["top3_near_high_count"] = ctx.get("top3_near_high_count")
        row["top3_near_high_values"] = ctx.get("top3_near_high_values")
        row["top3_near_high_breadth_profile_applied"] = bool(applies)
        row["top3_near_high_breadth_profile_name"] = (
            _profile_name(float(threshold), min_count)
            if threshold is not None and min_count > 0
            else None
        )
        row["rank_notional_top3_near_high_breadth_rule_version"] = RULE_VERSION

        if applies:
            multiplier = _profile_multiplier(profile, queue_rank)
            base_notional = _base_event_notional(row)
            new_notional = round(base_notional * multiplier, 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["top3_near_high_breadth_base_notional"] = base_notional
            row["rank_notional_multiplier"] = round(multiplier, 6)
            row["notional"] = new_notional
            row["shares"] = new_notional / entry_open
            row["pnl"] = round(new_notional * net_return, 2)
        adjusted.append(row)
    return adjusted


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "sector": _sector(trade),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "queue_rank": trade.get("queue_rank"),
                "candidate_breadth": trade.get("candidate_breadth"),
                "score": trade.get("score"),
                "score_top_to_second_gap": trade.get("score_top_to_second_gap"),
                "score_top3_spread": trade.get("score_top3_spread"),
                "near_high_60": features.get("near_high_60"),
                "top3_near_high_count": trade.get("top3_near_high_count"),
                "top3_near_high_values": trade.get("top3_near_high_values"),
                "top3_near_high_breadth_profile_applied": trade.get(
                    "top3_near_high_breadth_profile_applied"
                ),
                "top3_near_high_breadth_profile_name": trade.get(
                    "top3_near_high_breadth_profile_name"
                ),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _notional_by_breadth_profile(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(trade.get("top3_near_high_breadth_profile_name") or "baseline")
        row = out.setdefault(key, {"trade_count": 0, "notional_sum": 0.0, "pnl_sum": 0.0})
        row["trade_count"] += 1
        row["notional_sum"] += float(trade.get("notional") or 0.0)
        row["pnl_sum"] += float(trade.get("pnl") or 0.0)
    for row in out.values():
        row["notional_sum"] = round(row["notional_sum"], 2)
        row["pnl_sum"] = round(row["pnl_sum"], 2)
    return out


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    baseline_trades: list[dict[str, Any]],
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    selected = _apply_top3_near_high_breadth_profile(
        baseline_trades,
        variant_name=variant_name,
        variant=variant,
    )
    metrics = _metrics_for_trades(
        trades=selected,
        core_results=core_results,
        prices=prices,
    )
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    for label in WINDOWS:
        rows = [row for row in selected if row.get("window") == label]
        applied = [
            row for row in rows if row.get("top3_near_high_breadth_profile_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(rows),
            "top3_near_high_breadth_adjusted_trade_count": len(applied),
            "top3_near_high_breadth_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in rows),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for row in rows if float(row.get("pnl") or 0.0) > 0)
                / len(rows),
                4,
            )
            if rows
            else None,
            "ticker_distribution": dict(Counter(row.get("ticker") for row in rows)),
            "sector_distribution": dict(Counter(_sector(row) for row in rows)),
            "notional_by_top3_near_high_breadth_profile": (
                _notional_by_breadth_profile(rows)
            ),
            "selected_trades": _selected_trade_rows(rows),
        }
    applied_all = [
        row for row in selected if row.get("top3_near_high_breadth_profile_applied")
    ]
    applied_windows = {str(row.get("window")) for row in applied_all if row.get("window")}
    return {
        "variant_name": variant_name,
        "variant_type": "top3_near_high_breadth_rank_notional_profile",
        "near_high_min": variant.get("near_high_min"),
        "min_top3_count": variant.get("min_top3_count"),
        "profile": variant.get("profile"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "top3_near_high_breadth_adjusted_trade_count": len(applied_all),
        "top3_near_high_breadth_adjusted_windows": sorted(applied_windows),
        "single_ticker_positive_share": CONCENTRATION_HELPERS._single_ticker_positive_share(
            selected
        ),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = CORE_HELPERS._aggregate_delta(baseline_metrics, variant["metrics"])
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["top3_near_high_breadth_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["top3_near_high_breadth_adjusted_windows"])
        >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    tail_concentration_not_worse = (
        variant["single_ticker_positive_share"] is None
        or baseline_share is None
        or variant["single_ticker_positive_share"] <= baseline_share + 1e-12
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    passed = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and sample_guard_passed
        and adjusted_guard_passed
        and concentration_guard_passed
        and tail_concentration_not_worse
        and drawdown_guard_passed
    )
    share = variant["single_ticker_positive_share"]
    share_delta = (
        round(share - baseline_share, 6)
        if share is not None and baseline_share is not None
        else None
    )
    return {
        "passed": passed,
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "top3_near_high_breadth_adjusted_trade_count": variant[
            "top3_near_high_breadth_adjusted_trade_count"
        ],
        "top3_near_high_breadth_adjusted_windows": variant[
            "top3_near_high_breadth_adjusted_windows"
        ],
        "selected_trade_count": variant["selected_trade_count"],
        "sample_guard_passed": sample_guard_passed,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": share,
        "baseline_single_ticker_positive_share": baseline_share,
        "single_ticker_positive_share_delta": share_delta,
        "tail_concentration_not_worse": tail_concentration_not_worse,
        "concentration_guard_passed": concentration_guard_passed,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard_passed,
        "minimum_selected_trades": MIN_SELECTED_TRADES,
        "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
        "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
        "delta_metrics": delta,
    }


def _choose_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [
        row
        for row in rows
        if row["variant_name"] != BASELINE_VARIANT and row["gate4"]["passed"]
    ]
    if passing:
        return max(
            passing,
            key=lambda row: (
                row["gate4"]["aggregate_ev_delta"],
                row["gate4"]["aggregate_pnl_delta"],
                -row["gate4"]["max_drawdown_worse_max"],
                -row["aggression_order"],
            ),
        )
    return max(
        [row for row in rows if row["variant_name"] != BASELINE_VARIANT],
        key=lambda row: (
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            row["gate4"]["windows_ev_improved"],
            -row["gate4"]["windows_ev_regressed"],
            -row["gate4"]["max_drawdown_worse_max"],
        ),
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Top-3 Near-High Breadth Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `top3_near_high_breadth_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Near High Min | Min Count | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {threshold} | {count} | {profile} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                threshold=row["near_high_min"] if row["near_high_min"] is not None else "n/a",
                count=row["min_top3_count"] if row["min_top3_count"] is not None else "n/a",
                profile=row["profile"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["top3_near_high_breadth_adjusted_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share=f"{share:.2%}" if share is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bdd:.2%} | {add:.2%} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                trades=sleeve["top3_near_high_breadth_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
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


def build_payload() -> dict[str, Any]:
    gate2 = CORE_HELPERS._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    prices = CORE_HELPERS._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        core_results[label] = CORE_HELPERS._load_core_result(window)

    baseline_trades = _accepted_rank3_support_trades(
        core_results=core_results,
        prices=prices,
    )
    baseline_metrics = _metrics_for_trades(
        trades=baseline_trades,
        core_results=core_results,
        prices=prices,
    )
    baseline_share = CONCENTRATION_HELPERS._single_ticker_positive_share(
        baseline_trades
    )

    variants = [
        _variant_payload(
            variant_name=variant_name,
            variant=variant,
            baseline_trades=baseline_trades,
            core_results=core_results,
            prices=prices,
        )
        for variant_name, variant in TOP3_NEAR_HIGH_BREADTH_VARIANTS.items()
    ]
    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            baseline_share=baseline_share,
            variant=variant,
        )
        sweep_summary.append(
            {
                "variant_name": variant["variant_name"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "near_high_min": variant["near_high_min"],
                "min_top3_count": variant["min_top3_count"],
                "profile": variant["profile"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "top3_near_high_breadth_adjusted_trade_count": variant[
                    "top3_near_high_breadth_adjusted_trade_count"
                ],
                "top3_near_high_breadth_adjusted_windows": variant[
                    "top3_near_high_breadth_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(
        row for row in variants if row["variant_name"] == best["variant_name"]
    )
    delta = CORE_HELPERS._aggregate_delta(baseline_metrics, best_payload["metrics"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_top3_near_high_breadth_notional"
        if passed
        else "rejected_state_surface_top3_near_high_breadth_notional"
    )
    interpretation = (
        "Top-3 near-high breadth produced a promotable broader state-surface "
        "allocation field under the tail-aware gate."
        if passed
        else "Top-3 near-high breadth did not meet the harder tail-aware gate. "
        "Treat the result as attribution only, not another shared notional rule."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        ),
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "hypothesis": "A state-surface day with at least two of the top three candidates near their own 60-day highs is a broader, healthier rotation breadth state; a bounded top-3 paper-notional profile should improve EV without worsening tail concentration.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Tests a new production-visible breadth field instead of adjacent rank2/rank3 scalar retuning.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "top3_near_high_breadth_rank_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_near_high_min": best["near_high_min"],
            "best_min_top3_count": best["min_top3_count"],
            "best_profile": best["profile"],
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "LLM/news",
                "live/default orders",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows; core unchanged plus default-off state-surface paper overlay replay.",
        "before_metrics": baseline_metrics,
        "after_metrics": best_payload["metrics"],
        "delta_metrics": delta,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"]
            for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_ev_delta"]},
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_pnl_delta"]},
        "gate1": {
            "baseline_artifact": "data/experiments/exp-20260519-004/state_surface_rank3_near_high_support_notional.json",
            "baseline_variant": BASELINE_VARIANT,
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "queue_rank",
                "features.near_high_60",
                "rank_notional_multiplier",
                "event_notional_usd",
                "entry_open",
                "net_return_pct",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "hard_rule": "No filter or candidate gate changed; only top-three paper notional changes when breadth condition applies.",
        },
        "gate4": best["gate4"],
        "sweep_summary": sweep_summary,
        "surface_sleeve": best_payload["surface_sleeve"],
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": (
            "If accepted, add shared default-off policy and parity coverage before "
            "any commit; live/default orders stay disabled."
            if passed
            else "Do not retry adjacent near-high breadth profiles; move to forward "
            "replacement value or a distinct field."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: top-three near-high breadth may identify healthier state-surface rotation days.",
            "2_history_check": "exp-20260519-004 rank3 near-high support improved all windows but adjusted only 5 trades; exp-20260519-006 rank2 near-high made more money but worsened tail concentration. This tests breadth rather than adjacent rank scalar retuning.",
            "3_single_causal_variable": "top3_near_high_breadth_rank_notional_profile",
            "4_acceptance_standard": "Aggregate EV/PnL positive, >=2 EV-improved windows, zero EV-regressed windows, >=9 adjusted trades across >=2 windows, max drawdown guard, absolute concentration guard, and single-ticker positive share not worse than baseline.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(
        json.dumps(
            {
                "anti_js": payload["anti_js"],
                "decision": payload["decision"],
                "experiment_id": payload["experiment_id"],
                "best_variant": payload["parameters"]["best_variant"],
                "adjusted_trade_count": payload["gate4"][
                    "top3_near_high_breadth_adjusted_trade_count"
                ],
                "adjusted_windows": payload["gate4"][
                    "top3_near_high_breadth_adjusted_windows"
                ],
                "aggregate_ev_delta": payload["gate4"]["aggregate_ev_delta"],
                "aggregate_pnl_delta": payload["gate4"]["aggregate_pnl_delta"],
                "tail_concentration_not_worse": payload["gate4"][
                    "tail_concentration_not_worse"
                ],
                "gate4_passed": payload["gate4"]["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
