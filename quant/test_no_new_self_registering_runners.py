"""Guard: no NEW experiment runner may self-register into the registry.

Background
----------
~184 legacy runners in ``quant/experiments/`` write
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

Keep the detector here identical to the one that generated the allowlist.

No JavaScript was used.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
ALLOWLIST_PATH = EXPERIMENTS_DIR / "_self_register_legacy_allowlist.txt"


def _self_registers(text: str) -> bool:
    """True if the source mutates the registry experiments list or writes the
    registry file path directly."""
    if 'setdefault("experiments"' in text or "setdefault('experiments'" in text:
        return True
    if "experiment_registry.json" in text and (
        "_write_json(" in text or "json.dump" in text or ".write_text(" in text
    ):
        return True
    return False


def _load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.exists():
        return set()
    names = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.add(line)
    return names


def _current_offenders() -> set[str]:
    offenders = set()
    for path in sorted(EXPERIMENTS_DIR.glob("exp_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _self_registers(text):
            offenders.add(path.name)
    return offenders


def test_no_new_self_registering_runners():
    allowlist = _load_allowlist()
    assert allowlist, "legacy allowlist is missing or empty"
    new_offenders = sorted(_current_offenders() - allowlist)
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
