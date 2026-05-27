"""exp-20260527-017: Kova intraday entry readiness audit.

Kova's PDF emphasizes 15-minute and 60-minute contraction/pocket-pivot context
for early or precise entries. This audit checks whether the local default-off
Kova sidecar has PIT intraday rows for the accepted exp-20260526-007 VCP top-2
paper trades before any intraday alpha replay is attempted.

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
    _flatten,
    _load_json,
    _now,
    _repo_rel,
    _safe,
    _write_json,
    _write_text,
)


EXPERIMENT_ID = "exp-20260527-902"
STEM = "kova_intraday_entry_readiness_audit"
TRIAL_FAMILY = "kova_intraday_data_readiness"
CHANGED_VARIABLE = "kova_15m_60m_intraday_coverage_status_v1"
RULE_VERSION = "kova_15m_60m_intraday_coverage_status_v1"
SOURCE_VARIANT = "rank2_125"
REQUIRED_INTERVALS = ("15min", "60min")
MIN_COVERED_TRADES = 20
MIN_COVERED_WINDOWS = 2

KOVA_INTRADAY_DIR = REPO_ROOT / "data" / "kova" / "intraday"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
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
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _load_source_rank_profile() -> dict[str, Any]:
    source = _load_json(SOURCE_EXP007_JSON)
    variant = source.get("profile_results", {}).get(SOURCE_VARIANT)
    if not isinstance(variant, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} profile result")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} target_trades_by_window")
    return {"source": source, "variant": variant, "target_trades_by_window": trades_by_window}


def _load_intraday_rows() -> tuple[list[dict[str, Any]], list[str]]:
    paths = sorted(KOVA_INTRADAY_DIR.glob("*.jsonl")) if KOVA_INTRADAY_DIR.exists() else []
    rows: list[dict[str, Any]] = []
    for path in paths:
        for row in _read_jsonl(path):
            rows.append({**row, "source_file": _repo_rel(path)})
    return rows, [_repo_rel(path) for path in paths]


def _timestamp_date(row: dict[str, Any]) -> str:
    for key in ("timestamp", "datetime", "time", "bar_time"):
        value = row.get(key)
        if value:
            return str(value)[:10]
    return _date10(row.get("asof_date"))


def _source_trade_rows(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label in WINDOWS:
        out[label] = [
            {**row, "window": label}
            for row in source["target_trades_by_window"].get(label, [])
        ]
    return out


def _sidecar_summary(rows: list[dict[str, Any]], paths: list[str]) -> dict[str, Any]:
    by_status: Counter[str] = Counter()
    by_reason: Counter[str] = Counter()
    by_interval: Counter[str] = Counter()
    by_ticker_status: Counter[str] = Counter()
    for row in rows:
        status = str(row.get("status") or "")
        reason = str(row.get("reason") or row.get("error_message") or "")
        interval = str(row.get("interval") or "")
        ticker = str(row.get("ticker") or "").upper()
        by_status[status] += 1
        if reason:
            by_reason[reason] += 1
        if interval:
            by_interval[interval] += 1
        if ticker:
            by_ticker_status[f"{ticker}:{status}"] += 1
    return {
        "intraday_dir": _repo_rel(KOVA_INTRADAY_DIR),
        "files": paths,
        "file_count": len(paths),
        "row_count": len(rows),
        "by_status": dict(sorted(by_status.items())),
        "by_reason": dict(sorted(by_reason.items())),
        "by_interval": dict(sorted(by_interval.items())),
        "unique_ticker_status_count": len(by_ticker_status),
    }


def _coverage_for_trade(
    trade: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    ticker_rows = rows_by_ticker.get(ticker, [])
    ok_rows = [row for row in ticker_rows if row.get("status") == "ok"]
    skipped_rows = [row for row in ticker_rows if row.get("status") == "skipped"]
    interval_counts: dict[str, int] = {}
    for interval in REQUIRED_INTERVALS:
        interval_counts[interval] = sum(
            1
            for row in ok_rows
            if str(row.get("interval") or "") == interval
            and _timestamp_date(row) == signal_date
        )
    covered_intervals = [
        interval for interval, count in interval_counts.items() if count > 0
    ]
    if len(covered_intervals) == len(REQUIRED_INTERVALS):
        status = "covered_15m_60m_signal_date"
    elif covered_intervals:
        status = "partial_intraday_signal_date"
    elif skipped_rows and not ok_rows:
        status = "skipped_only_no_intraday_bars"
    elif ticker_rows:
        status = "no_signal_date_intraday_bars"
    else:
        status = "no_sidecar_rows_for_ticker"
    return {
        "window": trade.get("window"),
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": _date10(trade.get("entry_date")),
        "coverage_status": status,
        "covered_intervals": covered_intervals,
        "signal_date_ok_rows_by_interval": interval_counts,
        "ticker_sidecar_row_count": len(ticker_rows),
        "ticker_ok_intraday_row_count": len(ok_rows),
        "ticker_skipped_row_count": len(skipped_rows),
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
    for row in rows:
        if row["coverage_status"] == "covered_15m_60m_signal_date":
            by_window_covered[str(row.get("window") or "")] += 1
    return {
        "trade_count": len(rows),
        "by_coverage_status": dict(sorted(by_status.items())),
        "covered_trade_count": by_status["covered_15m_60m_signal_date"],
        "partial_trade_count": by_status["partial_intraday_signal_date"],
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
            "observed_only_intraday_entry_data_ready_for_later_replay",
            (
                "The Kova intraday sidecar has enough 15m/60m signal-date bars "
                "to support a later closed alpha replay. No strategy change is "
                "made here."
            ),
            evidence,
        )
    return (
        "data_gap_intraday_entry_rows_unavailable",
        (
            "The local Kova intraday sidecar does not have PIT 15m/60m bars for "
            "the accepted VCP top-2 trade dates. Do not run or promote an "
            "intraday Kova entry rule until the sidecar contains real bars."
        ),
        evidence,
    )


def _build_payload() -> dict[str, Any]:
    source = _load_source_rank_profile()
    source_rows_by_window = _source_trade_rows(source)
    source_rows = _flatten(source_rows_by_window)
    intraday_rows, intraday_paths = _load_intraday_rows()
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in intraday_rows:
        rows_by_ticker[str(row.get("ticker") or "").upper()].append(row)
    coverage_rows = [
        _coverage_for_trade(row, rows_by_ticker) for row in source_rows
    ]
    sidecar_summary = _sidecar_summary(intraday_rows, intraday_paths)
    coverage = _coverage_summary(coverage_rows)
    decision, interpretation, evidence = _decision(coverage)
    open_positions_audit = _audit_open_positions()
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "decision": decision,
        "created_at": _now(),
        "lane": "measurement_repair",
        "registry_lane": "measurement_repair",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "summary": interpretation,
        "alpha_hypothesis": (
            "Kova 15m/60m contraction and pocket-pivot context may improve VCP "
            "entry timing, but only if PIT intraday bars exist for historical "
            "trade dates."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Entry alpha is blocked by data readiness: 15m/60m bars must "
                "exist before testing precise intraday entries."
            ),
            "2_history_check": {
                "exp-20260526-037": "Kova readiness audit flagged intraday rows as unavailable.",
                "exp-20260527-001": "Kova sidecar added intraday surface, usually skipped without API key.",
                "exp-20260527-014": "Kova sidecar wiring stayed default-off.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "At least 20 trades across at least two windows must have both "
                "15m and 60m signal-date bars before alpha replay."
            ),
            "5_reproducibility": "Script writes JSON, markdown, ticket, log, and JSONL row.",
        },
        "acceptance_standard": {
            "promotion_allowed_in_this_experiment": False,
            "reason": "Coverage audit only; no entry rule is tested or promoted.",
            "readiness_gate": (
                "PIT 15m/60m rows cover at least 20 source trades across at "
                "least two standard windows."
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window source population",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
        },
        "gate1": {
            "passed": True,
            "source_paper_baseline": "exp-20260526-007 rank2_125 VCP top-2 paper sleeve",
            "source_trade_count": len(source_rows),
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True,
            "open_positions": open_positions_audit,
            "required_sidecar_fields": [
                "surface",
                "ticker",
                "status",
                "interval",
                "timestamp",
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
            "exp_20260527_902_kova_intraday_entry_readiness_audit.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        },
        "why_not_other_changes": (
            "Did not fetch network data, add API keys, retune entries/exits, "
            "change ranking, sizing, universe, LLM/news, or live/default orders."
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
        f"# {EXPERIMENT_ID} Kova Intraday Entry Readiness Audit",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Sidecar",
        "",
        f"- Intraday files: `{sidecar['file_count']}`.",
        f"- Intraday rows: `{sidecar['row_count']}`.",
        f"- Status counts: `{sidecar['by_status']}`.",
        f"- Reason counts: `{sidecar['by_reason']}`.",
        "",
        "## Trade Coverage",
        "",
        f"- Source trades: `{coverage['trade_count']}`.",
        f"- Fully covered 15m+60m signal-date trades: `{coverage['covered_trade_count']}`.",
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
        **existing,
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["registry_lane"],
        "owner": existing.get("owner") or "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": "kova_intraday_entry_readiness_audit",
        "mechanism_family": "kova_intraday_entry_timing",
        "trial_family": payload["trial_family"],
        "trial_variant_id": CHANGED_VARIABLE,
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": existing.get("prior_trial_count", 2),
        "nearby_prior_experiments": list(payload["gate_questions"]["2_history_check"].keys()),
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "intraday_sidecar_coverage_for_vcp_top2_trade_dates",
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260527_902_kova_intraday_entry_readiness_audit.py")),
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
            "quant/volatility_contraction_paper_sleeve.py",
            "operator_inputs/open_positions.json",
        ],
        "locked_variables": [
            "intraday data coverage audit only",
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
