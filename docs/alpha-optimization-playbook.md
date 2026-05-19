# Alpha Optimization Playbook

This file is the durable synthesis layer between
[`AGENTS.md`](D:/Github/ginger/AGENTS.md),
[`docs/backtesting.md`](D:/Github/ginger/docs/backtesting.md), and
[`docs/experiment_log.jsonl`](D:/Github/ginger/docs/experiment_log.jsonl).

It is not an experiment diary. Its purpose is to compress repository evidence
into:

- mechanism-level priors;
- anti-repeat rules;
- field-building standards;
- the current research queue for new alpha.

Last refreshed: 2026-05-18.

## How To Use This Playbook

Before changing strategy logic, answer:

1. Is the next idea primarily `allocation`, `field`, `entry`, `exit`,
   `candidate_pool`, or `measurement_repair`?
2. Has a nearby version already failed on the canonical windows?
3. Can the idea be expressed as one production-visible and replayable variable?
4. If not, which field, logging, or parity gap blocks it?

Default workflow:

1. Prefer `alpha_search` over `measurement_repair` unless measurement is the
   direct blocker.
2. Prefer fixed candidate set plus better capital routing over broader
   filtering.
3. Prefer one new field over one more scalar retune.
4. Prefer shared production-visible policy over backtest-only logic.
5. Prefer default-off paper sleeves before live promotion.

## Executive Summary

Ginger is still best understood as an event-enhanced medium-term trend /
breakout system. The current repo evidence says:

1. Core candidate generation is not the main bottleneck.
2. Most accepted alpha has come from narrow, capped, state-conditioned
   allocation changes on already-qualified signals.
3. Broad filters, broad reranking, and generic lifecycle rewrites are
   persistently lower quality than allocation changes.
4. Event alpha is real only when it proves replacement value against the next
   core use of capital.
5. LLM value comes from structured extraction and attribution, not from owning
   hard risk or execution decisions.
6. Default-off paper sleeves are now the correct incubation layer for new event
   families, candidate pools, and thematic cohorts.

Recent accepted work does not change that worldview:

- Core alpha still mostly comes from small post-sizing promotions on
  production-visible states.
- The state-surface sleeve improved when the candidate definition stayed tight
  and only paper allocation changed; the latest score-compression, rank-2
  ret20-lead, and score/ret20 disagreement refinements support queue-quality
  fields as better alpha inputs than another nearby breadth scalar.
- Core-misfit evidence is strongest as candidate-pool governance, not as live
  shorting: the default-off paper sleeve now observes only `trend_long`
  misfit signals after the combined `trend_long + breakout_long` scope proved
  more window-fragile.
- The latest measurement repair showed that strong paper PnL is still not
  promotion-ready when tail concentration is too high.

Interpretation: the next wave of alpha is more likely to come from better
fields and better sleeve governance than from nearby scalar tuning on the core
stack.

## Durable Mechanism Laws

### 1. Allocation Beats Filtering

Strong prior:

- small post-sizing top-ups on already-qualified signals;
- narrow state-conditioned risk promotions;
- sleeve-specific capital routing on a fixed candidate set;
- replacement-value routing before live promotion.

Weak prior:

- broad new filters;
- broad slot reranking;
- broad quality overlays;
- broad candidate-pool expansion into core;
- mirror-image penalties without independent evidence.

Default decision rule:

- If a proposal changes who is broadly allowed to trade, assume weak prior.
- If a proposal changes how already-good signals are sized, assume stronger
  prior.

### 2. One Good Field Beats One More Generic Rule

The repo repeatedly shows that noisy cohorts are not rescued by stacking more
generic guards.

Default rule:

- add one ex-ante state variable before adding another broad filter;
- keep the candidate set fixed when possible;
- if an idea needs many exceptions, it is probably overfit.

### 3. Replacement Value Beats Narrative Quality

Event stories are not sufficient. A sleeve earns attention only when it can
answer:

- why this candidate deserves capital over the next core slot;
- whether the outcome beats cash or the displaced candidate;
- whether the edge survives outside one cluster of winners.

Default rule:

- event work must eventually produce replacement-value evidence;
- label quality without capital-routing evidence is research, not alpha.

### 4. Small, Capped, Conditional Changes Dominate Big Rewrites

Accepted changes are usually:

- small in magnitude;
- narrow in scope;
- based on already-known fields;
- neutral to trade count and survival;
- controlled on drawdown drift.

Rejected changes are usually:

- global retunes;
- broad lifecycle rewrites;
- broad slot-priority changes;
- adjacent scalar mining after a state is already accepted.

### 5. Ticker Exceptions Are Valid but Should Stay Rare

Ticker-specific exceptions can be real, but they are dangerous to generalize.

Default rule:

- a ticker exception is acceptable only when it improves multiple windows and
  stays production-visible;
- it does not justify a sector rule by itself;
- once accepted, nearby retries stay frozen until new forward evidence exists.

### 6. Bad Longs Are Not Automatically Good Shorts

The core-misfit work supports three separate questions:

- is the cohort negative expected value for core longs?
- is there a fast-exit rescue?
- is there true inverse alpha after costs and sample controls?

Default rule:

- no-trade avoided value can justify a paper sleeve first;
- inverse evidence is still paper research until forward outcomes and
  execution-friction evidence mature.
- `exp-20260518-019` sharpened the core-misfit short read: the blanket
  fixed-10d inverse was old-window concentrated, but the production-visible
  `trend_long_only` condition produced `+$5,799.05` across 7 trades with both
  observed windows positive. Treat this as a paper observation priority for
  `CORE_MISFIT_PAPER`, not as a live short adapter; the mid-window proof is
  still one tiny trade and borrow/locate costs are unmodelled.
- `exp-20260518-022` promoted that evidence only into default-off paper-scope
  governance: `CORE_MISFIT_PAPER` now observes `trend_long` misfit signals by
  default. The stricter gate kept `95.38%` of identity paper inverse PnL while
  improving positive windows, win rate, worst trade, and max drawdown. Do not
  re-add `breakout_long` or expand the ticker set without new forward evidence
  or a new production-visible discriminator.

### 7. LLM Value Comes From Structure, Not Authority

Code owns:

- sizing;
- hard gates;
- risk budgets;
- slot policy;
- execution and lifecycle rules.

LLM owns:

- event understanding;
- topic extraction;
- contradiction detection;
- credibility or commitment tagging;
- catastrophe-style veto candidates;
- semantic surprise and attention structure.

Default rule:

- every LLM contribution should become schema-bound fields with provenance and
  attribution, not free-form trade authority.

### 8. Thin Cohorts Stay Research-Only

Directionally positive evidence is not enough if the rule only changes a few
rows.

Default rule:

- do not promote rules that touch one to three historical rows;
- thin samples should mature through forward evidence, paper sleeves, or a new
  field that widens the cohort honestly.

### 9. Tail Concentration Is A Promotion Blocker

Recent state-surface work adds one durable lesson:

- good paper EV and win rate are insufficient when a small number of winners
  dominate the sleeve.

Default rule:

- forward promotion gates must inspect concentration, not just mean returns;
- when tail concentration blocks promotion, the next step is a new quality or
  regime field, not more nearby notional tuning.
- `exp-20260518-021` rejected rank-2 ret5 leadership as that kind of nearby
  notional tuning: aggregate EV/PnL improved, but the best variant touched only
  6 trades and worsened single-ticker positive-share concentration versus the
  accepted baseline. Do not retry adjacent ret5 queue-notional profiles without
  a new field or forward evidence.
- `exp-20260518-023` accepted a small default-off rank-1 ret20 dominance plus
  score-gap notional field (`+0.0098` aggregate EV, `+$287.87` PnL), but it
  also raised single-ticker positive-share concentration from `36.12%` to
  `36.55%`. Treat this as a marginal incubation improvement, not permission to
  keep mining neighboring state-surface scalars without a new quality field or
  forward evidence.
- `exp-20260518-025` accepted a default-off top-2 Technology sector-cohesion
  notional field (`+0.0759` aggregate EV, `+$1,593.99` PnL), with 2 improved
  windows and no EV-regressed window. Concentration still rose slightly
  (`36.55% -> 36.80%`), so this remains an incubation improvement; do not keep
  mining adjacent sector-cohesion profiles without forward evidence or a new
  independent field.
- `exp-20260518-027` accepted a default-off residual rank-1 ret60 overheat
  notional field after top-2 Technology priority (`+0.1209` aggregate EV,
  `+$1,606.68` PnL), with 2 improved windows and no EV-regressed window. The
  broader `0.40` threshold failed, so do not mine nearby ret60 thresholds or
  override the accepted top-2 Technology priority without forward evidence or a
  new independent field.
- `exp-20260519-001` accepted a default-off residual score-expansion notional
  field (`+0.0552` aggregate EV, `+$725.33` PnL), with 2 improved windows and
  no EV-regressed window. It lowered concentration (`38.01% -> 37.43%`) and
  only applies to generic-breadth residual rows after higher-priority profiles.
  Treat this as a modest incubation improvement; do not mine nearby
  score-expansion thresholds or profiles without forward evidence or a new
  independent field.
- `exp-20260519-002` accepted a default-off recent same-ticker repeat notional
  field (`+0.2685` aggregate EV, `+$4,069.88` PnL), with 2 improved windows and
  no EV-regressed window. It applies after the accepted rank-notional stack:
  if a ticker reappears in the state-surface paper sleeve within `60` calendar
  days, scale that paper entry by `1.50`. Concentration rose (`38.01% ->
  41.28%`) but stayed under the `50%` guardrail. Treat this as a continuation
  field, not an invitation to mine adjacent repeat lookbacks/scalars without
  forward evidence or a distinct crowding-quality variable.
- `exp-20260519-003` accepted a default-off residual rank-1 score-isolation
  notional field (`+0.1039` aggregate EV, `+$1,536.65` PnL), with 2 improved
  windows and no EV-regressed window. It applies only inside the residual
  score-expansion branch when `score_top_to_second_gap >= 0.20`, and shifts
  paper notional toward rank 1 with `[2.2, 1.0, 0.7, 0.675, 0.35]`.
  Concentration improved (`40.70% -> 39.68%`). Treat this as a rank-quality
  field; do not mine adjacent score-gap thresholds or profiles without forward
  evidence or a distinct quality variable.
- `exp-20260519-004` accepted a default-off rank-3 near-high support notional
  field (`+0.1126` aggregate EV, `+$2,024.62` PnL), with all 3 windows
  improved and no drawdown worsening. It applies only when the third ranked
  same-day state-surface candidate has `near_high_60 >= 0.98`, then scales only
  rank 3 by `1.50` after the active profile multiplier. Concentration improved
  (`39.68% -> 38.43%`). Treat this as a rank-depth quality field; do not mine
  adjacent near-high thresholds/scalars on the frozen sample without forward
  evidence or a distinct queue-depth variable.

## What The Recent Logs Mean

Compressing the recent repository evidence into durable conclusions:

- accepted core changes still come mostly from conditional allocation on a
  stable candidate set;
- accepted paper-sleeve changes came from tighter candidate definitions and
  better paper allocation, not from broadening discretion;
- accepted core-misfit work came from narrowing the default-off observation
  scope, not from enabling live shorts or broad no-trade quarantines;
- rejected work was usually broad overlays, pool expansion, slot reranking,
  lifecycle retuning, or sample-thin interaction mining;
- the state-surface sleeve is a valid alpha incubator, but forward promotion is
  blocked until tail concentration improves;
- current high-value work should bias toward field creation, sleeve governance,
  and replacement-value attribution rather than another round of neighboring
  scalars.

## Candidate-Pool And Sleeve Doctrine

Candidate-pool work is valid alpha search when treated as capital governance,
not casual ticker picking.

### Current Ticker Pool Governance

Required evidence:

- ticker-plus-setup contribution across canonical windows;
- replacement value versus the next selected or sliced candidate;
- no-trade avoided value for suspected negative cohorts;
- forward paper outcomes for any proposed quarantine, removal, or inverse
  sleeve;
- exposure concentration and tail-loss contribution.

Valid outputs:

- keep in core;
- keep but down-size through a shared rule;
- move to default-off paper sleeve;
- require more forward evidence;
- remove only after a separate Gate 1-4 experiment.

### Sleeve Segmentation

Preferred sleeve roles:

- `CORE` for proven live capital;
- `CORE_MISFIT_PAPER` for suspicious long cohorts;
- `STATE_SURFACE_SATELLITE` for default-off candidate expansion;
- SEC / earnings event sleeves;
- Form 4 sleeves;
- buyback credibility sleeves;
- mechanical index / passive-flow sleeves;
- thematic pilot sleeves such as Space.

Each sleeve needs:

- its own candidate definition;
- paper/live status;
- capital and slot semantics;
- a forward gate;
- replacement-value metrics;
- promotion and kill criteria.

### All-Market Candidate Discovery

All-market search is valid but starts outside core.

Required controls:

- PIT universe membership;
- delisting and survivorship handling;
- stable liquidity and price gates;
- sector, industry, and theme attribution;
- no future membership or future-document leakage;
- direct comparison to the displaced core use of capital.

Valid first deliverables:

- research-only broad-universe snapshots;
- default-off daily queues;
- paper sleeves;
- fields that explain why all-market candidates beat current core competitors.

## Field-Building Standards

### New Alpha Should Become Fields First

Preferred sequence:

1. define the field;
2. log it in production;
3. verify PIT safety and replayability;
4. measure replacement value or allocation value;
5. promote only after multi-window or forward gate evidence.

### Preferred Field Shapes

Use compact and interpretable outputs:

- direction buckets such as `up/down/flat`;
- strength buckets such as `low/med/high`;
- provenance buckets such as `official/regulatory/secondary`;
- cohort flags such as `true/false`;
- one or two scalar diagnostics only when unavoidable.

Avoid:

- prompt prose as hidden logic;
- dense unlabeled float spam;
- fields that mix semantic judgment with hard risk decisions.

### Every LLM Field Needs Provenance

Minimum metadata:

- source document id;
- event id or accession id;
- system-known timestamp;
- evidence span or chunk reference;
- confidence or consistency tag;
- ontology version.

### Recommended Field Families

The current repo should preferentially build fields in these families:

- event identity:
  `event_family_v2`, `topic_path`, `ontology_version`,
  `emerging_topic_flag`;
- semantic surprise:
  `semantic_surprise_direction`, `semantic_surprise_strength`,
  `guidance_delta_direction`;
- call-quality structure:
  `topic_attention_divergence_bucket`, `manager_nonresponse_bucket`,
  `cross_channel_tone_gap_flag`, `tone_consistency_bucket`;
- credibility and commitment:
  `buyback_commitment_strength_bucket`,
  `buyback_remaining_capacity_signal`,
  `official_source_quality_bucket`;
- market-structure context:
  `options_activity_bucket`, `peer_event_relatedness_bucket`,
  `passive_flow_pressure_bucket`;
- firm-specific risk overlays:
  `firm_geopolitical_risk_bucket`,
  `geopolitical_exposure_change_flag`,
  `ai_disclosure_credibility_bucket`;
- KPI extraction:
  `kpi_delta_direction`, `kpi_surprise_vs_prior_bucket`,
  `kpi_evidence_span_count`, `kpi_extraction_coverage_flag`.

## Current High-Value Search Priorities

Priority order reflects expected value, replayability, implementation clarity,
and consistency with repo evidence.

### 1. State-Surface Maturation Through New Quality Fields

Why this stays first:

- the sleeve already has accepted paper evidence;
- forward promotion is now blocked by concentration, not by lack of edge;
- the next valid step is a new rank-quality, regime-quality, or crowding field.

Preferred directions:

- add fields that explain why top-ranked rotation names become too dominant;
- test those fields as paper ranking or paper notional inputs only;
- do not retune nearby queue-rank or regime-notional profiles on the same
  frozen sample.

### 2. Event Rotation Replacement-Value Maturation

Why it matters:

- this remains one of the strongest replay-only event signals;
- it preserves the core candidate set and uses a shared paper path;
- the main missing piece is forward replacement-value maturity.

Preferred work:

- mature closed forward paper outcomes;
- design trade-enabled adapters only after the forward gate clears;
- avoid nearby notional mining on the frozen windows.

### 3. Current Ticker Pool Governance

Why it matters:

- the accepted core stack is now dense enough that negative contribution and
  replacement value matter more;
- some cohorts likely belong in sleeves rather than in the same live budget.

Preferred work:

- contribution tables by ticker plus setup plus regime;
- no-trade avoided value;
- paper routing for suspect cohorts;
- separate live promotion or exclusion experiments only after paper evidence.

### 4. SEC / Earnings Semantic Expansion

Why it matters:

- it fits the doctrine of event-enhanced trend trading;
- it is still field-limited rather than alpha-empty;
- it can improve allocation and ranking without broadening discretion.

Preferred fields:

- `semantic_surprise_direction`
- `semantic_surprise_strength`
- `guidance_delta_direction`
- `topic_attention_divergence_bucket`
- `manager_nonresponse_bucket`
- `cross_channel_tone_gap_flag`

Recent repository evidence:

- `exp-20260518-009` supports a narrow SEC filing underreaction field:
  covered `neutral_or_mixed_language` financial-report candidates with
  `t1_excess_return_vs_spy <= 2%` improved all three fixed windows as a
  default-off paper-notional allocation. `exp-20260518-014` then improved the
  same branch by adding a SPY T+1 market-context field: accepted
  neutral-underreaction rows with `spy_t1_return >= -0.5%` receive extra
  default-off paper notional. Treat this as a forward-observation branch, not
  as proof that broad neutral tone or live SEC sizing is ready.

### 5. All-Market Candidate Discovery

Why it matters:

- upside is high;
- bias risk is also high;
- sleeves and replacement-value controls make it testable without contaminating
  core.

Preferred work:

- PIT universe construction;
- default-off broad-universe queue;
- feature attribution explaining why candidates beat current core competitors.

### 6. Buyback Credibility Sleeve v2

Default framing:

- this should resume only as a commitment-quality branch, not a keyword branch.

Preferred fields:

- `buyback_disclosure_type`
- `buyback_guidance_present`
- `buyback_commitment_strength_bucket`
- `buyback_remaining_capacity_signal`
- `repurchase_consistency_bucket`

### 7. High-Quality Insider Buying

Default framing:

- raw filing presence is not enough;
- Form 4 needs market-structure and credibility context.

Preferred fields:

- `options_activity_bucket`
- `cluster_buying_flag`
- `open_market_only_flag`
- `officer_seniority_bucket`
- `non_10b5_1_flag`
- `dollar_size_bucket`

### 8. Mechanical Index / Passive-Flow Event Sleeve

Why it matters:

- it is interpretable, deterministic, and less dependent on LLM ambiguity.

Preferred fields:

- `index_event_type`
- `effective_date`
- `pre_event_rank_distance`
- `rebalance_flow_window`
- `passive_flow_pressure_bucket`

### 9. Core-Misfit Paper Maturation

Default framing:

- this is a forward evidence program, not yet a live short or exclusion rule.

Preferred work:

- mature no-trade avoided value;
- mature inverse-paper value;
- cluster by ticker, setup family, and market state;
- prove any future exclusion is not one-window overfit.

### 10. Diagnostic Oracle Gap Analysis

Default framing:

- oracle work is a hypothesis generator, not acceptance evidence.

Preferred work:

- fixed-entry exit gap analysis;
- entry-oracle labels for selected, sliced, and rejected candidates;
- feature mining that converts observed gaps into one production-visible field.

## Research Refresh: External Themes Worth Converting Into Fields

This section is a research filter, not acceptance evidence. Reviewed on
2026-05-18.

### 1. Earnings spillovers should use explicit relatedness, not crude peer buckets

Repository implication:

- peer-event logic should use explicit relatedness features such as shared
  analyst coverage or other economic linkage;
- industry membership alone is too coarse.

Candidate fields:

- `peer_event_relatedness_bucket`
- `shared_analyst_coverage_flag`
- `peer_earnings_spillover_window`
- `peer_reaction_strength_bucket`

### 2. Earnings-call reaction bias is about information type, not raw tone

Repository implication:

- tangible operational facts and vague narrative should be separated;
- narrative-heavy positive or negative tone should not be treated as one scalar
  sentiment field.

Candidate fields:

- `operational_fact_density_bucket`
- `narrative_vagueness_bucket`
- `reaction_bias_flag`
- `analyst_tangible_vs_affective_gap`

### 3. Call-quality structure matters: divergence, non-response, and inconsistency

Repository implication:

- call quality should be decomposed rather than collapsed into one sentiment
  score;
- manager non-response, topic divergence, and cross-channel inconsistency are
  distinct states.

Candidate fields:

- `topic_attention_divergence_bucket`
- `manager_nonresponse_bucket`
- `manager_analyst_topic_gap_flag`
- `cross_channel_tone_gap_flag`
- `mixed_message_strength_bucket`

### 4. KPI extraction from earnings calls is now practical enough for field-first use

Repository implication:

- calls should be treated as a distinct extraction domain, not a weak copy of
  SEC-filings NLP;
- extraction QA and evidence-span logging are mandatory before alpha use.

Candidate fields:

- `kpi_delta_direction`
- `kpi_guidance_change_bucket`
- `kpi_surprise_vs_prior_bucket`
- `kpi_extraction_coverage_flag`
- `kpi_evidence_span_count`

### 5. Event-centric model design supports hierarchical schemas, not black-box trade authority

Repository implication:

- events should be primary decision units in research pipelines;
- reward trade-offs should be explicit in attribution;
- any learned event scorer belongs in paper/default-off paths first.

Candidate translations:

- hierarchical event labels instead of flat keyword bags;
- attribution by return, drawdown, hit rate, holding time, and replacement
  value;
- explicit paper gating for learned event scorers.

### 6. AI-themed disclosures need credibility fields, not keyword counts

Repository implication:

- AI mentions can be promotional or substantive;
- the useful signal is credibility, specificity, and analyst discrimination.

Candidate fields:

- `ai_disclosure_credibility_bucket`
- `ai_specificity_bucket`
- `ai_washing_flag`
- `ai_capex_or_product_evidence_flag`

### 7. Buyback and insider signals both need context, not presence flags

Repository implication:

- buyback alpha depends on commitment quality and remaining flexibility;
- insider-buying alpha depends on credibility and options-market competition.

Candidate fields:

- `buyback_commitment_strength_bucket`
- `buyback_remaining_capacity_signal`
- `options_competition_flag`
- `insider_purchase_context_quality`

### 8. Firm-level geopolitical exposure belongs at the issuer level

Repository implication:

- geopolitical risk should be represented as firm-level textual exposure, not
  only as a macro regime;
- this is especially relevant for semis, AI infra, defense, commodities, and
  supply-chain stories.

Candidate fields:

- `firm_geopolitical_risk_bucket`
- `geopolitical_topic_path`
- `geopolitical_exposure_change_flag`
- `call_level_geopolitical_intensity`

### 9. Volatility spillovers around earnings can become timing or crowding metadata

Repository implication:

- peer earnings do not only spill over in direction; they can also spill over
  in implied-volatility and timing pressure;
- useful as sleeve ranking context, not necessarily as a live core veto.

Candidate fields:

- `peer_iv_spillover_risk_bucket`
- `peer_reports_soon_flag`
- `announcement_cluster_density_bucket`
- `peer_event_crowding_flag`

### 10. Topic ontology management is itself an edge

Repository implication:

- topic systems must support emergence, hierarchy, and versioning;
- flat event tags will miss where new alpha first appears.

Candidate fields:

- `topic_path`
- `emerging_topic_flag`
- `topic_shift_vs_prior_call`
- `ontology_version`

## Anti-Repeat Rules

Do not retry the following without new evidence, a wider cohort, or a new
production-visible field:

- broad core filters and broad sector or strategy gates;
- broad slot, heat, or capacity sweeps;
- nearby scarce-slot or ample-slot scalar retries on the same accepted state;
- nearby state-surface queue-rank, floor, regime-notional, or
  candidate-breadth profile retunes on the frozen sample;
- nearby state-surface rank-1 ret20 dominance or score-gap notional profile
  retunes on the frozen sample;
- nearby state-surface rank-1 ret60 residual threshold/profile retunes on the
  frozen sample;
- nearby state-surface residual score-expansion threshold/profile retunes on
  the frozen sample;
- nearby state-surface residual rank-1 score-isolation threshold/profile
  retunes on the frozen sample;
- nearby state-surface rank-3 near-high support threshold/scalar retunes on
  the frozen sample;
- broad lifecycle target-width, runner, or trailing-stop retunes;
- nearby `RS20`, `RS60`, own-candle, `clean_spy`, `price_vs_200ma`, or
  green-deceleration scalar mining;
- nearby ticker-specific residual retunes after an exception is already
  accepted;
- broad Space pool expansion or thin Space interaction mining;
- SEC sleeve changes that add no new filing or call semantics;
- nearby SEC financial-report `negative_language` notional scalars on the
  frozen sample;
- buyback work that only adds keyword coverage;
- Form 4 work that ignores options-market context;
- LLM veto or ranking expansion without attribution fields;
- learned event scorers that bypass schema fields and sleeve gates.

## Update Discipline

Update this file only when one of these changes:

- a new result changes the mechanism-level prior;
- a family moves from promising to blocked, rejected, or accepted;
- a new anti-repeat rule becomes durable;
- a new research theme changes the field-building queue;
- a measurement blocker becomes the main constraint on a high-value alpha lane.

Write synthesis first. Keep experiment IDs sparse and use them only as anchors
for durable conclusions.
