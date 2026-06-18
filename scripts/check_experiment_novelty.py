"""Advisory near-neighbor check against docs/frozen_families.jsonl.

Given a proposed experiment (free-text description and/or family/variable
strings), infer its decision-fingerprint and report the nearest known families,
warning when it looks like a near-neighbor of a frozen or rejected family. This
is the warn-only layer: it never blocks. Later, scripts/experiment.py can import
`check()` and turn warnings into a soft gate (override with an explicit
new-evidence axis).

Usage:
    .\\.venv\\Scripts\\python.exe -B scripts\\check_experiment_novelty.py \\
        --describe "raw SEC companyfacts gross margin expansion candidate pool"
    .\\.venv\\Scripts\\python.exe -B scripts\\check_experiment_novelty.py \\
        --trial-family inventory_to_revenue_leanness_candidate_pool
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any

import experiment_fingerprint as fp

REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_PATH = REPO_ROOT / "docs" / "frozen_families.jsonl"

_FROZEN_STATUSES = {"frozen", "frozen_rejected"}


def _load_families() -> list[dict[str, Any]]:
    if not FROZEN_PATH.exists():
        return []
    rows = []
    for line in io.open(FROZEN_PATH, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def check(fingerprint: dict[str, Any], *, top_n: int = 5) -> dict[str, Any]:
    """Return nearest families and a warn verdict. Importable by experiment.py."""
    families = _load_families()
    scored = []
    for fam in families:
        score = fp.distance(fingerprint, fam.get("fingerprint") or {})
        scored.append((score, fam))
    scored.sort(key=lambda x: -x[0])
    nearest = scored[:top_n]
    # Warn if a frozen/rejected (or already-accepted) family is too close.
    blocking = [
        (s, f)
        for s, f in scored
        if s >= fp.WARN_THRESHOLD and f.get("status") in (_FROZEN_STATUSES | {"has_accepted"})
    ]
    warn = bool(blocking)
    return {
        "fingerprint": fingerprint,
        "warn": warn,
        "warn_threshold": fp.WARN_THRESHOLD,
        "nearest": [
            {
                "score": s,
                "family_key": f.get("family_key"),
                "status": f.get("status"),
                "trials": f.get("trials"),
                "accept_rate": f.get("accept_rate"),
                "data_source": (f.get("fingerprint") or {}).get("data_source"),
                "reopen_condition": f.get("reopen_condition"),
            }
            for s, f in nearest
        ],
        "blocking_matches": [
            {"score": s, "family_key": f.get("family_key"), "status": f.get("status")}
            for s, f in blocking[:top_n]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Advisory experiment near-neighbor / novelty check.")
    ap.add_argument("--describe", default="", help="Free-text hypothesis/decision description.")
    ap.add_argument("--trial-family", default="", help="Proposed trial family slug.")
    ap.add_argument("--changed-variable", default="", help="Proposed changed/decision variable.")
    ap.add_argument("--data-source", default="", help="Override inferred data_source.")
    ap.add_argument("--field-tags", default="", help="Comma-separated field tags override.")
    ap.add_argument("--gate-shape", default="", help="Override inferred gate_shape.")
    ap.add_argument("--top-n", type=int, default=5)
    ap.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = ap.parse_args()

    fingerprint = fp.infer_fingerprint(args.describe, args.trial_family, args.changed_variable)
    if args.data_source:
        fingerprint["data_source"] = args.data_source
    if args.field_tags:
        fingerprint["field_tags"] = sorted({t.strip() for t in args.field_tags.split(",") if t.strip()})
    if args.gate_shape:
        fingerprint["gate_shape"] = args.gate_shape

    result = check(fingerprint, top_n=args.top_n)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    print("Inferred fingerprint:")
    print(f"  data_source : {fingerprint['data_source']}")
    print(f"  gate_shape  : {fingerprint['gate_shape']}")
    print(f"  field_tags  : {', '.join(fingerprint['field_tags'][:18])}")
    print()
    verdict = "WARN  near-neighbor of a frozen / already-explored family" if result["warn"] else "ok    no strong near-neighbor"
    print(f"Verdict: {verdict}  (threshold {result['warn_threshold']})")
    print("\nNearest known families:")
    for n in result["nearest"]:
        flag = "  <-- frozen/explored" if n["status"] in (_FROZEN_STATUSES | {"has_accepted"}) and n["score"] >= fp.WARN_THRESHOLD else ""
        print(f"  {n['score']:.3f}  [{n['status']}]  {n['family_key']}  (trials={n['trials']}, accept={n['accept_rate']}){flag}")
    if result["warn"]:
        worst = result["nearest"][0]
        print("\nIf you proceed, declare a genuinely new evidence axis (new data source / field")
        print("not used by any prior family / new gate shape / forward replacement rows).")
        if worst.get("reopen_condition"):
            print(f"\nReopen condition recorded for the closest family:\n  {worst['reopen_condition']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
