import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from canonical_state_vectors import build_canonical_state_vectors
from cross_sectional_ranking_surface import build_cross_sectional_ranking_surface
from daily_context_archive import build_breadth_context, build_theme_density_context
from expectation_drift_surface import compute_expectation_drift_state
from longitudinal_ranking_validation import build_longitudinal_validation_report
from ranking_attribution import build_ranking_attribution


def _features():
    return {
        "AAA": {
            "ticker": "AAA",
            "trend_score": 0.8,
            "breakout_20d": True,
            "above_200ma": True,
            "momentum_10d_pct": 0.05,
            "momentum_20d_pct": 0.18,
            "momentum_60d_pct": 0.40,
            "avg_historical_surprise_pct": 8.0,
        },
        "BBB": {
            "ticker": "BBB",
            "trend_score": 0.4,
            "breakout_20d": False,
            "above_200ma": True,
            "momentum_10d_pct": 0.01,
            "momentum_20d_pct": 0.03,
            "momentum_60d_pct": 0.05,
            "avg_historical_surprise_pct": 0.0,
        },
        "CCC": {
            "ticker": "CCC",
            "trend_score": 0.1,
            "breakout_20d": False,
            "above_200ma": False,
            "momentum_10d_pct": -0.04,
            "momentum_20d_pct": -0.12,
            "momentum_60d_pct": -0.25,
            "avg_historical_surprise_pct": -5.0,
        },
        "SPY": {
            "ticker": "SPY",
            "trend_score": 0.5,
            "breakout_20d": False,
            "above_200ma": True,
            "momentum_20d_pct": 0.02,
            "momentum_60d_pct": 0.04,
        },
        "QQQ": {
            "ticker": "QQQ",
            "trend_score": 0.6,
            "breakout_20d": False,
            "above_200ma": True,
            "momentum_20d_pct": 0.04,
            "momentum_60d_pct": 0.08,
        },
    }


def test_cross_sectional_ranking_persists_full_rows_for_coverage():
    features = _features()
    ranking = build_cross_sectional_ranking_surface(features)

    assert ranking["schema_version"] >= 2
    assert ranking["universe_count"] == len(features)
    assert len(ranking["rows"]) == len(features)
    assert {row["ticker"] for row in ranking["rows"]} == set(features)
    assert ranking["leaders"][0]["alpha_score"] >= ranking["laggards"][0]["alpha_score"]


def test_ranking_attribution_includes_compact_annotated_trades():
    ranking = build_cross_sectional_ranking_surface(_features())
    result = {
        "period": "unit",
        "expected_value_score": 1.23,
        "trades": [
            {"ticker": "AAA", "entry_price": 100, "stop_price": 90, "shares": 10, "pnl": 500},
            {"ticker": "CCC", "entry_price": 50, "stop_price": 45, "shares": 10, "pnl": -100},
        ],
    }

    report = build_ranking_attribution(result, ranking)

    assert report["schema_version"] >= 2
    assert report["coverage"]["trades_total"] == 2
    assert report["coverage"]["trades_with_alpha_score"] == 2
    assert len(report["annotated_trades"]) == 2
    assert all("alpha_score_rank_pct" in trade for trade in report["annotated_trades"])
    assert all("r_multiple" in trade for trade in report["annotated_trades"])


def test_longitudinal_validation_detects_top_outperformance():
    report = {
        "source_period": "unit",
        "coverage": {"trades_total": 2, "trades_with_alpha_score": 2},
        "annotated_trades": [
            {"ticker": "AAA", "alpha_score_rank_pct": 0.05, "pnl": 1000, "r_multiple": 2.0, "alpha_score_components": {"relative_strength": 0.9}},
            {"ticker": "CCC", "alpha_score_rank_pct": 0.90, "pnl": -100, "r_multiple": -0.5, "alpha_score_components": {"relative_strength": 0.1}},
        ],
    }

    validation = build_longitudinal_validation_report(ranking_attribution_report=report)

    assert validation["top_decile_minus_bottom_quintile_avg_pnl"] == 1100
    assert "top-ranked names outperform bottom-ranked names" in validation["evidence_summary"]
    assert validation["component_evidence_summary"][0]["component"] == "relative_strength"


def test_expectation_drift_handles_zero_previous_without_crashing():
    state = compute_expectation_drift_state(
        current_snapshot={"eps_estimate_current_qtr": 1.2, "analyst_count_current_qtr": 5},
        snapshot_7d_ago={"eps_estimate_current_qtr": 0, "analyst_count_current_qtr": 4},
        snapshot_30d_ago={"eps_estimate_current_qtr": 1.0, "analyst_count_current_qtr": 3},
    )

    assert state["eps_revision_velocity_7d"] is None
    assert state["eps_revision_velocity_30d"] == 0.2
    assert state["analyst_participation_delta_30d"] == 2
    assert 0 <= state["expectation_drift_score"] <= 1


def test_canonical_state_vectors_cover_full_ranking_rows():
    features = _features()
    breadth = build_breadth_context(features)
    theme_density = build_theme_density_context(features)
    ranking = build_cross_sectional_ranking_surface(
        features,
        breadth_context=breadth,
        theme_density_context=theme_density,
        expectation_context={"rows": []},
    )
    bundle = {
        "leadership_persistence_surface": {"leaders": [], "weakening": []},
        "residual_strength_surface": {"leaders": [], "laggards": []},
        "expectation_drift_surface": {"leaders": [], "negative_revision": []},
        "theme_lifecycle_surface": {"themes": []},
        "cross_sectional_ranking_surface": ranking,
    }

    vectors = build_canonical_state_vectors(
        market_state_bundle=bundle,
        breadth_context=breadth,
        earnings_context={"rows": []},
        post_earnings_context={"rows": []},
    )

    assert vectors["summary"]["ticker_count"] == len(features)
    assert set(vectors["ticker_vectors"]) == set(features)
    for ticker, state in vectors["ticker_vectors"].items():
        assert set(vectors["vector_names"]) == set(state)
        assert 0 <= state["leadership_vector"]["score"] <= 1
