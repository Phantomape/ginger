from quant import current_paper_core_allocator as allocator


def test_surface_inventory_matches_frozen_current_contract() -> None:
    identity = allocator.validate_inventory()
    assert identity["surface_count"] == 41
    assert identity["paper_enabled_count"] == 35
    assert identity["paper_disabled_count"] == 6
    assert len({row["surface"] for row in allocator.SURFACE_SPECS}) == 41


def test_conflict_graph_blocks_composite_child_double_count() -> None:
    assert allocator.has_overlap(
        {
            "accepted_source_consensus_paper_sleeve",
            "alpha_score_market_regime_paper_sleeve",
        }
    )
    assert allocator.has_overlap(
        {
            "event_sleeve_bundle",
            "sec_negative_event_sleeve",
        }
    )
    assert not allocator.has_overlap(
        {
            "macro_relief_leadership_paper_sleeve",
            "ai_optical_paper_sleeve",
        }
    )
    assert not allocator.has_overlap(
        {
            "industry_relative_laggard_repair_paper_sleeve",
            "volatility_relief_stock_leadership_paper_sleeve",
        }
    )
    assert not allocator.has_overlap(
        {
            "alpha_score_market_regime_paper_sleeve",
            "volume_breadth_breakout_paper_sleeve",
        }
    )
    assert allocator.has_overlap(
        {
            "free_data_cross_source_consensus_paper_sleeve",
            "alpha_score_market_regime_paper_sleeve",
        }
    )


def test_coarse_enumerator_is_complete_for_two_independent_surfaces() -> None:
    rows = list(allocator.enumerate_coarse_allocations(("a", "b")))
    assert rows == [
        {},
        {"a": 0.025},
        {"a": 0.05},
        {"b": 0.025},
        {"b": 0.05},
        {"a": 0.025, "b": 0.025},
        {"a": 0.025, "b": 0.05},
        {"a": 0.05, "b": 0.025},
        {"a": 0.05, "b": 0.05},
    ]


def test_refinement_respects_caps_and_can_fall_back_to_null() -> None:
    rows = list(allocator.enumerate_refined_allocations(("a", "b")))
    assert {} in rows
    assert {"a": 0.05, "b": 0.05} in rows
    assert all(sum(row.values()) <= 0.10 for row in rows)
    assert all(max(row.values(), default=0.0) <= 0.05 for row in rows)


def test_recent_ledger_maps_exactly_to_registered_surfaces() -> None:
    recent = allocator.recent_surface_diagnostics()
    assert recent["row_count"] == 196
    assert recent["covered_surface_count"] == 21
    assert set(recent["surfaces"]) == {row["surface"] for row in allocator.SURFACE_SPECS}


def test_corrected_current_domain_has_exact_expected_vector_counts() -> None:
    reconstructed = allocator.reconstruct_surfaces()
    eligible = tuple(sorted(reconstructed["surface_returns"]))
    counts: dict[int, int] = {}
    total = 0
    for weights in allocator.enumerate_coarse_allocations(eligible):
        active = len(weights)
        counts[active] = counts.get(active, 0) + 1
        total += 1
    assert len(eligible) == 21
    assert counts == {0: 1, 1: 42, 2: 824, 3: 5032, 4: 5372}
    assert total == 11271
    eligible_set = set(eligible)
    assert sum(1 for edge in allocator.CONFLICT_EDGES if edge <= eligible_set) == 4


def test_module_is_evaluation_only() -> None:
    assert allocator.EXPERIMENT_ID == "exp-20260817-001"
    assert allocator.TOTAL_PAPER_CAP == 0.10
    assert allocator.MAX_ACTIVE_SURFACES == 4
