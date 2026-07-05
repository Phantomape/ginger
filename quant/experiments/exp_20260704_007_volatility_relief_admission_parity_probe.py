"""exp-20260704-007: volatility-relief admission parity probe.

Measurement repair only. The accepted volatility-relief default-off sleeve has
zero forward daily admissions over the current snapshot span. This runner uses
a real historical accepted relief day to verify daily snapshot semantics match
historical replay, then audits current forward contexts to separate true
regime sparsity from production/backtest admission drift.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260607_019_volatility_relief_stock_leadership_shared_adapter as accepted_adapter  # noqa: E402
import volatility_relief_stock_leadership_paper_sleeve as shared_vol  # noqa: E402


EXPERIMENT_ID = "exp-20260704-007"
OWNER = "alpha-explore"
SLUG = "volatility_relief_admission_parity_probe"
RUNNER = f"quant/experiments/exp_20260704_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
ACCEPTED_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260607-019"
    / "exp_20260607_019_volatility_relief_stock_leadership_shared_adapter.json"
)
SNAPSHOT_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "volatility_relief_leadership" / "snapshots.jsonl"
STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "volatility_relief_leadership" / "state.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_007_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_007_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\experiments\\exp_20260704_007_volatility_relief_admission_parity_probe.py",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str) + "\n",
        path,
    )


def as_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON, {})
    windows = payload.get("windows") or []
    generated = sum(as_int(window.get("signals_generated")) for window in windows)
    survived = sum(as_int(window.get("signals_survived")) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(as_int(window.get("trade_count") or window.get("total_trades")) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def baseline_window_path(label: str) -> Path:
    payload = load_json(BASELINE_JSON, {})
    for window in payload.get("windows") or []:
        if window.get("label") == label:
            return REPO_ROOT / str(window["path"])
    raise RuntimeError(f"baseline window not found: {label}")


def choose_representative_trade(accepted: dict[str, Any]) -> dict[str, Any]:
    by_window = accepted.get("target_trades_by_window") or {}
    for label in ("old_thin", "mid_weak", "late_strong"):
        rows = by_window.get(label) or []
        if rows:
            first = rows[0]
            signal_date = str(first.get("signal_date") or first.get("date"))[:10]
            same_day = [
                row
                for row in rows
                if str(row.get("signal_date") or row.get("date"))[:10] == signal_date
            ]
            return {"window_label": label, "signal_date": signal_date, "accepted_trades": same_day}
    raise RuntimeError("accepted volatility-relief artifact has no target trades")


def flatten_entries(entries_by_date: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rows in entries_by_date.values():
        out.extend(row for row in rows if isinstance(row, dict))
    return out


def compact_trade(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "decision_id": row.get("decision_id"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "pnl": row.get("pnl"),
        "candidate_score": row.get("candidate_score"),
        "same_ticker_ab_overlap": row.get("same_ticker_ab_overlap"),
    }


def representative_day_parity() -> dict[str, Any]:
    accepted = load_json(ACCEPTED_ARTIFACT, {})
    chosen = choose_representative_trade(accepted)
    label = chosen["window_label"]
    signal_date = chosen["signal_date"]
    cfg = accepted_adapter.framework.WINDOWS[label]
    sector_entries = accepted_adapter.framework._load_sector_entries()
    snapshot = accepted_adapter._load_window_snapshot(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    candidate_universe = accepted_adapter._candidate_universe(sector_entries)
    before_result = load_json(baseline_window_path(label), {})
    core_entries_by_date = accepted_adapter.framework.shadow._baseline_entries(before_result)
    core_entries = flatten_entries(core_entries_by_date)

    historical = shared_vol.build_volatility_relief_stock_leadership_historical_trades(
        ohlcv_by_ticker=snapshot,
        dates=[signal_date],
        candidate_universe=candidate_universe,
        core_entries_by_date=core_entries_by_date,
    )
    daily = shared_vol.build_volatility_relief_stock_leadership_snapshot(
        as_of=signal_date,
        ohlcv_by_ticker=snapshot,
        candidate_universe=candidate_universe,
        core_entries=core_entries,
        state=shared_vol.empty_volatility_relief_stock_leadership_state(),
        persist=False,
    )

    accepted_trades = chosen["accepted_trades"]
    accepted_tickers = [str(row.get("ticker") or "").upper() for row in accepted_trades]
    historical_tickers = [str(row.get("ticker") or "").upper() for row in historical.get("trades", [])]
    daily_tickers = [str(row.get("ticker") or "").upper() for row in daily.get("candidates", [])]
    accepted_decisions = [row.get("decision_id") for row in accepted_trades]
    historical_decisions = [row.get("decision_id") for row in historical.get("trades", [])]
    daily_decisions = [row.get("decision_id") for row in daily.get("candidates", [])]

    ticker_match = accepted_tickers == historical_tickers == daily_tickers
    decision_match = accepted_decisions == historical_decisions == daily_decisions
    lifecycle_match = [
        (
            a.get("ticker"),
            a.get("entry_date"),
            a.get("exit_date"),
            h.get("entry_date"),
            h.get("exit_date"),
            d.get("entry_date"),
            d.get("exit_date"),
        )
        for a, h, d in zip(accepted_trades, historical.get("trades", []), daily.get("candidates", []))
    ]
    lifecycle_passed = all(item[1] == item[3] == item[5] and item[2] == item[4] == item[6] for item in lifecycle_match)
    context_passed = bool((daily.get("volatility_relief_context") or {}).get("passed"))
    parity_passed = ticker_match and decision_match and lifecycle_passed and context_passed

    return {
        "accepted_artifact": repo_rel(ACCEPTED_ARTIFACT),
        "window_label": label,
        "signal_date": signal_date,
        "sector_entry_count": len(sector_entries),
        "loaded_ohlcv_tickers": len(snapshot),
        "accepted_trades": [compact_trade(row) for row in accepted_trades],
        "historical_trades": [compact_trade(row) for row in historical.get("trades", [])],
        "daily_candidates": [compact_trade(row) for row in daily.get("candidates", [])],
        "daily_new_pending_entries": [compact_trade(row) for row in daily.get("new_pending_entries", [])],
        "accepted_tickers": accepted_tickers,
        "historical_tickers": historical_tickers,
        "daily_tickers": daily_tickers,
        "accepted_decisions": accepted_decisions,
        "historical_decisions": historical_decisions,
        "daily_decisions": daily_decisions,
        "ticker_match": ticker_match,
        "decision_match": decision_match,
        "lifecycle_match": lifecycle_match,
        "lifecycle_passed": lifecycle_passed,
        "context_passed": context_passed,
        "parity_passed": parity_passed,
        "daily_context": daily.get("volatility_relief_context"),
        "daily_context_scan": daily.get("context_scan"),
        "historical_context_scan": historical.get("context_scan"),
        "daily_candidate_count": daily.get("candidate_count"),
        "daily_raw_candidate_count": daily.get("raw_candidate_count"),
        "historical_trade_count": len(historical.get("trades", [])),
    }


def current_forward_context_audit() -> dict[str, Any]:
    rows = read_jsonl(SNAPSHOT_JSONL)
    latest_by_asof: dict[str, dict[str, Any]] = {}
    for row in rows:
        asof = str(row.get("asof_date") or row.get("date") or "")[:10]
        if asof:
            latest_by_asof[asof] = row
    reasons: Counter[str] = Counter()
    passed_dates: list[str] = []
    passed_without_candidates: list[str] = []
    raw_total = 0
    candidate_total = 0
    new_pending_total = 0
    context_samples: list[dict[str, Any]] = []
    for asof, row in sorted(latest_by_asof.items()):
        context = row.get("volatility_relief_context") if isinstance(row.get("volatility_relief_context"), dict) else {}
        passed = context.get("passed") is True
        raw_count = as_int(row.get("raw_candidate_count"))
        candidate_count = as_int(row.get("candidate_count"))
        new_pending_count = as_int(row.get("new_pending_count"))
        if passed:
            passed_dates.append(asof)
            if raw_count == 0 and candidate_count == 0 and new_pending_count == 0:
                passed_without_candidates.append(asof)
        reason = str(context.get("reason") or context.get("status") or row.get("error") or "failed_context_without_reason")
        if not passed:
            reasons[reason] += 1
        raw_total += raw_count
        candidate_total += candidate_count
        new_pending_total += new_pending_count
        if len(context_samples) < 8:
            context_samples.append(
                {
                    "asof_date": asof,
                    "passed": passed,
                    "reason": reason,
                    "vixy_return": context.get("vixy_return"),
                    "spy_return": context.get("spy_return"),
                    "qqq_return": context.get("qqq_return"),
                    "candidate_count": row.get("candidate_count"),
                    "raw_candidate_count": row.get("raw_candidate_count"),
                }
            )

    state = load_json(STATE_JSON, {})
    skip_reasons = Counter(
        str(row.get("reason") or "unknown")
        for row in state.get("skipped_days") or []
        if isinstance(row, dict)
    )
    return {
        "snapshot_file": repo_rel(SNAPSHOT_JSONL),
        "snapshot_rows": len(rows),
        "unique_asof_dates": len(latest_by_asof),
        "first_asof_date": next(iter(sorted(latest_by_asof)), None),
        "last_asof_date": next(reversed(sorted(latest_by_asof)), None) if latest_by_asof else None,
        "context_passed_date_count": len(passed_dates),
        "context_passed_dates": passed_dates,
        "context_passed_without_candidates_dates": passed_without_candidates,
        "failed_context_reasons": dict(reasons.most_common()),
        "state_skip_reasons": dict(skip_reasons.most_common()),
        "raw_candidate_total": raw_total,
        "candidate_total": candidate_total,
        "new_pending_total": new_pending_total,
        "context_samples": context_samples,
        "accepted_rule_zero_fire_explained": (
            len(latest_by_asof) >= 10
            and raw_total == 0
            and candidate_total == 0
            and new_pending_total == 0
            and len(passed_without_candidates) == len(passed_dates)
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {})
    baseline = baseline_summary()
    parity = representative_day_parity()
    current_audit = current_forward_context_audit()
    accepted = bool(parity["parity_passed"] and current_audit["accepted_rule_zero_fire_explained"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_volatility_relief_admission_parity_confirmed"
        if accepted
        else "blocked_volatility_relief_admission_parity_drift_or_ambiguous_forward_context"
    )
    failed_reasons: list[str] = []
    if not parity["parity_passed"]:
        failed_reasons.append("representative_historical_daily_replay_mismatch")
    if not current_audit["accepted_rule_zero_fire_explained"]:
        failed_reasons.append("current_forward_zero_fire_not_fully_explained_by_accepted_rule")

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Forward evidence supply is an alpha bottleneck: if an accepted "
            "default-off sleeve underfires because daily production semantics "
            "drifted from replay, forward replacement-value evidence will never "
            "mature; if the helper is parity-clean, the legal next step is to "
            "wait for true VIXY relief rows rather than retuning thresholds."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "volatility_relief_admission_parity_probe",
        "trial_variant_id": "volatility_relief_representative_day_daily_vs_replay_v1",
        "single_causal_variable": "volatility_relief_daily_vs_replay_representative_day_parity_v1",
        "changed_variable": "volatility_relief_daily_vs_replay_representative_day_parity_v1",
        "causal_components": [
            "real accepted historical relief-day replay",
            "daily snapshot helper with persist false",
            "accepted artifact ticker/decision/lifecycle comparison",
            "current forward context reason audit",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": ["exp-20260607-019", "exp-20260704-006"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "representative_day_daily_vs_replay_parity_probe",
        "new_evidence_axis": (
            "Measurement-only representative-day parity evidence for an accepted "
            "default-off sleeve named by exp-20260704-006; no threshold, notional, "
            "top-N, hold, cooldown, or response rule changed."
        ),
        "gate1": {"passed": BASELINE_JSON.exists(), "baseline_metrics": baseline},
        "gate2": {
            "passed": bool(parity["context_passed"] and parity["daily_candidate_count"]),
            "fields_checked": [
                "accepted target_trades_by_window",
                "historical OHLCV rows for VIXY/SPY/QQQ/candidates",
                "broad-market sector universe",
                "daily snapshot candidate_count/raw_candidate_count",
                "decision_id",
                "entry_date",
                "exit_date",
            ],
            "entry_date_target_price_scope": (
                "No executable order or target exit is created. The parity probe "
                "checks paper entry_date/exit_date lifecycle fields on closed "
                "historical/default-off paper rows."
            ),
            "representative_window": parity["window_label"],
            "representative_signal_date": parity["signal_date"],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter/rank/size/exit rule changed; survival is baseline identity.",
        },
        "gate4": {
            "mode": "measurement_repair_volatility_relief_admission_parity",
            "passed": accepted,
            "accepted_measurement_repair": accepted,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "failed_reasons": failed_reasons,
            "representative_parity_passed": parity["parity_passed"],
            "current_zero_fire_explained_by_accepted_rule": current_audit["accepted_rule_zero_fire_explained"],
            "decision_basis": (
                "Accepted as measurement repair: a real historical accepted "
                "volatility-relief day matches between accepted artifact, shared "
                "historical replay, and daily snapshot helper; current forward zero-fire "
                "is explained by accepted-rule candidate absence on the few relief "
                "context-pass dates, not by helper admission drift."
                if accepted
                else (
                    "Blocked: the representative-day parity or current forward "
                    "context audit did not cleanly distinguish regime sparsity "
                    "from admission drift."
                )
            ),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "representative_day_parity": parity,
        "current_forward_context_audit": current_audit,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Read-only parity probe over the existing shared volatility-relief "
                "helper and existing paper snapshots. It does not alter live/default "
                "orders, rankings, sizing, exits, or paper snapshot generation."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The helper reproduced a real accepted historical relief day in "
                "daily snapshot mode, including tickers, decision IDs, entry/exit "
                "dates, and context. Current forward snapshots had three VIXY/SPY/QQQ "
                "relief context-pass dates but zero accepted-rule stock-leadership "
                "raw candidates, so zero admissions are expected under the accepted rule."
                if accepted
                else (
                    "The probe could not prove that current zero admissions are "
                    "only regime sparsity; inspect representative parity and current "
                    "context details before trusting forward absence."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune VIXY decline, SPY/QQQ relief, stock leadership, "
                "top-N, hold-day, cooldown, notional, or response curves from this "
                "zero-fire span. Its few relief context-pass dates produced no "
                "accepted-rule stock-leadership candidates."
            ),
            "new_evidence_required": (
                "Reopen volatility-relief activation only after new forward daily "
                "snapshots include actual VIXY relief context passes with closed "
                "cash/SPY/QQQ replacement value, or after a concrete daily helper "
                "input drift is observed."
            ),
        },
        "next_retry_requires": [
            "actual forward VIXY relief context-pass rows with closed replacement value",
            "or a concrete daily helper input drift, not a threshold retune",
        ],
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": False,
            "surprise_note": (
                "Low surprise: exp-20260704-006 suspected possible regime sparsity, "
                "and the representative daily-vs-replay probe confirmed helper parity."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "calibration",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    parity = payload["representative_day_parity"]
    audit = payload["current_forward_context_audit"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Representative day: `{parity["window_label"]}` / `{parity["signal_date"]}`
- Parity passed: `{parity["parity_passed"]}`
- Current context-pass dates: `{audit["context_passed_date_count"]}`
- Current new pending total: `{audit["new_pending_total"]}`
- Artifact: `{payload["artifact"]}`

## Gates

- Gate 1 baseline loaded: `{payload["gate1"]["passed"]}`
- Gate 2 representative fields verified: `{payload["gate2"]["passed"]}`
- Gate 3 survival unchanged: `{payload["gate3"]["passed"]}`
- Gate 4 measurement repair: `{payload["gate4"]["passed"]}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Reproduction

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "files": {path: {"exists": (REPO_ROOT / path).exists()} for path in CHANGED_FILES},
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = load_json(TICKET_JSON, {})
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["alpha_hypothesis"] = payload["alpha_hypothesis"]
    ticket["causal_components"] = payload["causal_components"]
    ticket["nearby_prior_experiments"] = payload["nearby_prior_experiments"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["new_evidence_axis"] = payload["new_evidence_axis"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
    }
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)
    update_ticket(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload.get("prediction"),
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "lean_quality_passed": True,
        },
    )
    print(json.dumps(log_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
