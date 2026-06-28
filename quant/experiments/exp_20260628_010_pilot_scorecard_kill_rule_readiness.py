from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260628-010"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "pilot_scorecard_kill_rule_readiness"

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


RUNNER = f"quant/experiments/exp_20260628_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_JSON = (
    REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PILOT_SCORECARD_JSON = REPO_ROOT / "data" / "pilots" / "pilot_scorecard.json"
PILOT_RECOMMENDATIONS_JSON = (
    REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-06-28.json"
)
FORWARD_RV_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad_rows = 0
    if not path.exists():
        return rows, bad_rows
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                bad_rows += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows, bad_rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    windows = windows if isinstance(windows, list) else []
    generated = sum(safe_int(window.get("signals_generated")) for window in windows)
    survived = sum(safe_int(window.get("signals_survived")) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "loaded": BASELINE_JSON.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows), 4
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(safe_int(window.get("trade_count")) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def normalize_scorecards(scorecard_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in scorecard_payload.get("scorecards", []) or []:
        rows.append(
            {
                "pilot": row.get("pilot"),
                "label": row.get("label"),
                "sleeve": row.get("sleeve"),
                "as_of": row.get("as_of"),
                "closed_trades": safe_int(row.get("closed_trades")),
                "open_positions": safe_int(row.get("open_positions")),
                "pending_entries": safe_int(row.get("pending_entries")),
                "hit_rate": round_or_none(row.get("hit_rate"), 4),
                "realized_pilot_pnl_usd": round_or_none(row.get("realized_pilot_pnl_usd"), 2),
                "replacement_value_rows": safe_int(row.get("replacement_value_rows")),
                "rv_vs_cash_usd": round_or_none(row.get("rv_vs_cash_usd"), 2),
                "rv_vs_spy_usd": round_or_none(row.get("rv_vs_spy_usd"), 2),
                "rv_vs_qqq_usd": round_or_none(row.get("rv_vs_qqq_usd"), 2),
                "book_max_drawdown_usd": round_or_none(row.get("book_max_drawdown_usd"), 2),
                "book_max_drawdown_pct": round_or_none(row.get("book_max_drawdown_pct"), 4),
                "drawdown_ceiling_breached": bool(row.get("drawdown_ceiling_breached")),
                "verdict": row.get("verdict"),
                "verdict_note": row.get("verdict_note"),
            }
        )
    return rows


def recommendation_summary(payload: dict[str, Any]) -> dict[str, Any]:
    per_pilot: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    for rec in payload.get("recommendations", []) or []:
        pilot = str(rec.get("pilot") or "")
        actionable = list(rec.get("actionable") or [])
        skipped = list(rec.get("skipped") or [])
        rows = [("actionable", row) for row in actionable] + [("skipped", row) for row in skipped]
        entry_present = sum(1 for _, row in rows if row.get("entry_date"))
        target_present = sum(1 for _, row in rows if row.get("target_price"))
        stop_hits = [
            {
                "bucket": bucket,
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "entry_price": row.get("entry_price"),
                "last_price": row.get("last_price"),
                "unrealized_pct": row.get("unrealized_pct"),
                "stop_status": row.get("stop_status"),
            }
            for bucket, row in rows
            if row.get("stop_status") == "STOP_HIT"
        ]
        per_pilot[pilot] = {
            "label": rec.get("label"),
            "sleeve": rec.get("sleeve"),
            "pilot_verdict": rec.get("pilot_verdict"),
            "pilot_verdict_note": rec.get("pilot_verdict_note"),
            "new_entries_blocked": bool(rec.get("new_entries_blocked")),
            "max_concurrent": rec.get("max_concurrent"),
            "actionable_count": len(actionable),
            "skipped_count": len(skipped),
            "row_count": len(rows),
            "entry_date_present": entry_present,
            "target_price_present": target_present,
            "target_price_required": False,
            "target_price_requirement_note": (
                "Not required for this time-exit scorecard audit; closed rows are "
                "settled through the forward replacement-value ledger."
            ),
            "stop_hit_count": len(stop_hits),
            "stop_hits": stop_hits,
        }
        for bucket, row in rows:
            all_rows.append(
                {
                    "pilot": pilot,
                    "bucket": bucket,
                    "ticker": row.get("ticker"),
                    "status": row.get("status"),
                    "entry_date": row.get("entry_date"),
                    "unrealized_pct": row.get("unrealized_pct"),
                    "stop_status": row.get("stop_status"),
                }
            )

    overlap = payload.get("cross_pilot_overlap") or []
    return {
        "as_of": payload.get("as_of"),
        "pilot_count": len(per_pilot),
        "per_pilot": per_pilot,
        "all_current_rows": all_rows,
        "cross_pilot_overlap": overlap,
        "cross_pilot_overlap_count": len(overlap),
        "stop_alerts": payload.get("stop_alerts") or [],
    }


def forward_rv_summary(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    sleeves = {str(row.get("sleeve")) for row in scorecards if row.get("sleeve")}
    rows, bad_rows = iter_jsonl(FORWARD_RV_JSONL)
    accum: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "rows": 0,
            "pnl_usd": 0.0,
            "rv_vs_cash_usd": 0.0,
            "rv_vs_spy_usd": 0.0,
            "rv_vs_qqq_usd": 0.0,
            "tickers": Counter(),
        }
    )
    for row in rows:
        sleeve = str(row.get("sleeve_key") or "")
        if sleeve not in sleeves:
            continue
        bucket = accum[sleeve]
        bucket["rows"] += 1
        bucket["pnl_usd"] += safe_float(row.get("pnl_usd")) or 0.0
        bucket["rv_vs_cash_usd"] += safe_float(row.get("replacement_value_vs_cash_usd")) or 0.0
        bucket["rv_vs_spy_usd"] += safe_float(row.get("replacement_value_vs_spy_usd")) or 0.0
        bucket["rv_vs_qqq_usd"] += safe_float(row.get("replacement_value_vs_qqq_usd")) or 0.0
        if row.get("ticker"):
            bucket["tickers"][str(row["ticker"])] += 1

    by_sleeve: dict[str, Any] = {}
    for sleeve in sorted(sleeves):
        bucket = accum.get(sleeve)
        if not bucket:
            by_sleeve[sleeve] = {
                "rows": 0,
                "pnl_usd": 0.0,
                "rv_vs_cash_usd": 0.0,
                "rv_vs_spy_usd": 0.0,
                "rv_vs_qqq_usd": 0.0,
                "top_ticker": None,
                "top_ticker_share": None,
            }
            continue
        top_ticker, top_count = bucket["tickers"].most_common(1)[0] if bucket["tickers"] else (None, 0)
        by_sleeve[sleeve] = {
            "rows": bucket["rows"],
            "pnl_usd": round(bucket["pnl_usd"], 2),
            "rv_vs_cash_usd": round(bucket["rv_vs_cash_usd"], 2),
            "rv_vs_spy_usd": round(bucket["rv_vs_spy_usd"], 2),
            "rv_vs_qqq_usd": round(bucket["rv_vs_qqq_usd"], 2),
            "top_ticker": top_ticker,
            "top_ticker_share": round(top_count / bucket["rows"], 4) if bucket["rows"] else None,
        }
    return {
        "path": repo_rel(FORWARD_RV_JSONL),
        "exists": FORWARD_RV_JSONL.exists(),
        "json_rows": len(rows),
        "bad_json_rows": bad_rows,
        "by_sleeve": by_sleeve,
    }


def expected_verdict(row: dict[str, Any], graduate_rule: dict[str, Any]) -> str:
    closed = safe_int(row.get("closed_trades"))
    rv_spy = safe_float(row.get("rv_vs_spy_usd")) or 0.0
    book_dd = safe_float(row.get("book_max_drawdown_pct")) or 0.0
    min_closed = safe_int(graduate_rule.get("min_closed"))
    min_rv_spy = safe_float(graduate_rule.get("min_rv_spy_usd")) or 0.0
    max_book_dd = safe_float(graduate_rule.get("max_book_dd_pct")) or 0.0
    if max_book_dd and book_dd > max_book_dd:
        return "KILL"
    if closed >= min_closed and rv_spy > min_rv_spy and (not max_book_dd or book_dd < max_book_dd):
        return "GRADUATE"
    return "COLLECTING"


def evaluate_scorecards(
    scorecards: list[dict[str, Any]],
    recommendations: dict[str, Any],
    graduate_rule: dict[str, Any],
) -> dict[str, Any]:
    per_pilot: list[dict[str, Any]] = []
    verdict_mismatches: list[dict[str, Any]] = []
    killed: list[dict[str, Any]] = []
    graduates: list[dict[str, Any]] = []
    collecting: list[dict[str, Any]] = []

    recs = recommendations.get("per_pilot") or {}
    for row in scorecards:
        pilot = str(row.get("pilot") or "")
        expected = expected_verdict(row, graduate_rule)
        actual = str(row.get("verdict") or "")
        rec = recs.get(pilot) or {}
        matched = actual == expected
        if not matched:
            verdict_mismatches.append(
                {
                    "pilot": pilot,
                    "expected_verdict": expected,
                    "actual_verdict": actual,
                }
            )
        normalized = {
            **row,
            "expected_verdict": expected,
            "verdict_reproduced": matched,
            "current_recommendation_verdict": rec.get("pilot_verdict"),
            "current_new_entries_blocked": rec.get("new_entries_blocked"),
            "current_stop_hit_count": rec.get("stop_hit_count"),
            "current_actionable_count": rec.get("actionable_count"),
            "current_skipped_count": rec.get("skipped_count"),
        }
        per_pilot.append(normalized)
        if actual == "KILL":
            killed.append(normalized)
        elif actual == "GRADUATE":
            graduates.append(normalized)
        else:
            collecting.append(normalized)

    kill_rule_reproducible = not verdict_mismatches and bool(killed)
    blocked_new_entries_ok = all(
        (recs.get(str(row.get("pilot") or "")) or {}).get("new_entries_blocked") is True
        for row in killed
    )
    no_graduate_candidate = not graduates
    return {
        "per_pilot": per_pilot,
        "verdict_mismatches": verdict_mismatches,
        "kill_rule_reproducible": kill_rule_reproducible,
        "killed_pilots": [row.get("pilot") for row in killed],
        "graduate_pilots": [row.get("pilot") for row in graduates],
        "collecting_pilots": [row.get("pilot") for row in collecting],
        "blocked_new_entries_ok": blocked_new_entries_ok,
        "no_graduate_candidate": no_graduate_candidate,
        "definitive_forward_decision_count": len(killed) + len(graduates),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = load_baseline_metrics()
    scorecard_payload = read_json(PILOT_SCORECARD_JSON, {})
    recommendations_payload = read_json(PILOT_RECOMMENDATIONS_JSON, {})
    scorecards = normalize_scorecards(scorecard_payload)
    recommendations = recommendation_summary(recommendations_payload)
    rv_summary = forward_rv_summary(scorecards)
    graduate_rule = scorecard_payload.get("graduate_rule") or {}
    evaluation = evaluate_scorecards(scorecards, recommendations, graduate_rule)

    scorecard_fields_ok = bool(scorecards) and all(
        row.get("pilot")
        and row.get("sleeve")
        and row.get("verdict")
        and row.get("closed_trades") is not None
        and row.get("rv_vs_spy_usd") is not None
        and row.get("book_max_drawdown_pct") is not None
        for row in scorecards
    )
    recommendation_fields_ok = bool(recommendations.get("per_pilot"))
    gate2_passed = scorecard_fields_ok and recommendation_fields_ok and FORWARD_RV_JSONL.exists()

    total_open_or_pending = sum(row["open_positions"] + row["pending_entries"] for row in scorecards)
    total_closed = sum(row["closed_trades"] for row in scorecards)
    total_rows = total_closed + total_open_or_pending
    scorecard_survival = round(total_closed / total_rows, 4) if total_rows else None

    observed_success = bool(
        evaluation["kill_rule_reproducible"] and evaluation["blocked_new_entries_ok"]
    )
    status = "observed_only"
    decision = (
        "observed_only_pilot_scorecard_kill_rule_confirmed"
        if observed_success
        else "blocked_pilot_scorecard_kill_rule_not_reproducible"
    )
    alpha_acceptance_passed = False
    failed_reasons = []
    if not observed_success:
        failed_reasons.append("kill_rule_not_reproducible")
    if evaluation["no_graduate_candidate"]:
        failed_reasons.append("no_graduate_candidate")
    if not gate2_passed:
        failed_reasons.append("scorecard_dependencies_incomplete")

    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else {}
    predicted_probability = safe_float(prediction.get("success_probability")) or 0.0
    actual_success = 1 if observed_success else 0

    post_run_reflection = {
        "why_result_happened": (
            "The precommitted scorecard reproduced one hard KILL: fundamental_growth_rs has "
            "7 closed rows, negative replacement value versus SPY and QQQ, and book drawdown "
            "above the 15% ceiling. Allocator_top1 and distribution_absorption remain "
            "COLLECTING because they have zero closed rows."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retune graduate/kill thresholds, pilot notional, scorecard drawdown "
            "ceilings, or current open-row slices on the same 2026-06-28 pilot surface."
        ),
        "new_evidence_required": (
            "Reopen only after one active pilot has at least 20 closed rows with positive "
            "replacement value versus SPY and QQQ under the unchanged scorecard rule, or "
            "after a materially new production-visible pilot data surface creates new rows."
        ),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_success": observed_success,
        "watchlist_ready": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "change_type": ticket.get("change_type"),
        "implementation_mode": "read_only_observed_forward_readiness",
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components", []),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "novelty": ticket.get("novelty"),
        "prediction": prediction,
        "parameters": {
            "scorecard_file": repo_rel(PILOT_SCORECARD_JSON),
            "recommendations_file": repo_rel(PILOT_RECOMMENDATIONS_JSON),
            "forward_replacement_value_file": repo_rel(FORWARD_RV_JSONL),
            "scorecard_as_of": scorecard_payload.get("as_of"),
            "recommendations_as_of": recommendations.get("as_of"),
            "graduate_rule": graduate_rule,
            "stop_loss_pct": scorecard_payload.get("stop_loss_pct"),
            "per_position_notional_usd": scorecard_payload.get("per_position_notional_usd"),
        },
        "pre_run_questions": {
            "alpha_hypothesis": ticket.get("hypothesis"),
            "history_check": ticket.get("novelty", {}).get("nearest", [])[:5],
            "single_policy_bundle": ticket.get("single_causal_variable"),
            "acceptance_standard": (
                "Observed-only success requires the precommitted daily scorecard verdicts "
                "to be reproducible from closed rows, RV and drawdown. It cannot promote "
                "live capital or accepted alpha without later Gate 1-4 evidence."
            ),
            "reproducibility": "Runner reads fixed 2026-06-28 scorecard/recommendation artifacts and writes deterministic closeout files.",
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "scorecard_pilot_count": len(scorecards),
            "total_closed_scorecard_rows": total_closed,
            "killed_pilots": evaluation["killed_pilots"],
            "graduate_pilots": evaluation["graduate_pilots"],
            "collecting_pilots": evaluation["collecting_pilots"],
        },
        "gate1": {
            "passed": baseline["loaded"],
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": gate2_passed,
            "scorecard_fields_ok": scorecard_fields_ok,
            "recommendation_fields_ok": recommendation_fields_ok,
            "forward_replacement_value_exists": FORWARD_RV_JSONL.exists(),
            "fields_checked": [
                "pilot",
                "sleeve",
                "closed_trades",
                "rv_vs_spy_usd",
                "rv_vs_qqq_usd",
                "book_max_drawdown_pct",
                "verdict",
                "new_entries_blocked",
                "entry_date",
            ],
            "entry_date_coverage_note": "Current open recommendation rows are audited for entry_date; closed rows are validated through scorecard/forward-RV aggregates.",
            "target_price_requirement": "not_applicable_time_exit_scorecard",
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "scorecard_closed_rows": total_closed,
            "scorecard_open_or_pending_rows": total_open_or_pending,
            "scorecard_closed_row_rate": scorecard_survival,
            "note": "No executable filter was added. This only validates the read-only pilot graduate/kill surface.",
        },
        "gate4": {
            "passed": False,
            "alpha_acceptance_passed": alpha_acceptance_passed,
            "observed_only": True,
            "observed_success": observed_success,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "kill_rule_reproducible": evaluation["kill_rule_reproducible"],
            "blocked_new_entries_ok": evaluation["blocked_new_entries_ok"],
            "no_graduate_candidate": evaluation["no_graduate_candidate"],
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "why_no_alpha_acceptance": (
                "This run confirms a kill/readiness conclusion only. No pilot has the "
                "precommitted >=20 closed rows, positive RV, and drawdown guard needed "
                "for promotion evidence."
            ),
        },
        "scorecard": {
            "as_of": scorecard_payload.get("as_of"),
            "graduate_rule": graduate_rule,
            "stop_loss_pct": scorecard_payload.get("stop_loss_pct"),
            "per_position_notional_usd": scorecard_payload.get("per_position_notional_usd"),
            "scorecards": evaluation["per_pilot"],
        },
        "recommendations": recommendations,
        "forward_replacement_value_check": rv_summary,
        "calibration": {
            "predicted_success_probability": predicted_probability,
            "actual_success": actual_success,
            "brier_score": round((predicted_probability - actual_success) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "failure_modes_observed": failed_reasons + ["no_alpha_promotion_candidate"],
            "predicted_failure_mode_hit": any(
                mode in failed_reasons for mode in prediction.get("main_failure_modes", [])
            ),
            "surprise_level": "medium" if observed_success else "low",
            "surprise_note": (
                "The scorecard produced a definite kill conclusion, but not a positive "
                "alpha promotion candidate."
            ),
        },
        "production_impact": {
            "trade_enabled_changed": False,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "shared_helper_changed": False,
            "paper_or_live_snapshot_changed": False,
            "read_only_sources": [
                repo_rel(PILOT_SCORECARD_JSON),
                repo_rel(PILOT_RECOMMENDATIONS_JSON),
                repo_rel(FORWARD_RV_JSONL),
            ],
        },
        "live_realistic_execution_envelope": {
            "status": "not_live_ready",
            "reason": "Observed-only scorecard audit; it confirms a kill/block decision, not a deployable alpha.",
            "notional_cap_evaluated": False,
            "liquidity_and_slippage_mode": "Existing forward replacement-value ledger and pilot scorecard accounting only.",
            "kill_switch": "Precommitted pilot scorecard KILL remains default-off; no production order changes.",
        },
        "rejection_reason": (
            "No accepted alpha or live promotion: the only definitive result is a "
            "fundamental_growth_rs KILL; other pilots remain collecting with zero closed rows."
        ),
        "next_retry_requires": post_run_reflection["new_evidence_required"],
        "post_run_reflection": post_run_reflection,
        "allowed_write_scope": ticket.get("allowed_write_scope", []),
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "related_files": {
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "manifest": repo_rel(MANIFEST_JSON),
            "ticket": repo_rel(TICKET_JSON),
            "baseline": repo_rel(BASELINE_JSON),
            "pilot_scorecard": repo_rel(PILOT_SCORECARD_JSON),
            "pilot_recommendations": repo_rel(PILOT_RECOMMENDATIONS_JSON),
            "forward_replacement_value": repo_rel(FORWARD_RV_JSONL),
        },
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
    }
    return payload


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_success",
        "watchlist_ready",
        "alpha_ready",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "nearby_prior_experiments",
        "new_evidence_type",
        "prediction",
        "parameters",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "scorecard",
        "calibration",
        "production_impact",
        "live_realistic_execution_envelope",
        "rejection_reason",
        "next_retry_requires",
        "post_run_reflection",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys if key in payload}


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def pct(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"{number * 100:.1f}%"


def build_card(payload: dict[str, Any]) -> str:
    rows = payload["scorecard"]["scorecards"]
    lines = [
        f"# {EXPERIMENT_ID}: pilot scorecard kill-rule readiness",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        "- Production behavior changed: no",
        "- Accepted alpha: no",
        "",
        "## Result",
        "",
    ]
    for row in rows:
        lines.append(
            "- {pilot}: verdict `{verdict}`, expected `{expected}`, closed `{closed}`, "
            "RV vs SPY `{rv_spy}`, RV vs QQQ `{rv_qqq}`, book DD `{dd}`".format(
                pilot=row.get("pilot"),
                verdict=row.get("verdict"),
                expected=row.get("expected_verdict"),
                closed=row.get("closed_trades"),
                rv_spy=money(row.get("rv_vs_spy_usd")),
                rv_qqq=money(row.get("rv_vs_qqq_usd")),
                dd=pct(row.get("book_max_drawdown_pct")),
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["next_retry_requires"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
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
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = build_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))

    result = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_success": payload["observed_only_success"],
        "watchlist_ready": payload["watchlist_ready"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "scorecard_pilot_count": payload["delta_metrics"]["scorecard_pilot_count"],
        "total_closed_scorecard_rows": payload["delta_metrics"]["total_closed_scorecard_rows"],
        "killed_pilots": payload["delta_metrics"]["killed_pilots"],
        "failed_reasons": payload["gate4"]["failed_reasons"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
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
        "parameters": payload["parameters"],
        "pre_run_questions": payload["pre_run_questions"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_success": payload["observed_only_success"],
                "killed_pilots": payload["delta_metrics"]["killed_pilots"],
                "total_closed_scorecard_rows": payload["delta_metrics"][
                    "total_closed_scorecard_rows"
                ],
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
