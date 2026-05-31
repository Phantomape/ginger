# Alpha Optimization Playbook

Last refreshed: 2026-05-30.

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
  adapter. Treat it like Fundamental Growth RS and VBB: forward replacement
  rows first, no FINRA score / IWM threshold / cooldown / top-N retunes on the
  same frozen windows.
- Space remains observe-only, but `exp-20260528-026` showed that a new
  production-visible OHLCV field (`daily_close_location >= 0.84` on
  governed Space `trend_long` signal days) can separate better paper
  candidates from old-window losers. `exp-20260529-020` added one incremental
  existing OHLCV field (`signal_day_ticker_open_close_return_pct >= 0.04`) on
  that accepted route, improving aggregate EV by `+0.0282` versus the
  high-close baseline by removing one weak-thrust stopout. Treat both as
  forward evidence buckets, not permission to retune Space price-action
  thresholds or enable live Space slots.
- The 2026-05-28/29 candidate-pool scouts rejected VWAP reclaim, long-base
  breadth, industry-leadership high-close/no-core-overlap, sector/market
  breadth agreement, ticker accumulation-quality breakout, Form 4 role quality,
  and AI optical low-close support. The durable lesson is that "reasonable"
  OHLCV pattern names are not enough; new pools need either a clearly new
  production-visible information source or immediate replacement-value evidence.
- Kova/CANSLIM-style intraday, base, pocket-pivot, distribution-day, 13F, and
  RS fields are useful context sidecars, but recent tests repeatedly failed to
  justify new gates, exits, pyramids, or notional scalars on the frozen sample.
  The one constructive lifecycle clue, early shakeout then reclaim in
  `exp-20260529-006`, was positive but only `7` trades, so it is forward
  monitoring context rather than a rule.
- Expectation/PEAD/residual-leadership work is still mostly attribution and
  measurement repair. The latest useful result is better PIT joins and ranking
  replacement attribution, not a promoted live rule.
- Form 4 remains watchlist material, not a clean candidate-pool lead. The
  latest multi-filer / owner-count replay (`exp-20260530-011`) was positive
  versus core but failed replacement value versus the raw Form 4 queue,
  materiality, sample, window coverage, and concentration guards. Do not
  promote owner-count alone or retry adjacent Form 4 role/owner-count fields
  without forward replacement rows or a new ownership-intensity mechanism.
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
  QQQ-confirmed VCP, and broad-market paper;
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

Frozen without new evidence:

- low-capex intensity, dual growth, gross-margin expansion, operating-margin
  durability, working-capital discipline, liquidity sweet spot, and recent VBB
  source-agreement notional support on the current frozen Companyfacts sample;
- any new Companyfacts scalar whose best case still depends on the already
  accepted operating-profit + RS stack rather than a new candidate source;
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

Local update: `exp-20260531-003` tested a free earnings-snapshot
`earnings_imminent_surprise_rs_candidate_source_v1` using the 1-7 day
pre-earnings window, durable positive historical surprise behavior, liquid
trend/RS confirmation, top-1/day, and a fixed 10-trading-day paper exit. It
was strongly positive in aggregate (`+3.3705` EV / `+$67,089.07`) but failed
Gate 4 because `late_strong` regressed (`-1.2475` EV / `-$16,159.23`) and max
drawdown drift was too high. `exp-20260531-004` then held that candidate
source fixed and changed only the lifecycle to exit before the earnings event.
That also failed: aggregate EV fell `-0.2235`, `late_strong` still regressed
(`-0.6113` EV / `-$4,136.93`), and max drawdown drift stayed too high
(`+1.90 pp`). Do not retry nearby imminent-earnings snapshot thresholds,
top-N, or pre-event hold/exit variants on the same frozen windows without
closed forward replacement-value rows or a materially richer
expectation-quality field.

### 4b. Pattern-Name Candidate Pools

Mechanism: the last batch of OHLCV pattern-name pools did not survive Gate 4.
VWAP reclaim, long-base breadth confirmation, industry leadership, sector
breadth agreement, and ticker accumulation-quality breakout are plausible
descriptions, but the frozen evidence says they are not sufficient candidate
sources by themselves.

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
- borrow-cost, borrow-availability, utilization, or options-implied squeeze
  context if a clean PIT source is added;
- cost-adjusted liquidity and fill-delay diagnostics.

Frozen without new evidence:

- FINRA score threshold, IWM/SPY threshold, cooldown length, top-N, hold-day,
  and fixed-notional retunes on the current frozen sample;
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

Engineering rule: no retrieval trace means no Gate 4 trading field.

Sources:

- FinAgent-RAG, 2026-05-06: <https://arxiv.org/abs/2605.05409>
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

Useful fields:

- `agent_decision_stage`
- `agent_evidence_ledger_id`
- `agent_action_schema_version`
- `agent_replay_split_id`
- `agent_transaction_cost_model_id`
- `agent_universe_pit_policy_id`
- `agent_execution_semantics_bucket`
- `agent_reproducibility_tier`

Engineering rule: an LLM agent can propose hypotheses or classify evidence,
but a trade-impacting action must still become a shared, replayable policy and
pass Gate 1-4.

Source:

- Agentic Trading: When LLM Agents Meet Financial Markets, 2026:
  <https://arxiv.org/abs/2605.19337>

### Event Graphs And Multi-Modal Market Context

New financial forecasting research increasingly treats news, fundamentals,
prices, and relational spillovers as graphs or multi-modal state. For Ginger,
this supports event-interaction and theme-propagation fields, not free-form LLM
trade calls.

Recent peer-information and graph-learning work points to two practical
directions: characteristic-similarity peer groups and early-peer earnings
transfer. These are more actionable than another price-pattern pool because
they create a testable "who should react to whom" relation before the trade.

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

Sources:

- Multi-graph heterogeneous market information forecasting, 2026:
  <https://www.sciencedirect.com/science/article/pii/S0957417426010559>
- NEXUS financial news interactions, 2026:
  <https://www.sciencedirect.com/science/article/pii/S0957417426013242>
- Graph learning on financial networks from firm-characteristic similarity,
  2026: <https://link.springer.com/article/10.1007/s41109-025-00755-2>
- Algorithmic trading and intra-industry information transfer, 2026:
  <https://link.springer.com/article/10.1007/s11142-026-09954-3>

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

### Transaction-Cost-Aware Allocation

Transaction costs should be visible before allocation, not only subtracted after
the backtest. This is especially important for high-turnover paper sleeves.
The accepted VBB cost/liquidity support is the local proof point: a simple
production-visible liquidity/range state can be a cleaner allocation field than
another alpha-shape threshold.

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
- VWAP-reclaim, long-base, industry-leadership, sector-breadth-agreement, or
  accumulation-quality candidate-pool retries on the same OHLCV-only frozen
  sample;
- raw SEC same-family burst, first/follow-on, same-ticker cross-family
  transition, or Form 4 owner-count retries without a richer relation or
  ownership-intensity mechanism;
- simple pre-entry high-confidence catalyst freshness or source/category
  diversity retries on the `exp-20260530-014` core trade rows without a
  materially richer catalyst-quality field or forward replacement-value
  evidence;
- SEC financial-report activation reviews or semantic allocation scalars while
  the production forward sleeve has zero candidates and zero closed
  replacement-value rows;
- Companyfacts support-scalar mining around the accepted operating-profit + RS
  stack;
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
