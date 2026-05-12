"""exp-20260511-113: Space one-slot capital allocation cap.

Tests whether the accepted default-off official Space sleeve should be
evaluated as one concurrent Space position instead of allowing multiple
official Space names to overlap. This follows the production observe-only
Space slot shape while keeping pool membership, risk scalars, targets,
ranking, exits, add-ons, LLM/news replay, and live slots locked.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ID = "exp-20260511-113"
STEM = "space_one_slot_cap"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402
import production_parity  # noqa: E402
import risk_engine  # noqa: E402


logging.basicConfig(level=logging.WARNING)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "core_snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "space_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_late_strong_with_space_catalyst.json"
        ),
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "core_snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "space_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_mid_weak_with_space_catalyst.json"
        ),
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "core_snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "space_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_old_thin_with_space_catalyst.json"
        ),
    },
}

OFFICIAL_SPACE_TICKERS = ("ASTS", "BKSY", "LUNR", "PL", "RDW", "RKLB")
DATA_VENDOR_TICKERS = ("BKSY", "PL")
LAUNCH_CONNECTIVITY_TICKERS = ("ASTS", "RKLB")
BASE_SPACE_RISK_SCALAR = 0.75
DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.1
LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
BASE_SPACE_TREND_TARGET_ATR_MULT = 5.0
LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT = 7.0

VARIANTS = {
    "accepted_exp105_stack": {
        "description": (
            "accepted exp-20260511-105 semantics with no separate Space "
            "concurrent-position cap"
        ),
        "space_slot_cap": None,
    },
    "space_one_slot_cap": {
        "description": (
            "allow at most one official Space position at a time; when no "
            "Space position is open, keep only the top-ranked Space signal "
            "before normal shared slot routing"
        ),
        "space_slot_cap": 1,
    },
}


def _round(value, digits=4):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe(value):
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"), 4
        ),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _delta(after: dict, before: dict) -> dict:
    keys = (
        "expected_value_score",
        "strategy_total_return_pct",
        "sharpe_daily",
        "total_pnl",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "worst_trade_pct",
        "tail_loss_share",
    )
    out = {}
    for key in keys:
        after_value = after.get(key)
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = _round(
                after_value - before_value,
                2 if key == "total_pnl" else 4,
            )
    return out


def _aggregate(metrics_by_window: dict[str, dict]) -> dict:
    values = list(metrics_by_window.values())
    return {
        "expected_value_score_sum": _round(
            sum(row.get("expected_value_score") or 0 for row in values), 4
        ),
        "total_pnl_sum": _round(
            sum(row.get("total_pnl") or 0 for row in values), 2
        ),
        "trade_count_sum": int(sum(row.get("trade_count") or 0 for row in values)),
        "signals_generated_sum": int(
            sum(row.get("signals_generated") or 0 for row in values)
        ),
        "signals_survived_sum": int(
            sum(row.get("signals_survived") or 0 for row in values)
        ),
        "min_survival_rate": _round(
            min(row.get("survival_rate") or 0 for row in values), 4
        ),
        "max_drawdown_pct_max": _round(
            max(row.get("max_drawdown_pct") or 0 for row in values), 4
        ),
    }


def _aggregate_delta(after: dict, before: dict) -> dict:
    return {
        "expected_value_score_sum": _round(
            after["expected_value_score_sum"] - before["expected_value_score_sum"],
            4,
        ),
        "total_pnl_sum": _round(
            after["total_pnl_sum"] - before["total_pnl_sum"],
            2,
        ),
        "trade_count_sum": after["trade_count_sum"] - before["trade_count_sum"],
        "signals_generated_sum": (
            after["signals_generated_sum"] - before["signals_generated_sum"]
        ),
        "signals_survived_sum": (
            after["signals_survived_sum"] - before["signals_survived_sum"]
        ),
        "min_survival_rate": _round(
            after["min_survival_rate"] - before["min_survival_rate"], 4
        ),
        "max_drawdown_pct_max": _round(
            after["max_drawdown_pct_max"] - before["max_drawdown_pct_max"], 4
        ),
    }


def _gate2_open_positions() -> dict:
    path = PROJECT_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "passed": False,
            "path": str(path.relative_to(PROJECT_ROOT)),
            "missing": "file",
        }
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    positions = list(payload.get("positions") or []) + list(payload.get("observations") or [])
    missing = [
        row.get("ticker") or "<unknown>"
        for row in positions
        if not row.get("entry_date") or row.get("target_price") in (None, "")
    ]
    return {
        "passed": not missing,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
    }


def _retarget_if_space_trend(signal: dict, features_dict: dict) -> dict:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "")
    if ticker not in OFFICIAL_SPACE_TICKERS or strategy != "trend_long":
        return signal
    atr = (features_dict.get(ticker) or {}).get("atr")
    if not atr:
        return signal
    target_mult = BASE_SPACE_TREND_TARGET_ATR_MULT
    if ticker in LAUNCH_CONNECTIVITY_TICKERS:
        target_mult = LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
    updated = risk_engine._retarget_signal_with_atr_mult(
        signal,
        atr,
        target_mult,
    )
    updated["space_trend_target_scope"] = "accepted_exp105_target_semantics"
    updated["space_trend_target_atr_mult"] = target_mult
    return updated


def _space_effective_risk_scalar(ticker: str, strategy: str) -> float:
    ticker = str(ticker or "").upper()
    strategy = str(strategy or "")
    scalar = BASE_SPACE_RISK_SCALAR
    if ticker in DATA_VENDOR_TICKERS and strategy == "breakout_long":
        scalar *= DATA_VENDOR_BREAKOUT_RISK_SCALAR
    if ticker in LAUNCH_CONNECTIVITY_TICKERS and strategy == "trend_long":
        scalar *= LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
    return scalar


def _summarize_signal(sig: dict) -> dict:
    return {
        "ticker": str(sig.get("ticker") or "").upper(),
        "strategy": sig.get("strategy"),
        "trade_quality_score": _round(sig.get("trade_quality_score"), 4),
        "confidence_score": _round(sig.get("confidence_score"), 4),
        "entry_price": _round(sig.get("entry_price"), 4),
    }


def _install_space_policy(space_slot_cap: int | None):
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals
    original_plan = production_parity.plan_entry_candidates

    def enrich_wrapper(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        return [_retarget_if_space_trend(signal, features_dict) for signal in enriched]

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = original_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in OFFICIAL_SPACE_TICKERS and sizing:
                scalar = _space_effective_risk_scalar(ticker, strategy)
                old_shares = int(sizing.get("shares_to_buy") or 0)
                new_shares = int(math.floor(old_shares * scalar))
                entry = float(signal.get("entry_price") or sizing.get("entry_price") or 0)
                net_risk = float(sizing.get("net_risk_per_share") or 0)
                sizing["space_base_risk_scalar_applied"] = BASE_SPACE_RISK_SCALAR
                sizing["space_effective_risk_scalar_applied"] = _round(scalar, 6)
                sizing["space_shares_before_scalar"] = old_shares
                sizing["shares_to_buy"] = new_shares
                sizing["position_value_usd"] = _round(new_shares * entry, 2)
                sizing["position_pct_of_portfolio"] = _round(
                    (new_shares * entry) / portfolio_value
                    if portfolio_value else 0,
                    4,
                )
                sizing["risk_amount_usd"] = _round(new_shares * net_risk, 2)
                sizing["risk_pct"] = (
                    (new_shares * net_risk) / portfolio_value
                    if portfolio_value else 0
                )
                signal = {**signal, "sizing": sizing}
            out.append(signal)
        return out

    def plan_wrapper(signals, open_positions, *args, **kwargs):
        input_signals = list(signals or [])
        if space_slot_cap is None:
            planned, entry_plan = original_plan(
                input_signals,
                open_positions,
                *args,
                **kwargs,
            )
            entry_plan["space_slot_cap"] = None
            entry_plan["space_slot_cap_dropped_signals"] = []
            return planned, entry_plan

        active_space = sum(
            1
            for pos in (open_positions or {}).get("positions", [])
            if str(pos.get("ticker") or "").upper() in OFFICIAL_SPACE_TICKERS
            and (pos.get("shares") or 0) > 0
        )
        remaining_space_slots = max(0, int(space_slot_cap) - active_space)
        kept = []
        dropped = []
        for signal in input_signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in OFFICIAL_SPACE_TICKERS:
                kept.append(signal)
                continue
            if remaining_space_slots > 0:
                kept.append(signal)
                remaining_space_slots -= 1
            else:
                dropped.append(signal)

        planned, entry_plan = original_plan(
            kept,
            open_positions,
            *args,
            **kwargs,
        )
        entry_plan["space_slot_cap"] = space_slot_cap
        entry_plan["space_slot_active_positions"] = active_space
        entry_plan["space_slot_cap_dropped_signals"] = [
            _summarize_signal(signal) for signal in dropped
        ]
        return planned, entry_plan

    risk_engine.enrich_signals = enrich_wrapper
    portfolio_engine.size_signals = size_wrapper
    production_parity.plan_entry_candidates = plan_wrapper
    return original_enrich, original_size, original_plan


def _restore_policy(original_enrich, original_size, original_plan):
    risk_engine.enrich_signals = original_enrich
    portfolio_engine.size_signals = original_size
    production_parity.plan_entry_candidates = original_plan


def _run_window(window: dict, universe: list[str], snapshot_key: str) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(PROJECT_ROOT / window[snapshot_key]),
        config={"REPLAY_PARTIAL_REDUCES": True, "REGIME_AWARE_EXIT": True},
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _run_core_baseline() -> dict:
    universe = get_universe()
    by_window = {}
    for label, window in WINDOWS.items():
        result = _run_window(window, universe, "core_snapshot")
        by_window[label] = _metrics(result)
    return {"by_window": by_window, "aggregate": _aggregate(by_window)}


def _run_variant(name: str, space_slot_cap: int | None) -> dict:
    core_universe = get_universe()
    universe = sorted(set(core_universe) | set(OFFICIAL_SPACE_TICKERS))
    original_enrich, original_size, original_plan = _install_space_policy(space_slot_cap)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
                "entry_execution_attribution": result.get(
                    "entry_execution_attribution"
                ),
            }
    finally:
        _restore_policy(original_enrich, original_size, original_plan)
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "space_slot_cap": space_slot_cap,
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _rounded_bucket(bucket: dict) -> dict:
    out = {}
    for key, row in bucket.items():
        out[key] = {
            **row,
            "pnl": _round(row.get("pnl"), 2),
        }
    return out


def _space_trade_attribution(result: dict) -> dict:
    trades = [
        trade for trade in result.get("trades") or []
        if str(trade.get("ticker") or "").upper() in OFFICIAL_SPACE_TICKERS
    ]
    by_ticker = {}
    by_strategy = {}
    by_exit_reason = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        strategy = str(trade.get("strategy") or "unknown")
        exit_reason = str(trade.get("exit_reason") or "unknown")
        pnl = float(trade.get("pnl") or 0.0)
        for bucket, key in (
            (by_ticker, ticker),
            (by_strategy, strategy),
            (by_exit_reason, exit_reason),
        ):
            row = bucket.setdefault(
                key,
                {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0},
            )
            row["trade_count"] += 1
            row["wins"] += int(pnl > 0)
            row["losses"] += int(pnl <= 0)
            row["pnl"] += pnl
    positive = [row["pnl"] for row in by_ticker.values() if row["pnl"] > 0]
    total_positive = sum(positive)
    return {
        "trade_count": len(trades),
        "wins": sum(1 for trade in trades if (trade.get("pnl") or 0) > 0),
        "losses": sum(1 for trade in trades if (trade.get("pnl") or 0) <= 0),
        "win_rate": (
            _round(
                sum(1 for trade in trades if (trade.get("pnl") or 0) > 0) / len(trades),
                4,
            )
            if trades
            else None
        ),
        "total_pnl": _round(
            sum(float(trade.get("pnl") or 0.0) for trade in trades), 2
        ),
        "single_ticker_positive_share": _round(
            max(positive) / total_positive if total_positive else 0.0,
            4,
        ),
        "by_ticker": _rounded_bucket(by_ticker),
        "by_strategy": _rounded_bucket(by_strategy),
        "by_exit_reason": _rounded_bucket(by_exit_reason),
        "trades": [
            {
                "ticker": str(trade.get("ticker") or "").upper(),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                "shares": trade.get("shares"),
            }
            for trade in trades
        ],
    }


def _gate(variant: dict, before: dict, core: dict) -> dict:
    aggregate_delta = _aggregate_delta(variant["aggregate"], before["aggregate"])
    aggregate_delta_vs_core = _aggregate_delta(variant["aggregate"], core["aggregate"])
    by_window_delta = {
        label: _delta(row["metrics"], before["by_window"][label]["metrics"])
        for label, row in variant["by_window"].items()
    }
    windows_ev_improved = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) > 0
    )
    windows_ev_regressed = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) < 0
    )
    max_drawdown_change = aggregate_delta["max_drawdown_pct_max"]
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] >= 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and max_drawdown_change <= 0.005
        and variant["aggregate"]["min_survival_rate"] >= 0.05
        and variant["aggregate"]["trade_count_sum"] >= 50
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": max_drawdown_change,
    }


def _artifact_markdown(payload: dict) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space one-slot cap",
        "",
        f"- Decision: `{payload['decision']}`",
        "- Single variable: official Space concurrent position cap.",
        f"- Best variant: `{best['variant']}`",
        (
            "- Aggregate EV delta vs accepted: "
            f"`{payload['expected_value_score_delta']:+.4f}`"
        ),
        (
            "- Aggregate PnL delta vs accepted: "
            f"`${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`"
        ),
        "",
        "## Three-Window Comparison",
        "",
        (
            "| Window | Before EV | After EV | dEV | Before PnL | "
            "After PnL | dPnL | Trades | Max DD | Survival |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{before_pnl:,.2f} | {after_pnl:,.2f} | {delta_pnl:+,.2f} | "
            "{trades} | {max_dd:.4f} | {survival:.4f} |".format(
                label=label,
                before_ev=before["expected_value_score"],
                after_ev=after["expected_value_score"],
                delta_ev=delta.get("expected_value_score", 0),
                before_pnl=before["total_pnl"],
                after_pnl=after["total_pnl"],
                delta_pnl=delta.get("total_pnl", 0),
                trades=after["trade_count"],
                max_dd=after["max_drawdown_pct"],
                survival=after["survival_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            (
                "Default-off Space metadata experiment. Live Space slots remain "
                "zero; positive promotion would need the shared Space forward "
                "hypothesis and production observe-only slot metadata to stay "
                "aligned."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _ticket(payload: dict) -> dict:
    best = payload["best_variant"]
    return {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "best_variant": best["variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_sum"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(
            Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
        ),
    }


def run() -> dict:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    core = _run_core_baseline()
    variants = {}
    for name, spec in VARIANTS.items():
        variant = _run_variant(name, spec["space_slot_cap"])
        variant["description"] = spec["description"]
        variants[name] = variant

    before = variants["accepted_exp105_stack"]
    for variant in variants.values():
        variant["gate"] = _gate(variant, before, core)

    candidates = [
        variant
        for name, variant in variants.items()
        if name != "accepted_exp105_stack"
    ]
    best_variant = max(
        candidates,
        key=lambda variant: (
            variant["gate"]["passed"],
            variant["gate"]["aggregate_delta_vs_before"][
                "expected_value_score_sum"
            ],
            variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    accepted = best_variant["gate"]["passed"]
    decision = (
        "accepted_default_off_space_one_slot_cap"
        if accepted
        else "rejected_space_one_slot_cap"
    )
    interpretation = (
        "A one-slot Space cap improved the accepted exp-105 stack across the "
        "three-window gate; promote only as default-off Space forward metadata "
        "because live Space slots remain zero."
        if accepted
        else (
            "The one-slot Space cap did not beat the accepted exp-105 stack. "
            "Space sleeve optimization should not solve overlap by reducing "
            "capacity alone; the next valid direction needs forward catalyst "
            "quality or replacement-value evidence."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "capital_allocation_shadow_replay",
        "changed_variable": "space_official_concurrent_position_cap",
        "single_causal_variable": (
            "maximum concurrent official Space positions inside the default-off "
            "official Space sleeve"
        ),
        "hypothesis": (
            "The accepted Space sleeve may be strongest as a replacement-value "
            "specialist sleeve with one concurrent official Space position. A "
            "one-slot cap could preserve the highest-ranked RKLB/ASTS/PL/RDW "
            "convexity while avoiding intra-theme crowding and weak secondary "
            "Space entries."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: cap the default-off official Space sleeve "
                "to one concurrent Space position."
            ),
            "2_history_check": {
                "exp-20260511-011": (
                    "Accepted official-catalyst Space 0.75x as default-off "
                    "forward hypothesis."
                ),
                "exp-20260511-031": (
                    "Accepted PL/BKSY breakout risk scalar 0.1x."
                ),
                "exp-20260511-032": (
                    "Accepted broad official Space trend target 5 ATR."
                ),
                "exp-20260511-105": (
                    "Accepted RKLB/ASTS launch-connectivity trend target 7 ATR; "
                    "this is the before state."
                ),
                "exp-20260511-110": (
                    "Rejected Space breakout stop widening; this run does not "
                    "change stop/target geometry."
                ),
                "exp-20260511-111": (
                    "Rejected PL/BKSY data-vendor trend target widening; this "
                    "run does not retune bucket targets."
                ),
            },
            "3_single_causal_variable": (
                "space_official_concurrent_position_cap; no target, stop, risk "
                "scalar, ticker pool, ranking score, add-on, LLM/news, or live "
                "slot change."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive "
                "aggregate EV and PnL, EV improvement in at least 2/3 windows "
                "with no EV regression, max drawdown drift <= 0.5 pp, survival "
                ">= 5%, and at least 50 total trades."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-105 Space stack, and "
                "the one-slot cap variant across the three canonical snapshots."
            ),
        },
        "historical_experiment_check": {
            "not_llm_soft_ranking": (
                "Space event-state forward ledger still has too few mature "
                "closed decisions for LLM/event soft ranking."
            ),
            "not_candidate_noise": (
                "No new ticker is added; the test changes only capital allocation "
                "inside the already accepted official operating Space pool."
            ),
            "not_nearby_retune": (
                "Targets, stops, PL/BKSY risk, and RKLB/ASTS trend semantics stay "
                "at accepted exp-105 values."
            ),
        },
        "parameters": {
            "before_space_slot_cap": None,
            "tested_space_slot_cap": 1,
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "data_vendor_breakout_risk_scalar": DATA_VENDOR_BREAKOUT_RISK_SCALAR,
            "launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "base_space_trend_target_atr_mult": BASE_SPACE_TREND_TARGET_ATR_MULT,
            "launch_connectivity_trend_target_atr_mult": (
                LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
            ),
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "locked_variables": [
                "official Space candidate pool",
                "base Space risk scalar",
                "PL/BKSY breakout 0.1x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "all accepted Space trend targets",
                "breakout stop and target widths",
                "core production universe",
                "core signal generation",
                "entry filters other than tested Space cap",
                "ranking",
                "MAX_POSITIONS",
                "exits",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["space_snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Core uses "
            "canonical snapshots; Space variants use the same exp-20260510-028 "
            "augmented snapshots. The accepted_before variant reproduces "
            "exp-20260511-105 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies "
                "built from a 2026-05-10 research universe; accepted changes "
                "remain default-off metadata until forward evidence matures."
            ),
        },
        "gate2": gate2,
        "gate3": {
            "new_core_filter_added": False,
            "space_capacity_gate_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"] >= 0.05,
        },
        "core_baseline_metrics": core["by_window"],
        "core_aggregate": core["aggregate"],
        "before_variant": before,
        "before_metrics": {
            "aggregate": before["aggregate"],
            **{label: row["metrics"] for label, row in before["by_window"].items()},
        },
        "after_metrics": {
            "aggregate": best_variant["aggregate"],
            **{
                label: row["metrics"]
                for label, row in best_variant["by_window"].items()
            },
        },
        "delta_metrics": {
            "aggregate": best_variant["gate"]["aggregate_delta_vs_before"],
            "by_window": best_variant["gate"]["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": best_variant["gate"][
            "aggregate_delta_vs_before"
        ]["expected_value_score_sum"],
        "gate_results": best_variant["gate"],
        "gate4": best_variant["gate"],
        "variants": variants,
        "best_variant": best_variant,
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space event-state forward data is still below the closed-decision "
                "gate; this run uses deterministic capital allocation replay."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": True,
            "parity_test_added": accepted,
            "daily_report_metadata_changed": accepted,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "decision_rationale": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "If rejected, do not retry simple Space slot-capacity caps on the "
            "same frozen snapshots. Future Space work needs forward event "
            "replacement value or a genuinely new catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260511_113_space_one_slot_cap.py",
            "data/experiments/exp-20260511-113/space_one_slot_cap.json",
            "docs/experiments/logs/exp-20260511-113.json",
            "docs/experiments/tickets/exp-20260511-113.json",
            "docs/experiments/artifacts/exp-20260511-113_space_one_slot_cap.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is still data-limited; candidate breadth already "
            "failed for mature satcom; nearby risk, target, and stop geometry "
            "were just tested. This run isolates Space capacity."
        ),
    }
    return payload


def persist(payload: dict) -> None:
    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / f"{STEM}.json"
    log_path = PROJECT_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = PROJECT_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        PROJECT_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{STEM}.md"
    )
    jsonl_path = PROJECT_ROOT / "docs" / "experiment_log.jsonl"
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(jsonl_path, payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "pnl_delta": result["delta_metrics"]["aggregate"]["total_pnl_sum"],
                "gate4_passed": result["gate4"]["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
