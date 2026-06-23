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
        [{"ticker": "HOOD", "shares": 10, "avg_cost": 105.20, "stop_price": 90.73, "target_price": 126.24}],
        {"HOOD": 110.0},
    )
    by_leg = {o["leg"]: o for o in plan["orders"]}
    assert by_leg["target"]["order_type"] == "LIMIT" and by_leg["target"]["price"] == 126.24
    assert by_leg["target"]["action"] == "PLACE" and by_leg["target"]["tif"] == "GTC"
    assert by_leg["stop"]["order_type"] == "STOP" and by_leg["stop"]["price"] == 90.73
    assert by_leg["stop"]["action"] == "PLACE"
    assert plan["summary"]["resting_orders_to_maintain"] == 2
    assert plan["warnings"] == []


def test_trailing_stop_winner_is_valid():
    # NVDA: stop above cost but below target and below current -> valid trailing stop.
    plan = _plan(
        [{"ticker": "NVDA", "shares": 5, "avg_cost": 177.24, "stop_price": 194.08, "target_price": 212.69}],
        {"NVDA": 205.0},
    )
    stop = next(o for o in plan["orders"] if o["leg"] == "stop")
    assert stop["action"] == "PLACE" and stop["price"] == 194.08
    assert not any("CORRUPT" in w for w in plan["warnings"])


def test_runner_past_target_keeps_trailing_stop_no_limit():
    # AMD real shape: price (551) blew through the recorded target (209) long ago;
    # stop (483) is a valid trailing stop BELOW market. -> runner: place the stop,
    # no resting limit, flag the stale target. The stop is NOT corrupt.
    plan = _plan(
        [{"ticker": "AMD", "shares": 7, "avg_cost": 174.21, "stop_price": 483.39, "target_price": 209.06}],
        {"AMD": 551.63},
    )
    stop = next(o for o in plan["orders"] if o["leg"] == "stop")
    assert stop["action"] == "PLACE" and stop["price"] == 483.39  # valid trailing stop
    assert not any(o["leg"] == "target" for o in plan["orders"])   # no resting limit
    assert plan["summary"]["past_target_runners"] == 1
    assert any("runner" in w and "AMD" in w for w in plan["warnings"])
    assert not any("CORRUPT" in w for w in plan["warnings"])


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


def test_zero_shares_skipped():
    plan = _plan([{"ticker": "GONE", "shares": 0, "avg_cost": 10, "stop_price": 9, "target_price": 12}], {"GONE": 11})
    assert plan["orders"] == []
