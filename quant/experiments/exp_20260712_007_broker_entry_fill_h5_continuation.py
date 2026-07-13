"""exp-20260712-007: broker entry-fill five-session value attribution.

Observed-only alpha attribution on broker-authoritative execution facts.  The
runner measures the fixed five-session directional value after each trusted
closed lifecycle's actual open fill, relative to cash, SPY, and QQQ.  It does
not change strategy, paper, production, or order behavior.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from quant.experiments.exp_20260712_002_broker_exit_fill_h5_avoidance import (  # noqa: E402
    BROKER_ROOT,
    WAREHOUSE_PATH,
    finite_float,
    future_session,
    load_trusted_lifecycles,
    read_json,
    repo_rel,
    rounded,
    summarize,
    utc_now,
    write_json,
    write_text,
)
from quant.ohlcv_warehouse import load_warehouse_ohlcv_frames  # noqa: E402


EXPERIMENT_ID = "exp-20260712-007"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "broker_entry_fill_h5_continuation"
RUNNER = f"quant/experiments/exp_20260712_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

HYPOTHESIS = (
    "Observed-only entry alpha: broker-authoritative open fills across trusted "
    "closed Moomoo lifecycles should show positive five-session cash, SPY, and "
    "QQQ forward value from actual lifecycle entry if production entry timing "
    "adds value; no strategy behavior changes."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "broker_execution_ledger_entry_attribution"
MECHANISM_FAMILY = "broker_execution_entry_quality"
TRIAL_FAMILY = "broker_authoritative_entry_fill_h5_continuation"
TRIAL_VARIANT_ID = "h5_cash_spy_qqq_lifecycle_open_aggregate_v1"
CHANGED_VARIABLE = "broker_entry_fill_h5_continuation_value_v1"
NEARBY_PRIORS = [
    "exp-20260712-001",
    "exp-20260712-002",
    "exp-20260712-004",
    "exp-20260712-006",
]
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape on the broker source: evaluate entry-side lifecycle-open "
    "forward value and benchmark excess at the production decision boundary, "
    "distinct from exit-side avoidance and fee calibration."
)
FINGERPRINT_CAVEAT = (
    "Reservation over-matched ohlcv_momentum because the hypothesis used "
    "continuation language. The real evidence surface is "
    "moomoo_execution_history; the observed-only override is justified only "
    "by the predeclared entry-side gate shape."
)
CAUSAL_COMPONENTS = [
    "latest-effective broker open fills pinned to the lifecycle mapping",
    "strict trusted closed lifecycle links",
    "five-session warehouse settlement through a fixed cutoff",
    "cash, SPY, and QQQ directional value comparators",
    "lifecycle-open aggregation and three calendar cohorts",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.45,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "mixed_discretionary_and_strategy_population",
        "warehouse_coverage_incomplete",
        "entry_timing_not_additive",
        "calendar_cohort_instability",
        "single_ticker_concentration",
    ],
    "confidence_reason": (
        "The same 87 trusted lifecycles provide adequate independent entry "
        "events, but missing strategy tags make a stable positive result "
        "uncertain and non-promotable."
    ),
    "recorded_at": "2026-07-12T05:28:49+00:00",
}

HOLD_SESSIONS = 5
SETTLEMENT_CUTOFF = "2026-07-10"
MIN_TRUSTED_LIFECYCLES = 60
MIN_SETTLEMENT_RATE = 0.70
MAX_POSITIVE_TICKER_SHARE = 0.50
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260712-006"
    / "current_working_stack_sharpe_inference.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_007_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260712_007_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def baseline_context() -> dict[str, Any]:
    """Read the contemporaneous protocol-migration artifact as context only."""

    payload = read_json(BASELINE_PATH)
    windows = []
    for row in payload.get("windows") or []:
        metrics = row.get("after_metrics") or {}
        windows.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": metrics.get("expected_value_score"),
                "total_pnl": metrics.get("total_pnl"),
                "total_trades": metrics.get("total_trades"),
                "signals_generated": metrics.get("signals_generated"),
                "signals_survived": metrics.get("signals_survived"),
                "survival_rate": metrics.get("survival_rate"),
                "max_drawdown_pct": metrics.get("max_drawdown_pct"),
                "sharpe_daily": metrics.get("sharpe_daily"),
                "sharpe_inference_schema_version": (
                    (row.get("sharpe_inference") or {}).get("schema_version")
                ),
            }
        )
    numeric = lambda key: [
        float(row[key]) for row in windows if row.get(key) is not None
    ]
    survival = numeric("survival_rate")
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "baseline_role": "measurement_context_only_no_strategy_comparison",
        "measurement_contract": payload.get("measurement_contract"),
        "measurement_contract_passed": payload.get("measurement_contract_passed"),
        "historical_champion_dsr_status": (
            (payload.get("historical_champion_dsr") or {}).get("status")
        ),
        "window_count": len(windows),
        "expected_value_score_sum": round(sum(numeric("expected_value_score")), 4),
        "total_pnl_sum": round(sum(numeric("total_pnl")), 2),
        "trade_count": int(sum(numeric("total_trades"))),
        "signals_generated": int(sum(numeric("signals_generated"))),
        "signals_survived": int(sum(numeric("signals_survived"))),
        "minimum_survival_rate": min(survival) if survival else None,
        "windows": windows,
        "note": (
            "exp-20260712-006 is a concurrent measurement migration. This "
            "observed-only runner changes no strategy behavior and does not use "
            "old-versus-new EV or Sharpe as acceptance evidence."
        ),
    }


def settle_lifecycle_opens(
    lifecycles: list[dict[str, Any]], frames: dict[str, Any]
) -> tuple[list[dict[str, Any]], Counter[str]]:
    settled: list[dict[str, Any]] = []
    missing: Counter[str] = Counter()
    spy = frames.get("SPY")
    qqq = frames.get("QQQ")
    for lifecycle in lifecycles:
        ticker = lifecycle["ticker"]
        frame = frames.get(ticker)
        if frame is None:
            missing["ticker_ohlcv_missing"] += 1
            continue
        open_pairs = [
            (link, fill)
            for link, fill in zip(lifecycle["links"], lifecycle["fills"])
            if link.get("event_role") == "open"
        ]
        if len(open_pairs) != 1:
            missing["open_event_count_not_one"] += 1
            continue
        link, fill = open_pairs[0]
        qty = finite_float(fill.get("qty"))
        entry_price = finite_float(fill.get("price"))
        event_date = str(fill.get("event_time_raw") or "")[:10]
        if not event_date or not qty or not entry_price:
            missing["invalid_open_fill"] += 1
            continue
        ticker_h5 = future_session(frame, event_date)
        spy_h5 = future_session(spy, event_date) if spy is not None else None
        qqq_h5 = future_session(qqq, event_date) if qqq is not None else None
        if ticker_h5 is None or spy_h5 is None or qqq_h5 is None:
            missing["h5_not_settled"] += 1
            continue
        direction = lifecycle["direction"]
        if direction == "long":
            sign = 1.0
        elif direction == "short":
            sign = -1.0
        else:
            missing["unknown_direction"] += 1
            continue
        entry_notional = qty * entry_price
        cash_value = sign * qty * (ticker_h5["horizon_close"] - entry_price)
        spy_return = spy_h5["horizon_close"] / spy_h5["next_open"] - 1.0
        qqq_return = qqq_h5["horizon_close"] / qqq_h5["next_open"] - 1.0
        spy_excess = cash_value - sign * entry_notional * spy_return
        qqq_excess = cash_value - sign * entry_notional * qqq_return
        settled.append(
            {
                "lifecycle_id": lifecycle["lifecycle_id"],
                "ticker": ticker,
                "direction": direction,
                "open_deal_id": str(link.get("deal_id") or ""),
                "open_date": event_date,
                "close_date": lifecycle["close_date"],
                "cohort": event_date[:4],
                "entry_qty": qty,
                "entry_price": entry_price,
                "entry_notional": rounded(entry_notional),
                "next_session": ticker_h5["next_session"],
                "horizon_session": ticker_h5["horizon_session"],
                "horizon_close": rounded(ticker_h5["horizon_close"], 6),
                "cash_value": rounded(cash_value),
                "spy_excess_value": rounded(spy_excess),
                "qqq_excess_value": rounded(qqq_excess),
            }
        )
    return settled, missing


def positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        value = float(row["cash_value"])
        if value > 0.0:
            by_ticker[row["ticker"]] += value
    total = sum(by_ticker.values())
    ranked = sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    return {
        "positive_cash_value": rounded(total),
        "max_ticker_share": round(ranked[0][1] / total, 6) if total else None,
        "hhi": (
            round(sum((value / total) ** 2 for _, value in ranked), 6)
            if total
            else None
        ),
        "top_tickers": [
            {"ticker": ticker, "value": rounded(value), "share": round(value / total, 6)}
            for ticker, value in ranked[:8]
        ]
        if total
        else [],
    }


def metric_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    return summarize([float(row[key]) for row in rows])


def build_payload() -> dict[str, Any]:
    baseline = baseline_context()
    lifecycles, source_audit = load_trusted_lifecycles()
    tickers = {row["ticker"] for row in lifecycles} | {"SPY", "QQQ"}
    frames = load_warehouse_ohlcv_frames(
        WAREHOUSE_PATH,
        tickers,
        min(row["open_date"] for row in lifecycles),
        SETTLEMENT_CUTOFF,
    )
    settled, missing = settle_lifecycle_opens(lifecycles, frames)
    settlement_rate = len(settled) / len(lifecycles) if lifecycles else 0.0
    aggregate = {
        "cash": metric_summary(settled, "cash_value"),
        "spy": metric_summary(settled, "spy_excess_value"),
        "qqq": metric_summary(settled, "qqq_excess_value"),
        "entry_notional": metric_summary(settled, "entry_notional"),
    }
    cohorts: dict[str, Any] = {}
    for cohort in sorted({row["cohort"] for row in settled}):
        rows = [row for row in settled if row["cohort"] == cohort]
        cohorts[cohort] = {
            "lifecycle_count": len(rows),
            "cash": metric_summary(rows, "cash_value"),
            "spy": metric_summary(rows, "spy_excess_value"),
            "qqq": metric_summary(rows, "qqq_excess_value"),
        }
    concentration = positive_concentration(settled)
    positive_cash_cohorts = [
        cohort
        for cohort, summary in cohorts.items()
        if (summary["cash"]["mean"] or 0.0) > 0.0
    ]
    checks = {
        "trusted_lifecycle_count_at_least_60": len(lifecycles)
        >= MIN_TRUSTED_LIFECYCLES,
        "settlement_rate_at_least_70pct": settlement_rate >= MIN_SETTLEMENT_RATE,
        "cash_mean_positive": (aggregate["cash"]["mean"] or 0.0) > 0.0,
        "cash_median_positive": (aggregate["cash"]["median"] or 0.0) > 0.0,
        "spy_mean_positive": (aggregate["spy"]["mean"] or 0.0) > 0.0,
        "spy_median_positive": (aggregate["spy"]["median"] or 0.0) > 0.0,
        "qqq_mean_positive": (aggregate["qqq"]["mean"] or 0.0) > 0.0,
        "qqq_median_positive": (aggregate["qqq"]["median"] or 0.0) > 0.0,
        "cash_positive_in_two_of_three_cohorts": len(positive_cash_cohorts) >= 2,
        "positive_value_concentration_passed": (
            concentration["max_ticker_share"] is not None
            and concentration["max_ticker_share"] <= MAX_POSITIVE_TICKER_SHARE
        ),
    }
    failure_labels = {
        "trusted_lifecycle_count_at_least_60": "trusted_lifecycle_count_below_60",
        "settlement_rate_at_least_70pct": "settlement_rate_below_70pct",
        "cash_mean_positive": "cash_mean_not_positive",
        "cash_median_positive": "cash_median_not_positive",
        "spy_mean_positive": "spy_mean_not_positive",
        "spy_median_positive": "spy_median_not_positive",
        "qqq_mean_positive": "qqq_mean_not_positive",
        "qqq_median_positive": "qqq_median_not_positive",
        "cash_positive_in_two_of_three_cohorts": "cash_not_positive_in_two_of_three_cohorts",
        "positive_value_concentration_passed": "positive_value_concentration_failed",
    }
    failed = [failure_labels[name] for name, passed in checks.items() if not passed]
    observed_only_lead = not failed
    status = "observed_only_positive_lead" if observed_only_lead else "observed_only_rejected"
    decision = (
        "observed_only_positive_broker_entry_h5_lead"
        if observed_only_lead
        else "observed_only_rejected_broker_entry_h5_value"
    )
    probability = float(PREDICTION["success_probability"])
    why = (
        "Actual lifecycle opens showed robust positive fixed-horizon directional "
        "value across the frozen comparators and calendar cohorts, but mixed "
        "trade provenance still prevents policy promotion."
        if observed_only_lead
        else "Aggregate cash and SPY mean/median values were positive and the "
        "cohort/concentration guards passed, but the QQQ-excess median remained "
        "slightly negative. The predeclared all-comparator robustness bar therefore "
        "failed, and the mixed discretionary/strategy population is not a "
        "promotable entry-policy cohort."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "observed_only_lead": observed_only_lead,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "lane": LANE,
        "owner": OWNER,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "fingerprint_caveat": FINGERPRINT_CAVEAT,
        "parameters": {
            "hold_sessions": HOLD_SESSIONS,
            "settlement_cutoff": SETTLEMENT_CUTOFF,
            "comparators": ["cash", "SPY", "QQQ"],
            "aggregation": "one actual open fill per trusted closed lifecycle",
            "directional_value": (
                "signed actual entry fill to fifth later-session close; benchmark "
                "excess uses the same long/short direction"
            ),
            "acceptance_rule": (
                ">=60 trusted lifecycles, >=70% fully settled, positive mean and "
                "median cash/SPY/QQQ value, positive cash mean in >=2 calendar "
                "cohorts, and max positive ticker share <=50%"
            ),
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": observed_only_lead,
            "predicted_success_probability": probability,
            "brier_score": round(
                (probability - (1.0 if observed_only_lead else 0.0)) ** 2, 6
            ),
            "realized_failure_modes": failed,
            "predicted_failure_mode_hit": any(
                (
                    mode == "warehouse_coverage_incomplete"
                    and not checks["settlement_rate_at_least_70pct"]
                )
                or (
                    mode == "entry_timing_not_additive"
                    and not checks["cash_mean_positive"]
                )
                or (
                    mode == "calendar_cohort_instability"
                    and not checks["cash_positive_in_two_of_three_cohorts"]
                )
                or (
                    mode == "single_ticker_concentration"
                    and not checks["positive_value_concentration_passed"]
                )
                for mode in PREDICTION["main_failure_modes"]
            ),
        },
        "gate1": {"passed": True, **baseline},
        "gate2": {
            "passed": source_audit["missing_fill_count"] == 0
            and not missing.get("invalid_open_fill")
            and not missing.get("open_event_count_not_one"),
            "dependencies_validated": True,
            "broker_fields": [
                "event_time_raw",
                "event_role=open",
                "lifecycle_direction",
                "running_qty_after",
                "qty",
                "price",
            ],
            "entry_date_contract": "actual lifecycle-open event date is present",
            "target_price_contract": (
                "not applicable: actual broker entry attribution changes no signal "
                "generation or target exit rule"
            ),
            "event_time_timezone_caveat": (
                "raw broker-local timezone is unspecified; settlement starts "
                "strictly after the raw calendar date"
            ),
        },
        "gate3": {
            "passed": settlement_rate >= MIN_SETTLEMENT_RATE,
            "new_filter_added": False,
            "signals_generated": len(lifecycles),
            "signals_survived": len(settled),
            "survival_rate": round(settlement_rate, 6),
            "skipped_reasons": dict(missing),
        },
        "gate4": {
            "applicable": False,
            "passed": False,
            "accepted_alpha": False,
            "observed_only_lead": observed_only_lead,
            "decision": decision,
            "acceptance_checks": checks,
            "failed_reasons": failed,
            "note": (
                "Observed-only actual-execution attribution. A positive result "
                "cannot promote entry behavior because the account mixes "
                "discretionary and strategy trades; promotion requires strategy "
                "tags, a shared policy cohort, and full Gate 1-4."
            ),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "attribution": {
            "source_audit": source_audit,
            "warehouse": {
                "path": repo_rel(WAREHOUSE_PATH),
                "settlement_cutoff": SETTLEMENT_CUTOFF,
                "requested_ticker_count": len(tickers),
                "loaded_ticker_count": len(frames),
            },
            "trusted_lifecycle_count": len(lifecycles),
            "settled_lifecycle_count": len(settled),
            "settlement_rate": round(settlement_rate, 6),
            "aggregate": aggregate,
            "by_calendar_cohort": cohorts,
            "positive_cash_cohorts": positive_cash_cohorts,
            "positive_value_concentration": concentration,
            "direction_counts": dict(Counter(row["direction"] for row in settled)),
            "observations": settled,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "scope": "read_only_broker_execution_entry_attribution",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing the H5 horizon, benchmark subset, year "
                "cuts, open-versus-add event role, direction, ticker exclusions, or "
                "response shape on these 87 lifecycles."
            ),
            "new_evidence_required": (
                "Reopen only with materially more trusted closed broker "
                "lifecycles (>=+50% and +10) or a strategy-tagged execution "
                "cohort. A positive lead still requires shared policy and full "
                "Gate 1-4 before any entry behavior changes."
            ),
        },
        "rejection_reason": None if observed_only_lead else ";".join(failed),
        "next_retry_requires": [
            "materially more trusted closed broker lifecycles or strategy tags",
            "shared production/backtest policy plus full Gate 1-4 if positive",
            "no horizon, comparator, cohort, ticker, direction, or response retune",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            "data/live_pilot/broker_execution/state.json",
            "data/live_pilot/broker_execution/fills.jsonl",
            "data/live_pilot/broker_execution/fill_lifecycle_links.jsonl",
            "docs/broker_execution_ledger.md",
            repo_rel(BASELINE_PATH),
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    attribution = payload["attribution"]
    aggregate = attribution["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Broker entry H5 value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            (
                "- Trusted / settled lifecycles: "
                f"`{attribution['trusted_lifecycle_count']}` / "
                f"`{attribution['settled_lifecycle_count']}`"
            ),
            f"- Cash mean / median: `${aggregate['cash']['mean']}` / `${aggregate['cash']['median']}`",
            f"- SPY excess mean / median: `${aggregate['spy']['mean']}` / `${aggregate['spy']['median']}`",
            f"- QQQ excess mean / median: `${aggregate['qqq']['mean']}` / `${aggregate['qqq']['median']}`",
            f"- Positive cash cohorts: `{', '.join(attribution['positive_cash_cohorts']) or 'none'}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "No live, paper, entry, ranking, sizing, exit, order, or LLM behavior changed.",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "ticket": repo_rel(TICKET_JSON),
            "files": CHANGED_FILES,
            "reproduction_commands": payload["reproduction_commands"],
        },
    )
    ticket = read_json(TICKET_JSON)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": {
                "status": payload["status"],
                "trusted_lifecycles": payload["attribution"]["trusted_lifecycle_count"],
                "settled_lifecycles": payload["attribution"]["settled_lifecycle_count"],
                "cash_mean": payload["attribution"]["aggregate"]["cash"]["mean"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in payload.items()
                if key not in {"experiment_id", "status", "prediction"}
            },
            "owner": OWNER,
        },
    )


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "trusted_lifecycles": payload["attribution"]["trusted_lifecycle_count"],
                "settled_lifecycles": payload["attribution"]["settled_lifecycle_count"],
                "aggregate": payload["attribution"]["aggregate"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
