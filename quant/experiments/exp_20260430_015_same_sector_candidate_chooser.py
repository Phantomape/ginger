"""exp-20260430-015 same-sector candidate chooser.

Alpha search. The global sector cap value stays fixed at 2; this tests only
which candidates survive inside an overfull same-day sector bucket before the
shared production/backtest entry filter applies the cap.
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

import backtester as bt  # noqa: E402
import production_parity as pp  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260430-015"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260430_015_same_sector_candidate_chooser.json"
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
    ("baseline_native_sector_order", None),
    ("same_sector_tqs_desc", "trade_quality_score"),
    ("same_sector_confidence_desc", "confidence_score"),
])


def _metrics(result: dict) -> dict:
    reasons = result.get("entry_execution_attribution", {}).get("reason_counts") or {}
    entry_filter = result.get("entry_filter_audit") or {}
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
        "sector_cap_dropped": len(entry_filter.get("sector_cap_dropped") or []),
        "entered": reasons.get("entered"),
        "slot_sliced": reasons.get("slot_sliced"),
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


def _sector_sorted_filter(original_filter, sort_key):
    def wrapper(
        signals,
        open_positions=None,
        active_tickers=None,
        market_regime=None,
        spy_pct_from_ma=None,
        qqq_pct_from_ma=None,
        max_per_sector=pp.MAX_PER_SECTOR,
    ):
        if sort_key is None:
            return original_filter(
                signals,
                open_positions=open_positions,
                active_tickers=active_tickers,
                market_regime=market_regime,
                spy_pct_from_ma=spy_pct_from_ma,
                qqq_pct_from_ma=qqq_pct_from_ma,
                max_per_sector=max_per_sector,
            )

        held = set(active_tickers or [])
        held.update(
            p.get("ticker")
            for p in pp._positive_positions(open_positions)
        )
        held.discard(None)

        planned = []
        audit = {
            "signals_before_entry_filters": len(signals or []),
            "already_held_dropped": [],
            "sector_cap_dropped": [],
            "bear_shallow_dropped": [],
            "signals_after_entry_filters": None,
            "max_per_sector": max_per_sector,
            "bear_shallow_active": False,
        }
        for sig in signals or []:
            if sig.get("ticker") in held:
                audit["already_held_dropped"].append(sig)
            else:
                planned.append(sig)

        by_sector = {}
        for idx, sig in enumerate(planned):
            by_sector.setdefault(sig.get("sector", "Unknown"), []).append((idx, sig))

        keep_indexes = set()
        for rows in by_sector.values():
            ranked = sorted(
                rows,
                key=lambda item: (
                    -float(item[1].get(sort_key) if item[1].get(sort_key) is not None else -999.0),
                    item[0],
                ),
            )
            for idx, _sig in ranked[:max_per_sector]:
                keep_indexes.add(idx)
            for _idx, dropped in ranked[max_per_sector:]:
                audit["sector_cap_dropped"].append(dropped)

        sorted_signals = [
            sig for idx, sig in enumerate(planned)
            if idx in keep_indexes
        ]

        regime = str(market_regime or "").upper()
        bear_shallow = (
            regime == "BEAR"
            and spy_pct_from_ma is not None
            and qqq_pct_from_ma is not None
            and min(spy_pct_from_ma, qqq_pct_from_ma) > -0.05
        )
        audit["bear_shallow_active"] = bear_shallow
        if bear_shallow:
            bear_sectors = {"Commodities", "Healthcare"}
            kept = []
            for sig in sorted_signals:
                if (
                    sig.get("sector") in bear_sectors
                    and (sig.get("trade_quality_score") or 0) >= 0.75
                ):
                    kept.append(sig)
                else:
                    audit["bear_shallow_dropped"].append(sig)
            sorted_signals = kept

        audit["signals_after_entry_filters"] = len(sorted_signals)
        return sorted_signals, audit

    return wrapper


def _run_window(universe: list[str], cfg: dict, sort_key: str | None) -> dict:
    original_pp_filter = pp.filter_entry_signal_candidates
    original_bt_filter = bt.filter_entry_signal_candidates
    patched = _sector_sorted_filter(original_pp_filter, sort_key)
    pp.filter_entry_signal_candidates = patched
    bt.filter_entry_signal_candidates = patched
    try:
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
    finally:
        pp.filter_entry_signal_candidates = original_pp_filter
        bt.filter_entry_signal_candidates = original_bt_filter

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
        "entry_filter_audit": result.get("entry_filter_audit"),
        "entry_execution_attribution": result.get("entry_execution_attribution"),
    }


def _build_payload() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, sort_key in VARIANTS.items():
            result = _run_window(universe, cfg, sort_key)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "same_sector_sort_key": sort_key,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} sector_drop={m['sector_cap_dropped']}"
            )

    baseline_rows = {
        label: next(
            r for r in rows
            if r["window"] == label and r["variant"] == "baseline_native_sector_order"
        )
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = baseline_rows[label]
            candidate = next(
                r for r in rows if r["window"] == label and r["variant"] == variant
            )
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6),
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
                "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
                "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
            },
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["windows_improved"],
            -item[1]["aggregate"]["windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    accepted = (
        best_agg["windows_improved"] >= 2
        and best_agg["expected_value_score_delta_sum"] > 0.10
        and (
            best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "entry_candidate_same_sector_chooser",
        "hypothesis": (
            "When the same-day sector cap has to drop candidates, choosing the "
            "highest-quality candidates inside each sector may improve capital "
            "allocation without changing the global sector cap."
        ),
        "parameters": {
            "single_causal_variable": "same-sector candidate ordering before MAX_PER_SECTOR cap",
            "baseline": "native order inside each sector",
            "tested_values": {
                "same_sector_tqs_desc": "sort only within sector by trade_quality_score descending",
                "same_sector_confidence_desc": "sort only within sector by confidence_score descending",
            },
            "locked_variables": [
                "signal generation",
                "global candidate ordering across sectors",
                "MAX_PER_SECTOR value",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "all sizing multipliers",
                "scarce-slot breakout deferral",
                "upside/adverse gap cancels",
                "add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
        },
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline_rows[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            "best_variant": best_variant,
            **{
                label: best_summary["by_window"][label]["after"]
                for label in WINDOWS
            },
        },
        "delta_metrics": {
            **{
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
        },
        "gate4_basis": (
            "Accepted by fixed-window Gate 4."
            if accepted
            else "Rejected: no same-sector chooser cleared multi-window Gate 4."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "temporary_shared_helper_patch_tested": True,
            "rolled_back_after_rejection": not accepted,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains data-limited, so this deterministic "
                "same-sector chooser alpha was tested instead."
            ),
        },
        "rejection_reason": (
            None if accepted
            else "The best variant failed expected-value/PnL materiality or window consistency."
        ),
        "do_not_repeat_without_new_evidence": [
            "Simple same-sector TQS or confidence ordering before MAX_PER_SECTOR.",
            "Treating sector-cap candidate survival movement as alpha without executed-trade improvement.",
        ],
        "next_retry_requires": [
            "A state-specific sector crowding discriminator or event/news quality signal.",
            "Evidence that the chosen same-sector replacement beats the dropped candidate after slot and heat constraints.",
        ],
        "rows": rows,
        "related_files": [
            "quant/experiments/exp_20260430_015_same_sector_candidate_chooser.py",
            "data/experiments/exp-20260430-015/exp_20260430_015_same_sector_candidate_chooser.json",
            "docs/experiments/logs/exp-20260430-015.json",
            "docs/experiments/tickets/exp-20260430-015.json",
        ],
    }


def main() -> None:
    payload = _build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    for path in (OUT_JSON, LOG_JSON, TICKET_JSON):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: v for k, v in payload.items() if k != "rows"}, ensure_ascii=False) + "\n")
    print(f"decision={payload['decision']} best={payload['after_metrics']['best_variant']}")
    print(json.dumps(payload["delta_metrics"]["aggregate"], indent=2))


if __name__ == "__main__":
    main()
