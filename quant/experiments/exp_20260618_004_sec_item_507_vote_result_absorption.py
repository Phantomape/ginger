"""exp-20260618-004: SEC Item 5.07 vote-result absorption scout.

Replay-only alpha search. The single decision hypothesis is a PIT SEC text
candidate source: Item 5.07 shareholder-vote result filings with parsed strong
vote support may mark governance-overhang relief or institutional support when
the signal-day price action absorbs the disclosure versus SPY before next-open
paper entry.

This is intentionally distinct from rejected non-management proxy-pressure form
entries: it uses the actual vote-result text field from Item 5.07 filings, not
proxy solicitation form provenance alone. No production code, shared adapter,
live/default orders, ranking, sizing, exits, LLM/news path, or watchlist
behavior is changed. A positive replay is only a lead until a shared
historical/daily helper reproduces the same parser and paper envelope.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260617_027_nonmanagement_proxy_pressure_absorption_scout as template


base = template.base

EXPERIMENT_ID = "exp-20260618-004"
STEM = "sec_item_507_vote_result_absorption"
TRIAL_FAMILY = "sec_item_507_vote_result_absorption_candidate_pool"
TRIAL_VARIANT_ID = "item_507_management_support_vote_result_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_item_507_vote_result_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
SEC_EVENTS_FILE = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
SEC_TEXT_FILE = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
CANONICAL_BASELINE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.0
MIN_SIGNAL_EXCESS_SPY = 0.005
MIN_CLOSE_LOCATION = 0.56
MIN_VOLUME_RATIO_20D = 0.75
MAX_REALIZED_VOL_20D = 0.120
MIN_RET20_EXCESS_SPY = -0.050
MIN_VOTE_SUPPORT_MAX = 0.85
MIN_PARSED_VOTE_PAIRS = 1

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "governance_vote_results_are_routine",
        "old_thin_window_regression",
        "parsed_vote_support_too_noisy",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "This is not a generic 8-K item or proxy form retry: it uses Item 5.07 "
        "vote-result text as the new PIT semantic field requested after "
        "proxy-pressure failures. Risk is high because annual-meeting vote "
        "outcomes may be routine and already priced, but it is free, "
        "replayable, and distinct from raw Companyfacts/FINRA/13F."
    ),
    "recorded_at": "2026-06-18T03:11:14Z",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_text": True,
    "uses_free_sec_submissions": True,
    "uses_free_ohlcv": True,
    "uses_llm": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "missing Item 5.07 event row, missing matching filing text, failed "
            "vote-result parse, weak parsed vote support, missing OHLCV, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "SEC Item 5.07 event join, vote-result parser, price-absorption gate, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 8-K Item 5.07 shareholder-vote result filings "
        "with parsed strong vote support, plus liquid signal-day absorption "
        "versus SPY, may identify governance-overhang relief and institutional "
        "support before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260617-027": (
            "Rejected non-management proxy-pressure form absorption and named "
            "parsed vote outcome as materially richer PIT governance evidence. "
            "This run tests the actual Item 5.07 vote-result text, not proxy "
            "solicitation forms."
        ),
        "exp-20260612-015/016": (
            "Rejected 13D/13G ownership-disclosure entries. This run does not "
            "use ownership filings; it uses issuer 8-K vote-result text."
        ),
        "exp-20260610-013": (
            "Rejected generic 8-K business-update leadership labels. This run "
            "requires Item 5.07 plus parsed vote-support numbers, not broad "
            "8-K item-code labels."
        ),
        "exp-20260617-019/020/022": (
            "Rejected filing-timeliness variants. This run is not a filing-lag "
            "or timeliness sweep; it tests vote-result semantics."
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
        "exp_20260618_004_sec_item_507_vote_result_absorption.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _num(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _vote_support_from_text(text: str) -> dict[str, Any] | None:
    compact = re.sub(r"\s+", " ", str(text or " ").replace("\u00a0", " "))
    lowered = compact.lower()
    support_values: list[float] = []

    # Labeled proposal blocks, e.g. "Votes Cast For: 3,493,776,585 96.4 %
    # Votes Cast Against: 130,902,587 3.6 %".
    labeled = re.compile(
        r"votes(?:\s+cast)?\s+for\s*:?\s*([0-9][0-9,]*)"
        r"(?:\s+([0-9]+(?:\.[0-9]+)?)\s*%)?"
        r".{0,140}?"
        r"votes(?:\s+cast)?\s+against\s*:?\s*([0-9][0-9,]*)"
        r"(?:\s+([0-9]+(?:\.[0-9]+)?)\s*%)?",
        flags=re.IGNORECASE,
    )
    for match in labeled.finditer(compact):
        votes_for = _num(match.group(1))
        votes_against = _num(match.group(3))
        if votes_for is None or votes_against is None or votes_for + votes_against <= 0:
            continue
        support_values.append(votes_for / (votes_for + votes_against))

    # Common tabular pattern under "Votes For % For Votes Against % Against".
    table = re.compile(
        r"([0-9][0-9,]{2,})\s+([0-9]+(?:\.[0-9]+)?)\s*%\s+"
        r"([0-9][0-9,]{2,})\s+([0-9]+(?:\.[0-9]+)?)\s*%",
        flags=re.IGNORECASE,
    )
    for match in table.finditer(compact):
        context = compact[max(0, match.start() - 220) : match.start()].lower()
        if "votes for" not in context or "votes against" not in context:
            continue
        pct_for = _num(match.group(2))
        pct_against = _num(match.group(4))
        if pct_for is None or pct_against is None or pct_for + pct_against <= 0:
            continue
        support_values.append(pct_for / (pct_for + pct_against))

    if not support_values:
        return None
    support_values.sort(reverse=True)
    context_hits = [
        key
        for key in (
            "election of directors",
            "ratification",
            "independent auditor",
            "executive compensation",
            "advisory vote",
            "proposal",
            "board",
        )
        if key in lowered
    ]
    return {
        "parsed_vote_pair_count": len(support_values),
        "vote_support_max": _round(max(support_values), 6),
        "vote_support_mean_top3": _round(sum(support_values[:3]) / min(3, len(support_values)), 6),
        "vote_support_min": _round(min(support_values), 6),
        "management_context_hits": context_hits,
        "management_context_hit_count": len(context_hits),
    }


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is not None:
        return _EVENT_INDEX_CACHE

    stats: Counter[str] = Counter()
    text_by_accession: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(SEC_TEXT_FILE):
        accession = str(row.get("accession_number") or "")
        if not accession:
            continue
        text_by_accession[accession] = row
        stats["text_rows_read"] += 1

    index: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str]] = set()
    for event in _read_jsonl(SEC_EVENTS_FILE):
        ticker = str(event.get("ticker") or "").upper()
        accession = str(event.get("accession_number") or "")
        if not ticker or not accession:
            stats["events_missing_key"] += 1
            continue
        if (ticker, accession) in seen:
            stats["duplicate_event_rows"] += 1
            continue
        seen.add((ticker, accession))
        if str(event.get("form_type") or "").upper() != "8-K":
            stats["non_8k_skipped"] += 1
            continue
        item_codes = {str(code) for code in (event.get("eight_k_item_codes") or [])}
        if "5.07" not in item_codes:
            stats["non_item_507_skipped"] += 1
            continue
        text_row = text_by_accession.get(accession)
        if not text_row:
            stats["missing_text_join"] += 1
            continue
        vote = _vote_support_from_text(str(text_row.get("combined_text") or ""))
        if not vote:
            stats["vote_parse_failed"] += 1
            continue
        if int(vote["parsed_vote_pair_count"] or 0) < MIN_PARSED_VOTE_PAIRS:
            stats["too_few_parsed_vote_pairs"] += 1
            continue
        if float(vote["vote_support_max"] or 0.0) < MIN_VOTE_SUPPORT_MAX:
            stats["weak_vote_support"] += 1
            continue
        if int(vote["management_context_hit_count"] or 0) <= 0:
            stats["missing_management_context"] += 1
            continue
        row = {
            "ticker": ticker,
            "cik": str(event.get("cik") or ""),
            "form": str(event.get("form_type") or ""),
            "filing_date": str(event.get("filing_date") or "")[:10],
            "usable_trade_date": str(event.get("usable_trade_date") or "")[:10],
            "accepted_at": str(event.get("accepted_at") or ""),
            "accession_number": accession,
            "primary_document": str(event.get("primary_document") or ""),
            "archive_url": str(event.get("archive_url") or ""),
            "item_codes": sorted(item_codes),
            **vote,
        }
        if len(row["usable_trade_date"]) != 10:
            stats["missing_usable_trade_date"] += 1
            continue
        index.setdefault(ticker, []).append(row)
        stats["qualified_vote_result_events"] += 1
        stats[f"ticker_{ticker}"] += 1
    for events in index.values():
        events.sort(key=lambda row: (row["usable_trade_date"], row["accession_number"]))

    summary = {
        "sec_events_file": _repo_rel(SEC_EVENTS_FILE),
        "sec_text_file": _repo_rel(SEC_TEXT_FILE),
        "field_source": "sec_filing_events_plus_sec_filing_text_item_507_vote_result_parser",
        "candidate_universe_scope": "tickers_present_in_sec_filing_text_20241002_20260421",
        "min_vote_support_max": MIN_VOTE_SUPPORT_MAX,
        "min_parsed_vote_pairs": MIN_PARSED_VOTE_PAIRS,
        "tickers_with_vote_result_events": len(index),
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
        "uses_companyfacts": False,
    }


def _signal_date_for_event(event: dict[str, Any], dates: list[str]) -> str | None:
    signal_date = str(event.get("usable_trade_date") or "")[:10]
    if signal_date in dates:
        return signal_date
    return None


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    scan: Counter[str] = Counter()
    scan["eligible_event_tickers"] = len(set(quality_index) & set(snapshot))
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = _signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_missing_signal_date"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan["item_507_vote_result_events"] += 1
            confirm = template._absorption_confirmation(
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
            vote_support = float(event["vote_support_max"] or 0.0)
            vote_mean = float(event["vote_support_mean_top3"] or vote_support)
            score = (
                1.35 * float(confirm["candidate_signal_excess_spy"])
                + 0.36 * float(confirm["candidate_close_location"])
                + 0.22 * max(0.0, float(confirm["candidate_ret20_excess_spy"]))
                + 0.16 * vote_support
                + 0.10 * vote_mean
                + 0.05 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_ITEM_507_VOTE_RESULT_ABSORPTION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "item_507_vote_result_text_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_text": True,
                    "uses_free_sec_submissions": True,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "sec_item_507_accession_number": event["accession_number"],
                    "sec_item_507_filing_date": event["filing_date"],
                    "sec_item_507_accepted_at": event["accepted_at"],
                    "sec_item_507_primary_document": event["primary_document"],
                    "sec_item_507_archive_url": event["archive_url"],
                    "sec_item_507_item_codes": event["item_codes"],
                    "vote_support_max": event["vote_support_max"],
                    "vote_support_mean_top3": event["vote_support_mean_top3"],
                    "vote_support_min": event["vote_support_min"],
                    "parsed_vote_pair_count": event["parsed_vote_pair_count"],
                    "management_context_hits": event["management_context_hits"],
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
            -float(row["vote_support_max"] or 0.0),
            -float(row["candidate_signal_excess_spy"] or 0.0),
            -float(row["candidate_close_location"] or 0.0),
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
        "min_vote_support_max": MIN_VOTE_SUPPORT_MAX,
        "min_parsed_vote_pairs": MIN_PARSED_VOTE_PAIRS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_item_507_vote_result_absorption"
        if gate["passed"]
        else "rejected_sec_item_507_vote_result_absorption_candidate_pool"
    )
    return gate


def _load_canonical_baseline_metrics() -> dict[str, dict[str, Any]]:
    payload = json.loads(CANONICAL_BASELINE_ARTIFACT.read_text(encoding="utf-8"))
    by_window = payload.get("by_window") or {}
    metrics: dict[str, dict[str, Any]] = {}
    for label in base.framework.WINDOWS:
        window = by_window.get(label) or {}
        after = window.get("after") or {}
        if not after:
            raise RuntimeError(f"Missing canonical baseline metrics for {label}")
        metrics[label] = dict(after)
    return metrics


def _align_zero_trade_payload_to_canonical_baseline(payload: dict[str, Any]) -> dict[str, Any]:
    target_summary = base.framework.sleeve._target_trade_summary(payload["target_trades_by_window"])
    if int(target_summary.get("total_trade_count") or 0) != 0:
        raise RuntimeError(
            "This runner must be rerun from canonical per-window baseline results "
            "before evaluating a non-zero Item 5.07 overlay."
        )

    canonical = _load_canonical_baseline_metrics()
    window_rows: dict[str, dict[str, Any]] = {}
    for label in base.framework.WINDOWS:
        before = dict(canonical[label])
        after = dict(canonical[label])
        delta = base.framework.overlay_helper._delta(after, before)
        payload["before_metrics"][label] = before
        payload["after_metrics"][label] = after
        payload["delta_metrics"]["by_window"][label] = delta
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": 0,
            "raw_candidate_count": int(payload["raw_candidate_counts"].get(label) or 0),
            "overlay_total_pnl": 0.0,
            "overlay_day_count": 0,
        }

    aggregate = base.framework._aggregate_window_rows(window_rows)
    payload["target_trade_summary"] = target_summary
    payload["delta_metrics"]["aggregate"] = aggregate
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    payload["gate1"]["baseline_metrics"] = payload["before_metrics"]
    payload["gate1"]["baseline_artifact"] = _repo_rel(CANONICAL_BASELINE_ARTIFACT)
    payload["gate3"]["minimum_core_survival_rate"] = round(
        min(float(row.get("survival_rate") or 0.0) for row in payload["before_metrics"].values()),
        6,
    )
    payload["gate3"]["survival_rate_by_window"] = {
        label: payload["before_metrics"][label].get("survival_rate")
        for label in payload["before_metrics"]
    }
    payload["gate3"]["passed"] = payload["gate3"]["minimum_core_survival_rate"] >= 0.05
    payload["gate4"] = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=payload["before_metrics"],
    )
    payload.setdefault("measurement_notes", []).append(
        "No Item 5.07 paper trades were generated; before/after metrics are "
        "anchored to the current docs/backtesting.md canonical accepted-stack "
        "artifact."
    )
    return payload


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The SEC Item 5.07 vote-result absorption source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    return (
        "The SEC Item 5.07 vote-result absorption source did not clear Gate 4 "
        f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The fixed "
        "bundle tested parsed strong vote-result support plus signal-day "
        "SPY-relative price absorption. The result is not retained or promoted."
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
            "mechanism_family": "production_visible_sec_text_governance_vote_result_candidate_pool",
            "new_evidence_type": "sec_item_507_parsed_vote_result_support_with_price_absorption",
            "nearby_prior_experiments": [
                "exp-20260617-027",
                "exp-20260612-015",
                "exp-20260612-016",
                "exp-20260610-013",
                "exp-20260617-019",
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
        "min_vote_support_max": MIN_VOTE_SUPPORT_MAX,
        "min_parsed_vote_pairs": MIN_PARSED_VOTE_PAIRS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "candidate_universe": "sec_filing_text_20241002_20260421_ticker_set",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "SEC Item 5.07 vote-result events are joined from sec_filing_events and "
        "sec_filing_text aggregate PIT files. The parser requires at least one "
        "For/Against vote-result pair with max support >= 85% and management/"
        "proposal context. The signal date is the SEC usable_trade_date. "
        "Candidates must show signal-day price absorption before next-open "
        "paper entry: non-negative daily return, return minus SPY >= 0.5%, "
        "close location >= 0.56, volume ratio >= 0.75, realized vol <= 12%, "
        "ret20 excess vs SPY >= -5%, price >= $10, and ADV20 >= $50M. Paper "
        "entry is the next available open with entry slippage; exit is the close "
        "10 trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["sec_events_source"] = _repo_rel(SEC_EVENTS_FILE)
    payload["backtest_protocol"]["sec_text_source"] = _repo_rel(SEC_TEXT_FILE)
    payload["gate2"]["runtime_fields"] = [
        "sec_filing_events.form_type",
        "sec_filing_events.eight_k_item_codes",
        "sec_filing_events.usable_trade_date",
        "sec_filing_events.accession_number",
        "sec_filing_text.combined_text",
        "parsed vote For/Against support pairs",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed Item 5.07 vote-result absorption bundle fails, do not "
        "retry by sweeping vote-support thresholds, parser regexes, signal "
        "excess, close-location, volume, volatility, ret20, price/ADV, top-N, "
        "hold days, cooldown, or notional on these frozen windows. A valid "
        "retry needs materially richer PIT governance semantics such as parsed "
        "board-seat outcome, shareholder-proposal category, dissident identity, "
        "ownership stake, vote swing versus prior annual meeting, or closed "
        "forward replacement-value observations."
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
            "Do not retry by sweeping Item 5.07 vote-support thresholds, parser "
            "regexes, signal excess, close-location, volume, volatility, ret20, "
            "price/ADV, top-N, hold days, cooldown, or notional on these windows."
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
    for label in base.framework.WINDOWS:
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
                events=scan.get("item_507_vote_result_events", 0),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Item 5.07 Vote-Result Absorption",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _configure_template() -> None:
    template.EXPERIMENT_ID = EXPERIMENT_ID
    template.STEM = STEM
    template.TRIAL_FAMILY = TRIAL_FAMILY
    template.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    template.CHANGED_VARIABLE = CHANGED_VARIABLE
    template.RULE_VERSION = RULE_VERSION
    template.OWNER = OWNER
    template.OUT_DIR = OUT_DIR
    template.OUT_JSON = OUT_JSON
    template.LOG_JSON = LOG_JSON
    template.TICKET_JSON = TICKET_JSON
    template.CARD_MD = CARD_MD
    template.MANIFEST_JSON = MANIFEST_JSON
    template.EXPERIMENT_LOG = EXPERIMENT_LOG
    template.REGISTRY_JSON = REGISTRY_JSON
    template.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    template.HOLD_DAYS = HOLD_DAYS
    template.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    template.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    template.MIN_PRICE = MIN_PRICE
    template.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    template.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    template.MIN_SIGNAL_EXCESS_SPY = MIN_SIGNAL_EXCESS_SPY
    template.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    template.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    template.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    template.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._load_event_index = _load_event_index
    template._build_quality_index = _build_quality_index
    template._candidate_rows_for_window = _candidate_rows_for_window
    template._gate4 = _gate4
    template._configure_base()


def main() -> None:
    _configure_template()
    payload = _align_zero_trade_payload_to_canonical_baseline(base._build_payload())
    payload = _postprocess_payload(payload)
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
