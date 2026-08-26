import pytest

import scripts.build_frozen_families as frozen


def test_duplicate_accounting_does_not_count_or_replace_reopen_metadata():
    owner = {
        "experiment_id": "exp-20260723-004",
        "trial_family": "core_drawdown_flow_put_stabilization_observer",
        "changed_variable": "shared_default_off_observer_v1",
        "trial_variant_id": "exp-20260723-004",
        "status": "accepted",
        "decision": "accepted",
        "post_run_reflection": {
            "realized_failure_mode": "none",
            "new_evidence_required": (
                "At least 20 independent settled forward positions under the frozen rule."
            ),
        },
    }
    duplicate = {
        "experiment_id": "exp-20260723-005",
        "trial_family": "core_drawdown_flow_put_stabilization_observer",
        "changed_variable": "duplicate_reservation_accounting",
        "trial_variant_id": "exp-20260723-005",
        "status": "rejected",
        "decision": "rejected",
        "post_run_reflection": {
            "realized_failure_mode": "duplicate_reservation_accounting",
            "new_evidence_required": "TODO",
        },
    }

    rows = frozen.build_rows([owner, duplicate])

    assert len(rows) == 1
    row = rows[0]
    assert row["family_key"] == "core_drawdown_flow_put_stabilization_observer"
    assert row["trials"] == 1
    assert row["accepted"] == 1
    assert row["rejected"] == 0
    assert row["representative_exps"] == ["exp-20260723-004"]
    assert row["reopen_condition"] == (
        "At least 20 independent settled forward positions under the frozen rule."
    )


def test_nonduplicate_failure_modes_remain_substantive_trials():
    records = [
        {
            "experiment_id": "exp-1",
            "trial_family": "ordinary_family",
            "status": "accepted",
            "post_run_reflection": {"realized_failure_mode": "none"},
        },
        {
            "experiment_id": "exp-2",
            "trial_family": "ordinary_family",
            "status": "rejected",
            "calibration": {"realized_failure_mode": "insufficient_density"},
        },
    ]

    row = frozen.build_rows(records)[0]

    assert row["trials"] == 2
    assert row["accepted"] == 1
    assert row["rejected"] == 1
    assert row["representative_exps"] == ["exp-1", "exp-2"]


def test_duplicate_marker_is_read_from_log_or_nested_ticket_shapes():
    owner = {
        "experiment_id": "exp-owner",
        "trial_family": "family",
        "status": "accepted",
    }
    duplicate_shapes = [
        {"calibration": {"realized_failure_mode": "duplicate_reservation_accounting"}},
        {
            "result": {
                "calibration": {
                    "realized_failure_mode": "duplicate_reservation_accounting"
                }
            }
        },
    ]

    for index, shape in enumerate(duplicate_shapes):
        duplicate = {
            "experiment_id": f"exp-duplicate-{index}",
            "trial_family": "family",
            "status": "rejected",
            "realized_failure_mode": "none",
            **shape,
        }
        row = frozen.build_rows([owner, duplicate])[0]
        assert row["trials"] == 1
        assert row["representative_exps"] == ["exp-owner"]


def test_private_replay_scout_ticket_fills_only_missing_family_metadata():
    record = {
        "experiment_id": "exp-scout",
        "record_type": "v2_private_replay_scout_result",
        "changed_variable": "presence_in_complete_source_frame",
        "status": "rejected",
        "decision": "rejected",
        "artifact": "data/experiments/exp-scout/result.json",
        "artifact_sha256": "a" * 64,
        "post_run_reflection": {
            "new_evidence_required": "A separately frozen later complete frame.",
        },
    }
    ticket = {
        "experiment_id": "exp-scout",
        "change_type": "private_replay_scout",
        "trial_family": "complete_frame_scout",
        "mechanism_family": "complete_frame_underreaction",
        "trial_variant_id": "exp-scout",
        "status": "rejected",
        "result": {
            "decision": "rejected",
            "artifact": "data/experiments/exp-scout/result.json",
            "artifact_sha256": "a" * 64,
        },
    }

    overlaid = frozen.overlay_private_replay_scout_trial_metadata(
        [record], [ticket]
    )
    row = frozen.build_rows(overlaid)[0]

    assert record.get("trial_family") is None
    assert overlaid[0]["trial_family"] == "complete_frame_scout"
    assert overlaid[0]["mechanism_family"] == "complete_frame_underreaction"
    assert "trial_variant_id" not in overlaid[0]
    assert row["family_key"] == "complete_frame_scout"
    assert row["status"] == "single_attempt"
    assert row["rejected"] == 1
    assert row["representative_exps"] == ["exp-scout"]
    assert row["reopen_condition"] == "A separately frozen later complete frame."
    assert "exp" not in row["fingerprint"]["field_tags"]


@pytest.mark.parametrize(
    ("ticket_payload", "error_match"),
    [
        (None, "ticket is missing or malformed"),
        ("{", "ticket is missing or malformed"),
        (
            '{"experiment_id":"exp-scout","change_type":"measurement_repair"}',
            "ticket change_type mismatch",
        ),
    ],
)
def test_private_replay_scout_ticket_loader_fails_closed(
    tmp_path, ticket_payload, error_match
):
    record = {
        "experiment_id": "exp-scout",
        "record_type": "v2_private_replay_scout_result",
    }
    ticket_path = tmp_path / "experiments" / "tickets" / "exp-scout.json"
    ticket_path.parent.mkdir(parents=True)
    if ticket_payload is not None:
        ticket_path.write_text(ticket_payload, encoding="utf-8")

    with pytest.raises(ValueError, match=error_match):
        frozen._private_replay_scout_tickets(tmp_path, [record])


def test_private_replay_scout_ticket_requires_both_family_fields():
    record = {
        "experiment_id": "exp-scout",
        "record_type": "v2_private_replay_scout_result",
        "status": "rejected",
        "decision": "rejected",
        "artifact": "data/experiments/exp-scout/result.json",
        "artifact_sha256": "a" * 64,
    }
    ticket = {
        "experiment_id": "exp-scout",
        "change_type": "private_replay_scout",
        "trial_family": "complete_frame_scout",
        "status": "rejected",
        "result": {
            "decision": "rejected",
            "artifact": "data/experiments/exp-scout/result.json",
            "artifact_sha256": "a" * 64,
        },
    }

    with pytest.raises(
        ValueError,
        match="ticket is missing mechanism_family for exp-scout",
    ):
        frozen.overlay_private_replay_scout_trial_metadata([record], [ticket])


def test_private_replay_scout_ticket_never_overrides_log_metadata():
    record = {
        "experiment_id": "exp-scout",
        "record_type": "v2_private_replay_scout_result",
        "trial_family": "log_family",
        "mechanism_family": "log_mechanism",
        "status": "rejected",
        "decision": "rejected",
        "artifact": "data/experiments/exp-scout/result.json",
        "artifact_sha256": "a" * 64,
    }
    ticket = {
        "experiment_id": "exp-scout",
        "change_type": "private_replay_scout",
        "trial_family": "ticket_family",
        "mechanism_family": "ticket_mechanism",
        "status": "rejected",
        "result": {
            "decision": "rejected",
            "artifact": "data/experiments/exp-scout/result.json",
            "artifact_sha256": "a" * 64,
        },
    }

    with pytest.raises(
        ValueError,
        match="private replay scout trial_family mismatch for exp-scout",
    ):
        frozen.overlay_private_replay_scout_trial_metadata([record], [ticket])


def test_non_scout_ticket_does_not_supply_missing_trial_metadata():
    record = {"experiment_id": "exp-repair", "status": "accepted"}
    ticket = {
        "experiment_id": "exp-repair",
        "change_type": "identity_or_measurement_repair",
        "trial_family": "repair_family",
    }

    assert frozen.overlay_private_replay_scout_trial_metadata(
        [record], [ticket]
    ) == [record]


def test_non_v2_private_replay_record_is_not_overlaid():
    record = {
        "experiment_id": "exp-legacy-scout",
        "record_type": "legacy_private_replay_result",
        "status": "rejected",
    }
    ticket = {
        "experiment_id": "exp-legacy-scout",
        "change_type": "private_replay_scout",
        "trial_family": "legacy_family",
    }

    assert frozen.overlay_private_replay_scout_trial_metadata(
        [record], [ticket]
    ) == [record]


def test_private_replay_scout_terminal_binding_must_match():
    record = {
        "experiment_id": "exp-scout",
        "record_type": "v2_private_replay_scout_result",
        "status": "rejected",
        "decision": "rejected",
        "artifact": "data/experiments/exp-scout/result.json",
        "artifact_sha256": "a" * 64,
    }
    ticket = {
        "experiment_id": "exp-scout",
        "change_type": "private_replay_scout",
        "trial_family": "complete_frame_scout",
        "mechanism_family": "complete_frame_underreaction",
        "status": "observed_only",
        "result": {
            "decision": "observed_only",
            "artifact": "data/experiments/exp-scout/result.json",
            "artifact_sha256": "a" * 64,
        },
    }

    with pytest.raises(
        ValueError,
        match="private replay scout terminal status mismatch for exp-scout",
    ):
        frozen.overlay_private_replay_scout_trial_metadata([record], [ticket])
