"""exp-20260614-013: SEC AI demand evidence-span candidate scout.

Replay-only alpha search. The single decision hypothesis is that SEC
financial-report text containing concrete AI / data-center demand acceleration
evidence, followed by a positive T+1 SPY-relative reaction, may identify
durable post-filing continuation candidates.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from sec_event_queue import language_features, sec_event_family, semantic_text  # noqa: E402


EXPERIMENT_ID = "exp-20260614-013"
STEM = "sec_ai_demand_evidence_span"
TRIAL_FAMILY = "sec_ai_demand_acceleration_evidence_span_candidate_pool"
TRIAL_VARIANT_ID = "sec_ai_demand_acceleration_evidence_span_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_ai_demand_acceleration_evidence_span_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_013_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_TEXT_PATH = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_filing_text_20241002_20260421.jsonl"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_T1_RETURN = 0.0
MIN_T1_EXCESS_SPY = 0.01
MAX_T1_RETURN = 0.18

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_SEC_RS20_COMPARATOR = {
    "experiment_id": "exp-20260614-004",
    "decision": "accepted_default_off_sec_financial_report_rs20_leader_notional_1.15x",
    "aggregate_expected_value_delta": 0.158184,
    "aggregate_pnl_delta": 3235.38,
}

WINDOWS = framework.WINDOWS
shadow = framework.shadow
overlay_helper = framework.overlay_helper
sleeve = framework.sleeve

AI_PATTERNS = (
    r"\bai\b",
    r"artificial intelligence",
    r"data centers?",
    r"custom ai",
    r"ai accelerators?",
    r"accelerated computing",
    r"\bgpu\b",
    r"networking",
)
DEMAND_PATTERNS = (
    r"strong demand",
    r"robust demand",
    r"accelerating demand",
    r"increasing demand",
    r"customer demand",
    r"continued momentum",
    r"record revenue",
    r"revenue grew",
    r"revenue growth",
    r"grew [0-9]+",
    r"growth of [0-9]+",
    r"guidance",
    r"outlook",
)
NEGATIVE_SPAN_PATTERNS = (
    r"risk factors?",
    r"cautionary",
    r"uncertaint",
    r"adversely",
    r"may not",
    r"could not",
)
CAUTION_BOUNDARY_RE = re.compile(
    r"(cautionary note|forward-looking statements|risk factors|about [A-Z][A-Za-z ]{2,40}\s*$)",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\s+\u2022\s+|\n+")

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "tech_concentration",
        "window_regression",
        "accepted_sec_comparator_not_beaten",
        "generic_ai_keyword_noise",
    ],
    "confidence_reason": (
        "Playbook now prefers new production-visible free PIT fields over "
        "allocator/threshold retunes. SEC text coverage spans all canonical "
        "windows and evidence spans can be replayed, but nearby SEC language, "
        "customer-commitment, and allocator-source experiments failed, so this "
        "is a speculative data-shape scout."
    ),
    "recorded_at": "2026-06-14T12:05:43+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
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
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing SEC text, evidence span, OHLCV, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same SEC "
        "financial-report text set, evidence-span extractor, T+1 reaction "
        "gate, liquidity gate, same-ticker overlap exclusion, cooldown, "
        "next-open paper entry, 10-day exit, costs, and concentration controls "
        "in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC financial-report text that contains concrete "
        "AI/data-center demand acceleration evidence and then receives a "
        "positive T+1 SPY-relative reaction may continue after next-open paper "
        "entry."
    ),
    "2_history_check": {
        "exp-20260614-004": (
            "Accepted standalone SEC financial-report RS20 leader notional "
            "support, EV +0.158184 and PnL +$3,235.38; this run must beat it "
            "to be more than a weak SEC near-neighbor."
        ),
        "exp-20260614-009": (
            "Rejected SEC financial-report allocator source extension; this "
            "run does not admit the SEC source into the accepted allocator."
        ),
        "exp-20260614-012": (
            "Blocked further repeats and named SEC evidence-span fields as one "
            "valid next data-edge direction."
        ),
        "exp-20260611-017": (
            "Rejected quantified counterparty commitment; this run uses "
            "earnings-release demand acceleration spans, not contract/customer "
            "commitment parsing."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least 20 paper "
        "trades across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and exp-20260614-004 SEC RS20 accepted comparator "
        "must be beaten. Replay-only positives are leads until shared daily/"
        "backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_013_sec_ai_demand_evidence_span.py"
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configure_sleeve_globals() -> None:
    sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    sleeve.STEM = STEM
    sleeve.TRIAL_FAMILY = TRIAL_FAMILY
    sleeve.CHANGED_VARIABLE = CHANGED_VARIABLE
    sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    sleeve.HOLD_DAYS = HOLD_DAYS
    sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    sleeve.OUT_DIR = OUT_DIR
    sleeve.OUT_JSON = OUT_JSON
    sleeve.LOG_JSON = LOG_JSON
    sleeve.TICKET_JSON = TICKET_JSON
    sleeve.CARD_MD = CARD_MD
    sleeve.EXPERIMENT_LOG = EXPERIMENT_LOG


def _load_sec_text_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with SEC_TEXT_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _business_text(row: dict[str, Any]) -> str:
    text = semantic_text(row)
    match = CAUTION_BOUNDARY_RE.search(text)
    if match:
        text = text[: match.start()]
    return re.sub(r"\s+", " ", text[:60000]).strip()


def _pattern_hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def _extract_ai_demand_spans(row: dict[str, Any]) -> dict[str, Any]:
    text = _business_text(row)
    spans: list[dict[str, Any]] = []
    ai_terms: Counter[str] = Counter()
    demand_terms: Counter[str] = Counter()
    rejected_negative_spans = 0
    for sentence in SENTENCE_SPLIT_RE.split(text):
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if len(cleaned) < 35:
            continue
        lowered = cleaned.lower()
        ai_hits = _pattern_hits(lowered, AI_PATTERNS)
        demand_hits = _pattern_hits(lowered, DEMAND_PATTERNS)
        if not ai_hits or not demand_hits:
            continue
        if _pattern_hits(lowered, NEGATIVE_SPAN_PATTERNS):
            rejected_negative_spans += 1
            continue
        for hit in ai_hits:
            ai_terms[hit] += 1
        for hit in demand_hits:
            demand_terms[hit] += 1
        spans.append(
            {
                "text": cleaned[:300],
                "ai_terms": ai_hits,
                "demand_terms": demand_hits,
            }
        )
        if len(spans) >= 5:
            break
    return {
        "span_count": len(spans),
        "spans": spans,
        "ai_terms": dict(sorted(ai_terms.items())),
        "demand_terms": dict(sorted(demand_terms.items())),
        "rejected_negative_spans": rejected_negative_spans,
    }


def _idx_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if shadow._date(row) >= target:
            return idx
    return None


def _close_to_close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = shadow._value(rows[start_idx], "Close")
    end_close = shadow._value(rows[end_idx], "Close")
    if not start_close or not end_close:
        return None
    return end_close / start_close - 1.0


def _t1_reaction(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    usable_trade_date: str,
) -> dict[str, Any]:
    rows = shadow._series(snapshot, ticker)
    spy_rows = shadow._series(snapshot, "SPY")
    event_idx = _idx_on_or_after(rows, usable_trade_date)
    spy_idx = _idx_on_or_after(spy_rows, usable_trade_date)
    if event_idx is None or spy_idx is None:
        return {"status": "missing_event_idx"}
    t1_idx = event_idx + 1
    spy_t1_idx = spy_idx + 1
    t1_return = _close_to_close_return(rows, event_idx, t1_idx)
    spy_t1_return = _close_to_close_return(spy_rows, spy_idx, spy_t1_idx)
    if t1_return is None or spy_t1_return is None:
        return {"status": "missing_t1_close"}
    event_row = rows[event_idx]
    t1_row = rows[t1_idx]
    close_price = shadow._value(t1_row, "Close")
    adv20 = framework._avg_dollar_volume(rows, t1_idx, 20)
    return {
        "status": "covered",
        "event_trading_date": shadow._date(event_row),
        "date": shadow._date(t1_row),
        "t1_return": _round(t1_return, 6),
        "spy_t1_return": _round(spy_t1_return, 6),
        "t1_excess_return_vs_spy": _round(t1_return - spy_t1_return, 6),
        "t1_close_price": _round(close_price, 4),
        "avg_dollar_volume_20d": _round(adv20, 2),
    }


def _candidate_from_text_row(
    *,
    row: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    entries_by_date: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    ticker = str(row.get("ticker") or "").upper()
    if not ticker or ticker not in snapshot:
        return None, "missing_ticker_ohlcv"
    if sec_event_family(row) != "earnings_8k":
        return None, "not_earnings_8k"
    usable = str(row.get("usable_trade_date") or "")[:10]
    if not usable:
        return None, "missing_usable_trade_date"

    evidence = _extract_ai_demand_spans(row)
    if evidence["span_count"] <= 0:
        return None, "no_ai_demand_evidence_span"
    language = language_features(row)
    if int(language.get("guidance_cut_hits") or 0) > 0:
        return None, "guidance_cut_hit"

    reaction = _t1_reaction(snapshot=snapshot, ticker=ticker, usable_trade_date=usable)
    if reaction.get("status") != "covered":
        return None, str(reaction.get("status") or "reaction_missing")
    signal_date = str(reaction["date"])
    t1_return = float(reaction["t1_return"])
    t1_excess = float(reaction["t1_excess_return_vs_spy"])
    close_price = float(reaction["t1_close_price"] or 0.0)
    adv20 = float(reaction["avg_dollar_volume_20d"] or 0.0)
    if t1_return <= MIN_T1_RETURN:
        return None, "t1_return_not_positive"
    if t1_excess < MIN_T1_EXCESS_SPY:
        return None, "t1_excess_below_min"
    if t1_return > MAX_T1_RETURN:
        return None, "t1_return_exhausted"
    if close_price < MIN_PRICE:
        return None, "price_below_min"
    if adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None, "adv20_below_min"

    ab_entries = entries_by_date.get(signal_date, [])
    score = (
        100.0 * t1_excess
        + 1.5 * float(evidence["span_count"])
        + 0.01 * math.log10(max(adv20, 1.0))
        - 0.25 * float(language.get("negative_phrase_hits") or 0)
    )
    candidate = {
        "ticker": ticker,
        "date": signal_date,
        "strategy": STEM,
        "rule_version": RULE_VERSION,
        "candidate_score": _round(score, 6),
        "event_trading_date": reaction["event_trading_date"],
        "usable_trade_date": usable,
        "filing_date": row.get("filing_date"),
        "accepted_at": row.get("accepted_at"),
        "accession_number": row.get("accession_number"),
        "form_type": row.get("form_type"),
        "form_base": row.get("form_base"),
        "event_family": "earnings_8k",
        "eight_k_item_codes": row.get("eight_k_item_codes"),
        "primary_document": row.get("primary_document"),
        "index_url": row.get("index_url"),
        "archive_url": row.get("archive_url"),
        "t1_return": reaction["t1_return"],
        "spy_t1_return": reaction["spy_t1_return"],
        "t1_excess_return_vs_spy": reaction["t1_excess_return_vs_spy"],
        "t1_close_price": reaction["t1_close_price"],
        "avg_dollar_volume_20d": reaction["avg_dollar_volume_20d"],
        "language_bucket": language.get("language_bucket"),
        "language_score": language.get("language_score"),
        "positive_phrase_hits": language.get("positive_phrase_hits"),
        "negative_phrase_hits": language.get("negative_phrase_hits"),
        "guidance_raise_hits": language.get("guidance_raise_hits"),
        "guidance_cut_hits": language.get("guidance_cut_hits"),
        "text_event_type": language.get("text_event_type"),
        "ai_demand_evidence": evidence,
        "same_day_ab_entry_count": len(ab_entries),
        "same_ticker_ab_overlap": any(
            str(entry.get("ticker") or "").upper() == ticker for entry in ab_entries
        ),
        "trade_enabled": False,
        "alters_orders": False,
        "evidence_span_rule_version": RULE_VERSION,
    }
    return candidate, "candidate"


def _candidate_rows_for_window(
    *,
    sec_text_rows: list[dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    candidates: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    evidence_samples: list[dict[str, Any]] = []
    for row in sec_text_rows:
        candidate, reason = _candidate_from_text_row(
            row=row,
            snapshot=snapshot,
            entries_by_date=entries_by_date,
        )
        if candidate is None:
            reject_counts[reason] += 1
            continue
        if not (cfg["start"] <= str(candidate["date"]) <= cfg["end"]):
            reject_counts["signal_date_outside_window"] += 1
            continue
        candidates.append(candidate)
        if len(evidence_samples) < 25:
            evidence_samples.append(
                {
                    "ticker": candidate["ticker"],
                    "date": candidate["date"],
                    "t1_excess_return_vs_spy": candidate["t1_excess_return_vs_spy"],
                    "spans": candidate["ai_demand_evidence"]["spans"][:2],
                }
            )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["t1_excess_return_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "rule_version": RULE_VERSION,
        "source_path": _repo_rel(SEC_TEXT_PATH),
        "loaded_text_rows": len(sec_text_rows),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "reject_counts": dict(sorted(reject_counts.items())),
        "evidence_samples": evidence_samples,
    }


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    aggregate_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    aggregate_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if aggregate_ev <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if aggregate_pnl <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate_ev <= ACCEPTED_SEC_RS20_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_sec_rs20_ev_not_beaten")
    if aggregate_pnl <= ACCEPTED_SEC_RS20_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_sec_rs20_pnl_not_beaten")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_sec_ai_demand_evidence_span"
            if passed
            else "rejected_sec_ai_demand_evidence_span_candidate_pool"
        ),
        "failed_reasons": failed,
        "accepted_sec_rs20_comparator": ACCEPTED_SEC_RS20_COMPARATOR,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_payload() -> dict[str, Any]:
    _configure_sleeve_globals()
    timestamp = _utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sec_text_rows = _load_sec_text_rows()
    sec_tickers = {str(row.get("ticker") or "").upper() for row in sec_text_rows}
    sec_tickers.discard("")
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and SEC AI demand evidence-span replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=sec_tickers,
        )
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sec_text_ticker_count": len(sec_tickers),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        candidates, scan = _candidate_rows_for_window(
            sec_text_rows=sec_text_rows,
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
        )
        selected_trades, filtered_candidates = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = sleeve._aggregate(window_rows)
    target_summary = sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "observed_only" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "predicted_failure_mode_hit": any(
            reason in gate4["failed_reasons"]
            for reason in (
                "target_sample_too_small",
                "target_window_coverage_too_small",
                "target_concentration_failed",
                "window_ev_regression",
                "accepted_sec_rs20_ev_not_beaten",
                "accepted_sec_rs20_pnl_not_beaten",
            )
        ),
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    interpretation = (
        "The SEC AI demand evidence-span source cleared numeric Gate 4 as a "
        "private replay lead only; no production surface was promoted."
        if gate4["passed"]
        else (
            "The SEC AI demand evidence-span source did not clear Gate 4. "
            "Do not promote or retry this exact AI/data-center demand span, "
            "T+1 reaction, liquidity, top1/day, cooldown, or 10d hold bundle "
            "on the same frozen windows."
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": bool(gate4["passed"]),
        "accepted_alpha": False,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_private_replay_scout",
        "implementation_mode": "private_replay_scout",
        "mechanism_family": "production_visible_free_sec_text_evidence_span_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": [
            "exp-20260614-004",
            "exp-20260614-009",
            "exp-20260614-012",
            "exp-20260611-017",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "sec_text_ai_demand_acceleration_evidence_span",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only SEC text evidence-span default-off paper overlay"
            ),
            "windows": WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sec_text_source": _repo_rel(SEC_TEXT_PATH),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "SEC text and close-of-day OHLCV are known by signal date. "
                "Signal date is the first post-event T+1 close. Paper entry is "
                "next available open with existing entry slippage; exit is the "
                "close 10 trading days after signal with target-side sell "
                "slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_t1_return": MIN_T1_RETURN,
            "min_t1_excess_spy": MIN_T1_EXCESS_SPY,
            "max_t1_return": MAX_T1_RETURN,
            "ai_patterns": AI_PATTERNS,
            "demand_patterns": DEMAND_PATTERNS,
            "negative_span_patterns": NEGATIVE_SPAN_PATTERNS,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "SEC filing text accession_number",
                "SEC filing text combined_text",
                "SEC filing text usable_trade_date",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The SEC AI demand "
                "evidence-span candidate source is additive default-off paper, "
                "so core signals generated/survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "scan_by_window": scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": (
                "The evidence-span rule is intended to separate concrete AI "
                "demand disclosures from generic positive earnings language. "
                "If it fails, the likely reason is sample concentration in "
                "crowded megacap/AI trades, generic AI wording, or the T+1 "
                "reaction already exhausting the 10-day edge."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping AI keywords, demand terms, T+1 "
                "thresholds, ADV/price filters, top-N, hold days, cooldown, or "
                "paper notional on the same frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs materially richer PIT semantic provenance, such "
                "as extracted segment revenue/guidance deltas, customer/order "
                "identity, analyst estimate breadth/dispersion, or closed "
                "forward replacement-value rows from a shared daily helper."
            ),
        },
        "next_retry_requires": [
            "materially richer PIT semantic provenance",
            "closed forward replacement-value rows",
            "shared helper plus daily snapshot parity for any positive replay",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC AI Demand Evidence Span",
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
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
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
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_sec_rs20_comparator": ACCEPTED_SEC_RS20_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": payload["rejection_reason"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


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
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": False,
        "calibration": payload["calibration"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "completed_at": payload["timestamp"],
            "production_impact": PRODUCTION_IMPACT,
            "post_run_reflection": payload["post_run_reflection"],
        },
        timeout_seconds=120,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
