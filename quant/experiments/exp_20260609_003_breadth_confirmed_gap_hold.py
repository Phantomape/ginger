"""exp-20260609-003: breadth-confirmed gap-and-hold candidates.

Replay-only alpha search. This tests one production-visible free-OHLCV
tail-state variable on top of the fixed exp-20260609-002 gap-and-hold event
absorption morphology: only admit candidates when the broad liquid stock
universe shows same-day breadth improvement.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260609_002_gap_and_hold_institutional_demand as base


framework = base.framework

EXPERIMENT_ID = "exp-20260609-003"
STEM = "breadth_confirmed_gap_hold"
TRIAL_FAMILY = "breadth_confirmed_gap_and_hold_candidate_pool"
TRIAL_VARIANT_ID = "breadth_confirmed_gap_hold_top1_next_open_10d_v1"
CHANGED_VARIABLE = "breadth_confirmed_gap_and_hold_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_003_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_BREADTH_UNIVERSE_COUNT = 300
MIN_POSITIVE_RETURN_BREADTH = 0.54
MIN_ABOVE_20DMA_BREADTH = 0.47
MIN_ADVANCING_VOLUME_SHARE = 0.55
MIN_BREADTH_RET20_EXCESS_MEDIAN = -0.005
MAX_BREADTH_RET5_MEDIAN = 0.055

MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = base.ACCEPTED_COMPRESSION_COMPARATOR

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "old_thin_regression",
        "drawdown_drift",
        "breadth_relabels_beta",
        "target_sample_too_small",
        "accepted_compression_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Gap-hold had positive aggregate but failed old_thin/drawdown; the "
        "playbook calls for tail-state breadth fields before promoting broad "
        "momentum pools. Prior ETF and industry breadth variants warn this can "
        "still relabel beta, so the prior odds remain low."
    ),
    "recorded_at": "2026-06-09T03:04:43+00:00",
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
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain a replay lead until a shared default-off adapter computes the "
        "same broad breadth tail-state, fixed gap-and-hold candidate fields, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, comparator, and concentration "
        "controls in both historical replay and daily production."
    ),
}

BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD
BASE_GATE4 = base.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _sma_close(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx - lookback + 1 < 0:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = framework._value(row, "Close")
        if close is None:
            return None
        values.append(close)
    return sum(values) / len(values) if values else None


def _breadth_context_for_date(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> dict[str, Any] | None:
    positive_returns = 0
    above_20dma = 0
    advancing_dollar_volume = 0.0
    total_dollar_volume = 0.0
    ret20_excess_values: list[float] = []
    ret5_values: list[float] = []
    usable = 0

    spy_rows = snapshot.get("SPY") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if spy_idx is None or spy_idx < 60:
        return None
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if spy_ret20 is None:
        return None

    for ticker in sorted(sector_entries):
        if ticker in base.EXCLUDED_TICKERS:
            continue
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 60:
            continue
        close = framework._value(rows[idx], "Close")
        volume = framework._value(rows[idx], "Volume")
        if close is None or close < base.MIN_PRICE or volume is None or volume <= 0:
            continue
        adv20 = framework._avg_dollar_volume(rows, idx)
        if adv20 is None or adv20 < base.MIN_AVG_DOLLAR_VOLUME_20D:
            continue
        daily_return = framework._daily_return(rows, idx)
        ret5 = framework._ret(rows, idx, 5)
        ret20 = framework._ret(rows, idx, 20)
        sma20 = _sma_close(rows, idx, 20)
        if daily_return is None or ret5 is None or ret20 is None or sma20 is None:
            continue
        usable += 1
        dollar_volume = close * volume
        total_dollar_volume += dollar_volume
        if daily_return > 0:
            positive_returns += 1
            advancing_dollar_volume += dollar_volume
        if close > sma20:
            above_20dma += 1
        ret5_values.append(ret5)
        ret20_excess_values.append(ret20 - spy_ret20)

    if usable < MIN_BREADTH_UNIVERSE_COUNT or total_dollar_volume <= 0:
        return None

    positive_return_breadth = positive_returns / usable
    above_20dma_breadth = above_20dma / usable
    advancing_volume_share = advancing_dollar_volume / total_dollar_volume
    ret20_excess_median = _median(ret20_excess_values)
    ret5_median = _median(ret5_values)
    if ret20_excess_median is None or ret5_median is None:
        return None

    passed = (
        positive_return_breadth >= MIN_POSITIVE_RETURN_BREADTH
        and above_20dma_breadth >= MIN_ABOVE_20DMA_BREADTH
        and advancing_volume_share >= MIN_ADVANCING_VOLUME_SHARE
        and ret20_excess_median >= MIN_BREADTH_RET20_EXCESS_MEDIAN
        and ret5_median <= MAX_BREADTH_RET5_MEDIAN
    )
    return {
        "breadth_passed": passed,
        "breadth_universe_count": usable,
        "positive_return_breadth": round(positive_return_breadth, 6),
        "above_20dma_breadth": round(above_20dma_breadth, 6),
        "advancing_volume_share": round(advancing_volume_share, 6),
        "breadth_ret20_excess_spy_median": round(ret20_excess_median, 6),
        "breadth_ret5_median": round(ret5_median, 6),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_breadth_context": 0,
        "days_with_breadth_pass": 0,
        "days_with_raw_gap_hold_candidates": 0,
        "days_with_breadth_confirmed_gap_hold_candidates": 0,
        "raw_gap_hold_candidates": 0,
        "breadth_confirmed_gap_hold_candidates": 0,
    }

    for signal_date in dates:
        breadth = _breadth_context_for_date(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            signal_date=signal_date,
        )
        if breadth is None:
            continue
        scan["days_with_breadth_context"] += 1
        if not breadth["breadth_passed"]:
            continue
        scan["days_with_breadth_pass"] += 1

        day_rows: list[dict[str, Any]] = []
        ab_entries = entries_by_date.get(signal_date, [])
        raw_count = 0
        for ticker in sorted(sector_entries):
            row = base._candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if row is None:
                continue
            raw_count += 1
            row["source"] = "BREADTH_CONFIRMED_GAP_AND_HOLD_PAPER"
            row["rule_version"] = RULE_VERSION
            row.update(breadth)
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            if row["same_ticker_ab_overlap"]:
                continue
            day_rows.append(row)

        if raw_count:
            scan["days_with_raw_gap_hold_candidates"] += 1
            scan["raw_gap_hold_candidates"] += raw_count
        if not day_rows:
            continue

        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["positive_return_breadth"]),
                -float(row["advancing_volume_share"]),
                -float(row["candidate_gap_pct"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_breadth_confirmed_gap_hold_candidates"] += 1
        scan["breadth_confirmed_gap_hold_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": raw_count,
                "breadth_confirmed_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_gap_pct": top["candidate_gap_pct"],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "positive_return_breadth": top["positive_return_breadth"],
                "above_20dma_breadth": top["above_20dma_breadth"],
                "advancing_volume_share": top["advancing_volume_share"],
                "breadth_ret20_excess_spy_median": top[
                    "breadth_ret20_excess_spy_median"
                ],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["positive_return_breadth"]),
            -float(row["advancing_volume_share"]),
            -float(row["candidate_gap_pct"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_breadth_universe_count": MIN_BREADTH_UNIVERSE_COUNT,
            "min_positive_return_breadth": MIN_POSITIVE_RETURN_BREADTH,
            "min_above_20dma_breadth": MIN_ABOVE_20DMA_BREADTH,
            "min_advancing_volume_share": MIN_ADVANCING_VOLUME_SHARE,
            "min_breadth_ret20_excess_median": MIN_BREADTH_RET20_EXCESS_MEDIAN,
            "max_breadth_ret5_median": MAX_BREADTH_RET5_MEDIAN,
        }
    )
    return candidates, day_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_pnl_not_beaten")
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_breadth_confirmed_gap_hold"
        if gate["passed"]
        else "rejected_breadth_confirmed_gap_hold_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Gap-and-hold event absorption may become robust when the broad "
                "liquid universe shows same-day breadth improvement, filtering "
                "event-day crowding without retuning gap thresholds."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
            "new_evidence_type": "production_visible_free_ohlcv_broad_breadth_tail_state",
            "nearby_prior_experiments": [
                "exp-20260609-002",
                "exp-20260608-003",
                "exp-20260607-014",
                "exp-20260608-013",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that broad breadth "
                "confirmation is either too blunt, too pro-cyclical, or just "
                "relabels beta while leaving the old_thin/drawdown failure. Do "
                "not answer by sweeping breadth, gap, volume, ret5/ret20, top-N, "
                "hold-day, cooldown, or paper notional thresholds on these "
                "frozen windows."
            ),
            "next_evidence_needed": (
                "A retry requires materially new PIT flow/catalyst evidence, "
                "forward replacement-value rows, or a different tail-state "
                "field. Pure breadth or gap-hold threshold retunes should stay "
                "frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_breadth_universe_count": MIN_BREADTH_UNIVERSE_COUNT,
            "min_positive_return_breadth": MIN_POSITIVE_RETURN_BREADTH,
            "min_above_20dma_breadth": MIN_ABOVE_20DMA_BREADTH,
            "min_advancing_volume_share": MIN_ADVANCING_VOLUME_SHARE,
            "min_breadth_ret20_excess_median": MIN_BREADTH_RET20_EXCESS_MEDIAN,
            "max_breadth_ret5_median": MAX_BREADTH_RET5_MEDIAN,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: gap-and-hold event absorption should be more "
            "durable when same-day broad breadth shows real participation, not "
            "only one crowded ticker gap."
        ),
        "2_history_check": {
            "exp-20260609-002": (
                "Fixed gap-and-hold improved aggregate EV/PnL but failed "
                "old_thin and drawdown. This keeps the morphology fixed and "
                "adds only a breadth tail-state field."
            ),
            "exp-20260608-003": (
                "IWM breadth-thrust stock leadership failed; broad ETF breadth "
                "can relabel beta. This run uses full liquid-universe breadth "
                "as a gate on a specific event morphology, not as the alpha "
                "source itself."
            ),
            "exp-20260607-014": (
                "Industry volume-breadth thrust failed old_thin/drawdown. This "
                "run tests broad participation and advancing-volume share, not "
                "industry volume breadth."
            ),
            "exp-20260608-013": (
                "Accepted compression breakout is the closest broad OHLCV "
                "comparator (+0.1608 EV, +$2,248.98, 44 trades). This run must "
                "beat it to matter."
            ),
        },
        "3_single_policy_bundle": (
            "Only one decision hypothesis is tested: fixed broad breadth "
            "confirmation for fixed gap-and-hold paper candidates with "
            "next-open entry and 10-trading-day close exit."
        ),
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and the accepted "
            "exp-20260608-013 compression-breakout comparator is beaten."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_003_breadth_confirmed_gap_hold.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted" if payload["gate4"]["passed"] else "rejected"
    )
    payload["interpretation"] = (
        "The breadth-confirmed gap-and-hold source cleared strict Gate 4 and "
        "beat the accepted compression comparator, but remains replay-only "
        "until a shared default-off adapter reproduces it."
        if payload["gate4"]["passed"]
        else (
            "The breadth-confirmed gap-and-hold source did not clear Gate 4 "
            "or did not beat the accepted compression comparator; do not "
            "promote or locally retune this breadth/gap-hold family on the "
            "frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Broad breadth confirmation may still be too blunt a tail-state "
            "field for event-day gap-hold continuation. If it fails a window, "
            "drawdown, or comparator gate, it did not separate durable "
            "institutional demand from pro-cyclical crowding after next-open "
            "execution costs."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping positive-return breadth, above-20DMA "
            "breadth, advancing-volume share, breadth ret20/ret5 medians, gap, "
            "hold, close-location, volume, top-N, hold-day, cooldown, or "
            "paper-notional thresholds on these frozen windows."
        ),
        "new_evidence_required": (
            "Need materially new PIT flow/catalyst provenance, forward "
            "replacement-value rows, or a different tail-state field before "
            "revisiting gap-hold continuation."
        ),
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Breadth pass days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("days_with_breadth_pass", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["accepted_compression_comparator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Breadth-Confirmed Gap-Hold",
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
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                comparator["expected_value_score_delta_sum"],
                comparator["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
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
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
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
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "breadth_pass_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_breadth_pass"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


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
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
