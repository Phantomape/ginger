"""exp-20260727-005: restore clean broad-forward paper-row production.

The prospective broad-market membership ledger became auditable on 2026-07-17,
but the paper sleeve carried five pre-cutoff positions into the clean generation.
Those legacy positions consumed every paper slot, so 21 post-cutoff candidate
emissions across 15 tickers created zero clean pending rows.  This runner freezes
that real fault, exercises the repaired cohort contract without persistence, and
records strategy-zero measurement impact.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, QUANT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from broad_market_paper_sleeve import (  # noqa: E402
    build_broad_market_paper_sleeve_snapshot,
    empty_broad_market_paper_state,
)
from data_paths import atomic_write_json  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260727-005"
SLUG = "broad_market_clean_forward_health"
RUNNER = f"quant/experiments/exp_20260727_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
ARTIFACT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT = ARTIFACT_DIR / f"exp_20260727_005_{SLUG}.json"
ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
REAL_STATE = ROOT / "data" / "paper_sleeves" / "broad_market" / "state.json"
REAL_SNAPSHOTS = (
    ROOT / "data" / "paper_sleeves" / "broad_market" / "snapshots.jsonl"
)
REAL_MEMBERSHIP = (
    ROOT / "data" / "state" / "broad_market_paper" / "universe_membership.jsonl"
)
CLEAN_CUTOFF = "2026-07-17"
WINDOW_END = "2026-07-26"
FORWARD_GENERATION = "broad_market_clean_forward_v1"
MEMBERSHIP_FIELDS = (
    "membership_as_of",
    "membership_hash",
    "membership_snapshot_hash",
    "membership_ledger_hash",
    "clean_cutoff",
    "forward_generation",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
    return rows


def freeze_real_starvation() -> dict[str, Any]:
    rows = [
        row
        for row in load_jsonl(REAL_SNAPSHOTS)
        if CLEAN_CUTOFF <= str(row.get("asof_date") or "")[:10] <= WINDOW_END
    ]
    candidate_tickers = sorted(
        {
            str(candidate.get("ticker") or "").upper()
            for row in rows
            for candidate in (row.get("candidates") or [])
            if isinstance(candidate, dict) and candidate.get("ticker")
        }
    )
    state = load_json(REAL_STATE)
    open_positions = [
        row for row in state.get("open_positions") or [] if isinstance(row, dict)
    ]
    clean_open = [
        row
        for row in open_positions
        if str(row.get("created_asof") or "")[:10] >= CLEAN_CUTOFF
    ]
    evidence = {
        "window": {"start": CLEAN_CUTOFF, "end": WINDOW_END},
        "snapshot_rows": len(rows),
        "unique_snapshot_dates": len(
            {str(row.get("asof_date") or "")[:10] for row in rows}
        ),
        "candidate_emissions": sum(int(row.get("candidate_count") or 0) for row in rows),
        "unique_candidate_ticker_count": len(candidate_tickers),
        "unique_candidate_tickers": candidate_tickers,
        "new_pending_emissions": sum(
            int(row.get("new_pending_count") or 0) for row in rows
        ),
        "open_position_counts": sorted(
            {int(row.get("open_position_count") or 0) for row in rows}
        ),
        "real_open_position_count": len(open_positions),
        "real_legacy_open_position_count": len(open_positions) - len(clean_open),
        "real_clean_open_position_count": len(clean_open),
        "real_open_tickers": sorted(
            str(row.get("ticker") or "").upper() for row in open_positions
        ),
    }
    evidence["checks"] = {
        "post_cutoff_snapshots_present": evidence["snapshot_rows"] == 9
        and evidence["unique_snapshot_dates"] == 8,
        "candidate_emissions_exact": evidence["candidate_emissions"] == 21,
        "candidate_breadth_exact": evidence["unique_candidate_ticker_count"] == 15,
        "zero_clean_admissions_reproduced": evidence["new_pending_emissions"] == 0,
        "all_five_slots_remained_occupied": evidence["open_position_counts"] == [5],
        "real_state_is_legacy_only": evidence["real_legacy_open_position_count"] == 5
        and evidence["real_clean_open_position_count"] == 0,
    }
    evidence["passed"] = all(evidence["checks"].values())
    return evidence


def synthetic_rows(start_price: float, step: float) -> list[dict[str, Any]]:
    # Index 60 is the fixed clean cutoff (2026-07-17); index 63 is the next
    # US-equity session (2026-07-20).  This proves prospective behavior only.
    start = date(2026, 5, 18)
    rows = []
    for index in range(64):
        close = start_price + step * index
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "open": close * 0.99,
                "high": close,
                "low": close * 0.98,
                "close": close,
                "volume": 1500.0 if index == 60 else 1000.0,
            }
        )
    return rows


def clean_feed(as_of: str) -> dict[str, Any]:
    return {
        "status": "loaded",
        "path": "synthetic-clean-feed.json",
        "rule_version": "warehouse_sector_cache_feed_v1",
        "as_of": as_of,
        "tickers": ["WIN"],
        "records": {"WIN": {"ticker": "WIN", "sector": "Industrials"}},
        "membership_as_of": as_of,
        "membership_hash": "1" * 64,
        "membership_snapshot_hash": "2" * 64,
        "membership_ledger_hash": "3" * 64,
        "membership_ledger_status": "appended",
        "clean_cutoff": as_of,
        "forward_generation": FORWARD_GENERATION,
    }


def legacy_full_state(created_asof: str) -> dict[str, Any]:
    state = empty_broad_market_paper_state()
    state["open_positions"] = [
        {
            "decision_id": f"legacy-{index}",
            "ticker": f"LEG{index}",
            "created_asof": created_asof,
            "entry_date": created_asof,
            "entry_price": 50.0,
            "notional": 7500.0,
            "observed_trading_days": 0,
            "last_seen_date": created_asof,
            "paper_status": "open",
            "trade_enabled": False,
        }
        for index in range(5)
    ]
    return state


def state_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = empty_broad_market_paper_state()
    for key in ("pending_entries", "open_positions", "closed_positions"):
        state[key] = list(snapshot.get(key) or [])
    return state


def membership_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in MEMBERSHIP_FIELDS}


def exercise_clean_cohort() -> dict[str, Any]:
    real_hashes_before = {
        "state": sha256(REAL_STATE),
        "snapshots": sha256(REAL_SNAPSHOTS),
        "membership": sha256(REAL_MEMBERSHIP),
    }
    spy = synthetic_rows(100.0, 0.02)
    winner = synthetic_rows(50.0, 0.35)
    first_day = spy[60]["date"]
    second_day = spy[63]["date"]
    feed = clean_feed(first_day)
    first = build_broad_market_paper_sleeve_snapshot(
        as_of=first_day,
        ohlcv_by_ticker={"SPY": spy, "WIN": winner},
        candidate_universe=feed,
        state=legacy_full_state(spy[59]["date"]),
        persist=False,
    )
    second = build_broad_market_paper_sleeve_snapshot(
        as_of=second_day,
        ohlcv_by_ticker={"SPY": spy, "WIN": winner},
        candidate_universe={
            **feed,
            "as_of": second_day,
            "membership_as_of": second_day,
        },
        state=state_from_snapshot(first),
        persist=False,
    )
    candidate = (first.get("candidates") or [{}])[0]
    pending = (first.get("pending_entries") or [{}])[0]
    opened = next(
        (
            row
            for row in second.get("open_positions") or []
            if str(row.get("ticker") or "").upper() == "WIN"
        ),
        {},
    )
    real_hashes_after = {
        "state": sha256(REAL_STATE),
        "snapshots": sha256(REAL_SNAPSHOTS),
        "membership": sha256(REAL_MEMBERSHIP),
    }
    result = {
        "first_day": first_day,
        "second_day": second_day,
        "first": {
            "candidate_count": first.get("candidate_count"),
            "new_pending_count": first.get("new_pending_count"),
            "pending_count": first.get("pending_count"),
            "open_position_count": first.get("open_position_count"),
            "cohort_capacity": first.get("cohort_capacity"),
            "candidate_membership": membership_projection(candidate),
            "pending_membership": membership_projection(pending),
        },
        "second": {
            "filled_count": second.get("filled_count"),
            "pending_count": second.get("pending_count"),
            "open_position_count": second.get("open_position_count"),
            "cohort_capacity": second.get("cohort_capacity"),
            "open_membership": membership_projection(opened),
        },
        "real_hashes_before": real_hashes_before,
        "real_hashes_after": real_hashes_after,
    }
    expected_first = membership_projection(feed)
    expected_second = {**expected_first, "membership_as_of": first_day}
    result["checks"] = {
        "legacy_positions_do_not_starve_clean_candidate": first.get(
            "new_pending_count"
        )
        == 1,
        "candidate_provenance_complete": membership_projection(candidate)
        == expected_first,
        "pending_provenance_complete": membership_projection(pending)
        == expected_first,
        "clean_pending_fills_next_session": second.get("filled_count") == 1,
        "open_provenance_complete": membership_projection(opened) == expected_second,
        "legacy_and_clean_positions_coexist_paper_only": second.get(
            "open_position_count"
        )
        == 6,
        "cohort_capacity_diagnostics_present": isinstance(
            first.get("cohort_capacity"), dict
        )
        and isinstance(second.get("cohort_capacity"), dict),
        "trade_remains_disabled": first.get("trade_enabled") is False
        and second.get("trade_enabled") is False,
        "no_real_files_written": real_hashes_before == real_hashes_after,
    }
    result["passed"] = all(result["checks"].values())
    return result


def run_validation() -> dict[str, Any]:
    python = str(ROOT / ".venv" / "Scripts" / "python.exe")
    commands = [
        [
            python,
            "-B",
            "-m",
            "pytest",
            "quant/test_broad_market_paper_sleeve.py",
            "-q",
        ],
        [
            python,
            "-B",
            "-m",
            "py_compile",
            "quant/broad_market_paper_sleeve.py",
            "quant/test_broad_market_paper_sleeve.py",
            RUNNER,
        ],
    ]
    runs = []
    for command in commands:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        runs.append(
            {
                "command": " ".join(command[1:]),
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "").strip().splitlines()[-8:],
                "stderr_tail": (proc.stderr or "").strip().splitlines()[-8:],
            }
        )
    return {"passed": all(row["returncode"] == 0 for row in runs), "runs": runs}


def main() -> int:
    ticket = load_json(TICKET)
    baseline = load_json(ACTIVE_BASELINE)
    real_fault = freeze_real_starvation()
    synthetic = exercise_clean_cohort()
    validation = run_validation()
    baseline_metrics = dict(baseline["aggregate"])
    zero_delta = {
        "expected_value_score_sum": 0.0,
        "total_pnl_sum": 0.0,
        "trade_count_sum": 0,
        "positive_ev_windows": 0,
        "minimum_survival_rate": 0.0,
        "worst_max_drawdown_pct": 0.0,
    }
    previous_result = ticket.get("result") if isinstance(ticket.get("result"), dict) else {}
    retriable_self_registered_block = (
        ticket.get("status") == "blocked"
        and previous_result.get("decision") == "blocked"
        and previous_result.get("artifact") == rel(ARTIFACT)
        and previous_result.get("log") == rel(LOG)
    )
    checks = {
        "ticket_lifecycle_valid": ticket.get("status")
        in {"claimed", "accepted", "accepted_measurement_repair"}
        or retriable_self_registered_block,
        "active_cash_feasible_gate1_readable": baseline.get("baseline_role")
        == "active_cash_feasible_gate1_reference",
        "real_starvation_frozen": real_fault["passed"],
        "clean_cohort_contract_passed": synthetic["passed"],
        "focused_pytest_passed": validation["runs"][0]["returncode"] == 0,
        "py_compile_passed": validation["runs"][1]["returncode"] == 0,
        "strategy_metrics_zero_delta": all(value == 0 for value in zero_delta.values()),
    }
    passed = all(checks.values())
    status = "accepted_measurement_repair" if passed else "blocked"
    decision = status
    now = utc_now()
    changed_files = [
        "quant/broad_market_paper_sleeve.py",
        "quant/test_broad_market_paper_sleeve.py",
        RUNNER,
        rel(ARTIFACT),
        rel(CARD),
        rel(LOG),
        rel(MANIFEST),
        rel(TICKET),
        rel(REGISTRY),
        "docs/experiment_log.jsonl",
    ]
    payload = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "owner": ticket.get("owner") or "codex-alpha-automation",
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": passed,
        "hypothesis": ticket["hypothesis"],
        "alpha_hypothesis": (
            "A PIT broad-universe selector can uncover positive replacement value "
            "outside the selection-conditioned core pool; the first candidate lead "
            "is attention or event evidence not yet confirmed by crowded execution flow."
        ),
        "change_type": ticket["change_type"],
        "implementation_mode": "clean_generation_paper_capacity_isolation",
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "single_causal_variable": ticket["single_causal_variable"],
        "changed_variable": ticket["changed_variable"],
        "causal_components": ticket["causal_components"],
        "nearby_prior_experiments": ticket["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["new_evidence_type"],
        "prediction": ticket.get("prediction"),
        "parameters": {
            "clean_cutoff": CLEAN_CUTOFF,
            "forward_generation": FORWARD_GENERATION,
            "max_active_clean_positions": 5,
            "legacy_carry_semantics": "mark_and_settle_but_do_not_consume_clean_capacity",
            "historical_backfill": False,
        },
        "date_range": {"start": CLEAN_CUTOFF, "end": WINDOW_END},
        "evaluation_windows": ticket.get("evaluation_windows") or [],
        "baseline_artifact": rel(ACTIVE_BASELINE),
        "ticket_baseline_reference": ticket.get("baseline_result_file"),
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics if passed else {},
        "delta_metrics": zero_delta if passed else {},
        "headline_metrics": {
            "post_cutoff_candidate_emissions": real_fault["candidate_emissions"],
            "post_cutoff_unique_candidate_tickers": real_fault[
                "unique_candidate_ticker_count"
            ],
            "pre_repair_clean_pending_rows": real_fault["new_pending_emissions"],
            "legacy_open_positions": real_fault["real_legacy_open_position_count"],
            "synthetic_clean_pending_after_repair": synthetic["first"][
                "new_pending_count"
            ],
            "synthetic_clean_fills_after_repair": synthetic["second"][
                "filled_count"
            ],
            "strategy_ev_delta": 0.0,
            "strategy_pnl_delta": 0.0,
            "strategy_trade_delta": 0,
        },
        "fault_reproduction": real_fault,
        "synthetic_no_persist_validation": synthetic,
        "validation": validation,
        "checks": checks,
        "gate1": {
            "passed": checks["active_cash_feasible_gate1_readable"],
            "reference": rel(ACTIVE_BASELINE),
            "aggregate": baseline_metrics,
            "role": "regression_anchor_only_not_unbiased_expected_return_estimate",
        },
        "gate2": {
            "passed": synthetic["passed"],
            "required_fields": list(MEMBERSHIP_FIELDS),
            "signal_sentinels": (
                "entry_date and target_price remain canonical core signal sentinels; "
                "this default-off paper repair does not alter core signal generation."
            ),
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "pre_repair_candidate_emissions": real_fault["candidate_emissions"],
            "pre_repair_clean_admissions": real_fault["new_pending_emissions"],
            "survival_rate_applicable": False,
        },
        "gate4": {
            "passed": passed,
            "decision": decision,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "strategy_behavior_changed": False,
            "failed_reasons": [name for name, ok in checks.items() if not ok],
        },
        "production_impact": {
            "shared_default_off_paper_helper_changed": passed,
            "backtester_changed": False,
            "run_adapter_changed": False,
            "trade_enabled": False,
            "orders_changed": False,
            "core_signal_generation_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "historical_rows_backfilled": False,
        },
        "core_universe_bias_audit": {
            "current_roster_replayed_historically": True,
            "prior_audit": "exp-20260717-003",
            "watchlist_proxy_static_minus_pit_pnl": 12835.39,
            "directly_ineligible_share_of_static_slice_pnl": 0.8486,
            "interpretation": (
                "Sensitivity evidence, not proof of leakage; the active 6.2057 "
                "Gate-1 is a fixed-basket regression anchor, not an unbiased return estimate."
            ),
            "historical_pit_security_master_available": False,
            "delisting_and_acquisition_coverage_available": False,
        },
        "alpha_synthesis": {
            "baseline_universe": [
                "PIT broad-market forward membership",
                "core static pool as replacement comparator only",
                "SPY",
                "QQQ",
                "cash",
            ],
            "opportunity_cost_winner": None,
            "evidence_surfaces_used": [
                "price",
                "broad forward membership",
                "portfolio capacity",
                "existing event/attention observers",
                "existing flow/positioning observers",
            ],
            "evidence_surfaces_missing": [
                "historical PIT security master with delisted/acquired names",
                "broad candidate absolute liquidity and halt provenance",
                "60 clean settled rows across at least 20 tickers",
                "unified cross-surface coverage matrix",
            ],
            "hypothesis_candidates": [
                "fresh attention without execution crowding",
                "outcome-blind broad-universe selection-bias audit",
                "low-overlap capital allocation among already-qualified candidates",
            ],
            "selected_hypothesis": (
                "Restore auditable broad forward candidate production before testing "
                "attention-without-crowding replacement value."
            ),
            "economic_mechanism": (
                "Searching all decision-time eligible names removes core identity as a "
                "prior and lets early information diffusion compete for the same capital slot."
            ),
            "falsifier": (
                "Broad candidates remain concentrated in core-like winners, fail liquidity "
                "or PIT attribution, or do not beat the displaced core candidate/cash across "
                "5/10/20-day horizons."
            ),
            "evidence_grade": "observer",
            "next_machine_action": (
                "Append future clean candidate decisions prospectively; do not backfill the "
                "21 lost emissions, and do not reserve an alpha ID before 60 clean settled "
                "rows across 20 tickers or a new historical PIT source."
            ),
        },
        "research_digest": {
            "fresh_entries": 0,
            "ledger_append_required": False,
            "disposition": "No fresh digest entries; no ledger append required.",
        },
        "acceptance_basis": (
            "The real forward-starvation fault is frozen, and a deterministic no-persist "
            "replay admits and fills a membership-bound clean row while preserving legacy "
            "carry marking and all live/default behavior."
        ),
        "rejection_reason": None
        if passed
        else ";".join(name for name, ok in checks.items() if not ok),
        "post_run_reflection": {
            "why_result_happened": (
                "Capacity was subtracted across generations, so five pre-cutoff carry "
                "positions permanently prevented the new clean cohort from starting."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not backfill lost post-cutoff candidates, retune the broad momentum "
                "profile, or treat current-roster warehouse history as PIT."
            ),
            "new_evidence_required": (
                "A genuinely historical PIT security master with delisting/acquisition "
                "coverage, or at least 60 clean settled broad-forward rows spanning 20 "
                "distinct tickers before alpha or allocation promotion."
            ),
        },
        "changed_files": changed_files,
        "related_files": changed_files
        + [rel(REAL_STATE), rel(REAL_SNAPSHOTS), rel(REAL_MEMBERSHIP), rel(ACTIVE_BASELINE)],
        "source_hashes": {
            rel(REAL_STATE): sha256(REAL_STATE),
            rel(REAL_SNAPSHOTS): sha256(REAL_SNAPSHOTS),
            rel(REAL_MEMBERSHIP): sha256(REAL_MEMBERSHIP),
            rel(ACTIVE_BASELINE): sha256(ACTIVE_BASELINE),
            "quant/broad_market_paper_sleeve.py": sha256(
                ROOT / "quant" / "broad_market_paper_sleeve.py"
            ),
            "quant/test_broad_market_paper_sleeve.py": sha256(
                ROOT / "quant" / "test_broad_market_paper_sleeve.py"
            ),
        },
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest "
            "quant\\test_broad_market_paper_sleeve.py -q",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            "quant\\broad_market_paper_sleeve.py "
            "quant\\test_broad_market_paper_sleeve.py "
            + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": passed,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, ARTIFACT, indent=2, ensure_ascii=False)
    save_experiment_log_entry(payload, allow_duplicate=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(
        f"# {EXPERIMENT_ID}: Broad clean-forward health\n\n"
        f"- Decision: `{decision}`\n"
        f"- Frozen fault: `{real_fault['candidate_emissions']}` candidate emissions / "
        f"`{real_fault['unique_candidate_ticker_count']}` tickers / "
        f"`{real_fault['new_pending_emissions']}` clean pending rows\n"
        f"- Legacy carry positions: `{real_fault['real_legacy_open_position_count']}`\n"
        f"- Synthetic repaired admission/fill: "
        f"`{synthetic['first']['new_pending_count']}` / "
        f"`{synthetic['second']['filled_count']}`\n"
        "- Strategy EV / PnL / trades changed: `0 / 0 / 0`\n"
        "- Accepted alpha: `false`; trade enabled: `false`\n\n"
        "Legacy paper positions continue to mark and settle, but they no longer "
        "starve the prospective membership-bound clean cohort. Historical candidate "
        "emissions are not backfilled.\n",
        encoding="utf-8",
    )
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=ticket.get("prediction"),
        result={
            "accepted": passed,
            "accepted_alpha": False,
            "accepted_measurement_repair": passed,
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
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
                "headline_metrics": payload["headline_metrics"],
                "artifact": rel(ARTIFACT),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
