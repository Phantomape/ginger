"""exp-20260518-013: state-surface score-dispersion notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
when the accepted rotation-only state-surface queue has compressed top-three
scores on the decision date, use a less rank-1-dominant paper-notional profile.
Core entries, exits, ranking, candidate eligibility, hold days, active
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


EXPERIMENT_ID = "exp-20260518-013"
EXPERIMENT_SLUG = "state_surface_score_dispersion_notional"
BASELINE_VARIANT = "accepted_candidate_breadth_rank_notional"

ACCEPTED_DEFAULT_PROFILE = [1.5, 1.25, 1.0, 0.75, 0.5]
ACCEPTED_CHOP_PROFILE = [1.625, 1.3, 1.0, 0.7, 0.375]
ACCEPTED_CANDIDATE_BREADTH_PROFILE = [1.6625, 1.315, 1.0, 0.675, 0.35]
ACCEPTED_CANDIDATE_BREADTH_MIN = 4
SCORE_COMPRESSION_MIN_BREADTH = 3

SCORE_DISPERSION_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "max_top3_score_spread": None,
                "aggression_order": 0,
                "description": "current accepted candidate-breadth profile",
            },
        ),
        (
            "top3_spread_le_030_rank2_lift",
            {
                "profile": [1.35, 1.45, 1.05, 0.675, 0.35],
                "max_top3_score_spread": 0.30,
                "aggression_order": 1,
                "description": "rank-2 lift only when top-three score spread is <= 0.30",
            },
        ),
        (
            "top3_spread_le_040_flat",
            {
                "profile": [1.45, 1.35, 1.05, 0.675, 0.35],
                "max_top3_score_spread": 0.40,
                "aggression_order": 2,
                "description": "mild flattening when top-three score spread is <= 0.40",
            },
        ),
        (
            "top3_spread_le_040_rank2_lift",
            {
                "profile": [1.35, 1.45, 1.05, 0.675, 0.35],
                "max_top3_score_spread": 0.40,
                "aggression_order": 3,
                "description": "rank-2 lift when top-three score spread is <= 0.40",
            },
        ),
        (
            "top3_spread_le_040_rank2_strong",
            {
                "profile": [1.25, 1.55, 1.10, 0.675, 0.35],
                "max_top3_score_spread": 0.40,
                "aggression_order": 4,
                "description": "strong rank-2 lift when top-three score spread is <= 0.40",
            },
        ),
        (
            "top3_spread_le_050_rank2_lift",
            {
                "profile": [1.35, 1.45, 1.05, 0.675, 0.35],
                "max_top3_score_spread": 0.50,
                "aggression_order": 5,
                "description": "rank-2 lift when top-three score spread is <= 0.50",
            },
        ),
    ]
)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260518_008_state_surface_candidate_breadth_rank_notional as breadth_exp  # noqa: E402


parent = breadth_exp.parent
spy_gate = breadth_exp.spy_gate
rank_exp = breadth_exp.rank_exp
regime_exp = breadth_exp.regime_exp
WINDOWS = breadth_exp.WINDOWS

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


def _score_dispersion_by_day(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        day = str(row.get("decision_date") or "")[:10]
        grouped.setdefault(day, []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for day, day_rows in grouped.items():
        ranked = sorted(
            day_rows,
            key=lambda row: (
                int(row.get("queue_rank") or row.get("rank") or 99),
                -float(row.get("score") or 0.0),
            ),
        )
        scores = [_float(row.get("score")) for row in ranked[:3]]
        scores = [score for score in scores if score is not None]
        top_score = scores[0] if scores else None
        rank2_score = scores[1] if len(scores) >= 2 else None
        rank3_score = scores[2] if len(scores) >= 3 else None
        top_to_second = (
            round(float(top_score) - float(rank2_score), 6)
            if top_score is not None and rank2_score is not None
            else None
        )
        top3_spread = (
            round(float(top_score) - float(rank3_score), 6)
            if top_score is not None and rank3_score is not None
            else None
        )
        out[day] = {
            "score_top": top_score,
            "score_rank2": rank2_score,
            "score_rank3": rank3_score,
            "score_top_to_second_gap": top_to_second,
            "score_top3_spread": top3_spread,
            "score_dispersion_sample_size": len(scores),
        }
    return out


def _baseline_profile_for_trade(
    trade: dict[str, Any],
    regime: str,
) -> tuple[str, list[float]]:
    candidate_breadth = int(trade.get("candidate_breadth") or 0)
    if candidate_breadth >= ACCEPTED_CANDIDATE_BREADTH_MIN:
        return "candidate_breadth_ge4_override", ACCEPTED_CANDIDATE_BREADTH_PROFILE
    if regime == "chop":
        return "chop_override", ACCEPTED_CHOP_PROFILE
    return "default", ACCEPTED_DEFAULT_PROFILE


def _profile_for_trade(
    *,
    variant_name: str,
    variant: dict[str, Any],
    trade: dict[str, Any],
    regime: str,
) -> tuple[str, list[float], bool]:
    baseline_name, baseline_profile = _baseline_profile_for_trade(trade, regime)
    if variant_name == BASELINE_VARIANT or not variant.get("profile"):
        return baseline_name, baseline_profile, False

    max_spread = _float(variant.get("max_top3_score_spread"))
    spread = _float(trade.get("score_top3_spread"))
    candidate_breadth = int(trade.get("candidate_breadth") or 0)
    if (
        max_spread is not None
        and spread is not None
        and spread <= max_spread
        and candidate_breadth >= SCORE_COMPRESSION_MIN_BREADTH
    ):
        threshold_tag = str(max_spread).replace(".", "p")
        return (
            f"score_compression_top3_le_{threshold_tag}",
            list(variant["profile"]),
            True,
        )
    return baseline_name, baseline_profile, False


def _apply_score_dispersion_profile(
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
        profile_name, profile, compression_applied = _profile_for_trade(
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
        row["score_dispersion_rank_notional_variant"] = variant_name
        row["score_dispersion_profile_name"] = profile_name
        row["score_compression_profile_applied"] = compression_applied
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
                "score_top_to_second_gap": trade.get("score_top_to_second_gap"),
                "score_dispersion_profile_name": trade.get("score_dispersion_profile_name"),
                "score_compression_profile_applied": trade.get("score_compression_profile_applied"),
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


def _notional_by_score_profile(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(trade.get("score_dispersion_profile_name") or "unknown")
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
        dispersion_by_day = _score_dispersion_by_day(queued)
        for row in queued:
            day = str(row.get("decision_date") or "")[:10]
            row["candidate_breadth"] = breadth_by_day[day]
            row.update(dispersion_by_day.get(day) or {})
        selected, selection_skipped = parent.base._select_trades(queued)
        adjusted = _apply_score_dispersion_profile(
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
            trade for trade in adjusted if trade.get("score_compression_profile_applied")
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
            "score_compression_adjusted_trade_count": len(adjusted_trades),
            "score_compression_adjusted_pnl": round(
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
            "notional_by_score_dispersion_profile": _notional_by_score_profile(adjusted),
            "surface_summary": parent.base._surface_summary(adjusted),
            "skipped_reason_counts": dict(skipped_reason_counts),
            "selected_trades": _selected_trade_rows(adjusted),
        }

    adjusted_all = [
        trade for trade in selected_all if trade.get("score_compression_profile_applied")
    ]
    adjusted_windows = {
        str(trade.get("window")) for trade in adjusted_all if trade.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "score_dispersion_rank_notional_profile",
        "profile": variant.get("profile"),
        "max_top3_score_spread": variant.get("max_top3_score_spread"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "score_compression_adjusted_trade_count": len(adjusted_all),
        "score_compression_adjusted_windows": sorted(adjusted_windows),
        "single_ticker_positive_share": _single_ticker_positive_share(selected_all),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    variant: dict[str, Any],
) -> dict[str, Any]:
    after_metrics = variant["metrics"]
    delta = parent._aggregate_delta(baseline_metrics, after_metrics)
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["score_compression_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["score_compression_adjusted_windows"]) >= MIN_ADJUSTED_WINDOWS
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
    return {
        "passed": passed,
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "selected_trade_count": variant["selected_trade_count"],
        "minimum_selected_trades": MIN_SELECTED_TRADES,
        "sample_guard_passed": sample_guard_passed,
        "score_compression_adjusted_trade_count": variant[
            "score_compression_adjusted_trade_count"
        ],
        "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
        "score_compression_adjusted_windows": variant["score_compression_adjusted_windows"],
        "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": variant["single_ticker_positive_share"],
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "concentration_guard_passed": concentration_guard_passed,
        "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard_passed,
        "delta_metrics": delta,
    }


def _choose_best(sweep_summary: list[dict[str, Any]]) -> dict[str, Any]:
    non_control = [row for row in sweep_summary if not row["is_identity_control"]]
    passing = [row for row in non_control if row["gate4"]["passed"]]
    if passing:
        return min(
            passing,
            key=lambda row: (
                int(row["aggression_order"]),
                -row["gate4"]["aggregate_ev_delta"],
            ),
        )
    return max(
        non_control,
        key=lambda row: (
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            -row["gate4"]["windows_ev_regressed"],
            -row["gate4"]["max_drawdown_worse_max"],
        ),
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Score-Dispersion Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `score_dispersion_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Max Top3 Spread | Profile | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {spread} | {profile} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                spread=row["max_top3_score_spread"],
                profile=row["profile"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["score_compression_adjusted_trade_count"],
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
                trades=sleeve["score_compression_adjusted_trade_count"],
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
        for variant_name, variant in SCORE_DISPERSION_VARIANTS.items()
    ]
    baseline = next(row for row in variants if row["variant_name"] == BASELINE_VARIANT)
    baseline_metrics = baseline["metrics"]

    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            variant=variant,
        )
        sweep_summary.append(
            {
                "variant_name": variant["variant_name"],
                "profile": variant["profile"],
                "max_top3_score_spread": variant["max_top3_score_spread"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "selected_trade_count": variant["selected_trade_count"],
                "score_compression_adjusted_trade_count": variant[
                    "score_compression_adjusted_trade_count"
                ],
                "score_compression_adjusted_windows": variant[
                    "score_compression_adjusted_windows"
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
        decision = "accepted_shared_default_off_policy_score_dispersion_notional"
        status = "accepted"
        interpretation = (
            "Compressed top-three state-surface queue scores are a production-visible "
            "allocation state. A rank-2 lift improves the accepted default-off paper "
            "sleeve in the fixed windows without changing candidate eligibility, "
            "ranking, hold days, or live/default orders."
        )
    else:
        decision = "rejected_state_surface_score_dispersion_notional"
        status = "rejected"
        interpretation = (
            "No tested score-dispersion paper-notional profile improved the accepted "
            "state-surface candidate-breadth baseline across the fixed-window gate."
        )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_rotation_score_dispersion_notional",
        "changed_variable": "score_dispersion_rank_notional_profile",
        "change_summary": (
            "Sweep a score-dispersion-conditioned paper notional profile for the "
            "accepted default-off rotation state-surface sleeve."
        ),
        "component": "quant/experiments",
        "mechanism_family": "state_aware_candidate_pool_allocation",
        "hypothesis": (
            "When the accepted rotation state-surface queue has tightly compressed "
            "top-three scores, rank-1 leadership is less distinct; shifting a bounded "
            "paper notional slice toward rank 2 should reduce false top-rank dominance "
            "and improve replacement value."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper score-dispersion allocation",
            "playbook_alignment": (
                "Targets state-surface maturation through a new production-visible "
                "rank-quality/crowding field. It avoids LLM soft-ranking data limits, "
                "does not broaden the core candidate pool, and does not change live orders."
            ),
        },
        "history_check": {
            "exp-20260518-002": "Accepted all-regime top-five queue-rank paper notional profile.",
            "exp-20260518-005": "Accepted conservative chop-regime profile.",
            "exp-20260518-008": "Accepted candidate-breadth profile; nearby breadth retunes are now anti-repeat.",
            "anti_repeat_boundary": (
                "This is not another unconditional rank-profile retune; the single new "
                "decision variable is the same-day top-three queue score spread."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: use compressed top-three state-surface queue scores "
                "as a production-visible rank-quality/crowding field before shifting "
                "paper notional from rank 1 toward rank 2."
            ),
            "2_history_check": (
                "Global rank, hold-day, ret20/ret5/ret60, near-high, volume, capacity, "
                "regime-profile, and candidate-breadth experiments are logged. No prior "
                "current-stack run isolated top-three queue score spread."
            ),
            "3_single_causal_variable": "score_dispersion_rank_notional_profile",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; best non-control profile must "
                "improve aggregate EV/PnL versus accepted candidate-breadth rank notional, "
                "improve at least two windows, regress zero windows, keep selected trades "
                f">= {MIN_SELECTED_TRADES}, adjusted trades >= {MIN_ADJUSTED_TRADES} "
                f"across >= {MIN_ADJUSTED_WINDOWS} windows, max drawdown drift <= "
                f"{MAX_DRAWDOWN_WORSE:.1%}, and single-ticker positive share <= "
                f"{MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_013_state_surface_score_dispersion_notional.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "score_dispersion_rank_notional_profile",
            "baseline_variant": BASELINE_VARIANT,
            "accepted_default_profile": ACCEPTED_DEFAULT_PROFILE,
            "accepted_chop_profile": ACCEPTED_CHOP_PROFILE,
            "accepted_candidate_breadth_profile": ACCEPTED_CANDIDATE_BREADTH_PROFILE,
            "accepted_candidate_breadth_min": ACCEPTED_CANDIDATE_BREADTH_MIN,
            "score_compression_min_breadth": SCORE_COMPRESSION_MIN_BREADTH,
            "variants": SCORE_DISPERSION_VARIANTS,
            "best_variant": best_summary["variant_name"],
            "best_score_dispersion_profile": best_summary["profile"],
            "best_max_top3_score_spread": best_summary["max_top3_score_spread"],
            "selection_rule": "least aggressive passing profile; otherwise best EV scout",
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
            "accepted_state_surface_candidate_breadth_baseline_metrics": baseline_metrics,
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
                "state_surface score_top3_spread",
                "state_surface features.ret20_excess_spy",
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
                "state-surface paper notional after queue ranking by using top-three "
                "score spread. The same state_surface_sleeve.py path is used by "
                "production; live/default orders remain disabled."
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
            "Promote the accepted score-dispersion profile in shared state_surface_sleeve.py, "
            "add parity coverage, and continue forward closed replacement-value observation."
            if best_summary["gate4"]["passed"]
            else "Keep the accepted candidate-breadth profile; next state-surface alpha needs a different production-visible discriminator or forward replacement-value evidence."
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
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface score-dispersion notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
            "best_variant": payload["parameters"]["best_variant"],
            "best_score_dispersion_profile": payload["parameters"][
                "best_score_dispersion_profile"
            ],
            "best_max_top3_score_spread": payload["parameters"][
                "best_max_top3_score_spread"
            ],
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
                    "best_score_dispersion_profile": payload["parameters"][
                        "best_score_dispersion_profile"
                    ],
                    "best_max_top3_score_spread": payload["parameters"][
                        "best_max_top3_score_spread"
                    ],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "windows_ev_improved": payload["gate4"]["windows_ev_improved"],
                    "windows_ev_regressed": payload["gate4"]["windows_ev_regressed"],
                    "adjusted_trade_count": payload["gate4"][
                        "score_compression_adjusted_trade_count"
                    ],
                    "adjusted_windows": payload["gate4"][
                        "score_compression_adjusted_windows"
                    ],
                    "single_ticker_positive_share": payload["gate4"][
                        "single_ticker_positive_share"
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
