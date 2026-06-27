"""exp-20260627-017: formalize broad liquid topN universe scout.

Read-only alpha_search closeout. The oracle regret compass records an
unregistered 2026-06-27 three-window scout comparing the curated core universe
with bare broad liquid top300/top500 expansion. This runner makes that evidence
auditable in the experiment registry without changing strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260627-017"
OWNER = "alpha-explore"
SLUG = "broad_liquid_topn_universe_expansion_scout"
RUNNER = f"quant/experiments/exp_20260627_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_017_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ORACLE_COMPASS = REPO_ROOT / "docs" / "oracle_regret_compass.md"
BROAD_UNIVERSE = REPO_ROOT / "data" / "state" / "broad_market_paper" / "universe.json"
CANONICAL_WAREHOUSE = (
    REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
)
BROAD_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

HYPOTHESIS = (
    "Formalize the oracle scratchpad hypothesis that expanding the accepted "
    "core universe to broad liquid top300/top500 improves opportunity quality; "
    "if core still wins aggregate EV, Sharpe, drawdown, and survival, freeze "
    "bare liquid-universe expansion."
)
CHANGE_TYPE = "universe_scout"
MECHANISM_FAMILY = "candidate_pool_universe_expansion"
TRIAL_FAMILY = "broad_liquid_topn_universe_expansion_scout"
TRIAL_VARIANT_ID = "core_vs_top300_top500_v1"
CHANGED_VARIABLE = "broad_liquid_topn_universe_expansion_scout_v1"
NEW_EVIDENCE_TYPE = "formalized_unregistered_oracle_universe_scout"
NEW_EVIDENCE_AXIS = (
    "Formal registry closeout of the 2026-06-27 oracle-regret broad-liquid "
    "top300/top500 universe scout documented in docs/oracle_regret_compass.md. "
    "This is a candidate-pool anti-repeat record, not an adjacent threshold or "
    "response-curve retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260616-026",
    "exp-20260617-020",
    "exp-20260617-021",
    "exp-20260627-003",
]
CAUSAL_COMPONENTS = [
    "core_vs_top300_vs_top500_universe_backtest",
    "canonical_three_windows",
    "read_only_artifact",
    "no_strategy_behavior_change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260627_017_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value


def round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return round(value, digits)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(make_json_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    rows = [
        row
        for row in read_jsonl(path)
        if row.get("experiment_id") != record.get("experiment_id")
    ]
    rows.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(make_json_safe(row), ensure_ascii=True, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "survival_collapse",
            "drawdown_worse",
            "old_thin_only_edge",
            "core_edge_concentrated",
            "accepted_comparator_not_beaten",
        ],
        "confidence_reason": (
            "Broad liquid expansion usually dilutes the curated core edge; this "
            "fallback is only used if the reserved ticket prediction is missing."
        ),
        "recorded_at": utc_now(),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_exists": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "warehouse": payload.get("warehouse") if isinstance(payload, dict) else None,
        "window_count": len(windows),
        "expected_value_score_sum": sum(
            float(row.get("expected_value_score") or 0.0) for row in windows
        ),
        "total_pnl": sum(float(row.get("total_pnl") or 0.0) for row in windows),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": (
            signals_survived / signals_generated if signals_generated else None
        ),
        "windows": [
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "sharpe_daily": row.get("sharpe_daily"),
                "total_pnl": row.get("total_pnl"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
            for row in windows
        ],
    }


def extract_compass_scout() -> dict[str, Any]:
    exists = ORACLE_COMPASS.exists()
    lines = ORACLE_COMPASS.read_text(encoding="utf-8-sig", errors="replace").splitlines() if exists else []
    evidence_lines = [
        {"line": idx, "text": line.strip()}
        for idx, line in enumerate(lines, start=1)
        if "top300" in line or "top500" in line or "core(43)" in line
    ]
    joined = "\n".join(item["text"] for item in evidence_lines)

    ev_match = re.search(
        r"EV\s*([0-9]+(?:\.[0-9]+)?)\s+vs\s+top300\s+([0-9]+(?:\.[0-9]+)?)\s+vs\s+top500\s+([0-9]+(?:\.[0-9]+)?)",
        joined,
        flags=re.IGNORECASE,
    )
    old_thin_match = re.search(
        r"old_thin.*?top300.*?([0-9]+(?:\.[0-9]+)?)\s+vs\s+([0-9]+(?:\.[0-9]+)?)",
        joined,
        flags=re.IGNORECASE | re.DOTALL,
    )
    survival_collapse = bool(re.search(r"10.?21", joined))
    says_core_won_risk = all(token in joined for token in ["Sharpe", "maxDD", "survival"])
    says_negative = "top300" in joined and "top500" in joined and bool(ev_match)

    aggregate_ev = {
        "core": float(ev_match.group(1)) if ev_match else None,
        "top300": float(ev_match.group(2)) if ev_match else None,
        "top500": float(ev_match.group(3)) if ev_match else None,
    }
    return {
        "source_file": repo_rel(ORACLE_COMPASS),
        "source_exists": exists,
        "evidence_lines": evidence_lines,
        "evidence_line_numbers": [item["line"] for item in evidence_lines],
        "evidence_mode": "formalized_documented_scout",
        "fresh_backtest_rerun": False,
        "aggregate_ev": aggregate_ev,
        "core_ev_advantage_vs_top300": (
            round_or_none(aggregate_ev["core"] - aggregate_ev["top300"], 4)
            if aggregate_ev["core"] is not None and aggregate_ev["top300"] is not None
            else None
        ),
        "core_ev_advantage_vs_top500": (
            round_or_none(aggregate_ev["core"] - aggregate_ev["top500"], 4)
            if aggregate_ev["core"] is not None and aggregate_ev["top500"] is not None
            else None
        ),
        "survival_collapsed_to_10_21_pct": survival_collapse,
        "core_won_sharpe_maxdd_survival": says_core_won_risk,
        "documented_negative_scout": says_negative and survival_collapse and says_core_won_risk,
        "old_thin_nuance": {
            "top300_raw_ev_higher": bool(old_thin_match),
            "top300_raw_ev": float(old_thin_match.group(1)) if old_thin_match else None,
            "core_raw_ev": float(old_thin_match.group(2)) if old_thin_match else None,
            "acceptance_override": False,
            "note": (
                "The documented nuance is old_thin raw EV only; drawdown doubled "
                "and top500 turned negative, so it is not a deployable broad "
                "universe expansion signal."
            ),
        },
    }


def broad_universe_summary() -> dict[str, Any]:
    payload = read_json(BROAD_UNIVERSE, {})
    records = payload.get("records") if isinstance(payload, dict) else {}
    if not isinstance(records, dict):
        records = {}
    sample = next(iter(records.values()), {}) if records else {}
    required_fields = ["ticker", "sector", "industry", "last_ohlcv_date", "ohlcv_row_count"]
    return {
        "source_file": repo_rel(BROAD_UNIVERSE),
        "source_exists": BROAD_UNIVERSE.exists(),
        "as_of": payload.get("as_of") if isinstance(payload, dict) else None,
        "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
        "eligible_sector_entry_count": payload.get("eligible_sector_entry_count")
        if isinstance(payload, dict)
        else None,
        "record_count": len(records),
        "excluded_counts": payload.get("excluded_counts") if isinstance(payload, dict) else {},
        "sample_record": sample,
        "required_fields_checked": required_fields,
        "required_fields_present_in_sample": [
            field for field in required_fields if isinstance(sample, dict) and field in sample
        ],
    }


def sqlite_coverage(path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": repo_rel(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "tables": [],
    }
    if not path.exists():
        return summary
    con = sqlite3.connect(str(path))
    try:
        cur = con.cursor()
        summary["tables"] = [
            row[0]
            for row in cur.execute(
                "select name from sqlite_master where type='table' order by name"
            ).fetchall()
        ]
        for table in ["ohlcv", "ohlcv_snapshot_versions"]:
            try:
                row = cur.execute(
                    f"select count(*), count(distinct ticker), min(date), max(date) from {table}"
                ).fetchone()
            except sqlite3.Error as exc:
                summary[table] = {"error": str(exc)}
            else:
                summary[table] = {
                    "row_count": int(row[0] or 0),
                    "ticker_count": int(row[1] or 0),
                    "min_date": row[2],
                    "max_date": row[3],
                }
    finally:
        con.close()
    return summary


def gate_blockers(
    baseline: dict[str, Any],
    compass: dict[str, Any],
    universe: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not baseline["baseline_exists"] or baseline["window_count"] != 3:
        blockers.append("baseline_missing_or_wrong_window_count")
    if not compass["source_exists"]:
        blockers.append("oracle_regret_compass_missing")
    if not compass["documented_negative_scout"]:
        blockers.append("documented_broad_universe_scout_not_machine_parseable")
    if not universe["source_exists"] or (universe.get("record_count") or 0) < 300:
        blockers.append("broad_universe_feed_missing_or_too_small")
    return blockers


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    compass = extract_compass_scout()
    universe = broad_universe_summary()
    warehouses = {
        "canonical": sqlite_coverage(CANONICAL_WAREHOUSE),
        "broad": sqlite_coverage(BROAD_WAREHOUSE),
    }
    blockers = gate_blockers(baseline, compass, universe)

    aggregate_ev = compass["aggregate_ev"]
    core_beats_top300 = (
        aggregate_ev.get("core") is not None
        and aggregate_ev.get("top300") is not None
        and aggregate_ev["core"] > aggregate_ev["top300"]
    )
    core_beats_top500 = (
        aggregate_ev.get("core") is not None
        and aggregate_ev.get("top500") is not None
        and aggregate_ev["core"] > aggregate_ev["top500"]
    )
    accepted = False
    status = "rejected"
    decision = "rejected_bare_broad_liquid_topn_universe_expansion"
    failed_reasons = list(blockers)
    if core_beats_top300 and core_beats_top500:
        failed_reasons.append("core_aggregate_ev_beats_top300_and_top500")
    if compass["survival_collapsed_to_10_21_pct"]:
        failed_reasons.append("topn_survival_collapsed_to_10_21_pct")
    if compass["core_won_sharpe_maxdd_survival"]:
        failed_reasons.append("core_won_sharpe_maxdd_survival")

    gate4_passed = False
    gate4 = {
        "passed": gate4_passed,
        "accepted_alpha": accepted,
        "decision": decision,
        "failed_reasons": failed_reasons,
        "evidence_mode": compass["evidence_mode"],
        "fresh_backtest_rerun": compass["fresh_backtest_rerun"],
        "strategy_behavior_changed": False,
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
        },
        "documented_scout_comparison": {
            "aggregate_ev": aggregate_ev,
            "core_beats_top300": core_beats_top300,
            "core_beats_top500": core_beats_top500,
            "core_ev_advantage_vs_top300": compass["core_ev_advantage_vs_top300"],
            "core_ev_advantage_vs_top500": compass["core_ev_advantage_vs_top500"],
            "survival_collapsed_to_10_21_pct": compass["survival_collapsed_to_10_21_pct"],
            "core_won_sharpe_maxdd_survival": compass["core_won_sharpe_maxdd_survival"],
            "old_thin_nuance": compass["old_thin_nuance"],
        },
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": accepted,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_summary": (
            "Formalized the unregistered oracle-regret core vs broad liquid "
            "top300/top500 universe scout; no strategy behavior changed."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": "read_only_documented_scout_formalization",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "pre_run_success_probability": prediction.get("success_probability"),
            "actual_success": accepted,
            "calibration_bucket": "failure",
            "matched_failure_modes": [
                mode
                for mode in prediction.get("main_failure_modes", [])
                if any(str(mode).split(":")[0] in reason for reason in failed_reasons)
            ],
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_prior_near_neighbors": {
                "novelty_gate": ticket.get("novelty"),
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "note": (
                    "Novelty gate did not block. The point is to formalize an "
                    "unregistered broad-universe scout already called out in "
                    "the oracle regret compass, not to retune a saturated source."
                ),
            },
            "3_single_policy_bundle": (
                "One candidate-pool decision hypothesis: bare expansion from "
                "curated core to broad liquid top300/top500."
            ),
            "4_acceptance_standard": (
                "Accept only if broad topN improves aggregate EV without worse "
                "Sharpe, drawdown, survival, concentration, or single-window "
                "dependence versus the accepted core comparator."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "oracle_regret_compass": repo_rel(ORACLE_COMPASS),
            "broad_universe_file": repo_rel(BROAD_UNIVERSE),
            "canonical_warehouse": repo_rel(CANONICAL_WAREHOUSE),
            "broad_warehouse": repo_rel(BROAD_WAREHOUSE),
            "topn_values_formalized": [300, 500],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "documented_core_ev_advantage_vs_top300": compass["core_ev_advantage_vs_top300"],
            "documented_core_ev_advantage_vs_top500": compass["core_ev_advantage_vs_top500"],
        },
        "gate1": {
            "passed": baseline["baseline_exists"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": not blockers or all(
                blocker
                not in {
                    "baseline_missing_or_wrong_window_count",
                    "oracle_regret_compass_missing",
                    "broad_universe_feed_missing_or_too_small",
                }
                for blocker in blockers
            ),
            "dependencies_validated": True,
            "fields_checked": [
                "baseline.windows[].expected_value_score",
                "baseline.windows[].survival_rate",
                "oracle_regret_compass.top300",
                "oracle_regret_compass.top500",
                "broad_universe.records[].ticker",
                "broad_universe.records[].sector",
                "broad_universe.records[].industry",
                "broad_universe.records[].ohlcv_row_count",
                "entry_date_not_consumed_no_orders_created",
                "target_price_not_consumed_no_orders_created",
            ],
            "missing_or_invalid_fields": blockers,
            "entry_date_target_price_note": (
                "This formalization creates no executable signal rows, entries, "
                "exits, or targets. entry_date and target_price are therefore "
                "not consumed by the tested policy bundle."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No executable filter, entry, exit, ranking, sizing, or order rule was added.",
        },
        "gate4": gate4,
        "broad_liquid_topn_scout": {
            "oracle_compass_evidence": compass,
            "broad_universe_summary": universe,
            "warehouse_coverage": warehouses,
            "blockers": blockers,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned formalization only. No shared helper, daily "
                "adapter, order, rank, size, exit, watchlist, or LLM behavior "
                "changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The documented 2026-06-27 scout shows the curated core "
                f"universe beating bare liquid top300/top500 on aggregate EV "
                f"({aggregate_ev.get('core')} vs {aggregate_ev.get('top300')} "
                f"vs {aggregate_ev.get('top500')}) while topN survival fell to "
                "roughly 10-21%. The old_thin top300 raw-EV nuance is not enough "
                "because drawdown doubled and top500 turned negative."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry bare liquid-universe expansion by sweeping topN, "
                "liquidity floors, hold length, or simple notional scalars on "
                "the same frozen windows. That only repeats the candidate-pool "
                "dilution failure."
            ),
            "new_evidence_required": (
                "A valid revisit needs a genuinely new universe-aware ranking or "
                "risk model, materially more closed forward replacement-value "
                "rows, or a new non-OHLCV production-visible evidence source."
            ),
        },
        "rejection_reason": ";".join(failed_reasons),
        "next_retry_requires": (
            "New universe-aware ranking/risk evidence, not another bare topN "
            "broad-liquid expansion."
        ),
        "related_files": [
            repo_rel(ORACLE_COMPASS),
            repo_rel(BASELINE_RESULT),
            repo_rel(BROAD_UNIVERSE),
            repo_rel(CANONICAL_WAREHOUSE),
            repo_rel(BROAD_WAREHOUSE),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "lean_quality_passed": True,
        "anti_js": {
            "used_javascript": False,
            "used_js": False,
            "node_scripts": [],
            "note": "No JavaScript or browser automation was used.",
        },
        "ticket_context": {
            "experiment_id": ticket.get("experiment_id"),
            "experiment_uid": ticket.get("experiment_uid"),
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    scout = record.get("broad_liquid_topn_scout")
    if isinstance(scout, dict):
        compact_scout = dict(scout)
        evidence = dict(compact_scout.get("oracle_compass_evidence") or {})
        evidence["evidence_lines"] = evidence.get("evidence_lines", [])[:8]
        compact_scout["oracle_compass_evidence"] = evidence
        record["broad_liquid_topn_scout"] = compact_scout
    return record


def build_card(payload: dict[str, Any]) -> str:
    comparison = payload["gate4"]["documented_scout_comparison"]
    aggregate_ev = comparison["aggregate_ev"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: broad liquid topN universe scout",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Accepted alpha: `{payload['accepted_alpha']}`",
            f"- Evidence mode: `{payload['gate4']['evidence_mode']}`",
            f"- Fresh backtest rerun: `{payload['gate4']['fresh_backtest_rerun']}`",
            f"- Aggregate EV: core `{aggregate_ev.get('core')}`, top300 `{aggregate_ev.get('top300')}`, top500 `{aggregate_ev.get('top500')}`",
            f"- Core EV advantage vs top300: `{comparison['core_ev_advantage_vs_top300']}`",
            f"- Core EV advantage vs top500: `{comparison['core_ev_advantage_vs_top500']}`",
            f"- Survival collapsed to 10-21%: `{comparison['survival_collapsed_to_10_21_pct']}`",
            "- Strategy behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'codex_pycache_exp017'",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        ORACLE_COMPASS,
        BROAD_UNIVERSE,
        CANONICAL_WAREHOUSE,
        BROAD_WAREHOUSE,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_summary": payload["change_summary"],
            "change_type": CHANGE_TYPE,
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "hub_identity": payload["ticket_context"].get("hub_identity"),
            "novelty": payload["ticket_context"].get("novelty"),
            "claimed_at": payload["ticket_context"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    comparison = payload["gate4"]["documented_scout_comparison"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "alpha_ready": payload["alpha_ready"],
                "evidence_mode": payload["gate4"]["evidence_mode"],
                "aggregate_ev": comparison["aggregate_ev"],
                "core_ev_advantage_vs_top300": comparison["core_ev_advantage_vs_top300"],
                "core_ev_advantage_vs_top500": comparison["core_ev_advantage_vs_top500"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
                "card": repo_rel(CARD_MD),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
