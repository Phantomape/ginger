"""Experiment exp-20260601-002: Companyfacts share contraction + RS scout.

Replay-only alpha scout. It tests whether SEC Companyfacts diluted-share
contraction is a useful candidate-pool discriminator on top of the accepted
Fundamental Growth + RS paper source. It does not change production orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260601-002"
STEM = "companyfacts_share_contraction_rs_candidate_pool"
TRIAL_FAMILY = "companyfacts_share_contraction_rs_candidate_pool"
CHANGED_VARIABLE = "shares_diluted_yoy_contraction_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = "exp-20260528-017"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "fundamental_growth_rs_low_liability_support.json"
)
NON_OHLCV_DIR = ROOT / "data" / "non_ohlcv"

MAX_SHARE_YOY_CHANGE = -0.005
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = ROOT / "operator_inputs" / "open_positions.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
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


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


class ShareCountIndex:
    def __init__(self, *, tickers: set[str]) -> None:
        ticker_set = {ticker.upper() for ticker in tickers}
        by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for path in sorted(NON_OHLCV_DIR.glob("sec_companyfacts_selected_*.jsonl")):
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("canonical") != "shares_diluted":
                        continue
                    ticker = str(row.get("ticker") or "").upper()
                    filed = str(row.get("filed") or "")[:10]
                    value = _as_float(row.get("value"))
                    fy = _as_int(row.get("fy"))
                    fp = str(row.get("fp") or "").upper()
                    if (
                        ticker not in ticker_set
                        or not filed
                        or value is None
                        or value <= 0.0
                        or fy is None
                        or not fp
                    ):
                        continue
                    by_ticker[ticker].append(
                        {
                            "ticker": ticker,
                            "filed": filed,
                            "value": value,
                            "fy": fy,
                            "fp": fp,
                            "end": row.get("end"),
                            "form": row.get("form"),
                            "duration_days": row.get("duration_days"),
                            "concept": row.get("concept"),
                            "unit": row.get("unit"),
                        }
                    )
        for rows in by_ticker.values():
            rows.sort(
                key=lambda row: (
                    str(row.get("filed") or ""),
                    str(row.get("end") or ""),
                    str(row.get("form") or ""),
                    float(row.get("value") or 0.0),
                )
            )
        self.by_ticker = by_ticker

    def yoy_change(self, ticker: str, signal_date: str) -> dict[str, Any]:
        rows = [
            row
            for row in self.by_ticker.get(ticker.upper(), [])
            if str(row.get("filed") or "") <= signal_date
        ]
        if not rows:
            return {
                "share_count_status": "missing_current_shares_diluted",
                "share_count_available": False,
                "known_at": "SEC Companyfacts filed date <= signal date",
            }
        current = rows[-1]
        priors = [
            row
            for row in rows
            if row.get("fy") == int(current["fy"]) - 1 and row.get("fp") == current.get("fp")
        ]
        if not priors:
            return {
                "share_count_status": "missing_prior_year_same_period",
                "share_count_available": False,
                "current_filed": current.get("filed"),
                "current_period_end": current.get("end"),
                "current_fy": current.get("fy"),
                "current_fp": current.get("fp"),
                "known_at": "SEC Companyfacts filed date <= signal date",
            }
        prior = priors[-1]
        current_value = _as_float(current.get("value"))
        prior_value = _as_float(prior.get("value"))
        if current_value is None or prior_value is None or prior_value <= 0.0:
            return {
                "share_count_status": "invalid_current_or_prior_value",
                "share_count_available": False,
                "current_filed": current.get("filed"),
                "prior_filed": prior.get("filed"),
                "known_at": "SEC Companyfacts filed date <= signal date",
            }
        change = current_value / prior_value - 1.0
        return {
            "share_count_status": "ok",
            "share_count_available": True,
            "shares_diluted_yoy_change": _round(change, 6),
            "share_count_contraction_pass_v1": change <= MAX_SHARE_YOY_CHANGE,
            "share_count_threshold_max_yoy_change": MAX_SHARE_YOY_CHANGE,
            "current_shares_diluted": _round(current_value, 3),
            "current_filed": current.get("filed"),
            "current_period_end": current.get("end"),
            "current_fy": current.get("fy"),
            "current_fp": current.get("fp"),
            "current_form": current.get("form"),
            "current_duration_days": current.get("duration_days"),
            "prior_shares_diluted": _round(prior_value, 3),
            "prior_filed": prior.get("filed"),
            "prior_period_end": prior.get("end"),
            "prior_fy": prior.get("fy"),
            "prior_fp": prior.get("fp"),
            "prior_form": prior.get("form"),
            "known_at": "SEC Companyfacts filed date <= signal date",
        }


def _load_source_payload() -> dict[str, Any]:
    with SOURCE_ARTIFACT.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _source_target_rows_by_window(payload: dict[str, Any]) -> OrderedDict[str, list[dict[str, Any]]]:
    rows = OrderedDict()
    raw = payload.get("target_trades_by_window") or {}
    for label in base.WINDOWS:
        window_rows = raw.get(label) or []
        rows[label] = [dict(row) for row in window_rows if isinstance(row, dict)]
    return rows


def _select_target_trades(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    share_index: ShareCountIndex,
) -> tuple[OrderedDict[str, list[dict[str, Any]]], dict[str, Any]]:
    selected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts_by_window: OrderedDict[str, dict[str, int]] = OrderedDict()
    raw_contraction_candidates_by_window: OrderedDict[str, int] = OrderedDict()

    for label, rows in rows_by_window.items():
        selected: list[dict[str, Any]] = []
        filtered: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
            context = share_index.yoy_change(ticker, signal_date)
            status_counts[str(context.get("share_count_status") or "unknown")] += 1
            candidate = {
                **row,
                **context,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": RULE_VERSION,
                "share_count_rule_version": RULE_VERSION,
                "strategy": "companyfacts_share_contraction_rs_candidate_pool",
                "trade_enabled": False,
                "alters_orders": False,
                "source_experiment_id": SOURCE_EXPERIMENT_ID,
                "source_artifact": _repo_rel(SOURCE_ARTIFACT),
                "paper_pnl_source": "pnl_without_low_liability_support",
            }
            if context.get("share_count_contraction_pass_v1") is not True:
                filtered.append({**candidate, "filter_reason": "share_count_contraction_not_available_or_not_met"})
                continue
            pnl = _as_float(row.get("pnl_without_low_liability_support"))
            if pnl is None:
                pnl = _as_float(row.get("pnl"))
                candidate["paper_pnl_source"] = "pnl"
            if pnl is None:
                filtered.append({**candidate, "filter_reason": "missing_paper_pnl"})
                continue
            selected.append({**candidate, "pnl": _round(pnl, 2), "paper_pnl": _round(pnl, 2)})

        selected_by_window[label] = selected
        filtered_by_window[label] = filtered[:200]
        status_counts_by_window[label] = dict(sorted(status_counts.items()))
        raw_contraction_candidates_by_window[label] = len(selected)

    diagnostics = {
        "source_target_trade_count_by_window": {
            label: len(rows) for label, rows in rows_by_window.items()
        },
        "selected_share_contraction_trade_count_by_window": dict(raw_contraction_candidates_by_window),
        "share_count_status_counts_by_window": status_counts_by_window,
        "filtered_candidates_sample_by_window": filtered_by_window,
    }
    return selected_by_window, diagnostics


def _load_baselines() -> OrderedDict[str, dict[str, Any]]:
    baselines: OrderedDict[str, dict[str, Any]] = OrderedDict()
    universe = sorted(base.get_universe())
    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay")
        result = base.shadow._run_baseline(universe, cfg)
        baselines[label] = {
            "result": result,
            "metrics": base.overlay_helper._metrics(result),
        }
    return baselines


def _run_windows(
    baselines: OrderedDict[str, dict[str, Any]],
    selected_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in base.WINDOWS.items():
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        trades = selected_by_window[label]
        overlay = base._overlay_from_paper_trades(before_result, trades)
        after = base.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = base.overlay_helper._delta(after, before)
        rows[label] = {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "target_trade_pnl_usd": _round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }
    return rows


def _aggregate(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in window_rows.values())
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in window_rows.values())
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in window_rows.values())
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in window_rows.values())
    max_drawdown_before = max(float(row["before"]["max_drawdown_pct"]) for row in window_rows.values())
    max_drawdown_after = max(float(row["after"]["max_drawdown_pct"]) for row in window_rows.values())
    return {
        "before": {
            "expected_value_score": _round(before_ev, 6),
            "strategy_total_pnl": _round(before_pnl, 2),
            "total_pnl": _round(before_pnl, 2),
            "max_drawdown_pct": _round(max_drawdown_before, 6),
        },
        "after": {
            "expected_value_score": _round(after_ev, 6),
            "strategy_total_pnl": _round(after_pnl, 2),
            "total_pnl": _round(after_pnl, 2),
            "max_drawdown_pct": _round(max_drawdown_after, 6),
        },
        "delta": {
            "expected_value_score": _round(after_ev - before_ev, 6),
            "expected_value_score_pct": _round((after_ev - before_ev) / before_ev, 6)
            if before_ev
            else None,
            "strategy_total_pnl": _round(after_pnl - before_pnl, 2),
            "total_pnl": _round(after_pnl - before_pnl, 2),
            "strategy_total_pnl_pct": _round((after_pnl - before_pnl) / before_pnl, 6)
            if before_pnl
            else None,
            "max_drawdown_pct": _round(max_drawdown_after - max_drawdown_before, 6),
        },
    }


def _target_summary(selected_by_window: OrderedDict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_trades = [row for rows in selected_by_window.values() for row in rows]
    by_ticker: dict[str, dict[str, Any]] = {}
    positive_total = 0.0
    for trade in all_trades:
        ticker = str(trade.get("ticker") or "").upper()
        pnl = float(trade.get("pnl") or 0.0)
        bucket = by_ticker.setdefault(
            ticker,
            {
                "ticker": ticker,
                "trade_count": 0,
                "paper_pnl_usd": 0.0,
                "positive_pnl_usd": 0.0,
            },
        )
        bucket["trade_count"] += 1
        bucket["paper_pnl_usd"] += pnl
        if pnl > 0.0:
            bucket["positive_pnl_usd"] += pnl
            positive_total += pnl

    ticker_rows = sorted(
        by_ticker.values(),
        key=lambda row: (-float(row["positive_pnl_usd"]), -int(row["trade_count"]), row["ticker"]),
    )
    for row in ticker_rows:
        row["paper_pnl_usd"] = _round(row["paper_pnl_usd"], 2)
        row["positive_pnl_usd"] = _round(row["positive_pnl_usd"], 2)
        row["positive_pnl_share"] = (
            _round(float(row["positive_pnl_usd"]) / positive_total, 6)
            if positive_total > 0.0
            else None
        )
    max_share = max(
        (float(row["positive_pnl_share"]) for row in ticker_rows if row["positive_pnl_share"] is not None),
        default=0.0,
    )
    hhi = sum(
        float(row["positive_pnl_share"]) ** 2
        for row in ticker_rows
        if row["positive_pnl_share"] is not None
    )
    return {
        "target_trade_count": len(all_trades),
        "target_trade_pnl_usd": _round(sum(float(row.get("pnl") or 0.0) for row in all_trades), 2),
        "positive_pnl_total_usd": _round(positive_total, 2),
        "max_single_positive_share": _round(max_share, 6),
        "positive_pnl_hhi": _round(hhi, 6),
        "trades_by_window": {label: len(rows) for label, rows in selected_by_window.items()},
        "pnl_by_window": {
            label: _round(sum(float(row.get("pnl") or 0.0) for row in rows), 2)
            for label, rows in selected_by_window.items()
        },
        "ticker_rows": ticker_rows,
    }


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    ev_windows_improved = [
        label
        for label, row in window_rows.items()
        if float(row["delta"].get("expected_value_score") or 0.0) > 0.0
    ]
    pnl_windows_improved = [
        label
        for label, row in window_rows.items()
        if float(row["delta"].get("total_pnl") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(float(row["delta"].get("max_drawdown_pct") or 0.0) for row in window_rows.values())
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values())
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for rows in target_summary["trades_by_window"].values() if rows > 0)
    gates = OrderedDict(
        [
            ("aggregate_expected_value_positive", float(aggregate["delta"]["expected_value_score"]) > 0.0),
            ("aggregate_pnl_positive", float(aggregate["delta"]["total_pnl"]) > 0.0),
            ("all_windows_expected_value_improved", len(ev_windows_improved) == len(window_rows)),
            ("all_windows_pnl_improved", len(pnl_windows_improved) == len(window_rows)),
            ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
            ("target_window_count_passed", target_window_count >= MIN_TARGET_WINDOWS),
            ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
            ("survival_floor_passed", min_survival_rate >= 0.05),
            (
                "concentration_guard_passed",
                float(target_summary["max_single_positive_share"] or 0.0) <= MAX_SINGLE_POSITIVE_SHARE
                and float(target_summary["positive_pnl_hhi"] or 0.0) <= MAX_POSITIVE_HHI,
            ),
        ]
    )
    failed = [name for name, passed in gates.items() if not passed]
    passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if passed
        else "rejected_companyfacts_share_contraction_rs_candidate_pool"
    )
    rationale = (
        "Gate 4 passed, but this replay-only scout still requires a shared "
        "live/backtest default-off adapter before any retained promotion."
        if passed
        else "The share-contraction discriminator did not clear Gate 4, so no "
        "production or shared policy change is retained."
    )
    return {
        "passed": passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_parity_before_promotion": passed,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Share Contraction + RS Candidate Pool",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            gate4["rationale"],
            "",
            "This scout used only filed-date Companyfacts share-count rows known on or before "
            "the signal date and the accepted frozen Fundamental Growth + RS paper rows. "
            "It made no live/default order, ranking, sizing, exit, LLM, news, or watchlist change.",
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_payload = _load_source_payload()
    source_rows_by_window = _source_target_rows_by_window(source_payload)
    tickers = {
        str(row.get("ticker") or "").upper()
        for rows in source_rows_by_window.values()
        for row in rows
        if row.get("ticker")
    }
    share_index = ShareCountIndex(tickers=tickers)
    selected_by_window, selection_diagnostics = _select_target_trades(source_rows_by_window, share_index)
    baselines = _load_baselines()
    window_rows = _run_windows(baselines, selected_by_window)
    aggregate = _aggregate(window_rows)
    target_summary = _target_summary(selected_by_window)
    gate4 = _gate4(aggregate, window_rows, target_summary)
    timestamp = _utc_now()
    decision = gate4["decision"]
    accepted = bool(gate4["passed"])

    before_metrics = OrderedDict((label, row["before"]) for label, row in window_rows.items())
    after_metrics = OrderedDict((label, row["after"]) for label, row in window_rows.items())
    delta_metrics = OrderedDict((label, row["delta"]) for label, row in window_rows.items())

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "SEC Companyfacts diluted-share contraction may identify shareholder-yield "
            "growth+RS candidates with better replacement value than the generic "
            "accepted Fundamental Growth + RS paper source."
        ),
        "change_type": "default_off_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "mechanism_family": "companyfacts_shareholder_yield_candidate_pool",
        "prior_trial_count": 2,
        "nearby_prior_experiments": ["exp-20260520-039", SOURCE_EXPERIMENT_ID],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_sec_companyfacts_share_count_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Selected source trades use their already slippage-adjusted next-open "
                "entry and ten-trading-day exit PnL. The overlay is booked on each "
                "paper exit date against the canonical core baseline equity curve."
            ),
        },
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "share_count_field": "shares_diluted",
            "share_count_source": "SEC Companyfacts selected JSONL",
            "max_shares_diluted_yoy_change": MAX_SHARE_YOY_CHANGE,
            "share_count_period_match": "same fiscal period, prior fiscal year",
            "paper_pnl_source": "pnl_without_low_liability_support",
            "locked_variables": [
                "core order generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "accepted alpha_score/source-consensus scalars",
                "accepted fundamental_growth_rs thresholds and top1 selection",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "pnl_improved_windows": 3,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: realized diluted-share contraction plus "
                "growth+RS may isolate shareholder-yield winners from the accepted "
                "Companyfacts paper source."
            ),
            "2_history_check": {
                "exp-20260520-039": "Related buyback/shareholder-yield direction; not promoted.",
                "exp-20260528-017": (
                    "Low-liability support was accepted; a share-count support scalar "
                    "was explicitly skipped because it mainly boosted APP and would "
                    "worsen concentration. This run tests candidate-pool usefulness "
                    "with concentration as a hard Gate 4 guard."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
                "all three windows improve; >=20 target trades across all windows; "
                "target trades in all three windows; drawdown drift <=0.5pp; "
                "survival >=5%; max single positive share <=0.50 and HHI <=0.30."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260601_002_companyfacts_share_contraction_rs_candidate_pool.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_artifact": _repo_rel(BEFORE_JSON),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "source target_trades_by_window entry_date",
                "source target_trades_by_window exit_date",
                "source pnl_without_low_liability_support",
                "sec_companyfacts_selected shares_diluted filed <= signal_date",
            ],
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values()) >= 0.05,
            "note": (
                "No core production filter was added. Survival rates are inherited "
                "from the canonical core baseline plus default-off paper overlay."
            ),
            "signals_generated_survived_by_window": {
                label: {
                    "signals_generated": row["after"].get("signals_generated"),
                    "signals_survived": row["after"].get("signals_survived"),
                    "survival_rate": row["after"].get("survival_rate"),
                }
                for label, row in window_rows.items()
            },
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "aggregate": aggregate,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "target_trades_by_window": selected_by_window,
        "selection_diagnostics": selection_diagnostics,
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": "LLM soft-ranking data was not used; this tests a free deterministic data edge.",
        },
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "new independent deconcentration evidence",
            "forward out-of-sample rows showing non-APP contribution",
            "no share-count support scalar retry on the same frozen windows",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_JSON,
        {
            **payload["aggregate"]["before"],
            "windows": payload["before_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))

    log_row = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["total_pnl"],
            "aggregate_strategy_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_trade_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["delta"]["expected_value_score"],
                "strategy_total_pnl_delta": row["delta"]["total_pnl"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for label, row in payload["window_results"].items()
        ],
        "production_impact": payload["production_impact"],
        "requires_parity_before_promotion": payload["gate4"]["requires_parity_before_promotion"],
        "failure_reasons": payload["gate4"]["failed_gates"],
        "artifact_path": _repo_rel(OUT_JSON),
    }
    _upsert_jsonl(EXPERIMENT_LOG, log_row)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "target_trade_count",
                        "target_trade_pnl_usd",
                        "max_single_positive_share",
                        "positive_pnl_hhi",
                        "trades_by_window",
                        "pnl_by_window",
                    )
                },
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
