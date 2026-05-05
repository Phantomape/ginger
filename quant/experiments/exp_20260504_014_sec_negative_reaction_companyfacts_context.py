"""Shadow-test SEC negative reaction events with Companyfacts context.

This experiment intentionally does not alter core strategy behavior. It tests
whether PIT-safe latest-prior SEC Companyfacts buckets make the already frozen
SEC negative-language + negative-reaction event packet more discriminating.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


EXPERIMENT_ID = "exp-20260504-014"
ROOT = Path(__file__).resolve().parents[2]

SEC_PACKET_PATH = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260504-008"
    / "sec_negative_reaction_absorption.json"
)
COMPANYFACTS_PATH = (
    ROOT
    / "data"
    / "non_ohlcv"
    / "sec_companyfacts_selected_20241002_20260421.jsonl"
)
RESULT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
LOG_PATH = ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_PATH = ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
AUDIT_PATH = (
    ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_negative_reaction_companyfacts_context_20260504.md"
)
EXPERIMENT_LOG_PATH = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_PATH = ROOT / "docs" / "experiment_registry.json"

BASELINE_3WINDOW = {
    "late_strong": {
        "expected_value_score": 3.4191,
        "sharpe_daily": 4.35,
        "total_pnl": 78600.33,
        "total_return_pct": 0.786,
        "max_drawdown_pct": 0.0541,
        "win_rate": 0.7895,
        "trade_count": 19,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
        "vs_spy_pct": 0.7319,
        "vs_qqq_pct": 0.728,
    },
    "mid_weak": {
        "expected_value_score": 1.4415,
        "sharpe_daily": 2.62,
        "total_pnl": 55015.08,
        "total_return_pct": 0.5502,
        "max_drawdown_pct": 0.0879,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
        "vs_spy_pct": 0.2958,
        "vs_qqq_pct": 0.2151,
    },
    "old_thin": {
        "expected_value_score": 0.3179,
        "sharpe_daily": 1.29,
        "total_pnl": 24642.07,
        "total_return_pct": 0.2464,
        "max_drawdown_pct": 0.0805,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 55,
        "survival_rate": 0.9167,
        "vs_spy_pct": 0.3137,
        "vs_qqq_pct": 0.3213,
    },
}

SEVERE_FLAGS = {
    "negative_net_income",
    "negative_operating_income",
    "negative_operating_cash_flow",
    "negative_gross_profit",
    "negative_free_cash_flow_proxy",
    "high_liabilities_to_assets",
}


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value)!r}")


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def load_primary_events() -> list[dict[str, Any]]:
    with SEC_PACKET_PATH.open("r", encoding="utf-8") as handle:
        packet = json.load(handle)
    return packet["shadow_metrics"]["primary_negative_language_negative_reaction"][
        "sample_events"
    ]


def load_companyfacts() -> tuple[
    dict[tuple[str, str], list[dict[str, Any]]], dict[str, list[dict[str, Any]]]
]:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with COMPANYFACTS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            ticker = row.get("ticker")
            accession = row.get("accession_number")
            if not ticker:
                continue
            if accession:
                by_key[(ticker, accession)].append(row)
            by_ticker[ticker].append(row)

    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row.get("filed") or "",
                row.get("end") or "",
                row.get("duration_days") or 0,
            )
        )

    return by_key, by_ticker


def select_asof_facts(
    event: dict[str, Any],
    by_key: dict[tuple[str, str], list[dict[str, Any]]],
    by_ticker: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, float], str, list[dict[str, Any]]]:
    ticker = event["ticker"]
    accession = event["accession_number"]
    usable_date = event["usable_trade_date"]

    rows = by_key.get((ticker, accession), [])
    source = "same_accession"
    if not rows:
        source = "latest_prior"
        rows = [
            row
            for row in by_ticker.get(ticker, [])
            if (row.get("filed") or "") <= usable_date
        ]
        if rows:
            max_filed = max(row.get("filed") or "" for row in rows)
            rows = [row for row in rows if (row.get("filed") or "") == max_filed]

    selected: dict[str, tuple[float, int]] = {}
    for row in rows:
        canonical = row.get("canonical")
        raw_value = row.get("value")
        if not canonical or raw_value is None:
            continue

        duration_days = row.get("duration_days")
        duration_score = 0 if duration_days is None else -abs(int(duration_days) - 91)
        current = selected.get(canonical)
        if current is None or duration_score > current[1]:
            selected[canonical] = (float(raw_value), duration_score)

    return {key: value for key, (value, _) in selected.items()}, source, rows


def classify_companyfacts(facts: dict[str, float]) -> tuple[str, list[str]]:
    if not facts:
        return "companyfacts_unavailable", []

    flags: list[str] = []
    if facts.get("net_income") is not None and facts["net_income"] < 0:
        flags.append("negative_net_income")
    if facts.get("operating_income") is not None and facts["operating_income"] < 0:
        flags.append("negative_operating_income")
    if (
        facts.get("operating_cash_flow") is not None
        and facts["operating_cash_flow"] < 0
    ):
        flags.append("negative_operating_cash_flow")
    if facts.get("gross_profit") is not None and facts["gross_profit"] < 0:
        flags.append("negative_gross_profit")
    if facts.get("operating_cash_flow") is not None and facts.get("capex") is not None:
        free_cash_flow_proxy = facts["operating_cash_flow"] - abs(facts["capex"])
        if free_cash_flow_proxy < 0:
            flags.append("negative_free_cash_flow_proxy")
    if facts.get("assets") and facts.get("liabilities"):
        if facts["liabilities"] / facts["assets"] > 0.8:
            flags.append("high_liabilities_to_assets")

    severe_count = len([flag for flag in flags if flag in SEVERE_FLAGS])
    has_positive_evidence = any(
        facts.get(key) is not None and facts[key] > 0
        for key in (
            "revenue",
            "gross_profit",
            "operating_income",
            "net_income",
            "operating_cash_flow",
        )
    )

    if severe_count >= 2:
        return "fundamental_pressure", flags
    if has_positive_evidence and severe_count <= 1:
        return "pressure_but_not_terminal", flags
    return "mixed_or_unknown", flags


def horizon_value(event: dict[str, Any], horizon: str, field: str) -> float | None:
    payload = event.get("horizons", {}).get(horizon, {})
    if payload.get("status") != "valid":
        return None
    value = payload.get(field)
    return None if value is None else float(value)


def summarize_rows(rows: list[dict[str, Any]], group_key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row[group_key]].append(row)

    output: dict[str, Any] = {}
    for key, group_rows in sorted(grouped.items()):
        excess_10d = [
            row["excess_return_10d"]
            for row in group_rows
            if row["excess_return_10d"] is not None
        ]
        excess_20d = [
            row["excess_return_20d"]
            for row in group_rows
            if row["excess_return_20d"] is not None
        ]
        output[key] = {
            "event_count": len(group_rows),
            "valid_10d_count": len(excess_10d),
            "avg_10d_excess_return_pct": _round_or_none(
                mean(excess_10d) * 100 if excess_10d else None, 6
            ),
            "median_10d_excess_return_pct": _round_or_none(
                median(excess_10d) * 100 if excess_10d else None, 6
            ),
            "positive_10d_rate": _round_or_none(
                sum(value > 0 for value in excess_10d) / len(excess_10d)
                if excess_10d
                else None,
                6,
            ),
            "valid_20d_count": len(excess_20d),
            "avg_20d_excess_return_pct": _round_or_none(
                mean(excess_20d) * 100 if excess_20d else None, 6
            ),
            "positive_20d_rate": _round_or_none(
                sum(value > 0 for value in excess_20d) / len(excess_20d)
                if excess_20d
                else None,
                6,
            ),
            "windows": dict(Counter(row["window"] for row in group_rows)),
            "tickers": sorted({row["ticker"] for row in group_rows}),
        }
    return output


def build_event_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key, by_ticker = load_companyfacts()
    rows: list[dict[str, Any]] = []

    for event in events:
        facts, source, raw_rows = select_asof_facts(event, by_key, by_ticker)
        bucket, flags = classify_companyfacts(facts)
        rows.append(
            {
                "ticker": event["ticker"],
                "window": event["window"],
                "usable_trade_date": event["usable_trade_date"],
                "entry_date": event.get("entry_date"),
                "accession_number": event["accession_number"],
                "reaction_excess_return_pct": round(
                    float(event.get("reaction_excess_return") or 0.0) * 100, 6
                ),
                "companyfacts_source": source,
                "companyfacts_row_count": len(raw_rows),
                "selected_fact_count": len(facts),
                "companyfacts_bucket": bucket,
                "companyfacts_flags": flags,
                "selected_facts_present": sorted(facts.keys()),
                "excess_return_10d": horizon_value(event, "10d", "excess_return"),
                "excess_return_20d": horizon_value(event, "20d", "excess_return"),
                "raw_return_10d": horizon_value(event, "10d", "return"),
                "raw_return_20d": horizon_value(event, "20d", "return"),
            }
        )

    return rows


def decide(bucket_summary: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[str, str]:
    pressure = bucket_summary.get("pressure_but_not_terminal", {})
    fundamental = bucket_summary.get("fundamental_pressure", {})
    same_accession_count = sum(
        row["companyfacts_source"] == "same_accession" for row in rows
    )

    if same_accession_count == 0:
        return (
            "rejected_no_companyfacts_discriminator",
            "All events joined only to latest-prior Companyfacts, so the context is stale relative to the 8-K reaction date.",
        )

    if (
        pressure.get("valid_10d_count", 0) >= 5
        and pressure.get("avg_10d_excess_return_pct") is not None
        and fundamental.get("avg_10d_excess_return_pct") is not None
        and pressure["avg_10d_excess_return_pct"]
        > fundamental["avg_10d_excess_return_pct"]
    ):
        return (
            "shadow_promising_not_promoted",
            "The recoverable-pressure bucket outperformed fundamental pressure, but this remains a shadow-only event classifier.",
        )

    return (
        "rejected_no_companyfacts_discriminator",
        "The fixed Companyfacts buckets did not improve the SEC negative-reaction packet and should not be promoted.",
    )


def build_result() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    events = load_primary_events()
    event_rows = build_event_rows(events)
    bucket_summary = summarize_rows(event_rows, "companyfacts_bucket")
    source_summary = summarize_rows(event_rows, "companyfacts_source")
    window_summary = summarize_rows(event_rows, "window")
    decision, decision_rationale = decide(bucket_summary, event_rows)

    all_valid_10d = [
        row["excess_return_10d"]
        for row in event_rows
        if row["excess_return_10d"] is not None
    ]
    all_valid_20d = [
        row["excess_return_20d"]
        for row in event_rows
        if row["excess_return_20d"] is not None
    ]

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "rejected",
        "decision": decision,
        "hypothesis": (
            "PIT-safe latest-prior Companyfacts context may separate recoverable "
            "negative SEC reaction events from genuine fundamental deterioration "
            "inside the frozen SEC negative-language + negative-reaction packet."
        ),
        "alpha_hypothesis": {
            "category": "event_source_context",
            "entry_or_ranking": "event_packet_qualification",
            "text": (
                "SEC 8-K negative-language events that sell off despite non-terminal "
                "fundamental context may rebound better than events with hard "
                "fundamental deterioration."
            ),
        },
        "change_type": "non_ohlcv_event_context_shadow_test",
        "single_causal_variable": (
            "Companyfacts context bucket layered on frozen SEC negative-reaction events"
        ),
        "historical_experiment_check": {
            "prior_same_family": {
                "exp-20260504-004": (
                    "Simple Companyfacts financial-quality score was not monotonic "
                    "and was not promoted."
                ),
                "exp-20260504-008": (
                    "SEC negative-language + negative-reaction packet was shadow "
                    "promising before capacity charging."
                ),
                "exp-20260504-010": (
                    "Standalone SEC event sleeve was positive but concentrated."
                ),
                "exp-20260504-011": (
                    "SEC event replacement value was inconclusive and blocked "
                    "core promotion."
                ),
                "exp-20260504-012": (
                    "A default-off forward SEC queue was added only for observation."
                ),
            },
            "why_this_is_not_repeat": (
                "This does not tune SEC keywords, reaction thresholds, sleeve sizing, "
                "or replacement slots. It tests one orthogonal context variable: "
                "PIT-safe Companyfacts bucket attribution on the frozen packet."
            ),
            "mechanism_insight_check": (
                "Complies with the playbook ban on direct SEC queue promotion and "
                "raw reaction-threshold sweeps; LLM soft-ranking remains blocked by "
                "sparse replay joins, so this uses a structured non-OHLCV context."
            ),
        },
        "parameters": {
            "primary_packet_source": str(SEC_PACKET_PATH.relative_to(ROOT)),
            "companyfacts_source": str(COMPANYFACTS_PATH.relative_to(ROOT)),
            "packet_rule": (
                "8-K Item 2.02 AND language_bucket == negative_language AND "
                "reaction_excess_return < 0"
            ),
            "companyfacts_pit_rule": "filed <= usable_trade_date; same accession preferred if present",
            "bucket_rules": {
                "fundamental_pressure": "at least two severe pressure flags",
                "pressure_but_not_terminal": (
                    "positive revenue/gross profit/operating income/net income/"
                    "operating cash flow evidence and no more than one severe flag"
                ),
                "mixed_or_unknown": "everything else with available facts",
                "companyfacts_unavailable": "no PIT-safe facts found",
            },
            "severe_flags": sorted(SEVERE_FLAGS),
            "locked_variables": [
                "SEC text language rule",
                "reaction threshold",
                "core A/B signal generation",
                "core A/B ranking",
                "core sizing",
                "core exits",
                "production orders",
                "LLM prompts",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            "late_strong": "slow-melt bull / accepted-stack dominant tape",
            "mid_weak": "rotation-heavy bull where accepted stack makes money but lags indexes",
            "old_thin": "mixed-to-weak older tape with lower win rate",
        },
        "before_metrics": BASELINE_3WINDOW,
        "after_metrics": BASELINE_3WINDOW,
        "expected_value_score_delta": {
            "late_strong": 0.0,
            "mid_weak": 0.0,
            "old_thin": 0.0,
            "production": 0.0,
        },
        "gate4": {
            "applicable": False,
            "core_strategy_changed": False,
            "result": "not_applicable_shadow_attribution_only",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "production_impact": "shadow_only_no_strategy_logic_changed",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "data_availability": {
            "sec_packet_event_count": len(event_rows),
            "valid_10d_event_count": len(all_valid_10d),
            "valid_20d_event_count": len(all_valid_20d),
            "same_accession_companyfacts_count": sum(
                row["companyfacts_source"] == "same_accession"
                for row in event_rows
            ),
            "latest_prior_companyfacts_count": sum(
                row["companyfacts_source"] == "latest_prior"
                for row in event_rows
            ),
            "companyfacts_unavailable_count": sum(
                row["companyfacts_bucket"] == "companyfacts_unavailable"
                for row in event_rows
            ),
            "pit_status": (
                "Companyfacts filed date is used as public-availability proxy; "
                "all joined context must be filed no later than the event usable date."
            ),
            "data_limitation": (
                "The SEC 8-K event packet had no same-accession XBRL Companyfacts "
                "rows, so this test only evaluates stale latest-prior context."
            ),
        },
        "shadow_metrics": {
            "all_primary_packet": {
                "event_count": len(event_rows),
                "valid_10d_count": len(all_valid_10d),
                "avg_10d_excess_return_pct": _round_or_none(
                    mean(all_valid_10d) * 100 if all_valid_10d else None, 6
                ),
                "median_10d_excess_return_pct": _round_or_none(
                    median(all_valid_10d) * 100 if all_valid_10d else None, 6
                ),
                "positive_10d_rate": _round_or_none(
                    sum(value > 0 for value in all_valid_10d) / len(all_valid_10d)
                    if all_valid_10d
                    else None,
                    6,
                ),
                "valid_20d_count": len(all_valid_20d),
                "avg_20d_excess_return_pct": _round_or_none(
                    mean(all_valid_20d) * 100 if all_valid_20d else None, 6
                ),
                "positive_20d_rate": _round_or_none(
                    sum(value > 0 for value in all_valid_20d) / len(all_valid_20d)
                    if all_valid_20d
                    else None,
                    6,
                ),
            },
            "by_companyfacts_bucket": bucket_summary,
            "by_companyfacts_source": source_summary,
            "by_window": window_summary,
            "event_rows": event_rows,
        },
        "decision_rationale": decision_rationale,
        "next_retry_requires": [
            "Do not promote or tune this Companyfacts overlay from latest-prior context.",
            "Retry only if same-accession or same-day earnings XBRL snapshots become PIT-safe at the event date.",
            "A valid retry must compare replacement value against frozen A/B alternatives, not just standalone event returns.",
        ],
        "related_files": [
            str(SEC_PACKET_PATH.relative_to(ROOT)),
            str(COMPANYFACTS_PATH.relative_to(ROOT)),
            f"data/experiments/{EXPERIMENT_ID}/sec_negative_reaction_companyfacts_context.json",
            str(LOG_PATH.relative_to(ROOT)),
            str(TICKET_PATH.relative_to(ROOT)),
            str(AUDIT_PATH.relative_to(ROOT)),
            str(Path(__file__).relative_to(ROOT)),
        ],
    }


def write_audit(result: dict[str, Any]) -> None:
    summary = result["shadow_metrics"]["all_primary_packet"]
    buckets = result["shadow_metrics"]["by_companyfacts_bucket"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC negative reaction Companyfacts context",
        "",
        "## Decision",
        "",
        f"- Status: {result['status']}",
        f"- Decision: {result['decision']}",
        f"- Rationale: {result['decision_rationale']}",
        "",
        "## Three-window baseline",
        "",
        "| Window | EV | Sharpe daily | Max DD | PnL | Win rate | Trades | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for window, metrics in BASELINE_3WINDOW.items():
        lines.append(
            "| {window} | {ev:.4f} | {sharpe:.2f} | {dd:.2%} | ${pnl:,.2f} | "
            "{win:.2%} | {trades} | {survival:.2%} |".format(
                window=window,
                ev=metrics["expected_value_score"],
                sharpe=metrics["sharpe_daily"],
                dd=metrics["max_drawdown_pct"],
                pnl=metrics["total_pnl"],
                win=metrics["win_rate"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
            )
        )

    lines.extend(
        [
            "",
            "Core metrics are unchanged because this is a shadow attribution experiment only.",
            "",
            "## Packet summary",
            "",
            (
                f"- Events: {summary['event_count']}; valid 10d: "
                f"{summary['valid_10d_count']}; avg 10d excess: "
                f"{summary['avg_10d_excess_return_pct']}%; positive 10d rate: "
                f"{summary['positive_10d_rate']}"
            ),
            (
                "- Companyfacts source coverage: "
                f"{result['data_availability']['same_accession_companyfacts_count']} "
                "same-accession, "
                f"{result['data_availability']['latest_prior_companyfacts_count']} "
                "latest-prior."
            ),
            "",
            "## Bucket results",
            "",
            "| Bucket | Events | Valid 10d | Avg 10d excess | Positive 10d | Windows |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for bucket, metrics in buckets.items():
        lines.append(
            "| {bucket} | {events} | {valid} | {avg}% | {pos} | {windows} |".format(
                bucket=bucket,
                events=metrics["event_count"],
                valid=metrics["valid_10d_count"],
                avg=metrics["avg_10d_excess_return_pct"],
                pos=metrics["positive_10d_rate"],
                windows=json.dumps(metrics["windows"], sort_keys=True),
            )
        )

    lines.extend(
        [
            "",
            "## Production impact",
            "",
            "No production order, ranking, sizing, signal generation, or backtester adapter changed.",
            "",
            "## Next retry condition",
            "",
            (
                "Retry only after PIT-safe same-accession or same-day earnings XBRL "
                "snapshots exist for SEC reaction events."
            ),
            "",
        ]
    )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_registry(result: dict[str, Any]) -> None:
    if REGISTRY_PATH.exists():
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    else:
        registry = {"experiments": []}

    entry = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": result["hypothesis"],
        "lane": result["lane"],
        "owner": "alpha-search",
        "status": result["decision"],
        "ticket_file": str(TICKET_PATH.relative_to(ROOT)),
        "updated_at": result["timestamp"],
    }
    experiments = registry.setdefault("experiments", [])
    for index, existing in enumerate(experiments):
        if existing.get("experiment_id") == EXPERIMENT_ID:
            experiments[index] = entry
            break
    else:
        experiments.append(entry)

    registry["updated_at"] = result["timestamp"]
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def write_outputs(result: dict[str, Any]) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    TICKET_PATH.parent.mkdir(parents=True, exist_ok=True)

    result_path = RESULT_DIR / "sec_negative_reaction_companyfacts_context.json"
    payload = json.dumps(result, indent=2, sort_keys=True, default=_json_default) + "\n"
    result_path.write_text(payload, encoding="utf-8")
    LOG_PATH.write_text(payload, encoding="utf-8")

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC negative reaction Companyfacts context",
        "lane": result["lane"],
        "status": result["decision"],
        "decision": result["decision"],
        "summary": result["decision_rationale"],
        "next_action": result["next_retry_requires"][0],
        "result_file": str(result_path.relative_to(ROOT)),
        "log_file": str(LOG_PATH.relative_to(ROOT)),
    }
    TICKET_PATH.write_text(
        json.dumps(ticket, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with EXPERIMENT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True, default=_json_default) + "\n")

    write_registry(result)
    write_audit(result)


def main() -> None:
    result = build_result()
    write_outputs(result)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": result["decision"]}))


if __name__ == "__main__":
    main()
