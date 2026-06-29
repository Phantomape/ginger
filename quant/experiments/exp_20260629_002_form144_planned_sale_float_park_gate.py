"""exp-20260629-002: park the Form144 planned-sale/float surface.

This runner records the current machine-checkable blocker for the Form144
planned-sale/float alpha-enabling surface. It intentionally changes no entry,
exit, ranking, sizing, risk, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260629-002"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "form144_planned_sale_float_park_gate"
RUNNER = f"quant/experiments/exp_20260629_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "form144_planned_sale_float_surface_park_gate_v1"
TRIAL_FAMILY = "form144_planned_sale_float_reopen_gate"
TRIAL_VARIANT_ID = "post_materializer_park_gate_v1"
MECHANISM_FAMILY = "production_visible_form144_planned_sale_forward_context"
CHANGE_TYPE = "identity_or_measurement_repair"
STATUS = "accepted_measurement_repair"
DECISION = "accepted_measurement_repair_form144_planned_sale_float_surface_parked"

BASELINE_RESULT = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
CONTEXT_SUMMARY_JSON = REPO_ROOT / "data" / "non_ohlcv" / "form144_planned_sale_context_summary_20260628.json"
CONTEXT_JSONL = REPO_ROOT / "data" / "non_ohlcv" / "form144_planned_sale_context_20260628.jsonl"
MATERIALIZER_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260628-020"
    / "exp_20260628_020_form144_primary_document_cache_materializer.json"
)
PRIMARY_DOC_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "form144_documents"
FORWARD_REPLACEMENT_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260629_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALPHA_HYPOTHESIS = (
    "Risk allocation: parsed Form144 planned-sale/float could identify known "
    "future supply overhang and support a default-off allocation downweight, "
    "but only after primary documents, parseable ratios, and closed forward "
    "replacement-value rows exist."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_jsonl_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def baseline_metrics() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT, {})
    if not isinstance(raw, dict):
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": False}
    windows: list[dict[str, Any]] = []
    for row in raw.get("windows") or []:
        if not isinstance(row, dict):
            continue
        windows.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "sharpe_daily": row.get("sharpe_daily"),
                "total_pnl": row.get("total_pnl"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "win_rate": row.get("win_rate"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
        )
    if not windows:
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": True}
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "loaded": True,
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 6
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": (
            round(signals_survived / signals_generated, 6) if signals_generated else None
        ),
        "max_drawdown_pct": max(float(row.get("max_drawdown_pct") or 0.0) for row in windows),
        "windows": windows,
    }


def count_primary_cache_files() -> dict[str, Any]:
    if not PRIMARY_DOC_CACHE_DIR.exists():
        return {
            "cache_dir": repo_rel(PRIMARY_DOC_CACHE_DIR),
            "exists": False,
            "file_count": 0,
            "sample_files": [],
        }
    files = [path for path in PRIMARY_DOC_CACHE_DIR.rglob("*") if path.is_file()]
    return {
        "cache_dir": repo_rel(PRIMARY_DOC_CACHE_DIR),
        "exists": True,
        "file_count": len(files),
        "sample_files": [repo_rel(path) for path in sorted(files)[:5]],
    }


def row_mentions_form144(row: dict[str, Any]) -> bool:
    for key, value in row.items():
        key_text = str(key).lower()
        if "form144" in key_text or "planned_sale" in key_text:
            return True
        if isinstance(value, str):
            value_text = value.lower()
            if "form144" in value_text or "planned_sale" in value_text:
                return True
    return False


def scan_forward_replacement_rows() -> dict[str, Any]:
    total_rows = 0
    form144_rows = 0
    closed_rows = 0
    high_bucket_rows = 0
    ticker_counts: Counter[str] = Counter()
    sample: list[dict[str, Any]] = []
    if not FORWARD_REPLACEMENT_JSONL.exists():
        return {
            "path": repo_rel(FORWARD_REPLACEMENT_JSONL),
            "exists": False,
            "total_rows": 0,
            "form144_tagged_rows": 0,
            "closed_forward_rows_with_cash_spy_qqq_replacement_value": 0,
            "high_planned_sale_float_bucket_rows": 0,
            "single_ticker_closed_row_share": None,
            "ticker_counts": {},
            "sample_form144_rows": [],
        }
    with FORWARD_REPLACEMENT_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            total_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or not row_mentions_form144(row):
                continue
            form144_rows += 1
            has_cash = row.get("replacement_value_vs_cash_usd") is not None
            has_spy = row.get("replacement_value_vs_spy_usd") is not None
            has_qqq = row.get("replacement_value_vs_qqq_usd") is not None
            status = str(row.get("status") or row.get("replacement_value_status") or "").lower()
            is_closed = status in {"enriched", "closed"} or bool(row.get("closed_forward_row"))
            if is_closed and has_cash and has_spy and has_qqq:
                closed_rows += 1
                ticker = str(row.get("ticker") or "")
                if ticker:
                    ticker_counts[ticker] += 1
            bucket = str(row.get("form144_planned_sale_bucket") or "").lower()
            if "high" in bucket:
                high_bucket_rows += 1
            if len(sample) < 5:
                sample.append(
                    {
                        "ticker": row.get("ticker"),
                        "entry_date": row.get("entry_date"),
                        "status": row.get("status") or row.get("replacement_value_status"),
                        "form144_planned_sale_bucket": row.get("form144_planned_sale_bucket"),
                    }
                )
    single_ticker_share = None
    if closed_rows and ticker_counts:
        single_ticker_share = round(max(ticker_counts.values()) / closed_rows, 6)
    return {
        "path": repo_rel(FORWARD_REPLACEMENT_JSONL),
        "exists": True,
        "total_rows": total_rows,
        "form144_tagged_rows": form144_rows,
        "closed_forward_rows_with_cash_spy_qqq_replacement_value": closed_rows,
        "high_planned_sale_float_bucket_rows": high_bucket_rows,
        "single_ticker_closed_row_share": single_ticker_share,
        "ticker_counts": dict(ticker_counts.most_common(10)),
        "sample_form144_rows": sample,
    }


def build_reopen_condition(
    context_summary: dict[str, Any],
    cache_counts: dict[str, Any],
    forward_counts: dict[str, Any],
) -> dict[str, Any]:
    machine_parseable_rows = int(context_summary.get("rows_with_machine_parseable_ratio") or 0)
    current_counts = {
        "context_rows": int(context_summary.get("rows_written") or 0),
        "context_jsonl_rows": count_jsonl_rows(CONTEXT_JSONL),
        "cached_primary_documents": int(
            context_summary.get("rows_with_cached_primary_document") or cache_counts.get("file_count") or 0
        ),
        "primary_document_cache_files": int(cache_counts.get("file_count") or 0),
        "parseable_planned_sale_to_float_rows": int(
            context_summary.get("rows_with_parseable_planned_sale_to_float") or 0
        ),
        "parseable_planned_sale_to_adv20_rows": int(
            context_summary.get("rows_with_parseable_planned_sale_to_adv20") or 0
        ),
        "machine_parseable_ratio_rows": machine_parseable_rows,
        "closed_forward_rows_with_cash_spy_qqq_replacement_value": int(
            forward_counts.get("closed_forward_rows_with_cash_spy_qqq_replacement_value") or 0
        ),
        "high_planned_sale_float_bucket_rows": int(
            forward_counts.get("high_planned_sale_float_bucket_rows") or 0
        ),
        "single_ticker_closed_row_share": forward_counts.get("single_ticker_closed_row_share"),
    }
    return {
        "surface": "Form144 planned-sale/float",
        "status": "parked",
        "blocking_reason": "primary_document_cache_and_forward_rows_not_materialized",
        "current_counts": current_counts,
        "required_to_reopen": {
            "cached_primary_documents_min": 1,
            "machine_parseable_ratio_rows_min": 1,
            "closed_forward_rows_min": 25,
            "high_planned_sale_float_bucket_rows_min": 8,
            "single_ticker_closed_row_share_max": 0.4,
            "required_replacement_values": ["cash", "SPY", "QQQ"],
        },
        "reopen_rule": (
            "Do not reserve another Form144 planned-sale/float readiness, "
            "risk-scalar, notional haircut, ranking, or candidate-pool experiment "
            "until cached/parseable primary documents and closed forward rows "
            "advance to the required counts."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    context_summary = read_json(CONTEXT_SUMMARY_JSON, {})
    materializer = read_json(MATERIALIZER_JSON, {})
    before = baseline_metrics()
    cache_counts = count_primary_cache_files()
    forward_counts = scan_forward_replacement_rows()
    reopen_condition = build_reopen_condition(context_summary, cache_counts, forward_counts)
    current = reopen_condition["current_counts"]
    park_passed = bool(
        before.get("loaded")
        and context_summary.get("rows_written") == 9594
        and current["cached_primary_documents"] == 0
        and current["machine_parseable_ratio_rows"] == 0
        and current["closed_forward_rows_with_cash_spy_qqq_replacement_value"] == 0
    )
    after = dict(before)
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": STATUS if park_passed else "rejected",
        "decision": DECISION if park_passed else "rejected_form144_planned_sale_float_surface_park_gate",
        "accepted": park_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": park_passed,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket.get("hypothesis") or ALPHA_HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "read_only_surface_park_gate",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "read-only Form144 context summary count audit",
            "primary document cache count",
            "parseable planned-sale ratio count",
            "closed forward replacement-value row count",
            "machine-checkable reopen condition",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260628-014",
            "exp-20260628-016",
            "exp-20260628-020",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_park_gate_after_blocked_materialization",
        "prediction": ticket.get("prediction") or {},
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "form144_context_summary": context_summary,
        "form144_materializer_summary": {
            "artifact": repo_rel(MATERIALIZER_JSON),
            "status": materializer.get("status"),
            "decision": materializer.get("decision"),
            "network_blocked": bool((materializer.get("gate4") or {}).get("network_blocked")),
            "cache_materialization_summary": materializer.get("cache_materialization_summary"),
        },
        "primary_document_cache_counts": cache_counts,
        "forward_replacement_scan": forward_counts,
        "reopen_condition": reopen_condition,
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": bool(context_summary.get("rows_written") and "entry_context_schema" in context_summary),
            "runtime_fields_checked": [
                "entry_date",
                "target_price",
                "form144_context_rows",
                "form144_latest_usable_trade_date",
                "form144_accession_number",
                "form144_planned_sale_bucket",
                "form144_planned_sale_to_float",
                "form144_planned_sale_to_adv20",
                "closed_forward_row",
            ],
            "field_status": {
                "entry_date": "required_by_outcome_join_schema",
                "target_price": "strategy_unchanged_not_consumed_by_this_repair",
                "planned_sale_ratio_fields": "not_materialized_zero_parseable_rows",
            },
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": "No signal, filter, ranking, sizing, exit, or order rule changed.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": park_passed,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": DECISION if park_passed else "rejected_form144_planned_sale_float_surface_park_gate",
            "before_after_strategy_delta": delta,
            "park_verdict": reopen_condition,
            "failed_reasons": [] if park_passed else ["park_gate_contract_not_met"],
        },
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "uses_future_form144_rows": False,
            "new_download_attempts": False,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only park gate. The existing Form144 context logger remains "
                "default-off; no trading policy consumes this surface."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260628-014 found Form4 selling-overhang attribution as "
                "observed-only; exp-20260628-016 created the Form144 context "
                "logger with 9,594 index rows but zero parseable planned-sale "
                "ratios; exp-20260628-020 added the materializer but network "
                "blocked the first batch and left the cache empty."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if strategy deltas stay zero "
                "and the current cached/parseable/closed-row counts plus reopen "
                "condition are recorded."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The PIT Form144 index/context ledger exists, but primary "
                "documents are not cached in this workspace, planned-sale ratio "
                "fields are not parseable, and no Form144-tagged closed forward "
                "replacement-value rows exist. That makes an allocation or "
                "risk response experiment untrustworthy today."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry Form144 by changing notional haircut, risk scalar, "
                "ranking, candidate-pool, or readiness-audit wording while cached "
                "primary documents, parseable ratios, and closed forward rows are "
                "still at the current counts."
            ),
            "new_evidence_required": (
                "At least one cached Form144 primary document parsed into "
                "planned_sale_to_float or planned_sale_to_adv20, then at least "
                "25 closed forward rows with cash/SPY/QQQ replacement value, at "
                "least 8 high planned-sale/float rows, and max single-ticker "
                "share <=40%."
            ),
        },
        "next_retry_requires": (
            "Reopen only after the current counts in reopen_condition advance: "
            "cached primary documents >0, machine-parseable ratio rows >0, and "
            "the forward gate starts moving toward >=25 closed rows."
        ),
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(CONTEXT_SUMMARY_JSON),
            repo_rel(CONTEXT_JSONL),
            repo_rel(MATERIALIZER_JSON),
            repo_rel(FORWARD_REPLACEMENT_JSONL),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
        "owner",
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
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "reopen_condition",
        "production_impact",
        "pre_run_questions",
        "prediction",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    row["lean_quality_passed"] = bool(payload["gate4"]["passed"])
    return row


def build_card(payload: dict[str, Any]) -> str:
    current = payload["reopen_condition"]["current_counts"]
    required = payload["reopen_condition"]["required_to_reopen"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Form144 Planned-Sale/Float Park Gate",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Context rows: `{current['context_rows']}`",
            f"- Cached primary documents: `{current['cached_primary_documents']}`",
            f"- Machine-parseable ratio rows: `{current['machine_parseable_ratio_rows']}`",
            f"- Closed Form144 forward rows: `{current['closed_forward_rows_with_cash_spy_qqq_replacement_value']}`",
            "",
            "## Reopen Condition",
            "",
            (
                "Reopen only after cached primary documents and parseable "
                "planned-sale ratios exist, then the closed forward row count "
                f"moves toward `{required['closed_forward_rows_min']}` with "
                "cash/SPY/QQQ replacement values."
            ),
            "",
            "## Interpretation",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        CONTEXT_SUMMARY_JSON,
        MATERIALIZER_JSON,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "reopen_condition": payload["reopen_condition"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
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
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "reopen_condition",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
        ]
        if key in payload
    }
    fields.update(
        {
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload.get("prediction") or {},
        result=result,
        status=payload["status"],
        fields=fields,
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
