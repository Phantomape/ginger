"""exp-20260527-905: VCP cost/liquidity notional scalar.

Alpha search. Starts from the accepted exp-20260526-007 QQQ-confirmed VCP
top-2 paper adapter with rank-notional profile [1.0, 1.25], then changes one
capital-allocation variable: the paper notional scalar for already-selected
trades with a high decision-date OHLCV cost/liquidity proxy.

This does not change VCP compression, breakout, QQQ/SPY confirmation, top-2
selection, rank profile, hold days, exits, core/live behavior, LLM/news, or
orders. Positive evidence still requires shared default-off adapter parity
before retention.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


EXPERIMENT_ID = "exp-20260527-905"
STEM = "vcp_cost_liquidity_scalar"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "vcp_high_expected_cost_notional_scalar"
RULE_VERSION = "vcp_cost_liquidity_scalar_v1"
SOURCE_EXP_ID = "exp-20260526-007"
SOURCE_REL = "data/experiments/exp-20260526-007/vcp_rank_notional_profile.json"
SOURCE_VARIANT = "rank2_125"
SOURCE_PROFILE = [1.0, 1.25]

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260526_007_vcp_rank_notional_profile as rank_source  # noqa: E402


OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HIGH_COST_BPS_THRESHOLD = 30.0
MIN_ADJUSTED_TRADES = 20
MIN_ADJUSTED_WINDOWS = 3
MIN_EV_LIFT_VS_SOURCE = 0.05
MAX_DRAWDOWN_WORSE_VS_SOURCE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

SCALAR_SWEEP: "OrderedDict[str, float]" = OrderedDict(
    [
        ("baseline_cost_scalar_1p00", 1.00),
        ("high_cost_scalar_0p80", 0.80),
        ("high_cost_scalar_1p10", 1.10),
        ("high_cost_scalar_1p20", 1.20),
        ("high_cost_scalar_1p30", 1.30),
    ]
)


base = rank_source.base
qqq_source = rank_source.qqq_source
topn_source = rank_source.topn_source
volatility_shadow = rank_source.volatility_shadow


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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _normalise_rows(rows: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        close = _float_or_none(raw.get("Close") or raw.get("close"))
        volume = _float_or_none(raw.get("Volume") or raw.get("volume"))
        if close is None or volume is None:
            continue
        out.append(
            {
                "date": _date10(raw.get("Date") or raw.get("date")),
                "close": close,
                "volume": volume,
            }
        )
    return sorted([row for row in out if row["date"]], key=lambda row: row["date"])


def _median_dollar_volume_20(
    snapshot: dict[str, Any],
    *,
    ticker: str,
    decision_date: str,
) -> float | None:
    rows = _normalise_rows(snapshot.get(str(ticker).upper()))
    idx = None
    for row_idx, row in enumerate(rows):
        if row["date"] <= decision_date:
            idx = row_idx
        else:
            break
    if idx is None:
        return None
    window = rows[max(0, idx - 19) : idx + 1]
    values = [
        float(row["close"]) * float(row["volume"])
        for row in window
        if float(row["close"]) > 0.0 and float(row["volume"]) > 0.0
    ]
    if not values:
        return None
    return float(median(values))


def _expected_round_trip_cost_bps(
    trade: dict[str, Any],
    median_dollar_volume_20: float | None,
) -> float:
    short_atr = float(trade.get("short_atr_pct") or 0.0)
    if median_dollar_volume_20 is None or median_dollar_volume_20 <= 0:
        liquidity_bps = 24.0
    else:
        liquidity_bps = min(32.0, 80.0 / math.sqrt(max(median_dollar_volume_20 / 1_000_000.0, 1.0)))
    volatility_bps = min(42.0, max(0.0, short_atr * 10000.0 * 0.08))
    return round(3.0 + liquidity_bps + volatility_bps, 4)


def _cost_bucket(cost_bps: float) -> str:
    if cost_bps >= 50.0:
        return "very_high"
    if cost_bps >= HIGH_COST_BPS_THRESHOLD:
        return "high"
    if cost_bps >= 25.0:
        return "medium"
    return "low"


def _scale_trade(
    trade: dict[str, Any],
    *,
    snapshot: dict[str, Any],
    high_cost_scalar: float,
    variant: str,
) -> dict[str, Any]:
    decision_date = _date10(trade.get("signal_date") or trade.get("date"))
    median_dv_20 = _median_dollar_volume_20(
        snapshot,
        ticker=str(trade.get("ticker") or ""),
        decision_date=decision_date,
    )
    cost_bps = _expected_round_trip_cost_bps(trade, median_dv_20)
    bucket = _cost_bucket(cost_bps)
    applied = cost_bps >= HIGH_COST_BPS_THRESHOLD and high_cost_scalar != 1.0
    scalar = high_cost_scalar if applied else 1.0
    base_notional = float(trade.get("paper_notional_usd") or 0.0)
    base_pnl = float(trade.get("pnl") or 0.0)
    out = dict(trade)
    out.update(
        {
            "cost_liquidity_variant": variant,
            "cost_liquidity_rule_version": RULE_VERSION,
            "expected_round_trip_cost_bps": cost_bps,
            "expected_round_trip_cost_bucket": bucket,
            "median_dollar_volume_20": round(median_dv_20, 2) if median_dv_20 else None,
            "cost_liquidity_scalar_applied": bool(applied),
            "cost_liquidity_notional_scalar": round(scalar, 6),
            "pre_cost_liquidity_notional": round(base_notional, 2),
            "pre_cost_liquidity_pnl": round(base_pnl, 2),
            "paper_notional_usd": round(base_notional * scalar, 2),
            "pnl": round(base_pnl * scalar, 2),
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return out


def _cost_bucket_counts(trades: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for trade in trades:
        counts[str(trade.get("expected_round_trip_cost_bucket") or "unknown")] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _cost_bucket_pnl(trades: list[dict[str, Any]]) -> dict[str, float]:
    pnl: dict[str, float] = {}
    for trade in trades:
        bucket = str(trade.get("expected_round_trip_cost_bucket") or "unknown")
        pnl[bucket] = pnl.get(bucket, 0.0) + float(trade.get("pnl") or 0.0)
    return {key: round(value, 2) for key, value in sorted(pnl.items())}


def _trade_sample(trades: list[dict[str, Any]], *, limit: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in sorted(trades, key=lambda row: (row.get("entry_date"), row.get("ticker")))[:limit]:
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "window": trade.get("window"),
                "signal_date": trade.get("signal_date") or trade.get("date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("vcp_candidate_rank_on_signal_date"),
                "paper_notional_usd": trade.get("paper_notional_usd"),
                "pre_cost_liquidity_notional": trade.get("pre_cost_liquidity_notional"),
                "pnl": trade.get("pnl"),
                "pre_cost_liquidity_pnl": trade.get("pre_cost_liquidity_pnl"),
                "expected_round_trip_cost_bps": trade.get("expected_round_trip_cost_bps"),
                "expected_round_trip_cost_bucket": trade.get("expected_round_trip_cost_bucket"),
                "median_dollar_volume_20": trade.get("median_dollar_volume_20"),
                "cost_liquidity_scalar_applied": trade.get("cost_liquidity_scalar_applied"),
                "cost_liquidity_notional_scalar": trade.get("cost_liquidity_notional_scalar"),
                "short_atr_pct": trade.get("short_atr_pct"),
                "dollar_volume": trade.get("dollar_volume"),
            }
        )
    return rows


def _aggregate_metric_delta(delta_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    windows_ev_regressed = [
        label for label, row in delta_by_window.items() if float(row.get("expected_value_score") or 0.0) < 0
    ]
    windows_pnl_regressed = [
        label for label, row in delta_by_window.items() if float(row.get("total_pnl") or 0.0) < 0
    ]
    return {
        "aggregate_ev_delta": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in delta_by_window.values()),
            6,
        ),
        "aggregate_pnl_delta": round(
            sum(float(row.get("total_pnl") or 0.0) for row in delta_by_window.values()),
            2,
        ),
        "windows_ev_improved": sum(
            1 for row in delta_by_window.values() if float(row.get("expected_value_score") or 0.0) > 0
        ),
        "windows_ev_regressed": len(windows_ev_regressed),
        "windows_ev_regressed_labels": windows_ev_regressed,
        "windows_pnl_improved": sum(
            1 for row in delta_by_window.values() if float(row.get("total_pnl") or 0.0) > 0
        ),
        "windows_pnl_regressed": len(windows_pnl_regressed),
        "windows_pnl_regressed_labels": windows_pnl_regressed,
        "max_drawdown_worse_max": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in delta_by_window.values()),
            6,
        ),
    }


def _evaluate_variant(
    *,
    variant: str,
    high_cost_scalar: float,
    core_results: dict[str, dict[str, Any]],
    core_metrics: dict[str, dict[str, Any]],
    source_metrics: dict[str, dict[str, Any]],
    source_trades_by_window: dict[str, list[dict[str, Any]]],
    snapshots: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    delta_vs_source: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    delta_vs_core: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    all_trades: list[dict[str, Any]] = []

    for label in base.WINDOWS:
        trades: list[dict[str, Any]] = []
        for raw in source_trades_by_window[label]:
            adjusted = _scale_trade(
                raw,
                snapshot=snapshots[label],
                high_cost_scalar=high_cost_scalar,
                variant=variant,
            )
            adjusted["window"] = label
            trades.append(adjusted)
        overlay = base._overlay_from_paper_trades(core_results[label], trades)
        after = base.overlay_helper._metrics_with_overlay(core_results[label], overlay)
        after_metrics[label] = after
        delta_vs_source[label] = base.overlay_helper._delta(after, source_metrics[label])
        delta_vs_core[label] = base.overlay_helper._delta(after, core_metrics[label])
        trades_by_window[label] = trades
        all_trades.extend(trades)

    adjusted = [row for row in all_trades if row.get("cost_liquidity_scalar_applied")]
    adjusted_windows = sorted({str(row.get("window")) for row in adjusted})
    source_ev_sum = sum(float(row.get("expected_value_score") or 0.0) for row in source_metrics.values())
    delta_summary = _aggregate_metric_delta(delta_vs_source)
    target_summary = base._target_trade_summary(trades_by_window)
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    adjusted_guard_passed = (
        len(adjusted) >= MIN_ADJUSTED_TRADES
        and len(adjusted_windows) >= MIN_ADJUSTED_WINDOWS
    )
    lift_passed = (
        source_ev_sum > 0
        and delta_summary["aggregate_ev_delta"] >= source_ev_sum * MIN_EV_LIFT_VS_SOURCE
    )
    failed: list[str] = []
    if variant == "baseline_cost_scalar_1p00":
        failed.append("baseline_variant_not_acceptance_candidate")
    if not lift_passed:
        failed.append("did_not_lift_source_ev_by_5pct")
    if delta_summary["aggregate_pnl_delta"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if delta_summary["windows_ev_regressed"]:
        failed.append("window_ev_regression_vs_source")
    if delta_summary["windows_pnl_regressed"]:
        failed.append("window_pnl_regression_vs_source")
    if delta_summary["max_drawdown_worse_max"] > MAX_DRAWDOWN_WORSE_VS_SOURCE:
        failed.append("drawdown_drift_vs_source_too_high")
    if not adjusted_guard_passed:
        failed.append("adjusted_sample_too_small")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    return {
        "variant": variant,
        "high_cost_scalar": high_cost_scalar,
        "high_cost_bps_threshold": HIGH_COST_BPS_THRESHOLD,
        "after_metrics": after_metrics,
        "delta_vs_source_by_window": delta_vs_source,
        "delta_vs_core_by_window": delta_vs_core,
        "delta_vs_source_summary": delta_summary,
        "target_trades_by_window": trades_by_window,
        "target_trade_summary": target_summary,
        "selected_trade_count": len(all_trades),
        "adjusted_trade_count": len(adjusted),
        "adjusted_windows": adjusted_windows,
        "pre_adjusted_pnl": round(sum(float(row.get("pre_cost_liquidity_pnl") or 0.0) for row in adjusted), 2),
        "adjusted_pnl": round(sum(float(row.get("pnl") or 0.0) for row in adjusted), 2),
        "incremental_adjusted_pnl": round(
            sum(
                float(row.get("pnl") or 0.0)
                - float(row.get("pre_cost_liquidity_pnl") or 0.0)
                for row in adjusted
            ),
            2,
        ),
        "notional_added_removed": round(
            sum(
                float(row.get("paper_notional_usd") or 0.0)
                - float(row.get("pre_cost_liquidity_notional") or 0.0)
                for row in adjusted
            ),
            2,
        ),
        "cost_bucket_counts": _cost_bucket_counts(all_trades),
        "cost_bucket_pnl": _cost_bucket_pnl(all_trades),
        "adjusted_cost_bucket_counts": _cost_bucket_counts(adjusted),
        "adjusted_trades_sample": _trade_sample(adjusted),
        "selected_trades_sample": _trade_sample(all_trades),
        "gate4": {
            "passed": not failed,
            "failed_reasons": failed,
            "source_ev_sum": round(source_ev_sum, 6),
            "min_ev_lift_vs_source": MIN_EV_LIFT_VS_SOURCE,
            "min_ev_lift_required": round(source_ev_sum * MIN_EV_LIFT_VS_SOURCE, 6),
            "aggregate_ev_delta_vs_source": delta_summary["aggregate_ev_delta"],
            "aggregate_pnl_delta_vs_source": delta_summary["aggregate_pnl_delta"],
            "windows_ev_regressed": delta_summary["windows_ev_regressed_labels"],
            "windows_pnl_regressed": delta_summary["windows_pnl_regressed_labels"],
            "max_drawdown_worse_vs_source": delta_summary["max_drawdown_worse_max"],
            "max_drawdown_worse_vs_source_guardrail": MAX_DRAWDOWN_WORSE_VS_SOURCE,
            "adjusted_trade_count": len(adjusted),
            "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
            "adjusted_windows": adjusted_windows,
            "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
            "adjusted_guard_passed": adjusted_guard_passed,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
                "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
                "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            },
        },
    }


def _choose_best(variants: dict[str, dict[str, Any]]) -> str:
    candidates = [name for name in variants if name != "baseline_cost_scalar_1p00"]
    return max(
        candidates,
        key=lambda name: (
            1 if variants[name]["gate4"]["passed"] else 0,
            float(variants[name]["delta_vs_source_summary"]["aggregate_ev_delta"]),
            float(variants[name]["delta_vs_source_summary"]["aggregate_pnl_delta"]),
            -float(variants[name]["delta_vs_source_summary"]["max_drawdown_worse_max"]),
        ),
    )


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _build_payload() -> dict[str, Any]:
    source_path = REPO_ROOT / SOURCE_REL
    if not source_path.exists():
        raise RuntimeError(f"Missing source artifact: {SOURCE_REL}")
    source_payload = _load_json(source_path)
    if source_payload.get("decision") != "accepted_shared_paper_adapter_vcp_rank_notional_profile":
        raise RuntimeError(f"Unexpected source decision: {source_payload.get('decision')}")

    rank_source._configure_base_module()
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(base.get_universe())
    core_results: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    core_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    source_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    snapshots: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    ranked_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    source_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    qqq_source._configure_base_module()
    rank_source._configure_base_module()
    qqq_source.MARKET_GATE_AUDIT.clear()
    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] source baseline replay")
        core_result = volatility_shadow._run_baseline(universe, cfg)
        core_metric = base.overlay_helper._metrics(core_result)
        snapshot = volatility_shadow._load_snapshot(cfg["snapshot"])
        candidates = qqq_source._candidate_rows_for_window(snapshot, cfg, universe, core_result)
        ranked = topn_source._rank_candidates_by_date(candidates)
        selected, _filtered = rank_source._select_profile_paper_trades(
            snapshot,
            ranked,
            profile=SOURCE_PROFILE,
            variant=SOURCE_VARIANT,
        )
        overlay = base._overlay_from_paper_trades(core_result, selected)
        source_metric = base.overlay_helper._metrics_with_overlay(core_result, overlay)
        core_results[label] = core_result
        core_metrics[label] = core_metric
        source_metrics[label] = source_metric
        snapshots[label] = snapshot
        ranked_candidates_by_window[label] = ranked
        source_trades_by_window[label] = selected

    source_artifact_metrics = source_payload["profile_results"][SOURCE_VARIANT]["after_metrics"]
    parity_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    parity_passed = True
    for label in base.WINDOWS:
        ev_drift = round(
            float(source_metrics[label]["expected_value_score"])
            - float(source_artifact_metrics[label]["expected_value_score"]),
            8,
        )
        pnl_drift = round(
            float(source_metrics[label]["total_pnl"])
            - float(source_artifact_metrics[label]["total_pnl"]),
            8,
        )
        trade_drift = int(source_metrics[label]["trade_count"]) - int(
            source_artifact_metrics[label]["trade_count"]
        )
        passed = abs(ev_drift) <= 0.0001 and abs(pnl_drift) <= 0.01 and trade_drift == 0
        parity_passed = parity_passed and passed
        parity_by_window[label] = {
            "passed": passed,
            "rerun_ev": round(float(source_metrics[label]["expected_value_score"]), 6),
            "artifact_ev": round(float(source_artifact_metrics[label]["expected_value_score"]), 6),
            "ev_drift": ev_drift,
            "rerun_pnl": round(float(source_metrics[label]["total_pnl"]), 2),
            "artifact_pnl": round(float(source_artifact_metrics[label]["total_pnl"]), 2),
            "pnl_drift": pnl_drift,
            "trade_count_drift": trade_drift,
        }

    variants: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for name, scalar in SCALAR_SWEEP.items():
        variants[name] = _evaluate_variant(
            variant=name,
            high_cost_scalar=float(scalar),
            core_results=core_results,
            core_metrics=core_metrics,
            source_metrics=source_metrics,
            source_trades_by_window=source_trades_by_window,
            snapshots=snapshots,
        )
        if not parity_passed:
            variants[name]["gate4"]["passed"] = False
            variants[name]["gate4"]["failed_reasons"].append("source_replay_parity_failed")

    best_name = _choose_best(variants)
    best = variants[best_name]
    accepted = [name for name, row in variants.items() if row["gate4"]["passed"]]
    decision = (
        "observed_positive_vcp_cost_liquidity_scalar_requires_shared_adapter"
        if accepted
        else "rejected_vcp_cost_liquidity_scalar"
    )
    status = "observed_only" if accepted else "rejected"
    timestamp = _utc_now()
    source_summary = base._target_trade_summary(source_trades_by_window)
    gate3_survival_min = min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values())

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "VCP top-2 paper trades with high decision-date OHLCV cost/liquidity "
            "proxy may have a distinct expected-value profile. A bounded paper "
            "notional scalar on that fixed cohort should improve EV without "
            "changing the accepted VCP source, QQQ/SPY gate, top-2 breadth, rank "
            "profile, hold period, or live behavior."
        ),
        "change_type": "default_off_paper_capital_allocation_scout",
        "mechanism_family": "volatility_contraction_cost_aware_allocation",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "vcp_cost_liquidity_scalar_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": (
            "paper notional scalar for already-selected accepted VCP top-2 trades "
            f"with expected_round_trip_cost_bps >= {HIGH_COST_BPS_THRESHOLD}"
        ),
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260525-037",
            "exp-20260526-007",
            "exp-20260527-024",
            "exp-20260527-902",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_cost_liquidity_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three fixed windows",
            "windows": base.WINDOWS,
            "comparison_baseline": SOURCE_EXP_ID,
            "source_artifact": SOURCE_REL,
            "replay_llm": False,
            "replay_news": False,
        },
        "parameters": {
            "source_experiment_id": SOURCE_EXP_ID,
            "source_variant": SOURCE_VARIANT,
            "source_rank_profile": SOURCE_PROFILE,
            "cost_proxy": {
                "inputs": [
                    "decision-date 20-session median dollar volume",
                    "decision-date short_atr_pct",
                ],
                "formula": (
                    "3 bps base + min(32, 80/sqrt(median_dollar_volume_20/1e6)) "
                    "+ min(42, short_atr_pct*10000*0.08)"
                ),
                "high_threshold_bps": HIGH_COST_BPS_THRESHOLD,
                "lookahead_policy": (
                    "Uses only OHLCV through the signal decision date; no post-entry "
                    "prices or future volume are inputs."
                ),
            },
            "scalar_sweep": SCALAR_SWEEP,
            "selected_variant": best_name,
            "selected_high_cost_scalar": best["high_cost_scalar"],
            "locked_variables": [
                "core universe",
                "VCP compression and breakout definition",
                "QQQ/SPY 20d confirmation",
                "top-2 daily candidate count",
                "rank-notional profile [1.0, 1.25]",
                "candidate ranking order",
                "hold days",
                "core ranking/sizing/exits",
                "portfolio heat",
                "LLM/news behavior",
                "live/default orders",
            ],
            "acceptance": {
                "must_compare_to": SOURCE_EXP_ID,
                "min_aggregate_ev_lift_vs_source": MIN_EV_LIFT_VS_SOURCE,
                "no_window_ev_or_pnl_regression_vs_source": True,
                "min_adjusted_trades": MIN_ADJUSTED_TRADES,
                "min_adjusted_windows": MIN_ADJUSTED_WINDOWS,
                "max_drawdown_worse_vs_source": MAX_DRAWDOWN_WORSE_VS_SOURCE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
                "requires_source_replay_parity": True,
            },
            "anti_js": "No JavaScript was used.",
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital/risk allocation: accepted VCP top-2 paper trades with "
                "high ex-ante cost/liquidity proxy may deserve a notional scalar."
            ),
            "2_past_similar_experiments": (
                "exp-20260526-007 accepted the rank profile [1.0, 1.25]. "
                "exp-20260527-024 rejected a broad-market cost/liquidity haircut. "
                "exp-20260527-902 showed Kova intraday timing is data-blocked. "
                "No prior VCP cost/liquidity scalar was found."
            ),
            "3_single_variable": CHANGED_VARIABLE,
            "4_acceptance": (
                "Same three windows from docs/backtesting.md. Must improve aggregate "
                "EV by at least 5% of the source EV, add positive PnL, avoid any "
                "EV/PnL-regressed window versus exp-20260526-007, keep drawdown "
                "drift <=0.50pp, and pass sample/concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260527_905_vcp_cost_liquidity_scalar.py"
            ),
        },
        "gate1": {
            "passed": parity_passed,
            "baseline_experiment_id": SOURCE_EXP_ID,
            "baseline_artifact": SOURCE_REL,
            "source_replay_parity": {
                "passed": parity_passed,
                "by_window": parity_by_window,
            },
            "source_trade_summary": source_summary,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "OHLCV Date/Open/High/Low/Close/Volume through signal date",
                "short_atr_pct",
                "20-session median dollar volume",
                "VCP rank on signal date",
            ],
            "passed": gate2_open_positions["passed"],
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(gate3_survival_min, 4),
            "passed": gate3_survival_min >= 0.05,
            "note": "No entry filter was added; accepted VCP selected trades remain fixed.",
        },
        "gate4": best["gate4"],
        "before_metrics": source_metrics,
        "after_metrics": best["after_metrics"],
        "delta_metrics": {
            "vs_source_by_window": best["delta_vs_source_by_window"],
            "vs_core_by_window": best["delta_vs_core_by_window"],
            "vs_source_summary": best["delta_vs_source_summary"],
        },
        "expected_value_score_delta": {
            "aggregate_vs_source": best["delta_vs_source_summary"]["aggregate_ev_delta"],
            **{
                label: best["delta_vs_source_by_window"][label]["expected_value_score"]
                for label in base.WINDOWS
            },
        },
        "total_pnl_delta": {
            "aggregate_vs_source": best["delta_vs_source_summary"]["aggregate_pnl_delta"],
            **{
                label: best["delta_vs_source_by_window"][label]["total_pnl"]
                for label in base.WINDOWS
            },
        },
        "sweep_summary": [
            {
                "variant": row["variant"],
                "high_cost_scalar": row["high_cost_scalar"],
                "passed": row["gate4"]["passed"],
                "failed_reasons": row["gate4"]["failed_reasons"],
                "adjusted_trade_count": row["adjusted_trade_count"],
                "adjusted_windows": row["adjusted_windows"],
                "aggregate_ev_delta_vs_source": row["delta_vs_source_summary"]["aggregate_ev_delta"],
                "aggregate_pnl_delta_vs_source": row["delta_vs_source_summary"]["aggregate_pnl_delta"],
                "windows_ev_regressed": row["delta_vs_source_summary"]["windows_ev_regressed_labels"],
                "windows_pnl_regressed": row["delta_vs_source_summary"]["windows_pnl_regressed_labels"],
                "max_drawdown_worse_vs_source": row["delta_vs_source_summary"]["max_drawdown_worse_max"],
                "cost_bucket_counts": row["cost_bucket_counts"],
                "adjusted_cost_bucket_counts": row["adjusted_cost_bucket_counts"],
                "pre_adjusted_pnl": row["pre_adjusted_pnl"],
                "adjusted_pnl": row["adjusted_pnl"],
                "incremental_adjusted_pnl": row["incremental_adjusted_pnl"],
                "notional_added_removed": row["notional_added_removed"],
            }
            for row in variants.values()
        ],
        "selected_variant": {
            "variant": best["variant"],
            "high_cost_scalar": best["high_cost_scalar"],
            "selected_trade_count": best["selected_trade_count"],
            "adjusted_trade_count": best["adjusted_trade_count"],
            "adjusted_windows": best["adjusted_windows"],
            "pre_adjusted_pnl": best["pre_adjusted_pnl"],
            "adjusted_pnl": best["adjusted_pnl"],
            "incremental_adjusted_pnl": best["incremental_adjusted_pnl"],
            "notional_added_removed": best["notional_added_removed"],
            "target_trade_summary": best["target_trade_summary"],
            "cost_bucket_counts": best["cost_bucket_counts"],
            "cost_bucket_pnl": best["cost_bucket_pnl"],
            "adjusted_cost_bucket_counts": best["adjusted_cost_bucket_counts"],
            "adjusted_trades_sample": best["adjusted_trades_sample"],
        },
        "variant_results": variants,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "research_replay_alters_paper_notional": True,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_core_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "promotion_blocker": (
                "If retained, implement the same cost/liquidity scalar through "
                "quant/volatility_contraction_paper_sleeve.py plus parity tests. "
                "This replay does not alter production/default-off behavior."
            ),
        },
        "interpretation": (
            "At least one cost/liquidity scalar passed the replay gate. This is "
            "only observed positive until the shared default-off VCP adapter is "
            "updated with parity tests."
            if accepted
            else (
                "No cost/liquidity scalar passed Gate 4. Keep the accepted VCP "
                "top-2 rank-notional adapter unchanged."
            )
        ),
        "rejection_reason": None if accepted else "; ".join(best["gate4"]["failed_reasons"]),
        "next_evidence_needed": (
            "Implement shared default-off VCP adapter parity before retaining this "
            "scalar; no live/default orders without forward replacement-value gates."
            if accepted
            else (
                "Do not retry adjacent VCP cost/liquidity thresholds or scalars on "
                "the frozen windows without new forward closed outcomes."
            )
        ),
        "why_not_other_changes": [
            "No VCP threshold, QQQ/SPY, top-N, rank-profile, pocket-pivot, or Kova retune.",
            "No state-surface or broad-market scalar mining.",
            "No LLM soft-ranking or prompt change.",
            "No live/default order path change.",
        ],
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "doc_ticket": _repo_rel(DOC_TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
            "source": SOURCE_REL,
        },
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} VCP Cost/Liquidity Scalar",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: high expected-cost paper-notional scalar on the",
        "already accepted VCP top-2 rank-notional paper trades.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate | Adjusted | dEV vs source | dPnL vs source | EV regressed | PnL regressed | Max DD worse |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {gate} | {adjusted} | {ev:+.4f} | ${pnl:+,.2f} | {evr} | {pnlr} | {dd:+.4%} |".format(
                variant=row["variant"],
                gate="PASS" if row["passed"] else "fail",
                adjusted=row["adjusted_trade_count"],
                ev=float(row["aggregate_ev_delta_vs_source"] or 0.0),
                pnl=float(row["aggregate_pnl_delta_vs_source"] or 0.0),
                evr=",".join(row["windows_ev_regressed"]) or "-",
                pnlr=",".join(row["windows_pnl_regressed"]) or "-",
                dd=float(row["max_drawdown_worse_vs_source"] or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Evidence",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["vs_source_by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
            )
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "date_range": payload["backtest_protocol"]["windows"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }


def main() -> int:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_json(DOC_TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "selected_variant": payload["selected_variant"],
                    "gate4": payload["gate4"],
                    "sweep_summary": payload["sweep_summary"],
                    "source_replay_parity": payload["gate1"]["source_replay_parity"],
                    "output": payload["related_files"]["output"],
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
