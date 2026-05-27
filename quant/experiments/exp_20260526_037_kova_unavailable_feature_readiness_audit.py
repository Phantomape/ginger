"""exp-20260526-037: Kova unavailable-feature readiness audit.

This measurement-repair audit classifies the Kova ideas that were mentioned
but not suitable for the daily-OHLCV VCP attribution batch. It does not create
signals, filters, rankings, sizing changes, exits, or orders.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    REPO_ROOT,
    SOURCE_EXP007_JSON,
    _audit_open_positions,
    _load_json,
    _repo_rel,
    _safe,
    _write_json,
    _write_text,
)


EXPERIMENT_ID = "exp-20260526-037"
STEM = "kova_unavailable_feature_readiness_audit"
RUNNER = REPO_ROOT / "quant" / "experiments" / "exp_20260526_037_kova_unavailable_feature_readiness_audit.py"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}

CANONICAL_WINDOWS = [
    {"name": "late_strong", "start": "2025-10-23", "end": "2026-04-21"},
    {"name": "mid_weak", "start": "2025-04-23", "end": "2025-10-22"},
    {"name": "old_thin", "start": "2024-10-02", "end": "2025-04-22"},
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _iter_repo_files() -> list[str]:
    paths: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        paths.append(_repo_rel(path))
    return sorted(paths)


def _matching_files(files: list[str], tokens: tuple[str, ...], limit: int = 20) -> list[str]:
    lowered = [(name, name.lower()) for name in files]
    matches = [
        name
        for name, lower in lowered
        if any(token.lower() in lower for token in tokens)
    ]
    return sorted(matches)[:limit]


def _jsonl_contains(path: Path, experiment_id: str) -> bool:
    if not path.exists():
        return False
    needle = f'"experiment_id": "{experiment_id}"'
    compact_needle = f'"experiment_id":"{experiment_id}"'
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            if needle in line or compact_needle in line:
                return True
    return False


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    if _jsonl_contains(path, EXPERIMENT_ID):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True) + "\n")


def _paths_payload() -> dict[str, str]:
    return {
        "json": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        "markdown": _repo_rel(ARTIFACT_MD),
    }


def _build_ideas(files: list[str]) -> dict[str, dict[str, Any]]:
    intraday_files = _matching_files(
        files,
        ("intraday", "minute", "15m", "60m", "1min", "5min", "hourly"),
    )
    ohlcv_files = _matching_files(files, ("ohlcv_snapshot",), limit=10)
    earnings_files = _matching_files(files, ("earnings_snapshot", "estimate_revision"), limit=12)
    rs_files = _matching_files(files, ("relative_strength", "rs20", "rs60", "rs_rating"), limit=12)
    institutional_files = _matching_files(files, ("13f", "institutional", "ownership"), limit=12)
    addon_files = _matching_files(files, ("addon", "add-on", "followthrough", "follow-through"), limit=12)
    stop_files = _matching_files(files, ("stop_breach", "r_multiple", "risk_haircut", "wide_stop"), limit=12)

    return {
        "intraday_precision_entry_15m_60m": {
            "kova_idea": "Use 15-minute/60-minute charts for precise pivot entries.",
            "readiness_status": "blocked_no_pit_intraday_ohlcv",
            "can_run_alpha_now": False,
            "coverage_evidence": {
                "daily_ohlcv_snapshots": ohlcv_files,
                "intraday_like_files": intraday_files,
            },
            "reason": (
                "The repository has daily OHLCV snapshots for the canonical windows, "
                "but no PIT 15m/60m bar archive was found. Daily bars cannot replay "
                "Kova's intraday precision entry without lookahead or invented fills."
            ),
            "next_unblocker": (
                "Add PIT intraday OHLCV snapshots with vendor/as-of timestamps and "
                "a replay fill policy before testing intraday pivot timing."
            ),
        },
        "canslim_fundamental_growth": {
            "kova_idea": "Require CAN SLIM-style EPS/sales growth and leadership context.",
            "readiness_status": "partial_non_ohlcv_not_canslim_complete",
            "can_run_alpha_now": False,
            "coverage_evidence": {
                "earnings_or_estimate_files": earnings_files,
                "missing_surfaces": [
                    "PIT quarterly EPS growth",
                    "PIT quarterly sales growth",
                    "PIT annual EPS growth",
                    "share float/supply trend",
                    "CAN SLIM composite labels",
                ],
            },
            "reason": (
                "Earnings snapshots and estimate-revision ledgers exist, but they are "
                "not a complete PIT CAN SLIM fundamental surface and should not be "
                "substituted for explicit growth fields."
            ),
            "next_unblocker": (
                "Create a forward-audited fundamental-growth sidecar with same-as-of "
                "identity before using CAN SLIM-style filters or ranking."
            ),
        },
        "rs_rating_or_leader_laggard": {
            "kova_idea": "Use RS Rating / leader-laggard confirmation.",
            "readiness_status": "proxy_only_no_ibd_rs_rating",
            "can_run_alpha_now": False,
            "coverage_evidence": {
                "relative_strength_proxy_files": rs_files,
                "missing_surfaces": ["proprietary or audited PIT RS Rating field"],
            },
            "reason": (
                "The codebase has relative-strength proxies, but no explicit PIT RS "
                "Rating. A proxy can be a separate hypothesis, not the same Kova field."
            ),
            "next_unblocker": (
                "Define a Ginger-native relative-strength proxy with its own frozen "
                "baseline, or ingest an audited RS Rating source if available."
            ),
        },
        "institutional_ownership_13f_accumulation": {
            "kova_idea": "Use institutional sponsorship / 13F accumulation.",
            "readiness_status": "blocked_no_pit_13f_ownership_surface",
            "can_run_alpha_now": False,
            "coverage_evidence": {
                "institutional_like_files": institutional_files,
                "required_fields": [
                    "manager filing date",
                    "reported period",
                    "position change",
                    "float-adjusted ownership",
                    "as-of availability date",
                ],
            },
            "reason": (
                "No usable PIT 13F/institutional ownership surface was found. "
                "Using today's ownership data for historical signals would be lookahead."
            ),
            "next_unblocker": (
                "Build a vendor/as-of 13F ownership sidecar and only then test "
                "institutional sponsorship as metadata or ranking."
            ),
        },
        "pyramid_addon_sequence": {
            "kova_idea": "Pyramid only after confirmation, adding as the position works.",
            "readiness_status": "requires_separate_lifecycle_replay",
            "can_run_alpha_now": False,
            "coverage_evidence": {
                "existing_addon_research_files": addon_files,
                "policy_surface": "Follow-through add-ons already exist as a separate production/backtest family.",
            },
            "reason": (
                "Pyramiding is a capital-allocation/lifecycle policy, not a candidate "
                "metadata bucket. It would change sizing, heat, and fill path and must "
                "be tested as one causal add-on policy against the accepted core stack."
            ),
            "next_unblocker": (
                "Only revisit with a new ex-ante add-on quality discriminator and a "
                "full real replay; do not mine frozen VCP winners for a pyramid rule."
            ),
        },
        "stop_under_higher_low_r_multiple": {
            "kova_idea": "Place stops under the higher low and evaluate trades in R multiples.",
            "readiness_status": "partial_requires_exit_and_risk_policy_replay",
            "can_run_alpha_now": False,
            "coverage_evidence": {
                "stop_or_risk_files": stop_files,
                "related_kova_attribution": "exp-20260526-022 computed pre-signal higher-low/base geometry only as metadata.",
            },
            "reason": (
                "Daily OHLCV can approximate a prior higher low, and R diagnostics exist, "
                "but using that level as a stop or sizing denominator changes exits and "
                "risk allocation. That is outside the accepted VCP paper metadata sleeve."
            ),
            "next_unblocker": (
                "Define a single VCP-specific exit/risk replay with explicit stop timing, "
                "gap handling, and R denominator before testing this as alpha."
            ),
        },
    }


def _build_payload() -> dict[str, Any]:
    files = _iter_repo_files()
    ideas = _build_ideas(files)
    blocked = [key for key, item in ideas.items() if not item["can_run_alpha_now"]]
    partial = [
        key
        for key, item in ideas.items()
        if item["readiness_status"].startswith("partial")
        or item["readiness_status"].startswith("proxy")
        or item["readiness_status"].startswith("requires")
    ]
    created_at = _now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only_data_gap",
        "decision": "observed_only_data_gap_kova_unavailable_features",
        "created_at": created_at,
        "lane": "measurement_repair",
        "registry_lane": "measurement_repair",
        "change_type": "measurement_repair_for_alpha_search",
        "trial_family": "kova_unavailable_feature_readiness",
        "trial_variant_id": "daily_ohlcv_gap_audit_v1",
        "changed_variable": "kova_unavailable_feature_coverage_status_v1",
        "single_causal_variable": "kova_unavailable_feature_coverage_status_v1",
        "alpha_hypothesis": (
            "Kova ideas that require intraday, fundamental, institutional, or lifecycle "
            "risk surfaces should be classified by PIT readiness before any alpha rule is attempted."
        ),
        "history_check": {
            "nearby_daily_ohlcv_kova_experiments": [
                "exp-20260526-022",
                "exp-20260526-023",
                "exp-20260526-024",
                "exp-20260526-025",
            ],
            "result": "Daily-OHLCV candidate metadata ideas were tested separately; remaining ideas are data or lifecycle gated.",
        },
        "gate1": {
            "baseline": _repo_rel(SOURCE_EXP007_JSON),
            "windows": CANONICAL_WINDOWS,
            "core_logic_changed": False,
        },
        "gate2": {
            "open_positions_audit": _audit_open_positions(),
            "data_surface_audit": "No missing daily OHLCV blocker for this audit; non-daily surfaces are classified below.",
        },
        "gate3": {
            "survival_impact": "none",
            "reason": "No filter, rank, sizing, exit, or order rule is added.",
        },
        "gate4": {
            "promotion_allowed": False,
            "reason": "This audit only records readiness/data gaps for future experiments.",
        },
        "ideas": ideas,
        "summary": {
            "idea_count": len(ideas),
            "blocked_or_not_alpha_ready_count": len(blocked),
            "partial_or_policy_gated_count": len(partial),
            "can_run_alpha_now_count": 0,
            "recommendation": (
                "Do not implement more Kova filters from these fields until intraday, "
                "fundamental, 13F, or lifecycle replay surfaces are explicitly added."
            ),
        },
        "artifacts": _paths_payload(),
        "related_files": [
            _repo_rel(RUNNER),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
        ],
        "production_impact": {
            "alters_orders": False,
            "alters_core_entries": False,
            "alters_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "metadata_only": True,
        },
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260526_037_kova_unavailable_feature_readiness_audit.py"
        ),
    }
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Kova Unavailable Feature Readiness Audit",
        "",
        "## Decision",
        "",
        f"`{payload['decision']}`. No strategy change, order change, rank change, sizing change, or exit change is allowed from this audit.",
        "",
        "## Readiness Matrix",
        "",
        "| Idea | Status | Why not tested as alpha now | Next unblocker |",
        "|---|---|---|---|",
    ]
    for key, item in payload["ideas"].items():
        lines.append(
            "| "
            + key
            + " | `"
            + item["readiness_status"]
            + "` | "
            + item["reason"]
            + " | "
            + item["next_unblocker"]
            + " |"
        )
    lines.extend(
        [
            "",
            "## Gate Notes",
            "",
            "- Gate 1: reused the accepted VCP rank-notional source only as context.",
            "- Gate 2: daily OHLCV is present; missing or incomplete non-daily surfaces are the result.",
            "- Gate 3: no survival impact because no filter is added.",
            "- Gate 4: promotion is disallowed; this is a readiness/data-gap artifact.",
            "",
            "## Reproduction",
            "",
            "```powershell",
            payload["repro_command"],
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(EXPERIMENT_REGISTRY)
    experiments = registry.setdefault("experiments", [])
    updated = False
    for entry in experiments:
        if entry.get("experiment_id") == EXPERIMENT_ID:
            entry.update(
                {
                    "status": payload["status"],
                    "lane": payload["registry_lane"],
                    "owner": "codex-kova",
                    "hypothesis": payload["alpha_hypothesis"],
                    "ticket_file": _repo_rel(TICKET_JSON),
                    "updated_at": payload["created_at"],
                    "completed_at": payload["created_at"],
                    "result": {
                        "decision": payload["decision"],
                        "artifact": _repo_rel(ARTIFACT_MD),
                        "json": _repo_rel(OUT_JSON),
                        "summary": payload["summary"]["recommendation"],
                    },
                }
            )
            updated = True
            break
    if not updated:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "updated_at": payload["created_at"],
                "completed_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"]["recommendation"],
                },
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _persist(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "owner": "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": "kova_readiness_audit",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "nearby_prior_experiments": payload["history_check"]["nearby_daily_ohlcv_kova_experiments"],
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": payload["related_files"]
        + [
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
            "docs/data_edge_context_layers.md",
        ],
        "must_not_touch": [
            "quant/run.py",
            "quant/backtester.py",
            "quant/volatility_contraction_paper_sleeve.py",
        ],
        "locked_variables": [
            "core entries",
            "ranking",
            "sizing",
            "exits",
            "LLM/news",
            "universe",
            "live/default orders",
            "VCP top-2 rank-notional paper sleeve",
        ],
        "evaluation_windows": CANONICAL_WINDOWS,
        "acceptance_rule": "Produce a reproducible PIT-readiness matrix; no strategy rule may be promoted from this audit.",
        "created_at": payload["created_at"],
        "completed_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"]["recommendation"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
        },
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_json(DOCS_TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _append_jsonl_once(EXPERIMENT_LOG, payload)
    _update_registry(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "idea_count": payload["summary"]["idea_count"],
                "can_run_alpha_now_count": payload["summary"]["can_run_alpha_now_count"],
                "artifact": _repo_rel(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
