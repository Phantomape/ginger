"""exp-20260525-030: VCP pre-signal event-context attribution.

This default-off, no-live-capital experiment tests one orthogonal field on top
of the accepted exp-20260525-022 QQQ-confirmed volatility-contraction paper
sleeve: whether the candidate had a same-ticker PIT-safe event snapshot in the
20 available event-snapshot days before the signal date.

It does not retune compression, breakout, QQQ/SPY confirmation, rank, notional,
hold days, exits, LLM/news, universe, or live/default orders. No JavaScript is
used.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base
import exp_20260525_022_volatility_contraction_qqq_confirmed_sleeve as qqq_source
import exp_20260426_volatility_contraction_breakout_shadow as volatility_shadow


EXPERIMENT_ID = "exp-20260525-030"
STEM = "vcp_event_context_attribution"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "pre_signal_event_snapshot_seen_20d"
EVENT_CONTEXT_RULE_VERSION = "vcp_pre_signal_event_snapshot_20d_v1"

REPO_ROOT = base.REPO_ROOT
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
EXP022_MIN_EV_LIFT = 0.05
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EVENT_GATE_AUDIT: dict[str, dict[str, Any]] = {}
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


def _prior_event_snapshot_keys(signal_date: str, lookback: int) -> list[str]:
    signal_key = _date_key(signal_date)
    keys = [key for key in _event_snapshot_paths() if key < signal_key]
    return keys[-int(lookback):]


def pre_signal_event_context(
    ticker: str,
    signal_date: str,
    *,
    lookback_snapshot_days: int = EVENT_LOOKBACK_SNAPSHOT_DAYS,
) -> dict[str, Any]:
    """Return event-snapshot metadata known before the signal date."""
    ticker = str(ticker or "").upper()
    keys = _prior_event_snapshot_keys(signal_date, lookback_snapshot_days)
    events: list[dict[str, Any]] = []
    latest_key = None
    for key in keys:
        snapshot = _load_event_snapshot(key)
        by_ticker = snapshot.get("events_by_ticker") if isinstance(snapshot, dict) else {}
        if not isinstance(by_ticker, dict):
            continue
        rows = [row for row in by_ticker.get(ticker, []) if isinstance(row, dict)]
        if rows:
            latest_key = key
            for row in rows:
                events.append({**row, "snapshot_date": key})
    event_types = sorted({str(row.get("event_type") or "") for row in events if row.get("event_type")})
    event_subtypes = sorted(
        {str(row.get("event_subtype") or "") for row in events if row.get("event_subtype")}
    )
    directions = sorted(
        {
            str(row.get("surprise_direction") or "")
            for row in events
            if row.get("surprise_direction")
        }
    )
    source_confidences = sorted(
        {
            str(row.get("source_confidence") or "")
            for row in events
            if row.get("source_confidence")
        }
    )
    latest_events = [
        row
        for row in events
        if latest_key is not None and row.get("snapshot_date") == latest_key
    ][:5]
    return {
        "event_context_rule_version": EVENT_CONTEXT_RULE_VERSION,
        "pre_signal_event_snapshot_seen_20d": bool(events),
        "pre_signal_event_snapshot_count_20d": len(events),
        "latest_pre_signal_event_snapshot_date": (
            f"{latest_key[:4]}-{latest_key[4:6]}-{latest_key[6:8]}" if latest_key else None
        ),
        "pre_signal_event_type_set_20d": event_types,
        "pre_signal_event_subtype_set_20d": event_subtypes,
        "pre_signal_event_direction_set_20d": directions,
        "pre_signal_event_source_confidence_set_20d": source_confidences,
        "event_context_status": "available" if keys else "no_prior_event_snapshots",
        "event_snapshot_days_checked": len(keys),
        "event_snapshot_lookback_days": int(lookback_snapshot_days),
        "latest_pre_signal_event_titles": [
            (row.get("attributes") or {}).get("title") for row in latest_events
        ],
        "known_at": "before_signal_date_close_event_snapshot_only",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _event_bucket(row: dict[str, Any]) -> str:
    return "event_seen_20d" if row.get("pre_signal_event_snapshot_seen_20d") else "event_quiet_20d"


def _candidate_bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_event_bucket(row)].append(row)
    out: dict[str, Any] = {}
    for bucket in ("event_seen_20d", "event_quiet_20d"):
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
    event_supported: list[dict[str, Any]] = []
    rejected_missing_market = 0
    rejected_qqq_false = 0
    rejected_no_event = 0

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
            row.update(pre_signal_event_context(str(row["ticker"]), str(row["date"])))
            all_candidates.append(row)
            if row["qqq_gt_spy20"] is None:
                rejected_missing_market += 1
                continue
            if row["qqq_gt_spy20"] is not True:
                rejected_qqq_false += 1
                continue
            qqq_confirmed.append(row)
            if row["pre_signal_event_snapshot_seen_20d"] is True:
                event_supported.append(row)
            else:
                rejected_no_event += 1

    event_supported.sort(
        key=lambda row: (
            row["date"],
            row["short_to_long_atr_ratio"],
            -row["candidate_day_rs_vs_spy"],
            -row["dollar_volume"],
            row["ticker"],
        )
    )
    EVENT_GATE_AUDIT[label] = {
        "raw_volatility_candidates": len(all_candidates),
        "qqq_confirmed_candidates": len(qqq_confirmed),
        "event_supported_after_qqq_candidates": len(event_supported),
        "rejected_qqq_not_leading_spy": rejected_qqq_false,
        "rejected_missing_market_context": rejected_missing_market,
        "rejected_no_event_context_after_qqq": rejected_no_event,
        "candidate_dates_before_gate": len({row["date"] for row in all_candidates}),
        "candidate_dates_after_qqq_gate": len({row["date"] for row in qqq_confirmed}),
        "candidate_dates_after_event_gate": len({row["date"] for row in event_supported}),
        "qqq_candidate_event_bucket_attribution": _candidate_bucket_summary(qqq_confirmed),
    }
    return event_supported


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


def _source_trade_event_bucket_attribution() -> dict[str, Any]:
    source = _read_source_exp022()
    by_lookback: dict[str, Any] = {}
    for lookback in (5, 10, 20):
        aggregate: dict[str, list[dict[str, Any]]] = defaultdict(list)
        by_window: dict[str, Any] = {}
        for label, trades in source.get("target_trades_by_window", {}).items():
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for trade in trades:
                row = dict(trade)
                context = pre_signal_event_context(
                    str(row.get("ticker") or ""),
                    str(row.get("signal_date") or row.get("date") or ""),
                    lookback_snapshot_days=lookback,
                )
                row.update(context)
                bucket = (
                    f"event_seen_{lookback}d"
                    if context["pre_signal_event_snapshot_count_20d"]
                    else f"event_quiet_{lookback}d"
                )
                grouped[bucket].append(row)
                aggregate[bucket].append({**row, "window": label})
            by_window[label] = {
                bucket: _trade_bucket_summary(rows)
                for bucket, rows in sorted(grouped.items())
            }
        by_lookback[f"{lookback}_snapshot_days"] = {
            "by_window": by_window,
            "aggregate": {
                bucket: _trade_bucket_summary(rows)
                for bucket, rows in sorted(aggregate.items())
            },
        }
    return {
        "source_experiment_id": "exp-20260525-022",
        "source_artifact": base._repo_rel(SOURCE_EXP022_JSON),
        "rule_version": EVENT_CONTEXT_RULE_VERSION,
        "interpretation": (
            "Read-only attribution of exp-022 selected paper trades by whether "
            "same-ticker event snapshots were present before the signal date."
        ),
        "lookbacks": by_lookback,
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
    )
    failed: list[str] = []
    if not core_gate4["passed"]:
        failed.append("did_not_pass_vs_core")
    if not sample_passed:
        failed.append("event_variant_sample_too_small")
    if not comparison_aggregate["beats_exp022_ev_by_min_5pct"]:
        failed.append("did_not_beat_exp022_aggregate_ev_by_5pct")
    if comparison_aggregate["windows_ev_regressed_vs_exp022"]:
        failed.append("window_ev_regression_vs_exp022")
    if comparison_aggregate["windows_pnl_regressed_vs_exp022"]:
        failed.append("window_pnl_regression_vs_exp022")

    payload["source_exp022_comparison"] = source_comparison
    payload["gate4_core_comparison"] = core_gate4
    payload["gate4"] = {
        **core_gate4,
        "passed": promotion_grade,
        "passed_vs_core": bool(core_gate4["passed"]),
        "promotion_grade_vs_exp022": promotion_grade,
        "accepted_for_attribution_only": bool(core_gate4["passed"]) and not promotion_grade,
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
        "event_variant_trade_count_min": MIN_TARGET_TRADES,
        "event_variant_window_count_min": MIN_TARGET_WINDOWS,
        "failed_reasons": failed,
    }
    payload["rejection_reason"] = None if promotion_grade else "; ".join(failed)
    return payload


def _decision_from_gate(payload: dict[str, Any]) -> str:
    if payload["gate4"]["promotion_grade_vs_exp022"]:
        return "promising_replay_only_vcp_event_context_replacement_gate"
    if payload["gate4"]["accepted_for_attribution_only"]:
        return "observed_only_vcp_event_context_attribution"
    return "rejected_vcp_event_context_gate"


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _update_gate4_for_exp022(payload)
    decision = _decision_from_gate(payload)
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Among exp-20260525-022 QQQ-confirmed volatility-contraction candidates, "
        "same-ticker event snapshots before the breakout may identify breakouts "
        "with a stronger non-price catalyst."
    )
    payload["change_type"] = "vcp_pre_signal_event_context_attribution_default_off_paper"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 5
    payload["nearby_prior_experiments"] = [
        "exp-20260525-020",
        "exp-20260525-022",
        "exp-20260525-024",
        "exp-20260525-027",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "pit_safe_event_snapshot_context_on_existing_vcp_candidates"
    payload["source_exp022_selected_trade_event_attribution"] = (
        _source_trade_event_bucket_attribution()
    )
    payload["event_gate_audit"] = EVENT_GATE_AUDIT
    payload["parameters"]["event_context_gate"] = {
        "rule_version": EVENT_CONTEXT_RULE_VERSION,
        "field": CHANGED_VARIABLE,
        "lookback_event_snapshot_days": EVENT_LOOKBACK_SNAPSHOT_DAYS,
        "date_boundary": "event snapshot date must be strictly before signal date",
        "source": "data/daily/snapshots/events/event_snapshot_YYYYMMDD.json",
        "missing_context_policy": "false_not_guessed",
    }
    payload["parameters"]["acceptance"].update(
        {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "aggregate_ev_lift_vs_exp022_min": EXP022_MIN_EV_LIFT,
            "no_ev_or_pnl_regression_vs_exp022_windows": True,
        }
    )
    payload["gate2"]["runtime_fields"].extend(
        [
            "daily event snapshots before signal date",
            "computed pre_signal_event_snapshot_seen_20d",
            "computed pre_signal_event_snapshot_count_20d",
            "computed latest_pre_signal_event_snapshot_date",
            "computed pre_signal_event_type_set_20d",
            "computed event_context_status",
        ]
    )
    payload["gate2"]["event_context"] = {
        "rule_version": EVENT_CONTEXT_RULE_VERSION,
        "event_snapshot_dir": base._repo_rel(EVENT_SNAPSHOT_DIR),
        "available_snapshot_count": len(_event_snapshot_paths()),
        "lookback_event_snapshot_days": EVENT_LOOKBACK_SNAPSHOT_DAYS,
        "audit": EVENT_GATE_AUDIT,
        "passed": len(_event_snapshot_paths()) > 0,
    }
    payload["gate2"]["passed"] = payload["gate2"]["passed"] and len(_event_snapshot_paths()) > 0
    payload["gate3"].update(
        {
            "new_core_filter_added": False,
            "core_survival_unchanged": True,
            "event_gated_paper_variant": {
                "selected_trade_count": payload["target_trade_summary"][
                    "total_trade_count"
                ],
                "windows_with_selected_trades": payload["target_trade_summary"][
                    "windows_with_target_trades"
                ],
            },
            "note": (
                "No core filter is added. The event condition gates only the "
                "default-off paper variant; core signals_generated/signals_survived "
                "remain unchanged."
            ),
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool: VCP breakouts with recent same-ticker event "
            "context may have better non-price catalyst support."
        ),
        "2_history_check": {
            "exp-20260525-022": "Accepted QQQ-confirmed VCP replay lead.",
            "exp-20260525-024": "Accepted default-off forward paper adapter.",
            "exp-20260525-027": "Rejected pocket-pivot support gate; volume support is metadata only.",
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three fixed windows; event variant must "
            "pass core guardrails, have >=20 selected trades and at least one "
            "trade in each window, beat exp-022 aggregate EV by >=5%, and avoid "
            "EV/PnL regression versus exp-022 in every window."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260525_030_vcp_event_context_attribution.py"
        ),
    }
    payload["why_not_other_changes"] = (
        "Did not retune VCP, QQQ/SPY, rank, notional, hold-days, exits, or "
        "LLM/news. Did not use same-day event snapshots because event timing "
        "inside the signal day is ambiguous; only strictly prior snapshots count."
    )
    if payload["gate4"]["promotion_grade_vs_exp022"]:
        interpretation = (
            "Recent event context beat exp-022 under the stricter replacement "
            "criteria. It remains replay-only until a separate activation experiment."
        )
    elif payload["gate4"]["accepted_for_attribution_only"]:
        interpretation = (
            "Recent event context passed the core comparison but did not beat "
            "exp-022. Treat as attribution only."
        )
    else:
        interpretation = (
            "Recent event context did not clear Gate 4. Do not use event presence "
            "as a VCP replacement/allocation gate; keep it as coverage attribution."
        )
    payload["interpretation"] = interpretation
    payload["next_evidence_needed"] = (
        "Use forward paper outcomes or richer event semantics before revisiting. "
        "Do not promote event absence/presence from this frozen-sample attribution."
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
        "| Window | Before EV | Event EV | dEV | Exp-022 dEV | EV vs 022 | Event PnL d | Exp-022 PnL d | PnL vs 022 | Trades | Event candidates |",
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
    source_attr = payload["source_exp022_selected_trade_event_attribution"]["lookbacks"][
        "20_snapshot_days"
    ]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VCP Event-Context Attribution",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: require `pre_signal_event_snapshot_seen_20d` "
                "inside the already accepted exp-022 QQQ-confirmed VCP paper sleeve."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- event EV delta vs core: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- exp-022 EV delta vs core: `{source_aggregate['source_exp022_overlay_ev_delta_sum']}`",
            f"- EV delta vs exp-022: `{source_aggregate['overlay_ev_delta_vs_exp022_sum']}` (`{source_aggregate['overlay_ev_lift_pct_vs_exp022']}`)",
            f"- event PnL delta vs core: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- PnL delta vs exp-022: `${source_aggregate['overlay_pnl_delta_vs_exp022_sum']}`",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            "",
            "## Exp-022 Selected-Trade Event Attribution",
            "",
            "```json",
            json.dumps(source_attr, indent=2, sort_keys=True),
            "```",
            "",
            "## Event Gate Audit",
            "",
            "```json",
            json.dumps(payload["event_gate_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
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
            "title": "VCP event-context attribution",
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
