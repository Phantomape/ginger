"""exp-20260528-033: AI optical low close-location paper support scout.

This alpha search tests one production-visible, free-OHLCV allocation field on
top of the accepted AI optical IWM-confirmed default-off paper sleeve:
signal-day target close location <= 0.60 gets a small fixed-notional paper
support. Core entries, ranking, sizing, exits, heat, the accepted IWM market
confirmation, target cohort, LLM/news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260525_003_ai_optical_iwm_confirmed_fixed_notional_sleeve as source


EXPERIMENT_ID = "exp-20260528-033"
STEM = "ai_optical_low_close_location_support"
TRIAL_FAMILY = "ai_optical_signal_day_low_close_location_support"
TRIAL_VARIANT_ID = "close_location_lte_0p60_scalar_1p10_v1"
CHANGED_VARIABLE = "ai_optical_signal_day_low_close_location_notional_scalar_v1"

CLOSE_LOCATION_MAX = 0.60
SUPPORT_NOTIONAL_SCALAR = 1.10
MIN_SUPPORTED_TRADES = 4
MIN_SUPPORTED_WINDOWS = 2
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


def _load_ohlcv_rows(snapshot: str, ticker: str) -> list[dict[str, Any]]:
    payload = json.loads((REPO_ROOT / snapshot).read_text(encoding="utf-8"))
    ohlcv = payload.get("ohlcv") or payload
    rows = ohlcv.get(ticker.upper()) or []
    return [row for row in rows if isinstance(row, dict)]


def _signal_day_row(snapshot: str, ticker: str, entry_date: str) -> dict[str, Any] | None:
    rows = _load_ohlcv_rows(snapshot, ticker)
    dated = [
        (str(_row_value(row, "date"))[:10], row)
        for row in rows
        if _row_value(row, "date")
    ]
    prior_rows = [(date, row) for date, row in dated if date < entry_date]
    if not prior_rows:
        return None
    return max(prior_rows, key=lambda item: item[0])[1]


def _close_location(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    try:
        high = float(_row_value(row, "high"))
        low = float(_row_value(row, "low"))
        close = float(_row_value(row, "close"))
    except (TypeError, ValueError):
        return None
    if high <= low:
        return None
    return (close - low) / (high - low)


def _trade_key(trade: dict[str, Any]) -> str:
    return f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"


def _target_trade_support_context(
    *,
    snapshot: str,
    trade: dict[str, Any],
) -> dict[str, Any]:
    entry_date = str(trade.get("entry_date") or "")
    row = _signal_day_row(snapshot, str(trade.get("ticker") or ""), entry_date)
    location = _close_location(row)
    signal_date = str(_row_value(row, "date"))[:10] if row else None
    return {
        "rule_version": TRIAL_VARIANT_ID,
        "field": "signal_day_target_close_location",
        "signal_date": signal_date,
        "close_location": _round(location, 6),
        "max_close_location": CLOSE_LOCATION_MAX,
        "paper_notional_scalar": SUPPORT_NOTIONAL_SCALAR,
        "passed": location is not None and location <= CLOSE_LOCATION_MAX,
        "why_production_visible": (
            "The target ticker OHLCV row is the trading day before entry, so the "
            "field is known before next-session paper sizing."
        ),
    }


def _apply_low_close_support(
    trade: dict[str, Any],
    support_context: dict[str, Any],
) -> dict[str, Any]:
    if not support_context.get("passed"):
        return {**trade, "low_close_location_support": support_context}
    return {
        **trade,
        "paper_notional_usd": _round(
            float(trade.get("paper_notional_usd") or source.BASE_NOTIONAL_USD)
            * SUPPORT_NOTIONAL_SCALAR,
            2,
        ),
        "pnl": round(float(trade.get("pnl") or 0.0) * SUPPORT_NOTIONAL_SCALAR, 2),
        "low_close_location_support": support_context,
    }


def _trade_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    supported_count = 0
    supported_pnl = 0.0
    for trades in target_trades_by_window.values():
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl
            if (trade.get("low_close_location_support") or {}).get("passed"):
                supported_count += 1
                supported_pnl += pnl

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
        "supported_trade_count": supported_count,
        "supported_trade_pnl": round(supported_pnl, 2),
    }


def _supported_trade_summary(
    supported_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    summary = _trade_summary(supported_trades_by_window)
    summary["windows_with_supported_trades"] = [
        label for label, trades in supported_trades_by_window.items() if trades
    ]
    return summary


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
        "supported_trade_count_sum": sum(
            row["supported_trade_count"] for row in rows.values()
        ),
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
    core_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    after_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    supported_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
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

            before_trades: list[dict[str, Any]] = []
            after_trades: list[dict[str, Any]] = []
            supported_trades: list[dict[str, Any]] = []
            rejected_trades: list[dict[str, Any]] = []
            for trade in raw_target_trades:
                key = _trade_key(trade)
                iwm_state = iwm_state_by_key[key]
                paper_trade = source._fixed_notional_trade(trade, iwm_state)
                if not iwm_state.get("passed"):
                    rejected_trades.append(paper_trade)
                    continue

                support_context = _target_trade_support_context(
                    snapshot=WINDOWS[label]["snapshot"],
                    trade=paper_trade,
                )
                after_trade = _apply_low_close_support(paper_trade, support_context)
                before_trades.append({**paper_trade, "low_close_location_support": support_context})
                after_trades.append(after_trade)
                if support_context["passed"]:
                    supported_trades.append(after_trade)

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
            supported_trades_by_window[label] = supported_trades
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
                "supported_trade_count": len(supported_trades),
                "rejected_trade_count": len(rejected_trades),
            }

    aggregate = _aggregate(window_rows)
    before_summary = _trade_summary(before_trades_by_window)
    after_summary = _trade_summary(after_trades_by_window)
    supported_summary = _supported_trade_summary(supported_trades_by_window)
    after_windows = after_summary["windows_with_target_trades"]
    supported_windows = supported_summary["windows_with_supported_trades"]
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
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and supported_summary["total_trade_count"] >= MIN_SUPPORTED_TRADES
        and len(supported_windows) >= MIN_SUPPORTED_WINDOWS
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
    if aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression_vs_accepted_iwm_only")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression_vs_accepted_iwm_only")
    if supported_summary["total_trade_count"] < MIN_SUPPORTED_TRADES:
        failed.append("supported_sample_too_small")
    if len(supported_windows) < MIN_SUPPORTED_WINDOWS:
        failed.append("supported_window_coverage_too_small")
    if len(after_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    decision = (
        "accepted_ai_optical_low_close_location_notional_support"
        if gate4_passed
        else "rejected_ai_optical_low_close_location_notional_support"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Accepted AI optical IWM-confirmed paper trades with low or mid "
            "signal-day close location may represent non-exhaustion demand rather "
            "than a spent intraday move, so a small fixed-notional paper support "
            "could improve the governed optical sleeve without adding tickers."
        ),
        "change_type": "default_off_paper_notional_support",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260525-003",
            "exp-20260525-005",
            "exp-20260525-018",
            "exp-20260526-012",
            "exp-20260528-022",
            "exp-20260528-026",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_ohlcv_signal_day_close_location_field_on_governed_optical_pool",
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md standard three-window dates; before is the "
                "accepted exp-20260525-005 IWM-only AI optical paper adapter. "
                "Target trade discovery uses the accepted exp-20260519-029 "
                "observation-universe OHLCV snapshots because canonical core "
                "snapshots do not cover the governed optical tickers."
            ),
            "windows": WINDOWS,
            "canonical_snapshot_target_coverage": canonical_coverage,
            "observation_snapshot_target_coverage": coverage,
            "before_policy": "accepted exp-20260525-005 IWM-only optical paper adapter",
            "after_policy": "same adapter plus close_location<=0.60 paper notional support",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "target_theme": source.prior.TARGET_THEME,
            "target_segment": source.prior.TARGET_SEGMENT,
            "target_tickers": target_tickers,
            "target_universe": target_universe,
            "paper_notional_usd_before": source.BASE_NOTIONAL_USD,
            "paper_notional_scalar_after": SUPPORT_NOTIONAL_SCALAR,
            "low_close_location_support": {
                "field": "target_ticker_signal_day_close_location",
                "max_close_location": CLOSE_LOCATION_MAX,
                "why_free_data_edge": (
                    "OHLCV is free, deterministic, and known from the target "
                    "ticker's prior trading day before paper entry."
                ),
            },
            "locked_variables": [
                "governed optical ticker cohort",
                "accepted IWM/SPY market confirmation",
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
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_supported_trades": MIN_SUPPORTED_TRADES,
                "min_supported_windows": MIN_SUPPORTED_WINDOWS,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: a free OHLCV close-location field may identify "
                "which accepted optical paper entries deserve slightly higher "
                "paper notional."
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
                    "retune the IWM threshold."
                ),
                "exp-20260526-012": (
                    "QQQ backup expansion added trades but regressed a window; this "
                    "keeps the accepted IWM-only candidate set fixed."
                ),
                "exp-20260528-022/026": (
                    "VBB and Space high-close supports worked on other cohorts. A "
                    "read-only optical audit showed optical high-close support was "
                    "not attractive, so this tests the inverse low/mid close field."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three windows, before=accepted IWM-only paper adapter and "
                "after=only close_location<=0.60 notional scalar. Require positive "
                "aggregate EV/PnL, no EV/PnL-regressed window, >=4 supported trades "
                "across >=2 windows, drawdown drift <=0.5pp, survival >=5%, and "
                "concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260528_033_ai_optical_low_close_location_support.py"
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
                    "Canonical core snapshots preserve standard windows but lack "
                    "full optical ticker coverage; this reuses the accepted optical "
                    "adapter's observation-universe snapshots."
                ),
            },
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "universe_state records.theme/theme_segment/status/liquidity_tier/history_class",
                "target OHLCV rows in all three observation snapshots",
                "IWM/SPY prior-close 20-day momentum",
                "target ticker prior trading-day high/low/close for close_location",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter, candidate-pool expansion, or live entry rule was "
                "added. This only rescales a subset of already accepted default-off "
                "paper trades."
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
            "supported_trade_count": supported_summary["total_trade_count"],
            "supported_trade_count_min": MIN_SUPPORTED_TRADES,
            "supported_windows": supported_windows,
            "supported_window_count_min": MIN_SUPPORTED_WINDOWS,
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
        "supported_trades_by_window": supported_trades_by_window,
        "rejected_trades_by_window": rejected_trades_by_window,
        "before_trade_summary": before_summary,
        "after_trade_summary": after_summary,
        "supported_trade_summary": supported_summary,
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
            "Skipped LLM soft-ranking because replay-safe attribution remains "
            "sparse; skipped nearby Companyfacts/VBB/Space scalar retunes due the "
            "playbook freeze risk; skipped optical QQQ/IWM threshold retunes after "
            "the recent QQQ expansion failed. This tests one free OHLCV allocation "
            "field on a governed candidate pool."
        ),
        "interpretation": (
            "The low close-location support passed all gates and is eligible for a "
            "separate default-off adapter parity change."
            if gate4_passed
            else (
                "The low close-location support improved aggregate EV/PnL but did "
                "not clear Gate 4 because the supported sample was too small; keep "
                "it rejected and do not promote production/shared policy."
            )
        ),
        "rejection_reason": None if gate4_passed else "; ".join(failed),
        "next_evidence_needed": (
            "Forward optical replacement-value rows or a materially larger governed "
            "optical sample before retrying close-location notional support."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Supported |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {supported} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                supported=len(payload["supported_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} AI Optical Low Close-Location Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: apply a 1.10x fixed-notional paper scalar only to accepted AI optical IWM-confirmed paper trades whose target ticker signal-day close location is <= 0.60.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- trial_variant_id: `{payload['trial_variant_id']}`",
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
            f"- supported trades: `{payload['supported_trade_summary']['total_trade_count']}` across `{len(payload['supported_trade_summary']['windows_with_supported_trades'])}` windows",
            f"- before target trades: `{payload['before_trade_summary']['total_trade_count']}`",
            f"- after target trades: `{payload['after_trade_summary']['total_trade_count']}`",
            f"- max single positive share: `{payload['after_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['after_trade_summary']['positive_pnl_hhi']}`",
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
            f"Rejection reason: `{payload['rejection_reason']}`.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket: dict[str, Any] = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8-sig"))
    ticket.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "rejection_reason": payload["rejection_reason"],
            },
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _update_ticket(payload)
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
                    "supported_trade_summary": payload["supported_trade_summary"],
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
