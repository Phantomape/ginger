"""Unit tests for exp-20260605-010 broad fundamental-growth attribution.

Covers PIT growth lookup, return/skip-forward math, the t-stat helper, the
within-ret20-band daily residual spread, and quintile bucketing.

No JavaScript was used.
"""

from __future__ import annotations

import json

from quant.experiments.exp_20260605_010_broad_fundamental_growth_attribution import (  # noqa: E501
    GROWTH_CLIP,
    SKIP_DAYS,
    T_STAT_FLOOR,
    _day_within_ret20_growth_spread,
    _quintile_groups,
    _ret,
    _skip_fwd,
    _tstat,
    latest_growth,
    load_growth_index,
)


def test_latest_growth_is_pit():
    idx = {"AAA": [("2025-01-15", 0.10), ("2025-04-20", 0.20), ("2025-07-25", 0.30)]}
    # before any filing
    assert latest_growth(idx, "AAA", "2025-01-01") is None
    # between first and second
    assert latest_growth(idx, "AAA", "2025-03-01") == 0.10
    # exactly on a filing date counts (asof <= signal_day)
    assert latest_growth(idx, "AAA", "2025-04-20") == 0.20
    # after last
    assert latest_growth(idx, "AAA", "2026-01-01") == 0.30
    # unknown ticker
    assert latest_growth(idx, "ZZZ", "2025-06-01") is None


def test_load_growth_index_filters_and_clips(tmp_path):
    rows = [
        {"ticker": "AAA", "canonical": "revenue", "asof_date": "2025-02-01", "yoy_growth": 0.25, "growth_status": "ok"},
        {"ticker": "AAA", "canonical": "revenue", "asof_date": "2025-05-01", "yoy_growth": 99.0, "growth_status": "ok"},   # clipped
        {"ticker": "AAA", "canonical": "revenue", "asof_date": "2025-03-01", "yoy_growth": None, "growth_status": "missing_prior_period"},  # dropped
        {"ticker": "BBB", "canonical": "eps_basic", "asof_date": "2025-02-01", "yoy_growth": 0.4, "growth_status": "ok"},  # wrong canonical
    ]
    p = tmp_path / "g.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    idx = load_growth_index(p, canonical="revenue")
    assert set(idx.keys()) == {"AAA"}  # BBB filtered (eps), missing dropped
    vals = dict(idx["AAA"])
    assert vals["2025-02-01"] == 0.25
    assert vals["2025-05-01"] == GROWTH_CLIP  # 99.0 clipped to +5.0
    # sorted by date
    assert idx["AAA"] == sorted(idx["AAA"])


def test_ret_and_skip_fwd():
    closes = [100.0, 110.0, 121.0, 90.0, 99.0, 108.9]
    assert abs(_ret(closes, 2, 2) - (121 / 100 - 1)) < 1e-9
    assert _ret(closes, 1, 5) is None
    # skip=1: pos=0, hold=3 -> entry=1, exit=4 -> 99/110 - 1
    assert SKIP_DAYS == 1
    assert abs(_skip_fwd(closes, 0, 3) - (99 / 110 - 1)) < 1e-9


def test_tstat():
    assert _tstat([0.01, 0.011, 0.009, 0.012, 0.010]) > 2
    t = _tstat([0.05, -0.05, 0.04, -0.04, 0.0])
    assert t is not None and abs(t) < 2
    assert _tstat([0.01, 0.01]) is None  # < 3 obs


def _row(g, r20, f20):
    return {"ticker": "T", "growth": g, "ret20": r20, "f20": f20, "f10": f20}


def test_within_ret20_band_spread_none_when_thin():
    # fewer than QUINTILE*QUINTILE*2 = 50 rows -> None
    rows = [_row(i / 10.0, i / 100.0, 0.01) for i in range(30)]
    assert _day_within_ret20_growth_spread(rows, "f20") is None


def test_within_ret20_band_spread_computes_with_enough_rows():
    # 100 rows: growth and ret20 independent-ish; should produce a number
    rows = []
    for i in range(100):
        rows.append(_row((i % 10) / 10.0, (i // 10) / 10.0, 0.001 * (i % 10)))
    val = _day_within_ret20_growth_spread(rows, "f20")
    assert val is not None
    assert isinstance(val, float)


def test_quintile_groups_partition():
    rows = [{"growth": i} for i in range(20)]
    g = _quintile_groups(rows, "growth")
    assert len(g) == 5
    assert sum(len(b) for b in g) == 20
    assert g[0][0]["growth"] == 0
    assert g[-1][-1]["growth"] == 19


def test_constants():
    assert SKIP_DAYS == 1
    assert T_STAT_FLOOR == 2.0
    assert GROWTH_CLIP == 5.0
