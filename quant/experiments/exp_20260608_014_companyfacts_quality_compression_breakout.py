"""exp-20260608-014: Companyfacts quality compression breakout scout.

Replay-only alpha search. It tests whether the accepted narrow-range
compression breakout candidate source improves when restricted to stocks with
fresh SEC Companyfacts evidence of revenue growth, EPS growth, and positive
operating income.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive numeric
result remains a private replay lead until a shared PIT Companyfacts helper
proves historical and daily parity.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260608_012_narrow_range_compression_breakout as base  # noqa: E402
import fundamental_growth_rs_paper_sleeve as fundamentals  # noqa: E402


framework = base.framework

EXPERIMENT_ID = "exp-20260608-014"
STEM = "companyfacts_quality_compression_breakout"
TRIAL_FAMILY = "companyfacts_quality_compression_breakout_candidate_pool"
TRIAL_VARIANT_ID = "companyfacts_quality_compression_breakout_top1_next_open_10d_v1"
CHANGED_VARIABLE = "companyfacts_quality_compression_breakout_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_014_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS
MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

MAX_COMPANYFACTS_AGE_DAYS = 120
MIN_REVENUE_YOY_GROWTH = 0.10
MIN_EPS_YOY_GROWTH = 0.10
REQUIRE_POSITIVE_OPERATING_INCOME = True

COMPANYFACTS_CONFIG = {
    **fundamentals.DEFAULT_CONFIG,
    "eps_growth_threshold": MIN_EPS_YOY_GROWTH,
    "revenue_growth_threshold": MIN_REVENUE_YOY_GROWTH,
    "min_fundamental_points": 2,
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "companyfacts_proxy_or_stale_data",
        "ohlcv_momentum_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Narrow-range compression just produced a small positive lead, and "
        "Companyfacts operating quality has historically been useful as a "
        "default-off support field. The risk is that Companyfacts candidate "
        "pool extensions have often been proxy-grade or too sparse, so this "
        "run is only a private replay scout."
    ),
    "recorded_at": "2026-06-08T13:08:00Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_companyfacts_adapter",
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
    "parity_note": (
        "This experiment changes no production code. It reads only SEC "
        "Companyfacts rows with filed date <= signal date in historical replay. "
        "A positive result cannot be promoted until a shared helper computes "
        "the same filing-recency, revenue-growth, EPS-growth, operating-profit, "
        "compression-breakout, next-open paper entry, 10-trading-day exit, "
        "cost, cooldown, and concentration semantics in both historical replay "
        "and daily default-off production snapshots."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float(value)
    if number is None:
        return None
    return round(number, digits)


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
            "require_positive_operating_income": REQUIRE_POSITIVE_OPERATING_INCOME,
        },
    }


def _companyfacts_quality_context(
    *,
    index: fundamentals.CompanyfactsFundamentalIndex,
    ticker: str,
    signal_date: str,
) -> dict[str, Any]:
    growth = index.fundamental_context(ticker, signal_date)
    operating = index.operating_quality(ticker, signal_date)

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
    eps_pass = eps_growth is not None and eps_growth >= MIN_EPS_YOY_GROWTH and _fresh(eps_age)
    operating_pass = (
        operating.get("operating_profit_quality_pass_v1") is True and _fresh(operating_age)
    )
    passed = revenue_pass and eps_pass and operating_pass
    if not revenue_pass:
        reason = "revenue_growth_or_recency_failed"
    elif not eps_pass:
        reason = "eps_growth_or_recency_failed"
    elif not operating_pass:
        reason = "operating_profit_or_recency_failed"
    else:
        reason = "passed"

    return {
        "companyfacts_quality_rule_version": RULE_VERSION,
        "companyfacts_quality_known_at": "SEC Companyfacts filed date <= signal_date",
        "companyfacts_quality_passed": passed,
        "companyfacts_quality_reject_reason": reason,
        "companyfacts_revenue_yoy_growth": _round(revenue_growth),
        "companyfacts_revenue_growth_status": growth.get("revenue_growth_status"),
        "companyfacts_revenue_current_filed": growth.get("revenue_current_filed"),
        "companyfacts_revenue_filing_age_days": revenue_age,
        "companyfacts_eps_yoy_growth": _round(eps_growth),
        "companyfacts_eps_growth_source": growth.get("eps_growth_source"),
        "companyfacts_eps_growth_status": growth.get("eps_growth_status"),
        "companyfacts_eps_current_filed": growth.get("eps_current_filed"),
        "companyfacts_eps_filing_age_days": eps_age,
        "companyfacts_operating_income_current_value": operating.get(
            "operating_income_current_value"
        ),
        "companyfacts_operating_income_status": operating.get("operating_income_status"),
        "companyfacts_operating_income_current_filed": operating.get(
            "operating_income_current_filed"
        ),
        "companyfacts_operating_income_filing_age_days": operating_age,
        "companyfacts_operating_margin_current": operating.get("operating_margin_current"),
        "companyfacts_revenue_growth_pass": revenue_pass,
        "companyfacts_eps_growth_pass": eps_pass,
        "companyfacts_operating_profit_pass": operating_pass,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    fundamental_index, fundamental_coverage = _load_fundamental_index(
        cfg=cfg, sector_entries=sector_entries
    )
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    reject_reasons: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_raw_compression_breakout_candidates": 0,
        "days_with_companyfacts_quality_candidates": 0,
        "raw_compression_breakout_candidates": 0,
        "companyfacts_quality_candidates": 0,
        "companyfacts_quality_reject_reasons": {},
        "fundamental_coverage": fundamental_coverage,
    }
    for signal_date in dates:
        raw_rows: list[dict[str, Any]] = []
        quality_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = base._candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if row is None:
                continue
            raw_rows.append(row)
            context = _companyfacts_quality_context(
                index=fundamental_index, ticker=ticker, signal_date=signal_date
            )
            if context["companyfacts_quality_passed"] is not True:
                reject_reasons[str(context["companyfacts_quality_reject_reason"])] += 1
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row.update(context)
            row.update(
                {
                    "source": "COMPANYFACTS_QUALITY_COMPRESSION_BREAKOUT_PAPER",
                    "rule_version": RULE_VERSION,
                    "uses_free_ohlcv_only": False,
                    "uses_free_sec_companyfacts": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                }
            )
            quality_rows.append(row)
        if raw_rows:
            scan["days_with_raw_compression_breakout_candidates"] += 1
            scan["raw_compression_breakout_candidates"] += len(raw_rows)
        if not quality_rows:
            continue
        quality_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_range_expansion_ratio"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(quality_rows)
        scan["days_with_companyfacts_quality_candidates"] += 1
        scan["companyfacts_quality_candidates"] += len(quality_rows)
        top = quality_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(raw_rows),
                "quality_candidate_count": len(quality_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_revenue_yoy_growth": top.get("companyfacts_revenue_yoy_growth"),
                "top_candidate_eps_yoy_growth": top.get("companyfacts_eps_yoy_growth"),
                "top_candidate_operating_margin": top.get(
                    "companyfacts_operating_margin_current"
                ),
                "top_candidate_range_expansion_ratio": top[
                    "candidate_range_expansion_ratio"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_range_expansion_ratio"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "base_rule_version": base.RULE_VERSION,
            "companyfacts_quality_reject_reasons": dict(reject_reasons),
            "compression_lookback_days": base.COMPRESSION_LOOKBACK_DAYS,
            "reference_range_lookback_days": base.REFERENCE_RANGE_LOOKBACK_DAYS,
            "max_companyfacts_age_days": MAX_COMPANYFACTS_AGE_DAYS,
            "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
            "min_eps_yoy_growth": MIN_EPS_YOY_GROWTH,
            "require_positive_operating_income": REQUIRE_POSITIVE_OPERATING_INCOME,
        }
    )
    return candidates, day_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    numeric_gate = base.BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    numeric_passed = bool(numeric_gate["passed"])
    if numeric_passed:
        return {
            **numeric_gate,
            "numeric_passed": True,
            "passed": False,
            "decision": "positive_replay_lead_not_promoted_companyfacts_quality_compression_breakout",
            "failed_reasons": ["private_replay_requires_shared_pit_companyfacts_adapter"],
            "promotion_blockers": [
                "no_shared_historical_and_daily_companyfacts_quality_helper",
                "private_replay_only_not_production_visible",
            ],
        }
    return {
        **numeric_gate,
        "numeric_passed": False,
        "decision": "rejected_companyfacts_quality_compression_breakout_candidate_pool",
    }


def _patch_framework() -> None:
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
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4


def _build_payload() -> dict[str, Any]:
    payload = base.BASE_BUILD_PAYLOAD()
    numeric_passed = bool(payload["gate4"].get("numeric_passed"))
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Fresh profitable SEC Companyfacts quality can anchor the "
                "accepted narrow-range compression breakout candidate source, "
                "expanding the default-off broad candidate pool through recent "
                "fundamental information absorption rather than raw ticker noise."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "companyfacts_quality_candidate_pool_scout",
            "new_evidence_type": "free_sec_companyfacts_quality_overlay_on_compression_breakout",
            "nearby_prior_experiments": [
                "exp-20260608-012",
                "exp-20260608-013",
                "exp-20260528-016",
                "exp-20260528-017",
                "exp-20260605-011",
                "exp-20260605-015",
            ],
            "prior_trial_count": 6,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that adding fresh "
                "Companyfacts quality makes the already selective compression "
                "source too sparse, or that the fundamental rows lag the price "
                "event and remove the timely accumulation signal. Do not answer "
                "by loosening one threshold on the same frozen windows unless "
                "new forward or shared-adapter evidence appears."
            ),
            "next_evidence_needed": (
                "A positive numeric result requires a shared PIT Companyfacts "
                "quality helper with daily default-off snapshots before "
                "promotion. A negative result should move away from this "
                "Companyfacts-compression intersection and seek a different "
                "free-data candidate-pool edge."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "base_compression_rule_version": base.RULE_VERSION,
            "max_companyfacts_age_days": MAX_COMPANYFACTS_AGE_DAYS,
            "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
            "min_eps_yoy_growth": MIN_EPS_YOY_GROWTH,
            "require_positive_operating_income": REQUIRE_POSITIVE_OPERATING_INCOME,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool: fresh SEC Companyfacts revenue/EPS/operating "
            "quality should distinguish accumulation after volatility "
            "compression from low-quality price spikes."
        ),
        "2_history_check": {
            "exp-20260608-012": (
                "Positive replay lead for narrow-range compression breakout; "
                "small edge, not live-ready."
            ),
            "exp-20260608-013": (
                "Accepted shared default-off adapter for the same compression "
                "source; avoid retuning its OHLCV thresholds."
            ),
            "exp-20260528-016/017": (
                "Companyfacts support layers helped as default-off context but "
                "need strict production/replay parity before promotion."
            ),
            "exp-20260605-011/015": (
                "Several Companyfacts candidate-pool or quality attempts were "
                "too sparse or proxy-grade; this run is intentionally a scout."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Numeric pass "
            "requires aggregate EV/PnL improvement, no EV/PnL regression "
            "window, target sample >=20 across all 3 windows, survival >=5%, "
            "drawdown drift <=0.5pp, and concentration guard pass. Promotion "
            "also requires a shared PIT Companyfacts helper, so this private "
            "run cannot be accepted even if numeric Gate 4 passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_014_companyfacts_quality_compression_breakout.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted" if numeric_passed else "rejected"
    )
    payload["interpretation"] = (
        "Numeric Gate 4 passed, but this remains an unpromoted private "
        "Companyfacts replay lead until shared historical/daily parity exists."
        if numeric_passed
        else (
            "The Companyfacts quality overlay did not clear numeric Gate 4. "
            "Do not promote it or retune the same thresholds on frozen windows."
        )
    )
    payload["rejection_reason"] = (
        "private_replay_requires_shared_pit_companyfacts_adapter"
        if numeric_passed
        else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = (
        {
            "why_result_happened": (
                "The fixed Companyfacts quality overlay cleared the numeric "
                "three-window replacement-value gates, but the evidence is not "
                "promotion-grade because the rule is implemented only inside a "
                "private replay runner. Production parity would need a shared "
                "PIT filing helper that emits the same daily default-off fields."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not claim this as accepted alpha or live-ready by only "
                "switching trade_enabled. Do not sweep revenue, EPS, filing-age, "
                "or compression thresholds on the same frozen windows."
            ),
            "new_evidence_required": (
                "Implement a shared historical/daily Companyfacts quality "
                "adapter and then rerun Gate 1-4 unchanged, or collect forward "
                "replacement-value rows proving the same source outside the "
                "frozen windows."
            ),
        }
        if numeric_passed
        else {
            "why_result_happened": (
                "The fixed quality overlay either made the compression source "
                "too sparse or selected filings whose fundamental confirmation "
                "lagged the price absorption event, so the three-window EV/PnL "
                "replacement value did not survive the standard gates."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by only relaxing revenue growth, EPS growth, "
                "filing age, operating-profit, hold-day, notional, or "
                "compression thresholds on the same windows."
            ),
            "new_evidence_required": (
                "A useful retry needs materially new data, such as a shared "
                "PIT filing timeliness/surprise layer or forward closed "
                "replacement-value evidence; otherwise move to a different "
                "free-data alpha family."
            ),
        }
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _window_card_rows(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw days | Quality days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw_days} | {quality_days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw_days=scan.get("days_with_raw_compression_breakout_candidates", 0),
                quality_days=scan.get("days_with_companyfacts_quality_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Companyfacts Quality Compression Breakout",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *_window_card_rows(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Private replay only. No shared policy, production adapter, "
                "watchlist, order path, core entry, ranking, sizing, or exit "
                "behavior changed."
            ),
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
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
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
                "raw_compression_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_compression_breakout_candidates"
                ),
                "quality_candidate_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_companyfacts_quality_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": False,
                "numeric_passed": bool(payload["gate4"].get("numeric_passed")),
                "calibration": payload["calibration"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(framework._safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    _patch_framework()
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
