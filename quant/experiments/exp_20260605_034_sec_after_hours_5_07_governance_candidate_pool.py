"""exp-20260605-034: SEC after-hours 8-K Item 5.07 governance pool.

Replay-only alpha search. It tests one production-visible SEC timing source:
after-hours Item 5.07 shareholder-vote 8-K filings whose first usable trading
day confirms trend/relative-strength quality, using the same delayed next-open
paper entry harness as the prior after-hours 8-K scouts.

No production adapter, live order path, shared policy, ranking, sizing, exits,
LLM/news path, or watchlist is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260605_019_sec_after_hours_8k_trend_candidate_pool as base


EXP_ID = "exp-20260605-034"
STEM = "sec_after_hours_5_07_governance_candidate_pool"
TRIAL_FAMILY = "sec_after_hours_5_07_governance_candidate_pool"
TRIAL_VARIANT_ID = "sec_after_hours_5_07_shareholder_vote_top1_delayed_entry_v1"
CHANGED_VARIABLE = "sec_after_hours_8k_item_5_07_shareholder_vote_trend_candidate_source_v1"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_034_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. It uses historical PIT-safe "
        "SEC filing feature rows, observed accepted_datetime timing, first "
        "usable trading-day OHLCV available after the close, and a delayed "
        "next-open paper entry. A positive result would still require a "
        "separate shared default-off SEC Item 5.07 governance adapter and "
        "focused parity tests before any report queue, candidate priority, "
        "watchlist, sizing, or order surface could change."
    ),
}


def _load_feature_rows_skip_malformed() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    source_files = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_features_*.jsonl"))
    raw_rows_scanned = 0
    malformed_rows_skipped = 0
    malformed_files: Counter[str] = Counter()
    by_window_all: Counter[str] = Counter()
    for path in source_files:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw_rows_scanned += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    malformed_rows_skipped += 1
                    malformed_files[path.name] += 1
                    continue
                usable = str(row.get("usable_trade_date") or "")[:10]
                window = base._window_name(usable)
                if window is None:
                    continue
                key = (
                    str(row.get("ticker") or "").upper(),
                    str(row.get("source_accession") or row.get("accession_number") or ""),
                    usable,
                    str(row.get("eight_k_item_type") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                by_window_all[window] += 1
                rows.append(row)
    rows.sort(
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("source_accession") or ""),
        )
    )
    return rows, {
        "source_file_count": len(source_files),
        "raw_rows_scanned": raw_rows_scanned,
        "malformed_rows_skipped": malformed_rows_skipped,
        "malformed_files": dict(sorted(malformed_files.items())),
        "unique_rows_in_canonical_windows": len(rows),
        "unique_rows_by_window": dict(sorted(by_window_all.items())),
    }


def _apply_config() -> None:
    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_JSON = BEFORE_JSON
    base.AFTER_JSON = AFTER_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.ARTIFACT_MD = ARTIFACT_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.INCLUDED_ITEM_CODES = frozenset({"5.07"})
    base.EXCLUDED_ITEM_PREFIXES = ("2.02", "2.03", "3.02", "4.01", "5.02")
    base._load_feature_rows = _load_feature_rows_skip_malformed
    base.__file__ = __file__
    base._gate4 = _governance_gate4
    base._write_artifact = _write_artifact


def _governance_gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate = _ORIGINAL_GATE4(aggregate_comparison, results, target_summary)
    if gate["passed"]:
        gate["decision"] = "positive_replay_lead_not_promoted_requires_shared_sec_5_07_adapter"
        gate["status"] = "observed_only"
        gate["rationale"] = (
            "The after-hours SEC Item 5.07 shareholder-vote source improved "
            "all canonical windows and passed sample, drawdown, survival, "
            "and concentration guards. It remains replay-only until a shared "
            "default-off adapter and parity tests are implemented."
        )
    else:
        gate["decision"] = "rejected_sec_after_hours_5_07_governance_candidate_pool"
        gate["status"] = "rejected"
        gate["rationale"] = (
            "One or more Gate 4 checks failed, so this after-hours SEC "
            "Item 5.07 shareholder-vote candidate source is not retained or "
            "promoted."
        )
    return gate


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    payload["experiment_id"] = EXP_ID
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["rule_version"] = CHANGED_VARIABLE
    payload["status"] = gate4["status"]
    payload["decision"] = gate4["decision"]
    payload["preflight"] = {
        "alpha_hypothesis": (
            "After-hours SEC 8-K Item 5.07 shareholder-vote filings with "
            "prior trend and relative-strength confirmation may add a "
            "PIT-safe default-off governance candidate source without "
            "expanding the core universe noisily."
        ),
        "category": "entry_candidate_pool",
        "playbook_alignment": (
            "Uses a free, production-visible SEC item/timing field and tests "
            "a distinct governance filing-event candidate-pool source instead "
            "of LLM soft-ranking, Companyfacts peer retunes, FTD/FINRA "
            "retunes, post-earnings support stack retunes, or broad "
            "OHLCV-only pattern mining."
        ),
        "nearby_prior_experiments": {
            "exp-20260504-039": (
                "Accepted a mixed SEC governance/procedural event overlay; "
                "this tests only the after-hours Item 5.07 shareholder-vote "
                "delayed-entry source."
            ),
            "exp-20260521-005": "Positive governance source-quality scalar scout inside accepted event bundle.",
            "exp-20260521-006": "Promoted governance source-quality scalar into the shared default-off event adapter.",
            "exp-20260605-019": "Rejected after-hours operational 8-K timing source.",
            "exp-20260605-020": "Rejected after-hours Item 5.02 leadership timing source.",
        },
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": base.MIN_TARGET_TRADES,
            "minimum_target_windows": base.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": base.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": base.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": base.MAX_POSITIVE_HHI,
        },
    }
    payload["parameters"]["included_item_codes"] = ["5.07"]
    payload["parameters"]["excluded_item_prefixes"] = list(base.EXCLUDED_ITEM_PREFIXES)
    payload["parameters"]["sec_item_family"] = "8-K Item 5.07 shareholder_vote"
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["next_action"] = (
        "If positive, build a shared default-off SEC Item 5.07 governance "
        "adapter with after-hours timing, delayed-entry semantics, and parity "
        "tests before promotion."
        if gate4["passed"]
        else "Do not retune nearby SEC Item 5.07 after-hours timing, trend/RS, "
        "or delayed-entry thresholds on this frozen sample; pivot to a "
        "different free-data candidate-pool mechanism or forward replacement rows."
    )
    return payload


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC After-Hours Item 5.07 Governance Candidate Pool",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        base._window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Rule",
            "",
            (
                "Select PIT-safe SEC 8-K feature rows with Item 5.07, exclude "
                "earnings, financing, auditor-change, and Item 5.02 leadership "
                "co-items, require `accepted_datetime` at or after 20:00, "
                "require first usable trading-day close-location >= "
                f"{base.MIN_SIGNAL_CLOSE_LOCATION}, and require nonnegative "
                "20-day excess return versus SPY. Entry is delayed to the "
                "next open after that close is known."
            ),
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_034_sec_after_hours_5_07_governance_candidate_pool.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    _apply_config()
    return _customize_payload(base.build_payload())


def main() -> int:
    _apply_config()
    payload = _customize_payload(base.build_payload())
    base.persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


_ORIGINAL_GATE4 = base._gate4


if __name__ == "__main__":
    raise SystemExit(main())
