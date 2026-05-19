"""exp-20260505-009 user historical watchlist with fresh OHLCV.

Observed-only alpha search. This downloads fresh OHLCV snapshots for the
canonical three windows, then compares the current core universe against the
same universe plus the user's historical watchlist. No production watchlist,
signal, ranking, sizing, exit, LLM, or news logic is changed.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260505-009"

REQUESTED_TICKERS_RAW = [
    "SNDK", "MU", "NBIS", "CRCL", "APP", "CRWD", "SNXX", "CEG",
    "COIN", "ORCL", "MTZ", "MSTR", "VST", "USO", "TSM", "AMZN",
    "HOOD", "RBLX", "CHKP", "APPX", "UNH", "PLTR", "AKAM", "TSLA",
    "META", "BLSH", "FIG", "FUTU", "COST", "IRM", "AIT", "IBIT",
    "BMNR", "BITB", "YANG", "QBTS", "QUBT", "SQQQ", "SOXS", "WRD",
    "VNET", "PRMB", "NVDA", "ACHR", "INFQ", "TTD", "SOFI", "TRIP",
    "TLRY", "OPEN", "CHAU", "TQQQ", "VTWO", "YINN", "AEVA", "WOLF",
    "LRN", "MSFT", "NFLX", "ALB.PRA", "QQQ", "MRVL", "PDD", "IAU",
    "VOO", "MCD", "WAB", "SOXL", "AAPL", "GOOG", "INTC", "CRDO",
    "IDXX", "AVAV", "LHX", "JPM", "AGX", "ISRG", "GE", ".RUT",
    "AMD",
]

# Yahoo uses dash notation for preferred shares. Russell 2000 cash index is not
# a directly tradeable instrument, so it is disclosed and excluded from the
# tradeable candidate pool instead of simulating imaginary fills.
YAHOO_ALIASES = {
    "ALB.PRA": "ALB-PA",
}
NON_TRADEABLE_REQUESTS = {
    ".RUT": "cash index; use IWM/VTWO for tradeable Russell exposure",
}

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
SNAPSHOT_DIR = OUT_DIR / "ohlcv"
OUT_JSON = OUT_DIR / "historical_watchlist_new_ohlcv.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_historical_watchlist_new_ohlcv.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        text = str(value).strip().upper()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _normalization() -> dict[str, Any]:
    requested = _dedupe(REQUESTED_TICKERS_RAW)
    tradeable = OrderedDict()
    skipped = OrderedDict()
    aliases = OrderedDict()
    for raw in requested:
        if raw in NON_TRADEABLE_REQUESTS:
            skipped[raw] = NON_TRADEABLE_REQUESTS[raw]
            continue
        normalized = YAHOO_ALIASES.get(raw, raw).upper()
        tradeable[raw] = normalized
        if normalized != raw:
            aliases[raw] = normalized
    return {
        "requested": requested,
        "tradeable_map": tradeable,
        "tradeable": sorted(set(tradeable.values())),
        "skipped": skipped,
        "aliases": aliases,
    }


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    total_pnl = round(float(result.get("total_pnl") or 0.0), 2)
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": total_pnl,
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "by_strategy": result.get("by_strategy") or {},
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key == "trade_count":
                out[key] = int(after_value - before_value)
            else:
                out[key] = round(after_value - before_value, 6)
    return out


def _snapshot_path(label: str) -> Path:
    return SNAPSHOT_DIR / f"{EXPERIMENT_ID}_{label}_fresh_ohlcv.json"


def _run_engine(
    universe: list[str],
    cfg: dict[str, str],
    *,
    ohlcv_snapshot_path: Path | None = None,
    save_ohlcv_snapshot_path: Path | None = None,
) -> dict[str, Any]:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=(
            str(ohlcv_snapshot_path) if ohlcv_snapshot_path is not None else None
        ),
        save_ohlcv_snapshot_path=(
            str(save_ohlcv_snapshot_path)
            if save_ohlcv_snapshot_path is not None
            else None
        ),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _load_snapshot(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _date_count(rows: list[dict[str, Any]], start: str, end: str) -> int:
    return sum(1 for row in rows if start <= str(row.get("Date", ""))[:10] <= end)


def _coverage(snapshot_path: Path, cfg: dict[str, str], normalization: dict[str, Any]) -> dict[str, Any]:
    payload = _load_snapshot(snapshot_path)
    raw_ohlcv = payload.get("ohlcv") or {}
    spy_rows = raw_ohlcv.get("SPY") or []
    expected_days = _date_count(spy_rows, cfg["start"], cfg["end"])
    by_ticker = OrderedDict()
    for raw, normalized in normalization["tradeable_map"].items():
        rows = raw_ohlcv.get(normalized) or []
        rows_in_window = _date_count(rows, cfg["start"], cfg["end"])
        by_ticker[raw] = {
            "yahoo_symbol": normalized,
            "rows_total": len(rows),
            "rows_in_window": rows_in_window,
            "coverage_fraction": (
                round(rows_in_window / expected_days, 4) if expected_days else 0.0
            ),
            "first_date": str(rows[0].get("Date", ""))[:10] if rows else None,
            "last_date": str(rows[-1].get("Date", ""))[:10] if rows else None,
            "downloaded": bool(rows),
        }
    downloaded = [
        raw for raw, row in by_ticker.items()
        if row["downloaded"] and row["coverage_fraction"] > 0
    ]
    missing = [raw for raw, row in by_ticker.items() if not row["downloaded"]]
    no_window_rows = [
        raw for raw, row in by_ticker.items()
        if row["downloaded"] and row["rows_in_window"] == 0
    ]
    full_coverage = [
        raw for raw, row in by_ticker.items()
        if row["coverage_fraction"] >= 0.95
    ]
    return {
        "snapshot_path": str(snapshot_path.relative_to(REPO_ROOT)),
        "snapshot_ticker_count": len(raw_ohlcv),
        "expected_trading_days": expected_days,
        "requested_downloaded_count": len(downloaded),
        "requested_full_coverage_count": len(full_coverage),
        "requested_missing_count": len(missing),
        "requested_no_window_rows_count": len(no_window_rows),
        "downloaded_requested_tickers": downloaded,
        "full_coverage_requested_tickers": full_coverage,
        "missing_requested_tickers": missing,
        "no_window_rows_requested_tickers": no_window_rows,
        "by_ticker": by_ticker,
    }


def _trade_sample(trades: list[dict[str, Any]], tickers: set[str]) -> list[dict[str, Any]]:
    out = []
    for trade in trades:
        if str(trade.get("ticker", "")).upper() not in tickers:
            continue
        out.append({
            "ticker": trade.get("ticker"),
            "strategy": trade.get("strategy"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "pnl": trade.get("pnl"),
            "return_pct": trade.get("return_pct"),
            "exit_reason": trade.get("exit_reason"),
        })
    return out


def _trade_stats(trades: list[dict[str, Any]], tickers: set[str]) -> dict[str, Any]:
    selected = [
        trade for trade in trades
        if str(trade.get("ticker", "")).upper() in tickers
    ]
    by_ticker = Counter(str(trade.get("ticker", "")).upper() for trade in selected)
    pnl_by_ticker: dict[str, float] = {}
    wins_by_ticker: Counter[str] = Counter()
    for trade in selected:
        ticker = str(trade.get("ticker", "")).upper()
        pnl = float(trade.get("pnl") or 0.0)
        pnl_by_ticker[ticker] = round(pnl_by_ticker.get(ticker, 0.0) + pnl, 2)
        if pnl > 0:
            wins_by_ticker[ticker] += 1
    return {
        "trade_count": len(selected),
        "total_pnl": round(sum(float(t.get("pnl") or 0.0) for t in selected), 2),
        "win_rate": (
            round(
                sum(1 for t in selected if float(t.get("pnl") or 0.0) > 0)
                / len(selected),
                4,
            )
            if selected else None
        ),
        "by_ticker": {
            ticker: {
                "trade_count": count,
                "pnl": pnl_by_ticker.get(ticker, 0.0),
                "wins": wins_by_ticker.get(ticker, 0),
            }
            for ticker, count in sorted(by_ticker.items())
        },
    }


def _aggregate(by_window: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = round(
        sum(float(v["before"]["expected_value_score"] or 0.0) for v in by_window.values()),
        6,
    )
    ev_delta = round(
        sum(float(v["delta"]["expected_value_score"] or 0.0) for v in by_window.values()),
        6,
    )
    pnl_before = round(sum(float(v["before"]["total_pnl"] or 0.0) for v in by_window.values()), 2)
    pnl_delta = round(sum(float(v["delta"]["total_pnl"] or 0.0) for v in by_window.values()), 2)
    return {
        "expected_value_score_before_sum": ev_before,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / ev_before, 6) if ev_before else None,
        "total_pnl_before_sum": pnl_before,
        "total_pnl_delta_sum": pnl_delta,
        "total_pnl_delta_pct": round(pnl_delta / pnl_before, 6) if pnl_before else None,
        "ev_windows_improved": sum(
            1 for v in by_window.values() if v["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for v in by_window.values() if v["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for v in by_window.values() if v["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for v in by_window.values() if v["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": max(v["delta"]["max_drawdown_pct"] for v in by_window.values()),
        "max_sharpe_daily_delta": max(v["delta"]["sharpe_daily"] for v in by_window.values()),
        "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
        "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
    }


def _accepted(aggregate: dict[str, Any]) -> bool:
    majority_ev = (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
    )
    material = (
        (aggregate["expected_value_score_delta_pct"] or 0.0) > 0.10
        or (aggregate["total_pnl_delta_pct"] or 0.0) > 0.05
        or aggregate["max_drawdown_delta_max"] < -0.01
        or aggregate["max_sharpe_daily_delta"] > 0.10
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return bool(majority_ev and material)


def _build_artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Historical Watchlist Fresh OHLCV",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Universe",
        "",
        f"- Requested tickers: `{payload['parameters']['requested_ticker_count']}`",
        f"- Tradeable requested tickers: `{payload['parameters']['tradeable_requested_ticker_count']}`",
        f"- Newly added vs current core universe: `{payload['parameters']['newly_added_ticker_count']}`",
        f"- Already present in core universe: `{payload['parameters']['already_in_base_count']}`",
        "- Skipped non-tradeable requests: "
        f"`{json.dumps(payload['parameters']['skipped_non_tradeable'], sort_keys=True)}`",
        "",
        "## Three-window deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Added-name trades | Added-name PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["delta_metrics"]["by_window"].items():
        d = row["delta"]
        added = row["added_ticker_trade_stats"]
        lines.append(
            f"| `{label}` | {d['expected_value_score']:+.4f} | "
            f"{d['total_pnl']:+.2f} | {d['sharpe_daily']:+.2f} | "
            f"{d['max_drawdown_pct']:+.4f} | {d['win_rate']:+.4f} | "
            f"{d['trade_count']:+d} | {added['trade_count']} | "
            f"{added['total_pnl']:+.2f} |"
        )
    lines.extend([
        "",
        "## Aggregate",
        "",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- Max Sharpe daily delta: `{aggregate['max_sharpe_daily_delta']:+.2f}`",
        f"- Trade-count delta sum: `{aggregate['trade_count_delta_sum']:+d}`",
        "",
        "## Data Notes",
        "",
        "- Fresh yfinance OHLCV snapshots were saved under `data/experiments/exp-20260505-009/ohlcv/`.",
        "- Baseline and expanded variants used the same fresh snapshot inside each window.",
        "- `.RUT` was skipped because it is a cash index, not a directly tradeable instrument.",
        "- `ALB.PRA` was downloaded as Yahoo symbol `ALB-PA`.",
        "",
        "## Parity",
        "",
        "No production code or core watchlist was changed. If accepted, promotion must go through universe governance / pilot handling rather than direct `filter.py` expansion.",
    ])
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept_lines = []
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    existing = json.loads(stripped)
                except json.JSONDecodeError:
                    kept_lines.append(line.rstrip("\n"))
                    continue
                if existing.get("experiment_id") == payload["experiment_id"]:
                    continue
                kept_lines.append(stripped)
    with path.open("w", encoding="utf-8") as fh:
        for line in kept_lines:
            fh.write(line + "\n")
        fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def build_payload() -> dict[str, Any]:
    normalization = _normalization()
    base_universe = sorted(set(get_universe()))
    requested_tradeable = normalization["tradeable"]
    expanded_universe = sorted(set(base_universe) | set(requested_tradeable))
    added_tickers = sorted(set(expanded_universe) - set(base_universe))
    already_in_base = sorted(set(requested_tradeable) & set(base_universe))
    added_set = set(added_tickers)

    rows = []
    by_window = OrderedDict()
    print(f"{EXPERIMENT_ID}: base={len(base_universe)} expanded={len(expanded_universe)} added={len(added_tickers)}")
    for label, cfg in WINDOWS.items():
        snapshot = _snapshot_path(label)
        print(f"[{label}] downloading fresh OHLCV and running expanded universe...")
        expanded_result = _run_engine(
            expanded_universe,
            cfg,
            save_ohlcv_snapshot_path=snapshot,
        )
        print(f"[{label}] running baseline on the same fresh snapshot...")
        baseline_result = _run_engine(
            base_universe,
            cfg,
            ohlcv_snapshot_path=snapshot,
        )

        before = _metrics(baseline_result)
        after = _metrics(expanded_result)
        delta = _delta(after, before)
        coverage = _coverage(snapshot, cfg, normalization)
        added_trade_sample = _trade_sample(expanded_result.get("trades", []), added_set)
        added_trade_stats = _trade_stats(expanded_result.get("trades", []), added_set)
        row = {
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "state_note": cfg["state_note"],
            "snapshot": str(snapshot.relative_to(REPO_ROOT)),
            "before": before,
            "after": after,
            "delta": delta,
            "coverage": coverage,
            "added_ticker_trade_stats": added_trade_stats,
            "added_ticker_trades": added_trade_sample,
            "entry_reason_counts_before": (
                baseline_result.get("entry_execution_attribution", {}).get("reason_counts", {})
            ),
            "entry_reason_counts_after": (
                expanded_result.get("entry_execution_attribution", {}).get("reason_counts", {})
            ),
        }
        rows.append(row)
        by_window[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "added_ticker_trade_stats": added_trade_stats,
        }
        print(
            f"[{label}] delta EV={delta['expected_value_score']:+.4f} "
            f"PnL={delta['total_pnl']:+.2f} SharpeD={delta['sharpe_daily']:+.2f} "
            f"trades={delta['trade_count']:+d} added_trades={added_trade_stats['trade_count']}"
        )

    aggregate = _aggregate(by_window)
    accepted = _accepted(aggregate)
    decision = (
        "accepted_for_governance_review"
        if accepted
        else "rejected_for_core_promotion"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "change_type": "candidate_pool_expansion",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The user's historical attention list may contain recurring momentum, "
            "event, AI-infrastructure, crypto-beta, and high-volatility candidates "
            "that the existing A/B/C signal stack can monetize when they are added "
            "to the candidate universe using fresh OHLCV."
        ),
        "alpha_hypothesis_category": "entry",
        "historical_experiment_check": {
            "near_repeat": "partial",
            "similar_failed_families": [
                "exp-20260504-028 macro ETF candidate-pool expansion rejected",
                "exp-20260504-045 energy pair-confirmed macro ETF rejected",
                "exp-20260505-006 active-position sector cap rejected",
                "exp-20260505-007 breakout above-200MA hard gate no-op",
            ],
            "why_not_simple_repeat": (
                "This run is not a macro ETF basket, threshold retune, sector cap, "
                "or moving-average gate. It tests a user-sourced historical "
                "attention universe with fresh OHLCV and compares baseline vs "
                "expanded using the same snapshots."
            ),
            "mechanism_insight_check": (
                "Recent notes warn against direct macro ETF promotion and core "
                "threshold/filter retunes. This remains an observed-only universe "
                "extension test and does not promote any ticker."
            ),
        },
        "parameters": {
            "single_causal_variable": "candidate universe = current core universe plus user's historical watchlist",
            "requested_ticker_count": len(normalization["requested"]),
            "requested_tickers": normalization["requested"],
            "tradeable_requested_ticker_count": len(requested_tradeable),
            "tradeable_requested_tickers": requested_tradeable,
            "newly_added_ticker_count": len(added_tickers),
            "newly_added_tickers": added_tickers,
            "already_in_base_count": len(already_in_base),
            "already_in_base_tickers": already_in_base,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "skipped_non_tradeable": normalization["skipped"],
            "yahoo_aliases": normalization["aliases"],
            "data_fields_verified": {
                "ohlcv": ["Open", "High", "Low", "Close", "Volume"],
                "sector": "existing risk_engine map when known; Unknown fallback otherwise",
                "entry_date": "simulated by backtester Position",
                "target_price": "computed by shared signal/risk path",
            },
            "locked_variables": [
                "signal_engine",
                "risk_engine",
                "portfolio_engine",
                "production_parity entry planning",
                "position sizing",
                "gap cancels",
                "exits",
                "add-ons",
                "LLM replay",
                "news replay",
                "event sleeves",
                "all numeric thresholds",
            ],
            "fresh_ohlcv": True,
            "baseline_and_expanded_share_snapshot_per_window": True,
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
        "before_metrics": {label: row["before"] for label, row in by_window.items()},
        "after_metrics": {label: row["after"] for label, row in by_window.items()},
        "delta_metrics": {
            "by_window": by_window,
            "aggregate": aggregate,
        },
        "coverage_by_window": {
            row["window"]: row["coverage"] for row in rows
        },
        "gate4_basis": (
            "Accepted for governance review only; multi-window materiality passed."
            if accepted
            else "Rejected for core promotion: expanded universe did not pass multi-window Gate 4."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "production_watchlist_changed": False,
            "promotion_requirement": (
                "If accepted, add qualifying names through universe governance "
                "or a default-off pilot sleeve, not direct filter.py expansion."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "This is a fully replayable OHLCV universe experiment.",
        },
        "rows": rows,
        "rejection_reason": (
            None
            if accepted
            else "Candidate-pool expansion failed the multi-window materiality/stability gate."
        ),
        "risk_of_change": (
            "The watchlist contains high-beta, crypto-beta, leveraged/inverse ETF, "
            "short-history, and unknown-sector names. A direct core promotion could "
            "increase turnover, crowd scarce slots, or simulate non-repeatable "
            "attention bias."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Production-aligned joined outcomes remain sparse.",
            "event_bundle_promotion": "Needs closed forward paper replacement-value evidence.",
            "macro_or_ETF_pool_only": "Recent macro ETF and energy-pair expansions were rejected.",
            "threshold_tuning": "Recent mechanism notes block nearby threshold/gate retunes without candidate audits.",
        },
        "related_files": [
            "quant/experiments/exp_20260505_009_historical_watchlist_new_ohlcv.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(SNAPSHOT_DIR.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> int:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "gate4_basis": payload["gate4_basis"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "next_action": (
            "Do not promote as core unless governance review identifies a smaller "
            "sub-basket with stable contribution and manageable complexity."
        ),
    }
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_build_artifact(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
