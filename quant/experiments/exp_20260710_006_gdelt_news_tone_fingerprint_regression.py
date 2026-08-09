"""exp-20260710-006: GDELT news-tone fingerprint regression coverage.

Measurement repair. The GDELT tone-shock alpha remains parked until archive
coverage is available, but future retries must be counted under the GDELT
source, not the generic ``other`` bucket. This runner records the guard
coverage and does not change strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-006"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "gdelt_news_tone_fingerprint_regression"
RUNNER = f"quant/experiments/exp_20260710_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import experiment_fingerprint as fp  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_006_{SLUG}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TEST_FILE = REPO_ROOT / "quant" / "test_experiment_fingerprint.py"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "Alpha hypothesis: GDELT daily company-news tone/volume shocks may become a "
    "replayable entry-risk or allocator signal once archive coverage is "
    "available; measurement blocker is that gdelt_news_tone must stay "
    "machine-classified outside data_source=other."
)
ALPHA_HYPOTHESIS = (
    "GDELT daily company-news tone and volume shocks may identify replayable "
    "negative event pressure or allocator-quality evidence once the parked "
    "archive coverage blocker is removed."
)
CHANGE_TYPE = "gdelt_news_tone_fingerprint_regression_measurement_repair"
TRIAL_FAMILY = "gdelt_news_tone_fingerprint_regression_coverage"
TRIAL_VARIANT_ID = "gdelt_news_tone_source_keyword_regression_v1"
SINGLE_CAUSAL_VARIABLE = "gdelt_news_tone_fingerprint_regression_coverage_v1"
MECHANISM_FAMILY = "external_news_tone_archive_measurement"
ACCEPTANCE_RULE = (
    "Accepted measurement repair if focused fingerprint examples resolve to "
    "gdelt_news_tone, adjacent news/event sources remain on their specific "
    "data_source keys, and no strategy/live behavior changes."
)

CHECKS = {
    "gdelt_doc_timeline_archive": {
        "text": "GDELT 2.0 DOC timelinetone timelinevolraw company news tone shock archive",
        "expected_source": "gdelt_news_tone",
    },
    "gdelt_slug_archive": {
        "text": "gdelt_news_tone company news tone_shock archive coverage",
        "expected_source": "gdelt_news_tone",
    },
    "news_event_exposure_control": {
        "text": "news_event_exposure observer daily pipeline",
        "expected_source": "news_event_exposure",
    },
    "entity_theme_news_control": {
        "text": "entity-theme news relation observer",
        "expected_source": "entity_theme_news",
    },
    "prediction_market_control": {
        "text": "prediction-market event odds observer",
        "expected_source": "prediction_market_event",
    },
}
TEST_LITERALS = [
    "GDELT 2.0 DOC timelinetone timelinevolraw news tone archive",
    "test_gdelt_news_tone_archive_source_without_news_overmatch",
]
CHANGED_FILES = [
    RUNNER,
    "quant/test_experiment_fingerprint.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_006_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\test_experiment_fingerprint.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
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
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(path)
    except PermissionError:
        path.write_text(text, encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checks() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, spec in CHECKS.items():
        actual = fp.infer_fingerprint(spec["text"])
        source_ok = actual["data_source"] == spec["expected_source"]
        results[name] = {
            **spec,
            "actual": actual,
            "source_ok": source_ok,
            "passed": source_ok,
        }
    test_text = TEST_FILE.read_text(encoding="utf-8")
    results["test_file_regression_literals"] = {
        "expected_literals": TEST_LITERALS,
        "missing_literals": [literal for literal in TEST_LITERALS if literal not in test_text],
    }
    results["test_file_regression_literals"]["passed"] = (
        not results["test_file_regression_literals"]["missing_literals"]
    )
    return results


def build_payload() -> dict[str, Any]:
    checks = run_checks()
    failed = [name for name, result in checks.items() if not result["passed"]]
    accepted = not failed
    decision = (
        "accepted_measurement_repair_gdelt_news_tone_fingerprint_regression"
        if accepted
        else "blocked_gdelt_news_tone_fingerprint_regression"
    )
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
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "new_evidence_type": "measurement_repair_for_new_data_source_guard",
        "new_evidence_axis": (
            "GDELT news-tone archive data_source guard regression coverage; "
            "does not retry the parked alpha or consume forward-row evidence."
        ),
        "acceptance_rule": ACCEPTANCE_RULE,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "nearby_prior_experiments": ["exp-20260709-020"],
        "checks": checks,
        "failed_checks": failed,
        "production_impact": {
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "trade_enabled": False,
        },
        "result": {
            "expected_value_score_delta": 0.0,
            "total_return_pct_delta": 0.0,
            "sharpe_daily_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "notes": "Fingerprint/test-only measurement repair; no strategy backtest delta.",
        },
        "changed_files": CHANGED_FILES,
        "verification_commands": VERIFICATION_COMMANDS,
        "post_run_reflection": (
            "GDELT remains alpha-blocked by archive coverage, not by novelty "
            "classification. Do not run a GDELT tone-shock alpha retry until "
            "the exp-20260709-020 coverage blocker is resolved."
        ),
        "next_step": (
            "Resolve GDELT archive materialization or offline DOC/GKG coverage; "
            "then rerun the parked tone-shock forward-value experiment."
        ),
    }


def build_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: GDELT news-tone fingerprint regression",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Lane: `{LANE}`",
            f"- Alpha hypothesis: {ALPHA_HYPOTHESIS}",
            f"- Measurement repair: {HYPOTHESIS}",
            f"- Failed checks: `{len(payload['failed_checks'])}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "- Production impact: no entry, exit, ranking, sizing, or order changes.",
            "",
            "## Checks",
            *[
                f"- `{name}`: {'PASS' if result['passed'] else 'FAIL'}"
                for name, result in payload["checks"].items()
            ],
            "",
            "## Next",
            payload["next_step"],
            "",
        ]
    )


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["decision"],
        "decision": payload["decision"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "baseline_result_file": payload["baseline_result_file"],
        "result": payload["result"],
        "production_impact": payload["production_impact"],
        "changed_files": CHANGED_FILES,
        "verification_commands": VERIFICATION_COMMANDS,
        "artifact": repo_rel(OUT_JSON),
        "post_run_reflection": payload["post_run_reflection"],
        "next_step": payload["next_step"],
    }


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [Path(path) for path in CHANGED_FILES]
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "decision": payload["decision"],
    }


def main() -> int:
    payload = build_payload()
    write_json(OUT_JSON, payload)
    write_text(CARD_MD, build_card(payload))
    save_experiment_log_entry(build_log(payload), allow_duplicate=False)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction={
            "success_probability": 0.95,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "test_does_not_cover_generic_news_overmatch",
                "current_mapping_missing_or_shadowed",
                "runner_record_not_reproducible",
            ],
            "confidence_reason": (
                "Current mapping exists, but quant/test_experiment_fingerprint.py "
                "had no GDELT regression before this measurement repair."
            ),
        },
        result=payload["result"],
        status=payload["decision"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "changed_variable": SINGLE_CAUSAL_VARIABLE,
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": payload["baseline_result_file"],
            "allowed_write_scope": [
                "quant/test_experiment_fingerprint.py",
                RUNNER,
                f"data/experiments/{EXPERIMENT_ID}/",
                f"experiments/logs/{EXPERIMENT_ID}.json",
                f"experiments/cards/{EXPERIMENT_ID}.md",
                f"experiments/manifests/{EXPERIMENT_ID}.json",
                f"experiments/tickets/{EXPERIMENT_ID}.json",
                "docs/experiment_registry.json",
            ],
            "acceptance_rule": ACCEPTANCE_RULE,
            "result_summary": payload["decision"],
            "changed_files": CHANGED_FILES,
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))
    print(json.dumps({"decision": payload["decision"], "artifact": repo_rel(OUT_JSON)}, indent=2))
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
