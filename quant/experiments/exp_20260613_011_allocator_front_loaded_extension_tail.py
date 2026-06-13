"""exp-20260613-011: accepted allocator front-loaded extension tail scout.

Alpha search, replay-only. The fixed hypothesis is that accepted allocator
trades whose last 5 trading days already consumed most of their 20-day trend
are front-loaded extension tails. Before = accepted allocator execution
envelope v2. After = the same envelope-constrained trades with that fixed tail
bucket removed. No shared helper, production runner, live/default orders,
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed.
No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict
from datetime import timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402


EXPERIMENT_ID = "exp-20260613-011"
STEM = "allocator_front_loaded_extension_tail"
CHANGED_VARIABLE = "accepted_allocator_front_loaded_extension_tail_exclusion_v1"
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_ID.replace('-', '_')}_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

# Fixed, predeclared tail-state classifier. It is intentionally coarse: a trade
# is a tail only when the 20-day move is meaningful and the last 5 days explain
# most of that move.
MIN_FRONT_LOADED_RET20 = 0.10
MIN_FRONT_LOADED_RET5 = 0.05
MIN_RET5_SHARE_OF_RET20 = 0.65
MIN_AFTER_TOTAL_TRADES = 20
MIN_SURVIVAL_RATE = 0.05
MIN_REMOVED_TRADES_FOR_EVIDENCE = 10
MAX_DRAWDOWN_WORSE = 0.005

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.08,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "tail_bucket_contains_winners",
        "filter_does_not_bind",
        "window_regression",
        "allocator_already_handles_source_quality",
    ],
    "confidence_reason": (
        "Playbook calls for tail-state classifier work, but nearby allocator and "
        "microstructure retunes mostly failed and the accepted envelope already "
        "arbitrates source quality. This is a fixed diagnostic bucket, not a sweep."
    ),
    "recorded_at": "2026-06-13T07:09:27Z",
}


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


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


def _float_metric(metrics: dict[str, Any], key: str) -> float:
    return float(metrics.get(key) or 0.0)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _date_index(snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    return {
        ticker: {str(row.get("Date") or "")[:10]: idx for idx, row in enumerate(rows)}
        for ticker, rows in snapshot.items()
    }


def _load_window_snapshot_immutable(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(days=100)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse = Path(framework.WAREHOUSE).resolve().as_posix()
    uri = f"file:{warehouse}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _tail_state_for_trade(
    trade: dict[str, Any],
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None:
        entry_date = str(trade.get("entry_date") or "")[:10]
        entry_idx = indices.get(ticker, {}).get(entry_date)
        if entry_idx is not None and entry_idx > 0:
            idx = entry_idx - 1
            signal_date = str(rows[idx].get("Date") or signal_date)[:10]
            spy_idx = indices.get("SPY", {}).get(signal_date)
    ret5 = framework._ret(rows, idx, 5) if idx is not None else None
    ret20 = framework._ret(rows, idx, 20) if idx is not None else None
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20) if spy_idx is not None else None
    share = (ret5 / ret20) if ret5 is not None and ret20 and ret20 > 0 else None
    front_loaded = (
        ret5 is not None
        and ret20 is not None
        and share is not None
        and ret20 >= MIN_FRONT_LOADED_RET20
        and ret5 >= MIN_FRONT_LOADED_RET5
        and share >= MIN_RET5_SHARE_OF_RET20
    )
    return {
        "signal_date_used_for_tail_state": signal_date or None,
        "candidate_ret5": _round(ret5),
        "candidate_ret20": _round(ret20),
        "candidate_spy_ret20": _round(spy_ret20),
        "candidate_ret20_excess_spy": _round(ret20 - spy_ret20)
        if ret20 is not None and spy_ret20 is not None
        else None,
        "candidate_ret5_share_of_ret20": _round(share),
        "front_loaded_extension_tail": bool(front_loaded),
        "tail_rule": (
            f"ret20>={MIN_FRONT_LOADED_RET20}, ret5>={MIN_FRONT_LOADED_RET5}, "
            f"ret5/ret20>={MIN_RET5_SHARE_OF_RET20}"
        ),
    }


def _apply_front_loaded_tail_filter(
    trades: list[dict[str, Any]],
    *,
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    indices = _date_index(snapshot)
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    missing_tail_state = 0
    removed_pnl = 0.0
    removed_counts: Counter[str] = Counter()
    for trade in trades:
        tail_state = _tail_state_for_trade(trade, snapshot=snapshot, indices=indices)
        annotated = {
            **trade,
            "tail_state": tail_state,
            "tail_filter_rule_version": CHANGED_VARIABLE,
        }
        if tail_state.get("candidate_ret5") is None or tail_state.get("candidate_ret20") is None:
            missing_tail_state += 1
        if tail_state["front_loaded_extension_tail"]:
            removed_pnl += float(trade.get("pnl") or 0.0)
            removed_counts[str(trade.get("source_family") or "unknown")] += 1
            removed.append(
                {**annotated, "tail_filter_skip_reason": "front_loaded_extension_tail"}
            )
        else:
            kept.append(annotated)
    audit = {
        "rule_version": CHANGED_VARIABLE,
        "input_trade_count": len(trades),
        "kept_trade_count": len(kept),
        "removed_trade_count": len(removed),
        "removed_pnl": round(removed_pnl, 2),
        "missing_tail_state_count": missing_tail_state,
        "removed_source_family_counts": dict(removed_counts),
        "parameters": {
            "min_front_loaded_ret20": MIN_FRONT_LOADED_RET20,
            "min_front_loaded_ret5": MIN_FRONT_LOADED_RET5,
            "min_ret5_share_of_ret20": MIN_RET5_SHARE_OF_RET20,
        },
    }
    return kept, removed, audit


def _dependency_audit(trades: list[dict[str, Any]]) -> dict[str, Any]:
    missing_entry = [
        str(row.get("ticker") or "<unknown>") for row in trades if not row.get("entry_date")
    ]
    missing_exit_price = [
        str(row.get("ticker") or "<unknown>") for row in trades if row.get("exit_price") in (None, "")
    ]
    missing_target_price = [
        str(row.get("ticker") or "<unknown>")
        for row in trades
        if row.get("target_price") in (None, "")
    ]
    return {
        "entry_date_present": not missing_entry,
        "exit_price_present": not missing_exit_price,
        "target_price_dependency": (
            "not used by this default-off paper sleeve; overlay depends on "
            "entry_date, entry_price, exit_date, exit_price, and pnl"
        ),
        "target_price_absent_count": len(missing_target_price),
        "missing_entry_date_tickers": missing_entry[:25],
        "missing_exit_price_tickers": missing_exit_price[:25],
        "passed": not missing_entry and not missing_exit_price,
    }


def _window_replay(label: str, cfg: dict[str, str]) -> dict[str, Any]:
    universe = sorted(framework.get_universe())
    baseline = framework.shadow._run_baseline(universe, cfg)
    core_metrics = framework.overlay_helper._metrics(baseline)
    core_entries = framework.shadow._baseline_entries(baseline)
    sector_entries = framework._load_sector_entries()
    snapshot = _load_window_snapshot_immutable(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    trades, allocator_audit = allocator.build_accepted_helper_source_priority_allocator_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries,
        windows=OrderedDict([(label, dict(cfg))]),
        candidate_universe=sector_entries,
        sector_entries=sector_entries,
    )
    envelope_kept, envelope_skipped, envelope_audit = allocator.apply_execution_envelope_to_trades(
        trades
    )
    tail_kept, tail_removed, tail_audit = _apply_front_loaded_tail_filter(
        envelope_kept,
        snapshot=snapshot,
    )
    before_overlay = framework.sleeve._overlay_from_paper_trades(baseline, envelope_kept)
    after_overlay = framework.sleeve._overlay_from_paper_trades(baseline, tail_kept)
    before_metrics = framework.overlay_helper._metrics_with_overlay(baseline, before_overlay)
    after_metrics = framework.overlay_helper._metrics_with_overlay(baseline, after_overlay)
    signals_generated = len(trades)
    signals_survived_envelope = len(envelope_kept)
    signals_survived_tail = len(tail_kept)
    survival_rate = (
        signals_survived_tail / signals_generated if signals_generated else 0.0
    )
    return {
        "label": label,
        "window": dict(cfg),
        "core_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_after_vs_before": framework.overlay_helper._delta(
            after_metrics,
            before_metrics,
        ),
        "before_ev_delta_vs_core": round(
            _float_metric(before_metrics, "expected_value_score")
            - _float_metric(core_metrics, "expected_value_score"),
            6,
        ),
        "after_ev_delta_vs_core": round(
            _float_metric(after_metrics, "expected_value_score")
            - _float_metric(core_metrics, "expected_value_score"),
            6,
        ),
        "before_pnl_delta_vs_core": round(
            _float_metric(before_metrics, "total_pnl")
            - _float_metric(core_metrics, "total_pnl"),
            2,
        ),
        "after_pnl_delta_vs_core": round(
            _float_metric(after_metrics, "total_pnl")
            - _float_metric(core_metrics, "total_pnl"),
            2,
        ),
        "signals_generated": signals_generated,
        "signals_survived_envelope": signals_survived_envelope,
        "signals_survived_after_tail_filter": signals_survived_tail,
        "survival_rate_after_tail_filter": round(survival_rate, 6),
        "unconstrained_trade_count": len(trades),
        "envelope_kept_trade_count": len(envelope_kept),
        "tail_kept_trade_count": len(tail_kept),
        "tail_removed_trade_count": len(tail_removed),
        "allocator_audit": allocator_audit,
        "envelope_audit": framework._safe(envelope_audit),
        "tail_filter_audit": framework._safe(tail_audit),
        "gate2_dependency_audit": _dependency_audit(tail_kept),
        "tail_removed_sample": framework._safe(tail_removed[:50]),
        "envelope_skipped_sample": framework._safe(envelope_skipped[:50]),
    }


def _gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failed: list[str] = []
    before_ev_sum = sum(_float_metric(row["before_metrics"], "expected_value_score") for row in rows)
    after_ev_sum = sum(_float_metric(row["after_metrics"], "expected_value_score") for row in rows)
    before_pnl_sum = sum(_float_metric(row["before_metrics"], "total_pnl") for row in rows)
    after_pnl_sum = sum(_float_metric(row["after_metrics"], "total_pnl") for row in rows)
    removed_total = sum(int(row["tail_removed_trade_count"]) for row in rows)
    after_trade_total = sum(int(row["tail_kept_trade_count"]) for row in rows)
    for row in rows:
        label = row["label"]
        ev_delta = (
            _float_metric(row["after_metrics"], "expected_value_score")
            - _float_metric(row["before_metrics"], "expected_value_score")
        )
        pnl_delta = (
            _float_metric(row["after_metrics"], "total_pnl")
            - _float_metric(row["before_metrics"], "total_pnl")
        )
        dd_delta = (
            _float_metric(row["after_metrics"], "max_drawdown_pct")
            - _float_metric(row["before_metrics"], "max_drawdown_pct")
        )
        if ev_delta < 0:
            failed.append("window_ev_regression:" + label)
        if pnl_delta < 0:
            failed.append("window_pnl_regression:" + label)
        if dd_delta > MAX_DRAWDOWN_WORSE:
            failed.append("window_drawdown_worse:" + label)
        if row["survival_rate_after_tail_filter"] < MIN_SURVIVAL_RATE:
            failed.append("survival_rate_below_min:" + label)
        if not row["gate2_dependency_audit"]["passed"]:
            failed.append("dependency_audit_failed:" + label)
    if after_ev_sum <= before_ev_sum:
        failed.append("aggregate_ev_not_improved")
    if after_pnl_sum <= before_pnl_sum:
        failed.append("aggregate_pnl_not_improved")
    if removed_total < MIN_REMOVED_TRADES_FOR_EVIDENCE:
        failed.append("tail_removed_count_too_thin")
    if after_trade_total < MIN_AFTER_TOTAL_TRADES:
        failed.append("after_trade_count_too_thin")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "observed_positive_private_tail_state_lead_requires_shared_helper"
            if passed
            else "rejected_front_loaded_extension_tail_filter"
        ),
        "failed_reasons": failed,
        "before_expected_value_score_sum": round(before_ev_sum, 6),
        "after_expected_value_score_sum": round(after_ev_sum, 6),
        "expected_value_score_delta": round(after_ev_sum - before_ev_sum, 6),
        "before_total_pnl_sum": round(before_pnl_sum, 2),
        "after_total_pnl_sum": round(after_pnl_sum, 2),
        "total_pnl_delta": round(after_pnl_sum - before_pnl_sum, 2),
        "tail_removed_trade_count": removed_total,
        "after_trade_count": after_trade_total,
        "acceptance_rule": (
            "after improves aggregate EV and PnL versus accepted allocator envelope "
            "v2, no canonical-window EV/PnL regression, target removal count >= 10, "
            "after trade count >= 20, survival >= 5%, and any promotion requires a "
            "shared helper plus parity."
        ),
    }


def _calibration(gate: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate["passed"] else 0
    return {
        "actual_decision": gate["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": PREDICTION["success_probability"],
        "brier_score": round(
            (PREDICTION["success_probability"] - float(actual_success)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": gate["expected_value_score_delta"],
        "ev_prediction_error": round(
            gate["expected_value_score_delta"] - PREDICTION["expected_ev_delta"],
            6,
        ),
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": gate["total_pnl_delta"],
        "pnl_prediction_error": round(
            gate["total_pnl_delta"] - PREDICTION["expected_pnl_delta"],
            2,
        ),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_modes": gate["failed_reasons"],
        "predicted_failure_mode_hit": any(
            reason.startswith(("window_", "tail_", "aggregate_"))
            for reason in gate["failed_reasons"]
        ),
    }


def build_payload() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] accepted allocator envelope v2 vs front-loaded extension tail filter")
        rows.append(_window_replay(label, cfg))
    gate = _gate(rows)
    calibration = _calibration(gate)
    status = "observed_only" if gate["passed"] else "rejected"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": framework._utc_now(),
        "lane": "alpha_search",
        "status": status,
        "accepted_alpha": False,
        "decision": gate["decision"],
        "change_type": "risk_allocation_candidate_pool_filter",
        "mechanism_family": "tail_state_classifier_for_momentum_candidate_pools",
        "trial_family": "accepted_allocator_tail_state_classifier",
        "trial_variant_id": "front_loaded_extension_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Accepted allocator selected trades where the last 5 trading days "
            "already consume most of the 20-day trend are front-loaded extension "
            "tails; excluding that fixed bucket should improve allocator EV by "
            "avoiding gap-chase decay without changing accepted source ordering."
        ),
        "pre_run_history_check": {
            "excluded_nearby_repeats": [
                "PEAD variants rejected or too thin: exp-20260607-025, exp-20260612-008, exp-20260612-011",
                "Form4 variants too concentrated/thin: exp-20260530-011, exp-20260609-025",
                "13F latest ingestion is measurement repair only and not PIT for canonical windows: exp-20260613-007",
                "allocator source-score/microstructure retunes saturated or rejected: exp-20260613-006, exp-20260613-009",
                "accepted allocator execution envelope baseline: exp-20260612-024",
            ],
            "why_this_is_not_a_repeat": (
                "This run tests a fixed tail-state classifier on the accepted "
                "envelope-constrained trade stream, not source priority, source score, "
                "daily slots, notional, hold length, or calendar timing."
            ),
        },
        "parameters": {
            "min_front_loaded_ret20": MIN_FRONT_LOADED_RET20,
            "min_front_loaded_ret5": MIN_FRONT_LOADED_RET5,
            "min_ret5_share_of_ret20": MIN_RET5_SHARE_OF_RET20,
            "baseline_artifact": "data/experiments/exp-20260612-024/exp_20260612_024_allocator_envelope_v2_equity_basis.json",
        },
        "gate1_baseline": {
            "protocol": "docs/backtesting.md canonical three windows",
            "before_definition": "accepted allocator execution envelope v2",
            "baseline_artifact": "data/experiments/exp-20260612-024/exp_20260612_024_allocator_envelope_v2_equity_basis.json",
        },
        "gate2_dependency_surface": {
            "fields_used": [
                "ticker",
                "signal_date",
                "entry_date",
                "entry_price",
                "exit_date",
                "exit_price",
                "pnl",
                "OHLCV close history at signal_date",
                "SPY close history at signal_date",
            ],
            "target_price_note": (
                "target_price is absent from accepted allocator paper trades and is "
                "not a dependency of this replay-only policy; entry_date and exit "
                "prices are validated per window."
            ),
        },
        "gate3_signal_survival": [
            {
                "window": row["label"],
                "signals_generated": row["signals_generated"],
                "signals_survived_envelope": row["signals_survived_envelope"],
                "signals_survived_after_tail_filter": row[
                    "signals_survived_after_tail_filter"
                ],
                "survival_rate_after_tail_filter": row["survival_rate_after_tail_filter"],
            }
            for row in rows
        ],
        "gate4": gate,
        "windows": framework._safe(rows),
        "prediction": {
            **PREDICTION,
            "actual_success": calibration["actual_success"],
            "brier_score": calibration["brier_score"],
        },
        "calibration": calibration,
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "shared_policy_changed": False,
            "replay_only": True,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "live_realism_evaluated": True,
            "live_ready": False,
            "production_consistency_note": (
                "No production or shared helper behavior changed. A positive result "
                "would remain a private lead until the same classifier is promoted "
                "into a shared default-off helper with daily snapshot parity."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "filled after execution; populated once gate is known"
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep ret5, ret20, ret5/ret20, hold length, source rank, "
                "daily slots, notional, or envelope thresholds on the frozen windows "
                "to rescue this bucket."
            ),
            "new_evidence_required": (
                "Use genuinely new tail-state features such as breadth support, "
                "same-day displacement type, or forward rows; otherwise stop near "
                "allocator tail-threshold tuning."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _fill_reflection(payload: dict[str, Any]) -> None:
    gate = payload["gate4"]
    if gate["passed"]:
        payload["post_run_reflection"]["why_result_happened"] = (
            "The fixed extension-tail bucket removed enough negative or low-value "
            "allocator-envelope trades to improve every canonical window, but it is "
            "still only a private replay lead because production/shared helper parity "
            "was intentionally not changed in this scout."
        )
        return
    reasons = ", ".join(gate["failed_reasons"]) or "unknown"
    payload["post_run_reflection"]["why_result_happened"] = (
        "The front-loaded extension bucket is not a clean decay state for the "
        f"accepted allocator envelope. Failure reasons: {reasons}. The accepted "
        "source-priority allocator already selects several momentum/relief mechanisms "
        "where recent strength can be the edge rather than a chase signal."
    )


def _build_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Accepted Allocator Front-Loaded Extension Tail",
        "",
        f"Status: {payload['status']} / {payload['decision']}",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Kept/Before | Removed | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["windows"]:
        before = row["before_metrics"]
        after = row["after_metrics"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | {bpnl:.2f} | {apnl:.2f} | {dpnl:.2f} | {kept}/{before_n} | {removed} | {survival:.2%} |".format(
                label=row["label"],
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(after["expected_value_score"]) - float(before["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(after["total_pnl"]) - float(before["total_pnl"]),
                kept=int(row["tail_kept_trade_count"]),
                before_n=int(row["envelope_kept_trade_count"]),
                removed=int(row["tail_removed_trade_count"]),
                survival=float(row["survival_rate_after_tail_filter"]),
            )
        )
    gate = payload["gate4"]
    lines.extend(
        [
            "",
            f"- Aggregate EV delta: {gate['expected_value_score_delta']}",
            f"- Aggregate PnL delta: {gate['total_pnl_delta']}",
            f"- Failed reasons: {', '.join(gate['failed_reasons']) or 'none'}",
            "",
            payload["production_impact"]["production_consistency_note"],
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "updated_at": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "files": [
            {"path": _repo_rel(Path(__file__)), "sha256": _sha256(Path(__file__))},
            {"path": _repo_rel(OUT_JSON), "sha256": _sha256(OUT_JSON)},
            {"path": _repo_rel(LOG_JSON), "sha256": _sha256(LOG_JSON)},
            {"path": _repo_rel(CARD_MD), "sha256": _sha256(CARD_MD)},
        ],
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    _fill_reflection(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _write_manifest(payload)
    gate = payload["gate4"]
    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "implementation_mode": "private_replay_scout",
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "nearby_prior_experiments": [
            "exp-20260612-024",
            "exp-20260613-006",
            "exp-20260613-009",
            "exp-20260611-005",
            "exp-20260611-007",
        ],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "gate1_baseline": payload["gate1_baseline"],
        "gate2_dependency_surface": payload["gate2_dependency_surface"],
        "gate3_signal_survival": payload["gate3_signal_survival"],
        "gate4": gate,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "gate4": gate,
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "decision": payload["decision"],
        "summary": (
            "Front-loaded extension tail filter over accepted allocator envelope "
            f"{payload['status']}; EV delta {gate['expected_value_score_delta']}, "
            f"PnL delta {gate['total_pnl_delta']}."
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card_file": _repo_rel(CARD_MD),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    persist(payload)
    print(json.dumps(_safe(payload["gate4"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
