from __future__ import annotations

import math

from quant.risk_engine import _sector_ret20_dispersion


def test_dispersion_ignores_nan_and_inf_momentum() -> None:
    # A non-finite momentum used to crash statistics.pstdev with
    # "'float' object has no attribute 'numerator'". It must now be excluded.
    from quant import risk_engine

    features = {
        "AAA": {"momentum_20d_pct": 1.0},
        "BBB": {"momentum_20d_pct": 3.0},
        "CCC": {"momentum_20d_pct": float("nan")},
        "DDD": {"momentum_20d_pct": float("inf")},
    }
    original = dict(getattr(risk_engine, "SECTOR_MAP", {}))
    try:
        # Distinct sectors so two finite sector averages survive.
        risk_engine.SECTOR_MAP.update({"AAA": "S0", "BBB": "S1", "CCC": "S2", "DDD": "S3"})
        result = _sector_ret20_dispersion(features)
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original)
    assert result is not None
    assert math.isfinite(result)


def test_dispersion_none_when_under_two_finite_sectors() -> None:
    features = {
        "AAA": {"momentum_20d_pct": float("nan")},
        "BBB": {"momentum_20d_pct": 2.0},
    }
    # Only one finite sector average remains -> not enough to disperse.
    assert _sector_ret20_dispersion(features) is None


def test_dispersion_matches_population_stdev_on_clean_input() -> None:
    import statistics

    from quant import risk_engine

    # Force distinct sectors so each ticker is its own sector average.
    features = {f"T{i}": {"momentum_20d_pct": v} for i, v in enumerate([1.0, 2.0, 3.0])}
    original = dict(getattr(risk_engine, "SECTOR_MAP", {}))
    try:
        risk_engine.SECTOR_MAP.update({"T0": "S0", "T1": "S1", "T2": "S2"})
        got = _sector_ret20_dispersion(features)
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original)
    assert got is not None
    assert abs(got - statistics.pstdev([1.0, 2.0, 3.0])) < 1e-9
