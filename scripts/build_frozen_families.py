"""Generate docs/frozen_families.jsonl from experiment logs (source of truth).

Turns the prose anti-repeat wall in docs/alpha-optimization-playbook.md into a
machine-readable registry the reservation-time novelty check can query. Pure
read-only over experiments/logs/*.json plus the meta-research freeze list;
writes one JSONL row per trial-family. Advisory artifact; changes no strategy
behavior.

Usage:
    .\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py
"""

from __future__ import annotations

import io
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import experiment_fingerprint as fp

REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / "experiments" / "logs"
META_REPORT = REPO_ROOT / "data" / "meta_research_report_latest.json"
OUT_PATH = REPO_ROOT / "docs" / "frozen_families.jsonl"


def _load_json(path: Path) -> Any:
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


def _meta_freeze_keys() -> set[str]:
    """Best-effort set of family tokens the meta-research engine flagged frozen."""
    report = _load_json(META_REPORT)
    keys: set[str] = set()
    if not isinstance(report, dict):
        return keys
    for fc in report.get("freeze_candidates", []) or []:
        if isinstance(fc, str):
            keys.add(fc)
        elif isinstance(fc, dict):
            for k in ("family", "trial_family", "mechanism_family", "family_key", "key"):
                if fc.get(k):
                    keys.add(str(fc[k]))
    for rec in report.get("recommendations", []) or []:
        if isinstance(rec, dict) and "freeze" in str(rec.get("type", "")):
            if rec.get("family"):
                keys.add(str(rec["family"]))
    return keys


def _decision_bucket(rec: dict[str, Any]) -> str:
    if rec.get("accepted") is True or rec.get("accepted_alpha") is True:
        return "accepted"
    status = str(rec.get("status") or "").lower()
    decision = str(rec.get("decision") or "").lower()
    if status.startswith("accept") or decision.startswith("accept") or "positive_replay_lead" in decision:
        # positive replay lead is a non-promoted lead, not a rejection
        return "accepted" if status.startswith("accept") else "lead"
    if status.startswith("block") or "blocked" in decision:
        return "blocked"
    return "rejected"


def _reopen_condition(rec: dict[str, Any]) -> str | None:
    refl = rec.get("post_run_reflection")
    if isinstance(refl, dict):
        for k in ("new_evidence_required", "new_evidence_needed"):
            if refl.get(k):
                return str(refl[k])[:400]
    for k in ("next_evidence_needed", "new_evidence_required"):
        if rec.get(k):
            return str(rec[k])[:400]
    return None


def main() -> int:
    meta_freeze = _meta_freeze_keys()
    families: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trials": 0, "accepted": 0, "rejected": 0, "blocked": 0, "lead": 0, "exps": [], "latest": None}
    )
    for path in sorted(LOGS_DIR.glob("*.json")):
        rec = _load_json(path)
        if not isinstance(rec, dict):
            continue
        family = str(rec.get("trial_family") or rec.get("mechanism_family") or "").strip()
        if not family:
            continue
        bucket = _decision_bucket(rec)
        agg = families[family]
        agg["trials"] += 1
        agg[bucket] = agg.get(bucket, 0) + 1
        eid = rec.get("experiment_id")
        if eid:
            agg["exps"].append(str(eid))
        # keep the lexicographically-latest experiment id's record for reopen text
        if agg["latest"] is None or (eid and str(eid) > str(agg["latest"].get("experiment_id", ""))):
            agg["latest"] = rec

    rows: list[dict[str, Any]] = []
    for family, agg in sorted(families.items()):
        trials = agg["trials"]
        accepted = agg["accepted"]
        rejected = agg["rejected"]
        accept_rate = round(accepted / trials, 4) if trials else 0.0
        is_meta_frozen = any(tok and tok in family for tok in meta_freeze) or family in meta_freeze
        if is_meta_frozen:
            status = "frozen"
        elif accepted == 0 and (rejected + agg.get("blocked", 0)) >= 2:
            status = "frozen_rejected"
        elif accepted > 0:
            status = "has_accepted"
        elif trials == 1 and accepted == 0:
            status = "single_attempt"
        else:
            status = "active"
        latest = agg["latest"] or {}
        fingerprint = fp.infer_fingerprint(
            family,
            latest.get("changed_variable") or "",
            latest.get("trial_variant_id") or "",
        )
        rows.append(
            {
                "family_key": family,
                "status": status,
                "trials": trials,
                "accepted": accepted,
                "rejected": rejected,
                "blocked": agg.get("blocked", 0),
                "leads": agg.get("lead", 0),
                "accept_rate": accept_rate,
                "representative_exps": sorted(set(agg["exps"]))[-4:],
                "reopen_condition": _reopen_condition(latest),
                "fingerprint": fingerprint,
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with io.open(OUT_PATH, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    frozen = sum(1 for r in rows if r["status"] in ("frozen", "frozen_rejected"))
    has_acc = sum(1 for r in rows if r["status"] == "has_accepted")
    print(f"wrote {len(rows)} families to {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  frozen/frozen_rejected: {frozen} | has_accepted: {has_acc} | meta_freeze_keys: {len(meta_freeze)}")
    print("  top frozen-rejected families by trials:")
    for r in sorted([r for r in rows if r["status"] == "frozen_rejected"], key=lambda x: -x["trials"])[:8]:
        print(f"    {r['trials']:>2} trials  {r['family_key']}  ({r['fingerprint']['data_source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
