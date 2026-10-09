"""V3 step 1: catch-up download of backfillable data only.

Every source here can be re-downloaded in full at any time, so a machine that was
off for a week recovers with one run.  Rules:

* ETF rows are stored unadjusted for dividends (split-adjusted close as yfinance
  reports it, plus dividend / split / capital-gain columns); total return is
  computed later from these columns.  yfinance's "Adj Close" is dropped because
  it rescales the whole history after every dividend.
* Rows already stored are never overwritten.  If a re-download disagrees with a
  stored row on any price / distribution column (volume is ignored), the disagreement is written to raw/revisions/ and raised as an
  alert; only dates after the stored last date are appended.
* Only completed sessions are stored (no intraday snapshot rows).
* Ken French tables revise history monthly, so they are stored as dated versions;
  a new version is written only when the parsed content changes.

Usage:  .venv/Scripts/python.exe v3/data/fetch.py [--root DIR] [--only etf,fred,french]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ETFS = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "SHY", "GLD", "DBC",
    "VNQ", "HYG", "LQD", "UUP", "BIL",
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
]
ETF_COLUMNS = ["date", "open", "high", "low", "close", "volume", "dividend", "split", "capital_gain"]
FRED_SERIES = ["DTB3", "DGS3MO", "DGS2", "DGS10"]
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}"
FRENCH_FILES = {
    "ind49_vw_monthly": "49_Industry_Portfolios_CSV.zip",
    "ff3_monthly": "F-F_Research_Data_Factors_CSV.zip",
    "mom_monthly": "F-F_Momentum_Factor_CSV.zip",
}
# End of the validation window (architecture doc section 3); rows up to here are frozen.
FREEZE_THROUGH = "2026-06-30"
SESSION_DONE_HOUR_ET = 18  # a session's daily bar is final after 18:00 New York time

DEFAULT_ROOT = Path(__file__).resolve().parent


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def last_complete_date(now_utc: pd.Timestamp) -> str:
    """Latest calendar date whose daily bar may be stored."""
    et = now_utc.tz_convert("America/New_York")
    day = et.normalize() if et.hour >= SESSION_DONE_HOUR_ET else et.normalize() - pd.Timedelta(days=1)
    return day.strftime("%Y-%m-%d")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frame_csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False, lineterminator="\n")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


def read_stored(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path, dtype={"date": str}, keep_default_na=True)


def merge_append_only(old: pd.DataFrame | None, new: pd.DataFrame, rtol: float = 1e-6):
    """Return (merged, revisions).  Stored rows are kept as-is; new dates are appended."""
    if old is None or old.empty:
        return new.reset_index(drop=True), pd.DataFrame()
    last = old["date"].max()
    overlap = old.merge(new, on="date", suffixes=("_old", "_new"))
    # volume of the latest session is routinely finalised a day later and is not used for returns
    value_cols = [c for c in new.columns if c not in ("date", "volume")]
    changed = pd.Series(False, index=overlap.index)
    for c in value_cols:
        a, b = overlap[f"{c}_old"], overlap[f"{c}_new"]
        both_nan = a.isna() & b.isna()
        diff = (a - b).abs() > rtol * b.abs().clip(lower=1.0)
        changed |= ~both_nan & (diff | (a.isna() != b.isna()))
    revisions = overlap[changed]
    appended = new[new["date"] > last]
    merged = pd.concat([old, appended], ignore_index=True)
    return merged, revisions


def freeze_hash(df: pd.DataFrame) -> str:
    return sha256_bytes(frame_csv(df[df["date"] <= FREEZE_THROUGH]).encode())


# ---------------------------------------------------------------- sources

def download_etf(ticker: str, cutoff: str) -> pd.DataFrame:
    import yfinance as yf

    h = yf.Ticker(ticker).history(period="max", auto_adjust=False, actions=True)
    if h.empty:
        raise RuntimeError(f"yfinance returned no rows for {ticker}")
    out = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in h.index],
        "open": h["Open"].round(4).values,
        "high": h["High"].round(4).values,
        "low": h["Low"].round(4).values,
        "close": h["Close"].round(4).values,
        "volume": h["Volume"].astype("int64").values,
        "dividend": h["Dividends"].round(6).values,
        "split": h["Stock Splits"].round(6).values,
        "capital_gain": (h["Capital Gains"] if "Capital Gains" in h else 0.0),
    })
    out["capital_gain"] = pd.to_numeric(out["capital_gain"]).fillna(0.0).round(6)
    out = out[out["date"] <= cutoff].drop_duplicates("date", keep="last")
    return out.sort_values("date").reset_index(drop=True)[ETF_COLUMNS]


def download_fred(series: str, cutoff: str) -> pd.DataFrame:
    r = requests.get(FRED_URL.format(series), timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), na_values=["."])
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce").round(4)
    df = df[df["date"] <= cutoff]
    return df.sort_values("date").reset_index(drop=True)


def parse_french_first_table(text: str) -> pd.DataFrame:
    """First table in a Ken French CSV = the monthly (value-weighted) section."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        first = line.split(",")[0].strip()
        if start is None and len(first) == 6 and first.isdigit():
            start = i
            header = [c.strip() for c in lines[i - 1].split(",")]
            break
    if start is None:
        raise RuntimeError("no monthly table found")
    rows = []
    for line in lines[start:]:
        cells = [c.strip() for c in line.split(",")]
        if not (len(cells[0]) == 6 and cells[0].isdigit()):
            break
        rows.append(cells)
    header[0] = "month"
    df = pd.DataFrame(rows, columns=header[: len(rows[0])])
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.replace([-99.99, -999.0], float("nan"))
    df["month"] = df["month"].str[:4] + "-" + df["month"].str[4:]
    return df


def download_french(filename: str) -> tuple[pd.DataFrame, str]:
    r = requests.get(FRENCH_URL.format(filename), timeout=120)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        inner = z.read(z.namelist()[0]).decode("latin-1")
    return parse_french_first_table(inner), sha256_bytes(r.content)


# ---------------------------------------------------------------- runners

def update_series(name: str, path: Path, new: pd.DataFrame, root: Path, stamp: str, alerts: list) -> dict:
    old = read_stored(path)
    merged, revisions = merge_append_only(old, new)
    if not revisions.empty:
        rev_path = root / "raw" / "revisions" / f"{name}_{stamp}.csv"
        atomic_write(rev_path, frame_csv(revisions))
        alerts.append(f"{name}: {len(revisions)} stored rows differ from source; kept stored rows, see {rev_path.relative_to(root).as_posix()}")
    text = frame_csv(merged)
    atomic_write(path, text)
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(text.encode()),
        "freeze_sha256": freeze_hash(merged),
        "rows": len(merged),
        "first": merged["date"].min(),
        "last": merged["date"].max(),
        "appended": len(merged) - (0 if old is None else len(old)),
    }


def run(root: Path, only: set[str]) -> dict:
    now = utc_now()
    cutoff = last_complete_date(now)
    stamp = now.strftime("%Y%m%d")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"files": {}}
    files = manifest["files"]
    alerts: list[str] = []
    errors: list[str] = []

    if "etf" in only:
        for t in ETFS:
            try:
                entry = update_series(f"etf_{t}", root / "raw" / "etf" / f"{t}.csv", download_etf(t, cutoff), root, stamp, alerts)
                entry["source"] = f"yfinance history(period=max, auto_adjust=False, actions=True) {t}"
                files[f"etf/{t}"] = entry
            except Exception as exc:  # keep going; the failure is reported, not hidden
                errors.append(f"etf {t}: {exc!r}")

    if "fred" in only:
        for s in FRED_SERIES:
            try:
                entry = update_series(f"fred_{s}", root / "raw" / "fred" / f"{s}.csv", download_fred(s, cutoff), root, stamp, alerts)
                entry["source"] = FRED_URL.format(s)
                files[f"fred/{s}"] = entry
            except Exception as exc:
                errors.append(f"fred {s}: {exc!r}")

    if "french" in only:
        for key, filename in FRENCH_FILES.items():
            try:
                df, zip_sha = download_french(filename)
                text = frame_csv(df)
                sha = sha256_bytes(text.encode())
                versions = files.get(f"french/{key}", {}).get("versions", [])
                if not versions or versions[-1]["sha256"] != sha:
                    path = root / "raw" / "french" / f"{key}_{stamp}.csv"
                    atomic_write(path, text)
                    versions.append({
                        "path": path.relative_to(root).as_posix(), "sha256": sha, "source_zip_sha256": zip_sha,
                        "rows": len(df), "first": df["month"].min(), "last": df["month"].max(), "downloaded": stamp,
                    })
                files[f"french/{key}"] = {"source": FRENCH_URL.format(filename), "versions": versions}
            except Exception as exc:
                errors.append(f"french {key}: {exc!r}")

    manifest.update({
        "schema": "v3-data-manifest-1",
        "freeze_through": FREEZE_THROUGH,
        "generated_at_utc": now.isoformat(),
        "last_complete_date": cutoff,
        "last_run_alerts": alerts,
        "last_run_errors": errors,
    })
    atomic_write(manifest_path, json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--only", default="etf,fred,french")
    args = ap.parse_args()
    m = run(args.root, set(args.only.split(",")))
    for a in m["last_run_alerts"]:
        print("ALERT", a)
    for e in m["last_run_errors"]:
        print("ERROR", e)
    print(f"done: {len(m['files'])} files, last_complete_date={m['last_complete_date']}")
    return 1 if m["last_run_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
