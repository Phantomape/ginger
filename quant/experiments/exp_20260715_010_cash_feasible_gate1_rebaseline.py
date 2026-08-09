"""Publish the execution-date-cash-feasible canonical Gate-1 baseline.

exp-20260715-008 accepted the cash-ledger measurement repair behind an
explicit flag and named this default flip/re-baseline as its required next
step.  This runner changes no admission semantics.  It reuses the exact
exp-20260712-015 frozen behavior inputs, verifies two default-on replays,
checks them against the exp-20260715-008 enforced reference, and proves that
an explicit False override still reproduces the archived unenforced anchor.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backtester import DEFAULT_CONFIG  # noqa: E402

import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402
import exp_20260715_008_cash_constrained_core_admission as cash_repair  # noqa: E402


EXPERIMENT_ID = "exp-20260715-010"
PROTOCOL_ID = "post_mtm_cash_feasible_gate1_frozen_inputs_v1"
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
FROZEN_INPUTS = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260712-015"
    / "frozen_behavior_inputs.json"
)
PRIOR_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
EXPECTED_ENFORCED = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260715-008"
    / "exp_20260715_008_cash_constrained_core_admission.json"
)
SOURCE_IDENTITY = EXP_DIR / "source_identity.json"
SOURCE_BUNDLE = EXP_DIR / "source_bundle.zip"
BEFORE_MEASUREMENT = EXP_DIR / "before_measurement.json"
AFTER_MEASUREMENT = EXP_DIR / "after_measurement.json"
REPLAY_IDENTITY = EXP_DIR / "double_replay_identity.json"
BASELINE_DIR = ROOT / "data" / "backtests" / "cash_feasible_20260715"
BASELINE_SUMMARY = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

HEADLINE_MAP = {
    "expected_value_score": "expected_value_score",
    "total_pnl": "total_pnl",
    "sharpe_daily": "sharpe_daily",
    "max_drawdown_pct": "max_drawdown_pct",
    "win_rate": "win_rate",
    "signals_generated": "signals_generated",
    "signals_survived": "signals_survived",
    "survival_rate": "survival_rate",
    "trade_count": "total_trades",
}


def _source_paths() -> list[Path]:
    """Bundle behavior sources plus every experiment helper this runner imports."""
    helper_paths = {
        Path(__file__).resolve(),
        Path(gate1.__file__).resolve(),
        Path(cash_repair.__file__).resolve(),
    }
    paths: list[Path] = []
    for path in QUANT.rglob("*.py"):
        rel_parts = path.relative_to(QUANT).parts
        if "__pycache__" in rel_parts or path.name.startswith("test_"):
            continue
        if "experiments" in rel_parts and path.resolve() not in helper_paths:
            continue
        paths.append(path)
    for name in ("requirements.txt", "pyproject.toml"):
        path = ROOT / name
        if path.exists():
            paths.append(path)
    return sorted(set(paths), key=gate1._repo_rel)


def _configure_gate1_helpers() -> None:
    """Point the proven exp-015 identity helpers at this new immutable anchor."""
    gate1.EXPERIMENT_ID = EXPERIMENT_ID
    gate1.PROTOCOL_ID = PROTOCOL_ID
    gate1.OLD_BASELINE = PRIOR_BASELINE
    gate1.EXP_DIR = EXP_DIR
    gate1.FROZEN_INPUTS = FROZEN_INPUTS
    gate1.SOURCE_IDENTITY = SOURCE_IDENTITY
    gate1.SOURCE_BUNDLE = SOURCE_BUNDLE
    gate1.BEFORE_MEASUREMENT = BEFORE_MEASUREMENT
    gate1.AFTER_MEASUREMENT = AFTER_MEASUREMENT
    gate1.REPLAY_IDENTITY = REPLAY_IDENTITY
    gate1.BASELINE_DIR = BASELINE_DIR
    gate1.BASELINE_SUMMARY = BASELINE_SUMMARY
    gate1.TICKET = TICKET
    # The imported exp-015 helper normally excludes every experiment runner
    # except itself. This baseline depends on three runners, so override the
    # enumerator before source hashing/bundling.
    gate1._source_paths = _source_paths


def _cash_summary(result: dict[str, Any]) -> dict[str, Any]:
    ledger = result.get("cash_ledger") or {}
    keys = (
        "enforced",
        "initial_cash",
        "min_cash",
        "min_cash_date",
        "negative_cash_event_count",
        "scaled_entry_count",
        "skipped_entry_count",
        "scaled_addon_count",
        "skipped_addon_count",
        "ending_cash",
        "core_realized_pnl",
        "cash_conservation_error",
        "cash_conservation_passed",
    )
    return {key: ledger.get(key) for key in keys}


def _expected_enforced_checks(
    pass_b: dict[str, dict[str, Any]], expected: dict[str, Any]
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        result = pass_b[label]["result"]
        expected_headline = expected["windows"][label]["after"]
        field_checks = {
            expected_key: result.get(result_key) == expected_headline.get(expected_key)
            for expected_key, result_key in HEADLINE_MAP.items()
        }
        cash = _cash_summary(result)
        cash_checks = {
            "enforced": cash["enforced"] is True,
            "zero_negative_cash_events": cash["negative_cash_event_count"] == 0,
            "nonnegative_min_cash": (
                isinstance(cash["min_cash"], (int, float)) and cash["min_cash"] >= 0
            ),
            "cash_conservation_passed": cash["cash_conservation_passed"] is True,
            "zero_cash_conservation_error": cash["cash_conservation_error"] == 0.0,
        }
        checks[label] = {
            "headline_fields": field_checks,
            "headline_all_match": all(field_checks.values()),
            "cash": cash,
            "cash_checks": cash_checks,
            "cash_all_pass": all(cash_checks.values()),
        }
    checks["all_windows_match"] = all(
        checks[spec["label"]]["headline_all_match"]
        and checks[spec["label"]]["cash_all_pass"]
        for spec in gate1.WINDOWS
    )
    return checks


def _run_explicit_unenforced_pass(
    frozen: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] explicit legacy override (cash ledger unenforced) ...", flush=True)
        result = cash_repair._run_window(
            spec, frozen, enforce_cash_ledger=False
        )
        identity = gate1._result_identity(result)
        result_path = EXP_DIR / f"replay_explicit_false_{label}.json"
        gate1._atomic_write_json(
            result_path, gate1._persistable_backtest_result(result)
        )
        records[label] = {
            "identity": identity,
            "result_path": gate1._repo_rel(result_path),
            "result_file_sha256": gate1._file_sha256(result_path),
            "cash": _cash_summary(result),
        }
    return records


def _run_explicit_enforced_pass(
    frozen: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if "CASH_LEDGER_ENFORCED" in gate1.RUN_CONFIG:
        raise RuntimeError("Unexpected pre-existing cash-ledger override")
    gate1.RUN_CONFIG["CASH_LEDGER_ENFORCED"] = True
    try:
        return gate1._run_pass("explicit_true", frozen)
    finally:
        gate1.RUN_CONFIG.pop("CASH_LEDGER_ENFORCED", None)


def _legacy_override_checks(
    legacy: dict[str, dict[str, Any]], prior: dict[str, Any]
) -> dict[str, Any]:
    prior_windows = {row["label"]: row for row in prior["windows"]}
    checks: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        identity = legacy[label]["identity"]
        reference = prior_windows[label]
        checks[label] = {
            "trade_rows_sha256_match": (
                identity["trade_rows_sha256"] == reference["trade_rows_sha256"]
            ),
            "daily_return_series_sha256_match": (
                identity["daily_return_series_sha256"]
                == reference["daily_return_series_sha256"]
            ),
            "expected_value_score_match": (
                identity["metrics"]["expected_value_score"]
                == reference["expected_value_score"]
            ),
            "total_pnl_match": (
                identity["metrics"]["total_pnl"] == reference["total_pnl"]
            ),
            "trade_count_match": (
                identity["metrics"]["total_trades"] == reference["trade_count"]
            ),
            "ledger_enforced_false": legacy[label]["cash"]["enforced"] is False,
        }
        checks[label]["all_match"] = all(checks[label].values())
    checks["all_windows_match"] = all(
        checks[spec["label"]]["all_match"] for spec in gate1.WINDOWS
    )
    return checks


def _enrich_published_manifests(
    rows: list[dict[str, Any]], pass_b: dict[str, dict[str, Any]]
) -> None:
    for row in rows:
        label = row["label"]
        cash = _cash_summary(pass_b[label]["result"])
        manifest_path = ROOT / row["manifest_path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema"] = "cash_feasible_gate1_window_baseline_v1"
        manifest["baseline_role"] = "active_cash_feasible_gate1_reference"
        manifest["cash_ledger"] = cash
        manifest["cash_policy_provenance"] = {
            "accepted_repair": "exp-20260715-008",
            "default_flip": EXPERIMENT_ID,
            "policy_changed_from_accepted_repair": False,
        }
        manifest["baseline_manifest_sha256"] = gate1._stable_hash(
            {
                "schema": manifest["schema"],
                "result_identity": manifest["result_identity"],
                "input_stage_sha256": manifest["input_stage_sha256"],
                "resolved_config_sha256": manifest["resolved_config_sha256"],
                "cash_ledger": cash,
                "source_tree_sha256": manifest["source_tree_sha256"],
                "source_bundle_sha256": manifest["source_bundle_sha256"],
            }
        )
        gate1._atomic_write_json(manifest_path, manifest)
        row["manifest_sha256"] = gate1._file_sha256(manifest_path)
        row["baseline_manifest_sha256"] = manifest["baseline_manifest_sha256"]
        row["cash_ledger"] = cash


def build_artifact() -> dict[str, Any]:
    _configure_gate1_helpers()
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    if DEFAULT_CONFIG.get("CASH_LEDGER_ENFORCED") is not True:
        raise RuntimeError("Canonical re-baseline requires the default cash ledger flag to be True")
    if "CASH_LEDGER_ENFORCED" in gate1.RUN_CONFIG:
        raise RuntimeError("Gate-1 RUN_CONFIG must exercise the default, not override it")

    source_pre = gate1._source_manifest()
    source_bundle = gate1._write_source_bundle(source_pre)
    gate1._atomic_write_json(
        SOURCE_IDENTITY, {**source_pre, "source_bundle": source_bundle}
    )
    frozen = gate1._load_or_capture_frozen_inputs(refresh=False)
    expected = json.loads(EXPECTED_ENFORCED.read_text(encoding="utf-8"))
    prior = json.loads(PRIOR_BASELINE.read_text(encoding="utf-8"))
    input_pre = gate1._input_stage(frozen)
    dependencies = gate1._dependency_identity()

    print("[explicit-true] replay pass A ...", flush=True)
    pass_a = _run_explicit_enforced_pass(frozen)
    source_after_a = gate1._source_manifest()
    input_after_a = gate1._input_stage(frozen)
    print("[default-on] replay pass B ...", flush=True)
    pass_b = gate1._run_pass("default", frozen)
    source_after_b = gate1._source_manifest()
    input_after_b = gate1._input_stage(frozen)
    legacy = _run_explicit_unenforced_pass(frozen)
    source_after_legacy = gate1._source_manifest()
    input_after_legacy = gate1._input_stage(frozen)

    source_stage_hashes = [
        stage["source_tree_sha256"]
        for stage in (source_pre, source_after_a, source_after_b, source_after_legacy)
    ]
    input_stage_hashes = [
        stage["input_stage_sha256"]
        for stage in (input_pre, input_after_a, input_after_b, input_after_legacy)
    ]
    per_window_exact = {}
    cash_ledger_hashes = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        pass_a_cash_hash = gate1._stable_hash(
            pass_a[label]["result"].get("cash_ledger") or {}
        )
        pass_b_cash_hash = gate1._stable_hash(
            pass_b[label]["result"].get("cash_ledger") or {}
        )
        cash_ledger_hashes[label] = {
            "explicit_true": pass_a_cash_hash,
            "default_true": pass_b_cash_hash,
            "match": pass_a_cash_hash == pass_b_cash_hash,
        }
        per_window_exact[label] = (
            pass_a[label]["identity"] == pass_b[label]["identity"]
            and cash_ledger_hashes[label]["match"]
        )
    expected_checks = _expected_enforced_checks(pass_b, expected)
    legacy_checks = _legacy_override_checks(legacy, prior)
    inference_passed = all(
        pass_b[spec["label"]]["identity"]["sharpe_inference_contract_passed"]
        for spec in gate1.WINDOWS
    )
    frozen_hash_matches = (
        frozen["behavior_sha256"]
        == expected["frozen_behavior_inputs"]["behavior_sha256"]
        == prior["frozen_behavior_inputs"]["behavior_sha256"]
    )
    acceptance = {
        "default_cash_ledger_enforced": (
            DEFAULT_CONFIG["CASH_LEDGER_ENFORCED"] is True
        ),
        "frozen_behavior_hash_matches_prior_and_exp008": frozen_hash_matches,
        "source_identity_stable": len(set(source_stage_hashes)) == 1,
        "input_identity_stable": len(set(input_stage_hashes)) == 1,
        "double_replay_exact_all_windows": all(per_window_exact.values()),
        "sharpe_inference_contract_passed": inference_passed,
        "expected_enforced_reference_matches": expected_checks["all_windows_match"],
        "explicit_false_reproduces_prior_anchor": legacy_checks["all_windows_match"],
        "source_bundle_verified": (
            source_bundle["sha256"] == gate1._file_sha256(SOURCE_BUNDLE)
        ),
    }
    accepted = all(acceptance.values())

    rows: list[dict[str, Any]] = []
    aggregate: dict[str, Any] = {}
    if accepted:
        rows, aggregate = gate1._publish_baseline(
            pass_b,
            source_pre,
            source_bundle,
            input_pre,
            frozen,
            dependencies,
        )
        _enrich_published_manifests(rows, pass_b)
        aggregate["expected_value_score_sum"] = round(
            aggregate["expected_value_score_sum"], 4
        )

    replay_identity = {
        "schema": "cash_feasible_gate1_double_replay_identity_v1",
        "experiment_id": EXPERIMENT_ID,
        "source_stage_hashes": source_stage_hashes,
        "input_stage_hashes": input_stage_hashes,
        "per_window_exact_identity": per_window_exact,
        "pass_a": {label: row["identity"] for label, row in pass_a.items()},
        "pass_b": {label: row["identity"] for label, row in pass_b.items()},
        "cash_ledger_hashes": cash_ledger_hashes,
        "expected_enforced_checks": expected_checks,
        "explicit_false_legacy_checks": legacy_checks,
        "explicit_false_results": legacy,
    }
    gate1._atomic_write_json(REPLAY_IDENTITY, replay_identity)
    gate1._atomic_write_json(
        BEFORE_MEASUREMENT,
        {
            "experiment_id": EXPERIMENT_ID,
            "role": "prior_unenforced_post_mtm_gate1_anchor",
            "source": gate1._repo_rel(PRIOR_BASELINE),
            "source_sha256": gate1._file_sha256(PRIOR_BASELINE),
            "aggregate": prior["aggregate"],
            "interpretation": (
                "Historical leverage-inflated upper bound; retained for provenance "
                "and explicit-False reproduction, not future Gate-4 comparison."
            ),
        },
    )

    artifact = {
        "schema": "cash_feasible_gate1_baseline_summary_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": "accepted_measurement_repair" if accepted else "blocked",
        "accepted_alpha": False,
        "protocol_id": PROTOCOL_ID,
        "baseline_role": (
            "active_cash_feasible_gate1_reference"
            if accepted
            else "provisional_diagnostic"
        ),
        "previous_baseline": gate1._repo_rel(PRIOR_BASELINE),
        "previous_baseline_role": "unenforced_leverage_inflated_upper_bound",
        "cross_protocol_comparison_allowed": True,
        "comparison_note": (
            "The frozen behavior/data/cost identity is unchanged; only the already "
            "accepted execution-date cash-admission gate becomes the default."
        ),
        "cash_policy": {
            "accepted_repair": "exp-20260715-008",
            "default_flip": EXPERIMENT_ID,
            "cash_ledger_enforced": True,
            "admission_semantics_changed_from_exp008": False,
            "locked_semantics": "scale affordable remainder or skip; release cash on exits/reduces",
        },
        "acceptance": acceptance,
        "source_identity": {
            "git_head": source_pre["git_head"],
            "git_branch": source_pre["git_branch"],
            "git_worktree_clean_for_quant": source_pre[
                "git_worktree_clean_for_quant"
            ],
            "source_tree_sha256": source_pre["source_tree_sha256"],
            "source_stage_hashes": source_stage_hashes,
            "source_bundle": source_bundle,
        },
        "input_identity": input_pre,
        "input_stage_hashes": input_stage_hashes,
        "frozen_behavior_inputs": {
            "path": gate1._repo_rel(FROZEN_INPUTS),
            "file_sha256": gate1._file_sha256(FROZEN_INPUTS),
            "behavior_sha256": frozen["behavior_sha256"],
            "universe_count": len(frozen["behavior"]["universe"]),
            "calendar_coverage_fraction": frozen["provenance"].get(
                "calendar_coverage_fraction"
            ),
        },
        "resolved_config": {**DEFAULT_CONFIG, **gate1.RUN_CONFIG},
        "resolved_config_sha256": gate1._stable_hash(
            {**DEFAULT_CONFIG, **gate1.RUN_CONFIG}
        ),
        "dependency_identity": dependencies,
        "double_replay": {
            "identity_artifact": gate1._repo_rel(REPLAY_IDENTITY),
            "per_window_exact_identity": per_window_exact,
            "all_exact": all(per_window_exact.values()),
        },
        "exp008_enforced_reference_checks": expected_checks,
        "explicit_false_legacy_compatibility": legacy_checks,
        "windows": rows,
        "aggregate": aggregate,
        "delta_vs_unenforced_prior": {
            "expected_value_score": (
                round(
                    aggregate.get("expected_value_score_sum", 0)
                    - prior["aggregate"]["expected_value_score_sum"],
                    4,
                )
                if accepted
                else None
            ),
            "total_pnl": (
                round(
                    aggregate.get("total_pnl_sum", 0)
                    - prior["aggregate"]["total_pnl_sum"],
                    2,
                )
                if accepted
                else None
            ),
        },
        "production_impact": {
            "backtester_default_order_admission_changed": True,
            "live_or_paper_orders_changed": False,
            "entry_exit_ranking_sizing_rules_changed": False,
            "live_ready": False,
            "parity_note": (
                "This publishes an executable-capital backtest anchor. Any live "
                "promotion still requires broker cash-reservation and sizing parity."
            ),
        },
        "known_limitations": [
            "The source bundle is recoverable but the surrounding worktree is not a clean release commit.",
            "The frozen yfinance earnings calendar retains the existing historical PIT caveat.",
            "DSR is not computable for a single baseline window without a selection-trial panel.",
        ],
        "alpha_hypothesis_enabled": (
            "Cash-constrained capital-allocation challengers can now be measured "
            "against executable opportunity cost instead of an overdrafted champion."
        ),
        "reproduction": {
            "command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260715_010_cash_feasible_gate1_rebaseline.py"
            )
        },
    }
    gate1._atomic_write_json(AFTER_MEASUREMENT, artifact)
    if accepted:
        gate1._atomic_write_json(BASELINE_SUMMARY, artifact)
    return artifact


def main() -> int:
    artifact = build_artifact()
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": artifact["decision"],
                "baseline_summary": (
                    gate1._repo_rel(BASELINE_SUMMARY)
                    if artifact["decision"] == "accepted_measurement_repair"
                    else None
                ),
                "acceptance": artifact["acceptance"],
                "aggregate": artifact["aggregate"],
                "delta_vs_unenforced_prior": artifact[
                    "delta_vs_unenforced_prior"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if artifact["decision"] == "accepted_measurement_repair" else 2


if __name__ == "__main__":
    raise SystemExit(main())
