"""exp-20260615-027: post-KPI alpha direction blocker scan.

This is an alpha-search direction-selection experiment, not a strategy replay.
It tests whether the recent experiment log plus currently available free data
surfaces contain one non-repeat, PIT-safe, shared-paper-ready alpha candidate.
No trading rule, production helper, ranking, sizing, exit, order, LLM decision,
or daily runner behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260615-027"
SLUG = "post_kpi_alpha_direction_blocker"
RUNNER_NAME = "quant/experiments/exp_20260615_027_post_kpi_alpha_direction_blocker.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"

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

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "all_candidates_frozen",
        "data_surface_insufficient",
        "no_shared_daily_parity",
        "no_gate4_ready_policy_bundle",
    ],
    "confidence_reason": (
        "Recent exp-20260615 history rejected SEC KPI/Form4 variants and blocked "
        "regime/forward-only lanes; only a materially new PIT data edge should proceed."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        lines = []
        replaced = False
        for line in text.splitlines():
            if marker in line:
                lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                lines.append(line)
        if not replaced:
            lines.append(json.dumps(record, sort_keys=True))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    with path.open("a", encoding="utf-8") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return proc.stdout.strip()


def build_backtest_snapshot(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "source": "docs/backtesting.md",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "expected_value_score": CANONICAL_AGGREGATE["expected_value_score"],
        "total_pnl": CANONICAL_AGGREGATE["total_pnl"],
        "total_trades": CANONICAL_AGGREGATE["trade_count"],
        "max_drawdown_pct": CANONICAL_AGGREGATE["max_drawdown_pct"],
        "signals_generated": CANONICAL_AGGREGATE["signals_generated"],
        "signals_survived": CANONICAL_AGGREGATE["signals_survived"],
        "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
        "windows": CANONICAL_WINDOWS,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "scope": "analysis_only_no_strategy_change",
        },
    }


def build_gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for window, before_row in before["windows"].items():
        after_row = after["windows"][window]
        by_window[window] = {
            "before_expected_value_score": before_row["expected_value_score"],
            "after_expected_value_score": after_row["expected_value_score"],
            "delta_expected_value_score": round(
                after_row["expected_value_score"] - before_row["expected_value_score"], 6
            ),
            "before_total_pnl": before_row["total_pnl"],
            "after_total_pnl": after_row["total_pnl"],
            "delta_total_pnl": round(after_row["total_pnl"] - before_row["total_pnl"], 2),
            "before_trade_count": before_row["trade_count"],
            "after_trade_count": after_row["trade_count"],
            "delta_trade_count": after_row["trade_count"] - before_row["trade_count"],
            "before_survival_rate": before_row["survival_rate"],
            "after_survival_rate": after_row["survival_rate"],
            "delta_survival_rate": round(after_row["survival_rate"] - before_row["survival_rate"], 6),
            "before_max_drawdown_pct": before_row["max_drawdown_pct"],
            "after_max_drawdown_pct": after_row["max_drawdown_pct"],
            "delta_max_drawdown_pct": round(
                after_row["max_drawdown_pct"] - before_row["max_drawdown_pct"], 6
            ),
        }
    return {
        "applicable": False,
        "passed": False,
        "reason": (
            "No strategy policy was launched because reviewed directions failed anti-repeat, "
            "PIT coverage, forward sample, or shared-paper parity readiness checks."
        ),
        "aggregate_before": CANONICAL_AGGREGATE,
        "aggregate_after": CANONICAL_AGGREGATE,
        "aggregate_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
            "max_drawdown_pct": 0.0,
        },
        "by_window": by_window,
    }


def log_extract(experiment_id: str) -> dict[str, Any]:
    payload = read_json(REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json", {})
    if not isinstance(payload, dict):
        return {"experiment_id": experiment_id, "exists": False}
    aggregate = (
        payload.get("aggregate_delta_vs_core")
        or payload.get("aggregate_delta")
        or payload.get("delta_metrics")
        or {}
    )
    gate4 = payload.get("gate4") or {}
    return {
        "experiment_id": experiment_id,
        "exists": True,
        "decision": payload.get("decision") or gate4.get("decision"),
        "accepted_alpha": payload.get("accepted_alpha"),
        "aggregate_delta": aggregate,
        "gate4": {
            "passed": gate4.get("passed"),
            "failed_reasons": gate4.get("failed_reasons"),
            "note": gate4.get("note"),
        },
    }


def latest_summary(prefix: str) -> dict[str, Any]:
    files = sorted((REPO_ROOT / "data" / "non_ohlcv").glob(f"{prefix}_*.json"))
    if not files:
        return {"exists": False, "source": None}
    path = files[-1]
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    keys = [
        "schema_version",
        "row_count",
        "rows_written",
        "pit_safe_rows",
        "pit_unsafe_rows",
        "estimate_revision_usable_rows",
        "matched_candidate_rows",
        "estimate_revision_usable_and_matched_candidate_rows",
        "candidate_match_rate",
        "collection_mode",
        "tickers_requested",
        "tickers_with_eps_estimate",
        "up_revision_rows",
        "down_revision_rows",
        "pit_safe_rate",
        "production_impact",
        "pit_notes",
    ]
    return {
        "exists": True,
        "source": repo_rel(path),
        **{key: payload.get(key) for key in keys if key in payload},
    }


def count_files(pattern: str) -> dict[str, Any]:
    files = sorted((REPO_ROOT / "data" / "non_ohlcv").glob(pattern))
    return {
        "pattern": f"data/non_ohlcv/{pattern}",
        "file_count": len(files),
        "first": repo_rel(files[0]) if files else None,
        "latest": repo_rel(files[-1]) if files else None,
    }


def companyfacts_summary() -> dict[str, Any]:
    path = REPO_ROOT / "data" / "non_ohlcv" / "sec_companyfacts_backfill_summary_20241002_20260421.json"
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    return {
        "source": repo_rel(path),
        "exists": path.exists(),
        "rows_written": payload.get("rows_written"),
        "tickers_requested": payload.get("tickers_requested"),
        "tickers_with_cik": payload.get("tickers_with_cik"),
        "selected_canonical_fields": payload.get("selected_canonical_fields"),
        "pit_caveat": payload.get("pit_caveat"),
    }


def build_candidate_reviews() -> list[dict[str, Any]]:
    estimate = latest_summary("estimate_revision_ledger_summary")
    options = latest_summary("options_onclickmedia_summary")
    return [
        {
            "candidate": "sec_saas_operating_kpi_text",
            "alpha_hypothesis": (
                "SaaS/subscription operating KPI evidence in SEC text could reveal durable demand "
                "where price momentum confirms absorption."
            ),
            "history_check": [log_extract("exp-20260615-026"), log_extract("exp-20260614-004")],
            "decision": "blocked_recent_negative_near_neighbor",
            "why_not_run": (
                "exp-20260615-026 was rejected: aggregate EV delta -0.0440, only four event "
                "trades, and late_strong regressed; it also failed to beat the accepted "
                "SEC financial-report RS20 comparator."
            ),
            "retry_requires": (
                "A structured SEC text field with broader PIT coverage and a distinct economic "
                "mechanism, not another keyword/evidence-span variant."
            ),
        },
        {
            "candidate": "form4_ceo_cfo_low_liability",
            "alpha_hypothesis": (
                "Senior officer insider purchases may be more informative when the balance sheet "
                "is low-liability and the market underreacts."
            ),
            "history_check": [log_extract("exp-20260615-024")],
            "decision": "blocked_recent_negative_near_neighbor",
            "why_not_run": (
                "exp-20260615-024 regressed all three windows versus core with aggregate EV "
                "delta -0.1888 and PnL delta -$1361.40."
            ),
            "retry_requires": "Materially new Form 4 feature evidence; no role, hold, notional, or liability retune.",
        },
        {
            "candidate": "pit_regime_chop_state_risk_allocation",
            "alpha_hypothesis": (
                "A PIT chop/tail-state classifier may reduce capital deployed in directionless "
                "or crash-prone states without muting momentum winners."
            ),
            "history_check": [log_extract("exp-20260615-021")],
            "decision": "blocked_forward_rows_and_parity",
            "why_not_run": (
                "exp-20260615-021 had a positive replay lead, but was rejected because current "
                "forward choppy replacement rows were zero and no shared daily regime artifact "
                "exists for promotion."
            ),
            "retry_requires": (
                "A shared daily PIT regime artifact plus at least 20 closed forward choppy rows "
                "with replacement-value evidence before a Gate 1-4 replay."
            ),
        },
        {
            "candidate": "accepted_allocator_source_retune",
            "alpha_hypothesis": (
                "Reordering accepted default-off paper sources could allocate capital toward "
                "higher EV candidate sleeves."
            ),
            "history_check": [log_extract("exp-20260611-005")],
            "decision": "blocked_repeat_risk_without_new_field",
            "why_not_run": (
                "The accepted lagged consensus allocator already supplies the current strongest "
                "shared helper; playbook guidance freezes source/order/scalar retunes unless a "
                "materially new PIT field is added."
            ),
            "retry_requires": "A new PIT data field that changes source priority evidence, not another ordering sweep.",
        },
        {
            "candidate": "pit_analyst_revision_breadth_dispersion",
            "alpha_hypothesis": (
                "Breadth, dispersion, and analyst-count changes in PIT earnings-estimate revisions "
                "could detect expectation upgrades before price fully incorporates them."
            ),
            "current_evidence": {
                "latest_summary": estimate,
                "file_coverage": count_files("estimate_revision_ledger_*.jsonl"),
            },
            "decision": "best_next_data_edge_not_gate4_ready",
            "why_not_run": (
                "The latest summary has usable forward rows but matched_candidate_rows is zero, "
                "so there is no all-window candidate-matched PIT feature set for a trustworthy "
                "Gate 1-4 alpha replay."
            ),
            "retry_requires": (
                "Backfill or construct PIT-safe matched revision features across all three canonical "
                "windows, then implement shared-paper-first daily parity."
            ),
        },
        {
            "candidate": "options_onclickmedia_flow_surface",
            "alpha_hypothesis": (
                "Free options-chain skew, liquidity, or open-interest changes might identify "
                "expectation shifts around liquid momentum names."
            ),
            "current_evidence": {
                "latest_summary": options,
                "file_coverage": count_files("options_onclickmedia_chain_*.jsonl"),
            },
            "decision": "blocked_forward_only_or_pit_unsafe_history",
            "why_not_run": (
                "The adapter explicitly marks historical backfills PIT unsafe; current usable data "
                "is forward daily only and covers too few dates/tickers for the canonical windows."
            ),
            "retry_requires": "A PIT-safe historical options source or enough closed forward rows for observed-only evidence.",
        },
        {
            "candidate": "sec_companyfacts_quality_or_growth_retest",
            "alpha_hypothesis": (
                "Free SEC companyfacts fundamentals can expand or rank candidate pools using "
                "balance-sheet quality and growth-confirmation features."
            ),
            "current_evidence": companyfacts_summary(),
            "decision": "blocked_frozen_threshold_family",
            "why_not_run": (
                "The data surface is broad, but recent Companyfacts quality, growth, and threshold "
                "variants are frozen/rejected unless a materially different PIT economic field is added."
            ),
            "retry_requires": (
                "A new structured mechanism such as customer/supplier contract economics, not another "
                "canonical-field threshold."
            ),
        },
    ]


def build_result() -> dict[str, Any]:
    before = build_backtest_snapshot("before_baseline")
    after = build_backtest_snapshot("after_no_strategy_change")
    gate4 = build_gate4(before, after)
    result = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": "rejected",
        "decision": "rejected_no_gate4_ready_nonrepeat_alpha_candidate",
        "accepted": False,
        "accepted_alpha": False,
        "lane": "alpha_search",
        "change_type": "alpha_direction_selection",
        "changed_variable": "highest_priority_nonrepeat_alpha_candidate_selection_after_post_kpi_history_scan_v1",
        "hypothesis": (
            "Post-KPI-history scan may identify one non-repeat production-visible free-data alpha "
            "candidate; launch only if it has all-window PIT evidence and shared-paper/daily parity, "
            "otherwise block strategy changes and document the next data-edge direction."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate pool / ranking / risk allocation search: find one non-repeat free-data "
                "alpha candidate that is PIT-safe, production-visible, and ready for shared-paper-first."
            ),
            "2_history_check": [
                "exp-20260615-021 rejected replay-only chop tilt: positive lead but no forward choppy rows/shared daily artifact.",
                "exp-20260615-024 rejected Form4 CEO/CFO low-liability: all three windows regressed vs core.",
                "exp-20260615-026 rejected SEC SaaS KPI text: aggregate EV negative and too few event trades.",
                "exp-20260611-005 accepted lagged consensus allocator; near-neighbor source retunes are frozen without new PIT fields.",
            ],
            "3_single_policy_bundle": (
                "The attributable decision is whether a non-repeat alpha candidate is ready today. "
                "All file writes are measurement/closeout artifacts for that decision."
            ),
            "4_acceptance_standard": (
                "Run a strategy alpha only if it can satisfy docs/backtesting.md Gate 1-4 across "
                "late_strong, mid_weak, and old_thin with shared-paper/default-off parity."
            ),
            "5_reproducibility": f".venv\\Scripts\\python.exe -B {RUNNER_NAME}",
        },
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "trade_count": 0,
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
            "max_drawdown_pct": 0.0,
        },
        "gate1": {
            "baseline_result_file": BASELINE_RESULT_FILE,
            "aggregate": CANONICAL_AGGREGATE,
            "by_window": CANONICAL_WINDOWS,
        },
        "gate2": {
            "runtime_fields_checked": False,
            "reason": "No executable rows or strategy policy were created.",
            "future_minimum_required_fields": ["entry_date", "target_price"],
        },
        "gate3": {
            "filter_added": False,
            "baseline_signals_generated": CANONICAL_AGGREGATE["signals_generated"],
            "baseline_signals_survived": CANONICAL_AGGREGATE["signals_survived"],
            "baseline_survival_rate": CANONICAL_AGGREGATE["survival_rate"],
            "minimum_window_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        },
        "gate4": gate4,
        "candidate_reviews": build_candidate_reviews(),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "scope": "analysis_only_no_strategy_change",
            "parity_risk": "none_from_this_run",
        },
        "calibration": {
            "actual_decision": "rejected_no_gate4_ready_nonrepeat_alpha_candidate",
            "actual_success": 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": 0.0,
            "realized_failure_mode": "no_gate4_ready_policy_bundle",
            "predicted_failure_mode_hit": True,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The strongest recent alpha-looking paths are not launchable today: SEC KPI and "
                "Form4 variants just failed the canonical windows, the chop/regime path lacks "
                "forward rows and a shared daily artifact, options data is forward-only or PIT "
                "unsafe historically, and estimate revisions are not yet matched to candidate "
                "rows across the three windows."
            ),
            "why_no_strategy_experiment": (
                "A strategy replay would either retest a frozen near-neighbor or use data that "
                "cannot be replayed PIT-safely and production-visibly. That would not be a "
                "trustworthy alpha measurement and would risk backtest/production inconsistency."
            ),
            "why_negative_or_blocked": (
                "The pre-run hypothesis that at least one non-repeat production-visible candidate "
                "was ready failed. The correct result is to reject launch and preserve the alpha "
                "direction evidence for the next run."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry SEC SaaS/KPI keyword spans, Form4 role/liability/hold/notional tweaks, "
                "chop-threshold/weight sweeps, accepted allocator source retunes, FINRA/FTD threshold "
                "retunes, or Companyfacts quality thresholds without materially new PIT fields."
            ),
            "new_evidence_required": (
                "Construct a free PIT data edge first: analyst revision breadth, dispersion, and analyst-count "
                "features matched to candidates across all three canonical windows, or structured SEC "
                "customer and supplier contract-economics fields with daily default-off parity."
            ),
            "best_next_alpha_direction": (
                "Optimize candidate-pool data edges, not thresholds. First priority is PIT analyst "
                "revision breadth/dispersion matched to historical candidates; second priority is "
                "structured SEC customer/supplier contract economics. Either must be implemented "
                "shared-paper-first before acceptance."
            ),
        },
        "related_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(ARTIFACT_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return result


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Post-KPI Alpha Direction Blocker",
        "",
        "## Decision",
        "",
        f"- Decision: `{result['decision']}`",
        "- Accepted alpha: `false`",
        "- Strategy code changed: `false`",
        "- Production/live impact: `none`",
        "",
        "## Gate 1-4",
        "",
        f"- Gate 1 baseline: `{BASELINE_RESULT_FILE}`.",
        "- Gate 2 fields: no executable rows created; any future alpha must validate `entry_date` and `target_price` at runtime.",
        f"- Gate 3 survival: no filter added; baseline survival `{CANONICAL_AGGREGATE['survival_rate']}`.",
        "- Gate 4: no behavior changed; all three windows are identical before/after because launch is rejected.",
        "",
        "| Window | EV Before | EV After | PnL Before | PnL After | Trades | Survival |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in result["gate4"]["by_window"].items():
        lines.append(
            f"| `{name}` | {row['before_expected_value_score']:.4f} | {row['after_expected_value_score']:.4f} | "
            f"${row['before_total_pnl']:.2f} | ${row['after_total_pnl']:.2f} | "
            f"{row['before_trade_count']} | {row['before_survival_rate']:.4f} |"
        )
    lines.extend(["", "## Candidate Reviews", "", "| Candidate | Decision | Why not run now |", "| --- | --- | --- |"])
    for item in result["candidate_reviews"]:
        lines.append(f"| `{item['candidate']}` | `{item['decision']}` | {item['why_not_run']} |")
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            result["post_run_reflection"]["best_next_alpha_direction"],
            "",
            "## Repro",
            "",
            f"- Runner: `{RUNNER_NAME}`",
            f"- JSON artifact: `{repo_rel(ARTIFACT_JSON)}`",
            f"- Before artifact: `{repo_rel(BEFORE_JSON)}`",
            f"- After artifact: `{repo_rel(AFTER_JSON)}`",
            f"- Log: `{repo_rel(LOG_JSON)}`",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_card(result: dict[str, Any]) -> str:
    return f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "rejected"
lane: "alpha_search"
change_type: "alpha_direction_selection"
mechanism_family: "free_data_candidate_pool_prioritization"
trial_family: "alpha_direction_triage"
trial_variant_id: "post_kpi_blocker_scan_v1"
changed_variable: "highest_priority_nonrepeat_alpha_candidate_selection_after_post_kpi_history_scan_v1"
completed_at: "{result["timestamp"]}"
tags:
  - "alpha_search"
  - "rejected"
  - "alpha_direction_selection"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Rejected launch after reviewing recent SEC KPI, Form4, PIT regime, allocator, analyst revision, options, and Companyfacts/SEC data-edge candidates. No strategy code changed and no production/backtest behavior changed.

## Hypothesis

{result["hypothesis"]}

## Gate 1-4

- Gate 1: baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3: no filter added; baseline min survival `0.7925`.
- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; strategy launch rejected.

## Decision

`{result["decision"]}`

## Why Rejected

{result["post_run_reflection"]["why_result_happened"]}

## Best Next Direction

{result["post_run_reflection"]["best_next_alpha_direction"]}

## Closeout

- Artifact: `{repo_rel(ARTIFACT_JSON)}`
- Before artifact: `{repo_rel(BEFORE_JSON)}`
- After artifact: `{repo_rel(AFTER_JSON)}`
- Markdown artifact: `{repo_rel(ARTIFACT_MD)}`
- Log: `{repo_rel(LOG_JSON)}`
- Runner: `{RUNNER_NAME}`
- No JavaScript was used.
"""


def write_manifest(result: dict[str, Any]) -> None:
    files = {
        "runner": REPO_ROOT / RUNNER_NAME,
        "artifact_json": ARTIFACT_JSON,
        "before_json": BEFORE_JSON,
        "after_json": AFTER_JSON,
        "artifact_md": ARTIFACT_MD,
        "log": LOG_JSON,
        "card": CARD_MD,
        "ticket": TICKET_JSON,
        "experiment_log": EXPERIMENT_LOG_JSONL,
        "registry": REGISTRY_JSON,
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "decision": result["decision"],
        "git": {
            "branch": git_value("branch", "--show-current"),
            "commit": git_value("rev-parse", "HEAD"),
            "dirty": bool(git_value("status", "--porcelain")),
        },
        "files": {
            key: {"path": repo_rel(value), "exists": value.exists(), "sha256": sha256(value)}
            for key, value in files.items()
        },
    }
    write_json(MANIFEST_JSON, manifest)


def persist(result: dict[str, Any]) -> None:
    before = result["before_metrics"]
    after = result["after_metrics"]
    write_json(BEFORE_JSON, before)
    write_json(AFTER_JSON, after)
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(ARTIFACT_MD, build_markdown(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, result)

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
        "mechanism_family": "free_data_candidate_pool_prioritization",
        "trial_family": "alpha_direction_triage",
        "trial_variant_id": "post_kpi_blocker_scan_v1",
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["changed_variable"],
        "causal_components": [
            "history_scan",
            "anti_repeat_gate",
            "pit_coverage_check",
            "shared_paper_parity_readiness",
            "gate4_applicability_decision",
        ],
        "nearby_prior_experiments": [
            "exp-20260615-014",
            "exp-20260615-015",
            "exp-20260615-021",
            "exp-20260615-024",
            "exp-20260615-026",
            "exp-20260611-005",
        ],
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
        status="rejected",
        fields=fields,
    )
    write_text(CARD_MD, build_card(result))
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
                "best_next_alpha_direction": result["post_run_reflection"]["best_next_alpha_direction"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
