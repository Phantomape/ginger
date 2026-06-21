"""exp-20260621-020: SEC 13F sector-normalized ownership surprise scout.

Replay-only alpha search. This tests the new evidence axis requested by the
previous 13F failure: ownership change must be unusually strong versus the
same sector's 13F holder/value-growth distribution, rather than merely passing
absolute holder-count, new-holder, low-crowding, or manager-conviction gates.

No production/shared helper, live order, ranking, sizing, exit, LLM/news, or
watchlist behavior changes. A positive result is only a replay lead until a
shared daily default-off 13F helper exists. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import timezone
from pathlib import Path
from typing import Any

import exp_20260621_019_sec13f_manager_conviction as prev


base = prev.base

EXPERIMENT_ID = "exp-20260621-020"
STEM = "sec13f_sector_normalized_ownership_surprise"
TRIAL_FAMILY = "sec13f_sector_normalized_ownership_surprise_candidate_pool"
TRIAL_VARIANT_ID = "sec13f_sector_surprise_liquid_leadership_top1_10d_v1"
CHANGED_VARIABLE = "sec13f_sector_normalized_ownership_surprise_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

ROOT = base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_020_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
DERIVED_CACHE_DIR = OUT_DIR / "derived_sec13f"

MIN_HOLDER_COUNT = 25
MIN_HOLDER_DELTA = 2
MIN_TOTAL_VALUE_GROWTH_PCT = 0.0
MIN_SECTOR_SAMPLE_COUNT = 12
MIN_VALUE_GROWTH_Z = 0.60
MIN_HOLDER_DELTA_Z = 0.20
MIN_COMBINED_SURPRISE_Z = 1.00

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "stale_quarterly_data",
        "sector_zscore_noise",
        "window_regression",
        "drawdown_drift",
        "not_incremental",
    ],
    "confidence_reason": (
        "The last 13F manager-conviction failure explicitly required "
        "sector-normalized ownership surprise as new evidence; local PIT "
        "13F zips cover all windows, but quarterly lag and overlap with "
        "liquid leadership keep odds low."
    ),
    "recorded_at": "2026-06-21T20:10:13+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_live_adapter",
    "implementation_mode": "private_replay_scout",
    "private_replay_scout_escape_reason": (
        "The sector-normalized 13F ownership-surprise aggregation is "
        "implemented only in this experiment. A positive result is lead-only "
        "until a shared helper computes the same field in historical replay "
        "and daily default-off snapshots."
    ),
    "live_realism_evaluated": False,
    "parity_note": (
        "This experiment changes no production code. A positive result remains "
        "a replay lead until a shared default-off helper computes the same PIT "
        "13F window pair, sector-relative holder/value surprise fields, "
        "leadership gates, overlap exclusion, entry, exit, costs, cooldown, "
        "and ledger fields identically in historical replay and daily "
        "production snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 13F sector-normalized ownership surprise, "
        "confirmed by liquid leadership, may identify institutional "
        "accumulation that is stronger than same-sector ownership drift and "
        "more informative than absolute holder-count or manager-conviction "
        "thresholds."
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
            "artifact: aggregate EV/PnL slightly negative and old_thin weak."
        ),
        "exp-20260621-019": (
            "Rejected new-manager portfolio-weight conviction: aggregate EV "
            "positive but late/old windows regressed and drawdown drift failed."
        ),
        "difference": (
            "This run computes sector-relative holder and value-growth "
            "z-scores inside each PIT 13F window pair. It is not an absolute "
            "holder-count, value-growth, low-crowding, new-holder, or "
            "manager-position-weight threshold retry."
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
        "exp_20260621_020_sec13f_sector_normalized_ownership_surprise.py"
    ),
}

_original_build_payload = prev._original_build_payload
_original_build_card = prev._original_build_card
_original_build_log_record = prev._original_build_log_record

_SECTOR_STATS_CACHE: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _mean_sd(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return mean, math.sqrt(variance)


def _zscore(value: float, mean: float, sd: float) -> float:
    if sd <= 1e-9:
        return 0.0
    return (value - mean) / sd


def _sector_key(sector_entries: dict[str, dict[str, Any]], ticker: str) -> str:
    meta = sector_entries.get(ticker) or {}
    sector = str(meta.get("sector") or "").strip()
    if sector:
        return sector
    industry = str(meta.get("industry") or "").strip()
    return industry or "unknown"


def _ownership_metrics(latest: dict[str, Any], prior: dict[str, Any]) -> dict[str, float]:
    total_value_usd = base._float(latest.get("total_value_usd")) or 0.0
    prior_total_value_usd = base._float(prior.get("total_value_usd")) or 0.0
    holder_count = int(latest.get("holder_count") or 0)
    prior_holder_count = int(prior.get("holder_count") or 0)
    holder_delta = holder_count - prior_holder_count
    return {
        "total_value_usd": total_value_usd,
        "prior_total_value_usd": prior_total_value_usd,
        "value_growth_pct": (total_value_usd - prior_total_value_usd)
        / max(prior_total_value_usd, 1.0),
        "holder_count": float(holder_count),
        "prior_holder_count": float(prior_holder_count),
        "holder_delta": float(holder_delta),
        "holder_growth_pct": holder_delta / max(prior_holder_count, 1),
    }


def _sector_pair_stats(
    *,
    latest_13f: dict[str, Any],
    prior_13f: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    key = (latest_13f["window_label"], prior_13f["window_label"])
    cached = _SECTOR_STATS_CACHE.get(key)
    if cached is not None:
        return cached

    grouped: dict[str, list[dict[str, float]]] = defaultdict(list)
    latest_by_ticker = latest_13f.get("holdings_by_ticker") or {}
    prior_by_ticker = prior_13f.get("holdings_by_ticker") or {}
    for ticker, latest in latest_by_ticker.items():
        prior = prior_by_ticker.get(ticker)
        if not prior:
            continue
        metrics = _ownership_metrics(latest, prior)
        if metrics["prior_holder_count"] < 5:
            continue
        sector = _sector_key(sector_entries, str(ticker))
        grouped[sector].append(metrics)

    stats: dict[str, dict[str, Any]] = {}
    for sector, rows in grouped.items():
        value_mean, value_sd = _mean_sd([row["value_growth_pct"] for row in rows])
        holder_mean, holder_sd = _mean_sd([row["holder_delta"] for row in rows])
        holder_growth_mean, holder_growth_sd = _mean_sd(
            [row["holder_growth_pct"] for row in rows]
        )
        stats[sector] = {
            "sector_sample_count": len(rows),
            "value_growth_pct_mean": value_mean,
            "value_growth_pct_sd": value_sd,
            "holder_delta_mean": holder_mean,
            "holder_delta_sd": holder_sd,
            "holder_growth_pct_mean": holder_growth_mean,
            "holder_growth_pct_sd": holder_growth_sd,
        }
    _SECTOR_STATS_CACHE[key] = stats
    return stats


def _load_13f_history(universe: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    original_derived = prev.DERIVED_CACHE_DIR
    original_rule = prev.RULE_VERSION
    original_experiment = prev.EXPERIMENT_ID
    prev.DERIVED_CACHE_DIR = DERIVED_CACHE_DIR
    prev.RULE_VERSION = RULE_VERSION
    prev.EXPERIMENT_ID = EXPERIMENT_ID
    try:
        by_label, summary = prev._load_13f_history(universe)
    finally:
        prev.DERIVED_CACHE_DIR = original_derived
        prev.RULE_VERSION = original_rule
        prev.EXPERIMENT_ID = original_experiment
    summary.update(
        {
            "sector_surprise_rule_version": RULE_VERSION,
            "new_evidence_axis": (
                "sector-normalized holder/value-growth surprise computed "
                "within each PIT 13F window-pair sector distribution"
            ),
            "derived_cache_dir": _repo_rel(DERIVED_CACHE_DIR),
        }
    )
    return by_label, summary


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

    metrics = _ownership_metrics(latest, prior)
    holder_count = int(metrics["holder_count"])
    prior_holder_count = int(metrics["prior_holder_count"])
    holder_delta = int(metrics["holder_delta"])
    value_growth_pct = metrics["value_growth_pct"]
    holder_growth_pct = metrics["holder_growth_pct"]
    total_value_usd = metrics["total_value_usd"]
    prior_total_value_usd = metrics["prior_total_value_usd"]

    if holder_count < MIN_HOLDER_COUNT:
        return None
    if holder_delta < MIN_HOLDER_DELTA:
        return None
    if value_growth_pct < MIN_TOTAL_VALUE_GROWTH_PCT:
        return None

    sector = _sector_key(sector_entries, ticker)
    stats = _sector_pair_stats(
        latest_13f=latest_13f,
        prior_13f=prior_13f,
        sector_entries=sector_entries,
    ).get(sector)
    if not stats or int(stats["sector_sample_count"]) < MIN_SECTOR_SAMPLE_COUNT:
        return None
    value_growth_z = _zscore(
        value_growth_pct,
        float(stats["value_growth_pct_mean"]),
        float(stats["value_growth_pct_sd"]),
    )
    holder_delta_z = _zscore(
        float(holder_delta),
        float(stats["holder_delta_mean"]),
        float(stats["holder_delta_sd"]),
    )
    holder_growth_z = _zscore(
        holder_growth_pct,
        float(stats["holder_growth_pct_mean"]),
        float(stats["holder_growth_pct_sd"]),
    )
    combined_surprise_z = (
        0.60 * value_growth_z + 0.30 * holder_delta_z + 0.10 * holder_growth_z
    )
    if value_growth_z < MIN_VALUE_GROWTH_Z:
        return None
    if holder_delta_z < MIN_HOLDER_DELTA_Z:
        return None
    if combined_surprise_z < MIN_COMBINED_SURPRISE_Z:
        return None

    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if (
        idx is None
        or spy_idx is None
        or idx < base.MIN_HISTORY_SESSIONS
        or spy_idx < base.MIN_HISTORY_SESSIONS
    ):
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
        1.25 * combined_surprise_z
        + 0.65 * value_growth_z
        + 0.35 * holder_delta_z
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
        "source": "SEC13F_SECTOR_NORMALIZED_OWNERSHIP_SURPRISE_LIQUID_LEADERSHIP_PAPER",
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
        "sec13f_sector": sector,
        "sec13f_sector_sample_count": int(stats["sector_sample_count"]),
        "sec13f_sector_value_growth_pct_mean": round(
            float(stats["value_growth_pct_mean"]), 6
        ),
        "sec13f_sector_holder_delta_mean": round(float(stats["holder_delta_mean"]), 6),
        "sec13f_value_growth_z": round(value_growth_z, 6),
        "sec13f_holder_delta_z": round(holder_delta_z, 6),
        "sec13f_holder_growth_z": round(holder_growth_z, 6),
        "sec13f_combined_surprise_z": round(combined_surprise_z, 6),
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
        -float(row.get("sec13f_combined_surprise_z") or 0.0),
        -float(row.get("sec13f_value_growth_z") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
    )


def _build_payload() -> dict[str, Any]:
    payload = _original_build_payload()
    passed = bool(payload.get("gate4", {}).get("passed"))
    decision = (
        "positive_replay_lead_not_promoted_sec13f_sector_normalized_ownership_surprise"
        if passed
        else "rejected_sec13f_sector_normalized_ownership_surprise_candidate_pool"
    )
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    aggregate = payload["delta_metrics"]["aggregate"]
    why = (
        "The sector-normalized 13F ownership-surprise field cleared the replay "
        "gate, but remains lead-only because shared daily helper parity and "
        "forward replacement rows are absent."
        if passed
        else (
            "The sector-normalized 13F ownership-surprise field failed Gate 4. "
            "Relative ownership change added economic specificity versus "
            "absolute 13F thresholds, but the delayed quarterly signal still "
            "did not create stable all-window replacement value after "
            "next-open execution and costs."
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
                "exp-20260621-019",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "pit_sec_13f_sector_normalized_ownership_surprise",
            "gate_questions": PRE_RUN_QUESTIONS,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": (
                "The SEC 13F sector-normalized ownership-surprise candidate "
                "source cleared numeric replay gates, but remains lead-only "
                "because no shared daily helper or production 13F sector "
                "snapshot was promoted."
                if passed
                else (
                    "The SEC 13F sector-normalized ownership-surprise "
                    "candidate source was rejected under the standard "
                    "three-window protocol."
                )
            ),
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_reasons"]),
            "next_evidence_needed": (
                "A retry needs materially richer manager identity/quality, "
                "sector-normalized ownership data with manager quality, "
                "independent borrow/options evidence, or closed forward "
                "replacement rows from a shared 13F helper. Do not sweep "
                "sector z-score, holder/value, ADV, close-location, ret20/"
                "ret60, top-N, hold, cooldown, or notional thresholds on the "
                "same frozen windows."
            ),
            "post_run_reflection": {
                "why_result_happened": why,
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping sector z-score thresholds, "
                    "holder/value growth thresholds, sector sample sizes, ADV, "
                    "close-location, ret20/ret60, top-N, hold-day, cooldown, "
                    "or notional thresholds on the same frozen windows."
                ),
                "new_evidence_required": (
                    "Need materially richer manager identity/quality, "
                    "sector-normalized ownership surprise with independent "
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
        "experiment-local PIT SEC 13F sector-normalized ownership-surprise "
        "paper overlay"
    )
    payload["backtest_protocol"]["sec13f_provenance"] = (
        "Local SEC structured Form 13F filing-window source-cache zip files. "
        "A signal day uses only the latest window whose end date is <= signal "
        "date and compares holder/value growth versus the prior fully ended "
        "window; the tested field is z-scored against the same-sector "
        "ownership-change distribution for that 13F pair."
    )
    payload["parameters"].update(
        {
            "min_holder_count": MIN_HOLDER_COUNT,
            "min_holder_delta": MIN_HOLDER_DELTA,
            "min_total_value_growth_pct": MIN_TOTAL_VALUE_GROWTH_PCT,
            "min_sector_sample_count": MIN_SECTOR_SAMPLE_COUNT,
            "min_value_growth_z": MIN_VALUE_GROWTH_Z,
            "min_holder_delta_z": MIN_HOLDER_DELTA_Z,
            "min_combined_surprise_z": MIN_COMBINED_SURPRISE_Z,
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
        f"# {EXPERIMENT_ID} SEC 13F Sector-Normalized Ownership Surprise",
    ).replace(
        "## 13F History",
        "## 13F Sector-Surprise History",
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
                "SEC 13F window pairs",
                "sector-relative holder/value surprise z-scores",
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
