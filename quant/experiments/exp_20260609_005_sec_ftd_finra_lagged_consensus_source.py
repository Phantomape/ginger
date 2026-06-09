"""exp-20260609-005: SEC FTD + FINRA as lagged consensus source.

Replay-only alpha search. Tests one causal variable: add the accepted SEC FTD
+ FINRA default-off paper rows as a distinct publication-lagged source family
inside the accepted lagged free-data consensus scout.

No production code, live orders, ranking, sizing, exits, LLM, or news behavior
is changed. No JavaScript is used.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260603_014_accepted_consensus_independent_source_family as same_day  # noqa: E402
import exp_20260604_008_lagged_independent_source_consensus as lagged  # noqa: E402
import exp_20260608_026_industry_laggard_lagged_consensus_source as helper  # noqa: E402
import sec_ftd_finra_paper_sleeve as sec_ftd_finra  # noqa: E402


EXPERIMENT_ID = "exp-20260609-005"
STEM = "sec_ftd_finra_lagged_consensus_source"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_source_family"
TRIAL_VARIANT_ID = "sec_ftd_finra_lagged_consensus_source_family_v1"
CHANGED_VARIABLE = "sec_ftd_finra_source_family_added_to_accepted_lagged_consensus_v1"
RULE_VERSION = "sec_ftd_finra_lagged_consensus_source_family_v1"

SOURCE_NAME = sec_ftd_finra.SLEEVE_NAME
SOURCE_FAMILY = "sec_ftd_settlement_pressure_with_finra_confirmation"
SOURCE_EXPERIMENT_ID = "exp-20260604-027"
REPLAY_LEAD_ID = "exp-20260604-026"
SHARED_SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260604_027_sec_ftd_finra_shared_adapter.json"
)
REPLAY_SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / REPLAY_LEAD_ID
    / "exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool.json"
)

ACCEPTED_LAGGED_ADAPTER_ID = "exp-20260604-009"
ACCEPTED_LAGGED_ADAPTER_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_LAGGED_ADAPTER_ID
    / "exp_20260604_009_lagged_consensus_shared_adapter.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "accepted_lagged_comparator_not_beaten",
        "sec_ftd_finra_redundant_with_existing_finra_short_pressure_sources",
        "window_regression",
        "source_rows_selected_only_as_prior_confirmation",
        "concentration_failed",
    ],
    "confidence_reason": (
        "The SEC FTD + FINRA adapter was accepted as a standalone default-off "
        "paper source with all-window positive evidence, but recent additions "
        "to the accepted lagged consensus often failed once compared against "
        "the current accepted lagged adapter."
    ),
    "recorded_at": "2026-06-09T05:08:05+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_consensus_adapter_change",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. A positive result would still "
        "require the shared free-data consensus adapter to load the accepted "
        "SEC FTD + FINRA paper source under the same source-family mapping in "
        "historical replay and daily production, with parity tests, before any "
        "daily report queue, candidate priority, paper notional, watchlist, or "
        "order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any, *, ensure_ascii: bool = True, sort_keys: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=ensure_ascii, indent=2, sort_keys=sort_keys)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = row["experiment_id"]
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if existing.get("experiment_id") == experiment_id:
                    return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _patch_source_family_context() -> None:
    lagged._configure_same_day_modules()
    same_day.SOURCE_FAMILIES[SOURCE_NAME] = SOURCE_FAMILY
    same_day.SOURCE_EXPERIMENT_IDS[SOURCE_NAME] = SOURCE_EXPERIMENT_ID


def _source_row_from_trade(trade: dict[str, Any], *, label: str) -> dict[str, Any] | None:
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    ticker = str(trade.get("ticker") or "").upper()
    if not signal_date or not ticker:
        return None
    score = trade.get("score")
    return {
        "source_name": SOURCE_NAME,
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "source_family": SOURCE_FAMILY,
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "window_label": label,
        "entry_date": trade.get("entry_date"),
        "paper_pnl": trade.get("paper_pnl", trade.get("pnl")),
        "pnl_usd": trade.get("pnl"),
        "return_pct": trade.get("pnl_pct_net"),
        "paper_notional_usd": trade.get("paper_notional_usd"),
        "candidate_selection_score": score,
        "sec_ftd_finra_score": score,
        "ftd_notional": trade.get("ftd_notional"),
        "ftd_notional_to_adv20": trade.get("ftd_notional_to_adv20"),
        "ftd_shares": trade.get("ftd_shares"),
        "ftd_publication_date": trade.get("ftd_publication_date"),
        "ftd_publication_age_days": trade.get("ftd_publication_age_days"),
        "ftd_settlement_date": trade.get("ftd_settlement_date"),
        "finra_days_to_cover": trade.get("finra_days_to_cover"),
        "finra_short_interest_change_pct": trade.get("finra_short_interest_change_pct"),
        "finra_publication_date": trade.get("finra_publication_date"),
        "finra_settlement_date": trade.get("finra_settlement_date"),
        "ret20_excess_spy": trade.get("ret20_excess_spy"),
        "volume_ratio_20": trade.get("volume_ratio_20"),
        "close_location": trade.get("close_location"),
        "avg_dollar_volume_20": trade.get("avg_dollar_volume_20"),
        "same_day_core_entry_count": trade.get("same_day_core_entry_count"),
        "same_ticker_core_overlap": trade.get("same_ticker_core_overlap"),
        "source_page": trade.get("source_page"),
        "uses_free_sec_ftd": True,
        "uses_free_finra": True,
        "uses_llm": False,
        "helper_rule_version": sec_ftd_finra.RULE_VERSION,
        "helper_ftd_rule_version": sec_ftd_finra.FTD_SOURCE_RULE_VERSION,
        "helper_finra_rule_version": sec_ftd_finra.FINRA_CONFIRMATION_RULE_VERSION,
        "source_artifact": _repo_rel(REPLAY_SOURCE_ARTIFACT),
        "shared_adapter_artifact": _repo_rel(SHARED_SOURCE_ARTIFACT),
        "historical_replay_experiment_id": REPLAY_LEAD_ID,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "alters_orders": False,
        "known_at": "after_sec_publication_and_finra_publication_before_paper_signal",
    }


def _sec_source_rows_by_window() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    payload = _load_json(REPLAY_SOURCE_ARTIFACT)
    rows_by_window = payload.get("target_trades_by_window") or {}
    out: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    diagnostics: dict[str, Any] = {
        "source_path": _repo_rel(REPLAY_SOURCE_ARTIFACT),
        "shared_source_path": _repo_rel(SHARED_SOURCE_ARTIFACT),
        "source_name": SOURCE_NAME,
        "source_family": SOURCE_FAMILY,
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "historical_replay_experiment_id": REPLAY_LEAD_ID,
        "helper_rule_version": sec_ftd_finra.RULE_VERSION,
        "helper_ftd_rule_version": sec_ftd_finra.FTD_SOURCE_RULE_VERSION,
        "helper_finra_rule_version": sec_ftd_finra.FINRA_CONFIRMATION_RULE_VERSION,
        "selected_trade_count_by_window": {},
        "source_row_count_by_window": {},
        "unique_ticker_count_by_window": {},
        "source_key_count_by_window": {},
    }
    for label in same_day.prior.base.WINDOWS:
        trades = [row for row in rows_by_window.get(label, []) if isinstance(row, dict)]
        tickers: set[str] = set()
        for trade in trades:
            source_row = _source_row_from_trade(trade, label=label)
            if source_row is None:
                continue
            key = (source_row["signal_date"], source_row["ticker"])
            out[label][key].append(source_row)
            tickers.add(source_row["ticker"])
        diagnostics["selected_trade_count_by_window"][label] = len(trades)
        diagnostics["source_row_count_by_window"][label] = sum(len(rows) for rows in out[label].values())
        diagnostics["unique_ticker_count_by_window"][label] = len(tickers)
        diagnostics["source_key_count_by_window"][label] = len(out[label])
    return out, diagnostics


def _merge_source_rows(
    base_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    added_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> dict[str, dict[tuple[str, str], list[dict[str, Any]]]]:
    merged = copy.deepcopy(base_rows)
    for label, by_key in added_rows.items():
        target = merged.setdefault(label, defaultdict(list))
        for key, rows in by_key.items():
            target.setdefault(key, [])
            target[key].extend(copy.deepcopy(rows))
    return merged


def _aggregate_vs_results(
    after_results: list[dict[str, Any]],
    before_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return helper._aggregate_vs_results(after_results, before_results)


def _aggregate_after(results: list[dict[str, Any]]) -> dict[str, Any]:
    return helper._aggregate_after(results)


def _window_comparison(
    results: list[dict[str, Any]],
    accepted_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return helper._window_comparison(results, accepted_results)


def _source_addition_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
    added_source_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> dict[str, Any]:
    all_selected = [row for rows in target_trades_by_window.values() for row in rows]
    selected_with_source = [row for row in all_selected if SOURCE_NAME in (row.get("source_names") or [])]
    current_source = [row for row in selected_with_source if SOURCE_NAME in (row.get("current_source_names") or [])]
    prior_source = [
        row
        for row in selected_with_source
        if any(
            source_row.get("source_name") == SOURCE_NAME
            and source_row.get("timing_role") == "prior_confirmation"
            for source_row in row.get("source_rows") or []
        )
    ]
    added_key_counts = {
        label: sum(len(rows) for rows in by_key.values())
        for label, by_key in added_source_rows.items()
    }
    return {
        "added_source_name": SOURCE_NAME,
        "added_source_family": SOURCE_FAMILY,
        "added_source_rows_by_window": dict(sorted(added_key_counts.items())),
        "selected_trade_count": len(all_selected),
        "selected_with_source_count": len(selected_with_source),
        "selected_with_current_source_count": len(current_source),
        "selected_with_prior_source_count": len(prior_source),
        "selected_with_source_pnl_usd": round(
            sum(_safe_float(row.get("pnl")) for row in selected_with_source),
            2,
        ),
        "source_combo_counts_selected": dict(
            sorted(Counter("+".join(row.get("source_names") or []) for row in all_selected).items())
        ),
        "family_combo_counts_selected": dict(
            sorted(Counter("+".join(row.get("source_families") or []) for row in all_selected).items())
        ),
    }


def _gate4(
    aggregate_vs_core: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    vs_lagged: dict[str, Any],
    source_summary: dict[str, Any],
) -> dict[str, Any]:
    base_gate = same_day.prior._gate4_decision(aggregate_vs_core, results, target_summary)
    comp = vs_lagged["comparison"]
    comparator_passed = (
        comp["expected_value_score_delta"] > 0.0
        and comp["strategy_total_pnl_delta"] > 0.0
        and comp["windows_ev_improved"] == 3
        and comp["windows_pnl_improved"] == 3
    )
    source_selected = int(source_summary["selected_with_source_count"]) > 0
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_lagged_consensus_comparator": comparator_passed,
        "new_source_selected_trade_count_positive": source_selected,
    }
    passed = bool(base_gate["passed"] and comparator_passed and source_selected)
    if passed:
        decision = "positive_replay_lead_requires_sec_ftd_finra_lagged_consensus_shared_adapter"
        rationale = (
            "Adding SEC FTD + FINRA as a distinct publication-lagged source "
            "family improved both core and current accepted lagged consensus "
            "across all three windows. Promotion would require a shared adapter "
            "and parity tests first."
        )
    elif not source_selected:
        decision = "rejected_sec_ftd_finra_lagged_consensus_no_selected_source_rows"
        rationale = "The SEC FTD + FINRA source produced no selected lagged-consensus trades."
    elif not comparator_passed:
        decision = "rejected_sec_ftd_finra_lagged_consensus_did_not_beat_accepted_lagged_comparator"
        rationale = (
            "The variant did not beat the current accepted lagged consensus "
            "comparator across all three canonical windows."
        )
    else:
        decision = "rejected_sec_ftd_finra_lagged_consensus_gate4_failed"
        rationale = base_gate["rationale"]
    return {
        "passed": passed,
        "decision": decision,
        "gates": gates,
        "rationale": rationale,
        "min_survival_rate": base_gate.get("min_survival_rate"),
        "max_drawdown_delta": base_gate.get("max_drawdown_delta"),
        "requires_parity_before_promotion": True,
        "accepted_comparator": ACCEPTED_LAGGED_ADAPTER_ID,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Accepted SEC FTD + FINRA borrow-pressure paper rows may improve "
            "the accepted lagged free-data consensus scout when treated as a "
            "distinct free-data source family."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "Matches the playbook preference for production-visible default-off "
            "candidate-pool adapters and free non-OHLCV data edges. It avoids "
            "thin LLM soft-ranking data, SEC phrase retunes, state-surface "
            "allocation retunes, and raw noisy ticker expansion."
        ),
        "nearby_prior_experiments": [
            "exp-20260604-009",
            "exp-20260604-026",
            "exp-20260604-027",
            "exp-20260604-015",
            "exp-20260606-028",
            "exp-20260608-026",
        ],
        "prior_difference": (
            "exp-20260604-026/027 accepted SEC FTD + FINRA as a standalone "
            "shared default-off paper adapter. exp-20260604-009 accepted "
            "lagged independent-source consensus and is the comparator. "
            "exp-20260604-015, exp-20260606-028, and exp-20260608-026 show "
            "that source additions often fail versus the accepted lagged stack. "
            "This run tests a different free non-OHLCV source family, not a "
            "lag-window, hold, threshold, or notional retune."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(same_day.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta_vs_core": "> 0",
            "aggregate_pnl_delta_vs_core": "> 0",
            "must_beat_current_accepted_lagged_consensus_comparator": True,
            "per_window_delta_vs_accepted_lagged_comparator": "3 of 3 windows > 0",
            "minimum_target_trades": same_day.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": same_day.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": same_day.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": same_day.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": same_day.prior.MAX_POSITIVE_HHI,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260609_005_sec_ftd_finra_lagged_consensus_source.py"
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate_vs_core"]["comparison"]
    accepted = payload["vs_accepted_lagged_comparator"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Added accepted SEC FTD + FINRA paper rows as a replay-only distinct "
            "publication-lagged source family to the accepted lagged consensus scout."
        ),
        "change_type": "default_off_paper_adapter_source_family_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 6,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "accepted_publication_lagged_sec_ftd_finra_source_family",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "added_source_name": SOURCE_NAME,
            "added_source_family": SOURCE_FAMILY,
            "helper_rule_version": sec_ftd_finra.RULE_VERSION,
            "helper_ftd_rule_version": sec_ftd_finra.FTD_SOURCE_RULE_VERSION,
            "helper_finra_rule_version": sec_ftd_finra.FINRA_CONFIRMATION_RULE_VERSION,
            "source_path": _repo_rel(REPLAY_SOURCE_ARTIFACT),
            "shared_source_path": _repo_rel(SHARED_SOURCE_ARTIFACT),
            "accepted_lagged_comparator": ACCEPTED_LAGGED_ADAPTER_ID,
            "trade_enabled": False,
        },
        "before_metrics": payload["accepted_lagged_comparator"]["aggregate_after"],
        "after_metrics": payload["aggregate_vs_core"]["after"],
        "delta_metrics": {
            "expected_value_score": accepted["expected_value_score_delta"],
            "total_pnl": accepted["strategy_total_pnl_delta"],
            "expected_value_score_vs_core": comparison["expected_value_score_delta"],
            "total_pnl_vs_core": comparison["strategy_total_pnl_delta"],
            "windows_ev_improved_vs_lagged": accepted["windows_ev_improved"],
            "windows_pnl_improved_vs_lagged": accepted["windows_pnl_improved"],
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": accepted["expected_value_score_delta"],
            "ev_prediction_error": round(
                accepted["expected_value_score_delta"] - PREDICTION["expected_ev_delta"],
                6,
            ),
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": accepted["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                accepted["strategy_total_pnl_delta"] - PREDICTION["expected_pnl_delta"],
                2,
            ),
            "realized_failure_mode": None
            if payload["gate4"]["passed"]
            else payload["gate4"]["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["gate4"]["decision"],
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "negative_reflection": (
            "If rejected, SEC FTD + FINRA likely has standalone edge but little "
            "replacement value inside the accepted lagged consensus because it "
            "overlaps the existing FINRA short-pressure family or selects rows "
            "that are already confirmed by stronger accepted sources. Do not "
            "retry with a family-name reclassification, lag-window sweep, "
            "threshold sweep, hold sweep, or notional sweep; the next attempt "
            "needs forward replacement-value evidence or a materially different "
            "non-OHLCV source."
        ),
        "next_retry_requires": [
            "closed forward replacement-value rows",
            "materially different non-OHLCV source or relation evidence",
            "shared production/backtest adapter and parity tests before promotion",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(REPLAY_SOURCE_ARTIFACT),
            _repo_rel(SHARED_SOURCE_ARTIFACT),
            _repo_rel(ACCEPTED_LAGGED_ADAPTER_ARTIFACT),
        ],
        "windows": payload["window_comparison"],
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    core = payload["aggregate_vs_core"]["comparison"]
    accepted = payload["vs_accepted_lagged_comparator"]["comparison"]
    source = payload["source_addition_summary"]
    lines = [
        f"# {EXPERIMENT_ID} SEC FTD + FINRA Lagged Consensus Source",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-Window Result",
        "",
        f"- Vs core EV delta: `{core['expected_value_score_delta']:+.4f}`",
        f"- Vs core PnL delta: `${core['strategy_total_pnl_delta']:+,.2f}`",
        f"- Vs accepted lagged consensus EV delta: `{accepted['expected_value_score_delta']:+.4f}`",
        f"- Vs accepted lagged consensus PnL delta: `${accepted['strategy_total_pnl_delta']:+,.2f}`",
        f"- Selected trades with SEC FTD + FINRA source: `{source['selected_with_source_count']}`",
        "",
        "| Window | EV Delta Vs Lagged | PnL Delta Vs Lagged | EV Delta Vs Core | Target Trades |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["window_comparison"]:
        lines.append(
            f"| {row['label']} | {row['expected_value_delta_vs_lagged']:+.4f} | "
            f"${row['strategy_total_pnl_delta_vs_lagged']:+,.2f} | "
            f"{row['expected_value_delta_vs_core']:+.4f} | "
            f"{row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Source Diagnostics",
            "",
            f"- SEC FTD + FINRA source rows by window: `{source['added_source_rows_by_window']}`",
            f"- Current SEC FTD + FINRA confirmations selected: `{source['selected_with_current_source_count']}`",
            f"- Prior SEC FTD + FINRA confirmations selected: `{source['selected_with_prior_source_count']}`",
            "",
            "## Production Boundary",
            "",
            "Replay-only. No shared consensus adapter, production path, live/default "
            "orders, ranking, sizing, exits, watchlists, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    _write_text(CARD_MD, "\n".join(lines))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "aggregate_expected_value_delta_vs_lagged": payload[
                    "vs_accepted_lagged_comparator"
                ]["comparison"]["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta_vs_lagged": payload[
                    "vs_accepted_lagged_comparator"
                ]["comparison"]["strategy_total_pnl_delta"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifacts": [
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(TICKET_JSON),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
        for item in experiments:
            if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
                item.update(
                    {
                        "status": "completed",
                        "decision": payload["gate4"]["decision"],
                        "completed_at": payload["completed_at"],
                        "updated_at": payload["completed_at"],
                        "artifact": _repo_rel(OUT_JSON),
                        "log": _repo_rel(LOG_JSON),
                        "aggregate_expected_value_delta": payload[
                            "vs_accepted_lagged_comparator"
                        ]["comparison"]["expected_value_score_delta"],
                        "aggregate_strategy_total_pnl_delta": payload[
                            "vs_accepted_lagged_comparator"
                        ]["comparison"]["strategy_total_pnl_delta"],
                    }
                )
                break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry, ensure_ascii=False, sort_keys=False)


def main() -> None:
    _patch_source_family_context()
    gate2 = same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    base_source_rows = same_day.prior._source_rows_by_window()
    added_rows, source_diagnostics = _sec_source_rows_by_window()
    extended_source_rows = _merge_source_rows(base_source_rows, added_rows)
    baselines = same_day.prior._load_baselines()

    accepted_results, accepted_target_trades = lagged._run_lagged_windows(
        baselines,
        base_source_rows,
    )
    results, target_trades_by_window = lagged._run_lagged_windows(
        baselines,
        extended_source_rows,
    )

    aggregate_vs_core = same_day.prior._aggregate_results(results)
    target_summary = same_day.prior._target_summary(target_trades_by_window)
    lagged_summary = lagged._lagged_source_summary(target_trades_by_window)
    vs_lagged = _aggregate_vs_results(results, accepted_results)
    source_summary = _source_addition_summary(target_trades_by_window, added_rows)
    gate4 = _gate4(aggregate_vs_core, results, target_summary, vs_lagged, source_summary)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: accepted SEC FTD + FINRA borrow-pressure "
                "paper rows may improve lagged accepted-source consensus quality."
            ),
            "2_history_check": {
                "exp-20260604-026/027": (
                    "SEC FTD + FINRA accepted as a standalone shared default-off "
                    "paper adapter with positive three-window evidence."
                ),
                "exp-20260604-009": (
                    "Accepted lagged independent-source consensus timing and "
                    "shared adapter; this is the comparator to beat."
                ),
                "exp-20260604-015": (
                    "VCP source-family addition did not clear the accepted lagged "
                    "comparator despite core-positive evidence."
                ),
                "exp-20260606-028/exp-20260608-026": (
                    "Rolling-correlation peer-shock and industry laggard source "
                    "additions both failed to beat the accepted lagged comparator."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows; accept only if "
                "the variant beats core and current accepted lagged consensus in "
                "all three windows with sample, drawdown, survival, and concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260609_005_sec_ftd_finra_lagged_consensus_source.py"
            ),
        },
        "source_files": {
            "accepted_lagged_comparator": _repo_rel(ACCEPTED_LAGGED_ADAPTER_ARTIFACT),
            SOURCE_NAME: _repo_rel(REPLAY_SOURCE_ARTIFACT),
            f"{SOURCE_NAME}_shared": _repo_rel(SHARED_SOURCE_ARTIFACT),
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "added_source_name": SOURCE_NAME,
            "added_source_family": SOURCE_FAMILY,
            "helper_rule_version": sec_ftd_finra.RULE_VERSION,
            "helper_ftd_rule_version": sec_ftd_finra.FTD_SOURCE_RULE_VERSION,
            "helper_finra_rule_version": sec_ftd_finra.FINRA_CONFIRMATION_RULE_VERSION,
            "prior_confirmation_trading_days": lagged.PRIOR_CONFIRMATION_TRADING_DAYS,
            "min_source_family_count": same_day.MIN_SOURCE_FAMILY_COUNT,
            "base_notional_usd": same_day.prior.BASE_NOTIONAL_USD,
            "hold_days": same_day.prior.HOLD_DAYS,
            "max_paper_trades_per_day": same_day.prior.MAX_PAPER_TRADES_PER_DAY,
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_family_admission_only": True,
            "min_survival_rate": min(_safe_float(row["before"].get("survival_rate")) for row in results),
        },
        "aggregate_vs_core": aggregate_vs_core,
        "accepted_lagged_comparator": {
            "experiment_id": ACCEPTED_LAGGED_ADAPTER_ID,
            "source_artifact": _repo_rel(ACCEPTED_LAGGED_ADAPTER_ARTIFACT),
            "aggregate_after": _aggregate_after(accepted_results),
            "target_summary": same_day.prior._target_summary(accepted_target_trades),
        },
        "vs_accepted_lagged_comparator": vs_lagged,
        "window_comparison": _window_comparison(results, accepted_results),
        "results": results,
        "target_summary": target_summary,
        "lagged_source_summary": lagged_summary,
        "sec_ftd_finra_source_diagnostics": source_diagnostics,
        "source_addition_summary": source_summary,
        "target_trades_by_window": target_trades_by_window,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    log_row = _experiment_log_record(payload)
    _write_json(LOG_JSON, log_row)
    _write_card(payload)
    _update_ticket(payload)
    _update_manifest(payload)
    _update_registry(payload)
    _append_jsonl_once(EXPERIMENT_LOG, log_row)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate_vs_core["comparison"],
                "aggregate_vs_accepted_lagged_consensus": vs_lagged["comparison"],
                "source_addition_summary": source_summary,
                "sec_ftd_finra_source_diagnostics": source_diagnostics,
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
