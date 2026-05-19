"""exp-20260506-024: meta-allocation state map.

Alpha search / discovery. This does not change entries, exits, sizing, ranking,
LLM, news, or universe membership. It reruns the canonical three windows and
maps accepted-stack trade and skip outcomes by replayable market-state buckets
so the next alpha rule is based on a state/sleeve opportunity map rather than a
nearby rejected threshold.
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
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260506-024"
STEM = "meta_allocation_state_map"

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


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _zero_delta(metrics: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, (int, float)):
            out[key] = 0 if isinstance(value, int) else 0.0
    return out


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected snapshot shape: {snapshot_path}")
    return {
        str(ticker).upper(): sorted(rows, key=lambda row: row.get("Date", ""))
        for ticker, rows in ohlcv.items()
        if isinstance(rows, list)
    }


def _rows_until(rows: list[dict[str, Any]], date_str: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("Date") or "") <= date_str]


def _close(row: dict[str, Any]) -> float | None:
    try:
        value = float(row.get("Close"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _ret(rows: list[dict[str, Any]], date_str: str, lookback: int) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) <= lookback:
        return None
    now = _close(hist[-1])
    then = _close(hist[-lookback - 1])
    if not now or not then:
        return None
    return now / then - 1.0


def _pct_from_sma(rows: list[dict[str, Any]], date_str: str, lookback: int) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback:
        return None
    now = _close(hist[-1])
    closes = [_close(row) for row in hist[-lookback:]]
    closes = [value for value in closes if value]
    if not now or len(closes) < lookback:
        return None
    avg = sum(closes) / len(closes)
    return now / avg - 1.0 if avg else None


def _breadth(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
    lookback: int,
) -> float | None:
    seen = 0
    above = 0
    for ticker in universe:
        rows = ohlcv.get(ticker.upper())
        if not rows:
            continue
        pct = _pct_from_sma(rows, date_str, lookback)
        if pct is None:
            continue
        seen += 1
        above += int(pct > 0)
    return above / seen if seen else None


def _sector_dispersion(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
) -> float | None:
    by_sector: dict[str, list[float]] = defaultdict(list)
    for ticker in universe:
        rows = ohlcv.get(ticker.upper())
        if not rows:
            continue
        value = _ret(rows, date_str, 20)
        if value is None:
            continue
        by_sector[risk_engine.SECTOR_MAP.get(ticker.upper(), "Unknown")].append(value)
    sector_returns = [
        sum(values) / len(values)
        for values in by_sector.values()
        if values
    ]
    if len(sector_returns) < 2:
        return None
    return statistics.pstdev(sector_returns)


def _state_for_date(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
) -> dict[str, Any]:
    spy_rows = ohlcv.get("SPY", [])
    qqq_rows = ohlcv.get("QQQ", [])
    iwm_rows = ohlcv.get("IWM", [])
    spy_ret20 = _ret(spy_rows, date_str, 20)
    qqq_ret20 = _ret(qqq_rows, date_str, 20)
    iwm_ret20 = _ret(iwm_rows, date_str, 20)
    spy_pct200 = _pct_from_sma(spy_rows, date_str, 200)
    qqq_pct200 = _pct_from_sma(qqq_rows, date_str, 200)
    breadth50 = _breadth(ohlcv, universe, date_str, 50)
    dispersion20 = _sector_dispersion(ohlcv, universe, date_str)

    min_index_pct200 = None
    pct_values = [value for value in (spy_pct200, qqq_pct200) if value is not None]
    if pct_values:
        min_index_pct200 = min(pct_values)

    qqq_minus_iwm = None
    if qqq_ret20 is not None and iwm_ret20 is not None:
        qqq_minus_iwm = qqq_ret20 - iwm_ret20

    iwm_minus_spy = None
    if iwm_ret20 is not None and spy_ret20 is not None:
        iwm_minus_spy = iwm_ret20 - spy_ret20

    if min_index_pct200 is not None and min_index_pct200 < 0:
        state_bucket = "weak_index"
    elif qqq_minus_iwm is not None and qqq_minus_iwm > 0.04:
        state_bucket = "narrow_cap_weight_leadership"
    elif iwm_minus_spy is not None and iwm_minus_spy > 0.02:
        state_bucket = "broad_rotation"
    else:
        state_bucket = "balanced_risk_on"

    breadth_bucket = "unknown"
    if breadth50 is not None:
        if breadth50 >= 0.65:
            breadth_bucket = "broad_breadth"
        elif breadth50 <= 0.45:
            breadth_bucket = "thin_breadth"
        else:
            breadth_bucket = "mixed_breadth"

    dispersion_bucket = "unknown"
    if dispersion20 is not None:
        if dispersion20 >= 0.08:
            dispersion_bucket = "high_sector_dispersion"
        elif dispersion20 <= 0.035:
            dispersion_bucket = "low_sector_dispersion"
        else:
            dispersion_bucket = "mid_sector_dispersion"

    return {
        "date": date_str,
        "state_bucket": state_bucket,
        "breadth_bucket": breadth_bucket,
        "dispersion_bucket": dispersion_bucket,
        "spy_ret20": _round(spy_ret20, 6),
        "qqq_ret20": _round(qqq_ret20, 6),
        "iwm_ret20": _round(iwm_ret20, 6),
        "qqq_minus_iwm_ret20": _round(qqq_minus_iwm, 6),
        "iwm_minus_spy_ret20": _round(iwm_minus_spy, 6),
        "min_index_pct_from_200sma": _round(min_index_pct200, 6),
        "universe_breadth_above_50sma": _round(breadth50, 6),
        "sector_ret20_dispersion": _round(dispersion20, 6),
    }


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [float(row.get("pnl") or 0.0) for row in rows]
    trade_count = len(rows)
    wins = sum(1 for value in pnl_values if value > 0)
    losses = trade_count - wins
    total_pnl = sum(pnl_values)
    return {
        "trade_count": trade_count,
        "wins": wins,
        "losses": losses,
        "win_rate": _round(wins / trade_count if trade_count else 0.0, 4),
        "total_pnl": _round(total_pnl, 2),
        "avg_pnl": _round(total_pnl / trade_count if trade_count else 0.0, 2),
    }


def _group_trades(
    trades: list[dict[str, Any]],
    state_cache: dict[str, dict[str, Any]],
    groupers: list[str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        date_str = str(trade.get("entry_date") or "")
        state = state_cache.get(date_str, {})
        values: list[str] = []
        for key in groupers:
            if key.startswith("state."):
                values.append(str(state.get(key.split(".", 1)[1], "unknown")))
            elif key == "sizing_family":
                multipliers = trade.get("sizing_multipliers") or {}
                if "spy_relative_leader_risk_on_multiplier_applied" in multipliers:
                    values.append("spy_relative_leader")
                elif multipliers:
                    values.append("+".join(sorted(multipliers)))
                else:
                    values.append("unmodified")
            else:
                values.append(str(trade.get(key) or "unknown"))
        grouped[tuple(values)].append(trade)

    summaries = []
    for key_tuple, rows in grouped.items():
        payload = {groupers[idx]: key_tuple[idx] for idx in range(len(groupers))}
        payload.update(_summarize_rows(rows))
        summaries.append(payload)
    return sorted(
        summaries,
        key=lambda item: (item["total_pnl"], item["trade_count"]),
        reverse=True,
    )


def _skip_map(
    skips: list[dict[str, Any]],
    state_cache: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: Counter[tuple[str, str, str]] = Counter()
    for skip in skips:
        date_str = str(skip.get("date") or "")
        state = state_cache.get(date_str, {})
        key = (
            str(state.get("state_bucket", "unknown")),
            str(skip.get("decision") or "unknown"),
            str(skip.get("strategy") or "unknown"),
        )
        grouped[key] += 1
    return [
        {
            "state_bucket": key[0],
            "decision": key[1],
            "strategy": key[2],
            "count": count,
        }
        for key, count in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    ]


def _run_window(window: dict[str, str]) -> dict[str, Any]:
    result = BacktestEngine(
        sorted(get_universe()),
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        include_pilot_sleeve=False,
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _window_analysis(label: str, window: dict[str, str]) -> dict[str, Any]:
    result = _run_window(window)
    snapshot = REPO_ROOT / window["snapshot"]
    ohlcv = _load_ohlcv(snapshot)
    universe = sorted(get_universe())

    dates = {
        str(trade.get("entry_date") or "")
        for trade in result.get("trades") or []
        if trade.get("entry_date")
    }
    skips = (result.get("entry_execution_attribution") or {}).get("sample_skips") or []
    dates.update(str(skip.get("date") or "") for skip in skips if skip.get("date"))
    state_cache = {
        date_str: _state_for_date(ohlcv, universe, date_str)
        for date_str in sorted(dates)
    }

    trades = result.get("trades") or []
    metrics = _metrics(result)
    return {
        "window": window,
        "metrics": metrics,
        "after_metrics": metrics,
        "delta": _zero_delta(metrics),
        "state_dates": state_cache,
        "trade_maps": {
            "state_strategy": _group_trades(trades, state_cache, ["state.state_bucket", "strategy"]),
            "state_sector": _group_trades(trades, state_cache, ["state.state_bucket", "sector"]),
            "state_sizing_family": _group_trades(
                trades,
                state_cache,
                ["state.state_bucket", "sizing_family"],
            ),
            "breadth_strategy": _group_trades(
                trades,
                state_cache,
                ["state.breadth_bucket", "strategy"],
            ),
            "dispersion_strategy": _group_trades(
                trades,
                state_cache,
                ["state.dispersion_bucket", "strategy"],
            ),
        },
        "skip_map": _skip_map(skips, state_cache),
        "entry_execution_reason_counts": (
            (result.get("entry_execution_attribution") or {}).get("reason_counts") or {}
        ),
        "capital_efficiency": result.get("capital_efficiency") or {},
        "by_strategy": result.get("by_strategy") or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution") or {},
    }


def _top_negative_cohorts(by_window: OrderedDict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for label, row in by_window.items():
        for map_name, cohorts in row["trade_maps"].items():
            for cohort in cohorts:
                if cohort["trade_count"] >= 2 and cohort["total_pnl"] < 0:
                    candidates.append({"window": label, "map": map_name, **cohort})
    return sorted(candidates, key=lambda item: (item["total_pnl"], -item["trade_count"]))[:10]


def _top_positive_cohorts(by_window: OrderedDict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for label, row in by_window.items():
        for map_name, cohorts in row["trade_maps"].items():
            for cohort in cohorts:
                if cohort["trade_count"] >= 2 and cohort["total_pnl"] > 0:
                    candidates.append({"window": label, "map": map_name, **cohort})
    return sorted(candidates, key=lambda item: (item["total_pnl"], item["trade_count"]), reverse=True)[:10]


def _aggregate_metrics(by_window: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_sum = sum(float(row["metrics"].get("expected_value_score") or 0.0) for row in by_window.values())
    pnl_sum = sum(float(row["metrics"].get("total_pnl") or 0.0) for row in by_window.values())
    trades = sum(int(row["metrics"].get("trade_count") or 0) for row in by_window.values())
    return {
        "expected_value_score_sum": _round(ev_sum, 6),
        "total_pnl_sum": _round(pnl_sum, 2),
        "trade_count_sum": trades,
        "expected_value_score_delta_sum": 0.0,
        "total_pnl_delta_sum": 0.0,
        "windows_ev_improved": 0,
        "windows_ev_regressed": 0,
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Meta-Allocation State Map",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Three-Window Metrics",
        "",
        "| Window | EV | PnL | SharpeD | DD | Win rate | Trades | Survival |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["by_window"].items():
        metrics = row["metrics"]
        lines.append(
            "| {label} | {ev} | {pnl} | {sharpe} | {dd} | {wr} | {trades} | {survival} |".format(
                label=label,
                ev=metrics["expected_value_score"],
                pnl=metrics["total_pnl"],
                sharpe=metrics["sharpe_daily"],
                dd=metrics["max_drawdown_pct"],
                wr=metrics["win_rate"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Positive Cohorts",
            "",
            "| Window | Map | Cohort | Trades | Win rate | PnL |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for item in payload["cohort_findings"]["top_positive_cohorts"][:8]:
        cohort = ", ".join(
            f"{key}={value}"
            for key, value in item.items()
            if key not in {"window", "map", "trade_count", "wins", "losses", "win_rate", "total_pnl", "avg_pnl"}
        )
        lines.append(
            f"| {item['window']} | {item['map']} | {cohort} | {item['trade_count']} | "
            f"{item['win_rate']} | {item['total_pnl']} |"
        )
    lines.extend(
        [
            "",
            "## Negative Cohorts",
            "",
            "| Window | Map | Cohort | Trades | Win rate | PnL |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for item in payload["cohort_findings"]["top_negative_cohorts"][:8]:
        cohort = ", ".join(
            f"{key}={value}"
            for key, value in item.items()
            if key not in {"window", "map", "trade_count", "wins", "losses", "win_rate", "total_pnl", "avg_pnl"}
        )
        lines.append(
            f"| {item['window']} | {item['map']} | {cohort} | {item['trade_count']} | "
            f"{item['win_rate']} | {item['total_pnl']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Next Alpha Candidate",
            "",
            payload["next_alpha_candidate"],
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        by_window[label] = _window_analysis(label, window)

    aggregate = _aggregate_metrics(by_window)
    positives = _top_positive_cohorts(by_window)
    negatives = _top_negative_cohorts(by_window)
    generated_at = datetime.now(timezone.utc).isoformat()

    interpretation = (
        "This is an alpha-search map, not a promoted rule. The strongest recurring "
        "positive surface remains state-aware capital allocation, but the map does "
        "not justify another simple SPY-relative leader, broad ETF, or raw collision "
        "ranking retest. Any executable follow-up should target a cohort that appears "
        "in at least two windows and is implemented in shared run/backtester policy."
    )
    next_alpha_candidate = (
        "Use this map to test a single shared-policy allocation rule only if the same "
        "state/sleeve cohort has enough touched trades in at least two windows; otherwise "
        "continue with event-overlay forward evidence rather than local threshold mining."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": "observed_only",
        "decision": "observed_only",
        "lane": "alpha_search",
        "change_type": "meta_allocation_state_map",
        "mechanism_family": "market_structure_sleeve_allocation",
        "hypothesis": (
            "A replayable market-structure map across sleeve, sector, breadth, and "
            "dispersion states can identify the next allocation alpha surface without "
            "repeating recently rejected local thresholds."
        ),
        "alpha_hypothesis": {
            "category": "allocation",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking and event-overlay promotion are sample-limited, and "
                "recent candidate-pool, SPY-leader, and collision-ranking retries were "
                "rejected. The playbook asks for a meta-allocation state map before "
                "another classifier or production rule."
            ),
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260429-026": (
                    "Earlier sleeve/sector audit found accepted sleeves were already "
                    "strong and tiny negative pockets were overfit-prone. This run adds "
                    "replayable market-structure state buckets and current-stack metrics."
                ),
                "exp-20260506-019": (
                    "Raw OHLCV collision ranking was rejected. This run does not reorder "
                    "or trade on the state variables."
                ),
                "exp-20260506-020": (
                    "Simple SPY/QQQ distance gating was rejected. This run records index, "
                    "breadth, and sector-dispersion states as attribution only."
                ),
            },
            "mechanism_insight_check": (
                "No production rule is promoted, so this avoids the recent no-go zones "
                "around SPY leader retuning, broad universe expansion, and simple index "
                "distance gates."
            ),
        },
        "parameters": {
            "single_causal_variable": "analysis-only market-state cohort attribution",
            "state_fields": [
                "QQQ 20d return minus IWM 20d return",
                "IWM 20d return minus SPY 20d return",
                "min(SPY, QQQ) pct from 200SMA",
                "current-universe breadth above 50SMA",
                "sector equal-weight 20d return dispersion",
            ],
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "position caps",
                "portfolio heat",
                "add-ons",
                "exits",
                "LLM/news replay",
                "pilot sleeve",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {label: row["metrics"] for label, row in by_window.items()},
        "after_metrics": {label: row["after_metrics"] for label, row in by_window.items()},
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in by_window.items()},
            "aggregate": aggregate,
        },
        "by_window": by_window,
        "cohort_findings": {
            "top_positive_cohorts": positives,
            "top_negative_cohorts": negatives,
        },
        "gate4": {
            "passed": False,
            "basis": (
                "No executable policy changed. Gate 4 is intentionally not claimed; "
                "the before/after metrics are identical across all three canonical windows."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "LLM soft-ranking remains data-limited, so this run uses deterministic "
                "OHLCV state attribution instead of changing LLM responsibilities."
            ),
        },
        "interpretation": interpretation,
        "next_alpha_candidate": next_alpha_candidate,
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260506_024_meta_allocation_state_map.py",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "Meta-allocation state map",
        "summary": (
            "Three-window state/sleeve map recorded; no production rule promoted."
        ),
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    TICKET_JSON.write_text(
        json.dumps(ticket, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"{EXPERIMENT_ID} observed_only")
    print(json.dumps(ticket, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
