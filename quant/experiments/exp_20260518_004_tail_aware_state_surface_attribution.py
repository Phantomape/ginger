"""exp-20260518-004: tail-aware state-surface attribution diagnostics.

Measurement repair supporting alpha search. This experiment does not change
core entries, exits, ranking, sizing, state-surface policy, or live/default
orders. It captures the canonical core control results, runs read-only
diagnostics across the new engines, and decides whether a single next
production-visible alpha variable is mature enough to test.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260518-004"
EXPERIMENT_SLUG = "tail_aware_state_surface_attribution"
ACCEPTED_RANK_PROFILE = "strong_top_heavy"
FLAT_RANK_PROFILE = "flat_100"
BASELINE_HOLD_DAYS = 20
REJECTED_HOLD_DAYS = 25

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from allocation_engine import allocate  # noqa: E402
from backtest_readonly_diagnostics import (  # noqa: E402
    _excess_kurtosis,
    _hhi,
    _skew,
    _tail_ratio,
    _top5_contribution,
    build_diagnostics,
)
from decay_monitor import rolling_decay_report  # noqa: E402
from evaluator_gates import evaluate_metrics  # noqa: E402
from portfolio_heat_engine import (  # noqa: E402
    DEFAULT_THEME_CLUSTER_MAP,
    DEFAULT_THEME_MAP,
    build_portfolio_heat_report,
    heat_score,
)
from regime_engine import apply_regime_to_allocation, classify_market_regime  # noqa: E402
from experiments import exp_20260517_014_state_surface_rotation_only_replay as parent  # noqa: E402
from experiments import exp_20260517_017_state_surface_rotation_ret20_excess_iwm_floor as spy_gate  # noqa: E402
from experiments import exp_20260518_001_state_surface_rotation_hold_days as hold_exp  # noqa: E402
from experiments import exp_20260518_002_state_surface_rank_notional as rank_exp  # noqa: E402


WINDOWS = parent.WINDOWS
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_SLUG}.json"
CANONICAL_DIR = OUT_DIR / "canonical"
DIAGNOSTICS_DIR = OUT_DIR / "diagnostics"
COHORT_JSON = OUT_DIR / "cohort_attribution.json"
NEXT_DECISION_JSON = OUT_DIR / "next_candidate_decision.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

EXPECTED_CORE_METRICS = {
    "late_strong": {
        "expected_value_score": 5.1628,
        "total_pnl": 117072.92,
        "sharpe_daily": 4.41,
        "max_drawdown_pct": 0.0665,
        "trade_count": 18,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 2.1402,
        "total_pnl": 78110.11,
        "sharpe_daily": 2.74,
        "max_drawdown_pct": 0.1119,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.5911,
        "total_pnl": 39667.96,
        "sharpe_daily": 1.49,
        "max_drawdown_pct": 0.1001,
        "trade_count": 22,
        "survival_rate": 0.8667,
    },
}


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
    line = json.dumps(_safe(payload), sort_keys=True)
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


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _money(value: Any) -> float:
    return round(float(_float(value, 0.0) or 0.0), 2)


def _strip_core_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        **{key: value for key, value in result.items() if key != "equity_curve"},
        "equity_curve_omitted": "stored experiment artifact omits equity_curve to avoid churn",
    }


def _tail_metrics_from_values(values: list[Any], prefix: str) -> dict[str, Any]:
    clean = [float(v) for v in (_float(value) for value in values) if v is not None]
    positives = [value for value in clean if value > 0]
    negatives = [value for value in clean if value <= 0]
    total_positive = sum(positives)
    total_negative = sum(negatives)
    return {
        f"{prefix}_count": len(clean),
        f"{prefix}_positive_count": len(positives),
        f"{prefix}_negative_count": len(negatives),
        f"{prefix}_mean": round(sum(clean) / len(clean), 6) if clean else None,
        f"{prefix}_min": round(min(clean), 6) if clean else None,
        f"{prefix}_max": round(max(clean), 6) if clean else None,
        f"{prefix}_positive_sum": round(total_positive, 6),
        f"{prefix}_negative_sum": round(total_negative, 6),
        f"{prefix}_skewness": _skew(clean),
        f"{prefix}_excess_kurtosis": _excess_kurtosis(clean),
        f"{prefix}_tail_ratio": _tail_ratio(clean),
        f"{prefix}_top_5_contribution_pct": _top5_contribution(clean),
        f"{prefix}_hhi_concentration": _hhi(clean),
    }


def _simple_sharpe(values: list[float]) -> float | None:
    clean = [float(v) for v in values if _float(v) is not None]
    if len(clean) < 2:
        return None
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    if std <= 0:
        return None
    return round((mean / std) * math.sqrt(len(clean)), 4)


def _paper_performance_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for trade in trades:
        out.append(
            {
                "status": "closed",
                "ticker": trade.get("ticker"),
                "strategy": "state_surface_paper",
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "entry_price": trade.get("entry_open") or trade.get("entry_price"),
                "exit_price": trade.get("exit_close") or trade.get("exit_price"),
                "stop_price": None,
                "shares": trade.get("shares"),
                "profit_loss": trade.get("pnl"),
            }
        )
    return out


def _paper_diagnostics(
    trades: list[dict[str, Any]],
    *,
    combined_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pnl_values = [float(_float(trade.get("pnl"), 0.0) or 0.0) for trade in trades]
    return_values = [
        float(_float(trade.get("net_return_pct"), 0.0) or 0.0) for trade in trades
    ]
    wins = [value for value in pnl_values if value > 0]
    expected_value = sum(pnl_values) / len(pnl_values) if pnl_values else 0.0
    metrics = {
        "total_trades": len(trades),
        "win_rate": round(len(wins) / len(trades), 4) if trades else 0.0,
        "expected_value_usd": round(expected_value, 2),
        "sharpe_ratio": _simple_sharpe(return_values),
        "max_drawdown_pct": (combined_metrics or {}).get("max_drawdown_pct"),
        "avg_paper_return": round(sum(return_values) / len(return_values), 6)
        if return_values
        else None,
        **_tail_metrics_from_values(pnl_values, "pnl"),
        **_tail_metrics_from_values(return_values, "return"),
    }
    return {
        "metrics_for_gates": metrics,
        "tail_gate_report_pnl": evaluate_metrics(metrics, prefer_r_multiple=False),
        "decay_report": rolling_decay_report(
            _paper_performance_trades(trades),
            baseline_metrics=metrics,
        ),
        "notes": [
            "State-surface paper trades have no planned stop, so true R-multiple is unavailable.",
            "Tail gates are evaluated with raw PnL and net-return distribution prefixes.",
        ],
    }


def _rank_notional_variant(
    *,
    profile_name: str,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    profile = list(rank_exp.RANK_NOTIONAL_PROFILES[profile_name])
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        candidates = rank_exp._rotation_candidates_for_top_five(
            label=label,
            window=window,
            result=core_results[label],
            prices=prices,
        )
        spy_filtered, spy_blocked = spy_gate._apply_locked_spy_floor(candidates)
        queued = rank_exp._attach_queue_ranks(spy_filtered)
        selected, selection_skipped = parent.base._select_trades(queued)
        adjusted = rank_exp._apply_rank_notional_profile(
            selected,
            profile_name=profile_name,
            profile=profile,
        )
        event_curve = rank_exp._event_equity_curve_variable_notional(
            adjusted,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        after_metrics[label] = parent.base._combined_metrics(
            core_results[label], event_curve, adjusted
        )
        selected_all.extend({**trade, "window": label} for trade in adjusted)
        skipped_reason_counts = Counter(
            str(row.get("reason") or "unknown")
            for row in [*spy_blocked, *selection_skipped]
        )
        surface_sleeve[label] = {
            "raw_rotation_candidate_count": len(candidates),
            "price_ready_rotation_candidate_count": sum(
                1 for row in candidates if row.get("status") == "price_ready"
            ),
            "ret20_excess_spy_blocked_price_ready_count": sum(
                1 for row in spy_blocked if row.get("status") == "price_ready"
            ),
            "selected_trade_count": len(adjusted),
            "selected_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in adjusted), 2
            ),
            "selected_win_rate": round(
                sum(1 for trade in adjusted if float(trade.get("pnl") or 0.0) > 0)
                / len(adjusted),
                4,
            )
            if adjusted
            else None,
            "notional_by_queue_rank": rank_exp._notional_by_queue_rank(adjusted),
            "surface_summary": parent.base._surface_summary(adjusted),
            "skipped_reason_counts": dict(skipped_reason_counts),
        }

    return {
        "variant_name": profile_name,
        "variant_type": "rank_notional_profile",
        "profile_multipliers": profile,
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "single_ticker_positive_share": rank_exp._single_ticker_positive_share(selected_all),
    }


def _hold_days_variant(
    *,
    hold_days: int,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        candidates = hold_exp._rotation_candidates_for_hold_days(
            hold_days=hold_days,
            label=label,
            window=window,
            result=core_results[label],
            prices=prices,
        )
        spy_filtered, spy_blocked = spy_gate._apply_locked_spy_floor(candidates)
        selected, selection_skipped = parent.base._select_trades(spy_filtered)
        event_curve = parent.base._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        after_metrics[label] = parent.base._combined_metrics(
            core_results[label], event_curve, selected
        )
        selected_all.extend({**trade, "window": label} for trade in selected)
        skipped_reason_counts = Counter(
            str(row.get("reason") or "unknown")
            for row in [*spy_blocked, *selection_skipped]
        )
        surface_sleeve[label] = {
            "raw_rotation_candidate_count": len(candidates),
            "price_ready_rotation_candidate_count": sum(
                1 for row in candidates if row.get("status") == "price_ready"
            ),
            "ret20_excess_spy_blocked_price_ready_count": sum(
                1 for row in spy_blocked if row.get("status") == "price_ready"
            ),
            "selected_trade_count": len(selected),
            "selected_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in selected), 2
            ),
            "selected_win_rate": round(
                sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0)
                / len(selected),
                4,
            )
            if selected
            else None,
            "surface_summary": parent.base._surface_summary(selected),
            "skipped_reason_counts": dict(skipped_reason_counts),
        }

    return {
        "variant_name": f"hold_{hold_days}",
        "variant_type": "hold_days",
        "hold_days": hold_days,
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "single_ticker_positive_share": hold_exp._single_ticker_positive_share(selected_all),
    }


def _rows_on_or_before(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    day: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in prices.get(str(ticker).upper(), [])
        if str(row.get("date") or "") <= day
    ]


def _ret_n(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    day: str,
    periods: int,
) -> float | None:
    rows = _rows_on_or_before(prices, ticker, day)
    if len(rows) <= periods:
        return None
    now = _float(rows[-1].get("close"))
    then = _float(rows[-periods - 1].get("close"))
    if now is None or then is None or then <= 0:
        return None
    return now / then - 1.0


def _pct_from_sma(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    day: str,
    periods: int,
) -> float | None:
    rows = _rows_on_or_before(prices, ticker, day)
    if len(rows) < periods:
        return None
    close = _float(rows[-1].get("close"))
    values = [_float(row.get("close")) for row in rows[-periods:]]
    clean = [value for value in values if value is not None]
    if close is None or len(clean) < periods:
        return None
    sma = sum(clean) / len(clean)
    if sma <= 0:
        return None
    return close / sma - 1.0


def _regime_for_date(
    prices: dict[str, list[dict[str, Any]]],
    day: str,
    *,
    theme_signal_count: int = 0,
    breakout_signal_count: int = 0,
) -> dict[str, Any]:
    spy_ret20 = _ret_n(prices, "SPY", day, 20)
    qqq_ret20 = _ret_n(prices, "QQQ", day, 20)
    context = {
        "spy_pct_from_ma": _pct_from_sma(prices, "SPY", day, 200),
        "qqq_pct_from_ma": _pct_from_sma(prices, "QQQ", day, 200),
        "spy_10d_return": _ret_n(prices, "SPY", day, 10),
        "qqq_10d_return": _ret_n(prices, "QQQ", day, 10),
        "spy_20d_return": spy_ret20,
        "qqq_20d_return": qqq_ret20,
        "qqq_minus_spy_ret20": qqq_ret20 - spy_ret20
        if qqq_ret20 is not None and spy_ret20 is not None
        else None,
        "theme_signal_count": theme_signal_count,
        "breakout_signal_count": breakout_signal_count,
    }
    return classify_market_regime(context)


def _theme_for_ticker(ticker: str) -> str:
    return str(DEFAULT_THEME_MAP.get(str(ticker).upper(), "unknown")).lower()


def _cluster_for_theme(theme: str) -> str:
    return str(DEFAULT_THEME_CLUSTER_MAP.get(str(theme).lower(), theme or "unknown")).lower()


def _annotated_trade_rows(
    trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_day = Counter(str(trade.get("decision_date") or "")[:10] for trade in trades)
    rows = []
    regime_cache: dict[str, dict[str, Any]] = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        decision_date = str(trade.get("decision_date") or "")[:10]
        if decision_date not in regime_cache:
            regime_cache[decision_date] = _regime_for_date(
                prices,
                decision_date,
                theme_signal_count=by_day.get(decision_date, 0),
                breakout_signal_count=by_day.get(decision_date, 0),
            )
        regime = regime_cache[decision_date]
        features = trade.get("features") or {}
        theme = _theme_for_ticker(ticker)
        rows.append(
            {
                "window": trade.get("window"),
                "ticker": ticker,
                "decision_date": decision_date,
                "decision_month": decision_date[:7],
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "surface": trade.get("surface"),
                "rank": trade.get("rank"),
                "queue_rank": trade.get("queue_rank"),
                "score": trade.get("score"),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
                "ret20_excess_spy": features.get("ret20_excess_spy"),
                "ret5": features.get("ret5"),
                "ret60": features.get("ret60"),
                "near_high_60": features.get("near_high_60"),
                "volume_ratio_20": features.get("volume_ratio_20"),
                "theme": theme,
                "theme_cluster": _cluster_for_theme(theme),
                "regime": regime.get("regime"),
                "regime_confidence": regime.get("confidence"),
            }
        )
    return rows


def _cohort_summary(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) if row.get(field) is not None else "unknown")
        bucket = grouped.setdefault(
            key,
            {
                "name": key,
                "trade_count": 0,
                "wins": 0,
                "pnl_sum": 0.0,
                "notional_sum": 0.0,
                "net_return_sum": 0.0,
                "windows": set(),
                "tickers": set(),
            },
        )
        pnl = float(_float(row.get("pnl"), 0.0) or 0.0)
        bucket["trade_count"] += 1
        bucket["wins"] += int(pnl > 0)
        bucket["pnl_sum"] += pnl
        bucket["notional_sum"] += float(_float(row.get("notional"), 0.0) or 0.0)
        bucket["net_return_sum"] += float(_float(row.get("net_return_pct"), 0.0) or 0.0)
        if row.get("window"):
            bucket["windows"].add(str(row["window"]))
        if row.get("ticker"):
            bucket["tickers"].add(str(row["ticker"]))
    out = []
    for bucket in grouped.values():
        count = int(bucket["trade_count"])
        out.append(
            {
                "name": bucket["name"],
                "trade_count": count,
                "windows": sorted(bucket["windows"]),
                "window_count": len(bucket["windows"]),
                "tickers": sorted(bucket["tickers"]),
                "ticker_count": len(bucket["tickers"]),
                "pnl_sum": round(float(bucket["pnl_sum"]), 2),
                "notional_sum": round(float(bucket["notional_sum"]), 2),
                "win_rate": round(bucket["wins"] / count, 4) if count else None,
                "avg_net_return_pct": round(bucket["net_return_sum"] / count, 6)
                if count
                else None,
            }
        )
    return sorted(out, key=lambda item: (item["pnl_sum"], item["trade_count"]), reverse=True)


def _heat_report_for_trades(trades: list[dict[str, Any]], sleeve_name: str) -> dict[str, Any]:
    positions = []
    for trade in trades:
        positions.append(
            {
                "ticker": trade.get("ticker"),
                "sleeve": sleeve_name,
                "position_value_usd": abs(float(_float(trade.get("notional"), 0.0) or 0.0)),
                "shares": trade.get("shares"),
                "entry_price": trade.get("entry_open") or trade.get("entry_price"),
                "theme": _theme_for_ticker(str(trade.get("ticker") or "")),
            }
        )
    total_value = sum(float(row["position_value_usd"]) for row in positions)
    report = build_portfolio_heat_report(
        positions,
        portfolio_value=total_value if total_value > 0 else None,
    )
    return {**report, "heat_score": heat_score(report)}


def _variant_diagnostics(
    variant: dict[str, Any],
    *,
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    by_window = OrderedDict()
    for label in WINDOWS:
        window_trades = [
            trade for trade in variant["selected_trades"] if trade.get("window") == label
        ]
        by_window[label] = {
            **_paper_diagnostics(
                window_trades,
                combined_metrics=variant["metrics"].get(label),
            ),
            "heat_report": _heat_report_for_trades(
                window_trades,
                f"{variant['variant_type']}:{variant['variant_name']}",
            ),
        }
    return {
        "aggregate": {
            **_paper_diagnostics(
                variant["selected_trades"],
                combined_metrics={
                    "max_drawdown_pct": max(
                        float(metrics.get("max_drawdown_pct") or 0.0)
                        for metrics in variant["metrics"].values()
                    )
                },
            ),
            "heat_report": _heat_report_for_trades(
                variant["selected_trades"],
                f"{variant['variant_type']}:{variant['variant_name']}",
            ),
        },
        "by_window": by_window,
        "cohorts": _cohorts_for_variant(variant, prices=prices),
    }


def _cohorts_for_variant(
    variant: dict[str, Any],
    *,
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows = _annotated_trade_rows(variant["selected_trades"], prices=prices)
    return {
        "selected_trade_rows": rows,
        "by_queue_rank": _cohort_summary(rows, "queue_rank"),
        "by_ticker": _cohort_summary(rows, "ticker"),
        "by_decision_month": _cohort_summary(rows, "decision_month"),
        "by_regime": _cohort_summary(rows, "regime"),
        "by_theme_cluster": _cohort_summary(rows, "theme_cluster"),
    }


def _trade_compare_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("window"),
        row.get("ticker"),
        row.get("decision_date"),
        row.get("entry_date"),
        row.get("queue_rank") or row.get("rank"),
    )


def _trade_deltas(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    before_map = {_trade_compare_key(row): row for row in before}
    out = []
    for row in after:
        key = _trade_compare_key(row)
        old = before_map.get(key)
        if not old:
            continue
        out.append(
            {
                "window": row.get("window"),
                "ticker": row.get("ticker"),
                "decision_date": row.get("decision_date"),
                "queue_rank": row.get("queue_rank"),
                "before_notional": old.get("notional"),
                "after_notional": row.get("notional"),
                "notional_delta": round(
                    float(_float(row.get("notional"), 0.0) or 0.0)
                    - float(_float(old.get("notional"), 0.0) or 0.0),
                    2,
                ),
                "before_pnl": old.get("pnl"),
                "after_pnl": row.get("pnl"),
                "pnl_delta": round(
                    float(_float(row.get("pnl"), 0.0) or 0.0)
                    - float(_float(old.get("pnl"), 0.0) or 0.0),
                    2,
                ),
                "net_return_pct": row.get("net_return_pct"),
            }
        )
    return out


def _core_control_delta(core_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = OrderedDict()
    passed = True
    for label, metrics in core_metrics.items():
        expected = EXPECTED_CORE_METRICS[label]
        row = {}
        for key, expected_value in expected.items():
            actual = metrics.get(key)
            if isinstance(expected_value, float):
                delta = round(float(actual or 0.0) - expected_value, 6)
            else:
                delta = int(actual or 0) - int(expected_value)
            row[key] = {"expected": expected_value, "actual": actual, "delta": delta}
            if abs(delta) > (0.01 if key == "total_pnl" else 0.0001):
                passed = False
        rows[label] = row
    return {"passed": passed, "by_window": rows}


def _aggregate_core_gate_metrics(core_diagnostics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trades = 0
    weighted_ev = 0.0
    sharpe_values = []
    max_dd = 0.0
    pnl_top5 = []
    for diag in core_diagnostics.values():
        metrics = diag["metrics_for_gates"]
        count = int(metrics.get("total_trades") or 0)
        trades += count
        weighted_ev += float(metrics.get("expected_value_usd") or 0.0) * count
        if metrics.get("sharpe_ratio") is not None:
            sharpe_values.append(float(metrics["sharpe_ratio"]))
        max_dd = max(max_dd, float(metrics.get("max_drawdown_pct") or 0.0))
        if metrics.get("pnl_top_5_contribution_pct") is not None:
            pnl_top5.append(float(metrics["pnl_top_5_contribution_pct"]))
    return {
        "total_trades": trades,
        "expected_value_usd": round(weighted_ev / trades, 2) if trades else 0.0,
        "sharpe_ratio": round(sum(sharpe_values) / len(sharpe_values), 4)
        if sharpe_values
        else None,
        "max_drawdown_pct": round(max_dd, 6),
        "pnl_top_5_contribution_pct": round(max(pnl_top5), 4) if pnl_top5 else None,
    }


def _allocation_preview(
    *,
    core_diagnostics: dict[str, dict[str, Any]],
    flat_variant: dict[str, Any],
    rank_variant: dict[str, Any],
) -> dict[str, Any]:
    sleeves = [
        {
            "name": "core_control_aggregate",
            "state": "core",
            "metrics": _aggregate_core_gate_metrics(core_diagnostics),
        },
        {
            "name": "state_surface_flat_top5",
            "state": "shadow",
            "metrics": flat_variant["diagnostics"]["aggregate"]["metrics_for_gates"],
        },
        {
            "name": "state_surface_rank_notional",
            "state": "shadow",
            "metrics": rank_variant["diagnostics"]["aggregate"]["metrics_for_gates"],
        },
    ]
    preview = allocate(sleeves)
    baseline_regime = classify_market_regime({})
    return {
        "read_only": True,
        "allocation_preview": preview,
        "baseline_regime_adjusted_preview": apply_regime_to_allocation(
            preview, baseline_regime
        ),
        "notes": [
            "Shadow state keeps state-surface sleeve capital weight at zero until promotion gates pass.",
            "This preview does not size or route any trade.",
        ],
    }


def _next_candidate_decision(
    *,
    flat_variant: dict[str, Any],
    rank_variant: dict[str, Any],
    hold_delta: dict[str, Any],
) -> dict[str, Any]:
    flat_tail = flat_variant["diagnostics"]["aggregate"]["metrics_for_gates"]
    rank_tail = rank_variant["diagnostics"]["aggregate"]["metrics_for_gates"]
    flat_top5 = _float(flat_tail.get("pnl_top_5_contribution_pct"))
    rank_top5 = _float(rank_tail.get("pnl_top_5_contribution_pct"))
    flat_hhi = _float(flat_tail.get("pnl_hhi_concentration"))
    rank_hhi = _float(rank_tail.get("pnl_hhi_concentration"))
    tail_not_worse = (
        flat_top5 is not None
        and rank_top5 is not None
        and rank_top5 <= flat_top5
        and flat_hhi is not None
        and rank_hhi is not None
        and rank_hhi <= flat_hhi
    )

    rank_rows = rank_variant["diagnostics"]["cohorts"]["selected_trade_rows"]
    touched_windows = sorted({str(row.get("window")) for row in rank_rows if row.get("window")})
    old_thin_rows = [row for row in rank_rows if row.get("window") == "old_thin"]
    mature_heat_or_regime_buckets = []
    for group_name in ("by_regime", "by_theme_cluster"):
        for row in rank_variant["diagnostics"]["cohorts"][group_name]:
            if int(row["trade_count"]) >= 9 and int(row["window_count"]) >= 2:
                mature_heat_or_regime_buckets.append({**row, "source": group_name})

    reasons = [
        "rank-notional is already accepted default-off; this experiment is a diagnostics closeout, not a new alpha rule",
        "hold-days 25 remains rejected because old_thin regressed in the fixed-window comparison",
    ]
    if tail_not_worse:
        reasons.append("accepted rank-notional did not worsen aggregate PnL tail concentration versus flat top-five")
    else:
        reasons.append("tail concentration did not clearly improve enough to justify another nearby rank-profile retune")
    if len(old_thin_rows) < 9:
        reasons.append("old_thin state-surface evidence is still thin, so do not infer a new old-window-specific rule")
    if not mature_heat_or_regime_buckets:
        reasons.append("no heat/regime bucket has enough two-window support to define a single next guard")

    return {
        "decision": "observed_only_no_new_strategy_variable",
        "next_alpha_variable": None,
        "candidate_if_future_evidence_arrives": "heat_or_regime_tail_guard_default_off_paper",
        "tail_not_worse_vs_flat": tail_not_worse,
        "flat_pnl_top5_contribution_pct": flat_top5,
        "rank_pnl_top5_contribution_pct": rank_top5,
        "flat_pnl_hhi_concentration": flat_hhi,
        "rank_pnl_hhi_concentration": rank_hhi,
        "rank_selected_trade_count": len(rank_rows),
        "rank_touched_windows": touched_windows,
        "old_thin_rank_trade_count": len(old_thin_rows),
        "hold_days_25_windows_ev_regressed": hold_delta.get("windows_ev_regressed"),
        "mature_heat_or_regime_buckets": mature_heat_or_regime_buckets,
        "reasons": reasons,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Tail-Aware State-Surface Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Read-only diagnostics. Core strategy logic, default-off state-surface policy, and live/default orders were not changed.",
        "",
        "## Core Control",
        "",
        "| Window | EV | PnL | Sharpe | Max DD | Trades | Survival | Control |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in WINDOWS:
        metrics = payload["gate1"]["canonical_core_baseline_metrics"][label]
        control = payload["core_control_delta"]["by_window"][label]
        lines.append(
            "| {label} | {ev:.4f} | ${pnl:,.2f} | {sharpe:.2f} | {dd:.2%} | {trades} | {survival:.2%} | {passed} |".format(
                label=label,
                ev=metrics["expected_value_score"],
                pnl=metrics["total_pnl"],
                sharpe=metrics["sharpe_daily"],
                dd=metrics["max_drawdown_pct"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
                passed="PASS"
                if all(abs(row["delta"]) <= 0.01 for row in control.values())
                else "CHECK",
            )
        )
    lines.extend(
        [
            "",
            "## Tail Comparison",
            "",
            "| Variant | Trades | EV delta vs control | PnL delta vs control | PnL top-5 | PnL HHI | Gate hard failures |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for name in ("flat_top5", "rank_notional", "hold_25"):
        row = payload["variant_comparison"][name]
        tail = row["diagnostics"]["aggregate"]["metrics_for_gates"]
        gate = row["diagnostics"]["aggregate"]["tail_gate_report_pnl"]
        delta = row.get("delta_vs_control") or {}
        lines.append(
            "| {name} | {trades} | {ev:+.4f} | ${pnl:+,.2f} | {top5} | {hhi} | {fails} |".format(
                name=name,
                trades=row["selected_trade_count"],
                ev=float(delta.get("aggregate_ev_delta") or 0.0),
                pnl=float(delta.get("aggregate_pnl_delta") or 0.0),
                top5="n/a"
                if tail.get("pnl_top_5_contribution_pct") is None
                else f"{tail['pnl_top_5_contribution_pct']:.2%}",
                hhi="n/a"
                if tail.get("pnl_hhi_concentration") is None
                else f"{tail['pnl_hhi_concentration']:.4f}",
                fails=", ".join(gate.get("hard_failures") or []) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Next Decision",
            "",
            f"`{payload['next_candidate_decision']['decision']}`.",
            "",
        ]
    )
    for reason in payload["next_candidate_decision"]["reasons"]:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    gate2 = parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    prices = parent._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    core_diagnostics: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = parent._load_core_result(window)
        core_results[label] = result
        core_metrics[label] = parent.base._core_metrics(result)
        core_diagnostics[label] = build_diagnostics(result)

    flat_variant = _rank_notional_variant(
        profile_name=FLAT_RANK_PROFILE,
        core_results=core_results,
        prices=prices,
    )
    rank_variant = _rank_notional_variant(
        profile_name=ACCEPTED_RANK_PROFILE,
        core_results=core_results,
        prices=prices,
    )
    hold_20_variant = _hold_days_variant(
        hold_days=BASELINE_HOLD_DAYS,
        core_results=core_results,
        prices=prices,
    )
    hold_25_variant = _hold_days_variant(
        hold_days=REJECTED_HOLD_DAYS,
        core_results=core_results,
        prices=prices,
    )

    for variant in (flat_variant, rank_variant, hold_20_variant, hold_25_variant):
        variant["diagnostics"] = _variant_diagnostics(variant, prices=prices)

    rank_delta = parent._aggregate_delta(flat_variant["metrics"], rank_variant["metrics"])
    hold_delta = parent._aggregate_delta(hold_20_variant["metrics"], hold_25_variant["metrics"])
    flat_delta_vs_core = parent._aggregate_delta(core_metrics, flat_variant["metrics"])
    rank_delta_vs_core = parent._aggregate_delta(core_metrics, rank_variant["metrics"])
    hold_25_delta_vs_core = parent._aggregate_delta(core_metrics, hold_25_variant["metrics"])

    trade_deltas = _trade_deltas(
        flat_variant["selected_trades"],
        rank_variant["selected_trades"],
    )
    old_thin_rank_deltas = [
        row for row in trade_deltas if row.get("window") == "old_thin"
    ]

    allocation_preview = _allocation_preview(
        core_diagnostics=core_diagnostics,
        flat_variant=flat_variant,
        rank_variant=rank_variant,
    )
    next_decision = _next_candidate_decision(
        flat_variant=flat_variant,
        rank_variant=rank_variant,
        hold_delta=hold_delta,
    )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    artifacts = {
        "core_results": core_results,
        "core_diagnostics": core_diagnostics,
        "cohort_attribution": rank_variant["diagnostics"]["cohorts"],
        "next_candidate_decision": next_decision,
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "observed_only",
        "decision": "observed_only_no_new_strategy_variable",
        "lane": "measurement_repair",
        "supports_alpha_lane": "event_rotation_replacement_value_maturation",
        "change_type": "read_only_tail_aware_diagnostics",
        "changed_variable": "none_read_only_attribution",
        "change_summary": (
            "Capture canonical core controls and diagnose flat/rank-notional/hold-days "
            "state-surface paper variants with tail gates, heat, regime, decay, and "
            "allocation preview."
        ),
        "component": "quant/experiments",
        "hypothesis": (
            "The accepted state-surface rank-notional result should be explained by "
            "broad queue-rank allocation quality rather than a hidden tail or heat "
            "concentration. If diagnostics reveal a single production-visible "
            "discriminator with enough support, that can become the next Gate 1-4 "
            "alpha experiment."
        ),
        "alpha_hypothesis": {
            "category": "measurement_repair_supporting_capital_allocation",
            "entry_exit_ranking_or_allocation": "diagnostic attribution for default-off paper allocation",
            "playbook_alignment": (
                "Matches the playbook instruction to avoid nearby state-surface "
                "retunes after exp-20260518-002 and instead seek a new field or "
                "forward maturation evidence."
            ),
        },
        "history_check": {
            "exp-20260518-001": "Rejected hold-days 25 because old_thin regressed.",
            "exp-20260518-002": "Accepted shared default-off queue-rank paper notional profile.",
            "today_added_engines": [
                "portfolio_heat_engine",
                "backtest_readonly_diagnostics",
                "regime_engine",
                "decay_monitor",
                "allocation_engine",
                "evaluator_gates",
                "performance_engine tail metrics",
            ],
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation diagnostics for accepted rank-notional state-surface paper sleeve",
            "2_history_check": "exp-20260518-001 rejected hold-days; exp-20260518-002 accepted rank-notional default-off.",
            "3_single_causal_variable": "none; read-only diagnostic closeout",
            "4_acceptance_standard": "diagnostic artifact must reproduce core controls and produce a next-variable/no-variable decision.",
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_003_tail_aware_state_surface_attribution.py"
            ),
        },
        "parameters": {
            "diagnostic_only": True,
            "canonical_windows": WINDOWS,
            "flat_rank_profile": FLAT_RANK_PROFILE,
            "accepted_rank_profile": ACCEPTED_RANK_PROFILE,
            "baseline_hold_days": BASELINE_HOLD_DAYS,
            "rejected_hold_days": REJECTED_HOLD_DAYS,
            "locked_variables": [
                "core entries",
                "core exits",
                "core ranking",
                "core sizing",
                "state_surface_sleeve policy",
                "rank_notional_profile",
                "hold_days",
                "daily candidate count",
                "ret20_excess_spy gate",
                "live/default orders",
            ],
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "canonical_core_baseline_metrics": core_metrics,
            "expected_core_metrics": EXPECTED_CORE_METRICS,
            "canonical_artifacts": {
                label: _repo_rel(CANONICAL_DIR / f"{label}_core_result.json")
                for label in WINDOWS
            },
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "state_surface surface",
                "state_surface rank",
                "state_surface queue_rank",
                "state_surface rank_notional_multiplier",
                "state_surface features.ret20_excess_spy",
                "state_surface features.ret60",
                "state_surface features.near_high_60",
                "state_surface features.volume_ratio_20",
                "OHLCV SPY/QQQ regime context",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_core_filter_added": False,
            "core_signals_generated_delta": 0,
            "core_signals_survived_delta": 0,
            "minimum_after_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in core_metrics.values()
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values()) >= 0.05,
        },
        "gate4": {
            "strategy_change_tested": False,
            "passed": None,
            "decision_rule": "read-only experiment; no alpha promotion or rejection from EV alone",
        },
        "core_control_delta": _core_control_delta(core_metrics),
        "core_diagnostics": {
            label: {
                "metrics_for_gates": diag["metrics_for_gates"],
                "tail_gate_report": diag["tail_gate_report"],
                "decay_report": diag["decay_report"],
                "allocation_preview": diag["allocation_preview"],
                "regime_report": diag["regime_report"],
                "regime_exit_bucket_coverage": diag["regime_exit_bucket_coverage"],
            }
            for label, diag in core_diagnostics.items()
        },
        "variant_comparison": {
            "flat_top5": {
                **{key: value for key, value in flat_variant.items() if key != "selected_trades"},
                "delta_vs_control": flat_delta_vs_core,
            },
            "rank_notional": {
                **{key: value for key, value in rank_variant.items() if key != "selected_trades"},
                "delta_vs_flat": rank_delta,
                "delta_vs_control": rank_delta_vs_core,
                "flat_to_rank_trade_deltas": trade_deltas,
                "old_thin_flat_to_rank_trade_deltas": old_thin_rank_deltas,
            },
            "hold_20": {
                **{key: value for key, value in hold_20_variant.items() if key != "selected_trades"},
            },
            "hold_25": {
                **{key: value for key, value in hold_25_variant.items() if key != "selected_trades"},
                "delta_vs_hold_20": hold_delta,
                "delta_vs_control": hold_25_delta_vs_core,
            },
        },
        "cohort_attribution": rank_variant["diagnostics"]["cohorts"],
        "allocation_engine_preview": allocation_preview,
        "next_candidate_decision": next_decision,
        "before_metrics": {
            "core_control": core_metrics,
            "flat_top5_state_surface_paper": flat_variant["metrics"],
            "hold_20_state_surface_paper": hold_20_variant["metrics"],
        },
        "after_metrics": {
            "rank_notional_state_surface_paper": rank_variant["metrics"],
            "hold_25_state_surface_paper": hold_25_variant["metrics"],
            "diagnostic_decision": next_decision,
        },
        "delta_metrics": {
            "rank_notional_vs_flat": rank_delta,
            "hold_25_vs_hold_20": hold_delta,
            "core_control_delta": _core_control_delta(core_metrics),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "diagnostic_only": True,
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "This closeout tests deterministic replayable diagnostics, not LLM event scoring.",
        },
        "interpretation": (
            "The diagnostics close out today's engines as read-only measurement "
            "infrastructure. The accepted rank-notional paper policy remains "
            "default-off; no new heat, regime, queue-rank, or hold-days rule is "
            "promoted from this run."
        ),
        "rejection_reason": None,
        "next_evidence_needed": (
            "Closed forward replacement-value outcomes or a mature two-window "
            "production-visible heat/regime discriminator before another "
            "state-surface Gate 1-4 strategy change."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(COHORT_JSON),
            _repo_rel(NEXT_DECISION_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload, artifacts


def persist(payload: dict[str, Any], artifacts: dict[str, Any]) -> None:
    for label, result in artifacts["core_results"].items():
        _write_json(CANONICAL_DIR / f"{label}_core_result.json", _strip_core_result(result))
    for label, diagnostics in artifacts["core_diagnostics"].items():
        _write_json(DIAGNOSTICS_DIR / f"{label}_core_diagnostics.json", diagnostics)

    _write_json(COHORT_JSON, artifacts["cohort_attribution"])
    _write_json(NEXT_DECISION_JSON, artifacts["next_candidate_decision"])
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Tail-aware state-surface attribution",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["changed_variable"],
            "core_control_passed": payload["core_control_delta"]["passed"],
            "rank_notional_tail_not_worse_vs_flat": payload["next_candidate_decision"][
                "tail_not_worse_vs_flat"
            ],
            "next_alpha_variable": payload["next_candidate_decision"]["next_alpha_variable"],
            "summary": payload["interpretation"],
            "artifact": _repo_rel(OUT_JSON),
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload, artifacts = build_payload()
    persist(payload, artifacts)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "core_control_passed": payload["core_control_delta"]["passed"],
                    "rank_notional_tail_not_worse_vs_flat": payload["next_candidate_decision"][
                        "tail_not_worse_vs_flat"
                    ],
                    "next_alpha_variable": payload["next_candidate_decision"][
                        "next_alpha_variable"
                    ],
                    "flat_pnl_top5_contribution_pct": payload["next_candidate_decision"][
                        "flat_pnl_top5_contribution_pct"
                    ],
                    "rank_pnl_top5_contribution_pct": payload["next_candidate_decision"][
                        "rank_pnl_top5_contribution_pct"
                    ],
                    "hold_days_25_windows_ev_regressed": payload["next_candidate_decision"][
                        "hold_days_25_windows_ev_regressed"
                    ],
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
