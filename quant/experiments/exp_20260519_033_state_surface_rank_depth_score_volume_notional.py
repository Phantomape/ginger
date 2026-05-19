"""exp-20260519-033: state-surface rank-depth score-volume notional.

Alpha search. Freezes the accepted state-surface paper stack through
exp-20260519-031, then tests one production-visible allocation variable:
already-selected rank-depth candidates with both absolute score quality and
volume confirmation receive a bounded paper-notional support scalar.

Core entries, exits, candidate eligibility, queue ranking, hold days, active
capacity, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260519_031_state_surface_absolute_score_support_notional as baseline_exp


EXPERIMENT_ID = "exp-20260519-033"
EXPERIMENT_SLUG = "state_surface_rank_depth_score_volume_notional"

prev = baseline_exp.prev
REPO_ROOT = baseline_exp.REPO_ROOT
WINDOWS = baseline_exp.WINDOWS
BASELINE_VARIANT = "accepted_absolute_score_support_notional"
MIN_SELECTED_TRADES = baseline_exp.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 6
MIN_ADJUSTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 3
MAX_DRAWDOWN_WORSE = baseline_exp.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = baseline_exp.MAX_SINGLE_TICKER_POSITIVE_SHARE
RULE_VERSION = "state_surface_rank_depth_score_volume_notional_v1"

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"{EXPERIMENT_SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SCORE_MIN = 0.90
VOLUME_MIN = 1.10
MIN_QUEUE_RANK = 2
MAX_QUEUE_RANK = 3

RANK_DEPTH_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [(BASELINE_VARIANT, {"scalar": None, "aggression_order": 0})]
)
for scalar in (1.025, 1.05, 1.075, 1.10, 1.125, 1.15):
    RANK_DEPTH_VARIANTS[
        f"rank_depth_score_volume_scalar_{str(scalar).replace('.', 'p')}"
    ] = {
        "scalar": scalar,
        "aggression_order": len(RANK_DEPTH_VARIANTS),
        "description": (
            "selected queue ranks 2-3 with score >= 0.90 and "
            f"volume_ratio_20 >= 1.10 receive {scalar:.3f}x notional support"
        ),
    }


def _round(value: Any, digits: int = 4) -> float | None:
    number = prev._float(value)
    if number is None:
        return None
    return round(number, digits)


def _profile_name(scalar: float | None) -> str | None:
    if scalar is None:
        return None
    scalar_text = str(round(float(scalar), 6)).rstrip("0").rstrip(".")
    return f"rank_depth_score_volume_{scalar_text.replace('.', 'p')}x"


def _score_volume_support_qualified(trade: dict[str, Any]) -> bool:
    queue_rank = int(trade.get("queue_rank") or 0)
    score = prev._float(trade.get("score"))
    volume_ratio = prev._float(trade.get("volume_ratio_20"))
    return bool(
        MIN_QUEUE_RANK <= queue_rank <= MAX_QUEUE_RANK
        and score is not None
        and score >= SCORE_MIN
        and volume_ratio is not None
        and volume_ratio >= VOLUME_MIN
    )


def _apply_score_volume_support(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    scalar = prev._float(variant.get("scalar"))
    adjusted: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        row["features"] = dict(row.get("features") or {})
        qualifies = _score_volume_support_qualified(row)
        applies = (
            variant_name != BASELINE_VARIANT
            and scalar is not None
            and qualifies
        )
        row["rank_depth_score_volume_variant"] = variant_name
        row["rank_depth_score_volume_rule_version"] = RULE_VERSION
        row["rank_notional_rank_depth_score_volume_rule_version"] = RULE_VERSION
        row["rank_depth_score_volume_applied"] = bool(applies)
        row["rank_depth_score_volume_qualified"] = bool(qualifies)
        row["rank_depth_score_volume_min_queue_rank"] = MIN_QUEUE_RANK
        row["rank_depth_score_volume_max_queue_rank"] = MAX_QUEUE_RANK
        row["rank_depth_score_volume_score"] = _round(row.get("score"), 6)
        row["rank_depth_score_volume_score_min"] = SCORE_MIN
        row["rank_depth_score_volume_volume_ratio_20"] = _round(
            row.get("volume_ratio_20"),
            6,
        )
        row["rank_depth_score_volume_volume_min"] = VOLUME_MIN
        row["rank_depth_score_volume_configured_scalar"] = _round(scalar, 6)
        row["rank_depth_score_volume_scalar"] = scalar if applies else None
        row["rank_depth_score_volume_profile_name"] = _profile_name(scalar)
        row["rank_depth_score_volume_base_multiplier"] = prev._float(
            row.get("rank_notional_multiplier")
        )
        if applies:
            base_notional = float(row.get("notional") or 0.0)
            new_notional = round(base_notional * float(scalar), 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["rank_depth_score_volume_base_notional"] = base_notional
            row["notional"] = new_notional
            row["shares"] = new_notional / entry_open
            row["pnl"] = round(new_notional * net_return, 2)
            base_multiplier = prev._float(row.get("rank_notional_multiplier"))
            if base_multiplier is not None:
                row["rank_notional_multiplier"] = round(
                    base_multiplier * float(scalar),
                    6,
                )
        adjusted.append(row)
    return adjusted


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = baseline_exp._selected_trade_rows(trades)
    for row, trade in zip(rows, trades):
        row["rank_depth_score_volume_applied"] = trade.get(
            "rank_depth_score_volume_applied"
        )
        row["rank_depth_score_volume_qualified"] = trade.get(
            "rank_depth_score_volume_qualified"
        )
        row["rank_depth_score_volume_scalar"] = trade.get(
            "rank_depth_score_volume_scalar"
        )
        row["rank_depth_score_volume_base_multiplier"] = trade.get(
            "rank_depth_score_volume_base_multiplier"
        )
        row["rank_depth_score_volume_profile_name"] = trade.get(
            "rank_depth_score_volume_profile_name"
        )
    return rows


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    baseline_payload: dict[str, Any],
    baseline_trades_by_window: dict[str, list[dict[str, Any]]],
    core_curves: dict[str, list[tuple[str, float]]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []
    for label, window in WINDOWS.items():
        baseline_trades = baseline_trades_by_window[label]
        selected = _apply_score_volume_support(
            baseline_trades,
            variant_name=variant_name,
            variant=variant,
        )
        if variant_name == BASELINE_VARIANT:
            metrics[label] = baseline_payload["after_metrics"][label]
        else:
            event_curve = prev._event_equity_curve_variable_notional(
                selected,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            metrics[label] = prev._metrics_from_core_curve(
                baseline_metrics=baseline_payload["after_metrics"][label],
                core_curve=core_curves[label],
                event_curve=event_curve,
                event_trades=selected,
                baseline_event_trades=baseline_trades,
            )
        selected_all.extend(selected)
        qualified = [
            row for row in selected if row.get("rank_depth_score_volume_qualified")
        ]
        applied = [
            row for row in selected if row.get("rank_depth_score_volume_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(selected),
            "rank_depth_score_volume_qualified_trade_count": len(qualified),
            "rank_depth_score_volume_adjusted_trade_count": len(applied),
            "rank_depth_score_volume_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied),
                2,
            ),
            "rank_depth_score_volume_qualified_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in qualified),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in selected),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for row in selected if float(row.get("pnl") or 0.0) > 0)
                / len(selected),
                4,
            )
            if selected
            else None,
            "selected_trades": _selected_trade_rows(selected),
        }
    applied_all = [
        row for row in selected_all if row.get("rank_depth_score_volume_applied")
    ]
    qualified_all = [
        row for row in selected_all if row.get("rank_depth_score_volume_qualified")
    ]
    applied_windows = {
        str(row.get("window")) for row in applied_all if row.get("window")
    }
    qualified_windows = {
        str(row.get("window")) for row in qualified_all if row.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "rank_depth_score_volume_notional_profile",
        "score_min": SCORE_MIN,
        "volume_min": VOLUME_MIN,
        "min_queue_rank": MIN_QUEUE_RANK,
        "max_queue_rank": MAX_QUEUE_RANK,
        "scalar": variant.get("scalar"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "rank_depth_score_volume_qualified_trade_count": len(qualified_all),
        "rank_depth_score_volume_qualified_windows": sorted(qualified_windows),
        "rank_depth_score_volume_adjusted_trade_count": len(applied_all),
        "rank_depth_score_volume_adjusted_windows": sorted(applied_windows),
        "single_ticker_positive_share": prev._single_ticker_positive_share(
            selected_all
        ),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = prev._aggregate_delta(baseline_metrics, variant["metrics"])
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["rank_depth_score_volume_adjusted_trade_count"]
        >= MIN_ADJUSTED_TRADES
        and len(variant["rank_depth_score_volume_adjusted_windows"])
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
        "rank_depth_score_volume_adjusted_trade_count": variant[
            "rank_depth_score_volume_adjusted_trade_count"
        ],
        "rank_depth_score_volume_adjusted_windows": variant[
            "rank_depth_score_volume_adjusted_windows"
        ],
        "rank_depth_score_volume_qualified_trade_count": variant[
            "rank_depth_score_volume_qualified_trade_count"
        ],
        "rank_depth_score_volume_qualified_windows": variant[
            "rank_depth_score_volume_qualified_windows"
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
        f"# {EXPERIMENT_ID} State-Surface Rank-Depth Score-Volume Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `rank_depth_score_volume_notional_scalar` for already-selected default-off state-surface paper candidates.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {scalar} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                scalar=row["scalar"] if row["scalar"] is not None else "n/a",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["rank_depth_score_volume_adjusted_trade_count"],
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
                trades=sleeve["rank_depth_score_volume_adjusted_trade_count"],
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


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(prev._safe(payload), sort_keys=True)
    payload_id = payload.get("experiment_id")
    temp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    replaced = False

    with temp_path.open("w", encoding="utf-8") as out:
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as src:
                for existing in src:
                    text = existing.rstrip("\r\n")
                    if not text.strip():
                        continue
                    try:
                        row = json.loads(text)
                    except json.JSONDecodeError:
                        out.write(text + "\n")
                        continue
                    if row.get("experiment_id") == payload_id:
                        if not replaced:
                            out.write(line + "\n")
                            replaced = True
                        continue
                    out.write(text + "\n")
        if not replaced:
            out.write(line + "\n")

    temp_path.replace(path)


def build_payload() -> dict[str, Any]:
    gate2 = prev._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = prev._json_load(baseline_exp.OUT_JSON)
    prices = prev._load_price_map()
    baseline_metrics = baseline_payload["after_metrics"]
    baseline_trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    core_curves: dict[str, list[tuple[str, float]]] = OrderedDict()
    for label, window in WINDOWS.items():
        rows = baseline_payload["surface_sleeve"][label]["selected_trades"]
        prepared = [prev._prepare_trade({**row, "window": label}, prices) for row in rows]
        baseline_trades_by_window[label] = prepared
        baseline_event_curve = prev._event_equity_curve_variable_notional(
            prepared,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        event_by_day = {
            row["date"]: float(row["event_pnl"]) for row in baseline_event_curve
        }
        combined_curve = [
            (str(day), float(equity))
            for day, equity in baseline_metrics[label]["combined_equity_curve"]
        ]
        core_curves[label] = [
            (day, round(equity - event_by_day.get(day, 0.0), 2))
            for day, equity in combined_curve
        ]

    baseline_trades_all = [
        row for rows in baseline_trades_by_window.values() for row in rows
    ]
    baseline_share = prev._single_ticker_positive_share(baseline_trades_all)
    variants = [
        _variant_payload(
            variant_name=name,
            variant=variant,
            baseline_payload=baseline_payload,
            baseline_trades_by_window=baseline_trades_by_window,
            core_curves=core_curves,
            prices=prices,
        )
        for name, variant in RANK_DEPTH_VARIANTS.items()
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
                "score_min": variant["score_min"],
                "volume_min": variant["volume_min"],
                "min_queue_rank": variant["min_queue_rank"],
                "max_queue_rank": variant["max_queue_rank"],
                "scalar": variant["scalar"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "rank_depth_score_volume_qualified_trade_count": variant[
                    "rank_depth_score_volume_qualified_trade_count"
                ],
                "rank_depth_score_volume_qualified_windows": variant[
                    "rank_depth_score_volume_qualified_windows"
                ],
                "rank_depth_score_volume_adjusted_trade_count": variant[
                    "rank_depth_score_volume_adjusted_trade_count"
                ],
                "rank_depth_score_volume_adjusted_windows": variant[
                    "rank_depth_score_volume_adjusted_windows"
                ],
                "single_ticker_positive_share": variant[
                    "single_ticker_positive_share"
                ],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(
        row for row in variants if row["variant_name"] == best["variant_name"]
    )
    delta = prev._aggregate_delta(baseline_metrics, best_payload["metrics"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_rank_depth_score_volume_notional"
        if passed
        else "rejected_state_surface_rank_depth_score_volume_notional"
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
        "hypothesis": "When selected state-surface rank-depth candidates still have both high absolute composite score and volume confirmation, the lower queue rank may understate depth quality; a bounded paper-notional support scalar can improve EV without changing eligibility or live execution.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Uses a new deterministic rank-depth quality interaction rather than a nearby absolute-score threshold retry, LLM soft-ranking, or candidate-pool expansion.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "rank_depth_score_volume_notional_scalar",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_scalar": best["scalar"],
            "score_min": SCORE_MIN,
            "volume_ratio_20_min": VOLUME_MIN,
            "min_queue_rank": MIN_QUEUE_RANK,
            "max_queue_rank": MAX_QUEUE_RANK,
            "condition": "selected state-surface paper candidate queue rank 2-3, score >= 0.90, and volume_ratio_20 >= 1.10",
            "profile_priority": "applies after accepted absolute-score support in the default-off paper notional stack",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "absolute-score support scalar",
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
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows; accepted exp-20260519-031 baseline artifact plus default-off state-surface paper overlay replay.",
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
            "baseline_artifact": prev._repo_rel(baseline_exp.OUT_JSON),
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": "Uses accepted exp-20260519-031 absolute-score support notional as Gate 1 baseline.",
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "queue_rank",
                "score",
                "volume_ratio_20",
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
            "hard_rule": "No filter, ranking, or candidate gate changed; only paper notional changes for already-selected trades.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260519-031": "Accepted absolute-score support; this experiment freezes it and adds volume-confirmed rank-depth quality rather than retuning the score threshold or scalar.",
            "exp-20260519-021": "Accepted rank-2 volume confirmation; this experiment uses volume only as a confluence field with absolute score across selected rank-depth candidates.",
            "anti_repeat": "Not a queue-lag scalar retry, global capacity retune, absolute-score threshold retry, candidate-pool expansion, SEC text scalar, or LLM soft-ranking experiment.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this tests replayable deterministic score and volume fields.",
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
            "Score-volume rank-depth support improved the default-off state-surface paper overlay without changing core trades, filters, ranking, or live/default orders."
            if passed
            else "Score-volume rank-depth support did not clear Gate 4; keep the accepted absolute-score stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata; keep forward tail/concentration monitoring before any live adapter work."
            if passed
            else "Do not retry nearby score-volume rank-depth support without a broader sample or a distinct risk/concentration field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: rank-depth state-surface candidates with both accepted absolute score and volume confirmation may deserve more paper capital.",
            "2_history_check": "Related score-only and volume-only state-surface fields were accepted, while nearby queue/capacity retunes are frozen. This tests their rank-depth confluence, not a threshold retune or new pool.",
            "3_single_causal_variable": "rank_depth_score_volume_notional_scalar",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, all three EV-improved windows, zero EV-regressed windows, adjusted trades >=6 across all 3 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            prev._repo_rel(Path(__file__)),
            prev._repo_rel(OUT_JSON),
            prev._repo_rel(LOG_JSON),
            prev._repo_rel(TICKET_JSON),
            prev._repo_rel(ARTIFACT_MD),
            prev._repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
        ],
    }
    return prev._safe(payload)


def main() -> None:
    payload = build_payload()
    prev._write_json(OUT_JSON, payload)
    prev._write_json(LOG_JSON, payload)
    prev._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface rank-depth score-volume notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": prev._repo_rel(OUT_JSON),
            "summary": (
                f"Score-volume rank-depth scalar {payload['parameters']['best_variant']} "
                f"changed aggregate EV {payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
                f"and PnL ${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(
        f"{EXPERIMENT_ID} {payload['decision']} "
        f"dEV={payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
        f"dPnL=${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}"
    )


if __name__ == "__main__":
    main()
