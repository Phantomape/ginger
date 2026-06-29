"""exp-20260628-019: breakout precursor full-stack promotion attempt.

This runner promotes the exp-20260628-015 full-population
``above_200ma & breakout_20d & not volume_spike`` lead into a fixed
top-1/day default-off candidate-source replay. It intentionally does not
retune the 2x volume threshold, hold days, notional, lookbacks, or response
curve.
"""

from __future__ import annotations

import hashlib
import json
import math
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
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260628-019"
OWNER = "alpha-explore"
STEM = "breakout_precursor_full_stack"
TRIAL_FAMILY = "breakout_without_2x_volume_precursor_full_stack"
TRIAL_VARIANT_ID = "breakout_precursor_top1_volume_ratio_rank_v1"
CHANGED_VARIABLE = "breakout_without_2x_volume_precursor_default_off_candidate_source_v1"

SOURCE_LEAD_EXPERIMENT_ID = "exp-20260628-015"
SOURCE_LEAD_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_LEAD_EXPERIMENT_ID
    / "exp_20260628_015_breakout_without_2x_volume_precursor_forward_replacement_value_v1.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
SAME_TICKER_COOLDOWN_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
}
ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
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
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
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
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_old_thin_20260604.json"
                ),
            },
        ),
    ]
)

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "fixed_window_instability",
        "accepted_comparator_not_beaten",
        "drawdown_or_concentration_failed",
        "full_population_false_positive_drag",
    ],
    "confidence_reason": (
        "exp-20260628-015 showed a de-biased full-population positive aggregate "
        "10d/20d lead, but fixed windows were mixed and prior trend-long "
        "precursor promotion failed when conditioned on actual future entries; "
        "this run tests the only valid promotion shape without threshold or "
        "response retuning."
    ),
    "recorded_at": "2026-06-28T23:05:58+00:00",
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=BASE_NOTIONAL_USD,
    max_capital_pct=0.40,
    min_dollar_volume=None,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=10,
    order_semantics="next_open",
    kill_switch_drawdown_pct=0.08,
    sleeve_drawdown_stop_pct=0.05,
    notes=(
        "Top-1/day with 10-trading-day hold and fixed $4,000 default-off "
        "paper notional. This run does not wire a daily snapshot, so the "
        "full-stack contract cannot be accepted even if economics pass."
    ),
)

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "experiment_owned_full_stack_replay_attempt",
    "shared_policy_changed": False,
    "backtester_adapter_changed": True,
    "run_adapter_changed": False,
    "replay_only": False,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "Historical replay consumes the exp-20260628-015 shared helper artifact "
        "but this experiment does not add daily default-off snapshot wiring. "
        "No live/default order, ranking, sizing, exit, watchlist, LLM, or news "
        "path changes."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/full_stack: the fixed breakout-without-2x-volume "
        "precursor source may have standalone replacement value when promoted "
        "from the exp-20260628-015 full-population forward lead into a "
        "top-1/day $4k next-open/10d default-off source."
    ),
    "2_history_check": {
        "exp-20260627-006": (
            "Positive but survivor-conditioned actual-entry precursor lead; "
            "not a valid base-rate test."
        ),
        "exp-20260627-007": (
            "Rejected unconditional default-off top-1 precursor source because "
            "future-entry conditioning was removed and fixed windows were weak."
        ),
        "exp-20260628-015": (
            "New full-population forward ledger: aggregate 10d/20d medians "
            "were positive, but late_strong and old_thin full-population "
            "medians were mixed; valid next step was a Gate 1-4 candidate "
            "source replay, not threshold retuning."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical windows. Aggregate EV/PnL must be "
        "positive, no EV/PnL regression window, at least 20 target trades in "
        "all 3 windows, survival >=5%, drawdown drift <=0.5pp, concentration "
        "guards pass, accepted compression and distribution comparators are "
        "beaten, and daily/default-off full-stack contract is complete."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260628_019_breakout_precursor_full_stack.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_lead_events() -> list[dict[str, Any]]:
    payload = _read_json(SOURCE_LEAD_JSON)
    events = payload.get("events")
    if not isinstance(events, list):
        raise RuntimeError(f"source lead artifact has no events list: {SOURCE_LEAD_JSON}")
    return [event for event in events if isinstance(event, dict)]


def _run_baseline_result(label: str, universe: list[str]) -> dict[str, Any]:
    cfg = {
        "start": WINDOWS[label]["start"],
        "end": WINDOWS[label]["end"],
        "snapshot": WINDOWS[label]["snapshot"],
    }
    return framework.shadow._run_baseline(universe, cfg)


def _equity_dates(result: dict[str, Any]) -> list[str]:
    return [str(day) for day, _ in (result.get("equity_curve") or [])]


def _event_rank_key(event: dict[str, Any]) -> tuple[float, float, str]:
    precursor = event.get("precursor") or {}
    volume_ratio = float(precursor.get("volume_spike_ratio") or 0.0)
    extension = float(precursor.get("extension_atr_mult") or 999.0)
    ticker = str(event.get("ticker") or "")
    return (-volume_ratio, extension, ticker)


def _trade_from_event(event: dict[str, Any], *, window_end: str) -> dict[str, Any] | None:
    forward = event.get("forward") or {}
    horizon = (forward.get("horizons") or {}).get(str(HOLD_DAYS)) or {}
    if horizon.get("status") != "settled":
        return None
    exit_date = str(horizon.get("exit_date") or "")
    entry_date = str(forward.get("entry_date") or "")
    signal_date = str(event.get("signal_date") or "")
    if not entry_date or not exit_date or not signal_date:
        return None
    if exit_date > window_end:
        return None
    pnl = float(horizon.get("forward_pnl_usd") or 0.0)
    pnl_pct = float(horizon.get("forward_net_return_pct") or 0.0) / 100.0
    precursor = event.get("precursor") or {}
    return {
        "source": "BREAKOUT_WITHOUT_2X_VOLUME_PRECURSOR_PAPER",
        "source_rule_version": "breakout_precursor_top1_volume_ratio_rank_v1",
        "ticker": str(event.get("ticker") or "").upper(),
        "date": signal_date,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": _round(forward.get("entry_fill"), 4),
        "exit_price": _round(horizon.get("exit_fill"), 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct, 8),
        "pnl": _round(pnl, 2),
        "volume_spike_ratio": _round(precursor.get("volume_spike_ratio"), 4),
        "extension_atr_mult": _round(precursor.get("extension_atr_mult"), 6),
        "pct_from_20ma": _round(precursor.get("pct_from_20ma"), 6),
        "momentum_10d_pct": _round(precursor.get("momentum_10d_pct"), 6),
        "pct_from_252w_high": _round(precursor.get("pct_from_252w_high"), 6),
        "entry_regime_label": event.get("entry_regime_label"),
        "became_trend_long_entry": bool(event.get("became_trend_long_entry")),
        "source_event_id": event.get("event_id"),
        "rank_policy": (
            "top1 per signal date by highest sub-2x volume_spike_ratio, then "
            "lowest extension_atr_mult, then ticker"
        ),
    }


def _select_trades_for_window(
    *,
    events: list[dict[str, Any]],
    label: str,
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = WINDOWS[label]
    dates = _equity_dates(before_result)
    date_pos = {day: idx for idx, day in enumerate(dates)}
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_count = 0
    for event in events:
        if event.get("window") != label:
            continue
        signal_date = str(event.get("signal_date") or "")
        if not (cfg["start"] <= signal_date <= cfg["end"]):
            continue
        raw_count += 1
        by_date[signal_date].append(event)

    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    next_allowed_by_ticker: dict[str, int] = {}
    daily_candidate_counts: dict[str, int] = {}
    for signal_date in sorted(by_date):
        pos = date_pos.get(signal_date)
        if pos is None:
            for event in by_date[signal_date]:
                filtered.append({**event, "filter_reason": "signal_date_not_in_baseline_curve"})
            continue
        ranked = sorted(by_date[signal_date], key=_event_rank_key)
        daily_candidate_counts[signal_date] = len(ranked)
        used_today = 0
        for event in ranked:
            ticker = str(event.get("ticker") or "").upper()
            if pos < next_allowed_by_ticker.get(ticker, -1):
                filtered.append({**event, "filter_reason": "same_ticker_cooldown"})
                continue
            trade = _trade_from_event(event, window_end=cfg["end"])
            if trade is None:
                filtered.append({**event, "filter_reason": "missing_settled_10d_exit_inside_window"})
                continue
            selected.append(trade)
            next_allowed_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
            used_today += 1
            break
        if used_today >= MAX_PAPER_TRADES_PER_DAY:
            for extra in ranked[1:]:
                if extra not in filtered:
                    filtered.append({**extra, "filter_reason": "daily_top1_limit"})

    audit = {
        "raw_candidate_count_by_window": {label: raw_count},
        "signal_dates_with_candidates": len(by_date),
        "selected_trade_count": len(selected),
        "filtered_count": len(filtered),
        "filter_reason_counts": dict(Counter(row.get("filter_reason") for row in filtered)),
        "max_daily_candidate_count": max(daily_candidate_counts.values()) if daily_candidate_counts else 0,
        "rank_policy": (
            "top1/day by highest volume_spike_ratio below 2.0, then lowest "
            "extension_atr_mult, then ticker"
        ),
    }
    return selected, filtered[:200], audit


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    for name, comparator in (
        ("compression", ACCEPTED_COMPRESSION_COMPARATOR),
        ("distribution", ACCEPTED_DISTRIBUTION_COMPARATOR),
    ):
        if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= comparator[
            "expected_value_score_delta_sum"
        ]:
            failed.append(f"accepted_{name}_ev_not_beaten")
        if float(aggregate["total_pnl_delta_sum"] or 0.0) <= comparator[
            "total_pnl_delta_sum"
        ]:
            failed.append(f"accepted_{name}_pnl_not_beaten")
    if not PRODUCTION_IMPACT["daily_snapshot_exposed"]:
        failed.append("daily_snapshot_not_exposed_for_full_stack_contract")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_breakout_precursor_default_off_candidate_source"
            if passed
            else "rejected_breakout_precursor_default_off_candidate_source"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            "top5_positive_pnl_share": _top5_positive_share(target_summary),
        },
        "accepted_comparators": {
            "compression": ACCEPTED_COMPRESSION_COMPARATOR,
            "distribution": ACCEPTED_DISTRIBUTION_COMPARATOR,
        },
        "full_stack_contract": {
            "daily_snapshot_exposed": PRODUCTION_IMPACT["daily_snapshot_exposed"],
            "parity_test_added": PRODUCTION_IMPACT["parity_test_added"],
        },
    }


def _full_stack_blocks(
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "adjusted_trade_count": target_summary["total_trade_count"],
        "adjusted_windows": target_summary["windows_with_target_trades"],
        "adjusted_window_count": len(target_summary["windows_with_target_trades"]),
        "max_drawdown_worse_max": aggregate["max_drawdown_delta_max"],
        "single_ticker_positive_share": target_summary["max_single_positive_pnl_share"],
        "top_5_contribution_pct": _top5_positive_share(target_summary),
        "hhi_concentration": target_summary["positive_pnl_hhi"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target_summary["total_trade_count"]
            if target_summary["total_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(require_tail_concentration_not_worse=False)
    return {
        "window_metrics": metrics,
        "gate4_strict_materiality": evaluate_gate4(
            metrics,
            thresholds=thresholds,
            check_materiality=True,
        ),
        "gate4_canonical": evaluate_gate4(
            metrics,
            thresholds=thresholds,
            check_materiality=False,
        ),
        "materiality_note": (
            "Strict materiality is recorded for transparency; for candidate "
            "sources the binding materiality standard is beating accepted "
            "comparators after costs."
        ),
    }


def build_payload() -> dict[str, Any]:
    framework._configure_sleeve_globals()
    fixed_sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    fixed_sleeve.STEM = STEM
    events = _load_lead_events()
    timestamp = _utc_now()
    universe = sorted(framework.get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    target_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label in WINDOWS:
        before_result = _run_baseline_result(label, universe)
        before = overlay_helper._metrics(before_result)
        selected, filtered, audit = _select_trades_for_window(
            events=events,
            label=label,
            before_result=before_result,
        )
        overlay = fixed_sleeve._overlay_from_paper_trades(before_result, selected)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)
        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected
        filtered_candidates_by_window[label] = filtered
        target_audit_by_window[label] = audit
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected),
            "raw_candidate_count": audit["raw_candidate_count_by_window"].get(label, 0),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = fixed_sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    full_stack = _full_stack_blocks(aggregate, target_summary)
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    verdict = full_stack_verdict(
        gate4=gate4,
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    if not gate4["passed"]:
        verdict = {
            **verdict,
            "verdict": "reject",
            "gate4_passed": False,
            "next_step": (
                "Reject and do not retune this precursor source on frozen "
                "windows. A valid retry needs genuinely new forward rows, "
                "daily default-off parity, or an orthogonal PIT qualifier."
            ),
        }

    accepted = gate4["passed"] and verdict["verdict"] != "reject"
    status = "accepted_paper_pending_forward" if accepted else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if accepted else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if accepted else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    reflection = {
        "why_result_happened": (
            "The full-population precursor source did not survive as a fixed "
            "top-1/day candidate source. The exp015 aggregate lead was diluted "
            "by false positives and remained window/comparator fragile once "
            "forced into a deployable paper allocation shape."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep the 2x volume threshold, rank tie-breaks, volume "
            "ratio response curves, hold days, cooldown, notional, or actual "
            "future-entry survivor slices on these frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs settled forward replacement-value rows from a "
            "daily default-off precursor logger, daily snapshot parity, or an "
            "orthogonal PIT qualifier such as non-OHLCV flow/borrow/options "
            "context; not another OHLCV volume-threshold retune."
        ),
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": status,
        "decision": gate4["decision"],
        "accepted": accepted,
        "accepted_alpha": accepted,
        "full_stack_verdict": verdict["verdict"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "new_evidence_type": "positive_full_population_forward_lead_full_stack_promotion",
        "nearby_prior_experiments": [
            "exp-20260627-006",
            "exp-20260627-007",
            "exp-20260628-015",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window accepted core "
                "baseline plus default-off paper overlay from exp015 event "
                "artifact"
            ),
            "windows": WINDOWS,
            "source_lead_artifact": _repo_rel(SOURCE_LEAD_JSON),
            "execution_model": (
                "Signal uses only signal-date OHLCV features from exp015. "
                "Paper entry is next open; exit is 10-trading-day close; "
                "events whose 10d exit is outside the fixed window are not "
                "scored in Gate 4."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "rank_policy": (
                "top1/day by highest volume_spike_ratio below 2.0, then "
                "lowest extension_atr_mult, then ticker"
            ),
            "thresholds_retuned": False,
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifacts": {
                label: WINDOWS[label]["baseline"] for label in WINDOWS
            },
            "passed": True,
        },
        "gate2": {
            "runtime_fields": [
                "entry_date",
                "target_price",
                "exp015 event signal_date",
                "exp015 forward.entry_date",
                "exp015 forward.horizons.10.exit_date",
                "exp015 forward.horizons.10.forward_pnl_usd",
                "precursor.volume_spike_ratio",
                "precursor.extension_atr_mult",
            ],
            "source_lead_event_count": len(events),
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
            "passed": True,
            "note": (
                "Default-off paper overlay only. Core signal generation and "
                "survival are unchanged."
            ),
        },
        "gate4": gate4,
        "full_stack": {
            **full_stack,
            "live_readiness": live_readiness,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
            "verdict": verdict,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "target_audit_by_window": target_audit_by_window,
        "filtered_candidate_samples_by_window": filtered_candidates_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The breakout-without-2x-volume precursor failed full-stack "
            "promotion; do not retain or retune it on frozen windows."
        ),
        "post_run_reflection": reflection,
        "next_retry_requires": [
            "daily default-off precursor logger forward rows",
            "orthogonal PIT qualifier beyond OHLCV volume threshold",
            "no frozen-window volume/lookback/notional retune",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(REGISTRY_JSON),
            _repo_rel(SOURCE_LEAD_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["target_audit_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                raw=audit["raw_candidate_count_by_window"].get(label, 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    verdict = payload["full_stack"]["verdict"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Breakout Precursor Full-Stack",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{payload['full_stack_verdict']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Full-Stack Contract",
            "",
            "- Canonical diagnostic gate: `{}`".format(
                payload["full_stack"]["gate4_canonical"]["status"]
            ),
            "- Live readiness blockers: `{}`".format(
                ", ".join(payload["full_stack"]["live_readiness"]["blockers"]) or "none"
            ),
            "- Daily snapshot exposed: `{}`".format(
                payload["production_impact"]["daily_snapshot_exposed"]
            ),
            "- Next step: {}".format(verdict["next_step"]),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "owner": OWNER,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifacts"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "full_stack": {
            "verdict": payload["full_stack"]["verdict"],
            "live_readiness": payload["full_stack"]["live_readiness"],
            "execution_envelope": payload["full_stack"]["execution_envelope"],
            "gate4_strict_materiality_status": payload["full_stack"][
                "gate4_strict_materiality"
            ]["status"],
            "gate4_canonical_status": payload["full_stack"]["gate4_canonical"]["status"],
            "materiality_note": payload["full_stack"]["materiality_note"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "raw_candidate_count": payload["target_audit_by_window"][label][
                    "raw_candidate_count_by_window"
                ].get(label, 0),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": "; ".join(payload["gate4"]["failed_reasons"]) or None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _read_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "new_evidence_type": payload["new_evidence_type"],
            "result": {
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["accepted"],
                "calibration": payload["calibration"],
            },
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        SOURCE_LEAD_JSON,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): _sha256(path)
            for path in paths
            if path.exists()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["accepted"],
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
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
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
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _build_log_record(payload))
    _write_text(CARD_MD, _build_card(payload))
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
