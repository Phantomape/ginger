"""Replay validation for the recipe-lane guard (exp-20260721-005).

Blocked set: real hypotheses from tickets burned in the documented lanes.
Control set: accepted or legitimately distinct tickets that must NOT match.

Run:
    .\\.venv\\Scripts\\python.exe -B -m pytest scripts\\test_recipe_lane_guard.py -q
"""

import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from create_experiment_ticket import (  # noqa: E402
    _load_recipe_lanes,
    classify_recipe_lane_match,
    evaluate_recipe_lane_guard,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tickets burned inside curated lanes: the guard must match them.
BURNED = [
    "exp-20260717-005",  # TSA checkpoint basket (official release lane)
    "exp-20260717-004",  # Fed H.8 bank-size pair (official release lane)
    "exp-20260716-005",  # PCAOB Form AP peer substitution (official release lane)
    "exp-20260715-007",  # Treasury auction bid-to-cover (official release lane)
    "exp-20260718-006",  # Hacker News attention (developer count lane)
    "exp-20260719-001",  # deps.dev Maven releases (developer count lane)
]

# Accepted or legitimately distinct tickets: the guard must NOT match.
CONTROLS = [
    "exp-20260711-004",  # MOVE relief shared paper sleeve (ACCEPTED)
    "exp-20260616-015",  # sbc burden improvement shared adapter (ACCEPTED)
    "exp-20260715-008",  # cash ledger execution repair (accepted measurement repair)
    "exp-20260620-009",  # supplier financing debt relief adapter (ACCEPTED)
]


def _ticket_text(experiment_id):
    path = os.path.join(REPO_ROOT, "experiments", "tickets", experiment_id + ".json")
    d = json.load(open(path, encoding="utf-8"))
    return " ".join(
        str(d.get(k) or "")
        for k in (
            "hypothesis",
            "single_causal_variable",
            "changed_variable",
            "trial_family",
            "mechanism_family",
        )
    )


def _args(lane="alpha_search", hypothesis="", override=False, axis=""):
    return types.SimpleNamespace(
        lane=lane,
        hypothesis=hypothesis,
        single_causal_variable="",
        changed_variable="",
        trial_family="",
        mechanism_family="",
        file_slug="",
        recipe_lane_override=override,
        new_evidence_axis=axis,
    )


def test_lanes_file_loads():
    lanes = _load_recipe_lanes()
    assert len(lanes) >= 5
    for lane in lanes:
        assert lane.get("lane_key")
        assert lane.get("source_cluster")
        assert lane.get("response_cluster")


def test_burned_tickets_match():
    lanes = _load_recipe_lanes()
    missed = []
    for eid in BURNED:
        matches = classify_recipe_lane_match(_ticket_text(eid), lanes)
        if not matches:
            missed.append(eid)
    assert not missed, f"guard failed to match burned tickets: {missed}"


def test_controls_do_not_match():
    lanes = _load_recipe_lanes()
    false_hits = []
    for eid in CONTROLS:
        matches = classify_recipe_lane_match(_ticket_text(eid), lanes)
        if matches:
            false_hits.append((eid, [m["lane_key"] for m in matches]))
    assert not false_hits, f"guard false-positived on controls: {false_hits}"


def test_guard_blocks_alpha_lane():
    text = _ticket_text("exp-20260717-005")
    result = evaluate_recipe_lane_guard(_args(hypothesis=text))
    assert result["applicable"]
    assert result["blocked"]


def test_guard_ignores_measurement_lane():
    text = _ticket_text("exp-20260717-005")
    result = evaluate_recipe_lane_guard(_args(lane="measurement_repair", hypothesis=text))
    assert not result["applicable"]
    assert not result["blocked"]


def test_override_requires_axis():
    text = _ticket_text("exp-20260717-005")
    no_axis = evaluate_recipe_lane_guard(_args(hypothesis=text, override=True))
    assert no_axis["blocked"]
    with_axis = evaluate_recipe_lane_guard(
        _args(hypothesis=text, override=True, axis="settled forward rows prove issuer mapping")
    )
    assert not with_axis["blocked"]
    assert with_axis["override_accepted"]


def test_batch_exit_only_when_unspent():
    # Developer lane: batch_exit_used=false -> explicit pooled batch passes.
    dev_batch = (
        "Single pooled batch over the remaining developer ecosystem count sources: "
        "github release and pypi package registry weekly count acceleration versus "
        "prior median, top 3 basket, fixed hold, evaluated once as one batch."
    )
    result = evaluate_recipe_lane_guard(_args(hypothesis=dev_batch))
    assert result["applicable"]
    assert result["batch_exit_detected"]
    assert not result["blocked"]

    # Official-release lane: batch_exit_used=true -> batch wording still blocks.
    official_batch = (
        "Single pooled batch over remaining official weekly release sources: "
        "treasury auction bid to cover and fdic call report basket, top 3, fixed hold."
    )
    result = evaluate_recipe_lane_guard(_args(hypothesis=official_batch))
    assert result["applicable"]
    assert result["blocked"]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
