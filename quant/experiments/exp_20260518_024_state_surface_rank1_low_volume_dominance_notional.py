"""exp-20260518-024: state-surface rank-1 low-volume dominance notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
when the accepted rank-1 ret20 dominance profile fires but rank 1 has weak
20-day volume participation, shift bounded paper notional away from rank 1.

Core entries, exits, candidate eligibility, queue size, hold days, active
capacity, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260518-024"
EXPERIMENT_SLUG = "state_surface_rank1_low_volume_dominance_notional"
BASELINE_VARIANT = "accepted_rank1_ret20_dominance_notional"

ACCEPTED_RANK1_DOMINANCE_VARIANT = {
    "profile": [1.60, 1.40, 1.00, 0.675, 0.35],
    "rank1_ret20_lead_min": 0.15,
    "score_gap_min": 0.45,
}

LOW_VOLUME_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "rank1_volume_max": None,
                "aggression_order": 0,
                "description": "current accepted rank-1 dominance stack",
            },
        ),
        (
            "rank1_volume_lt_050_rank2_shift",
            {
                "profile": [1.00, 1.85, 1.10, 0.675, 0.35],
                "rank1_volume_max": 0.50,
                "aggression_order": 1,
                "description": "thin low-volume trigger with rank-2-heavy transfer",
            },
        ),
        (
            "rank1_volume_lt_065_small_shift",
            {
                "profile": [1.55, 1.45, 1.00, 0.675, 0.35],
                "rank1_volume_max": 0.65,
                "aggression_order": 2,
                "description": "two-window low-volume trigger with small transfer",
            },
        ),
        (
            "rank1_volume_lt_065_balanced",
            {
                "profile": [1.50, 1.50, 1.00, 0.675, 0.35],
                "rank1_volume_max": 0.65,
                "aggression_order": 3,
                "description": "two-window low-volume trigger with balanced rank 1/2",
            },
        ),
        (
            "rank1_volume_lt_065_rank2_shift",
            {
                "profile": [1.00, 1.85, 1.10, 0.675, 0.35],
                "rank1_volume_max": 0.65,
                "aggression_order": 4,
                "description": "two-window low-volume trigger with rank-2-heavy transfer",
            },
        ),
    ]
)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260518_023_state_surface_rank1_ret20_dominance_notional as accepted  # noqa: E402


parent = accepted.parent
rank_exp = accepted.rank_exp
spy_gate = accepted.spy_gate
WINDOWS = accepted.WINDOWS

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

MIN_SELECTED_TRADES = spy_gate.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = 6
MIN_ADJUSTED_WINDOWS = 2
MAX_SINGLE_TICKER_POSITIVE_SHARE = spy_gate.MAX_SINGLE_TICKER_POSITIVE_SHARE
MAX_DRAWDOWN_WORSE = spy_gate.MAX_DRAWDOWN_WORSE


def _safe(value: Any) -> Any:
    return accepted._safe(value)


def _repo_rel(path: Path | str) -> str:
    return accepted._repo_rel(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    accepted._write_json(path, payload)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    accepted._upsert_jsonl(path, payload)


def _float(value: Any) -> float | None:
    return accepted._float(value)


def _profile_multiplier(profile: list[float], queue_rank: Any) -> float:
    return accepted._profile_multiplier(profile, queue_rank)


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    return accepted._single_ticker_positive_share(trades)


def _low_volume_profile_name(volume_max: float) -> str:
    value = str(round(float(volume_max), 6)).rstrip("0").rstrip(".")
    return f"rank1_low_volume_lt_{value.replace('.', 'p')}"


def _rank1_volume_by_window_day(
    trades: list[dict[str, Any]],
) -> dict[tuple[str, str], float | None]:
    out: dict[tuple[str, str], float | None] = {}
    for trade in trades:
        if int(trade.get("queue_rank") or 0) != 1:
            continue
        key = (
            str(trade.get("window") or ""),
            str(trade.get("decision_date") or "")[:10],
        )
        features = trade.get("features") or {}
        out[key] = _float(features.get("volume_ratio_20"))
    return out


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
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
                "rank1_ret20_excess_spy": trade.get("rank1_ret20_excess_spy"),
                "rank2_ret20_excess_spy": trade.get("rank2_ret20_excess_spy"),
                "rank2_ret20_excess_spy_lead": trade.get("rank2_ret20_excess_spy_lead"),
                "rank1_volume_ratio_20": trade.get("rank1_volume_ratio_20"),
                "rank1_low_volume_profile_applied": trade.get(
                    "rank1_low_volume_profile_applied"
                ),
                "rank1_low_volume_profile_name": trade.get(
                    "rank1_low_volume_profile_name"
                ),
                "base_rank_notional_profile_name": trade.get(
                    "rank1_ret20_dominance_profile_name"
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
        key = str(trade.get("rank1_low_volume_profile_name") or "baseline")
        row = out.setdefault(key, {"trade_count": 0, "notional_sum": 0.0, "pnl_sum": 0.0})
        row["trade_count"] += 1
        row["notional_sum"] += float(trade.get("notional") or 0.0)
        row["pnl_sum"] += float(trade.get("pnl") or 0.0)
    for row in out.values():
        row["notional_sum"] = round(row["notional_sum"], 2)
        row["pnl_sum"] = round(row["pnl_sum"], 2)
    return out


def _apply_low_volume_profile(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    rank1_volume = _rank1_volume_by_window_day(trades)
    adjusted = []
    base_notional = float(parent.base.EVENT_NOTIONAL)
    profile = variant.get("profile")
    volume_max = _float(variant.get("rank1_volume_max"))
    for trade in trades:
        row = dict(trade)
        key = (
            str(row.get("window") or ""),
            str(row.get("decision_date") or "")[:10],
        )
        rank1_volume_ratio = rank1_volume.get(key)
        row["rank1_volume_ratio_20"] = rank1_volume_ratio
        row["rank1_low_volume_variant"] = variant_name
        row["rank1_low_volume_profile_applied"] = False
        row["rank1_low_volume_profile_name"] = row.get(
            "rank1_ret20_dominance_profile_name"
        )

        applies = (
            variant_name != BASELINE_VARIANT
            and profile
            and volume_max is not None
            and rank1_volume_ratio is not None
            and rank1_volume_ratio < volume_max
            and bool(row.get("rank1_ret20_dominance_profile_applied"))
        )
        if applies:
            multiplier = _profile_multiplier(profile, row.get("queue_rank") or row.get("rank"))
            notional = round(base_notional * multiplier, 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["rank1_low_volume_profile_applied"] = True
            row["rank1_low_volume_profile_name"] = _low_volume_profile_name(volume_max)
            row["rank_notional_multiplier"] = multiplier
            row["notional"] = notional
            row["shares"] = notional / entry_open
            row["pnl"] = round(notional * net_return, 2)
        adjusted.append(row)
    return adjusted


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    baseline_trades: list[dict[str, Any]],
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    selected = _apply_low_volume_profile(
        baseline_trades,
        variant_name=variant_name,
        variant=variant,
    )
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        adjusted = [row for row in selected if row.get("window") == label]
        event_curve = rank_exp._event_equity_curve_variable_notional(
            adjusted,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        after_metrics[label] = parent.base._combined_metrics(
            core_results[label],
            event_curve,
            adjusted,
        )
        adjusted_trades = [
            trade for trade in adjusted if trade.get("rank1_low_volume_profile_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(adjusted),
            "rank1_low_volume_adjusted_trade_count": len(adjusted_trades),
            "rank1_low_volume_adjusted_pnl": round(
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
            "candidate_breadth_distribution": dict(
                Counter(str(row.get("candidate_breadth") or "unknown") for row in adjusted)
            ),
            "notional_by_queue_rank": rank_exp._notional_by_queue_rank(adjusted),
            "notional_by_rank1_low_volume_profile": _notional_by_profile(adjusted),
            "surface_summary": parent.base._surface_summary(adjusted),
            "selected_trades": _selected_trade_rows(adjusted),
        }

    adjusted_all = [
        trade for trade in selected if trade.get("rank1_low_volume_profile_applied")
    ]
    adjusted_windows = {
        str(trade.get("window")) for trade in adjusted_all if trade.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "rank1_low_volume_dominance_rank_notional_profile",
        "profile": variant.get("profile"),
        "rank1_volume_max": variant.get("rank1_volume_max"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "rank1_low_volume_adjusted_trade_count": len(adjusted_all),
        "rank1_low_volume_adjusted_windows": sorted(adjusted_windows),
        "single_ticker_positive_share": _single_ticker_positive_share(selected),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = parent._aggregate_delta(baseline_metrics, variant["metrics"])
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["rank1_low_volume_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["rank1_low_volume_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
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
        "rank1_low_volume_adjusted_trade_count": variant[
            "rank1_low_volume_adjusted_trade_count"
        ],
        "rank1_low_volume_adjusted_windows": variant[
            "rank1_low_volume_adjusted_windows"
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
        f"# {EXPERIMENT_ID} State-Surface Rank-1 Low-Volume Dominance Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `rank1_low_volume_dominance_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Volume Max | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {vol} | {profile} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                vol=row["rank1_volume_max"],
                profile=row["profile"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["rank1_low_volume_adjusted_trade_count"],
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
                trades=sleeve["rank1_low_volume_adjusted_trade_count"],
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
    gate2 = parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    prices = parent._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        result = parent._load_core_result(window)
        core_results[label] = result
        core_metrics[label] = parent.base._core_metrics(result)

    accepted_baseline = accepted._variant_payload(
        variant_name="rank1_ret20_dominance_ge_015_score_gap_ge_045_balanced",
        variant=ACCEPTED_RANK1_DOMINANCE_VARIANT,
        core_results=core_results,
        prices=prices,
    )
    baseline_trades = accepted_baseline["selected_trades"]
    variants = [
        _variant_payload(
            variant_name=variant_name,
            variant=variant,
            baseline_trades=baseline_trades,
            core_results=core_results,
            prices=prices,
        )
        for variant_name, variant in LOW_VOLUME_VARIANTS.items()
    ]
    baseline = next(row for row in variants if row["variant_name"] == BASELINE_VARIANT)
    baseline_metrics = baseline["metrics"]
    baseline_share = baseline["single_ticker_positive_share"]

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
                "profile": variant["profile"],
                "rank1_volume_max": variant["rank1_volume_max"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "selected_trade_count": variant["selected_trade_count"],
                "rank1_low_volume_adjusted_trade_count": variant[
                    "rank1_low_volume_adjusted_trade_count"
                ],
                "rank1_low_volume_adjusted_windows": variant[
                    "rank1_low_volume_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best_summary = _choose_best(sweep_summary)
    best_variant = next(
        row for row in variants if row["variant_name"] == best_summary["variant_name"]
    )
    delta = best_summary["gate4"]["delta_metrics"]

    if best_summary["gate4"]["passed"]:
        decision = "accepted_shared_default_off_policy_rank1_low_volume_dominance_notional"
        status = "accepted"
        interpretation = (
            "Rank-1 low-volume dominance is a positive state-surface paper "
            "allocation field on top of the accepted rank-1 dominance stack."
        )
    else:
        decision = "rejected_state_surface_rank1_low_volume_dominance_notional"
        status = "rejected"
        interpretation = (
            "The low-volume rank-1 dominance exception found a real mid_weak "
            "improvement clue, but Gate 4 rejects promotion: the broad enough "
            "variants regress late_strong, while the non-regressing trigger is "
            "single-window and sample-thin."
        )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_rank1_low_volume_dominance_notional",
        "changed_variable": "rank1_low_volume_dominance_rank_notional_profile",
        "change_summary": (
            "Sweep a rank-1 low-volume dominance paper-notional profile for the "
            "accepted default-off rotation state-surface sleeve."
        ),
        "component": "quant/experiments",
        "mechanism_family": "state_aware_candidate_pool_allocation",
        "hypothesis": (
            "When the accepted rank-1 ret20 dominance profile fires but rank 1 "
            "has weak 20-day volume participation, the queue may be overpaying "
            "for stale rank-1 leadership. A bounded profile that transfers "
            "paper notional toward rank 2 may improve replacement value."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper rank-quality allocation",
            "playbook_alignment": (
                "Targets state-surface maturation through a new production-visible "
                "crowding/participation field and avoids LLM soft-ranking data limits."
            ),
        },
        "history_check": {
            "exp-20260517-021": (
                "Rejected a candidate-level volume_ratio_20 floor; this experiment "
                "does not filter on volume and instead tests a rank-1 dominance "
                "notional exception."
            ),
            "exp-20260518-023": (
                "Accepted rank-1 ret20 dominance plus score gap as a small default-off "
                "paper allocation field."
            ),
            "anti_repeat_boundary": (
                "This is not a nearby rank/ret20 scalar retry. The single new "
                "discriminator is rank-1 volume participation inside the accepted "
                "rank-1 dominance state."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: use rank-1 volume participation as a production-visible "
                "state-surface paper notional field inside accepted rank-1 dominance days."
            ),
            "2_history_check": (
                "Volume floor was rejected; rank-1 dominance was accepted. This exact "
                "low-volume dominance notional exception is not logged as a prior experiment."
            ),
            "3_single_causal_variable": "rank1_low_volume_dominance_rank_notional_profile",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; best non-control profile "
                "must improve aggregate EV/PnL versus accepted exp-20260518-023, "
                "improve at least two windows, regress zero windows, keep selected "
                f"trades >= {MIN_SELECTED_TRADES}, adjusted trades >= "
                f"{MIN_ADJUSTED_TRADES} across >= {MIN_ADJUSTED_WINDOWS} windows, "
                f"max drawdown drift <= {MAX_DRAWDOWN_WORSE:.1%}, and single-ticker "
                f"positive share <= {MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_024_state_surface_rank1_low_volume_dominance_notional.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "rank1_low_volume_dominance_rank_notional_profile",
            "baseline_variant": BASELINE_VARIANT,
            "accepted_rank1_dominance_variant": ACCEPTED_RANK1_DOMINANCE_VARIANT,
            "variants": LOW_VOLUME_VARIANTS,
            "best_variant": best_summary["variant_name"],
            "best_profile": best_summary["profile"],
            "best_rank1_volume_max": best_summary["rank1_volume_max"],
            "selection_rule": "highest aggregate EV among passing profiles; otherwise best EV scout",
            "daily_candidate_count_locked": rank_exp.ACCEPTED_DAILY_CANDIDATE_COUNT,
            "locked_ret20_excess_spy_min": 0.0,
            "allowed_surfaces_locked": [rank_exp.TARGET_SURFACE],
            "decision_timing": "score after decision-date close; enter next trading day open",
            "candidate_source": "production universe only, excluding SPY/QQQ/IWM and existing same-day core candidates",
            "max_active_surface_positions": parent.base.MAX_ACTIVE_SURFACE_POSITIONS,
            "hold_days": parent.base.HOLD_DAYS,
            "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
            "locked_variables": [
                "core universe files",
                "signal generation",
                "entry filters",
                "candidate scoring weights",
                "daily candidate count",
                "state-surface surface eligibility",
                "state-surface ret20_excess_spy gate",
                "state-surface candidate-breadth profile",
                "state-surface score-compression profile",
                "state-surface rank-2 ret20 lead profile",
                "state-surface rank-2 ret20 score-gap profile",
                "state-surface rank-1 ret20 dominance profile",
                "state-surface active capacity",
                "state-surface hold days",
                "core risk sizing",
                "core position slots",
                "gap cancels",
                "add-ons",
                "core exits",
                "LLM/news replay",
                "event bundle definitions",
                "production orders",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "snapshots": {label: w["snapshot"] for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "canonical_core_baseline_metrics": core_metrics,
            "accepted_state_surface_baseline_metrics": baseline_metrics,
            "baseline_variant": BASELINE_VARIANT,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "state_surface surface",
                "state_surface score",
                "state_surface queue_rank",
                "state_surface decision_date",
                "state_surface candidate_breadth",
                "state_surface features.volume_ratio_20",
                "state_surface rank1_ret20_excess_spy",
                "state_surface rank2_ret20_excess_spy",
                "OHLCV next-session open",
                "OHLCV fixed-horizon exit close",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_core_filter_added": False,
            "core_signals_generated_delta": 0,
            "core_signals_survived_delta": 0,
            "minimum_after_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in core_metrics.values()
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values()) >= 0.05,
        },
        "gate4": best_summary["gate4"],
        "before_metrics": baseline_metrics,
        "after_metrics": best_variant["metrics"],
        "delta_metrics": delta,
        "surface_sleeve": best_variant["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"] for label in WINDOWS
        },
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        },
        "production_impact": {
            "shared_policy_changed": best_summary["gate4"]["passed"],
            "backtester_adapter_changed": False,
            "run_adapter_changed": best_summary["gate4"]["passed"],
            "replay_only": False,
            "parity_test_added": best_summary["gate4"]["passed"],
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "shared_policy_file": "quant/state_surface_sleeve.py",
            "parity_test_file": "quant/test_state_surface_sleeve.py",
            "production_impact": (
                "If accepted, shared default-off paper policy would change only "
                "state-surface paper notional after queue ranking by using rank-1 "
                "low-volume participation inside accepted rank-1 dominance days. "
                "The same state_surface_sleeve.py path is used by production; "
                "live/default orders remain disabled."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "LLM soft-ranking data remains sparse/PIT-limited; this deterministic "
                "state-surface allocation test uses replayable queue score and OHLCV fields."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if best_summary["gate4"]["passed"] else interpretation,
        "next_evidence_needed": (
            "Promote the accepted low-volume profile in shared state_surface_sleeve.py, "
            "add parity coverage, and continue forward closed replacement-value observation."
            if best_summary["gate4"]["passed"]
            else "Do not add the low-volume rank-1 dominance exception on frozen windows; next state-surface alpha needs either forward evidence or a different participation/crowding discriminator."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            "docs/production_backtest_parity.md",
            "docs/current_state.md",
            "docs/backtesting.md",
            "docs/alpha-optimization-playbook.md",
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface rank-1 low-volume dominance notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
            "best_variant": payload["parameters"]["best_variant"],
            "best_profile": payload["parameters"]["best_profile"],
            "best_rank1_volume_max": payload["parameters"]["best_rank1_volume_max"],
            "expected_value_score_delta": payload["delta_metrics"]["aggregate_ev_delta"],
            "total_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
            "gate4_passed": payload["gate4"]["passed"],
            "summary": payload["interpretation"],
            "artifact": _repo_rel(OUT_JSON),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["parameters"]["best_variant"],
                    "best_profile": payload["parameters"]["best_profile"],
                    "best_rank1_volume_max": payload["parameters"][
                        "best_rank1_volume_max"
                    ],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "windows_ev_improved": payload["gate4"]["windows_ev_improved"],
                    "windows_ev_regressed": payload["gate4"]["windows_ev_regressed"],
                    "adjusted_trade_count": payload["gate4"][
                        "rank1_low_volume_adjusted_trade_count"
                    ],
                    "adjusted_windows": payload["gate4"][
                        "rank1_low_volume_adjusted_windows"
                    ],
                    "single_ticker_positive_share": payload["gate4"][
                        "single_ticker_positive_share"
                    ],
                    "single_ticker_positive_share_delta": payload["gate4"][
                        "single_ticker_positive_share_delta"
                    ],
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
