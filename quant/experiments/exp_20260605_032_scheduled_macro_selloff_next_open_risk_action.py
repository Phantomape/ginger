"""exp-20260605-032: scheduled macro selloff next-open risk action.

Replay-only alpha search. This extends the rejected NFP-only selloff action
test by broadening the event calendar to official scheduled CPI, FOMC, and NFP
release/decision dates. The causal variable is only the event-family expansion;
selloff thresholds, action proxy, notional, hold period, costs, and slippage are
kept fixed from exp-20260605-030.

The action waits until the next open after a scheduled macro event day closes in
a SPY/QQQ selloff. Long QQQ represents adding beta; short QQQ represents
reducing or hedging beta. This changes no production code or live/default
orders. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260605-032"
STEM = "scheduled_macro_selloff_next_open_risk_action"
TRIAL_FAMILY = "scheduled_macro_selloff_next_open_risk_action"
TRIAL_VARIANT_ID = "scheduled_macro_cpi_fomc_nfp_selloff_rebound_v1"
CHANGED_VARIABLE = "scheduled_macro_calendar_event_family_expansion_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_032_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"exp_20260605_032_{STEM}_aggregate_before.json"
AFTER_JSON = OUT_DIR / f"exp_20260605_032_{STEM}_aggregate_after.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASE_NOTIONAL_USD = 20_000.0
HOLD_DAYS = 3
SELL_OFF_QQQ_RETURN = -0.010
SELL_OFF_SPY_RETURN = -0.0075
MIN_TARGET_EVENTS = 8
MIN_TARGET_WINDOWS = 3
MIN_EV_DELTA_PCT = 0.10
MAX_DRAWDOWN_WORSE = 0.005

ACTION_ADD_BETA = "add_beta_long_qqq"
ACTION_REDUCE_BETA = "reduce_beta_short_qqq"
ACTIONS = (ACTION_ADD_BETA, ACTION_REDUCE_BETA)

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

MACRO_EVENTS = [
    {"date": "2024-10-04", "family": "NFP", "label": "Sep 2024 Employment Situation"},
    {"date": "2024-10-10", "family": "CPI", "label": "Sep 2024 CPI"},
    {"date": "2024-11-01", "family": "NFP", "label": "Oct 2024 Employment Situation"},
    {"date": "2024-11-07", "family": "FOMC", "label": "Nov 2024 FOMC decision"},
    {"date": "2024-11-13", "family": "CPI", "label": "Oct 2024 CPI"},
    {"date": "2024-12-06", "family": "NFP", "label": "Nov 2024 Employment Situation"},
    {"date": "2024-12-11", "family": "CPI", "label": "Nov 2024 CPI"},
    {"date": "2024-12-18", "family": "FOMC", "label": "Dec 2024 FOMC decision"},
    {"date": "2025-01-10", "family": "NFP", "label": "Dec 2024 Employment Situation"},
    {"date": "2025-01-15", "family": "CPI", "label": "Dec 2024 CPI"},
    {"date": "2025-01-29", "family": "FOMC", "label": "Jan 2025 FOMC decision"},
    {"date": "2025-02-07", "family": "NFP", "label": "Jan 2025 Employment Situation"},
    {"date": "2025-02-12", "family": "CPI", "label": "Jan 2025 CPI"},
    {"date": "2025-03-07", "family": "NFP", "label": "Feb 2025 Employment Situation"},
    {"date": "2025-03-12", "family": "CPI", "label": "Feb 2025 CPI"},
    {"date": "2025-03-19", "family": "FOMC", "label": "Mar 2025 FOMC decision"},
    {"date": "2025-04-04", "family": "NFP", "label": "Mar 2025 Employment Situation"},
    {"date": "2025-04-10", "family": "CPI", "label": "Mar 2025 CPI"},
    {"date": "2025-05-02", "family": "NFP", "label": "Apr 2025 Employment Situation"},
    {"date": "2025-05-07", "family": "FOMC", "label": "May 2025 FOMC decision"},
    {"date": "2025-05-13", "family": "CPI", "label": "Apr 2025 CPI"},
    {"date": "2025-06-06", "family": "NFP", "label": "May 2025 Employment Situation"},
    {"date": "2025-06-11", "family": "CPI", "label": "May 2025 CPI"},
    {"date": "2025-06-18", "family": "FOMC", "label": "Jun 2025 FOMC decision"},
    {"date": "2025-07-03", "family": "NFP", "label": "Jun 2025 Employment Situation"},
    {"date": "2025-07-15", "family": "CPI", "label": "Jun 2025 CPI"},
    {"date": "2025-07-30", "family": "FOMC", "label": "Jul 2025 FOMC decision"},
    {"date": "2025-08-01", "family": "NFP", "label": "Jul 2025 Employment Situation"},
    {"date": "2025-08-12", "family": "CPI", "label": "Jul 2025 CPI"},
    {"date": "2025-09-05", "family": "NFP", "label": "Aug 2025 Employment Situation"},
    {"date": "2025-09-11", "family": "CPI", "label": "Aug 2025 CPI"},
    {"date": "2025-09-17", "family": "FOMC", "label": "Sep 2025 FOMC decision"},
    {"date": "2025-10-03", "family": "NFP", "label": "Sep 2025 Employment Situation"},
    {"date": "2025-10-29", "family": "FOMC", "label": "Oct 2025 FOMC decision"},
    {"date": "2025-11-07", "family": "NFP", "label": "Oct 2025 Employment Situation"},
    {"date": "2025-12-05", "family": "NFP", "label": "Nov 2025 Employment Situation"},
    {"date": "2025-12-10", "family": "FOMC", "label": "Dec 2025 FOMC decision"},
    {"date": "2025-12-18", "family": "CPI", "label": "Nov 2025 CPI"},
    {"date": "2026-01-09", "family": "NFP", "label": "Dec 2025 Employment Situation"},
    {"date": "2026-01-13", "family": "CPI", "label": "Dec 2025 CPI"},
    {"date": "2026-01-28", "family": "FOMC", "label": "Jan 2026 FOMC decision"},
    {"date": "2026-02-06", "family": "NFP", "label": "Jan 2026 Employment Situation"},
    {"date": "2026-02-13", "family": "CPI", "label": "Jan 2026 CPI"},
    {"date": "2026-03-06", "family": "NFP", "label": "Feb 2026 Employment Situation"},
    {"date": "2026-03-11", "family": "CPI", "label": "Feb 2026 CPI"},
    {"date": "2026-03-18", "family": "FOMC", "label": "Mar 2026 FOMC decision"},
    {"date": "2026-04-03", "family": "NFP", "label": "Mar 2026 Employment Situation"},
    {"date": "2026-04-10", "family": "CPI", "label": "Mar 2026 CPI"},
]

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_macro_selloff_sample",
        "aggregate_ev_delta_not_gt_10pct",
        "window_regression",
        "macro_event_proxy_overfit",
    ],
    "confidence_reason": (
        "NFP-only add-beta improved all three windows but failed the strict "
        "risk-allocation EV gate with five target events. CPI/FOMC/NFP expands "
        "the official scheduled macro event surface without retuning thresholds "
        "or hold period."
    ),
    "recorded_at": "2026-06-05T20:08:42Z",
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
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter exposing the same official CPI, "
        "FOMC, and NFP calendar, close-of-day SPY/QQQ selloff test, next-open "
        "QQQ beta action, hold period, cost/slippage model, duplicate-date "
        "dedupe rule, and no-live-order boundary in backtest and daily production."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _value(row: dict[str, Any], key: str) -> float | None:
    return shadow._value(row, key)


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = _value(rows[idx - 1], "Close")
    close = _value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _macro_calendar() -> "OrderedDict[str, dict[str, Any]]":
    grouped: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for event in sorted(MACRO_EVENTS, key=lambda row: (row["date"], row["family"])):
        row = grouped.setdefault(
            event["date"],
            {"date": event["date"], "families": [], "labels": []},
        )
        row["families"].append(event["family"])
        row["labels"].append(event["label"])
    return grouped


def _macro_selloff_context(
    snapshot: dict[str, list[dict[str, Any]]],
    event: dict[str, Any],
    label: str,
) -> dict[str, Any] | None:
    event_date = str(event["date"])
    spy_rows = shadow._series(snapshot, "SPY")
    qqq_rows = shadow._series(snapshot, "QQQ")
    spy_idx = shadow._row_index(spy_rows).get(event_date)
    qqq_idx = shadow._row_index(qqq_rows).get(event_date)
    if spy_idx is None or qqq_idx is None:
        return None
    spy_return = _daily_return(spy_rows, spy_idx)
    qqq_return = _daily_return(qqq_rows, qqq_idx)
    if spy_return is None or qqq_return is None:
        return None
    triggered = spy_return <= SELL_OFF_SPY_RETURN or qqq_return <= SELL_OFF_QQQ_RETURN
    return {
        "window": label,
        "event_date": event_date,
        "event_families": event["families"],
        "event_labels": event["labels"],
        "spy_event_day_return": round(spy_return, 6),
        "qqq_event_day_return": round(qqq_return, 6),
        "triggered": triggered,
        "trigger_rule": (
            f"SPY <= {SELL_OFF_SPY_RETURN:.4f} or QQQ <= {SELL_OFF_QQQ_RETURN:.4f}"
        ),
    }


def _qqq_action_trade(
    snapshot: dict[str, list[dict[str, Any]]],
    context: dict[str, Any],
    action: str,
) -> dict[str, Any] | None:
    qqq_rows = shadow._series(snapshot, "QQQ")
    idx = shadow._row_index(qqq_rows).get(str(context["event_date"]))
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + HOLD_DAYS
    if entry_idx >= len(qqq_rows) or exit_idx >= len(qqq_rows):
        return None
    entry_open = _value(qqq_rows[entry_idx], "Open")
    exit_close = _value(qqq_rows[exit_idx], "Close")
    if entry_open is None or exit_close is None:
        return None
    if action == ACTION_ADD_BETA:
        entry_price = apply_slippage(entry_open, SLIPPAGE_BPS_ENTRY, "buy")
        exit_price = apply_slippage(exit_close, SLIPPAGE_BPS_TARGET, "sell")
        pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    elif action == ACTION_REDUCE_BETA:
        entry_price = apply_slippage(entry_open, SLIPPAGE_BPS_TARGET, "sell")
        exit_price = apply_slippage(exit_close, SLIPPAGE_BPS_ENTRY, "buy")
        pnl_pct_net = 1.0 - (exit_price / entry_price) - ROUND_TRIP_COST_PCT
    else:
        raise ValueError(f"unknown action: {action}")
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    return {
        "ticker": "QQQ",
        "action": action,
        "source": STEM,
        "date": context["event_date"],
        "signal_date": context["event_date"],
        "entry_date": shadow._date(qqq_rows[entry_idx]),
        "exit_date": shadow._date(qqq_rows[exit_idx]),
        "entry_raw_open": _round(entry_open, 4),
        "exit_raw_close": _round(exit_close, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "macro_context": context,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    ev_delta = ev_after - ev_before
    pnl_delta = pnl_after - pnl_before
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before, 6) if ev_before else None,
        "required_expected_value_score_delta_sum": _round(ev_before * MIN_EV_DELTA_PCT, 6),
        "expected_value_score_delta_gt_required": ev_delta > ev_before * MIN_EV_DELTA_PCT,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / pnl_before, 6) if pnl_before else None,
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
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()),
            6,
        ),
        "target_event_count_sum": sum(row["target_event_count"] for row in rows.values()),
    }


def _action_gate(
    *,
    action: str,
    aggregate: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    target_events_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    target_windows = [label for label, rows in target_events_by_window.items() if rows]
    failed: list[str] = []
    if not aggregate["expected_value_score_delta_gt_required"]:
        failed.append("aggregate_ev_delta_not_gt_10pct")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if aggregate["target_event_count_sum"] < MIN_TARGET_EVENTS:
        failed.append("macro_selloff_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    return {
        "action": action,
        "passed": not failed,
        "failed_reasons": failed,
        "target_event_count": aggregate["target_event_count_sum"],
        "target_windows": target_windows,
        "minimum_core_survival_rate": round(min_survival, 6),
        "aggregate": aggregate,
    }


def _best_action(gates: dict[str, dict[str, Any]]) -> str:
    return max(
        gates,
        key=lambda action: (
            float(gates[action]["aggregate"]["expected_value_score_delta_sum"] or 0.0),
            float(gates[action]["aggregate"]["total_pnl_delta_sum"] or 0.0),
        ),
    )


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    calendar = _macro_calendar()
    universe = sorted(get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    action_rows: dict[str, "OrderedDict[str, dict[str, Any]]"] = {
        action: OrderedDict() for action in ACTIONS
    }
    action_trades: dict[str, "OrderedDict[str, list[dict[str, Any]]]"] = {
        action: OrderedDict() for action in ACTIONS
    }
    release_contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    triggered_contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and scheduled macro action replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])
        contexts = []
        triggers = []
        for event_date, event in calendar.items():
            if not (cfg["start"] <= event_date <= cfg["end"]):
                continue
            context = _macro_selloff_context(snapshot, event, label)
            if context is None:
                continue
            contexts.append(context)
            if context["triggered"]:
                triggers.append(context)
        before_metrics[label] = before
        release_contexts_by_window[label] = contexts
        triggered_contexts_by_window[label] = triggers

        for action in ACTIONS:
            trades = [
                trade
                for context in triggers
                for trade in [_qqq_action_trade(snapshot, context, action)]
                if trade is not None
            ]
            overlay = sleeve._overlay_from_paper_trades(before_result, trades)
            after = overlay_helper._metrics_with_overlay(before_result, overlay)
            delta = overlay_helper._delta(after, before)
            action_trades[action][label] = trades
            action_rows[action][label] = {
                "before": before,
                "after": after,
                "delta": delta,
                "target_event_count": len(trades),
                "overlay_total_pnl": overlay["overlay_total_pnl"],
            }

    action_aggregates = {action: _aggregate(action_rows[action]) for action in ACTIONS}
    action_gates = {
        action: _action_gate(
            action=action,
            aggregate=action_aggregates[action],
            before_metrics=before_metrics,
            target_events_by_window=action_trades[action],
        )
        for action in ACTIONS
    }
    best_action = _best_action(action_gates)
    best_gate = action_gates[best_action]
    if best_gate["passed"]:
        decision = f"positive_replay_lead_not_promoted_{best_action}"
        status = "accepted"
    else:
        decision = "rejected_scheduled_macro_selloff_next_open_risk_action"
        status = "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": best_gate["passed"],
        "failure_modes_observed": best_gate["failed_reasons"],
        "best_action": best_action,
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Scheduled macro release-day selloffs across official CPI, FOMC, "
            "and NFP dates may mean-revert at the next open. Broadening the "
            "event family may preserve the NFP-only positive sign while reducing "
            "thin-sample risk."
        ),
        "change_type": "scheduled_macro_selloff_next_open_risk_action",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": [
            "exp-20260605-027",
            "exp-20260605-030",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "official_cpi_fomc_nfp_scheduled_calendar_plus_free_ohlcv",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "event_calendar_sources": [
                {
                    "provider": "BLS Employment Situation release schedules",
                    "official_current_url": "https://www.bls.gov/schedule/news_release/empsit.htm",
                    "note": "Release dates are known before market open.",
                },
                {
                    "provider": "BLS CPI release schedule",
                    "official_current_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
                    "note": (
                        "Current official schedule confirms late-window CPI "
                        "release dates; older dates use historical BLS release "
                        "calendar convention and archived release dates."
                    ),
                },
                {
                    "provider": "Federal Reserve FOMC calendars",
                    "official_current_url": (
                        "https://www.federalreserve.gov/monetarypolicy/"
                        "fomccalendars.htm"
                    ),
                    "note": "FOMC action uses the second-day policy decision date.",
                },
            ],
            "lookahead_control": (
                "Event calendars are scheduled/official before the trade. The "
                "selloff trigger uses only the event-day close; the paper action "
                "enters at the next trading day's open."
            ),
        },
        "parameters": {
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "selloff_qqq_return_lte": SELL_OFF_QQQ_RETURN,
            "selloff_spy_return_lte": SELL_OFF_SPY_RETURN,
            "actions": ACTIONS,
            "macro_events": MACRO_EVENTS,
            "dedupe_rule": "one paper action per calendar date even if multiple macro families share it",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: after scheduled CPI/FOMC/NFP event days that "
                "close in SPY/QQQ selloffs, next-open QQQ beta may mean-revert."
            ),
            "2_history_check": {
                "exp-20260605-027": (
                    "A broader macro selloff ETF-rotation sleeve failed. This "
                    "test avoids ETF rotation and keeps the direct QQQ beta "
                    "action from the NFP-specific follow-up."
                ),
                "exp-20260605-030": (
                    "NFP-only add-beta improved all three windows but failed "
                    "the >10% aggregate EV gate with five events. This test "
                    "adds CPI/FOMC scheduled dates as new official evidence, "
                    "not a parameter retune."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three standard windows. As a risk-allocation action, the "
                "retained action needs aggregate EV delta >10% of baseline, "
                "positive aggregate PnL, no window EV/PnL regression, drawdown "
                "drift <=0.5pp, survival >=5%, and target events in all windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260605_032_scheduled_macro_selloff_next_open_risk_action.py"
            ),
        },
        "gate1": {"baseline_metrics": before_metrics, "passed": True},
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "official scheduled macro event date",
                "event family and label",
                "SPY Date/Open/Close OHLCV",
                "QQQ Date/Open/Close OHLCV",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
            >= 0.05,
        },
        "gate4": {
            "passed": best_gate["passed"],
            "best_action": best_action,
            "best_action_gate": best_gate,
            "all_action_gates": action_gates,
            "interpretation": (
                "add_beta means long QQQ next open; reduce_beta means short "
                "QQQ beta hedge next open. This is a beta proxy, not an exact "
                "portfolio position trim."
            ),
        },
        "before_metrics": before_metrics,
        "action_metrics": {
            action: {
                "by_window": action_rows[action],
                "aggregate": action_aggregates[action],
            }
            for action in ACTIONS
        },
        "release_contexts_by_window": release_contexts_by_window,
        "triggered_contexts_by_window": triggered_contexts_by_window,
        "action_trades_by_window": action_trades,
        "best_action": best_action,
        "expected_value_score_delta": best_gate["aggregate"]["expected_value_score_delta_sum"],
        "total_pnl_delta": best_gate["aggregate"]["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The scheduled macro selloff action did not clear Gate 4; the "
            "result is advisory/diagnostic only, not a retained strategy change."
            if not best_gate["passed"]
            else (
                "The scheduled macro selloff action cleared the strict replay "
                "gate but remains default-off until a shared adapter and parity "
                "tests exist."
            )
        ),
        "negative_reflection": (
            "If rejected, the likely cause is that scheduled macro selloffs are "
            "too heterogeneous: CPI/FOMC/NFP have different information content, "
            "and the fixed QQQ next-open action may be a beta timing proxy rather "
            "than a durable alpha source. Do not retune thresholds or hold days "
            "without a new PIT macro surprise/consensus field."
        ),
        "next_evidence_needed": (
            "A robust macro risk action needs more historical official release "
            "events with PIT surprise/consensus or a richer ex-ante macro state "
            "field. Do not retry by only changing selloff thresholds, hold days, "
            "notional, or the QQQ proxy."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Action | Window | dEV | dPnL | Events |",
        "|---|---|---:|---:|---:|",
    ]
    for action in ACTIONS:
        for label in WINDOWS:
            row = payload["action_metrics"][action]["by_window"][label]
            delta = row["delta"]
            rows.append(
                f"| {action} | {label} | {delta.get('expected_value_score', 0.0):+.4f} | "
                f"${delta.get('total_pnl', 0.0):+,.2f} | {row['target_event_count']} |"
            )
    aggregate_lines = []
    for action in ACTIONS:
        agg = payload["action_metrics"][action]["aggregate"]
        aggregate_lines.append(
            f"- `{action}`: EV `{agg['expected_value_score_delta_sum']}`, "
            f"PnL `${agg['total_pnl_delta_sum']}`, events `{agg['target_event_count_sum']}`"
        )
    triggered_lines = []
    for label, rows_for_window in payload["triggered_contexts_by_window"].items():
        families = Counter(family for row in rows_for_window for family in row["event_families"])
        triggered_lines.append(
            f"- `{label}`: `{len(rows_for_window)}` triggered macro selloff days, "
            f"families `{dict(families)}`"
        )
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            'lane: "alpha_search"',
            'change_type: "scheduled_macro_selloff_next_open_risk_action"',
            'mechanism_family: "macro_event_risk_allocation"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            f'updated_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            f"Best action by EV: `{payload['best_action']}`.",
            "",
            "## Three-Window Action Comparison",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            *aggregate_lines,
            "",
            "## Triggered Event Mix",
            "",
            *triggered_lines,
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "Replay-only/default-off; no production orders changed. No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    best_gate = payload["gate4"]["best_action_gate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "macro_event_risk_allocation",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "best_action": payload["best_action"],
        "aggregate_expected_value_delta": best_gate["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": best_gate["aggregate"][
            "total_pnl_delta_sum"
        ],
        "gate4": payload["gate4"],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }


def _judge_metric_artifacts(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    best_gate = payload["gate4"]["best_action_gate"]
    aggregate = best_gate["aggregate"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in payload["before_metrics"].values()
    )
    before = {
        "expected_value_score": aggregate["baseline_expected_value_score_sum"],
        "total_pnl": aggregate["baseline_total_pnl_sum"],
        "max_drawdown_pct": max(
            float(row.get("max_drawdown_pct") or 0.0)
            for row in payload["before_metrics"].values()
        ),
        "survival_rate": min_survival,
        "total_trades": sum(int(row.get("total_trades") or 0) for row in payload["before_metrics"].values()),
        "window_count": len(payload["before_metrics"]),
        "source": "aggregate_core_baseline_from_docs_backtesting_three_windows",
    }
    after = {
        "expected_value_score": aggregate["after_expected_value_score_sum"],
        "total_pnl": aggregate["after_total_pnl_sum"],
        "max_drawdown_pct": before["max_drawdown_pct"] + aggregate["max_drawdown_delta_max"],
        "survival_rate": min_survival,
        "total_trades": before["total_trades"] + aggregate["target_event_count_sum"],
        "target_event_count": aggregate["target_event_count_sum"],
        "window_count": len(payload["before_metrics"]),
        "best_action": payload["best_action"],
        "source": "aggregate_after_best_action_overlay_from_exp_20260605_032",
    }
    return before, after


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "owner": "alpha-search",
            "claimed_at": ticket.get("claimed_at") or payload["timestamp"],
            "completed_at": payload["timestamp"],
            "allowed_write_scope": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(EXPERIMENT_LOG),
            ],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "before": _repo_rel(BEFORE_JSON),
                "after": _repo_rel(AFTER_JSON),
                "log": _repo_rel(LOG_JSON),
                "accepted": payload["gate4"]["passed"],
                "best_action": payload["best_action"],
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "calibration": payload["calibration"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(BEFORE_JSON): _sha256(BEFORE_JSON),
            _repo_rel(AFTER_JSON): _sha256(AFTER_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
            _repo_rel(EXPERIMENT_LOG): _sha256(EXPERIMENT_LOG),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    before_judge, after_judge = _judge_metric_artifacts(payload)
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, before_judge)
    _write_json(AFTER_JSON, after_judge)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _update_ticket(payload)
    _write_manifest(payload)
    _upsert_jsonl(EXPERIMENT_LOG, log_record)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
