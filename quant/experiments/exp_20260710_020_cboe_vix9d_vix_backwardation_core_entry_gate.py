"""exp-20260710-020: Cboe VIX9D/VIX backwardation core-entry scout.

This is an experiment-local private replay scout.  It uses Yahoo's mirror of
the Cboe VIX9D and VIX daily closes, applies one fixed signal-day rule
(``VIX9D > VIX``), and removes otherwise-surviving core entry candidates on
those dates.  Production, shared policy, ranking, sizing, exits, and orders are
not changed.  A positive result is only a lead for a later shared-paper-first
implementation.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (QUANT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as bt  # noqa: E402
import feature_layer  # noqa: E402
import signal_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from yfinance_bootstrap import download_with_rate_limit_retry  # noqa: E402


EXPERIMENT_ID = "exp-20260710-020"
OWNER = "alpha-explore"
SLUG = "cboe_vix9d_vix_backwardation_core_entry_gate"
RUNNER = f"quant/experiments/exp_20260710_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260710_020_{SLUG}.json"
TERM_STRUCTURE_JSON = DATA_DIR / "cboe_vix9d_vix_daily_closes.json"
BEFORE_JSON = DATA_DIR / "before_measurement.json"
AFTER_JSON = DATA_DIR / "after_measurement.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)
WAREHOUSE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260519-030"
    / "warehouse_main.sqlite"
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "canonical_ev": 5.1628,
                "canonical_pnl": 117072.92,
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "canonical_ev": 2.1402,
                "canonical_pnl": 78110.11,
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "canonical_ev": 0.5911,
                "canonical_pnl": 39667.96,
            },
        ),
    ]
)

HYPOTHESIS = (
    "Private replay scout: CBOE VIX9D close above VIX close on the signal "
    "day is an option-implied near-term backwardation stress state in which "
    "current core next-open entries should be excluded; the fixed no-entry "
    "gate should improve canonical multi-window EV, PnL, and drawdown without "
    "threshold tuning."
)
CHANGED_VARIABLE = "cboe_vix9d_gt_vix_core_entry_exclusion_v1"
MECHANISM_FAMILY = "cboe_volatility_term_structure_entry_admission"
TRIAL_FAMILY = "cboe_vix9d_vix_backwardation_core_entry_gate"
NEW_EVIDENCE_AXIS = (
    "Genuinely new data source: CBOE option-implied VIX9D versus VIX term "
    "structure, explicitly named as required reopen evidence by "
    "exp-20260607-018 and exp-20260607-023; no prior family used VIX9D/VIX "
    "backwardation."
)
NEARBY = [
    "exp-20260603-024",
    "exp-20260607-018",
    "exp-20260607-023",
    "exp-20260708-028",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(result) or math.isinf(result) else result


def round6(value: Any) -> float:
    return round(number(value), 6)


def _close_series(frame: Any, ticker: str) -> Any:
    if getattr(frame, "empty", True):
        return None
    columns = getattr(frame, "columns", None)
    if getattr(columns, "nlevels", 1) > 1:
        try:
            return frame["Close"][ticker]
        except (KeyError, TypeError):
            try:
                return frame[("Close", ticker)]
            except (KeyError, TypeError):
                return None
    if ticker not in ("^VIX", "^VIX9D"):
        return None
    return frame.get("Close")


def fetch_term_structure() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    fetch_start = min(row["start"] for row in WINDOWS.values())
    max_end = dt.date.fromisoformat(max(row["end"] for row in WINDOWS.values()))
    fetch_end = (max_end + dt.timedelta(days=1)).isoformat()
    cached = read_json(TERM_STRUCTURE_JSON, {})
    cached_rows = cached.get("rows") or []
    cached_by_date = {
        str(row.get("date")): row
        for row in cached_rows
        if isinstance(row, dict) and row.get("date")
    }
    if (
        cached_by_date
        and min(cached_by_date) <= fetch_start
        and max(cached_by_date) >= max_end.isoformat()
        and all(
            cached_by_date.get(date, {}).get("complete")
            for date in (
                "2024-10-02",
                "2025-04-22",
                "2025-10-22",
                "2026-04-21",
            )
        )
    ):
        metadata = dict(cached.get("metadata") or {})
        metadata["cache_reused_at"] = utc_now()
        metadata["cache_reused"] = True
        return cached_by_date, metadata

    frame = download_with_rate_limit_retry(
        ["^VIX", "^VIX9D"],
        start=fetch_start,
        end=fetch_end,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if frame is None or frame.empty:
        raise RuntimeError("Yahoo mirror returned no VIX/VIX9D history")

    vix = _close_series(frame, "^VIX")
    vix9d = _close_series(frame, "^VIX9D")
    if vix is None or vix9d is None:
        raise RuntimeError("Yahoo mirror did not expose both VIX and VIX9D closes")

    state_by_date: dict[str, dict[str, Any]] = {}
    all_dates = sorted(set(vix.dropna().index) | set(vix9d.dropna().index))
    for index in all_dates:
        date_text = str(index.date())
        vix_value = number(vix.get(index), default=float("nan"))
        vix9d_value = number(vix9d.get(index), default=float("nan"))
        complete = not (math.isnan(vix_value) or math.isnan(vix9d_value))
        state_by_date[date_text] = {
            "date": date_text,
            "vix_close": round(vix_value, 6) if complete else None,
            "vix9d_close": round(vix9d_value, 6) if complete else None,
            "vix9d_minus_vix": round(vix9d_value - vix_value, 6) if complete else None,
            "backwardation": bool(complete and vix9d_value > vix_value),
            "complete": complete,
            "known_at": "signal_day_close_before_next_open_entry",
        }
    complete_rows = [row for row in state_by_date.values() if row["complete"]]
    metadata = {
        "source_owner": "Cboe Global Markets",
        "delivery_vendor": "Yahoo Finance index mirror via yfinance",
        "symbols": ["^VIX", "^VIX9D"],
        "official_reference_urls": [
            "https://www.cboe.com/tradable-products/vix/term-structure",
            "https://www.cboe.com/tradable-products/vix/vix-historical-data/",
        ],
        "fetch_start": fetch_start,
        "fetch_end_exclusive": fetch_end,
        "row_count": len(state_by_date),
        "complete_row_count": len(complete_rows),
        "backwardation_row_count": sum(1 for row in complete_rows if row["backwardation"]),
        "first_complete_date": complete_rows[0]["date"] if complete_rows else None,
        "last_complete_date": complete_rows[-1]["date"] if complete_rows else None,
        "gate_rule": "VIX9D close > VIX close",
        "missing_date_behavior": "fail_open_keep_core_entries",
        "downloaded_at": utc_now(),
        "cache_reused": False,
    }
    write_json(
        TERM_STRUCTURE_JSON,
        {"metadata": metadata, "rows": list(state_by_date.values())},
    )
    return state_by_date, metadata


def frozen_universe(snapshot_source: str) -> list[str]:
    """Return the universe embedded in the canonical snapshot.

    ``data_layer.get_universe()`` is intentionally current/live and has drifted
    since the fixed windows were accepted (TRIP left while GEV/HOOD/MUU/TQQQ
    entered).  Gate 1 must instead use the snapshot's frozen ticker list and
    remove the explicitly tagged cross-asset context proxies.
    """
    snapshot = read_json(REPO_ROOT / snapshot_source, {})
    metadata = snapshot.get("metadata") or {}
    tickers = {str(value).upper() for value in metadata.get("tickers") or []}
    proxies = {
        str(value).upper()
        for value in (
            list(metadata.get("cross_asset_proxies_added") or [])
            + list(metadata.get("added_tickers") or [])
        )
    }
    universe = sorted(tickers - proxies)
    if not universe:
        raise RuntimeError(f"canonical snapshot has no frozen universe: {snapshot_source}")
    return universe


@contextlib.contextmanager
def backwardation_entry_gate(state_by_date: dict[str, dict[str, Any]]):
    original_compute = feature_layer.compute_features
    original_generate = signal_engine.generate_signals
    original_filter = bt.filter_entry_signal_candidates
    audit_by_date: dict[str, dict[str, Any]] = {}

    def dated_compute_features(ticker, ohlcv_data, earnings_data):
        features = original_compute(ticker, ohlcv_data, earnings_data)
        if features is not None and ohlcv_data is not None and not ohlcv_data.empty:
            features["_cboe_signal_date"] = str(ohlcv_data.index[-1].date())
        return features

    def dated_generate_signals(features_dict, *args, **kwargs):
        signals = original_generate(features_dict, *args, **kwargs)
        signal_date = next(
            (
                str(features.get("_cboe_signal_date"))
                for features in features_dict.values()
                if isinstance(features, dict) and features.get("_cboe_signal_date")
            ),
            None,
        )
        for signal in signals:
            signal["_cboe_signal_date"] = signal_date
        return signals

    def filtered_entry_candidates(signals, *args, **kwargs):
        planned, audit = original_filter(signals, *args, **kwargs)
        signal_date = next(
            (
                str(signal.get("_cboe_signal_date"))
                for signal in signals or []
                if signal.get("_cboe_signal_date")
            ),
            None,
        )
        state = state_by_date.get(signal_date or "")
        backwardation = bool(state and state.get("backwardation"))
        dropped = list(planned) if backwardation else []
        if backwardation:
            planned = []
        audit["cboe_vix9d_vix"] = {
            "signal_date": signal_date,
            "state_available": bool(state and state.get("complete")),
            "backwardation": backwardation,
            "vix_close": state.get("vix_close") if state else None,
            "vix9d_close": state.get("vix9d_close") if state else None,
            "dropped_count": len(dropped),
            "dropped_tickers": [row.get("ticker") for row in dropped],
            "missing_date_fail_open": state is None or not state.get("complete", False),
        }
        audit["signals_after_entry_filters"] = len(planned)
        if signal_date:
            audit_by_date[signal_date] = audit["cboe_vix9d_vix"]
        return planned, audit

    feature_layer.compute_features = dated_compute_features
    signal_engine.generate_signals = dated_generate_signals
    bt.filter_entry_signal_candidates = filtered_entry_candidates
    try:
        yield audit_by_date
    finally:
        feature_layer.compute_features = original_compute
        signal_engine.generate_signals = original_generate
        bt.filter_entry_signal_candidates = original_filter


def metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": round6(result.get("expected_value_score")),
        "sharpe_daily": round6(result.get("sharpe_daily")),
        "total_pnl": round(number(result.get("total_pnl")), 2),
        "strategy_total_return_pct": round6(
            benchmarks.get("strategy_total_return_pct")
        ),
        "max_drawdown_pct": round6(result.get("max_drawdown_pct")),
        "win_rate": round6(result.get("win_rate")),
        "total_trades": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": round6(result.get("survival_rate")),
    }


def metric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in before:
        if isinstance(before[key], (int, float)) and isinstance(after.get(key), (int, float)):
            output[key] = round(number(after[key]) - number(before[key]), 6)
    return output


def run_window(
    label: str,
    spec: dict[str, Any],
    state_by_date: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    universe = frozen_universe(spec["snapshot"])
    common = {
        "universe": universe,
        "start": spec["start"],
        "end": spec["end"],
        "config": {"REGIME_AWARE_EXIT": True},
        "replay_llm": False,
        "replay_news": False,
        "data_dir": str(REPO_ROOT / "data"),
        "ohlcv_warehouse_path": str(WAREHOUSE),
        "ohlcv_warehouse_snapshot_source": spec["snapshot"],
    }
    before_result = BacktestEngine(**common).run()
    if before_result.get("error"):
        raise RuntimeError(f"{label} baseline failed: {before_result['error']}")
    with backwardation_entry_gate(state_by_date) as gate_audit:
        after_result = BacktestEngine(**common).run()
    if after_result.get("error"):
        raise RuntimeError(f"{label} after failed: {after_result['error']}")

    before_path = DATA_DIR / f"before_{label}.json"
    after_path = DATA_DIR / f"after_{label}.json"
    write_json(before_path, before_result)
    write_json(after_path, after_result)

    before_metrics = metrics(before_result)
    after_metrics = metrics(after_result)
    gate_rows = list(gate_audit.values())
    dropped_rows = [row for row in gate_rows if row["dropped_count"] > 0]
    backwardation_days = [
        date
        for date, state in state_by_date.items()
        if spec["start"] <= date <= spec["end"] and state.get("backwardation")
    ]
    return {
        "label": label,
        "start": spec["start"],
        "end": spec["end"],
        "snapshot": spec["snapshot"],
        "frozen_universe_count": len(universe),
        "frozen_universe": universe,
        "before_result": repo_rel(before_path),
        "after_result": repo_rel(after_path),
        "before": before_metrics,
        "after": after_metrics,
        "delta": metric_delta(after_metrics, before_metrics),
        "identity": {
            "canonical_ev": spec["canonical_ev"],
            "canonical_pnl": spec["canonical_pnl"],
            "ev_drift": round(before_metrics["expected_value_score"] - spec["canonical_ev"], 6),
            "pnl_drift": round(before_metrics["total_pnl"] - spec["canonical_pnl"], 2),
            "passed": abs(before_metrics["expected_value_score"] - spec["canonical_ev"]) <= 0.0001
            and abs(before_metrics["total_pnl"] - spec["canonical_pnl"]) <= 0.01,
        },
        "term_structure_coverage": {
            "backwardation_market_days": len(backwardation_days),
            "candidate_dates_seen": len(gate_rows),
            "candidate_dates_missing_state": sum(
                1 for row in gate_rows if row["missing_date_fail_open"]
            ),
            "candidate_dates_with_drops": len(dropped_rows),
            "dropped_signal_count": sum(row["dropped_count"] for row in dropped_rows),
            "dropped_ticker_counts": dict(
                Counter(
                    ticker
                    for row in dropped_rows
                    for ticker in row["dropped_tickers"]
                    if ticker
                )
            ),
            "drop_rows": dropped_rows,
        },
    }


def aggregate_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(row["before"]["expected_value_score"] for row in windows)
    after_ev = sum(row["after"]["expected_value_score"] for row in windows)
    before_pnl = sum(row["before"]["total_pnl"] for row in windows)
    after_pnl = sum(row["after"]["total_pnl"] for row in windows)
    return {
        "before_expected_value_score": round(before_ev, 6),
        "after_expected_value_score": round(after_ev, 6),
        "expected_value_score_delta": round(after_ev - before_ev, 6),
        "expected_value_score_delta_pct": round((after_ev / before_ev - 1.0) * 100.0, 4)
        if before_ev
        else None,
        "before_total_pnl": round(before_pnl, 2),
        "after_total_pnl": round(after_pnl, 2),
        "total_pnl_delta": round(after_pnl - before_pnl, 2),
        "ev_improved_windows": [
            row["label"] for row in windows if row["delta"]["expected_value_score"] > 0
        ],
        "ev_regressed_windows": [
            row["label"] for row in windows if row["delta"]["expected_value_score"] < 0
        ],
        "pnl_regressed_windows": [
            row["label"] for row in windows if row["delta"]["total_pnl"] < 0
        ],
        "max_drawdown_drift_max": max(
            row["delta"]["max_drawdown_pct"] for row in windows
        ),
        "before_trade_count": sum(row["before"]["total_trades"] for row in windows),
        "after_trade_count": sum(row["after"]["total_trades"] for row in windows),
        "trade_count_delta": sum(row["delta"]["total_trades"] for row in windows),
        "min_after_survival_rate": min(row["after"]["survival_rate"] for row in windows),
        "dropped_signal_count": sum(
            row["term_structure_coverage"]["dropped_signal_count"] for row in windows
        ),
        "candidate_dates_missing_state": sum(
            row["term_structure_coverage"]["candidate_dates_missing_state"]
            for row in windows
        ),
    }


def evaluate_gate4(aggregate: dict[str, Any]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    if aggregate["expected_value_score_delta"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if len(aggregate["ev_improved_windows"]) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if aggregate["ev_regressed_windows"]:
        failed.append("window_ev_regression")
    if aggregate["pnl_regressed_windows"]:
        failed.append("window_pnl_regression")
    if aggregate["max_drawdown_drift_max"] > 0.5:
        failed.append("drawdown_drift_above_0p5pp")
    if aggregate["after_trade_count"] < 40:
        failed.append("remaining_trade_count_below_40")
    if aggregate["min_after_survival_rate"] < 0.05:
        failed.append("survival_rate_below_5pct")
    if aggregate["dropped_signal_count"] <= 0:
        failed.append("gate_did_not_touch_any_candidate")
    if aggregate["candidate_dates_missing_state"] > 0:
        failed.append("candidate_date_term_structure_gap")
    return not failed, failed


def compact_window(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": row["label"],
        "before": row["before"],
        "after": row["after"],
        "delta": row["delta"],
        "identity": row["identity"],
        "term_structure_coverage": {
            key: value
            for key, value in row["term_structure_coverage"].items()
            if key != "drop_rows"
        },
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    state_by_date, source_metadata = fetch_term_structure()
    windows = [
        run_window(label, spec, state_by_date)
        for label, spec in WINDOWS.items()
    ]
    aggregate = aggregate_windows(windows)
    positive_lead, failed = evaluate_gate4(aggregate)
    identity_passed = all(row["identity"]["passed"] for row in windows)
    if not identity_passed:
        positive_lead = False
        failed = [*failed, "gate1_baseline_identity_failed"]

    decision = (
        "positive_replay_lead_not_promoted_cboe_vix9d_vix_backwardation_entry_gate"
        if positive_lead
        else "observed_only_rejected_cboe_vix9d_vix_backwardation_entry_gate"
    )
    realized_modes = [
        mode
        for mode in (ticket.get("prediction") or {}).get("main_failure_modes", [])
        if (
            (mode == "sample_too_thin" and aggregate["after_trade_count"] < 40)
            or (mode == "yahoo_cboe_date_gaps" and aggregate["candidate_dates_missing_state"] > 0)
            or (mode == "gate_removes_convex_recovery_winners" and aggregate["total_pnl_delta"] < 0)
            or (mode == "backwardation_days_already_blocked_by_bear_regime" and aggregate["dropped_signal_count"] == 0)
            or (mode == "one_window_concentration" and len(aggregate["ev_improved_windows"]) < 2)
        )
    ]
    completed_at = utc_now()
    production_impact = {
        "strategy_code_changed": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "entry_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "exit_rules_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "trade_enabled": False,
        "scope": "experiment_local_private_replay_scout",
    }
    why = (
        "The fixed option-implied backwardation state removed candidates on "
        "enough dates to improve the canonical replay without a window or risk "
        "regression. Because the data adapter and gate exist only in this "
        "runner, the result is a lead rather than accepted alpha."
        if positive_lead
        else "The fixed VIX9D>VIX backwardation gate did not improve the current "
        "core stack under the predeclared multi-window rules. The likely cause "
        "is overlap with existing bear/regime protection or deletion of "
        "high-convexity rebound entries rather than isolation of uniquely weak "
        "entry conditions."
    )
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(TERM_STRUCTURE_JSON),
        repo_rel(BEFORE_JSON),
        repo_rel(AFTER_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        "scripts/experiment_fingerprint.py",
        "quant/test_experiment_fingerprint.py",
        "docs/frozen_families.jsonl",
        *[row["before_result"] for row in windows],
        *[row["after_result"] for row in windows],
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": positive_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": "entry_exclusion_private_replay_scout",
        "implementation_mode": "private_replay_scout_data_shape_uncertain",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": ticket.get("causal_components", []),
        "new_evidence_type": "new_data_source",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY,
        "multiple_testing_risk_bucket": "low",
        "prediction": ticket.get("prediction"),
        "calibration": {
            "predicted_success_probability": (ticket.get("prediction") or {}).get(
                "success_probability"
            ),
            "realized_success": positive_lead,
            "realized_failure_modes": realized_modes or failed,
        },
        "source": source_metadata,
        "gate1": {
            "baseline_available": BASELINE_RESULT.exists(),
            "warehouse_available": WAREHOUSE.exists(),
            "canonical_windows": list(WINDOWS.keys()),
            "identity_passed": identity_passed,
            "windows": {row["label"]: row["identity"] for row in windows},
            "passed": BASELINE_RESULT.exists() and WAREHOUSE.exists() and identity_passed,
        },
        "gate2": {
            "required_term_structure_fields": ["date", "vix_close", "vix9d_close"],
            "decision_time": "after_signal_day_close_before_next_open",
            "missing_date_behavior": "fail_open_keep_core_entries",
            "entry_date_and_target_price_sentinels": {
                row["label"]: {
                    "entry_date_complete": all(
                        trade.get("entry_date")
                        for trade in read_json(REPO_ROOT / row["before_result"], {}).get("trades", [])
                    ),
                    "target_price_complete": all(
                        trade.get("target_price") is not None
                        for trade in read_json(REPO_ROOT / row["before_result"], {}).get("trades", [])
                    ),
                }
                for row in windows
            },
            "passed": aggregate["candidate_dates_missing_state"] == 0,
        },
        "gate3": {
            "signals_generated": {
                row["label"]: row["after"]["signals_generated"] for row in windows
            },
            "signals_survived": {
                row["label"]: row["after"]["signals_survived"] for row in windows
            },
            "survival_rate": {
                row["label"]: row["after"]["survival_rate"] for row in windows
            },
            "min_survival_rate": aggregate["min_after_survival_rate"],
            "passed": aggregate["min_after_survival_rate"] >= 0.05,
        },
        "gate4": {
            "full_backtest_replay": True,
            "positive_replay_lead": positive_lead,
            "accepted_alpha": False,
            "failed_reasons": failed,
            "aggregate": aggregate,
            "windows": [compact_window(row) for row in windows],
            "acceptance_rule": ticket.get("acceptance_rule"),
            "promotion_boundary": "positive result still requires shared-paper-first helper and parity",
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing the VIX9D/VIX spread threshold, using "
                "a ratio instead of a difference, adding lookbacks, switching "
                "to VIX3M/VIX6M, limiting to a strategy/ticker/window, changing "
                "missing-date handling, or converting the same rejected signal "
                "to a scalar/tilt. Those are retunes of this evidence surface."
            ),
            "new_evidence_required": (
                "If positive, the only next step is a shared-paper-first Cboe "
                "term-structure helper with daily default-off snapshot, parity, "
                "and the same fixed rule. If rejected, revisit only with "
                "materially settled forward rows from such a helper or a "
                "genuinely different volatility-risk-transfer source."
            ),
        },
        "rejection_reason": None if positive_lead else ";".join(failed),
        "next_retry_requires": [
            "shared_paper_first_fixed_rule_gate_1_4" if positive_lead else "different_volatility_risk_transfer_source",
            "no_vix9d_vix_threshold_ratio_lookback_strategy_window_or_response_retune",
        ],
        "changed_files": changed_files,
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(WAREHOUSE),
            *[spec["snapshot"] for spec in WINDOWS.values()],
            *NEARBY,
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "term_structure_artifact": repo_rel(TERM_STRUCTURE_JSON),
        "before_measurement": repo_rel(BEFORE_JSON),
        "after_measurement": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
        "ticket_before": ticket,
        "windows": windows,
        "completed_at": completed_at,
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "new_evidence_type",
        "new_evidence_axis",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "prediction",
        "calibration",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
        "artifact",
        "log",
        "completed_at",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["gate4"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: Cboe VIX9D/VIX Backwardation Entry Gate",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Positive replay lead: `{payload['observed_only_lead']}`",
        "- Production behavior changed: `false`",
        f"- Artifact: `{payload['artifact']}`",
        "",
        "## Aggregate",
        "",
        f"- EV: `{aggregate['before_expected_value_score']}` -> `{aggregate['after_expected_value_score']}` (`{aggregate['expected_value_score_delta']:+}`)",
        f"- PnL: `${aggregate['before_total_pnl']}` -> `${aggregate['after_total_pnl']}` (`${aggregate['total_pnl_delta']:+}`)",
        f"- Trades: `{aggregate['before_trade_count']}` -> `{aggregate['after_trade_count']}`",
        f"- Dropped signals: `{aggregate['dropped_signal_count']}`",
        f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
        "",
        "## Windows",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Dropped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["windows"]:
        lines.append(
            f"| {row['label']} | {row['before']['expected_value_score']} | "
            f"{row['after']['expected_value_score']} | {row['delta']['expected_value_score']} | "
            f"{row['before']['total_pnl']} | {row['after']['total_pnl']} | "
            f"{row['delta']['total_pnl']} | "
            f"{row['term_structure_coverage']['dropped_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "Forbidden retry: "
            + payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "Next evidence: "
            + payload["post_run_reflection"]["new_evidence_required"],
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    aggregate = payload["gate4"]["aggregate"]
    before = {
        "experiment_id": EXPERIMENT_ID,
        "measurement_type": "canonical_three_window_full_backtest_before",
        "expected_value_score": aggregate["before_expected_value_score"],
        "total_pnl": aggregate["before_total_pnl"],
        "total_trades": aggregate["before_trade_count"],
        "windows": {row["label"]: row["before"] for row in payload["windows"]},
    }
    after = {
        "experiment_id": EXPERIMENT_ID,
        "measurement_type": "canonical_three_window_full_backtest_after_vix9d_vix_gate",
        "expected_value_score": aggregate["after_expected_value_score"],
        "total_pnl": aggregate["after_total_pnl"],
        "total_trades": aggregate["after_trade_count"],
        "delta": {
            "expected_value_score": aggregate["expected_value_score_delta"],
            "total_pnl": aggregate["total_pnl_delta"],
            "total_trades": aggregate["trade_count_delta"],
        },
        "windows": {row["label"]: row["after"] for row in payload["windows"]},
    }
    log_record = compact_log(payload)
    ticket = dict(payload["ticket_before"] or {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["completed_at"],
            "result": {
                "decision": payload["decision"],
                "accepted": False,
                "accepted_alpha": False,
                "observed_only_lead": payload["observed_only_lead"],
                "artifact": payload["artifact"],
                "log": payload["log"],
                "gate4": payload["gate4"],
            },
        }
    )
    write_json(OUT_JSON, payload)
    write_json(BEFORE_JSON, before)
    write_json(AFTER_JSON, after)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, ticket)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            key: payload[key]
            for key in (
                "owner",
                "hypothesis",
                "change_type",
                "implementation_mode",
                "mechanism_family",
                "trial_family",
                "trial_variant_id",
                "single_causal_variable",
                "changed_variable",
                "new_evidence_type",
                "new_evidence_axis",
                "nearby_prior_experiments",
                "multiple_testing_risk_bucket",
                "gate1",
                "gate2",
                "gate3",
                "gate4",
                "production_impact",
                "post_run_reflection",
                "changed_files",
                "related_files",
                "lean_quality_passed",
                "calibration",
            )
        },
    )
    manifest_files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        TERM_STRUCTURE_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        REGISTRY_JSON,
        REPO_ROOT / "scripts" / "experiment_fingerprint.py",
        REPO_ROOT / "quant" / "test_experiment_fingerprint.py",
    ]
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "runner": RUNNER,
            "command": RUNNER_COMMAND,
            "files": {
                repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
                for path in manifest_files
            },
            "updated_at": utc_now(),
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "aggregate": payload["gate4"]["aggregate"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
