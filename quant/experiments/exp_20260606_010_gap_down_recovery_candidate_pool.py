"""exp-20260606-010: broad gap-down recovery candidate pool.

Replay-only alpha search. This retests the old observed-only gap-down recovery
shape on the current canonical three-window baseline and broad warehouse:
liquid stocks that gap down at the open, recover intraday, close high in their
daily range, and trade with volume confirmation become top-1 next-open
default-off paper candidates with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260606-010"
STEM = "gap_down_recovery_candidate_pool"
TRIAL_FAMILY = "gap_down_recovery_default_off_candidate_pool"
TRIAL_VARIANT_ID = "gap_down_intraday_reclaim_top1_next_open_10d_v1"
CHANGED_VARIABLE = "broad_liquid_gap_down_recovery_next_open_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_010_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_GAP_DOWN_PCT = -0.015
MIN_INTRADAY_RECOVERY_PCT = 0.012
MIN_CLOSE_LOCATION = 0.65
MIN_VOLUME_RATIO_20D = 1.15
MAX_CLOSE_VS_PREV_CLOSE_PCT = 0.015
MIN_RET5_EXCESS_SPY = -0.03
MIN_RET20_EXCESS_SPY = -0.05
MAX_REALIZED_VOL_20D = 0.10

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "old_thin_reversal_noise",
        "aggregate_ev_not_positive",
        "drawdown_drift",
        "positive_pnl_concentration",
    ],
    "confidence_reason": (
        "Older observed-only gap-down recovery had useful mid/old forward "
        "returns but mixed late-window evidence. Recent broad reversal tests "
        "failed, so probability is modest; the tested morphology is still "
        "distinct from 5-day momentum continuation and from raw selloff "
        "mean reversion."
    ),
    "recorded_at": "2026-06-06T08:05:35Z",
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
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same broad "
        "warehouse liquid stock universe, signal-day gap-down/recovery fields, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "core-overlap controls in both replay and daily production before any "
        "report queue, paper ledger, candidate priority, sizing, watchlist, or "
        "order surface could change."
    ),
}

BASE_GATE4 = framework._gate4
BASE_BUILD_PAYLOAD = framework._build_payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _close_vs_prev(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prev = framework._value(rows[idx - 1], "Close")
    close = framework._value(rows[idx], "Close")
    if prev is None or prev <= 0 or close is None:
        return None
    return close / prev - 1.0


def _gap_down_pct(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prev = framework._value(rows[idx - 1], "Close")
    open_ = framework._value(rows[idx], "Open")
    if prev is None or prev <= 0 or open_ is None:
        return None
    return open_ / prev - 1.0


def _intraday_recovery_pct(rows: list[dict[str, Any]], idx: int) -> float | None:
    open_ = framework._value(rows[idx], "Open")
    close = framework._value(rows[idx], "Close")
    if open_ is None or open_ <= 0 or close is None:
        return None
    return close / open_ - 1.0


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 20 or spy_idx < 20:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    gap_down = _gap_down_pct(rows, idx)
    intraday_recovery = _intraday_recovery_pct(rows, idx)
    close_location = framework._close_location(rows[idx])
    close_vs_prev = _close_vs_prev(rows, idx)
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    spy_ret5 = framework._ret(spy_rows, spy_idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    realized_vol = framework._realized_vol(rows, idx)
    required = [
        gap_down,
        intraday_recovery,
        close_location,
        close_vs_prev,
        volume_ratio,
        ret5,
        spy_ret5,
        ret20,
        spy_ret20,
        realized_vol,
    ]
    if any(value is None for value in required):
        return None
    assert gap_down is not None
    assert intraday_recovery is not None
    assert close_location is not None
    assert close_vs_prev is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert spy_ret5 is not None
    assert ret20 is not None
    assert spy_ret20 is not None
    assert realized_vol is not None

    ret5_excess_spy = ret5 - spy_ret5
    ret20_excess_spy = ret20 - spy_ret20
    if gap_down > MIN_GAP_DOWN_PCT:
        return None
    if intraday_recovery < MIN_INTRADAY_RECOVERY_PCT:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D:
        return None
    if close_vs_prev > MAX_CLOSE_VS_PREV_CLOSE_PCT:
        return None
    if ret5_excess_spy < MIN_RET5_EXCESS_SPY:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if realized_vol > MAX_REALIZED_VOL_20D:
        return None

    sector_meta = sector_entries[ticker]
    score = (
        7.0 * abs(gap_down)
        + 5.0 * intraday_recovery
        + 0.85 * close_location
        + 0.20 * min(volume_ratio, 4.0)
        + 1.0 * ret5_excess_spy
        + 0.50 * ret20_excess_spy
        - 1.0 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "GAP_DOWN_RECOVERY_PAPER",
        "candidate_score": round(score, 6),
        "candidate_gap_down_pct": round(gap_down, 6),
        "candidate_intraday_recovery_pct": round(intraday_recovery, 6),
        "candidate_close_vs_prev_close_pct": round(close_vs_prev, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_ret5": round(ret5, 6),
        "candidate_spy_ret5": round(spy_ret5, 6),
        "candidate_ret5_excess_spy": round(ret5_excess_spy, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_raw_gap_recovery_candidates": 0,
        "raw_gap_recovery_candidates": 0,
    }
    for signal_date in dates:
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_intraday_recovery_pct"]),
                -abs(float(row["candidate_gap_down_pct"])),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_gap_recovery_candidates"] += 1
        scan["raw_gap_recovery_candidates"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_gap_down_pct": day_rows[0]["candidate_gap_down_pct"],
                "top_candidate_intraday_recovery_pct": day_rows[0][
                    "candidate_intraday_recovery_pct"
                ],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_intraday_recovery_pct"]),
            -abs(float(row["candidate_gap_down_pct"])),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_gap_down_pct": MIN_GAP_DOWN_PCT,
            "min_intraday_recovery_pct": MIN_INTRADAY_RECOVERY_PCT,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_close_vs_prev_close_pct": MAX_CLOSE_VS_PREV_CLOSE_PCT,
            "min_ret5_excess_spy": MIN_RET5_EXCESS_SPY,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
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
    gate["decision"] = (
        "positive_replay_lead_not_promoted_gap_down_recovery_candidate_pool"
        if gate["passed"]
        else "rejected_gap_down_recovery_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Broad liquid stocks that gap down at the open but reclaim "
                "strongly by the close may identify event-sensitive recovery "
                "candidates with better 10-day next-open paper replacement "
                "value than raw broad momentum, without changing live orders."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "event_sensitive_free_ohlcv_reversal",
            "new_evidence_type": "current_canonical_warehouse_replay_of_old_observed_shadow_source",
            "nearby_prior_experiments": [
                "exp-20260427-013",
                "exp-20260427-017",
                "exp-20260606-003",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the old observed-only gap-down recovery shape "
                "does not survive current canonical next-open paper replay. "
                "Likely failure modes are reversal noise, bad old_thin crash "
                "states, or concentration in a few event gaps. Do not answer "
                "by locally retuning gap/recovery thresholds on these frozen "
                "windows."
            ),
            "next_evidence_needed": (
                "A retry requires forward replacement-value rows or a richer "
                "event provenance field that explains why the gap happened; "
                "pure OHLCV gap/recovery threshold retunes should stay frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_gap_down_pct": MIN_GAP_DOWN_PCT,
            "min_intraday_recovery_pct": MIN_INTRADAY_RECOVERY_PCT,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_close_vs_prev_close_pct": MAX_CLOSE_VS_PREV_CLOSE_PCT,
            "min_ret5_excess_spy": MIN_RET5_EXCESS_SPY,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: liquid broad stocks with a signal-day "
            "gap-down plus strong intraday recovery may represent event "
            "absorption/reclaim alpha rather than raw momentum."
        ),
        "2_history_check": {
            "exp-20260427-013": (
                "Observed-only gap-down recovery scout; candidate counts "
                "28/10/53, 10d forward return -0.08%/+6.69%/+1.52%, not "
                "production-promoted on the old baseline."
            ),
            "exp-20260427-017": (
                "Rerun of the same old observed-only family; no shared adapter "
                "or current-stack Gate 4 evidence."
            ),
            "exp-20260606-003": (
                "Broad extreme 5-day selloff reversal had zero material delta; "
                "this run uses same-day gap recovery with volume/range quality, "
                "not raw multi-day selloff."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_010_gap_down_recovery_candidate_pool.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The gap-down recovery candidate source cleared Gate 4 as a "
        "replay-only/default-off lead, but no production surface was promoted. "
        "A shared parity adapter is required before use."
        if payload["gate4"]["passed"]
        else (
            "The gap-down recovery candidate source did not clear Gate 4; do "
            "not promote or locally retune this OHLCV reversal family on the "
            "frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Gap days | Trades |",
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
                days=scan.get("days_with_raw_gap_recovery_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Gap-Down Recovery Candidate Pool",
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
        "mechanism_family": "event_sensitive_free_ohlcv_reversal",
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
                "gap_recovery_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_gap_recovery_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
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
