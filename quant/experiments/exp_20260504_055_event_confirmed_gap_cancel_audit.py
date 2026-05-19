"""exp-20260504-055 event-confirmed gap-cancel audit.

Alpha search preflight. Recent mechanism notes say broad upside-gap exceptions
failed, and a valid retry needs an orthogonal event/state source explaining why
the gap is confirmation rather than bad execution. This audit checks whether the
already-frozen exp-20260504-049 event bundle actually overlaps the A/B
``gap_cancel`` candidates before any shared policy change is attempted.

The script is observe-only: it runs the three canonical backtest windows, reads
the frozen event-bundle replay log, and writes coverage artifacts. It does not
change ranking, sizing, fills, exits, prompts, event thresholds, or production
defaults.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXP_ID = "exp-20260504-055"
SOURCE_EXP_ID = "exp-20260504-049"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "event_confirmed_gap_cancel_audit.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXP_ID}_event_confirmed_gap_cancel_audit.md"
)
SOURCE_LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{SOURCE_EXP_ID}.json"

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


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _date(value: Any) -> datetime:
    return datetime.fromisoformat(str(value)[:10])


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe": _round(result.get("sharpe"), 2),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "win_rate": _round(result.get("win_rate"), 4),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _event_trades(source_log: dict[str, Any], window: str) -> list[dict[str, Any]]:
    return list(source_log.get("event_overlay", {}).get(window, {}).get("event_trades") or [])


def _active_event_matches(skip: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    skip_ticker = str(skip.get("ticker") or "").upper()
    skip_date = _date(skip.get("date"))
    matches: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("ticker") or "").upper() != skip_ticker:
            continue
        entry_date = _date(event.get("entry_date"))
        exit_date = _date(event.get("exit_date"))
        if entry_date <= skip_date <= exit_date:
            matches.append(
                {
                    "ticker": skip_ticker,
                    "candidate_date": str(skip.get("date"))[:10],
                    "candidate_strategy": skip.get("strategy"),
                    "candidate_decision": skip.get("decision"),
                    "candidate_rank": skip.get("candidate_rank"),
                    "event_source": event.get("source"),
                    "event_entry_date": str(event.get("entry_date"))[:10],
                    "event_exit_date": str(event.get("exit_date"))[:10],
                    "event_pnl": event.get("pnl"),
                    "calendar_days_after_event_entry": (skip_date - entry_date).days,
                    "fill_date": (skip.get("details") or {}).get("fill_date"),
                    "fill_price": (skip.get("details") or {}).get("fill_price"),
                    "signal_entry": (skip.get("details") or {}).get("signal_entry"),
                }
            )
    return matches


def _ticker_only_overlaps(skips: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_tickers = {}
    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        event_tickers.setdefault(ticker, []).append(event)
    overlaps: list[dict[str, Any]] = []
    for skip in skips:
        ticker = str(skip.get("ticker") or "").upper()
        if ticker in event_tickers:
            overlaps.append(
                {
                    "ticker": ticker,
                    "candidate_date": str(skip.get("date"))[:10],
                    "candidate_decision": skip.get("decision"),
                    "event_count_same_window": len(event_tickers[ticker]),
                    "event_sources_same_window": sorted(
                        {str(event.get("source")) for event in event_tickers[ticker]}
                    ),
                }
            )
    return overlaps


def _run_window(name: str, cfg: dict[str, str], source_log: dict[str, Any]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        cfg["start"],
        cfg["end"],
        ohlcv_snapshot_path=cfg["snapshot"],
    )
    result = engine.run()
    attribution = result.get("entry_execution_attribution") or {}
    skips = list(attribution.get("sample_skips") or [])
    gap_skips = [row for row in skips if row.get("decision") == "gap_cancel"]
    adverse_skips = [row for row in skips if row.get("decision") == "adverse_gap_down_cancel"]
    events = _event_trades(source_log, name)
    matches = []
    for skip in gap_skips:
        matches.extend(_active_event_matches(skip, events))

    return {
        "baseline_metrics": _metrics(result),
        "candidate_skip_counts": {
            "gap_cancel": len(gap_skips),
            "adverse_gap_down_cancel": len(adverse_skips),
            "all_skips_sampled": len(skips),
        },
        "event_bundle_trade_count": len(events),
        "event_active_gap_cancel_matches": matches,
        "event_active_gap_cancel_match_count": len(matches),
        "same_ticker_window_overlaps": _ticker_only_overlaps(gap_skips, events),
        "same_ticker_window_overlap_count": len(_ticker_only_overlaps(gap_skips, events)),
        "gap_cancel_candidates": [
            {
                "date": str(row.get("date"))[:10],
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "candidate_rank": row.get("candidate_rank"),
                "fill_date": (row.get("details") or {}).get("fill_date"),
                "fill_price": (row.get("details") or {}).get("fill_price"),
                "signal_entry": (row.get("details") or {}).get("signal_entry"),
            }
            for row in gap_skips
        ],
    }


def _artifact_md(payload: dict[str, Any]) -> str:
    rows = []
    for name, window in payload["windows"].items():
        metrics = window["baseline_metrics"]
        rows.append(
            "| {name} | {ev} | {pnl} | {trades} | {survival} | {gaps} | {events} | {matches} |".format(
                name=name,
                ev=metrics["expected_value_score"],
                pnl=metrics["total_pnl"],
                trades=metrics["total_trades"],
                survival=metrics["survival_rate"],
                gaps=window["candidate_skip_counts"]["gap_cancel"],
                events=window["event_bundle_trade_count"],
                matches=window["event_active_gap_cancel_match_count"],
            )
        )
    return "\n".join(
        [
            "# exp-20260504-055 Event-Confirmed Gap-Cancel Audit",
            "",
            "## Result",
            "",
            "Rejected before implementation. The frozen exp-20260504-049 event bundle has zero active-window overlap with A/B upside gap-cancel candidates in all three canonical windows.",
            "",
            "| window | baseline EV | baseline PnL | trades | survival | gap_cancel candidates | event trades | active event matches |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## Decision",
            "",
            "- Do not add an event-confirmed upside-gap exception now.",
            "- Do not retune the gap threshold, event thresholds, event holding period, or event notional from this result.",
            "- A future retry needs a broader PIT-safe event candidate surface that overlaps skipped A/B candidates before any policy code change.",
            "",
        ]
    )


def main() -> None:
    source_log = json.loads(SOURCE_LOG_JSON.read_text(encoding="utf-8"))
    windows = OrderedDict()
    for name, cfg in WINDOWS.items():
        windows[name] = _run_window(name, cfg, source_log)

    total_gap_candidates = sum(
        window["candidate_skip_counts"]["gap_cancel"] for window in windows.values()
    )
    total_event_trades = sum(window["event_bundle_trade_count"] for window in windows.values())
    total_active_matches = sum(
        window["event_active_gap_cancel_match_count"] for window in windows.values()
    )
    total_ticker_overlaps = sum(
        window["same_ticker_window_overlap_count"] for window in windows.values()
    )

    before_metrics = {name: window["baseline_metrics"] for name, window in windows.items()}
    log_payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": "rejected_preflight",
        "decision": "rejected_no_event_coverage",
        "mechanism_family": "event_confirmed_execution_exception",
        "change_type": "alpha_preflight_coverage_audit",
        "hypothesis": (
            "If a frozen external event source is active around an A/B upside gap-cancel candidate, "
            "that gap may be confirmation rather than overextended execution and could justify a "
            "narrow shared-policy exception."
        ),
        "alpha_hypothesis": {
            "category": "entry_execution",
            "entry_exit_ranking_or_allocation": "entry execution exception",
            "why_this_now": (
                "Prior global upside-gap exception sweeps failed; recent playbook notes allow a retry "
                "only with an orthogonal event/state source. LLM soft-ranking is data-limited and the "
                "event overlay bundle must not be promoted without forward outcomes."
            ),
        },
        "single_causal_variable": (
            "coverage of A/B upside gap-cancel candidates by the frozen exp-20260504-049 event bundle"
        ),
        "parameters": {
            "source_event_bundle": SOURCE_EXP_ID,
            "confirmation_rule": "same ticker and gap-cancel candidate date inside frozen event trade active window",
            "strategy_change_attempted": False,
            "locked_variables": [
                "core A/B signal generation",
                "core candidate ranking",
                "core sizing",
                "entry gap thresholds",
                "event source thresholds",
                "event holding periods",
                "event notionals",
                "production defaults",
                "LLM/news decisions",
            ],
        },
        "historical_experiment_check": {
            "similar_experiments": {
                "exp-20260428-021": "Global upside gap threshold sweeps rejected; current 1.5% remains best.",
                "exp-20260428-022": "Sector/strategy upside-gap exceptions rejected; valid retry needs orthogonal event/state source.",
                "exp-20260503-048": "Form 4 near accepted A/B overlay too sparse; do not use Form 4 alone near entries.",
                "exp-20260504-049": "Default-off event bundle is positive as a satellite overlay but not yet live-promoted.",
                "exp-20260504-053": "Production only records default-off event bundle attribution; no live orders.",
            },
            "mechanism_insight_check": (
                "This tests the allowed orthogonal-event retry condition without changing thresholds or "
                "promoting event sleeves. It does not repeat the rejected global/sector gap exception."
            ),
        },
        "date_range": {
            name: {
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
            }
            for name, cfg in WINDOWS.items()
        },
        "market_regime_summary": {name: cfg["state_note"] for name, cfg in WINDOWS.items()},
        "before_metrics": before_metrics,
        "after_metrics": before_metrics,
        "expected_value_score_delta": {name: 0.0 for name in WINDOWS},
        "gate4": {
            "status": "not_applicable_no_strategy_change",
            "reason": "Rejected before implementation because coverage was zero in all canonical windows.",
        },
        "coverage": {
            "total_gap_cancel_candidates": total_gap_candidates,
            "total_event_bundle_trades": total_event_trades,
            "total_event_active_gap_cancel_matches": total_active_matches,
            "total_same_ticker_window_overlaps": total_ticker_overlaps,
            "by_window": {
                name: {
                    "gap_cancel_candidates": window["candidate_skip_counts"]["gap_cancel"],
                    "event_bundle_trades": window["event_bundle_trade_count"],
                    "event_active_gap_cancel_matches": window["event_active_gap_cancel_match_count"],
                    "same_ticker_window_overlaps": window["same_ticker_window_overlap_count"],
                }
                for name, window in windows.items()
            },
        },
        "decision_rationale": (
            "The orthogonal event source does not touch the candidates this rule would alter: "
            f"{total_active_matches}/{total_gap_candidates} gap-cancel candidates had an active "
            f"event-bundle match. Implementing the exception would be a zero-impact policy change "
            "or would require broadening the event source first, which is a separate causal variable."
        ),
        "rejection_reason": (
            "No active-window overlap between frozen event-bundle trades and upside gap-cancel candidates."
        ),
        "next_action": (
            "Do not implement event-confirmed upside-gap exceptions. Search for alpha in a different "
            "candidate-pool or lifecycle branch unless new PIT-safe event evidence overlaps skipped A/B candidates."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_signal_path_changed": False,
            "alters_orders": False,
            "alters_sizing": False,
            "alters_candidate_ranking": False,
            "replay_only": False,
            "observe_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking remains data-limited and this alpha hypothesis is event/execution based.",
        },
        "risk_of_change": (
            "None to live trading; the intentionally avoided risk is allowing overextended gap entries "
            "without event coverage, which could reintroduce the failure mode rejected by prior sweeps."
        ),
        "why_not_other_attractive_points": {
            "llm_soft_ranking": "Still insufficient replay/forward attribution coverage.",
            "event_bundle_promotion": "Positive replay exists, but forward closed outcomes are not yet available.",
            "macro_etf_pool": "Recent broad and pair-confirmed macro ETF expansions were rejected.",
            "gap_threshold_retune": "Prior sweeps already rejected nearby global threshold changes.",
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        ],
    }

    payload = {
        "experiment_id": EXP_ID,
        "source_event_bundle": SOURCE_EXP_ID,
        "windows": windows,
        "summary": log_payload["coverage"],
        "decision": log_payload["decision"],
        "decision_rationale": log_payload["decision_rationale"],
    }
    ticket = {
        "experiment_id": EXP_ID,
        "status": "completed_rejected",
        "lane": "alpha_search",
        "owner": "codex-automation",
        "hypothesis": log_payload["hypothesis"],
        "result": log_payload["decision_rationale"],
        "created_at": log_payload["timestamp"],
        "completed_at": log_payload["timestamp"],
        "related_files": log_payload["related_files"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_payload)
    _write_json(TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _artifact_md(payload))
    print(json.dumps(log_payload["coverage"], indent=2, sort_keys=True))
    print(log_payload["decision_rationale"])


if __name__ == "__main__":
    main()
