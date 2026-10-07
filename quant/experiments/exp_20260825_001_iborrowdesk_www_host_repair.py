"""exp-20260825-001: iBorrowDesk apex->www host fault recovery evidence capture.

The upstream site moved to www.iborrowdesk.com and the apex host now drops
/api requests with empty replies, so every daily archive refresh has aborted
with RemoteDisconnected since ~2026-07-21 and the PIT borrow archive froze.
This runner captures the measurement surface before and after repointing
``iborrowdesk_data_source.API_URL`` at the www host:

- fetch_state last_refresh_summary and per-ticker status distribution;
- newest last_success_utc across the archive;
- latest archived daily date for the pair forward-readiness short-side
  tickers that were blocked as stale_pit_borrow on 2026-08-25;
- a live probe of the apex and www /api/ticker/GM endpoints.

Usage:
    python -B quant/experiments/exp_20260825_001_iborrowdesk_www_host_repair.py before
    python -B quant/experiments/exp_20260825_001_iborrowdesk_www_host_repair.py after
"""
from __future__ import annotations

import collections
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))

import iborrowdesk_data_source as ibd  # noqa: E402
from data_paths import atomic_write_json  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260825-001"

# Short-side tickers blocked as stale_pit_borrow in the 2026-08-25 pair
# forward-readiness batch (record pair-ready-75e6dd99d4f8538811ac72ab).
STALE_SHORT_SIDE = ["ALB", "F", "FSS", "GM", "HMC", "LCID", "LI", "OSK", "PCAR", "RIVN"]


def _probe(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": ibd.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return f"http_{response.status}"
    except urllib.error.HTTPError as error:
        return f"http_{error.code}"
    except Exception as error:  # noqa: BLE001 - evidence capture only
        return type(error).__name__


def capture(phase: str) -> dict:
    state = ibd.load_fetch_state()
    per_ticker = state.get("tickers") or {}
    status_counts = collections.Counter(
        str((meta or {}).get("status")) for meta in per_ticker.values()
    )
    last_success = [
        meta.get("last_success_utc")
        for meta in per_ticker.values()
        if meta and meta.get("last_success_utc")
    ]
    short_side_latest_date = {}
    for ticker in STALE_SHORT_SIDE:
        history = ibd.load_history(ticker)
        rows = history.get("rows") or {}
        short_side_latest_date[ticker] = max(rows) if rows else None
    return {
        "experiment_id": "exp-20260825-001",
        "phase": phase,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "api_url": ibd.API_URL,
        "last_refresh_summary": state.get("last_refresh_summary"),
        "status_counts": dict(status_counts),
        "max_last_success_utc": max(last_success) if last_success else None,
        "stale_short_side_latest_archived_date": short_side_latest_date,
        "probe": {
            "apex_api": _probe("https://iborrowdesk.com/api/ticker/GM"),
            "www_api": _probe("https://www.iborrowdesk.com/api/ticker/GM"),
        },
    }


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "before"
    if phase not in ("before", "after"):
        raise SystemExit("phase must be 'before' or 'after'")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = capture(phase)
    out_path = OUT_DIR / f"iborrowdesk_www_host_repair_{phase}.json"
    atomic_write_json(snapshot, out_path)
    print(json.dumps(snapshot, indent=2)[:2000])
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
