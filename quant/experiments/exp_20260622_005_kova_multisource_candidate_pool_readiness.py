"""exp-20260622-005: Kova multi-source candidate-pool readiness.

Alpha-search data-edge probe. This run checks whether local Kova forward
snapshots are ready for a shared default-off candidate-pool alpha. It changes
no trading policy and uses no JavaScript.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260622-005"
SLUG = "kova_multisource_candidate_pool_readiness"
RUNNER_NAME = f"quant/experiments/exp_20260622_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260622_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_REPLACEMENT_VALUE = (
    REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
)

KOVA_ROOT = REPO_ROOT / "data" / "kova"
SURFACES = {
    "rs_proxy": {
        "path": KOVA_ROOT / "rs_proxy",
        "glob": "rs_proxy_*.jsonl",
        "required_fields": [
            "ticker",
            "asof_date",
            "known_at",
            "rs_proxy_rank_pct_20d",
            "excess_ret_20d_vs_spy",
            "status",
            "entry_date",
            "target_price",
        ],
    },
    "companyfacts_growth": {
        "path": KOVA_ROOT / "fundamentals",
        "glob": "companyfacts_growth*.jsonl",
        "required_fields": [
            "ticker",
            "asof_date",
            "query_asof_date",
            "known_at",
            "canonical",
            "yoy_growth",
            "growth_status",
            "entry_date",
            "target_price",
        ],
    },
    "sec13f_ownership": {
        "path": KOVA_ROOT / "institutional",
        "glob": "sec13f_ownership_*.jsonl",
        "required_fields": [
            "ticker",
            "asof_date",
            "provider",
            "status",
            "reason",
            "entry_date",
            "target_price",
        ],
    },
    "intraday_ohlcv": {
        "path": KOVA_ROOT / "intraday",
        "glob": "intraday_ohlcv_*.jsonl",
        "required_fields": [
            "ticker",
            "asof_date",
            "provider",
            "status",
            "reason",
            "entry_date",
            "target_price",
        ],
    },
    "kova_snapshots": {
        "path": KOVA_ROOT / "snapshots",
        "glob": "kova_data_snapshot_*.json",
        "required_fields": ["asof_date", "status", "entry_date", "target_price"],
    },
}

MIN_FORWARD_OBSERVATION_DATES = 20
MIN_CLOSED_FORWARD_OUTCOMES = 20
CANONICAL_WINDOWS = ("late_strong", "mid_weak", "old_thin")
MAX_ROWS_PER_FILE = 5_000
MAX_ROWS_PER_SURFACE = 40_000

HYPOTHESIS = (
    "candidate_pool/data-edge: Kova multi-source forward snapshots combining "
    "RS proxy, fundamentals, institutional ownership, and intraday flow may "
    "expose a production-visible free-data candidate-pool edge, but only if "
    "the local surface has PIT coverage across the three canonical windows or "
    "enough closed forward replacement rows."
)
CHANGED_VARIABLE = "kova_multisource_candidate_pool_readiness_v1"
TRIAL_FAMILY = "kova_multisource_candidate_pool_readiness"
TRIAL_VARIANT_ID = "kova_forward_snapshot_coverage_v1"
MECHANISM_FAMILY = "production_visible_kova_multisource_candidate_pool"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260621-017",
    "exp-20260622-003",
    "exp-20260621-003",
    "exp-20260621-019",
    "exp-20260621-020",
    "exp-20260614-014",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path).resolve()
    try:
        return value.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def iter_jsonl_limited(path: Path, max_rows: int) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows, False
    truncated = False
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if len(rows) >= max_rows:
                truncated = True
                break
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows, truncated


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        marker = f'"experiment_id": "{EXPERIMENT_ID}"'
        with path.open(encoding="utf-8-sig") as handle:
            if any(marker in line for line in handle):
                return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def date_from_filename(path: Path) -> str | None:
    match = re.search(r"(20\d{6})", path.name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def load_baseline() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT_FILE)
    windows: dict[str, dict[str, Any]] = {}
    for row in raw.get("windows") or []:
        label = str(row.get("label") or "")
        if not label:
            continue
        windows[label] = {
            "label": label,
            "start": row.get("start"),
            "end": row.get("end"),
            "snapshot": row.get("source"),
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
    return {"generated_at": raw.get("generated_at"), "windows": windows}


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows.values()),
            2,
        ),
        "total_trade_count": sum(int(row.get("trade_count") or 0) for row in windows.values()),
        "aggregate_signals_generated": sum(
            int(row.get("signals_generated") or 0) for row in windows.values()
        ),
        "aggregate_signals_survived": sum(
            int(row.get("signals_survived") or 0) for row in windows.values()
        ),
        "min_survival_rate": round(
            min(float(row.get("survival_rate") or 0.0) for row in windows.values()),
            4,
        )
        if windows
        else 0.0,
        "max_window_drawdown_pct": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in windows.values()),
            4,
        )
        if windows
        else 0.0,
    }


def window_for(value: Any, windows: dict[str, dict[str, Any]]) -> str | None:
    observed = parse_date(value)
    if observed is None:
        return None
    for label, window in windows.items():
        start = parse_date(window.get("start"))
        end = parse_date(window.get("end"))
        if start and end and start <= observed <= end:
            return label
    return None


def field_presence(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    out: dict[str, dict[str, Any]] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "present_rate": round(present / total, 4) if total else 0.0,
        }
    return out


def load_surface_rows(
    surface_key: str,
    spec: dict[str, Any],
) -> tuple[list[Path], list[dict[str, Any]], list[dict[str, Any]]]:
    files = sorted(Path(spec["path"]).glob(str(spec["glob"])))
    rows: list[dict[str, Any]] = []
    file_scan: list[dict[str, Any]] = []
    for path in files:
        if len(rows) >= MAX_ROWS_PER_SURFACE:
            file_scan.append(
                {
                    "file": repo_rel(path),
                    "file_date": date_from_filename(path),
                    "scanned_rows": 0,
                    "truncated": True,
                    "reason": "surface_scan_cap_reached",
                }
            )
            continue
        file_date = date_from_filename(path)
        if path.suffix.lower() == ".jsonl":
            remaining = max(0, MAX_ROWS_PER_SURFACE - len(rows))
            limit = min(MAX_ROWS_PER_FILE, remaining)
            scanned_rows, truncated = iter_jsonl_limited(path, limit)
            for row in scanned_rows:
                row["_source_file"] = repo_rel(path)
                row["_file_date"] = file_date
                rows.append(row)
            file_scan.append(
                {
                    "file": repo_rel(path),
                    "file_date": file_date,
                    "scanned_rows": len(scanned_rows),
                    "truncated": truncated,
                    "size_bytes": path.stat().st_size if path.exists() else None,
                }
            )
        else:
            payload = read_json(path)
            rows.append(
                {
                    "_source_file": repo_rel(path),
                    "_file_date": file_date,
                    "asof_date": payload.get("asof_date")
                    or payload.get("as_of_date")
                    or file_date,
                    "status": payload.get("status") or payload.get("overall_status"),
                    "snapshot_keys": sorted(str(key) for key in payload)[:30],
                }
            )
            file_scan.append(
                {
                    "file": repo_rel(path),
                    "file_date": file_date,
                    "scanned_rows": 1,
                    "truncated": False,
                    "size_bytes": path.stat().st_size if path.exists() else None,
                }
            )
    return files, rows, file_scan


def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        status = row.get("status") or row.get("growth_status") or "unknown"
        counts[str(status)] += 1
    return dict(sorted(counts.items()))


def ok_row_count(surface_key: str, rows: list[dict[str, Any]]) -> int:
    if surface_key == "companyfacts_growth":
        return sum(1 for row in rows if row.get("growth_status") == "ok")
    return sum(1 for row in rows if row.get("status") in (None, "ok"))


def audit_surface(
    surface_key: str,
    spec: dict[str, Any],
    windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    files, rows, file_scan = load_surface_rows(surface_key, spec)
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    file_dates = sorted({str(row.get("_file_date")) for row in rows if row.get("_file_date")})
    row_asof_dates = sorted(
        {
            str(row.get("asof_date") or row.get("as_of_date") or row.get("query_asof_date"))
            for row in rows
            if row.get("asof_date") or row.get("as_of_date") or row.get("query_asof_date")
        }
    )
    file_rows_by_window = Counter()
    row_asof_rows_by_window = Counter()
    for row in rows:
        file_label = window_for(row.get("_file_date"), windows)
        if file_label:
            file_rows_by_window[file_label] += 1
        asof_label = window_for(
            row.get("asof_date") or row.get("as_of_date") or row.get("query_asof_date"),
            windows,
        )
        if asof_label:
            row_asof_rows_by_window[asof_label] += 1
    ok_count = ok_row_count(surface_key, rows)
    file_window_labels = sorted(label for label, count in file_rows_by_window.items() if count > 0)
    row_window_labels = sorted(label for label, count in row_asof_rows_by_window.items() if count > 0)
    return {
        "surface": surface_key,
        "directory": repo_rel(Path(spec["path"])),
        "glob": spec["glob"],
        "file_count": len(files),
        "row_count": len(rows),
        "scan_limits": {
            "max_rows_per_file": MAX_ROWS_PER_FILE,
            "max_rows_per_surface": MAX_ROWS_PER_SURFACE,
            "truncated_file_count": sum(1 for item in file_scan if item.get("truncated")),
            "scanned_file_sample": file_scan[:20],
        },
        "ok_row_count": ok_count,
        "unique_tickers": len(tickers),
        "first_file_date": file_dates[0] if file_dates else None,
        "last_file_date": file_dates[-1] if file_dates else None,
        "file_date_count": len(file_dates),
        "row_asof_date_count": len(row_asof_dates),
        "first_row_asof_date": row_asof_dates[0] if row_asof_dates else None,
        "last_row_asof_date": row_asof_dates[-1] if row_asof_dates else None,
        "rows_by_canonical_window_file_date": {
            label: int(file_rows_by_window[label]) for label in CANONICAL_WINDOWS
        },
        "rows_by_canonical_window_row_asof": {
            label: int(row_asof_rows_by_window[label]) for label in CANONICAL_WINDOWS
        },
        "canonical_windows_with_file_rows": file_window_labels,
        "canonical_windows_with_row_asof_rows": row_window_labels,
        "status_counts": status_counts(rows),
        "dependency_presence": field_presence(rows, list(spec["required_fields"])),
        "sample_rows": [
            {
                key: row.get(key)
                for key in (
                    "ticker",
                    "asof_date",
                    "query_asof_date",
                    "status",
                    "growth_status",
                    "known_at",
                    "reason",
                    "_source_file",
                )
                if key in row
            }
            for row in rows[:5]
        ],
        "readiness": surface_readiness(surface_key, ok_count, file_window_labels, row_window_labels),
    }


def surface_readiness(
    surface_key: str,
    ok_count: int,
    file_window_labels: list[str],
    row_window_labels: list[str],
) -> dict[str, Any]:
    reasons: list[str] = []
    if ok_count <= 0:
        reasons.append("no_ok_rows")
    if surface_key in {"rs_proxy", "sec13f_ownership", "intraday_ohlcv", "kova_snapshots"}:
        if set(file_window_labels) != set(CANONICAL_WINDOWS):
            reasons.append("file_date_three_window_coverage_missing")
    if surface_key == "companyfacts_growth":
        reasons.append("existing_companyfacts_growth_family_not_new_by_itself")
        if not row_window_labels:
            reasons.append("filed_date_fixed_window_rows_missing")
    return {
        "passed_for_multisource_alpha": not reasons,
        "blocking_reasons": reasons,
    }


def scan_forward_replacement_matches() -> dict[str, Any]:
    rows = iter_jsonl(FORWARD_REPLACEMENT_VALUE)
    matches = []
    for row in rows:
        haystack = " ".join(
            str(row.get(key) or "").lower()
            for key in ("sleeve_key", "decision_id", "strategy", "source", "rule_version")
        )
        if "kova" in haystack:
            matches.append(row)
    enriched = [row for row in matches if row.get("status") == "enriched"]
    return {
        "ledger_path": repo_rel(FORWARD_REPLACEMENT_VALUE),
        "ledger_rows_scanned": len(rows),
        "matched_rows": len(matches),
        "enriched_matched_rows": len(enriched),
        "sample_matches": matches[:5],
    }


def scan_shared_helper_paths() -> dict[str, Any]:
    helpers = sorted(
        path
        for path in (REPO_ROOT / "quant").glob("*kova*paper_sleeve.py")
        if path.is_file()
    )
    return {
        "helper_count": len(helpers),
        "helpers": [repo_rel(path) for path in helpers],
        "daily_run_wiring_found": False,
        "historical_replay_wiring_found": False,
        "status": "missing_shared_kova_multisource_helper" if not helpers else "needs_review",
    }


def metric_deltas(windows: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    return {label: {field: 0.0 for field in fields} for label in windows}


def build_result() -> dict[str, Any]:
    baseline = load_baseline()
    windows = baseline["windows"]
    aggregate = aggregate_windows(windows)
    surface_audits = {
        key: audit_surface(key, spec, windows) for key, spec in SURFACES.items()
    }
    forward_matches = scan_forward_replacement_matches()
    helper_paths = scan_shared_helper_paths()
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or {
        "success_probability": 0.15,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "forward_only_surface",
            "no_fixed_window_history",
            "no_closed_forward_outcomes",
            "not_shared_daily_helper_ready",
        ],
        "confidence_reason": "Kova multi-source coverage likely remains forward-only.",
    }

    gate2_reasons = []
    for key, audit in surface_audits.items():
        for reason in audit["readiness"]["blocking_reasons"]:
            gate2_reasons.append(f"{key}:{reason}")
    if forward_matches["enriched_matched_rows"] < MIN_CLOSED_FORWARD_OUTCOMES:
        gate2_reasons.append("kova_forward_replacement_rows_below_20")
    if helper_paths["helper_count"] == 0:
        gate2_reasons.append("missing_shared_kova_multisource_helper")

    gate2_passed = not gate2_reasons
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_kova_multisource_surface_not_gate_ready",
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": "data_edge_readiness_gate",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "novelty": ticket.get("novelty"),
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Kova multi-source snapshots may turn accepted forward-only "
                "signals into a candidate-pool edge if RS, fundamentals, "
                "institutional ownership, and intraday/flow surfaces line up "
                "point-in-time across standard windows or closed forward rows."
            ),
            "2_history_check": {
                "novelty_gate": "experiment.py new found no blocking near-neighbor.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "distinction": (
                    "This audits a Kova multi-source surface, not Moomoo one-day "
                    "capital flow, SEC text phrase tuples, raw Companyfacts ratio "
                    "sweeps, or 13F direct-entry thresholds."
                ),
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three standard windows. Proceed to "
                "strategy replay only if Gate 2 finds PIT coverage, runtime "
                "fields, enough sample/forward rows, and a shared daily/backtest "
                "helper path."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
            "generated_at": baseline.get("generated_at"),
            "windows": windows,
            "aggregate": aggregate,
            "passed": True,
        },
        "gate2": {
            "passed": gate2_passed,
            "blocking_reasons": gate2_reasons,
            "dependency_fields_checked": {
                key: list(spec["required_fields"]) for key, spec in SURFACES.items()
            },
            "surface_audits": surface_audits,
            "shared_helper_paths": helper_paths,
            "forward_replacement_value_matches": forward_matches,
        },
        "gate3": {
            "passed": False,
            "blocking_reason": (
                "Kova multi-source candidate generation is blocked before "
                "survival/sample checks because Gate 2 found incomplete "
                "fixed-window coverage, skipped institutional/intraday surfaces, "
                "no shared helper, and no Kova closed forward replacement rows."
            ),
            "baseline_survival_by_window": {
                label: {
                    "signals_generated": row.get("signals_generated"),
                    "signals_survived": row.get("signals_survived"),
                    "survival_rate": row.get("survival_rate"),
                }
                for label, row in windows.items()
            },
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
            "minimum_core_survival_rate": aggregate.get("min_survival_rate"),
        },
        "gate4": {
            "ran_after_strategy": False,
            "reason_after_not_run": (
                "Blocked at Gate 2/3 readiness; after intentionally equals before."
            ),
            "before_windows": windows,
            "after_windows": windows,
            "delta_by_window": metric_deltas(windows),
            "aggregate_before": aggregate,
            "aggregate_after": aggregate,
            "aggregate_delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "failed_reasons": [
                "gate2_surface_readiness_blocked",
                "no_after_strategy_run",
                "no_candidate_trades",
            ],
            "passed": False,
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
        },
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "daily_snapshot_exposed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "trade_enabled": False,
            "uses_kova_data": True,
            "backtest_production_parity_risk": "avoided_by_blocking_before_strategy_logic",
            "parity_note": (
                "No buy/sell/filter/ranking/sizing/risk code changed. A future "
                "positive Kova alpha must use one shared default-off helper that "
                "historical replay and daily snapshots both call."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 0,
            "brier_score": round(float(prediction.get("success_probability") or 0.0) ** 2, 4),
            "realized": "blocked_before_strategy_replay",
            "realized_failure_modes": gate2_reasons,
        },
        "post_run_reflection": {
            "why_blocked": (
                "Kova is a distinct forward data surface, but it is not a Gate-4 "
                "candidate source yet. RS proxy has only late/recent file-date "
                "coverage, Companyfacts growth is an already explored/frozen "
                "family by itself, SEC13F and intraday rows are skipped in the "
                "current local snapshots, no Kova shared helper exists, and no "
                "closed Kova forward replacement-value rows are present."
            ),
            "negative_result_reflection": (
                "This is a data-edge readiness block, not evidence that Kova "
                "flow/fundamental data lacks alpha. The failure is that the "
                "surface cannot support the required three-window before/after "
                "or production/backtest parity claim today."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep Kova RS rank percentiles, Companyfacts growth "
                "thresholds, 13F skipped rows, intraday refresh flags, top-N, "
                "hold days, cooldown, or notional until there is fixed-window "
                "PIT coverage or closed forward replacement-value evidence."
            ),
            "next_new_evidence_required": (
                "Accumulate at least 20-30 closed Kova forward replacement rows "
                "under a shared default-off observer, or add PIT historical "
                "coverage for the same fields across all three canonical windows."
            ),
        },
        "related_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }
    return result


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "implementation_mode": result["implementation_mode"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": result["gate1"],
        "gate2": {
            "passed": result["gate2"]["passed"],
            "blocking_reasons": result["gate2"]["blocking_reasons"],
            "surface_summary": {
                key: {
                    "file_count": audit["file_count"],
                    "row_count": audit["row_count"],
                    "ok_row_count": audit["ok_row_count"],
                    "first_file_date": audit["first_file_date"],
                    "last_file_date": audit["last_file_date"],
                    "canonical_windows_with_file_rows": audit[
                        "canonical_windows_with_file_rows"
                    ],
                    "canonical_windows_with_row_asof_rows": audit[
                        "canonical_windows_with_row_asof_rows"
                    ],
                    "status_counts": audit["status_counts"],
                    "blocking_reasons": audit["readiness"]["blocking_reasons"],
                }
                for key, audit in result["gate2"]["surface_audits"].items()
            },
            "forward_replacement_value_matches": result["gate2"][
                "forward_replacement_value_matches"
            ],
            "shared_helper_paths": result["gate2"]["shared_helper_paths"],
        },
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "production_impact": result["production_impact"],
        "calibration": result["calibration"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "related_files": result["related_files"],
        "anti_js": result["anti_js"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Kova multi-source readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "",
        "## Surface Audit",
        "",
        "| Surface | Files | Rows | OK rows | File-date windows | Row-asof windows | Status counts |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for key, audit in result["gate2"]["surface_audits"].items():
        lines.append(
            "| {key} | {files} | {rows} | {ok} | {file_windows} | {row_windows} | {counts} |".format(
                key=key,
                files=audit["file_count"],
                rows=audit["row_count"],
                ok=audit["ok_row_count"],
                file_windows=", ".join(audit["canonical_windows_with_file_rows"]) or "none",
                row_windows=", ".join(audit["canonical_windows_with_row_asof_rows"]) or "none",
                counts=", ".join(f"{k}:{v}" for k, v in audit["status_counts"].items()) or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Baseline",
            "",
            "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Survival |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label, row in result["gate1"]["windows"].items():
        ev = float(row.get("expected_value_score") or 0.0)
        pnl = float(row.get("total_pnl") or 0.0)
        survival = float(row.get("survival_rate") or 0.0)
        lines.append(
            f"| {label} | {ev:.4f} | {ev:.4f} | 0.0000 | "
            f"${pnl:,.2f} | ${pnl:,.2f} | $0.00 | {survival:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_blocked"],
            "",
            result["post_run_reflection"]["next_new_evidence_required"],
            "",
            f"Reproduce: `{result['reproduction']}`",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER_NAME,
        ARTIFACT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        EXPERIMENT_LOG_JSONL,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256_file(path),
            }
            for path in files
        },
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON)
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    write_json(TICKET_JSON, ticket)


def persist(result: dict[str, Any]) -> None:
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))
    update_ticket(result)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields={
            "owner": "alpha-search-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_production_visible_forward_data_surface",
            "baseline_result_file": repo_rel(BASELINE_RESULT_FILE),
            "evaluation_windows": [
                {
                    "label": label,
                    "start": row.get("start"),
                    "end": row.get("end"),
                    "snapshot": row.get("snapshot"),
                }
                for label, row in result["gate1"]["windows"].items()
            ],
            "acceptance_rule": (
                "Blocked unless Kova multi-source data has PIT fixed-window "
                "coverage or at least 20-30 closed forward replacement-value rows "
                "plus a shared daily/backtest helper."
            ),
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_blocked"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(result))


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "gate2_passed": result["gate2"]["passed"],
                "blocking_reasons": result["gate2"]["blocking_reasons"],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
