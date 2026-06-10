"""exp-20260610-023: SEC contract-demand text leadership candidate pool.

Replay-only alpha search. This tests one fixed candidate-source variable:
SEC 8-K filing text with explicit contract, order, backlog, customer-demand,
or supply-agreement evidence, paired with signal-date liquid SPY-relative
leadership before a top-1 next-open default-off paper entry with a fixed
10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260610_013_sec_business_update_event_leadership as previous


framework = previous.framework
base = previous.base

EXPERIMENT_ID = "exp-20260610-023"
STEM = "sec_contract_demand_text_leadership"
TRIAL_FAMILY = "sec_contract_demand_text_leadership_candidate_pool"
TRIAL_VARIANT_ID = "sec_contract_demand_text_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_contract_demand_text_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_023_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SEC_TEXT_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
)

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

BUSINESS_UPDATE_EVENT_SUBTYPES = ("1.01", "7.01", "8.01")
ITEM_CODE_WEIGHTS = {"1.01": 1.20, "8.01": 1.00, "7.01": 0.95}
MIN_SEMANTIC_SCORE = 1.0

CONTRACT_DEMAND_PATTERNS: tuple[str, ...] = (
    r"\brecord backlog\b",
    r"\border backlog\b",
    r"\bbacklog\b",
    r"\bbookings\b",
    r"\bcustomer demand\b",
    r"\bdemand remains strong\b",
    r"\bstrong demand\b",
    r"\brobust demand\b",
    r"\bcustomer wins?\b",
    r"\bnew customers?\b",
    r"\bselected by\b",
    r"\bselects\b",
    r"\bcontract award(?:ed)?\b",
    r"\bawarded (?:a |an )?contract\b",
    r"\bpurchase orders?\b",
    r"\bcommercial agreement\b",
    r"\bsupply agreement\b",
    r"\bdistribution agreement\b",
    r"\bmaster services agreement\b",
    r"\bmulti[- ]year (?:agreement|contract|supply|partnership)\b",
    r"\bstrategic (?:partnership|collaboration)\b",
)
EXCLUSION_PATTERNS: tuple[str, ...] = (
    r"\bpublic offering\b",
    r"\bregistered direct\b",
    r"\bprivate placement\b",
    r"\bat[- ]the[- ]market\b",
    r"\batm offering\b",
    r"\bshelf registration\b",
    r"\bresale registration\b",
    r"\bsecurities purchase agreement\b",
    r"\bequity financing\b",
    r"\bconvertible (?:note|notes|debt|preferred)\b",
    r"\bsenior notes?\b",
    r"\bcredit agreement\b",
    r"\bdebt offering\b",
    r"\bwarrants?\b",
    r"\bdilution\b",
    r"\bgoing concern\b",
    r"\bbankruptcy\b",
    r"\btermination\b",
    r"\bterminated\b",
    r"\bmerger agreement\b",
    r"\bemployment agreement\b",
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "thin_text_sample",
        "generic_contract_language",
        "window_regression",
        "drawdown_drift",
        "compression_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Broad SEC item-code labels failed in exp-20260610-013, and the older "
        "SEC customer-contract text source failed in exp-20260603-012. This "
        "run is materially different because it requires explicit PIT filing "
        "text evidence plus the current liquid leadership, next-open, cost, "
        "cooldown, and accepted-compression comparator envelope. Success odds "
        "remain low because SEC contract language is sparse and can still be "
        "boilerplate or already priced."
    ),
    "recorded_at": "2026-06-10T21:08:56+00:00",
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
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_filing_text": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead. Promotion would require a shared default-off adapter "
        "that loads the same PIT SEC filing text rows, applies the exact same "
        "contract-demand pattern set and exclusions, uses the same signal-date "
        "OHLCV leadership gates, overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, comparator, and concentration "
        "guards in historical replay and daily production before any report "
        "queue, paper ledger, candidate priority, sizing, watchlist, or order "
        "surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 8-K filings with explicit contract/order/backlog/"
        "customer-demand filing-text evidence, when paired with same-day liquid "
        "SPY-relative leadership, may identify business-momentum underreaction "
        "candidates whose next-open 10d paper continuation beats generic SEC "
        "business-update labels."
    ),
    "2_history_check": {
        "exp-20260610-013": (
            "Rejected broad 8-K Item 1.01/7.01/8.01 business-update labels; "
            "the failure lesson asked for richer PIT event-strength text fields."
        ),
        "exp-20260603-012": (
            "Rejected customer-contract / demand-backlog text source. It lacked "
            "the current liquid leadership envelope and accepted-compression "
            "comparator used here."
        ),
        "exp-20260605-006": (
            "Rejected Ex-99/business-development source-span variant; mid/old "
            "improved but late regressed, drawdown and concentration failed."
        ),
        "exp-20260605-031": (
            "Rejected inverse SEC business-win sleeve; direct SEC text phrasing "
            "did not create a stable long or inverse signal."
        ),
        "exp-20260608-013": (
            "Accepted compression helper is the stock-candidate comparator this "
            "SEC text scout must beat before any promotion pressure."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT SEC filing text semantic keyword evidence "
        "for contract/order/backlog/customer-demand/supply agreement, fixed "
        "offering/debt/negative exclusions, 8-K Item 1.01/7.01/8.01, liquid "
        "sector-known stock universe, existing 20d/60d SPY-relative leadership "
        "gates, same-ticker core-overlap exclusion, top-1 next-open paper entry, "
        "10-day hold, cost, cooldown, and concentration gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and exp-20260608-013 "
        "accepted compression comparator is beaten. Production retention still "
        "requires a shared default-off helper."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_023_sec_contract_demand_text_leadership.py"
    ),
}

_TEXT_EVENT_CACHE: dict[str, Any] | None = None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if raw:
        return {
            part.strip()
            for part in str(raw).replace(";", ",").split(",")
            if part.strip()
        }
    return set()


def _pattern_matches(text: str, patterns: tuple[str, ...]) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    for pattern in patterns:
        matches.extend(re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL))
    return matches


def _snippets(text: str, matches: list[re.Match[str]], *, limit: int = 3) -> list[str]:
    snippets: list[str] = []
    compact = re.sub(r"\s+", " ", text).strip()
    lowered = compact.lower()
    for match in matches[:limit]:
        needle = match.group(0).lower()
        pos = lowered.find(needle)
        if pos < 0:
            continue
        start = max(pos - 90, 0)
        end = min(pos + len(needle) + 140, len(compact))
        snippets.append(compact[start:end])
    return snippets


def _semantic_event_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper().strip()
    usable_date = str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]
    if not ticker or not usable_date:
        return None
    if str(row.get("status") or "ok").lower() not in {"ok", ""}:
        return None
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    if "8-K" not in form_type:
        return None
    item_codes = _item_codes(row)
    if not item_codes.intersection(BUSINESS_UPDATE_EVENT_SUBTYPES):
        return None
    text = str(row.get("combined_text") or "")
    if not text:
        return None
    lowered = text.lower()
    positive_matches = _pattern_matches(lowered, CONTRACT_DEMAND_PATTERNS)
    exclusion_matches = _pattern_matches(lowered, EXCLUSION_PATTERNS)
    if not positive_matches or exclusion_matches:
        return None
    semantic_score = float(len(positive_matches))
    semantic_score += max(ITEM_CODE_WEIGHTS.get(code, 0.0) for code in item_codes)
    if "1.01" in item_codes:
        semantic_score += 0.15
    if len({match.group(0).lower() for match in positive_matches}) >= 2:
        semantic_score += 0.20
    if semantic_score < MIN_SEMANTIC_SCORE:
        return None
    source_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return {
        "ticker": ticker,
        "usable_trade_date": usable_date,
        "filing_date": str(row.get("filing_date") or "")[:10],
        "accepted_at": row.get("accepted_at"),
        "accession_number": row.get("accession_number"),
        "primary_document": row.get("primary_document"),
        "form_type": form_type,
        "item_codes": sorted(item_codes),
        "semantic_score": round(semantic_score, 6),
        "contract_demand_hit_count": len(positive_matches),
        "contract_demand_unique_hits": sorted(
            {match.group(0).lower() for match in positive_matches}
        )[:10],
        "exclusion_hit_count": len(exclusion_matches),
        "evidence_snippets": _snippets(text, positive_matches),
        "text_word_count": row.get("text_word_count"),
        "text_char_count": row.get("text_char_count"),
        "source_text_hash": source_hash,
        "pit_source": row.get("pit_source"),
        "pit_caveat": row.get("pit_caveat"),
    }


def _load_text_events() -> dict[str, Any]:
    global _TEXT_EVENT_CACHE
    if _TEXT_EVENT_CACHE is not None:
        return _TEXT_EVENT_CACHE

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    scan = Counter()
    examples: list[dict[str, Any]] = []
    if not SEC_TEXT_PATH.exists():
        _TEXT_EVENT_CACHE = {
            "by_date_ticker": by_date_ticker,
            "scan": {"text_file_missing": True, "path": _repo_rel(SEC_TEXT_PATH)},
            "examples": examples,
        }
        return _TEXT_EVENT_CACHE

    with SEC_TEXT_PATH.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            scan["text_rows_loaded"] += 1
            row = json.loads(line)
            if "8-K" in str(row.get("form_type") or row.get("form_base") or "").upper():
                scan["eight_k_rows"] += 1
            item_codes = _item_codes(row)
            if item_codes.intersection(BUSINESS_UPDATE_EVENT_SUBTYPES):
                scan["item_code_passed_rows"] += 1
            event = _semantic_event_from_row(row)
            if event is None:
                continue
            scan["semantic_passed_rows"] += 1
            by_date_ticker.setdefault(event["usable_trade_date"], {}).setdefault(
                event["ticker"], []
            ).append(event)
            if len(examples) < 12:
                examples.append(
                    {
                        "date": event["usable_trade_date"],
                        "ticker": event["ticker"],
                        "semantic_score": event["semantic_score"],
                        "item_codes": event["item_codes"],
                        "hits": event["contract_demand_unique_hits"][:5],
                        "accession_number": event["accession_number"],
                    }
                )

    _TEXT_EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": {**dict(scan), "source_text_file": _repo_rel(SEC_TEXT_PATH)},
        "examples": examples,
    }
    return _TEXT_EVENT_CACHE


def _text_events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_text_events()["by_date_ticker"].get(signal_date, {})


def _candidate_for_contract_text_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    row = base._candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        month_label="sec_contract_demand_text",
    )
    if row is None:
        return None

    top_event = sorted(
        events,
        key=lambda event: (
            -float(event.get("semantic_score") or 0.0),
            -int(event.get("contract_demand_hit_count") or 0),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    row["source"] = "SEC_CONTRACT_DEMAND_TEXT_LEADERSHIP_PAPER"
    row.pop("candidate_month_label", None)
    row["candidate_contract_text_score"] = top_event["semantic_score"]
    row["candidate_contract_text_event_count"] = len(events)
    row["candidate_contract_text_hits"] = top_event["contract_demand_unique_hits"][:8]
    row["candidate_contract_text_item_codes"] = top_event["item_codes"]
    row["candidate_contract_text_accession"] = top_event["accession_number"]
    row["candidate_contract_text_primary_document"] = top_event["primary_document"]
    row["candidate_contract_text_evidence_snippets"] = top_event["evidence_snippets"][:3]
    row["candidate_contract_text_source_hash"] = top_event["source_text_hash"]
    row["candidate_contract_text_pit_source"] = top_event["pit_source"]
    row["uses_free_ohlcv_only"] = False
    row["uses_free_sec_filing_text"] = True
    row["known_at"] = "signal_date_sec_filing_text_and_ohlcv_before_next_open_paper_entry"
    row["rule_version"] = RULE_VERSION
    return row


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    all_dates = framework.shadow._trading_dates(snapshot)
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    hit_distribution: Counter[str] = Counter()
    item_distribution: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_contract_text_tickers": 0,
        "contract_text_tickers": 0,
        "days_with_raw_contract_text_candidates": 0,
        "raw_contract_text_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        "source_text_scan": _load_text_events()["scan"],
        "source_text_examples": _load_text_events()["examples"][:12],
    }

    for signal_date in dates:
        events_by_ticker = _text_events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_contract_text_tickers"] += 1
        scan["contract_text_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_contract_text_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                continue
            for hit in row["candidate_contract_text_hits"]:
                hit_distribution[hit] += 1
            for item_code in row["candidate_contract_text_item_codes"]:
                item_distribution[item_code] += 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_contract_text_score"]),
                -float(row["candidate_score"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_contract_text_candidates"] += 1
        scan["raw_contract_text_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_contract_text_score": top[
                    "candidate_contract_text_score"
                ],
                "top_candidate_contract_text_hits": top[
                    "candidate_contract_text_hits"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_contract_text_score"]),
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_close_location"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "contract_demand_pattern_count": len(CONTRACT_DEMAND_PATTERNS),
            "exclusion_pattern_count": len(EXCLUSION_PATTERNS),
            "business_update_event_subtypes": list(BUSINESS_UPDATE_EVENT_SUBTYPES),
            "item_code_weights": ITEM_CODE_WEIGHTS,
            "hit_distribution": dict(sorted(hit_distribution.items())),
            "item_distribution": dict(sorted(item_distribution.items())),
            "min_semantic_score": MIN_SEMANTIC_SCORE,
            "min_price": base.MIN_PRICE,
            "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
            "min_signal_return": base.MIN_SIGNAL_RETURN,
            "min_close_location": base.MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
            "min_ret5": base.MIN_RET5,
            "max_ret5": base.MAX_RET5,
            "max_ret20": base.MAX_RET20,
            "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_pnl_not_beaten")
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_contract_demand_text_leadership"
        if gate["passed"]
        else "rejected_sec_contract_demand_text_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT SEC filing text usable_trade_date rows plus "
        "close-of-day OHLCV available on the signal date. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_event_ohlcv_candidate_pool",
            "new_evidence_type": (
                "production_visible_free_sec_filing_text_contract_demand_semantics_plus_ohlcv_leadership"
            ),
            "nearby_prior_experiments": [
                "exp-20260610-013",
                "exp-20260603-012",
                "exp-20260605-006",
                "exp-20260605-031",
                "exp-20260608-013",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that even explicit SEC "
                "contract/order/backlog phrasing remains a noisy promotional "
                "or already-priced text bucket once next-open execution, costs, "
                "liquid leadership, cooldown, and overlap controls are imposed. "
                "Do not answer by sweeping text pattern synonyms, item-code "
                "weights, RS thresholds, top-N, hold-day, cooldown, or notional "
                "on these frozen windows without materially new PIT evidence "
                "such as named customer/supplier relation extraction or "
                "forward source-utility labels."
            ),
            "next_evidence_needed": (
                "A retry needs materially richer PIT semantic evidence: named "
                "customer/supplier/counterparty extraction, contract value or "
                "duration, pre/post-market timing confirmation, or a replayable "
                "source-utility ledger showing which SEC text families beat "
                "the displaced candidate after costs."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "sec_text_path": _repo_rel(SEC_TEXT_PATH),
        "business_update_event_subtypes": list(BUSINESS_UPDATE_EVENT_SUBTYPES),
        "item_code_weights": ITEM_CODE_WEIGHTS,
        "contract_demand_patterns": list(CONTRACT_DEMAND_PATTERNS),
        "exclusion_patterns": list(EXCLUSION_PATTERNS),
        "min_semantic_score": MIN_SEMANTIC_SCORE,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
        "min_ret5": base.MIN_RET5,
        "max_ret5": base.MAX_RET5,
        "max_ret20": base.MAX_RET20,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "same_ticker_core_overlap_excluded": True,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed SEC contract-demand text leadership bundle cleared the "
            "canonical three-window gates and beat the accepted compression "
            "comparator, suggesting explicit filing-text business momentum "
            "evidence added replacement value beyond generic SEC item labels. "
            "It remains only a replay lead because no shared daily adapter or "
            "production parity path was added."
            if passed
            else (
                "The fixed SEC contract-demand text leadership bundle failed "
                "Gate 4. This says explicit SEC customer/contract/order/backlog "
                "phrases were not enough to create stable replacement value "
                "after next-open execution, costs, 10-day hold, cooldown, "
                "overlap controls, and accepted compression comparison. The "
                "useful next evidence is named relation/value extraction, not "
                "another synonym or price-threshold sweep."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping SEC text synonyms, item-code weights, "
            "8-K item subsets, ret20/ret60 relative-strength thresholds, "
            "signal-day return, close-location, volume-ratio bounds, top-N, "
            "hold-day, cooldown, or paper notional on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The SEC contract-demand text leadership source passed as a replay-only "
        "promotion lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The SEC contract-demand text leadership source was rejected; it "
            "did not establish a distinct free SEC text/OHLCV candidate-pool "
            "edge under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} {STEM}",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Artifact: `{_repo_rel(OUT_JSON)}`",
            f"- Log: `{_repo_rel(LOG_JSON)}`",
            "",
            "## Hypothesis",
            "",
            PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "",
            "## Three-Window Result",
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "mechanism_family": "production_visible_free_sec_event_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "contract_text_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_contract_text_tickers"
                ),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_contract_text_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
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
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
