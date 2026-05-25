"""exp-20260525-003: AI optical IWM-confirmed fixed-notional sleeve scout.

This alpha search follows the positive-but-rejected AI optical
no-displacement paper result from exp-20260524-035. The single tested routing
policy is a production-visible, fixed-notional default-off paper sleeve that
only admits the governed optical cohort when prior-close 20-day IWM momentum
beats SPY by at least 30bp.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260524_035_ai_optical_no_displacement_sleeve as prior


EXPERIMENT_ID = "exp-20260525-003"
STEM = "ai_optical_iwm_confirmed_fixed_notional_sleeve"
TRIAL_FAMILY = "governed_ai_optical_iwm_confirmed_fixed_notional_paper_sleeve"
CHANGED_VARIABLE = "ai_optical_iwm_confirmed_fixed_notional_paper_sleeve_routing_v1"

BASE_NOTIONAL_USD = 10_000.0
MIN_IWM_SPY_MOMENTUM_SPREAD = 0.003
MOMENTUM_LOOKBACK_DAYS = 20

MIN_TARGET_TRADES = 10
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
WINDOWS = prior.WINDOWS


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _row_value(row: dict[str, Any], key: str) -> Any:
    return row.get(key) if key in row else row.get(key.capitalize())


def _load_close_series(snapshot: str, ticker: str) -> dict[str, float]:
    payload = json.loads((REPO_ROOT / snapshot).read_text(encoding="utf-8"))
    ohlcv = payload.get("ohlcv") or payload
    rows = ohlcv.get(ticker) or []
    series: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = _row_value(row, "date")
        close = _row_value(row, "close")
        if not date or close in (None, ""):
            continue
        series[str(date)] = float(close)
    return series


def _momentum(series: dict[str, float], as_of: str, lookback: int) -> float | None:
    dates = sorted(series)
    prior_dates = [date for date in dates if date <= as_of]
    if not prior_dates:
        return None
    date = prior_dates[-1]
    index = dates.index(date)
    if index < lookback:
        return None
    prior_date = dates[index - lookback]
    prior_close = series[prior_date]
    if prior_close <= 0:
        return None
    return (series[date] / prior_close) - 1.0


def _previous_market_date(series: dict[str, float], entry_date: str) -> str | None:
    dates = sorted(date for date in series if date < entry_date)
    return dates[-1] if dates else None


def _market_confirmation(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    iwm = _load_close_series(snapshot, "IWM")
    spy = _load_close_series(snapshot, "SPY")
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        entry_date = str(trade.get("entry_date") or "")
        as_of = _previous_market_date(spy, entry_date)
        iwm_mom = _momentum(iwm, as_of, MOMENTUM_LOOKBACK_DAYS) if as_of else None
        spy_mom = _momentum(spy, as_of, MOMENTUM_LOOKBACK_DAYS) if as_of else None
        spread = (iwm_mom - spy_mom) if iwm_mom is not None and spy_mom is not None else None
        out[key] = {
            "market_state_as_of": as_of,
            "iwm_momentum20": _round(iwm_mom, 6),
            "spy_momentum20": _round(spy_mom, 6),
            "iwm_spy_momentum_spread": _round(spread, 6),
            "min_iwm_spy_momentum_spread": MIN_IWM_SPY_MOMENTUM_SPREAD,
            "passed": spread is not None and spread >= MIN_IWM_SPY_MOMENTUM_SPREAD,
        }
    return out


def _fixed_notional_trade(
    trade: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    pnl_pct = float(trade.get("pnl_pct_net") or 0.0)
    return {
        **trade,
        "core_sized_pnl": _round(trade.get("pnl"), 2),
        "core_sized_shares": trade.get("shares"),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl": round(BASE_NOTIONAL_USD * pnl_pct, 2),
        "pnl_pct_net": _round(pnl_pct, 6),
        "shares": None,
        "market_confirmation": market_state,
    }


def _target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    for trades in target_trades_by_window.values():
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl

    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
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
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "positive_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_pnl_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": _round((pnl_after - pnl_before) / pnl_before, 6)
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
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = prior._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    target_universe = prior._target_universe()
    target_tickers = target_universe["target_tickers"]
    coverage = prior._snapshot_coverage(target_tickers)
    canonical_coverage = prior._snapshot_coverage_for_windows(
        target_tickers,
        prior.CANONICAL_WINDOWS,
    )
    if not coverage["passed"]:
        raise RuntimeError(f"Gate 2 OHLCV coverage failed: {coverage}")

    base_universe = sorted(prior.get_universe())
    expanded_universe = sorted(set(base_universe) | set(target_tickers))
    target_set = set(target_tickers)

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_out_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    direct_core_admission_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    with prior._target_sector_patch(target_tickers):
        for label in WINDOWS:
            print(f"[{label}] baseline core universe")
            before_result = prior.base._run_window(label, base_universe)
            print(f"[{label}] expanded universe for optical target discovery")
            expanded_result = prior.base._run_window(label, expanded_universe)

            raw_target_trades = prior._target_trades(expanded_result, target_set)
            market_state = _market_confirmation(WINDOWS[label]["snapshot"], raw_target_trades)

            selected_trades: list[dict[str, Any]] = []
            rejected_trades: list[dict[str, Any]] = []
            for trade in raw_target_trades:
                key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
                state = market_state[key]
                paper_trade = _fixed_notional_trade(trade, state)
                if state["passed"]:
                    selected_trades.append(paper_trade)
                else:
                    rejected_trades.append(paper_trade)

            overlay = prior._overlay_from_target_trades(before_result, selected_trades)
            before = prior.overlay_helper._metrics(before_result)
            after = prior.overlay_helper._metrics_with_overlay(before_result, overlay)
            delta = prior.overlay_helper._delta(after, before)

            target_trades_by_window[label] = selected_trades
            filtered_out_by_window[label] = rejected_trades
            before_metrics[label] = before
            after_metrics[label] = after
            direct_core_admission_metrics[label] = prior.base._metrics(expanded_result)
            window_rows[label] = {
                "before": before,
                "after": after,
                "delta": delta,
                "overlay_total_pnl": overlay["overlay_total_pnl"],
                "overlay_day_count": overlay["overlay_day_count"],
                "target_trade_count": len(selected_trades),
                "filtered_out_trade_count": len(rejected_trades),
            }

    aggregate = _aggregate(window_rows)
    target_summary = _target_trade_summary(target_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )
    decision = (
        "promising_replay_only_ai_optical_iwm_confirmed_fixed_notional_sleeve"
        if gate4_passed
        else "rejected_ai_optical_iwm_confirmed_fixed_notional_sleeve"
    )

    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_improved"] != len(WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The governed AI optical connectivity cohort has positive standalone "
            "paper edge but the full no-displacement replay was blocked by single-"
            "ticker concentration. A production-visible fixed-notional paper sleeve "
            "that requires prior-close IWM 20d momentum to lead SPY by at least "
            "30bp may preserve the cross-window edge while avoiding core-sized "
            "winner concentration and weak small-cap tape."
        ),
        "change_type": "candidate_pool_iwm_confirmed_fixed_notional_paper_sleeve",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260523-003",
            "exp-20260524-026",
            "exp-20260524-035",
            "exp-20260525-002",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": (
            "production_visible_iwm_spy_smallcap_confirmation_plus_fixed_notional_"
            "sleeve_routing_for_existing_governed_optical_cohort"
        ),
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md three-window replay using exp-20260519-029 "
                "observation-universe OHLCV snapshots; target trades are discovered "
                "from expanded-universe replay, admitted only by prior-close IWM/SPY "
                "momentum confirmation, and added to baseline core equity at fixed "
                "paper notional without displacing core trades."
            ),
            "canonical_snapshot_target_coverage": canonical_coverage,
            "snapshot_coverage_note": (
                "The docs/backtesting.md canonical core snapshots preserve the "
                "standard date windows but do not contain the governed optical "
                "target tickers, so target-trade discovery uses the existing "
                "exp-20260519-029 observation-universe snapshots. Promotion still "
                "requires a shared/default-off adapter and parity validation."
            ),
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "target_theme": prior.TARGET_THEME,
            "target_segment": prior.TARGET_SEGMENT,
            "target_sector_map": prior.TARGET_SECTOR_MAP,
            "target_tickers": target_tickers,
            "target_universe": target_universe,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "source_ohlcv_experiment_id": prior.SOURCE_OHLCV_EXPERIMENT_ID,
            "paper_sleeve_routing": "additive_no_core_displacement",
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "market_confirmation": {
                "field": "prior_close_iwm_20d_momentum_minus_spy_20d_momentum",
                "min_spread": MIN_IWM_SPY_MOMENTUM_SPREAD,
                "lookback_trading_days": MOMENTUM_LOOKBACK_DAYS,
                "why_production_visible": (
                    "IWM and SPY OHLCV are free, deterministic, and available "
                    "before next-session paper entry."
                ),
            },
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "target cohort definition",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / capital allocation: existing governed AI optical "
                "candidates may be worth a small no-displacement paper sleeve only "
                "when small-cap risk appetite confirms the theme."
            ),
            "2_history_check": {
                "exp-20260523-003": (
                    "Direct optical core-pool admission failed because slot/capital "
                    "competition hurt all three windows."
                ),
                "exp-20260524-035": (
                    "No-displacement optical sleeve improved EV/PnL in all three "
                    "windows but failed concentration: CIEN positive share 52.53%."
                ),
                "exp-20260524-026": (
                    "Space communications IWM gate failed on a different cohort; "
                    "this tests optical connectivity no-displacement routing, not "
                    "Space core membership."
                ),
                "exp-20260525-002": (
                    "Low-deployment ETF small-cap breadth failed in the ETF overlay; "
                    "this test uses IWM/SPY as a risk-confirmation field for an "
                    "optical candidate sleeve."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows, positive aggregate EV/PnL, "
                "3/3 EV-improved windows, no PnL-regressed window, >=10 target "
                "paper trades across all 3 windows, drawdown drift <=0.5pp, "
                "survival >=5%, and target concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260525_003_ai_optical_iwm_confirmed_fixed_notional_sleeve.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "ohlcv_coverage": {
                "observation_snapshot_target_coverage": coverage,
                "canonical_snapshot_target_coverage": canonical_coverage,
                "note": (
                    "Canonical docs/backtesting snapshots have zero rows for many "
                    "optical target tickers; this replay therefore uses the same "
                    "date windows with exp-20260519-029 observation snapshots."
                ),
            },
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "universe_state records.theme/theme_segment/status/liquidity_tier/history_class",
                "target OHLCV rows in all three exp-20260519-029 snapshots",
                "IWM/SPY prior-close OHLCV for 20-day momentum confirmation",
                "risk_engine.SECTOR_MAP target tickers patched from TARGET_SECTOR_MAP in replay",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or core entry rule was added. The target cohort "
                "is evaluated as additive default-off paper, so core survival is "
                "unchanged from the baseline replay."
            ),
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
            "windows_ev_improved": aggregate["windows_ev_improved"],
            "windows_ev_regressed": aggregate["windows_ev_regressed"],
            "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
            "target_trade_count": target_summary["total_trade_count"],
            "target_trade_count_min": MIN_TARGET_TRADES,
            "target_windows": target_windows,
            "target_window_count_min": MIN_TARGET_WINDOWS,
            "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
            "survival_guard_passed": min_survival >= 0.05,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": target_summary[
                    "max_single_positive_pnl_share"
                ],
                "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
                "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "filtered_out_target_trades_by_window": filtered_out_by_window,
        "target_trade_summary": target_summary,
        "direct_core_admission_metrics": direct_core_admission_metrics,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "A retained result is a research lead only. Promotion requires a "
                "shared default-off optical paper adapter, daily report exposure, "
                "forward replacement-value ledger, and parity tests before any "
                "live/default behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because replay-safe attribution remains sparse; "
            "skipped SEC/event/state-surface/broad-market scalar retunes due recent "
            "anti-repeat gates; skipped raw core candidate-pool admission because "
            "optical direct core already failed. This uses a free, production-visible "
            "market confirmation field and fixed paper capital for an existing "
            "governed cohort."
        ),
        "interpretation": (
            "The optical IWM-confirmed fixed-notional paper route cleared the "
            "replay-only Gate 4 concentration and multi-window checks, but no "
            "production/shared policy was promoted. Treat this as a forward-watch "
            "sleeve lead, not a live capital change."
            if gate4_passed
            else (
                "The optical IWM-confirmed fixed-notional paper route did not clear "
                "Gate 4; keep the cohort in observation until forward replacement "
                "value or a stronger catalyst-quality field arrives."
            )
        ),
        "rejection_reason": None if gate4_passed else "; ".join(failed),
        "next_evidence_needed": (
            "Build a shared default-off optical paper adapter with IWM/SPY "
            "confirmation, daily report exposure, and forward replacement-value "
            "rows before any live/default behavior changes."
            if gate4_passed
            else (
                "Forward optical replacement-value outcomes or a materially new "
                "source/event-quality field; do not retry nearby optical routing "
                "thresholds on the frozen sample."
            )
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {filtered} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                filtered=len(payload["filtered_out_target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} AI Optical IWM-Confirmed Fixed-Notional Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route the fixed governed AI optical connectivity cohort into an additive fixed-notional default-off paper sleeve only when prior-close IWM 20d momentum leads SPY by at least 30bp.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- changed_variable: `{payload['changed_variable']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "AI optical IWM-confirmed fixed-notional sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": _repo_rel(ARTIFACT_MD),
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
