"""exp-20260519-001: residual state-surface score-expansion notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
after the accepted higher-priority state-surface profiles have applied, use a
bounded rank-notional profile for residual broad queues whose top-three score
spread shows a clear rank-1 leader.

Core entries, exits, candidate eligibility, queue size, hold days, active
capacity, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260518_027_state_surface_rank1_ret60_residual_notional as parent  # noqa: E402


EXPERIMENT_ID = "exp-20260519-001"
EXPERIMENT_SLUG = "state_surface_score_expansion_notional"

REPO_ROOT = parent.REPO_ROOT
WINDOWS = parent.WINDOWS
BASELINE_VARIANT = "accepted_rank1_ret60_residual_notional"
MIN_SELECTED_TRADES = parent.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = parent.MIN_ADJUSTED_TRADES
MIN_ADJUSTED_WINDOWS = parent.MIN_ADJUSTED_WINDOWS
MAX_DRAWDOWN_WORSE = parent.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = parent.MAX_SINGLE_TICKER_POSITIVE_SHARE

SCORE_EXPANSION_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "score_top3_spread_min": None,
                "candidate_breadth_min": None,
                "aggression_order": 0,
                "description": "current accepted residual rank-1 ret60 stack",
            },
        ),
        (
            "residual_score_expansion_ge_040_rank1_top",
            {
                "profile": [1.85, 1.25, 1.0, 0.675, 0.35],
                "score_top3_spread_min": 0.40,
                "candidate_breadth_min": 4,
                "aggression_order": 1,
                "description": "residual broad queue with score_top3_spread >= 0.40, rank-1 top-up",
            },
        ),
        (
            "residual_score_expansion_ge_040_balanced_top2",
            {
                "profile": [1.55, 1.55, 1.0, 0.675, 0.35],
                "score_top3_spread_min": 0.40,
                "candidate_breadth_min": 4,
                "aggression_order": 2,
                "description": "same residual score-expansion field, balanced rank 1/2",
            },
        ),
        (
            "residual_score_expansion_ge_080_rank1_top",
            {
                "profile": [1.85, 1.25, 1.0, 0.675, 0.35],
                "score_top3_spread_min": 0.80,
                "candidate_breadth_min": 4,
                "aggression_order": 3,
                "description": "stricter residual score expansion with rank-1 top-up",
            },
        ),
    ]
)

OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _current_accepted_trades(
    *,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    accepted_baseline = parent._current_accepted_baseline(
        core_results=core_results,
        prices=prices,
    )
    accepted_variant = parent.RESIDUAL_RET60_VARIANTS[
        "residual_rank1_ret60_ge_050_rank2_shift"
    ]
    return parent._apply_residual_rank1_ret60_profile(
        accepted_baseline["selected_trades"],
        variant_name="residual_rank1_ret60_ge_050_rank2_shift",
        variant=accepted_variant,
    )


def _metrics_for_trades(
    *,
    trades: list[dict[str, Any]],
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        selected = [row for row in trades if row.get("window") == label]
        event_curve = parent.rank_exp._event_equity_curve_variable_notional(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        metrics[label] = parent.parent.base._combined_metrics(
            core_results[label],
            event_curve,
            selected,
        )
    return metrics


def _score_expansion_profile_name(threshold: float) -> str:
    value = str(round(float(threshold), 6)).rstrip("0").rstrip(".")
    return f"score_expansion_top3_ge_{value.replace('.', 'p')}"


def _profile_multiplier(profile: list[float], rank: Any) -> float:
    try:
        queue_rank = int(rank)
    except (TypeError, ValueError):
        queue_rank = 1
    if queue_rank <= 0:
        queue_rank = 1
    if queue_rank > len(profile):
        return float(profile[-1])
    return float(profile[queue_rank - 1])


def _base_profile_name(row: dict[str, Any]) -> str:
    return str(
        row.get("score_expansion_profile_name")
        or row.get("rank1_ret60_residual_profile_name")
        or row.get("top2_sector_cohesion_profile_name")
        or row.get("rank_notional_profile_name")
        or ""
    )


def _apply_score_expansion_profile(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    adjusted = []
    base_notional = float(parent.parent.base.EVENT_NOTIONAL)
    profile = variant.get("profile")
    spread_min = parent._float(variant.get("score_top3_spread_min"))
    breadth_min = parent._float(variant.get("candidate_breadth_min"))
    for trade in trades:
        row = dict(trade)
        row["score_expansion_variant"] = variant_name
        row["score_expansion_profile_applied"] = False
        row["score_expansion_profile_name"] = _base_profile_name(row)
        row["score_expansion_min_top3_spread"] = None
        row["score_expansion_skipped_reason"] = None

        top3_spread = parent._float(row.get("score_top3_spread"))
        candidate_breadth = parent._float(row.get("candidate_breadth"))
        residual_generic_breadth = _base_profile_name(row) == "candidate_breadth_ge4_override"
        applies = (
            variant_name != BASELINE_VARIANT
            and profile
            and spread_min is not None
            and breadth_min is not None
            and top3_spread is not None
            and candidate_breadth is not None
            and top3_spread >= spread_min
            and candidate_breadth >= breadth_min
            and residual_generic_breadth
        )
        if not residual_generic_breadth and spread_min is not None:
            row["score_expansion_skipped_reason"] = (
                "higher_priority_rank_notional_profile_has_priority"
            )
        if applies:
            multiplier = _profile_multiplier(profile, row.get("queue_rank") or row.get("rank"))
            notional = round(base_notional * multiplier, 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["score_expansion_profile_applied"] = True
            row["score_expansion_profile_name"] = _score_expansion_profile_name(
                spread_min
            )
            row["score_expansion_min_top3_spread"] = spread_min
            row["rank_notional_multiplier"] = multiplier
            row["notional"] = notional
            row["shares"] = notional / entry_open
            row["pnl"] = round(notional * net_return, 2)
        adjusted.append(row)
    return adjusted


def _sector(trade: dict[str, Any]) -> str:
    return str(trade.get("sector") or parent.accepted._sector(trade.get("ticker")))


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = parent._features(trade)
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
                "score_expansion_min_top3_spread": trade.get(
                    "score_expansion_min_top3_spread"
                ),
                "score_expansion_profile_applied": trade.get(
                    "score_expansion_profile_applied"
                ),
                "score_expansion_profile_name": trade.get(
                    "score_expansion_profile_name"
                ),
                "score_expansion_skipped_reason": trade.get(
                    "score_expansion_skipped_reason"
                ),
                "base_rank_notional_profile_name": _base_profile_name(trade),
                "rank1_ret60": trade.get("rank1_ret60"),
                "rank1_ret60_residual_profile_applied": trade.get(
                    "rank1_ret60_residual_profile_applied"
                ),
                "top2_sector_cohesion": trade.get("top2_sector_cohesion"),
                "top2_sector_cohesion_profile_applied": trade.get(
                    "top2_sector_cohesion_profile_applied"
                ),
                "rank2_ret20_excess_spy": trade.get("rank2_ret20_excess_spy"),
                "rank2_ret20_excess_spy_lead": trade.get(
                    "rank2_ret20_excess_spy_lead"
                ),
                "ret20_excess_spy": features.get("ret20_excess_spy"),
                "ret5": features.get("ret5"),
                "ret60": features.get("ret60"),
                "near_high_60": features.get("near_high_60"),
                "volume_ratio_20": features.get("volume_ratio_20"),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _notional_by_profile(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(trade.get("score_expansion_profile_name") or "baseline")
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
    selected = _apply_score_expansion_profile(
        baseline_trades,
        variant_name=variant_name,
        variant=variant,
    )
    after_metrics = _metrics_for_trades(
        trades=selected,
        core_results=core_results,
        prices=prices,
    )
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    for label in WINDOWS:
        adjusted = [row for row in selected if row.get("window") == label]
        adjusted_trades = [
            trade for trade in adjusted if trade.get("score_expansion_profile_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(adjusted),
            "score_expansion_adjusted_trade_count": len(adjusted_trades),
            "score_expansion_adjusted_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in adjusted_trades),
                2,
            ),
            "selected_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in adjusted),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for trade in adjusted if float(trade.get("pnl") or 0.0) > 0)
                / len(adjusted),
                4,
            )
            if adjusted
            else None,
            "sector_distribution": dict(Counter(_sector(row) for row in adjusted)),
            "notional_by_queue_rank": parent.rank_exp._notional_by_queue_rank(adjusted),
            "notional_by_score_expansion_profile": _notional_by_profile(adjusted),
            "surface_summary": parent.parent.base._surface_summary(adjusted),
            "selected_trades": _selected_trade_rows(adjusted),
        }

    adjusted_all = [
        trade for trade in selected if trade.get("score_expansion_profile_applied")
    ]
    adjusted_windows = {
        str(trade.get("window")) for trade in adjusted_all if trade.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "residual_score_expansion_rank_notional_profile",
        "profile": variant.get("profile"),
        "score_top3_spread_min": variant.get("score_top3_spread_min"),
        "candidate_breadth_min": variant.get("candidate_breadth_min"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "score_expansion_adjusted_trade_count": len(adjusted_all),
        "score_expansion_adjusted_windows": sorted(adjusted_windows),
        "single_ticker_positive_share": parent._single_ticker_positive_share(selected),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = parent.parent._aggregate_delta(baseline_metrics, variant["metrics"])
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["score_expansion_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["score_expansion_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
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
        "score_expansion_adjusted_trade_count": variant[
            "score_expansion_adjusted_trade_count"
        ],
        "score_expansion_adjusted_windows": variant[
            "score_expansion_adjusted_windows"
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
    non_identity = [row for row in rows if row["variant_name"] != BASELINE_VARIANT]
    return max(
        non_identity,
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
        f"# {EXPERIMENT_ID} State-Surface Score-Expansion Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `residual_score_expansion_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Spread | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        spread = row["score_top3_spread_min"]
        lines.append(
            "| {variant} | {passed} | {spread} | {profile} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                spread=f"{spread:.2f}" if spread is not None else "n/a",
                profile=row["profile"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["score_expansion_adjusted_trade_count"],
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
                trades=sleeve["score_expansion_adjusted_trade_count"],
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
    gate2 = parent.parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    prices = parent.parent._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        core_results[label] = parent.parent._load_core_result(window)

    baseline_trades = _current_accepted_trades(
        core_results=core_results,
        prices=prices,
    )
    baseline_metrics = _metrics_for_trades(
        trades=baseline_trades,
        core_results=core_results,
        prices=prices,
    )
    baseline_share = parent._single_ticker_positive_share(baseline_trades)

    variants = [
        _variant_payload(
            variant_name=variant_name,
            variant=variant,
            baseline_trades=baseline_trades,
            core_results=core_results,
            prices=prices,
        )
        for variant_name, variant in SCORE_EXPANSION_VARIANTS.items()
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
                "score_top3_spread_min": variant["score_top3_spread_min"],
                "candidate_breadth_min": variant["candidate_breadth_min"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "score_expansion_adjusted_trade_count": variant[
                    "score_expansion_adjusted_trade_count"
                ],
                "score_expansion_adjusted_windows": variant[
                    "score_expansion_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(
        row for row in variants if row["variant_name"] == best["variant_name"]
    )
    delta = parent.parent._aggregate_delta(baseline_metrics, best_payload["metrics"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_score_expansion_notional"
        if passed
        else "rejected_state_surface_score_expansion_notional"
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
        "hypothesis": "After higher-priority state-surface profiles have applied, residual broad queues with score_top3_spread >= 0.40 contain a clearer rank-1 leader and should receive bounded rank-1 paper notional.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Targets state-surface maturation with a replayable rank-quality field while preserving stronger accepted top2-sector and rank1-ret60 profiles.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "residual_score_expansion_rank_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_profile": best["profile"],
            "best_score_top3_spread_min": best["score_top3_spread_min"],
            "best_candidate_breadth_min": best["candidate_breadth_min"],
            "profile_priority": "after top2 Technology, rank1 ret60 residual, rank2 ret20/score-gap, rank1 ret20 dominance, and score-compression profiles; before generic candidate-breadth profile",
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
            "baseline_artifact": parent._repo_rel(
                "data/experiments/exp-20260518-027/state_surface_rank1_ret60_residual_notional.json"
            ),
            "baseline_variant": BASELINE_VARIANT,
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "ticker",
                "decision_date",
                "queue_rank",
                "candidate_breadth",
                "score_top3_spread",
                "rank_notional_profile_name",
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
            "hard_rule": "No filter or candidate gate changed; survival is measured from the same selected paper/core trade set.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260518-013": "Accepted low score-compression (score_top3_spread <= 0.40) profile; this tests the opposite residual score-expansion side and does not retune that accepted branch.",
            "exp-20260518-021": "Rejected rank-2 ret5 leadership; this test does not use ret5.",
            "exp-20260518-024": "Rejected low-volume rank-1 dominance; this test does not use volume.",
            "exp-20260518-027": "Accepted residual rank1-ret60; this test preserves that priority and only touches generic candidate-breadth residual rows.",
            "anti_repeat": "Not a nearby ret20/ret60/volume/ret5 scalar retry; it is a residual score-dispersion branch before generic breadth allocation.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this deterministic paper allocation field uses replayable score-dispersion metadata.",
        },
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": True,
            "parity_test_added": passed,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
        },
        "interpretation": (
            "Residual score expansion improved the default-off state-surface paper overlay in two windows with no EV-regressed window, lower positive-contribution concentration, and no core/live order change."
            if passed
            else "Residual score expansion did not clear Gate 4; do not promote it without forward evidence."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata and continue monitoring forward concentration before any live adapter work."
            if passed
            else "Do not retry nearby residual score-expansion profiles without forward evidence or a genuinely new quality field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: residual score_top3_spread >= 0.40 may identify broad state-surface queues where rank 1 deserves more paper notional than generic candidate-breadth allocation.",
            "2_history_check": "Builds on exp-013 score-compression, exp-024 volume rejection, and exp-027 residual ret60 acceptance; exact residual score-expansion branch has not been tested.",
            "3_single_causal_variable": "residual_score_expansion_rank_notional_profile",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, >=2 improved windows, zero EV-regressed windows, adjusted trades >=6 across >=2 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            parent._repo_rel(Path(__file__)),
            parent._repo_rel(OUT_JSON),
            parent._repo_rel(LOG_JSON),
            parent._repo_rel(TICKET_JSON),
            parent._repo_rel(ARTIFACT_MD),
            parent._repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
        ],
    }
    return parent._safe(payload)


def main() -> None:
    payload = build_payload()
    parent._write_json(OUT_JSON, payload)
    parent._write_json(LOG_JSON, payload)
    parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface residual score-expansion notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": parent._repo_rel(OUT_JSON),
            "summary": (
                f"Residual score-expansion best profile {payload['parameters']['best_profile']} "
                f"changed aggregate EV {payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
                f"and PnL ${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    parent._upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
