"""exp-20260606-011: low-deployment ETF loss-streak kill switch.

Alpha-search replay only. This tests one production-visible risk boundary for
the accepted default-off low-deployment ETF cash substitute: after two prior
closed ETF sleeve losses, skip new paper entries for ten trading sessions.

The ETF candidate set, trend/momentum selector, next-open entry, 10-trading-day
close exit, notional, core strategy, LLM/news paths, and live order behavior are
locked. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260605_035_low_deployment_etf_cash_substitute as base
import exp_20260426_041_opening_range_continuation_shadow as shadow
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve
from data_layer import get_universe
from low_deployment_etf_overlay import (
    _core_active_count_by_date,
    _core_deployment_context,
    _normalise_ohlcv_rows,
    _replay_trade_from_candidate,
    _select_candidate,
    replay_low_deployment_etf_cash_substitute_trades,
)


EXPERIMENT_ID = "exp-20260606-011"
STEM = "low_deployment_etf_loss_streak_kill_switch"
TRIAL_FAMILY = "low_deployment_etf_cash_substitute_kill_switch"
TRIAL_VARIANT_ID = "low_deployment_etf_prior_closed_loss_streak_kill_switch_v1"
CHANGED_VARIABLE = "low_deployment_etf_prior_closed_loss_streak_kill_switch_v1"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_011_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"exp_20260606_011_{STEM}_aggregate_before.json"
AFTER_JSON = OUT_DIR / f"exp_20260606_011_{STEM}_aggregate_after.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

LOSS_STREAK_THRESHOLD = 2
COOLDOWN_TRADING_DAYS = 10

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_etf_comparator_not_beaten",
        "window_regression",
        "trade_count_too_low",
        "positive_trade_concentration",
    ],
    "confidence_reason": (
        "The playbook marks the accepted low-deployment ETF adapter as the "
        "strongest current direction and specifically calls out kill-switch or "
        "capital-cap design before activation. The nearby volatility-cap scout "
        "did not test a prior closed sleeve loss streak."
    ),
    "recorded_at": "2026-06-06T09:07:25Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "experiment_only_default_off_paper_kill_switch_candidate",
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
        "No production code is changed in this experiment. If the fixed "
        "loss-streak rule were positive, promotion would require adding the "
        "same stateful closed-paper-trade cooldown to the shared default-off "
        "low_deployment_etf_overlay helper and replay parity tests before any "
        "production-visible retention."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return _repo_rel(payload)
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


def _overlay_config() -> dict[str, Any]:
    return {
        "fallback_paper_notional_usd": base.BASE_NOTIONAL_USD,
        "hold_days": base.HOLD_DAYS,
        "max_active_core_positions": base.MAX_ACTIVE_CORE_POSITIONS,
        "max_overlay_open_positions": base.MAX_OVERLAY_OPEN_POSITIONS,
        "state_sma_days": base.STATE_SMA_DAYS,
        "state_momentum_days": base.STATE_MOMENTUM_DAYS,
        "candidate_tickers": base.OVERLAY_CANDIDATES,
        "enabled": False,
        "trade_enabled": False,
        "paper_enabled": True,
    }


def _loss_streak(trades: list[dict[str, Any]]) -> int:
    streak = 0
    for trade in reversed(trades):
        if float(trade.get("pnl") or 0.0) < 0.0:
            streak += 1
            continue
        break
    return streak


def _variant_overlay_trades(
    before_result: dict[str, Any],
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _overlay_config()
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(snapshot.get(ticker))
        for ticker in cfg["candidate_tickers"]
    }
    core_counts = _core_active_count_by_date(before_result)
    equity_dates = [str(day)[:10] for day, _ in before_result.get("equity_curve") or []]
    date_to_index = {day: idx for idx, day in enumerate(equity_dates)}

    open_trades: list[dict[str, Any]] = []
    closed_trades: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    cooldown_events: list[dict[str, Any]] = []
    disabled_until: str | None = None
    low_deployment_day_count = 0
    selectable_day_count = 0

    for day_idx, signal_date in enumerate(equity_dates):
        newly_closed = [
            trade for trade in open_trades if str(trade.get("exit_date") or "") <= signal_date
        ]
        open_trades = [
            trade for trade in open_trades if str(trade.get("exit_date") or "") > signal_date
        ]
        for trade in sorted(newly_closed, key=lambda row: str(row.get("exit_date") or "")):
            closed_trades.append(trade)
            if _loss_streak(closed_trades) >= LOSS_STREAK_THRESHOLD:
                until_idx = min(day_idx + COOLDOWN_TRADING_DAYS, len(equity_dates) - 1)
                candidate_until = equity_dates[until_idx]
                if disabled_until is None or candidate_until > disabled_until:
                    disabled_until = candidate_until
                    cooldown_events.append(
                        {
                            "trigger_date": signal_date,
                            "disabled_until": disabled_until,
                            "loss_streak": _loss_streak(closed_trades),
                            "trigger_trade": {
                                "ticker": trade.get("ticker"),
                                "signal_date": trade.get("signal_date"),
                                "entry_date": trade.get("entry_date"),
                                "exit_date": trade.get("exit_date"),
                                "pnl": trade.get("pnl"),
                            },
                        }
                    )

        active_core_positions = int(core_counts.get(signal_date, 0))
        context = _core_deployment_context(active_core_positions, cfg)
        if not context["low_deployment_condition_passed"]:
            skipped["core_above_low_deployment_threshold"] += 1
            continue
        low_deployment_day_count += 1
        if len(open_trades) >= int(cfg["max_overlay_open_positions"]):
            skipped["overlay_position_cap_full"] += 1
            continue
        if disabled_until is not None and signal_date <= disabled_until:
            skipped["loss_streak_cooldown"] += 1
            continue
        selection = _select_candidate(
            rows_by_ticker,
            as_of=signal_date,
            active_core_positions=active_core_positions,
            core_deployment_context=context,
            config=cfg,
        )
        if selection is None:
            skipped["no_etf_passing_signal_close_state"] += 1
            continue
        selectable_day_count += 1
        trade = _replay_trade_from_candidate(
            rows_by_ticker=rows_by_ticker,
            candidate=selection,
            config=cfg,
        )
        if trade is None:
            skipped["missing_entry_or_exit_price"] += 1
            continue
        trade["source"] = STEM
        trade["loss_streak_kill_switch"] = {
            "enabled": True,
            "threshold": LOSS_STREAK_THRESHOLD,
            "cooldown_trading_days": COOLDOWN_TRADING_DAYS,
            "prior_closed_trade_count": len(closed_trades),
            "prior_closed_loss_streak": _loss_streak(closed_trades),
            "disabled_until_before_entry": disabled_until,
            "decision_date_index": date_to_index.get(signal_date),
        }
        trades.append(trade)
        open_trades.append(trade)

    return trades, {
        "low_deployment_day_count": low_deployment_day_count,
        "selectable_day_count_before_position_cap": selectable_day_count,
        "skipped": dict(skipped),
        "cooldown_events": cooldown_events,
        "closed_trades_observed_for_kill_switch": len(closed_trades),
        "loss_streak_threshold": LOSS_STREAK_THRESHOLD,
        "cooldown_trading_days": COOLDOWN_TRADING_DAYS,
        "max_active_core_positions": int(cfg["max_active_core_positions"]),
        "max_overlay_open_positions": int(cfg["max_overlay_open_positions"]),
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["accepted_after"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["variant_after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["accepted_after"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["variant_after"]["total_pnl"] for row in rows.values())
    ev_delta = ev_after - ev_before
    pnl_delta = pnl_after - pnl_before
    return {
        "comparator_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before, 6) if ev_before else None,
        "comparator_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / pnl_before, 6) if pnl_before else None,
        "windows_ev_improved_vs_accepted": sum(
            1 for row in rows.values() if row["delta_vs_accepted"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed_vs_accepted": sum(
            1 for row in rows.values() if row["delta_vs_accepted"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved_vs_accepted": sum(
            1 for row in rows.values() if row["delta_vs_accepted"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed_vs_accepted": sum(
            1 for row in rows.values() if row["delta_vs_accepted"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max_vs_accepted": _round(
            max(row["delta_vs_accepted"]["max_drawdown_pct"] for row in rows.values()),
            6,
        ),
        "target_trade_count_sum": sum(row["variant_target_trade_count"] for row in rows.values()),
        "accepted_trade_count_sum": sum(row["accepted_target_trade_count"] for row in rows.values()),
        "target_windows": [
            label for label, row in rows.items() if int(row["variant_target_trade_count"] or 0) > 0
        ],
    }


def _concentration(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    total_positive = 0.0
    for trades in trades_by_window.values():
        for trade in trades:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl <= 0.0:
                continue
            ticker = str(trade.get("ticker") or "").upper()
            by_ticker[ticker] += pnl
            total_positive += pnl
    if total_positive <= 0.0:
        return {
            "positive_pnl_total": 0.0,
            "ticker_positive_pnl": {},
            "max_single_positive_share": None,
            "positive_pnl_hhi": None,
            "passed": False,
        }
    shares = {ticker: pnl / total_positive for ticker, pnl in by_ticker.items()}
    max_share = max(shares.values()) if shares else None
    hhi = sum(share * share for share in shares.values())
    return {
        "positive_pnl_total": _round(total_positive, 2),
        "ticker_positive_pnl": {ticker: _round(pnl, 2) for ticker, pnl in by_ticker.items()},
        "max_single_positive_share": _round(max_share, 6),
        "positive_pnl_hhi": _round(hhi, 6),
        "passed": bool(
            max_share is not None
            and max_share <= base.MAX_SINGLE_POSITIVE_SHARE
            and hhi <= base.MAX_POSITIVE_PNL_HHI
        ),
    }


def _gate(
    *,
    aggregate: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive_vs_accepted_etf")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive_vs_accepted_etf")
    if int(aggregate["windows_ev_regressed_vs_accepted"] or 0) > 0:
        failed.append("window_ev_regression_vs_accepted_etf")
    if int(aggregate["windows_pnl_regressed_vs_accepted"] or 0) > 0:
        failed.append("window_pnl_regression_vs_accepted_etf")
    if int(aggregate["target_trade_count_sum"] or 0) < base.MIN_TARGET_TRADES:
        failed.append("target_trade_count_too_small")
    if len(aggregate["target_windows"]) < base.MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max_vs_accepted"] or 0.0) > 0.0:
        failed.append("drawdown_worse_vs_accepted_etf")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration["passed"]:
        failed.append("positive_pnl_concentration_failed")
    return {
        "passed": not failed,
        "failed_reasons": failed,
        "minimum_core_survival_rate": _round(min_survival, 6),
        "aggregate": aggregate,
        "concentration": concentration,
        "comparator": "exp-20260606-001 accepted shared low-deployment ETF adapter",
        "acceptance_rule": (
            "The fixed loss-streak kill switch must beat the accepted ETF "
            "adapter, not merely the core baseline: positive aggregate EV/PnL "
            "vs accepted, no window EV/PnL regression, no drawdown worsening, "
            "minimum target trades/window coverage, survival >=5%, and positive "
            "PnL concentration passing."
        ),
    }


def _build_payload() -> dict[str, Any]:
    timestamp = base._utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    variant_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    accepted_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    diagnostics_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] accepted ETF comparator and loss-streak kill-switch replay")
        before_result = shadow._run_baseline(universe, cfg)
        core_before = overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])

        accepted_trades, accepted_diagnostics = replay_low_deployment_etf_cash_substitute_trades(
            core_backtest_result=before_result,
            ohlcv_by_ticker=snapshot,
            config=_overlay_config(),
        )
        accepted_overlay = sleeve._overlay_from_paper_trades(before_result, accepted_trades)
        accepted_after = overlay_helper._metrics_with_overlay(before_result, accepted_overlay)

        variant_trades, variant_diagnostics = _variant_overlay_trades(before_result, snapshot)
        variant_overlay = sleeve._overlay_from_paper_trades(before_result, variant_trades)
        variant_after = overlay_helper._metrics_with_overlay(before_result, variant_overlay)

        before_metrics[label] = core_before
        accepted_trades_by_window[label] = accepted_trades
        variant_trades_by_window[label] = variant_trades
        diagnostics_by_window[label] = {
            "accepted": accepted_diagnostics,
            "variant": variant_diagnostics,
        }
        window_rows[label] = {
            "core_before": core_before,
            "accepted_after": accepted_after,
            "variant_after": variant_after,
            "accepted_delta_vs_core": overlay_helper._delta(accepted_after, core_before),
            "variant_delta_vs_core": overlay_helper._delta(variant_after, core_before),
            "delta_vs_accepted": overlay_helper._delta(variant_after, accepted_after),
            "accepted_target_trade_count": len(accepted_trades),
            "variant_target_trade_count": len(variant_trades),
            "accepted_ticker_trade_counts": dict(
                Counter(str(trade["ticker"]) for trade in accepted_trades)
            ),
            "variant_ticker_trade_counts": dict(
                Counter(str(trade["ticker"]) for trade in variant_trades)
            ),
            "accepted_overlay_total_pnl": accepted_overlay["overlay_total_pnl"],
            "variant_overlay_total_pnl": variant_overlay["overlay_total_pnl"],
            "accepted_trades_sample": accepted_trades[:20],
            "variant_trades_sample": variant_trades[:20],
            "diagnostics": diagnostics_by_window[label],
        }

    aggregate = _aggregate(window_rows)
    concentration = _concentration(variant_trades_by_window)
    gate4 = _gate(
        aggregate=aggregate,
        before_metrics=before_metrics,
        concentration=concentration,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": (
            "accepted_low_deployment_etf_loss_streak_kill_switch"
            if gate4["passed"]
            else "rejected_low_deployment_etf_loss_streak_kill_switch"
        ),
        "hypothesis": (
            "The accepted default-off low-deployment ETF cash substitute may be "
            "activation-safer if it stops opening new paper entries after two "
            "prior closed ETF sleeve losses and waits ten trading sessions. "
            "This could reduce whipsaw/tail exposure while preserving the "
            "free-OHLCV replacement-value edge."
        ),
        "change_type": "default_off_paper_risk_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": {
            "exp-20260606-001": (
                "Accepted shared default-off ETF adapter: aggregate EV 7.8941 "
                "-> 10.9233, PnL $234,850.99 -> $279,157.90, all three "
                "windows improved, default-off and no live orders."
            ),
            "exp-20260522-004": (
                "Older low-deployment ETF volatility-cap scout was rejected; "
                "it tested selected ETF realized-volatility gating, not prior "
                "closed sleeve loss streak."
            ),
            "exp-20260605-028": (
                "Forward readiness audit found low_deployment_etf closest to "
                "activation but still blocked by closed sample and concentration."
            ),
        },
        "multiple_testing_risk_bucket": "medium",
        "new_evidence_type": "production_visible_stateful_kill_switch_on_accepted_adapter",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": gate4["passed"],
            "failure_modes_observed": gate4["failed_reasons"],
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "comparator": "exp-20260606-001 accepted shared ETF adapter",
            "REGIME_AWARE_EXIT": True,
            "replay_llm": False,
            "replay_news": False,
        },
        "parameters": {
            "loss_streak_threshold": LOSS_STREAK_THRESHOLD,
            "cooldown_trading_days": COOLDOWN_TRADING_DAYS,
            "base_notional_usd": base.BASE_NOTIONAL_USD,
            "hold_days": base.HOLD_DAYS,
            "max_active_core_positions": base.MAX_ACTIVE_CORE_POSITIONS,
            "max_overlay_open_positions": base.MAX_OVERLAY_OPEN_POSITIONS,
            "state_sma_days": base.STATE_SMA_DAYS,
            "state_momentum_days": base.STATE_MOMENTUM_DAYS,
            "overlay_candidates": base.OVERLAY_CANDIDATES,
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "ETF candidate set",
                "prior-close 20d momentum ranking",
                "positive 200d trend gate",
                "positive 20d momentum gate",
                "low-deployment threshold",
                "paper notional",
                "hold days",
                "one-open-position cap",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / capital allocation: add a production-visible "
                "loss-streak cooldown to the accepted default-off ETF cash "
                "substitute so low-deployment replacement value survives weak "
                "ETF sleeve regimes."
            ),
            "2_history_check": {
                "exp-20260606-001": "Accepted ETF comparator and current strongest lead.",
                "exp-20260522-004": "Rejected volatility-cap variant, not the same variable.",
                "exp-20260605-028": "Forward readiness audit; activation remains blocked.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three standard windows; compare against the accepted ETF "
                "adapter. The kill-switch must improve aggregate EV and PnL, "
                "avoid all window EV/PnL regressions, avoid drawdown worsening, "
                "retain enough trades/window coverage, pass survival and "
                "concentration checks."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260606_011_low_deployment_etf_loss_streak_kill_switch.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "accepted_etf_comparator_metrics": {
                label: row["accepted_after"] for label, row in window_rows.items()
            },
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "core baseline trades entry_date",
                "core baseline trades exit_date",
                "ETF Date/Open/Close OHLCV",
                "accepted paper ETF trades exit_date",
                "accepted paper ETF trades pnl",
                "baseline equity_curve dates",
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
        "gate4": gate4,
        "before_metrics": before_metrics,
        "window_metrics": window_rows,
        "accepted_trades_by_window": accepted_trades_by_window,
        "variant_trades_by_window": variant_trades_by_window,
        "diagnostics_by_window": diagnostics_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The fixed prior-loss-streak kill switch beat the accepted ETF "
            "adapter and should only be retained after shared-helper promotion "
            "and parity tests."
            if gate4["passed"]
            else (
                "The fixed prior-loss-streak kill switch did not beat the "
                "accepted ETF adapter and is not retained."
            )
        ),
        "negative_reflection": (
            "If rejected, the loss-streak rule probably cuts profitable recovery "
            "entries after ordinary ETF pullbacks. The accepted ETF edge is "
            "likely driven by persistent broad-market replacement exposure "
            "during low core deployment, so realized sleeve loss streak is too "
            "slow and too blunt as a state variable. Do not retry adjacent "
            "loss-streak/cooldown thresholds without new forward replacement "
            "rows or a materially different free data edge."
        ),
        "next_evidence_needed": (
            "Use forward replacement rows and cash/core-capacity context to "
            "design activation risk controls; avoid further ETF threshold, "
            "hold, notional, or cooldown retunes without new evidence."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | dEV vs accepted | dPnL vs accepted | Accepted trades | Variant trades | Cooldowns |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        row = payload["window_metrics"][label]
        delta = row["delta_vs_accepted"]
        rows.append(
            f"| {label} | {delta.get('expected_value_score', 0.0):+.4f} | "
            f"${delta.get('total_pnl', 0.0):+,.2f} | "
            f"{row['accepted_target_trade_count']} | {row['variant_target_trade_count']} | "
            f"{len(row['diagnostics']['variant']['cooldown_events'])} |"
        )
    agg = payload["gate4"]["aggregate"]
    concentration = payload["gate4"]["concentration"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            'lane: "alpha_search"',
            'change_type: "default_off_paper_risk_allocation"',
            'mechanism_family: "low_deployment_etf_cash_substitute_kill_switch"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            f'updated_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "## Three-Window Comparator Deltas",
            "",
            *rows,
            "",
            "## Aggregate Gate",
            "",
            f"- Comparator EV: `{agg['comparator_expected_value_score_sum']}`",
            f"- Variant EV: `{agg['after_expected_value_score_sum']}`",
            f"- EV delta vs accepted: `{agg['expected_value_score_delta_sum']}`",
            f"- PnL delta vs accepted: `${agg['total_pnl_delta_sum']}`",
            f"- Variant target trades: `{agg['target_trade_count_sum']}`",
            f"- Max drawdown delta vs accepted: `{agg['max_drawdown_delta_max_vs_accepted']}`",
            f"- Concentration: `{concentration}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(_safe(payload["gate4"]), indent=2, sort_keys=True),
            "```",
            "",
            "Replay-only/default-off; no production orders changed. No JavaScript was used.",
        ]
    ) + "\n"


def _build_artifact(payload: dict[str, Any]) -> str:
    agg = payload["gate4"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Low-Deployment ETF Loss-Streak Kill Switch",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Preflight Answers",
        "",
        f"1. Hypothesis: {payload['gate_questions']['1_alpha_hypothesis']}",
        (
            "2. History: exp-20260606-001 accepted the shared ETF adapter; "
            "exp-20260522-004 rejected ETF volatility cap; exp-20260605-028 "
            "found forward activation still blocked."
        ),
        f"3. Single variable: `{CHANGED_VARIABLE}`.",
        (
            "4. Acceptance: three canonical windows versus accepted ETF "
            "comparator; positive aggregate EV/PnL, no window regressions, "
            "no drawdown worsening, enough trades, survival/concentration pass."
        ),
        f"5. Reproduce: `{payload['gate_questions']['5_reproducibility']}`.",
        "",
        "## Aggregate vs Accepted ETF Comparator",
        "",
        f"- EV: `{agg['comparator_expected_value_score_sum']} -> "
        f"{agg['after_expected_value_score_sum']}` "
        f"({agg['expected_value_score_delta_sum']:+.4f})",
        f"- PnL: `${agg['comparator_total_pnl_sum']:,.2f} -> "
        f"${agg['after_total_pnl_sum']:,.2f}` "
        f"(${agg['total_pnl_delta_sum']:+,.2f})",
        f"- Variant trades: `{agg['target_trade_count_sum']}` "
        f"(accepted `{agg['accepted_trade_count_sum']}`)",
        f"- Max drawdown delta vs accepted: `{agg['max_drawdown_delta_max_vs_accepted']}`",
        "",
        "## Window Deltas",
        "",
        "| Window | EV delta | PnL delta | Accepted trades | Variant trades |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label in base.WINDOWS:
        row = payload["window_metrics"][label]
        delta = row["delta_vs_accepted"]
        lines.append(
            f"| `{label}` | {delta.get('expected_value_score', 0.0):+.4f} | "
            f"${delta.get('total_pnl', 0.0):+,.2f} | "
            f"{row['accepted_target_trade_count']} | {row['variant_target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production Boundary",
            "",
            "- Experiment-only, default-off paper replay; no production orders changed.",
            "- Positive retention would require shared-helper promotion and parity tests.",
            "- No JavaScript was used.",
            "",
            "## Reflection",
            "",
            payload["negative_reflection"]
            if payload["status"] == "rejected"
            else payload["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    aggregate = gate4["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": gate4["passed"],
        "mechanism_family": "low_deployment_etf_cash_substitute_kill_switch",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": gate4,
        "windows": [
            {
                "label": label,
                "accepted_expected_value": payload["window_metrics"][label]["accepted_after"][
                    "expected_value_score"
                ],
                "variant_expected_value": payload["window_metrics"][label]["variant_after"][
                    "expected_value_score"
                ],
                "expected_value_delta_vs_accepted": payload["window_metrics"][label][
                    "delta_vs_accepted"
                ]["expected_value_score"],
                "strategy_total_pnl_delta_vs_accepted": payload["window_metrics"][label][
                    "delta_vs_accepted"
                ]["total_pnl"],
                "accepted_target_trade_count": payload["window_metrics"][label][
                    "accepted_target_trade_count"
                ],
                "variant_target_trade_count": payload["window_metrics"][label][
                    "variant_target_trade_count"
                ],
            }
            for label in base.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }


def _judge_metric_artifacts(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    aggregate = payload["gate4"]["aggregate"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in payload["before_metrics"].values()
    )
    comparator_max_drawdown = max(
        float(row["accepted_after"].get("max_drawdown_pct") or 0.0)
        for row in payload["window_metrics"].values()
    )
    before = {
        "expected_value_score": aggregate["comparator_expected_value_score_sum"],
        "total_pnl": aggregate["comparator_total_pnl_sum"],
        "max_drawdown_pct": comparator_max_drawdown,
        "survival_rate": min_survival,
        "target_trade_count": aggregate["accepted_trade_count_sum"],
        "window_count": len(payload["before_metrics"]),
        "source": "aggregate_accepted_low_deployment_etf_comparator_three_windows",
    }
    after = {
        "expected_value_score": aggregate["after_expected_value_score_sum"],
        "total_pnl": aggregate["after_total_pnl_sum"],
        "max_drawdown_pct": comparator_max_drawdown
        + aggregate["max_drawdown_delta_max_vs_accepted"],
        "survival_rate": min_survival,
        "target_trade_count": aggregate["target_trade_count_sum"],
        "window_count": len(payload["before_metrics"]),
        "source": "aggregate_after_loss_streak_kill_switch_variant_three_windows",
    }
    return before, after


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "owner": "alpha-search-automation",
            "claimed_at": ticket.get("claimed_at") or payload["timestamp"],
            "completed_at": payload["timestamp"],
            "allowed_write_scope": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(BEFORE_JSON),
                _repo_rel(AFTER_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(EXPERIMENT_LOG),
            ],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "artifact_md": _repo_rel(ARTIFACT_MD),
                "before": _repo_rel(BEFORE_JSON),
                "after": _repo_rel(AFTER_JSON),
                "log": _repo_rel(LOG_JSON),
                "accepted": payload["gate4"]["passed"],
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
            _repo_rel(ARTIFACT_MD),
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
            _repo_rel(ARTIFACT_MD): _sha256(ARTIFACT_MD),
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
    _write_text(ARTIFACT_MD, _build_artifact(payload))
    _update_ticket(payload)
    _write_manifest(payload)
    _upsert_jsonl(EXPERIMENT_LOG, log_record)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
