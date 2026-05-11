# Current State

Last updated: 2026-05-11.

The current accepted core stack includes the 2026-05-10 TRIP sector taxonomy
completion from `exp-20260510-015`, layered on top of the RS20 entry-state
shared sizing promotion from `exp-20260510-012`. Both are documented in
`docs/backtesting.md` and `docs/alpha-optimization-playbook.md`. Canonical
fixed-window core metrics are:

| Window | EV | Return | Sharpe daily | Max DD | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|
| `late_strong` | 4.2340 | 94.09% | 4.50 | 5.48% | 19 | 80.39% |
| `mid_weak` | 1.6689 | 61.81% | 2.70 | 9.41% | 21 | 79.25% |
| `old_thin` | 0.3853 | 28.54% | 1.35 | 8.15% | 22 | 91.67% |

Latest standalone backtest datapoint: `data/backtest_results_20260510.json`
refreshes the accepted `late_strong` window at the same canonical values
(`EV 4.2340`, `PnL $94,086.91`, `survival 80.39%`). `mid_weak` and `old_thin`
still rely on the accepted three-window artifact from
`data/experiments/exp-20260510-015/trip_sector_taxonomy.json`.

Latest accepted alpha result: `exp-20260510-015` maps TRIP to Consumer
Discretionary in shared `risk_engine.SECTOR_MAP` instead of leaving it in the
`Unknown` sector path. Aggregate EV improved `+0.0171` (`+0.27%`) and aggregate
PnL improved `+$403.46` (`+0.22%`) across the three canonical windows, with
unchanged trade count and survival. The effect flows through shared sector
enrichment / sector-dispersion allocation, so this is production-visible and
not a replay-only branch.

Recent slot alpha-search scout: `exp-20260510-018` rejected effective core slot
accounting from observed-only slot-missed replacement value. All blocked rows
were positive in aggregate (`25` rows, `+$8,330.63`), but failed the gate because
win rate was only `40%` and only `1/3` windows was positive. Pure one-extra-slot
rows were positive but too concentrated in PLTR; breakout rows need
`available_slots > 1` because the accepted scarce-slot breakout deferral is
still active.

Latest alpha-search discovery: `exp-20260510-023` found that the newly completed
non-OHLCV SEC snapshots can support a three-window T+1 event-drift shadow
surface. The broad positive T+1 excess-drift SEC label was only paper-watch
quality (`363` valid 10d rows, 10d avg return `+1.22%`, win rate `51.79%`,
positive 10d-average windows `2/3`). `exp-20260510-024` then isolated the useful
semantic slice: `earnings_8k` plus `periodic_report` events with positive T+1
excess drift produced `184` valid 10d rows, 10d avg return `+2.23%`, win rate
`53.80%`, and positive 10d-average return in `3/3` windows. This is still
observed-only and must not become live trading without forward paper outcomes.

Latest production-visible alpha surface: `exp-20260510-025` moved that exact
SEC financial-report + positive T+1 excess label into a default-off paper queue
and sleeve. It is production-visible, but not trade-enabled: no orders, no core
ranking changes, no sizing changes, and no slot use. Focused tests passed
(`22 passed`), and the canonical three-window core metrics stayed unchanged:
`late_strong` EV `4.2340`, `mid_weak` EV `1.6689`, and `old_thin` EV `0.3853`.

Latest queue-quality refinement: `exp-20260510-027` keeps the SEC
financial-report T+1 queue default-off but freezes its forward observation pool
to non-platform candidates. On the same three fixed windows, excluding
`platform_pool` improved the 10d average from `0.022332` to `0.027636` across
`157` valid 10d non-platform rows, while the excluded platform slice averaged
`-0.008507`. This changes only the shared observe-only queue policy and still
requires closed forward paper outcomes before any trade-enabled promotion.

Latest SEC blocking audit: `exp-20260511-001` confirms the older filing-shock
branch is still blocked by missing directional event fields, not by PIT
timestamp plumbing. Same-accession repair checks found only sparse directional
rows and still no usable B/C candidate cohort, so do not spend another loop on
filing-recency retunes, Companyfacts weighting, or adjacent filing-shock
threshold work until PIT-safe EPS/revenue surprise or guidance fields exist on
actual candidate dates.

Latest candidate-pool alpha search: `exp-20260511-002` tested the
`SPACE_CATALYST_SHADOW` operating equities in deterministic snapshot copies.
The static replay was raw-positive in all three canonical windows: aggregate EV
`+2.3036`, aggregate PnL `+$64,577.73`, and added space trades contributed
`+$79,995.67` across `25` trades. It is still rejected for production alpha
because the pool is selected with 2026-05-10 knowledge and old-window max
drawdown worsened from `8.15%` to `11.71%`. Keep the space theme observe-only;
the next valid evidence is forward shadow replacement value, not live slot
enablement or core universe promotion.

Latest forward-observation alpha surface: `exp-20260511-003` accepted the
space catalyst theme as a production-visible, default-off shadow surface. The
daily run now exposes `SPACE_CATALYST_SHADOW` records, event fields, and
promotion gates in the universe state, report, and `quant_signals` output, but
keeps live slots at `0` and changes no orders, ranking, sizing, filters, or core
candidate pool. The canonical three-window core metrics stayed unchanged:
`late_strong` EV `4.2340`, `mid_weak` EV `1.6689`, and `old_thin` EV `0.3853`.
The next evidence is closed forward direct PnL and replacement value, not a
static space-pool promotion.

Latest space catalyst attribution step: `exp-20260511-008` started an
event-state shadow ledger for the space theme instead of re-mining a static
space basket. It seeded six official/attention events across
`fundamental_contract_regulatory`, `defense_budget_theme`, and `attention_only`
buckets, then tracked cash-relative, core/benchmark-relative, and same-theme
replacement value. Only the `LUNR` NASA CLPS event is mature so far: on a
`$10k` notional it was `-6.42%` after 1 trading day, `-1.51%` after 5 trading
days, and `+6.91%` after 10 trading days, with positive 10d same-theme value
and positive 10d `UFO`-relative value. The gate remains failed because only
`1/10` required closed decisions is mature. Keep the sleeve observe-only until
official catalyst buckets, not attention-only rows, prove positive forward
replacement value.

Current priority: do not retune local add-on trigger, cap, heat, reserve,
strategy-cohort variants, ETF overlay parameters, nearby RS20 risk scalars,
single-ticker sector taxonomy, global `MAX_POSITIONS`, or scarce-slot breakout
thresholds on the same frozen samples. Future slot work needs a shared
exposure/risk-based effective-slot accounting design with full portfolio replay
and production visibility, not another global slot-count sweep. Do not keep
retuning the SEC financial-report T+1 label or adjacent cohort slices on the
same frozen sample; after the non-platform queue freeze, the next evidence for
that branch is closed forward paper replacement value. For space catalyst, do
not mine adjacent tickers or enable live slots without closed forward
replacement-value evidence.

Latest Space risk-allocation alpha search: `exp-20260511-009` swept a sleeve-level risk scalar on the rejected static Space catalyst pool. The highest-EV variant was `1.0x`: aggregate EV delta `+2.3036`, aggregate PnL delta `$64,577.73`, max drawdown damage `3.56%`, and Gate passed `False`. The closest risk-controlled variant was `0.75x`, but it still regressed `late_strong` EV. Conclusion: simple static-pool risk discount is not enough; Space should remain official-catalyst forward paper, not broad static universe enablement or attention-headline ranking.

### 2026-05-11 alpha search note: TQS-conditioned sector follower risk

`exp-20260511-010` tested a relative-TQS discriminator on the rejected same-day
sector follower haircut. It improved aggregate EV by
`+0.1144` and PnL by
`$+1,481.64`, but touched only the late window, so no
shared production/backtest sizing policy was promoted.
