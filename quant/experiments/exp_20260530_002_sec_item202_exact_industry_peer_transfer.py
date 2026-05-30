"""exp-20260530-002: SEC Item 2.02 exact-industry peer transfer.

This alpha search tests one free-data candidate-pool source. After a positive
SEC 8-K Item 2.02 issuer reaction, only liquid peers with the same reference
industry string can become default-off paper candidates. Core signals, ranking,
sizing, exits, LLM/news, watchlists, and live/default orders are unchanged.
No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260529_010_peer_earnings_reaction_transfer as prior


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260530-002"
STEM = "sec_item202_exact_industry_peer_transfer"
TRIAL_FAMILY = "peer_earnings_reaction_exact_industry_candidate_pool"
CHANGED_VARIABLE = "sec_item_202_exact_industry_peer_transfer_candidate_source_v1"
RULE_VERSION = "sec_8k_item_202_exact_industry_peer_transfer_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_002_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_PEER_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MIN_PEER_RS20_VS_SPY = 0.0
MIN_PEER_CLOSE_LOCATION = 0.55
MIN_PEER_SIGNAL_EXCESS_RETURN_1D_VS_SPY = -0.01

framework = prior.framework


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
    framework.DOC_TICKET_JSON = TICKET_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = 1
    framework.MIN_TARGET_TRADES = 20
    framework.MIN_TARGET_WINDOWS = 3
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _industry_key(ticker: str) -> str:
    industry = str(prior._sector_info(ticker).get("industry") or "").strip()
    return " ".join(industry.lower().split())


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

    peer_universe = sorted(
        set(universe).intersection(snapshot).difference(framework.EXCLUDED_TICKERS)
    )
    peers_by_industry: dict[str, list[str]] = defaultdict(list)
    for ticker in peer_universe:
        sector = prior._sector_info(ticker).get("sector", "")
        industry_key = _industry_key(ticker)
        if not prior._valid_sector(sector):
            audit["peer_missing_sector"] += 1
            continue
        if not industry_key:
            audit["peer_missing_industry"] += 1
            continue
        peers_by_industry[industry_key].append(ticker)

    raw_events = [
        event
        for event in prior._load_sec_earnings_events()
        if str(event.get("usable_trade_date")) in date_set
    ]
    reaction_events: list[dict[str, Any]] = []
    for event in raw_events:
        issuer = str(event["ticker"]).upper()
        issuer_sector = prior._sector_info(issuer).get("sector", "")
        issuer_industry = prior._sector_info(issuer).get("industry", "")
        issuer_industry_key = _industry_key(issuer)
        if not prior._valid_sector(issuer_sector):
            audit["event_missing_sector"] += 1
            continue
        if not issuer_industry_key:
            audit["event_missing_industry"] += 1
            continue
        if issuer not in snapshot:
            audit["event_issuer_missing_ohlcv"] += 1
            continue
        reaction = prior._event_reaction(snapshot, event, spy_rows, spy_index)
        if reaction is None:
            audit["event_reaction_not_positive_enough"] += 1
            continue
        reaction["sector"] = issuer_sector
        reaction["industry"] = issuer_industry
        reaction["industry_key"] = issuer_industry_key
        reaction_events.append(reaction)

    min_idx = max(
        prior.MOVING_AVERAGE_DAYS,
        prior.RELATIVE_STRENGTH_DAYS,
        prior.AVG_DOLLAR_VOLUME_DAYS,
    )
    for event in reaction_events:
        date = str(event["date"])
        issuer = str(event["ticker"]).upper()
        industry_key = str(event["industry_key"])
        exact_industry_peers = peers_by_industry.get(industry_key, [])
        if not exact_industry_peers:
            audit["no_exact_industry_peers"] += 1
            continue

        for ticker in exact_industry_peers:
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

            avg_dollar_volume = prior._avg_dollar_volume(
                rows, idx, prior.AVG_DOLLAR_VOLUME_DAYS
            )
            if (
                avg_dollar_volume is None
                or avg_dollar_volume < MIN_PEER_AVG_DOLLAR_VOLUME_20D
            ):
                audit["peer_low_avg_dollar_volume"] += 1
                continue

            ma50 = framework._prior_average(rows, idx, prior.MOVING_AVERAGE_DAYS, "Close")
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
                (2.0 * float(event["issuer_excess_return_1d_vs_spy"]))
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
                    "event_source": "sec_8k_item_2_02",
                    "event_ticker": issuer,
                    "event_accession_number": event["accession_number"],
                    "event_accepted_at": event.get("accepted_at"),
                    "event_usable_trade_date": date,
                    "event_sector": event["sector"],
                    "event_industry": event["industry"],
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
                    "peer_sector": prior._sector_info(ticker).get("sector"),
                    "peer_industry": prior._sector_info(ticker).get("industry"),
                    "peer_relation_source": "exact_reference_industry_match",
                    "peer_relation_key": industry_key,
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
        "peer_industry_count": len(peers_by_industry),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "relation_field": "exact reference industry string match",
        "sec_events_source": framework.base._repo_rel(prior.SEC_EVENTS_FILE),
        "sector_map_source": framework.base._repo_rel(prior.SECTOR_MAP_JSON),
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_sec_item202_exact_industry_peer_transfer"
        if gate4["passed"]
        else "rejected_sec_item202_exact_industry_peer_transfer"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.30,
        "expected_ev_delta": 0.16,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "sample_too_thin_after_exact_industry_filter",
            "late_strong_regression",
            "single_industry_concentration",
            "industry_map_not_pit_enough_for_promotion",
        ],
        "confidence_reason": (
            "The prior same-sector and comovement SEC peer-transfer scouts were "
            "positive in aggregate but failed robustness. Exact industry is a "
            "sharper free peer-relation field named by the playbook as a valid "
            "next relation source, but it may cut sample size too far."
        ),
        "recorded_at": "2026-05-30T00:44:25+00:00",
        "brier_score": round((0.30 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "SEC 8-K Item 2.02 positive issuer reactions may transfer better "
                "to liquid peers with exact industry similarity than to broad "
                "same-sector or return-comovement peers."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": "sec_8k_item_202_exact_industry_peer_transfer_v1",
            "prior_trial_count": 2,
            "nearby_prior_experiments": [
                "exp-20260529-010",
                "exp-20260529-011",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "free_sec_event_plus_official_industry_peer_relation"
            ),
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": framework.MAX_PAPER_TRADES_PER_DAY,
                "sec_item_code": prior.EVENT_ITEM_CODE,
                "issuer_reaction_lookback_days": prior.ISSUER_REACTION_LOOKBACK_DAYS,
                "relative_strength_days": prior.RELATIVE_STRENGTH_DAYS,
                "moving_average_days": prior.MOVING_AVERAGE_DAYS,
                "avg_dollar_volume_days": prior.AVG_DOLLAR_VOLUME_DAYS,
                "min_issuer_return_1d": prior.MIN_ISSUER_RETURN_1D,
                "min_issuer_excess_return_1d_vs_spy": (
                    prior.MIN_ISSUER_EXCESS_RETURN_1D_VS_SPY
                ),
                "min_issuer_close_location": prior.MIN_ISSUER_CLOSE_LOCATION,
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
                    "peer must share the issuer's exact non-empty reference industry string",
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
                    "candidate_pool / entry: strong SEC Item 2.02 issuer reactions "
                    "may spill over only to peers with exact industry similarity, "
                    "not all same-sector names."
                ),
                "2_history_check": {
                    "exp-20260529-010": (
                        "Same-sector peer transfer improved aggregate EV but "
                        "failed late_strong. This run changes peer relation to "
                        "exact industry, not event thresholds."
                    ),
                    "exp-20260529-011": (
                        "Same-sector + 60d return comovement remained positive "
                        "in aggregate but failed late_strong and sample guard. "
                        "This run uses a distinct relation source: reference "
                        "industry similarity."
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
                    "exp_20260530_002_sec_item202_exact_industry_peer_transfer.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay coverage remains sparse; "
                "skipped Companyfacts/VBB/VCP/state-surface scalar retunes because "
                "the playbook requires forward rows or materially new fields. This "
                "tests a sharper free peer-relation field for the SEC peer-transfer "
                "direction and changes only the candidate-source relation."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. Acceptance would still "
                    "require a shared SEC-event paper adapter exposing the same "
                    "industry relation in production before any order-affecting use."
                ),
            },
            "interpretation": (
                "The exact-industry SEC peer-transfer sleeve cleared Gate 4 as a "
                "default-off replay lead; live/default orders remain disabled."
                if gate4["passed"]
                else (
                    "The exact-industry SEC peer-transfer sleeve did not clear "
                    "Gate 4. Do not promote it or retry nearby SEC Item 2.02 "
                    "peer-transfer relation thresholds on these frozen windows "
                    "without forward rows or a stronger relation source such as "
                    "customer/supplier links or multi-season event co-movement."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(
                gate4["failed_reasons"]
            ),
            "next_evidence_needed": (
                "Forward rows or a materially stronger peer-relation source such "
                "as customer/supplier links, audited industry-level similarity, "
                "or multi-season event co-movement."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "SEC Item 2.02 metadata uses PIT usable_trade_date. Issuer and exact "
        "industry peer OHLCV are observed through signal-date close; paper entry "
        "is next open and exit is ten trading days after signal."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "sec_events": {
            "source": framework.base._repo_rel(prior.SEC_EVENTS_FILE),
            "required_fields": [
                "ticker",
                "usable_trade_date",
                "accession_number",
                "form_base/form_type",
                "eight_k_item_codes",
                "pit_safe_flag",
            ],
            "events_loaded": len(prior._load_sec_earnings_events()),
        },
        "peer_relation": {
            "source": framework.base._repo_rel(prior.SECTOR_MAP_JSON),
            "required_fields": [
                "issuer reference sector and industry",
                "peer reference sector and industry",
                "peer OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV rows",
            ],
            "relation": "exact reference industry string match",
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
            "event_industry",
            "peer_industry",
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
            "# exp-20260530-002 SEC Item 2.02 Exact-Industry Peer Transfer",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: default-off paper candidates are SEC Item 2.02 peer-transfer rows whose peer has the same reference industry string as the positive-reaction issuer.",
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


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC Item 2.02 exact-industry peer transfer",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
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
    raise SystemExit(main())
