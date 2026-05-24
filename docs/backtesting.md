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

New backtest result files are written under `data\backtests\`. Legacy
root-level `data\backtest_results_*.json` references remain readable through
`quant/data_paths.py` compatibility resolvers when older checkouts still have
those files.

## 试点子组合回测

试点子组合回测（pilot sleeve replay）是显式开启的 point-in-time
模式。默认标准回测仍然是 core-only，不会把 `INTC` / `LITE` / `BE`
等试点 ticker 混入主候选池，也不会占用 core `MAX_POSITIONS` slot。

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-snapshot <SNAPSHOT> --include-pilot-sleeve
```

开启后，`AI_INFRA_PILOT`（AI 基建试点子组合）会使用
`data\state\universe\universe_registry.json` 和
`data\state\universe\universe_events.jsonl` 做每日
PIT 资格判断。backtester 会预加载截至回测结束日已经允许交易的 pilot
OHLCV，但每天是否能交易仍取决于当日 `first_trade_allowed_as_of` 和状态
回放结果。这个模式不会写入生产 append-only 日志
`data\ledgers\pilot_competition_decisions.jsonl`；counterfactual snapshot 与 outcome
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
| `late_strong` | `2025-10-23 -> 2026-04-21` | `data\ohlcv\ohlcv_snapshot_20251023_20260421.json` |
| `mid_weak` | `2025-04-23 -> 2025-10-22` | `data\ohlcv\ohlcv_snapshot_20250423_20251022.json` |
| `old_thin` | `2024-10-02 -> 2025-04-22` | `data\ohlcv\ohlcv_snapshot_20241002_20250422.json` |

Current accepted fixed-window metrics after core `exp-20260517-009`
(`ample_slot_stock_rank1_topup`) promoted the stock-only ample-slot rank-1
post-sizing top-up on top of the accepted scarce-slot rank-1 top-up:

| Label | EV score | Sharpe daily | Total PnL | Return | Max DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 5.1628 | 4.41 | $117,072.92 | 117.07% | 6.65% | 83.33% | 18 | 80.39% |
| `mid_weak` | 2.1402 | 2.74 | $78,110.11 | 78.11% | 11.19% | 52.38% | 21 | 79.25% |
| `old_thin` | 0.5911 | 1.49 | $39,667.96 | 39.67% | 10.01% | 40.91% | 22 | 86.67% |

Artifact note:
`data/experiments/exp-20260517-009/`
records the latest accepted three-window comparison. Aggregate accepted-stack
EV is `7.8941`; aggregate PnL is `$234,850.99`.

Previous accepted default-off state-surface paper rank-quality result:
`exp-20260518-020`
keeps core metrics unchanged and keeps the accepted rotation-only surface,
`ret20_excess_spy >= 0.0` gate, top-five queue, active cap, 20-day hold,
regime-aware rank-notional profile, candidate-breadth override,
score-compression override, and rank-2 ret20-lead override fixed, but adds a
production-visible score/ret20 disagreement override. When rank 2 leads rank 1
on `ret20_excess_spy` by at least `0.005` and rank 1 still leads rank 2 on
composite score by at least `0.30`, the paper-notional profile is
`[1.0, 1.85, 1.1, 0.675, 0.35]` times the $10,000 base. Versus the accepted
`exp-20260518-018` rank-2 ret20-lead baseline, aggregate paper-overlay EV
improved `+0.0575` and PnL improved `+$1,292.85`, with no EV-regressed window
(`late_strong unchanged`, `mid_weak +0.0376`, `old_thin +0.0199`). The rule
adjusted 6 paper trades across 2 windows, did not worsen max drawdown, lives in
shared `state_surface_sleeve.py`, is surfaced by the production default-off
paper path, and has focused parity tests; live/default orders remain disabled.

Previous accepted state-surface paper rank-dominance result: `exp-20260518-023`
keeps core metrics unchanged and keeps the accepted `exp-20260518-020`
state-surface stack fixed, but adds a production-visible rank-1 ret20 dominance
plus score-gap paper allocation override. When rank 1 leads rank 2 on
`ret20_excess_spy` by at least `0.15` and rank 1 leads rank 2 on composite
score by at least `0.45`, the paper-notional profile is
`[1.6, 1.4, 1.0, 0.675, 0.35]` times the $10,000 base. Versus the accepted
`exp-20260518-020` baseline, aggregate paper-overlay EV improved `+0.0098` and
PnL improved `+$287.87`, with no EV-regressed window (`late_strong +0.0006`,
`mid_weak +0.0092`, `old_thin unchanged`). The rule adjusted 6 paper trades
across 2 windows, did not worsen max drawdown, lives in shared
`state_surface_sleeve.py`, is surfaced by the production default-off paper
path, and has focused parity tests; live/default orders remain disabled.

Previous accepted state-surface paper sector-cohesion result:
`exp-20260518-025` keeps the accepted `exp-20260518-023` stack fixed, but adds
a production-visible top-2 Technology sector-cohesion paper allocation
override. When the first two ranked queue candidates are both Technology, the
paper-notional profile is `[1.45, 1.7, 1.15, 0.675, 0.35]` times the $10,000
base. Versus the accepted `exp-20260518-023` baseline, aggregate paper-overlay
EV improved `+0.0759` and PnL improved `+$1,593.99`, with no EV-regressed
window (`late_strong unchanged`, `mid_weak +0.0528`, `old_thin +0.0231`). The
rule adjusted 6 paper trades across 2 windows, did not worsen max drawdown,
and kept single-ticker positive-share concentration below the `50%` guardrail
(`36.55% -> 36.80%`). The rule lives in shared `state_surface_sleeve.py`, is
surfaced by the production default-off paper path, and has focused parity
tests; live/default orders remain disabled.

Previous accepted state-surface paper residual-rank result:
`exp-20260518-027` keeps the accepted `exp-20260518-025` stack fixed, gives the
top-2 Technology sector-cohesion rule priority, and adds one residual
production-visible rank-1 60-day return paper allocation field. When rank 1's
60-day return is at least `0.50` and no higher-priority top-2 Technology rule
has applied, the paper-notional profile is `[1.2, 1.85, 1.1, 0.675, 0.35]`
times the $10,000 base. Versus the accepted sector-cohesion baseline,
aggregate paper-overlay EV improved `+0.1209` and PnL improved `+$1,606.68`,
with no EV-regressed window (`late_strong +0.0148`, `mid_weak +0.1061`,
`old_thin unchanged`). The rule adjusted 6 paper trades across 2 windows, did
not worsen max drawdown, and kept single-ticker positive-share concentration
below the `50%` guardrail (`36.80% -> 38.01%`). The rule lives in shared
`state_surface_sleeve.py`, is surfaced by the production default-off paper
path, and has focused parity tests; live/default orders remain disabled.

Latest accepted state-surface paper score-expansion result:
`exp-20260519-001` keeps the accepted `exp-20260518-027` stack fixed and adds a
residual production-visible score-expansion paper allocation field. After all
higher-priority state-surface profiles have passed, when the same-day qualified
paper queue has at least four candidates and `score_top3_spread >= 0.40`, the
shared default-off paper path uses `[1.85, 1.25, 1.0, 0.675, 0.35]` times the
`$10,000` base. Versus the accepted residual-rank baseline, aggregate
paper-overlay EV improved `+0.0552` and PnL improved `+$725.33`, with no
EV-regressed window (`late_strong +0.0408`, `mid_weak +0.0144`, `old_thin`
unchanged). The rule adjusted 6 paper trades across 2 windows, worsened max
drawdown by only `0.14pp`, and lowered single-ticker positive-share
concentration from `38.01%` to `37.43%`. The rule lives in shared
`state_surface_sleeve.py`, is surfaced by the production default-off paper
path, and has focused parity tests; live/default orders remain disabled.

Previous accepted state-surface paper rank-1 score-isolation result:
`exp-20260519-003` keeps the accepted score-expansion plus recent-repeat stack
fixed and adds a residual production-visible rank-1 score-isolation paper
allocation field. After all higher-priority state-surface profiles have passed,
when the residual score-expansion branch applies and
`score_top_to_second_gap >= 0.20`, the shared default-off paper path uses
`[2.2, 1.0, 0.7, 0.675, 0.35]` times the `$10,000` base. Versus the accepted
combined score-expansion plus recent-repeat baseline, aggregate paper-overlay
EV improved `+0.1039` and PnL improved `+$1,536.65`, with no EV-regressed
window (`late_strong +0.0790`, `mid_weak +0.0249`, `old_thin` unchanged). The
rule adjusted 6 paper trades across 2 windows, worsened max drawdown by only
`0.25pp`, and lowered single-ticker positive-share concentration from `40.70%`
to `39.68%`. The rule lives in shared `state_surface_sleeve.py`, is surfaced by
the production default-off paper path, and has focused parity tests;
live/default orders remain disabled.

Latest accepted state-surface paper rank-depth support result:
`exp-20260519-006` keeps the accepted `exp-20260519-004` stack fixed and adds
one production-visible rank-2 near-high paper support scalar. When the second
ranked same-day qualified state-surface queue candidate has its own
`features.near_high_60 >= 0.975`, only rank 2's default-off paper notional is
scaled by `1.50x` after the active profile multiplier. Versus the accepted
rank-3 near-high baseline, aggregate paper-overlay EV improved `+0.3390` and
PnL improved `+$8,382.06`, with all three windows EV-positive and no
EV-regressed window (`late_strong +0.0741`, `mid_weak +0.1265`,
`old_thin +0.1384`). The rule adjusted 5 paper trades across all 3 windows,
worsened max drawdown by only `0.02pp`, and kept single-ticker
positive-share concentration inside the `50%` guardrail (`38.43% -> 43.75%`).
The rule lives in shared `state_surface_sleeve.py`, is surfaced by the
production default-off paper path, and has focused parity tests; live/default
orders remain disabled. The broader `exp-20260519-005` front-rank near-high
support scout is rejected because `mid_weak` EV regressed and max drawdown
drift exceeded the Gate 4 guardrail.

Previous accepted state-surface paper rank-depth volume result:
`exp-20260519-021` keeps the accepted rank-3 volume-confirmation stack fixed
and adds one production-visible rank-2 volume-confirmation paper support
scalar. When the second ranked same-day qualified state-surface queue candidate
has its own `features.volume_ratio_20 >= 1.10`, only rank 2's default-off paper
notional is scaled by `1.10x` after the active profile multiplier. Versus the
accepted `exp-20260519-015` rank-3 volume baseline, aggregate paper-overlay EV
improved `+0.1599` and PnL improved `+$3,346.57`, with all three windows
EV-positive and no EV-regressed window (`late_strong +0.0182`,
`mid_weak +0.0992`, `old_thin +0.0425`). The rule adjusted 7 paper trades
across all 3 windows, worsened max drawdown by only `0.14pp`, and kept
single-ticker positive-share concentration inside the `50%` guardrail
(`41.52% -> 42.91%`). The rule lives in shared `state_surface_sleeve.py`, is
surfaced by the production default-off paper path, and has focused parity
tests; live/default orders remain disabled.

Previous accepted state-surface paper ret5 follow-through result:
`exp-20260519-023` keeps the accepted `exp-20260519-021` stack fixed and adds
one production-visible top-3 positive 5-day return paper support scalar. When a
same-day qualified state-surface queue candidate is ranked 1 through 3 and has
its own `features.ret5 > 0.0`, only that candidate's default-off paper notional
is scaled by `1.25x` after the active profile, near-high, and volume scalars.
Versus the accepted rank-2 volume baseline, aggregate paper-overlay EV improved
`+0.7211` and PnL improved `+$14,108.30`, with all three windows EV-positive
and no EV-regressed window (`late_strong +0.2314`, `mid_weak +0.3282`,
`old_thin +0.1615`). The rule adjusted 18 paper trades across all 3 windows,
worsened max drawdown by at most `0.44pp`, inside the `0.50pp` Gate 4 guardrail,
and kept single-ticker positive-share concentration inside the `50%` guardrail
(`42.91% -> 40.43%`). The rule lives in shared `state_surface_sleeve.py`, is
surfaced by the production default-off paper path, and has focused parity tests;
live/default orders remain disabled.

Latest accepted state-surface paper market-breadth support result:
`exp-20260519-024` keeps the accepted `exp-20260519-023` stack fixed and adds
one production-visible market-state paper support scalar. When an already
selected same-day qualified state-surface candidate has `breadth_bucket ==
broad_breadth`, that candidate's default-off paper notional is scaled by
`1.10x` after the active profile, near-high, volume, and top-3 ret5 scalars.
Versus the accepted top-3 ret5 baseline, aggregate paper-overlay EV improved
`+0.3571` and PnL improved `+$6,920.20`, with no EV-regressed window
(`late_strong unchanged`, `mid_weak +0.2698`, `old_thin +0.0873`). The rule
adjusted 15 paper trades across 2 windows, worsened max drawdown by at most
`0.21pp`, inside the `0.50pp` Gate 4 guardrail, and kept single-ticker
positive-share concentration inside the `50%` guardrail (`40.43% -> 41.30%`).
The rule lives in shared `state_surface_sleeve.py`, is surfaced by the
production default-off paper path, and has focused parity tests; live/default
orders remain disabled.

Previous accepted state-surface paper sleeve-capacity result:
`exp-20260519-027` keeps the accepted `exp-20260519-026` rank/queue alignment
stack fixed and adds one production-visible default-off paper capacity scalar.
All already selected state-surface paper candidates receive `1.15x` notional
support after the accepted rank-notional profile stack. Versus the accepted
rank/queue alignment baseline, aggregate paper-overlay EV improved `+0.8724`
and PnL improved `+$16,211.14`, with no EV-regressed window: `late_strong +0.2005`,
`mid_weak +0.5234`, and `old_thin +0.1485`. The rule adjusted 24 paper
trades across all 3 windows, worsened max drawdown by at most `0.41pp`, inside
the `0.50pp` Gate 4 guardrail, and kept single-ticker positive-share
concentration inside the `50%` guardrail (`41.74% -> 41.74%`). The rule lives
in shared `state_surface_sleeve.py`, is surfaced by the production default-off
paper path, and has focused parity tests; live/default orders remain disabled.

Latest accepted state-surface paper queue-lag support result:
`exp-20260519-028` keeps the accepted `exp-20260519-027` sleeve-capacity stack
fixed and adds one production-visible selected-trade displacement support
scalar. When an already-selected state-surface paper candidate has
`rank > queue_rank`, the shared default-off paper path multiplies that
candidate's active paper notional by `1.25`. Versus the accepted
sleeve-capacity baseline, aggregate paper-overlay EV improved `+0.3875` and
PnL improved `+$6,716.53`, with no EV-regressed window: `late_strong +0.1699`,
`mid_weak +0.2176`, and `old_thin unchanged`. The rule adjusted 10 paper
trades across 2 windows, did not worsen max drawdown, and kept single-ticker
positive-share concentration inside the `50%` guardrail (`41.74% -> 41.03%`).
The rule lives in shared `state_surface_sleeve.py`, is surfaced by the
production default-off paper path, and has focused parity tests; live/default
orders remain disabled.

Latest accepted state-surface paper absolute-score support result:
`exp-20260519-031` keeps the accepted `exp-20260519-028` queue-lag stack
fixed and adds one production-visible absolute composite score support scalar.
When an already-selected state-surface paper candidate has `score >= 0.90`,
the shared default-off paper path multiplies that candidate's active paper
notional by `1.15` after the queue-lag stack. Versus the accepted queue-lag
baseline, aggregate paper-overlay EV improved `+0.6845` and PnL improved
`+$14,516.94`, with all three windows EV-positive and no EV-regressed window:
`late_strong +0.1422`, `mid_weak +0.3713`, and `old_thin +0.1710`. The rule
adjusted 16 paper trades across all 3 windows, worsened max drawdown by at
most `0.46pp`, inside the `0.50pp` Gate 4 guardrail, and kept single-ticker
positive-share concentration inside the `50%` guardrail (`41.03% -> 42.36%`).
The rule lives in shared `state_surface_sleeve.py`, is surfaced by the
production default-off paper path, and has focused parity tests; live/default
orders remain disabled.

Latest accepted state-surface paper rank-depth score-volume support result:
`exp-20260519-033` keeps the accepted `exp-20260519-031` absolute-score stack
fixed and adds one production-visible rank-depth score-volume support scalar.
When an already-selected state-surface paper candidate has `queue_rank` 2-3,
`score >= 0.90`, and `features.volume_ratio_20 >= 1.10`, the shared
default-off paper path multiplies that candidate's active paper notional by
`1.075` after the absolute-score stack. Versus the accepted absolute-score
baseline, aggregate paper-overlay EV improved `+0.1602` and PnL improved
`+$4,363.51`, with all three windows EV-positive and no EV-regressed window:
`late_strong +0.0127`, `mid_weak +0.0850`, and `old_thin +0.0625`. The rule
adjusted 7 paper trades across all 3 windows, worsened max drawdown by at most
`0.47pp`, inside the `0.50pp` Gate 4 guardrail, and kept single-ticker
positive-share concentration inside the `50%` guardrail (`42.36% -> 43.67%`).
The rule lives in shared `state_surface_sleeve.py`, is surfaced by the
production default-off paper path, and has focused parity tests; live/default
orders remain disabled.

Latest accepted state-surface paper low-extension support result:
`exp-20260520-001` keeps the accepted `exp-20260519-033` rank-depth
score-volume stack fixed and adds one production-visible short-term extension
support scalar. When an already-selected state-surface paper candidate has
`features.ret5 <= 0.02`, the shared default-off paper path multiplies that
candidate's active paper notional by `1.05` after the rank-depth score-volume
stack. Versus the accepted rank-depth score-volume baseline, aggregate
paper-overlay EV improved `+0.2368` and PnL improved `+$4,925.64`, with all
three windows EV/PnL-positive and no regression: `late_strong +0.0077` EV /
`+$161.85`, `mid_weak +0.1873` EV / `+$2,863.53`, and `old_thin +0.0418` EV /
`+$1,900.26`. The rule adjusted 9 paper trades across all 3 windows, worsened
max drawdown by at most `0.38pp`, inside the `0.50pp` Gate 4 guardrail, and
kept single-ticker positive-share concentration inside the `50%` guardrail
(`43.67% -> 44.49%`). The rule lives in shared `state_surface_sleeve.py`, is
surfaced by the production default-off paper path, and has focused parity
tests; live/default orders remain disabled.

Rejected state-surface paper trend-stability support result:
`exp-20260520-006` retested the accepted `exp-20260520-001` low-extension stack
under the stricter state-surface scalar Gate 4 rule. The historical
`features.ret20_excess_spy - features.ret60 / 3 <= 0.06` / `1.15x` candidate
improved aggregate EV by only `+3.487%` (`+0.5528` EV; `+$10,140.40`) across
the three fixed windows. That is below the required `>10%` aggregate EV uplift
for state-surface threshold/profile/notional-scalar tuning, so the scalar is
rejected despite positive window-level PnL. The production-visible shared
`state_surface_sleeve.py` path does not retain this trend-stability scalar.
Nearby trend-stability threshold/scalar retries need a broader sample, a
distinct production-visible quality/risk field, or strict `>10%` aggregate EV
evidence.

Latest accepted broad-market candidate-pool paper result:
`exp-20260519-036` keeps core metrics unchanged and promotes the fixed
`exp-20260519-035` `price_floor_40` broad-market leadership candidate
definition into a shared default-off paper adapter. Historical replay uses the
same shared `broad_market_paper_sleeve.py` feature/filter logic that production
now calls from `run.py`; live/default orders remain disabled. Versus the
accepted stack, aggregate paper-overlay EV improved `+0.7208` and PnL improved
`+$18,639.46`, with all three canonical windows EV-positive and no EV/PnL
regression: `late_strong +0.0121` EV / `+$4,795.64`, `mid_weak +0.6659` EV /
`+$11,047.61`, and `old_thin +0.0428` EV / `+$2,796.21`. The sleeve selected
90 paper trades across all three windows, max drawdown drift was `+0.23pp`,
single-ticker positive share was `11.16%`, top-five positive share was
`39.42%`, and shared-adapter parity versus the parent scout matched EV, PnL,
and trade count exactly. Treat this as paper candidate-pool alpha, not core
universe expansion.

Latest accepted broad-market paper rank-notional result:
`exp-20260519-037` keeps the accepted `exp-20260519-036` candidate definition,
price floor, hold, slot, and universe controls fixed, but changes the shared
default-off paper notional profile from flat `$7,500` to rank multipliers
`[1.20, 1.00, 0.80]` on the same selected candidates. Versus the accepted
flat-notional broad-market adapter, aggregate paper-overlay EV improved
`+0.2189` and PnL improved `+$3,876.84`, with all three canonical windows
EV/PnL-positive and no regression: `late_strong +0.1393` EV / `+$2,334.94`,
`mid_weak +0.0733` EV / `+$1,255.54`, and `old_thin +0.0063` EV /
`+$286.36`. The sleeve still selected 90 paper trades across all three
windows, max drawdown drift was `+0.15pp`, single-ticker positive share was
`12.24%`, and top-five positive share was `42.63%`. The rule lives in shared
`broad_market_paper_sleeve.py`, is surfaced by the production default-off
paper path, and has focused parity tests; live/default orders remain disabled.

Latest accepted broad-market paper low-extension result:
`exp-20260520-002` keeps the accepted `exp-20260519-037` candidate definition,
price floor, rank-notional profile, hold, slot, and universe controls fixed,
but adds one production-visible short-term extension support field. When an
already-selected broad-market paper candidate has `ret5 <= 0.02`, the shared
default-off paper path multiplies that candidate's active paper notional by
`1.15` after the accepted `[1.20, 1.00, 0.80]` rank profile. Versus the
accepted broad-market rank-notional baseline, aggregate paper-overlay EV
improved `+0.0545` and PnL improved `+$792.70`, with all three canonical
windows EV/PnL-positive and no regression: `late_strong +0.0170` EV /
`+$28.58`, `mid_weak +0.0218` EV / `+$474.74`, and `old_thin +0.0157` EV /
`+$289.38`. The rule adjusted 12 paper trades across all three windows, did
not worsen max drawdown, kept single-ticker positive share at `12.02%`, and
kept top-five positive share at `41.88%`. The rule lives in shared
`broad_market_paper_sleeve.py`, is surfaced by the production default-off
paper path, and has focused parity tests; live/default orders remain disabled.

Latest accepted broad-market paper high-volatility result:
`exp-20260520-003` keeps the accepted `exp-20260520-002` broad-market stack
fixed, but adds one production-visible realized-volatility support field. When
an already-selected broad-market paper candidate has 20-day realized volatility
of at least `0.055`, the shared default-off paper path multiplies that
candidate's active paper notional by `1.15` after the accepted rank-notional
and low-extension stack. Versus the accepted low-extension baseline, aggregate
paper-overlay EV improved `+0.1097` and PnL improved `+$2,164.26`, with all
three canonical windows EV/PnL-positive and no regression: `late_strong
+0.0516` EV / `+$1,109.90`, `mid_weak +0.0525` EV / `+$798.82`, and
`old_thin +0.0056` EV / `+$255.54`. The selected variant adjusted 9 paper
trades across all three windows; the raw `0.060` threshold had higher EV but
only touched the exact minimum 8 trades, so the accepted variant favors the
less fragile 9-trade support slice. Max drawdown worsened by at most `0.01pp`,
single-ticker positive share stayed at `13.25%`, and top-five positive share
stayed at `43.28%`. The rule lives in shared
`broad_market_paper_sleeve.py`, is surfaced by the production default-off
paper path, and has focused parity tests; live/default orders remain disabled.

Latest accepted broad-market paper trend-persistence result:
`exp-20260520-004` keeps the accepted `exp-20260520-003` broad-market stack
fixed, but adds one production-visible trend-persistence support field. When
an already-selected broad-market paper candidate has
`positive_day_ratio_20 >= 0.55`, the shared default-off paper path multiplies
that candidate's active paper notional by `1.15` after the accepted
rank-notional, low-extension, and high-volatility stack. Versus the accepted
high-volatility baseline, aggregate paper-overlay EV improved `+0.1197` and
PnL improved `+$3,502.29`, with all three canonical windows EV/PnL-positive
and no regression: `late_strong +0.0788` EV / `+$2,038.69`,
`mid_weak +0.0315` EV / `+$1,031.18`, and `old_thin +0.0094` EV /
`+$432.42`. The rule adjusted 79 paper trades across all three windows, max
drawdown worsened by at most `0.05pp`, single-ticker positive share stayed at
`13.52%`, and top-five positive share stayed at `42.72%`. The rule lives in
shared `broad_market_paper_sleeve.py`, is surfaced by the production
default-off paper path, and has focused parity tests; live/default orders
remain disabled.

Latest accepted broad-market measurement repair: `exp-20260524-008` changes no
canonical core backtest metric and does not alter the broad-market paper
profile, thresholds, notional scalars, hold period, slots, or trade-enabled
state. It only lets `run.py` use a conservative
`broad_market_universe_state_observation_feed_v1` fallback from daily
`universe_state` observation records when the static
`data/state/broad_market_paper/universe.json` feed is missing. This is
accepted as feed/forward-evidence repair, not as strategy alpha; future
broad-market activation still requires closed replacement-value outcomes and a
separate Gate 1-4 promotion.

Latest accepted default-off SEC paper result: `exp-20260519-008` keeps core
metrics unchanged and keeps the accepted financial-report T+1 paper queue,
10-trading-day hold, max position count, periodic-report scalars, accepted
neutral-underreaction rule, and accepted neutral-underreaction SPY T+1 context
rule fixed, but adds a production-visible earnings-release SPY T+1 context
paper-notional scalar. Covered `earnings_release_text` rows whose
`spy_t1_return` is at least `-0.5%` receive an additional `1.10x` default-off
paper-notional scalar. Versus the accepted `exp-20260518-014` SEC paper stack,
aggregate paper-overlay EV improved `+0.1885` and PnL improved `+$5,461.48`,
with all three fixed windows EV-positive (`late_strong +0.0011`,
`mid_weak +0.1126`, `old_thin +0.0748`) and no EV regression. The adjusted
sample is 29 closed paper trades across all windows, max drawdown worsened by
only `0.138pp`, and max single-ticker positive incremental PnL share stayed
inside the `65%` guardrail at `51.17%`; live/default orders remain disabled.

Latest accepted core-sizing result: core `exp-20260517-009` keeps entries,
exits, filters, universe, targets, heat, LLM, news, and pre-slot ranking
unchanged, but applies a shared cap-aware `1.05x` post-sizing top-up to the
already selected rank-1 stock signal when entry planning has at least four
available slots. ETF and Commodity sectors are excluded because broad
ample-slot promotion regressed `old_thin` through Commodity exposure in
`exp-20260517-008`. The sweep (`1.0125x`, `1.025x`, `1.05x`) improved
aggregate EV by `+0.0356` and aggregate PnL by `+$1,232.90`: `late_strong`
improved EV `+0.0267` / PnL `+$345.66`, `mid_weak` improved EV `+0.0089` /
PnL `+$887.24`, and `old_thin` stayed unchanged. Trade count, survival, worst
trade, loss streak, and `old_thin` drawdown did not worsen; `mid_weak` max
drawdown rose from `10.83%` to `11.19%` while staying within the Gate 4
guardrail. The rule lives in shared `production_parity.py`, used by both
`backtester.py` and `run.py`; focused parity tests cover the stock top-up and
Commodity exclusion.

Previous accepted core-sizing result: core `exp-20260517-004` keeps entries,
exits, filters, universe, targets, heat, LLM, news, and pre-slot ranking
unchanged, but applies a shared cap-aware `1.075x` post-sizing top-up to the
already selected rank-1 core signal only when entry planning has exactly one
remaining slot. The sweep (`1.025x`, `1.05x`, `1.075x`) improved aggregate EV
by `+0.0237` and aggregate PnL by `+$609.87`.

Previous accepted core-sizing result: core `exp-20260516-042` keeps entries,
exits, ranking, universe, filters, targets, heat, slots, LLM, and news logic
unchanged, but applies an ISRG-specific post-sizing core long scalar of `0.25x`
in shared `portfolio_engine.py` constants. The accepted non-control sweep value
improved the current stack by aggregate EV `+0.0512` and aggregate PnL
`+$1,857.98`: `late_strong` stayed unchanged, `mid_weak` improved EV `+0.0019`
/ PnL `+$70.72`, and `old_thin` improved EV `+0.0493` / PnL `+$1,787.26`.
The affected sample was two ISRG core long signals across `mid_weak` and
`old_thin`, trade count stayed `61`, minimum survival stayed `79.25%`, and max
drawdown did not worsen. The lifecycle diagnostic did not support a fast-target
rescue. The `0.0x` quarantine failed by regressing `old_thin`, so do not
generalize this into a Healthcare rule or retry nearby ISRG scalar/target
changes without new forward evidence.

Previous accepted core-sizing result: core `exp-20260516-039` keeps entries,
exits, ranking, universe, filters, targets, heat, slots, LLM, and news logic
unchanged, but applies a TSM-specific post-sizing core long scalar of `0.25x`
in shared `portfolio_engine.py` constants. The accepted non-control sweep value
improved the current stack by aggregate EV `+0.0143` and aggregate PnL
`+$607.71`: `late_strong` improved EV `+0.0017` / PnL `+$40.86`,
`mid_weak` improved EV `+0.0011` / PnL `+$31.40`, and `old_thin` improved EV
`+0.0115` / PnL `+$535.45`. The affected sample was four TSM core long signals
across all three windows, trade count moved `62 -> 61`, minimum survival stayed
`79.25%`, and max drawdown drift was only `+0.01 pp`. The lifecycle diagnostic
did not support a fast-target rescue: no TSM trade had close-to-close profit
available before stop, and the 1/3/5-day net holding windows were all negative.
The `0.0x` quarantine failed by regressing `old_thin` and aggregate PnL, so do
not generalize this into a semiconductor rule or retry nearby TSM scalar/target
changes without new forward evidence.

Latest promising replay-only default-off event allocation result:
`exp-20260517-010` keeps the canonical core baseline unchanged but revalidates
the event bundle's `rotation_breakout_leadership` paper allocation after the
accepted core `exp-20260517-009` stock-only ample-slot top-up. The best variant
remains `3.0x` paper notional for rotation-surface rows versus the current
`2.0x` non-generic positive event paper lead. Aggregate paper-overlay EV
improved `+0.5389` and aggregate PnL improved `+$7,987.90`, with all three
fixed windows EV-positive (`late_strong +0.3138`, `mid_weak +0.2171`,
`old_thin +0.0080`) and no EV regression. This is not a live/default order
change; promotion still requires a shared trade-enabled adapter,
run/backtester parity tests, and closed forward replacement-value evidence.

Latest accepted default-off event adapter refinement: `exp-20260521-001` keeps
the accepted `exp-20260520-044` front-rank event adapter fixed, but adds one
production-visible broad-breadth event quality scalar. When an eligible
default-off event paper row has `breadth_bucket == broad_breadth`, the shared
event adapter multiplies its already active paper notional by `1.25x`. Versus
the accepted front-rank adapter baseline, aggregate paper-overlay EV improved
`+0.3383` and PnL improved `+$5,550.72`, with all three canonical windows
EV/PnL-positive and no regression: `late_strong +0.0060` EV / `+$124.60`,
`mid_weak +0.3198` EV / `+$4,908.89`, and `old_thin +0.0125` EV / `+$517.23`.
The rule adjusted 15 paper trades across all three windows, max single positive
target contribution was `38.82%`, lives in shared `event_sleeve_bundle.py`, and
is surfaced by production reporting while live/default orders remain disabled.

Latest accepted default-off event source-quality refinement:
`exp-20260521-006` keeps the accepted event broad-breadth/front-rank adapter
fixed, but adds the production-visible `sec_governance_procedural` source
quality scalar from the positive `exp-20260521-005` scout. When a default-off
event paper row has `source == sec_governance_procedural`, the shared event
adapter multiplies its already active paper notional by `2.0x`; this stacks
after existing rotation, front-rank rotation, and broad-breadth paper tilts.
Versus the accepted `exp-20260521-001` broad-breadth baseline, aggregate
paper-overlay EV improved `+0.8812` and PnL improved `+$14,372.88`, with all
three canonical windows EV/PnL-positive and no EV regression:
`late_strong +0.0751` EV / `+$1,266.72`, `mid_weak +0.7078` EV / `+$9,564.38`, and
`old_thin +0.0983` EV / `+$3,541.78`. The rule adjusted 13 target paper trades
across all three windows and 9 tickers, max single positive target contribution
was `27.49%`, lives in shared `event_sleeve_bundle.py`, is surfaced by
production reporting, and keeps live/default orders disabled.

Previous accepted core-sizing result: core `exp-20260516-020` keeps entries,
exits, ranking, universe, filters, targets, heat, slots, LLM, and news logic
unchanged, but reduces the existing `trend_long` Technology 44-64 DTE risk
multiplier from `0.25x` to `0.125x` in shared `portfolio_engine.py` constants.

Previous accepted core-sizing result: core `exp-20260516-009` keeps entries,
exits, ranking, universe, filters, targets, heat, slots, LLM, and news logic
unchanged, but tags already-qualified `trend_long` / `breakout_long` signals
whose own signal-day candle is green, `momentum_10d_pct` and `momentum_20d_pct`
are both positive, `momentum_10d_pct < momentum_20d_pct`,
`trade_quality_score >= 0.95`, and sector is not Consumer Discretionary or
Communication Services. Those signals get an additional 1.025x cap-aware
post-sizing top-up in shared `risk_engine.py` and `portfolio_engine.py`. The
change improved EV/PnL in `late_strong` and `mid_weak` and left `old_thin`
unchanged: aggregate EV `+0.0309`, aggregate PnL `+$754.19`, trade count stayed
`62`, minimum survival stayed `79.25%`, and worst-window max drawdown drift
stayed inside Gate 4 at `+0.20 pp`. There is no production/backtest split
because both adapters call the same shared risk/sizing modules; the backtester
only adds attribution for the applied multiplier. 1.05x+ variants regressed
`old_thin`, and 1.075x failed drawdown, so do not retry nearby
green-deceleration scalars on these frozen windows without forward evidence or
a materially different production-visible discriminator.

Previous accepted core-sizing result: core `exp-20260515-028` keeps entries,
exits, ranking, universe, filters, targets, heat, slots, LLM, and news logic
unchanged, but gives already-qualified `trend_long` / `breakout_long` signals
with `trade_quality_score >= 0.95`, `rs20_entry_state_leader=true`, and
`signal_day_ticker_green_candle=true` an additional 1.075x cap-aware
post-sizing top-up in shared `risk_engine.py` and `portfolio_engine.py`. The
change improved EV/PnL in all three canonical windows: aggregate EV `+0.0866`,
aggregate PnL `+$2,604.84`, trade count stayed `62`, minimum survival stayed
`79.25%`, and worst-window max drawdown drift stayed inside Gate 4 at
`+0.49 pp`. `old_thin` survival moved from `90.00%` to `86.67%`
(`signals_survived -2` versus the accepted stack), so the accepted
interpretation is a targeted allocation top-up, not a survival improvement.
There is no production/backtest split because both adapters call the same
shared risk/sizing modules; the backtester only adds attribution for the
applied multiplier. 1.08x+ variants failed the drawdown guardrail, so do not
retry nearby confirmed-quality scalars without forward evidence or a materially
different production-visible discriminator.

Previous accepted core-sizing result: core `exp-20260515-026` keeps entries,
exits, ranking, universe, filters, targets, heat, slots, LLM, and news logic
unchanged, but gives already-qualified `trend_long` non-ETF/non-commodity
stock signals with `price_vs_200ma_extension_state=true` an additional 1.125x
cap-aware post-sizing top-up after the existing broad extension top-up in
shared `portfolio_engine.py`. The change improved EV/PnL in `mid_weak` and
`old_thin`, left `late_strong` unchanged, and produced no regressed windows:
aggregate EV `+0.0943`, aggregate PnL `+$3,086.63`, trade count stayed `62`,
minimum survival stayed `79.25%`, and worst-window max drawdown drift stayed
inside Gate 4 at `+0.47 pp`. `old_thin` survival moved from `91.67%` to
`90.00%` (`signals_survived -1`), so the accepted interpretation is a
conservative allocation top-up, not a survival improvement. There is no
production/backtest split because both adapters call the same shared sizing
module; the backtester only adds attribution for the applied multiplier. 1.15x+
variants failed the drawdown guardrail, so do not retry nearby trend-only
price-vs-200MA extension scalars without forward evidence or a materially
different production-visible discriminator.

Previous accepted core-sizing result: core `exp-20260515-018` keeps entries,
exits, ranking, universe, filters, targets, heat, slots, LLM, and news logic
unchanged, but tags already-qualified `trend_long` / `breakout_long`
non-ETF/non-commodity stock signals whose `price_vs_200ma_pct` is in the
same-day top quartile and applies a 1.025x cap-aware post-sizing top-up in
shared `risk_engine.py` and `portfolio_engine.py`. The change improved EV and
PnL in all three canonical windows and kept trade count and survival unchanged:
aggregate EV `+0.0208`, aggregate PnL `+$882.67`, max drawdown drift stayed
inside Gate 4 at `+0.10 pp`, and there is no production/backtest split because
both adapters call the same shared risk/sizing modules. Only 15 signals
adjusted, and 1.05x+ variants regressed `late_strong` or drawdown, so do not
retry nearby broad price-vs-200MA extension scalars on these frozen windows
without forward evidence or a materially different production-visible
discriminator.

Previous accepted core-sizing result: core `exp-20260515-013` keeps entries,
exits, ranking, universe, raw clean-SPY and RS20 multipliers, heat, slots, and
LLM/news logic unchanged, but lets only already-qualified clean-SPY cap-only
leaders with `rs20_entry_state_leader=true` use a 70% single-position cap in
shared `portfolio_engine.py`. The change improved EV and PnL in all three
canonical windows and kept trade count and survival unchanged: aggregate EV
`+0.3865`, aggregate PnL `+$8,878.68`, max drawdown drift stayed inside Gate 4
at `+0.30 pp`, and there is no production/backtest split because both adapters
call the same shared sizing module. Only 10 signals adjusted, so do not retry
nearby clean-SPY cap-only RS20 cap values on these frozen windows without
forward cap-room attribution or a materially different production-visible
discriminator.

Previous accepted core-sizing result: core `exp-20260515-008` keeps entries,
exits, ranking, universe, raw clean-SPY multipliers, heat, slots, and LLM/news
logic unchanged, but lets clean-SPY cap-only leaders use a 60%
single-position cap in shared `portfolio_engine.py`. The change improved EV
and PnL in all three canonical windows and kept trade count and survival
unchanged: aggregate EV `+0.1809`, aggregate PnL `+$4,488.22`, and max
drawdown drift stayed inside Gate 4 at `+0.22 pp`.

Previous accepted core-sizing result: core `exp-20260514-050` keeps entries,
exits, ranking, universe, raw Commodity multipliers, heat, slots, and LLM/news
logic unchanged, but lets only already-qualified `trend_long` GLD/IAU
Commodity near-high signals use a 57.5% single-position cap in shared
`portfolio_engine.py`. The change improved EV and PnL in all three canonical
windows and kept trade count and survival unchanged: aggregate EV `+0.0380`,
aggregate PnL `+$1,472.29`, max drawdown drift stayed inside Gate 4 at
`+0.09 pp`.

Previous accepted core-sizing result: core `exp-20260514-049` keeps entries,
exits, ranking, universe, raw Commodity multipliers, heat, slots, and LLM/news
logic unchanged, but lets only `breakout_long + Commodities` use a 57.5%
single-position cap in shared `portfolio_engine.py`. The change improved EV
and PnL in `late_strong` and `mid_weak`, left `old_thin` unchanged, and kept
trade count and survival unchanged: aggregate EV `+0.1092`, aggregate PnL
`+$2,119.18`, max drawdown did not worsen, and there is no
production/backtest split because both adapters call the same shared sizing
module. Only 5 signals adjusted, so do not retry nearby Commodity breakout cap
values on these frozen windows without forward cap-room attribution or a
materially different production-visible discriminator.

Previous accepted core-sizing result: core `exp-20260514-030` keeps entries,
exits, ranking, universe, raw Financials multipliers, heat, slots, and
LLM/news logic unchanged, but lets only `trend_long + Financials +
financials_sector_leader=true + mid_sector_dispersion=true` use a 55%
single-position cap in shared `portfolio_engine.py`. The change improved EV
and PnL in `mid_weak` and `old_thin`, left `late_strong` unchanged, and kept
trade count and survival unchanged: aggregate EV `+0.0123`, aggregate PnL
`+$618.16`, max drawdown drift stayed inside the Gate 4 guardrail at
`+0.13 pp` worst window, and there is no production/backtest split because
both adapters call the same shared sizing module. Only 3 signals adjusted, so
do not retry nearby Financials cap values on these frozen windows without
forward cap-room attribution or a materially different production-visible
discriminator.

Previous accepted core-sizing result: `exp-20260514-027` keeps the existing
clean SPY-relative leader signal-day 1.10x top-up unchanged but lets only that
already-accepted confirmation sleeve use a 52.5% single-position cap in shared
`portfolio_engine.py`. The change improved EV and PnL in all three fixed
windows with unchanged trade count and survival: aggregate EV `+0.0719`,
aggregate PnL `+$1,897.40`, max drawdown drift stayed inside the Gate 4
guardrail at `+0.11 pp` worst window, and there is no production/backtest
split because both adapters call the same shared sizing module. Do not retry
nearby clean-SPY signal-day cap values or the adjacent 1.10x scalar on these
frozen windows without forward cap-room attribution or a materially different
production-visible discriminator.

Previous accepted core-sizing result: `exp-20260514-023` keeps the existing
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

Latest accepted default-off Space replay result: `exp-20260519-027` promotes
the shared Space metadata/helper
`space_source_diversity_dual_catalyst_benchmark_breadth_trend_risk_scalar` from
`1.0125` to `1.021875` on top of accepted `exp-20260516-029`, for the same
source-diverse official Space `trend_long` signals whose event profile contains
both `customer_win` and `government_space_contract` and whose closed
event-state replacement rows are cash-, SPY-, QQQ-, UFO-, and ARKX-positive.
It uses the same three window labels above with frozen Space snapshots and
keeps live Space slots at zero. Versus the accepted `1.0125` baseline,
aggregate default-off Space EV improved `+0.0630` and PnL improved
`+$3,212.78`; window EV deltas were `late_strong +0.0271`, `mid_weak
+0.0359`, and `old_thin` unchanged. Aggregate max drawdown ceiling drift was
`+0.21 pp` versus current and `+0.48 pp` versus the original `1.0` anchor,
trade count stayed `63`, minimum survival stayed `62.67%`, and the changed
slice remained 4 LUNR/RKLB dual-catalyst benchmark-breadth trend signals. The
nearby `1.025` variant is rejected on these frozen windows because original
anchor drawdown drift reached `+0.53 pp`; do not retry nearby
dual-catalyst benchmark-breadth Space scalars without new closed forward rows
or a materially different production-visible replacement-quality field.

Previous accepted default-off Space replay result: `exp-20260516-029` added
the same helper at `1.0125` on top of accepted `exp-20260516-024`. Aggregate
default-off Space EV improved `+0.1868` and PnL improved `+$5,124.39`; window
EV deltas were `late_strong +0.0476`, `mid_weak +0.1392`, and `old_thin`
unchanged, with aggregate max drawdown ceiling drift `+0.27 pp`.

Previous accepted default-off Space replay result: `exp-20260516-024` adds only
the shared Space metadata/helper
`space_source_diversity_dual_catalyst_financing_profile_trend_risk_scalar=1.0125`
on top of accepted `exp-20260516-023`, for source-diverse official Space
`trend_long` signals whose event profile contains both `customer_win` and
`government_space_contract` and whose production registry `event_guard_profile`
is financing/dilution sensitive. It uses the same three window labels above
with frozen Space snapshots and keeps live Space slots at zero. Aggregate
default-off Space EV improved `+0.2847` and PnL improved `+$8,154.32`; window
EV deltas were `late_strong +0.0413`, `mid_weak +0.2434`, and `old_thin`
unchanged. Aggregate max drawdown ceiling drift was `+0.25 pp`, trade count
stayed `64`, minimum survival stayed `62.67%`, and the changed slice was
ASTS/RKLB dual-catalyst financing-profile trend evidence across 5 signals.
Stronger nearby `1.025x`/`1.05x` variants had higher raw EV but failed the
drawdown guardrail, so do not retry stronger nearby dual-catalyst
financing-profile Space scalars on these frozen windows without new closed
forward rows or a materially different production-visible catalyst-quality
field.

Previous accepted default-off Space replay result: `exp-20260516-023` adds only
the shared Space metadata/helper
`space_source_diversity_dual_catalyst_near_perfect_trend_risk_scalar=1.0125`
on top of accepted `exp-20260516-019`, for source-diverse official Space
`trend_long` signals whose event profile contains both `customer_win` and
`government_space_contract` and whose TQS is near-perfect but not perfect
(`0.95 <= TQS < 1.0`). It uses the same three window labels above with frozen
Space snapshots and keeps live Space slots at zero. Aggregate default-off Space
EV improved `+0.0809` and PnL improved `+$1,777.65`; window EV deltas were
`late_strong +0.0345`, `mid_weak +0.0464`, and `old_thin` unchanged. Aggregate
max drawdown ceiling drift was `+0.26 pp`, trade count stayed `64`, minimum
survival stayed `62.67%`, and the changed slice was ASTS/LUNR/RKLB
dual-catalyst near-perfect trend evidence across 4 signals. Do not retry
stronger nearby dual-catalyst near-perfect Space scalars on these frozen
windows without new closed forward rows or a materially different
production-visible catalyst-quality field.

Previous accepted default-off Space replay result: `exp-20260516-019` adds only
the shared Space metadata/helper
`space_source_diversity_dual_catalyst_same_theme_winner_trend_risk_scalar=1.0125`
on top of accepted `exp-20260516-015`, for source-diverse official Space
`trend_long` signals whose event profile contains both `customer_win` and
`government_space_contract` and whose closed defense-budget
`government_space_contract` rows are cash- and same-theme
replacement-positive. It uses the same three window labels above with frozen
Space snapshots and keeps live Space slots at zero. Aggregate default-off Space
EV improved `+0.1421` and PnL improved `+$4,954.90`; window EV deltas were
`late_strong +0.0399`, `mid_weak +0.1022`, and `old_thin` unchanged. Aggregate
max drawdown ceiling drift was `+0.26 pp`, trade count stayed `64`, minimum
survival stayed `62.67%`, and the changed slice was LUNR/RKLB dual-catalyst
same-theme-winner trend evidence across 4 signals. Do not retry stronger
nearby same-theme-winner Space scalars on these frozen windows without new
closed forward rows or a materially different production-visible
catalyst-quality field.

Latest rejected default-off Space peer-state alpha search: `exp-20260516-017`
and `exp-20260516-018` tested dual-catalyst peer-leader and peer-nonleader
scalars on top of accepted `exp-20260516-015`. After preserving the accepted
IWM-leader helper in the true baseline, neither candidate produced incremental
EV or PnL across the same three frozen Space replay windows. `exp-20260516-017`
selected the identity scalar (`1.0`) with aggregate EV/PnL delta `0.0`; the
non-identity peer-leader variants stayed sample-thin. `exp-20260516-018`
selected `0.95` for four ASTS/RKLB signals across two windows, but aggregate
EV/PnL delta was still `0.0`. No shared helper was promoted. Do not retry
nearby dual-catalyst peer-state Space scalars on these frozen windows without
new closed forward rows or a materially different production-visible
catalyst-quality field.

Previous accepted default-off Space replay result: `exp-20260516-015` adds only
the shared Space metadata/helper
`space_source_diversity_dual_catalyst_iwm_leader_trend_risk_scalar=1.0125` on
top of accepted `exp-20260516-014`, for official Space `trend_long` signals
whose source-diverse profile has both `customer_win` and
`government_space_contract` while IWM 20d momentum is above SPY 20d momentum.
It uses the same three window labels above with frozen Space snapshots and
keeps live Space slots at zero. Aggregate default-off Space EV improved
`+0.2377` and PnL improved `+$6,670.29`; window EV deltas were
`late_strong +0.0125`, `mid_weak +0.2252`, and `old_thin` unchanged. Aggregate
max drawdown ceiling drift was `+0.25 pp`, trade count stayed `64`, and
minimum survival stayed `62.67%`. The changed slice was ASTS/LUNR/RKLB
dual-catalyst trend evidence with small-cap risk appetite confirmed (5 adjusted
signals), so do not retry nearby dual-catalyst IWM-leader Space scalars on these
frozen windows without new closed forward rows or a materially different
production-visible catalyst-quality field.

Previous accepted default-off Space replay result: `exp-20260516-014` adds only
the shared Space metadata/helper
`space_source_diversity_dual_catalyst_trend_risk_scalar=1.025` on top of the
accepted `exp-20260515-044` source-diversity / peer-nonleader / near-perfect
stack, for official Space `trend_long` signals whose source-diverse profile has
both `customer_win` and `government_space_contract`. It uses the same three
window labels above with frozen Space snapshots and keeps live Space slots at
zero. Aggregate default-off Space EV improved `+0.5574` and PnL improved
`+$14,086.09`; window EV deltas were `late_strong +0.0804`,
`mid_weak +0.4770`, and `old_thin` unchanged. Aggregate max drawdown ceiling drift was
`+0.50 pp`, trade count stayed `64`, and minimum survival stayed `62.67%`. The
changed slice was dual-catalyst source-diversity trend evidence (`ASTS`,
`LUNR`, and `RKLB`, 6 adjusted signals), so do not retry nearby
dual-catalyst Space scalars on these frozen windows without new closed forward
rows or a materially different production-visible catalyst-quality field.

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

## Diagnostic / Oracle Analysis

Diagnostic analyses are allowed and encouraged, but they are not acceptance
evidence by themselves. They answer "where is the opportunity gap?" and "what
production-visible field might explain it?" They do not prove that a live rule
works until the idea is converted into a shared policy, paper sleeve, or field
and then tested through the standard Gate 1-4 protocol.

Oracle diagnostics are emitted by default with the canonical command. The saved
result includes `result["oracle_diagnostics"]` with `diagnostic_only=true`; the
block is also summarized in the console output. It does not change
`expected_value_score`, convergence, Gate 4, or any trade behavior.

To disable the diagnostic block for a smaller/debug-only run, add:

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-snapshot <SNAPSHOT> --no-oracle-diagnostics
```

`--include-oracle-diagnostics` remains accepted as a backwards-compatible alias
for explicit opt-in scripts.

Any oracle artifact must include:

- the canonical baseline artifact it was run against;
- the exact windows and snapshots;
- the candidate universe used;
- whether the analysis is fixed-entry, entry-oracle, ticker-pool, sleeve, or
  all-market;
- a clear `diagnostic_only: true` flag;
- the production-visible fields that could explain the oracle gap without
  using future data.

### Fixed-Entry Exit Oracle

Use this analysis to measure how far the current strategy is from better exits
when entries are held fixed.

Allowed diagnostic questions:

- With the same entries, what was the best achievable exit over the realized
  holding window?
- How much PnL did the current exit policy capture versus the best future
  price path?
- Were losses caused by bad entries, late exits, early exits, or avoidable
  giveback?
- Does the opportunity gap cluster by ticker, sector, strategy, sleeve,
  market state, DTE bucket, event family, or sizing rule?

Minimum metrics:

| Field | Meaning |
| --- | --- |
| `current_trade_pnl` | PnL under the canonical backtest exit. |
| `oracle_best_exit_pnl` | Best future exit PnL after the same entry under the diagnostic path. |
| `oracle_exit_gap_pnl` | `oracle_best_exit_pnl - current_trade_pnl`. |
| `profit_capture_ratio` | Current realized profit divided by oracle best profit when oracle best profit is positive. |
| `max_favorable_excursion_pct` | Best post-entry favorable move before final exit horizon. |
| `max_adverse_excursion_pct` | Worst post-entry adverse move before final exit horizon. |
| `giveback_pct` | Difference between max favorable move and realized exit result. |
| `oracle_best_exit_day` | Trading-day offset of the diagnostic best exit. |
| `exit_error_bucket` | `bad_entry`, `early_exit`, `late_exit`, `giveback`, or `no_oracle_edge`. |

Acceptance boundary:

- fixed-entry oracle output can justify a new exit hypothesis;
- it cannot justify a live exit change until that hypothesis is implemented as
  shared production/backtest logic and passes the same fixed-window protocol;
- do not use future-only best-exit timing as a rule input.

### Entry Oracle

Use this analysis to ask whether the current entry system is missing better
entries or selecting weak ones.

Allowed diagnostic questions:

- Among generated, selected, sliced, and rejected candidates, which future
  paths were actually attractive?
- Which production-known features distinguish selected winners from missed
  winners?
- Did ranking, slot pressure, filters, or universe membership cause the missed
  opportunity?
- Does a candidate's future edge cluster by ticker, sector, strategy, event
  family, relative strength, liquidity, volatility, market state, or news /
  filing field?

Minimum labels:

| Field | Meaning |
| --- | --- |
| `future_5d_return_pct` | Candidate forward return over 5 trading days. |
| `future_10d_return_pct` | Candidate forward return over 10 trading days. |
| `future_20d_return_pct` | Candidate forward return over 20 trading days. |
| `future_max_favorable_excursion_pct` | Best forward favorable move inside the diagnostic horizon. |
| `future_max_adverse_excursion_pct` | Worst forward adverse move inside the diagnostic horizon. |
| `selected_by_current_policy` | Whether the canonical policy selected the candidate. |
| `slot_sliced_by_current_policy` | Whether the candidate was qualified but lost to slot pressure. |
| `blocked_by_filter` | Filter or rule that blocked the candidate, when available. |
| `oracle_entry_quality_bucket` | Diagnostic label such as `strong`, `mixed`, `weak`, or `tail_risk`. |

Acceptance boundary:

- entry oracle output can only generate hypotheses about new fields, ranking,
  or sleeves;
- any promoted rule must use only fields known at decision time;
- broad filter or ranking changes still need full Gate 1-4 evidence.

### Ticker Pool And Sleeve Diagnostics

Use this analysis to decide whether current tickers belong in core, a smaller
risk budget, a default-off sleeve, or a removal watchlist.

Minimum metrics:

| Field | Meaning |
| --- | --- |
| `ticker_contribution_pnl` | Total realized PnL by ticker. |
| `ticker_contribution_ev` | EV contribution by ticker when available. |
| `tail_loss_contribution_pct` | Share of loss tail attributable to the ticker or cohort. |
| `replacement_value_pnl` | PnL versus the next selected or sliced candidate. |
| `no_trade_avoided_value_pnl` | Value of not taking the current-policy trade. |
| `sleeve_candidate` | Suggested sleeve destination, if any. |
| `forward_outcome_count` | Number of closed forward paper outcomes available. |

Acceptance boundary:

- ticker governance diagnostics can nominate keep, down-size, sleeve, observe,
  or remove candidates;
- live removal, quarantine, or down-sizing requires a separate Gate 1-4
  experiment unless it is explicitly paper/default-off;
- never remove a ticker solely from one to three bad trades.

### All-Market Candidate Discovery

Use this analysis to explore whether alpha exists outside the current ticker
pool.

Required controls:

- PIT universe membership;
- delisting and survivorship handling;
- stable price, liquidity, and data-quality gates;
- sector, industry, and theme attribution;
- no future index membership, future fundamentals, or future news availability
  as decision-time inputs;
- comparison against the existing core replacement candidate for the same day.

Minimum metrics:

| Field | Meaning |
| --- | --- |
| `research_universe_size` | Number of PIT-eligible securities considered. |
| `liquidity_pass_count` | Number that passed liquidity and price gates. |
| `paper_candidate_count` | Number emitted into the default-off queue. |
| `replacement_value_pnl` | Paper candidate PnL versus the displaced core candidate or cash. |
| `sector_concentration` | Exposure concentration by sector or theme. |
| `survivorship_controls_passed` | Whether PIT and delisting controls were documented. |

Acceptance boundary:

- all-market discovery starts as research-only or paper-only;
- it cannot expand core until the universe construction and replacement-value
  evidence are audited;
- all-market wins should first become a sleeve, field, or explicit ticker
  promotion protocol.

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
