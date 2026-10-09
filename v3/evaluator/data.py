"""Turn the stored V3 data into return panels.  No strategy logic here."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

V3 = Path(__file__).resolve().parents[1]
DATA = V3 / "data"


def manifest() -> dict:
    return json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))


def _read(rel: str) -> pd.DataFrame:
    return pd.read_csv(DATA / rel, dtype={"date": str, "month": str})


def total_return(df: pd.DataFrame) -> pd.Series:
    """Daily total return from a stored ETF frame (split-adjusted close + cash distributions)."""
    close = df["close"]
    r = (close + df["dividend"] + df["capital_gain"]) / close.shift(1) - 1
    return pd.Series(r.values, index=pd.to_datetime(df["date"]))


def etf_panel(m: dict | None = None) -> tuple[pd.DataFrame, pd.Series]:
    """(daily total returns per ETF on the SPY calendar, daily cash return from 3m T-bill)."""
    m = m or manifest()
    cols = {}
    for key, entry in sorted(m["files"].items()):
        if key.startswith("etf/"):
            cols[key[4:]] = total_return(_read(entry["path"]))
    panel = pd.DataFrame(cols).reindex(cols["SPY"].index)
    bill = _read(m["files"]["fred/DTB3"]["path"])
    rate = pd.Series(bill["value"].values, index=pd.to_datetime(bill["date"])) / 100.0
    # return for day t uses the rate known at t-1
    rate = rate.reindex(rate.index.union(panel.index)).ffill().shift(1).reindex(panel.index)
    cash = (rate / 252.0).fillna(0.0)
    return panel, cash


def evidence_panel(paths: dict) -> tuple[pd.DataFrame, pd.Series]:
    """(monthly returns: 49 value-weighted industries + 'MKT', monthly risk-free) from Ken French.

    ``paths`` maps french/<key> to the pinned version file (from evaluator.lock), so a later
    Ken French revision cannot silently change a past evaluation.
    """

    def latest(key: str) -> pd.DataFrame:
        df = _read(paths[key])
        df.index = pd.PeriodIndex(df.pop("month"), freq="M").to_timestamp(how="end").normalize()
        return df / 100.0

    ind = latest("french/ind49_vw_monthly")
    ff3 = latest("french/ff3_monthly")
    ind["MKT"] = ff3["Mkt-RF"] + ff3["RF"]
    return ind, ff3["RF"].reindex(ind.index).fillna(0.0)


SORT_FILES = {
    "MOM": "french/sort_prior_12_2_vw_monthly",
    "OP": "french/sort_op_vw_monthly",
    "INV": "french/sort_inv_vw_monthly",
    "BM": "french/sort_bm_vw_monthly",
}


def sorts_panel(paths: dict) -> tuple[pd.DataFrame, pd.Series]:
    """Monthly value-weighted returns of CRSP stock portfolios sorted on a characteristic
    (columns like 'MOM:Hi PRIOR', 'OP:Hi 10'), plus 'MKT'; and the monthly risk-free rate."""

    def read(key: str) -> pd.DataFrame:
        df = _read(paths[key])
        df.index = pd.PeriodIndex(df.pop("month"), freq="M").to_timestamp(how="end").normalize()
        return df / 100.0

    ff3 = read("french/ff3_monthly")
    cols = {f"{prefix}:{c}": s for prefix, key in SORT_FILES.items() for c, s in read(key).items()}
    panel = pd.DataFrame(cols).reindex(ff3.index)
    panel["MKT"] = ff3["Mkt-RF"] + ff3["RF"]
    return panel, ff3["RF"]
