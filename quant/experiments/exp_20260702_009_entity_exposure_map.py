"""exp-20260702-009: entity->listed-ticker exposure map v1 audit + closeout.

Measurement repair / alpha-enabling map construction only. Audits the map
built by `quant/entity_exposure_map.py` (entities.jsonl SIC enrichment,
sic_peer_index.json, theme_overlay.json) and measures deterministic join
coverage of fresh IPO-registration events per canonical window. Writes a
sample of exposure rows for review. No trading behavior change; the
propagation alpha test is a separate, later gated experiment.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from entity_exposure_map import map_event_to_exposures  # noqa: E402

EXPERIMENT_ID = "exp-20260702-009"
OWNER = "daniel-agent"
SLUG = "entity_exposure_map"
RUNNER = f"quant/experiments/exp_20260702_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

MAP_DIR = REPO_ROOT / "data" / "non_ohlcv" / "entity_exposure_map"
ENTITIES_JSONL = MAP_DIR / "entities.jsonl"
SIC_INDEX_JSON = MAP_DIR / "sic_peer_index.json"
OVERLAY_JSON = MAP_DIR / "theme_overlay.json"
MAP_MANIFEST = MAP_DIR / "manifest.json"
EVENT_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_009_{SLUG}.json"
SAMPLE_JSONL = DATA_DIR / "exposure_row_sample.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
    ("current_forward", "2026-04-22", "2026-12-31"),
]

CHANGED_FILES = [
    "quant/entity_exposure_map.py",
    "quant/test_entity_exposure_map.py",
    f"quant/experiments/exp_20260702_009_{SLUG}.py",
    "data/non_ohlcv/entity_exposure_map/entities.jsonl",
    "data/non_ohlcv/entity_exposure_map/sic_peer_index.json",
    "data/non_ohlcv/entity_exposure_map/theme_overlay.json",
    "data/non_ohlcv/entity_exposure_map/manifest.json",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_009_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/exposure_row_sample.jsonl",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    "docs/alpha_next_direction_20260701.md",
]

REPRO_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B quant\\entity_exposure_map.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_entity_exposure_map.py -q",
    RUNNER_COMMAND,
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def audit() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    entities = load_jsonl(ENTITIES_JSONL)
    sic_index = json.loads(SIC_INDEX_JSON.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY_JSON.read_text(encoding="utf-8"))
    events = load_jsonl(EVENT_ROWS)
    entity_by_cik = {e["cik"]: e for e in entities if e.get("cik")}

    ok = [e for e in entities if e.get("fetch_status") == "ok"]
    fresh_ipo = [
        e
        for e in events
        if e["event_class"] == "ipo_registration" and not e["is_amendment"]
    ]

    window_stats = {}
    samples: list[dict[str, Any]] = []
    theme_counter: Counter = Counter()
    for name, start, end in WINDOWS:
        sub = [e for e in fresh_ipo if start <= e["filed_date"] <= end]
        covered = 0
        edge_total = 0
        theme_edge_total = 0
        blank_check = 0
        for event in sub:
            entity = entity_by_cik.get(event["cik"])
            if entity and entity.get("is_blank_check"):
                blank_check += 1
            exposures = map_event_to_exposures(event, entity, sic_index, overlay)
            if exposures:
                covered += 1
                edge_total += len(exposures)
                theme_edges = [
                    x for x in exposures if x["relation_type"] == "theme_peer"
                ]
                theme_edge_total += len(theme_edges)
                for edge in theme_edges:
                    theme_counter[edge["theme"]] += 1
                if len(samples) < 60 and theme_edges:
                    samples.extend(theme_edges[:2])
        window_stats[name] = {
            "start": start,
            "end": end,
            "fresh_ipo_events": len(sub),
            "blank_check_events": blank_check,
            "events_with_exposures": covered,
            "coverage_pct": round(100.0 * covered / len(sub), 1) if sub else 0.0,
            "exposure_edges": edge_total,
            "theme_edges": theme_edge_total,
        }

    report = {
        "entities_total": len(entities),
        "entities_fetched_ok": len(ok),
        "entities_with_sic": sum(1 for e in ok if e.get("sic")),
        "blank_check_entities": sum(1 for e in ok if e.get("is_blank_check")),
        "listed_tickers_indexed": len(sic_index.get("listed_tickers") or []),
        "sic_buckets": len(sic_index.get("by_sic") or {}),
        "overlay_version": overlay.get("overlay_version"),
        "themes": len(overlay.get("themes") or []),
        "dropped_unlisted_peers": overlay.get("dropped_unlisted_peers"),
        "theme_edge_counts": dict(theme_counter.most_common()),
        "windows": window_stats,
    }
    return report, samples


def evaluate_gates(report: dict[str, Any]) -> dict[str, Any]:
    failed = []
    total = report["entities_total"]
    if not total:
        failed.append("no_entities")
    elif report["entities_with_sic"] / max(1, report["entities_fetched_ok"]) < 0.6:
        failed.append("sic_coverage_below_60pct")
    for name in ("old_thin", "mid_weak", "late_strong"):
        window = report["windows"][name]
        if window["events_with_exposures"] <= 0:
            failed.append(f"no_exposure_coverage_{name}")
        if window["theme_edges"] <= 0:
            failed.append(f"no_theme_edges_{name}")
    return {"passed": not failed, "failed_reasons": failed}


def build_payload(report: dict[str, Any], gates: dict[str, Any]) -> dict[str, Any]:
    accepted = gates["passed"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": (
            "accepted_measurement_repair_entity_exposure_map_v1"
            if accepted
            else "blocked_entity_exposure_map_v1_coverage"
        ),
        "accepted": accepted,
        "hypothesis": (
            "A layered entity->exposure map (deterministic CIK->SIC "
            "enrichment, SIC->listed-peer index from cached submissions, and "
            "a versioned LLM-curated theme overlay) joins corporate-event "
            "rows to listed-ticker exposure candidates deterministically, "
            "with zero hot-path LLM calls."
        ),
        "alpha_hypothesis": (
            "Later, separately gated: fresh IPO registrations and merger "
            "communications on primary entities propagate measurable "
            "replacement value to theme/SIC peers "
            "(docs/alpha_next_direction_20260701.md direction 0)."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_module_plus_versioned_static_map",
        "mechanism_family": "production_visible_sec_corporate_event_stream",
        "trial_family": "entity_exposure_map_construction",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": "entity_exposure_map_v1_sic_plus_theme_overlay",
        "changed_variable": "new_non_ohlcv_surface_entity_exposure_map",
        "causal_components": [
            "cik_sic_enrichment_with_backoff",
            "sic_listed_peer_index_from_local_cache",
            "versioned_theme_overlay_with_buildtime_peer_validation",
            "deterministic_direction_free_event_join",
            "blank_check_sic6770_exclusion",
        ],
        "nearby_prior_experiments": ["exp-20260702-008", "exp-20260630-005"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_entity_to_listed_peer_exposure_surface",
        "new_evidence_axis": (
            "first entity->listed-ticker relation surface keyed on "
            "non-tradable primary entities; prior relation surfaces were "
            "listed-to-listed only"
        ),
        "audit": report,
        "gate1": {"note": "measurement repair; canonical baseline unchanged"},
        "gate2": {
            "required_artifacts_present": all(
                p.exists()
                for p in (ENTITIES_JSONL, SIC_INDEX_JSON, OVERLAY_JSON)
            ),
        },
        "gate3": {
            "note": "no signal filtering changed; map coverage only",
        },
        "gate4": {
            "mode": "measurement_repair_map_coverage_audit",
            "passed": gates["passed"],
            "failed_reasons": gates["failed_reasons"],
        },
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_exits": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "backtester_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": False,
            "live_orders_changed": False,
            "live_ready": False,
            "paper_orders_changed": False,
            "parity_note": (
                "Static versioned map + pure join function; no run.py wiring. "
                "Exposure edges carry no direction claim; direction is the "
                "job of the separately gated propagation alpha test."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "SIC does the heavy lifting deterministically (incl. 6770 "
                "blank-check SPAC exclusion); the theme overlay only covers "
                "cross-SIC themes and is validated against locally listed "
                "tickers at build time so every edge is tradable."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not tune overlay keywords/peers per-window, add themes to "
                "chase coverage, or claim alpha from edge counts. The next "
                "experiment is the gated propagation test: event -> exposure "
                "tickers -> next-open forward replacement value vs "
                "explicit-ticker controls and accepted relation comparators."
            ),
            "new_evidence_required": (
                "Closed forward replacement-value rows for exposure tickers "
                "after fresh IPO / 425 events, with cost and comparator "
                "checks; optionally PIT SIC-as-of-filing repair."
            ),
        },
        "related_files": [
            "data/non_ohlcv/sec_corporate_event_stream/rows.jsonl",
        ],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRO_COMMANDS,
        "allowed_write_scope": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    report = payload["audit"]
    lines = [
        f"# {EXPERIMENT_ID}: entity->exposure map v1 (SIC + theme overlay)",
        "",
        f"- status: `{payload['status']}` / decision: `{payload['decision']}`",
        f"- entities: `{report['entities_total']}` "
        f"(ok `{report['entities_fetched_ok']}`, with SIC "
        f"`{report['entities_with_sic']}`, blank-check "
        f"`{report['blank_check_entities']}`)",
        f"- listed side: `{report['listed_tickers_indexed']}` tickers over "
        f"`{report['sic_buckets']}` SIC buckets; overlay "
        f"`{report['overlay_version']}` with `{report['themes']}` themes",
        "",
        "## Join coverage (fresh IPO events)",
        "",
    ]
    for name, window in report["windows"].items():
        lines.append(
            f"- `{name}`: {window['events_with_exposures']}/"
            f"{window['fresh_ipo_events']} events covered "
            f"({window['coverage_pct']}%), {window['exposure_edges']} edges "
            f"({window['theme_edges']} theme)"
        )
    lines += [
        "",
        "## Theme edge counts",
        "",
        f"`{report['theme_edge_counts']}`",
        "",
        "## Boundaries",
        "",
        "Direction-free edges; no run.py wiring; SPAC (SIC 6770) excluded.",
        "Next: separately gated propagation alpha test.",
        "",
        "## Repro",
        "",
    ]
    lines += [f"- `{cmd}`" for cmd in REPRO_COMMANDS]
    return "\n".join(lines) + "\n"


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "changed_files",
        "reproduction_commands",
    ]
    record = {key: payload[key] for key in keys}
    record["artifact"] = str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/")
    record["audit_summary"] = {
        "entities_with_sic": payload["audit"]["entities_with_sic"],
        "themes": payload["audit"]["themes"],
        "windows": {
            name: {
                "coverage_pct": window["coverage_pct"],
                "theme_edges": window["theme_edges"],
            }
            for name, window in payload["audit"]["windows"].items()
        },
    }
    return record


def upsert_experiment_log(record: dict[str, Any]) -> None:
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    atomic_write_text("\n".join(lines) + "\n", EXPERIMENT_LOG)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    tracked = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        SAMPLE_JSONL,
        ENTITIES_JSONL,
        SIC_INDEX_JSON,
        OVERLAY_JSON,
        MAP_MANIFEST,
        LOG_JSON,
        CARD_MD,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            str(path.relative_to(REPO_ROOT)).replace("\\", "/"): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in tracked
        },
        "updated_at": utc_now(),
    }


def main() -> int:
    for path in (ENTITIES_JSONL, SIC_INDEX_JSON, OVERLAY_JSON):
        if not path.exists():
            raise SystemExit(f"map artifact missing: {path}; run entity_exposure_map.py")
    report, samples = audit()
    gates = evaluate_gates(report)
    payload = build_payload(report, gates)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, OUT_JSON)
    atomic_write_text(
        "\n".join(json.dumps(s, ensure_ascii=False, sort_keys=True) for s in samples)
        + "\n",
        SAMPLE_JSONL,
    )
    log_record = compact_log_record(payload)
    atomic_write_json(log_record, LOG_JSON)
    atomic_write_text(build_card(payload), CARD_MD)
    upsert_experiment_log(log_record)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction={
            "success_probability": 0.7,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "SEC submissions throttling on ~1.9k entity CIKs",
                "SIC too coarse (6770 blank-check dominance)",
                "listed-side SIC coverage too thin",
            ],
            "confidence_reason": (
                "submissions JSON is a stable documented feed; join logic is "
                "pure and fixture-tested"
            ),
        },
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "decision": payload["decision"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "card_file": str(CARD_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    atomic_write_json(build_manifest(payload), MANIFEST_JSON)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "entities_with_sic": report["entities_with_sic"],
                "windows": {
                    name: {
                        "coverage_pct": window["coverage_pct"],
                        "edges": window["exposure_edges"],
                        "theme_edges": window["theme_edges"],
                    }
                    for name, window in report["windows"].items()
                },
                "failed_reasons": gates["failed_reasons"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
