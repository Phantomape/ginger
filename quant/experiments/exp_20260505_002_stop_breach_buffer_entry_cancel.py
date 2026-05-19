"""exp-20260505-002 stop-breach buffer entry-cancel sweep.

Alpha-search experiment. The existing shared execution policy cancels a next-
open entry only when the open is already at or below the signal stop. This
tests one narrowly-scoped entry-execution alpha: whether candidates whose next
open is very close to the stop should also be skipped because the trade has
already lost most of its planned risk budget before entry.

No production or default backtest strategy logic is changed by this script.
If a variant passes Gate 4, promotion must happen by changing the shared
production_parity.classify_entry_open_cancel policy used by both backtester.py
and run.py.
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

import backtester  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-002"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "stop_breach_buffer_entry_cancel.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

BASELINE_VARIANT = "baseline_stop_breach_only"
VARIANTS = OrderedDict(
    [
        (BASELINE_VARIANT, 0.0),
        ("near_stop_10pct_risk_buffer", 0.10),
        ("near_stop_20pct_risk_buffer", 0.20),
        ("near_stop_30pct_risk_buffer", 0.30),
    ]
)


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_payload(payload), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    total_pnl = float(result.get("total_pnl") or 0.0)
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "converged": (result.get("convergence") or {}).get("converged"),
    }


def _patch_stop_buffer(risk_buffer_fraction: float):
    original = backtester.classify_entry_open_cancel

    def patched_classify_entry_open_cancel(
        fill_price,
        signal_entry,
        stop_price=None,
        upside_gap_cancel_pct=None,
        adverse_gap_cancel_pct=None,
    ):
        reason = original(
            fill_price,
            signal_entry,
            stop_price=stop_price,
            upside_gap_cancel_pct=upside_gap_cancel_pct,
            adverse_gap_cancel_pct=adverse_gap_cancel_pct,
        )
        if reason is not None:
            return reason

        if (
            risk_buffer_fraction <= 0
            or fill_price is None
            or signal_entry is None
            or stop_price is None
        ):
            return None

        fill = float(fill_price)
        entry = float(signal_entry)
        stop = float(stop_price)
        risk_per_share = entry - stop
        if risk_per_share <= 0:
            return None

        near_stop_line = stop + risk_buffer_fraction * risk_per_share
        if fill <= near_stop_line:
            return "stop_breach_buffer_cancel"
        return None

    backtester.classify_entry_open_cancel = patched_classify_entry_open_cancel
    return original


def _run_window(
    *,
    universe: list[str],
    window: dict[str, str],
    risk_buffer_fraction: float,
) -> dict[str, Any]:
    original = _patch_stop_buffer(risk_buffer_fraction)
    try:
        result = BacktestEngine(
            universe=universe,
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
    finally:
        backtester.classify_entry_open_cancel = original

    if "error" in result:
        raise RuntimeError(result["error"])

    decision_counts = result.get("entry_execution_attribution", {}).get("reason_counts", {})
    return {
        "metrics": _metrics(result),
        "stop_breach_cancel_count": int(decision_counts.get("stop_breach_cancel", 0) or 0),
        "stop_breach_buffer_cancel_count": int(
            decision_counts.get("stop_breach_buffer_cancel", 0) or 0
        ),
        "entry_reason_counts": decision_counts,
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = _round(after_value - before_value)
        else:
            out[key] = None
    return out


def _accepted_by_gate4(aggregate: dict[str, Any]) -> bool:
    if aggregate["expected_value_score_windows_improved"] < 2:
        return False
    if aggregate["expected_value_score_delta_pct"] is not None:
        if aggregate["expected_value_score_delta_pct"] > 0.10:
            return True
    if aggregate["max_sharpe_daily_delta"] > 0.10:
        return True
    if aggregate["max_drawdown_delta_min"] < -0.01:
        return True
    if aggregate["total_pnl_delta_pct"] is not None and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    return (
        aggregate["trade_count_delta_sum"] > 0
        and aggregate["win_rate_delta_min"] is not None
        and aggregate["win_rate_delta_min"] >= 0
    )


def run_experiment() -> dict[str, Any]:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, risk_buffer_fraction in VARIANTS.items():
            result = _run_window(
                universe=universe,
                window=cfg,
                risk_buffer_fraction=risk_buffer_fraction,
            )
            rows.append(
                {
                    "window": label,
                    "start": cfg["start"],
                    "end": cfg["end"],
                    "snapshot": cfg["snapshot"],
                    "state_note": cfg["state_note"],
                    "variant": variant,
                    "risk_buffer_fraction": risk_buffer_fraction,
                    **result,
                }
            )
            metrics = result["metrics"]
            print(
                f"[{label} {variant}] EV={metrics['expected_value_score']} "
                f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
                f"DD={metrics['max_drawdown_pct']} trades={metrics['trade_count']} "
                f"buffer_cancels={result['stop_breach_buffer_cancel_count']}"
            )

    summary = OrderedDict()
    for variant in VARIANTS:
        if variant == BASELINE_VARIANT:
            continue

        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                row
                for row in rows
                if row["window"] == label and row["variant"] == BASELINE_VARIANT
            )
            candidate = next(
                row
                for row in rows
                if row["window"] == label and row["variant"] == variant
            )
            delta = _delta(candidate["metrics"], baseline["metrics"])
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": delta,
                "entry_reason_counts": candidate["entry_reason_counts"],
                "stop_breach_cancel_count": candidate["stop_breach_cancel_count"],
                "stop_breach_buffer_cancel_count": candidate[
                    "stop_breach_buffer_cancel_count"
                ],
            }

        baseline_ev_sum = round(
            sum(v["before"]["expected_value_score"] for v in by_window.values()), 6
        )
        ev_delta_sum = round(
            sum(v["delta"]["expected_value_score"] for v in by_window.values()), 6
        )
        baseline_pnl_sum = round(
            sum(v["before"]["total_pnl"] for v in by_window.values()), 2
        )
        pnl_delta_sum = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        aggregate = {
            "baseline_expected_value_score_sum": baseline_ev_sum,
            "expected_value_score_delta_sum": ev_delta_sum,
            "expected_value_score_delta_pct": (
                _round(ev_delta_sum / baseline_ev_sum) if baseline_ev_sum else None
            ),
            "baseline_total_pnl_sum": baseline_pnl_sum,
            "total_pnl_delta_sum": pnl_delta_sum,
            "total_pnl_delta_pct": (
                _round(pnl_delta_sum / baseline_pnl_sum) if baseline_pnl_sum else None
            ),
            "expected_value_score_windows_improved": sum(
                1
                for v in by_window.values()
                if (v["delta"]["expected_value_score"] or 0) > 0
            ),
            "expected_value_score_windows_regressed": sum(
                1
                for v in by_window.values()
                if (v["delta"]["expected_value_score"] or 0) < 0
            ),
            "trade_count_delta_sum": int(
                sum(v["delta"]["trade_count"] or 0 for v in by_window.values())
            ),
            "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
            "max_drawdown_delta_min": min(
                v["delta"]["max_drawdown_pct"] for v in by_window.values()
            ),
            "max_drawdown_delta_max": max(
                v["delta"]["max_drawdown_pct"] for v in by_window.values()
            ),
            "max_sharpe_daily_delta": max(
                v["delta"]["sharpe_daily"] for v in by_window.values()
            ),
            "stop_breach_buffer_cancel_count_sum": sum(
                v["stop_breach_buffer_cancel_count"] for v in by_window.values()
            ),
        }
        summary[variant] = {
            "by_window": by_window,
            "aggregate": aggregate,
            "decision": "accepted_candidate" if _accepted_by_gate4(aggregate) else "rejected",
        }

    best_variant, best_payload = max(
        summary.items(),
        key=lambda item: item[1]["aggregate"]["expected_value_score_delta_sum"],
    )

    best_aggregate = best_payload["aggregate"]
    decision = "accepted_candidate" if _accepted_by_gate4(best_aggregate) else "rejected"
    rejection_reason = None
    if decision == "rejected":
        rejection_reason = (
            "No variant improved expected_value_score in a majority of windows while "
            "also clearing a Gate 4 materiality threshold."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "change_type": "entry_execution_cancel_sweep",
        "single_causal_variable": "next-open distance-to-stop entry cancel buffer",
        "alpha_hypothesis": {
            "category": "entry_execution",
            "hypothesis": (
                "If the next open has already consumed most of the signal's planned "
                "entry-to-stop risk distance, skipping the entry may remove poor "
                "execution-quality trades without needing new data or LLM coverage."
            ),
            "why_this_not_llm": (
                "LLM soft-ranking remains sample-limited; this uses only entry, fill, "
                "and stop fields already present in the shared production/backtest "
                "entry execution policy."
            ),
        },
        "history_guardrails": {
            "checked_docs_backtesting": True,
            "does_not_repeat_llm_soft_ranking": True,
            "does_not_repeat_static_universe_expansion": True,
            "does_not_repeat_macro_etf_expansion": True,
            "does_not_repeat_gap_cancel_threshold_sweep": (
                "This sweep is scaled by entry-to-stop risk distance, not by raw "
                "entry gap percentage."
            ),
            "positive_result_requires_shared_policy_promotion": True,
        },
        "baseline": BASELINE_VARIANT,
        "variants": VARIANTS,
        "windows": WINDOWS,
        "rows": rows,
        "summary": summary,
        "best_variant": best_variant,
        "best_variant_aggregate": best_aggregate,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_note": (
                "This script only runs a counterfactual monkeypatch. Accepted alpha "
                "would need a shared production_parity policy change before use."
            ),
        },
        "modules_intentionally_unchanged": [
            "signal generation",
            "candidate universe",
            "sizing",
            "exits",
            "add-ons",
            "LLM/news replay",
            "earnings/event sleeves",
        ],
        "main_risk_if_promoted": (
            "A buffer could skip legitimate momentum entries whose stops are wide "
            "enough to survive a weak next open."
        ),
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Stop-breach buffer entry cancel",
            "lane": "alpha_search",
            "decision": decision,
            "best_variant": best_variant,
            "summary": {
                "best_variant_aggregate": best_aggregate,
                "rejection_reason": rejection_reason,
            },
            "artifacts": {
                "data": str(OUT_JSON.relative_to(REPO_ROOT)),
                "log": str(LOG_JSON.relative_to(REPO_ROOT)),
            },
        },
    )
    return payload


if __name__ == "__main__":
    result = run_experiment()
    print(
        f"{EXPERIMENT_ID} decision={result['decision']} "
        f"best_variant={result['best_variant']} "
        f"aggregate={result['best_variant_aggregate']}"
    )
