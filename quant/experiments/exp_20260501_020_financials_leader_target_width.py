"""exp-20260501-020 Financials sector-leader target-width sweep.

Alpha search. The accepted Financials sector-leader rule proved that relative
20-day leadership can justify more risk budget. This tests one separate causal
variable: whether the same leader discriminator also justifies a wider target.
Entries, ranking, sizing, slot caps, add-ons, LLM/news replay, and all non-
Financials exits remain locked.
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

import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import _retarget_signal_with_atr_mult  # noqa: E402


EXPERIMENT_ID = "exp-20260501-020"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "financials_leader_target_width.json"
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

BASELINE_TARGET_ATR = 4.5
TESTED_TARGET_ATR = OrderedDict([
    ("financials_leader_5_0atr", 5.0),
    ("financials_leader_5_5atr", 5.5),
    ("financials_leader_6_0atr", 6.0),
])


def _metrics(result: dict, target_mult: float | None = None) -> dict:
    benchmarks = result.get("benchmarks") or {}
    leader_trade_count = 0
    leader_trade_pnl = 0.0
    retargeted_trades = 0
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        if multipliers.get("financials_sector_leader_risk_multiplier_applied"):
            leader_trade_count += 1
            leader_trade_pnl += float(trade.get("pnl") or 0.0)
        if (
            target_mult is not None
            and multipliers.get("financials_sector_leader_risk_multiplier_applied")
            and trade.get("target_mult_used") == target_mult
        ):
            retargeted_trades += 1
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
        "financials_leader_trade_count": leader_trade_count,
        "financials_leader_trade_pnl": round(leader_trade_pnl, 2),
        "retargeted_trades": retargeted_trades,
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


def _run_window(universe: list[str], cfg: dict) -> dict:
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
    return result


def _install_target_patch(target_mult: float):
    original = risk_engine.enrich_signals

    def patched(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            if (
                sig.get("strategy") == "trend_long"
                and sig.get("sector") == "Financials"
                and sig.get("financials_sector_leader") is True
            ):
                atr = (features_dict.get(sig.get("ticker")) or {}).get("atr")
                if atr:
                    sig.update(_retarget_signal_with_atr_mult(sig, atr, target_mult))
                    sig["financials_sector_leader_target_width_applied"] = target_mult
        return enriched

    risk_engine.enrich_signals = patched
    return original


def _run_baseline(universe: list[str]) -> OrderedDict:
    rows = OrderedDict()
    for label, cfg in WINDOWS.items():
        result = _run_window(universe, cfg)
        rows[label] = {
            "metrics": _metrics(result),
            "leader_trades": _leader_trades(result),
        }
        m = rows[label]["metrics"]
        print(
            f"[{label}] baseline EV={m['expected_value_score']} "
            f"PnL={m['total_pnl']} DD={m['max_drawdown_pct']}"
        )
    return rows


def _run_variant(universe: list[str], name: str, target_mult: float) -> OrderedDict:
    original = _install_target_patch(target_mult)
    try:
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            result = _run_window(universe, cfg)
            rows[label] = {
                "metrics": _metrics(result, target_mult=target_mult),
                "leader_trades": _leader_trades(result),
            }
            m = rows[label]["metrics"]
            print(
                f"[{label}] {name} EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} DD={m['max_drawdown_pct']} "
                f"retargeted={m['retargeted_trades']}"
            )
        return rows
    finally:
        risk_engine.enrich_signals = original


def _leader_trades(result: dict) -> list[dict]:
    rows = []
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        if not multipliers.get("financials_sector_leader_risk_multiplier_applied"):
            continue
        rows.append({
            "ticker": trade.get("ticker"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "exit_reason": trade.get("exit_reason"),
            "pnl": trade.get("pnl"),
            "target_mult_used": trade.get("target_mult_used"),
        })
    return rows


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    total_pnl_delta = round(
        sum(deltas[label]["total_pnl"] for label in WINDOWS), 2
    )
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": round(
            sum(deltas[label]["expected_value_score"] for label in WINDOWS),
            6,
        ),
        "baseline_expected_value_score_sum": round(
            sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
            6,
        ),
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": (
            round(total_pnl_delta / baseline_total_pnl, 6)
            if baseline_total_pnl else None
        ),
        "ev_windows_improved": sum(
            1 for label in WINDOWS
            if deltas[label]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for label in WINDOWS
            if deltas[label]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for label in WINDOWS if deltas[label]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for label in WINDOWS if deltas[label]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": max(
            deltas[label]["max_drawdown_pct"] for label in WINDOWS
        ),
        "trade_count_delta_sum": sum(deltas[label]["trade_count"] for label in WINDOWS),
        "win_rate_delta_min": min(deltas[label]["win_rate"] for label in WINDOWS),
        "sharpe_daily_delta_max": max(
            deltas[label]["sharpe_daily"] for label in WINDOWS
        ),
        "retargeted_trades_delta_sum": sum(
            deltas[label]["retargeted_trades"] for label in WINDOWS
        ),
    }


def _passes_gate4(aggregate: dict) -> bool:
    baseline_ev = aggregate["baseline_expected_value_score_sum"]
    ev_delta = aggregate["expected_value_score_delta_sum"]
    pnl_delta_pct = aggregate["total_pnl_delta_pct"]
    return (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["ev_windows_regressed"] == 0
        and (
            (baseline_ev and ev_delta / baseline_ev > 0.10)
            or aggregate["sharpe_daily_delta_max"] > 0.1
            or aggregate["max_drawdown_delta_max"] < -0.01
            or (pnl_delta_pct is not None and pnl_delta_pct > 0.05)
            or (
                aggregate["trade_count_delta_sum"] > 0
                and aggregate["win_rate_delta_min"] >= 0
            )
        )
    )


def main() -> int:
    universe = get_universe()
    before = _run_baseline(universe)
    variants = OrderedDict()
    deltas = OrderedDict()
    for name, target_mult in TESTED_TARGET_ATR.items():
        rows = _run_variant(universe, name, target_mult)
        variants[name] = rows
        deltas[name] = _aggregate(before, rows)

    best_variant = max(
        deltas,
        key=lambda name: deltas[name]["expected_value_score_delta_sum"],
    )
    best_gate4 = _passes_gate4(deltas[best_variant])
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if best_gate4 else "rejected",
        "decision": "accepted" if best_gate4 else "rejected",
        "lane": "alpha_search",
        "change_type": "exit_lifecycle_financials_leader_target_width",
        "hypothesis": (
            "Financials trend signals that are 20-day sector-relative leaders "
            "may deserve a wider target, because the accepted risk-budget rule "
            "showed this discriminator identifies stronger Financials exposure."
        ),
        "alpha_hypothesis_category": "exit_lifecycle",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin, so this "
            "tests an alternate deterministic lifecycle alpha using existing "
            "sector-relative leader fields."
        ),
        "parameters": {
            "single_causal_variable": "Financials sector-leader trend target ATR width",
            "baseline_target_atr": BASELINE_TARGET_ATR,
            "tested_target_atr": TESTED_TARGET_ATR,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all sizing multipliers including accepted Financials leader 2.5x",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all non-Financials targets",
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
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: before[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            name: {
                label: variants[name][label]["metrics"] for label in WINDOWS
            }
            for name in TESTED_TARGET_ATR
        },
        "delta_metrics": deltas,
        "best_variant": best_variant,
        "best_variant_gate4": best_gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted later, implement in shared risk_engine target "
                "assignment so run.py and backtester.py receive identical "
                "target_price fields."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this is an alternate "
                "deterministic alpha search."
            ),
        },
        "history_guardrails": {
            "not_broad_financials_target_retry": True,
            "not_financials_leader_risk_multiplier_retry": True,
            "why_not_simple_repeat": (
                "This only tests target width for the already accepted "
                "Financials sector-leader subset; it does not retry broad "
                "Financials 6ATR targets or nearby leader risk multipliers."
            ),
        },
        "leader_trades": {
            "baseline": before,
            **{name: variants[name] for name in TESTED_TARGET_ATR},
        },
        "rejection_reason": (
            "Financials sector-leader target widening damaged mid_weak and "
            "old_thin because delayed exits converted or enlarged leader "
            "losses; the accepted leader risk-budget edge does not transfer "
            "to target extension."
        ) if not best_gate4 else None,
        "next_retry_requires": [
            "Do not retry nearby Financials leader target widths without event/news or forward evidence.",
            "Do not infer exit convexity from accepted Financials leader sizing.",
            "Future Financials lifecycle work needs a discriminator that avoids delayed-exit damage in mid_weak and old_thin.",
        ] if not best_gate4 else [],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": artifact["status"],
        "lane": artifact["lane"],
        "hypothesis": artifact["hypothesis"],
        "best_variant": best_variant,
        "best_variant_gate4": best_gate4,
        "next_retry_requires": artifact["next_retry_requires"],
        "artifacts": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
        ],
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2), encoding="utf-8")

    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(artifact, ensure_ascii=False) + "\n")

    print(f"wrote {OUT_JSON}")
    print(f"wrote {LOG_JSON}")
    print(f"wrote {TICKET_JSON}")
    print(f"best_variant={best_variant} gate4={best_gate4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
