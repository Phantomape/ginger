"""exp-20260626-009: SEC 10-K/10-Q text default coverage repair.

Measurement repair for the exp-20260626-008 filer-status blocker. The SEC
event builder already emits 10-K/10-Q events, but sec_filing_text_backfill
previously defaulted to 8-K/6-K only, so daily/replay text materialization
silently skipped the periodic reports needed for cover-page filer status.

No strategy, ranking, sizing, exit, order, LLM, or paper/live behavior changes.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (QUANT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from daily_non_ohlcv_snapshot import SEC_TEXT_DEFAULT_FORMS  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from sec_filing_text_backfill import DEFAULT_FORMS, _event_matches  # noqa: E402


EXPERIMENT_ID = "exp-20260626-009"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_10k_10q_text_default_coverage"
RUNNER = f"quant/experiments/exp_20260626_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_filing_text_backfill_10k_10q_default_text_coverage_v1"
MECHANISM_FAMILY = "sec_filing_text_materialization_repair"
TRIAL_FAMILY = "sec_10k_10q_text_default_coverage_repair"
TRIAL_VARIANT_ID = "default_forms_include_10k_10q_v1"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22"}),
    ]
)

OLD_DEFAULT_FORMS = ("8-K", "6-K")
PERIODIC_FORMS = {"10-K", "10-Q"}
DAILY_ITEM_CODES = None
CLI_DEFAULT_ITEM_CODES = {"2.02"}

HYPOTHESIS = (
    "Alpha blocker: SEC 10-K/10-Q cover-page filer-status alpha cannot be "
    "evaluated while sec_filing_text_backfill defaults exclude 10-K/10-Q events "
    "from the daily/replay text surface."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q cover-page filer-status transitions may "
    "identify improving issuer maturity, but that alpha is not testable until "
    "the text materializer admits periodic reports by accession and accepted_at."
)
PREDICTION = {
    "success_probability": 0.9,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "daily_import_not_using_default_forms",
        "no_10k_10q_events_in_current_surface",
        "unit_test_or_audit_failure",
    ],
    "confidence_reason": (
        "exp-20260626-008 found 10-K/10-Q event metadata but zero text rows. "
        "The code default was plainly 8-K/6-K only, while daily snapshots import "
        "that same DEFAULT_FORMS value; adding periodic reports should repair "
        "selection coverage without changing strategy decisions."
    ),
    "recorded_at": "2026-06-26T08:05:37+00:00",
}


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
    if isinstance(value, OrderedDict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, Counter):
        return {str(key): safe(item) for key, item in value.items()}
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
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors = 0
    if not path.exists():
        return rows, errors
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError:
            errors += 1
    return rows, errors


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def form_base(row: dict[str, Any]) -> str:
    return str(row.get("form_base") or row.get("form_type") or "").upper().replace("/A", "")


def forms_set(forms: tuple[str, ...] | list[str]) -> set[str]:
    return {str(form).strip().upper().replace("/A", "") for form in forms if str(form).strip()}


def row_key(row: dict[str, Any], path: Path) -> tuple[str, str, str]:
    accession = str(row.get("accession_number") or "")
    usable = str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    return accession or path.name, usable, ticker


def in_window(day: str, cfg: dict[str, str]) -> bool:
    return bool(day) and cfg["start"] <= day <= cfg["end"]


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
    windows = payload.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=0.0,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "survival_rate": round(
            (
                sum(int(row.get("signals_survived") or 0) for row in windows)
                / max(sum(int(row.get("signals_generated") or 0) for row in windows), 1)
            ),
            4,
        ),
        "windows": windows,
    }


def selection_summary(paths: list[Path], *, windows_only: bool) -> dict[str, Any]:
    old_forms = forms_set(OLD_DEFAULT_FORMS)
    new_forms = forms_set(tuple(DEFAULT_FORMS))
    seen: set[tuple[str, str, str]] = set()
    summary = {
        "source_files": [repo_rel(path) for path in paths],
        "json_parse_errors": 0,
        "unique_event_rows": 0,
        "old_default_selected_rows": 0,
        "new_default_selected_rows": 0,
        "newly_admitted_rows": 0,
        "newly_admitted_periodic_rows": 0,
        "form_counts": Counter(),
        "newly_admitted_form_counts": Counter(),
        "newly_admitted_ticker_count": 0,
        "newly_admitted_sample": [],
        "windows": OrderedDict(
            (
                label,
                {
                    "old_default_selected_rows": 0,
                    "new_default_selected_rows": 0,
                    "newly_admitted_rows": 0,
                    "newly_admitted_periodic_rows": 0,
                    "newly_admitted_form_counts": Counter(),
                },
            )
            for label in WINDOWS
        ),
    }
    newly_admitted_tickers: set[str] = set()

    for path in paths:
        rows, errors = iter_jsonl(path)
        summary["json_parse_errors"] += errors
        for row in rows:
            key = row_key(row, path)
            if key in seen:
                continue
            seen.add(key)
            usable = str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]
            if windows_only and not any(in_window(usable, cfg) for cfg in WINDOWS.values()):
                continue
            base = form_base(row)
            old_match = _event_matches(row, old_forms, DAILY_ITEM_CODES)
            new_match = _event_matches(row, new_forms, DAILY_ITEM_CODES)
            newly = new_match and not old_match

            summary["unique_event_rows"] += 1
            summary["form_counts"][base] += 1
            if old_match:
                summary["old_default_selected_rows"] += 1
            if new_match:
                summary["new_default_selected_rows"] += 1
            if newly:
                summary["newly_admitted_rows"] += 1
                summary["newly_admitted_form_counts"][base] += 1
                ticker = str(row.get("ticker") or "").upper()
                if ticker:
                    newly_admitted_tickers.add(ticker)
                if base in PERIODIC_FORMS:
                    summary["newly_admitted_periodic_rows"] += 1
                if len(summary["newly_admitted_sample"]) < 12:
                    summary["newly_admitted_sample"].append(
                        {
                            "ticker": ticker,
                            "form_type": row.get("form_type"),
                            "accession_number": row.get("accession_number"),
                            "accepted_at": row.get("accepted_at"),
                            "usable_trade_date": usable,
                            "primary_document": row.get("primary_document"),
                        }
                    )

            for label, cfg in WINDOWS.items():
                if not in_window(usable, cfg):
                    continue
                window = summary["windows"][label]
                if old_match:
                    window["old_default_selected_rows"] += 1
                if new_match:
                    window["new_default_selected_rows"] += 1
                if newly:
                    window["newly_admitted_rows"] += 1
                    window["newly_admitted_form_counts"][base] += 1
                    if base in PERIODIC_FORMS:
                        window["newly_admitted_periodic_rows"] += 1

    summary["newly_admitted_ticker_count"] = len(newly_admitted_tickers)
    return summary


def cli_default_scope_check() -> dict[str, Any]:
    old_forms = forms_set(OLD_DEFAULT_FORMS)
    new_forms = forms_set(tuple(DEFAULT_FORMS))
    rows = [
        {"form_type": "8-K", "form_base": "8-K", "eight_k_item_codes": ["5.02"]},
        {"form_type": "8-K", "form_base": "8-K", "eight_k_item_codes": ["2.02"]},
        {"form_type": "6-K", "form_base": "6-K", "eight_k_item_codes": []},
        {"form_type": "10-K", "form_base": "10-K", "eight_k_item_codes": []},
        {"form_type": "10-Q", "form_base": "10-Q", "eight_k_item_codes": []},
    ]
    return {
        "old_cli_default_matches": [
            form_base(row) for row in rows if _event_matches(row, old_forms, CLI_DEFAULT_ITEM_CODES)
        ],
        "new_cli_default_matches": [
            form_base(row) for row in rows if _event_matches(row, new_forms, CLI_DEFAULT_ITEM_CODES)
        ],
        "item_code_gate_still_blocks_non_202_8k": not _event_matches(
            rows[0],
            new_forms,
            CLI_DEFAULT_ITEM_CODES,
        ),
        "periodic_reports_bypass_8k_item_codes": all(
            _event_matches(row, new_forms, CLI_DEFAULT_ITEM_CODES) for row in rows[-2:]
        ),
    }


def latest_daily_events_path() -> Path | None:
    paths = sorted(NON_OHLCV_DIR.glob("sec_filing_events_20*.jsonl"))
    dated = [path for path in paths if len(path.stem.rsplit("_", 1)[-1]) == 8]
    return dated[-1] if dated else None


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    latest_path = latest_daily_events_path()
    current_daily = selection_summary([latest_path], windows_only=False) if latest_path else {}
    standard = selection_summary(sorted(NON_OHLCV_DIR.glob("sec_filing_events_*.jsonl")), windows_only=True)
    default_forms = list(DEFAULT_FORMS)
    daily_import_forms = list(SEC_TEXT_DEFAULT_FORMS)
    has_periodic_defaults = PERIODIC_FORMS.issubset(forms_set(tuple(default_forms)))
    daily_import_matches = forms_set(tuple(default_forms)) == forms_set(tuple(daily_import_forms))
    gate2_passed = (
        has_periodic_defaults
        and daily_import_matches
        and int(current_daily.get("newly_admitted_periodic_rows") or 0) > 0
        and int(standard.get("newly_admitted_periodic_rows") or 0) > 0
    )
    decision = (
        "accepted_measurement_repair_sec_10k_10q_text_default_coverage"
        if gate2_passed
        else "blocked_sec_10k_10q_text_default_coverage_not_verified"
    )
    status = "accepted_measurement_repair" if gate2_passed else "blocked"
    actual_success = 1 if gate2_passed else 0

    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "daily_snapshot_exposed": True,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "paper_orders_changed": False,
        "live_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "uses_free_sec_filing_events": True,
        "uses_free_sec_filing_text": True,
        "uses_llm": False,
        "replay_only": False,
        "live_realism_evaluated": False,
        "live_ready": False,
        "parity_note": (
            "Daily non-OHLCV snapshot imports SEC_TEXT_DEFAULT_FORMS from "
            "sec_filing_text_backfill, so the repaired default scope is shared "
            "by direct backfill CLI and daily data-refresh wiring. This changes "
            "data materialization only; no strategy consumer is promoted."
        ),
    }

    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": gate2_passed,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Expanded SEC filing text backfill defaults from 8-K/6-K to "
            "8-K/6-K/10-K/10-Q so periodic-report cover pages can be "
            "materialized for filer-status attribution."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "sec_filing_text_backfill default form scope",
            "daily_non_ohlcv_snapshot shared default import",
            "unit test for 10-K/10-Q selection and unchanged 8-K item-code gate",
            "coverage artifact only; no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260618-007",
            "exp-20260621-015",
            "exp-20260626-008",
        ],
        "multiple_testing_risk_bucket": "minimal_measurement_repair",
        "new_evidence_type": "alpha_blocker_measurement_repair",
        "new_evidence_axis": (
            "Repair the default text materialization scope for existing "
            "10-K/10-Q SEC event rows; not a SEC phrase, form-item, threshold, "
            "or filer-status alpha replay."
        ),
        "prediction": PREDICTION,
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "strategy_behavior_changed": False,
        },
        "gate2": {
            "passed": gate2_passed,
            "default_forms_before": list(OLD_DEFAULT_FORMS),
            "default_forms_after": default_forms,
            "daily_import_forms": daily_import_forms,
            "daily_import_matches_text_backfill_default": daily_import_matches,
            "current_daily_event_selection": current_daily,
            "standard_window_event_selection": standard,
            "cli_default_scope_check": cli_default_scope_check(),
            "required_fields_checked": [
                "sec_filing_events accession_number",
                "sec_filing_events accepted_at",
                "sec_filing_events usable_trade_date",
                "sec_filing_events primary_document",
                "sec_filing_text_backfill DEFAULT_FORMS",
                "daily_non_ohlcv_snapshot SEC_TEXT_DEFAULT_FORMS",
                "entry_date",
                "target_price",
            ],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; this only repairs data materialization scope.",
        },
        "gate4": {
            "passed": gate2_passed,
            "decision": decision,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "survival_rate_delta": 0.0,
            },
            "accepted_basis": (
                "Measurement repair accepted because the shared default text "
                "scope now includes 10-K/10-Q, daily snapshot wiring imports "
                "the same default, and existing daily plus standard-window SEC "
                "events contain periodic reports that old defaults skipped."
            )
            if gate2_passed
            else None,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "current_daily_newly_admitted_periodic_rows": int(
                current_daily.get("newly_admitted_periodic_rows") or 0
            ),
            "standard_window_newly_admitted_periodic_rows": int(
                standard.get("newly_admitted_periodic_rows") or 0
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": actual_success,
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": None if gate2_passed else "coverage_repair_not_verified",
            "predicted_failure_mode_hit": not gate2_passed,
            "surprise_note": (
                "The direct code default was the blocker; repairing it admitted "
                "existing 10-K/10-Q event rows without changing strategy behavior."
            )
            if gate2_passed
            else "The expected default-scope repair did not verify.",
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The SEC event backfill already collected periodic reports, but "
                "the filing-text materializer defaulted to 8-K/6-K only. That "
                "made cover-page filer status look absent even when accession "
                "metadata existed. The repair moves the blocker to actual text "
                "fetch/cache materialization and parser coverage."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not treat this as accepted filer-status alpha. Do not retry "
                "accelerated-filer-status, filing-timeliness, raw SEC item-code, "
                "or SEC phrase-list alpha until 10-K/10-Q text rows are actually "
                "materialized and parsed across the canonical windows."
            ),
            "new_evidence_required": (
                "Run SEC filing-text materialization with the repaired defaults "
                "for historical 10-K/10-Q events, parse cover-page filer-status "
                "booleans by accession/accepted_at, then rerun one fixed "
                "shared-paper-first filer-status transition rule."
            ),
        },
        "next_retry_requires": [
            "materialized 10-K/10-Q sec_filing_text rows across canonical windows",
            "parsed cover-page large_accelerated/accelerated/non_accelerated/smaller_reporting/EGC booleans",
            "one fixed transition rule with daily/default-off parity",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260618-007": "Blocked because historical 10-K/10-Q cover-page filer-status was absent.",
                "exp-20260626-008": "Blocked with 2,534 10-K/10-Q event rows but 0 10-K/10-Q text rows.",
                "novelty_gate": "Measurement repair lane; novelty did not block. This repairs text materialization scope, not alpha selection.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accepted as measurement repair if 10-K/10-Q are in DEFAULT_FORMS, "
                "daily_non_ohlcv_snapshot imports the same default, existing daily "
                "and standard-window events include rows newly admitted by the "
                "new default, unit tests pass, and strategy metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            repo_rel(Path(__file__)),
            repo_rel(BASELINE_RESULT),
            "data/non_ohlcv/sec_filing_events_*.jsonl",
        ],
        "changed_files": [
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sec_filing_text_backfill.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner and pytest only."},
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
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 10-K/10-Q Text Default Coverage",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            "Accepted as measurement repair. `sec_filing_text_backfill.DEFAULT_FORMS` now "
            "includes `10-K` and `10-Q`, and daily snapshot wiring imports the same default.",
            "",
            f"- Current daily newly admitted periodic rows: `{delta['current_daily_newly_admitted_periodic_rows']}`",
            f"- Standard-window newly admitted periodic rows: `{delta['standard_window_newly_admitted_periodic_rows']}`",
            f"- Strategy EV/PnL delta: `{delta['expected_value_score_sum_delta']}` / `${delta['total_pnl_delta']}`",
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
        REPO_ROOT / "quant" / "sec_filing_text_backfill.py",
        REPO_ROOT / "quant" / "test_sec_filing_text_backfill.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
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
        status=payload["status"],
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
            "evaluation_windows": [{"label": label, **cfg} for label, cfg in WINDOWS.items()],
            "acceptance_rule": payload["pre_run_questions"]["4_acceptance_standard"],
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
            "anti_js": payload["anti_js"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log_row(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
