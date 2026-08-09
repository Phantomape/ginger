"""Compact the monolithic experiment log and per-experiment shards by stripping
oversized diagnostic dump fields (e.g. *_by_window candidate/trade samples).

Those fields are 100x larger than the compact decision metadata, are not consumed
by any tooling (build_alpha_memory / experiment_history read only compact
fields), and already live in the experiment artifact (data/experiments/<id>/).
This rewrites docs/experiment_log.jsonl and experiments/logs/*.json so they hold
only the compact record + a marker, dramatically shrinking both. The full dumps
remain in the artifact dir (lossless).

This does NOT rewrite git history; it only shrinks future commits and read/load
cost. Run periodically (the self-registering automation writes shards via
copy-pasted code that bypasses the central forward-strip, so shards re-bloat).

Usage:
    .\.venv\Scripts\python.exe -B scripts\compact_experiment_records.py [--dry-run]
        [--log-only | --shards-only] [--max-field-kb 50]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment_registry import (
    DEFAULT_EXPERIMENT_LOGS_DIR,
    DEFAULT_LOG,
    LOG_FIELD_MAX_BYTES,
    _atomic_write_text,
    file_lock,
    strip_oversized_fields,
)


def _mb(n_bytes: int) -> float:
    return round(n_bytes / 1024 / 1024, 1)


def compact_log(log_path: Path, *, max_field_bytes: int, dry_run: bool) -> dict:
    log_path = Path(log_path)
    if not log_path.exists():
        return {"path": str(log_path), "status": "missing"}
    before_bytes = log_path.stat().st_size

    # Serialize against concurrent appends (append_log_entry takes the same lock).
    with file_lock(log_path):
        order: list[str] = []
        by_id: dict[str, dict] = {}
        malformed = 0
        with log_path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                experiment_id = row.get("experiment_id")
                if not experiment_id:
                    malformed += 1
                    continue
                stripped = strip_oversized_fields(row, max_field_bytes=max_field_bytes)
                if experiment_id not in by_id:
                    order.append(experiment_id)
                by_id[experiment_id] = stripped  # dedupe: keep last occurrence

        lines_out = [
            json.dumps(by_id[eid], ensure_ascii=False, sort_keys=True)
            for eid in order
        ]
        text = "\n".join(lines_out) + ("\n" if lines_out else "")
        after_bytes = len(text.encode("utf-8"))
        changed = after_bytes != before_bytes
        if not dry_run and changed:
            _atomic_write_text(text, log_path)

    return {
        "path": str(log_path),
        "status": "dry_run" if dry_run else "compacted",
        "rows": len(order),
        "deduped_rows": len(by_id),
        "malformed_skipped": malformed,
        "before_mb": _mb(before_bytes),
        "after_mb": _mb(after_bytes),
        "saved_mb": _mb(before_bytes - after_bytes),
        "rewritten_paths": [str(log_path)] if changed else [],
    }


def compact_shards(logs_dir: Path, *, max_field_bytes: int, dry_run: bool) -> dict:
    logs_dir = Path(logs_dir)
    if not logs_dir.is_dir():
        return {"dir": str(logs_dir), "status": "missing"}
    before_total = 0
    after_total = 0
    rewritten = 0
    scanned = 0
    rewritten_paths: list[str] = []
    for shard in sorted(logs_dir.glob("exp-*.json")):
        scanned += 1
        try:
            before = shard.stat().st_size
        except OSError:
            continue
        before_total += before
        with file_lock(shard):
            try:
                with shard.open(encoding="utf-8-sig") as handle:
                    row = json.load(handle)
            except (OSError, json.JSONDecodeError):
                after_total += before
                continue
            if not isinstance(row, dict):
                after_total += before
                continue
            stripped = strip_oversized_fields(row, max_field_bytes=max_field_bytes)
            if stripped == row:
                after_total += before
                continue
            text = json.dumps(stripped, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
            after_total += len(text.encode("utf-8"))
            rewritten += 1
            rewritten_paths.append(str(shard))
            if not dry_run:
                _atomic_write_text(text, shard)
    return {
        "dir": str(logs_dir),
        "status": "dry_run" if dry_run else "compacted",
        "shards_scanned": scanned,
        "shards_rewritten": rewritten,
        "before_mb": _mb(before_total),
        "after_mb": _mb(after_total),
        "saved_mb": _mb(before_total - after_total),
        "rewritten_paths": rewritten_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-only", action="store_true")
    parser.add_argument("--shards-only", action="store_true")
    parser.add_argument("--max-field-kb", type=float, default=LOG_FIELD_MAX_BYTES / 1024)
    parser.add_argument("--log-path", default=str(DEFAULT_LOG))
    parser.add_argument("--logs-dir", default=str(DEFAULT_EXPERIMENT_LOGS_DIR))
    parser.add_argument(
        "--write-manifest",
        help="Write the newline-separated list of rewritten file paths here "
        "(for a surgical `git add` under concurrency).",
    )
    args = parser.parse_args()

    max_field_bytes = int(args.max_field_kb * 1024)
    summary = {}
    rewritten: list[str] = []
    if not args.shards_only:
        summary["log"] = compact_log(
            Path(args.log_path), max_field_bytes=max_field_bytes, dry_run=args.dry_run
        )
        rewritten.extend(summary["log"].get("rewritten_paths", []))
    if not args.log_only:
        summary["shards"] = compact_shards(
            Path(args.logs_dir), max_field_bytes=max_field_bytes, dry_run=args.dry_run
        )
        rewritten.extend(summary["shards"].get("rewritten_paths", []))
    if args.write_manifest and not args.dry_run:
        Path(args.write_manifest).write_text("\n".join(rewritten), encoding="utf-8")
    # Keep the printed summary compact (omit the long path lists).
    for section in summary.values():
        section.pop("rewritten_paths", None)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
