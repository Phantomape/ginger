"""exp-20260508-034: staged initial entry with follow-through top-up.

This alpha-search experiment tests one causal variable: initial entry staging.
Instead of buying the full computed share count on entry, the replay buys a
fixed initial fraction and preserves the original computed share count as
``Position.original_shares`` so the existing day-2 follow-through add-on can
top up confirmed winners.

The patching is experiment-local. No production or default backtest behavior is
changed by this file.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
import portfolio_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260508-034"
STEM = "staged_entry_topup_replay"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_ID}_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

CORE_STRATEGIES = {"trend_long", "breakout_long"}

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "regime_note": "strong late accepted-stack tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "regime_note": "rotation-heavy weaker validation tape",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "regime_note": "older thin mixed-to-weak tape",
            },
        ),
    ]
)

# Gate-1 baseline measured in the current worktree with docs/backtesting.md
# command shape immediately before this experiment.
BASELINE = {
    "late_strong": {
        "expected_value_score": 4.0674,
        "sharpe_daily": 4.48,
        "sharpe": 6.57,
        "max_drawdown_pct": 0.0539,
        "total_pnl": 90788.88,
        "total_return_pct": 0.9079,
        "win_rate": 0.7895,
        "total_trades": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.6195,
        "sharpe_daily": 2.72,
        "sharpe": 4.36,
        "max_drawdown_pct": 0.0879,
        "total_pnl": 59540.63,
        "total_return_pct": 0.5954,
        "win_rate": 0.5238,
        "total_trades": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3583,
        "sharpe_daily": 1.31,
        "sharpe": 2.09,
        "max_drawdown_pct": 0.0903,
        "total_pnl": 27347.42,
        "total_return_pct": 0.2735,
        "win_rate": 0.4091,
        "total_trades": 22,
        "survival_rate": 0.9167,
    },
}

VARIANTS = OrderedDict(
    [
        ("initial_50pct", {"initial_entry_fraction": 0.50}),
        ("initial_75pct", {"initial_entry_fraction": 0.75}),
    ]
)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _round(value: Any, digits: int = 4) -> Any:
    number = _safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def _key(ticker: str, stop: Any, target: Any, staged_shares: int) -> tuple[str, float | None, float | None, int]:
    return (
        str(ticker or "").upper(),
        _round(stop, 4),
        _round(target, 4),
        int(staged_shares or 0),
    )


def _extract_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "sharpe": _round(result.get("sharpe"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct")
            if benchmarks.get("strategy_total_return_pct") is not None
            else result.get("total_return_pct"),
            4,
        ),
        "win_rate": _round(result.get("win_rate"), 4),
        "total_trades": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _addon_summary(result: dict[str, Any]) -> dict[str, Any]:
    attribution = result.get("followthrough_addon_attribution") or result.get("addon_attribution") or {}
    events = attribution.get("events") or []
    return {
        "scheduled": attribution.get("scheduled"),
        "executed": attribution.get("executed"),
        "skipped": attribution.get("skipped"),
        "checkpoint_rejected": attribution.get("checkpoint_rejected"),
        "executed_shares": sum(int(row.get("addon_shares") or 0) for row in events if row.get("status") == "executed"),
    }


def _patch_staged_entry(initial_fraction: float) -> tuple[Callable[[], None], dict[str, Any]]:
    original_size_signals = portfolio_engine.size_signals
    original_position_init = backtester.Position.__init__
    pending_original_by_key: dict[tuple[str, float | None, float | None, int], list[int]] = defaultdict(list)
    stats = {
        "initial_entry_fraction": initial_fraction,
        "signals_staged": 0,
        "original_shares_sum": 0,
        "staged_shares_sum": 0,
        "position_original_restored": 0,
    }

    def patched_size_signals(signals, *args, **kwargs):
        sized = original_size_signals(signals, *args, **kwargs)
        for sig in sized or []:
            if sig.get("strategy") not in CORE_STRATEGIES:
                continue
            sizing = sig.get("sizing") or {}
            original_shares = int(sizing.get("shares_to_buy") or 0)
            if original_shares <= 0:
                continue
            staged_shares = max(1, math.floor(original_shares * initial_fraction))
            if staged_shares >= original_shares:
                continue
            sizing["shares_to_buy"] = staged_shares
            sizing["staged_entry_original_shares"] = original_shares
            sizing["staged_entry_initial_fraction"] = initial_fraction
            sig["sizing"] = sizing
            pending_original_by_key[
                _key(
                    sig.get("ticker"),
                    sig.get("stop_price"),
                    sig.get("target_price"),
                    staged_shares,
                )
            ].append(original_shares)
            stats["signals_staged"] += 1
            stats["original_shares_sum"] += original_shares
            stats["staged_shares_sum"] += staged_shares
        return sized

    def patched_position_init(self, *args, **kwargs):
        original_position_init(self, *args, **kwargs)
        ticker = kwargs.get("ticker") if "ticker" in kwargs else (args[0] if len(args) > 0 else None)
        stop = kwargs.get("stop_price") if "stop_price" in kwargs else (args[2] if len(args) > 2 else None)
        target = kwargs.get("target_price") if "target_price" in kwargs else (args[3] if len(args) > 3 else None)
        shares = kwargs.get("shares") if "shares" in kwargs else (args[4] if len(args) > 4 else None)
        queue_key = _key(ticker, stop, target, int(shares or 0))
        originals = pending_original_by_key.get(queue_key) or []
        if originals:
            self.original_shares = originals.pop(0)
            stats["position_original_restored"] += 1

    portfolio_engine.size_signals = patched_size_signals
    backtester.Position.__init__ = patched_position_init

    def restore() -> None:
        portfolio_engine.size_signals = original_size_signals
        backtester.Position.__init__ = original_position_init

    return restore, stats


def _run_window(window: dict[str, str], initial_fraction: float) -> tuple[dict[str, Any], dict[str, Any]]:
    restore, stats = _patch_staged_entry(initial_fraction)
    try:
        engine = BacktestEngine(
            get_universe(),
            start=window["start"],
            end=window["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        result = engine.run()
    finally:
        restore()
    metrics = _extract_metrics(result)
    metrics["addon_summary"] = _addon_summary(result)
    metrics["staged_entry_stats"] = {
        key: int(value) if isinstance(value, int) else value
        for key, value in stats.items()
    }
    return metrics, result


def _aggregate_delta(after: dict[str, dict[str, Any]], before: dict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row.get("expected_value_score") or 0.0) for row in before.values())
    after_ev = sum(float(row.get("expected_value_score") or 0.0) for row in after.values())
    before_pnl = sum(float(row.get("total_pnl") or 0.0) for row in before.values())
    after_pnl = sum(float(row.get("total_pnl") or 0.0) for row in after.values())
    ev_positive = [
        label
        for label in before
        if float(after[label].get("expected_value_score") or 0.0)
        > float(before[label].get("expected_value_score") or 0.0)
    ]
    pnl_positive = [
        label
        for label in before
        if float(after[label].get("total_pnl") or 0.0)
        > float(before[label].get("total_pnl") or 0.0)
    ]
    return {
        "baseline_ev_sum": round(before_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - before_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
        "baseline_pnl_sum": round(before_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - before_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6) if before_pnl else None,
        "ev_positive_windows": ev_positive,
        "pnl_positive_windows": pnl_positive,
        "ev_regressed_windows": [label for label in before if label not in ev_positive and after[label].get("expected_value_score") != before[label].get("expected_value_score")],
        "pnl_regressed_windows": [label for label in before if label not in pnl_positive and after[label].get("total_pnl") != before[label].get("total_pnl")],
        "win_rate_regressions": [
            label
            for label in before
            if float(after[label].get("win_rate") or 0.0) < float(before[label].get("win_rate") or 0.0)
        ],
        "trade_count_delta_sum": sum(
            int(after[label].get("total_trades") or 0) - int(before[label].get("total_trades") or 0)
            for label in before
        ),
        "max_drawdown_delta_max": max(
            round(float(after[label].get("max_drawdown_pct") or 0.0) - float(before[label].get("max_drawdown_pct") or 0.0), 4)
            for label in before
        ),
        "sharpe_daily_delta_max": max(
            round(float(after[label].get("sharpe_daily") or 0.0) - float(before[label].get("sharpe_daily") or 0.0), 4)
            for label in before
        ),
    }


def _gate4(delta: dict[str, Any]) -> dict[str, Any]:
    ev_pct = delta.get("aggregate_ev_delta_pct")
    pnl_pct = delta.get("aggregate_pnl_delta_pct")
    ev_or_pnl_material = bool(
        (ev_pct is not None and ev_pct > 0.10)
        or (pnl_pct is not None and pnl_pct > 0.05)
    )
    no_ev_pnl_regression = not delta.get("ev_regressed_windows") and not delta.get("pnl_regressed_windows")
    secondary_pass = bool(
        delta.get("sharpe_daily_delta_max", 0.0) > 0.10
        or delta.get("max_drawdown_delta_max", 0.0) < -0.01
        or (delta.get("trade_count_delta_sum", 0) > 0 and not delta.get("win_rate_regressions"))
    )
    passed = ev_or_pnl_material or (secondary_pass and no_ev_pnl_regression)
    return {
        "passed": passed,
        "rule": (
            "EV first over the three canonical backtesting.md windows; "
            "secondary improvements cannot override aggregate EV/PnL regression."
        ),
        "reason": (
            "passed material EV/PnL or non-regressive secondary Gate 4 clause"
            if passed
            else "EV/PnL regressed, so drawdown improvement is insufficient"
        ),
    }


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_markdown(payload: dict[str, Any]) -> None:
    best = payload["after_metrics"]["best_variant"]
    deltas = payload["delta_metrics"][best]
    rows = []
    for label, before in payload["before_metrics"]["windows"].items():
        after = payload["after_metrics"]["variants"][best][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${dpnl:,.2f} | {ds:+.2f} | {dd:+.2%} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=after["expected_value_score"] - before["expected_value_score"],
                dpnl=after["total_pnl"] - before["total_pnl"],
                ds=after["sharpe_daily"] - before["sharpe_daily"],
                dd=after["max_drawdown_pct"] - before["max_drawdown_pct"],
            )
        )
    lines = [
        "# exp-20260508-034 Staged Entry Top-up Replay",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Best Variant",
        "",
        f"Best variant: `{best}`.",
        "",
        "| Window | EV Before | EV After | EV Delta | PnL Delta | Sharpe Daily Delta | Max DD Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        *rows,
        "",
        "## Aggregate",
        "",
        "```json",
        json.dumps(deltas, indent=2, sort_keys=True),
        "```",
        "",
        "## Production Parity",
        "",
        json.dumps(payload["production_impact"], indent=2, sort_keys=True),
        "",
        "## Anti-Repeat",
        "",
        payload["rejection_reason"] or "Promote only after shared production/backtest policy and parity tests.",
    ]
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    variant_metrics: OrderedDict[str, dict[str, dict[str, Any]]] = OrderedDict()
    raw_result_paths: dict[str, dict[str, str]] = {}
    for variant, params in VARIANTS.items():
        variant_metrics[variant] = {}
        raw_result_paths[variant] = {}
        for label, window in WINDOWS.items():
            metrics, result = _run_window(window, params["initial_entry_fraction"])
            variant_metrics[variant][label] = metrics
            result_path = OUT_DIR / f"{EXPERIMENT_ID}_{variant}_{label}_raw.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            raw_result_paths[variant][label] = str(result_path.relative_to(REPO_ROOT))

    deltas = OrderedDict(
        (variant, _aggregate_delta(metrics, BASELINE))
        for variant, metrics in variant_metrics.items()
    )
    best_variant = max(
        deltas,
        key=lambda name: (
            deltas[name]["aggregate_ev_delta"],
            deltas[name]["aggregate_pnl_delta"],
        ),
    )
    gate4 = _gate4(deltas[best_variant])
    decision = "accepted_for_promotion_required" if gate4["passed"] else "rejected"
    rejection_reason = None
    if not gate4["passed"]:
        rejection_reason = (
            "Gate 4 failed. Staging initial entries reduced exposure to winners "
            "more than it helped avoid losers; do not retry nearby 50%-75% "
            "staged-entry fractions without a new discriminator for which entries "
            "should be staged."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Buying a conservative initial fraction of each accepted A/B signal and "
            "using the existing day-2 follow-through add-on to top up confirmed "
            "winners may improve expected value by reducing loser exposure while "
            "preserving upside in trades that quickly work."
        ),
        "alpha_hypothesis_category": "capital_allocation_entry_lifecycle",
        "change_type": "staged_entry_topup_replay",
        "single_causal_variable": "initial entry fraction with original_shares preserved for day-2 top-up",
        "historical_experiment_check": {
            "not_repeated": [
                "Not a raw add-on heat-cap increase.",
                "Not same-day add-on ordering.",
                "Not checkpoint volume confirmation.",
                "Not second add-on enablement.",
                "Not an RS/no-gap scalar replay.",
            ],
            "mechanism_insight": (
                "exp-20260508-027 and exp-20260508-029 made conservative-entry "
                "intent metadata the next valid add-on direction; this replay tests "
                "that lifecycle alpha with a frozen original share count."
            ),
        },
        "parameters": {
            "variants": VARIANTS,
            "locked_variables": [
                "signal generation",
                "entry candidate ranking",
                "entry filters",
                "gap cancel rules",
                "stop/target rules",
                "day-2 add-on trigger",
                "day-2 add-on fraction",
                "position caps",
                "portfolio heat cap",
                "exits",
                "universe",
                "LLM/news replay",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["regime_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {
            "aggregate_ev_sum": round(
                sum(row["expected_value_score"] for row in BASELINE.values()), 4
            ),
            "aggregate_pnl": round(sum(row["total_pnl"] for row in BASELINE.values()), 2),
            "windows": BASELINE,
        },
        "after_metrics": {
            "best_variant": best_variant,
            "variants": variant_metrics,
        },
        "delta_metrics": deltas,
        "gate4": gate4,
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM/event ranking remains sample-limited; this run uses fully "
                "replayable OHLCV and existing add-on mechanics."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "promotion_requirement_if_positive": (
                "Implement staged initial shares and original_shares preservation "
                "in shared production/backtest policy, expose intended_shares in "
                "run.py, and add parity tests before live promotion."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry nearby 50%-75% staged-entry fractions alone.",
            "A valid retry needs an ex-ante discriminator identifying which accepted entries should be staged.",
            "If later positive, staged-entry sizing must be shared by production and backtest before promotion.",
        ],
        "raw_result_paths": raw_result_paths,
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "quant/experiments/exp_20260508_034_staged_entry_topup_replay.py",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    LOG_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "next_action": (
            "implement shared staged-entry policy"
            if gate4["passed"]
            else "do not retry without a staging discriminator"
        ),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2), encoding="utf-8")
    _write_markdown(payload)
    _append_jsonl(EXPERIMENT_LOG, payload)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "best_variant": best_variant,
        "delta": deltas[best_variant],
        "gate4": gate4,
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
