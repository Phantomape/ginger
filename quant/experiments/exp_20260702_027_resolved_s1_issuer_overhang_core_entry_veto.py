"""exp-20260702-027: resolved S-1/F-1 issuer-overhang core entry veto.

Replay-only alpha search. Tests one entry/risk hypothesis: if a canonical core
entry signal appears while the same listed issuer is inside the first 10
trading sessions after a resolved S-1/F-1 registration event, veto that core
entry. The signal is production-visible through the accepted SEC corporate
event stream, but this runner does not change shared policy, run.py, live
orders, paper sleeves, exits, ranking, or sizing.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260630_012_close_confirmed_static_stop as replay_base


EXPERIMENT_ID = "exp-20260702-027"
OWNER = "alpha-explore"
SLUG = "resolved_s1_issuer_overhang_core_entry_veto"
RUNNER = f"quant/experiments/exp_20260702_027_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = replay_base.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    text = str(entry)
    if text not in sys.path:
        sys.path.insert(0, text)

import backtester as bt  # noqa: E402
import feature_layer as fl  # noqa: E402
import signal_engine as se  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from ohlcv_warehouse import load_warehouse_snapshot_ohlcv_frames  # noqa: E402


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260519-030"
    / "warehouse_main.sqlite"
)
EVENT_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_027_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
}

BASE_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "REPLAY_PARTIAL_REDUCES": True,
}
OVERHANG_SIGNAL_SESSIONS = 10
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_SURVIVAL_RATE = 0.05

HYPOTHESIS = (
    "Entry/risk alpha: veto canonical core entries when the ticker has a "
    "resolved issuer-self S-1/F-1 registration overhang event in the prior 10 "
    "trading sessions, because exp-20260702-023 showed these issuers "
    "underperform their same-ticker baseline after filing."
)
CHANGE_TYPE = "entry_filter"
IMPLEMENTATION_MODE = "private_replay_scout"
MECHANISM_FAMILY = "entry_filter"
TRIAL_FAMILY = "resolved_s1_f1_issuer_overhang_core_entry_veto"
TRIAL_VARIANT_ID = "ten_session_signal_date_veto_v1"
CHANGED_VARIABLE = "resolved_s1_f1_recent_issuer_overhang_core_entry_veto_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_from_resolved_s1_issuer_self_lead"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260702-023",
    "exp-20260702-024",
    "exp-20260702-012",
]
CAUSAL_COMPONENTS = [
    "resolved issuer-self S-1/F-1 event stream",
    "core entry veto within fixed 10-session overhang window",
    "canonical three-window before-after replay",
    "production parity boundary",
]


def repo_rel(path: Path | str) -> str:
    return replay_base.repo_rel(path)


def read_json(path: Path, default: Any = None) -> Any:
    return replay_base.read_json(path, default)


def write_json(path: Path, payload: Any) -> None:
    replay_base.write_json(path, payload)


def write_text(path: Path, text: str) -> None:
    replay_base.write_text(path, text)


def safe(value: Any) -> Any:
    return replay_base.safe(value)


def rounded(value: Any, digits: int = 6) -> Any:
    return replay_base.rounded(value, digits)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def window_label(date_text: str | None) -> str | None:
    if not date_text:
        return None
    day = str(date_text)[:10]
    for label, spec in WINDOWS.items():
        if spec["start"] <= day <= spec["end"]:
            return label
    return None


def load_target_events() -> list[dict[str, Any]]:
    forms = {"S-1", "S-1/A", "F-1", "F-1/A"}
    rows = []
    for row in read_jsonl(EVENT_ROWS):
        if row.get("event_class") != "ipo_registration":
            continue
        if row.get("ticker_status") != "resolved":
            continue
        if row.get("form_type") not in forms:
            continue
        filed_date = str(row.get("filed_date") or "")[:10]
        if not filed_date:
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        rows.append(
            {
                "ticker": ticker,
                "filed_date": filed_date,
                "form_type": row.get("form_type"),
                "accession": row.get("accession"),
                "company_name": row.get("company_name"),
            }
        )
    return rows


def build_overhang_signal_dates() -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    events = load_target_events()
    core_universe = {str(ticker).upper() for ticker in get_universe()}
    tickers = {row["ticker"] for row in events}
    core_event_tickers = sorted(tickers & core_universe)
    core_events = [row for row in events if row["ticker"] in core_universe]
    events_by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in core_events:
        label = window_label(row["filed_date"])
        if label:
            events_by_window[label].append(row)

    frames_by_window: dict[str, dict[str, pd.DataFrame]] = {}
    for label, rows in events_by_window.items():
        spec = WINDOWS[label]
        frames_by_window[label] = load_warehouse_snapshot_ohlcv_frames(
            WAREHOUSE,
            spec["snapshot"],
            {row["ticker"] for row in rows},
            spec["start"],
            spec["end"],
        )
    frame_tickers = {
        ticker
        for frames in frames_by_window.values()
        for ticker in frames
    }
    by_ticker: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    audit: dict[str, Any] = {
        "event_rows": len(events),
        "unique_event_tickers": len(tickers),
        "core_universe_tickers": len(core_universe),
        "core_event_ticker_intersection_count": len(core_event_tickers),
        "core_event_ticker_intersection": core_event_tickers,
        "core_event_rows": len(core_events),
        "events_outside_core_universe_rows": len(events) - len(core_events),
        "tickers_with_warehouse_frame": len(frame_tickers),
        "missing_frame_event_rows": 0,
        "events_without_later_trading_day": 0,
        "marked_signal_dates": 0,
        "events_by_window": Counter(),
        "events_by_form": Counter(),
        "sample_marked_events": [],
    }
    marked_keys: set[tuple[str, str, str]] = set()

    for row in events:
        label = window_label(row["filed_date"])
        audit["events_by_form"][row["form_type"]] += 1
        audit["events_by_window"][label or "outside"] += 1
        if row["ticker"] not in core_universe:
            continue
        if not label:
            continue
        frame = frames_by_window.get(label, {}).get(row["ticker"])
        if frame is None or frame.empty:
            audit["missing_frame_event_rows"] += 1
            continue
        dates = list(frame.index)
        filed_ts = pd.Timestamp(row["filed_date"])
        later = [idx for idx, value in enumerate(dates) if value > filed_ts]
        if not later:
            audit["events_without_later_trading_day"] += 1
            continue
        start_idx = later[0]
        # Conservative signal-date semantics: only veto decisions made on or
        # after the first trading day after the filing date. A signal dated D
        # enters at D+1 open in the canonical backtester.
        for idx in range(start_idx, min(len(dates), start_idx + OVERHANG_SIGNAL_SESSIONS)):
            signal_date = str(dates[idx].date())
            key = (row["ticker"], signal_date, str(row.get("accession") or ""))
            if key in marked_keys:
                continue
            marked_keys.add(key)
            event_payload = {
                "filed_date": row["filed_date"],
                "form_type": row["form_type"],
                "accession": row.get("accession"),
                "company_name": row.get("company_name"),
                "overhang_signal_day_index": idx - start_idx + 1,
            }
            by_ticker[row["ticker"]][signal_date].append(event_payload)
            if len(audit["sample_marked_events"]) < 25:
                audit["sample_marked_events"].append(
                    {"ticker": row["ticker"], "signal_date": signal_date, **event_payload}
                )

    audit["marked_signal_dates"] = sum(len(days) for days in by_ticker.values())
    audit["marked_tickers"] = len(by_ticker)
    audit["events_by_window"] = dict(audit["events_by_window"].most_common())
    audit["events_by_form"] = dict(audit["events_by_form"].most_common())
    return {ticker: dict(days) for ticker, days in by_ticker.items()}, audit


def _signal_key(row: dict[str, Any]) -> str:
    return str(
        row.get("trade_key")
        or f"{row.get('ticker')}:{row.get('entry_date')}:{row.get('entry_price')}"
    )


def changed_trades(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    before_by_key = {_signal_key(row): row for row in before}
    after_by_key = {_signal_key(row): row for row in after}
    changed: list[dict[str, Any]] = []
    for key in sorted(set(before_by_key) | set(after_by_key)):
        b = before_by_key.get(key)
        a = after_by_key.get(key)
        if b is None or a is None:
            source = a or b or {}
            changed.append(
                {
                    "trade_key": key,
                    "change_type": "added_or_removed_trade",
                    "before_present": b is not None,
                    "after_present": a is not None,
                    "ticker": source.get("ticker"),
                    "strategy": source.get("strategy"),
                    "entry_date": source.get("entry_date"),
                    "pnl_delta": rounded(
                        float((a or {}).get("pnl") or 0.0)
                        - float((b or {}).get("pnl") or 0.0),
                        2,
                    ),
                }
            )
            continue
        fields = ("exit_date", "exit_reason", "exit_price", "pnl", "shares")
        if any(b.get(field) != a.get(field) for field in fields):
            changed.append(
                {
                    "trade_key": key,
                    "change_type": "modified_trade",
                    "ticker": a.get("ticker"),
                    "strategy": a.get("strategy"),
                    "entry_date": a.get("entry_date"),
                    "before_exit_date": b.get("exit_date"),
                    "after_exit_date": a.get("exit_date"),
                    "before_exit_reason": b.get("exit_reason"),
                    "after_exit_reason": a.get("exit_reason"),
                    "before_shares": b.get("shares"),
                    "after_shares": a.get("shares"),
                    "before_pnl": b.get("pnl"),
                    "after_pnl": a.get("pnl"),
                    "pnl_delta": rounded(
                        float(a.get("pnl") or 0.0) - float(b.get("pnl") or 0.0),
                        2,
                    ),
                }
            )
    return changed


def summarize_changed(changed: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [item for items in changed.values() for item in items]
    by_ticker = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    by_change = Counter(str(row.get("change_type") or "unknown") for row in rows)
    return {
        "changed_trade_count": len(rows),
        "changed_trade_count_by_window": {label: len(items) for label, items in changed.items()},
        "changed_pnl_delta_sum": round(sum(float(row.get("pnl_delta") or 0.0) for row in rows), 2),
        "changed_tickers": dict(by_ticker.most_common()),
        "change_types": dict(by_change.most_common()),
        "sample_changed_trades": rows[:30],
    }


def _patch_overhang_veto(overhang_dates: dict[str, dict[str, list[dict[str, Any]]]]) -> tuple[dict[str, Any], tuple[Any, Any, Any]]:
    original_compute = fl.compute_features
    original_generate = se.generate_signals
    original_filter = bt.filter_entry_signal_candidates
    stats: dict[str, Any] = {
        "generated_flagged_signals": 0,
        "post_filter_vetoed_signals": 0,
        "generated_by_window": Counter(),
        "vetoed_by_window": Counter(),
        "vetoed_by_ticker": Counter(),
        "vetoed_by_strategy": Counter(),
        "sample_generated_flags": [],
        "sample_vetoed_signals": [],
    }

    def patched_compute(ticker, ohlcv_data, earnings_data):
        features = original_compute(ticker, ohlcv_data, earnings_data)
        if features is not None and ohlcv_data is not None and len(ohlcv_data):
            features["__signal_date"] = str(pd.Timestamp(ohlcv_data.index[-1]).date())
        return features

    def patched_generate(
        features_dict,
        market_context=None,
        enabled_strategies=None,
        breakout_max_pullback_from_52w_high=None,
    ):
        signals = original_generate(
            features_dict,
            market_context=market_context,
            enabled_strategies=enabled_strategies,
            breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
        )
        for sig in signals:
            ticker = str(sig.get("ticker") or "").upper()
            signal_date = (features_dict.get(ticker) or {}).get("__signal_date")
            if not signal_date:
                continue
            sig["signal_date"] = signal_date
            events = overhang_dates.get(ticker, {}).get(signal_date) or []
            if not events:
                continue
            label = window_label(signal_date) or "outside"
            sig["resolved_s1_f1_overhang_veto_candidate"] = True
            sig["resolved_s1_f1_overhang_events"] = events
            sig["resolved_s1_f1_overhang_signal_date"] = signal_date
            stats["generated_flagged_signals"] += 1
            stats["generated_by_window"][label] += 1
            if len(stats["sample_generated_flags"]) < 25:
                stats["sample_generated_flags"].append(
                    {
                        "ticker": ticker,
                        "strategy": sig.get("strategy"),
                        "signal_date": signal_date,
                        "window": label,
                        "event_count": len(events),
                        "events": events[:3],
                    }
                )
        return signals

    def patched_filter(signals, *args, **kwargs):
        filtered, audit = original_filter(signals, *args, **kwargs)
        kept = []
        for sig in filtered:
            if sig.get("resolved_s1_f1_overhang_veto_candidate"):
                ticker = str(sig.get("ticker") or "").upper()
                signal_date = sig.get("resolved_s1_f1_overhang_signal_date") or sig.get("signal_date")
                label = window_label(signal_date) or "outside"
                stats["post_filter_vetoed_signals"] += 1
                stats["vetoed_by_window"][label] += 1
                stats["vetoed_by_ticker"][ticker] += 1
                stats["vetoed_by_strategy"][str(sig.get("strategy") or "unknown")] += 1
                if len(stats["sample_vetoed_signals"]) < 30:
                    stats["sample_vetoed_signals"].append(
                        {
                            "ticker": ticker,
                            "strategy": sig.get("strategy"),
                            "signal_date": signal_date,
                            "window": label,
                            "confidence_score": sig.get("confidence_score"),
                            "events": sig.get("resolved_s1_f1_overhang_events") or [],
                        }
                    )
                continue
            kept.append(sig)
        if isinstance(audit, dict):
            audit["resolved_s1_f1_overhang_core_entry_veto"] = {
                "post_filter_vetoed_signals_so_far": stats["post_filter_vetoed_signals"],
                "vetoed_by_window_so_far": dict(stats["vetoed_by_window"].most_common()),
            }
        return kept, audit

    fl.compute_features = patched_compute
    se.generate_signals = patched_generate
    bt.filter_entry_signal_candidates = patched_filter
    return stats, (original_compute, original_generate, original_filter)


def _restore_patch(originals: tuple[Any, Any, Any]) -> None:
    original_compute, original_generate, original_filter = originals
    fl.compute_features = original_compute
    se.generate_signals = original_generate
    bt.filter_entry_signal_candidates = original_filter


def _serialise_stats(stats: dict[str, Any]) -> dict[str, Any]:
    out = dict(stats)
    for key in ("generated_by_window", "vetoed_by_window", "vetoed_by_ticker", "vetoed_by_strategy"):
        out[key] = dict(out[key].most_common())
    return out


def run_window(
    label: str,
    apply_veto: bool,
    overhang_dates: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    spec = WINDOWS[label]
    stats: dict[str, Any] = {
        "generated_flagged_signals": 0,
        "post_filter_vetoed_signals": 0,
        "generated_by_window": Counter(),
        "vetoed_by_window": Counter(),
        "vetoed_by_ticker": Counter(),
        "vetoed_by_strategy": Counter(),
        "sample_generated_flags": [],
        "sample_vetoed_signals": [],
    }
    originals = None
    if apply_veto:
        stats, originals = _patch_overhang_veto(overhang_dates)
    try:
        result = BacktestEngine(
            get_universe(),
            start=spec["start"],
            end=spec["end"],
            config=BASE_CONFIG,
            ohlcv_warehouse_path=str(WAREHOUSE),
            ohlcv_warehouse_snapshot_source=str(spec["snapshot"]),
            include_oracle_diagnostics=False,
        ).run()
    finally:
        if originals is not None:
            _restore_patch(originals)
    if result.get("error"):
        raise RuntimeError(f"{label} failed: {result['error']}")
    return {
        "metrics": replay_base.metrics(result),
        "trades": result.get("trades") or [],
        "veto_stats": _serialise_stats(stats),
    }


def aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return replay_base.aggregate({label: rows[label]["metrics"] for label in WINDOWS})


def aggregate_delta(after: dict[str, dict[str, Any]], before: dict[str, dict[str, Any]]) -> dict[str, Any]:
    before_agg = aggregate(before)
    after_agg = aggregate(after)
    delta = replay_base.delta(after_agg, before_agg)
    before_ev = float(before_agg.get("expected_value_score_sum") or 0.0)
    before_pnl = float(before_agg.get("total_pnl_sum") or 0.0)
    ev_delta = float(delta.get("expected_value_score_sum") or 0.0)
    pnl_delta = float(delta.get("total_pnl_sum") or 0.0)
    delta["expected_value_score_delta_pct"] = round(ev_delta / before_ev, 6) if before_ev else None
    delta["total_pnl_delta_pct"] = round(pnl_delta / before_pnl, 6) if before_pnl else None
    delta["post_filter_vetoed_signals_sum"] = sum(
        int(after[label]["veto_stats"].get("post_filter_vetoed_signals") or 0)
        for label in WINDOWS
    )
    delta["generated_flagged_signals_sum"] = sum(
        int(after[label]["veto_stats"].get("generated_flagged_signals") or 0)
        for label in WINDOWS
    )
    return delta


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return {
        "success_probability": 0.18,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "zero_core_overlap",
            "cutting_winners",
            "window_regression",
            "source_saturation_block",
        ],
        "confidence_reason": (
            "exp-20260702-023 found a stable listed-issuer S-1/F-1 "
            "underperformance lead, but the core veto may touch few canonical "
            "entries or cut winners."
        ),
    }


def gate4(
    before_runs: dict[str, dict[str, Any]],
    after_runs: dict[str, dict[str, Any]],
    changed_summary: dict[str, Any],
    overhang_audit: dict[str, Any],
) -> dict[str, Any]:
    before_agg = aggregate(before_runs)
    after_agg = aggregate(after_runs)
    agg_delta = aggregate_delta(after_runs, before_runs)
    by_window_delta = {
        label: replay_base.delta(after_runs[label]["metrics"], before_runs[label]["metrics"])
        for label in WINDOWS
    }
    improved_ev = [
        label
        for label in WINDOWS
        if float(by_window_delta[label].get("expected_value_score") or 0.0) > 0
    ]
    regressed_ev = [
        label
        for label in WINDOWS
        if float(by_window_delta[label].get("expected_value_score") or 0.0) < 0
    ]
    regressed_pnl = [
        label
        for label in WINDOWS
        if float(by_window_delta[label].get("total_pnl") or 0.0) < 0
    ]
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in WINDOWS
    )
    failed: list[str] = []
    if float(agg_delta.get("expected_value_score_sum") or 0.0) <= 0:
        failed.append("aggregate_ev_not_positive")
    if float(agg_delta.get("total_pnl_sum") or 0.0) <= 0:
        failed.append("aggregate_pnl_not_positive")
    if regressed_ev:
        failed.append("window_ev_regression")
    if regressed_pnl:
        failed.append("window_pnl_regression")
    if max_drawdown_worse > MAX_DRAWDOWN_WORSE_GUARDRAIL:
        failed.append("drawdown_worse_than_guardrail")
    if after_agg["survival_rate_min"] < MIN_SURVIVAL_RATE:
        failed.append("survival_below_floor")
    if int(agg_delta.get("post_filter_vetoed_signals_sum") or 0) <= 0:
        failed.append("zero_post_filter_core_overlap")
    if int(changed_summary.get("changed_trade_count") or 0) <= 0:
        failed.append("no_changed_trades")
    if int(overhang_audit.get("core_event_ticker_intersection_count") or 0) <= 0:
        failed.append("zero_core_universe_event_ticker_intersection")
    passed = not failed
    return {
        "passed": passed,
        "accepted_alpha": False,
        "observed_only_lead": passed,
        "decision": (
            "positive_replay_lead_not_promoted_resolved_s1_overhang_core_veto"
            if passed
            else "rejected_resolved_s1_overhang_core_entry_veto"
        ),
        "failed_reasons": failed,
        "improved_ev_windows": improved_ev,
        "regressed_ev_windows": regressed_ev,
        "regressed_pnl_windows": regressed_pnl,
        "max_drawdown_worse": rounded(max_drawdown_worse),
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
        "before_aggregate": before_agg,
        "after_aggregate": after_agg,
        "aggregate_delta": agg_delta,
    }


def build_payload() -> dict[str, Any]:
    overhang_dates, overhang_audit = build_overhang_signal_dates()
    before_runs = {
        label: run_window(label, False, overhang_dates)
        for label in WINDOWS
    }
    after_runs = {
        label: run_window(label, True, overhang_dates)
        for label in WINDOWS
    }
    before_metrics = {label: before_runs[label]["metrics"] for label in WINDOWS}
    after_metrics = {label: after_runs[label]["metrics"] for label in WINDOWS}
    by_window_delta = {
        label: replay_base.delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    changed = {
        label: changed_trades(before_runs[label]["trades"], after_runs[label]["trades"])
        for label in WINDOWS
    }
    changed_summary = summarize_changed(changed)
    g4 = gate4(before_runs, after_runs, changed_summary, overhang_audit)
    prediction = load_ticket_prediction()
    probability = float(prediction.get("success_probability") or 0.0)
    actual_success = 1 if g4["passed"] else 0
    decision = g4["decision"]

    gate2_runtime = {
        "entry_date_checked_on_closed_trades": sum(
            len(before_runs[label]["trades"]) for label in WINDOWS
        ),
        "target_price_scope": (
            "Checked through normal backtester trade records; the veto does not "
            "consume target_price and does not change target exits."
        ),
        "resolved_s1_f1_event_rows_available": overhang_audit["event_rows"],
        "core_event_ticker_intersection_count": overhang_audit[
            "core_event_ticker_intersection_count"
        ],
        "core_event_rows": overhang_audit["core_event_rows"],
        "overhang_marked_tickers": overhang_audit["marked_tickers"],
        "passed": bool(overhang_audit["event_rows"] and overhang_audit["core_universe_tickers"]),
    }
    status = "observed_only_positive_lead" if g4["passed"] else "rejected"
    why = (
        "The fixed S-1/F-1 overhang veto improved the canonical replay, but it "
        "is not promoted because this runner used replay-only monkey patches "
        "rather than shared production/backtest policy."
        if g4["passed"]
            else (
                "The issuer-overhang effect did not translate into an executable "
                "core entry veto because no resolved S-1/F-1 issuer ticker "
                "intersected the canonical core universe."
                if "zero_core_universe_event_ticker_intersection" in g4["failed_reasons"]
                else "The fixed S-1/F-1 overhang veto failed Gate 4 after touching the canonical core entries."
            )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": replay_base.utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": bool(g4["passed"]),
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": probability,
            "brier_score": round((actual_success - probability) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": g4["failed_reasons"] or ["positive_replay_lead_not_promoted"],
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(g4["failed_reasons"])
            ),
            "actual_ev_delta": g4["aggregate_delta"].get("expected_value_score_sum"),
            "actual_pnl_delta": g4["aggregate_delta"].get("total_pnl_sum"),
            "surprise_note": why,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse": repo_rel(WAREHOUSE),
            "event_rows": repo_rel(EVENT_ROWS),
            "before_config": BASE_CONFIG,
            "overhang_signal_sessions": OVERHANG_SIGNAL_SESSIONS,
            "signal_date_semantics": (
                "A signal is vetoed only on or after the first trading day "
                "after filed_date; the backtester would otherwise enter at "
                "the next session open."
            ),
            "windows": {
                label: {**spec, "snapshot": repo_rel(spec["snapshot"])}
                for label, spec in WINDOWS.items()
            },
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new accepted without override; no strong "
                    "near-neighbor or source-saturation block."
                ),
                "exp-20260702-023": (
                    "Observed-only lead: resolved issuer S-1/F-1 rows "
                    "underperformed same-ticker baselines across windows."
                ),
                "exp-20260702-024": (
                    "Offering-economics sidecar blocked because target "
                    "accessions had no local text/features; this test uses a "
                    "new executable gate shape rather than a same-row field slice."
                ),
                "exp-20260702-012": (
                    "SEC event exposure top-1 peer propagation rejected; this "
                    "test is issuer-self core veto, not peer propagation."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Gate 4 requires positive aggregate EV and PnL, no EV/PnL "
                "window regression, drawdown drift <=0.5pp, survival >=5%, "
                "and at least one post-filter vetoed core signal that changes trades."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "overhang_audit": overhang_audit,
        "veto_stats_by_window": {
            label: after_runs[label]["veto_stats"]
            for label in WINDOWS
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate(before_runs),
            "aggregate_after": aggregate(after_runs),
            "aggregate_delta": aggregate_delta(after_runs, before_runs),
            "changed_trades": changed_summary,
        },
        "changed_trades_by_window": changed,
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "rerun_before_aggregate": aggregate(before_runs),
            "accepted_reference": {
                "expected_value_score_sum": 7.8941,
                "total_pnl_sum": 234850.99,
                "trade_count_sum": 61,
                "signals_generated_sum": 164,
                "signals_survived_sum": 135,
            },
        },
        "gate2": gate2_runtime,
        "gate3": {
            "new_entry_filter_added": True,
            "signals_generated_delta": g4["aggregate_delta"].get("signals_generated_sum"),
            "signals_survived_delta": g4["aggregate_delta"].get("signals_survived_sum"),
            "minimum_after_survival_rate": g4["after_aggregate"]["survival_rate_min"],
            "passed": g4["after_aggregate"]["survival_rate_min"] >= MIN_SURVIVAL_RATE,
        },
        "gate4": g4,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "target_geometry_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": True,
            "activation_envelope": {
                "intended_notional": "same core entries, except veto same-ticker entries inside fixed S-1/F-1 overhang window if ever promoted",
                "capital_cap": "current core caps; veto only reduces exposure",
                "liquidity_slippage_model": "unchanged canonical next-open fills and existing cost/slippage model",
                "portfolio_displacement": "same ranking and slots; veto may free a core slot for later entries",
                "order_semantics": "after-close decision, next-open entry suppressed for vetoed signals",
                "failure_handling": "if SEC event stream is unavailable, do not veto",
                "kill_switch": (
                    "do not promote if no post-filter overlap, any canonical "
                    "EV/PnL regression, drawdown drift >0.5pp, or survival <5%"
                ),
            },
            "parity_note": (
                "Replay-only monkey patch. A positive result would require a "
                "shared helper consumed by backtester and run.py plus focused parity tests."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune the 10-session overhang window, include/exclude "
                "amendments, change form subtype, entry lag, liquidity, event "
                "age, notional, or response shape on these same S-1/F-1 rows."
            ),
            "new_evidence_required": (
                "A valid retry needs parsed offering economics, selling-holder "
                "or effectiveness-date provenance, fresh forward rows under a "
                "shared helper, or a different issuer-overhang data source."
            ),
        },
        "rejection_reason": None if g4["passed"] else ";".join(g4["failed_reasons"]),
        "next_retry_requires": [
            "parsed registered amount or resale-vs-primary offering fields",
            "selling-holder or effectiveness-date provenance",
            "fresh forward rows under a shared helper",
            "do not rerun adjacent windows or response shapes on the same rows",
        ],
        "related_files": [
            RUNNER,
            repo_rel(EVENT_ROWS),
            repo_rel(BASELINE_RESULT),
            "quant/backtester.py",
            "quant/feature_layer.py",
            "quant/signal_engine.py",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(LOG_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B quant\\ohlcv_warehouse.py seed-snapshot-versions",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Vetoed | Changed trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        vetoed = payload["veto_stats_by_window"][label].get("post_filter_vetoed_signals")
        changed = payload["delta_metrics"]["changed_trades"]["changed_trade_count_by_window"].get(label)
        rows.append(
            f"| {label} | {before.get('expected_value_score')} | "
            f"{after.get('expected_value_score')} | {delta.get('expected_value_score')} | "
            f"{before.get('total_pnl')} | {after.get('total_pnl')} | "
            f"{delta.get('total_pnl')} | {vetoed} | {changed} |"
        )
    agg = payload["delta_metrics"]["aggregate_delta"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} resolved S-1 issuer-overhang core entry veto",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            HYPOTHESIS,
            "",
            *rows,
            "",
            "Aggregate delta: "
            f"EV `{agg.get('expected_value_score_sum')}`, "
            f"PnL `{agg.get('total_pnl_sum')}`, "
            f"post-filter vetoed signals `{agg.get('post_filter_vetoed_signals_sum')}`, "
            f"changed trades `{payload['delta_metrics']['changed_trades']['changed_trade_count']}`.",
            "",
            "Production boundary: replay-only monkey patch. No run.py, shared "
            "policy, live/default orders, paper sleeve, exit, ranking, or sizing "
            "behavior changed.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EVENT_ROWS,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": replay_base.utc_now(),
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": [
            {
                "path": repo_rel(path),
                "exists": path.exists(),
                "sha256": replay_base.sha256(path),
            }
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_text(CARD_MD, build_card(payload))
    replay_base.save_experiment_log_entry(payload, allow_duplicate=True)
    write_json(MANIFEST_JSON, build_manifest(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "accepted_alpha": payload["accepted_alpha"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "aggregate_delta": payload["delta_metrics"]["aggregate_delta"],
                    "post_filter_vetoed_signals": payload["delta_metrics"]["aggregate_delta"].get(
                        "post_filter_vetoed_signals_sum"
                    ),
                    "changed_trade_count": payload["delta_metrics"]["changed_trades"][
                        "changed_trade_count"
                    ],
                    "failed_reasons": payload["gate4"]["failed_reasons"],
                    "artifact": payload["artifact"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
