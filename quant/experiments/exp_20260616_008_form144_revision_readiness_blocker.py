"""exp-20260616-008: Form 144 and revision-breadth readiness blocker.

This is an alpha-search direction-selection experiment, not a strategy replay.
It tests whether the strongest non-repeat free-data candidate-pool directions
are executable with the current repository data. No trading rule, helper,
ranking, sizing, exit, daily runner, LLM/news behavior, watchlist, or order
path is changed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260616-008"
SLUG = "form144_revision_readiness_blocker"
RUNNER_NAME = "quant/experiments/exp_20260616_008_form144_revision_readiness_blocker.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "win_rate": 0.8333,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "sharpe_daily": 1.49,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

CANONICAL_AGGREGATE = {
    "expected_value_score": 7.8941,
    "total_pnl": 234850.99,
    "trade_count": 61,
    "signals_generated": 164,
    "signals_survived": 135,
    "survival_rate": round(135 / 164, 4),
    "min_survival_rate": 0.7925,
    "max_drawdown_pct": 0.1119,
}

REQUIRED_FORM144_FIELDS = [
    "planned_sale_value",
    "planned_sale_shares",
    "securities_to_be_sold",
    "seller_name",
    "holder_role",
    "relationship_to_issuer",
    "sale_pct_float",
    "public_float",
]

REQUIRED_REVISION_FIELDS = [
    "analyst_count_current_qtr",
    "analyst_count_next_qtr",
    "revenue_estimate_current_qtr",
    "revenue_estimate_next_qtr",
    "estimate_dispersion",
    "vendor_asof",
    "fiscal_period",
]

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "missing_parsed_form144_fields",
        "missing_historical_revision_breadth",
        "frozen_near_neighbor",
    ],
    "confidence_reason": (
        "Form 144 absorption produced positive replay evidence but failed the "
        "drawdown gate and requires parsed planned-sale, holder-role, and float "
        "fields. Analyst-revision breadth is also high priority, but historical "
        "snapshots have lacked breadth and dispersion fields, making success "
        "unlikely without a new data surface."
    ),
    "recorded_at": "2026-06-16T05:07:42Z",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: a trustworthy next alpha should use a free-data edge "
        "that expands or improves the candidate pool. The two strongest leads "
        "are Form 144 planned-sale absorption with sale-size/holder/float context "
        "and analyst-revision breadth/dispersion beyond the accepted EPS-only "
        "revision helper."
    ),
    "2_history_check": {
        "exp-20260612-023": (
            "Form 144 sale-notice absorption improved all three windows and "
            "aggregate EV/PnL, but was rejected because max drawdown drift "
            "exceeded the Gate 4 limit. Its reflection requires parsed Form 144 "
            "document fields, holder role, sale size as percent of float, broader "
            "PIT universe, or forward replacement rows."
        ),
        "exp-20260613-013": (
            "Isolated Form 144 retry was rejected on window regression and "
            "drawdown drift; it bans OHLCV/top-N/hold/notional/cooldown sweeps "
            "without new parsed Form 144 evidence."
        ),
        "exp-20260616-002": (
            "Earnings/revision field surface scan found historical snapshots "
            "lack analyst-count, revenue-estimate, dispersion, fiscal-period, "
            "and vendor-as-of fields needed for a non-repeat revision alpha."
        ),
        "exp-20260616-006": (
            "Seasoned new-listing lead was blocked because independent listing, "
            "float, lockup, revision, or sponsorship data was missing."
        ),
        "exp-20260615-029": (
            "Named-counterparty SEC contract economics was rejected with only "
            "one target trade and negative aggregate EV/PnL."
        ),
    },
    "3_single_decision_hypothesis": (
        "nonrepeat_alpha_candidate_readiness_after_form144_revision_surface_check_v1"
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Any strategy launch "
        "must show aggregate EV/PnL improvement, no unacceptable window "
        "regression, survival >=5%, at least 20 paper trades, acceptable "
        "drawdown drift, and production/backtest parity through shared helpers."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260616_008_form144_revision_readiness_blocker.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    line = json.dumps(record, sort_keys=True)
    if not path.exists():
        path.write_text(line + "\n", encoding="utf-8")
        return

    found = False
    lines: list[str] = []
    with path.open(encoding="utf-8") as fh:
        for old in fh:
            stripped = old.rstrip("\n")
            if marker in stripped:
                lines.append(line)
                found = True
            else:
                lines.append(stripped)
    if not found:
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return proc.stdout.strip()


def latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = sorted(directory.glob(pattern))
    return files[-1] if files else None


def build_backtest_snapshot(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "source": "docs/backtesting.md",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "expected_value_score": CANONICAL_AGGREGATE["expected_value_score"],
        "total_pnl": CANONICAL_AGGREGATE["total_pnl"],
        "total_trades": CANONICAL_AGGREGATE["trade_count"],
        "signals_generated": CANONICAL_AGGREGATE["signals_generated"],
        "signals_survived": CANONICAL_AGGREGATE["signals_survived"],
        "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
        "max_drawdown_pct": CANONICAL_AGGREGATE["max_drawdown_pct"],
        "windows": CANONICAL_WINDOWS,
    }


def count_jsonl(path: Path | None, *, max_rows: int | None = None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"exists": False, "source": repo_rel(path) if path else None, "row_count": 0, "sample_keys": []}
    row_count = 0
    sample_keys: list[str] = []
    with path.open(encoding="utf-8-sig") as fh:
        for line in fh:
            if not line.strip():
                continue
            row_count += 1
            if not sample_keys:
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    parsed = {}
                if isinstance(parsed, dict):
                    sample_keys = sorted(parsed)
            if max_rows is not None and row_count >= max_rows:
                break
    return {
        "exists": True,
        "source": repo_rel(path),
        "row_count": row_count,
        "sample_keys": sample_keys,
    }


def scan_jsonl_keys(path: Path | None, *, max_rows: int | None = None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"exists": False, "source": repo_rel(path) if path else None, "row_count": 0, "all_keys": []}
    row_count = 0
    all_keys: set[str] = set()
    form_type_counts: dict[str, int] = {}
    with path.open(encoding="utf-8-sig") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            row_count += 1
            all_keys.update(str(key) for key in row)
            form_type = row.get("form_type")
            if form_type is not None:
                form_type_counts[str(form_type)] = form_type_counts.get(str(form_type), 0) + 1
            if max_rows is not None and row_count >= max_rows:
                break
    return {
        "exists": True,
        "source": repo_rel(path),
        "row_count": row_count,
        "all_keys": sorted(all_keys),
        "form_type_counts": dict(sorted(form_type_counts.items())),
    }


def find_files_by_name(paths: list[Path], keywords: list[str], *, limit: int = 80) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    lowered = [keyword.lower() for keyword in keywords]
    for root in paths:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if any(keyword in name for keyword in lowered):
                matches.append(
                    {
                        "path": repo_rel(path),
                        "bytes": path.stat().st_size,
                        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    }
                )
                if len(matches) >= limit:
                    return {"match_count_limited": len(matches), "matches": matches, "truncated": True}
    return {"match_count_limited": len(matches), "matches": matches, "truncated": False}


def audit_form144_surface() -> dict[str, Any]:
    prior_event_file = REPO_ROOT / "data" / "experiments" / "exp-20260612-023" / "form144_sale_notice_events.jsonl"
    latest_sec_events = latest_file(REPO_ROOT / "data" / "non_ohlcv", "sec_filing_events_*.jsonl")
    prior_profile = scan_jsonl_keys(prior_event_file)
    latest_events_profile = scan_jsonl_keys(latest_sec_events, max_rows=5000)
    available_keys = set(prior_profile.get("all_keys") or []) | set(latest_events_profile.get("all_keys") or [])
    missing_fields = [field for field in REQUIRED_FORM144_FIELDS if field not in available_keys]
    doc_candidates = find_files_by_name(
        [
            REPO_ROOT / "data" / "cache" / "sec" / "form_index",
            REPO_ROOT / "data" / "cache" / "sec" / "filing_text",
            REPO_ROOT / "data" / "non_ohlcv",
        ],
        ["form144", "form_144", "144"],
        limit=80,
    )
    return {
        "prior_form144_event_archive": prior_profile,
        "latest_sec_filing_events_sample": latest_events_profile,
        "required_fields_for_trustworthy_retry": REQUIRED_FORM144_FIELDS,
        "available_field_union": sorted(available_keys),
        "missing_required_fields": missing_fields,
        "sec_cache_file_candidates": doc_candidates,
        "parsed_sale_size_ready": not missing_fields,
        "decision_relevance": (
            "The existing archive is an index/event feed with accession, filing date, ticker, "
            "and form type. It does not expose planned sale size, seller role, relationship, "
            "or percent-of-float fields needed to relaunch the positive Form 144 lead without "
            "repeating the frozen threshold family."
        ),
    }


def audit_earnings_snapshots() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"
    files = sorted(root.glob("earnings_snapshot_*.json"))
    probe_tags = ["20241002", "20250423", "20251023", "20260421", "20260615"]
    probes: dict[str, Any] = {}
    aggregate_field_counts: dict[str, int] = {}
    aggregate_rows = 0
    missing_fields: set[str] = set(REQUIRED_REVISION_FIELDS)
    for tag in probe_tags:
        path = root / f"earnings_snapshot_{tag}.json"
        payload = read_json(path, {})
        earnings = payload.get("earnings") if isinstance(payload, dict) else {}
        earnings = earnings if isinstance(earnings, dict) else {}
        field_counts: dict[str, int] = {}
        for row in earnings.values():
            if not isinstance(row, dict):
                continue
            aggregate_rows += 1
            for key in row:
                field_counts[key] = field_counts.get(key, 0) + 1
                aggregate_field_counts[key] = aggregate_field_counts.get(key, 0) + 1
                missing_fields.discard(key)
        probes[tag] = {
            "exists": path.exists(),
            "source": repo_rel(path),
            "ticker_rows": len(earnings),
            "field_counts": dict(sorted(field_counts.items())),
            "required_fields_present": {
                field: field in field_counts for field in REQUIRED_REVISION_FIELDS
            },
        }
    return {
        "snapshot_dir": repo_rel(root),
        "file_count": len(files),
        "first_snapshot": repo_rel(files[0]) if files else None,
        "last_snapshot": repo_rel(files[-1]) if files else None,
        "probe_snapshots": probes,
        "aggregate_probe_rows": aggregate_rows,
        "aggregate_probe_field_counts": dict(sorted(aggregate_field_counts.items())),
        "required_fields_for_nonrepeat_revision_alpha": REQUIRED_REVISION_FIELDS,
        "missing_required_fields": sorted(missing_fields),
        "decision_relevance": (
            "Historical snapshots cover the canonical dates but expose EPS estimate, "
            "days-to-earnings, last actual EPS, and surprise history rather than "
            "analyst-count breadth, revenue-estimate velocity, dispersion, vendor-as-of, "
            "or stable fiscal-period fields."
        ),
    }


def audit_revision_surface() -> dict[str, Any]:
    latest_summary = latest_file(REPO_ROOT / "data" / "non_ohlcv", "estimate_revision_ledger_summary_*.json")
    latest_ledger = latest_file(REPO_ROOT / "data" / "non_ohlcv", "estimate_revision_ledger_*.jsonl")
    ledger_profile = scan_jsonl_keys(latest_ledger, max_rows=5000)
    summary = read_json(latest_summary, {}) if latest_summary else {}
    missing_latest_fields = [
        field for field in REQUIRED_REVISION_FIELDS if field not in set(ledger_profile.get("all_keys") or [])
    ]
    return {
        "latest_revision_summary_path": repo_rel(latest_summary) if latest_summary else None,
        "latest_revision_summary": summary,
        "latest_revision_ledger": ledger_profile,
        "historical_earnings_snapshot_field_audit": audit_earnings_snapshots(),
        "required_fields_for_nonrepeat_revision_alpha": REQUIRED_REVISION_FIELDS,
        "missing_required_fields_in_latest_ledger": missing_latest_fields,
        "forward_matched_candidate_rows": int(summary.get("matched_candidate_rows") or 0),
        "decision_relevance": (
            "The latest forward ledger has useful EPS-delta scaffolding but zero matched "
            "candidate rows in the current summary, while the historical snapshots still "
            "lack the breadth and dispersion fields needed for a three-window replay."
        ),
    }


def summarize_related_experiment(experiment_id: str) -> dict[str, Any]:
    path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    log = read_json(path, {})
    if not isinstance(log, dict) or not log:
        return {"experiment_id": experiment_id, "exists": False, "log": repo_rel(path)}
    gate4 = log.get("gate4") if isinstance(log.get("gate4"), dict) else {}
    delta = log.get("delta_metrics") if isinstance(log.get("delta_metrics"), dict) else {}
    return {
        "experiment_id": experiment_id,
        "exists": True,
        "log": repo_rel(path),
        "status": log.get("status"),
        "decision": log.get("decision"),
        "changed_variable": log.get("changed_variable"),
        "accepted": bool(log.get("accepted") or log.get("accepted_alpha")),
        "aggregate_expected_value_delta": (
            delta.get("aggregate_expected_value_score")
            or gate4.get("aggregate_ev_delta")
            or log.get("aggregate_expected_value_delta")
        ),
        "aggregate_pnl_delta": (
            delta.get("aggregate_total_pnl")
            or gate4.get("aggregate_pnl_delta")
            or log.get("aggregate_strategy_total_pnl_delta")
        ),
        "gate4_passed": gate4.get("passed"),
        "target_trade_count": gate4.get("target_trade_count"),
        "failed_reasons": gate4.get("failed_reasons"),
        "post_run_reflection": log.get("post_run_reflection", {}),
    }


def build_gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    for label, before_row in before["windows"].items():
        after_row = after["windows"][label]
        by_window[label] = {
            "before_expected_value_score": before_row["expected_value_score"],
            "after_expected_value_score": after_row["expected_value_score"],
            "delta_expected_value_score": round(
                after_row["expected_value_score"] - before_row["expected_value_score"], 4
            ),
            "before_total_pnl": before_row["total_pnl"],
            "after_total_pnl": after_row["total_pnl"],
            "delta_total_pnl": round(after_row["total_pnl"] - before_row["total_pnl"], 2),
            "before_trade_count": before_row["trade_count"],
            "after_trade_count": after_row["trade_count"],
            "delta_trade_count": after_row["trade_count"] - before_row["trade_count"],
            "before_survival_rate": before_row["survival_rate"],
            "after_survival_rate": after_row["survival_rate"],
            "delta_survival_rate": round(after_row["survival_rate"] - before_row["survival_rate"], 4),
            "before_max_drawdown_pct": before_row["max_drawdown_pct"],
            "after_max_drawdown_pct": after_row["max_drawdown_pct"],
            "delta_max_drawdown_pct": round(after_row["max_drawdown_pct"] - before_row["max_drawdown_pct"], 4),
        }
    return {
        "applicable": False,
        "passed": False,
        "decision": "blocked_no_gate4_ready_independent_data_surface",
        "reason": (
            "No strategy policy was launched because the required independent Form 144 "
            "and revision-breadth data fields are absent. Before/after are intentionally "
            "identical across the canonical three windows."
        ),
        "aggregate_before": {
            "expected_value_score": before["expected_value_score"],
            "total_pnl": before["total_pnl"],
            "trade_count": before["total_trades"],
            "survival_rate": before["survival_rate"],
            "max_drawdown_pct": before["max_drawdown_pct"],
        },
        "aggregate_after": {
            "expected_value_score": after["expected_value_score"],
            "total_pnl": after["total_pnl"],
            "trade_count": after["total_trades"],
            "survival_rate": after["survival_rate"],
            "max_drawdown_pct": after["max_drawdown_pct"],
        },
        "aggregate_ev_delta": round(after["expected_value_score"] - before["expected_value_score"], 4),
        "aggregate_pnl_delta": round(after["total_pnl"] - before["total_pnl"], 2),
        "target_trade_count": 0,
        "target_trade_count_min": 20,
        "survival_guard_passed": before["survival_rate"] >= 0.05,
        "minimum_core_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        "by_window": by_window,
    }


def build_candidate_reviews(
    form144: dict[str, Any],
    revision: dict[str, Any],
    related: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "candidate": "form144_planned_sale_absorption_retry",
            "alpha_hypothesis": (
                "Public Form 144 sale notices may identify supply overhangs that "
                "are being absorbed by strong liquid leadership, but only sale-size, "
                "seller-role, and float context can distinguish real absorption from "
                "generic index-event timing."
            ),
            "decision": "blocked_missing_parsed_sale_size_role_float_fields",
            "current_evidence": {
                "form144_surface": form144,
                "positive_prior": related["exp-20260612-023"],
                "negative_retry": related["exp-20260613-013"],
            },
            "why_not_run": (
                "The current files contain event/index rows but not planned-sale "
                "shares or value, holder role, relationship to issuer, or sale as "
                "percent of float. A new replay would therefore be the same frozen "
                "near-neighbor family that already failed drawdown gates."
            ),
            "retry_requires": (
                "Parse Form 144 documents into PIT planned-sale shares/value, holder "
                "role, relationship, public float, and sale_pct_float; then implement "
                "a shared default-off helper with historical replay and daily snapshot."
            ),
        },
        {
            "candidate": "analyst_revision_breadth_dispersion",
            "alpha_hypothesis": (
                "Revision breadth, analyst-count confirmation, revenue-estimate "
                "velocity, and dispersion compression could rank expectation "
                "underreaction better than the accepted EPS-only revision helper."
            ),
            "decision": "blocked_missing_historical_breadth_dispersion_fields",
            "current_evidence": {
                "revision_surface": revision,
                "field_surface_prior": related["exp-20260616-002"],
            },
            "why_not_run": (
                "Historical earnings snapshots expose only EPS-style fields in the "
                "canonical windows, while the forward revision ledger currently has "
                "zero matched candidate rows. Running EPS-only deltas again would "
                "repeat an accepted/frozen helper rather than test a new alpha."
            ),
            "retry_requires": (
                "Persist analyst counts, revenue estimates, estimate dispersion, "
                "vendor_asof, and fiscal period with all-window or sufficient forward "
                "replacement coverage."
            ),
        },
        {
            "candidate": "sec_named_counterparty_contract_economics",
            "alpha_hypothesis": (
                "Structured customer/supplier identity and contract economics could "
                "beat generic SEC text event signals."
            ),
            "decision": "blocked_recent_negative_and_sparse",
            "current_evidence": related["exp-20260615-029"],
            "why_not_run": (
                "The latest named-counterparty replay had only one target trade and "
                "negative aggregate EV/PnL, so another text-span variant would be "
                "sparse and untrustworthy without a materially new structured field."
            ),
            "retry_requires": (
                "A persisted PIT contract-economics field with named counterparty, "
                "value, duration, renewal, margin, or backlog linkage."
            ),
        },
    ]


def build_result() -> dict[str, Any]:
    before = build_backtest_snapshot("before_baseline")
    after = build_backtest_snapshot("after_no_strategy_change")
    gate4 = build_gate4(before, after)
    form144 = audit_form144_surface()
    revision = audit_revision_surface()
    related = {
        exp_id: summarize_related_experiment(exp_id)
        for exp_id in [
            "exp-20260612-023",
            "exp-20260613-013",
            "exp-20260616-002",
            "exp-20260616-006",
            "exp-20260615-029",
            "exp-20260615-024",
        ]
    }
    candidate_reviews = build_candidate_reviews(form144, revision, related)
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": "rejected",
        "decision": "blocked_no_trustworthy_nonrepeat_form144_or_revision_alpha_surface",
        "accepted": False,
        "accepted_alpha": False,
        "lane": "alpha_search",
        "change_type": "alpha_direction_selection",
        "mechanism_family": "candidate_pool_data_edge",
        "trial_family": "form144_revision_data_readiness",
        "trial_variant_id": "v1",
        "changed_variable": "nonrepeat_alpha_candidate_readiness_after_form144_revision_surface_check_v1",
        "single_causal_variable": "nonrepeat_alpha_candidate_readiness_after_form144_revision_surface_check_v1",
        "causal_components": [
            "history_near_neighbor_check",
            "form144_field_inventory",
            "revision_breadth_field_inventory",
            "gate1_to_gate4_no_strategy_baseline_framing",
        ],
        "hypothesis": (
            "Form 144 planned-sale absorption and analyst-revision breadth remain "
            "the strongest free-data candidate-pool directions, but they are "
            "executable only if independent PIT sale-size/role/float or historical "
            "breadth/dispersion fields exist."
        ),
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "prediction": PREDICTION,
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": gate4["aggregate_ev_delta"],
            "aggregate_total_pnl": gate4["aggregate_pnl_delta"],
            "trade_count": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_delta": 0.0,
        },
        "gate1": {
            "baseline_result_file": BASELINE_RESULT_FILE,
            "aggregate_expected_value_score": before["expected_value_score"],
            "aggregate_total_pnl": before["total_pnl"],
            "windows": CANONICAL_WINDOWS,
        },
        "gate2": {
            "passed": False,
            "reason": "No executable rows were emitted because independent data readiness failed.",
            "required_runtime_fields_for_future_launch": ["entry_date", "target_price"],
        },
        "gate3": {
            "passed": before["survival_rate"] >= 0.05,
            "baseline_survival_rate": before["survival_rate"],
            "minimum_window_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
            "note": "No filter was added; baseline survival remains safely above the 5% hard stop.",
        },
        "gate4": gate4,
        "data_surface_audit": {
            "form144": form144,
            "revision_breadth": revision,
        },
        "related_experiments": related,
        "candidate_reviews": candidate_reviews,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "trade_enabled_changed": False,
            "replay_only": False,
            "reason": (
                "This runner changes no production or backtest trading path. A future "
                "positive alpha must be implemented shared-paper-first with the same "
                "helper used by historical replay and daily default-off snapshots."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_outcome": "blocked_rejected",
            "prediction_direction": "correct_low_probability",
            "surprise_note": (
                "The blocker matched the pre-run failure modes: Form 144 lacks parsed "
                "sale-size/role/float fields and revision breadth lacks historical "
                "breadth/dispersion coverage."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The alpha idea is directionally attractive, but the repository only "
                "has Form 144 index/event rows and EPS-centric revision snapshots. "
                "Those surfaces cannot isolate the promised causal edge, so launching "
                "a strategy would measure a frozen near-neighbor rather than a new "
                "candidate-pool alpha."
            ),
            "if_negative_reflection": (
                "This negative result is not evidence that Form 144 absorption or "
                "revision breadth lacks alpha; it is evidence that the current local "
                "fields cannot evaluate those alphas cleanly under Gate 1-4."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry Form 144 top-N, OHLCV gates, hold days, notional, "
                "cooldown, liquidity, or price-confirmation variants. Do not retry "
                "EPS-only revision thresholds, DTE windows, or revision-direction "
                "rankers. Do not relaunch SEC text counterparty variants without a "
                "new structured economics field."
            ),
            "new_evidence_required": (
                "Required new evidence is PIT parsed Form 144 planned-sale shares or "
                "value, holder role, relationship-to-issuer, public float and "
                "sale_pct_float, or historical/forward analyst-count, revenue-estimate, "
                "dispersion, vendor_asof, and fiscal-period coverage with closed "
                "candidate outcomes."
            ),
            "best_next_alpha_direction": (
                "Build a free-data candidate-pool edge by parsing Form 144 document "
                "sale-size and holder-role fields, or by backfilling analyst revision "
                "breadth/dispersion with PIT timestamps. Only after that should a "
                "shared default-off paper alpha run the three-window Gate 1-4 test."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(ARTIFACT_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "repro_commands": [
            ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260616_008_form144_revision_readiness_blocker.py",
            ".venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
    }
    return result


def build_markdown(result: dict[str, Any]) -> str:
    rows = result["gate4"]["by_window"]
    runner_path = RUNNER_NAME.replace("/", "\\")
    lines = [
        f"# {EXPERIMENT_ID}: Form 144 / Revision Readiness Blocker",
        "",
        "## Decision",
        "",
        f"`{result['decision']}`. No strategy code or production path changed.",
        "",
        "## Alpha Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## History Check",
        "",
    ]
    for exp_id, summary in result["related_experiments"].items():
        lines.append(f"- `{exp_id}`: `{summary.get('decision')}`; EV delta `{summary.get('aggregate_expected_value_delta')}`; PnL delta `{summary.get('aggregate_pnl_delta')}`.")
    lines.extend(
        [
            "",
            "## Gate 1-4",
            "",
            f"- Gate 1: baseline `{BASELINE_RESULT_FILE}`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.",
            "- Gate 2: failed intentionally; no executable rows because required independent fields are missing. Future rows still require `entry_date` and `target_price`.",
            "- Gate 3: no filter added; baseline survival `0.8232`, minimum window survival `0.7925`.",
            "- Gate 4: no strategy launched; before/after are unchanged in all canonical windows.",
            "",
            "| window | EV before | EV after | EV delta | PnL before | PnL after | PnL delta | trades before | trades after |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label, row in rows.items():
        lines.append(
            f"| {label} | {row['before_expected_value_score']:.4f} | "
            f"{row['after_expected_value_score']:.4f} | {row['delta_expected_value_score']:.4f} | "
            f"{row['before_total_pnl']:.2f} | {row['after_total_pnl']:.2f} | "
            f"{row['delta_total_pnl']:.2f} | {row['before_trade_count']} | {row['after_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Blocker Proof",
            "",
            f"- Form 144 missing fields: `{', '.join(result['data_surface_audit']['form144']['missing_required_fields'])}`.",
            f"- Revision historical missing fields: `{', '.join(result['data_surface_audit']['revision_breadth']['historical_earnings_snapshot_field_audit']['missing_required_fields'])}`.",
            f"- Latest revision matched candidate rows: `{result['data_surface_audit']['revision_breadth']['forward_matched_candidate_rows']}`.",
            "",
            "## Production / Backtest Parity",
            "",
            "No production/backtest behavior changed. A future positive must use a shared default-off helper in both historical replay and daily snapshots.",
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            "## Forbidden Near-Neighbor Retry",
            "",
            result["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## New Evidence Required",
            "",
            result["post_run_reflection"]["new_evidence_required"],
            "",
            "## Repro",
            "",
            f"```powershell\n.\\.venv\\Scripts\\python.exe -B {runner_path}\n```",
            "",
        ]
    )
    return "\n".join(lines)


def build_card(result: dict[str, Any]) -> str:
    return f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "rejected"
lane: "alpha_search"
change_type: "alpha_direction_selection"
mechanism_family: "candidate_pool_data_edge"
trial_family: "form144_revision_data_readiness"
trial_variant_id: "v1"
changed_variable: "nonrepeat_alpha_candidate_readiness_after_form144_revision_surface_check_v1"
completed_at: "{result["timestamp"]}"
tags:
  - "alpha_search"
  - "rejected"
  - "alpha_direction_selection"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Blocked Form 144 / revision-breadth alpha launch because the independent PIT fields required for a non-repeat candidate-pool test are absent. No strategy code changed and no production/backtest behavior changed.

## Hypothesis

{result["hypothesis"]}

## Gate 1-4

- Gate 1: baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3: no filter added; baseline survival `0.8232`.
- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; strategy launch rejected.

## Decision

`{result["decision"]}`

## Why Blocked

{result["post_run_reflection"]["why_result_happened"]}

## Best Next Direction

{result["post_run_reflection"]["best_next_alpha_direction"]}

## Closeout

- Artifact: `{repo_rel(ARTIFACT_JSON)}`
- Before artifact: `{repo_rel(BEFORE_JSON)}`
- After artifact: `{repo_rel(AFTER_JSON)}`
- Markdown artifact: `{repo_rel(ARTIFACT_MD)}`
- Log: `{repo_rel(LOG_JSON)}`
- Runner: `{RUNNER_NAME}`
- No JavaScript was used.
"""


def write_manifest(result: dict[str, Any]) -> None:
    files = {
        "runner": REPO_ROOT / RUNNER_NAME,
        "artifact_json": ARTIFACT_JSON,
        "before_json": BEFORE_JSON,
        "after_json": AFTER_JSON,
        "artifact_md": ARTIFACT_MD,
        "log": LOG_JSON,
        "card": CARD_MD,
        "ticket": TICKET_JSON,
        "experiment_log": EXPERIMENT_LOG_JSONL,
        "registry": REGISTRY_JSON,
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "decision": result["decision"],
        "git": {
            "branch": git_value("branch", "--show-current"),
            "commit": git_value("rev-parse", "HEAD"),
            "dirty": bool(git_value("status", "--porcelain")),
        },
        "files": {
            key: {"path": repo_rel(value), "exists": value.exists(), "sha256": sha256(value)}
            for key, value in files.items()
        },
    }
    write_json(MANIFEST_JSON, manifest)


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, result["before_metrics"])
    write_json(AFTER_JSON, result["after_metrics"])
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(ARTIFACT_MD, build_markdown(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, result)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before_result_file": repo_rel(BEFORE_JSON),
        "after_result_file": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": [
            "exp-20260612-023",
            "exp-20260613-013",
            "exp-20260616-002",
            "exp-20260616-006",
            "exp-20260615-029",
            "exp-20260615-024",
        ],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "post_run_reflection": result["post_run_reflection"],
        "gate4": result["gate4"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=registry_result,
        status="rejected",
        fields=fields,
    )
    write_text(CARD_MD, build_card(result))
    write_manifest(result)


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev_delta": result["delta_metrics"]["aggregate_expected_value_score"],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "form144_missing_fields": result["data_surface_audit"]["form144"]["missing_required_fields"],
                "revision_missing_historical_fields": result["data_surface_audit"]["revision_breadth"][
                    "historical_earnings_snapshot_field_audit"
                ]["missing_required_fields"],
                "best_next_alpha_direction": result["post_run_reflection"]["best_next_alpha_direction"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
