# Data Edge / Context Layers

This document is the agent-facing index for the passive intelligence, data-edge, ranking, and attribution tools added around the context-memory roadmap.

These modules are mostly **read-only** by design. They exist to accumulate replayable market context, run attribution, and evaluate whether new data surfaces deserve future strategy experiments. Unless explicitly promoted through `docs/backtesting.md` and `docs/experiment_log.jsonl`, they must not alter entries, exits, rankings, sizing, orders, or live capital.

---

## Operating principle

The current direction is to increase alpha density by accumulating high-information context, not by adding more ad hoc strategy rules.

Preferred workflow:

1. Produce daily context snapshots in production.
2. Keep them append-only and replayable.
3. Run attribution against historical trades / backtests.
4. Promote only the small subset that proves incremental value.
5. Do not use these tools for live decisions until a separate Gate 1-4 experiment accepts the change.

---

## Core data-edge surfaces

The five priority context surfaces are:

1. **Earnings Estimate Revision**
   - Goal: archive expectation trajectory, not just current EPS.
   - Useful future features: EPS revision velocity, revenue revision velocity, analyst count delta, surprise history, guidance tone.

2. **Breadth / Internal Structure**
   - Goal: understand whether individual breakouts are supported by broad participation.
   - Useful fields: above-200MA fraction, breakout breadth, momentum breadth, volume-spike breadth, sector participation.

3. **Post-Earnings Drift**
   - Goal: track whether earnings / surprise information leads to persistent follow-through.
   - Useful future attribution: T+2 / T+5 / T+15 forward returns after earnings events.

4. **Theme Density**
   - Goal: measure theme participation, crowding, and exhaustion.
   - Current themes include AI, AI power, crypto, space, mega-cap, and gold.

5. **Relative Strength Surface**
   - Goal: move from absolute breakout checks to cross-sectional leadership.
   - Useful fields: ticker vs SPY, ticker vs QQQ, ticker vs theme / peer basket,
     and ticker vs sector.

### `quant/residual_strength_surface.py`

Purpose: emit read-only residual leadership fields for attribution, including
`ret20_excess_spy`, `ret20_excess_qqq`, `theme_residuals`, `themes`,
`ret20_excess_sector`, and `sector`.

Sector residuals depend on sector labels in the feature dictionary. When
daily quant feature rows do not carry `sector`, expectation/residual
attribution may enrich them from the offline deterministic
`data/reference/broad_market_sector_map.json` cache via
`quant/broad_market_sector_map.py`. This is a replayable public-classification
proxy, not evidence that production observed the classification point-in-time;
do not use it for live ranking, sizing, entries, exits, or orders unless a
separate Gate 1-4 experiment promotes that behavior.

Accepted exception: `exp-20260602-010` promotes one bounded use of this surface
inside the shared default-off `FUNDAMENTAL_GROWTH_RS_PAPER` adapter only.
Already-selected Companyfacts paper candidates may receive a `1.05x` paper
notional scalar when signal-date close-to-close 20-day return beats the
persisted public-sector median by at least `3pp` and the sector has at least
`5` same-date return observations. This remains paper-only metadata with
`trade_enabled=false`; it must not alter live entries, exits, ranking, sizing,
orders, LLM/news decisions, or watchlists without another Gate 1-4 promotion.

### `quant/space_catalyst_sleeve.py`

Purpose: maintain the default-off Space catalyst observation surface, including
observe-only event/source metadata and blocked one-slot trade plans.

The accepted `exp-20260528-026` Space alpha adds a production-visible OHLCV
context field, `space_trend_high_close_bucket`, for governed Space
`trend_long` candidates whose signal-day `daily_close_location >= 0.84`.
The accepted `exp-20260529-020` refinement adds
`space_trend_high_close_intraday_thrust_bucket` when that same high-close
candidate also has `signal_day_ticker_open_close_return_pct >= 0.04`.
The accepted `exp-20260531-022` refinement adds
`space_arkx_ufo_breakout_complement_bucket` for governed Space `breakout_long`
candidates that pass the same high-close/intraday-thrust checks while ARKX 20d
momentum is greater than UFO 20d momentum. Production computes the price-action
inputs in `quant/feature_layer.py` and the ARKX/UFO relative state in
`quant/space_catalyst_sleeve.py` from the same daily OHLCV-derived
`momentum_20d_pct` feature surface used by the observation slot.

The accepted `exp-20260602-025` refinement adds
`space_catalyst_cost_liquidity_support_state` and the
`space_cost_liquidity_support_bucket` observation field. It uses only
production-visible daily OHLCV features from `quant/feature_layer.py`:
`signal_day_ticker_dollar_volume >= $100M` and
`signal_day_ticker_range_pct <= 0.11`. The helper is default-off paper metadata
for already selected Space candidates, applies `1.05x` paper support only in
the observation surface, and records `trade_enabled=False` /
`alters_orders=False`.

These are metadata only: they must not alter entries, exits, ranking, sizing,
orders, or live Space slots without a separate Gate 1-4 promotion experiment.

---

## Production context archive

### `quant/daily_context_archive.py`

Purpose: build and persist the daily context archive.

Primary functions:

- `build_daily_context_archive(...)`
- `persist_daily_context_archive(...)`
- `build_earnings_estimate_revision_context(...)`
- `build_breadth_context(...)`
- `build_theme_density_context(...)`
- `build_relative_strength_surface(...)`
- `build_post_earnings_drift_context(...)`

Output:

```text
data/daily/context/context_YYYYMMDD.json
```

Production impact:

```json
{
  "alters_signal_generation": false,
  "alters_candidate_ranking": false,
  "alters_sizing": false,
  "alters_orders": false
}
```

Agent rule: this file is the daily passive context memory. Prefer adding new context fields here before turning them into strategy logic.

---

## Earnings expectation archive

### `quant/earnings_expectation_archive.py`

Purpose: snapshot expectation fields so the system can study revision history over time.

Primary functions:

- `EarningsExpectationSnapshot`
- `append_snapshot(...)`
- `compute_revision_features(...)`
- `build_expectation_surface(...)`

Output:

```text
data/daily/earnings_expectations/earnings_expectations_YYYYMMDD.json
```

Agent rule: do not confuse current EPS availability with expectation drift. The value comes from daily historical snapshots.

### `quant/estimate_revision_ledger.py`

Purpose: build the default-off PIT estimate-revision ledger from daily earnings
snapshots, including same-event EPS estimate deltas and candidate/signal match
metadata.

Output:

```text
data/non_ohlcv/estimate_revision_ledger_YYYYMMDD.jsonl
data/non_ohlcv/estimate_revision_ledger_summary_YYYYMMDD.json
```

Agent rule: when organized and legacy earnings snapshots exist for the same
as-of date, ledger construction must de-duplicate before computing revision
deltas. Prefer PIT-safe organized snapshots over later legacy/root copies so a
compatibility artifact cannot create a false `current_snapshot_created_after_asof`
or `prior_snapshot_created_after_asof` blocker.

---

## SEC financial-report language provenance

### `quant/sec_event_queue.py`

Purpose: attach replayable SEC filing-text semantics to the default-off
financial-report T+1 drift queue before any fact/tone or guidance-language
allocation rule is promoted.

Production source pairing:

- `sec_filing_events_*.jsonl` supplies the event row and point-in-time
  `usable_trade_date`.
- `sec_filing_text_*.jsonl` supplies the semantic text used by
  `language_features(...)`.
- Rows are matched by `(ticker, accession_number)` with an accession-only
  fallback.

Candidate provenance fields:

- `language_bucket`
- `language_score`
- `positive_phrase_hits`
- `negative_phrase_hits`
- `guidance_raise_hits`
- `guidance_cut_hits`
- `text_event_type`
- `sec_text_coverage_status`
- `sec_text_accession_matched`
- `sec_text_primary_document`
- `language_feature_rule_version`

Agent rule: these fields are read-only context and attribution inputs. They
may support `fact_tone_gap_attribution`, but must not change paper/live
allocation until a separate Gate 1-4 experiment proves bucket-level predictive
value and updates production/backtest parity.

### `quant/experiments/exp_20260530_006_sec_event_family_burst_attribution.py`

Purpose: read-only event-graph attribution for a first untried SEC interaction
field, `sec_same_event_family_burst_count_v1`. It groups PIT SEC filing events
by `usable_trade_date` and event-family bucket, then compares singleton filings
with same-day same-family burst filings using fixed `$10k` next-open to
10-trading-day-close forward outcomes across the canonical windows.

Output:

```text
data/experiments/exp-20260530-006/sec_event_family_burst_attribution.json
data/experiments/exp-20260530-006/sec_event_family_burst_attribution_rows.json
experiments/artifacts/exp-20260530-006_sec_event_family_burst_attribution.md
experiments/logs/exp-20260530-006.json
```

Agent rule: this experiment rejected raw same-family SEC filing burst count as
a standalone field. High-burst rows had enough sample but only tiny average
10d separation versus singleton filings. Do not promote this count into
ranking, sizing, sleeves, LLM prompts, or orders. A future event-graph retry
needs richer relations, such as sector/theme propagation, source overlap,
first-reaction/follow-on sequencing, or characteristic-similarity peer links.

### `quant/experiments/exp_20260530_008_sec_first_reaction_followon_attribution.py`

Purpose: read-only event-graph attribution for `sec_first_reaction_followon_event_bucket_v1`.
It groups PIT SEC filing events by ticker and event-family bucket, uses only
prior same-ticker/same-family filing dates inside a 30-calendar-day lookback,
and compares first/isolated filings with follow-on filings using fixed `$10k`
next-open to 10-trading-day-close forward outcomes across the canonical
windows.

Output:

```text
data/experiments/exp-20260530-008/sec_first_reaction_followon_attribution.json
data/experiments/exp-20260530-008/sec_first_reaction_followon_attribution_rows.json
experiments/artifacts/exp-20260530-008_sec_first_reaction_followon_attribution.md
experiments/logs/exp-20260530-008.json
```

Agent rule: this experiment rejected first/follow-on SEC filing recurrence as a
standalone field. Follow-on sample size was adequate (`79`) and positive PnL
was not dominated by one ticker, but follow-on rows had worse average 10d PnL
and return than first/isolated rows and improved only one window. Do not promote
this bucket into ranking, sizing, sleeves, LLM prompts, or orders. Future
event-graph retries need a different relation source, such as sector/theme
propagation, source overlap, or characteristic-similarity peer links.

### `quant/experiments/exp_20260530_009_sec_cross_family_event_transition_attribution.py`

Purpose: read-only event-graph attribution for `sec_cross_family_event_transition_bucket_v1`.
It groups PIT SEC filing events by ticker, uses only prior same-ticker filing
dates inside a 30-calendar-day lookback, flags rows with any prior event from a
different `event_family_bucket`, and compares cross-family transitions with
filings that had no recent prior SEC event using fixed `$10k` next-open to
10-trading-day-close forward outcomes across the canonical windows.

Output:

```text
data/experiments/exp-20260530-009/sec_cross_family_event_transition_attribution.json
data/experiments/exp-20260530-009/sec_cross_family_event_transition_attribution_rows.json
experiments/artifacts/exp-20260530-009_sec_cross_family_event_transition_attribution.md
experiments/logs/exp-20260530-009.json
```

Agent rule: this experiment rejected same-ticker SEC cross-family event
transitions as a standalone field. Cross-family rows were not thin (`457`) and
positive PnL was not dominated by one ticker (`8.39%` top positive share), but
they underperformed no-recent-prior filings by `-$108.48` average 10d PnL and
`-1.0848%` average return, with only one of three windows improving. Do not
promote this bucket into ranking, sizing, sleeves, LLM prompts, or orders.
Future event-graph retries need a different relation source, such as
sector/theme propagation, source overlap, or characteristic-similarity peer
links.

### `quant/experiments/exp_20260530_018_pre_entry_catalyst_freshness_attribution.py`

Purpose: read-only catalyst timing attribution for
`high_confidence_pre_entry_catalyst_freshness_bucket_v1`. It reuses the
`exp-20260530-014` core trade rows and compares trades with a high-confidence
catalyst inside three calendar days before entry against trades with stale or
absent high-confidence catalyst context.

Output:

```text
data/experiments/exp-20260530-018/pre_entry_catalyst_freshness_attribution.json
data/experiments/exp-20260530-018/pre_entry_catalyst_freshness_attribution_rows.json
experiments/artifacts/exp-20260530-018_pre_entry_catalyst_freshness_attribution.md
experiments/logs/exp-20260530-018.json
```

Agent rule: this experiment rejected simple high-confidence catalyst
freshness. The fresh bucket had enough rows (`10`), `2/3` windows improved, and
concentration passed, but PnL and return lifts were below the materiality
gates. Do not promote this bucket into ranking, sizing, sleeves, LLM prompts,
or orders. Future catalyst timing work needs source-diversity,
catalyst-quality, peer/source propagation, or forward replacement-value
evidence beyond recency.

### `quant/experiments/exp_20260530_019_pre_entry_catalyst_diversity_attribution.py`

Purpose: read-only catalyst-quality attribution for
`high_confidence_pre_entry_catalyst_source_category_diversity_bucket_v1`. It
reuses the same `exp-20260530-014` core trade rows and asks whether a
high-confidence catalyst becomes more actionable when the pre-entry context has
multiple high-confidence sources or multiple high-confidence categories.

Output:

```text
data/experiments/exp-20260530-019/exp_20260530_019_pre_entry_catalyst_diversity_attribution.json
data/experiments/exp-20260530-019/pre_entry_catalyst_diversity_attribution_rows.json
experiments/artifacts/exp-20260530-019_pre_entry_catalyst_diversity_attribution.md
experiments/logs/exp-20260530-019.json
```

Agent rule: this experiment rejected simple source/category diversity because
there were zero diverse high-confidence rows on the canonical `exp-20260530-014`
core-trade sample. All `13` high-confidence rows were single-category
`sec_financial_report`. Do not promote or retry broad catalyst early-entry,
catalyst risk top-up, freshness, or source/category diversity on these frozen
rows. A valid continuation needs a materially richer catalyst-quality field,
such as source credibility plus semantic direction from SEC/news text, peer or
source propagation, or forward replacement-value rows.

### `quant/experiments/exp_20260530_020_sec_financial_report_forward_readiness_audit.py`

Purpose: read-only production forward-readiness audit for the default-off
`SEC_FINANCIAL_REPORT_T1_DRIFT_EVENT_SLEEVE_PAPER` sleeve. It rolls up
`data/paper_sleeves/sec_financial_report/snapshots.jsonl` and `state.json`,
checks the AGENTS Gate 2 `operator_inputs/open_positions.json` fields, and
decides whether the sleeve has enough forward candidates and closed outcomes
for a later activation or semantic allocation experiment.

Output:

```text
data/experiments/exp-20260530-020/exp_20260530_020_sec_financial_report_forward_readiness_audit.json
experiments/artifacts/exp-20260530-020_sec_financial_report_forward_readiness_audit.md
experiments/logs/exp-20260530-020.json
```

Agent rule: this experiment rejected SEC financial-report forward activation
readiness. The production snapshots from `2026-05-10` through `2026-05-29`
had `19` unique as-of dates, `459` loaded SEC event rows, and `31` T+1
evaluated rows, but `0` forward candidates, `0` candidate days, `0` closed
paper outcomes, and `$0.00` realized paper PnL. Do not promote activation,
semantic allocation, ranking, sizing, LLM prompts, or orders from this sleeve
until nonzero forward rows, closed outcomes, and replacement-value fields
exist.

---

## Sentiment and regime attribution surfaces

### `quant/sentiment_surface.py`

Purpose: classify fine-grained market sentiment for read-only attribution.

Current buckets:

- `panic_risk_off`
- `volatile_rebound`
- `choppy_uncertain`
- `healthy_trend`
- `low_vol_grind`
- `theme_mania`
- `baseline`

Primary functions:

- `classify_sentiment_surface(...)`
- `build_sentiment_trade_attribution(...)`

Agent rule: sentiment should first be used for attribution. Do not use it to change sizing or entry filters until attribution proves value.

### `quant/backtest_sentiment_attribution.py`

Purpose: sidecar attribution for canonical backtest result JSON files.

Usage:

```powershell
python quant/backtest_sentiment_attribution.py data/experiments/<exp>/<window>_result.json
```

Output: `<result_stem>_sentiment.json`

Important limitation: if the backtest artifact lacks full entry-day market context, the current sidecar infers sentiment conservatively from replay-visible regime metadata. Stronger conclusions require production persistence of full daily context.

---

## Continuous cross-sectional ranking

### `quant/cross_sectional_ranking_surface.py`

Purpose: build a continuous alpha score across the universe from replayable components.

Current components:

- `trend`
- `relative_strength`
- `expectation_revision`
- `post_earnings_drift`
- `theme_participation`
- `breadth_alignment`

Primary functions:

- `build_component_scores(...)`
- `compute_alpha_score(...)`
- `build_cross_sectional_ranking_surface(...)`

Default weights:

```json
{
  "trend": 0.30,
  "relative_strength": 0.25,
  "expectation_revision": 0.20,
  "post_earnings_drift": 0.10,
  "theme_participation": 0.10,
  "breadth_alignment": 0.05
}
```

Agent rule: this is a read-only ranking surface. It must not replace `signal_engine.py` or live ranking until a separate accepted experiment proves incremental value.

### `quant/alpha_score_market_regime_paper_sleeve.py`

Purpose: maintain the default-off `ALPHA_SCORE_MARKET_REGIME_PAPER` forward
observation ledger for the accepted full-universe `alpha_score` market-regime
safe-notional route.

Evidence boundary:

- `exp-20260531-021` passed the standard three-window Gate 4 with the fixed
  source at `$4,000` paper notional (`EV +1.6439`, PnL `+$32,770.52`, 151
  target trades, no drawdown worsening, concentration passed).
- `exp-20260531-023` promoted the route into a shared default-off adapter with
  focused parity tests. It did not change score weights, thresholds, top-N,
  hold period, live watchlists, or order paths.
- `exp-20260531-025` added the accepted source-consensus support from
  `exp-20260531-024` to the same shared adapter: when the selected alpha-score
  candidate also appears in accepted FINRA/IWM or VBB paper sources on the same
  signal date, only the default-off paper notional is scaled `1.25x`
  (`$4,000` -> `$5,000`). This remains metadata and paper ledger state only.

Inputs:

- current daily `features_dict` and `cross_sectional_ranking_surface`;
- already-loaded daily OHLCV for candidate tickers plus `SPY` and `IWM`;
- exact `as_of` open/close rows only for fills, hold-day advancement, and
  closes.

Adapter semantics:

- fixed full-universe PIT `alpha_score` top-decile/top-1 source;
- stock-only ETF exclusions and `avg_dollar_volume_20d >= $40m`;
- SPY close above its 50-day average and `IWM 20d return - SPY 20d return >= 0`;
- fixed `$4,000` base paper notional, accepted source-consensus `1.25x` paper
  support from same-day VBB/FINRA snapshots when present, next-open paper entry,
  and 20-trading-day paper exit;
- default-off `pending/open/closed` paper ledger, replacement-value report,
  forward gate, default-off attribution surface, and human-report block.

Agent rule: this sleeve is observe-only. Do not retune its thresholds,
market gate, top-N, hold, notional, or score weights on the same frozen
windows. Promotion to live/core behavior requires closed forward replacement
value and a separate Gate 1-4 activation experiment.

### `quant/accepted_source_consensus_paper_sleeve.py`

Purpose: maintain the default-off `ACCEPTED_SOURCE_CONSENSUS_PAPER` forward
observation ledger for the accepted-source consensus candidate-pool lead.

Evidence boundary:

- `exp-20260531-026` showed the standalone accepted-source consensus pool was a
  positive replay lead across all three canonical windows, but it was not
  production-equivalent until a shared adapter existed.
- `exp-20260531-029` promoted the same fixed source into a shared default-off
  adapter. It does not change score weights, thresholds, top-N, hold period,
  live watchlists, or order paths.

Adapter semantics:

- rebuilds the accepted alpha-score market-regime candidate source using the
  same production-visible OHLCV/features surface;
- admits only candidates whose same signal-date ticker also appears in accepted
  `VOLUME_BREADTH_BREAKOUT_PAPER` or `FINRA_IWM_CONFIRMED_PAPER` snapshots;
- uses fixed `$4,000` paper notional, no source-consensus notional scalar,
  next-open paper entry, and 20-trading-day paper exit;
- emits default-off `pending/open/closed` paper ledger, replacement-value
  report, forward gate, default-off attribution surface, and human-report block.

Agent rule: this sleeve is observe-only. Do not retune the source set, alpha
score thresholds, market gate, top-N, hold, or notional on the same frozen
windows. Promotion to live/core behavior requires closed forward replacement
value and a separate Gate 1-4 activation experiment.

### `quant/free_data_cross_source_consensus_paper_sleeve.py`

Purpose: maintain the default-off
`ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER` forward observation ledger for
the source-agnostic accepted free-data consensus lead.

Evidence boundary:

- `exp-20260531-030` showed that same signal-date ticker agreement across any
  two accepted free-data paper sleeves improved all three canonical windows
  (`EV +0.5103`, PnL `+$9,359.12`, `47` target trades) and passed drawdown,
  survival, sample, and concentration guards.
- `exp-20260601-001` promoted that fixed candidate definition into a shared
  default-off adapter. It does not change source thresholds, source notional,
  top-N, hold period outside this adapter, live watchlists, or order paths.
- `exp-20260601-028` added the accepted current-baseline
  core-capacity-available admission boundary. The adapter now requires the same
  production-visible core slot context used by entry planning and blocks new
  paper admissions when that context is missing or when active core positions
  are already at `MAX_POSITIONS`.

Adapter semantics:

- receives same-day snapshots from `FUNDAMENTAL_GROWTH_RS_PAPER`,
  `VOLUME_BREADTH_BREAKOUT_PAPER`, `FINRA_IWM_CONFIRMED_PAPER`, and
  `ALPHA_SCORE_MARKET_REGIME_PAPER`;
- admits only candidates whose ticker appears in at least two of those accepted
  free-data sources on the same signal date;
- admits those candidates only when `active core positions < MAX_POSITIONS`
  under the production core-slot accounting surface;
- uses fixed `$4,000` paper notional, top-1/day,
  seven-calendar-day same-ticker admitted-candidate cooldown, next-open paper
  entry, and 10-trading-day paper exit;
- emits default-off `pending/open/closed` paper ledger, replacement-value
  report, core-capacity gate metadata, forward gate, default-off attribution
  surface, and human-report block.

Agent rule: this sleeve is observe-only. Do not retune the source count, source
set, cooldown, notional, hold period, or nearby capacity variants on the same
frozen windows. Promotion to live/core behavior requires closed forward
replacement value and a separate Gate 1-4 activation experiment.

### `quant/ranking_attribution.py`

Purpose: evaluate whether `alpha_score` contains predictive information in historical / replay artifacts.

Usage:

```powershell
python quant/ranking_attribution.py <result_json> <ranking_surface_json>
```

Output: `<result_stem>_ranking_attribution.json`

Attribution outputs:

- bucket attribution by `top_decile`, `top_quartile`, `upper_mid`, `lower_mid`, `bottom_quartile`;
- component attribution by high / mid / low component score;
- coverage of trades with available alpha scores.

Agent rule: use ranking attribution to validate the ranking surface before proposing any live sizing or ranking experiment.

### `quant/entry_day_ranking_attribution.py`

Purpose: rebuild ranking and canonical state-vector context as of the trading day before each filled entry, then attribute realized trade outcomes to that point-in-time context.

Usage:

```powershell
python quant/entry_day_ranking_attribution.py <result_json> <ohlcv_snapshot_json>
```

Output: `<result_stem>_entry_day_ranking_attribution.json`

Attribution outputs:

- ranking bucket attribution by point-in-time `alpha_score` rank;
- component attribution by high / mid / low point-in-time component score,
  including coverage, value range, unique-value count, and constant-field
  diagnostics;
- canonical leadership / risk heat vector attribution and the combined
  leadership-risk state.

Agent rule: use this for predictive ranking / allocation research. A single static ranking surface is acceptable for historical explanation, but not for promoting a forward-looking ranking or sizing rule.

### `quant/pilot_sleeve.py` AI infra promotion readiness

Purpose: expose `AI_INFRA_AGGRESSIVE` pilot promotion blockers from the same
daily attribution surface that reports selected/sliced pilot candidates and
replacement-value metrics.

Output key: `ai_infra_aggressive_attribution.promotion_readiness`

Checks mirror `docs/universe_promotion_protocol.md` for `pilot ->
limited_production`: closed outcomes, direct pilot PnL, replacement value,
risk-adjusted replacement value, single-trade profit concentration, sleeve
drawdown, theme-beta explanation, event-risk clearance, and live slippage.

Agent rule: this is a read-only promotion-readiness diagnostic. It must not be
used to add slots, increase risk, or promote a ticker without a separate Gate
1-4 experiment and explicit production/backtest parity update.

### `quant/broad_market_paper_sleeve.py`

Purpose: maintain the default-off `BROAD_MARKET_LEADERSHIP_PAPER` forward
observation ledger for accepted broad-market leadership paper alpha.

Candidate feed order:

1. `data/state/broad_market_paper/universe.json` when present.
2. `broad_market_universe_state_observation_feed_v1`, derived from the daily
   persisted `universe_state` observation records when the static feed is
   missing.

The fallback feed excludes already tradeable core/pilot/governance names,
benchmarks, ETF/theme-beta benchmark rows, quarantined rows, and non-research /
non-specialist records. It is a measurement-repair path for forward evidence
collection, not a live candidate-pool promotion.

Agent rule: this feed may create pending/open/closed default-off paper rows and
replacement-value evidence. It must not enable orders, core universe expansion,
ranking, or sizing without a separate Gate 1-4 activation experiment.

### `quant/ai_optical_paper_sleeve.py`

Purpose: maintain the default-off `AI_OPTICAL_IWM_CONFIRMED_PAPER` forward
observation ledger for the accepted AI optical candidate-pool lead from
`exp-20260525-003`.

Candidate feed:

- Derived from the daily persisted `universe_state` observation records.
- Requires `theme == ai_optical_connectivity`,
  `theme_segment == optical_connectivity`, `status in {pilot, research}`,
  `history_class == full_history`, and `liquidity_tier in {ok, watch}`.
- Excludes current core-trade-universe names and benchmarks, but keeps pilot
  and research optical names because the experiment was a no-displacement
  paper sleeve rather than a core promotion.

The paper route reuses the normal trend/breakout signal stack for candidate
signals, applies a free-data IWM/SPY confirmation gate
(`IWM 20d momentum - SPY 20d momentum >= 0.003`), tracks fixed `$10k` paper
notional, and emits pending/open/closed replacement-value rows only.

Agent rule: this feed may collect forward replacement-value evidence. It must
not enable orders, promote optical names into the core universe, alter pilot
slots, ranking, sizing, or exits without a separate Gate 1-4 activation
experiment and parity update.

### `quant/volatility_contraction_paper_sleeve.py`

Purpose: maintain the default-off
`VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER` forward observation ledger for the
accepted replay lead from `exp-20260525-022` and the accepted top-2
candidate-depth paper expansion from `exp-20260525-037`.

Candidate route:

- Uses the daily loaded OHLCV universe plus `SPY` / `QQQ`.
- Requires the same volatility-contraction breakout source as exp-20260525-022:
  short ATR below long ATR, close above the prior 20-day high, close above the
  50-day moving average, positive same-day RS vs SPY, and adequate dollar
  volume.
- Requires the free-data market confirmation
  `QQQ 20d close-to-close return > SPY 20d close-to-close return`.
- Emits up to two ranked same-day candidates. `vcp_candidate_rank_on_signal_date`
  and `max_paper_trades_per_day` are paper metadata, not live ranking inputs.
- Emits read-only Kova pocket-pivot support metadata from
  `exp-20260525-027`: `pre_signal_pocket_pivot_seen_10d`,
  `pre_signal_pocket_pivot_count_10d`,
  `latest_pre_signal_pocket_pivot_date`,
  `latest_pre_signal_pocket_pivot_volume_ratio`, and
  `pocket_pivot_context_status`. The scan uses only the prior 10 trading days
  before the signal date, excludes the signal date, and marks missing prior
  down-day volume as unavailable/false rather than guessed.
- Tracks fixed `$10k` paper notional, next-open paper entry, 10-trading-day
  paper hold, closed outcomes, replacement-value summary, and concentration
  blockers only.

Agent rule: this sleeve may collect forward replacement-value evidence. It must
not enable orders, expand the core universe, alter live ranking, sizing, exits,
LLM/news, or consume live capital without a separate Gate 1-4 activation
experiment and parity update. The pocket-pivot fields are metadata only because
`exp-20260525-027` failed the replacement gate versus `exp-20260525-022`; the
top-2 expansion is default-off paper only until forward closed outcomes clear
the promotion gate.

### `quant/experiments/exp_20260528_010_kova_distribution_day_regime_attribution.py`

Purpose: read-only Kova market-regime attribution for the accepted
`VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER` top-2 paper trades. It joins
signal-date SPY / QQQ OHLCV to a distribution-day pressure bucket and a simple
confirmed-uptrend proxy, then reports VCP paper outcomes by bucket.

Output:

```text
data/experiments/exp-20260528-010/kova_distribution_day_regime_attribution.json
experiments/artifacts/exp-20260528-010_kova_distribution_day_regime_attribution.md
experiments/logs/exp-20260528-010.json
```

Agent rule: this attribution is context only. `exp-20260528-010` found full
coverage on the frozen accepted VCP top-2 sample, but the high-distribution
pressure bucket remained positive. Do not turn distribution-day counts or the
confirmed-uptrend proxy into a VCP gate, rank rule, notional scalar, exit, or
live order input without forward replacement-value evidence and a separate
Gate 1-4 strategy experiment.

### `quant/experiments/exp_20260528_014_kova_sell_side_lifecycle_taxonomy.py`

Purpose: read-only Kova sell-side lifecycle taxonomy for the accepted
`VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER` top-2 paper trades. It joins
post-entry OHLCV inside the source 10-trading-day paper hold and labels
stop-loss touch, high-volume support break, profit giveback, climax/churning,
event gap-down proxy, failed low-MFE breakout, and strong follow-through
patterns without changing exits.

Output:

```text
data/experiments/exp-20260528-014/kova_sell_side_lifecycle_taxonomy.json
experiments/artifacts/exp-20260528-014_kova_sell_side_lifecycle_taxonomy.md
experiments/logs/exp-20260528-014.json
```

Agent rule: this taxonomy is context only. `exp-20260528-014` found full
coverage on the frozen accepted VCP top-2 sample and identified
`failed_breakout_low_mfe` as a populated negative bucket (`14` trades,
`-$3,935.60`). That can nominate a later shared lifecycle replay, but it must
not become an exit, stop, gate, scalar, live order input, or prompt instruction
without an ex-ante trigger and separate Gate 1-4 production/backtest parity
experiment.

### `quant/experiments/exp_20260528_031_kova_day3_low_mfe_failed_breakout_exit_shadow_replay.py`

Purpose: read-only shadow replay for the Kova sell-side lifecycle direction
nominated by `exp-20260528-014`. It tests whether an ex-ante day-3 low-MFE
failed-breakout trigger can improve the accepted VCP top-2 paper trade exits
without using final 10-day outcomes to decide the exit.

Output:

```text
data/experiments/exp-20260528-031/kova_day3_low_mfe_failed_breakout_exit_shadow_replay.json
experiments/artifacts/exp-20260528-031_kova_day3_low_mfe_failed_breakout_exit_shadow_replay.md
experiments/logs/exp-20260528-031.json
```

Agent rule: this experiment may only report shadow replay evidence. It must
not change live exits, VCP entries, candidate ranking, sizing, paper notional,
LLM prompts, paper sleeves, or orders. Any promotion requires a separate shared
lifecycle policy with production/backtest parity.

### `quant/experiments/exp_20260529_006_kova_shakeout_reclaim_lifecycle_attribution.py`

Purpose: read-only attribution for the Kova shakeout/reclaim re-entry
direction. It buckets accepted VCP top-2 paper trades by whether the first
five trading days after entry include a `-4%` intraday shakeout followed by a
close back above the entry/pivot reclaim level with close location at least
`0.55`.

Output:

```text
data/experiments/exp-20260529-006/kova_shakeout_reclaim_lifecycle_attribution.json
experiments/artifacts/exp-20260529-006_kova_shakeout_reclaim_lifecycle_attribution.md
experiments/logs/exp-20260529-006.json
```

Agent rule: this is a clue, not a policy. `exp-20260529-006` found the
shakeout/reclaim bucket was positive but too thin (`7` trades versus a
pre-set `10`-trade minimum). It must not change exits, re-entry, ranking,
sizing, live orders, or VCP paper-sleeve allocation unless a later forward or
full lifecycle replay clears slot, heat, replacement-value, concentration, and
production/backtest parity gates.

### `quant/experiments/exp_20260529_025_kova_vcp_loss_streak_derisk_replay.py`

Purpose: closed-ledger shadow replay for the Kova operator-process direction
of reducing exposure after repeated stops. It tests a single paper notional
variable on the accepted VCP top-2 source: after two already-closed losing VCP
paper trades, halve subsequent VCP paper notional until a known closed winner
resets the streak.

Output:

```text
data/experiments/exp-20260529-025/kova_vcp_loss_streak_derisk_replay.json
experiments/artifacts/exp-20260529-025_kova_vcp_loss_streak_derisk_replay.md
experiments/logs/exp-20260529-025.json
```

Agent rule: this experiment rejected the narrow frozen-sample loss-streak
scalar. It triggered 11 trades and improved EV proxy by `+0.003721`, but
reduced aggregate PnL by `-$856.33` after scaling 6 winners and 5 losers. Do
not promote or retest this same closed-ledger VCP notional scalar without new
forward portfolio-state and replacement-value evidence.

### `quant/experiments/exp_20260530_004_vcp_forward_replacement_value_readiness_audit.py`

Purpose: read-only activation-readiness audit for the accepted
`VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER` top-2 paper sleeve. It reads the
production forward state, snapshots, and default-off attribution surface to
decide whether the sleeve has enough replacement-value evidence for a separate
activation review.

Output:

```text
data/experiments/exp-20260530-004/vcp_forward_replacement_value_readiness_audit.json
experiments/artifacts/exp-20260530-004_vcp_forward_replacement_value_readiness_audit.md
experiments/logs/exp-20260530-004.json
```

Agent rule: this audit found the surface is wired but immature. Snapshots
through `2026-05-28` had `candidate_count=0` and
`closed_forward_outcomes=0`, so activation remains blocked by missing forward
rows and replacement-value evidence. Do not promote VCP, retune QQQ/VCP/Kova
thresholds, or add a new VCP scalar from frozen-sample evidence until the
production ledger has nonzero candidates and enough closed forward outcomes.
If candidate count stays zero after more production days, inspect the paper
candidate feed as measurement repair before proposing another alpha rule.

### `quant/kova_data_sidecar.py`

Purpose: collect default-off Kova support data without changing entries,
ranking, sizing, exits, LLM/news, universe, or orders. The sidecar gives later
experiments PIT-tagged rows for ideas that could not be tested from daily OHLCV
alone.

Surfaces:

- `intraday_ohlcv`: Alpha Vantage 15m/60m bars when
  `ALPHA_VANTAGE_API_KEY` is provided. Missing key writes explicit `skipped`
  rows rather than failing production.
- `sec_companyfacts_growth`: derives EPS / revenue / net-income YoY rows from
  existing SEC Companyfacts selected rows, using `filed` as `asof_date`.
- `sec13f_institutional_ownership`: parses SEC 13F data-set zips or supplied
  zip files; ticker joins require a CUSIP map and otherwise remain explicitly
  `missing_cusip_ticker_map`.
- `ginger_rs_proxy`: computes OHLCV-based relative-strength proxy ranks versus
  `SPY`; this is a Ginger proxy, not IBD RS Rating.

Files:

```text
data/kova/intraday/intraday_ohlcv_YYYYMMDD.jsonl
data/kova/fundamentals/companyfacts_growth_YYYYMMDD.jsonl
data/kova/institutional/sec13f_ownership_YYYYMMDD.jsonl
data/kova/rs_proxy/rs_proxy_YYYYMMDD.jsonl
data/kova/snapshots/kova_data_snapshot_YYYYMMDD.json
```

Runner:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_kova_data_refresh.py --as-of YYYY-MM-DD --tickers AAPL MSFT NVDA --ohlcv-snapshot data\ohlcv\ohlcv_snapshot_YYYYMMDD_YYYYMMDD.json
```

Production wiring: `exp-20260527-014` wires the same sidecar into
`quant/run.py`. The daily run passes the already-loaded OHLCV dictionary plus
`SPY` into `persist_kova_data_snapshot`, attaches the result at
`non_ohlcv_snapshot["kova_data_sidecar"]`, and keeps all heavy external
refreshes explicit env-gated. Default production behavior performs no extra
OHLCV fetch, skips Alpha Vantage intraday unless `KOVA_REFRESH_INTRADAY=1` and
`ALPHA_VANTAGE_API_KEY` are present, skips SEC 13F network work unless the
13F env inputs are supplied, bounds local Companyfacts reads with
`KOVA_COMPANYFACTS_LOOKBACK_DAYS` defaulting to `820`, and writes explicit
skipped rows for unavailable optional sources.

Agent rule: these rows are context only. They may be used by future replay
experiments through an explicit as-of join, but they must not be consumed by
live orders or promoted into VCP gates without a separate Gate 1-4 experiment.

### `quant/volume_breadth_breakout_paper_sleeve.py`

Purpose: maintain the default-off `VOLUME_BREADTH_BREAKOUT_PAPER` forward
observation ledger for the accepted shared-adapter replay from
`exp-20260526-014`, which productionizes the positive replay-only
`exp-20260526-013` breadth/internal-structure lead.

Candidate route:

- Uses the daily loaded OHLCV universe plus `SPY`.
- Requires the fixed `volume_breadth_thrust_confirmed_breakout_v1` context:
  at least 30 eligible tickers, up-volume spike breadth >= 12%, market-up
  fraction >= 52%, and above-50d fraction >= 45%.
- Requires the candidate to close above its prior 20-day high and prior 50-day
  moving average, trade at least `$40m` signal-day dollar volume, have
  signal-day volume ratio >= 1.25, and beat SPY on the signal day.
- Emits ranked candidates but opens at most one paper entry per day, with a
  fixed `$10k` base paper notional plus the accepted
  `exp-20260528-018` breadth-intensity support scalar
  (`volume_breadth_fraction >= 0.25` -> `1.10x` paper notional) and the
  accepted `exp-20260528-022` signal-day high-close support scalar
  (`signal_day_close_location_value >= 0.70` -> `1.10x` paper notional),
  next-open paper entry, 10-trading-day close exit, closed outcomes,
  replacement-value summary, and concentration blockers.

Agent rule: this sleeve may collect forward replacement-value evidence. It
must not enable orders, expand the core universe, alter live ranking, sizing,
exits, LLM/news, or consume live capital without a separate Gate 1-4 activation
experiment and parity update. Do not retune the breadth, breakout, volume,
top-1, breadth-intensity support, or high-close support thresholds/scalars on
the frozen sample; use forward rows or an orthogonal production-visible field.

### `quant/post_earnings_underpriced_drift_paper_sleeve.py`

Purpose: maintain the default-off `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER`
forward observation ledger for the accepted post-earnings underpriced
positive-surprise drift lead from `exp-20260602-026`, which promoted the
positive `exp-20260602-023` replay result into a shared production-visible
adapter.

Candidate route:

- Uses daily earnings snapshots plus the daily loaded OHLCV universe and `SPY`.
- Confirms a positive EPS surprise event only on a snapshot transition where
  the prior snapshot had `days_to_earnings <= 7`, the current snapshot has
  `days_to_earnings >= 20`, and actual EPS or the latest surprise-history
  value changed.
- Requires latest surprise >= `3%`, at least `4` surprise-history rows, at
  least `2` positive historical surprises, and average historical surprise >=
  `0`.
- Admits signals only 0-5 trading days after the event, with average dollar
  volume >= `$40m`, close above the prior 50-day average, close-location >=
  `0.55`, 20-day RS vs SPY > `0`, event-to-signal return >= `0`, and
  event-to-signal excess versus SPY >= `0`.
- Applies the accepted underpricing discriminator: the ticker's 20-day return
  ending on the close before the event minus SPY's same-window return must be
  `<= 0`.
- Emits ranked candidates but opens at most one paper entry per day, with
  fixed `$10k` base paper notional, next-open paper entry, 10-trading-day
  close exit, closed outcomes, replacement-value summary, and concentration
  blockers only.

Agent rule: this sleeve may collect forward replacement-value evidence for the
accepted alpha. It must not enable orders, expand the core universe, alter live
ranking, sizing, exits, LLM/news, or consume live capital without a separate
Gate 1-4 activation experiment and parity update. Do not retune
`pre_event_rs20_vs_spy`, surprise thresholds, signal-offset windows, top-N,
hold-day, or base notional on the frozen sample without forward rows or a
materially richer event-quality field.

### `quant/fundamental_growth_rs_paper_sleeve.py`

Purpose: maintain the default-off `FUNDAMENTAL_GROWTH_RS_PAPER` forward
observation ledger for the accepted Companyfacts operating-profit quality +
gross-margin quality + RS candidate-pool alpha from `exp-20260528-008` and
`exp-20260601-026`, plus filing-timeliness paper support from
`exp-20260601-027` and cost-liquidity paper support from `exp-20260601-030`.

Candidate route:

- Uses the daily loaded OHLCV universe plus `SPY`, and local SEC Companyfacts
  rows whose `filed` date is <= the signal date.
- Requires EPS and/or revenue year-over-year growth points, positive current
  operating income, `gross_margin >= 0.40` from filed-date revenue plus gross
  profit or cost-of-revenue fallback, a liquid above-50d trend state,
  nonnegative 20d excess return versus SPY, and high RS percentile across the
  available 20/60/120d windows.
- Emits ranked candidates but opens at most one paper entry per day, with
  fixed `$10k` base paper notional, next-open paper entry, 10-trading-day close
  exit, closed outcomes, replacement-value summary, the accepted closed-ledger
  ticker profit-cap / global drawdown governor, accepted low-volume,
  filing-recency, filing-timeliness, and PIT liabilities/assets low-liability
  paper-notional support. The accepted cost-liquidity support gives selected
  candidates `1.05x` default-off paper notional only when signal-day
  `avg_dollar_volume_20 >= $200m` and `(high-low)/close <= 0.10`. Candidate
  metadata includes gross-margin status, value, source, filed-date provenance,
  operating-income filed-date lag from fiscal period end, and
  `cost_liquidity_*` OHLCV audit fields.

Agent rule: this sleeve may collect forward replacement-value evidence for the
accepted alpha. It must not enable orders, expand the core universe, alter live
ranking, sizing, exits, LLM/news, or consume live capital without a separate
Gate 1-4 activation experiment and parity update. Do not retune the
Companyfacts growth, operating-profit, gross-margin, RS, top-N, hold-day,
fixed-notional, low-volume, filing-recency, filing-timeliness, low-liability, or
cost-liquidity threshold/scalar, or closed-ledger-scalar parameters on the
frozen sample without forward rows or a new production-visible field.

### `quant/finra_iwm_paper_sleeve.py`

Purpose: maintain the default-off `FINRA_IWM_CONFIRMED_PAPER` forward
observation ledger for the accepted FINRA short-pressure + IWM confirmation +
same-ticker cooldown candidate-pool lead from `exp-20260530-007`.

Candidate route:

- Uses official FINRA biweekly short-interest rows only when
  `publication_date <= signal_date`.
- Requires the fixed OHLCV breakout/liquidity/relative-strength gates from
  `exp-20260529-017`.
- Requires the accepted IWM risk-appetite confirmation from `exp-20260530-005`:
  `IWM 20d return - SPY 20d return >= 0.003`.
- Applies the accepted seven-calendar-day same-ticker admitted-candidate
  cooldown from `exp-20260530-007`.
- Applies the accepted `exp-20260601-029` cost-liquidity support scalar:
  selected candidates with signal-day `dollar_volume >= $200m` and
  `(high-low)/close <= 0.10` receive `1.05x` default-off paper notional.
- Tracks fixed `$10k` base paper notional, supported paper notional,
  next-open paper entry, 10-trading-day paper hold, closed outcomes, and
  concentration blockers only.

Agent rule: this sleeve may collect forward replacement-value evidence for the
accepted alpha. It must not enable orders, expand the core universe, alter live
ranking, sizing, exits, LLM/news, or consume live capital without a separate
Gate 1-4 activation experiment and parity update. Do not retune the FINRA
score, IWM/SPY threshold, cooldown length, top-N, hold-day, base notional, or
cost-liquidity threshold/scalar on the frozen sample without forward rows or a
stronger borrow-cost/availability field.
The adapter emits `cost_liquidity_support` snapshot summary metadata plus
per-candidate `finra_iwm_cost_liquidity_*` fields; these fields are known after
signal-day close before next-open paper entry and never enable live orders.

### `quant/default_off_alpha_attribution.py`

Purpose: roll up promotion readiness and blocker reasons across default-off
alpha sleeves in one production-visible report surface.

Inputs:

- `pilot_attribution` / `ai_infra_aggressive_attribution`
- `sec_financial_report_event_sleeve`
- `event_sleeve_bundle`
- `state_surface_sleeve`
- `low_deployment_etf_overlay`
- `core_misfit_paper_sleeve`
- `broad_market_paper_sleeve`
- `ai_optical_paper_sleeve`
- `volume_breadth_breakout_paper_sleeve`
- `post_earnings_underpriced_drift_paper_sleeve`
- `fundamental_growth_rs_paper_sleeve`

Output keys:

- `default_off_alpha_attribution.surface_count`
- `default_off_alpha_attribution.status_counts`
- `default_off_alpha_attribution.eligible_for_separate_activation_review`
- `default_off_alpha_attribution.top_blockers`
- `default_off_alpha_attribution.surfaces`

Agent rule: this is a read-only activation and blocker dashboard. It may help
choose the next alpha or production-activation experiment, but no trade rule,
LLM prompt, sizing path, ranking path, exit path, or order adapter may consume
it without a separate Gate 1-4 promotion.

### `quant/experiments/exp_20260525_017_expectation_residual_leadership_attribution.py`

Purpose: production-visible, read-only attribution for the Expectation Drift x
Residual Leadership direction. `quant/run.py` refreshes it after the daily
`quant_signals_YYYYMMDD.json` artifact is written, so it can join persisted
candidate objects to PIT estimate-revision ledger rows and residual-strength
context without affecting the daily decision path.

Output:

```text
data/experiments/exp-20260525-017/expectation_residual_leadership_attribution.json
experiments/artifacts/exp-20260525-017_expectation_residual_leadership_attribution.md
experiments/logs/exp-20260525-017_expectation_residual_leadership_attribution.json
```

Agent rule: this observer may update coverage, bucket outcomes, and gate status
only. Its Bucket A/B/C/D result must not change entries, exits, ranking, sizing,
LLM prompts, paper sleeves, or orders. A passing result only unlocks a separate
Gate 1-4 PEAD paper sleeve or ranking-component experiment.

The artifact may also include `reconstructed_scout`, a non-PIT historical
triage view that reads reconstructed ledger 7d deltas when present. Scout rows
can help decide whether more PIT accumulation or a paid PIT data source is worth
pursuing, but they cannot satisfy the primary gate, alter the Bucket A/B/C/D
decision, or promote live logic.

### `quant/experiments/exp_20260525_021_expectation_residual_readiness_audit.py`

Purpose: read-only readiness audit for the Expectation Drift x Residual
Leadership attribution path. It explains whether `exp-20260525-017` has enough
PIT estimate-revision joins, residual-strength context, and closed 5/10/20-day
forward outcomes to be interpreted.

Output:

```text
data/experiments/exp-20260525-021/expectation_residual_readiness_audit.json
experiments/artifacts/exp-20260525-021_expectation_residual_readiness_audit.md
experiments/logs/exp-20260525-021.json
```

Agent rule: this audit may only report readiness, missing-field reasons, and
the exact rerun command for `exp-20260525-017`. It must not relax the positive
expectation definition, create a fallback for missing `eps_estimate_delta_7d`,
or unlock PEAD/ranking/sizing work unless its readiness gate passes.

### `quant/experiments/exp_20260525_023_expectation_revision_coverage_repair.py`

Purpose: read-only measurement repair for the expectation-revision leg of the
Expectation Drift x Residual Leadership direction. It explains why persisted
candidate objects do or do not join to PIT estimate-revision ledger rows and
why usable 7d/30d EPS deltas are absent.

Output:

```text
data/experiments/exp-20260525-023/expectation_revision_coverage_repair.json
experiments/artifacts/exp-20260525-023_expectation_revision_coverage_repair.md
experiments/logs/exp-20260525-023.json
```

Agent rule: this repair may classify coverage blockers only. It must not treat
missing `eps_estimate_delta_7d` as positive expectation, must not change
candidate generation, ranking, sizing, exits, LLM/news, paper sleeves, or
orders, and must route any alpha interpretation back through
`exp-20260525-021` before `exp-20260525-017`.

### `quant/experiments/exp_20260525_025_estimate_revision_snapshot_dedupe_repair.py`

Purpose: measurement-repair record for the estimate-revision snapshot de-dupe
guard. It audits whether duplicate organized/legacy earnings snapshots change
candidate-level PIT usability and records the repair evidence.

Output:

```text
data/experiments/exp-20260525-025/estimate_revision_snapshot_dedupe_repair.json
experiments/artifacts/exp-20260525-025_estimate_revision_snapshot_dedupe_repair.md
experiments/logs/exp-20260525-025.json
```

Agent rule: this experiment may justify rebuilding affected default-off
estimate-revision ledgers only. It does not unlock Bucket A interpretation,
PEAD paper sleeves, ranking changes, sizing changes, exits, LLM/news changes,
or orders unless `exp-20260525-021` later passes.

### `quant/experiments/exp_20260525_031_revision_lead_window_attribution.py`

Purpose: read-only attribution for short-lag EPS estimate-revision leads. It
tests whether a PIT-usable positive same-event `eps_estimate_delta_prev` can
appear 0-3 trading days before a persisted Ginger candidate object, including
weekend snapshot dates whose effective trade date is the next OHLCV trading
day.

Output:

```text
data/experiments/exp-20260525-031/revision_lead_window_attribution.json
experiments/artifacts/exp-20260525-031_revision_lead_window_attribution.md
experiments/logs/exp-20260525-031.json
```

Agent rule: this experiment may report candidate buckets, forward outcomes,
and current-position overlap only. It must not change entries, exits, ranking,
sizing, LLM/news, paper sleeves, or orders. A promising result only unlocks a
separate default-off PEAD paper sleeve or ranking-component experiment.

### `quant/experiments/exp_20260525_034_expectation_revision_watchlist_attribution.py`

Purpose: read-only attribution for a larger expectation-revision watchlist.
Instead of requiring a same-day Ginger candidate object, it starts from every
PIT-usable `estimate_revision_ledger` row, classifies strict
`eps_estimate_delta_7d > 0` expectation drift, records a wider non-promotable
watchlist using 7d / 30d / previous-snapshot positive revision evidence, and
joins residual leadership, later candidate hits, current-position overlap, and
5/10/20-day forward outcomes.

Output:

```text
data/experiments/exp-20260525-034/expectation_revision_watchlist_attribution.json
experiments/artifacts/exp-20260525-034_expectation_revision_watchlist_attribution.md
experiments/logs/exp-20260525-034.json
```

Agent rule: this experiment may grow a default-off research watchlist and
report bucket evidence only. The wide watchlist is evidence-accumulation
metadata, not a trade queue. It must not change entries, exits, ranking,
sizing, LLM/news, paper sleeves, or orders. A passing strict primary readout
only unlocks a separate PEAD paper sleeve or ranking-component experiment.

### `quant/experiments/exp_20260526_006_expectation_revision_overextension_attribution.py`

Purpose: read-only follow-up to the expectation-revision watchlist inversion.
It starts from the strict PIT-positive `eps_estimate_delta_7d > 0` rows emitted
by `exp-20260525-034` and tests whether residual leadership behaves more like
an overextension state than a confirmation state.

Output:

```text
data/experiments/exp-20260526-006/expectation_revision_overextension_attribution.json
experiments/artifacts/exp-20260526-006_expectation_revision_overextension_attribution.md
experiments/logs/exp-20260526-006.json
```

Agent rule: this experiment may report `non_overextended` versus
`overextended_residual_leader` bucket evidence only. It must not change
entries, exits, ranking, sizing, LLM/news, paper sleeves, or orders. A
directional result can only justify a separate forward default-off watchlist or
ranking-component experiment after concentration and closed-outcome maturity
are sufficient.

### `quant/experiments/exp_20260526_030_expectation_direction_untried_ideas_suite.py`

Purpose: read-only batch runner for the remaining untried ideas named in
`docs/alpha_direction_expectation_residual_leadership.md`. It writes separate
experiment records for revision velocity, PEAD readiness, surprise/guidance
coverage, ranking replacement proxy, full residual dimensions, promotion-metric
completeness, and breadth/theme context.

Output:

```text
data/experiments/exp-20260526-030/expectation_revision_velocity_attribution.json
data/experiments/exp-20260526-031/expectation_pead_readiness_probe.json
data/experiments/exp-20260526-032/expectation_guidance_surprise_coverage.json
data/experiments/exp-20260526-033/expectation_ranking_replacement_probe.json
data/experiments/exp-20260526-034/expectation_full_residual_dimension_probe.json
data/experiments/exp-20260526-035/expectation_attribution_metric_completeness.json
data/experiments/exp-20260526-036/expectation_breadth_theme_context_probe.json
experiments/artifacts/exp-20260526-030_expectation_revision_velocity_attribution.md
...
experiments/artifacts/exp-20260526-036_expectation_breadth_theme_context_probe.md
```

Agent rule: each output is an observed-only probe with its own single causal
variable. These probes may identify data gaps or future default-off paper/rank
tests only. They must not change entries, exits, candidate ranking, sizing,
LLM prompts, paper sleeves, or orders.

### `quant/experiments/exp_20260528_005_expectation_watchlist_old_alpha_score_join.py`

Purpose: read-only measurement repair for the blocked expectation ranking
replacement probe. It rebuilds the existing continuous cross-sectional ranking
surface by `feature_context_date` and joins `old_alpha_score`, rank, rank
bucket, and component diagnostics back to the expectation-revision watchlist
rows from `exp-20260525-034`.

Output:

```text
data/experiments/exp-20260528-005/expectation_watchlist_old_alpha_score_join.json
experiments/artifacts/exp-20260528-005_expectation_watchlist_old_alpha_score_join.md
experiments/logs/exp-20260528-005.json
```

Agent rule: this experiment repairs attribution coverage only. It may unlock a
future true old-score versus old-score-plus-expectation ranking experiment, but
it must not change entries, exits, candidate ranking, sizing, LLM prompts,
paper sleeves, or orders.

### `quant/experiments/exp_20260528_007_expectation_true_ranking_replacement_attribution.py`

Purpose: read-only alpha attribution for the true expectation ranking
replacement question. For every `feature_context_date` with expectation
watchlist coverage, it ranks the full daily cross-sectional surface by the old
`alpha_score` and by `alpha_score + expectation_residual_component_score`, then
compares the combined top-decile, retained rows, new combined top-decile rows,
and old top-decile rows that were displaced.

Output:

```text
data/experiments/exp-20260528-007/expectation_true_ranking_replacement_attribution.json
experiments/artifacts/exp-20260528-007_expectation_true_ranking_replacement_attribution.md
experiments/logs/exp-20260528-007.json
```

Agent rule: this experiment may only report whether the simple additive
expectation/residual component has replacement value on a full daily ranking
surface. It must not change entries, exits, candidate ranking, sizing, LLM
prompts, paper sleeves, or orders. Any promotion requires a separate Gate 1-4
strategy experiment with shared production-visible ranking logic.

### `quant/experiments/exp_20260528_009_expectation_pead_repaired_bucket_attribution.py`

Purpose: read-only alpha attribution for the expectation-revision PEAD line
after `exp-20260527-908` repaired PIT `last_earnings_date` and `pead_status`
coverage. It compares primary-positive revision rows across inside-T+2..T+15
non-overextended, inside-T+2..T+15 residual-leader, outside-PEAD, and
still-missing earnings-date buckets using closed 5d/10d/20d forward outcomes.

Output:

```text
data/experiments/exp-20260528-009/expectation_pead_repaired_bucket_attribution.json
experiments/artifacts/exp-20260528-009_expectation_pead_repaired_bucket_attribution.md
experiments/logs/exp-20260528-009.json
```

Agent rule: this experiment may only decide whether repaired PEAD buckets have
enough closed outcome evidence to justify a later default-off Gate 1-4 strategy
experiment. It must not change entries, exits, candidate ranking, sizing, LLM
prompts, paper sleeves, or orders.

### `quant/experiments/exp_20260528_013_expectation_pead_short_horizon_repaired_attribution.py`

Purpose: read-only alpha attribution for the short-horizon PEAD question after
the PIT `last_earnings_date` repair. It reads the same
`exp-20260527-908` enriched watchlist as `exp-20260528-009`, recomputes fresh
1d/2d/3d forward outcomes from local weekday close snapshots, and compares
inside-T+2..T+15 non-overextended, inside-T+2..T+15 residual-leader,
outside-PEAD, and still-missing earnings-date buckets.

Output:

```text
data/experiments/exp-20260528-013/expectation_pead_short_horizon_repaired_attribution.json
experiments/artifacts/exp-20260528-013_expectation_pead_short_horizon_repaired_attribution.md
experiments/logs/exp-20260528-013.json
```

Agent rule: this experiment may only decide whether the repaired PEAD bucket
has near-term attribution value before longer 5d/10d outcomes mature. It must
not change entries, exits, candidate ranking, sizing, LLM prompts, paper
sleeves, or orders.

### `quant/experiments/exp_20260528_029_expectation_outside_pead_deconcentration_attribution.py`

Purpose: read-only follow-up to `exp-20260528-013` for the outside-PEAD
short-horizon question. It reuses the corrected weekday close outcome builder,
then tests whether the primary-positive outside-T+2..T+15 bucket remains
positive after removing the largest positive ticker contributor and after
first-row-per-ticker de-duplication.

Output:

```text
data/experiments/exp-20260528-029/expectation_outside_pead_deconcentration_attribution.json
experiments/artifacts/exp-20260528-029_expectation_outside_pead_deconcentration_attribution.md
experiments/logs/exp-20260528-029.json
```

Agent rule: this experiment may only audit concentration and replacement-value
readiness for the outside-PEAD short-horizon bucket. It must not change
entries, exits, candidate ranking, sizing, LLM prompts, paper sleeves, or
orders.

---

## Tail / allocation / decay / heat diagnostics

### `quant/evaluator_gates.py`

Purpose: tail-aware gate report for strategy / sleeve metrics.

Checks include:

- negative skew;
- excess kurtosis;
- weak tail ratio;
- top-5 PnL concentration;
- HHI concentration;
- drawdown breach;
- live vs backtest decay.

Agent rule: use for diagnostics and promotion readiness. Do not treat passing gates as automatic trade approval.

### `quant/allocation_engine.py`

Purpose: promotion-gated, tail-aware capital allocation preview.

Important: currently a scoring/preview tool. It should not be wired into live capital without an accepted experiment.

### `quant/decay_monitor.py`

Purpose: rolling live/backtest health diagnostics.

Default windows: 10 / 20 / 50 trades.

Flags include:

- rolling R decay;
- non-positive rolling EV;
- negative rolling skew;
- weak rolling tail ratio.

### `quant/portfolio_heat_engine.py`

Purpose: detect fake diversification and crowding.

Diagnostics include:

- sector exposure;
- theme exposure;
- theme-cluster exposure;
- HHI concentration;
- heat flags.

### `quant/backtest_readonly_diagnostics.py`

Purpose: sidecar diagnostics for canonical backtest result JSON files.

Usage:

```powershell
python quant/backtest_readonly_diagnostics.py result.json
```

Output: `<result_stem>_diagnostics.json`

---

## Meta research tooling

### `quant/meta_research_engine.py`

Purpose: study the research process itself.

Reads:

```text
docs/experiment_log.jsonl
docs/experiments/logs/*.json
```

Outputs:

- `by_family`
- `by_change_type`
- `top_experiments`
- `worst_experiments`
- `freeze_candidates`
- `research_priorities`
- `recommendations`

Important: priority scores are research queue scores only. They are not trading signals and must not determine live sizing.

---

## Agent checklist before using these tools in a strategy experiment

Before turning any context field into entry / exit / ranking / sizing logic, answer:

1. Is the field produced in production, not just in a research script?
2. Is the field saved in an append-only, replayable daily artifact?
3. Does the backtester have point-in-time access to it?
4. Has attribution shown monotonic or otherwise interpretable predictive value?
5. Does the proposed change alter only one independent causal variable?
6. Does the change pass `docs/backtesting.md` Gate 1-4?
7. Is the experiment recorded in `docs/experiment_log.jsonl` whether accepted or rejected?

If the answer to 1-4 is no, keep the surface read-only and continue accumulating history.
