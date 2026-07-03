"""Second-order exposure observations for structured news events.

Experiment: exp-20260702-020 (measurement_repair, alpha-enabling surface).

For every qualified structured news event (daily_news_structured_event_ledger
rows, both polarities, all relation types) on a first-order ticker, record
observation rows for that ticker's SECOND-ORDER exposure set:

- sic_peer: listed companies sharing the first-order ticker's SIC code
  (entity_exposure_map sic_peer_index, deterministic, capped);
- theme_peer: listed peers of every theme whose curated basket contains the
  first-order ticker (entity_exposure_map theme overlay).

Rows use the same forward semantics as the first-order news observation
contract: entry at the next warehouse session OPEN strictly after event_date,
5d/10d close SPY-excess settlement. Direction is recorded (event polarity),
never predeclared: whether second-order names inherit, invert, or ignore the
first-order impact is the question for a later, separately gated read.

Ledger (append-only, dedup by (event_id, exposure_ticker)):
  data/non_ohlcv/news_event_exposure_observations/rows.jsonl
  data/non_ohlcv/news_event_exposure_observations/manifest.json

No trading behavior change.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from data_paths import atomic_write_json
from ohlcv_warehouse import load_warehouse_ohlcv_frames

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUT_DIR = DATA_DIR / "non_ohlcv" / "news_event_exposure_observations"
MAP_DIR = DATA_DIR / "non_ohlcv" / "entity_exposure_map"
COLD_DB = DATA_DIR / "warehouse" / "warehouse_main.sqlite"
HOT_DB = DATA_DIR / "warehouse" / "warehouse_main_hot.sqlite"
STRUCTURED_DAILY_DIR = DATA_DIR / "daily" / "news" / "structured"

SCHEMA_VERSION = "news_event_exposure_observation_v1"
MAX_SIC_PEERS = 15
HORIZONS = (5, 10)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_exposure_map(
    map_dir: Path | str | None = None,
) -> dict[str, Any]:
    base = Path(map_dir) if map_dir else MAP_DIR
    sic_index = json.loads((base / "sic_peer_index.json").read_text(encoding="utf-8"))
    overlay = json.loads((base / "theme_overlay.json").read_text(encoding="utf-8"))
    ticker_sic: dict[str, str] = {}
    for sic, peers in (sic_index.get("by_sic") or {}).items():
        for peer in peers:
            ticker_sic[peer["ticker"]] = sic
    ticker_themes: dict[str, list[str]] = {}
    for entry in overlay.get("themes") or []:
        for ticker in entry["listed_peers"]:
            ticker_themes.setdefault(ticker, []).append(entry["theme"])
    return {
        "sic_index": sic_index,
        "overlay": overlay,
        "ticker_sic": ticker_sic,
        "ticker_themes": ticker_themes,
    }


def exposure_set_for_ticker(
    ticker: str,
    exposure_map: Mapping[str, Any],
    *,
    max_sic_peers: int = MAX_SIC_PEERS,
) -> list[dict[str, str]]:
    """Deterministic second-order exposure edges for a first-order ticker."""
    ticker = ticker.upper()
    edges: list[dict[str, str]] = []
    seen: set[str] = {ticker}
    sic = exposure_map["ticker_sic"].get(ticker)
    if sic:
        peers = (exposure_map["sic_index"].get("by_sic") or {}).get(sic, [])
        for peer in peers[:max_sic_peers]:
            if peer["ticker"] in seen:
                continue
            seen.add(peer["ticker"])
            edges.append(
                {
                    "exposure_ticker": peer["ticker"],
                    "relation_type": "sic_peer",
                    "match_basis": f"sic:{sic}",
                    "theme": None,
                }
            )
    for theme in exposure_map["ticker_themes"].get(ticker, []):
        entry = next(
            t for t in exposure_map["overlay"]["themes"] if t["theme"] == theme
        )
        for peer in entry["listed_peers"]:
            if peer in seen:
                continue
            seen.add(peer)
            edges.append(
                {
                    "exposure_ticker": peer,
                    "relation_type": "theme_peer",
                    "match_basis": f"theme_membership:{theme}",
                    "theme": theme,
                }
            )
    return edges


def build_exposure_rows(
    event_rows: Iterable[Mapping[str, Any]],
    exposure_map: Mapping[str, Any],
    *,
    max_sic_peers: int = MAX_SIC_PEERS,
) -> list[dict[str, Any]]:
    rows = []
    for event in event_rows:
        ticker = str(event.get("ticker") or "").upper()
        event_id = event.get("event_id")
        event_date = event.get("event_date")
        if not ticker or not event_id or not event_date:
            continue
        for edge in exposure_set_for_ticker(
            ticker, exposure_map, max_sic_peers=max_sic_peers
        ):
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "event_id": event_id,
                    "event_date": event_date,
                    "published_at": event.get("published_at"),
                    "first_order_ticker": ticker,
                    "exposure_ticker": edge["exposure_ticker"],
                    "relation_type": edge["relation_type"],
                    "match_basis": edge["match_basis"],
                    "theme": edge["theme"],
                    "event_relation_type": event.get("relation_type"),
                    "event_polarity": event.get("relation_polarity"),
                    "event_rule_version": event.get("rule_version"),
                    "entry_semantics": "next_session_open_after_event_date",
                    "exit_semantics": "5d_and_10d_close_spy_excess",
                    "entry_date": None,
                    "excess_5d": None,
                    "excess_10d": None,
                    "outcome_status": "pending_forward_close",
                }
            )
    return rows


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("event_id")), str(row.get("exposure_ticker")))


def load_ledger(rows_path: Path) -> list[dict[str, Any]]:
    rows = []
    if not rows_path.exists():
        return rows
    with rows_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def merge_rows(
    existing: list[dict[str, Any]], fresh: Iterable[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    keys = {_row_key(r) for r in existing}
    appended = 0
    merged = list(existing)
    for row in fresh:
        key = _row_key(row)
        if key in keys:
            continue
        keys.add(key)
        merged.append(row)
        appended += 1
    return merged, appended


def load_frames(tickers: set[str]) -> dict[str, pd.DataFrame]:
    cold = load_warehouse_ohlcv_frames(COLD_DB, tickers, "2025-12-01", "2026-12-31")
    hot = {}
    if HOT_DB.exists():
        hot = load_warehouse_ohlcv_frames(HOT_DB, tickers, "2025-12-01", "2026-12-31")
    frames = {}
    for ticker in tickers:
        parts = [f for f in (cold.get(ticker), hot.get(ticker)) if f is not None]
        if not parts:
            continue
        merged = pd.concat(parts)
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        frames[ticker] = merged
    return frames


def _excess(
    frame: pd.DataFrame, spy: pd.DataFrame, entry: pd.Timestamp, horizon: int
) -> float | None:
    if entry not in frame.index or entry not in spy.index:
        return None
    pos = frame.index.get_loc(entry)
    spos = spy.index.get_loc(entry)
    epos, sepos = pos + horizon - 1, spos + horizon - 1
    if epos >= len(frame.index) or sepos >= len(spy.index):
        return None
    if frame.index[epos] != spy.index[sepos]:
        return None
    entry_open = float(frame.iloc[pos]["Open"])
    spy_open = float(spy.iloc[spos]["Open"])
    if entry_open <= 0 or spy_open <= 0:
        return None
    return (float(frame.iloc[epos]["Close"]) / entry_open - 1.0) - (
        float(spy.iloc[sepos]["Close"]) / spy_open - 1.0
    )


def settle_rows(
    rows: list[dict[str, Any]],
    frames: Mapping[str, pd.DataFrame] | None = None,
) -> dict[str, int]:
    pending = [r for r in rows if r["outcome_status"] == "pending_forward_close"]
    if frames is None:
        tickers = {r["exposure_ticker"] for r in pending} | {"SPY"}
        frames = load_frames(tickers)
    spy = frames.get("SPY")
    counts = {"settled": 0, "still_pending": 0, "no_frame": 0}
    if spy is None:
        counts["still_pending"] = len(pending)
        return counts
    for row in pending:
        frame = frames.get(row["exposure_ticker"])
        if frame is None:
            counts["no_frame"] += 1
            continue
        after = frame.index[frame.index > pd.Timestamp(row["event_date"])]
        if not len(after):
            counts["still_pending"] += 1
            continue
        entry = after[0]
        ex10 = _excess(frame, spy, entry, 10)
        if ex10 is None:
            counts["still_pending"] += 1
            continue
        ex5 = _excess(frame, spy, entry, 5)
        row["entry_date"] = str(entry.date())
        row["excess_5d"] = round(ex5, 6) if ex5 is not None else None
        row["excess_10d"] = round(ex10, 6)
        row["outcome_status"] = "closed"
        counts["settled"] += 1
    return counts


def write_ledger(
    rows: list[dict[str, Any]],
    *,
    out_dir: Path | str | None = None,
    extra_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    base.mkdir(parents=True, exist_ok=True)
    rows_path = base / "rows.jsonl"
    ordered = sorted(
        rows, key=lambda r: (r.get("event_date") or "", str(_row_key(r)))
    )
    tmp = "\n".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) for r in ordered
    )
    from data_paths import atomic_write_text

    atomic_write_text(tmp + "\n", rows_path)
    closed = [r for r in ordered if r["outcome_status"] == "closed"]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "rows": len(ordered),
        "closed_rows": len(closed),
        "pending_rows": len(ordered) - len(closed),
        "event_ids": len({r["event_id"] for r in ordered}),
        "first_order_tickers": len({r["first_order_ticker"] for r in ordered}),
        "exposure_tickers": len({r["exposure_ticker"] for r in ordered}),
        "max_sic_peers": MAX_SIC_PEERS,
        "last_run_utc": utc_now(),
    }
    if extra_manifest:
        manifest.update(dict(extra_manifest))
    atomic_write_json(manifest, base / "manifest.json")
    return manifest


def collect_structured_event_rows(
    *,
    replay_files: Iterable[Path | str] = (),
    daily_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Load structured event rows from replay JSONL files + daily artifacts."""
    events: list[dict[str, Any]] = []
    for path in replay_files:
        path = Path(path)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
    base = Path(daily_dir) if daily_dir else STRUCTURED_DAILY_DIR
    for path in sorted(base.glob("daily_news_structured_events_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        events.extend(payload.get("rows") or [])
    seen: set[str] = set()
    unique = []
    for event in events:
        eid = str(event.get("event_id"))
        if eid in seen:
            continue
        seen.add(eid)
        unique.append(event)
    return unique


def run(
    *,
    replay_files: Iterable[Path | str] = (),
    out_dir: Path | str | None = None,
    map_dir: Path | str | None = None,
    daily_dir: Path | str | None = None,
    frames: Mapping[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    exposure_map = load_exposure_map(map_dir)
    events = collect_structured_event_rows(
        replay_files=replay_files, daily_dir=daily_dir
    )
    fresh = build_exposure_rows(events, exposure_map)
    base = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    existing = load_ledger(base / "rows.jsonl")
    merged, appended = merge_rows(existing, fresh)
    settle_counts = settle_rows(merged, frames)
    manifest = write_ledger(
        merged,
        out_dir=base,
        extra_manifest={
            "source_events": len(events),
            "appended_this_run": appended,
            "settle_counts": settle_counts,
        },
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--replay-file",
        action="append",
        default=[],
        help="Historical structured event JSONL file(s) to replay.",
    )
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--map-dir", default=None)
    args = parser.parse_args(argv)
    manifest = run(replay_files=args.replay_file, out_dir=args.out_dir, map_dir=args.map_dir)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
