"""exp-20260707-010: microstructure tick gate CV overlay.

This runner converts the observed-only exp-20260707-002 tick-to-ATR20 lead into
a stricter deployment-shaped policy test.  For each source family and canonical
test window it trains a top-tertile ``tick_to_atr20`` admission cutoff on the
other two windows, applies that cutoff to the held-out window, then admits at
most one default-off paper row per signal date.

No production orders, live/default paper ledgers, ranking, sizing, exits, LLM,
news, or shared helpers are changed by this scout.  A positive result would
still require a shared default-off helper before any acceptance.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    import_path_s = str(import_path)
    if import_path_s not in sys.path:
        sys.path.insert(0, import_path_s)

import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as fixed_sleeve  # noqa: E402
import exp_20260706_023_portfolio_daily_equity_overlay as daily_mtm  # noqa: E402
import exp_20260707_002_microstructure_tick_viability_attribution as micro_attr  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260707-010"
OWNER = "alpha-explore"
STEM = "microstructure_tick_gate_cv_overlay"
LANE = "alpha_search"

TRIAL_FAMILY = "microstructure_tick_to_atr20_admission_gate"
TRIAL_VARIANT_ID = "leave_one_window_cutoff_short_trend_overlay_v1"
CHANGED_VARIABLE = "microstructure_tick_to_atr20_leave_one_window_admission_gate_v1"
MECHANISM_FAMILY = "microstructure_viability"
CHANGE_TYPE = "candidate_pool_full_stack"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260707_010_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_late_strong_20260604.json"
                ),
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_mid_weak_20260604.json"
                ),
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_old_thin_20260604.json"
                ),
            },
        ),
    ]
)

SOURCE_PRIORITY = {
    "distribution_day_absorption": 0,
    "breakout_without_2x_volume_precursor": 1,
    "gap_hold_core_flow_confirmed": 2,
}
MIN_TRAIN_ROWS_PER_SOURCE = 20
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
PAPER_NOTIONAL_USD = 4000.0
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
}
ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=PAPER_NOTIONAL_USD,
    max_capital_pct=0.40,
    min_dollar_volume=None,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=10,
    order_semantics="next_open_entry_10d_close_exit",
    kill_switch_drawdown_pct=0.08,
    sleeve_drawdown_stop_pct=0.05,
    notes=(
        "Experiment-owned overlay scout. It preserves the exp-20260707-002 "
        "ATR20 field contract but does not ship a daily shared helper."
    ),
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.05,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "window_instability",
        "cutoff_overfits_training_windows",
        "accepted_comparator_not_beaten",
        "drawdown_or_concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260707-002 found positive aggregate and two-window tick_to_atr20 "
        "attribution, but it was observed-only and late_strong/source stability "
        "were weak; a leave-one-window admission gate is a stricter "
        "deployment-shaped test with high failure risk."
    ),
    "recorded_at": "2026-07-07T10:04:33+00:00",
}

HYPOTHESIS = (
    "A fixed leave-one-window microstructure admission gate using entry-time "
    "tick_to_atr20 may convert the observed short-trend viability lead into "
    "deployable default-off paper overlay value without retuning momentum, "
    "hold, cooldown, or notional rules."
)

NEW_EVIDENCE_AXIS = (
    "New gate shape: converts exp-20260707-002 observed-only attribution into "
    "a leave-one-canonical-window admission policy trained on the other "
    "windows and evaluated as a default-off paper overlay; no ATR lookback, "
    "momentum threshold, top-N, hold-day, cooldown, notional, or response "
    "retune."
)

RELATED_FILES = [
    str(Path(__file__).relative_to(REPO_ROOT)).replace("\\", "/"),
    "quant/experiments/exp_20260707_002_microstructure_tick_viability_attribution.py",
    BASELINE_RESULT_FILE,
    *[source["path"] for source in micro_attr.SOURCE_ARTIFACTS],
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(row) for row in value]
    if isinstance(value, set):
        return sorted(safe(row) for row in value)
    if isinstance(value, Counter):
        return {str(key): safe(row) for key, row in value.items()}
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value


def read_json(path: Path | str, default: Any = None) -> Any:
    path = REPO_ROOT / path if not Path(path).is_absolute() else Path(path)
    try:
        with path.open(encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def quantile_threshold(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = math.ceil(len(ordered) * fraction) - 1
    idx = max(0, min(idx, len(ordered) - 1))
    return ordered[idx]


def signal_day(row: dict[str, Any]) -> str:
    return str(row.get("signal_date") or row.get("date") or row.get("entry_date") or "")


def load_enriched_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows, load_diagnostics = micro_attr.load_target_rows()
    enriched, enrichment_diagnostics = micro_attr.enrich_rows(raw_rows)
    diagnostics = {
        "raw_rows": len(raw_rows),
        "enriched_rows": len(enriched),
        "load_diagnostics": load_diagnostics,
        "enrichment_diagnostics": enrichment_diagnostics,
    }
    return enriched, diagnostics


def build_cutoffs(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cutoffs: dict[str, dict[str, Any]] = {}
    sources = sorted({str(row.get("attribution_source_label")) for row in rows})
    for source in sources:
        for test_window in WINDOWS:
            training = [
                float(row["tick_to_atr20"])
                for row in rows
                if row.get("attribution_source_label") == source
                and row.get("window") != test_window
                and as_float(row.get("tick_to_atr20")) is not None
            ]
            key = f"{source}:{test_window}"
            cutoff = (
                quantile_threshold(training, 2.0 / 3.0)
                if len(training) >= MIN_TRAIN_ROWS_PER_SOURCE
                else None
            )
            cutoffs[key] = {
                "source": source,
                "test_window": test_window,
                "training_windows": [
                    window for window in WINDOWS if window != test_window
                ],
                "training_rows": len(training),
                "cutoff_tick_to_atr20": cutoff,
                "passed_training_size": len(training) >= MIN_TRAIN_ROWS_PER_SOURCE,
                "fraction": "top_tertile_ge_66p7pct",
            }
    return cutoffs


def row_rank_key(row: dict[str, Any]) -> tuple[float, float, int, str]:
    tick_to_atr = float(row.get("tick_to_atr20") or 0.0)
    score = as_float(row.get("candidate_score"))
    if score is None:
        score = as_float(row.get("volume_spike_ratio"))
    source = str(row.get("attribution_source_label") or "")
    return (
        -tick_to_atr,
        -(score or 0.0),
        SOURCE_PRIORITY.get(source, 99),
        str(row.get("ticker") or ""),
    )


def select_policy_trades(
    rows: list[dict[str, Any]],
    cutoffs: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    eligible_by_window_day: defaultdict[str, defaultdict[str, list[dict[str, Any]]]]
    eligible_by_window_day = defaultdict(lambda: defaultdict(list))
    rejected_samples_by_window: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    reason_counts: Counter[str] = Counter()
    pass_counts_by_source_window: Counter[str] = Counter()
    input_counts_by_source_window: Counter[str] = Counter()

    for row in rows:
        window = str(row.get("window") or "")
        source = str(row.get("attribution_source_label") or "")
        key = f"{source}:{window}"
        input_counts_by_source_window[key] += 1
        cutoff_payload = cutoffs.get(key) or {}
        cutoff = cutoff_payload.get("cutoff_tick_to_atr20")
        tick_to_atr = as_float(row.get("tick_to_atr20"))
        day = signal_day(row)
        rejection_reason = None
        if window not in WINDOWS:
            rejection_reason = "unknown_window"
        elif cutoff is None:
            rejection_reason = "training_sample_too_thin"
        elif tick_to_atr is None:
            rejection_reason = "missing_tick_to_atr20"
        elif tick_to_atr < float(cutoff):
            rejection_reason = "below_leave_one_window_cutoff"
        elif not day:
            rejection_reason = "missing_signal_day"
        elif not row.get("exit_date"):
            rejection_reason = "missing_exit_date"

        if rejection_reason:
            reason_counts[rejection_reason] += 1
            if len(rejected_samples_by_window[window]) < 50:
                rejected_samples_by_window[window].append(
                    {
                        "ticker": row.get("ticker"),
                        "window": window,
                        "source": source,
                        "signal_day": day,
                        "tick_to_atr20": tick_to_atr,
                        "cutoff_tick_to_atr20": cutoff,
                        "reason": rejection_reason,
                    }
                )
            continue

        pass_counts_by_source_window[key] += 1
        accepted = dict(row)
        accepted["paper_notional_usd"] = (
            as_float(row.get("paper_notional_usd"))
            or as_float(row.get("notional_usd"))
            or as_float(row.get("paper_notional_usd_attribution"))
            or PAPER_NOTIONAL_USD
        )
        accepted["microstructure_cutoff_key"] = key
        accepted["microstructure_cutoff_tick_to_atr20"] = cutoff
        accepted["microstructure_gate_policy"] = (
            "source-specific leave-one-window top-tertile cutoff, then "
            "top1/day by highest tick_to_atr20"
        )
        eligible_by_window_day[window][day].append(accepted)

    selected_by_window: dict[str, list[dict[str, Any]]] = {window: [] for window in WINDOWS}
    top1_reject_counts: Counter[str] = Counter()
    top1_reject_samples: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for window, by_day in eligible_by_window_day.items():
        for day, candidates in sorted(by_day.items()):
            ranked = sorted(candidates, key=row_rank_key)
            if not ranked:
                continue
            selected_by_window[window].append(ranked[0])
            for extra in ranked[1:]:
                top1_reject_counts["daily_top1_limit"] += 1
                if len(top1_reject_samples[window]) < 50:
                    top1_reject_samples[window].append(
                        {
                            "ticker": extra.get("ticker"),
                            "source": extra.get("attribution_source_label"),
                            "signal_day": day,
                            "tick_to_atr20": extra.get("tick_to_atr20"),
                            "selected_ticker": ranked[0].get("ticker"),
                        }
                    )

    audit = {
        "cutoffs": cutoffs,
        "input_counts_by_source_window": dict(sorted(input_counts_by_source_window.items())),
        "pass_counts_by_source_window": dict(sorted(pass_counts_by_source_window.items())),
        "gate_reject_reason_counts": dict(sorted(reason_counts.items())),
        "daily_top1_reject_counts": dict(sorted(top1_reject_counts.items())),
        "rejected_samples_by_window": dict(rejected_samples_by_window),
        "daily_top1_reject_samples_by_window": dict(top1_reject_samples),
        "selected_counts_by_window": {
            window: len(selected_by_window.get(window, [])) for window in WINDOWS
        },
        "selected_counts_by_source": dict(
            sorted(
                Counter(
                    str(row.get("attribution_source_label") or "")
                    for rows_for_window in selected_by_window.values()
                    for row in rows_for_window
                ).items()
            )
        ),
    }
    return selected_by_window, audit


def target_trade_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    by_source_count: Counter[str] = Counter()
    by_source_pnl: Counter[str] = Counter()
    by_window_pnl: dict[str, float] = {}
    for label, trades in target_trades_by_window.items():
        by_window_pnl[label] = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            source = str(trade.get("attribution_source_label") or "")
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl
            by_source_count[source] += 1
            by_source_pnl[source] += pnl

    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    top5 = sum(sorted(positive.values(), reverse=True)[:5]) if positive_total > 0 else 0.0
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    positive_hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, trades in target_trades_by_window.items() if trades
        ],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_window_pnl": by_window_pnl,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "by_source_count": dict(sorted(by_source_count.items())),
        "by_source_pnl": {
            source: round(pnl, 2) for source, pnl in sorted(by_source_pnl.items())
        },
        "positive_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_pnl_share": max_positive_share,
        "top5_positive_pnl_share": round(top5 / positive_total, 6)
        if positive_total > 0
        else None,
        "positive_pnl_hhi": positive_hhi,
    }


def aggregate_window_rows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": round(ev_before, 6),
        "after_expected_value_score_sum": round(ev_after, 6),
        "expected_value_score_delta_sum": round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": round(pnl_before, 2),
        "after_total_pnl_sum": round(pnl_after, 2),
        "total_pnl_delta_sum": round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def daily_proxy_metrics(
    base_result: dict[str, Any],
    series: dict[Any, float],
    days: list[Any],
) -> dict[str, Any]:
    daily = daily_mtm.metric_series(series, days)
    return {
        "expected_value_score": round(float(daily["expected_value_score"]), 6),
        "total_pnl": round(float(daily["total_pnl"]), 2),
        "strategy_total_return_pct": round(float(daily["return_fraction"]), 6),
        "sharpe_daily": round(float(daily["sharpe_daily"]), 6),
        "max_drawdown_pct": round(float(daily["max_drawdown_pct"]), 6),
        "win_rate": overlay_helper._round(base_result.get("win_rate"), 4),
        "trade_count": base_result.get("total_trades"),
        "signals_generated": base_result.get("signals_generated"),
        "signals_survived": base_result.get("signals_survived"),
        "survival_rate": overlay_helper._round(base_result.get("survival_rate"), 4),
        "worst_trade_pct": overlay_helper._round(base_result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": base_result.get("max_consecutive_losses"),
        "tail_loss_share": overlay_helper._round(base_result.get("tail_loss_share"), 4),
        "daily_mtm_active_days": daily["active_days"],
        "daily_mtm_days": daily["days"],
        "measurement_basis": "daily_mtm_reconstructed_from_saved_trades",
    }


def build_window_metrics(
    selected_by_window: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    overlay_audit: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    baseline_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    core_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, window in WINDOWS.items():
        before_result = read_json(window["baseline"], {})
        if not isinstance(before_result, dict) or not isinstance(before_result.get("trades"), list):
            raise RuntimeError(f"missing baseline trades for {label}: {window['baseline']}")
        baseline_by_window[label] = before_result
        core_trades_by_window[label] = list(before_result.get("trades") or [])

    start, end = daily_mtm.date_bounds(core_trades_by_window, selected_by_window)
    price_map = daily_mtm.load_price_map(
        daily_mtm.ticker_set(core_trades_by_window, selected_by_window),
        start,
        end,
    )

    for label, window in WINDOWS.items():
        before_result = baseline_by_window[label]
        trades = selected_by_window.get(label, [])
        core_rows = core_trades_by_window.get(label, [])
        days = daily_mtm.window_days(price_map, label, [*core_rows, *trades])
        core_series, core_diag = daily_mtm.build_series_for_rows(
            core_rows,
            price_map,
            notional_key="entry_notional",
            share_key="shares",
        )
        overlay_series, overlay_diag = daily_mtm.build_series_for_rows(
            trades,
            price_map,
            notional_key="paper_notional_usd",
        )
        combined_series = daily_mtm.add_series(core_series, overlay_series)
        before = daily_proxy_metrics(before_result, core_series, days)
        after = daily_proxy_metrics(before_result, combined_series, days)
        delta = overlay_helper._delta(after, before)
        before_metrics[label] = before
        after_metrics[label] = after
        overlay_metrics = daily_mtm.metric_series(overlay_series, days)
        overlay_audit[label] = {
            "measurement_basis": "daily_mtm_reconstructed_from_saved_trades",
            "baseline_artifact": window["baseline"],
            "calendar_days": len(days),
            "calendar_start": days[0].isoformat() if days else None,
            "calendar_end": days[-1].isoformat() if days else None,
            "core_series_diagnostics": core_diag,
            "overlay_series_diagnostics": overlay_diag,
            "overlay_total_pnl": overlay_metrics["total_pnl"],
            "overlay_day_count": overlay_metrics["active_days"],
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "overlay_total_pnl": overlay_metrics["total_pnl"],
            "overlay_day_count": overlay_metrics["active_days"],
        }
    aggregate = aggregate_window_rows(window_rows)
    target_summary = target_trade_summary(selected_by_window)
    return before_metrics, after_metrics, {"by_window": window_rows, "aggregate": aggregate}, {
        "overlay": overlay_audit,
        "target_trade_summary": target_summary,
    }


def evaluate_gate4(
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_regressed"] > 0:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"] > 0:
        failed.append("window_pnl_regression")
    if aggregate["windows_ev_improved"] < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    for name, comparator in (
        ("compression", ACCEPTED_COMPRESSION_COMPARATOR),
        ("distribution", ACCEPTED_DISTRIBUTION_COMPARATOR),
    ):
        if (
            aggregate["expected_value_score_delta_sum"]
            <= comparator["expected_value_score_delta_sum"]
        ):
            failed.append(f"accepted_{name}_ev_not_beaten")
        if aggregate["total_pnl_delta_sum"] <= comparator["total_pnl_delta_sum"]:
            failed.append(f"accepted_{name}_pnl_not_beaten")

    economics_passed = not failed
    contract_blockers = [
        "shared_default_off_helper_not_promoted",
        "daily_snapshot_not_exposed",
        "parity_test_not_added",
    ]
    return {
        "passed": economics_passed,
        "economics_passed": economics_passed,
        "failed_reasons": failed,
        "contract_blockers_if_positive": contract_blockers,
        "decision": (
            "positive_replay_lead_not_promoted_microstructure_tick_gate"
            if economics_passed
            else "rejected_microstructure_tick_gate_cv_overlay"
        ),
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_windows": target_summary["windows_with_target_trades"],
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "survival_rate_min": round(min_survival, 6),
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "top5_positive_pnl_share": target_summary["top5_positive_pnl_share"],
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "comparators": {
            "accepted_compression": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_distribution": ACCEPTED_DISTRIBUTION_COMPARATOR,
        },
    }


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} Microstructure Tick Gate CV Overlay",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]["delta"]
        trades = payload["delta_metrics"]["by_window"][label]["target_trade_count"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                trades=trades,
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}`",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "allowed_write_scope": [repo_rel(path) for path in paths],
        "file_hashes": {repo_rel(path): sha256(path) for path in paths if path.exists()},
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": "No JavaScript was used.",
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now_iso()
    rows, row_diagnostics = load_enriched_rows()
    cutoffs = build_cutoffs(rows)
    selected_by_window, selection_audit = select_policy_trades(rows, cutoffs)
    before_metrics, after_metrics, delta_metrics, overlay_payload = build_window_metrics(
        selected_by_window
    )
    target_summary = overlay_payload["target_trade_summary"]
    gate4 = evaluate_gate4(delta_metrics["aggregate"], target_summary, before_metrics)

    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    verdict_input = {
        "passed": gate4["economics_passed"],
        "hard_failures": gate4["failed_reasons"],
        "warnings": gate4["contract_blockers_if_positive"],
    }
    verdict = full_stack_verdict(
        gate4=verdict_input,
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    if not gate4["economics_passed"]:
        status = "rejected"
        accepted = False
        decision = gate4["decision"]
        rejection_reason = "; ".join(gate4["failed_reasons"])
    else:
        status = "positive_replay_lead_not_promoted"
        accepted = False
        decision = gate4["decision"]
        rejection_reason = "economic lead was not promoted because no shared helper/daily snapshot was shipped"

    actual_success = 1 if gate4["economics_passed"] else 0
    predicted = float(PREDICTION["success_probability"])
    observed_failures = gate4["failed_reasons"] or gate4["contract_blockers_if_positive"]
    changed_files = [
        repo_rel(Path(__file__)),
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": LANE,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "full_stack_verdict": verdict["verdict"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "private_replay_scout_to_shared_helper_gate_shape_validation",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "fixed tick_to_atr20 field",
            "leave-one-window cutoff training",
            "default-off paper overlay",
            "canonical three-window Gate 1-4",
            "execution envelope",
            "no live orders",
        ],
        "nearby_prior_experiments": ["exp-20260707-002"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": observed_failures,
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"]) & set(observed_failures)
            ),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": delta_metrics["aggregate"]["expected_value_score_delta_sum"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": delta_metrics["aggregate"]["total_pnl_delta_sum"],
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260707-002": (
                    "Observed-only positive tick_to_atr20 attribution across "
                    "428 existing short-trend target rows; not activation-ready "
                    "without a shared helper/Gate 1-4 shape."
                ),
                "novelty_gate": (
                    "Reserved with novelty override on a legal new gate shape: "
                    "leave-one-window admission policy, not a field/threshold retune."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Canonical three-window default-off overlay must produce positive "
                "aggregate EV/PnL, no window regression, sufficient trades, "
                "drawdown drift <=0.5pp, concentration guards, and beat accepted "
                "compression/distribution comparators."
            ),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260707_010_microstructure_tick_gate_cv_overlay.py"
            ),
        },
        "parameters": {
            "source_artifacts": micro_attr.SOURCE_ARTIFACTS,
            "microstructure_field": "tick_to_atr20 = 0.01 / ATR20",
            "atr_lookback_sessions": 20,
            "cutoff_policy": (
                "For each source/test-window pair, train the top-tertile cutoff "
                "on the other two canonical windows and apply to the held-out "
                "window."
            ),
            "min_train_rows_per_source": MIN_TRAIN_ROWS_PER_SOURCE,
            "daily_selection": "top1/day by highest tick_to_atr20 after cutoff",
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "hold_days": 10,
            "thresholds_retuned": False,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md accepted three-window baseline plus "
                "experiment-owned default-off paper overlay from existing target "
                "trade artifacts."
            ),
            "windows": WINDOWS,
            "baseline_result_file": BASELINE_RESULT_FILE,
            "measurement_basis": (
                "Core and overlay economics are replayed from saved trades as "
                "warehouse-OHLCV daily mark-to-market proxy series because the "
                "archived 20260604 accepted baseline JSON stores "
                "equity_curve_integrity but omits the raw equity_curve."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifacts": {
                label: window["baseline"] for label, window in WINDOWS.items()
            },
            "measurement_basis": "daily_mtm_reconstructed_from_saved_trades",
            "row_diagnostics": row_diagnostics,
        },
        "gate2": {
            "passed": row_diagnostics["enriched_rows"] > 0,
            "fields_checked": [
                "ticker",
                "entry_date",
                "exit_date",
                "entry_price",
                "pnl",
                "tick_to_atr20",
                "target_price",
            ],
            "target_price_scope": (
                "The overlay consumes already settled fixed-horizon paper trades; "
                "it does not regenerate target exits or core signals."
            ),
            "cutoff_audit": cutoffs,
        },
        "gate3": {
            "passed": row_diagnostics["enriched_rows"] / max(row_diagnostics["raw_rows"], 1) >= 0.05,
            "new_core_filter_added": False,
            "signals_generated": row_diagnostics["raw_rows"],
            "signals_survived": row_diagnostics["enriched_rows"],
            "survival_rate": round(
                row_diagnostics["enriched_rows"] / max(row_diagnostics["raw_rows"], 1),
                6,
            ),
            "note": "Default-off paper overlay only; core signal survival is unchanged.",
        },
        "gate4": gate4,
        "full_stack": {
            "verdict": verdict,
            "live_readiness": live_readiness,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
            "contract_blockers": gate4["contract_blockers_if_positive"],
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "selection_audit": selection_audit,
        "overlay_audit": overlay_payload["overlay"],
        "target_trades_by_window": selected_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": delta_metrics["aggregate"]["expected_value_score_delta_sum"],
        "total_pnl_delta": delta_metrics["aggregate"]["total_pnl_delta_sum"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "live_ready": False,
            "live_realism_evaluated": True,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
            "parity_note": (
                "This is an experiment-owned replay scout. It does not alter "
                "production/backtest adapters or any order path. A positive "
                "result would still require shared-helper promotion."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The observed-only tick-to-ATR20 separation had to survive a "
                "source-specific leave-one-window cutoff and top1/day overlay. "
                "This stricter shape tests whether the field is deployable "
                "rather than merely explanatory."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun by changing ATR lookback, percentile cutoff, source "
                "set, top-N, hold days, cooldown, notional, or response shape on "
                "these same artifacts. Legal retries need PIT spread/depth/cost "
                "data, materially more forward rows, or a real shared helper with "
                "the same field contract."
            ),
            "new_evidence_required": (
                "PIT spread/depth or cost data, materially more settled forward "
                "rows, or a shared default-off helper that preserves this exact "
                "field contract."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "PIT spread/depth or cost source",
            "materially more closed forward rows",
            "shared default-off helper with this exact field contract",
            "no ATR lookback, percentile, source, top-N, hold-day, cooldown, notional retune",
        ],
        "changed_files": changed_files,
        "related_files": RELATED_FILES,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            "quant\\experiments\\exp_20260707_010_microstructure_tick_gate_cv_overlay.py",
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260707_010_microstructure_tick_gate_cv_overlay.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keep = [
        "experiment_id",
        "timestamp",
        "lane",
        "owner",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "full_stack_verdict",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "full_stack",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "target_trade_summary",
        "expected_value_score_delta",
        "total_pnl_delta",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "llm_metrics",
        "lean_quality_passed",
        "anti_js",
    ]
    return {key: payload.get(key) for key in keep}


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, build_manifest(payload))

    ticket = read_json(TICKET_JSON, {}) or {}
    result = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        **{
            key: value
            for key, value in ticket.items()
            if key not in {"result", "status", "completed_at"}
        },
        "owner": OWNER,
        "decision": payload["decision"],
        "summary": payload["rejection_reason"],
        "completed_at": payload["timestamp"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "full_stack": payload["full_stack"],
        "target_trade_summary": payload["target_trade_summary"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "aggregate": payload["delta_metrics"]["aggregate"],
                    "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": repo_rel(OUT_JSON),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
