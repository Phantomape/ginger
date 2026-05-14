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

## 试点子组合回测

试点子组合回测（pilot sleeve replay）是显式开启的 point-in-time
模式。默认标准回测仍然是 core-only，不会把 `INTC` / `LITE` / `BE`
等试点 ticker 混入主候选池，也不会占用 core `MAX_POSITIONS` slot。

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-snapshot <SNAPSHOT> --include-pilot-sleeve
```

开启后，`AI_INFRA_PILOT`（AI 基建试点子组合）会使用
`data\universe_registry.json` 和 `data\universe_events.jsonl` 做每日
PIT 资格判断。backtester 会预加载截至回测结束日已经允许交易的 pilot
OHLCV，但每天是否能交易仍取决于当日 `first_trade_allowed_as_of` 和状态
回放结果。这个模式不会写入生产 append-only 日志
`data\pilot_competition_decisions.jsonl`；counterfactual snapshot 与 outcome
attribution 只保存在本次回测的 `result["pilot_sleeve_replay"]` 里。

历史三窗口均早于 `2026-05-01`，因此加上 `--include-pilot-sleeve` 后
`pilot_sleeve_replay.entries` 应为 `0`，core metrics 也不应变化。这是
PIT 无泄漏的正确结果，不是 pilot sleeve 没有接入。

## AI_INFRA_AGGRESSIVE Sleeve Validation

The canonical command above remains the core-only baseline. It must stay
core-only so pilot sleeve results do not contaminate accepted core metrics.

Any experiment, rollout, parameter change, ticker addition/removal, slot
change, capital/risk scalar change, bull-booster change, or promotion decision
that touches `AI_INFRA_AGGRESSIVE` must also run the pilot-sleeve replay:

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-snapshot <SNAPSHOT> --include-pilot-sleeve
```

Acceptance records for `AI_INFRA_AGGRESSIVE` must report both:

- the unchanged core-only canonical baseline; and
- the `--include-pilot-sleeve` result, including
  `result["pilot_sleeve_replay"]`, direct PnL, cash-relative PnL, replacement
  value, risk-adjusted replacement value, selected/sliced candidates, sleeve
  slot usage, segment exposure, and bull-booster status.

If the fixed historical windows predate the sleeve activation date, zero pilot
entries are a valid PIT result. In that case, AI sleeve evidence must come from
post-activation replay, forward decision logs, or daily attribution artifacts;
do not infer that the sleeve is disconnected merely because old windows show
`pilot_sleeve_replay.entries == 0`.

Window labels used in experiment logs:

| Label | Date range | Snapshot |
| --- | --- | --- |
| `late_strong` | `2025-10-23 -> 2026-04-21` | `data\ohlcv_snapshot_20251023_20260421.json` |
| `mid_weak` | `2025-04-23 -> 2025-10-22` | `data\ohlcv_snapshot_20250423_20251022.json` |
| `old_thin` | `2024-10-02 -> 2025-04-22` | `data\ohlcv_snapshot_20241002_20250422.json` |

Current accepted fixed-window metrics after `exp-20260514-023` promoted the
trend Financials sector-leader 50% sleeve-specific position cap:

| Label | EV score | Sharpe daily | Total PnL | Return | Max DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 4.4313 | 4.35 | $101,873.18 | 101.87% | 5.98% | 78.95% | 19 | 80.39% |
| `mid_weak` | 1.8324 | 2.69 | $68,124.12 | 68.12% | 10.13% | 52.38% | 21 | 79.25% |
| `old_thin` | 0.4703 | 1.40 | $33,591.36 | 33.59% | 8.72% | 40.91% | 22 | 91.67% |

Artifact note:
`data/experiments/exp-20260514-023/financials_sector_leader_cap.json`
records the latest accepted three-window comparison. Aggregate accepted-stack
EV is `6.7340`; aggregate PnL is `$203,588.66`.

Latest accepted core-sizing result: `exp-20260514-023` keeps the existing
`trend_long + Financials + financials_sector_leader=true` 2.5x total risk
budget unchanged but lets only that already-accepted sleeve use a 50%
single-position cap in shared `portfolio_engine.py`. The change improved EV
and PnL in `mid_weak` and `old_thin`, left `late_strong` unchanged, and kept
trade count and survival unchanged: aggregate EV `+0.1173`, aggregate PnL
`+$3,782.63`, max drawdown drift stayed inside the Gate 4 guardrail at
`+0.24 pp` worst window, and there is no production/backtest split because
both adapters call the same shared sizing module. Do not retry nearby
Financials raw multipliers, target-width variants, or cap values on these
frozen windows without forward evidence or a materially different
production-visible discriminator.

Latest accepted default-off Space replay result: `exp-20260514-024` adds only
the shared Space metadata/helper
`space_forward_replacement_iwm_leader_trend_risk_scalar=1.025` for
`trend_long` signals already in the closed 10d forward same-theme
replacement-strength bucket when IWM 20d momentum leads SPY. It uses the same
three window labels above with frozen Space snapshots and keeps live Space
slots at zero. Aggregate default-off Space EV improved `+0.2282` and PnL
improved `+$6,852.85`; window EV deltas were `late_strong +0.0449`,
`mid_weak +0.1135`, and `old_thin +0.0698`. Max drawdown drift was `+0.34 pp`,
trade count stayed `68`, and minimum survival stayed `65.33%`. Stronger
nearby scalars (`1.05x+`) failed the `0.5 pp` drawdown guardrail, so do not
retry adjacent Space IWM-leader trend-strength multipliers on these frozen
windows without new forward evidence.

Previous accepted core-sizing result: `exp-20260514-018` keeps the existing
`trend_long + Commodities + pct_from_52w_high >= -3%` risk boost unchanged but
lets only that already-accepted sleeve use a 50% single-position cap in shared
`portfolio_engine.py`. The change improved EV and PnL in all three fixed
windows with unchanged trade count and survival: aggregate EV `+0.1319`,
aggregate PnL `+$5,902.08`, max drawdown drift stayed inside the Gate 4
guardrail at `+0.42 pp`, and there is no production/backtest split because
both adapters call the same shared sizing module. Do not retry nearby raw
commodity multipliers or cap values on these frozen windows without forward
evidence or a materially different production-visible discriminator.

Previous accepted core-sizing result: `exp-20260513-036` computes the
signal-day ticker-minus-SPY open-to-close return in shared `risk_engine.py`,
then applies a cap-aware 1.10x post-sizing top-up in `portfolio_engine.py` only
when a `trend_long` / `breakout_long` signal already qualified for the clean
`risk_on` SPY-relative leader sizing path and also beat SPY on the signal day.
The change improved EV and PnL in `late_strong` and `old_thin`, left
`mid_weak` unchanged, and preserved trade count and survival: aggregate EV
`+0.0246`, aggregate PnL `+$2,620.01`, max drawdown drift within the Gate 4
guardrail, and no production/backtest split because both adapters use the same
shared risk and sizing modules. Do not retry nearby clean SPY-leader signal-day
scalars on these frozen windows without forward evidence or a materially
different production-visible discriminator.

Previous accepted core-sizing result: `exp-20260513-030` computes
`momentum_60d_pct` in shared `feature_layer.py`, tags already-qualified
`trend_long` / `breakout_long` stock signals whose same-day 60-trading-day
return is in the top quintile of the non-ETF/non-commodity stock universe in
`risk_engine.py`, then applies a cap-aware 1.15x post-sizing top-up in
`portfolio_engine.py`. The change improved EV and PnL in all three fixed
windows with unchanged trade count and survival: aggregate EV `+0.1094`,
aggregate PnL `+$4,615.93`, max drawdown drift within the Gate 4 guardrail,
and no production/backtest split because both adapters use the same shared
modules. Do not retry nearby RS60 top-quintile scalars on these frozen windows
without forward evidence or a materially different production-visible
discriminator.

Previous accepted core-sizing result: `exp-20260513-007` tags signals whose
own signal-day open-to-close return is positive in shared `feature_layer.py` /
`risk_engine.py`, then applies a cap-aware 1.05x post-sizing top-up in
`portfolio_engine.py`. The change improved EV and PnL in all three fixed
windows with unchanged trade count and survival: aggregate EV `+0.0626`,
aggregate PnL `+$2,223.59`, max drawdown drift within the Gate 4 guardrail,
and no production/backtest split because both adapters use the same shared
modules. Do not retry nearby own-candle scalars on these frozen windows without
forward evidence or a materially narrower production-visible discriminator.

Previous accepted taxonomy result: `exp-20260510-015` maps TRIP through shared
sector enrichment as Consumer Discretionary instead of `Unknown`. This is a
small alpha/data-quality improvement, not a new threshold: aggregate EV
improved `+0.0171` / `+0.27%`, aggregate PnL improved `+$403.46` / `+0.22%`,
trade count and survival stayed unchanged, and max drawdown did not worsen.
Do not repeat single-ticker taxonomy mining on frozen samples; valid follow-up
taxonomy work needs a real production universe classification gap and the same
three-window no-regression evidence.

Previous accepted core-sizing result: `exp-20260510-012` promoted a shared
RS20 entry-state leader top-up. Signals whose ticker 20-day return beats SPY
20-day return by at least 5 percentage points are tagged in `risk_engine.py`;
`portfolio_engine.py` then applies a cap-aware 1.10x post-sizing share top-up
inside the existing position cap for that signal. The change improved EV and
PnL in all three fixed windows with unchanged trade count and survival:
aggregate EV `+0.2259` / `+3.74%`, aggregate PnL `+$6,364.03` / `+3.58%`.
The stronger 1.25x and 1.50x variants were rejected because `mid_weak` max
drawdown worsened too much. Do not retry nearby RS20 scalars on these frozen
windows without forward evidence or a materially different discriminator.

Previous accepted production-visible result: `exp-20260510-003` promoted the
`rotation_breakout_leadership` 3.0x event tilt into a shared default-off paper
adapter. This changed no core backtest metrics, no live/default orders, and no
canonical fixed-window baseline values at the time.

Latest accepted core-sizing result before that: `trend_long` Financials signals
whose 20-day return is above the equal-weight Financials sector 20-day return
now size at a total 2.5x risk budget. Non-leader Financials remain at the
accepted 1.5x budget. This improved PnL in 2/3 fixed windows with no
trade-count or win-rate regression: aggregate PnL `+$7,834.20` / `+6.43%`,
aggregate EV `+0.1974`. The main cost is `mid_weak` max drawdown rising from
6.16% to 7.99%, still inside the drawdown cap. Do not retry nearby Financials
leader multipliers without forward evidence or a materially different
sector-relative feature.

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
