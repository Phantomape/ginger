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

.\.venv\Scripts\python.exe -B quant\ohlcv_warehouse.py seed-snapshot-versions
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-warehouse data\experiments\exp-20260519-030\warehouse_main.sqlite --ohlcv-warehouse-snapshot-source <SNAPSHOT>
```

`<SNAPSHOT>` must be the matching canonical file for the window, for example
`data\ohlcv\ohlcv_snapshot_20241002_20250422.json` for `old_thin`. The command
above loads the warehouse `ohlcv_snapshot_versions` table, so standard
fixed-window baselines stay bit-exact to the organized snapshot files while
new work reads through the same SQLite warehouse surface.

For new broad/full-universe work, use the broad warehouse `ohlcv` table:

```powershell
.\.venv\Scripts\python.exe -B quant\ohlcv_warehouse.py seed-snapshots
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-warehouse data\experiments\exp-20260519-030\warehouse_main.sqlite
```

For legacy artifact reproduction that explicitly needs a JSON file input,
`--ohlcv-snapshot` remains supported:

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-snapshot <SNAPSHOT>
```

Do not mix OHLCV sources in a before/after Gate 4 comparison. Use
snapshot-vs-snapshot for legacy artifact reproduction, or
warehouse-vs-warehouse for new warehouse-backed experiments.

New backtest result files are written under `data\backtests\`. Legacy
root-level `data\backtest_results_*.json` references remain readable through
`quant/data_paths.py` compatibility resolvers when older checkouts still have
those files.

## 试点子组合回测

试点子组合回测（pilot sleeve replay）是显式开启的 point-in-time
模式。默认标准回测仍然是 core-only，不会把 `INTC` / `LITE` / `BE`
等试点 ticker 混入主候选池，也不会占用 core `MAX_POSITIONS` slot。

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-warehouse data\experiments\exp-20260519-030\warehouse_main.sqlite --ohlcv-warehouse-snapshot-source <SNAPSHOT> --include-pilot-sleeve
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
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-warehouse data\experiments\exp-20260519-030\warehouse_main.sqlite --ohlcv-warehouse-snapshot-source <SNAPSHOT> --include-pilot-sleeve
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

## Recent Observe-Only Window

New experiments should also report a recent diagnostic window when the data is
available and the extra run is practical. This window is observation only. It
must never block, accept, reject, roll back, or promote a strategy change.

| Label | Date range | Source | Gate role |
| --- | --- | --- | --- |
| `recent_observe` | `2026-04-22 -> <LATEST_COMPLETE_TRADING_DAY>` | broad warehouse `ohlcv` table | observe-only diagnostic |

Use the broad warehouse command shape:

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start 2026-04-22 --end <LATEST_COMPLETE_TRADING_DAY> --ohlcv-warehouse data\experiments\exp-20260519-030\warehouse_main.sqlite
```

Record recent-window output under `observe_only_windows` or an explicitly named
`recent_observe` block, not inside the Gate-4 decision block. Exclude it from
all acceptance arithmetic: aggregate EV/PnL deltas, window-improvement counts,
window-regression checks, drawdown guards, survival guards, concentration
guards, materiality checks, and comparator pass/fail logic. If the recent
window is unavailable, missing, stale, too short, or contradictory, record the
observation and continue using only the three fixed canonical windows for
Gate 1-4.

Current accepted fixed-window metrics use the production-faithful PIT earnings
snapshot `days_to_earnings` replay accepted in `exp-20260601-025` plus the
explicit same-day post-earnings continuation semantics accepted in
`exp-20260602-003`. The strategy stack keeps the core `exp-20260517-009`
(`ample_slot_stock_rank1_topup`) promotion on top of the accepted scarce-slot
rank-1 top-up, and now treats a same-day earnings row as post-event only when
actual EPS is already known and a later future earnings date exists.

| Label | EV score | Sharpe daily | Total PnL | Return | Max DD | Win rate | Trades | Survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 5.1628 | 4.41 | $117,072.92 | 117.07% | 6.65% | 83.33% | 18 | 80.39% |
| `mid_weak` | 2.1402 | 2.74 | $78,110.11 | 78.11% | 11.19% | 52.38% | 21 | 79.25% |
| `old_thin` | 0.5911 | 1.49 | $39,667.96 | 39.67% | 10.01% | 40.91% | 22 | 86.67% |

Artifact note:
`data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json`
records the current canonical core baseline version. Aggregate accepted-stack
EV is `7.8941`; aggregate PnL is `$234,850.99`. The prior PIT-DTE control
artifact is
`data/experiments/exp-20260601-025/exp_20260601_025_pit_dte_baseline_protocol.json`
with aggregate EV `6.3596` and PnL `$192,538.61`; use it only as the before
artifact for `exp-20260602-003` or older PIT-DTE comparisons.

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
.\.venv\Scripts\python.exe quant\backtester.py --start <START> --end <END> --ohlcv-warehouse data\experiments\exp-20260519-030\warehouse_main.sqlite --ohlcv-warehouse-snapshot-source <SNAPSHOT> --no-oracle-diagnostics
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
- paper/default-off ticker governance can be retained in the same experiment
  when it uses a shared helper, exposes the same observe-only daily surface, and
  leaves live/default orders unchanged;
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

- all-market discovery starts as paper/default-off or research-only;
- when PIT universe/data controls are already available and the daily path can
  expose the same fields, prefer a shared-paper-first default-off helper over a
  private research scout;
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
