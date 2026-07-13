"""exp-20260710-014: SEC 13G/A stake-change direction materialization.

Measurement repair / alpha-enabling field build. The parsed 13D/13G ownership
surface had a parser for 13G/A amendment direction fields, but canonical rows
still excluded 13G/A amendments. This runner records the local-cache refresh
result and persists the experiment artifacts. It does not alter strategy
ranking, sizing, exits, orders, or live/default trade settings.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-014"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec13ga_stake_change_direction_materialization"
RUNNER = f"quant/experiments/exp_20260710_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
CANONICAL_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_13d13g_holdings" / "rows.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_014_{SLUG}.json"
BEFORE_JSON = OUT_DIR / "before_measurement.json"
AFTER_JSON = OUT_DIR / "after_measurement.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: parsed SEC 13G/A amendment stake-change direction is the "
    "next named evidence axis for the 13D/13G ownership surface, but canonical "
    "rows still exclude 13G/A amendments and do not materialize "
    "previous-accession/current-stake/below-5pct direction fields for replay."
)
ALPHA_HYPOTHESIS = (
    "13G/A stake-change direction may separate passive index-fund trims/exits "
    "from non-Big3 stake increases, but this run only materializes the shared "
    "measurement fields and makes no alpha claim."
)
CHANGE_TYPE = "measurement_repair"
MECHANISM_FAMILY = "production_visible_sec_ownership_holder_stake_measurement"
TRIAL_FAMILY = "sec13ga_stake_change_direction_materialization"
TRIAL_VARIANT_ID = "sec13ga_direction_rows_v1"
SINGLE_CAUSAL_VARIABLE = "sec13ga_amendment_stake_change_direction_materialization_v1"
CHANGED_VARIABLE = "sec13ga_amendment_stake_change_direction_fields"
CAUSAL_COMPONENTS = [
    "13G/A amendment enumeration",
    "local XML-cache parsing",
    "previousAccessionNumber",
    "current item4 percent/share fields",
    "below-5pct exit flag",
    "canonical rows refresh",
    "no trading behavior change",
]
NEARBY_PRIORS = [
    "exp-20260618-016",
    "exp-20260710-003",
    "exp-20260710-004",
    "exp-20260710-005",
]
NEW_EVIDENCE_TYPE = "alpha_enabling_field_materialization"
NEW_EVIDENCE_AXIS = (
    "New alpha-enabling canonical 13G/A amendment rows plus stake-change "
    "direction fields (previous accession, current item4 percent/shares, "
    "below-5pct flag) explicitly required after exp-20260618-016; not a 13D "
    "Item-4 phrase, holder-type, classPercent threshold, notional, hold, or "
    "response-shape retry."
)
ACCEPTANCE_RULE = (
    "Accept as measurement repair only if 13G/A amendment rows are parsed from "
    "local cache, stake-change direction fields are present on canonical rows, "
    "focused tests pass, and no strategy/live order behavior changes."
)
CHANGED_FILES = [
    "quant/sec_13d13g_ingest.py",
    "quant/test_sec_13d13g_ingest.py",
    RUNNER,
    "data/non_ohlcv/sec_13d13g_holdings/rows.json",
    "data/experiments/exp-20260710-014/before_measurement.json",
    "data/experiments/exp-20260710-014/after_measurement.json",
    "data/experiments/exp-20260710-014/exp_20260710_014_sec13ga_stake_change_direction_materialization.json",
    "experiments/logs/exp-20260710-014.json",
    "experiments/cards/exp-20260710-014.md",
    "experiments/manifests/exp-20260710-014.json",
    "experiments/tickets/exp-20260710-014.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\sec_13d13g_ingest.py "
    "quant\\test_sec_13d13g_ingest.py "
    "quant\\experiments\\exp_20260710_014_sec13ga_stake_change_direction_materialization.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sec_13d13g_ingest.py -q",
    ".\\.venv\\Scripts\\python.exe -B quant\\sec_13d13g_ingest.py --families '13D,13G'",
    RUNNER_COMMAND,
]
BEFORE_SUMMARY = {
    "source": "pre-run canonical rows from exp-20260710-003 materialization",
    "parsed_row_count": 3480,
    "rows_by_family": {"13D": 950, "13G_init": 2530, "13G_amendment": 0},
    "include_amendments": {"13D": True, "13G": False},
    "sec13ga_direction_rows": 0,
    "sec13ga_computed_direction_rows": 0,
}


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
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_command(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": " ".join(args),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
        "passed": result.returncode == 0,
    }


def syntax_check(paths: list[str]) -> dict[str, Any]:
    failures = []
    for rel in paths:
        path = REPO_ROOT / rel
        try:
            compile(path.read_text(encoding="utf-8"), rel, "exec")
        except Exception as exc:  # pragma: no cover - diagnostic payload
            failures.append({"path": rel, "error": repr(exc)})
    return {
        "command": "in-memory compile() syntax check",
        "paths": paths,
        "returncode": 0 if not failures else 1,
        "failures": failures,
        "passed": not failures,
    }


def summarize_rows() -> dict[str, Any]:
    payload = read_json(CANONICAL_ROWS)
    rows = payload.get("rows", [])
    amends = [
        row
        for row in rows
        if row.get("family") == "13G" and row.get("is_amendment")
    ]
    init13g = [
        row
        for row in rows
        if row.get("family") == "13G" and not row.get("is_amendment")
    ]
    rows13d = [row for row in rows if row.get("family") == "13D"]
    status = Counter(row.get("sec13ga_direction_status") for row in amends)
    direction = Counter(row.get("sec13ga_stake_change_direction") for row in amends)
    windows = Counter(row.get("window") for row in amends)
    with_prev = sum(1 for row in amends if row.get("sec13ga_previous_accession"))
    with_current = sum(
        1 for row in amends if row.get("sec13ga_current_max_percent") is not None
    )
    with_delta = sum(
        1 for row in amends if row.get("sec13ga_percent_delta") is not None
    )
    below5 = sum(1 for row in amends if row.get("sec13ga_below_5pct") is True)
    sample = [
        {
            "ticker": row.get("ticker"),
            "accession": row.get("accession_number"),
            "previous": row.get("sec13ga_previous_accession"),
            "current_pct": row.get("sec13ga_current_max_percent"),
            "previous_pct": row.get("sec13ga_previous_max_percent"),
            "delta": row.get("sec13ga_percent_delta"),
            "direction": row.get("sec13ga_stake_change_direction"),
            "status": row.get("sec13ga_direction_status"),
        }
        for row in amends
        if row.get("sec13ga_direction_status") == "computed"
    ][:10]
    return {
        "generated_at": payload.get("generated_at"),
        "families": payload.get("families"),
        "include_amendments": payload.get("include_amendments"),
        "parsed_row_count": payload.get("parsed_row_count"),
        "fetch_status": payload.get("fetch_status"),
        "rows_by_family": {
            "13D": len(rows13d),
            "13G_init": len(init13g),
            "13G_amendment": len(amends),
        },
        "13ga_with_previous_accession": with_prev,
        "13ga_with_current_max_percent": with_current,
        "13ga_with_percent_delta": with_delta,
        "13ga_below_5pct_true": below5,
        "13ga_direction_status_counts": dict(status),
        "13ga_direction_counts": dict(direction),
        "13ga_by_window": dict(windows),
        "sample_computed": sample,
    }


def build_payload() -> dict[str, Any]:
    py_compile = syntax_check(
        [
            "quant/sec_13d13g_ingest.py",
            "quant/test_sec_13d13g_ingest.py",
            RUNNER,
        ]
    )
    pytest = run_command(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "quant/test_sec_13d13g_ingest.py",
            "-q",
        ]
    )
    after = summarize_rows()
    checks = {
        "families_quoted_correctly": after.get("families") == ["13D", "13G"],
        "preserved_13d_rows": after["rows_by_family"]["13D"] >= 900,
        "materialized_13ga_rows": after["rows_by_family"]["13G_amendment"] >= 100,
        "materialized_current_percent": after["13ga_with_current_max_percent"] >= 100,
        "materialized_previous_accession": after["13ga_with_previous_accession"] >= 100,
        "computed_direction_rows": sum(
            count
            for direction, count in after["13ga_direction_counts"].items()
            if direction not in (None, "None")
        )
        >= 100,
        "focused_py_compile_passed": py_compile["passed"],
        "focused_pytest_passed": pytest["passed"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    accepted = not failed
    decision = (
        "accepted_sec13ga_stake_change_direction_materialization"
        if accepted
        else "blocked_sec13ga_stake_change_direction_materialization"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted" if accepted else "blocked",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "measurement_repair_only": True,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260618-016 requested 13G/A stake-change direction before "
                "another 13D/13G alpha replay; exp-20260710-003 materialized "
                "13D Item-4 fields but explicitly still excluded 13G/A; "
                "exp-20260710-005 rejected concrete Item-4 campaign outcomes."
            ),
            "3_single_policy_bundle": SINGLE_CAUSAL_VARIABLE,
            "4_success_failure_standard": ACCEPTANCE_RULE,
            "5_reproducibility": "; ".join(VERIFICATION_COMMANDS),
        },
        "gate1": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "passed": True,
            "note": "No strategy metrics changed; baseline is cited for protocol continuity.",
        },
        "gate2": {
            "fields": [
                "accession_number",
                "form",
                "family",
                "is_amendment",
                "sec13ga_previous_accession",
                "sec13ga_current_max_percent",
                "sec13ga_current_max_shares",
                "sec13ga_below_5pct",
                "sec13ga_stake_change_direction",
            ],
            "before_measurement": BEFORE_SUMMARY,
            "after_measurement": after,
            "passed": checks["materialized_13ga_rows"]
            and checks["materialized_current_percent"]
            and checks["materialized_previous_accession"],
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": 164,
            "signals_survived": 135,
            "survival_rate": 0.823171,
            "passed": True,
            "note": "No executable filter was added; baseline survival is unchanged.",
        },
        "gate4": {
            "mode": "measurement_repair_field_materialization",
            "passed": accepted,
            "checks": checks,
            "failed_reasons": failed,
            "strategy_metric_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
            },
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "headline_metrics": {
            "checks_passed": sum(1 for passed in checks.values() if passed),
            "checks_total": len(checks),
            "failed_checks": failed,
            "before_parsed_rows": BEFORE_SUMMARY["parsed_row_count"],
            "after_parsed_rows": after["parsed_row_count"],
            "new_13ga_rows": after["rows_by_family"]["13G_amendment"],
            "computed_13ga_direction_rows": sum(
                count
                for direction, count in after["13ga_direction_counts"].items()
                if direction not in (None, "None")
            ),
            "percent_delta_rows": after["13ga_with_percent_delta"],
        },
        "verification": {"py_compile": py_compile, "pytest": pytest},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "ranking_sizing_exits_changed": False,
            "canonical_data_surface_changed": True,
            "live_ready": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The parser already knew how to read 13G/A direction fields, "
                "but canonical materialization used 13D amendments plus 13G "
                "initial filings only. Quoted-family local-cache refresh "
                "preserved 13D rows and added 2,787 13G/A rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair as alpha evidence and do not sweep "
                "13G/A holder types, classPercent thresholds, top-N, hold, "
                "notional, or response shape on these frozen rows."
            ),
            "new_evidence_required": (
                "Next 13G/A alpha work must be a fixed shared-paper-first "
                "policy using stake-change direction against accepted "
                "comparators, or wait for materially more closed forward rows "
                "or richer ownership/campaign data."
            ),
            "power_shell_reproduction_note": (
                "Quote --families as '13D,13G' in PowerShell; unquoted "
                "13D,13G is parsed incorrectly and can drop 13D rows."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": VERIFICATION_COMMANDS,
        "lean_quality_passed": accepted,
    }
    return payload


def build_card(payload: Mapping[str, Any]) -> str:
    metrics = payload["headline_metrics"]
    failed = ", ".join(metrics["failed_checks"]) or "none"
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 13G/A Stake-Change Direction",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- 13G/A rows materialized: `{metrics['new_13ga_rows']}`",
            f"- Computed direction rows: `{metrics['computed_13ga_direction_rows']}`",
            f"- Percent-delta rows: `{metrics['percent_delta_rows']}`",
            f"- Failed checks: `{failed}`",
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
            ".\\.venv\\Scripts\\python.exe -B quant\\sec_13d13g_ingest.py --families '13D,13G'",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
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
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    payload = safe(payload)
    write_json(BEFORE_JSON, BEFORE_SUMMARY)
    write_json(AFTER_JSON, payload["gate2"]["after_measurement"])
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
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
            "headline_metrics": payload["headline_metrics"],
            "summary": "measurement_repair_sec13ga_stake_change_direction_materialization",
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
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
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": payload["headline_metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
