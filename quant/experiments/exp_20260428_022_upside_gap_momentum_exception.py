"""exp-20260428-022 upside-gap momentum exception replay.

Hypothesis:
    The rejected global upside-gap sweep showed the 1.5% cancel threshold is not
    mis-sized globally. The remaining alpha question is narrower: for sleeves
    with already-accepted winner-truncation evidence, an upside next-open gap may
    be momentum confirmation rather than overextension. Test only the eligible
    cohort for an exception to upside-gap cancel; leave the threshold, entries,
    exits, add-ons, adverse-gap cancel, scarce-slot routing, LLM/news replay, and
    earnings unchanged.

This runner is experiment-only. Production behavior should change separately
only if a variant passes the fixed-window Gate 4 check.
"""

from __future__ import annotations

import json
import inspect
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import ADVERSE_GAP_CANCEL_PCT, CANCEL_GAP_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from production_parity import classify_entry_open_cancel  # noqa: E402


EXPERIMENT_ID = "exp-20260428-022"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_022_upside_gap_momentum_exception.json"

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
    ("baseline_no_exception", {"strategy": None, "sectors": []}),
    ("trend_technology_exception", {"strategy": "trend_long", "sectors": ["Technology"]}),
    ("trend_commodity_exception", {"strategy": "trend_long", "sectors": ["Commodities"]}),
    (
        "trend_technology_commodity_exception",
        {"strategy": "trend_long", "sectors": ["Technology", "Commodities"]},
    ),
])


_state = {
    "strategy": None,
    "sectors": set(),
    "exception_count": 0,
    "exception_events": [],
    "pending_sig": None,
}
_original_classifier = backtester.classify_entry_open_cancel

def _eligible(sig: dict | None) -> bool:
    if not sig or _state["strategy"] is None:
        return False
    return (
        sig.get("strategy") == _state["strategy"]
        and sig.get("sector") in _state["sectors"]
    )


def _patched_classifier(
    fill_price,
    signal_entry,
    stop_price=None,
    upside_gap_cancel_pct=None,
    adverse_gap_cancel_pct=ADVERSE_GAP_CANCEL_PCT,
):
    reason = classify_entry_open_cancel(
        fill_price,
        signal_entry,
        stop_price=stop_price,
        upside_gap_cancel_pct=upside_gap_cancel_pct,
        adverse_gap_cancel_pct=adverse_gap_cancel_pct,
    )
    pending_sig = _state.get("pending_sig")
    if reason != "gap_cancel" or not _eligible(pending_sig):
        return reason

    _state["exception_count"] += 1
    _state["exception_events"].append({
        "ticker": pending_sig.get("ticker"),
        "strategy": pending_sig.get("strategy"),
        "sector": pending_sig.get("sector"),
        "fill_price": round(float(fill_price), 4),
        "signal_entry": round(float(signal_entry), 4),
        "gap_pct": round(float(fill_price) / float(signal_entry) - 1.0, 6),
    })
    return None


def _patched_should_cancel_gap(fill_price, signal_entry, sig=None, today=None, ohlcv_all=None):
    reason = _patched_classifier(
        fill_price,
        signal_entry,
        upside_gap_cancel_pct=CANCEL_GAP_PCT,
        adverse_gap_cancel_pct=None,
    )
    return reason == "gap_cancel"


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


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _current_signal_from_stack() -> dict | None:
    frame = inspect.currentframe()
    if frame is None:
        return None
    caller = frame.f_back
    while caller is not None:
        sig = caller.f_locals.get("sig")
        if isinstance(sig, dict):
            return sig
        caller = caller.f_back
    return None


def _run_window(universe: list[str], cfg: dict, variant_cfg: dict) -> dict:

    _state["strategy"] = variant_cfg["strategy"]
    _state["sectors"] = set(variant_cfg["sectors"])
    _state["exception_count"] = 0
    _state["exception_events"] = []

    def with_sig(fill_price, signal_entry, stop_price=None, upside_gap_cancel_pct=None, adverse_gap_cancel_pct=None):
        sig = _current_signal_from_stack()
        original_pending = _state.get("pending_sig")
        _state["pending_sig"] = sig
        try:
            return _patched_classifier(
                fill_price,
                signal_entry,
                stop_price=stop_price,
                upside_gap_cancel_pct=upside_gap_cancel_pct,
                adverse_gap_cancel_pct=adverse_gap_cancel_pct,
            )
        finally:
            _state["pending_sig"] = original_pending

    original_classify = backtester.classify_entry_open_cancel
    original_should = backtester.should_cancel_gap
    backtester.classify_entry_open_cancel = with_sig
    backtester.should_cancel_gap = _patched_should_cancel_gap
    try:
        engine = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        )

        result = engine.run()
    finally:
        backtester.classify_entry_open_cancel = original_classify
        backtester.should_cancel_gap = original_should

    if "error" in result:
        raise RuntimeError(result["error"])
    reason_counts = result.get("entry_execution_attribution", {}).get("reason_counts", {})
    return {
        "metrics": _metrics(result),
        "gap_cancel_count": int(reason_counts.get("gap_cancel", 0) or 0),
        "adverse_gap_down_cancel_count": int(reason_counts.get("adverse_gap_down_cancel", 0) or 0),
        "exception_count": _state["exception_count"],
        "exception_events": list(_state["exception_events"]),
        "entry_reason_counts": reason_counts,
    }


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, variant_cfg in VARIANTS.items():
            result = _run_window(universe, cfg, variant_cfg)
            row = {
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "exception_strategy": variant_cfg["strategy"],
                "exception_sectors": variant_cfg["sectors"],
                **result,
            }
            rows.append(row)
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} trades={m['trade_count']} "
                f"gap_cancels={result['gap_cancel_count']} exceptions={result['exception_count']}"
            )

    summary = OrderedDict()
    for variant in VARIANTS:
        if variant == "baseline_no_exception":
            continue
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                r for r in rows
                if r["window"] == label and r["variant"] == "baseline_no_exception"
            )
            candidate = next(
                r for r in rows
                if r["window"] == label and r["variant"] == variant
            )
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "gap_cancel_count": candidate["gap_cancel_count"],
                "exception_count": candidate["exception_count"],
                "exception_events": candidate["exception_events"],
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": (
                    round(total_pnl_delta / baseline_total_pnl, 6)
                    if baseline_total_pnl else None
                ),
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
                "exception_count": sum(v["exception_count"] for v in by_window.values()),
                "gap_cancel_count": sum(v["gap_cancel_count"] for v in by_window.values()),
            },
        }

    best_variant, best = max(
        summary.items(),
        key=lambda item: item[1]["aggregate"]["expected_value_score_delta_sum"],
    )
    best_agg = best["aggregate"]
    accepted = (
        best_agg["windows_improved"] >= 2
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["expected_value_score_delta_sum"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
        )
        and best_agg["max_drawdown_delta_max"] < 0.01
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": (
            f"promote_{best_variant}" if accepted
            else "do_not_promote_upside_gap_exception"
        ),
        "hypothesis": (
            "For sleeves with accepted winner-truncation evidence, an upside "
            "next-open gap may be momentum confirmation rather than overextension; "
            "a narrow exception to the existing 1.5% upside-gap cancel may improve "
            "EV without changing the global threshold."
        ),
        "change_type": "alpha_search_entry_execution_state_exception",
        "parameters": {
            "single_causal_variable": "upside gap cancel exception cohort",
            "baseline_cancel_gap_pct": CANCEL_GAP_PCT,
            "adverse_gap_cancel_pct": ADVERSE_GAP_CANCEL_PCT,
            "variants": VARIANTS,
            "locked_variables": [
                "CANCEL_GAP_PCT",
                "ADVERSE_GAP_CANCEL_PCT",
                "signal generation",
                "risk sizing",
                "all exits",
                "day-2 follow-through add-on settings",
                "scarce-slot breakout routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "windows": WINDOWS,
        "rows": rows,
        "summary": summary,
        "best_variant": best_variant,
        "best_variant_summary": best,
        "history_guardrails": {
            "does_not_repeat_global_upside_gap_threshold_sweep": True,
            "does_not_repeat_adverse_gap_threshold_sweep": True,
            "does_not_repeat_addon_threshold_tuning": True,
            "does_not_use_llm_soft_ranking_sample": True,
            "does_not_reopen_c_strategy_single_field_repair": True,
        },
        "gate4_basis": (
            "Accepted because the best exception improved majority windows with "
            "no EV-regressing windows and passed EV/PnL materiality."
            if accepted else
            "Rejected because no exception cohort passed multi-window Gate 4."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "entry-execution alpha was tested instead."
            ),
        },
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = run_experiment()
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
