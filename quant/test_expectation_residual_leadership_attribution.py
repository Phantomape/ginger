from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "experiments"))

from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    classify_bucket,
    classify_expectation,
    classify_scout_expectation,
    extract_candidate_rows,
    residual_context_for_candidate,
)


def test_classify_bucket_matrix():
    assert classify_bucket(True, True) == "A_positive_expectation_and_residual_leader"
    assert classify_bucket(True, False) == "B_positive_expectation_only"
    assert classify_bucket(False, True) == "C_residual_leader_only"
    assert classify_bucket(False, False) == "D_neither"


def test_expectation_join_uses_primary_7d_delta_without_fallback():
    positive = classify_expectation(
        {
            "estimate_revision_usable": True,
            "eps_estimate_delta_7d": 0.04,
            "eps_estimate_delta_prev": 0.01,
        }
    )
    assert positive["expectation_positive"] is True
    assert positive["expectation_coverage_gap"] is None

    missing_7d = classify_expectation(
        {
            "estimate_revision_usable": True,
            "eps_estimate_delta_7d": None,
            "eps_estimate_delta_prev": 0.10,
            "revision_direction_prev": "up",
        }
    )
    assert missing_7d["expectation_positive"] is False
    assert missing_7d["expectation_coverage_gap"] == "missing_eps_estimate_delta_7d"

    unusable = classify_expectation(
        {
            "estimate_revision_usable": False,
            "eps_estimate_delta_7d": 0.05,
        }
    )
    assert unusable["expectation_positive"] is False
    assert unusable["expectation_join_status"] == "ledger_row_not_usable"


def test_reconstructed_scout_can_flag_unusable_positive_delta():
    row = {
        "estimate_revision_usable": False,
        "eps_estimate_delta_7d": 0.05,
        "pit_caveat": "current_snapshot_created_after_asof",
    }

    primary = classify_expectation(row)
    scout = classify_scout_expectation(row)

    assert primary["expectation_positive"] is False
    assert scout["scout_expectation_positive"] is True
    assert scout["scout_source_quality"] == "non_pit_reconstructed"
    assert scout["scout_pit_caveat"] == "current_snapshot_created_after_asof"


def test_extract_candidate_rows_ignores_feature_only_trend_rows():
    quant_payload = {
        "signals": [{"ticker": "AAA", "strategy": "trend_long", "action": "BUY"}],
        "features": {
            "AAA": {"ticker": "AAA", "close": 10},
            "FEATUREONLY": {"ticker": "FEATUREONLY", "close": 20},
        },
        "entry_execution_plan": {
            "slot_sliced_signals": [{"ticker": "BBB", "strategy": "breakout_long"}],
            "deferred_breakout_signals": [],
        },
        "pilot_entry_execution_plan": {
            "tradeable_pilot_signals": [{"ticker": "CCC", "strategy": "pilot"}],
            "pilot_slot_sliced_signals": [],
        },
    }

    rows = extract_candidate_rows(quant_payload, "2026-05-25")

    assert [row["ticker"] for row in rows] == ["AAA", "BBB", "CCC"]
    assert "FEATUREONLY" not in {row["ticker"] for row in rows}
    assert {row["candidate_source"] for row in rows} == {
        "signals",
        "entry_execution_plan.slot_sliced_signals",
        "pilot_entry_execution_plan.tradeable_pilot_signals",
    }


def test_residual_context_uses_existing_residual_strength_logic():
    features = {
        "AAA": {
            "ticker": "AAA",
            "momentum_20d_pct": 0.18,
            "momentum_60d_pct": 0.35,
        },
        "SPY": {"ticker": "SPY", "momentum_20d_pct": 0.02},
        "QQQ": {"ticker": "QQQ", "momentum_20d_pct": 0.03},
    }

    row = residual_context_for_candidate({"ticker": "AAA"}, features)

    assert row["residual_context_status"] == "ok"
    assert row["residual_state"] in {"residual_leader", "strong_residual_leader"}
    assert row["residual_leader"] is True
