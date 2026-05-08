"""exp-20260508-007: platform RS20 missed no-gap feature audit.

Observed-only follow-up to exp-20260507-035. The previous sleeve scout found
positive replacement value in missed platform rs20_leader candidates, but the
sample was too small and APP-concentrated. This audit changes one primary
question: among those already-missed platform RS20 rows, does the existing
`gap_up_3pct` entry-state tag separate chased breakouts from cleaner missed
continuation candidates?

No production path, ranking, sizing, exits, LLM/news, or backtester execution
logic is changed.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260508-007"
STEM = "platform_rs20_no_gap_missed_feature_audit"
SOURCE_EXPERIMENT = "exp-20260507-035"
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT
    / "platform_rs20_missed_sleeve_audit.json"
)

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

PRIMARY_FEATURE = "no_gap_up_3pct"
PLATFORM_POOL = ("META", "NFLX", "GOOG", "AMZN", "SPOT", "DIS", "APP")


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


def _feature_flags(row: dict[str, Any]) -> dict[str, bool]:
    tags = set(row.get("tags") or [])
    return {
        "no_gap_up_3pct": "gap_up_3pct" not in tags,
        "gap_up_3pct": "gap_up_3pct" in tags,
        "breakout_long": row.get("strategy") == "breakout_long",
        "trend_long": row.get("strategy") == "trend_long",
        "scarce_slot_breakout_deferred": (
            row.get("decision") == "scarce_slot_breakout_deferred"
        ),
        "slot_sliced": row.get("decision") == "slot_sliced",
        "candidate_rank_missing": row.get("candidate_rank") is None,
        "pre_earnings_0_21": (
            "pre_earnings_0_7" in tags or "pre_earnings_8_21" in tags
        ),
        "pre_earnings_46_plus": "pre_earnings_46_plus" in tags,
    }


def _flatten_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window_name, window in source.get("by_window", {}).items():
        for row in window.get("missed_rows", []):
            flags = _feature_flags(row)
            metrics = row.get("timing_metrics") or {}
            rows.append(
                {
                    **row,
                    "window": window_name,
                    "feature_flags": flags,
                    "gap_pct": _round(metrics.get("gap_pct"), 6),
                    "excess_spy_return_20d": _round(
                        metrics.get("excess_spy_return_20d"), 6
                    ),
                    "days_to_earnings": metrics.get("days_to_earnings"),
                }
            )
    rows.sort(key=lambda item: (item["window"], item["signal_date"], item["ticker"]))
    return rows


def _positive_share_by_ticker(rows: list[dict[str, Any]]) -> float | None:
    pnl_by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        pnl_by_ticker[str(row.get("ticker") or "")] += float(row.get("pnl") or 0.0)
    positive_values = [value for value in pnl_by_ticker.values() if value > 0]
    if not positive_values:
        return None
    return max(positive_values) / sum(positive_values)


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "avg_pnl": None,
            "avg_return_pct": None,
            "candidate_count": 0,
            "decision_counts": {},
            "max_single_ticker_positive_share": None,
            "median_return_pct": None,
            "pnl_by_ticker": {},
            "total_pnl": 0.0,
            "win_rate": None,
            "windows_present": 0,
        }
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    returns = [float(row.get("return_pct") or 0.0) for row in rows]
    decision_counts: Counter[str] = Counter(str(row.get("decision") or "unknown") for row in rows)
    pnl_by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        pnl_by_ticker[str(row.get("ticker") or "")] += float(row.get("pnl") or 0.0)
    return {
        "avg_pnl": _round(sum(pnls) / len(pnls), 2),
        "avg_return_pct": _round(sum(returns) / len(returns), 6),
        "candidate_count": len(rows),
        "decision_counts": dict(sorted(decision_counts.items())),
        "max_single_ticker_positive_share": _round(_positive_share_by_ticker(rows), 4),
        "median_return_pct": _round(median(returns), 6),
        "pnl_by_ticker": {
            ticker: _round(value, 2) for ticker, value in sorted(pnl_by_ticker.items())
        },
        "total_pnl": _round(sum(pnls), 2),
        "win_rate": _round(sum(1 for value in pnls if value > 0) / len(pnls), 4),
        "windows_present": len({str(row.get("window") or "") for row in rows}),
    }


def _split(
    name: str,
    rows: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    matched = [row for row in rows if predicate(row)]
    complement = [row for row in rows if not predicate(row)]
    return {
        "feature": name,
        "matched": _stats(matched),
        "complement": _stats(complement),
        "matched_rows": [
            {
                "window": row["window"],
                "signal_date": row["signal_date"],
                "ticker": row["ticker"],
                "strategy": row["strategy"],
                "decision": row["decision"],
                "gap_pct": row.get("gap_pct"),
                "days_to_earnings": row.get("days_to_earnings"),
                "excess_spy_return_20d": row.get("excess_spy_return_20d"),
                "return_pct": row.get("return_pct"),
                "pnl": row.get("pnl"),
            }
            for row in matched
        ],
    }


def _supporting_splits(rows: list[dict[str, Any]]) -> OrderedDict[str, Any]:
    split_specs: OrderedDict[str, Callable[[dict[str, Any]], bool]] = OrderedDict(
        [
            ("gap_up_3pct", lambda row: row["feature_flags"]["gap_up_3pct"]),
            ("breakout_long", lambda row: row["feature_flags"]["breakout_long"]),
            (
                "scarce_slot_breakout_deferred",
                lambda row: row["feature_flags"]["scarce_slot_breakout_deferred"],
            ),
            (
                "candidate_rank_missing",
                lambda row: row["feature_flags"]["candidate_rank_missing"],
            ),
            ("pre_earnings_0_21", lambda row: row["feature_flags"]["pre_earnings_0_21"]),
            (
                "pre_earnings_46_plus",
                lambda row: row["feature_flags"]["pre_earnings_46_plus"],
            ),
        ]
    )
    return OrderedDict((name, _split(name, rows, pred)) for name, pred in split_specs.items())


def _gate(primary: dict[str, Any]) -> dict[str, Any]:
    matched = primary["matched"]
    complement = primary["complement"]
    passed = (
        matched["candidate_count"] >= 8
        and (matched.get("total_pnl") or 0) > 0
        and (matched.get("win_rate") or 0) >= 0.5
        and (
            matched.get("max_single_ticker_positive_share") is None
            or matched["max_single_ticker_positive_share"] <= 0.5
        )
        and (complement.get("total_pnl") or 0) < 0
    )
    failures = []
    if matched["candidate_count"] < 8:
        failures.append("matched_candidate_count_lt_8")
    if (matched.get("total_pnl") or 0) <= 0:
        failures.append("matched_total_pnl_not_positive")
    if (matched.get("win_rate") or 0) < 0.5:
        failures.append("matched_win_rate_lt_50pct")
    if (
        matched.get("max_single_ticker_positive_share") is not None
        and matched["max_single_ticker_positive_share"] > 0.5
    ):
        failures.append("single_ticker_positive_share_gt_50pct")
    if (complement.get("total_pnl") or 0) >= 0:
        failures.append("complement_total_pnl_not_negative")
    return {
        "passed": passed,
        "failures": failures,
        "rules": {
            "matched_candidate_count": ">= 8",
            "matched_total_pnl": "> 0",
            "matched_win_rate": ">= 50%",
            "matched_single_ticker_positive_share": "<= 50%",
            "complement_total_pnl": "< 0",
        },
    }


def _feature_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "window": row["window"],
                "signal_date": row["signal_date"],
                "ticker": row["ticker"],
                "strategy": row["strategy"],
                "decision": row["decision"],
                "candidate_rank": row.get("candidate_rank"),
                "no_gap_up_3pct": row["feature_flags"]["no_gap_up_3pct"],
                "gap_pct": row.get("gap_pct"),
                "days_to_earnings": row.get("days_to_earnings"),
                "excess_spy_return_20d": row.get("excess_spy_return_20d"),
                "return_pct": row.get("return_pct"),
                "pnl": row.get("pnl"),
                "tags": row.get("tags"),
            }
        )
    return out


def _write_artifact(payload: dict[str, Any]) -> None:
    primary = payload["primary_split"]
    gate = payload["observed_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Platform RS20 No-Gap Missed Feature Audit",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- primary feature: `{PRIMARY_FEATURE}`",
        f"- gate passed: {gate['passed']}",
        f"- gate failures: {', '.join(gate['failures'])}",
        "",
        "## Primary Split",
        "",
        (
            "- matched no-gap rows: "
            f"count={primary['matched']['candidate_count']}, "
            f"pnl={primary['matched']['total_pnl']}, "
            f"win_rate={primary['matched']['win_rate']}, "
            "single_ticker_positive_share="
            f"{primary['matched']['max_single_ticker_positive_share']}"
        ),
        (
            "- complement gap-up rows: "
            f"count={primary['complement']['candidate_count']}, "
            f"pnl={primary['complement']['total_pnl']}, "
            f"win_rate={primary['complement']['win_rate']}"
        ),
        "",
        "## Supporting Splits",
        "",
    ]
    for name, split in payload["supporting_splits"].items():
        lines.append(
            "- "
            f"{name}: matched_count={split['matched']['candidate_count']}, "
            f"matched_pnl={split['matched']['total_pnl']}, "
            f"matched_win_rate={split['matched']['win_rate']}"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Observed-only feature audit of exp-20260507-035 missed rows.",
            "- Does not change production signals, ranking, sizing, exits, or orders.",
            "- Strong sample split is not promoted because count and concentration fail the gate.",
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
        "alpha_hypothesis_category": "entry_replacement_feature_audit",
        "change_type": "observed_only_entry_state_discriminator_audit",
        "mechanism_family": "platform_rs20_missed_candidate_gap_extension",
        "single_causal_variable": "missed_platform_rs20_no_gap_up_3pct_discriminator",
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "observed_metrics": payload["observed_metrics"],
        "primary_split": {
            "feature": payload["primary_split"]["feature"],
            "matched": payload["primary_split"]["matched"],
            "complement": payload["primary_split"]["complement"],
        },
        "supporting_split_summary": {
            name: {
                "matched": split["matched"],
                "complement": split["complement"],
            }
            for name, split in payload["supporting_splits"].items()
        },
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
    }


def main() -> None:
    source = _load_json(SOURCE_JSON)
    rows = _flatten_rows(source)
    primary_split = _split(
        PRIMARY_FEATURE,
        rows,
        lambda row: row["feature_flags"][PRIMARY_FEATURE],
    )
    supporting_splits = _supporting_splits(rows)
    observed_gate = _gate(primary_split)
    decision = (
        "forward_watch_candidate"
        if observed_gate["passed"]
        else "observed_only_underpowered"
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    date_range = source.get("date_range") or {
        name: f"{spec['start']} -> {spec['end']}"
        for name, spec in (
            (window, data.get("window_spec", {}))
            for window, data in source.get("by_window", {}).items()
        )
    }
    market_regime_summary = {
        name: (data.get("window_spec") or {}).get("state_note")
        for name, data in source.get("by_window", {}).items()
    }
    rejection_reason = None
    if not observed_gate["passed"]:
        rejection_reason = (
            "No-gap platform RS20 missed candidates split cleanly in-sample, "
            "but fail observed-only gate: "
            f"{', '.join(observed_gate['failures'])}."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "source_experiment": SOURCE_EXPERIMENT,
        "hypothesis": (
            "Among platform-pool rs20_leader candidates already missed by the core "
            "entry path, the absence of a signal-date `gap_up_3pct` tag may separate "
            "cleaner continuation misses from overextended chased entries."
        ),
        "decision": decision,
        "rejection_reason": rejection_reason,
        "parameters": {
            "platform_pool": PLATFORM_POOL,
            "source_rows": "exp-20260507-035 missed_rows",
            "primary_feature": PRIMARY_FEATURE,
            "locked_variables": [
                "core universe",
                "signal generation",
                "candidate ranking",
                "entry execution",
                "sizing",
                "exits",
                "LLM/news replay",
            ],
            "observed_gate": _gate(primary_split)["rules"],
        },
        "history_check": {
            "exp-20260507-034": "Hard platform RS20 entry gate rejected; do not retry nearby RS20 thresholds.",
            "exp-20260507-035": "Missed platform RS20 sleeve was positive but underpowered and APP-concentrated.",
            "exp-20260508-005": "Event state-score floor rejected; avoid another small threshold-only production rule.",
            "mechanism_insight_conflict": (
                "No conflict: this keeps RS20 as an oracle feature and tests one "
                "orthogonal existing entry-state tag without promotion."
            ),
        },
        "date_range": date_range,
        "market_regime_summary": market_regime_summary,
        "observed_metrics": _stats(rows),
        "observed_gate": observed_gate,
        "primary_split": primary_split,
        "supporting_splits": supporting_splits,
        "feature_matrix": _feature_matrix(rows),
        "gate4": {
            "passed": None,
            "basis": "Observed-only discriminator audit of prior missed rows; not a portfolio backtest.",
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
            "blocker_relation": "LLM/news replay is locked out of this deterministic feature audit.",
        },
        "next_retry_requires": [
            "Do not promote no-gap platform RS20 missed candidates from this six-row sample.",
            "A valid retry needs at least eight no-gap missed candidates with single-ticker positive contribution <= 50%.",
            "If forward evidence appears, test as a default-off sleeve with shared run.py/backtester semantics.",
            "A better retry should add an orthogonal event/news/earnings-quality discriminator, not another RS20 threshold.",
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
        "title": "Platform RS20 no-gap missed feature audit",
        "result": decision,
        "created_at": timestamp,
        "completed_at": timestamp,
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _log_record(payload))
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG, _log_record(payload))
    print(
        json.dumps(
            {
                "decision": decision,
                "rejection_reason": rejection_reason,
                "observed_gate": observed_gate,
                "primary_split": {
                    "matched": primary_split["matched"],
                    "complement": primary_split["complement"],
                },
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
