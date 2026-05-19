"""exp-20260519-025: state-surface rank-1 dominance crowding penalty.

Alpha search. Freezes the accepted state-surface paper stack through
exp-20260519-024, then tests one production-visible crowding-control variable:
already-selected dominant rank-1 candidates receive a bounded default-off
paper-notional haircut instead of another support scalar.

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

import exp_20260519_024_state_surface_broad_breadth_notional as prev


EXPERIMENT_ID = "exp-20260519-025"
EXPERIMENT_SLUG = "state_surface_rank1_dominance_crowding_penalty_notional"

REPO_ROOT = prev.REPO_ROOT
WINDOWS = prev.WINDOWS
BASELINE_VARIANT = "accepted_broad_breadth_support_notional"
ACCEPTED_BROAD_BREADTH_VARIANT = "broad_breadth_scalar_110"
MIN_SELECTED_TRADES = prev.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 6
MIN_ADJUSTED_WINDOWS = 2
MIN_EV_IMPROVED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = prev.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = prev.MAX_SINGLE_TICKER_POSITIVE_SHARE
RULE_VERSION = "state_surface_rank1_dominance_crowding_penalty_notional_v1"

DOC_HELPERS = prev.DOC_HELPERS
CORE_HELPERS = prev.CORE_HELPERS
CONCENTRATION_HELPERS = prev.CONCENTRATION_HELPERS

DOMINANCE_CROWDING_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "lead_min": None,
                "score_gap_min": None,
                "scalar": None,
                "aggression_order": 0,
                "description": "accepted stack through broad-breadth support",
            },
        ),
        (
            "rank1_dominance_crowding_scalar_095",
            {
                "lead_min": 0.15,
                "score_gap_min": 0.45,
                "scalar": 0.95,
                "aggression_order": 1,
                "description": "dominant rank-1 candidates receive a 5% haircut",
            },
        ),
        (
            "rank1_dominance_crowding_scalar_090",
            {
                "lead_min": 0.15,
                "score_gap_min": 0.45,
                "scalar": 0.90,
                "aggression_order": 2,
                "description": "dominant rank-1 candidates receive a 10% haircut",
            },
        ),
        (
            "rank1_dominance_crowding_scalar_085",
            {
                "lead_min": 0.15,
                "score_gap_min": 0.45,
                "scalar": 0.85,
                "aggression_order": 3,
                "description": "dominant rank-1 candidates receive a 15% haircut",
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


def _profile_name(lead_min: float, score_gap_min: float, scalar: float) -> str:
    lead_text = str(round(float(lead_min), 6)).rstrip("0").rstrip(".")
    gap_text = str(round(float(score_gap_min), 6)).rstrip("0").rstrip(".")
    scalar_text = str(round(float(scalar), 6)).rstrip("0").rstrip(".")
    return (
        f"rank1_dominance_ge_{lead_text.replace('.', 'p')}_"
        f"score_gap_ge_{gap_text.replace('.', 'p')}_"
        f"crowding_{scalar_text.replace('.', 'p')}x"
    )


def _accepted_broad_breadth_trades(
    *,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    baseline = prev._accepted_top3_ret5_trades(
        core_results=core_results,
        prices=prices,
    )
    accepted_variant = prev.BROAD_BREADTH_VARIANTS[ACCEPTED_BROAD_BREADTH_VARIANT]
    return prev._apply_broad_breadth_support(
        baseline,
        variant_name=ACCEPTED_BROAD_BREADTH_VARIANT,
        variant=accepted_variant,
    )


def _apply_rank1_dominance_crowding_penalty(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    lead_min = _float(variant.get("lead_min"))
    score_gap_min = _float(variant.get("score_gap_min"))
    scalar = _float(variant.get("scalar"))
    adjusted: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        features = dict(row.get("features") or {})
        row["features"] = features
        queue_rank = int(row.get("queue_rank") or 0)
        rank1_ret20 = _float(row.get("rank1_ret20_excess_spy"))
        rank2_ret20 = _float(row.get("rank2_ret20_excess_spy"))
        score_gap = _float(row.get("score_top_to_second_gap"))
        lead = (
            rank1_ret20 - rank2_ret20
            if rank1_ret20 is not None and rank2_ret20 is not None
            else None
        )
        applies = bool(
            variant_name != BASELINE_VARIANT
            and scalar is not None
            and lead_min is not None
            and score_gap_min is not None
            and queue_rank == 1
            and lead is not None
            and score_gap is not None
            and lead >= lead_min
            and score_gap >= score_gap_min
        )

        row["rank1_dominance_crowding_variant"] = variant_name
        row["rank1_dominance_crowding_rule_version"] = RULE_VERSION
        row["rank1_dominance_crowding_lead_min"] = lead_min
        row["rank1_dominance_crowding_score_gap_min"] = score_gap_min
        row["rank1_dominance_crowding_rank1_ret20_excess_spy"] = rank1_ret20
        row["rank1_dominance_crowding_rank2_ret20_excess_spy"] = rank2_ret20
        row["rank1_dominance_crowding_ret20_lead"] = lead
        row["rank1_dominance_crowding_score_gap"] = score_gap
        row["rank1_dominance_crowding_configured_scalar"] = scalar
        row["rank1_dominance_crowding_scalar"] = scalar if applies else None
        row["rank1_dominance_crowding_applied"] = applies
        row["rank1_dominance_crowding_profile_name"] = (
            _profile_name(lead_min, score_gap_min, scalar)
            if variant_name != BASELINE_VARIANT
            and lead_min is not None
            and score_gap_min is not None
            and scalar is not None
            else None
        )
        row["rank1_dominance_crowding_base_multiplier"] = _float(
            row.get("rank_notional_multiplier")
        )
        row["rank_notional_rank1_dominance_crowding_rule_version"] = RULE_VERSION

        if applies:
            base_notional = float(row.get("notional") or 0.0)
            new_notional = round(base_notional * float(scalar), 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["rank1_dominance_crowding_base_notional"] = base_notional
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


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "sector": prev.prev._sector(trade),
                "window": trade.get("window"),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "queue_rank": trade.get("queue_rank"),
                "state_bucket": trade.get("state_bucket"),
                "breadth_bucket": trade.get("breadth_bucket"),
                "dispersion_bucket": trade.get("dispersion_bucket"),
                "regime": trade.get("regime"),
                "score": trade.get("score"),
                "ret5": features.get("ret5"),
                "ret20_excess_spy": features.get("ret20_excess_spy"),
                "ret60": features.get("ret60"),
                "volume_ratio_20": features.get("volume_ratio_20"),
                "rank1_ret20_excess_spy": trade.get("rank1_ret20_excess_spy"),
                "rank2_ret20_excess_spy": trade.get("rank2_ret20_excess_spy"),
                "score_top_to_second_gap": trade.get("score_top_to_second_gap"),
                "broad_breadth_support_applied": trade.get(
                    "broad_breadth_support_applied"
                ),
                "rank1_dominance_crowding_applied": trade.get(
                    "rank1_dominance_crowding_applied"
                ),
                "rank1_dominance_crowding_scalar": trade.get(
                    "rank1_dominance_crowding_scalar"
                ),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    baseline_trades: list[dict[str, Any]],
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    selected = _apply_rank1_dominance_crowding_penalty(
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
        window_trades = [row for row in selected if row.get("window") == label]
        applied = [
            row for row in window_trades if row.get("rank1_dominance_crowding_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(window_trades),
            "rank1_dominance_crowding_adjusted_trade_count": len(applied),
            "rank1_dominance_crowding_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in window_trades),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for row in window_trades if float(row.get("pnl") or 0.0) > 0)
                / len(window_trades),
                4,
            )
            if window_trades
            else None,
            "ticker_distribution": dict(
                Counter(row.get("ticker") for row in window_trades)
            ),
            "sector_distribution": dict(
                Counter(prev.prev._sector(row) for row in window_trades)
            ),
            "selected_trades": _selected_trade_rows(window_trades),
        }
    applied_all = [
        row for row in selected if row.get("rank1_dominance_crowding_applied")
    ]
    applied_windows = {
        str(row.get("window")) for row in applied_all if row.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "rank1_dominance_crowding_penalty_notional_profile",
        "lead_min": variant.get("lead_min"),
        "score_gap_min": variant.get("score_gap_min"),
        "scalar": variant.get("scalar"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "rank1_dominance_crowding_adjusted_trade_count": len(applied_all),
        "rank1_dominance_crowding_adjusted_windows": sorted(applied_windows),
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
        variant["rank1_dominance_crowding_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["rank1_dominance_crowding_adjusted_windows"])
        >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"]
        <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    passed = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
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
        "rank1_dominance_crowding_adjusted_trade_count": variant[
            "rank1_dominance_crowding_adjusted_trade_count"
        ],
        "rank1_dominance_crowding_adjusted_windows": variant[
            "rank1_dominance_crowding_adjusted_windows"
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
        "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
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
        f"# {EXPERIMENT_ID} State-Surface Rank-1 Dominance Crowding Penalty",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `rank1_dominance_crowding_penalty_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Lead Min | Gap Min | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {lead} | {gap} | {scalar} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                lead=row["lead_min"] if row["lead_min"] is not None else "n/a",
                gap=row["score_gap_min"] if row["score_gap_min"] is not None else "n/a",
                scalar=row["scalar"] if row["scalar"] is not None else "n/a",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["rank1_dominance_crowding_adjusted_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share=f"{share:.2%}" if share is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted Trades |",
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
                trades=sleeve["rank1_dominance_crowding_adjusted_trade_count"],
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

    baseline_trades = _accepted_broad_breadth_trades(
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
        for variant_name, variant in DOMINANCE_CROWDING_VARIANTS.items()
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
                "lead_min": variant["lead_min"],
                "score_gap_min": variant["score_gap_min"],
                "scalar": variant["scalar"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "rank1_dominance_crowding_adjusted_trade_count": variant[
                    "rank1_dominance_crowding_adjusted_trade_count"
                ],
                "rank1_dominance_crowding_adjusted_windows": variant[
                    "rank1_dominance_crowding_adjusted_windows"
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
        "accepted_default_off_state_surface_rank1_dominance_crowding_penalty_notional"
        if passed
        else "rejected_state_surface_rank1_dominance_crowding_penalty_notional"
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
        "hypothesis": "State-surface rank-1 candidates that already dominate both relative momentum and composite score can become crowded; a bounded paper-notional haircut may improve EV concentration without changing eligibility or live execution.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Targets playbook-ranked concentration control through a new crowding response for already-selected dominant rank-1 candidates.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "rank1_dominance_crowding_penalty_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_lead_min": best["lead_min"],
            "best_score_gap_min": best["score_gap_min"],
            "best_scalar": best["scalar"],
            "profile_priority": "evaluated on top of the accepted broad-breadth support stack; applies only to queue-rank-1 trades that satisfy the accepted dominance thresholds",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "top3 ret5 follow-through scalar",
                "broad breadth support scalar",
                "candidate pool",
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
                "data/experiments/exp-20260519-024/state_surface_broad_breadth_notional.json"
            ),
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": "Uses the accepted broad-breadth support stack as Gate 1 baseline.",
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "queue_rank",
                "rank1_ret20_excess_spy",
                "rank2_ret20_excess_spy",
                "score_top_to_second_gap",
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
            "hard_rule": "No filter or candidate gate changed; only paper notional changes for existing selected trades.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260518-023": "Accepted rank-1 dominance boosted dominant names. This experiment tests the unexplored crowding-control response on that same production-visible trigger.",
            "exp-20260519-024": "Accepted broad-breadth support is frozen as baseline; this experiment adds no new breadth or pool expansion logic.",
            "anti_repeat": "Not a ret5, breadth, near-high, volume, sector-diversity, candidate-pool, or LLM soft-ranking retry; it is a new capital-routing response to dominance crowding.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "The targeted crowding signal is deterministic and replayable from existing state-surface metadata.",
        },
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": False,
            "parity_test_added": passed,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
            "default_off_paper_only": True,
        },
        "interpretation": (
            "Rank-1 dominance crowding control improved the default-off state-surface paper overlay without changing core trades, filters, or live/default orders."
            if passed
            else "Rank-1 dominance crowding control did not clear Gate 4; keep the accepted broad-breadth stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata; keep forward tail/concentration monitoring before any live adapter work."
            if passed
            else "Do not retry nearby rank1-dominance crowding penalties without forward evidence or a materially different production-visible field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: already-selected dominant rank-1 state-surface candidates may be crowded and deserve a bounded paper-notional haircut.",
            "2_history_check": "The repo has accepted rank1 dominance support but no canonical three-window experiment testing the opposite crowding-control response on the same trigger. Dispersion remains blocked and all-market expansion was already explored/rejected.",
            "3_single_causal_variable": "rank1_dominance_crowding_penalty_notional_profile",
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
            "title": "State-surface rank-1 dominance crowding penalty",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": DOC_HELPERS._repo_rel(OUT_JSON),
            "summary": (
                f"Variant {payload['parameters']['best_variant']} changed aggregate EV "
                f"{payload['delta_metrics']['aggregate_ev_delta']:+.4f} and PnL "
                f"${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
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
