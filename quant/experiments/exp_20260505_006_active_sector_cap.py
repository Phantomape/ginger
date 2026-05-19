"""exp-20260505-006 active-position sector cap experiment.

Alpha-search experiment. The current shared entry gate limits same-day new
signals per sector, but it does not count already-open positions in that sector.
This tests one narrowly scoped capital-allocation hypothesis: whether scarce
new-entry slots should avoid sectors that are already at the sector cap.

No production or default backtest strategy logic is changed by this script. If
the variant had passed Gate 4, promotion would require changing the shared
production_parity.filter_entry_signal_candidates helper and the backtester/run
adapters together.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import MAX_PER_SECTOR  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260505-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "active_sector_cap.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_active_sector_cap.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_payload(payload), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe_payload(payload), ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    by_strategy = result.get("by_strategy") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe": _round(result.get("sharpe"), 2),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "by_strategy": {
            key: {
                "trade_count": value.get("trade_count"),
                "win_rate": _round(value.get("win_rate"), 4),
                "total_pnl_usd": _round(value.get("total_pnl_usd"), 2),
                "profit_factor": _round(value.get("profit_factor"), 4),
                "avg_R": _round(value.get("avg_R"), 4),
            }
            for key, value in by_strategy.items()
            if isinstance(value, dict)
        },
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "expected_value_score",
        "sharpe",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
        "signals_generated",
        "signals_survived",
    ]
    out = {}
    for field in fields:
        left = before.get(field)
        right = after.get(field)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            out[field] = _round(right - left, 6)
    return out


def _run_window(window: dict[str, str]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    )
    return engine.run()


class ActiveSectorCapPatch:
    def __init__(self) -> None:
        self.original = backtester.filter_entry_signal_candidates
        self.dropped_by_window: dict[str, list[dict[str, Any]]] = {}
        self.current_window: str | None = None

    def __enter__(self) -> "ActiveSectorCapPatch":
        def active_sector_cap_filter(
            signals,
            open_positions=None,
            active_tickers=None,
            market_regime=None,
            spy_pct_from_ma=None,
            qqq_pct_from_ma=None,
            max_per_sector=MAX_PER_SECTOR,
        ):
            planned, audit = self.original(
                signals,
                open_positions=open_positions,
                active_tickers=active_tickers,
                market_regime=market_regime,
                spy_pct_from_ma=spy_pct_from_ma,
                qqq_pct_from_ma=qqq_pct_from_ma,
                max_per_sector=max_per_sector,
            )
            sector_counts: dict[str, int] = {}
            for ticker in active_tickers or []:
                sector = SECTOR_MAP.get(str(ticker).upper(), "Unknown")
                sector_counts[sector] = sector_counts.get(sector, 0) + 1

            kept = []
            dropped = []
            for sig in planned:
                sector = sig.get("sector", "Unknown")
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                if sector_counts[sector] <= max_per_sector:
                    kept.append(sig)
                    continue
                dropped_event = {
                    "ticker": sig.get("ticker"),
                    "sector": sector,
                    "strategy": sig.get("strategy"),
                    "confidence_score": sig.get("confidence_score"),
                    "trade_quality_score": sig.get("trade_quality_score"),
                    "active_sector_count_after_signal": sector_counts[sector],
                    "max_per_sector": max_per_sector,
                }
                dropped.append(dropped_event)

            if dropped and self.current_window:
                self.dropped_by_window.setdefault(self.current_window, []).extend(dropped)
            audit["active_sector_cap_dropped"] = dropped
            audit["signals_after_entry_filters"] = len(kept)
            return kept, audit

        backtester.filter_entry_signal_candidates = active_sector_cap_filter
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        backtester.filter_entry_signal_candidates = self.original


def _gate_summary(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    by_window = {}
    ev_before_sum = 0.0
    ev_delta_sum = 0.0
    pnl_before_sum = 0.0
    pnl_delta_sum = 0.0
    ev_windows_improved = 0
    ev_windows_regressed = 0
    pnl_windows_improved = 0
    pnl_windows_regressed = 0
    max_drawdown_delta_max = None
    max_sharpe_daily_delta = None
    trade_count_delta_sum = 0
    win_rate_delta_min = None

    for label in WINDOWS:
        delta = _delta(before[label], after[label])
        by_window[label] = {
            "before": before[label],
            "after": after[label],
            "delta": delta,
        }
        ev_before = before[label].get("expected_value_score") or 0.0
        ev_delta = delta.get("expected_value_score") or 0.0
        pnl_before = before[label].get("total_pnl") or 0.0
        pnl_delta = delta.get("total_pnl") or 0.0
        ev_before_sum += ev_before
        ev_delta_sum += ev_delta
        pnl_before_sum += pnl_before
        pnl_delta_sum += pnl_delta
        if ev_delta > 0:
            ev_windows_improved += 1
        elif ev_delta < 0:
            ev_windows_regressed += 1
        if pnl_delta > 0:
            pnl_windows_improved += 1
        elif pnl_delta < 0:
            pnl_windows_regressed += 1
        if "max_drawdown_pct" in delta:
            max_drawdown_delta_max = (
                delta["max_drawdown_pct"]
                if max_drawdown_delta_max is None
                else max(max_drawdown_delta_max, delta["max_drawdown_pct"])
            )
        if "sharpe_daily" in delta:
            max_sharpe_daily_delta = (
                delta["sharpe_daily"]
                if max_sharpe_daily_delta is None
                else max(max_sharpe_daily_delta, delta["sharpe_daily"])
            )
        trade_count_delta_sum += int(delta.get("trade_count") or 0)
        if "win_rate" in delta:
            win_rate_delta_min = (
                delta["win_rate"]
                if win_rate_delta_min is None
                else min(win_rate_delta_min, delta["win_rate"])
            )

    ev_delta_pct = ev_delta_sum / ev_before_sum if ev_before_sum else None
    pnl_delta_pct = pnl_delta_sum / pnl_before_sum if pnl_before_sum else None
    return {
        "by_window": by_window,
        "aggregate": {
            "expected_value_score_before_sum": _round(ev_before_sum, 4),
            "expected_value_score_delta_sum": _round(ev_delta_sum, 4),
            "expected_value_score_delta_pct": _round(ev_delta_pct, 6),
            "total_pnl_before_sum": _round(pnl_before_sum, 2),
            "total_pnl_delta_sum": _round(pnl_delta_sum, 2),
            "total_pnl_delta_pct": _round(pnl_delta_pct, 6),
            "ev_windows_improved": ev_windows_improved,
            "ev_windows_regressed": ev_windows_regressed,
            "pnl_windows_improved": pnl_windows_improved,
            "pnl_windows_regressed": pnl_windows_regressed,
            "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
            "max_sharpe_daily_delta": _round(max_sharpe_daily_delta, 6),
            "trade_count_delta_sum": trade_count_delta_sum,
            "win_rate_delta_min": _round(win_rate_delta_min, 6),
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_metrics"]
    after = payload["after_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} Active-Position Sector Cap",
        "",
        "## Result",
        "",
        "Rejected. Counting already-open position sectors inside the entry sector cap "
        "reduced capital deployment in the two windows where it fired and did not improve old_thin.",
        "",
        "| window | EV before | EV after | PnL delta | Sharpe delta | Win-rate delta | Trades delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        delta = payload["delta_metrics"]["by_window"][label]["delta"]
        lines.append(
            "| {label} | {ev_before:.4f} | {ev_after:.4f} | {pnl_delta:.2f} | "
            "{sharpe_delta:.2f} | {win_delta:.4f} | {trades_delta} |".format(
                label=label,
                ev_before=before[label]["expected_value_score"],
                ev_after=after[label]["expected_value_score"],
                pnl_delta=delta.get("total_pnl", 0.0),
                sharpe_delta=delta.get("sharpe_daily", 0.0),
                win_delta=delta.get("win_rate", 0.0),
                trades_delta=delta.get("trade_count", 0),
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "- Do not promote active-position sector counting into the entry sector cap.",
            "- Do not retry nearby sector-crowding entry filters without candidate-level replacement evidence.",
            "- The current same-day sector cap is preserving useful clustered winners despite apparent concentration risk.",
            "",
        ]
    )
    return "\n".join(lines)


def _append_playbook_update(payload: dict[str, Any]) -> None:
    marker = "### 2026-05-05 mechanism update: Active-position sector cap"
    existing = PLAYBOOK.read_text(encoding="utf-8")
    if marker in existing:
        return
    agg = payload["delta_metrics"]["aggregate"]
    text = f"""

{marker}

Status: rejected.

Core conclusion: `{EXPERIMENT_ID}` tested whether same-day entry sector caps
should also count already-open positions in each sector. The intuition was that
existing sector crowding might be using scarce new-entry slots too aggressively,
but the stricter cap removed useful clustered exposure.

Evidence: aggregate EV fell `{agg["expected_value_score_delta_sum"]:+.4f}`
(`{agg["expected_value_score_delta_pct"]:+.2%}`) and aggregate PnL fell
`${agg["total_pnl_delta_sum"]:,.2f}` (`{agg["total_pnl_delta_pct"]:+.2%}`).
`late_strong` and `mid_weak` both regressed; `old_thin` was unchanged.

Mechanism insight: the accepted stack still benefits from some sector clustering
after positions are already open. Sector crowding is not a portable alpha
discriminator by itself; treating concentration reduction as alpha damages
capital deployment.

Do not repeat: active-position sector-cap counting, stricter existing-sector
entry filters, or nearby sector-crowding rules without candidate-level
replacement evidence showing that the skipped clustered trade is worse than the
admitted alternative.
"""
    PLAYBOOK.write_text(existing.rstrip() + text + "\n", encoding="utf-8")


def main() -> int:
    before_metrics = {}
    before_results = {}
    for label, window in WINDOWS.items():
        result = _run_window(window)
        before_results[label] = result
        before_metrics[label] = _metrics(result)

    after_metrics = {}
    dropped_by_window = {}
    with ActiveSectorCapPatch() as patch:
        for label, window in WINDOWS.items():
            patch.current_window = label
            result = _run_window(window)
            after_metrics[label] = _metrics(result)
        dropped_by_window = patch.dropped_by_window

    delta_metrics = _gate_summary(before_metrics, after_metrics)
    dropped_summary = {
        label: {
            "drop_count": len(dropped_by_window.get(label, [])),
            "dropped": dropped_by_window.get(label, []),
        }
        for label in WINDOWS
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "rejected",
        "decision": "rejected",
        "lane": "alpha_search",
        "change_type": "entry_capital_allocation_sector_crowding",
        "alpha_hypothesis_category": "entry / capital allocation",
        "hypothesis": (
            "Already-open positions in a sector may consume the same scarce "
            "risk budget as new entries; counting active position sectors inside "
            "the entry sector cap may avoid lower-quality clustered trades."
        ),
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM soft-ranking still has too few joined outcomes; "
            "this tests an OHLCV/metadata allocator that is fully replayable."
        ),
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "similar_failed_families": [
                "same-day sector cap tightening to 1 was rejected",
                "sector-confirmed SPY leader sizing was rejected",
                "Unknown-sector risk-on cap was rejected",
            ],
            "why_not_simple_repeat": (
                "This does not change MAX_PER_SECTOR, sector leader multipliers, "
                "or missing-sector metadata. It only asks whether already-open "
                "positions should count against the existing cap."
            ),
        },
        "parameters": {
            "single_causal_variable": "count active position sectors in entry sector cap",
            "baseline_behavior": (
                "filter_entry_signal_candidates caps only same-day candidate counts "
                "per sector and ignores already-open position sectors."
            ),
            "tested_variant": "active_position_sector_cap",
            "active_sector_source": "active_tickers mapped through risk_engine.SECTOR_MAP",
            "max_per_sector": MAX_PER_SECTOR,
            "locked_variables": [
                "universe",
                "OHLCV snapshots",
                "signal generation",
                "signal ranking",
                "risk multipliers",
                "MAX_PER_SECTOR value",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "gap cancels",
                "add-ons",
                "exits",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "active_sector_cap_drops": dropped_summary,
        "gate4_basis": (
            "Rejected: EV and PnL regressed in late_strong and mid_weak, "
            "old_thin was unchanged, and no Gate 4 materiality threshold passed."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, update production_parity.filter_entry_signal_candidates "
                "and pass open-position sector context from both backtester.py and run.py."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": (
            "Active-position sector cap counting failed multi-window Gate 4 and "
            "reduced the accepted stack's strongest capital deployment windows."
        ),
        "risk_of_change": (
            "The rule would mistake profitable clustered leadership for generic "
            "sector concentration and may skip high-quality same-sector follow-through."
        ),
        "why_not_other_attractive_points": {
            "event_bundle_promotion": (
                "Replay-only bundle remains promising but needs closed forward paper outcomes."
            ),
            "LLM_soft_ranking": "Still production-aligned sample limited.",
            "macro_or_ETF_pool": "Recent macro ETF and energy-pair expansions were rejected.",
            "positionable_entry_planning": "exp-20260505-005 just rejected it.",
        },
        "do_not_repeat_without_new_evidence": [
            "Counting already-open sector positions in the entry sector cap.",
            "Treating lower sector concentration as alpha without replacement-value evidence.",
        ],
        "next_retry_requires": [
            "Candidate-level replacement evidence that the admitted non-clustered candidate beats the skipped clustered trade.",
            "A shared helper change plus run/backtester parity test before any production promotion.",
        ],
        "related_files": [
            str(Path("quant/experiments/exp_20260505_006_active_sector_cap.py")),
            str(Path("data/experiments/exp-20260505-006/active_sector_cap.json")),
            str(Path("experiments/logs/exp-20260505-006.json")),
            str(Path("experiments/tickets/exp-20260505-006.json")),
            str(Path("experiments/artifacts/exp-20260505-006_active_sector_cap.md")),
            str(Path("docs/experiment_log.jsonl")),
        ],
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "hypothesis": payload["hypothesis"],
        "date_range": payload["date_range"],
        "expected_value_score_delta": {
            label: delta_metrics["by_window"][label]["delta"].get("expected_value_score", 0.0)
            for label in WINDOWS
        },
        "production_impact": payload["production_impact"],
        "rejection_reason": payload["rejection_reason"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, payload)
    _append_playbook_update(payload)
    print(json.dumps(_safe_payload(payload["delta_metrics"]["aggregate"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
