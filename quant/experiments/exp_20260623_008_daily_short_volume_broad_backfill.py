"""exp-20260623-008: broad-universe moomoo daily short-volume PIT backfill.

Data-prep step for the broad-universe retest. Both exp-20260622-010 and
exp-20260622-021 rejected the daily short-volume imbalance signal, but BOTH were
judged on a 5-ticker archive and failed concentration by construction; both
closeouts name "materially broader archived Moomoo coverage" as the required new
evidence. This script provides exactly that: it archives the production-visible
liquid universe (get_universe(), ~51 names) across the three standard backtest
windows plus a lookback buffer, mirroring the exp-20260622-009 archive schema so
the downstream candidate-pool helper can read it.

Semantics / PIT boundary (carried from the exp-009 archive, do not relax):
- moomoo daily short volume is an ACTIVITY field (shares short-sold that day),
  NOT FINRA short-interest positioning. Treat as activity-only sell-pressure.
- Each row is stamped by `activity_date`; the value is knowable only AFTER that
  day's US close (published next day). The replay/helper must map each
  activity_date to the NEXT tradable session — the archive stores raw dated rows
  only and applies no lookahead.

Observe-only: writes a PIT archive, wires nothing into run.py, changes no
order/ranking/sizing/exit path. Requires OpenD running + logged in. Resumable:
re-running skips tickers already complete in the manifest.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_layer import get_universe  # noqa: E402

EXPERIMENT_ID = "exp-20260623-008"
OUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_daily_short_volume_broad"
ROWS_PATH = OUT_DIR / "rows.jsonl"
MANIFEST_PATH = OUT_DIR / "manifest.json"

# Cover the three standard windows (old_thin starts 2024-10-02) with a lookback
# buffer so a trailing-median/z-score helper has history before the first window.
START_DATE = "2024-06-01"

PAGE_NUM = 50            # max per page (range 1-50)
REQUEST_SLEEP_SEC = 1.1  # stay under 30 req / 30s
MAX_PAGES = 60           # safety cap; we stop earlier once we pass START_DATE

ACTIVITY_WARNING = (
    "Moomoo daily short volume is an activity field, not FINRA short-interest "
    "positioning. Any candidate-pool helper must use it as activity-only "
    "sell-pressure context and map each activity_date to the next tradable session."
)


def _f(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n == n else None  # drop NaN


def _load_existing() -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Return (rows_by_key, done_tickers) for resume."""
    rows: dict[str, dict[str, Any]] = {}
    done: set[str] = set()
    if ROWS_PATH.exists():
        for line in ROWS_PATH.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = f"{r.get('source_code')}|{r.get('activity_date')}"
            rows[key] = r
    if MANIFEST_PATH.exists():
        try:
            m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            done = set(m.get("completed_tickers") or [])
        except json.JSONDecodeError:
            pass
    return rows, done


def _fetch_ticker(ctx, code: str) -> tuple[list[dict[str, Any]], str | None]:
    from moomoo import RET_OK

    collected: list[dict[str, Any]] = []
    next_key = None
    pages = 0
    stamp = datetime.now(timezone.utc).isoformat()
    while pages < MAX_PAGES:
        kwargs = {"num": PAGE_NUM}
        if next_key not in (None, "", "-1"):
            kwargs["next_key"] = next_key
        ret, us_df, _hk_df = ctx.get_daily_short_volume(code, **kwargs)
        if ret != RET_OK:
            return collected, str(us_df)
        if us_df is None or us_df.empty:
            break
        page_min = "9999-99-99"
        for rec in us_df.to_dict("records"):
            ad = str(rec.get("timestamp_str") or "")[:10]
            if not ad:
                continue
            page_min = min(page_min, ad)
            if ad < START_DATE:
                continue
            collected.append({
                "activity_date": ad,
                "source_code": code,
                "archive_experiment_id": EXPERIMENT_ID,
                "collected_at": stamp,
                "pit_boundary": "activity_date_after_us_close",
                "positioning_warning": ACTIVITY_WARNING,
                "total_shares_short": _f(rec.get("total_shares_short")),
                "nasdaq_shares_short": _f(rec.get("nasdaq_shares_short")),
                "nyse_shares_short": _f(rec.get("nyse_shares_short")),
                "short_percent": _f(rec.get("short_percent")),
                "volume": _f(rec.get("volume")),
                "close_price": _f(rec.get("close_price")),
                "last_close_price": _f(rec.get("last_close_price")),
                "daily_trade_avg_ratio": _f(rec.get("daily_trade_avg_ratio")),
            })
        pages += 1
        nk = us_df.attrs.get("next_key", "") if hasattr(us_df, "attrs") else ""
        # stop once this page already reached before our start date, or no more
        if page_min < START_DATE or not nk or nk == "-1":
            break
        next_key = nk
        time.sleep(REQUEST_SLEEP_SEC)
    return collected, None


def main() -> int:
    try:
        from moomoo import OpenQuoteContext
        ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: cannot reach OpenD on 127.0.0.1:11111 ({e}).", file=sys.stderr)
        return 2

    universe = sorted(get_universe())
    codes = [f"US.{t}" for t in universe]
    rows_by_key, done = _load_existing()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    completed: list[str] = sorted(done)
    errors: dict[str, str] = {}
    try:
        for i, code in enumerate(codes, 1):
            if code in done:
                print(f"[skip {i}/{len(codes)}] {code} (already archived)", flush=True)
                continue
            # Per-ticker resilience: OpenD can drop the connection mid-run
            # (reason=CallClose). Catch it, reconnect once, and retry this ticker
            # so a transient disconnect doesn't abort the whole backfill.
            try:
                recs, err = _fetch_ticker(ctx, code)
            except Exception as fetch_exc:  # noqa: BLE001
                print(f"[warn {i}/{len(codes)}] {code} disconnected ({fetch_exc}); reconnecting", flush=True)
                try:
                    ctx.close()
                except Exception:
                    pass
                time.sleep(3.0)
                from moomoo import OpenQuoteContext as _OQC
                ctx = _OQC(host="127.0.0.1", port=11111)
                try:
                    recs, err = _fetch_ticker(ctx, code)
                except Exception as e2:  # noqa: BLE001
                    recs, err = [], f"retry_failed: {e2}"
            if err:
                errors[code] = err
                print(f"[ERR  {i}/{len(codes)}] {code}: {err}", flush=True)
            else:
                for r in recs:
                    rows_by_key[f"{r['source_code']}|{r['activity_date']}"] = r
                completed.append(code)
                dates = [r["activity_date"] for r in recs]
                rng = f"{min(dates)}..{max(dates)}" if dates else "(none)"
                print(f"[ok   {i}/{len(codes)}] {code} rows={len(recs)} {rng}", flush=True)
            # persist after every ticker so a kill/timeout keeps progress
            with ROWS_PATH.open("w", encoding="utf-8") as f:
                for r in sorted(rows_by_key.values(), key=lambda x: (x["source_code"], x["activity_date"])):
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            MANIFEST_PATH.write_text(json.dumps({
                "schema_version": 1,
                "source": "moomoo.get_daily_short_volume",
                "archive_experiment_id": EXPERIMENT_ID,
                "activity_only_warning": ACTIVITY_WARNING,
                "pit_boundary": "activity_date_after_us_close; map to next tradable session",
                "start_date": START_DATE,
                "universe": "get_universe()",
                "universe_size": len(codes),
                "completed_tickers": sorted(set(completed)),
                "errored_tickers": errors,
                "rows": len(rows_by_key),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2, ensure_ascii=False), encoding="utf-8")
            time.sleep(REQUEST_SLEEP_SEC)
    finally:
        try:
            ctx.close()
        except Exception:
            pass

    n_done = len(set(completed))
    print(f"\nDONE: {n_done}/{len(codes)} tickers, {len(rows_by_key)} rows, "
          f"{len(errors)} errors. archive={ROWS_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
