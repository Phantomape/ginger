"""exp-20260510-006 zero-position QQQ overlay replay.

Alpha search, replay-only. Prior QQQ overlay attempts failed when modeled as a
normal trade-style sleeve or broad idle-cash proxy. This run tests one narrower
timing discriminator on the refreshed accepted stack: allow a fixed-notional
QQQ overlay only on days when the core A/B book has zero active positions and
QQQ was in a positive long-term state at the prior close.

No production orders, default backtest behavior, signal generation, candidate
ranking, sizing, exits, add-ons, LLM, news, or universe membership are changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
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


EXPERIMENT_ID = "exp-20260510-006"
STEM = "zero_position_qqq_overlay"
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
OVERLAY_TICKER = "QQQ"
STATE_SMA_DAYS = 200
STATE_MOMENTUM_DAYS = 20
NOTIONAL_FRACTIONS = [0.10, 0.20, 0.30, 0.50, 1.00]

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
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
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
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


def _load_snapshot_rows(snapshot_path: str, ticker: str) -> list[dict[str, Any]]:
    payload = json.loads((REPO_ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows = []
    for row in (payload.get("ohlcv") or {}).get(ticker, []):
        rows.append(
            {
                "date": row["Date"],
                "open": float(row["Open"]),
                "close": float(row["Close"]),
            }
        )
    return sorted(rows, key=lambda row: row["date"])


def _core_active_dates(result: dict[str, Any]) -> set[str]:
    curve_dates = [day for day, _ in result.get("equity_curve") or []]
    active: set[str] = set()
    for trade in result.get("trades") or []:
        if trade.get("strategy") not in {"trend_long", "breakout_long"}:
            continue
        entry = trade.get("entry_date")
        exit_ = trade.get("exit_date")
        if not entry or not exit_:
            continue
        for day in curve_dates:
            if entry <= day <= exit_:
                active.add(day)
    return active


def _overlay_path(
    result: dict[str, Any],
    qqq_rows: list[dict[str, Any]],
    notional_fraction: float,
) -> dict[str, Any]:
    base_curve = result.get("equity_curve") or []
    curve_dates = {day for day, _ in base_curve}
    core_active = _core_active_dates(result)
    overlay_pnl_by_date: dict[str, float] = {}
    overlay_days: list[dict[str, Any]] = []

    for idx, row in enumerate(qqq_rows):
        day = row["date"]
        if day not in curve_dates or day in core_active:
            continue
        if idx < max(STATE_SMA_DAYS, STATE_MOMENTUM_DAYS) + 1:
            continue
        prior_idx = idx - 1
        prior = qqq_rows[prior_idx]
        sma_window = qqq_rows[prior_idx - STATE_SMA_DAYS + 1 : prior_idx + 1]
        sma = sum(item["close"] for item in sma_window) / len(sma_window)
        momentum = prior["close"] / qqq_rows[prior_idx - STATE_MOMENTUM_DAYS]["close"] - 1.0
        active = prior["close"] > sma and momentum > 0.0
        if not active:
            continue
        notional = INITIAL_CAPITAL * notional_fraction
        pnl = notional * (row["close"] / row["open"] - 1.0)
        overlay_pnl_by_date[day] = pnl
        overlay_days.append(
            {
                "date": day,
                "prior_close": _round(prior["close"], 4),
                "prior_sma200": _round(sma, 4),
                "prior_momentum20": _round(momentum, 6),
                "open": _round(row["open"], 4),
                "close": _round(row["close"], 4),
                "notional": _round(notional, 2),
                "pnl": _round(pnl, 2),
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in base_curve:
        cumulative_overlay += overlay_pnl_by_date.get(day, 0.0)
        combined_curve.append((day, round(float(equity) + cumulative_overlay, 2)))

    return {
        "combined_equity_curve": combined_curve,
        "overlay_total_pnl": round(sum(overlay_pnl_by_date.values()), 2),
        "overlay_day_count": len(overlay_days),
        "core_active_day_count": len(core_active),
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
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "min_overlay_day_count": min(row["overlay_day_count"] for row in rows.values()),
        "overlay_day_count_sum": sum(row["overlay_day_count"] for row in rows.values()),
    }


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
            "zero-position overlay value rather than production cash sizing."
        ),
    }


def _build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    base_by_window: dict[str, dict[str, Any]] = OrderedDict()
    qqq_by_window: dict[str, list[dict[str, Any]]] = {}
    variant_rows: dict[str, dict[str, Any]] = OrderedDict()

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
        base_by_window[label] = result
        qqq_by_window[label] = _load_snapshot_rows(window["snapshot"], OVERLAY_TICKER)

    for fraction in NOTIONAL_FRACTIONS:
        variant = f"zero_position_qqq_{int(fraction * 100):03d}pct_notional"
        windows: dict[str, dict[str, Any]] = OrderedDict()
        for label, result in base_by_window.items():
            overlay = _overlay_path(
                result=result,
                qqq_rows=qqq_by_window[label],
                notional_fraction=fraction,
            )
            before = _metrics(result)
            after = _metrics_with_overlay(result, overlay)
            windows[label] = {
                "before": before,
                "after": after,
                "delta": _delta(after, before),
                "overlay_total_pnl": overlay["overlay_total_pnl"],
                "overlay_day_count": overlay["overlay_day_count"],
                "core_active_day_count": overlay["core_active_day_count"],
                "overlay_days_sample": overlay["overlay_days"][:12],
            }
        variant_rows[variant] = {
            "notional_fraction": fraction,
            "windows": windows,
            "aggregate": _aggregate(windows),
        }

    best_variant_name, best_variant = max(
        variant_rows.items(),
        key=lambda item: (
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_aggregate = best_variant["aggregate"]
    passed = bool(
        best_aggregate["windows_ev_improved"] == len(WINDOWS)
        and best_aggregate["windows_ev_regressed"] == 0
        and best_aggregate["expected_value_score_delta_sum"] > 0
        and best_aggregate["total_pnl_delta_sum"] > 0
        and best_aggregate["max_drawdown_delta_max"] <= 0.0
        and best_aggregate["min_overlay_day_count"] >= 4
    )
    material = bool(
        (best_aggregate["expected_value_score_delta_pct"] or 0.0) >= 0.10
        or (best_aggregate["total_pnl_delta_pct"] or 0.0) >= 0.05
    )
    if passed and material:
        decision = "promising_replay_only"
    elif passed:
        decision = "directionally_positive_replay_only"
    else:
        decision = "rejected"

    if decision != "rejected":
        decision_rationale = (
            "Directionally positive replay-only: the zero-core-position QQQ "
            "fixed-notional overlay improved EV and PnL in all three canonical "
            "windows with no drawdown worsening. The aggregate uplift is below "
            "strong Gate 4 materiality and the touched sample is small, so this "
            "must not be routed to live/default orders without a shared adapter, "
            "cash/risk budget semantics, and forward replacement-value evidence."
        )
        rejection_reason = None
    else:
        decision_rationale = (
            "Rejected: the zero-core-position QQQ overlay failed the three-window "
            "EV/PnL/drawdown gate."
        )
        rejection_reason = decision_rationale

    before_metrics = {
        label: _metrics(result)
        for label, result in base_by_window.items()
    }
    after_metrics = {
        label: row["after"]
        for label, row in best_variant["windows"].items()
    }
    deltas = {
        label: row["delta"]
        for label, row in best_variant["windows"].items()
    }

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "zero_position_benchmark_overlay_allocation",
        "hypothesis": (
            "When the refreshed accepted A/B stack has no active core positions, "
            "a fixed-notional QQQ overlay gated by prior-close QQQ 200-day trend "
            "and 20-day momentum may reduce idle-period opportunity cost without "
            "displacing stock alpha or scarce slots."
        ),
        "change_type": "replay_only_zero_position_qqq_overlay",
        "single_causal_variable": (
            "QQQ overlay is allowed only on zero active core-position days; "
            "entries, exits, ranking, sizing, add-ons, LLM/news, universe, and "
            "core A/B trades stay locked."
        ),
        "alpha_hypothesis": {
            "category": "capital_allocation/risk_allocation",
            "playbook_alignment": (
                "Tests meta-allocation/regime routing after LLM soft-ranking, "
                "SEC filing-shock, platform RS20, and same-sample event-stack "
                "retunes are blocked or saturated."
            ),
        },
        "historical_experiment_check": {
            "exp-20260417-003": (
                "Passive SPY overlay was rejected in planning; this run uses the "
                "current three-window protocol and remains replay-only."
            ),
            "exp-20260425-025": (
                "QQQ as a stock-style idle-slot sleeve failed; this run does not "
                "create ATR/stop/target QQQ trades."
            ),
            "exp-20260425-026": (
                "Broad idle-cash QQQ overlay damaged mid_weak; this retry changes "
                "the timing discriminator to zero active core positions only and "
                "uses the refreshed accepted stack."
            ),
        },
        "parameters": {
            "overlay_ticker": OVERLAY_TICKER,
            "state_gate": (
                "prior close > prior 200-day SMA and prior 20-day return > 0"
            ),
            "notional_fraction_variants": NOTIONAL_FRACTIONS,
            "best_variant": best_variant_name,
            "best_notional_fraction": best_variant["notional_fraction"],
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
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": deltas,
            "aggregate": best_aggregate,
        },
        "expected_value_score_delta": best_aggregate["expected_value_score_delta_sum"],
        "gate3": {
            "survival_rates": {
                label: before_metrics[label]["survival_rate"]
                for label in WINDOWS
            },
            "new_filter_added": False,
            "note": "No signal filter or candidate filter was added; survival is unchanged.",
        },
        "gate4": {
            "passed_directionally": passed,
            "strong_materiality_passed": material,
            "basis": "Three canonical backtesting.md windows using the same snapshots.",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this alpha is deterministic "
                "capital allocation and does not depend on LLM replay."
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
                "cash/risk-budget semantics, explicit QQQ overlay order handling, "
                "and parity tests before any order path changes."
            ),
        },
        "risk_of_change": (
            "The best replay touches only a small number of zero-position days and "
            "uses fixed notional, not actual available cash. Treat as a forward "
            "paper hypothesis, not a production allocation rule."
        ),
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_action": (
            "Track zero-position benchmark overlay opportunities forward with "
            "same-day cash/risk context before building a trade-enabled adapter."
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

    payload = {
        **log_record,
        "variants": variant_rows,
    }
    return payload


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["parameters"]["best_variant"]
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Zero-position QQQ Overlay",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Best variant",
        "",
        f"- Variant: `{best}`",
        f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']}`",
        f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']}`",
        f"- Windows improved/regressed: `{aggregate['windows_ev_improved']}` / `{aggregate['windows_ev_regressed']}`",
        f"- Overlay days: `{aggregate['overlay_day_count_sum']}` total, min `{aggregate['min_overlay_day_count']}` per window",
        "",
        "## Three-window best-variant deltas",
        "",
        "| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["variants"][best]["windows"].items():
        delta = row["delta"]
        lines.append(
            "| {label} | {ev:.4f} | ${pnl:.2f} | {ret:.4f} | {sharpe:.2f} | {dd:.4f} | {days} |".format(
                label=label,
                ev=delta["expected_value_score"],
                pnl=delta["total_pnl"],
                ret=delta["strategy_total_return_pct"],
                sharpe=delta["sharpe_daily"],
                dd=delta["max_drawdown_pct"],
                days=row["overlay_day_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production impact",
            "",
            "- Replay-only; no live/default orders changed.",
            "- Any positive follow-up needs shared run/backtester cash/risk-budget semantics and parity tests.",
            "- `cash_usd` is currently not populated in open positions, so this is fixed-notional research, not production cash sizing.",
            "",
            "## Historical guardrail",
            "",
            "This is not a retry of QQQ as a stock-style ATR sleeve. It changes the timing discriminator to zero active core positions only and keeps all A/B trades locked.",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    log_record = {k: v for k, v in payload.items() if k != "variants"}
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, log_record)
    _write_artifact(payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, log_record)
    print(
        f"{EXPERIMENT_ID} {payload['decision']} "
        f"best={payload['parameters']['best_variant']} "
        f"EV_delta={payload['expected_value_score_delta']}"
    )


if __name__ == "__main__":
    main()
