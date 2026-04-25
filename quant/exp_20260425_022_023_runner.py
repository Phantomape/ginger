"""exp-20260425-022/023 rejected residual allocation probes.

Runtime-only alpha search after the accepted A+B residual sizing stack.

Probes:
    022: trend_long | Commodities at 0.25x / 0x risk.
    023: breakout_long | Financials at 0.25x / 0x risk.

No production trading code is changed by this runner.
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

EXPERIMENTS = OrderedDict([
    ("exp_20260425_022", {
        "hypothesis": (
            "trend_long Commodities may be a residual post-stack allocation "
            "leak distinct from the accepted low-TQS commodity breakout exemption"
        ),
        "match": {"strategy": "trend_long", "sector": "Commodities"},
        "variants": OrderedDict([
            ("baseline", 1.0),
            ("trend_commodities_x025", 0.25),
            ("trend_commodities_x000", 0.0),
        ]),
        "out_json": "data/exp_20260425_022_results.json",
    }),
    ("exp_20260425_023", {
        "hypothesis": (
            "remaining breakout Financials exposure may still waste risk after "
            "the accepted narrow DTE haircut"
        ),
        "match": {"strategy": "breakout_long", "sector": "Financials"},
        "variants": OrderedDict([
            ("baseline", 1.0),
            ("breakout_financials_x025", 0.25),
            ("breakout_financials_x000", 0.0),
        ]),
        "out_json": "data/exp_20260425_023_results.json",
    }),
])

_state = {
    "match": {},
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


def _matches(sig: dict) -> bool:
    match = _state["match"]
    return (
        sig.get("strategy") == match["strategy"]
        and sig.get("sector") == match["sector"]
    )


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
    multiplier = _state["multiplier"]

    for sig in sized:
        if not _matches(sig):
            continue
        _state["eligible_signals"] += 1
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
        new_sizing["exp_residual_probe_multiplier_applied"] = multiplier
        sig["sizing"] = new_sizing
        _state["adjusted_signals"] += 1

    return sized


def _install_patches():
    global _original_size_signals
    _original_size_signals = pe_module.size_signals
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    pe_module.size_signals = _original_size_signals


def _run_window(universe, label, cfg, variant_name, multiplier):
    _state["multiplier"] = multiplier
    _state["eligible_signals"] = 0
    _state["adjusted_signals"] = 0
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    ).run()
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant_name,
        "multiplier": multiplier,
        "eligible_signals": _state["eligible_signals"],
        "adjusted_signals": _state["adjusted_signals"],
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
    }


def main() -> int:
    universe = get_universe()
    _install_patches()
    try:
        for exp_id, exp_cfg in EXPERIMENTS.items():
            _state["match"] = exp_cfg["match"]
            rows = []
            for label, window_cfg in WINDOWS.items():
                for variant_name, multiplier in exp_cfg["variants"].items():
                    row = _run_window(universe, label, window_cfg, variant_name, multiplier)
                    rows.append(row)
                    print(
                        f"[{exp_id} {label} {variant_name}] "
                        f"EV={row['expected_value_score']} "
                        f"ret={row['total_return_pct']} "
                        f"sharpe_d={row['sharpe_daily']} "
                        f"dd={row['max_drawdown_pct']} "
                        f"trades={row['trade_count']} "
                        f"eligible={row['eligible_signals']} "
                        f"adjusted={row['adjusted_signals']}"
                    )

            out_path = os.path.join(REPO_ROOT, exp_cfg["out_json"])
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "experiment_id": exp_id.replace("_", "-"),
                        "hypothesis": exp_cfg["hypothesis"],
                        "match": exp_cfg["match"],
                        "results": rows,
                    },
                    f,
                    indent=2,
                )
            print(f"Wrote {out_path}")
    finally:
        _remove_patches()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
