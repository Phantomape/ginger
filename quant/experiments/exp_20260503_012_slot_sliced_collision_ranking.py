"""exp-20260503-012 slot-sliced collision ranking.

Alpha search. Retest relative-strength/TQS only where the accepted entry plan
actually slices same-day candidates for lack of slots. Non-collision days keep
the accepted ordering, which makes this a narrower follow-up to the rejected
global slot-ranking experiment.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260503-012"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "slot_sliced_collision_ranking.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

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
    ("baseline_existing_order", "baseline"),
    ("collision_tqs_then_rs20", "tqs_then_rs20"),
    ("collision_rs20_then_tqs", "rs20_then_tqs"),
    ("collision_conf_then_tqs_rs20", "conf_then_tqs_rs20"),
])


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "slot_sliced_count": (
            (result.get("entry_execution_attribution") or {})
            .get("reason_counts", {})
            .get("slot_sliced", 0)
        ),
        "scarce_slot_breakout_deferred": (
            (result.get("scarce_slot_attribution") or {})
            .get("breakout_deferred", 0)
        ),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _float_value(value: Any, default: float = float("-inf")) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rank(signals: list[dict[str, Any]], variant: str) -> list[dict[str, Any]]:
    if variant == "baseline" or len(signals) <= 1:
        return list(signals)

    def rs20(sig: dict[str, Any]) -> float:
        return _float_value(sig.get("ticker_ret20_minus_spy_pct"))

    def tqs(sig: dict[str, Any]) -> float:
        value = sig.get("trade_quality_score")
        if value is None:
            value = sig.get("confidence_score")
        return _float_value(value, default=0.0)

    def conf(sig: dict[str, Any]) -> float:
        return _float_value(sig.get("confidence_score"), default=0.0)

    if variant == "tqs_then_rs20":
        key = lambda sig: (tqs(sig), rs20(sig), conf(sig))
    elif variant == "rs20_then_tqs":
        key = lambda sig: (rs20(sig), tqs(sig), conf(sig))
    elif variant == "conf_then_tqs_rs20":
        key = lambda sig: (conf(sig), tqs(sig), rs20(sig))
    else:
        raise ValueError(f"Unknown variant: {variant}")
    return sorted(signals, key=key, reverse=True)


@contextmanager
def _collision_rank_patch(variant: str):
    original = backtester.plan_entry_candidates

    def patched(signals, open_positions, *args, **kwargs):
        planned, entry_plan = original(signals, open_positions, *args, **kwargs)
        slot_sliced = list(entry_plan.get("slot_sliced_signals") or [])
        slots = entry_plan.get("available_slots", 0)
        if variant == "baseline" or not slot_sliced or slots <= 0:
            return planned, entry_plan

        combined = list(planned) + slot_sliced
        reranked = _rank(combined, variant)
        new_planned = reranked[:slots]
        new_sliced = reranked[slots:]
        patched_plan = dict(entry_plan)
        patched_plan["slot_sliced_signals"] = new_sliced
        patched_plan["collision_rank_variant"] = variant
        patched_plan["collision_rank_changed"] = [
            {
                "before": [sig.get("ticker") for sig in planned],
                "after": [sig.get("ticker") for sig in new_planned],
                "sliced_before": [sig.get("ticker") for sig in slot_sliced],
                "sliced_after": [sig.get("ticker") for sig in new_sliced],
            }
        ]
        return new_planned, patched_plan

    backtester.plan_entry_candidates = patched
    try:
        yield
    finally:
        backtester.plan_entry_candidates = original


def _run_window(universe: list[str], cfg: dict[str, Any], variant: str) -> dict[str, Any]:
    with _collision_rank_patch(variant):
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
        raise RuntimeError(str(result["error"]))
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
        "entry_execution_attribution": result.get("entry_execution_attribution"),
        "scarce_slot_attribution": result.get("scarce_slot_attribution"),
    }


def _aggregate(by_window: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline_ev_sum = sum(v["before"]["expected_value_score"] for v in by_window.values())
    baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
    total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
    return {
        "expected_value_score_delta_sum": round(
            sum(v["delta"]["expected_value_score"] for v in by_window.values()),
            6,
        ),
        "expected_value_score_delta_pct": round(
            sum(v["delta"]["expected_value_score"] for v in by_window.values()) / baseline_ev_sum,
            6,
        ) if baseline_ev_sum else None,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6),
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
        "max_drawdown_delta_max": max(
            v["delta"]["max_drawdown_pct"] for v in by_window.values()
        ),
        "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
        "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
        "slot_sliced_delta_sum": sum(v["delta"]["slot_sliced_count"] for v in by_window.values()),
    }


def _append_log(payload: dict[str, Any]) -> None:
    if EXPERIMENT_LOG.exists():
        existing = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace")
        if f'"experiment_id":"{EXPERIMENT_ID}"' in existing or f'"experiment_id": "{EXPERIMENT_ID}"' in existing:
            return
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": "alpha_search_agent",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "single_causal_variable": payload["parameters"]["single_causal_variable"],
        "completed_at": payload["timestamp"],
        "result": {
            "best_variant": payload["after_metrics"]["best_variant"],
            "aggregate": payload["delta_metrics"]["aggregate"],
            "gate4_basis": payload["gate4_basis"],
        },
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _update_registry(payload: dict[str, Any]) -> None:
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8")) if REGISTRY_JSON.exists() else {
        "schema_version": 1,
        "experiments": [],
    }
    updated = False
    for item in registry.get("experiments", []):
        if item.get("experiment_id") == EXPERIMENT_ID:
            item.update({
                "status": payload["status"],
                "lane": payload["lane"],
                "owner": "alpha_search_agent",
                "hypothesis": payload["hypothesis"],
                "ticket_file": str(TICKET_JSON.relative_to(REPO_ROOT)),
                "updated_at": payload["timestamp"],
            })
            updated = True
            break
    if not updated:
        registry.setdefault("experiments", []).append({
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": payload["lane"],
            "owner": "alpha_search_agent",
            "hypothesis": payload["hypothesis"],
            "ticket_file": str(TICKET_JSON.relative_to(REPO_ROOT)),
            "updated_at": payload["timestamp"],
        })
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _build_payload() -> dict[str, Any]:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant_name, variant in VARIANTS.items():
            result = _run_window(universe, cfg, variant)
            row = {
                "window": label,
                "variant": variant_name,
                "ranking_variant": variant,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                **result,
            }
            rows.append(row)
            m = result["metrics"]
            print(
                f"[{label} {variant_name}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} slot_sliced={m['slot_sliced_count']}"
            )

    baseline_rows = {
        label: next(r for r in rows if r["window"] == label and r["variant"] == "baseline_existing_order")
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant_name in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            before = baseline_rows[label]["metrics"]
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant_name)
            by_window[label] = {
                "before": before,
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], before),
            }
        summary[variant_name] = {
            "by_window": by_window,
            "aggregate": _aggregate(by_window),
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["ev_windows_improved"],
            -item[1]["aggregate"]["ev_windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    accepted = (
        best_agg["ev_windows_improved"] >= 2
        and (
            best_agg["expected_value_score_delta_pct"] is not None
            and best_agg["expected_value_score_delta_pct"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (
                best_agg["trade_count_delta_sum"] > 0
                and best_agg["win_rate_delta_min"] >= 0
            )
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "accepted_candidate_needs_shared_policy" if accepted else "rejected",
        "decision": "deferred_until_shared_policy" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "slot_sliced_collision_ranking",
        "hypothesis": (
            "Only on days where survived candidates are slot-sliced, ranking the "
            "collision set by TQS and/or medium-term relative strength may improve "
            "scarce-slot capital allocation without changing non-collision entries."
        ),
        "parameters": {
            "single_causal_variable": "candidate ranking only inside slot-sliced collision sets",
            "baseline_order": "accepted production_parity.plan_entry_candidates order",
            "tested_orders": list(VARIANTS.keys())[1:],
            "fields_used": [
                "ticker_ret20_minus_spy_pct",
                "trade_quality_score",
                "confidence_score",
            ],
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "position sizing",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "scarce-slot breakout deferral thresholds",
                "add-ons",
                "all exits",
                "LLM/news replay",
                "earnings strategy",
                "non-slot-sliced entry days",
            ],
        },
        "date_range": {
            "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": {label: baseline_rows[label]["metrics"] for label in WINDOWS},
        "after_metrics": {
            "best_variant": best_variant,
            **{label: best_summary["by_window"][label]["after"] for label in WINDOWS},
        },
        "delta_metrics": {
            "best_variant": best_variant,
            "by_window": {label: best_summary["by_window"][label]["delta"] for label in WINDOWS},
            "aggregate": best_agg,
        },
        "all_variant_summaries": summary,
        "gate4_basis": (
            "Positive replay found, but not accepted until implemented through shared production/backtest policy."
            if accepted else
            "Rejected because no collision-only ranking variant cleared the fixed-window Gate 4 materiality and stability bar."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "A positive result must be implemented as a shared production_parity "
                "collision-ranking helper before it can affect live entries."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": "LLM soft-ranking remains sample-limited; this uses production-available deterministic fields.",
        },
        "history_guardrails": {
            "not_global_rs_slot_ranking_repeat": True,
            "only_changes_days_with_slot_sliced_candidates": True,
            "not_universe_expansion": True,
            "not_sizing_multiplier_retry": True,
            "not_exit_lifecycle_retry": True,
        },
        "rejection_reason": None if accepted else (
            "The narrower slot-sliced collision ranking did not improve a majority of windows with material aggregate EV/PnL evidence."
        ),
        "next_retry_requires": [
            "Do not retry global pre-slot RS/TQS sorting.",
            "Do not retry collision ranking unless a new discriminator is limited to the exact losing collision cases.",
            "Any positive ranking retry must be production/backtest shared before promotion.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            f"quant/experiments/{Path(__file__).name}",
        ],
    }
    return payload


def main() -> int:
    payload = _build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    _write_ticket(payload)
    _update_registry(payload)
    _append_log(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "best_variant": payload["after_metrics"]["best_variant"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "wrote": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
