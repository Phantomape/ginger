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
   - Useful fields: ticker vs SPY, ticker vs QQQ, ticker vs theme / peer basket.

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
