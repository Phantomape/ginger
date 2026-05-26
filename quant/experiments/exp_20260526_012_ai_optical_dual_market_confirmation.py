"""exp-20260526-012: AI optical dual market-confirmation expansion.

This alpha search tests one candidate-pool expansion variable on top of the
accepted default-off AI optical paper sleeve from exp-20260525-005:
admit the governed optical candidate when either the accepted IWM/SPY small-cap
confirmation passes or QQQ 20-day momentum leads SPY. The QQQ leg is a free,
production-visible growth-tape field and is evaluated only as default-off paper.

Core entries, ranking, sizing, exits, heat, LLM/news, and live/default orders
are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260525_003_ai_optical_iwm_confirmed_fixed_notional_sleeve as source


EXPERIMENT_ID = "exp-20260526-012"
STEM = "ai_optical_dual_market_confirmation"
TRIAL_FAMILY = "governed_ai_optical_dual_market_confirmation_candidate_expansion"
CHANGED_VARIABLE = "ai_optical_iwm_or_qqq_market_confirmation_candidate_expansion_v1"

MIN_QQQ_SPY_MOMENTUM_SPREAD = 0.0
MOMENTUM_LOOKBACK_DAYS = 20
MIN_AFTER_TRADES = 10
MIN_ADDED_TRADES = 2
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45

REPO_ROOT = source.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
WINDOWS = source.WINDOWS


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
        series[str(date)[:10]] = float(close)
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


def _qqq_market_confirmation(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    qqq = _load_close_series(snapshot, "QQQ")
    spy = _load_close_series(snapshot, "SPY")
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = _trade_key(trade)
        entry_date = str(trade.get("entry_date") or "")
        as_of = _previous_market_date(spy, entry_date)
        qqq_mom = _momentum(qqq, as_of, MOMENTUM_LOOKBACK_DAYS) if as_of else None
        spy_mom = _momentum(spy, as_of, MOMENTUM_LOOKBACK_DAYS) if as_of else None
        spread = (
            qqq_mom - spy_mom
            if qqq_mom is not None and spy_mom is not None
            else None
        )
        out[key] = {
            "market_state_as_of": as_of,
            "qqq_momentum20": _round(qqq_mom, 6),
            "spy_momentum20": _round(spy_mom, 6),
            "qqq_spy_momentum_spread": _round(spread, 6),
            "min_qqq_spy_momentum_spread": MIN_QQQ_SPY_MOMENTUM_SPREAD,
            "passed": spread is not None and spread > MIN_QQQ_SPY_MOMENTUM_SPREAD,
            "rule_version": "qqq_gt_spy20_close_to_close_v1",
        }
    return out


def _trade_key(trade: dict[str, Any]) -> str:
    return f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"


def _dual_market_trade(
    trade: dict[str, Any],
    *,
    iwm_state: dict[str, Any],
    qqq_state: dict[str, Any],
) -> dict[str, Any]:
    paper_trade = source._fixed_notional_trade(trade, iwm_state)
    iwm_passed = bool(iwm_state.get("passed"))
    qqq_passed = bool(qqq_state.get("passed"))
    paper_trade["market_confirmation"] = {
        "rule_version": "ai_optical_iwm_or_qqq_market_confirmation_v1",
        "passed": iwm_passed or qqq_passed,
        "accepted_iwm_confirmation": iwm_state,
        "qqq_backup_confirmation": qqq_state,
        "expanded_by_qqq_only": (not iwm_passed) and qqq_passed,
        "baseline_iwm_only_passed": iwm_passed,
    }
    return paper_trade


def _trade_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    qqq_only_count = 0
    qqq_only_pnl = 0.0
    for trades in target_trades_by_window.values():
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl
            market = trade.get("market_confirmation") or {}
            if market.get("expanded_by_qqq_only"):
                qqq_only_count += 1
                qqq_only_pnl += pnl

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
        "qqq_only_added_trade_count": qqq_only_count,
        "qqq_only_added_pnl": round(qqq_only_pnl, 2),
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "before_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "before_total_pnl_sum": _round(pnl_before, 2),
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
        "before_target_trade_count_sum": sum(
            row["before_target_trade_count"] for row in rows.values()
        ),
        "after_target_trade_count_sum": sum(
            row["after_target_trade_count"] for row in rows.values()
        ),
        "added_target_trade_count_sum": sum(row["added_trade_count"] for row in rows.values()),
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = source.prior._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    target_universe = source.prior._target_universe()
    target_tickers = target_universe["target_tickers"]
    coverage = source.prior._snapshot_coverage(target_tickers)
    canonical_coverage = source.prior._snapshot_coverage_for_windows(
        target_tickers,
        source.prior.CANONICAL_WINDOWS,
    )
    if not coverage["passed"]:
        raise RuntimeError(f"Gate 2 OHLCV coverage failed: {coverage}")

    base_universe = sorted(source.prior.get_universe())
    expanded_universe = sorted(set(base_universe) | set(target_tickers))
    target_set = set(target_tickers)

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    core_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    after_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    added_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    rejected_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    with source.prior._target_sector_patch(target_tickers):
        for label in WINDOWS:
            print(f"[{label}] baseline core universe")
            before_result = source.prior.base._run_window(label, base_universe)
            print(f"[{label}] expanded universe for optical target discovery")
            expanded_result = source.prior.base._run_window(label, expanded_universe)

            raw_target_trades = source.prior._target_trades(expanded_result, target_set)
            iwm_state_by_key = source._market_confirmation(
                WINDOWS[label]["snapshot"],
                raw_target_trades,
            )
            qqq_state_by_key = _qqq_market_confirmation(
                WINDOWS[label]["snapshot"],
                raw_target_trades,
            )

            before_trades: list[dict[str, Any]] = []
            after_trades: list[dict[str, Any]] = []
            added_trades: list[dict[str, Any]] = []
            rejected_trades: list[dict[str, Any]] = []
            for trade in raw_target_trades:
                key = _trade_key(trade)
                iwm_state = iwm_state_by_key[key]
                qqq_state = qqq_state_by_key[key]
                paper_trade = _dual_market_trade(
                    trade,
                    iwm_state=iwm_state,
                    qqq_state=qqq_state,
                )
                if iwm_state.get("passed"):
                    before_trades.append(paper_trade)
                if paper_trade["market_confirmation"]["passed"]:
                    after_trades.append(paper_trade)
                    if paper_trade["market_confirmation"]["expanded_by_qqq_only"]:
                        added_trades.append(paper_trade)
                else:
                    rejected_trades.append(paper_trade)

            before_overlay = source.prior._overlay_from_target_trades(
                before_result,
                before_trades,
            )
            after_overlay = source.prior._overlay_from_target_trades(
                before_result,
                after_trades,
            )
            core = source.prior.overlay_helper._metrics(before_result)
            before = source.prior.overlay_helper._metrics_with_overlay(
                before_result,
                before_overlay,
            )
            after = source.prior.overlay_helper._metrics_with_overlay(
                before_result,
                after_overlay,
            )
            delta = source.prior.overlay_helper._delta(after, before)

            core_metrics[label] = core
            before_metrics[label] = before
            after_metrics[label] = after
            before_trades_by_window[label] = before_trades
            after_trades_by_window[label] = after_trades
            added_trades_by_window[label] = added_trades
            rejected_trades_by_window[label] = rejected_trades
            window_rows[label] = {
                "core": core,
                "before": before,
                "after": after,
                "delta": delta,
                "before_overlay_total_pnl": before_overlay["overlay_total_pnl"],
                "after_overlay_total_pnl": after_overlay["overlay_total_pnl"],
                "before_target_trade_count": len(before_trades),
                "after_target_trade_count": len(after_trades),
                "added_trade_count": len(added_trades),
                "rejected_trade_count": len(rejected_trades),
            }

    aggregate = _aggregate(window_rows)
    before_summary = _trade_summary(before_trades_by_window)
    after_summary = _trade_summary(after_trades_by_window)
    added_summary = _trade_summary(added_trades_by_window)
    after_windows = after_summary["windows_with_target_trades"]
    concentration_passed = (
        after_summary["max_single_positive_pnl_share"] is not None
        and after_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and after_summary["positive_pnl_hhi"] is not None
        and after_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values())
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and after_summary["total_trade_count"] >= MIN_AFTER_TRADES
        and added_summary["total_trade_count"] >= MIN_ADDED_TRADES
        and len(after_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )

    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive_vs_accepted_iwm_only")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive_vs_accepted_iwm_only")
    if aggregate["windows_ev_improved"] != len(WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression_vs_accepted_iwm_only")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression_vs_accepted_iwm_only")
    if after_summary["total_trade_count"] < MIN_AFTER_TRADES:
        failed.append("after_sample_too_small")
    if added_summary["total_trade_count"] < MIN_ADDED_TRADES:
        failed.append("added_sample_too_small")
    if len(after_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    decision = (
        "accepted_ai_optical_dual_market_confirmation_candidate_expansion"
        if gate4_passed
        else "rejected_ai_optical_dual_market_confirmation_candidate_expansion"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted AI optical IWM-confirmed default-off paper sleeve may be "
            "too narrowly tied to small-cap breadth. Because optical AI demand is "
            "growth-led, a QQQ-over-SPY backup confirmation may expand the same "
            "governed candidate pool without adding arbitrary tickers or changing "
            "core/live behavior."
        ),
        "change_type": "candidate_pool_market_confirmation_expansion",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "iwm_or_qqq_20d_market_confirmation_v1",
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260525-003",
            "exp-20260525-005",
            "exp-20260525-018",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_free_qqq_growth_tape_confirmation",
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md standard three-window dates; target trade "
                "discovery uses the accepted exp-20260519-029 observation-universe "
                "OHLCV snapshots because canonical core snapshots do not cover the "
                "governed optical tickers."
            ),
            "windows": WINDOWS,
            "canonical_snapshot_target_coverage": canonical_coverage,
            "observation_snapshot_target_coverage": coverage,
            "before_policy": "accepted exp-20260525-005 IWM-only optical paper adapter",
            "after_policy": "IWM-only adapter plus QQQ-over-SPY backup confirmation",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "target_theme": source.prior.TARGET_THEME,
            "target_segment": source.prior.TARGET_SEGMENT,
            "target_tickers": target_tickers,
            "target_universe": target_universe,
            "paper_notional_usd": source.BASE_NOTIONAL_USD,
            "baseline_iwm_confirmation": {
                "field": "prior_close_iwm_20d_momentum_minus_spy_20d_momentum",
                "min_spread": source.MIN_IWM_SPY_MOMENTUM_SPREAD,
                "lookback_trading_days": source.MOMENTUM_LOOKBACK_DAYS,
            },
            "new_qqq_backup_confirmation": {
                "field": "prior_close_qqq_20d_momentum_minus_spy_20d_momentum",
                "min_spread": MIN_QQQ_SPY_MOMENTUM_SPREAD,
                "lookback_trading_days": MOMENTUM_LOOKBACK_DAYS,
                "why_production_visible": (
                    "QQQ and SPY OHLCV are free, deterministic, and known before "
                    "next-session paper entry."
                ),
            },
            "locked_variables": [
                "governed optical ticker cohort",
                "paper notional",
                "core universe",
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "compare_against": "accepted_iwm_only_adapter",
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_after_trades": MIN_AFTER_TRADES,
                "min_added_trades": MIN_ADDED_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool: expand the accepted governed AI optical paper "
                "candidate set using a free growth-tape confirmation field."
            ),
            "2_history_check": {
                "exp-20260525-003": (
                    "IWM-only fixed-notional optical paper sleeve passed vs core "
                    "with +0.4482 EV and +$7372.78 PnL."
                ),
                "exp-20260525-005": (
                    "Promoted the IWM-only route to a shared default-off paper "
                    "adapter; live/default orders remain disabled."
                ),
                "exp-20260525-018": (
                    "IWM/SPY spread-strength was not monotonic, so this does not "
                    "retune the IWM threshold or notional. It adds a distinct QQQ "
                    "growth-tape backup field."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three windows, before=accepted IWM-only paper adapter and "
                "after=IWM-or-QQQ expansion. Require positive aggregate EV/PnL, "
                "3/3 EV-improved windows, no PnL-regressed window, drawdown drift "
                "<=0.5pp, survival >=5%, and concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260526_012_ai_optical_dual_market_confirmation.py"
            ),
        },
        "gate1": {
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "baseline_policy": "accepted_exp_20260525_005_iwm_only_adapter",
            "baseline_metrics": before_metrics,
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "ohlcv_coverage": {
                "observation_snapshot_target_coverage": coverage,
                "canonical_snapshot_target_coverage": canonical_coverage,
                "note": (
                    "Canonical core snapshots preserve the standard windows but "
                    "lack full optical ticker coverage; the accepted optical "
                    "adapter evidence uses the observation-universe snapshots."
                ),
            },
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "universe_state records.theme/theme_segment/status/liquidity_tier/history_class",
                "target OHLCV rows in all three observation snapshots",
                "IWM/SPY prior-close 20-day momentum",
                "QQQ/SPY prior-close 20-day momentum",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": True,
            "minimum_core_survival_rate": _round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or live entry rule was added. This only expands "
                "the default-off paper candidate set for a governed cohort."
            ),
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
            "windows_ev_improved": aggregate["windows_ev_improved"],
            "windows_ev_regressed": aggregate["windows_ev_regressed"],
            "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
            "before_target_trade_count": before_summary["total_trade_count"],
            "after_target_trade_count": after_summary["total_trade_count"],
            "added_trade_count": added_summary["total_trade_count"],
            "added_trade_count_min": MIN_ADDED_TRADES,
            "target_windows": after_windows,
            "target_window_count_min": MIN_TARGET_WINDOWS,
            "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
            "survival_guard_passed": min_survival >= 0.05,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": after_summary[
                    "max_single_positive_pnl_share"
                ],
                "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi": after_summary["positive_pnl_hhi"],
                "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            },
        },
        "core_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "before_trades_by_window": before_trades_by_window,
        "after_trades_by_window": after_trades_by_window,
        "added_trades_by_window": added_trades_by_window,
        "rejected_trades_by_window": rejected_trades_by_window,
        "before_trade_summary": before_summary,
        "after_trade_summary": after_summary,
        "added_trade_summary": added_summary,
        "window_rows": window_rows,
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
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking, SEC semantics, expectation revision, VCP "
            "retunes, state-surface scalars, and recent mechanical OHLCV pattern "
            "retreads. This tests a single free-data growth-tape confirmation on "
            "an already governed production-visible paper adapter."
        ),
        "interpretation": (
            "The QQQ backup confirmation improved the accepted optical adapter "
            "in all three windows and can be promoted only after shared adapter "
            "and parity updates."
            if gate4_passed
            else (
                "The QQQ backup confirmation did not improve the accepted optical "
                "adapter robustly across the three windows. Keep the current "
                "IWM-only adapter and do not promote the OR gate."
            )
        ),
        "rejection_reason": None if gate4_passed else "; ".join(failed),
        "next_retry_requires": [
            "new_forward_rows",
            "materially_new_source_or_event_quality_field",
            "no nearby IWM/QQQ threshold or OR-gate retune on frozen windows",
        ],
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Before trades | After trades | Added |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {before_trades} | {after_trades} | {added} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                before_trades=len(payload["before_trades_by_window"][label]),
                after_trades=len(payload["after_trades_by_window"][label]),
                added=len(payload["added_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} AI Optical Dual Market Confirmation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: expand the accepted AI optical IWM-only default-off paper route to admit candidates when either IWM/SPY or QQQ/SPY market confirmation passes.",
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
            f"- EV delta vs accepted IWM-only: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs accepted IWM-only: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- added trades: `{payload['added_trade_summary']['total_trade_count']}` / `${payload['added_trade_summary']['total_pnl']}`",
            f"- after max single positive share: `{payload['after_trade_summary']['max_single_positive_pnl_share']}`",
            f"- after positive PnL HHI: `{payload['after_trade_summary']['positive_pnl_hhi']}`",
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
            "title": "AI optical QQQ backup confirmation",
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
                    "added_trade_summary": payload["added_trade_summary"],
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
