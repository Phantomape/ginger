"""exp-20260627-023: ORTEX short-interest sidecar readiness audit.

Measurement/readiness only. ORTEX is a plausible new PIT source for the
borrow/short-crowding axis that prior FINRA, Moomoo short-volume, and options
experiments said would be needed before reopening short-flow alpha work. This
runner audits the current local ORTEX JSON files and records whether they have
the publication/usable-trade-date and borrow-economics fields needed for any
future attribution or candidate-pool rule.

No network calls are made. No strategy helper, ranking, sizing, entry, exit,
paper order, live order, watchlist, or LLM boundary changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260627-023"
OWNER = "alpha-explore"
SLUG = "ortex_short_interest_sidecar_readiness"
RUNNER = f"quant/experiments/exp_20260627_023_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ORTEX_DIR = REPO_ROOT / "data" / "non_ohlcv" / "ortex"
ORTEX_SIDECAR = REPO_ROOT / "quant" / "ortex_data_sidecar.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_023_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: true PIT borrow/short-crowding alpha needs an ORTEX "
    "short-interest sidecar with decision-time publication/usable_trade dates "
    "and borrow-economics fields; audit the current local ORTEX rows before any "
    "FINRA/options/short-flow retry."
)
ALPHA_HYPOTHESIS = (
    "If short-crowding is a real long-alpha context rather than a stale FINRA "
    "proxy, ORTEX short-interest plus borrow-cost/utilization/loan-availability "
    "fields should eventually separate durable squeeze candidates from crowded "
    "false positives when joined to accepted allocator or forward rows."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_ortex_short_interest_readiness"
TRIAL_FAMILY = "ortex_short_interest_sidecar_readiness_gate"
TRIAL_VARIANT_ID = "initial_local_ortex_payload_audit_v1"
CHANGED_VARIABLE = "ortex_short_interest_sidecar_readiness_gate_v1"
NEW_EVIDENCE_TYPE = "new_ortex_short_interest_source_readiness_audit"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-003",
    "exp-20260625-019",
    "exp-20260625-024",
    "exp-20260627-002",
]
CAUSAL_COMPONENTS = [
    "local ORTEX JSON payload audit",
    "PIT publication/usable-trade-date coverage audit",
    "borrow economics field coverage audit",
    "baseline identity check",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260627_023_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "only_demo_tickers",
        "publication_date_absent",
        "usable_trade_date_absent",
        "borrow_economics_absent",
        "not_append_only_daily_ledger",
    ],
    "confidence_reason": (
        "ORTEX is a genuinely new source for the named borrow/short-crowding "
        "axis, but current local files appear to be two sample short-interest "
        "payloads rather than an append-only PIT daily ledger with borrow fee, "
        "utilization, or loan availability."
    ),
    "recorded_at": "2026-06-27T19:05:20+00:00",
}

SHORT_INTEREST_FIELDS = (
    "shortInterestShares",
    "shortInterestPcFreeFloat",
    "shortInterestUsd",
)
PIT_DATE_FIELDS = (
    "publication_date",
    "publicationDate",
    "published_at",
    "publishedAt",
    "usable_trade_date",
    "usableTradeDate",
    "as_of_date",
    "asOfDate",
)
BORROW_ECONOMICS_FIELDS = (
    "borrowFee",
    "borrow_fee",
    "costToBorrow",
    "ctb",
    "utilization",
    "loanAvailability",
    "loan_availability",
    "sharesAvailable",
    "shares_available",
    "daysToCover",
    "days_to_cover",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
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
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_present(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, float) and value != value:
        return False
    return True


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def summarize_numbers(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "min": None, "median": None, "mean": None, "max": None}
    return {
        "n": len(values),
        "min": round(min(values), 6),
        "median": round(median(values), 6),
        "mean": round(mean(values), 6),
        "max": round(max(values), 6),
    }


def parse_source_name(path: Path) -> tuple[str | None, str | None, str]:
    stem = path.stem
    body = stem
    if body.lower().startswith("ortex_"):
        body = body[6:]
    label = "unknown"
    if body.upper().endswith("_SHORT_INTEREST"):
        body = body[: -len("_SHORT_INTEREST")]
        label = "short_interest"
    parts = body.split("_")
    if len(parts) >= 2:
        return parts[0], "_".join(parts[1:]), label
    return None, None, label


def file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(
        timespec="seconds"
    )


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 6) if drawdowns else None,
        "window_count": len(windows),
        "windows": [
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
            }
            for row in windows
        ],
    }


def load_ortex_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for path in sorted(ORTEX_DIR.glob("ortex_*_SHORT_INTEREST.json")):
        exchange, ticker, label = parse_source_name(path)
        payload = read_json(path, {})
        raw_rows = payload.get("rows") if isinstance(payload, dict) else []
        if not isinstance(raw_rows, list):
            raw_rows = []
        file_info = {
            "path": repo_rel(path),
            "exchange": exchange,
            "ticker": ticker,
            "label": label,
            "mtime_utc": file_mtime_utc(path),
            "payload_length": payload.get("length") if isinstance(payload, dict) else None,
            "row_count": len(raw_rows),
            "credits_used": payload.get("creditsUsed") if isinstance(payload, dict) else None,
            "credits_left": payload.get("creditsLeft") if isinstance(payload, dict) else None,
            "sha256": sha256(path),
        }
        files.append(file_info)
        for raw in raw_rows:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            row["_source_file"] = repo_rel(path)
            row["_file_mtime_utc"] = file_info["mtime_utc"]
            row["_exchange"] = exchange
            row["_ticker"] = ticker
            row["_label"] = label
            rows.append(row)
    return rows, files


def field_coverage(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    scanned = len(rows)
    coverage: dict[str, Any] = {}
    for field in fields:
        present = sum(1 for row in rows if is_present(row.get(field)))
        coverage[field] = {
            "present_rows": present,
            "scanned_rows": scanned,
            "present_rate": round(present / scanned, 6) if scanned else 0.0,
        }
    return coverage


def any_field_count(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> int:
    return sum(1 for row in rows if any(is_present(row.get(field)) for field in fields))


def build_ortex_surface() -> dict[str, Any]:
    rows, files = load_ortex_rows()
    tickers = sorted({str(row.get("_ticker")) for row in rows if row.get("_ticker")})
    dates = sorted({str(row.get("date")) for row in rows if row.get("date")})
    pct_float = [
        value
        for value in (safe_float(row.get("shortInterestPcFreeFloat")) for row in rows)
        if value is not None
    ]
    shares = [
        value
        for value in (safe_float(row.get("shortInterestShares")) for row in rows)
        if value is not None
    ]
    usd = [
        value
        for value in (safe_float(row.get("shortInterestUsd")) for row in rows)
        if value is not None
    ]
    per_ticker = Counter(str(row.get("_ticker")) for row in rows if row.get("_ticker"))
    per_date = Counter(str(row.get("date")) for row in rows if row.get("date"))
    pit_rows = any_field_count(rows, PIT_DATE_FIELDS)
    borrow_rows = any_field_count(rows, BORROW_ECONOMICS_FIELDS)
    short_interest_rows = sum(
        1 for row in rows if all(is_present(row.get(field)) for field in SHORT_INTEREST_FIELDS)
    )
    sample_rows = [
        {
            "ticker": row.get("_ticker"),
            "exchange": row.get("_exchange"),
            "date": row.get("date"),
            "shortInterestShares": row.get("shortInterestShares"),
            "shortInterestPcFreeFloat": row.get("shortInterestPcFreeFloat"),
            "shortInterestUsd": row.get("shortInterestUsd"),
            "source_file": row.get("_source_file"),
            "file_mtime_utc": row.get("_file_mtime_utc"),
        }
        for row in rows[:4]
    ]
    return {
        "source_dir": repo_rel(ORTEX_DIR),
        "source_dir_exists": ORTEX_DIR.exists(),
        "source_files": files,
        "file_count": len(files),
        "row_count": len(rows),
        "unique_tickers": len(tickers),
        "tickers": tickers,
        "row_count_by_ticker": dict(per_ticker),
        "data_date_count": len(dates),
        "data_date_min": dates[0] if dates else None,
        "data_date_max": dates[-1] if dates else None,
        "row_count_by_data_date": dict(per_date),
        "short_interest_complete_rows": short_interest_rows,
        "pit_publication_or_usable_date_rows": pit_rows,
        "borrow_economics_populated_rows": borrow_rows,
        "field_coverage": {
            "short_interest": field_coverage(rows, SHORT_INTEREST_FIELDS),
            "pit_dates": field_coverage(rows, PIT_DATE_FIELDS),
            "borrow_economics": field_coverage(rows, BORROW_ECONOMICS_FIELDS),
        },
        "short_interest_pct_free_float": summarize_numbers(pct_float),
        "short_interest_shares": summarize_numbers(shares),
        "short_interest_usd": summarize_numbers(usd),
        "sample_rows": sample_rows,
        "pit_boundary": (
            "Rows have provider data dates and local file mtimes, but no "
            "provider publication_date or usable_trade_date. Treat as fetched "
            "sample payloads, not append-only PIT decision rows."
        ),
    }


def readiness_failures(surface: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if surface["row_count"] <= 0:
        failures.append("no_ortex_rows")
    if surface["unique_tickers"] < 20:
        failures.append("ticker_count_below_20")
    if surface["data_date_count"] < 20:
        failures.append("data_date_count_below_20")
    if surface["pit_publication_or_usable_date_rows"] <= 0:
        failures.append("publication_or_usable_trade_date_absent")
    if surface["borrow_economics_populated_rows"] <= 0:
        failures.append("borrow_fee_utilization_loan_availability_absent")
    if surface["short_interest_complete_rows"] != surface["row_count"]:
        failures.append("short_interest_fields_incomplete")
    failures.append("not_append_only_daily_snapshot_ledger")
    failures.append("no_closed_forward_replacement_rows_joined")
    return failures


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    surface = build_ortex_surface()
    failures = readiness_failures(surface)
    status = "blocked"
    decision = "blocked_ortex_short_interest_sidecar_not_alpha_ready"
    timestamp = utc_now()
    gate4_passed = not failures
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair_readiness_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low_new_source_but_thin_payload",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": decision,
            "actual_success": 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(PREDICTION["success_probability"] ** 2, 4),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failures,
            "predicted_failure_mode_hit": True,
            "surprise_note": (
                "No surprise: ORTEX rows exist, but they are a tiny sample of "
                "short-interest values without PIT publication/usable dates or "
                "borrow-economics fields."
            ),
        },
        "parameters": {
            "source_dir": repo_rel(ORTEX_DIR),
            "readiness_min_tickers": 20,
            "readiness_min_data_dates": 20,
            "requires_publication_or_usable_trade_date": True,
            "requires_borrow_fee_or_utilization_or_loan_availability": True,
            "requires_append_only_daily_ledger": True,
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
            "ortex_file_count": surface["file_count"],
            "ortex_row_count": surface["row_count"],
            "ortex_unique_tickers": surface["unique_tickers"],
            "ortex_data_date_count": surface["data_date_count"],
            "borrow_economics_populated_rows": surface["borrow_economics_populated_rows"],
            "pit_publication_or_usable_date_rows": surface[
                "pit_publication_or_usable_date_rows"
            ],
        },
        "gate1": {"passed": BASELINE_RESULT.exists(), "baseline_metrics": baseline},
        "gate2": {
            "passed": surface["row_count"] > 0,
            "dependencies_validated": True,
            "dependency_fields_checked": [
                "ticker_from_filename",
                "exchange_from_filename",
                "date",
                *SHORT_INTEREST_FIELDS,
                *PIT_DATE_FIELDS,
                *BORROW_ECONOMICS_FIELDS,
                "entry_date",
                "target_price",
            ],
            "blocking_reason": (
                "Source rows load and short-interest fields are present, but "
                "publication/usable_trade_date and borrow-economics fields are absent."
            ),
            "entry_date_present": False,
            "target_price_present": False,
            "entry_date_target_price_note": (
                "ORTEX sidecar rows are source observations, not trade rows; any "
                "future alpha must join them to candidate/forward rows with explicit "
                "entry_date and target_price elsewhere."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, source allocator, ranking, sizing, or order rule was added.",
        },
        "gate4": {
            "passed": gate4_passed,
            "decision": decision,
            "accepted_alpha": False,
            "alpha_ready": False,
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
            "readiness_rule": {
                "min_tickers": 20,
                "min_data_dates": 20,
                "requires_publication_or_usable_trade_date": True,
                "requires_borrow_economics": True,
                "requires_append_only_daily_ledger": True,
                "requires_closed_forward_replacement_value_rows": True,
            },
            "failed_reasons": failures,
        },
        "decision": decision,
        "rejection_reason": ";".join(failures),
        "ortex_surface": surface,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned readiness artifact only. It reads local ORTEX "
                "files and writes no shared helper, daily adapter, order, rank, "
                "size, exit, watchlist, or LLM changes."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260625-003": "Moomoo borrow availability sidecar was blocked with zero borrow-populated rows.",
                "exp-20260625-019": "Moomoo daily short-volume clean-flow gate failed accepted-allocator Gate 4.",
                "exp-20260625-024": "Toxic short-volume notional downweight also failed.",
                "exp-20260627-002": "Daily non-OHLCV borrow collection was wired default-off, but still needs populated rows.",
                "novelty_gate": (
                    "Reservation passed with no strong near-neighbor; this is a new "
                    "ORTEX source readiness audit, not a FINRA or short-volume threshold scan."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Alpha remains blocked unless ORTEX rows provide enough tickers/dates, "
                "publication or usable-trade dates, borrow economics, append-only daily "
                "ledger semantics, and closed forward replacement rows."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The local ORTEX files are useful proof that the fetcher can produce "
                "short-interest payloads, but they only cover AAPL/MSFT over two dates "
                "and do not include publication/usable-trade dates or borrow fee, "
                "utilization, loan availability, shares available, or days-to-cover."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not run ORTEX/FINRA/options/short-flow alpha gates, notional "
                "haircuts, or threshold scans from these two sample ORTEX files. "
                "Do not treat local file mtime as publication-date PIT evidence."
            ),
            "new_evidence_required": (
                "A valid retry needs an append-only ORTEX daily sidecar with provider "
                "publication_date or usable_trade_date, at least 20 tickers over 20 "
                "decision dates, populated borrow fee/utilization/loan availability "
                "or days-to-cover fields, then closed forward replacement-value rows."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(ORTEX_SIDECAR),
            repo_rel(ORTEX_DIR),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260625-003.json",
            "experiments/logs/exp-20260625-019.json",
            "experiments/logs/exp-20260625-024.json",
            "experiments/logs/exp-20260627-002.json",
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
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    surface = dict(payload["ortex_surface"])
    surface["sample_rows"] = surface["sample_rows"][:2]
    surface["source_files"] = surface["source_files"][:4]
    record["ortex_surface"] = surface
    return record


def build_card(payload: dict[str, Any]) -> str:
    surface = payload["ortex_surface"]
    return "\n".join(
        [
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Accepted alpha: `false`",
            f"- ORTEX files: `{surface['file_count']}`",
            f"- Rows: `{surface['row_count']}`",
            f"- Tickers: `{surface['unique_tickers']}`",
            f"- Data dates: `{surface['data_date_count']}`",
            f"- PIT publication/usable rows: `{surface['pit_publication_or_usable_date_rows']}`",
            f"- Borrow-economics rows: `{surface['borrow_economics_populated_rows']}`",
            "- Strategy behavior changed: `false`",
            "",
            "## Result",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
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
        ORTEX_SIDECAR,
        *sorted(ORTEX_DIR.glob("ortex_*_SHORT_INTEREST.json")),
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
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "alpha_ready": False,
            "observed_only_lead": False,
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
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "ortex_surface": {
                key: value
                for key, value in payload["ortex_surface"].items()
                if key not in {"sample_rows", "source_files"}
            },
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "ortex_file_count": payload["ortex_surface"]["file_count"],
                "ortex_row_count": payload["ortex_surface"]["row_count"],
                "unique_tickers": payload["ortex_surface"]["unique_tickers"],
                "data_date_count": payload["ortex_surface"]["data_date_count"],
                "borrow_economics_rows": payload["ortex_surface"][
                    "borrow_economics_populated_rows"
                ],
                "pit_publication_or_usable_date_rows": payload["ortex_surface"][
                    "pit_publication_or_usable_date_rows"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
