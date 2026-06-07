"""exp-20260607-006: macro relief sector-confirmed leadership scout.

Alpha search, replay-only.  It tests whether the accepted macro-relief
leadership candidate pool becomes cleaner when the candidate's broad-universe
sector median also rallies and beats SPY on the official macro relief day.

This does not change production code, live/default orders, core entries,
ranking, sizing, exits, watchlists, LLM, or news behavior.  A positive result
would still need a shared default-off adapter update before retention.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260606_020_macro_relief_top2_shared_adapter as exp020


EXPERIMENT_ID = "exp-20260607-006"
STEM = "macro_relief_sector_confirmed_leadership"
TRIAL_FAMILY = "macro_relief_sector_confirmed_leadership_candidate_pool"
TRIAL_VARIANT_ID = "macro_relief_sector_confirmed_leadership_v1"
CHANGED_VARIABLE = "macro_relief_sector_confirmed_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = exp020.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_006_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
ACCEPTED_COMPARATOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260606-020"
    / "exp_20260606_020_macro_relief_top2_shared_adapter.json"
)

BASE_NOTIONAL_USD = exp020.BASE_NOTIONAL_USD
HOLD_DAYS = exp020.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = exp020.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = exp020.SAME_TICKER_COOLDOWN_DAYS

MIN_SECTOR_MEMBER_COUNT = 5
MIN_SECTOR_MEDIAN_RETURN = 0.0
MIN_SECTOR_MEDIAN_EXCESS_SPY = 0.0

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "accepted_comparator_underperformance",
        "window_regression",
        "old_thin_tail",
        "sector_median_not_incremental",
    ],
    "confidence_reason": (
        "Macro relief top-2 leadership is accepted, and same-day sector "
        "median confirmation is a materially new free OHLCV breadth field, "
        "but accepted exp020 is already strong and sample can become thin."
    ),
    "recorded_at": "2026-06-07T04:04:46+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "Replay-only scout. A positive result would require a shared "
        "default-off macro relief adapter update that computes the same "
        "broad-universe sector median fields in historical replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
    ),
}

framework = exp020.framework
BASE_BUILD_PAYLOAD = exp020.BASE_BUILD_PAYLOAD
BASE_PERSIST = exp020.BASE_PERSIST


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, float):
        if not math.isfinite(payload):
            return None
        return round(payload, 10)
    if isinstance(payload, Path):
        return _repo_rel(payload)
    return payload


def _accepted_comparator_payload() -> dict[str, Any]:
    return json.loads(ACCEPTED_COMPARATOR_JSON.read_text(encoding="utf-8"))


def _sector_day_medians(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> dict[str, dict[str, Any]]:
    spy_rows = snapshot.get("SPY") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    spy_return = framework._daily_return(spy_rows, spy_idx) if spy_idx is not None else None
    if spy_return is None:
        return {}

    by_sector: dict[str, list[float]] = {}
    for ticker, meta in sector_entries.items():
        sector = str(meta.get("sector") or "")
        if not sector:
            continue
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 20:
            continue
        close = framework._value(rows[idx], "Close")
        if close is None or close < exp020.MIN_PRICE:
            continue
        adv20 = framework._avg_dollar_volume(rows, idx)
        if adv20 is None or adv20 < exp020.MIN_AVG_DOLLAR_VOLUME_20D:
            continue
        daily_return = framework._daily_return(rows, idx)
        if daily_return is None:
            continue
        by_sector.setdefault(sector, []).append(daily_return)

    out: dict[str, dict[str, Any]] = {}
    for sector, values in sorted(by_sector.items()):
        if len(values) < MIN_SECTOR_MEMBER_COUNT:
            continue
        med = median(values)
        out[sector] = {
            "sector": sector,
            "sector_member_count": len(values),
            "sector_median_return": round(med, 6),
            "sector_median_excess_spy": round(med - spy_return, 6),
            "spy_signal_day_return": round(spy_return, 6),
            "sector_confirmed": (
                med >= MIN_SECTOR_MEDIAN_RETURN
                and (med - spy_return) >= MIN_SECTOR_MEDIAN_EXCESS_SPY
            ),
        }
    return out


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, contexts, scan = exp020._candidate_rows_for_window(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    indices = {ticker: framework.shadow._row_index(rows) for ticker, rows in snapshot.items()}
    sector_state_by_date = {
        date_value: _sector_day_medians(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            signal_date=date_value,
        )
        for date_value in sorted({str(row.get("date") or "")[:10] for row in candidates})
    }

    confirmed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        sector = str(row.get("sector") or "")
        sector_state = sector_state_by_date.get(signal_date, {}).get(sector)
        enriched = {
            **row,
            "macro_sector_confirmation_rule_version": RULE_VERSION,
            "macro_sector_min_member_count": MIN_SECTOR_MEMBER_COUNT,
            "macro_sector_min_median_return": MIN_SECTOR_MEDIAN_RETURN,
            "macro_sector_min_median_excess_spy": MIN_SECTOR_MEDIAN_EXCESS_SPY,
            "macro_sector_state": sector_state,
        }
        if not sector_state:
            rejected.append({**enriched, "sector_confirmation_reject_reason": "missing_sector_state"})
            continue
        if not sector_state.get("sector_confirmed"):
            rejected.append(
                {**enriched, "sector_confirmation_reject_reason": "sector_not_confirmed"}
            )
            continue
        confirmed.append(enriched)

    scan = {
        **scan,
        "sector_confirmation_rule_version": RULE_VERSION,
        "pre_sector_confirm_candidate_count": len(candidates),
        "sector_confirmed_candidate_count": len(confirmed),
        "sector_rejected_candidate_count": len(rejected),
        "sector_state_by_date": sector_state_by_date,
        "sector_confirmation_parameters": {
            "min_sector_member_count": MIN_SECTOR_MEMBER_COUNT,
            "min_sector_median_return": MIN_SECTOR_MEDIAN_RETURN,
            "min_sector_median_excess_spy": MIN_SECTOR_MEDIAN_EXCESS_SPY,
        },
        "sector_rejected_sample": rejected[:25],
    }
    contexts = [
        {
            **context,
            "sector_confirmation": {
                "pre_sector_confirm_candidate_count": sum(
                    1 for row in candidates if row.get("date") == context.get("date")
                ),
                "sector_confirmed_candidate_count": sum(
                    1 for row in confirmed if row.get("date") == context.get("date")
                ),
            },
        }
        for context in contexts
    ]
    return confirmed, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = exp020._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    comparator = _accepted_comparator_payload()
    failed = list(gate["failed_reasons"])
    gate["decision"] = (
        "accepted_macro_relief_sector_confirmed_leadership_replay_lead"
        if gate["passed"]
        else "rejected_macro_relief_sector_confirmed_leadership_candidate_pool"
    )
    gate["accepted_comparator"] = {
        "experiment_id": "exp-20260606-020",
        "artifact": _repo_rel(ACCEPTED_COMPARATOR_JSON),
    }
    # Placeholder; final comparator deltas are filled after payload assembly
    # where after metrics are available.
    gate["requires_accepted_comparator_outperformance"] = True
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    return gate


def _accepted_comparator_deltas(payload: dict[str, Any]) -> dict[str, Any]:
    comparator = _accepted_comparator_payload()
    by_window: OrderedDict[str, dict[str, float]] = OrderedDict()
    ev_sum = 0.0
    pnl_sum = 0.0
    for label in framework.WINDOWS:
        after = payload["after_metrics"][label]
        accepted_after = comparator["after_metrics"][label]
        ev_delta = float(after["expected_value_score"]) - float(
            accepted_after["expected_value_score"]
        )
        pnl_delta = float(after["total_pnl"]) - float(accepted_after["total_pnl"])
        by_window[label] = {
            "expected_value_score_delta_vs_accepted": round(ev_delta, 6),
            "total_pnl_delta_vs_accepted": round(pnl_delta, 2),
        }
        ev_sum += ev_delta
        pnl_sum += pnl_delta
    return {
        "comparator_experiment_id": "exp-20260606-020",
        "comparator_artifact": _repo_rel(ACCEPTED_COMPARATOR_JSON),
        "expected_value_score_delta_sum_vs_accepted": round(ev_sum, 6),
        "total_pnl_delta_sum_vs_accepted": round(pnl_sum, 2),
        "by_window": by_window,
    }


def _apply_accepted_comparator_gate(payload: dict[str, Any]) -> None:
    comparator = _accepted_comparator_deltas(payload)
    failed = list(payload["gate4"]["failed_reasons"])
    if comparator["expected_value_score_delta_sum_vs_accepted"] <= 0:
        failed.append("accepted_comparator_ev_not_positive")
    if comparator["total_pnl_delta_sum_vs_accepted"] <= 0:
        failed.append("accepted_comparator_pnl_not_positive")
    for label, row in comparator["by_window"].items():
        if row["expected_value_score_delta_vs_accepted"] < 0:
            failed.append(f"accepted_comparator_window_ev_regression_{label}")
        if row["total_pnl_delta_vs_accepted"] < 0:
            failed.append(f"accepted_comparator_window_pnl_regression_{label}")
    payload["accepted_comparator_delta"] = comparator
    payload["gate4"]["failed_reasons"] = failed
    payload["gate4"]["passed"] = not failed
    payload["gate4"]["decision"] = (
        "positive_replay_lead_not_promoted_macro_relief_sector_confirmed"
        if payload["gate4"]["passed"]
        else "rejected_macro_relief_sector_confirmed_leadership_candidate_pool"
    )
    payload["status"] = (
        "positive_replay_lead_not_promoted" if payload["gate4"]["passed"] else "rejected"
    )
    payload["decision"] = payload["gate4"]["decision"]
    payload["calibration"] = {
        **payload.get("calibration", {}),
        "actual_gate4_passed": payload["gate4"]["passed"],
        "failure_modes_observed": list(payload["gate4"]["failed_reasons"]),
        "brier_score": round(
            (
                float(PREDICTION["success_probability"])
                - (1.0 if payload["gate4"]["passed"] else 0.0)
            )
            ** 2,
            6,
        ),
        "surprise_note": (
            "Core Gate 4 passed, but the stricter accepted-comparator check "
            "rejected the variant because late_strong regressed versus exp020."
            if not payload["gate4"]["passed"]
            else "The variant cleared both core and accepted-comparator gates."
        ),
    }


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    _apply_accepted_comparator_gate(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Official macro relief stock-leadership candidates may be "
                "cleaner when the candidate's broad-universe sector median "
                "also rallies and beats SPY on the event day."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "free_official_macro_calendar_plus_ohlcv_candidate_pool",
            "new_evidence_type": "new_production_visible_sector_breadth_field",
            "nearby_prior_experiments": [
                "exp-20260606-017",
                "exp-20260606-019",
                "exp-20260606-020",
                "exp-20260606-027",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the sector median confirmation either thinned "
                "the already accepted macro relief pool too much or failed to "
                "add incremental information beyond the stock-level leadership "
                "score. Do not retune sector median thresholds on these frozen "
                "windows without forward replacement-value rows or a materially "
                "new sector breadth construction."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_sector_member_count": MIN_SECTOR_MEMBER_COUNT,
            "min_sector_median_return": MIN_SECTOR_MEDIAN_RETURN,
            "min_sector_median_excess_spy": MIN_SECTOR_MEDIAN_EXCESS_SPY,
            "accepted_comparator_experiment_id": "exp-20260606-020",
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate-pool/ranking-quality: macro relief stock leadership "
            "should be more executable when the whole candidate sector confirms "
            "the relief day, rather than relying on a single stock shock."
        ),
        "2_history_check": {
            "exp-20260606-017": "top-1 macro relief was positive but too thin.",
            "exp-20260606-019": "top-2 macro relief passed as replay lead.",
            "exp-20260606-020": (
                "shared top-2 adapter accepted; this run must beat this "
                "accepted comparator, not just core."
            ),
            "exp-20260606-027": "macro stress resilient leadership was rejected.",
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md three canonical windows. The variant must pass "
            "core Gate 4 and also outperform accepted exp-20260606-020 in "
            "aggregate EV/PnL with no accepted-comparator window regression."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260607_006_macro_relief_sector_confirmed_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["interpretation"] = (
        "The sector-confirmed macro relief variant is only a positive replay "
        "lead. It is not accepted until shared historical/daily adapter "
        "semantics reproduce it."
        if payload["gate4"]["passed"]
        else (
            "The sector-confirmed macro relief variant did not clear Gate 4 "
            "against the accepted exp020 comparator. Keep the accepted top-2 "
            "macro relief adapter unchanged."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["next_evidence_needed"] = (
        "Forward replacement-value rows or a materially different sector "
        "breadth source. Do not retune sector median return/excess thresholds, "
        "macro relief thresholds, top-N, hold days, cooldown, or paper notional "
        "on the frozen windows."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | EV vs exp020 | Before PnL | After PnL | dPnL | PnL vs exp020 | Sector-confirmed raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        comp = payload["accepted_comparator_delta"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comp["expected_value_score_delta_vs_accepted"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comp["total_pnl_delta_vs_accepted"],
                raw=scan.get("sector_confirmed_candidate_count", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["accepted_comparator_delta"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Macro Relief Sector-Confirmed Leadership",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta vs core: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta vs core: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Aggregate EV delta vs accepted exp020: `{:+.4f}`".format(
                comparator["expected_value_score_delta_sum_vs_accepted"]
            ),
            "- Aggregate PnL delta vs accepted exp020: `${:+,.2f}`".format(
                comparator["total_pnl_delta_sum_vs_accepted"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, "
                "run adapter, backtester adapter, production watchlist, order "
                "path, core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["accepted_comparator_delta"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "free_official_macro_calendar_plus_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "accepted_comparator_artifact": _repo_rel(ACCEPTED_COMPARATOR_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparator_expected_value_delta": comparator[
            "expected_value_score_delta_sum_vs_accepted"
        ],
        "accepted_comparator_strategy_total_pnl_delta": comparator[
            "total_pnl_delta_sum_vs_accepted"
        ],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "expected_value_delta_vs_accepted": comparator["by_window"][label][
                    "expected_value_score_delta_vs_accepted"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "strategy_total_pnl_delta_vs_accepted": comparator["by_window"][label][
                    "total_pnl_delta_vs_accepted"
                ],
                "sector_confirmed_candidate_count": payload["context_scan_by_window"][label].get(
                    "sector_confirmed_candidate_count"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": payload["interpretation"],
            "forbidden_near_neighbor_retry": (
                "Do not retune macro sector median return/excess thresholds, "
                "macro relief thresholds, top-N, hold, cooldown, or notional "
                "on the frozen windows."
            ),
            "new_evidence_required": (
                "Forward replacement-value rows or a materially different "
                "sector breadth/participation field."
            ),
        },
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
            _repo_rel(ARTIFACT_MD): framework._sha256(ARTIFACT_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._write_text(ARTIFACT_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    framework._update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._select_paper_trades = exp020._select_paper_trades
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._write_manifest = _write_manifest
    framework.persist = persist


_patch_framework()


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
