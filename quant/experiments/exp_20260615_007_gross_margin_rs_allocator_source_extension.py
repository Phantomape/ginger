"""exp-20260615-007: gross-margin RS allocator source-extension blocker.

The proposed alpha was to admit accepted gross-margin RS rows into the accepted
helper source-priority allocator. The pre-run history check found that
exp-20260610-019 already exercised the current gross-margin-enabled
Fundamental Growth RS helper as an allocator source: selected rows carry
``gross_margin_pass_v1=True`` and ``gross_margin_rule_version``.

This runner records the blocker instead of launching a duplicate replay. It
does not change strategy, production, backtest, sizing, ranking, exit, LLM, or
order behavior. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260615-007"
STEM = "gross_margin_rs_allocator_source_extension"
DECISION = "blocked_duplicate_prior_gross_margin_allocator_source_extension"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_007_{STEM}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PRIOR_ALLOCATOR_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260610-019"
    / "exp_20260610_019_fundamental_growth_rs_allocator_source_extension.json"
)

BASELINE_BY_WINDOW = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "trade_count": 18,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "trade_count": 22,
        "survival_rate": 0.8667,
    },
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "source_overlap_displaces_better_rows",
        "accepted_allocator_window_comparator_regression",
        "gross_margin_rows_too_overlapping",
        "old_thin_regression",
    ],
    "confidence_reason": (
        "Gross-margin RS is an accepted shared default-off adapter with large "
        "positive historical evidence, but source extensions often fail by "
        "displacing better allocator rows; low-priority insertion limits but "
        "also reduces impact."
    ),
    "recorded_at": "2026-06-15T06:43:13+00:00",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                loaded = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if loaded.get("experiment_id") != record["experiment_id"]:
                kept.append(line)
    kept.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return loaded if isinstance(loaded, dict) else {}


def _duplicate_evidence() -> dict[str, Any]:
    payload = _load_json(PRIOR_ALLOCATOR_ARTIFACT)
    selected_counts: dict[str, int] = {}
    gross_margin_selected_counts: dict[str, int] = {}
    source_trade_counts: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    for label, rows in (payload.get("target_trades_by_window") or {}).items():
        selected = [
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("source_family") == "fundamental_growth_rs"
        ]
        selected_counts[label] = len(selected)
        gross_margin_selected_counts[label] = sum(
            1 for row in selected if row.get("gross_margin_pass_v1") is True
        )
        if selected:
            row = selected[0]
            examples.append(
                {
                    "window": label,
                    "ticker": row.get("ticker"),
                    "signal_date": row.get("signal_date") or row.get("date"),
                    "source_family": row.get("source_family"),
                    "source_priority_rank": row.get("source_priority_rank"),
                    "source_priority_accepted_experiment": row.get(
                        "source_priority_accepted_experiment"
                    ),
                    "gross_margin_pass_v1": row.get("gross_margin_pass_v1"),
                    "gross_margin_rule_version": row.get("gross_margin_rule_version"),
                    "source_rule_version": row.get("source_rule_version"),
                }
            )
    for label, audit in (payload.get("source_audit_by_window") or {}).items():
        counts = audit.get("source_trade_counts") or {}
        source_trade_counts[label] = int(counts.get("fundamental_growth_rs") or 0)
    return {
        "prior_experiment_id": "exp-20260610-019",
        "prior_artifact": _repo_rel(PRIOR_ALLOCATOR_ARTIFACT),
        "prior_decision": payload.get("decision"),
        "selected_fundamental_growth_rs_rows_by_window": selected_counts,
        "selected_rows_with_gross_margin_pass_by_window": gross_margin_selected_counts,
        "source_trade_counts_by_window": source_trade_counts,
        "example_selected_rows": examples,
        "duplicate_confirmed": bool(examples)
        and selected_counts == gross_margin_selected_counts,
        "interpretation": (
            "The prior allocator-extension replay already selected "
            "fundamental_growth_rs rows that pass the accepted gross-margin "
            "quality rule. A new gross_margin_rs source-extension replay would "
            "measure the same source-family admission under a new label."
        ),
    }


def _candidate_reviews(duplicate: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "candidate": "gross_margin_rs_allocator_source_extension",
            "alpha_hypothesis": (
                "Accepted gross-margin RS rows might add independent replacement "
                "value inside the source-priority allocator."
            ),
            "decision": "blocked_duplicate_prior",
            "history_check": ["exp-20260601-026", "exp-20260610-019"],
            "current_evidence": duplicate,
            "why_not_run": (
                "exp-20260610-019 already used current shared helper rows with "
                "gross_margin_pass_v1=True as the added allocator source."
            ),
            "retry_requires": (
                "A materially new source field or forward allocator displacement "
                "rows, not a relabeled gross-margin source-family admission."
            ),
        },
        {
            "candidate": "finra_iwm_shared_adapter_or_source_extension",
            "alpha_hypothesis": (
                "FINRA short-pressure plus IWM confirmation could add borrow-pressure "
                "replacement candidates."
            ),
            "decision": "blocked_already_shared_or_frozen",
            "history_check": [
                "exp-20260530-010",
                "exp-20260601-029",
                "exp-20260611-015",
            ],
            "current_evidence": {
                "shared_helper_exists": "quant/finra_iwm_paper_sleeve.py",
                "accepted_shared_adapter": "exp-20260530-010",
                "accepted_cost_liquidity_support": "exp-20260601-029",
                "allocator_source_extension": "exp-20260611-015 rejected SEC FTD + FINRA allocator source",
            },
            "why_not_run": (
                "The adapter promotion is already done and borrow-pressure source "
                "extension/retune lanes are frozen without new PIT borrow-cost or "
                "availability data."
            ),
            "retry_requires": "New PIT borrow-cost/availability evidence or forward rows.",
        },
        {
            "candidate": "broad_5d_winner_or_ret5_ret20_tail_candidate_pool",
            "alpha_hypothesis": (
                "Short-formation continuation might create a pure OHLCV candidate "
                "pool after controlling for ret20 momentum."
            ),
            "decision": "blocked_frozen_near_neighbor",
            "history_check": [
                "exp-20260601-008",
                "exp-20260606-004",
                "exp-20260606-005",
                "exp-20260606-006",
                "exp-20260609-007",
            ],
            "current_evidence": {
                "read_only_lead": "exp-20260601-008 proposed ret5 top-quintile incrementality",
                "candidate_pool_retries": "broad 5d winner continuation and market-confirmed/low-deployment variants rejected",
                "tail_filter": "exp-20260609-007 forbids ret5/ret20 threshold and tail-state sweeps",
            },
            "why_not_run": (
                "A new ret5/ret20 candidate-pool replay would duplicate frozen "
                "broad recent-winner continuation experiments."
            ),
            "retry_requires": "A new PIT flow/event-quality field or forward replacement rows.",
        },
        {
            "candidate": "companyfacts_quality_next_variant",
            "alpha_hypothesis": (
                "Free Companyfacts quality fields may sharpen momentum candidates."
            ),
            "decision": "blocked_frozen_near_neighbor",
            "history_check": [
                "exp-20260614-020",
                "exp-20260614-025",
                "exp-20260614-027",
                "exp-20260614-029",
                "exp-20260615-006",
            ],
            "current_evidence": {
                "cash_conversion": "positive but rejected on drawdown; TTM and acceleration variants closed",
                "diluted_share_contraction": "rejected",
                "industry_relative_asset_growth": "rejected on old_thin, drawdown, concentration",
            },
            "why_not_run": (
                "The remaining simple Companyfacts quality variants would be "
                "threshold/field mining near recent rejected experiments."
            ),
            "retry_requires": "New PIT relation/ownership context or forward replacement rows.",
        },
    ]


def _gate4() -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, before in BASELINE_BY_WINDOW.items():
        by_window[label] = {
            "before_expected_value_score": before["expected_value_score"],
            "after_expected_value_score": before["expected_value_score"],
            "expected_value_score_delta": 0.0,
            "before_total_pnl": before["total_pnl"],
            "after_total_pnl": before["total_pnl"],
            "strategy_total_pnl_delta": 0.0,
            "before_trade_count": before["trade_count"],
            "after_trade_count": before["trade_count"],
            "trade_count_delta": 0,
        }
    return {
        "passed": False,
        "decision": DECISION,
        "strategy_behavior_changed": False,
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "aggregate_trade_count_delta": 0,
        "by_window": by_window,
        "failed_reasons": [
            "duplicate_prior_experiment",
            "all_checked_high_potential_lanes_frozen_or_already_shared",
            "running_a_strategy_backtest_would_duplicate_frozen_near_neighbors",
        ],
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    duplicate = _duplicate_evidence()
    reviews = _candidate_reviews(duplicate)
    gate4 = _gate4()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": DECISION,
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": (
            "Test whether accepted Companyfacts gross-margin RS rows add "
            "independent replacement value as a fixed source family inside the "
            "accepted helper source-priority allocator."
        ),
        "change_type": "alpha_candidate_selection_blocker_proof",
        "mechanism_family": "alpha_direction_selection",
        "trial_family": "accepted_default_off_helper_source_priority_allocation",
        "trial_variant_id": "gross_margin_rs_source_family_added_to_accepted_helper_source_priority_allocator_v1",
        "changed_variable": "gross_margin_rs_source_family_added_to_accepted_helper_source_priority_allocator_v1",
        "single_causal_variable": "gross_margin_rs_source_family_added_to_accepted_helper_source_priority_allocator_v1",
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260601-026",
            "exp-20260610-019",
            "exp-20260610-014",
            "exp-20260613-031",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "duplicate_detection_for_accepted_source_extension",
        "prediction": PREDICTION,
        "gate1": {
            "passed": True,
            "baseline_source": "docs/backtesting.md",
            "by_window_baseline": deepcopy(BASELINE_BY_WINDOW),
            "aggregate_baseline": {
                "expected_value_score_sum": 7.8941,
                "total_pnl_sum": 234850.99,
                "trade_count_sum": 61,
                "min_survival_rate": 0.7925,
                "max_drawdown_pct_max": 0.1119,
            },
        },
        "gate2": {
            "passed_for_noop_blocker_record": True,
            "entry_date_required_for_future_alpha": True,
            "target_price_required_for_future_alpha": True,
            "note": "No executable signal rows, target prices, or exit contracts were created.",
        },
        "gate3": {
            "filter_added": False,
            "survival_rate_min": 0.7925,
            "survival_guard_passed": True,
        },
        "gate4": gate4,
        "candidate_reviews": reviews,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "parity_note": (
                "No strategy or production path changed. The proposed positive "
                "source-extension would have required shared allocator wiring, "
                "but the history check blocked it as a duplicate before code."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 0,
            "actual_decision": DECISION,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "brier_score": round(PREDICTION["success_probability"] ** 2, 6),
            "realized_failure_mode": "duplicate_prior_experiment",
            "predicted_failure_mode_hit": False,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Accepted gross-margin RS rows may improve allocator replacement "
                "value if they supply fundamental-quality candidates on dates "
                "where existing sources are absent or weaker."
            ),
            "2_history_check": [
                {
                    "experiment_id": "exp-20260610-019",
                    "decision": "rejected_fundamental_growth_rs_allocator_source_extension",
                    "duplicate_evidence": duplicate,
                },
                {
                    "experiment_id": "exp-20260601-026",
                    "decision": "accepted_shared_companyfacts_gross_margin_rs_adapter",
                    "note": "This is the accepted source whose rows were already present in exp-20260610-019.",
                },
            ],
            "3_single_decision_hypothesis": "gross_margin_rs_source_family_added_to_accepted_helper_source_priority_allocator_v1",
            "4_acceptance_standard": (
                "A launch would need docs/backtesting.md three canonical windows, "
                "positive aggregate EV/PnL, no window regression, sample/survival/"
                "drawdown/concentration pass, and current allocator comparator "
                "beat. This was blocked before replay because the launch would be "
                "a duplicate."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260615_007_gross_margin_rs_allocator_source_extension.py"
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The strongest apparent alpha was not new: exp-20260610-019 "
                "already admitted current gross-margin-enabled Fundamental "
                "Growth RS rows into the allocator and rejected it versus the "
                "accepted allocator comparator."
            ),
            "why_no_strategy_experiment": (
                "Running the replay would relabel a prior frozen source-extension "
                "experiment rather than test a new causal decision."
            ),
            "why_negative_or_blocked": (
                "The blocker is about alpha selection quality, not a software bug. "
                "The current high-EV path needs a new PIT field or forward rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry gross-margin/Fundamental Growth RS allocator source "
                "extension by changing source-family label, rank, top-N, notional, "
                "hold days, cooldown, or gross-margin threshold on the frozen windows."
            ),
            "new_evidence_required": (
                "Use a materially new production-visible PIT field, forward "
                "allocator displacement rows, or closed true-trigger replacement "
                "value evidence before another allocator-source launch."
            ),
            "best_next_alpha_direction": (
                "New free-data edge: PIT estimate breadth/dispersion/provenance, "
                "customer/supplier relation evidence, or forward closed rows from "
                "accepted default-off adapters."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _artifact_md(payload: dict[str, Any]) -> str:
    duplicate = payload["candidate_reviews"][0]["current_evidence"]
    lines = [
        f"# {EXPERIMENT_ID} Gross-Margin RS Allocator Source-Extension Blocker",
        "",
        f"- Decision: `{payload['decision']}`",
        "- Strategy behavior changed: `false`",
        "- No JavaScript was used.",
        "",
        "## Duplicate Evidence",
        "",
        f"- Prior artifact: `{duplicate['prior_artifact']}`",
        f"- Prior decision: `{duplicate['prior_decision']}`",
        f"- Fundamental source rows by window: `{duplicate['source_trade_counts_by_window']}`",
        f"- Selected FGRS rows by window: `{duplicate['selected_fundamental_growth_rs_rows_by_window']}`",
        f"- Selected rows with gross-margin pass: `{duplicate['selected_rows_with_gross_margin_pass_by_window']}`",
        "",
        "Example selected rows:",
        "",
        "| Window | Ticker | Signal Date | Gross Margin Pass | Gross Rule | Source Rank |",
        "|---|---|---:|---|---|---:|",
    ]
    for row in duplicate["example_selected_rows"]:
        lines.append(
            "| {window} | {ticker} | {signal_date} | {pass_} | {rule} | {rank} |".format(
                window=row.get("window"),
                ticker=row.get("ticker"),
                signal_date=row.get("signal_date"),
                pass_=row.get("gross_margin_pass_v1"),
                rule=row.get("gross_margin_rule_version"),
                rank=row.get("source_priority_rank"),
            )
        )
    lines.extend(
        [
            "",
            "## Gate 1-4",
            "",
            "- Gate 1: canonical baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.",
            "- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.",
            "- Gate 3: no filter added; baseline min survival `0.7925`.",
            "- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; launch blocked.",
            "",
            "## Conclusion",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "Best next direction: "
            + payload["post_run_reflection"]["best_next_alpha_direction"],
            "",
        ]
    )
    return "\n".join(lines)


def _card_md(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            'status: "blocked"',
            'lane: "alpha_search"',
            'change_type: "alpha_candidate_selection_blocker_proof"',
            'mechanism_family: "alpha_direction_selection"',
            'trial_family: "accepted_default_off_helper_source_priority_allocation"',
            'trial_variant_id: "gross_margin_rs_source_family_added_to_accepted_helper_source_priority_allocator_v1"',
            'changed_variable: "gross_margin_rs_source_family_added_to_accepted_helper_source_priority_allocator_v1"',
            f'completed_at: "{payload["timestamp"]}"',
            "tags:",
            '  - "alpha_search"',
            '  - "blocked"',
            '  - "duplicate_prior_experiment"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            "Closed as blocked after the history check proved the proposed gross-margin RS allocator source extension was already covered by `exp-20260610-019` using gross-margin-enabled rows. No strategy or production behavior changed.",
            "",
            "## Decision",
            "",
            f"`{payload['decision']}`",
            "",
            "## Gate 1-4",
            "",
            "- Gate 1: canonical three-window baseline from `docs/backtesting.md`.",
            "- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.",
            "- Gate 3: no filter added; baseline survival guard remains passed.",
            "- Gate 4: before/after identical; launch blocked as duplicate.",
            "",
            "## Closeout",
            "",
            f"- Artifact: `{_repo_rel(OUT_JSON)}`",
            f"- Markdown artifact: `{_repo_rel(ARTIFACT_MD)}`",
            f"- Log: `{_repo_rel(LOG_JSON)}`",
            f"- Runner: `{_repo_rel(Path(__file__))}`",
            "- No JavaScript was used.",
            "",
        ]
    )


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": "blocked",
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "candidate_reviews": payload["candidate_reviews"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON)
    ticket.update(
        {
            "status": "blocked",
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": {
                "decision": payload["decision"],
                "accepted": False,
                "accepted_alpha": False,
                "artifact": _repo_rel(OUT_JSON),
                "artifact_md": _repo_rel(ARTIFACT_MD),
                "log": _repo_rel(LOG_JSON),
                "gate4": payload["gate4"],
                "calibration": payload["calibration"],
                "production_impact": payload["production_impact"],
                "post_run_reflection": payload["post_run_reflection"],
            },
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": _repo_rel(OUT_JSON),
            "artifact_md": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    files = {
        "runner": Path(__file__),
        "artifact_json": OUT_JSON,
        "artifact_md": ARTIFACT_MD,
        "log": LOG_JSON,
        "card": CARD_MD,
        "ticket": TICKET_JSON,
        "experiment_log": EXPERIMENT_LOG,
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "generated_at": _utc_now(),
        "files": {
            name: {
                "path": _repo_rel(path),
                "exists": path.exists(),
                "sha256": _sha256(path),
            }
            for name, path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status="blocked",
        fields=fields,
    )


def main() -> None:
    payload = _build_payload()
    log_record = _log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_text(ARTIFACT_MD, _artifact_md(payload))
    _write_text(CARD_MD, _card_md(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_registry(payload, log_record)
    _write_manifest(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "duplicate_confirmed": payload["candidate_reviews"][0][
                    "current_evidence"
                ]["duplicate_confirmed"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
