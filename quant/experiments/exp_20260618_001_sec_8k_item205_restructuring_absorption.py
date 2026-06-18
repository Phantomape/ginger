"""exp-20260618-001: SEC 8-K Item 2.05 restructuring absorption scout.

Replay-only alpha search. The single decision hypothesis is that PIT SEC
8-K Item 2.05 restructuring-cost events can become positive candidate-pool
events when signal-day price action absorbs the cost-reset announcement versus
SPY before next-open paper entry.

This is distinct from broad 8-K business-update labels, offering/prospectus
forms, NT late-filing notices, and proxy-pressure forms. The structured SEC
item code itself is the event source, and no LLM/text semantics are used. No
production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. A positive result is only a
replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import bisect
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260617_027_nonmanagement_proxy_pressure_absorption_scout as runner


EXPERIMENT_ID = "exp-20260618-001"
STEM = "sec_8k_item205_restructuring_absorption"
TRIAL_FAMILY = "free_sec_submissions_8k_restructuring_absorption_candidate_pool"
TRIAL_VARIANT_ID = "sec_8k_item205_restructuring_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_8k_item_205_restructuring_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = runner.REPO_ROOT
SUBMISSIONS_CACHE = runner.SUBMISSIONS_CACHE
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_001_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = runner.BASE_NOTIONAL_USD
HOLD_DAYS = runner.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = runner.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = runner.SAME_TICKER_COOLDOWN_DAYS

ITEM_CODE = "2.05"
EVENT_FORMS = {"8-K"}
EVENT_WEIGHT = 1.0

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.0
MIN_SIGNAL_EXCESS_SPY = 0.005
MIN_CLOSE_LOCATION = 0.56
MIN_VOLUME_RATIO_20D = 0.75
MAX_REALIZED_VOL_20D = 0.120
MIN_RET20_EXCESS_SPY = -0.050
MAX_EVENT_AGE_TRADING_DAYS = 3

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "restructuring_is_true_distress",
        "thin_sample",
        "old_thin_regression",
        "accepted_distribution_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "8-K Item 2.05 is a free PIT SEC submissions field with clearer "
        "economics than broad 8-K labels and enough cache coverage, but recent "
        "SEC event absorption scouts failed and restructuring announcements may "
        "reflect real distress rather than overhang relief."
    ),
    "recorded_at": "2026-06-18T00:05:07+00:00",
}

PRODUCTION_IMPACT = {
    **runner.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_sec_submissions": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **runner.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "missing SEC submissions cache, missing CIK mapping, missing "
            "8-K Item 2.05 event rows, missing OHLCV, missing next open, or "
            "missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "SEC 8-K Item 2.05 events, acceptance-time signal date, price-absorption "
        "gate, cooldown, next-open paper entry, 10-day exit, costs, and "
        "concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 8-K Item 2.05 restructuring-cost events are "
        "normally negative, but when signal-day price action absorbs the "
        "announcement versus SPY, the cost-reset/overhang-relief information "
        "may create a next-open 10-trading-day default-off paper candidate."
    ),
    "2_history_check": {
        "exp-20260610-013": (
            "Rejected generic 8-K business-update leadership labels. This run "
            "uses one structured item-code field with explicit restructuring "
            "cost economics, not broad 8-K item-code or phrase labels."
        ),
        "exp-20260617-023": (
            "Rejected SEC offering/prospectus price absorption. This run does "
            "not retry financing/prospectus forms or their thresholds."
        ),
        "exp-20260617-025": (
            "Rejected NT late-filing notice absorption. This run uses cost-reset "
            "8-K restructuring items, not disclosure-delay notices."
        ),
        "exp-20260617-027": (
            "Rejected non-management proxy-pressure absorption. This run uses "
            "issuer 8-K restructuring-cost provenance, not proxy solicitation "
            "or governance-pressure forms."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260618_001_sec_8k_item205_restructuring_absorption.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return runner.base._repo_rel(path)


def _has_item_205(raw: Any) -> bool:
    parts = [part.strip() for part in str(raw or "").replace(";", ",").split(",")]
    return ITEM_CODE in {part for part in parts if part}


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is not None:
        return _EVENT_INDEX_CACHE

    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    uri = f"file:{Path(runner.base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with runner.sqlite3.connect(uri, uri=True) as con:
        rows = con.execute(
            """
            select u.ticker, u.cik
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
              and u.cik is not null
            order by u.ticker
            """
        ).fetchall()
    for ticker, cik in rows:
        try:
            ticker_ciks[str(ticker).upper()] = int(cik)
        except (TypeError, ValueError):
            stats["invalid_cik_rows"] += 1

    index: dict[str, list[dict[str, Any]]] = {}
    for ticker, cik in ticker_ciks.items():
        path = SUBMISSIONS_CACHE / f"CIK{cik:010d}.json"
        stats["warehouse_tickers_with_cik"] += 1
        if not path.exists():
            stats["missing_submissions_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_submissions_cache_file"] += 1
            continue
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form") or []
        filing_dates = recent.get("filingDate") or []
        acceptance_times = recent.get("acceptanceDateTime") or []
        accessions = recent.get("accessionNumber") or []
        primary_docs = recent.get("primaryDocument") or []
        items = recent.get("items") or []
        events: list[dict[str, Any]] = []
        for i in range(min(len(forms), len(filing_dates))):
            form = str(forms[i] or "").upper()
            if form not in EVENT_FORMS:
                continue
            item_text = str(items[i] if i < len(items) else "")
            if not _has_item_205(item_text):
                continue
            filing_date = runner._d10(filing_dates[i])
            if not filing_date:
                continue
            accession = str(accessions[i]) if i < len(accessions) else ""
            primary_doc = str(primary_docs[i]) if i < len(primary_docs) else ""
            acceptance = str(acceptance_times[i]) if i < len(acceptance_times) else ""
            events.append(
                {
                    "ticker": ticker,
                    "cik": f"{cik:010d}",
                    "form": form,
                    "items": item_text,
                    "filing_date": filing_date,
                    "accepted_after_close": runner._acceptance_after_close(acceptance),
                    "acceptance_datetime": acceptance,
                    "accession_number": accession,
                    "primary_document": primary_doc,
                    "event_weight": EVENT_WEIGHT,
                }
            )
            stats[f"form_{form}_item_{ITEM_CODE}"] += 1
        if events:
            events.sort(key=lambda row: (row["filing_date"], row["form"], row["accession_number"]))
            index[ticker] = events
            stats["tickers_with_item205_events"] += 1
            stats["item205_event_count"] += len(events)

    summary = {
        "submissions_cache": _repo_rel(SUBMISSIONS_CACHE),
        "warehouse_source": _repo_rel(runner.base.framework.WAREHOUSE),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "event_forms": sorted(EVENT_FORMS),
        "item_code": ITEM_CODE,
        **dict(stats),
    }
    _EVENT_INDEX_CACHE = (index, summary)
    return _EVENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "sec_submissions_8k_item205_not_companyfacts",
    }


def _signal_date_for_event(event: dict[str, Any], dates: list[str]) -> str | None:
    filing_date = event["filing_date"]
    pos = (
        bisect.bisect_right(dates, filing_date)
        if event.get("accepted_after_close")
        else bisect.bisect_left(dates, filing_date)
    )
    if pos >= len(dates):
        return None
    signal_date = dates[pos]
    age = sum(1 for day in dates if filing_date <= day <= signal_date) - 1
    if age > MAX_EVENT_AGE_TRADING_DAYS:
        return None
    return signal_date


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: runner.base.framework.shadow._row_index(
            runner.base.framework.shadow._series(snapshot, ticker)
        )
        for ticker in snapshot
    }
    dates = runner.base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    scan: Counter[str] = Counter()
    scan["eligible_event_tickers"] = len(set(quality_index) & set(snapshot))
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = _signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_after_last_or_stale"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan[f"form_{event['form']}_item_{ITEM_CODE}"] += 1
            confirm = runner._absorption_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_absorption_or_liquidity_gate"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            score = (
                1.60 * float(confirm["candidate_signal_excess_spy"])
                + 0.40 * float(confirm["candidate_close_location"])
                + 0.25 * max(0.0, float(confirm["candidate_ret20_excess_spy"]))
                + 0.08
                * runner.math.log10(
                    max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0
                )
                + 0.20 * float(event["event_weight"])
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_8K_ITEM205_RESTRUCTURING_ABSORPTION_PAPER",
                    "candidate_score": runner._round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_8k_item205_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_submissions": True,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "item205_form": event["form"],
                    "item205_items": event["items"],
                    "item205_filing_date": event["filing_date"],
                    "item205_accepted_after_close": event["accepted_after_close"],
                    "item205_acceptance_datetime": event["acceptance_datetime"],
                    "item205_accession_number": event["accession_number"],
                    "item205_primary_document": event["primary_document"],
                    "item205_event_weight": event["event_weight"],
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["candidate_signal_excess_spy"] or 0.0),
            -float(row["candidate_close_location"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = scan["eligible_event_tickers"]
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "event_forms": sorted(EVENT_FORMS),
        "item_code": ITEM_CODE,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = runner.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= runner.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= runner.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= runner.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= runner.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = runner.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = runner.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_8k_item205_restructuring_absorption"
        if gate["passed"]
        else "rejected_sec_8k_item205_restructuring_absorption_candidate_pool"
    )
    return gate


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The SEC 8-K Item 2.05 restructuring absorption source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    return (
        "The SEC 8-K Item 2.05 restructuring absorption source did not clear "
        f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
        "The fixed bundle tested structured Item 2.05 restructuring-cost 8-K "
        "events plus signal-day SPY-relative price absorption. The result is "
        "not retained or promoted."
    )


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = _interpretation(payload)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_submissions_restructuring_candidate_pool",
            "new_evidence_type": "sec_submissions_8k_item205_with_price_absorption",
            "nearby_prior_experiments": [
                "exp-20260610-013",
                "exp-20260617-023",
                "exp-20260617-025",
                "exp-20260617-027",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "event_forms": sorted(EVENT_FORMS),
        "item_code": ITEM_CODE,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "SEC restructuring events are read from EDGAR submissions cache recent "
        "8-K filings where recent.items contains Item 2.05. The signal date is "
        "the filing date unless the SEC acceptance timestamp is after 16:00, in "
        "which case it is the next trading day. Candidates must show signal-day "
        "price absorption before next-open paper entry: non-negative daily "
        "return, return minus SPY >= 0.5%, close location >= 0.56, volume ratio "
        ">= 0.75, realized vol <= 12%, ret20 excess vs SPY >= -5%, price >= "
        "$10, and ADV20 >= $50M. Paper entry is the next available open with "
        "entry slippage; exit is the close 10 trading days after the signal "
        "with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["submissions_source"] = _repo_rel(SUBMISSIONS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "SEC submissions recent.form (8-K)",
        "SEC submissions recent.items containing 2.05",
        "SEC submissions recent.filingDate",
        "SEC submissions recent.acceptanceDateTime",
        "SEC submissions recent.accessionNumber",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed Item 2.05 restructuring absorption bundle fails, do not "
        "retry by sweeping 8-K/A inclusion, signal excess, close-location, "
        "volume, volatility, ret20, price/ADV, event-age, top-N, hold days, "
        "cooldown, or notional on these frozen windows. A valid retry needs "
        "materially richer PIT restructuring semantics such as explicit charge "
        "size, headcount/facility reduction, segment affected, recurring cost "
        "savings, cash/non-cash split, or closed forward replacement-value rows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping 8-K/A inclusion, signal excess, "
            "close-location, volume, volatility, ret20, price/ADV, event-age, "
            "top-N, hold days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Events | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in runner.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=sum(v for k, v in scan.items() if k.startswith("form_")),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC 8-K Item 2.05 Restructuring Absorption",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): runner.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): runner.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): runner.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): runner.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): runner.base.framework._sha256(CARD_MD),
        },
    }
    runner.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = runner.base._build_log_record(payload)
    runner.base.framework._write_json(OUT_JSON, payload)
    runner.base.framework._write_json(LOG_JSON, payload)
    runner.base.framework._write_text(CARD_MD, _build_card(payload))
    runner.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    runner.base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _install() -> None:
    runner.EXPERIMENT_ID = EXPERIMENT_ID
    runner.STEM = STEM
    runner.TRIAL_FAMILY = TRIAL_FAMILY
    runner.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    runner.CHANGED_VARIABLE = CHANGED_VARIABLE
    runner.RULE_VERSION = RULE_VERSION
    runner.OWNER = OWNER
    runner.OUT_DIR = OUT_DIR
    runner.OUT_JSON = OUT_JSON
    runner.LOG_JSON = LOG_JSON
    runner.TICKET_JSON = TICKET_JSON
    runner.CARD_MD = CARD_MD
    runner.MANIFEST_JSON = MANIFEST_JSON
    runner.EXPERIMENT_LOG = EXPERIMENT_LOG
    runner.REGISTRY_JSON = REGISTRY_JSON
    runner.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    runner.HOLD_DAYS = HOLD_DAYS
    runner.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    runner.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    runner.MIN_PRICE = MIN_PRICE
    runner.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    runner.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    runner.MIN_SIGNAL_EXCESS_SPY = MIN_SIGNAL_EXCESS_SPY
    runner.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    runner.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    runner.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    runner.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    runner.MAX_EVENT_AGE_TRADING_DAYS = MAX_EVENT_AGE_TRADING_DAYS
    runner.PREDICTION = PREDICTION
    runner.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    runner.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    runner._EVENT_INDEX_CACHE = None
    runner._load_event_index = _load_event_index
    runner._build_quality_index = _build_quality_index
    runner._candidate_rows_for_window = _candidate_rows_for_window
    runner._gate4 = _gate4
    runner._postprocess_payload = _postprocess_payload
    runner._build_card = _build_card
    runner._write_manifest = _write_manifest
    runner._persist = _persist


def main() -> None:
    _install()
    runner.main()


if __name__ == "__main__":
    main()
