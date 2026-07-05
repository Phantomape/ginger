"""exp-20260704-020: repair supplier-financing missing forward replacement values.

Measurement repair only. exp-20260704-019 found the
supplier_financing_debt_relief sleeve had three newly closed forward rows, but
COHR and MU were missing cash/SPY/QQQ replacement-value comparators. This
runner uses the shared forward_replacement_value helper and the repaired hot
warehouse overlay reader from exp-20260704-017 to enrich only that supplier
state, then rebuilds the canonical forward_replacement_value.jsonl artifact.
It changes no entry, exit, ranking, sizing, risk budget, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260704-020"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "supplier_financing_missing_forward_rv_enrichment"
SLEEVE_KEY = "supplier_financing_debt_relief"
SLEEVE_TOKEN = "SUPPLIER_FINANCING_DEBT_RELIEF"
ASOF_DATE = "2026-07-04"
MIN_ACTIVATION_CLOSED_ROWS = 30

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import forward_replacement_value as frv  # noqa: E402
from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from scripts.experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


RUNNER = f"quant/experiments/exp_20260704_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_020_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"
STATE_JSON = SLEEVES_ROOT / SLEEVE_KEY / "state.json"
SNAPSHOTS_JSONL = SLEEVES_ROOT / SLEEVE_KEY / "snapshots.jsonl"
FORWARD_RV_JSONL = SLEEVES_ROOT / "forward_replacement_value.jsonl"
ARCHIVE_FORWARD_RV_JSONL = OUT_DIR / "forward_replacement_value_before.jsonl"
PRIOR_LOG_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260704-019.json"
WRITE_FALLBACKS: list[str] = []


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def safe_write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(
    payload: Any,
    path: str | Path,
    *,
    indent: int = 2,
    ensure_ascii: bool = True,
    default: Any = None,
) -> None:
    safe_write_text(
        json.dumps(
            make_json_safe(payload),
            indent=indent,
            ensure_ascii=ensure_ascii,
            sort_keys=True,
            default=default,
        )
        + "\n",
        Path(path),
    )


def write_json(path: Path, payload: Any) -> None:
    safe_write_json(payload, path, ensure_ascii=True)


def write_text(path: Path, text: str) -> None:
    safe_write_text(text, path)


def safe_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_int(value: Any) -> int:
    number = safe_float(value)
    return int(number) if number is not None else 0


def round_or_none(value: Any, digits: int = 4) -> float | None:
    number = safe_float(value)
    return round(number, digits) if number is not None else None


def make_json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(v) for v in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    windows = windows if isinstance(windows, list) else []
    generated = sum(safe_int(row.get("signals_generated")) for row in windows)
    survived = sum(safe_int(row.get("signals_survived")) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "loaded": BASELINE_JSON.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(safe_int(row.get("trade_count")) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
    }


def latest_snapshot() -> tuple[dict[str, Any], int]:
    snapshots = read_jsonl(SNAPSHOTS_JSONL)
    if not snapshots:
        return {}, 0
    return snapshots[-1], len(snapshots)


def replacement_complete(row: dict[str, Any]) -> bool:
    return (
        row.get("replacement_value_status") == "enriched"
        and safe_float(row.get("replacement_value_vs_cash_usd")) is not None
        and safe_float(row.get("replacement_value_vs_spy_usd")) is not None
        and safe_float(row.get("replacement_value_vs_qqq_usd")) is not None
    )


def slim_closed(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "hold_days": row.get("hold_days") or row.get("days_held"),
        "paper_notional_usd": round_or_none(row.get("paper_notional_usd") or row.get("notional_usd"), 2),
        "pnl": round_or_none(row.get("pnl"), 2),
        "target_price_present": row.get("target_price") is not None,
        "replacement_value_status": row.get("replacement_value_status"),
        "replacement_value_vs_cash_usd": round_or_none(row.get("replacement_value_vs_cash_usd"), 2),
        "replacement_value_vs_spy_usd": round_or_none(row.get("replacement_value_vs_spy_usd"), 2),
        "replacement_value_vs_qqq_usd": round_or_none(row.get("replacement_value_vs_qqq_usd"), 2),
        "trade_enabled": row.get("trade_enabled"),
        "decision_id": row.get("decision_id"),
    }


def summarize_supplier_state(state: dict[str, Any] | None = None) -> dict[str, Any]:
    if state is None:
        state = read_json(STATE_JSON, {})
    closed = state.get("closed_positions") if isinstance(state, dict) else []
    open_positions = state.get("open_positions") if isinstance(state, dict) else []
    pending = state.get("pending_entries") if isinstance(state, dict) else []
    closed = [row for row in closed if isinstance(row, dict)] if isinstance(closed, list) else []
    open_positions = (
        [row for row in open_positions if isinstance(row, dict)]
        if isinstance(open_positions, list)
        else []
    )
    pending = [row for row in pending if isinstance(row, dict)] if isinstance(pending, list) else []
    latest, snapshot_count = latest_snapshot()
    gate = latest.get("forward_paper_gate") if isinstance(latest, dict) else {}
    gate = gate if isinstance(gate, dict) else {}
    complete = [row for row in closed if replacement_complete(row)]
    cash = [safe_float(row.get("replacement_value_vs_cash_usd")) for row in complete]
    spy = [safe_float(row.get("replacement_value_vs_spy_usd")) for row in complete]
    qqq = [safe_float(row.get("replacement_value_vs_qqq_usd")) for row in complete]
    pnl = [safe_float(row.get("pnl")) for row in closed]
    cash = [value for value in cash if value is not None]
    spy = [value for value in spy if value is not None]
    qqq = [value for value in qqq if value is not None]
    pnl = [value for value in pnl if value is not None]
    return {
        "state_file": repo_rel(STATE_JSON),
        "state_exists": STATE_JSON.exists(),
        "state_updated_at": state.get("updated_at") if isinstance(state, dict) else None,
        "snapshot_file": repo_rel(SNAPSHOTS_JSONL),
        "snapshot_exists": SNAPSHOTS_JSONL.exists(),
        "snapshot_count": snapshot_count,
        "latest_snapshot_asof_date": latest.get("asof_date"),
        "closed_position_count": len(closed),
        "open_position_count": len(open_positions),
        "pending_entry_count": len(pending),
        "closed_replacement_value_count": len(complete),
        "closed_missing_replacement_value_count": len(closed) - len(complete),
        "raw_realized_pnl_usd": round(sum(pnl), 2) if pnl else 0.0,
        "replacement_value_vs_cash_usd": round(sum(cash), 2) if cash else 0.0,
        "replacement_value_vs_spy_usd": round(sum(spy), 2) if spy else 0.0,
        "replacement_value_vs_qqq_usd": round(sum(qqq), 2) if qqq else 0.0,
        "replacement_win_rate": (
            round(sum(1 for value in cash if value > 0) / len(cash), 4)
            if cash
            else None
        ),
        "closed_missing_replacement_rows": [
            slim_closed(row) for row in closed if not replacement_complete(row)
        ],
        "closed_positions": [slim_closed(row) for row in closed],
        "closed_missing_entry_or_target": [
            row.get("decision_id") or row.get("ticker")
            for row in closed
            if not row.get("entry_date") or row.get("target_price") is None
        ],
        "open_missing_entry_date": [
            row.get("decision_id") or row.get("ticker")
            for row in open_positions
            if not row.get("entry_date")
        ],
        "ticker_counts": Counter(row.get("ticker") or "unknown" for row in [*closed, *open_positions, *pending]),
        "closed_sector_counts": Counter(row.get("sector") or "unknown" for row in closed),
        "trade_enabled_values": sorted(
            {str(row.get("trade_enabled")) for row in [*closed, *open_positions, *pending]}
        ),
        "forward_paper_gate": {
            "passed": gate.get("passed"),
            "status": gate.get("status"),
            "closed_trade_count": gate.get("closed_trade_count"),
            "min_closed_trades": gate.get("min_closed_trades"),
            "net_pnl": gate.get("net_pnl"),
            "win_rate": gate.get("win_rate"),
            "reasons": gate.get("reasons") if isinstance(gate.get("reasons"), list) else [],
        },
    }


def is_supplier_row(row: dict[str, Any]) -> bool:
    decision_id = str(row.get("decision_id") or "")
    sleeve = str(row.get("sleeve") or row.get("source") or "")
    sleeve_key = str(row.get("sleeve_key") or "")
    return (
        sleeve_key == SLEEVE_KEY
        or SLEEVE_TOKEN in decision_id.upper()
        or SLEEVE_TOKEN in sleeve.upper()
    )


def summarize_forward_replacement() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_RV_JSONL)
    matches = [row for row in rows if is_supplier_row(row)]
    enriched = [row for row in matches if row.get("status") == "enriched"]
    cash = [safe_float(row.get("replacement_value_vs_cash_usd")) for row in enriched]
    spy = [safe_float(row.get("replacement_value_vs_spy_usd")) for row in enriched]
    qqq = [safe_float(row.get("replacement_value_vs_qqq_usd")) for row in enriched]
    cash = [value for value in cash if value is not None]
    spy = [value for value in spy if value is not None]
    qqq = [value for value in qqq if value is not None]
    return {
        "ledger_file": repo_rel(FORWARD_RV_JSONL),
        "ledger_exists": FORWARD_RV_JSONL.exists(),
        "total_rows": len(rows),
        "matching_rows": len(matches),
        "enriched_matching_rows": len(enriched),
        "status_counts": Counter(row.get("status") or "unknown" for row in matches),
        "tickers": sorted({str(row.get("ticker")) for row in matches if row.get("ticker")}),
        "replacement_value_vs_cash_usd": round(sum(cash), 2) if cash else 0.0,
        "replacement_value_vs_spy_usd": round(sum(spy), 2) if spy else 0.0,
        "replacement_value_vs_qqq_usd": round(sum(qqq), 2) if qqq else 0.0,
        "sample_matches": [
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "status": row.get("status"),
                "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
                "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
                "decision_id": row.get("decision_id"),
            }
            for row in matches
        ],
    }


def prior_summary() -> dict[str, Any]:
    prior = read_json(PRIOR_LOG_JSON, {})
    delta = prior.get("delta_metrics") if isinstance(prior, dict) else {}
    readiness = (
        prior.get("supplier_financing_debt_relief_readiness")
        if isinstance(prior, dict)
        else {}
    )
    state = readiness.get("state") if isinstance(readiness, dict) else {}
    forward = readiness.get("forward_replacement") if isinstance(readiness, dict) else {}
    return {
        "prior_experiment_id": "exp-20260704-019",
        "prior_log": repo_rel(PRIOR_LOG_JSON),
        "prior_log_exists": PRIOR_LOG_JSON.exists(),
        "prior_closed_position_count": delta.get("closed_position_count") if isinstance(delta, dict) else None,
        "prior_enriched_replacement_rows": delta.get("enriched_replacement_rows") if isinstance(delta, dict) else None,
        "prior_missing_replacement_count": (
            state.get("closed_missing_replacement_value_count") if isinstance(state, dict) else None
        ),
        "prior_forward_matching_rows": (
            forward.get("matching_rows") if isinstance(forward, dict) else None
        ),
        "prior_decision": prior.get("decision") if isinstance(prior, dict) else None,
        "prior_next_retry_requires": prior.get("next_retry_requires") if isinstance(prior, dict) else None,
    }


def enrich_supplier_state() -> dict[str, Any]:
    state = read_json(STATE_JSON, {})
    before_state = json.loads(json.dumps(state))
    closed = state.get("closed_positions") if isinstance(state, dict) else []
    closed = [row for row in closed if isinstance(row, dict)] if isinstance(closed, list) else []
    tickers = sorted({str(row.get("ticker")).upper() for row in closed if row.get("ticker")})
    bars_by_ticker = frv.load_comparator_bars()
    regime_spy_bars = frv.load_regime_spy_bars()
    sv_percentile_index = frv.load_short_volume_percentile_index()
    exhaustion_bars = frv.load_entry_exhaustion_bars(tickers)
    records = frv.enrich_state_closed_rows(
        state,
        bars_by_ticker,
        ASOF_DATE,
        SLEEVE_KEY,
        regime_spy_bars=regime_spy_bars,
        sv_percentile_index=sv_percentile_index,
        exhaustion_bars=exhaustion_bars,
    )
    state_changed = state != before_state
    if state_changed:
        safe_write_json(state, STATE_JSON, ensure_ascii=True)

    def runner_write_jsonl(path: str | Path, records_: list[dict[str, Any]]) -> None:
        text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records_)
        safe_write_text(text, Path(path))

    frv.atomic_write_json = safe_write_json
    frv._write_jsonl = runner_write_jsonl
    artifact_summary = frv.rebuild_current_state_artifact(
        sleeves_root=SLEEVES_ROOT,
        artifact_path=FORWARD_RV_JSONL,
        archive_path=ARCHIVE_FORWARD_RV_JSONL,
    )
    return {
        "state_changed": state_changed,
        "rows_updated_this_run": len(records),
        "updated_records": [
            {
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "status": row.get("status"),
                "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
                "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
                "decision_id": row.get("decision_id"),
            }
            for row in records
        ],
        "warehouse_inputs": {
            "comparator_tickers": sorted(bars_by_ticker.keys()),
            "comparator_bar_counts": {
                ticker: len(bars) for ticker, bars in sorted(bars_by_ticker.items())
            },
            "regime_spy_bars": len(regime_spy_bars),
            "short_volume_symbols": len(sv_percentile_index),
            "entry_exhaustion_tickers": len(exhaustion_bars),
        },
        "artifact_summary": artifact_summary,
        "write_fallbacks": list(WRITE_FALLBACKS),
    }


def classify_readiness(state: dict[str, Any], forward: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if state["closed_position_count"] < MIN_ACTIVATION_CLOSED_ROWS:
        blockers.append(
            f"closed_rows_below_activation_min:{state['closed_position_count']}/{MIN_ACTIVATION_CLOSED_ROWS}"
        )
    if forward["enriched_matching_rows"] < MIN_ACTIVATION_CLOSED_ROWS:
        blockers.append(
            f"replacement_rows_below_activation_min:{forward['enriched_matching_rows']}/{MIN_ACTIVATION_CLOSED_ROWS}"
        )
    if state["raw_realized_pnl_usd"] <= 0:
        blockers.append(f"non_positive_raw_realized_pnl:{state['raw_realized_pnl_usd']}")
    if state["replacement_value_vs_cash_usd"] <= 0:
        blockers.append(f"non_positive_replacement_vs_cash:{state['replacement_value_vs_cash_usd']}")
    if state["replacement_value_vs_spy_usd"] <= 0:
        blockers.append(f"non_positive_replacement_vs_spy:{state['replacement_value_vs_spy_usd']}")
    if state["replacement_value_vs_qqq_usd"] <= 0:
        blockers.append(f"non_positive_replacement_vs_qqq:{state['replacement_value_vs_qqq_usd']}")
    if state["forward_paper_gate"].get("passed") is not True:
        blockers.append("shared_forward_paper_gate_not_passed")
    return not blockers, blockers


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    prior = prior_summary()
    before_state = summarize_supplier_state()
    before_forward = summarize_forward_replacement()
    repair = enrich_supplier_state()
    after_state = summarize_supplier_state()
    after_forward = summarize_forward_replacement()
    alpha_ready, alpha_blockers = classify_readiness(after_state, after_forward)

    missing_repaired = (
        before_state["closed_missing_replacement_value_count"]
        - after_state["closed_missing_replacement_value_count"]
    )
    repair_success = (
        after_state["closed_position_count"] > 0
        and after_state["closed_missing_replacement_value_count"] == 0
        and after_forward["enriched_matching_rows"] >= after_state["closed_position_count"]
        and after_state["closed_missing_entry_or_target"] == []
        and after_state["open_missing_entry_date"] == []
    )
    decision = (
        "accepted_measurement_repair_supplier_financing_forward_replacement_enrichment"
        if repair_success
        else "blocked_supplier_financing_forward_replacement_enrichment_incomplete"
    )
    classification = (
        "measurement_repair_accepted_alpha_not_activation_ready"
        if repair_success and not alpha_ready
        else "measurement_repair_accepted_alpha_activation_candidate"
        if repair_success
        else "measurement_repair_blocked"
    )
    predicted = safe_float((ticket.get("prediction") or {}).get("success_probability")) or 0.0
    actual_success = 1 if repair_success else 0

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted" if repair_success else "blocked",
        "decision": decision,
        "accepted": repair_success,
        "accepted_alpha": False,
        "alpha_ready": alpha_ready,
        "classification": classification,
        "hypothesis": ticket.get("hypothesis"),
        "change_type": ticket.get("change_type"),
        "implementation_mode": "narrow_supplier_state_replacement_value_enrichment",
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components", []),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "new_evidence_axis": "measurement_repair_after_hot_warehouse_io_fix_for_two_missing_closed_rows",
        "novelty": ticket.get("novelty"),
        "prediction": ticket.get("prediction", {}),
        "parameters": {
            "asof_date": ASOF_DATE,
            "baseline_result_file": repo_rel(BASELINE_JSON),
            "state_file": repo_rel(STATE_JSON),
            "forward_replacement_value_file": repo_rel(FORWARD_RV_JSONL),
            "archived_previous_forward_replacement_value_file": repo_rel(ARCHIVE_FORWARD_RV_JSONL),
            "min_activation_closed_rows": MIN_ACTIVATION_CLOSED_ROWS,
        },
        "pre_run_questions": {
            "alpha_hypothesis": ticket.get("hypothesis"),
            "history_check": {
                "prior": prior,
                "novelty_nearest": ((ticket.get("novelty") or {}).get("nearest") or [])[:5],
            },
            "single_policy_bundle": ticket.get("single_causal_variable"),
            "acceptance_standard": (
                "Accept as measurement repair if all closed supplier-financing rows have "
                "cash/SPY/QQQ replacement values after enrichment and the shared artifact "
                "contains those rows. Treat alpha activation separately and require at "
                "least 30 closed enriched rows plus positive cash/SPY/QQQ replacement value."
            ),
            "reproducibility": RUNNER_COMMAND,
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
            "closed_position_count": after_state["closed_position_count"],
            "closed_missing_replacement_value_before": before_state[
                "closed_missing_replacement_value_count"
            ],
            "closed_missing_replacement_value_after": after_state[
                "closed_missing_replacement_value_count"
            ],
            "closed_missing_replacement_value_repaired": missing_repaired,
            "rows_updated_this_run": repair["rows_updated_this_run"],
            "forward_matching_rows_before": before_forward["matching_rows"],
            "forward_matching_rows_after": after_forward["matching_rows"],
            "forward_enriched_matching_rows_before": before_forward["enriched_matching_rows"],
            "forward_enriched_matching_rows_after": after_forward["enriched_matching_rows"],
            "raw_realized_pnl_usd": after_state["raw_realized_pnl_usd"],
            "replacement_value_vs_cash_usd": after_state["replacement_value_vs_cash_usd"],
            "replacement_value_vs_spy_usd": after_state["replacement_value_vs_spy_usd"],
            "replacement_value_vs_qqq_usd": after_state["replacement_value_vs_qqq_usd"],
        },
        "gate1": {
            "passed": baseline["loaded"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": (
                STATE_JSON.exists()
                and FORWARD_RV_JSONL.exists()
                and after_state["closed_missing_entry_or_target"] == []
                and after_state["open_missing_entry_date"] == []
                and after_state["closed_missing_replacement_value_count"] == 0
            ),
            "fields_checked": [
                "closed_positions.entry_date",
                "closed_positions.target_price",
                "closed_positions.pnl",
                "closed_positions.paper_notional_usd",
                "closed_positions.replacement_value_vs_cash_usd",
                "closed_positions.replacement_value_vs_spy_usd",
                "closed_positions.replacement_value_vs_qqq_usd",
                "forward_replacement_value.sleeve_key",
                "forward_replacement_value.status",
            ],
            "missing_or_invalid_fields": {
                "before_missing_replacement_rows": before_state["closed_missing_replacement_rows"],
                "after_missing_replacement_rows": after_state["closed_missing_replacement_rows"],
                "closed_missing_entry_or_target": after_state["closed_missing_entry_or_target"],
                "open_missing_entry_date": after_state["open_missing_entry_date"],
            },
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, exit, ranking, sizing, risk, or order rule changed.",
        },
        "gate4": {
            "passed": repair_success,
            "accepted_measurement_repair": repair_success,
            "accepted_alpha": False,
            "alpha_ready": alpha_ready,
            "classification": classification,
            "decision": decision,
            "repair_failed_reasons": []
            if repair_success
            else [
                "closed_supplier_rows_still_missing_replacement_value",
                "shared_forward_artifact_missing_supplier_rows",
            ],
            "alpha_activation_blockers": alpha_blockers,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
        },
        "supplier_financing_debt_relief_repair": {
            "prior": prior,
            "before_state": before_state,
            "before_forward_replacement": before_forward,
            "repair": repair,
            "after_state": after_state,
            "after_forward_replacement": after_forward,
        },
        "production_impact": {
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Only closed default-off supplier state rows and the shared forward "
                "replacement-value artifact changed; no executable policy or live order path changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": predicted,
            "actual_success": actual_success,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": (ticket.get("prediction") or {}).get("main_failure_modes", []),
            "realized_failure_modes": []
            if repair_success
            else ["replacement_enrichment_incomplete"],
            "alpha_realized_non_activation": alpha_blockers,
            "predicted_failure_mode_hit": "readiness_still_negative"
            in (ticket.get("prediction") or {}).get("main_failure_modes", []),
            "surprise_note": (
                "COHR and MU enriched mechanically from the repaired warehouse reader; "
                "the remaining negative readiness is an alpha conclusion, not a repair failure."
                if repair_success
                else "At least one closed supplier row still lacks replacement comparators."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The missing COHR/MU rows already had ticker, entry_date, exit_date, pnl, "
                "and notional, and the hot/cold overlay warehouse covers SPY/QQQ bars for "
                "their 2026-06-25 to 2026-07-02 holding window."
            ),
            "alpha_interpretation": (
                "Completing the measurement surface made the supplier-financing evidence "
                "stricter, not better: 3/30 closed rows are enriched, raw PnL totals "
                f"{after_state['raw_realized_pnl_usd']}, and replacement totals are "
                f"{after_state['replacement_value_vs_cash_usd']} cash, "
                f"{after_state['replacement_value_vs_spy_usd']} SPY, "
                f"{after_state['replacement_value_vs_qqq_usd']} QQQ."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune supplier-financing thresholds or re-run activation on the "
                "same three rows. Reopen only with materially more closed rows or a genuinely "
                "new supplier/payment/covenant/refinancing source."
            ),
            "new_evidence_required": (
                "Materially more closed default-off supplier-financing rows, or a new "
                "production-visible supplier/payment-term or covenant/refinancing source."
            ),
        },
        "rejection_reason": None
        if repair_success
        else "Replacement-value enrichment remained incomplete.",
        "next_retry_requires": [
            "materially_more_closed_supplier_financing_rows",
            "or_new_supplier_payment_term_covenant_refinancing_source",
            "no_threshold_or_response_function_retune_on_same_three_rows",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(STATE_JSON),
            repo_rel(FORWARD_RV_JSONL),
            repo_rel(ARCHIVE_FORWARD_RV_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "related_files": [
            "quant/forward_replacement_value.py",
            "quant/test_forward_replacement_value.py",
            "experiments/logs/exp-20260704-019.json",
            "experiments/logs/exp-20260704-017.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_forward_replacement_value.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": repair_success,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "owner": OWNER,
        "status": payload["status"],
        "lane": LANE,
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
        "new_evidence_axis": payload["new_evidence_axis"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "alpha_ready": payload["alpha_ready"],
        "classification": payload["classification"],
        "parameters": payload["parameters"],
        "pre_run_questions": payload["pre_run_questions"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "supplier_financing_debt_relief_repair": payload["supplier_financing_debt_relief_repair"],
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - supplier financing missing forward RV enrichment",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- classification: {payload['classification']}",
            f"- rows repaired: {delta['closed_missing_replacement_value_repaired']}",
            f"- forward supplier rows: {delta['forward_matching_rows_before']} -> {delta['forward_matching_rows_after']}",
            f"- replacement totals: cash {delta['replacement_value_vs_cash_usd']}, "
            f"SPY {delta['replacement_value_vs_spy_usd']}, QQQ {delta['replacement_value_vs_qqq_usd']}",
            f"- alpha activation blockers: {', '.join(gate4['alpha_activation_blockers'])}",
            "",
            "No entry, exit, ranking, sizing, risk, LLM decision boundary, or order behavior changed.",
            "",
            "Reproduce:",
            "",
            f"    {RUNNER_COMMAND}",
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
        REGISTRY_JSON,
        STATE_JSON,
        FORWARD_RV_JSONL,
        ARCHIVE_FORWARD_RV_JSONL,
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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_row = build_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "classification": payload["classification"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["post_run_reflection"]["alpha_interpretation"],
        },
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
            "new_evidence_axis": payload["new_evidence_axis"],
            "parameters": payload["parameters"],
            "pre_run_questions": payload["pre_run_questions"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "classification": payload["classification"],
                "rows_updated_this_run": payload["delta_metrics"]["rows_updated_this_run"],
                "missing_replacement_before": payload["delta_metrics"][
                    "closed_missing_replacement_value_before"
                ],
                "missing_replacement_after": payload["delta_metrics"][
                    "closed_missing_replacement_value_after"
                ],
                "replacement_value_vs_cash_usd": payload["delta_metrics"][
                    "replacement_value_vs_cash_usd"
                ],
                "replacement_value_vs_spy_usd": payload["delta_metrics"][
                    "replacement_value_vs_spy_usd"
                ],
                "replacement_value_vs_qqq_usd": payload["delta_metrics"][
                    "replacement_value_vs_qqq_usd"
                ],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
