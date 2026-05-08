"""exp-20260507-034: platform RS20 leader entry-gate replay.

Alpha search, replay-only. exp-20260507-032 showed that platform-pool
candidate events tagged rs20_leader had strong 20-day forward returns. This
experiment tests a tradable approximation: after the normal entry plan selects
core candidates, skip platform-pool entries whose signal-date 20-day return
does not beat SPY by at least 5 percentage points.

Same-day backfill is intentionally disabled. If a planned platform candidate is
skipped, later candidates do not fill that freed slot on the same date. Entries,
ranking, exits, sizing, add-ons, universe, LLM/news, and event sleeves otherwise
remain locked. The implementation is a runtime monkeypatch inside this script;
no production path is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-034"
STEM = "platform_rs20_entry_gate"
SOURCE_EXPERIMENT_ID = "exp-20260507-032"

PLATFORM_POOL = ("META", "NFLX", "GOOG", "AMZN", "SPOT", "DIS", "APP")
RS20_EXCESS_THRESHOLD = 0.05

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

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
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
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


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _window_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") if isinstance(result.get("benchmarks"), dict) else {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "entry_reason_counts": (
            (result.get("entry_execution_attribution") or {}).get("reason_counts")
        ),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key in (
        "expected_value_score",
        "total_pnl",
        "total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ):
        av = after.get(key)
        bv = before.get(key)
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            out[key] = _round(av - bv, 4 if key != "total_pnl" else 2)
        else:
            out[key] = None
    return out


def _trade_key(trade: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(trade.get("entry_date") or "")[:10],
        str(trade.get("ticker") or "").upper(),
        str(trade.get("strategy") or ""),
        str(trade.get("exit_date") or "")[:10],
    )


def _trade_deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_map = {_trade_key(trade): trade for trade in before.get("trades") or []}
    after_map = {_trade_key(trade): trade for trade in after.get("trades") or []}
    all_keys = sorted(set(before_map) | set(after_map))
    removed = []
    added = []
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    for key in all_keys:
        bt = before_map.get(key)
        at = after_map.get(key)
        ticker = key[1]
        bpnl = _float((bt or {}).get("pnl")) or 0.0
        apnl = _float((at or {}).get("pnl")) or 0.0
        delta = apnl - bpnl
        if abs(delta) > 0.005:
            pnl_delta_by_ticker[ticker] += delta
        if bt and not at:
            removed.append({
                "ticker": ticker,
                "strategy": key[2],
                "entry_date": key[0],
                "exit_date": key[3],
                "baseline_pnl": _round(bpnl, 2),
            })
        elif at and not bt:
            added.append({
                "ticker": ticker,
                "strategy": key[2],
                "entry_date": key[0],
                "exit_date": key[3],
                "variant_pnl": _round(apnl, 2),
            })
    return {
        "removed_trade_count": len(removed),
        "added_trade_count": len(added),
        "removed_trades": removed[:20],
        "added_trades": added[:20],
        "pnl_delta_by_ticker": {
            ticker: _round(value, 2) for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
    }


def _run_backtest(spec: dict[str, Any]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        start=spec["start"],
        end=spec["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
        },
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        include_entry_candidate_events=True,
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _make_gate_wrapper(original_plan, gate_state: dict[str, Any]):
    platform = set(PLATFORM_POOL)

    def _wrapped(signals, *args, **kwargs):
        planned, entry_plan = original_plan(signals, *args, **kwargs)
        kept = []
        skipped = []
        for rank, sig in enumerate(planned, start=1):
            ticker = str(sig.get("ticker") or "").upper()
            rel_rs20 = _float(sig.get("ticker_ret20_minus_spy_pct"))
            if ticker in platform and (rel_rs20 is None or rel_rs20 < RS20_EXCESS_THRESHOLD):
                skipped.append({
                    "ticker": ticker,
                    "strategy": sig.get("strategy"),
                    "candidate_rank": rank,
                    "ticker_ret20_minus_spy_pct": _round(rel_rs20, 4),
                    "threshold": RS20_EXCESS_THRESHOLD,
                    "reason": (
                        "missing_rs20" if rel_rs20 is None
                        else "platform_rs20_below_5pp"
                    ),
                })
                continue
            kept.append(sig)
        if skipped:
            gate_state["skipped_signals"].extend(skipped)
            gate_state["skipped_signal_count"] += len(skipped)
            gate_state["skipped_by_ticker"].update(item["ticker"] for item in skipped)
            gate_state["skipped_by_strategy"].update(
                item.get("strategy") or "unknown" for item in skipped
            )
        return kept, dict(entry_plan)

    return _wrapped


def _run_gated_backtest(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    original_plan = backtester_module.plan_entry_candidates
    gate_state = {
        "skipped_signal_count": 0,
        "skipped_signals": [],
        "skipped_by_ticker": Counter(),
        "skipped_by_strategy": Counter(),
    }
    backtester_module.plan_entry_candidates = _make_gate_wrapper(original_plan, gate_state)
    try:
        result = _run_backtest(spec)
    finally:
        backtester_module.plan_entry_candidates = original_plan
    gate_state["skipped_by_ticker"] = dict(sorted(gate_state["skipped_by_ticker"].items()))
    gate_state["skipped_by_strategy"] = dict(sorted(gate_state["skipped_by_strategy"].items()))
    gate_state["skipped_signals"] = gate_state["skipped_signals"][:50]
    return result, gate_state


def _replay_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    baseline = _run_backtest(spec)
    gated, gate_state = _run_gated_backtest(spec)
    before = _window_metrics(baseline)
    after = _window_metrics(gated)
    return {
        "window": name,
        "window_spec": spec,
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": _delta(after, before),
        "gate_state": gate_state,
        "trade_delta": _trade_deltas(baseline, gated),
    }


def _positive_share(pnl_delta_by_ticker: dict[str, float]) -> float | None:
    positives = [value for value in pnl_delta_by_ticker.values() if value > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return max(positives) / total


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    before_ev = sum(window["before_metrics"].get("expected_value_score") or 0.0 for window in by_window.values())
    after_ev = sum(window["after_metrics"].get("expected_value_score") or 0.0 for window in by_window.values())
    before_pnl = sum(window["before_metrics"].get("total_pnl") or 0.0 for window in by_window.values())
    after_pnl = sum(window["after_metrics"].get("total_pnl") or 0.0 for window in by_window.values())
    touched = sum(window["gate_state"].get("skipped_signal_count") or 0 for window in by_window.values())
    improved = 0
    regressed = 0
    max_dd_worsening = 0.0
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    skipped_by_ticker: Counter[str] = Counter()
    for window in by_window.values():
        ev_delta = window["delta_metrics"].get("expected_value_score") or 0.0
        if ev_delta > 0:
            improved += 1
        elif ev_delta < 0:
            regressed += 1
        max_dd_worsening = max(
            max_dd_worsening,
            window["delta_metrics"].get("max_drawdown_pct") or 0.0,
        )
        skipped_by_ticker.update(window["gate_state"].get("skipped_by_ticker") or {})
        for ticker, value in (window["trade_delta"].get("pnl_delta_by_ticker") or {}).items():
            pnl_delta_by_ticker[ticker] += float(value or 0.0)

    ev_delta = after_ev - before_ev
    pnl_delta = after_pnl - before_pnl
    ev_delta_pct = ev_delta / abs(before_ev) if before_ev else None
    pnl_delta_pct = pnl_delta / before_pnl if before_pnl else None
    max_single_share = _positive_share(dict(pnl_delta_by_ticker))
    gate4_passed = (
        ev_delta_pct is not None
        and ev_delta_pct > 0.10
        and improved >= 2
        and regressed == 0
        and max_dd_worsening <= 0.01
        and touched >= 8
        and (max_single_share is None or max_single_share <= 0.50)
    )
    return {
        "baseline_expected_value_score_sum": _round(before_ev, 4),
        "after_expected_value_score_sum": _round(after_ev, 4),
        "expected_value_score_delta_sum": _round(ev_delta, 4),
        "expected_value_score_delta_pct": _round(ev_delta_pct, 6),
        "baseline_total_pnl_sum": _round(before_pnl, 2),
        "after_total_pnl_sum": _round(after_pnl, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta_pct, 6),
        "windows_ev_improved": improved,
        "windows_ev_regressed": regressed,
        "max_drawdown_worsening_max": _round(max_dd_worsening, 4),
        "skipped_signal_count": touched,
        "skipped_by_ticker": dict(sorted(skipped_by_ticker.items())),
        "pnl_delta_by_ticker": {
            ticker: _round(value, 2) for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
        "max_single_ticker_positive_share": _round(max_single_share, 4),
        "gate4_passed": gate4_passed,
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    agg = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Platform RS20 Entry Gate",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- gate4_passed: {agg['gate4_passed']}",
        f"- skipped_signal_count: {agg['skipped_signal_count']}",
        f"- EV delta sum: {agg['expected_value_score_delta_sum']}",
        f"- PnL delta: {agg['total_pnl_delta_sum']}",
        "",
        "## By Window",
        "",
    ]
    for name, window in payload["by_window"].items():
        delta = window["delta_metrics"]
        lines.append(
            "- "
            f"{name}: EV {delta['expected_value_score']}, "
            f"PnL {delta['total_pnl']}, "
            f"DD {delta['max_drawdown_pct']}, "
            f"skipped {window['gate_state']['skipped_signal_count']}"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Runtime monkeypatch only; no production path changed.",
        "- Same-day backfill is disabled to isolate the entry-gate variable.",
        "- The gate uses signal-date ticker_ret20_minus_spy_pct >= 0.05.",
        "",
    ])
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
        "alpha_hypothesis_category": "entry",
        "change_type": "runtime_replay_entry_gate",
        "mechanism_family": "platform_entry_state_rs20_leader_gate",
        "single_causal_variable": "platform_pool_rs20_5pp_entry_gate_no_same_day_backfill",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "before_metrics": {
            name: window["before_metrics"] for name, window in payload["by_window"].items()
        },
        "after_metrics": {
            name: window["after_metrics"] for name, window in payload["by_window"].items()
        },
        "delta_metrics": payload["aggregate"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": payload.get("rejection_reason"),
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
    }


def main() -> None:
    by_window = OrderedDict((name, _replay_window(name, spec)) for name, spec in WINDOWS.items())
    aggregate = _aggregate(by_window)
    decision = "accepted_shadow" if aggregate["gate4_passed"] else "rejected"
    rejection_reason = None
    if not aggregate["gate4_passed"]:
        rejection_reason = (
            "Platform RS20 gate failed replay gate: "
            f"EV delta {aggregate['expected_value_score_delta_sum']} "
            f"({aggregate['expected_value_score_delta_pct']}), "
            f"windows improved/regressed "
            f"{aggregate['windows_ev_improved']}/{aggregate['windows_ev_regressed']}, "
            f"skipped signals {aggregate['skipped_signal_count']}, "
            f"max DD worsening {aggregate['max_drawdown_worsening_max']}."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "hypothesis": (
            "Platform-pool candidates only deserve execution when their signal-date "
            "20-day return leads SPY by at least 5 percentage points."
        ),
        "decision": decision,
        "rejection_reason": rejection_reason,
        "parameters": {
            "platform_pool": PLATFORM_POOL,
            "rs20_excess_threshold": RS20_EXCESS_THRESHOLD,
            "same_day_backfill": False,
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry ranking before normal plan",
                "sizing",
                "exits",
                "add-ons",
                "event sleeves",
                "LLM/news replay",
            ],
            "gate4": {
                "expected_value_score_delta_pct": "> 10%",
                "windows_ev_improved": ">= 2 of 3",
                "windows_ev_regressed": "0",
                "max_drawdown_worsening": "<= 1pp",
                "skipped_signal_count": ">= 8",
                "single_ticker_positive_contribution": "<= 50%",
            },
        },
        "history_check": {
            "mechanism_insight_conflict": (
                "Potential conflict with OHLCV-only entry caution; allowed as a "
                "bounded replay because it uses exp-032 oracle evidence and touches "
                "only the existing platform-pool candidate stream."
            ),
            "nearby_rejected": {
                "exp-20260507-008": "Mechanical platform pullback entry timing rejected.",
                "exp-20260507-030": "META/NFLX candidate overlap underpowered.",
                "exp-20260507-033": "Far-from-earnings entry-state risk replay rejected.",
            },
            "why_not_simple_repeat": (
                "This is not pullback timing, new universe promotion, or risk sizing. "
                "It tests one candidate-state entry gate with no same-day refill."
            ),
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "gate4": {
            "passed": aggregate["gate4_passed"],
            "basis": (
                "Full runtime backtest using monkeypatched entry-plan output. "
                "Promotion would require shared run.py/backtester policy and tests."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
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
            "blocker_relation": "LLM/news replay is locked out of this deterministic entry-state replay.",
        },
        "next_retry_requires": [
            "Do not retry nearby RS20 thresholds if rejected.",
            "A valid retry needs an orthogonal event/news discriminator or forward paper evidence.",
            "If accepted later, implement as shared entry policy consumed by run.py and backtester.py.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
            str(Path(__file__).relative_to(REPO_ROOT)),
        ],
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "title": "Platform RS20 leader entry gate",
        "result": decision,
        "created_at": timestamp,
        "completed_at": timestamp,
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _log_record(payload))
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG, _log_record(payload))
    print(json.dumps({
        "decision": decision,
        "rejection_reason": rejection_reason,
        "aggregate": aggregate,
    }, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
