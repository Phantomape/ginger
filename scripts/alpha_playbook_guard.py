"""Machine-enforced contract for the durable alpha playbook.

The same validator is used by pytest, ``experiment.py audit``, and the staged
pre-commit hook.  The hook reads index blobs, not worktree files, so partial
staging cannot hide a violation or create a false failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from git_index import GitIndexError, index_text, staged_paths


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_REL = "docs/alpha-optimization-playbook.md"
EXPERIMENTS_PREFIX = "quant/experiments/"
PLAYBOOK_BASENAME = "alpha-optimization-playbook.md"
RUNNER_CONTRACT_CUTOFF = "20260718"

MAX_LINES = 450
MAX_EXPERIMENT_REFS = 24
MAX_DURABLE_PRIORS = 12
MAX_ACTIVE_LANES = 3
MAX_FROZEN_FAMILIES = 13
MAX_QUANTITATIVE_EXCEPTIONS = 5

EXPECTED_H2 = (
    "Document Contract",
    "Durable Alpha Priors",
    "Current Direction",
    "Active Research Queue",
    "Candidate Decision Checklist",
    "Frozen Zones",
    "Update Discipline",
    "Why the Old Version Became a Chronicle",
)

SECTION_LINE_LIMITS = {
    "Document Contract": 55,
    "Durable Alpha Priors": 105,
    "Current Direction": 45,
    "Active Research Queue": 125,
    "Candidate Decision Checklist": 50,
    "Frozen Zones": 105,
    "Update Discipline": 70,
    "Why the Old Version Became a Chronicle": 40,
}

DATED_STATUS_HEADING = re.compile(
    r"(?im)^#{2,6}\s+(?:(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2})|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{1,2}).*\b(?:readout|status|update|results?)\b"
)
EXPERIMENT_REF = re.compile(r"\bexp-\d{8}-\d+\b")
PRIOR_START = re.compile(r"(?m)^\d+\. \*\*")
LANE_HEADING = re.compile(r"Lane ([1-3]): .+")
RUNNER_NAME = re.compile(r"^exp[-_](\d{8})[-_].*\.py$")


def _violation(
    code: str,
    message: str,
    *,
    actual: Any | None = None,
    limit: Any | None = None,
    path: str = PLAYBOOK_REL,
) -> dict[str, Any]:
    row: dict[str, Any] = {"code": code, "message": message, "path": path}
    if actual is not None:
        row["actual"] = actual
    if limit is not None:
        row["limit"] = limit
    return row


def _sections(text: str) -> tuple[list[str], dict[str, str]]:
    matches = list(re.finditer(r"(?m)^## ([^#\r\n].*)$", text))
    names = [match.group(1).strip() for match in matches]
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[match.start() : end]
    return names, sections


def _markdown_table_data_rows(section: str) -> list[str]:
    return [
        line
        for line in section.splitlines()
        if line.startswith("| ")
        and not line.startswith("|---")
        and not line.startswith("| Family ")
        and not line.startswith("| Surface ")
    ]


def audit_playbook_text(text: str, *, path: str = PLAYBOOK_REL) -> dict[str, Any]:
    """Return a stable, JSON-serializable contract report for one text blob."""
    violations: list[dict[str, Any]] = []
    lines = text.splitlines()
    h2_names, sections = _sections(text)
    experiment_refs = EXPERIMENT_REF.findall(text)
    lane_matches = list(re.finditer(r"(?m)^### Lane ([1-3]): .+$", text))

    if len(lines) > MAX_LINES:
        violations.append(
            _violation(
                "line_budget_exceeded",
                "synthesize or move trial facts to experiment logs",
                actual=len(lines),
                limit=MAX_LINES,
                path=path,
            )
        )

    if tuple(h2_names) != EXPECTED_H2:
        violations.append(
            _violation(
                "h2_sequence_changed",
                "H2 sections must match the durable synthesis schema exactly",
                actual=h2_names,
                limit=list(EXPECTED_H2),
                path=path,
            )
        )

    deep_headings = re.findall(r"(?m)^#{4,6}\s+.+$", text)
    if deep_headings:
        violations.append(
            _violation(
                "deep_heading_not_allowed",
                "H4-H6 headings create unbounded append-only substructure",
                actual=deep_headings,
                path=path,
            )
        )

    h3_names = re.findall(r"(?m)^### ([^#\r\n].*)$", text)
    invalid_h3 = [
        heading
        for heading in h3_names
        if not LANE_HEADING.fullmatch(heading)
        and heading != "Quantitative Parked-Surface Exceptions"
    ]
    if invalid_h3:
        violations.append(
            _violation(
                "unknown_h3",
                "only three queue lanes and the quantitative-exception heading are allowed",
                actual=invalid_h3,
                path=path,
            )
        )

    lane_numbers = [int(match.group(1)) for match in lane_matches]
    if lane_numbers != list(range(1, len(lane_numbers) + 1)) or not (
        1 <= len(lane_numbers) <= MAX_ACTIVE_LANES
    ):
        violations.append(
            _violation(
                "active_lane_contract_failed",
                "active lanes must be contiguous Lane 1..N with N between 1 and 3",
                actual=lane_numbers,
                limit=MAX_ACTIVE_LANES,
                path=path,
            )
        )

    for section_name, line_limit in SECTION_LINE_LIMITS.items():
        section = sections.get(section_name)
        if section is None:
            continue
        section_lines = len(section.splitlines())
        if section_lines > line_limit:
            violations.append(
                _violation(
                    "section_budget_exceeded",
                    f"section '{section_name}' exceeded its synthesis budget",
                    actual=section_lines,
                    limit=line_limit,
                    path=path,
                )
            )

    if len(experiment_refs) > MAX_EXPERIMENT_REFS:
        violations.append(
            _violation(
                "experiment_reference_budget_exceeded",
                "keep at most one representative experiment per durable prior",
                actual=len(experiment_refs),
                limit=MAX_EXPERIMENT_REFS,
                path=path,
            )
        )

    durable_section = sections.get("Durable Alpha Priors", "")
    durable_refs = EXPERIMENT_REF.findall(durable_section)
    if len(durable_refs) != len(experiment_refs):
        violations.append(
            _violation(
                "experiment_reference_outside_priors",
                "experiment IDs belong only in Durable Alpha Priors",
                actual=len(experiment_refs) - len(durable_refs),
                limit=0,
                path=path,
            )
        )

    durable_prior_count = len(PRIOR_START.findall(durable_section))
    if durable_prior_count > MAX_DURABLE_PRIORS:
        violations.append(
            _violation(
                "durable_prior_budget_exceeded",
                "consolidate mechanism priors before adding another",
                actual=durable_prior_count,
                limit=MAX_DURABLE_PRIORS,
                path=path,
            )
        )

    prior_boundaries = list(PRIOR_START.finditer(durable_section))
    for index, match in enumerate(prior_boundaries):
        end = (
            prior_boundaries[index + 1].start()
            if index + 1 < len(prior_boundaries)
            else len(durable_section)
        )
        count = len(EXPERIMENT_REF.findall(durable_section[match.start() : end]))
        if count > 1:
            violations.append(
                _violation(
                    "multiple_representative_experiments",
                    f"durable prior {index + 1} has more than one experiment ID",
                    actual=count,
                    limit=1,
                    path=path,
                )
            )

    frozen_section = sections.get("Frozen Zones", "")
    exception_marker = "### Quantitative Parked-Surface Exceptions"
    frozen_summary = frozen_section.split(exception_marker, 1)[0]
    exception_summary = (
        frozen_section.split(exception_marker, 1)[1]
        if exception_marker in frozen_section
        else ""
    )
    frozen_rows = len(_markdown_table_data_rows(frozen_summary))
    exception_rows = len(_markdown_table_data_rows(exception_summary))
    if frozen_rows > MAX_FROZEN_FAMILIES:
        violations.append(
            _violation(
                "frozen_family_budget_exceeded",
                "consolidate frozen trials into mechanism families",
                actual=frozen_rows,
                limit=MAX_FROZEN_FAMILIES,
                path=path,
            )
        )
    if exception_rows > MAX_QUANTITATIVE_EXCEPTIONS:
        violations.append(
            _violation(
                "quantitative_exception_budget_exceeded",
                "move encodable reopen conditions into frozen_families.jsonl",
                actual=exception_rows,
                limit=MAX_QUANTITATIVE_EXCEPTIONS,
                path=path,
            )
        )

    if "## Current Readout" in text or DATED_STATUS_HEADING.search(text):
        violations.append(
            _violation(
                "dated_readout_not_allowed",
                "dated status/readout sections belong in generated state or logs",
                path=path,
            )
        )
    if not re.search(r"Replace the keyed\s+statement", text):
        violations.append(
            _violation(
                "replacement_semantics_missing",
                "the update discipline must require keyed replacement",
                path=path,
            )
        )
    if "must not write this file" not in text:
        violations.append(
            _violation(
                "runner_write_ban_missing",
                "the update discipline must ban runner/closeout writes",
                path=path,
            )
        )
    if text.count("<!-- PLAYBOOK_END -->") != 1 or not text.rstrip().endswith(
        "<!-- PLAYBOOK_END -->"
    ):
        violations.append(
            _violation(
                "end_sentinel_failed",
                "fold content into a keyed section; never append after PLAYBOOK_END",
                path=path,
            )
        )

    return {
        "schema_version": 1,
        "passed": not violations,
        "path": path,
        "metrics": {
            "lines": len(lines),
            "experiment_references": len(experiment_refs),
            "durable_priors": durable_prior_count,
            "active_lanes": len(lane_matches),
            "frozen_families": frozen_rows,
            "quantitative_exceptions": exception_rows,
        },
        "limits": {
            "lines": MAX_LINES,
            "experiment_references": MAX_EXPERIMENT_REFS,
            "durable_priors": MAX_DURABLE_PRIORS,
            "active_lanes": MAX_ACTIVE_LANES,
            "frozen_families": MAX_FROZEN_FAMILIES,
            "quantitative_exceptions": MAX_QUANTITATIVE_EXCEPTIONS,
        },
        "violations": violations,
    }


def _iter_experiment_runners(repo_root: Path):
    experiments_dir = repo_root / "quant" / "experiments"
    if not experiments_dir.exists():
        return
    for path in sorted(experiments_dir.rglob("*.py")):
        if RUNNER_NAME.match(path.name):
            yield path


def audit_repository_contract(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Audit the worktree for pytest and the end-of-turn repository audit."""
    playbook_path = repo_root / PLAYBOOK_REL
    try:
        text = playbook_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return {
            "schema_version": 1,
            "passed": False,
            "path": PLAYBOOK_REL,
            "metrics": {},
            "limits": {},
            "violations": [
                _violation(
                    "playbook_unreadable",
                    f"cannot read the UTF-8 playbook: {exc}",
                )
            ],
        }

    report = audit_playbook_text(text)
    runner_violations: list[dict[str, Any]] = []
    for runner in _iter_experiment_runners(repo_root):
        match = RUNNER_NAME.match(runner.name)
        if match is None or match.group(1) < RUNNER_CONTRACT_CUTOFF:
            continue
        try:
            runner_text = runner.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            runner_violations.append(
                _violation(
                    "runner_unreadable",
                    f"cannot inspect experiment runner: {exc}",
                    path=runner.relative_to(repo_root).as_posix(),
                )
            )
            continue
        if PLAYBOOK_BASENAME in runner_text:
            runner_violations.append(
                _violation(
                    "new_runner_depends_on_playbook",
                    "experiment runners must persist facts to logs, not depend on the synthesized playbook",
                    path=runner.relative_to(repo_root).as_posix(),
                )
            )
    report["violations"].extend(runner_violations)
    report["passed"] = not report["violations"]
    report["runner_contract_cutoff"] = RUNNER_CONTRACT_CUTOFF
    return report


def audit_staged_contract(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Audit the exact index snapshot that a pre-commit hook will commit."""
    playbook_text = index_text(repo_root, PLAYBOOK_REL)
    report = audit_playbook_text(playbook_text)
    staged_runner_violations: list[dict[str, Any]] = []
    for relative_path in staged_paths(repo_root):
        normalized = relative_path.replace("\\", "/")
        if not normalized.startswith(EXPERIMENTS_PREFIX):
            continue
        name = Path(normalized).name
        if RUNNER_NAME.match(name) is None:
            continue
        runner_text = index_text(repo_root, normalized)
        if PLAYBOOK_BASENAME in runner_text:
            staged_runner_violations.append(
                _violation(
                    "staged_runner_depends_on_playbook",
                    "remove the playbook dependency before committing this runner",
                    path=normalized,
                )
            )
    report["violations"].extend(staged_runner_violations)
    report["passed"] = not report["violations"]
    report["source"] = "git_index"
    return report


def _print_block(report: dict[str, Any]) -> None:
    sys.stderr.write("BLOCKED: alpha playbook contract failed:\n")
    for row in report.get("violations", []):
        sys.stderr.write(
            f"  [{row.get('code')}] {row.get('path')}: {row.get('message')}\n"
        )
    sys.stderr.write(
        "Run `.\\.venv\\Scripts\\python.exe -m pytest "
        "quant\\test_alpha_playbook_contract.py -q` after fixing it.\n"
    )


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Validate the exact Git index snapshot for pre-commit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the structured report to stdout.",
    )
    args = parser.parse_args(argv)
    try:
        report = (
            audit_staged_contract(REPO_ROOT)
            if args.staged
            else audit_repository_contract(REPO_ROOT)
        )
    except GitIndexError as exc:
        sys.stderr.write(
            "BLOCKED: alpha playbook staged contract could not inspect the "
            f"Git index: {exc}\n"
        )
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"]:
        if not args.json:
            _print_block(report)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
