"""exp-20260708-009: SEC Item 2.05/2.06 restructuring entry-risk scout.

Read-only alpha-search experiment. The single decision hypothesis is that SEC
8-K Item 2.05 exit/disposal-cost disclosures and Item 2.06 impairment
disclosures identify near-term entry risk: liquid tickers with Item 2.05/2.06
should underperform over the next 10 sessions, supporting a default-off entry
risk gate rather than a long candidate source.

No production path, default orders, ranking, sizing, exits, LLM boundary,
watchlist, or shared policy is changed.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260707_019_sec_nt_late_filing_notice_entry_risk as base


EXPERIMENT_ID = "exp-20260708-009"
OWNER = "alpha-explore"
SLUG = "sec_item205206_restructuring_impairment_entry_risk"
RUNNER = f"quant/experiments/exp_20260708_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = base.REPO_ROOT
if str(base.SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(base.SCRIPTS_ROOT))

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260708_009_{SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

ITEM_CODES = {"2.05", "2.06"}
ITEM_FORMS = {"8-K", "8-K/A"}
MIN_SUPPORT_EVENTS_PER_WINDOW = 10
MIN_TOTAL_LIQUID_EVENTS = 30
MAX_SINGLE_TICKER_SHARE = 0.40

HYPOTHESIS = (
    "entry_filter/risk_allocation: SEC 8-K Item 2.05 exit/disposal-cost and "
    "Item 2.06 impairment disclosures are PIT restructuring or asset-"
    "deterioration events; liquid tickers with Item 2.05/2.06 should "
    "underperform over the next 10 sessions, supporting a default-off entry "
    "risk gate rather than a long candidate source."
)
CHANGE_TYPE = "entry_filter"
IMPLEMENTATION_MODE = "private_replay_scout"
MECHANISM_FAMILY = "free_sec_restructuring_impairment_entry_risk"
TRIAL_FAMILY = "sec_8k_item205206_restructuring_impairment_entry_risk"
TRIAL_VARIANT_ID = "item205206_next_open_10d_v1"
CHANGED_VARIABLE = "sec_8k_item205206_restructuring_impairment_10d_entry_risk_gate_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_sec_8k_item205206_restructuring_impairment"
NEW_EVIDENCE_AXIS = (
    "New gate shape: direct same-ticker SEC 8-K Item 2.05 exit/disposal-cost "
    "and Item 2.06 impairment next-open 10d entry-risk attribution. Prior NT "
    "late-filing, Item 3.01 listing-compliance, and Item 5.02 leadership "
    "experiments tested different disclosure items or text semantics, not "
    "restructuring/impairment event-risk."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260707-019",
    "exp-20260707-020",
    "exp-20260708-003",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def item_codes(value: Any) -> list[str]:
    return re.findall(r"\b\d\.\d{2}\b", str(value or ""))


def repo_rel(path: Path | str) -> str:
    return base.repo_rel(path)


def load_ticket_prediction() -> dict[str, Any]:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    return ticket.get("prediction") or {}


def load_item205206_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cik_ticker = base.load_cik_ticker_map()
    paths = sorted(base.SEC_SUBMISSIONS_ROOT.glob("CIK*.json"))
    paths += sorted((base.SEC_SUBMISSIONS_ROOT / "files").glob("CIK*.json"))
    events: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str, str]] = set()
    parse_errors = 0

    for path in paths:
        match = re.search(r"CIK(\d{10})", path.name)
        cik = match.group(1) if match else None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parse_errors += 1
            continue

        ticker = None
        if isinstance(payload, dict):
            tickers = payload.get("tickers") or []
            if tickers:
                ticker = str(tickers[0]).upper()
        ticker = ticker or (cik_ticker.get(cik) if cik else None)

        data = (payload.get("filings") or {}).get("recent") if isinstance(payload, dict) else None
        if data is None:
            data = payload
        if not isinstance(data, dict):
            continue

        forms = data.get("form") or []
        filing_dates = data.get("filingDate") or []
        report_dates = data.get("reportDate") or []
        accessions = data.get("accessionNumber") or []
        acceptances = data.get("acceptanceDateTime") or []
        primary_docs = data.get("primaryDocument") or []
        items = data.get("items") or []

        for index, raw_form in enumerate(forms):
            form = base._normalise_form(raw_form)
            if form not in ITEM_FORMS:
                continue
            raw_items = str(items[index] if index < len(items) else "")
            codes = item_codes(raw_items)
            matched_codes = sorted(set(codes) & ITEM_CODES)
            if not matched_codes:
                continue
            filing_date = base._safe_date(
                filing_dates[index] if index < len(filing_dates) else ""
            )
            window = base._window_for(filing_date)
            if not window:
                continue
            accession = str(accessions[index] if index < len(accessions) else "")
            key = (ticker, cik, accession, filing_date)
            if key in seen:
                continue
            seen.add(key)
            events.append(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "form_type": form,
                    "filing_date": filing_date,
                    "report_date": base._safe_date(
                        report_dates[index] if index < len(report_dates) else ""
                    ),
                    "accepted_at": str(
                        acceptances[index] if index < len(acceptances) else ""
                    ),
                    "accession_number": accession,
                    "primary_document": str(
                        primary_docs[index] if index < len(primary_docs) else ""
                    ),
                    "items_raw": raw_items,
                    "item_codes": codes,
                    "matched_item_codes": matched_codes,
                    "window": window,
                    "source_cache_file": repo_rel(path),
                }
            )

    diagnostics = {
        "cache_files_scanned": len(paths),
        "parse_errors": parse_errors,
        "raw_item205206_count": len(events),
        "raw_by_window": dict(Counter(row["window"] for row in events)),
        "raw_by_matched_item_code": dict(
            Counter(code for row in events for code in row["matched_item_codes"])
        ),
        "raw_unique_tickers": len({row["ticker"] for row in events if row.get("ticker")}),
        "raw_missing_ticker": sum(1 for row in events if not row.get("ticker")),
        "raw_top_item_combos": Counter(row["items_raw"] for row in events).most_common(10),
    }
    return sorted(events, key=lambda row: (row["filing_date"], row.get("ticker") or "")), diagnostics


def summarize_item205206_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    summary = base.summarize_trades(trades)
    supporting_windows: list[str] = []

    for label in base.WINDOWS:
        row = summary["by_window"][label]
        if (
            row["trade_count"] >= MIN_SUPPORT_EVENTS_PER_WINDOW
            and row["mean_net_long_return"] is not None
            and row["mean_net_long_return"] < 0
            and row["mean_excess_vs_same_ticker_unconditional"] is not None
            and row["mean_excess_vs_same_ticker_unconditional"] < 0
            and (
                row["max_single_ticker_share"] is None
                or row["max_single_ticker_share"] <= MAX_SINGLE_TICKER_SHARE
            )
        ):
            supporting_windows.append(label)
    summary["aggregate"]["supporting_windows"] = supporting_windows
    return summary


def build_payload() -> dict[str, Any]:
    events, event_diagnostics = load_item205206_events()
    tickers = {str(row["ticker"]).upper() for row in events if row.get("ticker")}
    prices = base.load_prices(tickers)
    trades, replay_diagnostics = base.replay_events(events, prices)
    summary = summarize_item205206_trades(trades)
    prediction = load_ticket_prediction()
    baseline_metrics = base.load_baseline_metrics()

    aggregate = summary["aggregate"]
    supporting_windows = aggregate["supporting_windows"]
    failed_reasons: list[str] = []
    if aggregate["trade_count"] < MIN_TOTAL_LIQUID_EVENTS:
        failed_reasons.append("liquid_sample_below_min_total")
    if len(supporting_windows) < 2:
        failed_reasons.append("event_drift_not_negative_in_two_windows")
    if aggregate["mean_net_long_return"] is None:
        failed_reasons.append("aggregate_long_drift_missing")
    elif aggregate["mean_net_long_return"] >= 0:
        failed_reasons.append("aggregate_long_drift_positive")
    if aggregate["mean_excess_vs_same_ticker_unconditional"] is None:
        failed_reasons.append("aggregate_excess_missing")
    elif aggregate["mean_excess_vs_same_ticker_unconditional"] >= 0:
        failed_reasons.append("aggregate_excess_not_negative")
    if (
        aggregate["max_single_ticker_share"] is not None
        and aggregate["max_single_ticker_share"] > MAX_SINGLE_TICKER_SHARE
    ):
        failed_reasons.append("ticker_concentration_too_high")

    support_lead = not failed_reasons
    decision = (
        "observed_positive_lead_sec_item205206_entry_risk_gate"
        if support_lead
        else "rejected_sec_item205206_entry_risk_gate"
    )
    status = "observed_only_positive_lead" if support_lead else "rejected"
    actual_success = 1 if support_lead else 0
    predicted_p = float(prediction.get("success_probability") or 0.0)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": support_lead,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_p,
            "brier_score": base.rounded((actual_success - predicted_p) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(failed_reasons)
            ),
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
        },
        "parameters": {
            "forms": sorted(ITEM_FORMS),
            "item_codes": sorted(ITEM_CODES),
            "hold_days": base.HOLD_DAYS,
            "round_trip_cost_pct": base.ROUND_TRIP_COST_PCT,
            "notional_usd": base.NOTIONAL_USD,
            "entry_policy": "next_session_open_after_filing_date",
            "exit_policy": "close_after_10_trading_sessions",
            "min_entry_price": base.MIN_ENTRY_PRICE,
            "min_adv20_usd": base.MIN_ADV20_USD,
            "same_ticker_cooldown_sessions": base.SAME_TICKER_COOLDOWN_SESSIONS,
            "support_rule": (
                "Positive lead only if >=30 total liquid events, at least two "
                "canonical windows have >=10 events with negative mean 10d net "
                "long return and negative same-ticker excess return, and ticker "
                "concentration is <=40%. Otherwise rejected; no behavior changes."
            ),
            "windows": base.WINDOWS,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new blocked broad SEC event/text neighbors; "
                    "override was recorded with a legal new gate shape: direct "
                    "same-ticker Item 2.05/2.06 restructuring and impairment "
                    "entry-risk attribution."
                ),
                "exp-20260707-019": (
                    "NT late-filing notice entry-risk scout; same SEC event-study "
                    "recipe but different disclosure-delay form family."
                ),
                "exp-20260707-020": (
                    "Direct Item 3.01 listing-noncompliance entry-risk scout; "
                    "not restructuring or impairment."
                ),
                "exp-20260708-003": (
                    "Item 5.02 leadership-quality text; not item-code "
                    "restructuring/impairment event risk."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Use the predeclared source-validation rule in parameters; "
                "this is replay-only, so a positive result would still need a "
                "shared helper plus full Gate 4 before any production entry gate."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": base.BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(base.BASELINE_RESULT),
            "baseline_metrics": baseline_metrics,
            "accepted_reference": {
                "expected_value_score_sum": 7.8941,
                "total_pnl_sum": 234850.99,
                "trade_count_sum": 61,
            },
        },
        "gate2": {
            "runtime_fields_checked": [
                "filing_date",
                "form_type",
                "item_codes",
                "matched_item_codes",
                "ticker",
                "entry_date",
                "entry_open",
                "exit_date",
                "exit_close",
                "adv20_usd",
            ],
            "missing_entry_date": sum(1 for row in trades if not row.get("entry_date")),
            "missing_exit_date": sum(1 for row in trades if not row.get("exit_date")),
            "target_price_relevance": (
                "No generated strategy signals are emitted; target_price is "
                "not consumed by this read-only event study. A later shared "
                "entry gate must re-run the normal signal contract checks."
            ),
            "passed": all(row.get("entry_date") and row.get("exit_date") for row in trades),
        },
        "gate3": {
            "new_entry_filter_added": False,
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "note": (
                "Attribution only; no filter applied, so baseline survival is "
                "unchanged and Gate 3 is informational."
            ),
            "passed": True,
        },
        "gate4": {
            "applicable": False,
            "passed": support_lead,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "supporting_windows": supporting_windows,
            "aggregate_mean_net_long_return": aggregate["mean_net_long_return"],
            "aggregate_mean_excess_vs_same_ticker_unconditional": aggregate[
                "mean_excess_vs_same_ticker_unconditional"
            ],
            "aggregate_total_long_pnl_usd": aggregate["total_long_pnl_usd"],
            "aggregate_total_risk_gate_avoided_loss_usd": aggregate[
                "total_risk_gate_avoided_loss_usd"
            ],
            "liquid_trade_count": aggregate["trade_count"],
            "note": (
                "No before/after strategy behavior changed. The source-validation "
                "rule must pass before any shared-helper Gate 4 follow-up."
            ),
        },
        "data_diagnostics": {**event_diagnostics, **replay_diagnostics},
        "event_study": summary,
        "sample_trades": trades[:50],
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "daily_snapshot_exposed": False,
            "default_off_paper_only": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only offline source validation over SEC cached submissions "
                "and warehouse OHLCV. No production/backtest behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The direct Item 2.05/2.06 surface did not produce broad negative "
                "deployable event drift after liquidity gates, or failed the "
                "predeclared support/concentration rule."
            )
            if not support_lead
            else (
                "Item 2.05/2.06 restructuring or impairment events showed broad "
                "negative event drift and deserve a shared-helper Gate 4 follow-up."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune price, ADV, hold days, cooldown, same-day ranking, "
                "2.05-vs-2.06 sub-slices, item-combination slices, or response "
                "functions on these same cached rows. A long-source inversion "
                "also needs a new gate shape."
            ),
            "new_evidence_required": (
                "A legal retry needs materially new Item 2.05/2.06 rows, "
                "text-provenance separating true impairment/restructuring from "
                "disposal accounting updates, or a different restructuring data "
                "source."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "next_retry_requires": [
            "materially new Item 2.05/2.06 rows",
            "or text-provenance separating true impairment/restructuring events",
            "or a different restructuring data source",
        ],
        "before_after_strategy_behavior_changed": False,
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(base.BASELINE_RESULT),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def make_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: SEC Item 2.05/2.06 restructuring entry-risk scout",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        HYPOTHESIS,
        "",
        "| Window | Trades | Mean long ret | Mean excess | Long PnL | Avoided-loss PnL | Negative share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        row = payload["event_study"]["by_window"][label]
        lines.append(
            f"| {label} | {row['trade_count']} | {row['mean_net_long_return']} | "
            f"{row['mean_excess_vs_same_ticker_unconditional']} | "
            f"{row['total_long_pnl_usd']} | "
            f"{row['total_risk_gate_avoided_loss_usd']} | "
            f"{row['negative_return_share']} |"
        )
    gate4 = payload["gate4"]
    lines += [
        "",
        f"Raw Item 2.05/2.06 rows: {payload['data_diagnostics']['raw_item205206_count']}; "
        f"liquid replay trades: {gate4['liquid_trade_count']}; "
        f"failed reasons: {gate4['failed_reasons']}.",
        "",
        "No behavior changed. A positive source-validation result would still "
        "need shared-helper Gate 4 before any production entry gate.",
    ]
    return "\n".join(lines) + "\n"


def make_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [Path(RUNNER), OUT_JSON, LOG_JSON, CARD_MD, MANIFEST_JSON, TICKET_JSON]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "files": [
            {
                "path": repo_rel(path if path.is_absolute() else REPO_ROOT / path),
                "exists": (path if path.is_absolute() else REPO_ROOT / path).exists(),
                "sha256": base.sha256(path if path.is_absolute() else REPO_ROOT / path),
            }
            for path in paths
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    base.write_json(OUT_JSON, payload)
    base.write_text(CARD_MD, make_card(payload))
    base.write_json(LOG_JSON, payload)
    base.append_jsonl(EXPERIMENT_LOG, payload)
    base.write_json(MANIFEST_JSON, make_manifest(payload))
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "accepted_alpha": payload["accepted_alpha"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "status": payload["status"],
                "gate4": payload["gate4"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
