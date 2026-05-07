"""exp-20260506-016: conditional extra slot for sliced SPY leaders.

Alpha search. Prior global capacity attempts were rejected, but the accepted
SPY-relative leader mechanism now has stronger sizing and follow-through
evidence. This replay tests a narrower allocation variable: when the normal
5-position cap slices an otherwise eligible SPY-relative leader, allow one
conditional extra core entry.

The script is replay-only. A passing result must be promoted through
production_parity.plan_entry_candidates before it can affect live orders.
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
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260506-016"
STEM = "spy_leader_extra_slot"
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
JSONL_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

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
    ("spy_leader_extra_slot_all_slices", {
        "require_available_slots_lte": None,
        "strategy_allowlist": None,
    }),
    ("spy_leader_extra_slot_scarce_only", {
        "require_available_slots_lte": 1,
        "strategy_allowlist": None,
    }),
    ("trend_spy_leader_extra_slot_all_slices", {
        "require_available_slots_lte": None,
        "strategy_allowlist": ["trend_long"],
    }),
])

ORIGINAL_PLAN_ENTRY_CANDIDATES = bt.plan_entry_candidates
PROMOTION_EVENTS = []


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


def _is_spy_relative_leader(sig: dict) -> bool:
    if sig.get("spy_relative_leader") is True:
        return True
    sizing = sig.get("sizing") or {}
    multipliers = sizing.get("sizing_multipliers") or sig.get("sizing_multipliers") or {}
    return (
        multipliers.get("spy_relative_leader_risk_on_multiplier_applied", 1.0) > 1.0
    )


def _positionable(sig: dict) -> bool:
    sizing = sig.get("sizing") or {}
    return bool(
        sizing.get("shares_to_buy")
        and sig.get("stop_price")
        and sig.get("target_price")
    )


def _make_patched_plan(variant: dict):
    require_slots_lte = variant.get("require_available_slots_lte")
    allowlist = set(variant.get("strategy_allowlist") or [])

    def _patched_plan_entry_candidates(*args, **kwargs):
        planned, audit = ORIGINAL_PLAN_ENTRY_CANDIDATES(*args, **kwargs)
        slots = audit.get("available_slots", 0)
        if require_slots_lte is not None and slots > require_slots_lte:
            return planned, audit

        sliced = list(audit.get("slot_sliced_signals") or [])
        selected = None
        selected_index = None
        for index, sig in enumerate(sliced):
            if allowlist and sig.get("strategy") not in allowlist:
                continue
            if not _is_spy_relative_leader(sig):
                continue
            if not _positionable(sig):
                continue
            selected = sig
            selected_index = index
            break

        if selected is None:
            return planned, audit

        planned = list(planned) + [selected]
        sliced = [
            sig for index, sig in enumerate(sliced)
            if index != selected_index
        ]
        audit = dict(audit)
        audit["slot_sliced_signals"] = sliced
        audit["signals_after_entry_plan"] = len(planned)
        audit["spy_leader_extra_slot_enabled"] = True
        audit["spy_leader_extra_slot_promoted"] = {
            "ticker": selected.get("ticker"),
            "strategy": selected.get("strategy"),
            "sector": selected.get("sector", "Unknown"),
            "available_slots": slots,
            "original_rank": (slots or 0) + (selected_index or 0) + 1,
            "trade_quality_score": selected.get("trade_quality_score"),
            "confidence_score": selected.get("confidence_score"),
            "shares_to_buy": (selected.get("sizing") or {}).get("shares_to_buy"),
            "risk_multipliers": (
                (selected.get("sizing") or {}).get("sizing_multipliers") or {}
            ),
        }
        PROMOTION_EVENTS.append(dict(audit["spy_leader_extra_slot_promoted"]))
        return planned, audit

    return _patched_plan_entry_candidates


def _run_window(window: dict, variant: dict | None = None) -> tuple[dict, list[dict]]:
    global PROMOTION_EVENTS
    PROMOTION_EVENTS = []
    bt.plan_entry_candidates = (
        _make_patched_plan(variant)
        if variant is not None
        else ORIGINAL_PLAN_ENTRY_CANDIDATES
    )
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
        return engine.run(), list(PROMOTION_EVENTS)
    finally:
        bt.plan_entry_candidates = ORIGINAL_PLAN_ENTRY_CANDIDATES


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


def _entry_stats(result: dict, promotions: list[dict]) -> dict:
    entry = result.get("entry_execution_attribution") or {}
    reason_counts = entry.get("reason_counts") or {}
    promoted_by_ticker = Counter(
        str(event.get("ticker") or "").upper()
        for event in promotions
        if event.get("ticker")
    )
    promoted_by_strategy = Counter(
        str(event.get("strategy") or "unknown")
        for event in promotions
    )
    return {
        "candidate_events": entry.get("candidate_events"),
        "entered_count": entry.get("entered_count"),
        "slot_sliced_count": reason_counts.get("slot_sliced", 0),
        "scarce_slot_breakout_deferred_count": reason_counts.get(
            "scarce_slot_breakout_deferred",
            0,
        ),
        "promoted_count": len(promotions),
        "promoted_by_ticker": dict(sorted(promoted_by_ticker.items())),
        "promoted_by_strategy": dict(sorted(promoted_by_strategy.items())),
        "sample_promotions": promotions[:12],
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
        "promoted_extra_slot_count_sum": sum(
            row["after_entry_stats"]["promoted_count"]
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


def _compact_jsonl_record(payload: dict) -> dict:
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["delta_metrics"]["expected_value_score_delta_sum"],
        "delta_metrics": payload["delta_metrics"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "production_impact": payload["production_impact"],
        "next_retry_requires": payload["next_retry_requires"],
    }


def _write_jsonl_record(record: dict) -> None:
    JSONL_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if JSONL_LOG.exists():
        for line in JSONL_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if existing.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(record, sort_keys=True, ensure_ascii=True))
    JSONL_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _markdown_report(payload: dict) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: SPY-leader extra slot",
        "",
        f"Decision: {payload['decision']}",
        "",
        "## Best Variant",
        "",
        f"- Best: `{payload['best_variant']}`",
        f"- Gate 4 passed: `{payload['gate4']['passed']}`",
        f"- Aggregate EV delta: `{payload['delta_metrics']['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `{payload['delta_metrics']['total_pnl_delta_sum']}`",
        "",
        "## Window Metrics",
        "",
        "| Window | EV before | EV after | PnL delta | Sharpe delta | DD delta | Trades delta | Extra-slot promotions |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["variants"][payload["best_variant"]]["rows"].items():
        lines.append(
            "| {label} | {before_ev} | {after_ev} | {pnl_delta} | {sharpe_delta} | {dd_delta} | {trade_delta} | {promotions} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                pnl_delta=row["delta"]["total_pnl"],
                sharpe_delta=row["delta"]["sharpe_daily"],
                dd_delta=row["delta"]["max_drawdown_pct"],
                trade_delta=row["delta"]["trade_count"],
                promotions=row["after_entry_stats"]["promoted_count"],
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
    baselines = {}
    for label, window in WINDOWS.items():
        raw, promotions = _run_window(window)
        baselines[label] = {
            "metrics": _metrics(raw),
            "entry_stats": _entry_stats(raw, promotions),
        }

    variants = OrderedDict()
    for name, variant in VARIANTS.items():
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            raw, promotions = _run_window(window, variant)
            before = baselines[label]["metrics"]
            after = _metrics(raw)
            rows[label] = {
                "window": window,
                "before": before,
                "after": after,
                "delta": _delta(before, after),
                "before_entry_stats": baselines[label]["entry_stats"],
                "after_entry_stats": _entry_stats(raw, promotions),
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
        "change_type": "scarce_slot_allocation",
        "mechanism_family": "spy_relative_leader_conditional_capacity",
        "hypothesis": (
            "If SPY-relative leaders are the accepted high-quality risk-on sleeve, then "
            "a single conditional sixth core slot for SPY leaders sliced by the standard "
            "5-position cap should improve opportunity capture without generic universe "
            "or capacity expansion."
        ),
        "alpha_hypothesis": {
            "category": "allocation",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking and event-bundle alpha remain sample-limited. Recent "
                "add-on heat and target-width variants are no-go zones, while the playbook "
                "still calls for explicit meta-allocation tests rather than more broad "
                "ticker expansion."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "global MAX_POSITIONS sweeps": (
                    "Rejected or unstable; this run is not a generic capacity increase "
                    "because only slot-sliced SPY-relative leaders are eligible."
                ),
                "exp-20260502-022": (
                    "SPY-relative leader first add-on cap at 60% is accepted; this run "
                    "does not change add-on cap, add-on trigger, or sizing multipliers."
                ),
                "exp-20260506-015": (
                    "Add-on-only heat room was directionally positive but below Gate 4; "
                    "this run moves to scarce-slot allocation instead of retrying nearby "
                    "add-on heat caps."
                ),
            },
            "why_not_simple_repeat": (
                "The tested variable is the entry slot allocator for a pre-existing leader "
                "sleeve. Thresholds, ranking, add-on policy, target width, exits, and "
                "candidate universe remain locked."
            ),
        },
        "parameters": {
            "single_causal_variable": "one conditional extra core entry slot for slot-sliced SPY-relative leaders",
            "baseline": {
                "max_positions": 5,
                "extra_slot_for_sliced_spy_relative_leader": False,
            },
            "tested_variants": VARIANTS,
            "best_variant": best_name,
            "locked_variables": [
                "universe",
                "signal generation",
                "candidate scoring",
                "candidate ordering before slot slicing",
                "entry filters",
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
                "Gate 4 requires material EV/PnL/Sharpe/drawdown improvement or more "
                "trades without win-rate decline, plus EV improvement in at least two "
                "canonical windows and no EV-regressed window."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the extra-slot rule in "
                "production_parity.plan_entry_candidates and add parity coverage before "
                "changing production behavior."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains production-sample limited, so this run tests a "
                "deterministic allocation lever instead of changing LLM duties."
            ),
        },
        "acceptance_reason": (
            "Best variant passed the three-window Gate 4 materiality and stability rules."
            if accepted else None
        ),
        "rejection_reason": (
            None if accepted else
            "The conditional extra-slot leader sleeve did not clear Gate 4. Either the "
            "fifth-slot slice is not the binding opportunity-cost bottleneck, or the "
            "marginal leader candidate is not strong enough without a richer state "
            "discriminator."
        ),
        "next_retry_requires": [
            "Do not retry generic MAX_POSITIONS or nearby sixth-slot variants.",
            "A valid retry needs a materially richer discriminator, such as explicit slot collision PnL attribution or forward evidence that sliced leaders outperform entered candidates.",
            "Any future promotion must live in production_parity.plan_entry_candidates and be covered by run/backtester parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260506_016_spy_leader_extra_slot.py",
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
    _write_jsonl_record(_compact_jsonl_record(payload))

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "title": "SPY-leader extra slot",
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
