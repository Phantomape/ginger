"""exp-20260623-013: Kova multi-source forward observation ledger.

Measurement repair for the Kova multi-source alpha blocker found in
exp-20260622-005. Kova is production-visible forward data, but it lacked a
normalized observation ledger that can later be closed with replacement-value
outcomes. This runner materializes that experiment-owned ledger only.

No strategy, ranking, sizing, exit, order, watchlist, LLM, or production daily
collector behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-013"
OWNER = "alpha-explore"
SLUG = "kova_multisource_forward_observation_ledger"
RUNNER = f"quant/experiments/exp_20260623_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_013_{SLUG}.json"
LEDGER_JSONL = DATA_DIR / "kova_multisource_forward_observation_ledger.jsonl"
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
KOVA_ROOT = REPO_ROOT / "data" / "kova"
SNAPSHOT_DIR = KOVA_ROOT / "snapshots"
RS_DIR = KOVA_ROOT / "rs_proxy"
FUNDAMENTALS_DIR = KOVA_ROOT / "fundamentals"
INSTITUTIONAL_DIR = KOVA_ROOT / "institutional"
INTRADAY_DIR = KOVA_ROOT / "intraday"

OBSERVATION_START = "2026-06-13"
SELECTED_FUNDAMENTAL_COMPONENTS = (
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "eps_diluted",
)

HYPOTHESIS = (
    "Kova multi-source candidate-pool alpha is blocked because the current "
    "production-visible Kova snapshots have no normalized forward observation "
    "ledger or future close/replacement placeholders; materialize a read-only "
    "ledger so later rows can close without re-scanning ad hoc snapshots."
)
ALPHA_HYPOTHESIS = (
    "Kova multi-source RS, filed-date fundamental growth, institutional "
    "ownership, and intraday flow may become an orthogonal candidate-pool edge, "
    "but the alpha is not testable until forward observations are replayable "
    "and later closed with replacement value."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "kova_multisource_forward_observation"
TRIAL_FAMILY = "kova_forward_observation_ledger"
TRIAL_VARIANT_ID = "kova_multisource_snapshot_rows_v1"
CHANGED_VARIABLE = "kova_multisource_forward_observation_ledger_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260622-005"]
CAUSAL_COMPONENTS = [
    "Kova snapshot normalization",
    "RS/fundamental/13F/intraday field capture",
    "forward outcome placeholders",
    "no strategy behavior change",
]

REQUIRED_LEDGER_FIELDS = [
    "observation_id",
    "asof_date",
    "ticker",
    "rs_proxy_status",
    "rs_proxy_rank_pct_20d",
    "companyfacts_growth_row_count",
    "sec13f_status",
    "intraday_status",
    "outcome_status",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def stable_id(parts: list[Any]) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
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


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def date_from_filename(path: Path) -> str | None:
    match = re.search(r"(20\d{6})", path.name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad_json = 0
    if not path.exists():
        return rows, bad_json
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                bad_json += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows, bad_json


def rows_by_ticker(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, bad_json = iter_jsonl(path)
    out: dict[str, dict[str, Any]] = {}
    status_counts: Counter[str] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        status = str(row.get("status") or row.get("growth_status") or "unknown")
        status_counts[status] += 1
        out[ticker] = row
    return out, {
        "path": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "bad_json_rows": bad_json,
        "status_counts": dict(sorted(status_counts.items())),
    }


def summarize_companyfacts(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, bad_json = iter_jsonl(path)
    ticker_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "companyfacts_growth_row_count": 0,
            "companyfacts_growth_ok_raw_rows": 0,
            "latest_component_asof": {},
            "latest_component_yoy_growth": {},
        }
    )
    status_counts: Counter[str] = Counter()
    canonical_counts: Counter[str] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        canonical = str(row.get("canonical") or "")
        status = str(row.get("growth_status") or "unknown")
        status_counts[status] += 1
        if canonical:
            canonical_counts[canonical] += 1
        stats = ticker_stats[ticker]
        stats["companyfacts_growth_row_count"] += 1
        if status == "ok":
            stats["companyfacts_growth_ok_raw_rows"] += 1
        if canonical not in SELECTED_FUNDAMENTAL_COMPONENTS or status != "ok":
            continue
        yoy = round_or_none(row.get("yoy_growth"), 6)
        if yoy is None:
            continue
        asof_date = str(row.get("asof_date") or "")[:10]
        prev_asof = str(stats["latest_component_asof"].get(canonical) or "")
        if not prev_asof or asof_date >= prev_asof:
            stats["latest_component_asof"][canonical] = asof_date
            stats["latest_component_yoy_growth"][canonical] = yoy
    compact: dict[str, dict[str, Any]] = {}
    for ticker, stats in ticker_stats.items():
        growth = dict(sorted(stats["latest_component_yoy_growth"].items()))
        compact[ticker] = {
            "companyfacts_growth_row_count": stats["companyfacts_growth_row_count"],
            "companyfacts_growth_ok_raw_rows": stats["companyfacts_growth_ok_raw_rows"],
            "companyfacts_selected_ok_component_count": len(growth),
            "companyfacts_selected_positive_yoy_count": sum(
                1 for value in growth.values() if value is not None and value > 0
            ),
            "companyfacts_latest_component_yoy_growth": growth,
            "companyfacts_latest_component_asof": dict(
                sorted(stats["latest_component_asof"].items())
            ),
        }
    return compact, {
        "path": repo_rel(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "bad_json_rows": bad_json,
        "status_counts": dict(sorted(status_counts.items())),
        "selected_components": list(SELECTED_FUNDAMENTAL_COMPONENTS),
        "selected_component_row_counts": {
            key: int(canonical_counts[key]) for key in SELECTED_FUNDAMENTAL_COMPONENTS
        },
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def source_file_for(directory: Path, stem: str, asof_date: str) -> Path:
    compact = asof_date.replace("-", "")
    return directory / f"{stem}_{compact}.jsonl"


def snapshot_files() -> list[Path]:
    files = []
    for path in sorted(SNAPSHOT_DIR.glob("kova_data_snapshot_*.json")):
        asof_date = date_from_filename(path)
        if asof_date and asof_date >= OBSERVATION_START:
            files.append(path)
    return files


def quality_flags(
    rs_row: dict[str, Any] | None,
    fundamental_stats: dict[str, Any] | None,
    sec13f_row: dict[str, Any] | None,
    intraday_row: dict[str, Any] | None,
) -> list[str]:
    flags = ["pending_forward_close", "no_entry_date_target_price_by_design"]
    if not rs_row or rs_row.get("status") != "ok":
        flags.append("rs_proxy_not_ok")
    if not fundamental_stats or not fundamental_stats.get("companyfacts_selected_ok_component_count"):
        flags.append("no_companyfacts_growth_ok_components")
    if not sec13f_row or sec13f_row.get("status") != "ok":
        flags.append("sec13f_unavailable_or_skipped")
    if not intraday_row or intraday_row.get("status") != "ok":
        flags.append("intraday_unavailable_or_skipped")
    return flags


def build_observation_ledger() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    file_audit: dict[str, Any] = {
        "snapshot_files": [],
        "rs_proxy": [],
        "companyfacts_growth": [],
        "sec13f_ownership": [],
        "intraday_ohlcv": [],
    }
    for snapshot_path in snapshot_files():
        snapshot = read_json(snapshot_path, {})
        asof_date = str(snapshot.get("asof_date") or date_from_filename(snapshot_path) or "")[:10]
        if not asof_date:
            continue
        rs_path = source_file_for(RS_DIR, "rs_proxy", asof_date)
        fundamentals_path = source_file_for(FUNDAMENTALS_DIR, "companyfacts_growth", asof_date)
        sec13f_path = source_file_for(INSTITUTIONAL_DIR, "sec13f_ownership", asof_date)
        intraday_path = source_file_for(INTRADAY_DIR, "intraday_ohlcv", asof_date)

        rs_by_ticker, rs_audit = rows_by_ticker(rs_path)
        sec13f_by_ticker, sec13f_audit = rows_by_ticker(sec13f_path)
        intraday_by_ticker, intraday_audit = rows_by_ticker(intraday_path)
        fundamentals_by_ticker, fundamentals_audit = summarize_companyfacts(fundamentals_path)

        file_audit["snapshot_files"].append(
            {
                "path": repo_rel(snapshot_path),
                "asof_date": asof_date,
                "ticker_count": len(snapshot.get("tickers") or []),
                "status": snapshot.get("status"),
                "schema_version": snapshot.get("schema_version"),
            }
        )
        file_audit["rs_proxy"].append(rs_audit)
        file_audit["companyfacts_growth"].append(fundamentals_audit)
        file_audit["sec13f_ownership"].append(sec13f_audit)
        file_audit["intraday_ohlcv"].append(intraday_audit)

        tickers = sorted(rs_by_ticker or {str(t).upper(): {} for t in snapshot.get("tickers") or []})
        for ticker in tickers:
            rs_row = rs_by_ticker.get(ticker)
            sec13f_row = sec13f_by_ticker.get(ticker)
            intraday_row = intraday_by_ticker.get(ticker)
            fundamental_stats = fundamentals_by_ticker.get(ticker)
            flags = quality_flags(rs_row, fundamental_stats, sec13f_row, intraday_row)
            ledger.append(
                {
                    "schema_version": 1,
                    "experiment_id": EXPERIMENT_ID,
                    "rule_version": CHANGED_VARIABLE,
                    "observation_id": stable_id([CHANGED_VARIABLE, asof_date, ticker]),
                    "source": "kova_multisource_forward_snapshot",
                    "alpha_candidate_state": "observation_only_pending_outcome",
                    "asof_date": asof_date,
                    "symbol": ticker,
                    "ticker": ticker,
                    "source_snapshot_file": repo_rel(snapshot_path),
                    "rs_proxy_source_file": repo_rel(rs_path),
                    "companyfacts_growth_source_file": repo_rel(fundamentals_path),
                    "sec13f_source_file": repo_rel(sec13f_path),
                    "intraday_source_file": repo_rel(intraday_path),
                    "rs_proxy_status": (rs_row or {}).get("status"),
                    "rs_proxy_rank_pct_20d": round_or_none((rs_row or {}).get("rs_proxy_rank_pct_20d"), 6),
                    "rs_proxy_rank_pct_60d": round_or_none((rs_row or {}).get("rs_proxy_rank_pct_60d"), 6),
                    "rs_proxy_rank_pct_120d": round_or_none((rs_row or {}).get("rs_proxy_rank_pct_120d"), 6),
                    "excess_ret_20d_vs_spy": round_or_none((rs_row or {}).get("excess_ret_20d_vs_spy"), 6),
                    "excess_ret_60d_vs_spy": round_or_none((rs_row or {}).get("excess_ret_60d_vs_spy"), 6),
                    "excess_ret_120d_vs_spy": round_or_none((rs_row or {}).get("excess_ret_120d_vs_spy"), 6),
                    "available_window_count": (rs_row or {}).get("available_window_count"),
                    "companyfacts_growth_row_count": (fundamental_stats or {}).get(
                        "companyfacts_growth_row_count", 0
                    ),
                    "companyfacts_growth_ok_raw_rows": (fundamental_stats or {}).get(
                        "companyfacts_growth_ok_raw_rows", 0
                    ),
                    "companyfacts_selected_ok_component_count": (fundamental_stats or {}).get(
                        "companyfacts_selected_ok_component_count", 0
                    ),
                    "companyfacts_selected_positive_yoy_count": (fundamental_stats or {}).get(
                        "companyfacts_selected_positive_yoy_count", 0
                    ),
                    "companyfacts_latest_component_yoy_growth": (fundamental_stats or {}).get(
                        "companyfacts_latest_component_yoy_growth", {}
                    ),
                    "companyfacts_latest_component_asof": (fundamental_stats or {}).get(
                        "companyfacts_latest_component_asof", {}
                    ),
                    "sec13f_status": (sec13f_row or {}).get("status"),
                    "sec13f_reason": (sec13f_row or {}).get("reason"),
                    "intraday_status": (intraday_row or {}).get("status"),
                    "intraday_reason": (intraday_row or {}).get("reason"),
                    "entry_date": None,
                    "target_price": None,
                    "planned_entry_date": None,
                    "planned_exit_date": None,
                    "entry_date_resolution": "not_scheduled_observation_only",
                    "target_price_resolution": "not_scheduled_observation_only",
                    "outcome_status": "pending_forward_close",
                    "forward_5d_return_pct": None,
                    "forward_10d_return_pct": None,
                    "replacement_value_vs_cash_usd": None,
                    "replacement_value_vs_spy_usd": None,
                    "replacement_value_vs_qqq_usd": None,
                    "quality_flags": flags,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )
    return ledger, file_audit


def field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    out: dict[str, dict[str, Any]] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "coverage": round(present / total, 6) if total else 0.0,
        }
    return out


def ledger_summary(ledger: list[dict[str, Any]], file_audit: dict[str, Any]) -> dict[str, Any]:
    dates = sorted({str(row["asof_date"]) for row in ledger})
    tickers = sorted({str(row["ticker"]) for row in ledger})
    flags: Counter[str] = Counter()
    sec13f_status: Counter[str] = Counter()
    intraday_status: Counter[str] = Counter()
    for row in ledger:
        for flag in row.get("quality_flags") or []:
            flags[str(flag)] += 1
        sec13f_status[str(row.get("sec13f_status") or "missing")] += 1
        intraday_status[str(row.get("intraday_status") or "missing")] += 1
    duplicates = len(ledger) - len({row["observation_id"] for row in ledger})
    return {
        "ledger_rows": len(ledger),
        "asof_date_start": dates[0] if dates else None,
        "asof_date_end": dates[-1] if dates else None,
        "asof_date_count": len(dates),
        "ticker_count": len(tickers),
        "duplicate_observation_ids": duplicates,
        "pending_outcome_rows": sum(
            1 for row in ledger if row["outcome_status"] == "pending_forward_close"
        ),
        "rs_proxy_ok_rows": sum(1 for row in ledger if row.get("rs_proxy_status") == "ok"),
        "companyfacts_with_selected_components": sum(
            1 for row in ledger if row.get("companyfacts_selected_ok_component_count", 0) > 0
        ),
        "companyfacts_with_any_positive_yoy": sum(
            1 for row in ledger if row.get("companyfacts_selected_positive_yoy_count", 0) > 0
        ),
        "sec13f_status_counts": dict(sorted(sec13f_status.items())),
        "intraday_status_counts": dict(sorted(intraday_status.items())),
        "quality_flag_counts": dict(sorted(flags.items())),
        "field_coverage": field_coverage(ledger, REQUIRED_LEDGER_FIELDS),
        "source_file_audit": file_audit,
        "sample_observations": ledger[:10],
    }


def write_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_ticket_prediction() -> dict[str, Any] | None:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction if isinstance(prediction, dict) else None


def calibration(success: bool, failed: list[str]) -> dict[str, Any]:
    return {
        "actual_success": 1 if success else 0,
        "actual_decision": (
            "accepted_measurement_repair_kova_multisource_forward_observation_ledger"
            if success
            else "blocked_kova_multisource_forward_observation_ledger"
        ),
        "predicted_success_probability": None,
        "brier_score": None,
        "predicted_failure_modes": [],
        "realized_failure_modes": failed,
        "surprise_note": (
            "Kova forward snapshots had enough RS and filed-date fundamentals to "
            "materialize an observation ledger; 13F and intraday remain explicit "
            "unavailable/skipped caveats rather than alpha evidence."
            if success
            else "Kova forward snapshots were insufficient to build a replayable observation ledger."
        ),
    }


def build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    baseline = baseline_metrics()
    ledger, file_audit = build_observation_ledger()
    summary = ledger_summary(ledger, file_audit)
    failed: list[str] = []
    if summary["ledger_rows"] <= 0:
        failed.append("no_ledger_rows")
    if summary["duplicate_observation_ids"] != 0:
        failed.append("duplicate_observation_ids")
    if summary["asof_date_count"] < 5:
        failed.append("too_few_forward_asof_dates")
    if summary["rs_proxy_ok_rows"] <= 0:
        failed.append("no_rs_proxy_ok_rows")
    if summary["companyfacts_with_selected_components"] <= 0:
        failed.append("no_companyfacts_selected_components")
    for field, coverage in summary["field_coverage"].items():
        if coverage["coverage"] < 0.95:
            failed.append(f"field_{field}_coverage_below_95pct")
    success = not failed
    decision = (
        "accepted_measurement_repair_kova_multisource_forward_observation_ledger"
        if success
        else "blocked_kova_multisource_forward_observation_ledger"
    )
    status = "accepted_measurement_repair" if success else "blocked"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": success,
        "accepted_alpha": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_visible_forward_observation_rows",
        "prediction": load_ticket_prediction(),
        "calibration": calibration(success, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260622-005": (
                    "Blocked Kova multi-source alpha because fixed-window PIT "
                    "coverage, shared helper, and closed forward replacement rows "
                    "were missing."
                ),
                "novelty_gate": (
                    "Reservation warned on 13F near-neighbors because Kova includes "
                    "an institutional surface. This run is measurement repair only "
                    "and does not threshold-test 13F, Companyfacts, intraday, or RS."
                ),
            },
            "3_single_policy_bundle": (
                "One measurement bundle: materialize Kova as-of/ticker observation "
                "rows with RS, selected fundamental-growth summaries, 13F/intraday "
                "status caveats, and pending outcome placeholders."
            ),
            "4_acceptance_standard": (
                "Accept only if the ledger has rows across multiple as-of dates, "
                "duplicate observation IDs are zero, required fields have coverage, "
                "and before/after strategy metrics are unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "observation_start": OBSERVATION_START,
            "kova_root": repo_rel(KOVA_ROOT),
            "ledger_output": repo_rel(LEDGER_JSONL),
            "required_ledger_fields": REQUIRED_LEDGER_FIELDS,
            "selected_fundamental_components": list(SELECTED_FUNDAMENTAL_COMPONENTS),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "dependencies_validated": success,
            "fields_checked": REQUIRED_LEDGER_FIELDS
            + ["entry_date", "target_price", "planned_entry_date", "planned_exit_date"],
            "field_coverage": summary["field_coverage"],
            "entry_date_present": False,
            "target_price_present": False,
            "entry_date_target_price_note": (
                "Kova observations are not executable candidates. entry_date and "
                "target_price are intentionally null; planned entry/exit placeholders "
                "remain null until a future shared observer defines settlement rules."
            ),
            "ledger_rows": summary["ledger_rows"],
            "asof_date_range": {
                "start": summary["asof_date_start"],
                "end": summary["asof_date_end"],
                "count": summary["asof_date_count"],
            },
            "ticker_count": summary["ticker_count"],
            "failed_reasons": failed,
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter or strategy rule was added.",
        },
        "gate4": {
            "passed": success,
            "decision": decision,
            "failed_reasons": failed,
            "acceptance_checks": {
                "ledger_rows_positive": summary["ledger_rows"] > 0,
                "duplicate_observation_ids_zero": summary["duplicate_observation_ids"] == 0,
                "multi_date_forward_surface": summary["asof_date_count"] >= 5,
                "rs_proxy_rows_present": summary["rs_proxy_ok_rows"] > 0,
                "companyfacts_components_present": (
                    summary["companyfacts_with_selected_components"] > 0
                ),
                "strategy_behavior_changed": False,
            },
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "strategy_rerun_required": False,
            "measurement_repair": True,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "ledger_rows_created": summary["ledger_rows"],
            "pending_outcome_rows": summary["pending_outcome_rows"],
        },
        "ledger_summary": summary,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "replay_only": False,
            "live_ready": False,
            "parity_note": (
                "This experiment writes an experiment-owned observation ledger only. "
                "Existing Kova snapshots are read-only inputs; future alpha promotion "
                "still requires shared daily/backtest wiring or closed replacement-value rows."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Kova now has enough forward daily snapshot files to create a "
                "replayable observation surface, but this remains measurement only: "
                "RS and filed-date fundamentals are present, while 13F and intraday "
                "are recorded as unavailable/skipped caveats."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry Kova RS rank, Companyfacts growth thresholds, 13F "
                "ownership, intraday refresh flags, top-N, hold, cooldown, or notional "
                "from this ledger until rows are closed with replacement value or a "
                "shared helper defines a fixed candidate policy."
            ),
            "new_evidence_required": (
                "Close 20-30 Kova forward observation rows under a predeclared shared "
                "default-off observer, or add PIT historical coverage across the "
                "canonical windows, before any Kova alpha claim."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(LEDGER_JSONL),
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260622-005.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }
    return payload, ledger


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["ledger_summary"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "lane": payload["lane"],
        "owner": payload["owner"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "ledger_summary": {
            "ledger_rows": summary["ledger_rows"],
            "asof_date_start": summary["asof_date_start"],
            "asof_date_end": summary["asof_date_end"],
            "asof_date_count": summary["asof_date_count"],
            "ticker_count": summary["ticker_count"],
            "duplicate_observation_ids": summary["duplicate_observation_ids"],
            "pending_outcome_rows": summary["pending_outcome_rows"],
            "rs_proxy_ok_rows": summary["rs_proxy_ok_rows"],
            "companyfacts_with_selected_components": summary[
                "companyfacts_with_selected_components"
            ],
            "sec13f_status_counts": summary["sec13f_status_counts"],
            "intraday_status_counts": summary["intraday_status_counts"],
            "quality_flag_counts": summary["quality_flag_counts"],
            "sample_observations": summary["sample_observations"][:3],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["ledger_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova multi-source forward observation ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Ledger rows: `{summary['ledger_rows']}`",
            f"- As-of dates: `{summary['asof_date_start']}` to `{summary['asof_date_end']}`",
            f"- Tickers: `{summary['ticker_count']}`",
            f"- Pending outcomes: `{summary['pending_outcome_rows']}`",
            "- Strategy behavior changed: `false`",
            "- Production orders changed: `false`",
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
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LEDGER_JSONL,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any], ledger: list[dict[str, Any]]) -> None:
    write_ledger(LEDGER_JSONL, ledger)
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "ledger_summary": log_record["ledger_summary"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "ledger": repo_rel(LEDGER_JSONL),
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
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload, ledger = build_payload()
    persist(payload, ledger)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "ledger_rows": payload["ledger_summary"]["ledger_rows"],
                "asof_date_start": payload["ledger_summary"]["asof_date_start"],
                "asof_date_end": payload["ledger_summary"]["asof_date_end"],
                "ticker_count": payload["ledger_summary"]["ticker_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
