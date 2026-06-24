"""Tests for the daily resting bracket-order playbook."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import bracket_orders as bo  # noqa: E402


def _plan(positions, prices, prior=None):
    return bo.build_bracket_orders(
        {"positions": positions}, prices, asof_date="2026-06-22", prior_orders=prior
    )


def test_normal_position_emits_both_legs():
    plan = _plan(
        [{"ticker": "HOOD", "shares": 10, "avg_cost": 105.20, "entry_stop_price": 95.0,
          "stop_price": 90.73, "target_price": 126.24}],
        {"HOOD": 110.0},
    )
    by_leg = {o["leg"]: o for o in plan["orders"]}
    assert by_leg["target"]["order_type"] == "LIMIT" and by_leg["target"]["price"] == 126.24
    assert by_leg["target"]["action"] == "PLACE" and by_leg["target"]["tif"] == "GTC"
    # static entry stop (95.0) preferred over the trailed stop_price (90.73)
    assert by_leg["stop"]["order_type"] == "STOP" and by_leg["stop"]["price"] == 95.0
    assert by_leg["stop"]["action"] == "PLACE" and by_leg["stop"]["stop_basis"] == "static_entry"
    assert plan["summary"]["resting_orders_to_maintain"] == 2
    assert plan["summary"]["stops_static_entry"] == 1
    assert plan["warnings"] == []


def test_static_entry_stop_preferred_over_trailed():
    # NVDA: trailed stop_price 194.08 but static entry stop 160 -> emit the static one
    # (exp-20260623-020: static is EV-optimal, do not trail).
    plan = _plan(
        [{"ticker": "NVDA", "shares": 5, "avg_cost": 177.24, "entry_stop_price": 160.0,
          "stop_price": 194.08, "target_price": 212.69}],
        {"NVDA": 205.0},
    )
    stop = next(o for o in plan["orders"] if o["leg"] == "stop")
    assert stop["price"] == 160.0 and stop["stop_basis"] == "static_entry"
    assert stop["action"] == "PLACE"


def test_trailed_fallback_when_no_entry_stop():
    # No entry_stop_price -> fall back to the trailed stop_price, but warn.
    plan = _plan(
        [{"ticker": "FOO", "shares": 5, "avg_cost": 100.0, "stop_price": 95.0, "target_price": 120.0}],
        {"FOO": 110.0},
    )
    stop = next(o for o in plan["orders"] if o["leg"] == "stop")
    assert stop["price"] == 95.0 and stop["stop_basis"] == "trailed_fallback"
    assert plan["summary"]["stops_trailed_fallback"] == 1
    assert any("TRAILED" in w and "FOO" in w for w in plan["warnings"])


def test_runner_past_target_keeps_static_stop_no_limit():
    # AMD: price (551) blew through the recorded target (209) long ago; the STATIC
    # entry stop (150) is below market. -> runner: place the static stop, no resting
    # limit, flag the stale target. The trailed 483 is NOT used.
    plan = _plan(
        [{"ticker": "AMD", "shares": 7, "avg_cost": 174.21, "entry_stop_price": 150.0,
          "stop_price": 483.39, "target_price": 209.06}],
        {"AMD": 551.63},
    )
    stop = next(o for o in plan["orders"] if o["leg"] == "stop")
    assert stop["action"] == "PLACE" and stop["price"] == 150.0  # static, not trailed 483
    assert stop["stop_basis"] == "static_entry"
    assert not any(o["leg"] == "target" for o in plan["orders"])   # no resting limit
    assert plan["summary"]["past_target_runners"] == 1
    assert any("runner" in w and "AMD" in w for w in plan["warnings"])


def test_target_reached_without_protective_stop_flags_exit_now():
    # target reached and NO stop below market -> genuinely exit now.
    plan = _plan(
        [{"ticker": "FOO", "shares": 4, "avg_cost": 100.0, "stop_price": None, "target_price": 110.0}],
        {"FOO": 120.0},  # above target, no protective stop
    )
    target = next(o for o in plan["orders"] if o["leg"] == "target")
    assert target["action"] == "EXIT_NOW"
    assert plan["summary"]["exit_now_flags"] >= 1
    assert plan["summary"]["past_target_runners"] == 0


def test_stop_already_breached_flags_exit_now():
    plan = _plan(
        [{"ticker": "TRIP", "shares": 100, "avg_cost": 11.76, "stop_price": 11.40, "target_price": 14.11}],
        {"TRIP": 11.0},  # below stop
    )
    stop = next(o for o in plan["orders"] if o["leg"] == "stop")
    assert stop["action"] == "EXIT_NOW"


def test_trailing_stop_move_detected_vs_prior():
    prior = _plan(
        [{"ticker": "GOOG", "shares": 3, "avg_cost": 290.39, "stop_price": 310.0, "target_price": 348.47}],
        {"GOOG": 330.0},
    )
    plan = _plan(
        [{"ticker": "GOOG", "shares": 3, "avg_cost": 290.39, "stop_price": 325.2, "target_price": 348.47}],
        {"GOOG": 335.0},
        prior=prior,
    )
    stop = next(o for o in plan["orders"] if o["leg"] == "stop")
    assert stop["action"] == "MOVE"
    assert "310" in stop["note"] and "325" in stop["note"]


def test_missing_price_still_places_with_verify_note():
    plan = _plan(
        [{"ticker": "XYZ", "shares": 1, "avg_cost": 50.0, "stop_price": 45.0, "target_price": 60.0}],
        {},  # no price
    )
    assert all(o["action"] == "PLACE" for o in plan["orders"])
    assert all("unavailable" in o["note"] for o in plan["orders"])


def test_output_only_policy_and_no_submission():
    plan = _plan([{"ticker": "HOOD", "shares": 10, "avg_cost": 105.2, "stop_price": 90.7, "target_price": 126.2}], {"HOOD": 110.0})
    assert plan["policy"] == "output_only_operator_places_orders"
    section = bo.render_bracket_orders_section(plan)
    assert "does NOT submit" in section
    assert "HOOD" in section


def test_covers_all_holding_groups():
    # Holdings split across positions / core_positions / observations must all be covered.
    payload = {
        "positions": [{"ticker": "GOOG", "shares": 6, "avg_cost": 290.0, "stop_price": 280.0, "target_price": 348.0}],
        "core_positions": [{"ticker": "AMZN", "shares": 4, "avg_cost": 248.0, "stop_price": 230.0, "target_price": 300.0}],
        "observations": [{"ticker": "META", "shares": 2, "avg_cost": 500.0, "stop_price": 480.0, "target_price": 600.0}],
    }
    plan = bo.build_bracket_orders(payload, {"GOOG": 300, "AMZN": 260, "META": 520}, asof_date="2026-06-23")
    tickers = {o["ticker"] for o in plan["orders"]}
    assert {"GOOG", "AMZN", "META"} <= tickers  # all three groups covered
    assert plan["summary"]["positions"] == 3


def test_entry_stops_map_is_used():
    plan = bo.build_bracket_orders(
        {"core_positions": [{"ticker": "AMZN", "shares": 4, "avg_cost": 248.0, "stop_price": 230.0, "target_price": 300.0}]},
        {"AMZN": 260.0}, asof_date="2026-06-23", entry_stops={"AMZN": 215.0},
    )
    stop = next(o for o in plan["orders"] if o["leg"] == "stop")
    assert stop["price"] == 215.0 and stop["stop_basis"] == "static_entry"


def test_positions_stale_suppresses_executable_orders():
    plan = bo.build_bracket_orders(
        {"positions": [{"ticker": "GOOG", "shares": 6, "avg_cost": 290.0, "entry_stop_price": 270.0,
                        "stop_price": 280.0, "target_price": 348.0}]},
        {"GOOG": 300.0}, asof_date="2026-06-23", positions_stale=True,
    )
    assert plan["positions_stale"] is True
    assert plan["summary"]["resting_orders_to_maintain"] == 0  # nothing placeable
    assert all(o["action"] == "SKIP_STALE" for o in plan["orders"])
    assert any("STALE" in w for w in plan["warnings"])
    assert "POSITIONS STALE" in bo.render_bracket_orders_section(plan)


def test_zero_shares_skipped():
    plan = _plan([{"ticker": "GONE", "shares": 0, "avg_cost": 10, "stop_price": 9, "target_price": 12}], {"GONE": 11})
    assert plan["orders"] == []
