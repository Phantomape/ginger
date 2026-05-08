"""exp-20260508-020: same-sector cap quality replay.

Alpha search, replay-only. This experiment tests one narrow allocation idea:
when the existing same-day sector cap would drop candidates, keep the top
same-sector candidates by already-computed quality fields instead of preserving
input order blindly.

It does not change global MAX_PER_SECTOR, signal generation, sizing, exits,
add-ons, scarce-slot routing, LLM/news replay, or the production order path. A
positive result would need to move this policy into production_parity.py and be
called by both run.py and backtester.py before any live effect.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260508-020"
STEM = "sector_cap_quality_replay"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return _safe(value.item())
        except (TypeError, ValueError):
            return str(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _quality_key(signal: dict[str, Any]) -> tuple[float, float, float]:
    pct_from_high = signal.get("pct_from_52w_high")
    return (
        float(signal.get("trade_quality_score") or 0.0),
        float(signal.get("confidence_score") or 0.0),
        float(pct_from_high if pct_from_high is not None else -999.0),
    )


def quality_sector_cap_filter(
    signals,
    open_positions=None,
    active_tickers=None,
    market_regime=None,
    spy_pct_from_ma=None,
    qqq_pct_from_ma=None,
    max_per_sector=2,
):
    """Variant filter: pick top same-sector candidates only when cap binds."""
    planned = list(signals or [])
    audit = {
        "signals_before_entry_filters": len(planned),
        "already_held_dropped": [],
        "sector_cap_dropped": [],
        "bear_shallow_dropped": [],
        "signals_after_entry_filters": None,
        "max_per_sector": max_per_sector,
        "bear_shallow_active": False,
        "sector_cap_policy": "quality_top_n_preserve_global_order",
    }

    held = set(active_tickers or [])
    for pos in (open_positions or {}).get("positions", []):
        if pos.get("ticker") and (pos.get("shares") or 0) > 0:
            held.add(pos.get("ticker"))
    held.discard(None)
    if held:
        kept = []
        for sig in planned:
            if sig.get("ticker") in held:
                audit["already_held_dropped"].append(sig)
            else:
                kept.append(sig)
        planned = kept

    by_sector = defaultdict(list)
    for idx, sig in enumerate(planned):
        by_sector[sig.get("sector", "Unknown")].append((idx, sig))

    keep_idx = set()
    for rows in by_sector.values():
        if len(rows) <= max_per_sector:
            keep_idx.update(idx for idx, _sig in rows)
            continue
        ranked = sorted(rows, key=lambda row: _quality_key(row[1]), reverse=True)
        winners = {idx for idx, _sig in ranked[:max_per_sector]}
        keep_idx.update(winners)
        for idx, sig in rows:
            if idx not in winners:
                dropped = dict(sig)
                dropped["sector_cap_quality_rank_key"] = _quality_key(sig)
                audit["sector_cap_dropped"].append(dropped)

    planned = [sig for idx, sig in enumerate(planned) if idx in keep_idx]

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
        for sig in planned:
            if (
                sig.get("sector") in bear_sectors
                and (sig.get("trade_quality_score") or 0) >= 0.75
            ):
                kept.append(sig)
            else:
                audit["bear_shallow_dropped"].append(sig)
        planned = kept

    audit["signals_after_entry_filters"] = len(planned)
    return planned, audit


def _metric_slice(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "total_trades": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "entry_reason_counts": (
            (result.get("entry_execution_attribution") or {}).get("reason_counts")
            or {}
        ),
    }


def _deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_pnl",
        "total_trades",
        "win_rate",
        "signals_survived",
        "survival_rate",
    ]
    out = {}
    for key in keys:
        if before.get(key) is None or after.get(key) is None:
            out[key] = None
        else:
            out[key] = round(float(after[key]) - float(before[key]), 6)
    return out


def run_window(label: str, spec: dict[str, Any]) -> dict[str, Any]:
    universe = get_universe()
    original_filter = bt.filter_entry_signal_candidates
    try:
        bt.filter_entry_signal_candidates = original_filter
        baseline = bt.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            ohlcv_snapshot_path=str(spec["snapshot"]),
        ).run()
        bt.filter_entry_signal_candidates = quality_sector_cap_filter
        variant = bt.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            ohlcv_snapshot_path=str(spec["snapshot"]),
        ).run()
    finally:
        bt.filter_entry_signal_candidates = original_filter

    before = _metric_slice(baseline)
    after = _metric_slice(variant)
    return {
        "window": label,
        "start": spec["start"],
        "end": spec["end"],
        "snapshot": str(spec["snapshot"].relative_to(REPO_ROOT)).replace("\\", "/"),
        "state_note": spec["state_note"],
        "before": before,
        "after": after,
        "delta": _deltas(before, after),
    }


def _gate4(rows: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate_before_ev = sum(row["before"]["expected_value_score"] for row in rows)
    aggregate_after_ev = sum(row["after"]["expected_value_score"] for row in rows)
    aggregate_before_pnl = sum(row["before"]["total_pnl"] for row in rows)
    aggregate_after_pnl = sum(row["after"]["total_pnl"] for row in rows)
    windows_ev_improved = sum(
        1
        for row in rows
        if row["after"]["expected_value_score"] > row["before"]["expected_value_score"]
    )
    windows_ev_regressed = sum(
        1
        for row in rows
        if row["after"]["expected_value_score"] < row["before"]["expected_value_score"]
    )
    return {
        "passed": False,
        "rule": "EV first over the three canonical backtesting.md windows; require material Gate 4 lift and no multi-window instability.",
        "aggregate_ev_delta": round(aggregate_after_ev - aggregate_before_ev, 4),
        "aggregate_ev_delta_pct": round(
            (aggregate_after_ev - aggregate_before_ev) / aggregate_before_ev,
            6,
        ),
        "aggregate_pnl_delta": round(aggregate_after_pnl - aggregate_before_pnl, 2),
        "aggregate_pnl_delta_pct": round(
            (aggregate_after_pnl - aggregate_before_pnl) / aggregate_before_pnl,
            6,
        ),
        "windows_ev_improved": windows_ev_improved,
        "windows_ev_regressed": windows_ev_regressed,
    }


def build_payload() -> dict[str, Any]:
    rows = [run_window(label, spec) for label, spec in WINDOWS.items()]
    before_metrics = {row["window"]: row["before"] for row in rows}
    after_metrics = {row["window"]: row["after"] for row in rows}
    expected_value_score_delta = {
        row["window"]: row["delta"]["expected_value_score"] for row in rows
    }
    gate4 = _gate4(rows)
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "rejected",
        "decision": "rejected",
        "mechanism_family": "same_day_sector_cap_candidate_replacement",
        "hypothesis": (
            "When same-day sector cap has to drop candidates, preserving the top "
            "same-sector candidates by existing quality fields may improve local "
            "capital allocation without changing MAX_PER_SECTOR."
        ),
        "change_type": "entry_candidate_cap_replay",
        "single_causal_variable": "same_sector_cap_quality_top_n_selection",
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}" for label, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            label: spec["state_note"] for label, spec in WINDOWS.items()
        },
        "parameters": {
            "max_per_sector": 2,
            "quality_key": [
                "trade_quality_score desc",
                "confidence_score desc",
                "pct_from_52w_high desc",
            ],
            "preserve_global_order_after_sector_selection": True,
            "locked_variables": [
                "signal generation",
                "global candidate order outside same-sector drops",
                "MAX_PER_SECTOR",
                "scarce-slot breakout deferral",
                "sizing",
                "entry open cancels",
                "exits",
                "add-ons",
                "LLM/news replay",
                "universe",
            ],
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "expected_value_score_delta": expected_value_score_delta,
        "gate4": gate4,
        "rejection_reason": (
            "Rejected: the variant was inert in late_strong and old_thin, but "
            "regressed mid_weak EV and PnL while lowering win rate."
        ),
        "historical_experiment_check": {
            "nearby_rejected": {
                "global_sector_cap_sweeps": "MAX_PER_SECTOR=1 damaged all windows; MAX_PER_SECTOR=3 was inert.",
                "active_position_sector_cap": "Counting already-open positions damaged clustered exposure.",
                "global_tqs_sorting": "Global TQS allocation ordering was rejected.",
            },
            "why_not_simple_repeat": (
                "This does not change sector cap size or globally sort by TQS; it "
                "only tests replacement selection inside same-sector cap collisions."
            ),
            "mechanism_insight_conflict": (
                "Allowed as a narrow candidate-level replacement test, but the "
                "negative result strengthens the sector-cap anti-repeat guardrail."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_positive": (
                "Move quality selection into production_parity.filter_entry_signal_candidates "
                "and add parity tests before enabling."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this deterministic "
                "candidate replacement test avoided LLM changes."
            ),
        },
        "why_not_other_attractive_points": {
            "addon_capital_allocation": "Blocked by add-on heat parity mismatch found in exp-20260508-019.",
            "llm_soft_ranking": "Production-aligned replay sample remains too sparse.",
            "10k_candidate_pool": "Forward watch has no eligible outside-universe closed outcomes yet.",
            "estimate_revisions": "Zero three-window candidate touches after data repair.",
        },
        "next_retry_requires": [
            "Do not retry nearby sector-cap quality, confidence, TQS, or same-sector replacement keys on the same fixed windows.",
            "A valid sector-cap retry needs new candidate-level replacement evidence, preferably event/news context, showing the skipped clustered trade is worse than the admitted alternative.",
        ],
        "rows": rows,
        "related_files": [
            "quant/experiments/exp_20260508_020_sector_cap_quality_replay.py",
            "data/experiments/exp-20260508-020/sector_cap_quality_replay.json",
            "docs/experiments/logs/exp-20260508-020.json",
            "docs/experiments/tickets/exp-20260508-020.json",
            "docs/experiments/artifacts/exp-20260508-020_sector_cap_quality_replay.md",
        ],
    }


def _artifact(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    lines = [
        "# exp-20260508-020 - Sector cap quality replay",
        "",
        "## Decision",
        "",
        "Rejected. The local quality replacement rule did not improve the canonical three-window replay.",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Results",
        "",
        "| Window | Baseline EV | Variant EV | EV delta | Baseline PnL | Variant PnL | PnL delta | Win-rate delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        before = row["before"]
        after = row["after"]
        delta = row["delta"]
        lines.append(
            "| {window} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dwr:+.4f} |".format(
                window=row["window"],
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dwr=delta["win_rate"],
            )
        )
    gate4 = payload["gate4"]
    lines.extend(
        [
            "",
            "## Mechanism Read",
            "",
            "The only active window was `mid_weak`, where the quality replacement admitted one extra trade but lowered win rate and PnL. This suggests same-sector cap collisions are not misallocated by simple TQS/confidence/near-high ordering.",
            "",
            "Do not retry nearby same-sector TQS, confidence, or quality-key variants without new event/news replacement evidence.",
            "",
            "## Gate 4",
            "",
            f"Passed: `{gate4['passed']}`. Aggregate EV delta `{gate4['aggregate_ev_delta']:+.4f}` ({gate4['aggregate_ev_delta_pct']:+.2%}); aggregate PnL delta `${gate4['aggregate_pnl_delta']:+,.2f}` ({gate4['aggregate_pnl_delta_pct']:+.2%}).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    payload = build_payload()
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "decision": payload["decision"],
        "next_retry_requires": payload["next_retry_requires"],
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _artifact(payload))
    print(json.dumps(_safe(payload["gate4"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
