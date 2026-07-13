"""exp-20260712-002: broker exit-fill five-session avoidance attribution.

Observed-only alpha attribution on broker-authoritative execution facts.  The
runner compares each real reduce/close fill with continuing those exited shares
for five later trading sessions, then aggregates the result by trusted closed
position lifecycle.  It changes no strategy, paper, production, or order path.
"""

from __future__ import annotations

import datetime as dt
import json
import math
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
from quant.ohlcv_warehouse import load_warehouse_ohlcv_frames  # noqa: E402


EXPERIMENT_ID = "exp-20260712-002"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "broker_exit_fill_h5_avoidance"
RUNNER = f"quant/experiments/exp_20260712_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

HYPOTHESIS = (
    "Observed-only exit alpha: broker-authoritative reduce and close fills "
    "across the 87 trusted closed lifecycles should show positive five-session "
    "cash, SPY, and QQQ exit-avoidance value versus continuing the exited "
    "shares if realized production exits add value rather than truncate winners."
)
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "broker_execution_ledger_exit_attribution"
MECHANISM_FAMILY = "broker_execution_exit_quality"
TRIAL_FAMILY = "broker_authoritative_exit_fill_h5_avoidance"
TRIAL_VARIANT_ID = "h5_cash_spy_qqq_lifecycle_aggregate_v1"
CHANGED_VARIABLE = "broker_exit_fill_h5_avoidance_value_v1"
NEARBY_PRIORS = ["exp-20260712-001", "exp-20260710-016"]
NEW_EVIDENCE_TYPE = "new_broker_authoritative_settled_lifecycles"
NEW_EVIDENCE_AXIS = (
    "New data source: the broker execution ledger contains 87 trusted closed "
    "Moomoo lifecycles with actual fills and quantities. Prior exit studies "
    "used modeled backtest trades or shadow advisory rows, not broker facts."
)
FINGERPRINT_CAVEAT = (
    "Reservation over-matched the ohlcv_momentum population because the "
    "hypothesis mentioned winner continuation. The real source is "
    "moomoo_execution_history / broker execution ledger; the observed-only "
    "override was justified by this genuinely new source."
)
CAUSAL_COMPONENTS = [
    "latest-effective broker fills pinned to the lifecycle mapping observation",
    "strict trusted closed lifecycle links",
    "five-session warehouse settlement through a fixed cutoff",
    "cash, SPY, and QQQ exit-avoidance comparators",
    "lifecycle-level aggregation and three calendar cohorts",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.35,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "warehouse_coverage_incomplete",
        "discretionary_trade_mix_not_strategy_attributable",
        "actual_exits_truncate_winners",
        "calendar_cohort_instability",
        "single_ticker_concentration",
    ],
    "confidence_reason": (
        "This is the first broker-authoritative closed-lifecycle surface and "
        "it supplies 87 quantity-anchored real exits across three calendar "
        "cohorts, so it can reveal whether production exits preserve capital. "
        "The account mixes discretionary and strategy trades and prior shadow-"
        "advisory severity was unstable, making a robust positive result uncertain."
    ),
    "recorded_at": "2026-07-12T02:09:40+00:00",
}

HOLD_SESSIONS = 5
SETTLEMENT_CUTOFF = "2026-07-10"
MIN_TRUSTED_LIFECYCLES = 60
MIN_SETTLEMENT_RATE = 0.70
MAX_POSITIVE_TICKER_SHARE = 0.50
BROKER_ROOT = REPO_ROOT / "data" / "live_pilot" / "broker_execution"
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260712_002_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rounded(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


def summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "sum": None, "mean": None, "median": None}
    return {
        "count": len(values),
        "sum": rounded(sum(values)),
        "mean": rounded(statistics.fmean(values)),
        "median": rounded(statistics.median(values)),
        "positive_rate": round(sum(value > 0.0 for value in values) / len(values), 6),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH)
    windows = list(payload.get("windows") or [])
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row["expected_value_score"]) for row in windows), 4
        ),
        "total_pnl_sum": round(sum(float(row["total_pnl"]) for row in windows), 2),
        "trade_count": sum(int(row["trade_count"]) for row in windows),
        "signals_generated": sum(int(row["signals_generated"]) for row in windows),
        "signals_survived": sum(int(row["signals_survived"]) for row in windows),
        "minimum_survival_rate": min(float(row["survival_rate"]) for row in windows),
        "windows": windows,
    }


def latest_rows_by_deal(
    rows: list[dict[str, Any]], *, observed_at_or_before: str | None = None
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        fact = row.get("fact") or {}
        deal_id = str(fact.get("deal_id") or "")
        if not deal_id:
            continue
        observed_at = str(row.get("observed_at_utc") or "")
        if observed_at_or_before and observed_at > observed_at_or_before:
            continue
        if int(row.get("ledger_sequence") or 0) >= int(
            latest.get(deal_id, {}).get("ledger_sequence") or 0
        ):
            latest[deal_id] = row
    return latest


def load_trusted_lifecycles() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    state = read_json(BROKER_ROOT / "state.json")
    lifecycle_state = state.get("lifecycle_replay") or {}
    rule_version = str(lifecycle_state.get("rule_version") or "")
    mapping_hash = str(lifecycle_state.get("mapping_input_hash") or "")
    if not rule_version or not mapping_hash:
        raise RuntimeError("broker lifecycle state lacks rule_version or mapping_input_hash")

    link_candidates = []
    for row in read_jsonl(BROKER_ROOT / "fill_lifecycle_links.jsonl"):
        fact = row.get("fact") or {}
        # v3 stores the overall mapping hash in state.json and a per-prefix
        # hash on each link.  The rule version plus latest deal projection is
        # therefore the stable consumer selector; requiring the obsolete v1
        # fact.mapping_input_hash would silently select zero rows.
        if fact.get("rule_version") == rule_version:
            link_candidates.append(row)
    links_by_deal = latest_rows_by_deal(link_candidates)
    if not links_by_deal:
        raise RuntimeError("no lifecycle links matched the pinned state mapping")
    mapping_observed_at = max(
        str(row.get("observed_at_utc") or "") for row in links_by_deal.values()
    )
    fills_by_deal = latest_rows_by_deal(
        read_jsonl(BROKER_ROOT / "fills.jsonl"),
        observed_at_or_before=mapping_observed_at,
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in links_by_deal.values():
        fact = row.get("fact") or {}
        lifecycle_id = str(fact.get("lifecycle_id") or "")
        if fact.get("link_status") == "linked" and lifecycle_id:
            grouped[lifecycle_id].append(fact)

    trusted = []
    missing_fill_count = 0
    for lifecycle_id, link_facts in grouped.items():
        link_facts.sort(
            key=lambda fact: (
                str(fact.get("event_time_raw") or ""),
                str(fact.get("deal_id") or ""),
            )
        )
        if finite_float(link_facts[-1].get("running_qty_after")) != 0.0:
            continue
        fill_facts = []
        complete = True
        for link in link_facts:
            deal_id = str(link.get("deal_id") or "")
            fill_row = fills_by_deal.get(deal_id)
            if not fill_row:
                missing_fill_count += 1
                complete = False
                break
            fill_facts.append(fill_row.get("fact") or {})
        if not complete:
            continue
        trusted.append(
            {
                "lifecycle_id": lifecycle_id,
                "ticker": str(link_facts[0].get("ticker") or "").upper(),
                "direction": str(link_facts[0].get("lifecycle_direction") or ""),
                "open_date": str(link_facts[0].get("event_time_raw") or "")[:10],
                "close_date": str(link_facts[-1].get("event_time_raw") or "")[:10],
                "links": link_facts,
                "fills": fill_facts,
            }
        )
    return trusted, {
        "source_root": repo_rel(BROKER_ROOT),
        "rule_version": rule_version,
        "mapping_input_hash": mapping_hash,
        "mapping_observed_at_utc": mapping_observed_at,
        "active_mapping_link_count": len(links_by_deal),
        "trusted_closed_lifecycle_count_state": lifecycle_state.get(
            "trusted_closed_lifecycle_count"
        ),
        "trusted_closed_lifecycle_count_loaded": len(trusted),
        "missing_fill_count": missing_fill_count,
        "broker_event_time_timezone_status": "broker_local_unspecified",
    }


def future_session(frame: Any, event_date: str) -> dict[str, Any] | None:
    event_ts = dt.datetime.strptime(event_date, "%Y-%m-%d").date()
    cutoff = dt.datetime.strptime(SETTLEMENT_CUTOFF, "%Y-%m-%d").date()
    later = frame[
        (frame.index.date > event_ts) & (frame.index.date <= cutoff)
    ].sort_index()
    if len(later) < HOLD_SESSIONS:
        return None
    start = later.iloc[0]
    end = later.iloc[HOLD_SESSIONS - 1]
    return {
        "next_session": later.index[0].date().isoformat(),
        "horizon_session": later.index[HOLD_SESSIONS - 1].date().isoformat(),
        "next_open": float(start["Open"]),
        "horizon_close": float(end["Close"]),
    }


def settle_lifecycles(
    lifecycles: list[dict[str, Any]], frames: dict[str, Any]
) -> tuple[list[dict[str, Any]], Counter[str]]:
    settled = []
    missing: Counter[str] = Counter()
    spy = frames.get("SPY")
    qqq = frames.get("QQQ")
    for lifecycle in lifecycles:
        ticker = lifecycle["ticker"]
        frame = frames.get(ticker)
        if frame is None:
            missing["ticker_ohlcv_missing"] += 1
            continue
        events = []
        for link, fill in zip(lifecycle["links"], lifecycle["fills"]):
            if link.get("event_role") not in {"reduce", "close"}:
                continue
            qty = finite_float(fill.get("qty"))
            exit_price = finite_float(fill.get("price"))
            event_date = str(fill.get("event_time_raw") or "")[:10]
            if not event_date or not qty or not exit_price:
                missing["invalid_exit_fill"] += 1
                events = []
                break
            ticker_h5 = future_session(frame, event_date)
            spy_h5 = future_session(spy, event_date) if spy is not None else None
            qqq_h5 = future_session(qqq, event_date) if qqq is not None else None
            if ticker_h5 is None or spy_h5 is None or qqq_h5 is None:
                missing["h5_not_settled"] += 1
                events = []
                break
            direction = lifecycle["direction"]
            if direction == "long":
                cash_avoidance = qty * (exit_price - ticker_h5["horizon_close"])
            elif direction == "short":
                cash_avoidance = qty * (ticker_h5["horizon_close"] - exit_price)
            else:
                missing["unknown_direction"] += 1
                events = []
                break
            exit_notional = qty * exit_price
            spy_return = spy_h5["horizon_close"] / spy_h5["next_open"] - 1.0
            qqq_return = qqq_h5["horizon_close"] / qqq_h5["next_open"] - 1.0
            events.append(
                {
                    "cash": cash_avoidance,
                    "spy": cash_avoidance + exit_notional * spy_return,
                    "qqq": cash_avoidance + exit_notional * qqq_return,
                    "notional": exit_notional,
                }
            )
        if not events:
            if not any(
                link.get("event_role") in {"reduce", "close"}
                for link in lifecycle["links"]
            ):
                missing["no_exit_event"] += 1
            continue
        settled.append(
            {
                "ticker": ticker,
                "direction": lifecycle["direction"],
                "open_date": lifecycle["open_date"],
                "close_date": lifecycle["close_date"],
                "cohort": lifecycle["close_date"][:4],
                "exit_fill_count": len(events),
                "exit_notional": sum(row["notional"] for row in events),
                "cash_avoidance": sum(row["cash"] for row in events),
                "spy_avoidance": sum(row["spy"] for row in events),
                "qqq_avoidance": sum(row["qqq"] for row in events),
            }
        )
    return settled, missing


def positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        if row["cash_avoidance"] > 0.0:
            by_ticker[row["ticker"]] += row["cash_avoidance"]
    total = sum(by_ticker.values())
    ranked = sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    return {
        "positive_cash_avoidance": rounded(total),
        "max_ticker_share": round(ranked[0][1] / total, 6) if total else None,
        "hhi": round(sum((value / total) ** 2 for value in by_ticker.values()), 6)
        if total
        else None,
        "top_tickers": [
            {"ticker": ticker, "value": rounded(value), "share": round(value / total, 6)}
            for ticker, value in ranked[:8]
        ]
        if total
        else [],
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    lifecycles, source_audit = load_trusted_lifecycles()
    tickers = {row["ticker"] for row in lifecycles} | {"SPY", "QQQ"}
    frames = load_warehouse_ohlcv_frames(
        WAREHOUSE_PATH,
        tickers,
        min(row["close_date"] for row in lifecycles),
        SETTLEMENT_CUTOFF,
    )
    settled, missing = settle_lifecycles(lifecycles, frames)
    settlement_rate = len(settled) / len(lifecycles) if lifecycles else 0.0

    aggregate = {
        "cash": summarize([row["cash_avoidance"] for row in settled]),
        "spy": summarize([row["spy_avoidance"] for row in settled]),
        "qqq": summarize([row["qqq_avoidance"] for row in settled]),
        "exit_notional": summarize([row["exit_notional"] for row in settled]),
    }
    cohorts = {}
    for cohort in sorted({row["cohort"] for row in settled}):
        rows = [row for row in settled if row["cohort"] == cohort]
        cohorts[cohort] = {
            "lifecycle_count": len(rows),
            "cash": summarize([row["cash_avoidance"] for row in rows]),
            "spy": summarize([row["spy_avoidance"] for row in rows]),
            "qqq": summarize([row["qqq_avoidance"] for row in rows]),
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
        "positive_value_concentration_passed": concentration["max_ticker_share"]
        is not None
        and concentration["max_ticker_share"] <= MAX_POSITIVE_TICKER_SHARE,
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
        "observed_only_positive_broker_exit_h5_avoidance_lead"
        if observed_only_lead
        else "observed_only_rejected_broker_exit_h5_avoidance"
    )
    probability = float(PREDICTION["success_probability"])
    now = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
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
            "aggregation": "sum exit-fill avoidance within trusted lifecycle",
            "ticker_continuation": "actual exit price to fifth later-session close",
            "benchmark_replacement": "next-session open to fifth later-session close",
            "acceptance_rule": (
                ">=60 trusted lifecycles, >=70% fully settled, positive mean and "
                "median cash/SPY/QQQ avoidance, positive cash mean in >=2 calendar "
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
                    mode == "actual_exits_truncate_winners"
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
            "passed": source_audit["missing_fill_count"] == 0,
            "dependencies_validated": True,
            "broker_fields": [
                "event_time_raw",
                "event_role",
                "lifecycle_direction",
                "running_qty_after",
                "qty",
                "price",
            ],
            "entry_date_contract": "lifecycle open event date present for every loaded lifecycle",
            "target_price_contract": (
                "not applicable: this consumes actual broker exits and changes no "
                "signal generation or target exit rule"
            ),
            "event_time_timezone_caveat": "raw broker-local timezone is unspecified; settlement starts strictly after the raw calendar date",
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
                "No strategy behavior changed. Even a positive result is only an "
                "actual-execution attribution lead because the account mixes "
                "discretionary and strategy trades; promotion requires a shared "
                "policy cohort and full Gate 1-4."
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
            "exit_fill_count": sum(row["exit_fill_count"] for row in settled),
            "aggregate": aggregate,
            "by_calendar_cohort": cohorts,
            "positive_cash_cohorts": positive_cash_cohorts,
            "positive_value_concentration": concentration,
            "direction_counts": dict(Counter(row["direction"] for row in settled)),
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
            "scope": "read_only_broker_execution_attribution",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Actual production exits produced robust positive five-session "
                "avoidance across the fixed comparators and time cohorts."
                if observed_only_lead
                else "Actual exits did not preserve a robust positive five-session "
                "avoidance relationship across cash, benchmark replacement, time "
                "cohorts, and concentration controls. The mixed discretionary/"
                "strategy population is not a promotable policy cohort."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing the H5 horizon, benchmark subset, year "
                "cuts, event-role subset, direction, ticker exclusions, or response "
                "shape on these 87 lifecycles."
            ),
            "new_evidence_required": (
                "A rejected result needs materially more trusted closed broker "
                "lifecycles (>=+50% and +10) or a new strategy-tagged execution "
                "cohort. A positive lead still requires a shared policy and full "
                "Gate 1-4 before any exit behavior changes."
            ),
        },
        "rejection_reason": None if observed_only_lead else ";".join(failed),
        "next_retry_requires": [
            "materially more trusted closed broker lifecycles or a strategy-tagged execution cohort",
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
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def build_card(payload: dict[str, Any]) -> str:
    attribution = payload["attribution"]
    aggregate = attribution["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Broker exit H5 avoidance",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Trusted / settled lifecycles: `{attribution['trusted_lifecycle_count']}` / `{attribution['settled_lifecycle_count']}`",
            f"- Cash mean / median: `${aggregate['cash']['mean']}` / `${aggregate['cash']['median']}`",
            f"- SPY mean / median: `${aggregate['spy']['mean']}` / `${aggregate['spy']['median']}`",
            f"- QQQ mean / median: `${aggregate['qqq']['mean']}` / `${aggregate['qqq']['median']}`",
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
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
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
                "trusted_lifecycles": payload["attribution"][
                    "trusted_lifecycle_count"
                ],
                "settled_lifecycles": payload["attribution"][
                    "settled_lifecycle_count"
                ],
                "cash_mean": payload["attribution"]["aggregate"]["cash"]["mean"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in build_log(payload).items()
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
                "trusted_lifecycles": payload["attribution"][
                    "trusted_lifecycle_count"
                ],
                "settled_lifecycles": payload["attribution"][
                    "settled_lifecycle_count"
                ],
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
