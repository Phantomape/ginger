"""exp-20260611-001: SEC filing complexity/change-density absorption scout.

Replay-only alpha search. This tests one fixed candidate-source variable:
PIT SEC 8-K filing text with high non-boilerplate complexity and material
change-density, then same-day liquid OHLCV absorption before next-open paper
entry with a fixed 10-trading-day hold.

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

import exp_20260610_024_sec_earnings_cadence_surprise_absorption as previous


framework = previous.framework
base = previous.base

EXPERIMENT_ID = "exp-20260611-001"
STEM = "sec_filing_complexity_change_density_absorption"
TRIAL_FAMILY = "sec_filing_complexity_change_density_absorption_candidate_pool"
TRIAL_VARIANT_ID = (
    "sec_filing_complexity_change_density_absorption_top1_next_open_10d_v1"
)
CHANGED_VARIABLE = (
    "sec_filing_complexity_change_density_absorption_candidate_source_v1"
)
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_001_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SEC_TEXT_PATH = previous.SEC_TEXT_PATH

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

MATERIAL_ITEM_CODES = {"1.01", "7.01", "8.01"}
MIN_TEXT_WORD_COUNT = 1_200
MIN_COMPLEXITY_SCORE = 5.50
MIN_MATERIAL_CHANGE_DENSITY = 0.006

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

MATERIAL_CHANGE_PATTERNS: tuple[str, ...] = (
    r"\bentered into\b",
    r"\bagreement\b",
    r"\bannounced\b",
    r"\blaunch(?:ed|es)?\b",
    r"\bapproval\b",
    r"\bguidance\b",
    r"\bexpects?\b",
    r"\bincreas(?:ed|e|es)\b",
    r"\breduc(?:ed|e|es)\b",
    r"\bcustomer\b",
    r"\bcontract\b",
    r"\bbacklog\b",
    r"\border\b",
    r"\baward(?:ed)?\b",
    r"\bpartnership\b",
    r"\bacquisition\b",
    r"\bdivestiture\b",
    r"\brestructuring\b",
    r"\brevenue\b",
    r"\bmargin\b",
    r"\bcash flow\b",
    r"\bebitda\b",
    r"\bproduction\b",
    r"\bcommercial\b",
)

BOILERPLATE_PATTERNS: tuple[str, ...] = (
    r"forward-looking statements?",
    r"safe harbor",
    r"risk factors?",
    r"cautionary",
    r"not undertake.{0,80}update",
    r"actual results.{0,80}differ",
)

EXCLUSION_PATTERNS: tuple[str, ...] = (
    r"\bpublic offering\b",
    r"\bprivate placement\b",
    r"\bregistered direct\b",
    r"\bat[- ]the[- ]market\b",
    r"\bwarrant\b",
    r"\bconvertible\b",
    r"\bbankruptcy\b",
    r"\bdelisting\b",
    r"\brestatement\b",
    r"\bmaterial weakness\b",
)

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2200.0,
    "main_failure_modes": [
        "payload_size_relabel",
        "phrase_synonym_sweep",
        "thin_mapped_sample",
        "accepted_compression_not_beaten",
        "window_regression",
    ],
    "confidence_reason": (
        "External disclosure-complexity research maps to replayable SEC text "
        "fields, but recent SEC payload, phrase, and cadence experiments failed, "
        "so this fixed non-boilerplate change-density bundle is low confidence."
    ),
    "recorded_at": "2026-06-11T00:09:39+00:00",
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
        "8-K material-item, text completeness, exclusion, non-boilerplate "
        "complexity, material-change density, signal-date OHLCV absorption, "
        "overlap exclusion, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, comparator, and concentration guards in historical replay "
        "and daily production before any report queue, paper ledger, candidate "
        "priority, sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 8-K filings with high non-boilerplate complexity "
        "and material-change density, when paired with same-day liquid "
        "SPY-relative price and volume absorption, may identify slow-disclosure "
        "underreaction candidates for next-open 10d paper drift."
    ),
    "2_history_check": {
        "exp-20260609-012": (
            "Rejected SEC large filing-payload absorption. It produced zero "
            "target trades because payload-filtered rows did not map to the "
            "replay price surface; this run uses the newer tradable candidate "
            "helper and a complexity/change-density field, not raw payload size."
        ),
        "exp-20260610-023": (
            "Rejected SEC contract-demand text leadership as sparse/noisy. "
            "This run does not sweep contract/customer phrase synonyms and "
            "uses structural text complexity plus change-density."
        ),
        "exp-20260610-024": (
            "Rejected SEC earnings cadence surprise absorption. This run does "
            "not use issuer cadence gaps, but the data is still 8-K heavy, so "
            "post-earnings near-neighbor failure is pre-registered."
        ),
        "history_search": (
            "No prior fixed SEC non-boilerplate complexity/change-density "
            "absorption experiment was found in experiment_log.jsonl, "
            "experiments/cards, or quant/experiments."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT SEC 8-K text rows, Item 1.01/7.01/8.01 "
        "material-update presence, minimum text completeness, financing/adverse "
        "exclusions, non-boilerplate complexity score, material-change density, "
        "existing liquid sector-known stock universe and OHLCV leadership/"
        "absorption gates, same-ticker core-overlap exclusion, top-1 next-open "
        "paper entry, 10-day hold, cost, cooldown, and concentration gates."
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
        "exp_20260611_001_sec_filing_complexity_change_density_absorption.py"
    ),
}

_EVENT_CACHE: dict[str, Any] | None = None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _date10(value: Any) -> str:
    return str(value or "")[:10]


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


def _pattern_count(text: str, patterns: tuple[str, ...]) -> int:
    return sum(
        len(re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL))
        for pattern in patterns
    )


def _text_features(text: str) -> dict[str, Any]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text)
    word_count = max(len(words), 1)
    lowered_words = [word.lower() for word in words]
    unique_long = len({word for word in lowered_words if len(word) > 5})
    long_words = sum(1 for word in lowered_words if len(word) >= 10)
    numeric_tokens = len(
        re.findall(
            r"(?:\$|\b)\d+(?:\.\d+)?\s?(?:%|million|billion|mw|gb|units|shares)?",
            text.lower(),
        )
    )
    material_hits = _pattern_count(text, MATERIAL_CHANGE_PATTERNS)
    boilerplate_hits = _pattern_count(text, BOILERPLATE_PATTERNS)
    unique_long_ratio = unique_long / word_count
    long_word_ratio = long_words / word_count
    numeric_density = numeric_tokens / word_count
    material_density = material_hits / word_count
    boilerplate_density = boilerplate_hits / word_count
    complexity_score = (
        unique_long_ratio * 25.0
        + long_word_ratio * 15.0
        + min(numeric_density * 100.0, 1.5)
        + min(material_density * 120.0, 2.0)
        - min(boilerplate_hits * 0.20, 1.0)
    )
    return {
        "word_count_recomputed": word_count,
        "unique_long_ratio": unique_long_ratio,
        "long_word_ratio": long_word_ratio,
        "numeric_token_density": numeric_density,
        "material_change_density": material_density,
        "boilerplate_density": boilerplate_density,
        "material_change_hits": material_hits,
        "boilerplate_hits": boilerplate_hits,
        "complexity_score": complexity_score,
    }


def _complexity_event_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper().strip()
    usable_date = _date10(row.get("usable_trade_date") or row.get("filing_date"))
    if not ticker or not usable_date:
        return None
    if str(row.get("status") or "ok").lower() not in {"ok", ""}:
        return None
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    if "8-K" not in form_type:
        return None
    item_codes = _item_codes(row)
    if not item_codes.intersection(MATERIAL_ITEM_CODES):
        return None
    text = str(row.get("combined_text") or "")
    if not text:
        return None
    text_word_count = int(row.get("text_word_count") or 0)
    if text_word_count < MIN_TEXT_WORD_COUNT:
        return None
    if _pattern_count(text, EXCLUSION_PATTERNS):
        return None
    features = _text_features(text)
    if features["complexity_score"] < MIN_COMPLEXITY_SCORE:
        return None
    if features["material_change_density"] < MIN_MATERIAL_CHANGE_DENSITY:
        return None
    source_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return {
        "ticker": ticker,
        "usable_trade_date": usable_date,
        "filing_date": _date10(row.get("filing_date")),
        "accepted_at": row.get("accepted_at"),
        "accession_number": row.get("accession_number"),
        "primary_document": row.get("primary_document"),
        "form_type": form_type,
        "item_codes": sorted(item_codes),
        "text_word_count": text_word_count,
        "text_char_count": row.get("text_char_count"),
        "documents_fetched": row.get("documents_fetched"),
        "source_text_hash": source_hash,
        "pit_source": row.get("pit_source"),
        "pit_caveat": row.get("pit_caveat"),
        "complexity_score": round(float(features["complexity_score"]), 6),
        "material_change_density": round(
            float(features["material_change_density"]), 8
        ),
        "material_change_hits": int(features["material_change_hits"]),
        "boilerplate_density": round(float(features["boilerplate_density"]), 8),
        "boilerplate_hits": int(features["boilerplate_hits"]),
        "unique_long_ratio": round(float(features["unique_long_ratio"]), 8),
        "long_word_ratio": round(float(features["long_word_ratio"]), 8),
        "numeric_token_density": round(float(features["numeric_token_density"]), 8),
    }


def _load_complexity_events() -> dict[str, Any]:
    global _EVENT_CACHE
    if _EVENT_CACHE is not None:
        return _EVENT_CACHE

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    examples: list[dict[str, Any]] = []
    scan = Counter()
    item_distribution = Counter()
    score_bucket_distribution = Counter()
    if not SEC_TEXT_PATH.exists():
        _EVENT_CACHE = {
            "by_date_ticker": by_date_ticker,
            "scan": {"text_file_missing": True, "path": _repo_rel(SEC_TEXT_PATH)},
            "examples": examples,
        }
        return _EVENT_CACHE

    with SEC_TEXT_PATH.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            scan["text_rows_loaded"] += 1
            row = json.loads(line)
            if "8-K" in str(row.get("form_type") or row.get("form_base") or "").upper():
                scan["eight_k_rows"] += 1
            item_codes = _item_codes(row)
            if item_codes.intersection(MATERIAL_ITEM_CODES):
                scan["material_item_rows"] += 1
            event = _complexity_event_from_row(row)
            if event is None:
                continue
            scan["complexity_passed_rows"] += 1
            for item_code in event["item_codes"]:
                item_distribution[item_code] += 1
            score_bucket_distribution[
                str(min(int(float(event["complexity_score"])), 12))
            ] += 1
            by_date_ticker.setdefault(event["usable_trade_date"], {}).setdefault(
                event["ticker"], []
            ).append(event)
            if len(examples) < 12:
                examples.append(
                    {
                        "date": event["usable_trade_date"],
                        "ticker": event["ticker"],
                        "complexity_score": event["complexity_score"],
                        "material_change_density": event["material_change_density"],
                        "material_change_hits": event["material_change_hits"],
                        "boilerplate_hits": event["boilerplate_hits"],
                        "item_codes": event["item_codes"],
                        "accession_number": event["accession_number"],
                    }
                )

    _EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": {
            **dict(scan),
            "source_text_file": _repo_rel(SEC_TEXT_PATH),
            "material_item_codes": sorted(MATERIAL_ITEM_CODES),
            "min_text_word_count": MIN_TEXT_WORD_COUNT,
            "min_complexity_score": MIN_COMPLEXITY_SCORE,
            "min_material_change_density": MIN_MATERIAL_CHANGE_DENSITY,
            "material_change_pattern_count": len(MATERIAL_CHANGE_PATTERNS),
            "boilerplate_pattern_count": len(BOILERPLATE_PATTERNS),
            "exclusion_pattern_count": len(EXCLUSION_PATTERNS),
            "item_distribution": dict(sorted(item_distribution.items())),
            "complexity_score_bucket_distribution": dict(
                sorted(score_bucket_distribution.items())
            ),
        },
        "examples": examples,
    }
    return _EVENT_CACHE


def _events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_complexity_events()["by_date_ticker"].get(signal_date, {})


def _candidate_for_complexity_ticker(
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
        month_label="sec_filing_complexity_change_density",
    )
    if row is None:
        return None

    top_event = sorted(
        events,
        key=lambda event: (
            -float(event.get("complexity_score") or 0.0),
            -float(event.get("material_change_density") or 0.0),
            -int(event.get("material_change_hits") or 0),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    complexity_rank_score = (
        float(top_event["complexity_score"])
        + 80.0 * float(top_event["material_change_density"])
        + 0.20 * float(row.get("candidate_score") or 0.0)
    )
    row["source"] = "SEC_FILING_COMPLEXITY_CHANGE_DENSITY_ABSORPTION_PAPER"
    row.pop("candidate_month_label", None)
    row["candidate_complexity_rank_score"] = round(complexity_rank_score, 6)
    row["candidate_sec_complexity_score"] = top_event["complexity_score"]
    row["candidate_sec_material_change_density"] = top_event[
        "material_change_density"
    ]
    row["candidate_sec_material_change_hits"] = top_event["material_change_hits"]
    row["candidate_sec_boilerplate_density"] = top_event["boilerplate_density"]
    row["candidate_sec_boilerplate_hits"] = top_event["boilerplate_hits"]
    row["candidate_sec_unique_long_ratio"] = top_event["unique_long_ratio"]
    row["candidate_sec_long_word_ratio"] = top_event["long_word_ratio"]
    row["candidate_sec_numeric_token_density"] = top_event["numeric_token_density"]
    row["candidate_sec_text_event_count"] = len(events)
    row["candidate_sec_text_word_count"] = top_event["text_word_count"]
    row["candidate_sec_text_char_count"] = top_event["text_char_count"]
    row["candidate_sec_text_item_codes"] = top_event["item_codes"]
    row["candidate_sec_text_accession"] = top_event["accession_number"]
    row["candidate_sec_text_primary_document"] = top_event["primary_document"]
    row["candidate_sec_text_source_hash"] = top_event["source_text_hash"]
    row["candidate_sec_text_pit_source"] = top_event["pit_source"]
    row["uses_free_ohlcv_only"] = False
    row["uses_free_sec_filing_text"] = True
    row["known_at"] = (
        "signal_date_sec_filing_complexity_and_ohlcv_before_next_open_paper_entry"
    )
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
    item_distribution: Counter[str] = Counter()
    complexity_bucket_distribution: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_complexity_event_tickers": 0,
        "complexity_event_tickers": 0,
        "days_with_raw_complexity_candidates": 0,
        "raw_complexity_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        "source_text_scan": _load_complexity_events()["scan"],
        "source_text_examples": _load_complexity_events()["examples"][:12],
    }

    for signal_date in dates:
        events_by_ticker = _events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_complexity_event_tickers"] += 1
        scan["complexity_event_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                scan["sector_missing_rejections"] = (
                    scan.get("sector_missing_rejections", 0) + 1
                )
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_complexity_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                scan["ohlcv_absorption_gate_rejections"] = (
                    scan.get("ohlcv_absorption_gate_rejections", 0) + 1
                )
                continue
            for item_code in row.get("candidate_sec_text_item_codes") or []:
                item_distribution[item_code] += 1
            complexity_bucket_distribution[
                str(min(int(float(row["candidate_sec_complexity_score"])), 12))
            ] += 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_complexity_rank_score"]),
                -float(row["candidate_score"]),
                -float(row["candidate_sec_material_change_density"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_complexity_candidates"] += 1
        scan["raw_complexity_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_complexity_rank_score": top[
                    "candidate_complexity_rank_score"
                ],
                "top_candidate_sec_complexity_score": top[
                    "candidate_sec_complexity_score"
                ],
                "top_candidate_sec_material_change_density": top[
                    "candidate_sec_material_change_density"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_complexity_rank_score"]),
            -float(row["candidate_score"]),
            -float(row["candidate_sec_material_change_density"]),
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
            "material_item_codes": sorted(MATERIAL_ITEM_CODES),
            "min_text_word_count": MIN_TEXT_WORD_COUNT,
            "min_complexity_score": MIN_COMPLEXITY_SCORE,
            "min_material_change_density": MIN_MATERIAL_CHANGE_DENSITY,
            "item_distribution": dict(sorted(item_distribution.items())),
            "complexity_bucket_distribution": dict(
                sorted(complexity_bucket_distribution.items())
            ),
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
        "positive_replay_lead_not_promoted_sec_filing_complexity_change_density_absorption"
        if gate["passed"]
        else "rejected_sec_filing_complexity_change_density_absorption_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT SEC 8-K filing text usable_trade_date rows plus "
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
                "production_visible_sec_text_complexity_change_density_x_price_absorption_field"
            ),
            "nearby_prior_experiments": [
                "exp-20260609-012",
                "exp-20260610-023",
                "exp-20260610-024",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that SEC text complexity and "
                "material-change density are still proxies for earnings release "
                "bulk or already-priced disclosure rather than independent "
                "replacement value once next-open execution, costs, liquid "
                "leadership, cooldown, overlap controls, and accepted "
                "compression comparison are imposed. Do not answer by sweeping "
                "complexity, density, item-code, RS, top-N, hold-day, cooldown, "
                "or notional thresholds on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially richer PIT evidence such as named "
                "counterparty/value extraction, non-earnings SEC coverage that "
                "maps to the tradable universe, or a forward source-utility "
                "ledger showing which disclosure complexity buckets beat the "
                "displaced candidate after costs."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "sec_text_path": _repo_rel(SEC_TEXT_PATH),
        "material_item_codes": sorted(MATERIAL_ITEM_CODES),
        "min_text_word_count": MIN_TEXT_WORD_COUNT,
        "min_complexity_score": MIN_COMPLEXITY_SCORE,
        "min_material_change_density": MIN_MATERIAL_CHANGE_DENSITY,
        "material_change_patterns": list(MATERIAL_CHANGE_PATTERNS),
        "boilerplate_patterns": list(BOILERPLATE_PATTERNS),
        "exclusion_patterns": list(EXCLUSION_PATTERNS),
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
            "The fixed SEC filing complexity/change-density absorption bundle "
            "cleared the canonical three-window gates and beat the accepted "
            "compression comparator, suggesting complex material-disclosure "
            "absorption added replacement value. It remains only a replay lead "
            "because no shared daily adapter or production parity path was added."
            if passed
            else (
                "The fixed SEC filing complexity/change-density absorption "
                "bundle failed Gate 4. This says non-boilerplate complexity and "
                "material-change density did not create a stable edge beyond "
                "existing event/OHLCV helpers after next-open execution, costs, "
                "10-day hold, cooldown, overlap controls, and accepted "
                "compression comparison. The useful next evidence is richer "
                "relation/value extraction or broader non-earnings SEC coverage, "
                "not threshold sweeps."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping complexity score, material-change density, "
            "text word count, 8-K item subsets, exclusion patterns, ret20/ret60 "
            "relative-strength thresholds, signal-day return, close-location, "
            "volume-ratio bounds, top-N, hold-day, cooldown, or paper notional "
            "on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The SEC filing complexity/change-density absorption source passed as "
        "a replay-only promotion lead, but no production surface changed and a "
        "shared default-off parity adapter is required before use."
        if passed
        else (
            "The SEC filing complexity/change-density absorption source was "
            "rejected; it did not establish a distinct free SEC text/OHLCV "
            "candidate-pool edge under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Event days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {event_days} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                event_days=scan.get("days_with_complexity_event_tickers", 0),
                days=scan.get("days_with_raw_complexity_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Filing Complexity Change-Density Absorption",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(
                PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=False, indent=2
            ),
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
                "complexity_event_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_complexity_event_tickers"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_complexity_candidates"
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
