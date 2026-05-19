"""exp-20260519-018: state-surface top-3 true-sector cohesion notional.

Alpha search. Tests the opposite crowding interpretation from exp-20260519-017:
if true-sector diversity hurt the state-surface paper queue, residual same-sector
top-three cohesion may indicate a stronger thematic tape. This changes only the
default-off paper rank-notional profile for already-selected state-surface rows.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
for search_path in (REPO_ROOT, QUANT_ROOT):
    text = str(search_path)
    if text not in sys.path:
        sys.path.insert(0, text)

import exp_20260519_016_state_surface_top3_sector_diversity_notional as base
from risk_engine import SECTOR_MAP


EXPERIMENT_ID = "exp-20260519-018"
EXPERIMENT_SLUG = "state_surface_top3_true_sector_cohesion_notional"
RULE_VERSION = "state_surface_top3_true_sector_cohesion_rank_notional_v1"

TOP3_TRUE_SECTOR_COHESION_VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            base.BASELINE_VARIANT,
            {
                "profile": None,
                "min_top3_sector_count": 1,
                "aggression_order": 0,
                "description": "accepted stack through rank-3 volume confirmation",
            },
        ),
        (
            "top3_true_sector_cohesion_rank1_lift",
            {
                "profile": [1.80, 1.25, 1.05, 0.675, 0.35],
                "min_top3_sector_count": 1,
                "aggression_order": 1,
                "description": "true-sector cohesive top three with rank-1 lift",
            },
        ),
        (
            "top3_true_sector_cohesion_rank2_lift",
            {
                "profile": [1.45, 1.70, 1.05, 0.675, 0.35],
                "min_top3_sector_count": 1,
                "aggression_order": 2,
                "description": "true-sector cohesive top three with rank-2 lift",
            },
        ),
        (
            "top3_true_sector_cohesion_rank3_lift",
            {
                "profile": [1.40, 1.25, 1.45, 0.675, 0.35],
                "min_top3_sector_count": 1,
                "aggression_order": 3,
                "description": "true-sector cohesive top three with rank-3 lift",
            },
        ),
        (
            "top3_true_sector_cohesion_balanced",
            {
                "profile": [1.65, 1.45, 1.20, 0.675, 0.35],
                "min_top3_sector_count": 1,
                "aggression_order": 4,
                "description": "true-sector cohesive top three with balanced top-3 support",
            },
        ),
    ]
)


def _true_sector(trade: dict[str, Any]) -> str:
    ticker = str(trade.get("ticker") or "").upper()
    return str(SECTOR_MAP.get(ticker) or "Unknown")


def _top3_true_sector_cohesion_state_by_window_day(
    trades: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trade in trades:
        grouped.setdefault(
            (
                str(trade.get("window") or ""),
                str(trade.get("decision_date") or "")[:10],
            ),
            [],
        ).append(trade)

    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, rows in grouped.items():
        ranked = sorted(rows, key=lambda row: int(row.get("queue_rank") or 999))
        top3 = ranked[:3]
        sectors = [_true_sector(row) for row in top3]
        known = [sector for sector in sectors if sector and sector != "Unknown"]
        sector_counts = Counter(known)
        same_sector = len(top3) >= 3 and len(known) == 3 and len(set(known)) == 1
        top2_cohesion_already_applied = any(
            bool(row.get("top2_sector_cohesion_profile_applied"))
            or str(row.get("rank_notional_profile_name") or "")
            == "top2_sector_cohesion_technology"
            for row in ranked
        )
        out[key] = {
            "top3_sector_sequence": sectors,
            "top3_sector_count": len(set(known)),
            "top3_sector_distribution": dict(sector_counts),
            "top3_sector_diversity": same_sector,
            "top3_sector_diversity_residual": same_sector
            and not top2_cohesion_already_applied,
            "top3_true_sector_cohesion": same_sector,
            "top3_true_sector_cohesion_residual": same_sector
            and not top2_cohesion_already_applied,
            "top2_sector_cohesion_already_applied": top2_cohesion_already_applied,
        }
    return out


def _profile_name(min_sector_count: int, profile: list[float]) -> str:
    text = "_".join(
        str(round(float(value), 6)).rstrip("0").rstrip(".").replace(".", "p")
        for value in profile
    )
    return f"top3_true_sector_cohesion_count_ge_{min_sector_count}_{text}"


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.RULE_VERSION = RULE_VERSION
    base.TOP3_SECTOR_DIVERSITY_VARIANTS = TOP3_TRUE_SECTOR_COHESION_VARIANTS
    base.OUT_JSON = (
        base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    )
    base.LOG_JSON = base.REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    base.TICKET_JSON = (
        base.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    base.ARTIFACT_MD = (
        base.REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    base.__file__ = str(Path(__file__).resolve())
    base._sector = _true_sector
    base._top3_sector_state_by_window_day = _top3_true_sector_cohesion_state_by_window_day
    base._profile_name = _profile_name


def _payload() -> dict[str, Any]:
    payload = base.build_payload()
    passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_top3_true_sector_cohesion_notional"
        if passed
        else "rejected_state_surface_top3_true_sector_cohesion_notional"
    )
    payload["decision"] = decision
    payload["status"] = "accepted" if passed else "rejected"
    payload["hypothesis"] = (
        "When the accepted rotation state-surface queue has true-sector top-three "
        "cohesion outside the already-promoted top-2 Technology cohort, the queue "
        "may represent a stronger theme and deserve residual default-off paper notional."
    )
    payload["alpha_hypothesis"] = {
        "category": "capital allocation",
        "entry_exit_ranking_or_allocation": "default-off paper allocation",
        "playbook_alignment": (
            "Continues state-surface maturation with a crowding/concentration "
            "quality field and uses exp-20260519-017's negative diversity result "
            "as directional evidence without changing entries or live orders."
        ),
    }
    payload["changed_variable"] = "top3_true_sector_cohesion_rank_notional_profile"
    payload["parameters"]["cohesion_definition"] = (
        "top three state-surface queue rows share the same known SECTOR_MAP sector"
    )
    payload["parameters"]["sector_source"] = "risk_engine.SECTOR_MAP"
    payload["gate2"]["runtime_fields"] = [
        "queue_rank",
        "ticker",
        "risk_engine.SECTOR_MAP sector",
        "decision_date",
        "top3_true_sector_cohesion",
        "top3_true_sector_cohesion_residual",
        "rank_notional_multiplier",
        "entry_open",
        "net_return_pct",
    ]
    payload["history_check"] = {
        "exp-20260518-025": (
            "Accepted top-2 Technology sector cohesion; this run is residual and "
            "does not override dates already carrying that promoted profile."
        ),
        "exp-20260519-017": (
            "Rejected true-sector top-three diversity with aggregate EV -0.4070; "
            "this tests the opposite same-sector concentration interpretation."
        ),
        "exp-20260519-015": (
            "Accepted rank-3 volume confirmation; this run freezes it and does not "
            "change any volume threshold."
        ),
        "anti_repeat": (
            "Not an LLM soft-ranking, candidate-pool, SEC text, near-high, volume, "
            "ret20, ret60, or score-gap retry."
        ),
    }
    payload["llm_metrics"] = {
        "used_llm": False,
        "why_not_llm": (
            "LLM soft-ranking data remains sparse/PIT-limited; this is a deterministic "
            "queue concentration field."
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": passed,
        "backtester_adapter_changed": False,
        "run_adapter_changed": passed,
        "replay_only": True,
        "parity_test_added": passed,
        "live_default_orders_changed": False,
        "core_metrics_changed": False,
        "default_off_paper_only": True,
    }
    payload["interpretation"] = (
        "Top-3 true-sector cohesion improved the default-off state-surface paper overlay without changing core/live behavior."
        if passed
        else "Top-3 true-sector cohesion did not clear Gate 4; keep the accepted rank3-volume stack unchanged."
    )
    payload["rejection_reason"] = None if passed else (
        "Failed Gate 4 under the canonical three-window state-surface paper protocol."
    )
    payload["next_evidence_needed"] = (
        "Promote only as shared default-off paper metadata; keep forward tail/concentration monitoring before any live adapter work."
        if passed
        else "Do not retry nearby top-three sector concentration profiles without forward evidence or a materially different queue-quality field."
    )
    payload["protocol_answers"]["1_alpha_hypothesis"] = (
        "capital allocation: residual true-sector top-three cohesion may signal theme strength after sector diversity proved harmful."
    )
    payload["protocol_answers"]["2_history_check"] = (
        "Prior accepted sector work was top-2 Technology cohesion. exp-20260519-017 rejected top-three diversity; this run tests same-sector concentration as the opposite crowding variable."
    )
    payload["protocol_answers"]["3_single_causal_variable"] = (
        "top3_true_sector_cohesion_rank_notional_profile"
    )
    payload["related_files"] = [
        base.DOC_HELPERS._repo_rel(Path(__file__)),
        base.DOC_HELPERS._repo_rel(base.OUT_JSON),
        base.DOC_HELPERS._repo_rel(base.LOG_JSON),
        base.DOC_HELPERS._repo_rel(base.TICKET_JSON),
        base.DOC_HELPERS._repo_rel(base.ARTIFACT_MD),
        base.DOC_HELPERS._repo_rel(base.EXPERIMENT_LOG),
        "quant/state_surface_sleeve.py",
        "quant/test_state_surface_sleeve.py",
    ]
    return payload


def main() -> None:
    _configure_base_module()
    payload = _payload()
    base.DOC_HELPERS._write_json(base.OUT_JSON, payload)
    base.DOC_HELPERS._write_json(base.LOG_JSON, payload)
    base.DOC_HELPERS._write_json(
        base.TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface top-3 true-sector cohesion notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base.DOC_HELPERS._repo_rel(base.OUT_JSON),
            "summary": (
                f"Top-3 true-sector cohesion best profile {payload['parameters']['best_profile']} "
                f"changed aggregate EV {payload['delta_metrics']['aggregate_ev_delta']:+.4f} "
                f"and PnL ${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    base.ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    base.ARTIFACT_MD.write_text(base._artifact_markdown(payload), encoding="utf-8")
    base.DOC_HELPERS._upsert_jsonl(base.EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
