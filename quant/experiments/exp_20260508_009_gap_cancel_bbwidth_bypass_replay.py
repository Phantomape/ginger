"""exp-20260508-009 gap-cancel BB-width bypass replay.

Alpha-search only. This script tests one entry-execution hypothesis without
changing the default backtester, production runner, ranking, sizing, exits, or
prompts:

    If an entry is cancelled only because the next open gaps beyond the shared
    open-cancel threshold, allow the fill when the signal-day 20-day Bollinger
    bandwidth is already wide enough to indicate an active volatility expansion.

The replay uses the canonical three fixed windows from docs/backtesting.md.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260508-009"
STEM = "gap_cancel_bbwidth_bypass_replay"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_BBWIDTH20 = 0.269211
TARGET_CANCEL_REASONS = {"gap_cancel", "adverse_gap_down_cancel"}

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

BASELINE = {
    "late_strong": {
        "expected_value_score": 3.6257,
        "sharpe_daily": 4.42,
        "max_drawdown_pct": 0.0539,
        "total_pnl": 82030.12,
        "strategy_total_return_pct": 0.8203,
        "win_rate": 0.75,
        "total_trades": 20,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.804,
    },
    "mid_weak": {
        "expected_value_score": 1.5478,
        "sharpe_daily": 2.69,
        "max_drawdown_pct": 0.0879,
        "total_pnl": 57542.74,
        "strategy_total_return_pct": 0.5754,
        "win_rate": 0.524,
        "total_trades": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.792,
    },
    "old_thin": {
        "expected_value_score": 0.3359,
        "sharpe_daily": 1.28,
        "max_drawdown_pct": 0.0905,
        "total_pnl": 26242.68,
        "strategy_total_return_pct": 0.2624,
        "win_rate": 0.409,
        "total_trades": 22,
        "signals_generated": 60,
        "signals_survived": 55,
        "survival_rate": 0.917,
    },
}


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return _safe(value.item())
        except (TypeError, ValueError):
            return str(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True) + "\n")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _scalar(value: Any) -> float | None:
    try:
        if hasattr(value, "item"):
            value = value.item()
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _bbwidth20(df: Any, signal_date: Any) -> float | None:
    if df is None or "Close" not in df:
        return None
    try:
        prior = df.loc[df.index <= signal_date]
    except Exception:
        return None
    if len(prior) < 20:
        return None
    closes = [_scalar(value) for value in prior["Close"].tail(20)]
    closes = [value for value in closes if value is not None]
    if len(closes) < 20:
        return None
    avg = sum(closes) / len(closes)
    if avg == 0:
        return None
    variance = sum((value - avg) ** 2 for value in closes) / len(closes)
    return 4.0 * math.sqrt(variance) / avg


def _metric_slice(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def _deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_pnl",
        "strategy_total_return_pct",
        "win_rate",
        "total_trades",
        "survival_rate",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        if before.get(key) is None or after.get(key) is None:
            out[key] = None
        else:
            out[key] = round(float(after[key]) - float(before[key]), 6)
    return out


@contextmanager
def _patched_cancel_classifier(events: list[dict[str, Any]]):
    original = bt.classify_entry_open_cancel

    def classifier(fill_price, signal_entry, stop_price=None, **kwargs):
        reason = original(fill_price, signal_entry, stop_price=stop_price, **kwargs)
        if reason not in TARGET_CANCEL_REASONS:
            return reason

        fill = _scalar(fill_price)
        stop = _scalar(stop_price)
        if reason == "adverse_gap_down_cancel" and stop is not None and fill is not None:
            if fill <= stop:
                return reason

        frame = inspect.currentframe()
        caller = frame.f_back if frame is not None else None
        if caller is None or caller.f_code.co_name != "run":
            return reason

        sig = caller.f_locals.get("sig")
        today = caller.f_locals.get("today")
        ohlcv_all = caller.f_locals.get("ohlcv_all")
        if not isinstance(sig, dict) or today is None or not isinstance(ohlcv_all, dict):
            return reason

        ticker = sig.get("ticker")
        df = ohlcv_all.get(ticker)
        bbwidth20 = _bbwidth20(df, today)
        if bbwidth20 is None or bbwidth20 < MIN_BBWIDTH20:
            return reason

        gap_pct = None
        entry = _scalar(signal_entry)
        if entry and fill is not None:
            gap_pct = fill / entry - 1.0
        events.append(
            {
                "date": str(today.date()) if hasattr(today, "date") else str(today),
                "ticker": ticker,
                "strategy": sig.get("strategy"),
                "sector": sig.get("sector"),
                "original_cancel_reason": reason,
                "fill_price": round(fill, 4) if fill is not None else None,
                "signal_entry": round(entry, 4) if entry is not None else None,
                "gap_pct": round(gap_pct, 6) if gap_pct is not None else None,
                "bbwidth20": round(bbwidth20, 6),
                "min_bbwidth20": MIN_BBWIDTH20,
            }
        )
        return None

    bt.classify_entry_open_cancel = classifier
    try:
        yield
    finally:
        bt.classify_entry_open_cancel = original


def _run_window(name: str, spec: dict[str, Any], universe: list[str]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    cfg = {
        "REGIME_AWARE_EXIT": True,
        "REPLAY_PARTIAL_REDUCES": True,
    }
    with _patched_cancel_classifier(events):
        engine = bt.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config=cfg,
            ohlcv_snapshot_path=str(spec["snapshot"]),
        )
        result = engine.run()
    after = _metric_slice(result)
    before = BASELINE[name]
    return {
        "window": name,
        "date_range": {"start": spec["start"], "end": spec["end"]},
        "snapshot": _repo_rel(spec["snapshot"]),
        "before_metrics": before,
        "after_metrics": after,
        "metric_deltas": _deltas(before, after),
        "bypass_events": events,
        "bypass_count": len(events),
    }


def _gate4(window_results: dict[str, Any]) -> dict[str, Any]:
    positive_ev = [
        name
        for name, row in window_results.items()
        if (row["metric_deltas"].get("expected_value_score") or 0) > 0
    ]
    negative_ev = [
        name
        for name, row in window_results.items()
        if (row["metric_deltas"].get("expected_value_score") or 0) < 0
    ]
    passed = len(positive_ev) >= 2 and not negative_ev
    return {
        "passed": passed,
        "positive_ev_windows": positive_ev,
        "negative_ev_windows": negative_ev,
        "basis": (
            "Three-window replay requires EV improvement in most windows and no "
            "negative EV window before any shared production/backtest promotion."
        ),
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} Gap Cancel BB-Width Bypass Replay",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- gate4 passed: {payload['gate4']['passed']}",
        "- production orders changed: false",
        "- shared policy changed: false",
        "",
        "## Metrics",
        "",
        "| Window | EV Before | EV After | EV Delta | Sharpe Daily Delta | PnL Delta | Trades Delta | Bypasses |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["windows"].items():
        before = row["before_metrics"]
        after = row["after_metrics"]
        delta = row["metric_deltas"]
        lines.append(
            "| {name} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{delta_sharpe:+.4f} | {delta_pnl:+.2f} | {delta_trades:+.0f} | {bypasses} |".format(
                name=name,
                before_ev=float(before["expected_value_score"]),
                after_ev=float(after["expected_value_score"]),
                delta_ev=float(delta["expected_value_score"] or 0.0),
                delta_sharpe=float(delta["sharpe_daily"] or 0.0),
                delta_pnl=float(delta["total_pnl"] or 0.0),
                delta_trades=float(delta["total_trades"] or 0.0),
                bypasses=row["bypass_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Bypass Events",
            "",
        ]
    )
    total_events = 0
    for name, row in payload["windows"].items():
        for event in row["bypass_events"]:
            total_events += 1
            lines.append(
                "- {window} {date} {ticker}: {reason}, gap={gap_pct}, bbwidth20={bbwidth20}".format(
                    window=name,
                    date=event["date"],
                    ticker=event["ticker"],
                    reason=event["original_cancel_reason"],
                    gap_pct=event["gap_pct"],
                    bbwidth20=event["bbwidth20"],
                )
            )
    if total_events == 0:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Production Parity",
            "",
            (
                "This replay did not alter shared production/backtest policy. If a "
                "future retry passes the three-window gate, the bypass must be "
                "implemented in `quant/production_parity.py` and surfaced in the "
                "daily execution note before it can affect live orders."
            ),
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["decision"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": "entry_execution",
        "change_type": "entry_open_cancel_bypass_replay",
        "mechanism_family": "gap_cancel_follow_through",
        "single_causal_variable": "bbwidth20_ge_0_269211_bypass_for_gap_cancelled_entries",
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "windows": payload["windows"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_reason": payload["decision_reason"],
        "next_action": payload["next_action"],
        "related_files": payload["related_files"],
        "verification": payload["verification"],
    }


def main() -> None:
    universe = get_universe()
    window_results = OrderedDict()
    for name, spec in WINDOWS.items():
        print(f"Running {name} {spec['start']} -> {spec['end']}")
        window_results[name] = _run_window(name, spec, universe)

    gate4 = _gate4(window_results)
    decision = "accepted_for_shared_policy_implementation" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        decision_reason = (
            "Replay improved expected value in the majority of canonical windows "
            "without a negative EV window. Shared policy implementation is still "
            "required before live use."
        )
        next_action = (
            "Implement the bypass in quant/production_parity.py, pass point-in-time "
            "context from backtester, surface the exception in production entry notes, "
            "then rerun the same three windows."
        )
    else:
        decision_reason = (
            "Three-window replay failed the promotion gate, so no production or "
            "shared backtest policy was changed."
        )
        next_action = (
            "Do not retry this exact BB-width bypass without new forward evidence "
            "or a different orthogonal discriminator."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Some open-gap cancelled entries are not bad chase risk; when the "
            "signal-day 20-day Bollinger bandwidth is already high, the gap may "
            "confirm volatility expansion and should be allowed to fill."
        ),
        "decision": decision,
        "decision_reason": decision_reason,
        "parameters": {
            "min_bbwidth20": MIN_BBWIDTH20,
            "target_cancel_reasons": sorted(TARGET_CANCEL_REASONS),
            "baseline_source": (
                "Current dirty-tree canonical baseline run in this automation turn; "
                "see artifact metrics table."
            ),
            "canonical_windows": list(WINDOWS.keys()),
        },
        "history_check": {
            "exp-20260507-920": (
                "Loss-attribution audit found bbwidth20>=0.269211 among top "
                "orthogonal discriminators for cancelled entries."
            ),
            "exp-20260508-003": (
                "Commodity near-high scalar failed; this experiment does not touch "
                "commodity sizing or near-high thresholds."
            ),
            "gap_threshold_family": (
                "This is not a raw CANCEL_GAP_PCT relaxation; the cancel threshold "
                "stays fixed and the test uses a separate signal-day volatility "
                "state discriminator."
            ),
            "mechanism_insight_conflict": (
                "No direct conflict, but sample support is small; promotion requires "
                "the canonical three-window gate."
            ),
        },
        "windows": window_results,
        "gate4": gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "report_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking data limitations did not block this deterministic "
                "entry-execution alpha search."
            ),
        },
        "next_action": next_action,
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "verification": {
            "command": (
                ".\\.venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260508_009_gap_cancel_bbwidth_bypass_replay.py"
            ),
            "three_window_protocol": "docs/backtesting.md canonical windows with fixed OHLCV snapshots",
        },
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "summary": decision_reason,
        "next_action": next_action,
        "gate4": gate4,
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _log_record(payload))
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG, _log_record(payload))

    print(json.dumps(_safe({"decision": decision, "gate4": gate4}), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
