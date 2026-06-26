from __future__ import annotations

from quant.short_volume_clean_flow_gate import (
    apply_clean_flow_gate,
    build_short_volume_percentile_index,
)


def _history_with_high_latest() -> dict[str, list[tuple[str, float]]]:
    rows = []
    for idx in range(30):
        rows.append((f"2026-01-{idx + 1:02d}", 0.10 + idx * 0.001))
    rows.append(("2026-02-02", 0.50))
    return {"TOP": rows}


def test_toxic_entry_date_percentile_is_rejected() -> None:
    index = build_short_volume_percentile_index(_history_with_high_latest())

    kept, rejected, audit = apply_clean_flow_gate(
        [
            {
                "ticker": "TOP",
                "signal_date": "2026-02-02",
                "entry_date": "2026-02-03",
            }
        ],
        index,
    )

    assert kept == []
    assert len(rejected) == 1
    assert rejected[0]["short_volume_ratio_quintile"] == 4
    assert rejected[0]["clean_flow_gate_reason"] == "toxic_short_volume_quintile"
    assert audit["rejected_count"] == 1


def test_signal_date_snapshot_can_use_same_day_activity_after_close() -> None:
    index = build_short_volume_percentile_index(_history_with_high_latest())

    kept, rejected, _audit = apply_clean_flow_gate(
        [{"ticker": "TOP", "signal_date": "2026-02-02"}],
        index,
    )

    assert kept == []
    assert len(rejected) == 1
    assert rejected[0]["short_volume_ratio_cutoff_basis"] == (
        "signal_date_activity_available_after_close"
    )


def test_missing_percentile_is_kept_not_failed_closed() -> None:
    index = build_short_volume_percentile_index(_history_with_high_latest())

    kept, rejected, audit = apply_clean_flow_gate(
        [{"ticker": "NEW", "signal_date": "2026-02-02", "entry_date": "2026-02-03"}],
        index,
    )

    assert len(kept) == 1
    assert rejected == []
    assert kept[0]["clean_flow_gate_reason"] == "missing_short_volume_percentile_kept"
    assert audit["missing_percentile_kept"] is True
