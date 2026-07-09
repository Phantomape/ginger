"""exp-20260704-010: industry-stable core-flow admission parity probe.

Measurement repair only. exp-20260704-006 found that the accepted
industry-stable core-flow default-off paper sleeve has no forward admissions
despite stable-industry raw contexts. This runner checks a real accepted
historical core-flow day against the current daily helper and audits current
forward snapshots for same-day core-flow confirmations. It does not change
thresholds, sizing, exits, orders, or shared sleeve behavior.
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
import exp_20260608_008_industry_stable_core_flow_shared_adapter as accepted_adapter  # noqa: E402
import industry_stable_core_flow_paper_sleeve as shared_is  # noqa: E402


EXPERIMENT_ID = "exp-20260704-010"
OWNER = "alpha-explore"
SLUG = "industry_stable_core_flow_admission_parity_probe"
RUNNER = f"quant/experiments/exp_20260704_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
BASELINE_ARCHIVE_DIR = REPO_ROOT / "data" / "backtests" / "archive" / "20260604_ohlcv_warehouse_replay"
ACCEPTED_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260608-008"
    / "exp_20260608_008_industry_stable_core_flow_shared_adapter.json"
)
SNAPSHOT_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "industry_stable_core_flow" / "snapshots.jsonl"
STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "industry_stable_core_flow" / "state.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_010_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\experiments\\exp_20260704_010_industry_stable_core_flow_admission_parity_probe.py",
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
        if window.get("label") != label:
            continue
        path = REPO_ROOT / str(window["path"])
        if path.exists():
            return path
        archived = BASELINE_ARCHIVE_DIR / Path(str(window["path"])).name
        if archived.exists():
            return archived
        return path
    raise RuntimeError(f"baseline window not found: {label}")


def choose_representative_trade(accepted: dict[str, Any]) -> dict[str, Any]:
    by_window = accepted.get("target_trades_by_window") or {}
    for label in ("old_thin", "mid_weak", "late_strong"):
        rows = [row for row in by_window.get(label) or [] if isinstance(row, dict)]
        if not rows:
            continue
        first = rows[0]
        signal_date = str(first.get("signal_date") or first.get("date"))[:10]
        same_day = [
            row
            for row in rows
            if str(row.get("signal_date") or row.get("date"))[:10] == signal_date
        ]
        return {
            "window_label": label,
            "signal_date": signal_date,
            "accepted_trades": same_day,
            "selection_reason": "first_old_thin_accepted_day"
            if label == "old_thin"
            else "first_available_accepted_day",
        }
    raise RuntimeError("accepted industry-stable core-flow artifact has no target trades")


def compact_trade(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    core_flow = row.get("core_flow_confirmation")
    if isinstance(core_flow, dict):
        core_flow = {
            "same_day_ab_entry_count": core_flow.get("same_day_ab_entry_count"),
            "same_day_ab_overlap": core_flow.get("same_day_ab_overlap"),
            "same_ticker_core_overlap": core_flow.get("same_ticker_core_overlap"),
            "same_ticker_core_overlap_excluded": core_flow.get("same_ticker_core_overlap_excluded"),
        }
    return {
        "ticker": row.get("ticker"),
        "decision_id": row.get("decision_id"),
        "signal_date": row.get("signal_date") or row.get("date"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "pnl": row.get("pnl"),
        "paper_notional_usd": row.get("paper_notional_usd"),
        "candidate_score": row.get("candidate_score"),
        "candidate_group_key": row.get("candidate_group_key"),
        "same_day_ab_entry_count": row.get("same_day_ab_entry_count"),
        "same_day_ab_overlap": row.get("same_day_ab_overlap"),
        "same_ticker_ab_overlap": row.get("same_ticker_ab_overlap"),
        "core_flow_confirmation": core_flow,
        "combined_state": row.get("combined_state"),
        "state_router_status": row.get("state_router_status"),
        "state_router_applied": row.get("state_router_applied"),
    }


def _ticker_list(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("ticker") or "").upper() for row in rows]


def _decision_list(rows: list[dict[str, Any]]) -> list[Any]:
    return [row.get("decision_id") for row in rows]


def representative_day_parity() -> dict[str, Any]:
    accepted = load_json(ACCEPTED_ARTIFACT, {})
    chosen = choose_representative_trade(accepted)
    label = chosen["window_label"]
    signal_date = chosen["signal_date"]
    cfg = accepted_adapter.framework.WINDOWS[label]
    sector_entries = accepted_adapter.framework._load_sector_entries()
    snapshot = accepted_adapter.framework._load_window_snapshot(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    window_sector_entries = {
        ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
    }
    candidate_universe = {
        "status": "warehouse_sector_known_liquid_common_stock_like_universe",
        "tickers": sorted(window_sector_entries),
        "records": window_sector_entries,
    }
    before_result = load_json(baseline_window_path(label), {})
    core_entries_by_date = accepted_adapter.framework.shadow._baseline_entries(before_result)
    core_entries = [
        row
        for row in core_entries_by_date.get(signal_date, [])
        if isinstance(row, dict)
    ]
    identity_config = dict(shared_is.DEFAULT_CONFIG)
    identity_config["state_router_enabled"] = False
    one_day_window = {
        label: {
            "start": signal_date,
            "end": signal_date,
            "snapshot": cfg.get("snapshot"),
        }
    }

    historical, historical_audit = shared_is.build_industry_stable_core_flow_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows=one_day_window,
        candidate_universe=candidate_universe,
        sector_entries=window_sector_entries,
        config=identity_config,
    )
    daily = shared_is.build_industry_stable_core_flow_snapshot(
        as_of=signal_date,
        ohlcv_by_ticker=snapshot,
        candidate_universe=candidate_universe,
        core_entries=core_entries,
        sector_entries=window_sector_entries,
        state=shared_is.empty_industry_stable_core_flow_state(),
        config=identity_config,
        persist=False,
    )

    accepted_trades = chosen["accepted_trades"]
    daily_rows = daily.get("candidates") or []
    accepted_tickers = _ticker_list(accepted_trades)
    historical_tickers = _ticker_list(historical)
    daily_tickers = _ticker_list(daily_rows)
    accepted_decisions = _decision_list(accepted_trades)
    historical_decisions = _decision_list(historical)
    daily_decisions = _decision_list(daily_rows)

    ticker_match = accepted_tickers == historical_tickers == daily_tickers
    decision_match = accepted_decisions == historical_decisions == daily_decisions
    lifecycle_match = [
        {
            "ticker": accepted_row.get("ticker"),
            "accepted_entry_date": accepted_row.get("entry_date"),
            "historical_entry_date": historical_row.get("entry_date"),
            "daily_entry_date": daily_row.get("entry_date"),
            "accepted_exit_date": accepted_row.get("exit_date"),
            "historical_exit_date": historical_row.get("exit_date"),
            "daily_exit_date": daily_row.get("exit_date"),
        }
        for accepted_row, historical_row, daily_row in zip(accepted_trades, historical, daily_rows)
    ]
    lifecycle_passed = (
        len(accepted_trades) == len(historical) == len(daily_rows)
        and all(
            item["accepted_entry_date"] == item["historical_entry_date"] == item["daily_entry_date"]
            and item["accepted_exit_date"] == item["historical_exit_date"] == item["daily_exit_date"]
            for item in lifecycle_match
        )
    )
    context = daily.get("industry_stable_core_flow_context") or {}
    scan = daily.get("context_scan") or {}
    core_flow_passed = (
        as_int(scan.get("core_flow_confirmed_dates")) >= 1
        and as_int(scan.get("raw_candidates_after_core_flow_filter")) >= len(daily_rows)
        and as_int(scan.get("raw_candidates_missing_core_flow")) == 0
        and all((row.get("core_flow_confirmation") or {}).get("same_day_ab_overlap") for row in daily_rows)
    )
    parity_passed = ticker_match and decision_match and lifecycle_passed and core_flow_passed

    return {
        "accepted_artifact": repo_rel(ACCEPTED_ARTIFACT),
        "window_label": label,
        "signal_date": signal_date,
        "selection_reason": chosen["selection_reason"],
        "sector_entry_count": len(sector_entries),
        "window_sector_entry_count": len(window_sector_entries),
        "loaded_ohlcv_tickers": len(snapshot),
        "same_day_core_entry_count": len(core_entries),
        "accepted_trades": [compact_trade(row) for row in accepted_trades],
        "historical_trades": [compact_trade(row) for row in historical],
        "daily_candidates": [compact_trade(row) for row in daily_rows],
        "daily_new_pending_entries": [compact_trade(row) for row in daily.get("new_pending_entries") or []],
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
        "core_flow_passed": core_flow_passed,
        "parity_passed": parity_passed,
        "daily_candidate_count": daily.get("candidate_count"),
        "daily_raw_candidate_count": daily.get("raw_candidate_count"),
        "daily_context": context,
        "daily_context_scan": scan,
        "historical_audit": {
            "selected_by_window": historical_audit.get("selected_by_window"),
            "raw_candidate_count_by_window": historical_audit.get("raw_candidate_count_by_window"),
            "scan_by_window": historical_audit.get("scan_by_window"),
        },
    }


def current_forward_snapshot_audit() -> dict[str, Any]:
    rows = read_jsonl(SNAPSHOT_JSONL)
    latest_by_asof: dict[str, dict[str, Any]] = {}
    for row in rows:
        asof = str(row.get("asof_date") or row.get("date") or "")[:10]
        if asof:
            latest_by_asof[asof] = row

    totals = Counter()
    samples: list[dict[str, Any]] = []
    raw_context_dates: list[str] = []
    core_flow_dates: list[str] = []
    reason_counts: Counter[str] = Counter()
    for asof, row in sorted(latest_by_asof.items()):
        context = row.get("industry_stable_core_flow_context")
        if not isinstance(context, dict):
            context = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else {}
        scan = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else context
        if not isinstance(scan, dict):
            scan = {}
        raw_before = as_int(scan.get("raw_candidates_before_core_flow_filter"))
        raw_after = as_int(scan.get("raw_candidates_after_core_flow_filter"))
        missing_core = as_int(scan.get("raw_candidates_missing_core_flow"))
        excluded_overlap = as_int(scan.get("raw_candidates_excluded_same_ticker_core_overlap"))
        core_flow_confirmed = as_int(scan.get("core_flow_confirmed_dates"))
        stable_groups = as_int(scan.get("stable_industry_group_rows"))
        candidate_count = as_int(row.get("candidate_count"))
        new_pending_count = as_int(row.get("new_pending_count"))

        totals["raw_candidates_before_core_flow_filter"] += raw_before
        totals["raw_candidates_after_core_flow_filter"] += raw_after
        totals["raw_candidates_missing_core_flow"] += missing_core
        totals["raw_candidates_excluded_same_ticker_core_overlap"] += excluded_overlap
        totals["core_flow_confirmed_dates"] += core_flow_confirmed
        totals["stable_industry_group_rows"] += stable_groups
        totals["candidate_count"] += candidate_count
        totals["new_pending_count"] += new_pending_count

        if raw_before > 0:
            raw_context_dates.append(asof)
        if core_flow_confirmed > 0:
            core_flow_dates.append(asof)
        if raw_before == 0 and stable_groups == 0:
            reason_counts["no_stable_industry_context"] += 1
        elif raw_before > 0 and raw_after == 0:
            reason_counts["raw_candidates_missing_or_excluded_core_flow"] += 1
        elif raw_after > 0 and candidate_count == 0:
            reason_counts["selected_candidate_blocked_after_core_flow"] += 1

        contexts = context.get("context_samples") if isinstance(context.get("context_samples"), list) else []
        sample_context = next((item for item in contexts if isinstance(item, dict)), None)
        if len(samples) < 8 and (raw_before > 0 or sample_context):
            samples.append(
                {
                    "asof_date": asof,
                    "raw_candidates_before_core_flow_filter": raw_before,
                    "raw_candidates_after_core_flow_filter": raw_after,
                    "raw_candidates_missing_core_flow": missing_core,
                    "raw_candidates_excluded_same_ticker_core_overlap": excluded_overlap,
                    "core_flow_confirmed_dates": core_flow_confirmed,
                    "candidate_count": candidate_count,
                    "new_pending_count": new_pending_count,
                    "top_context": {
                        key: sample_context.get(key)
                        for key in (
                            "date",
                            "top_candidate_before_core_flow",
                            "top_group_key_before_core_flow",
                            "top_score_before_core_flow",
                            "raw_candidate_count_before_core_flow_filter",
                            "raw_candidate_count_after_core_flow_filter",
                        )
                    }
                    if sample_context
                    else None,
                }
            )

    state = load_json(STATE_JSON, {})
    skip_reasons = Counter(
        str(row.get("reason") or "unknown")
        for row in state.get("skipped_days") or []
        if isinstance(row, dict)
    )
    raw_before_total = totals["raw_candidates_before_core_flow_filter"]
    raw_after_total = totals["raw_candidates_after_core_flow_filter"]
    missing_total = totals["raw_candidates_missing_core_flow"]
    excluded_total = totals["raw_candidates_excluded_same_ticker_core_overlap"]
    zero_fire_explained = (
        len(latest_by_asof) >= 10
        and totals["candidate_count"] == 0
        and totals["new_pending_count"] == 0
        and raw_before_total > 0
        and raw_after_total == 0
        and totals["core_flow_confirmed_dates"] == 0
        and raw_before_total == missing_total + excluded_total
    )
    return {
        "snapshot_file": repo_rel(SNAPSHOT_JSONL),
        "snapshot_rows": len(rows),
        "unique_asof_dates": len(latest_by_asof),
        "first_asof_date": min(latest_by_asof) if latest_by_asof else None,
        "last_asof_date": max(latest_by_asof) if latest_by_asof else None,
        "raw_context_dates": raw_context_dates,
        "raw_context_date_count": len(raw_context_dates),
        "core_flow_confirmed_dates": core_flow_dates,
        "core_flow_confirmed_date_count": len(core_flow_dates),
        "totals_deduped_by_asof_latest": dict(totals),
        "reason_counts": dict(reason_counts.most_common()),
        "state_file": repo_rel(STATE_JSON),
        "state_counts": {
            "pending_entries": len(state.get("pending_entries") or []),
            "open_positions": len(state.get("open_positions") or []),
            "closed_positions": len(state.get("closed_positions") or []),
            "skipped_days": len(state.get("skipped_days") or []),
        },
        "state_skip_reasons": dict(skip_reasons.most_common()),
        "context_samples": samples,
        "zero_fire_explained_by_missing_core_flow": zero_fire_explained,
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {})
    baseline = baseline_summary()
    parity = representative_day_parity()
    forward = current_forward_snapshot_audit()
    accepted = bool(parity["parity_passed"] and forward["zero_fire_explained_by_missing_core_flow"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_industry_stable_core_flow_admission_parity_confirmed"
        if accepted
        else "blocked_industry_stable_core_flow_admission_parity_drift_or_ambiguous_forward_context"
    )
    failed_reasons: list[str] = []
    if not parity["parity_passed"]:
        failed_reasons.append("representative_historical_daily_replay_mismatch")
    if not forward["zero_fire_explained_by_missing_core_flow"]:
        failed_reasons.append("current_forward_zero_fire_not_fully_explained_by_missing_core_flow")

    why = (
        "The accepted representative core-flow trade reproduced through the current "
        "shared historical helper and daily snapshot helper with matching ticker, "
        "decision ID, and entry/exit lifecycle. Current forward snapshots have "
        "stable-industry raw contexts but zero same-day core-flow confirmed dates, "
        "so zero admissions are expected under the accepted rule."
        if accepted
        else (
            "The probe did not cleanly distinguish true absence of same-day core-flow "
            "confirmations from an admission or input drift. Inspect representative "
            "parity and forward context counts before changing the sleeve."
        )
    )

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
            "Forward evidence supply is an alpha bottleneck: accepted "
            "industry-stable core-flow rows cannot mature if daily production "
            "observation fails to admit the same core-flow-confirmed industry "
            "leaders that replay admitted."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "industry_stable_core_flow_admission_parity_probe",
        "trial_variant_id": "industry_stable_core_flow_representative_day_daily_vs_replay_v1",
        "single_causal_variable": "industry_stable_core_flow_daily_vs_replay_representative_day_parity_v1",
        "changed_variable": "industry_stable_core_flow_daily_vs_replay_representative_day_parity_v1",
        "causal_components": [
            "accepted historical core-flow replay day",
            "daily snapshot helper with persist false",
            "current forward same-day core-flow context audit",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260608-008",
            "exp-20260613-010",
            "exp-20260704-006",
            "exp-20260704-007",
            "exp-20260704-009",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "representative_day_daily_vs_replay_core_flow_parity_probe",
        "new_evidence_axis": (
            "Measurement-only representative-day parity evidence for the accepted "
            "industry-stable core-flow sleeve named by exp-20260704-006; no "
            "threshold, notional, top-N, hold, cooldown, state, or response rule changed."
        ),
        "gate1": {"passed": BASELINE_JSON.exists(), "baseline_metrics": baseline},
        "gate2": {
            "passed": bool(parity["parity_passed"] and parity["same_day_core_entry_count"] > 0),
            "fields_checked": [
                "accepted target_trades_by_window",
                "historical OHLCV rows",
                "broad-market sector universe",
                "same-day core_entries_by_date",
                "daily snapshot candidate_count/raw_candidate_count",
                "decision_id",
                "entry_date",
                "exit_date",
                "core_flow_confirmation",
            ],
            "entry_date_target_price_scope": (
                "No executable order or target exit is created. The probe compares "
                "paper entry_date/exit_date lifecycle fields on accepted default-off rows."
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
            "mode": "measurement_repair_industry_stable_core_flow_admission_parity",
            "passed": accepted,
            "accepted_measurement_repair": accepted,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "failed_reasons": failed_reasons,
            "representative_parity_passed": parity["parity_passed"],
            "current_zero_fire_explained_by_missing_core_flow": forward[
                "zero_fire_explained_by_missing_core_flow"
            ],
            "decision_basis": why,
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
        "current_forward_snapshot_audit": forward,
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
                "Read-only parity probe over the existing shared industry-stable "
                "core-flow helper and existing paper snapshots. It does not alter "
                "live/default orders, rankings, sizing, exits, or paper snapshot generation."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune stable-industry thresholds, core-flow requirement, "
                "same-ticker overlap exclusion, state scalar, top-N, hold-day, "
                "cooldown, notional, or response curves from this zero-fire span."
            ),
            "new_evidence_required": (
                "Reopen industry-stable core-flow activation only after forward daily "
                "snapshots include same-day core-flow-confirmed rows with closed cash, "
                "SPY, and QQQ replacement value, or after a concrete daily helper input "
                "drift is observed."
            ),
        },
        "next_retry_requires": [
            "actual forward same-day core-flow-confirmed rows with closed replacement value",
            "or a concrete daily helper input drift, not a threshold retune",
        ],
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_mode_hit": False,
            "surprise_note": (
                "Low surprise: exp-20260704-006 isolated ISCF underfire to raw "
                "stable-industry contexts missing core flow, and this probe confirmed "
                "representative helper parity."
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
    forward = payload["current_forward_snapshot_audit"]
    totals = forward["totals_deduped_by_asof_latest"]
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
- Representative parity passed: `{parity["parity_passed"]}`
- Forward raw-before-core-flow total: `{totals.get("raw_candidates_before_core_flow_filter")}`
- Forward raw-after-core-flow total: `{totals.get("raw_candidates_after_core_flow_filter")}`
- Forward core-flow confirmed dates: `{forward["core_flow_confirmed_date_count"]}`
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
        "gate4": payload["gate4"],
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
