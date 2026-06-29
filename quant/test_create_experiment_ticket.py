import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from create_experiment_ticket import classify_saturated_source_axis  # noqa: E402


def test_saturated_source_axis_rejects_same_source_new_field_only():
    verdict = classify_saturated_source_axis(
        "same data source, same gate shape, new XBRL field never scanned before"
    )

    assert verdict["valid"] is False
    assert verdict["invalid_same_source_field_only"] is True
    assert verdict["categories"] == []


def test_saturated_source_axis_accepts_new_data_source():
    verdict = classify_saturated_source_axis(
        "new data source: PIT borrow fee and utilization sidecar"
    )

    assert verdict["valid"] is True
    assert verdict["categories"] == ["new_data_source"]


def test_saturated_source_axis_accepts_new_gate_shape():
    verdict = classify_saturated_source_axis(
        "new gate shape: shared forward default-off helper instead of candidate scan"
    )

    assert verdict["valid"] is True
    assert verdict["categories"] == ["new_gate_shape"]


def test_saturated_source_axis_accepts_more_forward_rows():
    verdict = classify_saturated_source_axis(
        "materially more closed forward rows with settled replacement value"
    )

    assert verdict["valid"] is True
    assert verdict["categories"] == ["materially_more_forward_rows"]
