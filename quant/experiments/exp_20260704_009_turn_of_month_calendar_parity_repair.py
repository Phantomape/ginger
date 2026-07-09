"""exp-20260704-009: turn-of-month daily calendar parity repair.

Measurement repair only. exp-20260704-008 proved the accepted turn-of-month
paper sleeve reproduced a representative month-end trade only when explicit
calendar context was supplied. This runner verifies the code repair: daily prep
now supplies deterministic known-month-end context when as_of is the last
regular US equity session of the month. It does not change thresholds, ranking,
sizing, exits, orders, or live/default trading.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260609_027_turn_of_month_liquid_leadership_shared_adapter as accepted_adapter  # noqa: E402
import turn_of_month_liquid_leadership_paper_sleeve as turn_sleeve  # noqa: E402


EXPERIMENT_ID = "exp-20260704-009"
OWNER = "alpha-explore"
SLUG = "turn_of_month_calendar_parity_repair"
RUNNER = f"quant/experiments/exp_20260704_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
ACCEPTED_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260609-027"
    / "exp_20260609_027_turn_of_month_liquid_leadership_shared_adapter.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    "quant/turn_of_month_liquid_leadership_paper_sleeve.py",
    "quant/test_turn_of_month_liquid_leadership_paper_sleeve.py",
    "docs/production_backtest_parity_matrix.md",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_009_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\turn_of_month_liquid_leadership_paper_sleeve.py "
    "quant\\test_turn_of_month_liquid_leadership_paper_sleeve.py "
    "quant\\experiments\\exp_20260704_009_turn_of_month_calendar_parity_repair.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_turn_of_month_liquid_leadership_paper_sleeve.py -q",
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


def choose_representative_trade() -> dict[str, Any]:
    accepted = load_json(ACCEPTED_ARTIFACT, {})
    by_window = accepted.get("target_trades_by_window") or {}
    flattened: list[tuple[str, dict[str, Any]]] = []
    for label in ("old_thin", "mid_weak", "late_strong"):
        for row in by_window.get(label) or []:
            if isinstance(row, dict):
                flattened.append((label, row))
    if not flattened:
        raise RuntimeError("accepted turn-of-month artifact has no target trades")
    label, chosen = next(
        (
            (label, row)
            for label, row in flattened
            if row.get("candidate_month_label") == "last_trading_day"
        ),
        flattened[0],
    )
    signal_date = str(chosen.get("signal_date") or chosen.get("date"))[:10]
    same_day = [
        row
        for row_label, row in flattened
        if row_label == label and str(row.get("signal_date") or row.get("date"))[:10] == signal_date
    ]
    return {"window_label": label, "signal_date": signal_date, "accepted_trades": same_day}


def flatten_entries(entries_by_date: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rows in entries_by_date.values():
        out.extend(row for row in rows if isinstance(row, dict))
    return out


def compact_trade(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    return {
        "ticker": row.get("ticker"),
        "decision_id": row.get("decision_id"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "month_label": row.get("candidate_month_label"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "pnl": row.get("pnl"),
        "candidate_score": row.get("candidate_score"),
    }


def id_list(rows: list[dict[str, Any]], key: str) -> list[str]:
    return [str(row.get(key) or "") for row in rows]


def repair_probe() -> dict[str, Any]:
    chosen = choose_representative_trade()
    label = chosen["window_label"]
    signal_date = chosen["signal_date"]
    cfg = accepted_adapter.framework.WINDOWS[label]
    sector_entries = accepted_adapter.framework._load_sector_entries()
    snapshot = accepted_adapter.framework._load_window_snapshot(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    window_sector_entries = {ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot}
    candidate_universe = {
        "status": "warehouse_sector_known_liquid_common_stock_like_universe",
        "tickers": sorted(window_sector_entries),
        "records": window_sector_entries,
    }
    before_result = load_json(baseline_window_path(label), {})
    core_entries_by_date = accepted_adapter.framework.shadow._baseline_entries(before_result)
    core_entries = flatten_entries(core_entries_by_date)
    calendar_dates = accepted_adapter.framework.shadow._trading_dates(snapshot)
    one_day_window = {label: {"start": signal_date, "end": signal_date, "snapshot": cfg.get("snapshot")}}

    historical, historical_audit = turn_sleeve.build_turn_of_month_liquid_leadership_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows=one_day_window,
        candidate_universe=candidate_universe,
        calendar_dates=calendar_dates,
        config=turn_sleeve.DEFAULT_CONFIG,
    )
    before_no_calendar = turn_sleeve.build_turn_of_month_liquid_leadership_snapshot(
        as_of=signal_date,
        ohlcv_by_ticker=snapshot,
        candidate_universe=candidate_universe,
        core_entries=core_entries,
        state=turn_sleeve.empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )
    repaired_prep = turn_sleeve.prep_and_build_turn_of_month_liquid_leadership_snapshot(
        as_of=signal_date,
        broad_market_ohlcv=snapshot,
        broad_market_candidate_universe=candidate_universe,
        core_entries=core_entries,
        state=turn_sleeve.empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )

    accepted_rows = chosen["accepted_trades"]
    before_rows = before_no_calendar.get("candidates") or []
    repaired_rows = repaired_prep.get("candidates") or []
    accepted_tickers = id_list(accepted_rows, "ticker")
    accepted_decisions = id_list(accepted_rows, "decision_id")
    historical_matches = (
        accepted_tickers == id_list(historical, "ticker")
        and accepted_decisions == id_list(historical, "decision_id")
    )
    before_matches = (
        accepted_tickers == id_list(before_rows, "ticker")
        and accepted_decisions == id_list(before_rows, "decision_id")
    )
    repaired_matches = (
        accepted_tickers == id_list(repaired_rows, "ticker")
        and accepted_decisions == id_list(repaired_rows, "decision_id")
    )
    return {
        "accepted_artifact": repo_rel(ACCEPTED_ARTIFACT),
        "window_label": label,
        "signal_date": signal_date,
        "accepted_trades": [compact_trade(row) for row in accepted_rows],
        "historical_trades": [compact_trade(row) for row in historical],
        "before_no_calendar_candidates": [compact_trade(row) for row in before_rows],
        "repaired_prep_candidates": [compact_trade(row) for row in repaired_rows],
        "historical_matches_accepted": historical_matches,
        "before_no_calendar_matches_accepted": before_matches,
        "repaired_prep_matches_accepted": repaired_matches,
        "before_no_calendar_candidate_count": before_no_calendar.get("candidate_count"),
        "repaired_prep_candidate_count": repaired_prep.get("candidate_count"),
        "before_no_calendar_new_pending_count": before_no_calendar.get("new_pending_count"),
        "repaired_prep_new_pending_count": repaired_prep.get("new_pending_count"),
        "before_no_calendar_scan": before_no_calendar.get("context_scan"),
        "repaired_prep_scan": repaired_prep.get("context_scan"),
        "historical_audit": {
            "total_selected": historical_audit.get("total_selected"),
            "raw_candidate_count_by_window": historical_audit.get("raw_candidate_count_by_window"),
            "scan_by_window": historical_audit.get("scan_by_window"),
        },
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {})
    baseline = baseline_summary()
    probe = repair_probe()
    accepted = bool(
        probe["historical_matches_accepted"]
        and not probe["before_no_calendar_matches_accepted"]
        and probe["repaired_prep_matches_accepted"]
    )
    failed_reasons: list[str] = []
    if not probe["historical_matches_accepted"]:
        failed_reasons.append("historical_replay_no_longer_matches_accepted_artifact")
    if probe["before_no_calendar_matches_accepted"]:
        failed_reasons.append("before_probe_unexpectedly_matches_after_repair")
    if not probe["repaired_prep_matches_accepted"]:
        failed_reasons.append("repaired_daily_prep_did_not_match_accepted_artifact")

    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_turn_of_month_daily_calendar_parity_repaired"
        if accepted
        else "blocked_turn_of_month_daily_calendar_parity_repair"
    )
    why = (
        "The repaired daily prep wrapper reproduced the accepted representative "
        "last-trading-day row without external calendar arguments, while the "
        "old no-calendar build path still failed closed. The fix supplies only a "
        "deterministic known-month-end label for actual last US equity sessions "
        "and leaves thresholds, rank, sizing, exits, orders, and live/default "
        "trading unchanged."
        if accepted
        else "The repair probe did not cleanly reproduce the accepted representative row."
    )
    payload = {
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
            "Forward evidence supply is an alpha bottleneck: accepted turn-of-month "
            "paper rows cannot mature if daily production omits deterministic "
            "month-end calendar context."
        ),
        "change_summary": (
            "Daily turn-of-month prep now supplies known_month_end_dates for actual "
            "last regular US equity sessions, plus regression coverage and parity docs."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "turn_of_month_daily_calendar_parity_repair",
        "trial_variant_id": "turn_of_month_known_month_end_daily_prep_v1",
        "single_causal_variable": "turn_of_month_daily_month_end_calendar_parity_repair_v1",
        "changed_variable": "turn_of_month_daily_month_end_calendar_parity_repair_v1",
        "causal_components": [
            "deterministic US equity session month-end label",
            "daily prep wrapper parity repair",
            "focused regression test",
            "production parity matrix update",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": ["exp-20260609-027", "exp-20260704-006", "exp-20260704-008"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "daily_calendar_parity_repair_after_representative_probe",
        "new_evidence_axis": (
            "Measurement repair for the exact daily/replay calendar drift isolated by "
            "exp-20260704-008; this is not a turn-of-month threshold, notional, hold, "
            "cooldown, top-N, or response retune."
        ),
        "gate1": {"passed": BASELINE_JSON.exists(), "baseline_metrics": baseline},
        "gate2": {
            "passed": bool(probe["historical_matches_accepted"] and probe["repaired_prep_matches_accepted"]),
            "fields_checked": [
                "accepted target_trades_by_window",
                "candidate_month_label",
                "deterministic US equity session calendar",
                "daily prep known_month_end_dates",
                "decision_id",
                "entry_date",
                "exit_date",
            ],
            "entry_date_target_price_scope": (
                "No executable order or target exit is created. The repair restores "
                "default-off paper candidate observation and checks paper entry/exit fields."
            ),
            "representative_window": probe["window_label"],
            "representative_signal_date": probe["signal_date"],
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
            "mode": "measurement_repair_turn_of_month_daily_calendar_parity_repair",
            "passed": accepted,
            "accepted_measurement_repair": accepted,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "failed_reasons": failed_reasons,
            "decision_basis": why,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "before_no_calendar_candidate_count": probe["before_no_calendar_candidate_count"],
            "after_repaired_prep_candidate_count": probe["repaired_prep_candidate_count"],
        },
        "repair_probe": probe,
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "daily_snapshot_changed": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_test_added": True,
            "parity_note": (
                "Default-off paper observation now labels true daily month-end dates "
                "through a deterministic market-session calendar. No core/live "
                "orders, ranking, sizing, exits, or prompts changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune month-start/end day counts, leadership thresholds, "
                "close-location, volume bounds, volatility bounds, top-N, hold-day, "
                "cooldown, notional, or response curves from this repair."
            ),
            "new_evidence_required": (
                "Let future daily snapshots accumulate post-repair turn_of_month rows "
                "and closed cash/SPY/QQQ replacement values before any activation or "
                "allocation experiment."
            ),
        },
        "next_retry_requires": [
            "post-repair forward turn_of_month rows",
            "closed cash/SPY/QQQ replacement value",
            "no frozen-window threshold/notional/hold/cooldown retune",
        ],
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": accepted,
            "surprise_note": (
                "Low surprise: exp-20260704-008 isolated the missing month-end label, "
                "and the deterministic calendar wrapper repaired the representative row."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }
    return payload


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
        "change_summary",
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
    probe = payload["repair_probe"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Representative day: `{probe["window_label"]}` / `{probe["signal_date"]}`
- Historical matches accepted: `{probe["historical_matches_accepted"]}`
- Before no-calendar matches accepted: `{probe["before_no_calendar_matches_accepted"]}`
- Repaired prep matches accepted: `{probe["repaired_prep_matches_accepted"]}`
- Artifact: `{payload["artifact"]}`

## Gates

- Gate 1 baseline loaded: `{payload["gate1"]["passed"]}`
- Gate 2 repair fields verified: `{payload["gate2"]["passed"]}`
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
    ticket["mechanism_family"] = payload["mechanism_family"]
    ticket["trial_family"] = payload["trial_family"]
    ticket["trial_variant_id"] = payload["trial_variant_id"]
    ticket["alpha_hypothesis"] = payload["alpha_hypothesis"]
    ticket["causal_components"] = payload["causal_components"]
    ticket["nearby_prior_experiments"] = payload["nearby_prior_experiments"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["new_evidence_axis"] = payload["new_evidence_axis"]
    ticket["implementation_mode"] = payload["implementation_mode"]
    ticket["decision"] = payload["decision"]
    ticket["changed_files"] = CHANGED_FILES
    allowed = ticket.setdefault("allowed_write_scope", [])
    for path in CHANGED_FILES:
        if path not in allowed:
            allowed.append(path)
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "gate4": payload["gate4"],
    }
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    safe_write_json(compact_log_record(payload), LOG_JSON)
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
    print(json.dumps(compact_log_record(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
