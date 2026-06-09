"""Guard: no NEW experiment runner may self-register into the registry.

Background
----------
~190 legacy runners in ``quant/experiments/`` write
``docs/experiment_registry.json`` directly via their own ``_update_registry()``
helpers. That bypasses ``create_ticket`` -> ``require_pre_run_prediction`` (so
alpha experiments can land with no prediction) and routinely drops the
``prediction`` from the persisted record (it survives only in the log). The
legacy offenders are grandfathered in
``quant/experiments/_self_register_legacy_allowlist.txt``.

This test fails when a NON-grandfathered runner self-registers, forcing new
runners to use ``experiment.py new/close`` or
``experiment_registry.persist_self_registered_result()`` (which enforces the
prediction and propagates it onto the ticket).

The detector lives in ``scripts/self_registration_guard.py`` so the pytest
guard, the audit CLI, the refresh tool, and the pre-commit hook never drift.

No JavaScript was used.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from self_registration_guard import (  # noqa: E402
    current_offenders as _current_offenders,
    load_allowlist as _load_allowlist,
    new_offenders as _new_offenders,
    self_registers as _self_registers,
)


def test_no_new_self_registering_runners():
    assert _load_allowlist(), "legacy allowlist is missing or empty"
    new_offenders = _new_offenders()
    assert not new_offenders, (
        "These new runners write the experiment registry directly, bypassing "
        "prediction enforcement:\n  "
        + "\n  ".join(new_offenders)
        + "\nUse `experiment.py new` to reserve (with a prediction) and "
        "`experiment.py close` to finalize, or call "
        "`experiment_registry.persist_self_registered_result()` which enforces "
        "the prediction and writes it onto the ticket. If a runner was migrated "
        "off direct registry writes, it will simply drop out of this check."
    )


def test_helper_is_not_flagged_as_self_registration():
    # Calling persist_self_registered_result() (an import) must NOT trip the
    # detector -- only direct registry writes should.
    sample = (
        "from experiment_registry import persist_self_registered_result\n"
        "persist_self_registered_result(REG, experiment_id=eid, lane='alpha_search',\n"
        "    prediction=pred, result=res, status='rejected')\n"
    )
    assert _self_registers(sample) is False


def test_detector_flags_direct_registry_write():
    assert _self_registers('registry.setdefault("experiments", []).append(x)') is True
    assert _self_registers(
        'p = REPO_ROOT / "docs" / "experiment_registry.json"\np.write_text(data)'
    ) is True


def test_helper_user_referencing_registry_path_is_exempt():
    # A runner that uses the sanctioned helper but references the registry path
    # (to pass it in) and writes its OWN artifact must NOT be flagged.
    sample = (
        'REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"\n'
        'OUT_JSON.write_text(json.dumps(payload))\n'
        'persist_self_registered_result(REGISTRY_JSON, experiment_id=eid,\n'
        '    lane="alpha_search", prediction=pred, result=res, status="rejected")\n'
    )
    assert _self_registers(sample) is False


def test_setdefault_overrides_helper_exemption():
    # Mutating the experiments list is the hard signal even if the helper is also
    # mentioned -- a sloppy runner must not hide a direct write behind the import.
    sample = (
        "persist_self_registered_result(REG, ...)\n"
        'registry.setdefault("experiments", []).append(entry)\n'
    )
    assert _self_registers(sample) is True


def test_current_offenders_are_all_grandfathered():
    # Sanity: the allowlist is a superset of current offenders (the guard only
    # fails on NEW ones). Equivalent to test_no_new_... but explicit.
    assert _current_offenders() <= _load_allowlist() | set(_new_offenders())
