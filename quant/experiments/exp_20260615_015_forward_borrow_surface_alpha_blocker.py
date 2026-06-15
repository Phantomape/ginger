from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260615-015"
SLUG = "forward_borrow_surface_alpha_blocker"
RUNNER_NAME = "quant/experiments/exp_20260615_015_forward_borrow_surface_alpha_blocker.py"

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_PATH = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_PATH = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_PATH = ROOT / "docs" / "experiment_log.jsonl"


CANONICAL_BASELINE = {
    "source": "docs/backtesting.md",
    "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
    "aggregate": {
        "expected_value_score": 7.8941,
        "total_pnl": 234850.99,
        "trade_count": 61,
        "signals_generated": 164,
        "signals_survived": 135,
        "survival_rate": round(135 / 164, 4),
        "min_survival_rate": 0.7925,
        "max_drawdown_pct": 0.1119,
    },
    "by_window": {
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
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def repo_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return proc.stdout.strip()


def count_wrapped_rows(path: Path, row_key: str = "rows") -> dict[str, Any]:
    payload = read_json(path, {})
    rows = payload.get(row_key) if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = []
    return {
        "source": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "pit_safe_rows": sum(1 for row in rows if isinstance(row, dict) and row.get("pit_safe") is True),
        "sample_keys": sorted(rows[0].keys())[:24] if rows and isinstance(rows[0], dict) else [],
        "updated_at": payload.get("updated_at") if isinstance(payload, dict) else None,
    }


def count_jsonl(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    skipped = sum(1 for row in rows if row.get("skipped") or row.get("status") == "skipped")
    return {
        "source": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "skipped_rows": skipped,
        "usable_rows": max(len(rows) - skipped, 0),
        "sample_keys": sorted(rows[0].keys())[:24] if rows else [],
    }


def state_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    closed = payload.get("closed_positions") or []
    open_positions = payload.get("open_positions") or []
    pending = payload.get("pending_entries") or []
    return {
        "source": repo_rel(path),
        "exists": path.exists(),
        "sleeve": payload.get("sleeve"),
        "closed_count": len(closed) if isinstance(closed, list) else 0,
        "open_count": len(open_positions) if isinstance(open_positions, list) else 0,
        "pending_count": len(pending) if isinstance(pending, list) else 0,
        "closed_pnl": round(sum(float(row.get("pnl") or 0) for row in closed if isinstance(row, dict)), 2)
        if isinstance(closed, list)
        else 0.0,
        "latest_closed_tickers": [
            row.get("ticker") for row in closed[-5:] if isinstance(row, dict) and row.get("ticker")
        ]
        if isinstance(closed, list)
        else [],
        "updated_at": payload.get("updated_at"),
    }


def forward_replacement_summary(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    by_sleeve: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "closed_rows": 0,
            "pnl_vs_cash": 0.0,
            "vs_spy": 0.0,
            "vs_spy_rows": 0,
            "vs_qqq": 0.0,
            "vs_qqq_rows": 0,
            "tickers": set(),
        }
    )
    for row in rows:
        sleeve = row.get("sleeve_key") or row.get("sleeve") or "unknown"
        bucket = by_sleeve[sleeve]
        bucket["closed_rows"] += 1
        bucket["pnl_vs_cash"] += float(row.get("replacement_value_vs_cash_usd") or row.get("pnl_usd") or 0)
        if row.get("replacement_value_vs_spy_usd") is not None:
            bucket["vs_spy"] += float(row.get("replacement_value_vs_spy_usd") or 0)
            bucket["vs_spy_rows"] += 1
        if row.get("replacement_value_vs_qqq_usd") is not None:
            bucket["vs_qqq"] += float(row.get("replacement_value_vs_qqq_usd") or 0)
            bucket["vs_qqq_rows"] += 1
        if row.get("ticker"):
            bucket["tickers"].add(row["ticker"])
    serialised = {}
    for sleeve, bucket in by_sleeve.items():
        serialised[sleeve] = {
            "closed_rows": bucket["closed_rows"],
            "pnl_vs_cash": round(bucket["pnl_vs_cash"], 2),
            "vs_spy": round(bucket["vs_spy"], 2),
            "vs_spy_rows": bucket["vs_spy_rows"],
            "vs_qqq": round(bucket["vs_qqq"], 2),
            "vs_qqq_rows": bucket["vs_qqq_rows"],
            "tickers": sorted(bucket["tickers"]),
        }
    return {
        "source": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "by_sleeve": dict(sorted(serialised.items())),
    }


def build_backtest_snapshot(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "expected_value_score": CANONICAL_BASELINE["aggregate"]["expected_value_score"],
        "total_pnl": CANONICAL_BASELINE["aggregate"]["total_pnl"],
        "total_trades": CANONICAL_BASELINE["aggregate"]["trade_count"],
        "signals_generated": CANONICAL_BASELINE["aggregate"]["signals_generated"],
        "signals_survived": CANONICAL_BASELINE["aggregate"]["signals_survived"],
        "survival_rate": CANONICAL_BASELINE["aggregate"]["survival_rate"],
        "max_drawdown_pct": CANONICAL_BASELINE["aggregate"]["max_drawdown_pct"],
        "benchmarks": {"strategy_total_return_pct": None},
        "windows": CANONICAL_BASELINE["by_window"],
    }


def gate4_snapshot() -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for name, row in CANONICAL_BASELINE["by_window"].items():
        by_window[name] = {
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
        }
    return {
        "applicable": False,
        "reason": "No strategy policy was launched because every reviewed direction failed anti-repeat, PIT coverage, forward sample, or production/backtest parity readiness checks.",
        "aggregate_before": CANONICAL_BASELINE["aggregate"],
        "aggregate_after": CANONICAL_BASELINE["aggregate"],
        "aggregate_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
            "max_drawdown_pct": 0.0,
        },
        "by_window": by_window,
    }


def coverage_snapshot() -> dict[str, Any]:
    return {
        "finra_short_interest": count_wrapped_rows(
            ROOT / "data" / "non_ohlcv" / "finra_short_interest" / "rows.json"
        ),
        "sec_ftd": count_wrapped_rows(ROOT / "data" / "non_ohlcv" / "sec_ftd" / "rows.json"),
        "sec_leadership_state": state_summary(
            ROOT / "data" / "paper_sleeves" / "sec_leadership" / "state.json"
        ),
        "sec_governance_state": state_summary(
            ROOT / "data" / "paper_sleeves" / "sec_governance" / "state.json"
        ),
        "forward_replacement": forward_replacement_summary(
            ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
        ),
        "estimate_revision_latest": {
            "summary": read_json(
                ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260614.json",
                {},
            ),
            "ledger": count_jsonl(
                ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_20260614.jsonl"
            ),
        },
        "sec_text_latest": count_jsonl(
            ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260614.jsonl"
        ),
        "kova_companyfacts_latest": count_jsonl(
            ROOT / "data" / "kova" / "fundamentals" / "companyfacts_growth_20260614.jsonl"
        ),
    }


def build_result() -> dict[str, Any]:
    now = utc_now()
    coverage = coverage_snapshot()
    forward = coverage["forward_replacement"]["by_sleeve"]
    state_surface = forward.get("state_surface", {})
    low_deployment = forward.get("low_deployment_etf", {})
    sec_leadership = coverage["sec_leadership_state"]
    sec_governance = coverage["sec_governance_state"]
    result = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_candidate",
        "accepted": False,
        "accepted_alpha": False,
        "lane": "alpha_search",
        "change_type": "alpha_direction_selection",
        "mechanism_family": "free_data_candidate_pool_prioritization",
        "trial_family": "alpha_direction_triage",
        "trial_variant_id": "blocker_scan_v2",
        "changed_variable": "highest_priority_nonrepeat_alpha_candidate_selection_after_forward_and_borrow_surface_scan_v1",
        "single_causal_variable": "highest_priority_nonrepeat_alpha_candidate_selection_after_forward_and_borrow_surface_scan_v1",
        "hypothesis": (
            "After exp-20260615-014, a fresh pass over FINRA/FTD, SEC leadership/governance, "
            "forward replacement value, analyst revision, and Kova data might reveal one "
            "non-repeat production-visible free-data alpha candidate. Launch only if PIT "
            "coverage, anti-repeat, and Gate 4 readiness all pass."
        ),
        "before_metrics": build_backtest_snapshot("before_baseline"),
        "after_metrics": build_backtest_snapshot("after_no_strategy_change"),
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
            "max_drawdown_pct": 0.0,
        },
        "gate4": gate4_snapshot(),
        "coverage_snapshot": coverage,
        "candidate_reviews": [
            {
                "candidate": "finra_sec_ftd_borrow_pressure_candidate_pool",
                "alpha_hypothesis": (
                    "High days-to-cover plus recent fails-to-deliver pressure could identify "
                    "squeeze-prone winners when demand is already visible in price."
                ),
                "history_check": ["exp-20260603-007", "exp-20260604-027", "exp-20260516-035", "exp-20260516-037"],
                "current_evidence": {
                    "finra_rows": coverage["finra_short_interest"],
                    "sec_ftd_rows": coverage["sec_ftd"],
                },
                "decision": "blocked_all_candidates_frozen",
                "why_not_run": (
                    "FINRA/IWM and SEC FTD confirmation already have accepted default-off adapters; "
                    "the playbook freezes FINRA/FTD top-N, cooldown, hold, notional, and parameter retunes "
                    "unless a new PIT borrow-cost or share-availability source appears."
                ),
                "retry_requires": "A new borrow fee, hard-to-borrow, or shares-available PIT field, not another FINRA/FTD threshold.",
            },
            {
                "candidate": "sec_item_502_leadership_or_governance_absorption",
                "alpha_hypothesis": (
                    "Official leadership-change or governance filings may create underreaction when "
                    "the next-day price confirms absorption."
                ),
                "history_check": ["exp-20260612-001", "exp-20260614-019", "sec_leadership_event_sleeve"],
                "current_evidence": {
                    "sec_leadership_state": sec_leadership,
                    "sec_governance_state": sec_governance,
                },
                "decision": "blocked_existing_default_off_sleeve_and_forward_sample_too_small",
                "why_not_run": (
                    "Item 5.02 leadership changes are already represented by the SEC leadership default-off sleeve; "
                    f"closed leadership rows are {sec_leadership.get('closed_count')} with "
                    f"closed PnL {sec_leadership.get('closed_pnl')}. A new item-code replay would be a near-duplicate "
                    "without richer semantic provenance."
                ),
                "retry_requires": "Richer PIT semantic fields such as named customer/supplier economics or board-quality context.",
            },
            {
                "candidate": "forward_replacement_promotion_check",
                "alpha_hypothesis": (
                    "A default-off paper helper with enough closed forward replacement value could justify "
                    "a shared-paper historical Gate 4 promotion check."
                ),
                "history_check": ["exp-20260615-014", "state_surface_sleeve_rules"],
                "current_evidence": {
                    "state_surface": state_surface,
                    "low_deployment_etf": low_deployment,
                    "all_sleeves": forward,
                },
                "decision": "blocked_forward_sample_too_small_or_frozen",
                "why_not_run": (
                    f"State-surface forward rows are positive but only {state_surface.get('closed_rows', 0)} closed rows; "
                    "low-deployment ETF has more rows but threshold/list/hold/notional retunes are frozen. "
                    "Neither is a valid new three-window policy bundle today."
                ),
                "retry_requires": "Enough closed true-trigger forward rows, plus a predeclared shared policy that can beat canonical Gate 4.",
            },
            {
                "candidate": "pit_analyst_revision_breadth_dispersion",
                "alpha_hypothesis": (
                    "Real PIT analyst revision breadth, analyst-count delta, and dispersion changes could rank "
                    "candidate-pool additions better than price-only momentum."
                ),
                "history_check": ["exp-20260609-011", "exp-20260615-014"],
                "current_evidence": coverage["estimate_revision_latest"],
                "decision": "blocked_data_surface_insufficient",
                "why_not_run": (
                    "The accepted revision-surprise low-extension source is fixed in the shared allocator, "
                    "but current revision trajectory data is still not matched enough for a fresh canonical "
                    "three-window candidate-pool alpha."
                ),
                "retry_requires": "Build PIT revision breadth/dispersion rows matched to candidates across all three canonical windows.",
            },
            {
                "candidate": "sec_customer_supplier_contract_economics",
                "alpha_hypothesis": (
                    "Customer/supplier identities and quantified contract economics from filings could create a "
                    "more orthogonal data edge than generic SEC text."
                ),
                "history_check": [
                    "exp-20260615-001",
                    "exp-20260615-011",
                    "exp-20260615-012",
                    "exp-20260615-013",
                    "exp-20260614-013",
                    "exp-20260614-015",
                ],
                "current_evidence": {
                    "latest_sec_text": coverage["sec_text_latest"],
                    "kova_companyfacts": coverage["kova_companyfacts_latest"],
                },
                "decision": "blocked_missing_materially_new_pit_semantic_field",
                "why_not_run": (
                    "Generic SEC demand, backlog, restructuring, deleveraging, and guidance evidence spans were "
                    "just rejected; current text rows do not expose a richer structured customer/supplier "
                    "contract-economics field."
                ),
                "retry_requires": "Extract and persist structured counterparty, contract value, duration, renewal, or margin economics before replay.",
            },
        ],
        "production_impact": {
            "scope": "alpha_direction_blocker_only",
            "strategy_code_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "parity_note": (
                "No positive alpha was retained. A future positive alpha must be shared-paper-first, "
                "default-off if exploratory, and covered by historical replay plus daily snapshot parity before acceptance."
            ),
        },
        "prediction": {
            "success_probability": 0.12,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "all_candidates_frozen",
                "data_surface_insufficient",
                "forward_sample_too_small",
                "no_gate4_ready_policy_bundle",
            ],
            "confidence_reason": (
                "exp-20260615-014 already blocked broad lanes; this run only adds FINRA/FTD freeze, "
                "SEC leadership/governance sleeve state, and forward replacement sample evidence."
            ),
        },
        "calibration": {
            "actual_decision": "blocked_no_gate4_ready_nonrepeat_alpha_candidate",
            "actual_success": 0,
            "predicted_success_probability": 0.12,
            "brier_score": round((0.12 - 0.0) ** 2, 6),
            "expected_ev_delta": 0.0,
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "realized_failure_mode": "no_gate4_ready_policy_bundle",
            "predicted_failure_mode_hit": True,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The fresh surfaces did not break the exp-20260615-014 blocker: FINRA/FTD is an accepted "
                "but frozen adapter lane, SEC leadership/governance is already represented with too little "
                "forward evidence, state-surface forward replacement is positive but only three closed rows, "
                "and revision/contract-economics data is not yet Gate 4 ready."
            ),
            "why_no_strategy_experiment": (
                "Running a strategy replay today would either retest a frozen near-neighbor or rely on a "
                "private/incomplete data surface, so the result would not be a trustworthy alpha measurement "
                "and would risk backtest/production inconsistency."
            ),
            "why_negative_or_blocked": (
                "This is a negative alpha-selection result. The pre-run hypothesis that one non-repeat, "
                "production-visible, free-data alpha candidate was ready today failed."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry FINRA/FTD retunes, SEC Item 5.02 item-code absorption, generic SEC text spans, "
                "Companyfacts quality thresholds, forward activation with fewer than durable closed rows, or "
                "accepted allocator/source retunes without a materially new PIT field."
            ),
            "new_evidence_required": (
                "Build a new free PIT data edge: analyst revision breadth/dispersion matched to candidates, "
                "or SEC customer/supplier contract-economics fields; then implement shared-paper-first with "
                "historical replay and daily default-off snapshot parity."
            ),
            "best_next_alpha_direction": (
                "Optimize data-edge construction, not thresholds: prioritize PIT analyst revision breadth/dispersion "
                "or SEC customer/supplier contract economics, then run a shared-paper-first Gate 1-4 experiment."
            ),
        },
        "related_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(ARTIFACT_MD),
            repo_rel(LOG_PATH),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return result


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Forward/Borrow Surface Alpha Blocker",
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
        f"- Gate 1 baseline: `docs/backtesting.md`, aggregate EV `{CANONICAL_BASELINE['aggregate']['expected_value_score']}`, PnL `${CANONICAL_BASELINE['aggregate']['total_pnl']}`.",
        "- Gate 2 fields: no executable rows created; future alpha still requires runtime `entry_date` and `target_price` checks.",
        f"- Gate 3 survival: no filter added; baseline min survival `{CANONICAL_BASELINE['aggregate']['min_survival_rate']}`.",
        "- Gate 4: no behavior changed; all three windows are identical before/after because the alpha launch is blocked.",
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
            f"- Log: `{repo_rel(LOG_PATH)}`",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_card(result: dict[str, Any]) -> str:
    now = result["timestamp"]
    return f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "blocked"
lane: "alpha_search"
change_type: "alpha_direction_selection"
mechanism_family: "free_data_candidate_pool_prioritization"
trial_family: "alpha_direction_triage"
trial_variant_id: "blocker_scan_v2"
changed_variable: "highest_priority_nonrepeat_alpha_candidate_selection_after_forward_and_borrow_surface_scan_v1"
completed_at: "{now}"
tags:
  - "alpha_search"
  - "blocked"
  - "alpha_direction_selection"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Closed as blocked after the forward replacement, FINRA/FTD, SEC leadership/governance, and revision/contract data scan. No strategy code changed and no production/backtest behavior changed.

## Hypothesis

{result["hypothesis"]}

## Gate 1-4

- Gate 1: baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3: no filter added; baseline min survival `0.7925`.
- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; launch blocked.

## Decision

`{result["decision"]}`

## Why Blocked

{result["post_run_reflection"]["why_result_happened"]}

## Best Next Direction

{result["post_run_reflection"]["best_next_alpha_direction"]}

## Closeout

- Artifact: `{repo_rel(ARTIFACT_JSON)}`
- Before artifact: `{repo_rel(BEFORE_JSON)}`
- After artifact: `{repo_rel(AFTER_JSON)}`
- Markdown artifact: `{repo_rel(ARTIFACT_MD)}`
- Log: `{repo_rel(LOG_PATH)}`
- Runner: `{RUNNER_NAME}`
- No JavaScript was used.
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_PATH, {})
    if not isinstance(ticket, dict):
        ticket = {}
    ticket.update(
        {
            "status": "blocked",
            "completed_at": result["timestamp"],
            "decision": result["decision"],
            "result": {
                "accepted": False,
                "accepted_alpha": False,
                "decision": result["decision"],
                "artifact": repo_rel(ARTIFACT_JSON),
                "before_result_file": repo_rel(BEFORE_JSON),
                "after_result_file": repo_rel(AFTER_JSON),
                "log": repo_rel(LOG_PATH),
                "runner": RUNNER_NAME,
                "delta_metrics": result["delta_metrics"],
                "summary": result["post_run_reflection"]["why_result_happened"],
            },
            "gate4": result["gate4"],
            "post_run_reflection": result["post_run_reflection"],
        }
    )
    write_json(TICKET_PATH, ticket)


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    with path.open("a", encoding="utf-8") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def write_manifest(result: dict[str, Any]) -> None:
    files = {
        "runner": ROOT / RUNNER_NAME,
        "artifact_json": ARTIFACT_JSON,
        "before_json": BEFORE_JSON,
        "after_json": AFTER_JSON,
        "artifact_md": ARTIFACT_MD,
        "log": LOG_PATH,
        "card": CARD_PATH,
        "ticket": TICKET_PATH,
        "experiment_log": EXPERIMENT_LOG_PATH,
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
    write_json(MANIFEST_PATH, manifest)


def main() -> None:
    result = build_result()
    write_json(BEFORE_JSON, build_backtest_snapshot("before_baseline"))
    write_json(AFTER_JSON, build_backtest_snapshot("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_PATH, result)
    write_text(ARTIFACT_MD, build_markdown(result))
    update_ticket(result)
    write_text(CARD_PATH, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_PATH, result)
    write_manifest(result)
    print(json.dumps({"decision": result["decision"], "experiment_id": EXPERIMENT_ID}, sort_keys=True))


if __name__ == "__main__":
    main()
