from __future__ import annotations

import json
import logging
import math
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ID = "exp-20260511-105"
ROOT = Path(__file__).resolve().parents[3]
QUANT_DIR = ROOT / "quant"
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

VARIANTS = {
    "accepted_5_0": {
        "description": (
            "accepted exp-20260511-032 target semantics: every official Space "
            "trend_long signal uses the 5 ATR target"
        ),
        "launch_connectivity_trend_target_atr_mult": 5.0,
    },
    "launch_connectivity_6_0": {
        "description": (
            "only RKLB/ASTS launch-connectivity trend_long signals use a 6 ATR "
            "target; all other official Space trend signals stay at 5 ATR"
        ),
        "launch_connectivity_trend_target_atr_mult": 6.0,
    },
    "launch_connectivity_7_0": {
        "description": (
            "only RKLB/ASTS launch-connectivity trend_long signals use a 7 ATR "
            "target; all other official Space trend signals stay at 5 ATR"
        ),
        "launch_connectivity_trend_target_atr_mult": 7.0,
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


def _install_space_policy(launch_connectivity_target_mult: float):
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
                    target_mult = launch_connectivity_target_mult
                updated = risk_engine._retarget_signal_with_atr_mult(
                    signal,
                    atr,
                    target_mult,
                )
                updated["space_trend_target_scope"] = (
                    "launch_connectivity_target_experiment"
                )
                updated["space_trend_target_atr_mult"] = target_mult
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
        ohlcv_snapshot_path=str(ROOT / window[snapshot_key]),
        config={"REPLAY_PARTIAL_REDUCES": True, "REGIME_AWARE_EXIT": True},
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _run_variant(name: str, target_mult: float) -> dict:
    core_universe = get_universe()
    universe = sorted(set(core_universe) | set(OFFICIAL_SPACE_TICKERS))
    original_enrich, original_size = _install_space_policy(target_mult)
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
        "launch_connectivity_trend_target_atr_mult": target_mult,
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


def main() -> int:
    out_dir = ROOT / "data" / "experiments" / EXPERIMENT_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{EXPERIMENT_ID}: running core baseline")
    core = _run_core_baseline()

    variants = {}
    for name, spec in VARIANTS.items():
        print(f"{EXPERIMENT_ID}: running {name}")
        variants[name] = _run_variant(
            name,
            spec["launch_connectivity_trend_target_atr_mult"],
        )

    before = variants["accepted_5_0"]
    for name, variant in variants.items():
        variant["description"] = VARIANTS[name]["description"]
        variant["gate"] = _gate(variant, before, core)

    candidates = [
        variant for name, variant in variants.items()
        if name != "accepted_5_0"
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
    decision = (
        "accepted_default_off_launch_connectivity_trend_target_extension"
        if best_variant["gate"]["passed"]
        else "rejected_launch_connectivity_trend_target_extension"
    )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "hypothesis": (
            "Exit alpha: RKLB/ASTS launch-connectivity Space trend_long winners "
            "may deserve a wider target than the accepted 5 ATR all-official "
            "Space trend target, while RDW/PL/BKSY trend targets stay fixed."
        ),
        "changed_variable": "space_launch_connectivity_trend_target_atr_mult",
        "single_causal_variable": (
            "target ATR multiple for RKLB/ASTS launch-connectivity trend_long "
            "signals inside the default-off official Space sleeve"
        ),
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Core uses canonical "
            "snapshots; Space variants use the same exp-20260510-028 snapshots. "
            "The accepted_before variant reproduces exp-20260511-032 policy semantics."
        ),
        "windows": WINDOWS,
        "parameters": {
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "data_vendor_breakout_risk_scalar": DATA_VENDOR_BREAKOUT_RISK_SCALAR,
            "launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "base_space_trend_target_atr_mult": BASE_SPACE_TREND_TARGET_ATR_MULT,
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "launch_connectivity_tickers": list(LAUNCH_CONNECTIVITY_TICKERS),
            "variants": {
                name: {
                    "description": spec["description"],
                    "launch_connectivity_trend_target_atr_mult": spec[
                        "launch_connectivity_trend_target_atr_mult"
                    ],
                }
                for name, spec in VARIANTS.items()
            },
        },
        "core_baseline": core,
        "before_variant": before,
        "variants": variants,
        "best_variant": best_variant,
        "decision": decision,
        "production_impact": {
            "shared_policy_changed": decision.startswith("accepted"),
            "backtester_adapter_changed": False,
            "run_adapter_changed": decision.startswith("accepted"),
            "replay_only": True,
            "parity_test_added": decision.startswith("accepted"),
            "daily_report_metadata_changed": decision.startswith("accepted"),
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "known_risks": [
            "Space candidate snapshots are frozen historical research copies, so any accepted result remains default-off forward metadata.",
            "Live Space slots remain zero; no production order/ranking/sizing behavior may change from this experiment.",
            "Launch/connectivity target-width evidence still needs forward replacement-value confirmation before trade-enabled promotion.",
        ],
    }

    artifact_path = out_dir / "space_launch_connectivity_trend_target.json"
    artifact_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "best_variant": best_variant["variant"],
        "best_gate": best_variant["gate"],
        "artifact": str(artifact_path.relative_to(ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
