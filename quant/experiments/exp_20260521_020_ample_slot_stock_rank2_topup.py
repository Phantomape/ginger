"""exp-20260521-020: ample-slot stock rank-2 top-up scout.

Alpha search. Test whether the second planned non-ETF/non-commodity stock
candidate also deserves a small cap-aware post-sizing top-up on days with
ample entry slots. The only causal variable is the rank-2 top-up scalar.

This runner uses an experiment-only monkey patch. If a variant passes Gate 4,
promotion must move the rule into shared production/backtest policy before
orders change.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
import production_parity as pp  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import (  # noqa: E402
    AMPLE_SLOT_STOCK_RANK1_AVAILABLE_SLOTS_MIN,
    AMPLE_SLOT_STOCK_RANK1_EXCLUDED_SECTORS,
    MAX_POSITION_PCT,
)
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260521-020"
STEM = "ample_slot_stock_rank2_topup"
RANK2_MULTIPLIER_KEY = "ample_slot_stock_rank2_risk_multiplier_applied"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        ("rank2_1p025x", {"rank2_multiplier": 1.025}),
        ("rank2_1p05x", {"rank2_multiplier": 1.05}),
        ("rank2_1p075x", {"rank2_multiplier": 1.075}),
        ("rank2_1p10x", {"rank2_multiplier": 1.10}),
    ]
)

MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 4
MIN_AFFECTED_WINDOW_COUNT = 2
MIN_TRADE_COUNT_SUM = 58
RANK2_TOPUPS: list[dict[str, Any]] = []


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _risk_distribution(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades") or []
    pnl_pcts = [
        float(trade.get("pnl_pct_net"))
        for trade in trades
        if trade.get("pnl_pct_net") is not None
    ]
    pnls = [float(trade.get("pnl") or 0.0) for trade in trades]
    worst_trade_pct = min(pnl_pcts) if pnl_pcts else None
    max_consecutive_losses = 0
    current_losses = 0
    for pnl in pnls:
        if pnl < 0:
            current_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_losses)
        else:
            current_losses = 0
    total_loss = abs(sum(pnl for pnl in pnls if pnl < 0))
    worst_three_loss = abs(sum(sorted((pnl for pnl in pnls if pnl < 0))[:3]))
    return {
        "worst_trade_pct": _round(worst_trade_pct, 6),
        "max_consecutive_losses": max_consecutive_losses,
        "tail_loss_share": _round(worst_three_loss / total_loss, 6)
        if total_loss
        else 0.0,
    }


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
        **_risk_distribution(result),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "worst_trade_pct",
        "max_consecutive_losses",
        "tail_loss_share",
    )
    out: dict[str, Any] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(
            after_value, (int, float)
        ):
            if key in {
                "trade_count",
                "signals_generated",
                "signals_survived",
                "max_consecutive_losses",
            }:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _aggregate(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    values = list(metrics_by_window.values())
    return {
        "expected_value_score_sum": _round(
            sum(float(item.get("expected_value_score") or 0.0) for item in values),
            4,
        ),
        "total_pnl_sum": _round(
            sum(float(item.get("total_pnl") or 0.0) for item in values),
            2,
        ),
        "trade_count_sum": int(sum(int(item.get("trade_count") or 0) for item in values)),
        "signals_generated_sum": int(
            sum(int(item.get("signals_generated") or 0) for item in values)
        ),
        "signals_survived_sum": int(
            sum(int(item.get("signals_survived") or 0) for item in values)
        ),
        "survival_rate_min": _round(
            min(float(item.get("survival_rate") or 0.0) for item in values),
            4,
        ),
        "max_drawdown_pct_max": _round(
            max(float(item.get("max_drawdown_pct") or 0.0) for item in values),
            4,
        ),
        "worst_trade_pct_min": _round(
            min(float(item.get("worst_trade_pct") or 0.0) for item in values),
            6,
        ),
        "max_consecutive_losses_max": int(
            max(int(item.get("max_consecutive_losses") or 0) for item in values)
        ),
        "tail_loss_share_max": _round(
            max(float(item.get("tail_loss_share") or 0.0) for item in values),
            6,
        ),
        "all_converged": all(bool(item.get("converged")) for item in values),
    }


def _aggregate_delta(
    after: dict[str, dict[str, Any]],
    before: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_agg = _aggregate(before)
    after_agg = _aggregate(after)
    return {
        "expected_value_score_sum": _round(
            after_agg["expected_value_score_sum"]
            - before_agg["expected_value_score_sum"],
            4,
        ),
        "total_pnl_sum": _round(after_agg["total_pnl_sum"] - before_agg["total_pnl_sum"], 2),
        "trade_count_sum": int(after_agg["trade_count_sum"] - before_agg["trade_count_sum"]),
        "max_drawdown_pct_max": _round(
            after_agg["max_drawdown_pct_max"] - before_agg["max_drawdown_pct_max"],
            6,
        ),
        "worst_trade_pct_min": _round(
            after_agg["worst_trade_pct_min"] - before_agg["worst_trade_pct_min"],
            6,
        ),
        "max_consecutive_losses_max": int(
            after_agg["max_consecutive_losses_max"]
            - before_agg["max_consecutive_losses_max"]
        ),
        "tail_loss_share_max": _round(
            after_agg["tail_loss_share_max"] - before_agg["tail_loss_share_max"],
            6,
        ),
        "survival_rate_min": _round(
            after_agg["survival_rate_min"] - before_agg["survival_rate_min"],
            6,
        ),
    }


def _open_position_field_check() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "checked_fields": ["entry_date", "target_price"],
            "missing_count": 0,
            "missing_examples": [],
            "note": "No live open position file; experiment does not add an exit rule.",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("positions", [])
    missing = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        absent = [
            field
            for field in ("entry_date", "target_price")
            if row.get(field) in (None, "")
        ]
        if absent:
            missing.append({"ticker": row.get("ticker"), "missing_fields": absent})
    return {
        "path": str(path),
        "exists": True,
        "checked_fields": ["entry_date", "target_price"],
        "position_count": len(rows or []),
        "missing_count": len(missing),
        "missing_examples": missing[:10],
        "note": "This allocation experiment does not depend on these fields.",
    }


def _apply_rank2_topup(
    planned: list[dict[str, Any]],
    available_slots: int,
    rank2_multiplier: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if (
        available_slots < AMPLE_SLOT_STOCK_RANK1_AVAILABLE_SLOTS_MIN
        or len(planned) < 2
        or rank2_multiplier <= 1.0
    ):
        return planned, []

    adjusted = list(planned)
    sig = dict(adjusted[1])
    sector = sig.get("sector")
    if not sector or sector in AMPLE_SLOT_STOCK_RANK1_EXCLUDED_SECTORS:
        return planned, []

    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return planned, []

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    portfolio_value = float(sizing.get("portfolio_value_usd") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0 or portfolio_value <= 0 or net_risk_per_share <= 0:
        return planned, []

    cap_pct = float(sizing.get("max_position_pct_applied") or MAX_POSITION_PCT)
    desired_shares = max(old_shares, int(math.floor(old_shares * rank2_multiplier)))
    cap_shares = int(math.floor(portfolio_value * cap_pct / entry))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= old_shares:
        return planned, []

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value
    sizing["ample_slot_stock_rank2_state"] = True
    sizing["ample_slot_stock_rank2_available_slots"] = available_slots
    sizing["ample_slot_stock_rank2_baseline_shares"] = old_shares
    sizing["ample_slot_stock_rank2_desired_shares"] = desired_shares
    sizing["ample_slot_stock_rank2_cap_shares"] = cap_shares
    sizing["ample_slot_stock_rank2_new_shares"] = new_shares
    sizing[RANK2_MULTIPLIER_KEY] = rank2_multiplier
    sig["sizing"] = sizing
    adjusted[1] = sig

    record = {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sector,
        "available_slots": available_slots,
        "baseline_shares": old_shares,
        "desired_shares": desired_shares,
        "cap_shares": cap_shares,
        "new_shares": new_shares,
        "multiplier": rank2_multiplier,
        "trade_quality_score": sig.get("trade_quality_score"),
        "confidence_score": sig.get("confidence_score"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
        "price_vs_200ma_extension_state": sig.get("price_vs_200ma_extension_state"),
        "days_to_earnings": sig.get("days_to_earnings"),
        "gap_vulnerability_pct": sig.get("gap_vulnerability_pct"),
    }
    return adjusted, [record]


def _make_ample_rank1_wrapper(
    original: Callable[..., tuple[list[dict[str, Any]], list[dict[str, Any]]]],
    rank2_multiplier: float,
):
    def wrapped(signals, available_slots, multiplier=None):
        planned, topups = original(signals, available_slots, multiplier=multiplier)
        adjusted, rank2_topups = _apply_rank2_topup(
            planned,
            available_slots,
            rank2_multiplier,
        )
        if rank2_topups:
            RANK2_TOPUPS.extend(rank2_topups)
        return adjusted, list(topups or []) + rank2_topups

    return wrapped


def _run_window(
    label: str,
    window: dict[str, Any],
    *,
    rank2_multiplier: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original_ample = pp._apply_ample_slot_stock_rank1_topup
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    RANK2_TOPUPS.clear()
    if RANK2_MULTIPLIER_KEY not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (
            *bt.SIZING_MULTIPLIER_KEYS,
            RANK2_MULTIPLIER_KEY,
        )
    if rank2_multiplier is not None:
        pp._apply_ample_slot_stock_rank1_topup = _make_ample_rank1_wrapper(
            original_ample,
            rank2_multiplier,
        )
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        result = engine.run()
        return result, list(RANK2_TOPUPS)
    finally:
        pp._apply_ample_slot_stock_rank1_topup = original_ample
        bt.SIZING_MULTIPLIER_KEYS = original_keys
        RANK2_TOPUPS.clear()


def _run_baseline() -> dict[str, dict[str, Any]]:
    return {
        label: _run_window(label, window)[0]
        for label, window in WINDOWS.items()
    }


def _run_variant(rank2_multiplier: float) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: dict[str, dict[str, Any]] = {}
    topups_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, window in WINDOWS.items():
        result, topups = _run_window(
            label,
            window,
            rank2_multiplier=rank2_multiplier,
        )
        results[label] = result
        topups_by_window[label] = topups
    return results, topups_by_window


def _gate4_status(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    topups_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    before_metrics = {label: _metrics(result) for label, result in before.items()}
    after_metrics = {label: _metrics(result) for label, result in after.items()}
    deltas = {
        label: _delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    agg_delta = _aggregate_delta(after_metrics, before_metrics)
    improved_windows = [
        label
        for label, delta in deltas.items()
        if float(delta.get("expected_value_score") or 0.0) > 0.0
    ]
    regressed_windows = [
        label
        for label, delta in deltas.items()
        if float(delta.get("expected_value_score") or 0.0) < 0.0
    ]
    topup_counts = {label: len(rows) for label, rows in topups_by_window.items()}
    affected_signal_count = sum(topup_counts.values())
    affected_window_count = sum(1 for count in topup_counts.values() if count > 0)
    passed = (
        agg_delta["expected_value_score_sum"] > 0.0
        and agg_delta["total_pnl_sum"] > 0.0
        and len(improved_windows) >= 2
        and not regressed_windows
        and agg_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and _aggregate(after_metrics)["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
        and _aggregate(after_metrics)["survival_rate_min"] >= 0.05
        and affected_signal_count >= MIN_AFFECTED_SIGNAL_COUNT
        and affected_window_count >= MIN_AFFECTED_WINDOW_COUNT
    )
    return {
        "passed": bool(passed),
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "topup_counts": topup_counts,
        "affected_signal_count": affected_signal_count,
        "affected_window_count": affected_window_count,
        "aggregate_delta": agg_delta,
        "window_deltas": deltas,
        "guardrails": {
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "min_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "min_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "min_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "min_survival_rate": 0.05,
        },
    }


def _topup_summary(topups_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    tickers: set[str] = set()
    sectors: dict[str, int] = {}
    for rows in topups_by_window.values():
        for row in rows:
            ticker = row.get("ticker")
            if ticker:
                tickers.add(str(ticker))
            sector = str(row.get("sector") or "Unknown")
            sectors[sector] = sectors.get(sector, 0) + 1
    return {
        "count": sum(len(rows) for rows in topups_by_window.values()),
        "window_counts": {label: len(rows) for label, rows in topups_by_window.items()},
        "unique_tickers": sorted(tickers),
        "sector_counts": dict(sorted(sectors.items())),
        "sample": {
            label: rows[:10]
            for label, rows in topups_by_window.items()
            if rows
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                kept.append(line)
    kept.append(json.dumps(record, sort_keys=True, ensure_ascii=False))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Trial accounting",
        f"- trial_family: {payload['trial_family']}",
        f"- changed_variable: {payload['changed_variable']}",
        f"- prior_trial_count: {payload['prior_trial_count']}",
        f"- multiple_testing_risk_bucket: {payload['multiple_testing_risk_bucket']}",
        f"- new_evidence_type: {payload['new_evidence_type']}",
        "",
        "## Three-window aggregate",
        f"- baseline EV: {payload['before_metrics']['aggregate']['expected_value_score_sum']}",
        f"- best EV: {payload['after_metrics']['aggregate']['expected_value_score_sum']}",
        f"- EV delta: {payload['delta_metrics']['aggregate']['expected_value_score_sum']}",
        f"- PnL delta: {payload['delta_metrics']['aggregate']['total_pnl_sum']}",
        f"- decision: {payload['decision']}",
        "",
        "## Sweep summary",
        "| variant | multiplier | EV delta | PnL delta | DD delta | affected | windows | passed |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {multiplier} | {ev_delta} | {pnl_delta} | {dd_delta} | {affected} | {windows} | {passed} |".format(
                variant=row["variant"],
                multiplier=row["rank2_multiplier"],
                ev_delta=row["gate4"]["aggregate_delta"]["expected_value_score_sum"],
                pnl_delta=row["gate4"]["aggregate_delta"]["total_pnl_sum"],
                dd_delta=row["gate4"]["aggregate_delta"]["max_drawdown_pct_max"],
                affected=row["gate4"]["affected_signal_count"],
                windows=",".join(row["gate4"]["improved_windows"]),
                passed=row["gate4"]["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Window deltas for selected variant",
            "| window | EV | PnL | DD | survival |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, row in payload["delta_metrics"]["windows"].items():
        lines.append(
            f"| {label} | {row.get('expected_value_score')} | {row.get('total_pnl')} | {row.get('max_drawdown_pct')} | {row.get('survival_rate')} |"
        )
    lines.extend(
        [
            "",
            "## Production impact",
            "```text",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "## Rejection reason / next evidence",
            payload.get("rejection_reason") or "n/a",
            "",
            json.dumps(payload.get("next_retry_requires"), indent=2, ensure_ascii=False),
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    field_check = _open_position_field_check()
    baseline_results = _run_baseline()
    before_metrics = {
        label: _metrics(result)
        for label, result in baseline_results.items()
    }

    sweep_summary = []
    variant_payloads: dict[str, dict[str, Any]] = {}
    for variant, params in VARIANTS.items():
        after_results, topups_by_window = _run_variant(params["rank2_multiplier"])
        after_metrics = {
            label: _metrics(result)
            for label, result in after_results.items()
        }
        gate4 = _gate4_status(baseline_results, after_results, topups_by_window)
        payload = {
            "variant": variant,
            "rank2_multiplier": params["rank2_multiplier"],
            "after_results": after_results,
            "after_metrics": after_metrics,
            "delta_metrics": {
                label: _delta(after_metrics[label], before_metrics[label])
                for label in WINDOWS
            },
            "gate4": gate4,
            "topup_summary": _topup_summary(topups_by_window),
        }
        variant_payloads[variant] = payload
        sweep_summary.append(
            {
                "variant": variant,
                "rank2_multiplier": params["rank2_multiplier"],
                "gate4": gate4,
                "topup_summary": payload["topup_summary"],
            }
        )

    def sort_key(item: dict[str, Any]) -> tuple[int, float, float]:
        return (
            1 if item["gate4"]["passed"] else 0,
            float(item["gate4"]["aggregate_delta"]["expected_value_score_sum"]),
            float(item["gate4"]["aggregate_delta"]["total_pnl_sum"]),
        )

    selected_summary = max(sweep_summary, key=sort_key)
    selected = variant_payloads[selected_summary["variant"]]
    selected_after = selected["after_metrics"]
    passed = bool(selected["gate4"]["passed"])
    status = "accepted" if passed else "rejected"
    decision = "accepted" if passed else "rejected"
    rejection_reason = None
    if not passed:
        if selected["gate4"]["regressed_windows"]:
            rejection_reason = (
                "Best variant failed Gate 4 because at least one standard "
                "window regressed on expected_value_score."
            )
        elif selected["gate4"]["affected_signal_count"] < MIN_AFFECTED_SIGNAL_COUNT:
            rejection_reason = (
                "Best variant failed sample guard; affected rank-2 top-up "
                "signals are too sparse."
            )
        else:
            rejection_reason = (
                "Best variant did not produce positive aggregate EV/PnL with "
                "all Gate 4 guardrails satisfied."
            )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "hypothesis": (
            "On days with at least four available slots, the second planned "
            "non-ETF/non-commodity stock candidate may be a replacement-value "
            "signal that deserves a small cap-aware post-sizing top-up."
        ),
        "change_summary": (
            "Sweep an experiment-only ample-slot stock rank-2 post-sizing "
            "risk multiplier over 1.025x, 1.05x, 1.075x, and 1.10x."
        ),
        "change_type": "capital_allocation",
        "mechanism_family": "core_slot_allocation",
        "trial_family": "core_slot_rank_post_sizing_topup",
        "trial_variant_id": selected["variant"],
        "changed_variable": "ample_slot_stock_rank2_risk_multiplier",
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260517-009",
            "exp-20260516-036",
            "exp-20260520-020",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_replacement_value_cohort",
        "component": "quant/production_parity.py",
        "parameters": {
            "available_slots_min": AMPLE_SLOT_STOCK_RANK1_AVAILABLE_SLOTS_MIN,
            "rank_index": 2,
            "excluded_sectors": list(AMPLE_SLOT_STOCK_RANK1_EXCLUDED_SECTORS),
            "baseline_multiplier": 1.0,
            "swept_multipliers": [
                params["rank2_multiplier"] for params in VARIANTS.values()
            ],
            "selected_multiplier": selected["rank2_multiplier"],
        },
        "date_range": {
            "protocol": "docs/backtesting.md standard_three_window",
            "windows": {
                label: {
                    "start": window["start"],
                    "end": window["end"],
                    "snapshot": window["snapshot"],
                    "state_note": window["state_note"],
                }
                for label, window in WINDOWS.items()
            },
        },
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "before_metrics": {
            "windows": before_metrics,
            "aggregate": _aggregate(before_metrics),
        },
        "after_metrics": {
            "windows": selected_after,
            "aggregate": _aggregate(selected_after),
        },
        "delta_metrics": {
            "windows": selected["delta_metrics"],
            "aggregate": _aggregate_delta(selected_after, before_metrics),
        },
        "sweep_summary": sweep_summary,
        "selected_topup_summary": selected["topup_summary"],
        "gate1": {
            "baseline_protocol": "docs/backtesting.md standard three non-overlapping windows",
            "baseline_artifact": str(OUT_JSON),
            "baseline_metrics_readable": True,
        },
        "gate2": {
            "field_check": field_check,
            "rule_dependencies": [
                "planned signal rank after shared entry planning",
                "sector",
                "sizing.shares_to_buy",
                "sizing.entry_price",
                "sizing.portfolio_value_usd",
                "sizing.net_risk_per_share",
                "sizing.max_position_pct_applied",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "survival_rate_min_before": _aggregate(before_metrics)[
                "survival_rate_min"
            ],
            "survival_rate_min_after": _aggregate(selected_after)[
                "survival_rate_min"
            ],
            "signals_generated_sum_before": _aggregate(before_metrics)[
                "signals_generated_sum"
            ],
            "signals_survived_sum_before": _aggregate(before_metrics)[
                "signals_survived_sum"
            ],
            "signals_generated_sum_after": _aggregate(selected_after)[
                "signals_generated_sum"
            ],
            "signals_survived_sum_after": _aggregate(selected_after)[
                "signals_survived_sum"
            ],
        },
        "gate4": selected["gate4"],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "llm_attribution_metric": "not_applicable",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_accepted": (
                "Move rank-2 top-up into quant/production_parity.py and add "
                "shared policy tests before any production orders change."
            ),
        },
        "why_not_other_changes": (
            "Recent event/state scalar and attention-persistence lanes are "
            "nearby rejected or sample-limited; broad-market and LLM soft-ranking "
            "forward datasets are too sparse for a credible alpha decision."
        ),
        "known_risks": [
            "High multiple-testing risk because rank-1 ample-slot top-up is already accepted.",
            "Experiment-only monkey patch must not be treated as production-ready.",
            "Top-up size changes fills and risk but not entry ordering or filters.",
        ],
        "rejection_reason": rejection_reason,
        "next_retry_requires": (
            [
                "Do not retry nearby rank-2 scalar values without new forward rows or a new production-visible replacement-value feature.",
                "If a variant passes, promote into shared production_parity policy and rerun this same three-window protocol.",
            ]
            if not passed
            else [
                "Promote selected scalar into shared production_parity policy.",
                "Add parity/unit coverage for rank-2 ample-slot top-up.",
                "Rerun the same three-window protocol after promotion.",
            ]
        ),
        "related_files": [
            "quant/experiments/exp_20260521_020_ample_slot_stock_rank2_topup.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
        "notes": "No JavaScript used. This is alpha_search, not measurement repair.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps(
        {
            "experiment_id": result["experiment_id"],
            "decision": result["decision"],
            "selected_variant": result["trial_variant_id"],
            "aggregate_delta": result["delta_metrics"]["aggregate"],
            "gate4_passed": result["gate4"]["passed"],
            "artifact": str(ARTIFACT_MD),
        },
        indent=2,
        sort_keys=True,
    ))
