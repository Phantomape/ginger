# Backtesting Commands

This file defines the single canonical deterministic backtest command used by
alpha experiments. Other ad hoc runs may be useful for debugging, but they are
not acceptance evidence.

## Canonical Command

Use exactly this command shape for production-parity fixed-window backtests.
Production-equivalent behavior is enabled by default in `quant/backtester.py`:
regime-aware exits are on, and the shared position-action replay container is on.
As of exp-20260429-017, pure `TRAILING_STOP` partial reduces are disabled by
that shared policy, so default replay does not re-enable the rejected daily
trim loop. Advisory production exits such as `SIGNAL_TARGET`, profit ladders,
and time stops are disclosed under `known_biases.exit_policy_unreplayed`; they
are not automatically executed by the canonical backtest.

```powershell
cd D:\Github\ginger

.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-snapshot <SNAPSHOT>
```

Window labels used in experiment logs:

| Label | Date range | Snapshot |
| --- | --- | --- |
| `late_strong` | `2025-10-23 -> 2026-04-21` | `data\ohlcv_snapshot_20251023_20260421.json` |
| `mid_weak` | `2025-04-23 -> 2025-10-22` | `data\ohlcv_snapshot_20250423_20251022.json` |
| `old_thin` | `2024-10-02 -> 2025-04-22` | `data\ohlcv_snapshot_20241002_20250422.json` |

Current accepted fixed-window metrics after exp-20260501-006:

| Label | EV score | Sharpe daily | Total PnL | Return | Max DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 2.7000 | 4.30 | $62,788.03 | 62.79% | 4.39% | 78.95% | 19 | 80.39% |
| `mid_weak` | 1.2036 | 2.58 | $46,654.10 | 46.65% | 7.99% | 52.38% | 21 | 79.25% |
| `old_thin` | 0.2563 | 1.27 | $20,181.65 | 20.18% | 6.88% | 40.91% | 22 | 91.67% |

Latest accepted result: `trend_long` Financials signals whose 20-day return is
above the equal-weight Financials sector 20-day return now size at a total
2.5x risk budget. Non-leader Financials remain at the accepted 1.5x budget.
This improved PnL in 2/3 fixed windows with no trade-count or win-rate
regression: aggregate PnL `+$7,834.20` / `+6.43%`, aggregate EV `+0.1974`.
The main cost is `mid_weak` max drawdown rising from 6.16% to 7.99%, still
inside the drawdown cap. Do not retry nearby Financials leader multipliers
without forward evidence or a materially different sector-relative feature.

Previous accepted result: GLD/IAU `trend_long` targets now use 8 ATR while SLV
and other Commodity trend targets remain on the accepted 7 ATR path. This
improved EV in all three fixed windows, with aggregate `EV delta +0.2537`,
aggregate PnL `+$4,554.88` / `+3.89%`, and no drawdown, trade-count, or win-rate
regression. It clears Gate 4 via `late_strong` daily Sharpe `+0.12`. Do not
continue nearby 8.5/9 ATR gold-target sweeps without forward or event/news
evidence.

Latest comparison result: lifting otherwise-unmodified `risk_on` signals with
`0.10 <= regime_exit_score < 0.20` to a 1.6x non-stacking risk budget improved
aggregate PnL by `$6,531.45` / `+5.90%` and aggregate EV by `+0.1814`.
EV improved in `late_strong` and `mid_weak`; `old_thin` regressed by `-0.0018`
EV and max drawdown rose by `+0.96 pp`, so nearby multiplier tuning should not
be repeated without forward or tail-risk evidence.

Latest add-on capacity result: matching `ADDON_MAX_POSITION_PCT` to the current
40% initial position cap was rejected as positive but immaterial. EV and PnL
improved in all three fixed windows, but the three-window PnL deltas
(`+$985.51`, `+$468.11`, `+$258.13`) added only `+1.46%`, below Gate 4's +5%
PnL threshold; Sharpe, drawdown, trade count, win rate, and survival did not
move enough to pass another acceptance criterion. Do not continue nearby add-on
cap tuning above 35% without forward concentration evidence or a stronger
add-on quality discriminator.

Previous comparison result: disabling pure `TRAILING_STOP` partial reduces
improved EV in 2/3 windows and PnL in 2/3 windows, with aggregate
`EV delta +0.4028`, `PnL delta +$12,837.60`, and trailing partial-reduce
executions dropping from 16 to 0. The comparison artifact is
`data/experiments/exp-20260429-011/exp-20260429-011_trailing_partial_reduce_parity.json`.

## High-Importance Metrics

The backtester emits these extra measurement fields for alpha experiments:

| Field | Why it matters |
| --- | --- |
| `capital_efficiency` | Shows return/PnL per trade and per calendar slot-day, so a strategy that ties up capital for too long is visible even if total return looks fine. |
| `sizing_rule_signal_attribution` | Counts how often each risk multiplier touched candidate signals, including zero-risk signals that never became trades. |
| `sizing_rule_trade_attribution` | Shows observed trade outcomes for positions that carried non-neutral sizing multipliers. This is attribution, not a counterfactual PnL claim. |
| `single_window_quality` | Summarizes whether the current window is positive on EV, return, daily Sharpe, and drawdown guardrails. |
| `multi_window_robustness` | Added to cross-window diagnostics; summarizes positive windows, EV spread, worst drawdown, and an observation-only robustness score. |

## Exit Policy Replay Scope

The canonical backtest currently executes full-position `stop_price` and
`target_price` exits. Production daily runs also compute held-position advisory
rules through `trend_signals.py` / `position_manager.py`, surface them to the
LLM workflow, and may preserve unexecuted `REDUCE`/`EXIT` advice through
`pending_actions.py`.

That advisory lifecycle is not treated as proven alpha until it has shadow
attribution. The backtester therefore emits
`known_biases.exit_policy_unreplayed`, `exit_advisory_shadow_attribution`, and
a matching caveat in saved results. This is measurement, not a license to add
backtester-only exit logic.

`exp-20260429-032` is the anti-repeat guardrail: a simple replay that converted
`target_price` into a next-open 33% `SIGNAL_TARGET` partial reduce was rejected
after EV and PnL regressed in all three fixed windows. Future retries need a
complete shared lifecycle design, not just a bare target trim.

`pending_actions.json` is also production-only execution memory. The canonical
backtest now discloses its presence and open action counts under
`known_biases.pending_action_replay_unreplayed`, but does not replay the current
ledger because it is not a point-in-time historical account snapshot.

## Production Parity Check

Backtests are acceptance evidence only when the tested behavior can be executed
or surfaced by the daily production path. Before accepting a strategy-affecting
change, check `docs/production_backtest_parity.md` and record whether the
change is:

- shared policy used by both `quant/backtester.py` and `quant/run.py`,
- a production adapter/reporting update,
- or an explicitly allowed replay-only difference such as LLM/news archive
  coverage.

If the fixed windows improve only because `backtester.py` contains logic that
`run.py` cannot call or expose, treat the result as a measurement defect, not
as accepted alpha.
