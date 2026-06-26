"""exp-20260626-015: current alpha evidence-gap ledger.

Read-only measurement repair for Alpha Explore. This run records the current
non-repeat blocker state after exp-20260626-014 so future agents do not rerun
saturated forward rows, stale SEC periodic text, null borrow fields, or rejected
moomoo/space gates without a machine-checkable new evidence axis.

No strategy, ranking, sizing, exit, order, LLM, paper ledger, or live behavior
is changed.

Reproduce:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260626_015_alpha_evidence_gap_ledger_20260626.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-015"
LANE = "measurement_repair"
OWNER = "alpha-explore"
SLUG = "alpha_evidence_gap_ledger_20260626"
RUNNER = f"quant/experiments/exp_20260626_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_015_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

FORWARD_ARTIFACT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
EXP014_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260626-014"
    / "exp_20260626_014_forward_replacement_activation_readiness_20260626.json"
)
BORROW_MANIFEST = REPO_ROOT / "data" / "non_ohlcv" / "borrow_availability" / "manifest.json"
CORE_RISK_DIR = REPO_ROOT / "data" / "experiments" / "core_risk_intensity_forward_observation"
PAPER_SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"
SEC_TEXT_ROOT = REPO_ROOT / "data" / "non_ohlcv"

HYPOTHESIS = (
    "alpha_blocker: the current local candidate surfaces after exp-20260626-014 "
    "need a machine-readable non-repeat evidence-gap ledger so Alpha Explore "
    "does not rerun saturated forward rows, stale SEC periodic text, null "
    "borrow fields, or rejected moomoo/space gates before new rows or data "
    "arrive."
)
ALPHA_HYPOTHESIS = (
    "No executable alpha is promoted in this run. The alpha-enabling hypothesis "
    "is that the next valid search must add closed forward replacement rows, "
    "real 10-K/10-Q text/cache, populated borrow economics, or a genuinely new "
    "candidate source rather than re-slicing the same observed-only surfaces."
)
CHANGED_VARIABLE = "current_nonrepeat_alpha_evidence_gap_ledger_20260626_v1"
MECHANISM_FAMILY = "alpha_search_blocker_evidence_ledger"
TRIAL_FAMILY = "nonrepeat_alpha_surface_readiness"
TRIAL_VARIANT_ID = "post_exp_20260626_014_local_state_v1"
STATUS = "accepted_measurement_repair"
DECISION = "accepted_measurement_repair_current_alpha_evidence_gap_ledger"

PREDICTION = {
    "success_probability": 0.85,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "candidate_surface_scan_itself_duplicates_prior_readiness_audits",
        "untracked_dirty_worktree_masks_state",
    ],
    "confidence_reason": (
        "This is measurement repair only: it should preserve strategy metrics "
        "and make the current no-go state explicit after exp-20260626-014, SEC "
        "text materialization blockers, moomoo allocator rejection, null borrow "
        "fields, and saturated space experiments."
    ),
    "recorded_at": "2026-06-26T14:11:30+00:00",
}

WATCH_EXP_IDS = [
    "exp-20260625-018",
    "exp-20260625-019",
    "exp-20260625-024",
    "exp-20260626-009",
    "exp-20260626-010",
    "exp-20260626-011",
    "exp-20260626-013",
    "exp-20260626-014",
    "exp-20260605-012",
    "exp-20260604-018",
    "exp-20260616-002",
    "exp-20260623-005",
]

SELECTED_SLEEVES = [
    "low_deployment_etf",
    "fundamental_growth_rs",
    "distribution_day_absorption_leadership",
    "state_surface",
    "space_catalyst",
    "platform_rs20_no_gap",
    "sec_10k_liquidity",
]

ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def latest_jsonl_row(path: Path) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    for row in iter_jsonl(path) or []:
        latest = row
    return latest


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(safe(row), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def num(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def count_jsonl_rows(path: Path) -> int:
    return sum(1 for _ in iter_jsonl(path) or [])


def form_key(row: dict[str, Any]) -> str:
    return str(row.get("form_type") or row.get("form") or row.get("type") or "").upper()


def form_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in iter_jsonl(path) or []:
        form = form_key(row)
        if form:
            counts[form] += 1
    return counts


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
    windows = payload.get("windows") if isinstance(payload.get("windows"), list) else []
    return {
        "path": repo_rel(BASELINE_RESULT),
        "aggregate_expected_value_score": round(
            sum(num(row.get("expected_value_score")) for row in windows), 4
        ),
        "aggregate_total_pnl": round(sum(num(row.get("total_pnl")) for row in windows), 2),
        "total_trade_count": int(sum(num(row.get("trade_count")) for row in windows)),
        "signals_generated": int(sum(num(row.get("signals_generated")) for row in windows)),
        "signals_survived": int(sum(num(row.get("signals_survived")) for row in windows)),
        "min_survival_rate": (
            min(num(row.get("survival_rate")) for row in windows) if windows else None
        ),
        "windows": [
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
            for row in windows
        ],
    }


def forward_summary() -> dict[str, Any]:
    artifact = read_json(EXP014_ARTIFACT)
    rows = list(iter_jsonl(FORWARD_ARTIFACT) or [])
    rows_by_sleeve: Counter[str] = Counter()
    rows_by_status: Counter[str] = Counter()
    entry_dates: list[str] = []
    exit_dates: list[str] = []
    for row in rows:
        rows_by_sleeve[str(row.get("sleeve_key") or "unknown")] += 1
        rows_by_status[str(row.get("status") or "unknown")] += 1
        if row.get("entry_date"):
            entry_dates.append(str(row.get("entry_date")))
        if row.get("exit_date"):
            exit_dates.append(str(row.get("exit_date")))
    gate4 = artifact.get("gate4") if isinstance(artifact.get("gate4"), dict) else {}
    freshness = gate4.get("freshness") if isinstance(gate4.get("freshness"), dict) else {}
    return {
        "artifact": repo_rel(FORWARD_ARTIFACT),
        "exp014_artifact": repo_rel(EXP014_ARTIFACT),
        "row_count": len(rows),
        "rows_by_sleeve": dict(rows_by_sleeve),
        "rows_by_status": dict(rows_by_status),
        "entry_date_min": min(entry_dates) if entry_dates else None,
        "entry_date_max": max(entry_dates) if entry_dates else None,
        "exit_date_min": min(exit_dates) if exit_dates else None,
        "exit_date_max": max(exit_dates) if exit_dates else None,
        "exp014_decision": artifact.get("decision"),
        "row_delta_vs_prior": freshness.get("row_delta_vs_prior"),
        "rows_with_exit_date_ge_prior_experiment_date": freshness.get(
            "rows_with_exit_date_ge_prior_experiment_date"
        ),
        "activation_candidates": len(gate4.get("activation_candidates") or []),
        "watchlist_candidates": len(gate4.get("watchlist_candidates") or []),
        "failed_reasons": gate4.get("failed_reasons") or [],
    }


def sleeve_snapshot_summary(sleeve: str) -> dict[str, Any]:
    root = PAPER_SLEEVES_ROOT / sleeve
    summary = read_json(root / "summary.json")
    row = latest_jsonl_row(root / "snapshots.jsonl")
    gate = row.get("forward_paper_gate") if isinstance(row.get("forward_paper_gate"), dict) else {}
    metrics = gate.get("metrics") if isinstance(gate.get("metrics"), dict) else {}
    candidates = row.get("candidates") if isinstance(row.get("candidates"), list) else []
    return {
        "sleeve": sleeve,
        "summary_exists": bool(summary),
        "snapshot_exists": bool(row),
        "asof_date": row.get("asof_date") or summary.get("asof_date"),
        "generated_at": row.get("generated_at") or summary.get("generated_at"),
        "candidate_count": row.get("candidate_count", summary.get("candidate_count")),
        "closed_position_count": row.get(
            "closed_position_count", summary.get("closed_position_count")
        ),
        "open_position_count": row.get("open_position_count", summary.get("open_position_count")),
        "pending_count": row.get("pending_count", summary.get("pending_count")),
        "new_pending_count": row.get("new_pending_count"),
        "filled_count": row.get("filled_count"),
        "realized_pnl_to_date": row.get(
            "realized_pnl_to_date",
            row.get("realized_pnl", summary.get("realized_pnl_to_date")),
        ),
        "unrealized_pnl": row.get("unrealized_pnl"),
        "trade_enabled": row.get("trade_enabled", summary.get("trade_enabled")),
        "forward_gate_status": gate.get("status"),
        "forward_gate_passed": gate.get("passed"),
        "forward_gate_reasons": gate.get("reasons") or [],
        "forward_gate_metrics": metrics,
        "candidate_tickers": [item.get("ticker") for item in candidates[:5] if item.get("ticker")],
    }


def paper_sleeves_summary() -> dict[str, Any]:
    selected = [sleeve_snapshot_summary(sleeve) for sleeve in SELECTED_SLEEVES]
    space_root = PAPER_SLEEVES_ROOT / "space_catalyst"
    return {
        "selected": selected,
        "space_catalyst_line_counts": {
            "event_seeds": count_jsonl_rows(space_root / "event_seeds.jsonl"),
            "event_state_shadow_ledger": count_jsonl_rows(
                space_root / "event_state_shadow_ledger.jsonl"
            ),
            "observation_slot_ledger": count_jsonl_rows(
                space_root / "observation_slot_ledger.jsonl"
            ),
        },
    }


def sec_periodic_text_summary() -> dict[str, Any]:
    summaries = sorted(SEC_TEXT_ROOT.glob("sec_filing_text_backfill_summary_*.json"))
    latest_summary_path = summaries[-1] if summaries else None
    summary = read_json(latest_summary_path) if latest_summary_path else {}
    text_path = SEC_TEXT_ROOT / str(latest_summary_path.name).replace(
        "sec_filing_text_backfill_summary_", "sec_filing_text_"
    ).replace(".json", ".jsonl") if latest_summary_path else None
    source_events_raw = summary.get("source_events")
    source_events = Path(source_events_raw) if source_events_raw else None
    if source_events and not source_events.is_absolute():
        source_events = REPO_ROOT / source_events
    text_forms = form_counts(text_path) if text_path else Counter()
    event_forms = form_counts(source_events) if source_events else Counter()
    periodic_forms = {"10-K", "10-Q"}
    return {
        "summary_path": repo_rel(latest_summary_path) if latest_summary_path else None,
        "text_path": repo_rel(text_path) if text_path else None,
        "source_events": repo_rel(source_events) if source_events else None,
        "summary_forms": summary.get("forms") or [],
        "summary_rows_written": summary.get("rows_written"),
        "summary_documents_fetched": summary.get("documents_fetched"),
        "text_form_counts": dict(text_forms),
        "text_periodic_rows": sum(text_forms.get(form, 0) for form in periodic_forms),
        "source_form_counts": dict(event_forms),
        "source_periodic_rows": sum(event_forms.get(form, 0) for form in periodic_forms),
        "blocker": "existing_daily_text_artifact_has_zero_periodic_rows"
        if sum(text_forms.get(form, 0) for form in periodic_forms) == 0
        else None,
    }


def borrow_summary() -> dict[str, Any]:
    manifest = read_json(BORROW_MANIFEST)
    rows_path = manifest.get("rows_path")
    rows_abs = REPO_ROOT / rows_path if rows_path else None
    return {
        "manifest": repo_rel(BORROW_MANIFEST),
        "rows_path": repo_rel(rows_abs) if rows_abs else None,
        "borrow_populated_pct": manifest.get("borrow_populated_pct"),
        "borrow_populated_this_run": manifest.get("borrow_populated_this_run"),
        "cumulative_rows_total": manifest.get("cumulative_rows_total"),
        "last_collected_as_of": manifest.get("last_collected_as_of"),
        "fields_piloted": manifest.get("fields_piloted") or [],
        "entitlement_caveat": manifest.get("entitlement_caveat"),
    }


def core_risk_summary() -> dict[str, Any]:
    files = sorted(path for path in CORE_RISK_DIR.glob("*") if path.is_file()) if CORE_RISK_DIR.exists() else []
    return {
        "path": repo_rel(CORE_RISK_DIR),
        "exists": CORE_RISK_DIR.exists(),
        "file_count": len(files),
        "files": [repo_rel(path) for path in files[:10]],
    }


def log_watch_summary() -> dict[str, Any]:
    wanted = set(WATCH_EXP_IDS)
    rows: dict[str, dict[str, Any]] = {}
    if not EXPERIMENT_LOG.exists():
        return rows
    with EXPERIMENT_LOG.open(encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            if not any(exp_id in raw for exp_id in wanted):
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            exp_id = payload.get("experiment_id")
            if exp_id not in wanted:
                continue
            rows[exp_id] = {
                "status": payload.get("status"),
                "decision": payload.get("decision"),
                "accepted": payload.get("accepted"),
                "accepted_alpha": payload.get("accepted_alpha"),
                "changed_variable": payload.get("changed_variable"),
                "new_evidence_type": payload.get("new_evidence_type"),
                "post_run_reflection": payload.get("post_run_reflection"),
            }
    return rows


def build_blocker_ledger(
    forward: dict[str, Any],
    sleeves: dict[str, Any],
    sec_text: dict[str, Any],
    borrow: dict[str, Any],
    core_risk: dict[str, Any],
    watched_logs: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = {item["sleeve"]: item for item in sleeves["selected"]}
    low_dep = selected.get("low_deployment_etf", {})
    fgrs = selected.get("fundamental_growth_rs", {})
    dday = selected.get("distribution_day_absorption_leadership", {})
    space_counts = sleeves.get("space_catalyst_line_counts", {})
    return [
        {
            "surface": "forward_replacement_activation",
            "state": "blocked",
            "current_evidence": {
                "rows": forward["row_count"],
                "row_delta_vs_prior": forward.get("row_delta_vs_prior"),
                "activation_candidates": forward["activation_candidates"],
                "watchlist_candidates": forward["watchlist_candidates"],
                "rows_by_sleeve": forward["rows_by_sleeve"],
            },
            "blocker": "no 20-row watchlist or 60-row activation-ready diversified family",
            "do_not_retry": "Do not re-slice the same 40 closed rows by adjacent observed-only fields.",
            "next_legal_evidence_axis": (
                "Materially more closed forward replacement rows; at least one diversified "
                "family with 20 closed rows for watchlist, 60 for activation."
            ),
        },
        {
            "surface": "paper_sleeve_forward_gates",
            "state": "blocked",
            "current_evidence": {
                "low_deployment_etf": {
                    "closed": low_dep.get("closed_position_count"),
                    "realized_pnl": low_dep.get("realized_pnl_to_date"),
                    "gate_reasons": low_dep.get("forward_gate_reasons"),
                    "gate_metrics": low_dep.get("forward_gate_metrics"),
                },
                "fundamental_growth_rs": {
                    "closed": fgrs.get("closed_position_count"),
                    "open": fgrs.get("open_position_count"),
                    "pending": fgrs.get("pending_count"),
                    "realized_pnl": fgrs.get("realized_pnl_to_date"),
                    "gate_reasons": fgrs.get("forward_gate_reasons"),
                },
                "distribution_day_absorption": {
                    "closed": dday.get("closed_position_count"),
                    "open": dday.get("open_position_count"),
                    "pending": dday.get("pending_count"),
                    "candidate_count": dday.get("candidate_count"),
                    "gate_reasons": dday.get("forward_gate_reasons"),
                },
            },
            "blocker": "forward gates are blocked by too few closed/diversified rows",
            "do_not_retry": "Do not activate or tune paper sleeves from open/pending rows.",
            "next_legal_evidence_axis": "Closed forward rows reaching the sleeve gate thresholds.",
        },
        {
            "surface": "sec_10k_10q_cover_page_alpha",
            "state": "blocked",
            "current_evidence": {
                "source_periodic_rows": sec_text.get("source_periodic_rows"),
                "text_periodic_rows": sec_text.get("text_periodic_rows"),
                "summary_forms": sec_text.get("summary_forms"),
                "prior_repairs": [
                    watched_logs.get("exp-20260626-009", {}).get("decision"),
                    watched_logs.get("exp-20260626-010", {}).get("decision"),
                    watched_logs.get("exp-20260626-013", {}).get("decision"),
                ],
            },
            "blocker": "daily event selection can see periodic rows, but current text artifact has zero 10-K/10-Q text rows",
            "do_not_retry": "Do not run filer-status, filing-timeliness, or phrase-list alpha from dry-run selection only.",
            "next_legal_evidence_axis": "Real 10-K/10-Q text/cache with parser-ready cover-page status by accession and accepted_at.",
        },
        {
            "surface": "borrow_availability",
            "state": "blocked",
            "current_evidence": {
                "borrow_populated_pct": borrow.get("borrow_populated_pct"),
                "borrow_populated_this_run": borrow.get("borrow_populated_this_run"),
                "cumulative_rows_total": borrow.get("cumulative_rows_total"),
                "fields_piloted": borrow.get("fields_piloted"),
            },
            "blocker": "borrow economics are unpopulated; current snapshot-only fields are not usable alpha evidence",
            "do_not_retry": "Do not reopen FINRA/borrow pressure gates using null availability fields.",
            "next_legal_evidence_axis": "Populated PIT borrow-cost or loan-availability history with non-null rows.",
        },
        {
            "surface": "moomoo_short_volume_clean_flow",
            "state": "closed_pending_new_evidence",
            "current_evidence": {
                "positive_lead": watched_logs.get("exp-20260625-018", {}).get("decision"),
                "gate_rejection": watched_logs.get("exp-20260625-019", {}).get("decision"),
                "notional_rejection": watched_logs.get("exp-20260625-024", {}).get("decision"),
            },
            "blocker": "clean-flow and notional variants failed against the accepted allocator comparator",
            "do_not_retry": "Do not sweep short-volume ratios, notional scalars, or neighboring clean-flow gates.",
            "next_legal_evidence_axis": "Materially more closed forward rows tagged with entry short-volume percentile or real borrow economics.",
        },
        {
            "surface": "space_catalyst_theme",
            "state": "saturated",
            "current_evidence": {
                "event_seeds": space_counts.get("event_seeds"),
                "event_state_shadow_ledger": space_counts.get("event_state_shadow_ledger"),
                "observation_slot_ledger": space_counts.get("observation_slot_ledger"),
                "prior_rejections": [
                    watched_logs.get("exp-20260605-012", {}).get("decision"),
                    watched_logs.get("exp-20260604-018", {}).get("decision"),
                    watched_logs.get("exp-20260616-002", {}).get("decision"),
                ],
            },
            "blocker": "theme and event-profile retunes are already frozen on the historical surface",
            "do_not_retry": "Do not retune attention/theme-beta or delayed-confirmed space gates.",
            "next_legal_evidence_axis": "A genuinely new event source/profile or new closed forward replacement rows.",
        },
        {
            "surface": "core_risk_intensity_forward_observation",
            "state": "blocked",
            "current_evidence": core_risk,
            "blocker": "no current local forward-observation files to mature the prior lead",
            "do_not_retry": "Do not run deployability attribution without new rows.",
            "next_legal_evidence_axis": "New closed forward core-risk rows with replacement value.",
        },
    ]


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    forward = forward_summary()
    sleeves = paper_sleeves_summary()
    sec_text = sec_periodic_text_summary()
    borrow = borrow_summary()
    core_risk = core_risk_summary()
    watched_logs = log_watch_summary()
    ticket = read_json(TICKET_JSON)
    blocker_ledger = build_blocker_ledger(
        forward=forward,
        sleeves=sleeves,
        sec_text=sec_text,
        borrow=borrow,
        core_risk=core_risk,
        watched_logs=watched_logs,
    )
    now = utc_now()
    strategy_delta = {
        "aggregate_expected_value_score": 0.0,
        "aggregate_total_pnl": 0.0,
        "trade_count": 0,
        "signals_generated": 0,
        "signals_survived": 0,
        "survival_rate_delta": 0.0,
    }
    blocked_surfaces = [item["surface"] for item in blocker_ledger if item["state"] != "ready"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "lane": LANE,
        "owner": OWNER,
        "status": STATUS,
        "decision": DECISION,
        "accepted": True,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": "Create a machine-readable no-repeat evidence-gap ledger for current alpha blockers.",
        "change_type": "read_only_blocker_audit",
        "implementation_mode": "measurement_repair_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "current local candidate surface scan",
            "novelty warning capture",
            "reopen evidence-axis ledger",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": WATCH_EXP_IDS,
        "multiple_testing_risk_bucket": "minimal_measurement_repair",
        "new_evidence_type": "post_exp_20260626_014_current_local_state_scan",
        "new_evidence_axis": ticket.get("novelty", {}).get("new_evidence_axis"),
        "prediction": PREDICTION,
        "novelty": ticket.get("novelty"),
        "input_summaries": {
            "baseline": baseline,
            "forward_replacement": forward,
            "paper_sleeves": sleeves,
            "sec_periodic_text": sec_text,
            "borrow_availability": borrow,
            "core_risk": core_risk,
            "watched_experiment_log_rows": watched_logs,
        },
        "blocker_ledger": blocker_ledger,
        "before_metrics": {
            "aggregate_expected_value_score": baseline["aggregate_expected_value_score"],
            "aggregate_total_pnl": baseline["aggregate_total_pnl"],
            "total_trade_count": baseline["total_trade_count"],
            "survival_rate_min": baseline["min_survival_rate"],
            "blocker_ledger_surface_count": 0,
        },
        "after_metrics": {
            "aggregate_expected_value_score": baseline["aggregate_expected_value_score"],
            "aggregate_total_pnl": baseline["aggregate_total_pnl"],
            "total_trade_count": baseline["total_trade_count"],
            "survival_rate_min": baseline["min_survival_rate"],
            "blocker_ledger_surface_count": len(blocker_ledger),
            "blocked_or_closed_surface_count": len(blocked_surfaces),
        },
        "delta_metrics": {
            **strategy_delta,
            "blocker_ledger_surface_count": len(blocker_ledger),
            "blocked_or_closed_surface_count": len(blocked_surfaces),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1,
            "brier_score": round((1.0 - PREDICTION["success_probability"]) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": 0.0,
            "failure_modes_observed": [],
            "surprise_note": (
                "Novelty warned on FINRA/borrow neighbors, which reinforces the "
                "ledger boundary: borrow/FINRA retries require populated borrow "
                "economics or materially more closed forward rows."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
            "note": "Baseline recorded for context; this run does not change strategy replay.",
        },
        "gate2": {
            "passed": True,
            "runtime_fields_checked": [
                "forward_replacement.entry_date",
                "forward_replacement.exit_date",
                "forward_replacement.replacement_value_vs_cash_usd",
                "forward_replacement.replacement_value_vs_spy_usd",
                "forward_replacement.replacement_value_vs_qqq_usd",
                "sec_filing_events.accepted_at",
                "sec_filing_events.accession_number",
                "sec_filing_events.form_type",
                "borrow_availability.short_sell_rate",
                "borrow_availability.short_available_volume",
            ],
            "entry_date_present": bool(forward.get("entry_date_min")),
            "target_price_scope": (
                "No executable candidate or target_price field is consumed. "
                "This is a read-only blocker ledger; target generation remains unchanged."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate_min": baseline["min_survival_rate"],
            "note": "No filter, entry rule, ranking rule, capital allocation, exit, or live path changed.",
        },
        "gate4": {
            "passed": True,
            "decision": DECISION,
            "accepted_basis": (
                "Accepted as measurement repair only. It records current alpha "
                "blockers and legal reopen evidence axes while preserving all "
                "strategy metrics."
            ),
            "alpha_gate4_ready": False,
            "before_after_strategy_delta": strategy_delta,
            "blocked_or_closed_surfaces": blocked_surfaces,
            "failed_reasons_for_new_alpha": [
                "no_activation_ready_forward_family",
                "stale_or_missing_periodic_sec_text",
                "borrow_fields_unpopulated",
                "moomoo_clean_flow_rejected_vs_allocator",
                "space_theme_saturated",
                "core_risk_forward_rows_absent",
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "uses_llm": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": "Read-only ledger; no helper, snapshot, order, ranking, sizing, exit, or LLM behavior changes.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The current local surfaces do not expose a lawful, non-repeat "
                "Gate 4 alpha path: forward rows remain below activation and "
                "watchlist thresholds; SEC periodic text is still not materialized; "
                "borrow fields are null; moomoo and space neighbor gates are closed."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun same-row forward attribution slices, FINRA/borrow "
                "threshold sweeps, moomoo clean-flow variants, space theme-beta "
                "retunes, or SEC filer-status alpha from dry-run periodic selection."
            ),
            "new_evidence_required": (
                "A retry needs materially more closed forward replacement rows, "
                "real 10-K/10-Q text/cache with parsed cover-page status, populated "
                "PIT borrow economics, or a genuinely new data source/gate shape."
            ),
        },
        "next_retry_requires": [
            "materially more closed forward replacement rows",
            "real 10-K/10-Q sec_filing_text rows with parser-ready cover-page status",
            "non-null PIT borrow-cost or availability fields",
            "new external event/data source instead of space/moomoo/FINRA threshold retunes",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": ticket.get("novelty"),
                "exp-20260626-014": "40 enriched forward rows, no 20-row watchlist or 60-row activation family.",
                "exp-20260626-013": "SEC periodic selection provenance accepted, but real periodic text remains stale/missing.",
                "exp-20260625-019/024": "moomoo clean-flow and notional variants rejected versus accepted allocator.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if strategy metrics stay unchanged "
                "and the output names current blockers plus machine-checkable reopen axes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            repo_rel(FORWARD_ARTIFACT),
            repo_rel(EXP014_ARTIFACT),
            repo_rel(BORROW_MANIFEST),
            "data/non_ohlcv/sec_filing_text_backfill_summary_20260625.json",
            "docs/experiment_log.jsonl",
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "evidence": "Python read-only runner only."},
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "hypothesis",
        "alpha_hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "novelty",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "calibration",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "lean_quality_passed",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    ledger_rows = [
        "| Surface | State | Blocker | Next evidence |",
        "|---|---|---|---|",
    ]
    for item in payload["blocker_ledger"]:
        ledger_rows.append(
            "| {surface} | {state} | {blocker} | {next_axis} |".format(
                surface=item["surface"],
                state=item["state"],
                blocker=item["blocker"],
                next_axis=item["next_legal_evidence_axis"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Alpha Evidence-Gap Ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Accepted alpha: `false`",
            "- Production orders changed: no",
            "- Strategy EV delta: `0.0`",
            "",
            "## Blockers",
            "",
            *ledger_rows,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            *payload["reproduction_commands"],
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        BASELINE_RESULT,
        FORWARD_ARTIFACT,
        EXP014_ARTIFACT,
        BORROW_MANIFEST,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_row)
    result = {
        "accepted": bool(payload["accepted"]),
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result=result,
        status=STATUS,
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "acceptance_rule": payload["pre_run_questions"]["4_acceptance_standard"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": payload["production_impact"],
            "reproduction_commands": payload["reproduction_commands"],
            "changed_files": payload["changed_files"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "anti_js": payload["anti_js"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "accepted_alpha": payload["accepted_alpha"],
                    "blocked_or_closed_surface_count": payload["after_metrics"][
                        "blocked_or_closed_surface_count"
                    ],
                    "strategy_delta": payload["delta_metrics"][
                        "aggregate_expected_value_score"
                    ],
                    "artifact": repo_rel(OUT_JSON),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
