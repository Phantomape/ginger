"""Issuer-name CUSIP->ticker mapping for SEC 13F holdings, scoped to a universe.

exp-20260613-007: SEC Form 13F identifies securities by CUSIP, not ticker, and
the repo has no licensed CUSIP map. This module builds a free CUSIP->ticker map
by matching each 13F holding's ``name_of_issuer`` against the company names in
``sec_company_tickers.json``, restricted to a caller-supplied universe so the
match space stays small and the false-positive surface is bounded.

The match is name-normalization + exact lookup (no fuzzy scoring): corporate
suffixes and share-class qualifiers are stripped, so "APPLE INC" and
"APPLE INC." collapse to the same key. This is deliberately conservative — a
normalized exact hit or nothing — because a wrong ticker is worse than an
unmapped holding for downstream joins.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

try:
    from data_paths import data_artifact_path
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant.data_paths import data_artifact_path


# Tokens dropped during normalization: legal suffixes, share-class and unit
# qualifiers, and filler words that vary between EDGAR issuer names and the
# company_tickers titles without changing identity.
_DROP_TOKENS = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "COMPANIES",
    "LTD", "LIMITED", "LLC", "LP", "PLC", "NV", "SA", "AG", "THE", "COM",
    "HLDG", "HLDGS", "HOLDING", "HOLDINGS", "GROUP", "GRP", "TR", "TRUST",
    "NEW", "CLASS", "CL", "SER", "SERIES", "SH", "SHS", "SHARES", "ADR", "ADS",
    "ORD", "ORDINARY", "COMMON", "STK", "STOCK", "UNIT", "UNITS", "PAR",
    "A", "B", "C",
}

_NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")
_WS = re.compile(r"\s+")


def normalize_issuer_name(name: Any) -> str:
    """Collapse an issuer/company name to a normalized match key."""
    text = _NON_ALNUM.sub(" ", str(name or "").upper())
    tokens = [tok for tok in _WS.sub(" ", text).split(" ") if tok and tok not in _DROP_TOKENS]
    return " ".join(tokens)


def load_company_name_index(
    company_tickers_path: Path | str | None = None,
) -> dict[str, str]:
    """Return ``{normalized_company_name: ticker}`` from the SEC ticker map.

    On a normalized-name collision (two tickers share a normalized name), the
    first ticker seen wins and the rest are dropped, so an ambiguous name maps
    to nothing rather than to an arbitrary ticker.
    """
    path = Path(company_tickers_path) if company_tickers_path else data_artifact_path("sec_company_tickers")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.values() if isinstance(payload, dict) else payload
    index: dict[str, str] = {}
    collisions: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        ticker = str(record.get("ticker") or "").upper().strip()
        key = normalize_issuer_name(record.get("title"))
        if not ticker or not key:
            continue
        if key in index and index[key] != ticker:
            collisions.add(key)
            continue
        index.setdefault(key, ticker)
    for key in collisions:
        index.pop(key, None)
    return index


def build_cusip_ticker_map(
    holding_rows: Iterable[dict[str, Any]],
    *,
    name_index: dict[str, str],
    universe: set[str] | None = None,
) -> dict[str, str]:
    """Build ``{cusip: ticker}`` from 13F rows via normalized issuer-name match.

    Each 13F row carries both ``cusip`` and ``name_of_issuer``; matching the
    name to the company index yields the ticker for that CUSIP. When the same
    CUSIP resolves to conflicting tickers across rows it is dropped. If
    ``universe`` is given, only CUSIPs whose ticker is in the universe are kept.
    """
    allowed = {str(t).upper() for t in universe} if universe is not None else None
    mapping: dict[str, str] = {}
    conflicts: set[str] = set()
    for row in holding_rows:
        cusip = str(row.get("cusip") or "").upper().replace(" ", "")
        if not cusip or cusip in conflicts:
            continue
        ticker = name_index.get(normalize_issuer_name(row.get("name_of_issuer")))
        if not ticker:
            continue
        if allowed is not None and ticker not in allowed:
            continue
        existing = mapping.get(cusip)
        if existing and existing != ticker:
            conflicts.add(cusip)
            mapping.pop(cusip, None)
            continue
        mapping.setdefault(cusip, ticker)
    return mapping
