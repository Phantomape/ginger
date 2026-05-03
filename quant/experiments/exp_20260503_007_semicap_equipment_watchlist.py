"""exp-20260503-007 semiconductor equipment watchlist scout.

Alpha search. Test whether adding liquid semiconductor equipment / compute
supplier leaders improves the current A+B candidate pool without changing
signal rules, ranking, sizing, exits, add-ons, LLM, or news replay.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from yfinance_bootstrap import configure_yfinance_runtime  # noqa: E402
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260503-007"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "semicap_equipment_watchlist.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "base_snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "aug_snapshot": f"data/experiments/{EXPERIMENT_ID}/ohlcv_aug_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "base_snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "aug_snapshot": f"data/experiments/{EXPERIMENT_ID}/ohlcv_aug_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "base_snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "aug_snapshot": f"data/experiments/{EXPERIMENT_ID}/ohlcv_aug_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

CANDIDATE_GROUP = OrderedDict([
    ("semicap_equipment_compute", ["QCOM", "AMAT", "ASML"]),
])

VARIANTS = OrderedDict([
    ("add_semicap_equipment_compute", ["QCOM", "AMAT", "ASML"]),
    ("add_qcom_only_control", ["QCOM"]),
    ("add_amat_only_control", ["AMAT"]),
    ("add_asml_only_control", ["ASML"]),
])

SECTOR_PATCH = {
    "QCOM": "Technology",
    "AMAT": "Technology",
    "ASML": "Technology",
}


def _load_snapshot(path: Path) -> dict[str, pd.DataFrame]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for ticker, rows in payload["ohlcv"].items():
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date").sort_index()
        frame.index.name = None
        out[ticker] = frame[["Open", "High", "Low", "Close", "Volume"]]
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
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _download_missing(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    df = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,
    )
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Volume"]
    if any(col not in df.columns for col in required):
        return None
    return df[required].dropna(how="any")


def _build_augmented_snapshots(candidates: list[str]) -> dict:
    configure_yfinance_runtime()
    coverage = {}
    for label, window in WINDOWS.items():
        aug_path = REPO_ROOT / window["aug_snapshot"]
        if aug_path.exists():
            existing = _load_snapshot(aug_path)
            coverage[label] = {}
            for ticker in candidates:
                frame = existing.get(ticker)
                coverage[label][ticker] = (
                    {
                        "source": "cached_aug_snapshot",
                        "rows": int(len(frame)),
                        "first": str(frame.index.min().date()),
                        "last": str(frame.index.max().date()),
                    }
                    if frame is not None and not frame.empty else
                    {"source": "missing", "rows": 0}
                )
            continue

        base = _load_snapshot(REPO_ROOT / window["base_snapshot"])
        dl_start = str((pd.Timestamp(window["start"]) - pd.Timedelta(days=450)).date())
        dl_end = str((pd.Timestamp(window["end"]) + pd.Timedelta(days=5)).date())
        coverage[label] = {}
        for ticker in candidates:
            if ticker in base:
                frame = base[ticker]
                coverage[label][ticker] = {
                    "source": "base_snapshot",
                    "rows": int(len(frame)),
                    "first": str(frame.index.min().date()),
                    "last": str(frame.index.max().date()),
                }
                continue
            df = _download_missing(ticker, dl_start, dl_end)
            if df is None or df.empty:
                coverage[label][ticker] = {"source": "missing", "rows": 0}
                continue
            base[ticker] = df
            coverage[label][ticker] = {
                "source": "downloaded",
                "rows": int(len(df)),
                "first": str(df.index.min().date()),
                "last": str(df.index.max().date()),
            }
        _write_snapshot(REPO_ROOT / window["aug_snapshot"], base, dl_start, dl_end)
    return coverage


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_val in before.items():
        after_val = after.get(key)
        out[key] = (
            round(after_val - before_val, 6)
            if isinstance(after_val, (int, float)) and isinstance(before_val, (int, float))
            else None
        )
    return out


def _candidate_trade_summary(result: dict, added: set[str]) -> dict:
    trades = [t for t in result.get("trades", []) if t.get("ticker") in added]
    by_ticker = {}
    for trade in trades:
        ticker = trade.get("ticker")
        rec = by_ticker.setdefault(ticker, {"trades": 0, "pnl": 0.0, "wins": 0})
        rec["trades"] += 1
        rec["pnl"] += float(trade.get("pnl") or 0.0)
        if (trade.get("pnl") or 0) > 0:
            rec["wins"] += 1
    for rec in by_ticker.values():
        rec["pnl"] = round(rec["pnl"], 2)
        rec["win_rate"] = round(rec["wins"] / rec["trades"], 4) if rec["trades"] else None
    return {
        "candidate_trade_count": len(trades),
        "candidate_pnl": round(sum(float(t.get("pnl") or 0.0) for t in trades), 2),
        "by_ticker": by_ticker,
    }


def _run_window(universe: list[str], window: dict, snapshot_key: str = "aug_snapshot") -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / window[snapshot_key]),
    )
    return engine.run()


def _aggregate(variant_rows: list[dict], baseline_by_window: dict) -> dict:
    pnl_delta_sum = round(sum(r["delta"]["total_pnl"] for r in variant_rows), 2)
    baseline_pnl_sum = sum(
        baseline_by_window[r["window"]]["metrics"]["total_pnl"]
        for r in variant_rows
    )
    return {
        "expected_value_score_delta_sum": round(
            sum(r["delta"]["expected_value_score"] for r in variant_rows), 4
        ),
        "total_pnl_delta_sum": pnl_delta_sum,
        "baseline_total_pnl_sum": round(baseline_pnl_sum, 2),
        "total_pnl_delta_pct": round(pnl_delta_sum / baseline_pnl_sum, 6)
        if baseline_pnl_sum else None,
        "ev_windows_improved": sum(
            1 for r in variant_rows if r["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for r in variant_rows if r["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for r in variant_rows if r["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for r in variant_rows if r["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": round(
            max(r["delta"]["max_drawdown_pct"] for r in variant_rows),
            6,
        ),
        "trade_count_delta_sum": sum(r["delta"]["trade_count"] for r in variant_rows),
        "win_rate_delta_min": round(min(r["delta"]["win_rate"] for r in variant_rows), 6),
        "candidate_trade_count_sum": sum(
            r["candidate_trades"]["candidate_trade_count"] for r in variant_rows
        ),
        "candidate_pnl_sum": round(
            sum(r["candidate_trades"]["candidate_pnl"] for r in variant_rows),
            2,
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    baseline_universe = sorted(get_universe())
    candidates = sorted({ticker for group in CANDIDATE_GROUP.values() for ticker in group})
    already_present = sorted(set(candidates) & set(baseline_universe))
    new_candidates = sorted(set(candidates) - set(baseline_universe))

    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(SECTOR_PATCH)
    try:
        coverage = _build_augmented_snapshots(candidates)
        tradeable_by_all_windows = [
            ticker for ticker in new_candidates
            if all((coverage[label].get(ticker) or {}).get("rows", 0) >= 220 for label in WINDOWS)
        ]
        variants = OrderedDict(
            (name, [ticker for ticker in tickers if ticker in tradeable_by_all_windows])
            for name, tickers in VARIANTS.items()
        )
        variants = OrderedDict((name, tickers) for name, tickers in variants.items() if tickers)

        rows = []
        baseline_by_window = {}
        for label, window in WINDOWS.items():
            result = _run_window(baseline_universe, window, snapshot_key="base_snapshot")
            if "error" in result:
                raise RuntimeError(f"baseline {label} failed: {result['error']}")
            baseline_by_window[label] = {"metrics": _metrics(result), "result": result}
            rows.append({
                "window": label,
                "variant": "baseline",
                "added": [],
                "metrics": baseline_by_window[label]["metrics"],
                "candidate_trades": {
                    "candidate_trade_count": 0,
                    "candidate_pnl": 0.0,
                    "by_ticker": {},
                },
            })

        summary = {}
        for variant, added in variants.items():
            variant_rows = []
            universe = sorted(set(baseline_universe) | set(added))
            for label, window in WINDOWS.items():
                result = _run_window(universe, window)
                if "error" in result:
                    raise RuntimeError(f"{variant} {label} failed: {result['error']}")
                metrics = _metrics(result)
                before = baseline_by_window[label]["metrics"]
                row = {
                    "window": label,
                    "variant": variant,
                    "added": added,
                    "metrics": metrics,
                    "delta": _delta(metrics, before),
                    "candidate_trades": _candidate_trade_summary(result, set(added)),
                }
                rows.append(row)
                variant_rows.append(row)
            by_window = {
                row["window"]: {
                    "before": baseline_by_window[row["window"]]["metrics"],
                    "after": row["metrics"],
                    "delta": row["delta"],
                    "candidate_trades": row["candidate_trades"],
                }
                for row in variant_rows
            }
            summary[variant] = {
                "added": added,
                "by_window": by_window,
                "aggregate": _aggregate(variant_rows, baseline_by_window),
            }

        promotion_pool = {
            name: rec
            for name, rec in summary.items()
            if rec["aggregate"]["candidate_trade_count_sum"] > 0
        } or summary
        best_variant = (
            max(
                promotion_pool,
                key=lambda name: (
                    promotion_pool[name]["aggregate"]["ev_windows_improved"]
                    - promotion_pool[name]["aggregate"]["ev_windows_regressed"],
                    promotion_pool[name]["aggregate"]["expected_value_score_delta_sum"],
                    promotion_pool[name]["aggregate"]["total_pnl_delta_sum"],
                ),
            )
            if promotion_pool else None
        )
        best = summary.get(best_variant) if best_variant else None
        economic_gate4 = False
        promotion_ready = False
        if best:
            agg = best["aggregate"]
            economic_gate4 = (
                (
                    agg["expected_value_score_delta_sum"]
                    / sum(item["metrics"]["expected_value_score"] for item in baseline_by_window.values())
                    > 0.10
                )
                or (agg["total_pnl_delta_pct"] is not None and agg["total_pnl_delta_pct"] > 0.05)
            ) and agg["ev_windows_improved"] >= 2
            promotion_ready = bool(
                economic_gate4
                and agg["win_rate_delta_min"] >= 0
                and agg["max_drawdown_delta_max"] <= 0.01
            )

        payload = {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": (
                "accepted_candidate" if promotion_ready else
                "observed_positive_deferred" if economic_gate4 else
                "rejected"
            ),
            "decision": (
                "accepted_candidate" if promotion_ready else
                "deferred" if economic_gate4 else
                "rejected"
            ),
            "lane": "alpha_search",
            "change_type": "candidate_universe_semicap_equipment",
            "hypothesis": (
                "Liquid semiconductor equipment and compute supplier leaders may "
                "improve the A+B candidate pool by adding durable AI-cycle exposure "
                "without broad ETF or noisy small-cap universe dilution."
            ),
            "alpha_hypothesis_category": "candidate_universe",
            "parameters": {
                "single_causal_variable": "tradeable universe membership",
                "candidate_group": CANDIDATE_GROUP,
                "tested_variants": variants,
                "already_present": already_present,
                "new_candidates": new_candidates,
                "sector_map_patch": SECTOR_PATCH,
                "locked_variables": [
                    "signal generation",
                    "entry filters",
                    "candidate ranking",
                    "position sizing",
                    "MAX_POSITIONS",
                    "MAX_POSITION_PCT",
                    "MAX_PORTFOLIO_HEAT",
                    "MAX_PER_SECTOR",
                    "gap cancels",
                    "add-ons",
                    "all exits",
                    "LLM/news replay",
                    "earnings strategy",
                ],
            },
            "coverage": coverage,
            "tradeable_by_all_windows": tradeable_by_all_windows,
            "snapshot_comparison_policy": {
                "baseline": "canonical base snapshots from docs/backtesting.md",
                "variants": "augmented snapshots containing only added candidate OHLCV",
                "reason": (
                    "Backtester context can depend on loaded OHLCV keys, so baseline "
                    "must not load added candidate rows."
                ),
            },
            "date_range": {
                "primary": "2025-10-23 -> 2026-04-21",
                "secondary": [
                    "2025-04-23 -> 2025-10-22",
                    "2024-10-02 -> 2025-04-22",
                ],
            },
            "market_regime_summary": {
                label: window["state_note"] for label, window in WINDOWS.items()
            },
            "before_metrics": {
                label: item["metrics"] for label, item in baseline_by_window.items()
            },
            "after_metrics": summary,
            "best_variant": best_variant,
            "best_variant_economic_gate4": economic_gate4,
            "best_variant_promotion_ready": promotion_ready,
            "gate4_basis": (
                "Accepted candidate: best variant passed economic Gate 4 plus "
                "win-rate and drawdown promotion guards."
                if promotion_ready else
                "Observed positive but deferred: best variant passed economic "
                "Gate 4, but promotion guards failed."
                if economic_gate4 else
                "Rejected: no tested semiconductor equipment universe variant "
                "cleared the fixed-window Gate 4 materiality and stability requirements."
            ),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "promotion_requirement": (
                    "If accepted, add selected tickers to filter._BASE_WATCHLIST "
                    "and tickers.COMMON_TICKERS, ensure risk_engine.SECTOR_MAP "
                    "contains sector tags, then rerun canonical production-code windows."
                ),
            },
            "llm_metrics": {
                "used_llm": False,
                "blocker_relation": (
                    "LLM soft-ranking and SEC filing ranking remain sample-limited, "
                    "so this tests a deterministic candidate-pool alpha instead."
                ),
            },
            "history_guardrails": {
                "not_etf_expansion_repeat": True,
                "not_raw_ai_infra_repeat": True,
                "uses_liquid_large_cap_individual_names": True,
                "production_promotion_requires_shared_watchlist_change": True,
            },
            "rejection_reason": (
                None if promotion_ready else
                "The tested candidate-pool change did not satisfy the full promotion gate."
            ),
            "rows": rows,
            "related_files": [
                str(OUT_JSON.relative_to(REPO_ROOT)),
                str(LOG_JSON.relative_to(REPO_ROOT)),
                str(TICKET_JSON.relative_to(REPO_ROOT)),
                f"quant/experiments/{Path(__file__).name}",
            ],
        }

        OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        LOG_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        ticket = {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "title": "Semicap equipment watchlist scout",
            "summary": (
                f"Best {best_variant} economic_gate4={economic_gate4} "
                f"promotion_ready={promotion_ready}"
            ),
            "best_variant": best_variant,
            "best_aggregate": best["aggregate"] if best else None,
            "production_impact": payload["production_impact"],
        }
        TICKET_JSON.write_text(json.dumps(ticket, indent=2, ensure_ascii=False), encoding="utf-8")
        with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
            compact = {k: v for k, v in payload.items() if k not in ("rows", "coverage")}
            handle.write(json.dumps(compact, ensure_ascii=False) + "\n")

        print(json.dumps({
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "best_variant": best_variant,
            "best_aggregate": best["aggregate"] if best else None,
            "economic_gate4": economic_gate4,
            "promotion_ready": promotion_ready,
            "tradeable_by_all_windows": tradeable_by_all_windows,
            "already_present": already_present,
        }, indent=2, ensure_ascii=False))
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original_sector_map)


if __name__ == "__main__":
    main()
