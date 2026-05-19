"""exp-20260507-035: missed platform RS20 candidate sleeve audit.

Observed-only alpha scout. exp-20260507-034 showed that turning platform
rs20_leader into a hard entry gate does not improve the core strategy enough.
This audit asks the complementary question: do platform-pool rs20_leader
candidates that the core system did not enter have enough replacement value to
justify a future default-off sleeve?

No production path is changed. The sleeve PnL below is a diagnostic fixed
notional replay using future exits, not a tradable promotion.
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

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from oracle_diagnostics import (  # noqa: E402
    _as_float,
    _earnings_for_candidate,
    _entry_row_index,
    _entry_state_candidate_events,
    _entry_timing_tags,
    _ticker_rows,
)


EXPERIMENT_ID = "exp-20260507-035"
STEM = "platform_rs20_missed_sleeve_audit"
SOURCE_EXPERIMENTS = ("exp-20260507-032", "exp-20260507-034")

PLATFORM_POOL = ("META", "NFLX", "GOOG", "AMZN", "SPOT", "DIS", "APP")
TREATMENT_TAG = "rs20_leader"
NOTIONAL_USD = 10_000.0
HOLD_DAYS = 20

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
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
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_late_strong.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_late_strong.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_mid_weak.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_mid_weak.json"
                ),
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_old_thin.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_old_thin.json"
                ),
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


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


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


def _normalize_date(raw_date: Any) -> str | None:
    if raw_date is None:
        return None
    text = str(raw_date)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _load_earnings_for_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for event in events:
        date_str = _normalize_date(event.get("date") or event.get("signal_date"))
        if not date_str or date_str in out:
            continue
        compact = date_str.replace("-", "")
        path = REPO_ROOT / "data" / f"earnings_snapshot_{compact}.json"
        if not path.exists():
            out[date_str] = {}
            continue
        payload = _load_json(path)
        earnings = payload.get("earnings") if isinstance(payload, dict) else {}
        out[date_str] = earnings if isinstance(earnings, dict) else {}
    return out


def _event_rows(
    backtest_result: dict[str, Any],
    snapshot: dict[str, Any],
    candidate_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_ticker = _ticker_rows(snapshot)
    spy_rows = rows_by_ticker.get("SPY")
    events = _entry_state_candidate_events(
        backtest_result,
        {"candidate_events": candidate_events},
    )
    earnings_by_date = _load_earnings_for_events(candidate_events)

    out: list[dict[str, Any]] = []
    seen = set()
    for event in events:
        signal_date = event["signal_date"]
        ticker = event["ticker"]
        if ticker not in PLATFORM_POOL:
            continue
        key = (
            signal_date,
            ticker,
            event.get("source"),
            event.get("candidate_rank"),
            event.get("decision"),
        )
        if key in seen:
            continue
        seen.add(key)

        rows = rows_by_ticker.get(ticker)
        if not rows:
            continue
        signal_idx = None
        for idx, row in enumerate(rows):
            if row.get("Date") == signal_date:
                signal_idx = idx
                break
        entry_idx = _entry_row_index(rows, signal_date, event.get("details"))
        if signal_idx is None or entry_idx is None:
            continue

        earnings = _earnings_for_candidate(earnings_by_date, signal_date, ticker)
        tags, metrics = _entry_timing_tags(
            rows,
            signal_idx,
            spy_rows,
            signal_date,
            earnings,
        )
        forward = rows[entry_idx:entry_idx + HOLD_DAYS]
        if not forward:
            continue
        entry_open = _as_float(forward[0].get("Open"))
        exit_close = _as_float(forward[-1].get("Close"))
        highs = [_as_float(row.get("High")) for row in forward]
        lows = [_as_float(row.get("Low")) for row in forward]
        highs = [value for value in highs if value is not None]
        lows = [value for value in lows if value is not None]
        if not entry_open or exit_close is None:
            continue
        shares = int(NOTIONAL_USD // (entry_open * (1 + ROUND_TRIP_COST_PCT)))
        if shares <= 0:
            continue
        entry_price = entry_open * (1 + ROUND_TRIP_COST_PCT)
        exit_price = exit_close * (1 - ROUND_TRIP_COST_PCT)
        pnl = (exit_price - entry_price) * shares
        invested = entry_price * shares
        out.append({
            "signal_date": signal_date,
            "entry_date": forward[0].get("Date"),
            "exit_date": forward[-1].get("Date"),
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "decision": event.get("decision") or "unknown",
            "candidate_rank": event.get("candidate_rank"),
            "tags": tags,
            "timing_metrics": metrics,
            "entry_open": _round(entry_open, 4),
            "exit_close": _round(exit_close, 4),
            "shares": shares,
            "notional_usd": _round(invested, 2),
            "pnl": _round(pnl, 2),
            "return_pct": _round(pnl / invested, 6) if invested else None,
            "mfe_pct": _round((max(highs) / entry_open) - 1, 6) if highs else None,
            "mae_pct": _round((min(lows) / entry_open) - 1, 6) if lows else None,
        })
    return out


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "candidate_count": 0,
            "total_pnl": 0.0,
            "avg_return_pct": None,
            "win_rate": None,
        }
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    returns = [float(row.get("return_pct") or 0.0) for row in rows]
    positives = [value for value in pnls if value > 0]
    pnl_by_ticker: defaultdict[str, float] = defaultdict(float)
    decision_counts: Counter[str] = Counter()
    for row in rows:
        pnl_by_ticker[row["ticker"]] += float(row.get("pnl") or 0.0)
        decision_counts[row["decision"]] += 1
    positive_share = None
    if positives:
        by_ticker_positive = [value for value in pnl_by_ticker.values() if value > 0]
        if by_ticker_positive:
            positive_share = max(by_ticker_positive) / sum(by_ticker_positive)
    return {
        "candidate_count": len(rows),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2),
        "avg_return_pct": _round(sum(returns) / len(returns), 6),
        "median_return_pct": _round(sorted(returns)[len(returns) // 2], 6),
        "win_rate": _round(sum(1 for value in pnls if value > 0) / len(pnls), 4),
        "decision_counts": dict(sorted(decision_counts.items())),
        "pnl_by_ticker": {
            ticker: _round(value, 2) for ticker, value in sorted(pnl_by_ticker.items())
        },
        "max_single_ticker_positive_share": _round(positive_share, 4),
    }


def _run_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    snapshot = _load_json(REPO_ROOT / spec["snapshot"])
    backtest = _load_json(REPO_ROOT / spec["backtest_results"])
    events_payload = _load_json(REPO_ROOT / spec["candidate_events"])
    events = events_payload.get("candidate_events") or []
    rows = _event_rows(backtest, snapshot, events)
    rs20_rows = [row for row in rows if TREATMENT_TAG in row.get("tags", [])]
    missed_rows = [row for row in rs20_rows if row.get("decision") != "entered"]
    return {
        "window": name,
        "window_spec": spec,
        "platform_candidate_count": len(rows),
        "platform_rs20_candidate_count": len(rs20_rows),
        "missed_platform_rs20_count": len(missed_rows),
        "missed_stats": _stats(missed_rows),
        "missed_rows": missed_rows,
    }


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for window in by_window.values():
        rows.extend(window["missed_rows"])
    stats = _stats(rows)
    gate_passed = (
        stats["candidate_count"] >= 8
        and (stats.get("total_pnl") or 0) > 0
        and (stats.get("win_rate") or 0) >= 0.5
        and (
            stats.get("max_single_ticker_positive_share") is None
            or stats["max_single_ticker_positive_share"] <= 0.5
        )
    )
    return {
        **stats,
        "windows_with_missed_candidates": sum(
            1 for window in by_window.values() if window["missed_platform_rs20_count"] > 0
        ),
        "gate_passed": gate_passed,
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    agg = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Platform RS20 Missed Sleeve Audit",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- missed candidate count: {agg['candidate_count']}",
        f"- fixed-notional PnL: {agg['total_pnl']}",
        f"- win rate: {agg['win_rate']}",
        f"- single ticker positive share: {agg['max_single_ticker_positive_share']}",
        "",
        "## By Window",
        "",
    ]
    for name, window in payload["by_window"].items():
        stats = window["missed_stats"]
        lines.append(
            "- "
            f"{name}: count={stats['candidate_count']}, "
            f"pnl={stats['total_pnl']}, "
            f"win_rate={stats['win_rate']}"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Observed-only fixed-notional sleeve audit.",
        "- Does not change production signals, sizing, orders, or core slots.",
        "- Intended to decide whether missed platform RS20 candidates deserve a future sleeve replay.",
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
        "alpha_hypothesis_category": "allocation_sleeve_scout",
        "change_type": "observed_only_fixed_notional_replacement_sleeve_audit",
        "mechanism_family": "platform_rs20_missed_candidate_replacement_value",
        "single_causal_variable": "missed_platform_rs20_leader_candidate_fixed_notional_20d_hold",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "observed_metrics": payload["aggregate"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": payload.get("rejection_reason"),
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
    }


def main() -> None:
    by_window = OrderedDict((name, _run_window(name, spec)) for name, spec in WINDOWS.items())
    aggregate = _aggregate(by_window)
    decision = "deferred_positive" if aggregate["gate_passed"] else "observed_only_underpowered"
    rejection_reason = None
    if not aggregate["gate_passed"]:
        rejection_reason = (
            "Missed platform RS20 sleeve audit is underpowered or too concentrated: "
            f"count {aggregate['candidate_count']}, PnL {aggregate['total_pnl']}, "
            f"win rate {aggregate['win_rate']}, single ticker positive share "
            f"{aggregate['max_single_ticker_positive_share']}."
        )
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "source_experiments": SOURCE_EXPERIMENTS,
        "hypothesis": (
            "Platform-pool rs20_leader candidates missed by the core entry path may "
            "have enough replacement value to justify a future default-off sleeve."
        ),
        "decision": decision,
        "rejection_reason": rejection_reason,
        "parameters": {
            "platform_pool": PLATFORM_POOL,
            "treatment_tag": TREATMENT_TAG,
            "notional_usd": NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "promotion_gate": {
                "missed_candidate_count": ">= 8",
                "fixed_notional_total_pnl": "> 0",
                "win_rate": ">= 50%",
                "single_ticker_positive_contribution": "<= 50%",
            },
        },
        "history_check": {
            "exp-20260507-034": "Hard platform RS20 entry gate rejected.",
            "exp-20260507-033": "Entry-state risk resize rejected.",
            "mechanism_insight_conflict": (
                "Avoids nearby RS20 threshold retuning; asks replacement-value "
                "question for already missed candidates."
            ),
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "gate4": {
            "passed": None,
            "basis": "Observed-only fixed-notional replacement-value audit; not a portfolio backtest.",
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
            "blocker_relation": "LLM/news replay is locked out of this deterministic sleeve scout.",
        },
        "next_retry_requires": [
            "Do not promote a platform RS20 missed-candidate sleeve from this sample alone.",
            "A valid retry needs at least eight missed candidates with less single-ticker concentration.",
            "Future replay must be default-off and share run.py/backtester sleeve semantics.",
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
        "title": "Platform RS20 missed candidate sleeve audit",
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
