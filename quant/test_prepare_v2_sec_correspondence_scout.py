from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/prepare_v2_sec_correspondence_scout.py"
SPEC = importlib.util.spec_from_file_location("prepare_v2_sec_correspondence_scout", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EXPECTED_SESSION_DATES = MODULE.EXPECTED_SESSION_DATES


def _rows(returns: list[float]) -> tuple[list[dict[str, object]], list[str]]:
    codes = [f"US.T{index:02d}" for index in range(len(returns))]
    rows = [
        {
            "code": code,
            "status": "usable",
            "entry_open": 100.0,
            "exit_close": 100.0 * (1.0 + value),
            "session_dates": EXPECTED_SESSION_DATES,
            "entry_date": EXPECTED_SESSION_DATES[0],
            "exit_date": EXPECTED_SESSION_DATES[-1],
        }
        for code, value in zip(codes, returns, strict=True)
    ]
    return rows, codes


def test_evaluate_positive_but_thin_is_inconclusive() -> None:
    rows, codes = _rows([-0.02] * 17)
    result = MODULE.evaluate_avoid_long_h5(
        rows,
        candidate_codes=codes,
        cost_bps=10.0,
        expected_session_dates=EXPECTED_SESSION_DATES,
    )
    assert result["directional_pass"] is True
    assert result["observed_only_lead_eligible"] is False
    assert result["diagnostic_disposition"] == "inconclusive_insufficient_sample"
    assert result["scientific_classification"] == "inconclusive_positive_scout"


def test_evaluate_falsifies_nonnegative_baseline() -> None:
    rows, codes = _rows([0.01] * 17)
    result = MODULE.evaluate_avoid_long_h5(
        rows,
        candidate_codes=codes,
        cost_bps=10.0,
        expected_session_dates=EXPECTED_SESSION_DATES,
    )
    assert result["directional_pass"] is False
    assert result["diagnostic_disposition"] == "rejected"


def test_evaluate_requires_exact_frozen_code_set() -> None:
    rows, codes = _rows([-0.02] * 10)
    with pytest.raises(ValueError, match="exactly match"):
        MODULE.evaluate_avoid_long_h5(
            rows[:-1],
            candidate_codes=codes,
            cost_bps=10.0,
            expected_session_dates=EXPECTED_SESSION_DATES,
        )


def test_evaluate_insufficient_coverage_is_not_falsification() -> None:
    rows, codes = _rows([-0.02] * 17)
    for index, row in enumerate(rows[9:], start=9):
        row.clear()
        row.update({"code": codes[index], "status": "missing"})
    result = MODULE.evaluate_avoid_long_h5(
        rows,
        candidate_codes=codes,
        cost_bps=10.0,
        expected_session_dates=EXPECTED_SESSION_DATES,
    )
    assert result["usable_security_count"] == 9
    assert result["diagnostic_disposition"] == "inconclusive_insufficient_sample"
    assert result["scientific_classification"] == "inconclusive_data_coverage"


def test_evaluate_rejects_duplicate_codes_h5_drift_and_nonpositive_exit() -> None:
    rows, codes = _rows([-0.02] * 10)
    with pytest.raises(ValueError, match="candidate codes must be unique"):
        MODULE.evaluate_avoid_long_h5(
            rows,
            candidate_codes=[*codes[:-1], codes[-2]],
            cost_bps=10.0,
            expected_session_dates=EXPECTED_SESSION_DATES,
        )
    rows[0]["session_dates"] = EXPECTED_SESSION_DATES[:-1]
    with pytest.raises(ValueError, match="exact frozen H5"):
        MODULE.evaluate_avoid_long_h5(
            rows,
            candidate_codes=codes,
            cost_bps=10.0,
            expected_session_dates=EXPECTED_SESSION_DATES,
        )
    rows[0]["session_dates"] = EXPECTED_SESSION_DATES
    rows[0]["exit_close"] = 0.0
    with pytest.raises(ValueError, match="finite positive prices"):
        MODULE.evaluate_avoid_long_h5(
            rows,
            candidate_codes=codes,
            cost_bps=10.0,
            expected_session_dates=EXPECTED_SESSION_DATES,
        )


def test_frozen_write_is_idempotent_but_rejects_drift(tmp_path: Path) -> None:
    path = tmp_path / "frozen.json"
    MODULE._write(path, {"trade_enabled": False, "value": 1})
    MODULE._write(path, {"trade_enabled": False, "value": 1})
    with pytest.raises(FileExistsError, match="refusing to mutate frozen artifact"):
        MODULE._write(path, {"trade_enabled": False, "value": 2})


def test_build_freezes_complete_correspondence_frame() -> None:
    with tempfile.TemporaryDirectory(
        prefix="correspondence-scout-", dir=ROOT / "data"
    ) as temp_dir:
        out_dir = Path(temp_dir)
        report = MODULE.build(
            freeze_at="2026-09-02T17:20:00Z",
            history_cutoff="2026-09-02T17:20:00Z",
            out_dir=out_dir,
        )
        assert report["source_row_count"] == 4183
        assert report["target_form_row_count"] == 67
        assert report["mapped_source_row_count"] == 20
        assert report["candidate_pool_count"] == 17
        assert report["primary_horizon_estimated_decision_count"] == 17
        assert report["disposition_counts"] == {
            "excluded": 2,
            "mapped": 20,
            "non_target_form": 4116,
            "unmapped": 45,
        }
        assert report["trade_enabled"] is False
        manifest = MODULE.json.loads(
            (out_dir / "source_disposition_manifest.json").read_text()
        )
        assert len(manifest["rows"]) == 4183
        assert sum(manifest["disposition_counts"].values()) == 4183
        pool = MODULE.json.loads((out_dir / "candidate_pool.json").read_text())
        assert pool["candidate_security_set_equals_mapped_deduplicated_set"] is True
        assert pool["candidate_count"] == 17
        decision = MODULE.json.loads((out_dir / "decision_record.json").read_text())
        assert decision["order_intent_count"] == 0
        assert decision["trade_enabled"] is False


def test_build_fails_closed_when_target_reachability_is_below_ten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = MODULE._parse_daily_index

    def only_nine(payload: bytes, *, form_date: str):
        rows = original(payload, form_date=form_date)
        kept = 0
        changed = []
        for row in rows:
            row = dict(row)
            if row["form_type"] == "CORRESP":
                if kept < 9:
                    kept += 1
                else:
                    row["form_type"] = "OTHER"
            changed.append(row)
        return changed

    monkeypatch.setattr(MODULE, "_parse_daily_index", only_nine)
    with pytest.raises(ValueError, match="disposition counts drifted|67 CORRESP"):
        MODULE.build(
            freeze_at="2026-09-02T17:20:00Z",
            history_cutoff="2026-09-02T17:20:00Z",
            out_dir=tmp_path,
        )
