"""exp-20260614-010 accepted allocator market-breadth tail readout.

Alpha search, read-only replay attribution. The fixed hypothesis is that
accepted allocator rows selected without broad market participation are a
tail-state bucket. Before = accepted allocator execution envelope v2. Virtual
after = the same closed paper rows with only the predeclared weak-breadth
bucket removed. No production/shared helper, live/default orders, ranking,
sizing, exits, LLM/news path, or watchlist behavior is changed.

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


EXPERIMENT_ID = "exp-20260614-010"
STEM = "allocator_market_breadth_tail_readout"
OWNER = "codex-alpha-search"
TRIAL_FAMILY = "accepted_allocator_tail_state_classifier"
TRIAL_VARIANT_ID = "accepted_allocator_market_breadth_support_bucket_readout_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{EXPERIMENT_ID.replace('-', '_')}_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_BREADTH_TICKERS = 150
MIN_STRONG_UP20_FRACTION = 0.55
MIN_STRONG_ABOVE_SMA20_FRACTION = 0.55
MAX_WEAK_UP20_FRACTION = 0.45
MAX_WEAK_ABOVE_SMA20_FRACTION = 0.45
MAX_WEAK_SPY_RET20 = 0.0

MIN_VIRTUAL_AFTER_TRADES = 20
MIN_BUCKET_TRADES_FOR_EVIDENCE = 8
MIN_TOTAL_ROWS_FOR_READOUT = 20
MAX_DRAWDOWN_WORSE = 0.005

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "breadth_bucket_does_not_separate",
        "source_family_mix_explains_result",
        "old_thin_tail_dominates",
        "no_promotion_from_read_only",
    ],
    "confidence_reason": (
        "The playbook asks for tail-state classifier field-building, while "
        "exp-20260613-011 rejected a nearby front-loaded extension filter. This "
        "fixed readout uses a distinct market-participation field and keeps all "
        "strategy behavior unchanged."
    ),
    "recorded_at": "2026-06-14T08:10:07Z",
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
    start = framework._parse_date(cfg["start"]) - timedelta(days=120)
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


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        value = framework._value(row, "Close")
        if value is None:
            return None
        values.append(float(value))
    return sum(values) / len(values)


def _breadth_context(
    signal_date: str,
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    eligible_tickers: set[str],
) -> dict[str, Any]:
    up20 = 0
    above_sma20 = 0
    valid = 0
    for ticker in sorted(eligible_tickers):
        rows = snapshot.get(ticker)
        idx = indices.get(ticker, {}).get(signal_date)
        if not rows or idx is None:
            continue
        ret20 = framework._ret(rows, idx, 20)
        sma20 = _sma(rows, idx, 20)
        close = framework._value(rows[idx], "Close") if idx < len(rows) else None
        if ret20 is None or sma20 is None or close is None:
            continue
        valid += 1
        if ret20 > 0:
            up20 += 1
        if close >= sma20:
            above_sma20 += 1

    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20) if spy_idx is not None else None
    qqq_ret20 = framework._ret(qqq_rows, qqq_idx, 20) if qqq_idx is not None else None
    up20_fraction = (up20 / valid) if valid else None
    above_sma20_fraction = (above_sma20 / valid) if valid else None

    if valid < MIN_BREADTH_TICKERS:
        bucket = "insufficient_breadth_coverage"
    elif (
        up20_fraction is not None
        and above_sma20_fraction is not None
        and up20_fraction >= MIN_STRONG_UP20_FRACTION
        and above_sma20_fraction >= MIN_STRONG_ABOVE_SMA20_FRACTION
        and (spy_ret20 or 0.0) >= 0.0
    ):
        bucket = "broad_market_support"
    elif (
        up20_fraction is not None
        and above_sma20_fraction is not None
        and (
            up20_fraction <= MAX_WEAK_UP20_FRACTION
            or above_sma20_fraction <= MAX_WEAK_ABOVE_SMA20_FRACTION
            or (spy_ret20 is not None and spy_ret20 <= MAX_WEAK_SPY_RET20)
        )
    ):
        bucket = "weak_or_narrow_market_support"
    else:
        bucket = "mixed_market_support"

    return {
        "signal_date": signal_date,
        "breadth_bucket": bucket,
        "valid_breadth_tickers": valid,
        "up20_fraction": _round(up20_fraction),
        "above_sma20_fraction": _round(above_sma20_fraction),
        "spy_ret20": _round(spy_ret20),
        "qqq_ret20": _round(qqq_ret20),
        "rule_version": CHANGED_VARIABLE,
    }


def _signal_date_for_trade(
    trade: dict[str, Any],
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
) -> str | None:
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    if signal_date:
        return signal_date
    ticker = str(trade.get("ticker") or "").upper()
    rows = snapshot.get(ticker) or []
    entry_date = str(trade.get("entry_date") or "")[:10]
    entry_idx = indices.get(ticker, {}).get(entry_date)
    if entry_idx is not None and entry_idx > 0 and entry_idx - 1 < len(rows):
        return str(rows[entry_idx - 1].get("Date") or "")[:10] or None
    return None


def _annotate_breadth(
    trades: list[dict[str, Any]],
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    eligible_tickers: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = _date_index(snapshot)
    context_cache: dict[str, dict[str, Any]] = {}
    annotated: list[dict[str, Any]] = []
    missing_signal_date = 0
    for trade in trades:
        signal_date = _signal_date_for_trade(trade, snapshot=snapshot, indices=indices)
        if not signal_date:
            missing_signal_date += 1
            context = {
                "breadth_bucket": "missing_signal_date",
                "rule_version": CHANGED_VARIABLE,
            }
        else:
            if signal_date not in context_cache:
                context_cache[signal_date] = _breadth_context(
                    signal_date,
                    snapshot=snapshot,
                    indices=indices,
                    eligible_tickers=eligible_tickers,
                )
            context = context_cache[signal_date]
        annotated.append(
            {
                **trade,
                "market_breadth_tail_state": context,
                "tail_state_rule_version": CHANGED_VARIABLE,
            }
        )
    audit = {
        "input_trade_count": len(trades),
        "missing_signal_date_count": missing_signal_date,
        "unique_signal_dates": len(context_cache),
        "bucket_counts": dict(
            Counter(
                str((row.get("market_breadth_tail_state") or {}).get("breadth_bucket"))
                for row in annotated
            )
        ),
    }
    return annotated, audit


def _bucket_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [float(row.get("pnl") or 0.0) for row in rows]
    wins = [value for value in pnl_values if value > 0]
    losses = [value for value in pnl_values if value <= 0]
    total_pnl = sum(pnl_values)
    return {
        "trade_count": len(rows),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": round(total_pnl / len(rows), 2) if rows else None,
        "win_rate": round(len(wins) / len(rows), 6) if rows else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "source_counts": dict(Counter(str(row.get("source_family") or "unknown") for row in rows)),
        "sample": _safe(rows[:25]),
    }


def _split_virtual_after(
    annotated: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    removed: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in annotated:
        bucket = str((row.get("market_breadth_tail_state") or {}).get("breadth_bucket"))
        buckets.setdefault(bucket, []).append(row)
        if bucket == "weak_or_narrow_market_support":
            removed.append({**row, "virtual_filter_reason": bucket})
        else:
            kept.append(row)
    return kept, removed, {bucket: _bucket_stats(rows) for bucket, rows in buckets.items()}


def _dependency_audit(trades: list[dict[str, Any]]) -> dict[str, Any]:
    missing_entry = [
        str(row.get("ticker") or "<unknown>") for row in trades if not row.get("entry_date")
    ]
    missing_exit_price = [
        str(row.get("ticker") or "<unknown>")
        for row in trades
        if row.get("exit_price") in (None, "")
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
            "not used by this default-off paper attribution; this readout depends "
            "on entry_date, entry_price, exit_date, exit_price, pnl, and signal-date OHLCV"
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
    annotated, breadth_audit = _annotate_breadth(
        envelope_kept,
        snapshot=snapshot,
        eligible_tickers=set(sector_entries),
    )
    virtual_kept, virtual_removed, bucket_stats = _split_virtual_after(annotated)
    before_overlay = framework.sleeve._overlay_from_paper_trades(baseline, envelope_kept)
    after_overlay = framework.sleeve._overlay_from_paper_trades(baseline, virtual_kept)
    before_metrics = framework.overlay_helper._metrics_with_overlay(baseline, before_overlay)
    after_metrics = framework.overlay_helper._metrics_with_overlay(baseline, after_overlay)
    signals_generated = len(trades)
    signals_survived_envelope = len(envelope_kept)
    signals_survived_virtual = len(virtual_kept)
    survival_rate = (
        signals_survived_virtual / signals_generated if signals_generated else 0.0
    )
    return {
        "label": label,
        "window": dict(cfg),
        "core_metrics": core_metrics,
        "before_metrics": before_metrics,
        "virtual_after_metrics": after_metrics,
        "delta_virtual_after_vs_before": framework.overlay_helper._delta(
            after_metrics,
            before_metrics,
        ),
        "before_ev_delta_vs_core": round(
            _float_metric(before_metrics, "expected_value_score")
            - _float_metric(core_metrics, "expected_value_score"),
            6,
        ),
        "virtual_after_ev_delta_vs_core": round(
            _float_metric(after_metrics, "expected_value_score")
            - _float_metric(core_metrics, "expected_value_score"),
            6,
        ),
        "before_pnl_delta_vs_core": round(
            _float_metric(before_metrics, "total_pnl")
            - _float_metric(core_metrics, "total_pnl"),
            2,
        ),
        "virtual_after_pnl_delta_vs_core": round(
            _float_metric(after_metrics, "total_pnl")
            - _float_metric(core_metrics, "total_pnl"),
            2,
        ),
        "signals_generated": signals_generated,
        "signals_survived_envelope": signals_survived_envelope,
        "signals_survived_virtual_after": signals_survived_virtual,
        "survival_rate_virtual_after": round(survival_rate, 6),
        "unconstrained_trade_count": len(trades),
        "envelope_kept_trade_count": len(envelope_kept),
        "virtual_after_trade_count": len(virtual_kept),
        "weak_breadth_removed_trade_count": len(virtual_removed),
        "allocator_audit": allocator_audit,
        "envelope_audit": _safe(envelope_audit),
        "breadth_audit": _safe(breadth_audit),
        "bucket_stats": _safe(bucket_stats),
        "gate2_dependency_audit": _dependency_audit(annotated),
        "weak_breadth_removed_sample": _safe(virtual_removed[:50]),
        "envelope_skipped_sample": _safe(envelope_skipped[:50]),
    }


def _gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failed: list[str] = []
    before_ev_sum = sum(_float_metric(row["before_metrics"], "expected_value_score") for row in rows)
    after_ev_sum = sum(_float_metric(row["virtual_after_metrics"], "expected_value_score") for row in rows)
    before_pnl_sum = sum(_float_metric(row["before_metrics"], "total_pnl") for row in rows)
    after_pnl_sum = sum(_float_metric(row["virtual_after_metrics"], "total_pnl") for row in rows)
    removed_total = sum(int(row["weak_breadth_removed_trade_count"]) for row in rows)
    before_total = sum(int(row["envelope_kept_trade_count"]) for row in rows)
    after_total = sum(int(row["virtual_after_trade_count"]) for row in rows)
    windows_ev_improved = 0
    windows_ev_regressed = 0
    windows_pnl_improved = 0
    windows_pnl_regressed = 0
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for row in rows:
        label = row["label"]
        ev_delta = (
            _float_metric(row["virtual_after_metrics"], "expected_value_score")
            - _float_metric(row["before_metrics"], "expected_value_score")
        )
        pnl_delta = (
            _float_metric(row["virtual_after_metrics"], "total_pnl")
            - _float_metric(row["before_metrics"], "total_pnl")
        )
        dd_delta = (
            _float_metric(row["virtual_after_metrics"], "max_drawdown_pct")
            - _float_metric(row["before_metrics"], "max_drawdown_pct")
        )
        if ev_delta > 0:
            windows_ev_improved += 1
        if ev_delta < 0:
            windows_ev_regressed += 1
            failed.append("window_ev_regression:" + label)
        if pnl_delta > 0:
            windows_pnl_improved += 1
        if pnl_delta < 0:
            windows_pnl_regressed += 1
            failed.append("window_pnl_regression:" + label)
        if dd_delta > MAX_DRAWDOWN_WORSE:
            failed.append("window_drawdown_worse:" + label)
        if row["survival_rate_virtual_after"] < 0.05:
            failed.append("survival_rate_below_min:" + label)
        if not row["gate2_dependency_audit"]["passed"]:
            failed.append("dependency_audit_failed:" + label)
        window_rows[label] = {
            "before_ev": _float_metric(row["before_metrics"], "expected_value_score"),
            "after_ev": _float_metric(row["virtual_after_metrics"], "expected_value_score"),
            "ev_delta": round(ev_delta, 6),
            "before_pnl": _float_metric(row["before_metrics"], "total_pnl"),
            "after_pnl": _float_metric(row["virtual_after_metrics"], "total_pnl"),
            "pnl_delta": round(pnl_delta, 2),
            "drawdown_delta": round(dd_delta, 6),
            "before_trades": int(row["envelope_kept_trade_count"]),
            "after_trades": int(row["virtual_after_trade_count"]),
            "removed_trades": int(row["weak_breadth_removed_trade_count"]),
        }

    if before_total < MIN_TOTAL_ROWS_FOR_READOUT:
        failed.append("readout_sample_too_thin")
    if removed_total < MIN_BUCKET_TRADES_FOR_EVIDENCE:
        failed.append("weak_breadth_bucket_too_thin")
    if after_total < MIN_VIRTUAL_AFTER_TRADES:
        failed.append("virtual_after_trade_count_too_thin")
    if after_ev_sum <= before_ev_sum:
        failed.append("aggregate_ev_not_improved")
    if after_pnl_sum <= before_pnl_sum:
        failed.append("aggregate_pnl_not_improved")

    virtual_gate_passed = not failed
    return {
        "passed": virtual_gate_passed,
        "decision": (
            "observed_positive_market_breadth_tail_state_lead_not_promoted"
            if virtual_gate_passed
            else "rejected_market_breadth_tail_state_classifier"
        ),
        "failed_reasons": failed,
        "before_expected_value_score_sum": round(before_ev_sum, 6),
        "virtual_after_expected_value_score_sum": round(after_ev_sum, 6),
        "expected_value_score_delta": round(after_ev_sum - before_ev_sum, 6),
        "before_total_pnl_sum": round(before_pnl_sum, 2),
        "virtual_after_total_pnl_sum": round(after_pnl_sum, 2),
        "total_pnl_delta": round(after_pnl_sum - before_pnl_sum, 2),
        "before_trade_count": before_total,
        "virtual_after_trade_count": after_total,
        "weak_breadth_removed_trade_count": removed_total,
        "windows_ev_improved": windows_ev_improved,
        "windows_ev_regressed": windows_ev_regressed,
        "windows_pnl_improved": windows_pnl_improved,
        "windows_pnl_regressed": windows_pnl_regressed,
        "window_rows": window_rows,
        "acceptance_rule": (
            "Observed-only virtual gate requires aggregate EV/PnL improvement "
            "versus the accepted allocator envelope, no canonical-window EV/PnL "
            "regression, weak-breadth sample >= 8, virtual-after trades >= 20, "
            "survival >= 5%, and no production behavior change. Passing this gate "
            "would only justify a later shared default-off helper; it is not retained."
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
            reason.startswith(("window_", "weak_breadth_", "aggregate_"))
            for reason in gate["failed_reasons"]
        ),
    }


def build_payload() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] accepted allocator market-breadth tail readout")
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
        "change_type": "read_only_tail_state_classifier_attribution",
        "mechanism_family": "tail_state_classifier_for_momentum_candidate_pools",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Accepted allocator rows may be tail-risk candidates when signal-date "
            "market participation is weak or narrow. Removing that fixed bucket "
            "virtually should improve the accepted allocator envelope if the "
            "bucket contains crowded continuation decay rather than alpha."
        ),
        "pre_run_history_check": {
            "exp-20260613-011": (
                "Rejected front-loaded extension tail exclusion; this run uses a "
                "distinct market-participation bucket and remains read-only."
            ),
            "exp-20260613-009": (
                "Rejected SEC financial-report allocator source extension; this "
                "run does not add sources or change source ranks."
            ),
            "playbook_tail_state_queue": (
                "Read-only tail-state attribution is the allowed first step before "
                "any paper adapter promotion."
            ),
        },
        "parameters": {
            "min_breadth_tickers": MIN_BREADTH_TICKERS,
            "min_strong_up20_fraction": MIN_STRONG_UP20_FRACTION,
            "min_strong_above_sma20_fraction": MIN_STRONG_ABOVE_SMA20_FRACTION,
            "max_weak_up20_fraction": MAX_WEAK_UP20_FRACTION,
            "max_weak_above_sma20_fraction": MAX_WEAK_ABOVE_SMA20_FRACTION,
            "max_weak_spy_ret20": MAX_WEAK_SPY_RET20,
        },
        "gate1_baseline": {
            "protocol": "docs/backtesting.md canonical three windows",
            "before_definition": "accepted allocator execution envelope v2",
            "virtual_after_definition": (
                "accepted allocator envelope rows excluding "
                "weak_or_narrow_market_support bucket"
            ),
            "baseline_artifact": (
                "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
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
                "SPY/QQQ close history at signal_date",
            ],
            "target_price_note": (
                "target_price is absent from accepted allocator paper trades and "
                "is not a dependency of this readout; entry_date and exit prices "
                "are validated per window."
            ),
        },
        "gate3_signal_survival": [
            {
                "window": row["label"],
                "signals_generated": row["signals_generated"],
                "signals_survived_envelope": row["signals_survived_envelope"],
                "signals_survived_virtual_after": row[
                    "signals_survived_virtual_after"
                ],
                "survival_rate_virtual_after": row["survival_rate_virtual_after"],
            }
            for row in rows
        ],
        "gate4": gate,
        "windows": _safe(rows),
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
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_paper_only": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "uses_llm": False,
            "uses_free_ohlcv_only": True,
            "live_realism_evaluated": True,
            "live_ready": False,
            "production_consistency_note": (
                "No production or shared helper behavior changed. A positive "
                "virtual result would remain a read-only lead until the same "
                "market-breadth bucket is implemented in a shared default-off "
                "helper and daily snapshot with parity tests."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": "filled after gate evaluation",
            "forbidden_near_neighbor_retry": (
                "Do not sweep breadth fractions, SMA lookbacks, SPY/QQQ cutoffs, "
                "allocator source ranks, top-N, notional, hold days, cooldown, or "
                "the execution envelope on these frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs materially new tail-state evidence such as forward "
                "closed replacement rows, same-day displacement type, or a PIT flow "
                "field beyond OHLCV breadth."
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
            "The weak/narrow breadth bucket removed enough low-value accepted "
            "allocator rows to improve the virtual readout across the canonical "
            "windows. It is still not retained because production/shared helper "
            "parity and default-off daily exposure were intentionally not changed."
        )
        return
    reasons = ", ".join(gate["failed_reasons"]) or "unknown"
    payload["post_run_reflection"]["why_result_happened"] = (
        "The market-breadth tail bucket did not cleanly separate accepted "
        f"allocator losers from winners. Failure reasons: {reasons}. The accepted "
        "allocator already mixes event, revision, volatility, relation, and "
        "industry-flow sources; broad breadth can remove valid relief/rotation "
        "trades as easily as crowded continuation tails."
    )


def _build_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Accepted Allocator Market-Breadth Tail Readout",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4 Three-Window Readout",
        "",
        "| Window | Before EV | Virtual After EV | dEV | Before PnL | Virtual After PnL | dPnL | Before Trades | After Trades | Removed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["windows"]:
        before = row["before_metrics"]
        after = row["virtual_after_metrics"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:,.2f} | {before_n} | {after_n} | {removed} |".format(
                label=row["label"],
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(after["expected_value_score"]) - float(before["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(after["total_pnl"]) - float(before["total_pnl"]),
                before_n=int(row["envelope_kept_trade_count"]),
                after_n=int(row["virtual_after_trade_count"]),
                removed=int(row["weak_breadth_removed_trade_count"]),
            )
        )
    gate = payload["gate4"]
    lines.extend(
        [
            "",
            f"- Aggregate EV delta: `{gate['expected_value_score_delta']:+.6f}`",
            f"- Aggregate PnL delta: `${gate['total_pnl_delta']:+,.2f}`",
            f"- Weak-breadth removed trades: `{gate['weak_breadth_removed_trade_count']}`",
            f"- Failed reasons: `{', '.join(gate['failed_reasons']) or 'none'}`",
            "",
            "## Production Impact",
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
        "implementation_mode": "read_only_private_replay_attribution",
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "nearby_prior_experiments": [
            "exp-20260613-011",
            "exp-20260613-009",
            "exp-20260611-005",
            "exp-20260612-024",
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
            "Market-breadth tail readout over accepted allocator envelope "
            f"{payload['status']}; EV delta {gate['expected_value_score_delta']}, "
            f"PnL delta {gate['total_pnl_delta']}."
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card_file": _repo_rel(CARD_MD),
    }
    persist_self_registered_result(
        REPO_ROOT / "docs" / "experiment_registry.json",
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )


def main() -> None:
    payload = build_payload()
    persist(payload)
    gate = payload["gate4"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "ev_delta": gate["expected_value_score_delta"],
                "pnl_delta": gate["total_pnl_delta"],
                "failed_reasons": gate["failed_reasons"],
                "artifact": _repo_rel(OUT_JSON),
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
