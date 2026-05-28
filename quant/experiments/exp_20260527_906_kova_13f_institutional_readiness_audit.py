"""exp-20260527-906: Kova 13F institutional readiness audit.

Kova's PDF emphasizes institutional sponsorship and accumulation. This audit
checks whether the default-off Kova SEC 13F sidecar has PIT ticker-mapped
current and prior ownership rows for the accepted exp-20260526-007 VCP top-2
paper trades before any institutional alpha ranking or filter is attempted.

No strategy rule, ranking, sizing, exit, universe, LLM/news path, or live order
path changes here.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    REPO_ROOT,
    SOURCE_EXP007_JSON,
    WINDOWS,
    _audit_open_positions,
    _date10,
    _load_json,
    _now,
    _repo_rel,
    _safe,
    _write_json,
    _write_text,
)


EXPERIMENT_ID = "exp-20260527-906"
STEM = "kova_13f_institutional_readiness_audit"
OUT_JSON_NAME = "exp_20260527_906_kova_13f_institutional_readiness_audit.json"
TRIAL_FAMILY = "kova_13f_institutional_readiness"
CHANGED_VARIABLE = "kova_13f_institutional_ownership_coverage_status_v1"
RULE_VERSION = "kova_13f_institutional_ownership_coverage_status_v1"
SOURCE_VARIANT = "rank2_125"
MIN_COVERED_TRADES = 20
MIN_COVERED_WINDOWS = 2

KOVA_INSTITUTIONAL_DIR = REPO_ROOT / "data" / "kova" / "institutional"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / OUT_JSON_NAME
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    found = False
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for existing in handle:
                if experiment_id not in existing:
                    continue
                try:
                    row = json.loads(existing)
                except json.JSONDecodeError:
                    continue
                if row.get("experiment_id") == experiment_id:
                    found = True
                    break
    if not found:
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(line + "\n")
        return
    temp_path = path.with_name(path.name + f".{EXPERIMENT_ID}.tmp")
    with path.open("r", encoding="utf-8", errors="replace") as src, temp_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        replaced = False
        for existing in src:
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                dst.write(existing.rstrip("\n") + "\n")
                continue
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    dst.write(line + "\n")
                    replaced = True
                continue
            dst.write(existing.rstrip("\n") + "\n")
    try:
        temp_path.replace(path)
    except PermissionError:
        with temp_path.open("r", encoding="utf-8", errors="replace") as src, path.open(
            "w", encoding="utf-8", newline=""
        ) as dst:
            for chunk in src:
                dst.write(chunk)
        try:
            temp_path.unlink(missing_ok=True)
        except PermissionError:
            pass


def _load_source_rank_profile() -> dict[str, Any]:
    source = _load_json(SOURCE_EXP007_JSON)
    variant = source.get("profile_results", {}).get(SOURCE_VARIANT)
    if not isinstance(variant, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} profile result")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} target_trades_by_window")
    return {"source": source, "variant": variant, "target_trades_by_window": trades_by_window}


def _load_institutional_rows() -> tuple[list[dict[str, Any]], list[str]]:
    paths = sorted(KOVA_INSTITUTIONAL_DIR.glob("*.jsonl")) if KOVA_INSTITUTIONAL_DIR.exists() else []
    rows: list[dict[str, Any]] = []
    for path in paths:
        for row in _read_jsonl(path):
            if row.get("surface") == "sec13f_institutional_ownership":
                rows.append({**row, "source_file": _repo_rel(path)})
    return rows, [_repo_rel(path) for path in paths]


def _source_trade_rows(source: dict[str, Any]) -> "OrderedDict[str, list[dict[str, Any]]]":
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label in WINDOWS:
        out[label] = [
            {**row, "window": label}
            for row in source["target_trades_by_window"].get(label, [])
        ]
    return out


def _period_key(row: dict[str, Any]) -> str:
    return _date10(row.get("report_period") or row.get("period_of_report") or row.get("asof_date"))


def _usable_row(row: dict[str, Any]) -> bool:
    return (
        row.get("surface") == "sec13f_institutional_ownership"
        and row.get("status") != "skipped"
        and bool(row.get("ticker"))
        and bool(_date10(row.get("asof_date")))
    )


def _sidecar_summary(rows: list[dict[str, Any]], paths: list[str]) -> dict[str, Any]:
    by_status: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()
    by_mapping: Counter[str] = Counter()
    by_provider: Counter[str] = Counter()
    by_file: Counter[str] = Counter()
    tickers_with_usable_rows: set[str] = set()
    report_periods: set[str] = set()
    for row in rows:
        status = str(row.get("status") or "ok")
        reason = str(row.get("reason") or row.get("error_message") or "")
        mapping_status = str(row.get("ticker_mapping_status") or "")
        provider = str(row.get("provider") or "")
        ticker = str(row.get("ticker") or "").upper()
        period = _period_key(row)
        by_status[status] += 1
        if reason:
            by_reason[reason] += 1
        if mapping_status:
            by_mapping[mapping_status] += 1
        if provider:
            by_provider[provider] += 1
        if row.get("source_file"):
            by_file[str(row["source_file"])] += 1
        if _usable_row(row):
            tickers_with_usable_rows.add(ticker)
            if period:
                report_periods.add(period)
    return {
        "institutional_dir": _repo_rel(KOVA_INSTITUTIONAL_DIR),
        "files": paths,
        "file_count": len(paths),
        "row_count": len(rows),
        "usable_row_count": sum(1 for row in rows if _usable_row(row)),
        "usable_ticker_count": len(tickers_with_usable_rows),
        "usable_report_period_count": len(report_periods),
        "by_status": dict(sorted(by_status.items())),
        "by_reason": dict(sorted(by_reason.items())),
        "by_ticker_mapping_status": dict(sorted(by_mapping.items())),
        "by_provider": dict(sorted(by_provider.items())),
        "by_file": dict(sorted(by_file.items())),
    }


def _aggregate_period(rows: list[dict[str, Any]]) -> dict[str, Any]:
    managers = {
        str(row.get("manager_cik") or row.get("manager_name") or row.get("accession_number") or "")
        for row in rows
        if row.get("manager_cik") or row.get("manager_name") or row.get("accession_number")
    }
    shares = [
        float(row["shares"])
        for row in rows
        if isinstance(row.get("shares"), (int, float)) and row.get("shares") is not None
    ]
    values = [
        float(row["value_usd_thousands"])
        for row in rows
        if isinstance(row.get("value_usd_thousands"), (int, float))
        and row.get("value_usd_thousands") is not None
    ]
    return {
        "row_count": len(rows),
        "manager_count": len(managers),
        "shares_sum": round(sum(shares), 4) if shares else None,
        "value_usd_thousands_sum": round(sum(values), 4) if values else None,
        "has_position_measure": bool(shares or values),
        "asof_dates": sorted({_date10(row.get("asof_date")) for row in rows if row.get("asof_date")}),
    }


def _coverage_for_trade(
    trade: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    ticker_rows = rows_by_ticker.get(ticker, [])
    skipped_rows = [row for row in ticker_rows if row.get("status") == "skipped"]
    eligible_rows = [
        row
        for row in ticker_rows
        if _usable_row(row) and _date10(row.get("asof_date")) <= signal_date
    ]
    by_period: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible_rows:
        period = _period_key(row)
        if period:
            by_period[period].append(row)
    periods = sorted(by_period)
    period_summaries = [
        {"report_period": period, **_aggregate_period(by_period[period])}
        for period in periods[-3:]
    ]
    if len(periods) >= 2 and any(row["has_position_measure"] for row in period_summaries):
        status = "covered_current_and_prior_13f"
    elif len(periods) == 1:
        status = "current_only_no_prior_13f"
    elif skipped_rows and not eligible_rows:
        status = "skipped_only_no_sec13f_zip"
    elif ticker_rows:
        status = "no_pit_13f_rows_asof_signal"
    else:
        status = "no_sidecar_rows_for_ticker"
    return {
        "window": trade.get("window"),
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": _date10(trade.get("entry_date")),
        "coverage_status": status,
        "ticker_sidecar_row_count": len(ticker_rows),
        "ticker_skipped_row_count": len(skipped_rows),
        "eligible_usable_row_count": len(eligible_rows),
        "eligible_report_period_count": len(periods),
        "eligible_report_periods": periods,
        "latest_period_summaries": period_summaries,
        "skip_reasons": sorted(
            {
                str(row.get("reason") or row.get("error_message") or "")
                for row in skipped_rows
                if row.get("reason") or row.get("error_message")
            }
        ),
    }


def _coverage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: Counter[str] = Counter(row["coverage_status"] for row in rows)
    by_window_covered: Counter[str] = Counter()
    by_window_status: dict[str, dict[str, int]] = defaultdict(dict)
    for row in rows:
        window = str(row.get("window") or "")
        status = row["coverage_status"]
        by_window_status[window][status] = by_window_status[window].get(status, 0) + 1
        if status == "covered_current_and_prior_13f":
            by_window_covered[window] += 1
    return {
        "trade_count": len(rows),
        "by_coverage_status": dict(sorted(by_status.items())),
        "by_window_coverage_status": {
            window: dict(sorted(statuses.items()))
            for window, statuses in sorted(by_window_status.items())
        },
        "covered_trade_count": by_status["covered_current_and_prior_13f"],
        "current_only_trade_count": by_status["current_only_no_prior_13f"],
        "covered_windows": sorted(
            window for window, count in by_window_covered.items() if count > 0
        ),
        "covered_trade_count_min": MIN_COVERED_TRADES,
        "covered_window_count_min": MIN_COVERED_WINDOWS,
    }


def _decision(coverage: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    covered = coverage["covered_trade_count"]
    covered_windows = coverage["covered_windows"]
    ready = covered >= MIN_COVERED_TRADES and len(covered_windows) >= MIN_COVERED_WINDOWS
    evidence = {
        "covered_trade_count": covered,
        "covered_trade_count_min": MIN_COVERED_TRADES,
        "covered_windows": covered_windows,
        "covered_window_count": len(covered_windows),
        "covered_window_count_min": MIN_COVERED_WINDOWS,
        "readiness_gate_passed": ready,
    }
    if ready:
        return (
            "observed_only_13f_institutional_data_ready_for_later_replay",
            (
                "The Kova SEC 13F sidecar has enough PIT ticker-mapped current "
                "and prior rows to support a later closed alpha replay. No "
                "strategy change is made here."
            ),
            evidence,
        )
    return (
        "data_gap_13f_institutional_rows_unavailable",
        (
            "The local Kova SEC 13F sidecar does not have enough PIT "
            "ticker-mapped current and prior ownership rows for the accepted "
            "VCP top-2 trade dates. Do not run or promote an institutional "
            "sponsorship rule until those rows exist."
        ),
        evidence,
    )


def _build_payload() -> dict[str, Any]:
    created_at = _now()
    source = _load_source_rank_profile()
    trades_by_window = _source_trade_rows(source)
    trades = [row for rows in trades_by_window.values() for row in rows]
    sidecar_rows, sidecar_paths = _load_institutional_rows()
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sidecar_rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            rows_by_ticker[ticker].append(row)
    coverage_rows = [_coverage_for_trade(trade, rows_by_ticker) for trade in trades]
    sidecar_summary = _sidecar_summary(sidecar_rows, sidecar_paths)
    coverage = _coverage_summary(coverage_rows)
    decision, summary, evidence = _decision(coverage)
    open_positions_audit = _audit_open_positions()
    source_variant = source["variant"]
    source_trade_count = len(trades)
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": created_at,
        "status": "observed_only",
        "registry_lane": "measurement_repair",
        "lane": "measurement_repair",
        "decision": decision,
        "summary": summary,
        "alpha_hypothesis": (
            "Kova institutional sponsorship and 13F accumulation may improve "
            "VCP candidate quality, but it must first have PIT ticker-mapped "
            "current and prior 13F rows for accepted VCP top-2 trades before "
            "any alpha ranking or filter can be tested."
        ),
        "change_type": "measurement_repair_for_alpha_search",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "kova_13f_current_prior_coverage_audit_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "acceptance_standard": (
            "At least 20 accepted VCP trades across at least two canonical "
            "windows must have PIT current and prior ticker-mapped SEC 13F "
            "rows as of signal_date before an institutional sponsorship alpha "
            "replay is attempted."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Institutional sponsorship / 13F accumulation may separate "
                "higher-quality VCP breakouts; this is a measurement repair "
                "readiness pass for a later ranking or filter hypothesis."
            ),
            "1_category": "ranking_candidate_metadata_readiness",
            "1_playbook_alignment": (
                "Aligned with the Kova sidecar requirement: non-OHLCV Kova "
                "surfaces must prove PIT coverage before alpha use."
            ),
            "2_history_check": {
                "exp-20260526-037": "Identified institutional ownership as blocked without a PIT 13F surface.",
                "exp-20260527-001": "Added default-off Kova SEC 13F sidecar, usually skipped without a zip/year/quarter.",
                "exp-20260527-014": "Wired the sidecar into production as default-off data collection only.",
                "exp-20260527-015": "Fundamental+RS proxy was observed only, not promoted.",
                "exp-20260527-902": "Intraday Kova readiness failed because local rows were skipped-only.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Readiness only: >=20 trades and >=2 windows with current+prior "
                "PIT 13F rows. Otherwise record data_gap, do not test/promote alpha."
            ),
            "5_reproducibility": "Script writes JSON, markdown, ticket, log, and JSONL row.",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp007 source sleeve",
            "paper_exit": "10 trading days after signal from exp007 source sleeve",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source_variant.get("expected_value_score_delta"),
                "total_pnl_delta_vs_core": source_variant.get("total_pnl_delta"),
                "target_trade_count": source_trade_count,
                "target_trade_summary": source_variant.get("target_trade_summary"),
            },
            "core_logic_changed": False,
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True,
            "open_positions": open_positions_audit,
            "required_sidecar_fields": [
                "surface",
                "ticker",
                "ticker_mapping_status",
                "asof_date",
                "report_period",
                "shares",
                "value_usd_thousands",
                "status",
                "reason",
            ],
            "sidecar_summary": sidecar_summary,
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "core_survival_changed": False,
            "note": "Read-only data readiness audit.",
        },
        "gate4": {
            "passed": False,
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": "Data readiness audit only; no strategy rule was tested.",
            "decision_evidence": evidence,
        },
        "sidecar_summary": sidecar_summary,
        "coverage_summary": coverage,
        "coverage_rows": coverage_rows,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "metadata_surface_changed": False,
            "read_only_data_audit": True,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260527_906_kova_13f_institutional_readiness_audit.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        },
        "why_not_other_changes": (
            "Did not fetch network data, add SEC 13F zip or CUSIP map inputs, "
            "retune entries/exits, change ranking, sizing, universe, LLM/news, "
            "or live/default orders."
        ),
    }


def _status_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| coverage status | trades |",
        "|---|---:|",
    ]
    for status, count in payload["coverage_summary"]["by_coverage_status"].items():
        lines.append(f"| {status} | {count} |")
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    sidecar = payload["sidecar_summary"]
    coverage = payload["coverage_summary"]
    lines = [
        f"# {EXPERIMENT_ID} Kova 13F Institutional Readiness Audit",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Sidecar",
        "",
        f"- Institutional files: `{sidecar['file_count']}`.",
        f"- Institutional rows: `{sidecar['row_count']}`.",
        f"- Usable PIT rows: `{sidecar['usable_row_count']}`.",
        f"- Status counts: `{sidecar['by_status']}`.",
        f"- Reason counts: `{sidecar['by_reason']}`.",
        f"- Ticker mapping counts: `{sidecar['by_ticker_mapping_status']}`.",
        "",
        "## Trade Coverage",
        "",
        f"- Source trades: `{coverage['trade_count']}`.",
        f"- Current+prior covered trades: `{coverage['covered_trade_count']}`.",
        f"- Covered windows: `{coverage['covered_windows']}`.",
        "",
        *_status_table(payload),
        "",
        "## Gate 4",
        "",
        "No strategy promotion was possible because this is a data-readiness audit.",
        "",
        "```json",
        json.dumps(payload["gate4"], indent=2, sort_keys=True),
        "```",
        "",
        "## Repro",
        "",
        "```powershell",
        payload["repro_command"],
        "```",
        "",
    ]
    return "\n".join(lines)


def _update_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = _load_json(EXPERIMENT_REGISTRY)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    updated = False
    for row in experiments:
        if not isinstance(row, dict):
            continue
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": row.get("owner") or "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
        updated = True
        break
    if not updated:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _existing_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        return _load_json(TICKET_JSON)
    except json.JSONDecodeError:
        return {}


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    existing = _existing_ticket()
    ticket_payload = {
        "experiment_id": payload["experiment_id"],
        "experiment_uid": existing.get("experiment_uid"),
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["registry_lane"],
        "owner": existing.get("owner") or "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": "kova_institutional_sponsorship_data_readiness",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": existing.get("prior_trial_count", 5),
        "nearby_prior_experiments": list(payload["gate_questions"]["2_history_check"].keys()),
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "sidecar_pit_coverage_audit",
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260527_906_kova_13f_institutional_readiness_audit.py")),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
        ],
        "must_not_touch": [
            "quant/backtester.py",
            "quant/run.py",
            "operator_inputs/open_positions.json",
            "data/experiments/exp-20260527-017/broad_market_sector_open_crowding_haircut.json",
        ],
        "locked_variables": [
            "13F sidecar coverage audit only",
            "entries",
            "exits",
            "ranking",
            "sizing",
            "universe",
            "live/default orders",
        ],
        "evaluation_windows": [
            {"start": cfg["start"], "end": cfg["end"]} for cfg in WINDOWS.values()
        ],
        "acceptance_rule": payload["acceptance_standard"],
        "created_at": existing.get("created_at", payload["created_at"]),
        "claimed_at": existing.get("claimed_at"),
        "completed_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": payload["artifacts"]["markdown"],
            "json": payload["artifacts"]["json"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
    }
    _write_json(TICKET_JSON, ticket_payload)
    _write_json(DOCS_TICKET_JSON, ticket_payload)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "sidecar": payload["sidecar_summary"],
                "coverage": payload["coverage_summary"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
