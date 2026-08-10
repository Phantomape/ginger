"""exp-20260728-005: mechanism-aware D3 legacy near-neighbor calibration.

Measurement repair sanctioned by the exp-20260728 massive-continuation
discovery closeout ("a separate measurement-repair audit may examine whether
legacy component-source and response-shape projections create broad D3 false
positives").

Root cause: ``distance`` awards 0.45 for source identity and 0.15 for
gate-shape identity, so two candidates sharing one source bucket start at a
0.60 structural floor above WARN_THRESHOLD (0.55), and the discovery engine
hard-rejected on ANY hit >= WARN. Three false-positive classes followed:

1. any second candidate family on a new single-source surface (the forward
   split candidate scored 0.7576 against the same-day rejected continuation
   candidate purely through shared source/shape/boilerplate);
2. schema-required vocabulary ("replacement value", from the mandatory
   replacement_value_comparator precommitment) text-routed every candidate
   into the forward_replacement_value source and forward_attribution shape
   buckets, colliding with unrelated attribution families at 0.62-0.63;
3. stale months-old never-closed tickets and same-day measurement-repair
   tickets participated as open_ticket priors, and inferred/alias-only
   projections (ohlcv_momentum / ohlcv_relation) matched every price-based
   candidate at ~0.61.

Repair (all outcome-blind; no strategy behavior change):

- discovery prior records preserve ``economic_mechanism``; explicit,
  essentially-disjoint mechanisms on both sides waive sub-structural hits
  (AGENTS.md section 2.4 axes (b)/(d));
- bare "replacement value" removed from the forward_replacement_value and
  forward_attribution keyword tuples (compound spellings retained), with
  docs/frozen_families.jsonl rebuilt so misrouted families (e.g. the PEAD
  group) return to their true faces;
- open_ticket priors honor the published in-flight window
  (GINGER_IN_FLIGHT_WINDOW_DAYS, default 7 days) and exclude
  measurement_repair-lane reservations;
- hits reachable only through inferred/alias-expanded projections require
  the structural-duplicate bar (0.85); hits on DECLARED evidence faces keep
  the reserve-time WARN calibration unchanged.

Run this module to regenerate the before/after artifact from the committed
preflight artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ART_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260728-005"
CANDIDATE = (
    REPO_ROOT / "data" / "alpha_search" / "massive_split_drift_candidate_20260728_1626.json"
)

PREFLIGHTS = {
    "before_repair_v1_discovery_false_positive": (
        "data/alpha_search/massive_split_drift_preflight_20260728_1626.json"
    ),
    "mid_repair_v2_keyword_bucket_false_positives": (
        "data/alpha_search/massive_split_drift_preflight_v2_20260728.json"
    ),
    "mid_repair_v3_stale_ticket_false_positives": (
        "data/alpha_search/massive_split_drift_preflight_v3_20260728.json"
    ),
    "after_repair_v5_calibrated": (
        "data/alpha_search/massive_split_drift_preflight_v5_20260728.json"
    ),
}


def build_artifact() -> dict:
    stages = {}
    for label, rel in PREFLIGHTS.items():
        payload = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
        stages[label] = {
            "artifact": rel,
            "decision": payload["decision"],
            "d3_reasons": payload["gates"]["D3"]["reasons"],
        }
    return {
        "schema_version": 1,
        "experiment_id": "exp-20260728-005",
        "record_type": "measurement_repair_before_after",
        "candidate": str(CANDIDATE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "stages": stages,
        "witnesses": {
            "cross_mechanism_discovery_pair_score": 0.7576,
            "keyword_bucket_family_scores": [0.6317, 0.6263, 0.6322, 0.6256, 0.6256],
            "stale_ticket_scores": [0.6227, 0.6235, 0.6235, 0.6346, 0.6171],
            "inferred_projection_family_scores": [0.6143, 0.6160, 0.6152, 0.6105, 0.6107],
            "structural_duplicate_threshold": 0.85,
            "mechanism_same_jaccard": 0.2,
        },
        "tests": [
            "quant/test_alpha_search_history.py (22 tests)",
            "quant/test_experiment_fingerprint.py (255+2 tests)",
            "quant/test_alpha_search_engine.py, test_alpha_search_contract.py (no regressions)",
        ],
        "frozen_families_rebuild": {
            "rebuilt": True,
            "verification": "pead_broad_universe_* families re-routed from forward_replacement_value to revision_expectation; 31 genuine settled-forward families remain in the bucket",
        },
        "trade_enabled": False,
        "production_impact": "none: discovery-guard calibration only; no entry, exit, ranking, sizing or order path changed",
    }


def main() -> None:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out = ART_DIR / "exp_20260728_005_d3_mechanism_aware_near_neighbor.json"
    out.write_text(json.dumps(build_artifact(), indent=1), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
