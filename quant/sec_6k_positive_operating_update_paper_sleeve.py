"""Default-off SEC 6-K positive operating-update candidate helper.

This module is a pure shared helper for exp-20260622-015. It parses PIT SEC
6-K/6-KA text rows into a deterministic positive operating-update context and
builds default-off paper candidates with the same semantics for historical
replay and daily observation. It does not write paper-sleeve state or emit
orders.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_QUANT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QUANT_DIR.parent
_EXPERIMENTS_DIR = _QUANT_DIR / "experiments"
for _path in (_QUANT_DIR, _EXPERIMENTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import exp_20260614_020_accruals_cash_conversion_quality as base  # noqa: E402


SLEEVE_NAME = "SEC_6K_POSITIVE_OPERATING_UPDATE_PAPER"
RULE_VERSION = "sec_6k_positive_operating_update_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

TEXT_DIR = _REPO_ROOT / "data" / "non_ohlcv"
BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_TEXT_WORDS = 100
MAX_TEXT_CHARS_SCANNED = 90_000
EVIDENCE_SPAN_CHARS = 750
ALLOWED_FORM_BASES = {"6-K", "6-K/A"}

OPERATING_CONTEXT_RE = re.compile(
    r"\b(revenue|revenues|sales|net sales|gross profit|operating profit|"
    r"operating income|income from operations|net income|profit|profits|"
    r"earnings|ebitda|adjusted ebitda|orders?|backlog|deliveries|shipments|"
    r"production|volume|customers?|subscribers?|guidance|outlook|forecast|"
    r"financial results|operating results|quarterly results|annual results)\b",
    re.IGNORECASE,
)
POSITIVE_RE = re.compile(
    r"\b(increased|increase|grew|growth|rose|rising|higher|improved|"
    r"improvement|expanded|expansion|record|strong|robust|accelerated|"
    r"beat|beats|exceeded|exceeds|above expectations|better than expected|"
    r"raises?|raised|upgraded|upgrade|positive outlook|significant growth)\b",
    re.IGNORECASE,
)
OUTLOOK_RAISE_RE = re.compile(
    r"\b(raises?|raised|increases?|increased|upgrades?|upgraded)\s+"
    r"(?:its\s+|the\s+|full[- ]year\s+|annual\s+)?"
    r"(guidance|outlook|forecast|revenue guidance|profit guidance|ebitda guidance)\b",
    re.IGNORECASE,
)
PCT_RE = re.compile(r"\b([1-9][0-9]?(?:\.[0-9]+)?)\s?%", re.IGNORECASE)
NEGATIVE_RE = re.compile(
    r"\b(decreased|declined|lower|fell|drop(?:ped)?|weak|weakness|loss|"
    r"net loss|operating loss|impairment|going concern|material uncertainty|"
    r"missed expectations|below expectations|cuts?|cut|reduced|reduces|"
    r"lowered|downgraded|negative outlook)\b",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(tender offer|cash tender|exchange offer|debt securities|senior notes|"
    r"convertible notes|indenture|credit agreement|loan agreement|securities "
    r"purchase agreement|underwriting agreement|at-the-market|atm offering|"
    r"common stock offering|preferred stock|warrant|share repurchase|buyback|"
    r"dividend|rights offering|merger agreement|acquisition agreement|scheme of "
    r"arrangement|settlement agreement|lawsuit|litigation|arbitration|"
    r"employment agreement|equity incentive|annual general meeting|notice of "
    r"meeting|proxy statement)\b",
    re.IGNORECASE,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify_positive_operating_update(text: str, stats: Counter[str] | None = None) -> dict[str, Any] | None:
    """Return deterministic 6-K positive operating-update context or None."""

    if not text or len(text.split()) < MIN_TEXT_WORDS:
        if stats is not None:
            stats["rejected_short_text"] += 1
        return None

    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    best: dict[str, Any] | None = None
    for hit in POSITIVE_RE.finditer(scanned):
        start = max(0, hit.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scanned), hit.end() + EVIDENCE_SPAN_CHARS)
        span = scanned[start:end]
        if EXCLUDE_RE.search(span):
            if stats is not None:
                stats["rejected_excluded_span"] += 1
            continue
        if not OPERATING_CONTEXT_RE.search(span):
            if stats is not None:
                stats["rejected_missing_operating_context"] += 1
            continue
        positives = sorted({match.group(0).lower() for match in POSITIVE_RE.finditer(span)})
        contexts = sorted({match.group(0).lower() for match in OPERATING_CONTEXT_RE.finditer(span)})
        negatives = sorted({match.group(0).lower() for match in NEGATIVE_RE.finditer(span)})
        outlook_raises = sorted({match.group(0).lower() for match in OUTLOOK_RAISE_RE.finditer(span)})
        pct_values = [_float_or_none(match.group(1)) for match in PCT_RE.finditer(span)]
        pct_values = [value for value in pct_values if value is not None and 0.0 < value <= 100.0]

        if negatives and len(negatives) > len(positives) and not outlook_raises:
            if stats is not None:
                stats["rejected_negative_dominant_span"] += 1
            continue

        strength = (
            1.00
            + 0.16 * min(len(positives), 6)
            + 0.10 * min(len(contexts), 8)
            + 0.35 * bool(outlook_raises)
            + 0.04 * min(max(pct_values or [0.0]), 40.0)
            - 0.10 * min(len(negatives), 4)
        )
        event = {
            "operating_update_strength": _round(strength, 6),
            "positive_terms": positives,
            "operating_context_terms": contexts,
            "negative_terms": negatives,
            "outlook_raise_terms": outlook_raises,
            "max_percent_value": _round(max(pct_values), 4) if pct_values else None,
            "evidence_excerpt": _clean_excerpt(span),
            "text_word_count_scanned": len(scanned.split()),
        }
        if best is None or float(event["operating_update_strength"] or 0.0) > float(
            best["operating_update_strength"] or 0.0
        ):
            best = event

    if stats is not None:
        stats["accepted_operating_update_spans" if best else "rejected_no_positive_operating_span"] += 1
    return best


def load_sec_6k_positive_operating_update_rows(
    *,
    max_filed: str,
    tickers: list[str] | None = None,
    text_dir: Path | str = TEXT_DIR,
    **_: Any,
) -> list[dict[str, Any]]:
    """Load unique PIT 6-K text events known by max_filed."""

    allowed = {ticker.upper() for ticker in tickers or []}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    stats: Counter[str] = Counter()
    for path in sorted(Path(text_dir).glob("sec_filing_text_*.jsonl")):
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    stats["json_decode_errors"] += 1
                    continue
                ticker = str(raw.get("ticker") or "").upper()
                if allowed and ticker not in allowed:
                    stats["skipped_not_allowed_ticker"] += 1
                    continue
                form_base = _form_base(raw)
                if form_base not in ALLOWED_FORM_BASES:
                    stats["skipped_form_base"] += 1
                    continue
                usable_date = str(raw.get("usable_trade_date") or "")[:10]
                if not usable_date or usable_date > max_filed:
                    stats["skipped_date"] += 1
                    continue
                accession = str(raw.get("accession_number") or "")
                key = accession or f"{ticker}:{usable_date}:{raw.get('primary_document')}"
                if key in seen:
                    stats["skipped_duplicate_accession"] += 1
                    continue
                seen.add(key)
                event = classify_positive_operating_update(str(raw.get("combined_text") or ""), stats)
                if event is None:
                    continue
                rows.append(
                    {
                        "ticker": ticker,
                        "date": usable_date,
                        "filing_date": str(raw.get("filing_date") or "")[:10],
                        "accepted_at": str(raw.get("accepted_at") or "")[:19],
                        "accession_number": accession,
                        "form_type": raw.get("form_type"),
                        "form_base": form_base,
                        "primary_document": raw.get("primary_document"),
                        "text_char_count": raw.get("text_char_count"),
                        "text_word_count": raw.get("text_word_count"),
                        "pit_source": raw.get("pit_source"),
                        "pit_caveat": raw.get("pit_caveat"),
                        **event,
                    }
                )
    return rows


def build_sec_6k_positive_operating_update_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    normalised_rows = _normalise_positive_operating_update_rows(text_rows, stats)
    for row in normalised_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        stats["rows_with_outlook_raise"] += 1 if row.get("outlook_raise_terms") else 0
        stats["rows_with_percent_value"] += 1 if row.get("max_percent_value") else 0
    for events in by_ticker.values():
        events.sort(
            key=lambda row: (
                row["date"],
                -float(row.get("operating_update_strength") or 0.0),
                row.get("accession_number") or "",
            )
        )
    return {ticker: {"events": events} for ticker, events in by_ticker.items()}, {
        "sec_6k_text_rows_loaded": len(normalised_rows),
        "sec_6k_text_rows_input": len(text_rows),
        "tickers_with_positive_operating_update": len(by_ticker),
        "text_source": _repo_rel(TEXT_DIR),
        "rule_version": RULE_VERSION,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        **dict(stats),
    }


def _normalise_positive_operating_update_rows(
    text_rows: list[dict[str, Any]],
    stats: Counter[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in text_rows:
        ticker = str(raw.get("ticker") or "").upper()
        form_base = _form_base(raw)
        if form_base not in ALLOWED_FORM_BASES:
            stats["skipped_form_base"] += 1
            continue
        usable_date = str(raw.get("date") or raw.get("usable_trade_date") or raw.get("filing_date") or "")[:10]
        if not ticker or not usable_date:
            stats["skipped_missing_ticker_or_date"] += 1
            continue
        accession = str(raw.get("accession_number") or "")
        key = accession or f"{ticker}:{usable_date}:{raw.get('primary_document')}"
        if key in seen:
            stats["skipped_duplicate_accession"] += 1
            continue
        seen.add(key)

        row = dict(raw)
        if not row.get("operating_update_strength"):
            event = classify_positive_operating_update(str(row.get("combined_text") or ""), stats)
            if event is None:
                continue
            row.update(event)
        row["ticker"] = ticker
        row["date"] = usable_date
        row["form_base"] = form_base
        rows.append(row)
    return rows


def candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return build_sec_6k_positive_operating_update_candidate_rows(
        ohlcv_by_ticker=snapshot,
        start=str(cfg["start"]),
        end=str(cfg["end"]),
        quality_index=quality_index,
        sector_entries=sector_entries,
        require_future_exit=True,
    )


def build_sec_6k_positive_operating_update_candidate_rows(
    *,
    ohlcv_by_ticker: dict[str, list[dict[str, Any]]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
    start: str,
    end: str,
    sector_entries: dict[str, dict[str, Any]] | None = None,
    require_future_exit: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot = {
        str(ticker).upper(): _normalise_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    snapshot = {ticker: rows for ticker, rows in snapshot.items() if rows}
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    scan: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    sectors = sector_entries or {}
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker].get("events", []):
            signal_date = str(event.get("date") or "")[:10]
            if not (start <= signal_date <= end):
                continue
            scan["event_rows_in_window"] += 1
            confirm = _price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
                require_future_exit=require_future_exit,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            meta = sectors.get(ticker, {})
            strength = float(event.get("operating_update_strength") or 0.0)
            pct_component = min(float(event.get("max_percent_value") or 0.0), 40.0) / 40.0
            outlook_component = 0.25 if event.get("outlook_raise_terms") else 0.0
            score = (
                0.85 * strength
                + 0.20 * pct_component
                + outlook_component
                + 0.48 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": SLEEVE_NAME,
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_6k_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "alters_orders": False,
                    **{f"text_{key}": value for key, value in event.items() if key not in {"ticker", "date"}},
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
            -float(row.get("text_operating_update_strength") or 0.0),
            -float(row.get("text_max_percent_value") or 0.0),
            -float(row.get("candidate_ret20_excess_spy") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "allowed_form_bases": sorted(ALLOWED_FORM_BASES),
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "require_future_exit": require_future_exit,
    }


def build_sec_6k_positive_operating_update_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, list[dict[str, Any]]],
    sec_text_rows: list[dict[str, Any]] | None = None,
    sector_entries: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Daily-capable observation snapshot; caller owns persistence/state."""

    as_of_date = str(as_of)[:10]
    text_rows = sec_text_rows
    if text_rows is None:
        text_rows = load_sec_6k_positive_operating_update_rows(max_filed=as_of_date)
    quality_index, quality_summary = build_sec_6k_positive_operating_update_quality_index(text_rows)
    candidates, scan = build_sec_6k_positive_operating_update_candidate_rows(
        ohlcv_by_ticker=ohlcv_by_ticker,
        start=as_of_date,
        end=as_of_date,
        quality_index=quality_index,
        sector_entries=sector_entries,
        require_future_exit=False,
    )
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "context_scan": scan,
        "quality_index_summary": quality_summary,
        "production_impact": production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "default-off paper candidate helper only; no live/default orders",
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": False,
        "trade_enabled": False,
        "alters_orders": False,
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
        "adapter_status": "shared_helper_not_wired_to_run_adapter",
        "scope": "default_off_sec_6k_positive_operating_update_observation",
    }


def _price_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    require_future_exit: bool,
) -> dict[str, Any] | None:
    rows = base.framework.shadow._series(snapshot, ticker)
    spy_rows = base.framework.shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if require_future_exit and idx + HOLD_DAYS >= len(rows):
        return None
    close = base.framework._value(rows[idx], "Close")
    if close is None or close < base.MIN_PRICE:
        return None
    adv20 = base.framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < base.MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = base.framework._daily_return(rows, idx)
    close_location = base.framework._close_location(rows[idx])
    ret20 = base.framework._ret(rows, idx, 20)
    ret60 = base.framework._ret(rows, idx, 60)
    spy_ret20 = base.framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = base.framework._ret(spy_rows, spy_idx, 60)
    realized_vol = base.framework._realized_vol(rows, idx, 20)
    required = (signal_return, close_location, ret20, ret60, spy_ret20, spy_ret60, realized_vol)
    if any(value is None for value in required):
        return None
    assert signal_return is not None and close_location is not None
    assert ret20 is not None and ret60 is not None
    assert spy_ret20 is not None and spy_ret60 is not None and realized_vol is not None
    if signal_return < base.MIN_SIGNAL_RETURN or signal_return > base.MAX_SIGNAL_RETURN:
        return None
    if close_location < base.MIN_CLOSE_LOCATION:
        return None
    if realized_vol > base.MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < base.MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < base.MIN_RET60_EXCESS_SPY:
        return None
    volume_ratio = base.framework._volume_ratio(rows, idx) or 0.0
    return {
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _normalise_rows(rows: Any) -> list[dict[str, Any]]:
    if rows is None:
        return []
    out: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        date_text = str(raw.get("Date") or raw.get("date") or "")[:10]
        if len(date_text) != 10:
            continue
        out.append({**raw, "Date": date_text})
    out.sort(key=lambda row: row["Date"])
    return out


def _form_base(row: dict[str, Any]) -> str:
    raw = row.get("form_base") or row.get("form_type") or row.get("form") or ""
    text = str(raw).upper().strip()
    if text == "6-K/A":
        return "6-K/A"
    return "6-K" if text.startswith("6-K") else text


def _clean_excerpt(text: str) -> str:
    return " ".join(str(text or "").split())[:420]


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float_or_none(value)
    if number is None:
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)
