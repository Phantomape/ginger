"""exp-20260613-017: SEC 13F new-holder initiation scout.

Replay-only alpha search. This tests one distinct PIT 13F field after the
aggregate sponsorship scout failed: true new institutional holders between two
fully ended 13F filing windows, confirmed by same-day liquid leadership.

No production/shared helper, live order, ranking, sizing, exit, LLM/news, or
watchlist behavior changes. A positive result is only a replay lead until a
shared daily default-off 13F helper exists. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import exp_20260613_014_sec13f_sponsorship_acceleration as base
from kova_data_sidecar import parse_sec13f_zip
from sec13f_universe_map import normalize_issuer_name


EXPERIMENT_ID = "exp-20260613-017"
STEM = "sec13f_new_holder_initiation"
TRIAL_FAMILY = "sec13f_new_holder_initiation_candidate_pool"
TRIAL_VARIANT_ID = "sec13f_new_holder_initiation_liquid_leadership_top1_10d_v1"
CHANGED_VARIABLE = "sec13f_new_holder_initiation_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

ROOT = base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_017_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

MIN_HOLDER_COUNT = 35
MIN_NEW_HOLDER_COUNT = 8
MIN_NEW_HOLDER_SHARE = 0.06
MIN_NEW_HOLDER_VALUE_USD = 1_000_000.0
MIN_NEW_HOLDER_VALUE_SHARE = 0.015
MAX_TOTAL_VALUE_DECLINE_PCT = -0.30

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "stale_quarterly_data",
        "window_regression",
        "not_incremental",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260613-014 rejected aggregate 13F holder/value growth, but its "
        "reflection called for true new-position signals. This tests a "
        "materially different PIT 13F field while acknowledging quarterly "
        "staleness and accepted allocator comparators."
    ),
    "recorded_at": "2026-06-13T13:03:22+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_live_adapter",
    "implementation_mode": "private_replay_scout",
    "private_replay_scout_escape_reason": (
        "The raw 13F manager-set aggregation is implemented only in this "
        "experiment. A positive result is lead-only until a shared helper "
        "computes the same new-holder field in historical replay and daily "
        "default-off snapshots."
    ),
    "parity_note": (
        "This experiment changes no production code. A positive result remains "
        "a replay lead until a shared default-off helper computes the same PIT "
        "13F window pair, new-holder manager sets, leadership gates, overlap "
        "exclusion, entry, exit, costs, cooldown, and ledger fields identically "
        "in historical replay and daily production snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: true new SEC 13F holders between two fully ended "
        "filing windows, confirmed by liquid same-day leadership, may add "
        "durable next-open paper alpha distinct from stale aggregate "
        "sponsorship growth."
    ),
    "2_history_check": {
        "exp-20260613-014": (
            "Aggregate 13F holder/value sponsorship acceleration was rejected "
            "because old_thin regressed and drawdown drift was too high."
        ),
        "exp-20260612-015": (
            "13D activist stake initiation was rejected with aggregate EV/PnL "
            "down and all windows regressing."
        ),
        "exp-20260612-016": (
            "13G passive-stake initiation was rejected, likely because annual "
            "batch events were stale and too sparse."
        ),
        "difference": (
            "This run tests true new 13F manager holders and their value share, "
            "not aggregate holder/value growth or 13D/13G filing-date events."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Pass only if "
        "aggregate EV/PnL improve, no window EV/PnL regression occurs, at "
        "least 20 paper trades span all 3 windows, survival >=5%, drawdown "
        "drift <=0.5pp, and concentration passes. A positive result is still "
        "lead-only until shared daily parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_017_sec13f_new_holder_initiation.py"
    ),
}

_original_load_13f_history = base._load_13f_history
_original_candidate_for_ticker = base._candidate_for_ticker
_original_candidate_sort_key = base._candidate_sort_key
_original_build_payload = base._build_payload
_original_build_card = base._build_card
_original_build_log_record = base._build_log_record


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _aggregate_manager_holdings(
    holding_rows: Iterable[dict[str, Any]],
    *,
    name_index: dict[str, str],
    universe: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    allowed = {str(ticker).upper() for ticker in universe}
    agg: dict[str, dict[str, Any]] = {}
    manager_values: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    cusip_map: dict[str, str] = {}
    cusip_conflicts: set[str] = set()
    for row in holding_rows:
        ticker = name_index.get(normalize_issuer_name(row.get("name_of_issuer")))
        if not ticker or ticker not in allowed:
            continue
        cusip = str(row.get("cusip") or "").upper().replace(" ", "")
        if cusip and cusip not in cusip_conflicts:
            existing = cusip_map.get(cusip)
            if existing and existing != ticker:
                cusip_conflicts.add(cusip)
                cusip_map.pop(cusip, None)
            else:
                cusip_map.setdefault(cusip, ticker)

        entry = agg.get(ticker)
        if entry is None:
            entry = {
                "ticker": ticker,
                "holder_count": 0,
                "position_row_count": 0,
                "total_value_usd": 0.0,
                "total_shares": 0.0,
                "report_period": row.get("report_period"),
            }
            agg[ticker] = entry
        entry["position_row_count"] += 1
        value = row.get("value_usd_thousands")
        shares = row.get("shares")
        value_num = float(value) if isinstance(value, (int, float)) else 0.0
        if value_num:
            entry["total_value_usd"] += value_num
        if isinstance(shares, (int, float)):
            entry["total_shares"] += float(shares)
        manager = str(row.get("manager_cik") or row.get("manager_name") or "").strip()
        if manager:
            manager_values[ticker][manager] += value_num

    for ticker, entry in agg.items():
        values = {
            manager: round(value, 2)
            for manager, value in manager_values.get(ticker, {}).items()
            if manager
        }
        entry["manager_values_usd"] = values
        entry["holder_count"] = len(values)
        entry["total_value_usd"] = round(entry["total_value_usd"], 2)
        entry["total_shares"] = round(entry["total_shares"], 2)
    return agg, cusip_map


def _load_13f_history(universe: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    name_index = base.load_company_name_index()
    by_label: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix=f"{EXPERIMENT_ID}_13f_") as tmp_name:
        tmp_root = Path(tmp_name)
        for year, month in base.SEC13F_WINDOW_STARTS:
            label = base.window_label(year, month)
            start, end = base._window_bounds(year, month)
            url = base.window_url(year, month)
            zip_path = tmp_root / f"{label}_form13f.zip"
            try:
                base._download_to_temp(url, zip_path)
                rows = list(
                    parse_sec13f_zip(
                        zip_path,
                        asof_date=end.isoformat(),
                        cusip_ticker_map=None,
                    )
                )
                holdings, cusip_map = _aggregate_manager_holdings(
                    rows,
                    name_index=name_index,
                    universe=universe,
                )
            except Exception as exc:  # pragma: no cover - network/data boundary
                errors.append(
                    {
                        "window_label": label,
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                        "url": url,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue
            payload = {
                "window_label": label,
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
                "known_after": end.isoformat(),
                "window_url": url,
                "raw_position_row_count": len(rows),
                "universe_covered_count": len(holdings),
                "universe_coverage_pct": round(100.0 * len(holdings) / max(len(universe), 1), 2),
                "cusip_map_size": len(cusip_map),
                "holdings_by_ticker": holdings,
            }
            by_label[label] = payload
            source_summaries.append(
                {key: value for key, value in payload.items() if key != "holdings_by_ticker"}
            )
            print(
                f"[{EXPERIMENT_ID}] loaded 13F {label}: "
                f"{len(holdings)} tickers from {len(rows)} rows"
            )
    return by_label, {
        "rule_version": base.SEC13F_RULE_VERSION,
        "manager_set_rule_version": RULE_VERSION,
        "universe_size": len(universe),
        "window_count_requested": len(base.SEC13F_WINDOW_STARTS),
        "window_count_loaded": len(by_label),
        "windows_loaded": source_summaries,
        "download_errors": errors,
        "source_storage": "SEC zip files downloaded to a temp directory only; not committed",
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    latest_13f: dict[str, Any],
    prior_13f: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in base.framework.EXCLUDED_TICKERS:
        return None
    latest_holdings = latest_13f["holdings_by_ticker"].get(ticker)
    prior_holdings = prior_13f["holdings_by_ticker"].get(ticker)
    if not latest_holdings or not prior_holdings:
        return None

    latest_managers = dict(latest_holdings.get("manager_values_usd") or {})
    prior_managers = dict(prior_holdings.get("manager_values_usd") or {})
    if not latest_managers or not prior_managers:
        return None
    new_managers = set(latest_managers) - set(prior_managers)

    holder_count = int(latest_holdings.get("holder_count") or 0)
    prior_holder_count = int(prior_holdings.get("holder_count") or 0)
    new_holder_count = len(new_managers)
    new_holder_share = new_holder_count / max(holder_count, 1)
    value_usd = base._float(latest_holdings.get("total_value_usd")) or 0.0
    prior_value_usd = base._float(prior_holdings.get("total_value_usd")) or 0.0
    value_delta = value_usd - prior_value_usd
    value_growth_pct = value_delta / max(prior_value_usd, 1.0)
    new_holder_value_usd = sum(float(latest_managers.get(manager) or 0.0) for manager in new_managers)
    new_holder_value_share = new_holder_value_usd / max(value_usd, 1.0)

    if holder_count < MIN_HOLDER_COUNT:
        return None
    if new_holder_count < MIN_NEW_HOLDER_COUNT:
        return None
    if new_holder_share < MIN_NEW_HOLDER_SHARE:
        return None
    if new_holder_value_usd < MIN_NEW_HOLDER_VALUE_USD:
        return None
    if new_holder_value_share < MIN_NEW_HOLDER_VALUE_SHARE:
        return None
    if value_growth_pct < MAX_TOTAL_VALUE_DECLINE_PCT:
        return None

    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < base.MIN_HISTORY_SESSIONS or spy_idx < base.MIN_HISTORY_SESSIONS:
        return None
    close = base.framework._value(rows[idx], "Close")
    if close is None or close < base.MIN_PRICE:
        return None
    adv20 = base.framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < base.MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = base.framework._daily_return(rows, idx)
    close_location = base.framework._close_location(rows[idx])
    volume_ratio = base.framework._volume_ratio(rows, idx)
    ret5 = base.framework._ret(rows, idx, 5)
    ret20 = base.framework._ret(rows, idx, 20)
    ret60 = base.framework._ret(rows, idx, 60)
    spy_ret20 = base.framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = base.framework._ret(spy_rows, spy_idx, 60)
    realized_vol = base.framework._realized_vol(rows, idx)
    required = [
        signal_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol,
    ]
    if any(value is None for value in required):
        return None
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    if float(signal_return) < base.MIN_SIGNAL_RETURN:
        return None
    if ret20_excess_spy < base.MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < base.MIN_RET60_EXCESS_SPY:
        return None
    if float(close_location) < base.MIN_CLOSE_LOCATION:
        return None
    if float(volume_ratio) < base.MIN_VOLUME_RATIO_20D:
        return None
    if float(volume_ratio) > base.MAX_VOLUME_RATIO_20D:
        return None
    if float(ret5) > base.MAX_RET5:
        return None
    if float(realized_vol) > base.MAX_REALIZED_VOL_20D:
        return None

    score = (
        1.80 * new_holder_share
        + 0.95 * min(new_holder_value_share, 0.50)
        + 0.015 * min(float(new_holder_count), 50.0)
        + 1.20 * ret20_excess_spy
        + 0.50 * ret60_excess_spy
        + 0.40 * float(close_location)
        + 0.10 * min(float(volume_ratio), 1.8)
        + 0.04 * math.log10(max(float(adv20), 1.0) / 1_000_000.0)
        - 0.50 * max(float(ret5), 0.0)
        - 0.40 * float(realized_vol)
    )
    sector_meta = sector_entries.get(ticker, {})
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "SEC13F_NEW_HOLDER_INITIATION_LIQUID_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": base._round(signal_return),
        "candidate_ret5": base._round(ret5),
        "candidate_ret20": base._round(ret20),
        "candidate_ret60": base._round(ret60),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": base._round(close_location),
        "candidate_avg_dollar_volume_20d": round(float(adv20), 2),
        "candidate_volume_ratio_20d": base._round(volume_ratio),
        "candidate_realized_vol_20d": base._round(realized_vol),
        "sec13f_latest_window": latest_13f["window_label"],
        "sec13f_latest_window_end": latest_13f["window_end"],
        "sec13f_prior_window": prior_13f["window_label"],
        "sec13f_prior_window_end": prior_13f["window_end"],
        "sec13f_holder_count": holder_count,
        "sec13f_prior_holder_count": prior_holder_count,
        "sec13f_holder_delta": new_holder_count,
        "sec13f_holder_growth_pct": round(new_holder_share, 6),
        "sec13f_total_value_usd": round(value_usd, 2),
        "sec13f_prior_total_value_usd": round(prior_value_usd, 2),
        "sec13f_value_delta_usd": round(value_delta, 2),
        "sec13f_value_growth_pct": round(new_holder_value_share, 6),
        "sec13f_total_value_growth_pct": round(value_growth_pct, 6),
        "sec13f_new_holder_count": new_holder_count,
        "sec13f_new_holder_share": round(new_holder_share, 6),
        "sec13f_new_holder_value_usd": round(new_holder_value_usd, 2),
        "sec13f_new_holder_value_share": round(new_holder_value_share, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("sec13f_new_holder_count") or 0.0),
        -float(row.get("sec13f_new_holder_value_share") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
    )


def _build_payload() -> dict[str, Any]:
    payload = _original_build_payload()
    passed = bool(payload.get("gate4", {}).get("passed"))
    decision = (
        "positive_replay_lead_not_promoted_sec13f_new_holder_initiation"
        if passed
        else "rejected_sec13f_new_holder_initiation_candidate_pool"
    )
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    aggregate = payload["delta_metrics"]["aggregate"]
    why = (
        "The true new-holder 13F field cleared the replay gate, but remains "
        "lead-only because shared daily helper parity and forward replacement "
        "rows are absent."
        if passed
        else (
            "The true new-holder 13F field failed Gate 4. New institutional "
            "manager initiations are still quarterly/stale, overlap liquid "
            "leadership already captured by accepted sources, or do not reduce "
            "old-window drawdown enough after next-open costs."
        )
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": decision,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_13f_candidate_pool",
            "nearby_prior_experiments": [
                "exp-20260613-014",
                "exp-20260612-015",
                "exp-20260612-016",
            ],
            "prior_trial_count": 3,
            "new_evidence_type": "pit_sec_13f_true_new_holder_initiation",
            "gate_questions": PRE_RUN_QUESTIONS,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": (
                "The true new-holder 13F candidate source cleared numeric "
                "replay gates, but remains lead-only because no shared daily "
                "helper or production 13F manager-set snapshot was promoted."
                if passed
                else (
                    "The true new-holder 13F candidate source was rejected "
                    "under the standard three-window protocol."
                )
            ),
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_reasons"]),
            "next_evidence_needed": (
                "A retry needs manager-quality segmentation, sector-relative "
                "new-holder surprise, options/borrow confirmation, or closed "
                "forward replacement rows from a shared 13F helper. Do not "
                "sweep new-holder count/share/value thresholds on the same "
                "frozen windows."
            ),
            "post_run_reflection": {
                "why_result_happened": why,
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping new-holder count, new-holder "
                    "share, new-holder value share, ADV, close-location, "
                    "ret20/ret60, top-N, hold-day, cooldown, or notional "
                    "thresholds on the same frozen windows."
                ),
                "new_evidence_required": (
                    "Need manager identity/quality, sector-normalized "
                    "new-holder surprise, independent options/borrow evidence, "
                    "or forward replacement-value rows from a shared helper."
                ),
            },
        }
    )
    payload["gate4"]["decision"] = decision
    payload["prediction"] = {
        **PREDICTION,
        "actual_success": 1 if passed else 0,
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "brier_score": payload["calibration"]["brier_score"],
    }
    payload["calibration"]["predicted_success_probability"] = PREDICTION[
        "success_probability"
    ]
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus "
        "experiment-local PIT SEC 13F true new-holder initiation paper overlay"
    )
    payload["backtest_protocol"]["sec13f_provenance"] = (
        "SEC structured Form 13F filing-window zip files. A signal day uses "
        "only the latest window whose end date is <= signal date and compares "
        "the set of filing-manager ids with the prior fully ended window."
    )
    payload["parameters"].update(
        {
            "min_holder_count": MIN_HOLDER_COUNT,
            "min_new_holder_count": MIN_NEW_HOLDER_COUNT,
            "min_new_holder_share": MIN_NEW_HOLDER_SHARE,
            "min_new_holder_value_usd": MIN_NEW_HOLDER_VALUE_USD,
            "min_new_holder_value_share": MIN_NEW_HOLDER_VALUE_SHARE,
            "max_total_value_decline_pct": MAX_TOTAL_VALUE_DECLINE_PCT,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(base.EXPERIMENT_LOG),
        _repo_rel(base.REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    text = _original_build_card(payload)
    return text.replace(
        f"# {EXPERIMENT_ID} SEC 13F Sponsorship Acceleration",
        f"# {EXPERIMENT_ID} SEC 13F New-Holder Initiation",
    ).replace(
        "## 13F History",
        "## 13F New-Holder History",
    )


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _original_build_log_record(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "change_type": "experiment_local_replay_candidate_pool",
            "implementation_mode": "private_replay_scout",
            "causal_components": [
                "SEC 13F manager-set window pairs",
                "true new-holder count/share/value field",
                "liquid leadership gates",
                "same-ticker core overlap exclusion",
                "next-open paper entry",
                "10d exit",
                "costs",
                "three-window Gate 1-4",
            ],
            "new_evidence_type": payload["new_evidence_type"],
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "negative_reflection": None
            if payload["gate4"]["passed"]
            else payload["post_run_reflection"]["why_result_happened"],
        }
    )
    return record


def _configure_base() -> None:
    base.__file__ = __file__
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
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.MIN_HOLDER_COUNT = MIN_HOLDER_COUNT
    base.MIN_HOLDER_DELTA = MIN_NEW_HOLDER_COUNT
    base.MIN_HOLDER_GROWTH_PCT = MIN_NEW_HOLDER_SHARE
    base.MIN_VALUE_GROWTH_PCT = MAX_TOTAL_VALUE_DECLINE_PCT
    base._load_13f_history = _load_13f_history
    base._candidate_for_ticker = _candidate_for_ticker
    base._candidate_sort_key = _candidate_sort_key
    base._build_payload = _build_payload
    base._build_card = _build_card
    base._build_log_record = _build_log_record


def main() -> None:
    _configure_base()
    base.main()


if __name__ == "__main__":
    main()
