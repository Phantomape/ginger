"""Convergence criteria for the quant system - single source of truth.

CLAUDE3.md section "收敛标准" codified as code so iteration decisions are
deterministic.  Each criterion has a fixed threshold; the function returns
per-criterion booleans plus an overall `converged` flag.

The "must beat passive index" criterion was added on top of the original
6 criteria after the user pointed out the system has no value if it cannot
clear SPY / QQQ buy-and-hold over the same window.
"""

CRITERIA = {
    "sharpe_min":         0.5,
    "max_drawdown_max":   0.20,
    "trade_count_min":    15,
    "win_rate_min":       0.40,
    "survival_rate_min":  0.05,
}


def _check(value, predicate):
    """Wrap a value + pass predicate so missing data → pass=False (not crash)."""
    if value is None:
        return {"value": None, "pass": False}
    return {"value": value, "pass": bool(predicate(value))}


def compute_expected_value_score(result):
    """Single-source north-star metric for strategy iteration.

    Definition:
        expected_value_score = strategy_total_return_pct * sharpe_daily

    Returns None when either input is unavailable. The score is rounded to
    4 decimals so saved JSON and CLI output remain stable across runs.
    """
    benchmarks = result.get("benchmarks") or {}
    strat_return = benchmarks.get("strategy_total_return_pct")
    sharpe_daily = result.get("sharpe_daily")
    if strat_return is None or sharpe_daily is None:
        return None
    return round(strat_return * sharpe_daily, 4)


def compute_convergence(result, phantom_rules_clean=True):
    """Apply the convergence criteria to a backtester result dict.

    Args:
        result: dict returned by `BacktestEngine.run()`.  Required keys:
            sharpe, max_drawdown_pct, total_trades, win_rate, survival_rate,
            benchmarks (dict with spy_buy_hold_return_pct,
            qqq_buy_hold_return_pct, strategy_total_return_pct).
        phantom_rules_clean: caller asserts that every active rule's
            pre-condition fields are populated in production data.  Defaults
            True; pass False when a known phantom rule is in flight (e.g.
            TIME_STOP firing without entry_date).

    Returns:
        {
          "converged": bool,
          "criteria":  {name: {"value": ..., "threshold": ..., "pass": bool}},
          "summary":   "X/N criteria pass",
        }
    """
    benchmarks = result.get("benchmarks") or {}
    spy = benchmarks.get("spy_buy_hold_return_pct")
    qqq = benchmarks.get("qqq_buy_hold_return_pct")
    strat_return = benchmarks.get("strategy_total_return_pct")

    criteria = {
        "sharpe_above_min": {
            **_check(result.get("sharpe"),
                     lambda v: v >= CRITERIA["sharpe_min"]),
            "threshold": CRITERIA["sharpe_min"],
        },
        "max_drawdown_under_cap": {
            **_check(result.get("max_drawdown_pct"),
                     lambda v: v <= CRITERIA["max_drawdown_max"]),
            "threshold": CRITERIA["max_drawdown_max"],
        },
        "trade_count_above_min": {
            **_check(result.get("total_trades"),
                     lambda v: v >= CRITERIA["trade_count_min"]),
            "threshold": CRITERIA["trade_count_min"],
        },
        "win_rate_above_min": {
            **_check(result.get("win_rate"),
                     lambda v: v >= CRITERIA["win_rate_min"]),
            "threshold": CRITERIA["win_rate_min"],
        },
        "survival_rate_above_min": {
            **_check(result.get("survival_rate"),
                     lambda v: v >= CRITERIA["survival_rate_min"]),
            "threshold": CRITERIA["survival_rate_min"],
        },
        "no_phantom_rules": {
            "value": phantom_rules_clean,
            "threshold": True,
            "pass": bool(phantom_rules_clean),
        },
        # Strict-greater-than: matching the index is not a win.
        "beats_spy_buy_hold": {
            "value": strat_return,
            "threshold": spy,
            "pass": (strat_return is not None and spy is not None
                     and strat_return > spy),
        },
        "beats_qqq_buy_hold": {
            "value": strat_return,
            "threshold": qqq,
            "pass": (strat_return is not None and qqq is not None
                     and strat_return > qqq),
        },
    }

    passes = sum(1 for c in criteria.values() if c["pass"])
    total  = len(criteria)
    return {
        "converged": passes == total,
        "criteria":  criteria,
        "summary":   f"{passes}/{total} criteria pass",
    }


def format_convergence_report(report):
    """ASCII table of per-criterion pass/fail for CLI output."""
    if not report or "criteria" not in report:
        return "  (no convergence data)"

    lines = []
    name_w = max(len(n) for n in report["criteria"]) + 2
    for name, c in report["criteria"].items():
        mark = "PASS" if c["pass"] else "FAIL"
        val = c["value"]
        thr = c["threshold"]
        if isinstance(val, float):
            val_s = f"{val:.4f}"
        else:
            val_s = str(val)
        if isinstance(thr, float):
            thr_s = f"{thr:.4f}"
        else:
            thr_s = str(thr)
        lines.append(f"  {mark:<5} {name:<{name_w}} value={val_s:<10} threshold={thr_s}")

    verdict = "CONVERGED" if report["converged"] else "NOT CONVERGED"
    lines.append("  " + "-" * 60)
    lines.append(f"  {verdict}  ({report['summary']})")
    return "\n".join(lines)
