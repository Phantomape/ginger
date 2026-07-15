"""Shared default-off FDA 510(k) clearance paper-sleeve policy.

The FDA says cleared 510(k)s are added to its public database weekly, but the
historical endpoint does not expose a per-record publication timestamp.  This
helper therefore never treats ``decision_date`` as immediately tradable.  It
uses a predeclared two-week availability envelope and enters only at the first
regular-session open strictly after that envelope.

The helper is deliberately default-off.  It cannot place orders, alter the
core candidate pool, or change ranking/sizing/exits.  Applicant mapping is a
normalized *exact* whitelist; substring matching is intentionally forbidden.
"""

from __future__ import annotations

import hashlib
import gzip
import json
import math
import re
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


RULE_VERSION = "fda_510k_traditional_clearance_14d_nextopen_10d_v1"
OFFICIAL_API_URL = "https://api.fda.gov/device/510k.json"
BASE_NOTIONAL_USD = 4_000.0
ROUND_TRIP_COST_PCT = 0.0035
AVAILABILITY_LAG_CALENDAR_DAYS = 14
HOLD_DAYS = 10
SAME_TICKER_COOLDOWN_SESSIONS = 10
TRADE_ENABLED = False


# These are sponsor strings observed on the official FDA rows and manually
# bound to an already-public parent.  Ambiguous substring collisions (for
# example VitalConnect/Alcon, Change Healthcare/GE Healthcare, Merge
# Healthcare/GE Healthcare, and Fresenius Kabi/Fresenius Medical Care) are
# intentionally absent.  3M is excluded because the 2024 SOLV separation
# makes issuer attribution product-dependent.
APPLICANT_ALIASES: dict[str, tuple[str, ...]] = {
    "ABT": (
        "Abbott",
        "Abbott Diagnostics Scarborough, Inc.",
        "Abbott Ireland",
        "Abbott Laboratories",
        "ABBOTT MEDICAL",
        "Abbott Molecular",
        "Abbott Molecular, Inc.",
        "Abbott Point of Care, Inc.",
    ),
    "ALC": ("Alcon Laboratories, Inc.",),
    "ATRC": ("AtriCure, Inc.",),
    "BDX": (
        "Bard Peripheral Vascular, Inc.",
        "Bd Integrated Diagnostic Solutions/Becton,",
        "Becton Dickinson",
        "Becton Dickinson Inc. (Bd)",
        "Becton Dickinson Infusion Therapy Systems, Inc.",
        "Becton, Dickinson and Company",
        "C.R. Bard, Inc.",
        "Davol, Inc., A Subsidiary of C.R. Bard, Inc.",
    ),
    "BSX": (
        "Boston Scientific",
        "Boston Scientific Cardiac Diagnostic Technologies, Inc.",
        "Boston Scientific Corporation",
        "Boston Scientific Neuromodulation Corporation",
    ),
    "CNMD": ("Conmed Corporation",),
    "DHR": ("Beckman Coulter, Inc.", "Cepheid", "Cepheid®"),
    "DXCM": ("Dexcom, Inc.",),
    "EW": ("Edwards Lifesciences", "Edwards Lifesciences, LLC"),
    "FMS": (
        "Fresenius Medical Care North America",
        "Fresenius Medical Care Renal Therapies Group, LLC",
    ),
    "GEHC": ("GE Healthcare", "Ge Healthcare Japan Corporation"),
    "GMED": ("Globus Medical, Inc.",),
    "HOLX": ("Hologic", "Hologic, Inc."),
    "ICUI": ("Icu Medical, Inc.",),
    "ISRG": ("Intuitive Surgical, Inc.",),
    "JNJ": (
        "Depuy Ireland UC",
        "Depuy Mitek",
        "DePuy Mitek, Inc.",
        "Depuy Orthopedics, Inc.",
    ),
    "KIDS": (
        "Orthopediatrics Canada Ulc Dba Pega Medical",
        "OrthoPediatrics Corp.",
    ),
    "MASI": ("Masimo Corporation",),
    "MDT": (
        "Covidien (Part of Medtronic)",
        "Medicrea International S.A.S. (Medtronic)",
        "Medtronic Minimed",
        "Medtronic Minimed, Inc.",
        "Medtronic Navigation",
        "Medtronic Navigation, Inc.",
        "Medtronic Neurosurgery",
        "Medtronic Sofamor Danek USA, Inc.",
        "Medtronic Sofamor Danek, Inc.",
        "Medtronic Xomed, Inc.",
        "Medtronic, Inc.",
        "Medtronic, Ireland",
    ),
    "MMSI": ("Merit Medical Ireland, Ltd.", "Merit Medical Systems, Inc."),
    "PEN": ("Penumbra, Inc.",),
    "PHG": (
        "Philips Consumer Lifestyle B.V.",
        "Philips DS North America, LLC",
        "Philips France Commercial",
        "Philips Healthcare (Suzhou) Co., Ltd.",
        "Philips Image Guided Therapy Corporation",
        "Philips Image Guided Therapy Devices",
        "Philips Medical Systems B.V.",
        "Philips Medical Systems Nederland B.V.",
        "Philips Medical Systems Technologies , Ltd.",
        "Philips Medizin Systeme Boeblingen GmbH",
        "Philips Medizin Systeme Böblingen GmbH",
        "Philips Ultrasound",
        "Philips Ultrasound, LLC",
    ),
    "PODD": ("Insulet Corporation",),
    "QGEN": ("QIAGEN GmbH",),
    "RMD": (
        "Resmed Corp",
        "Resmed Pty , Ltd.",
        "Resmed Pty Ltd (Registration Number: 3004604967)",
    ),
    "SNN": (
        "Smith & Nephew",
        "Smith & Nephew Inc., Endoscopy Div.",
        "Smith & Nephew Medical Limited",
        "Smith & Nephew Medical, Ltd.",
        "Smith & Nephew, Inc.",
    ),
    "STE": ("Steris", "STERIS Corporation"),
    "SYK": (
        "Howmedica Osteonics Corp (Dba Stryker Orthopaedics)",
        "Howmedica Osteonics Corp., Dba Stryker Orthopaedics",
        "Stryker Corporation (Tornier, Inc.)",
        "Stryker Corporation (Tornier, S.A.S.)",
        "Stryker Endoscopy",
        "Stryker GmbH",
        "Stryker Instruments",
        "Stryker Leibinger GmbH & Co KG",
        "Stryker Neurovascular",
        "Stryker Spine",
        "Stryker Sustainability Solutions",
        "Wright Medical Technology, Inc. (Stryker Corporation)",
        "Wright Medical Technology, Inc. (Stryker)",
    ),
    "TMO": ("Thermo Fisher Scientific", "Thermo Fisher Scientific (Oxoid Ltd.)"),
    "TNDM": ("Tandem Diabetes Care, Inc.",),
    "XRAY": ("Dentsply Sirona", "Dentsply Sirona, Inc."),
    "ZBH": (
        "Orthosoft Inc. (d/b/a) Zimmer CAS",
        "Zimmer Biomet",
        "Zimmer Medizinsysteme GmbH",
        "Zimmer, Inc.",
    ),
}


def _normalise_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).strip().upper()
    return re.sub(r"\s+", " ", text)


def _build_applicant_map() -> dict[str, str]:
    output: dict[str, str] = {}
    for ticker, aliases in APPLICANT_ALIASES.items():
        for alias in aliases:
            key = _normalise_name(alias)
            prior = output.get(key)
            if prior is not None and prior != ticker:
                raise RuntimeError(
                    f"FDA 510(k) applicant alias collision: {key} -> {prior}/{ticker}"
                )
            output[key] = ticker
    return output


APPLICANT_TO_TICKER = _build_applicant_map()


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


def _parse_date(value: Any) -> date:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{8}", raw):
        return datetime.strptime(raw, "%Y%m%d").date()
    return date.fromisoformat(raw[:10])


def _iso(value: Any) -> str:
    return _parse_date(value).isoformat()


def normalise_fda_510k_clearance_events(
    rows: Iterable[dict[str, Any]], *, require_provenance: bool = False
) -> list[dict[str, Any]]:
    """Map official Traditional rows through the exact issuer whitelist."""
    by_k_number: dict[str, dict[str, Any]] = {}
    for source in rows:
        row = dict(source)
        if str(row.get("clearance_type") or "").strip().lower() != "traditional":
            continue
        applicant = str(row.get("applicant") or "").strip()
        ticker = APPLICANT_TO_TICKER.get(_normalise_name(applicant))
        if not ticker:
            continue
        k_number = str(row.get("k_number") or "").strip().upper()
        if not k_number:
            continue
        decision_date = _iso(row.get("decision_date"))
        public_as_of = (
            _parse_date(decision_date)
            + timedelta(days=AVAILABILITY_LAG_CALENDAR_DAYS)
        ).isoformat()
        provenance = row.get("source_record_sha256") or _sha(row)
        if require_provenance and not provenance:
            raise ValueError(f"missing source provenance for {k_number}")
        event = {
            "event_id": k_number,
            "k_number": k_number,
            "ticker": ticker,
            "applicant": applicant,
            "device_name": str(row.get("device_name") or "").strip(),
            "product_code": str(row.get("product_code") or "").strip(),
            "decision_date": decision_date,
            "public_as_of": public_as_of,
            "availability_lag_calendar_days": AVAILABILITY_LAG_CALENDAR_DAYS,
            "clearance_type": "Traditional",
            "decision_description": str(
                row.get("decision_description") or ""
            ).strip(),
            "source_record_sha256": str(provenance),
            "rule_version": RULE_VERSION,
            "trade_enabled": False,
            "alters_orders": False,
        }
        prior = by_k_number.get(k_number)
        if prior and _canonical_json(prior) != _canonical_json(event):
            raise ValueError(f"conflicting FDA 510(k) row for {k_number}")
        by_k_number[k_number] = event
    return sorted(
        by_k_number.values(),
        key=lambda row: (row["decision_date"], row["ticker"], row["k_number"]),
    )


def save_fda_510k_clearance_archive(
    path: str | Path,
    events: Iterable[dict[str, Any]],
    *,
    raw_payload_manifest_sha256: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    destination = Path(path)
    normalized = normalise_fda_510k_clearance_events(
        (dict(row) for row in events), require_provenance=True
    )
    payload = {
        "schema": "fda_510k_clearance_archive_v1",
        "rule_version": RULE_VERSION,
        "generated_at": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "official_api_url": OFFICIAL_API_URL,
        "availability_contract": (
            "decision_date plus 14 calendar days; first later regular-session open"
        ),
        "raw_payload_manifest_sha256": raw_payload_manifest_sha256,
        "event_count": len(normalized),
        "ticker_count": len({row["ticker"] for row in normalized}),
        "events_sha256": _sha(normalized),
        "events": normalized,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def load_fda_510k_clearance_archive(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if payload.get("schema") != "fda_510k_clearance_archive_v1":
        raise ValueError("unsupported FDA 510(k) archive schema")
    events = normalise_fda_510k_clearance_events(
        payload.get("events") or [], require_provenance=True
    )
    if payload.get("events_sha256") != _sha(events):
        raise ValueError("FDA 510(k) archive hash mismatch")
    if payload.get("event_count") != len(events):
        raise ValueError("FDA 510(k) archive event count mismatch")
    return events


def refresh_fda_510k_clearance_archive(
    path: str | Path,
    *,
    start: str,
    end: str,
    timeout: float = 30.0,
    archive_payload_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Fetch, freeze, hash, normalize, and save official API pages."""
    raw_dir = Path(archive_payload_dir) if archive_payload_dir else None
    if raw_dir:
        raw_dir.mkdir(parents=True, exist_ok=True)
    start_api = _parse_date(start).strftime("%Y%m%d")
    end_api = _parse_date(end).strftime("%Y%m%d")
    all_rows: list[dict[str, Any]] = []
    manifest_pages: list[dict[str, Any]] = []
    skip = 0
    total: int | None = None
    while total is None or skip < total:
        query = urllib.parse.urlencode(
            {
                "search": (
                    f'decision_date:[{start_api} TO {end_api}] '
                    'AND clearance_type:"Traditional"'
                ),
                "limit": 1000,
                "skip": skip,
            }
        )
        url = f"{OFFICIAL_API_URL}?{query}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "ginger-research/1.0 (FDA 510k archive)"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        payload = json.loads(raw.decode("utf-8"))
        results = list(payload.get("results") or [])
        total = int(((payload.get("meta") or {}).get("results") or {}).get("total", 0))
        page_sha = hashlib.sha256(raw).hexdigest()
        page_row = {
            "skip": skip,
            "record_count": len(results),
            "sha256": page_sha,
            "url": url,
        }
        if raw_dir:
            page_path = raw_dir / f"openfda_510k_{skip:05d}.json.gz"
            compressed = gzip.compress(raw, compresslevel=9, mtime=0)
            page_path.write_bytes(compressed)
            page_row["path"] = page_path.name
            page_row["archive_sha256"] = hashlib.sha256(compressed).hexdigest()
            page_row["compression"] = "gzip"
        manifest_pages.append(page_row)
        all_rows.extend(results)
        if not results:
            break
        skip += len(results)
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "schema": "fda_510k_raw_api_manifest_v1",
        "retrieved_at": retrieved_at,
        "start": _iso(start),
        "end": _iso(end),
        "raw_record_count": len(all_rows),
        "pages": manifest_pages,
    }
    manifest_sha = _sha(manifest)
    if raw_dir:
        manifest_path = raw_dir / "openfda_fetch_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    events = normalise_fda_510k_clearance_events(all_rows)
    save_fda_510k_clearance_archive(
        path,
        events,
        raw_payload_manifest_sha256=manifest_sha,
        generated_at=retrieved_at,
    )
    return events


def verify_fda_510k_raw_manifest(
    archive_payload_dir: str | Path,
) -> dict[str, Any]:
    """Verify every frozen compressed API page and its uncompressed hash."""
    raw_dir = Path(archive_payload_dir)
    manifest_path = raw_dir / "openfda_fetch_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    verified: list[dict[str, Any]] = []
    for page in manifest.get("pages") or []:
        path = raw_dir / str(page["path"])
        archived = path.read_bytes()
        if hashlib.sha256(archived).hexdigest() != page.get("archive_sha256"):
            raise ValueError(f"FDA 510(k) compressed page hash mismatch: {path.name}")
        raw = gzip.decompress(archived)
        if hashlib.sha256(raw).hexdigest() != page.get("sha256"):
            raise ValueError(f"FDA 510(k) raw page hash mismatch: {path.name}")
        payload = json.loads(raw.decode("utf-8"))
        if len(payload.get("results") or []) != page.get("record_count"):
            raise ValueError(f"FDA 510(k) raw page row-count mismatch: {path.name}")
        verified.append(
            {
                "path": path.name,
                "sha256": page["sha256"],
                "archive_sha256": page["archive_sha256"],
                "record_count": page["record_count"],
            }
        )
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha(manifest),
        "raw_record_count": manifest.get("raw_record_count"),
        "page_count": len(verified),
        "pages": verified,
    }


def _normalise_bars(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        day = _iso(row.get("date") or row.get("Date"))
        values: dict[str, float] = {}
        valid = True
        for key in ("open", "high", "low", "close"):
            raw = row.get(key) if key in row else row.get(key.title())
            try:
                value = float(raw)
            except (TypeError, ValueError):
                valid = False
                break
            if not math.isfinite(value) or value <= 0:
                valid = False
                break
            values[key] = value
        if valid:
            output.append({"date": day, **values})
    return sorted(output, key=lambda row: row["date"])


def _atr_target(rows: list[dict[str, Any]], signal_idx: int, entry: float) -> float:
    start = max(0, signal_idx - 13)
    true_ranges: list[float] = []
    for idx in range(start, signal_idx + 1):
        row = rows[idx]
        prior_close = rows[idx - 1]["close"] if idx else row["close"]
        true_ranges.append(
            max(
                row["high"] - row["low"],
                abs(row["high"] - prior_close),
                abs(row["low"] - prior_close),
            )
        )
    atr = sum(true_ranges) / len(true_ranges) if true_ranges else entry * 0.02
    return round(entry + 3.5 * atr, 4)


def replay_fda_510k_clearance_paper_trades(
    *,
    events: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    start: str,
    end: str,
) -> dict[str, Any]:
    event_rows = normalise_fda_510k_clearance_events(
        (dict(row) for row in events), require_provenance=True
    )
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    start_iso, end_iso = _iso(start), _iso(end)
    # Multiple K-numbers for one issuer on one decision date express one
    # issuer-level catalyst.  The lexicographically first K-number is the
    # deterministic representative; no event-content ranking is introduced.
    issuer_days: dict[tuple[str, str], dict[str, Any]] = {}
    for row in event_rows:
        key = (row["ticker"], row["decision_date"])
        prior = issuer_days.get(key)
        if prior is None or row["k_number"] < prior["k_number"]:
            issuer_days[key] = row

    rejects: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    next_allowed: dict[str, int] = {}
    for candidate in sorted(
        issuer_days.values(),
        key=lambda row: (row["public_as_of"], row["ticker"], row["k_number"]),
    ):
        ticker = candidate["ticker"]
        rows = bars.get(ticker) or []
        if not rows:
            rejects["missing_ticker_bars"] += 1
            continue
        entry_idx = next(
            (idx for idx, row in enumerate(rows) if row["date"] > candidate["public_as_of"]),
            None,
        )
        if entry_idx is None or rows[entry_idx]["date"] < start_iso:
            rejects["outside_entry_window"] += 1
            continue
        if rows[entry_idx]["date"] > end_iso:
            rejects["outside_entry_window"] += 1
            continue
        if entry_idx < next_allowed.get(ticker, -1):
            rejects["same_ticker_cooldown"] += 1
            continue
        selected.append({**candidate, "signal_date": candidate["public_as_of"]})
        next_allowed[ticker] = entry_idx + SAME_TICKER_COOLDOWN_SESSIONS
        exit_idx = entry_idx + HOLD_DAYS - 1
        if exit_idx >= len(rows) or rows[exit_idx]["date"] > end_iso:
            unsettled.append(
                {**candidate, "unsettled_reason": "incomplete_10_session_horizon"}
            )
            continue
        entry_price = rows[entry_idx]["open"]
        exit_price = rows[exit_idx]["close"]
        signal_idx = max(0, entry_idx - 1)
        net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        trades.append(
            {
                **candidate,
                "signal_date": candidate["public_as_of"],
                "entry_date": rows[entry_idx]["date"],
                "exit_date": rows[exit_idx]["date"],
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "target_price": _atr_target(rows, signal_idx, entry_price),
                "hold_days": HOLD_DAYS,
                "hold_sessions_realized": HOLD_DAYS,
                "exit_reason": "scheduled_10_session_horizon_close",
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "pnl_pct_net": round(net_return, 10),
                "pnl": round(BASE_NOTIONAL_USD * net_return, 2),
            }
        )
    generated = sum(
        start_iso <= row["public_as_of"] <= end_iso for row in issuer_days.values()
    )
    survived = sum(
        start_iso <= row["entry_date"] <= end_iso for row in trades
    ) + len(unsettled)
    return {
        "trades": trades,
        "unsettled": unsettled,
        "selected_candidates": selected,
        "reject_totals": dict(sorted(rejects.items())),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else 0.0,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
    }


def build_fda_510k_clearance_paper_snapshot(
    *,
    events: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    as_of: str,
    lookback_calendar_days: int = 120,
) -> dict[str, Any]:
    end = _parse_date(as_of)
    replay = replay_fda_510k_clearance_paper_trades(
        events=events,
        ohlcv_by_ticker=ohlcv_by_ticker,
        start=(end - timedelta(days=lookback_calendar_days)).isoformat(),
        end=end.isoformat(),
    )
    return {
        "schema": "fda_510k_clearance_default_off_snapshot_v1",
        "as_of": end.isoformat(),
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "alters_orders": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "candidate_count": len(replay["selected_candidates"]),
        "closed_trade_count": len(replay["trades"]),
        "unsettled_count": len(replay["unsettled"]),
        "replay": replay,
    }


__all__ = [
    "APPLICANT_ALIASES",
    "APPLICANT_TO_TICKER",
    "AVAILABILITY_LAG_CALENDAR_DAYS",
    "BASE_NOTIONAL_USD",
    "HOLD_DAYS",
    "OFFICIAL_API_URL",
    "ROUND_TRIP_COST_PCT",
    "RULE_VERSION",
    "SAME_TICKER_COOLDOWN_SESSIONS",
    "build_fda_510k_clearance_paper_snapshot",
    "load_fda_510k_clearance_archive",
    "normalise_fda_510k_clearance_events",
    "refresh_fda_510k_clearance_archive",
    "replay_fda_510k_clearance_paper_trades",
    "save_fda_510k_clearance_archive",
    "verify_fda_510k_raw_manifest",
]
