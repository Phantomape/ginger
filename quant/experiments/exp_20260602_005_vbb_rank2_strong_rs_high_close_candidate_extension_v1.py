"""exp-20260602-005: VBB rank-2 strong-RS candidate extension.

This alpha search tests one candidate-pool extension on top of the accepted
default-off VBB paper adapter. It keeps the exp-20260526-014 top-1 VBB sleeve
as the before state, then adds at most one rank-2 candidate per breadth day only
when that second candidate also has strong same-day RS, high close location,
and high breadth intensity.

No production/shared adapter, ranking, sizing, exits, LLM/news, watchlist, or
live/default order path is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (ROOT, QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260526_013_volume_breadth_breakout_sleeve as vbb  # noqa: E402


EXPERIMENT_ID = "exp-20260602-005"
STEM = "vbb_rank2_strong_rs_candidate_extension"
TRIAL_FAMILY = "vbb_rank2_strong_rs_candidate_extension"
TRIAL_VARIANT_ID = "rank2_rs_gt_2pct_close_loc_70_breadth_25"
CHANGED_VARIABLE = "vbb_rank2_strong_rs_high_close_candidate_extension_v1"

REFERENCE_VBB_EXPERIMENT_ID = "exp-20260526-014"
CURRENT_CORE_BASELINE_EXPERIMENT_ID = "exp-20260602-003"
CURRENT_VBB_JSON = ROOT / "data/experiments/exp-20260526-014/volume_breadth_shared_adapter.json"
BASELINE_FILES = OrderedDict(
    [
        ("late_strong", ROOT / "data/experiments/exp-20260602-003/late_strong_after.json"),
        ("mid_weak", ROOT / "data/experiments/exp-20260602-003/mid_weak_after.json"),
        ("old_thin", ROOT / "data/experiments/exp-20260602-003/old_thin_after.json"),
    ]
)

MIN_RANK2_RS_VS_SPY = 0.02
MIN_RANK2_CLOSE_LOCATION = 0.70
MIN_RANK2_BREADTH_FRACTION = 0.25
MIN_RANK2_VOLUME_RATIO_20 = 1.50
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260602_005_vbb_rank2_strong_rs_high_close_candidate_extension_v1.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

FULL_VBB_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _complete_expected_value(metrics: dict[str, Any]) -> dict[str, Any]:
    out = dict(metrics)
    if out.get("expected_value_score") is None:
        strategy_return = out.get("strategy_total_return_pct")
        sharpe_daily = out.get("sharpe_daily")
        if isinstance(strategy_return, (int, float)) and isinstance(sharpe_daily, (int, float)):
            out["expected_value_score"] = _round(strategy_return * sharpe_daily, 4)
    return out


def _metric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in [
        "expected_value_score",
        "total_pnl",
        "strategy_total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ]:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            digits = 2 if key == "total_pnl" else 6
            out[key] = round(after_value - before_value, digits)
    return out


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


def _rank2_close_location(snapshot: dict[str, list[dict[str, Any]]], row: dict[str, Any]) -> float | None:
    ticker = str(row.get("ticker") or "").upper()
    date = str(row.get("date") or "")
    rows = vbb.ohlcv_helper._series(snapshot, ticker)
    idx = vbb.ohlcv_helper._row_index(rows).get(date)
    if idx is None:
        return None
    high = vbb.ohlcv_helper._value(rows[idx], "High")
    low = vbb.ohlcv_helper._value(rows[idx], "Low")
    close = vbb.ohlcv_helper._value(rows[idx], "Close")
    if high is None or low is None or close is None:
        return None
    if high <= low:
        return 1.0 if close >= high else 0.0
    return (close - low) / (high - low)


def _rank2_candidates_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    baseline_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    full_candidates = vbb._candidate_rows_for_window(snapshot, cfg, universe, baseline_result)
    by_date: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for row in full_candidates:
        by_date.setdefault(str(row.get("date") or ""), []).append(row)

    selected: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    source_rank2_count = 0
    for date, rows in by_date.items():
        if len(rows) < 2:
            reject_counts["no_rank2_candidate"] += 1
            continue
        rank2 = dict(rows[1])
        source_rank2_count += 1
        rank2["vbb_rank_in_day"] = 2
        rank2["rank2_rule_version"] = CHANGED_VARIABLE
        close_location = _rank2_close_location(snapshot, rank2)
        rank2["close_location"] = _round(close_location, 6)
        breadth_fraction = float(
            (rank2.get("volume_breadth_context") or {}).get("volume_breadth_fraction") or 0.0
        )
        rs_vs_spy = float(rank2.get("candidate_day_rs_vs_spy") or 0.0)
        volume_ratio = float(rank2.get("volume_ratio_20") or 0.0)

        if rs_vs_spy < MIN_RANK2_RS_VS_SPY:
            reject_counts["rank2_rs_below_min"] += 1
            continue
        if close_location is None or close_location < MIN_RANK2_CLOSE_LOCATION:
            reject_counts["rank2_close_location_below_min"] += 1
            continue
        if breadth_fraction < MIN_RANK2_BREADTH_FRACTION:
            reject_counts["breadth_fraction_below_min"] += 1
            continue
        if volume_ratio < MIN_RANK2_VOLUME_RATIO_20:
            reject_counts["rank2_volume_ratio_below_min"] += 1
            continue
        rank2["source_universe"] = "accepted_vbb_rank2_strong_rs_extension"
        rank2["trade_enabled"] = False
        rank2["alters_orders"] = False
        selected.append(rank2)

    diagnostics = {
        "full_vbb_candidate_count": len(full_candidates),
        "full_vbb_candidate_days": len(by_date),
        "source_rank2_candidate_days": source_rank2_count,
        "selected_rank2_candidate_count": len(selected),
        "selected_rank2_candidate_days": len({row["date"] for row in selected}),
        "selected_rank2_unique_tickers": len({row["ticker"] for row in selected}),
        "reject_counts": dict(sorted(reject_counts.items())),
        "thresholds": {
            "min_rank2_rs_vs_spy": MIN_RANK2_RS_VS_SPY,
            "min_rank2_close_location": MIN_RANK2_CLOSE_LOCATION,
            "min_rank2_breadth_fraction": MIN_RANK2_BREADTH_FRACTION,
            "min_rank2_volume_ratio_20": MIN_RANK2_VOLUME_RATIO_20,
        },
    }
    selected.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_day_rs_vs_spy"]),
            -float(row["close_location"] or 0.0),
            -float(row["volume_ratio_20"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    return selected, diagnostics


def _aggregate(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(float(row["before"]["expected_value_score"]) for row in window_rows.values())
    ev_after = sum(float(row["after"]["expected_value_score"]) for row in window_rows.values())
    pnl_before = sum(float(row["before"]["total_pnl"]) for row in window_rows.values())
    pnl_after = sum(float(row["after"]["total_pnl"]) for row in window_rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": _round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(1 for row in window_rows.values() if row["delta"]["expected_value_score"] > 0),
        "windows_ev_regressed": sum(1 for row in window_rows.values() if row["delta"]["expected_value_score"] < 0),
        "windows_pnl_improved": sum(1 for row in window_rows.values() if row["delta"]["total_pnl"] > 0),
        "windows_pnl_regressed": sum(1 for row in window_rows.values() if row["delta"]["total_pnl"] < 0),
        "max_drawdown_delta_max": _round(max(row["delta"]["max_drawdown_pct"] for row in window_rows.values()), 6),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in window_rows.values()),
    }


def _gate4(
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    checks = {
        "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
        "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
        "all_windows_ev_improved": aggregate["windows_ev_improved"] == len(base.WINDOWS)
        and aggregate["windows_ev_regressed"] == 0,
        "no_window_pnl_regression": aggregate["windows_pnl_regressed"] == 0,
        "target_trade_count_passed": target_summary["total_trade_count"] >= MIN_TARGET_TRADES,
        "target_window_count_passed": len(target_windows) >= MIN_TARGET_WINDOWS,
        "drawdown_guard_passed": aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE,
        "survival_guard_passed": min_survival >= 0.05,
        "concentration_passed": concentration_passed,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed,
        "checks": checks,
        "failed_gates": failed,
        "min_survival_rate": _round(min_survival, 6),
        "target_windows": target_windows,
        "acceptance": {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        },
    }


def _build_payload(now: str) -> dict[str, Any]:
    vbb._configure_base_module()
    vbb.BREATH_AUDIT = FULL_VBB_AUDIT
    base.MAX_PAPER_TRADES_PER_DAY = 1

    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    current_vbb = _load_json(CURRENT_VBB_JSON)
    universe = sorted(base.get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    rank2_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    rank2_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    rank2_diagnostics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        baseline_result = vbb.ohlcv_helper._run_baseline(universe, cfg)
        snapshot = vbb.ohlcv_helper._load_snapshot(cfg["snapshot"])
        rank2_candidates, diagnostics = _rank2_candidates_for_window(
            snapshot,
            cfg,
            universe,
            baseline_result,
        )
        rank2_trades, rank2_filtered = base._select_paper_trades(snapshot, rank2_candidates)
        top1_trades = list((current_vbb.get("target_trades_by_window") or {}).get(label) or [])
        top1_overlay = base._overlay_from_paper_trades(baseline_result, top1_trades)
        combined_trades = top1_trades + rank2_trades
        overlay = base._overlay_from_paper_trades(baseline_result, combined_trades)
        before = _complete_expected_value(
            base.overlay_helper._metrics_with_overlay(baseline_result, top1_overlay)
        )
        after = _complete_expected_value(base.overlay_helper._metrics_with_overlay(baseline_result, overlay))
        delta = _metric_delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        rank2_trades_by_window[label] = rank2_trades
        rank2_candidates_by_window[label] = rank2_candidates[:200]
        rank2_diagnostics[label] = {
            **diagnostics,
            "selected_rank2_trade_count": len(rank2_trades),
            "filtered_rank2_candidate_count": len(rank2_filtered),
            "filtered_rank2_reasons": dict(
                sorted(Counter(row.get("filter_reason") for row in rank2_filtered).items())
            ),
            "rank2_trade_pnl": _round(sum(float(row.get("pnl") or 0.0) for row in rank2_trades), 2),
            "reference_top1_trade_count": len(top1_trades),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(rank2_trades),
            "rank2_candidate_count": len(rank2_candidates),
            "rank2_candidate_days": len({row["date"] for row in rank2_candidates}),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
        }

    aggregate = _aggregate(window_rows)
    target_summary = base._target_trade_summary(rank2_trades_by_window)
    gate4 = _gate4(aggregate, target_summary, before_metrics)
    decision = (
        "promising_replay_only_vbb_rank2_strong_rs_candidate_extension"
        if gate4["passed"]
        else "rejected_vbb_rank2_strong_rs_candidate_extension"
    )
    interpretation = (
        "The rank-2 strong-RS VBB extension cleared replay Gate 4, but remains default-off. Promotion would require adding the same extension to the shared adapter with parity tests and forward replacement-value rows."
        if gate4["passed"]
        else "The rank-2 strong-RS VBB extension did not clear Gate 4. Do not promote it or retry nearby rank-2 RS/high-close/breadth thresholds on these frozen windows without forward evidence or a materially different source-quality field."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Under accepted VBB breadth days, rank-2 candidates may add replacement "
            "value only when the second candidate is also strong by same-day RS, "
            "high close location, and breadth intensity."
        ),
        "change_type": "vbb_rank2_strong_rs_candidate_extension",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260526-013",
            "exp-20260526-014",
            "exp-20260526-018",
            "exp-20260528-018",
            "exp-20260529-004",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_ohlcv_rank2_strength_candidate_pool_extension",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "before_state": f"{REFERENCE_VBB_EXPERIMENT_ID} accepted VBB top-1 after metrics",
            "core_baseline": CURRENT_CORE_BASELINE_EXPERIMENT_ID,
            "execution_model": "same as accepted VBB: signal after close, paper entry next open, exit after ten trading days at close, slippage/cost model unchanged",
        },
        "gate_questions": {
            "1_alpha_hypothesis": "candidate_pool: VBB rank-2 can be expanded only when same-day RS, close quality, and breadth intensity are all strong.",
            "2_history_check": "VBB top-1 accepted in exp-20260526-013/014; raw rank monotonicity rejected in exp-20260526-018, so this is not simple top-2. Later VBB breadth/cost supports were notional scalars, not candidate-source expansion.",
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": "Same three docs/backtesting.md windows, incremental versus accepted VBB after metrics; positive aggregate EV/PnL, all three windows EV-improved, no PnL regression, sample/concentration/drawdown/survival guards pass.",
            "5_reproducibility": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260602_005_vbb_rank2_strong_rs_high_close_candidate_extension_v1.py",
        },
        "parameters": {
            "reference_vbb_json": _repo_rel(CURRENT_VBB_JSON),
            "rank2_thresholds": {
                "min_rank2_rs_vs_spy": MIN_RANK2_RS_VS_SPY,
                "min_rank2_close_location": MIN_RANK2_CLOSE_LOCATION,
                "min_rank2_breadth_fraction": MIN_RANK2_BREADTH_FRACTION,
                "min_rank2_volume_ratio_20": MIN_RANK2_VOLUME_RATIO_20,
            },
            "locked_variables": [
                "accepted VBB top-1 source",
                "core universe",
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "VBB paper notional",
                "VBB hold days",
                "LLM/news replay",
                "live/default orders",
            ],
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": _repo_rel(CURRENT_VBB_JSON),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                "accepted VBB candidate rows",
                "same-date volume_breadth_fraction",
                "candidate_day_rs_vs_spy",
                "close_location derived from same-day OHLCV",
                "next-open entry and ten-trading-day close exit",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": True,
            "minimum_survival_rate_before": gate4["min_survival_rate"],
            "passed": gate4["min_survival_rate"] >= 0.05,
            "note": "Core survival is unchanged; this is additive default-off paper candidate-pool replay.",
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "rank2_diagnostics": rank2_diagnostics,
        "full_vbb_audit": FULL_VBB_AUDIT,
        "rank2_candidates_sample_by_window": rank2_candidates_by_window,
        "target_trades_by_window": rank2_trades_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "interpretation": interpretation,
        "production_impact": {
            "alters_orders": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "shared_adapter_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "default_off_paper_only": True,
            "promotion_requirement": "A retained result must be implemented in the shared VBB adapter with parity tests and forward replacement-value snapshots before any production exposure beyond replay artifacts.",
        },
        "anti_js": {"javascript_used": False},
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _markdown_report(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: VBB Rank-2 Strong-RS Candidate Extension",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Before: `{REFERENCE_VBB_EXPERIMENT_ID}` accepted VBB after metrics",
        "- JavaScript: not used",
        "",
        "## Gate 4 Summary",
        "",
        "| Metric | Before | After | Delta |",
        "|---|---:|---:|---:|",
        f"| Aggregate EV | {aggregate['baseline_expected_value_score_sum']:.4f} | {aggregate['after_expected_value_score_sum']:.4f} | {aggregate['expected_value_score_delta_sum']:+.4f} |",
        f"| Aggregate PnL | ${aggregate['baseline_total_pnl_sum']:,.2f} | ${aggregate['after_total_pnl_sum']:,.2f} | ${aggregate['total_pnl_delta_sum']:,.2f} |",
        f"| Max drawdown delta | | | {aggregate['max_drawdown_delta_max']:+.4f} |",
        "",
        "## Three Windows",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | Rank2 trades | Rank2 candidate days |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        diag = payload["rank2_diagnostics"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | {after['expected_value_score']:.4f} | {delta['expected_value_score']:+.4f} | ${delta['total_pnl']:,.2f} | {diag['selected_rank2_trade_count']} | {diag['selected_rank2_candidate_days']} |"
        )
    lines.extend(
        [
            "",
            "## Rank2 Diagnostics",
            "",
            "```json",
            json.dumps(payload["rank2_diagnostics"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Parity",
            "",
            (
                "No shared VBB adapter or production order path changed. This is "
                "incremental replay versus the accepted default-off VBB top-1 "
                "adapter; any positive result would still require shared-adapter "
                "implementation and parity tests before promotion."
            ),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def _write_card(payload: dict[str, Any], now: str) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    failed = ", ".join(payload["gate4"]["failed_gates"]) or "none"
    text = f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "{payload['status']}"
lane: "alpha_search"
change_type: "vbb_rank2_strong_rs_candidate_extension"
mechanism_family: "volume_breadth_breakout_candidate_pool"
trial_family: "{TRIAL_FAMILY}"
trial_variant_id: "{TRIAL_VARIANT_ID}"
changed_variable: "{CHANGED_VARIABLE}"
completed_at: "{now}"
artifact: "{_repo_rel(OUT_JSON)}"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Tested a default-off incremental VBB rank-2 strong-RS candidate extension. Decision: `{payload['decision']}`.

## Gate 4

- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`
- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:,.2f}`
- Rank2 trades: `{payload['target_trade_summary']['total_trade_count']}`
- Failed gates: `{failed}`

## Repro

`.\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260602_005_vbb_rank2_strong_rs_high_close_candidate_extension_v1.py`
"""
    _write_text(CARD_MD, text)


def _update_ticket(payload: dict[str, Any], now: str) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket["status"] = payload["status"]
    ticket["completed_at"] = now
    ticket["result"] = {
        "decision": payload["decision"],
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "artifact": _repo_rel(OUT_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
    }
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any], now: str) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    for item in registry.get("experiments", []):
        if item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = payload["status"]
            item["completed_at"] = now
            item["decision"] = payload["decision"]
            item["aggregate_expected_value_delta"] = payload["expected_value_score_delta"]
            item["aggregate_strategy_total_pnl_delta"] = payload["total_pnl_delta"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["report_file"] = _repo_rel(ARTIFACT_MD)
            break
    registry["updated_at"] = now
    _write_json(REGISTRY_JSON, registry)


def _write_manifest(now: str) -> None:
    files = {
        "runner": _repo_rel(Path(__file__)),
        "result": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "card": _repo_rel(CARD_MD),
        "artifact": _repo_rel(ARTIFACT_MD),
        "manifest": _repo_rel(MANIFEST_JSON),
        "reference_vbb": _repo_rel(CURRENT_VBB_JSON),
        "registry": _repo_rel(REGISTRY_JSON),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": now,
        "files": {
            label: {
                "path": rel_path,
                "exists": (ROOT / rel_path).exists(),
                "sha256": _sha256(ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any], now: str) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _markdown_report(payload))
    _write_card(payload, now)
    _update_ticket(payload, now)
    _update_registry(payload, now)
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest(now)


def main() -> int:
    now = _utc_now()
    payload = _build_payload(now)
    _persist(payload, now)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": _repo_rel(OUT_JSON),
                    "report": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
