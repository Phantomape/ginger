"""exp-20260613-025: forward options overlay closed-outcome check.

This is an observed-only alpha-search closeout. It reads the shadow options
forward ledger report produced by scripts/run_options_forward_ledger.py and
records whether newly accumulated PIT-safe option-chain rows create enough
closed outcome evidence to promote the overlay. No production strategy,
ranking, sizing, exits, LLM/news path, or order behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import append_log_entry, persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260613-025"
STEM = "options_forward_closed_outcome_overlay"
OWNER = "codex-alpha-explore"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_025_{STEM}.json"
REPORT_JSON = OUT_DIR / "options_forward_candidate_ledger_report.json"
LEDGER_JSONL = OUT_DIR / "options_forward_candidate_ledger.jsonl"
QUALITY_JSON = OUT_DIR / "options_collection_quality_gate.json"
QUARANTINE_JSON = OUT_DIR / "options_quarantined_quote_dates.json"

TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_JSON = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
OHLCV_SNAPSHOT = REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260501_with_pilot.json"
QUANT_SIGNAL_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"
CHAIN_DIR = REPO_ROOT / "data" / "non_ohlcv"

CHANGED_VARIABLE = "forward_options_structure_overlay_closed_outcome_attribution_v1"
TRIAL_FAMILY = "options_forward_closed_outcome_overlay"

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "production_signal_path_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "exits_changed": False,
    "orders_changed": False,
    "trade_enabled": False,
    "daily_snapshot_exposed": False,
    "replay_only": True,
    "default_off_shadow_only": True,
    "parity_test_added": False,
    "live_realism_evaluated": False,
    "live_ready": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: str | Path) -> str:
    value = Path(path)
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _sha256(path: str | Path) -> str | None:
    target = Path(path)
    if not target.exists():
        return None
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _replace_jsonl_entry(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = row["experiment_id"]
    kept: list[str] = []
    if path.exists():
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    existing = json.loads(stripped)
                except json.JSONDecodeError:
                    kept.append(stripped)
                    continue
                if existing.get("experiment_id") != experiment_id:
                    kept.append(stripped)
    kept.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _upsert_experiment_log(row: dict[str, Any]) -> None:
    try:
        append_log_entry(EXPERIMENT_LOG, row)
    except ValueError as exc:
        if "already exists" not in str(exc):
            raise
        _replace_jsonl_entry(EXPERIMENT_LOG, row)


def _baseline_metrics() -> dict[str, Any]:
    payload = _read_json(BASELINE_JSON)
    windows = {}
    for row in payload.get("windows") or []:
        label = row.get("label")
        if not label:
            continue
        windows[label] = {
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
    aggregate = {
        "expected_value_score_sum": round(
            sum((row.get("expected_value_score") or 0.0) for row in payload.get("windows") or []),
            4,
        ),
        "total_pnl_sum": round(
            sum((row.get("total_pnl") or 0.0) for row in payload.get("windows") or []),
            2,
        ),
        "trade_count_sum": sum((row.get("trade_count") or 0) for row in payload.get("windows") or []),
        "signals_generated_sum": sum((row.get("signals_generated") or 0) for row in payload.get("windows") or []),
        "signals_survived_sum": sum((row.get("signals_survived") or 0) for row in payload.get("windows") or []),
    }
    return {"by_window": windows, "aggregate": aggregate, "source": _repo_rel(BASELINE_JSON)}


def _available_dates(pattern: str, prefix: str) -> list[str]:
    dates = []
    for path in sorted(CHAIN_DIR.glob(pattern) if prefix == "options" else QUANT_SIGNAL_DIR.glob(pattern)):
        stem = path.stem
        suffix = stem.rsplit("_", 1)[-1]
        if len(suffix) == 8 and suffix.isdigit():
            dates.append(f"{suffix[:4]}-{suffix[4:6]}-{suffix[6:]}")
    return dates


def _ohlcv_snapshot_span() -> dict[str, Any]:
    payload = _read_json(OHLCV_SNAPSHOT)
    rows_by_ticker = payload.get("ohlcv", {}) if isinstance(payload, dict) else {}
    spans = []
    for ticker, rows in rows_by_ticker.items():
        if not isinstance(rows, list):
            continue
        dates = [
            str(row.get("Date") or row.get("date"))[:10]
            for row in rows
            if isinstance(row, dict) and (row.get("Date") or row.get("date"))
        ]
        if dates:
            spans.append({"ticker": ticker, "start": min(dates), "end": max(dates), "rows": len(dates)})
    return {
        "snapshot": _repo_rel(OHLCV_SNAPSHOT),
        "ticker_count": len(spans),
        "min_start": min((row["start"] for row in spans), default=None),
        "max_end": max((row["end"] for row in spans), default=None),
        "metadata": payload.get("metadata", {}) if isinstance(payload, dict) else {},
    }


def _build_payload() -> dict[str, Any]:
    ticket = _read_json(TICKET_JSON)
    report = _read_json(REPORT_JSON)
    candidate_summary = report.get("candidate_summary") or {}
    outcome = report.get("outcome_close_summary") or {}
    quality_gate = report.get("collection_quality_gate") or {}
    by_quote_date = report.get("by_options_quote_date") or {}
    quote_dates = sorted(by_quote_date)
    chain_dates = _available_dates("options_onclickmedia_chain_*.jsonl", "options")
    signal_dates = _available_dates("quant_signals_*.json", "quant")

    closed_counts = {
        "all_scoring_allowed_5d": (outcome.get("all_scoring_allowed") or {}).get("closed_5d_count"),
        "all_scoring_allowed_10d": (outcome.get("all_scoring_allowed") or {}).get("closed_10d_count"),
        "all_scoring_allowed_20d": (outcome.get("all_scoring_allowed") or {}).get("closed_20d_count"),
        "all_scoring_allowed_60d": (outcome.get("all_scoring_allowed") or {}).get("closed_60d_count"),
        "squeeze_20d": (outcome.get("squeeze_overlay") or {}).get("closed_20d_count"),
        "downside_20d": (outcome.get("downside_risk_overlay") or {}).get("closed_20d_count"),
    }
    any_closed = any((value or 0) > 0 for value in closed_counts.values())
    slot_conflict = outcome.get("slot_conflict") or {}
    slot_conflict_count = sum(
        (slot_conflict.get(key) or {}).get("conflict_count") or 0
        for key in ("squeeze_overlay", "downside_risk_overlay")
    )

    decision = "shadow_only_no_closed_outcomes"
    status = "observed_only"
    realized_failure_mode = "still_thin_closed_outcomes"
    if any_closed and slot_conflict_count > 0:
        decision = "shadow_only_forward_evidence_present_but_not_promoted"
        realized_failure_mode = "prior_overlay_rejection_persists"

    ohlcv_span = _ohlcv_snapshot_span()
    timestamp = _utc_now()
    ledger_command_dates = " ".join(f"--date {date}" for date in chain_dates)
    ledger_command = (
        ".\\.venv\\Scripts\\python.exe -B scripts\\run_options_forward_ledger.py "
        f"--experiment-id {EXPERIMENT_ID} "
        f"--output-dir data\\experiments\\{EXPERIMENT_ID} "
        "--ohlcv-snapshot data\\ohlcv\\ohlcv_snapshot_20251023_20260501_with_pilot.json "
        f"{ledger_command_dates}"
    )

    gate4 = {
        "applicable": False,
        "passed": False,
        "decision": decision,
        "reason": (
            "No strategy, replay policy, production path, ranking, sizing, entry, exit, "
            "or LLM behavior changed. The shadow overlay has zero closed 5/10/20/60d "
            "outcomes and zero slot-conflict examples."
        ),
        "promotion_blockers": [
            "closed_5d_10d_20d_60d_counts_all_zero",
            "slot_conflict_count_zero",
            "current_ohlcv_snapshot_ends_2026_05_01_before_option_signal_dates",
            "vendor_asof_unavailable_for_historical_replay",
            "earnings_iv_flag_not_wired",
            "short_interest_or_borrow_join_not_wired",
        ],
    }

    calibration = {
        "actual_decision": status,
        "actual_success": None,
        "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
        "brier_score": None,
        "calibration_direction": "not_scored_observed_only",
        "surprise_level": "not_scored",
        "expected_ev_delta": (ticket.get("prediction") or {}).get("expected_ev_delta"),
        "actual_ev_delta": None,
        "ev_prediction_error": None,
        "expected_pnl_delta": (ticket.get("prediction") or {}).get("expected_pnl_delta"),
        "actual_pnl_delta": None,
        "pnl_prediction_error": None,
        "predicted_failure_modes": (ticket.get("prediction") or {}).get("main_failure_modes") or [],
        "realized_failure_mode": realized_failure_mode,
        "predicted_failure_mode_hit": realized_failure_mode in ((ticket.get("prediction") or {}).get("main_failure_modes") or []),
        "surprise_note": (
            "Coverage improved from the May 15 audit, but the only available OHLCV snapshot "
            "still ends on 2026-05-01, so no option-tagged candidate has closed forward returns."
        ),
    }

    post_run_reflection = {
        "why_result_happened": (
            "The options collection matured to 29 real quote-date files and 85 joined candidates, "
            "but the outcome source did not mature with it. The ledger shows 84 rows where the "
            "candidate signal date is missing from OHLCV and one row with no ticker OHLCV snapshot, "
            "so the overlay has no closed forward returns or slot-conflict value."
        ),
        "realized_failure_mode": realized_failure_mode,
        "forbidden_near_neighbor_retry": (
            "Do not retune options squeeze/downside thresholds, same-day joins, quote-date joins, "
            "or standalone options entries on this frozen sample. Do not promote without closed "
            "forward outcomes and PIT-safe joins."
        ),
        "new_evidence_required": (
            "A retry requires an OHLCV/outcome snapshot covering at least 20 trading days after "
            "May-June 2026 candidate dates, plus PIT-safe short-interest/borrow and earnings-date "
            "joins before squeeze or earnings-vol tags can be production candidates."
        ),
    }

    after_metrics = {
        "expected_value_score": None,
        "total_pnl": None,
        "total_return": None,
        "sharpe_daily": None,
        "max_drawdown": None,
        "win_rate": None,
        "trade_count": None,
        "signals_generated": None,
        "signals_survived": None,
        "survival_rate": None,
        "vs_spy": None,
        "vs_qqq": None,
        "candidate_count": candidate_summary.get("candidate_count"),
        "overlap_with_existing_signals": candidate_summary.get("candidate_count"),
        "options_covered_candidates": candidate_summary.get("options_covered_candidates"),
        "options_scoring_allowed_candidates": candidate_summary.get("options_scoring_allowed_candidates"),
        "pit_join_safe_candidates": candidate_summary.get("pit_join_safe_candidates"),
        "pit_join_safe_rate": candidate_summary.get("pit_join_safe_rate"),
        "squeeze_overlay_candidates": candidate_summary.get("squeeze_overlay_candidates"),
        "downside_risk_overlay_candidates": candidate_summary.get("downside_risk_overlay_candidates"),
        "closed_forward_counts": closed_counts,
        "slot_conflict_count": slot_conflict_count,
        "production_impact": "none_default_off_shadow_artifact_only",
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "lane": "alpha_search",
        "run_type": "observed_only_shadow_experiment",
        "hypothesis": ticket.get("hypothesis"),
        "change_type": ticket.get("change_type"),
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": ticket.get("causal_components") or [],
        "prior_trial_count": 0,
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments") or [],
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "prediction": ticket.get("prediction"),
        "calibration": calibration,
        "gate_questions": {
            "1_alpha_hypothesis": (
                "PIT-safe EOD options IV/skew/OI structure may explain quality differences "
                "among existing Ginger candidates as a default-off overlay."
            ),
            "2_history_check": (
                "exp-20260506-009 rejected PIT-unsafe historical promotion; exp-20260515-099 "
                "stayed shadow-only because no forward outcomes were closed."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Promotion would require nonzero closed 5/10/20/60d outcomes, positive scarce-slot "
                "value, PIT-safe joins, and no production/backtest inconsistency."
            ),
            "5_reproducibility": ledger_command,
        },
        "historical_experiment_check": {
            "prior_options_records": [
                "exp-20260503-044 / exp-20260504-043 / exp-20260505-021: no usable structured options data or no new data.",
                "exp-20260506-003: initial OnClickMedia options harness.",
                "exp-20260506-009: rejected historical overlay promotion as PIT-unsafe with weak slot value.",
                "exp-20260515-099: clean forward ledger through 2026-05-14 stayed shadow-only with zero closed outcomes.",
            ],
            "finding": (
                "This run adds later May-June option rows and candidate joins, but does not introduce "
                "a new options threshold, production rule, or standalone entry mechanism."
            ),
        },
        "data_availability": {
            "chain_files": report.get("source_files", {}).get("chain_files", []),
            "chain_file_count": len(report.get("source_files", {}).get("chain_files", [])),
            "quote_date_range": {"start": quote_dates[0] if quote_dates else None, "end": quote_dates[-1] if quote_dates else None},
            "quant_signal_date_range": {
                "start": signal_dates[0] if signal_dates else None,
                "end": signal_dates[-1] if signal_dates else None,
                "count": len(signal_dates),
            },
            "ohlcv_snapshot_span": ohlcv_span,
            "pit_status": (
                "Forward option rows carry usable_trade_date and pit_safe flags; candidate joins use "
                "usable_trade_date. vendor_asof_available remains absent, so historical same-date "
                "promotion remains biased."
            ),
            "earnings_date_alignment": "Earnings IV flag remains not wired.",
            "short_interest_linkage": "No PIT-safe short-interest, borrow-fee, or shares-available join is wired.",
        },
        "collection_quality_gate": {
            "overall_status": quality_gate.get("overall_status"),
            "usable_quote_dates": quality_gate.get("usable_quote_dates"),
            "quarantined_quote_dates": quality_gate.get("quarantined_quote_dates"),
            "latest_quote_date_quality": (quality_gate.get("by_quote_date") or {}).get(quote_dates[-1]) if quote_dates else None,
        },
        "baseline_metrics": _baseline_metrics(),
        "before_metrics": {
            "expected_value_score": None,
            "total_pnl": None,
            "reason": "No executable strategy or replay baseline changed; accepted core context is recorded separately.",
        },
        "after_metrics": after_metrics,
        "delta_metrics": {
            "expected_value_score_delta": None,
            "total_pnl_delta": None,
            "reason": "No strategy replay, production path, ranking, sizing, slot, stop, target, or LLM behavior changed.",
        },
        "shadow_metrics": {
            **candidate_summary,
            "forward_return_of_tagged_candidates": {
                "all_scoring_allowed": outcome.get("all_scoring_allowed"),
                "squeeze_overlay": outcome.get("squeeze_overlay"),
                "no_squeeze_overlay": outcome.get("no_squeeze_overlay"),
                "downside_risk_overlay": outcome.get("downside_risk_overlay"),
                "no_downside_risk_overlay": outcome.get("no_downside_risk_overlay"),
                "squeeze_minus_no_squeeze_forward_20d": outcome.get("squeeze_minus_no_squeeze_forward_20d"),
                "downside_minus_no_downside_forward_20d": outcome.get("downside_minus_no_downside_forward_20d"),
            },
            "scarce_slot_opportunity_cost": slot_conflict,
            "by_options_quote_date": by_quote_date,
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "live_realistic_execution_envelope": {
            "evaluated": False,
            "reason": "Observed-only shadow ledger; no executable alpha or default-off production adapter was promoted.",
            "live_ready": False,
        },
        "post_run_reflection": post_run_reflection,
        "next_retry_requires": [
            "OHLCV/outcome snapshot covering May-June 2026 signal dates plus at least 20 forward trading days.",
            "Nonzero closed 5/10/20/60d outcomes for options_scoring_allowed rows.",
            "Positive scarce-slot conflict value versus same-day entered candidates.",
            "PIT-safe short-interest or borrow join before squeeze interpretation.",
            "PIT-safe earnings-date/IV join before earnings-vol overlay interpretation.",
        ],
        "rejection_reason": (
            "No production promotion: all closed forward counts are zero and slot-conflict count is zero."
        ),
        "artifacts": {
            "summary": _repo_rel(OUT_JSON),
            "report": _repo_rel(REPORT_JSON),
            "ledger": _repo_rel(LEDGER_JSONL),
            "quality_gate": _repo_rel(QUALITY_JSON),
            "quarantined_quote_dates": _repo_rel(QUARANTINE_JSON),
            "log": _repo_rel(LOG_JSON),
            "card": _repo_rel(CARD_MD),
            "ticket": _repo_rel(TICKET_JSON),
            "manifest": _repo_rel(MANIFEST_JSON),
        },
        "commands": {
            "ledger": ledger_command,
            "runner": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260613_025_options_forward_closed_outcome_overlay.py",
            "audit": ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        },
        "anti_js": "No JavaScript was used.",
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Refreshed the PIT-safe OnClickMedia options forward overlay ledger through "
            "2026-06-12 and checked whether closed candidate outcomes now exist."
        ),
        "change_type": payload["change_type"],
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": (
            "scripts/run_options_forward_ledger.py output artifacts; "
            "quant/experiments/exp_20260613_025_options_forward_closed_outcome_overlay.py"
        ),
        "parameters": {
            "candidate_join_date_mode": "usable_trade_date",
            "options_quote_date_range": payload["data_availability"]["quote_date_range"],
            "quality_gate": {
                "min_liquidity_pass_rate": 0.05,
                "min_liquid_tickers": 10,
                "min_market_rows_rate": 0.50,
            },
            "production_change_allowed": False,
            "standalone_entries_generated": 0,
        },
        "date_range": payload["data_availability"]["quote_date_range"],
        "secondary_windows": [],
        "market_regime_summary": {},
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "shadow_metrics": payload["shadow_metrics"],
        "baseline_metrics": payload["baseline_metrics"],
        "llm_metrics": {"used_llm": False},
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "gate4": payload["gate4"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": list(payload["artifacts"].values()),
        "commands": payload["commands"],
        "anti_js": payload["anti_js"],
        "notes": (
            "Coverage improved to 85 candidate rows and 14 scoring-allowed rows, but "
            "closed 5/10/20/60d counts remain zero because OHLCV outcomes stop at 2026-05-01."
        ),
    }


def _build_card(payload: dict[str, Any]) -> str:
    shadow = payload["shadow_metrics"]
    outcome = shadow["forward_return_of_tagged_candidates"]
    all_scoring = outcome.get("all_scoring_allowed") or {}
    quote_range = payload["data_availability"]["quote_date_range"]
    return "\n".join([
        "---",
        f"experiment_id: {json.dumps(EXPERIMENT_ID)}",
        f"status: {json.dumps(payload['status'])}",
        f"lane: {json.dumps(payload['lane'])}",
        f"change_type: {json.dumps(payload['change_type'])}",
        f"mechanism_family: {json.dumps(payload['mechanism_family'])}",
        f"trial_family: {json.dumps(payload['trial_family'])}",
        f"changed_variable: {json.dumps(payload['changed_variable'])}",
        "tags:",
        "  - alpha_search",
        "  - observed_only",
        "  - non_ohlcv_options_structure_overlay",
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Hypothesis",
        "",
        str(payload["hypothesis"]),
        "",
        "## Result",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Quote dates: `{quote_range.get('start')}` to `{quote_range.get('end')}`",
        f"- Candidate rows: `{shadow.get('candidate_count')}`",
        f"- Scoring-allowed rows: `{shadow.get('options_scoring_allowed_candidates')}`",
        f"- Closed 5d / 10d / 20d / 60d: `{all_scoring.get('closed_5d_count')}` / `{all_scoring.get('closed_10d_count')}` / `{all_scoring.get('closed_20d_count')}` / `{all_scoring.get('closed_60d_count')}`",
        "- Production impact: none; shadow-only artifact.",
        "",
        "## Reflection",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Next Evidence",
        "",
        "\n".join(f"- {item}" for item in payload["next_retry_requires"]),
        "",
        "## Reproduction",
        "",
        "```powershell",
        payload["commands"]["ledger"],
        payload["commands"]["runner"],
        "```",
        "",
    ])


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "status": payload["status"],
        "accepted": False,
        "accepted_alpha": False,
        "artifact": _repo_rel(OUT_JSON),
        "report": _repo_rel(REPORT_JSON),
        "ledger": _repo_rel(LEDGER_JSONL),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "numeric_gate4_passed": False,
        "shadow_metrics": {
            "candidate_count": payload["shadow_metrics"].get("candidate_count"),
            "options_scoring_allowed_candidates": payload["shadow_metrics"].get("options_scoring_allowed_candidates"),
            "closed_forward_counts": payload["after_metrics"].get("closed_forward_counts"),
            "slot_conflict_count": payload["after_metrics"].get("slot_conflict_count"),
        },
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "calibration": payload["calibration"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": log_record["notes"],
        "artifact": _repo_rel(OUT_JSON),
        "report": _repo_rel(REPORT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        REPORT_JSON,
        LEDGER_JSONL,
        QUALITY_JSON,
        QUARANTINE_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": _utc_now(),
        "anti_js": payload["anti_js"],
        "allowed_write_scope": [_repo_rel(path) for path in paths] + [_repo_rel(MANIFEST_JSON)],
        "file_hashes": {_repo_rel(path): _sha256(path) for path in paths if path.exists()},
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_experiment_log(log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_build_log_record(payload), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
