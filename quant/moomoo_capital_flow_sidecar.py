"""Observe-only moomoo capital-distribution daily sidecar.

Pilots a NEW data dimension the free-data stack lacks: per-ticker institutional
money-flow (super/big/mid/small order in/out) from the moomoo OpenAPI
`get_capital_distribution` endpoint.

IMPORTANT PIT / parity boundary (read before wiring into any decision):
- `capital_distribution` is a CURRENT-SNAPSHOT endpoint. moomoo provides no
  historical daily backfill, so this field can ONLY accumulate forward from the
  first collection date. It can never be replayed on the canonical historical
  windows. Validation is forward-only (months-scale), exactly like the accepted
  default-off paper sleeves.
- This sidecar is observe-only: `trade_enabled=False`, it changes no entry,
  exit, ranking, sizing, or order behavior, and it is NOT wired into run.py.
  It only appends a PIT-stamped daily artifact to build forward history.
- Requires OpenD running + logged in (127.0.0.1:11111). Run after the US close
  so the day's distribution is settled; stamp = collection date.

Promotion path (later, do NOT skip): once enough forward rows accumulate, run a
606-022-style observe-only attribution, then (if it survives an ex-top-ticker
robustness screen) a single frozen Gate 1-4 before any decision uses it.

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

OUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow"
ROWS_PATH = OUT_DIR / "rows.jsonl"
MANIFEST_PATH = OUT_DIR / "manifest.json"

# ETFs / indices: capital distribution is not meaningful (or N/A); skip to keep
# the artifact to single-name institutional flow.
SKIP_TICKERS = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV"}

REQUEST_SLEEP_SEC = 0.5  # stay well under moomoo quote rate limits


def _f(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n == n else None  # drop NaN


def _row_for_ticker(dist: dict[str, Any], *, ticker: str, code: str, as_of: str, collected_at: str) -> dict[str, Any]:
    in_super = _f(dist.get("capital_in_super")) or 0.0
    out_super = _f(dist.get("capital_out_super")) or 0.0
    in_big = _f(dist.get("capital_in_big")) or 0.0
    out_big = _f(dist.get("capital_out_big")) or 0.0
    in_mid = _f(dist.get("capital_in_mid")) or 0.0
    out_mid = _f(dist.get("capital_out_mid")) or 0.0
    in_small = _f(dist.get("capital_in_small")) or 0.0
    out_small = _f(dist.get("capital_out_small")) or 0.0
    net_super = round(in_super - out_super, 2)
    net_big = round(in_big - out_big, 2)
    net_mid = round(in_mid - out_mid, 2)
    net_small = round(in_small - out_small, 2)
    net_main = round(net_super + net_big, 2)  # institutional / main-force net
    net_total = round(net_super + net_big + net_mid + net_small, 2)
    gross_total = in_super + out_super + in_big + out_big + in_mid + out_mid + in_small + out_small
    # normalized main-force pressure in [-1, 1]; the replayable feature
    main_flow_ratio = round(net_main / gross_total, 6) if gross_total > 0 else None
    return {
        "as_of_date": as_of,
        "collected_at_utc": collected_at,
        "ticker": ticker,
        "moomoo_code": code,
        "capital_in_super": round(in_super, 2),
        "capital_out_super": round(out_super, 2),
        "capital_in_big": round(in_big, 2),
        "capital_out_big": round(out_big, 2),
        "capital_in_mid": round(in_mid, 2),
        "capital_out_mid": round(out_mid, 2),
        "capital_in_small": round(in_small, 2),
        "capital_out_small": round(out_small, 2),
        "net_super": net_super,
        "net_big": net_big,
        "net_mid": net_mid,
        "net_small": net_small,
        "net_main": net_main,
        "net_total": net_total,
        "main_flow_ratio": main_flow_ratio,
        "source": "moomoo_openapi_capital_distribution",
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
        # lazy import: broad sleeve pulls heavier deps
        from broad_market_paper_sleeve import load_broad_market_candidate_universe
        payload = load_broad_market_candidate_universe()
        tickers = list(payload.get("tickers") or []) if hasattr(payload, "get") else list(payload)
        return [t for t in sorted(set(tickers)) if t not in SKIP_TICKERS]
    return [t for t in sorted(get_universe()) if t not in SKIP_TICKERS]


def main(broad: bool = False) -> int:
    from moomoo import OpenQuoteContext, RET_OK  # local import: SDK only here

    as_of = date.today().isoformat()
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = _load_existing_keys()

    universe = _resolve_universe(broad)
    rows: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    skipped_dup = 0

    q = OpenQuoteContext(host="127.0.0.1", port=11111)
    try:
        for ticker in universe:
            if (ticker, as_of) in existing:
                skipped_dup += 1
                continue
            code = f"US.{ticker}"
            try:
                ret, data = q.get_capital_distribution(code)
            except Exception as exc:  # noqa: BLE001
                errors[ticker] = f"exception: {exc}"
                time.sleep(REQUEST_SLEEP_SEC)
                continue
            if ret != RET_OK:
                errors[ticker] = str(data)
                # back off a bit harder if it looks like a rate limit
                time.sleep(2.0 if "limit" in str(data).lower() or "frequ" in str(data).lower() else REQUEST_SLEEP_SEC)
                continue
            # get_capital_distribution returns a 1-row DataFrame
            if hasattr(data, "iloc") and len(data) > 0:
                dist = {k: data.iloc[0][k] for k in data.columns}
            elif isinstance(data, dict):
                dist = data
            else:
                errors[ticker] = "unexpected_payload_shape"
                time.sleep(REQUEST_SLEEP_SEC)
                continue
            rows.append(_row_for_ticker(dist, ticker=ticker, code=code, as_of=as_of, collected_at=collected_at))
            time.sleep(REQUEST_SLEEP_SEC)
    finally:
        q.close()

    # Append-only write
    with ROWS_PATH.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")

    total_rows = len(_load_existing_keys())
    manifest = {
        "source": "moomoo_openapi_capital_distribution",
        "endpoint": "get_capital_distribution",
        "schema": "observe_only_forward_accumulation_v1",
        "last_collected_as_of": as_of,
        "last_collected_at_utc": collected_at,
        "rows_appended_this_run": len(rows),
        "rows_skipped_duplicate": skipped_dup,
        "error_count": len(errors),
        "errors_sample": dict(list(errors.items())[:10]),
        "cumulative_rows_total": total_rows,
        "universe_size": len(universe),
        "skipped_tickers": sorted(SKIP_TICKERS),
        "pit_boundary": "current_snapshot_only; forward-only; never backfillable; observe-only; not wired to run.py or any decision",
        "rows_path": str(ROWS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "trade_enabled": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "as_of": as_of,
        "appended": len(rows),
        "skipped_dup": skipped_dup,
        "errors": len(errors),
        "cumulative_total": total_rows,
        "sample_errors": dict(list(errors.items())[:5]),
    }, indent=2))
    # Show a few strongest main-force net rows for a sanity read
    top = sorted(rows, key=lambda r: -(r["net_main"] or 0))[:5]
    bot = sorted(rows, key=lambda r: (r["net_main"] or 0))[:5]
    print("\nStrongest main-force INFLOW today:")
    for r in top:
        print(f"  {r['ticker']:6s} net_main={r['net_main']:>16,.0f}  ratio={r['main_flow_ratio']}")
    print("Strongest main-force OUTFLOW today:")
    for r in bot:
        print(f"  {r['ticker']:6s} net_main={r['net_main']:>16,.0f}  ratio={r['main_flow_ratio']}")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="moomoo capital-distribution observe-only daily sidecar")
    parser.add_argument("--broad", action="store_true",
                        help="collect the ~1230-name broad universe instead of the 49 core names")
    args = parser.parse_args()
    raise SystemExit(main(broad=args.broad))
