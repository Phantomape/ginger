"""exp-20260530-012: SEC sector-event breadth peer transfer.

This alpha search tests one free-data candidate-pool source. When multiple
same-sector SEC issuers have positive PIT-safe filing reactions inside a recent
trading-day window, liquid same-sector leaders that were not event issuers may
be default-off paper candidates.

Core signals, ranking, sizing, exits, LLM/news, watchlists, and live/default
orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260529_010_peer_earnings_reaction_transfer as prior


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260530-012"
STEM = "sec_sector_event_breadth_peer_transfer"
TRIAL_FAMILY = "sec_sector_event_breadth_peer_transfer_candidate_pool"
CHANGED_VARIABLE = "sec_sector_positive_event_breadth_transfer_candidate_source_v1"
RULE_VERSION = "sec_sector_positive_event_breadth_peer_transfer_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_012_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SECTOR_EVENT_LOOKBACK_TRADING_DAYS = 5
MIN_POSITIVE_EVENT_ISSUERS = 2
MIN_PEER_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MIN_PEER_RS20_VS_SPY = 0.0
MIN_PEER_CLOSE_LOCATION = 0.55
MIN_PEER_SIGNAL_EXCESS_RETURN_1D_VS_SPY = -0.01

framework = prior.framework
_SEC_EVENTS_CACHE: list[dict[str, Any]] | None = None


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_AGG_JSON = OUT_JSON
    framework.AFTER_AGG_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.DOC_TICKET_JSON = TICKET_JSON
    framework.ARTIFACT_MD = CARD_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = 1
    framework.MIN_TARGET_TRADES = 20
    framework.MIN_TARGET_WINDOWS = 3
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _event_family_bucket(row: dict[str, Any]) -> str:
    form_base = str(row.get("form_base") or row.get("form_type") or "").upper()
    if form_base in {"10-K", "10-K/A"}:
        return "periodic_report_10k"
    if form_base in {"10-Q", "10-Q/A"}:
        return "periodic_report_10q"
    if form_base == "8-K":
        codes = {str(code) for code in row.get("eight_k_item_codes") or []}
        raw = str(row.get("items_raw") or "")
        if not codes and raw:
            codes = {item.strip() for item in raw.split(",") if item.strip()}
        if "2.02" in codes:
            return "earnings_8k"
        if "1.01" in codes:
            return "material_agreement_8k"
        if "5.02" in codes:
            return "leadership_8k"
        if "5.03" in codes:
            return "governance_8k"
        if "7.01" in codes:
            return "fd_8k"
        if "8.01" in codes:
            return "other_8k"
        return "other_8k"
    if form_base:
        return f"form_{form_base.lower().replace('-', '')}"
    return "unknown_sec_event"


def _load_sec_events() -> list[dict[str, Any]]:
    global _SEC_EVENTS_CACHE
    if _SEC_EVENTS_CACHE is not None:
        return _SEC_EVENTS_CACHE

    path = prior.SEC_EVENTS_FILE
    if not path.exists():
        raise FileNotFoundError(prior.framework.base._repo_rel(path))

    events: dict[tuple[str, str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            ticker = str(row.get("ticker") or "").upper().strip()
            usable_trade_date = str(row.get("usable_trade_date") or "").strip()[:10]
            accession = str(row.get("accession_number") or "").strip()
            if not ticker or not usable_trade_date or not accession:
                continue
            if not bool(row.get("pit_safe_flag")):
                continue
            form_base = str(row.get("form_base") or row.get("form_type") or "")
            if not form_base:
                continue
            events[(ticker, accession, usable_trade_date)] = {
                "ticker": ticker,
                "usable_trade_date": usable_trade_date,
                "accession_number": accession,
                "accepted_at": row.get("accepted_at"),
                "form_base": row.get("form_base"),
                "form_type": row.get("form_type"),
                "eight_k_item_codes": row.get("eight_k_item_codes") or [],
                "event_family_bucket": _event_family_bucket(row),
                "source_file": path.name,
            }

    _SEC_EVENTS_CACHE = sorted(
        events.values(),
        key=lambda row: (
            str(row["usable_trade_date"]),
            str(row["ticker"]),
            str(row["accession_number"]),
        ),
    )
    return _SEC_EVENTS_CACHE


def _sector_positive_reaction_events(
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    spy_rows: list[dict[str, Any]],
    spy_index: dict[str, int],
    audit: Counter[str],
) -> dict[str, list[dict[str, Any]]]:
    date_set = set(dates)
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_events = [
        event
        for event in _load_sec_events()
        if str(event.get("usable_trade_date")) in date_set
    ]
    audit["sec_events_in_window"] += len(raw_events)
    for event in raw_events:
        issuer = str(event["ticker"]).upper()
        sector = prior._sector_info(issuer).get("sector", "")
        if not prior._valid_sector(sector):
            audit["event_missing_sector"] += 1
            continue
        if issuer not in snapshot:
            audit["event_issuer_missing_ohlcv"] += 1
            continue
        reaction = prior._event_reaction(snapshot, event, spy_rows, spy_index)
        if reaction is None:
            audit["event_reaction_not_positive_enough"] += 1
            continue
        reaction["sector"] = sector
        reaction["industry"] = prior._sector_info(issuer).get("industry", "")
        reaction["event_family_bucket"] = event["event_family_bucket"]
        out[str(reaction["date"])].append(reaction)
    return out


def _recent_sector_cluster(
    dates: list[str],
    date_index: int,
    sector: str,
    positive_events_by_date: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    start = max(0, date_index - SECTOR_EVENT_LOOKBACK_TRADING_DAYS + 1)
    recent_dates = dates[start : date_index + 1]
    return [
        event
        for date in recent_dates
        for event in positive_events_by_date.get(date, [])
        if str(event.get("sector")) == sector
    ]


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
    audit: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []

    peer_universe = sorted(
        set(universe).intersection(snapshot).difference(framework.EXCLUDED_TICKERS)
    )
    peers_by_sector: dict[str, list[str]] = defaultdict(list)
    for ticker in peer_universe:
        sector = prior._sector_info(ticker).get("sector", "")
        if prior._valid_sector(sector):
            peers_by_sector[sector].append(ticker)
        else:
            audit["peer_missing_sector"] += 1

    positive_events_by_date = _sector_positive_reaction_events(
        snapshot, dates, spy_rows, spy_index, audit
    )
    sectors = sorted(peers_by_sector)
    min_idx = max(
        prior.MOVING_AVERAGE_DAYS,
        prior.RELATIVE_STRENGTH_DAYS,
        prior.AVG_DOLLAR_VOLUME_DAYS,
    )

    for date_index, date in enumerate(dates):
        for sector in sectors:
            cluster = _recent_sector_cluster(
                dates, date_index, sector, positive_events_by_date
            )
            event_tickers = sorted({str(event["ticker"]).upper() for event in cluster})
            if len(event_tickers) < MIN_POSITIVE_EVENT_ISSUERS:
                audit["sector_cluster_too_thin"] += 1
                continue

            cluster_excess_values = [
                float(event["issuer_excess_return_1d_vs_spy"]) for event in cluster
            ]
            cluster_avg_excess = sum(cluster_excess_values) / len(cluster_excess_values)
            cluster_max_excess = max(cluster_excess_values)
            event_family_counts = Counter(str(event["event_family_bucket"]) for event in cluster)

            for ticker in peers_by_sector.get(sector, []):
                if ticker in event_tickers:
                    audit["peer_is_recent_event_issuer"] += 1
                    continue
                rows = framework.ohlcv_helper._series(snapshot, ticker)
                idx_by_date = framework.ohlcv_helper._row_index(rows)
                idx = idx_by_date.get(date)
                spy_idx = spy_index.get(date)
                if idx is None or spy_idx is None or idx < min_idx or spy_idx < min_idx:
                    audit["peer_insufficient_history"] += 1
                    continue

                close = framework.ohlcv_helper._value(rows[idx], "Close")
                volume = framework.ohlcv_helper._value(rows[idx], "Volume")
                if close is None or volume is None:
                    audit["peer_missing_close_or_volume"] += 1
                    continue

                avg_dollar_volume = prior._avg_dollar_volume(
                    rows, idx, prior.AVG_DOLLAR_VOLUME_DAYS
                )
                if (
                    avg_dollar_volume is None
                    or avg_dollar_volume < MIN_PEER_AVG_DOLLAR_VOLUME_20D
                ):
                    audit["peer_low_avg_dollar_volume"] += 1
                    continue

                ma50 = framework._prior_average(
                    rows, idx, prior.MOVING_AVERAGE_DAYS, "Close"
                )
                if ma50 is None or float(close) <= float(ma50):
                    audit["peer_below_ma50"] += 1
                    continue

                peer_return_1d = prior._daily_return(rows, idx)
                spy_return_1d = prior._daily_return(spy_rows, spy_idx)
                if peer_return_1d is None or spy_return_1d is None:
                    audit["peer_missing_signal_return"] += 1
                    continue
                peer_signal_excess = peer_return_1d - spy_return_1d
                if peer_signal_excess < MIN_PEER_SIGNAL_EXCESS_RETURN_1D_VS_SPY:
                    audit["peer_signal_day_too_weak"] += 1
                    continue

                peer_close_location = framework._close_location(rows[idx])
                if (
                    peer_close_location is None
                    or peer_close_location < MIN_PEER_CLOSE_LOCATION
                ):
                    audit["peer_weak_close_location"] += 1
                    continue

                ret20 = framework._close_return(
                    rows, idx - prior.RELATIVE_STRENGTH_DAYS, idx
                )
                spy_ret20 = framework._close_return(
                    spy_rows, spy_idx - prior.RELATIVE_STRENGTH_DAYS, spy_idx
                )
                if ret20 is None or spy_ret20 is None:
                    audit["peer_missing_relative_strength"] += 1
                    continue
                rs20_vs_spy = ret20 - spy_ret20
                if rs20_vs_spy < MIN_PEER_RS20_VS_SPY:
                    audit["peer_rs20_not_positive_vs_spy"] += 1
                    continue

                ab_entries = entries_by_date.get(date, [])
                score = (
                    (0.75 * len(event_tickers))
                    + (2.0 * cluster_avg_excess)
                    + cluster_max_excess
                    + (1.50 * float(rs20_vs_spy))
                    + float(peer_signal_excess)
                    + (0.25 * float(peer_close_location))
                    + min(float(avg_dollar_volume) / 1_000_000_000.0, 0.25)
                )
                candidates.append(
                    {
                        "ticker": ticker,
                        "date": date,
                        "strategy": STEM,
                        "rule_version": RULE_VERSION,
                        "event_source": "sec_sector_positive_event_breadth",
                        "sector_event_breadth_count": len(event_tickers),
                        "sector_event_count": len(cluster),
                        "sector_event_lookback_trading_days": (
                            SECTOR_EVENT_LOOKBACK_TRADING_DAYS
                        ),
                        "sector_event_tickers": event_tickers,
                        "sector_event_family_counts": dict(sorted(event_family_counts.items())),
                        "sector_event_avg_excess_return_1d_vs_spy": framework.base._round(
                            cluster_avg_excess, 6
                        ),
                        "sector_event_max_excess_return_1d_vs_spy": framework.base._round(
                            cluster_max_excess, 6
                        ),
                        "event_sector": sector,
                        "peer_sector": sector,
                        "peer_industry": prior._sector_info(ticker).get("industry"),
                        "peer_relation_source": (
                            "same_sector_recent_positive_sec_event_breadth"
                        ),
                        "close": framework.base._round(close, 4),
                        "volume": framework.base._round(volume, 2),
                        "ma50": framework.base._round(ma50, 4),
                        "avg_dollar_volume_20d": framework.base._round(
                            avg_dollar_volume, 2
                        ),
                        "peer_return_1d": framework.base._round(peer_return_1d, 6),
                        "peer_signal_excess_return_1d_vs_spy": framework.base._round(
                            peer_signal_excess, 6
                        ),
                        "peer_close_location": framework.base._round(
                            peer_close_location, 6
                        ),
                        "ret20": framework.base._round(ret20, 6),
                        "spy_ret20": framework.base._round(spy_ret20, 6),
                        "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                        "peer_transfer_score": framework.base._round(score, 6),
                        "same_day_ab_entry_count": len(ab_entries),
                        "same_day_ab_overlap": bool(ab_entries),
                        "same_ticker_ab_overlap": any(
                            trade.get("ticker") == ticker for trade in ab_entries
                        ),
                        "known_at": (
                            "after_recent_sec_event_usable_trade_date_closes_"
                            "before_next_open_paper_entry"
                        ),
                        "trade_enabled": False,
                        "alters_orders": False,
                    }
                )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["peer_transfer_score"]),
            -int(row["sector_event_breadth_count"]),
            -float(row["sector_event_avg_excess_return_1d_vs_spy"]),
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
        "positive_event_dates": len(positive_events_by_date),
        "positive_event_count": sum(len(rows) for rows in positive_events_by_date.values()),
        "peer_sector_count": len(peers_by_sector),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "relation_field": "same-sector recent positive SEC event breadth",
        "min_positive_event_issuers": MIN_POSITIVE_EVENT_ISSUERS,
        "sector_event_lookback_trading_days": SECTOR_EVENT_LOOKBACK_TRADING_DAYS,
        "sec_events_source": framework.base._repo_rel(prior.SEC_EVENTS_FILE),
        "sector_map_source": framework.base._repo_rel(prior.SECTOR_MAP_JSON),
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_sec_sector_event_breadth_peer_transfer"
        if gate4["passed"]
        else "rejected_sec_sector_event_breadth_peer_transfer"
    )
    actual_success = 1 if gate4["passed"] else 0
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
                "Positive SEC issuer reactions may propagate at the sector-event "
                "breadth level to liquid same-sector leaders, creating a free-data "
                "default-off candidate source."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260529-010",
                "exp-20260529-011",
                "exp-20260530-023",
                "exp-20260530-006",
                "exp-20260530-008",
                "exp-20260530-009",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "free_sec_event_sector_propagation_field",
            "prediction": {
                "success_probability": 0.27,
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
                "main_failure_modes": [
                    "sample_too_thin",
                    "late_strong_regression",
                    "sector_concentration",
                    "event_breadth_no_transfer",
                ],
                "confidence_reason": (
                    "Playbook asks for event graph sector/theme propagation beyond "
                    "raw same-ticker recurrence; prior peer-transfer variants were "
                    "rejected, so probability is modest."
                ),
                "recorded_at": "2026-05-30T07:06:52+00:00",
                "brier_score": round((0.27 - actual_success) ** 2, 6),
            },
            "calibration": {
                "actual_decision": decision,
                "actual_success": actual_success,
                "predicted_success_probability": 0.27,
                "brier_score": round((0.27 - actual_success) ** 2, 6),
                "predicted_failure_modes": [
                    "sample_too_thin",
                    "late_strong_regression",
                    "sector_concentration",
                    "event_breadth_no_transfer",
                ],
                "realized_failure_mode": ";".join(gate4["failed_reasons"])
                if gate4["failed_reasons"]
                else None,
                "predicted_failure_mode_hit": any(
                    reason in gate4["failed_reasons"]
                    for reason in (
                        "target_sample_too_small",
                        "window_ev_regression",
                        "window_pnl_regression",
                        "target_concentration_failed",
                    )
                ),
            },
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": framework.MAX_PAPER_TRADES_PER_DAY,
                "sector_event_lookback_trading_days": SECTOR_EVENT_LOOKBACK_TRADING_DAYS,
                "min_positive_event_issuers": MIN_POSITIVE_EVENT_ISSUERS,
                "issuer_reaction_lookback_days": prior.ISSUER_REACTION_LOOKBACK_DAYS,
                "min_issuer_return_1d": prior.MIN_ISSUER_RETURN_1D,
                "min_issuer_excess_return_1d_vs_spy": (
                    prior.MIN_ISSUER_EXCESS_RETURN_1D_VS_SPY
                ),
                "min_issuer_close_location": prior.MIN_ISSUER_CLOSE_LOCATION,
                "relative_strength_days": prior.RELATIVE_STRENGTH_DAYS,
                "moving_average_days": prior.MOVING_AVERAGE_DAYS,
                "avg_dollar_volume_days": prior.AVG_DOLLAR_VOLUME_DAYS,
                "min_peer_signal_excess_return_1d_vs_spy": (
                    MIN_PEER_SIGNAL_EXCESS_RETURN_1D_VS_SPY
                ),
                "min_peer_rs20_vs_spy": MIN_PEER_RS20_VS_SPY,
                "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
                "min_peer_avg_dollar_volume_20d": MIN_PEER_AVG_DOLLAR_VOLUME_20D,
                "source_definition": [
                    "SEC event row must be PIT safe with usable_trade_date",
                    "issuer positive reaction uses same signal-date OHLCV thresholds as prior SEC peer-transfer scouts",
                    "same sector must have at least two distinct positive-reaction event issuers in the last five trading days",
                    "candidate must be a non-event same-sector peer",
                    "candidate must be above prior 50-day moving average",
                    "candidate must have nonnegative 20-day relative strength versus SPY",
                    "candidate must have 20-day average dollar volume >= 40 million",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "peer_transfer_score desc",
                    "sector_event_breadth_count desc",
                    "sector_event_avg_excess_return_1d_vs_spy desc",
                    "rs20_vs_spy desc",
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
                    "candidate_pool / entry: multiple positive SEC issuer "
                    "reactions in a sector may reveal sector/theme propagation "
                    "before liquid same-sector leaders move."
                ),
                "2_history_check": {
                    "exp-20260529-010": (
                        "Single-issuer same-sector peer transfer failed late_strong."
                    ),
                    "exp-20260529-011": (
                        "Single-issuer same-sector return-comovement peer transfer "
                        "failed late_strong and robustness."
                    ),
                    "exp-20260530-023": (
                        "Exact-industry Item 2.02 transfer was too weak/thin. This "
                        "run uses sector-level multi-issuer event breadth across "
                        "SEC event families, not a single-issuer relation."
                    ),
                    "exp-20260530-006_to_009": (
                        "Raw same-ticker SEC recurrence fields were rejected. This "
                        "run tests cross-ticker sector propagation instead."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three fixed windows; positive "
                    "aggregate EV/PnL; 3/3 EV-improved windows; no PnL-regressed "
                    "window; >=20 paper trades across all 3 windows; drawdown "
                    "drift <=0.5pp; survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260530_012_sec_sector_event_breadth_peer_transfer.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe attribution remains "
                "sparse; skipped VCP/VBB/Companyfacts/FINRA/state-surface retunes "
                "because the playbook asks for forward rows or materially new "
                "fields. This is one new SEC sector-propagation candidate source."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production path changed. Acceptance would still require a "
                    "shared default-off SEC sector-event paper adapter exposing the "
                    "same PIT event-breadth field in production before retention."
                ),
            },
            "interpretation": (
                "The SEC sector-event breadth transfer source cleared Gate 4 as a "
                "default-off replay lead; live/default orders remain disabled."
                if gate4["passed"]
                else (
                    "The SEC sector-event breadth transfer source did not clear "
                    "Gate 4. Do not promote it or retry nearby sector-breadth SEC "
                    "event thresholds on these frozen windows without forward rows "
                    "or a stronger relation source such as customer/supplier links "
                    "or audited theme propagation."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(
                gate4["failed_reasons"]
            ),
            "next_evidence_needed": (
                "Forward rows or a materially stronger cross-ticker relation source "
                "such as customer/supplier links, audited theme propagation, or "
                "multi-season event co-movement."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "SEC event metadata uses PIT usable_trade_date. Sector positive-reaction "
        "breadth and peer OHLCV are observed through signal-date close; paper "
        "entry is next open and exit is ten trading days after signal."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "sec_events": {
            "source": framework.base._repo_rel(prior.SEC_EVENTS_FILE),
            "required_fields": [
                "ticker",
                "usable_trade_date",
                "accession_number",
                "form_base/form_type",
                "pit_safe_flag",
            ],
            "events_loaded": len(_load_sec_events()),
        },
        "peer_relation": {
            "source": framework.base._repo_rel(prior.SECTOR_MAP_JSON),
            "required_fields": [
                "issuer sector",
                "peer sector",
                "issuer OHLCV Date/Open/High/Low/Close/Volume",
                "peer OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV rows",
            ],
            "relation": "same-sector recent positive SEC event breadth",
        },
    }
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
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
            "sector_event_breadth_count",
            "sector_event_tickers",
            "sector_event_family_counts",
            "peer_relation_source",
            "peer_transfer_score",
            "rs20_vs_spy",
            "avg_dollar_volume_20d",
        ],
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
    return "\n".join(
        [
            "# exp-20260530-012 SEC Sector-Event Breadth Peer Transfer",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits non-event same-sector leaders when at least two same-sector SEC issuers had positive filing reactions in the recent five-trading-day window.",
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
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "updated_at": payload["timestamp"],
        "result_files": [
            framework.base._repo_rel(OUT_JSON),
            framework.base._repo_rel(LOG_JSON),
            framework.base._repo_rel(CARD_MD),
        ],
        "anti_js": payload["anti_js"],
    }
    framework.base._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        **(json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}),
        "status": payload["status"],
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "artifact_file": framework.base._repo_rel(OUT_JSON),
        "result_file": framework.base._repo_rel(LOG_JSON),
        "report_file": framework.base._repo_rel(CARD_MD),
        "result": {
            "decision": payload["decision"],
            "json": framework.base._repo_rel(OUT_JSON),
            "log": framework.base._repo_rel(LOG_JSON),
            "card": framework.base._repo_rel(CARD_MD),
            "aggregate": payload["delta_metrics"]["aggregate"],
            "gate4": payload["gate4"],
            "summary": payload["interpretation"],
        },
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_text(CARD_MD, _build_report(payload))
    _write_manifest(payload)
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
                    "artifact": framework.base._repo_rel(CARD_MD),
                    "json": framework.base._repo_rel(OUT_JSON),
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
