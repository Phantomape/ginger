"""exp-20260519-016: state-surface top-3 sector diversity notional.

Alpha search. Freezes the accepted state-surface paper stack through
exp-20260519-015, then tests one production-visible allocation variable:
same-day state-surface queues whose top three candidates span at least two
sectors receive a bounded residual default-off paper-notional profile.

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

import exp_20260519_015_state_surface_rank3_volume_confirmation_notional as prev


EXPERIMENT_ID = "exp-20260519-016"
EXPERIMENT_SLUG = "state_surface_top3_sector_diversity_notional"

REPO_ROOT = prev.REPO_ROOT
WINDOWS = prev.WINDOWS
BASELINE_VARIANT = "accepted_rank3_volume_confirmation_notional"
ACCEPTED_RANK3_VOLUME_VARIANT = "rank3_volume_ge_110_scalar_150"
MIN_SELECTED_TRADES = prev.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 6
MIN_ADJUSTED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = prev.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = prev.MAX_SINGLE_TICKER_POSITIVE_SHARE
RULE_VERSION = "state_surface_top3_sector_diversity_rank_notional_v1"

DOC_HELPERS = prev.DOC_HELPERS
CORE_HELPERS = prev.CORE_HELPERS
CONCENTRATION_HELPERS = prev.CONCENTRATION_HELPERS

TOP3_SECTOR_DIVERSITY_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "min_top3_sector_count": 2,
                "aggression_order": 0,
                "description": "accepted stack through rank-3 volume confirmation",
            },
        ),
        (
            "top3_sector_diversity_rank1_lift",
            {
                "profile": [1.75, 1.30, 1.0, 0.675, 0.35],
                "min_top3_sector_count": 2,
                "aggression_order": 1,
                "description": "top-3 sector diversity with rank-1 lift",
            },
        ),
        (
            "top3_sector_diversity_rank2_lift",
            {
                "profile": [1.45, 1.65, 1.05, 0.675, 0.35],
                "min_top3_sector_count": 2,
                "aggression_order": 2,
                "description": "top-3 sector diversity with rank-2 lift",
            },
        ),
        (
            "top3_sector_diversity_rank3_lift",
            {
                "profile": [1.45, 1.25, 1.35, 0.675, 0.35],
                "min_top3_sector_count": 2,
                "aggression_order": 3,
                "description": "top-3 sector diversity with rank-3 lift",
            },
        ),
        (
            "top3_sector_diversity_balanced",
            {
                "profile": [1.60, 1.40, 1.15, 0.675, 0.35],
                "min_top3_sector_count": 2,
                "aggression_order": 4,
                "description": "top-3 sector diversity with balanced top-3 support",
            },
        ),
        (
            "top3_sector_diversity_depth_relief",
            {
                "profile": [1.35, 1.45, 1.30, 0.675, 0.35],
                "min_top3_sector_count": 2,
                "aggression_order": 5,
                "description": "top-3 sector diversity shifts notional from rank 1 to rank 2/3",
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


def _float(value: Any) -> float | None:
    return prev._float(value)


def _accepted_rank3_volume_trades(
    *,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    baseline = prev._accepted_rank2_support_trades(
        core_results=core_results,
        prices=prices,
    )
    accepted_variant = prev.RANK3_VOLUME_CONFIRMATION_VARIANTS[
        ACCEPTED_RANK3_VOLUME_VARIANT
    ]
    return prev._apply_rank3_volume_confirmation(
        baseline,
        variant_name=ACCEPTED_RANK3_VOLUME_VARIANT,
        variant=accepted_variant,
    )


def _sector(trade: dict[str, Any]) -> str:
    return prev._sector(trade)


def _profile_multiplier(profile: list[float], queue_rank: Any) -> float:
    try:
        rank = int(queue_rank)
    except (TypeError, ValueError):
        rank = 1
    rank = max(rank, 1)
    if rank > len(profile):
        return float(profile[-1])
    return float(profile[rank - 1])


def _top3_sector_state_by_window_day(
    trades: list[dict[str, Any]],
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
        sectors = [_sector(row) for row in top3]
        known = [sector for sector in sectors if sector and sector != "Unknown"]
        sector_counts = Counter(known)
        top2_cohesion_already_applied = any(
            bool(row.get("top2_sector_cohesion_profile_applied"))
            or str(row.get("rank_notional_profile_name") or "")
            == "top2_sector_cohesion_technology"
            for row in ranked
        )
        out[key] = {
            "top3_sector_sequence": sectors,
            "top3_sector_count": len(set(known)),
            "top3_sector_distribution": dict(sector_counts),
            "top3_sector_diversity": len(top3) >= 3 and len(set(known)) >= 2,
            "top3_sector_diversity_residual": (
                len(top3) >= 3
                and len(set(known)) >= 2
                and not top2_cohesion_already_applied
            ),
            "top2_sector_cohesion_already_applied": top2_cohesion_already_applied,
        }
    return out


def _support_scalar(row: dict[str, Any]) -> float:
    scalar = 1.0
    for key in (
        "rank2_near_high_support_scalar",
        "rank3_near_high_support_scalar",
        "rank3_volume_confirmation_scalar",
        "recent_ticker_repeat_scalar",
    ):
        if bool(row.get(key.replace("_scalar", "_applied"))) or row.get(key) is not None:
            parsed = _float(row.get(key))
            if parsed is not None:
                scalar *= parsed
    return scalar


def _base_event_notional(row: dict[str, Any]) -> float:
    multiplier = _float(row.get("rank_notional_multiplier"))
    notional = _float(row.get("notional"))
    if multiplier is not None and multiplier > 0 and notional is not None:
        return notional / multiplier
    return 10_000.0


def _profile_name(min_sector_count: int, profile: list[float]) -> str:
    text = "_".join(str(round(float(value), 6)).rstrip("0").rstrip(".").replace(".", "p") for value in profile)
    return f"top3_sector_count_ge_{min_sector_count}_{text}"


def _apply_top3_sector_diversity_profile(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    state = _top3_sector_state_by_window_day(trades)
    adjusted: list[dict[str, Any]] = []
    profile = variant.get("profile")
    min_sector_count = int(variant.get("min_top3_sector_count") or 2)
    for trade in trades:
        row = dict(trade)
        key = (
            str(row.get("window") or ""),
            str(row.get("decision_date") or "")[:10],
        )
        sector_state = state.get(key) or {}
        row.update(sector_state)
        row["top3_sector_diversity_variant"] = variant_name
        row["top3_sector_diversity_profile_applied"] = False
        row["top3_sector_diversity_profile_name"] = None
        row["top3_sector_diversity_rule_version"] = RULE_VERSION
        row["rank_notional_top3_sector_diversity_rule_version"] = RULE_VERSION
        row["top3_sector_diversity_min_sector_count"] = min_sector_count
        row["top3_sector_diversity_configured_profile"] = profile
        row["top3_sector_diversity_base_multiplier"] = _float(
            row.get("rank_notional_multiplier")
        )

        applies = (
            variant_name != BASELINE_VARIANT
            and bool(profile)
            and bool(row.get("top3_sector_diversity_residual"))
            and int(row.get("top3_sector_count") or 0) >= min_sector_count
        )
        if applies:
            base_multiplier = _profile_multiplier(profile, row.get("queue_rank"))
            support = _support_scalar(row)
            final_multiplier = round(base_multiplier * support, 6)
            base_notional = _base_event_notional(row)
            new_notional = round(base_notional * final_multiplier, 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["top3_sector_diversity_profile_applied"] = True
            row["top3_sector_diversity_profile_name"] = _profile_name(
                min_sector_count,
                list(profile),
            )
            row["top3_sector_diversity_support_scalar"] = round(support, 6)
            row["rank_notional_multiplier"] = final_multiplier
            row["notional"] = new_notional
            row["shares"] = new_notional / entry_open
            row["pnl"] = round(new_notional * net_return, 2)
        adjusted.append(row)
    return adjusted


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


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "sector": _sector(trade),
                "window": trade.get("window"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "queue_rank": trade.get("queue_rank"),
                "candidate_breadth": trade.get("candidate_breadth"),
                "score": trade.get("score"),
                "ret20_excess_spy": features.get("ret20_excess_spy"),
                "ret60": features.get("ret60"),
                "near_high_60": features.get("near_high_60"),
                "volume_ratio_20": features.get("volume_ratio_20"),
                "rank2_near_high_support_applied": trade.get(
                    "rank2_near_high_support_applied"
                ),
                "rank3_near_high_support_applied": trade.get(
                    "rank3_near_high_support_applied"
                ),
                "rank3_volume_confirmation_applied": trade.get(
                    "rank3_volume_confirmation_applied"
                ),
                "top2_sector_cohesion_already_applied": trade.get(
                    "top2_sector_cohesion_already_applied"
                ),
                "top3_sector_sequence": trade.get("top3_sector_sequence"),
                "top3_sector_count": trade.get("top3_sector_count"),
                "top3_sector_diversity": trade.get("top3_sector_diversity"),
                "top3_sector_diversity_residual": trade.get(
                    "top3_sector_diversity_residual"
                ),
                "top3_sector_diversity_profile_applied": trade.get(
                    "top3_sector_diversity_profile_applied"
                ),
                "top3_sector_diversity_profile_name": trade.get(
                    "top3_sector_diversity_profile_name"
                ),
                "rank_notional_profile_name": trade.get("rank_notional_profile_name"),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _notional_by_diversity_profile(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(trade.get("top3_sector_diversity_profile_name") or "baseline")
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
    selected = _apply_top3_sector_diversity_profile(
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
        adjusted = [row for row in selected if row.get("window") == label]
        applied = [
            row for row in adjusted if row.get("top3_sector_diversity_profile_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(adjusted),
            "top3_sector_diversity_adjusted_trade_count": len(applied),
            "top3_sector_diversity_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in adjusted),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for row in adjusted if float(row.get("pnl") or 0.0) > 0)
                / len(adjusted),
                4,
            )
            if adjusted
            else None,
            "ticker_distribution": dict(Counter(row.get("ticker") for row in adjusted)),
            "sector_distribution": dict(Counter(_sector(row) for row in adjusted)),
            "notional_by_top3_sector_diversity_profile": (
                _notional_by_diversity_profile(adjusted)
            ),
            "selected_trades": _selected_trade_rows(adjusted),
        }
    applied_all = [
        row for row in selected if row.get("top3_sector_diversity_profile_applied")
    ]
    applied_windows = {str(row.get("window")) for row in applied_all if row.get("window")}
    return {
        "variant_name": variant_name,
        "variant_type": "top3_sector_diversity_rank_notional_profile",
        "profile": variant.get("profile"),
        "min_top3_sector_count": variant.get("min_top3_sector_count"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "top3_sector_diversity_adjusted_trade_count": len(applied_all),
        "top3_sector_diversity_adjusted_windows": sorted(applied_windows),
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
        variant["top3_sector_diversity_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["top3_sector_diversity_adjusted_windows"])
        >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
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
        "top3_sector_diversity_adjusted_trade_count": variant[
            "top3_sector_diversity_adjusted_trade_count"
        ],
        "top3_sector_diversity_adjusted_windows": variant[
            "top3_sector_diversity_adjusted_windows"
        ],
        "selected_trade_count": variant["selected_trade_count"],
        "sample_guard_passed": sample_guard_passed,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": share,
        "baseline_single_ticker_positive_share": baseline_share,
        "single_ticker_positive_share_delta": share_delta,
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
        ),
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Top-3 Sector Diversity Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `top3_sector_diversity_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {profile} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                profile=row["profile"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["top3_sector_diversity_adjusted_trade_count"],
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
                trades=sleeve["top3_sector_diversity_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
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

    baseline_trades = _accepted_rank3_volume_trades(
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
        for variant_name, variant in TOP3_SECTOR_DIVERSITY_VARIANTS.items()
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
                "profile": variant["profile"],
                "min_top3_sector_count": variant["min_top3_sector_count"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "top3_sector_diversity_adjusted_trade_count": variant[
                    "top3_sector_diversity_adjusted_trade_count"
                ],
                "top3_sector_diversity_adjusted_windows": variant[
                    "top3_sector_diversity_adjusted_windows"
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
        "accepted_default_off_state_surface_top3_sector_diversity_notional"
        if passed
        else "rejected_state_surface_top3_sector_diversity_notional"
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
        "hypothesis": "When the accepted rotation state-surface queue has top-three sector diversity, the queue has broader participation and can use a residual default-off paper-notional profile without increasing live risk.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Targets state-surface maturation with a new crowding/concentration field, avoids LLM soft-ranking data limits, and avoids candidate-pool expansion.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "top3_sector_diversity_rank_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_profile": best["profile"],
            "min_top3_sector_count": best["min_top3_sector_count"],
            "profile_priority": "residual only; does not override accepted top-2 Technology sector-cohesion dates, while existing rank2/rank3 support scalars remain additive",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "rank3 volume confirmation scalar",
                "rank3 near-high support scalar",
                "rank2 near-high support scalar",
                "recent repeat scalar",
                "SEC text scalars",
                "candidate-pool expansion",
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
            "baseline_artifact": DOC_HELPERS._repo_rel(
                "data/experiments/exp-20260519-015/state_surface_rank3_volume_confirmation_notional.json"
            ),
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": "Uses the accepted rank3 volume confirmation stack as Gate 1 baseline.",
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "queue_rank",
                "ticker",
                "SECTOR_MAP sector",
                "decision_date",
                "top3_sector_count",
                "top3_sector_diversity_residual",
                "rank_notional_multiplier",
                "entry_open",
                "net_return_pct",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in baseline_metrics.values()
            ),
            "after_survival_rate": {
                label: best_payload["metrics"][label].get("survival_rate")
                for label in WINDOWS
            },
            "hard_rule": "No filter or candidate gate changed; only paper notional changes on already-selected queue rows.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260518-025": "Accepted top-2 Technology sector cohesion; this run is residual and explicitly avoids overriding those dates.",
            "exp-20260519-015": "Accepted rank-3 volume confirmation; this run freezes it and tests sector diversity, not another volume threshold.",
            "exp-20260519-011": "Rejected candidate-pool expansion because the cached augmented baseline did not align and old_thin regressed.",
            "anti_repeat": "Not a near-high, volume, ret20, ret60, score-gap, repeat-lookback, SEC text, candidate-pool, or LLM soft-ranking retry.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this deterministic field uses replayable ticker-sector metadata and queue ranks.",
        },
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": True,
            "parity_test_added": passed,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
            "default_off_paper_only": True,
        },
        "interpretation": (
            "Top-3 sector diversity improved the default-off state-surface paper overlay without changing core/live behavior."
            if passed
            else "Top-3 sector diversity did not clear Gate 4; keep the accepted rank3-volume stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata; keep forward tail/concentration monitoring before any live adapter work."
            if passed
            else "Do not retry nearby sector-diversity profiles without forward evidence or a materially different production-visible crowding field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: residual top-three sector diversity may route paper notional toward broader participation queues while preserving accepted concentrated Technology cohesion.",
            "2_history_check": "Prior accepted sector work was top-2 Technology cohesion; current run freezes it and tests a residual top-three sector-count field. Recent rejected work covered candidate-pool expansion and SEC/negative-language scalars.",
            "3_single_causal_variable": "top3_sector_diversity_rank_notional_profile",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, at least two EV-improved windows, zero EV-regressed windows, adjusted trades >=6 across >=2 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            DOC_HELPERS._repo_rel(Path(__file__)),
            DOC_HELPERS._repo_rel(OUT_JSON),
            DOC_HELPERS._repo_rel(LOG_JSON),
            DOC_HELPERS._repo_rel(TICKET_JSON),
            DOC_HELPERS._repo_rel(ARTIFACT_MD),
            DOC_HELPERS._repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
        ],
    }
    return DOC_HELPERS._safe(payload)


def main() -> None:
    payload = build_payload()
    DOC_HELPERS._write_json(OUT_JSON, payload)
    DOC_HELPERS._write_json(LOG_JSON, payload)
    DOC_HELPERS._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface top-3 sector diversity notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": DOC_HELPERS._repo_rel(OUT_JSON),
            "summary": (
                f"Top-3 sector diversity best profile {payload['parameters']['best_profile']} "
                f"changed aggregate EV {payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
                f"and PnL ${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    DOC_HELPERS._upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
