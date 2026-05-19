"""exp-20260510-007 low-deployment dynamic ETF overlay replay.

Alpha search, replay-only. Prior idle-benchmark work showed that broad QQQ idle
cash exposure was too blunt, while a zero-active-core-position QQQ overlay was
directionally positive but small-sample. This experiment tests one richer, still
deterministic capital-allocation variable:

    When the core A/B book has at most one active position, add a fixed-notional
    liquid ETF overlay selected from a tiny cross-asset ETF set by prior-close
    20-day momentum, with the same positive 200-day trend and positive 20-day
    momentum gate.

No production orders, default backtest behavior, signal generation, candidate
ranking, sizing, exits, add-ons, LLM, news, or universe membership are changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from operator_input_paths import open_positions_path  # noqa: E402


EXPERIMENT_ID = "exp-20260510-007"
STEM = "low_deployment_dynamic_etf_overlay"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
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
MAX_ACTIVE_CORE_POSITIONS = 1
OVERLAY_NOTIONAL_FRACTION = 1.0
STATE_SMA_DAYS = 200
STATE_MOMENTUM_DAYS = 20
OVERLAY_CANDIDATES = ("QQQ", "SPY", "IWM", "GLD", "SLV")

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
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


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
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


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    kept = [line for line in lines if compact not in line and pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _load_snapshot_rows(snapshot_path: str) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads((REPO_ROOT / snapshot_path).read_text(encoding="utf-8"))
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker in OVERLAY_CANDIDATES:
        rows = []
        for row in (payload.get("ohlcv") or {}).get(ticker, []):
            rows.append(
                {
                    "date": row["Date"],
                    "open": float(row["Open"]),
                    "close": float(row["Close"]),
                }
            )
        if rows:
            out[ticker] = sorted(rows, key=lambda row: row["date"])
    return out


def _rows_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row["date"]): idx for idx, row in enumerate(rows)}


def _core_active_count_by_date(result: dict[str, Any]) -> dict[str, int]:
    curve_dates = [str(day) for day, _ in result.get("equity_curve") or []]
    counts: dict[str, int] = {day: 0 for day in curve_dates}
    for trade in result.get("trades") or []:
        if trade.get("strategy") not in {"trend_long", "breakout_long"}:
            continue
        entry = str(trade.get("entry_date") or "")
        exit_ = str(trade.get("exit_date") or "")
        if not entry or not exit_:
            continue
        for day in curve_dates:
            if entry <= day <= exit_:
                counts[day] = counts.get(day, 0) + 1
    return counts


def _candidate_state(
    rows: list[dict[str, Any]],
    idx: int,
) -> dict[str, Any] | None:
    if idx < max(STATE_SMA_DAYS, STATE_MOMENTUM_DAYS) + 1:
        return None
    prior_idx = idx - 1
    prior = rows[prior_idx]
    sma_window = rows[prior_idx - STATE_SMA_DAYS + 1 : prior_idx + 1]
    sma = sum(item["close"] for item in sma_window) / len(sma_window)
    momentum = prior["close"] / rows[prior_idx - STATE_MOMENTUM_DAYS]["close"] - 1.0
    if prior["close"] <= sma or momentum <= 0.0:
        return None
    return {
        "prior_close": prior["close"],
        "prior_sma200": sma,
        "prior_momentum20": momentum,
    }


def _select_overlay_ticker(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    index_by_ticker_date: dict[str, dict[str, int]],
    day: str,
) -> dict[str, Any] | None:
    candidates = []
    for ticker, rows in rows_by_ticker.items():
        idx = index_by_ticker_date.get(ticker, {}).get(day)
        if idx is None:
            continue
        state = _candidate_state(rows, idx)
        if state is None:
            continue
        candidates.append(
            {
                "ticker": ticker,
                "idx": idx,
                "momentum": float(state["prior_momentum20"]),
                "state": state,
            }
        )
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["momentum"], row["ticker"]))


def _overlay_path(
    result: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    base_curve = result.get("equity_curve") or []
    core_counts = _core_active_count_by_date(result)
    index_by_ticker_date = {
        ticker: _rows_by_date(rows) for ticker, rows in rows_by_ticker.items()
    }
    overlay_pnl_by_date: dict[str, float] = {}
    overlay_days: list[dict[str, Any]] = []
    candidate_counts: Counter[str] = Counter()
    low_deployment_day_count = 0

    for day, _ in base_curve:
        day = str(day)
        active_count = core_counts.get(day, 0)
        if active_count > MAX_ACTIVE_CORE_POSITIONS:
            continue
        low_deployment_day_count += 1
        selection = _select_overlay_ticker(rows_by_ticker, index_by_ticker_date, day)
        if selection is None:
            continue
        ticker = selection["ticker"]
        rows = rows_by_ticker[ticker]
        row = rows[selection["idx"]]
        notional = INITIAL_CAPITAL * OVERLAY_NOTIONAL_FRACTION
        pnl = notional * (row["close"] / row["open"] - 1.0)
        overlay_pnl_by_date[day] = pnl
        candidate_counts[ticker] += 1
        state = selection["state"]
        overlay_days.append(
            {
                "date": day,
                "ticker": ticker,
                "active_core_positions": active_count,
                "prior_close": _round(state["prior_close"], 4),
                "prior_sma200": _round(state["prior_sma200"], 4),
                "prior_momentum20": _round(state["prior_momentum20"], 6),
                "open": _round(row["open"], 4),
                "close": _round(row["close"], 4),
                "notional": _round(notional, 2),
                "pnl": _round(pnl, 2),
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in base_curve:
        cumulative_overlay += overlay_pnl_by_date.get(str(day), 0.0)
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))

    return {
        "combined_equity_curve": combined_curve,
        "overlay_total_pnl": round(sum(overlay_pnl_by_date.values()), 2),
        "overlay_day_count": len(overlay_days),
        "low_deployment_day_count": low_deployment_day_count,
        "ticker_day_counts": dict(candidate_counts),
        "overlay_days": overlay_days,
    }


def _curve_risk(curve: list[tuple[str, float]]) -> dict[str, Any]:
    values = [float(equity) for _, equity in curve]
    daily_returns = [
        (values[idx] / values[idx - 1]) - 1.0
        for idx in range(1, len(values))
        if values[idx - 1] != 0
    ]
    sharpe_daily = None
    if len(daily_returns) >= 2:
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((item - mean_return) ** 2 for item in daily_returns) / (
            len(daily_returns) - 1
        )
        std = math.sqrt(variance)
        if std > 0:
            sharpe_daily = round((mean_return / std) * math.sqrt(252), 2)

    peak = 0.0
    max_drawdown = 0.0
    for equity in values:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)

    return {
        "sharpe_daily": sharpe_daily,
        "max_drawdown_pct": round(max_drawdown, 4),
    }


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "strategy_total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"), 4
        ),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _metrics_with_overlay(
    result: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(result)
    total_pnl = float(result.get("total_pnl") or 0.0) + float(
        overlay["overlay_total_pnl"] or 0.0
    )
    risk = _curve_risk(overlay["combined_equity_curve"])
    benchmarks = dict(result.get("benchmarks") or {})
    strategy_return = total_pnl / INITIAL_CAPITAL
    benchmarks["strategy_total_return_pct"] = round(strategy_return, 4)
    if benchmarks.get("spy_buy_hold_return_pct") is not None:
        benchmarks["strategy_vs_spy_pct"] = round(
            strategy_return - benchmarks["spy_buy_hold_return_pct"], 4
        )
    if benchmarks.get("qqq_buy_hold_return_pct") is not None:
        benchmarks["strategy_vs_qqq_pct"] = round(
            strategy_return - benchmarks["qqq_buy_hold_return_pct"], 4
        )
    updated["benchmarks"] = benchmarks
    updated["total_pnl"] = round(total_pnl, 2)
    updated["sharpe_daily"] = risk["sharpe_daily"]
    updated["max_drawdown_pct"] = risk["max_drawdown_pct"]
    updated["expected_value_score"] = compute_expected_value_score(updated)
    return _metrics(updated)


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key in [
        "expected_value_score",
        "total_pnl",
        "strategy_total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ]:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            digits = 2 if key == "total_pnl" else 6
            out[key] = round(after_value - before_value, digits)
    return out


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_delta = sum(row["delta"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_delta = sum(row["delta"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / pnl_before, 6) if pnl_before else None,
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
        "min_overlay_day_count": min(row["overlay_day_count"] for row in rows.values()),
        "overlay_day_count_sum": sum(row["overlay_day_count"] for row in rows.values()),
        "low_deployment_day_count_sum": sum(
            row["low_deployment_day_count"] for row in rows.values()
        ),
    }


def _single_ticker_positive_share(windows: dict[str, dict[str, Any]]) -> float | None:
    by_ticker: Counter[str] = Counter()
    total_positive = 0.0
    for row in windows.values():
        for day in row["overlay_days"]:
            pnl = float(day.get("pnl") or 0.0)
            if pnl <= 0:
                continue
            total_positive += pnl
            by_ticker[str(day.get("ticker") or "").upper()] += pnl
    if total_positive <= 0 or not by_ticker:
        return None
    return round(max(by_ticker.values()) / total_positive, 4)


def _field_audit() -> dict[str, Any]:
    path = open_positions_path()
    if not path.exists():
        return {
            "path": _repo_rel(path),
            "exists": False,
            "all_positions_have_entry_date": False,
            "all_positions_have_target_price": False,
            "cash_usd_populated": False,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for key in ("positions", "observations"):
        rows.extend(payload.get(key) or [])
    return {
        "path": _repo_rel(path),
        "exists": True,
        "position_rows_checked": len(rows),
        "missing_entry_date": sorted(
            str(row.get("ticker") or "?") for row in rows if not row.get("entry_date")
        ),
        "missing_target_price": sorted(
            str(row.get("ticker") or "?") for row in rows if not row.get("target_price")
        ),
        "all_positions_have_entry_date": all(bool(row.get("entry_date")) for row in rows),
        "all_positions_have_target_price": all(bool(row.get("target_price")) for row in rows),
        "cash_usd_populated": payload.get("cash_usd") is not None,
        "cash_usd_note": (
            "cash_usd is not populated, so this replay measures fixed-notional "
            "overlay value rather than production cash sizing."
        ),
    }


def _build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    windows: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe=get_universe(),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        overlay = _overlay_path(result, _load_snapshot_rows(window["snapshot"]))
        before = _metrics(result)
        after = _metrics_with_overlay(result, overlay)
        windows[label] = {
            "before": before,
            "after": after,
            "delta": _delta(after, before),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
            "low_deployment_day_count": overlay["low_deployment_day_count"],
            "ticker_day_counts": overlay["ticker_day_counts"],
            "overlay_days": overlay["overlay_days"],
            "overlay_days_sample": overlay["overlay_days"][:20],
        }

    aggregate = _aggregate(windows)
    concentration = _single_ticker_positive_share(windows)
    concentration_ok = concentration is None or concentration <= 0.75
    material = bool(
        (aggregate["expected_value_score_delta_pct"] or 0.0) >= 0.10
        or (aggregate["total_pnl_delta_pct"] or 0.0) >= 0.05
    )
    directionally_positive = bool(
        aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["max_drawdown_delta_max"] <= 0.01
        and aggregate["min_overlay_day_count"] >= 4
        and concentration_ok
    )
    if directionally_positive and material:
        decision = "promising_replay_only_low_deployment_dynamic_etf_overlay"
        rejection_reason = None
    elif directionally_positive:
        decision = "directionally_positive_replay_only"
        rejection_reason = None
    else:
        decision = "rejected"
        rejection_reason = (
            "Rejected: the low-deployment dynamic ETF overlay failed the "
            "three-window EV/PnL/drawdown/concentration gate."
        )

    if decision == "promising_replay_only_low_deployment_dynamic_etf_overlay":
        decision_rationale = (
            "Promising replay-only: the low-deployment dynamic ETF overlay cleared "
            "the three-window EV/PnL materiality gate without breaching drawdown "
            "or concentration guards. It remains non-production because actual "
            "cash/risk budget semantics and shared run/backtester adapters are "
            "not implemented."
        )
    elif decision == "directionally_positive_replay_only":
        decision_rationale = (
            "Directionally positive replay-only: the overlay improved EV/PnL in "
            "all three canonical windows, but the aggregate uplift did not clear "
            "strong materiality. Keep it as a forward paper hypothesis only."
        )
    else:
        decision_rationale = rejection_reason

    before_metrics = {label: row["before"] for label, row in windows.items()}
    after_metrics = {label: row["after"] for label, row in windows.items()}
    deltas = {label: row["delta"] for label, row in windows.items()}

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "low_deployment_dynamic_etf_overlay_allocation",
        "hypothesis": (
            "When the accepted A/B core is materially under-deployed, a small "
            "liquid ETF selector using only prior-close momentum/trend state may "
            "capture replacement value without displacing scarce stock slots."
        ),
        "change_type": "replay_only_low_deployment_dynamic_etf_overlay",
        "single_causal_variable": (
            "Add a fixed-notional dynamic liquid ETF overlay only when active core "
            "A/B positions are <= 1; all core entries, exits, ranking, sizing, "
            "add-ons, LLM/news, and universe membership stay locked."
        ),
        "alpha_hypothesis": {
            "category": "capital_allocation/candidate_pool_extension",
            "playbook_alignment": (
                "Avoids currently blocked LLM soft-ranking, SEC filing shock, "
                "state/event parameter retunes, and add-on cap/heat searches; "
                "tests a production-definable candidate-pool allocation path "
                "using liquid existing snapshot instruments."
            ),
        },
        "historical_experiment_check": {
            "exp-20260425-026": (
                "Broad idle-cash QQQ overlay damaged mid_weak; this run requires "
                "severe low deployment and chooses from a tiny liquid ETF set by "
                "prior-close state."
            ),
            "exp-20260510-006": (
                "Zero-position fixed QQQ overlay was directionally positive but "
                "small-sample. This run changes the overlay selector/deployment "
                "policy rather than retuning QQQ notional."
            ),
            "ETF universe expansion guardrail": (
                "This does not make ETFs core tradeable universe members, does not "
                "alter signal generation, and does not consume A/B slots."
            ),
        },
        "parameters": {
            "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
            "overlay_candidates": list(OVERLAY_CANDIDATES),
            "overlay_selector": (
                "highest prior-close 20d momentum among candidates with prior "
                "close > 200d SMA and prior 20d momentum > 0"
            ),
            "overlay_notional_fraction": OVERLAY_NOTIONAL_FRACTION,
            "state_sma_days": STATE_SMA_DAYS,
            "state_momentum_days": STATE_MOMENTUM_DAYS,
            "locked_variables": [
                "signal generation",
                "candidate ranking",
                "entry gates",
                "position sizing",
                "exits",
                "follow-through add-ons",
                "LLM/news replay",
                "universe membership",
                "core A/B trade path",
            ],
        },
        "gate2_field_audit": _field_audit(),
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": deltas,
            "aggregate": aggregate,
        },
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "gate3": {
            "survival_rates": {
                label: before_metrics[label]["survival_rate"]
                for label in WINDOWS
            },
            "new_filter_added": False,
            "note": "No signal filter or candidate filter was added; survival is unchanged.",
        },
        "gate4": {
            "passed_directionally": directionally_positive,
            "strong_materiality_passed": material,
            "concentration_ok": concentration_ok,
            "single_ticker_positive_share": concentration,
            "basis": "Three canonical backtesting.md windows using the same snapshots.",
            "rule": (
                "Require 3/3 EV improvement, no PnL regression, positive aggregate "
                "EV/PnL, max drawdown worsening <= 1pp, min 4 overlay days per "
                "window, and single ETF positive contribution share <= 75%."
            ),
        },
        "overlay_summary": {
            label: {
                "overlay_day_count": row["overlay_day_count"],
                "low_deployment_day_count": row["low_deployment_day_count"],
                "ticker_day_counts": row["ticker_day_counts"],
                "overlay_total_pnl": row["overlay_total_pnl"],
                "overlay_days_sample": row["overlay_days_sample"],
            }
            for label, row in windows.items()
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this deterministic "
                "allocation test does not depend on LLM replay."
            ),
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
            "promotion_requirement_if_positive": (
                "A live/default version must define shared run.py/backtester.py "
                "cash/risk-budget semantics, explicit ETF overlay order handling, "
                "and parity tests before any order path changes."
            ),
        },
        "risk_of_change": (
            "The replay uses fixed notional and same-day ETF open-to-close returns, "
            "not actual available cash or broker execution. Treat any positive "
            "result as a forward paper hypothesis until cash/risk semantics are "
            "implemented in shared production/backtest policy."
        ),
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_action": (
            "If positive, track low-deployment ETF overlay opportunities forward "
            "with actual same-day cash/risk context before building a trade-enabled "
            "adapter. If rejected, do not retry idle ETF overlays without new "
            "deployment or forward replacement-value evidence."
        ),
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(Path(__file__)),
        ],
    }

    return {**log_record, "windows": windows}


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Low-deployment Dynamic ETF Overlay",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-window Deltas",
        "",
        "| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days | Ticker days |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, row in payload["windows"].items():
        delta = row["delta"]
        ticker_counts = ", ".join(
            f"{ticker}:{count}" for ticker, count in sorted(row["ticker_day_counts"].items())
        )
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {ret:+.4f} | {sharpe:+.2f} | {dd:+.4f} | {days} | {tickers} |".format(
                label=label,
                ev=delta["expected_value_score"],
                pnl=delta["total_pnl"],
                ret=delta["strategy_total_return_pct"],
                sharpe=delta["sharpe_daily"],
                dd=delta["max_drawdown_pct"],
                days=row["overlay_day_count"],
                tickers=ticker_counts or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- EV windows improved/regressed: `{aggregate['windows_ev_improved']}` / `{aggregate['windows_ev_regressed']}`",
            f"- Overlay days: `{aggregate['overlay_day_count_sum']}` selected from `{aggregate['low_deployment_day_count_sum']}` low-deployment days",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only. No live/default orders, core A/B signal generation, ranking, sizing, exits, add-ons, LLM/news behavior, or production adapters changed. Any positive follow-up needs shared run.py/backtester.py cash/risk-budget semantics and parity tests.",
            "",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    log_record = {key: value for key, value in payload.items() if key != "windows"}
    _write_json(LOG_JSON, log_record)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Low-deployment dynamic ETF overlay",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_artifact(payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, log_record)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "aggregate": payload["delta_metrics"]["aggregate"],
                    "gate4": payload["gate4"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
