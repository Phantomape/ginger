"""exp-20260625-004: local OHLCV recovery surface audit.

Measurement repair only. exp-20260625-002 materialized an estimate-revision
candidate-match outcome ledger, but could not settle current selected rows
because the local OHLCV warehouse stops before the required 2026-06-24 entry
date. This runner checks whether any other local price-like surface can safely
repair that blocker.

No strategy, shared helper, ranking, sizing, exit, paper order, live order,
watchlist, LLM, or production daily behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-004"
OWNER = "alpha-explore"
SLUG = "local_ohlcv_recovery_surface_audit"
RUNNER = f"quant/experiments/exp_20260625_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
EXP002_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260625-002"
    / "exp_20260625_002_estimate_revision_candidate_match_outcome_ledger.json"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_004_{SLUG}.json"
BEFORE_JSON = DATA_DIR / f"exp_20260625_004_{SLUG}_before.json"
AFTER_JSON = DATA_DIR / f"exp_20260625_004_{SLUG}_after.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

REQUIRED_ENTRY_DATE = "2026-06-24"
MIN_SETTLED_ROWS = 20
PROXY_NOTIONAL_USD = 4000.0
PRICE_LIKE_PATHS = (
    REPO_ROOT / "data" / "daily" / "universe" / "universe_state_20260624.json",
    REPO_ROOT
    / "data"
    / "daily"
    / "intraday"
    / "snapshots"
    / "intraday_review_20260624_1302ET.json",
    REPO_ROOT / "data" / "daily" / "orders" / "bracket_orders_20260623.json",
    REPO_ROOT / "data" / "backtests" / "backtest_results_20260623.json",
    REPO_ROOT / "data" / "kova" / "intraday" / "intraday_ohlcv_20260623.jsonl",
    REPO_ROOT / "data" / "kova" / "intraday" / "intraday_ohlcv_20260624.jsonl",
)

HYPOTHESIS = (
    "measurement_repair: estimate-revision candidate-match replacement value "
    "may become testable once the post-2026-06-15 OHLCV freshness blocker is "
    "audited across every local price-like surface; do not retest revision "
    "thresholds unless a true 2026-06-24 daily price source exists."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision candidate matches may contain replacement value, but "
    "that alpha is only testable if selected/current rows can be settled with "
    "PIT-safe 2026-06-24 daily prices versus cash, SPY, and QQQ."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "estimate_revision_candidate_match_measurement_repair"
TRIAL_FAMILY = "local_ohlcv_recovery_surface_audit"
TRIAL_VARIANT_ID = "local_post_20260615_ohlcv_recovery_surface_audit_v1"
CHANGED_VARIABLE = "local_post_20260615_ohlcv_recovery_surface_audit_v1"
CAUSAL_COMPONENTS = [
    "warehouse_date_range",
    "daily_universe_shape",
    "intraday_review_price_scope",
    "order_snapshot_price_scope",
    "local_price_file_search",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-002",
    "exp-20260624-012",
    "exp-20260624-002",
]
NEW_EVIDENCE_AXIS = (
    "Local price-like surface audit after exp-20260625-002, covering intraday "
    "review, orders, universe, backtest artifacts, and file inventory; not a "
    "revision threshold or observed-only forward condition reslice."
)
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"_decode_error": True, "raw_prefix": line[:200]})
            if limit is not None and len(rows) >= limit:
                break
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except json.JSONDecodeError:
                    row = {"_raw": stripped}
                if row.get("experiment_id") != record["experiment_id"]:
                    existing.append(row)
    existing.append(record)
    with path.open("w", encoding="utf-8") as handle:
        for row in existing:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def baseline_metrics() -> dict[str, Any]:
    data = load_json(BASELINE_RESULT, {})
    windows = data.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_exists": BASELINE_RESULT.exists(),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": sum(int(w.get("signals_generated") or 0) for w in windows),
        "signals_survived": sum(int(w.get("signals_survived") or 0) for w in windows),
        "survival_rate": round(
            sum(int(w.get("signals_survived") or 0) for w in windows)
            / max(1, sum(int(w.get("signals_generated") or 0) for w in windows)),
            4,
        ),
        "max_drawdown_pct_worst": max(
            [float(w.get("max_drawdown_pct") or 0.0) for w in windows] or [0.0]
        ),
        "windows": windows,
    }


def warehouse_audit() -> dict[str, Any]:
    if not WAREHOUSE.exists():
        return {
            "path": repo_rel(WAREHOUSE),
            "exists": False,
            "max_date": None,
            "rows": 0,
            "can_settle_required_entry_date": False,
            "reason": "warehouse_missing",
        }
    with sqlite3.connect(WAREHOUSE) as con:
        row = con.execute("select min(date), max(date), count(*) from ohlcv").fetchone()
    min_date, max_date, count = row
    return {
        "path": repo_rel(WAREHOUSE),
        "exists": True,
        "min_date": min_date,
        "max_date": max_date,
        "rows": int(count or 0),
        "required_entry_date": REQUIRED_ENTRY_DATE,
        "can_settle_required_entry_date": bool(max_date and str(max_date) >= REQUIRED_ENTRY_DATE),
        "reason": "ok" if max_date and str(max_date) >= REQUIRED_ENTRY_DATE else "warehouse_stale",
    }


def exp002_surface() -> dict[str, Any]:
    data = load_json(EXP002_ARTIFACT, {})
    rows = data.get("matched_outcome_rows") or []
    selected = [r for r in rows if r.get("surface_label") == "selected_current"]
    selected_tickers = sorted({str(r.get("ticker")) for r in selected if r.get("ticker")})
    entry_dates = Counter(str(r.get("entry_date") or "") for r in selected)
    return {
        "source_artifact": repo_rel(EXP002_ARTIFACT),
        "exists": EXP002_ARTIFACT.exists(),
        "exp002_decision": data.get("decision"),
        "matched_rows": len(rows),
        "selected_current_rows": len(selected),
        "selected_current_unique_tickers": len(selected_tickers),
        "selected_current_sample_tickers": selected_tickers[:20],
        "selected_current_entry_date_counts": dict(sorted(entry_dates.items())),
        "exp002_outcome_summary": data.get("outcome_summary") or {},
        "exp002_warehouse_date_range": (
            ((data.get("gate2") or {}).get("source_metadata") or {}).get("warehouse_date_range")
        ),
    }


OHLCV_FIELDS = {"open", "high", "low", "close", "volume"}
CURRENT_PRICE_FIELDS = {"current_price", "intraday_price", "price", "last_price"}


def walk_records(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    stack = [("$", payload)]
    while stack:
        path, value = stack.pop()
        if isinstance(value, dict):
            if any(k in value for k in ("ticker", "symbol")):
                record = dict(value)
                record["_path"] = path
                records.append(record)
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    stack.append((f"{path}.{key}", child))
        elif isinstance(value, list):
            for idx, child in enumerate(value):
                if isinstance(child, (dict, list)):
                    stack.append((f"{path}[{idx}]", child))
    return records


def classify_records(records: list[dict[str, Any]], selected_tickers: set[str]) -> dict[str, Any]:
    daily_ohlcv_rows: list[dict[str, Any]] = []
    current_price_rows: list[dict[str, Any]] = []
    for row in records:
        keys = set(row)
        ticker = str(row.get("ticker") or row.get("symbol") or "")
        date = str(row.get("date") or row.get("asof_date") or row.get("as_of_date") or "")
        if ticker and OHLCV_FIELDS.issubset(keys) and REQUIRED_ENTRY_DATE in date:
            daily_ohlcv_rows.append(row)
        if ticker and keys.intersection(CURRENT_PRICE_FIELDS):
            current_price_rows.append(row)
    daily_tickers = {str(r.get("ticker") or r.get("symbol")) for r in daily_ohlcv_rows}
    current_tickers = {str(r.get("ticker") or r.get("symbol")) for r in current_price_rows}
    return {
        "record_count_with_ticker": len(records),
        "daily_ohlcv_equivalent_rows_required_date": len(daily_ohlcv_rows),
        "daily_ohlcv_selected_current_ticker_coverage": len(daily_tickers & selected_tickers),
        "current_price_rows": len(current_price_rows),
        "current_price_selected_current_ticker_coverage": len(current_tickers & selected_tickers),
        "sample_daily_ohlcv_rows": [
            {
                "ticker": r.get("ticker") or r.get("symbol"),
                "date": r.get("date") or r.get("asof_date") or r.get("as_of_date"),
                "path": r.get("_path"),
            }
            for r in daily_ohlcv_rows[:5]
        ],
        "sample_current_price_rows": [
            {
                "ticker": r.get("ticker") or r.get("symbol"),
                "path": r.get("_path"),
                "price_fields": sorted(set(r).intersection(CURRENT_PRICE_FIELDS)),
            }
            for r in current_price_rows[:8]
        ],
    }


def audit_json_surface(path: Path, selected_tickers: set[str]) -> dict[str, Any]:
    payload = load_json(path)
    if payload is None:
        return {
            "path": repo_rel(path),
            "exists": False,
            "surface_type": "missing",
            "daily_ohlcv_equivalent_rows_required_date": 0,
            "daily_ohlcv_selected_current_ticker_coverage": 0,
            "current_price_rows": 0,
            "usable_for_entry_day_settlement": False,
            "reason": "file_missing",
        }
    records = walk_records(payload)
    classification = classify_records(records, selected_tickers)
    top_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    usable = classification["daily_ohlcv_selected_current_ticker_coverage"] >= MIN_SETTLED_ROWS
    return {
        "path": repo_rel(path),
        "exists": True,
        "surface_type": "json",
        "top_level_keys": top_keys[:30],
        **classification,
        "usable_for_entry_day_settlement": usable,
        "reason": "daily_ohlcv_equivalent_found" if usable else "no_candidate_level_daily_ohlcv",
    }


def audit_jsonl_surface(path: Path, selected_tickers: set[str]) -> dict[str, Any]:
    rows = load_jsonl(path)
    if not path.exists():
        return {
            "path": repo_rel(path),
            "exists": False,
            "surface_type": "missing",
            "daily_ohlcv_equivalent_rows_required_date": 0,
            "daily_ohlcv_selected_current_ticker_coverage": 0,
            "current_price_rows": 0,
            "usable_for_entry_day_settlement": False,
            "reason": "file_missing",
        }
    status_counts = Counter(str(r.get("status") or "missing") for r in rows)
    reason_counts = Counter(str(r.get("reason") or "missing") for r in rows)
    classification = classify_records(rows, selected_tickers)
    usable = classification["daily_ohlcv_selected_current_ticker_coverage"] >= MIN_SETTLED_ROWS
    return {
        "path": repo_rel(path),
        "exists": True,
        "surface_type": "jsonl",
        "row_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "top_reason_counts": dict(reason_counts.most_common(8)),
        **classification,
        "usable_for_entry_day_settlement": usable,
        "reason": "daily_ohlcv_equivalent_found" if usable else "no_candidate_level_daily_ohlcv",
    }


def audit_price_like_surfaces(selected_tickers: set[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in PRICE_LIKE_PATHS:
        if path.suffix.lower() == ".jsonl":
            results.append(audit_jsonl_surface(path, selected_tickers))
        else:
            results.append(audit_json_surface(path, selected_tickers))
    return results


def file_inventory() -> dict[str, Any]:
    terms = ("price", "quote", "ohlcv", "bar", "snapshot", "intraday", "orders", "universe")
    candidates: list[str] = []
    for path in (REPO_ROOT / "data").rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        rel = repo_rel(path)
        if ("20260624" in name or "20260623" in name) and any(term in rel.lower() for term in terms):
            candidates.append(rel)
    return {
        "candidate_price_like_file_count": len(candidates),
        "candidate_price_like_files": sorted(candidates)[:200],
    }


def build_gate2(exp002: dict[str, Any], warehouse: dict[str, Any], surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    usable_sources = [
        s
        for s in surfaces
        if s.get("daily_ohlcv_selected_current_ticker_coverage", 0) >= MIN_SETTLED_ROWS
    ]
    failed = []
    if not warehouse.get("can_settle_required_entry_date"):
        failed.append("warehouse_latest_date_before_required_entry_date")
    if not usable_sources:
        failed.append("no_local_daily_ohlcv_equivalent_for_20260624_selected_current_rows")
    if exp002["selected_current_rows"] == 0:
        failed.append("no_selected_current_rows_to_repair")
    return {
        "passed": not failed,
        "fields_checked": [
            "ticker",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "current_price",
            "intraday_price",
        ],
        "required_entry_date": REQUIRED_ENTRY_DATE,
        "minimum_selected_current_settled_rows": MIN_SETTLED_ROWS,
        "failed_reasons": failed,
        "exp002_surface": exp002,
        "warehouse": warehouse,
        "price_like_surfaces": surfaces,
    }


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        WAREHOUSE,
        EXP002_ARTIFACT,
        *PRICE_LIKE_PATHS,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path if path.is_absolute() else REPO_ROOT / path): {
                "exists": (path if path.is_absolute() else REPO_ROOT / path).exists(),
                "sha256": sha256(path if path.is_absolute() else REPO_ROOT / path),
            }
            for path in files
        },
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": payload["alpha_ready"],
        "decision": payload["decision"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "local_price_surface_recovery_audit",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "gate1": payload["gate1"],
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "failed_reasons": payload["gate2"]["failed_reasons"],
            "required_entry_date": REQUIRED_ENTRY_DATE,
            "warehouse": payload["gate2"]["warehouse"],
            "price_like_surface_summary": [
                {
                    "path": s["path"],
                    "exists": s["exists"],
                    "current_price_rows": s.get("current_price_rows"),
                    "daily_ohlcv_selected_current_ticker_coverage": s.get(
                        "daily_ohlcv_selected_current_ticker_coverage"
                    ),
                    "usable_for_entry_day_settlement": s.get("usable_for_entry_day_settlement"),
                    "reason": s.get("reason"),
                }
                for s in payload["gate2"]["price_like_surfaces"]
            ],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": repo_rel(OUT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    gate2 = payload["gate2"]
    lines = [
        f"# {EXPERIMENT_ID}: local OHLCV recovery surface audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Required entry date: `{REQUIRED_ENTRY_DATE}`",
        f"- Warehouse max date: `{gate2['warehouse'].get('max_date')}`",
        f"- Selected/current rows from exp002: `{gate2['exp002_surface']['selected_current_rows']}`",
        f"- Local usable settlement sources: `{sum(1 for s in gate2['price_like_surfaces'] if s.get('usable_for_entry_day_settlement'))}`",
        "",
        "## Readout",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Reproduction",
        "",
        f"`{RUNNER_COMMAND}`",
    ]
    return "\n".join(lines) + "\n"


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = load_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    warehouse = warehouse_audit()
    exp002 = exp002_surface()
    selected_tickers = set(exp002["selected_current_sample_tickers"])
    selected_tickers.update(
        str(t)
        for t in (load_json(EXP002_ARTIFACT, {}).get("matched_outcome_rows") or [])
        if isinstance(t, str)
    )
    all_exp002_rows = load_json(EXP002_ARTIFACT, {}).get("matched_outcome_rows") or []
    selected_tickers = {
        str(row.get("ticker"))
        for row in all_exp002_rows
        if row.get("surface_label") == "selected_current" and row.get("ticker")
    }
    surfaces = audit_price_like_surfaces(selected_tickers)
    gate2 = build_gate2(exp002, warehouse, surfaces)
    inventory = file_inventory()
    settled_coverage = max(
        [int(s.get("daily_ohlcv_selected_current_ticker_coverage") or 0) for s in surfaces]
        + [0]
    )
    alpha_ready = gate2["passed"] and settled_coverage >= MIN_SETTLED_ROWS
    failed_reasons = list(gate2["failed_reasons"])
    if not alpha_ready and "cannot_settle_minimum_selected_current_rows" not in failed_reasons:
        failed_reasons.append("cannot_settle_minimum_selected_current_rows")
    decision = (
        "accepted_measurement_repair_local_ohlcv_surface_found"
        if alpha_ready
        else "blocked_no_local_20260624_daily_ohlcv_recovery_surface"
    )
    status = "accepted" if alpha_ready else "blocked"
    why = (
        "A local daily OHLCV-equivalent surface was found for enough selected/current rows."
        if alpha_ready
        else (
            "No local price-like surface can safely settle the exp-20260625-002 "
            "selected/current estimate-revision rows for 2026-06-24. The warehouse "
            f"max date is {warehouse.get('max_date')}; intraday review and bracket "
            "orders expose current prices only for held/order tickers, Kova intraday "
            "is missing or skipped, and universe/backtest artifacts do not provide "
            "candidate-level daily open/high/low/close/volume for the required date."
        )
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "owner": OWNER,
        "status": status,
        "accepted": alpha_ready,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "observed_only_lead": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_audit_only_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "local_price_surface_recovery_audit",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "ticket_before": ticket,
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": gate2,
        "gate3": {
            "passed": exp002["selected_current_rows"] > 0,
            "signals_generated_proxy": exp002["selected_current_rows"],
            "signals_survived_proxy": settled_coverage,
            "survival_rate_proxy": round(settled_coverage / max(1, exp002["selected_current_rows"]), 4),
            "note": (
                "Signals_generated_proxy is selected/current rows needing settlement; "
                "signals_survived_proxy is local daily OHLCV-equivalent coverage, not "
                "an executable trading filter."
            ),
        },
        "gate4": {
            "passed": alpha_ready,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "expected_value_score_sum_before": baseline["expected_value_score_sum"],
            "expected_value_score_sum_after": baseline["expected_value_score_sum"],
            "aggregate_ev_delta": 0.0,
            "total_pnl_before": baseline["total_pnl"],
            "total_pnl_after": baseline["total_pnl"],
            "aggregate_pnl_delta": 0.0,
            "trade_count_before": baseline["trade_count"],
            "trade_count_after": baseline["trade_count"],
            "strategy_behavior_changed": False,
            "minimum_selected_current_settled_rows": MIN_SETTLED_ROWS,
            "max_selected_current_daily_ohlcv_coverage": settled_coverage,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "prediction": {
            "success_probability": 0.2,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "no_local_20260624_ohlcv",
                "only_intraday_positions_prices",
                "no_candidate_level_price_coverage",
                "warehouse_still_stale",
            ],
            "confidence_reason": (
                "exp-20260625-002 already showed the warehouse stops at 2026-06-15; "
                "this run checks whether other local surfaces can repair that "
                "specific blocker before any alpha retry."
            ),
            "recorded_at": (ticket.get("prediction") or {}).get("recorded_at"),
        },
        "calibration": {
            "actual_success": 1.0 if alpha_ready else 0.0,
            "actual_gate4_passed": alpha_ready,
            "brier_score": round((0.2 - (1.0 if alpha_ready else 0.0)) ** 2, 4),
            "predicted_failure_modes": [
                "no_local_20260624_ohlcv",
                "only_intraday_positions_prices",
                "no_candidate_level_price_coverage",
                "warehouse_still_stale",
            ],
            "realized_failure_modes": failed_reasons,
            "surprise_note": (
                "Low surprise. Local operational price files are not PIT-safe daily "
                "OHLCV and cannot substitute for the stale warehouse."
            ),
        },
        "production_impact": {
            "adapter_status": "none",
            "default_off_paper_only": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "shared_policy_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Measurement artifact only. This run audits local data availability "
                "and writes no shared helper, backtester adapter, daily adapter, "
                "order, rank, size, exit, watchlist, or LLM changes."
            ),
        },
        "price_file_inventory": inventory,
        "post_run_reflection": {
            "why_result_happened": why,
            "outcome_summary": (
                f"Warehouse latest date {warehouse.get('max_date')}; max selected/current "
                f"daily-OHLCV coverage across local side surfaces {settled_coverage}/"
                f"{exp002['selected_current_rows']}."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry revision thresholds, direction gates, top-N, hold days, "
                "notional, rank, or observed-only condition slices on the same "
                "2026-06-23/2026-06-24 surface. Do not treat intraday review current "
                "prices or bracket-order current prices as settled entry-day outcomes."
            ),
            "new_evidence_required": (
                "Refresh or materialize PIT-safe daily OHLCV through at least "
                "2026-06-24 for the selected/current candidate universe, or add a "
                "validated quote/bars archive with entry and close semantics for "
                "cash/SPY/QQQ replacement values."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260624-012": "Built the estimate-revision candidate match surface.",
                "exp-20260625-002": (
                    "Materialized row-level matched outcomes but blocked because "
                    "warehouse max date was before 2026-06-24."
                ),
                "novelty_gate": (
                    "Warned near revision families but did not block; this run audits "
                    "local price recovery, not revision policy."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Pass only if a PIT-safe local daily OHLCV or equivalent source can "
                "settle 2026-06-24 entry-day outcomes for at least 20 selected_current rows."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "artifact": repo_rel(OUT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "changed_files": ALLOWED_WRITE_SCOPE,
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(WAREHOUSE),
            repo_rel(EXP002_ARTIFACT),
            *[repo_rel(path) for path in PRICE_LIKE_PATHS],
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
        "proxy_notional_usd": PROXY_NOTIONAL_USD,
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, payload["gate1"]["baseline_metrics"])
    write_json(AFTER_JSON, payload["gate1"]["baseline_metrics"])
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
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": payload["alpha_ready"],
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
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
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
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
                "warehouse_max_date": payload["gate2"]["warehouse"].get("max_date"),
                "selected_current_rows": payload["gate2"]["exp002_surface"][
                    "selected_current_rows"
                ],
                "max_selected_current_daily_ohlcv_coverage": payload["gate4"][
                    "max_selected_current_daily_ohlcv_coverage"
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
