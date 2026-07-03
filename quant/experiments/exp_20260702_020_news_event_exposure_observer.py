"""exp-20260702-020: second-order news-event exposure observation ledger.

Measurement repair / alpha-enabling surface. Audits the ledger built by
`quant/news_event_exposure_observer.py`: structured news events (both
polarities, all relation types) joined to the entity_exposure_map to record
SIC-peer and theme-peer second-order observation rows with 5d/10d SPY-excess
settlement. Any polarity statistics in the artifact are DESCRIPTIVE context
only; the propagation verdict belongs to a later, separately predeclared
read. No trading behavior change.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260702-020"
OWNER = "daniel-agent"
SLUG = "news_event_exposure_observer"
RUNNER = f"quant/experiments/exp_20260702_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

LEDGER_DIR = REPO_ROOT / "data" / "non_ohlcv" / "news_event_exposure_observations"
ROWS_JSONL = LEDGER_DIR / "rows.jsonl"
LEDGER_MANIFEST = LEDGER_DIR / "manifest.json"
REPLAY_SOURCE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260630-006"
    / "daily_news_structured_event_rows.jsonl"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_020_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    "quant/news_event_exposure_observer.py",
    "quant/test_news_event_exposure_observer.py",
    f"quant/experiments/exp_20260702_020_{SLUG}.py",
    "data/non_ohlcv/news_event_exposure_observations/rows.jsonl",
    "data/non_ohlcv/news_event_exposure_observations/manifest.json",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_020_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    "docs/alpha_next_direction_20260701.md",
]
REPRO_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B quant\\news_event_exposure_observer.py "
    "--replay-file data\\experiments\\exp-20260630-006\\"
    "daily_news_structured_event_rows.jsonl",
    ".\\.venv\\Scripts\\python.exe -B -m pytest "
    "quant\\test_news_event_exposure_observer.py -q",
    RUNNER_COMMAND,
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict[str, Any]:
    rows = [
        json.loads(l)
        for l in ROWS_JSONL.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    closed = [r for r in rows if r["outcome_status"] == "closed"]
    keys = [(r["event_id"], r["exposure_ticker"]) for r in rows]
    concentration = Counter(r["first_order_ticker"] for r in rows)
    top_first, top_first_n = concentration.most_common(1)[0]

    descriptive = {}
    for polarity in ("positive", "negative"):
        sub = [
            r["excess_10d"]
            for r in closed
            if r["event_polarity"] == polarity and r["excess_10d"] is not None
        ]
        descriptive[polarity] = {
            "closed_rows": len(sub),
            "median_excess_10d_bp": round(1e4 * median(sub), 1) if sub else None,
            "positive_share": round(sum(1 for v in sub if v > 0) / len(sub), 3)
            if sub
            else None,
        }

    return {
        "rows": len(rows),
        "duplicate_keys": len(keys) - len(set(keys)),
        "closed_rows": len(closed),
        "pending_rows": len(rows) - len(closed),
        "event_ids": len({r["event_id"] for r in rows}),
        "first_order_tickers": len({r["first_order_ticker"] for r in rows}),
        "exposure_tickers": len({r["exposure_ticker"] for r in rows}),
        "event_date_span": [
            min(r["event_date"] for r in rows),
            max(r["event_date"] for r in rows),
        ],
        "relation_type_counts": dict(
            Counter(r["relation_type"] for r in rows)
        ),
        "event_polarity_counts": dict(
            Counter(r["event_polarity"] for r in rows)
        ),
        "top_first_order_ticker": top_first,
        "top_first_order_share": round(top_first_n / len(rows), 3),
        "descriptive_polarity_split_NOT_A_VERDICT": descriptive,
    }


def evaluate_gates(report: dict[str, Any]) -> dict[str, Any]:
    failed = []
    if report["duplicate_keys"]:
        failed.append("duplicate_rows")
    if report["closed_rows"] < 100:
        failed.append("too_few_closed_rows")
    for polarity, stats in report[
        "descriptive_polarity_split_NOT_A_VERDICT"
    ].items():
        if stats["closed_rows"] <= 0:
            failed.append(f"no_closed_rows_{polarity}")
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
            "accepted_measurement_repair_news_event_second_order_exposure_ledger"
            if accepted
            else "blocked_news_event_second_order_exposure_ledger"
        ),
        "accepted": accepted,
        "hypothesis": (
            "Qualified structured news events on first-order tickers can be "
            "joined to the entity_exposure_map to record second-order "
            "SIC-peer / theme-peer observation rows with next-open 5d/10d "
            "SPY-excess settlement, replayable over the 2026-01..06 archive "
            "and forward-accumulating for current events."
        ),
        "alpha_hypothesis": (
            "Later, separately predeclared read: do second-order exposure "
            "names drift with (or against) first-order event polarity after "
            "the overnight repricing (Meta->Nebius style propagation)?"
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_module_plus_append_only_ledger",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "news_event_second_order_exposure_observer",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": (
            "news_event_second_order_exposure_observation_ledger_v1"
        ),
        "changed_variable": "new_non_ohlcv_surface_news_event_exposure_observations",
        "causal_components": [
            "first_order_ticker_sic_peer_join",
            "theme_overlay_membership_join",
            "max_15_sic_peers_deterministic",
            "next_open_entry_5d_10d_close_spy_excess",
            "append_only_event_ticker_dedup",
            "polarity_and_relation_recorded_not_predeclared",
        ],
        "nearby_prior_experiments": [
            "exp-20260630-005",
            "exp-20260630-006",
            "exp-20260702-009",
            "exp-20260702-017",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_second_order_exposure_observation_rows",
        "new_evidence_axis": (
            "first join of the structured news event ledger to the "
            "entity_exposure_map relation graph; prior news observations "
            "were first-order-only"
        ),
        "audit": report,
        "gate1": {"note": "measurement repair; canonical baseline unchanged"},
        "gate2": {
            "required_artifacts_present": ROWS_JSONL.exists()
            and LEDGER_MANIFEST.exists(),
        },
        "gate3": {"note": "no signal filtering changed; observation rows only"},
        "gate4": {
            "mode": "measurement_repair_ledger_audit",
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
                "Append-only observation ledger + CLI; NOT wired into run.py "
                "yet (deferred to avoid contending with active claims). Daily "
                "refresh = rerun the CLI; settlement is idempotent."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp-20260630-006 replay already carried five months of "
                "qualified structured events, so second-order rows "
                "materialized immediately; settlement coverage is bounded by "
                "hot-warehouse per-ticker gaps (2026-04-24..05-21) and recent "
                "events still inside the 10d horizon."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not read polarity separation off this artifact as a "
                "verdict, and do not re-slice by relation type, theme, or "
                "horizon outside a predeclared read. The read experiment "
                "must predeclare cohort, minimum closed rows per cell, "
                "baseline control, and sign rule before looking."
            ),
            "new_evidence_required": (
                "More closed rows per (polarity x relation_type) cell — "
                "target >= 50 per cell — then one predeclared attribution "
                "read reusing the exp-20260702-017 baseline framework."
            ),
        },
        "related_files": [
            "data/experiments/exp-20260630-006/daily_news_structured_event_rows.jsonl",
            "data/non_ohlcv/entity_exposure_map/theme_overlay.json",
        ],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRO_COMMANDS,
        "allowed_write_scope": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    report = payload["audit"]
    desc = report["descriptive_polarity_split_NOT_A_VERDICT"]
    lines = [
        f"# {EXPERIMENT_ID}: second-order news-event exposure ledger",
        "",
        f"- status: `{payload['status']}` / decision: `{payload['decision']}`",
        f"- rows: `{report['rows']}` (closed `{report['closed_rows']}`, "
        f"pending `{report['pending_rows']}`), events `{report['event_ids']}`, "
        f"span `{report['event_date_span']}`",
        f"- first-order tickers `{report['first_order_tickers']}` "
        f"(top `{report['top_first_order_ticker']}` share "
        f"`{report['top_first_order_share']}`), exposure tickers "
        f"`{report['exposure_tickers']}`",
        f"- relation types: `{report['relation_type_counts']}`",
        "",
        "## Descriptive polarity split (NOT a verdict)",
        "",
        f"`{desc}`",
        "",
        "The verdict requires a separately predeclared read (cohort, >= 50",
        "closed rows per polarity x relation cell, baseline control, sign",
        "rule fixed before looking).",
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
        "rows": payload["audit"]["rows"],
        "closed_rows": payload["audit"]["closed_rows"],
        "event_ids": payload["audit"]["event_ids"],
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


def main() -> int:
    if not ROWS_JSONL.exists():
        raise SystemExit("ledger missing: run news_event_exposure_observer.py first")
    report = audit()
    gates = evaluate_gates(report)
    payload = build_payload(report, gates)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    atomic_write_json(log_record, LOG_JSON)
    atomic_write_text(build_card(payload), CARD_MD)
    upsert_experiment_log(log_record)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction={
            "success_probability": 0.75,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "structured event density too low",
                "second-order rows dominated by a few mega-cap first-order tickers",
                "hot warehouse gaps leave most replay rows unsettled",
            ],
            "confidence_reason": (
                "replay source and exposure map already exist; join and "
                "settlement are pure and fixture-tested"
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
            "implementation_mode": payload["implementation_mode"],
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
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            str(p.relative_to(REPO_ROOT)).replace("\\", "/"): {
                "exists": p.exists(),
                "sha256": sha256(p),
            }
            for p in (
                REPO_ROOT / RUNNER,
                OUT_JSON,
                ROWS_JSONL,
                LEDGER_MANIFEST,
                LOG_JSON,
                CARD_MD,
            )
        },
        "updated_at": utc_now(),
    }
    atomic_write_json(manifest, MANIFEST_JSON)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "rows": report["rows"],
                "closed_rows": report["closed_rows"],
                "descriptive_polarity_split_NOT_A_VERDICT": report[
                    "descriptive_polarity_split_NOT_A_VERDICT"
                ],
                "failed_reasons": gates["failed_reasons"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
