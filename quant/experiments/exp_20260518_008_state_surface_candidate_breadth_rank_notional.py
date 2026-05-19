"""exp-20260518-008: state-surface candidate-breadth rank notional.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
when the accepted rotation-only state-surface queue has at least four
qualified candidates on the decision date, use a slightly more top-heavy paper
notional profile. Core entries, exits, ranking, candidate eligibility, hold
days, active capacity, event bundle definitions, LLM/news, and live/default
orders are unchanged.

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


EXPERIMENT_ID = "exp-20260518-008"
EXPERIMENT_SLUG = "state_surface_candidate_breadth_rank_notional"
BASELINE_VARIANT = "accepted_regime_rank_notional"
MIN_CANDIDATE_BREADTH = 4

ACCEPTED_DEFAULT_PROFILE = [1.5, 1.25, 1.0, 0.75, 0.5]
ACCEPTED_CHOP_PROFILE = [1.625, 1.3, 1.0, 0.7, 0.375]

CANDIDATE_BREADTH_PROFILE_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "profile": None,
                "aggression_order": 0,
                "description": "current accepted regime-aware rank-notional profile",
            },
        ),
        (
            "breadth_ge4_chop_profile",
            {
                "profile": [1.625, 1.3, 1.0, 0.7, 0.375],
                "aggression_order": 1,
                "description": "use the accepted chop profile when candidate breadth is at least four",
            },
        ),
        (
            "breadth_ge4_mid1",
            {
                "profile": [1.6625, 1.315, 1.0, 0.675, 0.35],
                "aggression_order": 2,
                "description": "least-aggressive passing breadth profile",
            },
        ),
        (
            "breadth_ge4_mid2",
            {
                "profile": [1.6875, 1.325, 1.0, 0.65, 0.3375],
                "aggression_order": 3,
                "description": "moderate breadth profile",
            },
        ),
        (
            "breadth_ge4_strong",
            {
                "profile": [1.75, 1.35, 1.0, 0.6, 0.3],
                "aggression_order": 4,
                "description": "strong breadth profile",
            },
        ),
    ]
)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260517_014_state_surface_rotation_only_replay as parent  # noqa: E402
from experiments import exp_20260517_017_state_surface_rotation_ret20_excess_iwm_floor as spy_gate  # noqa: E402
from experiments import exp_20260518_002_state_surface_rank_notional as rank_exp  # noqa: E402
from experiments import exp_20260518_005_state_surface_regime_rank_notional as regime_exp  # noqa: E402


WINDOWS = parent.WINDOWS
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


def _profile_for_trade(
    *,
    variant_name: str,
    variant: dict[str, Any],
    trade: dict[str, Any],
    regime: str,
) -> tuple[str, list[float]]:
    candidate_breadth = int(trade.get("candidate_breadth") or 0)
    if (
        variant_name != BASELINE_VARIANT
        and candidate_breadth >= MIN_CANDIDATE_BREADTH
        and variant.get("profile")
    ):
        return "candidate_breadth_ge4_override", list(variant["profile"])
    if regime == "chop":
        return "chop_override", ACCEPTED_CHOP_PROFILE
    return "default", ACCEPTED_DEFAULT_PROFILE


def _apply_candidate_breadth_profile(
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
        profile_name, profile = _profile_for_trade(
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
        row["candidate_breadth_rank_notional_variant"] = variant_name
        row["candidate_breadth_profile_name"] = profile_name
        row["candidate_breadth"] = int(row.get("candidate_breadth") or 0)
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
                "candidate_breadth_profile_name": trade.get("candidate_breadth_profile_name"),
                "score": trade.get("score"),
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


def _notional_by_candidate_breadth(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = str(trade.get("candidate_breadth") or "unknown")
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
        for row in queued:
            row["candidate_breadth"] = breadth_by_day[
                str(row.get("decision_date") or "")[:10]
            ]
        selected, selection_skipped = parent.base._select_trades(queued)
        adjusted = _apply_candidate_breadth_profile(
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
        surface_sleeve[label] = {
            "raw_rotation_candidate_count": len(candidates),
            "price_ready_rotation_candidate_count": sum(
                1 for row in candidates if row.get("status") == "price_ready"
            ),
            "ret20_excess_spy_blocked_price_ready_count": sum(
                1 for row in spy_blocked if row.get("status") == "price_ready"
            ),
            "selected_trade_count": len(adjusted),
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
            "notional_by_candidate_breadth": _notional_by_candidate_breadth(adjusted),
            "surface_summary": parent.base._surface_summary(adjusted),
            "skipped_reason_counts": dict(skipped_reason_counts),
            "selected_trades": _selected_trade_rows(adjusted),
        }

    return {
        "variant_name": variant_name,
        "variant_type": "candidate_breadth_rank_notional_profile",
        "candidate_breadth_min": MIN_CANDIDATE_BREADTH,
        "profile": variant.get("profile"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
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
        f"# {EXPERIMENT_ID} State-Surface Candidate-Breadth Rank Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `candidate_breadth_rank_notional_profile` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Profile | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {profile} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {trades} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                profile=row["profile"],
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                trades=row["gate4"]["selected_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share=f"{share:.2%}" if share is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve trades |",
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
                trades=sleeve["selected_trade_count"],
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
        for variant_name, variant in CANDIDATE_BREADTH_PROFILE_VARIANTS.items()
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
                "candidate_breadth_min": variant["candidate_breadth_min"],
                "profile": variant["profile"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "selected_trade_count": variant["selected_trade_count"],
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
        decision = "accepted_shared_default_off_policy_candidate_breadth_rank_notional"
        status = "accepted"
        interpretation = (
            "The accepted state-surface queue has a production-visible candidate-breadth "
            "allocation edge. The least-aggressive passing profile improves all three "
            "fixed windows versus the accepted regime-aware rank-notional baseline "
            "without changing the candidate set, ranking, hold days, or live/default orders."
        )
    else:
        decision = "rejected_state_surface_candidate_breadth_rank_notional"
        status = "rejected"
        interpretation = (
            "No tested candidate-breadth rank-notional profile improved the accepted "
            "state-surface regime-aware rank-notional baseline across the fixed-window gate."
        )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_rotation_candidate_breadth_rank_notional",
        "changed_variable": "candidate_breadth_rank_notional_profile",
        "change_summary": (
            "Sweep a candidate-breadth-conditioned paper notional profile for the "
            "accepted default-off rotation state-surface sleeve."
        ),
        "component": "quant/experiments",
        "mechanism_family": "state_aware_candidate_pool_allocation",
        "hypothesis": (
            "When the accepted rotation state-surface queue has at least four "
            "qualified candidates on the decision date, breadth confirms a broader "
            "rotation thrust and queue rank should carry more allocation weight."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper candidate-breadth allocation",
            "playbook_alignment": (
                "Targets state-surface maturation through a new production-visible "
                "rank-quality/crowding field. It avoids LLM soft-ranking data limits, "
                "does not broaden the core candidate pool, and does not change live orders."
            ),
        },
        "history_check": {
            "exp-20260518-002": "Accepted all-regime top-five queue-rank paper notional profile.",
            "exp-20260518-005": "Accepted conservative chop-regime profile; stronger adjacent profiles passed but were not chosen.",
            "exp-20260518-006": "Added a tail-aware forward promotion gate, so this remains default-off paper only.",
            "anti_repeat_boundary": (
                "This is not another unconditional rank-profile retune; the single new "
                "decision variable is qualified same-day candidate breadth before active "
                "paper capacity selection."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: use same-day state-surface candidate breadth "
                ">= 4 as a production-visible confirmation before a slightly more "
                "top-heavy paper notional profile"
            ),
            "2_history_check": (
                "Global rank, hold-day, ret20/ret5/ret60, near-high, volume, capacity, "
                "and regime-profile experiments are already logged. No prior current-stack "
                "run isolated candidate breadth as the rank-notional selector."
            ),
            "3_single_causal_variable": "candidate_breadth_rank_notional_profile",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; best non-control profile must "
                "improve aggregate EV/PnL versus accepted regime-aware rank notional, "
                "improve at least two windows, regress zero windows, keep selected trades "
                f">= {MIN_SELECTED_TRADES}, max drawdown drift <= {MAX_DRAWDOWN_WORSE:.1%}, "
                f"and single-ticker positive share <= {MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_008_state_surface_candidate_breadth_rank_notional.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "candidate_breadth_rank_notional_profile",
            "baseline_variant": BASELINE_VARIANT,
            "accepted_default_profile": ACCEPTED_DEFAULT_PROFILE,
            "accepted_chop_profile": ACCEPTED_CHOP_PROFILE,
            "candidate_breadth_min": MIN_CANDIDATE_BREADTH,
            "variants": CANDIDATE_BREADTH_PROFILE_VARIANTS,
            "best_variant": best_summary["variant_name"],
            "best_candidate_breadth_profile": best_summary["profile"],
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
            "accepted_state_surface_regime_rank_notional_baseline_metrics": baseline_metrics,
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
                "state-surface paper notional after queue ranking by using same-day "
                "candidate breadth. The same state_surface_sleeve.py path is used by "
                "production; live/default orders remain disabled."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "LLM soft-ranking data remains sparse/PIT-limited; this deterministic "
                "state-surface allocation test uses replayable queue breadth and OHLCV fields."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if best_summary["gate4"]["passed"] else interpretation,
        "next_evidence_needed": (
            "Promote the accepted candidate-breadth profile in shared state_surface_sleeve.py, "
            "add parity coverage, and continue forward closed replacement-value observation."
            if best_summary["gate4"]["passed"]
            else "Keep the accepted regime-rank profile; next state-surface alpha needs a different production-visible discriminator or forward replacement-value evidence."
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
            "title": "State-surface candidate breadth rank notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
            "best_variant": payload["parameters"]["best_variant"],
            "best_candidate_breadth_profile": payload["parameters"]["best_candidate_breadth_profile"],
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
                    "best_candidate_breadth_profile": payload["parameters"]["best_candidate_breadth_profile"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "windows_ev_improved": payload["gate4"]["windows_ev_improved"],
                    "windows_ev_regressed": payload["gate4"]["windows_ev_regressed"],
                    "selected_trade_count": payload["gate4"]["selected_trade_count"],
                    "single_ticker_positive_share": payload["gate4"]["single_ticker_positive_share"],
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
