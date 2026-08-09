"""Default-off FDA Orange Book fresh-NEWA release-basket paper sleeve.

The official monthly Additions/Deletions PDF is the point-in-time source.  Its
recorded HTTP ``Last-Modified`` timestamp is the signal clock; approval dates
are used only to reject stale rows.  Holder attribution uses a preregistered
exact-alias table with effective dates.  No substring/fuzzy company matching,
outcome-driven ranking, or live order path exists here.

Historical replay and the prospective state writer share this parser and
policy.  The first manifest observed by a new state is always a historical
seed.  Only documents whose official timestamp is later than the preceding
successful observation can create prospective decisions.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

try:  # Package import in tests; script-style import from quant/run.py.
    from .data_paths import atomic_write_json
except ImportError:  # pragma: no cover - exercised by production import style.
    from data_paths import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = (
    ROOT / "data" / "non_ohlcv" / "fda_orange_book_newa" / "source_manifest.json"
)
DEFAULT_OUTPUT_ROOT = (
    ROOT / "data" / "paper_sleeves" / "fda_orange_book_newa_release_basket"
)
LANDING_URL = (
    "https://www.fda.gov/drugs/drug-approvals-and-databases/"
    "additionsdeletions-prescription-and-otc-drug-product-lists"
)
DOCUMENT_URL_PATTERN = "https://www.fda.gov/media/{media_id}/download?attachment="

RULE_VERSION = "fda_orange_book_fresh_newa_equal_weight_release_basket_nextopen_10d_v1"
SCHEMA_VERSION = "fda_orange_book_newa_release_basket_state_v1"
SLEEVE_NAME = "fda_orange_book_newa_release_basket"
RELEASE_BUDGET_USD = 16_000.0
ROUND_TRIP_COST_PCT = 0.0035
HOLD_SESSIONS = 10
MAX_APPROVAL_AGE_DAYS = 45
TRADE_ENABLED = False
MARKET_TZ = ZoneInfo("America/New_York")


# Each alias is a complete holder alias observed in the official PDF rows.
# Token-boundary matching permits surrounding product columns, but never a
# partial/fuzzy company name.  Effective dates make economic-parent mapping an
# event-date contract instead of a present-day lookup.
ISSUER_MAPPINGS: tuple[dict[str, Any], ...] = (
    {"ticker": "ABBV", "aliases": ("ABBVIE",), "effective_from": "2013-01-02"},
    {"ticker": "AMGN", "aliases": ("AMGEN", "AMGEN INC"), "effective_from": "1983-06-17"},
    {"ticker": "AZN", "aliases": ("ASTRAZENECA",), "effective_from": "1999-04-06"},
    {"ticker": "BAX", "aliases": ("BAXTER HLTHCARE CORP",), "effective_from": "1961-01-01"},
    {"ticker": "BIIB", "aliases": ("BIOGEN",), "effective_from": "1991-09-17"},
    {"ticker": "BMY", "aliases": ("BRISTOL MYERS SQUIBB",), "effective_from": "1989-10-04"},
    {"ticker": "GILD", "aliases": ("GILEAD SCIENCES INC",), "effective_from": "1992-01-22"},
    {"ticker": "GSK", "aliases": ("GLAXOSMITHKLINE",), "effective_from": "2000-12-27"},
    {"ticker": "JNJ", "aliases": ("JANSSEN PRODS", "JANSSEN BIOTECH"), "effective_from": "1961-01-01"},
    {"ticker": "LLY", "aliases": ("ELI LILLY AND CO",), "effective_from": "1952-01-01"},
    {"ticker": "NVS", "aliases": ("NOVARTIS",), "effective_from": "1996-12-17"},
    {"ticker": "PFE", "aliases": ("PFIZER", "HOSPIRA"), "effective_from": "1942-06-22"},
    {
        "ticker": "TEVA",
        "aliases": ("TEVA PHARMS USA INC", "TEVA PHARMS USA", "TEVA PHARMS INC"),
        "effective_from": "1990-03-26",
    },
    {"ticker": "VTRS", "aliases": ("MYLAN", "MYLAN LABS LTD"), "effective_from": "2020-11-16"},
    {"ticker": "VRTX", "aliases": ("VERTEX PHARMS INC",), "effective_from": "1991-07-24"},
    {"ticker": "AMRX", "aliases": ("AMNEAL", "AMNEAL IRELAND LTD"), "effective_from": "2018-05-07"},
    {"ticker": "CORT", "aliases": ("CORCEPT THERAP",), "effective_from": "2004-04-15"},
    {"ticker": "ACAD", "aliases": ("ACADIA PHARMS INC",), "effective_from": "2004-05-27"},
    {"ticker": "RDY", "aliases": ("DR REDDYS",), "effective_from": "2001-04-11"},
    {"ticker": "NBIX", "aliases": ("NEUROCRINE",), "effective_from": "1996-05-23"},
    {"ticker": "IONS", "aliases": ("IONIS PHARMS INC",), "effective_from": "1991-05-17"},
)

_APPROVAL_RE = re.compile(r"\b([A-Z]{3} [0-9]{2}, [0-9]{4})\b")
_APPLICATION_RE = re.compile(
    r"\b(?P<application>[0-9]{4,6})\s+(?P<product>[0-9]{3})\s+"
    r"(?P<approval>[A-Z]{3} [0-9]{2}, [0-9]{4})\b"
)


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _payload_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include a UTC offset: {value!r}")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _iso_date(value: Any) -> str:
    text = str(value or "").strip()
    return date.fromisoformat(text[:10]).isoformat()


def _normalise_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).upper()
    return re.sub(r"\s+", " ", text).strip()


def _alias_present(line: str, alias: str) -> bool:
    pattern = r"(?<![A-Z0-9])" + re.escape(_normalise_text(alias)) + r"(?![A-Z0-9])"
    return re.search(pattern, line) is not None


def map_holder_line_exact(line: str, *, event_date: str) -> str | None:
    """Return one event-date-valid ticker, rejecting partial or ambiguous hits."""
    event = date.fromisoformat(_iso_date(event_date))
    normalized = _normalise_text(line)
    matches: set[str] = set()
    for mapping in ISSUER_MAPPINGS:
        effective_from = date.fromisoformat(mapping["effective_from"])
        effective_to = (
            date.fromisoformat(mapping["effective_to"])
            if mapping.get("effective_to")
            else None
        )
        if event < effective_from or (effective_to and event > effective_to):
            continue
        if any(_alias_present(normalized, alias) for alias in mapping["aliases"]):
            matches.add(str(mapping["ticker"]))
    return next(iter(matches)) if len(matches) == 1 else None


def _extract_pdf_lines(path: Path) -> list[tuple[int, str]]:
    """Extract page-numbered lines without changing the frozen PDF bytes."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - workspace runtime includes it.
        raise RuntimeError("PyMuPDF is required to parse Orange Book PDFs") from exc
    rows: list[tuple[int, str]] = []
    with fitz.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            rows.extend(
                (page_number, raw_line)
                for raw_line in page.get_text(sort=True).splitlines()
            )
    return rows


def _parse_document_rows(
    document: dict[str, Any], path: Path
) -> tuple[list[dict[str, Any]], Counter[str]]:
    last_modified = _parse_timestamp(document["official_http_last_modified_utc"])
    publication_date = last_modified.date()
    parsed: dict[tuple[str, str], dict[str, Any]] = {}
    rejects: Counter[str] = Counter()
    for page_number, raw_line in _extract_pdf_lines(path):
        line = _normalise_text(raw_line)
        if not line.startswith(">A>"):
            continue
        if re.search(r"(?:^|\s)NEWA$", line) is None:
            rejects["addition_not_terminal_newa"] += 1
            continue
        approval_match = _APPROVAL_RE.search(line)
        application_matches = list(_APPLICATION_RE.finditer(line))
        if approval_match is None or not application_matches:
            rejects["missing_approval_or_application_number"] += 1
            continue
        application_match = application_matches[-1]
        approval_date = datetime.strptime(
            application_match.group("approval"), "%b %d, %Y"
        ).date()
        approval_age_days = (publication_date - approval_date).days
        if not 0 <= approval_age_days <= MAX_APPROVAL_AGE_DAYS:
            rejects["approval_outside_0_45_day_freshness"] += 1
            continue
        ticker = map_holder_line_exact(line, event_date=publication_date.isoformat())
        if ticker is None:
            rejects["unmapped_or_ambiguous_holder"] += 1
            continue
        application_number = application_match.group("application").zfill(6)
        product_number = application_match.group("product")
        key = (ticker, application_number)
        source_line_sha = hashlib.sha256(line.encode("utf-8")).hexdigest()
        prior = parsed.get(key)
        if prior is None:
            parsed[key] = {
                "application_event_id": (
                    f"orange_book:{document['media_id']}:{ticker}:{application_number}"
                ),
                "ticker": ticker,
                "application_number": application_number,
                "product_numbers": [product_number],
                "approval_date": approval_date.isoformat(),
                "approval_age_days": approval_age_days,
                "month": str(document["month"]),
                "media_id": int(document["media_id"]),
                "source_url": str(document["source_url"]),
                "source_relative_path": str(document["relative_path"]),
                "source_pdf_sha256": str(document["sha256"]),
                "official_http_last_modified_utc": _iso_utc(last_modified),
                "signal_timestamp": _iso_utc(last_modified),
                "signal_date": publication_date.isoformat(),
                "approval_date_role": "freshness_metadata_only_not_signal_clock",
                "source_pages": [page_number],
                "source_line_sha256s": [source_line_sha],
                "row_filter": "addition_marker_and_terminal_NEWA",
                "mapping_rule": "exact_event_date_holder_alias_no_fuzzy",
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
            }
        else:
            prior["product_numbers"] = sorted(
                set(prior["product_numbers"]) | {product_number}
            )
            prior["source_pages"] = sorted(set(prior["source_pages"]) | {page_number})
            prior["source_line_sha256s"] = sorted(
                set(prior["source_line_sha256s"]) | {source_line_sha}
            )
    return (
        sorted(
            parsed.values(),
            key=lambda row: (
                row["signal_timestamp"],
                row["ticker"],
                row["application_number"],
            ),
        ),
        rejects,
    )


def load_and_verify_source(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify every official PDF, then return fresh mapped application rows."""
    manifest_file = Path(manifest_path)
    raw_manifest = manifest_file.read_bytes()
    manifest = json.loads(raw_manifest.decode("utf-8-sig"))
    if int(manifest.get("schema_version") or 0) != 1:
        raise ValueError("unsupported Orange Book source manifest schema")
    source = manifest.get("source") or {}
    if source.get("landing_page_url") != LANDING_URL:
        raise ValueError("unexpected Orange Book landing-page identity")
    documents = list(manifest.get("documents") or [])
    if not documents:
        raise ValueError("Orange Book manifest has no documents")

    manifest_root = manifest_file.parent.resolve()
    verified_documents: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    seen_media_ids: set[int] = set()
    seen_months: set[str] = set()
    for source_document in documents:
        document = dict(source_document)
        media_id = int(document.get("media_id") or 0)
        month = str(document.get("month") or "")
        if media_id in seen_media_ids or month in seen_months:
            raise ValueError("duplicate Orange Book media_id or month")
        seen_media_ids.add(media_id)
        seen_months.add(month)
        expected_url = DOCUMENT_URL_PATTERN.format(media_id=media_id)
        if document.get("source_url") != expected_url:
            raise ValueError(f"unexpected official URL for Orange Book media {media_id}")
        last_modified = _parse_timestamp(
            document.get("official_http_last_modified_utc")
        )
        relative_path = Path(str(document.get("relative_path") or ""))
        path = (manifest_root / relative_path).resolve()
        if not path.is_relative_to(manifest_root):
            raise ValueError("Orange Book source path escapes manifest directory")
        if not path.is_file():
            raise FileNotFoundError(path)
        expected_bytes = int(document.get("bytes") or -1)
        if path.stat().st_size != expected_bytes:
            raise ValueError(f"Orange Book PDF byte-count mismatch: {path.name}")
        actual_sha = _file_sha256(path)
        if actual_sha != str(document.get("sha256") or "").lower():
            raise ValueError(f"Orange Book PDF SHA-256 mismatch: {path.name}")
        normalized_document = {
            **document,
            "media_id": media_id,
            "month": month,
            "official_http_last_modified_utc": _iso_utc(last_modified),
            "verified_path": str(path),
            "sha256": actual_sha,
        }
        rows, document_rejects = _parse_document_rows(normalized_document, path)
        rejects.update(document_rejects)
        all_decisions.extend(rows)
        verified_documents.append(normalized_document)

    all_decisions.sort(
        key=lambda row: (
            row["signal_timestamp"], row["ticker"], row["application_number"]
        )
    )
    source_identity = {
        "schema": "fda_orange_book_verified_source_v1",
        "landing_url": LANDING_URL,
        "manifest_path": str(manifest_file),
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "verified_document_count": len(verified_documents),
        "verified_total_bytes": sum(int(row["bytes"]) for row in verified_documents),
        "verified_documents_sha256": _payload_sha256(
            [
                {
                    "media_id": row["media_id"],
                    "month": row["month"],
                    "sha256": row["sha256"],
                    "official_http_last_modified_utc": row[
                        "official_http_last_modified_utc"
                    ],
                }
                for row in verified_documents
            ]
        ),
        "documents": verified_documents,
        "fresh_mapped_application_count": len(all_decisions),
        "parse_reject_totals": dict(sorted(rejects.items())),
        "rule_version": RULE_VERSION,
    }
    return all_decisions, source_identity


def _equal_notional_by_ticker(tickers: list[str]) -> dict[str, float]:
    ordered = sorted(set(tickers))
    if not ordered:
        return {}
    total_cents = int(round(RELEASE_BUDGET_USD * 100))
    base, remainder = divmod(total_cents, len(ordered))
    return {
        ticker: (base + (1 if index < remainder else 0)) / 100.0
        for index, ticker in enumerate(ordered)
    }


def build_historical_release_legs(
    decisions: Iterable[dict[str, Any]],
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    """Collapse applications into one equal-weight issuer leg per release."""
    grouped: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for source in decisions:
        row = dict(source)
        grouped[int(row["media_id"])][str(row["ticker"]).upper()].append(row)
    start_iso = _iso_date(start) if start is not None else None
    end_iso = _iso_date(end) if end is not None else None
    legs: list[dict[str, Any]] = []
    for media_id, ticker_rows in grouped.items():
        representative = min(
            (row for rows in ticker_rows.values() for row in rows),
            key=lambda row: (row["signal_timestamp"], row["application_number"]),
        )
        signal_date = str(representative["signal_date"])
        if start_iso and signal_date < start_iso:
            continue
        if end_iso and signal_date > end_iso:
            continue
        notionals = _equal_notional_by_ticker(list(ticker_rows))
        release_leg_count = len(notionals)
        for ticker in sorted(ticker_rows):
            rows = sorted(ticker_rows[ticker], key=lambda row: row["application_number"])
            application_numbers = sorted({row["application_number"] for row in rows})
            leg = {
                "decision_id": f"orange_book_newa:{media_id}:{ticker}",
                "release_id": f"orange_book_newa:{media_id}",
                "ticker": ticker,
                "month": representative["month"],
                "media_id": media_id,
                "signal_timestamp": representative["signal_timestamp"],
                "signal_date": signal_date,
                "official_http_last_modified_utc": representative[
                    "official_http_last_modified_utc"
                ],
                "source_url": representative["source_url"],
                "source_relative_path": representative["source_relative_path"],
                "source_pdf_sha256": representative["source_pdf_sha256"],
                "application_numbers": application_numbers,
                "application_count": len(application_numbers),
                "application_event_ids": [row["application_event_id"] for row in rows],
                "source_record_sha256": _payload_sha256(
                    sorted(
                        sha
                        for row in rows
                        for sha in row.get("source_line_sha256s") or []
                    )
                ),
                "release_leg_count": release_leg_count,
                "release_budget_usd": RELEASE_BUDGET_USD,
                "paper_notional_usd": notionals[ticker],
                "notional_usd": notionals[ticker],
                "weight_in_release": round(1.0 / release_leg_count, 10),
                "entry_rule": "next_NYSE_open_after_official_HTTP_Last_Modified_UTC",
                "exit_rule": "tenth_trading_session_close",
                "hold_sessions": HOLD_SESSIONS,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
            }
            legs.append(leg)
    return sorted(legs, key=lambda row: (row["signal_timestamp"], row["ticker"]))


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _normalise_bars(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for source in rows or []:
        row = dict(source)
        try:
            day = _iso_date(row.get("date") or row.get("Date"))
        except (TypeError, ValueError):
            continue
        values = {
            key: _number(row.get(key) if key in row else row.get(key.title()))
            for key in ("open", "high", "low", "close")
        }
        if all(value is not None for value in values.values()):
            by_date[day] = {"date": day, **values}
    return [by_date[day] for day in sorted(by_date)]


def _entry_and_exit_dates(
    signal_timestamp: str,
    market_rows: list[dict[str, Any]],
) -> tuple[str | None, str | None, str]:
    sessions = [row["date"] for row in market_rows]
    if not sessions:
        return None, None, "missing_spy_market_calendar"
    signal = _parse_timestamp(signal_timestamp).astimezone(MARKET_TZ)
    signal_day = signal.date().isoformat()
    before_open = signal.timetz().replace(tzinfo=None) < time(9, 30)
    eligible = [day for day in sessions if day >= signal_day] if before_open else [
        day for day in sessions if day > signal_day
    ]
    if not eligible:
        return None, None, "next_open_not_available"
    entry_date = eligible[0]
    entry_index = sessions.index(entry_date)
    exit_index = entry_index + HOLD_SESSIONS - 1
    if exit_index >= len(sessions):
        return entry_date, None, "incomplete_10_session_horizon"
    return entry_date, sessions[exit_index], "ready"


def _atr_target(rows: list[dict[str, Any]], entry_index: int, entry: float) -> float:
    signal_index = max(0, entry_index - 1)
    true_ranges: list[float] = []
    for index in range(max(0, signal_index - 13), signal_index + 1):
        row = rows[index]
        prior_close = rows[index - 1]["close"] if index else row["close"]
        true_ranges.append(
            max(
                row["high"] - row["low"],
                abs(row["high"] - prior_close),
                abs(row["low"] - prior_close),
            )
        )
    atr = sum(true_ranges) / len(true_ranges) if true_ranges else entry * 0.02
    return round(entry + 3.5 * atr, 4)


def _evaluate_leg(
    leg: dict[str, Any],
    *,
    bars: dict[str, list[dict[str, Any]]],
    window_start: str,
    window_end: str,
) -> tuple[str, dict[str, Any]]:
    ticker = str(leg["ticker"]).upper()
    ticker_rows = bars.get(ticker) or []
    if not ticker_rows:
        return "reject", {**leg, "unsettled_reason": "missing_ticker_bars"}
    entry_date, exit_date, calendar_status = _entry_and_exit_dates(
        str(leg["signal_timestamp"]), bars.get("SPY") or []
    )
    if entry_date is None:
        category = "unsettled" if calendar_status == "next_open_not_available" else "reject"
        return category, {**leg, "unsettled_reason": calendar_status}
    if entry_date < window_start or entry_date > window_end:
        return "reject", {**leg, "unsettled_reason": "entry_outside_window"}
    ticker_index = {row["date"]: index for index, row in enumerate(ticker_rows)}
    entry_index = ticker_index.get(entry_date)
    if entry_index is None:
        return "reject", {**leg, "unsettled_reason": "missing_exact_entry_bar"}
    entry_price = ticker_rows[entry_index]["open"]
    pending = {
        **leg,
        "entry_date": entry_date,
        "entry_price": round(entry_price, 4),
        "target_price": _atr_target(ticker_rows, entry_index, entry_price),
        "target_price_role": (
            "signal_contract_ATR_metadata_only; fixed_10_session_exit_controls_realized_close"
        ),
    }
    if exit_date is None or exit_date > window_end:
        return "unsettled", {
            **pending,
            "unsettled_reason": "incomplete_10_session_horizon",
        }
    exit_index = ticker_index.get(exit_date)
    if exit_index is None:
        return "reject", {**pending, "unsettled_reason": "missing_exact_exit_bar"}
    exit_price = ticker_rows[exit_index]["close"]
    net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
    notional = float(leg["paper_notional_usd"])
    return "trade", {
        **pending,
        "exit_date": exit_date,
        "exit_price": round(exit_price, 4),
        "scheduled_exit_date": exit_date,
        "exit_reason": "scheduled_10_session_horizon_close",
        "hold_sessions_realized": HOLD_SESSIONS,
        "pnl_pct_net": round(net_return, 10),
        "pnl": round(notional * net_return, 2),
        "pnl_usd": round(notional * net_return, 2),
        "outcome_status": "settled",
        "trade_enabled": False,
    }


def replay_orange_book_newa_release_basket_paper_trades(
    *,
    decisions: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    start: str,
    end: str,
) -> dict[str, Any]:
    """Replay all equal-weight issuer legs at next open through session ten."""
    start_iso, end_iso = _iso_date(start), _iso_date(end)
    candidate_legs = build_historical_release_legs(
        decisions, start=start_iso, end=end_iso
    )
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    for leg in candidate_legs:
        category, row = _evaluate_leg(
            leg, bars=bars, window_start=start_iso, window_end=end_iso
        )
        if category == "trade":
            trades.append(row)
        elif category == "unsettled":
            unsettled.append(row)
        else:
            rejects[str(row["unsettled_reason"])] += 1
    survived = len(trades) + len(unsettled)
    return {
        "candidate_legs": candidate_legs,
        "selected_candidates": candidate_legs,
        "trades": trades,
        "unsettled": unsettled,
        "reject_totals": dict(sorted(rejects.items())),
        "signals_generated": len(candidate_legs),
        "signals_survived": survived,
        "survival_rate": round(survived / len(candidate_legs), 6)
        if candidate_legs
        else 0.0,
        "release_count": len({row["release_id"] for row in candidate_legs}),
        "ticker_count": len({row["ticker"] for row in candidate_legs}),
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
    }


def _empty_state() -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "seen_documents": {},
        "decisions": [],
        "pending_decisions": [],
        "open_positions": [],
        "closed_trades": [],
        "trade_enabled": False,
    }


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_state()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"unsupported Orange Book paper state: {path}")
    for key in ("seen_documents", "decisions", "closed_trades"):
        expected = dict if key == "seen_documents" else list
        if not isinstance(payload.get(key), expected):
            raise ValueError(f"invalid Orange Book paper state field: {key}")
    return payload


def _load_default_warehouse_bars(
    tickers: list[str],
    *,
    warehouse_paths: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Use the repo-standard hot/cold warehouse reader for forward settlement."""
    try:
        from .entity_theme_news_observer import _load_warehouse_bars_for_tickers
    except ImportError:  # pragma: no cover - production script-style import.
        from entity_theme_news_observer import _load_warehouse_bars_for_tickers

    return _load_warehouse_bars_for_tickers(
        tickers,
        data_dir=ROOT / "data",
        warehouse_paths=warehouse_paths,
    )


def persist_daily_orange_book_newa_release_basket_paper_sleeve(
    today: str | date | datetime | None = None,
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    output_root: str | Path | None = None,
    observed_at: str | datetime | None = None,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    warehouse_paths: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> dict[str, Any]:
    """Atomically seed/append prospective decisions and mature closed trades."""
    observed = (
        _parse_timestamp(observed_at)
        if observed_at is not None
        else datetime.now(timezone.utc)
    )
    if today is None:
        as_of = observed.date().isoformat()
    elif isinstance(today, datetime):
        as_of = today.date().isoformat()
    elif isinstance(today, date):
        as_of = today.isoformat()
    else:
        as_of = _iso_date(today)
    output = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    state_path = output / "state.json"
    summary_path = output / "latest_summary.json"
    state = _load_state(state_path)
    bootstrap = not state["seen_documents"] and not state["decisions"]
    prior_observed = (
        _parse_timestamp(state["updated_at"])
        if state.get("updated_at")
        else None
    )

    application_decisions, source_identity = load_and_verify_source(manifest_path)
    all_legs = build_historical_release_legs(application_decisions)
    legs_by_media: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for leg in all_legs:
        legs_by_media[int(leg["media_id"])].append(leg)

    new_decisions: list[dict[str, Any]] = []
    seed_documents = 0
    late_documents = 0
    future_documents = 0
    for document in sorted(
        source_identity["documents"],
        key=lambda row: row["official_http_last_modified_utc"],
    ):
        key = str(document["media_id"])
        if key in state["seen_documents"]:
            continue
        modified = _parse_timestamp(document["official_http_last_modified_utc"])
        if modified > observed:
            future_documents += 1
            continue
        if bootstrap:
            status = "historical_manifest_seed_not_forward"
            seed_documents += 1
        elif prior_observed is None or modified <= prior_observed:
            status = "late_discovered_seed_not_forward"
            late_documents += 1
        else:
            status = "prospective_first_seen_document"
            for leg in legs_by_media.get(int(document["media_id"]), []):
                new_decisions.append(
                    {
                        **leg,
                        "first_seen_at": _iso_utc(observed),
                        "availability_timestamp_field": (
                            "official_http_last_modified_utc"
                        ),
                        "forward_event": True,
                        "prospective_evidence_eligible": True,
                        "seed_not_forward": False,
                        "outcome_status": "pending_10_trading_sessions",
                        "entry_date": None,
                        "target_price": None,
                    }
                )
        state["seen_documents"][key] = {
            "media_id": int(document["media_id"]),
            "month": document["month"],
            "sha256": document["sha256"],
            "official_http_last_modified_utc": document[
                "official_http_last_modified_utc"
            ],
            "first_seen_at": _iso_utc(observed),
            "forward_status": status,
            "seed_not_forward": status != "prospective_first_seen_document",
        }

    existing_ids = {str(row["decision_id"]) for row in state["decisions"]}
    for row in new_decisions:
        if row["decision_id"] not in existing_ids:
            state["decisions"].append(row)
            existing_ids.add(row["decision_id"])

    requested_tickers = sorted(
        {str(row.get("ticker") or "").upper() for row in state["decisions"]}
        | {"SPY"}
    )
    if ohlcv_by_ticker is None and state["decisions"]:
        raw_bars, warehouse_summary = _load_default_warehouse_bars(
            requested_tickers, warehouse_paths=warehouse_paths
        )
    elif ohlcv_by_ticker is None:
        raw_bars = {}
        warehouse_summary = {
            "status": "not_needed_no_forward_decisions",
            "requested_tickers": 0,
            "returned_tickers": 0,
        }
    else:
        raw_bars = ohlcv_by_ticker
        warehouse_summary = {
            "status": "provided",
            "requested_tickers": len(requested_tickers),
            "returned_tickers": sum(
                1 for rows in raw_bars.values() if rows is not None
            ),
        }
    bars = {
        str(ticker).upper(): [
            row for row in _normalise_bars(rows) if row["date"] <= as_of
        ]
        for ticker, rows in raw_bars.items()
    }
    closed_ids = {str(row["decision_id"]) for row in state["closed_trades"]}
    newly_closed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    open_positions: list[dict[str, Any]] = []
    refreshed_decisions: list[dict[str, Any]] = []
    for source in state["decisions"]:
        decision = dict(source)
        if decision["decision_id"] in closed_ids:
            refreshed_decisions.append(decision)
            continue
        category, evaluated = _evaluate_leg(
            decision,
            bars=bars,
            window_start="1900-01-01",
            window_end=as_of,
        )
        for key in ("entry_date", "entry_price", "target_price", "target_price_role"):
            if evaluated.get(key) is not None:
                decision[key] = evaluated[key]
        if category == "trade":
            closed = {
                **evaluated,
                "forward_event": True,
                "prospective_evidence_eligible": True,
                "first_seen_at": decision["first_seen_at"],
            }
            state["closed_trades"].append(closed)
            newly_closed.append(closed)
            closed_ids.add(decision["decision_id"])
            decision["outcome_status"] = "settled"
        else:
            decision["outcome_status"] = str(
                evaluated.get("unsettled_reason") or "pending"
            )
            pending.append(decision)
            if decision.get("entry_date"):
                open_positions.append(decision)
        refreshed_decisions.append(decision)
    state["decisions"] = sorted(
        refreshed_decisions, key=lambda row: (row["signal_timestamp"], row["ticker"])
    )
    state["pending_decisions"] = pending
    state["open_positions"] = open_positions
    state.update(
        {
            "updated_at": _iso_utc(observed),
            "as_of_date": as_of,
            "source_manifest_path": str(manifest_path),
            "source_manifest_sha256": source_identity["manifest_sha256"],
            "historical_seed_contract": (
                "bootstrap and late-discovered documents never create forward decisions"
            ),
            "trade_enabled": False,
            "strategy_behavior_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        }
    )
    atomic_write_json(state, state_path, default=str)
    summary = {
        "status": "ok",
        "schema": SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "observed_at": _iso_utc(observed),
        "bootstrap_historical_seed": bootstrap,
        "historical_seed_documents_appended": seed_documents,
        "late_discovered_seed_documents_appended": late_documents,
        "future_document_count": future_documents,
        "new_forward_decision_count": len(new_decisions),
        "decision_count": len(state["decisions"]),
        "pending_count": len(pending),
        "open_position_count": len(open_positions),
        "new_closed_trade_count": len(newly_closed),
        "closed_trade_count": len(state["closed_trades"]),
        "source_identity": source_identity,
        "warehouse": warehouse_summary,
        "state_path": str(state_path),
        "summary_path": str(summary_path),
        "release_budget_usd": RELEASE_BUDGET_USD,
        "hold_sessions": HOLD_SESSIONS,
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }
    atomic_write_json(summary, summary_path, default=str)
    return summary


__all__ = [
    "DEFAULT_MANIFEST_PATH",
    "DEFAULT_OUTPUT_ROOT",
    "DOCUMENT_URL_PATTERN",
    "HOLD_SESSIONS",
    "ISSUER_MAPPINGS",
    "LANDING_URL",
    "MAX_APPROVAL_AGE_DAYS",
    "RELEASE_BUDGET_USD",
    "ROUND_TRIP_COST_PCT",
    "RULE_VERSION",
    "SCHEMA_VERSION",
    "SLEEVE_NAME",
    "TRADE_ENABLED",
    "build_historical_release_legs",
    "load_and_verify_source",
    "map_holder_line_exact",
    "persist_daily_orange_book_newa_release_basket_paper_sleeve",
    "replay_orange_book_newa_release_basket_paper_trades",
]
