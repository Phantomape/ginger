# Alpha Optimization Playbook

Last refreshed: 2026-05-29.

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
  Accepted low-volume, filing-recency, and low-liability balance-sheet support
  improved the shared default-off paper adapter, but the sleeve is now mature
  enough that nearby frozen-sample scalar retunes should stop; collect forward
  replacement-value rows first.
- `VOLUME_BREADTH_BREAKOUT_PAPER` and QQQ-confirmed VCP show that free OHLCV
  market-confirmation fields can produce useful paper sleeves. Their next step
  is forward maturation, not another breadth/QQQ/top-N sweep.
- Space remains observe-only, but `exp-20260528-026` showed that a new
  production-visible OHLCV field (`daily_close_location >= 0.84` on
  governed Space `trend_long` signal days) can separate better paper candidates
  from old-window losers. Treat it as a forward evidence bucket, not permission
  to retune high-close thresholds or enable live Space slots.
- Kova/CANSLIM-style intraday, base, pocket-pivot, distribution-day, 13F, and
  RS fields are useful context sidecars, but recent tests repeatedly failed to
  justify new gates, exits, pyramids, or notional scalars on the frozen sample.
  The one constructive lifecycle clue, early shakeout then reclaim in
  `exp-20260529-006`, was positive but only `7` trades, so it is forward
  monitoring context rather than a rule.
- Expectation/PEAD/residual-leadership work is still mostly attribution and
  measurement repair. The latest useful result is better PIT joins and ranking
  replacement attribution, not a promoted live rule.
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
  `VOLUME_BREADTH_BREAKOUT_PAPER`, QQQ-confirmed VCP, and broad-market paper;
- add cost-adjusted replacement value where spread/liquidity data is available;
- compare selected rows against same-day core candidates and adjacent paper
  ranks;
- expose activation blockers in `default_off_alpha_attribution`.

Do not do next:

- retune Companyfacts growth, RS percentile, top-N, hold days, or fixed notional
  on the same windows;
- retune VCP QQQ/SPY, ATR compression, pocket-pivot, base geometry, or
  distribution-day gates without new forward evidence;
- promote paper sleeves into live capital only because historical paper PnL is
  large.

### 2. Fundamental Growth + RS

Mechanism: filed-date-safe Companyfacts growth plus positive operating-profit
quality plus OHLCV relative strength is a real candidate-pool lead. The useful
change was not "another fundamental filter"; it was a new default-off candidate
source with a closed-ledger governor for concentration/drawdown.

Keep fixed:

- PIT Companyfacts filed-date boundary;
- EPS/revenue growth points;
- positive operating income quality gate;
- RS proxy and top-1/day paper route;
- next-open entry and 10-trading-day paper exit;
- closed-ledger profit cap / drawdown governor.

Next valid fields:

- cash-conversion quality only if it improves forward replacement value;
- gross-margin / operating-margin durability;
- filing-timeliness, low-liability balance-sheet quality, and
  restatement/disclosure-quality context;
- cost-adjusted liquidity state.

### 3. Volume-Breadth And VCP Sleeves

Mechanism: market participation confirmation is more valuable than retuning
price-shape thresholds. Volume-breadth breakout and QQQ-confirmed VCP should
stay as default-off paper adapters until closed forward rows mature.

Keep fixed:

- volume-breadth top-1/day, fixed `$10k` base notional, accepted
  breadth-intensity support (`volume_breadth_fraction >= 0.25`, `1.10x`), and
  10-day paper hold;
- VCP QQQ-confirmed top-2 route and `[1.0, 1.25]` rank-notional profile.

Next valid work:

- forward replacement value by breadth/regime/cost bucket;
- hidden Nasdaq beta attribution;
- concentration and decay monitoring;
- candidate-rank breadth diagnostics.

Frozen without new evidence:

- volume-breadth breadth-intensity threshold/scalar retunes on the frozen
  sample;
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

Useful fields:

- `retrieval_strategy_bucket`
- `retrieval_trace_id`
- `retrieval_source_doc_id`
- `retrieval_section_id`
- `metadata_filter_json`
- `retrieval_failure_bucket`
- `cross_period_consistency_bucket`
- `numeric_evidence_json`

Engineering rule: no retrieval trace means no Gate 4 trading field.

Sources:

- FinAgent-RAG, 2026-05-06: <https://arxiv.org/abs/2605.05409>
- Rethinking Retrieval in financial LLM systems, 2025: <https://arxiv.org/abs/2511.18177>
- Financial-report RAG with reranking, 2026: <https://arxiv.org/abs/2603.16877>

### Event Graphs And Multi-Modal Market Context

New financial forecasting research increasingly treats news, fundamentals,
prices, and relational spillovers as graphs or multi-modal state. For Ginger,
this supports event-interaction and theme-propagation fields, not free-form LLM
trade calls.

Useful fields:

- `event_interaction_graph_bucket`
- `same_theme_event_burst_count`
- `source_disagreement_bucket`
- `ticker_to_theme_propagation_bucket`
- `first_reaction_vs_followon_event_bucket`
- `media_spillover_relation_bucket`

Sources:

- Multi-graph heterogeneous market information forecasting, 2026:
  <https://www.sciencedirect.com/science/article/pii/S0957417426010559>
- NEXUS financial news interactions, 2026:
  <https://www.sciencedirect.com/science/article/pii/S0957417426013242>

### Transaction-Cost-Aware Allocation

Transaction costs should be visible before allocation, not only subtracted after
the backtest. This is especially important for high-turnover paper sleeves.

Useful fields:

- `expected_round_trip_cost_bucket`
- `spread_liquidity_cost_bucket`
- `turnover_pressure_bucket`
- `cost_adjusted_replacement_value_pnl`
- `cost_adjusted_rank_delta`
- `fill_delay_risk_bucket`

Sources:

- Large-scale portfolio allocation under transaction costs, SSRN:
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3043216>
- Portfolio optimization with linear/fixed transaction costs, Boyd:
  <https://web.stanford.edu/~boyd/papers/portfolio.html>

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
