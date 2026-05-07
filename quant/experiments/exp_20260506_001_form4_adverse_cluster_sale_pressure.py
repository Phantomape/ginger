"""exp-20260506-001: Form 4 adverse cluster sale-pressure de-risk.

Alpha search. This tests one deterministic non-OHLCV discriminator:
large open-market insider sale clusters that are followed by an adverse
SPY-relative reaction. Matching core long entries are de-risked to 0.25x.

The script is replay-only. A passing result is not promoted unless the
feature and sizing multiplier are moved into shared production/backtest
policy with parity coverage.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import feature_layer as fl  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260506-001"
STEM = "form4_adverse_cluster_sale_pressure"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)

FORM4_PATH = REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"

SALE_LOOKBACK_DAYS = 20
SALE_VALUE_MIN_USD = 500_000
CLUSTER_MIN_UNIQUE_OWNERS = 2
POST_SALE_REACTION_DAYS = 3
ADVERSE_EXCESS_RETURN_MAX = -0.02
RISK_MULTIPLIER = 0.25
SIZING_KEY = "form4_adverse_cluster_sale_pressure_risk_multiplier_applied"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])


def _round(value, digits=4):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _is_true(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _pct_change(start, end):
    try:
        start = float(start)
        end = float(end)
    except (TypeError, ValueError):
        return None
    if start <= 0:
        return None
    return (end / start) - 1.0


def _idx_on_or_after(rows: list[dict], target: date) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _load_snapshot_closes(snapshot_path: Path) -> dict[str, list[dict]]:
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    out = {}
    for ticker, rows in (raw.get("ohlcv") or {}).items():
        parsed = []
        for row in rows:
            row_date = _parse_date(row.get("Date"))
            close = row.get("Close")
            if row_date is None or close is None:
                continue
            parsed.append({"date": row_date, "close": float(close)})
        parsed.sort(key=lambda row: row["date"])
        if parsed:
            out[str(ticker).upper()] = parsed
    return out


def _load_sale_clusters():
    raw_rows = 0
    qualified_rows = 0
    roleless_rows = 0
    clusters = {}

    with FORM4_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw_rows += 1
            row = json.loads(line)
            ticker = str(row.get("ticker") or "").upper().strip()
            tx_date = _parse_date(row.get("usable_trade_date") or row.get("transaction_date"))
            try:
                value = float(row.get("transaction_value") or 0)
            except (TypeError, ValueError):
                value = 0.0

            role_flag = any(
                _is_true(row.get(key))
                for key in ("is_officer", "is_director", "is_ten_percent_owner")
            )
            if not role_flag:
                roleless_rows += 1

            if (
                not ticker
                or tx_date is None
                or not _is_true(row.get("pit_safe_flag", True))
                or str(row.get("transaction_code") or "").upper() != "S"
                or str(row.get("acquired_disposed_code") or "").upper() != "D"
                or _is_true(row.get("10b5_1_flag"))
                or _is_true(row.get("option_exercise_flag"))
                or value < SALE_VALUE_MIN_USD
                or not role_flag
            ):
                continue

            qualified_rows += 1
            key = (ticker, tx_date)
            cluster = clusters.setdefault(
                key,
                {
                    "ticker": ticker,
                    "event_date": tx_date,
                    "total_value_usd": 0.0,
                    "transaction_count": 0,
                    "owners": set(),
                    "filings": set(),
                    "officer_sale": False,
                    "director_sale": False,
                    "ten_percent_owner_sale": False,
                },
            )
            cluster["total_value_usd"] += value
            cluster["transaction_count"] += 1
            owner = str(row.get("owner_name") or row.get("reporting_owner") or "").strip()
            if owner:
                cluster["owners"].add(owner)
            filing = str(row.get("accession_number") or row.get("source_url") or "").strip()
            if filing:
                cluster["filings"].add(filing)
            cluster["officer_sale"] = cluster["officer_sale"] or _is_true(row.get("is_officer"))
            cluster["director_sale"] = cluster["director_sale"] or _is_true(row.get("is_director"))
            cluster["ten_percent_owner_sale"] = cluster["ten_percent_owner_sale"] or _is_true(
                row.get("is_ten_percent_owner")
            )

    rows = []
    for cluster in clusters.values():
        owners = sorted(owner for owner in cluster["owners"] if owner)
        filings = sorted(filing for filing in cluster["filings"] if filing)
        rows.append({
            **cluster,
            "owners": owners,
            "filings": filings,
            "owner_count": len(owners),
            "filing_count": len(filings),
        })
    rows.sort(key=lambda row: (row["ticker"], row["event_date"]))
    summary = {
        "source": str(FORM4_PATH.relative_to(REPO_ROOT)),
        "raw_rows": raw_rows,
        "qualified_rows": qualified_rows,
        "aggregated_event_count": len(rows),
        "cluster_event_count": sum(
            1 for row in rows if row["owner_count"] >= CLUSTER_MIN_UNIQUE_OWNERS
        ),
        "qualified_ticker_count": len({row["ticker"] for row in rows}),
        "roleless_rows": roleless_rows,
        "filters": {
            "transaction_code": "S",
            "acquired_disposed_code": "D",
            "pit_safe_flag": True,
            "10b5_1_flag": False,
            "option_exercise_flag": False,
            "transaction_value_min_usd": SALE_VALUE_MIN_USD,
            "cluster_min_unique_owners": CLUSTER_MIN_UNIQUE_OWNERS,
            "post_sale_reaction_trading_days": POST_SALE_REACTION_DAYS,
            "adverse_excess_return_max": ADVERSE_EXCESS_RETURN_MAX,
            "eligible_lookback_calendar_days": SALE_LOOKBACK_DAYS,
            "role_required": "officer/director/10_percent_owner",
        },
    }
    return rows, summary


SALE_CLUSTERS, FORM4_SUMMARY = _load_sale_clusters()


def _build_adverse_cluster_events(snapshot_path: Path):
    closes = _load_snapshot_closes(snapshot_path)
    spy_rows = closes.get("SPY")
    by_ticker = defaultdict(list)
    coverage = {
        "raw_cluster_events": FORM4_SUMMARY["cluster_event_count"],
        "snapshot_ticker_missing": 0,
        "reaction_window_missing": 0,
        "reaction_computed": 0,
        "adverse_cluster_events": 0,
        "adverse_cluster_tickers": 0,
    }
    if not spy_rows:
        coverage["spy_missing"] = True
        return {}, coverage

    for cluster in SALE_CLUSTERS:
        if cluster["owner_count"] < CLUSTER_MIN_UNIQUE_OWNERS:
            continue
        ticker = cluster["ticker"]
        ticker_rows = closes.get(ticker)
        if not ticker_rows:
            coverage["snapshot_ticker_missing"] += 1
            continue
        reaction_idx = _idx_on_or_after(ticker_rows, cluster["event_date"])
        spy_reaction_idx = _idx_on_or_after(spy_rows, cluster["event_date"])
        if (
            reaction_idx is None
            or spy_reaction_idx is None
            or reaction_idx + POST_SALE_REACTION_DAYS >= len(ticker_rows)
            or spy_reaction_idx + POST_SALE_REACTION_DAYS >= len(spy_rows)
        ):
            coverage["reaction_window_missing"] += 1
            continue
        end_idx = reaction_idx + POST_SALE_REACTION_DAYS
        spy_end_idx = spy_reaction_idx + POST_SALE_REACTION_DAYS
        reaction_ret = _pct_change(ticker_rows[reaction_idx]["close"], ticker_rows[end_idx]["close"])
        spy_ret = _pct_change(spy_rows[spy_reaction_idx]["close"], spy_rows[spy_end_idx]["close"])
        if reaction_ret is None or spy_ret is None:
            coverage["reaction_window_missing"] += 1
            continue
        excess_ret = reaction_ret - spy_ret
        coverage["reaction_computed"] += 1
        if excess_ret > ADVERSE_EXCESS_RETURN_MAX:
            continue
        event = {
            "ticker": ticker,
            "event_date": cluster["event_date"],
            "eligible_date": ticker_rows[end_idx]["date"],
            "reaction_return": round(reaction_ret, 6),
            "spy_reaction_return": round(spy_ret, 6),
            "reaction_excess_return": round(excess_ret, 6),
            "total_value_usd": round(float(cluster["total_value_usd"]), 2),
            "transaction_count": int(cluster["transaction_count"]),
            "owner_count": int(cluster["owner_count"]),
            "filing_count": int(cluster["filing_count"]),
            "officer_sale": bool(cluster["officer_sale"]),
            "director_sale": bool(cluster["director_sale"]),
            "ten_percent_owner_sale": bool(cluster["ten_percent_owner_sale"]),
        }
        by_ticker[ticker].append(event)

    for events in by_ticker.values():
        events.sort(key=lambda row: row["eligible_date"])
    coverage["adverse_cluster_events"] = sum(len(events) for events in by_ticker.values())
    coverage["adverse_cluster_tickers"] = len(by_ticker)
    return dict(by_ticker), coverage


def _events_in_window(events_by_ticker, ticker, as_of_date):
    if not ticker or as_of_date is None:
        return []
    start = as_of_date - timedelta(days=SALE_LOOKBACK_DAYS)
    matches = []
    for event in events_by_ticker.get(str(ticker).upper(), []):
        eligible_date = event["eligible_date"]
        if start <= eligible_date <= as_of_date:
            matches.append(event)
        if eligible_date > as_of_date:
            break
    return matches


def _sale_pressure_payload(events_by_ticker, ticker, as_of_date):
    events = _events_in_window(events_by_ticker, ticker, as_of_date)
    if not events:
        return None
    return {
        "lookback_days": SALE_LOOKBACK_DAYS,
        "event_count": len(events),
        "latest_eligible_date": max(event["eligible_date"] for event in events).isoformat(),
        "total_value_usd": round(sum(float(event["total_value_usd"]) for event in events), 2),
        "transaction_count": sum(int(event["transaction_count"]) for event in events),
        "owner_count_max": max(int(event["owner_count"]) for event in events),
        "worst_reaction_excess_return": min(float(event["reaction_excess_return"]) for event in events),
        "officer_sale": any(event["officer_sale"] for event in events),
        "director_sale": any(event["director_sale"] for event in events),
        "ten_percent_owner_sale": any(event["ten_percent_owner_sale"] for event in events),
        "events": [
            {
                "event_date": event["event_date"].isoformat(),
                "eligible_date": event["eligible_date"].isoformat(),
                "total_value_usd": event["total_value_usd"],
                "owner_count": event["owner_count"],
                "transaction_count": event["transaction_count"],
                "reaction_excess_return": event["reaction_excess_return"],
            }
            for event in events
        ],
    }


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _make_compute_features(original_compute_features):
    def compute_features(ticker, ohlcv_data, earnings_data):
        features = original_compute_features(ticker, ohlcv_data, earnings_data)
        if features is None:
            return None
        if ohlcv_data is not None and not ohlcv_data.empty:
            features["as_of_date"] = ohlcv_data.index[-1].date().isoformat()
        return features

    return compute_features


def _make_enricher(original_enrich_signals, events_by_ticker):
    def enrich_signals(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich_signals(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        for sig in enriched:
            ticker = sig.get("ticker")
            features = features_dict.get(ticker) or {}
            as_of_date = _parse_date(features.get("as_of_date"))
            pressure = _sale_pressure_payload(events_by_ticker, ticker, as_of_date)
            if pressure:
                sig["form4_adverse_cluster_sale_pressure"] = pressure
        return enriched

    return enrich_signals


def _make_variant_sizer(original_size_signals):
    def size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if not sig.get("form4_adverse_cluster_sale_pressure"):
                continue
            sizing = sig.get("sizing") or {}
            if (sizing.get("shares_to_buy") or 0) <= 0:
                continue
            entry = sig.get("entry_price")
            stop = sig.get("stop_price")
            current_risk_pct = sizing.get("risk_pct")
            if not entry or not stop or current_risk_pct is None:
                continue
            new_sizing = pe.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=float(current_risk_pct) * RISK_MULTIPLIER,
                max_position_pct=sizing.get("max_position_pct_applied") or pe.MAX_POSITION_PCT,
            )
            if not new_sizing:
                continue
            for key, value in sizing.items():
                if key not in new_sizing:
                    new_sizing[key] = value
            new_sizing["risk_pct"] = float(current_risk_pct) * RISK_MULTIPLIER
            new_sizing[SIZING_KEY] = RISK_MULTIPLIER
            sig["sizing"] = new_sizing
        return sized

    return size_signals


def _run_window(window: dict, variant_enabled: bool = False) -> dict:
    snapshot_path = REPO_ROOT / window["snapshot"]
    events_by_ticker, coverage = _build_adverse_cluster_events(snapshot_path)
    original_compute_features = fl.compute_features
    original_enrich_signals = re.enrich_signals
    original_size_signals = pe.size_signals
    fl.compute_features = _make_compute_features(original_compute_features)
    re.enrich_signals = _make_enricher(original_enrich_signals, events_by_ticker)
    if variant_enabled:
        pe.size_signals = _make_variant_sizer(original_size_signals)
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(snapshot_path),
        )
        result = engine.run()
        result["form4_adverse_cluster_source_summary"] = {
            **FORM4_SUMMARY,
            "window_event_coverage": coverage,
        }
        return result
    finally:
        fl.compute_features = original_compute_features
        re.enrich_signals = original_enrich_signals
        pe.size_signals = original_size_signals


def _delta(before: dict, after: dict) -> dict:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
        "signals_generated",
        "signals_survived",
    )
    return {key: _round((after.get(key) or 0) - (before.get(key) or 0), 6) for key in keys}


def _touched_trade_attribution(result: dict) -> dict:
    rows = []
    for trade in result.get("trades") or []:
        sizing = trade.get("sizing_multipliers") or {}
        if sizing.get(SIZING_KEY) is not None:
            rows.append(trade)
    return {
        "trade_count": len(rows),
        "wins": sum(1 for row in rows if (row.get("pnl") or 0) > 0),
        "losses": sum(1 for row in rows if (row.get("pnl") or 0) <= 0),
        "total_pnl_usd": _round(sum(row.get("pnl") or 0 for row in rows), 2),
        "trades": [
            {
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "pnl": _round(row.get("pnl"), 2),
                "exit_reason": row.get("exit_reason"),
                "sizing_multipliers": row.get("sizing_multipliers") or {},
            }
            for row in rows
        ],
    }


def _aggregate(rows: dict) -> dict:
    baseline_ev = sum(float(row["before"]["expected_value_score"] or 0) for row in rows.values())
    baseline_pnl = sum(float(row["before"]["total_pnl"] or 0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0) for row in rows.values())
    return {
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / baseline_ev if baseline_ev else 0, 6),
        "baseline_expected_value_score_sum": _round(baseline_ev, 6),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "baseline_total_pnl_sum": _round(baseline_pnl, 2),
        "total_pnl_delta_pct": _round(pnl_delta / baseline_pnl if baseline_pnl else 0, 6),
        "ev_windows_improved": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for row in rows.values() if row["delta"]["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for row in rows.values() if row["delta"]["total_pnl"] < 0),
        "max_drawdown_delta_min": _round(min(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6),
        "max_drawdown_delta_max": _round(max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in rows.values()),
        "win_rate_delta_min": _round(min(row["delta"]["win_rate"] for row in rows.values()), 6),
        "sharpe_daily_delta_max": _round(max(row["delta"]["sharpe_daily"] for row in rows.values()), 6),
        "touched_trades_after": sum(
            row["touched_trade_attribution_after"]["trade_count"] for row in rows.values()
        ),
        "touched_trades_pnl_after": _round(
            sum(row["touched_trade_attribution_after"]["total_pnl_usd"] or 0 for row in rows.values()),
            2,
        ),
    }


def _gate4_passed(aggregate: dict) -> bool:
    material = (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["sharpe_daily_delta_max"] > 0.10
        or aggregate["max_drawdown_delta_min"] < -1.0
        or aggregate["total_pnl_delta_pct"] > 0.05
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return (
        material
        and aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
    )


def _build_payload(rows, aggregate, accepted, generated_at):
    decision = "accepted_shadow_not_promoted" if accepted else "rejected"
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            "Adverse Form 4 sale-cluster de-risking did not clear three-window "
            "Gate 4. The discriminator either did not touch enough core winners "
            "and losers to matter, or it reduced replacement-value quality under "
            "the current core stack."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "deterministic_event_overlay_entry_allocation",
        "mechanism_family": "form4_adverse_cluster_sale_pressure_long_entry_derisk",
        "hypothesis": (
            "Large non-10b5, non-option Form 4 sale clusters that are followed by "
            "an adverse SPY-relative reaction may identify core long entries with "
            "poorer forward replacement value; reducing their risk to 0.25x should "
            "improve multi-window EV without adding noisy tickers."
        ),
        "alpha_hypothesis": {
            "category": "allocation",
            "entry_exit_ranking_or_allocation": "allocation",
            "why_this_now": (
                "LLM soft-ranking is sample-limited, event-bundle live promotion "
                "awaits closed forward outcomes, and broad universe expansion has "
                "been rejected. This uses PIT Form 4 data and a price-confirmed "
                "negative event discriminator instead of another ticker basket."
            ),
        },
        "mechanism_insight_check": {
            "recent_bans_avoided": [
                "no raw AI infrastructure ticker promotion",
                "no simple Form 4 sale-pressure threshold/lookback retry",
                "no event-bundle delayed-entry gate",
                "no noisy broad watchlist expansion",
                "no LLM soft-ranking experiment without aligned samples",
            ],
            "why_not_simple_repeat": (
                "exp-20260505-010 rejected simple sale-pressure de-risking and "
                "explicitly required a new discriminator such as cluster selling "
                "or adverse price reaction. This test requires both a sale cluster "
                "and an adverse 3-trading-day SPY-relative reaction."
            ),
        },
        "parameters": {
            "single_causal_variable": "enable adverse cluster sale-pressure de-risk overlay",
            "risk_multiplier": RISK_MULTIPLIER,
            "sale_value_min_usd": SALE_VALUE_MIN_USD,
            "cluster_min_unique_owners": CLUSTER_MIN_UNIQUE_OWNERS,
            "post_sale_reaction_trading_days": POST_SALE_REACTION_DAYS,
            "adverse_excess_return_max": ADVERSE_EXCESS_RETURN_MAX,
            "eligible_lookback_calendar_days": SALE_LOOKBACK_DAYS,
            "baseline_behavior": "core A/B entries are not de-risked by Form 4 sale clusters",
            "locked_variables": [
                "universe",
                "entry rules",
                "exit rules",
                "candidate ordering",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "sector rules",
                "earnings rules",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "snapshots": {label: w["snapshot"] for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "before_metrics": {label: row["before"] for label, row in rows.items()},
        "after_metrics": {label: row["after"] for label, row in rows.items()},
        "delta_metrics": {
            "by_window": {label: row["delta"] for label, row in rows.items()},
            **aggregate,
        },
        "window_source_coverage": {
            label: row["source_coverage_after"] for label, row in rows.items()
        },
        "touched_trade_attribution_after": {
            label: row["touched_trade_attribution_after"] for label, row in rows.items()
        },
        "gate4": {
            "passed": accepted,
            "basis": (
                "Gate4 requires >10% aggregate EV lift, >0.1 Sharpe lift, >1pp "
                "drawdown reduction, >5% PnL lift, or more trades without win-rate "
                "decline. A retained alpha change must also improve EV in a majority "
                "of the three fixed windows with no EV-regressed window."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If this shadow result is promoted later, the Form 4 event feature "
                "and sizing multiplier must be implemented in shared production/"
                "backtest policy and exposed in run.py outputs before enabling."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "blocker_relation": (
                "This run did not treat the LLM as the problem. It avoided the "
                "sample-limited LLM soft-ranking lane and tested another alpha source."
            ),
        },
        "form4_source_summary": FORM4_SUMMARY,
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "Do not retry simple sale-pressure de-risking or nearby threshold/lookback changes.",
            "A valid retry needs a larger touched core-signal cohort, role-specific evidence such as CEO/CFO selling, or closed forward replacement-value evidence.",
            "Any positive promotion requires shared production/backtest policy plus parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260506_001_form4_adverse_cluster_sale_pressure.py",
        ],
    }


def _write_artifact(payload):
    delta = payload["delta_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} Form 4 adverse cluster sale-pressure",
        "",
        f"Status: {payload['decision']}",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- passed: {payload['gate4']['passed']}",
        f"- aggregate_ev_delta_sum: {delta['expected_value_score_delta_sum']}",
        f"- aggregate_ev_delta_pct: {delta['expected_value_score_delta_pct']}",
        f"- aggregate_pnl_delta_sum: {delta['total_pnl_delta_sum']}",
        f"- touched_trades_after: {delta['touched_trades_after']}",
        f"- touched_trades_pnl_after: {delta['touched_trades_pnl_after']}",
        "",
        "## Fixed Windows",
        "",
    ]
    for label in WINDOWS:
        lines.extend([
            f"### {label}",
            "",
            f"- before: {payload['before_metrics'][label]}",
            f"- after: {payload['after_metrics'][label]}",
            f"- delta: {payload['delta_metrics']['by_window'][label]}",
            f"- source_coverage: {payload['window_source_coverage'][label]}",
            f"- touched_trade_attribution_after: {payload['touched_trade_attribution_after'][label]}",
            "",
        ])
    if payload["rejection_reason"]:
        lines.extend(["## Rejection Reason", "", payload["rejection_reason"], ""])
    lines.extend([
        "## Production Parity",
        "",
        str(payload["production_impact"]),
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _write_outputs(payload):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "status": payload["decision"],
        "decision": payload["decision"],
        "title": "Form 4 adverse cluster sale-pressure",
        "summary": f"Gate4={payload['gate4']['passed']}; touched_trades={payload['delta_metrics']['touched_trades_after']}",
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_artifact(payload)


def main() -> int:
    import backtester as bt

    if SIZING_KEY not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (*bt.SIZING_MULTIPLIER_KEYS, SIZING_KEY)

    rows = OrderedDict()
    for label, window in WINDOWS.items():
        before_result = _run_window(window, variant_enabled=False)
        after_result = _run_window(window, variant_enabled=True)
        before = _metrics(before_result)
        after = _metrics(after_result)
        rows[label] = {
            "window": window,
            "before": before,
            "after": after,
            "delta": _delta(before, after),
            "source_coverage_before": before_result["form4_adverse_cluster_source_summary"]["window_event_coverage"],
            "source_coverage_after": after_result["form4_adverse_cluster_source_summary"]["window_event_coverage"],
            "touched_trade_attribution_after": _touched_trade_attribution(after_result),
        }

    aggregate = _aggregate(rows)
    accepted = _gate4_passed(aggregate)
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = _build_payload(rows, aggregate, accepted, generated_at)
    _write_outputs(payload)

    print(f"{EXPERIMENT_ID} {payload['decision']}")
    print(json.dumps(payload["delta_metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
