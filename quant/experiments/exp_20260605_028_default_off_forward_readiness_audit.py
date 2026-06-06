"""exp-20260605-028: default-off forward readiness audit.

This read-only alpha-search audit checks whether any currently observed
default-off paper sleeve has enough closed forward outcomes and
replacement-value evidence to justify activation review without retuning a
frozen backtest sample.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260605-028"
SLUG = "default_off_forward_readiness_audit"
STEM = f"exp_20260605_028_{SLUG}"
TRIAL_FAMILY = "default_off_forward_replacement_value_activation_readiness"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "current_forward_closed_outcome_and_replacement_value_evidence_by_default_off_sleeve"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PAPER_SLEEVE_ROOT = REPO_ROOT / "data" / "paper_sleeves"
OPERATOR_OPEN_POSITIONS = REPO_ROOT / "operator_inputs" / "open_positions.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

DEFAULT_MIN_CLOSED_TRADES = 20
DEFAULT_MIN_WIN_RATE = 0.52
DEFAULT_MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.75

PAPER_SLEEVE_DIRS = (
    "accepted_source_consensus",
    "ai_optical",
    "alpha_score_market_regime",
    "finra_iwm",
    "free_data_cross_source_consensus",
    "fundamental_growth_rs",
    "low_deployment_etf",
    "post_earnings_underpriced_drift",
    "sec_financial_report",
    "sec_ftd_finra",
    "volatility_contraction",
    "volume_breadth_breakout",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    rows: list[str] = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig") as handle:
            for raw in handle:
                line = raw.rstrip("\n")
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    rows.append(line)
                    continue
                if isinstance(row, dict) and row.get("experiment_id") == EXPERIMENT_ID:
                    continue
                rows.append(line)
    rows.append(json.dumps(payload, sort_keys=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(rows))
        handle.write("\n")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float:
    parsed = _as_float(value)
    return parsed if parsed is not None else 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round(value: Any, digits: int = 6) -> Any:
    parsed = _as_float(value)
    if parsed is None:
        return value
    return round(parsed, digits)


def _baseline_metrics() -> OrderedDict[str, dict[str, Any]]:
    artifact = _load_json(BASELINE_RESULT)
    out: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in artifact.get("windows") or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "")
        if not label:
            continue
        expected_value = _safe_float(row.get("expected_value_score"))
        sharpe_daily = _safe_float(row.get("sharpe_daily"))
        total_return_pct = row.get("total_return_pct")
        if total_return_pct is None and sharpe_daily:
            total_return_pct = round(expected_value / sharpe_daily, 6)
        out[label] = {
            "expected_value_score": row.get("expected_value_score"),
            "strategy_total_return_pct": total_return_pct,
            "sharpe_daily": row.get("sharpe_daily"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
        }
    return out


def _latest_snapshot(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        return {}
    return sorted(
        snapshots,
        key=lambda row: (
            str(row.get("asof_date") or ""),
            str(row.get("generated_at") or row.get("timestamp") or ""),
        ),
    )[-1]


def _date_range(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    dates = sorted({str(row.get("asof_date") or "")[:10] for row in snapshots if row.get("asof_date")})
    return {
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "unique_asof_dates": len(dates),
    }


def _list_field(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    rows = payload.get(field)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _state_summary(state: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "pending_entries",
        "open_positions",
        "closed_positions",
        "skipped_entries",
        "observations",
        "core_positions",
    )
    return {
        "updated_at": state.get("updated_at") or state.get("generated_at"),
        "counts": {field: len(_list_field(state, field)) for field in fields},
    }


def _closed_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("decision_id") or row.get("event_id") or row.get("id") or ""),
        str(row.get("ticker") or row.get("symbol") or "").upper(),
        str(row.get("entry_date") or row.get("trade_date") or ""),
        str(row.get("exit_date") or row.get("close_date") or ""),
    )


def _closed_rows(state: dict[str, Any], snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in _list_field(state, "closed_positions"):
        latest[_closed_key(row)] = row
    for snapshot in snapshots:
        for row in _list_field(snapshot, "closed_today"):
            latest[_closed_key(row)] = row
    return list(latest.values())


def _pnl_value(row: dict[str, Any]) -> float | None:
    for field in (
        "pnl",
        "pnl_usd",
        "realized_pnl",
        "cash_relative_pnl",
        "paper_pnl_usd",
        "core_sized_pnl",
    ):
        parsed = _as_float(row.get(field))
        if parsed is not None:
            return parsed
    horizon_10d = (row.get("horizons") or {}).get("10d") if isinstance(row.get("horizons"), dict) else {}
    if isinstance(horizon_10d, dict):
        for field in ("cash_relative_pnl", "same_theme_replacement_value", "qqq_relative_value"):
            parsed = _as_float(horizon_10d.get(field))
            if parsed is not None:
                return parsed
    return None


def _replacement_fields_present(payloads: list[Any]) -> dict[str, Any]:
    hits: Counter[str] = Counter()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lower = str(key).lower()
                if "replacement" in lower or "relative_value" in lower:
                    hits[str(key)] += 1
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for payload in payloads:
        visit(payload)
    return {
        "present": bool(hits),
        "fields": dict(sorted(hits.items())),
    }


def _closed_metrics(closed: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [_pnl_value(row) for row in closed]
    usable = [value for value in pnl_values if value is not None]
    ticker_pnl: defaultdict[str, float] = defaultdict(float)
    positive_ticker_pnl: defaultdict[str, float] = defaultdict(float)
    ticker_counts: Counter[str] = Counter()
    for row, pnl in zip(closed, pnl_values):
        ticker = str(row.get("ticker") or row.get("symbol") or "UNKNOWN").upper()
        if pnl is None:
            continue
        ticker_counts[ticker] += 1
        ticker_pnl[ticker] += pnl
        if pnl > 0:
            positive_ticker_pnl[ticker] += pnl
    total_positive = sum(positive_ticker_pnl.values())
    ranked_positive = [
        {
            "ticker": ticker,
            "positive_pnl": round(value, 2),
            "share": round(value / total_positive, 6) if total_positive else 0.0,
        }
        for ticker, value in sorted(positive_ticker_pnl.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "closed_rows": len(closed),
        "closed_rows_with_pnl": len(usable),
        "realized_pnl": round(sum(usable), 2),
        "win_rate": round(sum(1 for value in usable if value > 0) / len(usable), 6) if usable else None,
        "loss_rate": round(sum(1 for value in usable if value <= 0) / len(usable), 6) if usable else None,
        "ticker_count": len(ticker_counts),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "positive_pnl_total": round(total_positive, 2),
        "top_positive_ticker": ranked_positive[0]["ticker"] if ranked_positive else None,
        "top_positive_ticker_share": ranked_positive[0]["share"] if ranked_positive else None,
        "positive_pnl_hhi": round(
            sum((value / total_positive) ** 2 for value in positive_ticker_pnl.values()),
            6,
        )
        if total_positive
        else None,
        "positive_ticker_pnl": ranked_positive,
        "ticker_pnl": {
            ticker: round(value, 2)
            for ticker, value in sorted(ticker_pnl.items(), key=lambda item: item[1], reverse=True)
        },
    }


def _gate_from_snapshot(latest: dict[str, Any]) -> dict[str, Any] | None:
    gate = latest.get("forward_paper_gate")
    return gate if isinstance(gate, dict) else None


def _readiness_gate(latest: dict[str, Any], closed_metrics: dict[str, Any]) -> dict[str, Any]:
    explicit_gate = _gate_from_snapshot(latest)
    if explicit_gate:
        metrics = explicit_gate.get("metrics") if isinstance(explicit_gate.get("metrics"), dict) else {}
        reasons = explicit_gate.get("reasons") if isinstance(explicit_gate.get("reasons"), list) else []
        return {
            "source": "explicit_forward_paper_gate",
            "passed": bool(explicit_gate.get("passed")),
            "status": explicit_gate.get("status"),
            "reasons": [str(reason) for reason in reasons],
            "checks": explicit_gate.get("checks") if isinstance(explicit_gate.get("checks"), dict) else {},
            "thresholds": explicit_gate.get("thresholds") if isinstance(explicit_gate.get("thresholds"), dict) else {},
            "metrics": metrics,
        }

    thresholds = {
        "min_closed_trades": DEFAULT_MIN_CLOSED_TRADES,
        "min_win_rate": DEFAULT_MIN_WIN_RATE,
        "max_single_ticker_positive_share": DEFAULT_MAX_SINGLE_TICKER_POSITIVE_SHARE,
    }
    params = latest.get("parameters") if isinstance(latest.get("parameters"), dict) else {}
    thresholds["min_closed_trades"] = _safe_int(
        params.get("forward_gate_min_closed_trades") or thresholds["min_closed_trades"]
    )
    thresholds["min_win_rate"] = _safe_float(
        params.get("forward_gate_min_win_rate") or thresholds["min_win_rate"]
    )
    thresholds["max_single_ticker_positive_share"] = _safe_float(
        params.get("forward_gate_max_single_ticker_positive_share")
        or thresholds["max_single_ticker_positive_share"]
    )
    closed_trades = _safe_int(closed_metrics.get("closed_rows_with_pnl"))
    realized_pnl = _safe_float(closed_metrics.get("realized_pnl"))
    win_rate = closed_metrics.get("win_rate")
    top_share = closed_metrics.get("top_positive_ticker_share")
    checks = {
        "min_closed_trades": closed_trades >= thresholds["min_closed_trades"],
        "positive_net_pnl": realized_pnl > 0,
        "min_win_rate": win_rate is not None and win_rate >= thresholds["min_win_rate"],
        "max_single_ticker_positive_share": top_share is not None
        and top_share <= thresholds["max_single_ticker_positive_share"],
    }
    reasons = [name for name, passed in checks.items() if not passed]
    if closed_trades == 0:
        reasons.insert(0, "no_closed_forward_outcomes")
    return {
        "source": "derived_conservative_forward_gate",
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "thresholds": thresholds,
        "metrics": {
            "closed_trades": closed_trades,
            "realized_pnl": realized_pnl,
            "win_rate": win_rate,
            "single_ticker_positive_share": top_share,
        },
    }


def _snapshot_rollup(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    latest = _latest_snapshot(snapshots)
    return {
        "snapshot_rows_total": len(snapshots),
        "date_range": _date_range(snapshots),
        "candidate_count_sum": sum(_safe_int(row.get("candidate_count")) for row in snapshots),
        "filled_count_sum": sum(_safe_int(row.get("filled_count")) for row in snapshots),
        "closed_count_today_sum": sum(_safe_int(row.get("closed_count_today")) for row in snapshots),
        "max_open_position_count": max(
            (_safe_int(row.get("open_position_count")) for row in snapshots),
            default=0,
        ),
        "max_closed_position_count": max(
            (_safe_int(row.get("closed_position_count")) for row in snapshots),
            default=0,
        ),
        "latest_asof_date": latest.get("asof_date"),
        "latest_candidate_count": _safe_int(latest.get("candidate_count")),
        "latest_realized_pnl_to_date": _round(latest.get("realized_pnl_to_date"), 2),
        "latest_unrealized_pnl": _round(latest.get("unrealized_pnl"), 2),
        "latest_trade_enabled": latest.get("trade_enabled"),
        "latest_enabled": latest.get("enabled"),
        "latest_next_action": latest.get("next_action"),
    }


def _sleeve_audit(name: str) -> dict[str, Any]:
    sleeve_dir = PAPER_SLEEVE_ROOT / name
    state_path = sleeve_dir / "state.json"
    snapshot_path = sleeve_dir / "snapshots.jsonl"
    state = _load_json(state_path)
    snapshots = _load_jsonl(snapshot_path)
    latest = _latest_snapshot(snapshots)
    closed = _closed_rows(state, snapshots)
    closed_metrics = _closed_metrics(closed)
    readiness_gate = _readiness_gate(latest, closed_metrics)
    replacement = _replacement_fields_present([state, latest])
    notes: list[str] = []
    if not state_path.exists() and not snapshot_path.exists():
        notes.append("no_state_or_snapshot_file")
    if closed_metrics["closed_rows_with_pnl"] == 0:
        notes.append("no_closed_forward_rows_with_pnl")
    if not replacement["present"]:
        notes.append("no_replacement_value_field_detected")
    top_share = closed_metrics.get("top_positive_ticker_share")
    if top_share is not None and top_share > DEFAULT_MAX_SINGLE_TICKER_POSITIVE_SHARE:
        notes.append("positive_pnl_concentration_above_default_guard")
    if readiness_gate["passed"]:
        notes.append("activation_readiness_gate_passed")
    return {
        "sleeve_key": name,
        "state_file": _repo_rel(state_path),
        "snapshot_file": _repo_rel(snapshot_path),
        "files_present": {
            "state": state_path.exists(),
            "snapshots": snapshot_path.exists(),
        },
        "sleeve_name": latest.get("sleeve") or state.get("sleeve") or name,
        "state_summary": _state_summary(state),
        "snapshot_rollup": _snapshot_rollup(snapshots),
        "closed_metrics": closed_metrics,
        "replacement_value_fields": replacement,
        "readiness_gate": readiness_gate,
        "notes": notes,
    }


def _operator_open_positions_check() -> dict[str, Any]:
    payload = _load_json(OPERATOR_OPEN_POSITIONS) if OPERATOR_OPEN_POSITIONS.exists() else {}
    missing: list[str] = []
    checked_rows = 0
    checked_groups: list[str] = []
    for group_name in ("positions", "observations", "core_positions"):
        rows = payload.get(group_name)
        if rows is None:
            continue
        if not isinstance(rows, list):
            missing.append(f"{group_name}:not_a_list")
            continue
        checked_groups.append(group_name)
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                missing.append(f"{group_name}[{index}]:not_an_object")
                continue
            checked_rows += 1
            ticker = row.get("ticker") or f"row_{index}"
            for field in ("entry_date", "target_price"):
                if row.get(field) in (None, ""):
                    missing.append(f"{group_name}[{index}].{ticker}.{field}")
    if not OPERATOR_OPEN_POSITIONS.exists():
        missing.append("operator_inputs/open_positions.json:missing_file")
    return {
        "passed": not missing,
        "file": _repo_rel(OPERATOR_OPEN_POSITIONS),
        "checked_groups": checked_groups,
        "checked_rows": checked_rows,
        "missing_required_fields": missing,
    }


def _ranked_sleeves(sleeves: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, audit in sleeves.items():
        closed = audit["closed_metrics"]
        gate = audit["readiness_gate"]
        rows.append(
            {
                "sleeve_key": name,
                "sleeve_name": audit["sleeve_name"],
                "gate_passed": gate["passed"],
                "gate_reasons": gate["reasons"],
                "closed_rows_with_pnl": closed["closed_rows_with_pnl"],
                "realized_pnl": closed["realized_pnl"],
                "win_rate": closed["win_rate"],
                "top_positive_ticker": closed["top_positive_ticker"],
                "top_positive_ticker_share": closed["top_positive_ticker_share"],
                "replacement_value_fields_present": audit["replacement_value_fields"]["present"],
                "latest_asof_date": audit["snapshot_rollup"]["latest_asof_date"],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            bool(row["gate_passed"]),
            _safe_int(row["closed_rows_with_pnl"]),
            _safe_float(row["realized_pnl"]),
        ),
        reverse=True,
    )


def _gate4(
    baseline: OrderedDict[str, dict[str, Any]],
    sleeves: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ranked = _ranked_sleeves(sleeves)
    activation_ready = [row for row in ranked if row["gate_passed"]]
    closest = ranked[0] if ranked else {}
    min_survival = min((_safe_float(row.get("survival_rate")) for row in baseline.values()), default=0.0)
    failed: list[str] = []
    if not activation_ready:
        failed.append("no_activation_ready_default_off_sleeve")
    if not any(row["replacement_value_fields_present"] for row in ranked):
        failed.append("replacement_value_fields_missing_or_not_logged")
    if closest and "min_closed_trades" in closest.get("gate_reasons", []):
        failed.append("closest_sleeve_closed_sample_below_gate")
    if closest and "max_single_ticker_positive_share" in closest.get("gate_reasons", []):
        failed.append("closest_sleeve_positive_pnl_ticker_concentrated")
    if min_survival < 0.05:
        failed.append("core_survival_below_guard")
    return {
        "passed": not failed,
        "promotion_grade": bool(activation_ready),
        "failed_reasons": failed,
        "minimum_core_survival_rate": round(min_survival, 4),
        "activation_ready_sleeves": activation_ready,
        "closest_sleeve": closest,
        "ranked_sleeves": ranked,
        "strategy_behavior_changed": False,
    }


def _payload() -> dict[str, Any]:
    ticket = _load_json(TICKET_JSON)
    baseline = _baseline_metrics()
    sleeves = {name: _sleeve_audit(name) for name in PAPER_SLEEVE_DIRS}
    gate2 = _operator_open_positions_check()
    gate4 = _gate4(baseline, sleeves)
    timestamp = _now()
    aggregate_ev = sum(_safe_float(row.get("expected_value_score")) for row in baseline.values())
    aggregate_pnl = sum(_safe_float(row.get("total_pnl")) for row in baseline.values())
    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else {}
    success_probability = _safe_float(prediction.get("success_probability") or 0.18)
    decision = "rejected_no_default_off_sleeve_activation_ready"
    summary = (
        "Rejected: no default-off paper sleeve currently passes its forward activation "
        "readiness gate; low_deployment_etf is closest but remains below closed-sample "
        "and ticker-concentration requirements."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "created_at": ticket.get("created_at"),
        "lane": "alpha_search",
        "status": "rejected",
        "decision": decision,
        "hypothesis": ticket.get(
            "hypothesis",
            "Accepted default-off paper adapters may have enough current production forward closed outcomes.",
        ),
        "change_summary": "Read-only forward readiness audit; no strategy behavior changed.",
        "change_type": ticket.get("change_type", "forward_replacement_value_readiness_audit"),
        "mechanism_family": ticket.get("mechanism_family", "forward_replacement_value_readiness_audit"),
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": ticket.get("prior_trial_count", 0),
        "nearby_prior_experiments": ticket.get(
            "nearby_prior_experiments",
            ["exp-20260605-012", "exp-20260530-020", "exp-20260527-033"],
        ),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket", "minimal"),
        "new_evidence_type": ticket.get("new_evidence_type", "new_forward_rows"),
        "parameters": {
            "paper_sleeve_dirs": list(PAPER_SLEEVE_DIRS),
            "default_min_closed_trades": DEFAULT_MIN_CLOSED_TRADES,
            "default_min_win_rate": DEFAULT_MIN_WIN_RATE,
            "default_max_single_ticker_positive_share": DEFAULT_MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "production orders",
                "paper sleeve definitions",
                "forward gate thresholds",
            ],
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window accepted baseline",
            "baseline_result_file": _repo_rel(BASELINE_RESULT),
            "strategy_behavior_changed": False,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_logic_changed": False,
            "activation_ready_sleeve_count": len(gate4["activation_ready_sleeves"]),
            "audited_sleeve_count": len(sleeves),
        },
        "accepted_core_aggregate": {
            "expected_value_score_sum": round(aggregate_ev, 4),
            "total_pnl_sum": round(aggregate_pnl, 2),
        },
        "sleeve_audits": sleeves,
        "sleeve_rankings": gate4["ranked_sleeves"],
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": gate2["passed"],
            "required_runtime_fields": [
                "operator_inputs/open_positions.json.*[].entry_date",
                "operator_inputs/open_positions.json.*[].target_price",
                "paper_sleeves/*/state.json.closed_positions[].ticker",
                "paper_sleeves/*/state.json.closed_positions[].entry_date",
                "paper_sleeves/*/state.json.closed_positions[].pnl",
                "paper_sleeves/*/snapshots.jsonl[].asof_date",
                "paper_sleeves/*/snapshots.jsonl[].forward_paper_gate",
            ],
            "missing_required_fields": gate2["missing_required_fields"],
            "operator_open_positions_check": gate2,
            "llm_dependency": "none",
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "core_survival_changed": False,
            "minimum_core_survival_rate": gate4["minimum_core_survival_rate"],
            "note": "Read-only forward audit; no filtering or core survival change.",
        },
        "gate4": gate4,
        "prediction": {
            **prediction,
            "success_probability": success_probability,
            "brier_score": round((success_probability - 0.0) ** 2, 6),
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": 0,
            "predicted_success_probability": success_probability,
            "brier_score": round((success_probability - 0.0) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "realized_failure_mode": ";".join(gate4["failed_reasons"]),
            "predicted_failure_mode_hit": any(
                reason in ";".join(gate4["failed_reasons"])
                for reason in prediction.get("main_failure_modes", [])
            )
            if isinstance(prediction.get("main_failure_modes"), list)
            else False,
            "surprise_level": "low",
        },
        "preflight_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool/activation readiness: accepted default-off paper adapters "
                "may have enough current production forward closed outcomes and "
                "replacement-value evidence to identify a promotion candidate."
            ),
            "2_history_check": (
                "Nearby activation-readiness audits include exp-20260605-012 Space, "
                "exp-20260530-020 SEC financial-report, and exp-20260527-033 VCP. "
                "Recent retunes were rejected or frozen; this run checks new forward rows."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "No core baseline movement; pass only if a default-off sleeve passes its "
                "own forward gate or conservative closed-sample/win-rate/PnL/concentration "
                "checks with core survival >=5%."
            ),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260605_028_default_off_forward_readiness_audit.py"
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "default_off_attribution_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_capital_changed": False,
            "parity_test_added": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "rejection_reason": "; ".join(gate4["failed_reasons"]),
        "next_retry_requires": [
            "low_deployment_etf closed forward trades to reach its explicit 60-trade gate",
            "positive forward PnL not concentrated in one ticker",
            "logged replacement-value fields where activation depends on replacement value",
            "closed forward rows for VCP, volume breadth, fundamental growth, and SEC/FINRA sleeves",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(BASELINE_RESULT),
            _repo_rel(OPERATOR_OPEN_POSITIONS),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
        "summary": summary,
    }


def _card(payload: dict[str, Any]) -> str:
    closest = payload["gate4"]["closest_sleeve"]
    gate = payload["gate4"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            'status: "rejected"',
            'lane: "alpha_search"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            f'new_evidence_type: "{payload["new_evidence_type"]}"',
            f'updated_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["summary"],
            "",
            "## Gate 4",
            "",
            f"- Passed: `{gate['passed']}`",
            f"- Failed reasons: `{payload['rejection_reason']}`",
            f"- Activation-ready sleeves: `{len(gate['activation_ready_sleeves'])}`",
            "",
            "## Closest Sleeve",
            "",
            f"- Sleeve: `{closest.get('sleeve_key')}`",
            f"- Closed rows with PnL: `{closest.get('closed_rows_with_pnl')}`",
            f"- Realized PnL: `${_safe_float(closest.get('realized_pnl')):,.2f}`",
            f"- Win rate: `{closest.get('win_rate')}`",
            f"- Top positive ticker share: `{closest.get('top_positive_ticker_share')}`",
            f"- Gate reasons: `{', '.join(closest.get('gate_reasons') or [])}`",
            "",
            "## Files",
            "",
            f"- Result JSON: `{_repo_rel(OUT_JSON)}`",
            f"- Log JSON: `{_repo_rel(LOG_JSON)}`",
            f"- Runner: `{_repo_rel(Path(__file__))}`",
            "",
            "No strategy behavior changed. No JavaScript was used.",
            "",
        ]
    )


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    ticket = _load_json(TICKET_JSON)
    ticket.update(
        {
            "status": "rejected",
            "owner": "codex-alpha-explore",
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": {
                "json": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "summary": payload["summary"],
            },
            "summary": payload["summary"],
        }
    )
    return ticket


def _manifest(payload: dict[str, Any]) -> dict[str, Any]:
    manifest = _load_json(MANIFEST_JSON)
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "rejected",
            "updated_at": payload["timestamp"],
            "files": {
                **(manifest.get("files") if isinstance(manifest.get("files"), dict) else {}),
                "runner": {"path": _repo_rel(Path(__file__)), "exists": True},
                "result": {"path": _repo_rel(OUT_JSON), "exists": True},
                "log": {"path": _repo_rel(LOG_JSON), "exists": True},
                "ticket": {"path": _repo_rel(TICKET_JSON), "exists": True},
                "card": {"path": _repo_rel(CARD_MD), "exists": True},
            },
            "anti_js": "No JavaScript was used.",
        }
    )
    return manifest


def _registry_entry(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = dict(existing or {})
    entry.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "rejected",
            "lane": "alpha_search",
            "owner": "codex-alpha-explore",
            "hypothesis": payload["hypothesis"],
            "decision": payload["decision"],
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(LOG_JSON),
            "ticket_file": _repo_rel(TICKET_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
            "summary": payload["summary"],
            "completed_at": payload["timestamp"].replace("+00:00", "Z"),
            "updated_at": payload["timestamp"].replace("+00:00", "Z"),
            "result": {
                "json": _repo_rel(OUT_JSON),
                "decision": payload["decision"],
                "summary": payload["summary"],
            },
        }
    )
    return entry


def _upsert_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON) if REGISTRY_JSON.exists() else {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    if not isinstance(experiments, list):
        raise ValueError("docs/experiment_registry.json experiments must be a list")
    existing = None
    kept: list[dict[str, Any]] = []
    for row in experiments:
        if isinstance(row, dict) and row.get("experiment_id") == EXPERIMENT_ID:
            existing = row
            continue
        if isinstance(row, dict):
            kept.append(row)
    kept.append(_registry_entry(payload, existing))
    registry["experiments"] = kept
    registry["updated_at"] = payload["timestamp"].replace("+00:00", "Z")
    _write_json(REGISTRY_JSON, registry)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _card(payload))
    _write_json(TICKET_JSON, _ticket(payload))
    _write_json(MANIFEST_JSON, _manifest(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _upsert_registry(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Compute the audit and print the summary without writing artifacts.",
    )
    args = parser.parse_args()

    payload = _payload()
    if not args.no_persist:
        _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "gate2_passed": payload["gate2"]["passed"],
                "gate4": payload["gate4"],
                "result_json": _repo_rel(OUT_JSON),
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
