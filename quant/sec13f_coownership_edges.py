"""SEC 13F co-ownership network peer edges (Anton-Polk "Connected Stocks").

The aggregate ingest in ``sec13f_ingest.py`` collapses 13F rows to per-ticker
``holder_count`` and DISCARDS holder identity, so the manager->ticker bipartite
graph needed for a co-ownership peer network is not persisted. This module
re-parses the cached quarterly window zips, keeps the
``manager_cik -> set(ticker)`` edges, and projects them into a co-ownership peer
map: for each universe ticker, the peers most often co-held by the SAME
institutions.

Design choices (the relation, not a momentum relabel):
- Only universe-mapped holdings count (issuer-name -> ticker via the shared
  ``sec13f_universe_map`` index), identical to ``aggregate_universe_holdings``.
- A manager contributes co-ownership edges only when it holds between
  ``manager_min_holdings`` and ``manager_max_holdings`` universe names. This
  drops mega-diversified index funds (whose co-holding is uninformative and
  whose pair count would explode) and one-name filers, keeping concentrated
  active managers whose overlap is the Anton-Polk signal.
- Peer strength is the shared-manager COUNT plus a Jaccard score; both are kept
  so downstream code can threshold either way.

Data-only: no signals, orders, ranking, sizing, or exits. Reads the cached
zips written by ``sec13f_ingest.py`` and writes
``data/non_ohlcv/sec13f_institutional/coownership_edges_<window>.json``.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

try:
    from data_paths import atomic_write_json, data_artifact_path
    from kova_data_sidecar import parse_sec13f_zip
    from sec13f_universe_map import load_company_name_index, normalize_issuer_name
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant.data_paths import atomic_write_json, data_artifact_path
    from quant.kova_data_sidecar import parse_sec13f_zip
    from quant.sec13f_universe_map import load_company_name_index, normalize_issuer_name


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec13f_institutional"
DEFAULT_CACHE_DIR = DEFAULT_DIR / "source_cache"
RULE_VERSION = "sec13f_coownership_network_v1"

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def window_end_date(window_label: str) -> date:
    """Parse the filing-window end date from a label like 01jun2024-31aug2024."""
    end = window_label.split("-", 1)[1]
    day = int(end[:2])
    month = _MONTHS[end[2:5].lower()]
    year = int(end[5:9])
    return date(year, month, day)


def manager_ticker_edges(
    holding_rows: Iterable[dict[str, Any]],
    *,
    name_index: dict[str, str],
    universe: set[str],
) -> dict[str, set[str]]:
    """Build ``manager_cik -> set(universe ticker)`` from parsed 13F rows."""
    allowed = {str(t).upper() for t in universe}
    edges: dict[str, set[str]] = defaultdict(set)
    for row in holding_rows:
        ticker = name_index.get(normalize_issuer_name(row.get("name_of_issuer")))
        if not ticker or ticker not in allowed:
            continue
        manager = str(row.get("manager_cik") or row.get("manager_name") or "").strip()
        if not manager:
            continue
        edges[manager].add(ticker)
    return edges


def coownership_peers(
    manager_edges: dict[str, set[str]],
    *,
    manager_min_holdings: int = 5,
    manager_max_holdings: int = 100,
    top_k: int = 15,
    min_shared_managers: int = 30,
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    """Project manager->tickers edges into a per-ticker co-ownership peer map.

    Returns ``(peers_by_ticker, contributing_manager_count)``.
    """
    shared: dict[tuple[str, str], int] = defaultdict(int)
    holders: dict[str, int] = defaultdict(int)
    contributing_managers = 0
    for tickers in manager_edges.values():
        n = len(tickers)
        if n < manager_min_holdings or n > manager_max_holdings:
            continue
        contributing_managers += 1
        for t in tickers:
            holders[t] += 1
        for a, b in combinations(sorted(tickers), 2):
            shared[(a, b)] += 1

    peers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total = max(contributing_managers, 1)
    for (a, b), count in shared.items():
        if count < min_shared_managers:
            continue
        union = holders[a] + holders[b] - count
        jaccard = round(count / union, 6) if union else 0.0
        # Lift over independence: co-holding beyond each name's marginal
        # popularity. >1 = genuinely connected; ~1 = both just widely held.
        expected = holders[a] * holders[b] / total
        lift = round(count / expected, 6) if expected else 0.0
        edge = {"peer": None, "shared_managers": count, "jaccard": jaccard, "lift": lift}
        peers[a].append({**edge, "peer": b})
        peers[b].append({**edge, "peer": a})

    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in peers.items():
        # Rank by lift (the genuine connected-stocks signal), require enough
        # shared managers for the lift to be statistically meaningful.
        rows.sort(key=lambda r: (-r["lift"], -r["shared_managers"], r["peer"]))
        out[ticker] = rows[:top_k]
    return out, contributing_managers


def build_window_edges(
    window_label: str,
    *,
    universe: set[str],
    name_index: dict[str, str] | None = None,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    out_dir: Path | str = DEFAULT_DIR,
    manager_min_holdings: int = 5,
    manager_max_holdings: int = 100,
    top_k: int = 15,
    min_shared_managers: int = 30,
    persist: bool = True,
) -> dict[str, Any]:
    cache_root = Path(cache_dir)
    zip_path = cache_root / f"{window_label}_form13f.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"missing cached 13F zip: {zip_path}")
    idx = name_index if name_index is not None else load_company_name_index()
    asof = window_end_date(window_label).isoformat()
    rows = parse_sec13f_zip(zip_path, asof_date=asof, cusip_ticker_map=None)
    manager_edges = manager_ticker_edges(rows, name_index=idx, universe=universe)
    peer_map, contributing = coownership_peers(
        manager_edges,
        manager_min_holdings=manager_min_holdings,
        manager_max_holdings=manager_max_holdings,
        top_k=top_k,
        min_shared_managers=min_shared_managers,
    )
    payload = {
        "rule_version": RULE_VERSION,
        "window_label": window_label,
        "window_end_date": asof,
        "universe_size": len(universe),
        "managers_total": len(manager_edges),
        "managers_contributing": contributing,
        "tickers_with_peers": len(peer_map),
        "params": {
            "manager_min_holdings": manager_min_holdings,
            "manager_max_holdings": manager_max_holdings,
            "top_k": top_k,
            "min_shared_managers": min_shared_managers,
        },
        "peers_by_ticker": {t: peer_map[t] for t in sorted(peer_map)},
    }
    if persist:
        out_path = Path(out_dir) / f"coownership_edges_{window_label}.json"
        atomic_write_json(payload, out_path)
        payload["output_path"] = str(out_path)
    return payload


def discover_window_labels(cache_dir: Path | str = DEFAULT_CACHE_DIR) -> list[str]:
    cache_root = Path(cache_dir)
    labels = [p.name[: -len("_form13f.zip")] for p in cache_root.glob("*_form13f.zip")]
    return sorted(labels, key=window_end_date)


def latest_label_for(
    as_of: str | date, labels: Iterable[str]
) -> str | None:
    """PIT resolver: newest window whose filing-window end <= as_of."""
    asof = as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of)[:10])
    eligible = [lab for lab in labels if window_end_date(lab) <= asof]
    if not eligible:
        return None
    return max(eligible, key=window_end_date)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build SEC 13F co-ownership peer edges.")
    parser.add_argument("--universe", default=None, help="Path to universe.json; default broad-market feed.")
    parser.add_argument("--window", default=None, help="Single window label; default all cached windows.")
    parser.add_argument("--sample-ticker", default=None, help="Print the peer list for this ticker after build.")
    args = parser.parse_args()

    if args.universe:
        uni = json.loads(Path(args.universe).read_text(encoding="utf-8"))
    else:
        uni = json.loads(Path(data_artifact_path("broad_market_paper_universe")).read_text(encoding="utf-8"))
    tickers = uni.get("tickers") if isinstance(uni, dict) else uni
    universe = {str(t).upper() for t in (tickers or [])}

    name_index = load_company_name_index()
    labels = [args.window] if args.window else discover_window_labels()
    summary = []
    for label in labels:
        payload = build_window_edges(label, universe=universe, name_index=name_index)
        line = {
            "window_label": label,
            "managers_contributing": payload["managers_contributing"],
            "tickers_with_peers": payload["tickers_with_peers"],
        }
        if args.sample_ticker:
            line["sample"] = payload["peers_by_ticker"].get(args.sample_ticker.upper(), [])[:8]
        summary.append(line)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
