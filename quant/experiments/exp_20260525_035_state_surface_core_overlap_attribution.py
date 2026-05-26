"""exp-20260525-035: state-surface paper sleeve core-overlap attribution.

Measurement repair (read-only). Answers: of the default-off
`STATE_SURFACE_SATELLITE` paper sleeve PnL accepted through `exp-20260520-001`
on the canonical three fixed windows, how much comes from tickers that the
core stack also entered in the same window (and within +/-N trading days of
the paper entry)?

The answer gates a future Gate 1-4 `alpha_search` on a state-surface
core-overlap allocation rule. It does not change core entries, exits,
ranking, sizing, slots, heat, LLM/news, live orders, or state-surface paper
selection / notional / hold. It does not introduce any filter. Gate 1 core
metrics are validated by re-running the canonical three-window backtest;
Gate 2 verifies the open-positions field check; Gate 3 is N/A; Gate 4 is the
measurement repair acceptance.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-035"
EXPERIMENT_SLUG = "state_surface_core_overlap_attribution"
SOURCE_EXPERIMENT_ID = "exp-20260520-001"
SOURCE_SLUG = "state_surface_low_extension_support_notional"
CORE_BASELINE_EXPERIMENT_ID = "exp-20260517-009"
CORE_BASELINE_ARTIFACT = (
    "data/experiments/exp-20260517-009/ample_slot_stock_rank1_topup.json"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)


CANONICAL_ACCEPTED_AGGREGATE_EV = 7.8941
CANONICAL_ACCEPTED_AGGREGATE_PNL = 234850.99
EV_TOLERANCE = 0.01
PNL_TOLERANCE = 50.0
OVERLAP_TRADING_DAY_LOOKBACKS = (0, 3, 5)

PAPER_SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / f"{SOURCE_SLUG}.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    required = ("entry_date", "target_price")
    if not path.exists():
        return {
            "passed": False,
            "exists": False,
            "path": _repo_rel(path),
            "checked_positions": 0,
            "missing_required_fields": list(required),
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        positions = data.get("positions") or data.get("open_positions") or []
    else:
        positions = data
    missing: set[str] = set()
    checked = 0
    for pos in positions or []:
        if not isinstance(pos, dict):
            continue
        checked += 1
        for key in required:
            if pos.get(key) in (None, ""):
                missing.add(key)
    return {
        "passed": bool(positions) and not missing,
        "exists": True,
        "path": _repo_rel(path),
        "checked_positions": checked,
        "missing_required_fields": sorted(missing),
    }


def _run_canonical_window(label: str) -> dict[str, Any]:
    spec = WINDOWS[label]
    universe = get_universe()
    snapshot = REPO_ROOT / spec["snapshot"]
    engine = BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(snapshot),
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} backtest error: {result['error']}")
    return result


def _core_summary(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": float(result.get("expected_value_score") or 0.0),
        "total_pnl": float(result.get("total_pnl") or 0.0),
        "total_return_pct": float(
            benchmarks.get("strategy_total_return_pct")
            or result.get("total_return_pct")
            or 0.0
        ),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": result.get("survival_rate"),
    }


def _trading_day_axis(core_trades: list[dict[str, Any]], paper_trades: list[dict[str, Any]]) -> list[str]:
    days: set[str] = set()
    for trade in core_trades:
        for key in ("entry_date", "exit_date"):
            value = trade.get(key)
            if value:
                days.add(str(value)[:10])
    for trade in paper_trades:
        for key in ("entry_date", "exit_date", "decision_date"):
            value = trade.get(key)
            if value:
                days.add(str(value)[:10])
    return sorted(days)


def _trading_index(axis: list[str]) -> dict[str, int]:
    return {day: idx for idx, day in enumerate(axis)}


def _td_distance(idx: dict[str, int], a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    ai = idx.get(str(a)[:10])
    bi = idx.get(str(b)[:10])
    if ai is None or bi is None:
        return None
    return abs(ai - bi)


def _classify_paper_trade(
    paper_trade: dict[str, Any],
    core_by_ticker: dict[str, list[dict[str, Any]]],
    td_idx: dict[str, int],
) -> dict[str, Any]:
    ticker = str(paper_trade.get("ticker") or "").upper()
    paper_entry = str(paper_trade.get("entry_date") or "")[:10]
    same_ticker_core = core_by_ticker.get(ticker, [])
    nearest_distance: int | None = None
    nearest_core_entry: str | None = None
    nearest_core_exit: str | None = None
    nearest_core_strategy: str | None = None
    nearest_core_pnl: float | None = None
    for core in same_ticker_core:
        core_entry = str(core.get("entry_date") or "")[:10]
        distance = _td_distance(td_idx, paper_entry, core_entry)
        if distance is None:
            continue
        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_core_entry = core_entry
            nearest_core_exit = str(core.get("exit_date") or "")[:10]
            nearest_core_strategy = core.get("strategy")
            nearest_core_pnl = float(core.get("pnl") or 0.0)
    flags = {
        f"core_overlap_n{n}": (
            nearest_distance is not None and nearest_distance <= n
        )
        for n in OVERLAP_TRADING_DAY_LOOKBACKS
    }
    return {
        "ticker": ticker,
        "paper_entry_date": paper_entry,
        "paper_exit_date": str(paper_trade.get("exit_date") or "")[:10],
        "paper_pnl": float(paper_trade.get("pnl") or 0.0),
        "paper_notional": float(paper_trade.get("notional") or 0.0),
        "paper_queue_rank": paper_trade.get("queue_rank"),
        "paper_rank": paper_trade.get("rank"),
        "paper_sector": paper_trade.get("sector"),
        "paper_window": paper_trade.get("window"),
        "core_same_ticker_count": len(same_ticker_core),
        "nearest_core_entry_distance_td": nearest_distance,
        "nearest_core_entry_date": nearest_core_entry,
        "nearest_core_exit_date": nearest_core_exit,
        "nearest_core_strategy": nearest_core_strategy,
        "nearest_core_pnl": nearest_core_pnl,
        **flags,
    }


def _share(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _attribution_for_window(
    *,
    window: str,
    paper_trades: list[dict[str, Any]],
    core_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    axis = _trading_day_axis(core_trades, paper_trades)
    td_idx = _trading_index(axis)
    core_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for core in core_trades:
        ticker = str(core.get("ticker") or "").upper()
        if ticker:
            core_by_ticker[ticker].append(core)
    classifications = [
        _classify_paper_trade(trade, core_by_ticker, td_idx)
        for trade in paper_trades
    ]
    total_pnl = sum(c["paper_pnl"] for c in classifications)
    total_positive_pnl = sum(c["paper_pnl"] for c in classifications if c["paper_pnl"] > 0)
    lookbacks: dict[str, Any] = {}
    for n in OVERLAP_TRADING_DAY_LOOKBACKS:
        key = f"core_overlap_n{n}"
        overlap = [c for c in classifications if c[key]]
        non_overlap = [c for c in classifications if not c[key]]
        overlap_positive_pnl = sum(c["paper_pnl"] for c in overlap if c["paper_pnl"] > 0)
        non_overlap_positive_pnl = sum(c["paper_pnl"] for c in non_overlap if c["paper_pnl"] > 0)
        lookbacks[f"n{n}"] = {
            "lookback_trading_days": n,
            "paper_trades_with_core_overlap": len(overlap),
            "paper_trades_without_core_overlap": len(non_overlap),
            "pnl_from_core_overlap": round(sum(c["paper_pnl"] for c in overlap), 2),
            "pnl_from_non_overlap": round(sum(c["paper_pnl"] for c in non_overlap), 2),
            "pnl_from_core_overlap_share": _share(
                sum(c["paper_pnl"] for c in overlap), total_pnl
            ),
            "positive_pnl_from_core_overlap_share": _share(
                overlap_positive_pnl, total_positive_pnl
            ),
            "positive_pnl_from_non_overlap_share": _share(
                non_overlap_positive_pnl, total_positive_pnl
            ),
        }
    return {
        "window": window,
        "paper_trades_total": len(paper_trades),
        "core_trades_total": len(core_trades),
        "paper_pnl_total": round(total_pnl, 2),
        "paper_positive_pnl_total": round(total_positive_pnl, 2),
        "trading_days_in_axis": len(axis),
        "lookbacks": lookbacks,
        "classifications": classifications,
    }


def _aggregate_attribution(window_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    paper_total = sum(p["paper_trades_total"] for p in window_payloads.values())
    pnl_total = round(sum(p["paper_pnl_total"] for p in window_payloads.values()), 2)
    positive_total = round(
        sum(p["paper_positive_pnl_total"] for p in window_payloads.values()), 2
    )
    lookbacks: dict[str, Any] = {}
    for n in OVERLAP_TRADING_DAY_LOOKBACKS:
        key = f"n{n}"
        overlap_trades = sum(p["lookbacks"][key]["paper_trades_with_core_overlap"] for p in window_payloads.values())
        non_overlap_trades = sum(p["lookbacks"][key]["paper_trades_without_core_overlap"] for p in window_payloads.values())
        overlap_pnl = round(
            sum(p["lookbacks"][key]["pnl_from_core_overlap"] for p in window_payloads.values()),
            2,
        )
        non_overlap_pnl = round(
            sum(p["lookbacks"][key]["pnl_from_non_overlap"] for p in window_payloads.values()),
            2,
        )
        overlap_pos_pnl = 0.0
        non_overlap_pos_pnl = 0.0
        for p in window_payloads.values():
            for cls in p["classifications"]:
                if cls[f"core_overlap_n{n}"]:
                    if cls["paper_pnl"] > 0:
                        overlap_pos_pnl += cls["paper_pnl"]
                else:
                    if cls["paper_pnl"] > 0:
                        non_overlap_pos_pnl += cls["paper_pnl"]
        lookbacks[key] = {
            "lookback_trading_days": n,
            "paper_trades_with_core_overlap": overlap_trades,
            "paper_trades_without_core_overlap": non_overlap_trades,
            "pnl_from_core_overlap": overlap_pnl,
            "pnl_from_non_overlap": non_overlap_pnl,
            "pnl_from_core_overlap_share": _share(overlap_pnl, pnl_total),
            "positive_pnl_from_core_overlap_share": _share(
                round(overlap_pos_pnl, 2), positive_total
            ),
            "positive_pnl_from_non_overlap_share": _share(
                round(non_overlap_pos_pnl, 2), positive_total
            ),
        }
    return {
        "paper_trades_total": paper_total,
        "paper_pnl_total": pnl_total,
        "paper_positive_pnl_total": positive_total,
        "lookbacks": lookbacks,
    }


def _next_step_decision(aggregate: dict[str, Any]) -> dict[str, Any]:
    share_n5 = aggregate["lookbacks"]["n5"]["pnl_from_core_overlap_share"]
    if share_n5 is None:
        bucket = "no_paper_pnl_signal"
        recommendation = (
            "no_paper_pnl_to_evaluate; collect more closed forward outcomes."
        )
    elif share_n5 > 0.5:
        bucket = "majority_overlap_with_core"
        recommendation = (
            "alpha_search permitted: future state-surface paper notional rule "
            "may haircut core_overlap=true and modestly support core_overlap=false, "
            "but must pass state-surface tightened Gate 4 (>10% aggregate EV)."
        )
    elif share_n5 >= 0.2:
        bucket = "mixed_overlap_with_core"
        recommendation = (
            "no immediate allocation gate. Collect closed forward "
            "replacement-value rows; revisit only with a materially new "
            "production-visible discriminator."
        )
    else:
        bucket = "largely_independent_of_core"
        recommendation = (
            "state-surface paper alpha is largely independent of core on the "
            "frozen sample; prioritize sector/theme crowding or queue "
            "independence fields next, not core_overlap as a primary lever."
        )
    return {
        "next_step_bucket": bucket,
        "next_step_recommendation": recommendation,
        "pnl_from_core_overlap_share_n5": share_n5,
        "decision_thresholds": {
            "majority_overlap_min_share": 0.5,
            "mixed_overlap_min_share": 0.2,
        },
        "downstream_gate4_requirement_if_promoted": (
            "state_surface tightened Gate 4 requires aggregate EV improvement > 10%"
        ),
    }


def _production_impact() -> dict[str, bool]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }


def _load_source_paper_trades() -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(PAPER_SOURCE_JSON.read_text(encoding="utf-8"))
    surface_sleeve = payload.get("surface_sleeve") or {}
    out: dict[str, list[dict[str, Any]]] = OrderedDict()
    for window in WINDOWS:
        rows = (surface_sleeve.get(window) or {}).get("selected_trades") or []
        out[window] = [dict(row) for row in rows]
    return out


def _format_share(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate_attribution"]
    window_attr = payload["window_attribution"]
    decision = payload["next_step_decision"]
    gate1 = payload["gate1"]
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Paper Sleeve Core-Overlap Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Read-only `measurement_repair`. Quantifies the share of accepted",
        f"default-off state-surface paper PnL (latest accepted increment "
        f"`{SOURCE_EXPERIMENT_ID}`) that overlaps with same-window core entries.",
        "",
        "## Gate 1 Core Replay Verification",
        "",
        "```json",
        json.dumps(gate1, indent=2, sort_keys=True),
        "```",
        "",
        "## Aggregate Overlap Across Three Windows",
        "",
        "| Lookback (TD) | Paper Trades w/ Overlap | Paper Trades w/o Overlap | PnL from Overlap | PnL from Non-Overlap | Overlap PnL Share | Positive PnL Overlap Share |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for n in OVERLAP_TRADING_DAY_LOOKBACKS:
        row = aggregate["lookbacks"][f"n{n}"]
        lines.append(
            "| {n} | {ov} | {no} | ${ovp:,.2f} | ${nop:,.2f} | {osh} | {posh} |".format(
                n=n,
                ov=row["paper_trades_with_core_overlap"],
                no=row["paper_trades_without_core_overlap"],
                ovp=row["pnl_from_core_overlap"],
                nop=row["pnl_from_non_overlap"],
                osh=_format_share(row["pnl_from_core_overlap_share"]),
                posh=_format_share(row["positive_pnl_from_core_overlap_share"]),
            )
        )
    lines.extend(
        [
            "",
            "## Per-Window Summary",
            "",
            "| Window | Paper Trades | Core Trades | Paper PnL | N=0 Overlap Trades | N=0 Overlap PnL | N=3 Overlap Trades | N=3 Overlap PnL | N=5 Overlap Trades | N=5 Overlap PnL |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for window in WINDOWS:
        info = window_attr[window]
        n0 = info["lookbacks"]["n0"]
        n3 = info["lookbacks"]["n3"]
        n5 = info["lookbacks"]["n5"]
        lines.append(
            "| {w} | {pt} | {ct} | ${pp:,.2f} | {n0t} | ${n0p:,.2f} | {n3t} | ${n3p:,.2f} | {n5t} | ${n5p:,.2f} |".format(
                w=window,
                pt=info["paper_trades_total"],
                ct=info["core_trades_total"],
                pp=info["paper_pnl_total"],
                n0t=n0["paper_trades_with_core_overlap"],
                n0p=n0["pnl_from_core_overlap"],
                n3t=n3["paper_trades_with_core_overlap"],
                n3p=n3["pnl_from_core_overlap"],
                n5t=n5["paper_trades_with_core_overlap"],
                n5p=n5["pnl_from_core_overlap"],
            )
        )
    lines.extend(
        [
            "",
            "## Next-Step Decision",
            "",
            "```json",
            json.dumps(decision, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    paper_trades_by_window = _load_source_paper_trades()
    expected_paper_counts = {w: len(rows) for w, rows in paper_trades_by_window.items()}

    core_summaries: dict[str, dict[str, Any]] = OrderedDict()
    core_trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    for window in WINDOWS:
        result = _run_canonical_window(window)
        core_summaries[window] = _core_summary(result)
        core_trades_by_window[window] = result.get("trades") or []

    aggregate_ev = round(
        sum(row["expected_value_score"] for row in core_summaries.values()), 4
    )
    aggregate_pnl = round(
        sum(row["total_pnl"] for row in core_summaries.values()), 2
    )
    aggregate_trades = int(sum(row["trade_count"] for row in core_summaries.values()))

    ev_drift = round(aggregate_ev - CANONICAL_ACCEPTED_AGGREGATE_EV, 4)
    pnl_drift = round(aggregate_pnl - CANONICAL_ACCEPTED_AGGREGATE_PNL, 2)
    gate1_pass = (
        abs(ev_drift) <= EV_TOLERANCE and abs(pnl_drift) <= PNL_TOLERANCE
    )

    gate1 = {
        "passed": bool(gate1_pass),
        "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
        "baseline_artifact": CORE_BASELINE_ARTIFACT,
        "canonical_accepted_aggregate_expected_value_score_sum": CANONICAL_ACCEPTED_AGGREGATE_EV,
        "canonical_accepted_aggregate_total_pnl_sum": CANONICAL_ACCEPTED_AGGREGATE_PNL,
        "observed_aggregate_expected_value_score_sum": aggregate_ev,
        "observed_aggregate_total_pnl_sum": aggregate_pnl,
        "observed_aggregate_trade_count_sum": aggregate_trades,
        "expected_value_score_drift": ev_drift,
        "total_pnl_drift": pnl_drift,
        "ev_tolerance": EV_TOLERANCE,
        "pnl_tolerance": PNL_TOLERANCE,
        "by_window": core_summaries,
    }

    window_attr: dict[str, dict[str, Any]] = OrderedDict()
    for window in WINDOWS:
        window_attr[window] = _attribution_for_window(
            window=window,
            paper_trades=paper_trades_by_window[window],
            core_trades=core_trades_by_window[window],
        )
    aggregate_attr = _aggregate_attribution(window_attr)
    decision_payload = _next_step_decision(aggregate_attr)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "status": "observed_only_attribution_complete",
        "decision": "state_surface_core_overlap_attribution_complete",
        "read_only": True,
        "hypothesis": (
            "Quantify the share of accepted default-off state-surface paper "
            "PnL that is redundant with same-window core entries; the answer "
            "gates a future state-surface core-overlap allocation experiment."
        ),
        "change_summary": (
            "Read-only attribution joining accepted default-off state-surface "
            "paper sleeve selected trades (from "
            f"`{SOURCE_EXPERIMENT_ID}`) with same-window core entries from a "
            "canonical three-window backtest at trading-day lookbacks "
            f"{list(OVERLAP_TRADING_DAY_LOOKBACKS)}."
        ),
        "change_type": "measurement_repair_attribution_field",
        "mechanism_family": "state_surface_promotion_readiness",
        "trial_family": "state_surface_core_overlap_attribution",
        "trial_variant_id": "core_overlap_attribution_v1",
        "changed_variable": "state_surface_core_overlap_attribution_field",
        "single_causal_variable": "state_surface_core_overlap_attribution_field",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            CORE_BASELINE_EXPERIMENT_ID,
            SOURCE_EXPERIMENT_ID,
            "exp-20260518-006",
            "exp-20260524-012",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "state_surface_paper_vs_core_entry_overlap_join",
        "component": "quant/experiments/exp_20260525_035_state_surface_core_overlap_attribution.py",
        "parameters": {
            "overlap_trading_day_lookbacks": list(OVERLAP_TRADING_DAY_LOOKBACKS),
            "paper_source_artifact": _repo_rel(PAPER_SOURCE_JSON),
            "windows": {
                label: {
                    "start": spec["start"],
                    "end": spec["end"],
                    "snapshot": spec["snapshot"],
                }
                for label, spec in WINDOWS.items()
            },
            "expected_paper_trade_counts_by_window": expected_paper_counts,
            "canonical_accepted_aggregate_expected_value_score_sum": CANONICAL_ACCEPTED_AGGREGATE_EV,
            "canonical_accepted_aggregate_total_pnl_sum": CANONICAL_ACCEPTED_AGGREGATE_PNL,
            "ev_tolerance": EV_TOLERANCE,
            "pnl_tolerance": PNL_TOLERANCE,
            "exact_rerun_command": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_035_state_surface_core_overlap_attribution.py"
            ),
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            "core_baseline_artifact": CORE_BASELINE_ARTIFACT,
            "paper_source_artifact": _repo_rel(PAPER_SOURCE_JSON),
            "ohlcv_snapshots": [spec["snapshot"] for spec in WINDOWS.values()],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Measurement repair that gates the next state-surface "
                "allocation alpha_search: do state-surface paper trades earn "
                "PnL on tickers that core also entered?"
            ),
            "2_history_check": (
                "First explicit join between default-off state-surface paper "
                "sleeve trades and same-window core entries; no prior nearby "
                "experiment quantified this overlap."
            ),
            "3_single_causal_variable": "state_surface_core_overlap_attribution_field",
            "4_acceptance_standard": (
                "Gate 1 core EV/PnL drift within tolerance; report core-overlap "
                "shares per window and aggregated; emit next-step decision."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_035_state_surface_core_overlap_attribution.py"
            ),
        },
        "gate1": gate1,
        "gate2": {
            "passed": bool(gate2["passed"]),
            "field_check": gate2,
            "rule_dependencies": [
                "operator_inputs/open_positions.json entry_date/target_price",
                f"data/experiments/{SOURCE_EXPERIMENT_ID}/{SOURCE_SLUG}.json surface_sleeve.{{window}}.selected_trades",
                "canonical three-window OHLCV snapshots",
                "BacktestEngine result['trades'] ticker/entry_date/exit_date",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": True,
            "passed": bool(gate1_pass),
            "note": (
                "Gate 4 here is the measurement repair acceptance: core EV/PnL "
                "stay at the canonical accepted aggregate, attribution shares "
                "are emitted, and the next-step decision is conditional on the "
                "n=5 overlap share."
            ),
        },
        "window_attribution": window_attr,
        "aggregate_attribution": aggregate_attr,
        "next_step_decision": decision_payload,
        "before_metrics": {
            "accepted_core_expected_value_score_sum": CANONICAL_ACCEPTED_AGGREGATE_EV,
            "accepted_core_total_pnl_sum": CANONICAL_ACCEPTED_AGGREGATE_PNL,
            "state_surface_paper_pnl_total": round(
                sum(
                    sum(float(t.get("pnl") or 0.0) for t in trades)
                    for trades in paper_trades_by_window.values()
                ),
                2,
            ),
            "state_surface_paper_trade_total": sum(expected_paper_counts.values()),
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": aggregate_ev,
            "accepted_core_total_pnl_sum": aggregate_pnl,
            "state_surface_paper_pnl_total": aggregate_attr["paper_pnl_total"],
            "state_surface_paper_trade_total": aggregate_attr["paper_trades_total"],
            "strategy_behavior_changed": False,
            "pnl_from_core_overlap_share_n0": aggregate_attr["lookbacks"]["n0"][
                "pnl_from_core_overlap_share"
            ],
            "pnl_from_core_overlap_share_n3": aggregate_attr["lookbacks"]["n3"][
                "pnl_from_core_overlap_share"
            ],
            "pnl_from_core_overlap_share_n5": aggregate_attr["lookbacks"]["n5"][
                "pnl_from_core_overlap_share"
            ],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": ev_drift,
            "total_pnl_sum_delta": pnl_drift,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": ev_drift,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": _production_impact(),
        "decision_rule": (
            "If pnl_from_core_overlap_share_n5 > 0.50 the next "
            "state-surface alpha_search may propose a core-overlap-aware "
            "notional rule (subject to tightened state-surface Gate 4 >10%); "
            "if 0.20-0.50, hold for closed forward replacement-value rows; "
            "if < 0.20, prioritize sector/theme crowding or queue independence "
            "fields instead."
        ),
        "rejection_reason": None,
        "next_evidence_needed": (
            "Closed forward state-surface paper outcomes plus core-entry "
            "overlap on those forward rows (not just the frozen sample)."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG_JSONL),
            _repo_rel(PAPER_SOURCE_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "component",
        "parameters",
        "date_range",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "aggregate_attribution",
        "next_step_decision",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "decision_rule",
        "rejection_reason",
        "next_evidence_needed",
        "related_files",
        "anti_js",
    )
    return {key: payload[key] for key in keys}


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "measurement_repair",
            "owner": "codex",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": payload["single_causal_variable"],
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(LOG_JSON),
            "updated_at": payload["timestamp"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "gate1_passed": payload["gate1"]["passed"],
                    "aggregate_ev": payload["after_metrics"][
                        "accepted_core_expected_value_score_sum"
                    ],
                    "aggregate_pnl": payload["after_metrics"][
                        "accepted_core_total_pnl_sum"
                    ],
                    "pnl_from_core_overlap_share_n5": payload["after_metrics"][
                        "pnl_from_core_overlap_share_n5"
                    ],
                    "next_step_bucket": payload["next_step_decision"][
                        "next_step_bucket"
                    ],
                    "output": _repo_rel(OUT_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
