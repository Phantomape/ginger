"""V3 data health check.  Status is recomputed from the data on every run (never
read back from an earlier run), using now - last date against each source's
expected frequency.

Usage:  .venv/Scripts/python.exe v3/data/check.py [--root DIR] [--warehouse] [--opend]

--warehouse  cross-check ETF daily returns against the V1 sqlite warehouse (read-only)
--opend      cross-check unadjusted closes against moomoo OpenD (uses ~26 of the
             100-symbols-per-30-days history quota; skipped with a warning if OpenD is down)
"""
from __future__ import annotations

import argparse
import json
import socket
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import DEFAULT_ROOT, ETFS, atomic_write, last_complete_date, read_stored, utc_now  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
ETF_STALE_BDAYS = 1
FRED_STALE_BDAYS = 5
FRENCH_STALE_MONTHS = 3
JUMP_LIMIT = 0.25
XCHECK_TOL = 0.001  # 0.1%
# OpenD's pre-2018 closes differ from yfinance by ~0.2% on scattered days (mostly 2007-08)
# while yfinance and the V1 warehouse agree; only recent disagreement is an alert.
OPEND_RECENT_YEARS = 3


def bdays_behind(last: str, cutoff: str) -> int:
    return max(len(pd.bdate_range(pd.Timestamp(last) + pd.Timedelta(days=1), cutoff)), 0)


def etf_frames(root: Path) -> dict[str, pd.DataFrame]:
    out = {}
    for t in ETFS:
        df = read_stored(root / "raw" / "etf" / f"{t}.csv")
        if df is not None:
            out[t] = df
    return out


def check_etf(frames: dict[str, pd.DataFrame], cutoff: str) -> tuple[list[str], list[str]]:
    alerts, warnings = [], []
    calendar = set(frames["SPY"]["date"]) if "SPY" in frames else set()
    for t in ETFS:
        df = frames.get(t)
        if df is None:
            alerts.append(f"{t}: missing file")
            continue
        behind = bdays_behind(df["date"].max(), cutoff)
        if behind > ETF_STALE_BDAYS:
            alerts.append(f"{t}: stale, last {df['date'].max()} is {behind} business days behind {cutoff}")
        if df["date"].duplicated().any():
            alerts.append(f"{t}: duplicate dates")
        if (df["close"] <= 0).any() or df["close"].isna().any():
            alerts.append(f"{t}: non-positive or missing close")
        expected = {d for d in calendar if d >= df["date"].min()}
        missing = sorted(expected - set(df["date"]))
        if missing:
            alerts.append(f"{t}: {len(missing)} SPY sessions missing, first {missing[:3]}")
        ret = df["close"].pct_change()
        jumps = df.loc[(ret.abs() > JUMP_LIMIT) & (df["split"] == 0), "date"].tolist()
        if jumps:
            warnings.append(f"{t}: |daily price move| > {JUMP_LIMIT:.0%} on {jumps[:5]}")
    return alerts, warnings


def check_fred_french(root: Path, manifest: dict, cutoff: str) -> list[str]:
    alerts = []
    for key, entry in manifest.get("files", {}).items():
        if key.startswith("fred/"):
            df = read_stored(root / entry["path"])
            last = df.dropna()["date"].max()
            behind = bdays_behind(last, cutoff)
            if behind > FRED_STALE_BDAYS:
                alerts.append(f"{key}: stale, last value {last} is {behind} business days behind")
        elif key.startswith("french/"):
            last = entry["versions"][-1]["last"]
            months = (pd.Period(cutoff[:7], "M") - pd.Period(last, "M")).n
            if months > FRENCH_STALE_MONTHS:
                alerts.append(f"{key}: stale, last month {last}")
    return alerts


def plain_returns(df: pd.DataFrame) -> pd.Series:
    """Close-to-close returns on days without dividend/split/capital gain; equal under any adjustment."""
    s = df.set_index("date")["close"].pct_change()
    event = df.set_index("date")[["dividend", "split", "capital_gain"]].ne(0).any(axis=1)
    return s[~event].dropna()


def xcheck_warehouse(frames: dict[str, pd.DataFrame]) -> tuple[list[str], dict]:
    sys.path.insert(0, str(REPO / "quant"))
    from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH

    con = sqlite3.connect(f"file:{DEFAULT_WAREHOUSE_PATH}?mode=ro", uri=True)
    alerts, report = [], {}
    for t, df in frames.items():
        wh = pd.read_sql("select date, close from ohlcv where ticker=? order by date", con, params=(t,))
        if wh.empty:
            continue
        ours = df.set_index("date")
        wh = wh[wh["date"].isin(ours.index)].set_index("date")
        wr = wh["close"].pct_change()
        yr = plain_returns(df)
        both = pd.concat([yr, wr], axis=1, join="inner").dropna()
        both = both[both.index.isin(wh.index[1:])]
        bad = (both.iloc[:, 0] - both.iloc[:, 1]).abs() > XCHECK_TOL
        report[t] = {"days": int(len(both)), "mismatch_days": int(bad.sum()), "range": [wh.index.min(), wh.index.max()]}
        if len(both) and bad.mean() > 0.01:
            alerts.append(f"{t}: warehouse returns differ >0.1% on {int(bad.sum())}/{len(both)} days")
    con.close()
    return alerts, report


def opend_up(host: str = "127.0.0.1", port: int = 11111) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def xcheck_opend(frames: dict[str, pd.DataFrame], cutoff: str) -> tuple[list[str], list[str], dict]:
    if not opend_up():
        return [], ["opend: 127.0.0.1:11111 not reachable, cross-check skipped"], {}
    from moomoo import AuType, KLType, OpenQuoteContext, RET_OK

    q = OpenQuoteContext(host="127.0.0.1", port=11111)
    alerts, warnings, report = [], [], {}
    try:
        for t, df in frames.items():
            rows, page = [], None
            while True:
                ret, data, page = q.request_history_kline(
                    f"US.{t}", start="2000-01-01", end=df["date"].max(), ktype=KLType.K_DAY,
                    autype=AuType.NONE, max_count=1000, page_req_key=page,
                )
                if ret != RET_OK:
                    warnings.append(f"opend {t}: {data}")
                    break
                rows.append(data[["time_key", "close"]])
                if page is None:
                    break
            if not rows:
                continue
            od = pd.concat(rows)
            od["date"] = od["time_key"].str[:10]
            # yfinance close is split-adjusted; undo later splits to get the raw close OpenD reports
            factor = df["split"].replace(0, 1.0)[::-1].cumprod()[::-1].shift(-1, fill_value=1.0)
            raw = pd.Series((df["close"] * factor).values, index=df["date"])
            both = pd.concat([raw, od.set_index("date")["close"]], axis=1, join="inner").dropna()
            rel = (both.iloc[:, 0] / both.iloc[:, 1] - 1).abs()
            bad = rel > XCHECK_TOL
            recent_from = str(int(cutoff[:4]) - OPEND_RECENT_YEARS) + cutoff[4:]
            bad_recent = bad[bad.index >= recent_from]
            report[t] = {"days": int(len(both)), "mismatch_days": int(bad.sum()),
                         "mismatch_days_recent": int(bad_recent.sum()), "first": both.index.min()}
            if bad_recent.any():
                alerts.append(f"{t}: OpenD raw close differs >0.1% since {recent_from} on {list(bad_recent.index[bad_recent][:5])}")
            elif bad.any():
                warnings.append(f"{t}: OpenD raw close differs >0.1% on {int(bad.sum())} older days (before {recent_from})")
    finally:
        q.close()
    return alerts, warnings, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--warehouse", action="store_true")
    ap.add_argument("--opend", action="store_true")
    args = ap.parse_args()

    now = utc_now()
    cutoff = last_complete_date(now)
    manifest = json.loads((args.root / "manifest.json").read_text(encoding="utf-8"))
    frames = etf_frames(args.root)
    alerts, warnings = check_etf(frames, cutoff)
    alerts += check_fred_french(args.root, manifest, cutoff)
    alerts += [f"fetch: {e}" for e in manifest.get("last_run_errors", [])]
    alerts += [f"fetch: {a}" for a in manifest.get("last_run_alerts", [])]
    xchecks = {}
    if args.warehouse:
        a, xchecks["warehouse"] = xcheck_warehouse(frames)
        alerts += a
    if args.opend:
        a, w, xchecks["opend"] = xcheck_opend(frames, cutoff)
        alerts += a
        warnings += w

    health = {
        "generated_at_utc": now.isoformat(),
        "last_complete_date": cutoff,
        "status": "alert" if alerts else "ok",
        "alerts": alerts,
        "warnings": warnings,
        "cross_checks": xchecks,
    }
    atomic_write(args.root / "health.json", json.dumps(health, indent=1, sort_keys=True) + "\n")
    for a in alerts:
        print("ALERT", a)
    for w in warnings:
        print("WARN ", w)
    print(f"status={health['status']} alerts={len(alerts)} warnings={len(warnings)}")
    return 1 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
