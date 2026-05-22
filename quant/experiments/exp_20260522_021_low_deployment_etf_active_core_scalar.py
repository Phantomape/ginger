"""exp-20260522-021 low-deployment ETF active-core scalar scout.

Alpha search, replay-only. Tests one capital-competition variable inside the
accepted default-off low-deployment ETF overlay:

    scale paper notional only when the core book already has one active A/B
    position.

The ETF pool, raw momentum selector, activation threshold, core strategy, LLM,
news, exits, and live/default order path stay locked.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
import exp_20260522_004_low_deployment_etf_volatility_cap as helper  # noqa: E402


EXPERIMENT_ID = "exp-20260522-021"
STEM = "low_deployment_etf_active_core_scalar"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "accepted_raw_momentum_v1"
ACTIVE_CORE_ONE_SCALARS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("active_core_one_000", 0.00),
        ("active_core_one_025", 0.25),
        ("active_core_one_050", 0.50),
        ("active_core_one_075", 0.75),
        ("active_core_one_125", 1.25),
        ("active_core_one_150", 1.50),
    ]
)

WINDOWS = helper.WINDOWS
INITIAL_CAPITAL = helper.INITIAL_CAPITAL
MAX_ACTIVE_CORE_POSITIONS = helper.MAX_ACTIVE_CORE_POSITIONS
OVERLAY_NOTIONAL_FRACTION = helper.OVERLAY_NOTIONAL_FRACTION


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


def _safe(value: Any) -> Any:
    return helper._safe(value)


def _repo_rel(path: Path | str) -> str:
    return helper._repo_rel(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = (
        path.read_text(encoding="utf-8", errors="replace").splitlines()
        if path.exists()
        else []
    )
    kept = [line for line in lines if compact not in line and pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _curve_risk(curve: list[tuple[str, float]]) -> dict[str, Any]:
    values = [float(equity) for _, equity in curve]
    daily_returns = [
        values[idx] / values[idx - 1] - 1.0
        for idx in range(1, len(values))
        if values[idx - 1] != 0
    ]
    sharpe_daily = None
    if len(daily_returns) >= 2:
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((item - mean_return) ** 2 for item in daily_returns) / (
            len(daily_returns) - 1
        )
        std = math.sqrt(variance)
        if std > 0:
            sharpe_daily = round((mean_return / std) * math.sqrt(252), 2)

    peak = 0.0
    max_drawdown = 0.0
    for equity in values:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return {"sharpe_daily": sharpe_daily, "max_drawdown_pct": round(max_drawdown, 4)}


def _metrics_with_overlay(result: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    updated = dict(result)
    total_pnl = float(result.get("total_pnl") or 0.0) + float(
        overlay["overlay_total_pnl"] or 0.0
    )
    risk = _curve_risk(overlay["combined_equity_curve"])
    benchmarks = dict(result.get("benchmarks") or {})
    strategy_return = total_pnl / INITIAL_CAPITAL
    benchmarks["strategy_total_return_pct"] = round(strategy_return, 4)
    if benchmarks.get("spy_buy_hold_return_pct") is not None:
        benchmarks["strategy_vs_spy_pct"] = round(
            strategy_return - benchmarks["spy_buy_hold_return_pct"], 4
        )
    if benchmarks.get("qqq_buy_hold_return_pct") is not None:
        benchmarks["strategy_vs_qqq_pct"] = round(
            strategy_return - benchmarks["qqq_buy_hold_return_pct"], 4
        )
    updated["benchmarks"] = benchmarks
    updated["total_pnl"] = round(total_pnl, 2)
    updated["sharpe_daily"] = risk["sharpe_daily"]
    updated["max_drawdown_pct"] = risk["max_drawdown_pct"]
    updated["expected_value_score"] = compute_expected_value_score(updated)
    return helper._metrics(updated)


def _overlay_path(
    result: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    variant: str,
    active_core_one_scalar: float,
) -> dict[str, Any]:
    base_curve = result.get("equity_curve") or []
    core_counts = helper._core_active_count_by_date(result)
    index_by_ticker_date = {
        ticker: helper._rows_by_date(rows) for ticker, rows in rows_by_ticker.items()
    }
    overlay_pnl_by_date: dict[str, float] = {}
    overlay_days: list[dict[str, Any]] = []
    candidate_counts: Counter[str] = Counter()
    active_count_distribution: Counter[int] = Counter()
    low_deployment_day_count = 0

    for day, _ in base_curve:
        day = str(day)
        active_count = core_counts.get(day, 0)
        if active_count > MAX_ACTIVE_CORE_POSITIONS:
            continue
        low_deployment_day_count += 1
        selection = helper._select_overlay_ticker(
            rows_by_ticker,
            index_by_ticker_date,
            day,
            volatility_cap=None,
        )
        if selection is None:
            continue
        ticker = selection["ticker"]
        rows = rows_by_ticker[ticker]
        row = rows[selection["idx"]]
        notional_scalar = active_core_one_scalar if active_count == 1 else 1.0
        notional = INITIAL_CAPITAL * OVERLAY_NOTIONAL_FRACTION * notional_scalar
        pnl = notional * (float(row["close"]) / float(row["open"]) - 1.0)
        overlay_pnl_by_date[day] = pnl
        candidate_counts[ticker] += 1
        active_count_distribution[active_count] += 1
        state = selection["state"]
        overlay_days.append(
            {
                "date": day,
                "ticker": ticker,
                "active_core_positions": active_count,
                "prior_close": _round(state["prior_close"], 4),
                "prior_sma200": _round(state["prior_sma200"], 4),
                "prior_momentum20": _round(state["prior_momentum20"], 6),
                "notional_scalar": active_core_one_scalar if active_count == 1 else 1.0,
                "variant": variant,
                "open": _round(row["open"], 4),
                "close": _round(row["close"], 4),
                "notional": _round(notional, 2),
                "pnl": _round(pnl, 2),
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in base_curve:
        cumulative_overlay += overlay_pnl_by_date.get(str(day), 0.0)
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))

    return {
        "combined_equity_curve": combined_curve,
        "overlay_total_pnl": round(sum(overlay_pnl_by_date.values()), 2),
        "overlay_day_count": len(overlay_days),
        "low_deployment_day_count": low_deployment_day_count,
        "ticker_day_counts": dict(candidate_counts),
        "active_count_distribution": dict(active_count_distribution),
        "overlay_days": overlay_days,
    }


def _window_row(
    result: dict[str, Any],
    window: dict[str, str],
    *,
    variant: str,
    active_core_one_scalar: float,
) -> dict[str, Any]:
    overlay = _overlay_path(
        result,
        helper._load_snapshot_rows(window["snapshot"]),
        variant=variant,
        active_core_one_scalar=active_core_one_scalar,
    )
    before = helper._metrics(result)
    after = _metrics_with_overlay(result, overlay)
    return {
        "before": before,
        "after": after,
        "delta": helper._delta(after, before),
        "overlay_total_pnl": overlay["overlay_total_pnl"],
        "overlay_day_count": overlay["overlay_day_count"],
        "low_deployment_day_count": overlay["low_deployment_day_count"],
        "ticker_day_counts": overlay["ticker_day_counts"],
        "active_count_distribution": overlay["active_count_distribution"],
        "overlay_days": overlay["overlay_days"],
        "overlay_days_sample": overlay["overlay_days"][:20],
    }


def _variant_delta_vs_baseline(
    candidate_windows: dict[str, dict[str, Any]],
    baseline_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict()
    for label, row in candidate_windows.items():
        base = baseline_windows[label]
        by_window[label] = helper._delta(row["after"], base["after"])
        by_window[label]["overlay_total_pnl"] = round(
            row["overlay_total_pnl"] - base["overlay_total_pnl"], 2
        )
        by_window[label]["overlay_day_count"] = (
            row["overlay_day_count"] - base["overlay_day_count"]
        )

    ev_before = sum(row["after"]["expected_value_score"] for row in baseline_windows.values())
    ev_delta = sum(row["expected_value_score"] for row in by_window.values())
    pnl_before = sum(row["after"]["total_pnl"] for row in baseline_windows.values())
    pnl_delta = sum(row["total_pnl"] for row in by_window.values())
    return {
        "by_window": by_window,
        "aggregate": {
            "baseline_overlay_expected_value_score_sum": _round(ev_before, 6),
            "candidate_overlay_expected_value_score_delta_sum": _round(ev_delta, 6),
            "candidate_overlay_expected_value_score_delta_pct": (
                _round(ev_delta / ev_before, 6) if ev_before else None
            ),
            "baseline_overlay_total_pnl_sum": _round(pnl_before, 2),
            "candidate_overlay_total_pnl_delta_sum": _round(pnl_delta, 2),
            "candidate_overlay_total_pnl_delta_pct": (
                _round(pnl_delta / pnl_before, 6) if pnl_before else None
            ),
            "windows_ev_improved": sum(
                1 for row in by_window.values() if row.get("expected_value_score", 0) > 0
            ),
            "windows_ev_regressed": sum(
                1 for row in by_window.values() if row.get("expected_value_score", 0) < 0
            ),
            "windows_pnl_improved": sum(
                1 for row in by_window.values() if row.get("total_pnl", 0) > 0
            ),
            "windows_pnl_regressed": sum(
                1 for row in by_window.values() if row.get("total_pnl", 0) < 0
            ),
            "max_drawdown_delta_max": _round(
                max(row.get("max_drawdown_pct", 0.0) for row in by_window.values()),
                6,
            ),
            "min_overlay_day_count": min(
                row["overlay_day_count"] for row in candidate_windows.values()
            ),
            "overlay_day_count_sum": sum(
                row["overlay_day_count"] for row in candidate_windows.values()
            ),
        },
    }


def _single_ticker_positive_share(windows: dict[str, dict[str, Any]]) -> float | None:
    by_ticker: Counter[str] = Counter()
    total_positive = 0.0
    for row in windows.values():
        for day in row["overlay_days"]:
            pnl = float(day.get("pnl") or 0.0)
            if pnl <= 0:
                continue
            total_positive += pnl
            by_ticker[str(day.get("ticker") or "").upper()] += pnl
    if total_positive <= 0 or not by_ticker:
        return None
    return round(max(by_ticker.values()) / total_positive, 4)


def _gate4(
    variant_delta: dict[str, Any],
    candidate_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    aggregate = variant_delta["aggregate"]
    concentration = _single_ticker_positive_share(candidate_windows)
    concentration_ok = concentration is None or concentration <= 0.75
    directional = bool(
        aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and aggregate["candidate_overlay_expected_value_score_delta_sum"] > 0
        and aggregate["candidate_overlay_total_pnl_delta_sum"] > 0
        and aggregate["max_drawdown_delta_max"] <= 0.01
        and aggregate["min_overlay_day_count"] >= 4
        and concentration_ok
    )
    material = bool(
        (aggregate["candidate_overlay_expected_value_score_delta_pct"] or 0.0) >= 0.02
        or (aggregate["candidate_overlay_total_pnl_delta_pct"] or 0.0) >= 0.02
    )
    return {
        "passed": bool(directional and material),
        "passed_directionally": directional,
        "strong_materiality_passed": material,
        "concentration_ok": concentration_ok,
        "single_ticker_positive_share": concentration,
        "basis": (
            "Three canonical backtesting.md windows, active-core-one notional "
            "variants measured against accepted raw-momentum v1 low-deployment ETF overlay."
        ),
        "rule": (
            "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive "
            "aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive "
            "contribution share <= 75%, at least 4 overlay days in each window, "
            "and at least 2% aggregate EV or PnL uplift versus accepted v1."
        ),
    }


def _best_variant(variant_payloads: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    passed = [
        (name, payload)
        for name, payload in variant_payloads.items()
        if payload["gate4"]["passed"]
    ]
    pool = passed if passed else list(variant_payloads.items())
    return max(
        pool,
        key=lambda item: item[1]["delta_metrics"]["aggregate"][
            "candidate_overlay_expected_value_score_delta_sum"
        ],
    )


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["best_variant"]
    aggregate = payload["variant_results"][best]["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Low-deployment ETF Active-Core Scalar",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{best}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Trial Accounting",
        "",
        f"- trial_family: `{payload['trial_accounting']['trial_family']}`",
        f"- changed_variable: `{payload['changed_variable']}`",
        f"- prior_trial_count: `{payload['trial_accounting']['prior_trial_count']}`",
        f"- multiple_testing_risk_bucket: `{payload['trial_accounting']['multiple_testing_risk_bucket']}`",
        f"- new_evidence_type: `{payload['trial_accounting']['new_evidence_type']}`",
        "",
        "## Variant Sweep",
        "",
        "| Variant | active=1 scalar | EV delta | PnL delta | EV windows +/- | PnL windows +/- | DD max delta | Overlay days | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for variant, row in payload["variant_results"].items():
        agg = row["delta_metrics"]["aggregate"]
        lines.append(
            "| {variant} | {scalar:.2f} | {ev:+.4f} | ${pnl:+,.2f} | {ev_imp}/{ev_reg} | {pnl_imp}/{pnl_reg} | {dd:+.4f} | {days} | {gate} |".format(
                variant=variant,
                scalar=row["active_core_one_scalar"],
                ev=agg["candidate_overlay_expected_value_score_delta_sum"],
                pnl=agg["candidate_overlay_total_pnl_delta_sum"],
                ev_imp=agg["windows_ev_improved"],
                ev_reg=agg["windows_ev_regressed"],
                pnl_imp=agg["windows_pnl_improved"],
                pnl_reg=agg["windows_pnl_regressed"],
                dd=agg["max_drawdown_delta_max"],
                days=agg["overlay_day_count_sum"],
                gate="PASS" if row["gate4"]["passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Best Variant Three-window Deltas Vs Accepted v1",
            "",
            "| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | active-count split | Ticker days |",
            "|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for label, row in payload["variant_results"][best]["delta_metrics"]["by_window"].items():
        details = payload["variant_results"][best]["after_details"][label]
        ticker_counts = ", ".join(
            f"{ticker}:{count}"
            for ticker, count in sorted(details["ticker_day_counts"].items())
        )
        active_split = ", ".join(
            f"{active}:{count}"
            for active, count in sorted(details["active_count_distribution"].items())
        )
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {ret:+.4f} | {sharpe:+.2f} | {dd:+.4f} | {active_split} | {tickers} |".format(
                label=label,
                ev=row.get("expected_value_score", 0.0),
                pnl=row.get("total_pnl", 0.0),
                ret=row.get("strategy_total_return_pct", 0.0),
                sharpe=row.get("sharpe_daily", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
                active_split=active_split or "none",
                tickers=ticker_counts or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta vs v1: `{aggregate['candidate_overlay_expected_value_score_delta_sum']}` (`{aggregate['candidate_overlay_expected_value_score_delta_pct']}`)",
            f"- PnL delta vs v1: `${aggregate['candidate_overlay_total_pnl_delta_sum']}` (`{aggregate['candidate_overlay_total_pnl_delta_pct']}`)",
            f"- EV windows improved/regressed: `{aggregate['windows_ev_improved']}` / `{aggregate['windows_ev_regressed']}`",
            f"- PnL windows improved/regressed: `{aggregate['windows_pnl_improved']}` / `{aggregate['windows_pnl_regressed']}`",
            f"- max DD delta max: `{aggregate['max_drawdown_delta_max']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"  replay_only: {payload['production_impact']['replay_only']}",
            f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
            f"  default_off_paper_only: {payload['production_impact']['default_off_paper_only']}",
            f"  alters_orders: {payload['production_impact']['alters_orders']}",
            "```",
            "",
            "No JavaScript was used.",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")


def _write_ticket(payload: dict[str, Any]) -> None:
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "changed_variable": payload["changed_variable"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
        },
    )


def _build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    baseline_results = OrderedDict()
    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe=get_universe(),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        baseline_results[label] = result

    baseline_windows = OrderedDict(
        (
            label,
            _window_row(
                baseline_results[label],
                WINDOWS[label],
                variant=BASELINE_VARIANT,
                active_core_one_scalar=1.0,
            ),
        )
        for label in WINDOWS
    )

    variant_results: dict[str, dict[str, Any]] = OrderedDict()
    for variant, scalar in ACTIVE_CORE_ONE_SCALARS.items():
        after_windows = OrderedDict(
            (
                label,
                _window_row(
                    baseline_results[label],
                    WINDOWS[label],
                    variant=variant,
                    active_core_one_scalar=scalar,
                ),
            )
            for label in WINDOWS
        )
        delta_metrics = _variant_delta_vs_baseline(after_windows, baseline_windows)
        variant_results[variant] = {
            "active_core_one_scalar": scalar,
            "after_metrics": {label: row["after"] for label, row in after_windows.items()},
            "delta_metrics": delta_metrics,
            "gate4": _gate4(delta_metrics, after_windows),
            "after_details": {
                label: {
                    "overlay_total_pnl": row["overlay_total_pnl"],
                    "overlay_day_count": row["overlay_day_count"],
                    "low_deployment_day_count": row["low_deployment_day_count"],
                    "ticker_day_counts": row["ticker_day_counts"],
                    "active_count_distribution": row["active_count_distribution"],
                    "overlay_days_sample": row["overlay_days_sample"],
                }
                for label, row in after_windows.items()
            },
        }

    best_name, best_payload = _best_variant(variant_results)
    best_aggregate = best_payload["delta_metrics"]["aggregate"]
    gate = best_payload["gate4"]
    accepted = bool(gate["passed"])
    if accepted:
        decision = "accepted_default_off_low_deployment_etf_active_core_scalar"
        rejection_reason = None
        decision_rationale = (
            "The active-core scalar beat the accepted raw-momentum v1 overlay "
            "across all three canonical windows. Promotion would still require a "
            "shared default-off paper-policy patch and parity tests before any "
            "production-visible behavior changed."
        )
    else:
        decision = "rejected_low_deployment_etf_active_core_scalar"
        rejection_reason = (
            "No active-core-one notional scalar beat the accepted raw-momentum v1 "
            "overlay across the three-window EV/PnL/drawdown/materiality gate."
        )
        decision_rationale = rejection_reason

    before_metrics = {label: row["after"] for label, row in baseline_windows.items()}
    after_metrics = best_payload["after_metrics"]

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "low_deployment_dynamic_etf_overlay_allocation",
        "hypothesis": (
            "The accepted low-deployment ETF overlay may have different replacement "
            "value when the core book already has one active A/B position versus "
            "zero. Scaling only the active-core-one paper notional tests capital "
            "competition without changing the ETF selector, pool, activation "
            "threshold, or core behavior."
        ),
        "change_type": "alpha_search_overlay_capital_competition_allocation",
        "changed_variable": "low_deployment_etf_overlay_active_core_one_notional_scalar",
        "single_causal_variable": (
            "Only paper notional on overlay days with active_core_positions == 1 "
            "is swept; active_core_positions == 0 stays at the accepted 1.0x notional."
        ),
        "trial_accounting": {
            "trial_family": "low_deployment_dynamic_etf_overlay_capital_competition",
            "changed_variable": "active_core_one_notional_scalar",
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260510-007",
                "exp-20260518-003",
                "exp-20260522-004",
                "exp-20260522-018",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "new_production_visible_field",
            "new_evidence_detail": (
                "Uses active core A/B position count from the same shared planning "
                "state already surfaced by the default-off overlay."
            ),
        },
        "parameters": {
            "baseline_variant": BASELINE_VARIANT,
            "active_core_one_scalars": dict(ACTIVE_CORE_ONE_SCALARS),
            "baseline_active_core_one_scalar": 1.0,
            "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
            "candidate_tickers": list(helper.OVERLAY_CANDIDATES),
            "overlay_notional_fraction": OVERLAY_NOTIONAL_FRACTION,
            "state_sma_days": helper.STATE_SMA_DAYS,
            "state_momentum_days": helper.STATE_MOMENTUM_DAYS,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "position caps",
                "portfolio heat",
                "exits",
                "follow-through add-ons",
                "ETF candidate pool",
                "ETF raw momentum selector",
                "ETF activation threshold",
                "LLM/news replay",
                "live/default orders",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: active-core-one overlay days may have different "
                "replacement value than true zero-core idle days."
            ),
            "2_history_check": {
                "exp-20260510-007": "Accepted/promising raw-momentum dynamic ETF overlay at <=1 active core position.",
                "exp-20260518-003": "Activation-threshold variants rejected; this keeps <=1 activation fixed and changes only active=1 notional.",
                "exp-20260522-004": "Volatility cap rejected; this uses capital-competition state, not volatility.",
                "exp-20260522-018": "Momentum-lead gate rejected; this keeps raw momentum selector unchanged.",
            },
            "3_single_variable": "active_core_one_notional_scalar",
            "4_acceptance_standard": (
                "Compare each scalar against accepted raw-momentum v1 over the "
                "three docs/backtesting.md windows; require 3/3 EV improvement, "
                "no EV/PnL regression, positive aggregate EV/PnL, drawdown worsening "
                "<=1pp, concentration <=75%, and >=2% aggregate EV or PnL uplift."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260522_021_low_deployment_etf_active_core_scalar.py"
            ),
        },
        "alpha_hypothesis": {
            "category": "capital_allocation",
            "playbook_alignment": (
                "Tests replacement-value/capital competition in a default-off sleeve "
                "instead of LLM soft-ranking, broad-market identity-drift candidates, "
                "state-surface profile retunes, or adjacent event source scalars."
            ),
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three-window protocol",
            "core_baseline_metrics": {
                label: helper._metrics(result) for label, result in baseline_results.items()
            },
            "accepted_overlay_baseline_metrics": before_metrics,
        },
        "gate2_field_audit": helper._field_audit(),
        "gate3": {
            "new_core_filter_added": False,
            "new_overlay_candidate_filter_added": False,
            "note": (
                "No candidate filter was added; this is paper notional allocation "
                "inside the already accepted default-off ETF overlay. Core survival is unchanged."
            ),
            "survival_rates": {
                label: row["before"]["survival_rate"] for label, row in baseline_windows.items()
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "variant_results": variant_results,
        "best_variant": best_name,
        "best_variant_details": {
            "active_core_one_scalar": best_payload["active_core_one_scalar"],
            "delta_metrics": best_payload["delta_metrics"],
            "gate4": best_payload["gate4"],
        },
        "expected_value_score_delta": best_aggregate[
            "candidate_overlay_expected_value_score_delta_sum"
        ],
        "total_pnl_delta": best_aggregate["candidate_overlay_total_pnl_delta_sum"],
        "gate4": gate,
        "before_details": {
            label: {
                "overlay_total_pnl": row["overlay_total_pnl"],
                "overlay_day_count": row["overlay_day_count"],
                "low_deployment_day_count": row["low_deployment_day_count"],
                "ticker_day_counts": row["ticker_day_counts"],
                "active_count_distribution": row["active_count_distribution"],
                "overlay_days_sample": row["overlay_days_sample"],
            }
            for label, row in baseline_windows.items()
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this deterministic "
                "capital-competition test does not depend on LLM replay."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_orders_changed": False,
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_action": (
            "Keep accepted raw-momentum v1. Do not retry active-core-one ETF "
            "notional scalars or activation-threshold neighbors on the frozen "
            "windows without closed forward replacement-value evidence."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_artifact(payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, payload)
    best = payload["best_variant"]
    best_result = payload["variant_results"][best]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": best,
                    "best_active_core_one_scalar": best_result["active_core_one_scalar"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
