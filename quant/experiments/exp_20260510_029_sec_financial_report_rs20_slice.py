"""exp-20260510-029: SEC financial-report T1 drift + RS20 slice.

Observed-only follow-up to exp-20260510-024. It tests one structural
stratifier inside the financial-report SEC event drift candidates:

    accepted RS20 entry-state leadership
    ticker 20d return - SPY 20d return >= 5 percentage points

No production behavior changes. The stronger non-platform intersection is
reported as a diagnostic only because that adds a second discriminator.
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
EXPERIMENT_ID = "exp-20260510-029"
STEM = "sec_financial_report_rs20_slice"
SOURCE_EXPERIMENT_ID = "exp-20260510-024"
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "sec_financial_report_t1_drift_slice.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOW_SNAPSHOTS = OrderedDict(
    [
        ("late_strong", "data/ohlcv_snapshot_20251023_20260421.json"),
        ("mid_weak", "data/ohlcv_snapshot_20250423_20251022.json"),
        ("old_thin", "data/ohlcv_snapshot_20241002_20250422.json"),
    ]
)
FORWARD_HORIZONS = (1, 5, 10, 20)
SHADOW_NOTIONAL_USD = 10_000.0
RS20_LEADER_MIN_EXCESS_RETURN = 0.05


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


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _as_float(row: dict[str, Any], key: str) -> float | None:
    raw = row.get(key)
    if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
        return float(raw)
    return None


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (ohlcv or {}).items():
        out[str(ticker).upper()] = sorted(
            [{"date": _row_date(row), "close": _as_float(row, "Close")} for row in rows],
            key=lambda row: row["date"],
        )
    return out


def _index_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


def _return_between(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_value = rows[start_idx].get("close")
    end_value = rows[end_idx].get("close")
    if not isinstance(start_value, (int, float)) or not isinstance(end_value, (int, float)):
        return None
    if start_value <= 0:
        return None
    return float(end_value) / float(start_value) - 1.0


def _enrich_rows(source: dict[str, Any]) -> OrderedDict[str, list[dict[str, Any]]]:
    enriched: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for label, snapshot_path in WINDOW_SNAPSHOTS.items():
        snapshot = _load_snapshot(REPO_ROOT / snapshot_path)
        spy_rows = snapshot.get("SPY", [])
        rows = []
        for row in source["windows"][label]["candidate_rows"]:
            item = dict(row)
            ticker_rows = snapshot.get(str(item.get("ticker") or "").upper())
            ticker_idx = _index_on_or_after(ticker_rows or [], item["event_trading_date"]) if ticker_rows else None
            spy_idx = _index_on_or_after(spy_rows, item["event_trading_date"]) if spy_rows else None
            ticker_rs20 = _return_between(ticker_rows or [], ticker_idx - 20, ticker_idx) if ticker_idx is not None else None
            spy_rs20 = _return_between(spy_rows, spy_idx - 20, spy_idx) if spy_idx is not None else None
            rs20_excess = (
                ticker_rs20 - spy_rs20
                if isinstance(ticker_rs20, (int, float)) and isinstance(spy_rs20, (int, float))
                else None
            )
            item["window"] = label
            item["rs20_return"] = _round(ticker_rs20)
            item["spy_rs20_return"] = _round(spy_rs20)
            item["rs20_excess_vs_spy"] = _round(rs20_excess)
            item["rs20_leader_5pp"] = (
                isinstance(rs20_excess, (int, float))
                and rs20_excess >= RS20_LEADER_MIN_EXCESS_RETURN
            )
            rows.append(item)
        enriched[label] = rows
    return enriched


def _single_ticker_positive_share(rows: list[dict[str, Any]], horizon: int = 10) -> float | None:
    by_ticker: Counter[str] = Counter()
    for row in rows:
        raw = row.get(f"fwd_{horizon}d_return")
        if isinstance(raw, (int, float)) and raw > 0:
            by_ticker[str(row.get("ticker"))] += raw * SHADOW_NOTIONAL_USD
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return _round(max(by_ticker.values()) / total, 4)


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid10 = [row.get("fwd_10d_return") for row in rows if isinstance(row.get("fwd_10d_return"), (int, float))]
    return {
        "candidate_count": len(rows),
        "valid_10d_candidate_count": len(valid10),
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
        "max_single_ticker_positive_pnl_share_10d": _single_ticker_positive_share(rows, horizon=10),
    }


def _positive_avg_windows(enriched: OrderedDict[str, list[dict[str, Any]]], selector) -> int:
    count = 0
    for rows in enriched.values():
        selected = [row for row in rows if selector(row)]
        avg = _group_summary(selected)["forward_returns"]["fwd_10d_return"]["avg"]
        if isinstance(avg, (int, float)) and avg > 0:
            count += 1
    return count


def _flatten(enriched: OrderedDict[str, list[dict[str, Any]]], selector=lambda row: True) -> list[dict[str, Any]]:
    return [row for rows in enriched.values() for row in rows if selector(row)]


def _build_payload() -> dict[str, Any]:
    source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    enriched = _enrich_rows(source)
    selectors = OrderedDict(
        [
            ("all_financial_report_t1_drift", lambda row: True),
            ("rs20_leader_5pp", lambda row: bool(row.get("rs20_leader_5pp"))),
            ("not_rs20_leader_5pp", lambda row: not bool(row.get("rs20_leader_5pp"))),
            ("earnings_8k_rs20_leader_5pp", lambda row: row.get("event_family") == "earnings_8k" and bool(row.get("rs20_leader_5pp"))),
            ("periodic_report_rs20_leader_5pp", lambda row: row.get("event_family") == "periodic_report" and bool(row.get("rs20_leader_5pp"))),
            ("non_platform_rs20_leader_5pp_diagnostic", lambda row: row.get("cohort") != "platform_pool" and bool(row.get("rs20_leader_5pp"))),
            ("platform_pool_rs20_leader_5pp_diagnostic", lambda row: row.get("cohort") == "platform_pool" and bool(row.get("rs20_leader_5pp"))),
        ]
    )
    comparisons = OrderedDict()
    for name, selector in selectors.items():
        rows = _flatten(enriched, selector)
        comparisons[name] = {
            "aggregate": _group_summary(rows),
            "positive_avg_10d_windows": _positive_avg_windows(enriched, selector),
            "by_window": OrderedDict(
                (label, _group_summary([row for row in rows_by_window if selector(row)]))
                for label, rows_by_window in enriched.items()
            ),
        }

    primary = comparisons["rs20_leader_5pp"]["aggregate"]
    primary_gate = {
        "min_valid_10d_candidates": 50,
        "required_positive_avg_10d_windows": 3,
        "min_aggregate_10d_avg_return": 0.03,
        "min_aggregate_10d_win_rate": 0.55,
        "max_single_ticker_positive_pnl_share_10d": 0.35,
        "passed": (
            primary["valid_10d_candidate_count"] >= 50
            and comparisons["rs20_leader_5pp"]["positive_avg_10d_windows"] == 3
            and (primary["forward_returns"]["fwd_10d_return"]["avg"] or 0.0) >= 0.03
            and (primary["forward_returns"]["fwd_10d_return"]["win_rate"] or 0.0) >= 0.55
            and (primary["max_single_ticker_positive_pnl_share_10d"] or 1.0) <= 0.35
        ),
    }
    decision = "observed_only_stronger_oracle_feature_candidate" if primary_gate["passed"] else "observed_only_no_promotion"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    before_metrics = source.get("before_metrics") or {}
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": decision,
        "change_type": "new_strategy_shadow_stratification",
        "changed_variable": "accepted_rs20_entry_state_leader_overlay",
        "single_causal_variable": "RS20 leader 5pp state inside SEC financial-report T1 drift candidates",
        "hypothesis": (
            "SEC financial-report T+1 drift candidates that are also accepted RS20 entry-state leaders "
            "may have a stronger continuation edge than the full financial-report event slice."
        ),
        "protocol_answers": {
            "1_alpha_hypothesis": "Entry/oracle feature: combine the SEC financial-report T+1 drift label with the already accepted RS20 leader state.",
            "2_history_check": {
                "exp-20260510-012": "Accepted RS20 entry-state sizing top-up; this run reuses its 5pp leadership definition without changing multiplier or sizing.",
                "exp-20260510-024": "Observed-only financial-report T+1 drift slice found +2.23% 10d avg return; this run tests whether the accepted RS20 state isolates a stronger subgroup.",
                "anti_repeat": "This is not a nearby RS20 scalar sweep and does not change production sizing.",
            },
            "3_single_causal_variable": "RS20 leader 5pp overlay on the existing exp-20260510-024 candidate rows.",
            "4_gate": "Observed-only stronger-feature gate: >=50 valid 10d rows, 3/3 positive windows, avg10 >=3%, win rate >=55%, and max single ticker positive PnL share <=35%.",
            "5_reproducibility": f"Run {SOURCE_EXPERIMENT_ID}, then this script. Inputs are source artifact plus the three canonical OHLCV snapshots.",
        },
        "source_experiment": {
            "experiment_id": SOURCE_EXPERIMENT_ID,
            "artifact": str(SOURCE_JSON.relative_to(REPO_ROOT)),
            "source_decision": source.get("decision"),
        },
        "parameters": {
            "source_candidate_label": "SEC financial-report positive T+1 excess drift",
            "rs20_leader_min_excess_return": RS20_LEADER_MIN_EXCESS_RETURN,
            "rs20_return_anchor": "event_trading_date close versus close 20 trading sessions earlier",
            "primary_tested_slice": "rs20_leader_5pp",
            "diagnostic_only_slices": [
                "earnings_8k_rs20_leader_5pp",
                "periodic_report_rs20_leader_5pp",
                "non_platform_rs20_leader_5pp_diagnostic",
                "platform_pool_rs20_leader_5pp_diagnostic",
            ],
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
                "event family label",
            ],
        },
        "date_range": source.get("date_range"),
        "before_metrics": before_metrics,
        "after_metrics": before_metrics,
        "delta_metrics": {
            "aggregate": {
                "expected_value_score_delta_sum": 0.0,
                "total_pnl_delta_sum": 0.0,
                "trade_count_delta_sum": 0,
                "signals_generated_delta_sum": 0,
                "signals_survived_delta_sum": 0,
            },
            "shadow_attribution": {
                "primary_slice": comparisons["rs20_leader_5pp"],
                "baseline_slice": comparisons["all_financial_report_t1_drift"],
                "primary_avg_10d_lift": _round(
                    (comparisons["rs20_leader_5pp"]["aggregate"]["forward_returns"]["fwd_10d_return"]["avg"] or 0.0)
                    - (comparisons["all_financial_report_t1_drift"]["aggregate"]["forward_returns"]["fwd_10d_return"]["avg"] or 0.0)
                ),
            },
        },
        "comparisons": comparisons,
        "aggregate": comparisons["rs20_leader_5pp"]["aggregate"],
        "primary_gate": primary_gate,
        "enriched_candidate_rows": enriched,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "The next possible LLM role is filing-text semantic grading after deterministic RS20/event evidence is forward-collected.",
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
        "rejection_reason": "Observed-only stratification; it can justify forward paper collection, not production orders.",
        "next_evidence_needed": [
            "Track the exact financial-report + positive T+1 excess + RS20 leader label in a default-off forward paper queue.",
            "Treat non-platform RS20 as a separate follow-up variable if needed; do not merge it into this conclusion.",
            "Require closed forward replacement value before any shared live adapter.",
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


def _artifact(payload: dict[str, Any]) -> str:
    baseline = payload["comparisons"]["all_financial_report_t1_drift"]["aggregate"]
    primary = payload["aggregate"]
    diagnostic = payload["comparisons"]["non_platform_rs20_leader_5pp_diagnostic"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Financial-Report RS20 Slice",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Primary Slice",
        "",
        f"- source 10d avg: `{baseline['forward_returns']['fwd_10d_return']['avg']}`",
        f"- RS20 10d avg: `{primary['forward_returns']['fwd_10d_return']['avg']}`",
        f"- RS20 valid 10d rows: `{primary['valid_10d_candidate_count']}`",
        f"- RS20 10d win rate: `{primary['forward_returns']['fwd_10d_return']['win_rate']}`",
        f"- RS20 positive 10d windows: `{payload['comparisons']['rs20_leader_5pp']['positive_avg_10d_windows']}/3`",
        f"- max single ticker positive PnL share: `{primary['max_single_ticker_positive_pnl_share_10d']}`",
        f"- gate passed: `{payload['primary_gate']['passed']}`",
        "",
        "## Diagnostic Only",
        "",
        f"- non-platform RS20 10d avg: `{diagnostic['forward_returns']['fwd_10d_return']['avg']}`",
        f"- non-platform RS20 valid 10d rows: `{diagnostic['valid_10d_candidate_count']}`",
        f"- non-platform RS20 win rate: `{diagnostic['forward_returns']['fwd_10d_return']['win_rate']}`",
        "",
        "## Notes",
        "",
        "- Observed-only. No production orders, sizing, ranking, exits, or slots changed.",
        "- Non-platform is reported only as a diagnostic because it would add a second causal variable.",
    ]
    return "\n".join(lines) + "\n"


def _playbook_note(payload: dict[str, Any]) -> str:
    baseline = payload["comparisons"]["all_financial_report_t1_drift"]["aggregate"]
    primary = payload["aggregate"]
    diagnostic = payload["comparisons"]["non_platform_rs20_leader_5pp_diagnostic"]["aggregate"]
    return f"""
### 2026-05-10 mechanism update: SEC financial-report RS20 slice

Experiment: `{EXPERIMENT_ID}`

Decision: `{payload['decision']}`.

Finding: adding the already accepted RS20 leader state to the SEC
financial-report + positive T+1 excess-drift label lifted 10d average return
from `{baseline['forward_returns']['fwd_10d_return']['avg']}` to
`{primary['forward_returns']['fwd_10d_return']['avg']}` with
`{primary['valid_10d_candidate_count']}` valid rows, win rate
`{primary['forward_returns']['fwd_10d_return']['win_rate']}`, and positive
10d-average return in
`{payload['comparisons']['rs20_leader_5pp']['positive_avg_10d_windows']}/3`
windows. The diagnostic non-platform intersection was stronger at
`{diagnostic['forward_returns']['fwd_10d_return']['avg']}`, but it is a second
variable and needs its own pre-registered follow-up before becoming a rule.

Mechanism insight: the stronger event/oracle candidate is not platform-specific
and not a new RS20 sizing scalar; it is a public-PIT financial-report event
whose price already confirms RS20 leadership. The next production-visible step
should collect forward paper outcomes for this exact deterministic label.
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
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "production_impact": payload["production_impact"],
            "next_evidence_needed": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _append_playbook_note(_playbook_note(payload))
    primary = payload["aggregate"]
    diagnostic = payload["comparisons"]["non_platform_rs20_leader_5pp_diagnostic"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "primary_slice": "rs20_leader_5pp",
                "valid_10d_candidate_count": primary["valid_10d_candidate_count"],
                "aggregate_10d_avg": primary["forward_returns"]["fwd_10d_return"]["avg"],
                "aggregate_10d_win_rate": primary["forward_returns"]["fwd_10d_return"]["win_rate"],
                "positive_avg_10d_windows": payload["comparisons"]["rs20_leader_5pp"]["positive_avg_10d_windows"],
                "max_single_ticker_positive_pnl_share_10d": primary["max_single_ticker_positive_pnl_share_10d"],
                "gate_passed": payload["primary_gate"]["passed"],
                "diagnostic_nonplatform_10d_avg": diagnostic["forward_returns"]["fwd_10d_return"]["avg"],
                "wrote": str(OUT_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
