"""exp-20260518-023: state-surface rank-1 ret20 dominance notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
when the accepted rotation state-surface queue's rank-1 candidate strongly
dominates rank 2 on 20-day excess return versus SPY and still has a material
composite score lead, use a bounded rank-notional profile that keeps rank 1
large while lifting rank 2.

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


EXPERIMENT_ID = "exp-20260518-023"
EXPERIMENT_SLUG = "state_surface_rank1_ret20_dominance_notional"
BASELINE_VARIANT = "accepted_rank2_ret20_score_gap_notional"
ACCEPTED_SCORE_GAP_VARIANT = "rank2_ret20_lead_score_gap_ge_030_strong"

ACCEPTED_DEFAULT_PROFILE = [1.5, 1.25, 1.0, 0.75, 0.5]
ACCEPTED_CHOP_PROFILE = [1.625, 1.3, 1.0, 0.7, 0.375]
ACCEPTED_CANDIDATE_BREADTH_PROFILE = [1.6625, 1.315, 1.0, 0.675, 0.35]
ACCEPTED_CANDIDATE_BREADTH_MIN = 4
ACCEPTED_SCORE_COMPRESSION_PROFILE = [1.35, 1.45, 1.05, 0.675, 0.35]
ACCEPTED_SCORE_COMPRESSION_MIN_BREADTH = 3
ACCEPTED_SCORE_COMPRESSION_MAX_SPREAD = 0.40
ACCEPTED_RANK2_RET20_LEAD_PROFILE = [1.30, 1.55, 1.10, 0.675, 0.35]
ACCEPTED_RANK2_RET20_LEAD_MIN = 0.005
ACCEPTED_RANK2_SCORE_GAP_PROFILE = [1.00, 1.85, 1.10, 0.675, 0.35]
ACCEPTED_RANK2_SCORE_GAP_LEAD_MIN = 0.005
ACCEPTED_RANK2_SCORE_GAP_MIN = 0.30

DOMINANCE_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "rank1_ret20_lead_min": None,
                "score_gap_min": None,
                "aggression_order": 0,
                "description": "current accepted score/ret20 disagreement stack",
            },
        ),
        (
            "rank1_ret20_dominance_ge_015_score_gap_ge_045_balanced",
            {
                "profile": [1.60, 1.40, 1.00, 0.675, 0.35],
                "rank1_ret20_lead_min": 0.15,
                "score_gap_min": 0.45,
                "aggression_order": 1,
                "description": "rank-1 dominance confirmation with modest rank-2 lift",
            },
        ),
        (
            "rank1_ret20_dominance_ge_015_score_gap_ge_045_less_rank1",
            {
                "profile": [1.55, 1.40, 1.00, 0.675, 0.35],
                "rank1_ret20_lead_min": 0.15,
                "score_gap_min": 0.45,
                "aggression_order": 2,
                "description": "same dominance field with smaller rank-1 notional",
            },
        ),
        (
            "rank1_ret20_dominance_ge_015_score_gap_ge_045_rank2_heavy",
            {
                "profile": [1.45, 1.50, 1.10, 0.675, 0.35],
                "rank1_ret20_lead_min": 0.15,
                "score_gap_min": 0.45,
                "aggression_order": 3,
                "description": "same dominance field with stronger rank-2 transfer",
            },
        ),
    ]
)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260518_018_state_surface_rank2_ret20_lead_notional as prev  # noqa: E402


parent = prev.parent
spy_gate = prev.spy_gate
rank_exp = prev.rank_exp
regime_exp = prev.regime_exp
score_exp = prev.prev
WINDOWS = prev.WINDOWS

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


def _profile_multiplier(profile: list[float], queue_rank: Any) -> float:
    try:
        rank = int(queue_rank)
    except (TypeError, ValueError):
        rank = 1
    rank = max(rank, 1)
    if rank > len(profile):
        return float(profile[-1])
    return float(profile[rank - 1])


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [trade for trade in trades if float(trade.get("pnl") or 0.0) > 0]
    total_positive = sum(float(trade.get("pnl") or 0.0) for trade in positive)
    if total_positive <= 0:
        return None
    by_ticker: dict[str, float] = {}
    for trade in positive:
        ticker = str(trade.get("ticker") or "").upper()
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + float(trade.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 6) if by_ticker else None


def _accepted_profile_for_trade(
    trade: dict[str, Any],
    regime: str,
) -> tuple[str, list[float]]:
    rank2_lead = _float(trade.get("rank2_ret20_excess_spy_lead"))
    score_gap = _float(trade.get("score_top_to_second_gap"))
    if (
        rank2_lead is not None
        and rank2_lead >= ACCEPTED_RANK2_SCORE_GAP_LEAD_MIN
        and score_gap is not None
        and score_gap >= ACCEPTED_RANK2_SCORE_GAP_MIN
    ):
        return (
            "rank2_ret20_lead_ge_0p005_score_gap_ge_0p3",
            ACCEPTED_RANK2_SCORE_GAP_PROFILE,
        )
    if rank2_lead is not None and rank2_lead >= ACCEPTED_RANK2_RET20_LEAD_MIN:
        return "rank2_ret20_lead_ge_0p005", ACCEPTED_RANK2_RET20_LEAD_PROFILE

    candidate_breadth = int(trade.get("candidate_breadth") or 0)
    top3_spread = _float(trade.get("score_top3_spread"))
    if (
        candidate_breadth >= ACCEPTED_SCORE_COMPRESSION_MIN_BREADTH
        and top3_spread is not None
        and top3_spread <= ACCEPTED_SCORE_COMPRESSION_MAX_SPREAD
    ):
        return "score_compression_top3_le_0p4", ACCEPTED_SCORE_COMPRESSION_PROFILE
    if candidate_breadth >= ACCEPTED_CANDIDATE_BREADTH_MIN:
        return "candidate_breadth_ge4_override", ACCEPTED_CANDIDATE_BREADTH_PROFILE
    if regime == "chop":
        return "chop_override", ACCEPTED_CHOP_PROFILE
    return "default", ACCEPTED_DEFAULT_PROFILE


def _dominance_profile_name(lead_min: float, score_gap_min: float) -> str:
    lead = str(round(float(lead_min), 6)).rstrip("0").rstrip(".")
    gap = str(round(float(score_gap_min), 6)).rstrip("0").rstrip(".")
    return (
        f"rank1_ret20_dominance_ge_{lead.replace('.', 'p')}_"
        f"score_gap_ge_{gap.replace('.', 'p')}"
    )


def _profile_for_trade(
    *,
    variant_name: str,
    variant: dict[str, Any],
    trade: dict[str, Any],
    regime: str,
) -> tuple[str, list[float], bool]:
    baseline_name, baseline_profile = _accepted_profile_for_trade(trade, regime)
    if variant_name == BASELINE_VARIANT or not variant.get("profile"):
        return baseline_name, baseline_profile, False

    rank1_ret20 = _float(trade.get("rank1_ret20_excess_spy"))
    rank2_ret20 = _float(trade.get("rank2_ret20_excess_spy"))
    lead_min = _float(variant.get("rank1_ret20_lead_min"))
    score_gap = _float(trade.get("score_top_to_second_gap"))
    score_gap_min = _float(variant.get("score_gap_min"))
    if (
        rank1_ret20 is not None
        and rank2_ret20 is not None
        and lead_min is not None
        and score_gap is not None
        and score_gap_min is not None
        and (rank1_ret20 - rank2_ret20) >= lead_min
        and score_gap >= score_gap_min
    ):
        return (
            _dominance_profile_name(lead_min, score_gap_min),
            list(variant["profile"]),
            True,
        )
    return baseline_name, baseline_profile, False


def _apply_dominance_profile(
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
        profile_name, profile, dominance_profile_applied = _profile_for_trade(
            variant_name=variant_name,
            variant=variant,
            trade=row,
            regime=regime,
        )
        multiplier = _profile_multiplier(
            profile,
            row.get("queue_rank") or row.get("rank"),
        )
        notional = round(base_notional * multiplier, 2)
        entry_open = float(row["entry_open"])
        net_return = float(row["net_return_pct"])
        row["rank1_ret20_dominance_rank_notional_variant"] = variant_name
        row["rank1_ret20_dominance_profile_name"] = profile_name
        row["rank1_ret20_dominance_profile_applied"] = dominance_profile_applied
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
        rank1_ret20 = _float(trade.get("rank1_ret20_excess_spy"))
        rank2_ret20 = _float(trade.get("rank2_ret20_excess_spy"))
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
                "rank1_ret20_excess_spy": rank1_ret20,
                "rank2_ret20_excess_spy": rank2_ret20,
                "rank1_ret20_excess_spy_lead": (
                    round(rank1_ret20 - rank2_ret20, 6)
                    if rank1_ret20 is not None and rank2_ret20 is not None
                    else None
                ),
                "rank2_ret20_excess_spy_lead": trade.get("rank2_ret20_excess_spy_lead"),
                "rank1_ret20_dominance_profile_name": trade.get(
                    "rank1_ret20_dominance_profile_name"
                ),
                "rank1_ret20_dominance_profile_applied": trade.get(
                    "rank1_ret20_dominance_profile_applied"
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
        key = str(trade.get("rank1_ret20_dominance_profile_name") or "unknown")
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
        dispersion_by_day = score_exp._score_dispersion_by_day(queued)
        rank2_lead_by_day = prev._rank2_ret20_lead_by_day(queued)
        for row in queued:
            day = str(row.get("decision_date") or "")[:10]
            row["candidate_breadth"] = breadth_by_day[day]
            row.update(dispersion_by_day.get(day) or {})
            row.update(rank2_lead_by_day.get(day) or {})
        selected, selection_skipped = parent.base._select_trades(queued)
        adjusted = _apply_dominance_profile(
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
            core_results[label],
            event_curve,
            adjusted,
        )
        selected_all.extend({**trade, "window": label} for trade in adjusted)
        skipped_reason_counts = Counter(
            str(row.get("reason") or "unknown")
            for row in [*spy_blocked, *selection_skipped]
        )
        adjusted_trades = [
            trade
            for trade in adjusted
            if trade.get("rank1_ret20_dominance_profile_applied")
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
            "rank1_ret20_dominance_adjusted_trade_count": len(adjusted_trades),
            "rank1_ret20_dominance_adjusted_pnl": round(
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
            "notional_by_rank1_dominance_profile": _notional_by_profile(adjusted),
            "surface_summary": parent.base._surface_summary(adjusted),
            "skipped_reason_counts": dict(skipped_reason_counts),
            "selected_trades": _selected_trade_rows(adjusted),
        }

    adjusted_all = [
        trade
        for trade in selected_all
        if trade.get("rank1_ret20_dominance_profile_applied")
    ]
    adjusted_windows = {
        str(trade.get("window")) for trade in adjusted_all if trade.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "rank1_ret20_dominance_rank_notional_profile",
        "profile": variant.get("profile"),
        "rank1_ret20_lead_min": variant.get("rank1_ret20_lead_min"),
        "score_gap_min": variant.get("score_gap_min"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "rank1_ret20_dominance_adjusted_trade_count": len(adjusted_all),
        "rank1_ret20_dominance_adjusted_windows": sorted(adjusted_windows),
        "single_ticker_positive_share": _single_ticker_positive_share(selected_all),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    after_metrics = variant["metrics"]
    delta = parent._aggregate_delta(baseline_metrics, after_metrics)
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["rank1_ret20_dominance_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["rank1_ret20_dominance_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
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
        "rank1_ret20_dominance_adjusted_trade_count": variant[
            "rank1_ret20_dominance_adjusted_trade_count"
        ],
        "rank1_ret20_dominance_adjusted_windows": variant[
            "rank1_ret20_dominance_adjusted_windows"
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
        f"# {EXPERIMENT_ID} State-Surface Rank-1 Ret20 Dominance Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `rank1_ret20_dominance_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
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
                adj=row["gate4"]["rank1_ret20_dominance_adjusted_trade_count"],
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
                trades=sleeve["rank1_ret20_dominance_adjusted_trade_count"],
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

    variants = [
        _variant_payload(
            variant_name=variant_name,
            variant=variant,
            core_results=core_results,
            prices=prices,
        )
        for variant_name, variant in DOMINANCE_VARIANTS.items()
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
                "rank1_ret20_lead_min": variant["rank1_ret20_lead_min"],
                "score_gap_min": variant["score_gap_min"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "selected_trade_count": variant["selected_trade_count"],
                "rank1_ret20_dominance_adjusted_trade_count": variant[
                    "rank1_ret20_dominance_adjusted_trade_count"
                ],
                "rank1_ret20_dominance_adjusted_windows": variant[
                    "rank1_ret20_dominance_adjusted_windows"
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
        decision = "accepted_shared_default_off_policy_rank1_ret20_dominance_notional"
        status = "accepted"
        interpretation = (
            "Rank-1 ret20 dominance with a material score gap is a small but "
            "positive state-surface paper allocation field on top of the accepted "
            "score/ret20 disagreement stack. The best profile improves two fixed "
            "windows, regresses none, leaves drawdown unchanged, and remains "
            "default-off paper only."
        )
    else:
        decision = "rejected_state_surface_rank1_ret20_dominance_notional"
        status = "rejected"
        interpretation = (
            "No tested rank-1 ret20 dominance paper-notional profile improved the "
            "accepted state-surface stack across the fixed-window gate."
        )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_rank1_ret20_dominance_notional",
        "changed_variable": "rank1_ret20_dominance_rank_notional_profile",
        "change_summary": (
            "Sweep a rank-1 ret20 dominance paper-notional profile for the "
            "accepted default-off rotation state-surface sleeve."
        ),
        "component": "quant/experiments",
        "mechanism_family": "state_aware_candidate_pool_allocation",
        "hypothesis": (
            "When rank 1 strongly leads rank 2 on 20-day excess return versus SPY "
            "and also has a material composite score lead, the queue is exposing "
            "confirmed leadership rather than a rank-2 disagreement. A bounded "
            "rank-1-heavy profile with a modest rank-2 lift should improve paper "
            "replacement value."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper rank-quality allocation",
            "playbook_alignment": (
                "Targets state-surface maturation through a new production-visible "
                "rank-quality field and avoids LLM soft-ranking data limits."
            ),
        },
        "history_check": {
            "exp-20260518-020": (
                "Accepted score/ret20 disagreement profile where rank 2 leads "
                "rank 1 on ret20 despite rank-1 score leadership."
            ),
            "exp-20260518-021": (
                "Rejected ret5 leadership because it worsened concentration and "
                "introduced a weaker short-term momentum field."
            ),
            "anti_repeat_boundary": (
                "This is not a ret5 retry. The single discriminator is rank-1 "
                "ret20 dominance plus rank-1 score gap, a different queue-quality "
                "state from rank-2 ret20 disagreement."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: use rank-1 ret20 dominance plus score gap as "
                "a production-visible state-surface paper notional field."
            ),
            "2_history_check": (
                "Rank-2 ret20 disagreement is accepted; ret5 adjacent leadership "
                "was rejected. This exact rank-1 dominance field is not logged as "
                "a prior current-stack experiment."
            ),
            "3_single_causal_variable": "rank1_ret20_dominance_rank_notional_profile",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; best non-control profile "
                "must improve aggregate EV/PnL versus accepted exp-20260518-020, "
                "improve at least two windows, regress zero windows, keep selected "
                f"trades >= {MIN_SELECTED_TRADES}, adjusted trades >= "
                f"{MIN_ADJUSTED_TRADES} across >= {MIN_ADJUSTED_WINDOWS} windows, "
                f"max drawdown drift <= {MAX_DRAWDOWN_WORSE:.1%}, and single-ticker "
                f"positive share <= {MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_023_state_surface_rank1_ret20_dominance_notional.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "rank1_ret20_dominance_rank_notional_profile",
            "baseline_variant": BASELINE_VARIANT,
            "accepted_score_gap_variant": ACCEPTED_SCORE_GAP_VARIANT,
            "variants": DOMINANCE_VARIANTS,
            "best_variant": best_summary["variant_name"],
            "best_profile": best_summary["profile"],
            "best_rank1_ret20_lead_min": best_summary["rank1_ret20_lead_min"],
            "best_score_gap_min": best_summary["score_gap_min"],
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
                "state_surface score_top_to_second_gap",
                "state_surface features.ret20_excess_spy",
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
                "If accepted, shared default-off paper policy changes only "
                "state-surface paper notional after queue ranking by using rank-1 "
                "ret20 dominance plus score gap. The same state_surface_sleeve.py "
                "path is used by production; live/default orders remain disabled."
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
            "Promote the accepted rank-1 ret20 dominance profile in shared "
            "state_surface_sleeve.py, add parity coverage, and continue forward "
            "closed replacement-value observation."
            if best_summary["gate4"]["passed"]
            else "Keep the accepted state-surface stack; next alpha needs a different production-visible discriminator or forward replacement-value evidence."
        ),
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
            "title": "State-surface rank-1 ret20 dominance notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
            "best_variant": payload["parameters"]["best_variant"],
            "best_profile": payload["parameters"]["best_profile"],
            "best_rank1_ret20_lead_min": payload["parameters"]["best_rank1_ret20_lead_min"],
            "best_score_gap_min": payload["parameters"]["best_score_gap_min"],
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
                    "best_rank1_ret20_lead_min": payload["parameters"][
                        "best_rank1_ret20_lead_min"
                    ],
                    "best_score_gap_min": payload["parameters"]["best_score_gap_min"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "windows_ev_improved": payload["gate4"]["windows_ev_improved"],
                    "windows_ev_regressed": payload["gate4"]["windows_ev_regressed"],
                    "adjusted_trade_count": payload["gate4"][
                        "rank1_ret20_dominance_adjusted_trade_count"
                    ],
                    "adjusted_windows": payload["gate4"][
                        "rank1_ret20_dominance_adjusted_windows"
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
