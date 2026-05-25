"""exp-20260525-022: QQQ-confirmed volatility-contraction paper sleeve.

This follows exp-20260525-020 after its attribution showed that the
volatility-contraction top-1 sleeve failed in late_strong when Nasdaq
leadership was absent. The single changed variable is a production-visible
market confirmation gate: QQQ 20-day close-to-close return must exceed SPY
20-day close-to-close return on the signal date.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base
import exp_20260426_volatility_contraction_breakout_shadow as volatility_shadow


EXPERIMENT_ID = "exp-20260525-022"
STEM = "volatility_contraction_qqq_confirmed_sleeve"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = (
    "volatility_contraction_top1_qqq_gt_spy20_next_open_10d_fixed_notional_sleeve_v1"
)

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
SOURCE_EXP020_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260525-020"
    / "volatility_contraction_top1_fixed_notional_sleeve.json"
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30
MARKET_CONFIRM_LOOKBACK_DAYS = 20

MARKET_GATE_AUDIT: dict[str, dict[str, Any]] = {}


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = volatility_shadow

    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(volatility_shadow, name):
            setattr(volatility_shadow, name, None)


def _window_label(cfg: dict[str, str]) -> str:
    for label, row in base.WINDOWS.items():
        if (
            str(row["start"]) == str(cfg["start"])
            and str(row["end"]) == str(cfg["end"])
            and str(row["snapshot"]) == str(cfg["snapshot"])
        ):
            return label
    return f"{cfg['start']}_{cfg['end']}"


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        str(volatility_shadow._date(row)): idx
        for idx, row in enumerate(rows)
        if volatility_shadow._date(row)
    }


def _ret_to_date(
    rows: list[dict[str, Any]],
    index_by_date: dict[str, int],
    signal_date: str,
    lookback_days: int,
) -> float | None:
    idx = index_by_date.get(signal_date)
    if idx is None or idx < lookback_days:
        return None
    close_now = volatility_shadow._value(rows[idx], "Close")
    close_then = volatility_shadow._value(rows[idx - lookback_days], "Close")
    if not close_now or not close_then:
        return None
    return (close_now / close_then) - 1.0


def _market_context_for_date(
    snapshot: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any]:
    qqq_rows = volatility_shadow._series(snapshot, "QQQ")
    spy_rows = volatility_shadow._series(snapshot, "SPY")
    qqq_ret = _ret_to_date(
        qqq_rows, indexes["QQQ"], signal_date, MARKET_CONFIRM_LOOKBACK_DAYS
    )
    spy_ret = _ret_to_date(
        spy_rows, indexes["SPY"], signal_date, MARKET_CONFIRM_LOOKBACK_DAYS
    )
    if qqq_ret is None or spy_ret is None:
        return {
            "qqq_ret20_on_signal": None,
            "spy_ret20_on_signal": None,
            "qqq_minus_spy_ret20": None,
            "qqq_gt_spy20": None,
        }
    return {
        "qqq_ret20_on_signal": base._round(qqq_ret, 6),
        "spy_ret20_on_signal": base._round(spy_ret, 6),
        "qqq_minus_spy_ret20": base._round(qqq_ret - spy_ret, 6),
        "qqq_gt_spy20": qqq_ret > spy_ret,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    label = _window_label(cfg)
    entries_by_date = volatility_shadow._baseline_entries(before_result)
    dates = [
        date
        for date in volatility_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    indexes = {
        "QQQ": _date_index(volatility_shadow._series(snapshot, "QQQ")),
        "SPY": _date_index(volatility_shadow._series(snapshot, "SPY")),
    }
    all_candidates: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    rejected_missing = 0
    rejected_false = 0

    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in volatility_shadow.EXCLUDED_TICKERS:
            continue
        for row in volatility_shadow._candidate_rows(snapshot, ticker, dates):
            ab_entries = entries_by_date.get(row["date"], [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
            context = _market_context_for_date(snapshot, indexes, str(row["date"]))
            row.update(context)
            all_candidates.append(row)
            if row["qqq_gt_spy20"] is True:
                candidates.append(row)
            elif row["qqq_gt_spy20"] is None:
                rejected_missing += 1
            else:
                rejected_false += 1

    candidates.sort(
        key=lambda row: (
            row["date"],
            row["short_to_long_atr_ratio"],
            -row["candidate_day_rs_vs_spy"],
            -row["dollar_volume"],
            row["ticker"],
        )
    )
    MARKET_GATE_AUDIT[label] = {
        "raw_volatility_candidates": len(all_candidates),
        "qqq_confirmed_candidates": len(candidates),
        "rejected_qqq_not_leading_spy": rejected_false,
        "rejected_missing_market_context": rejected_missing,
        "candidate_dates_before_gate": len({row["date"] for row in all_candidates}),
        "candidate_dates_after_gate": len({row["date"] for row in candidates}),
    }
    return candidates


def _source_exp020_discriminator_precheck() -> dict[str, Any]:
    if not SOURCE_EXP020_JSON.exists():
        return {
            "available": False,
            "reason": "missing_source_exp020_json",
            "path": base._repo_rel(SOURCE_EXP020_JSON),
        }
    source = json.loads(SOURCE_EXP020_JSON.read_text(encoding="utf-8"))
    indexes_by_window: dict[str, dict[str, dict[str, int]]] = {}
    snapshots: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for label, cfg in source["backtest_protocol"]["windows"].items():
        snapshot = volatility_shadow._load_snapshot(cfg["snapshot"])
        snapshots[label] = snapshot
        indexes_by_window[label] = {
            "QQQ": _date_index(volatility_shadow._series(snapshot, "QQQ")),
            "SPY": _date_index(volatility_shadow._series(snapshot, "SPY")),
        }

    rows: list[dict[str, Any]] = []
    for label, trades in source.get("target_trades_by_window", {}).items():
        for trade in trades:
            row = dict(trade)
            row["window"] = label
            row.update(
                _market_context_for_date(
                    snapshots[label],
                    indexes_by_window[label],
                    str(row.get("signal_date") or row.get("date") or ""),
                )
            )
            rows.append(row)

    by_gate: dict[str, dict[str, Any]] = {}
    for gate_value, trades in sorted(
        _group_by(rows, lambda row: str(row.get("qqq_gt_spy20"))).items()
    ):
        by_window = {
            label: round(
                sum(
                    float(row.get("pnl") or 0.0)
                    for row in trades
                    if row.get("window") == label
                ),
                2,
            )
            for label in base.WINDOWS
        }
        by_gate[gate_value] = {
            "trade_count": len(trades),
            "total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
            "win_rate": base._round(
                sum(1 for row in trades if float(row.get("pnl") or 0.0) > 0)
                / len(trades),
                6,
            )
            if trades
            else None,
            "pnl_by_window": by_window,
        }
    return {
        "available": True,
        "source_experiment_id": "exp-20260525-020",
        "source_decision": source.get("decision"),
        "source_rejection_reason": source.get("rejection_reason"),
        "qqq_gt_spy20_bucket_summary": by_gate,
        "interpretation": (
            "In the rejected source sleeve, QQQ-leading-SPY isolated the late_strong "
            "failure without changing volatility-compression or breakout thresholds."
        ),
    }


def _group_by(rows: list[dict[str, Any]], key_fn: Any) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(key_fn(row))].append(row)
    return grouped


def _decision_from_gate(payload: dict[str, Any]) -> str:
    return (
        "promising_replay_only_volatility_contraction_qqq_confirmed_sleeve"
        if payload["gate4"]["passed"]
        else "rejected_volatility_contraction_qqq_confirmed_sleeve"
    )


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = _decision_from_gate(payload)
    market_context_missing = sum(
        int(row.get("rejected_missing_market_context") or 0)
        for row in MARKET_GATE_AUDIT.values()
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Volatility-contraction breakouts may need Nasdaq leadership confirmation. "
        "If QQQ's 20-day return exceeds SPY's 20-day return on the signal date, "
        "the same top-1 next-open fixed-notional sleeve should preserve the "
        "mid/old upside from exp-020 while removing the late_strong failure mode."
    )
    payload["change_type"] = "volatility_contraction_qqq_confirmed_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 2
    payload["nearby_prior_experiments"] = [
        "exp-20260426-045",
        "exp-20260525-007",
        "exp-20260525-020",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = (
        "exp020_failure_attribution_plus_materially_different_production_visible_"
        "qqq_vs_spy_market_confirmation_field"
    )
    payload["source_discriminator_precheck"] = _source_exp020_discriminator_precheck()
    payload["market_gate_audit"] = MARKET_GATE_AUDIT
    payload["parameters"]["shadow_entry_filters"] = {
        "short_atr_days": volatility_shadow.SHORT_ATR_DAYS,
        "long_atr_days": volatility_shadow.LONG_ATR_DAYS,
        "max_short_to_long_atr_ratio": volatility_shadow.MAX_SHORT_TO_LONG_ATR_RATIO,
        "breakout_close_above_prior_n_day_high": volatility_shadow.BREAKOUT_LOOKBACK_DAYS,
        "close_above_n_day_moving_average": volatility_shadow.MA_DAYS,
        "candidate_day_rs_vs_spy_min": volatility_shadow.MIN_CANDIDATE_RS_VS_SPY,
        "min_candidate_day_dollar_volume": volatility_shadow.MIN_DOLLAR_VOLUME,
    }
    payload["parameters"]["market_confirmation_gate"] = {
        "field": "QQQ 20 trading-day close-to-close return > SPY 20 trading-day close-to-close return",
        "lookback_trading_days": MARKET_CONFIRM_LOOKBACK_DAYS,
        "source": "canonical OHLCV snapshot Close values",
        "known_at": "after signal-date close, before next-open paper entry",
        "missing_context_policy": "reject candidate",
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "short_to_long_atr_ratio asc",
        "candidate_day_rs_vs_spy desc",
        "dollar_volume desc",
        "ticker asc",
    ]
    payload["parameters"]["acceptance"].update(
        {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
            "warning": (
                "Because the QQQ confirmation was selected from exp-020 attribution, "
                "a pass remains replay-only until forward paper rows confirm it."
            ),
        }
    )
    payload["gate2"]["runtime_fields"].extend(
        [
            "QQQ OHLCV Close on signal date and 20 trading days prior",
            "SPY OHLCV Close on signal date and 20 trading days prior",
            "computed qqq_gt_spy20 market confirmation",
        ]
    )
    payload["gate2"]["market_confirmation"] = {
        "missing_market_context_candidate_count": market_context_missing,
        "passed": market_context_missing == 0,
        "audit": MARKET_GATE_AUDIT,
    }
    payload["gate2"]["passed"] = payload["gate2"]["passed"] and market_context_missing == 0
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool: volatility-contraction breakouts may be "
            "profitable when confirmed by Nasdaq leadership, measured as QQQ "
            "20d return > SPY 20d return."
        ),
        "2_history_check": {
            "exp-20260426-045": (
                "Observed-only volatility-contraction audit; no current canonical "
                "before/after replay."
            ),
            "exp-20260525-007": (
                "QQQ-confirmed consumer-platform sleeve failed; that was a governed "
                "ticker pool, not this OHLCV compression entry source."
            ),
            "exp-20260525-020": (
                "Same volatility-contraction source added +10.43% aggregate EV but "
                "failed Gate 4 because late_strong EV/PnL regressed and drawdown "
                "drift exceeded the 0.5pp guardrail."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=20 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails. A pass is replay-only because the "
            "field came from exp-020 attribution."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260525_022_volatility_contraction_qqq_confirmed_sleeve.py"
        ),
    }
    payload["why_not_other_changes"] = (
        "Did not change ATR compression, breakout, sector, rank, sizing, or exit "
        "thresholds. Did not retry LLM soft-ranking because coverage remains sparse. "
        "The chosen discriminator is an orthogonal, free OHLCV market-confirmation "
        "field surfaced by exp-020 failure attribution."
    )
    payload["interpretation"] = (
        "The QQQ-confirmed volatility-contraction paper sleeve cleared Gate 4 as a "
        "replay-only lead. It is not production-promoted; the next evidence needed "
        "is forward paper replacement-value rows or a shared default-off adapter."
        if payload["gate4"]["passed"] and payload["gate2"]["passed"]
        else (
            "The QQQ-confirmed volatility-contraction paper sleeve did not clear "
            "the gates. Do not promote it; use the attribution record before any "
            "nearby retry."
        )
    )
    payload["next_evidence_needed"] = (
        "Run this exact QQQ-confirmed sleeve forward as default-off paper and log "
        "replacement value before any live/default promotion."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result still requires a shared default-off paper adapter that "
        "computes the same QQQ/SPY 20d close-to-close field in production and "
        "backtest, daily report exposure, a forward replacement-value ledger, and "
        "parity tests before live/default behavior changes."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
        base._repo_rel(SOURCE_EXP020_JSON),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | QQQ-gated candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} QQQ-Confirmed Volatility-Contraction Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: keep the exp-020 volatility-contraction top-1 "
                "paper sleeve, but require QQQ 20d return > SPY 20d return on "
                "the signal date."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Exp-020 Discriminator Precheck",
            "",
            "```json",
            json.dumps(
                payload["source_discriminator_precheck"],
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Market Gate Audit",
            "",
            "```json",
            json.dumps(payload["market_gate_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
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


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "QQQ-confirmed volatility-contraction sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_base_module()
    base._candidate_rows_for_window = _candidate_rows_for_window
    payload = _update_payload(base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate2": payload["gate2"]["market_confirmation"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
