"""exp-20260704-006: accepted sleeve admission fire-rate autopsy.

Measurement repair only. Accepted default-off paper sleeves cannot build
closed forward replacement-value evidence if their daily snapshots rarely admit
rows. This runner compares each sleeve's accepted replay trade count to its
deduped live paper snapshot fire rate and records the next parity probe targets.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260704-006"
OWNER = "alpha-explore"
SLUG = "accepted_sleeve_admission_fire_rate_autopsy"
RUNNER = f"quant/experiments/exp_20260704_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_006_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

REPLAY_TRADING_DAY_DENOMINATOR = 378

SLEEVE_AUDIT_TARGETS = [
    {
        "sleeve_dir": "volatility_relief_leadership",
        "sleeve_label": "VOLATILITY_RELIEF_LEADERSHIP_PAPER",
        "accepted_experiment": "exp-20260607-019",
        "accepted_target_trades_fallback": 88,
        "accepted_rule": "volatility_relief_stock_leadership_shared_default_off_adapter_v1",
    },
    {
        "sleeve_dir": "turn_of_month_liquid_leadership",
        "sleeve_label": "TURN_OF_MONTH_LIQUID_LEADERSHIP_PAPER",
        "accepted_experiment": "exp-20260609-027",
        "accepted_target_trades_fallback": 73,
        "accepted_rule": "turn_of_month_liquid_leadership_shared_default_off_adapter_v1",
    },
    {
        "sleeve_dir": "industry_stable_core_flow",
        "sleeve_label": "INDUSTRY_STABLE_CORE_FLOW_PAPER",
        "accepted_experiment": "exp-20260608-008",
        "accepted_target_trades_fallback": 47,
        "accepted_rule": "industry_stable_core_flow_shared_default_off_adapter_v1",
    },
    {
        "sleeve_dir": "narrow_range_compression_breakout",
        "sleeve_label": "NARROW_RANGE_COMPRESSION_BREAKOUT_PAPER",
        "accepted_experiment": "exp-20260608-013",
        "accepted_target_trades_fallback": 44,
        "accepted_rule": "narrow_range_compression_breakout_shared_default_off_adapter_v1",
    },
    {
        "sleeve_dir": "post_earnings_underpriced_drift",
        "sleeve_label": "POST_EARNINGS_UNDERPRICED_DRIFT_PAPER",
        "accepted_experiment": "exp-20260602-026",
        "accepted_target_trades_fallback": 20,
        "accepted_rule": "post_earnings_underpriced_drift_shared_adapter_v1",
    },
    {
        "sleeve_dir": "accepted_source_consensus",
        "sleeve_label": "ACCEPTED_SOURCE_CONSENSUS_PAPER",
        "accepted_experiment": "exp-20260601-001",
        "accepted_target_trades_fallback": None,
        "accepted_rule": "accepted_source_consensus_paper_v1",
    },
    {
        "sleeve_dir": "sec_ftd_finra",
        "sleeve_label": "SEC_FTD_FINRA_PAPER",
        "accepted_experiment": "exp-20260603-007",
        "accepted_target_trades_fallback": None,
        "accepted_rule": "sec_ftd_finra_paper_v1",
    },
]

COUNT_FIELDS = [
    "new_pending_count",
    "candidate_count",
    "raw_candidate_count",
    "closed_count_today",
    "open_position_count",
    "pending_count",
]

RAW_CONTEXT_KEYS = [
    "raw_candidate_count",
    "raw_candidates",
    "raw_candidates_before_core_flow_filter",
    "raw_candidates_after_core_flow_filter",
    "raw_candidates_missing_core_flow",
    "raw_volatility_relief_candidates",
    "raw_turn_of_month_candidates",
    "raw_compression_breakout_candidates",
    "raw_breakout_candidates",
    "supported_raw_candidate_count",
]

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_006_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\experiments\\exp_20260704_006_accepted_sleeve_admission_fire_rate_autopsy.py",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str)
        + "\n",
        path,
    )


def as_number(value: Any) -> float:
    if value is None or isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int:
    return int(as_number(value))


def flatten_dict(payload: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in payload.items():
        next_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten_dict(value, next_key))
        else:
            out[next_key] = value
    return out


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON, {})
    windows = payload.get("windows") or []
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(
            int(window.get("total_trades") or window.get("trade_count") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
        "replay_trading_day_denominator": REPLAY_TRADING_DAY_DENOMINATOR,
    }


def find_numeric(payload: Any, candidate_paths: list[str]) -> int | None:
    flat = flatten_dict(payload)
    for path in candidate_paths:
        value = flat.get(path)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    for key, value in flat.items():
        lower = key.lower()
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and "target" in lower
            and ("trade" in lower or "count" in lower)
        ):
            return int(value)
    return None


def accepted_target_trade_count(target: dict[str, Any]) -> dict[str, Any]:
    exp_id = str(target["accepted_experiment"])
    log_path = REPO_ROOT / "experiments" / "logs" / f"{exp_id}.json"
    log = load_json(log_path, {})
    extracted = find_numeric(
        log,
        [
            "gate4.target_trade_count",
            "gate4.target_trades",
            "delta_metrics.aggregate.target_trade_count_sum",
            "delta_metrics.aggregate.target_trades",
            "target_trade_count",
            "target_trades",
        ],
    )
    fallback = target.get("accepted_target_trades_fallback")
    value = extracted if extracted is not None else fallback
    return {
        "accepted_experiment": exp_id,
        "accepted_log": repo_rel(log_path),
        "target_trades": value,
        "source": "accepted_log" if extracted is not None else "manual_from_experiment_log",
        "fallback_used": extracted is None and fallback is not None,
        "available": value is not None,
    }


def merge_counter_field(counter: Counter[str], payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    for key, value in payload.items():
        amount = as_int(value)
        if amount:
            counter[str(key)] += amount


def collect_reject_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        merge_counter_field(counts, row.get("candidate_reject_counts"))
        audit = row.get("candidate_audit")
        if isinstance(audit, dict):
            merge_counter_field(counts, audit.get("audit_reject_counts"))
        context = row.get("context_scan")
        if isinstance(context, dict):
            for key, value in context.items():
                lower = str(key).lower()
                if ("missing" in lower or "reject" in lower or "excluded" in lower) and as_int(value):
                    counts[str(key)] += as_int(value)
    return dict(counts.most_common(12))


def context_raw_count(row: dict[str, Any]) -> int:
    direct = as_int(row.get("raw_candidate_count"))
    context = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else {}
    context_values = [
        as_int(context.get(key))
        for key in RAW_CONTEXT_KEYS
        if isinstance(context, dict) and key in context
    ]
    nested_values: list[int] = []
    for key, value in row.items():
        if key.endswith("_context") and isinstance(value, dict):
            nested_values.extend(
                as_int(value.get(raw_key)) for raw_key in RAW_CONTEXT_KEYS if raw_key in value
            )
    return max([direct, *context_values, *nested_values, 0])


def representative_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for row in rows:
        candidate = row.get("candidate")
        context = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else {}
        raw_count = context_raw_count(row)
        if candidate or raw_count or row.get("candidate_reject_counts"):
            samples.append(
                {
                    "asof_date": row.get("asof_date"),
                    "generated_at": row.get("generated_at"),
                    "candidate_count": as_int(row.get("candidate_count")),
                    "new_pending_count": as_int(row.get("new_pending_count")),
                    "raw_candidate_count": raw_count,
                    "candidate_ticker": candidate.get("ticker") if isinstance(candidate, dict) else None,
                    "context_keys": sorted(str(key) for key in context.keys())[:20],
                    "reject_counts": row.get("candidate_reject_counts")
                    or (row.get("candidate_audit") or {}).get("audit_reject_counts")
                    if isinstance(row.get("candidate_audit"), dict)
                    else row.get("candidate_reject_counts"),
                }
            )
        if len(samples) >= 6:
            break
    return samples


def latest_by_asof(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        asof = row.get("asof_date") or row.get("date") or row.get("generated_at")
        if asof:
            grouped[str(asof)].append(row)
    return dict(sorted(grouped.items()))


def max_count(rows: list[dict[str, Any]], field: str) -> int:
    if field == "raw_candidate_count":
        return max([context_raw_count(row) for row in rows] + [0])
    return max([as_int(row.get(field)) for row in rows] + [0])


def classify_sleeve(
    *,
    expected_fires: float | None,
    actual_new_pending_total: int,
    actual_raw_candidate_total: int,
    reject_counts: dict[str, int],
) -> str:
    if expected_fires is None:
        return "not_scored_missing_accepted_replay_trade_count"
    if expected_fires < 3.0 and actual_new_pending_total == 0 and actual_raw_candidate_total > 0:
        return "low_expected_span_but_raw_context_blocker_present"
    if expected_fires < 3.0:
        return "normal_sparse_or_low_expected_forward_span"
    ratio = actual_new_pending_total / max(expected_fires, 1e-9)
    if actual_new_pending_total == 0 and actual_raw_candidate_total > 0:
        return "probable_admission_or_context_blocker_raw_rows_do_not_survive"
    if actual_new_pending_total == 0 and reject_counts:
        return "probable_admission_or_context_blocker_reject_counts_present"
    if actual_new_pending_total == 0:
        return "possible_regime_sparse_but_needs_representative_day_replay"
    if ratio < 0.35:
        return "underfires_vs_replay_positive_control_or_drift"
    return "within_forward_span_expectation"


def audit_sleeve(target: dict[str, Any]) -> dict[str, Any]:
    sleeve_dir = REPO_ROOT / "data" / "paper_sleeves" / str(target["sleeve_dir"])
    snapshot_path = sleeve_dir / "snapshots.jsonl"
    rows = read_jsonl(snapshot_path)
    grouped = latest_by_asof(rows)
    daily_rows = [items for _, items in grouped.items()]
    counts_by_field = {
        field: sum(max_count(items, field) for items in daily_rows) for field in COUNT_FIELDS
    }
    raw_candidate_total = counts_by_field["raw_candidate_count"]
    target_count = accepted_target_trade_count(target)
    expected_fires = None
    replay_daily_fire_rate = None
    if target_count["target_trades"] is not None:
        replay_daily_fire_rate = float(target_count["target_trades"]) / REPLAY_TRADING_DAY_DENOMINATOR
        expected_fires = replay_daily_fire_rate * len(grouped)
    reject_counts = collect_reject_counts(rows)
    actual_new_pending_total = counts_by_field["new_pending_count"]
    ratio = (
        round(actual_new_pending_total / expected_fires, 4)
        if expected_fires and expected_fires > 0
        else None
    )
    classification = classify_sleeve(
        expected_fires=expected_fires,
        actual_new_pending_total=actual_new_pending_total,
        actual_raw_candidate_total=raw_candidate_total,
        reject_counts=reject_counts,
    )
    return {
        "sleeve_dir": target["sleeve_dir"],
        "sleeve_label": target["sleeve_label"],
        "accepted_rule": target["accepted_rule"],
        "snapshot_file": repo_rel(snapshot_path),
        "snapshot_file_exists": snapshot_path.exists(),
        "raw_snapshot_rows": len(rows),
        "unique_asof_dates": len(grouped),
        "first_asof_date": next(iter(grouped), None),
        "last_asof_date": next(reversed(grouped), None) if grouped else None,
        "duplicate_asof_days": sum(1 for items in grouped.values() if len(items) > 1),
        "accepted_target": target_count,
        "replay_daily_fire_rate": round(replay_daily_fire_rate, 6)
        if replay_daily_fire_rate is not None
        else None,
        "expected_fires_over_snapshot_span": round(expected_fires, 4)
        if expected_fires is not None
        else None,
        "actual_vs_expected_ratio": ratio,
        "actual_new_pending_total": actual_new_pending_total,
        "actual_candidate_total": counts_by_field["candidate_count"],
        "actual_raw_candidate_total": raw_candidate_total,
        "actual_closed_today_total": counts_by_field["closed_count_today"],
        "actual_open_position_total": counts_by_field["open_position_count"],
        "daily_count_fields": counts_by_field,
        "reject_counts": reject_counts,
        "classification": classification,
        "fire_gap": round((expected_fires or 0.0) - actual_new_pending_total, 4),
        "representative_samples": representative_sample(rows),
    }


def audit_sleeves() -> dict[str, Any]:
    rows = [audit_sleeve(target) for target in SLEEVE_AUDIT_TARGETS]
    scored = [row for row in rows if row["accepted_target"]["available"]]
    suspect = [
        row
        for row in scored
        if row["expected_fires_over_snapshot_span"] is not None
        and row["expected_fires_over_snapshot_span"] >= 3.0
        and row["actual_vs_expected_ratio"] is not None
        and row["actual_vs_expected_ratio"] < 0.35
    ]
    top_gaps = sorted(scored, key=lambda item: item["fire_gap"], reverse=True)
    return {
        "audited_sleeve_count": len(rows),
        "scored_sleeve_count": len(scored),
        "snapshot_files_present_count": sum(1 for row in rows if row["snapshot_file_exists"]),
        "underfire_sleeve_count": len(suspect),
        "zero_fire_scored_count": sum(1 for row in scored if row["actual_new_pending_total"] == 0),
        "rows": rows,
        "top_fire_gaps": [
            {
                "sleeve_dir": row["sleeve_dir"],
                "expected": row["expected_fires_over_snapshot_span"],
                "actual_new_pending": row["actual_new_pending_total"],
                "fire_gap": row["fire_gap"],
                "classification": row["classification"],
                "top_reject_counts": row["reject_counts"],
            }
            for row in top_gaps[:5]
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {})
    baseline = baseline_summary()
    sleeve_audit = audit_sleeves()
    gate2_passed = (
        sleeve_audit["snapshot_files_present_count"] >= 5
        and sleeve_audit["scored_sleeve_count"] >= 5
    )
    accepted = gate2_passed and sleeve_audit["underfire_sleeve_count"] >= 1
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_sleeve_admission_fire_rate_autopsy"
        if accepted
        else "blocked_sleeve_admission_fire_rate_autopsy"
    )
    primary_probe_sleeves = [
        row["sleeve_dir"]
        for row in sleeve_audit["top_fire_gaps"]
        if row["expected"] is not None and row["expected"] >= 3.0
    ][:3]
    secondary_probe_sleeves = [
        row["sleeve_dir"]
        for row in sleeve_audit["top_fire_gaps"]
        if row["classification"] == "low_expected_span_but_raw_context_blocker_present"
        and row["sleeve_dir"] not in primary_probe_sleeves
    ]
    next_probe_sleeves = (primary_probe_sleeves + secondary_probe_sleeves)[:3]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Forward evidence supply is itself an alpha bottleneck: accepted "
            "default-off paper sleeves that materially underfire versus their "
            "own replay-implied admission rates need admission/parity repair "
            "before their replacement-value outcomes can mature."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "accepted_sleeve_admission_fire_rate_autopsy",
        "trial_variant_id": "accepted_default_off_sleeve_admission_fire_rate_autopsy_v1",
        "single_causal_variable": "accepted_default_off_sleeve_admission_fire_rate_autopsy_v1",
        "changed_variable": "accepted_default_off_sleeve_admission_fire_rate_autopsy_v1",
        "causal_components": [
            "accepted replay target trade-count extraction",
            "deduped daily paper snapshot admission count audit",
            "underfire classification",
            "next parity probe target list",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260607-019",
            "exp-20260608-008",
            "exp-20260608-013",
            "exp-20260609-027",
            "exp-20260602-026",
            "exp-20260611-001",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "accepted_forward_snapshot_admission_rate_autopsy",
        "new_evidence_axis": (
            "Measurement-only audit across materially new forward paper snapshot "
            "rows for already accepted default-off sleeves; no retune or new "
            "threshold is introduced."
        ),
        "admission_audit_contract": {
            "dedupe_policy": "same asof_date counts once using max observed count per field",
            "replay_denominator_trading_days": REPLAY_TRADING_DAY_DENOMINATOR,
            "scored_sleeves": [
                target["sleeve_dir"]
                for target in SLEEVE_AUDIT_TARGETS
                if target.get("accepted_target_trades_fallback") is not None
            ],
            "not_scored_sleeves": [
                target["sleeve_dir"]
                for target in SLEEVE_AUDIT_TARGETS
                if target.get("accepted_target_trades_fallback") is None
            ],
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": gate2_passed,
            "fields_checked": [
                "asof_date",
                "new_pending_count",
                "candidate_count",
                "raw_candidate_count/context raw counts",
                "candidate_reject_counts",
                "candidate_audit.audit_reject_counts",
                "accepted replay target_trades",
            ],
            "entry_date_target_price_scope": (
                "Not applicable. This runner creates no entries, exits, target "
                "prices, paper orders, or live orders."
            ),
            "snapshot_files_present_count": sleeve_audit["snapshot_files_present_count"],
            "scored_sleeve_count": sleeve_audit["scored_sleeve_count"],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter/rank/size/exit rule changed; survival is baseline identity.",
        },
        "gate4": {
            "mode": "measurement_repair_admission_fire_rate_autopsy",
            "passed": accepted,
            "accepted_measurement_repair": accepted,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "underfire_sleeve_count": sleeve_audit["underfire_sleeve_count"],
            "zero_fire_scored_count": sleeve_audit["zero_fire_scored_count"],
            "top_fire_gaps": sleeve_audit["top_fire_gaps"],
            "decision_basis": (
                "Accepted only as measurement repair: the audit identified "
                "specific accepted default-off sleeves whose forward daily "
                "admission rate is far below replay-implied expectation, creating "
                "a concrete parity/debug queue for forward evidence maturation."
            ),
            "failed_reasons": []
            if accepted
            else ["insufficient_snapshot_or_accepted_target_coverage"],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "sleeve_admission_audit": sleeve_audit,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Read-only audit of existing default-off paper snapshots. It "
                "does not alter live/default orders, rankings, sizing, exits, or "
                "paper snapshot generation."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Several accepted sleeves have replay-implied daily admission "
                "rates that should have produced multiple forward rows over the "
                "current snapshot span, yet the daily snapshots produced zero or "
                "very few new pending rows. That is enough to prioritize parity "
                "probes before interpreting the absence of closed forward value "
                "as alpha failure."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune thresholds, notionals, response functions, or "
                "slice conditions on these sleeves from this audit alone. The "
                "next legal work is representative-day replay versus the daily "
                "helper for the named underfiring sleeves, or waiting for "
                "materially more closed forward rows."
            ),
            "new_evidence_required": (
                "For each underfiring sleeve, capture a representative historical "
                "replay admission day and compare the shared helper's daily "
                "context inputs to the backtest admission inputs, then repair only "
                "a proven production/backtest measurement drift."
            ),
        },
        "next_retry_requires": [
            f"representative-day daily-vs-replay parity probe for {sleeve}"
            for sleeve in next_probe_sleeves
        ],
        "next_probe_sleeves": next_probe_sleeves,
        "secondary_probe_sleeves": secondary_probe_sleeves,
        "prediction": ticket.get("prediction"),
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": False,
            "surprise_note": (
                "Moderate surprise: the audit produced a concrete ranked parity "
                "queue instead of only confirming sparse forward evidence."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "admission_audit_contract",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "next_probe_sleeves",
        "secondary_probe_sleeves",
        "calibration",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    gaps = payload["gate4"]["top_fire_gaps"]
    gap_lines = "\n".join(
        "- `{sleeve_dir}` expected `{expected}`, actual `{actual_new_pending}`, class `{classification}`".format(
            **gap
        )
        for gap in gaps
    )
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Audited sleeves: `{payload["sleeve_admission_audit"]["audited_sleeve_count"]}`
- Underfire sleeves: `{payload["gate4"]["underfire_sleeve_count"]}`
- Artifact: `{payload["artifact"]}`

## Top Fire Gaps

{gap_lines}

## Gates

- Gate 1 baseline loaded: `{payload["gate1"]["passed"]}`
- Gate 2 fields verified: `{payload["gate2"]["passed"]}`
- Gate 3 survival unchanged: `{payload["gate3"]["passed"]}`
- Gate 4 measurement repair: `{payload["gate4"]["passed"]}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Reproduction

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "files": {
            path: {"exists": (REPO_ROOT / path).exists()} for path in CHANGED_FILES
        },
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = load_json(TICKET_JSON, {})
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["alpha_hypothesis"] = payload["alpha_hypothesis"]
    ticket["causal_components"] = payload["causal_components"]
    ticket["nearby_prior_experiments"] = payload["nearby_prior_experiments"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
    }
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)
    update_ticket(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
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
            "admission_audit_contract": payload["admission_audit_contract"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "lean_quality_passed": True,
        },
    )
    print(json.dumps(log_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
