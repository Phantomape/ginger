"""Synthetic tests for the V3 data layer (no network)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))
import check  # noqa: E402
import fetch  # noqa: E402


def _etf(dates, closes, split=None):
    n = len(dates)
    return pd.DataFrame({
        "date": dates, "open": closes, "high": closes, "low": closes, "close": closes,
        "volume": [100] * n, "dividend": [0.0] * n, "split": split or [0.0] * n, "capital_gain": [0.0] * n,
    })


def test_catch_up_appends_only_new_dates():
    old = _etf(["2026-01-02", "2026-01-05"], [10.0, 11.0])
    new = _etf(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"], [10.0, 11.0, 12.0, 13.0])
    merged, revisions = fetch.merge_append_only(old, new)
    assert merged["date"].tolist() == ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
    assert revisions.empty


def test_revised_history_is_reported_not_overwritten():
    old = _etf(["2026-01-02", "2026-01-05"], [10.0, 11.0])
    new = _etf(["2026-01-02", "2026-01-05", "2026-01-06"], [10.0, 11.5, 12.0])
    merged, revisions = fetch.merge_append_only(old, new)
    assert merged.loc[merged["date"] == "2026-01-05", "close"].item() == 11.0
    assert revisions["date"].tolist() == ["2026-01-05"]
    assert merged["date"].max() == "2026-01-06"


def test_missing_values_compare_equal():
    old = pd.DataFrame({"date": ["2026-01-02"], "value": [float("nan")]})
    new = pd.DataFrame({"date": ["2026-01-02"], "value": [float("nan")]})
    assert fetch.merge_append_only(old, new)[1].empty


def test_intraday_session_is_not_stored():
    # 15:00 New York on 2026-10-07 -> only bars through 10-06 are final
    assert fetch.last_complete_date(pd.Timestamp("2026-10-07 19:00", tz="UTC")) == "2026-10-06"
    # 19:00 New York -> 10-07 bar is final
    assert fetch.last_complete_date(pd.Timestamp("2026-10-07 23:00", tz="UTC")) == "2026-10-07"


def test_freeze_hash_ignores_rows_after_freeze():
    a = _etf(["2026-06-29", "2026-06-30", "2026-07-01"], [1.0, 2.0, 3.0])
    b = _etf(["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"], [1.0, 2.0, 3.0, 4.0])
    c = _etf(["2026-06-29", "2026-06-30"], [1.0, 2.5])
    assert fetch.freeze_hash(a) == fetch.freeze_hash(b)
    assert fetch.freeze_hash(a) != fetch.freeze_hash(c)


def test_staleness_gaps_and_jumps():
    spy = _etf(["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07"], [1.0] * 5)
    gap = _etf(["2026-10-01", "2026-10-05", "2026-10-06", "2026-10-07"], [1.0, 1.0, 1.0, 1.5])
    stale = _etf(["2026-10-01", "2026-10-02"], [1.0, 1.0])
    frames = {t: spy for t in fetch.ETFS}
    frames["QQQ"], frames["TLT"] = gap, stale
    alerts, warnings = check.check_etf(frames, "2026-10-07")
    assert any(a.startswith("QQQ: 1 SPY sessions missing") for a in alerts)
    assert any(a.startswith("TLT: stale") for a in alerts)
    assert any(w.startswith("QQQ: |daily price move|") for w in warnings)
    assert not any(a.startswith("SPY") for a in alerts)


def test_one_holiday_is_not_stale():
    assert check.bdays_behind("2026-10-06", "2026-10-07") == 1
    assert check.bdays_behind("2026-10-02", "2026-10-07") == 3


def test_french_monthly_table_parse():
    text = "header text\n\n,Mkt-RF,SMB\n192607,  2.89, -2.55\n192608,-99.99,  1.0\n\n Annual Factors\n,Mkt-RF\n1927, 1.0\n"
    df = fetch.parse_french_first_table(text)
    assert df["month"].tolist() == ["1926-07", "1926-08"]
    assert pd.isna(df.loc[1, "Mkt-RF"]) and df.loc[0, "SMB"] == -2.55


def test_late_volume_update_is_not_a_revision():
    old = _etf(["2026-01-02"], [10.0])
    new = _etf(["2026-01-02"], [10.0])
    new["volume"] = 999
    assert fetch.merge_append_only(old, new)[1].empty
