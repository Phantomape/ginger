"""exp-20260428-003 Commodity trend target-extension screen.

Hypothesis:
    The prior target-exit re-entry test was inert because the real portfolio
    path produced no incremental fills after exit. If Commodity trend winners
    still contain continuation alpha, the cleaner execution semantic is to
    extend the target before the exit happens. This tests only
    `trend_long | Commodities` target width above the current accepted 7 ATR
    baseline; entries, sizing, add-ons, scarce-slot routing, LLM/news replay,
    and every other exit remain unchanged.

This runner is experiment-only. It monkeypatches risk enrichment at runtime and
does not change production strategy defaults.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import risk_engine as re_module  # noqa: E402


EXPERIMENT_ID = "exp-20260428-003"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_003_commodity_trend_target_extension.json"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("baseline", {"target_mult": None}),
    ("commodity_trend_target_8_0", {"target_mult": 8.0}),
    ("commodity_trend_target_9_0", {"target_mult": 9.0}),
    ("commodity_trend_target_10_0", {"target_mult": 10.0}),
])

BASELINE_CONFIG = {"REGIME_AWARE_EXIT": True}

_state = {"target_mult": None, "eligible": 0, "adjusted": 0}
_original_enrich_signals = None


def _eligible(sig: dict) -> bool:
    return (
        sig.get("strategy") == "trend_long"
        and sig.get("sector") == "Commodities"
    )


def _retarget(sig: dict, target_mult: float) -> dict:
    entry = sig.get("entry_price")
    stop = sig.get("stop_price")
    if entry is None or stop is None or entry <= stop:
        return sig
    atr = (entry - stop) / ATR_STOP_MULT
    target = round(entry + target_mult * atr, 2)
    risk_per_share = round(entry - stop, 2)
    reward_per_share = round(target - entry, 2)
    rr_ratio = (
        round(reward_per_share / risk_per_share, 2)
        if risk_per_share > 0 else None
    )
    return {
        **sig,
        "target_price": target,
        "reward_per_share": reward_per_share,
        "risk_reward_ratio": rr_ratio,
        "target_mult_used": target_mult,
        "target_width_applied": target_mult,
        "commodity_trend_target_extension_applied": target_mult,
    }


def _patched_enrich_signals(signals, features_dict, atr_target_mult=None):
    enriched = _original_enrich_signals(
        signals,
        features_dict,
        atr_target_mult=atr_target_mult,
    )
    target_mult = _state["target_mult"]
    if target_mult is None:
        return enriched

    out = []
    for sig in enriched:
        if not _eligible(sig):
            out.append(sig)
            continue
        _state["eligible"] += 1
        adjusted = _retarget(sig, target_mult)
        if adjusted is not sig:
            _state["adjusted"] += 1
        out.append(adjusted)
    return out


def _install_patch():
    global _original_enrich_signals
    _original_enrich_signals = re_module.enrich_signals
    re_module.enrich_signals = _patched_enrich_signals


def _remove_patch():
    if _original_enrich_signals is not None:
        re_module.enrich_signals = _original_enrich_signals


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def _run_window(universe: list[str], label: str, cfg: dict,
                variant_name: str, variant_cfg: dict) -> dict:
    _state["target_mult"] = variant_cfg["target_mult"]
    _state["eligible"] = 0
    _state["adjusted"] = 0
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=BASELINE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    trades = [
        t for t in result.get("trades", [])
        if t.get("strategy") == "trend_long" and t.get("sector") == "Commodities"
    ]
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant_name,
        "target_mult": variant_cfg["target_mult"],
        "metrics": _metrics(result),
        "eligible_signals": _state["eligible"],
        "adjusted_signals": _state["adjusted"],
        "commodity_trend_trade_count": len(trades),
        "commodity_trend_pnl": round(sum(float(t.get("pnl") or 0.0) for t in trades), 2),
        "commodity_trend_exits": [
            {
                "ticker": t.get("ticker"),
                "entry_date": t.get("entry_date"),
                "exit_date": t.get("exit_date"),
                "exit_reason": t.get("exit_reason"),
                "pnl": round(float(t.get("pnl") or 0.0), 2),
                "pnl_pct_net": t.get("pnl_pct_net"),
                "target_mult_used": t.get("target_mult_used"),
            }
            for t in trades
        ],
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key in before:
        b = before.get(key)
        a = after.get(key)
        out[key] = (
            round(a - b, 6)
            if isinstance(a, (int, float)) and isinstance(b, (int, float))
            else None
        )
    return out


def _summarize(rows: list[dict]) -> dict:
    by_variant = OrderedDict()
    for variant_name in VARIANTS:
        if variant_name == "baseline":
            continue
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                r for r in rows
                if r["window"] == label and r["variant"] == "baseline"
            )
            variant = next(
                r for r in rows
                if r["window"] == label and r["variant"] == variant_name
            )
            by_window[label] = {
                "before": baseline,
                "after": variant,
                "delta": _delta(variant["metrics"], baseline["metrics"]),
            }
        ev_delta_sum = round(
            sum(v["delta"]["expected_value_score"] for v in by_window.values()),
            6,
        )
        pnl_delta_sum = round(
            sum(v["delta"]["total_pnl"] for v in by_window.values()),
            2,
        )
        by_variant[variant_name] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": ev_delta_sum,
                "total_pnl_delta_sum": pnl_delta_sum,
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if (v["delta"]["expected_value_score"] or 0) > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if (v["delta"]["expected_value_score"] or 0) < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
            },
        }
    return by_variant


def main() -> int:
    universe = get_universe()
    rows = []
    _install_patch()
    try:
        for label, cfg in WINDOWS.items():
            for variant_name, variant_cfg in VARIANTS.items():
                row = _run_window(universe, label, cfg, variant_name, variant_cfg)
                metrics = row["metrics"]
                print(
                    f"[{label} {variant_name}] "
                    f"EV={metrics['expected_value_score']} "
                    f"PnL={metrics['total_pnl']} "
                    f"SharpeD={metrics['sharpe_daily']} "
                    f"DD={metrics['max_drawdown_pct']} "
                    f"Trades={metrics['trade_count']} "
                    f"comm_trend_pnl={row['commodity_trend_pnl']} "
                    f"eligible={row['eligible_signals']}"
                )
                rows.append(row)
    finally:
        _remove_patch()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "rejected",
        "decision": "rejected",
        "hypothesis": (
            "Commodity trend target exits may still contain continuation alpha, "
            "but re-entry after exit was inert under production execution. "
            "Extending only `trend_long | Commodities` targets before exit may "
            "capture that continuation without changing entry or allocation rules."
        ),
        "change_type": "alpha_search_exit_sweep",
        "parameters": {
            "single_causal_variable": "trend_long Commodities target width above current 7 ATR",
            "baseline_target_source": "current production TREND_COMMODITIES_TARGET_ATR_MULT = 7.0",
            "tested_target_mults": [8.0, 9.0, 10.0],
            "locked_variables": [
                "entries",
                "position sizing",
                "allocation ranking",
                "LLM/news replay",
                "follow-through add-ons",
                "scarce-slot breakout routing",
                "Technology trend target width",
                "all breakout exits",
                "all non-Commodity trend exits",
            ],
        },
        "prior_related_results": [
            {
                "experiment_id": "exp-20260425-031",
                "decision": "accepted",
                "reason": "7 ATR Commodity trend target width improved convex winner capture.",
            },
            {
                "experiment_id": "exp-20260428-002",
                "decision": "rejected",
                "reason": "Same-ticker post-target re-entry scheduled signals but created 0 incremental trades.",
            },
        ],
        "windows": WINDOWS,
        "variants": VARIANTS,
        "summary": _summarize(rows),
        "results": rows,
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "exit alpha was tested instead."
            ),
        },
        "rejection_reason": (
            "Rejected for production promotion. The best variant, 8 ATR, improved "
            "late_strong and old_thin but regressed mid_weak EV by -0.1035, "
            "Sharpe by -0.25, PnL by -$2,070.56, and drawdown by +0.56 pp; "
            "9/10 ATR materially damaged late_strong and aggregate EV."
        ),
        "next_retry_requires": [
            "Do not keep sweeping nearby Commodity trend targets above 7 ATR.",
            (
                "A valid retry needs a state or event discriminator explaining "
                "when late/old continuation should be held without damaging mid_weak."
            ),
            (
                "Do not use post-target continuation audits alone as production "
                "evidence; require production-path replay."
            ),
        ],
        "strategy_behavior_changed": False,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
