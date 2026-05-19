"""exp-20260518-021: state-surface rank-2 ret5 lead notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
whether rank-2 short-term momentum leadership should shift paper notional away
from rank 1 after the accepted rank-2 ret20 leadership rule.

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


EXPERIMENT_ID = "exp-20260518-021"
EXPERIMENT_SLUG = "state_surface_rank2_ret5_lead_notional"
BASELINE_VARIANT = "accepted_rank2_ret20_lead_notional"

RANK2_RET5_LEAD_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "rank2_ret5_lead_min": None,
                "require_rank1_ret5_negative": False,
                "aggression_order": 0,
                "description": "current accepted rank-2 ret20 lead stack",
            },
        ),
        (
            "rank2_ret5_lead_ge_000_rank2_lift",
            {
                "profile": [1.30, 1.55, 1.10, 0.675, 0.35],
                "rank2_ret5_lead_min": 0.0,
                "require_rank1_ret5_negative": False,
                "aggression_order": 1,
                "description": "rank-2 lift when rank 2 has stronger ret5 than rank 1",
            },
        ),
        (
            "rank2_ret5_lead_ge_020_rank2_lift",
            {
                "profile": [1.30, 1.55, 1.10, 0.675, 0.35],
                "rank2_ret5_lead_min": 0.02,
                "require_rank1_ret5_negative": False,
                "aggression_order": 2,
                "description": "rank-2 lift when rank-2 ret5 leads by at least 2pp",
            },
        ),
        (
            "rank2_ret5_lead_ge_050_rank2_lift",
            {
                "profile": [1.30, 1.55, 1.10, 0.675, 0.35],
                "rank2_ret5_lead_min": 0.05,
                "require_rank1_ret5_negative": False,
                "aggression_order": 3,
                "description": "rank-2 lift when rank-2 ret5 leads by at least 5pp",
            },
        ),
        (
            "rank1_ret5_negative_rank2_lift",
            {
                "profile": [1.30, 1.55, 1.10, 0.675, 0.35],
                "rank2_ret5_lead_min": 0.0,
                "require_rank1_ret5_negative": True,
                "aggression_order": 4,
                "description": "rank-2 lift only when rank 1 has negative ret5 and rank 2 is stronger",
            },
        ),
    ]
)


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260518_018_state_surface_rank2_ret20_lead_notional as accepted  # noqa: E402


parent = accepted.parent
prev = accepted.prev
spy_gate = accepted.spy_gate
rank_exp = accepted.rank_exp
regime_exp = accepted.regime_exp
WINDOWS = accepted.WINDOWS

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

MIN_SELECTED_TRADES = spy_gate.MIN_SELECTED_TRADES
MIN_ADJUSTED_TRADES = max(9, accepted.MIN_ADJUSTED_TRADES)
MIN_ADJUSTED_WINDOWS = accepted.MIN_ADJUSTED_WINDOWS
MAX_SINGLE_TICKER_POSITIVE_SHARE = spy_gate.MAX_SINGLE_TICKER_POSITIVE_SHARE
MAX_DRAWDOWN_WORSE = spy_gate.MAX_DRAWDOWN_WORSE


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _rank2_ret5_lead_by_day(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("decision_date") or "")[:10], []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for day, day_rows in grouped.items():
        ranked = sorted(
            day_rows,
            key=lambda row: (
                int(row.get("queue_rank") or row.get("rank") or 99),
                -float(row.get("score") or 0.0),
            ),
        )
        rank1 = ranked[0] if len(ranked) >= 1 else {}
        rank2 = ranked[1] if len(ranked) >= 2 else {}
        rank1_ret5 = _float((rank1.get("features") or {}).get("ret5"))
        rank2_ret5 = _float((rank2.get("features") or {}).get("ret5"))
        lead = (
            round(rank2_ret5 - rank1_ret5, 6)
            if rank1_ret5 is not None and rank2_ret5 is not None
            else None
        )
        out[day] = {
            "rank1_ret5": rank1_ret5,
            "rank2_ret5": rank2_ret5,
            "rank2_ret5_lead": lead,
            "rank2_ret5_lead_sample_size": min(len(ranked), 2),
        }
    return out


def _profile_for_trade(
    *,
    variant_name: str,
    variant: dict[str, Any],
    trade: dict[str, Any],
    regime: str,
) -> tuple[str, list[float], bool]:
    baseline_name, baseline_profile, baseline_applied = accepted._profile_for_trade(
        variant_name="rank2_ret20_lead_ge_005_broad_lift",
        variant={
            "profile": accepted.RANK2_RET20_LEAD_VARIANTS[
                "rank2_ret20_lead_ge_005_broad_lift"
            ]["profile"],
            "rank2_ret20_lead_min": 0.005,
        },
        trade=trade,
        regime=regime,
    )
    if baseline_applied:
        baseline_name = "rank2_ret20_lead_ge_0p005"

    if variant_name == BASELINE_VARIANT or not variant.get("profile"):
        return baseline_name, baseline_profile, False

    lead = _float(trade.get("rank2_ret5_lead"))
    min_lead = _float(variant.get("rank2_ret5_lead_min"))
    rank1_ret5 = _float(trade.get("rank1_ret5"))
    rank1_negative_required = bool(variant.get("require_rank1_ret5_negative"))
    if (
        lead is not None
        and min_lead is not None
        and lead >= min_lead
        and (not rank1_negative_required or (rank1_ret5 is not None and rank1_ret5 < 0))
    ):
        threshold_tag = str(min_lead).replace(".", "p")
        if rank1_negative_required:
            threshold_tag = f"rank1_negative_ge_{threshold_tag}"
        return (
            f"rank2_ret5_lead_{threshold_tag}",
            list(variant["profile"]),
            True,
        )
    return baseline_name, baseline_profile, False


def _apply_rank2_ret5_lead_profile(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_day = Counter(str(trade.get("decision_date") or "")[:10] for trade in trades)
    regime_cache: dict[str, dict[str, Any]] = {}
    adjusted = []
    base_notional = float(parent.base.EVENT_NOTIONAL)

    for trade in trades:
        row = dict(trade)
        decision_date = str(row.get("decision_date") or "")[:10]
        if decision_date not in regime_cache:
            regime_cache[decision_date] = regime_exp._regime_for_date(
                prices,
                decision_date,
                theme_signal_count=by_day.get(decision_date, 0),
                breakout_signal_count=by_day.get(decision_date, 0),
            )
        regime = str(regime_cache[decision_date].get("regime") or "")
        profile_name, profile, ret5_profile_applied = _profile_for_trade(
            variant_name=variant_name,
            variant=variant,
            trade=row,
            regime=regime,
        )
        multiplier = accepted._profile_multiplier(
            profile,
            row.get("queue_rank") or row.get("rank"),
        )
        notional = round(base_notional * multiplier, 2)
        entry_open = float(row["entry_open"])
        net_return = float(row["net_return_pct"])
        row["rank2_ret5_lead_rank_notional_variant"] = variant_name
        row["rank2_ret5_lead_profile_name"] = profile_name
        row["rank2_ret5_lead_profile_applied"] = ret5_profile_applied
        row["regime"] = regime
        row["rank_notional_multiplier"] = multiplier
        row["base_event_notional"] = base_notional
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
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "queue_rank": trade.get("queue_rank"),
                "candidate_breadth": trade.get("candidate_breadth"),
                "score": trade.get("score"),
                "score_top3_spread": trade.get("score_top3_spread"),
                "rank1_ret20_excess_spy": trade.get("rank1_ret20_excess_spy"),
                "rank2_ret20_excess_spy": trade.get("rank2_ret20_excess_spy"),
                "rank2_ret20_excess_spy_lead": trade.get("rank2_ret20_excess_spy_lead"),
                "rank1_ret5": trade.get("rank1_ret5"),
                "rank2_ret5": trade.get("rank2_ret5"),
                "rank2_ret5_lead": trade.get("rank2_ret5_lead"),
                "rank2_ret5_lead_profile_name": trade.get("rank2_ret5_lead_profile_name"),
                "rank2_ret5_lead_profile_applied": trade.get(
                    "rank2_ret5_lead_profile_applied"
                ),
                "regime": trade.get("regime"),
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
        key = str(trade.get("rank2_ret5_lead_profile_name") or "unknown")
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
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        candidates = rank_exp._rotation_candidates_for_top_five(
            label=label,
            window=window,
            result=core_results[label],
            prices=prices,
        )
        spy_filtered, spy_blocked = spy_gate._apply_locked_spy_floor(candidates)
        queued = rank_exp._attach_queue_ranks(spy_filtered)
        breadth_by_day = Counter(
            str(row.get("decision_date") or "")[:10] for row in queued
        )
        dispersion_by_day = prev._score_dispersion_by_day(queued)
        rank2_ret20_lead_by_day = accepted._rank2_ret20_lead_by_day(queued)
        rank2_ret5_lead_by_day = _rank2_ret5_lead_by_day(queued)
        for row in queued:
            day = str(row.get("decision_date") or "")[:10]
            row["candidate_breadth"] = breadth_by_day[day]
            row.update(dispersion_by_day.get(day) or {})
            row.update(rank2_ret20_lead_by_day.get(day) or {})
            row.update(rank2_ret5_lead_by_day.get(day) or {})
        selected, selection_skipped = parent.base._select_trades(queued)
        adjusted = _apply_rank2_ret5_lead_profile(
            selected,
            variant_name=variant_name,
            variant=variant,
            prices=prices,
        )
        event_curve = rank_exp._event_equity_curve_variable_notional(
            adjusted,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        after_metrics[label] = parent.base._combined_metrics(
            core_results[label], event_curve, adjusted
        )
        selected_all.extend({**trade, "window": label} for trade in adjusted)
        skipped_reason_counts = Counter(
            str(row.get("reason") or "unknown")
            for row in [*spy_blocked, *selection_skipped]
        )
        adjusted_trades = [
            trade for trade in adjusted if trade.get("rank2_ret5_lead_profile_applied")
        ]
        surface_sleeve[label] = {
            "raw_rotation_candidate_count": len(candidates),
            "price_ready_rotation_candidate_count": sum(
                1 for row in candidates if row.get("status") == "price_ready"
            ),
            "ret20_excess_spy_blocked_price_ready_count": sum(
                1 for row in spy_blocked if row.get("status") == "price_ready"
            ),
            "selected_trade_count": len(adjusted),
            "rank2_ret5_lead_adjusted_trade_count": len(adjusted_trades),
            "rank2_ret5_lead_adjusted_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in adjusted_trades), 2
            ),
            "selected_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in adjusted), 2
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
            "notional_by_rank2_ret5_profile": _notional_by_profile(adjusted),
            "surface_summary": parent.base._surface_summary(adjusted),
            "skipped_reason_counts": dict(skipped_reason_counts),
            "selected_trades": _selected_trade_rows(adjusted),
        }

    adjusted_all = [
        trade for trade in selected_all if trade.get("rank2_ret5_lead_profile_applied")
    ]
    adjusted_windows = {
        str(trade.get("window")) for trade in adjusted_all if trade.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "rank2_ret5_lead_rank_notional_profile",
        "profile": variant.get("profile"),
        "rank2_ret5_lead_min": variant.get("rank2_ret5_lead_min"),
        "require_rank1_ret5_negative": bool(variant.get("require_rank1_ret5_negative")),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "rank2_ret5_lead_adjusted_trade_count": len(adjusted_all),
        "rank2_ret5_lead_adjusted_windows": sorted(adjusted_windows),
        "single_ticker_positive_share": accepted._single_ticker_positive_share(selected_all),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    variant: dict[str, Any],
    baseline_single_ticker_positive_share: float | None,
) -> dict[str, Any]:
    after_metrics = variant["metrics"]
    delta = parent._aggregate_delta(baseline_metrics, after_metrics)
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["rank2_ret5_lead_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["rank2_ret5_lead_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    tail_concentration_not_worse = (
        variant["single_ticker_positive_share"] is None
        or baseline_single_ticker_positive_share is None
        or variant["single_ticker_positive_share"]
        <= baseline_single_ticker_positive_share + 1e-12
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
        and tail_concentration_not_worse
        and drawdown_guard_passed
    )
    return {
        "passed": passed,
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "rank2_ret5_lead_adjusted_trade_count": variant[
            "rank2_ret5_lead_adjusted_trade_count"
        ],
        "rank2_ret5_lead_adjusted_windows": variant[
            "rank2_ret5_lead_adjusted_windows"
        ],
        "selected_trade_count": variant["selected_trade_count"],
        "sample_guard_passed": sample_guard_passed,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": variant["single_ticker_positive_share"],
        "baseline_single_ticker_positive_share": baseline_single_ticker_positive_share,
        "concentration_guard_passed": concentration_guard_passed,
        "tail_concentration_not_worse": tail_concentration_not_worse,
        "single_ticker_positive_share_delta": (
            round(
                variant["single_ticker_positive_share"]
                - baseline_single_ticker_positive_share,
                6,
            )
            if variant["single_ticker_positive_share"] is not None
            and baseline_single_ticker_positive_share is not None
            else None
        ),
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
        row for row in rows if row["variant_name"] != BASELINE_VARIANT and row["gate4"]["passed"]
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
        f"# {EXPERIMENT_ID} State-Surface Rank-2 Ret5 Lead Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `rank2_ret5_lead_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Ret5 Lead Min | Rank1 Ret5 Negative | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {lead} | {r1neg} | {profile} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                lead=row["rank2_ret5_lead_min"],
                r1neg=row["require_rank1_ret5_negative"],
                profile=row["profile"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["rank2_ret5_lead_adjusted_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share=f"{share:.2%}" if share is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Best Non-Control Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=sleeve["rank2_ret5_lead_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
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

    variants = [
        _variant_payload(
            variant_name=variant_name,
            variant=variant,
            core_results=core_results,
            prices=prices,
        )
        for variant_name, variant in RANK2_RET5_LEAD_VARIANTS.items()
    ]
    baseline = next(row for row in variants if row["variant_name"] == BASELINE_VARIANT)
    baseline_metrics = baseline["metrics"]
    baseline_single_ticker_positive_share = baseline["single_ticker_positive_share"]

    sweep_summary: list[dict[str, Any]] = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            variant=variant,
            baseline_single_ticker_positive_share=baseline_single_ticker_positive_share,
        )
        variant["gate4"] = gate4
        sweep_summary.append(
            {
                "variant_name": variant["variant_name"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "profile": variant["profile"],
                "rank2_ret5_lead_min": variant["rank2_ret5_lead_min"],
                "require_rank1_ret5_negative": variant["require_rank1_ret5_negative"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "rank2_ret5_lead_adjusted_trade_count": variant[
                    "rank2_ret5_lead_adjusted_trade_count"
                ],
                "rank2_ret5_lead_adjusted_windows": variant[
                    "rank2_ret5_lead_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(row for row in variants if row["variant_name"] == best["variant_name"])
    best_gate = best["gate4"]
    if best_gate["passed"]:
        decision = "accepted_shared_default_off_policy_rank2_ret5_lead_notional"
        status = decision
        interpretation = (
            "Rank-2 ret5 leadership cleared the canonical state-surface paper gate."
        )
        rejection_reason = ""
        next_evidence = (
            "Promote the accepted rank-2 ret5 lead profile only if shared policy and "
            "parity coverage are added; keep live/default orders disabled."
        )
    else:
        decision = "rejected_state_surface_rank2_ret5_lead_notional"
        status = decision
        interpretation = (
            "Rank-2 short-term ret5 leadership is not a promotable follow-on to "
            "the accepted rank-2 ret20 leadership rule. The best non-control "
            "variant improved aggregate EV/PnL, but it failed the tail-aware "
            "promotion discipline because the adjusted sample is thin and "
            "single-ticker positive contribution concentration worsened versus "
            "the accepted baseline."
        )
        rejection_reason = interpretation
        next_evidence = (
            "Do not retry nearby rank-2 ret5, relative volume, or near-high notional "
            "profiles on the frozen state-surface sample. The next valid state-surface "
            "step needs forward replacement-value evidence or a genuinely different "
            "production-visible discriminator."
        )

    delta = parent._aggregate_delta(baseline_metrics, best_payload["metrics"])
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "anti_js": "No JavaScript was used.",
        "lane": "alpha_search",
        "change_type": "state_surface_rotation_rank_quality_notional",
        "changed_variable": "rank2_ret5_lead_rank_notional_profile",
        "single_causal_variable": "rank2_ret5_lead_rank_notional_profile",
        "hypothesis": (
            "After rank-2 ret20 leadership improved the state-surface sleeve, a "
            "shorter ret5 leadership relationship may identify when rank 2 deserves "
            "more paper notional than the accepted rank-quality stack gives it."
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
        },
        "history_check": {
            "exp-20260517-023": "Rejected absolute ret5 floor; this experiment tests relative queue ret5 shape instead.",
            "exp-20260518-013": "Accepted score-compression queue-shape override.",
            "exp-20260518-018": "Accepted rank-2 ret20 leadership override; this locks the baseline and tests a different short-term momentum field.",
        },
        "gate1": {
            "accepted_rank2_ret20_lead_baseline_metrics": baseline_metrics,
            "core_baseline_metrics": core_metrics,
        },
        "gate2": gate2,
        "gate3": {
            "new_filter_added": False,
            "selected_trade_count": best_payload["selected_trade_count"],
            "note": "No candidate filter, core entry filter, or live order path changed.",
        },
        "gate4": best_gate,
        "before_metrics": baseline_metrics,
        "after_metrics": best_payload["metrics"],
        "delta_metrics": delta,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"] for label in WINDOWS
        },
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        },
        "sweep_summary": sweep_summary,
        "best_variant": best,
        "surface_sleeve": best_payload["surface_sleeve"],
        "decision": decision,
        "status": status,
        "interpretation": interpretation,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": next_evidence,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "live_default_orders_changed": False,
            "candidate_ranking_changed": False,
            "candidate_filter_changed": False,
            "paper_notional_changed_if_rejected": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "Ranking/allocation: relative rank-2 ret5 leadership may be a queue-quality field.",
            "2_history_check": "Absolute ret5 floor failed; rank-2 ret20 lead succeeded; this tests a different short-horizon relative field.",
            "3_single_causal_variable": "rank2_ret5_lead_rank_notional_profile",
            "4_acceptance_standard": "Three canonical windows; aggregate EV/PnL positive, >=2 EV-improved windows, zero EV-regressed windows, adjusted trades >=9 across >=2 windows, single-ticker positive share not worse than baseline, absolute concentration guard, and drawdown guard pass.",
            "4_tail_aware_acceptance_standard": "Three canonical windows; aggregate EV/PnL positive, >=2 EV-improved windows, zero EV-regressed windows, adjusted trades >=9 across >=2 windows, single-ticker positive share not worse than baseline, absolute concentration guard, and drawdown guard pass.",
            "5_reproducibility": f".venv/Scripts/python.exe quant/experiments/{Path(__file__).name}",
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(
        json.dumps(
            {
                "anti_js": payload["anti_js"],
                "decision": payload["decision"],
                "experiment_id": EXPERIMENT_ID,
                "best_variant": payload["best_variant"]["variant_name"],
                "aggregate_ev_delta": payload["gate4"]["aggregate_ev_delta"],
                "aggregate_pnl_delta": payload["gate4"]["aggregate_pnl_delta"],
                "windows_ev_improved": payload["gate4"]["windows_ev_improved"],
                "windows_ev_regressed": payload["gate4"]["windows_ev_regressed"],
                "adjusted_trade_count": payload["gate4"][
                    "rank2_ret5_lead_adjusted_trade_count"
                ],
                "adjusted_windows": payload["gate4"][
                    "rank2_ret5_lead_adjusted_windows"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
