from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

MAX_LINES = 450
MAX_EXPERIMENT_REFS = 24
MAX_DURABLE_PRIORS = 12
MAX_ACTIVE_LANES = 3
MAX_FROZEN_FAMILIES = 13
MAX_QUANTITATIVE_EXCEPTIONS = 5
RUNNER_CONTRACT_CUTOFF = "20260718"

REQUIRED_HEADINGS = (
    "## Document Contract",
    "## Durable Alpha Priors",
    "## Current Direction",
    "## Active Research Queue",
    "## Frozen Zones",
    "## Update Discipline",
    "## Why the Old Version Became a Chronicle",
)

DATED_STATUS_HEADING = re.compile(
    r"(?im)^#{2,4}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
    r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:-\d{1,2})?.*"
    r"\b(?:readout|status|update)\b"
)


def _markdown_table_data_rows(section: str) -> list[str]:
    return [
        line
        for line in section.splitlines()
        if line.startswith("| ")
        and not line.startswith("|---")
        and not line.startswith("| Family ")
        and not line.startswith("| Surface ")
    ]


def test_alpha_playbook_stays_a_synthesis_map() -> None:
    text = PLAYBOOK_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert len(lines) <= MAX_LINES, (
        f"playbook has {len(lines)} lines; synthesize or move trial facts to "
        f"the logs before exceeding {MAX_LINES}"
    )

    missing = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    assert not missing, f"playbook contract sections are missing: {missing}"

    experiment_refs = re.findall(r"\bexp-\d{8}-\d+\b", text)
    assert len(experiment_refs) <= MAX_EXPERIMENT_REFS, (
        "too many experiment references; keep at most one representative "
        "experiment per durable prior"
    )

    durable_priors = re.findall(r"(?m)^\d+\. \*\*", text)
    assert len(durable_priors) <= MAX_DURABLE_PRIORS

    active_lanes = re.findall(r"(?m)^### Lane \d+:", text)
    assert 1 <= len(active_lanes) <= MAX_ACTIVE_LANES

    frozen_section = text.split("## Frozen Zones", 1)[1].split(
        "### Quantitative Parked-Surface Exceptions", 1
    )[0]
    assert len(_markdown_table_data_rows(frozen_section)) <= MAX_FROZEN_FAMILIES

    exception_section = text.split(
        "### Quantitative Parked-Surface Exceptions", 1
    )[1].split("## Update Discipline", 1)[0]
    assert (
        len(_markdown_table_data_rows(exception_section))
        <= MAX_QUANTITATIVE_EXCEPTIONS
    )

    assert "## Current Readout" not in text
    assert not DATED_STATUS_HEADING.search(text), (
        "dated readouts belong in generated state or experiment logs, not in "
        "the durable playbook"
    )
    assert "Replace the keyed\nstatement" in text
    assert "must not write this file" in text
    assert text.rstrip().endswith("<!-- PLAYBOOK_END -->"), (
        "content was appended outside the synthesis structure; fold it into a "
        "keyed section or keep it in the experiment log"
    )


def test_new_experiment_runners_do_not_depend_on_the_playbook() -> None:
    offenders: list[str] = []
    for path in (REPO_ROOT / "quant" / "experiments").glob("exp_*.py"):
        match = re.match(r"exp_(\d{8})_", path.name)
        if match is None or match.group(1) < RUNNER_CONTRACT_CUTOFF:
            continue
        if "alpha-optimization-playbook.md" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert not offenders, (
        "experiment runners must write exact facts to their logs, not read or "
        f"append the synthesized playbook: {offenders}"
    )
