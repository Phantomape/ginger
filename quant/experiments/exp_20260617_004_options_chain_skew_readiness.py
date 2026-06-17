"""exp-20260617-004: options-chain skew alpha readiness blocker.

This alpha-search experiment evaluates whether the free OnclickMedia options
chain surface can support a candidate-pool alpha under the canonical
backtesting protocol. It makes no strategy, ranking, sizing, exit, watchlist,
LLM/news, daily-runner, or order-path change.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260617-004"
SLUG = "options_chain_skew_readiness"
RUNNER_NAME = "quant/experiments/exp_20260617_004_options_chain_skew_readiness.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260617_004_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "win_rate": 0.8333,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "sharpe_daily": 1.49,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

CANONICAL_AGGREGATE = {
    "expected_value_score": 7.8941,
    "total_pnl": 234850.99,
    "trade_count": 61,
    "signals_generated": 164,
    "signals_survived": 135,
    "survival_rate": round(135 / 164, 4),
    "min_survival_rate": 0.7925,
    "max_drawdown_pct": 0.1119,
}

NEARBY_EXPERIMENTS = [
    "exp-20260617-003",
    "exp-20260616-024",
    "exp-20260616-026",
    "exp-20260616-027",
]

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "historical_options_coverage_absent",
        "vendor_asof_missing",
        "open_interest_lag",
        "fixed_window_gate4_blocked",
    ],
    "confidence_reason": (
        "Options flow is a plausible non-price free-data edge and is not the "
        "Form 4 option-exercise line, but local OnclickMedia files appear "
        "forward-collected only and likely cannot support backtesting.md "
        "fixed-window Gate 4."
    ),
    "recorded_at": "2026-06-17T02:04:45+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/data-edge: free options-chain call/put volume, near-term "
        "volume/open-interest imbalance, and IV skew may expose event demand or "
        "protective pressure earlier than price-only helpers, improving default-off "
        "candidate timing without adding noise tickers."
    ),
    "2_history_check": {
        "exp-20260617-003": (
            "Most executable non-repeat surfaces were blocked or frozen; it did "
            "not evaluate options-chain coverage."
        ),
        "docs/experiment_log.jsonl": (
            "No true options-chain alpha record was found. Recent 'option' hits "
            "are Form 4 option-exercise or generic notes that options are "
            "data/sample-limited."
        ),
        "data/non_ohlcv/options_onclickmedia_summary_20260615.json": (
            "Forward daily options collection exists with PIT-safe next-day "
            "usable rows, but vendor_asof is unavailable and open interest may lag."
        ),
    },
    "3_single_decision_hypothesis": "options_chain_skew_candidate_pool_readiness_v1",
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. A positive alpha would "
        "need enough PIT options-chain rows in late_strong, mid_weak, and old_thin, "
        "then same-protocol before/after Gate 4 with aggregate EV/PnL improvement, "
        "no unacceptable window regression, survival >=5%, enough target trades, "
        "drawdown/concentration guards, and shared daily/backtest helper parity."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260617_004_options_chain_skew_readiness.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def window_for(day: date) -> str | None:
    for label, window in CANONICAL_WINDOWS.items():
        if parse_iso_date(window["start"]) <= day <= parse_iso_date(window["end"]):
            return label
    return None


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return None


def baseline_metrics(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "source": "docs/backtesting.md",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "expected_value_score": CANONICAL_AGGREGATE["expected_value_score"],
        "total_pnl": CANONICAL_AGGREGATE["total_pnl"],
        "total_trades": CANONICAL_AGGREGATE["trade_count"],
        "signals_generated": CANONICAL_AGGREGATE["signals_generated"],
        "signals_survived": CANONICAL_AGGREGATE["signals_survived"],
        "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
        "max_drawdown_pct": CANONICAL_AGGREGATE["max_drawdown_pct"],
        "windows": CANONICAL_WINDOWS,
        "production_impact": {
            "scope": "analysis_only_no_strategy_change",
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
    }


def gate4_block(before: dict[str, Any], after: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, row in CANONICAL_WINDOWS.items():
        by_window[label] = {
            "before_expected_value_score": row["expected_value_score"],
            "after_expected_value_score": row["expected_value_score"],
            "delta_expected_value_score": 0.0,
            "before_total_pnl": row["total_pnl"],
            "after_total_pnl": row["total_pnl"],
            "delta_total_pnl": 0.0,
            "before_trade_count": row["trade_count"],
            "after_trade_count": row["trade_count"],
            "delta_trade_count": 0,
            "before_survival_rate": row["survival_rate"],
            "after_survival_rate": row["survival_rate"],
            "delta_survival_rate": 0.0,
            "before_max_drawdown_pct": row["max_drawdown_pct"],
            "after_max_drawdown_pct": row["max_drawdown_pct"],
            "delta_max_drawdown_pct": 0.0,
            "options_chain_file_count": audit["chain_files_by_fixed_window"].get(label, 0),
            "options_snapshot_ok_or_partial_count": audit["snapshot_status_by_fixed_window"]
            .get(label, {})
            .get("ok_or_partial", 0),
        }
    return {
        "decision": "blocked_no_fixed_window_options_chain_replay_coverage",
        "passed": False,
        "not_run_reason": "options_chain_source_has_no_canonical_fixed_window_replay_rows",
        "aggregate_expected_value_delta": after["expected_value_score"] - before["expected_value_score"],
        "aggregate_total_pnl_delta": after["total_pnl"] - before["total_pnl"],
        "minimum_core_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        "survival_guard_passed": CANONICAL_AGGREGATE["min_survival_rate"] >= 0.05,
        "target_trade_count": 0,
        "target_trade_count_min": 20,
        "target_windows": [],
        "failed_reasons": [
            "historical_options_chain_coverage_absent_in_all_three_fixed_windows",
            "fixed_window_gate4_blocked",
            "vendor_asof_missing",
            "open_interest_reporting_lag",
            "forward_only_observation_required_before_alpha_claim",
        ],
        "by_window": by_window,
    }


def audit_options_surface() -> dict[str, Any]:
    snapshot_status_by_window: dict[str, Counter[str]] = {
        label: Counter() for label in CANONICAL_WINDOWS
    }
    snapshot_examples_by_window: dict[str, list[dict[str, Any]]] = {
        label: [] for label in CANONICAL_WINDOWS
    }
    all_snapshot_status = Counter()
    forward_snapshot_status = Counter()
    snapshot_count = 0

    for path in sorted(NON_OHLCV_DIR.glob("daily_non_ohlcv_snapshot_*.json")):
        snapshot_count += 1
        date_token = path.stem.replace("daily_non_ohlcv_snapshot_", "")
        try:
            day = parse_yyyymmdd(date_token)
            payload = read_json(path)
        except Exception:
            continue
        options = payload.get("options_onclickmedia") or {}
        status = str(options.get("status") or "missing")
        all_snapshot_status[status] += 1
        label = window_for(day)
        if label:
            snapshot_status_by_window[label][status] += 1
            if len(snapshot_examples_by_window[label]) < 3:
                snapshot_examples_by_window[label].append(
                    {
                        "date": day.isoformat(),
                        "status": status,
                        "reason": options.get("reason"),
                        "rows_written": options.get("rows_written"),
                        "output_path": options.get("output_path"),
                    }
                )
        else:
            forward_snapshot_status[status] += 1

    chain_files: list[dict[str, Any]] = []
    chain_files_by_window = Counter()
    chain_files_outside_fixed = Counter()
    usable_dates = Counter()
    pit_flags = Counter()
    row_count = 0
    rows_with_vendor_asof = 0
    rows_with_open_interest = 0
    rows_with_volume = 0
    sample_fields: list[str] = []

    for path in sorted(NON_OHLCV_DIR.glob("options_onclickmedia_chain_*.jsonl")):
        if "exp-" in path.name:
            continue
        token = path.stem.replace("options_onclickmedia_chain_", "")
        try:
            file_day = parse_yyyymmdd(token)
        except ValueError:
            continue
        line_count = 0
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                line_count += 1
                row_count += 1
                if row_count == 1:
                    sample_fields = sorted(json.loads(line).keys())
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("vendor_asof"):
                    rows_with_vendor_asof += 1
                if row.get("open_interest") is not None:
                    rows_with_open_interest += 1
                if row.get("volume") is not None:
                    rows_with_volume += 1
                if row.get("usable_trade_date"):
                    usable_dates[str(row["usable_trade_date"])] += 1
                pit_flags[str(row.get("pit_safe_flag") or row.get("pit_safe"))] += 1
        label = window_for(file_day)
        if label:
            chain_files_by_window[label] += 1
        else:
            chain_files_outside_fixed[file_day.isoformat()] = line_count
        chain_files.append({"date": file_day.isoformat(), "rows": line_count, "path": repo_rel(path)})

    status_by_fixed_window: dict[str, dict[str, int]] = {}
    for label, counter in snapshot_status_by_window.items():
        status_by_fixed_window[label] = dict(counter)
        status_by_fixed_window[label]["ok_or_partial"] = counter.get("ok", 0) + counter.get("partial", 0)

    first_chain_date = chain_files[0]["date"] if chain_files else None
    last_chain_date = chain_files[-1]["date"] if chain_files else None
    return {
        "source": "onclickmedia_options",
        "snapshot_count": snapshot_count,
        "snapshot_status_all": dict(all_snapshot_status),
        "snapshot_status_outside_fixed_windows": dict(forward_snapshot_status),
        "snapshot_status_by_fixed_window": status_by_fixed_window,
        "snapshot_examples_by_fixed_window": snapshot_examples_by_window,
        "chain_file_count": len(chain_files),
        "chain_files_by_fixed_window": dict(chain_files_by_window),
        "chain_file_dates_outside_fixed_window": dict(chain_files_outside_fixed),
        "first_chain_date": first_chain_date,
        "last_chain_date": last_chain_date,
        "total_chain_rows": row_count,
        "rows_with_vendor_asof": rows_with_vendor_asof,
        "rows_with_open_interest": rows_with_open_interest,
        "rows_with_volume": rows_with_volume,
        "usable_trade_date_count": len(usable_dates),
        "first_usable_trade_date": min(usable_dates) if usable_dates else None,
        "last_usable_trade_date": max(usable_dates) if usable_dates else None,
        "pit_flags": dict(pit_flags),
        "sample_fields": sample_fields,
        "coverage_conclusion": (
            "Options-chain rows are forward-collected in 2026-05/2026-06 and "
            "do not cover late_strong, mid_weak, or old_thin. Earlier daily "
            "snapshots usually record options collection as skipped, so a "
            "three-window Gate 4 alpha replay cannot be run."
        ),
    }


def build_result() -> dict[str, Any]:
    before = baseline_metrics("before_baseline")
    after = baseline_metrics("after_no_strategy_change")
    audit = audit_options_surface()
    gate4 = gate4_block(before, after, audit)
    timestamp = utc_now()
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "blocked",
        "decision": "blocked_no_fixed_window_options_chain_replay_coverage",
        "lane": "alpha_search",
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": "production_visible_free_options_chain_candidate_pool",
        "trial_family": "options_chain_skew_candidate_pool_readiness",
        "trial_variant_id": "options_chain_skew_readiness_v1",
        "changed_variable": "options_chain_skew_candidate_pool_readiness_v1",
        "single_causal_variable": "options_chain_skew_candidate_pool_readiness_v1",
        "causal_components": [
            "data_coverage_audit",
            "three_window_gate_blocker",
            "production_parity_boundary",
            "no_strategy_change",
        ],
        "nearby_prior_experiments": NEARBY_EXPERIMENTS,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "prediction": PREDICTION,
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "aggregate_trade_count": 0,
            "minimum_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        },
        "gate4": gate4,
        "options_coverage_audit": audit,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 0,
            "actual_gate4_passed": False,
            "brier_score": round(PREDICTION["success_probability"] ** 2, 4),
            "failure_modes_observed": gate4["failed_reasons"],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "uses_free_options_chain": True,
            "parity_test_added": False,
            "parity_note": (
                "No strategy or adapter code changed. Existing options data "
                "collection is forward observation only. Any future positive "
                "options-chain alpha must first build fixed-window PIT coverage "
                "or collect enough closed forward replacement-value rows, then "
                "use one shared default-off helper for historical replay and "
                "daily production snapshots before retention."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The options-chain idea is economically plausible but not "
                "Gate-4-testable: local chain rows start after the three "
                "canonical fixed windows, earlier daily snapshots skipped options "
                "collection, vendor_asof is absent, and open interest has a "
                "documented reporting lag."
            ),
            "negative_reflection": (
                "Forcing a backtest from post-window options snapshots would be "
                "a production/backtest mismatch and would violate the fixed-window "
                "acceptance rule. A price-only proxy would just repeat frozen "
                "OHLCV morphology."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not test options-chain call/put skew, OI, IV, volume, "
                "expiration, moneyness, ticker-list, top-N, hold-day, or notional "
                "rules on fixed windows until PIT historical options coverage or "
                "sufficient closed forward replacement rows exist."
            ),
            "new_evidence_required": (
                "Either backfill PIT-safe historical options chains covering all "
                "three standard windows with vendor/as-of controls, or collect "
                "at least 20-30 closed forward replacement-value rows from the "
                "existing options snapshot surface before any alpha claim."
            ),
            "best_next_alpha_direction": (
                "Treat options as forward data-edge accumulation, not a current "
                "backtestable alpha. For immediate alpha search, only launch a "
                "new candidate source when it has PIT fields covering the three "
                "canonical windows and is not a frozen Companyfacts/OHLCV/Form4/"
                "FINRA neighbor."
            ),
        },
        "anti_js": "No JavaScript was used.",
        "reproduction": PRE_RUN_QUESTIONS["5_reproducibility"],
    }
    return result


def build_markdown(result: dict[str, Any]) -> str:
    gate = result["gate4"]
    audit = result["options_coverage_audit"]
    lines = [
        f"# {EXPERIMENT_ID} Options-Chain Skew Readiness",
        "",
        f"Status: `{result['status']}`",
        f"Decision: `{result['decision']}`",
        "",
        "## Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Gate 1-4",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Options chain files |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in gate["by_window"].items():
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {files} |".format(
                label=label,
                bev=row["before_expected_value_score"],
                aev=row["after_expected_value_score"],
                dev=row["delta_expected_value_score"],
                bpnl=row["before_total_pnl"],
                apnl=row["after_total_pnl"],
                dpnl=row["delta_total_pnl"],
                surv=row["before_survival_rate"],
                files=row["options_chain_file_count"],
            )
        )
    lines.extend(
        [
            "",
            f"- Aggregate EV delta: `{gate['aggregate_expected_value_delta']:+.4f}`",
            f"- Aggregate PnL delta: `${gate['aggregate_total_pnl_delta']:+,.2f}`",
            f"- Gate 4 status: `{gate['decision']}`",
            f"- Blocking reasons: `{', '.join(gate['failed_reasons'])}`",
            "",
            "## Options Surface",
            "",
            f"- Chain files: `{audit['chain_file_count']}`",
            f"- Chain date range: `{audit['first_chain_date']} -> {audit['last_chain_date']}`",
            f"- Chain rows: `{audit['total_chain_rows']}`",
            f"- Rows with vendor_asof: `{audit['rows_with_vendor_asof']}`",
            f"- Usable trade-date range: `{audit['first_usable_trade_date']} -> {audit['last_usable_trade_date']}`",
            f"- Coverage conclusion: {audit['coverage_conclusion']}",
            "",
            "## Production Impact",
            "",
            result["production_impact"]["parity_note"],
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "status": result["status"],
        "decision": result["decision"],
        "lane": result["lane"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "hypothesis": result["hypothesis"],
        "pre_run_questions": result["pre_run_questions"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "aggregate_expected_value_delta": result["delta_metrics"]["aggregate_expected_value_score"],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
        "gate4": result["gate4"],
        "options_coverage_audit": result["options_coverage_audit"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
    }


def write_manifest(result: dict[str, Any]) -> None:
    files = [
        REPO_ROOT / RUNNER_NAME,
        ARTIFACT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "git_head": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "files": {repo_rel(path): sha256(path) for path in files},
        "command": result["reproduction"],
    }
    write_json(MANIFEST_JSON, manifest)


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, result["before_metrics"])
    write_json(AFTER_JSON, result["after_metrics"])
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_markdown(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before_result_file": repo_rel(BEFORE_JSON),
        "after_result_file": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": NEARBY_EXPERIMENTS,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "post_run_reflection": result["post_run_reflection"],
        "gate4": result["gate4"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=registry_result,
        status="blocked",
        fields=fields,
    )
    write_manifest(result)


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev_delta": result["delta_metrics"]["aggregate_expected_value_score"],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "chain_file_count": result["options_coverage_audit"]["chain_file_count"],
                "chain_date_range": [
                    result["options_coverage_audit"]["first_chain_date"],
                    result["options_coverage_audit"]["last_chain_date"],
                ],
                "fixed_window_chain_files": result["options_coverage_audit"][
                    "chain_files_by_fixed_window"
                ],
                "best_next_alpha_direction": result["post_run_reflection"][
                    "best_next_alpha_direction"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
