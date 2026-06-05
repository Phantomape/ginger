"""exp-20260605-001: FUNDAMENTAL_GROWTH_RS_PAPER market-regime gate.

Replay-only alpha scout. Single causal variable: require the SPY close to be
at or above its 50-day moving average AND IWM 20-day return to be at least
SPY 20-day return before admitting a FUNDAMENTAL_GROWTH_RS_PAPER candidate.

BEFORE: all accepted FGRS paper trade rows from exp-20260601-026 (70/90/105).
AFTER: the same rows filtered to signal dates where the market regime passes.

Core signal, baseline ordering, sizing, exits, LLM/news, watchlists, and live
orders are unchanged. No JavaScript was used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "quant" / "experiments" / "legacy"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260605-001"
STEM = "fgrs_market_regime_gate"
TRIAL_FAMILY = "fundamental_growth_rs_market_regime_gate"
CHANGED_VARIABLE = "market_regime_admission_gate_on_fundamental_growth_rs_paper"
RULE_VERSION = "fundamental_growth_rs_market_regime_gate_v1"

SOURCE_EXPERIMENT_ID = "exp-20260601-026"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260601_026_companyfacts_gross_margin_rs_adapter.json"
)

SPY_MA_DAYS = 50
MARKET_RET_DAYS = 20
MIN_IWM_MINUS_SPY_RET20 = 0.0

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
CANONICAL_DOC_EV = 7.8941
CANONICAL_DOC_PNL = 234_850.99

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _ohlcv_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    return None


def _date_str(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _close_return(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    start = _ohlcv_value(rows[idx - days], "Close")
    end = _ohlcv_value(rows[idx], "Close")
    if not start or end is None:
        return None
    return (float(end) / float(start)) - 1.0


def _trailing_average(rows: list[dict[str, Any]], idx: int, days: int, field: str) -> float | None:
    if idx + 1 < days:
        return None
    values = [_ohlcv_value(row, field) for row in rows[idx + 1 - days: idx + 1]]
    clean = [float(v) for v in values if v is not None]
    if len(clean) < days:
        return None
    return sum(clean) / len(clean)


def _load_snapshot(cfg: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    path = ROOT / cfg["snapshot"]
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    raw = payload.get("ohlcv", payload)
    return {ticker: sorted(rows, key=_date_str) for ticker, rows in raw.items()}


def _build_regime_pass_cache(
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
) -> dict[str, dict[str, Any]]:
    spy_rows = snapshot.get("SPY") or []
    iwm_rows = snapshot.get("IWM") or []
    spy_idx_map = {_date_str(row): i for i, row in enumerate(spy_rows)}
    iwm_idx_map = {_date_str(row): i for i, row in enumerate(iwm_rows)}
    cache: dict[str, dict[str, Any]] = {}

    for date in dates:
        spy_idx = spy_idx_map.get(date)
        iwm_idx = iwm_idx_map.get(date)
        if spy_idx is None or iwm_idx is None:
            cache[date] = {
                "passed": False,
                "reason": "missing_benchmark_rows",
                "spy_above_50d_ma": False,
            }
            continue
        if spy_idx < max(SPY_MA_DAYS, MARKET_RET_DAYS) or iwm_idx < MARKET_RET_DAYS:
            cache[date] = {
                "passed": False,
                "reason": "insufficient_benchmark_history",
                "spy_above_50d_ma": False,
            }
            continue
        spy_close = _ohlcv_value(spy_rows[spy_idx], "Close")
        spy_ma50 = _trailing_average(spy_rows, spy_idx, SPY_MA_DAYS, "Close")
        spy_ret20 = _close_return(spy_rows, spy_idx, MARKET_RET_DAYS)
        iwm_ret20 = _close_return(iwm_rows, iwm_idx, MARKET_RET_DAYS)
        if spy_close is None or spy_ma50 is None or spy_ret20 is None or iwm_ret20 is None:
            cache[date] = {
                "passed": False,
                "reason": "missing_benchmark_data",
                "spy_above_50d_ma": False,
            }
            continue
        spy_above = spy_close >= spy_ma50
        iwm_minus_spy = iwm_ret20 - spy_ret20
        passed = spy_above and iwm_minus_spy >= MIN_IWM_MINUS_SPY_RET20
        if passed:
            reason = "passed"
        elif not spy_above:
            reason = "spy_below_50d_ma"
        else:
            reason = "iwm_lagging_spy_20d"
        cache[date] = {
            "passed": passed,
            "reason": reason,
            "spy_above_50d_ma": spy_above,
            "spy_close": _round(spy_close, 4),
            "spy_ma50": _round(spy_ma50, 4),
            "spy_ret20": _round(spy_ret20, 6),
            "iwm_ret20": _round(iwm_ret20, 6),
            "iwm_minus_spy_ret20": _round(iwm_minus_spy, 6),
        }
    return cache


def _load_source_payload() -> dict[str, Any]:
    with SOURCE_ARTIFACT.open(encoding="utf-8") as handle:
        return json.load(handle)


def _source_target_rows_by_window(
    payload: dict[str, Any],
) -> OrderedDict[str, list[dict[str, Any]]]:
    rows: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    raw = payload.get("target_trades_by_window") or {}
    for label in base.WINDOWS:
        window_rows = raw.get(label) or []
        rows[label] = [dict(row) for row in window_rows if isinstance(row, dict)]
    return rows


def _filter_by_regime(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    snapshots: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[
    OrderedDict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    filtered_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    regime_audit: dict[str, Any] = {}
    for label, rows in rows_by_window.items():
        snapshot = snapshots[label]
        dates = sorted({str(row.get("signal_date") or row.get("date") or "")[:10] for row in rows})
        regime_cache = _build_regime_pass_cache(snapshot, dates)

        bucket_counts: Counter[str] = Counter()
        passed_dates: set[str] = set()
        for date, ctx in regime_cache.items():
            bucket = str(ctx.get("reason") or "unknown")
            bucket_counts[bucket] += 1
            if ctx.get("passed"):
                passed_dates.add(date)

        selected: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        for row in rows:
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            if signal_date in passed_dates:
                selected.append({
                    **row,
                    "regime_gate_pass": True,
                    "regime_gate_reason": "passed",
                    "rule_version": RULE_VERSION,
                })
            else:
                regime_ctx = regime_cache.get(signal_date, {})
                removed.append({
                    **row,
                    "regime_gate_pass": False,
                    "regime_gate_reason": regime_ctx.get("reason", "missing_date_in_cache"),
                })

        filtered_by_window[label] = selected
        regime_audit[label] = {
            "source_trade_count": len(rows),
            "regime_passing_trade_count": len(selected),
            "regime_filtered_trade_count": len(removed),
            "regime_dates_checked": len(dates),
            "regime_passing_dates": len(passed_dates),
            "regime_bucket_counts": dict(sorted(bucket_counts.items())),
            "removed_sample": removed[:10],
        }
    return filtered_by_window, regime_audit


def _load_baselines() -> OrderedDict[str, dict[str, Any]]:
    baselines: OrderedDict[str, dict[str, Any]] = OrderedDict()
    universe = sorted(base.get_universe())
    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] running baseline")
        result = base.shadow._run_baseline(universe, cfg)
        baselines[label] = {
            "result": result,
            "metrics": base.overlay_helper._metrics(result),
        }
    return baselines


def _run_windows(
    baselines: OrderedDict[str, dict[str, Any]],
    before_by_window: OrderedDict[str, list[dict[str, Any]]],
    after_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in base.WINDOWS.items():
        baseline_result = baselines[label]["result"]
        baseline_metrics = baselines[label]["metrics"]

        before_trades = before_by_window[label]
        after_trades = after_by_window[label]

        overlay_before = base._overlay_from_paper_trades(baseline_result, before_trades)
        overlay_after = base._overlay_from_paper_trades(baseline_result, after_trades)

        metrics_before = base.overlay_helper._metrics_with_overlay(baseline_result, overlay_before)
        metrics_after = base.overlay_helper._metrics_with_overlay(baseline_result, overlay_after)
        delta = base.overlay_helper._delta(metrics_after, metrics_before)

        rows[label] = {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "baseline": baseline_metrics,
            "before": metrics_before,
            "after": metrics_after,
            "delta": delta,
            "before_trade_count": len(before_trades),
            "after_trade_count": len(after_trades),
            "filtered_trade_count": len(before_trades) - len(after_trades),
            "target_trade_count": len(after_trades),
            "before_trade_pnl_usd": _round(
                sum(_as_float(row.get("pnl") or 0.0) for row in before_trades), 2
            ),
            "after_trade_pnl_usd": _round(
                sum(_as_float(row.get("pnl") or 0.0) for row in after_trades), 2
            ),
            "overlay_before_total_pnl": overlay_before["overlay_total_pnl"],
            "overlay_after_total_pnl": overlay_after["overlay_total_pnl"],
        }
    return rows


def _aggregate(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"] or 0.0) for row in window_rows.values())
    after_ev = sum(float(row["after"]["expected_value_score"] or 0.0) for row in window_rows.values())
    before_pnl = sum(float(row["before"]["total_pnl"] or 0.0) for row in window_rows.values())
    after_pnl = sum(float(row["after"]["total_pnl"] or 0.0) for row in window_rows.values())
    max_dd_before = max(float(row["before"]["max_drawdown_pct"] or 0.0) for row in window_rows.values())
    max_dd_after = max(float(row["after"]["max_drawdown_pct"] or 0.0) for row in window_rows.values())
    return {
        "before": {
            "expected_value_score": _round(before_ev, 6),
            "total_pnl": _round(before_pnl, 2),
            "max_drawdown_pct": _round(max_dd_before, 6),
        },
        "after": {
            "expected_value_score": _round(after_ev, 6),
            "total_pnl": _round(after_pnl, 2),
            "max_drawdown_pct": _round(max_dd_after, 6),
        },
        "delta": {
            "expected_value_score": _round(after_ev - before_ev, 6),
            "expected_value_score_pct": _round((after_ev - before_ev) / before_ev, 6)
            if before_ev
            else None,
            "total_pnl": _round(after_pnl - before_pnl, 2),
            "max_drawdown_pct": _round(max_dd_after - max_dd_before, 6),
        },
    }


def _target_summary(
    after_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    all_trades = [row for rows in after_by_window.values() for row in rows]
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    trades_by_window = {label: len(rows) for label, rows in after_by_window.items()}
    for trade in all_trades:
        ticker = str(trade.get("ticker") or "").upper()
        pnl = _as_float(trade.get("pnl") or 0.0) or 0.0
        by_ticker_count[ticker] += 1
        by_ticker_pnl[ticker] += pnl
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_single = (
        _round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    pnl_hhi = (
        _round(sum((p / positive_total) ** 2 for p in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    ticker_rows = sorted(
        [
            {
                "ticker": ticker,
                "trade_count": by_ticker_count[ticker],
                "paper_pnl_usd": _round(by_ticker_pnl[ticker], 2),
                "positive_pnl_share": _round(
                    positive.get(ticker, 0.0) / positive_total, 6
                )
                if positive_total > 0
                else None,
            }
            for ticker in by_ticker_count
        ],
        key=lambda row: -(float(row["paper_pnl_usd"] or 0.0)),
    )
    return {
        "target_trade_count": len(all_trades),
        "trades_by_window": trades_by_window,
        "pnl_by_window": {
            label: _round(sum(_as_float(row.get("pnl") or 0.0) for row in rows), 2)
            for label, rows in after_by_window.items()
        },
        "target_trade_pnl_usd": _round(
            sum(_as_float(row.get("pnl") or 0.0) for row in all_trades), 2
        ),
        "positive_pnl_total_usd": _round(positive_total, 2),
        "max_single_positive_share": max_single,
        "positive_pnl_hhi": pnl_hhi,
        "ticker_rows": ticker_rows,
    }


def _baseline_caveat(aggregate: dict[str, Any]) -> dict[str, Any]:
    current_ev = float(aggregate["before"]["expected_value_score"])
    current_pnl = float(aggregate["before"]["total_pnl"])
    ev_delta = current_ev - CANONICAL_DOC_EV
    pnl_delta = current_pnl - CANONICAL_DOC_PNL
    matches = abs(ev_delta) <= 0.50 and abs(pnl_delta) <= 2000.0
    return {
        "baseline_matches_docs": matches,
        "canonical_docs_ev": CANONICAL_DOC_EV,
        "canonical_docs_pnl": CANONICAL_DOC_PNL,
        "current_replay_ev": _round(current_ev, 6),
        "current_replay_pnl": _round(current_pnl, 2),
        "ev_delta_vs_docs": _round(ev_delta, 6),
        "pnl_delta_vs_docs": _round(pnl_delta, 2),
        "note": (
            "Current replay baseline is close to the accepted docs/backtesting.md baseline."
            if matches
            else "Current replay baseline deviates from docs/backtesting.md; do not retain without resolving."
        ),
    }


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
    baseline_caveat: dict[str, Any],
) -> dict[str, Any]:
    ev_improved_windows = [
        label for label, row in window_rows.items()
        if float(row["delta"].get("expected_value_score") or 0.0) > 0.0
    ]
    pnl_improved_windows = [
        label for label, row in window_rows.items()
        if float(row["delta"].get("total_pnl") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(
        float(row["delta"].get("max_drawdown_pct") or 0.0) for row in window_rows.values()
    )
    min_survival_rate = min(
        float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values()
    )
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for v in target_summary["trades_by_window"].values() if v > 0)
    max_single = float(target_summary.get("max_single_positive_share") or 0.0)
    pnl_hhi = float(target_summary.get("positive_pnl_hhi") or 0.0)
    concentration_passed = (
        max_single <= MAX_SINGLE_POSITIVE_SHARE and pnl_hhi <= MAX_POSITIVE_HHI
    )
    alpha_gates = OrderedDict([
        ("aggregate_expected_value_positive", float(aggregate["delta"]["expected_value_score"]) > 0.0),
        ("aggregate_pnl_positive", float(aggregate["delta"]["total_pnl"]) > 0.0),
        ("all_windows_expected_value_improved", len(ev_improved_windows) == len(window_rows)),
        ("all_windows_pnl_improved", len(pnl_improved_windows) == len(window_rows)),
        ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
        ("target_window_count_passed", target_window_count >= MIN_TARGET_WINDOWS),
        ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
        ("survival_floor_passed", min_survival_rate >= 0.05),
        ("concentration_guard_passed", concentration_passed),
    ])
    gates = OrderedDict(alpha_gates)
    gates["baseline_matches_docs_for_retention"] = bool(baseline_caveat["baseline_matches_docs"])
    alpha_failed = [name for name, passed in alpha_gates.items() if not passed]
    failed = [name for name, passed in gates.items() if not passed]
    alpha_passed = not alpha_failed
    promotable_now = alpha_passed and bool(baseline_caveat["baseline_matches_docs"])
    if alpha_passed:
        decision = (
            "positive_replay_lead_not_promoted_requires_shared_adapter"
            if promotable_now
            else "positive_replay_lead_not_promoted_baseline_mismatch"
        )
        rationale = (
            "The market-regime gate passed all three windows and Gate 4 alpha checks. "
            "A shared default-off adapter must be implemented before promotion."
            if alpha_passed
            else "Gate 4 alpha checks failed; no strategy behavior is retained."
        )
    else:
        decision = "rejected_fgrs_market_regime_gate"
        rationale = "Gate 4 alpha checks failed; no strategy behavior is retained."
    return {
        "passed": promotable_now,
        "alpha_passed": alpha_passed,
        "promotable_now": promotable_now,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "alpha_failed_gates": alpha_failed,
        "failed_gates": failed,
        "ev_windows_improved": ev_improved_windows,
        "pnl_windows_improved": pnl_improved_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "target_trade_count": target_trade_count,
        "requires_shared_adapter_before_promotion": alpha_passed,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: FGRS Market-Regime Gate",
        "",
        f"- decision: `{payload['decision']}`",
        f"- single variable: `{CHANGED_VARIABLE}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- target trades (after gate): `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(payload['gate4']['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | "
            f"{row['before_trade_count']} | {row['after_trade_count']} |"
        )
    lines.extend([
        "",
        "## Regime Gate Audit",
        "",
        "| window | source | regime pass | regime fail |",
        "|---|---:|---:|---:|",
    ])
    for label, audit in payload["regime_audit"].items():
        lines.append(
            f"| {label} | {audit['source_trade_count']} | "
            f"{audit['regime_passing_trade_count']} | "
            f"{audit['regime_filtered_trade_count']} |"
        )
    lines.extend([
        "",
        "## Conclusion",
        "",
        payload["gate4"]["rationale"],
        "",
        f"- Regime gate: SPY close >= 50d MA AND IWM 20d return >= SPY 20d return (min {MIN_IWM_MINUS_SPY_RET20})",
        "- Source: exp-20260601-026 FGRS accepted trade rows",
        "- No live/default orders, core ranking, sizing, exits, LLM, or news changed.",
        "",
    ])
    return "\n".join(lines)


def _card(payload: dict[str, Any]) -> str:
    return "\n".join([
        f"# {EXPERIMENT_ID} FGRS market-regime gate",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['decision']}`",
        f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
        f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
        f"- Target trades (after gate): {payload['target_trade_summary']['target_trade_count']}",
        f"- Baseline matches docs: {payload['baseline_caveat']['baseline_matches_docs']}",
        "",
        "See artifact for three-window table and regime audit.",
        "",
    ])


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["alpha_passed"],
        "alpha_passed": payload["gate4"]["alpha_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "failed_gates": payload["gate4"]["failed_gates"],
        "metrics": {
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["decision"]
            item["completed_at"] = payload["timestamp"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["report_file"] = _repo_rel(ARTIFACT_MD)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["delta"]["expected_value_score"]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["delta"]["total_pnl"]
            break
    _write_json(REGISTRY_JSON, registry)


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    print("[source] loading source artifact")
    source_payload = _load_source_payload()
    source_rows_by_window = _source_target_rows_by_window(source_payload)

    print("[snapshots] loading OHLCV snapshots")
    snapshots = {label: _load_snapshot(cfg) for label, cfg in base.WINDOWS.items()}

    print("[regime] computing regime pass cache and filtering trades")
    after_by_window, regime_audit = _filter_by_regime(source_rows_by_window, snapshots)

    print("[baselines] running core backtester baselines")
    baselines = _load_baselines()

    print("[windows] computing before/after overlays")
    window_rows = _run_windows(baselines, source_rows_by_window, after_by_window)

    aggregate = _aggregate(window_rows)
    target_summary = _target_summary(after_by_window)
    baseline_caveat = _baseline_caveat(aggregate)
    gate4 = _gate4(aggregate, window_rows, target_summary, baseline_caveat)

    timestamp = _utc_now()
    decision = gate4["decision"]

    regime_date_coverage = {
        label: {
            "regime_passing_dates": audit["regime_passing_dates"],
            "regime_dates_checked": audit["regime_dates_checked"],
            "pass_rate": _round(
                audit["regime_passing_dates"] / audit["regime_dates_checked"], 4
            )
            if audit["regime_dates_checked"]
            else None,
            "bucket_counts": audit["regime_bucket_counts"],
        }
        for label, audit in regime_audit.items()
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "lane": "alpha_search",
        "decision": decision,
        "accepted": gate4["alpha_passed"],
        "hypothesis": (
            "A market-regime gate requiring SPY above its 50-day MA and IWM 20-day "
            "return at least SPY 20-day return applied to FUNDAMENTAL_GROWTH_RS_PAPER "
            "candidate admission concentrates entries in confirmed bullish regimes and "
            "improves sleeve EV."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": TRIAL_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260531-016",
            "exp-20260531-021",
            "exp-20260601-026",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "market_regime_gate_applied_to_highest_paper_ev_fgrs_sleeve",
        "parameters": {
            "spy_ma_days": SPY_MA_DAYS,
            "market_ret_days": MARKET_RET_DAYS,
            "min_iwm_minus_spy_ret20": MIN_IWM_MINUS_SPY_RET20,
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "rule_version": RULE_VERSION,
            "locked_variables": [
                "fgrs_candidate_scoring",
                "fgrs_entry_notional",
                "fgrs_hold_days",
                "core_signal_generation",
                "core_ranking",
                "core_sizing",
                "core_exits",
                "llm_news",
                "live_orders",
            ],
        },
        "aggregate": aggregate,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "regime_audit": regime_audit,
        "regime_date_coverage": regime_date_coverage,
        "baseline_caveat": baseline_caveat,
        "gate1": {
            "baseline_source": "docs/backtesting.md canonical three-window protocol",
            "baseline_ev": CANONICAL_DOC_EV,
            "baseline_pnl": CANONICAL_DOC_PNL,
            "note": "Baseline from exp-20260602-003 accepted run.",
        },
        "gate2": {
            "open_positions_check": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "data/ohlcv SPY/IWM Close rows for 50d MA and 20d return",
                "source artifact pnl, signal_date, exit_date",
            ],
            "note": (
                "Regime gate uses only SPY and IWM daily close prices with date <= signal_date. "
                "No LLM, news, event, or future bar used. PnL from source artifact is PIT-safe."
            ),
        },
        "gate3": {
            "note": "No core filter or live entry rule added. Regime gate is additive default-off paper only.",
            "candidate_pool_changed": False,
            "live_filter_added": False,
        },
        "gate4": gate4,
        "gate_questions": {
            "1_alpha_hypothesis": (
                "FGRS paper sleeve is highest-EV paper sleeve (~16 aggregate EV) with no "
                "market-context filter. The SPY/IWM regime gate proven for ALPHA_SCORE "
                "sleeve (exp-20260531-021) may concentrate FGRS entries in bullish regimes."
            ),
            "2_history_check": {
                "exp-20260531-016": (
                    "Market-regime gate on full-universe alpha_score source passed Gate 4 "
                    "as a positive replay lead (exp-20260531-021 promoted it to shared adapter)."
                ),
                "exp-20260531-021": (
                    "alpha_score market-regime shared adapter accepted. Gate passed all windows."
                ),
                "exp-20260601-026": (
                    "FGRS gross margin adapter accepted; current FGRS source with 70/90/105 "
                    "trades per window. No market regime gate applied to FGRS."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Three docs/backtesting.md windows; positive aggregate EV/PnL; 3/3 "
                "EV-improved windows; 3/3 PnL-improved windows; >=20 after-gate target "
                "trades; drawdown drift <=0.5pp; survival >=5%; concentration guardrails."
            ),
            "5_reproducibility": (
                "python3 -B quant/experiments/exp_20260605_001_fgrs_market_regime_gate.py"
            ),
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_orders_changed": False,
            "promotion_requirement": (
                "A positive replay lead requires a shared default-off adapter that "
                "implements the same regime gate in production and replay, plus parity "
                "tests, before any activation review."
            ),
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "anti_js": "No JavaScript was used.",
        "ticket": _load_ticket(),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(SOURCE_ARTIFACT),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }


def main() -> None:
    print(f"[{EXPERIMENT_ID}] starting")
    payload = _build_payload()
    agg = payload["aggregate"]
    gate4 = payload["gate4"]

    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_JSON,
        {
            **payload["aggregate"]["before"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
            "timestamp": payload["timestamp"],
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
            "timestamp": payload["timestamp"],
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _card(payload))
    _write_text(ARTIFACT_MD, _artifact(payload))
    _update_ticket(payload)
    _update_registry(payload)
    _upsert_jsonl(EXPERIMENT_LOG, {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "trial_family": payload["trial_family"],
        "changed_variable": payload["changed_variable"],
        "aggregate_ev_before": agg["before"]["expected_value_score"],
        "aggregate_ev_after": agg["after"]["expected_value_score"],
        "aggregate_ev_delta": agg["delta"]["expected_value_score"],
        "aggregate_pnl_delta": agg["delta"]["total_pnl"],
        "gate4_passed": gate4["passed"],
        "gate4_alpha_passed": gate4["alpha_passed"],
        "failed_gates": gate4["failed_gates"],
        "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
    })

    print(json.dumps(_safe({
        "decision": payload["decision"],
        "ev_before": agg["before"]["expected_value_score"],
        "ev_after": agg["after"]["expected_value_score"],
        "ev_delta": agg["delta"]["expected_value_score"],
        "pnl_delta": agg["delta"]["total_pnl"],
        "gate4_passed": gate4["passed"],
        "failed_gates": gate4["failed_gates"],
        "target_trades": payload["target_trade_summary"]["target_trade_count"],
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
