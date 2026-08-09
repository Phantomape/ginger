"""exp-20260714-007: in-flight open-ticket duplicate guard calibration evidence.

Measures the fingerprint duplicate score on real ticket pairs to document the
separation gap behind the GINGER_IN_FLIGHT_DUP_THRESHOLD=0.65 default, and
records the guard verdict for each known duplicate pair (after) versus the
pre-guard behavior (before: every pair reserved successfully because the
novelty gate only reads closed experiments).

Usage:
    .\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260714_007_in_flight_duplicate_guard.py
"""

import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as efp  # noqa: E402
from create_experiment_ticket import _field_tag_jaccard  # noqa: E402

EXPERIMENT_ID = "exp-20260714-007"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
THRESHOLD = 0.65

# Documented duplicate reservations (loser closed as accounting) plus the live
# rephrased duplicate exp-20260714-008 created while verifying this guard.
KNOWN_DUPLICATE_PAIRS = [
    ("exp-20260713-001", "exp-20260713-002"),
    ("exp-20260711-021", "exp-20260711-022"),
    ("exp-20260714-007", "exp-20260714-008"),
]

# Same-day distinct hypotheses: none of these may score at or above threshold.
DISTINCT_IDS = [f"exp-20260714-00{i}" for i in range(1, 7)]

# Legitimately related-but-distinct neighbors inside one sleeve family; the
# threshold must sit above this band so coordinated same-family work passes.
RELATED_DISTINCT_PAIRS = [
    ("exp-20260711-004", "exp-20260711-015"),
    ("exp-20260711-018", "exp-20260711-015"),
]


def _fingerprint(ticket):
    return efp.infer_fingerprint(
        ticket.get("hypothesis") or "",
        ticket.get("single_causal_variable") or "",
        ticket.get("trial_family") or "",
        ticket.get("mechanism_family") or "",
        ticket.get("changed_variable") or "",
    )


def _load(experiment_id):
    path = ROOT / "experiments" / "tickets" / f"{experiment_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _score(fp_a, fp_b):
    return max(efp.distance(fp_a, fp_b), _field_tag_jaccard(fp_a, fp_b))


def main():
    dup_rows = []
    for a, b in KNOWN_DUPLICATE_PAIRS:
        fa, fb = _fingerprint(_load(a)), _fingerprint(_load(b))
        score = _score(fa, fb)
        dup_rows.append(
            {
                "pair": [a, b],
                "score": score,
                "blocked_after": score >= THRESHOLD,
                "blocked_before": False,
            }
        )

    distinct_rows = []
    fps = {i: _fingerprint(_load(i)) for i in DISTINCT_IDS}
    for a, b in combinations(DISTINCT_IDS, 2):
        score = _score(fps[a], fps[b])
        distinct_rows.append({"pair": [a, b], "score": score, "false_positive": score >= THRESHOLD})

    related_rows = []
    for a, b in RELATED_DISTINCT_PAIRS:
        fa, fb = _fingerprint(_load(a)), _fingerprint(_load(b))
        score = _score(fa, fb)
        related_rows.append({"pair": [a, b], "score": score, "false_positive": score >= THRESHOLD})

    result = {
        "experiment_id": EXPERIMENT_ID,
        "threshold": THRESHOLD,
        "duplicate_pairs": dup_rows,
        "distinct_same_day_pairs": distinct_rows,
        "related_but_distinct_pairs": related_rows,
        "duplicate_pairs_all_blocked_after": all(r["blocked_after"] for r in dup_rows),
        "false_positive_count": sum(
            r["false_positive"] for r in distinct_rows + related_rows
        ),
        "min_duplicate_score": min(r["score"] for r in dup_rows),
        "max_distinct_score": max(
            r["score"] for r in distinct_rows + related_rows
        ),
        "note": (
            "before = pre-guard behavior: the frozen-family novelty gate reads "
            "only closed experiments, so every duplicate pair reserved "
            "successfully and the loser burned the ID as "
            "duplicate_reservation_accounting. after = "
            "evaluate_in_flight_duplicate_guard blocks scores >= threshold at "
            "reservation time; end-to-end verified 2026-07-14 (blocked exit 1, "
            "no ticket file created)."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "exp_20260714_007_in_flight_duplicate_guard.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
