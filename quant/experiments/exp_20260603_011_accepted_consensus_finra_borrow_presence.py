"""exp-20260603-011: accepted consensus FINRA borrow-pressure presence.

This alpha-search replay changes one source-presence variable in the accepted
free-data cross-source consensus scout: add the newly accepted FINRA
borrow-pressure candidate pool as an additional default-off source input.

Because the borrow-pressure source is a refinement of the accepted FINRA/IWM
source rather than an independent mechanism, Gate 4 includes an explicit
source-family independence guard. A positive replay is rejected if it is carried
by FINRA+FINRA double counting.

No production adapter, live order path, ranking, sizing, exits, thresholds, or
shared sleeve code is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_030_accepted_free_data_cross_source_consensus as prior


EXPERIMENT_ID = "exp-20260603-011"
STEM = "accepted_consensus_finra_borrow_presence"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_presence"
CHANGED_VARIABLE = "finra_borrow_pressure_presence_added_to_consensus_source_count"
RULE_VERSION = "finra_borrow_pressure_presence_v1"

ROOT = prior.ROOT
OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = Path("docs/experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = Path("experiments/artifacts") / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")

FINRA_BASE_SOURCE = "FINRA_IWM_CONFIRMED_PAPER"
FINRA_BORROW_SOURCE = "FINRA_BORROW_PRESSURE_PAPER"
FINRA_FAMILY_SOURCES = {FINRA_BASE_SOURCE, FINRA_BORROW_SOURCE}
MAX_FINRA_ONLY_TRADE_SHARE = 0.0
MAX_FINRA_ONLY_PNL_SHARE = 0.0

SOURCE_FILES = {
    **prior.SOURCE_FILES,
    FINRA_BORROW_SOURCE: Path(
        "data/experiments/exp-20260603-006/exp_20260603_006_finra_borrow_pressure_candidate_pool.json"
    ),
}
SOURCE_EXPERIMENT_IDS = {
    **prior.SOURCE_EXPERIMENT_IDS,
    FINRA_BORROW_SOURCE: "exp-20260603-006",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained result would need "
        "a shared default-off adapter with the same source-family semantics and "
        "parity tests before any daily report or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_prior_module() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.SOURCE_FILES = SOURCE_FILES
    prior.SOURCE_EXPERIMENT_IDS = SOURCE_EXPERIMENT_IDS
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.BEFORE_JSON = BEFORE_JSON
    prior.AFTER_JSON = AFTER_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Adding the newly accepted FINRA borrow-pressure source as a "
            "source-presence input to accepted free-data consensus may reveal "
            "incremental replacement value, but only if it does not rely on "
            "FINRA+FINRA double counting."
        ),
        "category": "ranking/candidate_pool",
        "playbook_alignment": (
            "Meta research favors production-visible default-off paper adapters. "
            "The playbook also warns against source-set retunes, so this run uses "
            "a strict source-family independence guard and remains replay-only."
        ),
        "nearby_prior_experiments": [
            "exp-20260531-030",
            "exp-20260601-001",
            "exp-20260603-006",
            "exp-20260603-007",
        ],
        "prior_difference": (
            "The FINRA borrow-pressure source was not available when exp-20260531-030 "
            "and exp-20260601-001 were accepted. This test adds only that fixed "
            "accepted artifact as a source-presence input; source thresholds, hold "
            "periods, notional, and live behavior are locked."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": prior.MIN_TARGET_TRADES,
            "minimum_target_windows": prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": prior.MAX_POSITIVE_HHI,
            "finra_only_double_count_trade_share": f"<= {MAX_FINRA_ONLY_TRADE_SHARE}",
            "finra_only_double_count_pnl_share": f"<= {MAX_FINRA_ONLY_PNL_SHARE}",
        },
        "reproducibility": (
            "All fixed source artifact paths, source-family diagnostics, canonical "
            "window before/after metrics, target trades, and rejection checks are "
            "persisted under this experiment ID."
        ),
    }


def _source_family_diagnostics(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    all_trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    finra_only = [
        trade
        for trade in all_trades
        if set(trade.get("source_names") or []) == FINRA_FAMILY_SOURCES
    ]
    total_positive = sum(max(float(trade.get("pnl", 0.0)), 0.0) for trade in all_trades)
    finra_only_positive = sum(max(float(trade.get("pnl", 0.0)), 0.0) for trade in finra_only)
    combo_counts = Counter("+".join(trade.get("source_names") or []) for trade in all_trades)
    return {
        "finra_family_sources": sorted(FINRA_FAMILY_SOURCES),
        "finra_only_trade_count": len(finra_only),
        "total_trade_count": len(all_trades),
        "finra_only_trade_share": round(len(finra_only) / len(all_trades), 6) if all_trades else 0.0,
        "finra_only_positive_pnl": round(finra_only_positive, 2),
        "total_positive_pnl": round(total_positive, 2),
        "finra_only_positive_pnl_share": round(finra_only_positive / total_positive, 6)
        if total_positive
        else 0.0,
        "source_combo_counts": dict(sorted(combo_counts.items())),
        "finra_only_examples": [
            {
                "date": trade.get("date") or trade.get("signal_date"),
                "ticker": trade.get("ticker"),
                "pnl": trade.get("pnl"),
                "source_names": trade.get("source_names"),
            }
            for trade in finra_only[:20]
        ],
        "guard": {
            "max_finra_only_trade_share": MAX_FINRA_ONLY_TRADE_SHARE,
            "max_finra_only_positive_pnl_share": MAX_FINRA_ONLY_PNL_SHARE,
        },
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    source_family: dict[str, Any],
) -> dict[str, Any]:
    gate = prior._gate4_decision(aggregate, results, target_summary)
    finra_independence_passed = (
        float(source_family["finra_only_trade_share"]) <= MAX_FINRA_ONLY_TRADE_SHARE
        and float(source_family["finra_only_positive_pnl_share"]) <= MAX_FINRA_ONLY_PNL_SHARE
    )
    gate["gates"]["source_family_independence_passed"] = finra_independence_passed
    gate["source_family_independence"] = source_family
    gate["passed_before_source_family_guard"] = bool(gate["passed"])
    gate["passed"] = bool(gate["passed"] and finra_independence_passed)
    gate["requires_parity_before_promotion"] = bool(gate["passed"])
    if not gate["passed"]:
        gate["decision"] = "rejected_finra_borrow_pressure_consensus_presence"
        if not finra_independence_passed:
            gate["rationale"] = (
                "The replay may improve metrics, but the added source is not "
                "independent: selected trades are admitted by FINRA/IWM plus its "
                "borrow-pressure subset. Counting that as cross-source agreement "
                "would create a misleading candidate-pool alpha."
            )
        else:
            gate["rationale"] = (
                "One or more canonical Gate 4 checks failed, so the added source "
                "presence is not retained."
            )
    else:
        gate["decision"] = "positive_replay_lead_not_promoted_requires_shared_cross_source_adapter"
        gate["rationale"] = (
            "The replay cleared canonical Gate 4 and the source-family independence "
            "guard. No production behavior changed; promotion would require a "
            "shared default-off adapter and parity tests."
        )
    return gate


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "why_rejected": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "finra_only_trade_share": payload["source_family_diagnostics"]["finra_only_trade_share"],
            "finra_only_positive_pnl_share": payload["source_family_diagnostics"][
                "finra_only_positive_pnl_share"
            ],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
        "anti_js": "No JavaScript was used.",
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    prior._write_card(payload)
    source_family = payload["source_family_diagnostics"]
    lines = [
        CARD_MD.read_text(encoding="utf-8"),
        "",
        "## Source-Family Independence Guard",
        "",
        f"- FINRA-only double-count trades: `{source_family['finra_only_trade_count']}` / `{source_family['total_trade_count']}`",
        f"- FINRA-only trade share: `{source_family['finra_only_trade_share']}`",
        f"- FINRA-only positive PnL share: `{source_family['finra_only_positive_pnl_share']}`",
        f"- Guard passed: `{payload['gate4']['gates']['source_family_independence_passed']}`",
        "",
        "```json",
        json.dumps(source_family, indent=2, sort_keys=True),
        "```",
        "",
        "No JavaScript was used.",
        "",
    ]
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket(path: Path, payload: dict[str, Any]) -> None:
    ticket = prior._load_json(path) if path.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "markdown_artifact": str(ARTIFACT_MD).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    prior._write_json(path, ticket)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = prior._load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = str(OUT_JSON).replace("\\", "/")
            item["log"] = str(LOG_JSON).replace("\\", "/")
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            break
    prior._write_json(REGISTRY_JSON, registry)


def main() -> None:
    _configure_prior_module()
    gate2 = prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = prior._source_rows_by_window()
    baselines = prior._load_baselines()
    results, target_trades_by_window = prior._run_windows(baselines, source_rows)
    aggregate = prior._aggregate_results(results)
    target_summary = prior._target_summary(target_trades_by_window)
    source_family = _source_family_diagnostics(target_trades_by_window)
    gate4 = _gate4_decision(aggregate, results, target_summary, source_family)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "source_files": {name: str(path).replace("\\", "/") for name, path in SOURCE_FILES.items()},
        "rule": {
            "rule_version": RULE_VERSION,
            "min_source_count": prior.MIN_SOURCE_COUNT,
            "base_notional_usd": prior.BASE_NOTIONAL_USD,
            "hold_days": prior.HOLD_DAYS,
            "max_paper_trades_per_day": prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": prior.SAME_TICKER_COOLDOWN_DAYS,
            "source_family_independence_guard": {
                "finra_family_sources": sorted(FINRA_FAMILY_SOURCES),
                "max_finra_only_trade_share": MAX_FINRA_ONLY_TRADE_SHARE,
                "max_finra_only_positive_pnl_share": MAX_FINRA_ONLY_PNL_SHARE,
            },
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_presence_only": True,
        },
        "aggregate": aggregate,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_diagnostics": source_family,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    prior._write_json(OUT_JSON, payload)
    prior._write_json(BEFORE_JSON, aggregate["before"])
    prior._write_json(AFTER_JSON, aggregate["after"])
    record = _experiment_log_record(payload)
    prior._write_json(LOG_JSON, record)
    _write_artifact(payload)
    _update_ticket(TICKET_JSON, payload)
    _update_ticket(DOC_TICKET_JSON, payload)
    _upsert_registry(payload)
    prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "source_family_independence_passed": gate4["gates"][
                    "source_family_independence_passed"
                ],
                "finra_only_trade_share": source_family["finra_only_trade_share"],
                "finra_only_positive_pnl_share": source_family[
                    "finra_only_positive_pnl_share"
                ],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
