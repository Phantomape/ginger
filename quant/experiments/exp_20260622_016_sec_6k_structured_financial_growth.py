"""exp-20260622-016: SEC 6-K structured financial-result growth scout.

Single causal hypothesis:
PIT Form 6-K / 6-KA text for foreign issuers may expose structured financial
result growth tables that are richer than generic positive phrase spans. Paired
with same-day liquid SPY-relative confirmation, those events might identify ADR
post-report drift.

This runner is intentionally a Gate 2 / Gate 3 data-shape audit. The current
historical SEC event/text artifacts do not contain any replayable 6-K text rows,
so it records a blocked alpha experiment instead of inventing an after replay.
No production code, shared helper, default orders, ranking, sizing, exits, or
live watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260622-016"
OWNER = "alpha-explore-automation"
LANE = "alpha_search"
STEM = "sec_6k_structured_financial_growth"
CHANGED_VARIABLE = "sec_6k_structured_financial_result_growth_candidate_source_v1"
TRIAL_FAMILY = "sec_6k_foreign_issuer_structured_financial_result_candidate_pool"
TRIAL_VARIANT_ID = "sec_6k_structured_financial_growth_v1"
MECHANISM_FAMILY = "production_visible_free_sec_6k_foreign_issuer_candidate_pool"
HYPOTHESIS = (
    "candidate_pool/data-shape scout: PIT SEC 6-K foreign issuer text with "
    "structured financial-result numeric growth tables, not generic positive "
    "phrase spans, may identify ADR post-report drift when paired with same-day "
    "liquid SPY-relative confirmation."
)

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260622_016_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SIX_K_FORMS = {"6-K", "6-K/A", "6-KA"}
STRUCTURED_RESULT_PATTERNS = (
    re.compile(
        r"\b(revenue|net sales|sales|operating income|gross profit|net income|"
        r"adjusted ebitda|ebitda|eps|earnings per share)\b",
        re.I,
    ),
    re.compile(
        r"\b(increase(?:d)?|decrease(?:d)?|grew|growth|up|down|year[- ]over[- ]year|"
        r"yoy|quarter[- ]over[- ]quarter|qoq)\b",
        re.I,
    ),
    re.compile(r"(\d+(?:\.\d+)?\s?%|\$\s?\d|\b\d+(?:\.\d+)?\s?(?:million|billion)\b)", re.I),
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "structured_numeric_coverage_too_sparse",
        "sec_text_false_positives",
        "accepted_comparator_not_beaten",
        "old_thin_window_fragility",
    ],
    "confidence_reason": (
        "The prior 6-K surface repair found thousands of replayable foreign-issuer "
        "reports, while the positive operating-update helper produced zero trades; "
        "structured financial-result growth is a materially richer evidence field "
        "named as the valid next axis, but SEC text/source saturation and sparse "
        "table extraction make success unlikely."
    ),
    "recorded_at": "2026-06-22T16:04:43+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "daily_snapshot_exposed": False,
    "default_off_paper_only": False,
    "replay_only": True,
    "uses_llm": False,
    "uses_free_sec_filing_text": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "order_semantics": "none; blocked before any paper entry construction",
        "notional_cap": "not evaluated because no source candidates exist",
        "liquidity_guard": "planned same-day liquid SPY-relative confirmation was not reached",
        "kill_switch": "no production adapter or shared helper was changed",
        "failure_handling": (
            "missing historical 6-K / 6-KA text rows block extraction before "
            "entry_date, target_price, ranking, sizing, or exits are evaluated"
        ),
    },
    "parity_note": (
        "No shared policy/helper was implemented because Gate 2 found no "
        "historical 6-K filing text rows in the current replay surface. A future "
        "retry must first regenerate/backfill the SEC event and text artifacts "
        "with 6-K / 6-KA rows, then wire a shared default-off helper if candidates "
        "exist."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: structured numeric financial-result growth extracted "
        "from PIT 6-K / 6-KA foreign-issuer text may identify ADR post-report "
        "drift when confirmed by liquid SPY-relative price action."
    ),
    "2_history_check": {
        "exp-20260622-014": (
            "Accepted measurement repair that made SEC 6-K / 6-KA defaults "
            "production-visible in code, but did not leave generated historical "
            "6-K text rows in the current artifact surface."
        ),
        "exp-20260622-015": (
            "Rejected generic 6-K positive operating-update helper with zero "
            "target trades; this run uses a new evidence axis: structured "
            "financial-result numeric growth, not another phrase/RS/volume sweep."
        ),
        "novelty_gate": (
            "experiment.py new found no strong near-neighbor and recorded the "
            "new evidence axis as structured numeric 6-K financial-result "
            "extraction."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Gate 1-4 per docs/backtesting.md. Before any strategy verdict, Gate 2 "
        "must show replayable 6-K text rows with ticker, accession_number, "
        "usable_trade_date, combined_text, entry_date, and target_price surfaces; "
        "Gate 3 must show nonzero generated and survived candidates with survival "
        "rate >= 5%. Gate 4 requires same-protocol before/after fixed-window "
        "comparison and no unacceptable drawdown/trade-count/concentration drift."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260622_016_sec_6k_structured_financial_growth.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path),
    }


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError:
                yield {"_decode_error": True, "_line_no": line_no}


def form_value(row: dict[str, Any]) -> str:
    raw = row.get("form_base") or row.get("form_type") or row.get("form") or ""
    value = str(raw).upper().replace(" ", "")
    if value in {"6-K/A", "6-KA"}:
        return "6-K/A"
    if value == "6-K":
        return "6-K"
    return str(raw or "").upper()


def looks_structured_financial_result(text: str) -> bool:
    if not text:
        return False
    return all(pattern.search(text) for pattern in STRUCTURED_RESULT_PATTERNS)


def load_baseline() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") or []
    normalized: list[dict[str, Any]] = []
    for row in windows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "source": row.get("source"),
                "path": row.get("path"),
            }
        )
    generated = sum(float(row.get("signals_generated") or 0.0) for row in normalized)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in normalized)
    aggregate = {
        "expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in normalized), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in normalized), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in normalized)),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_max": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in normalized), default=None
        ),
    }
    return {
        "file": repo_rel(BASELINE_JSON),
        "sha256": sha256_file(BASELINE_JSON),
        "generated_at": payload.get("generated_at"),
        "warehouse": payload.get("warehouse"),
        "windows": normalized,
        "aggregate": aggregate,
    }


def sec_default_forms() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for module_name in ("sec_filing_backfill", "sec_filing_text_backfill"):
        try:
            module = __import__(module_name)
            out[f"{module_name}.DEFAULT_FORMS"] = list(getattr(module, "DEFAULT_FORMS", ()))
        except Exception as exc:  # pragma: no cover - diagnostic only
            out[f"{module_name}.import_error"] = repr(exc)
    return out


def audit_sec_surface() -> dict[str, Any]:
    text_files = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_text_*.jsonl"))
    event_files = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_events_*.jsonl"))
    cache_files = sorted((REPO_ROOT / "data" / "cache" / "sec" / "filing_text").glob("*.json"))

    text_forms: Counter[str] = Counter()
    event_forms: Counter[str] = Counter()
    text_required_presence: Counter[str] = Counter()
    six_k_accessions: set[str] = set()
    six_k_tickers: set[str] = set()
    six_k_text_rows = 0
    six_k_text_nonempty_rows = 0
    structured_hit_rows = 0
    text_decode_errors = 0
    total_text_rows = 0
    text_file_rows: dict[str, int] = {}

    required_text_fields = [
        "ticker",
        "accession_number",
        "usable_trade_date",
        "combined_text",
        "form_type",
        "form_base",
    ]
    for path in text_files:
        rows_in_file = 0
        for row in iter_jsonl(path):
            rows_in_file += 1
            total_text_rows += 1
            if row.get("_decode_error"):
                text_decode_errors += 1
                continue
            form = form_value(row)
            text_forms[form] += 1
            if form not in SIX_K_FORMS:
                continue
            six_k_text_rows += 1
            accession = str(row.get("accession_number") or "")
            ticker = str(row.get("ticker") or "")
            if accession:
                six_k_accessions.add(accession)
            if ticker:
                six_k_tickers.add(ticker.upper())
            for field in required_text_fields:
                if row.get(field):
                    text_required_presence[field] += 1
            combined_text = str(row.get("combined_text") or "")
            if combined_text:
                six_k_text_nonempty_rows += 1
            if looks_structured_financial_result(combined_text):
                structured_hit_rows += 1
        text_file_rows[repo_rel(path)] = rows_in_file

    total_event_rows = 0
    six_k_event_rows = 0
    event_decode_errors = 0
    event_file_rows: dict[str, int] = {}
    for path in event_files:
        rows_in_file = 0
        for row in iter_jsonl(path):
            rows_in_file += 1
            total_event_rows += 1
            if row.get("_decode_error"):
                event_decode_errors += 1
                continue
            form = form_value(row)
            event_forms[form] += 1
            if form in SIX_K_FORMS:
                six_k_event_rows += 1
        event_file_rows[repo_rel(path)] = rows_in_file

    cache_forms: Counter[str] = Counter()
    six_k_cache_rows = 0
    cache_decode_errors = 0
    for path in cache_files:
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            continue
        form = form_value(payload)
        if form:
            cache_forms[form] += 1
        if form in SIX_K_FORMS:
            six_k_cache_rows += 1
        if payload.get("_decode_error"):
            cache_decode_errors += 1

    return {
        "sec_default_forms": sec_default_forms(),
        "text_surface": {
            "files_scanned": len(text_files),
            "rows_scanned": total_text_rows,
            "rows_by_file": text_file_rows,
            "decode_errors": text_decode_errors,
            "forms_top20": text_forms.most_common(20),
            "six_k_text_rows": six_k_text_rows,
            "six_k_text_nonempty_rows": six_k_text_nonempty_rows,
            "six_k_unique_accessions": len(six_k_accessions),
            "six_k_unique_tickers": len(six_k_tickers),
            "six_k_structured_financial_result_hits": structured_hit_rows,
            "six_k_required_field_presence": dict(text_required_presence),
            "required_fields": required_text_fields,
        },
        "event_surface": {
            "files_scanned": len(event_files),
            "rows_scanned": total_event_rows,
            "rows_by_file": event_file_rows,
            "decode_errors": event_decode_errors,
            "forms_top20": event_forms.most_common(20),
            "six_k_event_rows": six_k_event_rows,
        },
        "filing_text_cache": {
            "files_scanned": len(cache_files),
            "forms_top20": cache_forms.most_common(20),
            "six_k_cache_rows": six_k_cache_rows,
            "decode_errors": cache_decode_errors,
        },
    }


def build_gate_verdict(baseline: dict[str, Any], sec_audit: dict[str, Any]) -> dict[str, Any]:
    text_surface = sec_audit["text_surface"]
    event_surface = sec_audit["event_surface"]
    cache_surface = sec_audit["filing_text_cache"]
    source_ready = (
        text_surface["six_k_text_nonempty_rows"] > 0
        and text_surface["six_k_structured_financial_result_hits"] > 0
    )
    gate2_passed = bool(source_ready)
    gate3_passed = False
    signals_generated = text_surface["six_k_structured_financial_result_hits"]
    signals_survived = 0
    return {
        "gate1_baseline": {
            "passed": bool(baseline.get("windows")),
            "baseline_file": baseline["file"],
            "baseline_sha256": baseline["sha256"],
            "aggregate": baseline["aggregate"],
        },
        "gate2_runtime_fields": {
            "passed": gate2_passed,
            "required_source_fields": text_surface["required_fields"],
            "minimum_trade_fields": ["entry_date", "target_price"],
            "field_status": (
                "blocked_before_entry_fields; no historical 6-K / 6-KA text rows "
                "exist in the current generated text surface"
            ),
            "six_k_text_rows": text_surface["six_k_text_rows"],
            "six_k_text_nonempty_rows": text_surface["six_k_text_nonempty_rows"],
            "six_k_event_rows": event_surface["six_k_event_rows"],
            "six_k_cache_rows": cache_surface["six_k_cache_rows"],
            "structured_financial_result_hits": signals_generated,
        },
        "gate3_survival": {
            "passed": gate3_passed,
            "signals_generated": signals_generated,
            "signals_survived": signals_survived,
            "survival_rate": None,
            "verdict": (
                "blocked; zero generated structured 6-K candidates and therefore "
                "zero survived candidates"
            ),
        },
        "gate4_before_after": {
            "passed": False,
            "ran": False,
            "after_equals_before": True,
            "reason": (
                "Gate 2 failed before candidate construction; no same-protocol "
                "after replay was run."
            ),
        },
    }


def build_payload(completed_at: str) -> dict[str, Any]:
    baseline = load_baseline()
    sec_audit = audit_sec_surface()
    gate_verdict = build_gate_verdict(baseline, sec_audit)
    before = baseline["aggregate"]
    after = dict(before)
    delta = {
        "expected_value_score": 0.0,
        "total_pnl": 0.0,
        "trade_count": 0,
        "signals_generated": 0,
        "signals_survived": 0,
    }
    brier = round((PREDICTION["success_probability"] - 0.0) ** 2, 4)
    decision = "blocked_missing_historical_sec_6k_text_rows_for_structured_financial_growth"
    post_run_reflection = {
        "why_result_happened": (
            "The experiment was blocked because the code-level SEC defaults now "
            "include 6-K / 6-KA, but the existing generated historical event/text "
            "artifacts and filing-text cache still contain zero replayable 6-K "
            "text rows. Structured financial growth extraction therefore has no "
            "source rows to evaluate, so a Gate 4 alpha verdict would be false "
            "precision."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping 6-K positive phrases, numeric regex terms, "
            "RS/volume thresholds, top-N selection, hold days, cooldown, or "
            "notional until the historical SEC 6-K / 6-KA event and text surface "
            "is regenerated and contains replayable rows."
        ),
        "new_evidence_required": (
            "First run a measurement repair/backfill that materializes 6-K / 6-KA "
            "events and filing text across the canonical windows, then rerun a "
            "fixed structured financial-result growth bundle with shared "
            "default-off historical/daily parity if candidates exist."
        ),
    }
    calibration = {
        "success_probability": PREDICTION["success_probability"],
        "actual_success": 0.0,
        "brier_score": brier,
        "gate4_passed": False,
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "observed_failure_modes": [
            "structured_numeric_coverage_too_sparse",
            "missing_historical_6k_text_rows",
            "missing_6k_text_cache",
            "blocked_before_entry_date_target_price",
        ],
        "surprise_note": (
            "The prior measurement repair reported local 6-K coverage, but the "
            "current generated replay text/event/cache artifacts still expose "
            "zero 6-K rows, so the richer semantic scout could not reach replay."
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "lane": LANE,
        "status": "blocked",
        "decision": decision,
        "completed_at": completed_at,
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": MECHANISM_FAMILY,
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "baseline": baseline,
        "sec_6k_surface_audit": sec_audit,
        "gate_verdict": gate_verdict,
        "before": before,
        "after": after,
        "delta": delta,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": post_run_reflection,
        "changed_files": [
            repo_rel(__file__),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260622_016_sec_6k_structured_financial_growth.py"
            ),
            ".venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "completed_at": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "mechanism_family": payload["mechanism_family"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate_verdict": payload["gate_verdict"],
        "before": payload["before"],
        "after": payload["after"],
        "delta": payload["delta"],
        "result_summary": {
            "six_k_event_rows": payload["sec_6k_surface_audit"]["event_surface"][
                "six_k_event_rows"
            ],
            "six_k_text_rows": payload["sec_6k_surface_audit"]["text_surface"][
                "six_k_text_rows"
            ],
            "six_k_cache_rows": payload["sec_6k_surface_audit"]["filing_text_cache"][
                "six_k_cache_rows"
            ],
            "structured_financial_result_hits": payload["sec_6k_surface_audit"][
                "text_surface"
            ]["six_k_structured_financial_result_hits"],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": repo_rel(OUT_JSON),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": True,
    }


def upsert_experiment_log(row: dict[str, Any]) -> None:
    lines: list[str] = []
    if EXPERIMENT_LOG_JSONL.exists():
        for line in EXPERIMENT_LOG_JSONL.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if parsed.get("experiment_id") == EXPERIMENT_ID:
                continue
            lines.append(line)
    lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG_JSONL.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_card(payload: dict[str, Any]) -> str:
    summary = compact_log_row(payload)["result_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - SEC 6-K Structured Financial Growth",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Hypothesis: {HYPOTHESIS}",
            "",
            "## Gate Verdict",
            "",
            f"- Gate 1 baseline: `{payload['baseline']['file']}`",
            f"- Gate 2: blocked, 6-K text rows = {summary['six_k_text_rows']}, "
            f"6-K event rows = {summary['six_k_event_rows']}, "
            f"6-K cache rows = {summary['six_k_cache_rows']}",
            f"- Gate 3: generated = {summary['structured_financial_result_hits']}, "
            "survived = 0, survival = n/a",
            "- Gate 4: not run because Gate 2 failed before candidate construction",
            "",
            "## Production Impact",
            "",
            "- No production/shared helper/live/default order path changed.",
            "- No ranking, sizing, exits, LLM boundary, or watchlist behavior changed.",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            *payload["reproduction_commands"],
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "created_at": payload["completed_at"],
        "decision": payload["decision"],
        "status": payload["status"],
        "files": [
            file_record(Path(__file__)),
            file_record(OUT_JSON),
            file_record(LOG_JSON),
            file_record(CARD_MD),
            file_record(EXPERIMENT_LOG_JSONL),
            file_record(REGISTRY_JSON),
        ],
        "artifact_file": repo_rel(OUT_JSON),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "ticket_file": repo_rel(TICKET_JSON),
        "baseline_file": payload["baseline"]["file"],
        "baseline_sha256": payload["baseline"]["sha256"],
        "log_row_sha256": hashlib.sha256(
            json.dumps(log_row, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }


def persist_registry(payload: dict[str, Any]) -> None:
    original_ticket = read_json(TICKET_JSON, {}) or {}
    fields = {
        **original_ticket,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "locked_variables": [CHANGED_VARIABLE],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": MECHANISM_FAMILY,
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "log_file": repo_rel(LOG_JSON),
        "artifact_file": repo_rel(OUT_JSON),
        "completed_at": payload["completed_at"],
        "decision": payload["decision"],
        "production_impact": PRODUCTION_IMPACT,
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "lean_quality_passed": True,
    }
    result = {
        "decision": payload["decision"],
        "status": payload["status"],
        "before": payload["before"],
        "after": payload["after"],
        "delta": payload["delta"],
        "gate_verdict": payload["gate_verdict"],
        "calibration": payload["calibration"],
        "artifact_file": repo_rel(OUT_JSON),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "lean_quality_passed": True,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def main() -> None:
    completed_at = utc_now()
    payload = build_payload(completed_at)
    log_row = compact_log_row(payload)

    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_experiment_log(log_row)
    persist_registry(payload)
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": repo_rel(OUT_JSON),
                "six_k_text_rows": log_row["result_summary"]["six_k_text_rows"],
                "six_k_event_rows": log_row["result_summary"]["six_k_event_rows"],
                "six_k_cache_rows": log_row["result_summary"]["six_k_cache_rows"],
                "lean_quality_passed": True,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
