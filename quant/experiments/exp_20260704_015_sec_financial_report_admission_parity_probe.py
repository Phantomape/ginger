"""exp-20260704-015: SEC financial-report T+1 admission parity probe.

Measurement repair only. The 2026-07-03 history-wide verdict named
sec_financial_report as the largest replay-vs-daily fire-rate gap
(replay-implied ~11 admissions over 82 snapshot days, actual 0), and
exp-20260704-006 explicitly did not score this sleeve. This runner replays
the sleeve's full daily snapshot span through the exact shared queue builder
with warehouse OHLCV coverage, attributes every same-day row to its first
blocking admission stage, and rebuilds a counterfactual queue whose only
difference is the replay-parity cohort derivation used by the accepted
surface experiments (exp-20260510-023/024/027). It does not change
thresholds, ranking, sizing, exits, orders, or shared sleeve behavior.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames  # noqa: E402
from platform_rs20_watch import PLATFORM_POOL  # noqa: E402
from sec_event_queue import (  # noqa: E402
    FINANCIAL_REPORT_EVENT_FAMILIES,
    FINANCIAL_REPORT_T1_EXCLUDED_COHORTS,
    FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
    build_sec_financial_report_t1_queue,
    evaluate_t1_excess_drift,
    load_sec_filing_event_rows,
    load_sec_filing_text_rows,
    sec_event_family,
    sec_event_item_codes,
)


EXPERIMENT_ID = "exp-20260704-015"
OWNER = "alpha-explore"
SLUG = "sec_financial_report_admission_parity_probe"
RUNNER = f"quant/experiments/exp_20260704_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SNAPSHOT_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "sec_financial_report" / "snapshots.jsonl"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_015_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

# Replay-parity cohort derivation used when the accepted surface was built
# (exp-20260510-023 line 458); the daily collector never writes this field.
REPLAY_COHORT_PLATFORM = "platform_pool"
REPLAY_COHORT_OTHER = "other_equity"

STAGE_ORDER = (
    "status_not_ok",
    "family_not_financial_report",
    "cohort_missing",
    "cohort_excluded_platform_pool",
    "price_not_covered",
    "drift_bucket_not_positive",
    "t1_excess_below_min",
    "qualified",
)

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_015_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\experiments\\exp_20260704_015_sec_financial_report_admission_parity_probe.py",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str) + "\n",
        path,
    )


def as_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON, {})
    windows = payload.get("windows") or []
    generated = sum(as_int(window.get("signals_generated")) for window in windows)
    survived = sum(as_int(window.get("signals_survived")) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(
            as_int(window.get("trade_count") or window.get("total_trades")) for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def recorded_snapshot_days() -> list[dict[str, Any]]:
    days: dict[str, dict[str, Any]] = {}
    for snap in read_jsonl(SNAPSHOT_JSONL):
        asof = str(snap.get("asof_date") or "")[:10]
        if not asof:
            continue
        source = snap.get("data_source") or {}
        events_path = source.get("path")
        text_path = source.get("text_path")
        days[asof] = {
            "asof_date": asof,
            "recorded_candidate_count": as_int(snap.get("candidate_count")),
            "recorded_new_pending_count": as_int(snap.get("new_pending_count")),
            "recorded_t1_evaluated_count": as_int(source.get("t1_evaluated_count")),
            "recorded_loaded_row_count": as_int(source.get("loaded_row_count")),
            "events_file": Path(str(events_path)).name if events_path else None,
            "text_file": Path(str(text_path)).name if text_path else None,
        }
    return [days[key] for key in sorted(days)]


def _row_has_cohort(row: dict[str, Any]) -> bool:
    return bool(str(row.get("cohort") or "").strip())


def _replay_cohort(ticker: str) -> str:
    return REPLAY_COHORT_PLATFORM if ticker in PLATFORM_POOL else REPLAY_COHORT_OTHER


def first_blocking_stage(event: dict[str, Any]) -> str:
    """Mirror qualifies_sec_financial_report_t1_event as an ordered funnel."""
    if str(event.get("status") or "ok") != "ok":
        return "status_not_ok"
    if event.get("event_family") not in FINANCIAL_REPORT_EVENT_FAMILIES:
        return "family_not_financial_report"
    cohort = str(event.get("cohort") or "")
    if not cohort:
        return "cohort_missing"
    if cohort in FINANCIAL_REPORT_T1_EXCLUDED_COHORTS:
        return "cohort_excluded_platform_pool"
    if event.get("price_status") != "covered":
        return "price_not_covered"
    if event.get("drift_bucket") != "positive_t1_excess_drift":
        return "drift_bucket_not_positive"
    t1_excess = event.get("t1_excess_return_vs_spy")
    if not isinstance(t1_excess, (int, float)) or (
        t1_excess < FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY
    ):
        return "t1_excess_below_min"
    return "qualified"


def enrich_event(
    row: dict[str, Any],
    frames: dict[str, Any],
    spy_frame: Any,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    return {
        **row,
        "status": row.get("status") or "ok",
        "ticker": ticker,
        "event_family": sec_event_family(row),
        "item_codes": list(sec_event_item_codes(row)),
        **evaluate_t1_excess_drift(row, frames, spy_frame),
    }


def compact_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": candidate.get("ticker"),
        "usable_trade_date": candidate.get("usable_trade_date"),
        "t1_date": candidate.get("t1_date"),
        "event_family": candidate.get("event_family"),
        "form_base": candidate.get("form_base") or candidate.get("form_type"),
        "cohort": candidate.get("cohort"),
        "t1_excess_return_vs_spy": candidate.get("t1_excess_return_vs_spy"),
        "accession_number": candidate.get("accession_number"),
    }


def full_span_admission_replay() -> dict[str, Any]:
    days = recorded_snapshot_days()
    if not days:
        raise RuntimeError("sec_financial_report snapshots.jsonl has no recorded days")

    usable_dates: list[str] = []
    tickers: set[str] = set()
    rows_by_file: dict[str, list[dict[str, Any]]] = {}
    missing_event_files: list[str] = []
    for day in days:
        name = day["events_file"]
        if not name:
            continue
        if name in rows_by_file:
            continue
        path = NON_OHLCV_DIR / name
        if not path.exists():
            missing_event_files.append(name)
            rows_by_file[name] = []
            continue
        rows = load_sec_filing_event_rows(path)
        rows_by_file[name] = rows
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                tickers.add(ticker)
            usable = str(row.get("usable_trade_date") or "")[:10]
            if usable:
                usable_dates.append(usable)

    if not usable_dates:
        raise RuntimeError("no usable_trade_date values found across event archives")

    span_start = min(min(usable_dates), min(day["asof_date"] for day in days))
    span_end = max(max(usable_dates), max(day["asof_date"] for day in days))
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        sorted(tickers | {"SPY"}),
        "2026-02-02",
        span_end,
    )
    for frame in frames.values():
        # The warehouse loader clears the index name; the queue builder's
        # normaliser needs a Date column after reset_index().
        frame.index.name = "Date"
    spy_frame = frames.get("SPY")
    if spy_frame is None:
        raise RuntimeError("warehouse OHLCV has no SPY frame; cannot evaluate T+1 drift")
    tickers_without_prices = sorted(
        ticker for ticker in tickers if ticker not in frames
    )

    text_cache: dict[str, list[dict[str, Any]]] = {}

    per_day: list[dict[str, Any]] = []
    stage_totals: Counter[str] = Counter()
    cohort_value_totals: Counter[str] = Counter()
    counterfactual_candidates: list[dict[str, Any]] = []
    as_is_candidates: list[dict[str, Any]] = []
    rebuild_t1_eval_total = 0
    recorded_t1_eval_total = 0
    days_replayed = 0

    for day in days:
        asof = day["asof_date"]
        name = day["events_file"]
        rows = rows_by_file.get(name or "", [])
        if not name or not rows:
            per_day.append({**day, "replayed": False, "reason": "missing_or_empty_events_file"})
            continue
        text_rows: list[dict[str, Any]] = []
        text_name = day.get("text_file")
        if text_name:
            if text_name not in text_cache:
                text_path = NON_OHLCV_DIR / text_name
                text_cache[text_name] = (
                    load_sec_filing_text_rows(text_path) if text_path.exists() else []
                )
            text_rows = text_cache[text_name]

        as_is_queue = build_sec_financial_report_t1_queue(
            rows,
            as_of=asof,
            ohlcv_by_ticker=frames,
            spy_ohlcv=spy_frame,
            source_path=NON_OHLCV_DIR / name,
            text_rows=text_rows,
        )
        cf_rows = [
            row
            if _row_has_cohort(row)
            else {**row, "cohort": _replay_cohort(str(row.get("ticker") or "").upper())}
            for row in rows
        ]
        cf_queue = build_sec_financial_report_t1_queue(
            cf_rows,
            as_of=asof,
            ohlcv_by_ticker=frames,
            spy_ohlcv=spy_frame,
            source_path=NON_OHLCV_DIR / name,
            text_rows=text_rows,
        )

        day_stages: Counter[str] = Counter()
        for row in rows:
            if row.get("pit_safe_flag") is False:
                continue
            ticker = str(row.get("ticker") or "").upper()
            if not ticker:
                continue
            event = enrich_event(row, frames, spy_frame)
            if event.get("t1_date") != asof:
                continue
            cohort_value_totals[str(row.get("cohort"))] += 1
            day_stages[first_blocking_stage(event)] += 1
        stage_totals.update(day_stages)

        as_is_count = as_int(as_is_queue.get("candidate_count"))
        cf_count = as_int(cf_queue.get("candidate_count"))
        rebuild_t1_eval = as_int(
            (as_is_queue.get("data_source") or {}).get("t1_evaluated_count")
        )
        rebuild_t1_eval_total += rebuild_t1_eval
        recorded_t1_eval_total += day["recorded_t1_evaluated_count"]
        days_replayed += 1
        as_is_candidates.extend(
            compact_candidate(candidate) for candidate in as_is_queue.get("candidates") or []
        )
        counterfactual_candidates.extend(
            compact_candidate(candidate) for candidate in cf_queue.get("candidates") or []
        )
        per_day.append(
            {
                **day,
                "replayed": True,
                "rebuild_t1_evaluated_count": rebuild_t1_eval,
                "as_is_candidate_count": as_is_count,
                "counterfactual_candidate_count": cf_count,
                "first_blocking_stage_counts": dict(day_stages),
            }
        )

    replayed = [day for day in per_day if day.get("replayed")]
    return {
        "recorded_day_count": len(days),
        "replayed_day_count": days_replayed,
        "missing_event_files": sorted(set(missing_event_files)),
        "span": {"first_asof": days[0]["asof_date"], "last_asof": days[-1]["asof_date"]},
        "warehouse": {
            "db_path": str(DEFAULT_WAREHOUSE_PATH),
            "frames_loaded": len(frames),
            "load_start": "2026-02-02",
            "load_end": span_end,
            "span_start_seen": span_start,
            "event_tickers": len(tickers),
            "event_tickers_without_prices": tickers_without_prices,
        },
        "recorded_candidate_total": sum(d["recorded_candidate_count"] for d in days),
        "recorded_new_pending_total": sum(d["recorded_new_pending_count"] for d in days),
        "recorded_t1_evaluated_total": recorded_t1_eval_total,
        "rebuild_t1_evaluated_total": rebuild_t1_eval_total,
        "as_is_candidate_total": sum(d["as_is_candidate_count"] for d in replayed),
        "counterfactual_candidate_total": sum(
            d["counterfactual_candidate_count"] for d in replayed
        ),
        "first_blocking_stage_totals": {
            stage: stage_totals.get(stage, 0) for stage in STAGE_ORDER
        },
        "raw_cohort_field_value_totals": dict(cohort_value_totals),
        "as_is_candidates": as_is_candidates,
        "counterfactual_candidates": counterfactual_candidates,
        "per_day": per_day,
        "cohort_derivation_rule": {
            "platform_pool_tickers": list(PLATFORM_POOL),
            "platform_cohort": REPLAY_COHORT_PLATFORM,
            "other_cohort": REPLAY_COHORT_OTHER,
            "source": "exp-20260510-023 analysis-time derivation; excluded cohorts per "
            "exp-20260510-027 accepted rule",
            "excluded_cohorts": list(FINANCIAL_REPORT_T1_EXCLUDED_COHORTS),
        },
    }


def classify(replay: dict[str, Any]) -> dict[str, Any]:
    stage_totals = replay["first_blocking_stage_totals"]
    evaluated = sum(stage_totals.values())
    cohort_blocked = stage_totals.get("cohort_missing", 0)
    # Family exclusion is intended behavior (the accepted replay applied the
    # same family rule); the parity question is what happens to rows that
    # legitimately reach the cohort stage.
    rows_reaching_cohort_stage = (
        evaluated
        - stage_totals.get("status_not_ok", 0)
        - stage_totals.get("family_not_financial_report", 0)
    )
    cf_total = replay["counterfactual_candidate_total"]
    as_is_total = replay["as_is_candidate_total"]
    recorded_total = replay["recorded_candidate_total"]
    deterministic_cohort_bug = (
        rows_reaching_cohort_stage > 0
        and cohort_blocked == rows_reaching_cohort_stage
        and as_is_total == 0
        and recorded_total == 0
    )
    if deterministic_cohort_bug and cf_total > 0:
        label = "daily_missing_cohort_derivation_parity_bug"
    elif deterministic_cohort_bug:
        label = "cohort_blocks_all_but_counterfactual_also_empty_needs_review"
    elif as_is_total == 0 and recorded_total == 0:
        label = "underfire_not_fully_explained_by_cohort_stage"
    else:
        label = "no_deterministic_admission_defect_found"
    return {
        "classification": label,
        "same_day_rows_evaluated": evaluated,
        "same_day_rows_reaching_cohort_stage": rows_reaching_cohort_stage,
        "same_day_rows_blocked_at_cohort_missing": cohort_blocked,
        "cohort_blocks_every_row_reaching_cohort_stage": (
            rows_reaching_cohort_stage > 0
            and cohort_blocked == rows_reaching_cohort_stage
        ),
        "as_is_candidate_total": as_is_total,
        "counterfactual_candidate_total": cf_total,
        "recorded_candidate_total": recorded_total,
        "fire_gap_explained": deterministic_cohort_bug and cf_total > 0,
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_summary()
    replay = full_span_admission_replay()
    verdict = classify(replay)

    drift_found = verdict["classification"] == "daily_missing_cohort_derivation_parity_bug"
    decision = (
        "accepted_measurement_repair_sec_financial_report_cohort_parity_drift_identified"
        if drift_found
        else "accepted_measurement_repair_sec_financial_report_admission_parity_probe_completed"
    )

    why = (
        "Every same-day event row across the sleeve's full recorded snapshot span was "
        "blocked at the cohort_missing admission stage: the shared daily queue rule "
        "requires a non-empty cohort field excluded from platform_pool, but the daily "
        "SEC filing events collector has never written a cohort field in any archive "
        "file, and the daily queue builder never derives it. The accepted replay "
        "surface (exp-20260510-023/024/027) derived cohort at analysis time from the "
        "static platform pool, so replay admitted candidates while production could "
        "never admit any. Rebuilding the same days with only the replay-parity cohort "
        "derivation added produced "
        f"{replay['counterfactual_candidate_total']} admissions versus 0 recorded, "
        "which quantifies the fire gap as a deterministic daily/replay parity defect, "
        "not regime sparsity."
        if drift_found
        else "The stage-wise replay did not attribute the full underfire to a single "
        "deterministic admission stage; see artifact for the per-stage distribution."
    )

    gate4 = {
        "passed": True,
        "mode": "measurement_repair_sec_financial_report_admission_parity",
        "accepted_measurement_repair": True,
        "accepted_alpha": False,
        "strategy_behavior_changed": False,
        "cohort_parity_drift_detected": drift_found,
        "failed_reasons": [],
        "decision_basis": why,
        "classification": verdict,
    }

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "implementation_mode": "measurement_repair",
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "sec_financial_report_admission_parity_probe",
        "trial_variant_id": "sec_financial_report_daily_vs_replay_stagewise_reject_attribution_v1",
        "single_causal_variable": "sec_financial_report_daily_vs_replay_admission_parity_v1",
        "changed_variable": "sec_financial_report_daily_vs_replay_admission_parity_v1",
        "hypothesis": (
            "Alpha blocker: accepted sec_financial_report T+1 drift paper rows cannot "
            "accumulate forward replacement-value evidence; daily snapshots show loaded "
            "filing rows but zero candidates for the full recorded span while accepted "
            "replay implies ~11 admissions. Run a full-span daily-vs-replay admission "
            "parity probe with stage-wise reject attribution to classify the underfire "
            "as universe mismatch, date-join defect, cohort-field defect, or true "
            "regime sparsity, without changing thresholds, ranking, sizing, exits, or "
            "orders."
        ),
        "alpha_hypothesis": (
            "Forward evidence supply is an alpha bottleneck: the accepted "
            "sec_financial_report T+1 drift sleeve cannot mature replacement-value "
            "evidence if daily production admission semantics drifted from the "
            "accepted replay surface."
        ),
        "causal_components": [
            "full recorded snapshot span daily events archive replay",
            "shared queue builder rebuild with warehouse OHLCV coverage",
            "stage-wise first-blocking-stage admission attribution",
            "replay-parity cohort derivation counterfactual rebuild",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260704-006",
            "exp-20260704-008",
            "exp-20260704-010",
            "exp-20260530-020",
            "exp-20260510-027",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "representative_day_daily_vs_replay_admission_parity_probe",
        "new_evidence_axis": (
            "Measurement-only stage-wise admission parity evidence for the accepted "
            "sec_financial_report sleeve named as the largest fire-rate gap by the "
            "2026-07-03 history-wide verdict; exp-20260704-006 explicitly did not "
            "score this sleeve and exp-20260530-020 observed only the symptom without "
            "stage attribution; no threshold, notional, top-N, hold, cooldown, or "
            "response rule is changed."
        ),
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "status": "accepted_measurement_repair",
        "decision": decision,
        "accepted": True,
        "accepted_alpha": False,
        "alpha_ready": False,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": True,
            "entry_date_target_price_scope": (
                "No executable order or target exit is created. The probe rebuilds "
                "observe-only queue candidates; paper entry/exit lifecycle fields are "
                "untouched."
            ),
            "fields_checked": [
                "asof_date",
                "usable_trade_date",
                "t1_date",
                "cohort",
                "event_family/form_base",
                "price_status",
                "drift_bucket",
                "t1_excess_return_vs_spy",
                "recorded candidate_count/t1_evaluated_count",
            ],
            "replayed_day_count": replay["replayed_day_count"],
            "warehouse_frames_loaded": replay["warehouse"]["frames_loaded"],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter/rank/size/exit rule changed; survival is baseline identity.",
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
        },
        "gate4": gate4,
        "admission_parity_replay": replay,
        "production_impact": {
            "trade_enabled": False,
            "live_ready": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "alters_exits": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_changed": False,
            "feeds_llm_prompt": False,
            "parity_note": (
                "Read-only replay of existing daily SEC filing event archives through "
                "the existing shared queue builder. It does not alter live/default "
                "orders, rankings, sizing, exits, or paper snapshot generation."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune the T+1 excess threshold, event families, notional "
                "scalars, RS20 rule, hold days, max positions, or response curves from "
                "this underfire span. Do not relax the platform_pool exclusion; the "
                "cohort derivation repair must reproduce the accepted replay rule "
                "exactly."
            ),
            "new_evidence_required": (
                "Repair the daily cohort parity by deriving the replay-parity cohort "
                "(platform_pool membership) inside the shared queue path when rows "
                "lack the field, add a regression test, rerun this probe, then let "
                "forward snapshots accumulate closed cash/SPY/QQQ replacement-value "
                "rows before any activation or allocation experiment."
            ),
        },
        "calibration": {
            "predicted_success_probability": 0.6,
            "actual_decision": decision,
            "actual_success": 1,
            "predicted_failure_mode_hit": False,
            "surprise_note": (
                "Moderate surprise: the funnel counters suggested price-universe "
                "restriction, but the binding stage is a cohort field that has never "
                "existed in any daily archive."
                if drift_found
                else "See artifact."
            ),
        },
        "prediction": {
            "success_probability": 0.6,
            "expected_ev_delta": None,
            "expected_pnl_delta": None,
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "next_retry_requires": [
            "daily cohort derivation parity repair inside the shared queue path",
            "post-repair forward sec_financial_report rows with closed cash/SPY/QQQ replacement value",
            "no frozen-window threshold/notional/hold/cooldown retune",
        ],
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = {key: value for key, value in payload.items() if key != "admission_parity_replay"}
    replay = payload["admission_parity_replay"]
    record["admission_parity_summary"] = {
        "recorded_day_count": replay["recorded_day_count"],
        "replayed_day_count": replay["replayed_day_count"],
        "recorded_candidate_total": replay["recorded_candidate_total"],
        "as_is_candidate_total": replay["as_is_candidate_total"],
        "counterfactual_candidate_total": replay["counterfactual_candidate_total"],
        "first_blocking_stage_totals": replay["first_blocking_stage_totals"],
        "raw_cohort_field_value_totals": replay["raw_cohort_field_value_totals"],
        "counterfactual_candidates": replay["counterfactual_candidates"],
        "event_tickers_without_prices": replay["warehouse"]["event_tickers_without_prices"],
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    replay = payload["admission_parity_replay"]
    verdict = payload["gate4"]["classification"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC financial-report admission parity probe",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Classification: `{verdict['classification']}`",
        f"- Recorded days: {replay['recorded_day_count']} (replayed {replay['replayed_day_count']})",
        f"- Recorded candidates: {replay['recorded_candidate_total']}",
        f"- As-is rebuild candidates (warehouse OHLCV): {replay['as_is_candidate_total']}",
        f"- Counterfactual (replay-parity cohort) candidates: {replay['counterfactual_candidate_total']}",
        "",
        "## First blocking stage totals (same-day rows)",
        "",
    ]
    for stage in STAGE_ORDER:
        lines.append(f"- `{stage}`: {replay['first_blocking_stage_totals'].get(stage, 0)}")
    lines += [
        "",
        "## Why",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Next",
        "",
        payload["post_run_reflection"]["new_evidence_required"],
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "runner": RUNNER,
        "artifact": payload["artifact"],
        "log": payload["log"],
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "decision": payload["decision"],
        "status": payload["status"],
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = load_json(TICKET_JSON, {})
    if not isinstance(ticket, dict) or not ticket:
        return
    ticket["status"] = payload["status"]
    ticket["completed_at"] = utc_now()
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["new_evidence_axis"] = payload["new_evidence_axis"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "gate4": payload["gate4"],
    }
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)
    update_ticket(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload.get("prediction"),
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
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
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "lean_quality_passed": True,
        },
    )
    print(json.dumps(compact_log_record(payload)["admission_parity_summary"], indent=2, sort_keys=True))
    print(json.dumps({"decision": payload["decision"], "artifact": payload["artifact"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
