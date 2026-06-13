"""exp-20260612-007: state-surface expiry-conditional near-high hold extension.

Alpha search (exit_policy). Freezes the accepted state-surface default-off
paper stack through exp-20260520-001, then tests one predeclared decision
hypothesis: a position that reaches its fixed 20-trading-day hold expiry while
its close is still at or above a threshold fraction of its trailing 60-session
maximum close gets its paper hold extended by a fixed number of trading days,
then exits at close under the unchanged cost model. Capacity (max 3 active
positions) is re-simulated so extensions that would have blocked later entries
are charged for the blocked entries.

Anti-repeat boundary: exp-20260518-001 rejected all fixed hold horizons
{5,10,15,20,25,30} and demanded a different production-visible discriminator.
This experiment does not retune the global hold; the discriminator is the
PIT near-high state measured only on the expiry session, a field the daily
sleeve can compute from the same OHLCV it already consumes.

Entries, candidate eligibility, queue ranking, notional profiles, costs,
core strategy behavior, LLM/news, and live/default orders are unchanged.

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


EXPERIMENT_ID = "exp-20260612-007"
EXPERIMENT_SLUG = "state_surface_expiry_near_high_extension"
BASELINE_EXPERIMENT_ID = "exp-20260520-001"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260520_001_state_surface_low_extension_support_notional as baseline_exp  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402


prev = baseline_exp.prev
WINDOWS = baseline_exp.WINDOWS
BASELINE_VARIANT = "accepted_low_extension_support_notional"
RULE_VERSION = "state_surface_expiry_near_high_hold_extension_v1"
MIN_SELECTED_TRADES = baseline_exp.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 8
MIN_ADJUSTED_WINDOWS = 2
MIN_EV_IMPROVED_WINDOWS = 2
HARD_EV_LIFT_PCT = 0.10  # AGENTS.md state_surface tuning bar: aggregate EV +10%
MAX_DRAWDOWN_WORSE = baseline_exp.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = baseline_exp.MAX_SINGLE_TICKER_POSITIVE_SHARE
MAX_ACTIVE_POSITIONS = 3
NEAR_HIGH_LOOKBACK_SESSIONS = 60
MIN_NEAR_HIGH_HISTORY_SESSIONS = 20
IDENTITY_RETURN_TOLERANCE = 0.002

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260612_007_{EXPERIMENT_SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

EXTENSION_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [(BASELINE_VARIANT, {"near_high_min": None, "extension_days": None, "aggression_order": 0})]
)
for near_high_min in (0.90, 0.95, 0.975):
    for extension_days in (5, 10):
        EXTENSION_VARIANTS[
            f"near_high_ge_{str(near_high_min).replace('.', 'p')}_ext_{extension_days}d"
        ] = {
            "near_high_min": near_high_min,
            "extension_days": extension_days,
            "aggression_order": len(EXTENSION_VARIANTS),
            "description": (
                "positions whose expiry close is >= "
                f"{near_high_min:.3f}x trailing 60-session max close hold "
                f"{extension_days} extra trading days"
            ),
        }


def _round(value: Any, digits: int = 6) -> float | None:
    number = prev._float(value)
    if number is None:
        return None
    return round(number, digits)


def _ticker_rows(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in (prices.get(str(ticker).upper()) or [])
        if row.get("close") is not None
    ]


def _near_high_ratio_at(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    day: str,
) -> float | None:
    """Close-on-day divided by trailing 60-session max close, PIT at day."""
    rows = [row for row in _ticker_rows(prices, ticker) if row["date"] <= day]
    if not rows or rows[-1]["date"] != day:
        return None
    if len(rows) < MIN_NEAR_HIGH_HISTORY_SESSIONS:
        return None
    window = rows[-NEAR_HIGH_LOOKBACK_SESSIONS:]
    max_close = max(float(row["close"]) for row in window)
    if max_close <= 0:
        return None
    return float(rows[-1]["close"]) / max_close


def _extended_exit_date(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    expiry_day: str,
    extension_days: int,
    window_end: str,
) -> str:
    rows = _ticker_rows(prices, ticker)
    dates = [row["date"] for row in rows]
    if expiry_day not in dates:
        return expiry_day
    start = dates.index(expiry_day)
    target = min(start + int(extension_days), len(dates) - 1)
    while target > start and dates[target] > window_end:
        target -= 1
    return dates[target]


def _recompute_returns(
    row: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
    exit_day: str,
) -> tuple[float, float] | None:
    entry_open = prev._float(row.get("entry_open"))
    if entry_open is None or entry_open <= 0:
        return None
    exit_close = prev._close_on_or_before(prices, str(row["ticker"]), exit_day)
    if exit_close is None or exit_close <= 0:
        return None
    gross = exit_close / entry_open - 1.0
    net = gross - float(ROUND_TRIP_COST_PCT)
    return gross, net


def _capacity_filter(
    trades: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Replay sleeve capacity with (possibly extended) exits.

    Mirrors the daily sleeve order of operations: expiring positions close
    before same-day entries fill, so an exit on the entry date frees capacity.
    """
    ordered = sorted(
        trades,
        key=lambda row: (str(row.get("entry_date") or ""), int(row.get("queue_rank") or 99)),
    )
    active_exits: list[str] = []
    kept: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in ordered:
        entry_date = str(row.get("entry_date") or "")
        active_exits = [day for day in active_exits if day > entry_date]
        if len(active_exits) >= MAX_ACTIVE_POSITIONS:
            blocked.append(row)
            continue
        kept.append(row)
        active_exits.append(str(row.get("exit_date") or ""))
    return kept, blocked


def _apply_extension(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
    window_end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    near_high_min = prev._float(variant.get("near_high_min"))
    extension_days = variant.get("extension_days")
    adjusted: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        row["features"] = dict(row.get("features") or {})
        row["expiry_extension_variant"] = variant_name
        row["expiry_extension_rule_version"] = RULE_VERSION
        ratio = _near_high_ratio_at(prices, str(row["ticker"]), str(row["exit_date"]))
        row["expiry_near_high_ratio"] = _round(ratio)
        qualifies = (
            variant_name != BASELINE_VARIANT
            and near_high_min is not None
            and extension_days is not None
            and ratio is not None
            and ratio >= near_high_min
        )
        row["expiry_extension_qualified"] = bool(qualifies)
        row["expiry_extension_applied"] = False
        if qualifies:
            new_exit = _extended_exit_date(
                prices,
                str(row["ticker"]),
                str(row["exit_date"]),
                int(extension_days),
                window_end,
            )
            if new_exit != str(row["exit_date"]):
                recomputed = _recompute_returns(row, prices, new_exit)
                if recomputed is not None:
                    gross, net = recomputed
                    row["expiry_extension_applied"] = True
                    row["expiry_extension_original_exit_date"] = row["exit_date"]
                    row["expiry_extension_original_net_return_pct"] = row[
                        "net_return_pct"
                    ]
                    row["expiry_extension_original_pnl"] = row["pnl"]
                    row["exit_date"] = new_exit
                    row["gross_return_pct"] = _round(gross)
                    row["net_return_pct"] = _round(net)
                    row["pnl"] = round(float(row.get("notional") or 0.0) * net, 2)
        adjusted.append(row)
    kept, blocked = _capacity_filter(adjusted)
    for row in blocked:
        row["expiry_extension_capacity_blocked"] = True
    return kept, blocked


def _verify_identity_returns(
    trades: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Gate-2 style parity check: recomputed baseline returns match artifact."""
    worst = 0.0
    checked = 0
    mismatches: list[dict[str, Any]] = []
    for row in trades:
        recomputed = _recompute_returns(row, prices, str(row["exit_date"]))
        recorded = prev._float(row.get("net_return_pct"))
        if recomputed is None or recorded is None:
            continue
        checked += 1
        diff = abs(recomputed[1] - recorded)
        worst = max(worst, diff)
        if diff > IDENTITY_RETURN_TOLERANCE:
            mismatches.append(
                {
                    "ticker": row.get("ticker"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get("exit_date"),
                    "recorded_net_return_pct": recorded,
                    "recomputed_net_return_pct": _round(recomputed[1]),
                }
            )
    return {
        "checked_trades": checked,
        "worst_abs_net_return_diff": _round(worst),
        "tolerance": IDENTITY_RETURN_TOLERANCE,
        "mismatches": mismatches,
        "passed": not mismatches and checked > 0,
    }


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "window": trade.get("window"),
                "surface": trade.get("surface"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "queue_rank": trade.get("queue_rank"),
                "score": trade.get("score"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
                "expiry_near_high_ratio": trade.get("expiry_near_high_ratio"),
                "expiry_extension_qualified": trade.get("expiry_extension_qualified"),
                "expiry_extension_applied": trade.get("expiry_extension_applied"),
                "expiry_extension_original_exit_date": trade.get(
                    "expiry_extension_original_exit_date"
                ),
                "expiry_extension_original_net_return_pct": trade.get(
                    "expiry_extension_original_net_return_pct"
                ),
                "expiry_extension_original_pnl": trade.get(
                    "expiry_extension_original_pnl"
                ),
            }
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
    blocked_all: list[dict[str, Any]] = []
    for label, window in WINDOWS.items():
        baseline_trades = baseline_trades_by_window[label]
        selected, blocked = _apply_extension(
            baseline_trades,
            variant_name=variant_name,
            variant=variant,
            prices=prices,
            window_end=window["end"],
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
        blocked_all.extend(blocked)
        applied = [row for row in selected if row.get("expiry_extension_applied")]
        qualified = [row for row in selected if row.get("expiry_extension_qualified")]
        surface_sleeve[label] = {
            "selected_trade_count": len(selected),
            "capacity_blocked_trade_count": len(blocked),
            "expiry_extension_qualified_trade_count": len(qualified),
            "expiry_extension_adjusted_trade_count": len(applied),
            "expiry_extension_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied), 2
            ),
            "expiry_extension_adjusted_pnl_delta": round(
                sum(
                    float(row.get("pnl") or 0.0)
                    - float(row.get("expiry_extension_original_pnl") or 0.0)
                    for row in applied
                ),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in selected), 2
            ),
            "selected_trades": _selected_trade_rows(selected),
            "capacity_blocked_trades": _selected_trade_rows(blocked),
        }
    applied_all = [row for row in selected_all if row.get("expiry_extension_applied")]
    applied_windows = {
        str(row.get("window")) for row in applied_all if row.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "expiry_conditional_near_high_hold_extension",
        "near_high_min": variant.get("near_high_min"),
        "extension_days": variant.get("extension_days"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trade_count": len(selected_all),
        "capacity_blocked_trade_count": len(blocked_all),
        "expiry_extension_adjusted_trade_count": len(applied_all),
        "expiry_extension_adjusted_windows": sorted(applied_windows),
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
        variant["expiry_extension_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["expiry_extension_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    ev_lift_pct = delta.get("aggregate_ev_delta_pct")
    hard_ev_bar_passed = ev_lift_pct is not None and ev_lift_pct > HARD_EV_LIFT_PCT
    standard_passed = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and sample_guard_passed
        and adjusted_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    passed = standard_passed and hard_ev_bar_passed
    share = variant["single_ticker_positive_share"]
    return {
        "passed": passed,
        "standard_gate4_passed": standard_passed,
        "hard_ev_bar_passed": hard_ev_bar_passed,
        "hard_ev_bar_note": (
            "AGENTS.md: state_surface tuning requires aggregate EV lift > "
            f"{HARD_EV_LIFT_PCT:.0%} on the standard windows"
        ),
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_ev_delta_pct": ev_lift_pct,
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "selected_trade_count": variant["selected_trade_count"],
        "capacity_blocked_trade_count": variant["capacity_blocked_trade_count"],
        "expiry_extension_adjusted_trade_count": variant[
            "expiry_extension_adjusted_trade_count"
        ],
        "expiry_extension_adjusted_windows": variant[
            "expiry_extension_adjusted_windows"
        ],
        "sample_guard_passed": sample_guard_passed,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": share,
        "baseline_single_ticker_positive_share": baseline_share,
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
    candidates = [row for row in rows if row["variant_name"] != BASELINE_VARIANT]
    passing = [row for row in candidates if row["gate4"]["passed"]]
    pool = passing if passing else candidates
    return max(
        pool,
        key=lambda row: (
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            -row["gate4"]["max_drawdown_worse_max"],
            -row["aggression_order"],
        ),
    )


def build_payload() -> dict[str, Any]:
    gate2 = prev._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = prev._json_load(baseline_exp.OUT_JSON)
    prices = prev._load_price_map()
    baseline_metrics = baseline_payload["after_metrics"]
    baseline_trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    core_curves: dict[str, list[tuple[str, float]]] = OrderedDict()
    identity_checks: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        rows = baseline_payload["surface_sleeve"][label]["selected_trades"]
        prepared = [
            prev._prepare_trade({**row, "window": label}, prices) for row in rows
        ]
        baseline_trades_by_window[label] = prepared
        identity_checks[label] = _verify_identity_returns(prepared, prices)
        _, baseline_blocked = _capacity_filter(prepared)
        identity_checks[label]["baseline_capacity_blocked"] = len(baseline_blocked)
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

    identity_passed = all(row["passed"] for row in identity_checks.values()) and all(
        row["baseline_capacity_blocked"] == 0 for row in identity_checks.values()
    )
    if not identity_passed:
        raise RuntimeError(
            "Baseline identity parity failed: "
            + json.dumps(identity_checks, sort_keys=True)
        )

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
        for name, variant in EXTENSION_VARIANTS.items()
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
                "extension_days": variant["extension_days"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "capacity_blocked_trade_count": variant[
                    "capacity_blocked_trade_count"
                ],
                "expiry_extension_adjusted_trade_count": variant[
                    "expiry_extension_adjusted_trade_count"
                ],
                "expiry_extension_adjusted_windows": variant[
                    "expiry_extension_adjusted_windows"
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
        "accepted_default_off_state_surface_expiry_near_high_extension"
        if passed
        else "rejected_state_surface_expiry_near_high_extension"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "hypothesis": (
            "State-surface paper positions still near their trailing 60-session "
            "high at fixed 20-day hold expiry carry unfinished right-tail "
            "momentum; an expiry-conditional bounded hold extension captures "
            "post-expiry continuation without changing entries, ranking, "
            "sizing, or live orders."
        ),
        "alpha_hypothesis": {
            "category": "exit_policy",
            "entry_exit_ranking_or_allocation": "default-off paper exit lifecycle",
            "playbook_alignment": (
                "Uses a new production-visible PIT discriminator "
                "(near-high state on the expiry session) instead of the "
                "rejected fixed hold horizons of exp-20260518-001; "
                "default-off paper only."
            ),
        },
        "change_type": "default_off_paper_exit_policy",
        "changed_variable": "expiry_conditional_near_high_hold_extension",
        "trial_family": "state_surface_exit_lifecycle",
        "trial_variant_id": RULE_VERSION,
        "component": "quant/state_surface_sleeve.py (only if accepted)",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_near_high_min": best["near_high_min"],
            "best_extension_days": best["extension_days"],
            "near_high_lookback_sessions": NEAR_HIGH_LOOKBACK_SESSIONS,
            "min_near_high_history_sessions": MIN_NEAR_HIGH_HISTORY_SESSIONS,
            "max_active_positions": MAX_ACTIVE_POSITIONS,
            "capacity_semantics": (
                "expiring positions close before same-day entries fill; "
                "entries arriving while 3 extended positions are active are "
                "dropped and charged to the variant"
            ),
            "condition_timing": (
                "evaluated once, on the expiry session close, using only "
                "prices on or before that session"
            ),
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface notional profiles",
                "state-surface base 20-day hold",
                "round-trip cost model",
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
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260520-001 baseline artifact plus default-off state-surface "
            "paper overlay replay with recomputed exits."
        ),
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
            "baseline_experiment": BASELINE_EXPERIMENT_ID,
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": (
                "Accepted exp-20260520-001 low-extension support stack is the "
                "Gate 1 baseline; identity control reproduces it."
            ),
        },
        "gate2": {
            "open_position_fields": gate2,
            "identity_return_parity": identity_checks,
            "runtime_fields": [
                "entry_date",
                "exit_date",
                "entry_open",
                "net_return_pct",
                "notional",
                "queue_rank",
                "OHLCV trailing 60-session closes at expiry",
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
            "hard_rule": (
                "No entry filter, ranking, or candidate gate changed; only the "
                "paper exit date of already-selected trades changes."
            ),
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260518-001": (
                "Rejected all fixed hold horizons {5,10,15,20,25,30}; demanded a "
                "different production-visible discriminator. This run keeps the "
                "20-day base hold and conditions a bounded extension on the "
                "expiry-session near-high state, which no prior state-surface "
                "experiment tested."
            ),
            "exp-20260512-002": (
                "SEC event sleeve hold-day retune rejected; different sleeve, "
                "reinforces that unconditional hold changes fail."
            ),
            "exp-20260520-001": "Current accepted state-surface baseline (frozen).",
            "anti_repeat": (
                "Not a fixed hold retune, not a notional/profile scalar sweep, "
                "not an entry filter; the discriminator is a new PIT exit-side "
                "field evaluated only at expiry."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "Deterministic OHLCV exit-state field; no semantic input needed."
            ),
        },
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": not passed,
            "parity_test_added": passed,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
            "default_off_paper_only": True,
            "note": (
                "If accepted, the extension must be implemented in "
                "quant/state_surface_sleeve.py _advance_open_positions with a "
                "parity test before retention; if rejected, no production "
                "surface changes."
            ),
        },
        "execution_envelope": {
            "scope": "default-off paper only, trade_enabled=False",
            "notional": "unchanged per-row event notional (~$10k base, scaled)",
            "capital_cap": "max 3 concurrent paper positions, unchanged",
            "liquidity_slippage": (
                "exit-at-close convention with shared round-trip cost; "
                "extension adds no extra round trip"
            ),
            "portfolio_displacement": (
                "extensions consume sleeve capacity; blocked entries are "
                "charged in the after-measurement"
            ),
            "kill_switch": "sleeve paper_enabled flag; no live orders exist",
            "live_readiness": (
                "not live-eligible; would require forward rows and Gate 5 "
                "checklist after acceptance"
            ),
        },
        "interpretation": (
            "Expiry-conditional near-high extension improved the default-off "
            "state-surface paper overlay enough to clear both the standard "
            "Gate 4 and the >10% aggregate EV state-surface bar."
            if passed
            else (
                "Expiry-conditional near-high extension did not clear Gate 4 "
                "plus the >10% aggregate EV state-surface bar; keep the "
                "accepted 20-day hold unchanged."
            )
        ),
        "rejection_reason": None
        if passed
        else (
            "Failed the canonical three-window state-surface paper protocol "
            "with the AGENTS.md >10% aggregate EV hard bar."
        ),
        "next_evidence_needed": (
            "Implement shared sleeve extension + parity test, then collect "
            "forward default-off rows before any activation discussion."
            if passed
            else (
                "Do not retry near-high expiry extensions with nearby "
                "thresholds/extensions on these frozen windows; new evidence "
                "must come from forward closed paper rows (e.g. post-expiry "
                "continuation attribution on live snapshots) or a materially "
                "different exit-side field."
            )
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "exit_policy: expiry-session near-high state predicts "
                "post-expiry continuation worth a bounded paper hold extension."
            ),
            "2_history_check": (
                "exp-20260518-001 fixed hold sweep rejected; exp-20260512-002 "
                "SEC hold retune rejected; no prior expiry-conditional "
                "exit-state experiment on the state-surface sleeve."
            ),
            "3_single_causal_variable": "expiry_conditional_near_high_hold_extension",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; positive aggregate "
                "EV/PnL, >=2 EV-improved windows, zero regressed, adjusted "
                "trades >=8 across >=2 windows, DD drift <=0.5pp, single-ticker "
                "positive share <=50%, AND aggregate EV lift >10% per the "
                "AGENTS.md state-surface tuning bar."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260612_007_state_surface_expiry_near_high_extension.py"
            ),
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            prev._repo_rel(Path(__file__)),
            prev._repo_rel(OUT_JSON),
            prev._repo_rel(LOG_JSON),
            prev._repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
        ],
    }
    return prev._safe(payload)


def main() -> None:
    payload = build_payload()
    prev._write_json(OUT_JSON, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(
        f"{EXPERIMENT_ID} {payload['decision']} "
        f"dEV={payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
        f"({(payload['delta_metrics']['aggregate_ev_delta_pct'] or 0):+.2%}) "
        f"dPnL=${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}"
    )


if __name__ == "__main__":
    main()
