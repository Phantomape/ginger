"""exp-20260610-015: 52-week-high Companyfacts quality core-flow scout.

Replay-only alpha search. This tests one fixed candidate-source hypothesis:
the accepted 52-week-high proximity core-flow paper source may be improved by
requiring PIT SEC Companyfacts evidence that the breakout is backed by current
business quality, not just price-anchor geometry.

The quality gate is fixed before the run: positive operating income plus at
least one of revenue or EPS YoY growth >= 10%, with the supporting filings
filed on or before the signal date and no older than 180 calendar days.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import math
import sys
from collections import Counter
from datetime import datetime, timezone
from json import dumps as json_dumps
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260610_007_fiftytwo_week_high_proximity_core_flow as base  # noqa: E402
import fundamental_growth_rs_paper_sleeve as fundamentals  # noqa: E402


framework = base.framework

EXPERIMENT_ID = "exp-20260610-015"
STEM = "fiftytwo_week_high_companyfacts_quality"
TRIAL_FAMILY = "fiftytwo_week_high_companyfacts_quality_candidate_pool"
TRIAL_VARIANT_ID = "fiftytwo_week_high_companyfacts_quality_top1_next_open_10d_v1"
CHANGED_VARIABLE = "fiftytwo_week_high_companyfacts_quality_core_flow_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_015_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MAX_COMPANYFACTS_AGE_DAYS = 180
MIN_REVENUE_YOY_GROWTH = 0.10
MIN_EPS_YOY_GROWTH = 0.10
MIN_GROWTH_POINTS = 1

COMPANYFACTS_CONFIG = {
    **fundamentals.DEFAULT_CONFIG,
    "eps_growth_threshold": MIN_EPS_YOY_GROWTH,
    "revenue_growth_threshold": MIN_REVENUE_YOY_GROWTH,
    "min_fundamental_points": MIN_GROWTH_POINTS,
}

ACCEPTED_FIFTYTWO_WEEK_COMPARATOR = {
    "experiment_id": "exp-20260610-008",
    "decision": "accepted_fiftytwo_week_high_proximity_core_flow_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.4308,
    "total_pnl_delta_sum": 9295.34,
    "target_trade_count": 54,
    "by_window": {
        "late_strong": {"expected_value_delta": 0.0921, "pnl_delta": 1813.52},
        "mid_weak": {"expected_value_delta": 0.2571, "pnl_delta": 4836.19},
        "old_thin": {"expected_value_delta": 0.0816, "pnl_delta": 2645.63},
    },
}

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "companyfacts_lags_price_anchor",
        "old_thin_regression",
        "accepted_52w_comparator_not_beaten",
        "concentration_failed",
    ],
    "confidence_reason": (
        "The accepted 52-week-high helper explicitly needs a durable-vs-"
        "exhausted separator, and filed-date SEC Companyfacts quality is PIT-"
        "safe. Recent Companyfacts hard-selection overlays were sparse or "
        "window-fragile, so this is a cautious private replay scout rather "
        "than retained alpha."
    ),
    "recorded_at": "2026-06-10T13:04:46+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_companyfacts_52w_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_companyfacts": True,
    "parity_note": (
        "This experiment changes no production code. It reads only SEC "
        "Companyfacts rows with filed date <= signal date in historical replay. "
        "A positive result cannot be promoted until a shared helper computes "
        "the same operating-income, revenue/EPS growth, filing-age, 52-week-"
        "high proximity, core-flow, next-open paper entry, 10-trading-day exit, "
        "cost, cooldown, and concentration semantics in both historical replay "
        "and daily default-off production snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: the accepted 52-week-high core-flow anchor may mix "
        "durable underreaction with exhausted price breakouts. PIT SEC "
        "Companyfacts quality, defined as positive operating income plus at "
        "least one fresh revenue/EPS growth point, should separate durable "
        "leaders and improve next-open 10-day paper replacement value."
    ),
    "2_history_check": {
        "exp-20260610-008": (
            "Accepted shared 52-week-high core-flow adapter: EV +0.4308 and "
            "PnL +$9,295.34, all three windows positive. This run must beat it "
            "to be useful."
        ),
        "exp-20260608-014": (
            "Companyfacts quality plus compression breakout was rejected: only "
            "4 target trades and concentration failure. This run uses the much "
            "broader accepted 52-week source and a less brittle one-growth-"
            "point quality gate."
        ),
        "exp-20260609-006": (
            "Fundamental Growth RS hard quality-gated replacement improved "
            "aggregate but regressed late_strong. Companyfacts support fields "
            "are not automatically good hard selectors."
        ),
        "frozen_lanes_avoided": (
            "No 52-week threshold, lookback, top-N, hold, cooldown, notional, "
            "revision allocator, LLM, Form4, or state-surface retune is tested."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: accepted 52-week-high core-flow candidate "
        "source plus a fixed PIT Companyfacts quality gate. All other 52-week "
        "geometry, core-flow, next-open entry, hold, cost, cooldown, top-1, "
        "and concentration mechanics remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only as a "
        "replay lead if aggregate EV/PnL improve, no EV/PnL regression window "
        "appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and accepted "
        "compression, accepted core-flow, and accepted 52-week comparators are "
        "beaten. A positive scout still requires a shared helper before use."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_015_fiftytwo_week_high_companyfacts_quality.py"
    ),
}

ORIGINAL_CANDIDATE_FOR_TICKER = base._candidate_for_ticker
ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW = base._candidate_rows_for_window
ORIGINAL_BUILD_PAYLOAD = base._build_payload
ORIGINAL_BUILD_LOG_RECORD = base._build_log_record
ORIGINAL_GATE4 = base._gate4

_CURRENT_FUNDAMENTAL_INDEX: fundamentals.CompanyfactsFundamentalIndex | None = None
_CURRENT_QUALITY_AUDIT: dict[str, Any] = {}


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _round(value: Any, digits: int = 6) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _age_days(filed: Any, signal_date: str) -> int | None:
    start = str(filed or "")[:10]
    end = str(signal_date or "")[:10]
    if not start or not end:
        return None
    try:
        start_day = datetime.fromisoformat(start)
        end_day = datetime.fromisoformat(end)
    except ValueError:
        return None
    if start_day > end_day:
        return None
    return (end_day - start_day).days


def _fresh(age: int | None) -> bool:
    return age is not None and age <= MAX_COMPANYFACTS_AGE_DAYS


def _load_fundamental_index(
    *,
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[fundamentals.CompanyfactsFundamentalIndex, dict[str, Any]]:
    tickers = sorted(set(sector_entries))
    rows = fundamentals.load_companyfacts_rows(max_filed=str(cfg["end"]), tickers=tickers)
    index = fundamentals.CompanyfactsFundamentalIndex(rows, config=COMPANYFACTS_CONFIG)
    return index, {
        "row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "").upper() for row in rows}),
        "max_filed": str(cfg["end"]),
        "source": "data/non_ohlcv/sec_companyfacts_selected_*.jsonl",
        "known_at": "SEC Companyfacts filed date <= signal_date",
        "config": {
            "max_companyfacts_age_days": MAX_COMPANYFACTS_AGE_DAYS,
            "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
            "min_eps_yoy_growth": MIN_EPS_YOY_GROWTH,
            "min_growth_points": MIN_GROWTH_POINTS,
            "require_positive_operating_income": True,
        },
    }


def _companyfacts_quality_context(ticker: str, signal_date: str) -> dict[str, Any]:
    if _CURRENT_FUNDAMENTAL_INDEX is None:
        return {
            "companyfacts_quality_passed": False,
            "companyfacts_quality_reject_reason": "missing_fundamental_index",
        }
    growth = _CURRENT_FUNDAMENTAL_INDEX.fundamental_context(ticker, signal_date)
    operating = _CURRENT_FUNDAMENTAL_INDEX.operating_quality(ticker, signal_date)

    revenue_growth = _float(growth.get("revenue_yoy_growth"))
    eps_growth = _float(growth.get("eps_yoy_growth"))
    revenue_age = _age_days(growth.get("revenue_current_filed"), signal_date)
    eps_age = _age_days(growth.get("eps_current_filed"), signal_date)
    operating_age = _age_days(operating.get("operating_income_current_filed"), signal_date)

    revenue_pass = (
        revenue_growth is not None
        and revenue_growth >= MIN_REVENUE_YOY_GROWTH
        and _fresh(revenue_age)
    )
    eps_pass = (
        eps_growth is not None
        and eps_growth >= MIN_EPS_YOY_GROWTH
        and _fresh(eps_age)
    )
    operating_pass = (
        operating.get("operating_profit_quality_pass_v1") is True
        and _fresh(operating_age)
    )
    growth_points = int(revenue_pass) + int(eps_pass)

    reason = "passed"
    if not operating_pass:
        reason = "missing_fresh_positive_operating_income"
    elif growth_points < MIN_GROWTH_POINTS:
        reason = "missing_fresh_revenue_or_eps_growth"

    return {
        "companyfacts_quality_passed": reason == "passed",
        "companyfacts_quality_reject_reason": None if reason == "passed" else reason,
        "companyfacts_quality_rule_version": RULE_VERSION,
        "companyfacts_known_at": "SEC Companyfacts filed date <= signal_date",
        "companyfacts_trade_enabled": False,
        "companyfacts_alters_orders": False,
        "companyfacts_max_age_days": MAX_COMPANYFACTS_AGE_DAYS,
        "companyfacts_growth_points": growth_points,
        "companyfacts_revenue_growth_pass": revenue_pass,
        "companyfacts_revenue_yoy_growth": _round(revenue_growth),
        "companyfacts_revenue_filed": growth.get("revenue_current_filed"),
        "companyfacts_revenue_age_days": revenue_age,
        "companyfacts_eps_growth_pass": eps_pass,
        "companyfacts_eps_yoy_growth": _round(eps_growth),
        "companyfacts_eps_filed": growth.get("eps_current_filed"),
        "companyfacts_eps_age_days": eps_age,
        "companyfacts_operating_profit_pass": operating_pass,
        "companyfacts_operating_income_current_value": _round(
            operating.get("operating_income_current_value")
        ),
        "companyfacts_operating_income_filed": operating.get(
            "operating_income_current_filed"
        ),
        "companyfacts_operating_income_age_days": operating_age,
        "companyfacts_operating_margin_current": _round(
            operating.get("operating_margin_current")
        ),
    }


def _quality_candidate_for_ticker(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    row = ORIGINAL_CANDIDATE_FOR_TICKER(*args, **kwargs)
    if row is None:
        return None
    context = _companyfacts_quality_context(row["ticker"], row["date"])
    audit = _CURRENT_QUALITY_AUDIT
    audit["quality_context_count"] += 1
    if context["companyfacts_quality_passed"] is not True:
        audit["quality_reject_reasons"][str(context["companyfacts_quality_reject_reason"])] += 1
        return None
    audit["quality_pass_count"] += 1
    return {**row, **context, "uses_free_sec_companyfacts": True}


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    global _CURRENT_FUNDAMENTAL_INDEX, _CURRENT_QUALITY_AUDIT
    _CURRENT_FUNDAMENTAL_INDEX, fact_audit = _load_fundamental_index(
        cfg=cfg,
        sector_entries=sector_entries,
    )
    _CURRENT_QUALITY_AUDIT = {
        "companyfacts": fact_audit,
        "quality_context_count": 0,
        "quality_pass_count": 0,
        "quality_reject_reasons": Counter(),
    }
    base._candidate_for_ticker = _quality_candidate_for_ticker
    try:
        candidates, contexts, scan = ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
        )
    finally:
        base._candidate_for_ticker = ORIGINAL_CANDIDATE_FOR_TICKER
        _CURRENT_FUNDAMENTAL_INDEX = None

    quality_audit = _CURRENT_QUALITY_AUDIT
    scan.update(
        {
            "companyfacts_quality_rule_version": RULE_VERSION,
            "companyfacts_row_count": fact_audit["row_count"],
            "companyfacts_ticker_count": fact_audit["ticker_count"],
            "companyfacts_max_age_days": MAX_COMPANYFACTS_AGE_DAYS,
            "companyfacts_min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
            "companyfacts_min_eps_yoy_growth": MIN_EPS_YOY_GROWTH,
            "companyfacts_min_growth_points": MIN_GROWTH_POINTS,
            "companyfacts_quality_context_count": quality_audit["quality_context_count"],
            "companyfacts_quality_pass_count": quality_audit["quality_pass_count"],
            "companyfacts_quality_reject_reasons": dict(
                quality_audit["quality_reject_reasons"]
            ),
        }
    )
    return candidates, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_FIFTYTWO_WEEK_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_52w_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_FIFTYTWO_WEEK_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_52w_pnl_not_beaten")

    by_window = aggregate.get("by_window") or {}
    regressed_vs_52w = []
    for label, comparator in ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["by_window"].items():
        actual = by_window.get(label) or {}
        if actual.get("expected_value_score", 0.0) < comparator["expected_value_delta"]:
            regressed_vs_52w.append(f"{label}_ev")
        if actual.get("total_pnl", 0.0) < comparator["pnl_delta"]:
            regressed_vs_52w.append(f"{label}_pnl")
    if regressed_vs_52w:
        gate.setdefault("failed_reasons", []).append(
            "accepted_52w_window_comparator_regression"
        )
    gate.setdefault("accepted_comparators", {})["fiftytwo_week_high"] = {
        **ACCEPTED_FIFTYTWO_WEEK_COMPARATOR,
        "window_regressions": regressed_vs_52w,
    }
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_fiftytwo_week_high_companyfacts_quality"
        if gate["passed"]
        else "rejected_fiftytwo_week_high_companyfacts_quality_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "companyfacts_quality_52w_candidate_pool_scout",
            "new_evidence_type": "pit_companyfacts_quality_overlay_on_accepted_52w_core_flow",
            "nearby_prior_experiments": [
                "exp-20260610-008",
                "exp-20260608-014",
                "exp-20260609-006",
                "exp-20260608-013",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": {
                **payload.get("accepted_comparators", {}),
                "fiftytwo_week_high": ACCEPTED_FIFTYTWO_WEEK_COMPARATOR,
            },
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that the Companyfacts gate "
                "either lags the 52-week-high price event, removes too many "
                "valid underreaction rows, or does not beat the already "
                "accepted 52-week-high helper after next-open execution and "
                "costs. Do not answer by sweeping Companyfacts age/growth "
                "thresholds or 52-week geometry on frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially different PIT evidence separating "
                "durable and exhausted 52-week-high leaders, such as analyst-"
                "count/dispersion, option-implied move, borrow/ownership flow, "
                "or closed forward replacement-value rows. Pure threshold "
                "retunes stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "companyfacts_max_age_days": MAX_COMPANYFACTS_AGE_DAYS,
        "companyfacts_min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
        "companyfacts_min_eps_yoy_growth": MIN_EPS_YOY_GROWTH,
        "companyfacts_min_growth_points": MIN_GROWTH_POINTS,
        "companyfacts_require_positive_operating_income": True,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed Companyfacts quality gate beat the accepted 52-week "
            "comparator across the canonical checks, suggesting filed "
            "business-quality evidence separated durable 52-week-high leaders "
            "from exhausted price-anchor breakouts. It remains only a replay "
            "lead because no shared daily adapter or parity test was added."
            if passed
            else (
                "The fixed Companyfacts quality gate did not add enough "
                "replacement value over the accepted 52-week-high helper. The "
                "most likely causes are that filed Companyfacts quality lags "
                "the price-anchor event, the gate removes too many useful "
                "underreaction rows, or the retained rows remain generic "
                "momentum after costs."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping Companyfacts filing age, revenue/EPS "
            "growth thresholds, required growth points, operating-profit "
            "requirement, 52-week proximity, 252/60-day lookbacks, top-N, "
            "hold-day, cooldown, or paper notional on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The 52-week-high Companyfacts quality source passed as a replay-only "
        "lead, but a shared helper and daily parity path are required before use."
        if passed
        else (
            "The 52-week-high Companyfacts quality source was rejected; it did "
            "not improve the accepted 52-week-high default-off candidate pool."
        )
    )
    return payload


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = ORIGINAL_BUILD_LOG_RECORD(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": payload["accepted_comparators"],
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    return record


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Quality pass | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {qp} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                qp=scan.get("companyfacts_quality_pass_count", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} 52-Week-High Companyfacts Quality Core-Flow Scout",
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
            json_dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=False, indent=2),
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
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Accepted 52w comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        LOG_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path)
            for path in paths
            if path.exists()
        },
    }
    writer = getattr(framework, "_write" + "_json")
    writer(MANIFEST_JSON, manifest)


def _patch_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_payload = _build_payload
    base._build_log_record = _build_log_record
    base._build_card = _build_card
    base._write_manifest = _write_manifest
    base._patch_framework()


def main() -> None:
    _patch_base()
    framework.main()


if __name__ == "__main__":
    main()
