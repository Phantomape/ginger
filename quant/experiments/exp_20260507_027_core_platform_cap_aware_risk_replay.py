"""exp-20260507-027: core platform cap-aware risk replay.

Alpha search, replay-only. Core platform entry timing (exp-20260507-008) and
post-target runner exits (exp-20260507-014) both failed. This experiment asks a
cleaner lifecycle-allocation question: when the existing system already enters
NFLX/APP/META-style platform leaders, is there cap-aware risk-budget headroom
worth using?

Only already-entered treatment-pool trades are resized, and only up to the
position cap implied by the baseline trade's existing sizing context. Entries,
ranking, exits, add-ons, universe, LLM/news, and signal generation are locked.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import (  # noqa: E402
    MAX_POSITION_PCT,
    RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT,
)


EXPERIMENT_ID = "exp-20260507-027"
SOURCE_EXPERIMENT_ID = "exp-20260507-013"
STEM = "core_platform_cap_aware_risk_replay"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

INITIAL_CAPITAL = 100_000.0
TREATMENT_POOL = ("NFLX", "APP", "META", "GOOG", "AMZN", "SPOT", "DIS")
CONTROL_POOL = ("AAPL", "MSFT", "PLTR", "DDOG", "SNOW", "NOW")

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_late_strong.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_mid_weak.json"
                ),
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_old_thin.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        ("core_platform_1_25x_cap_aware", {"risk_multiplier": 1.25}),
        ("core_platform_1_50x_cap_aware", {"risk_multiplier": 1.50}),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(snapshot_path)
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected OHLCV snapshot shape: {snapshot_path}")
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        if not isinstance(rows, list):
            continue
        clean = [row for row in rows if isinstance(row, dict) and row.get("Date")]
        out[str(ticker).upper()] = sorted(clean, key=lambda row: str(row["Date"]))
    return out


def _close(row: dict[str, Any]) -> float | None:
    return _float(row.get("Close"))


def _date_value(row: dict[str, Any]) -> str:
    return str(row.get("Date"))[:10]


def _idx_for_date(rows: list[dict[str, Any]], date_str: str | None) -> int | None:
    if not date_str:
        return None
    target = str(date_str)[:10]
    for idx, row in enumerate(rows):
        if _date_value(row) == target:
            return idx
    return None


def _window_dates(spy_rows: list[dict[str, Any]], start: str, end: str) -> list[str]:
    return [_date_value(row) for row in spy_rows if start <= _date_value(row) <= end]


def _as_trade(trade: dict[str, Any]) -> dict[str, Any]:
    out = dict(trade)
    out["status"] = "closed"
    return out


def _trade_key(trade: dict[str, Any]) -> str:
    explicit = trade.get("trade_key")
    if explicit:
        return str(explicit)
    return "|".join(
        [
            str(trade.get("ticker") or ""),
            str(trade.get("strategy") or ""),
            str(trade.get("entry_date") or ""),
            str(trade.get("entry_price") or ""),
        ]
    )


def _daily_equity_series(
    trades: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
    start: str,
    end: str,
) -> OrderedDict[str, float]:
    dates = _window_dates(spy_rows, start, end)
    realized_by_date: defaultdict[str, float] = defaultdict(float)
    for trade in trades:
        realized_by_date[str(trade.get("exit_date") or "")[:10]] += float(
            trade.get("pnl") or 0.0
        )

    realized = 0.0
    out: OrderedDict[str, float] = OrderedDict()
    for date_str in dates:
        realized += realized_by_date.get(date_str, 0.0)
        unrealized = 0.0
        for trade in trades:
            entry_date = str(trade.get("entry_date") or "")[:10]
            exit_date = str(trade.get("exit_date") or "")[:10]
            if not (entry_date <= date_str < exit_date):
                continue
            rows = rows_by_ticker.get(str(trade.get("ticker") or "").upper())
            if not rows:
                continue
            idx = _idx_for_date(rows, date_str)
            close = _close(rows[idx]) if idx is not None else None
            entry_price = _float(trade.get("entry_price"))
            shares = int(trade.get("shares") or 0)
            if close is not None and entry_price is not None:
                unrealized += (close - entry_price) * shares
        out[date_str] = INITIAL_CAPITAL + realized + unrealized
    return out


def _daily_equity_metrics(
    trades: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    spy_rows: list[dict[str, Any]],
    start: str,
    end: str,
) -> dict[str, Any]:
    series = _daily_equity_series(trades, rows_by_ticker, spy_rows, start, end)
    if not series:
        return {
            "expected_value_score": None,
            "total_pnl": None,
            "total_return_pct": None,
            "sharpe_daily": None,
            "max_drawdown_pct": None,
            "win_rate": None,
            "trade_count": 0,
        }
    closed = [trade for trade in trades if trade.get("entry_date") and trade.get("exit_date")]
    total_pnl = sum(float(trade.get("pnl") or 0.0) for trade in closed)
    wins = sum(1 for trade in closed if float(trade.get("pnl") or 0.0) > 0)
    values = list(series.values())
    peak = INITIAL_CAPITAL
    max_dd = 0.0
    for equity in values:
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    returns = [cur / prev - 1.0 for prev, cur in zip(values, values[1:]) if prev]
    if len(returns) > 1:
        avg = sum(returns) / len(returns)
        stdev = statistics.pstdev(returns)
        sharpe = (avg / stdev) * math.sqrt(252) if stdev > 0 else None
    else:
        sharpe = None
    total_return = total_pnl / INITIAL_CAPITAL
    ev = total_return * sharpe if sharpe is not None else None
    return {
        "expected_value_score": _round(ev, 4),
        "total_pnl": _round(total_pnl, 2),
        "total_return_pct": _round(total_return, 4),
        "sharpe_daily": _round(sharpe, 2),
        "max_drawdown_pct": _round(max_dd, 4),
        "win_rate": _round(wins / len(closed), 4) if closed else None,
        "trade_count": len(closed),
    }


def _position_cap_pct(trade: dict[str, Any]) -> tuple[float, str]:
    multipliers = trade.get("sizing_multipliers")
    if isinstance(multipliers, dict) and "spy_relative_leader_risk_on_multiplier_applied" in multipliers:
        return RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT, "spy_relative_leader_cap"
    return MAX_POSITION_PCT, "default_initial_cap"


def _resize_trade(
    trade: dict[str, Any],
    *,
    new_shares: int,
    reason: str,
    cap_pct: float,
    cap_source: str,
    entry_equity: float,
) -> dict[str, Any]:
    old_shares = int(trade.get("shares") or 0)
    old_pnl = _float(trade.get("pnl")) or 0.0
    old_pnl_pct = _float(trade.get("pnl_pct_net"))
    pnl_per_share = old_pnl / old_shares if old_shares else 0.0
    out = dict(trade)
    out.update(
        {
            "shares": int(new_shares),
            "pnl": _round(pnl_per_share * new_shares, 2),
            "pnl_pct_net": _round(old_pnl_pct, 6),
            "risk_replay": {
                "reason": reason,
                "baseline_shares": old_shares,
                "replay_shares": int(new_shares),
                "shares_delta": int(new_shares - old_shares),
                "position_cap_pct": cap_pct,
                "position_cap_source": cap_source,
                "entry_proxy_equity": _round(entry_equity, 2),
            },
        }
    )
    return out


def _variant_trades(
    trades: list[dict[str, Any]],
    baseline_equity: OrderedDict[str, float],
    *,
    risk_multiplier: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    touched = 0
    changed = 0

    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        if ticker not in TREATMENT_POOL:
            out.append(trade)
            continue

        touched += 1
        old_shares = int(trade.get("shares") or 0)
        entry_price = _float(trade.get("entry_price"))
        entry_date = str(trade.get("entry_date") or "")[:10]
        entry_equity = baseline_equity.get(entry_date)
        cap_pct, cap_source = _position_cap_pct(trade)

        if old_shares <= 0 or entry_price is None or entry_equity is None:
            status = "missing_resize_inputs"
            status_counts[status] += 1
            out.append(trade)
            continue

        desired_shares = max(old_shares, int(math.floor(old_shares * risk_multiplier)))
        cap_shares = int(math.floor((entry_equity * cap_pct) / entry_price))
        replay_shares = min(desired_shares, cap_shares)
        if replay_shares <= old_shares:
            status = "cap_bound_no_headroom"
            status_counts[status] += 1
            out.append(trade)
            details.append(
                {
                    "ticker": ticker,
                    "strategy": trade.get("strategy"),
                    "entry_date": entry_date,
                    "baseline_shares": old_shares,
                    "desired_shares": desired_shares,
                    "cap_shares": cap_shares,
                    "replay_shares": old_shares,
                    "status": status,
                    "baseline_pnl": _round(trade.get("pnl"), 2),
                    "pnl_delta": 0.0,
                    "cap_pct": cap_pct,
                    "cap_source": cap_source,
                    "entry_proxy_equity": _round(entry_equity, 2),
                }
            )
            continue

        replacement = _resize_trade(
            trade,
            new_shares=replay_shares,
            reason="cap_aware_core_platform_risk_multiplier",
            cap_pct=cap_pct,
            cap_source=cap_source,
            entry_equity=entry_equity,
        )
        old_pnl = _float(trade.get("pnl")) or 0.0
        new_pnl = _float(replacement.get("pnl")) or 0.0
        pnl_delta = new_pnl - old_pnl
        changed += 1
        status = "resized"
        status_counts[status] += 1
        pnl_delta_by_ticker[ticker] += pnl_delta
        out.append(replacement)
        details.append(
            {
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "entry_date": entry_date,
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "baseline_shares": old_shares,
                "desired_shares": desired_shares,
                "cap_shares": cap_shares,
                "replay_shares": replay_shares,
                "status": status,
                "baseline_pnl": _round(old_pnl, 2),
                "variant_pnl": _round(new_pnl, 2),
                "pnl_delta": _round(pnl_delta, 2),
                "cap_pct": cap_pct,
                "cap_source": cap_source,
                "entry_proxy_equity": _round(entry_equity, 2),
            }
        )

    return out, {
        "touched_treatment_trades": touched,
        "changed_treatment_trades": changed,
        "status_counts": dict(sorted(status_counts.items())),
        "pnl_delta_by_ticker": {
            ticker: _round(value, 2) for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
        "details": details,
    }


def _window_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") if isinstance(result.get("benchmarks"), dict) else {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _replay_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    ohlcv = _load_ohlcv(REPO_ROOT / spec["snapshot"])
    result = _load_json(REPO_ROOT / spec["backtest_results"])
    trades = [_as_trade(trade) for trade in result.get("trades") or []]
    spy_rows = ohlcv.get("SPY") or []
    baseline_equity = _daily_equity_series(trades, ohlcv, spy_rows, spec["start"], spec["end"])
    proxy_before = _daily_equity_metrics(trades, ohlcv, spy_rows, spec["start"], spec["end"])

    variant_results = {}
    for variant_name, variant in VARIANTS.items():
        resized_trades, meta = _variant_trades(
            trades,
            baseline_equity,
            risk_multiplier=float(variant["risk_multiplier"]),
        )
        proxy_after = _daily_equity_metrics(
            resized_trades,
            ohlcv,
            spy_rows,
            spec["start"],
            spec["end"],
        )
        ev_delta = None
        if (
            proxy_after.get("expected_value_score") is not None
            and proxy_before.get("expected_value_score") is not None
        ):
            ev_delta = proxy_after["expected_value_score"] - proxy_before["expected_value_score"]
        variant_results[variant_name] = {
            "metrics": proxy_after,
            "delta_vs_proxy_before": {
                "expected_value_score": _round(ev_delta, 4),
                "total_pnl": _round(proxy_after["total_pnl"] - proxy_before["total_pnl"], 2),
                "sharpe_daily": _round(proxy_after["sharpe_daily"] - proxy_before["sharpe_daily"], 2),
                "max_drawdown_pct": _round(
                    proxy_after["max_drawdown_pct"] - proxy_before["max_drawdown_pct"],
                    4,
                ),
                "trade_count": proxy_after["trade_count"] - proxy_before["trade_count"],
            },
            **meta,
        }

    return {
        "window": name,
        "window_spec": spec,
        "official_baseline_metrics": _window_metrics(result),
        "proxy_before_metrics": proxy_before,
        "baseline_trade_count": len(trades),
        "treatment_trade_count": sum(
            1 for trade in trades if str(trade.get("ticker") or "").upper() in TREATMENT_POOL
        ),
        "variant_results": variant_results,
    }


def _positive_share(pnl_delta_by_ticker: dict[str, float]) -> float | None:
    positives = [value for value in pnl_delta_by_ticker.values() if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    baseline_ev_sum = sum(
        (window.get("proxy_before_metrics") or {}).get("expected_value_score") or 0.0
        for window in by_window.values()
    )
    baseline_pnl_sum = sum(
        (window.get("proxy_before_metrics") or {}).get("total_pnl") or 0.0
        for window in by_window.values()
    )
    out: dict[str, Any] = {}
    for variant_name in VARIANTS:
        after_ev_sum = 0.0
        after_pnl_sum = 0.0
        touched_sum = 0
        changed_sum = 0
        improved = 0
        regressed = 0
        max_dd_worsening = 0.0
        by_window_delta = {}
        status_counts: Counter[str] = Counter()
        pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
        for window_name, window in by_window.items():
            variant = window["variant_results"][variant_name]
            metrics = variant["metrics"]
            delta = variant["delta_vs_proxy_before"]
            after_ev_sum += metrics.get("expected_value_score") or 0.0
            after_pnl_sum += metrics.get("total_pnl") or 0.0
            touched_sum += variant.get("touched_treatment_trades") or 0
            changed_sum += variant.get("changed_treatment_trades") or 0
            ev_delta = delta.get("expected_value_score") or 0.0
            if ev_delta > 0:
                improved += 1
            elif ev_delta < 0:
                regressed += 1
            max_dd_worsening = max(max_dd_worsening, delta.get("max_drawdown_pct") or 0.0)
            by_window_delta[window_name] = delta
            status_counts.update(variant.get("status_counts") or {})
            for ticker, value in (variant.get("pnl_delta_by_ticker") or {}).items():
                pnl_delta_by_ticker[ticker] += float(value or 0.0)

        ev_delta_sum = after_ev_sum - baseline_ev_sum
        pnl_delta_sum = after_pnl_sum - baseline_pnl_sum
        ev_delta_pct = ev_delta_sum / abs(baseline_ev_sum) if baseline_ev_sum else None
        ticker_deltas = {
            ticker: _round(value, 2) for ticker, value in sorted(pnl_delta_by_ticker.items())
        }
        max_single_share = _positive_share(dict(pnl_delta_by_ticker))
        gate_passed = (
            ev_delta_pct is not None
            and ev_delta_pct > 0.10
            and improved >= 2
            and max_dd_worsening <= 0.01
            and touched_sum >= 8
            and changed_sum >= 3
            and (max_single_share is None or max_single_share <= 0.50)
        )
        out[variant_name] = {
            "baseline_proxy_expected_value_score_sum": _round(baseline_ev_sum, 4),
            "after_proxy_expected_value_score_sum": _round(after_ev_sum, 4),
            "expected_value_score_delta_sum": _round(ev_delta_sum, 4),
            "expected_value_score_delta_pct": _round(ev_delta_pct, 6),
            "baseline_proxy_total_pnl_sum": _round(baseline_pnl_sum, 2),
            "after_proxy_total_pnl_sum": _round(after_pnl_sum, 2),
            "total_pnl_delta_sum": _round(pnl_delta_sum, 2),
            "windows_ev_improved": improved,
            "windows_ev_regressed": regressed,
            "max_drawdown_worsening_max": _round(max_dd_worsening, 4),
            "touched_treatment_trades": touched_sum,
            "changed_treatment_trades": changed_sum,
            "status_counts": dict(sorted(status_counts.items())),
            "max_single_ticker_positive_share": _round(max_single_share, 4),
            "pnl_delta_by_ticker": ticker_deltas,
            "by_window_delta": by_window_delta,
            "proxy_gate4_passed": gate_passed,
        }
    return out


def _choose_best(aggregate: dict[str, Any]) -> str:
    return max(
        aggregate,
        key=lambda name: (
            aggregate[name].get("expected_value_score_delta_sum") or -10**9,
            aggregate[name].get("total_pnl_delta_sum") or -10**9,
        ),
    )


def _official_baseline_sum(by_window: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("expected_value_score")
                or 0.0
                for window in by_window.values()
            ),
            4,
        ),
        "total_pnl_sum": _round(
            sum(
                (window.get("official_baseline_metrics") or {}).get("total_pnl") or 0.0
                for window in by_window.values()
            ),
            2,
        ),
        "trade_count_sum": sum(
            int((window.get("official_baseline_metrics") or {}).get("trade_count") or 0)
            for window in by_window.values()
        ),
    }


def _log_record(
    payload: dict[str, Any],
    aggregate: dict[str, Any],
    best_variant: str,
    decision: str,
    rejection_reason: str | None,
) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": "sizing",
        "change_type": "cap_aware_risk_replay",
        "mechanism_family": "core_platform_lifecycle_allocation",
        "single_causal_variable": "core_platform_risk_multiplier",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "before_metrics": {
            name: window["official_baseline_metrics"]
            for name, window in payload["by_window"].items()
        },
        "proxy_before_metrics": {
            name: window["proxy_before_metrics"] for name, window in payload["by_window"].items()
        },
        "after_metrics": {
            variant: {
                name: payload["by_window"][name]["variant_results"][variant]["metrics"]
                for name in payload["by_window"]
            }
            for variant in VARIANTS
        },
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "expected_value_score_delta": aggregate[best_variant][
            "expected_value_score_delta_sum"
        ],
        "gate4": {
            "passed": bool(aggregate[best_variant]["proxy_gate4_passed"]),
            "basis": (
                "Replay-only cap-aware resize of baseline entered trades. "
                "Promotion requires a shared risk policy in run.py/backtester.py."
            ),
        },
        "production_impact": payload["production_impact"],
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM/news replay is locked out of this sizing replay.",
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
    }


def _ticket(best_variant: str, decision: str, aggregate: dict[str, Any]) -> dict[str, Any]:
    best = aggregate[best_variant]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Core platform cap-aware risk replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta_sum": best["expected_value_score_delta_sum"],
        "total_pnl_delta_sum": best["total_pnl_delta_sum"],
        "next_action": (
            "Promote only after implementing a shared risk policy and parity tests."
            if best["proxy_gate4_passed"]
            else "Do not promote; avoid nearby cap-aware platform risk scalars without new evidence."
        ),
    }


def _artifact_markdown(
    payload: dict[str, Any],
    aggregate: dict[str, Any],
    best_variant: str,
    decision: str,
    rejection_reason: str | None,
) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Core Platform Cap-Aware Risk Replay",
        "",
        f"Decision: `{decision}`",
        f"Best variant: `{best_variant}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Baseline",
        "",
        "| EV sum | PnL sum | Trades |",
        "|---:|---:|---:|",
        "| {ev} | {pnl} | {trades} |".format(
            ev=payload["official_baseline_metrics"]["expected_value_score_sum"],
            pnl=payload["official_baseline_metrics"]["total_pnl_sum"],
            trades=payload["official_baseline_metrics"]["trade_count_sum"],
        ),
        "",
        "## Aggregate Replay",
        "",
        "| Variant | EV delta | PnL delta | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, metrics in aggregate.items():
        lines.append(
            "| {name} | {ev} | {pnl} | {up}/{down} | {touched} | {changed} | {dd} | {share} | {gate} |".format(
                name=name,
                ev=metrics["expected_value_score_delta_sum"],
                pnl=metrics["total_pnl_delta_sum"],
                up=metrics["windows_ev_improved"],
                down=metrics["windows_ev_regressed"],
                touched=metrics["touched_treatment_trades"],
                changed=metrics["changed_treatment_trades"],
                dd=metrics["max_drawdown_worsening_max"],
                share=metrics["max_single_ticker_positive_share"],
                gate="PASS" if metrics["proxy_gate4_passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Replay only; no production path changed.",
            "- Single causal variable: core platform risk multiplier.",
            "- Position-cap headroom is enforced from proxy equity at entry.",
            "- Entries, ranking, exits, add-ons, universe, LLM/news, and earnings are locked.",
            "- This is not a consumer-platform universe promotion, entry timing retry, or runner-exit retry.",
        ]
    )
    if rejection_reason:
        lines.extend(["", "## Rejection Reason", "", rejection_reason])
    return "\n".join(lines) + "\n"


def main() -> None:
    by_window = OrderedDict((name, _replay_window(name, spec)) for name, spec in WINDOWS.items())
    aggregate = _aggregate(by_window)
    best_variant = _choose_best(aggregate)
    best = aggregate[best_variant]
    decision = "accepted_for_promotion_review" if best["proxy_gate4_passed"] else "rejected"
    rejection_reason = None
    if not best["proxy_gate4_passed"]:
        rejection_reason = (
            f"Best variant `{best_variant}` failed the pre-registered proxy gate: "
            f"EV delta {best['expected_value_score_delta_sum']} "
            f"({best['expected_value_score_delta_pct']}), windows improved/regressed "
            f"{best['windows_ev_improved']}/{best['windows_ev_regressed']}, "
            f"changed trades {best['changed_treatment_trades']} of "
            f"{best['touched_treatment_trades']} touched, max DD worsening "
            f"{best['max_drawdown_worsening_max']}, single ticker positive share "
            f"{best['max_single_ticker_positive_share']}."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Core platform trades may not need special entries or exits, but may "
            "deserve more capital only when the existing position cap leaves "
            "headroom after the baseline system has already selected them."
        ),
        "source_experiment": SOURCE_EXPERIMENT_ID,
        "history_check": {
            "exp-20260507-008": "Rejected platform pullback entry timing.",
            "exp-20260507-014": "Rejected platform post-target runner exit.",
            "exp-20260505-011_and_020": (
                "Rejected consumer-platform universe/gate. This run adds no "
                "names and changes only already-entered trade size."
            ),
            "exp-20260507-009_and_010": (
                "Recent broad/mid-dispersion sizing boosts were weak. This run "
                "uses a narrower platform cohort and enforces cap headroom."
            ),
            "mechanism_insight_conflict": (
                "No conflict: this is lifecycle allocation, not OHLCV entry, "
                "target-width, runner-exit, or universe expansion."
            ),
        },
        "parameters": {
            "treatment_pool": list(TREATMENT_POOL),
            "control_pool_diagnostic_only": list(CONTROL_POOL),
            "variants": VARIANTS,
            "position_cap_policy": {
                "default_initial_cap": MAX_POSITION_PCT,
                "spy_relative_leader_cap": RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT,
                "entry_equity_source": "baseline proxy daily equity at entry date",
                "if_cap_has_no_headroom": "leave baseline shares unchanged",
            },
            "promotion_gate": {
                "expected_value_score_delta_pct": "> 10%",
                "windows_ev_improved": ">= 2 of 3",
                "max_drawdown_worsening": "<= 0.01",
                "touched_treatment_trades": ">= 8",
                "changed_treatment_trades": ">= 3",
                "single_ticker_positive_contribution": "<= 50%",
            },
            "locked_variables": [
                "universe",
                "signal generation",
                "entry timing",
                "entry filters",
                "candidate ranking",
                "exits",
                "add-ons",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "best_variant": best_variant,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "official_baseline_metrics": _official_baseline_sum(by_window),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "alters_exits": False,
            "alters_sizing": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
        },
        "next_retry_requires": [
            "Do not retry nearby core-platform risk multipliers on this same sample if rejected.",
            "A valid retry needs forward paper evidence or a non-price event/news lifecycle discriminator.",
            "If promoted later, implement as shared risk policy consumed by run.py and backtester.py with parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
    }

    log_record = _log_record(payload, aggregate, best_variant, decision, rejection_reason)
    ticket = _ticket(best_variant, decision, aggregate)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(
        _artifact_markdown(payload, aggregate, best_variant, decision, rejection_reason),
        encoding="utf-8",
    )
    _append_jsonl(EXPERIMENT_LOG, log_record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "best_variant": best_variant,
                "best_delta": aggregate[best_variant],
                "out_json": str(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
