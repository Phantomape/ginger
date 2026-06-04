"""exp-20260603-017: SEC high/medium-credibility filing positive-reaction source-family scout.

Replay-only alpha search. This tests one variable: whether SEC high/medium-
credibility filings (10-K, 10-Q, 8-K item 2.02/2.05) with a positive signal-
day open-to-close return contribute an independent source family that improves
the accepted free-data consensus.

No shared adapter, production orders, watchlists, ranking, sizing, exits, LLM,
news, or default trade surfaces are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for _p in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import exp_20260426_041_opening_range_continuation_shadow as opening_shadow  # noqa: E402
import exp_20260525_022_volatility_contraction_qqq_confirmed_sleeve as qqq_source  # noqa: E402
import exp_20260526_007_vcp_rank_notional_profile as vcp_profile  # noqa: E402
import exp_20260603_014_accepted_consensus_independent_source_family as consensus  # noqa: E402


EXPERIMENT_ID = "exp-20260603-017"
STEM = "sec_credible_reaction_consensus_source_family"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_source_family"
CHANGED_VARIABLE = "sec_credible_positive_reaction_source_family_presence_added_to_independent_consensus_v1"
RULE_VERSION = "independent_source_family_with_sec_credible_reaction_v1"

ROOT = consensus.ROOT
OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_017_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")

SEC_SOURCE = "SEC_CREDIBLE_POSITIVE_REACTION_PAPER"
SEC_SOURCE_EXPERIMENT_ID = "exp-20260603-017"

# Comparison artifact: current accepted consensus baseline (exp-014 replay result)
CURRENT_ACCEPTED_CONSENSUS_ARTIFACT = Path(
    "data/experiments/exp-20260603-014/accepted_consensus_independent_source_family.json"
)

SOURCE_FILES = {
    **consensus.SOURCE_FILES,
    # SEC source is built inline from raw data; no pre-existing artifact path
}
SOURCE_EXPERIMENT_IDS = {
    **consensus.SOURCE_EXPERIMENT_IDS,
    SEC_SOURCE: SEC_SOURCE_EXPERIMENT_ID,
}
SOURCE_FAMILIES = {
    **consensus.SOURCE_FAMILIES,
    SEC_SOURCE: "sec_credible_reaction",
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
        "This experiment changes no production code. A retained result would need "
        "a shared default-off adapter that reconstructs the same SEC-credibility "
        "filter and independent source-family consensus in both replay and daily "
        "run paths before any candidate queue or order surface could change."
    ),
}

# Window definitions (from backtesting.md)
WINDOWS = {
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
}

# SEC filing data
SEC_EVENTS_BULK_PATH = Path("data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl")


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
    consensus.OUT_DIR = OUT_DIR
    consensus.OUT_JSON = OUT_JSON
    consensus.BEFORE_JSON = BEFORE_JSON
    consensus.AFTER_JSON = AFTER_JSON
    consensus.LOG_JSON = LOG_JSON
    consensus.TICKET_JSON = TICKET_JSON
    consensus.CARD_MD = CARD_MD
    consensus.EXPERIMENT_LOG = EXPERIMENT_LOG
    consensus.REGISTRY_JSON = REGISTRY_JSON
    consensus.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    consensus._configure_prior_module()
    consensus.prior._configure_base_module()
    consensus.prior.base.shadow = opening_shadow


def _is_high_medium_credibility(row: dict[str, Any]) -> bool:
    """Return True for 10-K, 10-Q (high) or 8-K items 2.02/2.05 (medium)."""
    ft = str(row.get("form_type") or "").upper().strip()
    if ft in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
        return True
    if ft in ("8-K", "8-K/A"):
        codes = row.get("eight_k_item_codes") or []
        code_str = ",".join(str(c) for c in codes)
        if "2.02" in code_str or "2.05" in code_str:
            return True
    return False


def _load_sec_filing_events() -> list[dict[str, Any]]:
    """Load all SEC filing events from the bulk archive."""
    path = REPO_ROOT / SEC_EVENTS_BULK_PATH
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _load_ohlcv_snapshot(snapshot_path: str | Path) -> dict[str, dict[str, Any]]:
    """Return {ticker: {date_str: row}} for signal-day lookups."""
    path = REPO_ROOT / snapshot_path
    with path.open("r", encoding="utf-8") as fh:
        snap = json.load(fh)
    ohlcv = snap.get("ohlcv") or snap.get("data") or {}
    by_ticker: dict[str, dict[str, Any]] = {}
    for ticker, rows in ohlcv.items():
        by_ticker[ticker.upper()] = {
            str(row.get("Date") or row.get("date") or ""): row
            for row in rows
            if isinstance(row, dict)
        }
    return by_ticker


def _signal_day_open_close_return(
    ticker: str,
    signal_date: str,
    ticker_date_map: dict[str, dict[str, Any]],
) -> float | None:
    """Compute open→close return for the signal day; None if data unavailable."""
    rows = ticker_date_map.get(ticker.upper())
    if not rows:
        return None
    row = rows.get(signal_date)
    if not row:
        return None
    try:
        open_px = float(row.get("Open") or row.get("open") or 0)
        close_px = float(row.get("Close") or row.get("close") or 0)
    except (TypeError, ValueError):
        return None
    if open_px <= 0:
        return None
    return (close_px - open_px) / open_px


def _build_sec_source_rows(
    events: list[dict[str, Any]],
    window_start: str,
    window_end: str,
    ticker_date_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build SEC credible positive-reaction source rows for one window."""
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for event in events:
        if not event.get("pit_safe_flag"):
            continue
        if not _is_high_medium_credibility(event):
            continue
        ticker = str(event.get("ticker") or "").upper()
        usable_date = str(event.get("usable_trade_date") or "")
        if not ticker or not usable_date:
            continue
        if usable_date < window_start or usable_date > window_end:
            continue
        key = (usable_date, ticker)
        if key in seen:
            continue
        ret = _signal_day_open_close_return(ticker, usable_date, ticker_date_map)
        if ret is None or ret <= 0:
            continue
        seen.add(key)
        ft = str(event.get("form_type") or "").upper().strip()
        if ft in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
            credibility = "high"
        else:
            credibility = "medium"
        codes = event.get("eight_k_item_codes") or []
        rows.append(
            {
                "source_name": SEC_SOURCE,
                "source_experiment_id": SEC_SOURCE_EXPERIMENT_ID,
                "date": usable_date,
                "signal_date": usable_date,
                "entry_date": usable_date,
                "ticker": ticker,
                "form_type": ft,
                "sec_source_credibility_bucket": credibility,
                "eight_k_item_codes": codes,
                "signal_day_open_close_return_pct": round(ret * 100, 4),
                "trade_enabled": False,
                "alters_orders": False,
                "known_at": f"{usable_date}T21:00:00Z",
            }
        )
    return sorted(rows, key=lambda r: (r["date"], r["ticker"]))


def _reconstruct_sec_rows() -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    """Build SEC credible reaction candidate rows per window."""
    events = _load_sec_filing_events()
    audit: dict[str, Any] = {
        "source": SEC_SOURCE,
        "source_experiment_id": SEC_SOURCE_EXPERIMENT_ID,
        "total_events_loaded": len(events),
        "rule": {
            "form_type_filter": ["10-K", "10-K/A", "10-Q", "10-Q/A", "8-K items 2.02/2.05"],
            "signal_day_return_filter": "> 0 (open-to-close)",
            "pit_safe_flag": True,
        },
        "windows": {},
    }
    rows_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in WINDOWS.items():
        ticker_date_map = _load_ohlcv_snapshot(cfg["snapshot"])
        rows = _build_sec_source_rows(
            events,
            window_start=cfg["start"],
            window_end=cfg["end"],
            ticker_date_map=ticker_date_map,
        )
        rows_by_window[label] = rows
        cred_counts: dict[str, int] = {}
        for r in rows:
            cred_counts[r["sec_source_credibility_bucket"]] = (
                cred_counts.get(r["sec_source_credibility_bucket"], 0) + 1
            )
        audit["windows"][label] = {
            "candidate_count": len(rows),
            "unique_tickers": len({r["ticker"] for r in rows}),
            "credibility_counts": cred_counts,
            "example_candidates": [
                {"date": r["date"], "ticker": r["ticker"], "form_type": r["form_type"],
                 "credibility": r["sec_source_credibility_bucket"],
                 "signal_day_return_pct": r["signal_day_open_close_return_pct"]}
                for r in rows[:5]
            ],
        }
    return rows_by_window, audit


def _source_rows_by_window_with_sec() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    """Combine existing consensus source rows with new SEC credible reaction rows."""
    combined = consensus.prior._source_rows_by_window()
    sec_rows_by_window, sec_audit = _reconstruct_sec_rows()
    for label, sec_rows in sec_rows_by_window.items():
        for row in sec_rows:
            signal_date = str(row.get("signal_date") or row.get("date") or "")
            ticker = str(row.get("ticker") or "").upper()
            if not signal_date or not ticker:
                continue
            combined[label][(signal_date, ticker)].append(row)
    return combined, sec_audit


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "A same-date ticker confirmed by SEC high/medium-credibility filings with positive "
            "signal-day open-to-close return and at least one other accepted free-data source "
            "family may have better replacement value than the current accepted independent-source "
            "consensus alone."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "Uses a broad, free, production-visible SEC filing classification. It avoids LLM "
            "soft-ranking, nearby FINRA/VBB/Fundamental-Growth retunes, state-surface threshold "
            "tuning, and forward-window retunes."
        ),
        "nearby_prior_experiments": [
            "exp-20260603-001",
            "exp-20260603-016",
            "exp-20260521-005",
            "exp-20260521-006",
            "exp-20260521-015",
        ],
        "prior_difference": (
            "exp-20260603-014 accepted independent source-family consensus without SEC credibility. "
            "exp-20260603-016 rejected VCP because it underperformed the current accepted consensus. "
            "This run adds one genuinely independent SEC filing credibility family using only "
            "public form-type and signal-day OHLCV reaction — not SEC text content, LLM scoring, "
            "or Companyfacts data."
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
            "The runner builds SEC candidates deterministically from public form-type and "
            "open-to-close return fields. Source-family mapping, SEC source-row audit, "
            "canonical before/after metrics, target trades, and Gate 4 diagnostics are persisted."
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
        source_row = source_results.get(label, {})
        candidate_after_ev = float(row["after"]["expected_value_score"])
        source_after_ev = float(source_row.get("after", {}).get("expected_value_score") or 0.0)
        candidate_after_pnl = float(row["after"]["total_pnl"])
        source_after_pnl = float(source_row.get("after", {}).get("total_pnl") or 0.0)
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
                "current_accepted_target_trade_count": source_row.get("target_trade_count"),
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
        "current_accepted_after_expected_value": source["aggregate"]["after"][
            "expected_value_score"
        ],
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
        gate4["decision"] = (
            "rejected_sec_credible_reaction_source_family_underperforms_current_accepted_consensus"
        )
        gate4["rationale"] = (
            "The SEC-credible-reaction-expanded consensus failed Gate 4. Either it underperformed "
            "the current accepted independent-source consensus on EV or PnL, or one or more "
            "windows regressed. Source-set expansions must beat the accepted comparator on all "
            "windows before retention or adapter promotion."
        )
        gate4["requires_parity_before_promotion"] = False
    return gate4


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    prediction = {
        "success_probability": 0.27,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "underperforms_current_accepted_consensus",
            "source_family_noise",
            "window_regression",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Default-off adapters and consensus are the top meta family, but recent source "
            "expansions failed unless the new source is independent and beats the accepted "
            "comparator; SEC credibility is production-visible but event-source history is noisy."
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
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_source_family_expansion",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 0,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_production_visible_field",
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
            "ev_prediction_error": None,
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": None,
            "realized_failure_mode": None
            if payload["gate4"]["passed"]
            else "sec_credible_reaction_source_family_gate4_failed",
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(
            payload["gate4"]["requires_parity_before_promotion"]
        ),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"][
                "expected_value_score"
            ],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"][
                "strategy_total_pnl"
            ],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"][
                "strategy_total_pnl"
            ],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "sec_candidate_count": sum(
                int(row["candidate_count"])
                for row in payload["sec_source_audit"]["windows"].values()
            ),
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
    gate4 = consensus.prior._gate4_decision(aggregate, results, target_summary)
    current_accepted_consensus_comparison = _current_accepted_consensus_comparison(
        aggregate, results
    )
    if not source_family_summary["all_selected_have_min_family_count"]:
        gate4["gates"]["source_family_min_count_passed"] = False
        gate4["passed"] = False
        gate4["decision"] = "rejected_sec_credible_reaction_source_family_invariant_failed"
        gate4["rationale"] = "At least one selected trade failed the source-family count invariant."
    else:
        gate4["gates"]["source_family_min_count_passed"] = True
    gate4 = _apply_current_accepted_guard(gate4, current_accepted_consensus_comparison)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "source_files": {
            name: str(path).replace("\\", "/") for name, path in SOURCE_FILES.items()
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
            "source_families": SOURCE_FAMILIES,
            "added_source_family": SOURCE_FAMILIES[SEC_SOURCE],
            "added_source": SEC_SOURCE,
            "sec_credibility_filter": ["high", "medium"],
            "signal_day_return_filter": "open_to_close > 0",
            "pit_safe_flag": True,
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
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    consensus.prior._write_json(OUT_JSON, payload)
    consensus.prior._write_json(BEFORE_JSON, aggregate["before"])
    consensus.prior._write_json(AFTER_JSON, aggregate["after"])
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
                "sec_source_audit": sec_source_audit,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
