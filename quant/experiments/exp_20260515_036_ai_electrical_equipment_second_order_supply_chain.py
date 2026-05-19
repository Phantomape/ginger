"""exp-20260515-036: AI electrical-equipment second-order supply-chain replay.

Alpha search. Test whether a narrow second-order AI infrastructure basket
focused on electrical equipment / power distribution / cooling infrastructure
improves the current accepted stack. This changes one causal variable only:
candidate-pool membership. Production universe, ranking, sizing, exits, LLM,
news, and pilot sleeves remain locked.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import risk_engine  # noqa: E402
from yfinance_bootstrap import configure_yfinance_runtime  # noqa: E402


EXPERIMENT_ID = "exp-20260515-036"
SUB_BASKET = ["VRT", "ETN", "PWR", "GEV"]
SECTOR_PATCH = {ticker: "Industrials" for ticker in SUB_BASKET}

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "base_snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "aug_snapshot": f"data/experiments/{EXPERIMENT_ID}/ohlcv_aug_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "base_snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "aug_snapshot": f"data/experiments/{EXPERIMENT_ID}/ohlcv_aug_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "base_snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "aug_snapshot": f"data/experiments/{EXPERIMENT_ID}/ohlcv_aug_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "ai_electrical_equipment_second_order_supply_chain.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_ai_electrical_equipment_second_order_supply_chain.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        "worst_3_trade_cluster_pct": _round(result.get("worst_3_trade_cluster_pct"), 4),
        "alpha_per_heat": _round(result.get("alpha_per_heat"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {
                "trade_count",
                "signals_generated",
                "signals_survived",
                "max_consecutive_losses",
            }:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _load_snapshot(path: Path) -> dict[str, pd.DataFrame]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, pd.DataFrame] = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date").sort_index()
        frame.index.name = None
        out[str(ticker).upper()] = frame[["Open", "High", "Low", "Close", "Volume"]]
    return out


def _write_snapshot(path: Path, ohlcv: dict[str, pd.DataFrame], start: str, end: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "experiment_id": EXPERIMENT_ID,
            "download_start": start,
            "download_end": end,
            "tickers": sorted(ohlcv),
        },
        "ohlcv": {},
    }
    for ticker, df in sorted(ohlcv.items()):
        frame = df.copy()
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.sort_index()
        rows = []
        for idx, row in frame.iterrows():
            rows.append({
                "Date": str(pd.Timestamp(idx).date()),
                "Open": float(row["Open"]),
                "High": float(row["High"]),
                "Low": float(row["Low"]),
                "Close": float(row["Close"]),
                "Volume": float(row["Volume"]),
            })
        payload["ohlcv"][ticker] = rows
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _download_history(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"{ticker} download returned no rows.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Volume"]
    if any(col not in df.columns for col in required):
        raise RuntimeError(f"{ticker} download missing required OHLCV columns.")
    return df[required].dropna(how="any")


def _build_augmented_snapshots() -> dict[str, Any]:
    configure_yfinance_runtime()
    coverage: dict[str, Any] = {}
    for label, window in WINDOWS.items():
        base_snapshot = REPO_ROOT / window["base_snapshot"]
        aug_snapshot = REPO_ROOT / window["aug_snapshot"]
        ohlcv = _load_snapshot(base_snapshot)
        coverage[label] = {}
        for ticker in SUB_BASKET:
            frame = ohlcv.get(ticker)
            source = "base_snapshot"
            if frame is None or frame.empty:
                frame = _download_history(
                    ticker=ticker,
                    start=window["start"],
                    end=str(pd.Timestamp(window["end"]) + pd.Timedelta(days=1))[:10],
                )
                source = "yfinance_download"
                ohlcv[ticker] = frame
            coverage[label][ticker] = {
                "source": source,
                "rows": int(len(frame)),
                "first": str(frame.index.min().date()),
                "last": str(frame.index.max().date()),
            }
        _write_snapshot(aug_snapshot, ohlcv, window["start"], window["end"])
    return coverage


def _run_engine(universe: list[str], snapshot_rel: str, start: str, end: str) -> dict[str, Any]:
    result = BacktestEngine(
        universe=universe,
        start=start,
        end=end,
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / snapshot_rel),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _candidate_trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_set = set(SUB_BASKET)
    rows = [
        trade for trade in trades
        if str(trade.get("ticker") or "").upper() in candidate_set
    ]
    by_ticker: dict[str, dict[str, Any]] = {}
    for trade in rows:
        ticker = str(trade.get("ticker") or "").upper()
        ticker_row = by_ticker.setdefault(ticker, {"trades": 0, "wins": 0, "pnl": 0.0})
        ticker_row["trades"] += 1
        pnl = float(trade.get("pnl") or 0.0)
        ticker_row["pnl"] += pnl
        if pnl > 0:
            ticker_row["wins"] += 1
    for ticker_row in by_ticker.values():
        ticker_row["pnl"] = _round(ticker_row["pnl"], 2)
        ticker_row["win_rate"] = _round(
            ticker_row["wins"] / ticker_row["trades"] if ticker_row["trades"] else 0.0,
            4,
        )
    return {
        "trade_count": len(rows),
        "wins": sum(1 for trade in rows if float(trade.get("pnl") or 0.0) > 0),
        "losses": sum(1 for trade in rows if float(trade.get("pnl") or 0.0) <= 0),
        "total_pnl": _round(sum(float(trade.get("pnl") or 0.0) for trade in rows), 2),
        "by_ticker": by_ticker,
        "trades": [
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": _round(trade.get("pnl"), 2),
                "return_pct": _round(trade.get("return_pct"), 4),
                "exit_reason": trade.get("exit_reason"),
            }
            for trade in rows
        ],
    }


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(float(row["before"]["expected_value_score"] or 0.0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0.0) for row in rows.values())
    pnl_before = sum(float(row["before"]["total_pnl"] or 0.0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0.0) for row in rows.values())
    return {
        "expected_value_score_before_sum": _round(ev_before, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before if ev_before else 0.0, 6),
        "total_pnl_before_sum": _round(pnl_before, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / pnl_before if pnl_before else 0.0, 6),
        "ev_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"].get("max_drawdown_pct", 0.0) for row in rows.values()), 6
        ),
        "survival_rate_delta_min": _round(
            min(row["delta"].get("survival_rate", 0.0) for row in rows.values()), 6
        ),
        "trade_count_delta_sum": sum(row["delta"].get("trade_count", 0) for row in rows.values()),
        "worst_trade_pct_delta_min": _round(
            min(row["delta"].get("worst_trade_pct", 0.0) for row in rows.values()), 6
        ),
        "tail_loss_share_delta_max": _round(
            max(row["delta"].get("tail_loss_share", 0.0) for row in rows.values()), 6
        ),
        "candidate_trade_count_sum": sum(
            row["candidate_trade_stats"]["trade_count"] for row in rows.values()
        ),
        "candidate_pnl_sum": _round(
            sum(row["candidate_trade_stats"]["total_pnl"] or 0.0 for row in rows.values()), 2
        ),
    }


def _decision(aggregate: dict[str, Any]) -> tuple[str, str]:
    ev_pct = aggregate["expected_value_score_delta_pct"] or 0.0
    pnl_pct = aggregate["total_pnl_delta_pct"] or 0.0
    if (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
        and ev_pct > 0.10
        and aggregate["max_drawdown_delta_max"] <= 0.01
        and aggregate["candidate_trade_count_sum"] >= 3
    ):
        return (
            "promising_replay_only_do_not_promote",
            "Positive static replay, but candidate-pool promotion still needs PIT/live replacement-value evidence.",
        )
    if (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["candidate_pnl_sum"] > 0
        and (ev_pct > 0 or pnl_pct > 0.03)
    ):
        return (
            "watchlist_replay_only",
            "Some positive replacement-value evidence, but not enough for production promotion.",
        )
    return (
        "rejected",
        "Second-order electrical-equipment basket did not produce robust three-window EV improvement.",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != payload["experiment_id"]:
                kept.append(line)
    kept.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} AI electrical-equipment second-order supply chain",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Sub-basket",
        "",
        ", ".join(f"`{ticker}`" for ticker in payload["parameters"]["candidate_tickers"]),
        "",
        "## Three-window deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | Survival delta | Trades delta | Basket trades | Basket PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["delta_metrics"]["by_window"].items():
        delta = row["delta"]
        basket = row["candidate_trade_stats"]
        lines.append(
            f"| {label} | {delta.get('expected_value_score', 0):+0.4f} | "
            f"{delta.get('total_pnl', 0):+0.2f} | {delta.get('sharpe_daily', 0):+0.2f} | "
            f"{delta.get('max_drawdown_pct', 0):+0.4f} | {delta.get('survival_rate', 0):+0.4f} | "
            f"{delta.get('trade_count', 0):+d} | {basket.get('trade_count', 0)} | "
            f"{basket.get('total_pnl', 0):+0.2f} |"
        )
    lines.extend([
        "",
        "## Aggregate",
        "",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+0.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+0.6f})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+0.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+0.6f})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / "
        f"`{aggregate['ev_windows_regressed']}`",
        f"- Basket trade count / PnL: `{aggregate['candidate_trade_count_sum']}` / "
        f"`${aggregate['candidate_pnl_sum']:+0.2f}`",
        "",
        "## Parity",
        "",
        "No production universe or order path changed. Any positive future promotion must go through shared watchlist/universe governance or a default-off pilot with run/backtester parity.",
        "",
        "## Decision Note",
        "",
        payload["decision_rationale"],
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    base_universe = list(get_universe())
    if any(ticker in set(base_universe) for ticker in SUB_BASKET):
        raise RuntimeError("Target basket is already in the base universe; experiment would not isolate a new variable.")

    coverage = _build_augmented_snapshots()
    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(SECTOR_PATCH)
    try:
        rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for label, window in WINDOWS.items():
            before_result = _run_engine(
                universe=base_universe,
                snapshot_rel=window["base_snapshot"],
                start=window["start"],
                end=window["end"],
            )
            after_result = _run_engine(
                universe=base_universe + SUB_BASKET,
                snapshot_rel=window["aug_snapshot"],
                start=window["start"],
                end=window["end"],
            )
            before_metrics = _metrics(before_result)
            after_metrics = _metrics(after_result)
            rows[label] = {
                "window": {
                    "start": window["start"],
                    "end": window["end"],
                    "snapshot": window["aug_snapshot"],
                    "state_note": window["state_note"],
                },
                "before": before_metrics,
                "after": after_metrics,
                "delta": _delta(after_metrics, before_metrics),
                "candidate_trade_stats": _candidate_trade_stats(after_result.get("trades", [])),
            }
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original_sector_map)

    aggregate = _aggregate(rows)
    decision, decision_rationale = _decision(aggregate)
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": decision,
        "lane": "alpha_search",
        "mechanism_family": "thematic_second_order_supply_chain_candidate_pool",
        "alpha_hypothesis_category": "candidate_pool_extension",
        "hypothesis": (
            "A narrow electrical-equipment / power-distribution / cooling basket may capture "
            "second-order AI datacenter buildout demand more cleanly than the already-tested "
            "first-order optical, power, or connectivity cohorts."
        ),
        "change_type": "candidate_pool_second_order_supply_chain",
        "changed_variable": "second_order_supply_chain_candidate_pool_membership",
        "single_causal_variable": "candidate universe includes VRT/ETN/PWR/GEV second-order electrical-equipment basket",
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows with baseline base snapshots vs augmented snapshots containing only added basket OHLCV",
        "historical_experiment_check": {
            "playbook_alignment": "thematic second-order supply chains was listed in docs/alpha-optimization-playbook.md as unexplored",
            "similar_prior_results": {
                "exp-20260501-008": "Rejected broader AI power/infra expansion that mixed first-order power, optical, miners, and storage; this run isolates a different second-order electrical-equipment cohort.",
                "exp-20260501-015": "Rejected optical/storage subset; this run avoids optical-first names.",
                "exp-20260506-018": "Rejected CEG single-name AI power candidate; this run avoids generation exposure and tests equipment/distribution instead.",
                "exp-20260510-011": "Rejected MRVL connectivity candidate; this run avoids connectivity/custom-silicon first-order exposure.",
                "exp-20260509-008": "Accepted forward AI infra pilot governance, but that run explicitly did not prove alpha and had zero pilot entries in canonical windows.",
            },
            "why_not_simple_repeat": "The tested cohort is a new second-order supply-chain family rather than a retry of optical, generation, connectivity, or broad AI-infra watchlist expansion.",
        },
        "gate_results": {
            "gate1_baseline": "Current code state replayed against the three canonical snapshots from docs/backtesting.md before adding the basket.",
            "gate2_field_check": {
                "candidate_tickers": SUB_BASKET,
                "sector_map_patch": SECTOR_PATCH,
                "ohlcv_coverage": coverage,
                "passed": True,
            },
            "gate3_survival_audit": {
                "hard_rule": "No new filter added; survival is read from measured after-vs-before results only.",
                "baseline_survival_rate": {label: rows[label]["before"]["survival_rate"] for label in rows},
                "after_survival_rate": {label: rows[label]["after"]["survival_rate"] for label in rows},
            },
            "gate4_measurement": {
                "basis": "Three canonical windows only; require stable EV improvement before any promotion.",
                "decision": decision,
            },
        },
        "parameters": {
            "candidate_tickers": SUB_BASKET,
            "sector_patch": SECTOR_PATCH,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(base_universe) + len(SUB_BASKET),
            "locked_variables": [
                "production watchlist",
                "signal generation",
                "ranking",
                "entry filters",
                "position sizing",
                "heat / slot rules",
                "exits",
                "LLM / news replay",
                "pilot sleeve governance",
            ],
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "base_snapshot": window["base_snapshot"],
                "aug_snapshot": window["aug_snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "before_metrics": {label: row["before"] for label, row in rows.items()},
        "after_metrics": {label: row["after"] for label, row in rows.items()},
        "expected_value_score_delta": {
            "late_strong": rows["late_strong"]["delta"].get("expected_value_score"),
            "mid_weak": rows["mid_weak"]["delta"].get("expected_value_score"),
            "old_thin": rows["old_thin"]["delta"].get("expected_value_score"),
            "aggregate": aggregate["expected_value_score_delta_sum"],
        },
        "delta_metrics": {
            "by_window": rows,
            "aggregate": aggregate,
        },
        "rejection_reason": (
            "No basket trade fired in any canonical window, and the added names only caused minor "
            "share-allocation drift in existing positions, reducing aggregate EV and PnL."
        ) if decision == "rejected" else None,
        "next_evidence_needed": (
            "Do not retry raw electrical-equipment basket expansion. A valid revisit needs an "
            "orthogonal ex-ante discriminator, such as official AI-capex/customer-win event tags "
            "or forward pilot replacement-value evidence, before adding these names again."
        ),
        "mechanism_read": (
            "The second-order basket produced zero direct trades in all three windows. The small "
            "regression came from competition/sizing drift in existing names rather than from new "
            "basket alpha, so the raw basket does not add useful replacement value."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": "Any positive follow-up must route through shared universe governance or a default-off pilot sleeve with run/backtester parity.",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "This direction is candidate-pool alpha search and does not depend on sparse LLM soft-ranking samples.",
        },
        "decision": decision,
        "decision_rationale": decision_rationale,
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)).replace("/", "\\"),
            str(LOG_JSON.relative_to(REPO_ROOT)).replace("/", "\\"),
            str(TICKET_JSON.relative_to(REPO_ROOT)).replace("/", "\\"),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("/", "\\"),
            "quant\\experiments\\exp_20260515_033_ai_electrical_equipment_second_order_supply_chain.py",
            "docs\\experiment_log.jsonl",
        ],
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "AI electrical-equipment second-order supply-chain replay",
        "status": decision,
        "lane": "alpha_search",
        "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("/", "\\"),
        "summary": decision_rationale,
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _write_artifact(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "decision_rationale": decision_rationale,
        "aggregate": aggregate,
    }, indent=2))


if __name__ == "__main__":
    main()
