"""exp-20260502-019 narrow liquid proxy ETF pool replay.

Alpha search. Test one candidate-pool variable: whether the failed broad proxy
ETF expansion can be narrowed to replayable, liquid sector/rate proxies that
avoid the known USO/XLP drag from exp-20260501-025.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260502-019"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "narrow_proxy_etf_pool.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

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

VARIANTS = OrderedDict([
    ("energy_healthcare_rate", ["XLE", "XLV", "TLT"]),
    ("energy_healthcare_only", ["XLE", "XLV"]),
    ("energy_healthcare_rates", ["XLE", "XLV", "IEF", "TLT"]),
])


def _metrics(result: dict, added: set[str]) -> dict:
    benchmarks = result.get("benchmarks") or {}
    added_trade_count = 0
    added_trade_pnl = 0.0
    added_tickers = set()
    for trade in result.get("trades", []):
        ticker = trade.get("ticker")
        if ticker in added:
            added_trade_count += 1
            added_trade_pnl += float(trade.get("pnl") or 0.0)
            added_tickers.add(ticker)
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "added_proxy_trade_count": added_trade_count,
        "added_proxy_trade_pnl": round(added_trade_pnl, 2),
        "added_proxy_tickers_traded": sorted(added_tickers),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _run_window(universe: list[str], cfg: dict, added: set[str]) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return {"metrics": _metrics(result, added), "trades": result.get("trades", [])}


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    total_pnl_delta = round(sum(d["total_pnl"] for d in deltas.values()), 2)
    baseline_ev = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(sum(d["expected_value_score"] for d in deltas.values()), 6)
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_expected_value_score_sum": baseline_ev,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6) if baseline_total_pnl else None,
        "ev_windows_improved": sum(1 for d in deltas.values() if d["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for d in deltas.values() if d["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for d in deltas.values() if d["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for d in deltas.values() if d["total_pnl"] < 0),
        "max_drawdown_delta_max": max(d["max_drawdown_pct"] for d in deltas.values()),
        "trade_count_delta_sum": sum(d["trade_count"] for d in deltas.values()),
        "win_rate_delta_min": min(d["win_rate"] for d in deltas.values()),
        "sharpe_daily_delta_max": max(d["sharpe_daily"] for d in deltas.values()),
        "added_proxy_trade_count_delta_sum": sum(
            d["added_proxy_trade_count"] for d in deltas.values()
        ),
        "added_proxy_trade_pnl_delta_sum": round(
            sum(d["added_proxy_trade_pnl"] for d in deltas.values()), 2
        ),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.10:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    base_universe = get_universe()
    baseline = OrderedDict()
    for label, cfg in WINDOWS.items():
        baseline[label] = _run_window(base_universe, cfg, set())
        m = baseline[label]["metrics"]
        print(
            f"[{label} baseline] EV={m['expected_value_score']} "
            f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
            f"DD={m['max_drawdown_pct']} WR={m['win_rate']} trades={m['trade_count']}"
        )

    variants = OrderedDict()
    for variant, additions in VARIANTS.items():
        added = set(additions)
        universe = sorted(set(base_universe) | added)
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            rows[label] = _run_window(universe, cfg, added)
            m = rows[label]["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"addedPnL={m['added_proxy_trade_pnl']} "
                f"addedTrades={m['added_proxy_trade_count']}"
            )
        aggregate = _aggregate(baseline, rows)
        variants[variant] = {
            "added_tickers": additions,
            "rows": rows,
            "aggregate": aggregate,
            "passes_gate4": _passes_gate4(aggregate),
        }

    best_variant, best = max(
        variants.items(),
        key=lambda item: (
            item[1]["passes_gate4"],
            item[1]["aggregate"]["ev_windows_improved"],
            -item[1]["aggregate"]["ev_windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    accepted = best["passes_gate4"]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "candidate_pool_narrow_proxy_etf_expansion",
        "hypothesis": (
            "A narrower liquid proxy ETF pool that excludes the known USO/XLP "
            "drag from exp-20260501-025 may add useful rotational candidates "
            "without the broad-proxy noise that failed the prior experiment."
        ),
        "alpha_hypothesis_category": "candidate_pool_meta_routing",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain outcome-join sparse; "
            "this tests a replayable deterministic candidate-pool alternative."
        ),
        "parameters": {
            "single_causal_variable": "narrow liquid proxy ETF candidate-pool expansion",
            "baseline": "current production watchlist after exp-20260501-024 accepted stack",
            "tested_variants": dict(VARIANTS),
            "selector": (
                "already-snapshotted liquid proxies excluding USO/XLP after "
                "the prior broad-proxy failure"
            ),
            "locked_variables": [
                "signal generation rules",
                "entry filters",
                "candidate ranking",
                "risk sizing rules",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all target/stop exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {label: baseline[label]["metrics"] for label in WINDOWS},
        "after_metrics": {
            name: {label: variant["rows"][label]["metrics"] for label in WINDOWS}
            for name, variant in variants.items()
        },
        "delta_metrics": {
            name: variant["aggregate"] for name, variant in variants.items()
        },
        "best_variant": best_variant,
        "best_variant_gate4": accepted,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add only the selected ETF set to filter._BASE_WATCHLIST "
                "and shared sector metadata, then rerun canonical windows before commit."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "This avoids the LLM soft-ranking data limitation rather than "
                "weakening or bypassing LLM responsibilities."
            ),
        },
        "history_guardrails": {
            "not_ai_infra_watchlist_retry": True,
            "not_recent_listing_retry": True,
            "not_broad_proxy_etf_retry": True,
            "why_not_simple_repeat": (
                "This is a narrower candidate-pool test that explicitly excludes "
                "the tickers responsible for the broad-proxy mid/old drag, not "
                "another all-proxy bundle."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "No narrow proxy ETF pool variant passed fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby proxy ETF subsets without forward or event/news evidence.",
            "A valid retry needs slot-aware replacement evidence or a production-ready regime route.",
            "If promoted, update production watchlist and shared sector metadata together.",
        ],
        "related_files": [
            "quant/experiments/exp_20260502_019_narrow_proxy_etf_pool.py",
            "data/experiments/exp-20260502-019/narrow_proxy_etf_pool.json",
            "docs/experiments/logs/exp-20260502-019.json",
            "docs/experiments/tickets/exp-20260502-019.json",
        ],
    }
    return payload


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Narrow proxy ETF pool",
        "summary": (
            f"Best {payload['best_variant']} "
            f"Gate4={payload['best_variant_gate4']}"
        ),
        "best_variant": payload["best_variant"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "production_impact": payload["production_impact"],
    }, indent=2), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "best_gate4": payload["best_variant_gate4"],
        "best_delta": payload["delta_metrics"][payload["best_variant"]],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
