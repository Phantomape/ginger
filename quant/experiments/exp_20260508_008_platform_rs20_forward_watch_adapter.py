"""exp-20260508-008: platform RS20 no-gap forward watch adapter.

Measurement adapter supporting alpha search. exp-20260508-007 found a clean
but underpowered no-gap split inside missed platform RS20 candidates. This
experiment records the code path that accumulates future observations without
changing production ranking, sizing, exits, slots, or orders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260508-008"
STEM = "platform_rs20_forward_watch_adapter"

SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260508-007"
    / "platform_rs20_no_gap_missed_feature_audit.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _write_artifact(payload: dict[str, Any]) -> None:
    source = payload["source_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} Platform RS20 Forward Watch Adapter",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        "- production orders changed: false",
        "- run adapter changed: true",
        "",
        "## Source Evidence",
        "",
        (
            "- exp-20260508-007 no-gap matched: "
            f"count={source['matched']['candidate_count']}, "
            f"pnl={source['matched']['total_pnl']}, "
            f"win_rate={source['matched']['win_rate']}"
        ),
        (
            "- exp-20260508-007 gap-up complement: "
            f"count={source['complement']['candidate_count']}, "
            f"pnl={source['complement']['total_pnl']}, "
            f"win_rate={source['complement']['win_rate']}"
        ),
        "",
        "## Adapter",
        "",
        "- `quant/platform_rs20_watch.py` records default-off watch rows.",
        "- `quant/run.py` persists the watch after entry execution planning.",
        "- `quant/report_generator.py` renders the watch as observe-only.",
        "- `quant/test_platform_rs20_watch.py` covers classification, dedupe persistence, and report rendering.",
        "",
    ]
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "measurement_repair_supporting_alpha_search",
        "status": payload["decision"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": "entry_forward_attribution",
        "change_type": "forward_watch_adapter",
        "mechanism_family": "platform_rs20_no_gap_forward_sample_accumulation",
        "single_causal_variable": "platform_rs20_no_gap_forward_watch_logging",
        "historical_experiment_check": payload["history_check"],
        "parameters": payload["parameters"],
        "source_metrics": payload["source_metrics"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_reason": payload["decision_reason"],
        "next_action": payload["next_action"],
        "related_files": payload["related_files"],
        "verification": payload["verification"],
    }


def main() -> None:
    source = _load_json(SOURCE_JSON)
    source_metrics = {
        "matched": source["primary_split"]["matched"],
        "complement": source["primary_split"]["complement"],
        "observed_gate_failures": source["observed_gate"]["failures"],
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "hypothesis": (
            "The platform RS20 no-gap missed-candidate hypothesis cannot be "
            "promoted from six frozen rows, so the correct next step is to "
            "accumulate forward observations through a default-off run adapter."
        ),
        "decision": "accepted_measurement_adapter",
        "decision_reason": (
            "Adapter is data-only, explicitly observe-only in reports, and covered "
            "by tests. It creates future alpha evidence without changing live orders."
        ),
        "source_metrics": source_metrics,
        "parameters": {
            "watch_name": "PLATFORM_RS20_NO_GAP_FORWARD_WATCH",
            "platform_pool": ["META", "NFLX", "GOOG", "AMZN", "SPOT", "DIS", "APP"],
            "rs20_excess_threshold": 0.05,
            "gap_up_threshold": 0.03,
            "source_decisions": ["scarce_slot_breakout_deferred", "slot_sliced"],
            "forward_promotion_gate": {
                "no_gap_missed_candidates": ">= 8",
                "single_ticker_positive_contribution": "<= 50%",
                "closed_forward_outcomes": "required before sleeve replay",
            },
        },
        "history_check": {
            "exp-20260507-034": "Hard platform RS20 entry gate rejected.",
            "exp-20260507-035": "Missed platform RS20 sleeve positive but underpowered and APP-concentrated.",
            "exp-20260508-007": "No-gap split clean in-sample but failed count and concentration gates.",
            "mechanism_insight_conflict": (
                "No conflict: this does not promote a rule or retry a threshold; "
                "it persists forward evidence for the next valid retry."
            ),
        },
        "gate4": {
            "passed": None,
            "basis": "Measurement adapter only; no strategy replay or production orders changed.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "report_adapter_changed": True,
            "parity_test_added": False,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM/news replay is outside this deterministic watch adapter.",
        },
        "next_action": (
            "Let daily runs accumulate data/platform_rs20_no_gap_forward_watch.jsonl; "
            "only retry a sleeve replay after enough closed forward outcomes exist."
        ),
        "related_files": [
            "quant/platform_rs20_watch.py",
            "quant/test_platform_rs20_watch.py",
            "quant/run.py",
            "quant/report_generator.py",
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(Path(__file__)),
        ],
        "verification": {
            "tests": (
                ".\\.venv\\Scripts\\python.exe -m pytest "
                "quant\\test_platform_rs20_watch.py "
                "quant\\test_oracle_diagnostics.py "
                "quant\\test_entry_execution_attribution.py -q -> 12 passed"
            ),
            "ast": "AST parse OK for watch module, tests, run.py, report_generator.py, exp-007 script.",
        },
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "title": "Platform RS20 no-gap forward watch adapter",
        "result": payload["decision"],
        "created_at": timestamp,
        "completed_at": timestamp,
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _log_record(payload))
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG, _log_record(payload))
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "source_gate_failures": source_metrics["observed_gate_failures"],
                "related_files": payload["related_files"],
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
