"""exp-20260603-017: SEC credible-reaction consensus source-family scout.

Replay-only alpha search. This tests one variable: whether high/medium
credibility SEC filings that have a positive signal-day reaction add an
independent source family to the accepted free-data consensus.

No shared adapter, production orders, watchlists, ranking, sizing, exits, LLM,
news, or default trade surfaces are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_041_opening_range_continuation_shadow as opening_shadow
import exp_20260603_014_accepted_consensus_independent_source_family as consensus


EXPERIMENT_ID = "exp-20260603-017"
STEM = "sec_credible_reaction_consensus_source_family"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_source_family"
CHANGED_VARIABLE = "sec_credible_positive_reaction_source_family_presence_added_to_independent_consensus_v1"
RULE_VERSION = "independent_source_family_with_sec_credible_reaction_v1"

ROOT = consensus.ROOT
OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_017_{STEM}.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")

SEC_SOURCE = "SEC_CREDIBLE_REACTION_PAPER"
SEC_SOURCE_EXPERIMENT_ID = EXPERIMENT_ID
SEC_SOURCE_FAMILY = "sec_credible_positive_reaction"
SEC_EVENTS_FILE = Path("data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl")
CURRENT_ACCEPTED_CONSENSUS_ARTIFACT = Path(
    "data/experiments/exp-20260603-014/accepted_consensus_independent_source_family.json"
)

MIN_SIGNAL_DAY_EXCESS_VS_SPY = 0.01
MIN_SIGNAL_DAY_RETURN = 0.0

SOURCE_FILES = {**consensus.SOURCE_FILES}
SOURCE_EXPERIMENT_IDS = {
    **consensus.SOURCE_EXPERIMENT_IDS,
    SEC_SOURCE: SEC_SOURCE_EXPERIMENT_ID,
}
SOURCE_FAMILIES = {
    **consensus.SOURCE_FAMILIES,
    SEC_SOURCE: SEC_SOURCE_FAMILY,
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained lead would need "
        "a shared default-off SEC source-row adapter that uses the same filing "
        "credibility, PIT usable_trade_date, signal-day OHLCV reaction, and "
        "independent source-family consensus in both replay and daily run paths "
        "before any candidate queue or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_consensus_module() -> None:
    consensus.EXPERIMENT_ID = EXPERIMENT_ID
    consensus.STEM = STEM
    consensus.TRIAL_FAMILY = TRIAL_FAMILY
    consensus.CHANGED_VARIABLE = CHANGED_VARIABLE
    consensus.RULE_VERSION = RULE_VERSION
    consensus.SOURCE_FILES = SOURCE_FILES
    consensus.SOURCE_EXPERIMENT_IDS = SOURCE_EXPERIMENT_IDS
    consensus.SOURCE_FAMILIES = SOURCE_FAMILIES
    consensus.OUT_DIR = OUT_DIR
    consensus.OUT_JSON = OUT_JSON
    consensus.BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
    consensus.AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
    consensus.LOG_JSON = LOG_JSON
    consensus.TICKET_JSON = TICKET_JSON
    consensus.CARD_MD = CARD_MD
    consensus.EXPERIMENT_LOG = EXPERIMENT_LOG
    consensus.REGISTRY_JSON = REGISTRY_JSON
    consensus.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    consensus._configure_prior_module()
    consensus.prior._configure_base_module()
    consensus.prior.base.shadow = opening_shadow


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _value(row: dict[str, Any], key: str) -> float | None:
    value = _as_float(row.get(key))
    if value is not None:
        return value
    return _as_float(row.get(key.lower()))


def _series(snapshot: dict[str, list[dict[str, Any]]], ticker: str) -> list[dict[str, Any]]:
    return sorted(snapshot.get(ticker.upper()) or snapshot.get(ticker.lower()) or [], key=_date)


def _close_to_close_return(rows: list[dict[str, Any]], signal_date: str) -> float | None:
    index_by_date = {_date(row): index for index, row in enumerate(rows)}
    index = index_by_date.get(signal_date)
    if index is None or index <= 0:
        return None
    previous_close = _value(rows[index - 1], "Close")
    signal_close = _value(rows[index], "Close")
    if previous_close is None or previous_close <= 0 or signal_close is None:
        return None
    return (signal_close / previous_close) - 1.0


def _load_sec_events() -> list[dict[str, Any]]:
    path = ROOT / SEC_EVENTS_FILE
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            if isinstance(row, dict):
                events.append(row)
    return events


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw_codes = row.get("eight_k_item_codes")
    codes: set[str] = set()
    if isinstance(raw_codes, list):
        codes.update(str(item).strip() for item in raw_codes if str(item).strip())
    elif raw_codes:
        codes.update(str(raw_codes).replace(";", ",").split(","))
    items_raw = row.get("items_raw")
    if items_raw:
        codes.update(str(item).strip() for item in str(items_raw).replace(";", ",").split(","))
    return {code for code in codes if code}


def _source_credibility_bucket(row: dict[str, Any]) -> str | None:
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    form_base = form_type.split("/")[0]
    if form_base in {"10-K", "10-Q"}:
        return "high"
    if form_base == "8-K" and (_item_codes(row) & {"2.02", "2.05"}):
        return "medium"
    return None


def _sec_source_row(row: dict[str, Any], signal_return: float, spy_return: float) -> dict[str, Any]:
    excess_return = signal_return - spy_return
    signal_date = str(row.get("usable_trade_date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    return {
        "source_name": SEC_SOURCE,
        "source_experiment_id": SEC_SOURCE_EXPERIMENT_ID,
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "form_type": row.get("form_type"),
        "form_base": row.get("form_base"),
        "eight_k_item_codes": sorted(_item_codes(row)),
        "sec_accession_number": row.get("accession_number"),
        "accepted_at": row.get("accepted_at"),
        "usable_trade_date": signal_date,
        "source_credibility_bucket": _source_credibility_bucket(row),
        "signal_day_return_pct": round(signal_return * 100.0, 6),
        "signal_day_spy_return_pct": round(spy_return * 100.0, 6),
        "signal_day_excess_return_vs_spy_pct": round(excess_return * 100.0, 6),
        "min_signal_day_excess_vs_spy_pct": MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0,
        "known_at": f"{signal_date}T21:00:00Z",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _sec_rows_for_window(
    events: list[dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = str(cfg["start"])
    end = str(cfg["end"])
    spy_rows = _series(snapshot, "SPY")
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    rejection_counts: Counter[str] = Counter()
    raw_in_window = 0
    eligible_credible = 0

    for event in events:
        signal_date = str(event.get("usable_trade_date") or "")[:10]
        ticker = str(event.get("ticker") or "").upper()
        if not signal_date or signal_date < start or signal_date > end:
            continue
        raw_in_window += 1
        if not ticker:
            rejection_counts["missing_ticker"] += 1
            continue
        credibility = _source_credibility_bucket(event)
        if credibility is None:
            rejection_counts["low_credibility_form_or_item"] += 1
            continue
        eligible_credible += 1
        ticker_rows = _series(snapshot, ticker)
        if not ticker_rows or not spy_rows:
            rejection_counts["missing_ohlcv"] += 1
            continue
        signal_return = _close_to_close_return(ticker_rows, signal_date)
        spy_return = _close_to_close_return(spy_rows, signal_date)
        if signal_return is None or spy_return is None:
            rejection_counts["missing_signal_day_reaction"] += 1
            continue
        excess_return = signal_return - spy_return
        if signal_return < MIN_SIGNAL_DAY_RETURN:
            rejection_counts["negative_signal_day_return"] += 1
            continue
        if excess_return < MIN_SIGNAL_DAY_EXCESS_VS_SPY:
            rejection_counts["insufficient_signal_day_excess_vs_spy"] += 1
            continue
        source_row = _sec_source_row(event, signal_return, spy_return)
        key = (signal_date, ticker)
        previous = rows_by_key.get(key)
        if previous is None or float(source_row["signal_day_excess_return_vs_spy_pct"]) > float(
            previous["signal_day_excess_return_vs_spy_pct"]
        ):
            rows_by_key[key] = source_row

    rows = sorted(
        rows_by_key.values(),
        key=lambda item: (
            str(item["signal_date"]),
            -float(item["signal_day_excess_return_vs_spy_pct"]),
            str(item["ticker"]),
        ),
    )
    audit = {
        "raw_event_count_in_window": raw_in_window,
        "eligible_high_or_medium_credibility_count": eligible_credible,
        "source_row_count": len(rows),
        "dedupe_rule": "one_best_excess_return_row_per_signal_date_ticker",
        "min_signal_day_return_pct": MIN_SIGNAL_DAY_RETURN * 100.0,
        "min_signal_day_excess_vs_spy_pct": MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0,
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "credibility_counts_selected": dict(
            sorted(Counter(str(row["source_credibility_bucket"]) for row in rows).items())
        ),
    }
    return rows, audit


def _source_rows_by_window_with_sec() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    combined = consensus.prior._source_rows_by_window()
    events = _load_sec_events()
    audit: dict[str, Any] = {
        "source": SEC_SOURCE,
        "source_experiment_id": SEC_SOURCE_EXPERIMENT_ID,
        "source_file": str(SEC_EVENTS_FILE).replace("\\", "/"),
        "credibility_rule": "10-K/10-Q high, 8-K item 2.02 or 2.05 medium",
        "positive_reaction_rule": (
            "usable_trade_date close-to-close return must be positive and exceed SPY by at least "
            f"{MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0:.2f}%"
        ),
        "windows": {},
    }
    for label, cfg in consensus.prior.base.WINDOWS.items():
        snapshot = consensus.prior.base.shadow._load_snapshot(cfg["snapshot"])
        sec_rows, window_audit = _sec_rows_for_window(events, snapshot, cfg)
        audit["windows"][label] = window_audit
        for source_row in sec_rows:
            signal_date = str(source_row.get("signal_date") or source_row.get("date") or "")
            ticker = str(source_row.get("ticker") or "").upper()
            if not signal_date or not ticker:
                continue
            combined[label][(signal_date, ticker)].append(source_row)
    return combined, audit


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "A high/medium credibility SEC filing with a positive signal-day reaction may be a "
            "free, production-visible source family that improves the accepted independent-source "
            "consensus when it confirms an already accepted source on the same ticker/date."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "Follows the playbook preference for broad, free, production-visible default-off "
            "candidate-pool sources. It avoids LLM soft-ranking, state-surface retuning, and "
            "Companyfacts/Form 4 nearby retries."
        ),
        "nearby_prior_experiments": [
            "exp-20260603-001",
            "exp-20260603-016",
            "exp-20260521-005",
            "exp-20260521-006",
            "exp-20260521-015",
        ],
        "prior_difference": (
            "Prior SEC source-quality runs used event/text quality as direct overlays. This run "
            "only admits the SEC event as a separate confirming source family when the market has "
            "already reacted positively on the PIT usable trade date, and it must beat the current "
            "accepted independent-source consensus comparator."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "beats_current_accepted_consensus": "required for source-family expansion retention",
            "minimum_target_trades": consensus.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": consensus.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": consensus.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": consensus.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": consensus.prior.MAX_POSITIVE_HHI,
            "source_family_min_count": consensus.MIN_SOURCE_FAMILY_COUNT,
        },
        "reproducibility": (
            "The runner persists SEC source-row construction audits, canonical before/after "
            "metrics, target trades, target source-family composition, and Gate 4 diagnostics."
        ),
    }


def _current_accepted_consensus_comparison(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    source = consensus.prior._load_json(ROOT / CURRENT_ACCEPTED_CONSENSUS_ARTIFACT)
    source_results = {str(row["label"]): row for row in source.get("results", [])}
    window_rows: list[dict[str, Any]] = []
    windows_ev_regressed: list[str] = []
    windows_pnl_regressed: list[str] = []
    for row in results:
        label = str(row["label"])
        source_row = source_results[label]
        candidate_after_ev = float(row["after"]["expected_value_score"])
        source_after_ev = float(source_row["after"]["expected_value_score"])
        candidate_after_pnl = float(row["after"]["total_pnl"])
        source_after_pnl = float(source_row["after"]["total_pnl"])
        ev_delta = round(candidate_after_ev - source_after_ev, 6)
        pnl_delta = round(candidate_after_pnl - source_after_pnl, 2)
        if ev_delta < 0:
            windows_ev_regressed.append(label)
        if pnl_delta < 0:
            windows_pnl_regressed.append(label)
        window_rows.append(
            {
                "label": label,
                "candidate_after_expected_value": candidate_after_ev,
                "current_accepted_after_expected_value": source_after_ev,
                "after_expected_value_delta_vs_current_accepted": ev_delta,
                "candidate_after_total_pnl": candidate_after_pnl,
                "current_accepted_after_total_pnl": source_after_pnl,
                "after_total_pnl_delta_vs_current_accepted": pnl_delta,
                "candidate_target_trade_count": row["target_trade_count"],
                "current_accepted_target_trade_count": source_row["target_trade_count"],
            }
        )
    aggregate_ev_delta = round(
        float(aggregate["after"]["expected_value_score"])
        - float(source["aggregate"]["after"]["expected_value_score"]),
        6,
    )
    aggregate_pnl_delta = round(
        float(aggregate["after"]["strategy_total_pnl"])
        - float(source["aggregate"]["after"]["strategy_total_pnl"]),
        2,
    )
    return {
        "comparison_artifact": str(CURRENT_ACCEPTED_CONSENSUS_ARTIFACT).replace("\\", "/"),
        "current_accepted_experiment_id": str(source.get("experiment_id")),
        "candidate_after_expected_value": aggregate["after"]["expected_value_score"],
        "current_accepted_after_expected_value": source["aggregate"]["after"]["expected_value_score"],
        "after_expected_value_delta_vs_current_accepted": aggregate_ev_delta,
        "candidate_after_strategy_total_pnl": aggregate["after"]["strategy_total_pnl"],
        "current_accepted_after_strategy_total_pnl": source["aggregate"]["after"][
            "strategy_total_pnl"
        ],
        "after_strategy_total_pnl_delta_vs_current_accepted": aggregate_pnl_delta,
        "beats_current_accepted_ev": aggregate_ev_delta > 0,
        "beats_current_accepted_pnl": aggregate_pnl_delta > 0,
        "windows_ev_regressed_vs_current_accepted": windows_ev_regressed,
        "windows_pnl_regressed_vs_current_accepted": windows_pnl_regressed,
        "by_window": window_rows,
    }


def _apply_current_accepted_guard(
    gate4: dict[str, Any],
    current_comparison: dict[str, Any],
) -> dict[str, Any]:
    gate4["gates"]["beats_current_accepted_consensus_ev"] = bool(
        current_comparison["beats_current_accepted_ev"]
    )
    gate4["gates"]["beats_current_accepted_consensus_pnl"] = bool(
        current_comparison["beats_current_accepted_pnl"]
    )
    gate4["gates"]["no_window_ev_regression_vs_current_accepted_consensus"] = not bool(
        current_comparison["windows_ev_regressed_vs_current_accepted"]
    )
    gate4["gates"]["no_window_pnl_regression_vs_current_accepted_consensus"] = not bool(
        current_comparison["windows_pnl_regressed_vs_current_accepted"]
    )
    if not all(gate4["gates"].values()):
        gate4["passed"] = False
        gate4["decision"] = "rejected_sec_credible_reaction_source_family_gate4_failed"
        gate4["rationale"] = (
            "The SEC credible-reaction source family failed the full Gate 4 source-expansion "
            "standard. New source-family additions must improve the core baseline across the "
            "standard windows and beat the current accepted independent-source consensus before "
            "retention or adapter promotion."
        )
        gate4["requires_parity_before_promotion"] = False
    return gate4


def _selected_sec_usage(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    selected_with_sec: list[dict[str, Any]] = []
    by_window: dict[str, int] = {}
    by_ticker: Counter[str] = Counter()
    for label, trades in target_trades_by_window.items():
        count = 0
        for trade in trades:
            source_names = set(str(name) for name in trade.get("source_names") or [])
            if SEC_SOURCE not in source_names:
                continue
            count += 1
            selected_with_sec.append(trade)
            by_ticker[str(trade.get("ticker") or "").upper()] += 1
        by_window[label] = count
    return {
        "selected_trade_count_with_sec_source": len(selected_with_sec),
        "selected_trade_pnl_usd_with_sec_source": round(
            sum(float(row.get("pnl") or 0.0) for row in selected_with_sec), 2
        ),
        "selected_trade_count_with_sec_source_by_window": by_window,
        "selected_trade_count_with_sec_source_by_ticker": dict(sorted(by_ticker.items())),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    prediction = {
        "success_probability": 0.27,
        "expected_ev_delta": 0.25,
        "expected_pnl_delta": 4500.0,
        "main_failure_modes": [
            "underperforms_current_accepted_consensus",
            "source_family_noise",
            "window_regression",
            "concentration_failed",
        ],
        "confidence_reason": (
            "SEC filing credibility and signal-day reaction are free and production-visible, but "
            "event-source history has been noisy and recent source-family expansions must beat the "
            "accepted comparator."
        ),
        "recorded_at": "2026-06-03T16:06:56+00:00",
    }
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "sec_credible_positive_reaction_source_family_added_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_source_family_scout",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 5,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_sec_filing_credibility_plus_ohlcv_reaction",
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": prediction,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": prediction["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "ev_prediction_error": round(
                comparison["expected_value_score_delta"] - prediction["expected_ev_delta"], 6
            ),
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                comparison["strategy_total_pnl_delta"] - prediction["expected_pnl_delta"], 2
            ),
            "realized_failure_mode": None
            if payload["gate4"]["passed"]
            else "sec_credible_reaction_source_family_gate4_failed",
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "sec_source_row_count": sum(
                int(row["source_row_count"]) for row in payload["sec_source_audit"]["windows"].values()
            ),
            "selected_trade_count_with_sec_source": payload["selected_sec_usage"][
                "selected_trade_count_with_sec_source"
            ],
            "selected_trade_pnl_usd_with_sec_source": payload["selected_sec_usage"][
                "selected_trade_pnl_usd_with_sec_source"
            ],
            "after_ev_delta_vs_current_accepted_consensus": payload[
                "current_accepted_consensus_comparison"
            ]["after_expected_value_delta_vs_current_accepted"],
            "after_pnl_delta_vs_current_accepted_consensus": payload[
                "current_accepted_consensus_comparison"
            ]["after_strategy_total_pnl_delta_vs_current_accepted"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
        "anti_js": "No JavaScript was used.",
    }


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = consensus.prior._load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "markdown_artifact": str(CARD_MD).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    consensus.prior._write_json(TICKET_JSON, ticket)


def main() -> None:
    _configure_consensus_module()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows, sec_source_audit = _source_rows_by_window_with_sec()
    _configure_consensus_module()
    baselines = consensus.prior._load_baselines()
    results, target_trades_by_window = consensus._run_windows(baselines, source_rows)
    aggregate = consensus.prior._aggregate_results(results)
    target_summary = consensus.prior._target_summary(target_trades_by_window)
    source_family_summary = consensus._source_family_summary(target_trades_by_window)
    selected_sec_usage = _selected_sec_usage(target_trades_by_window)
    gate4 = consensus.prior._gate4_decision(aggregate, results, target_summary)
    current_accepted_consensus_comparison = _current_accepted_consensus_comparison(aggregate, results)
    if not source_family_summary["all_selected_have_min_family_count"]:
        gate4["gates"]["source_family_min_count_passed"] = False
        gate4["passed"] = False
        gate4["decision"] = "rejected_sec_credible_reaction_source_family_invariant_failed"
        gate4["rationale"] = "At least one selected trade failed the source-family count invariant."
    else:
        gate4["gates"]["source_family_min_count_passed"] = True
    gate4 = _apply_current_accepted_guard(gate4, current_accepted_consensus_comparison)
    completed_at = _utc_now()
    added_source_family = SOURCE_FAMILIES[SEC_SOURCE]

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "source_files": {
            **{name: str(path).replace("\\", "/") for name, path in SOURCE_FILES.items()},
            SEC_SOURCE: str(SEC_EVENTS_FILE).replace("\\", "/"),
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
            "source_families": SOURCE_FAMILIES,
            "added_source_family": added_source_family,
            "added_source": SEC_SOURCE,
            "added_source_family_name": added_source_family,
            "min_signal_day_return_pct": MIN_SIGNAL_DAY_RETURN * 100.0,
            "min_signal_day_excess_vs_spy_pct": MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0,
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_family_admission_only": True,
        },
        "sec_source_audit": sec_source_audit,
        "aggregate": aggregate,
        "current_accepted_consensus_comparison": current_accepted_consensus_comparison,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "selected_sec_usage": selected_sec_usage,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    consensus.prior._write_json(OUT_JSON, payload)
    record = _experiment_log_record(payload)
    consensus.prior._write_json(LOG_JSON, record)
    consensus.prior._write_card(payload)
    _write_ticket(payload)
    consensus._upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "current_accepted_consensus_comparison": current_accepted_consensus_comparison,
                "source_family_summary": source_family_summary,
                "selected_sec_usage": selected_sec_usage,
                "sec_source_audit": sec_source_audit,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
