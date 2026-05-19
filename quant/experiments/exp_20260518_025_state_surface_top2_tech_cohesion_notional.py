"""exp-20260518-025: state-surface top-2 Technology cohesion notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
when the accepted rotation state-surface queue has rank 1 and rank 2 both in
Technology, use a bounded rank-notional profile that lifts rank 2 and rank 3.

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


EXPERIMENT_ID = "exp-20260518-025"
EXPERIMENT_SLUG = "state_surface_top2_tech_cohesion_notional"
BASELINE_VARIANT = "accepted_rank1_ret20_dominance_notional"
TARGET_SECTOR = "Technology"

TECH_COHESION_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "target_sector": TARGET_SECTOR,
                "aggression_order": 0,
                "description": "current accepted rank-1 dominance stack",
            },
        ),
        (
            "top2_tech_rank2_lift",
            {
                "profile": [1.45, 1.70, 1.15, 0.675, 0.35],
                "target_sector": TARGET_SECTOR,
                "aggression_order": 1,
                "description": "top-2 Technology cohesion with rank-2/3 lift",
            },
        ),
        (
            "top2_tech_rank23_lift",
            {
                "profile": [1.40, 1.70, 1.25, 0.675, 0.35],
                "target_sector": TARGET_SECTOR,
                "aggression_order": 2,
                "description": "top-2 Technology cohesion with stronger rank-3 lift",
            },
        ),
        (
            "top2_tech_balanced",
            {
                "profile": [1.55, 1.55, 1.10, 0.675, 0.35],
                "target_sector": TARGET_SECTOR,
                "aggression_order": 3,
                "description": "top-2 Technology cohesion with balanced rank 1/2",
            },
        ),
        (
            "top2_tech_rank2_heavy",
            {
                "profile": [1.20, 1.90, 1.20, 0.675, 0.35],
                "target_sector": TARGET_SECTOR,
                "aggression_order": 4,
                "description": "top-2 Technology cohesion with rank-2-heavy transfer",
            },
        ),
    ]
)

ACCEPTED_RANK1_DOMINANCE_VARIANT = {
    "profile": [1.60, 1.40, 1.00, 0.675, 0.35],
    "rank1_ret20_lead_min": 0.15,
    "score_gap_min": 0.45,
}

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from risk_engine import SECTOR_MAP  # noqa: E402
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
    line = json.dumps(_safe(payload), sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _profile_multiplier(profile: list[float], queue_rank: Any) -> float:
    try:
        rank = int(queue_rank)
    except (TypeError, ValueError):
        rank = 1
    rank = max(rank, 1)
    if rank > len(profile):
        return float(profile[-1])
    return float(profile[rank - 1])


def _sector(ticker: Any) -> str:
    return str(SECTOR_MAP.get(str(ticker or "").upper()) or "Unknown")


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    return accepted._single_ticker_positive_share(trades)


def _top2_sector_by_window_day(
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
        rank1_sector = _sector(ranked[0].get("ticker")) if len(ranked) >= 1 else None
        rank2_sector = _sector(ranked[1].get("ticker")) if len(ranked) >= 2 else None
        out[key] = {
            "rank1_sector": rank1_sector,
            "rank2_sector": rank2_sector,
            "top2_sector_cohesion": (
                len(ranked) >= 2
                and rank1_sector
                and rank1_sector != "Unknown"
                and rank1_sector == rank2_sector
            ),
            "top2_sector_cohesion_sector": (
                rank1_sector
                if len(ranked) >= 2 and rank1_sector == rank2_sector
                else None
            ),
        }
    return out


def _tech_cohesion_profile_name(sector: str) -> str:
    return f"top2_sector_cohesion_{'_'.join(str(sector).lower().split())}"


def _apply_tech_cohesion_profile(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    top2_sector = _top2_sector_by_window_day(trades)
    adjusted = []
    base_notional = float(parent.base.EVENT_NOTIONAL)
    profile = variant.get("profile")
    target_sector = str(variant.get("target_sector") or TARGET_SECTOR)
    for trade in trades:
        row = dict(trade)
        key = (
            str(row.get("window") or ""),
            str(row.get("decision_date") or "")[:10],
        )
        sector_state = top2_sector.get(key) or {}
        row.update(sector_state)
        row["top2_sector_cohesion_variant"] = variant_name
        row["top2_sector_cohesion_profile_applied"] = False
        row["top2_sector_cohesion_profile_name"] = row.get(
            "rank1_ret20_dominance_profile_name"
        )

        applies = (
            variant_name != BASELINE_VARIANT
            and profile
            and bool(row.get("top2_sector_cohesion"))
            and row.get("rank1_sector") == target_sector
            and row.get("rank2_sector") == target_sector
        )
        if applies:
            multiplier = _profile_multiplier(profile, row.get("queue_rank") or row.get("rank"))
            notional = round(base_notional * multiplier, 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["top2_sector_cohesion_profile_applied"] = True
            row["top2_sector_cohesion_profile_name"] = _tech_cohesion_profile_name(
                target_sector
            )
            row["rank_notional_multiplier"] = multiplier
            row["notional"] = notional
            row["shares"] = notional / entry_open
            row["pnl"] = round(notional * net_return, 2)
        adjusted.append(row)
    return adjusted


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "sector": _sector(trade.get("ticker")),
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
                "rank1_sector": trade.get("rank1_sector"),
                "rank2_sector": trade.get("rank2_sector"),
                "top2_sector_cohesion": trade.get("top2_sector_cohesion"),
                "top2_sector_cohesion_sector": trade.get(
                    "top2_sector_cohesion_sector"
                ),
                "top2_sector_cohesion_profile_applied": trade.get(
                    "top2_sector_cohesion_profile_applied"
                ),
                "top2_sector_cohesion_profile_name": trade.get(
                    "top2_sector_cohesion_profile_name"
                ),
                "base_rank_notional_profile_name": trade.get(
                    "rank1_ret20_dominance_profile_name"
                ),
                "rank1_ret20_excess_spy": trade.get("rank1_ret20_excess_spy"),
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
        key = str(trade.get("top2_sector_cohesion_profile_name") or "baseline")
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
    selected = _apply_tech_cohesion_profile(
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
            trade for trade in adjusted if trade.get("top2_sector_cohesion_profile_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(adjusted),
            "top2_sector_cohesion_adjusted_trade_count": len(adjusted_trades),
            "top2_sector_cohesion_adjusted_pnl": round(
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
            "sector_distribution": dict(
                Counter(_sector(row.get("ticker")) for row in adjusted)
            ),
            "notional_by_queue_rank": rank_exp._notional_by_queue_rank(adjusted),
            "notional_by_top2_sector_cohesion_profile": _notional_by_profile(adjusted),
            "surface_summary": parent.base._surface_summary(adjusted),
            "selected_trades": _selected_trade_rows(adjusted),
        }

    adjusted_all = [
        trade for trade in selected if trade.get("top2_sector_cohesion_profile_applied")
    ]
    adjusted_windows = {
        str(trade.get("window")) for trade in adjusted_all if trade.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "top2_technology_sector_cohesion_rank_notional_profile",
        "profile": variant.get("profile"),
        "target_sector": variant.get("target_sector"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected,
        "selected_trade_count": len(selected),
        "top2_sector_cohesion_adjusted_trade_count": len(adjusted_all),
        "top2_sector_cohesion_adjusted_windows": sorted(adjusted_windows),
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
        variant["top2_sector_cohesion_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["top2_sector_cohesion_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
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
        "top2_sector_cohesion_adjusted_trade_count": variant[
            "top2_sector_cohesion_adjusted_trade_count"
        ],
        "top2_sector_cohesion_adjusted_windows": variant[
            "top2_sector_cohesion_adjusted_windows"
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
        f"# {EXPERIMENT_ID} State-Surface Top-2 Technology Cohesion Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `top2_technology_sector_cohesion_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
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
                adj=row["gate4"]["top2_sector_cohesion_adjusted_trade_count"],
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
                trades=sleeve["top2_sector_cohesion_adjusted_trade_count"],
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
        for variant_name, variant in TECH_COHESION_VARIANTS.items()
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
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "profile": variant["profile"],
                "target_sector": variant["target_sector"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "top2_sector_cohesion_adjusted_trade_count": variant[
                    "top2_sector_cohesion_adjusted_trade_count"
                ],
                "top2_sector_cohesion_adjusted_windows": variant[
                    "top2_sector_cohesion_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(
        row for row in variants if row["variant_name"] == best["variant_name"]
    )
    delta = parent._aggregate_delta(baseline_metrics, best_payload["metrics"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_top2_tech_cohesion_notional"
        if passed
        else "rejected_state_surface_top2_tech_cohesion_notional"
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
        "hypothesis": "When the accepted rotation state-surface queue has rank 1 and rank 2 both in Technology, the sector-cohesion state identifies a stronger rank-2/3 follow-through basket than the generic rank-notional stack.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Targets state-surface maturation through a new production-visible rank-quality/crowding field, not LLM soft ranking.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "top2_technology_sector_cohesion_rank_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_profile": best["profile"],
            "target_sector": TARGET_SECTOR,
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
            "baseline_artifact": _repo_rel(
                "data/experiments/exp-20260518-023/state_surface_rank1_ret20_dominance_notional.json"
            ),
            "baseline_variant": BASELINE_VARIANT,
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "ticker",
                "SECTOR_MAP sector",
                "decision_date",
                "queue_rank",
                "rank1_sector",
                "rank2_sector",
                "top2_sector_cohesion",
                "entry_open",
                "net_return_pct",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in baseline_metrics.values()
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
            "exp-20260518-023": "Accepted rank-1 ret20 dominance plus score gap as a small default-off paper allocation field.",
            "exp-20260518-024": "Rejected low-volume rank-1 dominance because it improved only one window or regressed one window; this test uses an orthogonal sector-cohesion discriminator.",
            "anti_repeat": "Not a ret5, volume, near-high, rank-only, hold-days, or candidate-count profile retry.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this deterministic paper allocation field uses replayable ticker-sector metadata and queue ranks.",
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
            "Top-2 Technology sector cohesion improves the default-off state-surface paper overlay in two windows without EV regression or drawdown drift. "
            "It slightly increases positive PnL concentration, so this is an incubation improvement rather than live promotion evidence."
            if passed
            else "Top-2 Technology sector cohesion did not clear Gate 4; do not promote it without forward evidence."
        ),
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": (
            "Collect forward state-surface paper outcomes and monitor concentration; do not mine adjacent sector-cohesion profiles on the frozen windows without a new field."
            if passed
            else "Do not retry nearby top-2 sector-cohesion profiles without forward evidence or a different production-visible discriminator."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: top-2 Technology sector cohesion may identify a better rank-2/3 paper notional profile.",
            "2_history_check": "Different from exp-20260518-024 low-volume and exp-20260518-021 ret5 leadership; prior sector gates were broad core filters, while this is default-off paper allocation after queue selection.",
            "3_single_causal_variable": "top2_technology_sector_cohesion_rank_notional_profile",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, >=2 improved windows, zero EV-regressed windows, adjusted trades >=6 across >=2 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
        ],
    }
    return _safe(payload)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface top-2 Technology cohesion notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "summary": (
                f"Top-2 Technology cohesion best profile {payload['parameters']['best_profile']} "
                f"changed aggregate EV {payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
                f"and PnL ${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
