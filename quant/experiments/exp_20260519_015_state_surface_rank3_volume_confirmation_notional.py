"""exp-20260519-015: state-surface rank-3 volume confirmation notional.

Alpha search. Freezes the accepted state-surface paper stack through
exp-20260519-006, then tests one production-visible allocation variable:
queue-rank 3 candidates with own volume confirmation receive a bounded
default-off paper-notional scalar.

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


EXPERIMENT_ID = "exp-20260519-015"
EXPERIMENT_SLUG = "state_surface_rank3_volume_confirmation_notional"

REPO_ROOT = prev.REPO_ROOT
WINDOWS = prev.WINDOWS
BASELINE_VARIANT = "accepted_rank2_near_high_support_notional"
ACCEPTED_RANK2_VARIANT = "rank2_near_high_ge_0975_scalar_150"
MIN_SELECTED_TRADES = prev.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 5
MIN_ADJUSTED_WINDOWS = 3
MAX_DRAWDOWN_WORSE = prev.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = prev.MAX_SINGLE_TICKER_POSITIVE_SHARE
RULE_VERSION = "state_surface_rank3_volume_confirmation_notional_v1"

DOC_HELPERS = prev.DOC_HELPERS
CORE_HELPERS = prev.CORE_HELPERS
CONCENTRATION_HELPERS = prev.CONCENTRATION_HELPERS

RANK3_VOLUME_CONFIRMATION_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "volume_min": None,
                "scalar": None,
                "target_queue_rank": 3,
                "aggression_order": 0,
                "description": "accepted stack through rank-2 near-high support",
            },
        ),
        (
            "rank3_volume_ge_100_scalar_125",
            {
                "volume_min": 1.00,
                "scalar": 1.25,
                "target_queue_rank": 3,
                "aggression_order": 1,
                "description": "rank 3 volume ratio >= 1.00 receives 25% support",
            },
        ),
        (
            "rank3_volume_ge_100_scalar_150",
            {
                "volume_min": 1.00,
                "scalar": 1.50,
                "target_queue_rank": 3,
                "aggression_order": 2,
                "description": "rank 3 volume ratio >= 1.00 receives 50% support",
            },
        ),
        (
            "rank3_volume_ge_110_scalar_125",
            {
                "volume_min": 1.10,
                "scalar": 1.25,
                "target_queue_rank": 3,
                "aggression_order": 3,
                "description": "rank 3 volume ratio >= 1.10 receives 25% support",
            },
        ),
        (
            "rank3_volume_ge_110_scalar_150",
            {
                "volume_min": 1.10,
                "scalar": 1.50,
                "target_queue_rank": 3,
                "aggression_order": 4,
                "description": "rank 3 volume ratio >= 1.10 receives 50% support",
            },
        ),
        (
            "rank3_volume_ge_120_scalar_125",
            {
                "volume_min": 1.20,
                "scalar": 1.25,
                "target_queue_rank": 3,
                "aggression_order": 5,
                "description": "rank 3 volume ratio >= 1.20 receives 25% support",
            },
        ),
        (
            "rank3_volume_ge_120_scalar_150",
            {
                "volume_min": 1.20,
                "scalar": 1.50,
                "target_queue_rank": 3,
                "aggression_order": 6,
                "description": "rank 3 volume ratio >= 1.20 receives 50% support",
            },
        ),
        (
            "rank3_volume_ge_130_scalar_125",
            {
                "volume_min": 1.30,
                "scalar": 1.25,
                "target_queue_rank": 3,
                "aggression_order": 7,
                "description": "rank 3 volume ratio >= 1.30 receives 25% support",
            },
        ),
        (
            "rank3_volume_ge_130_scalar_150",
            {
                "volume_min": 1.30,
                "scalar": 1.50,
                "target_queue_rank": 3,
                "aggression_order": 8,
                "description": "rank 3 volume ratio >= 1.30 receives 50% support",
            },
        ),
        (
            "rank3_volume_ge_150_scalar_125",
            {
                "volume_min": 1.50,
                "scalar": 1.25,
                "target_queue_rank": 3,
                "aggression_order": 9,
                "description": "rank 3 volume ratio >= 1.50 receives 25% support",
            },
        ),
        (
            "rank3_volume_ge_150_scalar_150",
            {
                "volume_min": 1.50,
                "scalar": 1.50,
                "target_queue_rank": 3,
                "aggression_order": 10,
                "description": "rank 3 volume ratio >= 1.50 receives 50% support",
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


def _profile_name(volume_min: float, scalar: float) -> str:
    threshold = str(round(float(volume_min), 6)).rstrip("0").rstrip(".")
    scalar_text = str(round(float(scalar), 6)).rstrip("0").rstrip(".")
    return (
        "rank3_volume_ge_"
        f"{threshold.replace('.', 'p')}_{scalar_text.replace('.', 'p')}x"
    )


def _accepted_rank2_support_trades(
    *,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    baseline = prev._accepted_rank3_support_trades(
        core_results=core_results,
        prices=prices,
    )
    accepted_variant = prev.RANK2_NEAR_HIGH_VARIANTS[ACCEPTED_RANK2_VARIANT]
    return prev._apply_rank2_near_high_support(
        baseline,
        variant_name=ACCEPTED_RANK2_VARIANT,
        variant=accepted_variant,
    )


def _apply_rank3_volume_confirmation(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    threshold = _float(variant.get("volume_min"))
    scalar = _float(variant.get("scalar"))
    target_rank = int(variant.get("target_queue_rank") or 3)
    adjusted: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        features = dict(row.get("features") or {})
        row["features"] = features
        queue_rank = int(row.get("queue_rank") or row.get("rank") or 999)
        volume_ratio = _float(features.get("volume_ratio_20"))
        applies = (
            variant_name != BASELINE_VARIANT
            and threshold is not None
            and scalar is not None
            and queue_rank == target_rank
            and volume_ratio is not None
            and volume_ratio >= threshold
        )

        row["rank3_volume_confirmation_variant"] = variant_name
        row["rank3_volume_confirmation_rule_version"] = RULE_VERSION
        row["rank3_volume_confirmation_volume_ratio_20"] = volume_ratio
        row["rank3_volume_confirmation_target_queue_rank"] = target_rank
        row["rank3_volume_confirmation_min"] = threshold
        row["rank3_volume_confirmation_configured_scalar"] = scalar
        row["rank3_volume_confirmation_scalar"] = scalar if applies else None
        row["rank3_volume_confirmation_applied"] = bool(applies)
        row["rank3_volume_confirmation_profile_name"] = (
            _profile_name(threshold, scalar)
            if variant_name != BASELINE_VARIANT
            and threshold is not None
            and scalar is not None
            else None
        )
        row["rank3_volume_confirmation_base_multiplier"] = _float(
            row.get("rank_notional_multiplier")
        )
        row["rank_notional_rank3_volume_confirmation_rule_version"] = RULE_VERSION

        if applies:
            base_notional = float(row.get("notional") or 0.0)
            new_notional = round(base_notional * float(scalar), 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["rank3_volume_confirmation_base_notional"] = base_notional
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
    return prev._metrics_for_trades(
        trades=trades,
        core_results=core_results,
        prices=prices,
    )


def _sector(trade: dict[str, Any]) -> str:
    return prev._sector(trade)


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "sector": _sector(trade),
                "window": trade.get("window"),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "queue_rank": trade.get("queue_rank"),
                "candidate_breadth": trade.get("candidate_breadth"),
                "score": trade.get("score"),
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
                "rank3_volume_confirmation_min": trade.get(
                    "rank3_volume_confirmation_min"
                ),
                "rank3_volume_confirmation_scalar": trade.get(
                    "rank3_volume_confirmation_scalar"
                ),
                "rank3_volume_confirmation_profile_name": trade.get(
                    "rank3_volume_confirmation_profile_name"
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


def _notional_by_volume_profile(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(trade.get("rank3_volume_confirmation_profile_name") or "baseline")
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
    selected = _apply_rank3_volume_confirmation(
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
            row for row in adjusted if row.get("rank3_volume_confirmation_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(adjusted),
            "rank3_volume_confirmation_adjusted_trade_count": len(applied),
            "rank3_volume_confirmation_adjusted_pnl": round(
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
            "notional_by_rank3_volume_confirmation_profile": (
                _notional_by_volume_profile(adjusted)
            ),
            "selected_trades": _selected_trade_rows(adjusted),
        }
    applied_all = [
        row for row in selected if row.get("rank3_volume_confirmation_applied")
    ]
    applied_windows = {str(row.get("window")) for row in applied_all if row.get("window")}
    return {
        "variant_name": variant_name,
        "variant_type": "rank3_volume_confirmation_notional_profile",
        "volume_min": variant.get("volume_min"),
        "scalar": variant.get("scalar"),
        "target_queue_rank": variant.get("target_queue_rank"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "rank3_volume_confirmation_adjusted_trade_count": len(applied_all),
        "rank3_volume_confirmation_adjusted_windows": sorted(applied_windows),
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
        variant["rank3_volume_confirmation_adjusted_trade_count"]
        >= MIN_ADJUSTED_TRADES
        and len(variant["rank3_volume_confirmation_adjusted_windows"])
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
        "rank3_volume_confirmation_adjusted_trade_count": variant[
            "rank3_volume_confirmation_adjusted_trade_count"
        ],
        "rank3_volume_confirmation_adjusted_windows": variant[
            "rank3_volume_confirmation_adjusted_windows"
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
        f"# {EXPERIMENT_ID} State-Surface Rank-3 Volume Confirmation Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `rank3_volume_confirmation_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Volume Min | Scalar | Target Rank | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {threshold} | {scalar} | {rank} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                threshold=(
                    row["volume_min"] if row["volume_min"] is not None else "n/a"
                ),
                scalar=row["scalar"] if row["scalar"] is not None else "n/a",
                rank=row["target_queue_rank"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"][
                    "rank3_volume_confirmation_adjusted_trade_count"
                ],
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
                trades=sleeve["rank3_volume_confirmation_adjusted_trade_count"],
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

    baseline_trades = _accepted_rank2_support_trades(
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
        for variant_name, variant in RANK3_VOLUME_CONFIRMATION_VARIANTS.items()
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
                "volume_min": variant["volume_min"],
                "scalar": variant["scalar"],
                "target_queue_rank": variant["target_queue_rank"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "rank3_volume_confirmation_adjusted_trade_count": variant[
                    "rank3_volume_confirmation_adjusted_trade_count"
                ],
                "rank3_volume_confirmation_adjusted_windows": variant[
                    "rank3_volume_confirmation_adjusted_windows"
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
        "accepted_default_off_state_surface_rank3_volume_confirmation_notional"
        if passed
        else "rejected_state_surface_rank3_volume_confirmation_notional"
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
        "hypothesis": "Rank-3 state-surface candidates with volume confirmation are lower-depth continuation alternatives and deserve bounded default-off paper-notional support.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Continues state-surface maturation with an OHLCV-confirmed rank-depth field, avoids LLM soft-ranking data limits, and avoids noisy candidate-pool expansion.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "rank3_volume_confirmation_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_volume_min": best["volume_min"],
            "best_scalar": best["scalar"],
            "target_queue_rank": best["target_queue_rank"],
            "profile_priority": "applies after accepted rank-notional, recent-repeat, rank3 near-high, and rank2 near-high profiles; applies only to queue_rank == 3",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "rank3 near-high support scalar",
                "rank2 near-high support scalar",
                "SEC negative-language/reaction scalars rejected earlier today",
                "candidate-pool expansion rejected earlier today",
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
                "data/experiments/exp-20260519-006/state_surface_rank2_near_high_support_notional.json"
            ),
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": "Uses the accepted rank2 near-high support stack as Gate 1 baseline.",
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "queue_rank",
                "features.volume_ratio_20",
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
            "hard_rule": "No filter or candidate gate changed; only queue_rank == 3 paper notional changes.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260519-006": "Accepted rank-2 near-high support; this experiment freezes it and tests rank-3 own volume confirmation only.",
            "exp-20260519-005": "Rejected front-rank near-high support; this experiment does not touch queue_rank 1/2 near-high logic.",
            "exp-20260519-013": "Rejected SEC negative-language confirmed reaction; this experiment avoids the SEC/LLM-limited path.",
            "exp-20260519-014": "Rejected AI infra pilot segment shadow; this experiment avoids candidate-pool expansion without PIT breadth.",
            "anti_repeat": "Not a near-high threshold retune, score-gap, ret20, ret60, sector-cohesion, repeat-lookback, SEC text, candidate-pool, or LLM soft-ranking retry.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this deterministic field is replayable from existing OHLCV-derived volume_ratio_20 metadata.",
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
            "Rank-3 volume confirmation improved the default-off state-surface paper overlay in all three windows while staying paper-only and production-visible."
            if passed
            else "Rank-3 volume confirmation did not clear Gate 4; keep the accepted rank2-support stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata; keep forward tail/concentration monitoring before any live adapter work."
            if passed
            else "Do not retry nearby rank3 volume profiles without forward evidence or a distinct quality field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: queue_rank == 3 candidates with volume_ratio_20 >= 1.10 indicate confirmed participation and deserve bounded paper-notional support.",
            "2_history_check": "Prior accepted work covered rank3 near-high and rank2 near-high support; current failed work covered SEC text and candidate-pool expansion, so this tests a distinct OHLCV confirmation field.",
            "3_single_causal_variable": "rank3_volume_confirmation_notional_profile",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, all three windows EV-positive, zero EV-regressed windows, adjusted trades >=5 across all 3 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
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
            "title": "State-surface rank-3 volume confirmation notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": DOC_HELPERS._repo_rel(OUT_JSON),
            "summary": (
                f"Rank-3 volume profile {payload['parameters']['best_variant']} "
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
