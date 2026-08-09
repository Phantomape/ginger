"""Tests for the in-flight open-ticket duplicate guard (exp-20260714-007).

The frozen-family novelty gate only sees closed experiments, so concurrent
agents could reserve the same hypothesis twice; the loser burned the ID as
duplicate_reservation_accounting. evaluate_in_flight_duplicate_guard is the
machine form of the AGENTS.md §7 pre-reserve self-check.
"""

import datetime
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as efp  # noqa: E402
from create_experiment_ticket import (  # noqa: E402
    evaluate_in_flight_duplicate_guard,
)

TODAY = datetime.date(2026, 7, 14)

DUP_HYPOTHESIS = (
    "Observed-only event-decision-basket alpha: collapse settled "
    "entity_theme_news observer rows by exact URL, equal-weight each unique "
    "mapped ticker inside the URL, then equal-weight each URL event."
)


def _args(**overrides):
    base = {
        "lane": "alpha_search",
        "hypothesis": DUP_HYPOTHESIS,
        "single_causal_variable": "entity_theme_news_exact_url_event_basket",
        "changed_variable": "entity_theme_news_exact_url_event_basket",
        "trial_family": "entity_theme_news_event_decision_basket",
        "mechanism_family": "entity_theme_news_event_decision_basket",
        "file_slug": "entity_theme_event_basket",
        "experiment_id": None,
        "in_flight_duplicate_override": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _fingerprint_for(args):
    return efp.infer_fingerprint(
        args.hypothesis or "",
        args.single_causal_variable or "",
        args.trial_family or "",
        args.mechanism_family or "",
        args.file_slug or "",
    )


def _write_ticket(root, experiment_id, *, status, hypothesis, created_days_ago=0, **extra):
    tickets = root / "experiments" / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": experiment_id,
        "status": status,
        "hypothesis": hypothesis,
        "owner": extra.pop("owner", None),
        "single_causal_variable": extra.pop("single_causal_variable", ""),
        "trial_family": extra.pop("trial_family", ""),
        "mechanism_family": extra.pop("mechanism_family", ""),
        "changed_variable": extra.pop("changed_variable", ""),
    }
    payload.update(extra)
    (tickets / f"{experiment_id}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_blocks_verbatim_duplicate_of_open_ticket(tmp_path):
    _write_ticket(
        tmp_path,
        "exp-20260713-099",
        status="proposed",
        hypothesis=DUP_HYPOTHESIS,
        single_causal_variable="entity_theme_news_exact_url_event_basket",
        trial_family="entity_theme_news_event_decision_basket",
        owner="other-agent",
    )
    args = _args()
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["applicable"] is True
    assert verdict["blocked"] is True
    assert verdict["matches"][0]["experiment_id"] == "exp-20260713-099"
    assert verdict["matches"][0]["score"] >= verdict["threshold"]


def test_blocks_unclassified_other_source_duplicate(tmp_path):
    # Verbatim duplicates whose data_source falls to "other" are exactly the
    # classifier escape AGENTS.md §2.4 warns about; the raw tag Jaccard must
    # still catch them even though the classified distance stays low.
    hypothesis = (
        "A brand new never-classified widget telemetry stream may surface "
        "pre-announcement demand shifts for one covered issuer."
    )
    _write_ticket(
        tmp_path,
        "exp-20260714-098",
        status="claimed",
        hypothesis=hypothesis,
        owner="other-agent",
    )
    args = _args(
        hypothesis=hypothesis,
        single_causal_variable="",
        changed_variable="",
        trial_family="",
        mechanism_family="",
        file_slug="",
    )
    fingerprint = _fingerprint_for(args)
    assert fingerprint["data_source"] == "other"
    verdict = evaluate_in_flight_duplicate_guard(
        args, fingerprint, repo_root=tmp_path, today=TODAY
    )
    assert verdict["blocked"] is True


def test_blocks_rephrased_duplicate(tmp_path):
    # The live 2026-07-14 miss: a rephrased (not verbatim) duplicate scored
    # just under the old 0.75 threshold because trial/mechanism family
    # default-fill happens at reserve time, not check time. The calibrated
    # 0.65 default must catch a same-idea rephrase.
    _write_ticket(
        tmp_path,
        "exp-20260713-099",
        status="claimed",
        hypothesis=(
            "Observed-only event-decision basket: dedupe settled "
            "entity_theme_news observer rows by URL, weight each mapped "
            "ticker equally within the URL, and weight each URL event "
            "equally to test replacement value."
        ),
        single_causal_variable="entity_theme_news_exact_url_event_basket",
        owner="other-agent",
    )
    args = _args(
        trial_family="",
        mechanism_family="",
        file_slug="",
    )
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["blocked"] is True


def test_ignores_closed_ticket(tmp_path):
    _write_ticket(
        tmp_path,
        "exp-20260713-099",
        status="rejected",
        hypothesis=DUP_HYPOTHESIS,
        single_causal_variable="entity_theme_news_exact_url_event_basket",
    )
    args = _args()
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["blocked"] is False
    assert verdict["matches"] == []


def test_ignores_stale_open_ticket_outside_window(tmp_path):
    # Months-old proposed tickets (e.g. the April backlog) are stale, not
    # in-flight; the ID date prefix keeps them from false-blocking new work.
    _write_ticket(
        tmp_path,
        "exp-20260426-040",
        status="proposed",
        hypothesis=DUP_HYPOTHESIS,
        single_causal_variable="entity_theme_news_exact_url_event_basket",
    )
    args = _args()
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["blocked"] is False
    assert verdict["matches"] == []


def test_allows_distinct_hypothesis_same_window(tmp_path):
    _write_ticket(
        tmp_path,
        "exp-20260713-099",
        status="proposed",
        hypothesis=(
            "Shared-paper-first candidate-pool alpha: an official FDIC "
            "Quarterly Banking Profile first release may lead regional bank "
            "relative strength."
        ),
        single_causal_variable="fdic_qbp_first_release_candidate_pool",
        trial_family="fdic_quarterly_banking_profile_candidate_pool",
    )
    args = _args()
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["blocked"] is False
    assert verdict["matches"] == []


def test_override_records_and_unblocks(tmp_path):
    _write_ticket(
        tmp_path,
        "exp-20260713-099",
        status="proposed",
        hypothesis=DUP_HYPOTHESIS,
        single_causal_variable="entity_theme_news_exact_url_event_basket",
        trial_family="entity_theme_news_event_decision_basket",
    )
    args = _args(in_flight_duplicate_override=True)
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["blocked"] is False
    assert verdict["override_accepted"] is True
    assert verdict["matches"]


def test_fails_safe_without_tickets_dir(tmp_path):
    args = _args()
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["applicable"] is False
    assert verdict["blocked"] is False


def test_skips_own_explicit_experiment_id(tmp_path):
    _write_ticket(
        tmp_path,
        "exp-20260714-050",
        status="proposed",
        hypothesis=DUP_HYPOTHESIS,
        single_causal_variable="entity_theme_news_exact_url_event_basket",
        trial_family="entity_theme_news_event_decision_basket",
    )
    args = _args(experiment_id="exp-20260714-050")
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["blocked"] is False
    assert verdict["matches"] == []


def test_corrupt_ticket_json_is_skipped(tmp_path):
    tickets = tmp_path / "experiments" / "tickets"
    tickets.mkdir(parents=True)
    (tickets / "exp-20260714-097.json").write_text("{not json", encoding="utf-8")
    _write_ticket(
        tmp_path,
        "exp-20260714-096",
        status="proposed",
        hypothesis=DUP_HYPOTHESIS,
        single_causal_variable="entity_theme_news_exact_url_event_basket",
        trial_family="entity_theme_news_event_decision_basket",
    )
    args = _args()
    verdict = evaluate_in_flight_duplicate_guard(
        args, _fingerprint_for(args), repo_root=tmp_path, today=TODAY
    )
    assert verdict["blocked"] is True
    assert verdict["matches"][0]["experiment_id"] == "exp-20260714-096"
