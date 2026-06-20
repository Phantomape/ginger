"""exp-20260620-014: supplier-source anchored same-industry peer leadership.

Replay-only alpha search. The single decision hypothesis is that the accepted
supplier-financing/debt-relief direct source can be used as a timestamped
relation anchor: on the same signal date, a same-industry liquid peer with
stronger SPY-relative leadership may capture industry demand spillover without
retuning the accepted supplier helper.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it. No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import exp_20260620_003_defensive_sector_relative_strength as scaffold  # noqa: E402
import exp_20260620_005_supplier_financing_debt_relief_intersection as supplier_source  # noqa: E402


template = scaffold.template
framework = scaffold.framework

EXPERIMENT_ID = "exp-20260620-014"
STEM = "supplier_source_peer_relative_leadership"
TRIAL_FAMILY = "supplier_source_peer_relative_leadership_candidate_pool"
TRIAL_VARIANT_ID = "supplier_source_peer_relative_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "supplier_source_peer_relative_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_014_{STEM}.json"
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

MARKET_PROXY_TICKER = "SPY"
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 75_000_000.0
MIN_PEER_RET20_EXCESS_SPY = 0.05
MIN_PEER_RET60_EXCESS_SPY = 0.05
MIN_PEER_EDGE_OVER_ANCHOR_RET20 = 0.015
MIN_PEER_EDGE_OVER_ANCHOR_RET60 = -0.02
MIN_PEER_RET5 = -0.03
MIN_SIGNAL_RETURN = -0.04
MAX_SIGNAL_RETURN = 0.08
MIN_CLOSE_LOCATION = 0.55
MAX_REALIZED_VOL_20D = 0.12
MAX_PEERS_PER_ANCHOR_DAY = 5

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3_500.0,
    "main_failure_modes": [
        "generic_peer_transfer_not_incremental",
        "window_regression",
        "drawdown_drift",
        "accepted_relation_comparator_not_beaten",
        "supplier_helper_overlap",
    ],
    "confidence_reason": (
        "The accepted supplier helper provides a timestamped production-visible "
        "source anchor, and relation-aware source propagation is listed as a "
        "valid research queue. Confidence stays low because generic peer "
        "transfer, same-sector SEC transfer, and lead-lag variants have "
        "repeatedly failed after costs."
    ),
    "recorded_at": "2026-06-20T13:06:18+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
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
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "uses_free_ohlcv": True,
    "uses_accepted_supplier_source_anchor": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $75M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing accepted supplier source anchor, missing same-industry "
            "peer OHLCV, missing SPY OHLCV, missing next open, or missing 10d "
            "exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "accepted supplier-source anchor, same-industry peer relation, peer "
        "leadership gate, cooldown, next-open paper entry, 10-day exit, costs, "
        "and concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/relation: an accepted supplier-financing debt-relief "
        "direct signal can act as a PIT relation anchor; on the same signal "
        "date, a same-industry liquid peer with stronger SPY-relative "
        "leadership may capture industry demand spillover without retuning the "
        "accepted supplier helper."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Novelty gate warned on supplier/Companyfacts and peer families. "
            "Override is recorded because the new evidence axis is accepted "
            "supplier source rows used only as timestamped relation anchors; "
            "the traded candidate is a different same-industry peer."
        ),
        "exp-20260620-009": (
            "Accepted the direct supplier-financing/debt-relief helper as a "
            "standalone shared default-off paper adapter. This run does not "
            "retune DPO, debt, risk, notional, hold, or cooldown."
        ),
        "exp-20260620-011": (
            "Rejected adding the accepted supplier source into the allocator. "
            "This run is not allocator rank insertion; it tests a peer relation "
            "candidate source outside the accepted allocator."
        ),
        "exp-20260608-025": (
            "Rejected characteristic-similar same-industry peer shock. This run "
            "requires an accepted supplier-source anchor, not a generic peer shock."
        ),
        "exp-20260610-022": (
            "Rejected rolling lead-lag peer underreaction. This run is same-day "
            "source propagation, not lagged price diffusion."
        ),
        "exp-20260618-006": (
            "Rejected intraindustry lead-lag direction stability. This run does "
            "not reuse static lead-lag thresholds."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution and closest accepted relation/source comparators must be "
        "beaten. Replay-only positives are leads until shared daily/backtest "
        "parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_014_supplier_source_peer_relative_leadership.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    return scaffold._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return scaffold._round(value, digits)


def _peer_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    anchor: dict[str, Any],
) -> dict[str, Any] | None:
    rows = framework.shadow._series(snapshot, ticker)
    spy_rows = framework.shadow._series(snapshot, MARKET_PROXY_TICKER)
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get(MARKET_PROXY_TICKER, {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if min(idx, spy_idx) < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx, 20)
    required = (
        signal_return,
        close_location,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol,
    )
    if any(value is None for value in required):
        return None
    assert signal_return is not None and close_location is not None
    assert ret5 is not None and ret20 is not None and ret60 is not None
    assert spy_ret20 is not None and spy_ret60 is not None and realized_vol is not None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if ret5 < MIN_PEER_RET5:
        return None
    if realized_vol > MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    anchor_ret20_excess = float(anchor.get("candidate_ret20_excess_spy") or 0.0)
    anchor_ret60_excess = float(anchor.get("candidate_ret60_excess_spy") or 0.0)
    if ret20_excess_spy < MIN_PEER_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_PEER_RET60_EXCESS_SPY:
        return None
    peer_edge_ret20 = ret20_excess_spy - anchor_ret20_excess
    peer_edge_ret60 = ret60_excess_spy - anchor_ret60_excess
    if peer_edge_ret20 < MIN_PEER_EDGE_OVER_ANCHOR_RET20:
        return None
    if peer_edge_ret60 < MIN_PEER_EDGE_OVER_ANCHOR_RET60:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    anchor_strength = max(anchor_ret20_excess, 0.0)
    score = (
        0.55 * ret20_excess_spy
        + 0.25 * ret60_excess_spy
        + 0.35 * peer_edge_ret20
        + 0.15 * max(peer_edge_ret60, 0.0)
        + 0.10 * ret5
        + 0.10 * close_location
        + 0.08 * anchor_strength
        - 0.45 * realized_vol
        + 0.02 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    return {
        "candidate_score": _round(score, 6),
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret5": _round(ret5, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret60": _round(ret60, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_peer_edge_ret20_excess_spy": _round(peer_edge_ret20, 6),
        "candidate_peer_edge_ret60_excess_spy": _round(peer_edge_ret60, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    eligible_tickers: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    quality_index, quality_summary = supplier_source._build_quality_index([])
    direct_candidates, direct_scan = supplier_source._candidate_rows_for_window(
        snapshot=snapshot,
        cfg=cfg,
        sector_entries=sector_entries,
        quality_index=quality_index,
    )
    direct_trades, direct_rejected = supplier_source.base.framework._select_paper_trades(
        snapshot=snapshot,
        candidates=direct_candidates,
    )

    eligible_by_industry: dict[str, list[str]] = {}
    for ticker in sorted(set(eligible_tickers) & set(snapshot)):
        meta = sector_entries.get(ticker) or {}
        industry = meta.get("industry")
        if not industry or ticker == MARKET_PROXY_TICKER:
            continue
        eligible_by_industry.setdefault(str(industry), []).append(ticker)

    direct_tickers_by_date: dict[str, set[str]] = {}
    for row in direct_candidates:
        direct_tickers_by_date.setdefault(str(row.get("date")), set()).add(str(row.get("ticker")))

    scan: Counter[str] = Counter()
    scan["direct_raw_candidate_rows"] = len(direct_candidates)
    scan["direct_selected_anchor_trades"] = len(direct_trades)
    scan["direct_rejected_candidate_rows"] = len(direct_rejected)
    scan["quality_index_tickers"] = len(quality_index)
    candidates: list[dict[str, Any]] = []
    anchor_sample: list[dict[str, Any]] = []

    for anchor in direct_trades:
        signal_date = str(anchor.get("signal_date") or anchor.get("date") or "")[:10]
        anchor_ticker = str(anchor.get("ticker") or "").upper()
        anchor_industry = str(anchor.get("industry") or "")
        if not signal_date or not anchor_ticker or not anchor_industry:
            scan["anchor_missing_relation_fields"] += 1
            continue
        peers = [
            ticker
            for ticker in eligible_by_industry.get(anchor_industry, [])
            if ticker != anchor_ticker
            and ticker not in direct_tickers_by_date.get(signal_date, set())
        ]
        if not peers:
            scan["anchor_no_same_industry_peers"] += 1
            continue
        scan["anchor_peer_days"] += 1
        if len(anchor_sample) < 8:
            anchor_sample.append(
                {
                    "signal_date": signal_date,
                    "anchor_ticker": anchor_ticker,
                    "anchor_industry": anchor_industry,
                    "anchor_ret20_excess_spy": anchor.get("candidate_ret20_excess_spy"),
                    "peer_count": len(peers),
                }
            )
        peer_rows: list[dict[str, Any]] = []
        for ticker in peers:
            scan["peer_day_evaluations"] += 1
            confirm = _peer_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
                anchor=anchor,
            )
            if confirm is None:
                scan["failed_peer_confirmation"] += 1
                continue
            meta = sector_entries.get(ticker, {})
            peer_rows.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SUPPLIER_SOURCE_PEER_RELATIVE_LEADERSHIP_PAPER",
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "anchor_source_rule_version": supplier_source.CHANGED_VARIABLE,
                    "known_at": "accepted_supplier_source_anchor_and_signal_date_ohlcv_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "anchor_ticker": anchor_ticker,
                    "anchor_industry": anchor_industry,
                    "anchor_signal_date": signal_date,
                    "anchor_source": anchor.get("source"),
                    "anchor_candidate_score": anchor.get("candidate_score"),
                    "anchor_ret20_excess_spy": anchor.get("candidate_ret20_excess_spy"),
                    "anchor_ret60_excess_spy": anchor.get("candidate_ret60_excess_spy"),
                    "anchor_paper_pnl": anchor.get("pnl"),
                    "same_ticker_ab_overlap": False,
                    "uses_accepted_supplier_source_anchor": True,
                    "uses_free_sec_companyfacts": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **confirm,
                }
            )
        peer_rows.sort(
            key=lambda row: (
                -float(row.get("candidate_score") or 0.0),
                -float(row.get("candidate_peer_edge_ret20_excess_spy") or 0.0),
                -float(row.get("candidate_ret20_excess_spy") or 0.0),
                -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
                row["ticker"],
            )
        )
        selected_peer_rows = peer_rows[:MAX_PEERS_PER_ANCHOR_DAY]
        scan["qualified_peer_rows"] += len(peer_rows)
        scan["emitted_peer_rows"] += len(selected_peer_rows)
        candidates.extend(selected_peer_rows)

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row.get("candidate_score") or 0.0),
            -float(row.get("candidate_peer_edge_ret20_excess_spy") or 0.0),
            -float(row.get("candidate_ret20_excess_spy") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(candidates)
    scan["candidate_signal_days"] = len({row["date"] for row in candidates})
    scan["candidate_tickers"] = len({row["ticker"] for row in candidates})
    scan["anchor_sample"] = anchor_sample
    return candidates, {
        **dict(scan),
        "direct_source_scan": direct_scan,
        "quality_index_summary": quality_summary,
        "max_peers_per_anchor_day": MAX_PEERS_PER_ANCHOR_DAY,
    }


def _configure_template() -> None:
    template.EXPERIMENT_ID = EXPERIMENT_ID
    template.STEM = STEM
    template.TRIAL_FAMILY = TRIAL_FAMILY
    template.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    template.CHANGED_VARIABLE = CHANGED_VARIABLE
    template.RULE_VERSION = RULE_VERSION
    template.OWNER = OWNER
    template.OUT_DIR = OUT_DIR
    template.OUT_JSON = OUT_JSON
    template.LOG_JSON = LOG_JSON
    template.TICKET_JSON = TICKET_JSON
    template.CARD_MD = CARD_MD
    template.MANIFEST_JSON = MANIFEST_JSON
    template.EXPERIMENT_LOG = EXPERIMENT_LOG
    template.REGISTRY_JSON = REGISTRY_JSON
    template.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    template.HOLD_DAYS = HOLD_DAYS
    template.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    template.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    template.RATE_PROXY_TICKER = "TLT"
    template.GROWTH_PROXY_TICKER = "QQQ"
    template.MARKET_PROXY_TICKER = MARKET_PROXY_TICKER
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._load_window_snapshot = scaffold._load_window_snapshot
    template._candidate_rows_for_window = _candidate_rows_for_window


def _finalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    target_summary = payload["target_trade_summary"]
    decision = (
        "positive_replay_lead_not_promoted_supplier_source_peer_relative_leadership"
        if gate4["passed"]
        else "rejected_supplier_source_peer_relative_leadership_candidate_pool"
    )
    payload["decision"] = decision
    payload["gate4"]["decision"] = decision
    payload["mechanism_family"] = "production_visible_free_ohlcv_relation_alpha"
    payload["new_evidence_type"] = "accepted_supplier_source_relation_anchor"
    payload["nearby_prior_experiments"] = [
        "exp-20260620-009",
        "exp-20260620-011",
        "exp-20260608-025",
        "exp-20260610-022",
        "exp-20260618-006",
    ]
    payload["prior_trial_count"] = 0
    payload["multiple_testing_risk_bucket"] = "high"
    payload["backtest_protocol"]["candidate_ohlcv_source"] = _repo_rel(framework.WAREHOUSE)
    payload["backtest_protocol"]["source_anchor"] = "accepted exp-20260620-009 supplier-financing/debt-relief helper rows"
    payload["backtest_protocol"]["execution_model"] = (
        "Accepted supplier-financing/debt-relief direct rows are computed from "
        "PIT raw SEC Companyfacts and signal-date OHLCV, then used only as "
        "timestamped same-industry relation anchors. Candidate peers are "
        "different tickers in the same industry with stronger SPY-relative "
        "ret20 leadership at the signal close. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_peer_ret20_excess_spy": MIN_PEER_RET20_EXCESS_SPY,
        "min_peer_ret60_excess_spy": MIN_PEER_RET60_EXCESS_SPY,
        "min_peer_edge_over_anchor_ret20": MIN_PEER_EDGE_OVER_ANCHOR_RET20,
        "min_peer_edge_over_anchor_ret60": MIN_PEER_EDGE_OVER_ANCHOR_RET60,
        "min_peer_ret5": MIN_PEER_RET5,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "max_peers_per_anchor_day": MAX_PEERS_PER_ANCHOR_DAY,
    }
    payload["gate2"]["runtime_fields"] = [
        "accepted supplier-financing/debt-relief source rows",
        "raw SEC Companyfacts fields used by the accepted supplier helper",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "candidate sector/industry metadata",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    for coverage in payload["warehouse_coverage_by_window"].values():
        coverage["relation_anchor"] = "accepted_supplier_financing_debt_relief_source"
    payload["interpretation"] = (
        "The supplier-source peer relation cleared Gate 4 as a replay-only/"
        "default-off lead, but no production surface was promoted."
        if gate4["passed"]
        else (
            "The supplier-source peer relation did not clear Gate 4 (failed: "
            + (", ".join(gate4["failed_reasons"]) or "none")
            + "). Do not promote or tune this peer relation on the same frozen windows."
        )
    )
    payload["next_evidence_needed"] = (
        "A retry needs materially richer PIT relation provenance such as named "
        "supplier/customer contract links, payment-term disclosure, peer "
        "source-family propagation with forward replacement-value rows, or "
        "customer/supplier graph edges. Do not sweep peer edge thresholds, "
        "industry grouping, RS/close/volume/vol guards, top-N, hold, cooldown, "
        "or notional on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Gate 4 passed numerically, but this is replay-only because no "
            "shared daily/backtest helper exists."
            if gate4["passed"]
            else (
                "Rejected. The accepted supplier source did not transfer "
                "reliable edge to different same-industry peers after "
                "next-open execution, costs, cooldown, and comparator checks "
                "(failed: {}). The result suggests the accepted supplier alpha "
                "is issuer-specific cross-statement evidence, not a broad "
                "industry spillover signal."
            ).format(", ".join(gate4["failed_reasons"]) or "none")
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                target_summary["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping peer edge thresholds, same-industry "
            "grouping, RS/close/volume/volatility guards, top-N, hold days, "
            "cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": (
            "Need named supplier/customer relation provenance, source-family "
            "propagation forward rows, or other PIT relation graph evidence "
            "before revisiting supplier-source peer propagation."
        ),
    }
    payload["related_files"] = [
        _repo_rel(THIS_FILE),
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Anchors | Raw peers | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {anchors} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                anchors=scan.get("direct_selected_anchor_trades", 0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Supplier Source Peer Relative Leadership",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                template.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                template.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                template.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                template.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": _repo_rel(template.BASELINE_RESULT_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": template.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": template.DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "direct_selected_anchor_trades": payload["context_scan_by_window"][label].get("direct_selected_anchor_trades"),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(THIS_FILE),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(THIS_FILE): framework._sha256(THIS_FILE),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
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
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
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
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    template.base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    _configure_template()
    payload = _finalize_payload(template._build_payload())
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
