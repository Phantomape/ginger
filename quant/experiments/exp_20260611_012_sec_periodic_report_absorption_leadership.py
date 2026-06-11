"""exp-20260611-012: SEC periodic-report absorption leadership candidate pool.

Alpha search. This tests one production-visible free-data candidate source:
PIT SEC 10-Q/10-K filing events paired with same-day liquid market absorption
and relative leadership before a default-off next-open paper entry with a fixed
10-trading-day hold.

No live orders, live ranking, live sizing, core exits, LLM/news decisions, or
trade-enabled production behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260611-012"
STEM = "sec_periodic_report_absorption_leadership"
TRIAL_FAMILY = "sec_periodic_report_absorption_leadership_candidate_pool"
TRIAL_VARIANT_ID = "sec_periodic_report_absorption_leadership_shared_default_off_v1"
CHANGED_VARIABLE = (
    "sec_periodic_report_absorption_leadership_shared_default_off_candidate_source_v1"
)
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260611_012_sec_periodic_report_absorption_helper as periodic  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_012_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_EVENTS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PERIODIC_CONFIG = {
    **periodic.DEFAULT_CONFIG,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": BASE_NOTIONAL_USD,
    "hold_days": HOLD_DAYS,
    "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
    "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
}

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
    "target_trade_count": 44,
}

ACCEPTED_DISTRIBUTION_DAY_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

PREDICTION = {
    "success_probability": 0.23,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "thin_periodic_report_sample",
        "overlap_with_existing_earnings_or_companyfacts_sources",
        "same_day_absorption_is_generic_momentum",
        "old_thin_window_regression",
        "accepted_distribution_day_comparator_not_beaten",
    ],
    "confidence_reason": (
        "SEC 10-Q/10-K filing events are free, PIT, production-visible, and "
        "available across the three canonical windows. The test is distinct "
        "from failed 8-K text-label runs because it asks whether the market "
        "absorbed mandatory periodic reports and immediately marked relative "
        "leadership before the next open."
    ),
    "recorded_at": "2026-06-11T08:00:39Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "experiment_local_replay_helper_no_daily_or_shared_promotion",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "default_off_paper_only": True,
    "parity_note": (
        "The rejected experiment keeps only experiment-local replay helper "
        "code and a focused parity test. It is not wired into live orders, "
        "live ranking, live sizing, core exits, daily production snapshots, "
        "or trade-enabled production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 10-Q/10-K periodic reports paired with "
        "same-day positive return, SPY/QQQ relative leadership, close quality, "
        "liquidity, and non-parabolic trend guards may identify stocks where "
        "the market absorbed fundamental disclosure and should continue after "
        "next-open default-off paper entry."
    ),
    "2_history_check": {
        "nearby_rejected_sec_event_text": [
            "exp-20260610-013 rejected broad 8-K business-update event labels.",
            "exp-20260610-023 rejected SEC contract-demand text leadership.",
            "exp-20260610-024 rejected SEC earnings cadence surprise absorption.",
            "exp-20260611-001 rejected SEC filing complexity/change density.",
            "exp-20260609-006 rejected Companyfacts quality-gated replacement.",
        ],
        "difference_from_priors": (
            "This is not 8-K item-code semantics, Companyfacts scalar mining, "
            "Form 4, or LLM soft ranking. It uses mandatory periodic 10-Q/10-K "
            "events with same-day absorption and leadership, then a fixed "
            "next-open paper replay."
        ),
        "accepted_current_comparator": (
            "exp-20260611-007 distribution-day absorption leadership is the "
            "current accepted stock-candidate source comparator and must be "
            "beaten before promotion pressure."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Pass only if "
        "aggregate EV/PnL improve, no EV/PnL window regression, at least 20 "
        "target trades across all 3 windows, survival >=5%, drawdown drift "
        "<=0.5pp, concentration passes, accepted compression is beaten, and "
        "the stronger accepted distribution-day comparator is beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_012_sec_periodic_report_absorption_leadership.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_globals() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework.sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    framework.sleeve.STEM = STEM
    framework.sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.sleeve.HOLD_DAYS = HOLD_DAYS
    framework.sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    return periodic.build_sec_periodic_report_absorption_candidate_rows(
        ohlcv_by_ticker=snapshot,
        sec_filing_events=SEC_EVENTS_PATH,
        dates=dates,
        sector_entries=sector_entries,
        core_entries_by_date=entries_by_date,
        config=PERIODIC_CONFIG,
    )


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = gate.setdefault("failed_reasons", [])
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        failed.append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        failed.append("accepted_compression_pnl_not_beaten")
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_DISTRIBUTION_DAY_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        failed.append("accepted_distribution_day_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_DISTRIBUTION_DAY_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        failed.append("accepted_distribution_day_pnl_not_beaten")
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["accepted_distribution_day_comparator"] = ACCEPTED_DISTRIBUTION_DAY_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_pending_daily_adapter_sec_periodic_report_absorption_leadership"
        if gate["passed"]
        else "rejected_sec_periodic_report_absorption_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    _configure_globals()
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] baseline core replay and SEC periodic-report overlay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries_all),
        )
        sector_entries = {
            ticker: meta
            for ticker, meta in sector_entries_all.items()
            if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
            "sec_event_source": _repo_rel(SEC_EVENTS_PATH),
        }
        candidates, contexts, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
        )
        selected_trades, filtered_candidates = (
            periodic.select_sec_periodic_report_absorption_paper_trades(
                rows_by_ticker=snapshot,
                candidates=candidates,
                config=PERIODIC_CONFIG,
            )
        )
        for trade in selected_trades:
            trade["window"] = label
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        contexts_by_window[label] = contexts
        context_scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "candidate_day_count": scan.get("days_with_raw_periodic_report_candidates", 0),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework.sleeve._aggregate(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    passed = bool(gate4["passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "positive_replay_lead_not_promoted" if passed else "rejected",
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "experiment_local_replay_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_periodic_report_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260610-013",
            "exp-20260610-023",
            "exp-20260610-024",
            "exp-20260611-001",
            "exp-20260609-006",
            "exp-20260611-007",
        ],
        "prior_trial_count": 6,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_pit_sec_10q_10k_absorption_leadership_candidate_pool",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "experiment-local SEC periodic-report paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sec_event_source": _repo_rel(SEC_EVENTS_PATH),
            "replay_llm": False,
            "replay_news": False,
            "execution_model": (
                "Signal uses only PIT SEC filing usable date and signal-date "
                "OHLCV available before next-session open. Paper entry is next "
                "available open with entry slippage; exit is the close 10 "
                "trading days after signal with target-side sell slippage and "
                "ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            **periodic._parameter_summary(PERIODIC_CONFIG),
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "same_ticker_core_overlap_excluded": True,
            "single_causal_variable": CHANGED_VARIABLE,
        },
        "gate_questions": PRE_RUN_QUESTIONS,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SEC filing event ticker/form_type/usable_trade_date/pit_safe_flag",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No core entry filter is added. The SEC periodic-report source "
                "is additive default-off paper; core signals and survival are "
                "unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "contexts_by_window": contexts_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        "accepted_distribution_day_comparator": ACCEPTED_DISTRIBUTION_DAY_COMPARATOR,
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed SEC periodic-report absorption bundle cleared the "
                "standard gates and beat the current accepted stock-candidate "
                "comparator, suggesting mandatory report absorption added "
                "replacement value beyond generic momentum. It remains not "
                "promoted until daily adapter wiring and forward paper rows "
                "prove parity."
                if passed
                else (
                    "The fixed SEC periodic-report absorption bundle failed "
                    "Gate 4. The likely reason is that same-day strength after "
                    "10-Q/10-K filing is not distinct enough from generic "
                    "liquid momentum or already priced earnings information "
                    "after next-open execution, costs, cooldown, and overlap "
                    "controls."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping 10-Q/10-K form mix, same-day return, "
                "relative-strength, close-location, volume, ret5/ret20, top-N, "
                "hold-day, cooldown, or notional thresholds on these frozen "
                "windows."
            ),
            "new_evidence_required": (
                "A retry needs a materially richer free PIT field, such as "
                "parsed report-quality change, cross-filing fundamental surprise, "
                "or forward daily replacement-value evidence."
            ),
        },
        "interpretation": (
            "The SEC periodic-report absorption source passed as a replay lead "
            "but was not promoted to daily production surfaces."
            if passed
            else (
                "The SEC periodic-report absorption source was rejected under "
                "the standard three-window protocol and stricter current "
                "accepted comparator."
            )
        ),
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "Richer PIT periodic-report content or forward replacement rows; "
            "do not threshold-tune the same same-day absorption family."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
            _repo_rel("quant/experiments/exp_20260611_012_sec_periodic_report_absorption_helper.py"),
            _repo_rel("quant/test_sec_periodic_report_absorption_leadership_paper_sleeve.py"),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Filing days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {filing_days} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                filing_days=scan.get("periodic_report_days", 0),
                days=scan.get("days_with_raw_periodic_report_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Periodic-Report Absorption Leadership",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=True, indent=2),
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Compression comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Distribution-day comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_DISTRIBUTION_DAY_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_DISTRIBUTION_DAY_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": f"{_repo_rel(OUT_JSON)}#before_metrics",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "periodic_report_days": payload["context_scan_by_window"][label].get(
                    "periodic_report_days"
                ),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel("quant/experiments/exp_20260611_012_sec_periodic_report_absorption_helper.py"),
            _repo_rel("quant/test_sec_periodic_report_absorption_leadership_paper_sleeve.py"),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel("quant/experiments/exp_20260611_012_sec_periodic_report_absorption_helper.py"): framework._sha256(
                REPO_ROOT
                / "quant"
                / "experiments"
                / "exp_20260611_012_sec_periodic_report_absorption_helper.py"
            ),
            _repo_rel("quant/test_sec_periodic_report_absorption_leadership_paper_sleeve.py"): framework._sha256(
                REPO_ROOT / "quant" / "test_sec_periodic_report_absorption_leadership_paper_sleeve.py"
            ),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
