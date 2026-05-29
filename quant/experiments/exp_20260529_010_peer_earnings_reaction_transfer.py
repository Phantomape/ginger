"""exp-20260529-010: peer earnings-reaction transfer paper sleeve.

This alpha search tests one stock-only candidate-pool source using free SEC
filing metadata plus OHLCV: after an 8-K Item 2.02 issuer posts a strong
same-day excess reaction, same-sector liquid peers with positive relative
strength become default-off paper candidates for next-open entry.

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


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260529-010"
STEM = "peer_earnings_reaction_transfer"
TRIAL_FAMILY = "peer_earnings_reaction_transfer_candidate_pool"
CHANGED_VARIABLE = "peer_earnings_reaction_transfer_candidate_source_v1"
RULE_VERSION = "sec_8k_202_positive_peer_transfer_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260529_010_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEC_EVENTS_FILE = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_filing_events_20241002_20260421.jsonl"
)
SECTOR_MAP_JSON = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"

EVENT_ITEM_CODE = "2.02"
ISSUER_REACTION_LOOKBACK_DAYS = 1
RELATIVE_STRENGTH_DAYS = 20
MOVING_AVERAGE_DAYS = 50
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_ISSUER_RETURN_1D = 0.02
MIN_ISSUER_EXCESS_RETURN_1D_VS_SPY = 0.015
MIN_ISSUER_CLOSE_LOCATION = 0.55
MIN_PEER_SIGNAL_EXCESS_RETURN_1D_VS_SPY = -0.01
MIN_PEER_RS20_VS_SPY = 0.0
MIN_PEER_CLOSE_LOCATION = 0.55
MIN_PEER_AVG_DOLLAR_VOLUME_20D = 40_000_000.0

EXCLUDED_SECTORS = {"", "ETF", "Commodities", "Unknown", "unknown"}
_SEC_EARNINGS_EVENTS_CACHE: list[dict[str, Any]] | None = None
_SECTOR_MAP_CACHE: dict[str, dict[str, str]] | None = None


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
    framework.DOC_TICKET_JSON = DOC_TICKET_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = 1
    framework.MIN_TARGET_TRADES = 20
    framework.MIN_TARGET_WINDOWS = 3
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _load_sector_map() -> dict[str, dict[str, str]]:
    global _SECTOR_MAP_CACHE
    if _SECTOR_MAP_CACHE is not None:
        return _SECTOR_MAP_CACHE

    out: dict[str, dict[str, str]] = {}
    if SECTOR_MAP_JSON.exists():
        payload = json.loads(SECTOR_MAP_JSON.read_text(encoding="utf-8"))
        entries = payload.get("entries") or {}
        for ticker, row in entries.items():
            sector = str(row.get("sector") or "").strip()
            industry = str(row.get("industry") or "").strip()
            if sector:
                out[str(ticker).upper()] = {"sector": sector, "industry": industry}

    helper_map = getattr(framework.ohlcv_helper, "SECTOR_MAP", {}) or {}
    for ticker, sector in helper_map.items():
        out.setdefault(
            str(ticker).upper(),
            {"sector": str(sector or "").strip(), "industry": ""},
        )

    _SECTOR_MAP_CACHE = out
    return out


def _sector_info(ticker: str) -> dict[str, str]:
    return _load_sector_map().get(str(ticker).upper(), {"sector": "", "industry": ""})


def _valid_sector(sector: str) -> bool:
    return bool(sector) and sector not in EXCLUDED_SECTORS


def _contains_item_202(row: dict[str, Any]) -> bool:
    codes = row.get("eight_k_item_codes")
    if isinstance(codes, list):
        return any(str(code).strip() == EVENT_ITEM_CODE for code in codes)
    if codes is None:
        return False
    return EVENT_ITEM_CODE in str(codes)


def _load_sec_earnings_events() -> list[dict[str, Any]]:
    global _SEC_EARNINGS_EVENTS_CACHE
    if _SEC_EARNINGS_EVENTS_CACHE is not None:
        return _SEC_EARNINGS_EVENTS_CACHE

    candidates = [SEC_EVENTS_FILE] if SEC_EVENTS_FILE.exists() else []
    if not candidates:
        candidates = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_events_*.jsonl"))

    events: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in candidates:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ticker = str(row.get("ticker") or "").upper().strip()
                usable_trade_date = str(row.get("usable_trade_date") or "").strip()
                accession = str(row.get("accession_number") or "").strip()
                if not ticker or not usable_trade_date or not accession:
                    continue
                if not bool(row.get("pit_safe_flag")):
                    continue
                form_base = str(row.get("form_base") or row.get("form_type") or "")
                if not form_base.startswith("8-K"):
                    continue
                if not _contains_item_202(row):
                    continue
                events[(ticker, accession, usable_trade_date)] = {
                    "ticker": ticker,
                    "usable_trade_date": usable_trade_date,
                    "accession_number": accession,
                    "accepted_at": row.get("accepted_at"),
                    "source_file": path.name,
                }

    _SEC_EARNINGS_EVENTS_CACHE = sorted(
        events.values(),
        key=lambda row: (
            str(row["usable_trade_date"]),
            str(row["ticker"]),
            str(row["accession_number"]),
        ),
    )
    return _SEC_EARNINGS_EVENTS_CACHE


def _avg_dollar_volume(
    rows: list[dict[str, Any]], idx: int, days: int
) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if values else None


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < ISSUER_REACTION_LOOKBACK_DAYS:
        return None
    prior_close = framework.ohlcv_helper._value(
        rows[idx - ISSUER_REACTION_LOOKBACK_DAYS], "Close"
    )
    close = framework.ohlcv_helper._value(rows[idx], "Close")
    if not prior_close or close is None:
        return None
    return (float(close) / float(prior_close)) - 1.0


def _event_reaction(
    snapshot: dict[str, list[dict[str, Any]]],
    event: dict[str, Any],
    spy_rows: list[dict[str, Any]],
    spy_index: dict[str, int],
) -> dict[str, Any] | None:
    ticker = str(event["ticker"]).upper()
    rows = framework.ohlcv_helper._series(snapshot, ticker)
    if not rows:
        return None
    idx_by_date = framework.ohlcv_helper._row_index(rows)
    date = str(event["usable_trade_date"])
    idx = idx_by_date.get(date)
    spy_idx = spy_index.get(date)
    if idx is None or spy_idx is None or idx < 1 or spy_idx < 1:
        return None

    issuer_return = _daily_return(rows, idx)
    spy_return = _daily_return(spy_rows, spy_idx)
    issuer_close_location = framework._close_location(rows[idx])
    if issuer_return is None or spy_return is None or issuer_close_location is None:
        return None
    issuer_excess = issuer_return - spy_return
    if issuer_return < MIN_ISSUER_RETURN_1D:
        return None
    if issuer_excess < MIN_ISSUER_EXCESS_RETURN_1D_VS_SPY:
        return None
    if issuer_close_location < MIN_ISSUER_CLOSE_LOCATION:
        return None

    return {
        "ticker": ticker,
        "date": date,
        "issuer_return_1d": issuer_return,
        "spy_return_1d": spy_return,
        "issuer_excess_return_1d_vs_spy": issuer_excess,
        "issuer_close_location": issuer_close_location,
        "accession_number": event["accession_number"],
        "accepted_at": event.get("accepted_at"),
        "source_file": event.get("source_file"),
    }


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
    date_set = set(dates)
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()

    peer_universe = sorted(set(universe).intersection(snapshot).difference(framework.EXCLUDED_TICKERS))
    peers_by_sector: dict[str, list[str]] = defaultdict(list)
    missing_peer_sector = 0
    for ticker in peer_universe:
        sector = _sector_info(ticker).get("sector", "")
        if not _valid_sector(sector):
            missing_peer_sector += 1
            continue
        peers_by_sector[sector].append(ticker)

    raw_events = [
        event
        for event in _load_sec_earnings_events()
        if str(event.get("usable_trade_date")) in date_set
    ]
    reaction_events: list[dict[str, Any]] = []
    for event in raw_events:
        issuer = str(event["ticker"]).upper()
        issuer_sector = _sector_info(issuer).get("sector", "")
        if not _valid_sector(issuer_sector):
            audit["event_missing_sector"] += 1
            continue
        if issuer not in snapshot:
            audit["event_issuer_missing_ohlcv"] += 1
            continue
        reaction = _event_reaction(snapshot, event, spy_rows, spy_index)
        if reaction is None:
            audit["event_reaction_not_positive_enough"] += 1
            continue
        reaction["sector"] = issuer_sector
        reaction["industry"] = _sector_info(issuer).get("industry", "")
        reaction_events.append(reaction)

    min_idx = max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS, AVG_DOLLAR_VOLUME_DAYS)
    for event in reaction_events:
        date = str(event["date"])
        issuer = str(event["ticker"]).upper()
        sector = str(event["sector"])
        same_sector_peers = peers_by_sector.get(sector, [])
        if not same_sector_peers:
            audit["no_same_sector_peers"] += 1
            continue

        for ticker in same_sector_peers:
            if ticker == issuer:
                audit["peer_is_issuer"] += 1
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

            avg_dollar_volume = _avg_dollar_volume(rows, idx, AVG_DOLLAR_VOLUME_DAYS)
            if avg_dollar_volume is None or avg_dollar_volume < MIN_PEER_AVG_DOLLAR_VOLUME_20D:
                audit["peer_low_avg_dollar_volume"] += 1
                continue

            ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if ma50 is None or float(close) <= float(ma50):
                audit["peer_below_ma50"] += 1
                continue

            peer_return_1d = _daily_return(rows, idx)
            spy_return_1d = _daily_return(spy_rows, spy_idx)
            if peer_return_1d is None or spy_return_1d is None:
                audit["peer_missing_signal_return"] += 1
                continue
            peer_signal_excess = peer_return_1d - spy_return_1d
            if peer_signal_excess < MIN_PEER_SIGNAL_EXCESS_RETURN_1D_VS_SPY:
                audit["peer_signal_day_too_weak"] += 1
                continue

            peer_close_location = framework._close_location(rows[idx])
            if peer_close_location is None or peer_close_location < MIN_PEER_CLOSE_LOCATION:
                audit["peer_weak_close_location"] += 1
                continue

            ret20 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
            spy_ret20 = framework._close_return(spy_rows, spy_idx - RELATIVE_STRENGTH_DAYS, spy_idx)
            if ret20 is None or spy_ret20 is None:
                audit["peer_missing_relative_strength"] += 1
                continue
            rs20_vs_spy = ret20 - spy_ret20
            if rs20_vs_spy < MIN_PEER_RS20_VS_SPY:
                audit["peer_rs20_not_positive_vs_spy"] += 1
                continue

            ab_entries = entries_by_date.get(date, [])
            score = (
                (2.0 * float(event["issuer_excess_return_1d_vs_spy"]))
                + (1.5 * float(rs20_vs_spy))
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
                    "event_source": "sec_8k_item_2_02",
                    "event_ticker": issuer,
                    "event_accession_number": event["accession_number"],
                    "event_accepted_at": event.get("accepted_at"),
                    "event_usable_trade_date": date,
                    "event_sector": sector,
                    "event_industry": event.get("industry"),
                    "event_source_file": event.get("source_file"),
                    "event_issuer_return_1d": framework.base._round(
                        event["issuer_return_1d"], 6
                    ),
                    "event_issuer_excess_return_1d_vs_spy": framework.base._round(
                        event["issuer_excess_return_1d_vs_spy"], 6
                    ),
                    "event_issuer_close_location": framework.base._round(
                        event["issuer_close_location"], 6
                    ),
                    "peer_sector": sector,
                    "peer_industry": _sector_info(ticker).get("industry"),
                    "peer_relation_source": "same_sector_static_reference_map",
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "ma50": framework.base._round(ma50, 4),
                    "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                    "peer_return_1d": framework.base._round(peer_return_1d, 6),
                    "peer_signal_excess_return_1d_vs_spy": framework.base._round(
                        peer_signal_excess, 6
                    ),
                    "peer_close_location": framework.base._round(peer_close_location, 6),
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                    "peer_transfer_score": framework.base._round(score, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "known_at": "after_sec_event_usable_trade_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["peer_transfer_score"]),
            -float(row["event_issuer_excess_return_1d_vs_spy"]),
            -float(row["rs20_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            str(row["event_ticker"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "sec_8k_item_202_events_in_window": len(raw_events),
        "positive_reaction_events": len(reaction_events),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "unique_event_tickers": len({row["event_ticker"] for row in candidates}),
        "peer_sector_count": len(peers_by_sector),
        "missing_peer_sector_count": missing_peer_sector,
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "sec_events_source": framework.base._repo_rel(SEC_EVENTS_FILE),
        "sector_map_source": framework.base._repo_rel(SECTOR_MAP_JSON),
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_peer_earnings_reaction_transfer"
        if gate4["passed"]
        else "rejected_peer_earnings_reaction_transfer"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.34,
        "expected_ev_delta": 0.18,
        "expected_pnl_delta": 3500.0,
        "main_failure_modes": [
            "peer_effect_decays_by_next_open",
            "sector_map_not_discriminating_enough",
            "sample_too_thin_after_strong_event_filter",
            "concentration",
        ],
        "confidence_reason": (
            "The playbook favors production-visible default-off candidate-pool "
            "alpha and explicitly lists peer earnings transfer as a valid new "
            "field. SEC Item 2.02 metadata is free and replayable, but same-sector "
            "classification is a static reference proxy until promoted."
        ),
        "recorded_at": "2026-05-29T07:40:00+00:00",
        "brier_score": round((0.34 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "A strong positive SEC 8-K Item 2.02 issuer reaction may transfer "
                "to liquid same-sector peers that already have positive trend and "
                "relative strength, creating a free-data candidate-pool source."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": "sec_8k_item_202_positive_peer_transfer_v1",
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260528-028",
                "exp-20260528-036",
                "exp-20260529-001",
                "exp-20260529-005",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "free_sec_8k_item_202_event_metadata_plus_same_sector_peer_transfer"
            ),
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": framework.MAX_PAPER_TRADES_PER_DAY,
                "sec_item_code": EVENT_ITEM_CODE,
                "issuer_reaction_lookback_days": ISSUER_REACTION_LOOKBACK_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_issuer_return_1d": MIN_ISSUER_RETURN_1D,
                "min_issuer_excess_return_1d_vs_spy": MIN_ISSUER_EXCESS_RETURN_1D_VS_SPY,
                "min_issuer_close_location": MIN_ISSUER_CLOSE_LOCATION,
                "min_peer_signal_excess_return_1d_vs_spy": (
                    MIN_PEER_SIGNAL_EXCESS_RETURN_1D_VS_SPY
                ),
                "min_peer_rs20_vs_spy": MIN_PEER_RS20_VS_SPY,
                "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
                "min_peer_avg_dollar_volume_20d": MIN_PEER_AVG_DOLLAR_VOLUME_20D,
                "source_definition": [
                    "SEC filing event has form_base/form_type 8-K and Item 2.02",
                    "event row must have pit_safe_flag true and usable_trade_date",
                    "issuer reaction is measured at usable_trade_date close versus prior close and SPY",
                    "same-sector peers are production universe tickers with OHLCV history",
                    "peer must be above prior 50-day moving average",
                    "peer must have positive 20-day relative strength versus SPY",
                    "peer must have 20-day average dollar volume >= 40 million",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "peer_transfer_score desc",
                    "event_issuer_excess_return_1d_vs_spy desc",
                    "rs20_vs_spy desc",
                    "avg_dollar_volume_20d desc",
                    "event_ticker asc",
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
                    "candidate_pool / entry: strong positive SEC 8-K Item 2.02 "
                    "issuer reactions may spill over to liquid same-sector peers "
                    "that already have trend and relative strength."
                ),
                "2_history_check": {
                    "exp-20260528-028": (
                        "PEAD window testing was rejected; this run uses peer "
                        "transfer from same-day SEC Item 2.02 issuer reaction, "
                        "not a 5-day/10-day PEAD hold retune."
                    ),
                    "exp-20260528-036": (
                        "Sector/market breadth agreement was rejected. This run "
                        "uses an issuer-specific SEC event as the causal context, "
                        "not broad sector breadth."
                    ),
                    "exp-20260529-001_and_005": (
                        "VWAP reclaim and long-base/breadth candidate pools were "
                        "rejected. This run adds a non-OHLCV filing-event field "
                        "instead of retuning pattern-name OHLCV pools."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
                    "trades across all 3 windows; drawdown drift <=0.5pp; survival "
                    ">=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260529_010_peer_earnings_reaction_transfer.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay coverage remains sparse; "
                "skipped Companyfacts/VBB/VCP/state-surface scalar retunes because "
                "the playbook calls for forward rows or new fields. Peer earnings "
                "transfer is an explicit free-data edge candidate and changes one "
                "candidate-source variable only."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. If this were accepted, "
                    "promotion would require a shared SEC-event adapter, a shared "
                    "sector-map source, and replay/live parity tests before any "
                    "order-affecting use."
                ),
            },
            "interpretation": (
                "The peer earnings-reaction transfer sleeve cleared Gate 4 as a "
                "default-off replay lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The peer earnings-reaction transfer sleeve did not clear Gate 4. "
                    "Do not promote it or retry nearby same-sector SEC-event thresholds "
                    "on the same frozen windows without forward rows or a stronger "
                    "peer-relation field such as industry/supply-chain similarity."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, use forward rows or a materially sharper free peer "
                "relation such as industry-level similarity, customer/supplier links, "
                "or observed historical earnings-reaction co-movement."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "SEC Item 2.02 event metadata uses pit_safe usable_trade_date. Issuer and "
        "peer OHLCV are observed through the signal-date close; paper entry is "
        "the next available open with production entry slippage; exit is ten "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "sec_events": {
            "source": framework.base._repo_rel(SEC_EVENTS_FILE),
            "required_fields": [
                "ticker",
                "usable_trade_date",
                "accession_number",
                "form_base/form_type",
                "eight_k_item_codes",
                "pit_safe_flag",
            ],
            "events_loaded": len(_load_sec_earnings_events()),
        },
        "sector_map": {
            "source": framework.base._repo_rel(SECTOR_MAP_JSON),
            "tickers_with_sector": len(
                [
                    ticker
                    for ticker, info in _load_sector_map().items()
                    if _valid_sector(info.get("sector", ""))
                ]
            ),
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
            "event_ticker",
            "event_accession_number",
            "event_issuer_excess_return_1d_vs_spy",
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
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260529-010 Peer Earnings-Reaction Transfer",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper candidate source that admits liquid same-sector peers after a positive SEC 8-K Item 2.02 issuer reaction, top-1 per day, next-open entry, ten-trading-day exit.",
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
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Peer earnings-reaction transfer paper sleeve",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_json(DOC_TICKET_JSON, ticket_payload)
    framework.base._write_text(ARTIFACT_MD, _build_report(payload))
    framework.base._write_text(CARD_MD, _build_report(payload))
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
                    "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
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
