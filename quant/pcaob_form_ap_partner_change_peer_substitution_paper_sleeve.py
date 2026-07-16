"""Shared default-off PCAOB Form AP partner-change peer sleeve.

The helper is intentionally offline: callers inject a previously downloaded
official ``FirmFilings.zip`` path and its expected SHA-256.  The archive is
hashed before it is parsed and a mismatch fails closed.  Historical replay and
the daily paper snapshot use the same source filters, CIK/share-class mapping,
partner-change detector, peer ranking, and availability clock.

The policy never emits orders.  A Form AP filing becomes observable one
calendar day after its filing date and may enter only at the first market open
*strictly after* that availability date.  This conservative clock avoids using
the PCAOB daily dataset refresh before it could have contained the filing.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SLEEVE_NAME = "PCAOB_FORM_AP_PARTNER_CHANGE_PEER_SUBSTITUTION_PAPER"
RULE_VERSION = "pcaob_form_ap_partner_change_peer_top1_20s_v1"
OFFICIAL_ARCHIVE_MEMBER = "FirmFilings.csv"
OFFICIAL_AUDIT_REPORT_TYPE = (
    "Issuer, other than Employee Benefit Plan or Investment Company"
)
AVAILABILITY_LAG_CALENDAR_DAYS = 1
PRIOR_FISCAL_PERIOD_MIN_DAYS = 250
PRIOR_FISCAL_PERIOD_MAX_DAYS = 500
ADV_LOOKBACK_SESSIONS = 60
MIN_TRADABLE_INDUSTRY_PEERS = 2
HOLD_SESSIONS = 20
BASE_NOTIONAL_USD = 4_000.0
ROUND_TRIP_COST_PCT = 0.0035
TRADE_ENABLED = False


_REQUIRED_COLUMNS = {
    "Form Filing ID",
    "Latest Form AP Filing",
    "Amendment Previous Filing",
    "Audit Report Type",
    "Issuer Name",
    "Issuer CIK",
    "Fiscal Period End Date",
    "Engagement Partner ID",
    "Engagement Partner Other Ids",
    "Original Firm Form ID",
    "Amends Firm Form ID",
    "Filing Date",
}


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _field(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        key = name.strip().lower()
        if key in lowered:
            return lowered[key]
    return None


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    candidates = [text, text[:10]]
    formats = (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    )
    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                pass
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def _iso_date(value: Any) -> str | None:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else None


def _canonical_cik(value: Any) -> str | None:
    text = str(value or "").strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    digits = re.sub(r"\D", "", text)
    if not digits or int(digits) <= 0 or len(digits) > 10:
        return None
    return digits.zfill(10)


def _partner_ids(primary: Any, others: Any) -> tuple[str, ...]:
    output: set[str] = set()
    for raw in (primary, others):
        for value in re.split(r"#\^#|[;,|\s]+", str(raw or "").strip()):
            identifier = value.strip().upper()
            if identifier:
                output.add(identifier)
    return tuple(sorted(output))


def _truthy_latest(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true"}


def _false_amendment(value: Any) -> bool:
    return str(value or "").strip().lower() in {"0", "false"}


def _production_impact() -> dict[str, bool]:
    return {
        "trade_enabled": False,
        "alters_orders": False,
        "alters_live_orders": False,
        "alters_core_signal_generation": False,
        "alters_core_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
    }


def policy_provenance() -> dict[str, Any]:
    return {
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "official_archive_member": OFFICIAL_ARCHIVE_MEMBER,
        "audit_report_type": OFFICIAL_AUDIT_REPORT_TYPE,
        "source_filters": {
            "latest_form_ap_filing": "1",
            "amendment_previous_filing": "false",
            "original_firm_form_id": "blank",
            "amends_firm_form_id": "blank",
        },
        "availability_lag_calendar_days": AVAILABILITY_LAG_CALENDAR_DAYS,
        "entry_clock": "first_market_open_strictly_after_availability_date",
        "prior_fiscal_period_gap_days": [
            PRIOR_FISCAL_PERIOD_MIN_DAYS,
            PRIOR_FISCAL_PERIOD_MAX_DAYS,
        ],
        "partner_identity": "primary_id_union_other_ids",
        "share_class_rule": (
            "maximum minimum three-window median close_times_volume; ticker tie-break"
        ),
        "same_iso_filing_week_partner_change_peer_exclusion": True,
        "minimum_tradable_industry_peers": MIN_TRADABLE_INDUSTRY_PEERS,
        "peer_rank": "trailing_60_session_mean_close_times_volume_desc",
        "daily_top_n": 1,
        "hold_sessions": HOLD_SESSIONS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "production_impact": _production_impact(),
    }


def load_hash_bound_pcaob_form_ap_filings(
    source_zip_path: str | Path,
    *,
    expected_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify and parse the official archive with the fixed original-row filter."""

    path = Path(source_zip_path)
    expected = str(expected_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("expected_sha256 must be a 64-character lowercase hex digest")
    archive = path.read_bytes()
    actual = hashlib.sha256(archive).hexdigest()
    if actual != expected:
        raise ValueError(
            f"PCAOB FirmFilings archive hash mismatch: expected {expected}, got {actual}"
        )

    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = bundle.namelist()
        if OFFICIAL_ARCHIVE_MEMBER not in names:
            raise ValueError(
                f"PCAOB archive missing required member {OFFICIAL_ARCHIVE_MEMBER!r}"
            )
        info = bundle.getinfo(OFFICIAL_ARCHIVE_MEMBER)
        raw_csv = bundle.read(OFFICIAL_ARCHIVE_MEMBER)

    reader = csv.DictReader(
        io.StringIO(raw_csv.decode("utf-8-sig"), newline="")
    )
    headers = set(reader.fieldnames or [])
    missing = sorted(_REQUIRED_COLUMNS - headers)
    if missing:
        raise ValueError(f"PCAOB FirmFilings CSV missing columns: {missing}")

    rejects: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    input_count = 0
    for source in reader:
        input_count += 1
        row = dict(source)
        if not _truthy_latest(row.get("Latest Form AP Filing")):
            rejects["not_latest_form_ap_filing"] += 1
            continue
        if not _false_amendment(row.get("Amendment Previous Filing")):
            rejects["amendment_previous_filing_not_false"] += 1
            continue
        if str(row.get("Original Firm Form ID") or "").strip():
            rejects["original_firm_form_id_not_blank"] += 1
            continue
        if str(row.get("Amends Firm Form ID") or "").strip():
            rejects["amends_firm_form_id_not_blank"] += 1
            continue
        if str(row.get("Audit Report Type") or "").strip() != OFFICIAL_AUDIT_REPORT_TYPE:
            rejects["audit_report_type_not_fixed_issuer_type"] += 1
            continue
        cik = _canonical_cik(row.get("Issuer CIK"))
        fiscal_end = _parse_date(row.get("Fiscal Period End Date"))
        filing_at = _parse_datetime(row.get("Filing Date"))
        partners = _partner_ids(
            row.get("Engagement Partner ID"),
            row.get("Engagement Partner Other Ids"),
        )
        filing_id = str(row.get("Form Filing ID") or "").strip()
        if not cik:
            rejects["missing_or_invalid_issuer_cik"] += 1
            continue
        if not fiscal_end:
            rejects["missing_or_invalid_fiscal_period_end"] += 1
            continue
        if not filing_at:
            rejects["missing_or_invalid_filing_date"] += 1
            continue
        if not filing_id:
            rejects["missing_form_filing_id"] += 1
            continue
        if not partners:
            rejects["missing_engagement_partner_ids"] += 1
            continue
        rows.append(
            {
                "form_filing_id": filing_id,
                "issuer_cik": cik,
                "issuer_name": str(row.get("Issuer Name") or "").strip(),
                "fiscal_period_end": fiscal_end.isoformat(),
                "filing_timestamp": filing_at.isoformat(timespec="seconds"),
                "filing_date": filing_at.date().isoformat(),
                "engagement_partner_ids": list(partners),
                "engagement_partner_primary_id": str(
                    row.get("Engagement Partner ID") or ""
                ).strip(),
                "engagement_partner_other_ids": str(
                    row.get("Engagement Partner Other Ids") or ""
                ).strip(),
                "source_record_sha256": _sha(row),
                "source_archive_sha256": actual,
                "source_archive_member": OFFICIAL_ARCHIVE_MEMBER,
            }
        )

    rows.sort(
        key=lambda item: (
            item["issuer_cik"],
            item["fiscal_period_end"],
            item["filing_timestamp"],
            item["form_filing_id"],
        )
    )
    provenance = {
        "source_path": str(path.resolve()),
        "source_filename": path.name,
        "source_archive_sha256": actual,
        "expected_source_archive_sha256": expected,
        "source_archive_size_bytes": len(archive),
        "source_archive_member": OFFICIAL_ARCHIVE_MEMBER,
        "source_member_crc32": f"{info.CRC:08x}",
        "source_member_size_bytes": info.file_size,
        "source_member_compressed_size_bytes": info.compress_size,
        "source_member_sha256": hashlib.sha256(raw_csv).hexdigest(),
        "input_row_count": input_count,
        "filtered_row_count": len(rows),
        "filter_reject_totals": dict(sorted(rejects.items())),
        "policy": policy_provenance(),
    }
    return rows, provenance


def extract_partner_change_events(
    filings: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compare each CIK/fiscal period with its nearest valid prior period.

    If the archive contains more than one original row for the same CIK and
    fiscal period, only the first filing is used.  That is the only row known
    when the partner identity is first reported and avoids later same-period
    rows leaking into the event definition.
    """

    raw = [dict(row) for row in filings]
    by_cik_period: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    rejects: Counter[str] = Counter()
    for row in raw:
        cik = _canonical_cik(row.get("issuer_cik"))
        fiscal = _iso_date(row.get("fiscal_period_end"))
        filing = _parse_datetime(row.get("filing_timestamp") or row.get("filing_date"))
        partners = tuple(sorted(set(row.get("engagement_partner_ids") or [])))
        if not cik or not fiscal or not filing or not partners:
            rejects["invalid_normalised_filing"] += 1
            continue
        row["issuer_cik"] = cik
        row["fiscal_period_end"] = fiscal
        row["filing_timestamp"] = filing.isoformat(timespec="seconds")
        row["filing_date"] = filing.date().isoformat()
        row["engagement_partner_ids"] = list(partners)
        by_cik_period[(cik, fiscal)].append(row)

    first_by_cik_period: dict[tuple[str, str], dict[str, Any]] = {}
    for key, rows in by_cik_period.items():
        ranked = sorted(
            rows,
            key=lambda row: (row["filing_timestamp"], row["form_filing_id"]),
        )
        first_by_cik_period[key] = ranked[0]
        rejects["later_duplicate_cik_fiscal_period"] += max(0, len(ranked) - 1)

    periods_by_cik: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in first_by_cik_period.values():
        periods_by_cik[row["issuer_cik"]].append(row)
    for rows in periods_by_cik.values():
        rows.sort(
            key=lambda row: (
                row["fiscal_period_end"],
                row["filing_timestamp"],
                row["form_filing_id"],
            )
        )

    events: list[dict[str, Any]] = []
    comparison_count = 0
    for cik in sorted(periods_by_cik):
        rows = periods_by_cik[cik]
        for current in rows:
            current_fiscal = date.fromisoformat(current["fiscal_period_end"])
            current_filing = datetime.fromisoformat(current["filing_timestamp"])
            possible: list[tuple[int, dict[str, Any]]] = []
            for prior in rows:
                prior_fiscal = date.fromisoformat(prior["fiscal_period_end"])
                gap = (current_fiscal - prior_fiscal).days
                if not (
                    PRIOR_FISCAL_PERIOD_MIN_DAYS
                    <= gap
                    <= PRIOR_FISCAL_PERIOD_MAX_DAYS
                ):
                    continue
                if datetime.fromisoformat(prior["filing_timestamp"]) >= current_filing:
                    continue
                possible.append((gap, prior))
            if not possible:
                rejects["missing_prior_fiscal_period_250_500d"] += 1
                continue
            # The most recent valid prior fiscal period is the smallest gap.
            gap_days, prior = sorted(
                possible,
                key=lambda pair: (
                    pair[0],
                    pair[1]["filing_timestamp"],
                    pair[1]["form_filing_id"],
                ),
            )[0]
            comparison_count += 1
            current_partners = tuple(current["engagement_partner_ids"])
            prior_partners = tuple(prior["engagement_partner_ids"])
            if current_partners == prior_partners:
                rejects["partner_set_unchanged"] += 1
                continue
            filing_day = date.fromisoformat(current["filing_date"])
            availability = filing_day + timedelta(
                days=AVAILABILITY_LAG_CALENDAR_DAYS
            )
            iso = filing_day.isocalendar()
            event_id = (
                f"PCAOB_FORM_AP:{cik}:{current['fiscal_period_end']}:"
                f"{current['form_filing_id']}"
            )
            events.append(
                {
                    "event_id": event_id,
                    "issuer_cik": cik,
                    "issuer_name": current.get("issuer_name") or "",
                    "form_filing_id": current["form_filing_id"],
                    "prior_form_filing_id": prior["form_filing_id"],
                    "fiscal_period_end": current["fiscal_period_end"],
                    "prior_fiscal_period_end": prior["fiscal_period_end"],
                    "prior_fiscal_period_gap_days": gap_days,
                    "filing_timestamp": current["filing_timestamp"],
                    "filing_date": current["filing_date"],
                    "availability_date": availability.isoformat(),
                    "signal_date": availability.isoformat(),
                    "iso_filing_week": f"{iso.year}-W{iso.week:02d}",
                    "engagement_partner_ids": list(current_partners),
                    "prior_engagement_partner_ids": list(prior_partners),
                    "partner_change": True,
                    "source_archive_sha256": current.get(
                        "source_archive_sha256"
                    ),
                    "source_archive_member": current.get(
                        "source_archive_member", OFFICIAL_ARCHIVE_MEMBER
                    ),
                    "source_record_sha256": current.get("source_record_sha256"),
                    "prior_source_record_sha256": prior.get(
                        "source_record_sha256"
                    ),
                    "rule_version": RULE_VERSION,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    events.sort(
        key=lambda row: (
            row["signal_date"],
            row["issuer_cik"],
            row["filing_timestamp"],
            row["form_filing_id"],
            row["event_id"],
        )
    )
    issuer_week_first: dict[tuple[str, str], dict[str, Any]] = {}
    issuer_week_duplicate_count = 0
    for event in events:
        key = (event["issuer_cik"], event["iso_filing_week"])
        if key in issuer_week_first:
            issuer_week_duplicate_count += 1
            rejects["later_duplicate_issuer_week_partner_change"] += 1
            continue
        issuer_week_first[key] = event
    events = list(issuer_week_first.values())
    audit = {
        "input_filtered_filing_count": len(raw),
        "unique_cik_fiscal_period_count": len(first_by_cik_period),
        "prior_comparison_count": comparison_count,
        "partner_change_event_count": len(events),
        "partner_change_cik_count": len({row["issuer_cik"] for row in events}),
        "duplicate_issuer_week_partner_change_event_count": (
            issuer_week_duplicate_count
        ),
        "reject_totals": dict(sorted(rejects.items())),
    }
    return events, audit


def _normalise_windows(
    windows: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    if isinstance(windows, Mapping):
        items = windows.items()
    else:
        items = ((str(row.get("name") or ""), row) for row in windows)
    for name, value in items:
        if isinstance(value, Mapping):
            start = _iso_date(value.get("start"))
            end = _iso_date(value.get("end"))
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            start = _iso_date(value[0])
            end = _iso_date(value[1])
        else:
            start = end = None
        if not name or not start or not end or start > end:
            raise ValueError(f"invalid standard window {name!r}: {value!r}")
        output.append({"name": str(name), "start": start, "end": end})
    output.sort(key=lambda row: (row["start"], row["end"], row["name"]))
    return output


def _normalise_bars(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for source in rows or []:
        row = dict(source)
        day = _iso_date(_field(row, "date", "Date"))
        open_price = _finite_float(_field(row, "open", "Open"))
        close = _finite_float(_field(row, "close", "Close"))
        volume = _finite_float(_field(row, "volume", "Volume"))
        high = _finite_float(_field(row, "high", "High"))
        low = _finite_float(_field(row, "low", "Low"))
        if (
            day
            and open_price is not None
            and close is not None
            and volume is not None
            and open_price > 0
            and close > 0
            and volume >= 0
        ):
            output[day] = {
                "date": day,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
    return [output[day] for day in sorted(output)]


def _status_ok(row: Mapping[str, Any], aliases: Sequence[str]) -> bool:
    value = _field(row, *aliases)
    return str(value or "").strip().lower() == "ok"


def resolve_exact_cik_security_universe(
    *,
    security_master: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    standard_windows: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Resolve one exact-CIK share class using all three standard windows."""

    windows = _normalise_windows(standard_windows)
    if len(windows) != 3:
        raise ValueError("PCAOB share-class resolution requires exactly 3 windows")
    bars = {
        str(ticker).strip().upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    rejects: Counter[str] = Counter()
    eligible_by_cik: dict[str, list[dict[str, Any]]] = defaultdict(list)
    input_rows = list(security_master)
    for source in input_rows:
        row = dict(source)
        ticker = str(_field(row, "ticker", "symbol") or "").strip().upper()
        cik = _canonical_cik(_field(row, "cik", "issuer_cik"))
        industry = str(_field(row, "industry", "gics_industry") or "").strip()
        sector = str(_field(row, "sector", "gics_sector") or "").strip()
        if not ticker or not cik:
            rejects["missing_ticker_or_exact_cik"] += 1
            continue
        if not _status_ok(
            row,
            (
                "warehouse_hygiene_status",
                "hygiene_status",
                "warehouse_status",
            ),
        ):
            rejects["warehouse_hygiene_status_not_ok"] += 1
            continue
        if not _status_ok(
            row,
            (
                "all_windows_status",
                "all_windows_full_liquid_status",
                "all_window_status",
            ),
        ):
            rejects["all_windows_status_not_ok"] += 1
            continue
        if not _status_ok(
            row,
            ("sector_status", "sector_mapping_status"),
        ):
            rejects["sector_status_not_ok"] += 1
            continue
        if not industry:
            rejects["missing_industry"] += 1
            continue
        ticker_bars = bars.get(ticker) or []
        window_medians: dict[str, float] = {}
        for window in windows:
            values = [
                bar["close"] * bar["volume"]
                for bar in ticker_bars
                if window["start"] <= bar["date"] <= window["end"]
                and bar["close"] > 0
                and bar["volume"] >= 0
            ]
            if values:
                window_medians[window["name"]] = float(statistics.median(values))
        if len(window_medians) != 3:
            rejects["missing_three_window_median_dollar_volume"] += 1
            continue
        min_median = min(window_medians.values())
        if not math.isfinite(min_median) or min_median <= 0:
            rejects["nonpositive_three_window_min_median_dollar_volume"] += 1
            continue
        eligible_by_cik[cik].append(
            {
                "ticker": ticker,
                "issuer_cik": cik,
                "issuer_name": str(
                    _field(row, "issuer_name", "name", "company_name") or ""
                ).strip(),
                "sector": sector,
                "industry": industry,
                "warehouse_hygiene_status": "ok",
                "all_windows_status": "ok",
                "sector_status": "ok",
                "window_median_dollar_volume": {
                    key: round(value, 6)
                    for key, value in sorted(window_medians.items())
                },
                "three_window_min_median_dollar_volume": round(min_median, 6),
            }
        )

    universe: dict[str, dict[str, Any]] = {}
    share_class_counts: dict[str, int] = {}
    for cik, rows in sorted(eligible_by_cik.items()):
        # Collapse duplicate security-master rows before counting share classes.
        by_ticker: dict[str, dict[str, Any]] = {}
        for row in rows:
            prior = by_ticker.get(row["ticker"])
            if prior is None or row["three_window_min_median_dollar_volume"] > prior[
                "three_window_min_median_dollar_volume"
            ]:
                by_ticker[row["ticker"]] = row
        ranked = sorted(
            by_ticker.values(),
            key=lambda row: (
                -row["three_window_min_median_dollar_volume"],
                row["ticker"],
            ),
        )
        chosen = dict(ranked[0])
        chosen["share_class_candidate_count"] = len(ranked)
        chosen["share_class_selection_rank"] = 1
        chosen["share_class_rule"] = (
            "max_three_window_min_median_dollar_volume_then_ticker"
        )
        universe[cik] = chosen
        share_class_counts[cik] = len(ranked)

    ticker_collisions: dict[str, list[str]] = defaultdict(list)
    for cik, row in universe.items():
        ticker_collisions[row["ticker"]].append(cik)
    for ticker, ciks in ticker_collisions.items():
        if len(ciks) > 1:
            for cik in ciks:
                universe.pop(cik, None)
            rejects["selected_ticker_maps_to_multiple_ciks"] += len(ciks)

    audit = {
        "input_security_master_count": len(input_rows),
        "eligible_share_class_count": sum(len(rows) for rows in eligible_by_cik.values()),
        "resolved_cik_count": len(universe),
        "resolved_ticker_count": len({row["ticker"] for row in universe.values()}),
        "multi_share_class_cik_count": sum(
            count > 1 for count in share_class_counts.values()
        ),
        "share_class_candidate_counts": share_class_counts,
        "standard_windows": windows,
        "reject_totals": dict(sorted(rejects.items())),
    }
    return universe, audit


def _market_dates(
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    explicit: Iterable[Any] | None,
) -> list[str]:
    values = explicit
    if values is None:
        values = ohlcv_by_ticker.get("SPY") or ohlcv_by_ticker.get("spy") or []
    output: set[str] = set()
    for value in values:
        if isinstance(value, Mapping):
            value = _field(value, "date", "Date")
        day = _iso_date(value)
        if day:
            output.add(day)
    return sorted(output)


def _trailing_adv(
    rows: Sequence[Mapping[str, Any]], entry_date: str
) -> tuple[float | None, list[str]]:
    prior = [row for row in rows if row["date"] < entry_date]
    if len(prior) < ADV_LOOKBACK_SESSIONS:
        return None, []
    lookback = prior[-ADV_LOOKBACK_SESSIONS:]
    values = [float(row["close"]) * float(row["volume"]) for row in lookback]
    if len(values) != ADV_LOOKBACK_SESSIONS or any(
        not math.isfinite(value) or value <= 0 for value in values
    ):
        return None, []
    return float(sum(values) / len(values)), [row["date"] for row in lookback]


def build_partner_change_peer_candidates(
    *,
    events: Iterable[Mapping[str, Any]],
    universe_by_cik: Mapping[str, Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: str | None = None,
    end: str | None = None,
    signal_date: str | None = None,
    market_calendar: Iterable[Any] | None = None,
    require_entry_bar: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build daily top-one unaffected-industry-peer candidates."""

    event_rows = [dict(row) for row in events]
    bars = {
        str(ticker).strip().upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    calendar = _market_dates(ohlcv_by_ticker, market_calendar)
    start_iso = _iso_date(start) if start is not None else None
    end_iso = _iso_date(end) if end is not None else None
    signal_iso = _iso_date(signal_date) if signal_date is not None else None
    if start is not None and start_iso is None:
        raise ValueError(f"invalid start: {start!r}")
    if end is not None and end_iso is None:
        raise ValueError(f"invalid end: {end!r}")
    if signal_date is not None and signal_iso is None:
        raise ValueError(f"invalid signal_date: {signal_date!r}")

    changed_ciks_by_week: dict[str, set[str]] = defaultdict(set)
    for row in event_rows:
        changed_ciks_by_week[str(row.get("iso_filing_week") or "")].add(
            str(row.get("issuer_cik") or "")
        )

    universe = {str(cik): dict(row) for cik, row in universe_by_cik.items()}
    rejects: Counter[str] = Counter()
    qualified: list[dict[str, Any]] = []
    target_event_in_scope_count = 0
    for event in sorted(
        event_rows,
        key=lambda row: (
            str(row.get("signal_date") or ""),
            str(row.get("issuer_cik") or ""),
            str(row.get("event_id") or ""),
        ),
    ):
        if signal_iso is not None and event.get("signal_date") != signal_iso:
            continue
        target_cik = str(event.get("issuer_cik") or "")
        target = universe.get(target_cik)
        if target is None:
            rejects["target_exact_cik_not_in_tradable_universe"] += 1
            continue
        availability = _iso_date(event.get("availability_date") or event.get("signal_date"))
        if availability is None:
            rejects["invalid_availability_date"] += 1
            continue
        entry_date = next((day for day in calendar if day > availability), None)
        if entry_date is None:
            rejects["missing_strict_next_market_open"] += 1
            continue
        if (start_iso and entry_date < start_iso) or (
            end_iso and entry_date > end_iso
        ):
            rejects["entry_outside_window"] += 1
            continue
        target_event_in_scope_count += 1
        changed_ciks = changed_ciks_by_week.get(
            str(event.get("iso_filing_week") or ""), set()
        )
        peers: list[dict[str, Any]] = []
        for peer_cik, peer in universe.items():
            if peer_cik == target_cik:
                continue
            if peer_cik in changed_ciks:
                continue
            if str(peer.get("industry") or "") != str(target.get("industry") or ""):
                continue
            ticker = str(peer.get("ticker") or "").upper()
            peer_bars = bars.get(ticker) or []
            adv, adv_dates = _trailing_adv(peer_bars, entry_date)
            if adv is None:
                continue
            index = {row["date"]: idx for idx, row in enumerate(peer_bars)}
            if require_entry_bar and entry_date not in index:
                continue
            peers.append(
                {
                    "peer_cik": peer_cik,
                    "peer_ticker": ticker,
                    "peer_sector": peer.get("sector") or "",
                    "peer_industry": peer.get("industry") or "",
                    "peer_adv_60": adv,
                    "peer_adv_first_date": adv_dates[0],
                    "peer_adv_last_date": adv_dates[-1],
                    "peer_adv_session_count": len(adv_dates),
                    "peer_three_window_min_median_dollar_volume": peer.get(
                        "three_window_min_median_dollar_volume"
                    ),
                    "peer_share_class_candidate_count": int(
                        peer.get("share_class_candidate_count") or 1
                    ),
                    "peer_from_multi_share_class_cik": int(
                        peer.get("share_class_candidate_count") or 1
                    )
                    > 1,
                }
            )
        ranked = sorted(
            peers,
            key=lambda row: (-row["peer_adv_60"], row["peer_ticker"]),
        )
        if len(ranked) < MIN_TRADABLE_INDUSTRY_PEERS:
            rejects["fewer_than_two_tradable_unchanged_industry_peers"] += 1
            continue
        selected = ranked[0]
        candidate_id = f"{SLEEVE_NAME}:{event['event_id']}:{selected['peer_ticker']}"
        qualified.append(
            {
                **event,
                "candidate_id": candidate_id,
                "target_cik": target_cik,
                "target_ticker": target["ticker"],
                "target_sector": target.get("sector") or "",
                "target_industry": target.get("industry") or "",
                "target_three_window_min_median_dollar_volume": target.get(
                    "three_window_min_median_dollar_volume"
                ),
                "target_share_class_candidate_count": int(
                    target.get("share_class_candidate_count") or 1
                ),
                "target_from_multi_share_class_cik": int(
                    target.get("share_class_candidate_count") or 1
                )
                > 1,
                **selected,
                "industry": target.get("industry") or "",
                "entry_date": entry_date,
                "tradable_peer_count": len(ranked),
                "eligible_peer_tickers_by_adv": [
                    row["peer_ticker"] for row in ranked
                ],
                "same_week_changed_ciks_excluded": sorted(
                    changed_ciks - {target_cik}
                ),
                "hold_sessions": HOLD_SESSIONS,
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "rule_version": RULE_VERSION,
                "sleeve": SLEEVE_NAME,
                "trade_enabled": False,
                "alters_orders": False,
                "paper_status": "pending",
            }
        )

    selected_candidates: list[dict[str, Any]] = []
    eligible_by_entry_date: dict[str, int] = {}
    for entry_date, rows in sorted(
        _group_by(qualified, "entry_date").items()
    ):
        ranked = sorted(
            rows,
            key=lambda row: (
                -row["peer_adv_60"],
                row["target_ticker"],
                row["event_id"],
            ),
        )
        eligible_by_entry_date[entry_date] = len(ranked)
        selected_candidates.append({**ranked[0], "daily_rank": 1})
        rejects["daily_top1_limit"] += max(0, len(ranked) - 1)

    audit = {
        "input_partner_change_event_count": len(event_rows),
        "target_event_in_scope_count": target_event_in_scope_count,
        "peer_qualified_event_count": len(qualified),
        "selected_candidate_count": len(selected_candidates),
        "eligible_by_entry_date": eligible_by_entry_date,
        "target_ticker_count": len(
            {row["target_ticker"] for row in selected_candidates}
        ),
        "peer_ticker_count": len(
            {row["peer_ticker"] for row in selected_candidates}
        ),
        "selected_target_from_multi_share_class_cik_count": sum(
            bool(row["target_from_multi_share_class_cik"])
            for row in selected_candidates
        ),
        "selected_peer_from_multi_share_class_cik_count": sum(
            bool(row["peer_from_multi_share_class_cik"])
            for row in selected_candidates
        ),
        "reject_totals": dict(sorted(rejects.items())),
        "production_impact": _production_impact(),
    }
    return selected_candidates, audit


def _group_by(
    rows: Iterable[Mapping[str, Any]], key: str
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        output[str(row[key])].append(dict(row))
    return dict(output)


def _atr_target(
    rows: Sequence[Mapping[str, Any]], entry_idx: int, entry_price: float
) -> float:
    true_ranges: list[float] = []
    end_idx = entry_idx - 1
    for idx in range(max(0, end_idx - 13), end_idx + 1):
        high = _finite_float(rows[idx].get("high"))
        low = _finite_float(rows[idx].get("low"))
        close = _finite_float(rows[idx].get("close"))
        if high is None or low is None or close is None:
            continue
        previous_close = (
            _finite_float(rows[idx - 1].get("close")) if idx > 0 else close
        )
        if previous_close is None:
            continue
        true_ranges.append(
            max(high - low, abs(high - previous_close), abs(low - previous_close))
        )
    atr = sum(true_ranges) / len(true_ranges) if true_ranges else entry_price * 0.02
    return round(entry_price + 3.5 * atr, 4)


def _top_share(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    counts = Counter(str(row.get(key) or "") for row in rows)
    return round(max(counts.values()) / len(rows), 6)


def replay_partner_change_peer_substitution(
    *,
    events: Iterable[Mapping[str, Any]],
    universe_by_cik: Mapping[str, Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: str,
    end: str,
    market_calendar: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Replay one window with entry-open and inclusive session-20 close."""

    start_iso, end_iso = _iso_date(start), _iso_date(end)
    if not start_iso or not end_iso or start_iso > end_iso:
        raise ValueError(f"invalid replay window: {start!r}, {end!r}")
    bars = {
        str(ticker).strip().upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    candidates, candidate_audit = build_partner_change_peer_candidates(
        events=events,
        universe_by_cik=universe_by_cik,
        ohlcv_by_ticker=ohlcv_by_ticker,
        start=start_iso,
        end=end_iso,
        market_calendar=market_calendar,
        require_entry_bar=True,
    )
    rejects: Counter[str] = Counter(candidate_audit["reject_totals"])
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    for candidate in candidates:
        rows = bars.get(candidate["peer_ticker"]) or []
        index = {row["date"]: idx for idx, row in enumerate(rows)}
        entry_idx = index.get(candidate["entry_date"])
        if entry_idx is None:
            rejects["missing_peer_entry_bar"] += 1
            unsettled.append(
                {**candidate, "unsettled_reason": "missing_peer_entry_bar"}
            )
            continue
        exit_idx = entry_idx + HOLD_SESSIONS - 1
        if exit_idx >= len(rows) or rows[exit_idx]["date"] > end_iso:
            rejects["incomplete_20_session_horizon"] += 1
            unsettled.append(
                {
                    **candidate,
                    "unsettled_reason": "incomplete_20_session_horizon",
                }
            )
            continue
        entry_price = float(rows[entry_idx]["open"])
        exit_price = float(rows[exit_idx]["close"])
        net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        trades.append(
            {
                **candidate,
                # Signal-contract ticker is the actually purchased peer.
                "ticker": candidate["peer_ticker"],
                "entry_price": round(entry_price, 6),
                "exit_date": rows[exit_idx]["date"],
                "exit_price": round(exit_price, 6),
                "target_price": _atr_target(rows, entry_idx, entry_price),
                "target_price_semantics": "sentinel_only_not_exit_driver",
                "target_price_is_exit_driver": False,
                "target_price_lookback_end_date": (
                    rows[entry_idx - 1]["date"] if entry_idx > 0 else None
                ),
                "hold_sessions_realized": HOLD_SESSIONS,
                "exit_reason": "scheduled_session20_close",
                "net_return": round(net_return, 10),
                "pnl_pct_net": round(net_return, 10),
                "pnl": round(BASE_NOTIONAL_USD * net_return, 2),
                "paper_status": "closed",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    selected_count = len(candidates)
    generated = int(candidate_audit["target_event_in_scope_count"])
    coverage = {
        **candidate_audit,
        "settled_trade_count": len(trades),
        "unsettled_candidate_count": len(unsettled),
        "target_ticker_count": len({row["target_ticker"] for row in trades}),
        "peer_ticker_count": len({row["peer_ticker"] for row in trades}),
        "target_top1_share": _top_share(trades, "target_ticker"),
        "peer_top1_share": _top_share(trades, "peer_ticker"),
        "issuer_week_count": len(
            {(row["target_cik"], row["iso_filing_week"]) for row in trades}
        ),
        "signals_generated": generated,
        "signals_survived": selected_count,
        "survival_rate": round(selected_count / generated, 6) if generated else 0.0,
        "reject_totals": dict(sorted(rejects.items())),
    }
    return {
        "schema": "pcaob_form_ap_partner_change_peer_replay_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "window": {"start": start_iso, "end": end_iso},
        "selected_candidates": candidates,
        "trades": trades,
        "unsettled": unsettled,
        "coverage_audit": coverage,
        "signals_generated": generated,
        "signals_survived": selected_count,
        "survival_rate": coverage["survival_rate"],
        "trade_enabled": False,
        "orders": [],
        "production_impact": _production_impact(),
    }


def build_pcaob_form_ap_partner_change_peer_substitution_historical(
    *,
    source_zip_path: str | Path,
    expected_sha256: str,
    security_master: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    standard_windows: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    market_calendar: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Build all three standard historical windows from one verified source."""

    windows = _normalise_windows(standard_windows)
    if len(windows) != 3:
        raise ValueError("historical PCAOB build requires exactly 3 standard windows")
    filings, source_provenance = load_hash_bound_pcaob_form_ap_filings(
        source_zip_path, expected_sha256=expected_sha256
    )
    events, event_audit = extract_partner_change_events(filings)
    universe, universe_audit = resolve_exact_cik_security_universe(
        security_master=security_master,
        ohlcv_by_ticker=ohlcv_by_ticker,
        standard_windows=windows,
    )
    replay_by_window: dict[str, dict[str, Any]] = {}
    for window in windows:
        replay_by_window[window["name"]] = replay_partner_change_peer_substitution(
            events=events,
            universe_by_cik=universe,
            ohlcv_by_ticker=ohlcv_by_ticker,
            start=window["start"],
            end=window["end"],
            market_calendar=market_calendar,
        )
    settled = [
        trade
        for replay in replay_by_window.values()
        for trade in replay["trades"]
    ]
    return {
        "schema": "pcaob_form_ap_partner_change_peer_historical_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "orders": [],
        "policy": policy_provenance(),
        "source_provenance": source_provenance,
        "event_audit": event_audit,
        "universe_audit": universe_audit,
        "event_count": len(events),
        "events_sha256": _sha(events),
        "resolved_universe_sha256": _sha(universe),
        "windows": replay_by_window,
        "aggregate_coverage_audit": {
            "settled_trade_count": len(settled),
            "target_ticker_count": len({row["target_ticker"] for row in settled}),
            "peer_ticker_count": len({row["peer_ticker"] for row in settled}),
            "target_top1_share": _top_share(settled, "target_ticker"),
            "peer_top1_share": _top_share(settled, "peer_ticker"),
            "target_from_multi_share_class_cik_count": sum(
                bool(row["target_from_multi_share_class_cik"])
                for row in settled
            ),
            "selected_peer_from_multi_share_class_cik_count": sum(
                bool(row["peer_from_multi_share_class_cik"])
                for row in settled
            ),
            "window_settled_trade_counts": {
                name: len(replay["trades"])
                for name, replay in replay_by_window.items()
            },
        },
        "production_impact": _production_impact(),
    }


def build_pcaob_form_ap_partner_change_peer_substitution_paper_snapshot(
    *,
    source_zip_path: str | Path,
    expected_sha256: str,
    security_master: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    standard_windows: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    as_of_date: str,
    market_calendar: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Build the daily default-off candidate snapshot without outcome reads."""

    as_of = _iso_date(as_of_date)
    if not as_of:
        raise ValueError(f"invalid as_of_date: {as_of_date!r}")
    filings, source_provenance = load_hash_bound_pcaob_form_ap_filings(
        source_zip_path, expected_sha256=expected_sha256
    )
    events, event_audit = extract_partner_change_events(filings)
    universe, universe_audit = resolve_exact_cik_security_universe(
        security_master=security_master,
        ohlcv_by_ticker=ohlcv_by_ticker,
        standard_windows=standard_windows,
    )
    candidates, candidate_audit = build_partner_change_peer_candidates(
        events=events,
        universe_by_cik=universe,
        ohlcv_by_ticker=ohlcv_by_ticker,
        signal_date=as_of,
        market_calendar=market_calendar,
        require_entry_bar=False,
    )
    return {
        "schema": "pcaob_form_ap_partner_change_peer_default_off_snapshot_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": len(candidates),
        "pending_count": len(candidates),
        "candidates": candidates,
        "pending_entries": candidates,
        "orders": [],
        "source_provenance": source_provenance,
        "event_audit": event_audit,
        "universe_audit": universe_audit,
        "coverage_audit": candidate_audit,
        "policy": policy_provenance(),
        "production_impact": _production_impact(),
    }


__all__ = [
    "ADV_LOOKBACK_SESSIONS",
    "AVAILABILITY_LAG_CALENDAR_DAYS",
    "BASE_NOTIONAL_USD",
    "HOLD_SESSIONS",
    "MIN_TRADABLE_INDUSTRY_PEERS",
    "OFFICIAL_ARCHIVE_MEMBER",
    "OFFICIAL_AUDIT_REPORT_TYPE",
    "PRIOR_FISCAL_PERIOD_MAX_DAYS",
    "PRIOR_FISCAL_PERIOD_MIN_DAYS",
    "ROUND_TRIP_COST_PCT",
    "RULE_VERSION",
    "SLEEVE_NAME",
    "TRADE_ENABLED",
    "build_partner_change_peer_candidates",
    "build_pcaob_form_ap_partner_change_peer_substitution_historical",
    "build_pcaob_form_ap_partner_change_peer_substitution_paper_snapshot",
    "extract_partner_change_events",
    "load_hash_bound_pcaob_form_ap_filings",
    "policy_provenance",
    "replay_partner_change_peer_substitution",
    "resolve_exact_cik_security_universe",
]
