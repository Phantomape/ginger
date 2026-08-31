"""Outcome-blind SEC EFFECT / prospectus linkage for the frozen resale roster.

The script reads no post-event prices or outcome labels.  It uses SEC
submissions metadata to determine whether a frozen S-1/F-1 can be linked by
CIK and SEC file number to a later EFFECT and/or 424B3/424B4 filing.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROSTER = (
    REPO_ROOT
    / "data"
    / "alpha_search"
    / "sec_selling_holder_overhang_roster_20260824.json"
)
DEFAULT_ECONOMICS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_offering_economics_tradeable"
    / "rows.jsonl"
)
DEFAULT_CACHE = REPO_ROOT / "data" / "non_ohlcv" / "sec_submissions_cache"
DEFAULT_EFFECT_CACHE = REPO_ROOT / "data" / "non_ohlcv" / "sec_effectiveness" / "raw"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "data"
    / "alpha_search"
    / "sec_selling_holder_effectiveness_linkage_20260824.json"
)
DEFAULT_USER_AGENT = "ginger-research/1.0 research@example.com"
PROSPECTUS_FORMS = {"424B3", "424B4"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            rows.append(value)
    return rows


def request_json(url: str, user_agent: str, attempts: int = 3) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept-Encoding": "identity"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                value = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("SEC response is not a JSON object")
            return value
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
            time.sleep(float(attempt))
    raise RuntimeError("unreachable")


def request_bytes(url: str, user_agent: str, attempts: int = 3) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept-Encoding": "identity"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
            time.sleep(float(attempt))
    raise RuntimeError("unreachable")


def cached_json(
    *, url: str, cache_path: Path, user_agent: str, delay_seconds: float
) -> dict[str, Any]:
    if cache_path.exists():
        value = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return value
    value = request_json(url, user_agent)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    time.sleep(delay_seconds)
    return value


def columnar_rows(columns: dict[str, Any]) -> list[dict[str, Any]]:
    arrays = {key: value for key, value in columns.items() if isinstance(value, list)}
    count = max((len(value) for value in arrays.values()), default=0)
    return [
        {
            key: values[index] if index < len(values) else None
            for key, values in arrays.items()
        }
        for index in range(count)
    ]


def normalize_file_number(value: Any) -> str:
    return " ".join(str(value or "").upper().split())


def filing_clock(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("filingDate") or "9999-12-31"),
        str(row.get("acceptanceDateTime") or ""),
    )


def load_cik_filings(
    cik: str,
    *,
    minimum_date: str,
    cache_dir: Path,
    user_agent: str,
    delay_seconds: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    padded = str(cik).zfill(10)
    recent_url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    recent_path = cache_dir / f"CIK{padded}.json"
    submission = cached_json(
        url=recent_url,
        cache_path=recent_path,
        user_agent=user_agent,
        delay_seconds=delay_seconds,
    )
    filings = submission.get("filings") or {}
    rows = columnar_rows((filings.get("recent") or {}))
    sources = [recent_path.resolve().relative_to(REPO_ROOT).as_posix()]
    for descriptor in filings.get("files") or []:
        if not isinstance(descriptor, dict):
            continue
        name = str(descriptor.get("name") or "")
        filing_from = str(descriptor.get("filingFrom") or "0000-00-00")
        filing_to = str(descriptor.get("filingTo") or "9999-12-31")
        if not name or filing_to < minimum_date or filing_from > date.today().isoformat():
            continue
        history_path = cache_dir / name
        history = cached_json(
            url=f"https://data.sec.gov/submissions/{name}",
            cache_path=history_path,
            user_agent=user_agent,
            delay_seconds=delay_seconds,
        )
        rows.extend(columnar_rows(history))
        sources.append(history_path.resolve().relative_to(REPO_ROOT).as_posix())
    by_accession: dict[str, dict[str, Any]] = {}
    for row in rows:
        accession = str(row.get("accessionNumber") or "")
        if accession:
            by_accession.setdefault(accession, row)
    return list(by_accession.values()), sources


def event_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "form": row.get("form"),
        "accession": row.get("accessionNumber"),
        "filing_date": row.get("filingDate"),
        "acceptance_datetime_raw": row.get("acceptanceDateTime"),
        "file_number": row.get("fileNumber"),
        "primary_document": row.get("primaryDocument"),
    }


def effect_document_url(cik: str, event: dict[str, Any]) -> str:
    accession_plain = str(event.get("accessionNumber") or "").replace("-", "")
    primary_name = Path(str(event.get("primaryDocument") or "primary_doc.xml")).name
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_plain}/{primary_name}"
    )


def parse_effect_document(raw: bytes) -> dict[str, Any]:
    root = ET.fromstring(raw)
    values: dict[str, str] = {}
    wanted = {
        "finalEffectivenessDispDate",
        "finalEffectivenessDispTime",
        "form",
        "fileNumber",
    }
    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1]
        if name in wanted and name not in values and element.text:
            values[name] = element.text.strip()
    effective_date = values.get("finalEffectivenessDispDate")
    effective_time = values.get("finalEffectivenessDispTime")
    effective_at_utc = None
    if effective_date and effective_time:
        local = datetime.strptime(
            f"{effective_date} {effective_time}", "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=ZoneInfo("America/New_York"))
        effective_at_utc = (
            local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        )
    return {
        "effective_date": effective_date,
        "effective_time_sec_display": effective_time,
        "effective_timezone_contract": "America/New_York",
        "effective_at_utc": effective_at_utc,
        "registration_form": values.get("form"),
        "file_number": values.get("fileNumber"),
    }


def load_effect_clock(
    cik: str,
    event: dict[str, Any],
    *,
    cache_dir: Path,
    user_agent: str,
    delay_seconds: float,
) -> dict[str, Any]:
    accession = str(event.get("accessionNumber") or "")
    cache_path = cache_dir / f"{accession}.xml"
    url = effect_document_url(cik, event)
    if cache_path.exists():
        raw = cache_path.read_bytes()
    else:
        raw = request_bytes(url, user_agent)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(raw)
        time.sleep(delay_seconds)
    parsed = parse_effect_document(raw)
    return {
        **parsed,
        "document_url": url,
        "document_path": cache_path.resolve().relative_to(REPO_ROOT).as_posix(),
        "document_sha256": hashlib.sha256(raw).hexdigest(),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    roster_path = Path(args.roster).resolve()
    economics_path = Path(args.economics).resolve()
    cache_dir = Path(args.cache_dir).resolve()
    effect_cache_dir = Path(args.effect_cache_dir).resolve()
    output_path = Path(args.output).resolve()
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    frozen_rows = roster["rows"]
    economics = {
        str(row.get("accession")): row for row in load_jsonl(economics_path)
    }

    by_cik: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unresolved_source: list[str] = []
    for frozen in frozen_rows:
        source = economics.get(str(frozen.get("accession")))
        if not source or not source.get("cik"):
            unresolved_source.append(str(frozen.get("accession")))
            continue
        joined = {**frozen, "cik": str(source["cik"]).zfill(10)}
        by_cik[joined["cik"]].append(joined)

    filings_by_cik: dict[str, list[dict[str, Any]]] = {}
    cache_sources: list[str] = []
    fetch_failures: dict[str, str] = {}
    for cik, rows in sorted(by_cik.items()):
        minimum_date = min(str(row["accepted_at"])[:10] for row in rows)
        try:
            filings, sources = load_cik_filings(
                cik,
                minimum_date=minimum_date,
                cache_dir=cache_dir,
                user_agent=args.user_agent,
                delay_seconds=args.delay_seconds,
            )
            filings_by_cik[cik] = filings
            cache_sources.extend(sources)
        except Exception as exc:  # failure is retained, never silently dropped
            fetch_failures[cik] = f"{type(exc).__name__}: {exc}"
            filings_by_cik[cik] = []

    output_rows: list[dict[str, Any]] = []
    effect_clocks: dict[str, dict[str, Any]] = {}
    effect_clock_failures: dict[str, str] = {}
    for cik, rows in sorted(by_cik.items()):
        filings = filings_by_cik[cik]
        by_accession = {
            str(row.get("accessionNumber")): row for row in filings
        }
        for frozen in rows:
            accession = str(frozen["accession"])
            registration = by_accession.get(accession)
            file_number = normalize_file_number(
                registration.get("fileNumber") if registration else None
            )
            after_date = str(frozen["accepted_at"])[:10]
            same_file_later = [
                row
                for row in filings
                if file_number
                and normalize_file_number(row.get("fileNumber")) == file_number
                and str(row.get("filingDate") or "") >= after_date
                and str(row.get("accessionNumber") or "") != accession
            ]
            effects = sorted(
                (row for row in same_file_later if row.get("form") == "EFFECT"),
                key=filing_clock,
            )
            prospectuses = sorted(
                (
                    row
                    for row in same_file_later
                    if str(row.get("form") or "") in PROSPECTUS_FORMS
                ),
                key=filing_clock,
            )
            official_effect_clock = None
            if effects:
                effect_accession = str(effects[0].get("accessionNumber") or "")
                if effect_accession not in effect_clocks and effect_accession not in effect_clock_failures:
                    try:
                        effect_clocks[effect_accession] = load_effect_clock(
                            cik,
                            effects[0],
                            cache_dir=effect_cache_dir,
                            user_agent=args.user_agent,
                            delay_seconds=args.delay_seconds,
                        )
                    except Exception as exc:
                        effect_clock_failures[effect_accession] = (
                            f"{type(exc).__name__}: {exc}"
                        )
                official_effect_clock = effect_clocks.get(effect_accession)
            output_rows.append(
                {
                    "window": frozen["window"],
                    "ticker": frozen["ticker"],
                    "cik": cik,
                    "registration_accession": accession,
                    "registration_accepted_at": frozen["accepted_at"],
                    "registration_form": frozen["form_type"],
                    "registration_found_in_submissions": registration is not None,
                    "file_number": file_number or None,
                    "effect": event_projection(effects[0]) if effects else None,
                    "official_effect_clock": official_effect_clock,
                    "first_resale_prospectus": (
                        event_projection(prospectuses[0]) if prospectuses else None
                    ),
                    "effect_count_same_file_later": len(effects),
                    "resale_prospectus_count_same_file_later": len(prospectuses),
                }
            )

    counts_by_window: dict[str, dict[str, int]] = {}
    for window in ("old_thin", "mid_weak", "late_strong"):
        window_rows = [row for row in output_rows if row["window"] == window]
        counts_by_window[window] = {
            "roster_rows": len(window_rows),
            "registration_found": sum(
                bool(row["registration_found_in_submissions"]) for row in window_rows
            ),
            "file_number_present": sum(bool(row["file_number"]) for row in window_rows),
            "effect_linked": sum(row["effect"] is not None for row in window_rows),
            "official_effect_clock_exact": sum(
                bool((row["official_effect_clock"] or {}).get("effective_at_utc"))
                for row in window_rows
            ),
            "resale_prospectus_linked": sum(
                row["first_resale_prospectus"] is not None for row in window_rows
            ),
            "effect_or_resale_prospectus_linked": sum(
                row["effect"] is not None
                or row["first_resale_prospectus"] is not None
                for row in window_rows
            ),
            "exact_activation_clock": sum(
                bool((row["official_effect_clock"] or {}).get("effective_at_utc"))
                or row["first_resale_prospectus"] is not None
                for row in window_rows
            ),
        }
    aggregate = dict(Counter())
    for values in counts_by_window.values():
        for key, value in values.items():
            aggregate[key] = aggregate.get(key, 0) + value

    payload = {
        "schema_version": 1,
        "record_type": "sec_registration_effectiveness_outcome_blind_linkage",
        "generated_at": date.today().isoformat(),
        "source": "SEC data.sec.gov submissions metadata",
        "join_rule": (
            "exact registration accession -> same CIK and normalized SEC fileNumber "
            "-> earliest later EFFECT and earliest later 424B3/424B4"
        ),
        "outcome_fields_read": [],
        "post_decision_price_values_read": False,
        "trade_enabled": False,
        "roster_path": roster_path.relative_to(REPO_ROOT).as_posix(),
        "roster_sha256": sha256_file(roster_path),
        "economics_path": economics_path.relative_to(REPO_ROOT).as_posix(),
        "economics_sha256": sha256_file(economics_path),
        "unique_ciks": len(by_cik),
        "cache_files": sorted(set(cache_sources)),
        "fetch_failures": fetch_failures,
        "effect_clock_failures": effect_clock_failures,
        "unresolved_source_accessions": unresolved_source,
        "counts_by_window": counts_by_window,
        "aggregate_counts": aggregate,
        "readiness_rule": (
            "A follow-up execution-clock replay may be proposed only if at least "
            "30 rows in every frozen window have an exact official EFFECT clock "
            "or an exact resale-prospectus acceptance clock; "
            "otherwise park without an experiment ID."
        ),
        "readiness_passed": all(
            values["exact_activation_clock"] >= 30
            for values in counts_by_window.values()
        ),
        "rows": output_rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roster", default=str(DEFAULT_ROSTER))
    parser.add_argument("--economics", default=str(DEFAULT_ECONOMICS))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument("--effect-cache-dir", default=str(DEFAULT_EFFECT_CACHE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--delay-seconds", type=float, default=0.12)
    return parser.parse_args()


if __name__ == "__main__":
    result = build(parse_args())
    print(
        json.dumps(
            {
                "output": DEFAULT_OUTPUT.relative_to(REPO_ROOT).as_posix(),
                "unique_ciks": result["unique_ciks"],
                "fetch_failure_count": len(result["fetch_failures"]),
                "counts_by_window": result["counts_by_window"],
                "aggregate_counts": result["aggregate_counts"],
                "readiness_passed": result["readiness_passed"],
            },
            indent=2,
        )
    )
