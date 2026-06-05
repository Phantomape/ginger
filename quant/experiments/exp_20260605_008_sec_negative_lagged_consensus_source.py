"""exp-20260605-008: SEC negative reaction as lagged consensus source.

Replay-only alpha search. Tests one causal variable: add the existing
production-visible SEC negative-reaction event queue as a new independent
source family in the accepted lagged free-data consensus construction.

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

import exp_20260604_008_lagged_independent_source_consensus as lagged  # noqa: E402
import exp_20260603_014_accepted_consensus_independent_source_family as same_day  # noqa: E402
from sec_event_queue import (  # noqa: E402
    RULE_VERSION as SEC_NEGATIVE_QUEUE_RULE_VERSION,
    build_sec_event_queue,
    load_sec_filing_text_rows,
)


EXPERIMENT_ID = "exp-20260605-008"
STEM = "sec_negative_lagged_consensus_source"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_source_family"
TRIAL_VARIANT_ID = "sec_negative_reaction_lagged_consensus_source_family_v1"
CHANGED_VARIABLE = "sec_negative_reaction_source_family_added_to_accepted_lagged_consensus_v1"
RULE_VERSION = "sec_negative_reaction_lagged_consensus_source_family_v1"

SEC_SOURCE_NAME = "SEC_NEGATIVE_REACTION_EVENT_SLEEVE_PAPER"
SEC_SOURCE_FAMILY = "sec_negative_reaction"
SEC_SOURCE_EXPERIMENT_ID = "exp-20260504-012"
SEC_TEXT_PATH = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"

ACCEPTED_LAGGED_ADAPTER_ID = "exp-20260604-009"
ACCEPTED_LAGGED_ADAPTER_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_LAGGED_ADAPTER_ID
    / "exp_20260604_009_lagged_consensus_shared_adapter.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_008_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.08,
    "expected_pnl_delta": 1800.0,
    "main_failure_modes": [
        "zero_overlap",
        "accepted_lagged_comparator_not_beaten",
        "window_regression",
        "concentration_failed",
        "forward_rows_immature",
    ],
    "confidence_reason": (
        "SEC negative reaction is production-visible and free, but recent "
        "independent source-family additions usually fail accepted comparator guards."
    ),
    "recorded_at": "2026-06-05T05:12:26+00:00",
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
    "production_signal_path_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. A positive result would still "
        "require a shared default-off consensus adapter and parity tests before "
        "any daily report queue, candidate priority, paper notional, or order "
        "surface could change."
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
    same_day.SOURCE_FAMILIES[SEC_SOURCE_NAME] = SEC_SOURCE_FAMILY
    same_day.SOURCE_EXPERIMENT_IDS[SEC_SOURCE_NAME] = SEC_SOURCE_EXPERIMENT_ID


def _rows_by_usable_date(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        usable = str(row.get("usable_trade_date") or "")[:10]
        if usable:
            by_date[usable].append(row)
    return by_date


def _source_row_from_sec_candidate(candidate: dict[str, Any], *, signal_date: str) -> dict[str, Any]:
    return {
        "source_name": SEC_SOURCE_NAME,
        "source_experiment_id": SEC_SOURCE_EXPERIMENT_ID,
        "source_family": SEC_SOURCE_FAMILY,
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": str(candidate.get("ticker") or "").upper(),
        "usable_trade_date": candidate.get("usable_trade_date"),
        "reaction_date": candidate.get("reaction_date"),
        "known_at": f"{signal_date}T21:00:00Z",
        "accession_number": candidate.get("accession_number"),
        "language_score": candidate.get("language_score"),
        "language_bucket": candidate.get("language_bucket"),
        "negative_phrase_hits": candidate.get("negative_phrase_hits"),
        "guidance_cut_hits": candidate.get("guidance_cut_hits"),
        "text_event_type": candidate.get("text_event_type"),
        "reaction_excess_return": candidate.get("reaction_excess_return"),
        "reaction_bucket": candidate.get("reaction_bucket"),
        "sec_queue_rule_version": SEC_NEGATIVE_QUEUE_RULE_VERSION,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _sec_source_rows_by_window() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    text_rows = load_sec_filing_text_rows(SEC_TEXT_PATH)
    rows_by_date = _rows_by_usable_date(text_rows)
    out: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    diagnostics: dict[str, Any] = {
        "source_path": _repo_rel(SEC_TEXT_PATH),
        "loaded_text_row_count": len(text_rows),
        "queue_rule_version": SEC_NEGATIVE_QUEUE_RULE_VERSION,
        "candidate_count_by_window": {},
        "source_row_count_by_window": {},
        "unique_ticker_count_by_window": {},
        "source_key_count_by_window": {},
    }

    for label, cfg in same_day.prior.base.WINDOWS.items():
        snapshot = same_day.prior.base.shadow._load_snapshot(cfg["snapshot"])
        dates = lagged._date_order(snapshot, cfg["start"], cfg["end"])
        trading_dates = set(dates)
        ohlcv_by_ticker = snapshot.get("ohlcv", snapshot)
        spy_ohlcv = ohlcv_by_ticker.get("SPY")
        candidate_count = 0
        tickers: set[str] = set()
        usable_dates = [
            usable
            for usable in sorted(rows_by_date)
            if cfg["start"] <= usable <= cfg["end"]
        ]
        for usable in usable_dates:
            queue = build_sec_event_queue(
                rows_by_date[usable],
                as_of=usable,
                ohlcv_by_ticker=ohlcv_by_ticker,
                spy_ohlcv=spy_ohlcv,
                source_path=SEC_TEXT_PATH,
            )
            for candidate in queue.get("candidates") or []:
                candidate_count += 1
                signal_date = str(
                    candidate.get("reaction_date") or candidate.get("usable_trade_date") or ""
                )[:10]
                ticker = str(candidate.get("ticker") or "").upper()
                if not signal_date or not ticker or signal_date not in trading_dates:
                    continue
                source_row = _source_row_from_sec_candidate(candidate, signal_date=signal_date)
                out[label][(signal_date, ticker)].append(source_row)
                tickers.add(ticker)
        diagnostics["candidate_count_by_window"][label] = candidate_count
        diagnostics["source_row_count_by_window"][label] = sum(
            len(rows) for rows in out[label].values()
        )
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
    before_by_label = {row["label"]: row for row in before_results}
    per_window = []
    for row in after_results:
        before = before_by_label[row["label"]]
        delta = same_day.prior.base.overlay_helper._delta(row["after"], before["after"])
        per_window.append(
            {
                "label": row["label"],
                "expected_value_score_delta": delta["expected_value_score"],
                "strategy_total_pnl_delta": delta["total_pnl"],
                "total_pnl_delta": delta["total_pnl"],
                "max_drawdown_delta": delta["max_drawdown_pct"],
            }
        )
    after_ev = sum(_safe_float(row["after"].get("expected_value_score")) for row in after_results)
    before_ev = sum(_safe_float(row["after"].get("expected_value_score")) for row in before_results)
    after_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in after_results)
    before_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in before_results)
    return {
        "comparison": {
            "expected_value_score_delta": round(after_ev - before_ev, 6),
            "strategy_total_pnl_delta": round(after_pnl - before_pnl, 2),
            "total_pnl_delta": round(after_pnl - before_pnl, 2),
            "windows_ev_improved": sum(
                1 for row in per_window if row["expected_value_score_delta"] > 0.0
            ),
            "windows_ev_regressed": sum(
                1 for row in per_window if row["expected_value_score_delta"] < 0.0
            ),
            "windows_pnl_improved": sum(
                1 for row in per_window if row["strategy_total_pnl_delta"] > 0.0
            ),
            "windows_pnl_regressed": sum(
                1 for row in per_window if row["strategy_total_pnl_delta"] < 0.0
            ),
            "per_window": per_window,
        }
    }


def _source_addition_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
    added_source_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> dict[str, Any]:
    all_selected = [row for rows in target_trades_by_window.values() for row in rows]
    selected_with_sec = [
        row for row in all_selected if SEC_SOURCE_NAME in (row.get("source_names") or [])
    ]
    current_sec = [
        row
        for row in selected_with_sec
        if SEC_SOURCE_NAME in (row.get("current_source_names") or [])
    ]
    prior_sec = [
        row
        for row in selected_with_sec
        if any(
            source_row.get("source_name") == SEC_SOURCE_NAME
            and source_row.get("timing_role") == "prior_confirmation"
            for source_row in row.get("source_rows") or []
        )
    ]
    added_key_counts = {
        label: sum(len(rows) for rows in by_key.values())
        for label, by_key in added_source_rows.items()
    }
    return {
        "added_source_name": SEC_SOURCE_NAME,
        "added_source_family": SEC_SOURCE_FAMILY,
        "added_source_rows_by_window": dict(sorted(added_key_counts.items())),
        "selected_trade_count": len(all_selected),
        "selected_with_sec_source_count": len(selected_with_sec),
        "selected_with_current_sec_count": len(current_sec),
        "selected_with_prior_sec_count": len(prior_sec),
        "selected_with_sec_pnl_usd": round(
            sum(_safe_float(row.get("pnl")) for row in selected_with_sec),
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
    source_selected = int(source_summary["selected_with_sec_source_count"]) > 0
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_lagged_consensus_comparator": comparator_passed,
        "new_source_selected_trade_count_positive": source_selected,
    }
    passed = bool(base_gate["passed"] and comparator_passed and source_selected)
    if passed:
        decision = "positive_replay_lead_requires_sec_negative_lagged_consensus_shared_adapter"
        rationale = (
            "Adding SEC negative reaction as an independent source family improved "
            "both core and current accepted lagged consensus across all three windows. "
            "Promotion would require a shared adapter and parity tests first."
        )
    elif not source_selected:
        decision = "rejected_sec_negative_lagged_consensus_no_selected_source_rows"
        rationale = "The SEC negative source produced no selected lagged-consensus trades."
    elif not comparator_passed:
        decision = "rejected_sec_negative_lagged_consensus_did_not_beat_accepted_lagged_comparator"
        rationale = (
            "The variant did not beat the current accepted lagged consensus "
            "comparator across all three canonical windows."
        )
    else:
        decision = "rejected_sec_negative_lagged_consensus_gate4_failed"
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
            "SEC negative-reaction 8-K Item 2.02 events may improve accepted "
            "lagged free-data consensus as a production-visible independent "
            "source family."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "Matches the playbook preference for broad, free, production-visible "
            "default-off candidate-pool scouts. It avoids LLM soft-ranking, "
            "Companyfacts retunes, FTD retunes, and state-surface threshold work."
        ),
        "nearby_prior_experiments": [
            "exp-20260504-010",
            "exp-20260504-012",
            "exp-20260604-008",
            "exp-20260604-009",
            "exp-20260605-002",
            "exp-20260529-019",
        ],
        "prior_difference": (
            "Prior SEC negative work made an observe-only queue/sleeve and event "
            "bundle, not a lagged accepted-source consensus confirmation family. "
            "exp-20260605-002 added FTD+FINRA and produced no selected source rows; "
            "this tests an independent SEC text/reaction queue instead."
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
            "quant\\experiments\\exp_20260605_008_sec_negative_lagged_consensus_source.py"
        ),
    }


def _aggregate_after(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            sum(_safe_float(row["after"].get("expected_value_score")) for row in results),
            6,
        ),
        "strategy_total_pnl": round(
            sum(_safe_float(row["after"].get("total_pnl")) for row in results),
            2,
        ),
    }


def _window_comparison(
    results: list[dict[str, Any]],
    accepted_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    accepted_by_label = {row["label"]: row for row in accepted_results}
    rows = []
    for row in results:
        accepted = accepted_by_label[row["label"]]
        accepted_delta = same_day.prior.base.overlay_helper._delta(row["after"], accepted["after"])
        rows.append(
            {
                "label": row["label"],
                "expected_value_before_lagged": accepted["after"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta_vs_lagged": accepted_delta["expected_value_score"],
                "strategy_total_pnl_before_lagged": accepted["after"]["total_pnl"],
                "strategy_total_pnl_after": row["after"]["total_pnl"],
                "strategy_total_pnl_delta_vs_lagged": accepted_delta["total_pnl"],
                "expected_value_delta_vs_core": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta_vs_core": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "raw_lagged_consensus_candidate_count": row["raw_lagged_consensus_candidate_count"],
                "lagged_independent_candidate_count": row["lagged_independent_candidate_count"],
            }
        )
    return rows


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
            "Added existing SEC negative-reaction queue rows as a replay-only "
            "independent source family to the lagged consensus scout."
        ),
        "change_type": "default_off_paper_adapter_source_family_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 4,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "existing_production_visible_sec_negative_queue_as_new_source_family",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "added_source_name": SEC_SOURCE_NAME,
            "added_source_family": SEC_SOURCE_FAMILY,
            "sec_queue_rule_version": SEC_NEGATIVE_QUEUE_RULE_VERSION,
            "source_path": _repo_rel(SEC_TEXT_PATH),
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
        "next_retry_requires": [
            "closed forward replacement-value rows",
            "materially different source relation or genuinely new free-data source",
            "shared production/backtest adapter and parity tests before promotion",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(SEC_TEXT_PATH),
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
        f"# {EXPERIMENT_ID} SEC Negative Lagged Consensus Source",
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
        f"- Selected trades with SEC negative source: `{source['selected_with_sec_source_count']}`",
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
            f"- SEC source rows by window: `{source['added_source_rows_by_window']}`",
            f"- Current SEC confirmations selected: `{source['selected_with_current_sec_count']}`",
            f"- Prior SEC confirmations selected: `{source['selected_with_prior_sec_count']}`",
            "",
            "## Production Boundary",
            "",
            "Replay-only. No shared adapter, production path, live/default orders, "
            "ranking, sizing, exits, watchlists, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    text = "\n".join(lines)
    _write_text(CARD_MD, text)
    _write_text(ARTIFACT_MD, text)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "markdown_artifact": _repo_rel(ARTIFACT_MD),
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
                _repo_rel(ARTIFACT_MD),
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
    sec_rows, sec_diagnostics = _sec_source_rows_by_window()
    extended_source_rows = _merge_source_rows(base_source_rows, sec_rows)
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
    source_summary = _source_addition_summary(target_trades_by_window, sec_rows)
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
                "entry/candidate_pool: SEC negative-reaction queue rows may improve "
                "lagged accepted-source consensus quality."
            ),
            "2_history_check": {
                "exp-20260504-010": "SEC negative-language plus negative reaction packet was standalone promising.",
                "exp-20260504-012": "Promoted shared default-off SEC negative-reaction forward queue.",
                "exp-20260604-008": "Accepted lagged independent-source timing replay lead.",
                "exp-20260604-009": "Promoted accepted lagged consensus shared adapter.",
                "exp-20260605-002": "Rejected FTD+FINRA addition to lagged consensus; no selected added-source rows.",
                "exp-20260529-019": "Rejected separate Item 5.02 positive-reaction candidate pool.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows; accept only if "
                "the variant beats core and current accepted lagged consensus in "
                "all three windows with sample, drawdown, survival, and concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_008_sec_negative_lagged_consensus_source.py"
            ),
        },
        "source_files": {
            "accepted_lagged_comparator": _repo_rel(ACCEPTED_LAGGED_ADAPTER_ARTIFACT),
            SEC_SOURCE_NAME: _repo_rel(SEC_TEXT_PATH),
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "added_source_name": SEC_SOURCE_NAME,
            "added_source_family": SEC_SOURCE_FAMILY,
            "sec_queue_rule_version": SEC_NEGATIVE_QUEUE_RULE_VERSION,
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
            "min_survival_rate": min(
                _safe_float(row["before"].get("survival_rate")) for row in results
            ),
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
        "sec_source_diagnostics": sec_diagnostics,
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
                "sec_source_diagnostics": sec_diagnostics,
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
