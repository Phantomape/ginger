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
    assert addon["reason"] == "eligible_non_generic_positive_state_surface"
    assert addon["scalar"] == 2.0
    assert addon["base_event_notional_usd"] == 10000.0
    assert addon["adjusted_event_notional_usd"] == 20000.0
    assert addon["incremental_notional_usd"] == 10000.0
    assert by_ticker["EVT"]["paper_event_notional_usd"] == 20000.0
    assert by_ticker["EVT"]["event_notional_usd"] == 10000.0
    assert by_ticker["EVT"]["trade_enabled"] is False
    assert by_ticker["EVT"]["alters_orders"] is False
    assert by_ticker["BAL"]["state_surface_addon"]["reason"] == "generic_state_surface"
    assert by_ticker["NEG"]["state_surface_addon"]["reason"] == "nonpositive_state_surface_score"
    assert snapshot["state_surface_addon"]["eligible_candidate_count"] == 1
    assert snapshot["state_surface_addon"]["incremental_notional_usd"] == 10000.0
    assert snapshot["state_surface_addon"]["production_impact"]["alters_orders"] is False
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
    assert action["state_surface_addon"]["scalar"] == 2.0
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
    assert "incremental=$10,000.00" in report
    assert "surfaces=rotation_breakout_leadership" in report
