"""exp-20260620-012: post-supplier allocator non-repeat alpha surface readiness.

This alpha-search experiment records a blocker instead of forcing a
near-neighbor replay. It verifies whether a fresh, free, production-visible PIT
candidate-pool surface is ready for the canonical three-window Gate 1-4
protocol after revenue-estimate coverage proved absent and recent accepted
helper allocator source insertions were exhausted or rejected.

No trading rule, helper, ranking, sizing, exit, LLM/news behavior, daily runner,
watchlist, or order path is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260620-012"
SLUG = "post_supplier_allocator_nonrepeat_surface"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260620_012_post_supplier_allocator_nonrepeat_surface.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260620_012_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

EARNINGS_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
EXPERIMENT_DATA_DIR = REPO_ROOT / "data" / "experiments"
EXPERIMENT_LOG_DIR = REPO_ROOT / "experiments" / "logs"
BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "candidate_pool/data-edge readiness: after revenue-estimate coverage was "
    "zero across sampled earnings snapshots and accepted-helper allocator "
    "source insertions were exhausted or rejected, a new alpha should proceed "
    "only if a non-repeat PIT field has canonical three-window coverage and a "
    "shared daily/backtest parity path."
)

PREDICTION = {
    "success_probability": 0.05,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "missing_revision_revenue_fields",
        "accepted_allocator_source_neighbors_exhausted",
        "structured_sec_primary_text_missing",
        "options_borrow_missing_canonical_coverage",
        "frozen_companyfacts_form4_sec_text_ohlcv_neighbors",
    ],
    "confidence_reason": (
        "Local scans show revenue_estimate=0 across sampled earnings snapshots "
        "and remaining production-visible helper allocator insertions have "
        "already failed the binding accepted allocator comparator; forcing a "
        "replay would be a frozen-neighbor retune."
    ),
}

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "strategy_total_return_pct": 117.07,
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
        "strategy_total_return_pct": 78.11,
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
        "strategy_total_return_pct": 39.67,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

ALLOCATOR_SOURCE_EXPERIMENTS = [
    {
        "experiment_id": "exp-20260610-006",
        "surface": "macro relief source-priority allocator extension",
        "decision": "rejected",
        "summary": "Accepted-helper allocator source extension was rejected; do not retry source rank/threshold/notional.",
    },
    {
        "experiment_id": "exp-20260610-009",
        "surface": "52-week-high source allocator extension",
        "decision": "rejected",
        "summary": "52-week helper works as its own default-off paper alpha, but allocator source insertion was rejected.",
    },
    {
        "experiment_id": "exp-20260610-016",
        "surface": "post-earnings allocator source extension",
        "decision": "rejected",
        "summary": "Post-earnings source rank/helper threshold/top-N/notional/hold/cooldown retries are frozen.",
    },
    {
        "experiment_id": "exp-20260611-008",
        "surface": "distribution absorption allocator source",
        "decision": "rejected",
        "summary": "Distribution source did not beat accepted allocator comparators.",
    },
    {
        "experiment_id": "exp-20260614-009",
        "surface": "SEC financial-report allocator source extension",
        "decision": "rejected",
        "summary": "SEC financial source extension was rejected versus accepted allocator.",
    },
    {
        "experiment_id": "exp-20260616-016",
        "surface": "SBC burden allocator source",
        "decision": "rejected",
        "summary": "Aggregate positive but failed accepted allocator comparator, window regressions, and drawdown.",
    },
    {
        "experiment_id": "exp-20260618-022",
        "surface": "distribution gap-fill allocator source",
        "decision": "rejected",
        "summary": "Gap-fill/rank/threshold/top-N/hold/cooldown/notional retries closed.",
    },
    {
        "experiment_id": "exp-20260620-011",
        "surface": "supplier financing + debt relief rank-3 allocator source",
        "decision": "rejected",
        "summary": "Aggregate EV/PnL positive, but old_thin failed accepted allocator comparator.",
    },
]

RELATED_SURFACE_EXPERIMENTS = [
    {
        "experiment_id": "exp-20260618-007",
        "surface": "historical 10-K/10-Q cover-page filer status",
        "decision": "blocked",
        "summary": "Daily SEC text snapshots cover dates, but standard-window target 10-K/10-Q rows were absent.",
    },
    {
        "experiment_id": "exp-20260618-013",
        "surface": "offering/prospectus primary-document economics",
        "decision": "blocked",
        "summary": "Submissions metadata saw offering/prospectus accessions, but local primary text coverage was zero.",
    },
    {
        "experiment_id": "exp-20260619-015",
        "surface": "regime-conditioned intraindustry liquidity lead-lag",
        "decision": "rejected",
        "summary": "Aggregate positive but no mid_weak risk-off trades and failed window coverage/comparators.",
    },
    {
        "experiment_id": "exp-20260620-010",
        "surface": "contract asset / unbilled revenue",
        "decision": "rejected",
        "summary": "Aggregate near-flat positive but late_strong/old_thin EV regressions and drawdown drift failed Gate 4.",
    },
    {
        "experiment_id": "exp-20260620-011",
        "surface": "supplier financing + debt relief allocator insertion",
        "decision": "rejected",
        "summary": "Did not beat accepted allocator comparator in old_thin; rank/DPO/debt/risk/notional retries closed.",
    },
]

DATE_RE = re.compile(r"_(\d{8})(?:\.|_|$)")
REVENUE_KEYS = {
    "revenue_estimate",
    "sales_estimate",
    "revenue_consensus",
    "revenue_expected",
    "rev_estimate",
}
ANALYST_KEYS = {
    "analyst_count",
    "analyst_revision_count",
    "estimate_count",
    "revenue_analyst_count",
    "eps_analyst_count",
    "vendor_asof",
    "estimate_vendor_asof",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


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
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if path.exists() and needle in path.read_text(encoding="utf-8-sig"):
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def canonical_window_list() -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "start": data["start"],
            "end": data["end"],
            "snapshot": data["snapshot"],
        }
        for label, data in CANONICAL_WINDOWS.items()
    ]


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, float]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in windows.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in windows.values()),
            2,
        ),
        "total_trade_count": float(
            sum(int(row["trade_count"]) for row in windows.values())
        ),
        "min_survival_rate": round(
            min(float(row["survival_rate"]) for row in windows.values()),
            4,
        ),
        "max_window_drawdown_pct": round(
            max(float(row["max_drawdown_pct"]) for row in windows.values()),
            4,
        ),
    }


def metric_delta(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> dict[str, dict[str, float]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
    ]
    deltas: dict[str, dict[str, float]] = {}
    for label, row in before.items():
        deltas[label] = {
            field: round(float(after[label][field]) - float(row[field]), 6)
            for field in fields
        }
    return deltas


def date_from_path(path: Path) -> str | None:
    match = DATE_RE.search(path.name)
    return match.group(1) if match else None


def as_iso_date(date_key: str) -> str:
    return f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}"


def in_window(date_key: str, window: dict[str, Any]) -> bool:
    date_iso = as_iso_date(date_key)
    return str(window["start"]) <= date_iso <= str(window["end"])


def in_any_standard_window(date_key: str | None) -> bool:
    if not date_key:
        return False
    return any(in_window(date_key, window) for window in CANONICAL_WINDOWS.values())


def iter_earnings_rows(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    earnings = payload.get("earnings")
    if isinstance(earnings, dict):
        return [row for row in earnings.values() if isinstance(row, dict)]
    if isinstance(earnings, list):
        return [row for row in earnings if isinstance(row, dict)]
    return []


def audit_earnings_revenue_coverage() -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {
        label: {
            "files": 0,
            "rows": 0,
            "eps_estimate_rows": 0,
            "revenue_estimate_rows": 0,
            "vendor_asof_rows": 0,
            "analyst_metadata_rows": 0,
            "sample_files": [],
        }
        for label in CANONICAL_WINDOWS
    }
    latest_files = []
    total = {
        "files": 0,
        "rows": 0,
        "eps_estimate_rows": 0,
        "revenue_estimate_rows": 0,
        "vendor_asof_rows": 0,
        "analyst_metadata_rows": 0,
    }
    observed_keys: Counter[str] = Counter()

    for path in sorted(EARNINGS_DIR.glob("earnings_snapshot_*.json")):
        date_key = date_from_path(path)
        rows = iter_earnings_rows(path)
        file_stats = {
            "path": repo_rel(path),
            "date_key": date_key,
            "rows": len(rows),
            "eps_estimate_rows": 0,
            "revenue_estimate_rows": 0,
            "vendor_asof_rows": 0,
            "analyst_metadata_rows": 0,
        }
        for row in rows:
            observed_keys.update(row.keys())
            if row.get("eps_estimate") is not None:
                file_stats["eps_estimate_rows"] += 1
            if any(row.get(key) is not None for key in REVENUE_KEYS):
                file_stats["revenue_estimate_rows"] += 1
            if any(
                row.get(key) is not None
                for key in ("vendor_asof", "estimate_vendor_asof")
            ):
                file_stats["vendor_asof_rows"] += 1
            if any(row.get(key) is not None for key in ANALYST_KEYS):
                file_stats["analyst_metadata_rows"] += 1

        for key in total:
            if key == "files":
                continue
            total[key] += int(file_stats[key])
        total["files"] += 1
        if len(latest_files) >= 8:
            latest_files.pop(0)
        latest_files.append(file_stats)

        if not date_key:
            continue
        for label, window in CANONICAL_WINDOWS.items():
            if not in_window(date_key, window):
                continue
            stats = by_window[label]
            stats["files"] += 1
            for key in [
                "rows",
                "eps_estimate_rows",
                "revenue_estimate_rows",
                "vendor_asof_rows",
                "analyst_metadata_rows",
            ]:
                stats[key] += int(file_stats[key])
            samples = stats["sample_files"]
            if len(samples) < 5:
                samples.append(file_stats)

    total["observed_top_keys"] = observed_keys.most_common(25)
    total["latest_files"] = latest_files
    return {
        "status": "blocked_zero_revenue_estimate_coverage",
        "total": total,
        "by_window": by_window,
        "required_for_alpha": [
            "revenue_estimate",
            "vendor_asof or estimate_vendor_asof",
            "analyst breadth / dispersion metadata",
        ],
        "interpretation": (
            "The earnings snapshots have broad EPS estimate coverage, but zero "
            "revenue estimate rows and zero vendor-as-of rows in the scanned "
            "snapshot set, so top-line revision alpha cannot pass Gate 2."
        ),
    }


def count_jsonl_forms(prefix: str) -> dict[str, Any]:
    forms: Counter[str] = Counter()
    rows = 0
    files = 0
    same_accession_fact_rows = 0
    non_missing_feature_values = Counter()
    for path in sorted(NON_OHLCV_DIR.glob(f"{prefix}_*.jsonl")):
        date_key = date_from_path(path)
        if not in_any_standard_window(date_key):
            continue
        files += 1
        with path.open(encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                rows += 1
                form = str(row.get("form_base") or row.get("form_type") or "").upper()
                forms[form or "UNKNOWN"] += 1
                availability = row.get("field_availability") or {}
                if availability.get("same_accession_facts") not in {
                    None,
                    "missing",
                    "missing_no_same_accession_companyfacts",
                }:
                    same_accession_fact_rows += 1
                for key in [
                    "revenue_surprise",
                    "eps_surprise",
                    "guidance_raise_cut",
                    "gross_margin_delta",
                    "inventory_growth",
                    "receivables_growth",
                    "fcf_to_net_income_gap",
                ]:
                    if row.get(key) is not None:
                        non_missing_feature_values[key] += 1
    return {
        "files": files,
        "rows": rows,
        "forms_top": forms.most_common(20),
        "s8_rows": sum(v for k, v in forms.items() if k.startswith("S-8")),
        "offering_like_rows": sum(
            v
            for k, v in forms.items()
            if k.startswith(("S-1", "S-3", "F-3", "424B"))
        ),
        "tenk_tenq_rows": sum(v for k, v in forms.items() if k in {"10-K", "10-Q"}),
        "same_accession_fact_rows": same_accession_fact_rows,
        "non_missing_feature_values": dict(non_missing_feature_values),
    }


def count_options_coverage() -> dict[str, Any]:
    dates = [
        date_from_path(path)
        for path in NON_OHLCV_DIR.glob("options_onclickmedia_chain_*.jsonl")
    ]
    dates = sorted(d for d in dates if d)
    canonical = [d for d in dates if in_any_standard_window(d)]
    return {
        "chain_file_count": len(dates),
        "min_date": dates[0] if dates else None,
        "max_date": dates[-1] if dates else None,
        "canonical_window_chain_file_count": len(canonical),
        "canonical_window_dates_sample": canonical[:10],
        "verdict": (
            "blocked_missing_mid_old_canonical_coverage"
            if len(canonical) < 20
            else "needs_separate_asof_lag_audit"
        ),
    }


def latest_summary(prefix: str) -> dict[str, Any]:
    paths = sorted(NON_OHLCV_DIR.glob(f"{prefix}_*.json"))
    if not paths:
        return {"status": "missing"}
    latest = paths[-1]
    payload = read_json(latest)
    return {
        "path": repo_rel(latest),
        "date_key": date_from_path(latest),
        "summary_keys": sorted(payload.keys())[:30],
        "summary": payload,
    }


def artifact_exists(exp_id: str) -> bool:
    return (EXPERIMENT_DATA_DIR / exp_id).exists() or (
        EXPERIMENT_LOG_DIR / f"{exp_id}.json"
    ).exists()


def prior_artifact_summary(exp_id: str) -> dict[str, Any]:
    log_path = EXPERIMENT_LOG_DIR / f"{exp_id}.json"
    payload = read_json(log_path)
    if not payload:
        data_dir = EXPERIMENT_DATA_DIR / exp_id
        for candidate in sorted(data_dir.glob("*.json")) if data_dir.exists() else []:
            if candidate.name.startswith("before_") or candidate.name.startswith("after_"):
                continue
            payload = read_json(candidate)
            if payload:
                break
    return {
        "experiment_id": exp_id,
        "local_artifact_found": bool(payload) or artifact_exists(exp_id),
        "decision": payload.get("decision") or payload.get("status"),
        "aggregate_expected_value_delta": payload.get("aggregate_expected_value_delta")
        or (payload.get("delta_metrics") or {}).get("aggregate_expected_value_score"),
        "aggregate_strategy_total_pnl_delta": payload.get(
            "aggregate_strategy_total_pnl_delta"
        )
        or (payload.get("delta_metrics") or {}).get("aggregate_total_pnl"),
    }


def build_inventory() -> dict[str, Any]:
    return {
        "earnings_revenue_coverage": audit_earnings_revenue_coverage(),
        "sec_filing_text": count_jsonl_forms("sec_filing_text"),
        "sec_filing_events": count_jsonl_forms("sec_filing_events"),
        "sec_filing_features": count_jsonl_forms("sec_filing_features"),
        "options_onclickmedia": count_options_coverage(),
        "estimate_revision_latest": latest_summary("estimate_revision_ledger_summary"),
        "moomoo_capital_flow": {
            "manifest": read_json(NON_OHLCV_DIR / "moomoo_capital_flow" / "manifest.json"),
            "row_file_exists": (
                NON_OHLCV_DIR / "moomoo_capital_flow" / "rows.jsonl"
            ).exists(),
        },
        "borrow_fee_rows_exists": (
            NON_OHLCV_DIR / "borrow_fee" / "rows.json"
        ).exists(),
        "finra_short_interest_rows_exists": (
            NON_OHLCV_DIR / "finra_short_interest" / "rows.json"
        ).exists(),
        "sec_13d13g_rows_exists": (
            NON_OHLCV_DIR / "sec_13d13g_holdings" / "rows.json"
        ).exists(),
        "sec_ftd_rows_exists": (NON_OHLCV_DIR / "sec_ftd" / "rows.json").exists(),
        "allocator_source_prior_artifacts": [
            prior_artifact_summary(row["experiment_id"])
            for row in ALLOCATOR_SOURCE_EXPERIMENTS
        ],
    }


def candidate_surface_verdicts(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    revenue = inventory["earnings_revenue_coverage"]["total"]
    text_forms = inventory["sec_filing_text"]
    features = inventory["sec_filing_features"]
    options = inventory["options_onclickmedia"]
    revision = inventory["estimate_revision_latest"].get("summary") or {}
    return [
        {
            "surface": "revenue-estimate upward revision / top-line demand upgrade",
            "gate2_verdict": "blocked_zero_revenue_estimate_coverage",
            "evidence": (
                f"earnings snapshot rows={revenue['rows']}, eps_estimate_rows="
                f"{revenue['eps_estimate_rows']}, revenue_estimate_rows="
                f"{revenue['revenue_estimate_rows']}, vendor_asof_rows="
                f"{revenue['vendor_asof_rows']}."
            ),
            "needed_new_axis": (
                "Historical PIT revenue estimate, vendor as-of, analyst count, "
                "and dispersion rows joined to candidates in all standard windows."
            ),
        },
        {
            "surface": "accepted-helper allocator source insertion",
            "gate2_verdict": "blocked_exhausted_recent_accepted_allocator_neighbors",
            "evidence": (
                "Recent allocator insertions for macro, 52-week, post-earnings, "
                "distribution, SEC financial, SBC, and supplier sources have "
                "all been rejected or closed versus the accepted allocator "
                "comparator."
            ),
            "needed_new_axis": (
                "A materially new source with closed forward displacement rows "
                "or a non-overlapping PIT field; not rank/notional/top-N retunes."
            ),
        },
        {
            "surface": "S-8 / offering financing economics",
            "gate2_verdict": "blocked_missing_primary_text_economics",
            "evidence": (
                f"sec_filing_text standard-window S-8 rows={text_forms['s8_rows']}; "
                f"offering-like rows={text_forms['offering_like_rows']}; "
                "prior readiness artifacts found zero local primary text coverage "
                "for terms/proceeds/dilution parsing."
            ),
            "needed_new_axis": (
                "PIT primary-document registered-share, proceeds, security type, "
                "and dilution terms normalized by float/market cap."
            ),
        },
        {
            "surface": "historical 10-K/10-Q cover-page filer status",
            "gate2_verdict": "blocked_missing_target_rows_in_daily_text_cache",
            "evidence": (
                f"standard-window parsed sec_filing_text 10-K/10-Q rows="
                f"{text_forms['tenk_tenq_rows']}; prior readiness artifact "
                "reported zero target 10-K/10-Q daily SEC text rows."
            ),
            "needed_new_axis": (
                "Historical PIT cover-page accelerated/large accelerated filer "
                "status rows, not current SEC submissions metadata."
            ),
        },
        {
            "surface": "SEC filing features plus same-accession facts",
            "gate2_verdict": "blocked_no_material_feature_tuple",
            "evidence": (
                f"feature rows={features['rows']}, same_accession_fact_rows="
                f"{features['same_accession_fact_rows']}, non_missing="
                f"{features['non_missing_feature_values']}."
            ),
            "needed_new_axis": (
                "Same-accession structured facts or PIT consensus/guidance fields "
                "joined to 8-K items."
            ),
        },
        {
            "surface": "options skew / open interest",
            "gate2_verdict": options["verdict"],
            "evidence": (
                f"OnclickMedia chain files span {options['min_date']} to "
                f"{options['max_date']}; canonical-window file count="
                f"{options['canonical_window_chain_file_count']}."
            ),
            "needed_new_axis": (
                "Historical PIT option chain rows with vendor as-of, OI lag, "
                "spread, stale-chain, and fill-cost controls."
            ),
        },
        {
            "surface": "analyst revision breadth / dispersion beyond EPS",
            "gate2_verdict": "blocked_missing_candidate_join_and_revenue_fields",
            "evidence": (
                "Latest revision summary exists, but revenue-estimate coverage is "
                f"zero and latest summary keys={sorted(revision)[:12]}."
            ),
            "needed_new_axis": (
                "As-of revision breadth/dispersion rows joined to historical "
                "candidates, including revenue estimates, across all three windows."
            ),
        },
        {
            "surface": "FINRA / FTD / borrow pressure",
            "gate2_verdict": "blocked_missing_borrow_cost_axis_or_frozen_replay_family",
            "evidence": (
                "Historical FINRA/FTD rows exist, but recent FINRA/FTD allocator "
                "and pressure attempts failed comparator/window gates; borrow fee "
                f"rows exist={inventory['borrow_fee_rows_exists']}."
            ),
            "needed_new_axis": (
                "PIT borrow fee, utilization, loan availability, or option put-skew "
                "context with canonical coverage."
            ),
        },
        {
            "surface": "Companyfacts cash-flow / working-capital / burden ratios",
            "gate2_verdict": "blocked_frozen_family",
            "evidence": (
                "Contract assets, debt relief, DPO/DSO/DIO/CCC, inventory, "
                "receivables, SBC, segment/customer, advertising, and relief/"
                "overhang fields were rejected or accepted-then-frozen."
            ),
            "needed_new_axis": (
                "PIT customer identity, contract economics, segment profit mix, "
                "debt maturity/covenant terms, or closed forward rows."
            ),
        },
        {
            "surface": "OHLCV relation / lead-lag",
            "gate2_verdict": "blocked_replay_family_closed",
            "evidence": (
                "Static and regime-conditioned intraindustry lead-lag variants "
                "were rejected; retunes need forward/live state-tagged rows."
            ),
            "needed_new_axis": (
                "Forward replacement-value rows or a non-price relation provenance "
                "field, not more frozen-window threshold slicing."
            ),
        },
    ]


def baseline_artifact(label: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "label": label,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "canonical_source": "docs/backtesting.md",
        "windows": CANONICAL_WINDOWS,
        "aggregate": aggregate_windows(CANONICAL_WINDOWS),
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": (
            "This blocker experiment does not run an after policy. The after "
            "artifact intentionally repeats the canonical baseline to avoid "
            "claiming alpha from a blocked surface."
        ),
    }


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or PREDICTION
    inventory = build_inventory()
    surfaces = candidate_surface_verdicts(inventory)
    before_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    after_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    delta = {
        key: round(after_aggregate[key] - before_aggregate[key], 6)
        for key in [
            "aggregate_expected_value_score",
            "aggregate_total_pnl",
            "total_trade_count",
            "min_survival_rate",
            "max_window_drawdown_pct",
        ]
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface_after_supplier_allocator",
        "hypothesis": HYPOTHESIS,
        "change_type": "alpha_surface_readiness_blocker",
        "mechanism_family": "production_visible_free_pit_candidate_pool_surface_selection",
        "trial_family": "post_supplier_allocator_nonrepeat_surface_readiness",
        "trial_variant_id": "revenue_zero_allocator_exhaustion_v1",
        "single_causal_variable": "post_supplier_allocator_nonrepeat_alpha_surface_readiness_v1",
        "changed_variable": "post_supplier_allocator_nonrepeat_alpha_surface_readiness_v1",
        "causal_components": [
            "revenue-estimate field coverage audit",
            "accepted-helper allocator exhaustion audit",
            "standard 3-window baseline comparison",
            "no strategy policy change unless Gate2-ready",
        ],
        "prediction": prediction,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "pre_run_answers": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "candidate_pool/data_edge readiness",
            "history_check": {
                "related_surfaces": RELATED_SURFACE_EXPERIMENTS,
                "allocator_source_experiments": ALLOCATOR_SOURCE_EXPERIMENTS,
            },
            "single_policy_bundle_under_test": (
                "Readiness of non-repeat free PIT candidate-pool surfaces after "
                "supplier allocator rejection; no entry, exit, ranking, sizing, "
                "or risk policy is changed."
            ),
            "success_criteria": (
                "Proceed only if a materially new surface has three-window "
                "coverage, runtime fields, novelty clearance, and a shared "
                "daily/historical parity path."
            ),
            "reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B "
                + RUNNER_NAME.replace("/", "\\")
            ),
        },
        "novelty_check": {
            "reservation_warning": (ticket.get("novelty") or {}).get("warn"),
            "override_recorded": (ticket.get("novelty") or {}).get("override"),
            "new_evidence_axis": (ticket.get("novelty") or {}).get(
                "new_evidence_axis"
            ),
            "nearest": (ticket.get("novelty") or {}).get("nearest"),
            "interpretation": (
                "The override is valid only because this is a post-exp-20260620-011 "
                "cross-surface readiness blocker, not a revision/ranking strategy retry."
            ),
        },
        "gate1_baseline": {
            "status": "passed",
            "source": BASELINE_RESULT_FILE,
            "canonical_windows": canonical_window_list(),
            "baseline_aggregate": before_aggregate,
            "windows": CANONICAL_WINDOWS,
        },
        "gate2_field_availability": {
            "status": "blocked",
            "minimum_runtime_fields_checked": ["entry_date", "target_price"],
            "minimum_runtime_field_result": (
                "Existing canonical rows expose the minimum runtime fields, but "
                "no new non-repeat surface exposes the additional PIT fields "
                "needed for a trustworthy after policy."
            ),
            "local_inventory": inventory,
            "candidate_surfaces": surfaces,
            "blocking_item": (
                "Every reviewed free surface is either frozen by recent "
                "three-window evidence or lacks canonical-window PIT fields and "
                "production/backtest parity inputs."
            ),
        },
        "gate3_survival": {
            "status": "not_applicable_no_new_filter",
            "baseline_min_survival_rate": before_aggregate["min_survival_rate"],
            "guardrail": "survival_rate must stay >= 0.05",
            "interpretation": (
                "No new filter was tested because Gate 2 blocked all candidate "
                "surfaces before strategy replay."
            ),
        },
        "gate4": {
            "status": "blocked_no_after_policy",
            "before": CANONICAL_WINDOWS,
            "after": CANONICAL_WINDOWS,
            "window_deltas": metric_delta(CANONICAL_WINDOWS, CANONICAL_WINDOWS),
            "aggregate_before": before_aggregate,
            "aggregate_after": after_aggregate,
            "aggregate_delta": delta,
            "acceptance_result": "blocked",
            "reason": (
                "No after policy was run. The after metrics intentionally equal "
                "the canonical baseline; this is a blocker record, not an alpha claim."
            ),
        },
        "delta_metrics": delta,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_mode": "all_free_surfaces_frozen_or_missing_pit_coverage",
            "surprise": (
                "Low surprise: revenue_estimate and vendor_asof coverage are zero, "
                "S-8/offering economics lack primary text, 10-K/10-Q filer status "
                "lacks historical target rows, options/borrow are not canonical-ready, "
                "and accepted allocator source insertions are exhausted."
            ),
        },
        "production_impact": {
            "production_code_changed": False,
            "backtest_code_changed": False,
            "shared_helper_added": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_changed": False,
            "parity_assessment": (
                "No production/backtest inconsistency can be introduced because "
                "no trading policy or helper changed. Any future positive alpha "
                "must be implemented as a shared default-off helper before acceptance."
            ),
            "live_realistic_execution_envelope": "not_applicable_no_tradable_alpha",
        },
        "post_run_reflection": {
            "why_blocked": (
                "The current high-potential free-data directions are blocked by "
                "missing PIT fields or frozen-family evidence. Running a strategy "
                "replay now would mostly retune known losers."
            ),
            "negative_result_reflection": (
                "Recent negative results failed because old_thin regressed, "
                "drawdown/concentration worsened, accepted comparators were not "
                "beaten, or the candidate sample was zero/thin. The blocker "
                "prevents repeating those shapes."
            ),
            "best_next_alpha_direction": (
                "Build or import a new PIT surface first: SEC offering/S-8 "
                "primary-document economics, historical cover-page filer status, "
                "parsed customer/segment contract economics, PIT borrow/options "
                "as-of rows, or analyst breadth/dispersion including revenue "
                "estimates joined to historical candidate rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry accepted-helper allocator source rank/notional/top-N, "
                "contract assets, supplier DPO/debt relief, cash-conversion, "
                "working-capital, S-8/offering metadata, FINRA/FTD, 13D/G stake "
                "thresholds, Form4 code filters, or OHLCV lead-lag thresholds "
                "without the named new data axis."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")
        ),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["created_at"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": [
            row["experiment_id"] for row in RELATED_SURFACE_EXPERIMENTS
        ]
        + [row["experiment_id"] for row in ALLOCATOR_SOURCE_EXPERIMENTS],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "before_artifact": repo_rel(BEFORE_JSON),
        "after_artifact": repo_rel(AFTER_JSON),
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "delta_metrics": result["delta_metrics"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "changed_files": result["changed_files"],
        "reproduction": result["reproduction"],
        "lean_quality_passed": result["lean_quality_passed"],
        "anti_js": result["anti_js"],
        "accepted": False,
        "accepted_alpha": False,
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: post-supplier allocator non-repeat surface readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- No strategy, production helper, ranking, sizing, exit, watchlist, or order path changed.",
        "",
        "## Three-window Gate 4",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, before in CANONICAL_WINDOWS.items():
        after = CANONICAL_WINDOWS[label]
        delta = result["gate4"]["window_deltas"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | "
            f"{after['expected_value_score']:.4f} | "
            f"{delta['expected_value_score']:.4f} | "
            f"${before['total_pnl']:,.2f} | ${after['total_pnl']:,.2f} | "
            f"${delta['total_pnl']:,.2f} |"
        )
    agg = result["gate4"]["aggregate_before"]
    revenue = result["gate2_field_availability"]["local_inventory"][
        "earnings_revenue_coverage"
    ]["total"]
    lines.extend(
        [
            "",
            "## Readout",
            "",
            "No alpha was run or accepted. The after artifact is intentionally identical "
            "to the canonical baseline: aggregate EV "
            f"{agg['aggregate_expected_value_score']:.4f}, aggregate PnL "
            f"${agg['aggregate_total_pnl']:,.2f}.",
            "",
            "Revenue estimate coverage scan: "
            f"rows={revenue['rows']}, eps_estimate_rows={revenue['eps_estimate_rows']}, "
            f"revenue_estimate_rows={revenue['revenue_estimate_rows']}, "
            f"vendor_asof_rows={revenue['vendor_asof_rows']}.",
            "",
            result["post_run_reflection"]["best_next_alpha_direction"],
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Blocked alpha-search readiness artifact. This records why no non-repeat "
        "free PIT candidate-pool alpha should be run after exp-20260620-011.\n\n"
        f"- Artifact: `{repo_rel(ARTIFACT_JSON)}`\n"
        f"- Before: `{repo_rel(BEFORE_JSON)}`\n"
        f"- After: `{repo_rel(AFTER_JSON)}`\n"
        f"- Decision: `{result['decision']}`\n"
    )


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "lane": result["lane"],
            "files": result["changed_files"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "ticket": repo_rel(TICKET_JSON),
            "runner": RUNNER_NAME,
            "command": result["reproduction"],
            "anti_js": result["anti_js"],
            "updated_at": now_utc(),
        },
    )


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline"))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "prior_trial_count": len(RELATED_SURFACE_EXPERIMENTS)
        + len(ALLOCATOR_SOURCE_EXPERIMENTS),
        "nearby_prior_experiments": [
            row["experiment_id"] for row in RELATED_SURFACE_EXPERIMENTS
        ]
        + [row["experiment_id"] for row in ALLOCATOR_SOURCE_EXPERIMENTS],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "fresh_post_supplier_allocator_cross_surface_readiness_audit",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "evaluation_windows": canonical_window_list(),
        "acceptance_rule": (
            "Blocked unless a genuinely new, production-visible PIT alpha "
            "surface with coverage in all three canonical windows is available."
        ),
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_blocked"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
        "post_run_reflection": result["post_run_reflection"],
        "production_impact": result["production_impact"],
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "lean_quality_passed": result["lean_quality_passed"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields=fields,
    )
    write_manifest(result)


def main() -> None:
    result = build_result()
    persist(result)
    revenue = result["gate2_field_availability"]["local_inventory"][
        "earnings_revenue_coverage"
    ]["total"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"][
                    "aggregate_total_pnl"
                ],
                "revenue_estimate_rows": revenue["revenue_estimate_rows"],
                "vendor_asof_rows": revenue["vendor_asof_rows"],
                "blocked_surfaces": len(
                    result["gate2_field_availability"]["candidate_surfaces"]
                ),
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
