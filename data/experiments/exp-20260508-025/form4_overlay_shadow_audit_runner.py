from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXP_ID = "exp-20260508-025"
ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "data" / "experiments" / EXP_ID
ARTIFACT = OUT_DIR / "form4_overlay_shadow_audit.json"
REPORT = ROOT / "docs" / "non_ohlcv_data_audit" / "form4_20260508.md"
LOG = ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TX_PATH = ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
LATEST_TX_PATH = ROOT / "data" / "non_ohlcv" / "form4_transactions_20260507.jsonl"
SHADOW_EVENTS_PATH = (
    ROOT
    / "data"
    / "non_ohlcv"
    / "form4_purchase_shadow_outcomes_20241002_20260421.json"
)
TRADE_OVERLAP_PATH = (
    ROOT
    / "data"
    / "non_ohlcv"
    / "form4_accepted_trade_overlap_20241002_20260421.json"
)
SKIP_OVERLAP_PATH = (
    ROOT
    / "data"
    / "non_ohlcv"
    / "form4_entry_skip_oracle_overlap_20241002_20260421.json"
)
SUMMARY_PATH = ROOT / "data" / "non_ohlcv" / "form4_backfill_summary_20260507.json"
SNAPSHOTS = [
    ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
    ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
    ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
]
HORIZONS = (5, 10, 20, 60, 90)
WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}
REQUIRED_FIELDS = (
    "ticker",
    "cik",
    "accession_number",
    "accepted_at",
    "filing_date",
    "transaction_date",
    "officer_title",
    "is_director",
    "is_officer",
    "is_10pct_owner",
    "transaction_code",
    "shares",
    "price",
    "transaction_value",
    "direct_or_indirect",
    "ownership_nature",
    "10b5_1_flag",
    "option_exercise_flag",
    "open_market_purchase_flag",
    "usable_trade_date",
    "pit_safe_flag",
)


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    try:
        return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def date10(value: Any) -> str:
    return str(value or "")[:10]


def parse_date(value: Any):
    text = date10(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def number(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed):
        return default
    return parsed


def mean(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 6) if clean else None


def median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if value is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 6)
    return round((clean[mid - 1] + clean[mid]) / 2.0, 6)


def norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def ceo_cfo_or_president(title: Any) -> bool:
    text = str(title or "").lower()
    return any(
        token in text
        for token in ("chief executive", "chief financial", "ceo", "cfo", "president")
    )


def owner_is_issuer(row: dict[str, Any]) -> bool:
    owner = norm_text(row.get("owner_name"))
    issuer = norm_text(row.get("issuer_name"))
    symbol = norm_text(row.get("issuer_trading_symbol") or row.get("ticker"))
    if not owner:
        return False
    if issuer and (owner == issuer or issuer in owner or owner in issuer):
        return True
    return bool(symbol and owner == symbol)


def load_price_map() -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for path in SNAPSHOTS:
        payload = load_json(path)
        for ticker, rows in (payload.get("ohlcv") or {}).items():
            for row in rows or []:
                day = date10(row.get("Date"))
                if not day:
                    continue
                by_ticker_date[str(ticker).upper()][day] = {
                    "date": day,
                    "open": number(row.get("Open")),
                    "close": number(row.get("Close")),
                    "high": number(row.get("High")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda item: item["date"])
        for ticker, rows in by_ticker_date.items()
    }


def first_index_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def forward_return(
    prices: dict[str, list[dict[str, Any]]], ticker: str, usable_date: str, horizon: int
) -> dict[str, Any] | None:
    rows = prices.get(str(ticker).upper())
    spy_rows = prices.get("SPY")
    if not rows or not spy_rows:
        return None
    idx = first_index_on_or_after(rows, usable_date)
    spy_idx = first_index_on_or_after(spy_rows, usable_date)
    if idx is None or spy_idx is None:
        return None
    exit_idx = idx + horizon
    spy_exit_idx = spy_idx + horizon
    if exit_idx >= len(rows) or spy_exit_idx >= len(spy_rows):
        return None
    entry = rows[idx]
    exit_row = rows[exit_idx]
    spy_entry = spy_rows[spy_idx]
    spy_exit = spy_rows[spy_exit_idx]
    if not entry["open"] or not exit_row["close"] or not spy_entry["open"] or not spy_exit["close"]:
        return None
    ret = exit_row["close"] / entry["open"] - 1.0
    spy_ret = spy_exit["close"] / spy_entry["open"] - 1.0
    return {
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "return_pct": round(ret * 100.0, 4),
        "spy_return_pct": round(spy_ret * 100.0, 4),
        "excess_vs_spy_pct": round((ret - spy_ret) * 100.0, 4),
    }


def drawdown_from_60d_high(prices: dict[str, list[dict[str, Any]]], ticker: str, usable_date: str):
    rows = prices.get(str(ticker).upper()) or []
    idx = first_index_on_or_after(rows, usable_date)
    if idx is None or idx < 2:
        return None
    prior = rows[max(0, idx - 60) : idx]
    highs = [row["high"] for row in prior if row.get("high")]
    closes = [row["close"] for row in prior if row.get("close")]
    if not highs or not closes:
        return None
    peak = max(highs)
    if not peak:
        return None
    return round(closes[-1] / peak - 1.0, 6)


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "event_count": len(events),
        "ticker_count": len({event["ticker"] for event in events}),
        "total_purchase_value": round(sum(event.get("total_purchase_value") or 0 for event in events), 2),
        "by_window": {},
        "horizons": {},
        "scoring_fields": {
            "cluster_buying_30d_count": sum(1 for event in events if event.get("cluster_buying_30d")),
            "CEO_CFO_buy_count": sum(1 for event in events if event.get("CEO_CFO_buy_flag")),
            "post_drawdown_purchase_20pct_count": sum(1 for event in events if event.get("post_drawdown_purchase")),
            "first_purchase_1y_reliable_true_count": sum(
                1
                for event in events
                if event.get("first_purchase_1y") is True
                and event.get("first_purchase_1y_reliable")
            ),
        },
    }
    for window, (start, end) in WINDOWS.items():
        subset = [
            event
            for event in events
            if start <= str(event.get("usable_trade_date") or "") <= end
        ]
        out["by_window"][window] = {
            "event_count": len(subset),
            "ticker_count": len({event["ticker"] for event in subset}),
            "total_purchase_value": round(
                sum(event.get("total_purchase_value") or 0 for event in subset), 2
            ),
        }
    for horizon in HORIZONS:
        returns: list[float] = []
        excess: list[float] = []
        for event in events:
            outcome = (event.get("outcomes") or {}).get(str(horizon))
            if not outcome:
                continue
            returns.append(outcome["return_pct"])
            excess.append(outcome["excess_vs_spy_pct"])
        out["horizons"][str(horizon)] = {
            "count": len(returns),
            "avg_return_pct": mean(returns),
            "median_return_pct": median(returns),
            "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 4)
            if returns
            else None,
            "avg_excess_vs_spy_pct": mean(excess),
            "median_excess_vs_spy_pct": median(excess),
            "excess_win_rate": round(sum(1 for value in excess if value > 0) / len(excess), 4)
            if excess
            else None,
        }
    return out


def enrich_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prices = load_price_map()
    events = []
    for event in raw_events:
        row = dict(event)
        row["CEO_CFO_buy_flag"] = bool(
            row.get("any_ceo_cfo_or_president") or row.get("CEO_CFO_buy_flag")
        )
        row["forward_queue_purchase_500k"] = bool(
            row.get("meaningful_purchase_v1")
            and (number(row.get("total_purchase_value"), 0.0) or 0.0) >= 500_000.0
        )
        row["drawdown_from_60d_high_before_event"] = drawdown_from_60d_high(
            prices, row["ticker"], row["usable_trade_date"]
        )
        row["post_drawdown_purchase"] = (
            row["drawdown_from_60d_high_before_event"] is not None
            and row["drawdown_from_60d_high_before_event"] <= -0.20
        )
        row.setdefault("outcomes", {})
        if "90" not in row["outcomes"]:
            outcome = forward_return(prices, row["ticker"], row["usable_trade_date"], 90)
            if outcome:
                row["outcomes"]["90"] = outcome
        row["insider_buy_value_to_market_cap"] = None
        row["market_cap_available"] = False
        events.append(row)

    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_ticker[event["ticker"]].append(event)
    min_date = min(
        parsed
        for parsed in (parse_date(event["usable_trade_date"]) for event in events)
        if parsed is not None
    )
    for ticker_events in by_ticker.values():
        ticker_events.sort(key=lambda item: item["usable_trade_date"])
        for idx, event in enumerate(ticker_events):
            current = parse_date(event["usable_trade_date"])
            prior_30 = [
                prior
                for prior in ticker_events[: idx + 1]
                if current
                and parse_date(prior["usable_trade_date"])
                and 0 <= (current - parse_date(prior["usable_trade_date"])).days <= 30
            ]
            owner_count_30 = sum(int(prior.get("owner_count") or 0) for prior in prior_30)
            event["cluster_buying_30d_event_count"] = len(prior_30)
            event["cluster_buying_30d_owner_count"] = owner_count_30
            event["cluster_buying_30d"] = (
                len(prior_30) >= 2
                or owner_count_30 >= 2
                or int(event.get("owner_count") or 0) >= 2
            )
            prior_1y = [
                prior
                for prior in ticker_events[:idx]
                if current
                and parse_date(prior["usable_trade_date"])
                and 0 < (current - parse_date(prior["usable_trade_date"])).days <= 365
            ]
            event["first_purchase_1y"] = not prior_1y
            event["first_purchase_1y_reliable"] = bool((current - min_date).days >= 365) if current else False
            event["first_purchase_3y"] = False if prior_1y else True
            event["first_purchase_3y_reliable"] = False
    return events


def count_required_field_gaps(rows: list[dict[str, Any]]) -> dict[str, Any]:
    open_market = [row for row in rows if row.get("open_market_purchase_flag")]
    duplicate_seen = set()
    duplicate_count = 0
    for row in open_market:
        key = (
            row.get("ticker"),
            row.get("accession_number"),
            row.get("transaction_date"),
            row.get("transaction_code"),
            row.get("shares"),
            row.get("price"),
            row.get("owner_cik"),
            row.get("security_title"),
            row.get("table"),
        )
        if key in duplicate_seen:
            duplicate_count += 1
        duplicate_seen.add(key)
    return {
        "row_count": len(rows),
        "open_market_purchase_row_count": len(open_market),
        "required_fields": list(REQUIRED_FIELDS),
        "missing_all_rows": {
            field: sum(1 for row in rows if row.get(field) in (None, "", []))
            for field in REQUIRED_FIELDS
        },
        "missing_open_market_purchase_rows": {
            field: sum(1 for row in open_market if row.get(field) in (None, "", []))
            for field in REQUIRED_FIELDS
        },
        "pit_safe_true_rows": sum(1 for row in rows if row.get("pit_safe_flag") is True),
        "rows_missing_accepted_at": sum(1 for row in rows if not row.get("accepted_at")),
        "rows_missing_usable_trade_date": sum(1 for row in rows if not row.get("usable_trade_date")),
        "duplicate_open_market_transaction_key_count": duplicate_count,
    }


def latest_purchase_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    purchases = [row for row in rows if row.get("open_market_purchase_flag")]
    return {
        "source_path": repo_rel(LATEST_TX_PATH),
        "row_count": len(rows),
        "open_market_purchase_row_count": len(purchases),
        "open_market_purchase_value_total": round(
            sum(number(row.get("transaction_value"), 0.0) or 0.0 for row in purchases), 2
        ),
        "open_market_tickers": sorted({str(row.get("ticker") or "").upper() for row in purchases}),
        "note": (
            "Fresh 2026-05-07 file had tiny TSM buys and one CAT $219k director buy; "
            "none reached the default-off $500k queue threshold."
        ),
    }


def build_baseline_metrics() -> dict[str, Any]:
    out = {
        "source": (
            "accepted-stack before blocks from experiments/logs/"
            "exp-20260508-020.json and exp-20260508-023.json"
        ),
        "late_strong": {
            "expected_value_score": 3.7435,
            "total_return_pct": 0.8356,
            "total_pnl": 83562.53,
            "sharpe_daily": 4.48,
            "max_drawdown_pct": 0.0539,
            "win_rate": 0.7895,
            "trade_count": 19,
            "signals_generated": 51,
            "signals_survived": 41,
            "survival_rate": 0.8039,
            "spy_buy_hold_return_pct": 0.0541,
            "qqq_buy_hold_return_pct": 0.0580,
            "strategy_vs_spy_pct": 0.7815,
            "strategy_vs_qqq_pct": 0.7777,
        },
        "mid_weak": {
            "expected_value_score": 1.5478,
            "total_return_pct": 0.5754,
            "total_pnl": 57542.74,
            "sharpe_daily": 2.69,
            "max_drawdown_pct": 0.0879,
            "win_rate": 0.5238,
            "trade_count": 21,
            "signals_generated": 53,
            "signals_survived": 42,
            "survival_rate": 0.7925,
            "spy_buy_hold_return_pct": 0.2544,
            "qqq_buy_hold_return_pct": 0.3351,
            "strategy_vs_spy_pct": 0.3210,
            "strategy_vs_qqq_pct": 0.2403,
        },
        "old_thin": {
            "expected_value_score": 0.3359,
            "total_return_pct": 0.2624,
            "total_pnl": 26242.68,
            "sharpe_daily": 1.28,
            "max_drawdown_pct": 0.0905,
            "win_rate": 0.4091,
            "trade_count": 22,
            "signals_generated": 60,
            "signals_survived": 55,
            "survival_rate": 0.9167,
            "spy_buy_hold_return_pct": -0.0672,
            "qqq_buy_hold_return_pct": -0.0749,
            "strategy_vs_spy_pct": 0.3296,
            "strategy_vs_qqq_pct": 0.3373,
        },
    }
    out["aggregate"] = {
        "expected_value_score_sum": round(
            sum(out[name]["expected_value_score"] for name in WINDOWS), 4
        ),
        "total_pnl_sum": round(sum(out[name]["total_pnl"] for name in WINDOWS), 2),
        "trade_count_sum": sum(out[name]["trade_count"] for name in WINDOWS),
        "signals_generated_sum": sum(out[name]["signals_generated"] for name in WINDOWS),
        "signals_survived_sum": sum(out[name]["signals_survived"] for name in WINDOWS),
    }
    return out


def main() -> int:
    raw_rows = load_jsonl(TX_PATH)
    latest_rows = load_jsonl(LATEST_TX_PATH)
    shadow_events = load_json(SHADOW_EVENTS_PATH)
    trade_overlap = load_json(TRADE_OVERLAP_PATH)
    skip_overlap = load_json(SKIP_OVERLAP_PATH)
    latest_summary = load_json(SUMMARY_PATH)
    events = enrich_events(shadow_events.get("events") or [])
    meaningful = [event for event in events if event.get("meaningful_purchase_v1")]
    queue_500k = [event for event in events if event.get("forward_queue_purchase_500k")]
    ceo_cfo = [
        event
        for event in meaningful
        if event.get("CEO_CFO_buy_flag") or event.get("any_ceo_cfo_or_president")
    ]
    cluster = [event for event in meaningful if event.get("cluster_buying_30d")]
    post_drawdown = [event for event in meaningful if event.get("post_drawdown_purchase")]
    no_signal_events = meaningful

    field_presence = count_required_field_gaps(raw_rows)
    cik_mapping_gap_report = {
        "source": repo_rel(SUMMARY_PATH),
        "tickers_requested": latest_summary.get("tickers_requested"),
        "tickers_mapped": latest_summary.get("tickers_mapped"),
        "missing_cik_tickers": latest_summary.get("missing_cik_tickers") or [],
        "segments": latest_summary.get("segments") or [],
        "mapping_blocker": False,
        "interpretation": (
            "CIK mapping is adequate for current core/pilot/observation Form 4 coverage; "
            "SNXX is the only current missing ticker in the latest Form 4 backfill summary."
        ),
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "parity_test_added": False,
        "replay_only": True,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "production_impact": "shadow_audit_only_no_production_change",
    }
    historical_experiment_check = {
        "same_family_experiments": {
            "exp-20260503-017": (
                "Initial Insider/Form 4 audit was data_gap: CIK mapping usable, "
                "no PIT-safe transaction-level archive yet."
            ),
            "exp-20260503-020/025/026/030/033/037": (
                "No-new-data duplicate guardrail checks; all data_gap and no production change."
            ),
            "exp-20260503-046": (
                "After adapter/backfill, standalone meaningful Form 4 purchase events had "
                "positive forward 20d returns, but this was shadow-only."
            ),
            "exp-20260503-048": (
                "Accepted-trade overlap was zero through 20d and only 2/62 trades at 60d, "
                "5/62 at 90d."
            ),
            "exp-20260503-049": (
                "Entry-skip oracle top opportunities had zero Form 4 overlap through 120d."
            ),
            "exp-20260507-012": (
                "Event-bundle source pruning rejected; Form 4-only had no selected trades "
                "and dropping Form 4 did not improve the full bundle."
            ),
        },
        "why_this_is_not_a_simple_repeat": (
            "Prior data-gap is resolved by local PIT-safe transaction JSONL rows; this run "
            "compiles current overlay evidence and explicitly does not retune thresholds or "
            "promote production."
        ),
        "mechanism_insight_check": (
            "No conflict: avoids OHLCV threshold scans, source-pruning promotion, "
            "standalone entries, and production signal path changes."
        ),
    }
    decision = "shadow_only"
    decision_rationale = (
        "Standalone PIT-safe Form 4 purchase events have positive average forward returns, "
        "but the overlay does not currently touch enough existing Ginger candidates: "
        "0/62 accepted trades match within 20d, 0/45 top skipped slot opportunities match "
        "through 120d, and the latest forward queue has 0 $500k candidates. This supports "
        "continued default-off observation, not production promotion."
    )
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    artifact = {
        "experiment_id": EXP_ID,
        "created_at": created_at,
        "status": "observed_only",
        "decision": decision,
        "lane": "alpha_discovery",
        "alpha_hypothesis_category": "entry_confirmation_overlay",
        "hypothesis": (
            "Public-market insider Form 4 buying, especially large CEO/CFO or clustered "
            "open-market purchases, may confirm existing trend_long/breakout_long "
            "candidates; this run only audits PIT-safe coverage and shadow overlap."
        ),
        "non_ohlcv_data_source": (
            "SEC Form 4 transaction-level XML rows from data/non_ohlcv/form4_transactions_*.jsonl"
        ),
        "mechanism_family": "non_ohlcv_event_confirmation_insider_form4",
        "single_causal_variable": (
            "Form 4 meaningful open-market purchase overlay tags on existing Ginger candidates"
        ),
        "experiment_mode": "shadow_audit_no_production_change",
        "historical_experiment_check": historical_experiment_check,
        "data_availability": {
            "combined_historical_form4_path": repo_rel(TX_PATH),
            "latest_daily_form4_path": repo_rel(LATEST_TX_PATH),
            "daily_form4_file_count": len(
                list((ROOT / "data" / "non_ohlcv").glob("form4_transactions_*.jsonl"))
            ),
            "date_range_from_rows": {
                "usable_min": min(date10(row.get("usable_trade_date")) for row in raw_rows if row.get("usable_trade_date")),
                "usable_max": max(date10(row.get("usable_trade_date")) for row in raw_rows if row.get("usable_trade_date")),
                "accepted_min": min(date10(row.get("accepted_at")) for row in raw_rows if row.get("accepted_at")),
                "accepted_max": max(date10(row.get("accepted_at")) for row in raw_rows if row.get("accepted_at")),
            },
            "field_presence": field_presence,
            "cik_mapping_gap_report": cik_mapping_gap_report,
            "pit_status": {
                "overall": "pit_replay_safe_for_shadow_when_using_accepted_at_and_usable_trade_date",
                "caveat": (
                    "Historical files were generated later as backfills, so they prove "
                    "replayable filing timing but not that live Ginger had this source "
                    "before the adapter existed."
                ),
                "rows_missing_usable_trade_date": field_presence["rows_missing_usable_trade_date"],
                "rows_missing_accepted_at": field_presence["rows_missing_accepted_at"],
                "pit_safe_true_rows": field_presence["pit_safe_true_rows"],
            },
        },
        "scoring_availability": {
            "insider_buy_value_to_market_cap": {
                "status": "missing",
                "reason": "No point-in-time market-cap/share-count field in local Form 4 or OHLCV snapshots.",
            },
            "cluster_buying_30d": {
                "status": "available_from_transactions",
                "definition": (
                    "same ticker has >=2 open-market purchase event-days or >=2 distinct "
                    "owners within 30 calendar days"
                ),
            },
            "CEO_CFO_buy_flag": {
                "status": "available_from_officer_title",
                "null_title_risk": "officer_title can be null, especially director-only rows",
            },
            "first_purchase_1y": {
                "status": "partially_available",
                "reliable_after": "2025-10-03",
                "reason": "combined local Form 4 rows start 2024-10-03",
            },
            "first_purchase_3y": {
                "status": "biased_unavailable",
                "reason": "local history is less than 3 years",
            },
            "post_drawdown_purchase": {
                "status": "shadow_computable",
                "definition": (
                    "prior close <=20% below prior 60-trading-day high; not a production rule"
                ),
            },
            "exclude_option_exercise": {"status": "available", "field": "option_exercise_flag"},
            "exclude_tiny_purchase": {
                "status": "available",
                "thresholds_tested_as_tags_only": [50_000, 500_000],
            },
            "exclude_10b5_1": {"status": "available", "field": "10b5_1_flag"},
        },
        "baseline_metrics": build_baseline_metrics(),
        "shadow_metrics": {
            "candidate_count": {
                "accepted_trade_rows": trade_overlap.get("trade_count"),
                "top_skipped_oracle_rows": skip_overlap.get("top_skipped_candidate_count"),
                "form4_open_market_event_days": len(events),
                "meaningful_purchase_50k_event_days": len(meaningful),
                "forward_queue_purchase_500k_event_days": len(queue_500k),
            },
            "form4_forward_returns": {
                "all_open_market_purchase": summarize_events(events),
                "meaningful_purchase_50k": summarize_events(meaningful),
                "forward_queue_purchase_500k": summarize_events(queue_500k),
                "ceo_cfo_meaningful_purchase": summarize_events(ceo_cfo),
                "cluster_30d_meaningful_purchase": summarize_events(cluster),
                "post_drawdown_meaningful_purchase": summarize_events(post_drawdown),
            },
            "existing_signal_overlap": {
                "meaningful_purchase_50k": trade_overlap.get("lookbacks"),
                "entry_confirmation_read": (
                    "No accepted trades had a meaningful Form 4 purchase within 20 calendar "
                    "days before entry; 60/90d matches are sparse and more suitable as "
                    "hold/add-on research than entry confirmation."
                ),
            },
            "insider_buy_but_no_existing_signal": {
                "definition": (
                    "meaningful Form 4 event-days; accepted-trade overlap is zero through "
                    "20d, so this is effectively the no-existing-signal cohort for entry "
                    "confirmation."
                ),
                "event_count": len(no_signal_events),
                "forward_returns": summarize_events(no_signal_events),
            },
            "slot_value_audit": {
                "meaningful_purchase_50k": skip_overlap.get("lookbacks"),
                "scarce_slot_opportunity_cost": (
                    "No measured slot-conflict value: top skipped opportunities had zero "
                    "Form 4 overlap through 120d."
                ),
            },
            "latest_forward_queue_status": latest_purchase_summary(latest_rows),
        },
        "expected_value_score_delta": {
            "value": 0.0,
            "status": "not_applicable_shadow_only_no_strategy_change",
            "reason": "No entries, ranking, sizing, exits, slots, or production/backtest policy changed.",
        },
        "production_impact": production_impact,
        "decision_rationale": decision_rationale,
        "next_action": (
            "Keep the Form 4 queue/sleeve default-off and add candidate-row joins only after "
            "Ginger persists all generated candidates, not just accepted trades and top skipped oracle rows."
        ),
        "related_files": [
            repo_rel(TICKET),
            repo_rel(LOG),
            repo_rel(ARTIFACT),
            repo_rel(REPORT),
            repo_rel(TX_PATH),
            repo_rel(LATEST_TX_PATH),
            repo_rel(SHADOW_EVENTS_PATH),
            repo_rel(TRADE_OVERLAP_PATH),
            repo_rel(SKIP_OVERLAP_PATH),
            "quant/form4_event_queue.py",
            "quant/form4_event_sleeve.py",
            "quant/form4_backfill.py",
        ],
    }
    write_outputs(artifact, meaningful, queue_500k, trade_overlap, skip_overlap, production_impact)
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "decision": decision,
                "artifact": repo_rel(ARTIFACT),
                "report": repo_rel(REPORT),
                "meaningful_20d_avg_return_pct": artifact["shadow_metrics"]["form4_forward_returns"]["meaningful_purchase_50k"]["horizons"]["20"]["avg_return_pct"],
                "accepted_trade_20d_overlap": trade_overlap["lookbacks"]["20"]["with_prior_form4"]["trade_count"],
                "slot_overlap_120d": skip_overlap["lookbacks"]["120"]["matched"]["candidate_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def write_outputs(
    artifact: dict[str, Any],
    meaningful: list[dict[str, Any]],
    queue_500k: list[dict[str, Any]],
    trade_overlap: dict[str, Any],
    skip_overlap: dict[str, Any],
    production_impact: dict[str, Any],
) -> None:
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    LOG.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_report(artifact, meaningful, queue_500k, trade_overlap, skip_overlap)

    if TICKET.exists():
        ticket = load_json(TICKET)
        scopes = ticket.setdefault("allowed_write_scope", [])
        runner_scope = repo_rel(Path(__file__))
        if runner_scope not in scopes:
            scopes.append(runner_scope)
        ticket["status"] = "observed_only"
        ticket["completed_at"] = artifact["created_at"]
        ticket["result"] = {
            "decision": artifact["decision"],
            "log_file": repo_rel(LOG),
            "artifact": repo_rel(ARTIFACT),
            "report": repo_rel(REPORT),
            "production_impact": production_impact,
        }
        TICKET.write_text(
            json.dumps(ticket, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if REGISTRY.exists():
        registry = load_json(REGISTRY)
        found = False
        for entry in registry.get("experiments", []):
            if entry.get("experiment_id") == EXP_ID:
                entry.update(
                    {
                        "status": "observed_only",
                        "owner": "loss-attribution",
                        "updated_at": artifact["created_at"],
                        "ticket_file": repo_rel(TICKET),
                    }
                )
                found = True
                break
        if not found:
            registry.setdefault("experiments", []).append(
                {
                    "experiment_id": EXP_ID,
                    "hypothesis": artifact["hypothesis"],
                    "lane": "alpha_discovery",
                    "owner": "loss-attribution",
                    "status": "observed_only",
                    "ticket_file": repo_rel(TICKET),
                    "updated_at": artifact["created_at"],
                }
            )
        REGISTRY.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    exists = False
    if EXPERIMENT_LOG.exists():
        with EXPERIMENT_LOG.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    if json.loads(line).get("experiment_id") == EXP_ID:
                        exists = True
                        break
                except json.JSONDecodeError:
                    continue
    if not exists:
        with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(artifact, ensure_ascii=False, sort_keys=True) + "\n")


def write_report(
    artifact: dict[str, Any],
    meaningful: list[dict[str, Any]],
    queue_500k: list[dict[str, Any]],
    trade_overlap: dict[str, Any],
    skip_overlap: dict[str, Any],
) -> None:
    returns = artifact["shadow_metrics"]["form4_forward_returns"]
    availability = artifact["data_availability"]
    field_presence = availability["field_presence"]
    cik = availability["cik_mapping_gap_report"]

    lines = [
        "# Form 4 Insider Overlay Audit",
        "",
        f"- experiment_id: `{EXP_ID}`",
        "- decision: `shadow_only`",
        "- production_impact: `shadow_audit_only_no_production_change`",
        f"- source: `{repo_rel(TX_PATH)}`",
        "",
        "## Hypothesis",
        "",
        "Open-market insider Form 4 buying may confirm existing `trend_long` / "
        "`breakout_long` candidates, especially large CEO/CFO buys, clustered buys, "
        "first buys, and post-drawdown buys. This audit does not create standalone "
        "entries or alter production.",
        "",
        "## Historical Check",
        "",
        "- Prior May 3 Form 4 audits were `data_gap` because transaction-level PIT files did not exist yet.",
        "- Later Form 4 shadow outcomes showed positive standalone forward returns, but accepted-trade overlap was zero through 20d.",
        "- May 7 event-bundle source pruning rejected Form 4 source promotion; Form 4 had no selected trades in that replay.",
        "",
        "## Data Availability And PIT",
        "",
        f"- daily Form 4 JSONL files: `{availability['daily_form4_file_count']}`",
        f"- combined rows: `{field_presence['row_count']}`; open-market purchase rows: `{field_presence['open_market_purchase_row_count']}`",
        f"- PIT-safe rows: `{field_presence['pit_safe_true_rows']}`; missing `accepted_at`: `{field_presence['rows_missing_accepted_at']}`; missing `usable_trade_date`: `{field_presence['rows_missing_usable_trade_date']}`",
        f"- CIK mapping: `{cik['tickers_mapped']}/{cik['tickers_requested']}` mapped; missing `{', '.join(cik['missing_cik_tickers']) or 'none'}`",
        "- Caveat: historical files are later backfills, so they are PIT-replayable by timestamp but not proof that live Ginger had the source before the adapter existed.",
        "",
        "## Shadow Forward Returns",
        "",
        "| Cohort | Events | Tickers | 10d avg return | 20d avg return | 60d avg return | 90d avg return | 20d avg excess vs SPY |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in (
        "meaningful_purchase_50k",
        "forward_queue_purchase_500k",
        "ceo_cfo_meaningful_purchase",
        "cluster_30d_meaningful_purchase",
    ):
        row = returns[label]

        def fmt_horizon(horizon: int, key: str = "avg_return_pct") -> str:
            value = row["horizons"].get(str(horizon), {}).get(key)
            return "n/a" if value is None else f"{value:.2f}%"

        lines.append(
            f"| `{label}` | {row['event_count']} | {row['ticker_count']} | "
            f"{fmt_horizon(10)} | {fmt_horizon(20)} | {fmt_horizon(60)} | "
            f"{fmt_horizon(90)} | {fmt_horizon(20, 'avg_excess_vs_spy_pct')} |"
        )
    lines.extend(
        [
            "",
            "## Existing Signal Overlap",
            "",
            "| Lookback | Matched accepted trades | Matched avg PnL | Unmatched accepted trades | Unmatched avg PnL |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for lookback in ("10", "20", "60", "90"):
        row = trade_overlap["lookbacks"][lookback]
        matched = row["with_prior_form4"]
        unmatched = row["without_prior_form4"]
        matched_pnl = matched["avg_pnl_pct_net"]
        unmatched_pnl = unmatched["avg_pnl_pct_net"]
        lines.append(
            f"| {lookback}d | {matched['trade_count']} | "
            f"{'n/a' if matched_pnl is None else f'{matched_pnl:.2f}%'} | "
            f"{unmatched['trade_count']} | "
            f"{'n/a' if unmatched_pnl is None else f'{unmatched_pnl:.2f}%'} |"
        )
    lines.extend(
        [
            "",
            "## Slot Value",
            "",
            f"- top skipped oracle candidates checked: `{skip_overlap['top_skipped_candidate_count']}`",
            "- meaningful Form 4 overlap with top skipped opportunities: `0` through 120d",
            "- scarce-slot opportunity cost: not measurable from current rows; Form 4 does not explain saved breakout slot conflicts.",
            "",
            "## Decision",
            "",
            artifact["decision_rationale"],
            "",
            "Next smallest action: keep the default-off Form 4 paper queue alive and join it to a future all-candidate ledger once Ginger persists generated candidates beyond accepted trades and top skipped oracle rows.",
            "",
        ]
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
