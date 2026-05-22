from __future__ import annotations

from event_sleeve_bundle import (
    build_event_sleeve_bundle_trade_plan,
    build_event_sleeve_bundle_snapshot,
    evaluate_event_bundle_kill_switch,
    evaluate_forward_paper_gate,
)


def _sleeve(
    *,
    candidate_count: int = 0,
    new_pending_count: int = 0,
    filled_count: int = 0,
    closed_count_today: int = 0,
    skipped_count_today: int = 0,
    pending_count: int = 0,
    open_position_count: int = 0,
    closed_position_count: int = 0,
    realized_pnl_to_date: float = 0.0,
    unrealized_pnl: float = 0.0,
    open_positions: list[dict[str, object]] | None = None,
    closed_positions_today: list[dict[str, object]] | None = None,
    closed_positions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": candidate_count,
        "new_pending_count": new_pending_count,
        "filled_count": filled_count,
        "closed_count_today": closed_count_today,
        "skipped_count_today": skipped_count_today,
        "pending_count": pending_count,
        "open_position_count": open_position_count,
        "closed_position_count": closed_position_count,
        "realized_pnl_to_date": realized_pnl_to_date,
        "unrealized_pnl": unrealized_pnl,
        "open_positions": open_positions or [],
        "closed_positions_today": closed_positions_today or [],
        "closed_positions": closed_positions or [],
    }


def test_event_sleeve_bundle_aggregates_sources_without_trade_authority() -> None:
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-04",
        form4_event_sleeve=_sleeve(
            candidate_count=2,
            new_pending_count=1,
            pending_count=1,
            open_position_count=1,
            realized_pnl_to_date=120.25,
            unrealized_pnl=-10.0,
            open_positions=[{"ticker": "INTC"}],
        ),
        sec_negative_event_sleeve=_sleeve(
            candidate_count=1,
            filled_count=1,
            closed_count_today=1,
            closed_position_count=1,
            realized_pnl_to_date=220.0,
            closed_positions_today=[{"ticker": "LITE"}],
        ),
        sec_governance_event_sleeve=_sleeve(
            candidate_count=3,
            skipped_count_today=1,
            open_position_count=1,
            unrealized_pnl=30.5,
            open_positions=[{"ticker": "CRDO"}],
        ),
    )

    assert snapshot["enabled"] is False
    assert snapshot["trade_enabled"] is False
    assert snapshot["candidate_count"] == 6
    assert snapshot["new_pending_count"] == 1
    assert snapshot["filled_count"] == 1
    assert snapshot["closed_count_today"] == 1
    assert snapshot["skipped_count_today"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["open_position_count"] == 2
    assert snapshot["closed_position_count"] == 1
    assert snapshot["realized_pnl_to_date"] == 340.25
    assert snapshot["unrealized_pnl"] == 20.5
    assert {row["source"] for row in snapshot["open_positions"]} == {
        "form4_meaningful_purchase",
        "sec_governance_procedural",
    }
    assert snapshot["closed_positions_today"][0]["source"] == "sec_negative_reaction"
    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["production_impact"]["alters_sizing"] is False
    assert snapshot["trade_plan"]["status"] == "blocked"
    assert snapshot["trade_plan"]["trade_enabled"] is False
    assert "trade_adapter_disabled" in snapshot["trade_plan"]["block_reasons"]


def test_event_sleeve_bundle_normalizes_candidates_and_dedupes_by_priority() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-04",
        form4_event_queue={
            "rule_version": "form4_rule",
            "candidates": [
                {
                    "ticker": "XYZ",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                }
            ],
        },
        sec_negative_event_queue={
            "rule_version": "sec_negative_rule",
            "candidates": [
                {
                    "ticker": "XYZ",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                }
            ],
        },
        sec_governance_event_queue={
            "rule_version": "sec_governance_rule",
            "candidates": [
                {
                    "ticker": "XYZ",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "ABC",
                    "usable_trade_date": "2026-05-04",
                    "reaction_bucket": "reaction_-2_to_0",
                    "counterfactual": counterfactual,
                },
            ],
        },
    )

    assert snapshot["raw_candidate_count"] == 4
    assert snapshot["deduped_candidate_count"] == 2
    assert snapshot["duplicate_candidate_count"] == 2
    assert snapshot["candidate_schema"]["audit"]["valid"] is True
    xyz = [row for row in snapshot["candidates"] if row["ticker"] == "XYZ"]
    assert len(xyz) == 1
    assert xyz[0]["source"] == "sec_governance_procedural"
    assert {row["source"] for row in snapshot["deduped_candidates"]} == {
        "sec_negative_reaction",
        "form4_meaningful_purchase",
    }
    abc = [row for row in snapshot["candidates"] if row["ticker"] == "ABC"]
    assert abc[0]["reaction_bucket"] == "reaction_-2_to_0"
    assert all(row["alters_orders"] is False for row in snapshot["candidates"])


def test_event_sleeve_bundle_marks_non_generic_state_surface_addon_without_orders() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-04",
        form4_event_queue={
            "rule_version": "form4_rule",
            "candidates": [
                {
                    "ticker": "EVT",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "BREAD",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "BAL",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "NEG",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                },
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 3,
            "scored_candidates": [
                {
                    "ticker": "EVT",
                    "score": 1.24,
                    "surface": "rotation_breakout_leadership",
                    "decision_date": "2026-05-04",
                },
                {
                    "ticker": "BAL",
                    "score": 1.11,
                    "surface": "balanced_state_leadership",
                    "decision_date": "2026-05-04",
                },
                {
                    "ticker": "BREAD",
                    "score": 0.33,
                    "surface": "broad_breadth_trend_persistence",
                    "decision_date": "2026-05-04",
                },
                {
                    "ticker": "NEG",
                    "score": -0.22,
                    "surface": "broad_breadth_trend_persistence",
                    "decision_date": "2026-05-04",
                },
            ],
        },
    )

    by_ticker = {row["ticker"]: row for row in snapshot["candidates"]}
    addon = by_ticker["EVT"]["state_surface_addon"]
    assert addon["eligible"] is True
    assert addon["reason"] == "eligible_rotation_breakout_positive_state_surface_positive_state_context"
    assert addon["scalar"] == 3.75
    assert addon["base_event_notional_usd"] == 10000.0
    assert addon["adjusted_event_notional_usd"] == 37500.0
    assert addon["incremental_notional_usd"] == 27500.0
    assert addon["rotation_tilt"] is True
    assert addon["positive_state_context_tilt"] is True
    assert by_ticker["EVT"]["paper_event_notional_usd"] == 37500.0
    assert by_ticker["EVT"]["event_notional_usd"] == 10000.0
    assert by_ticker["EVT"]["trade_enabled"] is False
    assert by_ticker["EVT"]["alters_orders"] is False
    bread = by_ticker["BREAD"]["state_surface_addon"]
    assert bread["reason"] == "eligible_non_generic_positive_state_surface_positive_state_context"
    assert bread["scalar"] == 2.5
    assert bread["rotation_tilt"] is False
    assert (
        by_ticker["BAL"]["state_surface_addon"]["reason"]
        == "generic_state_surface_positive_state_context"
    )
    assert by_ticker["NEG"]["state_surface_addon"]["reason"] == "nonpositive_state_surface_score"
    assert snapshot["state_surface_addon"]["eligible_candidate_count"] == 2
    assert snapshot["state_surface_addon"]["rotation_tilt_candidate_count"] == 1
    assert snapshot["state_surface_addon"]["positive_state_context_tilt_candidate_count"] == 3
    assert snapshot["state_surface_addon"]["incremental_notional_usd"] == 45000.0
    assert (
        snapshot["state_surface_addon"]["rotation_tilt_incremental_notional_usd"]
        == 20000.0
    )
    assert (
        snapshot["state_surface_addon"]["positive_state_context_tilt_incremental_notional_usd"]
        == 15000.0
    )
    assert snapshot["state_surface_addon"]["production_impact"]["alters_orders"] is False
    assert snapshot["trade_plan"]["trade_enabled"] is False


def test_event_sleeve_bundle_applies_front_rank_rotation_tilt_without_orders() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-20",
        form4_event_queue={
            "rule_version": "form4_rule",
            "candidates": [
                {
                    "ticker": "LITE",
                    "usable_trade_date": "2026-05-20",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "SLOW",
                    "usable_trade_date": "2026-05-20",
                    "counterfactual": counterfactual,
                },
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 10,
            "scored_candidates": [
                {
                    "ticker": "LITE",
                    "rank": 1,
                    "score": 1.24,
                    "surface": "rotation_breakout_leadership",
                    "decision_date": "2026-05-20",
                },
                {
                    "ticker": "SLOW",
                    "rank": 5,
                    "score": 0.71,
                    "surface": "rotation_breakout_leadership",
                    "decision_date": "2026-05-20",
                },
            ],
        },
    )

    by_ticker = {row["ticker"]: row for row in snapshot["candidates"]}
    front = by_ticker["LITE"]["state_surface_addon"]
    assert front["eligible"] is True
    assert front["reason"] == "eligible_front_rank_rotation_breakout_positive_state_surface_positive_state_context"
    assert front["scalar"] == 5.0
    assert front["state_rank"] == 1
    assert front["state_rank_pct"] == 0.1
    assert front["rotation_tilt"] is True
    assert front["front_rank_rotation_tilt"] is True
    assert by_ticker["LITE"]["paper_event_notional_usd"] == 50000.0
    assert by_ticker["LITE"]["trade_enabled"] is False
    assert by_ticker["LITE"]["alters_orders"] is False

    slower = by_ticker["SLOW"]["state_surface_addon"]
    assert slower["reason"] == "eligible_rotation_breakout_positive_state_surface_positive_state_context"
    assert slower["scalar"] == 3.75
    assert slower["state_rank_pct"] == 0.5
    assert slower["front_rank_rotation_tilt"] is False

    summary = snapshot["state_surface_addon"]
    assert summary["rotation_tilt_candidate_count"] == 2
    assert summary["front_rank_rotation_tilt_candidate_count"] == 1
    assert summary["positive_state_context_tilt_candidate_count"] == 2
    assert summary["rotation_tilt_incremental_notional_usd"] == 50000.0
    assert summary["front_rank_rotation_tilt_incremental_notional_usd"] == 30000.0
    assert summary["parameters"]["front_rank_rotation_max_rank_pct"] == 0.2
    assert summary["parameters"]["front_rank_rotation_tilt_scalar"] == 4.0
    assert snapshot["trade_plan"]["trade_enabled"] is False


def test_event_sleeve_bundle_applies_broad_breadth_event_tilt_without_orders() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-21",
        form4_event_queue={
            "rule_version": "form4_rule",
            "candidates": [
                {
                    "ticker": "WIDE",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "BREAD",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "PLAIN",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                },
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 10,
            "scored_candidates": [
                {
                    "ticker": "WIDE",
                    "rank": 1,
                    "score": 1.24,
                    "surface": "rotation_breakout_leadership",
                    "breadth_bucket": "broad_breadth",
                    "decision_date": "2026-05-21",
                },
                {
                    "ticker": "BREAD",
                    "rank": 4,
                    "score": 0.84,
                    "surface": "broad_breadth_trend_persistence",
                    "breadth_bucket": "broad_breadth",
                    "decision_date": "2026-05-21",
                },
                {
                    "ticker": "PLAIN",
                    "rank": 5,
                    "score": 0.71,
                    "surface": "broad_breadth_trend_persistence",
                    "breadth_bucket": "mixed_breadth",
                    "decision_date": "2026-05-21",
                },
            ],
        },
    )

    by_ticker = {row["ticker"]: row for row in snapshot["candidates"]}
    front = by_ticker["WIDE"]["state_surface_addon"]
    assert front["front_rank_rotation_tilt"] is True
    assert front["broad_breadth_tilt"] is True
    assert front["broad_breadth_scalar"] == 1.25
    assert front["scalar"] == 6.25
    assert by_ticker["WIDE"]["paper_event_notional_usd"] == 62500.0
    assert by_ticker["WIDE"]["alters_orders"] is False

    broad = by_ticker["BREAD"]["state_surface_addon"]
    assert broad["reason"] == "eligible_non_generic_positive_state_surface_broad_breadth_support_positive_state_context"
    assert broad["broad_breadth_tilt"] is True
    assert broad["scalar"] == 3.125
    assert by_ticker["BREAD"]["paper_event_notional_usd"] == 31250.0

    plain = by_ticker["PLAIN"]["state_surface_addon"]
    assert plain["broad_breadth_tilt"] is False
    assert plain["scalar"] == 2.5
    assert by_ticker["PLAIN"]["paper_event_notional_usd"] == 25000.0

    summary = snapshot["state_surface_addon"]
    assert summary["broad_breadth_tilt_candidate_count"] == 2
    assert summary["positive_state_context_tilt_candidate_count"] == 3
    assert summary["broad_breadth_tilt_incremental_notional_usd"] == 15000.0
    assert summary["parameters"]["broad_breadth_bucket"] == "broad_breadth"
    assert summary["parameters"]["broad_breadth_tilt_scalar"] == 1.25
    assert snapshot["trade_plan"]["trade_enabled"] is False


def test_event_sleeve_bundle_applies_governance_source_quality_tilt_without_orders() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-21",
        sec_governance_event_queue={
            "rule_version": "sec_governance_rule",
            "candidates": [
                {
                    "ticker": "GOV",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "GBRD",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                },
            ],
        },
        sec_negative_event_queue={
            "rule_version": "sec_negative_rule",
            "candidates": [
                {
                    "ticker": "NBRD",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                }
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 8,
            "scored_candidates": [
                {
                    "ticker": "GOV",
                    "rank": 6,
                    "score": 0.91,
                    "surface": "balanced_state_leadership",
                    "breadth_bucket": "mixed_breadth",
                    "decision_date": "2026-05-21",
                },
                {
                    "ticker": "GBRD",
                    "rank": 3,
                    "score": 1.03,
                    "surface": "broad_breadth_trend_persistence",
                    "breadth_bucket": "broad_breadth",
                    "decision_date": "2026-05-21",
                },
                {
                    "ticker": "NBRD",
                    "rank": 4,
                    "score": 0.88,
                    "surface": "broad_breadth_trend_persistence",
                    "breadth_bucket": "broad_breadth",
                    "decision_date": "2026-05-21",
                },
            ],
        },
    )

    by_ticker = {row["ticker"]: row for row in snapshot["candidates"]}
    gov = by_ticker["GOV"]["state_surface_addon"]
    assert gov["eligible"] is False
    assert gov["reason"] == "generic_state_surface_sec_governance_source_quality_positive_state_context"
    assert gov["source_quality_tilt"] is True
    assert gov["source_quality_scalar"] == 2.0
    assert gov["state_surface_scalar"] == 1.0
    assert gov["scalar"] == 2.5
    assert by_ticker["GOV"]["paper_event_notional_usd"] == 25000.0
    assert by_ticker["GOV"]["alters_orders"] is False

    gov_broad = by_ticker["GBRD"]["state_surface_addon"]
    assert gov_broad["eligible"] is True
    assert gov_broad["broad_breadth_tilt"] is True
    assert gov_broad["source_quality_tilt"] is True
    assert gov_broad["state_surface_scalar"] == 2.5
    assert gov_broad["scalar"] == 6.25
    assert by_ticker["GBRD"]["paper_event_notional_usd"] == 62500.0

    neg_broad = by_ticker["NBRD"]["state_surface_addon"]
    assert neg_broad["source_quality_tilt"] is False
    assert neg_broad["scalar"] == 3.125
    assert by_ticker["NBRD"]["paper_event_notional_usd"] == 31250.0

    summary = snapshot["state_surface_addon"]
    assert summary["eligible_candidate_count"] == 2
    assert summary["broad_breadth_tilt_candidate_count"] == 2
    assert summary["source_quality_tilt_candidate_count"] == 2
    assert summary["positive_state_context_tilt_candidate_count"] == 3
    assert summary["incremental_notional_usd"] == 88750.0
    assert summary["broad_breadth_tilt_incremental_notional_usd"] == 10000.0
    assert summary["source_quality_tilt_incremental_notional_usd"] == 35000.0
    assert summary["parameters"]["source_quality_source"] == "sec_governance_procedural"
    assert summary["parameters"]["source_quality_tilt_scalar"] == 2.0
    assert snapshot["trade_plan"]["trade_enabled"] is False


def test_event_sleeve_bundle_applies_negative_reaction_tilt_without_orders() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-21",
        sec_negative_event_queue={
            "rule_version": "sec_negative_rule",
            "candidates": [
                {
                    "ticker": "NNEG",
                    "usable_trade_date": "2026-05-21",
                    "reaction_bucket": "reaction_-2_to_0",
                    "counterfactual": counterfactual,
                }
            ],
        },
        sec_governance_event_queue={
            "rule_version": "sec_governance_rule",
            "candidates": [
                {
                    "ticker": "GNEG",
                    "usable_trade_date": "2026-05-21",
                    "reaction_bucket": "negative_excess_0_to_minus_2pct",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "GPOS",
                    "usable_trade_date": "2026-05-21",
                    "reaction_bucket": "positive_excess_0_to_2pct",
                    "counterfactual": counterfactual,
                },
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 8,
            "scored_candidates": [
                {
                    "ticker": "NNEG",
                    "rank": 2,
                    "score": 0.84,
                    "surface": "broad_breadth_trend_persistence",
                    "breadth_bucket": "broad_breadth",
                    "decision_date": "2026-05-21",
                },
                {
                    "ticker": "GNEG",
                    "rank": 6,
                    "score": 0.91,
                    "surface": "balanced_state_leadership",
                    "breadth_bucket": "mixed_breadth",
                    "decision_date": "2026-05-21",
                },
                {
                    "ticker": "GPOS",
                    "rank": 7,
                    "score": 0.76,
                    "surface": "balanced_state_leadership",
                    "breadth_bucket": "mixed_breadth",
                    "decision_date": "2026-05-21",
                },
            ],
        },
    )

    by_ticker = {row["ticker"]: row for row in snapshot["candidates"]}
    neg = by_ticker["NNEG"]["state_surface_addon"]
    assert neg["eligible"] is True
    assert neg["broad_breadth_tilt"] is True
    assert neg["negative_reaction_tilt"] is True
    assert neg["positive_state_context_tilt"] is True
    assert neg["negative_reaction_bucket"] == "reaction_-2_to_0"
    assert neg["state_surface_scalar"] == 2.5
    assert neg["negative_reaction_scalar"] == 2.0
    assert neg["positive_state_context_scalar"] == 1.25
    assert neg["scalar"] == 6.25
    assert by_ticker["NNEG"]["paper_event_notional_usd"] == 62500.0
    assert by_ticker["NNEG"]["alters_orders"] is False

    gov_neg = by_ticker["GNEG"]["state_surface_addon"]
    assert gov_neg["eligible"] is False
    assert gov_neg["source_quality_tilt"] is True
    assert gov_neg["negative_reaction_tilt"] is True
    assert gov_neg["positive_state_context_tilt"] is True
    assert gov_neg["source_quality_scalar"] == 2.0
    assert gov_neg["negative_reaction_scalar"] == 2.0
    assert gov_neg["positive_state_context_scalar"] == 1.25
    assert gov_neg["scalar"] == 5.0
    assert (
        gov_neg["reason"]
        == "generic_state_surface_sec_governance_source_quality_negative_reaction_support_positive_state_context"
    )
    assert by_ticker["GNEG"]["paper_event_notional_usd"] == 50000.0

    gov_pos = by_ticker["GPOS"]["state_surface_addon"]
    assert gov_pos["source_quality_tilt"] is True
    assert gov_pos["negative_reaction_tilt"] is False
    assert gov_pos["positive_state_context_tilt"] is True
    assert gov_pos["scalar"] == 2.5
    assert by_ticker["GPOS"]["paper_event_notional_usd"] == 25000.0

    summary = snapshot["state_surface_addon"]
    assert summary["source_quality_tilt_candidate_count"] == 2
    assert summary["negative_reaction_tilt_candidate_count"] == 2
    assert summary["positive_state_context_tilt_candidate_count"] == 3
    assert summary["source_quality_tilt_incremental_notional_usd"] == 20000.0
    assert summary["negative_reaction_tilt_incremental_notional_usd"] == 45000.0
    assert summary["positive_state_context_tilt_incremental_notional_usd"] == 27500.0
    assert summary["incremental_notional_usd"] == 107500.0
    assert "reaction_-2_to_0" in summary["parameters"]["negative_reaction_buckets"]
    assert summary["parameters"]["negative_reaction_tilt_scalar"] == 2.0
    assert summary["parameters"]["positive_state_context_tilt_scalar"] == 1.25
    assert snapshot["trade_plan"]["trade_enabled"] is False


def test_event_sleeve_bundle_applies_governance_503_haircut_without_orders() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-22",
        sec_governance_event_queue={
            "rule_version": "sec_governance_rule",
            "candidates": [
                {
                    "ticker": "G503",
                    "usable_trade_date": "2026-05-22",
                    "eight_k_item_codes": ["5.03", "9.01"],
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "GN03",
                    "usable_trade_date": "2026-05-22",
                    "eight_k_item_codes": ["9.01"],
                    "counterfactual": counterfactual,
                },
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 2,
            "scored_candidates": [
                {
                    "ticker": "G503",
                    "score": 0.64,
                    "surface": "balanced_state_leadership",
                    "state_bucket": "narrow_cap_weight_leadership",
                    "decision_date": "2026-05-22",
                },
                {
                    "ticker": "GN03",
                    "score": 0.64,
                    "surface": "balanced_state_leadership",
                    "state_bucket": "narrow_cap_weight_leadership",
                    "decision_date": "2026-05-22",
                },
            ],
        },
    )

    by_ticker = {row["ticker"]: row for row in snapshot["candidates"]}
    haircut = by_ticker["G503"]["state_surface_addon"]
    assert by_ticker["G503"]["eight_k_item_codes"] == ["5.03", "9.01"]
    assert haircut["source_quality_tilt"] is True
    assert haircut["positive_state_context_tilt"] is True
    assert haircut["governance_503_haircut"] is True
    assert haircut["governance_503_haircut_scalar"] == 0.25
    assert haircut["scalar"] == 0.625
    assert haircut["pre_governance_503_adjusted_event_notional_usd"] == 25000.0
    assert haircut["governance_503_haircut_incremental_notional_usd"] == -18750.0
    assert by_ticker["G503"]["paper_event_notional_usd"] == 6250.0
    assert by_ticker["G503"]["alters_orders"] is False

    no_haircut = by_ticker["GN03"]["state_surface_addon"]
    assert no_haircut["source_quality_tilt"] is True
    assert no_haircut["positive_state_context_tilt"] is True
    assert no_haircut["governance_503_haircut"] is False
    assert no_haircut["scalar"] == 2.5
    assert by_ticker["GN03"]["paper_event_notional_usd"] == 25000.0

    summary = snapshot["state_surface_addon"]
    assert summary["governance_503_haircut_candidate_count"] == 1
    assert summary["source_quality_tilt_incremental_notional_usd"] == 20000.0
    assert summary["positive_state_context_tilt_incremental_notional_usd"] == 10000.0
    assert summary["governance_503_haircut_incremental_notional_usd"] == -18750.0
    assert summary["incremental_notional_usd"] == 11250.0
    assert summary["parameters"]["governance_503_haircut_scalar"] == 0.25
    assert "5.03" in summary["parameters"]["governance_503_item_codes"]
    assert snapshot["trade_plan"]["trade_enabled"] is False


def test_event_sleeve_bundle_applies_non_narrow_state_context_without_orders() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-21",
        form4_event_queue={
            "rule_version": "form4_rule",
            "candidates": [
                {
                    "ticker": "NNR",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                }
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 3,
            "scored_candidates": [
                {
                    "ticker": "NNR",
                    "rank": 2,
                    "score": -0.10,
                    "surface": "balanced_state_leadership",
                    "state_bucket": "balanced_risk_on",
                    "breadth_bucket": "mixed_breadth",
                    "decision_date": "2026-05-21",
                }
            ],
        },
    )

    addon = snapshot["candidates"][0]["state_surface_addon"]
    assert addon["eligible"] is False
    assert addon["positive_state_context_tilt"] is False
    assert addon["non_narrow_state_context_tilt"] is True
    assert addon["state_bucket"] == "balanced_risk_on"
    assert addon["non_narrow_state_context_scalar"] == 1.15
    assert addon["scalar"] == 1.15
    assert snapshot["candidates"][0]["paper_event_notional_usd"] == 11500.0
    assert snapshot["candidates"][0]["alters_orders"] is False

    summary = snapshot["state_surface_addon"]
    assert summary["non_narrow_state_context_tilt_candidate_count"] == 1
    assert summary["non_narrow_state_context_tilt_incremental_notional_usd"] == 1500.0
    assert summary["parameters"]["non_narrow_state_context_tilt_scalar"] == 1.15
    assert (
        "balanced_risk_on"
        in summary["parameters"]["non_narrow_state_context_state_buckets"]
    )
    assert snapshot["trade_plan"]["trade_enabled"] is False


def test_event_bundle_trade_plan_stays_blocked_until_explicit_enablement() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-04",
        form4_event_queue={
            "rule_version": "form4_rule",
            "candidates": [
                {
                    "ticker": "EVT",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                }
            ],
        },
    )

    trade_plan = build_event_sleeve_bundle_trade_plan(snapshot)

    assert trade_plan["status"] == "blocked"
    assert trade_plan["trade_enabled"] is False
    assert trade_plan["actions"] == []
    assert "trade_adapter_disabled" in trade_plan["block_reasons"]
    assert "forward_paper_gate_blocked" in trade_plan["block_reasons"]
    assert trade_plan["production_impact"]["alters_orders"] is False


def test_event_bundle_trade_plan_emits_same_gated_action_when_gate_passes() -> None:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-04",
        form4_event_queue={
            "rule_version": "form4_rule",
            "candidates": [
                {
                    "ticker": "EVT",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": counterfactual,
                }
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 1,
            "scored_candidates": [
                {
                    "ticker": "EVT",
                    "score": 1.24,
                    "surface": "rotation_breakout_leadership",
                    "decision_date": "2026-05-04",
                }
            ],
        },
    )
    snapshot["forward_paper_gate"] = {
        "passed": True,
        "status": "passed",
        "reasons": [],
    }
    snapshot["kill_switch"] = {"triggered": False, "status": "clear", "reasons": []}

    trade_plan = build_event_sleeve_bundle_trade_plan(
        snapshot,
        config={"trade_enabled": True, "micro_live_notional_usd": 2500.0},
        portfolio_value=200_000.0,
    )

    assert trade_plan["status"] == "ready"
    assert trade_plan["trade_enabled"] is True
    assert trade_plan["block_reasons"] == []
    assert trade_plan["action_count"] == 1
    action = trade_plan["actions"][0]
    assert action["ticker"] == "EVT"
    assert action["action"] == "BUY"
    assert action["notional_usd"] == 2500.0
    assert action["entry_timing"] == "next_session_open"
    assert action["state_surface_addon"]["trade_enabled"] is True
    assert action["state_surface_addon"]["scalar"] == 3.75
    assert trade_plan["production_impact"]["alters_orders"] is True


def test_forward_paper_gate_passes_after_sufficient_source_diverse_outcomes() -> None:
    closed = []
    for idx in range(15):
        source = "sec_governance_procedural" if idx < 8 else "sec_negative_reaction"
        pnl = 100.0 if idx in {0, 1, 2, 3, 4, 5, 8, 9, 10, 11} else -20.0
        closed.append(
            {
                "source": source,
                "ticker": f"T{idx}",
                "exit_date": f"2026-05-{idx + 1:02d}",
                "pnl": pnl,
            }
        )

    gate = evaluate_forward_paper_gate(
        closed_positions=closed,
        source_summaries={},
        schema_audit={"valid": True},
    )

    assert gate["passed"] is True
    assert gate["metrics"]["closed_trades"] == 15
    assert gate["metrics"]["win_rate"] == 0.6667
    assert set(gate["metrics"]["represented_sources"]) == {
        "sec_governance_procedural",
        "sec_negative_reaction",
    }


def test_event_bundle_kill_switch_trips_on_three_consecutive_losses() -> None:
    closed = [
        {"source": "form4_meaningful_purchase", "exit_date": "2026-05-01", "pnl": 50.0},
        {"source": "form4_meaningful_purchase", "exit_date": "2026-05-02", "pnl": -10.0},
        {"source": "form4_meaningful_purchase", "exit_date": "2026-05-03", "pnl": -20.0},
        {"source": "form4_meaningful_purchase", "exit_date": "2026-05-04", "pnl": -30.0},
    ]

    kill = evaluate_event_bundle_kill_switch(
        closed_positions=closed,
        schema_audit={"valid": True},
    )

    assert kill["triggered"] is True
    assert "consecutive_closed_losses" in kill["reasons"]


def test_event_sleeve_bundle_reports_missing_source_as_zero() -> None:
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-04",
        form4_event_sleeve=_sleeve(candidate_count=1),
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["source_summaries"]["sec_negative_reaction"]["available"] is False
    assert snapshot["source_summaries"]["sec_negative_reaction"]["status"] == "missing_snapshot"


def test_report_generator_renders_event_sleeve_bundle_without_orders() -> None:
    from report_generator import generate_daily_report

    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-04",
        form4_event_sleeve=_sleeve(candidate_count=1, pending_count=1),
        sec_negative_event_sleeve=_sleeve(candidate_count=1, open_position_count=1),
        sec_governance_event_sleeve=_sleeve(candidate_count=1, closed_count_today=1),
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        event_sleeve_bundle=snapshot,
    )

    assert "DEFAULT-OFF EVENT OVERLAY BUNDLE" in report
    assert "Trade enabled: False" in report
    assert "Form 4 meaningful purchase" in report
    assert "SEC negative reaction" in report
    assert "SEC governance/procedural" in report


def test_report_generator_renders_event_state_surface_addon_attribution() -> None:
    from report_generator import generate_daily_report

    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-04",
        form4_event_queue={
            "rule_version": "form4_rule",
            "candidates": [
                {
                    "ticker": "EVT",
                    "usable_trade_date": "2026-05-04",
                    "counterfactual": {"frozen": True},
                }
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 1,
            "scored_candidates": [
                {
                    "ticker": "EVT",
                    "score": 1.24,
                    "surface": "rotation_breakout_leadership",
                    "decision_date": "2026-05-04",
                }
            ],
        },
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        event_sleeve_bundle=snapshot,
    )

    assert "State-surface add-on:" in report
    assert "eligible=1/1" in report
    assert "incremental=$27,500.00" in report
    assert "rotation=1" in report
    assert "front_rank=0" in report
    assert "positive_state=1" in report
    assert "surfaces=rotation_breakout_leadership" in report
