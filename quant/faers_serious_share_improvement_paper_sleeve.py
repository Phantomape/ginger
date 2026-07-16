"""Default-off FAERS serious-outcome-share improvement paper sleeve.

The policy in this module is deliberately frozen and source-only.  For each
official quarterly FAERS ASCII release, initial manufacturer reports are
deduplicated by ``caseid``/``caseversion`` and joined to OUTC by ``primaryid``.
Only exact, current-title Healthcare mappings supplied by the caller are
eligible.  A decline in serious-outcome share versus the adjacent quarter is
ranked from most negative to least negative; at most ten issuers form one
fixed USD 10,000 equal-weight basket.

Historical replay and the prospective snapshot call the same parser and
selection functions.  This module never emits an executable order:
``trade_enabled`` is hard-coded to ``False`` and every public result contains
``orders=[]``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any


SLEEVE_NAME = "faers_serious_share_improvement_quarterly_basket"
RULE_VERSION = "faers_serious_share_improvement_equal_weight_20s_v1"
SOURCE_RULE_VERSION = "faers_quarterly_ascii_initial_case_outc_exact_map_v1"

QUARTERS = (
    "2024q2",
    "2024q3",
    "2024q4",
    "2025q1",
    "2025q2",
    "2025q3",
    "2025q4",
)
RELEASE_EFFECTIVE_SESSION = {
    "2024q3": "2024-10-31",
    "2024q4": "2025-01-29",
    "2025q1": "2025-04-29",
    "2025q2": "2025-07-30",
    "2025q3": "2025-10-31",
    "2025q4": "2026-01-28",
}
WINDOW_QUARTERS = {
    "old_thin": ("2024q3", "2024q4"),
    "mid_weak": ("2025q1", "2025q2"),
    "late_strong": ("2025q3", "2025q4"),
}

MIN_CASES_EACH_QUARTER = 100
CASE_VOLUME_RATIO_MIN = 0.5
CASE_VOLUME_RATIO_MAX = 2.0
MAX_ISSUERS_PER_RELEASE = 10
EVENT_NOTIONAL_USD = 10_000.0
HOLD_SESSIONS = 20
ROUND_TRIP_COST_BPS = 35.0
ROUND_TRIP_COST_PCT = ROUND_TRIP_COST_BPS / 10_000.0
ATR_PERIOD = 14
ATR_TARGET_MULTIPLE = 3.5
TRADE_ENABLED = False

FDA_SOURCE_LANDING_URL = (
    "https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-"
    "reporting-system-faers/fda-adverse-event-reporting-system-faers-"
    "quarterly-data-extract-files"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_STOPWORDS = {
    "INC",
    "INCORPORATED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "COMPANIES",
    "LTD",
    "LIMITED",
    "LLC",
    "LP",
    "PLC",
    "NV",
    "SA",
    "AG",
    "THE",
    "COM",
    "HLDG",
    "HLDGS",
    "HOLDING",
    "HOLDINGS",
    "GROUP",
    "GRP",
    "TR",
    "TRUST",
    "NEW",
    "CLASS",
    "CL",
    "SER",
    "SERIES",
    "SH",
    "SHS",
    "SHARES",
    "ADR",
    "ADS",
    "ORD",
    "ORDINARY",
    "COMMON",
    "STK",
    "STOCK",
    "UNIT",
    "UNITS",
    "PAR",
    "A",
    "B",
    "C",
    "AND",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _payload_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_issuer_name(value: Any) -> str:
    """Return the exact-map key used by the preregistered preflight."""

    text = str(value or "").upper().replace("&", " AND ")
    tokens = re.sub(r"[^A-Z0-9 ]+", " ", text).split()
    return " ".join(token for token in tokens if token not in _STOPWORDS)


def _normalise_issuer_index(
    issuer_index: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    rows: list[tuple[str, str, str | None]] = []
    if isinstance(issuer_index, Mapping):
        iterator = issuer_index.items()
        for raw_name, raw_value in iterator:
            if isinstance(raw_value, Mapping):
                ticker = raw_value.get("ticker")
                title = raw_value.get("warehouse_title")
            else:
                ticker = raw_value
                title = None
            rows.append((str(raw_name), str(ticker or ""), str(title) if title else None))
    else:
        for source in issuer_index:
            if not isinstance(source, Mapping):
                raise TypeError("issuer_index rows must be mappings")
            rows.append(
                (
                    str(
                        source.get("normalized_sender")
                        or source.get("issuer_name")
                        or source.get("warehouse_title")
                        or ""
                    ),
                    str(source.get("ticker") or ""),
                    str(source.get("warehouse_title") or "") or None,
                )
            )

    by_key: dict[str, set[str]] = defaultdict(set)
    title_by_pair: dict[tuple[str, str], str | None] = {}
    for raw_name, raw_ticker, title in rows:
        key = normalize_issuer_name(raw_name)
        ticker = raw_ticker.strip().upper()
        if not key or not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
            raise ValueError("issuer_index contains an invalid exact-map row")
        by_key[key].add(ticker)
        title_by_pair[(key, ticker)] = title

    if "VERTEX" in by_key:
        raise ValueError("ambiguous short sender VERTEX must remain fail-closed")
    collisions = {key: values for key, values in by_key.items() if len(values) != 1}
    if collisions:
        raise ValueError(f"issuer_index has normalized-name collisions: {sorted(collisions)}")

    exact = {key: next(iter(values)) for key, values in sorted(by_key.items())}
    manifest = []
    for key, ticker in exact.items():
        row = {"normalized_sender": key, "ticker": ticker}
        title = title_by_pair.get((key, ticker))
        if title:
            row["warehouse_title"] = title
        manifest.append(row)
    return exact, manifest


def _member_with_prefix(archive: zipfile.ZipFile, prefix: str) -> str:
    matches = [
        name
        for name in archive.namelist()
        if Path(name).name.lower().startswith(prefix)
        and name.lower().endswith(".txt")
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {prefix} TXT member, found {matches}")
    return matches[0]


def _reader_field_map(reader: csv.DictReader) -> dict[str, str]:
    return {
        str(name or "").strip().lower(): str(name)
        for name in (reader.fieldnames or [])
    }


def _field(row: Mapping[str, Any], fields: Mapping[str, str], name: str) -> str:
    return str(row.get(fields.get(name, ""), "") or "").strip()


def _parse_quarter(
    path: Path,
    exact_issuer_index: Mapping[str, str],
) -> tuple[dict[str, dict[str, float | int]], dict[str, Any]]:
    """Parse one verified FAERS ZIP without fuzzy/entity-substring matching."""

    with zipfile.ZipFile(path) as archive:
        demo_member = _member_with_prefix(archive, "demo")
        outc_member = _member_with_prefix(archive, "outc")

        serious_primaryids: set[str] = set()
        outc_row_count = 0
        with archive.open(outc_member) as raw:
            text = io.TextIOWrapper(raw, encoding="latin1", newline="")
            reader = csv.DictReader(text, delimiter="$", quotechar='"')
            fields = _reader_field_map(reader)
            if not {"primaryid", "outc_cod"}.issubset(fields):
                raise ValueError(f"FAERS OUTC schema mismatch in {path.name}")
            for row in reader:
                outc_row_count += 1
                primaryid = _field(row, fields, "primaryid")
                if primaryid and _field(row, fields, "outc_cod"):
                    serious_primaryids.add(primaryid)

        latest_initial: dict[str, tuple[int, str, str]] = {}
        conflicted_cases: set[str] = set()
        demo_row_count = 0
        initial_row_count = 0
        invalid_caseversion_count = 0
        with archive.open(demo_member) as raw:
            text = io.TextIOWrapper(raw, encoding="latin1", newline="")
            reader = csv.DictReader(text, delimiter="$", quotechar='"')
            fields = _reader_field_map(reader)
            required = {
                "primaryid",
                "caseid",
                "caseversion",
                "i_f_code",
                "mfr_sndr",
            }
            if not required.issubset(fields):
                raise ValueError(f"FAERS DEMO schema mismatch in {path.name}")
            for row in reader:
                demo_row_count += 1
                if _field(row, fields, "i_f_code").upper() != "I":
                    continue
                initial_row_count += 1
                caseid = _field(row, fields, "caseid")
                primaryid = _field(row, fields, "primaryid")
                sender = _field(row, fields, "mfr_sndr")
                if not caseid or not primaryid or not sender:
                    continue
                try:
                    caseversion = int(_field(row, fields, "caseversion"))
                except ValueError:
                    invalid_caseversion_count += 1
                    continue
                candidate = (caseversion, primaryid, sender)
                prior = latest_initial.get(caseid)
                if prior is None or caseversion > prior[0]:
                    latest_initial[caseid] = candidate
                    conflicted_cases.discard(caseid)
                elif caseversion == prior[0] and candidate[1:] != prior[1:]:
                    # Equal-version conflicts cannot be ordered point in time.
                    conflicted_cases.add(caseid)

    counts: dict[str, Counter[str]] = defaultdict(Counter)
    unmapped_case_count = 0
    short_vertex_case_count = 0
    for caseid, (_, primaryid, sender) in latest_initial.items():
        if caseid in conflicted_cases:
            continue
        sender_key = normalize_issuer_name(sender)
        if sender_key == "VERTEX":
            short_vertex_case_count += 1
            continue
        ticker = exact_issuer_index.get(sender_key)
        if ticker is None:
            unmapped_case_count += 1
            continue
        counts[ticker]["initial_cases"] += 1
        if primaryid in serious_primaryids:
            counts[ticker]["serious_cases"] += 1

    quarterly = {
        ticker: {
            "initial_cases": int(values["initial_cases"]),
            "serious_cases": int(values["serious_cases"]),
            "serious_share": values["serious_cases"] / values["initial_cases"],
        }
        for ticker, values in sorted(counts.items())
        if values["initial_cases"]
    }
    audit = {
        "demo_member": demo_member,
        "outc_member": outc_member,
        "demo_row_count": demo_row_count,
        "initial_row_count": initial_row_count,
        "latest_initial_case_count": len(latest_initial),
        "equal_version_conflict_case_count": len(conflicted_cases),
        "invalid_caseversion_count": invalid_caseversion_count,
        "outc_row_count": outc_row_count,
        "serious_primaryid_count": len(serious_primaryids),
        "mapped_initial_case_count": sum(
            int(row["initial_cases"]) for row in quarterly.values()
        ),
        "unmapped_initial_case_count": unmapped_case_count,
        "short_vertex_fail_closed_case_count": short_vertex_case_count,
        "mapped_ticker_count": len(quarterly),
    }
    return quarterly, audit


def load_hash_bound_faers_quarters(
    raw_dir: str | Path,
    expected_sha256_by_quarter: Mapping[str, str],
    issuer_index: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, dict[str, float | int]]], dict[str, Any]]:
    """Verify all seven frozen ZIPs, then parse their exact-mapped counts."""

    raw_path = Path(raw_dir).resolve()
    if set(expected_sha256_by_quarter) != set(QUARTERS):
        raise ValueError("expected_sha256_by_quarter must contain exactly seven fixed quarters")
    exact_index, issuer_manifest = _normalise_issuer_index(issuer_index)

    quarterly: dict[str, dict[str, dict[str, float | int]]] = {}
    files: list[dict[str, Any]] = []
    bundle_digest = hashlib.sha256()
    for quarter in QUARTERS:
        expected = str(expected_sha256_by_quarter[quarter]).strip().lower()
        if _SHA256_RE.fullmatch(expected) is None:
            raise ValueError(f"invalid expected SHA-256 for {quarter}")
        path = (raw_path / f"faers_ascii_{quarter}.zip").resolve()
        if not path.is_relative_to(raw_path):  # pragma: no cover - fixed filename.
            raise ValueError("FAERS source path escapes raw_dir")
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = _file_sha256(path)
        if actual != expected:
            raise ValueError(f"FAERS ZIP hash mismatch for {quarter}")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                bundle_digest.update(chunk)
        counts, parse_audit = _parse_quarter(path, exact_index)
        quarterly[quarter] = counts
        files.append(
            {
                "quarter": quarter,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": actual,
                "parse_audit": parse_audit,
            }
        )

    source_provenance = {
        "schema": "faers_hash_bound_quarterly_source_v1",
        "source_rule_version": SOURCE_RULE_VERSION,
        "official_source": "FDA Adverse Event Reporting System quarterly ASCII extracts",
        "official_source_landing_url": FDA_SOURCE_LANDING_URL,
        "raw_dir": str(raw_path),
        "quarter_count": len(files),
        "quarters": list(QUARTERS),
        "zip_sha256": {row["quarter"]: row["sha256"] for row in files},
        "total_bytes": sum(int(row["bytes"]) for row in files),
        "concatenated_bundle_sha256": bundle_digest.hexdigest(),
        "files": files,
        "release_effective_sessions": dict(RELEASE_EFFECTIVE_SESSION),
        "release_clock_rule": (
            "fixed preregistered first regular session after official quarterly availability"
        ),
        "issuer_map_rule": "Healthcare current-title normalized exact equality only",
        "issuer_map_entry_count": len(issuer_manifest),
        "issuer_map_sha256": _payload_sha256(issuer_manifest),
        "short_vertex_fail_closed": True,
    }
    return quarterly, source_provenance


def build_quarterly_candidates(
    quarterly_counts: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Apply the frozen adjacent-quarter eligibility, ranking, and top-ten cap."""

    selected_by_quarter: dict[str, list[dict[str, Any]]] = {}
    audit_by_quarter: dict[str, dict[str, Any]] = {}
    for index, quarter in enumerate(QUARTERS):
        if index == 0:
            selected_by_quarter[quarter] = []
            audit_by_quarter[quarter] = {
                "prior_quarter": None,
                "mapped_ticker_count": len(quarterly_counts.get(quarter, {})),
                "common_ticker_count": 0,
                "eligible_adjacent_pair_count": 0,
                "improving_eligible_count": 0,
                "selected_count": 0,
                "reject_totals": {},
            }
            continue
        prior_quarter = QUARTERS[index - 1]
        current_rows = quarterly_counts.get(quarter, {})
        prior_rows = quarterly_counts.get(prior_quarter, {})
        common = sorted(set(current_rows) & set(prior_rows))
        eligible: list[dict[str, Any]] = []
        rejects: Counter[str] = Counter()
        for ticker in common:
            current = current_rows[ticker]
            prior = prior_rows[ticker]
            try:
                current_cases = int(current["initial_cases"])
                prior_cases = int(prior["initial_cases"])
                current_share = float(current["serious_share"])
                prior_share = float(prior["serious_share"])
            except (KeyError, TypeError, ValueError):
                rejects["invalid_quarterly_count_row"] += 1
                continue
            if min(current_cases, prior_cases) < MIN_CASES_EACH_QUARTER:
                rejects["minimum_cases_not_met"] += 1
                continue
            ratio = current_cases / prior_cases
            if not CASE_VOLUME_RATIO_MIN <= ratio <= CASE_VOLUME_RATIO_MAX:
                rejects["case_volume_ratio_outside_range"] += 1
                continue
            delta = current_share - prior_share
            eligible.append(
                {
                    "decision_id": f"faers:{quarter}:{ticker}",
                    "quarter": quarter,
                    "prior_quarter": prior_quarter,
                    "release_effective_session": RELEASE_EFFECTIVE_SESSION[quarter],
                    "ticker": str(ticker).upper(),
                    "current_initial_cases": current_cases,
                    "prior_initial_cases": prior_cases,
                    "case_volume_ratio": ratio,
                    "current_serious_share": current_share,
                    "prior_serious_share": prior_share,
                    "serious_share_delta": delta,
                    "signal_rule": "strictly_negative_serious_outcome_share_delta",
                    "ranking_rule": "most_negative_delta_first_ticker_tiebreak",
                    "rule_version": RULE_VERSION,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )
        eligible.sort(key=lambda row: (row["serious_share_delta"], row["ticker"]))
        improving = [row for row in eligible if row["serious_share_delta"] < 0]
        selected = [dict(row) for row in improving[:MAX_ISSUERS_PER_RELEASE]]
        notionals = _equal_weight_notionals([row["ticker"] for row in selected])
        for rank, row in enumerate(selected, start=1):
            row["selection_rank"] = rank
            row["selected"] = True
            row["release_selected_count"] = len(selected)
            row["weight_in_release"] = round(1.0 / len(selected), 10)
            row["event_notional_usd"] = EVENT_NOTIONAL_USD
            row["notional_usd"] = notionals[row["ticker"]]
            row["paper_notional_usd"] = notionals[row["ticker"]]
            row["entry_rule"] = (
                "first_regular_market_session_open_on_or_after_release_effective_session"
            )
            row["exit_rule"] = "twentieth_market_session_close"
            row["hold_sessions"] = HOLD_SESSIONS
            row["round_trip_cost_bps"] = ROUND_TRIP_COST_BPS
        selected_by_quarter[quarter] = selected
        audit_by_quarter[quarter] = {
            "prior_quarter": prior_quarter,
            "mapped_ticker_count": len(current_rows),
            "common_ticker_count": len(common),
            "eligible_adjacent_pair_count": len(eligible),
            "improving_eligible_count": len(improving),
            "selected_count": len(selected),
            "reject_totals": dict(sorted(rejects.items())),
        }
    return selected_by_quarter, audit_by_quarter


def _equal_weight_notionals(tickers: Sequence[str]) -> dict[str, float]:
    ordered = list(tickers)
    if len(set(ordered)) != len(ordered):
        raise ValueError("one quarterly release cannot select a ticker twice")
    if not ordered:
        return {}
    total_cents = int(round(EVENT_NOTIONAL_USD * 100))
    base, remainder = divmod(total_cents, len(ordered))
    return {
        ticker: (base + (1 if index < remainder else 0)) / 100.0
        for index, ticker in enumerate(ordered)
    }


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _finite_positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _normalise_bars(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for source in rows or []:
        day = _iso_date(source.get("date") or source.get("Date"))
        open_price = _finite_positive(source.get("open") or source.get("Open"))
        high = _finite_positive(source.get("high") or source.get("High"))
        low = _finite_positive(source.get("low") or source.get("Low"))
        close = _finite_positive(source.get("close") or source.get("Close"))
        if day is None or None in (open_price, high, low, close):
            continue
        if low > min(open_price, close) or high < max(open_price, close) or high < low:
            continue
        by_date[day] = {
            "date": day,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        }
    return [by_date[day] for day in sorted(by_date)]


def _normalise_ohlcv(
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }


def _normalise_calendar(
    market_calendar: Iterable[Any] | None,
    bars_by_ticker: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[str]:
    days: set[str] = set()
    if market_calendar is not None:
        for raw in market_calendar:
            if isinstance(raw, Mapping):
                value = raw.get("date") or raw.get("session") or raw.get("Date")
            else:
                value = raw
            day = _iso_date(value)
            if day:
                days.add(day)
    else:
        for rows in bars_by_ticker.values():
            days.update(str(row["date"]) for row in rows)
    if not days:
        raise ValueError("market_calendar has no valid sessions")
    return sorted(days)


def _normalise_windows(
    standard_windows: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    windows: list[dict[str, str]] = []
    if isinstance(standard_windows, Mapping):
        iterator = standard_windows.items()
        for name, value in iterator:
            if isinstance(value, Mapping):
                start, end = value.get("start"), value.get("end")
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                start, end = value[0], value[1]
            else:
                raise TypeError("standard window must be a mapping or (start, end)")
            windows.append({"name": str(name), "start": str(start), "end": str(end)})
    else:
        for value in standard_windows:
            windows.append(
                {
                    "name": str(value.get("name")),
                    "start": str(value.get("start")),
                    "end": str(value.get("end")),
                }
            )
    normalized: list[dict[str, str]] = []
    for row in windows:
        start = _iso_date(row["start"])
        end = _iso_date(row["end"])
        if not row["name"] or start is None or end is None or start > end:
            raise ValueError(f"invalid standard window: {row}")
        normalized.append({"name": row["name"], "start": start, "end": end})
    if len(normalized) != 3 or len({row["name"] for row in normalized}) != 3:
        raise ValueError("FAERS historical replay requires exactly three named windows")
    return normalized


def _first_session_on_or_after(sessions: Sequence[str], value: str) -> int | None:
    for index, day in enumerate(sessions):
        if day >= value:
            return index
    return None


def _atr_target(
    rows: Sequence[Mapping[str, Any]],
    entry_date: str,
    entry_price: float,
) -> tuple[float | None, str | None]:
    prior = [row for row in rows if row["date"] < entry_date]
    if not prior:
        return None, None
    sample = prior[-ATR_PERIOD:]
    true_ranges: list[float] = []
    prior_close: float | None = None
    for row in sample:
        high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
        true_range = high - low
        if prior_close is not None:
            true_range = max(true_range, abs(high - prior_close), abs(low - prior_close))
        true_ranges.append(true_range)
        prior_close = close
    atr = sum(true_ranges) / len(true_ranges)
    return round(entry_price + ATR_TARGET_MULTIPLE * atr, 6), str(sample[-1]["date"])


def _candidate_with_schedule(
    candidate: Mapping[str, Any],
    bars_by_ticker: Mapping[str, Sequence[Mapping[str, Any]]],
    sessions: Sequence[str],
) -> tuple[dict[str, Any], str | None]:
    row = dict(candidate)
    entry_index = _first_session_on_or_after(
        sessions, str(row["release_effective_session"])
    )
    entry_date = sessions[entry_index] if entry_index is not None else None
    exit_index = entry_index + HOLD_SESSIONS - 1 if entry_index is not None else None
    exit_date = (
        sessions[exit_index]
        if exit_index is not None and exit_index < len(sessions)
        else None
    )
    ticker_bars = list(bars_by_ticker.get(str(row["ticker"]), []))
    bar_by_date = {str(bar["date"]): bar for bar in ticker_bars}
    entry_bar = bar_by_date.get(entry_date or "")
    entry_price = float(entry_bar["open"]) if entry_bar else None
    target_price = None
    target_lookback_end = None
    if entry_date and entry_price:
        target_price, target_lookback_end = _atr_target(
            ticker_bars, entry_date, entry_price
        )
    row.update(
        {
            "entry_date": entry_date,
            "entry_price": round(entry_price, 6) if entry_price else None,
            "target_price": target_price,
            "target_price_semantics": "sentinel_only_not_exit_driver",
            "target_price_is_exit_driver": False,
            "target_price_lookback_end_date": target_lookback_end,
            "scheduled_exit_date": exit_date,
        }
    )
    if entry_date is None:
        return row, "market_calendar_missing_entry_session"
    if entry_bar is None:
        return row, "missing_entry_open"
    if target_price is None:
        return row, "missing_pre_entry_atr_history"
    if exit_date is None:
        return row, "market_calendar_not_yet_through_session20"
    if exit_date not in bar_by_date:
        return row, "missing_session20_close"
    return row, None


def _settle_candidate(
    scheduled: Mapping[str, Any],
    bars_by_ticker: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    row = dict(scheduled)
    bar_by_date = {
        str(bar["date"]): bar for bar in bars_by_ticker[str(row["ticker"])]
    }
    exit_date = str(row["scheduled_exit_date"])
    exit_price = float(bar_by_date[exit_date]["close"])
    entry_price = float(row["entry_price"])
    gross_return = exit_price / entry_price - 1.0
    net_return = gross_return - ROUND_TRIP_COST_PCT
    row.update(
        {
            "exit_date": exit_date,
            "exit_price": round(exit_price, 6),
            "hold_sessions_realized": HOLD_SESSIONS,
            "gross_return": round(gross_return, 10),
            "net_return": round(net_return, 10),
            "pnl_pct_net": round(net_return, 10),
            "pnl": round(float(row["notional_usd"]) * net_return, 2),
            "exit_reason": "scheduled_session20_close",
            "paper_status": "closed",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return row


def _top1_share(rows: Sequence[Mapping[str, Any]]) -> float:
    counts = Counter(str(row["ticker"]) for row in rows)
    return max(counts.values(), default=0) / len(rows) if rows else 0.0


def _production_impact() -> dict[str, Any]:
    return {
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "alters_live_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "max_displacement": 0,
    }


def policy_provenance() -> dict[str, Any]:
    return {
        "rule_version": RULE_VERSION,
        "gate_shape": "standalone_quarterly_candidate_pool",
        "signal": "strictly_negative_serious_outcome_share_delta",
        "ranking": "most_negative_delta_first_ticker_tiebreak",
        "max_issuers_per_release": MAX_ISSUERS_PER_RELEASE,
        "minimum_cases_each_adjacent_quarter": MIN_CASES_EACH_QUARTER,
        "case_volume_ratio_min": CASE_VOLUME_RATIO_MIN,
        "case_volume_ratio_max": CASE_VOLUME_RATIO_MAX,
        "entry": "first_regular_session_open_on_or_after_release_effective_session",
        "exit": "20th_session_close",
        "hold_sessions": HOLD_SESSIONS,
        "event_notional_usd": EVENT_NOTIONAL_USD,
        "allocation": "equal_weight_within_release_without_bar_availability_replacement",
        "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
        "target_price": f"entry_open_plus_{ATR_TARGET_MULTIPLE}x_pre_entry_ATR_sentinel_only",
        "trade_enabled": False,
    }


def _replay_window(
    *,
    window: Mapping[str, str],
    selected_by_quarter: Mapping[str, Sequence[Mapping[str, Any]]],
    audit_by_quarter: Mapping[str, Mapping[str, Any]],
    bars_by_ticker: Mapping[str, Sequence[Mapping[str, Any]]],
    sessions: Sequence[str],
) -> dict[str, Any]:
    selected_source = [
        dict(row)
        for quarter in QUARTERS[1:]
        for row in selected_by_quarter[quarter]
        if window["start"] <= str(row["release_effective_session"]) <= window["end"]
    ]
    selected: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()
    for source in selected_source:
        scheduled, reason = _candidate_with_schedule(source, bars_by_ticker, sessions)
        selected.append(scheduled)
        if reason:
            unsettled.append({**scheduled, "unsettled_reason": reason, "paper_status": "unsettled"})
            rejects[reason] += 1
        else:
            trades.append(_settle_candidate(scheduled, bars_by_ticker))

    included_quarters = [
        quarter
        for quarter in QUARTERS[1:]
        if window["start"] <= RELEASE_EFFECTIVE_SESSION[quarter] <= window["end"]
    ]
    generated = sum(
        int(audit_by_quarter[quarter]["eligible_adjacent_pair_count"])
        for quarter in included_quarters
    )
    survived = len(selected_source)
    coverage = {
        "included_quarters": included_quarters,
        "eligible_adjacent_pair_count": generated,
        "selected_count": survived,
        "settled_trade_count": len(trades),
        "unsettled_count": len(unsettled),
        "unique_ticker_count": len({row["ticker"] for row in selected_source}),
        "top1_share": _top1_share(selected_source),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else 0.0,
        "entry_date_present_count": sum(bool(row["entry_date"]) for row in selected),
        "target_price_present_count": sum(bool(row["target_price"]) for row in selected),
        "settled_sentinel_contract_passed": all(
            bool(row["entry_date"] and row["target_price"]) for row in trades
        ),
        "event_notional_sums_usd": {
            quarter: round(
                sum(
                    float(row["notional_usd"])
                    for row in selected_source
                    if row["quarter"] == quarter
                ),
                2,
            )
            for quarter in included_quarters
        },
        "unsettled_reason_totals": dict(sorted(rejects.items())),
    }
    return {
        "schema": "faers_serious_share_improvement_window_replay_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "window": dict(window),
        "selected": selected,
        "trades": trades,
        "unsettled": unsettled,
        "coverage": coverage,
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": coverage["survival_rate"],
        "trade_enabled": False,
        "orders": [],
        "production_impact": _production_impact(),
    }


def build_historical_replay(
    raw_dir: str | Path,
    expected_sha256_by_quarter: Mapping[str, str],
    issuer_index: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    standard_windows: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    market_calendar: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Build the three standard historical windows from hash-bound sources."""

    windows = _normalise_windows(standard_windows)
    quarterly, source_provenance = load_hash_bound_faers_quarters(
        raw_dir, expected_sha256_by_quarter, issuer_index
    )
    selected_by_quarter, selection_audit = build_quarterly_candidates(quarterly)
    bars_by_ticker = _normalise_ohlcv(ohlcv_by_ticker)
    sessions = _normalise_calendar(market_calendar, bars_by_ticker)
    replay_by_window = {
        window["name"]: _replay_window(
            window=window,
            selected_by_quarter=selected_by_quarter,
            audit_by_quarter=selection_audit,
            bars_by_ticker=bars_by_ticker,
            sessions=sessions,
        )
        for window in windows
    }
    all_trades = [
        trade for replay in replay_by_window.values() for trade in replay["trades"]
    ]
    all_selected = [
        row for replay in replay_by_window.values() for row in replay["selected"]
    ]
    return {
        "schema": "faers_serious_share_improvement_historical_replay_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "orders": [],
        "policy": policy_provenance(),
        "source_provenance": source_provenance,
        "selection_audit_by_quarter": selection_audit,
        "selected_by_quarter_sha256": _payload_sha256(selected_by_quarter),
        "windows": replay_by_window,
        "aggregate_coverage": {
            "selected_count": len(all_selected),
            "settled_trade_count": len(all_trades),
            "unsettled_count": len(all_selected) - len(all_trades),
            "unique_ticker_count": len({row["ticker"] for row in all_selected}),
            "top1_share": _top1_share(all_selected),
            "window_selected_counts": {
                name: len(replay["selected"])
                for name, replay in replay_by_window.items()
            },
            "window_settled_trade_counts": {
                name: len(replay["trades"])
                for name, replay in replay_by_window.items()
            },
            "settled_sentinel_contract_passed": all(
                bool(row["entry_date"] and row["target_price"])
                for row in all_trades
            ),
        },
        "production_impact": _production_impact(),
    }


def build_paper_snapshot(
    raw_dir: str | Path,
    expected_sha256_by_quarter: Mapping[str, str],
    issuer_index: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    as_of_date: str,
    market_calendar: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Build active source-only paper candidates as of one market date.

    The snapshot never reads a post-entry outcome.  It includes a selected leg
    while it is pending or open through its scheduled twentieth-session close.
    """

    as_of = _iso_date(as_of_date)
    if as_of is None:
        raise ValueError(f"invalid as_of_date: {as_of_date!r}")
    quarterly, source_provenance = load_hash_bound_faers_quarters(
        raw_dir, expected_sha256_by_quarter, issuer_index
    )
    selected_by_quarter, selection_audit = build_quarterly_candidates(quarterly)
    bars_by_ticker = _normalise_ohlcv(ohlcv_by_ticker)
    sessions = _normalise_calendar(market_calendar, bars_by_ticker)

    candidates: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    active_quarters: set[str] = set()
    for quarter in QUARTERS[1:]:
        if RELEASE_EFFECTIVE_SESSION[quarter] > as_of:
            continue
        for source in selected_by_quarter[quarter]:
            scheduled, reason = _candidate_with_schedule(source, bars_by_ticker, sessions)
            entry_date = scheduled.get("entry_date")
            exit_date = scheduled.get("scheduled_exit_date")
            if entry_date is None:
                continue
            # A known scheduled close remains active through that day's close.
            if exit_date is not None and as_of > exit_date:
                continue
            if exit_date is None:
                elapsed = sum(entry_date <= day <= as_of for day in sessions)
                if elapsed > HOLD_SESSIONS:
                    continue
            snapshot_row = {
                **scheduled,
                "as_of_date": as_of,
                "paper_status": "pending" if as_of < entry_date else "open",
                "snapshot_unsettled_reason": reason,
                "trade_enabled": False,
                "alters_orders": False,
            }
            # No exit price, return, or PnL is exposed on this forward surface.
            for forbidden in ("exit_price", "gross_return", "net_return", "pnl"):
                snapshot_row.pop(forbidden, None)
            candidates.append(snapshot_row)
            active_quarters.add(quarter)
            if snapshot_row["paper_status"] == "pending":
                pending.append(snapshot_row)
            else:
                positions.append(snapshot_row)

    candidates.sort(key=lambda row: (row["release_effective_session"], row["selection_rank"], row["ticker"]))
    pending.sort(key=lambda row: (row["entry_date"], row["selection_rank"], row["ticker"]))
    positions.sort(key=lambda row: (row["entry_date"], row["selection_rank"], row["ticker"]))
    generated = sum(
        int(selection_audit[quarter]["eligible_adjacent_pair_count"])
        for quarter in active_quarters
    )
    coverage = {
        "active_quarters": sorted(active_quarters),
        "candidate_count": len(candidates),
        "pending_entry_count": len(pending),
        "paper_position_count": len(positions),
        "unique_ticker_count": len({row["ticker"] for row in candidates}),
        "top1_share": _top1_share(candidates),
        "signals_generated": generated,
        "signals_survived": len(candidates),
        "survival_rate": round(len(candidates) / generated, 6) if generated else 0.0,
        "entry_date_present_count": sum(bool(row["entry_date"]) for row in candidates),
        "target_price_present_count": sum(bool(row["target_price"]) for row in candidates),
    }
    return {
        "schema": "faers_serious_share_improvement_default_off_snapshot_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "pending_entries": pending,
        "paper_positions": positions,
        "coverage": coverage,
        "orders": [],
        "policy": policy_provenance(),
        "source_provenance": source_provenance,
        "selection_audit_by_quarter": selection_audit,
        "production_impact": _production_impact(),
    }


__all__ = [
    "ATR_PERIOD",
    "ATR_TARGET_MULTIPLE",
    "CASE_VOLUME_RATIO_MAX",
    "CASE_VOLUME_RATIO_MIN",
    "EVENT_NOTIONAL_USD",
    "HOLD_SESSIONS",
    "MAX_ISSUERS_PER_RELEASE",
    "MIN_CASES_EACH_QUARTER",
    "QUARTERS",
    "RELEASE_EFFECTIVE_SESSION",
    "ROUND_TRIP_COST_BPS",
    "ROUND_TRIP_COST_PCT",
    "RULE_VERSION",
    "SLEEVE_NAME",
    "TRADE_ENABLED",
    "WINDOW_QUARTERS",
    "build_historical_replay",
    "build_paper_snapshot",
    "build_quarterly_candidates",
    "load_hash_bound_faers_quarters",
    "normalize_issuer_name",
    "policy_provenance",
]
