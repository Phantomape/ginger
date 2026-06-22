"""One-off probe: does moomoo `get_daily_short_volume` meet our backfill bar?

Observe-only. Connects to a running OpenD (127.0.0.1:11111, like the rest of the
moomoo sidecars), pulls the US daily short-volume series for a handful of liquid
tickers, paginates all the way back, and reports per ticker:
  - row count, earliest/latest date, and whether the history reaches our oldest
    standard backtest window start (2024-10-02) and the 2024-01-01 stretch goal.

Why: the agent shortlist flagged daily short volume as the best PIT-safe,
backfillable, NOT-already-owned moomoo source (and it lands in our highest-yield
candidate-pool source family, finra_short_interest). But that was read from docs,
not the live API. Before reserving any experiment we must confirm (a) US coverage
and (b) that the history actually reaches 2024 on the live feed. This script
answers exactly that and writes a JSON artifact; it wires nothing into run.py and
changes no decision path.

Requires: OpenD running + logged in. Run after the US close. Rate limit is
30 req / 30s, so we sleep between page requests.

No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# Oldest standard backtest window start (docs/backtesting.md old_thin) and a
# stretch goal. A source that cannot reach OLDEST_WINDOW_START is unusable for
# historical replay on the canonical windows.
OLDEST_WINDOW_START = "2024-10-02"
STRETCH_START = "2024-01-01"

# Representative liquid US names spanning mega/large/mid cap. Override with
# --tickers. Kept small to respect the rate limit during a probe.
DEFAULT_TICKERS = [
    "US.AAPL", "US.NVDA", "US.TSLA", "US.PLTR", "US.SOFI",
]

PAGE_NUM = 50  # max per page (range 1-50) -> fewest requests
REQUEST_SLEEP_SEC = 1.1  # stay under 30 req / 30s
MAX_PAGES = 80  # 80 * 50 = 4000 daily rows ~ 15 trading years; a safety cap


def _connect(port: int):
    from moomoo import OpenQuoteContext  # local import: SDK only here

    return OpenQuoteContext(host="127.0.0.1", port=port)


def _records(df) -> list[dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    return df.to_dict("records")


def probe_ticker(ctx, code: str) -> dict[str, Any]:
    from moomoo import RET_OK

    dates: list[str] = []
    rows = 0
    pages = 0
    next_key = None
    error = None
    try:
        while pages < MAX_PAGES:
            kwargs = {"num": PAGE_NUM}
            if next_key not in (None, "", "-1"):
                kwargs["next_key"] = next_key
            ret, us_df, hk_df = ctx.get_daily_short_volume(code, **kwargs)
            if ret != RET_OK:
                error = str(us_df)  # on error the 2nd value is the message
                break
            recs = _records(us_df)
            rows += len(recs)
            for r in recs:
                ts = r.get("timestamp_str") or r.get("timestamp")
                if ts:
                    dates.append(str(ts)[:10])
            pages += 1
            nk = ""
            if us_df is not None and hasattr(us_df, "attrs"):
                nk = us_df.attrs.get("next_key", "")
            if not nk or nk == "-1":
                break
            next_key = nk
            time.sleep(REQUEST_SLEEP_SEC)
    except Exception as e:  # noqa: BLE001 - probe must not crash the batch
        error = f"{type(e).__name__}: {e}"

    earliest = min(dates) if dates else None
    latest = max(dates) if dates else None
    return {
        "code": code,
        "rows": rows,
        "pages": pages,
        "earliest": earliest,
        "latest": latest,
        "reaches_oldest_window": bool(earliest and earliest <= OLDEST_WINDOW_START),
        "reaches_2024_stretch": bool(earliest and earliest <= STRETCH_START),
        "hit_page_cap": pages >= MAX_PAGES,
        "error": error,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=11111)
    ap.add_argument(
        "--tickers",
        default="",
        help="Comma-separated codes (e.g. US.AAPL,US.NVDA). Defaults to a built-in liquid set.",
    )
    ap.add_argument("--out", default="", help="Output JSON path. Defaults under data/probes/.")
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] or DEFAULT_TICKERS

    try:
        ctx = _connect(args.port)
    except Exception as e:  # noqa: BLE001
        print(
            f"ERROR: could not connect to OpenD on 127.0.0.1:{args.port} ({e}).\n"
            "Is OpenD running and logged in? Run after the US close.",
            file=sys.stderr,
        )
        return 2

    out_path = Path(args.out) if args.out else (
        REPO_ROOT / "data" / "probes" / f"moomoo_daily_short_volume_probe_{date.today().isoformat()}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _flush(rows):
        # Write a partial artifact after every ticker so a kill/timeout still
        # leaves whatever was probed so far.
        out_path.write_text(
            json.dumps({"partial": True, "stamp": date.today().isoformat(), "results": rows},
                       indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    results = []
    try:
        for code in tickers:
            res = probe_ticker(ctx, code)
            results.append(res)
            flag = "OK" if res["reaches_oldest_window"] else ("PARTIAL" if res["rows"] else "EMPTY")
            print(
                f"[{flag:7s}] {code:10s} rows={res['rows']:5d} "
                f"range={res['earliest']}..{res['latest']} "
                f"reaches_2024_window={res['reaches_oldest_window']} "
                f"err={res['error']}",
                flush=True,
            )
            _flush(results)
            time.sleep(REQUEST_SLEEP_SEC)
    finally:
        try:
            ctx.close()
        except Exception:
            pass

    n = len(results)
    n_cov = sum(1 for r in results if r["rows"] > 0)
    n_window = sum(1 for r in results if r["reaches_oldest_window"])
    n_stretch = sum(1 for r in results if r["reaches_2024_stretch"])
    earliest_overall = min((r["earliest"] for r in results if r["earliest"]), default=None)

    verdict = (
        "GO" if (n_window == n_cov and n_cov >= max(1, n // 2))
        else "PARTIAL" if n_window
        else "NO-GO"
    )

    summary = {
        "probe": "moomoo_daily_short_volume",
        "stamp": date.today().isoformat(),
        "oldest_window_start": OLDEST_WINDOW_START,
        "stretch_start": STRETCH_START,
        "tickers_probed": n,
        "tickers_with_data": n_cov,
        "tickers_reaching_oldest_window": n_window,
        "tickers_reaching_2024_stretch": n_stretch,
        "earliest_date_seen": earliest_overall,
        "verdict": verdict,
        "results": results,
    }

    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"VERDICT: {verdict}  (coverage {n_cov}/{n}, reach-2024-window {n_window}/{n_cov})")
    print(f"earliest date seen across all probed tickers: {earliest_overall}")
    print(f"artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
