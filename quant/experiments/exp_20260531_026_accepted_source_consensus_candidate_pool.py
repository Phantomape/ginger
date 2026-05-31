"""exp-20260531-026: accepted-source consensus candidate pool.

This alpha search keeps the accepted exp-20260531-021/025 alpha-score
market-regime route fixed and tests one standalone candidate-pool variable:
only paper candidates where the alpha-score sleeve and at least one other
accepted free-data paper source select the same ticker on the same signal date.

Core ranking, market gates, hold days, notional, LLM/news behavior, watchlists,
orders, and production trading are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional as base_exp


framework = base_exp.framework
REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-026"
STEM = "accepted_source_consensus_candidate_pool"
TRIAL_FAMILY = "accepted_source_consensus_candidate_pool"
CHANGED_VARIABLE = "accepted_source_consensus_candidate_pool_v1"
RULE_VERSION = "accepted_source_consensus_candidate_pool_v1"

BASELINE_EXPERIMENT_ID = "exp-20260531-021"
BASELINE_SAFE_NOTIONAL_USD = 4_000.0
ALPHA_SCORE_SOURCE_NAME = "ALPHA_SCORE_MARKET_REGIME_PAPER"
CONSENSUS_SOURCE_FILES = {
    "FINRA_IWM_CONFIRMED_PAPER": (
        "data/experiments/exp-20260530-007/"
        "exp_20260530_007_finra_iwm_same_ticker_cooldown_candidate_pool.json"
    ),
    "VOLUME_BREADTH_BREAKOUT_PAPER": (
        "data/experiments/exp-20260529-004/"
        "exp_20260529_004_vbb_cost_liquidity_support.json"
    ),
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_026_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = CARD_MD
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _signal_key(row: dict[str, Any]) -> tuple[str, str] | None:
    date_value = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    if not date_value or not ticker:
        return None
    return date_value, ticker


def _load_consensus_keys() -> dict[tuple[str, str], set[str]]:
    keys: dict[tuple[str, str], set[str]] = {}
    for source_name, rel_path in CONSENSUS_SOURCE_FILES.items():
        path = REPO_ROOT / rel_path
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for rows in (payload.get("target_trades_by_window") or {}).values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = _signal_key(row)
                if key is None:
                    continue
                keys.setdefault(key, set()).add(source_name)
    return keys


def _patch_framework() -> None:
    base_exp._patch_framework()
    for module in (base_exp, base_exp.source, base_exp.source.source, framework):
        module.EXPERIMENT_ID = EXPERIMENT_ID
        module.STEM = STEM
        module.TRIAL_FAMILY = TRIAL_FAMILY
        module.CHANGED_VARIABLE = CHANGED_VARIABLE
        module.RULE_VERSION = RULE_VERSION
        module.OUT_DIR = OUT_DIR
        module.OUT_JSON = OUT_JSON
        module.BEFORE_AGG_JSON = BEFORE_AGG_JSON
        module.AFTER_AGG_JSON = AFTER_AGG_JSON
        module.LOG_JSON = LOG_JSON
        module.TICKET_JSON = TICKET_JSON
        module.CARD_MD = CARD_MD
        module.ARTIFACT_MD = ARTIFACT_MD
        module.EXPERIMENT_LOG = EXPERIMENT_LOG

    framework.base.BASE_NOTIONAL_USD = BASELINE_SAFE_NOTIONAL_USD
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = base_exp._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    consensus = _load_consensus_keys()
    supported: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for row in candidates:
        key = _signal_key(row)
        sources = sorted(consensus.get(key, set())) if key else []
        if not sources:
            continue
        for source_name in sources:
            source_counts[source_name] = source_counts.get(source_name, 0) + 1
        supported.append(
            {
                **row,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": RULE_VERSION,
                "source_consensus_candidate_pool": True,
                "source_consensus_sources": sources,
                "source_consensus_source_count": 1 + len(sources),
                "primary_source": ALPHA_SCORE_SOURCE_NAME,
                "source_consensus_known_at": (
                    "after_signal_date_close_before_next_open_paper_entry"
                ),
                "paper_notional_usd": BASELINE_SAFE_NOTIONAL_USD,
                "baseline_safe_paper_notional_usd": BASELINE_SAFE_NOTIONAL_USD,
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    return supported, {
        **audit,
        "rule_version": RULE_VERSION,
        "source_experiment_id": BASELINE_EXPERIMENT_ID,
        "raw_candidate_count_before_consensus_filter": len(candidates),
        "source_consensus_key_count": len(consensus),
        "source_consensus_candidate_count": len(supported),
        "source_consensus_source_counts": dict(sorted(source_counts.items())),
        "source_consensus_min_source_count": 2,
        "baseline_safe_paper_notional_usd": BASELINE_SAFE_NOTIONAL_USD,
        "consensus_source_files": CONSENSUS_SOURCE_FILES,
    }


def _candidate_pool_summary(payload: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    all_rows: list[dict[str, Any]] = []
    for label, trades in payload.get("target_trades_by_window", {}).items():
        rows = list(trades or [])
        all_rows.extend(rows)
        by_window[label] = {
            "trade_count": len(rows),
            "total_pnl": framework.base._round(
                sum(float(row.get("pnl") or 0.0) for row in rows),
                2,
            ),
            "source_counts": dict(
                sorted(
                    {
                        source_name: sum(
                            1
                            for row in rows
                            if source_name in (row.get("source_consensus_sources") or [])
                        )
                        for source_name in CONSENSUS_SOURCE_FILES
                    }.items()
                )
            ),
        }
    return {
        "trade_count": len(all_rows),
        "windows": [
            label for label, row in by_window.items() if row["trade_count"] > 0
        ],
        "total_pnl": framework.base._round(
            sum(float(row.get("pnl") or 0.0) for row in all_rows),
            2,
        ),
        "by_window": by_window,
        "source_counts": dict(
            sorted(
                {
                    source_name: sum(
                        1
                        for row in all_rows
                        if source_name in (row.get("source_consensus_sources") or [])
                    )
                    for source_name in CONSENSUS_SOURCE_FILES
                }.items()
            )
        ),
    }


def _append_gate4_failure(payload: dict[str, Any], reason: str) -> None:
    payload["gate4"]["passed"] = False
    failed = payload["gate4"].setdefault("failed_reasons", [])
    if reason not in failed:
        failed.append(reason)


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = base_exp._postprocess_payload(payload)
    summary = _candidate_pool_summary(payload)
    target_summary = payload.get("target_trade_summary") or {}
    if summary["trade_count"] < 20:
        _append_gate4_failure(payload, "source_consensus_trade_count_below_20")
    if len(summary["windows"]) < 3:
        _append_gate4_failure(payload, "source_consensus_missing_standard_window")
    if float(target_summary.get("max_single_positive_pnl_share") or 0.0) > 0.50:
        _append_gate4_failure(payload, "positive_pnl_ticker_concentration_above_50pct")
    if float(target_summary.get("positive_pnl_hhi") or 0.0) > 0.30:
        _append_gate4_failure(payload, "positive_pnl_hhi_above_0p30")

    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_consensus_candidate_adapter"
        if gate4["passed"]
        else "rejected_accepted_source_consensus_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "A standalone accepted-source consensus default-off paper "
                "candidate pool may improve alpha density when at least two "
                "production-visible free-data sleeves select the same ticker "
                "on the same signal date."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260531-024",
                "exp-20260531-025",
                "exp-20260531-021",
                "exp-20260530-007",
                "exp-20260529-004",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_cross_source_agreement_candidate_pool",
            "prediction": {
                "success_probability": 0.32,
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
                "main_failure_modes": [
                    "thin_sample",
                    "window_regression",
                    "drawdown_drift",
                    "source_consensus_nearby_repeat",
                ],
                "confidence_reason": (
                    "Meta research ranks default-off adapters highest and "
                    "exp024/025 showed cross-source agreement has positive "
                    "incremental evidence, but this standalone pool is adjacent "
                    "and may be thin."
                ),
                "recorded_at": "2026-05-31T21:06:09+00:00",
                "brier_score": round((0.32 - actual_success) ** 2, 6),
            },
            "parameters": {
                **payload["parameters"],
                "source_definition_fixed_from": BASELINE_EXPERIMENT_ID,
                "primary_source": ALPHA_SCORE_SOURCE_NAME,
                "baseline_safe_paper_notional_usd": BASELINE_SAFE_NOTIONAL_USD,
                "source_consensus_min_source_count": 2,
                "consensus_source_files": CONSENSUS_SOURCE_FILES,
                "changed_only": [
                    "keep exp-20260531-021 alpha_score candidate definition fixed",
                    "keep $4,000 paper notional, top-1/day, 20-trading-day hold, market gate, score weights, LLM/news, and live orders fixed",
                    "retain only candidates whose signal-date ticker also appears in accepted FINRA/IWM or VBB paper target trades",
                ],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / capital allocation: accepted-source "
                    "cross-sleeve agreement should isolate higher-density "
                    "default-off paper candidates without retuning alpha_score."
                ),
                "2_history_check": {
                    "exp-20260531-024": (
                        "Positive replay lead: 1.25x support for alpha_score "
                        "rows with FINRA/IWM or VBB same-date agreement."
                    ),
                    "exp-20260531-025": (
                        "Promoted that support into the shared default-off "
                        "alpha_score adapter. This run does not change it."
                    ),
                    "exp-20260531-021": (
                        "Accepted alpha_score market-regime $4,000 paper source; "
                        "this run uses its rows as the primary source."
                    ),
                    "exp-20260530-007": (
                        "Accepted FINRA/IWM same-ticker cooldown candidate pool."
                    ),
                    "exp-20260529-004": (
                        "Accepted VBB cost/liquidity supported paper route."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; no EV or PnL-regressed window versus core; >=20 "
                    "target trades across all 3 windows; drawdown drift <=0.5pp; "
                    "survival >=5%; max single positive share <=0.50; positive "
                    "PnL HHI <=0.30."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260531_026_accepted_source_consensus_candidate_pool.py"
                ),
            },
            "source_consensus_candidate_pool_summary": summary,
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_ranking": False,
                "alters_core_sizing": False,
                "alters_core_exits": False,
                "llm_or_news_changed": False,
                "shared_adapter_changed": False,
                "trade_enabled": False,
                "default_off_paper_only": True,
                "replay_only": True,
                "promotion_requirement": (
                    "A positive result is not retained as production-equivalent "
                    "until a shared default-off adapter computes the same "
                    "source-consensus candidate field for production and replay."
                ),
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
            },
            "why_not_other_changes": (
                "Skipped alpha_score score, threshold, top-N, hold-day, market "
                "gate, notional, and source-consensus scalar retunes because the "
                "playbook freezes nearby alpha_score mining. This run tests only "
                "whether already accepted source overlap can stand as its own "
                "candidate pool."
            ),
            "interpretation": (
                "The accepted-source consensus candidate pool cleared replay "
                "Gate 4, but it remains replay-only until the same consensus "
                "field is implemented in a shared default-off adapter."
                if gate4["passed"]
                else (
                    "The accepted-source consensus candidate pool did not clear "
                    "Gate 4. Do not promote it or retune nearby overlap filters "
                    "on these frozen windows without new forward evidence."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If positive, add a shared default-off consensus-candidate "
                "adapter and production/replay parity tests. If rejected, move "
                "to a different free-data candidate-pool surface instead of "
                "retuning same-source overlap."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "The accepted exp-20260531-021 alpha_score market-regime source is "
        "rebuilt point-in-time using signal-date OHLCV/context. The only "
        "changed variable is filtering that paper candidate pool to rows whose "
        "same signal-date ticker is also present in accepted FINRA/IWM or VBB "
        "paper target trades. Paper notional stays fixed at $4,000, entry is "
        "the next available open, and exit remains 20 trading days after signal."
    )
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "paper_notional_usd",
            "known_at",
            "alpha_score",
            "alpha_score_bucket",
            "rank_score_validity_regime_bucket",
            "source_consensus_candidate_pool",
            "source_consensus_sources",
            "source_consensus_source_count",
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(CARD_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Consensus trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    summary = payload["source_consensus_candidate_pool_summary"]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=summary["by_window"][label]["trade_count"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260531-026 Accepted-Source Consensus Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: retain only accepted alpha_score market-regime paper candidates that overlap an accepted FINRA/IWM or VBB paper source on the same signal date and ticker.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs core: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- consensus trades: `{summary['trade_count']}` across `{len(summary['windows'])}` windows",
            f"- consensus total PnL: `${summary['total_pnl']}`",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Source Mix",
            "",
            "```json",
            json.dumps(summary, indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result still requires a shared default-off consensus-candidate adapter and parity tests before retention.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Accepted-source consensus candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "json": framework.base._repo_rel(OUT_JSON),
        "card": framework.base._repo_rel(CARD_MD),
        "artifact": framework.base._repo_rel(CARD_MD),
        "before_aggregate": payload["judge_before_aggregate"],
        "after_aggregate": payload["judge_after_aggregate"],
        "summary": payload["interpretation"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "result_file": framework.base._repo_rel(OUT_JSON),
            "card_file": framework.base._repo_rel(CARD_MD),
            "artifact_file": framework.base._repo_rel(CARD_MD),
            "gate4_passed": payload["gate4"]["passed"],
            "delta_metrics": {
                "expected_value_score": payload["expected_value_score_delta"],
                "total_pnl": payload["total_pnl_delta"],
                "max_drawdown_pct": payload["delta_metrics"]["aggregate"][
                    "max_drawdown_delta_max"
                ],
            },
        },
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    report = _build_report(payload)
    framework.base._write_text(CARD_MD, report)
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "source_consensus_candidate_pool_summary": payload[
                        "source_consensus_candidate_pool_summary"
                    ],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "card": framework.base._repo_rel(CARD_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
