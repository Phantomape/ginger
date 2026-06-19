"""Parsed point-in-time Schedule 13D/13G holder-stake ingestion.

exp-20260618-016. Prior raw 13D/13G *metadata-only* event gates were rejected
(exp-20260612-015 13D, exp-20260612-016 13G) and several June-18 readiness
audits (exp-012/013/014) concluded the missing piece was a parsed PIT
holder/stake/intent table. EDGAR now hosts structured ``primary_doc.xml``
cover-page documents for Schedule 13D/13G filings (schemas
``http://www.sec.gov/edgar/schedule13D`` / ``schedule13G``) carrying reporting
person identity, beneficial-ownership ``classPercent``, share counts, reporting
person type, and (13D) purpose text. This module enumerates ownership filings
from the local SEC submissions cache, fetches and caches the structured XML
from EDGAR, and parses it into normalized rows.

No trading policy, ranking, sizing, exits, live orders, or default trade
settings are touched here. This is a read/ingest data surface. No JavaScript is
used.

PIT contract: ``signal_date`` is the SEC ``filing_date``; production must enter
no earlier than the next trading session, so downstream replay uses next-open
after ``filing_date``. ``usable_trade_date`` records that next-business-day
floor (calendar approximation; the replay snaps to the next real trading day in
the OHLCV warehouse).
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
XML_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "ownership_13d13g"
OUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec_13d13g_holdings"
OUT_ROWS = OUT_DIR / "rows.json"

USER_AGENT = "ginger-research phantomape93@gmail.com"

# Canonical three standard windows (docs/backtesting.md).
WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}

# Big-3 passive index complexes: their 13G filings are overwhelmingly
# mechanical index rebalancing, not informed accumulation. Used only as an
# attribute tag for diagnostics, never as a hard production rule here.
BIG3_TOKENS = ("vanguard", "blackrock", "state street", "ssga")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def normalize_cik(value: Any) -> str | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits.zfill(10) if digits else None


def window_for_date(filing_date: str) -> str | None:
    for label, (start, end) in WINDOWS.items():
        if start <= filing_date <= end:
            return label
    return None


def _next_business_day(filing_date: str) -> str:
    try:
        d = date.fromisoformat(filing_date)
    except ValueError:
        return filing_date
    d += timedelta(days=1)
    while d.weekday() >= 5:  # Sat/Sun -> Monday (calendar approximation)
        d += timedelta(days=1)
    return d.isoformat()


def is_13d13g(form: str, description: str) -> tuple[bool, str | None, bool]:
    """Return (is_match, family, is_amendment)."""
    text = f"{form} {description}".upper()
    if "13D" not in text and "13G" not in text:
        return (False, None, False)
    family = "13D" if "13D" in text else "13G"
    is_amend = "/A" in form.upper()
    return (True, family, is_amend)


def iter_ownership_filings(
    families: Iterable[str] = ("13D", "13G"),
    include_amendments: bool = True,
) -> list[dict[str, Any]]:
    """Enumerate 13D/13G filings in the canonical windows from submissions cache.

    Each submissions file is per-issuer-company; ``tickers[0]`` is the issuer
    ticker and EDGAR mirrors the filing under the issuer CIK archive dir, so the
    structured XML is fetchable from the issuer CIK + accession.
    """
    families = set(families)
    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(SUBMISSIONS_DIR.glob("CIK*.json")):
        payload = read_json(path, {})
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        descriptions = recent.get("primaryDocDescription", [])
        accessions = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        accepted_times = recent.get("acceptanceDateTime", [])
        primary_docs = recent.get("primaryDocument", [])
        tickers = payload.get("tickers") or []
        ticker = tickers[0] if tickers else None
        cik = normalize_cik(payload.get("cik") or path.stem.removeprefix("CIK"))
        for idx, raw_form in enumerate(forms):
            form = str(raw_form or "").strip().upper()
            description = (
                descriptions[idx]
                if idx < len(descriptions) and descriptions[idx]
                else ""
            )
            matched, family, is_amend = is_13d13g(form, description)
            if not matched or family not in families:
                continue
            if is_amend and not include_amendments:
                continue
            filing_date = filing_dates[idx] if idx < len(filing_dates) else ""
            label = window_for_date(filing_date)
            if not label:
                continue
            accession = accessions[idx] if idx < len(accessions) else ""
            key = (cik or "", accession)
            if not accession or key in seen:
                continue
            seen.add(key)
            primary_document = primary_docs[idx] if idx < len(primary_docs) else ""
            structured = (
                "xslschedule" in str(primary_document).lower()
                or str(primary_document).lower().endswith(".xml")
            )
            events.append(
                {
                    "ticker": ticker,
                    "issuer_cik": cik,
                    "accession_number": accession,
                    "form": form,
                    "family": family,
                    "is_amendment": is_amend,
                    "primary_doc_description": description,
                    "filing_date": filing_date,
                    "accepted_at": accepted_times[idx] if idx < len(accepted_times) else "",
                    "primary_document": primary_document,
                    "structured_xml": bool(structured),
                    "window": label,
                    "usable_trade_date": _next_business_day(filing_date),
                }
            )
    return events


def _archive_dir(cik: str, accession: str) -> str:
    acc_nodash = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}"


def fetch_primary_doc_xml(
    event: dict[str, Any], *, refresh: bool = False, request_delay_sec: float = 0.12
) -> dict[str, Any]:
    """Fetch and cache the structured ``primary_doc.xml`` for one filing."""
    accession = event["accession_number"]
    cik = event["issuer_cik"]
    XML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = XML_CACHE_DIR / f"{accession.replace('-', '')}.xml"
    if cache_path.exists() and not refresh:
        return {"status": "cached", "path": cache_path, "raw": cache_path.read_text(encoding="utf-8")}
    if not cik or not accession:
        return {"status": "missing_ids", "path": None, "raw": None}
    url = f"{_archive_dir(cik, accession)}/primary_doc.xml"
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        time.sleep(request_delay_sec)
        return {"status": f"http_{exc.code}", "path": None, "raw": None, "url": url}
    except Exception as exc:  # noqa: BLE001 - network robustness
        time.sleep(request_delay_sec)
        return {"status": f"err_{type(exc).__name__}", "path": None, "raw": None, "url": url}
    time.sleep(request_delay_sec)
    if "edgarSubmission" not in raw:
        return {"status": "not_structured_xml", "path": None, "raw": raw, "url": url}
    cache_path.write_text(raw, encoding="utf-8")
    return {"status": "fetched", "path": cache_path, "raw": raw}


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_all_local(root: ET.Element, name: str) -> list[ET.Element]:
    return [el for el in root.iter() if _localname(el.tag) == name]


def _first_text(root: ET.Element, name: str) -> str | None:
    for el in root.iter():
        if _localname(el.tag) == name and (el.text or "").strip():
            return el.text.strip()
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def parse_schedule_xml(raw_xml: str) -> dict[str, Any] | None:
    """Parse one structured Schedule 13D/13G ``primary_doc.xml``.

    Returns issuer fields plus per-reporting-person stake details. Robust to the
    13D vs 13G schema differences by matching on local element names.
    """
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return None
    if _localname(root.tag) != "edgarSubmission":
        return None

    submission_type = _first_text(root, "submissionType")
    amendment_no = _first_text(root, "amendmentNo")
    # 13G uses eventDateRequiresFilingThisStatement; 13D uses dateOfEvent.
    event_date = _first_text(root, "eventDateRequiresFilingThisStatement") or _first_text(
        root, "dateOfEvent"
    )
    issuer_name = _first_text(root, "issuerName")
    issuer_cik = _first_text(root, "issuerCik")
    issuer_cusip = _first_text(root, "issuerCusipNumber") or _first_text(root, "issuerCusip")

    # Reporting persons: each detail block carries a name, classPercent,
    # aggregate shares, and type. Schemas nest these under
    # coverPageHeaderReportingPersonDetails (13G) or reportingPersonDetails (13D).
    persons: list[dict[str, Any]] = []
    detail_names = (
        "coverPageHeaderReportingPersonDetails",  # 13G
        "reportingPersonDetails",
        "reportingPersonInfo",  # 13D
    )
    detail_blocks: list[ET.Element] = []
    for dn in detail_names:
        detail_blocks.extend(_find_all_local(root, dn))
    for block in detail_blocks:
        name = None
        class_pct = None
        agg_shares = None
        rp_type = None
        citizenship = None
        for el in block.iter():
            ln = _localname(el.tag)
            txt = (el.text or "").strip()
            if not txt:
                continue
            if ln in ("reportingPersonName", "nameOfReportingPerson") and name is None:
                name = txt
            elif ln in ("classPercent", "percentOfClass") and class_pct is None:
                # 13G: classPercent; 13D: percentOfClass. Junk like
                # "See Items 11 and 13" returns None via _to_float.
                class_pct = _to_float(txt)
            elif (
                ln
                in (
                    "reportingPersonBeneficiallyOwnedAggregateNumberOfShares",  # 13G
                    "aggregateAmountOwned",  # 13D
                )
                and agg_shares is None
            ):
                agg_shares = _to_float(txt)
            elif ln in ("typeOfReportingPerson", "reportingPersonType") and rp_type is None:
                rp_type = txt
            elif ln in ("citizenshipOrOrganization", "citizenshipOrPlaceOfOrganization") and citizenship is None:
                citizenship = txt
        if any(v is not None for v in (name, class_pct, agg_shares, rp_type)):
            persons.append(
                {
                    "reporting_person_name": name,
                    "class_percent": class_pct,
                    "aggregate_shares": agg_shares,
                    "reporting_person_type": rp_type,
                    "citizenship": citizenship,
                }
            )

    # Fallback: some filings put a single percent at top level.
    if not persons:
        top_pct = _to_float(
            _first_text(root, "classPercent") or _first_text(root, "percentOfClass")
        )
        top_name = _first_text(root, "reportingPersonName")
        if top_pct is not None or top_name is not None:
            persons.append(
                {
                    "reporting_person_name": top_name,
                    "class_percent": top_pct,
                    "aggregate_shares": _to_float(
                        _first_text(
                            root,
                            "reportingPersonBeneficiallyOwnedAggregateNumberOfShares",
                        )
                        or _first_text(root, "aggregateAmountOwned")
                    ),
                    "reporting_person_type": _first_text(root, "typeOfReportingPerson"),
                    "citizenship": None,
                }
            )

    comments = _first_text(root, "comments")
    return {
        "submission_type": submission_type,
        "amendment_no": amendment_no,
        "event_date": event_date,
        "issuer_name": issuer_name,
        "issuer_cik_xml": normalize_cik(issuer_cik),
        "issuer_cusip": issuer_cusip,
        "reporting_persons": persons,
        "comments": (comments or "")[:500] or None,
    }


def parse_13ga_direction_fields(raw_xml: str) -> dict[str, Any] | None:
    """Parse the 13G/A amendment fields needed for stake-change DIRECTION.

    The cover-page ``coverPageHeaderReportingPersonDetails`` block on a 13G/A is
    frequently empty of a percent; the authoritative current beneficial-ownership
    percent lives per-reporting-person in ``<item4><classPercent>`` /
    ``<amountBeneficiallyOwned>``. ``<previousAccessionNumber>`` gives a clean PIT
    pointer to the immediately prior filing (initial 13G or earlier 13G/A) so a
    later replay can chain to the prior stake without future data. The item5
    ``classOwnership5PercentOrLess`` = ``Y`` flag is the cleanest 100%-captured
    directional fact: the holder has fallen below the 5% reporting threshold
    (a major trim / exit).

    Returns ``None`` only when the document is not a structured edgarSubmission.
    Fields may be ``None`` individually when the schema omits them.
    """
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return None
    if _localname(root.tag) != "edgarSubmission":
        return None

    previous_accession = None
    below_5pct = None
    for el in root.iter():
        name = _localname(el.tag)
        txt = (el.text or "").strip()
        if name == "previousAccessionNumber" and txt and previous_accession is None:
            previous_accession = txt
        if name == "classOwnership5PercentOrLess" and txt:
            below_5pct = txt.strip().upper() == "Y"

    # Per-reporting-person current percent from item4 blocks. A single 13G/A may
    # carry several item4 blocks (one per reporting person); the max is the
    # filer-group beneficial-ownership level comparable to ``max_class_percent``.
    item4_percents: list[float] = []
    item4_shares: list[float] = []
    for el in root.iter():
        if _localname(el.tag) != "item4":
            continue
        cp = None
        amt = None
        for c in el.iter():
            cn = _localname(c.tag)
            ct = (c.text or "").strip()
            if not ct:
                continue
            if cn == "classPercent" and cp is None:
                cp = _to_float(ct)
            elif cn == "amountBeneficiallyOwned" and amt is None:
                amt = _to_float(ct)
        if cp is not None:
            item4_percents.append(cp)
        if amt is not None:
            item4_shares.append(amt)

    current_max_percent = max(item4_percents) if item4_percents else None
    current_max_shares = max(item4_shares) if item4_shares else None
    return {
        "previous_accession": previous_accession,
        "below_5pct": below_5pct,
        "item4_current_max_percent": current_max_percent,
        "item4_current_max_shares": current_max_shares,
        "item4_person_count": len(item4_percents),
    }


def _holder_flags(persons: list[dict[str, Any]]) -> dict[str, Any]:
    names = " | ".join((p.get("reporting_person_name") or "").lower() for p in persons)
    is_big3 = any(tok in names for tok in BIG3_TOKENS)
    pcts = [p["class_percent"] for p in persons if p.get("class_percent") is not None]
    max_pct = max(pcts) if pcts else None
    # IA (investment adviser) / II (institution) are typical passive types.
    types = {(p.get("reporting_person_type") or "").upper() for p in persons}
    return {
        "is_big3": is_big3,
        "max_class_percent": max_pct,
        "reporting_person_types": sorted(t for t in types if t),
        "n_reporting_persons": len(persons),
    }


def build_parsed_rows(events: list[dict[str, Any]], *, fetch: bool, refresh: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    status_counter: Counter = Counter()
    for ev in events:
        if fetch:
            res = fetch_primary_doc_xml(ev, refresh=refresh)
        else:
            cache_path = XML_CACHE_DIR / f"{ev['accession_number'].replace('-', '')}.xml"
            if cache_path.exists():
                res = {"status": "cached", "raw": cache_path.read_text(encoding="utf-8")}
            else:
                res = {"status": "not_fetched", "raw": None}
        status_counter[res["status"]] += 1
        raw = res.get("raw")
        parsed = parse_schedule_xml(raw) if raw else None
        if not parsed:
            continue
        flags = _holder_flags(parsed["reporting_persons"])
        rows.append(
            {
                "ticker": ev["ticker"],
                "issuer_cik": ev["issuer_cik"],
                "accession_number": ev["accession_number"],
                "form": ev["form"],
                "family": ev["family"],
                "is_amendment": ev["is_amendment"],
                "filing_date": ev["filing_date"],
                "accepted_at": ev["accepted_at"],
                "usable_trade_date": ev["usable_trade_date"],
                "window": ev["window"],
                "submission_type": parsed["submission_type"],
                "amendment_no": parsed["amendment_no"],
                "event_date": parsed["event_date"],
                "issuer_name": parsed["issuer_name"],
                "issuer_cusip": parsed["issuer_cusip"],
                "reporting_persons": parsed["reporting_persons"],
                "comments": parsed["comments"],
                **flags,
            }
        )
    return {"rows": rows, "fetch_status": dict(status_counter)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest parsed Schedule 13D/13G holder-stake rows.")
    parser.add_argument("--families", default="13D,13G", help="Comma list of families to ingest.")
    parser.add_argument("--no-amendments", action="store_true", help="Skip /A amendments.")
    parser.add_argument("--fetch", action="store_true", help="Fetch missing XML from EDGAR.")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch even if cached.")
    parser.add_argument("--max", type=int, default=0, help="Limit number of filings (0 = all).")
    args = parser.parse_args()

    families = [f.strip() for f in args.families.split(",") if f.strip()]
    events = iter_ownership_filings(
        families=families, include_amendments=not args.no_amendments
    )
    if args.max:
        events = events[: args.max]
    result = build_parsed_rows(events, fetch=args.fetch, refresh=args.refresh)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": utc_now(),
        "windows": WINDOWS,
        "families": families,
        "include_amendments": not args.no_amendments,
        "total_events_enumerated": len(events),
        "parsed_row_count": len(result["rows"]),
        "fetch_status": result["fetch_status"],
        "rows": result["rows"],
    }
    OUT_ROWS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "total_events": len(events),
                "parsed_rows": len(result["rows"]),
                "fetch_status": result["fetch_status"],
                "out": str(OUT_ROWS.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
