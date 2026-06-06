"""exp-20260606-016: revision velocity with surprise-history confirmation.

Replay-only alpha search. This tests one production-visible free-data quality
field on top of the prior EPS estimate-revision velocity scout: keep the same
20-trading-day positive EPS estimate-revision candidate source, but require a
positive historical earnings-surprise profile before selecting the daily top-1
next-open paper candidate.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260604_029_analyst_revision_velocity_candidate_pool as revision_base


EXPERIMENT_ID = "exp-20260606-016"
STEM = "revision_surprise_history_confirmed"
TRIAL_FAMILY = "analyst_revision_surprise_history_confirmed_candidate_pool"
TRIAL_VARIANT_ID = "revision_velocity_positive_surprise_history_top1_v1"
CHANGED_VARIABLE = "positive_surprise_history_confirmed_revision_velocity_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = revision_base.BASE_NOTIONAL_USD
HOLD_DAYS = revision_base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = revision_base.MAX_PAPER_TRADES_PER_DAY

MIN_PRICE = revision_base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20 = revision_base.MIN_AVG_DOLLAR_VOLUME_20
MIN_VOLUME_RATIO_20 = revision_base.MIN_VOLUME_RATIO_20
MIN_CLOSE_LOCATION = revision_base.MIN_CLOSE_LOCATION
MIN_RET20_EXCESS_SPY = revision_base.MIN_RET20_EXCESS_SPY

REVISION_LOOKBACK_TRADING_DAYS = revision_base.REVISION_LOOKBACK_TRADING_DAYS
MIN_EPS_ESTIMATE_REVISION_20D_PCT = revision_base.MIN_EPS_ESTIMATE_REVISION_20D_PCT
MIN_DAYS_TO_EARNINGS = revision_base.MIN_DAYS_TO_EARNINGS
MAX_DAYS_TO_EARNINGS = revision_base.MAX_DAYS_TO_EARNINGS

MIN_SURPRISE_HISTORY_COUNT = 4
MIN_POSITIVE_SURPRISE_COUNT = 3
MIN_POSITIVE_SURPRISE_RATIO = 0.75
MIN_AVG_HISTORICAL_SURPRISE_PCT = 0.0

MIN_TARGET_TRADES = revision_base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = revision_base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = revision_base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = revision_base.MAX_POSITIVE_HHI

ROOT = revision_base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_016_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
REVISION_ROWS_JSON = OUT_DIR / "earnings_revision_rows_summary.json"
REVISION_FILES_JSON = OUT_DIR / "earnings_revision_snapshot_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

framework = revision_base.framework
ftd_base = revision_base.ftd_base
_ORIGINAL_BUILD_PAYLOAD = revision_base._build_payload
_ORIGINAL_ARTIFACT = revision_base._artifact


def _surprise_confirmation_passed(revision_row: dict[str, Any]) -> tuple[bool, str | None]:
    positive_count = revision_base._float(revision_row.get("positive_surprise_count"))
    history_count = revision_base._float(revision_row.get("surprise_history_count"))
    avg_surprise = revision_base._float(revision_row.get("avg_historical_surprise_pct"))
    if positive_count is None or history_count is None or avg_surprise is None:
        return False, "missing_surprise_history"
    if history_count < MIN_SURPRISE_HISTORY_COUNT:
        return False, "surprise_history_too_short"
    positive_ratio = positive_count / history_count if history_count > 0 else 0.0
    if positive_count < MIN_POSITIVE_SURPRISE_COUNT:
        return False, "positive_surprise_count_below_threshold"
    if positive_ratio < MIN_POSITIVE_SURPRISE_RATIO:
        return False, "positive_surprise_ratio_below_threshold"
    if avg_surprise < MIN_AVG_HISTORICAL_SURPRISE_PCT:
        return False, "avg_historical_surprise_negative"
    return True, None


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy = ftd_base._prepared_frame(frames["SPY"]) if "SPY" in frames else None
    if spy is None:
        raise RuntimeError("SPY is required for ret20 excess control")

    universe = {ticker.upper() for ticker in frames}
    revision_context = revision_base._load_revision_context(universe, frames)
    rows_by_date_ticker = revision_context["rows_by_date_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])
    spy_closes = [float(value) for value in spy["Close"].tolist()]

    for ticker, frame in frames.items():
        ticker = ticker.upper()
        if ticker in framework.base.shadow.EXCLUDED_TICKERS or ticker in {"SPY", "QQQ", "IWM"}:
            continue
        fr = ftd_base._prepared_frame(frame)
        closes = [float(value) for value in fr["Close"].tolist()]
        pos_by_date = {idx: pos for pos, idx in enumerate(fr.index)}
        for asof in fr.loc[start:end].index:
            signal_date = str(asof.date())
            revision_row = rows_by_date_ticker.get(signal_date, {}).get(ticker)
            if revision_row is None:
                continue
            raw_pass_counts["snapshot_revision_row"] += 1
            revision = revision_base._float(revision_row.get("eps_estimate_revision_20d_pct"))
            days_to_earnings = revision_base._float(revision_row.get("days_to_earnings"))
            if revision is None or days_to_earnings is None:
                reject_counts["missing_revision_or_dte"] += 1
                continue
            if revision < MIN_EPS_ESTIMATE_REVISION_20D_PCT:
                reject_counts["revision_below_threshold"] += 1
                continue
            if not (MIN_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_DAYS_TO_EARNINGS):
                reject_counts["days_to_earnings_outside_window"] += 1
                continue
            raw_pass_counts["revision_velocity_passed"] += 1

            surprise_ok, surprise_reject = _surprise_confirmation_passed(revision_row)
            if not surprise_ok:
                reject_counts[str(surprise_reject)] += 1
                continue
            raw_pass_counts["surprise_history_confirmed"] += 1

            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue
            row = fr.loc[asof]
            spy_pos = int(spy.index.get_loc(asof))
            ret20 = framework._ret(closes, pos, 20)
            spy_ret20 = framework._ret(spy_closes, spy_pos, 20)
            values = {
                "close": float(row["Close"]),
                "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
                "volume_ratio_20": float(row["volume_ratio_20"]),
                "close_location": float(row["close_location"]),
                "ret20_excess_spy": (
                    ret20 - spy_ret20
                    if ret20 is not None and spy_ret20 is not None
                    else None
                ),
            }
            if any(value is None or not math.isfinite(value) for value in values.values()):
                continue
            raw_pass_counts["fields_non_null"] += 1
            if values["close"] < MIN_PRICE:
                continue
            if values["avg_dollar_volume_20"] < MIN_AVG_DOLLAR_VOLUME_20:
                continue
            raw_pass_counts["liquidity_passed"] += 1
            if bool(row.get("breakout_20")) is not True:
                continue
            raw_pass_counts["breakout_passed"] += 1
            if values["volume_ratio_20"] < MIN_VOLUME_RATIO_20:
                continue
            if values["close_location"] < MIN_CLOSE_LOCATION:
                continue
            if values["ret20_excess_spy"] < MIN_RET20_EXCESS_SPY:
                continue
            raw_pass_counts["price_action_passed"] += 1

            same_day_core = core_entries.get(signal_date, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                continue
            positive_count = revision_base._float(revision_row.get("positive_surprise_count")) or 0.0
            history_count = revision_base._float(revision_row.get("surprise_history_count")) or 0.0
            surprise_ratio = positive_count / history_count if history_count > 0 else 0.0
            avg_surprise = revision_base._float(revision_row.get("avg_historical_surprise_pct")) or 0.0
            score = (
                min(revision, 0.50) * 10.0
                + values["ret20_excess_spy"] * 2.0
                + min(values["volume_ratio_20"], 4.0) * 0.25
                + values["close_location"]
                + 0.10 * surprise_ratio
                + 0.005 * min(avg_surprise, 25.0)
            )
            candidate = {
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "window": label,
                "score": framework._round(score, 6),
                "prior_snapshot_date": revision_row.get("prior_snapshot_date"),
                "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
                "eps_estimate_current": revision_row.get("eps_estimate_current"),
                "eps_estimate_prior": revision_row.get("eps_estimate_prior"),
                "eps_estimate_revision_20d_pct": framework._round(revision, 6),
                "days_to_earnings": framework._round(days_to_earnings, 2),
                "avg_historical_surprise_pct": revision_row.get("avg_historical_surprise_pct"),
                "positive_surprise_count": revision_row.get("positive_surprise_count"),
                "surprise_history_count": revision_row.get("surprise_history_count"),
                "positive_surprise_ratio": framework._round(surprise_ratio, 6),
                "avg_dollar_volume_20": framework._round(values["avg_dollar_volume_20"], 2),
                "volume_ratio_20": framework._round(values["volume_ratio_20"], 6),
                "close_location": framework._round(values["close_location"], 6),
                "ret20_excess_spy": framework._round(values["ret20_excess_spy"], 6),
                "same_day_core_entry_count": len(same_day_core),
                "same_ticker_core_overlap": False,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
                "source_caveat": revision_row.get("source_caveat"),
            }
            if len(examples) < 20:
                examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "revision_20d": candidate["eps_estimate_revision_20d_pct"],
                        "positive_surprise_count": candidate["positive_surprise_count"],
                        "surprise_history_count": candidate["surprise_history_count"],
                        "avg_historical_surprise_pct": candidate[
                            "avg_historical_surprise_pct"
                        ],
                    }
                )
            candidates_by_date.setdefault(signal_date, []).append(candidate)

    selected: list[dict[str, Any]] = []
    raw_candidate_count = 0
    for signal_date, rows in sorted(candidates_by_date.items()):
        raw_candidate_count += len(rows)
        rows.sort(
            key=lambda item: (
                -float(item["score"]),
                -float(item["eps_estimate_revision_20d_pct"]),
                -float(item["ret20_excess_spy"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "revision_reject_counts": dict(sorted(reject_counts.items())),
        "revision_examples": examples,
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
        "surprise_history_gate": {
            "min_surprise_history_count": MIN_SURPRISE_HISTORY_COUNT,
            "min_positive_surprise_count": MIN_POSITIVE_SURPRISE_COUNT,
            "min_positive_surprise_ratio": MIN_POSITIVE_SURPRISE_RATIO,
            "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
        },
    }


def _build_payload() -> dict[str, Any]:
    payload = _ORIGINAL_BUILD_PAYLOAD()
    numeric_passed = bool(payload["gate4"]["passed"])
    passed = False
    if numeric_passed:
        decision = "positive_proxy_lead_not_promoted_requires_revision_surprise_adapter"
        rationale = (
            "Numeric Gate 4 passed, but the historical EPS-estimate and "
            "surprise-history snapshot source remains proxy-grade. Do not "
            "retain or promote until a shared PIT analyst-revision adapter "
            "proves production/backtest parity."
        )
    else:
        decision = "rejected_revision_surprise_history_confirmed_candidate_pool"
        rationale = (
            "Gate 4 failed; the surprise-history confirmation did not make "
            "revision velocity robust enough for retention."
        )
    actual_success = 1 if passed else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    payload["gate4"]["decision"] = decision
    payload["gate4"]["rationale"] = rationale
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "rejected" if not passed else "accepted",
            "decision": decision,
            "accepted": passed,
            "hypothesis": (
                "EPS estimate revision velocity candidates with positive "
                "historical earnings-surprise confirmation may keep the "
                "revision alpha while reducing weak-window tail risk."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "analyst_revision_expectation_trajectory",
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260604-029",
                "exp-20260605-029",
                "exp-20260604-020",
                "exp-20260604-001",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_production_visible_revision_quality_field",
            "interpretation": rationale,
            "rejection_reason": None if numeric_passed else "; ".join(
                payload["gate4"]["failed_gates"]
            ),
            "prediction": {
                "success_probability": 0.22,
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
                "main_failure_modes": [
                    "old_thin_regression",
                    "thin_sample",
                    "latest_surprise_near_repeat",
                    "drawdown_drift",
                ],
                "confidence_reason": (
                    "The raw revision-velocity scout had positive aggregate EV "
                    "and acceptable drawdown but old_thin regressed; historical "
                    "surprise confirmation is already present in replayable "
                    "daily earnings snapshots and is distinct from the failed "
                    "persistent-underreaction variant."
                ),
                "recorded_at": "2026-06-06T14:06:23+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.22 - actual_success) ** 2, 6),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Ticker must pass the exp-20260604-029 20d EPS estimate "
                "revision velocity source and also have at least 3 positive "
                "historical earnings surprises among at least 4 records, a "
                "positive surprise ratio >= 75%, and non-negative average "
                "historical surprise."
            ),
            "min_surprise_history_count": MIN_SURPRISE_HISTORY_COUNT,
            "min_positive_surprise_count": MIN_POSITIVE_SURPRISE_COUNT,
            "min_positive_surprise_ratio": MIN_POSITIVE_SURPRISE_RATIO,
            "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: positive EPS estimate revision velocity "
            "is cleaner when the issuer has a history of actually beating "
            "earnings expectations, reducing estimate-only optimism risk."
        ),
        "2_history_check": {
            "exp-20260604-029": (
                "Raw 20d EPS revision velocity was aggregate-positive "
                "(+0.2400 EV / +$3,025.32) but old_thin regressed."
            ),
            "exp-20260605-029": (
                "Persistent 10d+20d revision underreaction became aggregate "
                "negative and regressed late_strong."
            ),
            "exp-20260604-020": (
                "PEAD persistent revision bucket lacked enough closed positive "
                "rows, so PEAD-specific promotion remains blocked."
            ),
            "exp-20260604-001": (
                "Latest-vs-average surprise support failed; this run uses "
                "surprise history only as a quality confirmation for revision "
                "velocity candidates, not a PEAD notional scalar."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; positive aggregate "
            "EV/PnL; no EV/PnL-regressed window; sample, drawdown, survival, "
            "and concentration guards pass; source provenance must be shared "
            "and parity-safe before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_016_revision_surprise_history_confirmed.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["production_impact"]["parity_note"] = (
        "Replay-only/default-off. This experiment changes no production code. "
        "A positive result would require a shared default-off adapter that "
        "computes EPS estimate revision velocity and historical surprise "
        "confirmation from the same PIT earnings snapshot surface in both "
        "replay and daily production before any report queue, paper ledger, "
        "ranking, sizing, watchlist, or order surface could change."
    )
    payload["anti_js"] = "No JavaScript was used."
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    text = _ORIGINAL_ARTIFACT(payload)
    return text.replace(
        "Analyst Revision Velocity Candidate Pool",
        "Revision Surprise-History Confirmed Candidate Pool",
    )


def _patch_revision_base() -> None:
    revision_base.EXPERIMENT_ID = EXPERIMENT_ID
    revision_base.STEM = STEM
    revision_base.TRIAL_FAMILY = TRIAL_FAMILY
    revision_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    revision_base.RULE_VERSION = RULE_VERSION
    revision_base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    revision_base.HOLD_DAYS = HOLD_DAYS
    revision_base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    revision_base.MIN_PRICE = MIN_PRICE
    revision_base.MIN_AVG_DOLLAR_VOLUME_20 = MIN_AVG_DOLLAR_VOLUME_20
    revision_base.MIN_VOLUME_RATIO_20 = MIN_VOLUME_RATIO_20
    revision_base.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    revision_base.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    revision_base.REVISION_LOOKBACK_TRADING_DAYS = REVISION_LOOKBACK_TRADING_DAYS
    revision_base.MIN_EPS_ESTIMATE_REVISION_20D_PCT = MIN_EPS_ESTIMATE_REVISION_20D_PCT
    revision_base.MIN_DAYS_TO_EARNINGS = MIN_DAYS_TO_EARNINGS
    revision_base.MAX_DAYS_TO_EARNINGS = MAX_DAYS_TO_EARNINGS
    revision_base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    revision_base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    revision_base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    revision_base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    revision_base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    revision_base.OUT_DIR = OUT_DIR
    revision_base.OUT_JSON = OUT_JSON
    revision_base.BEFORE_JSON = BEFORE_JSON
    revision_base.AFTER_JSON = AFTER_JSON
    revision_base.REVISION_ROWS_JSON = REVISION_ROWS_JSON
    revision_base.REVISION_FILES_JSON = REVISION_FILES_JSON
    revision_base.LOG_JSON = LOG_JSON
    revision_base.ARTIFACT_MD = ARTIFACT_MD
    revision_base.CARD_MD = CARD_MD
    revision_base.EXPERIMENT_LOG = EXPERIMENT_LOG
    revision_base._candidate_rows_for_window = _candidate_rows_for_window
    revision_base._build_payload = _build_payload
    revision_base._artifact = _artifact


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _patch_revision_base()
    revision_base._patch_framework()
    return framework.run(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": framework._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
