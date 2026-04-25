"""exp-20260425-024 residual cluster audit and runtime sizing probes.

This runner starts from the current accepted A+B stack and does not change
production logic. It emits a fresh fixed-window trade audit, then screens one
candidate residual allocation rule if a replayable cluster is present.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine as pe_module  # noqa: E402


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])

VARIANTS = OrderedDict([
    ("baseline", {"multiplier": 1.0}),
    ("trend_healthcare_late_dte_025", {"multiplier": 0.25}),
    ("trend_healthcare_late_dte_000", {"multiplier": 0.0}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_024_results.json")
AUDIT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_024_trade_audit.json")

_state = {
    "multiplier": 1.0,
    "eligible_signals": 0,
    "adjusted_signals": 0,
}


def _zero_risk_sizing(portfolio_value, entry_price, stop_price, base_risk_pct):
    return {
        "portfolio_value_usd": round(portfolio_value, 2),
        "risk_pct": 0.0,
        "risk_amount_usd": 0.0,
        "entry_price": round(entry_price, 2),
        "stop_price": round(stop_price, 2),
        "risk_per_share": round(entry_price - stop_price, 2),
        "net_risk_per_share": round(
            (entry_price - stop_price)
            + entry_price * pe_module.ROUND_TRIP_COST_PCT
            + entry_price * pe_module.EXEC_LAG_PCT,
            4,
        ),
        "shares_to_buy": 0,
        "position_value_usd": 0.0,
        "position_pct_of_portfolio": 0.0,
        "base_risk_pct": base_risk_pct,
    }


def _copy_sizing_metadata(old_sizing: dict, new_sizing: dict):
    for key, value in old_sizing.items():
        if key.endswith("_applied") or key in (
            "base_risk_pct",
            "trade_quality_score",
            "low_tqs_haircut_exempt_sector",
        ):
            new_sizing[key] = value


def _eligible(sig: dict) -> bool:
    if sig.get("strategy") != "trend_long" or sig.get("sector") != "Healthcare":
        return False
    dte = sig.get("days_to_earnings")
    if dte is None or not (60 <= dte <= 75):
        return False
    pct_from_high = sig.get("pct_from_52w_high")
    if pct_from_high is None:
        conditions = sig.get("conditions_met") or {}
        pct_from_high = conditions.get("pct_from_52w_high")
    return pct_from_high is not None and pct_from_high >= -0.01


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)

    for sig in sized:
        if not _eligible(sig):
            continue
        _state["eligible_signals"] += 1
        multiplier = _state["multiplier"]
        if multiplier >= 1.0:
            continue

        sizing = sig.get("sizing")
        entry = sig.get("entry_price")
        stop = sig.get("stop_price")
        if not sizing or entry is None or stop is None:
            continue

        current_signal_risk_pct = sizing.get("risk_pct", 0.0)
        if multiplier <= 0:
            new_sizing = _zero_risk_sizing(
                portfolio_value,
                entry,
                stop,
                sizing.get("base_risk_pct", current_signal_risk_pct),
            )
        else:
            new_sizing = pe_module.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=current_signal_risk_pct * multiplier,
            )
            if not new_sizing:
                continue

        _copy_sizing_metadata(sizing, new_sizing)
        new_sizing["trend_healthcare_late_dte_multiplier_applied"] = multiplier
        sig["sizing"] = new_sizing
        _state["adjusted_signals"] += 1

    return sized


def _install_patches():
    global _original_size_signals
    _original_size_signals = pe_module.size_signals
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    pe_module.size_signals = _original_size_signals


def _run_engine(universe: list[str], label: str, cfg: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    return engine.run()


def _summary(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
    }


def _audit(universe: list[str]) -> dict:
    audit = OrderedDict()
    for label, cfg in WINDOWS.items():
        result = _run_engine(universe, label, cfg)
        audit[label] = {
            "summary": _summary(result),
            "trades": result.get("trades", []),
        }
        print(f"[audit {label}] EV={audit[label]['summary']['expected_value_score']} "
              f"trades={audit[label]['summary']['trade_count']}")
    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)
    return audit


def _run_variant(
    universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict
) -> dict:
    _state["multiplier"] = variant_cfg["multiplier"]
    _state["eligible_signals"] = 0
    _state["adjusted_signals"] = 0

    result = _run_engine(universe, label, cfg)
    summary = _summary(result)
    summary.update({
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant_name,
        "trend_healthcare_late_dte_multiplier": variant_cfg["multiplier"],
        "eligible_trend_healthcare_late_dte_signals": _state["eligible_signals"],
        "adjusted_trend_healthcare_late_dte_signals": _state["adjusted_signals"],
    })
    return summary


def main() -> int:
    universe = get_universe()
    _audit(universe)

    _install_patches()
    try:
        results = []
        for label, cfg in WINDOWS.items():
            for variant_name, variant_cfg in VARIANTS.items():
                summary = _run_variant(universe, label, cfg, variant_name, variant_cfg)
                print(
                    f"[{label} {variant_name}] "
                    f"EV={summary['expected_value_score']} "
                    f"ret={summary['total_return_pct']} "
                    f"sharpe_d={summary['sharpe_daily']} "
                    f"dd={summary['max_drawdown_pct']} "
                    f"trades={summary['trade_count']} "
                    f"eligible={summary['eligible_trend_healthcare_late_dte_signals']} "
                    f"adjusted={summary['adjusted_trend_healthcare_late_dte_signals']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "trend_healthcare_late_dte_near_high_probe",
                    "definition": (
                        "apply a sleeve-specific risk multiplier only when "
                        "strategy == trend_long, sector == Healthcare, "
                        "60 <= days_to_earnings <= 75, and "
                        "pct_from_52w_high >= -0.01"
                    ),
                    "goal": (
                        "test whether the remaining Healthcare trend old-thin "
                        "loss is a replayable late-DTE near-high exhaustion pocket"
                    ),
                },
                "variants": VARIANTS,
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nWrote {AUDIT_JSON}")
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
