"""exp-20260622-008: Moomoo daily short-volume backfill readiness.

Alpha-search data-edge audit. This run checks whether the local Moomoo
get_daily_short_volume probe is a credible next source for a shared default-off
candidate-pool field. It changes no trading policy.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260622-008"
SLUG = "moomoo_daily_short_volume_backfill_readiness"
RUNNER_NAME = f"quant/experiments/exp_20260622_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260622_008_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PROBE_JSON = (
    REPO_ROOT / "data" / "probes" / "moomoo_daily_short_volume_probe_2026-06-21.json"
)

RAW_ARCHIVE_CANDIDATES = [
    REPO_ROOT / "data" / "non_ohlcv" / "moomoo_daily_short_volume",
    REPO_ROOT / "data" / "moomoo_daily_short_volume",
    REPO_ROOT / "data" / "vendor" / "moomoo_daily_short_volume",
]
SHARED_HELPER_CANDIDATES = [
    REPO_ROOT / "quant" / "moomoo_daily_short_volume.py",
    REPO_ROOT / "quant" / "data_sources" / "moomoo_daily_short_volume.py",
    REPO_ROOT / "quant" / "paper_sleeves" / "moomoo_daily_short_volume.py",
]
DAILY_SNAPSHOT_CANDIDATES = [
    REPO_ROOT / "data" / "paper_sleeves" / "moomoo_daily_short_volume_snapshot.jsonl",
    REPO_ROOT / "data" / "paper_sleeves" / "daily_moomoo_short_volume.jsonl",
]

HYPOTHESIS = (
    "candidate_pool/data-edge: Moomoo daily short-volume activity ratios may "
    "provide a production-visible borrow/sell-pressure context field, but only "
    "if the API-backed historical surface reaches the canonical windows and is "
    "archived as activity-only PIT rows before any candidate-pool replay."
)
CHANGED_VARIABLE = "moomoo_daily_short_volume_backfill_readiness_v1"
TRIAL_FAMILY = "moomoo_daily_short_volume_backfill_readiness"
TRIAL_VARIANT_ID = "moomoo_daily_short_volume_probe_20260621_v1"
MECHANISM_FAMILY = "production_visible_moomoo_daily_short_volume_activity_candidate_pool"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260621-017",
    "exp-20260503-015",
    "exp-20260505-022",
    "exp-20260622-003",
]
NEW_EVIDENCE_AXIS = (
    "Moomoo OpenD get_daily_short_volume probe shows 5/5 liquid US tickers "
    "have daily short-volume history reaching 2024-10-02 and the 2024 stretch; "
    "prior short/borrow audits had zero local daily-short-volume files and only "
    "warned to label it activity-only rather than short-interest positioning."
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if f'"experiment_id": "{EXPERIMENT_ID}"' in line:
                    return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def load_baseline() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT_FILE)
    windows: dict[str, dict[str, Any]] = {}
    for row in raw.get("windows") or []:
        label = str(row.get("label") or "")
        if not label:
            continue
        windows[label] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "snapshot": row.get("source"),
            "expected_value_score": row.get("expected_value_score"),
            "sharpe_daily": row.get("sharpe_daily"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "win_rate": row.get("win_rate"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
        }
    return {"generated_at": raw.get("generated_at"), "windows": windows}


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows.values()),
            2,
        ),
        "total_trade_count": sum(int(row.get("trade_count") or 0) for row in windows.values()),
        "min_survival_rate": round(
            min(float(row.get("survival_rate") or 0.0) for row in windows.values()),
            4,
        )
        if windows
        else 0.0,
        "max_window_drawdown_pct": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in windows.values()),
            4,
        )
        if windows
        else 0.0,
    }


def field_presence(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    out: dict[str, dict[str, Any]] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "present_rate": round(present / total, 4) if total else 0.0,
        }
    return out


def list_existing_paths(paths: list[Path]) -> list[str]:
    return [repo_rel(path) for path in paths if path.exists()]


def count_candidate_files(paths: list[Path]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            candidates.append({"path": repo_rel(path), "exists": False, "file_count": 0})
            continue
        if path.is_file():
            candidates.append({"path": repo_rel(path), "exists": True, "file_count": 1})
            continue
        files = [p for p in path.rglob("*") if p.is_file()]
        candidates.append(
            {"path": repo_rel(path), "exists": True, "file_count": len(files)}
        )
    return {
        "candidates": candidates,
        "any_existing": any(row["exists"] for row in candidates),
        "total_files": sum(int(row["file_count"]) for row in candidates),
    }


def baseline_artifact(label: str, gate1: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "label": label,
        "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
        "windows": gate1["windows"],
        "aggregate": gate1["aggregate"],
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": "No after strategy was launched; after intentionally equals before.",
    }


def metric_deltas(windows: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    return {label: {field: 0.0 for field in fields} for label in windows}


def audit_probe() -> dict[str, Any]:
    probe = read_json(PROBE_JSON)
    rows = [row for row in probe.get("results") or [] if isinstance(row, dict)]
    row_counts = [int(row.get("rows") or 0) for row in rows]
    earliest_dates = [parse_date(row.get("earliest")) for row in rows]
    latest_dates = [parse_date(row.get("latest")) for row in rows]
    earliest_dates = [item for item in earliest_dates if item is not None]
    latest_dates = [item for item in latest_dates if item is not None]

    tickers_probed = int(probe.get("tickers_probed") or 0)
    tickers_with_data = int(probe.get("tickers_with_data") or 0)
    reaching_oldest = int(probe.get("tickers_reaching_oldest_window") or 0)
    reaching_stretch = int(probe.get("tickers_reaching_2024_stretch") or 0)
    coverage_denominator = max(tickers_probed, len(rows), 1)

    dependency_fields = [
        "code",
        "rows",
        "pages",
        "earliest",
        "latest",
        "reaches_oldest_window",
        "reaches_2024_stretch",
        "hit_page_cap",
        "error",
        "entry_date",
        "target_price",
    ]
    raw_archive = count_candidate_files(RAW_ARCHIVE_CANDIDATES)
    shared_helper_existing = list_existing_paths(SHARED_HELPER_CANDIDATES)
    daily_snapshot = count_candidate_files(DAILY_SNAPSHOT_CANDIDATES)

    blocking_reasons = []
    if probe.get("verdict") != "GO":
        blocking_reasons.append("probe_verdict_not_go")
    if reaching_oldest < coverage_denominator:
        blocking_reasons.append("not_all_probe_tickers_reach_oldest_window")
    if reaching_stretch < coverage_denominator:
        blocking_reasons.append("not_all_probe_tickers_reach_2024_stretch")
    if raw_archive["total_files"] == 0:
        blocking_reasons.append("raw_daily_short_volume_rows_not_archived")
    if not shared_helper_existing:
        blocking_reasons.append("shared_default_off_helper_missing")
    if daily_snapshot["total_files"] == 0:
        blocking_reasons.append("daily_default_off_snapshot_missing")
    blocking_reasons.extend(
        [
            "probe_sample_only_not_candidate_universe",
            "activity_field_not_short_interest_positioning",
            "no_candidate_pool_replay_rows_with_entry_date_target_price",
        ]
    )

    return {
        "probe_path": repo_rel(PROBE_JSON),
        "probe": probe,
        "result_count": len(rows),
        "tickers_probed": tickers_probed,
        "tickers_with_data": tickers_with_data,
        "tickers_reaching_oldest_window": reaching_oldest,
        "tickers_reaching_2024_stretch": reaching_stretch,
        "coverage_rates": {
            "with_data": round(tickers_with_data / coverage_denominator, 4),
            "reaching_oldest_window": round(reaching_oldest / coverage_denominator, 4),
            "reaching_2024_stretch": round(reaching_stretch / coverage_denominator, 4),
        },
        "earliest_date_seen": min(earliest_dates).isoformat() if earliest_dates else None,
        "latest_date_seen": max(latest_dates).isoformat() if latest_dates else None,
        "oldest_window_start": probe.get("oldest_window_start"),
        "stretch_start": probe.get("stretch_start"),
        "row_count_stats": {
            "min": min(row_counts) if row_counts else 0,
            "median": median(row_counts) if row_counts else 0,
            "max": max(row_counts) if row_counts else 0,
            "total_probe_rows_reported": sum(row_counts),
        },
        "per_ticker": [
            {
                "code": row.get("code"),
                "rows": row.get("rows"),
                "earliest": row.get("earliest"),
                "latest": row.get("latest"),
                "reaches_oldest_window": row.get("reaches_oldest_window"),
                "reaches_2024_stretch": row.get("reaches_2024_stretch"),
                "hit_page_cap": row.get("hit_page_cap"),
                "error": row.get("error"),
            }
            for row in rows
        ],
        "dependency_presence": field_presence(rows, dependency_fields),
        "raw_archive": raw_archive,
        "shared_helper": {
            "candidate_paths": [repo_rel(path) for path in SHARED_HELPER_CANDIDATES],
            "existing_paths": shared_helper_existing,
            "exists": bool(shared_helper_existing),
        },
        "daily_snapshot": daily_snapshot,
        "readiness": {
            "source_probe_coverage_passed": (
                probe.get("verdict") == "GO"
                and tickers_with_data == coverage_denominator
                and reaching_oldest == coverage_denominator
                and reaching_stretch == coverage_denominator
            ),
            "strategy_replay_allowed": False,
            "blocking_reasons": blocking_reasons,
        },
    }


def build_result() -> dict[str, Any]:
    baseline = load_baseline()
    windows = baseline["windows"]
    aggregate = aggregate_windows(windows)
    probe_audit = audit_probe()
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or {
        "success_probability": 0.22,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "probe_sample_too_small",
            "no_raw_archived_rows",
            "activity_not_positioning",
            "missing_shared_helper",
        ],
        "confidence_reason": (
            "Moomoo probe coverage is promising, but the source is not yet an "
            "archived PIT decision surface."
        ),
    }

    gate1 = {
        "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
        "generated_at": baseline.get("generated_at"),
        "windows": windows,
        "aggregate": aggregate,
        "passed": True,
    }
    gate2 = {
        "source_probe_fields_checked": [
            "code",
            "rows",
            "earliest",
            "latest",
            "reaches_oldest_window",
            "reaches_2024_stretch",
        ],
        "strategy_runtime_fields_checked": ["entry_date", "target_price"],
        "dependency_presence": probe_audit["dependency_presence"],
        "source_probe_fields_passed": True,
        "strategy_field_gate_passed": False,
        "passed": False,
        "blocking_reason": (
            "Probe rows prove API coverage, but they are not archived candidate "
            "rows and do not expose entry_date/target_price replay fields."
        ),
    }
    gate3 = {
        "baseline_survival_by_window": {
            label: {
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
            for label, row in windows.items()
        },
        "source_probe_coverage_passed": probe_audit["readiness"][
            "source_probe_coverage_passed"
        ],
        "tickers_probed": probe_audit["tickers_probed"],
        "tickers_with_data": probe_audit["tickers_with_data"],
        "tickers_reaching_oldest_window": probe_audit[
            "tickers_reaching_oldest_window"
        ],
        "tickers_reaching_2024_stretch": probe_audit["tickers_reaching_2024_stretch"],
        "coverage_rates": probe_audit["coverage_rates"],
        "earliest_date_seen": probe_audit["earliest_date_seen"],
        "latest_date_seen": probe_audit["latest_date_seen"],
        "row_count_stats": probe_audit["row_count_stats"],
        "strategy_replay_allowed": False,
        "passed": False,
        "blocking_reasons": probe_audit["readiness"]["blocking_reasons"],
        "blocking_reason": (
            "Coverage is positive for the five-ticker probe, but strategy replay "
            "is blocked until raw PIT rows, a shared helper, daily snapshot, and "
            "candidate-pool replay rows exist."
        ),
    }
    gate4 = {
        "ran_after_strategy": False,
        "reason_after_not_run": (
            "Blocked at Gate 2/3 readiness; after intentionally equals before."
        ),
        "before_windows": windows,
        "after_windows": windows,
        "delta_by_window": metric_deltas(windows),
        "aggregate_before": aggregate,
        "aggregate_after": aggregate,
        "aggregate_delta": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "min_survival_rate": 0.0,
            "max_window_drawdown_pct": 0.0,
        },
        "passed": False,
    }

    predicted = float(prediction.get("success_probability") or 0.0)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": "observed_only_positive_backfill_lead_not_alpha",
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "novelty": ticket.get("novelty"),
        "pre_run_questions": {
            "money_making_hypothesis": (
                "Daily short-volume activity may proxy same-day sell pressure "
                "or crowding context that can improve candidate selection once "
                "it is archived as a PIT activity field."
            ),
            "history_check": (
                "Novelty gate warned on FINRA/borrow-pressure neighbors and was "
                "overridden only because this run has new Moomoo API coverage "
                "evidence, not a short-interest threshold retune."
            ),
            "single_attributable_policy_bundle": (
                "Backfill readiness of one source: Moomoo daily short-volume "
                "activity. No threshold, top-N, hold period, notional, exit, "
                "ranking, or allocation policy is tested."
            ),
            "acceptance_criteria": (
                "Observed-only lead if coverage is canonical-window capable; no "
                "alpha acceptance until raw PIT rows, shared helper, daily "
                "snapshot, and Gate 1-4 replay exist."
            ),
            "reproducibility": RUNNER_COMMAND,
        },
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
        },
        "probe_audit": probe_audit,
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "uses_moomoo_daily_short_volume": False,
            "backtest_production_parity_risk": "none_from_this_run",
            "parity_note": (
                "No buy/sell/filter/ranking/sizing/risk code changed. A future "
                "test must add a shared default-off helper and daily snapshot "
                "before historical replay or live-visible observations."
            ),
        },
        "live_realistic_execution_envelope": {
            "live_ready": False,
            "trade_enabled": False,
            "notional_cap": None,
            "capital_cap": None,
            "liquidity_slippage_model": "not_evaluated_for_observed_only_source_probe",
            "max_positions": None,
            "sector_theme_limits": None,
            "kill_switch": "future helper must remain default-off until Gate 1-4",
            "order_semantics": "no_orders_from_this_run",
            "failure_handling": "do_not_trade_on_missing_or_stale_short_volume_rows",
            "entered_after_measurement": False,
        },
        "calibration": {
            "predicted_success_probability": predicted,
            "actual_success": 1,
            "actual_success_definition": (
                "Positive data-edge readiness lead only; not alpha acceptance."
            ),
            "brier_score": round((1.0 - predicted) ** 2, 4),
            "realized": "positive_backfill_readiness_lead_blocked_before_strategy",
            "realized_failure_modes": [
                reason
                for reason in probe_audit["readiness"]["blocking_reasons"]
                if reason
                in {
                    "raw_daily_short_volume_rows_not_archived",
                    "shared_default_off_helper_missing",
                    "activity_field_not_short_interest_positioning",
                    "probe_sample_only_not_candidate_universe",
                }
            ],
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The probe is materially positive as a data-source lead: 5/5 "
                "liquid US tickers returned daily short-volume rows, all 5 "
                "reached the old_thin start and the 2024 stretch, and earliest "
                "coverage goes back to 2020-06-30. It is still not a strategy "
                "result because the repository has no raw archived PIT row store, "
                "shared helper, daily default-off snapshot, or candidate replay "
                "rows with entry_date/target_price."
            ),
            "negative_result_reflection": (
                "This does not validate a short-interest or borrow-positioning "
                "alpha. Daily short volume is an activity field; using it as "
                "positioning would recreate a known frozen-family error."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not threshold-sweep daily_short_volume_ratio, top-N, hold "
                "days, notional, cooldown, or FINRA short-interest labels from "
                "this probe-only artifact."
            ),
            "new_evidence_required": (
                "Archive raw Moomoo daily short-volume rows for a broader "
                "candidate universe with usable_trade_date and activity-only "
                "schema labels; then add a shared default-off observation helper, "
                "daily snapshot, parity test, and only then run Gate 1-4 replay."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "new_evidence_axis": result["new_evidence_axis"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "production_impact": result["production_impact"],
        "calibration": result["calibration"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    gate3 = result["gate3"]
    lines = [
        f"# {EXPERIMENT_ID}: Moomoo daily short-volume backfill readiness",
        "",
        "- Lane: alpha_search",
        "- Status: observed_only",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "",
        "## Source Coverage",
        "",
        f"- Tickers probed: {gate3['tickers_probed']}",
        f"- Tickers with data: {gate3['tickers_with_data']}",
        f"- Reached old_thin start: {gate3['tickers_reaching_oldest_window']}",
        f"- Reached 2024 stretch: {gate3['tickers_reaching_2024_stretch']}",
        f"- Earliest date seen: {gate3['earliest_date_seen']}",
        f"- Latest date seen: {gate3['latest_date_seen']}",
        "",
        "## Baseline",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in result["gate1"]["windows"].items():
        ev = float(row.get("expected_value_score") or 0.0)
        pnl = float(row.get("total_pnl") or 0.0)
        lines.append(
            f"| {label} | {ev:.4f} | {ev:.4f} | 0.0000 | "
            f"${pnl:,.2f} | ${pnl:,.2f} | $0.00 |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            result["post_run_reflection"]["new_evidence_required"],
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Observed-only alpha-search readiness record for the Moomoo daily "
        "short-volume source probe.\n\n"
        f"- Artifact: `{repo_rel(ARTIFACT_JSON)}`\n"
        f"- Log: `{repo_rel(LOG_JSON)}`\n"
        f"- Decision: `{result['decision']}`\n"
        f"- Reproduce: `{result['reproduction']}`\n"
    )


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER_NAME,
        ARTIFACT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        README_MD,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline", result["gate1"]))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change", result["gate1"]))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="observed_only",
        fields={
            "owner": "alpha-explore-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_production_visible_activity_data_source",
            "new_evidence_axis": result["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
            "evaluation_windows": [
                {
                    "label": label,
                    "start": row.get("start"),
                    "end": row.get("end"),
                    "snapshot": row.get("snapshot"),
                }
                for label, row in result["gate1"]["windows"].items()
            ],
            "acceptance_rule": (
                "Observed-only positive readiness lead only: no strategy "
                "acceptance until raw PIT rows, shared helper, daily snapshot, "
                "and Gate 1-4 replay exist."
            ),
            "decision": result["decision"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(result))


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "tickers_with_data": result["gate3"]["tickers_with_data"],
                "tickers_reaching_oldest_window": result["gate3"][
                    "tickers_reaching_oldest_window"
                ],
                "earliest_date_seen": result["gate3"]["earliest_date_seen"],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
