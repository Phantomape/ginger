"""Tests for regime_tagged_scorecard.build_scorecard (pure aggregation)."""

from __future__ import annotations

import json

from regime_tagged_scorecard import build_scorecard, load_forward_paper_rows, load_forward_replacement_rows


def _stub_regime(mapping):
    def _fn(asof):
        return mapping.get(asof)
    return _fn


def test_tags_and_buckets_rows_by_regime():
    rows = [
        {"sleeve": "A", "ticker": "X", "entry_date": "2026-05-01", "replacement_value_vs_spy_usd": 100.0},
        {"sleeve": "A", "ticker": "Y", "entry_date": "2026-05-02", "replacement_value_vs_spy_usd": -80.0},
        {"sleeve": "B", "ticker": "Z", "entry_date": "2026-05-03", "replacement_value_vs_spy_usd": 50.0},
    ]
    regime_fn = _stub_regime({
        "2026-05-01": {"regime_label": "risk_on_trend", "p_choppy_range": 0.1, "exposure_scalar": 0.95},
        "2026-05-02": {"regime_label": "choppy_range", "p_choppy_range": 0.7, "exposure_scalar": 0.65},
        "2026-05-03": {"regime_label": "risk_on_trend", "p_choppy_range": 0.2, "exposure_scalar": 0.9},
    })
    sc = build_scorecard(rows, regime_fn)
    assert sc["tagged_rows"] == 3
    assert sc["by_regime"]["choppy_range"]["count"] == 1
    assert sc["by_regime"]["choppy_range"]["mean_replacement_value_vs_spy_usd"] == -80.0
    assert sc["by_regime"]["risk_on_trend"]["count"] == 2
    assert sc["tiny_sample_warning"] is True


def test_soft_tilt_helps_when_chop_rows_are_losers():
    # chop row is the loser and gets the lowest exposure -> exposure weighting
    # should raise the mean replacement value above equal-weight.
    rows = [
        {"entry_date": "d1", "replacement_value_vs_spy_usd": 100.0},
        {"entry_date": "d2", "replacement_value_vs_spy_usd": -100.0},
    ]
    regime_fn = _stub_regime({
        "d1": {"regime_label": "risk_on_trend", "p_choppy_range": 0.1, "exposure_scalar": 1.0},
        "d2": {"regime_label": "choppy_range", "p_choppy_range": 0.8, "exposure_scalar": 0.5},
    })
    sc = build_scorecard(rows, regime_fn)
    ct = sc["soft_tilt_counterfactual"]
    assert ct["equal_weight_mean_rv_vs_spy_usd"] == 0.0
    # weighted = (1.0*100 + 0.5*-100)/(1.5) = 33.33 > 0
    assert ct["exposure_weighted_mean_rv_vs_spy_usd"] > 0
    assert ct["tilt_gain_usd"] > 0


def test_unknown_regime_rows_are_untagged():
    rows = [{"entry_date": "d1", "replacement_value_vs_spy_usd": 10.0}]
    sc = build_scorecard(rows, _stub_regime({"d1": {"regime_label": "unknown"}}))
    assert sc["tagged_rows"] == 0
    assert sc["untagged_rows"] == 1


def test_missing_rv_still_tags_but_excluded_from_rv_mean():
    rows = [{"entry_date": "d1", "replacement_value_vs_spy_usd": None}]
    regime_fn = _stub_regime({"d1": {"regime_label": "risk_on_trend", "p_choppy_range": 0.1, "exposure_scalar": 0.9}})
    sc = build_scorecard(rows, regime_fn)
    assert sc["tagged_rows"] == 1
    assert sc["by_regime"]["risk_on_trend"]["mean_replacement_value_vs_spy_usd"] is None


def test_load_forward_replacement_rows_normalizes_and_dedups(tmp_path):
    artifact = tmp_path / "forward_replacement_value.jsonl"
    rows = [
        {
            "decision_id": "d1",
            "sleeve_key": "sleeve_a",
            "ticker": "ABC",
            "entry_date": "2026-06-01",
            "exit_date": "2026-06-10",
            "pnl_usd": 10,
            "replacement_value_vs_spy_usd": 5,
            "entry_regime_label": "risk_on_trend",
            "entry_regime_exposure_scalar": 0.9,
        },
        {
            "decision_id": "d1",
            "sleeve_key": "sleeve_a",
            "ticker": "ABC",
            "entry_date": "2026-06-01",
            "exit_date": "2026-06-11",
            "pnl_usd": 12,
            "replacement_value_vs_spy_usd": 7,
            "entry_regime_label": "risk_on_trend",
            "entry_regime_exposure_scalar": 0.91,
        },
    ]
    artifact.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    loaded = load_forward_replacement_rows(artifact)

    assert len(loaded) == 1
    assert loaded[0]["source"] == "forward_replacement_value"
    assert loaded[0]["sleeve"] == "sleeve_a"
    assert loaded[0]["exit_date"] == "2026-06-11"
    assert loaded[0]["pnl"] == 12
    assert loaded[0]["entry_regime_exposure_scalar"] == 0.91


def test_load_forward_paper_rows_prefers_canonical_artifact(tmp_path):
    artifact = tmp_path / "forward_replacement_value.jsonl"
    artifact.write_text(json.dumps({
        "decision_id": "canonical",
        "sleeve_key": "canonical_sleeve",
        "ticker": "CAN",
        "entry_date": "2026-06-02",
        "replacement_value_vs_spy_usd": 25,
        "entry_regime_label": "risk_on_trend",
    }) + "\n", encoding="utf-8")

    loaded = load_forward_paper_rows(forward_replacement_path=artifact)

    assert len(loaded) == 1
    assert loaded[0]["decision_id"] == "canonical"
    assert loaded[0]["sleeve"] == "canonical_sleeve"


def test_build_scorecard_uses_existing_entry_regime_fields():
    rows = [
        {
            "source": "forward_replacement_value",
            "decision_id": "d1",
            "sleeve": "A",
            "ticker": "X",
            "entry_date": "2026-06-01",
            "exit_date": "2026-06-10",
            "replacement_value_vs_cash_usd": 120.0,
            "replacement_value_vs_spy_usd": 100.0,
            "replacement_value_vs_qqq_usd": 80.0,
            "entry_regime_label": "choppy_range",
            "entry_regime_p_choppy_range": 0.8,
            "entry_regime_exposure_scalar": 0.5,
            "entry_regime_tag_rule_version": "forward_replacement_entry_regime_tag_v1",
        }
    ]

    sc = build_scorecard(rows, _stub_regime({}))

    assert sc["tagged_rows"] == 1
    tagged = sc["rows"][0]
    assert tagged["source"] == "forward_replacement_value"
    assert tagged["decision_id"] == "d1"
    assert tagged["regime_label"] == "choppy_range"
    assert tagged["regime_fidelity"] == "forward_replacement_entry_regime_tag_v1"
    assert tagged["replacement_value_vs_cash_usd"] == 120.0
    assert tagged["replacement_value_vs_qqq_usd"] == 80.0
