from __future__ import annotations

import numpy as np

from quant.joint_strategy_allocator import (
    BUCKETS,
    candidate_bucket,
    enumerate_global_vectors,
    enumerate_local_vectors,
    evaluate_weights,
    optimize_vectors,
)


def _surfaces():
    core = {
        "old_thin": np.asarray([0.001, -0.0005, 0.001]),
        "mid_weak": np.asarray([0.001, -0.0005, 0.001]),
        "late_strong": np.asarray([0.001, -0.0005, 0.001]),
    }
    buckets = {
        bucket: {window: np.zeros(3) for window in core} for bucket in BUCKETS
    }
    buckets[BUCKETS[0]] = {
        window: np.asarray([0.003, 0.0, 0.003]) for window in core
    }
    buckets[BUCKETS[1]] = {
        window: np.asarray([0.002, 0.0, 0.002]) for window in core
    }
    return core, buckets


def test_candidate_bucket_uses_fixed_taxonomy():
    row = {
        "family": "companyfacts gross margin",
        "path": "data/companyfacts_ratio.json",
        "status": "rejected",
        "decision": "rejected",
    }
    assert candidate_bucket(row) == "fundamental_quality"


def test_global_vectors_are_complete_bounded_and_include_null():
    vectors = list(enumerate_global_vectors())
    assert len(vectors) == len(set(vectors))
    assert (0.0,) * len(BUCKETS) in vectors
    assert all(sum(vector) <= 0.10 + 1e-12 for vector in vectors)
    assert all(max(vector) <= 0.05 + 1e-12 for vector in vectors)


def test_local_vectors_obey_quarter_point_and_l1_radius():
    center = (0.05, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    vectors = list(enumerate_local_vectors(center))
    assert center in vectors
    assert len(vectors) == len(set(vectors))
    for vector in vectors:
        assert sum(vector) <= 0.10 + 1e-12
        assert max(vector) <= 0.05 + 1e-12
        assert sum(abs(left - right) for left, right in zip(vector, center)) <= 0.01 + 1e-12
        assert all(abs(round(value / 0.0025) * 0.0025 - value) <= 1e-12 for value in vector)


def test_evaluate_and_optimize_prefer_positive_diversifying_buckets():
    core, buckets = _surfaces()
    result = evaluate_weights(
        (0.05, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        labels=tuple(core),
        core_returns=core,
        bucket_returns=buckets,
    )
    assert result["aggregate_ev_delta"] > 0
    assert result["aggregate_pnl_delta"] > 0
    search = optimize_vectors(
        enumerate_global_vectors(),
        labels=tuple(core),
        core_returns=core,
        bucket_returns=buckets,
    )
    assert not search["fallback_to_null_core"]
    selected = search["selected"]["weights"]
    assert selected[BUCKETS[0]] == 0.05
    assert selected[BUCKETS[1]] == 0.05
