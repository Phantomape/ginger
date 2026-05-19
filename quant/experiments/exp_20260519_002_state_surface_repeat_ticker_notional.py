"""exp-20260519-002: state-surface recent ticker repeat notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
when the same ticker reappears in the state-surface sleeve within 60 calendar
days, treat the repeat as a continuation-quality field and scale the paper
notional.

Core entries, exits, candidate eligibility, queue ranking, hold days, active
capacity, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260519_001_state_surface_score_expansion_notional as parent  # noqa: E402


EXPERIMENT_ID = "exp-20260519-002"
EXPERIMENT_SLUG = "state_surface_repeat_ticker_notional"

REPO_ROOT = parent.REPO_ROOT
WINDOWS = parent.WINDOWS
BASELINE_VARIANT = "accepted_score_expansion_notional"
MIN_SELECTED_TRADES = parent.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 2
MIN_ADJUSTED_WINDOWS = 2
MAX_DRAWDOWN_WORSE = parent.MAX_DRAWDOWN_WORSE
MAX_SINGLE_TICKER_POSITIVE_SHARE = parent.MAX_SINGLE_TICKER_POSITIVE_SHARE
LOOKBACK_DAYS = 60
RULE_VERSION = "state_surface_recent_ticker_repeat_notional_v1"

REPEAT_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "scalar": None,
                "aggression_order": 0,
                "description": "current accepted score-expansion state-surface stack",
            },
        ),
        (
            "repeat_60d_dampen_0_50",
            {
                "scalar": 0.50,
                "aggression_order": 1,
                "description": "same ticker repeated within 60d receives half notional",
            },
        ),
        (
            "repeat_60d_dampen_0_75",
            {
                "scalar": 0.75,
                "aggression_order": 2,
                "description": "same ticker repeated within 60d receives 75% notional",
            },
        ),
        (
            "repeat_60d_topup_1_10",
            {
                "scalar": 1.10,
                "aggression_order": 3,
                "description": "same ticker repeated within 60d receives 10% top-up",
            },
        ),
        (
            "repeat_60d_topup_1_25",
            {
                "scalar": 1.25,
                "aggression_order": 4,
                "description": "same ticker repeated within 60d receives 25% top-up",
            },
        ),
        (
            "repeat_60d_topup_1_50",
            {
                "scalar": 1.50,
                "aggression_order": 5,
                "description": "same ticker repeated within 60d receives 50% top-up",
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


def _parse_date(value: Any) -> date | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _repeat_profile_name(scalar: float | None) -> str:
    if scalar is None:
        return "no_recent_ticker_repeat_adjustment"
    value = str(round(float(scalar), 6)).rstrip("0").rstrip(".")
    return f"recent_ticker_repeat_60d_{value.replace('.', 'p')}x"


def _base_multiplier(row: dict[str, Any]) -> float | None:
    parsed = parent.parent._float(row.get("rank_notional_multiplier"))
    if parsed is not None:
        return parsed
    notional = parent.parent._float(row.get("notional"))
    if notional is None:
        return None
    return notional / float(parent.parent.parent.base.EVENT_NOTIONAL)


def _base_profile_name(row: dict[str, Any]) -> str:
    return str(
        row.get("score_expansion_profile_name")
        or row.get("rank1_ret60_residual_profile_name")
        or row.get("top2_sector_cohesion_profile_name")
        or row.get("rank_notional_profile_name")
        or ""
    )


def _apply_recent_repeat_scalar(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    scalar: float | None,
) -> list[dict[str, Any]]:
    last_seen: dict[tuple[str, str], date] = {}
    adjusted: list[dict[str, Any]] = []
    ordered = sorted(
        trades,
        key=lambda row: (
            str(row.get("window") or ""),
            str(row.get("decision_date") or row.get("entry_date") or ""),
            int(row.get("queue_rank") or row.get("rank") or 99),
            str(row.get("ticker") or ""),
        ),
    )
    for trade in ordered:
        row = dict(trade)
        ticker = str(row.get("ticker") or "").upper()
        window = str(row.get("window") or "")
        decision_dt = _parse_date(row.get("decision_date") or row.get("entry_date"))
        key = (window, ticker)
        prior_dt = last_seen.get(key)
        days_since = (
            (decision_dt - prior_dt).days
            if decision_dt is not None and prior_dt is not None
            else None
        )
        repeat_applies = (
            scalar is not None
            and days_since is not None
            and 0 <= days_since <= LOOKBACK_DAYS
        )

        base_notional = parent.parent._float(row.get("notional"))
        base_multiplier = _base_multiplier(row)
        row["recent_ticker_repeat_variant"] = variant_name
        row["recent_ticker_repeat_rule_version"] = RULE_VERSION
        row["recent_ticker_repeat_profile_name"] = _repeat_profile_name(scalar)
        row["recent_ticker_repeat_lookback_days"] = LOOKBACK_DAYS
        row["recent_ticker_repeat_applied"] = bool(repeat_applies)
        row["recent_ticker_repeat_days_since_prior"] = days_since
        row["recent_ticker_repeat_prior_decision_date"] = (
            prior_dt.isoformat() if prior_dt is not None else None
        )
        row["recent_ticker_repeat_scalar"] = scalar if repeat_applies else None
        row["recent_ticker_repeat_base_notional"] = base_notional
        row["base_rank_notional_profile_name"] = _base_profile_name(row)

        if repeat_applies and base_notional is not None:
            new_notional = round(base_notional * float(scalar), 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["notional"] = new_notional
            row["shares"] = new_notional / entry_open
            row["pnl"] = round(new_notional * net_return, 2)
            if base_multiplier is not None:
                row["rank_notional_multiplier"] = round(
                    base_multiplier * float(scalar),
                    6,
                )
        if decision_dt is not None:
            last_seen[key] = decision_dt
        adjusted.append(row)
    return sorted(
        adjusted,
        key=lambda row: (
            str(row.get("window") or ""),
            str(row.get("decision_date") or row.get("entry_date") or ""),
            int(row.get("queue_rank") or row.get("rank") or 99),
            str(row.get("ticker") or ""),
        ),
    )


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
    return str(trade.get("sector") or parent.parent.accepted._sector(trade.get("ticker")))


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
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
                "score_top3_spread": trade.get("score_top3_spread"),
                "base_rank_notional_profile_name": trade.get(
                    "base_rank_notional_profile_name"
                ),
                "recent_ticker_repeat_applied": trade.get(
                    "recent_ticker_repeat_applied"
                ),
                "recent_ticker_repeat_days_since_prior": trade.get(
                    "recent_ticker_repeat_days_since_prior"
                ),
                "recent_ticker_repeat_prior_decision_date": trade.get(
                    "recent_ticker_repeat_prior_decision_date"
                ),
                "recent_ticker_repeat_scalar": trade.get(
                    "recent_ticker_repeat_scalar"
                ),
                "recent_ticker_repeat_profile_name": trade.get(
                    "recent_ticker_repeat_profile_name"
                ),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _notional_by_repeat_profile(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(trade.get("recent_ticker_repeat_profile_name") or "baseline")
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
    selected = _apply_recent_repeat_scalar(
        baseline_trades,
        variant_name=variant_name,
        scalar=variant.get("scalar"),
    )
    after_metrics = _metrics_for_trades(
        trades=selected,
        core_results=core_results,
        prices=prices,
    )
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    for label in WINDOWS:
        adjusted = [row for row in selected if row.get("window") == label]
        repeat_trades = [
            row for row in adjusted if row.get("recent_ticker_repeat_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(adjusted),
            "recent_repeat_adjusted_trade_count": len(repeat_trades),
            "recent_repeat_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in repeat_trades),
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
            "notional_by_queue_rank": parent.parent.rank_exp._notional_by_queue_rank(
                adjusted
            ),
            "notional_by_repeat_profile": _notional_by_repeat_profile(adjusted),
            "surface_summary": parent.parent.parent.base._surface_summary(adjusted),
            "selected_trades": _selected_trade_rows(adjusted),
        }
    repeat_all = [row for row in selected if row.get("recent_ticker_repeat_applied")]
    repeat_windows = {str(row.get("window")) for row in repeat_all if row.get("window")}
    return {
        "variant_name": variant_name,
        "variant_type": "recent_ticker_repeat_notional_scalar",
        "lookback_days": LOOKBACK_DAYS,
        "scalar": variant.get("scalar"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "recent_repeat_adjusted_trade_count": len(repeat_all),
        "recent_repeat_adjusted_windows": sorted(repeat_windows),
        "single_ticker_positive_share": parent.parent._single_ticker_positive_share(
            selected
        ),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = parent.parent.parent._aggregate_delta(
        baseline_metrics,
        variant["metrics"],
    )
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["recent_repeat_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["recent_repeat_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
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
        "recent_repeat_adjusted_trade_count": variant[
            "recent_repeat_adjusted_trade_count"
        ],
        "recent_repeat_adjusted_windows": variant[
            "recent_repeat_adjusted_windows"
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
        f"# {EXPERIMENT_ID} State-Surface Recent Ticker Repeat Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `recent_ticker_repeat_60d_notional_scalar` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        scalar = row["scalar"]
        lines.append(
            "| {variant} | {passed} | {scalar} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                scalar=f"{scalar:.2f}" if scalar is not None else "n/a",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["recent_repeat_adjusted_trade_count"],
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
                trades=sleeve["recent_repeat_adjusted_trade_count"],
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
    gate2 = parent.parent.parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    prices = parent.parent.parent._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        core_results[label] = parent.parent.parent._load_core_result(window)

    baseline_trades = parent._current_accepted_trades(
        core_results=core_results,
        prices=prices,
    )
    baseline_metrics = _metrics_for_trades(
        trades=baseline_trades,
        core_results=core_results,
        prices=prices,
    )
    baseline_share = parent.parent._single_ticker_positive_share(baseline_trades)

    variants = [
        _variant_payload(
            variant_name=variant_name,
            variant=variant,
            baseline_trades=baseline_trades,
            core_results=core_results,
            prices=prices,
        )
        for variant_name, variant in REPEAT_VARIANTS.items()
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
                "lookback_days": variant["lookback_days"],
                "scalar": variant["scalar"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "recent_repeat_adjusted_trade_count": variant[
                    "recent_repeat_adjusted_trade_count"
                ],
                "recent_repeat_adjusted_windows": variant[
                    "recent_repeat_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(
        row for row in variants if row["variant_name"] == best["variant_name"]
    )
    delta = parent.parent.parent._aggregate_delta(
        baseline_metrics,
        best_payload["metrics"],
    )
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_recent_ticker_repeat_notional"
        if passed
        else "rejected_state_surface_recent_ticker_repeat_notional"
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
        "hypothesis": "State-surface same-ticker repeats within 60 calendar days may be continuation-quality signals, so a bounded paper-notional top-up can improve replacement value without changing candidate eligibility.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Targets state-surface maturation through a new crowding/repeat-exposure field, not a neighboring score-expansion threshold/profile retune.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "recent_ticker_repeat_60d_notional_scalar",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "lookback_days": LOOKBACK_DAYS,
            "best_scalar": best["scalar"],
            "profile_priority": "after accepted rank-notional profiles have set base paper notional; same-ticker repeat scalar adjusts only pending paper entry notional",
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
            "baseline_artifact": parent.parent._repo_rel(
                "data/experiments/exp-20260519-001/state_surface_score_expansion_notional.json"
            ),
            "baseline_variant": BASELINE_VARIANT,
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "ticker",
                "decision_date",
                "queue_rank",
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
            "hard_rule": "No filter or candidate gate changed; survival is measured from the same selected paper/core trade set.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260519-001": "Accepted residual score-expansion allocation; this experiment freezes that stack and tests only a new repeat-exposure field.",
            "state_surface_adjacent_retunes": "Playbook blocks nearby score-expansion/profile mining without a new independent field; this uses same-ticker recurrence in sleeve state.",
            "llm_soft_ranking": "Skipped because sparse/PIT-limited attribution remains a known data limit.",
            "sec_neutral_underreaction": "Skipped because recent stricter variants were sample-limited and concentrated.",
            "core_misfit": "Skipped because additional gate slicing after trend_long_only is small-sample and already logged.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this deterministic field is replayable from sleeve state.",
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
            "Recent same-ticker repeats improved default-off state-surface paper allocation in two windows with zero EV-regressed windows; keep it paper-only while forward concentration matures."
            if passed
            else "Recent same-ticker repeat sizing did not clear Gate 4; keep the accepted score-expansion stack unchanged."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Promote only as shared default-off paper metadata; require forward tail/concentration evidence before any live adapter work."
            if passed
            else "Do not retry nearby repeat lookbacks/scalars without forward evidence or a distinct crowding-quality field."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: same-ticker repeats inside 60 calendar days may indicate durable trend continuation for the state-surface sleeve.",
            "2_history_check": "Prior state-surface work mined rank-quality and score-dispersion fields; no accepted experiment used sleeve-state same-ticker recurrence.",
            "3_single_causal_variable": "recent_ticker_repeat_60d_notional_scalar",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, >=2 improved windows, zero EV-regressed windows, adjusted trades >=2 across >=2 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
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
            "title": "State-surface recent ticker repeat notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": parent.parent._repo_rel(OUT_JSON),
            "summary": (
                f"Recent repeat best scalar {payload['parameters']['best_scalar']} "
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
