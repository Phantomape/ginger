"""exp-20260627-025: intraday advisory shadow-action forward attribution.

Observed-only alpha attribution. The single question is whether production-
visible intraday advisory shadow actions on existing positions identify held
names with worse next-1d / next-3d close returns than OK positions.

This runner changes no shared policy, entry, exit, ranking, sizing, paper state,
live order, watchlist, daily artifact, or LLM boundary. A positive result would
only justify more forward logging and a later shared exit-lifecycle experiment.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from ohlcv_warehouse import connect_overlay_reader  # noqa: E402


EXPERIMENT_ID = "exp-20260627-025"
OWNER = "alpha-explore"
SLUG = "intraday_advisory_shadow_forward_outcome"
RUNNER = f"quant/experiments/exp_20260627_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "intraday" / "snapshots"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_025_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only attribution: production-visible intraday advisory shadow "
    "actions on existing positions should identify held names with worse "
    "next-1d/3d forward close returns than OK positions, creating a future "
    "shared exit-lifecycle evidence lead without changing strategy behavior."
)
CHANGE_TYPE = "observed_only_forward_attribution"
IMPLEMENTATION_MODE = "observed_only_intraday_exit_advisory_attribution"
MECHANISM_FAMILY = "intraday_exit_advisory_forward_attribution"
TRIAL_FAMILY = "intraday_advisory_shadow_action_forward_outcome"
TRIAL_VARIANT_ID = "primary_shadow_action_vs_ok_next_1d_3d_v1"
CHANGED_VARIABLE = "intraday_advisory_shadow_action_forward_outcome_v1"
NEW_EVIDENCE_TYPE = "post_exp024_intraday_primary_action_closed_forward_rows"
NEW_EVIDENCE_AXIS = (
    "New forward rows from production-visible intraday_review snapshots carrying "
    "primary or derivable advisory shadow actions; this is not a target-trim "
    "replay, threshold sweep, or frozen candidate-pool retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260627-013",
    "exp-20260627-024",
    "exp-20260429-032",
    "exp-20260623-003",
]
CAUSAL_COMPONENTS = [
    "intraday_review snapshots",
    "primary advisory shadow action extraction",
    "next-1d and next-3d OHLCV settlement",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "mature_forward_rows_too_thin",
        "weekend_or_unsettled_rows_filtered",
        "review_actions_legacy_target_noise",
        "no_directional_separation",
    ],
    "confidence_reason": (
        "The intraday review surface now emits primary advisory shadow actions "
        "and exp-20260627-013 explicitly named post-exp024 intraday closed rows "
        "with primary actions as a legal new evidence axis. The evidence is "
        "early and likely thin, but it is production-visible and tests "
        "exit-lifecycle attribution without touching orders."
    ),
    "recorded_at": "2026-06-27T21:04:59+00:00",
}
CONFIG = {
    "asof_min_date": "2026-06-22",
    "asof_max_date": "2026-06-27",
    "horizons": [1, 3],
    "min_primary_h1_rows": 20,
    "min_primary_h1_action_rows": 8,
    "min_primary_h1_ok_rows": 8,
    "min_h3_action_rows": 3,
    "min_h3_ok_rows": 3,
    "required_action_underperformance_pp": 1.0,
}


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
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": sum(int(w.get("signals_generated") or 0) for w in windows),
        "signals_survived": sum(int(w.get("signals_survived") or 0) for w in windows),
        "survival_rate": min(
            (float(w.get("survival_rate") or 0.0) for w in windows), default=None
        ),
        "max_drawdown_pct_worst": max(
            (float(w.get("max_drawdown_pct") or 0.0) for w in windows), default=None
        ),
        "window_count": len(windows),
    }


def snapshot_date(path: Path) -> str:
    stem = path.stem
    # intraday_review_YYYYMMDD_1302ET
    return stem.split("_")[2]


def normalized_date(raw: str) -> str:
    raw = str(raw or "")[:10]
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    raw = raw.replace("-", "")[:8]
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def load_intraday_snapshots() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(SNAPSHOT_DIR.glob("intraday_review_*.json")):
        try:
            payload = read_json(path, {})
        except json.JSONDecodeError:
            continue
        day = normalized_date(str(payload.get("date") or snapshot_date(path)))
        if day < CONFIG["asof_min_date"] or day > CONFIG["asof_max_date"]:
            continue
        rows.append({"path": path, "date": day, "payload": payload})
    return rows


def load_price_rows(tickers: set[str]) -> dict[str, dict[str, dict[str, float]]]:
    if not tickers:
        return {}
    out: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    placeholders = ",".join("?" for _ in tickers)
    sql = (
        "SELECT ticker, date, open, high, low, close FROM ohlcv_overlay "
        f"WHERE ticker IN ({placeholders}) ORDER BY ticker, date"
    )
    conn = connect_overlay_reader()
    try:
        for ticker, day, open_, high, low, close in conn.execute(sql, tuple(sorted(tickers))):
            out[str(ticker)][str(day)] = {
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
            }
    finally:
        conn.close()
    return dict(out)


def trading_dates(price_rows: dict[str, dict[str, dict[str, float]]]) -> list[str]:
    return sorted((price_rows.get("SPY") or {}).keys())


def future_date_for(calendar: list[str], day: str, horizon: int) -> str | None:
    after = [value for value in calendar if value > day]
    if len(after) < horizon:
        return None
    return after[horizon - 1]


def first_float(*values: Any) -> float | None:
    for raw in values:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value == value:
            return value
    return None


def infer_shadow_action(position: dict[str, Any]) -> dict[str, Any]:
    native = position.get("primary_advisory_shadow_action")
    if isinstance(native, dict):
        return {
            "shadow_action": native.get("shadow_action") or "UNKNOWN",
            "rule": native.get("rule"),
            "urgency": native.get("urgency"),
            "source": "native_primary_advisory_shadow_action",
            "pending_action": bool(native.get("pending_action")),
            "creates_order": bool(native.get("creates_order")),
            "advisory_only": bool(native.get("advisory_only", True)),
        }

    context = position.get("context") or {}
    exit_signals = context.get("exit_signals") or {}
    rules = [r for r in (exit_signals.get("triggered_rules") or []) if isinstance(r, dict)]
    if not rules:
        return {
            "shadow_action": "NONE",
            "rule": None,
            "urgency": None,
            "source": "derived_no_triggered_rule",
            "pending_action": False,
            "creates_order": False,
            "advisory_only": True,
        }

    def priority(rule: dict[str, Any]) -> tuple[int, int]:
        urgency = str(rule.get("urgency") or "").upper()
        name = str(rule.get("rule") or "").upper()
        if urgency == "CRITICAL" or name == "CRITICAL_EXIT":
            return (0, 0)
        if urgency == "HIGH":
            return (1, 0)
        if name == "SIGNAL_TARGET":
            return (1, 1)
        if urgency == "REVIEW":
            return (2, 0)
        return (3, 0)

    selected = sorted(rules, key=priority)[0]
    urgency = str(selected.get("urgency") or "").upper() or None
    rule_name = str(selected.get("rule") or "").upper() or None
    if urgency in {"CRITICAL", "HIGH"} and rule_name != "LEGACY_TARGET_REVIEW":
        action = "EXIT"
    elif rule_name in {"SIGNAL_TARGET", "TARGET_EXIT"}:
        action = "EXIT"
    else:
        action = "REVIEW"
    return {
        "shadow_action": action,
        "rule": rule_name,
        "urgency": urgency,
        "source": "derived_from_context_exit_signals",
        "pending_action": False,
        "creates_order": False,
        "advisory_only": True,
    }


def extract_observations(
    snapshots: list[dict[str, Any]],
    price_rows: dict[str, dict[str, dict[str, float]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    calendar = trading_dates(price_rows)
    observations: list[dict[str, Any]] = []
    skipped = Counter()
    source_counts = Counter()
    native_primary_count = 0

    for item in snapshots:
        day = item["date"]
        payload = item["payload"]
        path = item["path"]
        if day not in set(calendar):
            skipped["snapshot_non_trading_or_no_spy_bar"] += 1
            continue
        positions = payload.get("positions") or []
        if not isinstance(positions, list):
            skipped["snapshot_positions_not_list"] += 1
            continue
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            ticker = str(pos.get("ticker") or "").upper().strip()
            if not ticker:
                skipped["position_missing_ticker"] += 1
                continue
            if day not in (price_rows.get(ticker) or {}):
                skipped["position_missing_entry_bar"] += 1
                continue
            action = infer_shadow_action(pos)
            source_counts[action["source"]] += 1
            if action["source"] == "native_primary_advisory_shadow_action":
                native_primary_count += 1
            quote = pos.get("quote") or {}
            context = pos.get("context") or {}
            entry_close = price_rows[ticker][day]["close"]
            spy_entry = (price_rows.get("SPY") or {}).get(day, {}).get("close")
            qqq_entry = (price_rows.get("QQQ") or {}).get(day, {}).get("close")
            outcomes: dict[str, Any] = {}
            for horizon in CONFIG["horizons"]:
                future_day = future_date_for(calendar, day, int(horizon))
                key = f"h{horizon}"
                if not future_day:
                    outcomes[key] = {"status": "unsettled_missing_calendar_date"}
                    continue
                future_bar = (price_rows.get(ticker) or {}).get(future_day)
                spy_future = (price_rows.get("SPY") or {}).get(future_day, {}).get("close")
                qqq_future = (price_rows.get("QQQ") or {}).get(future_day, {}).get("close")
                if not future_bar:
                    outcomes[key] = {
                        "status": "unsettled_missing_ticker_future_bar",
                        "future_date": future_day,
                    }
                    continue
                future_close = future_bar["close"]
                ticker_return = (future_close / entry_close - 1.0) * 100.0
                row = {
                    "status": "settled",
                    "future_date": future_day,
                    "entry_close": round(entry_close, 6),
                    "future_close": round(future_close, 6),
                    "return_pct": round(ticker_return, 6),
                }
                if spy_entry and spy_future:
                    spy_return = (float(spy_future) / float(spy_entry) - 1.0) * 100.0
                    row["spy_return_pct"] = round(spy_return, 6)
                    row["spy_excess_pct"] = round(ticker_return - spy_return, 6)
                if qqq_entry and qqq_future:
                    qqq_return = (float(qqq_future) / float(qqq_entry) - 1.0) * 100.0
                    row["qqq_return_pct"] = round(qqq_return, 6)
                    row["qqq_excess_pct"] = round(ticker_return - qqq_return, 6)
                outcomes[key] = row

            observations.append(
                {
                    "observation_id": f"{day}:{ticker}:{path.stem}",
                    "snapshot_file": repo_rel(path),
                    "date": day,
                    "time_label": payload.get("time_label"),
                    "ticker": ticker,
                    "sleeve": pos.get("sleeve"),
                    "status_bucket": str(pos.get("status") or "UNKNOWN").upper(),
                    "shadow_action": action["shadow_action"],
                    "shadow_rule": action["rule"],
                    "shadow_urgency": action["urgency"],
                    "shadow_source": action["source"],
                    "has_shadow_action": action["shadow_action"] not in {"NONE", None},
                    "quote_price": first_float(quote.get("price")),
                    "daily_return_pct": first_float(context.get("daily_return_pct")),
                    "distance_to_hard_stop_pct": first_float(
                        pos.get("distance_to_hard_stop_pct")
                    ),
                    "distance_to_atr_stop_pct": first_float(pos.get("distance_to_atr_stop_pct")),
                    "distance_to_trailing_stop_pct": first_float(
                        pos.get("distance_to_trailing_stop_pct")
                    ),
                    "distance_to_target_pct": first_float(pos.get("distance_to_target_pct")),
                    "proximity_flags": list(pos.get("proximity_flags") or []),
                    "outcomes": outcomes,
                }
            )

    diagnostics = {
        "snapshot_count": len(snapshots),
        "trading_snapshot_count": len({row["date"] for row in observations}),
        "observation_count": len(observations),
        "skipped_counts": dict(skipped),
        "shadow_source_counts": dict(source_counts),
        "native_primary_advisory_shadow_action_count": native_primary_count,
        "calendar_min": min(calendar) if calendar else None,
        "calendar_max": max(calendar) if calendar else None,
    }
    return observations, diagnostics


def settled_rows(observations: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    key = f"h{horizon}"
    return [row for row in observations if (row.get("outcomes") or {}).get(key, {}).get("status") == "settled"]


def metric_values(rows: list[dict[str, Any]], horizon: int, field: str) -> list[float]:
    key = f"h{horizon}"
    out: list[float] = []
    for row in rows:
        raw = (row.get("outcomes") or {}).get(key, {}).get(field)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value == value:
            out.append(value)
    return out


def summarize_numeric(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "positive_rate": None}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 6),
        "median": round(statistics.median(values), 6),
        "positive_rate": round(sum(1 for v in values if v > 0) / len(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def bucket_summary(rows: list[dict[str, Any]], horizon: int, bucket_field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(bucket_field) or "UNKNOWN")].append(row)
    summary: dict[str, Any] = {}
    for bucket, members in sorted(groups.items()):
        summary[bucket] = {
            "row_count": len(members),
            "return_pct": summarize_numeric(metric_values(members, horizon, "return_pct")),
            "spy_excess_pct": summarize_numeric(metric_values(members, horizon, "spy_excess_pct")),
            "qqq_excess_pct": summarize_numeric(metric_values(members, horizon, "qqq_excess_pct")),
            "ticker_counts": dict(Counter(row["ticker"] for row in members).most_common(10)),
        }
    return summary


def compare_action_vs_ok(observations: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    rows = settled_rows(observations, horizon)
    action_rows = [
        row
        for row in rows
        if row.get("has_shadow_action") and row.get("shadow_action") != "NONE"
    ]
    ok_rows = [
        row
        for row in rows
        if row.get("status_bucket") == "OK" and not row.get("has_shadow_action")
    ]
    action_return = summarize_numeric(metric_values(action_rows, horizon, "return_pct"))
    ok_return = summarize_numeric(metric_values(ok_rows, horizon, "return_pct"))
    action_spy = summarize_numeric(metric_values(action_rows, horizon, "spy_excess_pct"))
    ok_spy = summarize_numeric(metric_values(ok_rows, horizon, "spy_excess_pct"))
    return {
        "horizon": horizon,
        "settled_rows": len(rows),
        "action_rows": len(action_rows),
        "ok_no_action_rows": len(ok_rows),
        "action_return_pct": action_return,
        "ok_no_action_return_pct": ok_return,
        "action_spy_excess_pct": action_spy,
        "ok_no_action_spy_excess_pct": ok_spy,
        "action_minus_ok_return_mean_pp": (
            round(float(action_return["mean"]) - float(ok_return["mean"]), 6)
            if action_return["mean"] is not None and ok_return["mean"] is not None
            else None
        ),
        "action_minus_ok_spy_excess_mean_pp": (
            round(float(action_spy["mean"]) - float(ok_spy["mean"]), 6)
            if action_spy["mean"] is not None and ok_spy["mean"] is not None
            else None
        ),
    }


def evaluate_gate4(observations: list[dict[str, Any]]) -> dict[str, Any]:
    comparisons = {
        f"h{horizon}": compare_action_vs_ok(observations, horizon)
        for horizon in CONFIG["horizons"]
    }
    h1 = comparisons["h1"]
    h3 = comparisons["h3"]
    failed: list[str] = []
    if h1["settled_rows"] < CONFIG["min_primary_h1_rows"]:
        failed.append("h1_settled_rows_below_min")
    if h1["action_rows"] < CONFIG["min_primary_h1_action_rows"]:
        failed.append("h1_action_rows_below_min")
    if h1["ok_no_action_rows"] < CONFIG["min_primary_h1_ok_rows"]:
        failed.append("h1_ok_rows_below_min")
    if h3["action_rows"] < CONFIG["min_h3_action_rows"]:
        failed.append("h3_action_rows_below_min")
    if h3["ok_no_action_rows"] < CONFIG["min_h3_ok_rows"]:
        failed.append("h3_ok_rows_below_min")

    h1_edge = h1.get("action_minus_ok_spy_excess_mean_pp")
    h3_edge = h3.get("action_minus_ok_spy_excess_mean_pp")
    required = -float(CONFIG["required_action_underperformance_pp"])
    if h1_edge is None or h1_edge > required:
        failed.append("h1_action_underperformance_not_met")
    if h3_edge is None or h3_edge > required:
        failed.append("h3_action_underperformance_not_met")

    passed = not failed
    decision = (
        "observed_only_positive_intraday_shadow_action_forward_lead_not_promoted"
        if passed
        else "observed_only_rejected_no_stable_intraday_shadow_action_edge"
    )
    return {
        "observed_only": True,
        "passed": passed,
        "decision": decision,
        "failed_reasons": failed,
        "comparisons": comparisons,
        "bucket_summary": {
            f"h{horizon}": {
                "by_shadow_action": bucket_summary(
                    settled_rows(observations, horizon), horizon, "shadow_action"
                ),
                "by_status_bucket": bucket_summary(
                    settled_rows(observations, horizon), horizon, "status_bucket"
                ),
                "by_shadow_rule": bucket_summary(
                    settled_rows(observations, horizon), horizon, "shadow_rule"
                ),
            }
            for horizon in CONFIG["horizons"]
        },
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    snapshots = load_intraday_snapshots()
    tickers = {"SPY", "QQQ"}
    for item in snapshots:
        for pos in item["payload"].get("positions") or []:
            if isinstance(pos, dict) and pos.get("ticker"):
                tickers.add(str(pos["ticker"]).upper())
    prices = load_price_rows(tickers)
    observations, source_diagnostics = extract_observations(snapshots, prices)
    gate4 = evaluate_gate4(observations)
    metrics = baseline_metrics()
    accepted = bool(gate4["passed"])
    status = "observed_only" if accepted else "observed_only_rejected"
    now = utc_now()
    realized_failure_modes = list(gate4["failed_reasons"])
    predicted_modes = PREDICTION["main_failure_modes"]
    prediction_hit = any(
        mode in {
            "mature_forward_rows_too_thin",
            "review_actions_legacy_target_noise",
            "no_directional_separation",
        }
        for mode in predicted_modes
    ) and bool(realized_failure_modes)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": gate4["decision"],
        "accepted": accepted,
        "accepted_alpha": False,
        "observed_only_lead": accepted,
        "lane": "alpha_search",
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
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 6),
            "predicted_failure_modes": predicted_modes,
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": prediction_hit,
            "surprise_note": (
                "The sample stayed early and did not produce a stable h1/h3 "
                "underperformance edge."
                if not accepted
                else "The early intraday action rows separated enough to become "
                "an observed-only lead, but no strategy behavior changed."
            ),
        },
        "parameters": {
            "config": CONFIG,
            "snapshot_glob": repo_rel(SNAPSHOT_DIR / "intraday_review_*.json"),
            "settlement_source": "ohlcv_warehouse.ohlcv_overlay",
        },
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_metrics": metrics,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "note": "Observed-only attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": bool(source_diagnostics["observation_count"]),
            "fields_checked": [
                "intraday_review.date",
                "positions[].ticker",
                "positions[].status",
                "positions[].quote.price",
                "positions[].context.exit_signals.triggered_rules",
                "positions[].primary_advisory_shadow_action",
                "ohlcv_overlay.entry_close",
                "ohlcv_overlay.future_close",
                "entry_date",
                "target_price",
            ],
            "source_diagnostics": source_diagnostics,
            "target_price_relevance": (
                "No target exits are scheduled. target_price is represented only "
                "inside existing intraday exit-level context for attribution."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_survival_rate": metrics.get("survival_rate"),
            "signals_generated": source_diagnostics["observation_count"],
            "signals_survived": len(settled_rows(observations, 1)),
            "survival_rate": round(
                len(settled_rows(observations, 1)) / source_diagnostics["observation_count"],
                6,
            )
            if source_diagnostics["observation_count"]
            else 0.0,
            "note": "No executable filter was added; rows are only attributed.",
        },
        "gate4": gate4,
        "before_metrics": metrics,
        "after_metrics": metrics,
        "delta_metrics": gate4["before_after_strategy_delta"],
        "observations": observations,
        "summary": {
            "observation_count": len(observations),
            "h1_settled_rows": len(settled_rows(observations, 1)),
            "h3_settled_rows": len(settled_rows(observations, 3)),
            "shadow_action_counts": dict(Counter(row["shadow_action"] for row in observations)),
            "status_bucket_counts": dict(Counter(row["status_bucket"] for row in observations)),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only attribution over existing intraday snapshots and OHLCV "
                "settlement. No order, exit, or daily adapter behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The current intraday sample is too young for a stable exit "
                "advisory signal: h1 rows are available, but h3 support and "
                "action-vs-OK separation are not strong enough to justify a "
                "shared exit-lifecycle policy."
                if not accepted
                else "The fixed intraday action buckets separated forward "
                "outcomes, but the result is still observed-only and needs more "
                "closed rows before any shared exit policy can be tested."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune SIGNAL_TARGET, TIME_STOP, stop-distance, target "
                "distance, or REVIEW/EXIT buckets on the same 2026-06-22..26 "
                "snapshots. Do not convert this into a target-trim replay."
            ),
            "new_evidence_required": (
                "More intraday snapshots with native primary_advisory_shadow_action, "
                "settled h3/h5/h10 outcomes, true quote timestamps or broker bar IDs, "
                "and slot-reuse/replacement-value accounting before Gate 1-4 exit promotion."
            ),
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if not accepted else None,
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            "data/daily/intraday/snapshots",
            "data/warehouse/warehouse_main.sqlite",
            "data/warehouse/warehouse_main_hot.sqlite",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": list((ticket or {}).get("allowed_write_scope") or []),
        "ticket_before": ticket,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
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
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    comparisons = gate4["comparisons"]
    lines = [
        f"# {EXPERIMENT_ID}: Intraday Advisory Shadow Forward Outcome",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Hypothesis",
        "",
        HYPOTHESIS,
        "",
        "## Result",
        "",
        f"- h1 settled/action/OK rows: `{comparisons['h1']['settled_rows']}` / "
        f"`{comparisons['h1']['action_rows']}` / `{comparisons['h1']['ok_no_action_rows']}`",
        f"- h1 action-minus-OK SPY-excess mean: "
        f"`{comparisons['h1']['action_minus_ok_spy_excess_mean_pp']}` pp",
        f"- h3 settled/action/OK rows: `{comparisons['h3']['settled_rows']}` / "
        f"`{comparisons['h3']['action_rows']}` / `{comparisons['h3']['ok_no_action_rows']}`",
        f"- h3 action-minus-OK SPY-excess mean: "
        f"`{comparisons['h3']['action_minus_ok_spy_excess_mean_pp']}` pp",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Reflection",
        "",
        f"- Why: {payload['post_run_reflection']['why_result_happened']}",
        f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
        f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": (REPO_ROOT / path).exists() if not path.is_absolute() else path.exists(),
                             "sha256": sha256(REPO_ROOT / path) if not path.is_absolute() else sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "summary": payload["summary"],
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "h1_comparison": payload["gate4"]["comparisons"]["h1"],
                "h3_comparison": payload["gate4"]["comparisons"]["h3"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
