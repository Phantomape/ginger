"""exp-20260507-905: same-day entry-cluster tail-risk replay.

Alpha search, replay-only. The hold-quality audit in exp-20260507-903 found a
small but expensive same-entry-date loss cluster. This experiment asks the
tradable version: when the shared entry planner accepts multiple A/B trades on
the same signal date, does later-ranked cluster tail exposure deserve less risk?

Entries, candidate ordering, universe, LLM/news, earnings, exits, and add-ons
are locked. Only already-entered trend/breakout trades are resized in replay.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-905"
STEM = "same_day_entry_cluster_tail_risk"

INITIAL_CAPITAL = 100_000.0
CORE_STRATEGIES = {"trend_long", "breakout_long"}

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

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        (
            "cluster2_rank2plus_0_50x",
            {"min_cluster_size": 2, "rank_floor": 2, "risk_scalar": 0.50},
        ),
        (
            "cluster2_rank2plus_0_00x",
            {"min_cluster_size": 2, "rank_floor": 2, "risk_scalar": 0.00},
        ),
        (
            "cluster3_rank3plus_0_50x",
            {"min_cluster_size": 3, "rank_floor": 3, "risk_scalar": 0.50},
        ),
        (
            "cluster3_rank3plus_0_00x",
            {"min_cluster_size": 3, "rank_floor": 3, "risk_scalar": 0.00},
        ),
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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _date_value(row: dict[str, Any]) -> str:
    return str(row.get("Date"))[:10]


def _close(row: dict[str, Any]) -> float | None:
    return _float(row.get("Close"))


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
        if int(trade.get("shares") or 0) <= 0:
            continue
        realized_by_date[str(trade.get("exit_date") or "")[:10]] += float(
            trade.get("pnl") or 0.0
        )

    realized = 0.0
    out: OrderedDict[str, float] = OrderedDict()
    for date_str in dates:
        realized += realized_by_date.get(date_str, 0.0)
        unrealized = 0.0
        for trade in trades:
            shares = int(trade.get("shares") or 0)
            if shares <= 0:
                continue
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

    closed = [
        trade
        for trade in trades
        if trade.get("entry_date") and trade.get("exit_date") and int(trade.get("shares") or 0) > 0
    ]
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


def _run_backtest(spec: dict[str, Any]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        start=spec["start"],
        end=spec["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
        },
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        include_entry_candidate_events=True,
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _entered_candidate_meta(result: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in result.get("entry_candidate_events") or []:
        if event.get("decision") != "entered":
            continue
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        fill_date = str(details.get("fill_date") or "")[:10]
        ticker = str(event.get("ticker") or "").upper()
        strategy = str(event.get("strategy") or "")
        if not (ticker and strategy and fill_date):
            continue
        snapshot = event.get("signal_snapshot") if isinstance(event.get("signal_snapshot"), dict) else {}
        out[(ticker, strategy, fill_date)] = {
            "entry_plan_date": str(event.get("date") or "")[:10],
            "candidate_rank": int(event.get("candidate_rank") or 999999),
            "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
            "trade_quality_score": snapshot.get("trade_quality_score"),
            "confidence_score": snapshot.get("confidence_score"),
            "planned_shares": details.get("shares"),
        }
    return out


def _cluster_stats(
    trades: list[dict[str, Any]],
    meta_by_trade: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    clusters: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched = 0
    for trade in trades:
        strategy = str(trade.get("strategy") or "")
        if strategy not in CORE_STRATEGIES:
            continue
        key = (
            str(trade.get("ticker") or "").upper(),
            strategy,
            str(trade.get("entry_date") or "")[:10],
        )
        meta = meta_by_trade.get(key)
        if not meta:
            unmatched += 1
            continue
        clusters[meta["entry_plan_date"]].append(trade)

    sizes = Counter(len(items) for items in clusters.values())
    cluster_pnl_by_size: defaultdict[int, float] = defaultdict(float)
    for items in clusters.values():
        cluster_pnl_by_size[len(items)] += sum(float(t.get("pnl") or 0.0) for t in items)

    return {
        "core_entered_trades_with_candidate_meta": sum(len(items) for items in clusters.values()),
        "core_entered_trades_without_candidate_meta": unmatched,
        "entry_plan_cluster_size_counts": dict(sorted(sizes.items())),
        "cluster_pnl_by_size": {
            str(size): _round(pnl, 2) for size, pnl in sorted(cluster_pnl_by_size.items())
        },
    }


def _resize_trade(trade: dict[str, Any], *, new_shares: int, replay_meta: dict[str, Any]) -> dict[str, Any]:
    old_shares = int(trade.get("shares") or 0)
    old_pnl = _float(trade.get("pnl")) or 0.0
    old_pnl_pct = _float(trade.get("pnl_pct_net"))
    scalar = (new_shares / old_shares) if old_shares else 0.0
    out = dict(trade)
    out.update(
        {
            "shares": int(new_shares),
            "pnl": _round(old_pnl * scalar, 2),
            "pnl_pct_net": _round(old_pnl_pct, 6),
            "entry_cluster_tail_risk_replay": replay_meta,
        }
    )
    return out


def _variant_trades(
    trades: list[dict[str, Any]],
    meta_by_trade: dict[tuple[str, str, str], dict[str, Any]],
    *,
    min_cluster_size: int,
    rank_floor: int,
    risk_scalar: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    clusters: defaultdict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for trade in trades:
        strategy = str(trade.get("strategy") or "")
        if strategy not in CORE_STRATEGIES:
            continue
        key = (
            str(trade.get("ticker") or "").upper(),
            strategy,
            str(trade.get("entry_date") or "")[:10],
        )
        meta = meta_by_trade.get(key)
        if meta:
            clusters[meta["entry_plan_date"]].append((trade, meta))

    treatment_keys: dict[tuple[str, str, str], dict[str, Any]] = {}
    for plan_date, items in clusters.items():
        if len(items) < min_cluster_size:
            continue
        for trade, meta in items:
            rank = int(meta.get("candidate_rank") or 999999)
            if rank < rank_floor:
                continue
            key = (
                str(trade.get("ticker") or "").upper(),
                str(trade.get("strategy") or ""),
                str(trade.get("entry_date") or "")[:10],
            )
            treatment_keys[key] = {
                "entry_plan_date": plan_date,
                "entry_cluster_size": len(items),
                "candidate_rank": rank,
                "min_cluster_size": min_cluster_size,
                "rank_floor": rank_floor,
                "risk_scalar": risk_scalar,
            }

    out: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    touched = 0
    changed = 0

    for trade in trades:
        key = (
            str(trade.get("ticker") or "").upper(),
            str(trade.get("strategy") or ""),
            str(trade.get("entry_date") or "")[:10],
        )
        treatment = treatment_keys.get(key)
        if not treatment:
            out.append(dict(trade))
            status_counts["untouched"] += 1
            continue

        old_shares = int(trade.get("shares") or 0)
        old_pnl = _float(trade.get("pnl")) or 0.0
        touched += 1
        if old_shares <= 0:
            out.append(dict(trade))
            status_counts["no_baseline_shares"] += 1
            continue

        new_shares = int(math.floor(old_shares * risk_scalar))
        if risk_scalar > 0 and new_shares <= 0:
            new_shares = 1
        replacement = _resize_trade(trade, new_shares=new_shares, replay_meta=treatment)
        new_pnl = _float(replacement.get("pnl")) or 0.0
        if new_shares == old_shares:
            status_counts["unchanged"] += 1
        elif new_shares == 0:
            status_counts["removed"] += 1
            changed += 1
        else:
            status_counts["resized"] += 1
            changed += 1
        pnl_delta = new_pnl - old_pnl
        pnl_delta_by_ticker[key[0]] += pnl_delta
        out.append(replacement)
        details.append(
            {
                "ticker": key[0],
                "strategy": key[1],
                "entry_date": key[2],
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "baseline_shares": old_shares,
                "variant_shares": new_shares,
                "baseline_pnl": _round(old_pnl, 2),
                "variant_pnl": _round(new_pnl, 2),
                "pnl_delta": _round(pnl_delta, 2),
                **treatment,
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


def _replay_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    ohlcv = _load_ohlcv(REPO_ROOT / spec["snapshot"])
    result = _run_backtest(spec)
    trades = [dict(trade) for trade in result.get("trades") or []]
    spy_rows = ohlcv.get("SPY") or []
    meta_by_trade = _entered_candidate_meta(result)
    proxy_before = _daily_equity_metrics(trades, ohlcv, spy_rows, spec["start"], spec["end"])
    variant_results = {}
    for variant_name, variant in VARIANTS.items():
        resized_trades, meta = _variant_trades(trades, meta_by_trade, **variant)
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
                "win_rate": _round(proxy_after["win_rate"] - proxy_before["win_rate"], 4),
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
        "cluster_stats": _cluster_stats(trades, meta_by_trade),
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
        sharpe_improved = 0
        dd_improved = 0
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
            if (delta.get("sharpe_daily") or 0.0) > 0.1:
                sharpe_improved += 1
            if (delta.get("max_drawdown_pct") or 0.0) < -0.01:
                dd_improved += 1
            max_dd_worsening = max(max_dd_worsening, delta.get("max_drawdown_pct") or 0.0)
            by_window_delta[window_name] = delta
            status_counts.update(variant.get("status_counts") or {})
            for ticker, value in (variant.get("pnl_delta_by_ticker") or {}).items():
                pnl_delta_by_ticker[ticker] += float(value or 0.0)

        ev_delta_sum = after_ev_sum - baseline_ev_sum
        pnl_delta_sum = after_pnl_sum - baseline_pnl_sum
        ev_delta_pct = ev_delta_sum / abs(baseline_ev_sum) if baseline_ev_sum else None
        pnl_delta_pct = pnl_delta_sum / baseline_pnl_sum if baseline_pnl_sum else None
        max_single_share = _positive_share(dict(pnl_delta_by_ticker))
        gate4_passed = (
            improved >= 2
            and regressed == 0
            and changed_sum >= 3
            and (
                (ev_delta_pct is not None and ev_delta_pct > 0.10)
                or (pnl_delta_pct is not None and pnl_delta_pct > 0.05)
                or sharpe_improved >= 2
                or dd_improved >= 2
            )
            and max_dd_worsening <= 0.01
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
            "total_pnl_delta_pct": _round(pnl_delta_pct, 6),
            "windows_ev_improved": improved,
            "windows_ev_regressed": regressed,
            "windows_sharpe_improved_gt_0_1": sharpe_improved,
            "windows_dd_improved_gt_1pp": dd_improved,
            "max_drawdown_worsening_max": _round(max_dd_worsening, 4),
            "touched_treatment_trades": touched_sum,
            "changed_treatment_trades": changed_sum,
            "status_counts": dict(sorted(status_counts.items())),
            "max_single_ticker_positive_share": _round(max_single_share, 4),
            "pnl_delta_by_ticker": {
                ticker: _round(value, 2)
                for ticker, value in sorted(pnl_delta_by_ticker.items())
            },
            "by_window_delta": by_window_delta,
            "proxy_gate4_passed": gate4_passed,
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
        "alpha_hypothesis_category": "capital_allocation",
        "change_type": "same_day_entry_cluster_tail_risk_replay",
        "mechanism_family": "accepted_entry_cluster_rank_tail_sizing",
        "single_causal_variable": "same_day_entry_cluster_tail_risk_scalar",
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
                "Replay-only resize of already-entered A/B cluster-tail trades. "
                "Promotion requires shared entry/risk policy in production_parity.py "
                "and consumers in run.py/backtester.py."
            ),
        },
        "production_impact": payload["production_impact"],
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM/news replay is locked out of this deterministic entry-cluster replay.",
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "risk_of_change": payload["risk_of_change"],
        "why_not_other_attractive_points": payload["why_not_other_attractive_points"],
    }


def _ticket(best_variant: str, decision: str, aggregate: dict[str, Any]) -> dict[str, Any]:
    best = aggregate[best_variant]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Same-day entry cluster tail-risk replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta_sum": best["expected_value_score_delta_sum"],
        "total_pnl_delta_sum": best["total_pnl_delta_sum"],
        "next_action": (
            "Promote only after shared production/backtest cluster policy and parity tests."
            if best["proxy_gate4_passed"]
            else "Do not promote; avoid same-day cluster tail haircuts without new evidence."
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
        f"# {EXPERIMENT_ID} Same-Day Entry-Cluster Tail Risk",
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
        "| Variant | EV delta | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, metrics in aggregate.items():
        lines.append(
            "| {name} | {ev} | {pnl} | {pnl_pct} | {up}/{down} | {touched} | {changed} | {dd} | {share} | {gate} |".format(
                name=name,
                ev=metrics["expected_value_score_delta_sum"],
                pnl=metrics["total_pnl_delta_sum"],
                pnl_pct=metrics["total_pnl_delta_pct"],
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
            "## Window Deltas",
            "",
            "| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta | Trade delta |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, metrics in aggregate.items():
        for window, delta in metrics["by_window_delta"].items():
            lines.append(
                "| {name} | {window} | {ev} | {pnl} | {sharpe} | {dd} | {trades} |".format(
                    name=name,
                    window=window,
                    ev=delta["expected_value_score"],
                    pnl=delta["total_pnl"],
                    sharpe=delta["sharpe_daily"],
                    dd=delta["max_drawdown_pct"],
                    trades=delta["trade_count"],
                )
            )
    lines.extend(
        [
            "",
            "## Cluster Coverage",
            "",
            "| Window | Cluster size counts | Cluster PnL by size |",
            "|---|---|---|",
        ]
    )
    for name, window in payload["by_window"].items():
        stats = window["cluster_stats"]
        lines.append(
            "| {name} | `{counts}` | `{pnl}` |".format(
                name=name,
                counts=json.dumps(stats["entry_plan_cluster_size_counts"], sort_keys=True),
                pnl=json.dumps(stats["cluster_pnl_by_size"], sort_keys=True),
            )
        )
    if rejection_reason:
        lines.extend(["", "## Rejection Reason", "", rejection_reason])
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "No live or default-backtest strategy changed. Any future promotion would need a shared cluster-tail entry/risk policy consumed by `run.py` and `backtester.py`, plus parity tests.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    by_window = OrderedDict(
        (name, _replay_window(name, spec)) for name, spec in WINDOWS.items()
    )
    aggregate = _aggregate(by_window)
    best_variant = _choose_best(aggregate)
    best = aggregate[best_variant]
    decision = "accepted_replay_only" if best["proxy_gate4_passed"] else "rejected"
    rejection_reason = None
    if decision == "rejected":
        rejection_reason = (
            f"Best variant `{best_variant}` failed Gate 4: EV delta "
            f"{best['expected_value_score_delta_sum']} "
            f"({best['expected_value_score_delta_pct']}), PnL delta "
            f"{best['total_pnl_delta_sum']} ({best['total_pnl_delta_pct']}), "
            f"windows improved/regressed {best['windows_ev_improved']}/"
            f"{best['windows_ev_regressed']}, changed trades "
            f"{best['changed_treatment_trades']} of {best['touched_treatment_trades']} "
            f"touched, max DD worsening {best['max_drawdown_worsening_max']}, "
            f"single ticker positive share {best['max_single_ticker_positive_share']}."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "hypothesis": (
            "Same signal-date accepted A/B clusters may represent correlated "
            "late-cycle exposure; preserving the first planner-ranked trade "
            "while reducing later-ranked cluster tail risk may improve EV "
            "without adding a new ticker universe or LLM dependency."
        ),
        "official_baseline_metrics": _official_baseline_sum(by_window),
        "by_window": by_window,
        "aggregate": aggregate,
        "best_variant": best_variant,
        "decision": decision,
        "history_check": {
            "mechanism_insight_conflict": (
                "No conflict: this does not repeat LLM soft-ranking, C-sleeve "
                "reenablement, event-source pruning, runner exits, or platform "
                "risk add-ons. It follows exp-20260507-903's same-entry-date "
                "loss-family clue with a deterministic ex-ante allocation test."
            ),
            "nearby_rejected": {
                "exp-20260507-027": (
                    "Core platform cap-aware risk add-on failed; this tests "
                    "cluster tail risk reduction rather than ticker-family risk increase."
                ),
                "exp-20260507-033": (
                    "Far-from-earnings entry-state risk add-on failed; this "
                    "uses same-day planner cluster rank and does not depend on earnings distance."
                ),
                "exp-20260507-903": (
                    "Hold-quality taxonomy was observed-only and identified "
                    "same_entry_date_loss_cluster as small but costly; it did not "
                    "test an ex-ante risk scalar."
                ),
            },
            "why_this_is_not_repeat": (
                "The variable is entry-plan cluster rank within already-accepted "
                "A/B candidates, not early follow-through, ticker identity, LLM "
                "ranking, event metadata, or earnings timing."
            ),
        },
        "parameters": {
            "variants": VARIANTS,
            "core_strategies": sorted(CORE_STRATEGIES),
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "earnings strategy",
                "LLM/news replay",
                "exits",
                "add-ons",
                "partial reduces",
            ],
            "cluster_key": "entry_candidate_event.date",
            "candidate_rank_source": "shared entry planner candidate_rank",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "next_retry_requires": [
            "Only retest if new out-of-sample clusters show repeated tail losses.",
            "Any promotion must put the cluster policy in shared production_parity.py.",
            "Do not combine this with ticker, earnings, or event filters in the same iteration.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        ],
        "risk_of_change": (
            "Could under-size later-ranked same-day winners in strong breadth "
            "regimes where multiple accepted breakouts are legitimate alpha."
        ),
        "why_not_other_attractive_points": {
            "llm_soft_ranking": "Replay/outcome join coverage remains too sparse for a trustworthy alpha test.",
            "event_bundle_promotion": "exp-20260507-026 is already default-off observed; direct promotion still needs forward replacement value.",
            "universe_expansion": "Recent event-sensitive liquidity universe work did not beat core windows; no broad noisy ticker expansion here.",
            "earnings_c_sleeve": "exp-20260507-011 regressed all windows and remains data-quality constrained.",
        },
    }

    log_record = _log_record(payload, aggregate, best_variant, decision, rejection_reason)
    payload["log_record"] = log_record
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, _ticket(best_variant, decision, aggregate))
    _write_text(
        ARTIFACT_MD,
        _artifact_markdown(payload, aggregate, best_variant, decision, rejection_reason),
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "best_variant": best_variant,
                "best": best,
                "outputs": {
                    "data": str(OUT_JSON),
                    "log": str(LOG_JSON),
                    "ticket": str(TICKET_JSON),
                    "artifact": str(ARTIFACT_MD),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
