"""Shared default-off Federal Reserve H.8 bank-size pair helper.

The helper is intentionally pure.  Historical replay and the daily observer
both supply hash-bound official H.8 archive HTML plus a regular-session
calendar, and receive the same canonical releases and weekly KRE/KBE pair
decisions.  It performs no network access, persistence, price lookup, or order
submission.

Only seasonally adjusted Table 6 (large domestically chartered banks) and
Table 8 (small domestically chartered banks) are accepted.  Each release uses
the rightmost reported value for line 36, ``Other deposits``, and line 10,
``Commercial and industrial loans``.  Missing, duplicated, non-positive, or
schema-inconsistent inputs fail closed.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse


SLEEVE_NAME = "FED_H8_BANK_SIZE_RELATIVE_VALUE_PAPER"
RULE_VERSION = "fed_h8_large_small_deposit_ci_lag4_kre_kbe_v1"
SOURCE_NAME = "federal_reserve_h8_dated_archive_html"
H8_RELEASE_SCHEMA_VERSION = "fed_h8_release_v1"
H8_SIGNAL_SCHEMA_VERSION = "fed_h8_bank_size_signal_v1"
H8_DECISION_SCHEMA_VERSION = "fed_h8_bank_size_pair_decision_v1"

TRADE_ENABLED = False
LAG_RELEASES = 4
NOTIONAL_USD_PER_LEG = 4_000.0
NOTIONAL_USD = NOTIONAL_USD_PER_LEG
ROUND_TRIP_COST_PCT_PER_LEG = 0.0035
ROUND_TRIP_COST_PCT = ROUND_TRIP_COST_PCT_PER_LEG
MAX_CONCURRENT_PAIRS = 1

KRE_TICKER = "KRE"
KBE_TICKER = "KBE"
TICKERS = (KRE_TICKER, KBE_TICKER)
POSITIVE_SIGNAL_LONG_TICKER = KRE_TICKER
POSITIVE_SIGNAL_SHORT_TICKER = KBE_TICKER

LARGE_BANK_KEY = "large"
SMALL_BANK_KEY = "small"
OTHER_DEPOSITS_KEY = "other_deposits"
COMMERCIAL_INDUSTRIAL_LOANS_KEY = "commercial_and_industrial_loans"
FIELD_KEYS = (OTHER_DEPOSITS_KEY, COMMERCIAL_INDUSTRIAL_LOANS_KEY)

TABLE_SPECS: dict[str, dict[str, Any]] = {
    LARGE_BANK_KEY: {
        "table_number": 6,
        "title_fragment": "large domestically chartered commercial banks",
    },
    SMALL_BANK_KEY: {
        "table_number": 8,
        "title_fragment": "small domestically chartered commercial banks",
    },
}

FIELD_SPECS: dict[str, dict[str, Any]] = {
    OTHER_DEPOSITS_KEY: {
        "line_number": 36,
        "label": "Other deposits",
    },
    COMMERCIAL_INDUSTRIAL_LOANS_KEY: {
        "line_number": 10,
        "label": "Commercial and industrial loans",
    },
}

# H.8 is weekly.  Holiday shifts can move a release by a day or two, while a
# gap wider than this means the list is not a complete release sequence and
# index i-4 would not be the locked four-release lag.
MIN_RELEASE_GAP_DAYS = 4
MAX_RELEASE_GAP_DAYS = 10
MIN_LAG4_SPAN_DAYS = 21
MAX_LAG4_SPAN_DAYS = 35

_MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|"
    r"October|November|December"
)
_RELEASE_DATE_RE = re.compile(
    rf"\brelease\s+date\s*:?\s*((?:{_MONTH_PATTERN})\s+\d{{1,2}},\s+\d{{4}})",
    re.IGNORECASE,
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class H8SchemaError(ValueError):
    """Raised when an H.8 release cannot satisfy the locked PIT contract."""


def _normalise_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _normalise_label(value: Any) -> str:
    text = _normalise_text(value).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _iso_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    text = _normalise_text(value).replace(",", "").replace("−", "-")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


class _H8HTMLCollector(HTMLParser):
    """Collect headings and table rows without depending on third-party HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page_text: list[str] = []
        self.tables: list[dict[str, Any]] = []
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._last_heading = ""
        self._table: dict[str, Any] | None = None
        self._caption_depth = 0
        self._caption_parts: list[str] = []
        self._between_heading_parts: list[str] = []
        self._row: list[dict[str, Any]] | None = None
        self._cell_tag: str | None = None
        self._cell_parts: list[str] = []
        self._cell_attrs: dict[str, str] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        attributes = {str(key).lower(): value or "" for key, value in attrs}
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_tag = tag
            self._heading_parts = []
        if tag == "table":
            if self._table is not None:
                raise H8SchemaError("nested_html_table")
            self._table = {
                "heading": self._last_heading,
                "local_context": _normalise_text(
                    "".join(self._between_heading_parts)
                ),
                "id": _normalise_text(attributes.get("id")),
                "title": _normalise_text(attributes.get("title")),
                "summary": _normalise_text(
                    attributes.get("summary") or attributes.get("aria-label")
                ),
                "caption": "",
                "rows": [],
            }
            self._between_heading_parts = []
        elif tag == "caption" and self._table is not None:
            self._caption_depth += 1
            self._caption_parts = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell_tag = tag
            self._cell_parts = []
            self._cell_attrs = attributes
        elif tag == "br":
            if self._cell_tag is not None:
                self._cell_parts.append(" ")
            if self._heading_tag is not None:
                self._heading_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"th", "td"} and self._cell_tag == tag and self._row is not None:
            self._row.append(
                {
                    "tag": tag,
                    "text": _normalise_text("".join(self._cell_parts)),
                    "attrs": dict(self._cell_attrs),
                }
            )
            self._cell_tag = None
            self._cell_parts = []
            self._cell_attrs = {}
        elif tag == "tr" and self._table is not None:
            if self._row:
                self._table["rows"].append(self._row)
            self._row = None
        elif tag == "caption" and self._table is not None and self._caption_depth:
            self._caption_depth -= 1
            self._table["caption"] = _normalise_text("".join(self._caption_parts))
            self._caption_parts = []
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        elif tag == self._heading_tag:
            self._last_heading = _normalise_text("".join(self._heading_parts))
            self._between_heading_parts = []
            self._heading_tag = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        self.page_text.append(data)
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._caption_depth:
            self._caption_parts.append(data)
        if self._cell_tag is not None:
            self._cell_parts.append(data)
        if (
            self._last_heading
            and self._heading_tag is None
            and self._table is None
        ):
            self._between_heading_parts.append(data)


def _decode_and_verify_html(html_text: str | bytes, source_sha256: Any) -> str:
    supplied_hash = str(source_sha256 or "").strip().lower()
    if not _SHA256_RE.fullmatch(supplied_hash):
        raise H8SchemaError("invalid_source_sha256")
    if isinstance(html_text, bytes):
        raw = bytes(html_text)
        try:
            decoded = raw.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise H8SchemaError("html_not_utf8") from exc
    elif isinstance(html_text, str):
        decoded = html_text
        raw = decoded.encode("utf-8")
    else:
        raise H8SchemaError("html_text_must_be_str_or_bytes")
    if not decoded.strip():
        raise H8SchemaError("empty_html")
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != supplied_hash:
        raise H8SchemaError("source_sha256_mismatch")
    return decoded


def _validate_source_url(source_url: Any, release_date: str) -> str:
    url = str(source_url or "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or not (
        host == "federalreserve.gov" or host.endswith(".federalreserve.gov")
    ):
        raise H8SchemaError("non_official_h8_source_url")
    date_token = release_date.replace("-", "")
    path = parsed.path.lower()
    if not re.search(rf"/releases/h8/{date_token}(?:/|$)", path):
        raise H8SchemaError("source_url_release_date_mismatch")
    return url


def _validate_page_release_date(page_text: str, release_date: str) -> None:
    parsed_dates: set[str] = set()
    for match in _RELEASE_DATE_RE.findall(page_text):
        try:
            parsed_dates.add(datetime.strptime(match, "%B %d, %Y").date().isoformat())
        except ValueError:
            continue
    if not parsed_dates:
        raise H8SchemaError("missing_official_release_date_marker")
    if parsed_dates != {release_date}:
        raise H8SchemaError("html_release_date_mismatch")


def _table_identity(table: Mapping[str, Any]) -> str:
    return _normalise_text(
        " ".join(
            str(table.get(key) or "")
            for key in ("heading", "title", "caption", "summary")
        )
    )


def _table_body_text(table: Mapping[str, Any]) -> str:
    rows = table.get("rows") or []
    return _normalise_text(
        " ".join(
            str(cell.get("text") or "")
            for row in rows
            for cell in row
            if isinstance(cell, Mapping)
        )
    )


def _select_table(
    tables: Sequence[Mapping[str, Any]], bank_size: str
) -> Mapping[str, Any]:
    spec = TABLE_SPECS[bank_size]
    number = int(spec["table_number"])
    title_fragment = str(spec["title_fragment"])
    matches: list[Mapping[str, Any]] = []
    for table in tables:
        heading = _normalise_label(table.get("heading"))
        title = _normalise_label(table.get("title"))
        if (
            re.search(rf"\btable\s+{number}\b", heading)
            and title_fragment in heading
            and re.search(rf"\btable\s+{number}\b", title)
            and title_fragment in title
            and str(table.get("id") or "").strip().lower() == f"h8t{number}"
        ):
            matches.append(table)
    if len(matches) != 1:
        raise H8SchemaError(f"expected_one_table_{number}_found_{len(matches)}")
    table = matches[0]
    # Fed places ``span.tableunit`` immediately before the nested table inside
    # the matching ``div.data-table``.  ``local_context`` is only text observed
    # after this table's h4 and before this exact table starts; it cannot borrow
    # the identical units phrase from Table 7/8/9 elsewhere on the page.
    units_context = _normalise_label(
        f"{table.get('local_context') or ''} {_table_body_text(table)}"
    )
    if (
        "seasonally adjusted" not in units_context
        or "billions of dollars" not in units_context
    ):
        raise H8SchemaError(f"table_{number}_units_or_adjustment_mismatch")
    week_ending_spans: list[int] = []
    for row in table.get("rows") or []:
        for cell in row:
            if not isinstance(cell, Mapping) or cell.get("tag") != "th":
                continue
            if _normalise_label(cell.get("text")) != "week ending":
                continue
            attrs = cell.get("attrs")
            raw_span = attrs.get("colspan") if isinstance(attrs, Mapping) else None
            try:
                week_ending_spans.append(int(raw_span))
            except (TypeError, ValueError):
                week_ending_spans.append(1)
    if 4 not in week_ending_spans:
        raise H8SchemaError(f"table_{number}_missing_four_week_ending_block")
    return table


def _extract_latest_field(
    table: Mapping[str, Any], field_key: str
) -> dict[str, Any]:
    spec = FIELD_SPECS[field_key]
    expected_line = int(spec["line_number"])
    expected_label = _normalise_label(spec["label"])
    matching_rows: list[tuple[list[Mapping[str, Any]], int]] = []
    for raw_row in table.get("rows") or []:
        row = [cell for cell in raw_row if isinstance(cell, Mapping)]
        texts = [_normalise_text(cell.get("text")) for cell in row]
        labels = [_normalise_label(text) for text in texts]
        label_indexes = [
            index for index, label in enumerate(labels) if expected_label in label
        ]
        if not label_indexes:
            continue
        label_index = label_indexes[0]
        prefix = " ".join(texts[: label_index + 1])
        if not re.search(rf"(^|\D){expected_line}(\D|$)", prefix):
            continue
        matching_rows.append((row, label_index))
    if len(matching_rows) != 1:
        raise H8SchemaError(
            f"expected_one_{field_key}_row_found_{len(matching_rows)}"
        )
    row, label_index = matching_rows[0]
    value_cells = row[label_index + 1 :]
    if len(value_cells) < 4:
        raise H8SchemaError(f"insufficient_terminal_weekly_cells_for_{field_key}")
    terminal_weekly_values = [
        _finite_float(cell.get("text")) for cell in value_cells[-4:]
    ]
    if any(number is None for number in terminal_weekly_values):
        raise H8SchemaError(f"non_numeric_terminal_weekly_value_for_{field_key}")
    weekly_values = [float(number) for number in terminal_weekly_values if number is not None]
    if len(weekly_values) != 4 or any(number <= 0 for number in weekly_values):
        raise H8SchemaError(f"invalid_terminal_weekly_values_for_{field_key}")
    numeric_values = [
        number
        for number in (
            _finite_float(cell.get("text")) for cell in value_cells
        )
        if number is not None
    ]
    if not numeric_values:
        raise H8SchemaError(f"missing_numeric_values_for_{field_key}")
    latest = weekly_values[-1]
    return {
        "line_number": expected_line,
        "label": str(spec["label"]),
        "latest_value": latest,
        "reported_numeric_value_count": len(numeric_values),
        "reported_value_count": len(numeric_values),
        "weekly_value_count": len(weekly_values),
        "weekly_values": weekly_values,
        "latest_value_selection": "rightmost_of_four_terminal_weekly_numeric_cells",
    }


def parse_h8_release_html(
    html_text: str | bytes,
    release_date: Any,
    source_url: Any,
    source_sha256: Any,
) -> dict[str, Any]:
    """Parse one hash-bound official dated H.8 HTML release.

    The caller must pass the official publication date, a dated Federal
    Reserve archive URL containing that date, and the SHA-256 of the exact
    input bytes (or UTF-8 encoding when ``html_text`` is a string).
    """

    release_iso = _iso_date(release_date)
    if release_iso is None:
        raise H8SchemaError("invalid_release_date")
    html = _decode_and_verify_html(html_text, source_sha256)
    url = _validate_source_url(source_url, release_iso)
    collector = _H8HTMLCollector()
    try:
        collector.feed(html)
        collector.close()
    except H8SchemaError:
        raise
    except Exception as exc:  # pragma: no cover - HTMLParser is very defensive
        raise H8SchemaError("malformed_html") from exc
    page_text = _normalise_text(" ".join(collector.page_text))
    page_label = _normalise_label(page_text)
    if "h 8" not in page_label or (
        "assets and liabilities of commercial banks" not in page_label
    ):
        raise H8SchemaError("missing_h8_page_identity")
    _validate_page_release_date(page_text, release_iso)

    tables: dict[str, dict[str, Any]] = {}
    latest_values: dict[str, dict[str, float]] = {}
    for bank_size in (LARGE_BANK_KEY, SMALL_BANK_KEY):
        selected = _select_table(collector.tables, bank_size)
        fields = {
            field_key: _extract_latest_field(selected, field_key)
            for field_key in FIELD_KEYS
        }
        tables[bank_size] = {
            "table_number": int(TABLE_SPECS[bank_size]["table_number"]),
            "table_id": str(selected.get("id") or ""),
            "title": _table_identity(selected),
            "units": "billions_usd_seasonally_adjusted",
            "fields": fields,
        }
        latest_values[bank_size] = {
            field_key: float(fields[field_key]["latest_value"])
            for field_key in FIELD_KEYS
        }

    return {
        "schema_version": H8_RELEASE_SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "release_date": release_iso,
        "publication_date": release_iso,
        "availability_semantics": "official_release_date_after_close_next_open",
        "source_url": url,
        "source_sha256": str(source_sha256).strip().lower(),
        "latest_value_selection": "rightmost_numeric_cell_per_release_table",
        "latest_values": latest_values,
        "tables": tables,
        "rule_version": RULE_VERSION,
        "trade_enabled": TRADE_ENABLED,
    }


def _validated_release_values(
    release: Mapping[str, Any], *, role: str
) -> tuple[str, dict[str, dict[str, float]]]:
    if not isinstance(release, Mapping):
        raise H8SchemaError(f"{role}_release_not_mapping")
    if release.get("schema_version") != H8_RELEASE_SCHEMA_VERSION:
        raise H8SchemaError(f"{role}_release_schema_mismatch")
    if release.get("source") != SOURCE_NAME:
        raise H8SchemaError(f"{role}_release_source_mismatch")
    release_date = _iso_date(release.get("release_date"))
    if release_date is None:
        raise H8SchemaError(f"{role}_release_date_invalid")
    _validate_source_url(release.get("source_url"), release_date)
    source_hash = str(release.get("source_sha256") or "").strip().lower()
    if not _SHA256_RE.fullmatch(source_hash):
        raise H8SchemaError(f"{role}_release_sha256_invalid")
    if release.get("trade_enabled") is not False:
        raise H8SchemaError(f"{role}_release_not_default_off")
    raw_values = release.get("latest_values")
    if not isinstance(raw_values, Mapping):
        raise H8SchemaError(f"{role}_release_latest_values_missing")
    values: dict[str, dict[str, float]] = {}
    for bank_size in (LARGE_BANK_KEY, SMALL_BANK_KEY):
        bank_values = raw_values.get(bank_size)
        if not isinstance(bank_values, Mapping):
            raise H8SchemaError(f"{role}_{bank_size}_values_missing")
        values[bank_size] = {}
        for field_key in FIELD_KEYS:
            value = _finite_float(bank_values.get(field_key))
            if value is None or value <= 0:
                raise H8SchemaError(f"{role}_{bank_size}_{field_key}_invalid")
            values[bank_size][field_key] = value
    return release_date, values


def compute_h8_signal(
    current_release: Mapping[str, Any],
    lag4_release: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute the locked small-minus-large four-release growth signal."""

    current_date, current = _validated_release_values(
        current_release, role="current"
    )
    lag_date, lagged = _validated_release_values(lag4_release, role="lag4")
    span_days = (date.fromisoformat(current_date) - date.fromisoformat(lag_date)).days
    if not MIN_LAG4_SPAN_DAYS <= span_days <= MAX_LAG4_SPAN_DAYS:
        raise H8SchemaError("lag4_release_span_invalid")

    components: dict[str, dict[str, float]] = {}
    signal = 0.0
    for field_key in FIELD_KEYS:
        small_growth = math.log(
            current[SMALL_BANK_KEY][field_key]
            / lagged[SMALL_BANK_KEY][field_key]
        )
        large_growth = math.log(
            current[LARGE_BANK_KEY][field_key]
            / lagged[LARGE_BANK_KEY][field_key]
        )
        spread = small_growth - large_growth
        components[field_key] = {
            "small_log_growth": small_growth,
            "large_log_growth": large_growth,
            "small_minus_large_log_growth": spread,
        }
        signal += spread

    if signal > 0:
        direction = "long_kre_short_kbe"
        long_ticker = KRE_TICKER
        short_ticker = KBE_TICKER
    elif signal < 0:
        direction = "long_kbe_short_kre"
        long_ticker = KBE_TICKER
        short_ticker = KRE_TICKER
    else:
        direction = "flat_exact_zero"
        long_ticker = None
        short_ticker = None

    return {
        "schema_version": H8_SIGNAL_SCHEMA_VERSION,
        "current_release_date": current_date,
        "lag4_release_date": lag_date,
        "lag_releases": LAG_RELEASES,
        "lag_span_days": span_days,
        "formula": (
            "sum_field[log(small_i/small_i_minus_4)-"
            "log(large_i/large_i_minus_4)]"
        ),
        "components": components,
        "signal": signal,
        "direction": direction,
        "long_ticker": long_ticker,
        "short_ticker": short_ticker,
        "active_pair": long_ticker is not None,
        "rule_version": RULE_VERSION,
        "trade_enabled": TRADE_ENABLED,
    }


def _normalise_trading_sessions(values: Iterable[Any]) -> list[str]:
    sessions: set[str] = set()
    for raw in values or []:
        value = raw
        if isinstance(raw, Mapping):
            if raw.get("is_regular_session") is False:
                continue
            session_type = str(raw.get("session_type") or "").strip().lower()
            if session_type and session_type not in {"regular", "regular_session"}:
                continue
            value = raw.get("date") or raw.get("session_date")
        day = _iso_date(value)
        if day is None:
            raise H8SchemaError("invalid_trading_session_date")
        if date.fromisoformat(day).weekday() >= 5:
            raise H8SchemaError("weekend_cannot_be_regular_session")
        sessions.add(day)
    return sorted(sessions)


def _next_session(day: str, sessions: Sequence[str]) -> str | None:
    return next((candidate for candidate in sessions if candidate > day), None)


def _validate_complete_weekly_sequence(release_dates: Sequence[str]) -> None:
    for previous, current in zip(release_dates, release_dates[1:]):
        gap = (date.fromisoformat(current) - date.fromisoformat(previous)).days
        if not MIN_RELEASE_GAP_DAYS <= gap <= MAX_RELEASE_GAP_DAYS:
            raise H8SchemaError(
                f"non_contiguous_weekly_release_sequence:{previous}:{current}:{gap}"
            )


def _pair_legs(long_ticker: str | None, short_ticker: str | None) -> list[dict[str, Any]]:
    if long_ticker is None or short_ticker is None:
        return []
    cost_usd = NOTIONAL_USD_PER_LEG * ROUND_TRIP_COST_PCT_PER_LEG
    return [
        {
            "ticker": long_ticker,
            "side": "long",
            "paper_notional_usd": NOTIONAL_USD_PER_LEG,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT_PER_LEG,
            "round_trip_cost_usd": cost_usd,
            "trade_enabled": TRADE_ENABLED,
        },
        {
            "ticker": short_ticker,
            "side": "short",
            "paper_notional_usd": NOTIONAL_USD_PER_LEG,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT_PER_LEG,
            "round_trip_cost_usd": cost_usd,
            "trade_enabled": TRADE_ENABLED,
        },
    ]


def build_weekly_pair_decisions(
    releases: Iterable[Mapping[str, Any]],
    trading_sessions: Iterable[Any],
) -> list[dict[str, Any]]:
    """Build lag-4 weekly decisions with strict post-publication open timing.

    A complete contiguous weekly release sequence is mandatory.  The first
    four releases are lag anchors.  A decision enters at the first regular
    session strictly after release ``i`` and exits/rebalances at the first
    regular session strictly after release ``i+1``.  The newest decision may
    remain pending or open until the next release/session becomes observable.
    """

    canonical: list[tuple[str, Mapping[str, Any]]] = []
    seen_dates: set[str] = set()
    for raw in releases:
        release_date, _ = _validated_release_values(raw, role="sequence")
        if release_date in seen_dates:
            raise H8SchemaError(f"duplicate_release_date:{release_date}")
        seen_dates.add(release_date)
        canonical.append((release_date, raw))
    canonical.sort(key=lambda item: item[0])
    release_dates = [item[0] for item in canonical]
    _validate_complete_weekly_sequence(release_dates)
    sessions = _normalise_trading_sessions(trading_sessions)

    decisions: list[dict[str, Any]] = []
    for index in range(LAG_RELEASES, len(canonical)):
        release_date, current = canonical[index]
        lag_date, lagged = canonical[index - LAG_RELEASES]
        signal = compute_h8_signal(current, lagged)
        next_release_date = (
            canonical[index + 1][0] if index + 1 < len(canonical) else None
        )
        entry_date = _next_session(release_date, sessions)
        exit_date = (
            _next_session(next_release_date, sessions)
            if next_release_date is not None
            else None
        )
        active_pair = bool(signal["active_pair"])
        if not active_pair:
            status = "no_pair_exact_zero_signal"
        elif entry_date is None:
            status = "pending_entry_session"
        elif next_release_date is None:
            status = "open_awaiting_next_release"
        elif exit_date is None:
            status = "open_awaiting_exit_session"
        else:
            status = "settled"
        legs = _pair_legs(signal["long_ticker"], signal["short_ticker"])
        decisions.append(
            {
                "schema_version": H8_DECISION_SCHEMA_VERSION,
                "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{release_date}",
                "signal_date": release_date,
                "release_date": release_date,
                "publication_date": release_date,
                "lag4_release_date": lag_date,
                "lag_releases": LAG_RELEASES,
                "next_release_date": next_release_date,
                "entry_date": entry_date,
                "entry_semantics": "first_regular_session_open_strictly_after_release",
                "exit_date": exit_date,
                "exit_semantics": (
                    "first_regular_session_open_strictly_after_next_release"
                ),
                "status": status,
                "signal": float(signal["signal"]),
                "signal_components": signal["components"],
                "direction": signal["direction"],
                "long_ticker": signal["long_ticker"],
                "short_ticker": signal["short_ticker"],
                "legs": legs,
                "paper_notional_usd_per_leg": NOTIONAL_USD_PER_LEG,
                "gross_paper_notional_usd": (
                    2.0 * NOTIONAL_USD_PER_LEG if active_pair else 0.0
                ),
                "net_paper_notional_usd": 0.0,
                "round_trip_cost_pct_per_leg": ROUND_TRIP_COST_PCT_PER_LEG,
                "round_trip_cost_usd_pair": sum(
                    float(leg["round_trip_cost_usd"]) for leg in legs
                ),
                "max_concurrent_pairs": MAX_CONCURRENT_PAIRS,
                "target_price": None,
                "target_price_role": "not_applicable_next_release_open_rebalance",
                "current_source_url": current["source_url"],
                "current_source_sha256": current["source_sha256"],
                "lag4_source_url": lagged["source_url"],
                "lag4_source_sha256": lagged["source_sha256"],
                "rule_version": RULE_VERSION,
                "trade_enabled": TRADE_ENABLED,
            }
        )

    # Adjacent active decisions must share one rebalance open, proving the
    # single-pair policy cannot overlap when a next-release session is known.
    for previous, current in zip(decisions, decisions[1:]):
        if previous["exit_date"] is not None and current["entry_date"] is not None:
            if previous["exit_date"] != current["entry_date"]:
                raise H8SchemaError("pair_rebalance_session_discontinuity")
    return decisions


__all__ = [
    "COMMERCIAL_INDUSTRIAL_LOANS_KEY",
    "FIELD_KEYS",
    "FIELD_SPECS",
    "H8_DECISION_SCHEMA_VERSION",
    "H8_RELEASE_SCHEMA_VERSION",
    "H8_SIGNAL_SCHEMA_VERSION",
    "H8SchemaError",
    "KBE_TICKER",
    "KRE_TICKER",
    "LAG_RELEASES",
    "LARGE_BANK_KEY",
    "MAX_CONCURRENT_PAIRS",
    "NOTIONAL_USD",
    "NOTIONAL_USD_PER_LEG",
    "OTHER_DEPOSITS_KEY",
    "POSITIVE_SIGNAL_LONG_TICKER",
    "POSITIVE_SIGNAL_SHORT_TICKER",
    "ROUND_TRIP_COST_PCT",
    "ROUND_TRIP_COST_PCT_PER_LEG",
    "RULE_VERSION",
    "SLEEVE_NAME",
    "SMALL_BANK_KEY",
    "SOURCE_NAME",
    "TABLE_SPECS",
    "TICKERS",
    "TRADE_ENABLED",
    "build_weekly_pair_decisions",
    "compute_h8_signal",
    "parse_h8_release_html",
]
