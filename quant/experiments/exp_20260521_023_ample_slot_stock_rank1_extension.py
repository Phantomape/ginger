"""exp-20260521-023: ample-slot stock rank-1 extension.

Alpha search. The accepted production/backtest stack already applies a
1.05x cap-aware top-up to the first planned non-ETF/non-commodity stock
signal when four or more entry slots are open. This runner tests whether
that accepted scalar is under-sized.

This is intentionally experiment-only. If a variant clears the stricter
near-neighbor Gate 4 threshold, promotion must change the shared production
policy and rerun the same three-window protocol.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as bt  # noqa: E402
import exp_20260521_020_ample_slot_stock_rank2_topup as helper  # noqa: E402
import production_parity as pp  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import (  # noqa: E402
    AMPLE_SLOT_STOCK_RANK1_AVAILABLE_SLOTS_MIN,
    AMPLE_SLOT_STOCK_RANK1_EXCLUDED_SECTORS,
    AMPLE_SLOT_STOCK_RANK1_RISK_MULTIPLIER,
    MAX_POSITION_PCT,
)
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260521-023"
STEM = "ample_slot_stock_rank1_extension"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = helper.WINDOWS
BASELINE_MULTIPLIER = AMPLE_SLOT_STOCK_RANK1_RISK_MULTIPLIER
VARIANTS = OrderedDict(
    [
        ("rank1_1p0625x", {"rank1_multiplier": 1.0625}),
        ("rank1_1p075x", {"rank1_multiplier": 1.075}),
        ("rank1_1p10x", {"rank1_multiplier": 1.10}),
    ]
)

MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 6
MIN_AFFECTED_WINDOW_COUNT = 2
MIN_TRADE_COUNT_SUM = 58
MIN_AGGREGATE_EV_DELTA_PCT = 0.10
RANK1_TOPUPS: list[dict[str, Any]] = []


def _apply_rank1_topup(
    signals: list[dict[str, Any]],
    available_slots: int,
    rank1_multiplier: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if (
        available_slots < AMPLE_SLOT_STOCK_RANK1_AVAILABLE_SLOTS_MIN
        or not signals
        or rank1_multiplier <= 1.0
    ):
        return signals, []

    planned = list(signals)
    sig = dict(planned[0])
    sector = sig.get("sector")
    if not sector or sector in AMPLE_SLOT_STOCK_RANK1_EXCLUDED_SECTORS:
        return signals, []

    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return signals, []

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    portfolio_value = float(sizing.get("portfolio_value_usd") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0 or portfolio_value <= 0 or net_risk_per_share <= 0:
        return signals, []

    cap_pct = float(sizing.get("max_position_pct_applied") or MAX_POSITION_PCT)
    desired_shares = max(old_shares, int(math.floor(old_shares * rank1_multiplier)))
    cap_shares = int(math.floor(portfolio_value * cap_pct / entry))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= old_shares:
        return signals, []

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value
    sizing["ample_slot_stock_rank1_state"] = True
    sizing["ample_slot_stock_rank1_available_slots"] = available_slots
    sizing["ample_slot_stock_rank1_baseline_shares"] = old_shares
    sizing["ample_slot_stock_rank1_desired_shares"] = desired_shares
    sizing["ample_slot_stock_rank1_cap_shares"] = cap_shares
    sizing["ample_slot_stock_rank1_new_shares"] = new_shares
    sizing["ample_slot_stock_rank1_risk_multiplier_applied"] = rank1_multiplier
    sig["sizing"] = sizing
    planned[0] = sig

    return planned, [
        {
            "ticker": sig.get("ticker"),
            "strategy": sig.get("strategy"),
            "sector": sector,
            "available_slots": available_slots,
            "baseline_shares": old_shares,
            "desired_shares": desired_shares,
            "cap_shares": cap_shares,
            "new_shares": new_shares,
            "multiplier": rank1_multiplier,
            "trade_quality_score": sig.get("trade_quality_score"),
            "confidence_score": sig.get("confidence_score"),
            "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
            "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
            "price_vs_200ma_extension_state": sig.get("price_vs_200ma_extension_state"),
            "days_to_earnings": sig.get("days_to_earnings"),
            "gap_vulnerability_pct": sig.get("gap_vulnerability_pct"),
        }
    ]


def _make_rank1_wrapper(rank1_multiplier: float):
    def wrapped(signals, available_slots, multiplier=None):
        planned, topups = _apply_rank1_topup(
            signals,
            available_slots,
            rank1_multiplier,
        )
        if topups:
            RANK1_TOPUPS.extend(topups)
        return planned, topups

    return wrapped


def _run_window(
    label: str,
    window: dict[str, Any],
    *,
    rank1_multiplier: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original_ample = pp._apply_ample_slot_stock_rank1_topup
    RANK1_TOPUPS.clear()
    if rank1_multiplier is not None:
        pp._apply_ample_slot_stock_rank1_topup = _make_rank1_wrapper(
            rank1_multiplier,
        )
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        result = engine.run()
        return result, list(RANK1_TOPUPS)
    finally:
        pp._apply_ample_slot_stock_rank1_topup = original_ample
        RANK1_TOPUPS.clear()


def _run_baseline() -> dict[str, dict[str, Any]]:
    return {
        label: _run_window(label, window)[0]
        for label, window in WINDOWS.items()
    }


def _run_variant(
    rank1_multiplier: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: dict[str, dict[str, Any]] = {}
    topups_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, window in WINDOWS.items():
        result, topups = _run_window(
            label,
            window,
            rank1_multiplier=rank1_multiplier,
        )
        results[label] = result
        topups_by_window[label] = topups
    return results, topups_by_window


def _gate4_status(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    topups_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    before_metrics = {label: helper._metrics(result) for label, result in before.items()}
    after_metrics = {label: helper._metrics(result) for label, result in after.items()}
    deltas = {
        label: helper._delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    before_agg = helper._aggregate(before_metrics)
    after_agg = helper._aggregate(after_metrics)
    agg_delta = helper._aggregate_delta(after_metrics, before_metrics)
    baseline_ev = float(before_agg["expected_value_score_sum"] or 0.0)
    ev_delta_pct = (
        float(agg_delta["expected_value_score_sum"] or 0.0) / baseline_ev
        if baseline_ev > 0.0
        else 0.0
    )
    improved_windows = [
        label
        for label, delta in deltas.items()
        if float(delta.get("expected_value_score") or 0.0) > 0.0
    ]
    regressed_windows = [
        label
        for label, delta in deltas.items()
        if float(delta.get("expected_value_score") or 0.0) < 0.0
    ]
    topup_counts = {label: len(rows) for label, rows in topups_by_window.items()}
    affected_signal_count = sum(topup_counts.values())
    affected_window_count = sum(1 for count in topup_counts.values() if count > 0)
    passed = (
        ev_delta_pct >= MIN_AGGREGATE_EV_DELTA_PCT
        and agg_delta["total_pnl_sum"] > 0.0
        and len(improved_windows) >= 2
        and not regressed_windows
        and agg_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and after_agg["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
        and after_agg["survival_rate_min"] >= 0.05
        and affected_signal_count >= MIN_AFFECTED_SIGNAL_COUNT
        and affected_window_count >= MIN_AFFECTED_WINDOW_COUNT
    )
    return {
        "passed": bool(passed),
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "topup_counts": topup_counts,
        "affected_signal_count": affected_signal_count,
        "affected_window_count": affected_window_count,
        "aggregate_delta": agg_delta,
        "aggregate_ev_delta_pct": helper._round(ev_delta_pct, 6),
        "window_deltas": deltas,
        "guardrails": {
            "min_aggregate_ev_delta_pct": MIN_AGGREGATE_EV_DELTA_PCT,
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "min_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "min_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "min_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "min_survival_rate": 0.05,
        },
    }


def _topup_summary(topups_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    tickers: set[str] = set()
    sectors: dict[str, int] = {}
    for rows in topups_by_window.values():
        for row in rows:
            ticker = row.get("ticker")
            if ticker:
                tickers.add(str(ticker))
            sector = str(row.get("sector") or "Unknown")
            sectors[sector] = sectors.get(sector, 0) + 1
    return {
        "count": sum(len(rows) for rows in topups_by_window.values()),
        "window_counts": {label: len(rows) for label, rows in topups_by_window.items()},
        "unique_tickers": sorted(tickers),
        "sector_counts": dict(sorted(sectors.items())),
        "sample": {
            label: rows[:10]
            for label, rows in topups_by_window.items()
            if rows
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                kept.append(line)
    kept.append(json.dumps(record, sort_keys=True, ensure_ascii=False))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Trial accounting",
        f"- trial_family: {payload['trial_family']}",
        f"- changed_variable: {payload['changed_variable']}",
        f"- prior_trial_count: {payload['prior_trial_count']}",
        f"- multiple_testing_risk_bucket: {payload['multiple_testing_risk_bucket']}",
        f"- new_evidence_type: {payload['new_evidence_type']}",
        "",
        "## Three-window aggregate",
        f"- baseline EV: {payload['before_metrics']['aggregate']['expected_value_score_sum']}",
        f"- best EV: {payload['after_metrics']['aggregate']['expected_value_score_sum']}",
        f"- EV delta: {payload['delta_metrics']['aggregate']['expected_value_score_sum']}",
        f"- EV delta pct: {payload['gate4']['aggregate_ev_delta_pct']}",
        f"- PnL delta: {payload['delta_metrics']['aggregate']['total_pnl_sum']}",
        f"- decision: {payload['decision']}",
        "",
        "## Sweep summary",
        "| variant | multiplier | EV delta | EV delta pct | PnL delta | DD delta | affected | windows | passed |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {multiplier} | {ev_delta} | {ev_delta_pct} | {pnl_delta} | {dd_delta} | {affected} | {windows} | {passed} |".format(
                variant=row["variant"],
                multiplier=row["rank1_multiplier"],
                ev_delta=row["gate4"]["aggregate_delta"]["expected_value_score_sum"],
                ev_delta_pct=row["gate4"]["aggregate_ev_delta_pct"],
                pnl_delta=row["gate4"]["aggregate_delta"]["total_pnl_sum"],
                dd_delta=row["gate4"]["aggregate_delta"]["max_drawdown_pct_max"],
                affected=row["gate4"]["affected_signal_count"],
                windows=",".join(row["gate4"]["improved_windows"]),
                passed=row["gate4"]["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Window deltas for selected variant",
            "| window | EV | PnL | DD | survival |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, row in payload["delta_metrics"]["windows"].items():
        lines.append(
            f"| {label} | {row.get('expected_value_score')} | {row.get('total_pnl')} | {row.get('max_drawdown_pct')} | {row.get('survival_rate')} |"
        )
    lines.extend(
        [
            "",
            "## Production impact",
            "```text",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "## Rejection reason / next evidence",
            payload.get("rejection_reason") or "n/a",
            "",
            json.dumps(payload.get("next_retry_requires"), indent=2, ensure_ascii=False),
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    field_check = helper._open_position_field_check()
    baseline_results = _run_baseline()
    before_metrics = {
        label: helper._metrics(result)
        for label, result in baseline_results.items()
    }

    sweep_summary = []
    variant_payloads: dict[str, dict[str, Any]] = {}
    for variant, params in VARIANTS.items():
        after_results, topups_by_window = _run_variant(params["rank1_multiplier"])
        after_metrics = {
            label: helper._metrics(result)
            for label, result in after_results.items()
        }
        gate4 = _gate4_status(baseline_results, after_results, topups_by_window)
        payload = {
            "variant": variant,
            "rank1_multiplier": params["rank1_multiplier"],
            "after_results": after_results,
            "after_metrics": after_metrics,
            "delta_metrics": {
                label: helper._delta(after_metrics[label], before_metrics[label])
                for label in WINDOWS
            },
            "gate4": gate4,
            "topup_summary": _topup_summary(topups_by_window),
        }
        variant_payloads[variant] = payload
        sweep_summary.append(
            {
                "variant": variant,
                "rank1_multiplier": params["rank1_multiplier"],
                "gate4": gate4,
                "topup_summary": payload["topup_summary"],
            }
        )

    def sort_key(item: dict[str, Any]) -> tuple[int, float, float]:
        return (
            1 if item["gate4"]["passed"] else 0,
            float(item["gate4"]["aggregate_delta"]["expected_value_score_sum"]),
            float(item["gate4"]["aggregate_delta"]["total_pnl_sum"]),
        )

    selected_summary = max(sweep_summary, key=sort_key)
    selected = variant_payloads[selected_summary["variant"]]
    selected_after = selected["after_metrics"]
    passed = bool(selected["gate4"]["passed"])
    decision = "candidate_passed_requires_shared_policy_promotion" if passed else "rejected"
    rejection_reason = None
    if not passed:
        if selected["gate4"]["regressed_windows"]:
            rejection_reason = (
                "Best variant failed Gate 4 because at least one standard "
                "window regressed on expected_value_score."
            )
        elif (
            float(selected["gate4"]["aggregate_ev_delta_pct"] or 0.0)
            < MIN_AGGREGATE_EV_DELTA_PCT
        ):
            rejection_reason = (
                "Best variant did not clear the required 10% aggregate EV "
                "lift for a high multiple-testing near-neighbor scalar."
            )
        else:
            rejection_reason = (
                "Best variant did not produce positive aggregate EV/PnL with "
                "all Gate 4 guardrails satisfied."
            )

    delta_aggregate = helper._aggregate_delta(selected_after, before_metrics)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "candidate_passed" if passed else "rejected",
        "decision": decision,
        "hypothesis": (
            "The accepted ample-slot stock rank-1 1.05x top-up may be "
            "under-sized; if rank-1 stock signals are true replacement-value "
            "leaders when four or more slots are open, a modestly higher "
            "cap-aware scalar should improve EV across standard windows."
        ),
        "change_summary": (
            "Sweep an experiment-only replacement for the shared ample-slot "
            "stock rank-1 scalar over 1.0625x, 1.075x, and 1.10x against the "
            "current 1.05x production/backtest baseline."
        ),
        "change_type": "capital_allocation",
        "mechanism_family": "core_slot_allocation",
        "trial_family": "core_ample_slot_stock_rank1_topup_extension",
        "trial_variant_id": selected["variant"],
        "changed_variable": "ample_slot_stock_rank1_risk_multiplier",
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260517-008",
            "exp-20260517-009",
            "exp-20260521-020",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "not_declared",
        "component": "quant/production_parity.py",
        "parameters": {
            "available_slots_min": AMPLE_SLOT_STOCK_RANK1_AVAILABLE_SLOTS_MIN,
            "rank_index": 1,
            "excluded_sectors": list(AMPLE_SLOT_STOCK_RANK1_EXCLUDED_SECTORS),
            "baseline_multiplier": BASELINE_MULTIPLIER,
            "swept_multipliers": [
                params["rank1_multiplier"] for params in VARIANTS.values()
            ],
            "selected_multiplier": selected["rank1_multiplier"],
        },
        "backtest_protocol": "docs/backtesting.md standard_three_window",
        "date_range": {
            "protocol": "docs/backtesting.md standard_three_window",
            "windows": {
                label: {
                    "start": window["start"],
                    "end": window["end"],
                    "snapshot": window["snapshot"],
                    "state_note": window["state_note"],
                }
                for label, window in WINDOWS.items()
            },
        },
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "before_metrics": {
            "windows": before_metrics,
            "aggregate": helper._aggregate(before_metrics),
        },
        "after_metrics": {
            "windows": selected_after,
            "aggregate": helper._aggregate(selected_after),
        },
        "delta_metrics": {
            "windows": selected["delta_metrics"],
            "aggregate": delta_aggregate,
        },
        "expected_value_score_delta": delta_aggregate["expected_value_score_sum"],
        "sweep_summary": sweep_summary,
        "selected_topup_summary": selected["topup_summary"],
        "gate1": {
            "baseline_protocol": "docs/backtesting.md standard three non-overlapping windows",
            "baseline_artifact": str(OUT_JSON),
            "baseline_metrics_readable": True,
        },
        "gate2": {
            "field_check": field_check,
            "rule_dependencies": [
                "planned signal rank after shared entry planning",
                "sector",
                "sizing.shares_to_buy",
                "sizing.entry_price",
                "sizing.portfolio_value_usd",
                "sizing.net_risk_per_share",
                "sizing.max_position_pct_applied",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "survival_rate_min_before": helper._aggregate(before_metrics)[
                "survival_rate_min"
            ],
            "survival_rate_min_after": helper._aggregate(selected_after)[
                "survival_rate_min"
            ],
            "signals_generated_sum_before": helper._aggregate(before_metrics)[
                "signals_generated_sum"
            ],
            "signals_survived_sum_before": helper._aggregate(before_metrics)[
                "signals_survived_sum"
            ],
            "signals_generated_sum_after": helper._aggregate(selected_after)[
                "signals_generated_sum"
            ],
            "signals_survived_sum_after": helper._aggregate(selected_after)[
                "signals_survived_sum"
            ],
        },
        "gate4": selected["gate4"],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "llm_attribution_metric": "not_applicable",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_candidate_passed": (
                "Change AMPLE_SLOT_STOCK_RANK1_RISK_MULTIPLIER in "
                "quant/constants.py, which is consumed by the shared "
                "production_parity policy, then rerun this protocol."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking and SEC fact_tone_gap lanes lack enough "
            "backtest-visible forward rows; recent event reaction, source "
            "complexity, space leader-pool, and rank-2 top-up attempts were "
            "either rejected or sample-limited. This tests a production-visible "
            "core capital-allocation variable instead."
        ),
        "known_risks": [
            "High multiple-testing risk because the 1.05x rank-1 top-up is already accepted.",
            "No new evidence type was declared, so Gate 4 requires a 10% aggregate EV lift.",
            "Experiment-only monkey patch must not be treated as a production policy change.",
        ],
        "rejection_reason": rejection_reason,
        "next_retry_requires": (
            [
                "Do not retry nearby rank-1 ample-slot scalar values without new forward rows or a distinct production-visible feature.",
                "Prefer a different alpha family unless a new replacement-value cohort is identified.",
            ]
            if not passed
            else [
                "Promote selected scalar into quant/constants.py shared policy.",
                "Rerun the same three-window protocol after promotion.",
                "Add or update parity coverage if the shared call surface changes.",
            ]
        ),
        "related_files": [
            "quant/experiments/exp_20260521_023_ample_slot_stock_rank1_extension.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
        "notes": "No JavaScript used. This is alpha_search, not measurement repair.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_variant": result["trial_variant_id"],
                "aggregate_delta": result["delta_metrics"]["aggregate"],
                "aggregate_ev_delta_pct": result["gate4"]["aggregate_ev_delta_pct"],
                "gate4_passed": result["gate4"]["passed"],
                "artifact": str(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )
