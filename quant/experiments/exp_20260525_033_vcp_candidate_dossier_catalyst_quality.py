"""exp-20260525-033: VCP candidate dossier / catalyst-quality attribution.

This default-off, no-live-capital experiment adds one read-only diagnostic
field on top of the accepted exp-20260525-022 QQQ-confirmed VCP paper sleeve:
``vcp_catalyst_quality_bucket_v1``.

The goal is not to create another gate. It replays the exact exp-022 candidate
pool and selection, then attributes selected and unselected candidates by a
PIT-safe dossier that combines strictly prior event context with prior
pocket-pivot support.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_volatility_contraction_breakout_shadow as volatility_shadow  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260525_022_volatility_contraction_qqq_confirmed_sleeve as qqq_source  # noqa: E402
from volatility_contraction_paper_sleeve import compute_pre_signal_pocket_pivot_context  # noqa: E402


EXPERIMENT_ID = "exp-20260525-033"
STEM = "vcp_candidate_dossier_catalyst_quality"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "vcp_catalyst_quality_bucket_v1"
DOSSIER_RULE_VERSION = "vcp_candidate_dossier_catalyst_quality_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
SOURCE_EXP022_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260525-022"
    / "volatility_contraction_qqq_confirmed_sleeve.json"
)
EVENT_SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "events"

EVENT_LOOKBACK_SNAPSHOT_DAYS = 20
MIN_SELECTED_TRADES_FOR_ATTRIBUTION = 20
MIN_BUCKET_TRADES_FOR_SEPARATION = 5
MIN_SEPARATION_PNL = 100.0
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30
SUPPORTIVE_QUALITY_BUCKETS = {
    "A_positive_catalyst_plus_volume_support",
    "B_positive_catalyst_only",
    "C_volume_support_only",
}

DOSSIER_AUDIT: dict[str, dict[str, Any]] = {}
_EVENT_SNAPSHOT_PATHS: dict[str, Path] | None = None
_EVENT_SNAPSHOT_CACHE: dict[str, dict[str, Any]] = {}


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MIN_TARGET_TRADES = 20
    base.MIN_TARGET_WINDOWS = 3
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = volatility_shadow

    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(volatility_shadow, name):
            setattr(volatility_shadow, name, None)


def _date_key(value: Any) -> str:
    return str(value or "")[:10].replace("-", "")


def _event_snapshot_paths() -> dict[str, Path]:
    global _EVENT_SNAPSHOT_PATHS
    if _EVENT_SNAPSHOT_PATHS is not None:
        return _EVENT_SNAPSHOT_PATHS
    paths: dict[str, Path] = {}
    if EVENT_SNAPSHOT_DIR.exists():
        for path in EVENT_SNAPSHOT_DIR.glob("event_snapshot_*.json"):
            key = path.stem.split("_")[-1]
            if len(key) == 8 and key.isdigit():
                paths[key] = path
    _EVENT_SNAPSHOT_PATHS = dict(sorted(paths.items()))
    return _EVENT_SNAPSHOT_PATHS


def _load_event_snapshot(date_key: str) -> dict[str, Any]:
    if date_key not in _EVENT_SNAPSHOT_CACHE:
        path = _event_snapshot_paths().get(date_key)
        if path is None:
            _EVENT_SNAPSHOT_CACHE[date_key] = {}
        else:
            _EVENT_SNAPSHOT_CACHE[date_key] = json.loads(path.read_text(encoding="utf-8"))
    return _EVENT_SNAPSHOT_CACHE[date_key]


def _prior_event_snapshot_keys(signal_date: str) -> list[str]:
    signal_key = _date_key(signal_date)
    keys = [key for key in _event_snapshot_paths() if key < signal_key]
    return keys[-EVENT_LOOKBACK_SNAPSHOT_DAYS:]


def _prior_event_rows(ticker: str, signal_date: str) -> list[dict[str, Any]]:
    ticker = str(ticker or "").upper()
    rows: list[dict[str, Any]] = []
    for key in _prior_event_snapshot_keys(signal_date):
        snapshot = _load_event_snapshot(key)
        by_ticker = snapshot.get("events_by_ticker") if isinstance(snapshot, dict) else {}
        if not isinstance(by_ticker, dict):
            continue
        for row in by_ticker.get(ticker, []):
            if isinstance(row, dict):
                rows.append({**row, "snapshot_date": key})
    return rows


def _event_quality_bucket(events: list[dict[str, Any]]) -> str:
    if not events:
        return "no_prior_event"
    directions = {str(row.get("surprise_direction") or "").lower() for row in events}
    subtypes = {str(row.get("event_subtype") or "").lower() for row in events}
    confidences = {str(row.get("source_confidence") or "").lower() for row in events}
    warnings = []
    positives = []
    for row in events:
        flags = row.get("quality_flags") if isinstance(row.get("quality_flags"), dict) else {}
        warnings.extend(flags.get("warning") or [])
        positives.extend(flags.get("positive") or [])
    has_negative = "negative" in directions or warnings or any("negative" in item for item in subtypes)
    has_positive = (
        "positive" in directions
        or positives
        or any(item.endswith("_positive") or "positive" in item for item in subtypes)
    )
    has_high_confidence = "high" in confidences
    if has_negative:
        return "negative_or_warning_event"
    if has_positive and has_high_confidence:
        return "positive_high_confidence_event"
    if has_positive:
        return "positive_lower_confidence_event"
    if has_high_confidence:
        return "high_confidence_context_no_positive_direction"
    return "low_confidence_or_unknown_context"


def _event_context_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    latest_key = max((str(row.get("snapshot_date") or "") for row in events), default=None)
    latest_rows = [row for row in events if row.get("snapshot_date") == latest_key][:5]
    latest_date = (
        f"{latest_key[:4]}-{latest_key[4:6]}-{latest_key[6:8]}" if latest_key else None
    )
    return {
        "pre_signal_event_snapshot_count_20d": len(events),
        "pre_signal_event_snapshot_seen_20d": bool(events),
        "latest_pre_signal_event_snapshot_date": latest_date,
        "pre_signal_event_type_set_20d": sorted(
            {str(row.get("event_type") or "") for row in events if row.get("event_type")}
        ),
        "pre_signal_event_subtype_set_20d": sorted(
            {str(row.get("event_subtype") or "") for row in events if row.get("event_subtype")}
        ),
        "pre_signal_event_direction_set_20d": sorted(
            {
                str(row.get("surprise_direction") or "")
                for row in events
                if row.get("surprise_direction")
            }
        ),
        "pre_signal_event_source_confidence_set_20d": sorted(
            {
                str(row.get("source_confidence") or "")
                for row in events
                if row.get("source_confidence")
            }
        ),
        "latest_pre_signal_event_titles": [
            (row.get("attributes") or {}).get("title") for row in latest_rows
        ],
    }


def _vcp_structure_bucket(row: dict[str, Any]) -> str:
    ratio = row.get("short_to_long_atr_ratio")
    breakout = row.get("breakout_above_prior_20d_high_pct")
    pct_above_50d = row.get("pct_above_50d_ma")
    if isinstance(ratio, (int, float)) and ratio <= 0.70:
        if isinstance(breakout, (int, float)) and breakout <= 0.04:
            return "tight_compression_orderly_breakout"
        return "tight_compression_extended_breakout"
    if isinstance(ratio, (int, float)) and ratio <= 0.80:
        if isinstance(pct_above_50d, (int, float)) and pct_above_50d <= 0.20:
            return "normal_compression_orderly_trend"
        return "normal_compression_extended_trend"
    return "loose_compression_context"


def _dossier_quality_bucket(event_bucket: str, pocket_seen: bool) -> str:
    if event_bucket == "negative_or_warning_event":
        return "D_negative_or_warning_catalyst"
    if event_bucket == "positive_high_confidence_event" and pocket_seen:
        return "A_positive_catalyst_plus_volume_support"
    if event_bucket in {
        "positive_high_confidence_event",
        "positive_lower_confidence_event",
    }:
        return "B_positive_catalyst_only"
    if pocket_seen:
        return "C_volume_support_only"
    if event_bucket in {
        "high_confidence_context_no_positive_direction",
        "low_confidence_or_unknown_context",
    }:
        return "E_ambiguous_prior_context"
    return "F_no_prior_catalyst_or_support"


def _dossier_score(event_bucket: str, pocket_seen: bool, structure_bucket: str) -> float:
    score = {
        "positive_high_confidence_event": 2.0,
        "positive_lower_confidence_event": 1.0,
        "high_confidence_context_no_positive_direction": 0.25,
        "low_confidence_or_unknown_context": 0.0,
        "no_prior_event": 0.0,
        "negative_or_warning_event": -2.0,
    }.get(event_bucket, 0.0)
    if pocket_seen:
        score += 1.5
    if structure_bucket == "tight_compression_orderly_breakout":
        score += 1.0
    elif structure_bucket.startswith("tight_compression"):
        score += 0.5
    elif structure_bucket == "normal_compression_orderly_trend":
        score += 0.25
    return base._round(score, 3)


def build_candidate_dossier(
    row: dict[str, Any],
    ticker_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    signal_date = str(row.get("date") or row.get("signal_date") or "")
    events = _prior_event_rows(ticker, signal_date)
    event_bucket = _event_quality_bucket(events)
    event_summary = _event_context_summary(events)
    pocket = compute_pre_signal_pocket_pivot_context(ticker_rows, signal_date)
    structure_bucket = _vcp_structure_bucket(row)
    pocket_seen = bool(pocket.get("pre_signal_pocket_pivot_seen_10d"))
    quality_bucket = _dossier_quality_bucket(event_bucket, pocket_seen)
    return {
        "vcp_dossier_rule_version": DOSSIER_RULE_VERSION,
        "vcp_catalyst_quality_bucket_v1": quality_bucket,
        "vcp_event_quality_bucket_v1": event_bucket,
        "vcp_structure_bucket_v1": structure_bucket,
        "vcp_catalyst_quality_score_v1": _dossier_score(
            event_bucket, pocket_seen, structure_bucket
        ),
        "vcp_dossier_context_status": "available",
        "vcp_dossier_known_at": "after_signal_date_close_before_next_open_paper_entry",
        "vcp_dossier_event_snapshot_lookback_days": EVENT_LOOKBACK_SNAPSHOT_DAYS,
        "vcp_dossier_event_date_boundary": "event_snapshot_date_strictly_before_signal_date",
        "trade_enabled": False,
        "alters_orders": False,
        **event_summary,
        **pocket,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    label = qqq_source._window_label(cfg)
    entries_by_date = volatility_shadow._baseline_entries(before_result)
    dates = [
        date
        for date in volatility_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    indexes = {
        "QQQ": qqq_source._date_index(volatility_shadow._series(snapshot, "QQQ")),
        "SPY": qqq_source._date_index(volatility_shadow._series(snapshot, "SPY")),
    }
    all_candidates: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    rejected_missing = 0
    rejected_false = 0

    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in volatility_shadow.EXCLUDED_TICKERS:
            continue
        ticker_rows = volatility_shadow._series(snapshot, ticker)
        for row in volatility_shadow._candidate_rows(snapshot, ticker, dates):
            ab_entries = entries_by_date.get(row["date"], [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
            row.update(
                qqq_source._market_context_for_date(
                    snapshot,
                    indexes,
                    str(row["date"]),
                )
            )
            row.update(build_candidate_dossier(row, ticker_rows))
            all_candidates.append(row)
            if row["qqq_gt_spy20"] is True:
                candidates.append(row)
            elif row["qqq_gt_spy20"] is None:
                rejected_missing += 1
            else:
                rejected_false += 1

    candidates.sort(
        key=lambda row: (
            row["date"],
            row["short_to_long_atr_ratio"],
            -row["candidate_day_rs_vs_spy"],
            -row["dollar_volume"],
            row["ticker"],
        )
    )
    DOSSIER_AUDIT[label] = {
        "raw_volatility_candidates": len(all_candidates),
        "qqq_confirmed_candidates": len(candidates),
        "rejected_qqq_not_leading_spy": rejected_false,
        "rejected_missing_market_context": rejected_missing,
        "candidate_dates_before_gate": len({row["date"] for row in all_candidates}),
        "candidate_dates_after_gate": len({row["date"] for row in candidates}),
        "qqq_candidate_bucket_attribution": _candidate_bucket_summary(candidates),
    }
    return candidates


def _read_exp022() -> dict[str, Any]:
    return json.loads(SOURCE_EXP022_JSON.read_text(encoding="utf-8"))


def _trade_key(row: dict[str, Any]) -> tuple[str, str, float]:
    return (
        str(row.get("ticker") or ""),
        str(row.get("signal_date") or row.get("date") or ""),
        round(float(row.get("pnl") or 0.0), 2),
    )


def _exp022_selection_parity(payload: dict[str, Any]) -> dict[str, Any]:
    source = _read_exp022()
    by_window: dict[str, Any] = {}
    mismatch_count = 0
    for label in base.WINDOWS:
        source_keys = [_trade_key(row) for row in source["target_trades_by_window"][label]]
        replay_keys = [_trade_key(row) for row in payload["target_trades_by_window"][label]]
        mismatches = [
            {"index": idx, "source": source_key, "replay": replay_key}
            for idx, (source_key, replay_key) in enumerate(zip(source_keys, replay_keys))
            if source_key != replay_key
        ]
        mismatch_count += len(mismatches) + abs(len(source_keys) - len(replay_keys))
        by_window[label] = {
            "source_trade_count": len(source_keys),
            "replay_trade_count": len(replay_keys),
            "ordered_trade_keys_match": source_keys == replay_keys,
            "mismatch_sample": mismatches[:5],
        }
    source_agg = source["delta_metrics"]["aggregate"]
    replay_agg = payload["delta_metrics"]["aggregate"]
    ev_diff = base._round(
        replay_agg["expected_value_score_delta_sum"]
        - source_agg["expected_value_score_delta_sum"],
        6,
    )
    pnl_diff = base._round(
        replay_agg["total_pnl_delta_sum"] - source_agg["total_pnl_delta_sum"],
        2,
    )
    return {
        "source_experiment_id": "exp-20260525-022",
        "source_artifact": base._repo_rel(SOURCE_EXP022_JSON),
        "by_window": by_window,
        "aggregate_ev_delta_diff": ev_diff,
        "aggregate_pnl_delta_diff": pnl_diff,
        "mismatch_count": mismatch_count,
        "passed": mismatch_count == 0 and abs(ev_diff) <= 0.0001 and abs(pnl_diff) <= 0.01,
    }


def _candidate_bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("vcp_catalyst_quality_bucket_v1") or "missing_bucket")].append(row)
    out: dict[str, Any] = {}
    for bucket, bucket_rows in sorted(grouped.items()):
        fwd10 = [
            float(row["fwd_10d"])
            for row in bucket_rows
            if isinstance(row.get("fwd_10d"), (int, float))
        ]
        out[bucket] = {
            "candidate_count": len(bucket_rows),
            "candidate_date_count": len({row.get("date") for row in bucket_rows}),
            "ticker_count": len({row.get("ticker") for row in bucket_rows}),
            "avg_fwd_10d": base._round(sum(fwd10) / len(fwd10), 6) if fwd10 else None,
            "fwd_10d_win_rate": (
                base._round(sum(1 for value in fwd10 if value > 0) / len(fwd10), 6)
                if fwd10
                else None
            ),
            "fwd_10d_sample": len(fwd10),
        }
    return out


def _trade_bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("vcp_catalyst_quality_bucket_v1") or "missing_bucket")].append(row)
    out: dict[str, Any] = {}
    for bucket, bucket_rows in sorted(grouped.items()):
        pnls = [float(row.get("pnl") or 0.0) for row in bucket_rows]
        positives = [value for value in pnls if value > 0]
        out[bucket] = {
            "trade_count": len(bucket_rows),
            "total_pnl": base._round(sum(pnls), 2),
            "avg_pnl": base._round(sum(pnls) / len(pnls), 2) if pnls else None,
            "win_rate": (
                base._round(sum(1 for value in pnls if value > 0) / len(pnls), 6)
                if pnls
                else None
            ),
            "positive_pnl": base._round(sum(positives), 2),
            "negative_pnl": base._round(sum(value for value in pnls if value < 0), 2),
            "ticker_count": len({row.get("ticker") for row in bucket_rows}),
            "tickers": sorted({str(row.get("ticker") or "").upper() for row in bucket_rows}),
            "windows": sorted({str(row.get("window") or "") for row in bucket_rows}),
        }
    return out


def _selected_trade_attribution(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate_rows: list[dict[str, Any]] = []
    by_window: dict[str, Any] = {}
    for label, rows in payload["target_trades_by_window"].items():
        window_rows = [{**row, "window": label} for row in rows]
        aggregate_rows.extend(window_rows)
        by_window[label] = _trade_bucket_summary(window_rows)
    aggregate = _trade_bucket_summary(aggregate_rows)
    all_pnls = [float(row.get("pnl") or 0.0) for row in aggregate_rows]
    all_avg = sum(all_pnls) / len(all_pnls) if all_pnls else 0.0
    eligible = {
        bucket: row
        for bucket, row in aggregate.items()
        if int(row["trade_count"]) >= MIN_BUCKET_TRADES_FOR_SEPARATION
        and row["avg_pnl"] is not None
    }
    best_bucket = None
    worst_bucket = None
    if eligible:
        best_bucket = max(eligible, key=lambda key: eligible[key]["avg_pnl"])
        worst_bucket = min(eligible, key=lambda key: eligible[key]["avg_pnl"])
    separation = None
    useful = False
    if best_bucket and worst_bucket:
        separation = base._round(
            eligible[best_bucket]["avg_pnl"] - eligible[worst_bucket]["avg_pnl"],
            2,
        )
        useful = (
            eligible[best_bucket]["avg_pnl"] > all_avg
            and eligible[worst_bucket]["avg_pnl"] < all_avg
            and separation >= MIN_SEPARATION_PNL
        )
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "overall_avg_pnl": base._round(all_avg, 2) if all_pnls else None,
        "eligible_bucket_min_trades": MIN_BUCKET_TRADES_FOR_SEPARATION,
        "best_eligible_bucket": best_bucket,
        "worst_eligible_bucket": worst_bucket,
        "best_worst_avg_pnl_separation": separation,
        "useful_quality_separation": useful,
    }


def _dossier_samples(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, trades in payload["target_trades_by_window"].items():
        for row in trades:
            rows.append(
                {
                    "window": label,
                    "ticker": row.get("ticker"),
                    "signal_date": row.get("signal_date") or row.get("date"),
                    "pnl": row.get("pnl"),
                    "vcp_catalyst_quality_bucket_v1": row.get(
                        "vcp_catalyst_quality_bucket_v1"
                    ),
                    "vcp_event_quality_bucket_v1": row.get("vcp_event_quality_bucket_v1"),
                    "vcp_structure_bucket_v1": row.get("vcp_structure_bucket_v1"),
                    "pre_signal_event_snapshot_count_20d": row.get(
                        "pre_signal_event_snapshot_count_20d"
                    ),
                    "pre_signal_pocket_pivot_seen_10d": row.get(
                        "pre_signal_pocket_pivot_seen_10d"
                    ),
                    "latest_pre_signal_event_titles": row.get(
                        "latest_pre_signal_event_titles"
                    ),
                }
            )
    rows.sort(key=lambda row: (row["window"], str(row["signal_date"]), str(row["ticker"])))
    return rows[:50]


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    selected_attr = _selected_trade_attribution(payload)
    parity = _exp022_selection_parity(payload)
    replay_gate4 = dict(payload["gate4"])
    selected_trade_count = int(payload["target_trade_summary"]["total_trade_count"])
    coverage_passed = (
        selected_trade_count >= MIN_SELECTED_TRADES_FOR_ATTRIBUTION
        and all(
            row.get("vcp_catalyst_quality_bucket_v1")
            for rows in payload["target_trades_by_window"].values()
            for row in rows
        )
    )
    diagnostic_separation = bool(
        parity["passed"]
        and coverage_passed
        and selected_attr["useful_quality_separation"]
    )
    hypothesis_supported = bool(
        diagnostic_separation
        and selected_attr["best_eligible_bucket"] in SUPPORTIVE_QUALITY_BUCKETS
    )
    decision = (
        "observed_only_vcp_candidate_dossier_supportive_quality_edge"
        if hypothesis_supported
        else (
            "observed_only_vcp_candidate_dossier_counter_signal"
            if diagnostic_separation
            else "observed_only_vcp_candidate_dossier_no_clear_quality_edge"
        )
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Among exp-20260525-022 QQQ-confirmed VCP candidates, a PIT-safe dossier "
        "bucket that separates prior catalyst quality from prior volume support "
        "may explain which breakouts have stronger replacement value without "
        "creating another hard gate."
    )
    payload["change_type"] = "default_off_vcp_candidate_dossier_attribution"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 6
    payload["nearby_prior_experiments"] = [
        "exp-20260525-020",
        "exp-20260525-022",
        "exp-20260525-024",
        "exp-20260525-027",
        "exp-20260525-030",
        "exp-20260525-032",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate_high"
    payload["new_evidence_type"] = "pit_safe_vcp_candidate_dossier_bucket_attribution"
    payload["vcp_candidate_dossier"] = {
        "rule_version": DOSSIER_RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "candidate_bucket_attribution_by_window": DOSSIER_AUDIT,
        "selected_trade_bucket_attribution": selected_attr,
        "selected_trade_dossier_samples": _dossier_samples(payload),
        "source_exp022_selection_parity": parity,
    }
    payload["gate4_strategy_replay"] = replay_gate4
    payload["gate4"] = {
        "passed": hypothesis_supported,
        "observed_only": True,
        "strategy_behavior_changed": False,
        "promotion_grade": False,
        "source_exp022_selection_parity_passed": parity["passed"],
        "dossier_coverage_passed": coverage_passed,
        "selected_trade_count": selected_trade_count,
        "selected_trade_count_min": MIN_SELECTED_TRADES_FOR_ATTRIBUTION,
        "diagnostic_bucket_separation": diagnostic_separation,
        "supportive_quality_hypothesis_supported": hypothesis_supported,
        "supportive_quality_buckets": sorted(SUPPORTIVE_QUALITY_BUCKETS),
        "best_eligible_bucket": selected_attr["best_eligible_bucket"],
        "worst_eligible_bucket": selected_attr["worst_eligible_bucket"],
        "best_worst_avg_pnl_separation": selected_attr[
            "best_worst_avg_pnl_separation"
        ],
        "min_bucket_trades_for_separation": MIN_BUCKET_TRADES_FOR_SEPARATION,
        "min_avg_pnl_separation": MIN_SEPARATION_PNL,
        "note": (
            "This gate grades attribution usefulness only. It cannot promote a "
            "trade gate, sizing rule, ranking rule, or live/default order path."
        ),
    }
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool attribution: Kova-style support is more "
            "likely useful as a multi-field dossier bucket than as a simple "
            "pocket-pivot or event-presence boolean gate."
        ),
        "2_history_check": {
            "exp-20260525-022": "Accepted QQQ-confirmed VCP replay lead.",
            "exp-20260525-027": "Pocket-pivot boolean gate lagged exp-022.",
            "exp-20260525-030": "Event-presence boolean gate lagged exp-022.",
            "exp-20260525-032": "Nearby VCP volume-dryup support scout exists; this run is dossier attribution, not another support gate.",
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Observed-only: exact exp-022 selected-trade parity, >=20 selected "
            "trades with dossier buckets, and an eligible best/worst bucket "
            f"average-PnL separation of at least ${MIN_SEPARATION_PNL:.0f}, "
            "where the best eligible bucket must be one of the supportive "
            "catalyst/volume buckets. "
            "Passing does not promote trading behavior."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260525_033_vcp_candidate_dossier_catalyst_quality.py"
        ),
    }
    payload["gate2"]["runtime_fields"].extend(
        [
            "daily event snapshots strictly before signal date",
            "computed vcp_catalyst_quality_bucket_v1",
            "computed vcp_event_quality_bucket_v1",
            "computed vcp_structure_bucket_v1",
            "computed pre_signal_pocket_pivot_seen_10d",
        ]
    )
    payload["gate2"]["vcp_candidate_dossier"] = {
        "event_snapshot_dir": base._repo_rel(EVENT_SNAPSHOT_DIR),
        "event_snapshot_count": len(_event_snapshot_paths()),
        "pocket_pivot_source": "volatility_contraction_paper_sleeve.compute_pre_signal_pocket_pivot_context",
        "date_boundary": "event snapshots before signal date; pocket pivot scans prior trading days and excludes signal date",
        "passed": len(_event_snapshot_paths()) > 0,
    }
    payload["gate3"].update(
        {
            "new_core_filter_added": False,
            "core_survival_unchanged": True,
            "candidate_pool_changed": False,
            "note": (
                "No core filter, paper filter, ranking, sizing, or exit rule was "
                "added. The exp-022 selected trades are replayed unchanged, with "
                "dossier metadata attached for attribution."
            ),
        }
    )
    payload["parameters"]["vcp_candidate_dossier"] = {
        "rule_version": DOSSIER_RULE_VERSION,
        "field": CHANGED_VARIABLE,
        "event_snapshot_lookback_days": EVENT_LOOKBACK_SNAPSHOT_DAYS,
        "event_date_boundary": "strictly_before_signal_date",
        "pocket_pivot_scan": "prior_10_trading_days_excluding_signal_date",
        "bucket_order": [
            "A_positive_catalyst_plus_volume_support",
            "B_positive_catalyst_only",
            "C_volume_support_only",
            "D_negative_or_warning_catalyst",
            "E_ambiguous_prior_context",
            "F_no_prior_catalyst_or_support",
        ],
        "trade_enabled": False,
        "alters_orders": False,
    }
    payload["parameters"]["acceptance"].update(
        {
            "observed_only": True,
            "exp022_selection_parity_required": True,
            "min_selected_trades_for_attribution": MIN_SELECTED_TRADES_FOR_ATTRIBUTION,
            "min_bucket_trades_for_separation": MIN_BUCKET_TRADES_FOR_SEPARATION,
            "min_avg_pnl_separation": MIN_SEPARATION_PNL,
        }
    )
    if hypothesis_supported:
        payload["interpretation"] = (
            "The VCP dossier produced a supportive read-only quality separation "
            "while leaving exp-022 selection unchanged. It still cannot affect "
            "trading without a later promotion experiment."
        )
    elif diagnostic_separation:
        payload["interpretation"] = (
            "The VCP dossier was replay/PIT-safe and separated outcomes, but the "
            "best eligible bucket was not a supportive catalyst/volume bucket. "
            "This argues against turning Kova-style prior support into a VCP gate "
            "on the frozen sample."
        )
    else:
        payload["interpretation"] = (
            "The VCP dossier was replay/PIT-safe but did not create a clear "
            "quality edge strong enough to justify a new gate. Keep it as "
            "candidate-level attribution only."
        )
    payload["next_evidence_needed"] = (
        "Use this dossier on closed forward exp-022 paper rows and richer event "
        "semantics before considering any ranking or allocation experiment."
    )
    payload["why_not_other_changes"] = (
        "Did not retune VCP, QQQ/SPY, rank, notional, hold-days, exits, universe, "
        "or LLM/news. The experiment adds metadata and attribution only."
    )
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "default_off_paper_only": True,
        "production_watchlist_changed": False,
        "production_orders_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
        base._repo_rel(SOURCE_EXP022_JSON),
    ]
    if hypothesis_supported:
        payload["rejection_reason"] = None
    elif diagnostic_separation:
        payload["rejection_reason"] = "best_eligible_bucket_was_not_supportive_quality"
    else:
        payload["rejection_reason"] = "no_clear_quality_bucket_separation"
    payload["anti_js"] = "No JavaScript was used."
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    selected = payload["vcp_candidate_dossier"]["selected_trade_bucket_attribution"]
    rows = [
        "| Bucket | Trades | Total PnL | Avg PnL | Win Rate | Tickers |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket, stats in selected["aggregate"].items():
        rows.append(
            "| {bucket} | {trades} | ${pnl:,.2f} | ${avg:,.2f} | {win} | {tickers} |".format(
                bucket=bucket,
                trades=stats["trade_count"],
                pnl=stats["total_pnl"],
                avg=stats["avg_pnl"] or 0.0,
                win=stats["win_rate"],
                tickers=stats["ticker_count"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    parity = payload["vcp_candidate_dossier"]["source_exp022_selection_parity"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VCP Candidate Dossier / Catalyst Quality",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: `vcp_catalyst_quality_bucket_v1`, a read-only "
                "candidate dossier bucket for the unchanged exp-022 VCP sleeve."
            ),
            "",
            "## Exp-022 Replay Parity",
            "",
            f"- selected-trade parity passed: `{parity['passed']}`",
            f"- aggregate EV delta diff: `{parity['aggregate_ev_delta_diff']}`",
            f"- aggregate PnL delta diff: `${parity['aggregate_pnl_delta_diff']}`",
            f"- replay EV delta vs core: `{aggregate['expected_value_score_delta_sum']}`",
            f"- replay PnL delta vs core: `${aggregate['total_pnl_delta_sum']}`",
            "",
            "## Selected-Trade Bucket Attribution",
            "",
            *rows,
            "",
            "## Quality Separation",
            "",
            "```json",
            json.dumps(
                {
                    "overall_avg_pnl": selected["overall_avg_pnl"],
                    "best_eligible_bucket": selected["best_eligible_bucket"],
                    "worst_eligible_bucket": selected["worst_eligible_bucket"],
                    "best_worst_avg_pnl_separation": selected[
                        "best_worst_avg_pnl_separation"
                    ],
                    "useful_quality_separation": selected["useful_quality_separation"],
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Candidate Bucket Audit",
            "",
            "```json",
            json.dumps(DOSSIER_AUDIT, indent=2, sort_keys=True),
            "```",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "VCP candidate dossier catalyst-quality attribution",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_base_module()
    base._candidate_rows_for_window = _candidate_rows_for_window
    payload = _update_payload(base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "selected_trade_bucket_attribution": payload[
                        "vcp_candidate_dossier"
                    ]["selected_trade_bucket_attribution"]["aggregate"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
