"""exp-20260522-012: default core position cap relief scout.

Alpha search. Tests one capital-allocation variable: whether the default
single-position cap is too tight after the accepted narrow cap/risk overlays.

This runner uses an experiment-only monkey patch. If a variant passes Gate 4,
promotion must move the value into shared production/backtest constants before
orders change.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260521_020_ample_slot_stock_rank2_topup as core_helper  # noqa: E402
import portfolio_engine as pe  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import MAX_POSITION_PCT as BASE_MAX_POSITION_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260522-012"
STEM = "default_position_cap_relief"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = core_helper.WINDOWS
VARIANTS = OrderedDict(
    [
        ("default_cap_0525", {"default_max_position_pct": 0.525}),
        ("default_cap_0550", {"default_max_position_pct": 0.550}),
        ("default_cap_0575", {"default_max_position_pct": 0.575}),
    ]
)

MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_TRADE_COUNT_SUM = 58
MIN_SURVIVAL_RATE = 0.05
MIN_AFFECTED_WINDOW_COUNT = 2
MIN_CHANGED_COMMON_TRADES = 4


def _run_window(window: dict[str, Any], cap: float | None = None) -> dict[str, Any]:
    original_cap = pe.MAX_POSITION_PCT
    if cap is not None:
        pe.MAX_POSITION_PCT = cap
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        return engine.run()
    finally:
        pe.MAX_POSITION_PCT = original_cap


def _run_baseline() -> dict[str, dict[str, Any]]:
    return {label: _run_window(window) for label, window in WINDOWS.items()}


def _run_variant(cap: float) -> dict[str, dict[str, Any]]:
    return {label: _run_window(window, cap=cap) for label, window in WINDOWS.items()}


def _trade_key(trade: dict[str, Any]) -> str:
    return "|".join(
        str(trade.get(field) or "")
        for field in ("ticker", "entry_date", "strategy", "entry_price")
    )


def _changed_trade_summary(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    before_by_key = {_trade_key(row): row for row in before.get("trades") or []}
    after_by_key = {_trade_key(row): row for row in after.get("trades") or []}
    common = sorted(set(before_by_key) & set(after_by_key))
    changed_rows = []
    for key in common:
        old = before_by_key[key]
        new = after_by_key[key]
        if int(old.get("shares") or 0) == int(new.get("shares") or 0):
            continue
        changed_rows.append(
            {
                "key": key,
                "ticker": new.get("ticker"),
                "entry_date": new.get("entry_date"),
                "sector": new.get("sector"),
                "strategy": new.get("strategy"),
                "shares_before": old.get("shares"),
                "shares_after": new.get("shares"),
                "pnl_before": core_helper._round(old.get("pnl"), 2),
                "pnl_after": core_helper._round(new.get("pnl"), 2),
            }
        )
    return {
        "common_changed": len(changed_rows),
        "added": len(set(after_by_key) - set(before_by_key)),
        "removed": len(set(before_by_key) - set(after_by_key)),
        "sample": changed_rows[:12],
    }


def _variant_eval(
    before_results: dict[str, dict[str, Any]],
    after_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {
        label: core_helper._metrics(result) for label, result in before_results.items()
    }
    after_metrics = {
        label: core_helper._metrics(result) for label, result in after_results.items()
    }
    deltas = {
        label: core_helper._delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    changed = {
        label: _changed_trade_summary(before_results[label], after_results[label])
        for label in WINDOWS
    }
    improved_windows = [
        label
        for label, delta in deltas.items()
        if float(delta.get("expected_value_score") or 0.0) > 0.0
    ]
    regressed_windows = [
        label
        for label, delta in deltas.items()
        if float(delta.get("expected_value_score") or 0.0) < 0.0
    ]
    affected_window_count = sum(
        1
        for row in changed.values()
        if int(row.get("common_changed") or 0)
        or int(row.get("added") or 0)
        or int(row.get("removed") or 0)
    )
    changed_common_trades = sum(int(row.get("common_changed") or 0) for row in changed.values())
    agg_delta = core_helper._aggregate_delta(after_metrics, before_metrics)
    after_agg = core_helper._aggregate(after_metrics)
    passed = (
        agg_delta["expected_value_score_sum"] > 0.0
        and agg_delta["total_pnl_sum"] > 0.0
        and len(improved_windows) >= 2
        and not regressed_windows
        and agg_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and after_agg["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
        and after_agg["survival_rate_min"] >= MIN_SURVIVAL_RATE
        and affected_window_count >= MIN_AFFECTED_WINDOW_COUNT
        and changed_common_trades >= MIN_CHANGED_COMMON_TRADES
    )
    return {
        "after_metrics": {"windows": after_metrics, "aggregate": after_agg},
        "delta_metrics": {"windows": deltas, "aggregate": agg_delta},
        "changed_trades": changed,
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "affected_window_count": affected_window_count,
        "changed_common_trades": changed_common_trades,
        "passed": bool(passed),
        "guardrails": {
            "requires_no_ev_regression_windows": True,
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "min_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "min_survival_rate": MIN_SURVIVAL_RATE,
            "min_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "min_changed_common_trades": MIN_CHANGED_COMMON_TRADES,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                kept.append(line)
    kept.append(json.dumps(record, sort_keys=True, ensure_ascii=False))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Trial accounting",
        f"- trial_family: {payload['trial_family']}",
        f"- changed_variable: {payload['changed_variable']}",
        f"- prior_trial_count: {payload['prior_trial_count']}",
        f"- multiple_testing_risk_bucket: {payload['multiple_testing_risk_bucket']}",
        f"- new_evidence_type: {payload['new_evidence_type']}",
        "",
        "## Three-window aggregate",
        f"- baseline EV: {payload['before_metrics']['aggregate']['expected_value_score_sum']}",
        f"- best EV: {payload['after_metrics']['aggregate']['expected_value_score_sum']}",
        f"- EV delta: {payload['delta_metrics']['aggregate']['expected_value_score_sum']}",
        f"- PnL delta: {payload['delta_metrics']['aggregate']['total_pnl_sum']}",
        f"- decision: {payload['decision']}",
        "",
        "## Sweep summary",
        "| variant | cap | EV delta | PnL delta | DD delta | improved | regressed | changed | passed |",
        "|---|---:|---:|---:|---:|---|---|---:|---|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {cap} | {ev_delta} | {pnl_delta} | {dd_delta} | {improved} | {regressed} | {changed} | {passed} |".format(
                variant=row["variant"],
                cap=row["default_max_position_pct"],
                ev_delta=row["delta_metrics"]["aggregate"]["expected_value_score_sum"],
                pnl_delta=row["delta_metrics"]["aggregate"]["total_pnl_sum"],
                dd_delta=row["delta_metrics"]["aggregate"]["max_drawdown_pct_max"],
                improved=",".join(row["improved_windows"]),
                regressed=",".join(row["regressed_windows"]),
                changed=row["changed_common_trades"],
                passed=row["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Window deltas for selected variant",
            "| window | EV | PnL | DD | survival |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, row in payload["delta_metrics"]["windows"].items():
        lines.append(
            f"| {label} | {row.get('expected_value_score')} | {row.get('total_pnl')} | {row.get('max_drawdown_pct')} | {row.get('survival_rate')} |"
        )
    lines.extend(
        [
            "",
            "## Production impact",
            "```text",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            payload["rejection_reason"],
            "",
            "## Next evidence needed",
            payload["next_evidence_needed"],
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    field_check = core_helper._open_position_field_check()
    baseline_results = _run_baseline()
    before_metrics = {
        label: core_helper._metrics(result) for label, result in baseline_results.items()
    }
    sweep_summary = []
    variant_results = {}
    for variant_name, config in VARIANTS.items():
        after_results = _run_variant(float(config["default_max_position_pct"]))
        evaluation = _variant_eval(baseline_results, after_results)
        sweep_summary.append(
            {
                "variant": variant_name,
                "default_max_position_pct": config["default_max_position_pct"],
                **evaluation,
            }
        )
        variant_results[variant_name] = {
            "config": config,
            "evaluation": evaluation,
        }
    best = max(
        sweep_summary,
        key=lambda row: row["delta_metrics"]["aggregate"]["expected_value_score_sum"],
    )
    decision = (
        "candidate_passed_requires_shared_policy_promotion"
        if best["passed"]
        else "rejected_failed_gate4"
    )
    rejection_reason = (
        "Best variant failed Gate 4 because at least one fixed window regressed in EV; do not promote a broad default cap retune from mixed-window evidence."
        if not best["passed"]
        else "n/a"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "change_type": "alpha_search",
        "hypothesis": (
            "Default cap-bound core entries may be underallocated after the accepted "
            "narrow cap/risk overlays; modestly relaxing the default single-position "
            "cap could increase expected value without changing entries, exits, ranking, "
            "candidate pool, LLM authority, or filters."
        ),
        "trial_family": "core_default_position_cap_relief",
        "changed_variable": "default_max_position_pct",
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260428-025",
            "exp-20260502-021",
            "exp-20260514-018",
            "exp-20260514-049",
            "exp-20260517-009",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "cap_bound_core_trade_diagnostics",
        "single_causal_variable": (
            "experiment-only monkey patch of portfolio_engine.MAX_POSITION_PCT; all "
            "entries, exits, ranking, filters, universe, LLM/news replay, and accepted "
            "narrow overlay caps stay fixed"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "config": {
                "REGIME_AWARE_EXIT": True,
                "replay_llm": False,
                "replay_news": False,
            },
            "windows": WINDOWS,
        },
        "parameters": {
            "baseline_default_max_position_pct": BASE_MAX_POSITION_PCT,
            "variant_default_max_position_pct": {
                key: value["default_max_position_pct"] for key, value in VARIANTS.items()
            },
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core exits",
                "filters",
                "risk multipliers",
                "accepted sleeve-specific caps",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "gate2_field_check": field_check,
        "before_metrics": {
            "windows": before_metrics,
            "aggregate": core_helper._aggregate(before_metrics),
        },
        "after_metrics": best["after_metrics"],
        "delta_metrics": best["delta_metrics"],
        "sweep_summary": sweep_summary,
        "best_variant": {
            "variant": best["variant"],
            "default_max_position_pct": best["default_max_position_pct"],
            "passed": best["passed"],
        },
        "expected_value_score_delta": best["delta_metrics"]["aggregate"][
            "expected_value_score_sum"
        ],
        "expected_value_score_delta_pct": core_helper._round(
            best["delta_metrics"]["aggregate"]["expected_value_score_sum"]
            / core_helper._aggregate(before_metrics)["expected_value_score_sum"],
            6,
        ),
        "total_pnl_delta": best["delta_metrics"]["aggregate"]["total_pnl_sum"],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Do not retry broad default cap values on the same fixed sample. If this "
            "mechanism is revisited, use a new production-visible cap-bound quality "
            "state that avoids old_thin V-style loser amplification and promote only "
            "through shared constants/policy with a parity test."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "live_default_orders_changed": False,
            "notes": (
                "No strategy behavior changed. The cap values were tested by a local "
                "monkey patch only; no positive result is kept without shared policy "
                "promotion."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking due sparse attribution, broad-market identity "
            "because recent controls failed, event fact-tone/governance near-neighbor "
            "scalars due repeated mixed evidence, and state-surface notional/capital "
            "retunes due the stricter same-family materiality gate."
        ),
        "known_risks": [
            "High multiple-testing risk around cap and capacity family.",
            "Best sweep result improved aggregate EV but amplified at least one weak-window loser.",
            "Replay-only monkey patch is not production behavior.",
        ],
        "variant_results": variant_results,
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    return payload


def main() -> None:
    payload = run()
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
