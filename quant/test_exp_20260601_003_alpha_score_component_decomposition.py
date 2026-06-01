"""Unit tests for exp-20260601-003 alpha_score component decomposition.

Covers dispersion + within/across-day variance decomposition, the RS
double-sort control, and the judge branches: momentum-only edge,
incremental non-momentum accept (survives RS control), RS-collinear
downgrade, and constant-component detection.

No JavaScript was used.
"""

from __future__ import annotations

from quant.experiments.exp_20260601_003_alpha_score_component_decomposition_forward_return import (  # noqa: E501
    COMPONENTS,
    EDGE_FLOOR,
    _component_dispersion,
    _conditional_spread_vs_rs,
    component_attribution,
    judge,
)


def _obs(asof, ticker, comps, r5):
    full = {c: 0.5 for c in COMPONENTS}
    full.update(comps)
    return {
        "asof_date": asof,
        "ticker": ticker,
        "alpha_score": sum(full.values()) / len(full),
        "components": full,
        "forward_returns": {5: r5, 10: r5, 20: r5},
    }


def test_dispersion_flags_constant_component():
    obs = [_obs("d1", f"T{i}", {"expectation_revision": 0.5}, 0.01) for i in range(50)]
    disp = _component_dispersion(obs, "expectation_revision")
    assert disp["distinct"] == 1
    assert disp["near_constant"] is True
    assert disp["std"] == 0.0


def test_dispersion_within_vs_across_day_share():
    # A component that varies WITHIN each day (cross-sectional) -> high within share.
    obs = []
    for d in ("d1", "d2", "d3"):
        for i in range(40):
            obs.append(_obs(d, f"{d}T{i}", {"relative_strength": i / 40.0}, 0.0))
    disp = _component_dispersion(obs, "relative_strength")
    assert disp["within_day_variance_share"] is not None
    assert disp["within_day_variance_share"] > 0.9  # almost all within-day
    assert disp["cross_sectional"] is True


def test_dispersion_market_timing_low_within_share():
    # A component identical across tickers on a day but differing across days
    # -> low within-day share (market timing).
    obs = []
    day_levels = {"d1": 0.3, "d2": 0.6, "d3": 0.9}
    for d, lvl in day_levels.items():
        for i in range(40):
            obs.append(_obs(d, f"{d}T{i}", {"breadth_alignment": lvl}, 0.0))
    disp = _component_dispersion(obs, "breadth_alignment")
    assert disp["within_day_variance_share"] == 0.0
    assert disp["cross_sectional"] is False


def test_conditional_spread_collapses_when_collinear_with_rs():
    # Build a component perfectly equal to RS -> conditional spread within RS
    # bands should be ~0 (no residual signal).
    obs = []
    for d in ("d1", "d2", "d3", "d4"):
        for i in range(50):
            rs = i / 50.0
            r5 = 0.02 * rs  # returns driven purely by RS
            obs.append(_obs(d, f"{d}T{i}", {"relative_strength": rs, "breadth_alignment": rs}, r5))
    resid = _conditional_spread_vs_rs(obs, "breadth_alignment", 5)
    assert resid is not None
    assert abs(resid) < EDGE_FLOOR  # collapses after RS control


def test_conditional_spread_survives_when_independent():
    # breadth independent of RS and independently drives returns -> residual survives.
    obs = []
    for d in ("d1", "d2", "d3", "d4"):
        for i in range(50):
            rs = (i % 10) / 10.0
            breadth = (i // 10) / 5.0  # orthogonal-ish to rs ordering
            r5 = 0.05 * breadth  # returns driven by breadth, not rs
            obs.append(_obs(d, f"{d}T{i}", {"relative_strength": rs, "breadth_alignment": breadth}, r5))
    resid = _conditional_spread_vs_rs(obs, "breadth_alignment", 5)
    assert resid is not None
    assert resid >= EDGE_FLOOR


def _attr(obs):
    return component_attribution(obs, {"w1": obs})


def test_judge_momentum_only_when_rs_drives_and_others_collinear():
    # RS drives returns; breadth == RS (collinear). Expect momentum_only.
    obs = []
    for d in ("d1", "d2", "d3"):
        for i in range(60):
            rs = i / 60.0
            obs.append(_obs(d, f"{d}T{i}", {"relative_strength": rs, "breadth_alignment": rs}, 0.03 * rs))
    attr = _attr(obs)
    gates = judge(attr, len(obs))
    assert "relative_strength" in gates["gate4"]["momentum_components_with_edge"]
    # breadth flagged univariate but collinear -> not incremental
    assert gates["gate4"]["non_momentum_components_with_edge"] == []
    assert gates["gate4"]["status"] == "observed_only_momentum_only_edge"


def test_judge_accepts_when_independent_non_momentum_edge_survives_rs():
    obs = []
    for d in ("d1", "d2", "d3"):
        for i in range(60):
            rs = (i % 12) / 12.0
            breadth = (i // 12) / 5.0
            # returns driven by breadth, independent of rs ordering
            obs.append(_obs(d, f"{d}T{i}", {"relative_strength": rs, "breadth_alignment": breadth}, 0.05 * breadth))
    attr = _attr(obs)
    gates = judge(attr, len(obs))
    assert "breadth_alignment" in gates["gate4"]["non_momentum_components_with_edge"]
    assert gates["gate4"]["status"] == "accepted_incremental_component_edge"


def test_constants():
    assert EDGE_FLOOR == 0.005
