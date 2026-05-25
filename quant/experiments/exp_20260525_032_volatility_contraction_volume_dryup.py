"""exp-20260525-032: VCP volume dry-up confirmation.

This default-off, no-live-capital experiment tests one orthogonal field on top
of the accepted exp-20260525-022 QQQ-confirmed volatility-contraction paper
sleeve: whether volume dried up before the breakout signal.

It does not retune compression, breakout, QQQ/SPY confirmation, rank, notional,
hold days, exits, LLM/news, universe, or live/default orders. No JavaScript is
used.
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

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260525_022_volatility_contraction_qqq_confirmed_sleeve as qqq_source  # noqa: E402
import exp_20260426_volatility_contraction_breakout_shadow as volatility_shadow  # noqa: E402


EXPERIMENT_ID = "exp-20260525-032"
STEM = "volatility_contraction_volume_dryup"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "pre_signal_volume_dryup_ratio_10v50_lte_0p80"
VOLUME_DRYUP_RULE_VERSION = "pre_signal_volume_dryup_10v50_v1"

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

SHORT_VOLUME_DAYS = 10
LONG_VOLUME_DAYS = 50
VOLUME_DRYUP_MAX_RATIO = 0.80
EXP022_MIN_EV_LIFT = 0.05
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

VOLUME_DRYUP_AUDIT: dict[str, dict[str, Any]] = {}


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
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
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


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _volume(row: dict[str, Any]) -> float | None:
    value = row.get("Volume") if "Volume" in row else row.get("volume")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def compute_pre_signal_volume_dryup_context(
    rows: list[dict[str, Any]],
    signal_date: str,
    *,
    short_days: int = SHORT_VOLUME_DAYS,
    long_days: int = LONG_VOLUME_DAYS,
    max_ratio: float = VOLUME_DRYUP_MAX_RATIO,
) -> dict[str, Any]:
    """Return PIT-safe volume dry-up metadata before a signal date."""
    normalised = sorted(
        [row for row in rows or [] if _date10(row.get("Date") or row.get("date"))],
        key=lambda row: _date10(row.get("Date") or row.get("date")),
    )
    signal_date = _date10(signal_date)
    index_by_date = {
        _date10(row.get("Date") or row.get("date")): idx
        for idx, row in enumerate(normalised)
    }
    base_context = {
        "pre_signal_volume_dryup_rule_version": VOLUME_DRYUP_RULE_VERSION,
        "pre_signal_volume_dryup_ratio_10v50": None,
        "pre_signal_volume_dryup_passed": False,
        "pre_signal_volume_dryup_short_avg_volume": None,
        "pre_signal_volume_dryup_long_avg_volume": None,
        "volume_dryup_status": "unavailable",
        "volume_dryup_short_days": int(short_days),
        "volume_dryup_long_days": int(long_days),
        "volume_dryup_max_ratio": float(max_ratio),
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }
    idx = index_by_date.get(signal_date)
    if idx is None:
        return {**base_context, "volume_dryup_status": "missing_signal_date"}
    if short_days <= 0 or long_days <= 0 or short_days > long_days:
        return {**base_context, "volume_dryup_status": "invalid_window_config"}
    if idx < long_days:
        return {**base_context, "volume_dryup_status": "insufficient_history"}

    short_window = normalised[idx - short_days:idx]
    long_window = normalised[idx - long_days:idx]
    short_volumes = [_volume(row) for row in short_window]
    long_volumes = [_volume(row) for row in long_window]
    if (
        len(short_volumes) != short_days
        or len(long_volumes) != long_days
        or any(value is None for value in short_volumes)
        or any(value is None for value in long_volumes)
    ):
        return {
            **base_context,
            "volume_dryup_status": "insufficient_valid_volume_history",
        }

    short_avg = sum(float(value) for value in short_volumes if value is not None) / short_days
    long_avg = sum(float(value) for value in long_volumes if value is not None) / long_days
    if long_avg <= 0:
        return {**base_context, "volume_dryup_status": "invalid_long_avg_volume"}
    ratio = short_avg / long_avg
    return {
        **base_context,
        "pre_signal_volume_dryup_ratio_10v50": base._round(ratio, 6),
        "pre_signal_volume_dryup_passed": ratio <= float(max_ratio),
        "pre_signal_volume_dryup_short_avg_volume": base._round(short_avg, 2),
        "pre_signal_volume_dryup_long_avg_volume": base._round(long_avg, 2),
        "volume_dryup_status": "available",
    }


def _volume_context_for_row(
    snapshot: dict[str, list[dict[str, Any]]],
    row: dict[str, Any],
) -> dict[str, Any]:
    rows = volatility_shadow._series(snapshot, str(row.get("ticker") or ""))
    return compute_pre_signal_volume_dryup_context(rows, str(row.get("date") or ""))


def _dryup_bucket(row: dict[str, Any]) -> str:
    if row.get("pre_signal_volume_dryup_passed") is True:
        return "dryup_supported"
    if row.get("volume_dryup_status") == "available":
        return "dryup_not_supported_available"
    return "dryup_unavailable"


def _candidate_bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_dryup_bucket(row)].append(row)
    out: dict[str, Any] = {}
    for bucket in (
        "dryup_supported",
        "dryup_not_supported_available",
        "dryup_unavailable",
    ):
        bucket_rows = grouped.get(bucket, [])
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
    qqq_confirmed: list[dict[str, Any]] = []
    dryup_supported: list[dict[str, Any]] = []
    rejected_missing_market = 0
    rejected_qqq_false = 0
    rejected_no_dryup = 0
    rejected_dryup_unavailable = 0

    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in volatility_shadow.EXCLUDED_TICKERS:
            continue
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
            row.update(_volume_context_for_row(snapshot, row))
            all_candidates.append(row)
            if row["qqq_gt_spy20"] is None:
                rejected_missing_market += 1
                continue
            if row["qqq_gt_spy20"] is not True:
                rejected_qqq_false += 1
                continue
            qqq_confirmed.append(row)
            if row["pre_signal_volume_dryup_passed"] is True:
                dryup_supported.append(row)
            else:
                rejected_no_dryup += 1
                if _dryup_bucket(row) == "dryup_unavailable":
                    rejected_dryup_unavailable += 1

    dryup_supported.sort(
        key=lambda row: (
            row["date"],
            row["short_to_long_atr_ratio"],
            -row["candidate_day_rs_vs_spy"],
            -row["dollar_volume"],
            row["ticker"],
        )
    )
    VOLUME_DRYUP_AUDIT[label] = {
        "raw_volatility_candidates": len(all_candidates),
        "qqq_confirmed_candidates": len(qqq_confirmed),
        "dryup_supported_after_qqq_candidates": len(dryup_supported),
        "rejected_qqq_not_leading_spy": rejected_qqq_false,
        "rejected_missing_market_context": rejected_missing_market,
        "rejected_no_volume_dryup_after_qqq": rejected_no_dryup,
        "rejected_volume_dryup_unavailable_after_qqq": rejected_dryup_unavailable,
        "candidate_dates_before_gate": len({row["date"] for row in all_candidates}),
        "candidate_dates_after_qqq_gate": len({row["date"] for row in qqq_confirmed}),
        "candidate_dates_after_dryup_gate": len({row["date"] for row in dryup_supported}),
        "qqq_candidate_volume_dryup_bucket_attribution": _candidate_bucket_summary(
            qqq_confirmed
        ),
    }
    return dryup_supported


def _read_source_exp022() -> dict[str, Any]:
    return json.loads(SOURCE_EXP022_JSON.read_text(encoding="utf-8"))


def _trade_bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    return {
        "trade_count": len(rows),
        "total_pnl": base._round(sum(pnls), 2),
        "avg_pnl": base._round(sum(pnls) / len(pnls), 2) if pnls else None,
        "win_rate": (
            base._round(sum(1 for value in pnls if value > 0) / len(pnls), 6)
            if pnls
            else None
        ),
        "positive_pnl": base._round(sum(value for value in pnls if value > 0), 2),
        "negative_pnl": base._round(sum(value for value in pnls if value < 0), 2),
        "tickers": sorted({str(row.get("ticker") or "").upper() for row in rows}),
    }


def _source_trade_dryup_bucket_attribution() -> dict[str, Any]:
    source = _read_source_exp022()
    aggregate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_window: dict[str, Any] = {}
    for label, trades in source.get("target_trades_by_window", {}).items():
        cfg = source["backtest_protocol"]["windows"][label]
        snapshot = volatility_shadow._load_snapshot(cfg["snapshot"])
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            row = dict(trade)
            row["date"] = str(row.get("signal_date") or row.get("date") or "")
            row.update(_volume_context_for_row(snapshot, row))
            bucket = _dryup_bucket(row)
            grouped[bucket].append(row)
            aggregate[bucket].append({**row, "window": label})
        by_window[label] = {
            bucket: _trade_bucket_summary(rows)
            for bucket, rows in sorted(grouped.items())
        }
    return {
        "source_experiment_id": "exp-20260525-022",
        "source_artifact": base._repo_rel(SOURCE_EXP022_JSON),
        "rule_version": VOLUME_DRYUP_RULE_VERSION,
        "interpretation": (
            "Read-only attribution of exp-022 selected paper trades by whether "
            "prior 10-day volume had dried up versus prior 50-day volume."
        ),
        "by_window": by_window,
        "aggregate": {
            bucket: _trade_bucket_summary(rows)
            for bucket, rows in sorted(aggregate.items())
        },
    }


def _exp022_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    source = _read_source_exp022()
    by_window: dict[str, Any] = {}
    ev_regressed: list[str] = []
    pnl_regressed: list[str] = []
    for label in base.WINDOWS:
        variant_delta = payload["delta_metrics"]["by_window"][label]
        source_delta = source["delta_metrics"]["by_window"][label]
        ev_delta_vs_source = base._round(
            variant_delta["expected_value_score"] - source_delta["expected_value_score"],
            6,
        )
        pnl_delta_vs_source = base._round(
            variant_delta["total_pnl"] - source_delta["total_pnl"],
            2,
        )
        if ev_delta_vs_source < 0:
            ev_regressed.append(label)
        if pnl_delta_vs_source < 0:
            pnl_regressed.append(label)
        by_window[label] = {
            "source_exp022_overlay_ev_delta": source_delta["expected_value_score"],
            "variant_overlay_ev_delta": variant_delta["expected_value_score"],
            "overlay_ev_delta_vs_exp022": ev_delta_vs_source,
            "source_exp022_overlay_pnl_delta": source_delta["total_pnl"],
            "variant_overlay_pnl_delta": variant_delta["total_pnl"],
            "overlay_pnl_delta_vs_exp022": pnl_delta_vs_source,
        }
    source_agg = source["delta_metrics"]["aggregate"]
    variant_agg = payload["delta_metrics"]["aggregate"]
    source_ev = float(source_agg["expected_value_score_delta_sum"])
    variant_ev = float(variant_agg["expected_value_score_delta_sum"])
    source_pnl = float(source_agg["total_pnl_delta_sum"])
    variant_pnl = float(variant_agg["total_pnl_delta_sum"])
    return {
        "source_experiment_id": "exp-20260525-022",
        "source_artifact": base._repo_rel(SOURCE_EXP022_JSON),
        "by_window": by_window,
        "aggregate": {
            "source_exp022_overlay_ev_delta_sum": base._round(source_ev, 6),
            "variant_overlay_ev_delta_sum": base._round(variant_ev, 6),
            "overlay_ev_delta_vs_exp022_sum": base._round(variant_ev - source_ev, 6),
            "overlay_ev_lift_pct_vs_exp022": (
                base._round((variant_ev - source_ev) / abs(source_ev), 6)
                if source_ev
                else None
            ),
            "source_exp022_overlay_pnl_delta_sum": base._round(source_pnl, 2),
            "variant_overlay_pnl_delta_sum": base._round(variant_pnl, 2),
            "overlay_pnl_delta_vs_exp022_sum": base._round(variant_pnl - source_pnl, 2),
            "beats_exp022_ev_by_min_5pct": (
                variant_ev >= source_ev * (1.0 + EXP022_MIN_EV_LIFT)
            ),
            "windows_ev_regressed_vs_exp022": ev_regressed,
            "windows_pnl_regressed_vs_exp022": pnl_regressed,
        },
    }


def _update_gate4_for_exp022(payload: dict[str, Any]) -> dict[str, Any]:
    source_comparison = _exp022_comparison(payload)
    core_gate4 = dict(payload["gate4"])
    target_windows = payload["target_trade_summary"]["windows_with_target_trades"]
    trade_count = int(payload["target_trade_summary"]["total_trade_count"])
    sample_passed = trade_count >= MIN_TARGET_TRADES and len(target_windows) >= MIN_TARGET_WINDOWS
    concentration = core_gate4["target_concentration"]
    comparison_aggregate = source_comparison["aggregate"]
    no_window_regression_vs_exp022 = (
        not comparison_aggregate["windows_ev_regressed_vs_exp022"]
        and not comparison_aggregate["windows_pnl_regressed_vs_exp022"]
    )
    promotion_grade = (
        bool(core_gate4["passed"])
        and sample_passed
        and comparison_aggregate["beats_exp022_ev_by_min_5pct"]
        and no_window_regression_vs_exp022
        and payload["delta_metrics"]["aggregate"]["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and bool(concentration["passed"])
    )
    core_positive = (
        payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"] > 0
        and payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"] > 0
    )
    failed: list[str] = []
    if not core_gate4["passed"]:
        failed.append("did_not_pass_vs_core")
    if not sample_passed:
        failed.append("volume_dryup_variant_sample_too_small")
    if not comparison_aggregate["beats_exp022_ev_by_min_5pct"]:
        failed.append("did_not_beat_exp022_aggregate_ev_by_5pct")
    if comparison_aggregate["windows_ev_regressed_vs_exp022"]:
        failed.append("window_ev_regression_vs_exp022")
    if comparison_aggregate["windows_pnl_regressed_vs_exp022"]:
        failed.append("window_pnl_regression_vs_exp022")
    if payload["delta_metrics"]["aggregate"]["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration["passed"]:
        failed.append("target_concentration_failed")

    payload["source_exp022_comparison"] = source_comparison
    payload["gate4_core_comparison"] = core_gate4
    payload["gate4"] = {
        **core_gate4,
        "passed": promotion_grade,
        "passed_vs_core": bool(core_gate4["passed"]),
        "positive_vs_core": core_positive,
        "promotion_grade_vs_exp022": promotion_grade,
        "accepted_for_attribution_only": core_positive and not promotion_grade,
        "exp022_min_ev_lift": EXP022_MIN_EV_LIFT,
        "beats_exp022_ev_by_min_5pct": comparison_aggregate[
            "beats_exp022_ev_by_min_5pct"
        ],
        "no_ev_or_pnl_window_regression_vs_exp022": no_window_regression_vs_exp022,
        "windows_ev_regressed_vs_exp022": comparison_aggregate[
            "windows_ev_regressed_vs_exp022"
        ],
        "windows_pnl_regressed_vs_exp022": comparison_aggregate[
            "windows_pnl_regressed_vs_exp022"
        ],
        "volume_dryup_variant_trade_count_min": MIN_TARGET_TRADES,
        "volume_dryup_variant_window_count_min": MIN_TARGET_WINDOWS,
        "failed_reasons": failed,
        "comparison_artifact": base._repo_rel(SOURCE_EXP022_JSON),
    }
    payload["rejection_reason"] = None if promotion_grade else "; ".join(failed)
    return payload


def _decision_from_gate(payload: dict[str, Any]) -> str:
    if payload["gate4"]["promotion_grade_vs_exp022"]:
        return "promising_replay_only_vcp_volume_dryup_replacement_gate"
    if payload["gate4"]["accepted_for_attribution_only"]:
        return "observed_only_vcp_volume_dryup_attribution"
    return "rejected_vcp_volume_dryup_gate"


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _update_gate4_for_exp022(payload)
    decision = _decision_from_gate(payload)
    unavailable = sum(
        int(row.get("rejected_volume_dryup_unavailable_after_qqq") or 0)
        for row in VOLUME_DRYUP_AUDIT.values()
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Among exp-20260525-022 QQQ-confirmed volatility-contraction candidates, "
        "pre-signal volume dry-up may identify cleaner supply contraction before "
        "the breakout and improve replacement value."
    )
    payload["change_type"] = "vcp_pre_signal_volume_dryup_attribution_default_off_paper"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 6
    payload["nearby_prior_experiments"] = [
        "exp-20260525-020",
        "exp-20260525-022",
        "exp-20260525-024",
        "exp-20260525-027",
        "exp-20260525-030",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "pit_safe_prior_volume_dryup_on_existing_vcp_candidates"
    payload["source_exp022_selected_trade_volume_dryup_attribution"] = (
        _source_trade_dryup_bucket_attribution()
    )
    payload["volume_dryup_audit"] = VOLUME_DRYUP_AUDIT
    payload["parameters"]["volume_dryup_gate"] = {
        "rule_version": VOLUME_DRYUP_RULE_VERSION,
        "field": CHANGED_VARIABLE,
        "ratio_definition": "avg volume over prior 10 trading days / avg volume over prior 50 trading days",
        "threshold": VOLUME_DRYUP_MAX_RATIO,
        "signal_day_policy": "excluded_from_both_windows",
        "missing_context_policy": "false_not_guessed",
    }
    payload["parameters"]["acceptance"].update(
        {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "aggregate_ev_lift_vs_exp022_min": EXP022_MIN_EV_LIFT,
            "no_ev_or_pnl_regression_vs_exp022_windows": True,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        }
    )
    payload["gate2"]["runtime_fields"].extend(
        [
            "candidate ticker OHLCV Volume for 50 trading days before signal date",
            "candidate ticker OHLCV Volume for 10 trading days before signal date",
            "computed pre_signal_volume_dryup_ratio_10v50",
            "computed pre_signal_volume_dryup_passed",
            "computed volume_dryup_status",
        ]
    )
    payload["gate2"]["volume_dryup_context"] = {
        "rule_version": VOLUME_DRYUP_RULE_VERSION,
        "unavailable_after_qqq_candidate_count": unavailable,
        "audit": VOLUME_DRYUP_AUDIT,
        "passed": True,
    }
    payload["gate3"].update(
        {
            "new_core_filter_added": False,
            "core_survival_unchanged": True,
            "volume_dryup_gated_paper_variant": {
                "selected_trade_count": payload["target_trade_summary"][
                    "total_trade_count"
                ],
                "windows_with_selected_trades": payload["target_trade_summary"][
                    "windows_with_target_trades"
                ],
            },
            "note": (
                "No core filter is added. The volume dry-up condition gates only "
                "the default-off replay paper variant; core signals_generated/"
                "signals_survived remain unchanged."
            ),
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool: existing QQQ-confirmed VCP candidates with "
            "pre-signal volume dry-up may show cleaner supply contraction before "
            "the breakout."
        ),
        "2_history_check": {
            "exp-20260525-020": "Raw top-1 VCP rejected on late_strong/drawdown.",
            "exp-20260525-022": "QQQ > SPY 20d confirmation passed with +1.2493 aggregate EV and +$23,409.56 PnL.",
            "exp-20260525-024": "Accepted default-off forward paper adapter for exp-022.",
            "exp-20260525-027": "Pocket-pivot support was rejected versus exp-022; do not repeat it as a gate.",
            "exp-20260525-030": "Experiment ID occupied by parallel VCP event-context attribution.",
            "exp-20260525-031": "Experiment ID occupied by parallel EPS revision lead-window attribution.",
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three fixed windows; volume-dryup variant "
            "must have >=20 selected trades and at least one in each window, pass "
            "core guardrails, beat exp-022 aggregate EV by >=5%, avoid EV/PnL "
            "regression vs exp-022 in every window, keep max drawdown drift "
            "<=0.50pp, and pass concentration guards."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260525_032_volatility_contraction_volume_dryup.py"
        ),
    }
    payload["why_not_other_changes"] = (
        "Did not retune VCP, QQQ/SPY, rank, notional, hold-days, exits, or "
        "LLM/news. Did not repeat pocket-pivot as a filter because exp-027 "
        "already rejected it versus exp-022."
    )
    if payload["gate4"]["promotion_grade_vs_exp022"]:
        interpretation = (
            "Volume dry-up beat exp-022 under the stricter replacement criteria. "
            "It remains replay-only until a separate adapter/parity update and "
            "activation experiment."
        )
    elif payload["gate4"]["accepted_for_attribution_only"]:
        interpretation = (
            "Volume dry-up was positive versus core but did not beat exp-022. "
            "Treat it as attribution metadata only, not a replacement/allocation gate."
        )
    else:
        interpretation = (
            "Volume dry-up did not clear Gate 4. Do not use it as a VCP "
            "replacement/allocation gate; keep the attribution record only."
        )
    payload["interpretation"] = interpretation
    payload["next_evidence_needed"] = (
        "Use forward paper outcomes or a materially new free-data confirmation "
        "source before revisiting. Do not retune the 10v50 threshold on this "
        "frozen sample."
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
    payload["anti_js"] = "No JavaScript was used."
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | Dry-up EV | dEV | Exp-022 dEV | EV vs 022 | Dry-up PnL d | Exp-022 PnL d | PnL vs 022 | Trades | Dry-up candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        comp = payload["source_exp022_comparison"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {sdev:+.4f} | "
            "{vdev:+.4f} | ${dpnl:+,.2f} | ${sdpnl:+,.2f} | ${vpnl:+,.2f} | "
            "{trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                sdev=comp["source_exp022_overlay_ev_delta"],
                vdev=comp["overlay_ev_delta_vs_exp022"],
                dpnl=delta.get("total_pnl", 0.0),
                sdpnl=comp["source_exp022_overlay_pnl_delta"],
                vpnl=comp["overlay_pnl_delta_vs_exp022"],
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    source_aggregate = payload["source_exp022_comparison"]["aggregate"]
    source_attr = payload["source_exp022_selected_trade_volume_dryup_attribution"][
        "aggregate"
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VCP Volume Dry-Up Confirmation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: require `pre_signal_volume_dryup_ratio_10v50 <= 0.80` "
                "inside the already accepted exp-022 QQQ-confirmed VCP paper sleeve."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- dry-up EV delta vs core: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- exp-022 EV delta vs core: `{source_aggregate['source_exp022_overlay_ev_delta_sum']}`",
            f"- EV delta vs exp-022: `{source_aggregate['overlay_ev_delta_vs_exp022_sum']}` (`{source_aggregate['overlay_ev_lift_pct_vs_exp022']}`)",
            f"- dry-up PnL delta vs core: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- PnL delta vs exp-022: `${source_aggregate['overlay_pnl_delta_vs_exp022_sum']}`",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Exp-022 Selected-Trade Volume Attribution",
            "",
            "```json",
            json.dumps(source_attr, indent=2, sort_keys=True),
            "```",
            "",
            "## Volume Dry-Up Gate Audit",
            "",
            "```json",
            json.dumps(payload["volume_dryup_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only/default-off paper attribution only. No live orders, "
                "watchlists, shared adapter, core entries, ranking, sizing, exits, "
                "LLM/news, or backtester behavior changed."
            ),
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
            "title": "VCP volume dry-up confirmation",
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
                    "source_exp022_comparison": payload["source_exp022_comparison"][
                        "aggregate"
                    ],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
