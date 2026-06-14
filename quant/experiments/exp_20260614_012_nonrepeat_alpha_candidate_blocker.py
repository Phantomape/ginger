from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260614-012"
SLUG = "nonrepeat_alpha_candidate_blocker"
RUNNER_NAME = "quant/experiments/exp_20260614_012_nonrepeat_alpha_candidate_blocker.py"

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / "nonrepeat_alpha_candidate_blocker.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_PATH = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_PATH = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_PATH = ROOT / "docs" / "experiment_log.jsonl"


CANONICAL_BASELINE = {
    "source": "docs/backtesting.md",
    "aggregate": {
        "expected_value_score_sum": 7.8941,
        "total_pnl_sum": 234850.99,
        "trade_count_sum": 61,
        "min_survival_rate": 0.7925,
        "max_drawdown_pct_max": 0.1119,
    },
    "by_window": {
        "late_strong": {
            "start": "2025-10-23",
            "end": "2026-04-21",
            "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            "expected_value_score": 5.1628,
            "sharpe_daily": 4.41,
            "total_pnl": 117072.92,
            "strategy_total_return_pct": 1.1707,
            "max_drawdown_pct": 0.0665,
            "win_rate": 0.8333,
            "trade_count": 18,
            "survival_rate": 0.8039,
        },
        "mid_weak": {
            "start": "2025-04-23",
            "end": "2025-10-22",
            "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            "expected_value_score": 2.1402,
            "sharpe_daily": 2.74,
            "total_pnl": 78110.11,
            "strategy_total_return_pct": 0.7811,
            "max_drawdown_pct": 0.1119,
            "win_rate": 0.5238,
            "trade_count": 21,
            "survival_rate": 0.7925,
        },
        "old_thin": {
            "start": "2024-10-02",
            "end": "2025-04-22",
            "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            "expected_value_score": 0.5911,
            "sharpe_daily": 1.49,
            "total_pnl": 39667.96,
            "strategy_total_return_pct": 0.3967,
            "max_drawdown_pct": 0.1001,
            "win_rate": 0.4091,
            "trade_count": 22,
            "survival_rate": 0.8667,
        },
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def experiment_log(eid: str) -> dict[str, Any]:
    return read_json(ROOT / "experiments" / "logs" / f"{eid}.json", {})


def summarize_recent_history() -> list[dict[str, Any]]:
    ids = [
        "exp-20260614-003",
        "exp-20260614-004",
        "exp-20260614-005",
        "exp-20260614-006",
        "exp-20260614-007",
        "exp-20260614-009",
        "exp-20260614-010",
        "exp-20260614-011",
        "exp-20260605-015",
        "exp-20260605-016",
        "exp-20260613-031",
    ]
    rows: list[dict[str, Any]] = []
    for eid in ids:
        obj = experiment_log(eid)
        rows.append(
            {
                "experiment_id": eid,
                "decision": obj.get("decision") or obj.get("status"),
                "changed_variable": obj.get("changed_variable") or obj.get("single_causal_variable"),
                "reason": obj.get("rejection_reason")
                or obj.get("blocked_reason")
                or obj.get("post_run_reflection"),
            }
        )
    return rows


def coverage_snapshot() -> dict[str, Any]:
    estimate = read_json(ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260613.json", {})
    form4 = read_json(ROOT / "data" / "non_ohlcv" / "form4_backfill_summary_20241002_20260502.json", {})
    platform = read_json(ROOT / "data" / "paper_sleeves" / "platform_rs20_no_gap" / "summary.json", {})
    sec10k = read_json(ROOT / "data" / "paper_sleeves" / "sec_10k_liquidity" / "summary.json", {})
    forward_activation = experiment_log("exp-20260614-003").get("activation_summary", {})
    return {
        "estimate_revision_20260613": {
            "row_count": estimate.get("row_count"),
            "estimate_revision_usable_rows": estimate.get("estimate_revision_usable_rows"),
            "up_revision_rows": estimate.get("up_revision_rows"),
            "matched_candidate_rows": estimate.get("matched_candidate_rows"),
            "candidate_match_rate": estimate.get("candidate_match_rate"),
            "pit_safe_rate": estimate.get("pit_safe_rate"),
            "source": "data/non_ohlcv/estimate_revision_ledger_summary_20260613.json",
        },
        "form4_backfill_20241002_20260502": {
            "rows_written": form4.get("rows_written"),
            "open_market_purchase_count": form4.get("open_market_purchase_count"),
            "transaction_code_p_count": (form4.get("transaction_code_counts") or {}).get("P"),
            "excluded_external_issuer_rows": form4.get("excluded_external_issuer_rows"),
            "tickers_mapped": form4.get("tickers_mapped"),
            "source": "data/non_ohlcv/form4_backfill_summary_20241002_20260502.json",
        },
        "platform_rs20_no_gap_forward_watch": {
            "candidate_count": platform.get("candidate_count"),
            "ledger_row_count": platform.get("ledger_row_count"),
            "source": "data/paper_sleeves/platform_rs20_no_gap/summary.json",
        },
        "sec_10k_liquidity_forward_watch": {
            "candidate_count": sec10k.get("candidate_count"),
            "ledger_row_count": sec10k.get("ledger_row_count"),
            "ten_k_event_count": sec10k.get("ten_k_event_count"),
            "source": "data/paper_sleeves/sec_10k_liquidity/summary.json",
        },
        "accepted_adapter_forward_activation": {
            "activation_ready_count": forward_activation.get("activation_ready_count"),
            "activation_ready_sleeves": forward_activation.get("activation_ready_sleeves"),
            "top_forward_rows": forward_activation.get("top_forward_rows", [])[:5],
            "source": "experiments/logs/exp-20260614-003.json",
        },
    }


def candidate_reviews(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    estimate = coverage["estimate_revision_20260613"]
    form4 = coverage["form4_backfill_20241002_20260502"]
    platform = coverage["platform_rs20_no_gap_forward_watch"]
    sec10k = coverage["sec_10k_liquidity_forward_watch"]
    forward = coverage["accepted_adapter_forward_activation"]
    return [
        {
            "candidate": "analyst_estimate_revision_pead",
            "alpha_hypothesis": "Upward estimate drift after earnings should identify expectation underreaction and expand the candidate pool with a non-price data edge.",
            "history_check": [
                "exp-20260526-031",
                "exp-20260604-020",
                "exp-20260610-025",
                "exp-20260614-005",
            ],
            "current_evidence": estimate,
            "decision": "blocked_data_coverage_too_thin",
            "why_not_run": "Only 53 usable prior-event rows, 1 up-revision row, and 0 matched candidate rows are present for the latest ledger; a three-window Gate 1-4 alpha would be mostly empty.",
            "retry_requires": "PIT estimate breadth, dispersion, and revision rows matched to candidates across all canonical windows.",
        },
        {
            "candidate": "accepted_default_off_forward_activation",
            "alpha_hypothesis": "A mature default-off paper helper with closed true-trigger replacement value could be promoted without adding frozen historical filters.",
            "history_check": [
                "exp-20260608-021",
                "exp-20260611-022",
                "exp-20260612-019",
                "exp-20260614-003",
            ],
            "current_evidence": forward,
            "decision": "blocked_no_activation_ready_sleeve",
            "why_not_run": "The latest activation audit found 0 activation-ready sleeves; low-deployment ETF rows were off-trigger observations, not true-trigger closed rows.",
            "retry_requires": "At least 20 closed true-trigger forward rows for one sleeve with replacement value versus cash, SPY, and QQQ.",
        },
        {
            "candidate": "sec_financial_report_next_extension",
            "alpha_hypothesis": "Financial-report filing drift may have durable edge when combined with a new filing-quality or evidence-span discriminator.",
            "history_check": [
                "exp-20260614-004",
                "exp-20260614-009",
                "exp-20260612-005",
                "exp-20260611-017",
            ],
            "current_evidence": {
                "accepted_comparator": "exp-20260614-004 accepted RS20 leader 1.15x default-off support",
                "allocator_extension": "exp-20260614-009 rejected versus accepted allocator",
                "platform_rs20_no_gap": platform,
                "sec_10k_liquidity": sec10k,
            },
            "decision": "blocked_near_neighbor_or_empty_forward_watch",
            "why_not_run": "The accepted SEC RS20 helper should not be retuned, the allocator source extension regressed, and two obvious daily watches have 0 candidates.",
            "retry_requires": "A materially new PIT SEC text/evidence-span field with replayable rows, not another RS threshold or source-priority sweep.",
        },
        {
            "candidate": "form4_insider_or_external_issuer_edge",
            "alpha_hypothesis": "Open-market insider buying or external-issuer ownership relationships may identify informed demand beyond price-only signals.",
            "history_check": [
                "exp-20260613-026",
                "exp-20260609-025",
                "exp-20260610-006",
                "exp-20260612-020",
                "exp-20260613-017",
            ],
            "current_evidence": form4,
            "decision": "blocked_frozen_near_neighbor",
            "why_not_run": "The backfill has data, but recent Form4 direct, role, ownership, withholding, sale-pressure, and overlap variants have already been rejected or frozen.",
            "retry_requires": "A new field such as forward ownership-normalized external-issuer relation mapping, not another transaction-code or threshold variant.",
        },
        {
            "candidate": "companyfacts_peer_or_quality_extension",
            "alpha_hypothesis": "Fresh fundamental growth with peer confirmation could add broad candidate-pool replacement value.",
            "history_check": [
                "exp-20260605-014",
                "exp-20260605-015",
                "exp-20260605-016",
                "exp-20260613-031",
            ],
            "current_evidence": {
                "positive_replay_lead": "exp-20260605-014",
                "shared_adapter_promotion": "exp-20260605-015 rejected on window regression and drawdown drift",
                "peer_price_absorption": "exp-20260605-016 rejected",
                "operating_efficiency": "exp-20260613-031 rejected versus accepted low-liability comparator",
            },
            "decision": "blocked_frozen_companyfacts_neighborhood",
            "why_not_run": "The broad Companyfacts family already has accepted low-liability/recency/low-volume helpers and rejected nearby peer/quality variants.",
            "retry_requires": "New free-data relation or forward paper rows; do not sweep growth, peer, cooldown, or liability thresholds on frozen windows.",
        },
        {
            "candidate": "accepted_allocator_source_arbitration",
            "alpha_hypothesis": "Same-day source conflicts could be improved by choosing the ex-ante source most likely to outperform.",
            "history_check": [
                "exp-20260613-003",
                "exp-20260613-033",
                "exp-20260614-009",
                "exp-20260614-010",
                "exp-20260614-011",
            ],
            "current_evidence": {
                "oracle_gap": "exp-20260613-003 observed a source-choice gap, but it used future PnL",
                "recent_ex_ante_tests": "correlation crowding, SEC source extension, market-breadth tail, and source-pair router all failed accepted-allocator comparator tests",
            },
            "decision": "blocked_ex_ante_fields_failed",
            "why_not_run": "The oracle gap is real but recent production-visible ex-ante fields failed to harvest it; another source-priority parameter sweep would be a duplicate.",
            "retry_requires": "New forward source-conflict rows or a new relation/provenance field that was not present in the failed routers.",
        },
    ]


def gate4_noop() -> dict[str, Any]:
    return {
        "strategy_behavior_changed": False,
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "aggregate_trade_count_delta": 0,
        "by_window": {
            name: {
                "before_expected_value_score": row["expected_value_score"],
                "after_expected_value_score": row["expected_value_score"],
                "expected_value_score_delta": 0.0,
                "before_total_pnl": row["total_pnl"],
                "after_total_pnl": row["total_pnl"],
                "strategy_total_pnl_delta": 0.0,
                "before_trade_count": row["trade_count"],
                "after_trade_count": row["trade_count"],
                "trade_count_delta": 0,
            }
            for name, row in CANONICAL_BASELINE["by_window"].items()
        },
        "passed": False,
        "failed_reasons": [
            "no_valid_nonrepeat_candidate",
            "required_new_data_or_forward_rows_absent",
            "running_a_strategy_backtest_would_duplicate_frozen_near_neighbors",
        ],
    }


def build_result() -> dict[str, Any]:
    coverage = coverage_snapshot()
    reviews = candidate_reviews(coverage)
    now = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "blocked",
        "accepted": False,
        "accepted_alpha": False,
        "decision": "blocked_no_valid_nonrepeat_alpha_candidate_after_latest_history_scan",
        "lane": "alpha_search",
        "change_type": "alpha_candidate_selection_blocker_proof",
        "changed_variable": "highest_priority_nonrepeat_alpha_candidate_selection_v2",
        "hypothesis": "Choose the strongest non-repeat production-visible alpha direction after the latest June 14 experiments; only launch if it has PIT/free-data coverage across the canonical three windows and is not a frozen near-neighbor.",
        "pre_run_questions": {
            "1_alpha_hypothesis": "The next viable alpha should expand or improve the candidate pool with a new free PIT data edge or mature default-off paper evidence.",
            "2_history_check": summarize_recent_history(),
            "3_single_decision_hypothesis": "highest_priority_nonrepeat_alpha_candidate_selection_v2",
            "4_acceptance_standard": "Launch only if the candidate is non-repeat, has three-window PIT/free-data coverage, can satisfy Gate 1-4, and has a shared production/backtest parity path if positive.",
            "5_reproducibility": f"See {ARTIFACT_JSON.relative_to(ROOT).as_posix()} and {ARTIFACT_MD.relative_to(ROOT).as_posix()}.",
        },
        "prediction": {
            "success_probability": 0.08,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "all_high_potential_lanes_frozen",
                "data_coverage_too_thin",
                "no_new_production_visible_pit_field",
            ],
            "confidence_reason": "After exp-20260614-005, the newly tested relation, SEC allocator, tail-state, and source-router lanes also failed; remaining promising estimate/forward lanes lack rows.",
            "recorded_at": now,
        },
        "gate1": {
            "baseline_source": "docs/backtesting.md",
            "aggregate_baseline": CANONICAL_BASELINE["aggregate"],
            "by_window_baseline": CANONICAL_BASELINE["by_window"],
        },
        "gate2": {
            "passed_for_noop_blocker_record": True,
            "entry_date_required_for_future_alpha": True,
            "target_price_required_for_future_alpha": True,
            "note": "No executable signal rows, target prices, or exit contracts were created in this blocker record.",
        },
        "gate3": {
            "filter_added": False,
            "survival_rate_min": CANONICAL_BASELINE["aggregate"]["min_survival_rate"],
            "survival_guard_passed": True,
        },
        "gate4": gate4_noop(),
        "candidate_reviews": reviews,
        "coverage_snapshot": coverage,
        "production_impact": {
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "parity_note": "No strategy or production path changed. A positive future alpha must be shared-paper-first with historical replay plus daily default-off snapshot parity.",
        },
        "calibration": {
            "actual_decision": "blocked_no_valid_nonrepeat_alpha_candidate_after_latest_history_scan",
            "actual_success": 0,
            "predicted_success_probability": 0.08,
            "brier_score": round((0.08 - 0.0) ** 2, 6),
            "expected_ev_delta": 0.0,
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "realized_failure_mode": "recent_ex_ante_lanes_failed_and_remaining_data_lanes_are_too_thin",
            "predicted_failure_mode_hit": True,
        },
        "post_run_reflection": {
            "why_result_happened": "The blocker is stronger than exp-20260614-005 because the intervening relation, SEC allocator, market-breadth tail, and source-pair router experiments also failed accepted comparators, while analyst revision and forward activation data remain too sparse.",
            "why_no_strategy_experiment": "A fresh strategy run would either retest a frozen near-neighbor or operate on empty/insufficient rows, making the Gate 4 evidence unreliable.",
            "why_negative_or_blocked": "The negative conclusion is about alpha selection quality, not a software bug: current local evidence says the next high-EV work needs a new free PIT field or forward closed rows.",
            "forbidden_near_neighbor_retry": "Do not sweep SEC RS20 thresholds/scalars, accepted allocator source priority, source-pair history, market breadth tail buckets, Form4 transaction thresholds, Companyfacts peer/quality thresholds, calendar/TOM rules, or analyst revision filters on the current sparse rows.",
            "new_evidence_required": "Collect new free PIT estimate breadth/dispersion/provenance rows, SEC evidence-span semantics, customer/supplier or external-issuer relation mappings, or at least 20 closed true-trigger forward rows before another Gate 1-4 alpha launch.",
            "best_next_alpha_direction": "Build a new production-visible free-data edge, with priority on PIT estimate breadth/dispersion or SEC evidence-span fields; do not optimize current price/allocator thresholds.",
        },
        "artifact": ARTIFACT_JSON.relative_to(ROOT).as_posix(),
        "artifact_md": ARTIFACT_MD.relative_to(ROOT).as_posix(),
        "card": CARD_PATH.relative_to(ROOT).as_posix(),
        "log": LOG_PATH.relative_to(ROOT).as_posix(),
        "runner": RUNNER_NAME,
        "anti_js": "No JavaScript was used.",
    }


def build_markdown(result: dict[str, Any]) -> str:
    reviews = result["candidate_reviews"]
    lines = [
        f"# {EXPERIMENT_ID} Nonrepeat Alpha Candidate Blocker",
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
        f"- Gate 1 baseline: `docs/backtesting.md`, aggregate EV `{CANONICAL_BASELINE['aggregate']['expected_value_score_sum']}`, PnL `${CANONICAL_BASELINE['aggregate']['total_pnl_sum']}`.",
        "- Gate 2 fields: no executable rows created; future alpha still requires `entry_date` and `target_price`.",
        f"- Gate 3 survival: no filter added; baseline min survival `{CANONICAL_BASELINE['aggregate']['min_survival_rate']}`.",
        "- Gate 4: no behavior changed; all three windows are identical before/after and the alpha launch is blocked.",
        "",
        "| Window | EV Before | EV After | PnL Before | PnL After | Trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in result["gate4"]["by_window"].items():
        lines.append(
            f"| `{name}` | {row['before_expected_value_score']:.4f} | {row['after_expected_value_score']:.4f} | "
            f"${row['before_total_pnl']:.2f} | ${row['after_total_pnl']:.2f} | {row['before_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Reviews",
            "",
            "| Candidate | Decision | Why not run now |",
            "| --- | --- | --- |",
        ]
    )
    for item in reviews:
        lines.append(
            f"| `{item['candidate']}` | `{item['decision']}` | {item['why_not_run']} |"
        )
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
            f"- JSON artifact: `{result['artifact']}`",
            f"- Log: `{result['log']}`",
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
change_type: "alpha_candidate_selection_blocker_proof"
mechanism_family: "alpha_direction_selection"
trial_family: "nonrepeat_alpha_candidate_launch"
trial_variant_id: "blocker_after_20260614_recent_rejections"
changed_variable: "highest_priority_nonrepeat_alpha_candidate_selection_v2"
completed_at: "{now}"
tags:
  - "alpha_search"
  - "blocked"
  - "alpha_direction_selection"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Closed as blocked after the latest history scan. No strategy code changed and no production/backtest behavior changed.

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

- Artifact: `{result["artifact"]}`
- Markdown artifact: `{result["artifact_md"]}`
- Log: `{result["log"]}`
- Runner: `{RUNNER_NAME}`
- No JavaScript was used.
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_PATH, {})
    ticket.update(
        {
            "status": "blocked",
            "completed_at": result["timestamp"],
            "decision": result["decision"],
            "result": {
                "accepted": False,
                "accepted_alpha": False,
                "decision": result["decision"],
                "artifact": result["artifact"],
                "log": result["log"],
                "runner": RUNNER_NAME,
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
            key: {
                "path": value.relative_to(ROOT).as_posix(),
                "exists": value.exists(),
                "sha256": sha256(value),
            }
            for key, value in files.items()
        },
    }
    write_json(MANIFEST_PATH, manifest)


def main() -> None:
    result = build_result()
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_PATH, result)
    write_text(ARTIFACT_MD, build_markdown(result))
    update_ticket(result)
    write_text(CARD_PATH, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_PATH, result)
    write_manifest(result)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": result["decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()
