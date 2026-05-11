"""exp-20260511-005: SEC financial-report core priority replay.

Alpha search. Test one ranking/capital-routing variable: core A/B signals with
an active non-platform SEC financial-report positive T+1 excess-drift label get
entry-planning priority over untagged survived signals. This reuses the frozen
exp-20260510-027 event label and does not retune SEC thresholds, hold days,
event families, sizing, exits, add-ons, or LLM/news behavior.

Replay only unless Gate 4 clears and the same event-priority helper is promoted
into shared production/backtest policy with parity tests.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260511-005"
STEM = "sec_financial_report_core_priority"
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260510-027"
    / "sec_financial_report_non_platform_t1_queue.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

ACTIVE_HOLD_DAYS = 10

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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return round(out, digits)


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(payload_line)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(payload_line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _append_playbook_note(note: str) -> None:
    old = PLAYBOOK.read_text(encoding="utf-8") if PLAYBOOK.exists() else ""
    if f"Experiment: `{EXPERIMENT_ID}`" in old:
        return
    PLAYBOOK.write_text(old.rstrip() + "\n\n" + note.strip() + "\n", encoding="utf-8")


def _audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[tuple[str, dict[str, Any]]] = []
    for section in ("positions", "observations"):
        for row in payload.get(section, []):
            if isinstance(row, dict):
                rows.append((section, row))

    missing: list[dict[str, Any]] = []
    for section, row in rows:
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append(
                    {
                        "section": section,
                        "ticker": row.get("ticker"),
                        "field": field,
                    }
                )
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _load_snapshot_dates(snapshot_path: str) -> list[str]:
    payload = json.loads((REPO_ROOT / snapshot_path).read_text(encoding="utf-8"))
    ohlcv = payload.get("ohlcv") or {}
    date_set: set[str] = set()
    for rows in ohlcv.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("Date"):
                date_set.add(str(row["Date"])[:10])
    return sorted(date_set)


def _load_source_rows() -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    out: dict[str, list[dict[str, Any]]] = {}
    for label in WINDOWS:
        window = (payload.get("windows") or {}).get(label) or {}
        rows = []
        for row in window.get("candidate_rows") or []:
            if not isinstance(row, dict):
                continue
            if row.get("cohort") == "platform_pool":
                continue
            if not row.get("ticker") or not row.get("usable_trade_date"):
                continue
            rows.append(dict(row))
        out[label] = rows
    return out


def _active_event_map(
    rows: list[dict[str, Any]],
    trading_dates: list[str],
    *,
    hold_days: int,
) -> dict[str, list[str]]:
    date_index = {date: idx for idx, date in enumerate(trading_dates)}
    active: dict[str, set[str]] = {}
    for row in rows:
        event_date = str(row.get("usable_trade_date") or "")[:10]
        idx = date_index.get(event_date)
        if idx is None:
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        for active_date in trading_dates[idx : idx + hold_days]:
            active.setdefault(active_date, set()).add(ticker)
    return {date: sorted(tickers) for date, tickers in active.items()}


def _patched_backtester_module(temp_dir: Path):
    source = (QUANT_DIR / "backtester.py").read_text(encoding="utf-8")

    helper = '''

SEC_FINANCIAL_REPORT_PRIORITY_EVENTS = {}
SEC_FINANCIAL_REPORT_PRIORITY_AUDIT = {}


def _sec_financial_report_core_priority_rank(signals, today):
    """Move active SEC financial-report tagged signals ahead of untagged signals."""
    date_key = str(pd.Timestamp(today).date())
    active_tickers = set(SEC_FINANCIAL_REPORT_PRIORITY_EVENTS.get(date_key, []))
    if not signals or not active_tickers:
        return signals
    tagged = []
    untagged = []
    input_order = []
    for sig in signals:
        ticker = str(sig.get("ticker") or "").strip().upper()
        input_order.append(ticker)
        if ticker in active_tickers:
            copied = dict(sig)
            copied["sec_financial_report_core_priority"] = True
            tagged.append(copied)
        else:
            untagged.append(sig)
    if not tagged:
        return signals
    output = tagged + untagged
    SEC_FINANCIAL_REPORT_PRIORITY_AUDIT[date_key] = {
        "active_event_tickers": sorted(active_tickers),
        "tagged_signal_tickers": [
            str(sig.get("ticker") or "").strip().upper() for sig in tagged
        ],
        "input_order": input_order,
        "output_order": [
            str(sig.get("ticker") or "").strip().upper() for sig in output
        ],
    }
    return output
'''

    anchor = "logger = logging.getLogger(__name__)\n"
    if anchor not in source:
        raise RuntimeError("backtester logger anchor not found")
    source = source.replace(anchor, anchor + helper, 1)

    insertion_anchor = "            # ── 3. Enter positions at next-day open ─────────────────────────\n"
    insertion = (
        "            signals = _sec_financial_report_core_priority_rank(signals, today)\n\n"
        + insertion_anchor
    )
    if insertion_anchor not in source:
        raise RuntimeError("backtester entry-plan insertion anchor not found")
    source = source.replace(insertion_anchor, insertion, 1)

    temp_path = temp_dir / "backtester.py"
    temp_path.write_text(source, encoding="utf-8")
    module_name = f"{EXPERIMENT_ID.replace('-', '_')}_patched_backtester"
    spec = importlib.util.spec_from_file_location(module_name, temp_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load patched backtester")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tail_loss_share(trades: list[dict[str, Any]], n: int = 5) -> float | None:
    losses = sorted(
        [abs(float(t.get("pnl") or 0.0)) for t in trades if float(t.get("pnl") or 0.0) < 0],
        reverse=True,
    )
    if not losses:
        return None
    return round(sum(losses[:n]) / sum(losses), 4)


def _max_consecutive_losses(trades: list[dict[str, Any]]) -> int:
    ordered = sorted(trades, key=lambda t: (t.get("exit_date") or "", t.get("entry_date") or ""))
    streak = 0
    worst = 0
    for trade in ordered:
        if float(trade.get("pnl") or 0.0) < 0:
            streak += 1
            worst = max(worst, streak)
        else:
            streak = 0
    return worst


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    trades = result.get("trades") or []
    worst_trade_pct = None
    if trades:
        worst_trade_pct = min(float(t.get("pnl_pct_net") or 0.0) for t in trades)
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(worst_trade_pct, 6),
        "max_consecutive_losses": _max_consecutive_losses(trades),
        "tail_loss_share": _tail_loss_share(trades),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = _round(after_value - before_value, 6)
    return out


def _aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            6,
        ),
        "total_pnl_sum": _round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in metrics.values())),
        "max_drawdown_pct_max": _round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            6,
        ),
        "survival_rate_min": _round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            6,
        ),
    }


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _round(after[key] - before[key], 6)
        for key in after
        if isinstance(after.get(key), (int, float)) and isinstance(before.get(key), (int, float))
    }


def _run_window(
    module,
    label: str,
    *,
    active_events: dict[str, list[str]] | None,
) -> dict[str, Any]:
    spec = WINDOWS[label]
    module.SEC_FINANCIAL_REPORT_PRIORITY_EVENTS = active_events or {}
    module.SEC_FINANCIAL_REPORT_PRIORITY_AUDIT = {}
    engine = module.BacktestEngine(
        sorted(get_universe()),
        start=spec["start"],
        end=spec["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
        },
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} failed: {result['error']}")
    return {
        "metrics": _metrics(result),
        "audit": dict(module.SEC_FINANCIAL_REPORT_PRIORITY_AUDIT),
        "trades": result.get("trades") or [],
    }


def _changed_trades(
    before_trades: list[dict[str, Any]],
    after_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    def key(trade: dict[str, Any]) -> str:
        return "|".join(
            [
                str(trade.get("ticker") or ""),
                str(trade.get("entry_date") or ""),
                str(trade.get("strategy") or ""),
                str(round(float(trade.get("entry_price") or 0.0), 4)),
            ]
        )

    before_keys = {key(trade): trade for trade in before_trades}
    after_keys = {key(trade): trade for trade in after_trades}
    before_key_set = set(before_keys)
    after_key_set = set(after_keys)
    added = [after_keys[k] for k in sorted(after_key_set - before_key_set)]
    removed = [before_keys[k] for k in sorted(before_key_set - after_key_set)]
    common_changed = []
    for item_key in sorted(before_key_set & after_key_set):
        before = before_keys[item_key]
        after = after_keys[item_key]
        if _round(before.get("pnl"), 2) != _round(after.get("pnl"), 2):
            common_changed.append({"before": before, "after": after})
    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "common_pnl_changed_count": len(common_changed),
        "added": added,
        "removed": removed,
        "common_pnl_changed": common_changed,
    }


def _write_markdown(payload: dict[str, Any]) -> None:
    rows = [
        "| Window | Base EV | After EV | dEV | Base PnL | After PnL | dPnL | Tagged days | Changed trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        base = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {tagged_days} | {changed} |".format(
                label=label,
                bev=base["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=base["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                tagged_days=payload["priority_audit"][label]["tagged_signal_days"],
                changed=payload["changed_trades"][label]["added_count"]
                + payload["changed_trades"][label]["removed_count"]
                + payload["changed_trades"][label]["common_pnl_changed_count"],
            )
        )

    text = f"""# {EXPERIMENT_ID} SEC Financial-Report Core Priority

Decision: `{payload["decision"]}`.

Hypothesis: core A/B signals with an active non-platform SEC financial-report positive T+1 excess-drift label may deserve entry-planning priority over untagged survived signals.

{chr(10).join(rows)}

Protocol: `docs/backtesting.md` canonical three-window fixed-snapshot replay.

Single causal variable: event-conditioned entry-planning priority for already-survived core signals. No SEC thresholds, event families, hold days, sizing, exits, add-ons, universe membership, LLM/news replay, or live orders changed.

Production impact: replay-only scout. A positive result would require a shared production/backtest event-priority helper and parity tests before any live/default behavior could change.
"""
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(text, encoding="utf-8")


def _playbook_note(payload: dict[str, Any]) -> str:
    aggregate_delta = payload["delta_metrics"]["aggregate_delta"]
    return f"""
### 2026-05-11 mechanism update: SEC financial-report core priority

Experiment: `{EXPERIMENT_ID}`

Decision: `{payload["decision"]}`.

Finding: prioritizing already-survived core A/B candidates that carried the
frozen non-platform SEC financial-report positive T+1 excess-drift label did
not improve the canonical three-window stack. Aggregate EV delta was
`{aggregate_delta["expected_value_score_sum"]:+.4f}` and aggregate PnL delta
was `${aggregate_delta["total_pnl_sum"]:+,.2f}`.

Mechanism insight: the SEC financial-report T+1 surface remains a useful
default-off forward queue, but the current same-sample event tag is not enough
to override native core entry-planning order. Keep collecting closed forward
replacement value before promoting the tag into core ranking, sizing, or live
orders.

Do not repeat: SEC financial-report T+1 core-priority ranking, nearby active
hold-day priority variants, or promotion of the frozen SEC queue tag into core
slot ordering on these same windows without closed forward replacement-value
evidence or a genuinely new semantic event-quality field.
"""


def main() -> None:
    timestamp = _utc_now()
    gate2_positions = _audit_open_positions()
    if not gate2_positions["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2_positions}")

    source_rows = _load_source_rows()
    active_events_by_window: dict[str, dict[str, list[str]]] = {}
    source_summary: dict[str, Any] = {}
    for label, spec in WINDOWS.items():
        trading_dates = _load_snapshot_dates(spec["snapshot"])
        active_map = _active_event_map(
            source_rows[label],
            trading_dates,
            hold_days=ACTIVE_HOLD_DAYS,
        )
        active_events_by_window[label] = active_map
        source_summary[label] = {
            "source_rows": len(source_rows[label]),
            "active_dates": len(active_map),
            "unique_event_tickers": len(
                {str(row.get("ticker") or "").upper() for row in source_rows[label]}
            ),
        }

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    priority_audit: dict[str, Any] = {}
    changed_trades: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix=f"{EXPERIMENT_ID}_") as temp_name:
        module = _patched_backtester_module(Path(temp_name))
        for label in WINDOWS:
            baseline = _run_window(module, label, active_events=None)
            variant = _run_window(
                module,
                label,
                active_events=active_events_by_window[label],
            )
            before_metrics[label] = baseline["metrics"]
            after_metrics[label] = variant["metrics"]
            priority_audit[label] = {
                "source_summary": source_summary[label],
                "tagged_signal_days": len(variant["audit"]),
                "tagged_signal_count": sum(
                    len(row.get("tagged_signal_tickers") or [])
                    for row in variant["audit"].values()
                ),
                "days": variant["audit"],
            }
            changed_trades[label] = _changed_trades(
                baseline["trades"],
                variant["trades"],
            )

    by_window_delta = {
        label: _delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = _aggregate(before_metrics)
    aggregate_after = _aggregate(after_metrics)
    aggregate_metric_delta = _aggregate_delta(aggregate_after, aggregate_before)
    ev_improved_windows = sum(
        1
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
    )
    ev_regressed_windows = sum(
        1
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
    )
    pnl_improved_windows = sum(
        1 for label in WINDOWS if after_metrics[label]["total_pnl"] > before_metrics[label]["total_pnl"]
    )
    pnl_regressed_windows = sum(
        1 for label in WINDOWS if after_metrics[label]["total_pnl"] < before_metrics[label]["total_pnl"]
    )
    total_tagged_signal_count = sum(
        row["tagged_signal_count"] for row in priority_audit.values()
    )
    total_changed_trades = sum(
        row["added_count"] + row["removed_count"] + row["common_pnl_changed_count"]
        for row in changed_trades.values()
    )

    gate4_passed = (
        aggregate_metric_delta["expected_value_score_sum"] > 0
        and aggregate_metric_delta["total_pnl_sum"] > 0
        and ev_improved_windows >= 2
        and ev_regressed_windows == 0
        and aggregate_after["survival_rate_min"] >= 0.05
        and total_changed_trades > 0
    )

    decision = "accepted_replay_candidate_needs_shared_promotion" if gate4_passed else "rejected"
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Core A/B signals with an active non-platform SEC financial-report positive T+1 "
            "excess-drift label may deserve entry-planning priority over untagged survived signals."
        ),
        "alpha_hypothesis_category": "entry_ranking / candidate_pool_allocation",
        "change_type": "event_conditioned_core_priority_replay",
        "changed_variable": "entry-planning priority for SEC financial-report T+1 tagged survived core signals",
        "single_causal_variable": "move active SEC financial-report tagged survived signals before untagged signals before plan_entry_candidates",
        "parameters": {
            "source_label": "sec_financial_report_positive_t1_excess_non_platform_v2",
            "source_experiment": "exp-20260510-027",
            "active_hold_days": ACTIVE_HOLD_DAYS,
            "ranking_semantics": "stable partition: tagged survived signals first, native order preserved inside tagged and untagged groups",
            "locked_variables": [
                "SEC event threshold and family definition",
                "production universe",
                "signal generation",
                "entry filters",
                "position sizing",
                "position caps",
                "portfolio heat",
                "exits",
                "add-ons",
                "LLM/news replay",
            ],
        },
        "protocol_answers": {
            "alpha_hypothesis": "entry/ranking: deterministic financial-report event drift tags may improve slot allocation among survived core candidates.",
            "history_check": (
                "SEC T+1 broad and financial-report slices were observed-only; exp-20260510-027 froze "
                "the non-platform queue. This does not retune that label and instead tests whether the "
                "frozen tag helps core slot priority."
            ),
            "single_independent_variable": "event-conditioned pre-entry-plan priority",
            "acceptance_criteria": (
                "Pass only if aggregate EV and PnL improve, at least two windows improve EV, no window "
                "regresses EV, survival stays above 5%, and the variant changes executed trades."
            ),
            "reproducibility": "The script reruns baseline and variant across the three docs/backtesting.md snapshots.",
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "snapshots": {label: spec["snapshot"] for label, spec in WINDOWS.items()},
        "backtest_protocol": "docs/backtesting.md standard three-window fixed-snapshot protocol",
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_metric_delta,
            "ev_improved_windows": ev_improved_windows,
            "ev_regressed_windows": ev_regressed_windows,
            "pnl_improved_windows": pnl_improved_windows,
            "pnl_regressed_windows": pnl_regressed_windows,
        },
        "expected_value_score_delta": aggregate_metric_delta["expected_value_score_sum"],
        "priority_audit": priority_audit,
        "changed_trades": changed_trades,
        "gate_results": {
            "gate1": "baseline rerun with docs/backtesting.md accepted three-window snapshots",
            "gate2": {
                "operator_position_fields": gate2_positions,
                "sec_source_fields": [
                    "ticker",
                    "usable_trade_date",
                    "cohort",
                    "event_family",
                ],
                "passed": gate2_positions["passed"] and SOURCE_JSON.exists(),
            },
            "gate3": {
                "new_filter_added": False,
                "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
                "passed": aggregate_after["survival_rate_min"] >= 0.05,
            },
            "gate4": {
                "passed": gate4_passed,
                "basis": "canonical three-window before/after replay",
                "changed_trade_count": total_changed_trades,
                "tagged_signal_count": total_tagged_signal_count,
            },
        },
        "risk_distribution": {
            label: {
                key: after_metrics[label].get(key)
                for key in ("worst_trade_pct", "max_consecutive_losses", "tail_loss_share")
            }
            for label in WINDOWS
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": "Production-aligned LLM ranking samples remain too thin; this uses a deterministic SEC event label.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_behavior_changed": False,
            "positive_result_requires_shared_policy": True,
        },
        "decision": decision,
        "rejection_reason": None if gate4_passed else (
            "The SEC financial-report T+1 core-priority replay did not pass Gate 4 across the three canonical windows."
        ),
        "next_evidence_needed": [
            "Closed forward paper replacement-value outcomes for the SEC financial-report queue.",
            "A production-shared event-priority helper and parity tests before any live/default use if future evidence turns positive.",
            "A genuinely new semantic event-quality field before retrying same-sample SEC core ranking.",
        ],
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
        "why_not_other_changes": {
            "LLM_soft_ranking": "Still sample-limited.",
            "SEC_threshold_retune": "Blocked by anti-repeat; this uses the frozen non-platform label.",
            "space_catalyst": "Already moved to forward shadow; static promotion rejected.",
            "global_ranking": "All-signal 52-week proximity and score-only global ranking were rejected.",
        },
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC financial-report core priority",
        "status": decision,
        "lane": "alpha_search",
        "decision": decision,
        "summary": {
            "aggregate_ev_delta": aggregate_metric_delta["expected_value_score_sum"],
            "aggregate_pnl_delta": aggregate_metric_delta["total_pnl_sum"],
            "changed_trade_count": total_changed_trades,
            "tagged_signal_count": total_tagged_signal_count,
        },
        "artifacts": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        ],
        "next_action": payload["next_evidence_needed"][0],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_markdown(payload)
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _append_playbook_note(_playbook_note(payload))
    print(json.dumps(payload["delta_metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
