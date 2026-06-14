"""exp-20260614-018: Clustered Form 4 open-market purchase event sleeve, re-run
on the BROAD historical insider sample.

This is a data-breadth redo of exp-20260508-028. That experiment found clustered
PIT-safe Form 4 open-market purchases to be a directionally positive standalone
default-off event sleeve, but rejected it as ``positive_sample_not_material``:
the local Form 4 archive then covered only ~49 tickers / 234 open-market buys
(the narrow watchlist, starved by a reduced SEC CIK map).

The 2026-06-13/06-14 broad SEC backfill (exp-20260613-023) widened the open-market
buy sample to 611 distinct tickers / 3,901 buys (~16x). The SINGLE changed variable
is the breadth of the insider sample. The event-qualification rule, cluster
definition, notional, holding period, costs, baseline core stack, ranking, sizing
and exits are all identical to exp-20260508-028.

No production code, live order path, shared policy, ranking, sizing, exits, LLM/news
path, or watchlist is changed. Replay-only / default-off. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from form4_event_queue import BASE_MEANINGFUL_PURCHASE_VALUE  # noqa: E402

import exp_20260504_034_form4_satellite_overlay as overlay  # noqa: E402
import exp_20260508_028_form4_cluster_satellite as cluster  # noqa: E402
from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    load_warehouse_frames,
)


EXP_ID = "exp-20260614-018"
STEM = "form4_cluster_broad_universe"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260614_018_broad_universe_insider_sample_for_the_clustered_form_4_open_market_purchase_even.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

# Broad open-market-purchase Form 4 rows materialized by exp-20260613-023.
BROAD_FORM4_PATH = OUT_DIR / "form4_open_market_purchases_broad_20240802_20260615.jsonl"

# Same date ranges as exp-20260508-028; snapshots are the existing core-universe
# OHLCV snapshots used for the canonical baseline (the event sleeve itself is
# priced from the broad warehouse, below).
WINDOWS = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21",
                         "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                         "state_note": "slow-melt bull / accepted-stack dominant tape"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22",
                      "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                      "state_note": "rotation-heavy bull where strategy makes money but lags indexes"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22",
                      "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                      "state_note": "mixed-to-weak older tape with lower win rate"}),
    ]
)


def _price_map_from_frames(frames: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, Any]]]:
    """Broad warehouse OHLCV -> {ticker: [{date, open, close, volume}]} (the
    contract the shared event-sleeve overlay expects, incl. SPY trading days)."""
    prices: dict[str, list[dict[str, Any]]] = {}
    for ticker, frame in frames.items():
        rows: list[dict[str, Any]] = []
        for day, row in frame.iterrows():
            rows.append(
                {
                    "date": str(day.date()),
                    "open": float(row["Open"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
            )
        prices[ticker] = rows
    return prices


def _patch_reused_modules() -> None:
    """Point the reused exp-028 cluster harness at the broad sample + our windows."""
    cluster.COMBINED_FORM4_PATH = BROAD_FORM4_PATH
    cluster.WINDOWS = WINDOWS  # date ranges for _load_cluster_events / _window_name
    overlay.WINDOWS = WINDOWS


def build_payload() -> dict[str, Any]:
    _patch_reused_modules()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    frames = load_warehouse_frames()
    prices = _price_map_from_frames(frames)

    events, event_file = cluster._load_cluster_events(prices)
    event_candidates = [overlay._candidate_trade(event, prices) for event in events]

    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas: dict[str, dict[str, Any]] = OrderedDict()
    gate_by_window: dict[str, dict[str, Any]] = OrderedDict()
    event_details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected, skipped = overlay._select_event_trades(
            event_candidates, start=window["start"], end=window["end"]
        )
        event_curve = overlay._event_equity_curve(
            selected, prices=prices, start=window["start"], end=window["end"]
        )
        before_metrics[label] = overlay._core_metrics(result)
        after_metrics[label] = (
            overlay._combined_metrics(result, event_curve, selected)
            if selected
            else dict(before_metrics[label])
        )
        deltas[label] = overlay._delta(before_metrics[label], after_metrics[label])
        gate_by_window[label] = overlay._gate4(before_metrics[label], after_metrics[label])
        event_details[label] = {
            "candidate_count": sum(
                1 for row in event_candidates
                if window["start"] <= cluster._date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "price_ready_count": sum(
                1 for row in event_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= cluster._date10(row.get("usable_trade_date")) <= window["end"]
            ),
            "selected_trade_count": len(selected),
            "skipped_count": len(skipped),
            "selected_trades": selected,
            "skipped_candidates": skipped[:20],
        }

    aggregate_delta = cluster._aggregate_delta(before_metrics, after_metrics)
    gate = cluster._gate_result(gate_by_window, aggregate_delta, event_details)

    if gate["passed"]:
        decision = "accepted_for_default_off_paper_promotion"
        status = "accepted_default_off"
        rationale = (
            "On the broad insider sample, clustered Form 4 open-market buying cleared "
            "material aggregate lift, zero EV regression, and the pre-registered "
            "sample/concentration guard. Promotion still requires a shared default-off "
            "run/backtest adapter and live-realistic envelope before trade-enabled use."
        )
    elif (
        aggregate_delta["aggregate_ev_delta"] > 0
        and aggregate_delta["aggregate_pnl_delta"] > 0
        and aggregate_delta["windows_ev_regressed"] == 0
    ):
        decision = "rejected_positive_sample_not_material"
        status = "rejected"
        rationale = (
            "Even on the broad insider sample, clustered Form 4 buying stayed "
            "directionally positive but below the materiality / sample / concentration "
            "guards, so it does not justify another event sleeve promotion."
        )
    else:
        decision = "rejected"
        status = "rejected"
        rationale = (
            "On the broad insider sample, clustered Form 4 buying did not improve enough "
            "windows or introduced EV/PnL regression under the canonical three-window replay."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Clustered/multi-owner PIT-safe Form 4 open-market purchases, re-run on the "
            "broad historical insider sample (49->611 tickers, 234->3901 buys), give a "
            "positive standalone default-off event sleeve whose three-window aggregate EV/PnL "
            "lift is now material at adequate sample, where the narrow exp-20260508-028 replay "
            "was positive-but-immaterial."
        ),
        "change_type": "default_off_paper_event_sleeve",
        "mechanism_family": "form4_clustered_insider_buy_event_satellite",
        "single_causal_variable": "breadth of the insider sample (broad backfill) for the SAME clustered Form 4 open-market purchase event rule as exp-20260508-028",
        "parameters": {
            "base_meaningful_purchase_min_total_value": BASE_MEANINGFUL_PURCHASE_VALUE,
            "cluster_window_calendar_days": 30,
            "cluster_definition": "same ticker has >=2 meaningful event days in 30d, or owner_count_30d >=2, or current event owner_count >=2",
            "event_notional_usd": overlay.EVENT_NOTIONAL,
            "max_event_positions": overlay.MAX_EVENT_POSITIONS,
            "hold_days": overlay.HOLD_DAYS,
            "round_trip_cost_pct": overlay.ROUND_TRIP_COST_PCT,
            "price_source": "broad warehouse (all_windows_full_liquid) via load_warehouse_frames",
            "form4_source": cluster._repo_rel(event_file) if 'cluster' in dir() and event_file else str(BROAD_FORM4_PATH),
            "locked_variables": [
                "core universe", "core signal generation", "core candidate ranking",
                "core position sizing", "core exits", "LLM/news replay settings",
                "Form 4 transaction parser", "event qualification rule",
                "event notional", "event holding period", "cluster definition",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "historical_experiment_check": {
            "exp-20260508-028": "Same clustered open-market buy rule; positive but immaterial on ~49 tickers / 234 buys.",
            "exp-20260504-034": "Prior >=500k single-event Form 4 satellite, positive but immaterial.",
            "exp-20260512-101": "Multi-owner buy cluster observed-only on the narrow sample.",
            "single_changed_variable": "ONLY the insider sample breadth changed (broad SEC backfill, exp-20260613-023); rule/params identical.",
            "why_not_forbidden_retry": "The narrow rejections were sample-size only with no forbidden-retry note; a larger sample is the explicit new evidence, not a threshold retune.",
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "deltas": deltas,
        "aggregate_delta": aggregate_delta,
        "gate4": gate,
        "event_details": event_details,
        "decision_rationale": rationale,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "alters_exits": False,
            "promotion_blocker_if_positive": (
                "A shared default-off Form 4 cluster queue/paper adapter must be wired in "
                "run.py + replay with parity tests and a live-realistic execution envelope "
                "before any trade-enabled promotion."
            ),
        },
        "data_source": {
            "form4_transactions_path": str(BROAD_FORM4_PATH).replace("\\", "/"),
            "form4_open_market_tickers": 611,
            "form4_open_market_rows": 3901,
            "warehouse_price_frames": len(frames),
            "pit_status": "uses accepted_at/usable_trade_date from the broad Form 4 archive; OHLCV from broad warehouse",
        },
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _judge_aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev = sum(float(r.get("expected_value_score") or 0.0) for r in metrics.values())
    pnl = sum(float(r.get("total_pnl") or 0.0) for r in metrics.values())
    trades = sum(int(r.get("trade_count") or 0) for r in metrics.values())
    return {"expected_value_score": round(ev, 4), "total_pnl": round(pnl, 2), "total_trades": trades}


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, _judge_aggregate(payload["before_metrics"]))
    _write_json(AFTER_JSON, _judge_aggregate(payload["after_metrics"]))
    print(json.dumps({
        "experiment_id": EXP_ID,
        "decision": payload["decision"],
        "aggregate_delta": payload["aggregate_delta"],
        "gate4": {k: payload["gate4"][k] for k in (
            "passed", "material_aggregate", "zero_ev_regression",
            "selected_event_trades", "sample_guard_passed", "single_ticker_positive_share")},
        "anti_js": "No JavaScript was used.",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
