"""exp-20260530-017: pre-entry catalyst core risk top-up scout.

This alpha search tests one risk-allocation variable: a small risk-budget
top-up for already-selected core trend/breakout candidates that have a
PIT-safe high-confidence catalyst in the ten calendar days before the signal.

The runner is replay-only. It does not change shared production policy,
run.py, order generation, ranking, exits, or the live/default order path.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260530-017"
STEM = "pre_entry_catalyst_core_risk_topup"
TRIAL_FAMILY = "pre_entry_catalyst_core_risk_allocation"
TRIAL_VARIANT_ID = "high_confidence_catalyst_core_risk_topup_v1"
CHANGED_VARIABLE = "pre_entry_high_confidence_catalyst_core_risk_scalar"
SIZING_KEY = "pre_entry_high_confidence_catalyst_core_risk_multiplier_applied"
BASELINE_VARIANT = "scalar_1p00_control"
SCALARS = [1.05, 1.10, 1.15]
MAX_DRAWDOWN_WORSE = 0.005
MIN_SURVIVAL_RATE = 0.05
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine, DEFAULT_CONFIG  # noqa: E402
from constants import MAX_POSITION_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import backtester as backtester_module  # noqa: E402
import feature_layer  # noqa: E402
import portfolio_engine  # noqa: E402
from exp_20260530_014_pre_entry_catalyst_attribution import (  # noqa: E402
    HIGH_CONFIDENCE_CATEGORIES,
    LOOKBACK_CALENDAR_DAYS,
    _event_index,
    _events_for_trade,
)


WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_017_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_CARD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): _safe(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_safe(value) for value in obj]
    if isinstance(obj, tuple):
        return [_safe(value) for value in obj]
    if isinstance(obj, set):
        return sorted(_safe(value) for value in obj)
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_text(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    if "T" in text:
        text = text.split("T", 1)[0]
    return text[:10]


def _result_metrics(result: dict[str, Any]) -> dict[str, Any]:
    ret = result.get("strategy_total_return_pct")
    if ret is None:
        ret = (result.get("benchmarks") or {}).get("strategy_total_return_pct")
    if ret is None:
        ret = result.get("total_return_pct")
    trades = result.get("trade_count")
    if trades is None:
        trades = result.get("total_trades")
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(ret, 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": trades,
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = _round(after_value - before_value, 6)
    return out


def _aggregate(rows: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    metrics = []
    for row in rows.values():
        bucket = row[key]
        metrics.append(bucket.get("metrics") or bucket.get(key) or bucket)
    return {
        "expected_value_score_sum": _round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics), 4
        ),
        "strategy_total_return_pct_sum": _round(
            sum(float(row.get("strategy_total_return_pct") or 0.0) for row in metrics), 4
        ),
        "total_pnl_sum": _round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics), 2
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in metrics),
        "signals_generated_sum": sum(
            int(row.get("signals_generated") or 0) for row in metrics
        ),
        "signals_survived_sum": sum(
            int(row.get("signals_survived") or 0) for row in metrics
        ),
        "min_survival_rate": _round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics), 4
        ),
        "max_drawdown_pct_max": _round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics), 4
        ),
    }


def _trade_key(trade: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(trade.get("ticker") or "").upper(),
        str(trade.get("strategy") or ""),
        str(trade.get("entry_date") or ""),
        str(trade.get("exit_date") or ""),
    )


def _incremental_trade_rows(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    window_label: str,
) -> list[dict[str, Any]]:
    before_by_key = {_trade_key(row): row for row in before.get("trades") or []}
    out: list[dict[str, Any]] = []
    for row in after.get("trades") or []:
        multipliers = row.get("sizing_multipliers") or {}
        if SIZING_KEY not in multipliers:
            continue
        key = _trade_key(row)
        baseline = before_by_key.get(key)
        if not baseline:
            continue
        delta = float(row.get("pnl") or 0.0) - float(baseline.get("pnl") or 0.0)
        out.append(
            {
                "window": window_label,
                "ticker": key[0],
                "strategy": key[1],
                "entry_date": key[2],
                "exit_date": key[3],
                "scalar": multipliers.get(SIZING_KEY),
                "before_pnl": _round(baseline.get("pnl"), 2),
                "after_pnl": _round(row.get("pnl"), 2),
                "incremental_pnl": _round(delta, 2),
                "shares_before": baseline.get("shares"),
                "shares_after": row.get("shares"),
            }
        )
    return out


def _concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive_by_ticker: dict[str, float] = {}
    for row in rows:
        delta = float(row.get("incremental_pnl") or 0.0)
        if delta <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        positive_by_ticker[ticker] = positive_by_ticker.get(ticker, 0.0) + delta
    total = sum(positive_by_ticker.values())
    if total <= 0:
        return {
            "positive_incremental_pnl": 0.0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_ticker": None,
            "passed": False,
        }
    shares = {ticker: value / total for ticker, value in positive_by_ticker.items()}
    top_ticker, top_share = max(shares.items(), key=lambda item: item[1])
    hhi = sum(share * share for share in shares.values())
    return {
        "positive_incremental_pnl": _round(total, 2),
        "max_single_positive_pnl_share": _round(top_share, 6),
        "positive_pnl_hhi": _round(hhi, 6),
        "top_positive_ticker": top_ticker,
        "passed": top_share <= MAX_SINGLE_POSITIVE_SHARE and hhi <= MAX_POSITIVE_HHI,
    }


def _run_window(universe: list[str], window: dict[str, str]) -> dict[str, Any]:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        config=dict(DEFAULT_CONFIG),
        ohlcv_snapshot_path=window["snapshot"],
    )
    return engine.run()


def _run_after_window(
    universe: list[str],
    window: dict[str, str],
    event_index: dict[str, Any],
    scalar: float,
) -> dict[str, Any]:
    # BacktestEngine imports compute_features and size_signals inside run(). To
    # make the signal date available to size_signals without touching shared
    # modules, patch compute_features globally and wrap size_signals with a
    # tiny feature cache refreshed by compute_features side effects.
    original_compute_features = feature_layer.compute_features
    original_size_signals = portfolio_engine.size_signals
    original_multiplier_keys = backtester_module.SIZING_MULTIPLIER_KEYS

    if SIZING_KEY not in original_multiplier_keys:
        backtester_module.SIZING_MULTIPLIER_KEYS = (
            tuple(original_multiplier_keys) + (SIZING_KEY,)
        )

    daily_features: dict[str, dict[str, Any]] = {}

    def patched_compute_features(ticker, ohlcv_data, earnings_data):
        features = original_compute_features(ticker, ohlcv_data, earnings_data)
        if features is not None and ohlcv_data is not None and len(ohlcv_data) > 0:
            features["_signal_date"] = str(ohlcv_data.index[-1].date())
            daily_features[str(ticker).upper()] = features
        return features

    def patched_size_signals(signals, portfolio_value, risk_pct=None):
        for signal in signals or []:
            ticker = str(signal.get("ticker") or "").upper()
            features = daily_features.get(ticker) or {}
            signal_date_text = features.get("_signal_date")
            if signal_date_text and not signal.get("signal_date"):
                signal["signal_date"] = signal_date_text
            has_catalyst = False
            high_conf_events: list[dict[str, Any]] = []
            if ticker and signal_date_text:
                signal_date = datetime.strptime(signal_date_text, "%Y-%m-%d").date()
                high_conf_events = [
                    row
                    for row in _events_for_trade(event_index, ticker, signal_date)
                    if row.get("high_confidence")
                    and row.get("category") in HIGH_CONFIDENCE_CATEGORIES
                ]
                has_catalyst = bool(high_conf_events)
            signal["pre_entry_high_confidence_catalyst"] = has_catalyst
            if high_conf_events:
                signal["pre_entry_high_confidence_catalyst_events"] = high_conf_events[:5]

        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for signal in sized or []:
            sizing = signal.get("sizing") or {}
            sizing.setdefault(SIZING_KEY, 1.0)
            strategy = signal.get("strategy")
            if (
                not signal.get("pre_entry_high_confidence_catalyst")
                or strategy not in {"trend_long", "breakout_long"}
            ):
                continue
            old_shares = int(sizing.get("shares_to_buy") or 0)
            if old_shares <= 0:
                continue
            entry = _as_float(sizing.get("entry_price") or signal.get("entry_price"))
            if not entry or entry <= 0:
                continue
            max_shares = max(
                old_shares,
                int(math.floor(portfolio_value * MAX_POSITION_PCT / entry)),
            )
            new_shares = min(max_shares, int(math.floor(old_shares * scalar)))
            if new_shares <= old_shares:
                continue
            net_risk_per_share = _as_float(sizing.get("net_risk_per_share")) or 0.0
            position_value = entry * new_shares
            risk_amount = net_risk_per_share * new_shares
            sizing["pre_entry_high_confidence_catalyst_baseline_shares"] = old_shares
            sizing["pre_entry_high_confidence_catalyst_new_shares"] = new_shares
            sizing["shares_to_buy"] = new_shares
            sizing["position_value_usd"] = round(position_value, 2)
            sizing["position_pct_of_portfolio"] = (
                round(position_value / portfolio_value, 4) if portfolio_value else 0.0
            )
            sizing["risk_amount_usd"] = round(risk_amount, 2)
            sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
            sizing[SIZING_KEY] = scalar
        return sized

    feature_layer.compute_features = patched_compute_features
    portfolio_engine.size_signals = patched_size_signals
    try:
        return _run_window(universe, window)
    finally:
        feature_layer.compute_features = original_compute_features
        portfolio_engine.size_signals = original_size_signals
        backtester_module.SIZING_MULTIPLIER_KEYS = original_multiplier_keys


def _evaluate_gate(
    variant_rows: dict[str, dict[str, Any]],
    before_aggregate: dict[str, Any],
    after_aggregate: dict[str, Any],
    incremental_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    aggregate_ev_delta = (
        after_aggregate["expected_value_score_sum"]
        - before_aggregate["expected_value_score_sum"]
    )
    aggregate_pnl_delta = after_aggregate["total_pnl_sum"] - before_aggregate["total_pnl_sum"]
    concentration = _concentration(incremental_rows)
    window_ev_regressions = [
        label
        for label, row in variant_rows.items()
        if (row["delta"].get("expected_value_score") or 0.0) < 0
    ]
    window_pnl_regressions = [
        label
        for label, row in variant_rows.items()
        if (row["delta"].get("total_pnl") or 0.0) < 0
    ]
    max_drawdown_worse = max(
        (row["delta"].get("max_drawdown_pct") or 0.0) for row in variant_rows.values()
    )
    target_trade_count = len(incremental_rows)
    target_windows = sorted({row["window"] for row in incremental_rows})
    failed_reasons = []
    if aggregate_ev_delta <= 0:
        failed_reasons.append("aggregate_ev_not_positive")
    if aggregate_pnl_delta <= 0:
        failed_reasons.append("aggregate_pnl_not_positive")
    if window_ev_regressions:
        failed_reasons.append("ev_regressed_window")
    if window_pnl_regressions:
        failed_reasons.append("pnl_regressed_window")
    if after_aggregate["min_survival_rate"] < MIN_SURVIVAL_RATE:
        failed_reasons.append("survival_rate_below_5pct")
    if max_drawdown_worse > MAX_DRAWDOWN_WORSE:
        failed_reasons.append("max_drawdown_drift_above_guardrail")
    if target_trade_count < 10:
        failed_reasons.append("target_trade_count_below_10")
    if len(target_windows) < 2:
        failed_reasons.append("target_window_coverage_below_2")
    if not concentration["passed"]:
        failed_reasons.append("target_concentration_failed")
    return {
        "passed": not failed_reasons,
        "failed_reasons": failed_reasons,
        "rule": (
            "Pass if aggregate EV/PnL improve, no canonical window regresses on "
            "EV or PnL, min survival stays >=5%, max drawdown drift <=0.5pp, "
            ">=10 adjusted trades across >=2 windows, and positive incremental "
            "PnL concentration stays below 40% single ticker / 0.30 HHI."
        ),
        "aggregate_ev_delta": _round(aggregate_ev_delta, 6),
        "aggregate_pnl_delta": _round(aggregate_pnl_delta, 2),
        "windows_ev_regressed": window_ev_regressions,
        "windows_pnl_regressed": window_pnl_regressions,
        "max_drawdown_worse": _round(max_drawdown_worse, 6),
        "target_trade_count": target_trade_count,
        "target_windows": target_windows,
        "concentration": concentration,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Pre-Entry Catalyst Core Risk Top-Up",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: small risk-budget scalar for already-selected "
            "core trend/breakout candidates with a PIT high-confidence "
            "pre-entry catalyst."
        ),
        "",
        "## Best Variant",
        "",
        f"- Variant: `{best['variant_id']}`",
        f"- Scalar: `{best['scalar']}`",
        f"- Gate 4 passed: `{best['gate4']['passed']}`",
        f"- Aggregate EV delta: `{best['gate4']['aggregate_ev_delta']}`",
        f"- Aggregate PnL delta: `${best['gate4']['aggregate_pnl_delta']}`",
        f"- Adjusted trades: `{best['gate4']['target_trade_count']}`",
        "",
        "| Window | EV before | EV after | dEV | PnL delta | Max DD delta | Trades delta | Survival delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in best["windows"].items():
        before = row["before"]
        after = row["after"]
        delta = row["delta"]
        lines.append(
            "| "
            f"{label} | "
            f"{before.get('expected_value_score'):.4f} | "
            f"{after.get('expected_value_score'):.4f} | "
            f"{delta.get('expected_value_score', 0):+.4f} | "
            f"${delta.get('total_pnl', 0):+,.2f} | "
            f"{delta.get('max_drawdown_pct', 0):+.4f} | "
            f"{delta.get('trade_count', 0)} | "
            f"{delta.get('survival_rate', 0):+.4f} |"
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(best["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only scout. No shared policy, production adapter, "
                "backtester adapter, watchlist, order path, ranking, exits, "
                "LLM path, or live/default order behavior changed."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    timestamp = _utc_now()
    universe = get_universe()
    event_index, source_stats = _event_index()

    before_rows: dict[str, dict[str, Any]] = {}
    for label, window in WINDOWS.items():
        result = _run_window(universe, window)
        before_rows[label] = {
            "window": window,
            "metrics": _result_metrics(result),
            "raw": result,
        }

    before_aggregate = _aggregate(
        {label: {"before": row} for label, row in before_rows.items()},
        "before",
    )
    variants: list[dict[str, Any]] = []
    for scalar in SCALARS:
        variant_id = f"scalar_{str(scalar).replace('.', 'p')}"
        rows: dict[str, dict[str, Any]] = {}
        incremental_rows: list[dict[str, Any]] = []
        for label, window in WINDOWS.items():
            after_result = _run_after_window(universe, window, event_index, scalar)
            before_metrics = before_rows[label]["metrics"]
            after_metrics = _result_metrics(after_result)
            delta = _delta(after_metrics, before_metrics)
            rows[label] = {
                "window": window,
                "before": before_metrics,
                "after": after_metrics,
                "delta": delta,
                "raw": after_result,
            }
            incremental_rows.extend(
                _incremental_trade_rows(
                    before_rows[label]["raw"],
                    after_result,
                    window_label=label,
                )
            )
        after_aggregate = _aggregate(
            {label: {"after": row} for label, row in rows.items()},
            "after",
        )
        gate4 = _evaluate_gate(rows, before_aggregate, after_aggregate, incremental_rows)
        variants.append(
            {
                "variant_id": variant_id,
                "scalar": scalar,
                "before_aggregate": before_aggregate,
                "after_aggregate": after_aggregate,
                "delta_aggregate": _delta(after_aggregate, before_aggregate),
                "windows": {
                    label: {
                        "window": row["window"],
                        "before": row["before"],
                        "after": row["after"],
                        "delta": row["delta"],
                    }
                    for label, row in rows.items()
                },
                "incremental_trade_rows": incremental_rows,
                "gate4": gate4,
            }
        )

    best_variant = max(
        variants,
        key=lambda row: (
            row["gate4"]["passed"],
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
        ),
    )
    accepted = bool(best_variant["gate4"]["passed"])
    decision = (
        "accepted_replay_only_pre_entry_catalyst_core_risk_topup"
        if accepted
        else "rejected_pre_entry_catalyst_core_risk_topup"
    )
    actual_success = 1 if accepted else 0

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "hypothesis": (
            "Existing core trend/breakout trades with a PIT high-confidence "
            "pre-entry catalyst may deserve a small shared risk-budget top-up "
            "because exp-20260530-014 showed positive three-window outcome "
            "separation."
        ),
        "change_type": "risk_allocation_scout",
        "mechanism_family": "event_context_risk_allocation",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": (
            "Sweep only the risk scalar applied to already-selected core "
            "trend/breakout signals with a high-confidence pre-entry catalyst."
        ),
        "parameters": {
            "candidate_scalars": SCALARS,
            "best_scalar": best_variant["scalar"],
            "lookback_calendar_days": LOOKBACK_CALENDAR_DAYS,
            "high_confidence_categories": sorted(HIGH_CONFIDENCE_CATEGORIES),
            "sizing_key": SIZING_KEY,
            "windows": WINDOWS,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "risk allocation: high-confidence production-visible catalyst "
                "context may identify existing core trend/breakout candidates "
                "worth modestly larger risk budget."
            ),
            "2_history_check": {
                "exp-20260530-014": (
                    "Observed high-confidence catalyst context on 13 core "
                    "trades with positive average lift in all three windows."
                ),
                "exp-20260530-016": (
                    "Rejected using the same high-confidence catalyst field for "
                    "near-breakout early entries; aggregate EV was only +0.0211 "
                    "and old_thin regressed."
                ),
                "meta_research": (
                    "Risk-topup families are high multiple-testing risk, but "
                    "this run uses a new production-visible event-context field "
                    "instead of a nearby price-threshold retune."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": best_variant["gate4"]["rule"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. The after "
            "variants monkeypatch only this runner process; shared production "
            "logic is unchanged."
        ),
        "before_metrics": before_aggregate,
        "after_metrics": best_variant["after_aggregate"],
        "delta_metrics": best_variant["delta_aggregate"],
        "expected_value_score_delta": best_variant["gate4"]["aggregate_ev_delta"],
        "total_pnl_delta": best_variant["gate4"]["aggregate_pnl_delta"],
        "variants": variants,
        "best_variant": best_variant,
        "gate4": best_variant["gate4"],
        "source_coverage": source_stats,
        "decision": decision,
        "rejection_reason": (
            None if accepted else "; ".join(best_variant["gate4"]["failed_reasons"])
        ),
        "next_retry_requires": (
            "Do not retry nearby pre-entry catalyst risk scalars on the frozen "
            "windows. A valid continuation needs either a shared production "
            "event-context adapter plus forward rows, or a materially sharper "
            "catalyst-quality field that resolves the old_thin/window risk."
        ),
        "prediction": {
            "success_probability": 0.28,
            "expected_ev_delta": 0.15,
            "expected_pnl_delta": 2500.0,
            "main_failure_modes": [
                "thin_sample",
                "window_regression",
                "drawdown_drift",
                "event_context_not_share-scalable",
            ],
            "confidence_reason": (
                "Observed core-trade catalyst bucket has positive average lift "
                "in all three windows, but only 13 high-confidence trades and "
                "risk-topup families have high multiple-testing risk."
            ),
            "recorded_at": "2026-05-30T21:06:27+00:00",
            "brier_score": round((0.28 - actual_success) ** 2, 6),
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": 0.28,
            "brier_score": round((0.28 - actual_success) ** 2, 6),
            "expected_ev_delta": 0.15,
            "actual_ev_delta": best_variant["gate4"]["aggregate_ev_delta"],
            "expected_pnl_delta": 2500.0,
            "actual_pnl_delta": best_variant["gate4"]["aggregate_pnl_delta"],
            "predicted_failure_modes": [
                "thin_sample",
                "window_regression",
                "drawdown_drift",
                "event_context_not_share-scalable",
            ],
            "realized_failure_mode": ";".join(best_variant["gate4"]["failed_reasons"]),
            "predicted_failure_mode_hit": bool(best_variant["gate4"]["failed_reasons"]),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": True,
            "alters_orders": False,
            "promotion_note": (
                "A positive replay is not production-retained unless a later "
                "shared adapter exposes the same catalyst context in run.py and "
                "backtester.py with parity tests."
            ),
        },
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            f"quant/experiments/{Path(__file__).name}",
        ],
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_AGG_JSON, before_aggregate)
    _write_json(AFTER_AGG_JSON, best_variant["after_aggregate"])
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "codex-alpha-search",
            "status": payload["status"],
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "decision": decision,
            "gate4": best_variant["gate4"],
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(best_variant["gate4"]), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
