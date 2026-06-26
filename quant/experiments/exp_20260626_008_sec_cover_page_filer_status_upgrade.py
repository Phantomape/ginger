"""exp-20260626-008: SEC cover-page filer-status upgrade coverage.

This tests one alpha-enabling hypothesis: 10-K/10-Q cover-page filer-status
upgrades could be a PIT structured data edge for candidate selection. The run
stops at Gate 2 if local replay text does not contain 10-K/10-Q cover pages.

No strategy, adapter, ranking, sizing, exit, order, watchlist, LLM, or paper
ledger behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-008"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "sec_cover_page_filer_status_upgrade"
RUNNER = f"quant/experiments/exp_20260626_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_cover_page_filer_status_upgrade_candidate_source_v1"
TRIAL_FAMILY = "sec_cover_page_filer_status_upgrade_candidate_pool"
TRIAL_VARIANT_ID = "cover_page_filer_status_upgrade_text_coverage_v1"
MECHANISM_FAMILY = "production_visible_sec_cover_page_filer_status_candidate_pool"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22"}),
    ]
)

HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q cover-page filer-status upgrades from "
    "smaller/non-accelerated/EGC toward accelerated or large-accelerated status "
    "may identify improving institutional eligibility whose next-open 10-day "
    "default-off paper continuation beats accepted comparators when paired with "
    "liquid SPY-relative confirmation."
)
NEW_EVIDENCE_AXIS = (
    "Machine-checkable new PIT field: parsed 10-K/10-Q cover-page filer-status "
    "upgrade keyed by accession/accepted_at, distinct from filing earliness, "
    "raw SEC item codes, 13D/13G holder metadata, Companyfacts ratios, and SEC "
    "text phrase lists."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260617-020",
    "exp-20260617-022",
    "exp-20260618-016",
    "exp-20260625-005",
    "exp-20260626-007",
]
PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "thin_upgrade_sample",
        "old_thin_text_coverage_gap",
        "filing_status_not_incremental",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Playbook explicitly lists historical 10-K/10-Q cover-page filer status "
        "keyed by accession and accelerated-filer-status change as a remaining "
        "structured-data edge after filing-timeliness and raw SEC item-code "
        "failures. Confidence is low because SEC text/event families are "
        "saturated and upgrades may be sparse, but the field is "
        "machine-checkable and not a threshold sweep."
    ),
    "recorded_at": "2026-06-26T07:04:46+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "production_watchlist_changed": False,
    "uses_free_sec_filing_events": True,
    "uses_free_sec_filing_text": True,
    "uses_llm": False,
    "replay_only": False,
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "Coverage audit only. A future positive alpha requires a shared "
        "historical/daily parser for the same cover-page status fields, a "
        "default-off paper helper, parity test, and full Gate 1-4 replay."
    ),
}

STATUS_PATTERN = re.compile(
    r"(large accelerated filer|accelerated filer|non-accelerated filer|"
    r"smaller reporting company|emerging growth company)\s+(true|false|x|"
    r"\u2612|\u2611|\u2610|\u00fe|\u00a8)",
    re.IGNORECASE,
)


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
    if isinstance(value, (list, tuple)):
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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def in_window(day: str, cfg: dict[str, str]) -> bool:
    return cfg["start"] <= day <= cfg["end"]


def form_base(row: dict[str, Any]) -> str:
    return str(row.get("form_base") or row.get("form_type") or "").upper().split("/")[0]


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


def extract_cover_status(text: str) -> dict[str, bool | None]:
    statuses: dict[str, bool | None] = {
        "large_accelerated_filer": None,
        "accelerated_filer": None,
        "non_accelerated_filer": None,
        "smaller_reporting_company": None,
        "emerging_growth_company": None,
    }
    if not text:
        return statuses
    for match in STATUS_PATTERN.finditer(text[:12000]):
        key = match.group(1).lower().replace("-", "_").replace(" ", "_")
        raw = match.group(2).lower()
        checked = raw in {"true", "x", "\u2612", "\u2611", "\u00fe"}
        if raw in {"false", "\u2610", "\u00a8"}:
            checked = False
        statuses[key] = checked
    return statuses


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


def coverage_audit() -> dict[str, Any]:
    event_counts: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    text_counts: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    status_rows: list[dict[str, Any]] = []

    for label, cfg in WINDOWS.items():
        event_counts[label] = {
            "10k_10q_event_rows": 0,
            "forms": Counter(),
            "tickers": set(),
            "parse_errors": 0,
        }
        text_counts[label] = {
            "10k_10q_text_rows": 0,
            "forms": Counter(),
            "tickers": set(),
            "parse_errors": 0,
            "parseable_cover_status_rows": 0,
        }

    for path in sorted(NON_OHLCV_DIR.glob("sec_filing_events_*.jsonl")):
        rows, errors = iter_jsonl(path)
        for label, cfg in WINDOWS.items():
            event_counts[label]["parse_errors"] += errors
        for row in rows:
            usable = str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]
            base = form_base(row)
            if base not in {"10-K", "10-Q"}:
                continue
            for label, cfg in WINDOWS.items():
                if in_window(usable, cfg):
                    event_counts[label]["10k_10q_event_rows"] += 1
                    event_counts[label]["forms"][base] += 1
                    event_counts[label]["tickers"].add(str(row.get("ticker") or "").upper())

    for path in sorted(NON_OHLCV_DIR.glob("sec_filing_text_*.jsonl")):
        rows, errors = iter_jsonl(path)
        for label, cfg in WINDOWS.items():
            text_counts[label]["parse_errors"] += errors
        for row in rows:
            usable = str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]
            base = form_base(row)
            if base not in {"10-K", "10-Q"}:
                continue
            for label, cfg in WINDOWS.items():
                if not in_window(usable, cfg):
                    continue
                text_counts[label]["10k_10q_text_rows"] += 1
                text_counts[label]["forms"][base] += 1
                text_counts[label]["tickers"].add(str(row.get("ticker") or "").upper())
                statuses = extract_cover_status(str(row.get("combined_text") or ""))
                if any(value is not None for value in statuses.values()):
                    text_counts[label]["parseable_cover_status_rows"] += 1
                    status_rows.append(
                        {
                            "window": label,
                            "ticker": str(row.get("ticker") or "").upper(),
                            "form_type": row.get("form_type"),
                            "accession_number": row.get("accession_number"),
                            "accepted_at": row.get("accepted_at"),
                            "usable_trade_date": usable,
                            "statuses": statuses,
                        }
                    )

    def freeze(section: "OrderedDict[str, dict[str, Any]]") -> OrderedDict[str, dict[str, Any]]:
        frozen: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        for label, row in section.items():
            frozen[label] = {
                **{key: value for key, value in row.items() if key not in {"forms", "tickers"}},
                "forms": dict(row["forms"]),
                "ticker_count": len(row["tickers"]),
            }
        return frozen

    return {
        "event_coverage": freeze(event_counts),
        "text_coverage": freeze(text_counts),
        "parseable_status_rows_sample": status_rows[:25],
        "total_10k_10q_event_rows": sum(
            row["10k_10q_event_rows"] for row in event_counts.values()
        ),
        "total_10k_10q_text_rows": sum(row["10k_10q_text_rows"] for row in text_counts.values()),
        "total_parseable_cover_status_rows": sum(
            row["parseable_cover_status_rows"] for row in text_counts.values()
        ),
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    coverage = coverage_audit()
    gate2_passed = coverage["total_parseable_cover_status_rows"] > 0
    status = "blocked"
    decision = (
        "blocked_sec_cover_page_filer_status_text_surface_missing"
        if not gate2_passed
        else "blocked_sec_cover_page_filer_status_upgrade_replay_not_implemented"
    )
    failed_reasons = []
    if coverage["total_10k_10q_event_rows"] <= 0:
        failed_reasons.append("no_10k_10q_event_rows")
    if coverage["total_10k_10q_text_rows"] <= 0:
        failed_reasons.append("no_10k_10q_text_rows_in_replay_text_surface")
    if coverage["total_parseable_cover_status_rows"] <= 0:
        failed_reasons.append("no_parseable_cover_page_filer_status_rows")

    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": "gate2_field_availability_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "SEC filing event coverage audit",
            "SEC filing text cover-page parser availability audit",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate_sec_structured_data_saturation",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "new_evidence_type": "sec_cover_page_filer_status_field_availability",
        "prediction": PREDICTION,
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": gate2_passed,
            "required_fields_checked": [
                "sec_filing_events accepted_at",
                "sec_filing_events usable_trade_date",
                "sec_filing_text combined_text for 10-K/10-Q",
                "cover-page filer status fields",
                "entry_date",
                "target_price",
            ],
            "coverage": coverage,
            "blocking_reason": "; ".join(failed_reasons),
        },
        "gate3": {
            "passed": False,
            "filter_added": False,
            "signals_generated_proxy": coverage["total_10k_10q_event_rows"],
            "signals_survived_proxy": coverage["total_parseable_cover_status_rows"],
            "survival_rate_proxy": 0.0,
            "note": "No executable filter was added; the candidate field is unavailable.",
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "parseable_cover_status_rows": coverage["total_parseable_cover_status_rows"],
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 0,
            "brier_score": round(PREDICTION["success_probability"] ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": "field_availability_blocked",
            "predicted_failure_mode_hit": True,
        },
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": "; ".join(failed_reasons),
        "post_run_reflection": {
            "why_result_happened": (
                "The event archive contains 10-K/10-Q filing metadata, but the "
                "local SEC filing text replay surface did not provide parseable "
                "10-K/10-Q cover-page rows for the canonical windows, so the "
                "status-upgrade field cannot be tested without creating ghost "
                "inputs."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry accelerated-filer-status alpha, filing-timeliness, "
                "raw form/item metadata, or SEC phrase-list variants until "
                "10-K/10-Q cover-page text is materialized with accession and "
                "accepted_at provenance."
            ),
            "new_evidence_required": (
                "Materialize historical 10-K/10-Q cover-page XBRL/text rows "
                "keyed by accession_number, accepted_at, usable_trade_date, "
                "ticker, and parsed filer-status booleans; then rerun one fixed "
                "upgrade/downgrade candidate rule through shared-paper-first."
            ),
        },
        "next_retry_requires": [
            "historical 10-K/10-Q cover-page text or XBRL rows",
            "parsed large_accelerated/accelerated/non_accelerated/smaller_reporting/EGC booleans",
            "accession_number and accepted_at keyed PIT provenance",
            "one fixed status-upgrade rule before any threshold or universe sweep",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": NEW_EVIDENCE_AXIS,
                "exp-20260617-020": "Rejected 10-K filing-timeliness; not this field.",
                "exp-20260617-022": "Rejected 10-Q filing-timeliness; not this field.",
                "exp-20260618-016": "Built 13D/13G holder/stake surface; different source.",
                "exp-20260626-007": "Rejected Companyfacts product/service mix; different source.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Gate 2 must find parseable 10-K/10-Q cover-page status rows. "
                "Only then may a candidate replay attempt Gate 3/4 under "
                "docs/backtesting.md with accepted comparator checks."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            repo_rel(Path(__file__)),
            repo_rel(BASELINE_RESULT),
            "data/non_ohlcv/sec_filing_events_*.jsonl",
            "data/non_ohlcv/sec_filing_text_*.jsonl",
        ],
        "changed_files": [
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
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_summary": "Audited whether SEC 10-K/10-Q cover-page filer-status upgrade can be replayed; blocked because replay text lacks parseable 10-K/10-Q cover pages.",
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    coverage = payload["gate2"]["coverage"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC Cover-Page Filer Status Upgrade",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            "Gate 2 blocked the alpha replay. The filing-event archive has "
            f"`{coverage['total_10k_10q_event_rows']}` 10-K/10-Q event rows "
            "across the canonical windows, but the replay text surface has "
            f"`{coverage['total_10k_10q_text_rows']}` 10-K/10-Q text rows and "
            f"`{coverage['total_parseable_cover_status_rows']}` parseable cover-page status rows.",
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
        "accepted": False,
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
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
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
            "production_impact": PRODUCTION_IMPACT,
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
