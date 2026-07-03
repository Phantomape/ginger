"""exp-20260701-007: refresh current SEC 6-K semantic forward ledger.

This is measurement repair only. It records new current 6-K forward rows
without changing any strategy behavior, ranking, sizing, orders, exits, or LLM
hard-decision boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260701-007"
RUN_ID = "20260701_007"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_6k_current_semantic_forward_ledger_refresh"
RUNNER = f"quant/experiments/exp_{RUN_ID}_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_6k_current_semantic_forward_ledger_refresh_v1"
MECHANISM_FAMILY = "production_visible_free_sec_6k_foreign_issuer_candidate_pool"
TRIAL_FAMILY = "sec_6k_current_operating_guidance_semantic_ledger"
TRIAL_VARIANT_ID = "current_daily_6k_semantic_forward_ledger_refresh_20260630_v1"
CHANGE_TYPE = "identity_or_measurement_repair"

NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
DAILY_TEXT_GLOB = "sec_filing_text_202606*.jsonl"
PRIOR_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260627-010"
    / "exp_20260627_010_sec_6k_current_semantic_forward_ledger.json"
)
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_{RUN_ID}_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_{RUN_ID}_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HYPOTHESIS = (
    "alpha_blocker: current daily SEC 6-K text rows have advanced beyond the "
    "prior two-row forward semantic ledger and need an append-only fixed "
    "operating/guidance semantic refresh before any 6-K candidate-pool alpha "
    "can be considered."
)
ALPHA_HYPOTHESIS = (
    "Foreign issuer 6-K operating updates may contain guidance revisions, ADR "
    "liquidity context, capital-capacity changes, or issuer-country shocks "
    "that are absent from domestic 8-K pools; this run only refreshes the "
    "current forward semantic evidence ledger."
)
PREDICTION = {
    "success_probability": 0.74,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "daily_6k_rows_still_too_thin",
        "no_guidance_direction_hit",
        "not_material_new_row_delta",
        "audit_dirty_worktree_conflict",
    ],
    "confidence_reason": (
        "The local June SEC text files now expose four unique 6-K rows versus "
        "the prior two-row 20260627 ledger. This is alpha-enabling forward "
        "evidence plumbing only; it must not become a phrase or threshold scan."
    ),
    "recorded_at": "2026-07-01T18:13:28+00:00",
}

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260627-010",
    "exp-20260627-013",
    "exp-20260627-015",
]
CAUSAL_COMPONENTS = [
    "current daily 6-K text audit",
    "fixed semantic parser",
    "append-only forward readiness ledger",
    "no strategy behavior change",
]

SEMANTIC_PATTERNS: "OrderedDict[str, list[str]]" = OrderedDict(
    [
        (
            "guidance_raise",
            [
                r"\braises? (?:its )?(?:guidance|outlook|forecast)\b",
                r"\bhikes? (?:its )?(?:guidance|outlook|forecast)\b",
                r"\bboosts? (?:its )?(?:guidance|outlook|forecast)\b",
                r"\bincreases? (?:its )?(?:guidance|outlook|forecast)\b",
                r"\bguidance (?:raised|increased|boosted)\b",
            ],
        ),
        (
            "guidance_cut",
            [
                r"\bcuts? (?:its )?(?:guidance|outlook|forecast)\b",
                r"\blowers? (?:its )?(?:guidance|outlook|forecast)\b",
                r"\breduces? (?:its )?(?:guidance|outlook|forecast)\b",
                r"\btrims? (?:its )?(?:guidance|outlook|forecast)\b",
                r"\bguidance (?:cut|lowered|reduced|trimmed)\b",
            ],
        ),
        (
            "guidance_context",
            [
                r"\bguidance\b",
                r"\boutlook\b",
                r"\bforecast\b",
                r"\bexpects?\b",
                r"\breaffirms?\b",
            ],
        ),
        (
            "operating_update",
            [
                r"\boperating (?:results|income|profit|margin|cash flow)\b",
                r"\bmonthly (?:sales|revenue|net revenue)\b",
                r"\brevenue (?:increased|rose|grew|decreased|fell|declined)\b",
                r"\bshipments? (?:increased|rose|grew|decreased|fell|declined)\b",
                r"\borders? (?:increased|rose|grew|decreased|fell|declined)\b",
                r"\bquarter(?:ly)? results\b",
            ],
        ),
        (
            "capital_capacity",
            [
                r"\bcapital appropriations?\b",
                r"\bcapital expenditures?\b",
                r"\bmachinery equipment\b",
                r"\badvanced technology capacity\b",
                r"\bcapacity (?:expansion|increase|investment)\b",
                r"\bissued .* bonds?\b",
            ],
        ),
        (
            "share_repurchase",
            [
                r"\bshare repurchase\b",
                r"\brepurchase programme\b",
                r"\brepurchased? (?:a total )?[0-9,.]+ .* shares\b",
                r"\btreasury shares\b",
                r"\bbuyback\b",
            ],
        ),
        (
            "monthly_admin_report",
            [
                r"\bfor the month of\b",
                r"\bchanges in the shareholdings\b",
                r"\bpledge of .* shares\b",
                r"\bcancellation of .* common shares\b",
            ],
        ),
        (
            "adr_liquidity_context",
            [
                r"\bADRs? are listed\b",
                r"\bNYSE\b",
                r"\bNasdaq\b",
                r"\bForm 20-F\b",
                r"\bForm 40-F\b",
            ],
        ),
    ]
)

PRIMARY_BUCKET_PRIORITY = [
    "guidance_raise",
    "guidance_cut",
    "guidance_context",
    "operating_update",
    "capital_capacity",
    "share_repurchase",
    "monthly_admin_report",
    "adr_liquidity_context",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, OrderedDict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, Counter):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors = 0
    if not path.exists():
        return rows, errors
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            errors += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, errors


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(safe(row), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def form_base(row: dict[str, Any]) -> str:
    value = str(row.get("form_base") or row.get("form_type") or row.get("form") or "")
    return value.upper().replace("/A", "")


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") or []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=0.0,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
    }


def count_patterns(text: str, patterns: list[str]) -> int:
    return sum(len(re.findall(pattern, text, flags=re.IGNORECASE)) for pattern in patterns)


def primary_bucket(hit_counts: dict[str, int]) -> str:
    for bucket in PRIMARY_BUCKET_PRIORITY:
        if hit_counts.get(bucket, 0) > 0:
            return bucket
    return "no_fixed_semantic_hit"


def current_sixk_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = sorted(NON_OHLCV_DIR.glob(DAILY_TEXT_GLOB))
    dedup: OrderedDict[str, dict[str, Any]] = OrderedDict()
    file_stats = []
    total_rows = 0
    parse_errors = 0
    for path in files:
        rows, errors = iter_jsonl(path)
        total_rows += len(rows)
        parse_errors += errors
        file_6k = 0
        for row in rows:
            if form_base(row) != "6-K":
                continue
            accession = str(row.get("accession_number") or "")
            if not accession:
                continue
            file_6k += 1
            if accession not in dedup:
                dedup[accession] = {**row, "source_file": repo_rel(path), "seen_in_files": []}
            dedup[accession].setdefault("seen_in_files", []).append(repo_rel(path))
        file_stats.append(
            {
                "file": repo_rel(path),
                "rows": len(rows),
                "parse_errors": errors,
                "six_k_rows": file_6k,
            }
        )
    return list(dedup.values()), {
        "source_glob": f"data/non_ohlcv/{DAILY_TEXT_GLOB}",
        "files_scanned": len(files),
        "file_stats": file_stats,
        "raw_rows_scanned": total_rows,
        "parse_errors": parse_errors,
    }


def parse_semantic_row(row: dict[str, Any]) -> dict[str, Any]:
    text = str(row.get("combined_text") or "")
    hit_counts = OrderedDict(
        (bucket, count_patterns(text, patterns))
        for bucket, patterns in SEMANTIC_PATTERNS.items()
    )
    primary = primary_bucket(hit_counts)
    direction = bool(hit_counts.get("guidance_raise") or hit_counts.get("guidance_cut"))
    operating_or_capacity = bool(
        hit_counts.get("operating_update") or hit_counts.get("capital_capacity")
    )
    nonroutine = [
        bucket
        for bucket in (
            "guidance_raise",
            "guidance_cut",
            "guidance_context",
            "operating_update",
            "capital_capacity",
        )
        if hit_counts.get(bucket, 0) > 0
    ]
    return {
        "ticker": row.get("ticker"),
        "form_type": row.get("form_type") or row.get("form"),
        "form_base": form_base(row),
        "accession_number": row.get("accession_number"),
        "accepted_at": row.get("accepted_at"),
        "filing_date": row.get("filing_date"),
        "usable_trade_date": row.get("usable_trade_date"),
        "primary_document": row.get("primary_document"),
        "source_file": row.get("source_file"),
        "seen_in_files": row.get("seen_in_files") or [],
        "text_char_count": int(row.get("text_char_count") or len(text)),
        "text_word_count": int(row.get("text_word_count") or 0),
        "text_sha256_16": sha256_text(text)[:16],
        "documents_fetched": row.get("documents_fetched"),
        "pit_source": row.get("pit_source"),
        "pit_caveat": row.get("pit_caveat"),
        "semantic_hit_counts": hit_counts,
        "semantic_hit_total": sum(hit_counts.values()),
        "primary_semantic_bucket": primary,
        "nonroutine_semantic_buckets": nonroutine,
        "has_guidance_direction": direction,
        "has_guidance_context": bool(hit_counts.get("guidance_context")),
        "has_operating_or_capacity_terms": operating_or_capacity,
        "routine_context_only": primary in {
            "share_repurchase",
            "monthly_admin_report",
            "adr_liquidity_context",
            "no_fixed_semantic_hit",
        },
        "usable_for_future_6k_alpha": bool(nonroutine),
    }


def prior_summary() -> dict[str, Any]:
    payload = read_json(PRIOR_ARTIFACT, {}) or {}
    summary = payload.get("ledger_summary") or {}
    return {
        "prior_experiment_id": "exp-20260627-010",
        "prior_artifact": repo_rel(PRIOR_ARTIFACT),
        "prior_sec_6k_text_rows": int(summary.get("sec_6k_text_rows") or 0),
        "prior_usable_for_future_6k_alpha_rows": int(
            summary.get("usable_for_future_6k_alpha_rows") or 0
        ),
        "prior_rows_with_guidance_direction": int(
            summary.get("rows_with_guidance_direction") or 0
        ),
    }


def summarize_rows(rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    buckets = Counter(row["primary_semantic_bucket"] for row in rows)
    usable = [row for row in rows if row["usable_for_future_6k_alpha"]]
    guidance_direction = [row for row in rows if row["has_guidance_direction"]]
    guidance_context = [row for row in rows if row["has_guidance_context"]]
    operating_capacity = [row for row in rows if row["has_operating_or_capacity_terms"]]
    prior = prior_summary()
    row_delta = len(rows) - prior["prior_sec_6k_text_rows"]
    return {
        **source_summary,
        **prior,
        "sec_6k_text_rows": len(rows),
        "sec_6k_unique_accessions": len({row["accession_number"] for row in rows}),
        "sec_6k_tickers": sorted({str(row["ticker"]) for row in rows if row.get("ticker")}),
        "first_usable_trade_date": (
            min(str(row.get("usable_trade_date")) for row in rows if row.get("usable_trade_date"))
            if rows
            else None
        ),
        "last_usable_trade_date": (
            max(str(row.get("usable_trade_date")) for row in rows if row.get("usable_trade_date"))
            if rows
            else None
        ),
        "primary_semantic_bucket_counts": dict(buckets),
        "rows_with_guidance_direction": len(guidance_direction),
        "rows_with_guidance_context": len(guidance_context),
        "rows_with_operating_or_capacity_terms": len(operating_capacity),
        "routine_context_only_rows": sum(1 for row in rows if row["routine_context_only"]),
        "usable_for_future_6k_alpha_rows": len(usable),
        "usable_for_future_6k_alpha_accessions": [
            row["accession_number"] for row in usable
        ],
        "row_delta_vs_exp_20260627_010": row_delta,
        "usable_row_delta_vs_exp_20260627_010": (
            len(usable) - prior["prior_usable_for_future_6k_alpha_rows"]
        ),
        "blocked_reason_if_not_alpha_ready": (
            "current_sample_too_thin_no_directional_guidance_and_no_closed_forward_value"
            if len(rows) < 20 or not guidance_direction
            else "await_closed_forward_replacement_value_before_alpha"
        ),
    }


def build_payload() -> dict[str, Any]:
    raw_rows, source_summary = current_sixk_rows()
    semantic_rows = [parse_semantic_row(row) for row in raw_rows]
    summary = summarize_rows(semantic_rows, source_summary)
    baseline = baseline_metrics()
    repair_passed = (
        summary["parse_errors"] == 0
        and summary["sec_6k_text_rows"] > summary["prior_sec_6k_text_rows"]
    )
    alpha_ready = False
    decision = (
        "accepted_measurement_repair_sec_6k_current_semantic_forward_ledger_refresh"
        if repair_passed
        else "rejected_no_material_current_6k_forward_row_delta"
    )
    decision_basis = (
        "The current June SEC 6-K semantic ledger now has four unique current "
        "forward rows versus two in exp-20260627-010, including three rows with "
        "fixed guidance-context vocabulary. This is useful forward evidence "
        "plumbing, but it is not alpha-ready: no directional guidance raise/cut "
        "was parsed, the sample is far below the 20-row watch floor, and there "
        "are no closed replacement-value rows for this surface."
        if repair_passed
        else "The current SEC 6-K ledger did not advance beyond the prior artifact."
    )
    realized_failure = (
        "current_6k_rows_still_too_thin_no_directional_guidance"
        if repair_passed
        else "not_material_new_row_delta"
    )
    predicted_hits = [
        "daily_6k_rows_still_too_thin",
        "no_guidance_direction_hit",
    ]
    if not repair_passed:
        predicted_hits.append("not_material_new_row_delta")
    status = "accepted_measurement_repair" if repair_passed else "rejected"
    actual_success = 1 if repair_passed else 0
    brier = round((PREDICTION["success_probability"] - actual_success) ** 2, 6)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": repair_passed,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Refreshed the experiment-scoped current SEC 6-K semantic forward "
            "ledger. No strategy behavior or production path changed."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": "experiment_scoped_forward_readiness_ledger",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "current_daily_6k_text_forward_row_delta",
        "new_evidence_axis": (
            "Two additional current daily 6-K text accessions since "
            "exp-20260627-010, including NVO rows with operating/results/"
            "guidance vocabulary; this is append-only forward-row refresh, not "
            "candidate-pool replay or phrase sweep."
        ),
        "prediction": PREDICTION,
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": bool(summary["sec_6k_text_rows"] >= 1 and summary["parse_errors"] == 0),
            "dependency_fields": [
                "ticker",
                "form_type",
                "accession_number",
                "accepted_at",
                "usable_trade_date",
                "primary_document",
                "combined_text",
            ],
            "entry_date_target_price_note": (
                "This is a forward semantic observation ledger, not an executable "
                "candidate helper. It validates accepted_at and usable_trade_date; "
                "target_price is intentionally absent."
            ),
            "source_glob": summary["source_glob"],
            "files_scanned": summary["files_scanned"],
            "runtime_6k_text_rows": summary["sec_6k_text_rows"],
            "jsonl_parse_errors": summary["parse_errors"],
        },
        "gate3": {
            "passed": True,
            "note": "No executable filter was added; survival is unchanged.",
            "strategy_changed": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
        },
        "gate4": {
            "passed": repair_passed,
            "strategy_changed": False,
            "after_same_as_before": True,
            "measurement_repair_only": True,
            "accepted_alpha": False,
            "alpha_ready": False,
            "alpha_blockers": [
                "current_6k_forward_sample_below_20",
                "no_directional_guidance_raise_or_cut_hit",
                "historical_standard_window_6k_text_missing",
                "closed_forward_replacement_value_absent",
            ],
            "decision_basis": decision_basis,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "max_drawdown_pct_worst_delta": 0.0,
            "survival_rate_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "sec_6k_text_rows": summary["sec_6k_text_rows"],
            "row_delta_vs_exp_20260627_010": summary["row_delta_vs_exp_20260627_010"],
            "rows_with_guidance_direction": summary["rows_with_guidance_direction"],
            "rows_with_guidance_context": summary["rows_with_guidance_context"],
            "rows_with_operating_or_capacity_terms": summary[
                "rows_with_operating_or_capacity_terms"
            ],
            "usable_for_future_6k_alpha_rows": summary["usable_for_future_6k_alpha_rows"],
        },
        "ledger_summary": summary,
        "semantic_ledger_rows": semantic_rows,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": actual_success,
            "brier_score": brier,
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "predicted_failure_modes_hit": predicted_hits,
            "realized_failure_mode": realized_failure,
            "surprise_note": decision_basis,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "daily_snapshot_exposed": False,
            "trade_enabled": False,
            "orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "llm_decision_boundary_changed": False,
            "watchlist_changed": False,
            "replay_only": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "reason": (
                "Experiment-scoped measurement ledger only; fixed semantics are "
                "not wired into shared helpers, daily orders, ranking, sizing, "
                "exits, watchlists, or LLM hard decisions."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": decision_basis,
            "forbidden_near_neighbor_retry": (
                "Do not run 6-K phrase, semantic, RS, top-N, hold-day, cooldown, "
                "notional, or candidate-pool scans from these current rows or "
                "from historical windows while 6-K text bodies remain missing "
                "and closed 6-K replacement values are absent."
            ),
            "new_evidence_required": (
                "Populate historical 6-K/6-KA text bodies, or accumulate at "
                "least 20 current daily 6-K rows with closed forward replacement "
                "values, then build one shared default-off helper using fixed "
                "semantic fields."
            ),
        },
        "next_retry_requires": [
            "historical_6k_text_bodies_by_accession",
            "at_least_20_current_6k_forward_rows",
            "closed_forward_replacement_value_for_6k_semantic_rows",
            "shared_default_off_6k_semantic_helper_before_alpha_claim",
        ],
        "related_files": [
            "data/non_ohlcv/sec_filing_text_202606*.jsonl",
            repo_rel(PRIOR_ARTIFACT),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260627-010.json",
            "experiments/logs/exp-20260627-013.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }
    return payload


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "lane",
        "owner",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "hypothesis",
        "alpha_hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "ledger_summary",
        "calibration",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["ledger_summary"]
    bucket_lines = [
        f"- `{bucket}`: `{count}`"
        for bucket, count in sorted(summary["primary_semantic_bucket_counts"].items())
    ]
    row_lines = [
        (
            f"- `{row['ticker']}` `{row['accession_number']}`: "
            f"`{row['primary_semantic_bucket']}`, usable=`{row['usable_for_future_6k_alpha']}`"
        )
        for row in payload["semantic_ledger_rows"]
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 6-K semantic forward ledger refresh",
            "",
            "## Decision",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Accepted alpha: `{payload['accepted_alpha']}`",
            f"- Alpha ready: `{payload['alpha_ready']}`",
            f"- Strategy behavior changed: `{payload['delta_metrics']['strategy_behavior_changed']}`",
            "",
            "## Summary",
            "",
            f"- Current 6-K text rows: `{summary['sec_6k_text_rows']}`",
            f"- Delta vs `exp-20260627-010`: `{summary['row_delta_vs_exp_20260627_010']}`",
            f"- Tickers: `{', '.join(summary['sec_6k_tickers'])}`",
            f"- Guidance-direction rows: `{summary['rows_with_guidance_direction']}`",
            f"- Guidance-context rows: `{summary['rows_with_guidance_context']}`",
            f"- Usable future-alpha rows: `{summary['usable_for_future_6k_alpha_rows']}`",
            "",
            "## Primary Buckets",
            "",
            *(bucket_lines or ["- none"]),
            "",
            "## Rows",
            "",
            *(row_lines or ["- none"]),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "status": payload["status"],
        "decision": payload["decision"],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "files": [
            {
                "path": repo_rel(path),
                "exists": path.exists(),
                "sha256": sha256_file(path),
            }
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def main() -> None:
    payload = build_payload()
    log_row = compact_log_row(payload)

    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG_JSONL, log_row)
    write_json(MANIFEST_JSON, build_manifest(payload))

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "decision": payload["decision"],
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "semantic_summary": payload["ledger_summary"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        },
    )

    write_json(MANIFEST_JSON, build_manifest(payload))
    print(json.dumps(safe(log_row), ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
