# Current State

Last updated: 2026-05-13.

The current accepted core stack includes the 2026-05-13 clean SPY-relative
leader signal-day sizing promotion from `exp-20260513-036`, layered on top of
the RS60 top-quintile stock sizing promotion from `exp-20260513-030`, the
signal-day own-green candle sizing promotion from `exp-20260513-007`, the
2026-05-10 TRIP sector taxonomy completion from `exp-20260510-015`, and the
RS20 entry-state shared sizing promotion from `exp-20260510-012`. These are
documented in `docs/backtesting.md` and
`docs/alpha-optimization-playbook.md`. Canonical fixed-window core metrics are:

| Window | EV | Return | Sharpe daily | Max DD | Trades | Survival |
|---|---:|---:|---:|---:|---:|---:|
| `late_strong` | 4.3768 | 99.70% | 4.39 | 6.02% | 19 | 80.39% |
| `mid_weak` | 1.6788 | 62.64% | 2.68 | 9.70% | 21 | 79.25% |
| `old_thin` | 0.4292 | 31.56% | 1.36 | 8.36% | 22 | 91.67% |

Latest accepted three-window artifact:
`data/experiments/exp-20260513-036/clean_spy_leader_signal_day_risk.json`.
Aggregate core EV is now `6.4848`; aggregate PnL is `$193,903.95`.
Latest saved single-window backtest artifact on disk is
`data/backtest_results_20260513.json`; it predates `exp-20260513-036` and
matches the prior `old_thin` core window at EV `0.4151`, total PnL
`$30,524.01`, daily Sharpe `1.36`, max drawdown `8.21%`, `22` trades, and
survival `91.67%`.

Latest accepted alpha result: `exp-20260513-036` computes signal-day
ticker-minus-SPY open-to-close return in shared `risk_engine.py` and applies a
1.10x cap-aware post-sizing top-up in `portfolio_engine.py` only to already
clean `risk_on` SPY-relative leaders whose ticker also beat SPY on the signal
day. Aggregate EV improved `+0.0246` and aggregate PnL improved `+$2,620.01`
across the three canonical windows, with unchanged trade count and survival.
The rule lives in shared `risk_engine.py` and `portfolio_engine.py`, with
backtester attribution and focused tests, so it is production-visible and not a
replay-only branch.

Previous accepted alpha result: `exp-20260513-030` computes 60-trading-day
momentum in shared `feature_layer.py`, tags already-qualified `trend_long` /
`breakout_long` stock signals whose same-day return is in the top quintile of
the feature-complete non-ETF/non-commodity stock universe, and applies a
1.15x cap-aware post-sizing top-up. Aggregate EV improved `+0.1094` and
aggregate PnL improved `+$4,615.93` across the three canonical windows, with
unchanged trade count and survival. The rule lives in shared `feature_layer.py`,
`risk_engine.py`, and `portfolio_engine.py`, with backtester attribution and
focused parity tests, so it is production-visible and not a replay-only branch.

Previous accepted alpha result: `exp-20260513-007` tags signals whose own
signal-day candle closes above its open and applies a conservative 1.05x
cap-aware post-sizing top-up. Aggregate EV improved `+0.0626` and aggregate
PnL improved `+$2,223.59` across the three canonical windows, with unchanged
trade count and survival. The rule lives in shared `feature_layer.py`,
`risk_engine.py`, and `portfolio_engine.py`, with backtester attribution and
focused parity tests, so it is production-visible and not a replay-only branch.

Latest accepted default-off SEC paper stack: `exp-20260511-112`,
`exp-20260512-001`, `exp-20260512-006`, `exp-20260512-007`, and
`exp-20260512-020` now define the current financial-report T+1 paper baseline.
The accepted sleeve is:
non-platform `earnings_8k` / `periodic_report` rows only, `max_positions=3`,
`t1_excess_return_vs_spy >= 1%`, 10-trading-day hold, `$15,000` base paper
notional, `periodic_report` at `1.25x` that base, and `10-Q periodic_report`
at `2.00x`. The latest accepted three-window sleeve datapoint is aggregate EV
`8.558004`, total PnL `$234,762.79`, sleeve PnL `$48,332.18`, and max
drawdown ceiling `10.0721%`. `exp-20260512-025` then rejected 10-Q-first queue
priority despite positive aggregate EV/PnL because only `old_thin` improved
while `late_strong` regressed, so the next valid SEC step is forward
replacement value or a new earnings-quality field, not another same-sample
queue-order or lifecycle retune.

Latest accepted default-off Space forward stack: the accepted official-catalyst
Space baseline from `exp-20260511-011`, `019`, `021`, `031`, `032`, and `105`
now extends through `exp-20260512-004`, `008`, `013`, `031`, `032`, `037`,
`038`, `041`, `112`, `exp-20260513-012`, `exp-20260513-014`,
`exp-20260513-015`, `exp-20260513-020`, `exp-20260513-028`,
`exp-20260513-032`, `exp-20260513-038`, `exp-20260513-039`, and
`exp-20260513-108`, `exp-20260513-110`, `exp-20260513-113`, and
`exp-20260514-002`.
The supported direction is quality-conditioned risk allocation, peer-relative
breakout leadership, small-cap risk-appetite allocation, and production-visible
catalyst-quality allocation: perfect-TQS official Space signals get a `1.5x`
top-up, near-perfect official Space `trend_long` gets a `1.10x` top-up,
peer-nonleader official Space `breakout_long` gets `0.00x` extra risk, official
Space signals get `1.10x` extra default-off risk when IWM 20d momentum is above
SPY 20d momentum, official Space `trend_long` signals get `1.15x` extra
default-off risk when IWM leads SPY and the ticker's 20d momentum leads the
official Space basket average, `launch_lunar` theme-segment signals get
`1.10x` extra default-off risk, and official Space signals with production registry
`liquidity_tier=ok` get `1.10x` extra default-off risk, and official Space
signals tied to `customer_win` event seeds from official/regulatory/company
primary sources get `1.10x` extra default-off risk, and official Space signals
with source-qualified `customer_win` plus Space peer momentum leadership get
`1.10x` extra default-off risk, and official Space signals with
`government_space_contract` from official/government sources plus Space peer
momentum leadership get `1.05x` extra default-off risk, and official Space signals
whose production registry `event_guard_profile` contains financing/dilution get
`1.075x` extra default-off risk, and official Space signals with production
registry `liquidity_tier=watch` get `1.10x` extra default-off risk, and
official Space signals with at least two official non-attention event seed rows
get `1.075x` extra default-off risk, and official Space signals with exactly
one official non-attention defense-budget `government_space_contract` seed and
no `customer_win` seed get `1.05x` extra default-off risk, and official Space
signals whose event-seed profile has both an attention-only seed and an official
non-attention seed get `1.25x` extra default-off risk, official Space signals
with non-attention source diversity get `1.075x` extra default-off risk, and
source-diverse official Space signals that also lead the Space peer basket get
`1.15x` extra default-off risk, and source-diverse official Space signals also
get `1.05x` extra default-off risk when IWM 20d momentum beats SPY 20d
momentum, and source-diverse official Space signals that also lead the Space
peer basket while IWM beats SPY get a further `1.05x` extra default-off risk,
and official non-attention Space tickers whose closed 10d event-state profiles
are both cash-positive and same-theme replacement-positive get a further
`1.05x` extra default-off risk, and the narrower BKSY/RDW/RKLB closed-forward
profile bucket with average 10d same-theme replacement value `>= $500` gets
another `1.05x` extra default-off risk.
This remains
metadata/helper only with live Space slots at zero. `exp-20260512-010` rejected
nearby near-perfect breakout TQS gating, `exp-20260512-031` accepted the
IWM-relative state only at `1.10x`, `exp-20260512-032` accepted launch/lunar
theme risk only at `1.10x`, `exp-20260512-035` rejected data/defense theme
scaling, `exp-20260512-037` accepted liquidity-tier anchor risk only at
`1.10x`, and `exp-20260512-038` accepted customer-source risk only at `1.10x`;
`exp-20260512-041` accepted financing/dilution profile risk only at `1.075x`;
`exp-20260512-112` accepted watch-liquidity risk only at `1.10x`;
`exp-20260513-012` accepted multi-event official catalyst-depth risk only at
`1.075x`; `exp-20260513-014` accepted customer-source peer-leader risk only at
`1.10x`; and `exp-20260513-015` accepted government-contract peer-leader risk
only at `1.05x`; and `exp-20260513-020` accepted IWM-plus-peer-leader
`trend_long` risk only at `1.15x`; and `exp-20260513-028` accepted
single-event defense-only risk only at `1.05x`; and `exp-20260513-032`
accepted attention-overlay-with-official-catalyst risk only at `1.25x`. The
`exp-20260513-032` aggregate improved versus the accepted `exp-20260513-028`
stack from EV `17.8725` / PnL `$436,331.45` to EV `18.7513` / PnL
`$444,450.36`; all three windows improved EV and max drawdown ceiling improved
by `3.84 pp`. `exp-20260513-038` then accepted source-diversity risk only at
`1.075x`, and `exp-20260513-039` accepted the source-diversity peer-leader
interaction only at `1.15x`: aggregate EV moved from `22.1922` to `22.9617`,
PnL from `$529,603.76` to `$550,143.02`, with no trade-count or survival
change. `exp-20260513-108` then accepted the source-diversity IWM-leader
interaction only at `1.05x`: aggregate EV moved from `22.9617` to `23.4374`,
PnL from `$550,143.02` to `$564,173.22`, all three windows improved EV, max
drawdown drift stayed inside Gate 4 at `+0.47 pp`, and live Space slots still
zero. `exp-20260513-110` then accepted the source-diversity peer+IWM-leader
interaction only at `1.05x`: aggregate EV moved from `23.4374` to `23.6930`,
PnL from `$564,173.22` to `$570,527.21`, `mid_weak` and `old_thin` improved
while `late_strong` was unchanged, max drawdown drift stayed inside Gate 4 at
`+0.40 pp`, trade count and survival stayed unchanged, and live Space slots
still zero. `exp-20260513-113` then accepted forward replacement-positive
official Space risk only at `1.05x`: aggregate EV moved from `23.6930` to
`24.0468`, PnL from `$570,527.21` to `$584,613.67`, all three windows improved
EV, max drawdown drift stayed inside Gate 4 at `+0.48 pp`, trade count and
survival stayed unchanged, and live Space slots still zero.
`exp-20260514-002` then accepted same-theme replacement-strength risk only at
the `$500` floor / `1.05x` scalar: aggregate EV moved from `24.0468` to
`24.4642`, PnL from `$584,613.67` to `$599,684.05`, all three windows improved
EV, max drawdown drift stayed inside Gate 4 at `+0.49 pp`, trade count and
survival stayed unchanged, and live Space slots still zero.

Latest rejected Space alpha search: `exp-20260513-019` tested whether the
accepted customer-source edge should also top up peer-nonleader official Space
signals. Aggregate EV improved `+0.1320`, but the result did not clear the
Space three-window gate, so customer-source allocation should stay tied to
stronger peer-quality buckets. Do not promote customer-source peer-nonleader
scaling on the frozen snapshots.

Latest rejected core entry alpha search: `exp-20260512-024` tested a
deterministic OHLCV `pullback_reclaim_long` entry shape for leadership
pullbacks above the 200MA, 5-15% below 52-week highs, with positive 10d/20d
momentum and no 20d breakout/breakdown. It failed all three canonical windows:
aggregate EV `6.2882 -> 3.9873`, aggregate PnL `-$48,599.83`, and max drawdown
ceiling worsened `+2.07 pp`. Do not promote or retune nearby pullback/reclaim
entry thresholds on the frozen windows; this candidate-pool direction adds too
many lower-quality trades under the current exit/risk stack.

Latest rejected core exit alpha search: `exp-20260513-112` tested converting
the observed early SPY-relative underperformance loss family into a next-open
full exit after the third holding-session close. It executed only three exits,
all in `old_thin`, and failed Gate 4: aggregate EV `6.4848 -> 6.4440`,
aggregate PnL `$193,903.95 -> $192,217.84`, with no improved window and
`old_thin` EV `0.4292 -> 0.3884`. Do not retune nearby day-count or
relative-weakness exit thresholds without forward lifecycle attribution.

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
strategy-cohort variants, ETF overlay parameters, nearby RS20 or RS60 risk
scalars, single-ticker sector taxonomy, global `MAX_POSITIONS`, or scarce-slot
breakout thresholds on the same frozen samples. Future slot work needs a shared
exposure/risk-based effective-slot accounting design with full portfolio replay
and production visibility, not another global slot-count sweep. Do not keep
retuning the SEC financial-report T+1 label or adjacent cohort slices on the
same frozen sample; after the non-platform queue freeze, the next evidence for
that branch is closed forward paper replacement value. For space catalyst, do
not mine adjacent tickers or enable live slots without closed forward
replacement-value evidence.

Latest Space risk-allocation alpha search: `exp-20260511-009` swept a sleeve-level risk scalar on the rejected static Space catalyst pool. The highest-EV variant was `1.0x`: aggregate EV delta `+2.3036`, aggregate PnL delta `$64,577.73`, max drawdown damage `3.56%`, and Gate passed `False`. The closest risk-controlled variant was `0.75x`, but it still regressed `late_strong` EV. Conclusion: simple static-pool risk discount is not enough; Space should remain official-catalyst forward paper, not broad static universe enablement or attention-headline ranking.

Latest low-deployment ETF alpha search: `exp-20260512-777` tested whether the
accepted default-off low-deployment ETF overlay should change its candidate
pool from the current `QQQ` / `SPY` / `IWM` / `GLD` / `SLV` set. No tested
variant beat v1 across the canonical three-window gate. `equity_only` improved
2/3 windows but regressed one; `add_energy` and `cross_asset_plus` had positive
aggregate EV/PnL but were single-window/unstable with drawdown damage. Keep the
v1 paper pool unchanged and do not retry adjacent ETF pool variants on the same
frozen samples without forward replacement-value evidence.

### 2026-05-11 alpha search note: TQS-conditioned sector follower risk

`exp-20260511-010` tested a relative-TQS discriminator on the rejected same-day
sector follower haircut. It improved aggregate EV by
`+0.1144` and PnL by
`$+1,481.64`, but touched only the late window, so no
shared production/backtest sizing policy was promoted.

Latest accepted Space forward hypothesis: `exp-20260511-011` locked the official-catalyst Space subpool from `exp-20260511-010` and swept only the risk budget. The best passing scalar was `0.75x`: aggregate EV delta `+1.5598`, aggregate PnL delta `$32,256.34`, and max drawdown damage `1.97%`. This is production-visible but default-off: live Space slots remain zero until forward replacement-value evidence matures.

Latest Space sleeve refinement: `exp-20260511-012` tested whether the accepted official-catalyst Space 0.75x forward hypothesis should be restricted to `trend_long` entries. The result was `rejected_trend_only_refinement`: aggregate EV delta versus exp-20260511-011 was `-0.3072` and aggregate PnL delta was `$-1,909.20`. Keep the official-catalyst 0.75x hypothesis unchanged unless forward strategy-family replacement value says otherwise.

Latest same-sector cluster risk scout: `exp-20260511-013` broadened the relative-TQS same-day same-sector follower haircut from the prior risk-on-only scout to all core A/B entries. The result was `rejected_replay_only`: aggregate EV moved `+0.0740`, but aggregate PnL fell `$-529.66` and `old_thin` regressed by EV `-0.0404` / PnL `$-2,011.30`. Do not promote or repeat all-core same-sector TQS follower haircuts on the frozen windows without forward cluster-quality evidence or a different orthogonal discriminator.

Latest Space breakout refinement: `exp-20260511-015` tested a Space official-catalyst `breakout_long` entry-to-stop risk-distance cap on top of the accepted 0.75x default-off hypothesis. The result was `rejected_breakout_risk_distance_refinement`: best cap `10%`, aggregate EV delta versus exp-20260511-011 `+0.0000`, aggregate PnL delta `$+0.00`. Keep Space live slots at zero; any accepted refinement remains default-off until forward replacement-value evidence matures.

## Latest Space Add-On Refinement

Latest Space add-on refinement: `exp-20260511-014` tested disabling follow-through add-ons for the accepted 0.75x official-catalyst Space sleeve. The refinement was rejected versus `exp-20260511-011`; keep the accepted sleeve unchanged and do not disable all Space add-ons without a more selective ex-ante lifecycle signal.

Latest Space RS20 refinement: `exp-20260511-016` tested whether the accepted official-catalyst Space 0.75x forward hypothesis should require the existing `rs20_entry_state_leader` flag. The result was `rejected_rs20_leader_refinement`: aggregate EV delta versus exp-20260511-011 `+0.0000`, aggregate PnL delta `$+0.00`. Keep the official-catalyst 0.75x hypothesis unchanged unless forward RS20-bucket replacement value says otherwise.

Latest core broad-rotation alpha search: `exp-20260511-017` tested `breakout_long` risk allocation when `IWM` 20d momentum beat `SPY` by more than 2pp. The best variant was `1.50x`, with aggregate EV delta `+0.1269` and PnL delta `$+1,740.56`, but only `late_strong` improved, `mid_weak` was unchanged, and `old_thin` regressed slightly. No shared policy was promoted; do not retry nearby broad-rotation breakout multipliers on this same threshold without event/news context, candidate replacement value, or a richer breadth discriminator.

Latest Space data-vendor refinement: `exp-20260511-018` tested whether the accepted official-catalyst Space 0.75x forward hypothesis should allow PL/BKSY only as `trend_long` entries. The result was `rejected_data_vendor_trend_gate`: aggregate EV delta versus exp-20260511-011 `-0.4195`, aggregate PnL delta `$-1,137.22`. Do not generalize this to all Space breakout entries; keep it scoped to the data-vendor subsegment.

Latest Space data-vendor breakout risk refinement: `exp-20260511-019` swept an extra risk scalar for PL/BKSY `breakout_long` entries inside the accepted official-catalyst Space 0.75x forward hypothesis. The best scalar was `0.25` with decision `accepted_default_off_data_vendor_breakout_risk_haircut`: aggregate EV delta versus exp-20260511-011 `+0.2741`, aggregate PnL delta `$+3,774.55`. This is now shared default-off Space sleeve metadata/helper only; live Space slots remain zero and no core order/ranking/sizing path changed.

Latest Space launch/connectivity trend risk refinement: `exp-20260511-021` tested an extra bounded scalar for RKLB/ASTS `trend_long` entries on top of the accepted official-catalyst Space 0.75x hypothesis and PL/BKSY breakout 0.25x haircut. The best scalar was `1.25` with decision `accepted_default_off_launch_connectivity_trend_risk_topup`: aggregate EV delta versus exp019 `+0.3686`, aggregate PnL delta `$+6,661.77`.

Latest Space non-data-vendor breakout risk refinement: `exp-20260511-022` swept an extra scalar for RKLB/ASTS/RDW/LUNR-style `breakout_long` entries while keeping the accepted PL/BKSY breakout haircut and RKLB/ASTS trend top-up fixed. The best scalar was `0.25` with decision `rejected_non_data_vendor_breakout_risk_haircut`: aggregate EV delta versus the accepted Space + PL/BKSY haircut + RKLB/ASTS trend before state `+0.2184`, aggregate PnL delta `$-44.75`.

Latest Space remaining trend risk refinement: `exp-20260511-023` tested extending the accepted trend top-up beyond RKLB/ASTS to remaining official-catalyst `trend_long` entries. The best scalar was `1.5` with decision `rejected_remaining_trend_risk_topup`: aggregate EV delta versus exp021 `+0.2263`, aggregate PnL delta `$+10,047.75`. The result was positive but underpowered because it improved fewer than two canonical windows.



## exp-20260511-026 Space satcom breadth low-risk

- timestamp: 2026-05-11T14:18:24+00:00
- lane: alpha_search
- decision: rejected_satcom_breadth_low_risk_extension
- changed_variable: space_satcom_breadth_risk_scalar
- best_satcom_breadth_risk_scalar: 0.75
- expected_value_score_delta_vs_before: 0.9043
- before_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 9.395, 'total_pnl_sum': 242349.79, 'trade_count_sum': 83, 'min_survival_rate': 0.8462, 'max_drawdown_pct_max': 0.1013}
- interpretation: Space alpha should stay focused on the official-catalyst operating sleeve and the already accepted PL/BKSY and RKLB/ASTS risk refinements. Mature-satcom breadth is not strong enough to add without a future PIT event trigger.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-026\space_satcom_breadth_low_risk.json`

## exp-20260511-027 Post-news item-composition gate

- timestamp: 2026-05-11T15:06:44+00:00
- lane: alpha_search
- decision: rejected_item_composition_gate
- changed_variable: post_news_8k_item_composition_gate
- best_variant: exclude_auxiliary_items
- result: versus raw post-news, aggregate EV improved `+0.2028` but only `late_strong` improved; `mid_weak` and `old_thin` regressed versus the raw post-news surface.
- core comparison: the best gated stack was still positive versus accepted core in all three windows (`aggregate EV +0.4491`, PnL `+$8,407.30`), but missed the materiality gate and worsened old-window drawdown.
- interpretation: post-news continuation remains a forward candidate-pool lead, but 8-K auxiliary-item exclusion is not a stable discriminator on the frozen sample.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False}
- artifact: `data\experiments\exp-20260511-027\post_news_item_composition.json`


## exp-20260511-028 Space launch/connectivity breakout risk

- timestamp: 2026-05-11T15:17:38+00:00
- lane: alpha_search
- decision: rejected_launch_connectivity_breakout_risk_haircut
- changed_variable: space_launch_connectivity_breakout_risk_scalar
- best_launch_connectivity_breakout_scalar: 0.25
- expected_value_score_delta_vs_before: 0.2184
- before_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.7091, 'total_pnl_sum': 227092.33, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1016}
- interpretation: The RKLB/ASTS trend top-up remains the supported launch/connectivity refinement. Do not add a separate breakout haircut for RKLB/ASTS on this frozen replay sample.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-028\space_launch_connectivity_breakout_risk.json`
## exp-20260511-029 Post-news surprise-direction gate

- timestamp: 2026-05-11T16:10:40+00:00
- lane: alpha_search
- decision: rejected_surprise_direction_gate
- changed_variable: post_news_surprise_direction_gate
- best_variant: unknown_only
- expected_value_score_delta_vs_raw: 0.0012
- gate4_passed: False
- interpretation: The PIT surprise_direction semantic label did not improve the locked post-news continuation surface enough to justify promotion. Explicit positive/negative labels were sparse and did not rescue the raw PEAD-like sleeve from the materiality problem.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'alters_signal_generation': False, 'alters_candidate_ranking': False, 'alters_sizing': False, 'alters_orders': False, 'live_slots_changed': False}
- artifact: `data\experiments\exp-20260511-029\post_news_surprise_direction.json`


## exp-20260511-030 Space theme momentum risk

- timestamp: 2026-05-11T16:26:26+00:00
- lane: alpha_search
- decision: rejected_theme_weak_space_risk_scalar
- changed_variable: space_theme_weak_risk_scalar
- best_theme_weak_risk_scalar: 0.0
- expected_value_score_delta_vs_before: 0.0
- before_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Do not add a theme ETF momentum risk gate to the Space sleeve. The accepted Space stack should stay focused on catalyst bucket and ticker/strategy lifecycle scalars, not theme ETF timing.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-030\space_theme_momentum_risk.json`


## exp-20260511-031 Space data-vendor breakout zero sweep

- timestamp: 2026-05-11T16:52:12+00:00
- lane: alpha_search
- decision: accepted_default_off_data_vendor_breakout_0_1_scalar
- changed_variable: space_data_vendor_breakout_risk_scalar
- best_data_vendor_breakout_risk_scalar: 0.1
- expected_value_score_delta_vs_before: 0.0572
- before_aggregate: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.5479, 'total_pnl_sum': 227864.06, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: A lower PL/BKSY breakout scalar improved the accepted Space stack under the three-window gate. Promote only as default-off forward metadata because Space live slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-031\space_data_vendor_breakout_zero_sweep.json`

## exp-20260511-032 Space event ledger adapter

- timestamp: 2026-05-11
- lane: measurement_repair
- decision: accepted_observe_only_daily_event_ledger_adapter
- changed_variable: space_event_ledger_daily_adapter
- result: the daily path now builds and persists a `SPACE_CATALYST_EVENT_STATE_SHADOW_LEDGER`, includes it in `trend_signals` / `quant_signals`, and renders it in the report without enabling Space live slots.
- validation: focused tests `20 passed`; snapshot probe on the augmented late window at `2026-04-21` produced `2` active seed events, `2` event rows, `1` closed 10d decision, and a blocked promotion gate.
- interpretation: Space should now collect forward event-state evidence daily. Do not promote `SPACE_CATALYST_SPECIALIST` until official catalyst buckets produce at least `10` mature closed decisions with positive direct and replacement value.
- production_impact: {'shared_policy_changed': False, 'shared_observation_helper_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'live_slots_changed': False, 'live_slots': 0}


## exp-20260511-032 Space trend target extension

- timestamp: 2026-05-11T17:14:31+00:00
- lane: alpha_search
- decision: accepted_default_off_space_trend_target_extension
- changed_variable: space_official_trend_target_atr_mult
- best_space_trend_target_atr_mult: 5.0
- expected_value_score_delta_vs_before: 0.4081
- before_aggregate: {'expected_value_score_sum': 8.5479, 'total_pnl_sum': 227864.06, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.956, 'total_pnl_sum': 237013.66, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Wider targets for official-catalyst Space trend entries improved the accepted default-off Space stack. Promotion must remain default-off metadata/helper only because live Space slots are zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-032\space_trend_target_extension.json`


## exp-20260511-037 Space breakout target extension

- timestamp: 2026-05-11T18:07:37+00:00
- lane: alpha_search
- decision: rejected_space_breakout_target_extension
- changed_variable: space_official_breakout_target_atr_mult
- best_space_breakout_target_atr_mult: 6.0
- expected_value_score_delta_vs_before: 0.0179
- before_aggregate: {'expected_value_score_sum': 8.956, 'total_pnl_sum': 237013.66, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.9739, 'total_pnl_sum': 237817.62, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Space breakout convexity is not the next supported same-sample refinement. Keep the accepted trend target extension, PL/BKSY breakout haircut, and RKLB/ASTS trend top-up unchanged.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-037\space_breakout_target_extension.json`

## exp-20260511-038 Space trend target bucket scope

- timestamp: 2026-05-11T18:15:03+00:00
- lane: alpha_search
- decision: rejected_space_trend_target_scope
- changed_variable: space_official_trend_target_bucket_scope
- best_variant: exclude_data_vendor_trend
- expected_value_score_delta_vs_before: -0.0270
- before_aggregate: {'expected_value_score_sum': 8.9564, 'total_pnl_sum': 237030.87, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 8.9294, 'total_pnl_sum': 235932.28, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Keep the accepted official-catalyst Space 5 ATR trend target broad across the full official bucket. Narrowing it away from PL/BKSY data-vendor trend or toward launch/connectivity did not add alpha on the frozen three-window sample.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-038\space_trend_target_bucket_scope.json`

## exp-20260511-105 Space launch/connectivity trend target

- timestamp: 2026-05-11T19:12:47+00:00
- lane: alpha_search
- decision: accepted_default_off_launch_connectivity_trend_target_extension
- changed_variable: space_launch_connectivity_trend_target_atr_mult
- best_launch_connectivity_trend_target_atr_mult: 7.0
- expected_value_score_delta_vs_before: 0.9838
- before_aggregate: {'expected_value_score_sum': 8.9564, 'total_pnl_sum': 237030.87, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_aggregate: {'expected_value_score_sum': 9.9402, 'total_pnl_sum': 253985.68, 'trade_count_sum': 73, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- interpretation: Keep the accepted 5 ATR target for all official Space trend signals, but use 7 ATR for RKLB/ASTS launch/connectivity trend_long signals. This is default-off Space metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-105\space_launch_connectivity_trend_target.json`

## exp-20260511-106 Space lunar/manufacturing trend target

- timestamp: 2026-05-11T20:46:58+00:00
- lane: alpha_search
- decision: rejected_lunar_manufacturing_trend_target_extension
- changed_variable: space_lunar_manufacturing_trend_target_atr_mult
- best_variant: lunar_manufacturing_7_0
- expected_value_score_delta_vs_before: -0.0788
- pnl_delta_vs_before: $-4,380.35
- interpretation: RKLB/ASTS launch-connectivity trend convexity does not transfer to LUNR/RDW lunar/manufacturing trend signals. Keep non-launch official Space trend targets at the accepted 5 ATR path.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-106\space_lunar_manufacturing_trend_target.json`

## exp-20260511-110 Space breakout stop width

- timestamp: 2026-05-11T21:22:33+00:00
- lane: alpha_search
- decision: rejected_space_breakout_stop_width
- changed_variable: space_official_breakout_stop_atr_mult
- best_variant: breakout_stop_2_0
- expected_value_score_delta_vs_before: -0.2752
- pnl_delta_vs_before: $+964.57
- interpretation: Widening official Space breakout stops helped late_strong but damaged mid_weak and old_thin EV. Space breakout fragility is not fixed by simply giving breakouts more stop room; keep the accepted exp-105 stack unchanged.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-110\space_breakout_stop_width.json`

## exp-20260511-111 Space data-vendor trend target

- timestamp: 2026-05-11T22:18:26+00:00
- lane: alpha_search
- decision: rejected_data_vendor_trend_target_extension
- changed_variable: space_data_vendor_trend_target_atr_mult
- best_variant: data_vendor_trend_target_6_0
- expected_value_score_delta_vs_before: -0.3228
- pnl_delta_vs_before: $-13,201.24
- interpretation: PL/BKSY data-vendor trend target widening damaged old_thin and did nothing in late_strong or mid_weak. Keep PL/BKSY trend targets at the accepted broad 5 ATR Space trend setting; do not retry nearby data-vendor trend target widths on the frozen snapshots.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260511-111\space_data_vendor_trend_target.json`

## exp-20260511-112 SEC financial-report T+1 paper sleeve capacity

- timestamp: 2026-05-11T22:24:41+00:00
- lane: alpha_search
- decision: accept_default_off_paper_capacity_candidate
- changed_variable: sec_financial_report_event_sleeve_max_positions
- baseline_max_positions: 1
- promoted_default_max_positions: 3
- expected_value_score_delta: +0.174785
- sleeve_pnl_delta: +$6,351.95
- total_pnl_delta: +$6,766.07
- before_aggregate: {'expected_value_score_sum': 6.414058, 'total_pnl_sum': 187675.61, 'trade_count_sum': 88, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.092599, 'sleeve_total_pnl_sum': 2204.51, 'sleeve_closed_trade_count_sum': 26}
- after_aggregate: {'expected_value_score_sum': 6.588843, 'total_pnl_sum': 194441.68, 'trade_count_sum': 124, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.118812, 'sleeve_total_pnl_sum': 8556.46, 'sleeve_closed_trade_count_sum': 62}
- interpretation: The SEC financial-report positive T+1 queue supports a larger default-off paper observation capacity, but not full max=5/10 capacity because old_thin drawdown rises too much. Promote max=3 only for paper observation; keep live orders disabled.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': False, 'alters_sizing': False}
- artifact: `data\experiments\exp-20260511-112\exp_20260511_112_sec_financial_report_t1_sleeve_capacity.json`

## exp-20260512-001 SEC financial-report T+1 excess floor

- timestamp: 2026-05-12T00:08:20+00:00
- lane: alpha_search
- decision: accepted_default_off_t1_excess_floor
- changed_variable: sec_financial_report_t1_excess_return_floor
- promoted_floor: 0.01 ticker-vs-SPY T+1 excess return
- expected_value_score_delta: +0.820356
- total_pnl_delta: +$15,448.11
- sleeve_pnl_delta: +$15,448.11
- before_aggregate: {'expected_value_score_sum': 6.588843, 'total_pnl_sum': 194441.68, 'trade_count_sum': 124, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.118812, 'sleeve_total_pnl_sum': 8556.46, 'sleeve_closed_trade_count_sum': 62}
- after_aggregate: {'expected_value_score_sum': 7.409199, 'total_pnl_sum': 209889.79, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.090703, 'sleeve_total_pnl_sum': 24004.57, 'sleeve_closed_trade_count_sum': 52}
- interpretation: The SEC financial-report positive T+1 queue should require at least +1% ticker-vs-SPY T+1 excess before entering the default-off paper sleeve. This improved EV and PnL in all three canonical windows while reducing max drawdown and keeping 52 closed sleeve trades.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': True, 'alters_sizing': False}
- artifact: `data\experiments\exp-20260512-001\exp_20260512_001_sec_financial_report_t1_excess_floor.json`

## exp-20260512-004 Space perfect-TQS risk

- timestamp: 2026-05-12T01:31:38+00:00
- lane: alpha_search
- decision: accepted_default_off_space_perfect_tqs_risk
- changed_variable: space_perfect_trade_quality_score_risk_scalar
- best_space_perfect_tqs_risk_scalar: 1.5
- expected_value_score_delta_vs_before: +1.2496
- total_pnl_delta_vs_before: +$26,296.52
- before_aggregate: {'expected_value_score_sum': 10.2590, 'total_pnl_sum': 261960.17, 'trade_count_sum': 73, 'min_survival_rate': 0.8070, 'max_drawdown_pct_max': 0.1056}
- after_aggregate: {'expected_value_score_sum': 11.5086, 'total_pnl_sum': 288256.69, 'trade_count_sum': 72, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1056}
- interpretation: Space optimization should now prioritize signal-quality-conditioned risk allocation. The accepted perfect-TQS 1.5x top-up remains default-off metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-004\space_perfect_tqs_risk.json`

## exp-20260512-002 SEC financial-report hold days

- timestamp: 2026-05-12T01:06:19+00:00
- lane: alpha_search
- decision: rejected_hold_days
- changed_variable: sec_financial_report_event_sleeve_hold_days
- best_hold_days: 12
- expected_value_score_delta: -0.126504
- total_pnl_delta: -$2,705.41
- sleeve_pnl_delta: -$2,481.89
- before_aggregate: {'expected_value_score_sum': 7.409199, 'total_pnl_sum': 209889.79, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.090703, 'sleeve_total_pnl_sum': 24004.57, 'sleeve_closed_trade_count_sum': 52}
- after_aggregate: {'expected_value_score_sum': 7.282695, 'total_pnl_sum': 207184.38, 'trade_count_sum': 106, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.089763, 'sleeve_total_pnl_sum': 21522.68, 'sleeve_closed_trade_count_sum': 44}
- interpretation: Keep the accepted 10-trading-day SEC financial-report paper sleeve hold. Shorter/later fixed holds did not beat the accepted max-3 plus 1% T+1 excess setup across the three canonical windows.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': False, 'alters_sizing': False, 'alters_exit_lifecycle': True}
- artifact: `data\experiments\exp-20260512-002\exp_20260512_002_sec_financial_report_hold_days.json`

## exp-20260512-006 SEC financial-report event notional

- timestamp: 2026-05-12T02:24:05Z
- lane: alpha_search
- decision: accepted_default_off_event_notional_15000
- changed_variable: sec_financial_report_event_sleeve_event_notional_usd
- promoted default: $15,000 per default-off paper event, with max_positions=3, T+1 excess >= 1%, and 10-trading-day hold unchanged.
- expected_value_score_delta: +0.505389
- total_pnl_delta: +$12,237.07
- before_aggregate: {'expected_value_score_sum': 7.409199, 'total_pnl_sum': 209889.79, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.090703, 'sleeve_total_pnl_sum': 24004.57, 'sleeve_closed_trade_count_sum': 52}
- after_aggregate: {'expected_value_score_sum': 7.914588, 'total_pnl_sum': 222126.86, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.093657, 'sleeve_total_pnl_sum': 36006.85, 'sleeve_closed_trade_count_sum': 52}
- interpretation: After the accepted event-quality floor, the SEC financial-report T+1 sleeve can carry a larger default-off paper budget. This is risk allocation, not candidate expansion: no live orders, candidate ranking, hold period, or queue filter changed.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': False, 'alters_candidate_ranking': False, 'alters_sizing': True}
- artifact: `data\experiments\exp-20260512-006\exp_20260512_006_sec_financial_report_event_notional.json`

## exp-20260512-008 Space near-perfect TQS trend risk

- timestamp: 2026-05-12T03:24:26Z
- lane: alpha_search
- decision: accepted_default_off_space_near_perfect_tqs_trend_risk
- changed_variable: space_near_perfect_tqs_trend_risk_scalar
- best scalar: 1.10 for official Space `trend_long` signals with `0.95 <= trade_quality_score < 1.0`, on top of the accepted exp-20260512-004 Space stack.
- expected_value_score_delta: +0.2392
- total_pnl_delta: +$5,210.37
- window evidence: EV and PnL improved in all three canonical Space augmented windows: `late_strong +0.0971` EV / `+$2,048.33`, `mid_weak +0.1270` EV / `+$2,317.91`, and `old_thin +0.0151` EV / `+$844.13`.
- interpretation: Space optimization should stay in signal-quality-conditioned risk allocation. The accepted near-perfect TQS trend top-up remains default-off metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-008\space_near_perfect_tqs_trend_risk.json`

## exp-20260512-010 Space near-perfect TQS breakout risk

- timestamp: 2026-05-12T05:44:12Z
- lane: alpha_search
- decision: rejected_space_near_perfect_tqs_breakout_risk
- changed_variable: space_near_perfect_tqs_breakout_risk_scalar
- best scalar: 0.25 for official Space `breakout_long` signals with `0.95 <= trade_quality_score < 1.0`, on top of the accepted exp-20260512-008 Space stack.
- expected_value_score_delta: +0.2498
- total_pnl_delta: +$3,033.22
- window evidence: only `mid_weak` improved (`+0.2498` EV / `+$3,033.22`); `late_strong` and `old_thin` were unchanged, so Gate 4 failed with only one improved window.
- interpretation: near-perfect TQS is useful for Space trend risk, but it is not a robust Space breakout discriminator. Do not add a separate high-TQS breakout scalar on these frozen snapshots.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-010\space_near_perfect_tqs_breakout_risk.json`

## exp-20260512-007 SEC financial-report periodic-report notional

- timestamp: 2026-05-12T03:15:31Z
- lane: alpha_search
- decision: accepted_default_off_periodic_report_notional_1.25x
- changed_variable: sec_financial_report_periodic_report_notional_scalar
- promoted default: `periodic_report` rows use `1.25x` of the accepted `$15,000` base paper notional; `earnings_8k` stays at `1.0x`.
- expected_value_score_delta: +0.190856
- total_pnl_delta: +$3,408.57
- before_aggregate: {'expected_value_score_sum': 7.914587, 'total_pnl_sum': 222126.86, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.093657, 'sleeve_total_pnl_sum': 36006.85, 'sleeve_closed_trade_count_sum': 52}
- after_aggregate: {'expected_value_score_sum': 8.105443, 'total_pnl_sum': 225535.43, 'trade_count_sum': 114, 'min_survival_rate': 0.792453, 'max_drawdown_pct_max': 0.096499, 'sleeve_total_pnl_sum': 39337.77, 'sleeve_closed_trade_count_sum': 52}
- interpretation: Semantic event-family risk allocation improved the default-off SEC financial-report T+1 sleeve after the accepted $15k base budget. This changes no live orders, queue qualification, ranking, capacity, or hold period.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': False, 'parity_test_added': True, 'default_off_paper_only': True, 'alters_orders': False, 'alters_signal_generation': False, 'alters_candidate_ranking': False, 'alters_sizing': True}
- artifact: `data\experiments\exp-20260512-007\exp_20260512_007_sec_financial_report_periodic_notional.json`

## exp-20260512-013 Space peer-nonleader breakout risk

- timestamp: 2026-05-12T06:37:30+00:00
- lane: alpha_search
- decision: accepted_default_off_space_peer_nonleader_breakout_risk
- changed_variable: space_peer_nonleader_breakout_risk_scalar
- best scalar: 0.00 for official Space `breakout_long` signals whose own 20d momentum is not above the official Space basket average, on top of the accepted exp-20260512-008 Space stack.
- expected_value_score_delta: +0.3297
- total_pnl_delta: +$4,209.46
- window evidence: `late_strong +0.0180` EV / `+$375.38`, `mid_weak +0.3117` EV / `+$3,834.08`, and `old_thin unchanged`; no window regressed.
- interpretation: Space breakout work has a stronger ex-ante peer-leadership discriminator than the rejected near-perfect TQS breakout scalar. Nonleader breakouts should be zero-risk in the default-off Space forward stack; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-013\space_peer_nonleader_breakout_risk.json`

## exp-20260512-031 Space IWM-relative momentum risk

- timestamp: 2026-05-12T12:30:02+00:00
- lane: alpha_search
- decision: accepted_default_off_space_iwm_relative_momentum_risk
- changed_variable: space_iwm_relative_leader_risk_scalar
- best scalar: `1.10x` for official Space signals when IWM 20d momentum is above SPY 20d momentum, on top of the accepted exp-20260512-013 Space stack.
- expected_value_score_delta: +0.4142
- total_pnl_delta: +$9,550.74
- window evidence: EV and PnL improved in all three Space augmented windows: `late_strong +0.1072` EV / `+$2,267.34`, `mid_weak +0.2138` EV / `+$3,541.68`, and `old_thin +0.0932` EV / `+$3,741.72`.
- interpretation: Space official-catalyst risk should modestly scale up when small caps lead the broad tape. This is default-off observation-slot metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-031\space_iwm_relative_momentum_risk.json`

## exp-20260512-032 Space launch/lunar theme-segment risk

- timestamp: 2026-05-12T13:27:47+00:00
- lane: alpha_search
- decision: accepted_default_off_space_launch_lunar_theme_risk
- changed_variable: space_launch_lunar_theme_segment_risk_scalar
- best scalar: `1.10x` for official Space signals whose production universe-registry `theme_segment` is `launch_lunar`, on top of the accepted exp-20260512-031 Space stack.
- expected_value_score_delta: +0.2404
- total_pnl_delta: +$5,233.68
- window evidence: EV and PnL improved in all three Space augmented windows: `late_strong +0.1048` EV / `+$2,447.13`, `mid_weak +0.1227` EV / `+$2,092.83`, and `old_thin +0.0129` EV / `+$693.72`.
- interpretation: Space official-catalyst risk has a modest production-visible launch/lunar bucket edge that survived the three-window gate. This is default-off observation-slot metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-032\space_launch_lunar_theme_risk.json`

## exp-20260512-035 Space data/defense theme-segment risk

- timestamp: 2026-05-12T14:33:05+00:00
- lane: alpha_search
- decision: rejected_space_data_defense_theme_risk
- changed_variable: space_data_defense_theme_segment_risk_scalar
- best scalar: `1.25x` for official Space signals whose production universe-registry `theme_segment` is `space_data_defense`, on top of the accepted exp-20260512-032 Space stack.
- expected_value_score_delta: +0.1986
- total_pnl_delta: +$8,204.94
- before_aggregate: {'expected_value_score_sum': 12.7321, 'total_pnl_sum': 312460.94, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1128}
- after_aggregate: {'expected_value_score_sum': 12.9307, 'total_pnl_sum': 320665.88, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1191}
- window evidence: only `old_thin` improved (`+0.2051` EV / `+$8,350.90`); `mid_weak` regressed (`-0.0065` EV / `$-145.96`) and `late_strong` was unchanged. Max drawdown worsened by `0.63` percentage points, above the gate guardrail.
- interpretation: Space data/defense bucket scaling is old-window concentrated and does not survive the accepted three-window Space gate. Do not retry adjacent BKSY/PL/RDW data/defense theme scalars on these frozen snapshots.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-035\space_data_defense_theme_risk.json`

## exp-20260512-038 Space official customer-source risk

- timestamp: 2026-05-12T16:01:19+00:00
- lane: alpha_search
- decision: accepted_default_off_space_official_customer_source_risk
- changed_variable: space_official_customer_source_risk_scalar
- best scalar: `1.10x` for official Space signals whose production event seed profile has `customer_win` from official/regulatory/company primary sources, on top of the accepted exp-20260512-037 liquidity-tier stack.
- expected_value_score_delta: +0.5354
- total_pnl_delta: +$10,864.99
- before_aggregate: {'expected_value_score_sum': 12.9711, 'total_pnl_sum': 318249.96, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1161}
- after_aggregate: {'expected_value_score_sum': 13.5065, 'total_pnl_sum': 329114.95, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1197}
- window evidence: EV and PnL improved in all three Space augmented windows: `late_strong +0.1156` EV / `+$2,965.84`, `mid_weak +0.4107` EV / `+$7,037.53`, and `old_thin +0.0091` EV / `+$861.62`.
- interpretation: Space catalyst-quality allocation should prefer source-qualified customer-win events over another local theme/ticker scalar. This remains shared default-off observation metadata/helper only; live Space slots remain zero.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-038\space_official_customer_source_risk.json`

## exp-20260512-040 Space defense-budget source risk

- timestamp: 2026-05-12T16:32:04+00:00
- lane: alpha_search
- decision: rejected_space_defense_budget_source_risk
- changed_variable: space_defense_budget_source_risk_scalar
- best scalar: `1.25x` for official Space signals whose event seed profile has `defense_budget_theme` + `government_space_contract` from `official_government_release`, on top of the accepted exp-20260512-038 customer-source stack.
- expected_value_score_delta: +2.3678
- total_pnl_delta: +$52,220.36
- before_aggregate: {'expected_value_score_sum': 13.5065, 'total_pnl_sum': 329114.95, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1197}
- after_aggregate: {'expected_value_score_sum': 15.8743, 'total_pnl_sum': 381335.31, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1351}
- window evidence: EV and PnL improved in all three Space augmented windows, but max drawdown drift exceeded the Gate 4 guardrail: `1.10x` already worsened max drawdown by `0.62` percentage points and `1.25x` by `1.54` percentage points.
- interpretation: broad official defense-budget source exposure behaves like a high-beta Space exposure amplifier, not a safe catalyst-quality discriminator. Do not retry adjacent defense-budget/government-contract source scalars on these frozen snapshots.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-040\space_defense_budget_source_risk.json`

## exp-20260512-041 Space financing/dilution profile risk

- timestamp: 2026-05-12T16:43:03+00:00
- lane: alpha_search
- decision: accepted_default_off_space_financing_dilution_profile_risk
- changed_variable: space_financing_dilution_event_guard_profile_risk_scalar
- best scalar: `1.075x` for official Space signals whose production registry `event_guard_profile` contains `financing` or `dilution`, on top of the accepted exp-20260512-038 customer-source stack.
- expected_value_score_delta: +0.5022
- total_pnl_delta: +$11,012.31
- before_aggregate: {'expected_value_score_sum': 13.5065, 'total_pnl_sum': 329114.95, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1197}
- after_aggregate: {'expected_value_score_sum': 14.0087, 'total_pnl_sum': 340127.26, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1243}
- window evidence: EV and PnL improved in all three Space augmented windows: `late_strong +0.0915` EV / `+$2,463.78`, `mid_weak +0.3582` EV / `+$6,053.43`, and `old_thin +0.0525` EV / `+$2,495.10`. Max drawdown drift was `+0.46` percentage points, inside the Gate 4 guardrail.
- interpretation: production registry event-guard profile terms are a usable Space catalyst-quality allocation field when sized conservatively. `1.10x` had higher raw EV but failed drawdown; keep `1.075x` and do not retry adjacent financing/dilution profile scalars on these frozen snapshots.
- production_impact: {'shared_policy_changed': True, 'backtester_adapter_changed': False, 'run_adapter_changed': True, 'replay_only': True, 'parity_test_added': True, 'daily_report_metadata_changed': True, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-041\space_financing_dilution_profile_risk.json`

## exp-20260512-043 Space mission-binary profile risk

- timestamp: 2026-05-12T17:41:41+00:00
- lane: alpha_search
- decision: rejected_space_mission_binary_profile_risk
- changed_variable: space_mission_binary_event_guard_profile_risk_scalar
- best scalar: `0.50x`, but all tested scalars from `0.50x` through `1.25x` produced zero EV/PnL delta versus the accepted exp-20260512-041 Space stack.
- expected_value_score_delta: +0.0000
- total_pnl_delta: +$0.00
- before_aggregate: {'expected_value_score_sum': 14.0087, 'total_pnl_sum': 340127.26, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1243}
- after_aggregate: {'expected_value_score_sum': 14.0087, 'total_pnl_sum': 340127.26, 'trade_count_sum': 70, 'min_survival_rate': 0.7746, 'max_drawdown_pct_max': 0.1243}
- window evidence: `mission_binary` matched only `LUNR` and adjusted just 2 signals; neither adjusted signal changed executed shares enough to move any of the three fixed windows.
- interpretation: mission-binary registry profile is not a material Space risk-allocation alpha on the frozen Space replay. Do not retry adjacent mission-binary profile scalars without forward replacement-value evidence or a different production-observable catalyst field.
- production_impact: {'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'daily_report_metadata_changed': False, 'live_slots_changed': False, 'live_slots': 0}
- artifact: `data\experiments\exp-20260512-043\space_mission_binary_profile_risk.json`

Latest core state-allocation alpha search: `exp-20260512-106` and
`exp-20260512-107` tested signal-day sector-proxy tape as a production-knowable
risk allocation state. The adverse-tape 0.5x haircut failed Gate 4 with
aggregate EV `-0.0251` and PnL `-$1,901.95`; it only improved `mid_weak` and
regressed `old_thin`. The positive-tape 1.10x top-up was directionally positive
but underpowered, with aggregate EV `+0.0140` and PnL `+$820.26`, improving only
`old_thin`. No shared policy was promoted. Do not retry fixed +/-1% signal-day
sector-tape scalars without forward attribution or a stronger state
discriminator.

Latest Form 4 alpha search: `exp-20260512-108` tested a PIT-safe 5-trading-day
pre-entry relative-strength confirmation on top of the latest single-owner
Form 4 forward-queue replay. The confirmed slice stayed positive versus core
(`aggregate EV +0.2115`, PnL `+$4,014.97`, no core EV regression), but it
regressed the single-owner baseline in all three windows (`aggregate EV
-0.1074`, PnL `-$1,900.00`) and left only 5 selected event trades, below the
sample guard. No shared policy or production adapter was changed. Keep Form 4
in forward observation and do not add pre-entry RS qualification to the frozen
single-owner queue without new forward replacement-value evidence.

Latest core breakout alpha search: `exp-20260513-001` tested a cap-aware risk
scalar for already-qualified `breakout_long` signals whose existing
`conditions_met.volume_spike_ratio > 2.0`. The best scalar was only `1.05x`,
with aggregate EV `+0.0002` and PnL `+$2.62`; it improved only `mid_weak` and
left `late_strong` / `old_thin` unchanged. No shared sizing policy was promoted.
Do not retry fixed core breakout strong-volume scalars on these frozen windows
without forward breakout volume-bucket attribution or a stronger orthogonal
entry-quality state.

Latest rejected core state-allocation alpha search: `exp-20260513-013` tested
whether the previously rejected broad momentum-acceleration top-up becomes
robust when restricted to signals that also have the accepted signal-day own
green candle. The best scalar was `1.25x`: aggregate EV improved `+0.0869` and
PnL improved `+$1,344.23`, but `old_thin` still regressed by EV `-0.0080` /
PnL `-$387.79`, so Gate 4 failed and no shared policy was promoted. Do not
retry adjacent core momentum-acceleration scalars on these frozen windows
without a materially different production-visible discriminator.

Latest rejected core setup-quality alpha search: `exp-20260513-016` tested a
cap-aware risk top-up for core `trend_long` / `breakout_long` signals with
near-perfect `trade_quality_score >= 0.95`. The best scalar was `1.20x`:
aggregate EV improved `+0.0376` and PnL improved `+$4,016.23`, but `old_thin`
EV regressed slightly and the max drawdown ceiling worsened by `+1.42`
percentage points, failing Gate 4. Do not promote or retry broad high-TQS core
sizing on the frozen windows without a narrower production-visible
discriminator or forward setup-quality attribution.

Latest rejected core stacked-quality alpha search: `exp-20260513-018` tested
whether the already accepted own-green candle and RS20 leader states become
promotion-grade when stacked with high setup quality. The best scalar was a
confirmed-quality `1.20x` top-up, but aggregate EV improved only `+0.0534`
and PnL `+$4,540.10` while the edge stayed old-window concentrated and failed
the multi-window gate. Do not stack own-green, RS20, and near-perfect
setup-quality multipliers on the frozen core windows without forward
setup-quality attribution showing this state is not just local overfit.

Latest rejected index ETF lifecycle alpha search: `exp-20260513-017` tested
whether `QQQ` / `SPY` / `IWM` should receive a separate wider target-width pool
after a live QQQ `SIGNAL_TARGET` felt early. The sweep changed only the index
ETF target ATR multiple (`5.0x`, `6.0x`, `7.0x`) and left entries, ranking,
sizing, universe, LLM/news, and hard stops unchanged. The best variant was
`5.0x`: aggregate EV fell `-0.1030` / `-1.62%` and PnL fell `-$2,267.28` /
`-1.21%`; the only changed trade was `IWM` in `mid_weak`, where delaying the
target exit reduced PnL from `$4,783.80` to `$2,513.69`. Do not split broad
index ETFs into a promoted target pool without forward target-touch evidence
or a narrower state-conditioned lifecycle discriminator.

Latest rejected core slot-priority alpha search: `exp-20260513-027` tested
whether the accepted signal-day own-green state should also rank ahead of
non-green candidates during same-day slot slicing. The scout changed only the
slot ordering after existing filters, sizing, and scarce-slot breakout
deferral; it did not change entry logic, sizing, exits, universe, LLM/news, or
add-ons. Gate 4 failed: aggregate EV fell `-2.2683` and PnL fell
`-$40,404.08`, entirely from `late_strong`, where replacing GLD/IAU exposure
with green IWM/AMD and later META materially hurt results. Keep own-green as
the accepted small sizing helper, not as a slot-priority ranking key, unless
forward collision evidence changes the prior.

Latest rejected core clean-leader refinement: `exp-20260513-038` tested an
extra cap-aware top-up only for already accepted clean SPY-relative leader
signal-day winners whose existing stop had at least the 2% gap cushion. No
entry, ranking, exit, target, universe, LLM/news, or production policy changed.
Gate 4 failed: best `1.025x` moved aggregate EV `-0.0002` while adding
`$589.77` PnL, improved only `old_thin`, and regressed `late_strong`. Do not
promote or keep retuning clean-leader execution-cushion overlays on the frozen
windows without forward evidence or a genuinely independent state variable.

Latest rejected core clean-leader non-confirmation search: `exp-20260513-109`
tested a post-sizing risk haircut for already clean risk-on SPY-relative
leaders whose signal-day ticker return did not beat SPY. The best `0.90x`
variant improved `mid_weak` and `old_thin` EV by only `+0.0006` combined, but
regressed `late_strong` by `-0.0791` EV and cut aggregate PnL by `$2,006.90`.
Keep signal-day SPY outperformance as the accepted positive-confirmation top-up
only; do not add the mirror-image haircut without forward evidence.

Latest Space alpha search: `exp-20260513-020` tested a Space `trend_long`
risk scalar conditioned on both IWM 20d momentum beating SPY and the ticker's
20d momentum beating the official Space basket average, on top of the accepted
`exp-20260513-015` Space stack. The accepted scalar is `1.15x`. Aggregate EV
improved `+0.7810` to `17.6697` and PnL improved `+$17,229.17` to
`$421,418.99`, with no EV-regressed window. `mid_weak` improved `+0.6377` EV /
`+$10,980.05`, `old_thin` improved `+0.1433` EV / `+$6,249.12`, and
`late_strong` was unchanged. Max drawdown drift was `+0.44` percentage points,
inside the Gate 4 guardrail; min survival stayed `70.42%`, well above the
guardrail. Promote only as shared default-off Space
metadata/helper; live Space slots remain zero.

Latest rejected Space peer-bucket alpha search: `exp-20260513-019` tested
whether the accepted customer-source edge should also top up peer-nonleader
official Space signals. Aggregate EV improved `+0.1320`, but the result did
not clear the Space three-window gate, so customer-source allocation should
stay tied to stronger peer-quality buckets. Do not promote customer-source
peer-nonleader scaling on the frozen snapshots; the next valid Space step is
forward replacement value by catalyst family/source/peer bucket or a genuinely
new production-visible official catalyst-quality field.

Latest rejected Space lifecycle alpha search: `exp-20260513-026` tested
whether the accepted IWM-plus-peer-leader `trend_long` state should also get a
wider target ATR floor. The best 8 ATR floor raised aggregate EV by `+0.4165`
but cut aggregate PnL by `$21,220.04`, improved only `mid_weak`, and regressed
`old_thin` by `-1.1259` EV / `-$42,518.52` with max drawdown worsening to
`19.68%`. Keep the accepted exp020 state as a sizing helper, not a lifecycle
target-width rule, until forward target-touch evidence exists.
