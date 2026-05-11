"""exp-20260511-107: RS20 entry-state regime-scope replay.

Alpha search. The accepted RS20 entry-state policy adds a modest cap-aware
1.10x top-up to already selected trend/breakout signals when the ticker beats
SPY by at least five points over 20 trading days. This experiment does not
retune that threshold or multiplier. It tests one orthogonal variable: whether
the top-up should be scoped by the existing regime-exit bucket.

No production policy is changed by this script. A positive result must be
implemented in shared portfolio policy before it can be retained.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260511-107"
STEM = "rs20_entry_state_regime_scope"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


WINDOWS: OrderedDict[str, dict[str, str]] = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            "exclude_defensive",
            {
                "allowed_buckets": ("balanced", "risk_on"),
                "description": "Disable RS20 entry-state top-up only for defensive regime-exit signals.",
            },
        ),
        (
            "risk_on_only",
            {
                "allowed_buckets": ("risk_on",),
                "description": "Allow RS20 entry-state top-up only for risk_on regime-exit signals.",
            },
        ),
    ]
)

RESULT_KEYS = [
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
    "worst_trade_pct",
    "max_consecutive_losses",
    "tail_loss_share",
]

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SCOPE_SUPPRESSIONS: list[dict[str, Any]] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def round_value(value: Any, digits: int = 6) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    return value


def safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_payload(item) for item in value]
    if isinstance(value, tuple):
        return [safe_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe_payload(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_payload(payload), ensure_ascii=False, sort_keys=True) + "\n")


def audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[tuple[str, dict[str, Any]]] = []
    for section in ("positions", "observations"):
        for row in payload.get(section, []):
            if isinstance(row, dict):
                rows.append((section, row))

    missing: list[dict[str, Any]] = []
    for section, row in rows:
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append(
                    {
                        "section": section,
                        "ticker": row.get("ticker"),
                        "field": field,
                    }
                )

    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    summary = {key: round_value(result.get(key)) for key in RESULT_KEYS}
    summary["strategy_total_return_pct"] = round_value(
        benchmarks.get("strategy_total_return_pct")
    )
    summary["trade_count"] = int(result.get("total_trades") or 0)
    summary["spy_buy_hold_return_pct"] = round_value(
        benchmarks.get("spy_buy_hold_return_pct")
    )
    summary["qqq_buy_hold_return_pct"] = round_value(
        benchmarks.get("qqq_buy_hold_return_pct")
    )
    convergence = result.get("convergence") or {}
    if convergence:
        summary["converged"] = bool(convergence.get("converged", False))
    return summary


def metric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in RESULT_KEYS:
        av = after.get(key)
        bv = before.get(key)
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            delta[key] = round_value(av - bv)
        else:
            delta[key] = None
    return delta


def trade_key(trade: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(trade.get("entry_date") or "")[:10],
        str(trade.get("ticker") or "").upper(),
        str(trade.get("strategy") or ""),
        str(trade.get("entry_price") or ""),
    )


def has_rs20_topup(trade: dict[str, Any]) -> bool:
    multipliers = trade.get("sizing_multipliers") or {}
    value = multipliers.get("rs20_entry_state_risk_multiplier_applied")
    return isinstance(value, (int, float)) and float(value) > 1.0


def make_scope_wrapper(
    original: Callable[..., list[dict[str, Any]]],
    *,
    variant: str,
    allowed_buckets: tuple[str, ...],
) -> Callable[..., list[dict[str, Any]]]:
    allowed = set(allowed_buckets)

    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        patched: list[dict[str, Any]] = []
        for sig in signals:
            should_scope = (
                sig.get("rs20_entry_state_leader") is True
                and sig.get("strategy") in {"trend_long", "breakout_long"}
                and sig.get("regime_exit_bucket") not in allowed
            )
            if not should_scope:
                patched.append(sig)
                continue
            clone = dict(sig)
            clone["rs20_entry_state_leader"] = False
            clone["rs20_entry_state_regime_scope_suppressed"] = True
            clone["rs20_entry_state_regime_scope_variant"] = variant
            patched.append(clone)
            SCOPE_SUPPRESSIONS.append(
                {
                    "variant": variant,
                    "ticker": sig.get("ticker"),
                    "strategy": sig.get("strategy"),
                    "sector": sig.get("sector"),
                    "regime_exit_bucket": sig.get("regime_exit_bucket"),
                    "regime_exit_score": sig.get("regime_exit_score"),
                    "entry_price": sig.get("entry_price"),
                    "trade_quality_score": sig.get("trade_quality_score"),
                    "ticker_ret20_minus_spy_pct": sig.get("ticker_ret20_minus_spy_pct"),
                }
            )
        sized = original(patched, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if not sig.get("rs20_entry_state_regime_scope_suppressed"):
                continue
            sizing = dict(sig.get("sizing") or {})
            sizing["rs20_entry_state_regime_scope_suppressed"] = True
            sizing["rs20_entry_state_regime_scope_variant"] = variant
            sig["sizing"] = sizing
        return sized

    return wrapped


def run_backtest(
    spec: dict[str, str],
    *,
    variant: str | None = None,
    allowed_buckets: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    global SCOPE_SUPPRESSIONS
    SCOPE_SUPPRESSIONS = []
    original_size_signals = portfolio_engine.size_signals
    if variant is not None and allowed_buckets is not None:
        portfolio_engine.size_signals = make_scope_wrapper(
            original_size_signals,
            variant=variant,
            allowed_buckets=allowed_buckets,
        )
    try:
        engine = BacktestEngine(
            get_universe(),
            start=spec["start"],
            end=spec["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
            include_entry_candidate_events=True,
        )
        result = engine.run()
    finally:
        portfolio_engine.size_signals = original_size_signals
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result, list(SCOPE_SUPPRESSIONS)


def summarize_suppressions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket = Counter(str(row.get("regime_exit_bucket") or "unknown") for row in rows)
    by_ticker = Counter(str(row.get("ticker") or "UNKNOWN").upper() for row in rows)
    by_strategy = Counter(str(row.get("strategy") or "unknown") for row in rows)
    return {
        "suppressed_signal_count": len(rows),
        "by_bucket": dict(sorted(by_bucket.items())),
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_strategy": dict(sorted(by_strategy.items())),
        "sample": rows[:12],
    }


def summarize_trade_changes(
    before_trades: list[dict[str, Any]],
    after_trades: list[dict[str, Any]],
    allowed_buckets: tuple[str, ...],
) -> dict[str, Any]:
    after_by_key = {trade_key(trade): trade for trade in after_trades}
    details: list[dict[str, Any]] = []
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    touched = 0
    changed = 0
    allowed = set(allowed_buckets)

    for before in before_trades:
        if not has_rs20_topup(before):
            continue
        bucket = before.get("regime_exit_bucket")
        if bucket in allowed:
            continue
        touched += 1
        after = after_by_key.get(trade_key(before))
        before_pnl = float(before.get("pnl") or 0.0)
        after_pnl = float(after.get("pnl") or 0.0) if after else 0.0
        before_shares = int(before.get("shares") or 0)
        after_shares = int(after.get("shares") or 0) if after else 0
        pnl_delta = after_pnl - before_pnl
        if after is None or before_shares != after_shares or abs(pnl_delta) > 0.005:
            changed += 1
        ticker = str(before.get("ticker") or "UNKNOWN").upper()
        pnl_delta_by_ticker[ticker] += pnl_delta
        details.append(
            {
                "ticker": ticker,
                "strategy": before.get("strategy"),
                "sector": before.get("sector"),
                "regime_exit_bucket": bucket,
                "entry_date": before.get("entry_date"),
                "exit_date": before.get("exit_date"),
                "exit_reason": before.get("exit_reason"),
                "before_shares": before_shares,
                "after_shares": after_shares,
                "before_pnl": round_value(before_pnl, 2),
                "after_pnl": round_value(after_pnl, 2),
                "pnl_delta": round_value(pnl_delta, 2),
            }
        )

    positives = [value for value in pnl_delta_by_ticker.values() if value > 0]
    positive_total = sum(positives)
    max_positive_share = (
        max(positives) / positive_total if positive_total > 0 and positives else None
    )
    return {
        "touched_rs20_disallowed_bucket_trades": touched,
        "changed_rs20_disallowed_bucket_trades": changed,
        "pnl_delta_by_ticker": {
            ticker: round_value(value, 2)
            for ticker, value in sorted(pnl_delta_by_ticker.items())
        },
        "max_single_ticker_positive_share": round_value(max_positive_share, 4),
        "details": details,
    }


def aggregate_results(by_window: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline_ev = sum(
        (window["baseline"]["metrics"].get("expected_value_score") or 0.0)
        for window in by_window.values()
    )
    baseline_pnl = sum(
        (window["baseline"]["metrics"].get("total_pnl") or 0.0)
        for window in by_window.values()
    )
    aggregate: dict[str, Any] = {}
    for variant in VARIANTS:
        ev_sum = 0.0
        pnl_sum = 0.0
        trade_count_sum = 0
        signals_generated_sum = 0
        signals_survived_sum = 0
        min_survival_rate: float | None = None
        max_drawdown = 0.0
        max_drawdown_worsening = 0.0
        improved = 0
        regressed = 0
        touched = 0
        changed = 0
        suppressed = 0
        pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
        by_window_delta: dict[str, Any] = {}

        for window_name, window in by_window.items():
            metrics = window["variants"][variant]["metrics"]
            delta = window["variants"][variant]["delta_vs_baseline"]
            trade_changes = window["variants"][variant]["trade_changes"]
            ev_sum += metrics.get("expected_value_score") or 0.0
            pnl_sum += metrics.get("total_pnl") or 0.0
            trade_count_sum += int(metrics.get("trade_count") or 0)
            signals_generated_sum += int(metrics.get("signals_generated") or 0)
            signals_survived_sum += int(metrics.get("signals_survived") or 0)
            survival = metrics.get("survival_rate")
            if isinstance(survival, (int, float)):
                min_survival_rate = (
                    float(survival)
                    if min_survival_rate is None
                    else min(min_survival_rate, float(survival))
                )
            max_drawdown = max(max_drawdown, float(metrics.get("max_drawdown_pct") or 0.0))
            dd_delta = delta.get("max_drawdown_pct")
            if isinstance(dd_delta, (int, float)):
                max_drawdown_worsening = max(max_drawdown_worsening, float(dd_delta))
            ev_delta = delta.get("expected_value_score")
            if isinstance(ev_delta, (int, float)) and ev_delta > 0:
                improved += 1
            elif isinstance(ev_delta, (int, float)) and ev_delta < 0:
                regressed += 1
            touched += int(trade_changes.get("touched_rs20_disallowed_bucket_trades") or 0)
            changed += int(trade_changes.get("changed_rs20_disallowed_bucket_trades") or 0)
            suppressed += int(
                window["variants"][variant]["suppression_summary"].get(
                    "suppressed_signal_count"
                )
                or 0
            )
            for ticker, value in (
                trade_changes.get("pnl_delta_by_ticker") or {}
            ).items():
                pnl_delta_by_ticker[ticker] += float(value or 0.0)
            by_window_delta[window_name] = delta

        ev_delta_sum = ev_sum - baseline_ev
        pnl_delta_sum = pnl_sum - baseline_pnl
        positives = [value for value in pnl_delta_by_ticker.values() if value > 0]
        positive_total = sum(positives)
        max_positive_share = (
            max(positives) / positive_total if positives and positive_total > 0 else None
        )
        aggregate[variant] = {
            "expected_value_score_sum": round_value(ev_sum, 4),
            "expected_value_score_delta_sum": round_value(ev_delta_sum, 4),
            "expected_value_score_delta_pct": round_value(
                ev_delta_sum / abs(baseline_ev) if baseline_ev else None,
                6,
            ),
            "total_pnl_sum": round_value(pnl_sum, 2),
            "total_pnl_delta_sum": round_value(pnl_delta_sum, 2),
            "total_pnl_delta_pct": round_value(
                pnl_delta_sum / abs(baseline_pnl) if baseline_pnl else None,
                6,
            ),
            "trade_count_sum": trade_count_sum,
            "signals_generated_sum": signals_generated_sum,
            "signals_survived_sum": signals_survived_sum,
            "min_survival_rate": round_value(min_survival_rate, 4),
            "max_drawdown_pct_max": round_value(max_drawdown, 4),
            "max_drawdown_worsening_vs_baseline": round_value(
                max_drawdown_worsening,
                4,
            ),
            "windows_ev_improved": improved,
            "windows_ev_regressed": regressed,
            "suppressed_signal_count": suppressed,
            "touched_rs20_disallowed_bucket_trades": touched,
            "changed_rs20_disallowed_bucket_trades": changed,
            "pnl_delta_by_ticker": {
                ticker: round_value(value, 2)
                for ticker, value in sorted(pnl_delta_by_ticker.items())
            },
            "max_single_ticker_positive_share": round_value(max_positive_share, 4),
            "by_window_delta": by_window_delta,
        }
    return aggregate


def choose_best(aggregate: dict[str, Any]) -> str:
    return max(
        aggregate,
        key=lambda variant: (
            aggregate[variant].get("expected_value_score_delta_sum") or -10**9,
            aggregate[variant].get("total_pnl_delta_sum") or -10**9,
        ),
    )


def gate_passed(metrics: dict[str, Any]) -> bool:
    return (
        (metrics.get("expected_value_score_delta_sum") or 0.0) > 0.0
        and (metrics.get("total_pnl_delta_sum") or 0.0) > 0.0
        and (metrics.get("windows_ev_improved") or 0) >= 2
        and (metrics.get("windows_ev_regressed") or 0) == 0
        and (metrics.get("max_drawdown_worsening_vs_baseline") or 0.0) <= 0.01
        and (metrics.get("min_survival_rate") or 0.0) >= 0.05
        and (metrics.get("touched_rs20_disallowed_bucket_trades") or 0) >= 3
        and (
            metrics.get("max_single_ticker_positive_share") is None
            or metrics.get("max_single_ticker_positive_share") <= 0.50
        )
    )


def build_artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} RS20 Entry-State Regime Scope",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{payload['best_variant']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Aggregate",
        "",
        "| Variant | EV delta | PnL delta | Windows EV +/- | Touched trades | Suppressed signals | Max DD change | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for variant, metrics in payload["aggregate"].items():
        lines.append(
            "| {variant} | {ev} | {pnl} | {up}/{down} | {touched} | {suppressed} | {dd} | {gate} |".format(
                variant=variant,
                ev=metrics["expected_value_score_delta_sum"],
                pnl=metrics["total_pnl_delta_sum"],
                up=metrics["windows_ev_improved"],
                down=metrics["windows_ev_regressed"],
                touched=metrics["touched_rs20_disallowed_bucket_trades"],
                suppressed=metrics["suppressed_signal_count"],
                dd=metrics["max_drawdown_worsening_vs_baseline"],
                gate="PASS" if gate_passed(metrics) else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Window Deltas",
            "",
            "| Variant | Window | EV delta | PnL delta | Return delta | Sharpe delta | DD delta | Survival delta |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for variant, metrics in payload["aggregate"].items():
        for window, delta in metrics["by_window_delta"].items():
            lines.append(
                "| {variant} | {window} | {ev} | {pnl} | {ret} | {sharpe} | {dd} | {surv} |".format(
                    variant=variant,
                    window=window,
                    ev=delta["expected_value_score"],
                    pnl=delta["total_pnl"],
                    ret=delta["strategy_total_return_pct"],
                    sharpe=delta["sharpe_daily"],
                    dd=delta["max_drawdown_pct"],
                    surv=delta["survival_rate"],
                )
            )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only experiment. No shared policy, run adapter, backtester adapter, orders, exits, ranking, filters, LLM boundary, or universe membership changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    gate2 = audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2['missing_required_fields']}")

    by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for window_name, spec in WINDOWS.items():
        baseline_result, _ = run_backtest(spec)
        baseline_metrics = summarize_result(baseline_result)
        window_payload: dict[str, Any] = {
            "window": window_name,
            "window_spec": spec,
            "baseline": {
                "metrics": baseline_metrics,
                "trade_count": len(baseline_result.get("trades") or []),
            },
            "variants": {},
        }
        baseline_trades = [dict(trade) for trade in baseline_result.get("trades") or []]
        for variant, config in VARIANTS.items():
            variant_result, suppressions = run_backtest(
                spec,
                variant=variant,
                allowed_buckets=tuple(config["allowed_buckets"]),
            )
            variant_metrics = summarize_result(variant_result)
            window_payload["variants"][variant] = {
                "metrics": variant_metrics,
                "delta_vs_baseline": metric_delta(variant_metrics, baseline_metrics),
                "suppression_summary": summarize_suppressions(suppressions),
                "trade_changes": summarize_trade_changes(
                    baseline_trades,
                    [dict(trade) for trade in variant_result.get("trades") or []],
                    tuple(config["allowed_buckets"]),
                ),
            }
        by_window[window_name] = window_payload

    aggregate = aggregate_results(by_window)
    best_variant = choose_best(aggregate)
    best = aggregate[best_variant]
    passed = gate_passed(best)
    decision = (
        "accepted_replay_only_shared_policy_candidate"
        if passed
        else "rejected_rs20_entry_state_regime_scope"
    )
    if passed:
        decision_rationale = (
            "The best regime-scope variant improved EV/PnL across the canonical "
            "windows without unacceptable drawdown, survival, or concentration "
            "damage. It is not retained as production logic in this run; a shared "
            "portfolio policy and parity tests are required before promotion."
        )
        rejection_reason = None
    else:
        decision_rationale = (
            "Rejected: scoping the accepted RS20 entry-state top-up by regime "
            "bucket did not clear the three-window Gate 4 criteria, so the shared "
            "RS20 policy remains unchanged and nearby regime-scope variants should "
            "not be retried without new evidence."
        )
        rejection_reason = decision_rationale

    timestamp = utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted RS20 entry-state 1.10x top-up may be weaker in "
            "defensive or non-risk-on regime-exit buckets; restricting the "
            "existing top-up by regime scope could improve risk-adjusted EV "
            "without changing the RS20 threshold, multiplier, entries, exits, "
            "ranking, candidate pool, or LLM boundary."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "change_type": "rs20_entry_state_regime_scope_replay",
        "mechanism_family": "entry_state_rs20_regime_scoped_allocation",
        "changed_variable": "rs20_entry_state_regime_eligibility_scope",
        "single_causal_variable": "regime buckets allowed to receive accepted RS20 entry-state top-up",
        "date_range": {
            name: {
                "start": spec["start"],
                "end": spec["end"],
                "snapshot": spec["snapshot"],
            }
            for name, spec in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Baseline is the "
            "current accepted core stack; variants patch only portfolio sizing "
            "eligibility for the already accepted RS20 entry-state top-up."
        ),
        "gate2_field_audit": gate2,
        "historical_experiment_check": {
            "exp-20260510-010": "Found broad RS20 entry-state allocation lead in replay-only form.",
            "exp-20260510-012": "Promoted 1.10x cap-aware RS20 entry-state sizing into shared policy; nearby scalar/threshold retunes are banned.",
            "exp-20260511-102": "Accepted-stack loss taxonomy showed some RS20-sized low-MFE losses but required an ex-ante state/event discriminator before any change.",
            "why_this_is_not_a_repeat": "This tests regime eligibility scope, not the RS20 threshold, multiplier, missed-candidate sleeve, platform subset, or no-gap same-sample variant.",
        },
        "parameters": {
            "accepted_rs20_multiplier": 1.10,
            "accepted_rs20_min_rel_return": "ticker 20d return minus SPY 20d return >= 5 percentage points",
            "variants": VARIANTS,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "exits",
                "add-ons",
                "base risk scalars",
                "RS20 threshold",
                "RS20 multiplier",
                "LLM/news",
            ],
        },
        "before_metrics": {
            name: payload["baseline"]["metrics"] for name, payload in by_window.items()
        },
        "after_metrics": {
            variant: {
                name: by_window[name]["variants"][variant]["metrics"]
                for name in by_window
            }
            for variant in VARIANTS
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "delta_metrics": aggregate,
        "best_variant": best_variant,
        "expected_value_score_delta": best["expected_value_score_delta_sum"],
        "gate4": {
            "passed": passed,
            "windows_ev_improved": best["windows_ev_improved"],
            "windows_ev_regressed": best["windows_ev_regressed"],
            "min_survival_rate": best["min_survival_rate"],
            "max_drawdown_worsening_vs_baseline": best[
                "max_drawdown_worsening_vs_baseline"
            ],
            "basis": "Actual BacktestEngine reruns on all three canonical windows.",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Do not retry nearby RS20 regime-scope variants unless a forward "
            "or event/news discriminator shows defensive/non-risk-on RS20 "
            "leaders have different replacement value."
        ),
        "related_files": [
            str(Path(__file__).relative_to(REPO_ROOT)),
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
        ],
    }

    log_record = {
        key: payload[key]
        for key in [
            "experiment_id",
            "timestamp",
            "lane",
            "status",
            "decision",
            "hypothesis",
            "alpha_hypothesis_category",
            "change_type",
            "mechanism_family",
            "changed_variable",
            "single_causal_variable",
            "date_range",
            "backtest_protocol",
            "gate2_field_audit",
            "historical_experiment_check",
            "parameters",
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "best_variant",
            "expected_value_score_delta",
            "gate4",
            "llm_metrics",
            "production_impact",
            "decision_rationale",
            "rejection_reason",
            "next_evidence_needed",
            "related_files",
        ]
    }
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "RS20 entry-state regime-scope replay",
        "decision": decision,
        "best_variant": best_variant,
        "expected_value_score_delta": best["expected_value_score_delta_sum"],
        "total_pnl_delta": best["total_pnl_delta_sum"],
        "windows_ev_improved": best["windows_ev_improved"],
        "windows_ev_regressed": best["windows_ev_regressed"],
        "next_action": (
            "Implement shared policy plus parity tests before promotion."
            if passed
            else "Keep accepted RS20 policy unchanged; avoid nearby regime-scope retry."
        ),
    }

    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(build_artifact(payload), encoding="utf-8")
    append_jsonl(EXPERIMENT_LOG, log_record)
    print(json.dumps(ticket, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
