"""exp-20260527-012: sector-leadership same-sector core activity.

This alpha search keeps the rejected sector-leadership candidate source fixed
and changes one variable: default-off paper candidates are admitted only when
the accepted core replay has same-date trend/breakout activity in the same
sector. It is a candidate-pool confirmation test, not a sector-return threshold
or notional retune.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260525_916_sector_leadership_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260527-012"
STEM = "sector_leadership_same_sector_core_activity"
TRIAL_FAMILY = "sector_leadership_same_sector_core_activity_paper_sleeve"
CHANGED_VARIABLE = "sector_leadership_same_sector_core_activity_confirmation_v1"
CONFIRMATION_FIELD = "same_day_core_same_sector_entry_count"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MIN_TARGET_TRADES = 20
    base.MAX_SINGLE_POSITIVE_SHARE = 0.40
    base.MAX_POSITIVE_HHI = 0.30


def _trade_sector(trade: dict[str, Any]) -> str:
    sector = trade.get("sector")
    if sector:
        return str(sector)
    ticker = str(trade.get("ticker") or "").upper()
    return str(base.shadow.SECTOR_MAP.get(ticker, "Unknown"))


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = base._BASE_CANDIDATE_ROWS_FOR_WINDOW(snapshot, cfg, universe, before_result)
    entries_by_date = base.shadow._baseline_entries(before_result)
    confirmed: list[dict[str, Any]] = []
    for row in rows:
        sector = str(row.get("sector") or "Unknown")
        ab_entries = entries_by_date.get(str(row.get("date") or ""), [])
        same_sector_entries = [
            trade
            for trade in ab_entries
            if _trade_sector(trade) == sector
        ]
        if not same_sector_entries:
            continue
        row["same_sector_core_activity_confirmation_rule_version"] = CHANGED_VARIABLE
        row["same_day_core_same_sector_entry_count"] = len(same_sector_entries)
        row["same_day_core_same_sector_tickers"] = sorted(
            {
                str(trade.get("ticker") or "").upper()
                for trade in same_sector_entries
                if trade.get("ticker")
            }
        )
        row["same_sector_core_activity_confirmed"] = True
        confirmed.append(row)
    return confirmed


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_sector_leadership_same_sector_core_activity"
        if gate4_passed
        else "rejected_sector_leadership_same_sector_core_activity"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Sector-leadership candidates should have better replacement value when "
        "the accepted core stack shows same-date trend/breakout activity in the "
        "same sector, because the candidate is then participating in an already "
        "confirmed sector move rather than a standalone relative-strength print."
    )
    payload["change_type"] = "sector_leadership_same_sector_core_activity_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 4
    payload["nearby_prior_experiments"] = [
        "exp-20260426-049",
        "exp-20260525-916",
        "exp-20260525-029",
        "exp-20260525-028",
        "exp-20260526-010",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_same_sector_core_activity_field"
    payload["trial_variant_id"] = "same_sector_core_activity_confirmation"
    payload["parameters"]["confirmation_rule"] = {
        "field": CONFIRMATION_FIELD,
        "definition": (
            "candidate signal date has at least one accepted-core trend_long or "
            "breakout_long entry in the same sector"
        ),
        "candidate_filter": f"{CONFIRMATION_FIELD} > 0",
        "rule_version": CHANGED_VARIABLE,
        "kept_fixed": [
            "sector_leadership_top1_candidate_source",
            "fixed_10000_usd_paper_notional",
            "next_open_paper_entry",
            "10_trading_day_close_exit",
            "same_ticker_core_overlap_exclusion",
            "core_entry_ranking_sizing_exit_behavior",
        ],
    }
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool: sector-leadership paper candidates should "
            "only be tracked when same-sector accepted-core activity confirms "
            "the move."
        ),
        "2_history_check": {
            "exp-20260525-916": (
                "Raw sector-leadership top-1 improved aggregate EV/PnL but "
                "failed on late_strong regression, drawdown drift, and "
                "concentration."
            ),
            "exp-20260526-010": (
                "Any same-date core activity improved aggregate EV/PnL and no "
                "window PnL regressed, but late_strong EV still regressed."
            ),
            "this_run": (
                "Same-sector core activity has not been tested as the single "
                "confirmation field for the sector-leadership paper source."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=20 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260527_012_sector_leadership_same_sector_core_activity.py"
        ),
    }
    payload["gate2"]["runtime_fields"].extend(
        [
            "baseline accepted-core trend_long/breakout_long entry_date by ticker",
            "baseline accepted-core sector",
            "sector-leadership candidate sector",
        ]
    )
    payload["gate2"]["note"] = (
        "The confirmation field is derived from same-date accepted-core activity "
        "and sector labels already present in replay trade rows or the shared "
        "sector map. No production behavior changed; promotion would require "
        "the same field in shared production/backtest adapter code."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or core entry rule was added. The default-off paper "
        "candidate pool is narrowed by a same-sector core activity confirmation, "
        "so core survival remains unchanged from the baseline replay."
    )
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, SEC/Kova semantics, and expectation-revision "
        "activation because current records remain PIT/sample-limited. Skipped "
        "VCP/VBB threshold, top-N, rank-notional, absorption, and state-surface "
        "retunes due playbook freeze and recent rejections. This tests a "
        "materially different same-sector activity confirmation on the otherwise "
        "rejected sector-leadership source."
    )
    payload["interpretation"] = (
        "The same-sector core-activity confirmation cleared Gate 4 as replay-only "
        "evidence; do not promote until the confirmation field is implemented "
        "through shared default-off production/backtest plumbing and parity tests."
        if gate4_passed
        else (
            "The same-sector core-activity confirmation did not clear Gate 4; do "
            "not retry nearby sector-leadership confirmation fields on the same "
            "frozen windows without forward paper rows or a genuinely new "
            "source-quality field."
        )
    )
    payload["rejection_reason"] = None if gate4_passed else payload.get("rejection_reason")
    payload["next_evidence_needed"] = (
        "Forward paper rows or a different source-quality field; do not keep "
        "mining sector-leadership confirmation variants on the frozen sample."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(DOC_TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    payload["production_impact"].update(
        {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "Implement the same-sector core-activity confirmation in a "
                "shared default-off paper adapter plus parity tests before any "
                "daily report, ranking, sizing, or order behavior can consume it."
            ),
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Confirmed candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Sector-Leadership Same-Sector Core Activity",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: keep the sector-leadership candidate source "
                "fixed, but admit paper candidates only when same-date accepted "
                "core trend/breakout activity is present in the same sector."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Filter the sector-leadership default-off paper source to candidates "
            "with same-sector accepted-core activity on the signal date."
        ),
        "change_type": payload["change_type"],
        "mechanism_family": "candidate_pool_alpha",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": base._repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "date_range": payload["backtest_protocol"]["windows"],
        "gate_questions": payload["gate_questions"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "target_trade_summary": payload["target_trade_summary"],
        "llm_metrics": payload["llm_metrics"],
        "production_impact": payload["production_impact"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def _persist(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Sector-leadership same-sector core activity",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "summary": payload["interpretation"],
    }
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, ticket)
    base._write_json(DOC_TICKET_JSON, ticket)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._append_jsonl_once(EXPERIMENT_LOG, _experiment_log_entry(payload))


def main() -> int:
    _configure_base_module()
    if not hasattr(base, "_BASE_CANDIDATE_ROWS_FOR_WINDOW"):
        base._BASE_CANDIDATE_ROWS_FOR_WINDOW = base._candidate_rows_for_window
    base._candidate_rows_for_window = _candidate_rows_for_window
    payload = _patch_payload(base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
