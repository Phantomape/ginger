"""Shadow replay for event-quality confirmed leader runners.

This is the next retry after exp-20260506-010 rejected a broad OHLCV-only
event-leader profit ladder.  The exit mechanics are intentionally locked to
the best prior shadow variant; the single new causal variable is the qualifier:
only earnings/SEC events with auditable quality, positive excess reaction,
post-event drift, and no full retracement are allowed to use the runner mode.

No production or canonical backtest behavior is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from exp_20260506_010_event_leader_profit_ladder import (  # noqa: E402
    REPO_ROOT,
    WINDOWS,
    _append_jsonl,
    _delta,
    _leader_trade,
    _load_json,
    _load_snapshot,
    _official_metric_view,
    _proxy_metrics,
    _row_index,
    _simulate_variant_trade,
    _write_json,
)


EXPERIMENT_ID = "exp-20260506-023"
EVENT_PACKET_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260504-002"
    / "earnings_sec_price_reaction_packet.json"
)

QUALIFIER = {
    "sec_packet_type": "results_8k",
    "min_eps_surprise_pct": 8.0,
    "min_reaction_excess_return": 0.02,
    "min_post_event_to_entry_excess": 0.02,
    "min_event_gain_retained": 0.50,
    "min_event_entry_lag_trading_days": 3,
    "max_event_entry_lag_trading_days": 20,
}

COHORT_CONFIRM_DAYS = 5
RUNNER_VARIANT = {
    "profit_floor_trigger_r": None,
    "profit_floor_r": None,
    "target_partial_fraction": 0.50,
    "trail_after_target_r": 1.5,
}


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _load_event_packets() -> list[dict[str, Any]]:
    payload = _load_json(EVENT_PACKET_PATH)
    return list(((payload.get("shadow_metrics") or {}).get("sample_events") or []))


def _event_quality(packet: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    eps_surprise = _num(packet.get("eps_surprise_pct"))
    reaction_excess = _num(packet.get("reaction_excess_return"))
    sec_ok = packet.get("sec_packet_type") == QUALIFIER["sec_packet_type"]
    eps_ok = eps_surprise is not None and eps_surprise >= QUALIFIER["min_eps_surprise_pct"]
    reaction_ok = (
        reaction_excess is not None
        and reaction_excess >= QUALIFIER["min_reaction_excess_return"]
    )
    return bool(sec_ok and eps_ok and reaction_ok), {
        "sec_ok": sec_ok,
        "eps_surprise_pct": eps_surprise,
        "eps_ok": eps_ok,
        "reaction_excess_return": reaction_excess,
        "reaction_ok": reaction_ok,
    }


def _trading_day_distance(rows: list[dict[str, Any]], start: str, end: str) -> int | None:
    start_idx = _row_index(rows, start)
    end_idx = _row_index(rows, end)
    if start_idx is None or end_idx is None or end_idx < start_idx:
        return None
    return end_idx - start_idx


def _retained_event_gain(
    packet: dict[str, Any],
    rows: list[dict[str, Any]],
    test_date: str,
) -> float | None:
    reaction_idx = _row_index(rows, str(packet.get("reaction_date") or "")[:10])
    test_idx = _row_index(rows, test_date)
    if reaction_idx is None or reaction_idx <= 0 or test_idx is None:
        return None
    pre_event_close = rows[reaction_idx - 1]["close"]
    reaction_close = rows[reaction_idx]["close"]
    test_open = rows[test_idx]["open"]
    event_gain = reaction_close - pre_event_close
    if event_gain <= 0:
        return None
    return (test_open - pre_event_close) / event_gain


def _post_event_excess(
    packet: dict[str, Any],
    ticker_rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
    test_date: str,
) -> float | None:
    entry_date = str(packet.get("entry_date") or "")[:10]
    ticker_start_idx = _row_index(ticker_rows, entry_date)
    ticker_end_idx = _row_index(ticker_rows, test_date)
    spy_start_idx = _row_index(spy_rows, entry_date)
    spy_end_idx = _row_index(spy_rows, test_date)
    if (
        ticker_start_idx is None
        or ticker_end_idx is None
        or spy_start_idx is None
        or spy_end_idx is None
        or ticker_end_idx < ticker_start_idx
        or spy_end_idx < spy_start_idx
    ):
        return None
    ticker_base = ticker_rows[ticker_start_idx]["open"]
    ticker_test = ticker_rows[ticker_end_idx]["open"]
    spy_base = spy_rows[spy_start_idx]["open"]
    spy_test = spy_rows[spy_end_idx]["open"]
    if ticker_base <= 0 or spy_base <= 0:
        return None
    return (ticker_test / ticker_base - 1.0) - (spy_test / spy_base - 1.0)


def _matches_event_quality_runner(
    trade: dict[str, Any],
    packets: list[dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[bool, dict[str, Any]]:
    ticker = str(trade.get("ticker") or "").upper()
    trade_entry = str(trade.get("entry_date") or "")[:10]
    ticker_rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    if not ticker_rows or not spy_rows:
        return False, {"reason": "missing_price_rows"}
    if not _leader_trade(trade):
        return False, {"reason": "not_spy_relative_leader"}

    candidates = []
    for packet in packets:
        if str(packet.get("ticker") or "").upper() != ticker:
            continue
        event_entry = str(packet.get("entry_date") or "")[:10]
        lag = _trading_day_distance(ticker_rows, event_entry, trade_entry)
        if lag is None:
            continue
        if not (
            QUALIFIER["min_event_entry_lag_trading_days"]
            <= lag
            <= QUALIFIER["max_event_entry_lag_trading_days"]
        ):
            continue
        quality_ok, quality = _event_quality(packet)
        retained = _retained_event_gain(packet, ticker_rows, trade_entry)
        post_excess = _post_event_excess(packet, ticker_rows, spy_rows, trade_entry)
        retained_ok = (
            retained is not None
            and retained >= QUALIFIER["min_event_gain_retained"]
        )
        post_excess_ok = (
            post_excess is not None
            and post_excess >= QUALIFIER["min_post_event_to_entry_excess"]
        )
        candidate = {
            "ticker": ticker,
            "event_date": packet.get("event_date"),
            "event_entry_date": event_entry,
            "trade_entry_date": trade_entry,
            "event_to_trade_lag": lag,
            "quality": quality,
            "event_gain_retained": retained,
            "event_gain_retained_ok": retained_ok,
            "post_event_to_entry_excess": post_excess,
            "post_event_to_entry_excess_ok": post_excess_ok,
        }
        candidate["qualified"] = bool(quality_ok and retained_ok and post_excess_ok)
        candidates.append(candidate)

    qualified = [item for item in candidates if item["qualified"]]
    if not qualified:
        return False, {
            "reason": "no_qualified_event_quality_packet",
            "near_packets": candidates,
        }
    best = max(
        qualified,
        key=lambda item: (
            item.get("post_event_to_entry_excess") or 0.0,
            item.get("event_gain_retained") or 0.0,
        ),
    )
    return True, best


def _make_runner_trades(
    baseline: dict[str, Any],
    packets: list[dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
    end_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trades = []
    touched = []
    for trade in baseline.get("trades", []):
        ticker = str(trade.get("ticker") or "").upper()
        rows = snapshot.get(ticker) or []
        qualified, qualifier = _matches_event_quality_runner(trade, packets, snapshot)
        if not qualified:
            trades.append(dict(trade))
            continue
        out = _simulate_variant_trade(dict(trade), rows, end_date, RUNNER_VARIANT)
        out["event_quality_leader_runner_applied"] = True
        out["event_quality_leader_runner_qualifier"] = qualifier
        touched.append(
            {
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "entry_date": trade.get("entry_date"),
                "baseline_exit_date": trade.get("exit_date"),
                "variant_exit_date": out.get("exit_date"),
                "baseline_exit_reason": trade.get("exit_reason"),
                "variant_exit_reason": out.get("exit_reason"),
                "baseline_pnl": round(float(trade.get("pnl") or 0.0), 2),
                "variant_pnl": round(float(out.get("pnl") or 0.0), 2),
                "pnl_delta": round(
                    float(out.get("pnl") or 0.0)
                    - float(trade.get("pnl") or 0.0),
                    2,
                ),
                "qualifier": qualifier,
                "partial_events": out.get("variant_partial_events") or [],
            }
        )
        trades.append(out)
    return trades, touched


def _forward_return(
    rows: list[dict[str, Any]],
    entry_idx: int,
    horizon: int,
) -> dict[str, Any]:
    exit_idx = entry_idx + horizon
    if entry_idx < 0 or exit_idx >= len(rows):
        return {"status": "pending"}
    entry_open = rows[entry_idx]["open"]
    exit_close = rows[exit_idx]["close"]
    if entry_open <= 0:
        return {"status": "invalid_price"}
    return {
        "status": "valid",
        "entry_date": rows[entry_idx]["date"],
        "exit_date": rows[exit_idx]["date"],
        "return": round(exit_close / entry_open - 1.0, 6),
    }


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _cohort_diagnostics(
    packets: list[dict[str, Any]],
    snapshots_by_window: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    rows = []
    rejection_counts: dict[str, int] = {}
    watched = []
    for packet in packets:
        ticker = str(packet.get("ticker") or "").upper()
        event_entry = str(packet.get("entry_date") or "")[:10]
        window_label = None
        for label, spec in WINDOWS.items():
            if spec["start"] <= event_entry <= spec["end"]:
                window_label = label
                break
        if window_label is None:
            continue
        snapshot = snapshots_by_window[window_label]
        ticker_rows = snapshot.get(ticker) or []
        spy_rows = snapshot.get("SPY") or []
        quality_ok, quality = _event_quality(packet)
        reason = None
        if not quality_ok:
            reason = "event_quality_failed"
        entry_idx = _row_index(ticker_rows, event_entry) if ticker_rows else None
        confirm_idx = entry_idx + COHORT_CONFIRM_DAYS if entry_idx is not None else None
        confirm_date = (
            ticker_rows[confirm_idx]["date"]
            if confirm_idx is not None and confirm_idx < len(ticker_rows)
            else None
        )
        retained = (
            _retained_event_gain(packet, ticker_rows, confirm_date)
            if confirm_date else None
        )
        post_excess = (
            _post_event_excess(packet, ticker_rows, spy_rows, confirm_date)
            if confirm_date else None
        )
        if reason is None and confirm_date is None:
            reason = "missing_confirm_day"
        if reason is None and (
            retained is None or retained < QUALIFIER["min_event_gain_retained"]
        ):
            reason = "full_or_major_retracement"
        if reason is None and (
            post_excess is None
            or post_excess < QUALIFIER["min_post_event_to_entry_excess"]
        ):
            reason = "post_event_drift_failed"

        row = {
            "ticker": ticker,
            "window": window_label,
            "event_date": packet.get("event_date"),
            "event_entry_date": event_entry,
            "confirm_date": confirm_date,
            "quality": quality,
            "event_gain_retained": retained,
            "post_event_to_confirm_excess": post_excess,
            "qualified": reason is None,
            "rejection_reason": reason,
            "horizons_from_confirm_plus_1": {},
        }
        if row["qualified"] and confirm_idx is not None:
            forward_entry_idx = confirm_idx + 1
            for horizon in (5, 10, 20):
                fwd = _forward_return(ticker_rows, forward_entry_idx, horizon)
                spy_fwd = _forward_return(spy_rows, _row_index(spy_rows, ticker_rows[forward_entry_idx]["date"]) or -1, horizon)
                if fwd.get("status") == "valid" and spy_fwd.get("status") == "valid":
                    fwd["excess_vs_spy"] = round(fwd["return"] - spy_fwd["return"], 6)
                row["horizons_from_confirm_plus_1"][f"{horizon}d"] = fwd
        else:
            rejection_counts[reason or "unknown"] = rejection_counts.get(reason or "unknown", 0) + 1
        if ticker in {"META", "NFLX"}:
            watched.append(row)
        rows.append(row)

    qualified_rows = [row for row in rows if row["qualified"]]
    summary = OrderedDict()
    for horizon in ("5d", "10d", "20d"):
        vals = [
            row["horizons_from_confirm_plus_1"].get(horizon, {}).get("return")
            for row in qualified_rows
        ]
        excess_vals = [
            row["horizons_from_confirm_plus_1"].get(horizon, {}).get("excess_vs_spy")
            for row in qualified_rows
        ]
        vals = [float(value) for value in vals if isinstance(value, (int, float))]
        excess_vals = [
            float(value) for value in excess_vals if isinstance(value, (int, float))
        ]
        summary[horizon] = {
            "count": len(vals),
            "avg_return": _avg(vals),
            "win_rate": (
                round(sum(1 for value in vals if value > 0) / len(vals), 4)
                if vals else None
            ),
            "avg_excess_vs_spy": _avg(excess_vals),
            "excess_win_rate": (
                round(sum(1 for value in excess_vals if value > 0) / len(excess_vals), 4)
                if excess_vals else None
            ),
        }

    return {
        "candidate_count": len(rows),
        "qualified_count": len(qualified_rows),
        "rejection_counts": rejection_counts,
        "forward_summary": summary,
        "qualified_rows": qualified_rows,
        "meta_nflx_rows": watched,
    }


def _analyze() -> dict[str, Any]:
    packets = _load_event_packets()
    snapshots_by_window = {
        label: _load_snapshot(REPO_ROOT / spec["snapshot"])
        for label, spec in WINDOWS.items()
    }
    by_window: dict[str, Any] = OrderedDict()
    for label, spec in WINDOWS.items():
        baseline = _load_json(REPO_ROOT / spec["baseline"])
        snapshot = snapshots_by_window[label]
        before_proxy = _proxy_metrics(
            list(baseline.get("trades") or []),
            snapshot,
            spec["start"],
            spec["end"],
        )
        runner_trades, touched = _make_runner_trades(
            baseline,
            packets,
            snapshot,
            spec["end"],
        )
        after_proxy = _proxy_metrics(
            runner_trades,
            snapshot,
            spec["start"],
            spec["end"],
        )
        by_window[label] = {
            "official_baseline_metrics": _official_metric_view(baseline),
            "before_proxy_metrics": before_proxy,
            "after_proxy_metrics": after_proxy,
            "delta_proxy_metrics": _delta(after_proxy, before_proxy),
            "touched_trade_count": len(touched),
            "touched_pnl_delta": round(sum(item["pnl_delta"] for item in touched), 2),
            "touched_trades": touched,
            "coverage_note": (
                "event packet coverage available"
                if label == "late_strong"
                else "blocked_no_historical_event_packets"
            ),
        }

    ev_delta_sum = 0.0
    pnl_delta_sum = 0.0
    ev_improved = 0
    pnl_improved = 0
    touched_count = 0
    touched_pnl_delta = 0.0
    for row in by_window.values():
        delta = row["delta_proxy_metrics"]
        ev_delta = float(delta.get("expected_value_score") or 0.0)
        pnl_delta = float(delta.get("total_pnl") or 0.0)
        ev_delta_sum += ev_delta
        pnl_delta_sum += pnl_delta
        ev_improved += int(ev_delta > 0)
        pnl_improved += int(pnl_delta > 0)
        touched_count += int(row["touched_trade_count"])
        touched_pnl_delta += float(row["touched_pnl_delta"])

    return {
        "by_window": by_window,
        "aggregate": {
            "expected_value_score_delta_sum": round(ev_delta_sum, 4),
            "total_pnl_delta_sum": round(pnl_delta_sum, 2),
            "ev_windows_improved": ev_improved,
            "pnl_windows_improved": pnl_improved,
            "touched_trade_count": touched_count,
            "touched_pnl_delta_sum": round(touched_pnl_delta, 2),
        },
        "cohort_diagnostics": _cohort_diagnostics(packets, snapshots_by_window),
    }


def main() -> int:
    analysis = _analyze()
    aggregate = analysis["aggregate"]
    gate4_shadow_passed = (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["touched_trade_count"] >= 3
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": timestamp,
        "lane": "alpha_search",
        "status": "promising_shadow_only" if gate4_shadow_passed else "rejected_shadow",
        "decision": "shadow_only_not_production_promoted",
        "change_type": "exit_lifecycle_shadow_replay",
        "mechanism_family": "event_quality_leader_runner",
        "hypothesis": (
            "Large-cap leaders after auditable earnings/SEC re-rating should enter "
            "a runner lifecycle only when the event has positive financial quality, "
            "positive excess reaction, post-event drift, and no full retracement."
        ),
        "alpha_hypothesis": {
            "category": "exit / lifecycle winner capture",
            "why_not_repeat_of_exp_20260506_010": (
                "The prior OHLCV-only event proxy was rejected. This run keeps the "
                "same runner exit mechanics and changes only the event qualifier to "
                "require SEC results-8K context, EPS surprise, excess reaction, "
                "post-event drift confirmation, and retained event gain."
            ),
        },
        "historical_experiment_check": {
            "similar_failures_checked": {
                "exp-20260506-010": "OHLCV proxy + simple profit ladder rejected.",
                "exp-20260506-006": "Broad SPY-leader target width rejected.",
                "simple_profit_protection": "Playbook blocks broad profit floors.",
            },
            "mechanism_insight_check": (
                "This avoids nearby target/trailing sweeps by changing the cohort "
                "definition, not the exit parameters."
            ),
        },
        "parameters": {
            "single_causal_variable": "event-quality plus post-event drift qualifier",
            "qualifier": QUALIFIER,
            "cohort_confirm_days": COHORT_CONFIRM_DAYS,
            "locked_runner_variant_from_exp_20260506_010": RUNNER_VARIANT,
            "locked_variables": [
                "candidate universe",
                "signal generation",
                "entry filters",
                "entry ordering",
                "risk sizing",
                "position slots",
                "add-ons",
                "LLM/news gates",
                "runner exit parameters",
            ],
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            label: spec["state_note"]
            for label, spec in WINDOWS.items()
        },
        "coverage": {
            "event_packet_source": str(EVENT_PACKET_PATH.relative_to(REPO_ROOT)),
            "canonical_window_gap": (
                "The SEC/earnings event packet source covers the late_strong "
                "canonical window only. mid_weak and old_thin remain blocked for "
                "semantic event replay, so this cannot be promoted even if the "
                "covered-window shadow looks good."
            ),
        },
        "results": analysis,
        "gate4_shadow": {
            "passed": gate4_shadow_passed,
            "basis": (
                "Fixed-entry shadow requires positive proxy EV in at least two "
                "canonical windows and at least three touched trades. Coverage gaps "
                "also block production promotion."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "promotion_requirement": (
                "Promotion would require shared event-quality state and runner "
                "policy in run.py/backtester.py, plus historical event packets in "
                "all canonical windows."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": (
                "This is not a judgment against LLM semantics. It uses structured "
                "SEC/earnings packets because full historical LLM event replay is "
                "still sparse."
            ),
        },
        "risk_of_change": (
            "A runner can keep capital tied up after target. Fixed-entry replay "
            "does not measure slot reuse or opportunity cost."
        ),
        "next_action": (
            "Do not promote unless multi-window event semantics are available and "
            "the qualified cohort creates enough touched-trade evidence."
        ),
    }

    result_path = (
        REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / "event_quality_leader_runner.json"
    )
    log_path = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    artifact_path = (
        REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_event_quality_leader_runner.md"
    )

    _write_json(result_path, payload)
    _write_json(log_path, payload)
    _write_json(
        ticket_path,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": payload["lane"],
            "status": payload["status"],
            "hypothesis": payload["hypothesis"],
            "next_action": payload["next_action"],
        },
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("w", encoding="utf-8") as handle:
        handle.write(f"# {EXPERIMENT_ID}: Event-Quality Leader Runner\n\n")
        handle.write(f"- Status: `{payload['status']}`\n")
        handle.write(
            "- Aggregate proxy EV delta: "
            f"`{aggregate['expected_value_score_delta_sum']}`\n"
        )
        handle.write(
            "- Aggregate proxy PnL delta: "
            f"`{aggregate['total_pnl_delta_sum']}`\n"
        )
        handle.write(f"- Touched trades: `{aggregate['touched_trade_count']}`\n")
        handle.write(
            "- Qualified standalone event cohort: "
            f"`{analysis['cohort_diagnostics']['qualified_count']}` / "
            f"`{analysis['cohort_diagnostics']['candidate_count']}`\n\n"
        )
        handle.write(
            "This is fixed-entry and standalone-cohort shadow evidence only; it "
            "does not model slot reuse or production event-state parity.\n"
        )

    _append_jsonl(
        REPO_ROOT / "docs" / "experiment_log.jsonl",
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "change_type": payload["change_type"],
            "hypothesis": payload["hypothesis"],
            "date_range": payload["date_range"],
            "parameters": payload["parameters"],
            "market_regime_summary": payload["market_regime_summary"],
            "before_metrics": "see docs/experiments/logs/exp-20260506-023.json",
            "after_metrics": "see docs/experiments/logs/exp-20260506-023.json",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "decision": payload["status"],
            "rejection_reason": (
                None if gate4_shadow_passed else "Insufficient multi-window and touched-trade evidence."
            ),
            "production_impact": payload["production_impact"],
        },
    )

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "aggregate": aggregate,
        "cohort": payload["results"]["cohort_diagnostics"]["forward_summary"],
        "result_path": str(result_path),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
