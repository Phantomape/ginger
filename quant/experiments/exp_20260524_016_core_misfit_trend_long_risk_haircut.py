"""exp-20260524-016: core-misfit trend_long risk haircut sweep.

Alpha search on one causal variable: a post-sizing share multiplier for the
existing CORE_MISFIT_PAPER ticker set when the source strategy is trend_long.
This tests reduced long exposure, not live shorting, ticker expansion, or a
hard no-entry rule.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260523_011_core_misfit_trend_long_no_entry as prev  # noqa: E402


EXPERIMENT_ID = "exp-20260524-016"
STEM = "core_misfit_trend_long_risk_haircut"
TRIAL_FAMILY = "core_misfit_long_risk_governance"
CHANGED_VARIABLE = "core_misfit_trend_long_post_sizing_multiplier"
TARGET_TICKERS = prev.TARGET_TICKERS
TARGET_STRATEGY = prev.TARGET_STRATEGY
WINDOWS = prev.WINDOWS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("misfit_trend_risk_025", 0.25),
        ("misfit_trend_risk_050", 0.50),
        ("misfit_trend_risk_075", 0.75),
    ]
)

MIN_TARGET_TRADES = 3
MIN_TARGET_WINDOWS = 2
MIN_CHANGED_TRADES = 3
MIN_EV_IMPROVED_WINDOWS = 2
MAX_EV_REGRESSED_WINDOWS = 0
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_TICKER_SHARE = 0.50
MAX_POSITIVE_PNL_HHI = 0.45


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    value = Path(path) if not isinstance(path, Path) else path
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(prev.base._safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(prev.base._safe(payload), ensure_ascii=True, sort_keys=True)
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


def _run_window(label: str, multiplier: float | None = None) -> dict[str, Any]:
    spec = WINDOWS[label]
    engine = prev.base.BacktestEngine(
        sorted(prev.base.get_universe()),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        include_entry_candidate_events=True,
    )
    context = (
        prev._core_misfit_trend_long_haircut(multiplier)
        if multiplier is not None
        else nullcontext()
    )
    with context:
        return engine.run()


def _candidate_adjustment_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_set = set(TARGET_TICKERS)
    for event in result.get("entry_candidate_events") or []:
        ticker = str(event.get("ticker") or "").upper()
        if ticker not in target_set or event.get("strategy") != TARGET_STRATEGY:
            continue
        snapshot = event.get("signal_snapshot") or {}
        sizing = snapshot.get("sizing") or {}
        if "core_misfit_trend_long_haircut_multiplier_applied" not in sizing:
            continue
        baseline_shares = int(sizing.get("core_misfit_trend_long_baseline_shares") or 0)
        new_shares = int(sizing.get("core_misfit_trend_long_new_shares") or 0)
        rows.append(
            {
                "date": event.get("date"),
                "ticker": ticker,
                "strategy": event.get("strategy"),
                "decision": event.get("decision"),
                "candidate_rank": event.get("candidate_rank"),
                "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
                "baseline_shares": baseline_shares,
                "new_shares": new_shares,
                "multiplier": sizing.get(
                    "core_misfit_trend_long_haircut_multiplier_applied"
                ),
                "changed": new_shares < baseline_shares,
            }
        )
    return rows


def _trade_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("ticker") or "").upper(),
        str(row.get("strategy") or ""),
        str(row.get("entry_date") or ""),
    )


def _trade_delta_summary(
    before_by_window: dict[str, list[dict[str, Any]]],
    after_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    positive_by_ticker: dict[str, float] = {}
    for label in WINDOWS:
        before_map = {_trade_key(row): row for row in before_by_window[label]}
        after_map = {_trade_key(row): row for row in after_by_window[label]}
        for key, before in before_map.items():
            after = after_map.get(key)
            if not after:
                continue
            delta_pnl = round(float(after.get("pnl") or 0.0) - float(before.get("pnl") or 0.0), 2)
            share_delta = int(after.get("shares") or 0) - int(before.get("shares") or 0)
            changed = share_delta != 0 or abs(delta_pnl) >= 0.01
            row = {
                "window": label,
                "ticker": key[0],
                "entry_date": key[2],
                "exit_date": after.get("exit_date"),
                "before_shares": before.get("shares"),
                "after_shares": after.get("shares"),
                "share_delta": share_delta,
                "before_pnl": before.get("pnl"),
                "after_pnl": after.get("pnl"),
                "incremental_pnl": delta_pnl,
                "changed": changed,
            }
            rows.append(row)
            if delta_pnl > 0:
                positive_by_ticker[key[0]] = positive_by_ticker.get(key[0], 0.0) + delta_pnl

    positive_values = sorted(positive_by_ticker.values(), reverse=True)
    positive_total = sum(positive_values)
    hhi = (
        sum((value / positive_total) ** 2 for value in positive_values)
        if positive_total > 0
        else None
    )
    return {
        "matched_target_trades": len(rows),
        "changed_trade_count": sum(1 for row in rows if row["changed"]),
        "windows_with_target_trades": sorted(
            {row["window"] for row in rows if row["changed"] or row["incremental_pnl"] != 0}
        ),
        "incremental_pnl": round(sum(row["incremental_pnl"] for row in rows), 2),
        "positive_incremental_pnl": round(positive_total, 2),
        "positive_by_ticker": {
            ticker: round(value, 2) for ticker, value in sorted(positive_by_ticker.items())
        },
        "max_single_positive_ticker_share": (
            round(max(positive_values) / positive_total, 4)
            if positive_values and positive_total > 0
            else None
        ),
        "positive_pnl_hhi": round(hhi, 4) if hhi is not None else None,
        "sample_rows": rows[:30],
    }


def _window_deltas(
    before_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
) -> "OrderedDict[str, dict[str, Any]]":
    return OrderedDict(
        (label, prev.base._delta(after_metrics[label], before_metrics[label]))
        for label in WINDOWS
    )


def _gate(
    *,
    aggregate_before: dict[str, Any],
    aggregate_after: dict[str, Any],
    by_window_delta: dict[str, dict[str, Any]],
    before_target_trade_summary: dict[str, Any],
    trade_delta_summary: dict[str, Any],
) -> dict[str, Any]:
    aggregate_delta = prev.base._delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label, row in by_window_delta.items()
        if (row.get("expected_value_score") or 0.0) > 0
    ]
    regressed = [
        label
        for label, row in by_window_delta.items()
        if (row.get("expected_value_score") or 0.0) < 0
    ]
    max_drawdown_worse = max(
        float(row.get("max_drawdown_pct") or 0.0) for row in by_window_delta.values()
    )
    max_share = trade_delta_summary["max_single_positive_ticker_share"]
    hhi = trade_delta_summary["positive_pnl_hhi"]
    checks = {
        "positive_aggregate_ev": aggregate_delta["expected_value_score_sum"] > 0,
        "positive_aggregate_pnl": aggregate_delta["total_pnl_sum"] > 0,
        "ev_improved_window_coverage": len(improved) >= MIN_EV_IMPROVED_WINDOWS,
        "no_ev_regressed_windows": len(regressed) <= MAX_EV_REGRESSED_WINDOWS,
        "drawdown_worse_guard": max_drawdown_worse <= MAX_DRAWDOWN_WORSE,
        "survival_guard": aggregate_after["min_survival_rate"] >= 0.05,
        "target_trade_sample": before_target_trade_summary["trade_count"] >= MIN_TARGET_TRADES,
        "target_window_sample": (
            len(before_target_trade_summary["windows_with_trades"]) >= MIN_TARGET_WINDOWS
        ),
        "changed_trade_sample": trade_delta_summary["changed_trade_count"] >= MIN_CHANGED_TRADES,
        "single_positive_ticker_share_cap": (
            max_share is None or max_share <= MAX_SINGLE_POSITIVE_TICKER_SHARE
        ),
        "positive_pnl_hhi_cap": hhi is None or hhi <= MAX_POSITIVE_PNL_HHI,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "aggregate_delta": aggregate_delta,
        "by_window_delta": by_window_delta,
        "improved_windows": improved,
        "regressed_windows": regressed,
        "max_drawdown_worse": prev.base._round(max_drawdown_worse, 6),
        "rules": {
            "min_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
            "max_ev_regressed_windows": MAX_EV_REGRESSED_WINDOWS,
            "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "min_changed_trades": MIN_CHANGED_TRADES,
            "max_single_positive_ticker_share": MAX_SINGLE_POSITIVE_TICKER_SHARE,
            "max_positive_pnl_hhi": MAX_POSITIVE_PNL_HHI,
        },
    }


def _build_variant(
    *,
    variant: str,
    multiplier: float,
    before_metrics: dict[str, dict[str, Any]],
    before_target_trades: dict[str, list[dict[str, Any]]],
    aggregate_before: dict[str, Any],
) -> dict[str, Any]:
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_target_trades: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    adjustment_events: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label in WINDOWS:
        print(f"[{label}] {variant}")
        result = _run_window(label, multiplier=multiplier)
        after_metrics[label] = prev.base._metrics(result)
        after_target_trades[label] = prev._target_trades(result)
        adjustment_events[label] = _candidate_adjustment_events(result)

    by_window_delta = _window_deltas(before_metrics, after_metrics)
    aggregate_after = prev.base._aggregate(after_metrics)
    before_trade_summary = prev._summarize_target_trades(before_target_trades)
    after_trade_summary = prev._summarize_target_trades(after_target_trades)
    trade_delta = _trade_delta_summary(before_target_trades, after_target_trades)
    adjustment_count = sum(
        1 for rows in adjustment_events.values() for row in rows if row.get("changed")
    )
    gate = _gate(
        aggregate_before=aggregate_before,
        aggregate_after=aggregate_after,
        by_window_delta=by_window_delta,
        before_target_trade_summary=before_trade_summary,
        trade_delta_summary=trade_delta,
    )
    return {
        "variant": variant,
        "multiplier": multiplier,
        "after_metrics": after_metrics,
        "after_aggregate": aggregate_after,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_delta": gate["aggregate_delta"],
        },
        "after_target_trades_by_window": after_target_trades,
        "after_target_trade_summary": after_trade_summary,
        "adjustment_events_by_window": adjustment_events,
        "adjusted_signal_count": adjustment_count,
        "trade_delta_summary": trade_delta,
        "gate4": gate,
    }


def _select_best(variants: OrderedDict[str, dict[str, Any]]) -> str:
    passing = [key for key, row in variants.items() if row["gate4"]["passed"]]
    pool = passing or list(variants)
    return max(
        pool,
        key=lambda key: (
            variants[key]["gate4"]["aggregate_delta"]["expected_value_score_sum"],
            variants[key]["gate4"]["aggregate_delta"]["total_pnl_sum"],
            -float(variants[key]["gate4"]["max_drawdown_worse"] or 0.0),
        ),
    )


def _rejection_reason(gate: dict[str, Any]) -> str:
    failed = [key for key, value in gate["checks"].items() if not value]
    if "no_ev_regressed_windows" in failed:
        return "Best variant failed Gate 4 because at least one standard window regressed in expected_value_score."
    if "positive_aggregate_ev" in failed or "positive_aggregate_pnl" in failed:
        return "Best variant failed Gate 4 because aggregate EV or PnL did not improve."
    if "single_positive_ticker_share_cap" in failed or "positive_pnl_hhi_cap" in failed:
        return "Best variant failed concentration guard for positive incremental PnL."
    return "Best variant failed Gate 4 checks: " + ", ".join(failed) + "."


def _artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Core-Misfit Trend Long Risk Haircut",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Three-Window Aggregate",
        f"- baseline EV: `{payload['before_metrics']['aggregate']['expected_value_score_sum']}`",
        f"- best EV: `{payload['after_metrics']['aggregate']['expected_value_score_sum']}`",
        f"- EV delta: `{payload['delta_metrics']['aggregate_delta']['expected_value_score_sum']}`",
        f"- PnL delta: `${payload['delta_metrics']['aggregate_delta']['total_pnl_sum']}`",
        "",
        "## Sweep Summary",
        "| variant | multiplier | EV delta | PnL delta | DD delta | changed trades | max pos share | HHI | passed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["sweep_summary"]:
        gate = row["gate4"]
        trade_delta = row["trade_delta_summary"]
        lines.append(
            "| {variant} | {multiplier} | {ev} | {pnl} | {dd} | {changed} | {share} | {hhi} | {passed} |".format(
                variant=row["variant"],
                multiplier=row["multiplier"],
                ev=gate["aggregate_delta"]["expected_value_score_sum"],
                pnl=gate["aggregate_delta"]["total_pnl_sum"],
                dd=gate["max_drawdown_worse"],
                changed=trade_delta["changed_trade_count"],
                share=trade_delta["max_single_positive_ticker_share"],
                hhi=trade_delta["positive_pnl_hhi"],
                passed=gate["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Selected Window Deltas",
            "| window | EV | PnL | DD | survival |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, row in payload["delta_metrics"]["by_window"].items():
        lines.append(
            f"| {label} | {row.get('expected_value_score')} | {row.get('total_pnl')} | {row.get('max_drawdown_pct')} | {row.get('survival_rate')} |"
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "```json",
            json.dumps(prev.base._safe(payload["gate4"]), indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "No shared production policy, run adapter, backtester adapter, watchlist, or order path changed. If accepted later, this must move into shared sizing policy with parity tests before order behavior changes.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "trial_family": payload["trial_family"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "gate": payload["gate4"],
        "related_files": payload["related_files"],
    }


def build_payload() -> dict[str, Any]:
    gate2_open_positions = prev.base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")
    coverage = prev._snapshot_coverage(list(TARGET_TICKERS))
    if not coverage["passed"]:
        raise RuntimeError(f"Gate 2 OHLCV coverage failed: {coverage}")

    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_target_trades: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label in WINDOWS:
        print(f"[{label}] baseline")
        result = _run_window(label)
        before_metrics[label] = prev.base._metrics(result)
        before_target_trades[label] = prev._target_trades(result)

    aggregate_before = prev.base._aggregate(before_metrics)
    before_trade_summary = prev._summarize_target_trades(before_target_trades)

    variants: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for variant, multiplier in VARIANTS.items():
        variants[variant] = _build_variant(
            variant=variant,
            multiplier=multiplier,
            before_metrics=before_metrics,
            before_target_trades=before_target_trades,
            aggregate_before=aggregate_before,
        )

    best_key = _select_best(variants)
    best = variants[best_key]
    gate = best["gate4"]
    accepted = gate["passed"]
    decision = (
        "positive_replay_deferred_requires_shared_core_misfit_risk_policy"
        if accepted
        else "rejected_core_misfit_trend_long_risk_haircut"
    )
    rejection_reason = None if accepted else _rejection_reason(gate)
    timestamp = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": decision,
        "hypothesis": (
            "The established CORE_MISFIT_PAPER ticker set may be negative for "
            "core long exposure but too blunt for a hard no-entry rule. A "
            "bounded post-sizing risk haircut for TSM/ISRG/V/DDOG trend_long "
            "signals may improve EV by reducing the known drag while preserving "
            "some participation and avoiding replacement-slot side effects."
        ),
        "change_type": "core_long_risk_allocation_haircut",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260516-043",
            "exp-20260517-002",
            "exp-20260517-003",
            "exp-20260518-019",
            "exp-20260519-019",
            "exp-20260523-011",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "risk_haircut_instead_of_hard_no_entry_on_existing_core_misfit_cohort",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window core replay",
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "target_tickers": list(TARGET_TICKERS),
            "target_strategy": TARGET_STRATEGY,
            "swept_multipliers": dict(VARIANTS),
            "selected_variant": best_key,
            "selected_multiplier": best["multiplier"],
            "locked_variables": [
                "universe",
                "signal rules",
                "ranking",
                "all non-target sizing rules",
                "exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
            ],
            "acceptance": gate["rules"],
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: existing core-misfit trend_long names should "
                "receive less long risk, not zero risk, because hard no-entry "
                "was too disruptive."
            ),
            "2_history_check": {
                "exp-20260516-043": (
                    "Accepted default-off CORE_MISFIT_PAPER observation scope "
                    "for TSM/ISRG/V/DDOG."
                ),
                "exp-20260517-003": (
                    "Inverse fixed-10d shadow was positive but too fragile for live shorting."
                ),
                "exp-20260518-019": (
                    "trend_long conditioned inverse shadow was promising but still replay-only."
                ),
                "exp-20260523-011": (
                    "Hard no-entry failed Gate 4 because replacement/slot effects worsened old_thin."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three-window before/after; require aggregate "
                "EV/PnL improvement, at least two EV-improved windows, no "
                "EV-regressed window, drawdown/survival/sample/concentration "
                "guards, and no production/backtest split."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260524_016_core_misfit_trend_long_risk_haircut.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "ohlcv_coverage": coverage,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "entry_candidate_events.ticker",
                "entry_candidate_events.strategy",
                "signal.sizing.shares_to_buy",
                "signal.sizing.entry_price",
                "target OHLCV rows in all three standard snapshots",
            ],
            "passed": gate2_open_positions["passed"] and coverage["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_sum_before": aggregate_before.get("signals_generated_sum"),
            "signals_survived_sum_before": aggregate_before.get("signals_survived_sum"),
            "survival_rate_min_before": aggregate_before.get("min_survival_rate"),
            "survival_rate_min_after": best["after_aggregate"].get("min_survival_rate"),
            "passed": best["after_aggregate"].get("min_survival_rate", 0) >= 0.05,
            "note": (
                "All tested multipliers are above zero, so target entries remain "
                "eligible; this is sizing risk allocation, not a new filter."
            ),
        },
        "gate4": gate,
        "before_metrics": {
            "windows": before_metrics,
            "aggregate": aggregate_before,
        },
        "after_metrics": {
            "windows": best["after_metrics"],
            "aggregate": best["after_aggregate"],
        },
        "delta_metrics": best["delta_metrics"],
        "before_target_trades_by_window": before_target_trades,
        "before_target_trade_summary": before_trade_summary,
        "after_target_trades_by_window": best["after_target_trades_by_window"],
        "after_target_trade_summary": best["after_target_trade_summary"],
        "adjustment_events_by_window": best["adjustment_events_by_window"],
        "trade_delta_summary": best["trade_delta_summary"],
        "expected_value_score_delta": gate["aggregate_delta"]["expected_value_score_sum"],
        "total_pnl_delta": gate["aggregate_delta"]["total_pnl_sum"],
        "sweep_summary": [
            {
                "variant": key,
                "multiplier": row["multiplier"],
                "after_aggregate": row["after_aggregate"],
                "delta_metrics": row["delta_metrics"],
                "adjusted_signal_count": row["adjusted_signal_count"],
                "trade_delta_summary": row["trade_delta_summary"],
                "gate4": row["gate4"],
            }
            for key, row in variants.items()
        ],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "live_short_enabled": False,
            "promotion_requirement": (
                "If accepted later, implement the risk haircut in shared "
                "production/backtest sizing policy with parity coverage before "
                "any live order behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking due sparse attribution; skipped SEC/event/"
            "state-surface/broad-market near-neighbor scalars after recent "
            "concentration and identity blockers; skipped direct candidate-pool "
            "promotion after recent AI and consumer pilot cohorts failed. This "
            "uses the existing core-misfit evidence but tests a softer risk "
            "allocation treatment than the rejected hard no-entry rule."
        ),
        "known_risks": [
            "Ticker-specific governance has moderate multiple-testing risk.",
            "Risk haircuts can reduce winners if core-misfit is not stable.",
            "If accepted, production parity requires shared policy and tests before orders change.",
        ],
        "interpretation": (
            "The risk haircut is a candidate only; it must be promoted into shared "
            "policy and rerun before production use."
            if accepted
            else "Do not promote a CORE_MISFIT_PAPER trend_long risk haircut from this replay."
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Move the policy into shared sizing with parity tests, then rerun the same windows."
            if accepted
            else (
                "Keep CORE_MISFIT_PAPER as default-off observation; retry only "
                "with new forward closed outcomes or a materially different "
                "production-visible discriminator."
            )
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Core-misfit trend_long risk haircut",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
            "updated_at": payload["timestamp"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact(payload))
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            prev.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "selected_variant": payload["parameters"]["selected_variant"],
                    "selected_multiplier": payload["parameters"]["selected_multiplier"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "gate4_checks": payload["gate4"]["checks"],
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
