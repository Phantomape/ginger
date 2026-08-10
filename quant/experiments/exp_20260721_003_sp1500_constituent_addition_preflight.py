"""Outcome-blind S&P Composite 1500 constituent-addition preflight.

This runner reads injected local release tables, warehouse session dates, and
closes *strictly before* each supplied manifest date.  It never reads candidate
entry/exit prices, forward returns, or PnL, and it never reads closes on or
after the supplied date.  Because the offline harness does not verify that the
manifest date is the true publication clock, it makes no stronger claim about
real post-publication prices.  This is a density/concentration preflight, not
an alpha result or trading adapter.

Policy frozen by exp-20260721-003:

* only exact ``Action`` values ``Addition`` and ``Deletion`` for the S&P 500,
  S&P MidCap 400, and S&P SmallCap 600 are admitted;
* an addition whose ticker is also deleted on the same publication/effective
  event clock is a Composite 1500 tier migration and is excluded, including
  when the two rows are split across release URLs;
* a supplied date-only manifest clock is treated as conservatively available
  at EOD for schedule construction, while remaining explicitly unverified;
* releases on the same calendar publication date form one event clock;
* clock legs use inverse volatility weights, where volatility is the sample
  standard deviation of exactly 20 close-to-close log returns made from the
  last 21 positive closes strictly before the supplied manifest date.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urljoin


EXPERIMENT_ID = "exp-20260721-003"
RULE_VERSION = "sp1500_net_new_preflight_inverse_vol_v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260721_003_sp1500_constituent_addition_preflight.json"
)
DEFAULT_WAREHOUSES = (
    REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite",
    REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite",
)
ARCHIVE_URL = "https://press.spglobal.com/index.php?s=2429&l=100&year={year}"
WINDOWS = (
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
)
TARGET_INDEX_NAMES = {
    "s p 500": ("S&P 500", 500),
    "s p midcap 400": ("S&P MidCap 400", 400),
    "s p mid cap 400": ("S&P MidCap 400", 400),
    "s p 400": ("S&P MidCap 400", 400),
    "s p smallcap 600": ("S&P SmallCap 600", 600),
    "s p small cap 600": ("S&P SmallCap 600", 600),
    "s p 600": ("S&P SmallCap 600", 600),
}
REQUIRED_HEADERS = (
    "effective date",
    "index name",
    "action",
    "company name",
    "ticker",
    "gics sector",
)
OUTCOME_BLIND_QUERY_CONTRACT = (
    {
        "purpose": "warehouse_session_calendar",
        "selected_columns": ["date"],
        "price_columns": [],
        "post_manifest_date_price_read": False,
    },
    {
        "purpose": "strict_pre_manifest_date_20_return_realized_volatility",
        "selected_columns": ["date", "close"],
        "predicate": "ticker = ? AND date < supplied_manifest_date AND close > 0",
        "ordering_and_limit": "date DESC LIMIT 21",
        "post_manifest_date_price_read": False,
    },
)


def _normal_text(value: Any) -> str:
    text = str(value or "").replace("\xa0", " ")
    return " ".join(text.split())


def _key_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normal_text(value).casefold()).strip()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    canonical = "\x1f".join(_normal_text(part) for part in parts)
    return f"{prefix}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_MONTH_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))


def parse_date(value: Any) -> str:
    """Extract one calendar date without making an intraday-time claim."""
    text = _normal_text(value)
    iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))).isoformat()
    named = re.search(
        rf"\b({_MONTH_PATTERN})\.?\s+(\d{{1,2}})\s*,?\s*(20\d{{2}})\b",
        text,
        flags=re.IGNORECASE,
    )
    if named:
        month = _MONTHS[named.group(1).casefold().rstrip(".")]
        return date(int(named.group(3)), month, int(named.group(2))).isoformat()
    numeric = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", text)
    if numeric:
        return date(
            int(numeric.group(3)), int(numeric.group(1)), int(numeric.group(2))
        ).isoformat()
    raise ValueError(f"no supported calendar date in {value!r}")


class _ArchiveParser(HTMLParser):
    """Extract ``li.wd_item`` / ``wd_date`` / ``wd_title a`` records."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.item_depth: int | None = None
        self.date_depth: int | None = None
        self.title_depth: int | None = None
        self.anchor_depth: int | None = None
        self.current: dict[str, Any] | None = None
        self.items: list[dict[str, str]] = []

    @staticmethod
    def _classes(attrs: Sequence[tuple[str, str | None]]) -> set[str]:
        values = dict(attrs).get("class") or ""
        return {part.casefold() for part in values.split()}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        classes = self._classes(attrs)
        if tag.casefold() == "li" and "wd_item" in classes:
            self.item_depth = self.depth
            self.current = {"date_parts": [], "title_parts": [], "href": ""}
        if self.current is None:
            return
        if "wd_date" in classes:
            self.date_depth = self.depth
        if "wd_title" in classes:
            self.title_depth = self.depth
        if tag.casefold() == "a" and self.title_depth is not None:
            self.anchor_depth = self.depth
            self.current["href"] = dict(attrs).get("href") or ""

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        if self.date_depth is not None:
            self.current["date_parts"].append(data)
        if self.anchor_depth is not None:
            self.current["title_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is not None:
            if self.depth == self.anchor_depth:
                self.anchor_depth = None
            if self.depth == self.date_depth:
                self.date_depth = None
            if self.depth == self.title_depth:
                self.title_depth = None
            if self.depth == self.item_depth:
                self.items.append(
                    {
                        "published_text": _normal_text(" ".join(self.current["date_parts"])),
                        "title": _normal_text(" ".join(self.current["title_parts"])),
                        "href": _normal_text(self.current["href"]),
                    }
                )
                self.current = None
                self.item_depth = None
                self.date_depth = None
                self.title_depth = None
                self.anchor_depth = None
        self.depth = max(0, self.depth - 1)


class _TableParser(HTMLParser):
    """Small deterministic HTML table extractor with rowspan expansion."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[dict[str, Any]]]] = []
        self.table: list[list[dict[str, Any]]] | None = None
        self.row: list[dict[str, Any]] | None = None
        self.cell: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag == "table" and self.table is None:
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            attributes = dict(attrs)
            self.cell = {
                "parts": [],
                "rowspan": max(1, int(attributes.get("rowspan") or 1)),
                "colspan": max(1, int(attributes.get("colspan") or 1)),
            }
        elif tag == "br" and self.cell is not None:
            self.cell["parts"].append(" ")

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.cell["text"] = _normal_text(" ".join(self.cell.pop("parts")))
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def _expand_rows(raw_rows: Sequence[Sequence[Mapping[str, Any]]]) -> list[list[str]]:
    active: dict[int, tuple[int, str]] = {}
    expanded: list[list[str]] = []
    for raw_row in raw_rows:
        values: dict[int, str] = {}
        next_active: dict[int, tuple[int, str]] = {}
        for column, (remaining, text) in active.items():
            values[column] = text
            if remaining > 1:
                next_active[column] = (remaining - 1, text)
        column = 0
        for cell in raw_row:
            while column in values:
                column += 1
            text = _normal_text(cell.get("text"))
            colspan = max(1, int(cell.get("colspan") or 1))
            rowspan = max(1, int(cell.get("rowspan") or 1))
            for offset in range(colspan):
                target = column + offset
                values[target] = text
                if rowspan > 1:
                    next_active[target] = (rowspan - 1, text)
            column += colspan
        active = next_active
        if values:
            width = max(values) + 1
            expanded.append([values.get(index, "") for index in range(width)])
    return expanded


def parse_archive_html(html: str | bytes, *, archive_url: str) -> list[dict[str, str]]:
    payload = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else str(html)
    parser = _ArchiveParser()
    parser.feed(payload)
    releases: list[dict[str, str]] = []
    for item in parser.items:
        title = item["title"]
        if not re.search(r"set\s+to\s+join\s+s\s*&\s*p", title, flags=re.IGNORECASE):
            continue
        if not item["href"]:
            continue
        try:
            published_date = parse_date(item["published_text"])
        except ValueError:
            continue
        releases.append(
            {
                "published_date": published_date,
                "publication_precision": "date_only",
                "availability_rule": "publication_date_conservative_eod",
                "title": title,
                "source_url": urljoin(archive_url, item["href"]),
            }
        )
    unique = {row["source_url"]: row for row in releases}
    return sorted(unique.values(), key=lambda row: (row["published_date"], row["source_url"]))


def _target_index(value: Any) -> tuple[str, int] | None:
    return TARGET_INDEX_NAMES.get(_key_text(value))


def _normal_ticker(value: Any) -> str | None:
    text = _normal_text(value).upper().replace(".", "-")
    text = re.sub(r"\s+", "", text)
    if not re.fullmatch(r"[A-Z][A-Z0-9-]{0,11}", text):
        return None
    return text


def parse_release_html(
    html: str | bytes,
    *,
    source_url: str,
    published_date: str,
    title: str = "",
) -> list[dict[str, Any]]:
    """Parse exact official constituent-change table rows.

    Rows with a non-exact action or an index outside 500/400/600 are ignored.
    The archive publication date is authoritative and remains date-only.
    """
    published = parse_date(published_date)
    payload = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else str(html)
    parser = _TableParser()
    parser.feed(payload)
    parsed: list[dict[str, Any]] = []
    for raw_table in parser.tables:
        rows = _expand_rows(raw_table)
        header: dict[str, int] | None = None
        for row in rows:
            keys = [_key_text(cell) for cell in row]
            candidate = {name: keys.index(name) for name in REQUIRED_HEADERS if name in keys}
            if len(candidate) == len(REQUIRED_HEADERS):
                header = candidate
                continue
            if header is None:
                continue
            if max(header.values()) >= len(row):
                continue
            action_text = _normal_text(row[header["action"]])
            if action_text not in {"Addition", "Deletion"}:
                continue
            index = _target_index(row[header["index name"]])
            if index is None:
                continue
            ticker = _normal_ticker(row[header["ticker"]])
            if ticker is None:
                continue
            try:
                effective = parse_date(row[header["effective date"]])
            except ValueError:
                continue
            canonical_index, tier = index
            row_id = _stable_id(
                "sp1500-row", source_url, published, effective, action_text, ticker, tier
            )
            parsed.append(
                {
                    "row_id": row_id,
                    "published_date": published,
                    "publication_precision": "date_only",
                    "availability_rule": "publication_date_conservative_eod",
                    "published_at": None,
                    "effective_date": effective,
                    "index_name": canonical_index,
                    "index_tier": tier,
                    "action": action_text,
                    "company_name": _normal_text(row[header["company name"]]),
                    "ticker": ticker,
                    "source_ticker": _normal_text(row[header["ticker"]]).upper(),
                    "gics_sector": _normal_text(row[header["gics sector"]]) or "Unknown",
                    "source_url": source_url,
                    "release_title": _normal_text(title),
                }
            )
    unique = {row["row_id"]: row for row in parsed}
    return sorted(
        unique.values(),
        key=lambda row: (
            row["published_date"],
            row["source_url"],
            row["action"],
            row["ticker"],
            row["index_tier"],
        ),
    )


def _readonly_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _load_sessions(warehouse_paths: Sequence[str | Path]) -> list[str]:
    sessions: set[str] = set()
    for raw_path in warehouse_paths:
        path = Path(raw_path)
        if not path.is_file():
            continue
        with sqlite3.connect(_readonly_uri(path), uri=True) as connection:
            tables = {
                str(row[0])
                for row in connection.execute("select name from sqlite_master where type='table'")
            }
            if "ohlcv" not in tables:
                continue
            # Calendar only. No open/close/high/low/return column is selected.
            for (day,) in connection.execute("select distinct date from ohlcv order by date"):
                text = str(day)[:10]
                if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", text):
                    sessions.add(text)
    return sorted(sessions)


def _strict_prepublication_closes(
    warehouse_paths: Sequence[str | Path], ticker: str, published_date: str
) -> list[tuple[str, float]]:
    by_date: dict[str, float] = {}
    for raw_path in warehouse_paths:
        path = Path(raw_path)
        if not path.is_file():
            continue
        with sqlite3.connect(_readonly_uri(path), uri=True) as connection:
            tables = {
                str(row[0])
                for row in connection.execute("select name from sqlite_master where type='table'")
            }
            if "ohlcv" not in tables:
                continue
            rows = connection.execute(
                "select date, close from ohlcv "
                "where upper(ticker) = ? and date < ? and close > 0 "
                "order by date desc limit 21",
                (ticker.upper(), published_date),
            )
            for day, close in rows:
                try:
                    value = float(close)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value) and value > 0:
                    by_date[str(day)[:10]] = value
    return sorted(by_date.items())[-21:]


def strict_prepublication_sigma(
    warehouse_paths: Sequence[str | Path], ticker: str, published_date: str
) -> tuple[float | None, dict[str, Any]]:
    closes = _strict_prepublication_closes(warehouse_paths, ticker, published_date)
    if len(closes) != 21:
        return None, {
            "status": "insufficient_prepublication_closes",
            "close_count": len(closes),
            "required_close_count": 21,
        }
    returns = [math.log(closes[index][1] / closes[index - 1][1]) for index in range(1, 21)]
    sigma = statistics.stdev(returns)
    if not math.isfinite(sigma) or sigma <= 0:
        return None, {
            "status": "nonpositive_prepublication_sigma",
            "close_count": 21,
            "return_count": 20,
        }
    return sigma, {
        "status": "ok",
        "close_count": 21,
        "return_count": 20,
        "first_close_date": closes[0][0],
        "last_close_date": closes[-1][0],
        "last_close_strictly_before_publication": closes[-1][0] < published_date,
    }


def _window_for_publication(published_date: str) -> tuple[str, str, str] | None:
    for label, start, end in WINDOWS:
        if start <= published_date <= end:
            return label, start, end
    return None


def _schedule(
    published_date: str, effective_date: str, sessions: Sequence[str]
) -> tuple[str | None, str | None, str | None]:
    entry = next((day for day in sessions if day > published_date), None)
    exit_ = next((day for day in reversed(sessions) if day < effective_date), None)
    if entry is None:
        return None, exit_, "missing_next_warehouse_session"
    if exit_ is None:
        return entry, None, "missing_pre_effective_warehouse_session"
    if entry >= exit_:
        return entry, exit_, "entry_not_before_exit"
    return entry, exit_, None


def _top_weighted(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, Any] | None:
    totals: dict[str, float] = defaultdict(float)
    denominator = 0.0
    for row in rows:
        weight = float(row["risk_weight"])
        totals[str(row.get(field) or "Unknown")] += weight
        denominator += weight
    if not totals or denominator <= 0:
        return None
    _name, weight = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[0]
    return {
        "risk_weight": round(weight, 12),
        "share": round(weight / denominator, 12),
        "share_pct": round(weight / denominator * 100.0, 4),
    }


def inverse_vol_weights(sigmas: Mapping[str, float]) -> dict[str, dict[str, float]]:
    """Return budget-conserving inverse-vol weights and risk contributions."""
    checked: dict[str, float] = {}
    for key, raw_sigma in sigmas.items():
        sigma = float(raw_sigma)
        if not math.isfinite(sigma) or sigma <= 0:
            raise ValueError(f"sigma for {key!r} must be finite and positive")
        checked[str(key)] = sigma
    if not checked:
        raise ValueError("at least one sigma is required")
    inverse = {key: 1.0 / sigma for key, sigma in checked.items()}
    denominator = sum(inverse.values())
    return {
        key: {
            "risk_weight": inverse[key] / denominator,
            "risk_contribution": inverse[key] / denominator * checked[key],
        }
        for key in sorted(checked)
    }


def build_preflight(
    release_rows: Sequence[Mapping[str, Any]],
    *,
    warehouse_paths: Sequence[str | Path],
    source_documents: Sequence[Mapping[str, Any]] = (),
    source_failures: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build the zero-outcome preflight artifact from parsed official rows."""
    sessions = _load_sessions(warehouse_paths)
    deduped = {str(row["row_id"]): dict(row) for row in release_rows}
    rows = sorted(deduped.values(), key=lambda row: str(row["row_id"]))
    # One economic event clock can be split across multiple release URLs.
    # Pair tier deletions/additions across URLs, but never across a different
    # publication date or effective date.
    deleted_by_event_clock: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        if row["action"] == "Deletion":
            event_key = (str(row["published_date"]), str(row["effective_date"]))
            deleted_by_event_clock[event_key].add(str(row["ticker"]))

    raw_by_window: dict[str, dict[str, list[dict[str, Any]]]] = {
        label: {"additions": [], "migrations": [], "net_new": []}
        for label, _start, _end in WINDOWS
    }
    failure_counts: dict[str, Counter[str]] = {label: Counter() for label, *_ in WINDOWS}
    eligible_by_clock: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)

    for row in rows:
        if row["action"] != "Addition":
            continue
        window = _window_for_publication(str(row["published_date"]))
        if window is None:
            continue
        label, start, end = window
        raw_by_window[label]["additions"].append(row)
        event_key = (str(row["published_date"]), str(row["effective_date"]))
        if str(row["ticker"]) in deleted_by_event_clock[event_key]:
            raw_by_window[label]["migrations"].append(row)
            failure_counts[label]["sp1500_tier_migration_same_event_clock"] += 1
            continue
        raw_by_window[label]["net_new"].append(row)
        entry, exit_, schedule_failure = _schedule(
            str(row["published_date"]), str(row["effective_date"]), sessions
        )
        if schedule_failure:
            failure_counts[label][schedule_failure] += 1
            continue
        assert entry is not None and exit_ is not None
        if not (start <= entry <= end and start <= exit_ <= end):
            failure_counts[label]["lifecycle_outside_standard_window"] += 1
            continue
        sigma, risk_detail = strict_prepublication_sigma(
            warehouse_paths, str(row["ticker"]), str(row["published_date"])
        )
        if sigma is None:
            failure_counts[label][str(risk_detail["status"])] += 1
            continue
        leg = {
            **row,
            "entry_date": entry,
            "entry_price_field": "open_not_read_in_preflight",
            "entry_rule": "first_warehouse_session_strictly_after_publication_date_open",
            "exit_date": exit_,
            "exit_price_field": "close_not_read_in_preflight",
            "exit_rule": "last_warehouse_session_strictly_before_effective_date_close",
            "prepublication_sigma": sigma,
            "risk_lookback": risk_detail,
            "risk_weight": None,
            "risk_contribution": None,
        }
        clock_key = (label, str(row["published_date"]))
        ticker = str(row["ticker"])
        if ticker in eligible_by_clock[clock_key]:
            failure_counts[label]["duplicate_ticker_same_publication_clock"] += 1
            continue
        eligible_by_clock[clock_key][ticker] = leg

    clocks_by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (label, published), ticker_legs in sorted(eligible_by_clock.items()):
        allocations = inverse_vol_weights(
            {
                ticker: float(leg["prepublication_sigma"])
                for ticker, leg in ticker_legs.items()
            }
        )
        weighted_legs: list[dict[str, Any]] = []
        for ticker in sorted(ticker_legs):
            leg = dict(ticker_legs[ticker])
            leg.update(allocations[ticker])
            weighted_legs.append(leg)
        clocks_by_window[label].append(
            {
                "clock_id": _stable_id("sp1500-clock", published),
                "publication_date": published,
                "release_urls": sorted({str(leg["source_url"]) for leg in weighted_legs}),
                "leg_count": len(weighted_legs),
                "risk_weight_sum": round(sum(float(leg["risk_weight"]) for leg in weighted_legs), 12),
                "legs": weighted_legs,
            }
        )

    window_results: dict[str, Any] = {}
    for label, start, end in WINDOWS:
        clocks = clocks_by_window.get(label, [])
        eligible = [leg for clock in clocks for leg in clock["legs"]]
        top_sector = _top_weighted(eligible, "gics_sector")
        top_ticker = _top_weighted(eligible, "ticker")
        unique_tickers = sorted({str(leg["ticker"]) for leg in eligible})
        counts = {
            "all_additions": len(raw_by_window[label]["additions"]),
            "migrations": len(raw_by_window[label]["migrations"]),
            "net_new": len(raw_by_window[label]["net_new"]),
            "eligible": len(eligible),
            "clocks": len(clocks),
            "unique_ticker": len(unique_tickers),
        }
        criteria = {
            "min_clocks_5": counts["clocks"] >= 5,
            "min_unique_tickers_10": counts["unique_ticker"] >= 10,
            "top_risk_weighted_sector_lte_35pct": bool(
                top_sector is not None and float(top_sector["share_pct"]) <= 35.0
            ),
        }
        window_results[label] = {
            "start": start,
            "end": end,
            "counts": counts,
            "top_risk_weighted_sector": top_sector,
            "top_risk_weighted_ticker": top_ticker,
            "failure_reasons": dict(sorted(failure_counts[label].items())),
            "criteria": criteria,
            "passed": all(criteria.values()),
        }

    density_criteria_passed = all(window_results[label]["passed"] for label, *_ in WINDOWS)
    # The official site's terms do not authorize this content for an
    # investment-strategy workflow.  Even a statistically passing local audit
    # therefore cannot promote the surface or trigger outcome reads.
    overall_passed = False
    return {
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "decision": "source_contract_blocked_do_not_read_outcomes",
        "overall_passed": overall_passed,
        "density_criteria_passed": density_criteria_passed,
        "source_contract_authorized_for_investment_strategy": False,
        "publication_clock_provenance_verified": False,
        "pit_candidate": False,
        "outcome_blind": True,
        "outcome_reads_performed": False,
        # The manifest clock is not independently verified by this offline
        # harness.  It can prove only that no rows on/after the supplied date
        # were read, not that the supplied date is the true publication time.
        "post_manifest_date_price_or_return_data_read": False,
        "post_publication_price_or_return_data_read": None,
        "post_publication_read_status": "unknown_due_unverified_manifest_clock",
        "strictly_pre_manifest_date_close_input_read": True,
        "trade_enabled": False,
        "candidate_eligible": False,
        "orders": [],
        "strategy_behavior_changed": False,
        "policy": {
            "source_rows": "exact Action=Addition/Deletion and index in S&P 500/MidCap 400/SmallCap 600",
            "migration_exclusion": "same publication date plus effective date plus ticker has a Deletion row, across release URLs",
            "candidate_population": "net_new_to_sp_composite_1500_only",
            "publication_availability": "supplied_manifest_date_conservative_EOD_but_unverified",
            "entry": "first warehouse session strictly after publication date; open value not read",
            "exit": "last warehouse session strictly before effective date; close value not read",
            "clock": "merge all releases sharing one calendar publication date",
            "risk": "inverse of sample sigma over 20 close-to-close log returns from 21 closes strictly before supplied manifest date",
        },
        "outcome_blind_query_contract": list(OUTCOME_BLIND_QUERY_CONTRACT),
        "forbidden_fields_not_read": [
            "entry_open",
            "exit_close",
            "forward_return",
            "pnl",
            "spy_replacement_value",
            "qqq_replacement_value",
        ],
        "warehouse_paths": [str(Path(path)) for path in warehouse_paths],
        "warehouse_session_count": len(sessions),
        # Content-license boundary: persist hashes/counts only.  Do not emit
        # release URLs, titles, tickers, row details, or raw HTML.
        "source_input_fingerprints": [
            {
                key: document.get(key)
                for key in ("document_type", "sha256", "bytes", "parsed_row_count")
                if document.get(key) is not None
            }
            for document in source_documents
        ],
        "source_failure_counts": dict(
            sorted(Counter(str(item.get("stage") or "unknown") for item in source_failures).items())
        ),
        "parsed_official_row_count": len(rows),
        "windows": window_results,
    }


def load_local_release_manifest(path: str | Path) -> list[dict[str, Any]]:
    """Load an explicitly supplied local manifest; never access the network.

    Manifest entries contain ``source_url``, ``published_date``, optional
    ``title``, and ``html_path``.  Raw HTML is parsed in place, hashed, and is
    never copied into the artifact or repository by this runner.
    """
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    entries = payload.get("releases") if isinstance(payload, Mapping) else payload
    if not isinstance(entries, list):
        raise ValueError("local manifest must be a list or contain a releases list")
    documents: list[dict[str, Any]] = []
    for raw in entries:
        if not isinstance(raw, Mapping):
            raise ValueError("each local release manifest entry must be an object")
        html_path = Path(str(raw["html_path"]))
        if not html_path.is_absolute():
            html_path = manifest_path.parent / html_path
        documents.append(
            {
                "source_url": str(raw["source_url"]),
                "published_date": str(raw["published_date"]),
                "title": str(raw.get("title") or ""),
                "html": html_path.read_bytes(),
                "local_path": str(html_path),
            }
        )
    return documents


def run_preflight(
    *,
    warehouse_paths: Sequence[str | Path] = DEFAULT_WAREHOUSES,
    output_path: str | Path | None = DEFAULT_OUTPUT,
    release_documents: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Consume explicitly injected local release HTML, build, and persist.

    There is intentionally no live-fetch path.  This prevents accidental use
    or redistribution after the source-contract audit failed.
    """
    documents: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    if release_documents is None:
        raise ValueError("release_documents is required; live network fetch is disabled")
    else:
        for document in release_documents:
            source_url = str(document["source_url"])
            html = document["html"]
            payload = html.encode("utf-8") if isinstance(html, str) else bytes(html)
            parsed = parse_release_html(
                payload,
                source_url=source_url,
                published_date=str(document["published_date"]),
                title=str(document.get("title") or ""),
            )
            rows.extend(parsed)
            documents.append(
                {
                    "url": source_url,
                    "document_type": "release_injected",
                    "sha256": _sha256_bytes(payload),
                    "bytes": len(payload),
                    "published_date": parse_date(document["published_date"]),
                    "parsed_row_count": len(parsed),
                }
            )
    artifact = build_preflight(
        rows,
        warehouse_paths=warehouse_paths,
        source_documents=documents,
        source_failures=failures,
    )
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(destination)
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--warehouse", action="append", dest="warehouses")
    parser.add_argument("--manifest", required=True, help="explicit local JSON manifest")
    args = parser.parse_args(argv)
    artifact = run_preflight(
        warehouse_paths=args.warehouses or DEFAULT_WAREHOUSES,
        output_path=args.output,
        release_documents=load_local_release_manifest(args.manifest),
    )
    compact = {
        "experiment_id": artifact["experiment_id"],
        "decision": artifact["decision"],
        "overall_passed": artifact["overall_passed"],
        "windows": {
            label: {
                "counts": row["counts"],
                "top_risk_weighted_sector": row["top_risk_weighted_sector"],
                "passed": row["passed"],
            }
            for label, row in artifact["windows"].items()
        },
        "output": args.output,
    }
    print(json.dumps(compact, indent=2, sort_keys=True))
    return 0 if artifact["overall_passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
