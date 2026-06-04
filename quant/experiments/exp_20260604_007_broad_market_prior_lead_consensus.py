"""exp-20260604-007: broad-market prior-lead consensus confirmation.

Replay-only alpha search. This tests one variable: whether the accepted,
production-visible BROAD_MARKET_LEADERSHIP_PAPER sleeve can confirm accepted
free-data consensus rows when it led the same ticker by 1-3 trading days.

No shared adapter, production order path, ranking, sizing, exits, LLM, news,
watchlists, source thresholds, hold period, cooldown, or notional policy is
changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260603_014_accepted_consensus_independent_source_family as consensus  # noqa: E402
import exp_20260604_002_broad_market_consensus_source_family as broad_same_day  # noqa: E402


EXPERIMENT_ID = "exp-20260604-007"
STEM = "broad_market_prior_lead_consensus"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_timing"
CHANGED_VARIABLE = "broad_market_prior_3_trading_day_lead_confirmation"
RULE_VERSION = "accepted_consensus_with_broad_market_prior_3d_lead_v1"

BROAD_MARKET_SOURCE = broad_same_day.BROAD_MARKET_SOURCE
BROAD_MARKET_EXPERIMENT_ID = broad_same_day.BROAD_MARKET_EXPERIMENT_ID
BROAD_MARKET_FAMILY = broad_same_day.BROAD_MARKET_FAMILY
BROAD_MARKET_RULE_VERSION = broad_same_day.BROAD_MARKET_RULE_VERSION
MIN_LEAD_TRADING_DAYS = 1
MAX_LEAD_TRADING_DAYS = 3

ROOT = consensus.ROOT
OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_007_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
ACCEPTED_COMPARATOR_JSON = OUT_DIR / f"{STEM}_accepted_comparator_aggregate.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = Path("docs/experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = Path("experiments/artifacts") / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")

BROAD_MARKET_SOURCE_ARTIFACT = broad_same_day.BROAD_MARKET_SOURCE_ARTIFACT
CURRENT_ACCEPTED_COMPARATOR_ARTIFACT = broad_same_day.CURRENT_ACCEPTED_COMPARATOR_ARTIFACT

SOURCE_FILES = {
    **consensus.SOURCE_FILES,
    BROAD_MARKET_SOURCE: BROAD_MARKET_SOURCE_ARTIFACT,
}
SOURCE_EXPERIMENT_IDS = {
    **consensus.SOURCE_EXPERIMENT_IDS,
    BROAD_MARKET_SOURCE: BROAD_MARKET_EXPERIMENT_ID,
}
SOURCE_FAMILIES = {
    **consensus.SOURCE_FAMILIES,
    BROAD_MARKET_SOURCE: BROAD_MARKET_FAMILY,
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
        "This experiment changes no production code. A retained prior-lead "
        "source-timing construction would need the shared free-data consensus "
        "adapter to consume the same prior 1-3 trading-day BROAD_MARKET_LEADERSHIP_PAPER "
        "rows in both daily run and replay before any candidate queue or order "
        "surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _safe(value: Any) -> Any:
    return broad_same_day._safe(value)


def _load_json(path: Path) -> Any:
    return broad_same_day._load_json(path)


def _write_json(path: Path, payload: Any) -> None:
    broad_same_day._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    broad_same_day._write_text(path, text)


def _configure_consensus_module() -> None:
    consensus.EXPERIMENT_ID = EXPERIMENT_ID
    consensus.STEM = STEM
    consensus.TRIAL_FAMILY = TRIAL_FAMILY
    consensus.CHANGED_VARIABLE = CHANGED_VARIABLE
    consensus.RULE_VERSION = RULE_VERSION
    consensus.SOURCE_FILES = SOURCE_FILES
    consensus.SOURCE_EXPERIMENT_IDS = SOURCE_EXPERIMENT_IDS
    consensus.SOURCE_FAMILIES = SOURCE_FAMILIES
    consensus.OUT_DIR = OUT_DIR
    consensus.OUT_JSON = OUT_JSON
    consensus.BEFORE_JSON = BEFORE_JSON
    consensus.AFTER_JSON = AFTER_JSON
    consensus.LOG_JSON = LOG_JSON
    consensus.TICKET_JSON = TICKET_JSON
    consensus.CARD_MD = CARD_MD
    consensus.EXPERIMENT_LOG = EXPERIMENT_LOG
    consensus.REGISTRY_JSON = REGISTRY_JSON
    consensus.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    consensus._configure_prior_module()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _trading_day_indexes_by_window() -> dict[str, dict[str, int]]:
    indexes: dict[str, dict[str, int]] = {}
    for label, cfg in consensus.prior.base.WINDOWS.items():
        snapshot = _load_json(REPO_ROOT / cfg["snapshot"])
        rows_by_ticker = snapshot.get("ohlcv") or {}
        trading_days = sorted(
            {
                str(row.get("Date"))[:10]
                for rows in rows_by_ticker.values()
                if isinstance(rows, list)
                for row in rows
                if isinstance(row, dict)
                and cfg["start"] <= str(row.get("Date"))[:10] <= cfg["end"]
            }
        )
        indexes[label] = {day: idx for idx, day in enumerate(trading_days)}
    return indexes


def _shifted_broad_market_source_rows_by_window() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    existing = consensus.prior._source_rows_by_window()
    merged: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = {
        label: {key: list(rows) for key, rows in keyed.items()}
        for label, keyed in existing.items()
    }
    broad_rows, broad_diagnostics = broad_same_day._broad_market_source_rows_by_window()
    trading_indexes = _trading_day_indexes_by_window()

    diagnostics: dict[str, Any] = {
        "source": BROAD_MARKET_SOURCE,
        "source_experiment_id": BROAD_MARKET_EXPERIMENT_ID,
        "source_artifact": str(BROAD_MARKET_SOURCE_ARTIFACT).replace("\\", "/"),
        "source_family": BROAD_MARKET_FAMILY,
        "timing_rule": "same_ticker_prior_1_to_3_trading_day_lead_confirmation",
        "min_lead_trading_days": MIN_LEAD_TRADING_DAYS,
        "max_lead_trading_days": MAX_LEAD_TRADING_DAYS,
        "broad_market_raw": broad_diagnostics,
        "windows": {},
    }

    for label, keyed in broad_rows.items():
        by_ticker: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for (source_date, ticker), rows in keyed.items():
            for row in rows:
                by_ticker[ticker].append((source_date, row))

        lag_counts: Counter[int] = Counter()
        shifted_rows_added = 0
        confirmed_existing_keys: set[tuple[str, str]] = set()
        target = merged.setdefault(label, {})
        day_index = trading_indexes.get(label, {})
        existing_key_count = len(existing.get(label, {}))
        same_date_overlap = sum(
            1
            for key in keyed
            if key in existing.get(label, {}) and existing.get(label, {}).get(key)
        )

        for target_date, ticker in sorted(existing.get(label, {})):
            target_idx = day_index.get(target_date)
            if target_idx is None:
                continue
            for source_date, row in by_ticker.get(ticker, []):
                source_idx = day_index.get(source_date)
                if source_idx is None:
                    continue
                lead_days = target_idx - source_idx
                if lead_days < MIN_LEAD_TRADING_DAYS or lead_days > MAX_LEAD_TRADING_DAYS:
                    continue
                shifted = dict(row)
                shifted.update(
                    {
                        "date": target_date,
                        "signal_date": target_date,
                        "consensus_join_date": target_date,
                        "source_original_signal_date": source_date,
                        "source_timing_lag_trading_days": lead_days,
                        "source_timing_rule": (
                            "broad_market_prior_1_to_3_trading_day_same_ticker_lead"
                        ),
                        "known_at": row.get("known_at") or f"{source_date}T21:00:00Z",
                        "trade_enabled": False,
                        "alters_orders": False,
                    }
                )
                target.setdefault((target_date, ticker), []).append(shifted)
                shifted_rows_added += 1
                lag_counts[lead_days] += 1
                confirmed_existing_keys.add((target_date, ticker))

        diagnostics["windows"][label] = {
            "existing_source_key_count": existing_key_count,
            "raw_broad_source_key_count": len(keyed),
            "same_date_overlap_with_existing_source_rows": same_date_overlap,
            "prior_lead_shifted_rows_added": shifted_rows_added,
            "prior_lead_confirmed_existing_key_count": len(confirmed_existing_keys),
            "prior_lead_lag_counts": dict(sorted(lag_counts.items())),
            "all_source_row_counts_after_merge": sum(len(rows) for rows in target.values()),
        }

    return merged, diagnostics


def _source_family_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    family_combo_counts = Counter("+".join(trade.get("source_families") or []) for trade in all_trades)
    raw_combo_counts = Counter("+".join(trade.get("source_names") or []) for trade in all_trades)
    broad_confirmed = [
        trade for trade in all_trades if BROAD_MARKET_FAMILY in (trade.get("source_families") or [])
    ]
    prior_lead_confirmed = [
        trade
        for trade in broad_confirmed
        if any(
            row.get("source_name") == BROAD_MARKET_SOURCE and row.get("source_timing_lag_trading_days")
            for row in trade.get("source_rows") or []
        )
    ]
    lag_counts: Counter[int] = Counter()
    for trade in prior_lead_confirmed:
        for row in trade.get("source_rows") or []:
            if row.get("source_name") == BROAD_MARKET_SOURCE:
                lag = row.get("source_timing_lag_trading_days")
                if lag is not None:
                    lag_counts[int(lag)] += 1
    return {
        "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
        "source_families": SOURCE_FAMILIES,
        "selected_family_combo_counts": dict(sorted(family_combo_counts.items())),
        "selected_raw_source_combo_counts": dict(sorted(raw_combo_counts.items())),
        "broad_market_confirmed_trade_count": len(broad_confirmed),
        "broad_market_prior_lead_confirmed_trade_count": len(prior_lead_confirmed),
        "broad_market_prior_lead_lag_counts_in_selected_trades": dict(sorted(lag_counts.items())),
        "total_trade_count": len(all_trades),
        "all_selected_have_min_family_count": all(
            len(trade.get("source_families") or []) >= consensus.MIN_SOURCE_FAMILY_COUNT
            for trade in all_trades
        ),
    }


def _accepted_comparator(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    return broad_same_day._accepted_comparator(aggregate, results)


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Broad-market leadership is unlikely to overlap same-day with accepted consensus rows, "
            "but a prior 1-3 trading-day same-ticker leadership signal may be a production-visible "
            "free-OHLCV lead confirmation that expands consensus without adding noisy tickers."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "The playbook blocks broad-market same-day consensus retries unless new forward overlap "
            "rows or a materially different source-timing construction exists. This tests only that "
            "source-timing construction and leaves source count, source families, thresholds, hold, "
            "cooldown, notional, ranking, sizing, exits, LLM, and production orders locked."
        ),
        "nearby_prior_experiments": [
            "exp-20260604-002 same-day broad-market consensus source family rejected with zero overlap",
            "exp-20260603-014 accepted independent source-family consensus comparator",
            "exp-20260603-015 promoted independent source-family shared default-off adapter",
            "exp-20260603-016 VCP source-family expansion rejected versus accepted comparator",
            "exp-20260604-006 theme-density source family rejected versus accepted comparator",
        ],
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta_vs_current_core": "> 0",
            "aggregate_pnl_delta_vs_current_core": "> 0",
            "accepted_comparator": "exp-20260603-014 after aggregate",
            "aggregate_expected_value_delta_vs_accepted": "> 0",
            "aggregate_pnl_delta_vs_accepted": "> 0",
            "per_window_expected_value_vs_accepted": "no regression windows",
            "minimum_target_trades": consensus.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": consensus.prior.MIN_TARGET_WINDOWS,
            "survival_rate_floor": 0.05,
            "production_retention": "requires shared adapter parity before promotion",
        },
        "reproducibility": (
            "The runner rebuilds broad-market source rows from the accepted helper, shifts only "
            "prior 1-3 trading-day same-ticker rows onto existing accepted source keys, and persists "
            "timing diagnostics, target trades, window metrics, and accepted-comparator deltas."
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    accepted = payload["accepted_comparator"]
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.2,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "lead_overlap_sparse",
            "accepted_comparator_not_beaten",
            "window_regression",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Same-day broad-market overlap was zero, but prior-day leadership could be a real "
            "free-OHLCV lead relation. Recent source-family additions make success unlikely."
        ),
        "recorded_at": "2026-06-04T07:09:50+00:00",
    }
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "broad_market_prior_3d_lead_consensus_confirmation_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_source_timing_construction",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 6,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_free_ohlcv_source_timing_construction",
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": prediction,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": prediction["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_ev_delta_vs_accepted": accepted["aggregate_expected_value_delta_vs_accepted"],
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "actual_pnl_delta_vs_accepted": accepted["aggregate_total_pnl_delta_vs_accepted"],
            "realized_failure_mode": None
            if payload["gate4"]["passed"]
            else "accepted_comparator_or_gate4_failed",
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "aggregate_expected_value_delta_vs_accepted": accepted[
                "aggregate_expected_value_delta_vs_accepted"
            ],
            "aggregate_total_pnl_delta_vs_accepted": accepted["aggregate_total_pnl_delta_vs_accepted"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "broad_market_prior_lead_confirmed_trade_count": payload["source_family_summary"][
                "broad_market_prior_lead_confirmed_trade_count"
            ],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "expected_value_delta_vs_accepted": accepted["by_window"][row["label"]][
                    "expected_value_score_delta_vs_accepted"
                ],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "strategy_total_pnl_delta_vs_accepted": accepted["by_window"][row["label"]][
                    "total_pnl_delta_vs_accepted"
                ],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            str(OUT_JSON).replace("\\", "/"),
            str(ARTIFACT_MD).replace("\\", "/"),
            str(LOG_JSON).replace("\\", "/"),
            str(TICKET_JSON).replace("\\", "/"),
            str(DOC_TICKET_JSON).replace("\\", "/"),
        ],
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
        "anti_js": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    accepted = payload["accepted_comparator"]
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Prior-Lead Consensus",
        "",
        f"Decision: `{payload['gate4']['decision']}`.",
        "",
        (
            "Single causal variable: use `BROAD_MARKET_LEADERSHIP_PAPER` only when it led "
            "the same ticker by 1-3 trading days before an accepted consensus source key."
        ),
        "",
        "## Three-Window Evidence",
        "",
        "| Window | Before EV | After EV | dEV | Accepted EV | dEV vs Accepted | dPnL | dPnL vs Accepted | Targets |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        label = row["label"]
        accepted_row = accepted["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {acev:.4f} | {dacev:+.4f} | ${dpnl:+,.2f} | ${dacpnl:+,.2f} | {targets} |".format(
                label=label,
                bev=float(row["before"]["expected_value_score"]),
                aev=float(row["after"]["expected_value_score"]),
                dev=float(row["comparison"]["expected_value_score_delta"]),
                acev=float(accepted_row["accepted_expected_value_score"]),
                dacev=float(accepted_row["expected_value_score_delta_vs_accepted"]),
                dpnl=float(row["comparison"]["strategy_total_pnl_delta"]),
                dacpnl=float(accepted_row["total_pnl_delta_vs_accepted"]),
                targets=int(row["target_trade_count"]),
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core baseline: `{payload['aggregate']['comparison']['expected_value_score_delta']}`",
            f"- PnL delta vs core baseline: `${payload['aggregate']['comparison']['strategy_total_pnl_delta']:,.2f}`",
            f"- EV delta vs accepted comparator: `{accepted['aggregate_expected_value_delta_vs_accepted']}`",
            f"- PnL delta vs accepted comparator: `${accepted['aggregate_total_pnl_delta_vs_accepted']:,.2f}`",
            f"- Target trades: `{payload['target_summary']['target_trade_count']}`",
            f"- Broad-market prior-lead confirmed target trades: `{payload['source_family_summary']['broad_market_prior_lead_confirmed_trade_count']}`",
            "",
            "## Timing Diagnostics",
            "",
            "```json",
            json.dumps(payload["source_diagnostics"]["windows"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(PRODUCTION_IMPACT, indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_artifacts(payload: dict[str, Any]) -> None:
    markdown = _artifact_markdown(payload)
    _write_text(REPO_ROOT / CARD_MD, markdown)
    _write_text(REPO_ROOT / ARTIFACT_MD, markdown)


def _update_ticket(path: Path, payload: dict[str, Any]) -> None:
    abs_path = REPO_ROOT / path
    ticket = _load_json(abs_path) if abs_path.exists() else {}
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
    _write_json(abs_path, ticket)


def _upsert_registry(payload: dict[str, Any]) -> None:
    path = REPO_ROOT / REGISTRY_JSON
    if not path.exists():
        return
    registry = _load_json(path)
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
    _write_json(path, registry)


def main() -> None:
    _configure_consensus_module()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows, source_diagnostics = _shifted_broad_market_source_rows_by_window()
    baselines = consensus.prior._load_baselines()
    results, target_trades_by_window = consensus._run_windows(baselines, source_rows)
    aggregate = consensus.prior._aggregate_results(results)
    target_summary = consensus.prior._target_summary(target_trades_by_window)
    source_family_summary = _source_family_summary(target_trades_by_window)
    gate4 = consensus.prior._gate4_decision(aggregate, results, target_summary)
    accepted_comparator = _accepted_comparator(aggregate, results)

    if not source_family_summary["all_selected_have_min_family_count"]:
        gate4["gates"]["source_family_min_count_passed"] = False
        gate4["passed"] = False
        gate4["decision"] = "rejected_broad_market_prior_lead_source_family_invariant_failed"
        gate4["rationale"] = "At least one selected trade failed the independent source-family count invariant."
    else:
        gate4["gates"]["source_family_min_count_passed"] = True

    gate4["accepted_comparator"] = {
        "passed": accepted_comparator["passed"],
        "aggregate_expected_value_delta_vs_accepted": accepted_comparator[
            "aggregate_expected_value_delta_vs_accepted"
        ],
        "aggregate_total_pnl_delta_vs_accepted": accepted_comparator[
            "aggregate_total_pnl_delta_vs_accepted"
        ],
        "ev_regression_windows_vs_accepted": accepted_comparator[
            "ev_regression_windows_vs_accepted"
        ],
    }
    gate4["gates"]["accepted_comparator_beaten"] = bool(accepted_comparator["passed"])
    if gate4["passed"] and not accepted_comparator["passed"]:
        gate4["passed"] = False
        gate4["decision"] = "rejected_broad_market_prior_lead_underperformed_accepted_comparator"
        gate4["rationale"] = (
            "The candidate improved versus the core baseline but failed the current accepted "
            "free-data consensus comparator from exp-20260603-014."
        )
        gate4["requires_parity_before_promotion"] = False
    elif gate4["passed"]:
        gate4["decision"] = "positive_broad_market_prior_lead_requires_shared_adapter"
        gate4["rationale"] = (
            "Canonical three-window replay beat both the core baseline and the current accepted "
            "consensus comparator. No production behavior changed; promotion requires shared "
            "live/backtest prior-lead consensus adapter parity first."
        )
        gate4["requires_parity_before_promotion"] = True

    completed_at = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "source_files": {name: str(path).replace("\\", "/") for name, path in SOURCE_FILES.items()},
        "source_diagnostics": source_diagnostics,
        "rule": {
            "rule_version": RULE_VERSION,
            "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
            "source_families": SOURCE_FAMILIES,
            "broad_market_source": BROAD_MARKET_SOURCE,
            "min_lead_trading_days": MIN_LEAD_TRADING_DAYS,
            "max_lead_trading_days": MAX_LEAD_TRADING_DAYS,
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_timing_admission_only": True,
        },
        "aggregate": aggregate,
        "accepted_comparator": accepted_comparator,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(REPO_ROOT / OUT_JSON, payload)
    _write_json(REPO_ROOT / BEFORE_JSON, aggregate["before"])
    _write_json(REPO_ROOT / AFTER_JSON, aggregate["after"])
    _write_json(REPO_ROOT / ACCEPTED_COMPARATOR_JSON, accepted_comparator)
    record = _experiment_log_record(payload)
    _write_json(REPO_ROOT / LOG_JSON, record)
    _write_artifacts(payload)
    _update_ticket(TICKET_JSON, payload)
    _update_ticket(DOC_TICKET_JSON, payload)
    _upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(REPO_ROOT / EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "accepted_comparator": gate4["accepted_comparator"],
                "source_family_summary": source_family_summary,
                "source_timing_diagnostics": source_diagnostics["windows"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
