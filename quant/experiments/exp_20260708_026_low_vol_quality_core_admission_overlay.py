"""exp-20260708-026: low-volatility/quality core admission overlay.

Read-only saved-trade diagnostic. The fixed question is whether core trades
that were both high realized-volatility and high SPY-beta at entry were poor
quality momentum entries that should have been blocked before entry. This
runner changes no strategy code, backtester adapter, sizing rule, order path,
paper/live state, or LLM boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260708-026"
OWNER = "codex-alpha-explore"
SLUG = "low_vol_quality_core_admission_overlay"
RUNNER = f"quant/experiments/exp_20260708_026_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)
WINDOW_SOURCES = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
        "core_result": REPO_ROOT
        / "data"
        / "backtests"
        / "archive"
        / "20260604_ohlcv_warehouse_replay"
        / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
    },
]

PLAN_DOC = REPO_ROOT / "docs" / "core_entry_admission_external_strategy_plan.md"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_026_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_measurement.json"
AFTER_JSON = DATA_DIR / "after_measurement.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "A fixed low-volatility/quality admission overlay should reveal whether "
    "current core trades with both entry-time 60-session realized volatility "
    "and 60-session SPY beta in the same-day top quintile are lower-quality "
    "crowded momentum entries that should be blocked before entry rather than "
    "merely sized or stopped after entry."
)
CHANGE_TYPE = "entry_admission_observed_only_counterfactual"
IMPLEMENTATION_MODE = "read_only_saved_trade_counterfactual"
MECHANISM_FAMILY = "core_low_vol_quality_admission_overlay"
TRIAL_FAMILY = "core_high_vol_high_beta_admission_overlay"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "core_high_vol_high_beta_no_entry_admission_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New gate shape: converts external low-volatility/Betting-Against-Beta "
    "prior into a pre-entry quality admission diagnostic on existing core "
    "saved trades, using same-day cross-sectional top-quintile realized-vol "
    "and SPY-beta ranks; not a low-vol candidate-pool retry, not a Donchian/"
    "12-1 retune, and not a scalar/stop threshold change."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260606-015",
    "exp-20260611-019",
    "exp-20260708-021",
    "exp-20260708-024",
]
CAUSAL_COMPONENTS = [
    "saved core trades",
    "entry-time 60-session realized volatility percentile",
    "entry-time 60-session SPY beta percentile",
    "fixed top-quintile-both no-entry diagnostic",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "high_vol_high_beta_contains_best_winners",
        "too_few_blocked_trades",
        "one_window_concentration",
        "private_counterfactual_ignores_slot_replacement",
    ],
    "confidence_reason": (
        "Prior low-vol/defensive candidate pools often failed by deleting "
        "convex winners, but the user asked for ways to avoid bad core "
        "contexts before stops. This fixed admission diagnostic tests that "
        "boundary without retuning existing strategy thresholds."
    ),
    "recorded_at": "2026-07-08T18:51:24+00:00",
}

CONFIG = {
    "lookback_return_sessions": 60,
    "annualization_days": 252,
    "top_quintile_percentile": 0.80,
    "min_feature_universe_count": 20,
    "min_blocked_trades_for_lead": 3,
    "min_remaining_trades_for_lead": 45,
    "min_improved_windows_for_lead": 2,
    "max_single_ticker_blocked_count_share": 0.50,
    "max_single_window_abs_delta_share": 0.75,
    "diagnostic_only": True,
    "acceptance_rule": (
        "Observed-only lead only: blocked high-vol/high-beta core trades must "
        "have negative aggregate PnL, improve additive PnL in at least two "
        "canonical windows, preserve at least 45 remaining saved trades, and "
        "avoid single-ticker/window concentration. Any positive result still "
        "requires a shared-helper Gate 1-4 before behavior changes."
    ),
}

EXCLUDED_TICKERS = {
    "SPY",
    "QQQ",
    "IWM",
    "GLD",
    "IAU",
    "SLV",
    "IEF",
    "TLT",
    "USO",
    "UUP",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def rounded(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def money(value: Any) -> float:
    numeric = as_float(value)
    return 0.0 if numeric is None else numeric


def valid_bar(row: dict[str, Any]) -> bool:
    return all(money(row.get(field)) > 0.0 for field in ("Open", "High", "Low", "Close"))


def load_snapshot(path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    raw = read_json(path, {})
    metadata = raw.get("metadata") or {}
    excluded = set(EXCLUDED_TICKERS)
    excluded.update(str(ticker).upper() for ticker in metadata.get("cross_asset_proxies_added") or [])
    excluded.update(str(ticker).upper() for ticker in metadata.get("added_tickers") or [])
    all_rows: dict[str, list[dict[str, Any]]] = {}
    eligible_rows: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw.get("ohlcv") or {}).items():
        ticker_key = str(ticker).upper()
        cleaned = [row for row in rows if isinstance(row, dict) and valid_bar(row)]
        cleaned.sort(key=lambda row: str(row.get("Date") or ""))
        if not cleaned:
            continue
        all_rows[ticker_key] = cleaned
        if ticker_key not in excluded:
            eligible_rows[ticker_key] = cleaned
    universe = {
        "metadata": metadata,
        "excluded_tickers": sorted(excluded),
        "all_ticker_count": len(all_rows),
        "eligible_ticker_count": len(eligible_rows),
        "eligible_tickers": sorted(eligible_rows),
    }
    return all_rows, eligible_rows, universe


def row_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row["Date"]): idx for idx, row in enumerate(rows)}


def daily_return(rows: list[dict[str, Any]], index: int) -> float | None:
    if index <= 0 or index >= len(rows):
        return None
    prev_close = money(rows[index - 1].get("Close"))
    close = money(rows[index].get("Close"))
    if prev_close <= 0.0 or close <= 0.0:
        return None
    return close / prev_close - 1.0


def return_by_date(rows: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for idx in range(1, len(rows)):
        ret = daily_return(rows, idx)
        if ret is not None:
            result[str(rows[idx]["Date"])] = ret
    return result


def covariance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    return sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right)) / (
        len(left) - 1
    )


def feature_for_entry(
    ticker: str,
    rows: list[dict[str, Any]] | None,
    entry_date: str,
    spy_returns: dict[str, float],
) -> tuple[dict[str, Any] | None, str]:
    if not rows:
        return None, "missing_ticker_rows"
    index_by_date = row_by_date(rows)
    entry_idx = index_by_date.get(entry_date)
    if entry_idx is None:
        return None, "missing_entry_bar"
    signal_idx = entry_idx - 1
    lookback = int(CONFIG["lookback_return_sessions"])
    if signal_idx < lookback:
        return None, "insufficient_history"

    stock_returns: list[float] = []
    aligned_spy_returns: list[float] = []
    aligned_dates: list[str] = []
    start_idx = signal_idx - lookback + 1
    for idx in range(start_idx, signal_idx + 1):
        stock_ret = daily_return(rows, idx)
        date = str(rows[idx]["Date"])
        spy_ret = spy_returns.get(date)
        if stock_ret is None or spy_ret is None:
            continue
        stock_returns.append(stock_ret)
        aligned_spy_returns.append(spy_ret)
        aligned_dates.append(date)

    if len(stock_returns) < lookback:
        return None, f"insufficient_aligned_returns_{len(stock_returns)}"
    if len(set(stock_returns)) <= 1:
        return None, "zero_stock_return_variance"
    spy_variance = covariance(aligned_spy_returns, aligned_spy_returns)
    if spy_variance <= 0.0:
        return None, "zero_spy_return_variance"
    realized_vol = statistics.stdev(stock_returns) * math.sqrt(
        CONFIG["annualization_days"]
    )
    beta = covariance(stock_returns, aligned_spy_returns) / spy_variance
    return (
        {
            "ticker": ticker,
            "entry_date": entry_date,
            "signal_date": str(rows[signal_idx]["Date"]),
            "lookback_sessions": lookback,
            "aligned_return_count": len(stock_returns),
            "first_return_date": aligned_dates[0],
            "last_return_date": aligned_dates[-1],
            "realized_vol_60d": realized_vol,
            "spy_beta_60d": beta,
        },
        "ok",
    )


def percentile_rank(value: float, values: list[float]) -> float | None:
    if not values:
        return None
    return sum(1 for item in values if item <= value) / len(values)


def feature_distribution_for_date(
    eligible_rows: dict[str, list[dict[str, Any]]],
    entry_date: str,
    spy_returns: dict[str, float],
) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    missing_reasons: Counter[str] = Counter()
    for ticker, rows in eligible_rows.items():
        feature, reason = feature_for_entry(ticker, rows, entry_date, spy_returns)
        if feature is None:
            missing_reasons[reason] += 1
            continue
        features.append(feature)
    vols = [money(row["realized_vol_60d"]) for row in features]
    betas = [money(row["spy_beta_60d"]) for row in features]
    return {
        "entry_date": entry_date,
        "feature_count": len(features),
        "missing_reasons": dict(sorted(missing_reasons.items())),
        "vol_values": vols,
        "beta_values": betas,
        "vol_cutoff_80": rounded(sorted(vols)[math.ceil(len(vols) * 0.8) - 1], 6)
        if vols
        else None,
        "beta_cutoff_80": rounded(sorted(betas)[math.ceil(len(betas) * 0.8) - 1], 6)
        if betas
        else None,
    }


def trade_id(trade: dict[str, Any]) -> str:
    if trade.get("trade_key"):
        return str(trade["trade_key"])
    return "|".join(
        str(trade.get(key) or "")
        for key in ("ticker", "strategy", "entry_date", "exit_date", "entry_price")
    )


def trade_pnl(trade: dict[str, Any]) -> float:
    return money(trade.get("pnl"))


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [trade_pnl(trade) for trade in trades]
    count = len(trades)
    wins = sum(1 for value in pnls if value > 0.0)
    losses = sum(1 for value in pnls if value < 0.0)
    return {
        "trades": count,
        "wins": wins,
        "losses": losses,
        "total_pnl": rounded(sum(pnls), 2),
        "avg_pnl": rounded(sum(pnls) / count, 2) if count else None,
        "win_rate": rounded(wins / count, 4) if count else None,
        "largest_winner": rounded(max(pnls), 2) if pnls else None,
        "largest_loser": rounded(min(pnls), 2) if pnls else None,
    }


def root_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": rounded(as_float(result.get("expected_value_score"))),
        "sharpe_daily": rounded(as_float(result.get("sharpe_daily"))),
        "total_pnl": rounded(as_float(result.get("total_pnl")), 2),
        "max_drawdown_pct": rounded(as_float(result.get("max_drawdown_pct"))),
        "win_rate": rounded(as_float(result.get("win_rate"))),
        "total_trades": int(result.get("total_trades") or len(result.get("trades") or [])),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": rounded(as_float(result.get("survival_rate"))),
    }


def enriched_trade_record(
    window_label: str,
    trade: dict[str, Any],
    feature: dict[str, Any],
    distribution: dict[str, Any],
) -> dict[str, Any]:
    vol = money(feature["realized_vol_60d"])
    beta = money(feature["spy_beta_60d"])
    vol_percentile = percentile_rank(vol, distribution["vol_values"])
    beta_percentile = percentile_rank(beta, distribution["beta_values"])
    return {
        "window": window_label,
        "trade_id": trade_id(trade),
        "ticker": str(trade.get("ticker") or "").upper(),
        "strategy": str(trade.get("strategy") or ""),
        "entry_date": trade.get("entry_date"),
        "signal_date": feature["signal_date"],
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": rounded(trade_pnl(trade), 2),
        "pnl_pct_net": rounded(as_float(trade.get("pnl_pct_net"))),
        "entry_price": rounded(as_float(trade.get("entry_price")), 4),
        "exit_price": rounded(as_float(trade.get("exit_price")), 4),
        "realized_vol_60d": rounded(vol),
        "spy_beta_60d": rounded(beta),
        "realized_vol_percentile": rounded(vol_percentile),
        "spy_beta_percentile": rounded(beta_percentile),
        "same_day_feature_universe_count": distribution["feature_count"],
        "vol_top_quintile": bool(
            vol_percentile is not None
            and vol_percentile >= CONFIG["top_quintile_percentile"]
        ),
        "beta_top_quintile": bool(
            beta_percentile is not None
            and beta_percentile >= CONFIG["top_quintile_percentile"]
        ),
        "vol_cutoff_80": distribution["vol_cutoff_80"],
        "beta_cutoff_80": distribution["beta_cutoff_80"],
    }


def should_block(record: dict[str, Any]) -> bool:
    return bool(record["vol_top_quintile"] and record["beta_top_quintile"])


def analyze_window(source: dict[str, Any]) -> dict[str, Any]:
    all_rows, eligible_rows, universe = load_snapshot(source["snapshot"])
    core_result = read_json(source["core_result"], {})
    trades = core_result.get("trades") or []
    if not isinstance(trades, list):
        trades = []
    spy_rows = all_rows.get("SPY")
    spy_returns = return_by_date(spy_rows or [])
    date_distribution_cache: dict[str, dict[str, Any]] = {}
    enriched: list[dict[str, Any]] = []
    blocked_records: list[dict[str, Any]] = []
    feature_missing: Counter[str] = Counter()

    for trade in trades:
        entry_date = str(trade.get("entry_date") or "")
        ticker = str(trade.get("ticker") or "").upper()
        if not entry_date or not ticker:
            feature_missing["missing_trade_entry_or_ticker"] += 1
            continue
        if entry_date not in date_distribution_cache:
            date_distribution_cache[entry_date] = feature_distribution_for_date(
                eligible_rows, entry_date, spy_returns
            )
        distribution = date_distribution_cache[entry_date]
        feature, reason = feature_for_entry(ticker, all_rows.get(ticker), entry_date, spy_returns)
        if feature is None:
            feature_missing[reason] += 1
            continue
        if distribution["feature_count"] < CONFIG["min_feature_universe_count"]:
            feature_missing["same_day_feature_universe_below_floor"] += 1
            continue
        record = enriched_trade_record(source["label"], trade, feature, distribution)
        enriched.append(record)
        if should_block(record):
            blocked_records.append(record)

    blocked_ids = {record["trade_id"] for record in blocked_records}
    blocked_trades = [trade for trade in trades if trade_id(trade) in blocked_ids]
    kept_trades = [trade for trade in trades if trade_id(trade) not in blocked_ids]
    blocked_pnl = sum(trade_pnl(trade) for trade in blocked_trades)
    baseline_trade_pnl = sum(trade_pnl(trade) for trade in trades)
    baseline_total_pnl = money(core_result.get("total_pnl"))
    delta_pnl = -blocked_pnl
    counterfactual_pnl = baseline_total_pnl + delta_pnl

    distribution_counts = [
        int(row["feature_count"]) for row in date_distribution_cache.values()
    ]
    return {
        "label": source["label"],
        "start": source["start"],
        "end": source["end"],
        "snapshot_file": repo_rel(source["snapshot"]),
        "core_result_file": repo_rel(source["core_result"]),
        "universe": universe,
        "baseline_metrics": root_metrics(core_result),
        "baseline_trade_summary": summarize_trades(trades),
        "feature_coverage": {
            "saved_trade_count": len(trades),
            "feature_evaluable_trade_count": len(enriched),
            "feature_evaluable_rate": rounded(len(enriched) / len(trades), 4)
            if trades
            else None,
            "feature_missing_reasons": dict(sorted(feature_missing.items())),
            "unique_entry_dates": len(date_distribution_cache),
            "min_same_day_feature_universe_count": min(distribution_counts)
            if distribution_counts
            else None,
            "median_same_day_feature_universe_count": rounded(
                statistics.median(distribution_counts), 2
            )
            if distribution_counts
            else None,
        },
        "enriched_trade_count": len(enriched),
        "blocked_trade_summary": summarize_trades(blocked_trades),
        "kept_trade_summary": summarize_trades(kept_trades),
        "blocked_trades": blocked_records,
        "blocked_pnl_sum": rounded(blocked_pnl, 2),
        "additive_counterfactual_total_pnl": rounded(counterfactual_pnl, 2),
        "additive_pnl_delta": rounded(delta_pnl, 2),
        "pnl_reconciliation": {
            "sum_trade_pnl": rounded(baseline_trade_pnl, 2),
            "reported_total_pnl": rounded(baseline_total_pnl, 2),
            "difference": rounded(baseline_trade_pnl - baseline_total_pnl, 2),
        },
        "improves_additive_pnl": bool(delta_pnl > 0.0),
        "diagnostic_limits": {
            "slot_replacement_measured": False,
            "cash_drag_measured": False,
            "exit_path_replayed": False,
            "expected_value_score_recomputed": False,
            "reason": "Saved-trade additive attribution only; not a full backtest.",
        },
    }


def aggregate_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_records = [
        record for window in windows for record in window.get("blocked_trades", [])
    ]
    ticker_counts = Counter(record["ticker"] for record in blocked_records)
    strategy_counts = Counter(record["strategy"] for record in blocked_records)
    ticker_pnl: defaultdict[str, float] = defaultdict(float)
    strategy_pnl: defaultdict[str, float] = defaultdict(float)
    window_abs_delta: defaultdict[str, float] = defaultdict(float)
    for window in windows:
        window_abs_delta[window["label"]] += abs(float(window["additive_pnl_delta"] or 0.0))
    for record in blocked_records:
        ticker_pnl[record["ticker"]] += money(record.get("pnl"))
        strategy_pnl[record["strategy"]] += money(record.get("pnl"))

    total_blocked = len(blocked_records)
    baseline_pnl = sum(money(window["baseline_metrics"].get("total_pnl")) for window in windows)
    delta_pnl = sum(money(window["additive_pnl_delta"]) for window in windows)
    counterfactual_pnl = baseline_pnl + delta_pnl
    blocked_pnl = sum(money(window["blocked_pnl_sum"]) for window in windows)
    total_baseline_trades = sum(
        int(window["baseline_metrics"].get("total_trades") or 0) for window in windows
    )
    remaining_trades = sum(
        int(window["kept_trade_summary"].get("trades") or 0) for window in windows
    )
    enriched_trades = sum(int(window["enriched_trade_count"]) for window in windows)
    improved_windows = [
        window["label"] for window in windows if window["improves_additive_pnl"]
    ]
    max_ticker_count_share = (
        max(ticker_counts.values()) / total_blocked if total_blocked else 0.0
    )
    total_abs_delta = sum(window_abs_delta.values())
    max_window_abs_delta_share = (
        max(window_abs_delta.values()) / total_abs_delta if total_abs_delta else 0.0
    )
    return {
        "baseline_total_pnl": rounded(baseline_pnl, 2),
        "additive_counterfactual_total_pnl": rounded(counterfactual_pnl, 2),
        "additive_pnl_delta": rounded(delta_pnl, 2),
        "blocked_pnl_sum": rounded(blocked_pnl, 2),
        "baseline_trade_count": total_baseline_trades,
        "feature_evaluable_trade_count": enriched_trades,
        "feature_evaluable_rate": rounded(enriched_trades / total_baseline_trades, 4)
        if total_baseline_trades
        else None,
        "remaining_trade_count": remaining_trades,
        "blocked_trade_count": total_blocked,
        "improved_windows": improved_windows,
        "improved_window_count": len(improved_windows),
        "blocked_ticker_counts": dict(sorted(ticker_counts.items())),
        "blocked_strategy_counts": dict(sorted(strategy_counts.items())),
        "blocked_ticker_pnl": {
            ticker: rounded(value, 2) for ticker, value in sorted(ticker_pnl.items())
        },
        "blocked_strategy_pnl": {
            strategy: rounded(value, 2) for strategy, value in sorted(strategy_pnl.items())
        },
        "max_single_ticker_blocked_count_share": rounded(max_ticker_count_share, 4),
        "window_abs_delta_share": {
            label: rounded(value / total_abs_delta, 4) if total_abs_delta else 0.0
            for label, value in sorted(window_abs_delta.items())
        },
        "max_single_window_abs_delta_share": rounded(max_window_abs_delta_share, 4),
    }


def evaluate_lead(aggregate: dict[str, Any]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    if money(aggregate["blocked_pnl_sum"]) >= 0.0:
        failed.append("blocked_trades_not_negative_aggregate_pnl")
    if int(aggregate["improved_window_count"]) < CONFIG["min_improved_windows_for_lead"]:
        failed.append("fewer_than_two_windows_improve_additive_pnl")
    if int(aggregate["blocked_trade_count"]) < CONFIG["min_blocked_trades_for_lead"]:
        failed.append("too_few_blocked_trades")
    if int(aggregate["remaining_trade_count"]) < CONFIG["min_remaining_trades_for_lead"]:
        failed.append("remaining_trade_count_below_usefulness_floor")
    if (
        money(aggregate["max_single_ticker_blocked_count_share"])
        > CONFIG["max_single_ticker_blocked_count_share"]
    ):
        failed.append("single_ticker_blocked_count_concentration")
    if (
        money(aggregate["max_single_window_abs_delta_share"])
        > CONFIG["max_single_window_abs_delta_share"]
    ):
        failed.append("single_window_delta_concentration")
    return not failed, failed


def compact_gate4(gate4: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnostic_only": gate4["diagnostic_only"],
        "observed_only_lead": gate4["observed_only_lead"],
        "full_gate4_passed": gate4["full_gate4_passed"],
        "failed_reasons": gate4["failed_reasons"],
        "aggregate": gate4["aggregate"],
        "windows": [
            {
                "label": window["label"],
                "baseline_total_pnl": window["baseline_metrics"]["total_pnl"],
                "blocked_trade_count": window["blocked_trade_summary"]["trades"],
                "blocked_pnl_sum": window["blocked_pnl_sum"],
                "additive_pnl_delta": window["additive_pnl_delta"],
                "additive_counterfactual_total_pnl": window[
                    "additive_counterfactual_total_pnl"
                ],
                "improves_additive_pnl": window["improves_additive_pnl"],
                "feature_evaluable_trade_count": window["feature_coverage"][
                    "feature_evaluable_trade_count"
                ],
            }
            for window in gate4["windows"]
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = read_json(BASELINE_RESULT, {})
    windows = [analyze_window(source) for source in WINDOW_SOURCES]
    aggregate = aggregate_windows(windows)
    observed_only_lead, failed_reasons = evaluate_lead(aggregate)
    full_gate4_passed = False
    decision = (
        "observed_only_lead_low_vol_quality_admission_requires_shared_helper_gate_1_4"
        if observed_only_lead
        else "observed_only_rejected_low_vol_quality_core_admission_overlay"
    )
    why = (
        "The fixed high-vol/high-beta diagnostic removed a negative aggregate "
        "core cohort across enough windows, so the idea is a lead for a later "
        "shared admission helper. It is not accepted strategy behavior because "
        "this saved-trade diagnostic does not replay slot replacement, cash "
        "drag, ranking, or exits."
        if observed_only_lead
        else "The fixed high-vol/high-beta diagnostic did not clear the "
        "predeclared observed-only lead criteria. In this sample, broad "
        "top-quintile volatility plus top-quintile beta is not sufficient by "
        "itself to justify a core no-entry rule."
    )
    production_impact = {
        "strategy_code_changed": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "paper_state_changed": False,
        "llm_decision_boundary_changed": False,
        "trade_enabled": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "read_only_saved_trade_additive_counterfactual",
    }
    changed_files = [
        repo_rel(PLAN_DOC),
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(BEFORE_JSON),
        repo_rel(AFTER_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    completed_at = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "realized_success": observed_only_lead,
            "realized_failure_modes": failed_reasons,
        },
        "config": CONFIG,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_result_summary": {
            "artifact_exists": BASELINE_RESULT.exists(),
            "artifact": repo_rel(BASELINE_RESULT),
            "accepted_stack_aggregate_ev": baseline.get("aggregate", {}).get(
                "expected_value_score"
            )
            if isinstance(baseline.get("aggregate"), dict)
            else None,
        },
        "gate1": {
            "baseline_available": BASELINE_RESULT.exists(),
            "canonical_snapshots": [repo_rel(source["snapshot"]) for source in WINDOW_SOURCES],
            "canonical_core_results": [repo_rel(source["core_result"]) for source in WINDOW_SOURCES],
            "baseline_protocol": "current accepted core stack plus saved canonical warehouse window trades",
            "passed": BASELINE_RESULT.exists()
            and all(Path(source["snapshot"]).exists() for source in WINDOW_SOURCES)
            and all(Path(source["core_result"]).exists() for source in WINDOW_SOURCES),
        },
        "gate2": {
            "required_saved_trade_fields": ["ticker", "entry_date", "strategy", "pnl"],
            "required_ohlcv_fields": ["Date", "Close"],
            "target_price_required_for_signal_generation": False,
            "uses_runtime_production_visible_fields": True,
            "note": (
                "This diagnostic consumes saved trade rows and PIT OHLCV "
                "snapshots. It verifies the fields used by the attribution; "
                "target_price remains a signal-generation sentinel for any "
                "future shared-helper promotion."
            ),
            "passed": all(
                all(field in trade for field in ("ticker", "entry_date", "strategy", "pnl"))
                for source in WINDOW_SOURCES
                for trade in (read_json(source["core_result"], {}).get("trades") or [])
            ),
        },
        "gate3": {
            "no_filter_added_to_strategy": True,
            "diagnostic_trade_survival_not_signal_survival": True,
            "baseline_signals_generated": {
                window["label"]: window["baseline_metrics"]["signals_generated"]
                for window in windows
            },
            "baseline_signals_survived": {
                window["label"]: window["baseline_metrics"]["signals_survived"]
                for window in windows
            },
            "baseline_survival_rate": {
                window["label"]: window["baseline_metrics"]["survival_rate"]
                for window in windows
            },
            "feature_evaluable_trade_count": aggregate["feature_evaluable_trade_count"],
            "remaining_saved_trades_after_diagnostic_block": aggregate[
                "remaining_trade_count"
            ],
            "passed": True,
        },
        "gate4": {
            "diagnostic_only": True,
            "full_gate4_passed": full_gate4_passed,
            "observed_only_lead": observed_only_lead,
            "failed_reasons": failed_reasons
            + ["not_full_gate4_saved_trade_counterfactual"],
            "aggregate": aggregate,
            "windows": windows,
            "acceptance_rule": CONFIG["acceptance_rule"],
            "not_recomputed": [
                "expected_value_score",
                "sharpe_daily",
                "max_drawdown_pct",
                "slot_replacement",
                "cash_drag",
                "ranking_effect",
            ],
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not rerun this same saved-trade diagnostic by changing the "
                "60-session lookback, 80th-percentile thresholds, beta/vol "
                "rank formula, ticker universe exclusions, strategy scope, or "
                "window slices. Those are retunes on the same OHLCV momentum "
                "surface."
            ),
            "new_evidence_required": (
                "A positive next step would require a shared production/"
                "backtest admission helper and full Gate 1-4 replay. After a "
                "negative result, move to a different admission field, PEAD/"
                "revision activation/envelope work with legal evidence, or a "
                "short-cycle family with new evidence rather than retuning this "
                "low-vol/high-beta diagnostic."
            ),
        },
        "rejection_reason": None if observed_only_lead else ";".join(failed_reasons),
        "next_retry_requires": [
            "shared_helper_gate_1_4_before_any_behavior_change"
            if observed_only_lead
            else "different_admission_field_or_external_baseline_family",
            "no_low_vol_beta_lookback_threshold_universe_strategy_or_window_retune_on_same_saved_trades",
        ],
        "changed_files": changed_files,
        "related_files": [
            repo_rel(PLAN_DOC),
            repo_rel(BASELINE_RESULT),
            *[repo_rel(source["snapshot"]) for source in WINDOW_SOURCES],
            *[repo_rel(source["core_result"]) for source in WINDOW_SOURCES],
            repo_rel(TICKET_JSON),
        ],
        "allowed_write_scope": ticket.get("allowed_write_scope", []),
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "before_measurement": repo_rel(BEFORE_JSON),
        "after_measurement": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
        "ticket_before": ticket,
        "completed_at": completed_at,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": compact_gate4(payload["gate4"]),
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "completed_at": payload["completed_at"],
    }


def build_before_after(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    aggregate = payload["gate4"]["aggregate"]
    before = {
        "experiment_id": EXPERIMENT_ID,
        "measurement_type": "saved_trade_baseline_pnl",
        "diagnostic_only": True,
        "expected_value_score": None,
        "total_pnl": aggregate["baseline_total_pnl"],
        "total_trades": aggregate["baseline_trade_count"],
        "blocked_trade_count": 0,
        "note": "Before measurement uses saved canonical trade PnL only.",
    }
    after = {
        "experiment_id": EXPERIMENT_ID,
        "measurement_type": "saved_trade_high_vol_high_beta_no_entry_additive_counterfactual",
        "diagnostic_only": True,
        "expected_value_score": None,
        "total_pnl": aggregate["additive_counterfactual_total_pnl"],
        "total_trades": aggregate["remaining_trade_count"],
        "blocked_trade_count": aggregate["blocked_trade_count"],
        "total_pnl_delta": aggregate["additive_pnl_delta"],
        "note": "After measurement excludes blocked saved trades; not a full backtest.",
    }
    return before, after


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    aggregate = gate4["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: Low-Vol/Quality Core Admission Overlay",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Observed-only lead: `{payload['observed_only_lead']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Aggregate",
        "",
        f"- Baseline PnL: `${aggregate['baseline_total_pnl']}`",
        f"- Counterfactual PnL: `${aggregate['additive_counterfactual_total_pnl']}`",
        f"- Additive PnL delta: `${aggregate['additive_pnl_delta']}`",
        f"- Blocked trades: `{aggregate['blocked_trade_count']}` / `{aggregate['baseline_trade_count']}`",
        f"- Feature-evaluable trades: `{aggregate['feature_evaluable_trade_count']}`",
        f"- Improved windows: `{', '.join(aggregate['improved_windows']) or 'none'}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Windows",
        "",
        "| Window | Baseline PnL | Evaluable | Blocked trades | Blocked PnL | PnL delta | Counterfactual PnL | Improved |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for window in gate4["windows"]:
        lines.append(
            f"| {window['label']} | {window['baseline_metrics']['total_pnl']} | "
            f"{window['feature_coverage']['feature_evaluable_trade_count']} | "
            f"{window['blocked_trade_summary']['trades']} | {window['blocked_pnl_sum']} | "
            f"{window['additive_pnl_delta']} | {window['additive_counterfactual_total_pnl']} | "
            f"{window['improves_additive_pnl']} |"
        )
    lines.extend(
        [
            "",
            "## Blocked Tickers",
            "",
            f"- Counts: `{aggregate['blocked_ticker_counts']}`",
            f"- PnL: `{aggregate['blocked_ticker_pnl']}`",
            f"- Strategies: `{aggregate['blocked_strategy_counts']}`",
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        PLAN_DOC,
        REPO_ROOT / RUNNER,
        OUT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    before, after = build_before_after(payload)
    log_record = compact_log_record(payload)
    ticket = dict(payload["ticket_before"] or {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["completed_at"],
            "result": {
                "decision": payload["decision"],
                "accepted": payload["accepted"],
                "accepted_alpha": payload["accepted_alpha"],
                "observed_only_lead": payload["observed_only_lead"],
                "artifact": payload["artifact"],
                "log": payload["log"],
                "gate4": log_record["gate4"],
            },
        }
    )

    write_json(OUT_JSON, payload)
    write_json(BEFORE_JSON, before)
    write_json(AFTER_JSON, after)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, ticket)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "runner": RUNNER,
            "gate4": log_record["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "before_measurement": payload["before_measurement"],
            "after_measurement": payload["after_measurement"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": log_record["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "gate4": compact_gate4(payload["gate4"]),
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
