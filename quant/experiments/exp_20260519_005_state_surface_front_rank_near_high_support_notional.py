"""exp-20260519-005: state-surface front-rank near-high support notional.

Alpha search. Freezes the accepted state-surface paper stack through
exp-20260519-004, then tests one production-visible allocation variable:
front-ranked queue candidates (rank 1 or 2) whose own price is still close to
its 60-day high receive a bounded default-off paper-notional scalar.

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

import exp_20260519_004_state_surface_rank3_near_high_support_notional as parent


EXPERIMENT_ID = "exp-20260519-005"
EXPERIMENT_SLUG = "state_surface_front_rank_near_high_support_notional"

REPO_ROOT = parent.REPO_ROOT
WINDOWS = parent.WINDOWS
BASELINE_VARIANT = "accepted_rank3_near_high_support_notional"
MIN_SELECTED_TRADES = parent.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 5
MIN_ADJUSTED_WINDOWS = 3
MAX_DRAWDOWN_WORSE = parent.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = parent.MAX_SINGLE_TICKER_POSITIVE_SHARE
RULE_VERSION = "state_surface_front_rank_near_high_support_notional_v1"

FRONT_RANK_NEAR_HIGH_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "near_high_min": None,
                "scalar": None,
                "max_queue_rank": 2,
                "aggression_order": 0,
                "description": "accepted stack through rank-3 near-high support",
            },
        ),
        (
            "front_rank_near_high_ge_098_scalar_110",
            {
                "near_high_min": 0.98,
                "scalar": 1.10,
                "max_queue_rank": 2,
                "aggression_order": 1,
                "description": "rank 1/2 candidate near 60-day high receives 10% support",
            },
        ),
        (
            "front_rank_near_high_ge_098_scalar_125",
            {
                "near_high_min": 0.98,
                "scalar": 1.25,
                "max_queue_rank": 2,
                "aggression_order": 2,
                "description": "rank 1/2 candidate near 60-day high receives 25% support",
            },
        ),
        (
            "front_rank_near_high_ge_098_scalar_150",
            {
                "near_high_min": 0.98,
                "scalar": 1.50,
                "max_queue_rank": 2,
                "aggression_order": 3,
                "description": "rank 1/2 candidate near 60-day high receives 50% support",
            },
        ),
    ]
)

OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _accepted_rank3_support_trades(
    *,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    baseline = parent._accepted_rank1_score_isolation_trades(
        core_results=core_results,
        prices=prices,
    )
    accepted_variant = parent.RANK3_NEAR_HIGH_VARIANTS[
        "rank3_near_high_ge_098_scalar_150"
    ]
    return parent._apply_rank3_near_high_support(
        baseline,
        variant_name="rank3_near_high_ge_098_scalar_150",
        variant=accepted_variant,
    )


def _float(value: Any) -> float | None:
    return parent._float(value)


def _profile_name(near_high_min: float, scalar: float, max_queue_rank: int) -> str:
    threshold = str(round(float(near_high_min), 6)).rstrip("0").rstrip(".")
    scalar_text = str(round(float(scalar), 6)).rstrip("0").rstrip(".")
    return (
        f"front_rank_le_{max_queue_rank}_near_high_ge_"
        f"{threshold.replace('.', 'p')}_{scalar_text.replace('.', 'p')}x"
    )


def _apply_front_rank_near_high_support(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    threshold = _float(variant.get("near_high_min"))
    scalar = _float(variant.get("scalar"))
    max_rank = int(variant.get("max_queue_rank") or 2)
    adjusted: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        queue_rank = int(row.get("queue_rank") or row.get("rank") or 999)
        near_high = _float((row.get("features") or {}).get("near_high_60"))
        applies = (
            variant_name != BASELINE_VARIANT
            and threshold is not None
            and scalar is not None
            and near_high is not None
            and queue_rank <= max_rank
            and near_high >= threshold
        )

        row["front_rank_near_high_support_variant"] = variant_name
        row["front_rank_near_high_support_rule_version"] = RULE_VERSION
        row["front_rank_near_high_60"] = near_high
        row["front_rank_near_high_support_max_queue_rank"] = max_rank
        row["front_rank_near_high_support_min"] = threshold
        row["front_rank_near_high_support_configured_scalar"] = scalar
        row["front_rank_near_high_support_scalar"] = scalar if applies else None
        row["front_rank_near_high_support_applied"] = bool(applies)
        row["front_rank_near_high_support_profile_name"] = (
            _profile_name(threshold, scalar, max_rank)
            if variant_name != BASELINE_VARIANT
            and threshold is not None
            and scalar is not None
            else None
        )
        row["rank_notional_front_rank_near_high_support_rule_version"] = RULE_VERSION

        if applies:
            base_notional = float(row.get("notional") or 0.0)
            new_notional = round(base_notional * float(scalar), 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["front_rank_near_high_support_base_notional"] = base_notional
            row["notional"] = new_notional
            row["shares"] = new_notional / entry_open
            row["pnl"] = round(new_notional * net_return, 2)
            base_multiplier = _float(row.get("rank_notional_multiplier"))
            if base_multiplier is not None:
                row["rank_notional_multiplier"] = round(
                    base_multiplier * float(scalar),
                    6,
                )
        adjusted.append(row)
    return adjusted


def _metrics_for_trades(
    *,
    trades: list[dict[str, Any]],
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    return parent._metrics_for_trades(
        trades=trades,
        core_results=core_results,
        prices=prices,
    )


def _sector(trade: dict[str, Any]) -> str:
    return parent._sector(trade)


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
                "front_rank_near_high_support_applied": trade.get(
                    "front_rank_near_high_support_applied"
                ),
                "front_rank_near_high_support_min": trade.get(
                    "front_rank_near_high_support_min"
                ),
                "front_rank_near_high_support_scalar": trade.get(
                    "front_rank_near_high_support_scalar"
                ),
                "front_rank_near_high_support_profile_name": trade.get(
                    "front_rank_near_high_support_profile_name"
                ),
                "rank3_near_high_support_applied": trade.get(
                    "rank3_near_high_support_applied"
                ),
                "rank_notional_profile_name": trade.get(
                    "rank1_score_isolation_profile_name"
                )
                or trade.get("rank_notional_profile_name"),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _notional_by_support_profile(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(
            trade.get("front_rank_near_high_support_profile_name") or "baseline"
        )
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
    selected = _apply_front_rank_near_high_support(
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
            row for row in adjusted if row.get("front_rank_near_high_support_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(adjusted),
            "front_rank_near_high_support_adjusted_trade_count": len(applied),
            "front_rank_near_high_support_adjusted_pnl": round(
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
            "notional_by_front_rank_near_high_support_profile": (
                _notional_by_support_profile(adjusted)
            ),
            "selected_trades": _selected_trade_rows(adjusted),
        }
    applied_all = [
        row for row in selected if row.get("front_rank_near_high_support_applied")
    ]
    applied_windows = {str(row.get("window")) for row in applied_all if row.get("window")}
    return {
        "variant_name": variant_name,
        "variant_type": "front_rank_near_high_support_notional_scalar",
        "near_high_min": variant.get("near_high_min"),
        "scalar": variant.get("scalar"),
        "max_queue_rank": variant.get("max_queue_rank"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "front_rank_near_high_support_adjusted_trade_count": len(applied_all),
        "front_rank_near_high_support_adjusted_windows": sorted(applied_windows),
        "single_ticker_positive_share": parent.parent.repeat.parent.parent._single_ticker_positive_share(
            selected
        ),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = parent.parent.repeat.parent.parent.parent._aggregate_delta(
        baseline_metrics,
        variant["metrics"],
    )
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["front_rank_near_high_support_adjusted_trade_count"]
        >= MIN_ADJUSTED_TRADES
        and len(variant["front_rank_near_high_support_adjusted_windows"])
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
        and delta["windows_ev_improved"] >= 3
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
        "front_rank_near_high_support_adjusted_trade_count": variant[
            "front_rank_near_high_support_adjusted_trade_count"
        ],
        "front_rank_near_high_support_adjusted_windows": variant[
            "front_rank_near_high_support_adjusted_windows"
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
        f"# {EXPERIMENT_ID} State-Surface Front-Rank Near-High Support Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `front_rank_near_high_support_notional_scalar` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Near High Min | Scalar | Max Rank | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {threshold} | {scalar} | {max_rank} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                threshold=row["near_high_min"] if row["near_high_min"] is not None else "n/a",
                scalar=row["scalar"] if row["scalar"] is not None else "n/a",
                max_rank=row["max_queue_rank"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["front_rank_near_high_support_adjusted_trade_count"],
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
                trades=sleeve[
                    "front_rank_near_high_support_adjusted_trade_count"
                ],
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
    gate2 = parent.parent.repeat.parent.parent.parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    prices = parent.parent.repeat.parent.parent.parent._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        core_results[label] = parent.parent.repeat.parent.parent.parent._load_core_result(
            window
        )

    baseline_trades = _accepted_rank3_support_trades(
        core_results=core_results,
        prices=prices,
    )
    baseline_metrics = _metrics_for_trades(
        trades=baseline_trades,
        core_results=core_results,
        prices=prices,
    )
    baseline_share = parent.parent.repeat.parent.parent._single_ticker_positive_share(
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
        for variant_name, variant in FRONT_RANK_NEAR_HIGH_VARIANTS.items()
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
                "scalar": variant["scalar"],
                "max_queue_rank": variant["max_queue_rank"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "front_rank_near_high_support_adjusted_trade_count": variant[
                    "front_rank_near_high_support_adjusted_trade_count"
                ],
                "front_rank_near_high_support_adjusted_windows": variant[
                    "front_rank_near_high_support_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(
        row for row in variants if row["variant_name"] == best["variant_name"]
    )
    delta = parent.parent.repeat.parent.parent.parent._aggregate_delta(
        baseline_metrics,
        best_payload["metrics"],
    )
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_front_rank_near_high_support_notional"
        if passed
        else "rejected_state_surface_front_rank_near_high_support_notional"
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
        "hypothesis": "When a front-ranked rotation state-surface candidate is itself close to its 60-day high, the rank-quality evidence is stronger and deserves bounded default-off paper-notional support.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Targets state-surface maturation with a new front-rank quality field, avoiding LLM soft-ranking limits, candidate-pool noise, and adjacent rank3 threshold retuning.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "front_rank_near_high_support_notional_scalar",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_near_high_min": best["near_high_min"],
            "best_scalar": best["scalar"],
            "max_queue_rank": best["max_queue_rank"],
            "profile_priority": "applies after the accepted rank-notional profile and rank3 support, before pending paper entry; applies only to queue_rank <= 2",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "rank3 near-high support scalar",
                "recent ticker repeat scalar",
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
            "baseline_artifact": parent.parent._repo_rel(
                "data/experiments/exp-20260519-004/state_surface_rank3_near_high_support_notional.json"
            ),
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": "Uses the accepted rank3 near-high support stack as Gate 1 baseline.",
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
            "minimum_baseline_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in baseline_metrics.values()
            ),
            "after_survival_rate": {
                label: best_payload["metrics"][label].get("survival_rate")
                for label in WINDOWS
            },
            "hard_rule": "No filter or candidate gate changed; only queue_rank <= 2 paper notional changes.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260519-004": "Accepted rank-3 near-high support; this experiment freezes it and tests front-rank own near-high confirmation, not rank3 threshold/scalar retuning.",
            "exp-20260519-003": "Accepted rank-1 score-isolation; this experiment does not change score-gap thresholds or profiles.",
            "exp-20260518-027": "Accepted rank-1 ret60 residual; this experiment does not change ret60 thresholds or profiles.",
            "anti_repeat": "Not an adjacent score-gap, ret20, ret60, sector-cohesion, repeat-lookback, candidate-pool, or LLM soft-ranking retry.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this deterministic rank-quality field is replayable from OHLCV-derived near-high metadata.",
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
            "Front-rank near-high support improved the default-off state-surface paper overlay in all three windows while staying paper-only and production-visible."
            if passed
            else "Front-rank near-high support did not clear Gate 4; keep the accepted rank3-support stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata; keep forward tail/concentration monitoring before any live adapter work."
            if passed
            else "Do not retry nearby front-rank near-high scalars without forward evidence or a distinct quality field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: queue_rank <= 2 candidates close to 60-day highs indicate stronger front-rank continuation quality and deserve bounded paper-notional support.",
            "2_history_check": "Prior accepted work covered score-expansion, repeat, rank1 isolation, and rank3 queue-depth support. No logged experiment used front-rank own near-high support.",
            "3_single_causal_variable": "front_rank_near_high_support_notional_scalar",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, all three windows EV-positive, zero EV-regressed windows, adjusted trades >=5 across all 3 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            parent.parent._repo_rel(Path(__file__)),
            parent.parent._repo_rel(OUT_JSON),
            parent.parent._repo_rel(LOG_JSON),
            parent.parent._repo_rel(TICKET_JSON),
            parent.parent._repo_rel(ARTIFACT_MD),
            parent.parent._repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
        ],
    }
    return parent.parent._safe(payload)


def main() -> None:
    payload = build_payload()
    parent.parent._write_json(OUT_JSON, payload)
    parent.parent._write_json(LOG_JSON, payload)
    parent.parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface front-rank near-high support notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": parent.parent._repo_rel(OUT_JSON),
            "summary": (
                f"Front-rank near-high scalar {payload['parameters']['best_scalar']} "
                f"changed aggregate EV {payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
                f"and PnL ${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    parent.parent._upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
