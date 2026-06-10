"""exp-20260610-017: compression-breakout tail-state scout.

Replay-only alpha search. This tests one fixed candidate-source hypothesis:
the accepted narrow-range compression breakout source may avoid exhausted
tail-state rows when the signal date has broad market participation and the
candidate's intraday low does not materially lose the prior close.

The runner reuses the accepted exp-20260608-012/013 compression candidate
construction and adds one fixed tail-state gate. It changes no production code,
shared helper, live/default orders, core ranking, sizing, exits, LLM/news path,
or watchlists. A positive result is only a replay lead until shared historical
and daily helper parity reproduces it. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260608_012_narrow_range_compression_breakout as base  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


framework = base.framework

EXPERIMENT_ID = "exp-20260610-017"
STEM = "compression_tail_state_breakout"
TRIAL_FAMILY = "compression_breakout_tail_state_candidate_pool"
TRIAL_VARIANT_ID = "compression_breakout_tail_state_top1_next_open_10d_v1"
CHANGED_VARIABLE = "compression_breakout_tail_state_candidate_gate_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_017_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "aggregate_ev_delta": 0.1608,
    "aggregate_pnl_delta": 2248.98,
    "target_trade_count": 44,
    "by_window": {
        "late_strong": {"expected_value_delta": 0.0927, "pnl_delta": 1030.63},
        "mid_weak": {"expected_value_delta": 0.0546, "pnl_delta": 844.73},
        "old_thin": {"expected_value_delta": 0.0135, "pnl_delta": 373.62},
    },
}

TAIL_STATE_POLICY = {
    "min_positive_return_breadth": 0.50,
    "min_above_20dma_breadth": 0.50,
    "min_advancing_dollar_volume_share": 0.50,
    "min_breadth_ret20_excess_spy_median": -0.005,
    "min_candidate_low_vs_prior_close_pct": -0.005,
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_compression_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
        "tail_state_not_incremental",
    ],
    "confidence_reason": (
        "Accepted compression breakout proves the base structure can work, "
        "but broad tail-state and breadth-confirmed momentum neighbors often "
        "failed; this tests a materially narrower production-visible OHLCV "
        "tail-state instead of retuning compression thresholds."
    ),
    "recorded_at": "2026-06-10T15:05:38+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_tail_state_scout_no_shared_adapter_change",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": base.BASE_NOTIONAL_USD,
        "daily_entry_slots": base.MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": base.SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": base.HOLD_DAYS,
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "liquidity_source": "accepted compression helper price and ADV gates",
        "portfolio_displacement": "none unless a later shared helper and activation envelope pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes in this scout",
        "failure_handling": "missing OHLCV or tail-state context rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. It reuses accepted "
        "compression candidate rows in a replay runner and adds one fixed "
        "tail-state gate. A positive result would require adding the gate to a "
        "shared helper, daily snapshot wiring, and parity tests before retention."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: accepted compression breakouts mix clean accumulation "
        "with exhausted breakouts. A PIT tail-state requiring broad market "
        "participation and candidate low support near the prior close may remove "
        "tail-risk rows while preserving the compression edge."
    ),
    "2_history_check": {
        "exp-20260608-013": (
            "Accepted shared compression adapter: aggregate EV +0.1608, PnL "
            "+$2,248.98, all three windows positive. This is the binding comparator."
        ),
        "exp-20260609-007": (
            "Broad winner-continuation tail-state separated rows but failed "
            "materiality; this run narrows the field to accepted compression candidates."
        ),
        "exp-20260609-003": (
            "Breadth-confirmed gap-hold failed old_thin/drawdown; this run does "
            "not add a gap-and-hold source, only a majority-participation context gate."
        ),
        "exp-20260610-016": (
            "Recent allocator source-extension failed comparator checks, so this "
            "run avoids adding another source family to the accepted allocator."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "docs/backtesting.md three canonical windows. Must improve aggregate EV/PnL, "
        "have no EV/PnL regression window, pass sample/survival/drawdown/concentration "
        "guards, and beat exp-20260608-013 aggregate plus per-window EV/PnL comparator. "
        "A positive result remains a replay lead until shared helper parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_017_compression_tail_state_breakout.py"
    ),
}

ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW = base._candidate_rows_for_window
ORIGINAL_GATE4 = base._gate4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _round(value: Any, digits: int = 6) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _value(row: dict[str, Any], name: str) -> float | None:
    keys = (name, name.lower(), name.upper(), name.capitalize())
    for key in keys:
        if key in row:
            return _float(row.get(key))
    return None


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or row.get("Date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _series(snapshot: dict[str, list[dict[str, Any]]], ticker: str) -> list[dict[str, Any]]:
    return framework.shadow._series(snapshot, ticker)


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    close = _value(rows[idx], "close")
    prior = _value(rows[idx - lookback], "close")
    if close is None or prior is None or prior <= 0:
        return None
    return close / prior - 1.0


def _sma_close(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    values = [_value(row, "close") for row in rows[idx - lookback : idx]]
    if any(value is None for value in values):
        return None
    valid = [float(value) for value in values if value is not None]
    return sum(valid) / len(valid) if valid else None


def _tail_context_for_date(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> dict[str, Any]:
    spy_rows = _series(snapshot, "SPY")
    spy_idx = indices.get("SPY", {}).get(signal_date)
    spy_ret20 = _ret(spy_rows, spy_idx, 20) if spy_idx is not None else None
    count = 0
    positive_count = 0
    above_20dma_count = 0
    advancing_dollar_volume = 0.0
    total_dollar_volume = 0.0
    ret20_excess_values: list[float] = []
    for ticker in sorted(sector_entries):
        rows = _series(snapshot, ticker)
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 20:
            continue
        close = _value(rows[idx], "close")
        prior_close = _value(rows[idx - 1], "close")
        volume = _value(rows[idx], "volume")
        sma20 = _sma_close(rows, idx, 20)
        ret1 = None if close is None or prior_close is None or prior_close <= 0 else close / prior_close - 1.0
        ret20 = _ret(rows, idx, 20)
        if close is None or prior_close is None or volume is None or ret1 is None:
            continue
        count += 1
        dollar_volume = max(close, 0.0) * max(volume, 0.0)
        total_dollar_volume += dollar_volume
        if ret1 > 0:
            positive_count += 1
            advancing_dollar_volume += dollar_volume
        if sma20 is not None and close > sma20:
            above_20dma_count += 1
        if ret20 is not None and spy_ret20 is not None:
            ret20_excess_values.append(ret20 - spy_ret20)

    positive_return_breadth = positive_count / count if count else None
    above_20dma_breadth = above_20dma_count / count if count else None
    advancing_share = (
        advancing_dollar_volume / total_dollar_volume if total_dollar_volume > 0 else None
    )
    median_excess = (
        statistics.median(ret20_excess_values) if ret20_excess_values else None
    )
    passed = (
        positive_return_breadth is not None
        and positive_return_breadth >= TAIL_STATE_POLICY["min_positive_return_breadth"]
        and above_20dma_breadth is not None
        and above_20dma_breadth >= TAIL_STATE_POLICY["min_above_20dma_breadth"]
        and advancing_share is not None
        and advancing_share >= TAIL_STATE_POLICY["min_advancing_dollar_volume_share"]
        and median_excess is not None
        and median_excess >= TAIL_STATE_POLICY["min_breadth_ret20_excess_spy_median"]
    )
    return {
        "date": signal_date,
        "tail_state_market_passed": passed,
        "breadth_universe_count": count,
        "positive_return_breadth": _round(positive_return_breadth),
        "above_20dma_breadth": _round(above_20dma_breadth),
        "advancing_dollar_volume_share": _round(advancing_share),
        "breadth_ret20_excess_spy_median": _round(median_excess),
        "tail_state_policy": deepcopy(TAIL_STATE_POLICY),
        "rule_version": RULE_VERSION,
    }


def _candidate_low_vs_prior_close(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    row: dict[str, Any],
) -> float | None:
    ticker = str(row.get("ticker") or "").upper()
    signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
    rows = _series(snapshot, ticker)
    idx = indices.get(ticker, {}).get(signal_date)
    if idx is None or idx <= 0:
        return None
    low = _value(rows[idx], "low")
    prior_close = _value(rows[idx - 1], "close")
    if low is None or prior_close is None or prior_close <= 0:
        return None
    return low / prior_close - 1.0


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, contexts, scan = ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    indices = {
        ticker: _row_index(_series(snapshot, ticker))
        for ticker in set(snapshot).union({"SPY"})
    }
    context_by_date = {
        context["date"]: _tail_context_for_date(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            signal_date=str(context["date"]),
        )
        for context in contexts
    }
    filtered: list[dict[str, Any]] = []
    rejected_reasons: Counter[str] = Counter()
    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        context = context_by_date.get(signal_date)
        low_vs_prior = _candidate_low_vs_prior_close(
            snapshot=snapshot,
            indices=indices,
            row=row,
        )
        out = deepcopy(row)
        out.update(
            {
                "base_source_rule_version": base.CHANGED_VARIABLE,
                "tail_state_rule_version": RULE_VERSION,
                "tail_state_policy": deepcopy(TAIL_STATE_POLICY),
                "candidate_low_vs_prior_close_pct": _round(low_vs_prior),
                "tail_state_context": context,
            }
        )
        if not context:
            rejected_reasons["missing_tail_state_context"] += 1
            continue
        if not context.get("tail_state_market_passed"):
            rejected_reasons["market_tail_state_failed"] += 1
            continue
        if low_vs_prior is None:
            rejected_reasons["missing_candidate_low_vs_prior_close"] += 1
            continue
        if low_vs_prior < TAIL_STATE_POLICY["min_candidate_low_vs_prior_close_pct"]:
            rejected_reasons["candidate_prior_close_support_failed"] += 1
            continue
        out["tail_state_passed"] = True
        filtered.append(out)

    scan.update(
        {
            "base_raw_compression_breakout_candidates": len(candidates),
            "tail_state_filtered_candidates": len(filtered),
            "tail_state_rejected_candidates": len(candidates) - len(filtered),
            "tail_state_reject_reasons": dict(rejected_reasons),
            "tail_state_policy": deepcopy(TAIL_STATE_POLICY),
            "tail_state_rule_version": RULE_VERSION,
        }
    )
    contexts_out = [
        {
            **deepcopy(context),
            "tail_state_context": context_by_date.get(str(context.get("date") or "")),
        }
        for context in contexts
    ][:50]
    return filtered, contexts_out, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    if float(aggregate.get("expected_value_score_delta_sum") or 0.0) <= ACCEPTED_COMPRESSION_COMPARATOR["aggregate_ev_delta"]:
        failed.append("accepted_compression_aggregate_ev_not_beaten")
    if float(aggregate.get("total_pnl_delta_sum") or 0.0) <= ACCEPTED_COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_aggregate_pnl_not_beaten")
    gate.update(
        {
            "passed": not failed,
            "decision": (
                "positive_replay_lead_not_promoted_compression_tail_state_breakout"
                if not failed
                else "rejected_compression_tail_state_breakout_candidate_pool"
            ),
            "failed_reasons": failed,
            "accepted_compression_comparator": deepcopy(ACCEPTED_COMPRESSION_COMPARATOR),
        }
    )
    return gate


def _apply_comparator_window_checks(payload: dict[str, Any]) -> None:
    gate = payload["gate4"]
    failed = list(gate.get("failed_reasons") or [])
    per_window: dict[str, Any] = {}
    for label, comparator in ACCEPTED_COMPRESSION_COMPARATOR["by_window"].items():
        delta = payload["delta_metrics"]["by_window"][label]
        ev_delta = float(delta.get("expected_value_score") or 0.0)
        pnl_delta = float(delta.get("total_pnl") or 0.0)
        ev_passed = ev_delta > float(comparator["expected_value_delta"])
        pnl_passed = pnl_delta > float(comparator["pnl_delta"])
        per_window[label] = {
            "ev_delta": _round(ev_delta, 4),
            "accepted_ev_delta": comparator["expected_value_delta"],
            "ev_passed": ev_passed,
            "pnl_delta": _round(pnl_delta, 2),
            "accepted_pnl_delta": comparator["pnl_delta"],
            "pnl_passed": pnl_passed,
        }
        if not ev_passed:
            failed.append(f"accepted_compression_{label}_ev_not_beaten")
        if not pnl_passed:
            failed.append(f"accepted_compression_{label}_pnl_not_beaten")
    gate["accepted_compression_window_comparator"] = per_window
    gate["failed_reasons"] = sorted(dict.fromkeys(failed))
    gate["passed"] = not gate["failed_reasons"]
    gate["decision"] = (
        "positive_replay_lead_not_promoted_compression_tail_state_breakout"
        if gate["passed"]
        else "rejected_compression_tail_state_breakout_candidate_pool"
    )
    payload["decision"] = gate["decision"]
    payload["status"] = "accepted" if gate["passed"] else "rejected"
    payload["calibration"]["actual_gate4_passed"] = gate["passed"]
    payload["calibration"]["failure_modes_observed"] = gate["failed_reasons"]
    payload["calibration"]["brier_score"] = round(
        (PREDICTION["success_probability"] - (1.0 if gate["passed"] else 0.0)) ** 2,
        6,
    )


def _patch_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._patch_framework()


def _build_payload() -> dict[str, Any]:
    _patch_base()
    payload = base._build_payload()
    _apply_comparator_window_checks(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "replay_only_candidate_pool_tail_state_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
            "new_evidence_type": "production_visible_free_ohlcv_compression_tail_state_field",
            "nearby_prior_experiments": [
                "exp-20260608-013",
                "exp-20260609-007",
                "exp-20260609-003",
                "exp-20260610-016",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "accepted_compression_comparator": deepcopy(ACCEPTED_COMPRESSION_COMPARATOR),
            "tail_state_policy": deepcopy(TAIL_STATE_POLICY),
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "gate_questions": PRE_RUN_QUESTIONS,
            "anti_js": "No JavaScript was used.",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The compression tail-state gate cleared the canonical and accepted "
                "compression comparator gates as a replay-only lead. It is not "
                "retained until a shared helper and daily parity reproduce it."
                if payload["gate4"]["passed"]
                else (
                    "The compression tail-state gate failed Gate 4 or the accepted "
                    "compression comparator. No strategy logic is retained."
                )
            ),
            "rejection_reason": (
                None
                if payload["gate4"]["passed"]
                else "; ".join(payload["gate4"]["failed_reasons"])
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The fixed tail-state gate either thinned too much of the accepted "
                    "compression edge or failed to improve every accepted-comparator "
                    "window. Compression itself remains accepted; this result only "
                    "rejects the added breadth/low-support tail-state discriminator."
                    if not payload["gate4"]["passed"]
                    else (
                        "The tail-state gate improved the accepted compression source "
                        "by removing weaker market-support and intraday-damage rows; "
                        "the result still requires shared helper parity and forward rows."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping market breadth thresholds, candidate "
                    "low-vs-prior-close thresholds, compression lookbacks, range "
                    "expansion, volume, close-location, ret5/ret20, top-N, hold, "
                    "cooldown, or notional on these frozen windows."
                ),
                "new_evidence_required": (
                    "A retry needs forward replacement-value rows or a materially "
                    "different PIT flow/catalyst field; not another OHLCV tail-state "
                    "threshold sweep."
                ),
            },
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
            ],
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "tail_state_policy": deepcopy(TAIL_STATE_POLICY),
        "single_causal_variable": CHANGED_VARIABLE,
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | dEV | Accepted dEV | dPnL | Accepted dPnL | Raw | Tail pass | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        comp = ACCEPTED_COMPRESSION_COMPARATOR["by_window"][label]
        rows.append(
            "| {label} | {dev:+.4f} | {cev:+.4f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {raw} | {tail} | {trades} |".format(
                label=label,
                dev=float(delta.get("expected_value_score") or 0.0),
                cev=float(comp["expected_value_delta"]),
                dpnl=float(delta.get("total_pnl") or 0.0),
                cpnl=float(comp["pnl_delta"]),
                raw=scan.get("base_raw_compression_breakout_candidates", 0),
                tail=scan.get("tail_state_filtered_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Compression Tail-State Breakout",
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
            "- Aggregate EV delta: `{:+.4f}` versus accepted compression `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["aggregate_ev_delta"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` versus accepted compression `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Production Impact",
            "",
            "Replay-only/default-off paper scout. No production orders, run adapter, shared helper, core ranking, sizing, exits, LLM/news, or watchlists changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": deepcopy(ACCEPTED_COMPRESSION_COMPARATOR),
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "base_raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "base_raw_compression_breakout_candidates"
                ),
                "tail_state_filtered_candidate_count": payload["context_scan_by_window"][label].get(
                    "tail_state_filtered_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "accepted_alpha": False,
        "production_accepted": False,
        "shared_adapter_required": bool(payload["gate4"]["passed"]),
        "numeric_gate4_passed": bool(payload["gate4"]["passed"]),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )

    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": result,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": payload["related_files"],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)
    print(
        "completed {experiment_id}: {decision} | dEV={ev:+.4f} | dPnL=${pnl:+,.2f}".format(
            experiment_id=EXPERIMENT_ID,
            decision=payload["decision"],
            ev=payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"],
            pnl=payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
        )
    )


if __name__ == "__main__":
    main()
