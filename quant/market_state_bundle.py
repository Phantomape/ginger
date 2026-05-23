"""Unified market-state bundle.

Aggregates the continuous market-state surfaces into one replayable snapshot:
- breadth / internal structure
- theme lifecycle
- residual strength
- leadership persistence
- expectation drift
- cross-sectional ranking

This is a passive intelligence bundle only.
"""

from __future__ import annotations

from cross_sectional_ranking_surface import build_cross_sectional_ranking_surface
from expectation_drift_surface import build_expectation_drift_surface
from leadership_persistence_surface import build_leadership_surface
from residual_strength_surface import build_residual_strength_surface
from theme_lifecycle_surface import build_theme_lifecycle_surface


def build_market_state_bundle(
    *,
    features_dict,
    breadth_context=None,
    theme_density_context=None,
    expectation_context=None,
    expectation_snapshot_history=None,
):
    """Build unified replayable market-state bundle."""

    leadership_surface = build_leadership_surface(features_dict)

    residual_surface = build_residual_strength_surface(features_dict)

    theme_lifecycle_surface = build_theme_lifecycle_surface(features_dict)

    expectation_surface = build_expectation_drift_surface(
        expectation_snapshot_history or {}
    )

    ranking_surface = build_cross_sectional_ranking_surface(
        features_dict,
        breadth_context=breadth_context,
        theme_density_context=theme_density_context,
        expectation_context=expectation_context,
    )

    return {
        "schema_version": 1,
        "read_only": True,
        "leadership_persistence_surface": leadership_surface,
        "residual_strength_surface": residual_surface,
        "theme_lifecycle_surface": theme_lifecycle_surface,
        "expectation_drift_surface": expectation_surface,
        "cross_sectional_ranking_surface": ranking_surface,
        "summary": {
            "persistent_leader_count": leadership_surface["distribution"].get("persistent_leader_count"),
            "strong_residual_leader_count": residual_surface["distribution"].get("strong_residual_leader_count"),
            "theme_mania_count": theme_lifecycle_surface["state_counts"].get("mania"),
            "theme_exhaustion_count": theme_lifecycle_surface["state_counts"].get("exhaustion"),
            "strong_positive_revision_count": expectation_surface["distribution"].get("strong_positive_revision_count"),
            "top_alpha_score": ranking_surface["distribution"].get("max_alpha_score"),
        },
        "notes": [
            "Unified replayable market-state context bundle.",
            "Designed for attribution and future context-aware allocation research.",
            "Does not alter live trading decisions.",
        ],
    }
