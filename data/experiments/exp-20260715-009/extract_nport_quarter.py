"""Reproduce one compact SEC N-PORT quarter for exp-20260715-009.

The fixed CUSIP-to-ticker identity surface is recovered from the already
materialized historical compacts.  This intentionally avoids extending the
experiment universe from sparse issuer-provided ticker strings.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path


def _read_json_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json_gz(path: Path, payload) -> None:
    # Pin the gzip header timestamp and embedded filename so rerunning the
    # official quarter extraction is byte-for-byte reproducible.
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")


def _reader(archive: zipfile.ZipFile, member: str):
    raw = archive.open(member)
    text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
    return raw, text, csv.DictReader(text, delimiter="\t")


def _identity_map(compact_dir: Path) -> dict[str, str]:
    pairs: dict[str, set[str]] = defaultdict(set)
    for path in sorted(compact_dir.glob("core_holdings_*.json.gz")):
        for row in _read_json_gz(path):
            pairs[str(row["cusip"]).upper()].add(str(row["ticker"]).upper())
    ambiguous = {cusip: tickers for cusip, tickers in pairs.items() if len(tickers) != 1}
    if ambiguous:
        raise RuntimeError(f"ambiguous frozen identity surface: {ambiguous}")
    return {cusip: next(iter(tickers)) for cusip, tickers in pairs.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("quarter", help="lowercase quarter label, for example 2026q2")
    parser.add_argument("compact_dir", type=Path)
    args = parser.parse_args()

    args.compact_dir.mkdir(parents=True, exist_ok=True)
    identity = _identity_map(args.compact_dir)
    with zipfile.ZipFile(args.zip_path) as archive:
        raw, text, rows = _reader(archive, "SUBMISSION.tsv")
        try:
            submissions = {
                row["ACCESSION_NUMBER"]: {
                    "filing_date": row["FILING_DATE"],
                    "report_date": row["REPORT_DATE"],
                    "sub_type": row["SUB_TYPE"],
                }
                for row in rows
                if row.get("SUB_TYPE") in {"NPORT-P", "NPORT-P/A"}
            }
        finally:
            text.close()
            raw.close()

        raw, text, rows = _reader(archive, "FUND_REPORTED_INFO.tsv")
        try:
            series_by_accession = {
                row["ACCESSION_NUMBER"]: row["SERIES_ID"]
                for row in rows
                if row["ACCESSION_NUMBER"] in submissions and row.get("SERIES_ID")
            }
        finally:
            text.close()
            raw.close()

        grouped: dict[tuple[str, ...], list[float]] = defaultdict(lambda: [0.0, 0.0])
        raw, text, rows = _reader(archive, "FUND_REPORTED_HOLDING.tsv")
        try:
            for row in rows:
                accession = row.get("ACCESSION_NUMBER", "")
                meta = submissions.get(accession)
                series_id = series_by_accession.get(accession)
                cusip = row.get("ISSUER_CUSIP", "").strip().upper()
                ticker = identity.get(cusip)
                if not meta or not series_id or not ticker:
                    continue
                if row.get("UNIT") != "NS" or row.get("ASSET_CAT") != "EC":
                    continue
                if row.get("PAYOFF_PROFILE") != "Long":
                    continue
                try:
                    balance = float(row["BALANCE"])
                    currency_value = float(row["CURRENCY_VALUE"])
                except (KeyError, TypeError, ValueError):
                    continue
                if balance < 0 or currency_value <= 0:
                    continue
                key = (
                    accession,
                    series_id,
                    ticker,
                    cusip,
                    meta["filing_date"],
                    meta["report_date"],
                    meta["sub_type"],
                    row.get("CURRENCY_CODE", ""),
                )
                grouped[key][0] += balance
                grouped[key][1] += currency_value
        finally:
            text.close()
            raw.close()

    holdings = [
        {
            "accession": key[0],
            "series_id": key[1],
            "ticker": key[2],
            "cusip": key[3],
            "filing_date": key[4],
            "report_date": key[5],
            "sub_type": key[6],
            "currency_code": key[7],
            "balance": values[0],
            "currency_value": values[1],
        }
        for key, values in sorted(grouped.items())
    ]
    output = args.compact_dir / f"core_holdings_{args.quarter}.json.gz"
    _write_json_gz(output, holdings)

    reports_path = args.compact_dir / "series_reports.json.gz"
    reports = _read_json_gz(reports_path) if reports_path.exists() else []
    reports = [row for row in reports if row.get("quarter") != args.quarter]
    reports.extend(
        {
            "accession": accession,
            "series_id": series_id,
            "filing_date": submissions[accession]["filing_date"],
            "report_date": submissions[accession]["report_date"],
            "sub_type": submissions[accession]["sub_type"],
            "quarter": args.quarter,
        }
        for accession, series_id in series_by_accession.items()
    )
    reports.sort(key=lambda row: (row["filing_date"], row["accession"], row["series_id"]))
    _write_json_gz(reports_path, reports)
    print(json.dumps({
        "quarter": args.quarter,
        "identity_pairs": len(identity),
        "holding_rows": len(holdings),
        "series_reports_total": len(reports),
        "output": str(output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
