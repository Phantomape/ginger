"""exp-20260524-023: broad-market correlation crowding replacement.

Alpha search for the default-off broad-market leadership paper sleeve.

The accepted broad-market price-floor pool, rank profile, low-extension,
high-volatility, and trend-persistence scalars stay fixed. This run changes
one causal variable: a same-day selection replacement rule that skips a
candidate when its trailing 20-day return correlation to already-open or
same-day selected broad-market sleeve names is above a threshold.

The intent is hidden-beta/crowding alpha governance, not a data or logging
repair. The surface is production-computable from OHLCV only. No JavaScript is
used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260524-023"
EXPERIMENT_SLUG = "broad_market_correlation_crowding"
BASELINE_EXPERIMENT_ID = "exp-20260520-004"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"
REFERENCE_EXPERIMENT_ID = "exp-20260524-022"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
from broad_market_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    backtest_trade_from_feature,
    build_broad_market_feature,
    candidate_passes_profile,
)


WINDOWS = p35.WINDOWS
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / BASELINE_EXPERIMENT_ID
    / "broad_market_trend_persistence_notional.json"
)
CONTROL_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / CONTROL_EXPERIMENT_ID
    / "broad_market_shared_paper_adapter.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

PROFILE_CONFIG = {
    **DEFAULT_CONFIG,
    "ret20_excess_spy_min": 0.035,
    "ret60_min": 0.08,
    "near_high_60_min": 0.93,
    "volume_ratio_20_min": 1.00,
    "decision_close_price_min": 40.0,
    "paper_notional_usd": 7_500.0,
    "rank_notional_multipliers": [1.20, 1.00, 0.80],
    "low_extension_ret5_max": 0.02,
    "low_extension_notional_scalar": 1.15,
    "high_volatility_20_min": 0.055,
    "high_volatility_notional_scalar": 1.15,
    "trend_persistence_positive_day_ratio_20_min": 0.55,
    "trend_persistence_notional_scalar": 1.15,
    "max_active_positions": 5,
    "daily_entry_slots": 3,
    "hold_days": 20,
}

CORRELATION_CAP_SWEEP: OrderedDict[str, dict[str, float | None]] = OrderedDict(
    [
        ("baseline_no_correlation_cap", {"max_positive_corr": None}),
        ("corr_cap_0p95", {"max_positive_corr": 0.95}),
        ("corr_cap_0p90", {"max_positive_corr": 0.90}),
        ("corr_cap_0p85", {"max_positive_corr": 0.85}),
        ("corr_cap_0p80", {"max_positive_corr": 0.80}),
        ("corr_cap_0p75", {"max_positive_corr": 0.75}),
    ]
)

LOOKBACK_DAYS = 20
MIN_CORRELATION_PAIRS = 15
MIN_REPLACED_TRADES = 4
MIN_REPLACED_WINDOWS = 2
MIN_EV_IMPROVED_WINDOWS = 3
MIN_RELATIVE_EV_IMPROVEMENT = 0.10


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


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rank_key(row: dict[str, Any]) -> tuple[float, float, float, str]:
    return (
        float(row["score"]),
        float(row["ret20_excess_spy"]),
        float(row["volume_ratio_20"]),
        str(row["ticker"]),
    )


def _close(row: dict[str, Any]) -> float | None:
    value = row.get("close")
    try:
        close = float(value)
    except (TypeError, ValueError):
        return None
    if close <= 0 or not math.isfinite(close):
        return None
    return close


def _trailing_returns(rows: list[dict[str, Any]], idx: int) -> list[float]:
    start = max(1, idx - LOOKBACK_DAYS + 1)
    values: list[float] = []
    for pos in range(start, idx + 1):
        prev_close = _close(rows[pos - 1])
        close = _close(rows[pos])
        if prev_close is None or close is None:
            continue
        values.append((close / prev_close) - 1.0)
    return values


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < MIN_CORRELATION_PAIRS or len(right) < MIN_CORRELATION_PAIRS:
        return None
    size = min(len(left), len(right))
    left = left[-size:]
    right = right[-size:]
    mean_left = sum(left) / size
    mean_right = sum(right) / size
    num = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    den_left = math.sqrt(sum((a - mean_left) ** 2 for a in left))
    den_right = math.sqrt(sum((b - mean_right) ** 2 for b in right))
    den = den_left * den_right
    if den <= 0 or not math.isfinite(den):
        return None
    corr = num / den
    if not math.isfinite(corr):
        return None
    return max(-1.0, min(1.0, corr))


def _correlation_to_reference(
    *,
    ticker: str,
    reference_ticker: str,
    day: str,
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> float | None:
    ticker_rows = prices.get(ticker) or []
    reference_rows = prices.get(reference_ticker) or []
    ticker_idx = (indexes.get(ticker) or {}).get(day)
    reference_idx = (indexes.get(reference_ticker) or {}).get(day)
    if ticker_idx is None or reference_idx is None:
        return None
    return _pearson(
        _trailing_returns(ticker_rows, ticker_idx),
        _trailing_returns(reference_rows, reference_idx),
    )


def _max_positive_correlation(
    *,
    ticker: str,
    references: list[str],
    day: str,
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> tuple[float | None, str | None]:
    best_corr: float | None = None
    best_reference: str | None = None
    for reference_ticker in references:
        if reference_ticker == ticker:
            continue
        corr = _correlation_to_reference(
            ticker=ticker,
            reference_ticker=reference_ticker,
            day=day,
            prices=prices,
            indexes=indexes,
        )
        if corr is None:
            continue
        if corr > 0 and (best_corr is None or corr > best_corr):
            best_corr = corr
            best_reference = reference_ticker
    return best_corr, best_reference


def _select_rows_for_window(
    *,
    label: str,
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    max_positive_corr: float | None,
) -> dict[str, Any]:
    spec = WINDOWS[label]
    days = p35._trading_days(prices, spec["start"], spec["end"])
    spy_rows = prices.get("SPY") or []
    spy_index = indexes.get("SPY") or {}
    active: list[dict[str, str]] = []
    selected_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    for day in days:
        active = [row for row in active if row["exit_date"] > day]
        capacity = int(PROFILE_CONFIG["max_active_positions"]) - len(active)
        if capacity <= 0:
            continue

        active_tickers = {row["ticker"] for row in active}
        features: list[dict[str, Any]] = []
        for ticker in candidate_tickers:
            if ticker in active_tickers:
                continue
            rows = prices.get(ticker) or []
            idx = (indexes.get(ticker) or {}).get(day)
            if idx is None:
                continue
            feature = build_broad_market_feature(
                ticker=ticker,
                rows=rows,
                idx=idx,
                spy_rows=spy_rows,
                spy_index=spy_index,
            )
            if feature and candidate_passes_profile(feature, PROFILE_CONFIG):
                features.append(feature)

        ranked = sorted(features, key=_rank_key, reverse=True)
        daily_slots = min(int(PROFILE_CONFIG["daily_entry_slots"]), capacity)
        selected_today: list[str] = []
        selected_count = 0

        for queue_rank, feature in enumerate(ranked, start=1):
            if selected_count >= daily_slots:
                break
            ticker = str(feature["ticker"])
            references = sorted(active_tickers | set(selected_today))
            max_corr, reference = _max_positive_correlation(
                ticker=ticker,
                references=references,
                day=day,
                prices=prices,
                indexes=indexes,
            )
            blocked = (
                max_positive_corr is not None
                and max_corr is not None
                and max_corr > float(max_positive_corr)
            )
            if blocked:
                blocked_rows.append(
                    {
                        "window": label,
                        "decision_date": day,
                        "ticker": ticker,
                        "queue_rank": queue_rank,
                        "score": feature.get("score"),
                        "max_positive_corr": round(float(max_corr), 6),
                        "reference_ticker": reference,
                        "max_positive_corr_cap": max_positive_corr,
                        "active_reference_count": len(references),
                    }
                )
                continue

            selected_count += 1
            selected_rank = selected_count
            annotated = dict(feature)
            annotated["correlation_cap_applied"] = max_positive_corr is not None
            annotated["max_positive_corr_to_open_or_selected"] = (
                round(float(max_corr), 6) if max_corr is not None else None
            )
            annotated["correlation_reference_ticker"] = reference
            annotated["max_positive_corr_cap"] = max_positive_corr
            annotated["active_reference_count"] = len(references)
            annotated["day_candidate_count"] = len(ranked)
            annotated["candidate_queue_rank"] = queue_rank
            selected_rows.append(
                {
                    "window": label,
                    "rank": selected_rank,
                    "feature": annotated,
                }
            )
            trade = backtest_trade_from_feature(
                feature=annotated,
                prices_by_ticker=prices,
                window_end=spec["end"],
                rank=selected_rank,
                config=PROFILE_CONFIG,
            )
            if trade is None:
                continue
            active.append({"ticker": trade["ticker"], "exit_date": trade["exit_date"]})
            active_tickers.add(trade["ticker"])
            selected_today.append(trade["ticker"])

    return {"selected_rows": selected_rows, "blocked_rows": blocked_rows}


def _variant_trades(
    *,
    selected_rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    label: str,
) -> list[dict[str, Any]]:
    spec = WINDOWS[label]
    trades: list[dict[str, Any]] = []
    for row in selected_rows:
        trade = backtest_trade_from_feature(
            feature=row["feature"],
            prices_by_ticker=prices,
            window_end=spec["end"],
            rank=int(row["rank"]),
            config=PROFILE_CONFIG,
        )
        if trade is None:
            continue
        trade["window"] = label
        trade["correlation_cap_applied"] = row["feature"].get("correlation_cap_applied")
        trade["max_positive_corr_to_open_or_selected"] = row["feature"].get(
            "max_positive_corr_to_open_or_selected"
        )
        trade["correlation_reference_ticker"] = row["feature"].get(
            "correlation_reference_ticker"
        )
        trade["max_positive_corr_cap"] = row["feature"].get("max_positive_corr_cap")
        trade["active_reference_count"] = row["feature"].get("active_reference_count")
        trade["day_candidate_count"] = row["feature"].get("day_candidate_count")
        trade["candidate_queue_rank"] = row["feature"].get("candidate_queue_rank")
        trades.append(trade)
    return trades


def _trade_key(trade: dict[str, Any]) -> tuple[str, str, str]:
    return (str(trade["window"]), str(trade["decision_date"]), str(trade["ticker"]))


def _trade_rows(trades: list[dict[str, Any]], *, limit: int = 60) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in sorted(trades, key=lambda row: (row["entry_date"], row["ticker"]))[:limit]:
        rows.append(
            {
                "ticker": trade["ticker"],
                "window": trade["window"],
                "decision_date": trade["decision_date"],
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "pnl": trade["pnl"],
                "net_return_pct": trade["net_return_pct"],
                "rank": trade["rank"],
                "candidate_queue_rank": trade.get("candidate_queue_rank"),
                "score": trade["score"],
                "ret20_excess_spy": trade["ret20_excess_spy"],
                "ret5": trade.get("ret5"),
                "ret60": trade["ret60"],
                "volume_ratio_20": trade["volume_ratio_20"],
                "near_high_60": trade["near_high_60"],
                "realized_volatility_20": trade.get("realized_volatility_20"),
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "notional": trade.get("notional"),
                "correlation_cap_applied": trade.get("correlation_cap_applied"),
                "max_positive_corr_to_open_or_selected": trade.get(
                    "max_positive_corr_to_open_or_selected"
                ),
                "correlation_reference_ticker": trade.get("correlation_reference_ticker"),
                "max_positive_corr_cap": trade.get("max_positive_corr_cap"),
                "active_reference_count": trade.get("active_reference_count"),
                "day_candidate_count": trade.get("day_candidate_count"),
            }
        )
    return rows


def _window_sleeve_summary(
    trades: list[dict[str, Any]],
    scout: dict[str, Any],
    blocked_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    base = p35._window_sleeve_summary(trades, scout)
    base["correlation_blocked_count"] = len(blocked_rows)
    base["correlation_blocked_sample"] = blocked_rows[:20]
    base["sample_trades"] = _trade_rows(trades, limit=25)
    return base


def _variant_payload(
    *,
    variant_name: str,
    max_positive_corr: float | None,
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    identity_keys: set[tuple[str, str, str]] | None,
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    all_blocked: list[dict[str, Any]] = []

    for label, spec in WINDOWS.items():
        selected = _select_rows_for_window(
            label=label,
            candidate_tickers=candidate_tickers,
            prices=prices,
            indexes=indexes,
            max_positive_corr=max_positive_corr,
        )
        trades = _variant_trades(
            selected_rows=selected["selected_rows"],
            prices=prices,
            label=label,
        )
        blocked_rows = selected["blocked_rows"]
        all_trades.extend(trades)
        all_blocked.extend(blocked_rows)
        curve = p35._event_equity_curve(
            trades=trades,
            prices=prices,
            start=spec["start"],
            end=spec["end"],
        )
        after_metrics[label] = p35._metrics_from_overlay(
            baseline_metrics=control_metrics[label],
            event_curve=curve,
            event_trades=trades,
        )
        sleeve[label] = _window_sleeve_summary(
            trades,
            {
                "trades": trades,
                "candidate_signal_days": None,
                "candidate_signal_count": None,
                "max_daily_candidate_count": None,
            },
            blocked_rows,
        )

    keys = {_trade_key(row) for row in all_trades}
    if identity_keys is None:
        replaced_count = 0
        replaced_windows: list[str] = []
    else:
        replacement_keys = keys - identity_keys
        replaced_count = len(replacement_keys)
        replaced_windows = sorted({key[0] for key in replacement_keys})

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = p35._single_ticker_positive_share(all_trades)
    top5_share = p35._top5_positive_share(all_trades)
    relative_ev_improvement = float(delta["aggregate_ev_delta_pct"] or 0.0)
    sample_guard_passed = len(all_trades) >= p35.MIN_SELECTED_TRADES
    replacement_guard_passed = (
        replaced_count >= MIN_REPLACED_TRADES
        and len(replaced_windows) >= MIN_REPLACED_WINDOWS
    )
    window_guard_passed = selected_windows >= p35.MIN_SELECTED_WINDOWS
    concentration_guard_passed = (
        (single_share is None or single_share <= p35.MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (top5_share is None or top5_share <= p35.MAX_TOP5_POSITIVE_SHARE)
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= p35.MAX_DRAWDOWN_WORSE
    materiality_guard_passed = relative_ev_improvement >= MIN_RELATIVE_EV_IMPROVEMENT
    gate4_passed = bool(
        variant_name != "baseline_no_correlation_cap"
        and delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and delta["windows_pnl_regressed"] == 0
        and sample_guard_passed
        and replacement_guard_passed
        and window_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
        and materiality_guard_passed
    )
    return {
        "variant_name": variant_name,
        "max_positive_corr": max_positive_corr,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "replaced_trade_count": replaced_count,
        "replaced_windows": replaced_windows,
        "correlation_blocked_count": len(all_blocked),
        "correlation_blocked_windows": sorted({row["window"] for row in all_blocked}),
        "correlation_blocked_sample": all_blocked[:60],
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": p35._event_risk(all_trades),
        "selected_trades_sample": _trade_rows(all_trades, limit=60),
        "replacement_trades_sample": [
            row for row in _trade_rows(all_trades, limit=200) if _trade_key(row) not in (identity_keys or set())
        ][:40],
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta": delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
            "relative_ev_improvement": relative_ev_improvement,
            "minimum_relative_ev_improvement": MIN_RELATIVE_EV_IMPROVEMENT,
            "materiality_guard_passed": materiality_guard_passed,
            "windows_ev_improved": delta["windows_ev_improved"],
            "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
            "windows_ev_regressed": delta["windows_ev_regressed"],
            "windows_pnl_improved": delta["windows_pnl_improved"],
            "windows_pnl_regressed": delta["windows_pnl_regressed"],
            "selected_trade_count": len(all_trades),
            "minimum_selected_trades": p35.MIN_SELECTED_TRADES,
            "sample_guard_passed": sample_guard_passed,
            "replaced_trade_count": replaced_count,
            "minimum_replaced_trades": MIN_REPLACED_TRADES,
            "replaced_windows": replaced_windows,
            "minimum_replaced_windows": MIN_REPLACED_WINDOWS,
            "replacement_guard_passed": replacement_guard_passed,
            "selected_windows": selected_windows,
            "minimum_selected_windows": p35.MIN_SELECTED_WINDOWS,
            "window_guard_passed": window_guard_passed,
            "single_ticker_positive_share": single_share,
            "max_single_ticker_positive_share": p35.MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "top5_positive_share": top5_share,
            "max_top5_positive_share": p35.MAX_TOP5_POSITIVE_SHARE,
            "concentration_guard_passed": concentration_guard_passed,
            "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
            "max_drawdown_worse_guardrail": p35.MAX_DRAWDOWN_WORSE,
            "drawdown_guard_passed": drawdown_guard_passed,
        },
    }


def _choose_selected(variants: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in variants if row["gate4"]["passed"]]
    pool = passing or [
        row for row in variants if row["variant_name"] != "baseline_no_correlation_cap"
    ]
    return sorted(
        pool,
        key=lambda row: (
            bool(row["gate4"]["passed"]),
            float(row["delta_metrics"]["aggregate_ev_delta"]),
            float(row["delta_metrics"]["aggregate_pnl_delta"]),
            -float(row["gate4"]["max_drawdown_worse_max"]),
        ),
        reverse=True,
    )[0]


def _sweep_summary(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "variant_name": row["variant_name"],
            "max_positive_corr": row["max_positive_corr"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "replaced_trade_count": row["replaced_trade_count"],
            "replaced_windows": row["replaced_windows"],
            "correlation_blocked_count": row["correlation_blocked_count"],
            "aggregate_ev_delta": row["delta_metrics"]["aggregate_ev_delta"],
            "relative_ev_improvement": row["gate4"]["relative_ev_improvement"],
            "aggregate_pnl_delta": row["delta_metrics"]["aggregate_pnl_delta"],
            "windows_ev_improved": row["gate4"]["windows_ev_improved"],
            "windows_ev_regressed": row["gate4"]["windows_ev_regressed"],
            "windows_pnl_regressed": row["gate4"]["windows_pnl_regressed"],
            "max_drawdown_worse_max": row["gate4"]["max_drawdown_worse_max"],
            "single_ticker_positive_share": row["single_ticker_positive_share"],
            "top5_positive_share": row["top5_positive_share"],
            "materiality_guard_passed": row["gate4"]["materiality_guard_passed"],
        }
        for row in variants
    ]


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Correlation Crowding Replacement",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single causal variable: trailing-20-day positive return correlation cap "
            "against already-open or same-day selected broad-market sleeve names."
        ),
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Replaced | Blocked | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse | Top5 Share |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        top5 = row["top5_positive_share"]
        lines.append(
            "| {variant} | {gate} | {replaced} | {blocked} | {ev:+.4f} | {rel:+.2%} | ${pnl:+,.2f} | {wi} | {wr} | {dd:+.4%} | {top5} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["passed"] else "FAIL",
                replaced=row["replaced_trade_count"],
                blocked=row["correlation_blocked_count"],
                ev=float(row["aggregate_ev_delta"] or 0.0),
                rel=float(row["relative_ev_improvement"] or 0.0),
                pnl=float(row["aggregate_pnl_delta"] or 0.0),
                wi=row["windows_ev_improved"],
                wr=row["windows_ev_regressed"],
                dd=float(row["max_drawdown_worse_max"] or 0.0),
                top5=f"{top5:.2%}" if top5 is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Evidence",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
            )
        )
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


def build_payload() -> dict[str, Any]:
    if not BASELINE_JSON.exists():
        raise RuntimeError(f"Missing baseline artifact: {_repo_rel(BASELINE_JSON)}")
    if not CONTROL_JSON.exists():
        raise RuntimeError(f"Missing control artifact: {_repo_rel(CONTROL_JSON)}")

    gate2 = p35._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = _json_load(BASELINE_JSON)
    control_payload = _json_load(CONTROL_JSON)
    expected_decision = "accepted_default_off_broad_market_trend_persistence_notional"
    if baseline_payload.get("decision") != expected_decision:
        raise RuntimeError(f"Unexpected baseline decision: {baseline_payload.get('decision')}")

    control_metrics = control_payload["before_metrics"]
    before_metrics = baseline_payload["after_metrics"]
    warehouse = p35._warehouse_audit()
    candidate_universe = baseline_payload["candidate_universe"]
    frozen_tickers = list(candidate_universe["tickers"])
    prices = p35._load_price_rows(frozen_tickers)
    indexes = p35._index_by_date(prices)

    identity_values = CORRELATION_CAP_SWEEP["baseline_no_correlation_cap"]
    identity = _variant_payload(
        variant_name="baseline_no_correlation_cap",
        max_positive_corr=identity_values["max_positive_corr"],
        control_metrics=control_metrics,
        before_metrics=before_metrics,
        candidate_tickers=frozen_tickers,
        prices=prices,
        indexes=indexes,
        identity_keys=None,
    )
    identity_keys = {
        _trade_key(row)
        for row in sum(
            [
                _variant_trades(
                    selected_rows=_select_rows_for_window(
                        label=label,
                        candidate_tickers=frozen_tickers,
                        prices=prices,
                        indexes=indexes,
                        max_positive_corr=None,
                    )["selected_rows"],
                    prices=prices,
                    label=label,
                )
                for label in WINDOWS
            ],
            [],
        )
    }
    variants = [identity]
    variants.extend(
        _variant_payload(
            variant_name=name,
            max_positive_corr=values["max_positive_corr"],
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            candidate_tickers=frozen_tickers,
            prices=prices,
            indexes=indexes,
            identity_keys=identity_keys,
        )
        for name, values in CORRELATION_CAP_SWEEP.items()
        if name != "baseline_no_correlation_cap"
    )

    identity_control = {
        "passed": (
            abs(float(identity["delta_metrics"]["aggregate_ev_delta"])) < 1e-9
            and abs(float(identity["delta_metrics"]["aggregate_pnl_delta"])) < 0.01
            and abs(float(identity["gate4"]["max_drawdown_worse_max"])) < 1e-9
        ),
        "variant_name": identity["variant_name"],
        "aggregate_ev_delta_vs_accepted_artifact": identity["delta_metrics"]["aggregate_ev_delta"],
        "aggregate_pnl_delta_vs_accepted_artifact": identity["delta_metrics"]["aggregate_pnl_delta"],
        "max_drawdown_worse_max_vs_accepted_artifact": identity["gate4"]["max_drawdown_worse_max"],
    }

    selected = _choose_selected(variants)
    selected["gate4"]["identity_control_passed"] = identity_control["passed"]
    if not identity_control["passed"]:
        selected["gate4"]["passed"] = False
    accepted = selected["gate4"]["passed"]
    decision = (
        "accepted_default_off_broad_market_correlation_crowding"
        if accepted
        else "rejected_broad_market_correlation_crowding"
    )
    status = "accepted" if accepted else "rejected"
    aggregate_before = p35._aggregate(before_metrics)
    aggregate_after = p35._aggregate(selected["after_metrics"])
    gate3 = {
        "signals_generated": {
            label: before_metrics[label].get("signals_generated") for label in WINDOWS
        },
        "signals_survived": {
            label: before_metrics[label].get("signals_survived") for label in WINDOWS
        },
        "survival_rate": {
            label: before_metrics[label].get("survival_rate") for label in WINDOWS
        },
        "survival_rate_min": aggregate_before["survival_rate_min"],
        "passed": aggregate_before["survival_rate_min"] >= 0.05,
        "note": "No core filter was added; broad-market sleeve remains default-off paper only.",
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "parity_test_added": False,
        "live_order_path_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Broad-market momentum leaders can cluster into the same hidden beta. "
            "Replacing high trailing-correlation candidates with the next ranked "
            "eligible candidate may improve the default-off paper sleeve by "
            "reducing crowded downside without adding new tickers or LLM fields."
        ),
        "change_type": "default_off_paper_candidate_selection",
        "changed_variable": "broad_market_trailing20_positive_correlation_crowding_cap",
        "single_causal_variable": "positive trailing-20-day correlation cap against open or same-day selected broad-market names",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "reference_experiment_id": REFERENCE_EXPERIMENT_ID,
            "selected_variant": selected["variant_name"],
            "selected_max_positive_corr": selected["max_positive_corr"],
            "lookback_days": LOOKBACK_DAYS,
            "minimum_correlation_pairs": MIN_CORRELATION_PAIRS,
            "minimum_relative_ev_improvement": MIN_RELATIVE_EV_IMPROVEMENT,
            "sweep": CORRELATION_CAP_SWEEP,
            "profile_config": {
                key: PROFILE_CONFIG[key]
                for key in (
                    "ret20_excess_spy_min",
                    "ret60_min",
                    "near_high_60_min",
                    "volume_ratio_20_min",
                    "decision_close_price_min",
                    "paper_notional_usd",
                    "rank_notional_multipliers",
                    "low_extension_ret5_max",
                    "low_extension_notional_scalar",
                    "high_volatility_20_min",
                    "high_volatility_notional_scalar",
                    "trend_persistence_positive_day_ratio_20_min",
                    "trend_persistence_notional_scalar",
                    "max_active_positions",
                    "daily_entry_slots",
                    "hold_days",
                )
            },
            "candidate_count": candidate_universe.get("candidate_count"),
            "excluded_count": candidate_universe.get("excluded_count"),
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"]} for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260520-004 trend-persistence broad-market adapter is the before "
            "state; after state adds a correlation-crowding replacement rule."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(BASELINE_JSON),
            "control_artifact": _repo_rel(CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
        },
        "gate2": gate2,
        "gate3": gate3,
        "identity_control": identity_control,
        "gate4": selected["gate4"],
        "before_metrics": before_metrics,
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "expected_value_score_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_ev_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "total_pnl_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_pnl_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["total_pnl"]
                for label in WINDOWS
            },
        },
        "sweep_summary": _sweep_summary(variants),
        "selected_variant": {
            "variant_name": selected["variant_name"],
            "max_positive_corr": selected["max_positive_corr"],
            "selected_trade_count": selected["selected_trade_count"],
            "replaced_trade_count": selected["replaced_trade_count"],
            "replaced_windows": selected["replaced_windows"],
            "correlation_blocked_count": selected["correlation_blocked_count"],
            "correlation_blocked_windows": selected["correlation_blocked_windows"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "replacement_trades_sample": selected["replacement_trades_sample"],
            "correlation_blocked_sample": selected["correlation_blocked_sample"],
        },
        "broad_market_sleeve": selected["broad_market_sleeve"],
        "candidate_universe": candidate_universe,
        "warehouse_audit": warehouse,
        "llm_metrics": {
            "changed": False,
            "reason": "This run avoids sparse LLM soft-ranking and does not alter LLM prompts or decisions.",
        },
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": "ranking/selection: avoid hidden-beta crowding by replacing candidates whose trailing 20-day positive correlation to open/same-day selected broad-market names is too high.",
            "2_past_similar_experiments": "Broad-market price-floor, rank-notional, low-extension ret5, high-volatility, trend-persistence, score-gap, strong-close crowding, recent-repeat, absolute-score, trend-efficiency, red-day pullback, and max-daily-return variants were tested; trailing-correlation replacement was not formalized for this sleeve.",
            "3_single_variable": "Only max_positive_corr changes; universe, eligibility profile, rank profile, accepted notional scalars, hold, slots, and candidate source stay fixed.",
            "4_acceptance": "Gate 4 requires positive aggregate EV/PnL, all 3 windows EV-positive, no EV/PnL regression windows, >=4 replacements across >=2 windows, concentration guard, <=0.5pp max drawdown worsening, identity control, and >=10% aggregate EV improvement due frozen-sample broad-market crowding retune risk.",
            "5_reproducibility": "Script, JSON artifact, log, ticket, markdown artifact, and JSONL identify windows, parameters, selected/blocked examples, and metrics.",
        },
        "interpretation": (
            "Trailing correlation is a production-visible crowding proxy aligned "
            "with the playbook's broad-market hidden-beta governance direction. "
            "Because this still modifies a frozen default-off sleeve selection "
            "surface, no shared adapter is changed unless the strict materiality "
            "gate is cleared."
        ),
        "rejection_reason": None
        if accepted
        else "Correlation-crowding replacement did not clear the strict three-window broad-market materiality gate.",
        "next_evidence_needed": (
            "If forward broad-market paper trades show high-correlation clusters "
            "driving losses, retest with live ledger replacement-value evidence "
            "before enabling any shared selection rule."
        ),
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
            "baseline": _repo_rel(BASELINE_JSON),
            "control": _repo_rel(CONTROL_JSON),
        },
    }
    return payload


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
    }
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(json.dumps(_safe(payload["sweep_summary"]), indent=2, sort_keys=True))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "selected_variant": payload["selected_variant"]["variant_name"],
                    "gate4": payload["gate4"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "output": payload["related_files"]["output"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
