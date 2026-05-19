"""exp-20260511-110: Space official-catalyst breakout stop width.

Tests whether the default-off Space official-catalyst breakout sleeve should
use a wider initial stop than the generic 1.5 ATR breakout stop. The replay
keeps candidate pool, ranking, risk scalars, trend targets, add-ons, LLM/news,
and live slots locked.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ID = "exp-20260511-110"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402
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
            "accepted exp-20260511-105 semantics: Space breakouts keep the "
            "generic 1.5 ATR stop"
        ),
        "space_breakout_stop_atr_mult": 1.5,
    },
    "breakout_stop_2_0": {
        "description": (
            "only official Space breakout_long signals use a 2.0 ATR stop; "
            "targets, risk scalars, trend targets, and entries stay fixed"
        ),
        "space_breakout_stop_atr_mult": 2.0,
    },
    "breakout_stop_2_5": {
        "description": (
            "only official Space breakout_long signals use a 2.5 ATR stop; "
            "targets, risk scalars, trend targets, and entries stay fixed"
        ),
        "space_breakout_stop_atr_mult": 2.5,
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
        return {"passed": False, "path": str(path.relative_to(PROJECT_ROOT)), "missing": "file"}
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


def _restop_signal_with_atr_mult(signal: dict, atr: float, stop_mult: float) -> dict:
    entry = float(signal["entry_price"])
    target = float(signal["target_price"])
    stop = max(0.01, round(entry - stop_mult * atr, 2))
    risk_per_share = round(entry - stop, 2)
    reward_per_share = round(target - entry, 2)
    rr_ratio = (
        round(reward_per_share / risk_per_share, 2)
        if risk_per_share > 0
        else None
    )

    cost_per_share = round(entry * risk_engine.ROUND_TRIP_COST_PCT, 4)
    net_reward = reward_per_share - cost_per_share
    net_risk = risk_per_share + cost_per_share
    net_rr_ratio = (
        round(net_reward / net_risk, 2)
        if net_risk > 0 and net_reward > 0
        else None
    )

    adj_entry = round(entry * (1 + risk_engine.EXEC_LAG_PCT), 2)
    adj_reward = round(target - adj_entry, 2)
    adj_risk = round(adj_entry - stop, 2)
    adj_net_cost = round(adj_entry * risk_engine.ROUND_TRIP_COST_PCT, 4)
    exec_lag_adj_rr = (
        round((adj_reward - adj_net_cost) / (adj_risk + adj_net_cost), 2)
        if adj_risk > 0 and adj_reward > adj_net_cost
        else None
    )

    return {
        **signal,
        "stop_price": stop,
        "risk_per_share": risk_per_share,
        "reward_per_share": reward_per_share,
        "risk_reward_ratio": rr_ratio,
        "net_risk_reward_ratio": net_rr_ratio,
        "exec_lag_adj_net_rr": exec_lag_adj_rr,
        "gap_vulnerability_pct": _round(risk_per_share / entry, 4),
        "space_breakout_stop_atr_mult": stop_mult,
        "stop_width_applied": stop_mult,
    }


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


def _rounded_bucket(bucket: dict[str, dict]) -> dict[str, dict]:
    return {
        key: {**row, "pnl": _round(row["pnl"], 2)}
        for key, row in sorted(bucket.items())
    }


def _install_space_policy(space_breakout_stop_mult: float):
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals

    def enrich_wrapper(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        adjusted = []
        for signal in enriched:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            features = features_dict.get(ticker) or {}
            atr = features.get("atr")
            if ticker in OFFICIAL_SPACE_TICKERS and strategy == "trend_long" and atr:
                target_mult = BASE_SPACE_TREND_TARGET_ATR_MULT
                if ticker in LAUNCH_CONNECTIVITY_TICKERS:
                    target_mult = LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
                updated = risk_engine._retarget_signal_with_atr_mult(
                    signal,
                    atr,
                    target_mult,
                )
                updated["space_trend_target_scope"] = (
                    "accepted_exp105_target_semantics"
                )
                updated["space_trend_target_atr_mult"] = target_mult
                adjusted.append(updated)
            elif (
                ticker in OFFICIAL_SPACE_TICKERS
                and strategy == "breakout_long"
                and atr
            ):
                updated = _restop_signal_with_atr_mult(
                    signal,
                    float(atr),
                    space_breakout_stop_mult,
                )
                adjusted.append(updated)
            else:
                adjusted.append(signal)
        return adjusted

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = original_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in OFFICIAL_SPACE_TICKERS and sizing:
                scalar = BASE_SPACE_RISK_SCALAR
                if ticker in DATA_VENDOR_TICKERS and strategy == "breakout_long":
                    scalar *= DATA_VENDOR_BREAKOUT_RISK_SCALAR
                if (
                    ticker in LAUNCH_CONNECTIVITY_TICKERS
                    and strategy == "trend_long"
                ):
                    scalar *= LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
                old_shares = int(sizing.get("shares_to_buy") or 0)
                new_shares = int(math.floor(old_shares * scalar))
                entry = float(signal.get("entry_price") or sizing.get("entry_price") or 0)
                net_risk = float(sizing.get("net_risk_per_share") or 0)
                sizing["space_base_risk_scalar_applied"] = BASE_SPACE_RISK_SCALAR
                sizing["space_extra_risk_scalar_applied"] = _round(
                    scalar / BASE_SPACE_RISK_SCALAR,
                    6,
                )
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

    risk_engine.enrich_signals = enrich_wrapper
    portfolio_engine.size_signals = size_wrapper
    return original_enrich, original_size


def _restore_policy(original_enrich, original_size):
    risk_engine.enrich_signals = original_enrich
    portfolio_engine.size_signals = original_size


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


def _run_variant(name: str, stop_mult: float) -> dict:
    core_universe = get_universe()
    universe = sorted(set(core_universe) | set(OFFICIAL_SPACE_TICKERS))
    original_enrich, original_size = _install_space_policy(stop_mult)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
            }
    finally:
        _restore_policy(original_enrich, original_size)
    metrics_by_window = {
        label: row["metrics"]
        for label, row in by_window.items()
    }
    return {
        "variant": name,
        "space_breakout_stop_atr_mult": stop_mult,
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _run_core_baseline() -> dict:
    universe = get_universe()
    by_window = {}
    for label, window in WINDOWS.items():
        result = _run_window(window, universe, "core_snapshot")
        by_window[label] = _metrics(result)
    return {
        "by_window": by_window,
        "aggregate": _aggregate(by_window),
    }


def _gate(variant: dict, before: dict, core: dict) -> dict:
    before_aggregate = before["aggregate"]
    variant_aggregate = variant["aggregate"]
    core_aggregate = core["aggregate"]
    by_window_deltas = {}
    improved = 0
    regressed = 0
    for label, row in variant["by_window"].items():
        after_metrics = row["metrics"]
        before_metrics = before["by_window"][label]["metrics"]
        delta = _delta(after_metrics, before_metrics)
        by_window_deltas[label] = delta
        if delta.get("expected_value_score", 0) > 0:
            improved += 1
        elif delta.get("expected_value_score", 0) < 0:
            regressed += 1
    aggregate_delta = _aggregate_delta(variant_aggregate, before_aggregate)
    aggregate_delta_vs_core = _aggregate_delta(variant_aggregate, core_aggregate)
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and improved >= 2
        and regressed == 0
        and aggregate_delta["max_drawdown_pct_max"] <= 0.005
        and variant_aggregate["min_survival_rate"] >= 0.05
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_deltas,
        "windows_ev_improved_vs_before": improved,
        "windows_ev_regressed_vs_before": regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
    }


def _ticket(payload: dict) -> dict:
    best = payload["best_variant"]
    gate = best["gate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Space breakout stop width",
        "status": payload["decision"],
        "decision": payload["decision"],
        "best_variant": best["variant"],
        "expected_value_score_delta_vs_before": gate[
            "aggregate_delta_vs_before"
        ]["expected_value_score_sum"],
        "gate4": gate,
        "summary": payload["decision_rationale"],
    }


def _artifact_markdown(payload: dict) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Space Breakout Stop Width",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Single variable: official Space `breakout_long` stop ATR multiple.",
        "",
        "| Variant | Window | EV | EV delta vs accepted | PnL delta vs accepted | Trades | Max DD | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    before = payload["before_variant"]
    for name, variant in payload["variants"].items():
        for label, row in variant["by_window"].items():
            metrics = row["metrics"]
            delta = _delta(metrics, before["by_window"][label]["metrics"])
            lines.append(
                f"| {name} | {label} | {metrics['expected_value_score']:.4f} | "
                f"{delta.get('expected_value_score', 0):+.4f} | "
                f"{delta.get('total_pnl', 0):+,.2f} | {metrics['trade_count']} | "
                f"{metrics['max_drawdown_pct']:.4f} | {metrics['survival_rate']:.4f} |"
            )
    best = payload["best_variant"]
    best_delta = best["gate"]["aggregate_delta_vs_before"]
    lines.extend(
        [
            "",
            "## Best Variant",
            "",
            f"- Best variant: `{best['variant']}`",
            f"- Aggregate EV delta vs accepted: `{best_delta['expected_value_score_sum']:+.4f}`",
            f"- Aggregate PnL delta vs accepted: `${best_delta['total_pnl_sum']:+,.2f}`",
            f"- Gate 4 passed: `{best['gate']['passed']}`",
            "",
            "## Interpretation",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Default-off Space replay. Live Space slots remain zero; no core production orders, ranking, signal generation, or live sizing changed.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    print(f"{EXPERIMENT_ID}: running core baseline")
    core = _run_core_baseline()

    variants = {}
    for name, spec in VARIANTS.items():
        print(f"{EXPERIMENT_ID}: running {name}")
        variants[name] = _run_variant(
            name,
            spec["space_breakout_stop_atr_mult"],
        )

    before = variants["accepted_exp105_stack"]
    for name, variant in variants.items():
        variant["description"] = VARIANTS[name]["description"]
        variant["gate"] = _gate(variant, before, core)

    candidates = [
        variant for name, variant in variants.items()
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
        "accepted_default_off_space_breakout_stop_width"
        if accepted
        else "rejected_space_breakout_stop_width"
    )
    decision_rationale = (
        "Wider official Space breakout stops improved the accepted Space stack "
        "in at least two canonical windows without EV regression or unacceptable "
        "drawdown/survival damage."
        if accepted
        else (
            "Wider official Space breakout stops did not beat the accepted "
            "exp-105 Space stack under the three-window gate. Space breakout "
            "fragility is not solved by simply giving breakouts more stop room."
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "exit_stop_shadow_sweep",
        "changed_variable": "space_official_breakout_stop_atr_mult",
        "single_causal_variable": (
            "initial stop ATR multiple for official-catalyst Space breakout_long "
            "signals inside the default-off Space sleeve"
        ),
        "hypothesis": (
            "Official-catalyst Space breakout losses may be ordinary volatility "
            "shakeouts caused by the generic 1.5 ATR stop. A wider breakout stop "
            "could improve EV while the existing Space risk scalars keep notional "
            "bounded."
        ),
        "gate_questions": {
            "alpha_hypothesis": (
                "Exit/risk allocation: widen only the official Space breakout "
                "initial stop while keeping Space trend target, risk, pool, and "
                "ranking locked."
            ),
            "prior_similar_experiments": [
                "exp-20260511-015 rejected simple Space breakout entry-to-stop risk-distance caps.",
                "exp-20260511-022 rejected applying the PL/BKSY breakout haircut to non-data-vendor breakouts.",
                "exp-20260511-028 rejected a separate RKLB/ASTS breakout risk scalar.",
                "exp-20260511-037 rejected wider official Space breakout targets.",
                "No prior Space run isolated breakout stop ATR width itself.",
            ],
            "single_causal_variable": (
                "Only the Space breakout stop ATR multiple changes; target widths, "
                "risk scalars, entries, ranking, exits other than stop level, "
                "candidate pool, add-ons, LLM/news, and live slots stay locked."
            ),
            "acceptance_standard": (
                "Must improve aggregate EV and PnL versus exp-105, improve EV "
                "in at least two windows with no EV regression, keep max "
                "drawdown drift <= 0.5 pp, and survival >= 5%."
            ),
            "reproducibility": (
                "This script reruns core, accepted exp-105 Space stack, and "
                "2.0/2.5 ATR Space breakout stop variants across the three "
                "docs/backtesting.md fixed snapshots."
            ),
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Core uses canonical "
            "snapshots; Space variants use the same exp-20260510-028 augmented "
            "snapshots. The accepted_before variant reproduces exp-20260511-105 "
            "policy semantics."
        ),
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["space_snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "parameters": {
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "data_vendor_breakout_risk_scalar": DATA_VENDOR_BREAKOUT_RISK_SCALAR,
            "launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "base_space_trend_target_atr_mult": BASE_SPACE_TREND_TARGET_ATR_MULT,
            "launch_connectivity_trend_target_atr_mult": (
                LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
            ),
            "tested_space_breakout_stop_atr_mult": [1.5, 2.0, 2.5],
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "locked_variables": [
                "official Space candidate pool",
                "Space base risk scalar",
                "PL/BKSY breakout scalar",
                "RKLB/ASTS trend risk scalar",
                "RKLB/ASTS trend target",
                "all Space trend targets",
                "breakout target width",
                "core universe",
                "core signal generation",
                "core ranking",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three-window fixed snapshots",
            "core_baseline_metrics": core["by_window"],
            "accepted_before_metrics": {
                label: row["metrics"] for label, row in before["by_window"].items()
            },
        },
        "gate2": gate2,
        "gate3": {
            "new_core_filter_added": False,
            "min_survival_rate": before["aggregate"]["min_survival_rate"],
            "passed": before["aggregate"]["min_survival_rate"] >= 0.05,
        },
        "core_baseline": core,
        "before_variant": before,
        "variants": variants,
        "best_variant": best_variant,
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
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space event-state forward data is still below the closed-decision "
                "gate; this run uses deterministic OHLCV stop-width replay."
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
        "decision_rationale": decision_rationale,
        "rejection_reason": None if accepted else decision_rationale,
        "next_evidence_needed": (
            "If rejected, do not retry nearby Space breakout stop widths on the "
            "same frozen snapshots; future work needs forward replacement value "
            "or a genuinely new official catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260511_110_space_breakout_stop_width.py",
            "data/experiments/exp-20260511-110/space_breakout_stop_width.json",
            "experiments/logs/exp-20260511-110.json",
            "experiments/tickets/exp-20260511-110.json",
            "experiments/artifacts/exp-20260511-110_space_breakout_stop_width.md",
            "docs/experiment_log.jsonl",
        ],
    }


def persist(payload: dict) -> None:
    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / "space_breakout_stop_width.json"
    log_path = PROJECT_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = PROJECT_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        PROJECT_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_space_breakout_stop_width.md"
    )
    jsonl_path = PROJECT_ROOT / "docs" / "experiment_log.jsonl"
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(jsonl_path, payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"]["variant"],
                    "best_gate": payload["best_variant"]["gate"],
                    "artifact": (
                        "data/experiments/exp-20260511-110/"
                        "space_breakout_stop_width.json"
                    ),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
