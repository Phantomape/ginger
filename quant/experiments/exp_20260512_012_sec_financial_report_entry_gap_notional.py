"""exp-20260512-012: SEC financial-report entry-gap notional.

Alpha search on one causal variable: a paper-notional scalar for accepted
SEC financial-report T+1 sleeve entries whose actual T+2 open is non-negative
versus the prior trading day's close. The intent is to test whether the
post-filing drift queue deserves more risk only when the fill itself confirms
that the immediate reaction has not faded before entry.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260512-012"
STEM = "exp_20260512_012_sec_financial_report_entry_gap_notional"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exp_20260511_112_sec_financial_report_t1_sleeve_capacity import (  # noqa: E402
    WINDOWS,
    _aggregate,
    _combine_curves,
    _core_metrics,
    _equity_metrics,
    _load_exp100,
    _load_snapshot_prices,
    _normalise_core_curve,
    _rebuild_sleeve_state,
    _round,
    _rows_by_t1_date,
    _run_core_backtest,
    _safe,
    _write_json,
)
from exp_20260512_002_sec_financial_report_hold_days import (  # noqa: E402
    _filter_current_queue,
)
from sec_event_queue import FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY  # noqa: E402
from sec_financial_report_event_sleeve import (  # noqa: E402
    DEFAULT_EVENT_NOTIONAL_USD,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_financial_report_entry_gap_notional.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_ENTRY_GAP_SCALAR = 1.0
ENTRY_GAP_SCALAR_VARIANTS = (1.0, 1.10, 1.25, 1.50)
ENTRY_GAP_FLOOR = 0.0
MIN_PROMOTION_CLOSED_TRADES = 40
MIN_ENTRY_GAP_BUCKET_CLOSED_TRADES = 20
MAX_DRAWDOWN_WORSENING = 0.005


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
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


def _window_prev_date_map(prices_by_date: OrderedDict[str, dict[str, Any]]) -> dict[str, str]:
    dates = list(prices_by_date.keys())
    return {dates[index]: dates[index - 1] for index in range(1, len(dates))}


def _entry_gap_for_position(
    position: dict[str, Any],
    prices_by_date: OrderedDict[str, dict[str, Any]],
    prev_by_date: dict[str, str],
) -> tuple[float | None, str | None, float | None]:
    entry_date = str(position.get("entry_date") or "")[:10]
    ticker = str(position.get("ticker") or "").upper()
    prev_date = prev_by_date.get(entry_date)
    prev_close = None
    if prev_date:
        prev_close = (prices_by_date.get(prev_date) or {}).get("close", {}).get(ticker)
    entry_price = position.get("entry_price")
    if not prev_close or not entry_price:
        return None, prev_date, prev_close
    return float(entry_price) / float(prev_close) - 1.0, prev_date, float(prev_close)


def _entry_gap_scalar(
    position: dict[str, Any],
    prices_by_date: OrderedDict[str, dict[str, Any]],
    prev_by_date: dict[str, str],
    scalar: float,
) -> float:
    gap, _, _ = _entry_gap_for_position(position, prices_by_date, prev_by_date)
    if gap is not None and gap >= ENTRY_GAP_FLOOR:
        return float(scalar)
    return 1.0


def _pnl_for_position(
    position: dict[str, Any],
    *,
    prices_by_date: OrderedDict[str, dict[str, Any]],
    prev_by_date: dict[str, str],
    entry_gap_scalar: float,
    closed: bool,
) -> float:
    scalar = _entry_gap_scalar(position, prices_by_date, prev_by_date, entry_gap_scalar)
    if closed:
        return float(position.get("pnl") or 0.0) * scalar
    return float(position.get("net_pnl_if_closed_now") or 0.0) * scalar


def _adjust_closed_position(
    position: dict[str, Any],
    *,
    prices_by_date: OrderedDict[str, dict[str, Any]],
    prev_by_date: dict[str, str],
    entry_gap_scalar: float,
) -> dict[str, Any]:
    adjusted = dict(position)
    gap, prev_date, prev_close = _entry_gap_for_position(position, prices_by_date, prev_by_date)
    scalar = _entry_gap_scalar(position, prices_by_date, prev_by_date, entry_gap_scalar)
    source_notional = float(position.get("notional") or 0.0)
    adjusted["entry_gap_vs_prior_close"] = _round(gap, 6)
    adjusted["entry_gap_prior_close_date"] = prev_date
    adjusted["entry_gap_prior_close"] = _round(prev_close, 4)
    adjusted["entry_gap_notional_scalar"] = scalar
    adjusted["entry_gap_bucket"] = "nonnegative" if scalar != 1.0 else "negative_or_missing"
    adjusted["source_notional"] = _round(source_notional, 2)
    adjusted["notional"] = _round(source_notional * scalar, 2)
    adjusted["pnl"] = _round(float(position.get("pnl") or 0.0) * scalar, 2)
    return adjusted


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    entry_gap_scalar: float,
) -> dict[str, Any]:
    prices_by_date = _load_snapshot_prices(window["snapshot"])
    prev_by_date = _window_prev_date_map(prices_by_date)
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
            "rule_version": "exp-20260512-012-replay",
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
            config={
                "max_positions": DEFAULT_MAX_POSITIONS,
                "event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
                "periodic_report_notional_scalar": DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            },
            persist=False,
        )
        skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
        state = _rebuild_sleeve_state(snapshot, skipped_entries)

        realized = sum(
            _pnl_for_position(
                item,
                prices_by_date=prices_by_date,
                prev_by_date=prev_by_date,
                entry_gap_scalar=entry_gap_scalar,
                closed=True,
            )
            for item in state.get("closed_positions") or []
        )
        unrealized = sum(
            _pnl_for_position(
                item,
                prices_by_date=prices_by_date,
                prev_by_date=prev_by_date,
                entry_gap_scalar=entry_gap_scalar,
                closed=False,
            )
            for item in state.get("open_positions") or []
        )
        pnl_by_date[as_of] = realized + unrealized
        open_positions = state.get("open_positions") or []
        max_open_positions = max(max_open_positions, len(open_positions))
        max_gross_notional = max(
            max_gross_notional,
            sum(
                float(item.get("notional") or 0.0)
                * _entry_gap_scalar(item, prices_by_date, prev_by_date, entry_gap_scalar)
                for item in open_positions
            ),
        )

    closed_positions = [
        _adjust_closed_position(
            item,
            prices_by_date=prices_by_date,
            prev_by_date=prev_by_date,
            entry_gap_scalar=entry_gap_scalar,
        )
        for item in state.get("closed_positions") or []
    ]
    wins = sum(1 for item in closed_positions if float(item.get("pnl") or 0.0) > 0)
    entry_gap_closed = [
        item
        for item in closed_positions
        if item.get("entry_gap_bucket") == "nonnegative"
    ]

    sleeve_curve = [
        (date_value, 100_000.0 + pnl) for date_value, pnl in pnl_by_date.items()
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
            "entry_gap_nonnegative_closed_trade_count": len(entry_gap_closed),
            "entry_gap_nonnegative_total_pnl": _round(
                sum(float(item.get("pnl") or 0.0) for item in entry_gap_closed),
                2,
            ),
        }
    )
    return {
        "daily_pnl": list(pnl_by_date.items()),
        "metrics": standalone_metrics,
        "sample_closed_positions": closed_positions[:10],
    }


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    entry_gap_scalar: float,
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            entry_gap_scalar=entry_gap_scalar,
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
            "sample_closed_positions": sleeve["sample_closed_positions"],
        }
    return {"by_window": by_window, "aggregate": _aggregate(by_window)}


def _window_checks(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    checks = {}
    for label in WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        sleeve_m = after["by_window"][label]["sleeve_metrics"]
        checks[label] = {
            "ev_delta": _round(
                after_m["expected_value_score"] - before_m["expected_value_score"],
                6,
            ),
            "pnl_delta": _round(after_m["total_pnl"] - before_m["total_pnl"], 2),
            "max_drawdown_delta": _round(
                after_m["max_drawdown_pct"] - before_m["max_drawdown_pct"],
                6,
            ),
            "entry_gap_nonnegative_closed_trade_count": sleeve_m[
                "entry_gap_nonnegative_closed_trade_count"
            ],
            "entry_gap_nonnegative_total_pnl": sleeve_m[
                "entry_gap_nonnegative_total_pnl"
            ],
        }
    return checks


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, after_value in after["aggregate"].items():
        before_value = before["aggregate"].get(key)
        if isinstance(after_value, (int, float)) and isinstance(
            before_value, (int, float)
        ):
            delta = after_value - before_value
            out[f"{key}_delta"] = _round(delta, 2 if "pnl" in key else 6)
            out[f"{key}_delta_pct"] = _round(
                delta / before_value if before_value else None,
                6,
            )
    return out


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(after, before)
    checks = _window_checks(after, before)
    ev_positive_windows = sum(1 for row in checks.values() if row["ev_delta"] > 0)
    pnl_positive_windows = sum(1 for row in checks.values() if row["pnl_delta"] > 0)
    ev_regressed_windows = sum(1 for row in checks.values() if row["ev_delta"] < 0)
    max_drawdown_delta = max(row["max_drawdown_delta"] for row in checks.values())
    entry_gap_closed = sum(
        row["entry_gap_nonnegative_closed_trade_count"] for row in checks.values()
    )
    passed = (
        aggregate_delta.get("expected_value_score_sum_delta", 0) > 0
        and aggregate_delta.get("sleeve_total_pnl_sum_delta", 0) > 0
        and ev_positive_windows == 3
        and pnl_positive_windows == 3
        and ev_regressed_windows == 0
        and max_drawdown_delta <= MAX_DRAWDOWN_WORSENING
        and after["aggregate"]["sleeve_closed_trade_count_sum"]
        >= MIN_PROMOTION_CLOSED_TRADES
        and entry_gap_closed >= MIN_ENTRY_GAP_BUCKET_CLOSED_TRADES
    )
    return {
        "passed": passed,
        "rule": (
            "Pass if aggregate EV and sleeve PnL improve, EV and PnL improve "
            "in all three windows, max drawdown worsens by no more than 0.5 "
            "percentage points in any window, the sleeve keeps at least 40 "
            "closed trades, and the nonnegative entry-gap bucket has at least "
            "20 closed trades."
        ),
        "aggregate_delta": aggregate_delta,
        "window_checks": checks,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "pnl_positive_windows": pnl_positive_windows,
        "max_drawdown_delta_max": max_drawdown_delta,
        "sleeve_closed_trade_count_after": after["aggregate"][
            "sleeve_closed_trade_count_sum"
        ],
        "entry_gap_nonnegative_closed_trade_count_after": entry_gap_closed,
    }


def _variant_name(scalar: float) -> str:
    return f"entry_gap_nonnegative_scalar_{scalar:.2f}"


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC financial-report entry-gap notional",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Sleeve trades | Gap bucket trades | Max DD d |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    best = payload["variants"][payload["best_variant"]]
    before = payload["before_variant"]
    for label in WINDOWS:
        before_m = before["by_window"][label]["combined_metrics"]
        after_m = best["by_window"][label]["combined_metrics"]
        check = best["gate"]["window_checks"][label]
        sleeve = best["by_window"][label]["sleeve_metrics"]
        lines.append(
            "| {label} | {bev:.6f} | {aev:.6f} | {dev:+.6f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | {gap_trades} | {dd:+.4%} |".format(
                label=label,
                bev=before_m["expected_value_score"],
                aev=after_m["expected_value_score"],
                dev=check["ev_delta"],
                bpnl=before_m["total_pnl"],
                apnl=after_m["total_pnl"],
                dpnl=check["pnl_delta"],
                trades=sleeve["closed_trade_count"],
                gap_trades=check["entry_gap_nonnegative_closed_trade_count"],
                dd=check["max_drawdown_delta"],
            )
        )
    gate = best["gate"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Best scalar: `{best['entry_gap_nonnegative_notional_scalar']:.2f}`",
            "- EV delta: `{:+.6f}`".format(
                gate["aggregate_delta"]["expected_value_score_sum_delta"]
            ),
            "- Total PnL delta: `${:+,.2f}`".format(
                gate["aggregate_delta"]["total_pnl_sum_delta"]
            ),
            "- Sleeve PnL delta: `${:+,.2f}`".format(
                gate["aggregate_delta"]["sleeve_total_pnl_sum_delta"]
            ),
            f"- Gate passed: `{gate['passed']}`",
            "",
            "## Protocol Answers",
            "",
            json.dumps(payload["protocol_answers"], indent=2, sort_keys=True),
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "",
        ]
    )
    return "\n".join(lines)


def _core_results() -> dict[str, dict[str, Any]]:
    out = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        out[label] = {
            "result": result,
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }
    return out


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    raw_exp100 = _load_exp100()
    exp100 = _filter_current_queue(raw_exp100)
    core_results = _core_results()
    before = _run_variant(
        core_results=core_results,
        exp100=exp100,
        entry_gap_scalar=BASELINE_ENTRY_GAP_SCALAR,
    )
    variants: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for scalar in ENTRY_GAP_SCALAR_VARIANTS:
        name = _variant_name(scalar)
        row = _run_variant(
            core_results=core_results,
            exp100=exp100,
            entry_gap_scalar=scalar,
        )
        row["entry_gap_nonnegative_notional_scalar"] = scalar
        row["gate"] = _gate(row, before)
        variants[name] = row

    passing = [name for name, row in variants.items() if row["gate"]["passed"]]
    if passing:
        best_name = max(
            passing,
            key=lambda name: variants[name]["aggregate"]["expected_value_score_sum"],
        )
    else:
        best_name = max(
            variants,
            key=lambda name: variants[name]["aggregate"]["expected_value_score_sum"],
        )
    best = variants[best_name]
    decision = (
        "accepted_default_off_entry_gap_nonnegative_notional_"
        f"{best['entry_gap_nonnegative_notional_scalar']:.2f}x"
        if best["gate"]["passed"]
        else "rejected_entry_gap_nonnegative_notional_scalar"
    )
    interpretation = (
        "Nonnegative T+2 entry gaps improved the accepted SEC financial-report "
        "paper sleeve under the three-window gate. Promotion should stay "
        "default-off and shared because the surface still emits no live orders."
        if best["gate"]["passed"]
        else (
            "A nonnegative T+2 entry gap did not identify a robust enough "
            "allocation edge on top of the accepted SEC financial-report paper "
            "sleeve. Keep the accepted capacity, T+1 floor, base notional, "
            "periodic scalar, and 10-day hold unchanged."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "accepted" if best["gate"]["passed"] else "rejected",
        "decision": decision,
        "changed_variable": "sec_financial_report_entry_gap_nonnegative_notional_scalar",
        "change_type": "alpha_search_execution_quality_risk_allocation",
        "single_causal_variable": (
            "paper-notional scalar for SEC financial-report T+1 entries whose "
            "T+2 open is nonnegative versus the prior trading day's close"
        ),
        "hypothesis": (
            "Inside the accepted SEC financial-report T+1 paper sleeve, a "
            "nonnegative T+2 opening gap versus prior close is an execution-time "
            "confirmation that the positive filing reaction has not faded; those "
            "paper entries may deserve a modest higher notional without changing "
            "queue eligibility, ranking, capacity, hold days, or live orders."
        ),
        "parameters": {
            "base_event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
            "periodic_report_notional_scalar": DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
            "max_positions": DEFAULT_MAX_POSITIONS,
            "min_t1_excess_return_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
            "entry_gap_floor_vs_prior_close": ENTRY_GAP_FLOOR,
            "baseline_entry_gap_nonnegative_notional_scalar": BASELINE_ENTRY_GAP_SCALAR,
            "tested_entry_gap_nonnegative_notional_scalars": list(
                ENTRY_GAP_SCALAR_VARIANTS
            ),
            "source_candidate_artifact": (
                "data\\experiments\\exp-20260511-100\\"
                "exp_20260511_100_sec_financial_report_positive_t1_forward_outcome_refresh.json"
            ),
        },
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
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production paper-sleeve replay over the same OHLCV snapshots. "
            "Core replay uses REPLAY_PARTIAL_REDUCES and REGIME_AWARE_EXIT."
        ),
        "candidate_counts_after_current_queue_filter": {
            label: len(window.get("candidate_rows") or [])
            for label, window in exp100.get("windows", {}).items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": best["aggregate"],
        "delta_metrics": {
            "aggregate": best["gate"]["aggregate_delta"],
            "by_window": best["gate"]["window_checks"],
        },
        "expected_value_score_delta": best["gate"]["aggregate_delta"][
            "expected_value_score_sum_delta"
        ],
        "total_pnl_delta": best["gate"]["aggregate_delta"]["total_pnl_sum_delta"],
        "best_variant": best_name,
        "before_variant": before,
        "variants": variants,
        "gate": best["gate"],
        "gate4": {
            "passed": best["gate"]["passed"],
            "rule": best["gate"]["rule"],
        },
        "interpretation": interpretation,
        "rejection_reason": (
            "" if best["gate"]["passed"] else "No nonnegative entry-gap notional scalar cleared the three-window gate."
        ),
        "next_evidence_needed": (
            "Promote only as shared default-off paper-sleeve metadata/helper, "
            "then collect forward replacement-value evidence before any live-order scope."
            if best["gate"]["passed"]
            else (
                "Forward replacement-value evidence or a genuinely new execution-quality "
                "field before retrying SEC entry-gap allocation."
            )
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": True,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "risk allocation: scale paper notional only for accepted SEC "
                "financial-report T+1 sleeve entries whose T+2 open is nonnegative "
                "versus prior close."
            ),
            "2_history_check": (
                "exp-20260512-001 accepted the T+1 excess floor; exp-20260512-006 "
                "accepted global $15k notional; exp-20260512-007 accepted periodic-report "
                "family notional; exp-20260512-009 rejected queue-rank notional; "
                "exp-20260512-011 rejected clean earnings 8-K notional. No logged SEC "
                "financial-report run isolated T+2 fill-gap confirmation."
            ),
            "3_single_causal_variable": "nonnegative T+2 entry-gap paper-notional scalar only",
            "4_acceptance_standard": (
                "Three fixed windows, aggregate EV and sleeve PnL improve, EV/PnL "
                "improve in all three windows, max drawdown drift <=0.5pp, at least "
                "40 closed sleeve trades, and at least 20 closed nonnegative-gap trades."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260512_012_sec_financial_report_entry_gap_notional.py"
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking and filing-shock fields remain data-limited. Nearby "
            "SEC floors, hold periods, form exclusions, global notional, periodic "
            "scalar, queue-rank notional, and clean earnings 8-K notional variants "
            "are already logged, so this run changes only execution-time entry-gap "
            "risk allocation."
        ),
    }
    return payload


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
        "next_evidence_needed": payload["next_evidence_needed"],
    }
    _write_json(DOC_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)
    print(json.dumps(_safe(ticket), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
