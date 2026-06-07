"""Build compact alpha-research memory from experiment records.

This generator deliberately keeps the registry light. It reads the raw
per-experiment facts through ``quant.meta_research_engine`` and writes derived,
LLM-sized memory surfaces:

- ``docs/alpha_context_pack.md``: default short context for new agents.
- ``docs/lessons/*.md``: mechanism-level lesson cards for targeted retrieval.

The generated files are summaries, not sources of truth. Raw tickets, logs,
artifacts, and cards remain authoritative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.meta_research_engine import (  # noqa: E402
    _changed_variable,
    _decision,
    _dedupe_records_by_experiment_id,
    _delta,
    _experiment_id,
    _is_accepted_decision,
    _is_rejected_decision,
    _mechanism_family,
    _trial_family,
    build_meta_report,
    is_strategy_iteration_record,
    load_experiment_logs,
    score_experiment,
)


DEFAULT_CONTEXT_PACK = REPO_ROOT / "docs" / "alpha_context_pack.md"
DEFAULT_LESSONS_DIR = REPO_ROOT / "docs" / "lessons"
DEFAULT_CONTEXT_LINE_BUDGET = 420
GIT_MEMORY_SOURCE_PATHS = (
    "docs/experiment_log.jsonl",
    "experiments/logs",
    "docs/experiments/logs",
)


def slugify(value):
    text = str(value or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unknown"


def one_line(value, limit=180):
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def display_source(value, root=REPO_ROOT):
    if not value:
        return ""
    path = Path(str(value))
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except (OSError, ValueError):
        return str(value).replace("\\", "/")


def money(value):
    return f"${value:,.2f}"


def signed(value, digits=4):
    return f"{value:+.{digits}f}"


def record_fingerprint(records, root=REPO_ROOT):
    rows = [
        {
            "experiment_id": _experiment_id(record),
            "decision": _decision(record),
            "mechanism_family": _mechanism_family(record),
            "trial_family": _trial_family(record),
            "changed_variable": _changed_variable(record),
            "ev_delta": round(_delta(record, "expected_value_score"), 6),
            "pnl_delta": round(_delta(record, "total_pnl") or _delta(record, "pnl"), 2),
            "source": display_source(record.get("_source"), root=root),
        }
        for record in records
    ]
    payload = json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def sorted_records(records):
    return sorted(records, key=lambda record: _experiment_id(record))


def compact_reflection(record):
    reflection = record.get("post_run_reflection")
    if isinstance(reflection, dict):
        parts = [
            reflection.get("why_result_happened"),
            reflection.get("forbidden_near_neighbor_retry"),
            reflection.get("new_evidence_required"),
        ]
        text = " ".join(str(part or "").strip() for part in parts if part)
        if text:
            return one_line(text, 220)
    calibration = record.get("calibration")
    if isinstance(calibration, dict) and calibration.get("surprise_note"):
        return one_line(calibration.get("surprise_note"), 220)
    return one_line(record.get("notes") or record.get("rejection_reason"), 220)


def record_summary(record, root=REPO_ROOT):
    return {
        "experiment_id": _experiment_id(record),
        "decision": _decision(record),
        "mechanism_family": _mechanism_family(record),
        "trial_family": _trial_family(record),
        "changed_variable": _changed_variable(record),
        "ev_delta": round(_delta(record, "expected_value_score"), 4),
        "pnl_delta": round(_delta(record, "total_pnl") or _delta(record, "pnl"), 2),
        "score": score_experiment(record),
        "reflection": compact_reflection(record),
        "summary": one_line(
            record.get("hypothesis")
            or record.get("change_summary")
            or record.get("notes")
            or record.get("experiment_id"),
            220,
        ),
        "source": display_source(record.get("_source"), root=root),
    }


def load_strategy_records(root):
    records = [
        record
        for record in load_experiment_logs(root)
        if isinstance(record, dict) and not record.get("_parse_error")
    ]
    deduped = _dedupe_records_by_experiment_id(records)
    return [record for record in deduped if is_strategy_iteration_record(record)]


def group_by_mechanism(records):
    groups = defaultdict(list)
    for record in sorted_records(records):
        groups[_mechanism_family(record)].append(record)
    return dict(groups)


def mechanism_stats(records):
    accepted = [record for record in records if _is_accepted_decision(record)]
    rejected = [record for record in records if _is_rejected_decision(record)]
    return {
        "experiments": len(records),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "accept_rate": round(len(accepted) / len(records), 4) if records else 0.0,
        "sum_ev_delta": round(sum(_delta(record, "expected_value_score") for record in records), 4),
        "sum_pnl_delta": round(
            sum(_delta(record, "total_pnl") or _delta(record, "pnl") for record in records),
            2,
        ),
        "latest_experiment": _experiment_id(records[-1]) if records else None,
    }


def trial_guidance_for_mechanism(report, mechanism):
    groups = report.get("trial_accounting", {}).get("groups", [])
    rows = [
        row
        for row in groups
        if mechanism in set(row.get("mechanism_families") or [])
    ]
    risk_rank = {"high": 0, "moderate": 1, "low": 2, "minimal": 3}
    return sorted(
        rows,
        key=lambda row: (
            risk_rank.get(row.get("multiple_testing_risk_bucket"), 9),
            -int(row.get("effective_trial_count") or 0),
            row.get("trial_family") or "",
        ),
    )


def select_lesson_mechanisms(records, report, count):
    groups = group_by_mechanism(records)
    scored = []
    high_risk_mechanisms = set()
    for row in report.get("trial_accounting", {}).get("high_risk_groups", []):
        high_risk_mechanisms.update(row.get("mechanism_families") or [])

    priority_families = {
        item.get("family")
        for item in report.get("strategy_research_priorities", [])[: count * 2]
    }

    for mechanism, rows in groups.items():
        stats = mechanism_stats(rows)
        recency_bonus = 1.0 if stats["latest_experiment"] else 0.0
        high_risk_bonus = 3.0 if mechanism in high_risk_mechanisms else 0.0
        priority_bonus = 2.0 if mechanism in priority_families else 0.0
        accepted_bonus = min(3.0, stats["accepted"] * 0.8)
        volume_bonus = min(3.0, stats["experiments"] * 0.15)
        evidence_bonus = min(3.0, abs(stats["sum_ev_delta"]) * 0.2)
        scored.append(
            (
                high_risk_bonus
                + priority_bonus
                + accepted_bonus
                + volume_bonus
                + evidence_bonus
                + recency_bonus,
                mechanism,
            )
        )

    return [
        mechanism
        for _, mechanism in sorted(scored, key=lambda item: (-item[0], item[1]))[:count]
    ]


def build_memory_model(root=REPO_ROOT, lesson_count=12, recent_count=12):
    root = Path(root)
    records = load_strategy_records(root)
    report = build_meta_report(root)
    lesson_mechanisms = select_lesson_mechanisms(records, report, lesson_count)
    groups = group_by_mechanism(records)
    top_positive = sorted(
        [record_summary(record, root=root) for record in records],
        key=lambda row: (row["score"], row["ev_delta"], row["pnl_delta"]),
        reverse=True,
    )[:recent_count]
    recent = [
        record_summary(record, root=root)
        for record in sorted_records(records)[-recent_count:]
    ]
    return {
        "schema_version": 1,
        "source": "raw experiment logs via quant.meta_research_engine",
        "records": records,
        "report": report,
        "fingerprint": record_fingerprint(records, root=root),
        "lesson_mechanisms": lesson_mechanisms,
        "groups": groups,
        "top_positive": top_positive,
        "recent": recent,
    }


def render_priority_rows(report, limit=8):
    lines = []
    for item in report.get("strategy_research_priorities", [])[:limit]:
        summary = item.get("evidence_summary") or {}
        lines.append(
            "- `{family}` priority `{priority:.4f}`: experiments `{experiments}`, "
            "accept `{accept_rate:.2%}`, sum EV `{ev}`, sum PnL `{pnl}`.".format(
                family=item.get("family"),
                priority=float(item.get("priority") or 0.0),
                experiments=summary.get("experiments"),
                accept_rate=float(summary.get("accept_rate") or 0.0),
                ev=signed(float(summary.get("sum_ev_delta") or 0.0)),
                pnl=money(float(summary.get("sum_pnl_delta") or 0.0)),
            )
        )
        why = item.get("why") or []
        penalties = item.get("penalties") or []
        if why:
            lines.append(f"  Reason: {one_line('; '.join(why), 240)}")
        if penalties:
            lines.append(f"  Guardrail: {one_line('; '.join(penalties), 240)}")
    return lines


def render_freeze_rows(report, limit=10):
    rows = report.get("trial_accounting", {}).get("high_risk_groups", [])
    if not rows:
        rows = report.get("freeze_candidates", [])
    lines = []
    for row in rows[:limit]:
        if "trial_family" in row:
            lines.append(
                "- `{trial}` / `{var}`: `{guidance}` after `{count}` effective trials; "
                "recent `{recent}`.".format(
                    trial=row.get("trial_family"),
                    var=row.get("changed_variable"),
                    guidance=row.get("retry_guidance"),
                    count=row.get("effective_trial_count"),
                    recent=", ".join(row.get("recent_experiments") or []),
                )
            )
        else:
            lines.append(
                "- `{name}`: `{reason}`, experiments `{experiments}`, accept `{accept:.2%}`.".format(
                    name=row.get("name"),
                    reason=row.get("reason"),
                    experiments=row.get("experiments"),
                    accept=float(row.get("accept_rate") or 0.0),
                )
            )
    return lines


def render_experiment_rows(rows):
    lines = []
    for row in rows:
        lines.append(
            "- `{experiment_id}` `{decision}`: EV `{ev}`, PnL `{pnl}`, family "
            "`{family}`, trial `{trial}`.".format(
                experiment_id=row["experiment_id"],
                decision=row["decision"],
                ev=signed(row["ev_delta"]),
                pnl=money(row["pnl_delta"]),
                family=row["mechanism_family"],
                trial=row["trial_family"],
            )
        )
        detail = row["reflection"] or row["summary"]
        if detail:
            lines.append(f"  Lesson: {one_line(detail, 240)}")
    return lines


def render_context_pack(model, context_line_budget=DEFAULT_CONTEXT_LINE_BUDGET):
    report = model["report"]
    records = model["records"]
    lines = [
        "# Alpha Context Pack",
        "",
        "Generated by `scripts/build_alpha_memory.py`. This is the default short",
        "LLM memory surface for alpha search. It is a derived summary, not a source",
        "of truth; inspect experiment tickets, logs, cards, and artifacts for exact",
        "facts before changing strategy behavior.",
        "",
        "## Source Snapshot",
        "",
        f"- Strategy records counted: `{len(records)}`",
        f"- Raw records loaded by meta report: `{report.get('records_loaded')}`",
        f"- History fingerprint: `{model['fingerprint']}`",
        "- Authoritative raw facts: `experiments/tickets`, `experiments/logs`,",
        "  `experiments/cards`, `experiments/artifacts`, and committed code.",
        "- Full current stack reference: `docs/current_state.md`.",
        "",
        "## How To Use",
        "",
        "- Read this file first for default memory.",
        "- Read a `docs/lessons/*.md` card when touching its mechanism family.",
        "- Read `docs/current_state.md` only for exact accepted-stack, baseline,",
        "  activation, or blocker details that are relevant to the current task.",
        "- Run `.\\.venv\\Scripts\\python.exe -B scripts\\build_alpha_memory.py --git-ref HEAD`",
        "  after closing and committing material alpha experiments so this pack",
        "  reflects the latest committed lessons.",
        "",
        "## Current Research Priorities",
        "",
    ]
    lines.extend(render_priority_rows(report))
    lines.extend(
        [
            "",
            "## Frozen Or High-Risk Near Neighbors",
            "",
        ]
    )
    freeze_rows = render_freeze_rows(report)
    lines.extend(freeze_rows or ["- No high-risk trial groups found in current logs."])
    lines.extend(
        [
            "",
            "## Recent Experiments",
            "",
        ]
    )
    lines.extend(render_experiment_rows(model["recent"]))
    lines.extend(
        [
            "",
            "## Highest-Signal Historical Records",
            "",
        ]
    )
    lines.extend(render_experiment_rows(model["top_positive"][:8]))
    lines.extend(
        [
            "",
            "## Mechanism Lesson Cards",
            "",
        ]
    )
    for mechanism in model["lesson_mechanisms"]:
        lines.append(f"- [`{mechanism}`](lessons/{slugify(mechanism)}.md)")
    lines.extend(
        [
            "",
            "## Line Budget",
            "",
            f"- Target maximum lines: `{context_line_budget}`",
            "- Actual lines when generated: `__LINE_COUNT__`",
        ]
    )
    text = "\n".join(lines).rstrip() + "\n"
    actual_lines = len(text.splitlines())
    text = text.replace("__LINE_COUNT__", str(actual_lines))
    if actual_lines > context_line_budget:
        raise ValueError(
            f"context pack has {actual_lines} lines, above budget {context_line_budget}"
        )
    return text


def render_lesson_card(mechanism, records, report, *, root=REPO_ROOT):
    rows = sorted_records(records)
    stats = mechanism_stats(rows)
    accepted = [
        record_summary(record, root=root)
        for record in rows
        if _is_accepted_decision(record)
    ]
    rejected = [
        record_summary(record, root=root)
        for record in rows
        if _is_rejected_decision(record)
    ]
    recent = [record_summary(record, root=root) for record in rows[-6:]]
    guidance = trial_guidance_for_mechanism(report, mechanism)
    latest = recent[-1] if recent else None

    lines = [
        f"# Lesson: {mechanism}",
        "",
        "Generated by `scripts/build_alpha_memory.py`. This card compresses",
        "mechanism-level memory. It is not authoritative; inspect raw experiment",
        "records before making strategy changes.",
        "",
        "## Current Conclusion",
        "",
        f"- Experiments: `{stats['experiments']}`",
        f"- Accepted / rejected: `{stats['accepted']}` / `{stats['rejected']}`",
        f"- Accept rate: `{stats['accept_rate']:.2%}`",
        f"- Sum EV delta: `{signed(stats['sum_ev_delta'])}`",
        f"- Sum PnL delta: `{money(stats['sum_pnl_delta'])}`",
    ]
    if latest:
        lines.append(
            "- Latest: `{experiment_id}` `{decision}` with EV `{ev}` and PnL `{pnl}`.".format(
                experiment_id=latest["experiment_id"],
                decision=latest["decision"],
                ev=signed(latest["ev_delta"]),
                pnl=money(latest["pnl_delta"]),
            )
        )
    lines.extend(["", "## Retained Or Positive Evidence", ""])
    if accepted:
        lines.extend(render_experiment_rows(accepted[-6:]))
    else:
        lines.append("- No accepted records found for this mechanism in loaded logs.")
    lines.extend(["", "## Rejections And Failure Lessons", ""])
    if rejected:
        lines.extend(render_experiment_rows(rejected[-8:]))
    else:
        lines.append("- No rejected records found for this mechanism in loaded logs.")
    lines.extend(["", "## Retry Discipline", ""])
    if guidance:
        for row in guidance[:8]:
            lines.append(
                "- `{trial}` / `{var}`: risk `{risk}`, guidance `{guidance}`, recent `{recent}`.".format(
                    trial=row.get("trial_family"),
                    var=row.get("changed_variable"),
                    risk=row.get("multiple_testing_risk_bucket"),
                    guidance=row.get("retry_guidance"),
                    recent=", ".join(row.get("recent_experiments") or []),
                )
            )
            failure = row.get("most_recent_failure")
            if failure:
                lines.append(
                    f"  Latest failure: `{failure.get('experiment_id')}` "
                    f"{one_line(failure.get('rejection_reason'), 220)}"
                )
    else:
        lines.append("- Use standard Gate 1-4; no high-risk trial group is linked.")
    lines.extend(["", "## Recent Raw Records", ""])
    for row in recent:
        lines.append(
            "- `{experiment_id}` source `{source}`.".format(
                experiment_id=row["experiment_id"],
                source=one_line(row["source"], 140),
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def write_alpha_memory(
    root=REPO_ROOT,
    context_pack=DEFAULT_CONTEXT_PACK,
    lessons_dir=DEFAULT_LESSONS_DIR,
    lesson_count=12,
    recent_count=12,
    context_line_budget=DEFAULT_CONTEXT_LINE_BUDGET,
):
    model = build_memory_model(
        root=root,
        lesson_count=lesson_count,
        recent_count=recent_count,
    )
    context_pack = Path(context_pack)
    lessons_dir = Path(lessons_dir)
    context_pack.parent.mkdir(parents=True, exist_ok=True)
    lessons_dir.mkdir(parents=True, exist_ok=True)

    context_text = render_context_pack(
        model,
        context_line_budget=context_line_budget,
    )
    context_pack.write_text(context_text, encoding="utf-8")

    written_lessons = []
    for mechanism in model["lesson_mechanisms"]:
        path = lessons_dir / f"{slugify(mechanism)}.md"
        text = render_lesson_card(
            mechanism,
            model["groups"][mechanism],
            model["report"],
            root=root,
        )
        path.write_text(text, encoding="utf-8")
        written_lessons.append(path)

    return {
        "context_pack": context_pack,
        "lessons": written_lessons,
        "records_counted": len(model["records"]),
        "fingerprint": model["fingerprint"],
    }


def materialize_git_ref_logs(git_ref, target_root, repo_root=REPO_ROOT):
    """Copy committed experiment log inputs from a git ref into a temp root."""
    target_root = Path(target_root)
    listed = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            git_ref,
            "--",
            *GIT_MEMORY_SOURCE_PATHS,
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    paths = [
        line.strip()
        for line in listed.stdout.splitlines()
        if line.strip()
        and (
            line.strip() == "docs/experiment_log.jsonl"
            or line.strip().endswith(".json")
        )
    ]
    if not paths:
        return []

    query = "".join(f"{git_ref}:{rel_path}\n" for rel_path in paths).encode("utf-8")
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repo_root,
        input=query,
        check=True,
        capture_output=True,
    )
    data = batch.stdout
    cursor = 0
    written = []
    for rel_path in paths:
        header_end = data.index(b"\n", cursor)
        header = data[cursor:header_end].decode("utf-8", errors="replace")
        cursor = header_end + 1
        parts = header.split()
        if len(parts) < 3 or parts[1] != "blob":
            raise ValueError(f"unexpected git cat-file header for {rel_path}: {header}")
        size = int(parts[2])
        blob = data[cursor: cursor + size]
        cursor += size
        if cursor < len(data) and data[cursor: cursor + 1] == b"\n":
            cursor += 1
        out_path = target_root / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(blob)
        written.append(rel_path)
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--context-pack", default=str(DEFAULT_CONTEXT_PACK))
    parser.add_argument("--lessons-dir", default=str(DEFAULT_LESSONS_DIR))
    parser.add_argument("--lesson-count", type=int, default=12)
    parser.add_argument("--recent-count", type=int, default=12)
    parser.add_argument("--context-line-budget", type=int, default=DEFAULT_CONTEXT_LINE_BUDGET)
    parser.add_argument(
        "--git-ref",
        default=None,
        help=(
            "Build from committed experiment logs at this git ref instead of "
            "the possibly dirty workspace, for reproducible summary refreshes."
        ),
    )
    args = parser.parse_args(argv)

    if args.git_ref:
        with tempfile.TemporaryDirectory(prefix="alpha-memory-git-ref-") as tmp:
            materialized = materialize_git_ref_logs(
                args.git_ref,
                Path(tmp),
                repo_root=Path(args.root),
            )
            result = write_alpha_memory(
                root=Path(tmp),
                context_pack=Path(args.context_pack),
                lessons_dir=Path(args.lessons_dir),
                lesson_count=args.lesson_count,
                recent_count=args.recent_count,
                context_line_budget=args.context_line_budget,
            )
            result["git_ref"] = args.git_ref
            result["materialized_inputs"] = materialized
    else:
        result = write_alpha_memory(
            root=Path(args.root),
            context_pack=Path(args.context_pack),
            lessons_dir=Path(args.lessons_dir),
            lesson_count=args.lesson_count,
            recent_count=args.recent_count,
            context_line_budget=args.context_line_budget,
        )
    print(
        json.dumps(
            {
                "context_pack": str(result["context_pack"]),
                "git_ref": result.get("git_ref"),
                "lessons": [str(path) for path in result["lessons"]],
                "materialized_input_count": len(result.get("materialized_inputs") or []),
                "records_counted": result["records_counted"],
                "fingerprint": result["fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
