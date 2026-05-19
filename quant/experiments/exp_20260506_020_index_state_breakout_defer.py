"""exp-20260506-020: index-state gated scarce-slot breakout deferral.

Alpha search. The accepted one-slot breakout defer rule is a narrow
meta-allocation rule, but prior diagnostics showed deferred breakouts are not
uniformly bad. This replay tests the pre-existing shared state hook:
only defer one-slot breakout entries when the weaker of SPY/QQQ is not far
above its 200-day average.

The script is replay-only. A passing result must be promoted by changing the
shared constant used by both production_parity.py and backtester.py.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260506-020"
STEM = "index_state_breakout_defer"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
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
    ("defer_when_index_le_0pct_from_ma", {
        "defer_breakout_max_min_index_pct_from_ma": 0.00,
        "description": "defer only when either SPY or QQQ is at/below its 200-day average",
    }),
    ("defer_when_index_le_5pct_from_ma", {
        "defer_breakout_max_min_index_pct_from_ma": 0.05,
        "description": "defer when the weaker index is no more than 5% above its 200-day average",
    }),
    ("defer_when_index_le_10pct_from_ma", {
        "defer_breakout_max_min_index_pct_from_ma": 0.10,
        "description": "defer when the weaker index is no more than 10% above its 200-day average",
    }),
    ("defer_when_index_le_15pct_from_ma", {
        "defer_breakout_max_min_index_pct_from_ma": 0.15,
        "description": "defer when the weaker index is no more than 15% above its 200-day average",
    }),
])


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


def _entry_stats(result: dict) -> dict:
    entry = result.get("entry_execution_attribution") or {}
    reason_counts = entry.get("reason_counts") or {}
    deferred = entry.get("scarce_slot_deferred_events") or []
    min_index_values = [
        event.get("min_index_pct_from_ma")
        for event in deferred
        if event.get("min_index_pct_from_ma") is not None
    ]
    by_ticker = Counter(
        str(event.get("ticker") or "UNKNOWN").upper()
        for event in deferred
    )
    return {
        "candidate_events": entry.get("candidate_events"),
        "entered_count": entry.get("entered_count"),
        "slot_sliced_count": reason_counts.get("slot_sliced", 0),
        "scarce_slot_breakout_deferred_count": reason_counts.get(
            "scarce_slot_breakout_deferred",
            0,
        ),
        "deferred_tickers": dict(sorted(by_ticker.items())),
        "deferred_min_index_pct_from_ma_min": _round(min(min_index_values), 4) if min_index_values else None,
        "deferred_min_index_pct_from_ma_max": _round(max(min_index_values), 4) if min_index_values else None,
        "sample_deferred_events": deferred[:12],
    }


def _run_window(window: dict, variant: dict | None = None) -> dict:
    config = {
        "REGIME_AWARE_EXIT": True,
        "REPLAY_PARTIAL_REDUCES": True,
    }
    if variant is not None:
        config["DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA"] = variant[
            "defer_breakout_max_min_index_pct_from_ma"
        ]
    engine = BacktestEngine(
        sorted(get_universe()),
        start=window["start"],
        end=window["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        include_pilot_sleeve=False,
    )
    return engine.run()


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
        "deferred_breakout_delta_sum": sum(
            row["after_entry_stats"]["scarce_slot_breakout_deferred_count"]
            - row["before_entry_stats"]["scarce_slot_breakout_deferred_count"]
            for row in rows.values()
        ),
        "slot_sliced_delta_sum": sum(
            row["after_entry_stats"]["slot_sliced_count"]
            - row["before_entry_stats"]["slot_sliced_count"]
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
        f"# {EXPERIMENT_ID}: index-state gated breakout defer",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Best Variant",
        "",
        f"- Best: `{payload['best_variant']}`",
        f"- Gate 4 passed: `{payload['gate4']['passed']}`",
        f"- Aggregate EV delta: `{payload['delta_metrics']['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `{payload['delta_metrics']['total_pnl_delta_sum']}`",
        f"- Deferred breakout delta: `{payload['delta_metrics']['deferred_breakout_delta_sum']}`",
        "",
        "## Window Metrics",
        "",
        "| Window | EV before | EV after | PnL delta | Sharpe delta | DD delta | Deferred delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        lines.append(
            "| {label} | {before_ev} | {after_ev} | {pnl_delta} | {sharpe_delta} | {dd_delta} | {defer_delta} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                pnl_delta=row["delta"]["total_pnl"],
                sharpe_delta=row["delta"]["sharpe_daily"],
                dd_delta=row["delta"]["max_drawdown_pct"],
                defer_delta=(
                    row["after_entry_stats"]["scarce_slot_breakout_deferred_count"]
                    - row["before_entry_stats"]["scarce_slot_breakout_deferred_count"]
                ),
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


def main() -> int:
    baselines = OrderedDict()
    for label, window in WINDOWS.items():
        raw = _run_window(window)
        baselines[label] = {
            "metrics": _metrics(raw),
            "entry_stats": _entry_stats(raw),
        }

    variants = OrderedDict()
    for name, variant in VARIANTS.items():
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            raw = _run_window(window, variant)
            before = baselines[label]["metrics"]
            after = _metrics(raw)
            rows[label] = {
                "window": window,
                "before": before,
                "after": after,
                "delta": _delta(before, after),
                "before_entry_stats": baselines[label]["entry_stats"],
                "after_entry_stats": _entry_stats(raw),
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
        "change_type": "state_conditioned_meta_allocation",
        "mechanism_family": "index_state_gated_scarce_slot_breakout_defer",
        "hypothesis": (
            "The accepted one-slot breakout defer rule should create more EV if it "
            "fires only when cap-weight index state is not already strongly above "
            "trend. In very strong index states, taking the current breakout may be "
            "better than preserving a slot for later candidates."
        ),
        "alpha_hypothesis": {
            "category": "allocation / ranking",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft ranking and event overlay promotion are sample-limited, "
                "broad universe growth and recent single-name expansions were rejected, "
                "and the playbook names mid_weak meta-allocation as the cleanest "
                "unblocked alpha surface."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260427-028": (
                    "Unconditional one-slot breakout defer is accepted and modestly "
                    "positive in mid_weak/old_thin."
                ),
                "exp-20260427-021": (
                    "Simple market-regime allowlists were rejected; this run uses the "
                    "pre-existing continuous SPY/QQQ distance-from-MA hook instead."
                ),
                "exp-20260427-025": (
                    "Simple breadth thresholds failed; this run tests cap-weight index "
                    "trend state, not breadth-above-SMA."
                ),
                "exp-20260506-019": (
                    "Pullback/60d collision ranking failed; this run does not reorder "
                    "candidates and only changes when the accepted defer hook fires."
                ),
            },
            "why_not_simple_repeat": (
                "The only causal variable is the existing shared "
                "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA guard. Universe, signal "
                "generation, entry filters, ranking, sizing, exits, add-ons, LLM/news, "
                "and slot count remain locked."
            ),
        },
        "parameters": {
            "single_causal_variable": "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA",
            "baseline": {
                "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 1,
                "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": None,
            },
            "tested_variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ordering",
                "MAX_POSITIONS",
                "MAX_PER_SECTOR",
                "sizing multipliers",
                "position caps",
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
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, promote by changing quant/constants.py only; "
                "production_parity.plan_entry_candidates is already the shared "
                "run/backtester path for this guard."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains production-sample limited, so this run "
                "tests a deterministic shared meta-allocation lever instead of "
                "changing LLM duties."
            ),
        },
        "acceptance_reason": (
            "Best variant passed the three-window Gate 4 materiality and stability rules."
            if accepted else None
        ),
        "rejection_reason": (
            None if accepted else
            "Index-distance gating did not improve the accepted one-slot breakout "
            "defer rule enough to clear Gate 4. The accepted unconditional hook "
            "remains the best tested version; do not retry nearby SPY/QQQ "
            "distance-from-MA thresholds without a richer capacity-timing signal."
        ),
        "next_retry_requires": [
            "Do not retry nearby SPY/QQQ pct-from-200MA thresholds as a simple guard.",
            "A valid retry needs a richer capacity-timing discriminator, such as closed opportunity-cost evidence or sector/dispersion state that explains later-candidate value.",
            "Any future promotion must use the shared production_parity path and add parity coverage if the shared helper changes.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260506_020_index_state_breakout_defer.py",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    ARTIFACT_MD.write_text(_markdown_report(payload), encoding="utf-8")

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "title": "Index-state breakout defer",
        "summary": f"Best {best_name}; Gate4={accepted}",
        "best_variant": best_name,
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    TICKET_JSON.write_text(
        json.dumps(ticket, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"{EXPERIMENT_ID} {decision} best={best_name}")
    print(json.dumps(ticket["delta_metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
