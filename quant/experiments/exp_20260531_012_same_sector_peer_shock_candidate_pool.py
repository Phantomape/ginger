"""exp-20260531-012: same-sector peer-shock candidate pool.

This alpha search tests one free, production-visible OHLCV relation field:
after a strong positive same-sector peer shock, a liquid unshocked peer with
basic trend/RS confirmation becomes a default-off paper candidate.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_037_ticker_accumulation_quality_breakout as framework

from broad_market_sector_map import RULE_VERSION as SECTOR_RULE_VERSION
from broad_market_sector_map import load_cache, lookup_sector


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-012"
STEM = "same_sector_peer_shock_candidate_pool"
TRIAL_FAMILY = "same_sector_peer_shock_candidate_pool"
CHANGED_VARIABLE = "same_sector_strong_positive_peer_shock_candidate_source_v1"
RULE_VERSION = "same_sector_strong_positive_peer_shock_top1_10d_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_012_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

LOOKBACK_DAYS = 5
VOLUME_LOOKBACK_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
HOLD_DAYS = 10

MIN_PEER_GAP = 0.05
MIN_PEER_VOLUME_RATIO = 1.80
MIN_PEER_DAY_RETURN = 0.03
MIN_WEIGHTED_PEER_SHOCK_SCORE = 0.03
MIN_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MIN_CLOSE_PRICE = 10.0
MIN_RS_20D_VS_SPY = 0.0
MIN_SECTOR_MEMBERS = 4

EXCLUDED_TICKERS = set(framework.EXCLUDED_TICKERS)


def _patch_framework() -> None:
    for module in (framework, framework.base):
        module.EXPERIMENT_ID = EXPERIMENT_ID
        module.STEM = STEM
        module.TRIAL_FAMILY = TRIAL_FAMILY
        module.CHANGED_VARIABLE = CHANGED_VARIABLE
        module.OUT_DIR = OUT_DIR
        module.OUT_JSON = OUT_JSON
        module.LOG_JSON = LOG_JSON
        module.TICKET_JSON = TICKET_JSON
        module.ARTIFACT_MD = ARTIFACT_MD
        module.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.RULE_VERSION = RULE_VERSION
    framework.EXCLUDED_TICKERS = EXCLUDED_TICKERS
    framework.base.HOLD_DAYS = HOLD_DAYS
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _avg_dollar_volume(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
) -> float | None:
    if idx + 1 < days:
        return None
    values: list[float] = []
    for row in rows[idx + 1 - days : idx + 1]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if values else None


def _volume_ratio(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    volume = framework.ohlcv_helper._value(rows[idx], "Volume")
    prior = [
        framework.ohlcv_helper._value(row, "Volume")
        for row in rows[idx - days : idx]
    ]
    clean = [float(value) for value in prior if isinstance(value, (int, float))]
    if volume is None or len(clean) < days:
        return None
    avg = sum(clean) / len(clean)
    return float(volume) / avg if avg else None


def _day_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx <= 0:
        return None
    prev_close = framework.ohlcv_helper._value(rows[idx - 1], "Close")
    close = framework.ohlcv_helper._value(rows[idx], "Close")
    if not prev_close or close is None:
        return None
    return (float(close) / float(prev_close)) - 1.0


def _gap_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx <= 0:
        return None
    prev_close = framework.ohlcv_helper._value(rows[idx - 1], "Close")
    open_price = framework.ohlcv_helper._value(rows[idx], "Open")
    if not prev_close or open_price is None:
        return None
    return (float(open_price) / float(prev_close)) - 1.0


def _sector_maps(
    tickers: set[str],
) -> tuple[dict[str, str], dict[str, dict[str, Any]], dict[str, int], Counter[str]]:
    cache = load_cache()
    sector_by_ticker: dict[str, str] = {}
    lookup_by_ticker: dict[str, dict[str, Any]] = {}
    status_counts: Counter[str] = Counter()
    members: Counter[str] = Counter()
    for ticker in sorted(tickers):
        lookup = lookup_sector(ticker, cache)
        lookup_by_ticker[ticker] = lookup
        status_counts[str(lookup.get("status") or "missing")] += 1
        sector = lookup.get("sector")
        if sector:
            sector_by_ticker[ticker] = str(sector)
            members[str(sector)] += 1
    return sector_by_ticker, lookup_by_ticker, dict(members), status_counts


def _detect_positive_peer_shocks(
    snapshot: dict[str, list[dict[str, Any]]],
    eligible: set[str],
    sector_by_ticker: dict[str, str],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, set[str]], Counter[str]]:
    by_sector_date: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    own_shock_dates: dict[str, set[str]] = defaultdict(set)
    audit: Counter[str] = Counter()

    for ticker in sorted(eligible):
        sector = sector_by_ticker.get(ticker)
        if not sector:
            audit["missing_sector_for_shock_detection"] += 1
            continue
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        for idx in range(max(VOLUME_LOOKBACK_DAYS, 1), len(rows)):
            date = str(rows[idx].get("Date") or "")
            gap = _gap_return(rows, idx)
            day_ret = _day_return(rows, idx)
            volume_ratio = _volume_ratio(rows, idx, VOLUME_LOOKBACK_DAYS)
            if gap is None or day_ret is None or volume_ratio is None:
                audit["missing_shock_context"] += 1
                continue
            if gap < MIN_PEER_GAP:
                audit["peer_gap_below_threshold"] += 1
                continue
            if volume_ratio < MIN_PEER_VOLUME_RATIO:
                audit["peer_volume_ratio_below_threshold"] += 1
                continue
            if day_ret < MIN_PEER_DAY_RETURN:
                audit["peer_day_return_below_threshold"] += 1
                continue
            own_shock_dates[ticker].add(date)
            by_sector_date[sector][date].append(
                {
                    "ticker": ticker,
                    "date": date,
                    "gap_return": framework.base._round(gap, 6),
                    "day_return": framework.base._round(day_ret, 6),
                    "volume_ratio_20d": framework.base._round(volume_ratio, 6),
                }
            )
            audit["positive_peer_shocks"] += 1
    return by_sector_date, own_shock_dates, audit


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
    eligible = set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)
    sector_by_ticker, lookup_by_ticker, sector_member_counts, sector_status_counts = (
        _sector_maps(eligible)
    )
    peer_shocks, own_shock_dates, shock_audit = _detect_positive_peer_shocks(
        snapshot,
        eligible,
        sector_by_ticker,
    )

    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()

    for ticker in sorted(eligible):
        sector = sector_by_ticker.get(ticker)
        if not sector:
            audit["missing_sector"] += 1
            continue
        if sector_member_counts.get(sector, 0) < MIN_SECTOR_MEMBERS:
            audit["sector_too_small"] += 1
            continue
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        for date in dates:
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            min_idx = max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS, AVG_DOLLAR_VOLUME_DAYS)
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < RELATIVE_STRENGTH_DAYS:
                audit["insufficient_history"] += 1
                continue
            if date in own_shock_dates.get(ticker, set()):
                audit["candidate_had_same_day_own_shock"] += 1
                continue

            recent_own_shock = False
            peer_score = 0.0
            peer_count = 0
            peer_tickers: list[str] = []
            peer_event_rows: list[dict[str, Any]] = []
            for age in range(1, LOOKBACK_DAYS + 1):
                prior_idx = idx - age
                if prior_idx < 0:
                    break
                prior_date = str(rows[prior_idx].get("Date") or "")
                if prior_date in own_shock_dates.get(ticker, set()):
                    recent_own_shock = True
                    break
                weight = (LOOKBACK_DAYS - age + 1) / LOOKBACK_DAYS
                for event in peer_shocks.get(sector, {}).get(prior_date, []):
                    peer_ticker = str(event.get("ticker") or "")
                    if peer_ticker == ticker:
                        continue
                    event_return = float(event.get("day_return") or 0.0)
                    peer_score += event_return * weight
                    peer_count += 1
                    peer_tickers.append(peer_ticker)
                    if len(peer_event_rows) < 8:
                        peer_event_rows.append(
                            {
                                **event,
                                "lookback_age_trading_days": age,
                                "recency_weight": framework.base._round(weight, 6),
                            }
                        )
            if recent_own_shock:
                audit["candidate_had_recent_own_shock"] += 1
                continue
            if peer_count <= 0:
                audit["no_recent_positive_peer_shock"] += 1
                continue
            if peer_score < MIN_WEIGHTED_PEER_SHOCK_SCORE:
                audit["peer_shock_score_below_threshold"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if close is None or volume is None:
                audit["missing_close_or_volume"] += 1
                continue
            if float(close) < MIN_CLOSE_PRICE:
                audit["below_min_close_price"] += 1
                continue
            avg_dollar_volume = _avg_dollar_volume(rows, idx, AVG_DOLLAR_VOLUME_DAYS)
            if avg_dollar_volume is None:
                audit["missing_avg_dollar_volume"] += 1
                continue
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                audit["low_avg_dollar_volume"] += 1
                continue

            ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if ma50 is None:
                audit["missing_ma50"] += 1
                continue
            if float(close) <= float(ma50):
                audit["below_ma50"] += 1
                continue
            ret20 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
            spy_ret20 = framework._close_return(
                spy_rows,
                spy_idx - RELATIVE_STRENGTH_DAYS,
                spy_idx,
            )
            if ret20 is None or spy_ret20 is None:
                audit["missing_relative_strength"] += 1
                continue
            rs20_vs_spy = ret20 - spy_ret20
            if rs20_vs_spy <= MIN_RS_20D_VS_SPY:
                audit["rs20_not_positive_vs_spy"] += 1
                continue

            close_location = framework._close_location(rows[idx])
            ab_entries = entries_by_date.get(date, [])
            candidates.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "sector": sector,
                    "sector_lookup": lookup_by_ticker.get(ticker),
                    "sector_rule_version": SECTOR_RULE_VERSION,
                    "peer_shock_score": framework.base._round(peer_score, 6),
                    "peer_shock_count": peer_count,
                    "peer_shock_unique_tickers": sorted(set(peer_tickers)),
                    "peer_shock_events_sample": peer_event_rows,
                    "peer_shock_lookback_days": LOOKBACK_DAYS,
                    "peer_shock_thresholds": {
                        "min_peer_gap": MIN_PEER_GAP,
                        "min_peer_volume_ratio": MIN_PEER_VOLUME_RATIO,
                        "min_peer_day_return": MIN_PEER_DAY_RETURN,
                        "min_weighted_peer_shock_score": MIN_WEIGHTED_PEER_SHOCK_SCORE,
                    },
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "avg_dollar_volume_20d": framework.base._round(
                        avg_dollar_volume,
                        2,
                    ),
                    "ma50": framework.base._round(ma50, 4),
                    "signal_close_location": framework.base._round(close_location, 6),
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
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
            -float(row["peer_shock_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "sector_status_counts": dict(sorted(sector_status_counts.items())),
        "sector_member_counts": dict(sorted(sector_member_counts.items())),
        "positive_peer_shock_audit": dict(sorted(shock_audit.items())),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_same_sector_peer_shock_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Strong positive same-sector peer shocks from free OHLCV may "
                "identify liquid unshocked continuation candidates as a "
                "default-off paper candidate pool."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260530-001",
                "exp-20260530-012",
                "exp-20260531-010",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "new_production_visible_free_ohlcv_peer_relation_field",
            "prediction": {
                "success_probability": 0.30,
                "expected_ev_delta": 0.20,
                "expected_pnl_delta": 3000.0,
                "main_failure_modes": [
                    "window_regression",
                    "drawdown_drift_too_high",
                    "target_concentration_failed",
                    "peer_shock_sample_too_noisy",
                ],
                "confidence_reason": (
                    "Read-only exp-20260530-001 found a strong-positive sector "
                    "peer shock 10d excess-return lift, but subperiod stability "
                    "was imperfect and prior SEC peer-transfer candidates failed."
                ),
                "recorded_at": "2026-05-31T12:09:10+00:00",
            },
            "calibration": {
                "actual_decision": decision,
                "actual_success": actual_success,
                "predicted_success_probability": 0.30,
                "brier_score": framework.base._round((0.30 - actual_success) ** 2, 6),
                "expected_ev_delta": 0.20,
                "actual_ev_delta": payload["expected_value_score_delta"],
                "ev_prediction_error": framework.base._round(
                    payload["expected_value_score_delta"] - 0.20,
                    6,
                ),
                "expected_pnl_delta": 3000.0,
                "actual_pnl_delta": payload["total_pnl_delta"],
                "pnl_prediction_error": framework.base._round(
                    payload["total_pnl_delta"] - 3000.0,
                    2,
                ),
                "predicted_failure_modes": [
                    "window_regression",
                    "drawdown_drift_too_high",
                    "target_concentration_failed",
                    "peer_shock_sample_too_noisy",
                ],
                "realized_failure_mode": (
                    gate4["failed_reasons"][0]
                    if gate4.get("failed_reasons")
                    else None
                ),
                "predicted_failure_mode_hit": bool(
                    set(gate4.get("failed_reasons") or set()).intersection(
                        {
                            "window_ev_regression",
                            "window_pnl_regression",
                            "drawdown_drift_too_high",
                            "target_concentration_failed",
                            "target_sample_too_small",
                        }
                    )
                ),
            },
        }
    )
    payload["preflight_questions"] = {
        "1_alpha_hypothesis": (
            "Same-sector strong positive peer shocks may create delayed "
            "continuation in liquid unshocked peers; category: candidate-pool "
            "alpha_search. It follows the playbook's preference for free, "
            "production-visible data-edge fields and candidate-pool sleeves."
        ),
        "2_prior_experiments": {
            "exp-20260530-001": (
                "Read-only peer information-transfer attribution found a "
                "strong-positive sector peer shock 10d excess-return lift, but "
                "failed monotonicity and temporal-stability preregistration."
            ),
            "exp-20260530-012": (
                "SEC sector-event breadth peer transfer failed aggregate EV/PnL "
                "and concentration gates."
            ),
            "exp-20260531-010": (
                "SEC Item 2.02 characteristic-similarity peer transfer was "
                "positive but failed window/sample/concentration gates."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md late_strong, mid_weak, old_thin windows; "
            "positive aggregate EV/PnL, 3/3 EV-improved windows, no PnL "
            "regression, >=20 target trades across all 3 windows, drawdown drift "
            "<=0.5pp, survival >=5%, and concentration guardrails pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260531_012_same_sector_peer_shock_candidate_pool.py"
        ),
    }
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "sector",
            "sector_lookup",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "peer_shock_score",
            "peer_shock_count",
            "peer_shock_unique_tickers",
            "peer_shock_events_sample",
            "avg_dollar_volume_20d",
            "ma50",
            "rs20_vs_spy",
        ],
    )
    payload["gate2"]["note"] = (
        "The candidate source uses only signal-date-known OHLCV, prior peer "
        "shock rows, offline sector cache metadata, and SPY OHLCV. It does not "
        "ask the LLM or production to infer hidden fields."
    )
    payload["production_impact"] = {
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
            "A passing replay would still require a shared default-off paper "
            "adapter plus parity tests before production reports or any order "
            "path can use the field."
        ),
    }
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because replay-safe attribution remains "
        "sparse; skipped alpha_score component/threshold retunes because the "
        "latest runs failed drawdown and concentration; skipped FINRA/VBB/VCP/"
        "Companyfacts/state-surface scalar retunes because the playbook requires "
        "new forward rows or a materially different field."
    )
    payload["interpretation"] = (
        "The same-sector peer-shock source cleared the replay gate but still "
        "needs a shared default-off adapter before any production exposure."
        if gate4["passed"]
        else (
            "The same-sector peer-shock source did not clear Gate 4. Do not "
            "promote it or retry nearby peer-shock gap/volume/score thresholds "
            "on the same frozen windows without new forward rows or a stronger "
            "relation source."
        )
    )
    payload["rejection_reason"] = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    payload["next_evidence_needed"] = (
        "A valid retry needs forward replacement-value rows or a materially "
        "stronger peer relation source, such as true earnings-calendar peer "
        "events, customer/supplier links, or audited theme propagation."
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(CARD_MD),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
    ]
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
            "# exp-20260531-012 Same-Sector Peer-Shock Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: default-off paper candidates from liquid unshocked peers after strong positive same-sector OHLCV peer shocks.",
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
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity tests.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Same-sector peer-shock candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "json": framework.base._repo_rel(OUT_JSON),
        "card": framework.base._repo_rel(CARD_MD),
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "result_file": framework.base._repo_rel(OUT_JSON),
            "card_file": framework.base._repo_rel(CARD_MD),
            "artifact": framework.base._repo_rel(ARTIFACT_MD),
            "gate4_passed": payload["gate4"]["passed"],
            "delta_metrics": {
                "expected_value_score": payload["expected_value_score_delta"],
                "total_pnl": payload["total_pnl_delta"],
                "max_drawdown_pct": payload["delta_metrics"]["aggregate"][
                    "max_drawdown_delta_max"
                ],
            },
        },
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    report = _build_report(payload)
    framework.base._write_text(CARD_MD, report)
    framework.base._write_text(ARTIFACT_MD, report)
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


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
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
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
