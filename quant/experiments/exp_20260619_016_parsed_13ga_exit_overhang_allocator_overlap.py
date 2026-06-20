"""exp-20260619-016: parsed 13G/A exit-overhang allocator overlap.

Read-only alpha search. The hypothesis is that newly parsed non-Big3
Schedule 13G/A drop-below-5% exit events from exp-20260619-014 may be a
negative ownership-overhang context for accepted default-off allocator paper
entries. If true, allocator entries with a recent exit-below-5% event should
underperform enough that a later shared veto could improve replacement value.

No strategy, shared helper, production adapter, ranking, sizing, exits, LLM,
watchlist, or orders are changed. This runner only measures overlap against the
accepted allocator artifact from exp-20260611-005.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260619-016"
STEM = "parsed_13ga_exit_overhang_allocator_overlap"
OWNER = "alpha-search-automation"
CHANGED_VARIABLE = "parsed_13ga_exit_below5_overhang_veto_for_accepted_allocator_rows_v1"
TRIAL_FAMILY = "parsed_13ga_exit_overhang_allocator_overlap"
TRIAL_VARIANT_ID = "exit_below5_non_big3_overlap_10_trading_sessions_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from experiment_registry import persist_self_registered_result  # noqa: E402


ALLOCATOR_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260611-005"
    / "exp_20260611_005_lagged_consensus_shared_allocator_source.json"
)
SURFACE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260619-014"
    / "parsed_13ga_direction_rows.json"
)
WAREHOUSE_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_016_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

OVERHANG_LOOKBACK_TRADING_DAYS = 10
MIN_OVERLAP_TRADES = 20
MIN_WINDOW_COUNT = 3

PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "overlap_too_thin",
        "window_fragile_veto",
        "accepted_allocator_not_improved",
        "ownership_context_not_actionable",
    ],
    "confidence_reason": (
        "exp-20260619-014 built a new PIT parsed 13G/A direction surface and "
        "found the only clean signal was negative non-Big3 drop-below-5% drift, "
        "while accepted allocator rows are the current high-priority default-off "
        "surface. Main risk is sparse overlap or a weak negative signal after "
        "accepted allocator selection."
    ),
    "recorded_at": "2026-06-19T17:58:29+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(json.dumps(payload, sort_keys=True))
                replaced = True
            else:
                rows.append(line)
    if not replaced:
        rows.append(json.dumps(payload, sort_keys=True))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def spy_calendar_index() -> dict[str, int]:
    con = sqlite3.connect(str(WAREHOUSE_DB))
    try:
        rows = con.execute(
            "SELECT DISTINCT date FROM ohlcv WHERE ticker = 'SPY' ORDER BY date"
        ).fetchall()
    finally:
        con.close()
    return {str(row[0]): idx for idx, row in enumerate(rows)}


def trade_pnl(row: dict[str, Any]) -> float:
    value = row.get("paper_pnl")
    if value is None:
        value = row.get("pnl")
    return float(value or 0.0)


def event_index(surface: dict[str, Any], date_index: dict[str, int]) -> dict[str, list[dict[str, Any]]]:
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in surface.get("rows") or []:
        if row.get("direction") != "exit_below5":
            continue
        if bool(row.get("is_big3")):
            continue
        usable_date = row.get("usable_trade_date")
        ticker = row.get("ticker")
        if not ticker or usable_date not in date_index:
            continue
        events[str(ticker).upper()].append(row)
    for rows in events.values():
        rows.sort(key=lambda item: str(item.get("usable_trade_date") or ""))
    return dict(events)


def matching_events(
    trade: dict[str, Any],
    events_by_ticker: dict[str, list[dict[str, Any]]],
    date_index: dict[str, int],
) -> list[dict[str, Any]]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = trade.get("entry_date")
    signal_date = trade.get("signal_date") or trade.get("date")
    entry_idx = date_index.get(str(entry_date))
    if not ticker or entry_idx is None or not signal_date:
        return []
    matches: list[dict[str, Any]] = []
    for event in events_by_ticker.get(ticker, []):
        usable_date = event.get("usable_trade_date")
        event_idx = date_index.get(str(usable_date))
        if event_idx is None:
            continue
        age = entry_idx - event_idx
        if age < 0 or age > OVERHANG_LOOKBACK_TRADING_DAYS:
            continue
        if str(event.get("filing_date") or "") > str(signal_date):
            continue
        enriched = dict(event)
        enriched["overhang_age_trading_days"] = age
        matches.append(enriched)
    return matches


def summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "sum": 0.0, "avg": None, "win_rate": None}
    wins = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "sum": round(sum(values), 2),
        "avg": round(sum(values) / len(values), 4),
        "win_rate": round(wins / len(values), 4),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    allocator = read_json(ALLOCATOR_ARTIFACT)
    surface = read_json(SURFACE_JSON)
    date_index = spy_calendar_index()
    events_by_ticker = event_index(surface, date_index)

    vetoed_rows: list[dict[str, Any]] = []
    all_pnls: list[float] = []
    veto_pnls: list[float] = []
    non_veto_pnls: list[float] = []
    by_window: dict[str, dict[str, Any]] = {}
    source_family_counter: Counter[str] = Counter()
    age_counter: Counter[str] = Counter()

    target_trades = allocator.get("target_trades_by_window") or {}
    for window, rows in target_trades.items():
        window_all: list[float] = []
        window_veto: list[float] = []
        for row in rows:
            pnl = trade_pnl(row)
            window_all.append(pnl)
            all_pnls.append(pnl)
            matches = matching_events(row, events_by_ticker, date_index)
            if not matches:
                non_veto_pnls.append(pnl)
                continue
            veto_pnls.append(pnl)
            window_veto.append(pnl)
            source_family_counter[str(row.get("source_family") or "unknown")] += 1
            for match in matches:
                age_counter[str(match["overhang_age_trading_days"])] += 1
            vetoed_rows.append(
                {
                    "window": window,
                    "ticker": row.get("ticker"),
                    "signal_date": row.get("signal_date") or row.get("date"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get("exit_date"),
                    "source_family": row.get("source_family"),
                    "pnl": round(pnl, 2),
                    "matched_exit_below5_events": [
                        {
                            "accession_number": match.get("accession_number"),
                            "filing_date": match.get("filing_date"),
                            "usable_trade_date": match.get("usable_trade_date"),
                            "current_percent": match.get("current_percent"),
                            "prior_percent": match.get("prior_percent"),
                            "pct_delta": match.get("pct_delta"),
                            "overhang_age_trading_days": match.get("overhang_age_trading_days"),
                            "reporting_person_types": match.get("reporting_person_types"),
                        }
                        for match in matches
                    ],
                }
            )
        by_window[window] = {
            "accepted_allocator_trade_count": len(rows),
            "overlap_trade_count": len(window_veto),
            "overlap_rate": round(len(window_veto) / len(rows), 6) if rows else 0.0,
            "accepted_allocator_pnl": round(sum(window_all), 2),
            "vetoed_trade_pnl_sum": round(sum(window_veto), 2),
            "counterfactual_veto_delta_pnl": round(-sum(window_veto), 2),
            "accepted_allocator_pnl_after_veto": round(sum(window_all) - sum(window_veto), 2),
            "vetoed_trade_summary": summarize(window_veto),
        }

    windows_with_overlap = [window for window, stats in by_window.items() if stats["overlap_trade_count"] > 0]
    vetoed_pnl_sum = round(sum(veto_pnls), 2)
    veto_delta_pnl = round(-sum(veto_pnls), 2)
    overlap_count = len(veto_pnls)

    failed_reasons: list[str] = []
    if overlap_count < MIN_OVERLAP_TRADES:
        failed_reasons.append("target_overlap_trade_count_too_small")
    if len(windows_with_overlap) < MIN_WINDOW_COUNT:
        failed_reasons.append("target_window_coverage_too_small")
    if veto_delta_pnl <= 0:
        failed_reasons.append("counterfactual_veto_pnl_not_positive")
    if not all(by_window[w]["counterfactual_veto_delta_pnl"] > 0 for w in windows_with_overlap):
        failed_reasons.append("window_veto_pnl_not_consistently_positive")
    failed_reasons.append("no_full_gate4_ev_replay_or_shared_helper")

    decision = "rejected_parsed_13ga_exit_overhang_allocator_veto_overlap"
    interpretation = (
        "The parsed 13G/A exit-below-5% overhang context does not justify a "
        "future accepted-allocator veto: overlap is only "
        f"{overlap_count}/331 trades and removing those trades would reduce "
        f"accepted allocator PnL by ${abs(veto_delta_pnl):,.2f}."
    )

    gate4 = {
        "passed": False,
        "decision": decision,
        "failed_reasons": failed_reasons,
        "accepted_allocator_reference_experiment": "exp-20260611-005",
        "accepted_allocator_aggregate_ev_delta": allocator.get("gate4", {}).get("aggregate_ev_delta"),
        "accepted_allocator_aggregate_pnl_delta": allocator.get("gate4", {}).get("aggregate_pnl_delta"),
        "overlap_trade_count": overlap_count,
        "overlap_trade_count_min": MIN_OVERLAP_TRADES,
        "windows_with_overlap": windows_with_overlap,
        "target_window_count_min": MIN_WINDOW_COUNT,
        "vetoed_trade_pnl_sum": vetoed_pnl_sum,
        "counterfactual_veto_delta_pnl": veto_delta_pnl,
        "counterfactual_allocator_pnl_delta_after_veto": round(
            float(allocator.get("gate4", {}).get("aggregate_pnl_delta") or 0.0) + veto_delta_pnl,
            2,
        ),
        "expected_value_delta_after_veto": None,
        "expected_value_note": (
            "This read-only overlap test does not reconstruct the allocator daily "
            "equity curve, so EV/Sharpe acceptance is unavailable and the result "
            "cannot pass Gate 4."
        ),
    }

    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "trade_enabled": False,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": False,
        "parity_test_added": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_free_ohlcv": False,
        "uses_free_sec_ownership_text": True,
        "live_realism_evaluated": True,
        "live_ready": False,
        "execution_envelope": {
            "trade_enabled": False,
            "order_semantics": "no broker order; read-only veto overlap audit",
            "target_notional_per_paper_trade": 4000.0,
            "overhang_lookback_trading_days": OVERHANG_LOOKBACK_TRADING_DAYS,
            "portfolio_displacement": "accepted allocator paper rows only; no production displacement",
            "kill_switch": "not applicable because no helper or orders were promoted",
            "failure_handling": (
                "missing parsed 13G/A direction row, missing SPY trading calendar, "
                "future filing date, or event outside the fixed 10-trading-session "
                "lookback produces no veto tag"
            ),
        },
        "parity_note": (
            "No production code was changed. A positive result would still require "
            "a shared helper that exposes the parsed 13G/A exit-overhang tag in "
            "both historical replay and daily default-off snapshots."
        ),
    }

    post_run_reflection = {
        "why_result_happened": (
            "The ownership-exit context rarely intersects the accepted allocator, "
            "and the few overlapping trades are not the expected weak cohort. The "
            "largest overlap was old_thin AFRM, a strong winner; the veto would "
            "remove more winner PnL than loser PnL."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping 13G/A exit age, Big3/non-Big3 holder filters, "
            "stake-percent exits, allocator source ranks, top-N, hold days, "
            "cooldown, or paper notional on these frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs closed forward accepted-allocator replacement rows "
            "tagged with parsed ownership exits, richer holder/activist outcome "
            "provenance, or repaired structured-XML coverage that materially "
            "changes overlap."
        ),
    }

    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 0,
        "actual_gate4_passed": False,
        "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 4),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "failure_modes_observed": failed_reasons,
        "surprise_note": (
            "The main predicted failure mode occurred: overlap was too thin. The "
            "direction was worse than expected because the veto cohort had positive "
            "net PnL, so removing it would hurt rather than help."
        ),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "rejected",
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": (
            "Recent parsed non-Big3 Schedule 13G/A exit-below-5% events may "
            "identify ownership distribution overhang; accepted default-off "
            "allocator paper entries that overlap this context should underperform "
            "enough that a future shared veto could improve replacement value."
        ),
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": "production_visible_sec_ownership_overhang_context",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": [
            "exp-20260619-014",
            "exp-20260611-005",
            "exp-20260618-016",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "parsed_13ga_exit_below5_negative_overlap_context",
        "backtest_protocol": {
            "source": "read-only overlap attribution against accepted allocator artifact",
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "accepted_allocator_artifact": repo_rel(ALLOCATOR_ARTIFACT),
            "parsed_13ga_direction_surface": repo_rel(SURFACE_JSON),
            "overhang_lookback_trading_days": OVERHANG_LOOKBACK_TRADING_DAYS,
            "windows": allocator.get("backtest_protocol", {}).get("windows"),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/risk_allocation: parsed non-Big3 13G/A "
                "exit-below-5% events may be negative ownership-overhang context "
                "for accepted default-off allocator entries."
            ),
            "2_history_check": {
                "exp-20260619-014": (
                    "Built the parsed 13G/A direction surface; long-side increases "
                    "were weak, while non-Big3 drop-below-5% exits had negative "
                    "10-day context."
                ),
                "exp-20260611-005": (
                    "Current accepted source-priority allocator reference with "
                    "aggregate EV +2.1849 and PnL +$40,397.21."
                ),
                "novelty_gate": (
                    "Warned near accepted allocator arbitration families; override "
                    "recorded because this uses new parsed ownership-exit context, "
                    "not allocator source-rank or stake-threshold retuning."
                ),
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "A veto lead would need enough overlap across all three windows, "
                "positive aggregate and per-window veto PnL, no concentration issue, "
                "and later full Gate 1-4 EV replay through a shared helper."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260619_016_parsed_13ga_exit_overhang_allocator_overlap.py"
            ),
        },
        "prediction": PREDICTION,
        "calibration": calibration,
        "accepted_allocator_reference": {
            "experiment_id": "exp-20260611-005",
            "artifact": repo_rel(ALLOCATOR_ARTIFACT),
            "gate4": allocator.get("gate4"),
            "target_trade_summary": allocator.get("target_trade_summary"),
        },
        "surface_summary": {
            "source_experiment_id": surface.get("experiment_id"),
            "rows_total": len(surface.get("rows") or []),
            "exit_below5_non_big3_events": sum(len(rows) for rows in events_by_ticker.values()),
            "tickers_with_exit_below5_non_big3_events": len(events_by_ticker),
            "direction_distribution": surface.get("coverage", {}).get("direction_distribution"),
        },
        "overlap_attribution": {
            "all_trade_summary": summarize(all_pnls),
            "vetoed_trade_summary": summarize(veto_pnls),
            "non_vetoed_trade_summary": summarize(non_veto_pnls),
            "by_window": by_window,
            "source_family_count": dict(sorted(source_family_counter.items())),
            "overhang_age_trading_days_count": dict(sorted(age_counter.items(), key=lambda kv: int(kv[0]))),
            "vetoed_rows": vetoed_rows,
        },
        "gate4": gate4,
        "numeric_gate4_passed": False,
        "decision": decision,
        "interpretation": interpretation,
        "rejection_reason": "; ".join(failed_reasons),
        "next_retry_requires": [
            "closed forward allocator replacement rows tagged with parsed ownership exits",
            "richer holder or activist outcome provenance",
            "materially changed structured-XML coverage or overlap",
        ],
        "post_run_reflection": post_run_reflection,
        "production_impact": production_impact,
        "related_files": [
            f"quant/experiments/exp_20260619_016_{STEM}.py",
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["interpretation"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": payload["new_evidence_type"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "before_metrics": {
            "accepted_allocator_aggregate_ev_delta": payload["gate4"]["accepted_allocator_aggregate_ev_delta"],
            "accepted_allocator_aggregate_pnl_delta": payload["gate4"]["accepted_allocator_aggregate_pnl_delta"],
            "accepted_allocator_trade_count": payload["overlap_attribution"]["all_trade_summary"]["count"],
        },
        "after_metrics": {
            "counterfactual_veto_delta_pnl": payload["gate4"]["counterfactual_veto_delta_pnl"],
            "counterfactual_allocator_pnl_delta_after_veto": payload["gate4"][
                "counterfactual_allocator_pnl_delta_after_veto"
            ],
            "overlap_trade_count": payload["gate4"]["overlap_trade_count"],
        },
        "delta_metrics": {
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": payload["gate4"]["counterfactual_veto_delta_pnl"],
            "vetoed_trade_pnl_sum": payload["gate4"]["vetoed_trade_pnl_sum"],
        },
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "reproduce": (
            ".venv/Scripts/python.exe -B quant/experiments/"
            "exp_20260619_016_parsed_13ga_exit_overhang_allocator_overlap.py"
        ),
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Parsed 13G/A Exit Overhang Allocator Overlap",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Overlap trades: `{gate4['overlap_trade_count']}`",
            f"- Veto PnL delta: `${gate4['counterfactual_veto_delta_pnl']:,.2f}`",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons'])}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Result",
            "",
            payload["interpretation"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "allowed_write_scope": [
            f"quant/experiments/exp_20260619_016_{STEM}.py",
            repo_rel(OUT_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(LOG_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            f"quant/experiments/exp_20260619_016_{STEM}.py": sha256_file(Path(__file__)),
            repo_rel(OUT_JSON): sha256_file(OUT_JSON),
            repo_rel(LOG_JSON): sha256_file(LOG_JSON),
            repo_rel(CARD_MD): sha256_file(CARD_MD),
            repo_rel(TICKET_JSON): sha256_file(TICKET_JSON),
        },
        "anti_js": payload["anti_js"],
    }
    write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = build_log_record(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text(build_card(payload), encoding="utf-8")
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": False,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": payload["gate4"]["counterfactual_veto_delta_pnl"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": payload["gate4"]["counterfactual_veto_delta_pnl"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status="rejected",
        fields=fields,
    )
    write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "overlap_trade_count": payload["gate4"]["overlap_trade_count"],
                "counterfactual_veto_delta_pnl": payload["gate4"][
                    "counterfactual_veto_delta_pnl"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
