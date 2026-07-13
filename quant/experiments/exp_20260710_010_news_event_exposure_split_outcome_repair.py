"""exp-20260710-010: repair split-contaminated news exposure outcomes.

Measurement repair. exp-20260709-008 repaired split-discontinuous OHLCV
warehouse rows and identified stale news_event_exposure observations for
KLAC/CRWD as contaminated consumers. The daily observer only settles pending
rows, so already closed rows must be recomputed once against the repaired
warehouse before this surface can support future alpha reads.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


EXPERIMENT_ID = "exp-20260710-010"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "news_event_exposure_split_outcome_repair"
RUNNER = f"quant/experiments/exp_20260710_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import experiment_registry as expreg  # noqa: E402
from news_event_exposure_observer import (  # noqa: E402
    DEFAULT_OUT_DIR,
    MAX_SIC_PEERS,
    SCHEMA_VERSION,
    _excess,
    load_frames,
    load_ledger,
)


DATA_DIR = REPO_ROOT / "data"
LEDGER_DIR = DEFAULT_OUT_DIR
ROWS_JSONL = LEDGER_DIR / "rows.jsonl"
LEDGER_MANIFEST_JSON = LEDGER_DIR / "manifest.json"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

AFFECTED_TICKERS = ("KLAC", "CRWD")
EXTREME_ABS_EXCESS_THRESHOLD = 0.5

HYPOTHESIS = (
    "Repair the news_event_exposure observer ledger rows contaminated by "
    "pre-exp-20260709-008 KLAC/CRWD warehouse split discontinuities so future "
    "second-order structured-news alpha reads use repaired OHLCV outcomes "
    "rather than stale impossible -90% excess returns."
)
ALPHA_HYPOTHESIS = (
    "Second-order structured-news exposure may support a future candidate-pool "
    "or LLM event-scoring alpha once its forward outcome rows are trustworthy "
    "and current-event closed rows materially increase."
)
SINGLE_CAUSAL_VARIABLE = (
    "news_event_exposure_split_contaminated_outcome_repair_v1"
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "identity_or_measurement_repair"
TRIAL_FAMILY = "news_event_exposure_split_contaminated_outcome_repair"
TRIAL_VARIANT_ID = "news_event_exposure_klac_crwd_closed_outcome_recompute_v1"
CAUSAL_COMPONENTS = [
    "reuse news_event_exposure_observer entry/exit semantics",
    "closed KLAC/CRWD exposure rows only",
    "repaired OHLCV warehouse values from exp-20260709-008",
    "no strategy, ranking, sizing, exit, or order behavior change",
]
ACCEPTANCE_RULE = (
    "Accepted measurement repair if closed KLAC/CRWD news_event_exposure rows "
    "are recomputed against repaired warehouse OHLCV, impossible split-size "
    "excess values are reduced, the ledger remains schema-consistent, and no "
    "trading behavior changes."
)

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_010_{SLUG}.json",
    "data/non_ohlcv/news_event_exposure_observations/rows.jsonl",
    "data/non_ohlcv/news_event_exposure_observations/manifest.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\experiments\\exp_20260710_010_news_event_exposure_split_outcome_repair.py",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def write_json(path: Path, payload: Any) -> None:
    write_text(
        path,
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
    )


def install_registry_direct_writer() -> None:
    def _direct_write_text(text: str, path: str | Path) -> None:
        write_text(Path(path), text)

    expreg._atomic_write_text = _direct_write_text


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("event_id")), str(row.get("exposure_ticker")))


def numeric_excess(row: Mapping[str, Any], field: str) -> float | None:
    value = row.get(field)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_extreme_outcome(row: Mapping[str, Any]) -> bool:
    for field in ("excess_5d", "excess_10d"):
        value = numeric_excess(row, field)
        if value is not None and abs(value) >= EXTREME_ABS_EXCESS_THRESHOLD:
            return True
    return False


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row.get("outcome_status") == "closed"]
    pending = [
        row for row in rows if row.get("outcome_status") == "pending_forward_close"
    ]
    affected = [
        row
        for row in rows
        if str(row.get("exposure_ticker") or "").upper() in AFFECTED_TICKERS
    ]
    affected_closed = [
        row for row in affected if row.get("outcome_status") == "closed"
    ]
    extreme = [row for row in affected_closed if is_extreme_outcome(row)]
    by_ticker: dict[str, dict[str, int]] = {
        ticker: {"rows": 0, "closed_rows": 0, "extreme_closed_rows": 0}
        for ticker in AFFECTED_TICKERS
    }
    for row in affected:
        ticker = str(row.get("exposure_ticker") or "").upper()
        if ticker not in by_ticker:
            continue
        by_ticker[ticker]["rows"] += 1
        if row.get("outcome_status") == "closed":
            by_ticker[ticker]["closed_rows"] += 1
            if is_extreme_outcome(row):
                by_ticker[ticker]["extreme_closed_rows"] += 1
    return {
        "rows": len(rows),
        "closed_rows": len(closed),
        "pending_rows": len(pending),
        "event_ids": len({row.get("event_id") for row in rows}),
        "first_order_tickers": len({row.get("first_order_ticker") for row in rows}),
        "exposure_tickers": len({row.get("exposure_ticker") for row in rows}),
        "affected_rows": len(affected),
        "affected_closed_rows": len(affected_closed),
        "affected_extreme_closed_rows": len(extreme),
        "affected_by_ticker": by_ticker,
        "sample_extreme_rows": [
            {
                "event_id": row.get("event_id"),
                "event_date": row.get("event_date"),
                "exposure_ticker": row.get("exposure_ticker"),
                "entry_date": row.get("entry_date"),
                "excess_5d": row.get("excess_5d"),
                "excess_10d": row.get("excess_10d"),
            }
            for row in extreme[:12]
        ],
    }


def compact_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": row.get("event_id"),
        "event_date": row.get("event_date"),
        "first_order_ticker": row.get("first_order_ticker"),
        "exposure_ticker": row.get("exposure_ticker"),
        "relation_type": row.get("relation_type"),
        "entry_date": row.get("entry_date"),
        "excess_5d": row.get("excess_5d"),
        "excess_10d": row.get("excess_10d"),
        "outcome_status": row.get("outcome_status"),
    }


def recompute_closed_row(
    row: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
) -> tuple[dict[str, Any], str | None]:
    ticker = str(row.get("exposure_ticker") or "").upper()
    frame = frames.get(ticker)
    spy = frames.get("SPY")
    if frame is None:
        return dict(row), "no_frame"
    if spy is None:
        return dict(row), "no_spy_frame"
    event_date = row.get("event_date")
    if not event_date:
        return dict(row), "missing_event_date"
    try:
        event_ts = pd.Timestamp(event_date)
    except (TypeError, ValueError):
        return dict(row), "invalid_event_date"
    after = frame.index[frame.index > event_ts]
    if not len(after):
        return dict(row), "no_entry_after_event"
    entry = after[0]
    ex10 = _excess(frame, spy, entry, 10)
    if ex10 is None:
        return dict(row), "no_10d_close"
    ex5 = _excess(frame, spy, entry, 5)
    repaired = dict(row)
    repaired["entry_date"] = str(entry.date())
    repaired["excess_5d"] = round(ex5, 6) if ex5 is not None else None
    repaired["excess_10d"] = round(ex10, 6)
    repaired["outcome_status"] = "closed"
    return repaired, None


def rows_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, ensure_ascii=True) == json.dumps(
        right, sort_keys=True, ensure_ascii=True
    )


def repair_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets = [
        row
        for row in rows
        if row.get("outcome_status") == "closed"
        and str(row.get("exposure_ticker") or "").upper() in AFFECTED_TICKERS
    ]
    frames = load_frames({str(row.get("exposure_ticker") or "").upper() for row in targets} | {"SPY"})
    repaired_rows: list[dict[str, Any]] = []
    changed_samples: list[dict[str, Any]] = []
    by_ticker: dict[str, dict[str, int]] = {
        ticker: {
            "target_rows": 0,
            "recomputed_rows": 0,
            "changed_rows": 0,
            "skipped_rows": 0,
            "extreme_before": 0,
            "extreme_after": 0,
        }
        for ticker in AFFECTED_TICKERS
    }
    skip_reasons: dict[str, int] = {}
    recomputed = 0
    changed = 0
    skipped = 0

    for row in rows:
        ticker = str(row.get("exposure_ticker") or "").upper()
        should_recompute = (
            row.get("outcome_status") == "closed" and ticker in AFFECTED_TICKERS
        )
        if not should_recompute:
            repaired_rows.append(dict(row))
            continue
        by_ticker[ticker]["target_rows"] += 1
        if is_extreme_outcome(row):
            by_ticker[ticker]["extreme_before"] += 1
        repaired, reason = recompute_closed_row(row, frames)
        if reason:
            skipped += 1
            by_ticker[ticker]["skipped_rows"] += 1
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            repaired_rows.append(dict(row))
            continue
        recomputed += 1
        by_ticker[ticker]["recomputed_rows"] += 1
        if is_extreme_outcome(repaired):
            by_ticker[ticker]["extreme_after"] += 1
        if not rows_equal(row, repaired):
            changed += 1
            by_ticker[ticker]["changed_rows"] += 1
            if len(changed_samples) < 20:
                changed_samples.append(
                    {"before": compact_row(row), "after": compact_row(repaired)}
                )
        repaired_rows.append(repaired)

    return repaired_rows, {
        "target_rows": len(targets),
        "recomputed_rows": recomputed,
        "changed_rows": changed,
        "skipped_rows": skipped,
        "skip_reasons": skip_reasons,
        "by_ticker": by_ticker,
        "changed_samples": changed_samples,
        "frames_loaded": sorted(frames.keys()),
    }


def write_ledger(rows: list[dict[str, Any]], repair_summary: Mapping[str, Any]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (row.get("event_date") or "", str(row_key(row))))
    write_text(
        ROWS_JSONL,
        "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in ordered),
    )
    closed = [row for row in ordered if row.get("outcome_status") == "closed"]
    previous_manifest = {}
    if LEDGER_MANIFEST_JSON.exists():
        with LEDGER_MANIFEST_JSON.open(encoding="utf-8-sig") as handle:
            previous_manifest = json.load(handle)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "rows": len(ordered),
        "closed_rows": len(closed),
        "pending_rows": len(ordered) - len(closed),
        "event_ids": len({row.get("event_id") for row in ordered}),
        "first_order_tickers": len({row.get("first_order_ticker") for row in ordered}),
        "exposure_tickers": len({row.get("exposure_ticker") for row in ordered}),
        "max_sic_peers": MAX_SIC_PEERS,
        "last_run_utc": utc_now(),
        "source_events": previous_manifest.get("source_events"),
        "appended_this_run": 0,
        "settle_counts": previous_manifest.get("settle_counts"),
        "repair": {
            "experiment_id": EXPERIMENT_ID,
            "rule_version": TRIAL_VARIANT_ID,
            "affected_tickers": list(AFFECTED_TICKERS),
            "target_rows": repair_summary.get("target_rows"),
            "recomputed_rows": repair_summary.get("recomputed_rows"),
            "changed_rows": repair_summary.get("changed_rows"),
            "skipped_rows": repair_summary.get("skipped_rows"),
            "updated_at": utc_now(),
        },
    }
    write_json(LEDGER_MANIFEST_JSON, manifest)
    return manifest


def load_baseline_summary() -> dict[str, Any]:
    if not BASELINE_RESULT.exists():
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "exists": False}
    with BASELINE_RESULT.open(encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "exists": True,
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            6,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def run_repair() -> dict[str, Any]:
    if not ROWS_JSONL.exists():
        raise FileNotFoundError(ROWS_JSONL)
    manifest_before = {}
    if LEDGER_MANIFEST_JSON.exists():
        with LEDGER_MANIFEST_JSON.open(encoding="utf-8-sig") as handle:
            manifest_before = json.load(handle)
    before_rows = load_ledger(ROWS_JSONL)
    before_rows_copy = deepcopy(before_rows)
    before_summary = summarize_rows(before_rows_copy)
    after_rows, repair_summary = repair_rows(before_rows_copy)
    after_summary = summarize_rows(after_rows)
    prior_repair = manifest_before.get("repair") if isinstance(manifest_before, dict) else {}
    idempotent_replay = (
        isinstance(prior_repair, dict)
        and prior_repair.get("experiment_id") == EXPERIMENT_ID
        and before_summary["affected_extreme_closed_rows"] == 0
        and after_summary["affected_extreme_closed_rows"] == 0
    )

    failed_checks: list[str] = []
    if not before_rows:
        failed_checks.append("ledger_empty")
    if repair_summary["target_rows"] <= 0:
        failed_checks.append("no_closed_klac_crwd_target_rows")
    if repair_summary["recomputed_rows"] <= 0:
        failed_checks.append("no_rows_recomputed")
    if repair_summary["changed_rows"] <= 0 and not idempotent_replay:
        failed_checks.append("no_rows_changed")
    if (
        after_summary["affected_extreme_closed_rows"]
        >= before_summary["affected_extreme_closed_rows"]
        and not idempotent_replay
    ):
        failed_checks.append("extreme_outcomes_not_reduced")
    if after_summary["rows"] != before_summary["rows"]:
        failed_checks.append("ledger_row_count_changed")
    if after_summary["closed_rows"] != before_summary["closed_rows"]:
        failed_checks.append("closed_row_count_changed")

    accepted = not failed_checks
    if accepted and not idempotent_replay:
        ledger_manifest = write_ledger(after_rows, repair_summary)
    else:
        ledger_manifest = manifest_before

    return {
        "before_rows": before_summary,
        "after_rows": after_summary,
        "repair_summary": repair_summary,
        "idempotent_replay": idempotent_replay,
        "ledger_manifest_before": manifest_before,
        "ledger_manifest_after": ledger_manifest,
        "failed_checks": failed_checks,
        "accepted": accepted,
    }


def payload_for_idempotent_replay(repair: Mapping[str, Any]) -> dict[str, Any] | None:
    if not repair.get("idempotent_replay") or not OUT_JSON.exists():
        return None
    with OUT_JSON.open(encoding="utf-8-sig") as handle:
        prior = json.load(handle)
    if not isinstance(prior, dict):
        return None
    if prior.get("experiment_id") != EXPERIMENT_ID or not prior.get(
        "accepted_measurement_repair"
    ):
        return None
    validation = {
        "timestamp": utc_now(),
        "status": "accepted_measurement_repair_idempotent_replay",
        "current_affected_extreme_closed_rows": repair["after_rows"][
            "affected_extreme_closed_rows"
        ],
        "current_rows": repair["after_rows"]["rows"],
        "current_closed_rows": repair["after_rows"]["closed_rows"],
        "recomputed_rows": repair["repair_summary"]["recomputed_rows"],
        "changed_rows": repair["repair_summary"]["changed_rows"],
        "failed_checks": repair["failed_checks"],
    }
    validations = list(prior.get("replay_validations") or [])
    validations.append(validation)
    prior["timestamp"] = utc_now()
    prior["idempotent_replay"] = True
    prior["replay_validations"] = validations[-5:]
    prior["status"] = "accepted_measurement_repair"
    prior["accepted"] = True
    prior["accepted_measurement_repair"] = True
    prior["decision"] = (
        "accepted_measurement_repair_news_event_exposure_split_outcomes_repaired"
    )
    return prior


def build_payload(repair: Mapping[str, Any]) -> dict[str, Any]:
    accepted = bool(repair["accepted"])
    decision = (
        "accepted_measurement_repair_news_event_exposure_split_outcomes_repaired"
        if accepted
        else "blocked_news_event_exposure_split_outcome_repair"
    )
    baseline = load_baseline_summary()
    before_rows = repair["before_rows"]
    after_rows = repair["after_rows"]
    repair_summary = repair["repair_summary"]
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "live_ready": False,
        "data_ledger_repaired": accepted,
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "closed_observer_outcome_recompute",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": [
            "exp-20260702-017",
            "exp-20260702-018",
            "exp-20260702-020",
            "exp-20260709-008",
            "exp-20260709-010",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_fault_recovery",
        "new_evidence_axis": (
            "Fault recovery for stale closed news_event_exposure rows named by "
            "exp-20260709-008 contamination audit; not a new alpha slice or "
            "threshold retune."
        ),
        "before_metrics": {
            "strategy": baseline,
            "ledger": before_rows,
        },
        "after_metrics": {
            "strategy": baseline,
            "ledger": after_rows,
        },
        "delta_metrics": {
            "strategy_behavior_changed": False,
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "rows_delta": after_rows["rows"] - before_rows["rows"],
            "closed_rows_delta": after_rows["closed_rows"] - before_rows["closed_rows"],
            "affected_extreme_closed_rows_delta": (
                after_rows["affected_extreme_closed_rows"]
                - before_rows["affected_extreme_closed_rows"]
            ),
            "recomputed_rows": repair_summary["recomputed_rows"],
            "changed_rows": repair_summary["changed_rows"],
        },
        "repair": repair,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "experiment.py novelty gate found no blocking match; this is "
                "fault recovery for exp-20260709-008 contamination, not a "
                "near-neighbor alpha read."
            ),
            "3_single_policy_bundle": (
                "Recompute only closed KLAC/CRWD news_event_exposure outcomes "
                "using the existing observer semantics and repaired warehouse."
            ),
            "4_success_failure_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "passed": baseline.get("exists") is True,
            "baseline_metrics": baseline,
            "note": "Measurement repair only; no strategy replay delta.",
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields": [
                "event_date",
                "entry_date",
                "excess_5d",
                "excess_10d",
                "outcome_status",
                "exposure_ticker",
            ],
            "entry_date": "recomputed by existing observer entry semantics",
            "target_price_scope": "not_applicable_fixed_horizon_observer_rows",
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "note": "No executable filter, rank, or sizing rule was added.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "strategy_behavior_changed": False,
            "failed_reasons": repair["failed_checks"],
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The split repair fixed the OHLCV warehouse, but the observer "
                "ledger persisted closed outcomes by value. Recomputing closed "
                "KLAC/CRWD exposure rows removed stale split-boundary excess "
                "returns without changing row count or trading behavior."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another ID to recompute these same closed "
                "KLAC/CRWD news_event_exposure rows, and do not run alpha "
                "slices on this surface merely because the repaired values are "
                "clean."
            ),
            "new_evidence_required": (
                "Future alpha work needs materially more closed current-event "
                "second-order rows under the daily observer, a distinct PIT "
                "relation/economic source, or a new execution gate shape."
            ),
        },
        "rejection_reason": None if accepted else ";".join(repair["failed_checks"]),
        "related_files": [
            repo_rel(ROWS_JSONL),
            repo_rel(LEDGER_MANIFEST_JSON),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260709-008.json",
        ],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": VERIFICATION_COMMANDS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": accepted,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    repair = payload["repair"]
    before = repair["before_rows"]
    after = repair["after_rows"]
    summary = repair["repair_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: news exposure split outcome repair",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Target rows: `{summary['target_rows']}`",
            f"- Recomputed rows: `{summary['recomputed_rows']}`",
            f"- Changed rows: `{summary['changed_rows']}`",
            f"- Extreme affected closed rows: `{before['affected_extreme_closed_rows']}` -> `{after['affected_extreme_closed_rows']}`",
            "- Accepted alpha: `false`",
            "- Strategy behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    files.extend([ROWS_JSONL, LEDGER_MANIFEST_JSON, BASELINE_RESULT])
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": CHANGED_FILES,
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    install_registry_direct_writer()
    write_json(OUT_JSON, payload)
    expreg.save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    expreg.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=None,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "headline_metrics": {
                "target_rows": payload["repair"]["repair_summary"]["target_rows"],
                "recomputed_rows": payload["repair"]["repair_summary"]["recomputed_rows"],
                "changed_rows": payload["repair"]["repair_summary"]["changed_rows"],
                "extreme_before": payload["repair"]["before_rows"][
                    "affected_extreme_closed_rows"
                ],
                "extreme_after": payload["repair"]["after_rows"][
                    "affected_extreme_closed_rows"
                ],
            },
            "summary": "measurement_repair_news_event_exposure_split_outcomes",
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    repair = run_repair()
    payload = payload_for_idempotent_replay(repair) or build_payload(repair)
    persist(payload)
    print_repair = payload.get("repair", repair)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": payload["artifact"],
                "idempotent_replay": bool(repair.get("idempotent_replay")),
                "target_rows": print_repair["repair_summary"]["target_rows"],
                "recomputed_rows": print_repair["repair_summary"]["recomputed_rows"],
                "changed_rows": print_repair["repair_summary"]["changed_rows"],
                "extreme_before": print_repair["before_rows"][
                    "affected_extreme_closed_rows"
                ],
                "extreme_after": print_repair["after_rows"][
                    "affected_extreme_closed_rows"
                ],
                "failed_checks": repair["failed_checks"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
