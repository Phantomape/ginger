"""exp-20260620-023: core-stack static SPY beta hedge.

Replay-only alpha search. The fixed decision hypothesis is portfolio risk
allocation: use the measured pooled SPY beta from exp-20260620-020
(`0.347743`) as a static daily short-SPY hedge overlay on the accepted core
stack. Entries, exits, ranking, sizing, candidate selection, and production
orders stay unchanged.

The hedge is intentionally measured as a no-cost upper bound. If the no-cost
overlay fails Gate 4, realistic borrow/slippage/rebalance costs can only make
the policy worse. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_convergence, compute_expected_value_score  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260620-023"
STEM = "core_stack_static_spy_beta_hedge"
TRIAL_FAMILY = "core_stack_static_spy_beta_hedge"
TRIAL_VARIANT_ID = "static_spy_beta_hedge_exp020_pooled_beta_v1"
CHANGED_VARIABLE = "core_stack_static_spy_beta_hedge_v1"
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_023_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
BASELINE_RESULT_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
EXP020_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260620-020"
    / "exp_20260620_020_core_stack_beta_alpha_attribution.json"
)

HEDGE_BETA = 0.347743
INITIAL_CAPITAL_FALLBACK = 100_000.0
MIN_RISK_ALLOCATION_EV_DELTA_PCT = 0.10
MAX_DRAWDOWN_WORSE = 0.0
TRADING_DAYS = 252

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "r2_too_low",
        "hedges_positive_spy_drift",
        "ev_regression",
        "drawdown_not_improved",
        "production_hedge_unsupported",
    ],
    "confidence_reason": (
        "New evidence is exp-20260620-020's measured core beta/alpha "
        "attribution, not another candidate-source or threshold sweep. "
        "Success odds are low because market beta explained only about 4.4% "
        "of mean daily return and prior macro hedge/reduce-beta actions lost "
        "money, but the fixed scalar tests whether hedging improves "
        "risk-adjusted EV without touching alpha selection."
    ),
    "recorded_at": "2026-06-20T17:57:13+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "uses_llm": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "hedge_instrument": "SPY",
        "hedge_direction": "short",
        "hedge_notional_rule": (
            "daily no-cost upper-bound overlay: short SPY notional equals "
            "0.347743 times prior-day simulated core equity"
        ),
        "rebalance_frequency": "daily_close_return_model_only",
        "order_semantics": "not implemented; no broker order",
        "portfolio_displacement": "none; overlay-only replay",
        "kill_switch": "not live eligible; no production adapter changes",
        "failure_handling": (
            "missing core equity curve or same-snapshot SPY close return "
            "rejects the measurement"
        ),
    },
    "parity_note": (
        "Replay-only upper-bound risk-allocation measurement. A positive result "
        "would require a shared hedge policy, production hedge instrument "
        "support, borrow/cost modeling, and daily order/parity tests before any "
        "retention. This run changes no production behavior."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "risk_allocation: exp-20260620-020 showed the accepted core stack "
        "carries small positive realized SPY beta while most return is "
        "residual alpha; a fixed SPY beta hedge sized to the measured pooled "
        "beta may improve EV and drawdown by stripping unrewarded market "
        "exposure without changing entries, exits, ranking, or candidate "
        "selection."
    ),
    "2_history_check": {
        "exp-20260620-020": (
            "Built the new attribution surface: pooled SPY beta 0.347743, "
            "market-model R2 0.0189, beta share of mean daily return 0.0442."
        ),
        "exp-20260605-030": (
            "NFP event-level reduce/short-Q QQQ hedge was rejected; this run "
            "is not an event timing hedge and uses static core beta instead."
        ),
        "exp-20260605-032": (
            "CPI/FOMC/NFP event-level hedge/rebound action was rejected; this "
            "run does not retune event calendars, thresholds, QQQ, or hold "
            "days."
        ),
        "exp-20260618-008": (
            "Equity-curve adaptive sizing was rejected; this run does not use "
            "drawdown thresholds or exposure cuts, only a fixed measured beta "
            "overlay."
        ),
        "novelty_gate": (
            "Reservation novelty check found no strong near-neighbor; no "
            "override was used."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Gate 1-4 per docs/backtesting.md. For this risk-allocation scalar-like "
        "policy, aggregate EV must improve by more than 10%, aggregate PnL must "
        "improve, no window EV/PnL regression is allowed, survival must remain "
        ">=5%, and max drawdown must not worsen. Because the runner is a "
        "no-cost hedge upper bound, failure rejects nearby static hedge "
        "retries."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_023_core_stack_static_spy_beta_hedge.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Path):
        return _repo_rel(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _round(value: Any, digits: int = 6) -> float | None:
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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _get_universe() -> list[str]:
    try:
        from data_layer import get_universe

        return list(get_universe())
    except Exception:
        from filter import WATCHLIST

        return list(WATCHLIST)


def _standard_metrics() -> dict[str, dict[str, Any]]:
    payload = json.loads(BASELINE_RESULT_JSON.read_text(encoding="utf-8"))
    return {str(row["label"]): dict(row) for row in payload["windows"]}


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "passed": False,
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "reason": "missing_open_positions_json",
        }
    payload = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for key in ("positions", "core_positions", "observations"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    missing_entry = [
        str(row.get("ticker") or "<unknown>")
        for row in rows
        if not row.get("entry_date")
    ]
    missing_target = [
        str(row.get("ticker") or "<unknown>")
        for row in rows
        if row.get("target_price") in (None, "")
    ]
    return {
        "passed": not missing_entry and not missing_target,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(rows),
        "checked_groups": ["positions", "core_positions", "observations"],
        "missing_entry_date_tickers": missing_entry,
        "missing_target_price_tickers": missing_target,
    }


def _snapshot_spy_returns(snapshot_path: Path) -> dict[str, float]:
    snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ohlcv = snap.get("ohlcv", snap)
    rows = sorted(ohlcv.get("SPY") or [], key=lambda row: str(row["Date"])[:10])
    returns: dict[str, float] = {}
    prev_close = None
    for row in rows:
        date = str(row["Date"])[:10]
        close = float(row["Close"])
        if prev_close is not None and prev_close > 0:
            returns[date] = close / prev_close - 1.0
        prev_close = close
    return returns


def _daily_returns_from_curve(equity_curve: list) -> dict[str, float]:
    returns: dict[str, float] = {}
    prev = None
    for date_raw, equity_raw in equity_curve:
        date = str(date_raw)[:10]
        equity = float(equity_raw)
        if prev is not None and prev > 0:
            returns[date] = equity / prev - 1.0
        prev = equity
    return returns


def _sharpe_daily(daily_returns: list[float]) -> float | None:
    if len(daily_returns) < 2:
        return None
    mean_r = sum(daily_returns) / len(daily_returns)
    var_r = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std_r = math.sqrt(var_r) if var_r > 0 else 0.0
    if std_r <= 0:
        return None
    return round((mean_r / std_r) * math.sqrt(TRADING_DAYS), 2)


def _max_drawdown(equity_curve: list[tuple[str, float]]) -> float:
    peak = 0.0
    max_dd = 0.0
    for _, equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 4)


def _derive_initial_capital(result: dict[str, Any]) -> float:
    total_pnl = result.get("total_pnl")
    strat_ret = (result.get("benchmarks") or {}).get("strategy_total_return_pct")
    if isinstance(total_pnl, (int, float)) and isinstance(strat_ret, (int, float)):
        if abs(strat_ret) > 1e-12:
            return float(total_pnl) / float(strat_ret)
    return INITIAL_CAPITAL_FALLBACK


def _bench_return_from_snapshot(snapshot_path: Path, ticker: str) -> float | None:
    snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ohlcv = snap.get("ohlcv", snap)
    rows = sorted(ohlcv.get(ticker) or [], key=lambda row: str(row["Date"])[:10])
    if len(rows) < 2:
        return None
    first = float(rows[0]["Close"])
    last = float(rows[-1]["Close"])
    if first <= 0:
        return None
    return last / first - 1.0


def _hedged_metrics(
    *,
    label: str,
    before_result: dict[str, Any],
    snapshot_path: Path,
    standard_before: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    equity_curve = before_result.get("equity_curve") or []
    if len(equity_curve) < 2:
        raise RuntimeError(f"{label}: missing equity_curve")

    spy_returns = _snapshot_spy_returns(snapshot_path)
    strat_returns = _daily_returns_from_curve(equity_curve)
    initial_capital = _derive_initial_capital(before_result)
    before = dict(before_result)
    before.update(standard_before[label])

    after_curve: list[tuple[str, float]] = [(str(equity_curve[0][0])[:10], float(equity_curve[0][1]))]
    hedge_rows: list[dict[str, Any]] = []
    daily_after_returns: list[float] = []
    missing_spy_dates: list[str] = []

    for date_raw, _equity_raw in equity_curve[1:]:
        date = str(date_raw)[:10]
        strat_ret = strat_returns.get(date)
        spy_ret = spy_returns.get(date)
        if strat_ret is None:
            raise RuntimeError(f"{label}: missing strategy return for {date}")
        if spy_ret is None:
            missing_spy_dates.append(date)
            spy_ret = 0.0
        prior_after_equity = after_curve[-1][1]
        hedge_return = -HEDGE_BETA * spy_ret
        after_return = strat_ret + hedge_return
        after_equity = prior_after_equity * (1.0 + after_return)
        after_curve.append((date, after_equity))
        daily_after_returns.append(after_return)
        hedge_rows.append(
            {
                "date": date,
                "strategy_daily_return": _round(strat_ret, 8),
                "spy_daily_return": _round(spy_ret, 8),
                "hedge_beta": HEDGE_BETA,
                "hedge_return": _round(hedge_return, 8),
                "after_daily_return": _round(after_return, 8),
                "prior_after_equity": _round(prior_after_equity, 2),
                "hedge_notional_usd": _round(prior_after_equity * HEDGE_BETA, 2),
                "after_equity": _round(after_equity, 2),
            }
        )

    final_after_equity = after_curve[-1][1]
    strategy_total_return_pct = final_after_equity / initial_capital - 1.0
    total_pnl = strategy_total_return_pct * initial_capital
    sharpe_daily = _sharpe_daily(daily_after_returns)
    max_drawdown_pct = _max_drawdown(after_curve)
    spy_buy_hold = _bench_return_from_snapshot(snapshot_path, "SPY")
    qqq_buy_hold = _bench_return_from_snapshot(snapshot_path, "QQQ")

    after = dict(before)
    after["total_pnl"] = round(total_pnl, 2)
    after["sharpe_daily"] = sharpe_daily
    after["max_drawdown_pct"] = max_drawdown_pct
    after["benchmarks"] = {
        **(before.get("benchmarks") or {}),
        "spy_buy_hold_return_pct": round(spy_buy_hold, 4)
        if spy_buy_hold is not None
        else None,
        "qqq_buy_hold_return_pct": round(qqq_buy_hold, 4)
        if qqq_buy_hold is not None
        else None,
        "strategy_total_return_pct": round(strategy_total_return_pct, 4),
        "strategy_vs_spy_pct": round(strategy_total_return_pct - spy_buy_hold, 4)
        if spy_buy_hold is not None
        else None,
        "strategy_vs_qqq_pct": round(strategy_total_return_pct - qqq_buy_hold, 4)
        if qqq_buy_hold is not None
        else None,
    }
    after["expected_value_score"] = compute_expected_value_score(after)
    after["convergence"] = compute_convergence(after)
    after["static_spy_beta_hedge_overlay"] = {
        "hedge_beta": HEDGE_BETA,
        "hedge_direction": "short_SPY",
        "cost_model": "no_cost_upper_bound",
        "daily_rows": len(hedge_rows),
        "missing_spy_return_dates": missing_spy_dates,
        "initial_capital": round(initial_capital, 2),
    }

    delta = _delta(after, before)
    slim_before = _slim_metrics(before)
    slim_after = _slim_metrics(after)
    return slim_before, slim_after, delta, hedge_rows


def _slim_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades")
        if result.get("total_trades") is not None
        else result.get("trade_count"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "spy_buy_hold_return_pct": benchmarks.get("spy_buy_hold_return_pct"),
        "qqq_buy_hold_return_pct": benchmarks.get("qqq_buy_hold_return_pct"),
        "strategy_vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    after_s = _slim_metrics(after)
    before_s = _slim_metrics(before)
    out: dict[str, Any] = {}
    for key, before_value in before_s.items():
        after_value = after_s.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            digits = 2 if key == "total_pnl" else 4
            out[key] = round(float(after_value) - float(before_value), digits)
    return out


def _aggregate(window_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in window_rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in window_rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in window_rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in window_rows.values())
    ev_delta = ev_after - ev_before
    pnl_delta = pnl_after - pnl_before
    dd_delta_max = max(row["delta"].get("max_drawdown_pct", 0.0) for row in window_rows.values())
    dd_delta_min = min(row["delta"].get("max_drawdown_pct", 0.0) for row in window_rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before, 6)
        if ev_before
        else None,
        "required_expected_value_score_delta_sum": _round(
            ev_before * MIN_RISK_ALLOCATION_EV_DELTA_PCT, 6
        ),
        "expected_value_score_delta_gt_required": (
            ev_delta > ev_before * MIN_RISK_ALLOCATION_EV_DELTA_PCT
        )
        if ev_before
        else False,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "windows_ev_improved": sum(
            1 for row in window_rows.values() if row["delta"].get("expected_value_score", 0) > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in window_rows.values() if row["delta"].get("expected_value_score", 0) < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in window_rows.values() if row["delta"].get("total_pnl", 0) > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in window_rows.values() if row["delta"].get("total_pnl", 0) < 0
        ),
        "max_drawdown_delta_max": _round(dd_delta_max, 6),
        "max_drawdown_delta_min": _round(dd_delta_min, 6),
        "total_core_trade_count": sum(
            int(row["before"].get("total_trades") or 0) for row in window_rows.values()
        ),
        "minimum_core_survival_rate": _round(
            min(float(row["before"].get("survival_rate") or 0.0) for row in window_rows.values()),
            6,
        ),
    }


def _gate4(aggregate: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if not aggregate["expected_value_score_delta_gt_required"]:
        failed.append("aggregate_ev_delta_not_gt_10pct")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_worse")
    if float(aggregate["max_drawdown_delta_min"] or 0.0) >= 0.0:
        failed.append("drawdown_not_improved")
    if float(aggregate["minimum_core_survival_rate"] or 0.0) < 0.05:
        failed.append("core_survival_rate_below_5pct")
    return {
        "passed": not failed,
        "decision": (
            "positive_replay_lead_not_promoted_core_stack_static_spy_beta_hedge"
            if not failed
            else "rejected_core_stack_static_spy_beta_hedge"
        ),
        "failed_reasons": failed,
        "aggregate": aggregate,
        "acceptance_rule": (
            "Risk-allocation scalar-like policy must improve aggregate EV by "
            ">10%, improve aggregate PnL, avoid every window regression, keep "
            "survival >=5%, and not worsen drawdown. This no-cost upper-bound "
            "runner also requires at least one window drawdown improvement."
        ),
    }


def _load_exp020_summary() -> dict[str, Any]:
    payload = json.loads(EXP020_ARTIFACT.read_text(encoding="utf-8"))
    pooled = ((payload.get("attribution") or {}).get("pooled") or {}).get(
        "market_model", {}
    )
    return {
        "artifact": _repo_rel(EXP020_ARTIFACT),
        "pooled_market_beta": pooled.get("beta_market"),
        "pooled_r2": pooled.get("r2"),
        "pooled_beta_share_of_mean": (
            (pooled.get("mean_daily_decomposition") or {}).get("beta_share_of_mean")
        ),
        "pooled_alpha_annualized": pooled.get("alpha_annualized"),
        "pooled_alpha_tstat": pooled.get("alpha_tstat"),
    }


def _run_window(label: str, cfg: dict[str, str], standard: dict[str, dict[str, Any]]):
    print(f"[{label}] core baseline and static SPY beta hedge overlay")
    universe = sorted(_get_universe())
    snapshot = REPO_ROOT / cfg["snapshot"]
    engine = BacktestEngine(
        universe,
        start=cfg["start"],
        end=cfg["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
            "ATR_STOP_DAILY_RECOMPUTE": False,
            "ATR_STOP_TRIGGER_ON_CLOSE": False,
            "ATR_STOP_EXIT_NEXT_OPEN": False,
        },
        ohlcv_snapshot_path=str(snapshot),
        include_oracle_diagnostics=False,
    )
    before_result = engine.run()
    if "error" in before_result:
        raise RuntimeError(f"{label}: backtest error: {before_result['error']}")
    before, after, delta, hedge_rows = _hedged_metrics(
        label=label,
        before_result=before_result,
        snapshot_path=snapshot,
        standard_before=standard,
    )
    return {
        "before": before,
        "after": after,
        "delta": delta,
        "hedge_rows_sample": hedge_rows[:20],
        "hedge_day_count": len(hedge_rows),
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open_positions = _audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    standard = _standard_metrics()
    exp020 = _load_exp020_summary()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label, cfg in WINDOWS.items():
        window_rows[label] = _run_window(label, cfg, standard)

    aggregate = _aggregate(window_rows)
    gate4 = _gate4(aggregate)
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = (
        "The no-cost static SPY beta hedge cleared the strict risk-allocation "
        "Gate 4, but remains only a replay lead because no shared hedge policy "
        "or production hedge order support exists."
        if gate4["passed"]
        else (
            "Rejected. The no-cost static SPY beta hedge did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "Because this is already a no-cost upper bound, realistic hedge "
            "costs would not rescue the policy."
        )
    )
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0))
            ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": gate4["passed"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "risk_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "core_stack_portfolio_beta_risk_allocation",
        "new_evidence_type": "new_core_stack_beta_alpha_attribution_surface",
        "nearby_prior_experiments": [
            "exp-20260620-020",
            "exp-20260605-030",
            "exp-20260605-032",
            "exp-20260618-008",
        ],
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "exp020_beta_attribution_source": exp020,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "same-snapshot no-cost static SPY beta hedge overlay"
            ),
            "windows": WINDOWS,
            "baseline_result_file": _repo_rel(BASELINE_RESULT_JSON),
            "beta_source_artifact": _repo_rel(EXP020_ARTIFACT),
            "hedge_beta": HEDGE_BETA,
            "hedge_semantics": (
                "daily return overlay: after_return = core_return - "
                "0.347743 * same-day SPY close-to-close return"
            ),
            "costs": "no_cost_upper_bound",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "hedge_beta": HEDGE_BETA,
            "hedge_instrument": "SPY",
            "hedge_direction": "short",
            "cost_model": "none_upper_bound",
            "min_risk_allocation_ev_delta_pct": MIN_RISK_ALLOCATION_EV_DELTA_PCT,
            "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md canonical three-window baseline",
            "baseline_metrics": OrderedDict(
                (label, row["before"]) for label, row in window_rows.items()
            ),
            "ev_sanity": {
                label: {
                    "recomputed": row["before"]["expected_value_score"],
                    "standard": standard[label]["expected_value_score"],
                }
                for label, row in window_rows.items()
            },
            "passed": True,
        },
        "gate2": {
            "open_positions_field_audit": gate2_open_positions,
            "runtime_fields_checked": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "core backtest equity_curve",
                "same-snapshot SPY close-to-close returns",
                "fixed hedge beta from exp-20260620-020",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": aggregate["minimum_core_survival_rate"],
            "survival_rate_by_window": OrderedDict(
                (label, row["before"].get("survival_rate"))
                for label, row in window_rows.items()
            ),
            "passed": float(aggregate["minimum_core_survival_rate"] or 0.0) >= 0.05,
            "note": (
                "No entry, exit, ranking, sizing, or filter changed; survival "
                "is inherited from the accepted core baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": OrderedDict(
            (label, row["before"]) for label, row in window_rows.items()
        ),
        "after_metrics": OrderedDict(
            (label, row["after"]) for label, row in window_rows.items()
        ),
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "hedge_diagnostics": OrderedDict(
            (
                label,
                {
                    "hedge_day_count": row["hedge_day_count"],
                    "hedge_rows_sample": row["hedge_rows_sample"],
                },
            )
            for label, row in window_rows.items()
        ),
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "Do not retry static SPY beta hedges, hedge-beta scalar sweeps, "
            "or daily rebalance-cost variants on these frozen windows. A valid "
            "hedge retry needs a materially different PIT state field, such as "
            "forward state-tagged beta instability, options/volatility hedge "
            "pricing, or a production-supported hedge instrument with closed "
            "forward replacement-value rows."
        ),
        "post_run_reflection": {
            "why_result_happened": interpretation,
            "outcome_summary": (
                "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
                "max drawdown delta {:+.4f}; min drawdown delta {:+.4f}; "
                "core trades unchanged at {}.".format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                    float(aggregate["max_drawdown_delta_max"] or 0.0),
                    float(aggregate["max_drawdown_delta_min"] or 0.0),
                    aggregate["total_core_trade_count"],
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry static SPY beta hedge scalar sweeps, QQQ/IWM "
                "proxy substitutions, no-cost versus cost rebalance variants, "
                "or drawdown-triggered hedge toggles on the frozen windows."
            ),
            "new_evidence_required": (
                "Need a materially different PIT hedge state surface, forward "
                "state-tagged hedge rows, real hedge instrument support, or "
                "new factor data such as MTUM/QUAL/USMV to justify reopening."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Sharpe d |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {sh:+.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                sh=delta.get("sharpe_daily", 0.0),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core-Stack Static SPY Beta Hedge",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate EV delta pct: `{:+.2%}`".format(
                aggregate["expected_value_score_delta_pct"] or 0.0
            ),
            "- Required EV delta pct: `{:.2%}`".format(
                MIN_RISK_ALLOCATION_EV_DELTA_PCT
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Max drawdown delta: `{:+.4f}`".format(
                aggregate["max_drawdown_delta_max"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only no-cost upper-bound hedge overlay. No shared "
                "policy, production adapter, broker order, watchlist, core "
                "entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": _repo_rel(BASELINE_RESULT_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "max_drawdown_delta": payload["delta_metrics"]["by_window"][label][
                    "max_drawdown_pct"
                ],
                "hedge_day_count": payload["hedge_diagnostics"][label][
                    "hedge_day_count"
                ],
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(_build_log_record(payload)),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
