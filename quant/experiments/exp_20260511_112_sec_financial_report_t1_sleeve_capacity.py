"""exp-20260511-112: SEC financial-report T+1 paper sleeve capacity.

Alpha search on one causal variable: the default-off paper sleeve's
``max_positions`` capacity for the frozen SEC financial-report positive T+1
queue. The replay calls the production paper-sleeve builder directly; it does
not change core signal generation, ranking, sizing, exits, LLM behavior, or
live orders.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260511-112"
STEM = "exp_20260511_112_sec_financial_report_t1_sleeve_capacity"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from sec_financial_report_event_sleeve import (  # noqa: E402
    DEFAULT_EVENT_NOTIONAL_USD,
    DEFAULT_MAX_POSITIONS,
    SLEEVE_NAME,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

SOURCE_EXP100_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260511-100"
    / "exp_20260511_100_sec_financial_report_positive_t1_forward_outcome_refresh.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = (
    REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_financial_report_t1_sleeve_capacity.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

STARTING_CAPITAL = 100_000.0
MAX_POSITION_VARIANTS = (1, 2, 3, 5, 10)
BASELINE_MAX_POSITIONS = 1
PROMOTION_VARIANT = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _upsert_registry(payload: dict[str, Any]) -> None:
    if EXPERIMENT_REGISTRY.exists():
        registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8-sig"))
    else:
        registry = {"experiments": []}
    experiments = [
        row
        for row in registry.get("experiments", [])
        if row.get("experiment_id") != EXPERIMENT_ID
    ]
    experiments.append(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": payload["hypothesis"],
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": payload["status"],
            "ticket_file": f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            "updated_at": payload["timestamp"],
        }
    )
    registry["experiments"] = sorted(
        experiments, key=lambda row: str(row.get("experiment_id") or "")
    )
    _write_json(EXPERIMENT_REGISTRY, registry)


def _load_exp100() -> dict[str, Any]:
    return json.loads(SOURCE_EXP100_JSON.read_text(encoding="utf-8"))


def _as_float(row: dict[str, Any], key: str) -> float | None:
    raw = row.get(key)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _load_snapshot_prices(path: str) -> OrderedDict[str, dict[str, dict[str, float]]]:
    payload = json.loads((REPO_ROOT / path).read_text(encoding="utf-8-sig"))
    by_date: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: {"open": {}, "close": {}}
    )
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        symbol = str(ticker).upper()
        for row in rows or []:
            date_value = str(row.get("Date") or row.get("date") or "")[:10]
            if not date_value:
                continue
            open_price = _as_float(row, "Open")
            close_price = _as_float(row, "Close")
            if open_price is not None and open_price > 0:
                by_date[date_value]["open"][symbol] = open_price
            if close_price is not None and close_price > 0:
                by_date[date_value]["close"][symbol] = close_price
    return OrderedDict(sorted(by_date.items()))


def _equity_metrics(
    equity_curve: list[tuple[str, float]],
    *,
    trade_count: int,
    win_rate: float | None,
    signals_generated: int | None = None,
    signals_survived: int | None = None,
) -> dict[str, Any]:
    if not equity_curve:
        return {}
    equities = [float(value) for _, value in equity_curve]
    start = equities[0]
    end = equities[-1]
    daily_returns = [
        (right / left) - 1.0
        for left, right in zip(equities, equities[1:])
        if left and math.isfinite(left) and math.isfinite(right)
    ]
    if len(daily_returns) > 1:
        stdev = statistics.stdev(daily_returns)
        sharpe_daily = (
            statistics.mean(daily_returns) / stdev * math.sqrt(252.0)
            if stdev
            else 0.0
        )
    else:
        sharpe_daily = 0.0
    peak = start
    max_drawdown = 0.0
    for equity in equities:
        peak = max(peak, equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    strategy_return = (end / start) - 1.0 if start else 0.0
    survival_rate = (
        signals_survived / signals_generated
        if signals_generated and signals_survived is not None
        else None
    )
    return {
        "expected_value_score": _round(strategy_return * sharpe_daily, 6),
        "max_drawdown_pct": _round(max_drawdown, 6),
        "sharpe_daily": _round(sharpe_daily, 6),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "strategy_total_return_pct": _round(strategy_return, 6),
        "survival_rate": _round(survival_rate, 6),
        "total_pnl": _round(end - start, 2),
        "trade_count": trade_count,
        "win_rate": _round(win_rate, 6),
    }


def _core_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 6),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 6),
        "sharpe_daily": _round(result.get("sharpe_daily"), 6),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "strategy_total_return_pct": _round(
            (float(result.get("total_pnl") or 0.0) / STARTING_CAPITAL), 6
        ),
        "survival_rate": _round(result.get("survival_rate"), 6),
        "tail_loss_share": _round(result.get("tail_loss_share"), 6),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "trade_count": result.get("total_trades"),
        "win_rate": _round(result.get("win_rate"), 6),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 6),
    }


def _run_core_backtest(window: dict[str, str]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        config={"REPLAY_PARTIAL_REDUCES": True, "REGIME_AWARE_EXIT": True},
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def _normalise_core_curve(result: dict[str, Any]) -> list[tuple[str, float]]:
    out = []
    for raw_date, raw_equity in result.get("equity_curve") or []:
        out.append((str(raw_date)[:10], float(raw_equity)))
    return out


def _rows_by_t1_date(window_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in window_payload.get("candidate_rows") or []:
        t1_date = str(row.get("t1_date") or "")[:10]
        if not t1_date:
            continue
        candidate = dict(row)
        candidate["source_experiment"] = "exp-20260511-100"
        by_date[t1_date].append(candidate)
    return by_date


def _rebuild_sleeve_state(
    snapshot: dict[str, Any],
    skipped_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    state = empty_sec_financial_report_event_sleeve_state()
    state["updated_at"] = snapshot.get("generated_at")
    state["pending_entries"] = list(snapshot.get("pending_entries") or [])
    state["open_positions"] = list(snapshot.get("open_positions") or [])
    state["closed_positions"] = list(snapshot.get("closed_positions") or [])
    state["skipped_entries"] = list(skipped_entries)
    return state


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    max_positions: int,
) -> dict[str, Any]:
    prices_by_date = _load_snapshot_prices(window["snapshot"])
    candidates_by_t1 = _rows_by_t1_date(window_payload)
    state = empty_sec_financial_report_event_sleeve_state()
    skipped_entries: list[dict[str, Any]] = []
    pnl_by_date: OrderedDict[str, float] = OrderedDict()
    max_open_positions = 0
    max_gross_notional = 0.0
    enqueued_candidates = 0

    for as_of, prices in prices_by_date.items():
        candidates = candidates_by_t1.get(as_of, [])
        enqueued_candidates += len(candidates)
        queue = {
            "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
            "rule_version": "exp-20260511-100-replay",
            "enabled": False,
            "asof_date": as_of,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "data_source": {
                "status": "replay",
                "source_experiment": "exp-20260511-100",
                "window": window_label,
            },
        }
        snapshot = build_sec_financial_report_event_sleeve_snapshot(
            sec_financial_report_t1_queue=queue,
            as_of=as_of,
            open_prices=prices["open"],
            current_prices=prices["close"],
            state=state,
            config={"max_positions": max_positions},
            persist=False,
        )
        skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
        state = _rebuild_sleeve_state(snapshot, skipped_entries)
        realized = float(snapshot.get("realized_pnl_to_date") or 0.0)
        unrealized = float(snapshot.get("unrealized_pnl") or 0.0)
        pnl_by_date[as_of] = realized + unrealized
        open_positions = snapshot.get("open_positions") or []
        max_open_positions = max(max_open_positions, len(open_positions))
        max_gross_notional = max(
            max_gross_notional,
            sum(float(item.get("notional") or 0.0) for item in open_positions),
        )

    closed_positions = state.get("closed_positions") or []
    wins = sum(1 for item in closed_positions if float(item.get("pnl") or 0.0) > 0)
    sleeve_curve = [
        (date_value, STARTING_CAPITAL + pnl) for date_value, pnl in pnl_by_date.items()
    ]
    standalone_metrics = _equity_metrics(
        sleeve_curve,
        trade_count=len(closed_positions),
        win_rate=(wins / len(closed_positions) if closed_positions else None),
    )
    standalone_metrics.update(
        {
            "candidate_count": enqueued_candidates,
            "closed_trade_count": len(closed_positions),
            "open_position_count_end": len(state.get("open_positions") or []),
            "skipped_capacity_count": len(skipped_entries),
            "max_open_positions": max_open_positions,
            "max_gross_notional": _round(max_gross_notional, 2),
        }
    )
    return {
        "daily_pnl": list(pnl_by_date.items()),
        "metrics": standalone_metrics,
        "sample_closed_positions": closed_positions[:10],
    }


def _combine_curves(
    core_curve: list[tuple[str, float]],
    sleeve_daily_pnl: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    sleeve_by_date = {date_value: float(pnl) for date_value, pnl in sleeve_daily_pnl}
    last_pnl = 0.0
    combined = []
    for date_value, core_equity in core_curve:
        if date_value in sleeve_by_date:
            last_pnl = sleeve_by_date[date_value]
        combined.append((date_value, float(core_equity) + last_pnl))
    return combined


def _aggregate(by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(float(row["combined_metrics"].get("expected_value_score") or 0.0) for row in by_window.values()),
            6,
        ),
        "max_drawdown_pct_max": _round(
            max(float(row["combined_metrics"].get("max_drawdown_pct") or 0.0) for row in by_window.values()),
            6,
        ),
        "min_survival_rate": _round(
            min(float(row["combined_metrics"].get("survival_rate") or 0.0) for row in by_window.values()),
            6,
        ),
        "sleeve_closed_trade_count_sum": sum(
            int(row["sleeve_metrics"].get("closed_trade_count") or 0)
            for row in by_window.values()
        ),
        "sleeve_total_pnl_sum": _round(
            sum(float(row["sleeve_metrics"].get("total_pnl") or 0.0) for row in by_window.values()),
            2,
        ),
        "total_pnl_sum": _round(
            sum(float(row["combined_metrics"].get("total_pnl") or 0.0) for row in by_window.values()),
            2,
        ),
        "trade_count_sum": sum(
            int(row["combined_metrics"].get("trade_count") or 0)
            for row in by_window.values()
        ),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key in sorted(set(before) | set(after)):
        left = before.get(key)
        right = after.get(key)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            out[f"{key}_delta"] = _round(float(right) - float(left), 6)
            out[f"{key}_delta_pct"] = _round(
                (float(right) - float(left)) / abs(float(left)), 6
            ) if float(left) else None
    return out


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _delta(after["aggregate"], before["aggregate"])
    window_checks = {}
    for label in WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        window_checks[label] = {
            "ev_delta": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "pnl_delta": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "max_drawdown_delta": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
        }
    ev_positive_windows = sum(1 for row in window_checks.values() if row["ev_delta"] > 0)
    pnl_positive_windows = sum(1 for row in window_checks.values() if row["pnl_delta"] > 0)
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in window_checks.values())
    passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("sleeve_total_pnl_sum_delta") or 0.0) >= 5_000.0
        and ev_positive_windows >= 2
        and pnl_positive_windows == 3
        and max_drawdown_delta_max <= 0.05
    )
    return {
        "aggregate_delta": aggregate_delta,
        "ev_positive_windows": ev_positive_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "passed": passed,
        "pnl_positive_windows": pnl_positive_windows,
        "rule": (
            "Pass if aggregate EV improves, sleeve PnL delta >= $5k, PnL improves "
            "in all three windows, EV improves in at least two windows, and no "
            "window adds more than 5 percentage points of drawdown."
        ),
        "window_checks": window_checks,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC financial-report T+1 sleeve capacity",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Changed variable: `{payload['changed_variable']}`",
            f"- Before: max_positions={BASELINE_MAX_POSITIONS}; after candidate: max_positions={PROMOTION_VARIANT}",
        "- Replay path: production `build_sec_financial_report_event_sleeve_snapshot`, persist disabled.",
        "",
        "## Aggregate",
        "",
        "| Variant | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in payload["variants"].items():
        agg = row["aggregate"]
        lines.append(
            f"| {name} | {agg['expected_value_score_sum']:.6f} | "
            f"${agg['total_pnl_sum']:,.2f} | ${agg['sleeve_total_pnl_sum']:,.2f} | "
            f"{agg['sleeve_closed_trade_count_sum']} | {agg['max_drawdown_pct_max']:.4f} |"
        )
    impact = payload["production_impact"]
    if impact.get("shared_policy_changed"):
        production_summary = (
            "Promotion applied to the shared default-off paper sleeve config: "
            f"`DEFAULT_MAX_POSITIONS={PROMOTION_VARIANT}`. `run.py` consumes the "
            "same production sleeve builder, `trade_enabled` remains false, and "
            "no live orders or core signal path changed."
        )
    else:
        production_summary = (
            "No live orders or core strategy path changed by this experiment "
            "artifact. A future promotion would remain default-off paper-only "
            "unless a separate shared adapter change and parity test are added."
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            json.dumps(_safe(payload["gate"]), ensure_ascii=False, indent=2, sort_keys=True),
            "",
            "## Production impact",
            "",
            production_summary,
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    now = _utc_now()
    exp100 = _load_exp100()
    universe = get_universe()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        core_results[label] = {
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }

    variants: dict[str, dict[str, Any]] = OrderedDict()
    for max_positions in MAX_POSITION_VARIANTS:
        variant_name = f"max_positions_{max_positions}"
        by_window = {}
        for label, window in WINDOWS.items():
            sleeve = _run_sleeve_replay(
                label,
                window,
                exp100["windows"][label],
                max_positions=max_positions,
            )
            core_curve = core_results[label]["equity_curve"]
            combined_curve = _combine_curves(core_curve, sleeve["daily_pnl"])
            core_metrics = core_results[label]["metrics"]
            combined_metrics = _equity_metrics(
                combined_curve,
                trade_count=int(core_metrics.get("trade_count") or 0)
                + int(sleeve["metrics"].get("closed_trade_count") or 0),
                win_rate=None,
                signals_generated=core_metrics.get("signals_generated"),
                signals_survived=core_metrics.get("signals_survived"),
            )
            by_window[label] = {
                "combined_metrics": combined_metrics,
                "core_metrics": core_metrics,
                "sleeve_metrics": sleeve["metrics"],
            }
        variants[variant_name] = {
            "max_positions": max_positions,
            "by_window": by_window,
            "aggregate": _aggregate(by_window),
        }

    before = variants[f"max_positions_{BASELINE_MAX_POSITIONS}"]
    after = variants[f"max_positions_{PROMOTION_VARIANT}"]
    gate = _gate(after, before)
    decision = (
        "accept_default_off_paper_capacity_candidate"
        if gate["passed"]
        else "reject_capacity_candidate"
    )
    promotion_applied = DEFAULT_MAX_POSITIONS == PROMOTION_VARIANT

    payload: dict[str, Any] = {
        "after_metrics": after["by_window"],
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for the core "
            "baseline, plus production paper-sleeve replay over the same OHLCV "
            "snapshots. Core replay uses REPLAY_PARTIAL_REDUCES and "
            "REGIME_AWARE_EXIT."
        ),
        "before_metrics": before["by_window"],
        "change_type": "alpha_search_capital_allocation",
        "changed_variable": "sec_financial_report_event_sleeve_max_positions",
        "decision": decision,
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "experiment_id": EXPERIMENT_ID,
        "gate": gate,
        "hypothesis": (
            "The frozen SEC financial-report positive T+1 queue has enough "
            "capacity that the default-off paper event sleeve should track more "
            "than one concurrent position without degrading three-window EV or "
            "drawdown guardrails."
        ),
        "lane": "alpha_search",
        "llm_metrics": {"used_llm": False, "llm_role_changed": False},
        "parameters": {
            "default_event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
            "production_default_max_positions_at_run": DEFAULT_MAX_POSITIONS,
            "baseline_max_positions": BASELINE_MAX_POSITIONS,
            "hold_days": "PRIMARY_HORIZON_TRADING_DAYS",
            "max_position_variants": list(MAX_POSITION_VARIANTS),
            "promotion_variant": PROMOTION_VARIANT,
            "source_candidate_artifact": str(SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
        },
        "production_impact": {
            "shared_policy_changed": promotion_applied,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promotion_applied,
            "replay_only": not promotion_applied,
            "parity_test_added": promotion_applied,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "default_off_paper_only": True,
            "live_orders_changed": False,
            "production_signal_path_changed": False,
            "uses_production_sleeve_builder": True,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: SEC financial-report T+1 event queue may "
                "support a larger default-off paper sleeve capacity."
            ),
            "2_history_check": (
                "exp-20260511-100 refreshed forward outcomes and stayed "
                "observed-only; no production paper sleeve max-position capacity "
                "sweep over the three canonical windows was recorded."
            ),
            "3_single_causal_variable": "max_positions only",
            "4_acceptance_standard": (
                "Three fixed windows, aggregate EV improvement, >=$5k sleeve PnL "
                "delta, PnL positive in 3/3 windows, EV positive in >=2/3, no "
                ">5pp drawdown worsening."
            ),
            "5_reproducibility": (
                f"Run .venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
        ],
        "single_causal_variable": "sec_financial_report_event_sleeve_max_positions",
        "status": "accepted_candidate" if gate["passed"] else "rejected",
        "timestamp": now,
        "universe_count": len(universe),
        "variants": variants,
    }

    if not gate["passed"]:
        payload["rejection_reason"] = (
            "Capacity expansion did not clear the three-window replay gate."
        )
    else:
        payload["rejection_reason"] = None

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": "alpha_search",
        "owner": "alpha-search",
        "status": payload["status"],
        "created_at": now,
        "updated_at": now,
        "next_action": (
            "Forward-observe the default-off paper sleeve; do not enable live orders."
            if promotion_applied
            else "If promoted, change only the default-off paper sleeve capacity and "
            "add a focused parity/default-off test; do not enable live orders."
            if gate["passed"]
            else "Do not promote this capacity setting without forward evidence."
        ),
    }
    log_payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "date_range": {
            "primary": {
                "start": WINDOWS["late_strong"]["start"],
                "end": WINDOWS["late_strong"]["end"],
            },
            "secondary": [
                {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
                {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
            ],
        },
        "backtest_protocol": payload["backtest_protocol"],
        "parameters": payload["parameters"],
        "before_metrics": before["aggregate"],
        "after_metrics": after["aggregate"],
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "decision": decision,
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": (
            "Forward out-of-sample default-off paper observation before any live-order scope."
            if promotion_applied
            else "Default-off paper capacity promotion patch plus focused no-orders "
            "test, then forward observation."
            if gate["passed"]
            else "Forward out-of-sample capacity evidence."
        ),
        "production_impact": payload["production_impact"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, log_payload)
    _write_json(DOC_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, log_payload)
    _upsert_registry(payload)

    print(json.dumps(_safe(log_payload), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
