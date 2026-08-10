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
