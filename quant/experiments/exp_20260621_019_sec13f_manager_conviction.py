"""exp-20260621-019: SEC 13F new-manager conviction scout.

Replay-only alpha search. This tests a materially different 13F field after
aggregate sponsorship, true new-holder count, and low-crowding 13F variants
failed: a new manager must hold the ticker as a meaningful weight inside that
manager's own reported 13F portfolio.

No production/shared helper, live order, ranking, sizing, exit, LLM/news, or
watchlist behavior changes. A positive result is only a replay lead until a
shared daily default-off 13F helper exists. No JavaScript is used.
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260613_014_sec13f_sponsorship_acceleration as base
from sec13f_universe_map import normalize_issuer_name


EXPERIMENT_ID = "exp-20260621-019"
STEM = "sec13f_manager_conviction"
TRIAL_FAMILY = "sec13f_manager_conviction_candidate_pool"
TRIAL_VARIANT_ID = "sec13f_new_manager_conviction_liquid_leadership_top1_10d_v1"
CHANGED_VARIABLE = "sec13f_new_manager_conviction_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

ROOT = base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_019_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
SOURCE_CACHE_DIR = ROOT / "data" / "non_ohlcv" / "sec13f_institutional" / "source_cache"
SEC13F_AGG_DIR = ROOT / "data" / "non_ohlcv" / "sec13f_institutional"
DERIVED_CACHE_DIR = OUT_DIR / "derived_sec13f"

MIN_HOLDER_COUNT = 35
MIN_CONVICTION_MANAGER_COUNT = 1
MIN_MANAGER_POSITION_WEIGHT = 0.004
MIN_MANAGER_POSITION_VALUE_USD = 1_000_000.0
MIN_CONVICTION_VALUE_USD = 2_000_000.0
MIN_CONVICTION_VALUE_SHARE = 0.004
MAX_TOTAL_VALUE_DECLINE_PCT = -0.35

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "stale_quarterly_data",
        "window_regression",
        "drawdown_drift",
        "not_incremental",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Prior 13F aggregate holder/value and low-crowding entries failed, "
        "but their reflections explicitly require manager-quality "
        "segmentation. Local SEC 13F source-cache zips now allow a distinct "
        "PIT field: new managers whose position is meaningful within their "
        "own reported portfolio, reducing stale aggregate ownership noise. "
        "Main risk is quarterly delay and overlap with accepted liquid "
        "leadership sources."
    ),
    "recorded_at": "2026-06-21T19:07:08+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_live_adapter",
    "implementation_mode": "private_replay_scout",
    "private_replay_scout_escape_reason": (
        "The manager-level portfolio-weight aggregation is implemented only "
        "in this experiment. A positive result is lead-only until a shared "
        "helper computes the same field in historical replay and daily "
        "default-off snapshots."
    ),
    "live_realism_evaluated": False,
    "parity_note": (
        "This experiment changes no production code. A positive result remains "
        "a replay lead until a shared default-off helper computes the same PIT "
        "13F window pair, manager-level position weights, leadership gates, "
        "overlap exclusion, entry, exit, costs, cooldown, and ledger fields "
        "identically in historical replay and daily production snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 13F new-manager portfolio-weight conviction, "
        "confirmed by liquid leadership, may identify institutional "
        "accumulation with more information content than aggregate "
        "holder-count or low-crowding 13F fields."
    ),
    "2_history_check": {
        "exp-20260613-014": (
            "Rejected aggregate 13F holder/value sponsorship acceleration: "
            "old_thin regressed and drawdown drift was too high."
        ),
        "exp-20260613-017": (
            "Rejected true new-holder initiation: aggregate EV/PnL were "
            "negative with late/old regressions."
        ),
        "exp-20260615-009": (
            "Rejected low-crowding context filter on the 13F leadership "
            "artifact: aggregate EV/PnL slightly negative and old_thin still "
            "weak."
        ),
        "difference": (
            "This run uses manager-level portfolio weight / conviction from "
            "the raw local SEC 13F source cache. It is not a holder-count, "
            "total-value-growth, low-crowding quantile, or 13D/13G filing "
            "event retry."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Pass only if "
        "aggregate EV/PnL improve, no window EV/PnL regression occurs, at "
        "least 20 paper trades span all 3 windows, survival >=5%, drawdown "
        "drift <=0.5pp, concentration passes, and the accepted allocator "
        "comparator is respected. A positive result is still lead-only until "
        "shared daily parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260621_019_sec13f_manager_conviction.py"
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


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_sec_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return date.fromisoformat(text[:10])
    for fmt in ("%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(text.upper(), fmt).date()
        except ValueError:
            continue
    return None


def _zip_entry_by_suffix(archive: zipfile.ZipFile, suffixes: tuple[str, ...]) -> str:
    suffixes_u = tuple(suffix.upper() for suffix in suffixes)
    for name in archive.namelist():
        name_u = name.upper()
        if any(name_u.endswith(suffix) for suffix in suffixes_u):
            return name
    raise ValueError(f"SEC 13F zip missing {suffixes[0]}")


def _dict_reader(archive: zipfile.ZipFile, entry_name: str) -> csv.DictReader:
    raw = archive.open(entry_name)
    text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
    delimiter = "\t" if entry_name.upper().endswith(".TSV") else ","
    return csv.DictReader(text, delimiter=delimiter)


def _known_after_for_label(label: str, fallback: date) -> date:
    snapshot_path = SEC13F_AGG_DIR / f"holdings_{label}.json"
    if not snapshot_path.exists():
        return fallback
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return date.fromisoformat(str(payload.get("as_of") or fallback.isoformat())[:10])


def _load_cached_scan(cache_path: Path, zip_path: Path) -> dict[str, Any] | None:
    if not cache_path.exists():
        return None
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    stat = zip_path.stat()
    if payload.get("zip_size") != stat.st_size:
        return None
    if payload.get("zip_mtime_ns") != stat.st_mtime_ns:
        return None
    return payload


def _submission_index(zip_path: Path, *, known_after: date) -> tuple[dict[str, dict[str, Any]], int]:
    with zipfile.ZipFile(zip_path) as archive:
        sub_name = _zip_entry_by_suffix(archive, ("SUBMISSION.TSV", "SUBMISSION.CSV"))
        submissions: dict[str, dict[str, Any]] = {}
        raw_count = 0
        reader = _dict_reader(archive, sub_name)
        for row in reader:
            raw_count += 1
            accession = str(row.get("ACCESSION_NUMBER") or "").strip()
            if not accession:
                continue
            filing_date = _parse_sec_date(row.get("FILING_DATE"))
            if filing_date and filing_date > known_after:
                continue
            cik = str(row.get("CIK") or "").strip()
            submissions[accession] = {
                "manager": cik or accession,
                "filing_date": filing_date.isoformat() if filing_date else None,
                "report_period": row.get("PERIODOFREPORT"),
            }
    return submissions, raw_count


def _scan_13f_window(
    *,
    label: str,
    start: date,
    end: date,
    zip_path: Path,
    known_after: date,
    name_index: dict[str, str],
    universe: set[str],
) -> dict[str, Any]:
    DERIVED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stat = zip_path.stat()
    cache_path = DERIVED_CACHE_DIR / f"{label}_{RULE_VERSION}.json"
    cached = _load_cached_scan(cache_path, zip_path)
    if cached:
        return cached

    allowed = {str(ticker).upper() for ticker in universe}
    submissions, raw_submission_count = _submission_index(zip_path, known_after=known_after)
    manager_totals: dict[str, float] = defaultdict(float)
    manager_values: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    agg: dict[str, dict[str, Any]] = {}
    cusip_map: dict[str, str] = {}
    cusip_conflicts: set[str] = set()
    raw_position_row_count = 0
    universe_position_row_count = 0

    with zipfile.ZipFile(zip_path) as archive:
        info_name = _zip_entry_by_suffix(archive, ("INFOTABLE.TSV", "INFOTABLE.CSV"))
        reader = _dict_reader(archive, info_name)
        for row in reader:
            accession = str(row.get("ACCESSION_NUMBER") or "").strip()
            submission = submissions.get(accession)
            if not submission:
                continue
            raw_position_row_count += 1
            manager = str(submission.get("manager") or "").strip()
            value_num = _float_or_zero(row.get("VALUE"))
            if manager:
                manager_totals[manager] += value_num
            ticker = name_index.get(normalize_issuer_name(row.get("NAMEOFISSUER")))
            if not ticker or ticker not in allowed:
                continue
            universe_position_row_count += 1
            cusip = str(row.get("CUSIP") or "").upper().replace(" ", "")
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
                    "report_period": submission.get("report_period"),
                }
                agg[ticker] = entry
            entry["position_row_count"] += 1
            entry["total_value_usd"] += value_num
            entry["total_shares"] += _float_or_zero(row.get("SSHPRNAMT"))
            if manager:
                manager_values[ticker][manager] += value_num

    for ticker, entry in agg.items():
        values = {
            manager: round(value, 2)
            for manager, value in manager_values.get(ticker, {}).items()
            if manager
        }
        weights = {
            manager: round(value / manager_totals[manager], 8)
            for manager, value in values.items()
            if manager_totals.get(manager, 0.0) > 0.0
        }
        conviction = {
            manager: value
            for manager, value in values.items()
            if weights.get(manager, 0.0) >= MIN_MANAGER_POSITION_WEIGHT
            and value >= MIN_MANAGER_POSITION_VALUE_USD
        }
        entry["manager_values_usd"] = values
        entry["manager_position_weights"] = weights
        entry["conviction_manager_values_usd"] = conviction
        entry["holder_count"] = len(values)
        entry["conviction_holder_count"] = len(conviction)
        entry["total_value_usd"] = round(entry["total_value_usd"], 2)
        entry["total_shares"] = round(entry["total_shares"], 2)

    payload = {
        "window_label": label,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "known_after": known_after.isoformat(),
        "zip_path": _repo_rel(zip_path),
        "zip_size": stat.st_size,
        "zip_mtime_ns": stat.st_mtime_ns,
        "raw_submission_count": raw_submission_count,
        "raw_position_row_count": raw_position_row_count,
        "universe_position_row_count": universe_position_row_count,
        "universe_covered_count": len(agg),
        "universe_coverage_pct": round(100.0 * len(agg) / max(len(universe), 1), 2),
        "cusip_map_size": len(cusip_map),
        "manager_count": len(manager_totals),
        "holdings_by_ticker": agg,
    }
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _load_13f_history(universe: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    name_index = base.load_company_name_index()
    by_label: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    for year, month in base.SEC13F_WINDOW_STARTS:
        label = base.window_label(year, month)
        start, end = base._window_bounds(year, month)
        zip_path = SOURCE_CACHE_DIR / f"{label}_form13f.zip"
        known_after = _known_after_for_label(label, end)
        try:
            payload = _scan_13f_window(
                label=label,
                start=start,
                end=end,
                zip_path=zip_path,
                known_after=known_after,
                name_index=name_index,
                universe=universe,
            )
        except Exception as exc:  # pragma: no cover - local data boundary
            errors.append(
                {
                    "window_label": label,
                    "window_start": start.isoformat(),
                    "window_end": end.isoformat(),
                    "known_after": known_after.isoformat(),
                    "zip_path": _repo_rel(zip_path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        by_label[label] = payload
        source_summaries.append(
            {key: value for key, value in payload.items() if key != "holdings_by_ticker"}
        )
        print(
            f"[{EXPERIMENT_ID}] loaded local 13F {label}: "
            f"{payload['universe_covered_count']} tickers from "
            f"{payload['raw_position_row_count']} rows"
        )
    return by_label, {
        "rule_version": base.SEC13F_RULE_VERSION,
        "manager_conviction_rule_version": RULE_VERSION,
        "universe_size": len(universe),
        "window_count_requested": len(base.SEC13F_WINDOW_STARTS),
        "window_count_loaded": len(by_label),
        "windows_loaded": source_summaries,
        "load_errors": errors,
        "source_storage": _repo_rel(SOURCE_CACHE_DIR),
        "new_evidence_axis": (
            "manager-level portfolio weight / conviction segmentation from "
            "historical PIT SEC 13F source-cache zips"
        ),
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
    latest = latest_13f["holdings_by_ticker"].get(ticker)
    prior = prior_13f["holdings_by_ticker"].get(ticker)
    if not latest or not prior:
        return None

    latest_values = dict(latest.get("manager_values_usd") or {})
    prior_values = dict(prior.get("manager_values_usd") or {})
    latest_weights = dict(latest.get("manager_position_weights") or {})
    latest_conviction = dict(latest.get("conviction_manager_values_usd") or {})
    if not latest_values or not prior_values or not latest_conviction:
        return None
    new_managers = set(latest_values) - set(prior_values)
    conviction_new = {
        manager: float(latest_conviction[manager])
        for manager in new_managers
        if manager in latest_conviction
    }
    conviction_manager_count = len(conviction_new)
    conviction_value_usd = sum(conviction_new.values())
    total_value_usd = base._float(latest.get("total_value_usd")) or 0.0
    prior_total_value_usd = base._float(prior.get("total_value_usd")) or 0.0
    value_growth_pct = (total_value_usd - prior_total_value_usd) / max(prior_total_value_usd, 1.0)
    holder_count = int(latest.get("holder_count") or 0)
    prior_holder_count = int(prior.get("holder_count") or 0)
    holder_delta = holder_count - prior_holder_count
    holder_growth_pct = holder_delta / max(prior_holder_count, 1)
    conviction_value_share = conviction_value_usd / max(total_value_usd, 1.0)
    conviction_weight_sum = sum(float(latest_weights.get(manager) or 0.0) for manager in conviction_new)
    conviction_weight_max = max(
        [float(latest_weights.get(manager) or 0.0) for manager in conviction_new] or [0.0]
    )

    if holder_count < MIN_HOLDER_COUNT:
        return None
    if conviction_manager_count < MIN_CONVICTION_MANAGER_COUNT:
        return None
    if conviction_value_usd < MIN_CONVICTION_VALUE_USD:
        return None
    if conviction_value_share < MIN_CONVICTION_VALUE_SHARE:
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
        1.65 * min(conviction_weight_sum, 0.12)
        + 1.20 * min(conviction_weight_max, 0.05)
        + 0.05 * min(float(conviction_manager_count), 20.0)
        + 0.30 * math.log1p(max(conviction_value_usd, 0.0) / 1_000_000.0)
        + 1.10 * ret20_excess_spy
        + 0.45 * ret60_excess_spy
        + 0.35 * float(close_location)
        + 0.08 * min(float(volume_ratio), 1.8)
        - 0.50 * max(float(ret5), 0.0)
        - 0.40 * float(realized_vol)
    )
    sector_meta = sector_entries.get(ticker, {})
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "SEC13F_NEW_MANAGER_CONVICTION_LIQUID_LEADERSHIP_PAPER",
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
        "sec13f_holder_delta": holder_delta,
        "sec13f_holder_growth_pct": round(holder_growth_pct, 6),
        "sec13f_total_value_usd": round(total_value_usd, 2),
        "sec13f_prior_total_value_usd": round(prior_total_value_usd, 2),
        "sec13f_total_value_growth_pct": round(value_growth_pct, 6),
        "sec13f_value_growth_pct": round(value_growth_pct, 6),
        "sec13f_new_conviction_manager_count": conviction_manager_count,
        "sec13f_new_conviction_value_usd": round(conviction_value_usd, 2),
        "sec13f_new_conviction_value_share": round(conviction_value_share, 6),
        "sec13f_new_conviction_weight_sum": round(conviction_weight_sum, 6),
        "sec13f_new_conviction_weight_max": round(conviction_weight_max, 6),
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
        -float(row.get("sec13f_new_conviction_weight_sum") or 0.0),
        -float(row.get("sec13f_new_conviction_value_usd") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
    )


def _build_payload() -> dict[str, Any]:
    payload = _original_build_payload()
    passed = bool(payload.get("gate4", {}).get("passed"))
    decision = (
        "positive_replay_lead_not_promoted_sec13f_manager_conviction"
        if passed
        else "rejected_sec13f_manager_conviction_candidate_pool"
    )
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    aggregate = payload["delta_metrics"]["aggregate"]
    why = (
        "The 13F manager-conviction field cleared the replay gate, but remains "
        "lead-only because shared daily helper parity and forward replacement "
        "rows are absent."
        if passed
        else (
            "The manager-conviction field failed Gate 4. Requiring new "
            "manager portfolio weight improved the economic specificity of "
            "the 13F signal, but quarterly delayed ownership still overlaps "
            "liquid leadership and did not create stable all-window "
            "replacement value after next-open costs."
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
                "exp-20260613-017",
                "exp-20260615-009",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "pit_sec_13f_manager_portfolio_weight_conviction",
            "gate_questions": PRE_RUN_QUESTIONS,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": (
                "The SEC 13F manager-conviction candidate source cleared "
                "numeric replay gates, but remains lead-only because no "
                "shared daily helper or production 13F manager-weight snapshot "
                "was promoted."
                if passed
                else (
                    "The SEC 13F manager-conviction candidate source was "
                    "rejected under the standard three-window protocol."
                )
            ),
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_reasons"]),
            "next_evidence_needed": (
                "A retry needs materially richer manager identity/quality, "
                "sector-normalized ownership surprise, independent borrow/"
                "options evidence, or closed forward replacement rows from a "
                "shared 13F helper. Do not sweep manager-weight, value, ADV, "
                "close-location, ret20/ret60, top-N, hold, cooldown, or "
                "notional thresholds on the same frozen windows."
            ),
            "post_run_reflection": {
                "why_result_happened": why,
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping manager position weight, "
                    "conviction manager count, conviction value, value share, "
                    "ADV, close-location, ret20/ret60, top-N, hold-day, "
                    "cooldown, or notional thresholds on the same frozen "
                    "windows."
                ),
                "new_evidence_required": (
                    "Need materially richer manager identity/quality, "
                    "sector-normalized ownership surprise, independent "
                    "borrow/options evidence, or forward replacement-value "
                    "rows from a shared helper."
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
        "experiment-local PIT SEC 13F manager-conviction paper overlay"
    )
    payload["backtest_protocol"]["sec13f_provenance"] = (
        "Local SEC structured Form 13F filing-window source-cache zip files. "
        "A signal day uses only the latest window whose end date is <= signal "
        "date and compares new managers versus the prior fully ended window; "
        "manager conviction is measured as ticker value divided by that "
        "manager's own 13F portfolio value in the latest window."
    )
    payload["parameters"].update(
        {
            "min_holder_count": MIN_HOLDER_COUNT,
            "min_conviction_manager_count": MIN_CONVICTION_MANAGER_COUNT,
            "min_manager_position_weight": MIN_MANAGER_POSITION_WEIGHT,
            "min_manager_position_value_usd": MIN_MANAGER_POSITION_VALUE_USD,
            "min_conviction_value_usd": MIN_CONVICTION_VALUE_USD,
            "min_conviction_value_share": MIN_CONVICTION_VALUE_SHARE,
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
        f"# {EXPERIMENT_ID} SEC 13F Manager Conviction",
    ).replace(
        "## 13F History",
        "## 13F Manager-Conviction History",
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
                "SEC 13F manager-level window pairs",
                "new-manager portfolio-weight conviction field",
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
            "anti_js": "No JavaScript was used.",
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
