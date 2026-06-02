"""exp-20260602-015: relative-strength acceleration candidate pool.

This alpha search tests one stock-only, free-OHLCV default-off paper source.
It looks for liquid stocks whose recent 5-day excess return versus SPY
accelerates above the prior 15-day excess while 20-day relative strength and
signal-day close quality remain strong.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_037_ticker_accumulation_quality_breakout as framework


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-015"
STEM = "rs_acceleration_candidate_pool"
TRIAL_FAMILY = "rs_acceleration_candidate_pool"
CHANGED_VARIABLE = "rs_acceleration_top1_candidate_source_v1"
RULE_VERSION = "stock_rs_acceleration_top1_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_015_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

RECENT_RS_DAYS = 5
FULL_RS_DAYS = 20
PRIOR_RS_DAYS = FULL_RS_DAYS - RECENT_RS_DAYS
MOVING_AVERAGE_DAYS = 50
AVG_DOLLAR_VOLUME_DAYS = 20
NEAR_HIGH_LOOKBACK_DAYS = 20
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RS5_VS_SPY = 0.025
MIN_RS20_VS_SPY = 0.04
MIN_RS_ACCELERATION = 0.015
MIN_SIGNAL_CLOSE_LOCATION = 0.70
MIN_CLOSE_VS_PRIOR_20D_HIGH = 0.965

MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = framework.EXCLUDED_TICKERS


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(framework.base._safe(payload), handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    framework.AFTER_AGG_JSON = AFTER_AGG_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework._candidate_rows_for_window = _candidate_rows_for_window


def _avg_dollar_volume(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            continue
        values.append(float(close) * float(volume))
    if len(values) < days:
        return None
    return sum(values) / len(values)


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = [
        date
        for date in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    min_idx = max(
        MOVING_AVERAGE_DAYS,
        FULL_RS_DAYS,
        AVG_DOLLAR_VOLUME_DAYS,
        NEAR_HIGH_LOOKBACK_DAYS,
    )

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        for date in dates:
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < FULL_RS_DAYS:
                audit["insufficient_history"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if not close or volume is None:
                audit["missing_close_or_volume"] += 1
                continue

            avg_dollar_volume = _avg_dollar_volume(
                rows,
                idx,
                AVG_DOLLAR_VOLUME_DAYS,
            )
            if avg_dollar_volume is None:
                audit["missing_avg_dollar_volume"] += 1
                continue
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                audit["low_avg_dollar_volume"] += 1
                continue

            ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if ma50 is None or float(close) <= ma50:
                audit["not_above_ma50"] += 1
                continue

            prior_high_20d = framework._prior_high(
                rows,
                idx,
                NEAR_HIGH_LOOKBACK_DAYS,
                "High",
            )
            if not prior_high_20d:
                audit["missing_near_high_context"] += 1
                continue
            close_vs_prior_high = float(close) / float(prior_high_20d)
            if close_vs_prior_high < MIN_CLOSE_VS_PRIOR_20D_HIGH:
                audit["not_near_prior_20d_high"] += 1
                continue

            close_location = framework._close_location(rows[idx])
            if close_location is None or close_location < MIN_SIGNAL_CLOSE_LOCATION:
                audit["weak_signal_close_location"] += 1
                continue

            ret5 = framework._close_return(rows, idx - RECENT_RS_DAYS, idx)
            ret20 = framework._close_return(rows, idx - FULL_RS_DAYS, idx)
            prior15 = framework._close_return(
                rows,
                idx - FULL_RS_DAYS,
                idx - RECENT_RS_DAYS,
            )
            spy_ret5 = framework._close_return(
                spy_rows,
                spy_idx - RECENT_RS_DAYS,
                spy_idx,
            )
            spy_ret20 = framework._close_return(
                spy_rows,
                spy_idx - FULL_RS_DAYS,
                spy_idx,
            )
            spy_prior15 = framework._close_return(
                spy_rows,
                spy_idx - FULL_RS_DAYS,
                spy_idx - RECENT_RS_DAYS,
            )
            if any(
                value is None
                for value in (ret5, ret20, prior15, spy_ret5, spy_ret20, spy_prior15)
            ):
                audit["missing_relative_strength"] += 1
                continue

            rs5_vs_spy = float(ret5) - float(spy_ret5)
            rs20_vs_spy = float(ret20) - float(spy_ret20)
            prior15_vs_spy = float(prior15) - float(spy_prior15)
            rs_acceleration = rs5_vs_spy - prior15_vs_spy
            if rs5_vs_spy < MIN_RS5_VS_SPY:
                audit["rs5_too_weak"] += 1
                continue
            if rs20_vs_spy < MIN_RS20_VS_SPY:
                audit["rs20_too_weak"] += 1
                continue
            if rs_acceleration < MIN_RS_ACCELERATION:
                audit["rs_acceleration_too_weak"] += 1
                continue

            ab_entries = entries_by_date.get(date, [])
            candidates.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "avg_dollar_volume_20d": framework.base._round(
                        avg_dollar_volume,
                        2,
                    ),
                    "ma50": framework.base._round(ma50, 4),
                    "prior_high_20d": framework.base._round(prior_high_20d, 4),
                    "close_vs_prior_high_20d": framework.base._round(
                        close_vs_prior_high,
                        6,
                    ),
                    "signal_close_location": framework.base._round(
                        close_location,
                        6,
                    ),
                    "ret5": framework.base._round(ret5, 6),
                    "ret20": framework.base._round(ret20, 6),
                    "prior15_return": framework.base._round(prior15, 6),
                    "spy_ret5": framework.base._round(spy_ret5, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "spy_prior15_return": framework.base._round(spy_prior15, 6),
                    "rs5_vs_spy": framework.base._round(rs5_vs_spy, 6),
                    "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                    "prior15_vs_spy": framework.base._round(prior15_vs_spy, 6),
                    "rs_acceleration": framework.base._round(rs_acceleration, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "known_at": "after_signal_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["rs_acceleration"]),
            -float(row["rs5_vs_spy"]),
            -float(row["rs20_vs_spy"]),
            -float(row["signal_close_location"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_rs_acceleration_candidate_pool_replay_lead"
        if gate4["passed"]
        else "rejected_rs_acceleration_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.29,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "momentum_chase_reversal",
            "late_strong_regression",
            "thin_target_windows",
            "positive_pnl_concentration",
        ],
        "confidence_reason": (
            "Meta research favors production-visible default-off paper "
            "adapters, but recent OHLCV candidate pools often overfit; this "
            "variant avoids VCP/reclaim and uses only a single RS-acceleration "
            "source."
        ),
        "recorded_at": "2026-06-02T10:18:25+00:00",
        "brier_score": round((0.29 - actual_success) ** 2, 6),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Stock-only relative-strength acceleration candidates may add "
                "default-off replacement alpha when recent 5-day excess versus "
                "SPY accelerates above the prior 15-day excess while 20-day "
                "relative strength, high-close quality, and liquidity stay strong."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260426-047",
                "exp-20260426-051",
                "exp-20260429-002",
                "exp-20260528-037",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "free_ohlcv_recent_relative_strength_acceleration_candidate_source",
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "recent_rs_days": RECENT_RS_DAYS,
                "full_rs_days": FULL_RS_DAYS,
                "prior_rs_days": PRIOR_RS_DAYS,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "near_high_lookback_days": NEAR_HIGH_LOOKBACK_DAYS,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_rs5_vs_spy": MIN_RS5_VS_SPY,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_rs_acceleration": MIN_RS_ACCELERATION,
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "min_close_vs_prior_20d_high": MIN_CLOSE_VS_PRIOR_20D_HIGH,
                "source_definition": [
                    "stock ticker only; no ETF/proxy tickers",
                    "20-day average dollar volume >= 50 million",
                    "close above prior 50-day moving average",
                    "close >= 96.5% of prior 20-day high",
                    "signal-day close location >= 0.70",
                    "5-day return exceeds SPY by at least 2.5%",
                    "20-day return exceeds SPY by at least 4.0%",
                    "5-day excess minus prior 15-day excess >= 1.5%",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "rs_acceleration desc",
                    "rs5_vs_spy desc",
                    "rs20_vs_spy desc",
                    "signal_close_location desc",
                    "avg_dollar_volume_20d desc",
                    "ticker asc",
                ],
                "locked_variables": [
                    "core universe membership",
                    "core signal generation",
                    "core ranking",
                    "core position sizing",
                    "core exits",
                    "portfolio heat",
                    "slot rules",
                    "LLM/news replay",
                    "watchlists",
                    "live/default orders",
                ],
                "acceptance": payload["parameters"]["acceptance"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: near-high stocks with accelerating "
                    "recent relative strength may add cleaner replacement alpha "
                    "than static momentum screens."
                ),
                "2_history_check": {
                    "exp-20260426-047_and_051": (
                        "Pullback reclaim shadow was promising but failed "
                        "production-path replay; this is not a reclaim pattern."
                    ),
                    "exp-20260429-002": (
                        "Sector persistence failed under slot-aware replay; this "
                        "does not use sector persistence."
                    ),
                    "exp-20260525-020_to_024": (
                        "Volatility-contraction/VCP has accepted and rejected "
                        "nearby work; this run avoids range-compression/VCP fields."
                    ),
                    "exp-20260528-037": (
                        "OBV plus price breakout was a distinct accumulation "
                        "source; this run tests recent RS acceleration instead."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; 3/3 EV-improved windows; no PnL-regressed window; "
                    ">=20 paper trades across all 3 windows; drawdown drift "
                    "<=0.5pp; survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_015_rs_acceleration_candidate_pool.py"
                ),
            },
            "gate2": {
                **payload["gate2"],
                "target_trade_field_coverage": framework._field_coverage(
                    all_target_trades,
                    [
                        "ticker",
                        "signal_date",
                        "entry_date",
                        "exit_date",
                        "entry_price",
                        "exit_price",
                        "pnl",
                        "known_at",
                        "rs5_vs_spy",
                        "rs20_vs_spy",
                        "prior15_vs_spy",
                        "rs_acceleration",
                        "signal_close_location",
                        "avg_dollar_volume_20d",
                        "close_vs_prior_high_20d",
                    ],
                ),
                "runtime_fields": [
                    "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                    "SPY OHLCV rows for same-window relative strength",
                    "operator_inputs/open_positions.json entry_date",
                    "operator_inputs/open_positions.json target_price",
                ],
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "A retained result would require a shared default-off paper "
                    "adapter and parity tests before any daily report or live/"
                    "default behavior changes."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe joins remain "
                "sparse. Skipped 13F because the known audit shows no usable "
                "PIT rows. Skipped VCP/inside-day/reclaim and Companyfacts "
                "adjacent retunes because recent logs require forward rows or "
                "materially new fields. This uses one free-OHLCV RS-acceleration "
                "field."
            ),
            "interpretation": (
                "The RS acceleration sleeve cleared Gate 4 as a replay-only "
                "lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The RS acceleration sleeve did not clear Gate 4. Do not "
                    "promote it or retry nearby RS5/RS20 acceleration thresholds "
                    "on these frozen windows without forward paper rows or an "
                    "orthogonal source-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or an orthogonal free-data "
                "quality field; do not simply retune RS acceleration thresholds."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
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
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Relative-Strength Acceleration Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits stock-only recent RS-acceleration candidates, top-1 per day, next-open entry, ten-trading-day exit.",
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
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    _write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    _write_json(LOG_JSON, payload)
    report = _build_report(payload)
    _write_text(ARTIFACT_MD, report)
    _write_text(CARD_MD, report)

    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)
    _write_manifest()


def _write_manifest() -> None:
    files = {
        "runner": _repo_rel(Path(__file__)),
        "result": _repo_rel(OUT_JSON),
        "before_aggregate": _repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": _repo_rel(AFTER_AGG_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "card": _repo_rel(CARD_MD),
        "artifact": _repo_rel(ARTIFACT_MD),
        "manifest": _repo_rel(MANIFEST_JSON),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
