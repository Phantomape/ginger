"""exp-20260505-005 positionable entry planning.

Alpha search. Tests whether candidates with zero computed shares should be
removed before scarce-slot planning and slot slicing. This is a candidate
allocation experiment, not a new filter threshold: sizing has already made the
candidate non-positionable, so the only changed variable is whether it can still
consume entry-plan priority.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import production_parity as pp  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-005"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "positionable_entry_planning.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_positionable_entry_planning.md"
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
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("baseline", False),
    ("positionable_before_entry_plan", True),
])


def _shares_to_buy(sig: dict) -> int:
    sizing = sig.get("sizing") or {}
    try:
        return int(sizing.get("shares_to_buy") or 0)
    except (TypeError, ValueError):
        return 0


def _metrics(result: dict) -> dict:
    reasons = (result.get("entry_execution_attribution") or {}).get("reason_counts") or {}
    scarce = result.get("scarce_slot_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "entered": reasons.get("entered", 0),
        "no_shares": reasons.get("no_shares", 0),
        "slot_sliced": reasons.get("slot_sliced", 0),
        "scarce_slot_breakout_deferred": reasons.get(
            "scarce_slot_breakout_deferred", 0
        ),
        "gap_cancel": reasons.get("gap_cancel", 0),
        "adverse_gap_down_cancel": reasons.get("adverse_gap_down_cancel", 0),
        "breakout_deferred": scarce.get("breakout_deferred", 0),
        "by_strategy": result.get("by_strategy") or {},
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
    return out


def _positionable_plan(original_plan):
    def wrapper(
        signals,
        open_positions,
        market_context=None,
        max_positions=pp.MAX_POSITIONS,
        defer_breakout_when_slots_lte=pp.DEFER_BREAKOUT_WHEN_SLOTS_LTE,
        defer_breakout_max_min_index_pct_from_ma=pp.DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA,
        active_positions_count=None,
    ):
        input_signals = list(signals or [])
        dropped = [sig for sig in input_signals if _shares_to_buy(sig) <= 0]
        positionable = [sig for sig in input_signals if _shares_to_buy(sig) > 0]
        planned, audit = original_plan(
            positionable,
            open_positions,
            market_context=market_context,
            max_positions=max_positions,
            defer_breakout_when_slots_lte=defer_breakout_when_slots_lte,
            defer_breakout_max_min_index_pct_from_ma=defer_breakout_max_min_index_pct_from_ma,
            active_positions_count=active_positions_count,
        )
        audit["positionable_entry_planning"] = {
            "signals_before_positionable_filter": len(input_signals),
            "signals_after_positionable_filter": len(positionable),
            "non_positionable_dropped_before_plan": len(dropped),
            "dropped_sample": [
                {
                    "ticker": sig.get("ticker"),
                    "strategy": sig.get("strategy"),
                    "sector": sig.get("sector"),
                    "trade_quality_score": sig.get("trade_quality_score"),
                    "confidence_score": sig.get("confidence_score"),
                    "shares_to_buy": _shares_to_buy(sig),
                    "risk_pct_after": (sig.get("sizing") or {}).get("risk_pct_after"),
                    "risk_multipliers": (
                        (sig.get("sizing") or {}).get("sizing_multipliers") or {}
                    ),
                }
                for sig in dropped[:10]
            ],
        }
        return planned, audit

    return wrapper


def _run_window(universe: list[str], cfg: dict, positionable_plan: bool) -> dict:
    original_pp_plan = pp.plan_entry_candidates
    original_bt_plan = bt.plan_entry_candidates
    if positionable_plan:
        patched = _positionable_plan(original_pp_plan)
        pp.plan_entry_candidates = patched
        bt.plan_entry_candidates = patched
    try:
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        ).run()
    finally:
        pp.plan_entry_candidates = original_pp_plan
        bt.plan_entry_candidates = original_bt_plan

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "entry_execution_attribution": result.get("entry_execution_attribution"),
        "scarce_slot_attribution": result.get("scarce_slot_attribution"),
        "trades": result.get("trades", []),
    }


def _aggregate(by_window: OrderedDict) -> dict:
    baseline_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
    pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
    ev_before = round(sum(v["before"]["expected_value_score"] for v in by_window.values()), 6)
    ev_delta = round(sum(v["delta"]["expected_value_score"] for v in by_window.values()), 6)
    return {
        "expected_value_score_before_sum": ev_before,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / ev_before, 6) if ev_before else None,
        "total_pnl_before_sum": baseline_pnl,
        "total_pnl_delta_sum": pnl_delta,
        "total_pnl_delta_pct": round(pnl_delta / baseline_pnl, 6) if baseline_pnl else None,
        "ev_windows_improved": sum(
            1 for v in by_window.values() if v["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for v in by_window.values() if v["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for v in by_window.values() if v["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for v in by_window.values() if v["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": max(v["delta"]["max_drawdown_pct"] for v in by_window.values()),
        "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
        "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
        "no_shares_delta_sum": sum(v["delta"].get("no_shares", 0) for v in by_window.values()),
        "slot_sliced_delta_sum": sum(v["delta"].get("slot_sliced", 0) for v in by_window.values()),
    }


def _accepted(aggregate: dict) -> bool:
    majority_ev = aggregate["ev_windows_improved"] >= 2 and aggregate["ev_windows_regressed"] == 0
    gate4 = (
        (aggregate["expected_value_score_delta_pct"] or 0) > 0.10
        or (aggregate["total_pnl_delta_pct"] or 0) > 0.05
        or aggregate["max_drawdown_delta_max"] < -0.01
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return bool(majority_ev and gate4)


def _build_artifact(payload: dict) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Positionable Entry Planning",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-window deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | no_shares delta | slot_sliced delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["delta_metrics"]["by_window"].items():
        d = row["delta"]
        lines.append(
            f"| `{label}` | {d['expected_value_score']:+.4f} | "
            f"{d['total_pnl']:+.2f} | {d['sharpe_daily']:+.2f} | "
            f"{d['max_drawdown_pct']:+.4f} | {d['win_rate']:+.4f} | "
            f"{d['trade_count']:+d} | {d.get('no_shares', 0):+d} | "
            f"{d.get('slot_sliced', 0):+d} |"
        )
    lines.extend([
        "",
        "## Aggregate",
        "",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- no_shares delta sum: `{aggregate['no_shares_delta_sum']:+d}`",
        f"- slot_sliced delta sum: `{aggregate['slot_sliced_delta_sum']:+d}`",
        "",
        "## Parity",
        "",
        "No production code was changed by this experiment. If accepted, the rule must be implemented as a shared helper in production_parity.py and called by both backtester.py and run.py before entry planning.",
    ])
    return "\n".join(lines) + "\n"


def _build_payload() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, enabled in VARIANTS.items():
            result = _run_window(universe, cfg, enabled)
            rows.append({
                "window": label,
                "variant": variant,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "positionable_before_entry_plan": enabled,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} no_shares={m['no_shares']} "
                f"slot_sliced={m['slot_sliced']}"
            )

    by_window = OrderedDict()
    for label in WINDOWS:
        baseline = next(
            r for r in rows if r["window"] == label and r["variant"] == "baseline"
        )
        candidate = next(
            r for r in rows
            if r["window"] == label and r["variant"] == "positionable_before_entry_plan"
        )
        by_window[label] = {
            "before": baseline["metrics"],
            "after": candidate["metrics"],
            "delta": _delta(candidate["metrics"], baseline["metrics"]),
        }

    aggregate = _aggregate(by_window)
    accepted = _accepted(aggregate)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "entry_position_allocation",
        "alpha_hypothesis_category": "candidate_allocation",
        "hypothesis": (
            "Candidates whose shared sizing result is zero shares should not "
            "consume scarce-slot planning priority; removing only those already "
            "non-positionable candidates before entry planning may improve "
            "capital allocation without changing signal thresholds, risk "
            "multipliers, or exits."
        ),
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too sparse; this tests "
            "a deterministic candidate-allocation alpha that uses already-audited "
            "sizing output instead."
        ),
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "similar_failed_families": [
                "exp-20260503-012 slot-sliced collision ranking",
                "exp-20260502-011 old_thin strong skipped-candidate insertion",
                "exp-20260430-015 same-sector candidate chooser",
            ],
            "why_not_simple_repeat": (
                "This does not sort by TQS/RS, insert skipped candidates, widen "
                "capacity, or retune breakout deferral. It only asks whether "
                "already-zero-share candidates should be excluded from entry-plan "
                "slot competition."
            ),
        },
        "parameters": {
            "single_causal_variable": "drop zero-share candidates before entry planning",
            "baseline": "all sized signals enter plan_entry_candidates, even if shares_to_buy == 0",
            "tested_variant": "positionable_before_entry_plan",
            "positionable_definition": "sizing.shares_to_buy > 0",
            "locked_variables": [
                "universe",
                "OHLCV snapshots",
                "signal generation",
                "entry filters before sizing",
                "all sizing multipliers",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "scarce-slot breakout deferral thresholds",
                "gap cancels",
                "add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: row["before"] for label, row in by_window.items()
        },
        "after_metrics": {
            label: row["after"] for label, row in by_window.items()
        },
        "delta_metrics": {
            "by_window": by_window,
            "aggregate": aggregate,
        },
        "gate4_basis": (
            "Accepted by multi-window Gate 4."
            if accepted
            else "Rejected: positionable entry planning did not clear multi-window Gate 4."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "temporary_shared_helper_patch_tested": True,
            "promotion_requirement": (
                "If accepted, implement as shared production_parity helper and "
                "call it from both backtester.py and run.py before plan_entry_candidates."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": (
            None
            if accepted
            else "The variant failed EV/PnL materiality or multi-window consistency."
        ),
        "risk_of_change": (
            "If promoted, this may let lower-ranked but positionable candidates "
            "replace zero-risk candidates; the main risk is admitting marginal "
            "late-order candidates that sizing had not directly disqualified."
        ),
        "why_not_other_attractive_points": {
            "event_bundle_promotion": "Positive replay exists, but forward closed outcomes are not available yet.",
            "LLM_soft_ranking": "Still insufficient production-aligned outcome joins.",
            "macro_or_ETF_pool": "Recent macro ETF and energy-pair expansions were rejected.",
            "breakout_deferral_retune": "Recent quality/rank/state variants failed or are explicitly blocked.",
        },
        "do_not_repeat_without_new_evidence": [
            "Dropping zero-share candidates before entry planning if this run fails.",
            "Treating lower no_shares counts as alpha without executed trade improvement.",
        ],
        "next_retry_requires": [
            "A stronger proof that the newly admitted positionable candidates beat the displaced no-share path.",
            "A shared production/backtest helper plus parity test before any promotion.",
        ],
        "related_files": [
            "quant/experiments/exp_20260505_005_positionable_entry_planning.py",
            "data/experiments/exp-20260505-005/positionable_entry_planning.json",
            "experiments/logs/exp-20260505-005.json",
            "experiments/tickets/exp-20260505-005.json",
            "experiments/artifacts/exp-20260505-005_positionable_entry_planning.md",
        ],
        "rows": rows,
    }
    return payload


def main() -> None:
    payload = _build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    TICKET_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    ARTIFACT_MD.write_text(_build_artifact(payload), encoding="utf-8")
    log_record = {k: v for k, v in payload.items() if k != "rows"}
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_record, ensure_ascii=False) + "\n")
    print(f"decision={payload['decision']}")
    print(json.dumps(payload["delta_metrics"]["aggregate"], indent=2))


if __name__ == "__main__":
    main()
