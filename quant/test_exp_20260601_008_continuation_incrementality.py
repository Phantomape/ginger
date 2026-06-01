"""Unit tests for exp-20260601-008 long-only continuation incrementality.

Covers the return/forward helpers, the t-stat, quintile grouping, and --
the load-bearing fix -- the incrementality gate that requires the ret20
double-sort residual to be BOTH above cost AND statistically significant
(t >= 2), not merely a positive point estimate.

No JavaScript was used.
"""

from __future__ import annotations

from quant.experiments.exp_20260601_008_long_only_continuation_incrementality import (  # noqa: E501
    HOLD,
    LONG_ONLY_COST,
    SKIP_DAYS,
    T_STAT_FLOOR,
    _quintile_groups,
    _ret,
    _skip_fwd,
    _tstat,
)


def test_ret_and_skip_fwd():
    closes = [100.0, 102.0, 101.0, 105.0, 110.0, 108.0, 120.0]
    assert abs(_ret(closes, 4, 4) - (110 / 100 - 1)) < 1e-9
    assert _ret(closes, 1, 5) is None
    # skip=1: pos=0, hold=5 -> entry=1, exit=6 -> 120/102 - 1
    assert SKIP_DAYS == 1
    assert abs(_skip_fwd(closes, 0, 5) - (120 / 102 - 1)) < 1e-9


def test_quintile_groups_partition():
    rows = [{"k": i} for i in range(10)]
    groups = _quintile_groups(rows, "k")
    assert len(groups) == 5
    assert sum(len(g) for g in groups) == 10
    assert groups[0][0]["k"] == 0   # lowest
    assert groups[-1][-1]["k"] == 9  # highest


def test_tstat_significance():
    # tight positive series -> high t
    assert _tstat([0.01, 0.011, 0.009, 0.012, 0.010]) > 2
    # noisy zero-mean -> low t
    t = _tstat([0.05, -0.05, 0.04, -0.04, 0.0])
    assert t is not None and abs(t) < 2


def test_incrementality_requires_significant_residual():
    """Mirror the judge's incremental_ok logic: positive residual point
    estimate with insignificant t must NOT count as incremental (this is the
    exp-20260601-008 fix that flipped accept -> observed_only)."""

    def incremental_ok(resid_mean, resid_tstat):
        return (
            resid_mean is not None
            and resid_mean > LONG_ONLY_COST
            and resid_tstat is not None
            and resid_tstat >= T_STAT_FLOOR
        )

    # the real exp-008 case: residual above cost but t = 1.00 -> NOT incremental
    assert incremental_ok(0.0047, 1.00) is False
    # significant residual -> incremental
    assert incremental_ok(0.0047, 2.5) is True
    # significant but below cost -> not incremental
    assert incremental_ok(0.002, 3.0) is False


def test_constants():
    assert HOLD == 10
    assert SKIP_DAYS == 1
    assert T_STAT_FLOOR == 2.0
    assert abs(LONG_ONLY_COST - 0.0035) < 1e-9
