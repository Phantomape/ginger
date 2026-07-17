from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from quant.convergence import compute_expected_value_score, expected_value_score_raw
from quant import historical_current_contract_reassessment as audit


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _surface(*, explicit_notional: bool) -> dict[str, list[dict[str, object]]]:
    rows: dict[str, list[dict[str, object]]] = {}
    for index, window in enumerate(audit.WINDOWS):
        row: dict[str, object] = {
            "ticker": "abc",
            "entry_date": f"2025-01-0{index + 2}",
            "exit_date": f"2025-01-0{index + 3}",
            "entry_price": 10.0,
            "exit_price": 11.0,
            "shares": 400.0,
        }
        if explicit_notional:
            row["paper_notional_usd"] = 4_000.0
        rows[window] = [row]
    return rows


def test_sign_preserving_ev_helper_and_wrapper() -> None:
    assert expected_value_score_raw(-0.10, -1.5) == pytest.approx(-0.15)
    assert expected_value_score_raw(0.10, -1.5) == pytest.approx(0.15)
    assert expected_value_score_raw(None, 1.0) is None
    assert compute_expected_value_score(
        {
            "benchmarks": {"strategy_total_return_pct": -0.10},
            "sharpe_daily": -1.5,
        }
    ) == -0.15


def test_daily_metric_and_bootstrap_score_keep_return_sign() -> None:
    values = np.asarray([-0.01, -0.02, 0.005], dtype=float)
    metrics = audit.current_return_metrics(values)
    assert metrics["total_return_fraction"] < 0.0
    assert metrics["sharpe_daily"] < 0.0
    assert metrics["expected_value_score"] < 0.0

    boot = np.vstack([values, values * 0.5])
    scores = audit.current_bootstrap_ev(boot)
    assert np.all(scores < 0.0)


def test_non_long_proxy_is_detected_before_long_replay() -> None:
    surface = _surface(explicit_notional=True)
    surface["late_strong"][0]["paper_direction"] = "inverse_short_proxy"
    normalized, report = audit._normalize_target_surface(surface)
    assert len(normalized["late_strong"]) == 1
    assert report["unsupported_non_long_direction_row_count"] == 1
    assert report["explicit_direction_values"] == {"inverse_short_proxy": 1}


def test_single_window_candidate_adds_evidence_blocker_without_hiding_hard_failure() -> None:
    report = {
        "passed": False,
        "status": "blocked",
        "portfolio_verdict": "portfolio_reject",
        "hard_failures": ["non_positive_aggregate_pnl"],
        "measurement_blockers": [],
        "evidence_blockers": [],
        "checks": {},
        "metrics": {},
    }
    result = audit._enforce_candidate_window_coverage(
        report, candidate_trade_window_count=1, minimum=2
    )
    assert result["portfolio_verdict"] == "portfolio_reject"
    assert "insufficient_candidate_window_coverage" in result["evidence_blockers"]
    assert result["checks"]["candidate_trade_window_coverage"] is False


def test_price_snapshot_cannot_replay_against_a_drifting_candidate_scan(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="evidence-manifest"):
        audit.run_reassessment(
            experiment_id="exp-test",
            output_dir=tmp_path / "out",
            ohlcv_snapshot_path=tmp_path / "prices.json.gz",
            bootstrap_replicates=10,
        )


def test_frozen_snapshot_requires_expected_hash_and_matching_sidecar(
    tmp_path: Path,
) -> None:
    payload = {
        "experiment_id": "exp-test",
        "rows": [],
        "potential_requested_pair_count": 0,
        "actual_consumed_pair_count": 0,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    compressed = gzip.compress(raw, mtime=0)
    digest = hashlib.sha256(compressed).hexdigest()
    path = tmp_path / "rows.json.gz"
    path.write_bytes(compressed)
    path.with_name(f"{path.name}.sha256").write_text(
        f"{digest}  {path.name}\n", encoding="ascii"
    )
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        audit._load_ohlcv_snapshot(
            path,
            expected_experiment_id="exp-test",
            expected_gzip_sha256="0" * 64,
        )
    rows, identity = audit._load_ohlcv_snapshot(
        path,
        expected_experiment_id="exp-test",
        expected_gzip_sha256=digest,
    )
    assert rows == []
    assert identity["gzip_sha256"] == digest


def test_recursive_manifest_normalizes_and_deduplicates_surfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    for experiment_id in ("exp-20250101-001", "exp-20250101-002"):
        _write_json(
            tmp_path / "experiments" / "tickets" / f"{experiment_id}.json",
            {
                "experiment_id": experiment_id,
                "status": "rejected",
                "lane": "alpha_search",
                "result": {"decision": "rejected"},
            },
        )
        _write_json(
            tmp_path / "experiments" / "logs" / f"{experiment_id}.json",
            {
                "experiment_id": experiment_id,
                "status": "rejected",
                "before_metrics": {
                    "benchmarks": {"strategy_total_return_pct": 0.10},
                    "sharpe_daily": 2.0,
                    "expected_value_score": 0.20,
                },
                "after_metrics": {},
            },
        )

    first = "exp-20250101-001"
    second = "exp-20250101-002"
    first_surface = _surface(explicit_notional=False)
    first_surface["late_strong"].append(
        {"ticker": "observer-only", "entry_date": "2025-01-02"}
    )
    _write_json(
        tmp_path / "data" / "experiments" / first / "nested" / "candidate.json",
        {
            "experiment_id": first,
            "target_trades_by_window": first_surface,
            "sharpe_inference": {
                "return_series": [
                    {"date": "2025-01-02", "return": 0.01},
                    {"date": "2025-01-03", "return": -0.005},
                ]
            },
        },
    )
    _write_json(
        tmp_path / "data" / "experiments" / second / "candidate.json",
        {
            "experiment_id": second,
            "target_trades_by_window": _surface(explicit_notional=True),
        },
    )

    _, _, ticket_by_id = audit.scan_experiment_tickets()
    _, _, log_by_id = audit.scan_experiment_logs()
    rows, eligible, summary = audit.scan_top_level_artifacts(
        log_by_id, ticket_by_id
    )

    assert summary["experiment_json_artifact_count"] == 2
    assert summary["target_trade_artifact_count"] == 2
    assert summary["eligible_unique_trade_surface_count"] == 1
    assert summary["derived_paper_notional_row_count"] == 3
    assert summary["excluded_embedded_row_count"] == 1
    assert summary["artifact_with_exact_daily_series_count"] == 1
    assert summary["aliased_behavior_surface_count"] == 1
    assert summary["duplicate_alias_artifact_count"] == 1
    assert eligible[0]["experiment_id"] == first
    assert eligible[0]["surface_alias_count"] == 2
    assert any(row["artifact_disposition"] == "duplicate_trade_surface" for row in rows)


def test_simultaneous_bounds_are_seed_deterministic() -> None:
    core = {
        window: np.asarray([0.01, -0.002, 0.004, 0.003, -0.001], dtype=float)
        for window in audit.WINDOWS
    }
    candidate = {
        "candidate-a": {
            window: np.asarray([0.012, -0.001, 0.005, 0.004, 0.0], dtype=float)
            for window in audit.WINDOWS
        },
        "candidate-b": {
            window: np.asarray([0.0, 0.0, 0.0, 0.0, 0.0], dtype=float)
            for window in audit.WINDOWS
        },
    }
    first = audit.simultaneous_current_bounds(
        core, candidate, replicates=200, block_length=2, seed=42
    )
    second = audit.simultaneous_current_bounds(
        core, candidate, replicates=200, block_length=2, seed=42
    )
    assert first == second
