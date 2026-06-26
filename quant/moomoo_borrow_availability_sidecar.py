"""Observe-only moomoo borrow-availability / short-financing daily sidecar.

Pilots the data axis the repo's frozen FINRA / options / squeeze families keep
naming as their reopen condition: PIT **borrow fee / loan availability /
shortability**, which raw FINRA short-interest share counts and daily short
volume do NOT provide.

The moomoo `get_market_snapshot` schema exposes, per equity:
  - enable_short_sell          (bool)  shortable right now
  - short_sell_rate            (%)     indicative borrow / short-financing rate
  - short_available_volume     (int)   shares available to borrow (availability)
  - short_margin_initial_ratio (%)     short initial-margin requirement

ENTITLEMENT CAVEAT (read before trusting this archive):
- On 2026-06-24 these four fields returned NaN for both US (AAPL/NVDA/GME) and
  HK (00700/09988) on the current OpenD account, while last_price populated
  normally. So the fields exist in the protocol but are not populated under this
  account's market-data entitlement. This sidecar therefore records, every run,
  how many names came back populated (`borrow_populated`), so the operator can
  see if/when the entitlement starts delivering data. Until `borrow_populated`
  is consistently > 0, this archive is a readiness probe, not a usable surface.

PIT / parity boundary (same wall as moomoo_capital_flow_sidecar):
- `get_market_snapshot` is a CURRENT-SNAPSHOT endpoint. moomoo provides no
  historical borrow-rate backfill, so this field can ONLY accumulate forward
  from the first collection date. It can never be replayed on the canonical
  historical windows. Validation is forward-only (months-scale).
- Observe-only: `trade_enabled=False`. It changes no entry, exit, ranking,
  sizing, or order behavior and is NOT wired into run.py. It only appends a
  PIT-stamped daily artifact to build forward history.
- Requires OpenD running + logged in (127.0.0.1:11111). Run after the US close
  so the day's borrow state is settled; stamp = collection date.

Promotion path (later, do NOT skip): once enough forward rows accumulate AND
`borrow_populated` is reliably non-zero, run an observe-only attribution
(do short_sell_rate / short_available_volume separate forward outcomes?), then
a single frozen Gate 1-4 before any decision uses it. Borrow-rate is the named
reopen key for the FINRA short-interest, options-skew, and squeeze families.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_layer import get_universe  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "borrow_availability"
ROWS_PATH = OUT_DIR / "rows.jsonl"
MANIFEST_PATH = OUT_DIR / "manifest.json"

# Index/commodity ETFs: borrow data is not the intended single-name surface.
SKIP_TICKERS = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV"}

SNAPSHOT_BATCH = 50      # get_market_snapshot accepts a code_list; batch to respect quota
REQUEST_SLEEP_SEC = 0.6  # stay under moomoo snapshot rate limits between batches

# Borrow fields we are piloting plus context fields.
_BORROW_FIELDS = (
    "enable_short_sell",
    "short_sell_rate",
    "short_available_volume",
    "short_margin_initial_ratio",
)


def _f(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n == n else None  # drop NaN


def _b(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    try:
        if value != value:  # NaN
            return None
    except TypeError:
        pass
    s = str(value).strip().lower()
    if s in ("true", "1", "1.0", "yes"):
        return True
    if s in ("false", "0", "0.0", "no"):
        return False
    return None


def _row(rec: dict[str, Any], *, ticker: str, code: str, as_of: str, collected_at: str) -> dict[str, Any]:
    enable_short = _b(rec.get("enable_short_sell"))
    short_rate = _f(rec.get("short_sell_rate"))
    short_avail = _f(rec.get("short_available_volume"))
    short_margin = _f(rec.get("short_margin_initial_ratio"))
    last_price = _f(rec.get("last_price"))
    # A row is "borrow-populated" if any genuine borrow field came back non-null.
    borrow_populated = any(v is not None for v in (enable_short, short_rate, short_avail, short_margin))
    return {
        "as_of_date": as_of,
        "collected_at_utc": collected_at,
        "ticker": ticker,
        "moomoo_code": code,
        "enable_short_sell": enable_short,
        "short_sell_rate_pct": short_rate,
        "short_available_volume": short_avail,
        "short_margin_initial_ratio_pct": short_margin,
        "last_price": last_price,
        "sec_status": (str(rec.get("sec_status")) if rec.get("sec_status") is not None else None),
        "equity_valid": _b(rec.get("equity_valid")),
        "borrow_populated": borrow_populated,
        "source": "moomoo_openapi_market_snapshot",
        "pit_note": "current_snapshot_only_forward_accumulation_no_historical_backfill",
        "trade_enabled": False,
    }


def _load_existing_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if ROWS_PATH.exists():
        for line in ROWS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            keys.add((str(row.get("ticker")), str(row.get("as_of_date"))))
    return keys


def _resolve_universe(broad: bool) -> list[str]:
    if broad:
        from broad_market_paper_sleeve import load_broad_market_candidate_universe
        payload = load_broad_market_candidate_universe()
        tickers = list(payload.get("tickers") or []) if hasattr(payload, "get") else list(payload)
        return [t for t in sorted(set(tickers)) if t not in SKIP_TICKERS]
    return [t for t in sorted(get_universe()) if t not in SKIP_TICKERS]


def _chunks(seq: list[str], n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main(broad: bool = False) -> int:
    from moomoo import OpenQuoteContext, RET_OK  # local import: SDK only here

    as_of = date.today().isoformat()
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = _load_existing_keys()

    universe = [t for t in _resolve_universe(broad) if (t, as_of) not in existing]
    skipped_dup = (len(_resolve_universe(broad))) - len(universe)
    rows: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    q = OpenQuoteContext(host="127.0.0.1", port=11111)
    try:
        for batch in _chunks(universe, SNAPSHOT_BATCH):
            codes = [f"US.{t}" for t in batch]
            try:
                ret, data = q.get_market_snapshot(codes)
            except Exception as exc:  # noqa: BLE001
                for t in batch:
                    errors[t] = f"exception: {exc}"
                time.sleep(REQUEST_SLEEP_SEC)
                continue
            if ret != RET_OK:
                for t in batch:
                    errors[t] = str(data)
                time.sleep(2.0 if "limit" in str(data).lower() or "frequ" in str(data).lower() else REQUEST_SLEEP_SEC)
                continue
            by_code = {}
            if hasattr(data, "iterrows"):
                for _, r in data.iterrows():
                    by_code[str(r.get("code"))] = {k: r[k] for k in data.columns}
            for t, code in zip(batch, codes):
                rec = by_code.get(code)
                if rec is None:
                    errors[t] = "missing_in_snapshot_response"
                    continue
                rows.append(_row(rec, ticker=t, code=code, as_of=as_of, collected_at=collected_at))
            time.sleep(REQUEST_SLEEP_SEC)
    finally:
        q.close()

    with ROWS_PATH.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")

    total_rows = len(_load_existing_keys())
    borrow_populated = sum(1 for r in rows if r["borrow_populated"])
    rates = [r["short_sell_rate_pct"] for r in rows if r["short_sell_rate_pct"] is not None]
    manifest = {
        "source": "moomoo_openapi_market_snapshot",
        "endpoint": "get_market_snapshot",
        "fields_piloted": list(_BORROW_FIELDS),
        "schema": "observe_only_forward_accumulation_v1",
        "last_collected_as_of": as_of,
        "last_collected_at_utc": collected_at,
        "rows_appended_this_run": len(rows),
        "rows_skipped_duplicate": skipped_dup,
        "borrow_populated_this_run": borrow_populated,
        "borrow_populated_pct": (round(100.0 * borrow_populated / len(rows), 2) if rows else None),
        "short_sell_rate_min": (min(rates) if rates else None),
        "short_sell_rate_max": (max(rates) if rates else None),
        "error_count": len(errors),
        "errors_sample": dict(list(errors.items())[:10]),
        "cumulative_rows_total": total_rows,
        "universe_size": len(universe),
        "skipped_tickers": sorted(SKIP_TICKERS),
        "entitlement_caveat": (
            "borrow fields (short_sell_rate/short_available_volume/enable_short_sell/"
            "short_margin_initial_ratio) returned NaN for US+HK on 2026-06-24; this "
            "archive is a readiness probe until borrow_populated_this_run is reliably > 0."
        ),
        "pit_boundary": "current_snapshot_only; forward-only; never backfillable; observe-only; not wired to run.py or any decision",
        "rows_path": str(ROWS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "trade_enabled": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "as_of": as_of,
        "appended": len(rows),
        "borrow_populated_this_run": borrow_populated,
        "borrow_populated_pct": manifest["borrow_populated_pct"],
        "short_sell_rate_min": manifest["short_sell_rate_min"],
        "short_sell_rate_max": manifest["short_sell_rate_max"],
        "errors": len(errors),
        "cumulative_total": total_rows,
        "sample_errors": dict(list(errors.items())[:5]),
    }, indent=2))
    if borrow_populated:
        pop = sorted((r for r in rows if r["short_sell_rate_pct"] is not None),
                     key=lambda r: -(r["short_sell_rate_pct"] or 0))[:8]
        print("\nHighest indicative borrow rate today:")
        for r in pop:
            print(f"  {r['ticker']:6s} rate={r['short_sell_rate_pct']}%  avail={r['short_available_volume']}  shortable={r['enable_short_sell']}")
    else:
        print("\nNo borrow fields populated this run (entitlement gap). Archive seeded as readiness probe.")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="moomoo borrow-availability observe-only daily sidecar")
    parser.add_argument("--broad", action="store_true",
                        help="collect the broad universe instead of the core names")
    args = parser.parse_args()
    raise SystemExit(main(broad=args.broad))
