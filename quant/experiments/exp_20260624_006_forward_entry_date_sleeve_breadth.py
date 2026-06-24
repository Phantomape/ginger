"""exp-20260624-006: entry-date cross-sleeve forward attribution.

Observed-only alpha attribution. The runner asks whether closed forward
replacement rows entered on dates with multiple distinct default-off paper
sleeves carry better replacement value than singleton-sleeve dates. It changes
no helper, ranking, sizing, exit, ledger mutation, order path, or live behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-006"
OWNER = "alpha-explore"
SLUG = "forward_entry_date_sleeve_breadth"
RUNNER = f"quant/experiments/exp_20260624_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_006_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_REPLACEMENT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"

HYPOTHESIS = (
    "Observed-only attribution: closed forward replacement rows entered on "
    "dates with broader same-day distinct sleeve participation should show "
    "stronger replacement value than singleton-sleeve dates; otherwise same-date "
    "cross-sleeve breadth must remain measurement-only and not feed allocation."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
TRIAL_FAMILY = "forward_replacement_entry_date_cross_sleeve_breadth"
TRIAL_VARIANT_ID = "v1"
CHANGED_VARIABLE = "forward_replacement_entry_date_cross_sleeve_breadth_v1"
NEW_EVIDENCE_TYPE = "forward_replacement_ledger_entry_date_sleeve_breadth"
NEW_EVIDENCE_AXIS = (
    "Machine-checkable forward replacement ledger field: distinct closed paper "
    "sleeve count by entry_date, computed only from production "
    "data/paper_sleeves/forward_replacement_value.jsonl rows. This is not an "
    "OHLCV/sector breadth candidate-pool source, regime scalar, sleeve_health, "
    "ticker memory, stock-vs-ETF, allocator source-rank/capacity, notional, "
    "hold-day, or threshold retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-027",
    "exp-20260623-028",
    "exp-20260624-001",
    "exp-20260624-004",
]
CAUSAL_COMPONENTS = [
    "read-only forward replacement ledger",
    "entry-date distinct sleeve breadth cohorting",
    "no strategy behavior change",
]
REPLACEMENT_FIELDS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
CONFIG = {
    "multi_sleeve_min_distinct_sleeves": 2,
    "min_multi_sleeve_rows": 8,
    "min_multi_sleeve_entry_dates": 2,
    "min_singleton_rows": 8,
    "min_mean_comparator_wins": 2,
    "max_single_entry_date_positive_share": 0.70,
    "max_single_ticker_positive_share": 0.70,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = read_jsonl(path)
    output: list[dict[str, Any]] = []
    replaced = False
    for existing in records:
        if existing.get("experiment_id") == EXPERIMENT_ID:
            output.append(record)
            replaced = True
        else:
            output.append(existing)
    if not replaced:
        output.append(record)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in output:
            handle.write(json.dumps(item, sort_keys=True) + "\n")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def row_identity(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("decision_id") or ""),
            str(row.get("sleeve_key") or ""),
            str(row.get("ticker") or ""),
            str(row.get("entry_date") or ""),
            str(row.get("exit_date") or ""),
        ]
    )


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return {
        "recorded_at": utc_now(),
        "success_probability": 0.16,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "forward_rows_too_few",
            "cross_sleeve_breadth_is_crowding_not_alpha",
            "qqq_or_single_date_concentration",
            "no_benchmark_relative_monotonicity",
        ],
        "confidence_reason": (
            "Fallback prediction from the reserved ticket: cross-sleeve same-date "
            "participation may be useful, but the forward ledger is small."
        ),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def load_forward_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows = read_jsonl(FORWARD_REPLACEMENT)
    deduped: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        deduped[row_identity(row)] = row

    usable: list[dict[str, Any]] = []
    missing_required = 0
    for row in deduped.values():
        entry_date = str(row.get("entry_date") or "")[:10]
        exit_date = str(row.get("exit_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        sleeve_key = str(row.get("sleeve_key") or "")
        values = {field: as_float(row.get(field)) for field in REPLACEMENT_FIELDS}
        if (
            not entry_date
            or not exit_date
            or not ticker
            or not sleeve_key
            or any(value is None for value in values.values())
        ):
            missing_required += 1
            continue
        usable.append(
            {
                **row,
                **values,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "ticker": ticker,
                "sleeve_key": sleeve_key,
                "entry_month": entry_date[:7],
            }
        )
    usable.sort(key=lambda row: (row["entry_date"], row["exit_date"], row["ticker"], row["sleeve_key"]))
    return usable, {
        "source_artifact": repo_rel(FORWARD_REPLACEMENT),
        "raw_rows": len(raw_rows),
        "deduped_rows": len(deduped),
        "usable_rows": len(usable),
        "missing_required_rows": missing_required,
        "entry_date_min": min((row["entry_date"] for row in usable), default=None),
        "entry_date_max": max((row["entry_date"] for row in usable), default=None),
        "artifact_not_mutated": True,
    }


def attach_entry_date_breadth(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[str(row["entry_date"])].append(row)

    output: list[dict[str, Any]] = []
    for row in rows:
        peers = by_date[str(row["entry_date"])]
        sleeve_count = len({str(peer.get("sleeve_key") or "") for peer in peers})
        ticker_count = len({str(peer.get("ticker") or "") for peer in peers})
        row_count = len(peers)
        cohort = "multi_sleeve_date" if sleeve_count >= CONFIG["multi_sleeve_min_distinct_sleeves"] else "singleton_sleeve_date"
        output.append(
            {
                **row,
                "entry_date_row_count": row_count,
                "entry_date_distinct_sleeve_count": sleeve_count,
                "entry_date_distinct_ticker_count": ticker_count,
                "entry_date_breadth_cohort": cohort,
            }
        )
    return output


def distribution(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(clean),
        "sum": round(sum(clean), 2),
        "mean": round(sum(clean) / len(clean), 4),
        "median": round(median(clean), 4),
        "min": round(min(clean), 4),
        "max": round(max(clean), 4),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 6),
    }


def top_counts(rows: list[dict[str, Any]], key: str, limit: int = 12) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or "unknown") for row in rows)
    total = len(rows) or 1
    return [
        {"key": value, "n": count, "row_share": round(count / total, 6)}
        for value, count in counts.most_common(limit)
    ]


def positive_share(rows: list[dict[str, Any]], field: str, key: str) -> float | None:
    positive_by_key: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        value = as_float(row.get(field))
        if value is not None and value > 0:
            positive_by_key[str(row.get(key) or "unknown")] += value
    total = sum(positive_by_key.values())
    if total <= 0:
        return None
    return round(max(positive_by_key.values()) / total, 6)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "n": len(rows),
        "distinct_entry_dates": len({str(row.get("entry_date") or "") for row in rows}),
        "distinct_tickers": len({str(row.get("ticker") or "unknown") for row in rows}),
        "distinct_sleeves": len({str(row.get("sleeve_key") or "unknown") for row in rows}),
        "entry_dates": top_counts(rows, "entry_date"),
        "tickers": top_counts(rows, "ticker"),
        "sleeves": top_counts(rows, "sleeve_key"),
        "entry_months": top_counts(rows, "entry_month"),
        "entry_date_distinct_sleeve_count_distribution": dict(
            sorted(
                Counter(
                    int(row.get("entry_date_distinct_sleeve_count") or 0)
                    for row in rows
                ).items()
            )
        ),
    }
    for field in REPLACEMENT_FIELDS:
        values = [float(row[field]) for row in rows if as_float(row.get(field)) is not None]
        summary[field] = distribution(values)
        summary[field]["max_single_entry_date_positive_share"] = positive_share(
            rows,
            field,
            "entry_date",
        )
        summary[field]["max_single_ticker_positive_share"] = positive_share(
            rows,
            field,
            "ticker",
        )
    return summary


def grouped_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "unknown")].append(row)
    return {name: summarize_rows(group) for name, group in sorted(groups.items())}


def compare_groups(target: dict[str, Any], comparator: dict[str, Any]) -> dict[str, Any]:
    wins = 0
    by_field: dict[str, Any] = {}
    for field in REPLACEMENT_FIELDS:
        target_mean = target[field]["mean"]
        comparator_mean = comparator[field]["mean"]
        delta = None
        beats = False
        if target_mean is not None and comparator_mean is not None:
            delta = round(target_mean - comparator_mean, 4)
            beats = target_mean > comparator_mean
            wins += int(beats)
        by_field[field] = {
            "target_mean": target_mean,
            "comparator_mean": comparator_mean,
            "target_minus_comparator_mean": delta,
            "target_beats_comparator_mean": beats,
        }
    return {"mean_comparator_wins": wins, "by_field": by_field}


def build_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    multi = [row for row in rows if row["entry_date_breadth_cohort"] == "multi_sleeve_date"]
    singleton = [row for row in rows if row["entry_date_breadth_cohort"] == "singleton_sleeve_date"]
    multi_summary = summarize_rows(multi)
    singleton_summary = summarize_rows(singleton)
    return {
        "all_rows": summarize_rows(rows),
        "cohorts": {
            "multi_sleeve_date": multi_summary,
            "singleton_sleeve_date": singleton_summary,
            **grouped_summary(rows, "entry_date_breadth_cohort"),
        },
        "by_entry_date_distinct_sleeve_count": grouped_summary(
            rows,
            "entry_date_distinct_sleeve_count",
        ),
        "multi_sleeve_vs_singleton": compare_groups(multi_summary, singleton_summary),
        "sample_rows": [
            {
                "entry_date_breadth_cohort": row["entry_date_breadth_cohort"],
                "entry_date_distinct_sleeve_count": row["entry_date_distinct_sleeve_count"],
                "entry_date_row_count": row["entry_date_row_count"],
                "ticker": row["ticker"],
                "sleeve_key": row["sleeve_key"],
                "entry_date": row["entry_date"],
                "exit_date": row["exit_date"],
                "replacement_value_vs_cash_usd": round_or_none(row["replacement_value_vs_cash_usd"], 2),
                "replacement_value_vs_spy_usd": round_or_none(row["replacement_value_vs_spy_usd"], 2),
                "replacement_value_vs_qqq_usd": round_or_none(row["replacement_value_vs_qqq_usd"], 2),
            }
            for row in rows[:25]
        ],
    }


def evaluate_gate4(analysis: dict[str, Any]) -> dict[str, Any]:
    target = analysis["cohorts"]["multi_sleeve_date"]
    comparator = analysis["cohorts"]["singleton_sleeve_date"]
    comparison = analysis["multi_sleeve_vs_singleton"]
    entry_date_concentration = max(
        (
            target[field]["max_single_entry_date_positive_share"] or 0.0
            for field in REPLACEMENT_FIELDS
        ),
        default=0.0,
    )
    ticker_concentration = max(
        (
            target[field]["max_single_ticker_positive_share"] or 0.0
            for field in REPLACEMENT_FIELDS
        ),
        default=0.0,
    )
    checks = {
        "multi_sleeve_rows_passed": target["n"] >= CONFIG["min_multi_sleeve_rows"],
        "multi_sleeve_entry_dates_passed": (
            target["distinct_entry_dates"] >= CONFIG["min_multi_sleeve_entry_dates"]
        ),
        "singleton_rows_passed": comparator["n"] >= CONFIG["min_singleton_rows"],
        "multi_sleeve_total_positive_all_comparators": all(
            target[field]["sum"] > 0 for field in REPLACEMENT_FIELDS
        ),
        "multi_sleeve_mean_positive_all_comparators": all(
            (target[field]["mean"] or 0.0) > 0 for field in REPLACEMENT_FIELDS
        ),
        "multi_sleeve_beats_singleton_two_comparators": (
            comparison["mean_comparator_wins"] >= CONFIG["min_mean_comparator_wins"]
        ),
        "multi_sleeve_entry_date_concentration_passed": (
            entry_date_concentration <= CONFIG["max_single_entry_date_positive_share"]
        ),
        "multi_sleeve_ticker_concentration_passed": (
            ticker_concentration <= CONFIG["max_single_ticker_positive_share"]
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    observed_only_lead = not failed
    decision = (
        "observed_only_positive_forward_entry_date_sleeve_breadth_lead_not_promoted"
        if observed_only_lead
        else "rejected_forward_entry_date_sleeve_breadth_not_allocation_ready"
    )
    return {
        "observed_only_lead": observed_only_lead,
        "decision": decision,
        "failed_reasons": failed,
        "acceptance_checks": checks,
        "target_concentration": {
            "max_single_entry_date_positive_share": entry_date_concentration,
            "max_single_ticker_positive_share": ticker_concentration,
            "entry_date_guardrail": CONFIG["max_single_entry_date_positive_share"],
            "ticker_guardrail": CONFIG["max_single_ticker_positive_share"],
        },
        "multi_sleeve_mean_comparator_wins": comparison["mean_comparator_wins"],
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
        "lead_limitations": [
            "Forward-only closed paper rows, not canonical fixed-window Gate 4 evidence.",
            "No shared helper, daily adapter, rank, notional, exit, or order rule changed.",
            "Any allocation gate requires a separate shared-policy Gate 1-4 experiment.",
        ],
    }


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    observed: list[str] = []
    if "multi_sleeve_rows_passed" in failed or "singleton_rows_passed" in failed:
        observed.append("forward_rows_too_few")
    if "multi_sleeve_beats_singleton_two_comparators" in failed:
        observed.append("no_benchmark_relative_monotonicity")
    if (
        "multi_sleeve_entry_date_concentration_passed" in failed
        or "multi_sleeve_ticker_concentration_passed" in failed
    ):
        observed.append("qqq_or_single_date_concentration")
    if "multi_sleeve_mean_positive_all_comparators" in failed:
        observed.append("cross_sleeve_breadth_is_crowding_not_alpha")
    declared = set(prediction.get("main_failure_modes") or [])
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": int(actual),
        "brier_score": round((probability - actual) ** 2, 6),
        "failed_reasons": failed,
        "failure_modes_observed": observed,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "predicted_failure_mode_hit": bool(declared & set(observed)),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["gate4"]["observed_only_lead"],
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "source_audit": payload["attribution"]["source_audit"],
            "all_rows": analysis["all_rows"],
            "cohorts": analysis["cohorts"],
            "multi_sleeve_vs_singleton": analysis["multi_sleeve_vs_singleton"],
            "by_entry_date_distinct_sleeve_count": analysis[
                "by_entry_date_distinct_sleeve_count"
            ],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "updated_at": payload["timestamp"],
        "anti_js": payload["anti_js"],
    }


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    multi = analysis["cohorts"]["multi_sleeve_date"]
    singleton = analysis["cohorts"]["singleton_sleeve_date"]
    comparison = analysis["multi_sleeve_vs_singleton"]["by_field"]
    rows = [
        "| Comparator | Multi-Sleeve Sum | Multi-Sleeve Mean | Multi-Sleeve Median | Singleton Mean | Delta Mean |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for field in REPLACEMENT_FIELDS:
        rows.append(
            "| {field} | {target_sum} | {target_mean} | {target_median} | {comp_mean} | {delta} |".format(
                field=field,
                target_sum=money(multi[field]["sum"]),
                target_mean=money(multi[field]["mean"]),
                target_median=money(multi[field]["median"]),
                comp_mean=money(singleton[field]["mean"]),
                delta=money(comparison[field]["target_minus_comparator_mean"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: entry-date cross-sleeve breadth attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: `false`",
            "- Shared helper promoted: `false`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Cohort Summary",
            "",
            f"- Multi-sleeve rows: `{multi['n']}` across `{multi['distinct_entry_dates']}` entry dates",
            f"- Singleton rows: `{singleton['n']}` across `{singleton['distinct_entry_dates']}` entry dates",
            f"- Mean comparator wins: `{analysis['multi_sleeve_vs_singleton']['mean_comparator_wins']}`",
            "",
            "## Replacement Value",
            "",
            *rows,
            "",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        FORWARD_REPLACEMENT,
        BASELINE_RESULT,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in paths},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    rows, source_audit = load_forward_rows()
    enriched_rows = attach_entry_date_breadth(rows)
    analysis = build_analysis(enriched_rows)
    gate4 = evaluate_gate4(analysis)
    status = "observed_only_positive_lead" if gate4["observed_only_lead"] else "observed_only_rejected"
    decision = str(gate4["decision"])
    why_result = (
        "Same-date multi-sleeve participation separated later forward rows, but "
        "this is forward-only attribution and no allocation gate was promoted."
        if gate4["observed_only_lead"]
        else "Same-date multi-sleeve participation did not clear the fixed "
        "forward attribution screen; the likely blockers are thin sample, "
        "single-date/ticker concentration, or the cohort behaving like crowding "
        "rather than independent confirmation."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_read_only_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Initial reservation blocked on textual near-neighbor to old "
                    "OHLCV breadth families; override recorded because this run "
                    "uses machine-checkable forward replacement ledger entry-date "
                    "sleeve counts, not sector/industry breadth thresholds."
                ),
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "source_saturation": (
                    "Reservation source-saturation report: ohlcv_relation 5/95 "
                    "accepted, accept_rate 0.0526, above the 0.05 block threshold."
                ),
            },
            "3_single_policy_bundle": (
                "One read-only attribution bundle: for each closed forward "
                "replacement row, count distinct sleeves on the same entry_date "
                "and compare multi-sleeve dates against singleton-sleeve dates."
            ),
            "4_success_failure_standard": (
                "Observed-only positive lead only if multi-sleeve rows have enough "
                "sample and dates, positive total and mean replacement value versus "
                "cash/SPY/QQQ, beat singleton rows on at least two mean comparators, "
                "and pass entry-date/ticker concentration guards."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_artifact": repo_rel(FORWARD_REPLACEMENT),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
            "replacement_fields": REPLACEMENT_FIELDS,
            "pit_rule": (
                "same entry_date distinct sleeve count is known from default-off "
                "paper observations on that date; no future closed outcomes enter "
                "the cohort assignment"
            ),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_summary": baseline,
            "note": "Observed-only attribution; before and after strategy policy are identical.",
        },
        "gate2": {
            "passed": bool(enriched_rows),
            "source_audit": source_audit,
            "required_fields": [
                "entry_date",
                "exit_date",
                "ticker",
                "sleeve_key",
                *REPLACEMENT_FIELDS,
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in enriched_rows),
            "target_price": {
                "available": False,
                "source": "not_applicable_observed_only_forward_replacement_rows",
                "reason": "No executable target, entry, exit, order, or paper ledger mutation is scheduled.",
            },
        },
        "gate3": {
            "strategy_filter_added": False,
            "signals_generated": source_audit["deduped_rows"],
            "signals_survived": source_audit["usable_rows"],
            "survival_rate": (
                round(source_audit["usable_rows"] / source_audit["deduped_rows"], 4)
                if source_audit["deduped_rows"]
                else None
            ),
            "baseline_survival_rate": baseline["survival_rate"],
            "passed": True,
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": {**baseline, "strategy_behavior_changed": False},
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "source_audit": source_audit,
            "analysis": analysis,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "parity_note": "Read-only attribution over existing forward replacement ledger rows.",
        },
        "calibration": calibration(prediction, gate4["observed_only_lead"], gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": why_result,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing the multi-sleeve threshold, row-count "
                "gates, sleeve inclusion, entry-date concentration caps, ticker "
                "concentration caps, notional method, hold days, or activation "
                "thresholds on this same 35-row forward ledger."
            ),
            "new_evidence_required": (
                "Need materially more closed forward replacement rows with "
                "multi-sleeve same-date support, or a separate shared-policy "
                "Gate 1-4 allocation test after the ledger has genuine "
                "multi-date, multi-sleeve coverage."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_REPLACEMENT),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260623-027.json",
            "experiments/logs/exp-20260623-028.json",
            "experiments/logs/exp-20260624-001.json",
            "experiments/logs/exp-20260624-004.json",
            "docs/backtesting.md",
            "docs/production_backtest_parity.md",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["gate4"]["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": {
            "source_audit": payload["attribution"]["source_audit"],
            "cohorts": payload["attribution"]["analysis"]["cohorts"],
            "multi_sleeve_vs_singleton": payload["attribution"]["analysis"][
                "multi_sleeve_vs_singleton"
            ],
        },
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    analysis = payload["attribution"]["analysis"]
    multi = analysis["cohorts"]["multi_sleeve_date"]
    singleton = analysis["cohorts"]["singleton_sleeve_date"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "multi_sleeve_rows": multi["n"],
                "multi_sleeve_entry_dates": multi["distinct_entry_dates"],
                "singleton_rows": singleton["n"],
                "mean_comparator_wins": analysis["multi_sleeve_vs_singleton"][
                    "mean_comparator_wins"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "multi_sleeve_cash_sum": multi["replacement_value_vs_cash_usd"]["sum"],
                "multi_sleeve_spy_sum": multi["replacement_value_vs_spy_usd"]["sum"],
                "multi_sleeve_qqq_sum": multi["replacement_value_vs_qqq_usd"]["sum"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
