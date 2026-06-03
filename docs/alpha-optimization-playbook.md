# Alpha Optimization Playbook

Last refreshed: 2026-06-03.

This is Ginger's long-lived alpha research playbook. It is not an experiment
log and should not repeat every trial. Detailed records belong in
`docs/experiment_log.jsonl`, `experiments/logs/*.json`, and the experiment
artifacts. This file keeps only durable mechanism-level lessons, anti-repeat
rules, and the next research queues that are most likely to improve
`expected_value_score = total_return_pct * sharpe_daily`.

## Operating Rules

Before any strategy change, answer five questions:

1. What is the alpha hypothesis, and is it entry, exit, ranking, capital
   allocation, candidate-pool, LLM event scoring, or risk allocation?
2. Has the same or adjacent trial family been tried before? What failed?
3. What is the single causal variable changed this time?
4. What is the Gate 1-4 acceptance standard from `docs/backtesting.md`?
5. If it fails, can the next agent reproduce it from repository records?

Default priority:

1. Prefer `alpha_search` unless a measurement gap directly blocks a high-value
   alpha test.
2. Prefer new production-visible fields over another threshold/scalar sweep.
3. Prefer default-off paper sleeves before core/live expansion.
4. Prefer replacement value and concentration evidence over standalone PnL.
5. Prefer shared production/backtest policy over replay-only cleverness.

## One-Page Readout

The system's strongest current pattern is not "more filters." It is:

- use broad, cheap, production-visible candidate-pool sources;
- convert them into default-off paper adapters;
- collect closed forward rows with replacement-value and concentration
  accounting;
- only then consider live sleeve activation.

Recent repository evidence supports this priority:

- `FUNDAMENTAL_GROWTH_RS_PAPER` is the current best candidate-pool lead:
  Companyfacts growth + positive operating-profit quality + OHLCV RS produced a
  large three-window paper improvement, then became a shared default-off adapter.
  Accepted low-volume, filing-recency, low-liability balance-sheet,
  filing-timeliness, cost-liquidity, and sector-residual strength support
  improved the shared default-off paper adapter. The latest accepted increment
  is `exp-20260602-010`: already-selected candidates get a `1.05x` default-off
  paper scalar only when their signal-date 20-day return beats the persisted
  public-sector median by at least `3pp` with at least `5` sector-member return
  observations. The sleeve is now mature enough that nearby frozen-sample
  Companyfacts scalar, threshold, and sector-residual retunes should stop;
  collect forward replacement-value rows or find a materially new free-data
  field first.
- The accepted post-earnings continuation repair changed the core baseline,
  but not the default rule for earnings alpha. `exp-20260602-003` made the
  same-day post-event state explicit and PIT-safe: use the just-released event
  only after actual EPS is known and a later future earnings date exists, then
  roll DTE to that next event. This recovered aggregate core EV `6.3596 ->
  7.8941` and PnL `$192,538.61 -> $234,850.99`. Nearby post-earnings candidate
  pools split: `exp-20260602-004` rejected the generic strong-reaction pool,
  while `exp-20260602-023` found that positive-surprise post-earnings drift
  rows whose pre-event 20-day ticker return did not outperform SPY were cleaner.
  `exp-20260602-026` promoted that lead into the shared default-off
  `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` adapter; the shared-helper replay
  improved all three canonical windows with aggregate EV `+0.3547`, PnL
  `+$3,557.15`, `20` target paper trades, no drawdown worsening, max single
  positive share `0.308744`, and positive PnL HHI `0.192948`.
  `exp-20260602-027` then added one shared free-OHLCV support field on top of
  the same adapter: already-selected candidates with signal-date
  `avg_dollar_volume_20d >= $1B` receive `1.10x` default-off paper notional.
  The combined shared adapter improved all three canonical windows versus core
  by aggregate EV `+0.4116` and PnL `+$4,058.33`; the support slice adjusted
  `13` paper trades across all windows and added `+$501.18` incremental paper
  PnL over exp026. `exp-20260603-004` then accepted one materially different
  free-data event-quality support field: already-selected candidates whose
  signal-date 20-day return is at least the public-sector median, with at
  least `3` same-sector return observations, receive an additional `1.05x`
  default-off paper scalar. Compared with the exp027 after-metrics baseline,
  all three canonical windows improved, but only marginally (`EV +0.0082`,
  PnL `+$199.95`, `16` supported trades). Retain it for forward observation;
  do not mine nearby post-earnings sector-residual thresholds, min-member
  counts, or scalar values on the frozen windows. The next valid earnings work
  is forward replacement-value accumulation or a materially richer
  event-quality field, not implicit DTE resets, generic PEAD/pre-earnings
  threshold sweeps, nearby `pre_event_rs20_vs_spy` retunes, or post-earnings
  high-liquidity/sector-residual threshold/scalar retunes.
- `VOLUME_BREADTH_BREAKOUT_PAPER` and QQQ-confirmed VCP show that free OHLCV
  market-confirmation fields can produce useful paper sleeves. Their next step
  is forward maturation, not another breadth/QQQ/top-N sweep. The latest
  accepted VBB increment is cost/liquidity support
  (`dollar_volume >= $200m` and signal-day range/close `<= 0.10`, `1.05x`);
  this reinforces that cheap execution state belongs in the field layer before
  allocation, not as an after-the-fact PnL adjustment.
- `FINRA_IWM_CONFIRMED_PAPER` is the newest accepted free-data candidate-pool
  adapter. The raw short-pressure breakout plus IWM confirmation (`exp-20260530-005`)
  had useful three-window evidence but failed concentration by a narrow margin;
  adding a seven-calendar-day same-ticker admitted-candidate cooldown
  (`exp-20260530-007`) reduced concentration and passed the paper gate, then
  `exp-20260530-010` promoted the route into a shared default-off forward
  adapter. `exp-20260601-029` added the only retained support increment so far:
  `1.05x` paper notional when selected FINRA/IWM candidates have signal-day
  `dollar_volume >= $200m` and `(high-low)/close <= 0.10`, improving all three
  canonical windows by `+0.0072` EV / `+$314.56`. `exp-20260603-006` then
  found one stronger replay lead, not yet a shared adapter: require the latest
  PIT-safe FINRA row to have `days_to_cover >= 3.0` and positive
  `short_interest_change_pct` before admitting the accepted FINRA/IWM/cooldown
  candidate. This improved all three canonical windows by aggregate EV
  `+0.2585` and PnL `+$5,688.12` with `22` target trades and concentration
  inside guardrails. Treat it like Fundamental Growth RS and VBB: the next
  valid step is a shared default-off adapter plus parity tests and forward
  replacement rows, not FINRA score / IWM threshold / cooldown / top-N / hold /
  cost-liquidity threshold/scalar or nearby `days_to_cover` /
  `short_interest_change_pct` threshold retunes on the same frozen windows.
- Full-universe ranking is promising as attribution, and now has one
  default-off paper queue. Raw `alpha_score` remains unsuitable for live/core
  ranking, but the market-regime-gated safe-notional route passed Gate 4 and
  was promoted into a shared observation adapter.
  `exp-20260531-005` showed a top-1 `alpha_score` candidate pool can produce
  large aggregate historical paper gains, but it failed promotion because the
  ladder was not robust enough for a live-facing source. The follow-up
  full-universe quantile attribution (`exp-20260531-006`) found a small pooled
  top-vs-bottom 5d edge (`+0.556 pp`) across `3,551` observations and `2/3`
  positive windows, but no clean monotonic quintile ladder. `exp-20260601-003`
  decomposed that edge by component (with a relative_strength double-sort
  control) and found it is essentially `relative_strength` only -- but on the
  same narrow 52-name curated, momentum-homogeneous watchlist.
  `exp-20260601-006` re-ran both on the broad 1,446-ticker
  all-windows-full-liquid warehouse universe (`96,833` observations) and the
  edge SHRANK when the universe broadened, the opposite of a generalizable
  alpha: composite 5d spread `+0.21 pp` (below the `0.5 pp` floor),
  relative_strength `+0.34 pp` (also below floor), no component clears the bar,
  and the only positive composite window is `late_strong` (`1/3`). The
  universe-robust conclusion is that raw `alpha_score` has NO robust 5d
  cross-sectional forward-return edge; the narrow-watchlist edge was largely a
  curated-momentum-universe, single-regime artifact, and
  `expectation_revision` / `post_earnings_drift` are perfectly constant
  (unpopulated) on broad tickers. Do not propose `alpha_score` reweighting as a
  live ranking/sizing change; reviving the surface needs genuinely populated
  non-momentum components AND a per-regime robustness requirement. The accepted route is narrow: top-decile/top-1 with SPY above 50d,
  IWM 20d return at least SPY 20d return, 20-day hold, and `$4,000`
  default-off base paper notional only. `exp-20260531-025` added the only
  retained increment so far: `1.25x` default-off paper-notional support when
  the same ticker/signal date also appears in accepted FINRA/IWM or VBB paper
  sources. Treat this as a forward-evidence bucket, not permission to retune
  alpha_score thresholds, weights, top-N, hold, market gate, or notional.
  `exp-20260531-029` added a separate observe-only
  `ACCEPTED_SOURCE_CONSENSUS_PAPER` adapter for the fixed exp026 pool: accepted
  alpha-score market-regime rows are admitted only when accepted FINRA/IWM or
  VBB also selects the same ticker on the same signal date, with fixed `$4,000`
  paper notional and no extra source-consensus scalar. The next evidence is
  forward replacement value for that adapter, not another same-source overlap
  retune. `exp-20260531-030` found a broader source-agnostic variant: any two
  accepted free-data paper sleeves agreeing on the same ticker/date plus a
  seven-calendar-day same-ticker cooldown improved all three canonical windows
  (`EV +0.5103`, PnL `+$9,359.12`, `47` target trades) and passed concentration.
  `exp-20260601-001` rebuilt that fixed definition as the shared observe-only
  `ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER` adapter. After the PIT-DTE
  baseline was accepted, `exp-20260601-028` retained the prior
  core-capacity-available discriminator in that shared adapter: paper consensus
  candidates are admitted only when production-visible core capacity remains,
  improving current-baseline aggregate EV by `+1.1099` and PnL by
  `+$22,063.58` across all three windows. The next evidence is forward
  replacement value for this adapter, not source-count, source-set, cooldown,
  hold, notional, or nearby capacity retuning on the frozen windows.
- Space remains observe-only, but `exp-20260528-026` showed that a new
  production-visible OHLCV field (`daily_close_location >= 0.84` on
  governed Space `trend_long` signal days) can separate better paper
  candidates from old-window losers. `exp-20260529-020` added one incremental
  existing OHLCV field (`signal_day_ticker_open_close_return_pct >= 0.04`) on
  that accepted route, improving aggregate EV by `+0.0282` versus the
  high-close baseline by removing one weak-thrust stopout. `exp-20260531-022`
  added an ARKX>UFO relative-momentum metadata bucket for governed
  `breakout_long` high-close/thrust candidates, improving aggregate EV by
  `+0.0753` versus `exp-20260529-020` with one RKLB incremental trade.
  `exp-20260602-025` accepted the shared default-off Space cost/liquidity
  helper from the positive `exp-20260602-024` lead: already selected Space
  paper candidates get `1.05x` paper support only when signal-day dollar volume
  is at least `$100M` and signal-day range is at most `11%`; the three-window
  replay stayed positive versus core (`+0.8766` EV / `+$16,587.61`) and
  improved the accepted Space route by `+0.0226` EV / `+$466.41` with no
  EV/PnL-regressed windows. Treat these as forward evidence buckets, not
  permission to retune Space
  price-action or ETF thresholds or enable live Space slots.
- The 2026-05-28/29 candidate-pool scouts rejected VWAP reclaim, long-base
  breadth, industry-leadership high-close/no-core-overlap, sector/market
  breadth agreement, ticker accumulation-quality breakout, Form 4 role quality,
  and AI optical low-close support. The durable lesson is that "reasonable"
  OHLCV pattern names are not enough; new pools need either a clearly new
  production-visible information source or immediate replacement-value evidence.
  The 2026-06-01 broad-universe OHLCV scouts reinforce this: gap-up/hold/high-
  close (`exp-20260601-010`), stock-only governance on the same pattern
  (`exp-20260601-011`), and undercut/reclaim absorption (`exp-20260601-012`)
  all failed Gate 4. Do not keep renaming OHLCV price-shape patterns as new
  candidate pools unless the trial adds a new information-transfer, cost,
  liquidity, or replacement-value mechanism.
- Kova/CANSLIM-style intraday, base, pocket-pivot, distribution-day, 13F, and
  RS fields are useful context sidecars, but recent tests repeatedly failed to
  justify new gates, exits, pyramids, or notional scalars on the frozen sample.
  The one constructive lifecycle clue, early shakeout then reclaim in
  `exp-20260529-006`, was positive but only `7` trades, so it is forward
  monitoring context rather than a rule.
- Expectation/PEAD/residual-leadership work is still mostly attribution and
  measurement repair. The latest useful result is better PIT joins and ranking
  replacement attribution, not a promoted live rule. The 2026-05-31
  pre-earnings surprise/RS experiments were either outright negative or
  high-variance positive with a `late_strong` regression and drawdown breach;
  pre-earnings run-up needs richer expectation-quality fields or forward
  replacement rows, not another imminent-earnings threshold or hold-period
  sweep.
- Form 4 remains watchlist material, not a clean candidate-pool lead. The
  latest multi-filer / owner-count replay (`exp-20260530-011`) was positive
  versus core but failed replacement value versus the raw Form 4 queue,
  materiality, sample, window coverage, and concentration guards. Do not
  promote owner-count alone or retry adjacent Form 4 role/owner-count fields
  without forward replacement rows or a new ownership-intensity mechanism.
  The 2026-05-31 purchase-value-versus-liquidity scout did not change that
  prior.
- Same-ticker SEC event recurrence is now frozen as a standalone event-graph
  idea. Same-family bursts, first/follow-on recurrence, same-ticker
  cross-family transitions, small two-ticker bursts, sector-event breadth
  transfer, and exact-industry Item 2.02 peer transfer all failed to produce a
  promotable relation. Future event work must use a stronger relation source:
  characteristic-similarity peers, source overlap, theme propagation, or
  semantic fact/tone direction with audited retrieval traces.
- State-surface has too many accepted paper scalars. More nearby
  queue/profile/notional mining now requires a hard >10% aggregate EV lift or
  should be rolled back.

## Durable Repository Lessons

### Allocation Beats Filtering

Historically robust improvements have come from small allocation changes on
already-qualified trades, or from isolated paper sleeves, not broad new
filters. Broad filters and mirror-image punishments often reduce survival,
shift the sample, and fail out-of-window.

Keep:

- narrow post-sizing support on already-qualified signals;
- sleeve-level capital routing;
- risk allocation tied to a production-visible state;
- replacement-value accounting versus core, cash, and adjacent rank.

Avoid:

- new broad gates with no survival audit;
- slot reranking from a single attractive feature;
- mirror-image haircuts just because the positive version worked;
- exit retunes without shadow attribution.

### New Fields Beat New Scalars

A useful field explains a mechanism. A scalar usually exploits one frozen
sample. Good fields include:

- profitability quality, cash conversion, and filed-date-safe growth context;
- source credibility, disclosure quality, fact/tone gap, and event-family
  structure;
- market participation, breadth, cost/liquidity, and hidden-beta context;
- replacement-value, concentration, decay, and forward closed-outcome state.

If an idea needs many `if/else` exceptions, the field layer is probably not
good enough yet.

### Sleeves Are The Right Boundary

Default-off sleeves are the incubation path for:

- broad-market candidate pools;
- fundamental-growth/RS candidates;
- VCP and volume-breadth breakouts;
- SEC/event overlays;
- passive/index mechanics;
- Kova/CANSLIM context;
- AI infra, Space, and other thematic pilots.

Every sleeve must report:

- candidate definition and PIT availability;
- cash-relative and core-displacement replacement value;
- adjacent-rank comparison where available;
- concentration and top-contributor share;
- closed forward outcomes;
- kill-gate state and activation blockers.

### Replacement Value Is The Hard Promotion Test

Standalone paper PnL is not enough. Promotion evidence must show the sleeve is
better than cash and better than the core candidate or queue rank it displaces.
If uplift comes from one ticker, one sector, one theme, one source, or one
window, default answer is "observe longer."

### Exit Changes Need Extra Suspicion

Simple target widening, target splitting, fixed stop tightening, and
post-entry pattern exits have repeatedly damaged winners or shifted drawdown.
Exit work should start as fixed-entry oracle or shadow attribution, then become
a shared lifecycle policy only if the explanatory field is known before the
decision and passes Gate 1-4.

### LLM Belongs In The Audit Layer

LLM output should become schema-bound fields, not direct trading authority.
Good LLM responsibilities:

- event family and semantic subcategory;
- source credibility;
- factual direction versus tone direction;
- fact/tone disagreement;
- special call or unusual disclosure flags;
- segment/KPI revision direction;
- regulatory or policy exposure;
- manager attention/nonresponse buckets.

Bad LLM responsibilities:

- sizing;
- stop/target selection;
- slot priority;
- portfolio heat;
- bypassing hard filters;
- final order instruction.

## Current Research Queue

### 1. Forward Maturation Of Candidate-Pool Sleeves

Meta research currently ranks `production_visible_default_off_paper_adapter_for_candidate_pool_alpha`
as the highest-value strategy family. The right work is not more frozen-sample
tuning; it is forward maturity.

Do next:

- roll up closed forward outcomes for `FUNDAMENTAL_GROWTH_RS_PAPER`,
  `VOLUME_BREADTH_BREAKOUT_PAPER`, `FINRA_IWM_CONFIRMED_PAPER`,
  `ALPHA_SCORE_MARKET_REGIME_PAPER`, `ACCEPTED_SOURCE_CONSENSUS_PAPER`,
  `ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER`, QQQ-confirmed VCP, and
  broad-market paper;
- add cost-adjusted replacement value where spread/liquidity data is available;
- compare selected rows against same-day core candidates and adjacent paper
  ranks;
- expose activation blockers in `default_off_alpha_attribution`.

Do not do next:

- retune Companyfacts growth, RS percentile, top-N, hold days, or fixed notional
  on the same windows;
- retune VCP QQQ/SPY, ATR compression, pocket-pivot, base geometry, or
  distribution-day gates without new forward evidence;
- retune FINRA score, IWM/SPY confirmation threshold, same-ticker cooldown,
  top-N, hold day, or paper notional without forward rows or a stronger
  borrow-cost / availability field;
- promote paper sleeves into live capital only because historical paper PnL is
  large.

### 2. Fundamental Growth + RS

Mechanism: filed-date-safe Companyfacts growth plus positive operating-profit
and gross-margin quality plus OHLCV relative strength is a real candidate-pool
lead. The useful change was not "another fundamental filter"; it was a new
default-off candidate source with a closed-ledger governor for
concentration/drawdown. `exp-20260601-026` accepted the gross-margin quality
candidate source after the PIT-DTE baseline repair: EV `6.3596 -> 12.6985` and
PnL `$192,538.61 -> $300,134.87`, with all three windows improved.
`exp-20260601-027` accepted the next orthogonal Companyfacts support field:
operating-income filings made within `45` days of quarter end or `75` days of
annual period end receive a `1.05x` default-off paper-notional scalar. It
improved the gross-margin adapter EV `12.6985 -> 13.0745` and PnL
`$300,134.87 -> $305,514.70`, with all three windows improved.
`exp-20260601-030` accepted a production-visible Companyfacts/OHLCV
cost-liquidity support field: already-selected candidates with signal-day
`avg_dollar_volume_20 >= $200m` and `(high-low)/close <= 0.10` receive a
`1.05x` default-off paper-notional scalar. It improved the accepted
filing-timeliness adapter EV `13.0745 -> 13.4753` and PnL
`$305,514.70 -> $311,052.25`, with all three windows improved.
`exp-20260602-010` accepted the next genuinely orthogonal support field:
already-selected candidates whose signal-date 20-day return beats the
persisted public-sector median by at least `3pp` with at least `5`
sector-member observations receive a `1.05x` default-off scalar. It improved
the shared adapter EV `15.7099 -> 16.1444` and PnL `$353,364.63 ->
$359,253.44`, with all windows improving and max drawdown slightly improving.
The adjacent 2026-06-02 Companyfacts scouts define the boundary: cash
conversion was a positive replay lead but was not promoted without forward
rows (`exp-20260602-001`), while asset turnover was rejected because the lift
concentrated too heavily in APP (`exp-20260602-007`).
The 2026-06-03 disclosure/source-provenance scouts narrowed the remaining
``restatement/disclosure-quality`` opening: amended-form support was not
testable because accepted Companyfacts rows had zero amended-form coverage
(`exp-20260603-002`), and cost-of-revenue gross-margin fallback support
improved all three windows but failed concentration (`exp-20260603-003`,
aggregate EV `+0.2035`, PnL `+$3,029.19`, APP positive-share `0.887952`,
HHI `0.796841`). Do not retry this source-provenance scalar family on the
frozen sample with ticker blacklists or nearby form/source flags.

Keep fixed:

- PIT Companyfacts filed-date boundary;
- EPS/revenue growth points;
- positive operating income quality gate;
- gross-margin quality source: `gross_margin >= 0.40` using filed-date revenue
  plus gross profit, with cost-of-revenue fallback and 60-400 day duration
  guard;
- RS proxy and top-1/day paper route;
- next-open entry and 10-trading-day paper exit;
- closed-ledger profit cap / drawdown governor.
- accepted filing-timeliness support: `10-Q <= 45` days and `10-K <= 75` days
  from fiscal period end to filed date, `1.05x` paper notional.
- accepted cost-liquidity support: `avg_dollar_volume_20 >= $200m` and
  signal-day `(high-low)/close <= 0.10`, `1.05x` paper notional.
- accepted sector-residual support: signal-date 20-day return at least `3pp`
  above the persisted public-sector median with at least `5` sector observations,
  `1.05x` paper notional.

Next valid fields:

- cash-conversion quality only after forward replacement-value rows confirm the
  positive `exp-20260602-001` replay lead;
- operating-margin durability only with new forward evidence or an orthogonal
  data field;
- restatement/disclosure-quality context only if it is materially different
  from amended-form coverage and gross-margin source provenance;
- cost-adjusted replacement-value attribution beyond the accepted coarse
  cost-liquidity state.

Frozen without new evidence:

- low-capex intensity, dual growth, gross-margin expansion, operating-margin
  durability, working-capital discipline, liquidity sweet spot, and recent VBB
  source-agreement notional support on the current frozen Companyfacts sample;
- earnings-price / earnings-yield value thresholds or support scalars on the
  current frozen Companyfacts + RS sample. `exp-20260601-004` found strong
  three-window paper PnL but rejected the field because positive PnL HHI stayed
  above the concentration guard, with APP/MU dominating the lift;
- gross-margin threshold, duration, source-precedence, or notional-scalar
  retunes around the accepted `exp-20260601-026` candidate source;
- filing-timeliness threshold/form/scalar retunes around the accepted
  `exp-20260601-027` support field;
- cost-liquidity threshold/scalar retunes around the accepted
  `exp-20260601-030` support field;
- sector-residual threshold/scalar retunes around the accepted
  `exp-20260602-010` support field;
- asset-turnover support retries on the current frozen sample after
  `exp-20260602-007` failed concentration despite positive raw replay PnL;
- amended-form and gross-margin source-provenance support/haircut retries on
  the current frozen Companyfacts stack after `exp-20260603-002` had zero
  selected-row coverage and `exp-20260603-003` failed concentration despite
  positive all-window EV/PnL;
- any new nearby Companyfacts scalar whose best case still depends on the
  already accepted operating-profit + RS stack rather than a new candidate
  source or a genuinely new PIT data field;
- score-tercile/rank monotonicity changes until forward rows show stable
  replacement value, not just partial in-sample ordering.

### 3. Volume-Breadth And VCP Sleeves

Mechanism: market participation confirmation is more valuable than retuning
price-shape thresholds. Volume-breadth breakout and QQQ-confirmed VCP should
stay as default-off paper adapters until closed forward rows mature.

Keep fixed:

- volume-breadth top-1/day, fixed `$10k` base notional, accepted
  breadth-intensity support (`volume_breadth_fraction >= 0.25`, `1.10x`),
  signal-day high-close support (`signal_day_close_location_value >= 0.70`,
  `1.10x`), cost/liquidity support (`dollar_volume >= $200m` and
  signal-day range/close `<= 0.10`, `1.05x`), and 10-day paper hold;
- VCP QQQ-confirmed top-2 route and `[1.0, 1.25]` rank-notional profile.

Next valid work:

- forward replacement value by breadth/regime/cost bucket;
- VCP forward accumulation or candidate-feed readiness only after noting
  `exp-20260530-004`: the VCP report is wired, but production snapshots through
  `2026-05-28` had `0` candidates and `0` closed forward outcomes;
- hidden Nasdaq beta attribution;
- concentration and decay monitoring;
- candidate-rank breadth diagnostics.

Frozen without new evidence:

- volume-breadth breadth-intensity threshold/scalar retunes on the frozen
  sample;
- volume-breadth high-close and cost/liquidity threshold/scalar retunes on the
  frozen sample;
- QQQ/SPY threshold sweeps;
- pocket-pivot allocation gates;
- base-geometry / higher-low gates;
- breakout-day volume/high-close gates;
- distribution-day exit/risk rules;
- pyramid/add-on rules.

### 4. Expectation / PEAD / Residual Leadership

Mechanism: expectation data is promising but still coverage- and attribution-
gated. Repaired PIT joins and old-score replacement attribution are useful
measurement progress, but not a promoted trading rule.

**5d horizon FROZEN as of 2026-05-29.** The measurement blockers were fixed
(`exp-20260527-908` PIT `last_earnings_date` 85.1% on primary positive;
`exp-20260528-030` PIT `eps_estimate_delta_30d` 80.85%) and all three core
sub-hypotheses were then tested directly with closed forward outcomes and
each rejected at the 5d primary horizon:

- residual leadership inside the PEAD window: `exp-20260528-027`, 5d lift
  **−3.60 pp** -> `rejected_no_residual_pead_edge`;
- PEAD window itself across 3 revision tiers (no residual filter):
  `exp-20260528-028`, cleanest-tier 5d lift **−0.40 pp** ->
  `rejected_no_pead_window_lift_across_tiers`;
- revision magnitude high vs low (7d + 30d axes): `exp-20260529-007`,
  decisive 7d-axis 5d lift **−1.15 pp** -> `rejected_no_revision_magnitude_edge`.

All three show the same 5d-negative / 10d-positive signature, but every 10d
bucket on the current single-earnings-season sample is below the published
closed-outcome floors, so the 10d flip is an open question, not evidence.
See `docs/alpha_direction_expectation_residual_leadership.md` 2026-05-29
freeze note for the full table.

Do next:

- continue PIT estimate revision accumulation across more than one earnings
  season so the 10d buckets clear the floors;
- add `revenue_estimate` / `analyst_count` velocity fields and full PIT
  `ret20_excess_sector` / `ret20_excess_theme` coverage — these widen the
  eventual 10d test rather than re-running a disproven 5d one;
- a retry must be a pre-registered 10d hypothesis on a multi-season sample,
  not another 5d attribution.

`exp-20260531-018` is the pre-registration for that future 10d test. It is
blocked until at least two independent earnings seasons have PIT
`eps_estimate_delta_30d` coverage and at least `20` usable candidates per
season; do not run it on the current single-season sample.

Do not:

- treat missing estimate revisions as neutral-positive;
- promote residual leadership alone as confirmation (disproven 5d:
  `exp-20260528-027`);
- re-test the PEAD window or revision magnitude as a 5d alpha clue on the
  current watchlist — the fields are populated, the sample is the blocker
  (`exp-20260528-028`, `exp-20260529-007`); a new 5d attribution on this
  direction must not take the top priority slot until a second earnings
  season exists;
- promote outside-PEAD short-horizon rows from the current frozen sample:
  `exp-20260528-029` found the apparent 1d/2d edge collapses after removing
  the top ticker or de-duplicating by ticker;
- add PEAD live ranking until production-visible fields and forward outcomes
  exist.

2026-05-31 update: the pre-earnings direction produced useful negative
evidence. `exp-20260531-001` rejected a pre-earnings surprise + 30d EPS
revision + RS source outright. `exp-20260531-003` found large aggregate
historical paper gains for an imminent 1-7 day surprise/RS source, but failed
Gate 4 because `late_strong` regressed and drawdown drift was too high.
`exp-20260531-004` then changed only the lifecycle to exit before the earnings
event; it also failed. Do not retry nearby imminent-earnings snapshot
thresholds, top-N, revision add-ons, or pre-event hold/exit variants on the
same frozen windows. A valid retry needs multi-season forward rows,
replacement value, and a materially richer expectation-quality field such as
revision breadth, analyst-count velocity, guidance text direction, or
surprise durability by regime.

2026-06-02 update: `exp-20260602-002` found a positive observed-only
post-earnings reset continuation lead when same-day earnings candidates are
split from pre-event risk and mapped to the next future earnings date after
the event. Against the canonical PIT-DTE Gate 1 baseline, aggregate EV improved
`6.3596 -> 7.8941` (`+24.13%`) and PnL improved
`$192,538.61 -> $234,850.99` (`+$42,312.38`); `8` exact-day reset trades
accounted for `$41,383.87` of the gain. This is not a license to restore the
old implicit calendar-DTE behavior. Valid next work is an explicit PIT-safe
event-timing policy with `pre_earnings_risk`, `post_earnings_continuation`,
`days_since_earnings`, `next_future_earnings_dte`, and before-open/after-close
timing parity. Do not retest nearby DTE thresholds until those fields exist.

### 4a. Continuous Ranking Surface

Mechanism: a broad cross-sectional `alpha_score` may contain useful ordering
information, but filled-trade attribution is biased because current core
selection already concentrates entries in the top buckets.

Current evidence:

- `exp-20260530-022` showed filled core trades are rank-degenerate, so entry
  attribution cannot test whether low-score names underperform.
- `exp-20260531-005` tested top-1/day full-universe `alpha_score` routing and
  was historically positive but rejected as a candidate-pool promotion.
- `exp-20260531-006` scored the full daily universe and found a small pooled
  5d top-bottom quintile spread with adequate observations, but no monotonic
  ladder and only `2/3` positive windows.
- `exp-20260531-016` added a production-visible broad risk-appetite gate to
  the same top-1/day route. It improved all three windows and passed
  concentration, but failed the drawdown guardrail, so regime gating is a
  useful clue rather than an accepted sleeve.
- `exp-20260531-017` decomposed the same full-universe PIT sample by existing
  `alpha_score_components`. No component produced a clean monotonic 5d ladder:
  breadth alignment and relative strength had top-bottom edge without
  monotonicity, theme participation inverted, and expectation/post-earnings
  components were effectively constant. This weakens raw component-gate and
  score-weight tuning as the next step.
- `exp-20260531-021` kept the `exp-20260531-016` source fixed but reduced
  default-off paper notional from `$10,000` to `$4,000`. It passed the
  standard three-window Gate 4 (`EV +1.6439`, PnL `+$32,770.52`, 151 target
  trades, no drawdown worsening, concentration passed).
- `exp-20260531-023` promoted that fixed source into
  `ALPHA_SCORE_MARKET_REGIME_PAPER`, a shared default-off production-visible
  adapter. It did not change score weights, thresholds, top-N, hold period, or
  live/default orders.
- `exp-20260531-025` promoted the positive `exp-20260531-024` source-consensus
  replay into that shared adapter. The only added behavior is default-off
  paper-notional support (`$4,000` -> `$5,000`) when the selected alpha-score
  candidate also appears in accepted FINRA/IWM or VBB paper sources on the same
  signal date. It remains observe-only.
- `exp-20260601-003` re-confirmed the `exp-20260531-017` component finding with
  an added relative_strength double-sort control: on the narrow 52-name
  watchlist the only robust cross-sectional component was `relative_strength`
  (`+0.81 pp` 5d, 3/3 windows); `breadth_alignment`'s univariate edge collapsed
  to `+0.34 pp` after controlling for RS (collinear), and
  `expectation_revision` / `post_earnings_drift` were perfectly constant
  (30% of composite weight inert). Narrow-universe verdict: alpha_score is
  RS-momentum, not incremental.
- `exp-20260601-006` is the decisive robustness test: it re-ran the composite
  quintile ladder AND the RS-controlled component decomposition on the broad
  1,446-ticker all-windows-full-liquid warehouse universe (`96,833` obs).
  Broadening the universe SHRANK the edge -- the opposite of a generalizable
  alpha. Composite 5d spread fell `+0.56 pp` (narrow) -> `+0.21 pp` (broad,
  below the `0.5 pp` floor); `relative_strength` fell `+0.81` -> `+0.34 pp`
  (also below floor); no component cleared the bar; the only positive composite
  window was `late_strong` (`1/3`). The universe-robust conclusion: raw
  `alpha_score` has NO robust 5d cross-sectional forward-return edge; the
  narrow-watchlist edge was largely a curated-momentum-universe, single-regime
  artifact.

Do next:

- collect forward replacement value for `ALPHA_SCORE_MARKET_REGIME_PAPER`
  against cash, same-day core candidates, and adjacent default-off paper ranks;
- only continue full-universe ranking work if it adds out-of-sample
  replacement value, regime/sector/liquidity conditioning, or a new
  production-visible information source beyond the current raw components;
- test whether top-score rows have positive replacement value versus the exact
  same-day core or default-off paper candidate they would displace;
- add cost-adjusted rank deltas before any top-N paper adapter;
- keep raw `alpha_score` as a read-only triage field outside the accepted
  market-regime safe-notional paper adapter.

Do not:

- promote a raw top-1 `alpha_score` sleeve from aggregate PnL alone;
- retune the accepted `ALPHA_SCORE_MARKET_REGIME_PAPER` thresholds, top-N,
  market gate, hold period, source-consensus scalar, or `$4,000` base notional
  on the same frozen windows;
- promote or retune raw `alpha_score_components` as gates/weights on these
  frozen windows without new evidence;
- tune score weights on the same frozen windows without a pre-registered
  component hypothesis;
- use filled-trade-only rank attribution to claim the surface works;
- claim raw `alpha_score` carries cross-sectional alpha from narrow-watchlist
  evidence: `exp-20260601-006` showed the edge SHRINKS below the materiality
  floor on the broad 1,446-ticker universe and is carried by a single regime
  (`late_strong`). Any revival must (a) use a broad universe, (b) show
  per-regime / out-of-window robustness, and (c) add a genuinely populated
  non-momentum component (the current expectation/PEAD inputs are constant on
  broad tickers), not a reweighting of the existing OHLCV-momentum components.

Unified close-out of the broad-universe cross-sectional line (do not re-mine):

- The broad 1,446-ticker warehouse cross-section was probed three ways and
  the only robust signal each time was momentum the core already trades:
  composite `alpha_score` reduces to `relative_strength`
  (`exp-20260601-003/006`); short-horizon **reversal is rejected**
  (`exp-20260601-007` -- with a skip-day and t-stat, every formation/hold
  cell is continuation, not reversal); and the incidental short-formation
  **continuation is a real long-only momentum tilt but NOT incremental over
  ret20** (`exp-20260601-008` -- top-quintile excess +0.47pct/10d net,
  t=2.82, 3/3 windows, but the ret20 double-sort residual is t=1.00,
  insignificant).
- Durable lesson: broad-universe OHLCV cross-sectional structure = momentum,
  and the core entry already trades momentum, so factor-mining the broad
  warehouse keeps rediscovering it. A new cross-sectional edge needs either a
  populated NON-momentum field (data-population problem) or a direct
  replacement-value test versus the actual same-day core candidate a name
  would displace (not a ret20/alpha_score proxy). Do not open another
  broad-universe OHLCV cross-sectional factor probe without one of those.
- Method note worth keeping: require any "incremental over X" claim to pass a
  double-sort residual that is BOTH above cost AND statistically significant
  (t>=2); a positive residual point estimate alone is not evidence
  (`exp-20260601-008` caught and corrected exactly this).
- Time-of-day structure is not a near-term lever on the current broad liquid
  universe. `exp-20260601-009` decomposed close-to-close returns into overnight
  and intraday components and found no robust overnight premium: overnight mean
  +0.044pct/day, t=1.15; overnight-minus-intraday t=0.11; only `2/3` windows
  positive. Reopening this direction requires a small/micro-cap universe or a
  much longer multi-regime sample plus explicit open/close turnover costs.

### 4b. Pattern-Name Candidate Pools

Mechanism: the last batch of OHLCV pattern-name pools did not survive Gate 4.
VWAP reclaim, long-base breadth confirmation, industry leadership, sector
breadth agreement, and ticker accumulation-quality breakout are plausible
descriptions, but the frozen evidence says they are not sufficient candidate
sources by themselves.

2026-06-01 update: the broader warehouse did not rescue the same family. Gap-up
hold high-close improved aggregate EV but failed because one window regressed
and drawdown drift was too high (`exp-20260601-010`). Stock-only governance
removed ETF/ETN/proxy noise but made aggregate PnL negative and still regressed
two windows (`exp-20260601-011`). Undercut/reclaim absorption was materially
different from gap chasing, but aggregate EV and PnL fell, only `old_thin`
improved, and baseline drift blocked any promotion (`exp-20260601-012`).

Valid retry requires one of:

- a new PIT data source, such as peer earnings transfer, option-implied event
  state, broker/estimate dispersion, or audited intraday liquidity state;
- a replacement-value test against the exact same-day core/paper candidate that
  would be displaced;
- a pre-registered forward cohort with concentration and cost-adjusted outcome
  gates.

Do not:

- rename another OHLCV breakout/pullback shape and test it as a new pool on the
  same windows;
- use high-close or VWAP reclaim as a broad candidate-pool source without a
  separate information-transfer or liquidity mechanism;
- retry broad gap-up/hold/high-close, stock-only gap governance, or
  undercut/reclaim absorption on the same frozen warehouse without new
  replacement-value evidence or a new PIT data source;
- promote Form 4 role quality, multi-filer owner count, or AI optical low-close
  support from the current thin or replacement-negative samples.

### 4c. FINRA Short Pressure + Risk Appetite

Mechanism: short-pressure breakout rows need an independent risk-appetite
confirmation and de-clustering. The useful accepted version is not "high short
interest alone"; it is official FINRA publication-date-safe short-pressure
context, OHLCV breakout/liquidity/RS gates, IWM-vs-SPY confirmation, and a
seven-calendar-day same-ticker admitted-candidate cooldown.

Keep fixed:

- official FINRA publication-date boundary;
- accepted OHLCV breakout/liquidity/relative-strength gates from
  `exp-20260529-017`;
- IWM 20d return minus SPY 20d return `>= 0.003`;
- seven-calendar-day same-ticker admitted-candidate cooldown;
- fixed `$10k` paper notional, next-open entry, and 10-trading-day paper exit;
- default-off shared adapter only.

Next valid work:

- forward replacement value versus same-day core candidates, cash, and adjacent
  paper ranks;
- concentration decay after the cooldown in real forward rows;
- promote the `exp-20260603-006` borrow-pressure replay lead into a shared
  default-off adapter with parity tests before treating it as retained
  production-visible surface;
- genuinely new PIT borrow-cost, loan-availability, utilization, or
  options-implied squeeze context if a clean source is added;
- cost-adjusted liquidity and fill-delay diagnostics.

Frozen without new evidence:

- FINRA score threshold, IWM/SPY threshold, cooldown length, top-N, hold-day,
  and fixed-notional retunes on the current frozen sample;
- nearby `days_to_cover` or `short_interest_change_pct` threshold retunes around
  `exp-20260603-006` before shared-adapter parity and forward rows exist;
- raw FINRA monotonic ranking or high-short-pressure breakout without IWM
  confirmation;
- promotion to live capital before closed forward replacement-value rows pass a
  separate activation gate.

### 5. State-Surface

State-surface is mature enough that additional profile/scalar tuning is
high-risk multiple testing. Work here should move toward:

- concentration and overlap with core;
- replacement value;
- sector/theme crowding;
- persistence versus extension;
- activation readiness and kill-gates.

Any same-family notional/profile/capital tweak needs >10% aggregate EV uplift
under the standard multi-window protocol, otherwise roll it back.

### 6. Event / SEC / News / LLM

Event alpha should move from single headline sentiment to structured event
state:

- source credibility and source overlap;
- disclosure quality;
- fact/tone gap;
- special-call and incremental-disclosure flags;
- event-family by market-state;
- regulatory/policy exposure;
- event interaction bursts and theme propagation.

The next useful unit is a schema-bound field or event graph that can be
replayed and attributed, not a prompt asking the model to buy or sell.

Local update: `exp-20260530-018` tested a simple pre-entry catalyst timing
field, `high_confidence_pre_entry_catalyst_freshness_bucket_v1`, on the
`exp-20260530-014` core trade rows. Fresh high-confidence catalyst rows
(`<=3` calendar days before entry) had enough sample (`10`) and improved
`2/3` windows, but the average lift versus stale or absent high-confidence
catalyst context was only `$68.95` PnL and `+2.808 pp` return, below the
pre-registered materiality gates. Treat catalyst recency alone as rejected.
`exp-20260530-019` then tested the obvious source/category-diversity refinement,
`high_confidence_pre_entry_catalyst_source_category_diversity_bucket_v1`, and
found zero diverse high-confidence rows: all `13` high-confidence rows were
single-category `sec_financial_report`. Treat simple catalyst source/category
diversity as rejected on these rows too. The next catalyst/event direction must
add a materially richer quality field, such as source credibility plus semantic
direction from SEC/news text, peer/source propagation, or forward replacement
value; do not rerun the same freshness or diversity cuts on the same rows.
`exp-20260530-020` then audited the production forward readiness of the
default-off SEC financial-report T+1 paper sleeve. Historical replay evidence
can stay in the archive, but the current production forward surface is not
activation-ready: `19` unique snapshot days through `2026-05-29` loaded `459`
SEC event rows and evaluated `31` T+1 rows while producing `0` candidates, `0`
candidate days, `0` pending/open/closed paper positions, and `$0.00` realized
paper PnL. Treat SEC financial-report activation or semantic allocation as
blocked until the candidate feed emits nonzero forward rows with closed
replacement-value outcomes.

### 7. Kova / CANSLIM Context

Kova data is a sidecar until proven otherwise.

Allowed:

- intraday/Companyfacts/13F/RS proxy readiness and coverage audits;
- read-only base, pocket-pivot, distribution-day, MA-stack, RS, and 13F
  context;
- attribution against already accepted paper trades.

Not allowed without new PIT surfaces and Gate 1-4:

- VCP gates based on Kova context;
- stop-under-base or fixed max-loss exits;
- simple day-3 low-MFE failed-breakout exits on the frozen VCP sample;
- shakeout/reclaim re-entry or hold rules from the frozen VCP sample unless
  forward rows and full slot/heat/replacement-value replay clear the gate;
- confirmation pyramid rules;
- pocket-pivot notional support;
- 13F/RS/fundamental live ranking changes.

## Research-Informed Field Backlog

The following literature updates should be treated as field and workflow ideas,
not direct strategy rules.

### Financial RAG And SEC Extraction

Recent financial RAG work points to agentic retrieval, metadata-aware
non-vector retrieval, reranking, and executable arithmetic as the practical
path for SEC/earnings fields. For Ginger, the priority is not larger context
windows; it is traceable retrieval.

The newest benchmark papers strengthen the same rule: LLMs degrade sharply
when tasks require cross-document, cross-entity, or longitudinal SEC reasoning,
and long financial reports create both retrieval-location and arithmetic-error
failure modes. Therefore financial RAG should produce audited fields and
failure buckets, not direct trade instructions.

Time-series augmented generation extends the same lesson to numeric market
work: the LLM should choose tools, assemble evidence, and verify calculations,
while deterministic code owns the time-series computation. For Ginger, this
means SEC, earnings, and price-derived fields should persist both the evidence
trace and the tool/execution trace before they can be considered for Gate 4.

The newest agentic financial-document benchmarks add one practical standard:
multi-step filing QA is only useful when the system can show which table,
footnote, period, entity, and arithmetic path produced the field. For Ginger,
an SEC-derived growth, margin, cash-conversion, liability, or guidance field
should therefore carry both source-span provenance and calculation provenance.
If the field cannot be replayed from the archived filing text/XBRL row and the
calculation trace, it belongs in research notes, not in a paper sleeve.

Useful fields:

- `retrieval_strategy_bucket`
- `retrieval_trace_id`
- `retrieval_source_doc_id`
- `retrieval_section_id`
- `metadata_filter_json`
- `retrieval_failure_bucket`
- `cross_period_consistency_bucket`
- `numeric_evidence_json`
- `cross_entity_comparison_failure_bucket`
- `longitudinal_tracking_failure_bucket`
- `calculation_verification_status`
- `evidence_table_span_ids`
- `time_series_tool_call_id`
- `tool_selection_accuracy_bucket`
- `tool_result_validation_status`
- `price_series_asof_policy_id`
- `numeric_hallucination_bucket`
- `filing_table_entity_id`
- `filing_period_alignment_bucket`
- `xbrl_fact_id`
- `calculation_trace_json`
- `arithmetic_replay_status`
- `field_source_span_hash`

Engineering rule: no retrieval trace means no Gate 4 trading field.

Sources:

- FinAgent-RAG, 2026-05-06: <https://arxiv.org/abs/2605.05409>
- FinAgent financial-document benchmark dataset, 2026:
  <https://huggingface.co/datasets/finagent-benchmark/finagent-benchmark>
- Time Series Augmented Generation for Financial Applications, 2026-04-21:
  <https://arxiv.org/abs/2604.19633>
- Rethinking Retrieval in financial LLM systems, 2025: <https://arxiv.org/abs/2511.18177>
- Financial-report RAG with reranking, 2026: <https://arxiv.org/abs/2603.16877>
- Document-level numerical reasoning across financial-report tables, 2026:
  <https://arxiv.org/abs/2604.03664>
- Fin-RATE SEC filing benchmark, 2026:
  <https://arxiv.org/abs/2602.07294>

### Agentic Trading Evaluation

Recent agentic-trading surveys are useful mainly as a warning. The live
research frontier is moving toward LLM agents that retrieve, reason, emit
actions, and adapt, but reproducibility is still weak: transaction costs,
survivorship, split timing, universe handling, and execution semantics are
often missing or incomparable. Ginger should borrow the audit checklist, not
delegate trading authority to agents.

Live-agent benchmarking points to the same boundary from the other side:
general LLM capability does not automatically become trading capability, and
risk control is the differentiator across markets. For Ginger, this means
agent benchmarks are useful for evaluation design, not as permission to let an
agent own entries, exits, or sizing.

Memory-controlled trading-agent benchmarks add a sharper warning: model
rationales can change materially when ticker identities, names, or memories are
masked or decayed. Ginger should treat LLM memory as an experimental variable.
Any LLM-assisted market memory should have named decay windows, masking policy,
and replay split IDs so the system can tell whether a result came from genuine
evidence, ticker-name priors, or stale narrative carryover.

Agent workflows are useful as research operators: they can propose hypotheses,
retrieve source packets, run attribution scripts, and write a replayable
evidence ledger. They are not strategy controllers. Any agent-produced
recommendation must land as one of three artifacts before it matters:
schema-bound context field, default-off paper candidate, or deterministic
shared policy.

Useful fields:

- `agent_decision_stage`
- `agent_evidence_ledger_id`
- `agent_action_schema_version`
- `agent_replay_split_id`
- `agent_transaction_cost_model_id`
- `agent_universe_pit_policy_id`
- `agent_execution_semantics_bucket`
- `agent_reproducibility_tier`
- `agent_tool_trace_id`
- `agent_hypothesis_ticket_id`
- `agent_evidence_packet_hash`
- `agent_replay_command_hash`
- `agent_memory_decay_policy_id`
- `agent_identity_mask_policy_id`
- `agent_memory_window_bucket`
- `agent_known_to_doing_gap_bucket`
- `agent_rationale_stability_bucket`

Engineering rule: an LLM agent can propose hypotheses or classify evidence,
but a trade-impacting action must still become a shared, replayable policy and
pass Gate 1-4.

Source:

- Agentic Trading: When LLM Agents Meet Financial Markets, 2026:
  <https://arxiv.org/abs/2605.19337>
- From Knowing to Doing: A Memory-Controlled Benchmark for LLM Trading Agents
  on Stock Markets, 2026: <https://arxiv.org/abs/2605.28359>
- AI-Trader: Benchmarking Autonomous Agents in Real-Time Financial Markets,
  2025/2026: <https://arxiv.org/abs/2512.10971>

### Event Graphs And Multi-Modal Market Context

New financial forecasting research increasingly treats news, fundamentals,
prices, and relational spillovers as graphs or multi-modal state. For Ginger,
this supports event-interaction and theme-propagation fields, not free-form LLM
trade calls.

The latest multimodal stock-forecasting work is moving beyond flat feature
concatenation toward cross-attention, gated fusion, and graph/market-structure
representations. The usable lesson is not to add a neural forecaster to live
orders; it is to persist relation-aware fields that can be replayed:
peer/sector hierarchy, covariance-network state, text/price alignment quality,
and whether a modality helped or hurt after costs.

New graph-transformer and hyperbolic/cross-attention work reinforces the same
implementation lesson: relation construction is the alpha hypothesis. A graph
field is not useful because it is graph-shaped; it is useful only if its edge
source, sparsification rule, time window, and modality contribution can be
replayed and compared against the displaced candidate after costs. This is the
proper retry path after local same-ticker SEC recurrence tests failed.

Recent peer-information and graph-learning work points to two practical
directions: characteristic-similarity peer groups and early-peer earnings
transfer. These are more actionable than another price-pattern pool because
they create a testable "who should react to whom" relation before the trade.
Characteristic-similarity graphs are especially relevant after the local SEC
event-graph failures: same-ticker recurrence was too weak, while edges built
from fundamentals, liquidity, momentum, sector/theme, analyst coverage, or
customer/supplier relations may encode a real propagation channel.

Useful fields:

- `event_interaction_graph_bucket`
- `same_theme_event_burst_count`
- `source_disagreement_bucket`
- `ticker_to_theme_propagation_bucket`
- `first_reaction_vs_followon_event_bucket`
- `media_spillover_relation_bucket`
- `characteristic_similarity_peer_bucket`
- `early_peer_earnings_reaction_bucket`
- `peer_event_age_trading_days`
- `peer_transfer_strength_score`
- `peer_relation_source_bucket`
- `peer_similarity_method_id`
- `peer_similarity_window_id`
- `peer_edge_weight`
- `peer_edge_sparsification_bucket`
- `peer_relation_pit_valid_flag`
- `modality_alignment_window_id`
- `text_price_alignment_bucket`
- `market_structure_graph_bucket`
- `graph_edge_construction_method`
- `modality_contribution_after_cost_bucket`
- `cross_modal_negative_transfer_bucket`
- `relation_construction_hypothesis_id`
- `graph_sparsification_method_id`
- `edge_asof_timestamp`
- `modality_gate_reason`
- `relation_displacement_value_bucket`

Local update: `exp-20260530-006` tested the simplest raw SEC filing interaction
field, `sec_same_event_family_burst_count_v1`, and rejected it. The sample was
large enough (`245` high-burst rows), but high-burst filings beat singleton
filings by only `+$12.41` average 10d PnL and `+0.124%` average return, far
below the materiality gate. Do not promote or retry raw same-family filing
burst count alone. `exp-20260530-008` then tested first-reaction/follow-on
sequencing with a 30-calendar-day same-ticker/same-event-family prior filing
lookback. That field was also rejected: `79` follow-on rows had `-$129.95`
average 10d PnL lift and `-1.2995%` average return lift versus first/isolated
filings, and only `1/3` windows improved. `exp-20260530-009` tested the adjacent
but distinct same-ticker cross-family event-transition field,
`sec_cross_family_event_transition_bucket_v1`. It had enough data (`457`
cross-family rows) and no single-ticker concentration issue (`8.39%` top
positive share), but average 10d PnL lift versus no-recent-prior filings was
`-$108.48`, average return lift was `-1.0848%`, and only `1/3` windows improved.
Future event-graph work needs a relation structure beyond same-ticker filing
recurrence or family transitions themselves, such as sector/theme propagation,
source overlap, or characteristic-similarity peer links.

Additional 2026-05-30 evidence extended the freeze: exact-industry Item 2.02
peer transfer, sector-event breadth transfer, and small same-family SEC bursts
also failed. That makes relation quality the bottleneck, not event count.

Sources:

- Multi-graph heterogeneous market information forecasting, 2026:
  <https://www.sciencedirect.com/science/article/pii/S0957417426010559>
- NEXUS financial news interactions, 2026:
  <https://www.sciencedirect.com/science/article/pii/S0957417426013242>
- Graph learning on financial networks from firm-characteristic similarity,
  2026: <https://link.springer.com/article/10.1007/s41109-025-00755-2>
- Algorithmic trading and intra-industry information transfer, 2026:
  <https://link.springer.com/article/10.1007/s11142-026-09954-3>
- Hyperbolic cross-attention multimodal stock forecasting, 2026:
  <https://link.springer.com/article/10.1007/s00521-026-12118-8>
- Explainable temporal heterogeneous graph transformer for stock return
  prediction, 2026: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6800538>

### Regime-Aware Predictability And Friction-Aware Control

Recent portfolio research aligns with Ginger's local evidence: alpha is
state-dependent, and the controller that decides whether and how to act is as
important as the raw signal. The practical lesson is not to add an opaque
optimizer. It is to persist the state variables that explain when a signal
should be trusted, whether turnover is worth paying for, and whether a sleeve
is replacing something better.

Two current papers are especially actionable. A 2026 regime-aware agentic
portfolio framework reports walk-forward improvements when LLM-derived text
signals are embedded in a transparent, friction-aware state-action-controller
with dynamic caps, turnover budgets, and cost gates instead of direct LLM
orders. NBER's 2026 "Mosaics of Predictability" argues that predictability is
asset-specific and state-dependent, concentrating in large earnings surprises,
high earnings-price stocks, low-volume stocks, and countercyclical / low
liquidity regimes. Both reinforce the same local rule: promote fields that
describe where predictability should exist, not generic filters that assume it
exists everywhere.

Local evidence now matches this: pre-earnings surprise/RS and full-universe
`alpha_score` can look strong in aggregate while failing by window, drawdown,
or monotonicity. The practical next step is not more top-N selection; it is
state-conditioned attribution that says when the score is allowed to matter.

Recent ML+Markowitz work is also relevant as an engineering pattern: keep
return estimation, covariance/risk, constraints, and final allocation in one
auditable pipeline. For Ginger, any future optimizer-like component should
emit its expected-return source, covariance window, constraint shadow prices,
and displacement cost before it can influence capital.

LLM-to-optimizer papers, including Black-Litterman variants, are useful only
when the LLM view is converted into a bounded expected-return view with an
explicit confidence estimate and then passed through deterministic constraints.
For Ginger, this maps to default-off allocation previews and paper sleeves, not
to free-form portfolio instructions. The minimum viable output is a view,
confidence, cost, covariance, constraint, and displacement record that can be
replayed without the LLM.

Useful fields:

- `predictability_mosaic_bucket`
- `earnings_surprise_predictability_bucket`
- `earnings_price_value_bucket`
- `low_volume_predictability_bucket`
- `market_liquidity_regime_bucket`
- `countercyclical_predictability_bucket`
- `state_action_controller_version`
- `dynamic_position_cap_reason`
- `turnover_budget_remaining`
- `expected_sharpe_improvement_after_cost`
- `friction_gate_passed`
- `constraint_elasticity_bucket`
- `llm_signal_role`
- `rank_score_validity_regime_bucket`
- `full_universe_rank_ladder_status`
- `replacement_candidate_score_gap`
- `expected_return_model_id`
- `covariance_estimation_window_id`
- `constraint_shadow_price_bucket`
- `optimizer_turnover_penalty_id`
- `allocation_displacement_cost_bucket`
- `llm_view_expected_return_bucket`
- `llm_view_confidence_calibration_bucket`
- `black_litterman_view_source_id`
- `allocation_constraint_set_id`
- `optimizer_replay_hash`

Engineering rule: regime-aware allocation belongs first in read-only
attribution and default-off sleeves. A live sizing or cap change must be a
shared deterministic controller input, not an LLM-generated action and not a
black-box policy.

Sources:

- Regime-aware portfolio optimization with LLM signals, 2026:
  <https://link.springer.com/article/10.1007/s41060-026-01066-0>
- Mosaics of Predictability, NBER 2026:
  <https://www.nber.org/papers/w35158>
- Machine learning portfolio optimization comparative study, 2026:
  <https://link.springer.com/article/10.1186/s40854-026-00927-8>
- Machine Learning Meets Markowitz, NBER 2026:
  <https://www.nber.org/papers/w34861>
- LLM-enhanced Black-Litterman portfolio optimization, 2025:
  <https://arxiv.org/abs/2504.14345>

### Transaction-Cost-Aware Allocation

Transaction costs should be visible before allocation, not only subtracted after
the backtest. This is especially important for high-turnover paper sleeves.
The accepted VBB cost/liquidity support is the local proof point: a simple
production-visible liquidity/range state can be a cleaner allocation field than
another alpha-shape threshold.

For ranking and candidate-pool sleeves, the cost field should be computed
against the displaced alternative. A candidate that is positive versus cash but
negative after spread/slippage versus the same-day core candidate is not an
activation candidate.

Useful fields:

- `expected_round_trip_cost_bucket`
- `spread_liquidity_cost_bucket`
- `turnover_pressure_bucket`
- `cost_adjusted_replacement_value_pnl`
- `cost_adjusted_rank_delta`
- `fill_delay_risk_bucket`
- `no_trade_zone_bucket`
- `liquidity_range_efficiency_bucket`
- `paper_to_live_cost_decay_bucket`

Sources:

- Large-scale portfolio allocation under transaction costs, SSRN:
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3043216>
- Portfolio optimization with linear/fixed transaction costs, Boyd:
  <https://web.stanford.edu/~boyd/papers/portfolio.html>
- Behaviorally informed DRL for portfolio optimization with regime-aware
  allocation thresholds, 2026:
  <https://www.nature.com/articles/s41598-026-35902-x>

### Changepoints And Regime Validation

Cross-sectional changepoints should be validation and recalibration triggers,
not blunt entry filters. Use them to explain sleeve decay, hidden beta, and
sector crowding.

Useful fields:

- `cross_section_changepoint_pressure_bucket`
- `sector_changepoint_pressure_bucket`
- `residual_variance_shift_bucket`
- `model_recalibration_due_flag`
- `post_changepoint_sleeve_decay_bucket`

Source:

- Changepoint detection in the cross-section of stock returns, 2026:
  <https://link.springer.com/article/10.1007/s10479-026-07075-3>

## Anti-Repeat Rules

Do not repeat these without forward rows or a materially different
production-visible field:

- broad filter/gate tightening on the core stack;
- nearby risk scalar / top-up sweeps;
- state-surface rank/profile/notional retunes below the hard EV threshold;
- QQQ/VCP/Kova threshold retunes;
- VCP activation reviews or Kova/VCP retunes before nonzero production forward
  candidates and closed replacement-value rows exist;
- FINRA/IWM/cooldown/top-N retunes before the accepted default-off FINRA sleeve
  has closed forward replacement-value rows or a new PIT borrow-cost /
  availability field;
- raw full-universe `alpha_score` top-N promotion or score-weight tuning before
  component-level attribution shows a monotonic ladder, regime stability, and
  cost-adjusted replacement value;
- broad-universe OHLCV cross-sectional factor mining that only re-discovers
  momentum, including short-horizon reversal retries, 5d/10d continuation
  promotion without ret20-incremental evidence, or time-of-day overnight
  premium retries on the same 1,446-ticker warehouse sample;
- imminent pre-earnings surprise/RS threshold, revision, top-N, hold-period, or
  pre-event-exit retries on the same frozen windows;
- VWAP-reclaim, long-base, industry-leadership, sector-breadth-agreement, or
  accumulation-quality candidate-pool retries on the same OHLCV-only frozen
  sample;
- gap-up/hold/high-close, stock-only gap-governance, or undercut/reclaim
  absorption candidate-pool retries on the same broad warehouse windows without
  a new PIT source or exact same-day replacement-value test;
- raw SEC same-family burst, first/follow-on, same-ticker cross-family
  transition, sector-event breadth transfer, exact-industry Item 2.02 peer
  transfer, small same-family burst, or Form 4 owner-count retries without a
  richer relation or ownership-intensity mechanism;
- simple pre-entry high-confidence catalyst freshness or source/category
  diversity retries on the `exp-20260530-014` core trade rows without a
  materially richer catalyst-quality field or forward replacement-value
  evidence;
- SEC financial-report activation reviews or semantic allocation scalars while
  the production forward sleeve has zero candidates and zero closed
  replacement-value rows;
- Companyfacts support-scalar mining around the accepted operating-profit + RS
  stack;
- Companyfacts cash-conversion promotion from the frozen replay alone; require
  forward replacement-value rows after the positive-but-unpromoted
  `exp-20260602-001` lead;
- Companyfacts asset-turnover support retries on the current sample after
  `exp-20260602-007` failed concentration;
- implicit same-day earnings DTE reset semantics or generic post-earnings
  reaction/positive-surprise candidate-pool retries after `exp-20260602-003`
  accepted the explicit continuation policy and `exp-20260602-004` /
  `exp-20260602-006` failed to promote standalone paper pools;
- nearby post-earnings underpriced drift `pre_event_rs20_vs_spy`, high-liquidity
  threshold/scalar, sector-residual threshold/min-member/scalar, score, or
  close-location retunes after `exp-20260602-026`, `exp-20260602-027`, and
  `exp-20260603-004`; require forward replacement-value rows or a materially
  richer event-quality field;
- simple target, stop, or fixed max-loss exit changes;
- ticker-specific exceptions from one or two trades;
- missing-archive or missing-text availability as an alpha field;
- LLM direct buy/sell/sizing authority.

## Minimum Standard For Any New LLM Field

Every new LLM-derived field must have:

1. schema-bound JSON output;
2. source document id, timestamp, and span/evidence binding;
3. schema or ontology version;
4. retrieval/parse/reasoning failure buckets;
5. production visibility in `run.py` artifacts or daily reports;
6. point-in-time replay safety;
7. chronological evaluation before any strategy use.

## Update Discipline

Update this file only when a result changes mechanism-level priors, freezes a
research family, changes the next 1-3 research queues, or adds a research idea
that maps to concrete replayable fields. Keep experiment detail in logs.
