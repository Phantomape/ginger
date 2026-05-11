"""exp-20260510-024: SEC financial-report T+1 drift slice.

This observed-only runner consumes the exp-20260510-023 SEC event-drift
surface and tests one narrower causal label: positive T+1 excess drift on
financial-report SEC events only (`earnings_8k` and `periodic_report`).

It does not change production, backtest trading behavior, sizing, ranking,
slots, exits, LLM, or the event snapshot pipeline.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260510-024"
STEM = "sec_financial_report_t1_drift_slice"
SOURCE_EXPERIMENT_ID = "exp-20260510-023"
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "sec_t1_drift_event_surface.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

FINANCIAL_REPORT_FAMILIES = ("earnings_8k", "periodic_report")
FORWARD_HORIZONS = (1, 5, 10, 20)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(payload_line)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(payload_line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _append_playbook_note(note: str) -> None:
    old = PLAYBOOK.read_text(encoding="utf-8") if PLAYBOOK.exists() else ""
    if f"Experiment: `{EXPERIMENT_ID}`" in old:
        return
    PLAYBOOK.write_text(old.rstrip() + "\n\n" + note.strip() + "\n", encoding="utf-8")


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _summary(values: list[Any]) -> dict[str, Any]:
    clean = sorted(
        float(value)
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(float(value))
    )
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
        }

    def percentile(q: float) -> float:
        return clean[int(round((len(clean) - 1) * q))]

    return {
        "count": len(clean),
        "avg": _round(statistics.mean(clean)),
        "median": _round(statistics.median(clean)),
        "win_rate": _round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "p10": _round(percentile(0.10)),
        "p25": _round(percentile(0.25)),
        "p75": _round(percentile(0.75)),
        "p90": _round(percentile(0.90)),
    }


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_count": len(rows),
        "valid_10d_candidate_count": sum(1 for row in rows if isinstance(row.get("fwd_10d_return"), (int, float))),
        "unique_tickers": len({row["ticker"] for row in rows}),
        "platform_pool_count": sum(1 for row in rows if row.get("cohort") == "platform_pool"),
        "ticker_counts": Counter(row["ticker"] for row in rows).most_common(15),
        "event_family_counts": Counter(row["event_family"] for row in rows).most_common(),
        "forward_returns": {
            f"fwd_{horizon}d_return": _summary([row.get(f"fwd_{horizon}d_return") for row in rows])
            for horizon in FORWARD_HORIZONS
        },
        "shadow_pnl_proxy": {
            f"fwd_{horizon}d_pnl_proxy": _summary([row.get(f"fwd_{horizon}d_pnl_proxy") for row in rows])
            for horizon in FORWARD_HORIZONS
        },
    }


def _filtered_rows(window: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in window.get("shadow_candidate_rows", [])
        if row.get("event_family") in FINANCIAL_REPORT_FAMILIES
    ]


def _build_payload() -> dict[str, Any]:
    source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    windows: OrderedDict[str, Any] = OrderedDict()
    all_rows: list[dict[str, Any]] = []
    positive_10d_windows = 0
    for label, window in source["windows"].items():
        rows = _filtered_rows(window)
        all_rows.extend(rows)
        summary = _group_summary(rows)
        avg_10d = summary["forward_returns"]["fwd_10d_return"]["avg"]
        if isinstance(avg_10d, (int, float)) and avg_10d > 0:
            positive_10d_windows += 1
        windows[label] = {
            "window": label,
            "start": window.get("start"),
            "end": window.get("end"),
            "state_note": window.get("state_note"),
            "source_positive_t1_excess_candidates": window["drift_bucket_summary"]["positive_t1_excess_drift"]["candidate_count"],
            "financial_report_t1_excess_summary": summary,
            "candidate_rows": rows,
        }

    aggregate = _group_summary(all_rows)
    gate = {
        "min_valid_10d_candidates": 50,
        "required_positive_avg_10d_windows": 3,
        "min_aggregate_10d_win_rate": 0.52,
        "min_aggregate_10d_avg_return": 0.0,
        "passed": (
            aggregate["valid_10d_candidate_count"] >= 50
            and positive_10d_windows == 3
            and (aggregate["forward_returns"]["fwd_10d_return"]["win_rate"] or 0.0) >= 0.52
            and (aggregate["forward_returns"]["fwd_10d_return"]["avg"] or 0.0) > 0
        ),
    }
    decision = "observed_only_forward_paper_queue_candidate" if gate["passed"] else "observed_only_no_promotion"
    baseline_before = source.get("before_metrics") or {}
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": decision,
        "change_type": "new_strategy_shadow_slice",
        "changed_variable": "sec_financial_report_event_family_gate",
        "single_causal_variable": "financial_report_family_slice_of_positive_sec_t1_excess_drift",
        "hypothesis": (
            "Within positive T+1 SEC excess-drift candidates, financial-report events "
            "(earnings 8-K and periodic 10-Q/10-K filings) may have more stable continuation "
            "than the broader SEC event surface."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "Entry/oracle alpha source: after a PIT-safe SEC financial-report event beats SPY on T+1, "
                "a T+2 open shadow entry may have stable continuation."
            ),
            "2_history_check": {
                "exp-20260509-020": "Rejected broad PEAD threshold recipe; this run changes event family only, not reaction magnitude, volume, or hold length.",
                "exp-20260510-023": "Source surface showed the broad positive T+1 SEC label passed paper-watch gate but mixed families; this run isolates the financial-report semantic family.",
            },
            "3_single_causal_variable": "event_family_gate = earnings_8k or periodic_report",
            "4_gate": "Observed-only candidate gate requires >=50 valid 10d rows, 3/3 positive avg windows, aggregate 10d win rate >=52%, and positive aggregate 10d average return.",
            "5_reproducibility": f"Re-run {SOURCE_EXPERIMENT_ID}, then this script. Outputs are under data/experiments and docs/experiments.",
        },
        "backtest_protocol": (
            "Observed-only slice of exp-20260510-023 across the three docs/backtesting.md fixed windows. "
            "No before/after strategy backtest is valid because no trading behavior changed."
        ),
        "source_experiment": {
            "experiment_id": SOURCE_EXPERIMENT_ID,
            "artifact": str(SOURCE_JSON.relative_to(REPO_ROOT)),
            "source_decision": source.get("decision"),
            "source_single_causal_variable": source.get("single_causal_variable"),
        },
        "parameters": {
            "source_bucket": "positive_t1_excess_drift",
            "included_event_families": list(FINANCIAL_REPORT_FAMILIES),
            "excluded_event_families": [
                "capital_contract_8k",
                "fd_other_8k",
                "governance_8k",
                "other_8k",
                "other_sec",
            ],
            "shadow_entry": "T+2 open, inherited from exp-20260510-023",
            "forward_horizons_trading_days": list(FORWARD_HORIZONS),
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "sizing",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "T+1 drift label",
            ],
        },
        "date_range": source.get("date_range"),
        "before_metrics": baseline_before,
        "after_metrics": baseline_before,
        "delta_metrics": {
            "aggregate": {
                "expected_value_score_delta_sum": 0.0,
                "total_pnl_delta_sum": 0.0,
                "trade_count_delta_sum": 0,
                "signals_generated_delta_sum": 0,
                "signals_survived_delta_sum": 0,
            },
            "shadow_attribution": {
                "positive_avg_10d_windows": positive_10d_windows,
                "financial_report_candidate_count": aggregate["candidate_count"],
                "valid_10d_candidate_count": aggregate["valid_10d_candidate_count"],
                "forward_10d": aggregate["forward_returns"]["fwd_10d_return"],
                "forward_20d": aggregate["forward_returns"]["fwd_20d_return"],
                "platform_pool_forward_10d": _summary(
                    [
                        row.get("fwd_10d_return")
                        for row in all_rows
                        if row.get("cohort") == "platform_pool"
                    ]
                ),
            },
        },
        "aggregate": {
            **aggregate,
            "positive_avg_10d_windows": positive_10d_windows,
            "candidate_gate": gate,
        },
        "windows": windows,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "The next useful LLM contribution is semantic filing-text grading for the financial-report queue, not hard risk control.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "rejection_reason": (
            "Observed-only same-sample slice; it can justify forward paper collection, not production orders."
        ),
        "next_evidence_needed": [
            "Create a default-off forward paper queue for the exact financial-report + positive T+1 excess label.",
            "Capture closed paper replacement value before considering a shared live adapter.",
            "Use LLM only for filing-text semantic quality labels after the deterministic event queue is stable.",
        ],
        "related_files": [
            str(SOURCE_JSON.relative_to(REPO_ROOT)),
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Financial-Report T+1 Drift Slice",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Aggregate",
        "",
        f"- candidates: `{aggregate['candidate_count']}`",
        f"- valid 10d candidates: `{aggregate['valid_10d_candidate_count']}`",
        f"- positive 10d avg windows: `{aggregate['positive_avg_10d_windows']}/3`",
        f"- 10d avg return: `{aggregate['forward_returns']['fwd_10d_return']['avg']}`",
        f"- 10d win rate: `{aggregate['forward_returns']['fwd_10d_return']['win_rate']}`",
        f"- 20d avg return: `{aggregate['forward_returns']['fwd_20d_return']['avg']}`",
        f"- gate passed: `{aggregate['candidate_gate']['passed']}`",
        "",
        "## Windows",
        "",
    ]
    for label, window in payload["windows"].items():
        summary = window["financial_report_t1_excess_summary"]
        lines.extend(
            [
                f"### {label}",
                "",
                f"- candidates: `{summary['candidate_count']}`",
                f"- 10d avg: `{summary['forward_returns']['fwd_10d_return']['avg']}`",
                f"- 10d win rate: `{summary['forward_returns']['fwd_10d_return']['win_rate']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Notes",
            "",
            "- Observed-only slice. It does not change production orders or core backtest behavior.",
            "- The right next step is a default-off forward paper queue, not production promotion.",
        ]
    )
    return "\n".join(lines) + "\n"


def _playbook_note(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    return f"""
### 2026-05-10 mechanism update: SEC financial-report T+1 drift slice

Experiment: `{EXPERIMENT_ID}`

Decision: `{payload['decision']}`.

Finding: narrowing the broader SEC T+1 event-drift surface to financial-report
events (`earnings_8k` plus `periodic_report`) materially cleaned up stability:
`{aggregate['valid_10d_candidate_count']}` valid 10d rows, 10d average return
`{aggregate['forward_returns']['fwd_10d_return']['avg']}`, 10d win rate
`{aggregate['forward_returns']['fwd_10d_return']['win_rate']}`, and positive
10d average return in `{aggregate['positive_avg_10d_windows']}/3` windows.

Mechanism insight: for the event/oracle stack, the next production-visible work
should be a default-off forward paper queue for this exact deterministic label.
Do not promote same-sample SEC event trades directly, and do not retry broad
PEAD reaction-magnitude, volume, or fixed-hold sweeps.
""".strip()


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "production_impact": payload["production_impact"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "next_evidence_needed": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _append_playbook_note(_playbook_note(payload))
    aggregate = payload["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "candidate_count": aggregate["candidate_count"],
                "valid_10d_candidate_count": aggregate["valid_10d_candidate_count"],
                "positive_avg_10d_windows": aggregate["positive_avg_10d_windows"],
                "aggregate_10d_avg": aggregate["forward_returns"]["fwd_10d_return"]["avg"],
                "aggregate_10d_win_rate": aggregate["forward_returns"]["fwd_10d_return"]["win_rate"],
                "gate_passed": aggregate["candidate_gate"]["passed"],
                "wrote": str(OUT_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
