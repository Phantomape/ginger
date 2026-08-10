"""exp-20260726-003: live-drift policy-entry eligibility repair.

This measurement-repair runner reproduces the real MRVL +520.64bp legacy
core fill alert, while keeping the evidence boundary explicit: the broker
ledger proves a real BUY fill but does not establish the timestamp timezone,
regular/extended-hours classification, or strategy provenance.  Strategy
provenance comes independently from the current operator position.

The runner verifies that v3 keeps MRVL in the raw core exposure metrics while
excluding its non-policy entry from execution alerts, retains alerting for a
synthetic ``trend_long`` core fill, fails closed for incomplete v3 rows, and
uses current-position provenance only as an in-memory compatibility overlay
for append-only v1/v2 history.  It also hashes the production ledger/state,
runs the focused 19-test contract plus ``py_compile``, and performs an exact
three-window cash-feasible Gate-1 identity replay before self-registration.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, QUANT, EXPERIMENTS, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from backtester import DEFAULT_CONFIG  # noqa: E402
from data_paths import atomic_write_json  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from fill_model import SLIPPAGE_BPS_ENTRY, apply_slippage  # noqa: E402
from open_position_schema import account_positions  # noqa: E402
import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402
import live_drift_reconciliation as ldr  # noqa: E402


EXPERIMENT_ID = "exp-20260726-003"
SLUG = "live_drift_policy_entry_eligibility"
RUNNER = f"quant/experiments/exp_20260726_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
ARTIFACT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT = ARTIFACT_DIR / f"exp_20260726_003_{SLUG}.json"
ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
POSITIONS = ROOT / "operator_inputs" / "open_positions.json"
DRIFT_LEDGER = ROOT / "data" / "live_pilot" / "live_drift" / "ledger.jsonl"
DRIFT_STATE = ROOT / "data" / "live_pilot" / "live_drift" / "state.json"
BROKER_FILLS = ROOT / "data" / "live_pilot" / "broker_execution" / "fills.jsonl"
DIGEST = ROOT / "data" / "research_digest" / "latest_digest.md"
DIGEST_LEDGER = ROOT / "data" / "research_digest" / "ledger.jsonl"

MRVL_POSITION_ID = "5438192453869111284"
MRVL_DEAL_ID = "813560059998291594"
MRVL_ASOF = "2026-07-24"
EXPECTED_MRVL_FILL_DRIFT = 0.052064
EXPECTED_MRVL_FILL_DRIFT_BPS = 520.64


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def surface_fingerprint() -> dict[str, Any]:
    ledger_rows = load_jsonl(DRIFT_LEDGER)
    return {
        "ledger": {
            "path": rel(DRIFT_LEDGER),
            "sha256": sha256(DRIFT_LEDGER),
            "byte_count": DRIFT_LEDGER.stat().st_size,
            "row_count": len(ledger_rows),
        },
        "state": {
            "path": rel(DRIFT_STATE),
            "sha256": sha256(DRIFT_STATE),
            "byte_count": DRIFT_STATE.stat().st_size,
        },
    }


def research_digest_snapshot() -> dict[str, Any]:
    heading_pattern = re.compile(r"^##\s+(res-\S+)")
    digest_ids = [
        match.group(1)
        for line in DIGEST.read_text(encoding="utf-8-sig").splitlines()
        if (match := heading_pattern.match(line)) is not None
    ]
    ledger_rows = load_jsonl(DIGEST_LEDGER)
    consumed_ids = {
        str(row.get("entry_id")) for row in ledger_rows if row.get("entry_id")
    }
    fresh_ids = [entry_id for entry_id in digest_ids if entry_id not in consumed_ids]
    status_counts = Counter(str(row.get("status") or "unknown") for row in ledger_rows)
    return {
        "digest_path": rel(DIGEST),
        "digest_sha256": sha256(DIGEST),
        "ledger_path": rel(DIGEST_LEDGER),
        "ledger_sha256": sha256(DIGEST_LEDGER),
        "digest_entry_ids": digest_ids,
        "fresh_entry_ids": fresh_ids,
        "fresh_entries": len(fresh_ids),
        "ledger_append_required": bool(fresh_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "disposition": (
            "No fresh research-digest entries; no ledger append is required."
            if not fresh_ids
            else "Blocked: fresh entries require an explicit synthesis disposition."
        ),
        "passed": not fresh_ids,
    }


def broker_fill_fact() -> dict[str, Any]:
    matches = []
    for row in load_jsonl(BROKER_FILLS):
        fact = row.get("fact") or {}
        if (
            row.get("record_type") == "broker_deal_snapshot"
            and str(fact.get("deal_id")) == MRVL_DEAL_ID
            and str(fact.get("ticker") or "").upper() == "MRVL"
            and fact.get("trd_side") == "BUY"
            and str(fact.get("qty")) == "10"
            and str(fact.get("price")) == "211.56"
        ):
            matches.append(row)
    if len(matches) != 1:
        raise AssertionError(f"expected one canonical MRVL deal snapshot, got {len(matches)}")
    row = matches[0]
    fact = row["fact"]
    return {
        "source_path": rel(BROKER_FILLS),
        "source_sha256": sha256(BROKER_FILLS),
        "record_type": row.get("record_type"),
        "record_hash": row.get("record_hash"),
        "fact_hash": row.get("fact_hash"),
        "observed_at_utc": row.get("observed_at_utc"),
        "deal_id": fact.get("deal_id"),
        "ticker": fact.get("ticker"),
        "side": fact.get("trd_side"),
        "quantity": fact.get("qty"),
        "price": fact.get("price"),
        "gross_notional": fact.get("gross_notional"),
        "currency": fact.get("currency"),
        "trade_environment": fact.get("trade_environment"),
        "source": fact.get("source"),
        "event_time_raw": fact.get("event_time_raw"),
        "event_time_timezone_status": fact.get("event_time_timezone_status"),
        "event_time_utc": fact.get("event_time_utc"),
        "evidence_boundary": (
            "The broker record establishes a real BUY of 10 MRVL at 211.56 and "
            "retains the raw broker timestamp. Because timezone status is "
            "broker_local_unspecified and event_time_utc is null, it does not "
            "establish regular versus extended hours. It also does not establish "
            "manual/FOMO provenance; that comes from operator_inputs separately."
        ),
    }


def _synthetic_alert_row(rule_version: str) -> dict[str, Any]:
    return {
        "asof_date": "2026-07-24",
        "position_id": f"compat-{rule_version}",
        "ticker": "SYNTH",
        "strategy_bucket": "core",
        "reconcilable": True,
        "suspect_multi_fill": False,
        "market_val": 10_000.0,
        "fill_drift_pct": 0.01,
        "trajectory_drift_pct": 0.0,
        "rule_version": rule_version,
    }


def reproduce_and_verify_live_drift() -> dict[str, Any]:
    operator_payload = load_json(POSITIONS)
    positions = account_positions(operator_payload, positive_only=True)
    mrvl_matches = [
        row
        for row in positions
        if str(row.get("position_id")) == MRVL_POSITION_ID
        and str(row.get("ticker") or "").upper() == "MRVL"
    ]
    if len(mrvl_matches) != 1:
        raise AssertionError(f"expected one current MRVL position, got {len(mrvl_matches)}")
    mrvl = mrvl_matches[0]

    ledger_rows = load_jsonl(DRIFT_LEDGER)
    persisted_state = load_json(DRIFT_STATE)
    legacy_rows = [
        row
        for row in ledger_rows
        if row.get("rule_version")
        in {"live_drift_reconciliation_v1", "live_drift_reconciliation_v2"}
    ]
    legacy_alert = ldr.evaluate_drift_alert(legacy_rows)
    mrvl_core_legacy = [
        row
        for row in legacy_rows
        if str(row.get("position_id")) == MRVL_POSITION_ID
        and row.get("ticker") == "MRVL"
        and row.get("strategy_bucket") == "core"
    ]

    broker = broker_fill_fact()

    enriched_rows = ldr._enrich_legacy_alert_rows(legacy_rows, [mrvl])
    enriched_alert = ldr.evaluate_drift_alert(enriched_rows)
    enriched_mrvl = [
        row
        for row in enriched_rows
        if str(row.get("position_id")) == MRVL_POSITION_ID
        and row.get("rule_version")
        in {"live_drift_reconciliation_v1", "live_drift_reconciliation_v2"}
    ]
    original_mrvl = [
        row
        for row in legacy_rows
        if str(row.get("position_id")) == MRVL_POSITION_ID
    ]

    # Deterministic bars reproduce the exact real ledger inputs. They avoid
    # inferring any broker timezone/session classification from event_time_raw.
    mrvl_bars = [
        {"date": "2026-07-22", "open": 200.99, "close": 210.99},
        {"date": "2026-07-23", "open": 209.32, "close": 209.32},
        {"date": "2026-07-24", "open": 194.23, "close": 194.23},
    ]
    repaired_state = ldr.build_live_drift_reconciliation(
        as_of=MRVL_ASOF,
        positions=[mrvl],
        bars_fn=lambda ticker: mrvl_bars,
        persist=False,
        ledger_path=DRIFT_LEDGER,
        state_path=DRIFT_STATE,
    )
    persisted_core = (persisted_state.get("buckets") or {}).get("core") or {}
    repaired_core = (repaired_state.get("buckets") or {}).get("core") or {}
    raw_core_keys = (
        "positions",
        "reconciled",
        "notional_usd",
        "weighted_trajectory_drift_pct",
        "mean_fill_drift_pct",
    )
    persisted_raw_core = {key: persisted_core.get(key) for key in raw_core_keys}
    repaired_raw_core = {key: repaired_core.get(key) for key in raw_core_keys}

    modeled_entry = apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    trend_position = {
        "position_id": "synthetic-trend-long",
        "ticker": "SYNTH",
        "direction": "long",
        "shares": 100.0,
        "avg_cost": modeled_entry * 1.01,
        "entry_date": "2026-07-22",
        "market_val": 10_100.0,
        "unrealized_pl": 0.0,
        "opened_by_strategy": "trend_long",
        "sleeve": "core_strategy",
        "slot_policy": "consumes_core_slot",
    }
    trend_row = ldr.reconcile_position(
        trend_position,
        [
            {"date": "2026-07-22", "open": 100.0, "close": 100.5},
            {"date": "2026-07-24", "open": 100.5, "close": 101.0},
        ],
        MRVL_ASOF,
    )
    trend_alert = ldr.evaluate_drift_alert([trend_row])

    v1_alert = ldr.evaluate_drift_alert(
        [_synthetic_alert_row("live_drift_reconciliation_v1")]
    )
    v2_alert = ldr.evaluate_drift_alert(
        [_synthetic_alert_row("live_drift_reconciliation_v2")]
    )
    v3_alert = ldr.evaluate_drift_alert(
        [_synthetic_alert_row("live_drift_reconciliation_v3")]
    )

    checks = {
        "persisted_fault_is_v2_core_fill_alert": (
            persisted_state.get("rule_version") == "live_drift_reconciliation_v2"
            and (persisted_state.get("alert") or {}).get("fill_alert") is True
            and (persisted_state.get("alert") or {}).get(
                "latest_mean_fill_drift_pct"
            )
            == EXPECTED_MRVL_FILL_DRIFT
        ),
        "legacy_alert_reproduced": (
            legacy_alert.get("fill_alert") is True
            and legacy_alert.get("latest_mean_fill_drift_pct")
            == EXPECTED_MRVL_FILL_DRIFT
        ),
        "mrvl_two_forward_core_rows_reproduced": (
            len(mrvl_core_legacy) == 2
            and {row.get("asof_date") for row in mrvl_core_legacy}
            == {"2026-07-23", "2026-07-24"}
            and all(
                row.get("fill_drift_pct") == EXPECTED_MRVL_FILL_DRIFT
                for row in mrvl_core_legacy
            )
        ),
        "mrvl_520_64bp_exact": (
            round(EXPECTED_MRVL_FILL_DRIFT * 10_000, 2)
            == EXPECTED_MRVL_FILL_DRIFT_BPS
        ),
        "operator_provenance_is_fomo_but_core_exposure": (
            mrvl.get("opened_by_strategy") == "fomo"
            and ldr.strategy_bucket(mrvl) == "core"
        ),
        "signal_sentinel_fields_present": (
            bool(str(mrvl.get("entry_date") or "")[:10])
            and float(mrvl.get("target_price") or 0.0) > 0.0
        ),
        "broker_real_fill_fact_matches": (
            broker["trade_environment"] == "REAL"
            and broker["side"] == "BUY"
            and broker["quantity"] == "10"
            and broker["price"] == "211.56"
        ),
        "broker_timezone_and_session_not_inferred": (
            broker["event_time_timezone_status"] == "broker_local_unspecified"
            and broker["event_time_utc"] is None
            and "does not establish regular versus extended hours"
            in broker["evidence_boundary"]
        ),
        "legacy_ledger_rows_remain_unmodified_in_memory": all(
            "core_execution_alert_eligible" not in row for row in original_mrvl
        ),
        "current_position_enrichment_excludes_mrvl_copies": (
            bool(enriched_mrvl)
            and all(
                row.get("entry_strategy_provenance") == "fomo"
                and row.get("core_execution_alert_eligible") is False
                and row.get("core_execution_alert_exclusion_reason")
                == "entry_not_attributable_to_core_policy"
                for row in enriched_mrvl
            )
            and enriched_alert.get("fill_alert") is False
        ),
        "v3_nonpersist_build_used": (
            repaired_state.get("rule_version") == "live_drift_reconciliation_v3"
            and repaired_state.get("appended_rows") == 0
        ),
        "raw_core_bucket_metrics_unchanged": repaired_raw_core == persisted_raw_core,
        "v3_clears_false_policy_alert": (
            (repaired_state.get("alert") or {}).get("fill_alert") is False
            and (repaired_state.get("alert") or {}).get(
                "latest_mean_fill_drift_pct"
            )
            is None
        ),
        "trend_long_core_fill_remains_eligible_and_alerts": (
            trend_row.get("strategy_bucket") == "core"
            and trend_row.get("entry_strategy_provenance") == "trend_long"
            and trend_row.get("core_execution_alert_eligible") is True
            and trend_row.get("fill_drift_pct") == 0.01
            and trend_alert.get("fill_alert") is True
        ),
        "legacy_v1_v2_missing_field_compatibility": (
            v1_alert.get("fill_alert") is True and v2_alert.get("fill_alert") is True
        ),
        "v3_missing_eligibility_fails_closed": (
            v3_alert.get("fill_alert") is False
            and v3_alert.get("latest_mean_fill_drift_pct") is None
        ),
        "alert_formulas_and_thresholds_unchanged": (
            ldr.ALERT_TRAJECTORY_DRIFT_PCT == -0.015
            and ldr.ALERT_CONSECUTIVE_SESSIONS == 10
            and ldr.ALERT_MEAN_FILL_DRIFT_PCT == 0.003
            and trend_alert.get("thresholds")
            == {
                "trajectory_drift_pct": -0.015,
                "consecutive_sessions": 10,
                "mean_fill_drift_pct": 0.003,
            }
        ),
    }
    return {
        "operator_positions_path": rel(POSITIONS),
        "operator_positions_sha256": sha256(POSITIONS),
        "current_mrvl_position": {
            key: mrvl.get(key)
            for key in (
                "position_id",
                "ticker",
                "shares",
                "avg_cost",
                "entry_date",
                "market_val",
                "unrealized_pl",
                "opened_by_strategy",
                "sleeve",
                "slot_policy",
                "position_group",
            )
        },
        "broker_fill": broker,
        "before": {
            "persisted_state": persisted_state,
            "legacy_alert_reproduction": legacy_alert,
            "mrvl_core_legacy_rows": mrvl_core_legacy,
        },
        "after": {
            "rule_version": repaired_state.get("rule_version"),
            "raw_core_bucket": repaired_core,
            "alert": repaired_state.get("alert"),
            "appended_rows": repaired_state.get("appended_rows"),
        },
        "raw_core_identity": {
            "before": persisted_raw_core,
            "after": repaired_raw_core,
            "exact": repaired_raw_core == persisted_raw_core,
        },
        "legacy_in_memory_enrichment": {
            "alert_before": legacy_alert,
            "alert_after": enriched_alert,
            "mrvl_enriched_rows": enriched_mrvl,
            "persisted_rows_mutated": False,
        },
        "synthetic_policy_core_fill": {
            "row": trend_row,
            "alert": trend_alert,
        },
        "version_compatibility": {
            "v1_missing_field": v1_alert,
            "v2_missing_field": v2_alert,
            "v3_missing_field": v3_alert,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_focused_validation() -> dict[str, Any]:
    python = str(ROOT / ".venv" / "Scripts" / "python.exe")
    commands = [
        [
            python,
            "-B",
            "-m",
            "pytest",
            "quant/test_live_drift_reconciliation.py",
            "-q",
        ],
        [
            python,
            "-B",
            "-m",
            "py_compile",
            "quant/live_drift_reconciliation.py",
            "quant/test_live_drift_reconciliation.py",
            RUNNER,
        ],
    ]
    runs = []
    for index, command in enumerate(commands):
        proc = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        count_contract = True if index else "19 passed" in stdout
        runs.append(
            {
                "command": " ".join(command[1:]),
                "returncode": proc.returncode,
                "expected_test_count_observed": count_contract,
                "stdout_tail": stdout.strip().splitlines()[-5:],
                "stderr_tail": stderr.strip().splitlines()[-5:],
                "passed": proc.returncode == 0 and count_contract,
            }
        )
    return {
        "expected_focused_tests": 19,
        "runs": runs,
        "passed": all(row["passed"] for row in runs),
    }


def _cash_identity(result: dict[str, Any]) -> dict[str, Any]:
    ledger = result.get("cash_ledger") or {}
    keys = (
        "enforced",
        "min_cash",
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


def gate1_identity_replay() -> dict[str, Any]:
    baseline = load_json(ACTIVE_BASELINE)
    baseline_windows = {row["label"]: row for row in baseline["windows"]}
    frozen = gate1._load_or_capture_frozen_inputs(refresh=False)
    windows: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        result, identity = gate1._run_window(spec, frozen)
        reference = baseline_windows[label]
        headline = {
            "expected_value_score": result.get("expected_value_score"),
            "total_pnl": result.get("total_pnl"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "signals_generated": result.get("signals_generated"),
            "signals_survived": result.get("signals_survived"),
            "survival_rate": result.get("survival_rate"),
        }
        reference_headline = {key: reference.get(key) for key in headline}
        cash = _cash_identity(result)
        reference_cash = {
            key: (reference.get("cash_ledger") or {}).get(key) for key in cash
        }
        checks = {
            "trade_rows_sha256_match": identity["trade_rows_sha256"]
            == reference["trade_rows_sha256"],
            "daily_return_series_sha256_match": identity[
                "daily_return_series_sha256"
            ]
            == reference["daily_return_series_sha256"],
            "headline_metrics_match": headline == reference_headline,
            "cash_ledger_match": cash == reference_cash,
            "sharpe_inference_contract_passed": identity[
                "sharpe_inference_contract_passed"
            ],
        }
        windows[label] = {
            "checks": checks,
            "passed": all(checks.values()),
            "headline": headline,
            "reference_headline": reference_headline,
            "trade_rows_sha256": identity["trade_rows_sha256"],
            "daily_return_series_sha256": identity[
                "daily_return_series_sha256"
            ],
            "cash_ledger": cash,
        }
    return {
        "baseline_path": rel(ACTIVE_BASELINE),
        "baseline_sha256": sha256(ACTIVE_BASELINE),
        "default_cash_ledger_enforced": DEFAULT_CONFIG.get("CASH_LEDGER_ENFORCED")
        is True,
        "windows": windows,
        "passed": (
            DEFAULT_CONFIG.get("CASH_LEDGER_ENFORCED") is True
            and len(windows) == 3
            and all(row["passed"] for row in windows.values())
        ),
        "aggregate": baseline["aggregate"],
    }


def main() -> int:
    ticket = load_json(TICKET)
    digest = research_digest_snapshot()
    surface_before = surface_fingerprint()
    live_drift = reproduce_and_verify_live_drift()
    validation = run_focused_validation()
    gate1_replay = gate1_identity_replay()
    surface_after = surface_fingerprint()

    no_surface_write = surface_before == surface_after
    persisted_mrvl_rows = [
        row
        for row in load_jsonl(DRIFT_LEDGER)
        if str(row.get("position_id")) == MRVL_POSITION_ID
        and row.get("rule_version")
        in {"live_drift_reconciliation_v1", "live_drift_reconciliation_v2"}
    ]
    append_only_history_preserved = bool(persisted_mrvl_rows) and all(
        "core_execution_alert_eligible" not in row for row in persisted_mrvl_rows
    )
    checks = {
        "ticket_lifecycle_valid": ticket.get("status")
        in {"claimed", "accepted_measurement_repair"},
        "real_legacy_fault_and_repair_contract_passed": live_drift["passed"],
        "focused_19_tests_and_pycompile_passed": validation["passed"],
        "three_window_cash_feasible_gate1_identity_passed": gate1_replay["passed"],
        "canonical_live_drift_ledger_and_state_hashes_unchanged": no_surface_write,
        "persisted_v1_v2_rows_remain_append_only": append_only_history_preserved,
        "research_digest_has_no_undispositioned_fresh_entries": digest["passed"],
    }
    passed = all(checks.values())
    status = "accepted_measurement_repair" if passed else "blocked"
    decision = status
    now = utc_now()
    failed_checks = [name for name, ok in checks.items() if not ok]
    reserved_prediction = ticket.get("prediction") or {}
    prediction = {
        **reserved_prediction,
        "confidence_reason": (
            "The current operator position explicitly carries "
            "opened_by_strategy=fomo while shared core policy tags are explicit, "
            "and the broker ledger independently proves BUY 10 MRVL at 211.56. "
            "The broker timestamp has no established timezone/session label."
        ),
        "reserved_wording_caveat": (
            "The reserved ticket's manual/ETH wording is not treated as broker "
            "evidence; only the raw fill fact and separate operator provenance are used."
        ),
    }
    probability = float(prediction.get("success_probability") or 0.9)
    baseline_metrics = gate1_replay["aggregate"]
    zero_delta = {
        "expected_value_score_sum": 0.0,
        "total_pnl_sum": 0.0,
        "trade_count_sum": 0,
        "positive_ev_windows": 0,
        "minimum_survival_rate": 0.0,
        "worst_max_drawdown_pct": 0.0,
    }
    changed_files = [
        "quant/live_drift_reconciliation.py",
        "quant/test_live_drift_reconciliation.py",
        "docs/live_drift_reconciliation.md",
        RUNNER,
        rel(ARTIFACT),
        rel(LOG),
        rel(CARD),
        rel(MANIFEST),
        rel(TICKET),
        "docs/experiment_log.jsonl",
        rel(REGISTRY),
    ]
    related_files = changed_files + [
        rel(ACTIVE_BASELINE),
        rel(POSITIONS),
        rel(DRIFT_LEDGER),
        rel(DRIFT_STATE),
        rel(BROKER_FILLS),
        rel(DIGEST),
        rel(DIGEST_LEDGER),
    ]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "measurement_repair",
        "owner": ticket.get("owner") or "codex-alpha-automation",
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": passed,
        "alpha_ready": False,
        "hypothesis": (
            "Urgent live-drift fault recovery: two correctly core-bucketed MRVL "
            "sessions trigger a +520.64bp fill alert, while the broker ledger proves "
            "the fill and the operator position separately identifies FOMO provenance. "
            "Separating core exposure ownership from policy-entry execution-model "
            "eligibility should preserve raw drift without treating this entry as a "
            "policy-conformant next-open fill; no timezone/session inference is required."
        ),
        "reserved_ticket_hypothesis": ticket["hypothesis"],
        "reserved_ticket_hypothesis_caveat": (
            "The reserved manual/after-hours wording is retained for audit only and "
            "is not adopted as a fact by this runner."
        ),
        "alpha_hypothesis": (
            "Default-off core drawdown stabilization that combines price "
            "stabilization, positive flow, and elevated near-put positioning may "
            "identify forced-selling exhaustion; its forward settlements remain "
            "insufficient for an alpha claim."
        ),
        "change_type": ticket["change_type"],
        "implementation_mode": "observe_only_live_drift_policy_entry_eligibility_v3",
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "single_causal_variable": ticket["single_causal_variable"],
        "changed_variable": ticket["changed_variable"],
        "causal_components": ticket.get("causal_components") or [],
        "nearby_prior_experiments": ticket["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["new_evidence_type"],
        "ticket_baseline_reference": ticket.get("baseline_result_file"),
        "active_gate1_baseline": rel(ACTIVE_BASELINE),
        "evidence_boundary": (
            "The broker ledger proves BUY 10 MRVL at 211.56 with a raw timestamp "
            "whose timezone is unspecified. It does not prove regular/extended "
            "hours or manual/FOMO attribution. FOMO provenance is independently "
            "read from the operator position; no session label is required by the repair."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": probability,
            "actual_success": 1 if passed else 0,
            "brier_score": round((probability - (1.0 if passed else 0.0)) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_checks,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(failed_checks)
            ),
            "surprise_note": (
                "Current-position provenance cleanly enriches append-only v1/v2 "
                "alert copies while v3 raw exposure metrics remain exact."
                if passed
                else "One or more predeclared measurement checks failed."
            ),
        },
        "pre_run_questions": {
            "1_money_hypothesis": (
                "The underlying price-flow-derivatives drawdown observer may improve "
                "candidate quality; this repair only restores trustworthy execution attribution."
            ),
            "2_history_and_novelty": (
                "exp-20260706-019 created the surface, exp-20260707-011 handled "
                "multi-fill warm positions, and exp-20260723-010 aligned core-slot "
                "classification. Two new correctly core-classified MRVL v2 sessions "
                "expose the distinct policy-entry provenance mismatch."
            ),
            "3_single_bundle": ticket["single_causal_variable"],
            "4_acceptance": ticket["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
            "6_opportunity_cost": (
                "Cash/no new executable entry remains the cross-sectional winner; "
                "no current observer has enough independent settled evidence to displace it."
            ),
            "7_cross_surface_boundary": (
                "Price, flow, derivatives, event, positioning, portfolio exposure, "
                "operator provenance, broker fills, and live drift were inventoried. "
                "Only the measurement boundary is changed; alpha surfaces remain immature."
            ),
        },
        "alpha_synthesis": {
            "baseline_universe": [
                "47-name cash-feasible core",
                "current broad observation universe",
                "current broker account positions",
                "accepted default-off sleeves",
                "cash",
                "SPY",
                "QQQ",
            ],
            "opportunity_cost_winner": "cash/no new executable entry",
            "evidence_surfaces_used": [
                "price",
                "flow",
                "derivatives",
                "events",
                "positioning",
                "portfolio exposure",
                "operator position provenance",
                "broker execution facts",
                "live drift ledger/state",
                "research digest",
            ],
            "evidence_surfaces_missing": [
                "20 independent closed flow-put decisions",
                "intraday strict 100/20/5/5 maturity",
                "revision cash conflicts and H5/H10/H20 settlements",
                "settled prediction-market rows",
            ],
            "hypothesis_candidates": [
                {
                    "lead": "deep-drawdown stabilization x positive flow x near-put OI",
                    "baseline": "cash and baseline core candidate pool",
                    "treatment": "default-off three-surface observer candidate",
                    "horizon": "fixed forward close windows",
                    "replacement_value": "cash-feasible next-best candidate or cash",
                    "falsifier": "low survival, weak chronological halves, or concentration",
                },
                {
                    "lead": "timestamp-safe estimate revision x muted price response",
                    "baseline": "same-session eligible universe",
                    "treatment": "revision-ranked default-off candidate",
                    "horizon": "H5/H10/H20",
                    "replacement_value": "cash-feasible candidate displaced at admission",
                    "falsifier": "fewer than 10 cash conflicts or 30 settlements per horizon",
                },
                {
                    "lead": "intraday REDUCE_RISK versus next-close hold",
                    "baseline": "next-close hold",
                    "treatment": "deterministic reduce-risk observer action",
                    "horizon": "same-session to next close",
                    "replacement_value": "realized avoided loss net of execution",
                    "falsifier": "strict cohorts fail the frozen 100/20/5/5 contract",
                },
            ],
            "selected_hypothesis": "core drawdown price-flow-derivatives observer",
            "economic_mechanism": (
                "Price stabilization plus flow absorption and crowded downside hedging "
                "may mark exhaustion of forced selling."
            ),
            "falsifier": (
                "Survival below 5%, nonpositive chronological halves, single-name "
                "positive-PnL concentration above 40%, or insufficient independent closes."
            ),
            "evidence_grade": "measurement_repair_underlying_alpha_observer",
            "next_machine_action": (
                "Continue routine observer production and settlements without new IDs; "
                "retain cash until a frozen reopen contract is met."
            ),
        },
        "research_digest": digest,
        "parameters": {
            "rule_version": ldr.RULE_VERSION,
            "policy_entry_tags": sorted(ldr.CORE_STRATEGY_POSITION_TAGS),
            "trajectory_alert_threshold": ldr.ALERT_TRAJECTORY_DRIFT_PCT,
            "trajectory_alert_consecutive_sessions": ldr.ALERT_CONSECUTIVE_SESSIONS,
            "fill_alert_threshold": ldr.ALERT_MEAN_FILL_DRIFT_PCT,
            "mrvl_expected_raw_fill_drift_pct": EXPECTED_MRVL_FILL_DRIFT,
            "mrvl_expected_raw_fill_drift_bps": EXPECTED_MRVL_FILL_DRIFT_BPS,
            "persist": False,
            "strategy_parameters_changed": False,
        },
        "gate1": {
            "passed": gate1_replay["passed"],
            "baseline": rel(ACTIVE_BASELINE),
            "baseline_sha256": gate1_replay["baseline_sha256"],
            "aggregate": baseline_metrics,
            "per_window_identity": gate1_replay["windows"],
        },
        "gate2": {
            "passed": live_drift["passed"] and validation["passed"],
            "fields_checked": [
                "entry_date",
                "target_price contract unchanged",
                "position_id",
                "opened_by_strategy",
                "strategy_bucket",
                "entry_strategy_provenance",
                "entry_strategy_provenance_field",
                "core_execution_alert_eligible",
                "core_execution_alert_exclusion_reason",
            ],
            "provenance_boundary": "operator position, not broker timestamp inference",
        },
        "gate3": {
            "passed": gate1_replay["passed"],
            "filter_added": False,
            "entry_admission_changed": False,
            "signals_generated": sum(
                row["headline"]["signals_generated"]
                for row in gate1_replay["windows"].values()
            ),
            "signals_survived": sum(
                row["headline"]["signals_survived"]
                for row in gate1_replay["windows"].values()
            ),
            "minimum_survival_rate": baseline_metrics["minimum_survival_rate"],
            "survival_floor": 0.05,
        },
        "gate4": {
            "passed": passed,
            "accepted_alpha": False,
            "accepted_measurement_repair": passed,
            "before_after_strategy_delta": zero_delta,
            "measurement_blockers": failed_checks,
            "decision": decision,
        },
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics if gate1_replay["passed"] else {},
        "delta_metrics": zero_delta if gate1_replay["passed"] else {},
        "before": live_drift["before"],
        "after": live_drift["after"],
        "live_drift_verification": live_drift,
        "validation": validation,
        "surface_hash_guard": {
            "before": surface_before,
            "after": surface_after,
            "exact": no_surface_write,
            "persist_called": False,
        },
        "checks": checks,
        "source_hashes": {
            "active_baseline": sha256(ACTIVE_BASELINE),
            "operator_positions": sha256(POSITIONS),
            "live_drift_ledger_before": surface_before["ledger"]["sha256"],
            "live_drift_ledger_after": surface_after["ledger"]["sha256"],
            "live_drift_state_before": surface_before["state"]["sha256"],
            "live_drift_state_after": surface_after["state"]["sha256"],
            "broker_fills": sha256(BROKER_FILLS),
            "research_digest": sha256(DIGEST),
            "research_digest_ledger": sha256(DIGEST_LEDGER),
        },
        "production_impact": {
            "shared_measurement_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "observe_only": True,
            "trade_enabled": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "raw_core_exposure_metrics_changed": False,
            "policy_execution_alert_attribution_changed": True,
            "live_ready": False,
        },
        "acceptance_basis": (
            "The real +520.64bp legacy MRVL alert is reproduced; broker and "
            "operator evidence are kept separate; non-persisting v3 retains exact "
            "raw core metrics while clearing the false policy alert; valid trend_long "
            "fills still alert; v1/v2 compatibility and v3 fail-closed behavior pass; "
            "canonical hashes and all three Gate-1 windows remain exact."
            if passed
            else None
        ),
        "rejection_reason": ";".join(failed_checks) if failed_checks else None,
        "post_run_reflection": {
            "why_result_happened": (
                "Core-slot ownership and core-policy entry attribution were encoded "
                "as one label. MRVL correctly consumed core exposure but its FOMO "
                "operator provenance did not justify comparison with the strategy's "
                "next-open fill model."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another FOMO/manual core-slot alert-exclusion or "
                "v1/v2 provenance-overlay repair; focused tests own this contract."
            ),
            "new_evidence_required": (
                "A new production position whose authoritative policy-entry tag is "
                "misclassified despite v3, an upstream provenance schema change, or "
                "a valid trend/breakout/earnings policy fill whose alert is suppressed."
            ),
        },
        "next_retry_requires": [
            "No near-neighbor retry; regression tests own v3 eligibility semantics.",
            "Underlying alpha waits for its frozen independent-settlement reopen count.",
        ],
        "changed_files": changed_files,
        "related_files": related_files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_live_drift_reconciliation.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": passed,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, ARTIFACT, indent=2, ensure_ascii=False)
    save_experiment_log_entry(
        payload,
        allow_duplicate=True,
        expected_experiment_id=EXPERIMENT_ID,
    )
    CARD.write_text(
        f"# {EXPERIMENT_ID}: live-drift policy-entry eligibility\n\n"
        f"- Decision: `{decision}`\n"
        "- Raw MRVL core fill drift retained: `+520.64bp`\n"
        "- Broker fact: `BUY 10 MRVL @ 211.56`; timezone/session not inferred\n"
        "- Operator provenance: `fomo`; execution-alert eligible: `false`\n"
        "- Synthetic `trend_long` core fill remains alert-eligible\n"
        f"- Canonical ledger/state hashes unchanged: `{no_surface_write}`\n"
        f"- Three-window Gate-1 exact identity: `{gate1_replay['passed']}`\n"
        "- Strategy EV / PnL / trades / survival / drawdown delta: `0`\n"
        "- Accepted alpha: `false`; trade enabled: `false`\n\n"
        "Accepted only as an observe-only measurement repair. The broker timestamp "
        "has no established timezone/session label, and the underlying alpha remains "
        "an immature default-off observer.\n",
        encoding="utf-8",
    )
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=prediction,
        result={
            "accepted": passed,
            "accepted_alpha": False,
            "accepted_measurement_repair": passed,
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "gate4": payload["gate4"],
            "headline_metrics": baseline_metrics,
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        },
        status=status,
        fields={
            **payload,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "card_file": rel(CARD),
            "revision_manifest_file": rel(MANIFEST),
            "ticket_file": rel(TICKET),
            "allowed_write_scope": ticket["allowed_write_scope"],
            "reopen_condition": payload["post_run_reflection"][
                "new_evidence_required"
            ],
        },
    )
    atomic_write_json(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "runner": RUNNER,
            "checks": checks,
            "updated_at": now,
        },
        MANIFEST,
        indent=2,
        ensure_ascii=False,
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "checks": checks,
                "artifact": rel(ARTIFACT),
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
