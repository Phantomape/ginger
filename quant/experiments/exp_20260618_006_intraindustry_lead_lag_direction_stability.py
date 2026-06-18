"""exp-20260618-006: PIT intra-industry lead-lag direction stability scout.

Replay-only alpha search. The single decision hypothesis is a candidate-pool
relation source: a same-industry laggard should only be considered after liquid
industry leaders move when prior, point-in-time completed leader events for
that ticker show positive next-10-day excess return.

This is deliberately different from exp-20260617-021's static liquidity-leader
lead-lag source. The current leader/laggard setup is still required, but this
scout adds a rolling ex-ante direction-stability gate computed only from
historical observations whose 10-day outcome was known before the signal date.

No production code, shared helper, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. A positive result is only a
replay lead until a shared historical/daily helper reproduces it. No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260618-006"
STEM = "intraindustry_lead_lag_direction_stability"
TRIAL_FAMILY = "free_ohlcv_intraindustry_lead_lag_direction_stability_candidate_pool"
TRIAL_VARIANT_ID = "lead_lag_direction_stability_top1_next_open_10d_v1"
CHANGED_VARIABLE = "intraindustry_lead_lag_direction_stability_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_006_{STEM}.json"
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

# Current signal construction.
LEAD_LOOKBACK_DAYS = 10
LOAD_LOOKBACK_CALENDAR_DAYS = 390
MIN_HISTORY_IDX = 80
MIN_INDUSTRY_MEMBERS = 6
LEADER_TOP_K = 3
MIN_LEADER_EXCESS_RET = 0.04
MIN_DIFFUSION_GAP = 0.05
MAX_CANDIDATE_EXCESS_RET = 0.02
MIN_CANDIDATE_RET = -0.06

# Ex-ante historical relation gate. Outcomes must be fully known before the
# current signal close, so each anchor must finish its 10-day hold before today.
RELATION_LOOKBACK_DAYS = 180
RELATION_MIN_OBS = 8
RELATION_HISTORY_MIN_LEADER_EXCESS_RET = 0.02
RELATION_MAX_HISTORY_CANDIDATE_EXCESS_RET = 0.03
RELATION_MIN_MEDIAN_FWD_EXCESS = 0.0
RELATION_MIN_HIT_RATE = 0.50
RELATION_MIN_SCORE = 0.002

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0

EXCLUDED_TICKERS = {
    "ARKX", "BIL", "DIA", "GLD", "IAU", "IBIT", "IEF", "IWM", "QQQ", "SHY",
    "SLV", "SPY", "TLT", "UFO", "UUP", "USO", "VIXM", "VIXY", "VXX",
    "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "relation_history_noisy",
        "old_thin_window_regression",
        "accepted_distribution_comparator_not_beaten",
        "thin_sample",
        "drawdown_drift_too_high",
    ],
    "confidence_reason": (
        "Static intraindustry liquidity-leader lead-lag was positive in "
        "aggregate but regime/window fragile. Its closeout explicitly allowed "
        "materially different relation construction such as PIT lead-lag "
        "direction stability. This test adds an ex-ante historical "
        "predictiveness gate using only outcomes known before the signal date, "
        "so it is not a threshold retune of the frozen static source."
    ),
    "recorded_at": "2026-06-18T05:04:24Z",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "industry with fewer than 6 liquid members, missing leader basket, "
            "insufficient completed PIT relation history, missing OHLCV, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. The core baseline stays "
        "the canonical core replay and only the default-off paper candidate "
        "snapshot is the broad liquid universe. A positive result is only a "
        "replay lead until a shared default-off helper computes the same PIT "
        "per-industry liquidity-leader basket, rolling completed direction "
        "stability gate, next-open paper entry, 10-day exit, costs, cooldown, "
        "and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool relation: a same-industry laggard should only be "
        "considered after liquid industry leaders move when past PIT lead-lag "
        "direction stability shows that leader moves historically predicted "
        "that ticker's next-10d excess return."
    ),
    "2_history_check": {
        "exp-20260617-021": (
            "Rejected static intraindustry liquidity-leader lead-lag source: "
            "aggregate EV/PnL was positive but late_strong and old_thin "
            "regressed, drawdown drift was too high, and the closeout froze "
            "static threshold sweeps while allowing materially different "
            "relation construction such as PIT lead-lag direction stability."
        ),
        "exp-20260607-007": (
            "Accepted industry-relative laggard repair requires whole-industry "
            "median strength and same-day repair confirmation. This run uses a "
            "leader subset plus ex-ante relation history and still keeps the "
            "candidate not-yet-moved."
        ),
        "exp-20260608-008": (
            "Accepted industry-stable core-flow keys on stable leaders with "
            "core entry-flow confirmation. This run tests ticker-specific "
            "historical diffusion reliability, not core-flow confirmation."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no unacceptable window regression, survival >=5%, at "
        "least 20 paper trades across all windows, drawdown drift <=0.5pp, "
        "concentration pass, and accepted compression/distribution candidate "
        "comparators must be beaten. Replay positives are leads only until "
        "shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260618_006_intraindustry_lead_lag_direction_stability.py"
    ),
}

_BROAD_TICKER_CACHE: set[str] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _broad_liquid_tickers() -> set[str]:
    global _BROAD_TICKER_CACHE
    if _BROAD_TICKER_CACHE is not None:
        return _BROAD_TICKER_CACHE
    uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as con:
        rows = con.execute(
            """
            select u.ticker
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
            order by u.ticker
            """
        ).fetchall()
    tickers = {str(r[0]).upper() for r in rows} - EXCLUDED_TICKERS
    _BROAD_TICKER_CACHE = tickers
    return tickers


def _broad_load_window_snapshot(
    *, cfg: dict[str, str], eligible_tickers: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """Load broad liquid OHLCV with enough pre-window history for relation stats."""
    _ = eligible_tickers
    start = base.framework._parse_date(cfg["start"]) - timedelta(days=LOAD_LOOKBACK_CALENDAR_DAYS)
    end = base.framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(_broad_liquid_tickers() | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, base.framework._date_str(start), base.framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    _ = companyfacts_rows
    return {}, {
        "field_source": "ohlcv_relation_no_companyfacts",
        "selected_companyfacts_rows_ignored": 0,
    }


def _industry_key(meta: dict[str, Any]) -> str | None:
    industry = meta.get("industry") or meta.get("gics_industry")
    sector = meta.get("sector") or meta.get("gics_sector")
    key = industry or sector
    return str(key) if key else None


def _forward_excess(
    *,
    rows: list[dict[str, Any]],
    idx: int,
    spy_rows: list[dict[str, Any]],
    spy_idx: int,
    hold_days: int,
) -> float | None:
    if idx + hold_days >= len(rows) or spy_idx + hold_days >= len(spy_rows):
        return None
    close0 = base.framework._value(rows[idx], "Close")
    close1 = base.framework._value(rows[idx + hold_days], "Close")
    spy0 = base.framework._value(spy_rows[spy_idx], "Close")
    spy1 = base.framework._value(spy_rows[spy_idx + hold_days], "Close")
    if close0 is None or close0 <= 0 or close1 is None:
        return None
    if spy0 is None or spy0 <= 0 or spy1 is None:
        return None
    return (close1 / close0 - 1.0) - (spy1 / spy0 - 1.0)


def _relation_stats(
    *,
    signal_date: str,
    ticker: str,
    leaders: list[str],
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    spy_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker)
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if rows is None or idx is None or spy_idx is None:
        return None
    if idx < MIN_HISTORY_IDX or spy_idx < MIN_HISTORY_IDX:
        return None
    earliest = max(MIN_HISTORY_IDX, idx - RELATION_LOOKBACK_DAYS)
    latest = idx - HOLD_DAYS - 1
    if latest <= earliest:
        return None

    observations: list[float] = []
    leader_excesses: list[float] = []
    for anchor_idx in range(earliest, latest + 1):
        anchor_date = rows[anchor_idx].get("Date")
        if anchor_date is None:
            continue
        anchor_spy_idx = indices.get("SPY", {}).get(str(anchor_date))
        if anchor_spy_idx is None or anchor_spy_idx + HOLD_DAYS >= spy_idx:
            continue
        spy_ret = base.framework._ret(spy_rows, anchor_spy_idx, LEAD_LOOKBACK_DAYS)
        if spy_ret is None:
            continue
        leader_values: list[float] = []
        for leader in leaders:
            leader_rows = snapshot.get(leader)
            leader_idx = indices.get(leader, {}).get(str(anchor_date))
            if leader_rows is None or leader_idx is None:
                continue
            leader_ret = base.framework._ret(leader_rows, leader_idx, LEAD_LOOKBACK_DAYS)
            if leader_ret is None:
                continue
            leader_values.append(float(leader_ret - spy_ret))
        if not leader_values:
            continue
        leader_excess = median(leader_values)
        if leader_excess < RELATION_HISTORY_MIN_LEADER_EXCESS_RET:
            continue
        candidate_ret = base.framework._ret(rows, anchor_idx, LEAD_LOOKBACK_DAYS)
        if candidate_ret is None:
            continue
        candidate_excess = candidate_ret - spy_ret
        if candidate_excess > RELATION_MAX_HISTORY_CANDIDATE_EXCESS_RET:
            continue
        fwd = _forward_excess(
            rows=rows,
            idx=anchor_idx,
            spy_rows=spy_rows,
            spy_idx=anchor_spy_idx,
            hold_days=HOLD_DAYS,
        )
        if fwd is None:
            continue
        observations.append(float(fwd))
        leader_excesses.append(float(leader_excess))

    if len(observations) < RELATION_MIN_OBS:
        return None
    median_fwd = median(observations)
    mean_fwd = mean(observations)
    hit_rate = sum(1 for value in observations if value > 0.0) / len(observations)
    avg_leader_excess = mean(leader_excesses) if leader_excesses else 0.0
    relation_score = median_fwd + 0.02 * (hit_rate - 0.5) + 0.05 * max(avg_leader_excess, 0.0)
    if median_fwd < RELATION_MIN_MEDIAN_FWD_EXCESS:
        return None
    if hit_rate < RELATION_MIN_HIT_RATE:
        return None
    if relation_score < RELATION_MIN_SCORE:
        return None
    return {
        "observation_count": len(observations),
        "median_forward_excess": median_fwd,
        "mean_forward_excess": mean_fwd,
        "hit_rate": hit_rate,
        "avg_leader_excess": avg_leader_excess,
        "relation_score": relation_score,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _ = quality_index
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    window_dates = [d for d in dates if start <= d <= end]
    spy_rows = base.framework.shadow._series(snapshot, "SPY")

    industry_members: dict[str, list[str]] = defaultdict(list)
    for ticker, meta in sector_entries.items():
        if ticker in EXCLUDED_TICKERS or ticker not in snapshot:
            continue
        key = _industry_key(meta)
        if key:
            industry_members[key].append(ticker)

    scan: Counter[str] = Counter()
    scan["industries"] = sum(1 for m in industry_members.values() if len(m) >= MIN_INDUSTRY_MEMBERS)
    scan["sector_known_tickers"] = len(sector_entries)
    candidates: list[dict[str, Any]] = []

    for signal_date in window_dates:
        spy_idx = indices.get("SPY", {}).get(signal_date)
        if spy_idx is None or spy_idx < MIN_HISTORY_IDX:
            continue
        spy_retL = base.framework._ret(spy_rows, spy_idx, LEAD_LOOKBACK_DAYS)
        if spy_retL is None:
            continue
        metrics: dict[str, dict[str, float]] = {}
        for ticker, rows in snapshot.items():
            if ticker == "SPY" or ticker in EXCLUDED_TICKERS:
                continue
            idx = indices.get(ticker, {}).get(signal_date)
            if idx is None or idx < MIN_HISTORY_IDX or idx + HOLD_DAYS >= len(rows):
                continue
            close = base.framework._value(rows[idx], "Close")
            if close is None or close < MIN_PRICE:
                continue
            adv20 = base.framework._avg_dollar_volume(rows, idx)
            if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
                continue
            retL = base.framework._ret(rows, idx, LEAD_LOOKBACK_DAYS)
            if retL is None:
                continue
            metrics[ticker] = {
                "adv20": float(adv20),
                "retL": float(retL),
                "retL_excess": float(retL - spy_retL),
                "close": float(close),
            }
        for industry, members in industry_members.items():
            present = [t for t in members if t in metrics]
            if len(present) < MIN_INDUSTRY_MEMBERS:
                continue
            scan["industry_day_evaluations"] += 1
            ranked = sorted(present, key=lambda t: metrics[t]["adv20"], reverse=True)
            leaders = ranked[:LEADER_TOP_K]
            leader_set = set(leaders)
            leader_excess = median(metrics[t]["retL_excess"] for t in leaders)
            if leader_excess < MIN_LEADER_EXCESS_RET:
                scan["leader_basket_too_weak"] += 1
                continue
            for ticker in present:
                if ticker in leader_set:
                    continue
                m = metrics[ticker]
                gap = leader_excess - m["retL_excess"]
                if gap < MIN_DIFFUSION_GAP:
                    continue
                if m["retL_excess"] > MAX_CANDIDATE_EXCESS_RET:
                    continue
                if m["retL"] < MIN_CANDIDATE_RET:
                    continue
                scan["static_gate_candidate_rows"] += 1
                rel = _relation_stats(
                    signal_date=signal_date,
                    ticker=ticker,
                    leaders=leaders,
                    snapshot=snapshot,
                    indices=indices,
                    spy_rows=spy_rows,
                )
                if rel is None:
                    scan["relation_gate_rejected_rows"] += 1
                    continue
                scan["qualified_candidate_rows"] += 1
                meta = sector_entries.get(ticker, {})
                score = (
                    2.00 * min(float(rel["relation_score"]), 0.20)
                    + 0.75 * min(gap, 0.40)
                    + 0.35 * min(leader_excess, 0.40)
                    + 0.025 * math.log10(max(m["adv20"], 1.0) / 1_000_000.0)
                )
                candidates.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": "INTRAINDUSTRY_LEAD_LAG_DIRECTION_STABILITY_PAPER",
                        "candidate_score": _round(score, 6),
                        "rule_version": RULE_VERSION,
                        "source_rule_version": RULE_VERSION,
                        "known_at": (
                            "signal_close_and_completed_historical_relation_before_"
                            "next_open_paper_entry"
                        ),
                        "sector": meta.get("sector"),
                        "industry": _industry_key(meta),
                        "uses_free_ohlcv": True,
                        "uses_free_sec_companyfacts": False,
                        "uses_llm": False,
                        "trade_enabled": False,
                        "leadlag_industry": industry,
                        "leadlag_leader_tickers": leaders,
                        "leadlag_leader_excess_ret10": _round(leader_excess, 6),
                        "leadlag_candidate_excess_ret10": _round(m["retL_excess"], 6),
                        "leadlag_candidate_ret10": _round(m["retL"], 6),
                        "leadlag_diffusion_gap": _round(gap, 6),
                        "leadlag_industry_member_count": len(present),
                        "leadlag_relation_observation_count": rel["observation_count"],
                        "leadlag_relation_median_forward_excess": _round(
                            rel["median_forward_excess"], 6
                        ),
                        "leadlag_relation_mean_forward_excess": _round(
                            rel["mean_forward_excess"], 6
                        ),
                        "leadlag_relation_hit_rate": _round(rel["hit_rate"], 6),
                        "leadlag_relation_avg_leader_excess": _round(
                            rel["avg_leader_excess"], 6
                        ),
                        "leadlag_relation_score": _round(rel["relation_score"], 6),
                        "candidate_avg_dollar_volume_20d": _round(m["adv20"], 2),
                        "candidate_close": _round(m["close"], 4),
                    }
                )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row.get("leadlag_relation_score") or 0.0),
            -float(row["leadlag_diffusion_gap"] or 0.0),
            -float(row["leadlag_leader_excess_ret10"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = len(
        {t for m in industry_members.values() if len(m) >= MIN_INDUSTRY_MEMBERS for t in m}
    )
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "lead_lookback_days": LEAD_LOOKBACK_DAYS,
        "leader_top_k": LEADER_TOP_K,
        "min_industry_members": MIN_INDUSTRY_MEMBERS,
        "min_leader_excess_ret": MIN_LEADER_EXCESS_RET,
        "min_diffusion_gap": MIN_DIFFUSION_GAP,
        "max_candidate_excess_ret": MAX_CANDIDATE_EXCESS_RET,
        "min_candidate_ret": MIN_CANDIDATE_RET,
        "relation_lookback_days": RELATION_LOOKBACK_DAYS,
        "relation_min_obs": RELATION_MIN_OBS,
        "relation_history_min_leader_excess_ret": RELATION_HISTORY_MIN_LEADER_EXCESS_RET,
        "relation_max_history_candidate_excess_ret": RELATION_MAX_HISTORY_CANDIDATE_EXCESS_RET,
        "relation_min_median_fwd_excess": RELATION_MIN_MEDIAN_FWD_EXCESS,
        "relation_min_hit_rate": RELATION_MIN_HIT_RATE,
        "relation_min_score": RELATION_MIN_SCORE,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_intraindustry_lead_lag_direction_stability"
        if gate["passed"]
        else "rejected_intraindustry_lead_lag_direction_stability_candidate_pool"
    )
    return gate


def _load_companyfacts_rows_stub(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    return []


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_companyfacts_rows_stub
    base._load_window_snapshot = _broad_load_window_snapshot
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The PIT intra-industry lead-lag direction-stability source cleared "
            "the numeric three-window replay screen on the broad liquid universe, "
            "but remains only a replay lead because no shared daily/backtest "
            "helper was promoted."
        )
    else:
        by_window = payload["delta_metrics"]["by_window"]
        interpretation = (
            "The PIT intra-industry lead-lag direction-stability source did not "
            "clear Gate 4 (failed: {failed}). The relation gate was intended to "
            "keep only tickers where prior completed leader events predicted "
            "positive 10-day excess return, but the fixed bundle still produced "
            "aggregate EV {ev:+.4f}, PnL ${pnl:+,.2f}, and max drawdown drift "
            "{dd:+.4f}. By window: late_strong dEV {late_ev:+.4f}/dPnL "
            "${late_pnl:+,.2f}; mid_weak dEV {mid_ev:+.4f}/dPnL "
            "${mid_pnl:+,.2f}; old_thin dEV {old_ev:+.4f}/dPnL "
            "${old_pnl:+,.2f}. Economic reading: free-OHLCV lead-lag history is "
            "too noisy as a standalone always-on source; ticker-specific "
            "direction stability does not reliably distinguish diffusion from "
            "leader reversal or persistent laggard weakness across regimes."
        ).format(
            failed=", ".join(gate4["failed_reasons"]) or "none",
            ev=aggregate["expected_value_score_delta_sum"],
            pnl=aggregate["total_pnl_delta_sum"],
            dd=float(aggregate["max_drawdown_delta_max"] or 0.0),
            late_ev=by_window["late_strong"]["expected_value_score"],
            late_pnl=by_window["late_strong"]["total_pnl"],
            mid_ev=by_window["mid_weak"]["expected_value_score"],
            mid_pnl=by_window["mid_weak"]["total_pnl"],
            old_ev=by_window["old_thin"]["expected_value_score"],
            old_pnl=by_window["old_thin"]["total_pnl"],
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_pit_lead_lag_direction_stability",
            "nearby_prior_experiments": [
                "exp-20260617-021",
                "exp-20260607-007",
                "exp-20260608-008",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "lead_lookback_days": LEAD_LOOKBACK_DAYS,
        "leader_top_k": LEADER_TOP_K,
        "min_industry_members": MIN_INDUSTRY_MEMBERS,
        "min_leader_excess_ret": MIN_LEADER_EXCESS_RET,
        "min_diffusion_gap": MIN_DIFFUSION_GAP,
        "max_candidate_excess_ret": MAX_CANDIDATE_EXCESS_RET,
        "min_candidate_ret": MIN_CANDIDATE_RET,
        "relation_lookback_days": RELATION_LOOKBACK_DAYS,
        "relation_min_obs": RELATION_MIN_OBS,
        "relation_history_min_leader_excess_ret": RELATION_HISTORY_MIN_LEADER_EXCESS_RET,
        "relation_max_history_candidate_excess_ret": RELATION_MAX_HISTORY_CANDIDATE_EXCESS_RET,
        "relation_min_median_fwd_excess": RELATION_MIN_MEDIAN_FWD_EXCESS,
        "relation_min_hit_rate": RELATION_MIN_HIT_RATE,
        "relation_min_score": RELATION_MIN_SCORE,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "For each signal date, every liquid broad-universe name's 10-day return "
        "excess vs SPY and 20-day dollar volume are computed from PIT OHLCV. "
        "Within each industry of >=6 liquid members, the top-3 by dollar volume "
        "form the leader basket; an event fires for a non-leader member when "
        "the leader basket median 10d excess is >=+4%, the candidate lags by "
        ">=5pp, the candidate's own 10d excess is <=+2%, and its 10d return is "
        ">=-6%. The candidate must also have at least 8 completed prior "
        "leader-event observations in the prior 180 trading sessions whose "
        "10-day forward outcomes finished before the signal date, with "
        "positive median forward excess, hit rate >=50%, and relation score "
        ">=0.002. Paper entry is the next available open with entry slippage; "
        "exit is the close 10 trading days after the signal with target-side "
        "sell slippage and round-trip costs. The core baseline remains the "
        "canonical core replay; only the candidate snapshot is broad liquid."
    )
    payload["gate2"]["runtime_fields"] = [
        "warehouse OHLCV Date/Open/High/Low/Close/Volume (broad liquid universe)",
        "SPY OHLCV for relative strength",
        "broad_market_sector_map industry/sector membership",
        "derived 10d excess return and 20d dollar volume per ticker",
        "completed pre-signal relation observations and 10d forward excess",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "Do not sweep static lead-lag thresholds on these frozen windows. If "
        "the idea is revisited, require materially new relation provenance "
        "(customer/supplier/product linkage, transfer-entropy edges, or closed "
        "forward replacement rows) or a pre-registered forward live-pilot that "
        "tags regime at entry time without retrofitting the frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping leader-top-K, min-leader-excess, "
            "diffusion-gap, candidate-excess cap, relation lookback, min obs, "
            "hit rate, median-forward threshold, relation-score threshold, "
            "price/ADV floors, top-N, hold days, cooldown, or notional on these "
            "windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} PIT Intra-Industry Lead-Lag Direction Stability",
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
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
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


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
    base.persist_self_registered_result(
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
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
