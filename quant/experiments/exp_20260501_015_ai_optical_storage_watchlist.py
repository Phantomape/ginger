"""exp-20260501-015 AI optical/storage watchlist test.

Alpha search. Test whether the cleanest AI infrastructure sub-theme from the
prior robustness audit, INTC + LITE, is stable enough for production watchlist
promotion. This changes one causal variable: tradeable universe membership.
Signal generation, ranking, sizing, exits, add-ons, LLM/news replay, and all
thresholds stay locked.
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
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260501-015"
SOURCE_EXPERIMENT_ID = "exp-20260501-008"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "ai_optical_storage_watchlist.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20251023_20260421.json"
        ),
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20250423_20251022.json"
        ),
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": (
            f"data/experiments/{SOURCE_EXPERIMENT_ID}/"
            "ohlcv_aug_20241002_20250422.json"
        ),
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("add_intc_lite", ["INTC", "LITE"]),
    ("add_lite_only", ["LITE"]),
    ("add_intc_only_control", ["INTC"]),
])

SECTOR_PATCH = {
    "INTC": "Technology",
    "LITE": "Technology",
}

BASELINE = {
    "late_strong": {
        "expected_value_score": 2.7000,
        "sharpe_daily": 4.30,
        "total_pnl": 62788.03,
        "total_return_pct": 0.6279,
        "max_drawdown_pct": 0.0439,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
        "tail_loss_share": 0.5045,
    },
    "mid_weak": {
        "expected_value_score": 1.2036,
        "sharpe_daily": 2.58,
        "total_pnl": 46654.10,
        "total_return_pct": 0.4665,
        "max_drawdown_pct": 0.0799,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
        "tail_loss_share": 0.4839,
    },
    "old_thin": {
        "expected_value_score": 0.2563,
        "sharpe_daily": 1.27,
        "total_pnl": 20181.65,
        "total_return_pct": 0.2018,
        "max_drawdown_pct": 0.0688,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
        "tail_loss_share": 0.4234,
    },
}


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
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
            if isinstance(after_val, (int, float))
            and isinstance(before_val, (int, float))
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
        rec["win_rate"] = (
            round(rec["wins"] / rec["trades"], 4) if rec["trades"] else None
        )
    return {
        "candidate_trade_count": len(trades),
        "candidate_pnl": round(sum(float(t.get("pnl") or 0.0) for t in trades), 2),
        "by_ticker": by_ticker,
    }


def _run_window(universe: list[str], window: dict) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    )
    return engine.run()


def _aggregate(variant_rows: list[dict]) -> dict:
    pnl_delta_sum = round(sum(r["delta"]["total_pnl"] for r in variant_rows), 2)
    baseline_pnl_sum = round(
        sum(BASELINE[r["window"]]["total_pnl"] for r in variant_rows), 2
    )
    candidate_pnl_sum = round(
        sum(r["candidate_trades"]["candidate_pnl"] for r in variant_rows), 2
    )
    return {
        "expected_value_score_delta_sum": round(
            sum(r["delta"]["expected_value_score"] for r in variant_rows), 4
        ),
        "total_pnl_delta_sum": pnl_delta_sum,
        "baseline_total_pnl_sum": baseline_pnl_sum,
        "total_pnl_delta_pct": (
            round(pnl_delta_sum / baseline_pnl_sum, 6) if baseline_pnl_sum else None
        ),
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
            max(r["delta"]["max_drawdown_pct"] for r in variant_rows), 6
        ),
        "trade_count_delta_sum": sum(r["delta"]["trade_count"] for r in variant_rows),
        "win_rate_delta_min": round(min(r["delta"]["win_rate"] for r in variant_rows), 6),
        "candidate_trade_count_sum": sum(
            r["candidate_trades"]["candidate_trade_count"] for r in variant_rows
        ),
        "candidate_pnl_sum": candidate_pnl_sum,
        "interaction_pnl_sum": round(pnl_delta_sum - candidate_pnl_sum, 2),
    }


def _ranked(summary: dict) -> list[dict]:
    rows = []
    for name, rec in summary.items():
        agg = rec["aggregate"]
        rows.append({
            "variant": name,
            "added": rec["added"],
            "ev_delta_sum": agg["expected_value_score_delta_sum"],
            "pnl_delta_sum": agg["total_pnl_delta_sum"],
            "candidate_pnl_sum": agg["candidate_pnl_sum"],
            "ev_windows_improved": agg["ev_windows_improved"],
            "ev_windows_regressed": agg["ev_windows_regressed"],
            "pnl_windows_improved": agg["pnl_windows_improved"],
            "pnl_windows_regressed": agg["pnl_windows_regressed"],
            "max_drawdown_delta_max": agg["max_drawdown_delta_max"],
            "win_rate_delta_min": agg["win_rate_delta_min"],
            "candidate_trade_count_sum": agg["candidate_trade_count_sum"],
        })
    return sorted(
        rows,
        key=lambda r: (
            r["ev_windows_improved"] - r["ev_windows_regressed"],
            r["ev_delta_sum"],
            r["pnl_delta_sum"],
        ),
        reverse=True,
    )


def _append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in existing:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    baseline_universe = sorted(get_universe())
    original_sector_map = dict(risk_engine.SECTOR_MAP)
    risk_engine.SECTOR_MAP.update(SECTOR_PATCH)

    summary = {}
    try:
        for variant, added in VARIANTS.items():
            universe = sorted(set(baseline_universe) | set(added))
            variant_rows = []
            for label, window in WINDOWS.items():
                result = _run_window(universe, window)
                if "error" in result:
                    raise RuntimeError(f"{variant} {label} failed: {result['error']}")
                metrics = _metrics(result)
                delta = _delta(metrics, BASELINE[label])
                row = {
                    "window": label,
                    "variant": variant,
                    "added": added,
                    "metrics": metrics,
                    "delta": delta,
                    "candidate_trades": _candidate_trade_summary(result, set(added)),
                }
                variant_rows.append(row)

            summary[variant] = {
                "added": added,
                "by_window": {
                    r["window"]: {
                        "before": BASELINE[r["window"]],
                        "after": r["metrics"],
                        "delta": r["delta"],
                        "candidate_trades": r["candidate_trades"],
                    }
                    for r in variant_rows
                },
                "aggregate": _aggregate(variant_rows),
            }
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original_sector_map)

    ranked = _ranked(summary)
    best_variant = ranked[0]["variant"]
    best = summary[best_variant]["aggregate"]
    best_gate4_passed = (
        best["total_pnl_delta_pct"] > 0.05
        and best["ev_windows_improved"] >= 2
        and best["ev_windows_regressed"] == 0
        and best["win_rate_delta_min"] >= 0
    )
    decision = "accepted" if best_gate4_passed else "rejected"
    rejection_reason = None if best_gate4_passed else (
        "The clean optical/storage subset did not satisfy the multi-window EV "
        "and win-rate stability gate for production watchlist promotion."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "candidate_universe",
        "hypothesis": (
            "A narrow AI infrastructure optical/storage-semi watchlist using "
            "INTC + LITE can preserve the upside seen in the broader AI infra "
            "pool while avoiding the BE old-tape fragility."
        ),
        "alpha_hypothesis_category": "candidate_universe",
        "parameters": {
            "single_causal_variable": "tradeable universe membership",
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "tested_variants": VARIANTS,
            "sector_map_patch": SECTOR_PATCH,
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "position caps",
                "portfolio heat",
                "add-ons",
                "exits",
                "LLM/news replay",
                "earnings strategy",
            ],
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
        "before_metrics": BASELINE,
        "after_metrics": summary,
        "ranking": ranked,
        "best_variant": best_variant,
        "best_variant_gate4_passed": best_gate4_passed,
        "gate4_basis": (
            "Acceptance requires aggregate PnL > +5%, EV improvement in at "
            "least two windows without any EV regression, and no win-rate "
            "decline because this is a production watchlist expansion."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add the selected tickers to filter.WATCHLIST, "
                "tickers.COMMON_TICKERS, and risk_engine.SECTOR_MAP, then rerun "
                "canonical three-window backtests on production code."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this tests a "
                "deterministic candidate-pool alpha instead."
            ),
        },
        "history_guardrails": {
            "builds_on_exp_20260501_008": True,
            "builds_on_exp_20260501_010": True,
            "not_be_intc_repeat": True,
            "why_not_simple_repeat": (
                "The tested subset explicitly removes BE, TLN, VST, DBRG, and "
                "miners, isolating optical/storage-semi exposure."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [] if best_gate4_passed else [
            "Forward evidence for INTC/LITE or an event/news discriminator.",
            "A theme-level rule that improves at least two windows without "
            "win-rate degradation.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260501_015_ai_optical_storage_watchlist.py",
        ],
    }

    for path in (OUT_JSON, LOG_JSON, TICKET_JSON):
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    jsonl_record = {
        key: payload[key]
        for key in [
            "experiment_id",
            "timestamp",
            "status",
            "decision",
            "lane",
            "change_type",
            "hypothesis",
            "alpha_hypothesis_category",
            "parameters",
            "date_range",
            "market_regime_summary",
            "before_metrics",
            "best_variant",
            "gate4_basis",
            "production_impact",
            "llm_metrics",
            "history_guardrails",
            "rejection_reason",
            "next_retry_requires",
            "related_files",
        ]
    }
    jsonl_record["after_metrics"] = {
        name: rec["aggregate"] for name, rec in summary.items()
    }
    _append_once(
        EXPERIMENT_LOG,
        f'"experiment_id": "{EXPERIMENT_ID}"',
        json.dumps(jsonl_record, ensure_ascii=False) + "\n",
    )

    if not best_gate4_passed:
        playbook_text = f"""

### 2026-05-01 mechanism update: AI optical/storage watchlist

Status: rejected.

Core conclusion: `{EXPERIMENT_ID}` tested whether the cleaner AI infrastructure
optical/storage-semi subset (`INTC + LITE`) could avoid the BE old-tape
fragility seen in the broader pool. It should not be promoted.

Evidence: best variant `{best_variant}` produced aggregate PnL delta
`${best['total_pnl_delta_sum']:,.2f}` / `{best['total_pnl_delta_pct']:.2%}` and
aggregate EV delta `{best['expected_value_score_delta_sum']:+.4f}`. It did not
clear the multi-window production gate: EV improved in
`{best['ev_windows_improved']}` windows, regressed in
`{best['ev_windows_regressed']}`, and minimum win-rate delta was
`{best['win_rate_delta_min']:+.4f}`.

Mechanism insight: removing the fragile power names cleans up the old-tape loss
source, but the remaining optical/storage-semi effect is still too
late-window-concentrated for a raw production watchlist addition.

Do not repeat: promoting `INTC + LITE`, `LITE` alone, or `INTC` alone as a raw
watchlist addition without forward evidence or event/news confirmation.

Next valid retry requires: forward evidence, a point-in-time event/news
discriminator, or a broader theme rule that improves at least two fixed windows
without win-rate degradation.
"""
        _append_once(PLAYBOOK, f"`{EXPERIMENT_ID}`", playbook_text)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "best_variant": best_variant,
        "best_aggregate": best,
        "ranking": ranked,
    }, indent=2))


if __name__ == "__main__":
    main()
