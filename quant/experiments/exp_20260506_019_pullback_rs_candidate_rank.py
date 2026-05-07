"""exp-20260506-019: collision-only pullback/60d momentum candidate ranking.

Alpha search. The standalone pullback-RS EOD research file showed positive
cross-sectional rank information, but it was not promoted because it did not
prove slot-aware portfolio value. This replay tests one narrow translation:
when there are more already-qualified core candidates than available slots,
rank only that collision set by point-in-time OHLCV momentum features.

The script is replay-only. A passing result must be promoted through shared
feature/ranking policy before it can affect live orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import feature_layer  # noqa: E402
import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260506-019"
STEM = "pullback_rs_candidate_rank"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy profits but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("collision_rank_momentum_60", {
        "score_field": "momentum_60d_pct",
        "score_description": "higher trailing 60-day return first",
    }),
    ("collision_rank_pullback_rs_60_5", {
        "score_field": "pullback_rs_60_5_score",
        "score_description": "higher 60-day return minus 5-day return first",
    }),
])

ORIGINAL_PLAN_ENTRY_CANDIDATES = bt.plan_entry_candidates
ORIGINAL_COMPUTE_FEATURES = feature_layer.compute_features
ORIGINAL_ENRICH_SIGNALS = risk_engine.enrich_signals
RANK_EVENTS = []


def _round(value, digits=4):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _momentum_pct(ohlcv_data, lookback: int):
    if ohlcv_data is None or len(ohlcv_data) < lookback + 1:
        return None
    try:
        close = float(ohlcv_data["Close"].iloc[-1])
        prior = float(ohlcv_data["Close"].iloc[-lookback - 1])
    except (KeyError, TypeError, ValueError):
        return None
    if prior <= 0:
        return None
    return round((close - prior) / prior, 4)


def _patched_compute_features(ticker, ohlcv_data, earnings_data):
    features = ORIGINAL_COMPUTE_FEATURES(ticker, ohlcv_data, earnings_data)
    if not features:
        return features
    momentum_5 = _momentum_pct(ohlcv_data, 5)
    momentum_60 = _momentum_pct(ohlcv_data, 60)
    features["momentum_5d_pct"] = momentum_5
    features["momentum_60d_pct"] = momentum_60
    if isinstance(momentum_60, (int, float)) and isinstance(momentum_5, (int, float)):
        features["pullback_rs_60_5_score"] = round(momentum_60 - momentum_5, 4)
    else:
        features["pullback_rs_60_5_score"] = None
    return features


def _patched_enrich_signals(signals, features_dict, atr_target_mult=None):
    enriched = ORIGINAL_ENRICH_SIGNALS(
        signals,
        features_dict,
        atr_target_mult=atr_target_mult,
    )
    for sig in enriched:
        features = (features_dict or {}).get(sig.get("ticker")) or {}
        for field in (
            "momentum_5d_pct",
            "momentum_60d_pct",
            "pullback_rs_60_5_score",
        ):
            if field in features:
                sig[field] = features.get(field)
    return enriched


def _score_value(sig: dict, field: str):
    value = sig.get(field)
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    return None


def _make_patched_plan(variant: dict):
    score_field = variant["score_field"]

    def _patched_plan_entry_candidates(signals, *args, **kwargs):
        input_signals = list(signals or [])
        active_positions = kwargs.get("active_positions_count")
        max_positions = kwargs.get("max_positions")
        if active_positions is None:
            active_positions = 0
        if max_positions is None:
            max_positions = 5
        slots = max(0, int(max_positions) - int(active_positions))

        ranked_signals = input_signals
        rank_event = None
        if slots > 0 and len(input_signals) > slots:
            indexed = list(enumerate(input_signals))

            def _rank_key(item):
                original_index, sig = item
                score = _score_value(sig, score_field)
                missing = 1 if score is None else 0
                return (missing, -(score or 0.0), original_index)

            ranked_pairs = sorted(indexed, key=_rank_key)
            ranked_signals = [sig for _, sig in ranked_pairs]
            before_top = input_signals[:slots]
            after_top = ranked_signals[:slots]
            if [s.get("ticker") for s in before_top] != [s.get("ticker") for s in after_top]:
                rank_event = {
                    "score_field": score_field,
                    "available_slots": slots,
                    "candidates": len(input_signals),
                    "before_top": [
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "score": sig.get(score_field),
                        }
                        for sig in before_top
                    ],
                    "after_top": [
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "score": sig.get(score_field),
                        }
                        for sig in after_top
                    ],
                }
                RANK_EVENTS.append(rank_event)

        planned, audit = ORIGINAL_PLAN_ENTRY_CANDIDATES(
            ranked_signals,
            *args,
            **kwargs,
        )
        audit = dict(audit)
        audit["candidate_collision_rank_field"] = score_field
        audit["candidate_collision_rank_applied"] = rank_event is not None
        if rank_event is not None:
            audit["candidate_collision_rank_event"] = rank_event
        return planned, audit

    return _patched_plan_entry_candidates


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _delta(before: dict, after: dict) -> dict:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
        "signals_generated",
        "signals_survived",
    )
    return {
        key: _round((after.get(key) or 0) - (before.get(key) or 0), 6)
        for key in keys
    }


def _entry_stats(result: dict, rank_events: list[dict]) -> dict:
    entry = result.get("entry_execution_attribution") or {}
    reason_counts = entry.get("reason_counts") or {}
    changed_by_field = Counter(
        str(event.get("score_field") or "unknown") for event in rank_events
    )
    return {
        "candidate_events": entry.get("candidate_events"),
        "entered_count": entry.get("entered_count"),
        "slot_sliced_count": reason_counts.get("slot_sliced", 0),
        "scarce_slot_breakout_deferred_count": reason_counts.get(
            "scarce_slot_breakout_deferred",
            0,
        ),
        "rank_changed_collision_count": len(rank_events),
        "rank_changed_by_field": dict(sorted(changed_by_field.items())),
        "sample_rank_events": rank_events[:12],
    }


def _aggregate(rows: dict) -> dict:
    baseline_ev = sum(float(row["before"]["expected_value_score"] or 0) for row in rows.values())
    baseline_pnl = sum(float(row["before"]["total_pnl"] or 0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0) for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(baseline_ev, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / baseline_ev if baseline_ev else 0, 6),
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / baseline_pnl if baseline_pnl else 0, 6),
        "ev_windows_improved": sum(
            1 for row in rows.values()
            if row["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values()
            if row["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values()
            if row["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values()
            if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_min": _round(
            min(row["delta"]["max_drawdown_pct"] for row in rows.values()),
            6,
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()),
            6,
        ),
        "sharpe_daily_delta_min": _round(
            min(row["delta"]["sharpe_daily"] for row in rows.values()),
            6,
        ),
        "sharpe_daily_delta_max": _round(
            max(row["delta"]["sharpe_daily"] for row in rows.values()),
            6,
        ),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in rows.values()),
        "win_rate_delta_min": _round(min(row["delta"]["win_rate"] for row in rows.values()), 6),
        "slot_sliced_delta_sum": sum(
            row["after_entry_stats"]["slot_sliced_count"]
            - row["before_entry_stats"]["slot_sliced_count"]
            for row in rows.values()
        ),
        "entered_delta_sum": sum(
            row["after_entry_stats"]["entered_count"]
            - row["before_entry_stats"]["entered_count"]
            for row in rows.values()
        ),
        "rank_changed_collision_count_sum": sum(
            row["after_entry_stats"]["rank_changed_collision_count"]
            for row in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict) -> bool:
    materiality = (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["total_pnl_delta_pct"] > 0.05
        or aggregate["sharpe_daily_delta_min"] > 0.10
        or aggregate["max_drawdown_delta_min"] < -0.01
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    stability = (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
    )
    return bool(materiality and stability)


def _markdown_report(payload: dict) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: pullback-RS candidate collision rank",
        "",
        f"Decision: {payload['decision']}",
        "",
        "## Best Variant",
        "",
        f"- Best: `{payload['best_variant']}`",
        f"- Gate 4 passed: `{payload['gate4']['passed']}`",
        f"- Aggregate EV delta: `{payload['delta_metrics']['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `{payload['delta_metrics']['total_pnl_delta_sum']}`",
        f"- Rank-changed collisions: `{payload['delta_metrics']['rank_changed_collision_count_sum']}`",
        "",
        "## Window Metrics",
        "",
        "| Window | EV before | EV after | PnL delta | Sharpe delta | DD delta | Trades delta | Rank changes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        lines.append(
            "| {label} | {before_ev} | {after_ev} | {pnl_delta} | {sharpe_delta} | {dd_delta} | {trade_delta} | {rank_changes} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                pnl_delta=row["delta"]["total_pnl"],
                sharpe_delta=row["delta"]["sharpe_daily"],
                dd_delta=row["delta"]["max_drawdown_pct"],
                trade_delta=row["delta"]["trade_count"],
                rank_changes=row["after_entry_stats"]["rank_changed_collision_count"],
            )
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        payload["rejection_reason"] or payload["acceptance_reason"],
        "",
        "Production impact: replay-only experiment. No live order, ranking, sizing, entry policy, or run.py behavior changed.",
        "",
    ])
    return "\n".join(lines)


def _run_window(window: dict, variant: dict | None = None) -> tuple[dict, list[dict]]:
    global RANK_EVENTS
    RANK_EVENTS = []
    if variant is None:
        bt.plan_entry_candidates = ORIGINAL_PLAN_ENTRY_CANDIDATES
        feature_layer.compute_features = ORIGINAL_COMPUTE_FEATURES
        risk_engine.enrich_signals = ORIGINAL_ENRICH_SIGNALS
    else:
        bt.plan_entry_candidates = _make_patched_plan(variant)
        feature_layer.compute_features = _patched_compute_features
        risk_engine.enrich_signals = _patched_enrich_signals
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
            include_pilot_sleeve=False,
        )
        return engine.run(), list(RANK_EVENTS)
    finally:
        bt.plan_entry_candidates = ORIGINAL_PLAN_ENTRY_CANDIDATES
        feature_layer.compute_features = ORIGINAL_COMPUTE_FEATURES
        risk_engine.enrich_signals = ORIGINAL_ENRICH_SIGNALS


def main() -> int:
    baselines = {}
    for label, window in WINDOWS.items():
        raw, rank_events = _run_window(window)
        baselines[label] = {
            "metrics": _metrics(raw),
            "entry_stats": _entry_stats(raw, rank_events),
        }

    variants = OrderedDict()
    for name, variant in VARIANTS.items():
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            raw, rank_events = _run_window(window, variant)
            before = baselines[label]["metrics"]
            after = _metrics(raw)
            rows[label] = {
                "window": window,
                "before": before,
                "after": after,
                "delta": _delta(before, after),
                "before_entry_stats": baselines[label]["entry_stats"],
                "after_entry_stats": _entry_stats(raw, rank_events),
            }
        aggregate = _aggregate(rows)
        variants[name] = {
            "parameters": variant,
            "rows": rows,
            "aggregate": aggregate,
            "gate4_passed": _gate4_passed(aggregate),
        }

    ranked = sorted(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
        reverse=True,
    )
    best_name, best = ranked[0]
    accepted = best["gate4_passed"]
    decision = "accepted_for_promotion" if accepted else "rejected"
    generated_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "candidate_collision_ranking",
        "mechanism_family": "pullback_rs_eod_to_slot_allocator",
        "hypothesis": (
            "If the standalone pullback-RS EOD research contains transferable "
            "cross-sectional information, then using 60-day momentum or 60-day "
            "momentum minus 5-day return to break scarce-slot candidate collisions "
            "should improve aggregate EV without adding tickers or filters."
        ),
        "alpha_hypothesis": {
            "category": "ranking",
            "entry_exit_ranking_or_allocation": "ranking",
            "why_this_now": (
                "LLM soft-ranking, event-bundle promotion, broad universe expansion, "
                "single-name mining, generic slot unlocks, and nearby add-on/breakout "
                "variants are either data-limited or recently rejected. This tests a "
                "deterministic OHLCV ranking signal from an existing research artifact."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "experiments/research/pullback_rs_eod": (
                    "Observed promising standalone rank IC/top-bottom spread, but "
                    "not promoted due survivorship and no slot-aware integration."
                ),
                "exp-20260505-018": (
                    "Breakout-only RS/confidence/52w ranking variants were rejected; "
                    "this run is not a breakout subsequence order and only fires when "
                    "the shared entry planner has more core candidates than slots."
                ),
                "global pre-slot sorting family": (
                    "Prior broad candidate sorting was unstable; this run restricts "
                    "the tested variable to two research-backed OHLCV scores and "
                    "records collision changes explicitly."
                ),
            },
            "why_not_simple_repeat": (
                "The causal variable is a point-in-time OHLCV score applied only to "
                "candidate-slot collisions. Universe, signal generation, filters, "
                "sizing, exits, add-ons, LLM/news replay, and slot capacity remain locked."
            ),
        },
        "parameters": {
            "single_causal_variable": "collision-only candidate rank by OHLCV pullback/60d momentum score",
            "baseline": {
                "collision_rank_field": None,
                "feature_fields_added": [],
            },
            "tested_variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "MAX_POSITIONS",
                "MAX_PER_SECTOR",
                "sizing multipliers",
                "MAX_POSITION_PCT",
                "portfolio heat cap",
                "add-on policy",
                "exit policy",
                "LLM/news replay",
                "pilot sleeve",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {label: data["metrics"] for label, data in baselines.items()},
        "after_metrics": {
            label: row["after"] for label, row in best["rows"].items()
        },
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in best["rows"].items()},
            **best["aggregate"],
        },
        "variants": variants,
        "best_variant": best_name,
        "gate4": {
            "passed": accepted,
            "basis": (
                "Gate 4 requires material EV/PnL/Sharpe/drawdown improvement or "
                "more trades without win-rate decline, plus EV improvement in at "
                "least two canonical windows and no EV-regressed window."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, promote the feature fields and collision ranking "
                "through shared feature/ranking policy used by both backtester.py "
                "and run.py before changing production behavior."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this run deliberately "
                "uses deterministic OHLCV data instead of changing LLM duties."
            ),
        },
        "acceptance_reason": (
            "Best variant passed the three-window Gate 4 materiality and stability rules."
            if accepted else None
        ),
        "rejection_reason": (
            None if accepted else
            "The research-backed pullback/60d score did not clear Gate 4 in the "
            "slot-aware entry planner. Either the standalone rank IC does not "
            "survive portfolio collision costs, or this score needs a different "
            "state/context discriminator before it can improve live allocation."
        ),
        "next_retry_requires": [
            "Do not retry nearby raw 60-day momentum or 60-minus-5 collision sorting variants.",
            "A valid retry needs a new discriminator such as regime/state conditioning or closed-trade attribution showing that sliced high-score candidates outperform entered low-score candidates.",
            "Any future promotion must be shared by backtester.py and run.py, with parity coverage, before live behavior changes.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260506_019_pullback_rs_candidate_rank.py",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(payload, indent=2, ensure_ascii=True)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    ARTIFACT_MD.write_text(_markdown_report(payload), encoding="utf-8")

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "title": "Pullback-RS collision rank",
        "summary": f"Best {best_name}; Gate4={accepted}",
        "best_variant": best_name,
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    TICKET_JSON.write_text(
        json.dumps(ticket, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    print(f"{EXPERIMENT_ID} {decision} best={best_name}")
    print(json.dumps(ticket["delta_metrics"], indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
