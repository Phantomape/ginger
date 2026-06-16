"""exp-20260616-026: FINRA borrow-pressure BROAD-universe candidate scout.

Replay-only alpha search. Same fixed borrow-pressure gate as exp-20260603-006 /
exp-20260616-024 (days_to_cover >= 3.0 AND short_interest_change_pct > 0, PIT
join on publication date), but candidates are scanned over the BROAD liquid
universe (~1440 backfilled FINRA tickers) instead of the ~47-name core. The
core baseline stays core-only; the broad FINRA paper trades are an additive
default-off overlay measured on top of it.

Rationale: the core universe is too liquid for days_to_cover >= 3 (mega-caps
print ~2-3), so exp-20260616-024 had a thin, fragile signal. Forced-covering
continuation should be strongest in higher-short small/mid names, which only the
broad backfilled archive (exp-20260616-020) makes testable across all three
windows.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
import exp_20260616_024_finra_borrow_pressure_three_window as v


EXPERIMENT_ID = "exp-20260616-026"
STEM = "finra_borrow_pressure_broad_universe"
TRIAL_FAMILY = "finra_borrow_pressure_broad_universe"
TRIAL_VARIANT_ID = "finra_borrow_pressure_dtc3_short_rising_broad_top1_next_open_10d_v1"
CHANGED_VARIABLE = "finra_borrow_pressure_broad_universe_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_026_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_FINRA_DAYS_TO_COVER = v.MIN_FINRA_DAYS_TO_COVER
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = v.MIN_FINRA_SHORT_INTEREST_CHANGE_PCT
MAX_FINRA_PUBLICATION_AGE_DAYS = v.MAX_FINRA_PUBLICATION_AGE_DAYS

PREDICTION = {
    "success_probability": 0.30,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "broad_universe_concentration",
        "window_regression",
        "accepted_comparator_not_beaten",
        "drawdown_drift",
        "survivorship_or_liquidity_leak",
    ],
    "confidence_reason": (
        "The core universe is too liquid for days-to-cover above three, so "
        "exp-20260616-024 had a thin fragile signal; the broad liquid universe "
        "holds the higher-short small and mid names where forced covering is "
        "strongest, and the archive now covers all three windows. Disconfirmer: "
        "a broad squeeze pool may concentrate in a few violent names, relabel "
        "small-cap momentum, or fail comparator and drawdown guards."
    ),
    "recorded_at": "2026-06-16T21:10:00+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_broad_universe_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_finra_short_interest": True,
    "broad_universe": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing FINRA row published on/before signal date, stale latest "
            "print, days_to_cover below 3.0, non-positive short-interest change, "
            "missing broad-universe OHLCV, missing next open, or missing 10d exit "
            "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "Replay-only. Candidates scan the broad liquid universe; the core "
        "baseline is unchanged core-only. No shared helper, live orders, "
        "ranking, sizing, exits, or watchlists change. A positive broad result "
        "would justify a shared-paper-first broad FINRA helper, not a live order."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT FINRA borrow-pressure (days_to_cover >= 3.0 AND "
        "short_interest_change_pct > 0) scanned over the broad liquid universe "
        "with liquid SPY-relative confirmation may add positive next-open 10-day "
        "replacement value on top of the core baseline across all three windows."
    ),
    "2_history_check": {
        "exp-20260603-006": (
            "Accepted borrow-pressure on a 42-ticker archive (all 3 windows, EV "
            "+0.2585). This run widens the candidate universe to ~1440 names."
        ),
        "exp-20260616-024": (
            "Core-universe out-of-sample test was rejected (late_strong "
            "regressed); the core pool is too liquid for high days-to-cover."
        ),
        "exp-20260616-020": (
            "Backfilled the FINRA archive to 1440 tickers across all 3 windows, "
            "which makes this broad test possible."
        ),
        "exp-20260613-023": (
            "Widened the live FINRA candidate universe to broad; this run is the "
            "historical-window analogue of that broadening."
        ),
        "exp-20260529-017": (
            "Early narrow short-pressure breakout variant rejected on thin data."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260616_026_finra_borrow_pressure_broad_universe.py"
    ),
}

_BROAD_UNIVERSE_CACHE: set[str] | None = None
_ORIG_LOAD_WINDOW_SNAPSHOT = base._load_window_snapshot


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _broad_universe() -> set[str]:
    global _BROAD_UNIVERSE_CACHE
    if _BROAD_UNIVERSE_CACHE is None:
        index, _summary = v._load_finra_index()
        _BROAD_UNIVERSE_CACHE = set(index.keys())
    return _BROAD_UNIVERSE_CACHE


def _broad_load_window_snapshot(*, cfg: dict[str, str], eligible_tickers: set[str]) -> dict[str, Any]:
    """Load OHLCV for the BROAD FINRA universe (plus whatever was requested).

    The base payload builder asks for the core universe; we expand it to the
    full backfilled FINRA universe so candidates can be scanned broadly. The
    core baseline is computed separately by shadow._run_baseline on the core
    universe and is unaffected.
    """
    expanded = set(eligible_tickers) | _broad_universe()
    return _ORIG_LOAD_WINDOW_SNAPSHOT(cfg=cfg, eligible_tickers=expanded)


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = v._load_finra_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "finra_short_interest_rows_json_publication_date_pit_broad_universe",
        "broad_universe": True,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []

    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            observation = v._finra_borrow_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_borrow_pressure_gate"] += 1
                continue
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            days_to_cover = float(observation["days_to_cover"] or 0.0)
            short_change_pct = float(observation["short_interest_change_pct"] or 0.0)
            score = (
                0.10 * min(days_to_cover, 15.0)
                + 0.010 * min(short_change_pct, 50.0)
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "FINRA_BORROW_PRESSURE_BROAD_PAPER",
                    "candidate_score": base._round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_finra_short_interest": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"finra_{k}": val for k, val in observation.items()},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["finra_days_to_cover"] or 0.0),
            -float(row["finra_short_interest_change_pct"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "broad_universe_size": len(_broad_universe()),
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "max_finra_publication_age_days": MAX_FINRA_PUBLICATION_AGE_DAYS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_finra_borrow_pressure_broad_universe"
        if gate["passed"]
        else "rejected_finra_borrow_pressure_broad_universe"
    )
    return gate


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
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
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._load_window_snapshot = _broad_load_window_snapshot


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "Broad-universe FINRA borrow-pressure produced positive three-window "
            "replacement value on top of the core baseline. This is a replay "
            "lead; a shared-paper-first broad FINRA helper plus parity is the next "
            "step, not a live order."
        )
    else:
        interpretation = (
            "Broad-universe FINRA borrow-pressure did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The "
            "squeeze-fuel effect does not produce robust replacement value even "
            "in the broad short-interest population; do not retune the fixed "
            "thresholds on the frozen windows."
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "lane": "alpha_search",
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_finra_short_interest_candidate_pool",
            "new_evidence_type": "finra_broad_universe_borrow_pressure_replay",
            "nearby_prior_experiments": [
                "exp-20260603-006",
                "exp-20260616-024",
                "exp-20260616-020",
                "exp-20260613-023",
                "exp-20260529-017",
            ],
            "prior_trial_count": 2,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "base_notional_usd": base.BASE_NOTIONAL_USD,
        "hold_days": base.HOLD_DAYS,
        "max_paper_trades_per_day": base.MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": base.SAME_TICKER_COOLDOWN_DAYS,
        "broad_universe_size": len(_broad_universe()),
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "max_finra_publication_age_days": MAX_FINRA_PUBLICATION_AGE_DAYS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Candidates scan the broad backfilled FINRA liquid universe. FINRA "
        "biweekly rows are joined PIT by publication date (usable_trade_date <= "
        "signal date), latest print within 25 days only. The fixed "
        "borrow-pressure gate (days_to_cover >= 3.0 AND short_interest_change_pct "
        "> 0) plus signal-date OHLCV confirmation selects top-1/day. Core "
        "baseline is unchanged core-only; broad paper trades are an additive "
        "overlay. Next-open entry, 10-day exit, entry/exit slippage, "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["finra_source"] = _repo_rel(v.FINRA_ROWS_PATH)
    payload["gate2"]["runtime_fields"] = [
        "FINRA short_interest, short_interest_change_pct, days_to_cover",
        "FINRA settlement_date, publication_date, usable_trade_date (PIT)",
        "broad warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If positive, promote a shared-paper-first BROAD FINRA helper with "
        "historical replay + daily snapshot + parity test, and collect closed "
        "forward replacement-value rows. If negative, FINRA short interest is not "
        "standalone entry alpha even broadly; use it as crowding/risk context and "
        "require a materially different PIT borrow-cost / availability field "
        "before any retry. Do not threshold-sweep the frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping days_to_cover, short-interest-change, "
            "freshness, RS/close/volume guards, universe liquidity floor, top-N, "
            "hold, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} FINRA Borrow-Pressure Broad Universe",
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
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Broad universe size: `{}`".format(len(_broad_universe())),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only broad-universe scout. Core baseline unchanged "
                "core-only. No shared policy, run/backtester adapter, watchlist, "
                "order path, ranking, sizing, or exit behavior changed."
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
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": base.DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "eligible_quality_tickers": payload["context_scan_by_window"][label].get(
                    "eligible_quality_tickers"
                ),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


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
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
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
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
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
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
