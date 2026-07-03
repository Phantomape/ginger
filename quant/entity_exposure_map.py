"""Entity -> listed-ticker exposure map v1 for corporate-event propagation.

Experiment: exp-20260702-009 (measurement_repair, alpha-enabling map build).

Design (docs/alpha_next_direction_20260701.md, direction 0):
- slow layer: a versioned, reviewable static map; the LLM's job is offline
  curation of the THEME overlay below, never a hot-path per-event call;
- deterministic layers: entity CIK -> SIC industry code (SEC submissions
  JSON) and SIC -> listed peers (locally cached listed-company submissions);
- fast layer: `map_event_to_exposures` joins a corporate-event row (from
  `sec_corporate_event_stream`) against the map with zero network and zero
  LLM calls, so historical replay is fully replayable.

PIT caveat (recorded in the artifact): SIC comes from the CURRENT submissions
JSON, not an as-of-filing snapshot. SIC reclassification is rare over this
horizon, but rows carry `sic_as_of` so a later PIT repair can supersede it.

No trading behavior change. Exposure rows are observation evidence for a
separately gated propagation alpha experiment.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from data_paths import atomic_write_json
from sec_submissions import fetch_submission
from sec_ticker_map import normalize_cik

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUT_DIR = DATA_DIR / "non_ohlcv" / "entity_exposure_map"
DEFAULT_EVENT_ROWS = (
    DATA_DIR / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
DEFAULT_SUBMISSIONS_CACHE = DATA_DIR / "cache" / "sec" / "submissions"
DEFAULT_USER_AGENT = "ginger-research phantomape93@gmail.com"

SCHEMA_VERSION = "entity_exposure_map_v1"
BLANK_CHECK_SIC = "6770"

# ---------------------------------------------------------------------------
# Theme overlay v1 — LLM-curated, versioned, reviewable.
#
# Curation rules:
# - a theme exists only when SIC alone cannot express it (e.g. "space" spans
#   3760/3812/4899/3721) or when name keywords carry signal SIC misses;
# - `listed_peers` are candidates; build-time validation keeps only tickers
#   present in the local listed-company submissions cache and records drops;
# - keywords are matched as case-insensitive word fragments against entity
#   names and SIC descriptions. Keep them specific enough to avoid collisions
#   (e.g. "bitcoin mining", not "mining").
# - edges carry NO direction claim. Whether a fresh IPO in a theme is
#   bullish attention or bearish supply for peers is the alpha question, and
#   it belongs to the separately gated experiment.
# ---------------------------------------------------------------------------
THEME_OVERLAY_VERSION = "theme_overlay_v1_20260702"
THEME_OVERLAY: list[dict[str, Any]] = [
    {
        "theme": "space_launch_satellites",
        "sic_codes": ["3760"],
        "name_keywords": [
            "space", "satellite", "orbital", "launch", "rocket", "lunar",
            "aerospace",
        ],
        "listed_peers": ["RKLB", "ASTS", "LUNR", "SPCE", "RDW", "PL", "BKSY"],
    },
    {
        "theme": "semiconductors_ai_hardware",
        "sic_codes": ["3674", "3559"],
        "name_keywords": ["semiconductor", "chip", "foundry", "photonics"],
        "listed_peers": [
            "NVDA", "AMD", "AVGO", "MU", "ARM", "SMCI", "MRVL", "INTC",
            "QCOM", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC",
        ],
    },
    {
        "theme": "ai_software_platforms",
        "sic_codes": [],
        "name_keywords": [
            "artificial intelligence", " ai ", "machine learning",
            "generative",
        ],
        "listed_peers": ["PLTR", "MSFT", "GOOGL", "META", "NOW", "AI"],
    },
    {
        "theme": "crypto_digital_assets",
        "sic_codes": [],
        "name_keywords": [
            "crypto", "bitcoin", "blockchain", "digital asset", "stablecoin",
            "bitcoin mining", "web3", "token",
        ],
        "listed_peers": ["COIN", "MSTR", "HOOD", "MARA", "RIOT", "CLSK", "GLXY"],
    },
    {
        "theme": "ev_battery",
        "sic_codes": ["3711"],
        "name_keywords": ["electric vehicle", "battery", "lithium", " ev "],
        "listed_peers": ["TSLA", "RIVN", "LCID", "ALB", "GM", "F"],
    },
    {
        "theme": "biotech_pharma",
        "sic_codes": ["2836", "2834"],
        "name_keywords": [
            "therapeutics", "biosciences", "pharmaceutical", "oncology",
            "biotech", "biopharma", "medicines",
        ],
        "listed_peers": [
            "MRNA", "LLY", "PFE", "AMGN", "REGN", "VRTX", "GILD", "BMY",
        ],
    },
    {
        "theme": "defense_primes_and_drones",
        "sic_codes": ["3480", "3724", "3812"],
        "name_keywords": ["defense", "munitions", "drone", "unmanned"],
        "listed_peers": ["LMT", "RTX", "NOC", "GD", "KTOS", "AVAV", "LHX"],
    },
    {
        "theme": "fintech_payments",
        "sic_codes": ["6141", "6199"],
        "name_keywords": [
            "fintech", "payments", "lending platform", "neobank",
        ],
        "listed_peers": ["SOFI", "PYPL", "XYZ", "V", "MA", "HOOD", "AFRM"],
    },
    {
        "theme": "cybersecurity",
        "sic_codes": [],
        "name_keywords": ["cyber", "security software", "threat"],
        "listed_peers": ["CRWD", "PANW", "ZS", "NET", "FTNT", "S", "OKTA"],
    },
    {
        "theme": "quantum_computing",
        "sic_codes": [],
        "name_keywords": ["quantum"],
        "listed_peers": ["IONQ", "RGTI", "QBTS"],
    },
    {
        "theme": "nuclear_uranium",
        "sic_codes": [],
        "name_keywords": ["nuclear", "uranium", "reactor", "fission"],
        "listed_peers": ["CCJ", "OKLO", "SMR", "LEU", "UEC", "CEG", "VST"],
    },
    {
        "theme": "solar_clean_energy",
        "sic_codes": [],
        "name_keywords": ["solar", "renewable", "geothermal", "hydrogen"],
        "listed_peers": ["FSLR", "ENPH", "RUN", "NEE", "PLUG", "BE"],
    },
    {
        "theme": "evtol_air_mobility",
        "sic_codes": ["3721"],
        "name_keywords": ["evtol", "air taxi", "air mobility", "aviation"],
        "listed_peers": ["JOBY", "ACHR", "BA"],
    },
    {
        "theme": "cloud_saas_data",
        "sic_codes": ["7372"],
        "name_keywords": ["cloud", "software-as-a-service", "saas", "data platform"],
        "listed_peers": ["SNOW", "NET", "DDOG", "MDB", "CRM", "ORCL"],
    },
    {
        "theme": "streaming_media",
        "sic_codes": [],
        "name_keywords": ["streaming", "entertainment platform"],
        "listed_peers": ["NFLX", "DIS", "ROKU", "SPOT", "WBD"],
    },
    {
        "theme": "ecommerce_marketplaces",
        "sic_codes": [],
        "name_keywords": ["marketplace", "e-commerce", "ecommerce"],
        "listed_peers": ["AMZN", "SHOP", "MELI", "ETSY", "EBAY"],
    },
    {
        "theme": "data_center_power_cooling",
        "sic_codes": [],
        "name_keywords": ["data center", "datacenter", "colocation"],
        "listed_peers": ["VRT", "DLR", "EQIX", "ANET", "CEG", "VST"],
    },
    {
        "theme": "weight_loss_glp1",
        "sic_codes": [],
        "name_keywords": ["obesity", "metabolic", "glp-1", "weight"],
        "listed_peers": ["LLY", "NVO", "HIMS", "VKTX"],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Entity enrichment (deterministic layer 1: CIK -> SIC)
# ---------------------------------------------------------------------------


def fetch_entity_record(
    cik: str,
    *,
    cache_dir: Path | str | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    sleep_seconds: float = 0.12,
) -> dict[str, Any]:
    """Fetch one entity submissions payload with backoff; never raises on 404."""
    cik_norm = normalize_cik(cik)
    if not cik_norm:
        return {"cik": cik, "fetch_status": "invalid_cik"}
    last_error = "unknown"
    for attempt in range(5):
        try:
            payload = fetch_submission(
                cik_norm,
                cache_dir=cache_dir,
                user_agent=user_agent,
                sleep_seconds=sleep_seconds,
            )
            tickers = [
                str(t).upper() for t in (payload.get("tickers") or []) if t
            ]
            return {
                "cik": cik_norm,
                "fetch_status": "ok",
                "name": payload.get("name"),
                "sic": str(payload.get("sic") or "") or None,
                "sic_description": payload.get("sicDescription") or None,
                "tickers": tickers,
                "is_blank_check": str(payload.get("sic") or "") == BLANK_CHECK_SIC,
                "sic_as_of": utc_now()[:10],
            }
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"cik": cik_norm, "fetch_status": "not_found"}
            last_error = f"http_{exc.code}"
            if exc.code in (403, 429, 500, 502, 503) and attempt < 4:
                time.sleep(10.0 * (attempt + 1))
                continue
            return {"cik": cik_norm, "fetch_status": last_error}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = f"error_{type(exc).__name__}"
            if attempt < 4:
                time.sleep(5.0 * (attempt + 1))
                continue
    return {"cik": cik_norm, "fetch_status": last_error}


def enrich_entities(
    ciks: Iterable[str],
    *,
    cache_dir: Path | str | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    progress_every: int = 200,
) -> list[dict[str, Any]]:
    unique = sorted({normalize_cik(c) for c in ciks if normalize_cik(c)})
    records = []
    for idx, cik in enumerate(unique):
        records.append(
            fetch_entity_record(cik, cache_dir=cache_dir, user_agent=user_agent)
        )
        if progress_every and (idx + 1) % progress_every == 0:
            print(f"enriched {idx + 1}/{len(unique)} entities", flush=True)
    return records


# ---------------------------------------------------------------------------
# Listed-side index (deterministic layer 2: SIC -> listed peers)
# ---------------------------------------------------------------------------


def build_sic_peer_index(
    cache_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Scan cached submissions for listed companies and index them by SIC."""
    base = Path(cache_dir) if cache_dir else DEFAULT_SUBMISSIONS_CACHE
    by_sic: dict[str, list[dict[str, str]]] = {}
    listed_tickers: set[str] = set()
    scanned = 0
    for path in sorted(base.glob("CIK*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        scanned += 1
        tickers = [str(t).upper() for t in (payload.get("tickers") or []) if t]
        sic = str(payload.get("sic") or "")
        if not tickers or not sic:
            continue
        ticker = tickers[0]
        listed_tickers.add(ticker)
        by_sic.setdefault(sic, []).append(
            {
                "ticker": ticker,
                "cik": normalize_cik(payload.get("cik")) or "",
                "name": payload.get("name") or "",
                "sic_description": payload.get("sicDescription") or "",
            }
        )
    for peers in by_sic.values():
        peers.sort(key=lambda p: p["ticker"])
    return {
        "schema_version": SCHEMA_VERSION,
        "scanned_submissions": scanned,
        "listed_tickers": sorted(listed_tickers),
        "by_sic": dict(sorted(by_sic.items())),
    }


def validate_theme_overlay(
    overlay: list[dict[str, Any]], listed_tickers: set[str]
) -> dict[str, Any]:
    """Keep only peers that exist in the local listed set; record drops."""
    themes = []
    dropped: dict[str, list[str]] = {}
    for entry in overlay:
        kept = [t for t in entry["listed_peers"] if t in listed_tickers]
        gone = [t for t in entry["listed_peers"] if t not in listed_tickers]
        if gone:
            dropped[entry["theme"]] = gone
        themes.append({**entry, "listed_peers": kept})
    return {
        "schema_version": SCHEMA_VERSION,
        "overlay_version": THEME_OVERLAY_VERSION,
        "themes": themes,
        "dropped_unlisted_peers": dropped,
    }


# ---------------------------------------------------------------------------
# Fast layer: deterministic event -> exposure join
# ---------------------------------------------------------------------------


def _keyword_hit(text: str, keyword: str) -> bool:
    padded = f" {text.lower()} "
    needle = keyword.lower()
    if needle.startswith(" ") or needle.endswith(" "):
        return needle in padded
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(needle), padded))


def classify_entity_themes(
    name: str | None,
    sic: str | None,
    sic_description: str | None,
    overlay_themes: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Return [{theme, match_basis}] for an entity, deterministic."""
    hits = []
    text = " ".join(part for part in (name, sic_description) if part)
    for entry in overlay_themes:
        if sic and sic in entry["sic_codes"]:
            hits.append({"theme": entry["theme"], "match_basis": f"sic:{sic}"})
            continue
        for keyword in entry["name_keywords"]:
            if text and _keyword_hit(text, keyword):
                hits.append(
                    {"theme": entry["theme"], "match_basis": f"keyword:{keyword}"}
                )
                break
    return hits


def map_event_to_exposures(
    event: dict[str, Any],
    entity: dict[str, Any] | None,
    sic_index: dict[str, Any],
    overlay: dict[str, Any],
    *,
    max_sic_peers: int = 30,
) -> list[dict[str, Any]]:
    """Join one corporate-event row to listed-ticker exposure candidates.

    Deterministic, offline, direction-free: edge rows describe WHO is exposed
    and WHY (sic_peer / theme_peer), never which way prices should move.
    """
    entity = entity or {}
    name = entity.get("name") or event.get("company_name")
    sic = entity.get("sic")
    sic_desc = entity.get("sic_description")
    exposures: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    if entity.get("is_blank_check"):
        return []

    if sic:
        for peer in (sic_index.get("by_sic") or {}).get(sic, [])[:max_sic_peers]:
            key = (peer["ticker"], "sic_peer")
            if key in seen:
                continue
            seen.add(key)
            exposures.append(
                {
                    "event_accession": event.get("accession"),
                    "event_class": event.get("event_class"),
                    "filed_date": event.get("filed_date"),
                    "primary_entity_cik": event.get("cik"),
                    "primary_entity_name": name,
                    "ticker": peer["ticker"],
                    "relation_type": "sic_peer",
                    "match_basis": f"sic:{sic}",
                    "theme": None,
                    "overlay_version": overlay.get("overlay_version"),
                }
            )
    for hit in classify_entity_themes(
        name, sic, sic_desc, overlay.get("themes") or []
    ):
        theme_entry = next(
            (t for t in overlay["themes"] if t["theme"] == hit["theme"]), None
        )
        if theme_entry is None:
            continue
        for ticker in theme_entry["listed_peers"]:
            key = (ticker, "theme_peer")
            if key in seen:
                continue
            seen.add(key)
            exposures.append(
                {
                    "event_accession": event.get("accession"),
                    "event_class": event.get("event_class"),
                    "filed_date": event.get("filed_date"),
                    "primary_entity_cik": event.get("cik"),
                    "primary_entity_name": name,
                    "ticker": ticker,
                    "relation_type": "theme_peer",
                    "match_basis": hit["match_basis"],
                    "theme": hit["theme"],
                    "overlay_version": overlay.get("overlay_version"),
                }
            )
    return exposures


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------


def build_map(
    *,
    event_rows_path: Path | str | None = None,
    out_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    skip_fetch: bool = False,
) -> dict[str, Any]:
    rows_path = Path(event_rows_path) if event_rows_path else DEFAULT_EVENT_ROWS
    out_base = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    out_base.mkdir(parents=True, exist_ok=True)

    events = []
    with rows_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    ipo_ciks = sorted(
        {e["cik"] for e in events if e["event_class"] == "ipo_registration" and e["cik"]}
    )

    entities_path = out_base / "entities.jsonl"
    if skip_fetch and entities_path.exists():
        entities = [
            json.loads(l)
            for l in entities_path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
    else:
        entities = enrich_entities(
            ipo_ciks, cache_dir=cache_dir, user_agent=user_agent
        )
        with entities_path.open("w", encoding="utf-8") as handle:
            for record in entities:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    sic_index = build_sic_peer_index(cache_dir)
    atomic_write_json(sic_index, out_base / "sic_peer_index.json")

    overlay = validate_theme_overlay(
        THEME_OVERLAY, set(sic_index["listed_tickers"])
    )
    atomic_write_json(overlay, out_base / "theme_overlay.json")

    ok = [e for e in entities if e.get("fetch_status") == "ok"]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "overlay_version": THEME_OVERLAY_VERSION,
        "built_at_utc": utc_now(),
        "event_rows": len(events),
        "ipo_entity_ciks": len(ipo_ciks),
        "entities_fetched_ok": len(ok),
        "entities_with_sic": sum(1 for e in ok if e.get("sic")),
        "blank_check_entities": sum(1 for e in ok if e.get("is_blank_check")),
        "listed_tickers_indexed": len(sic_index["listed_tickers"]),
        "sic_buckets": len(sic_index["by_sic"]),
        "themes": len(overlay["themes"]),
        "dropped_unlisted_peers": overlay["dropped_unlisted_peers"],
        "pit_note": (
            "sic is the CURRENT submissions classification (sic_as_of per "
            "entity row), not an as-of-filing snapshot"
        ),
    }
    atomic_write_json(summary, out_base / "manifest.json")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--event-rows", default=None)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse an existing entities.jsonl instead of fetching.",
    )
    args = parser.parse_args(argv)
    summary = build_map(
        event_rows_path=args.event_rows,
        out_dir=args.out_dir,
        cache_dir=args.cache_dir,
        user_agent=args.user_agent,
        skip_fetch=args.skip_fetch,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
