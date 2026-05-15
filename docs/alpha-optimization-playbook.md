# Alpha Optimization Playbook

Last reviewed: 2026-05-15.

This file is Ginger's compressed alpha doctrine. It is not an experiment diary.
It should summarize:

- where the system has repeatedly made money;
- where repeated experiments failed for structural reasons;
- which missing fields are blocking valid next experiments;
- which recent research is worth translating into replayable fields.

Detailed runs belong in:

- `docs/experiment_log.jsonl`
- `docs/experiments/logs/*.json`
- `data/experiments/**`
- `docs/current_state.md`
- `docs/backtesting.md`

If this file conflicts with `AGENTS.md`, `AGENTS.md` wins. If this file
conflicts with `docs/backtesting.md` on windows or acceptance rules,
`docs/backtesting.md` wins.

## How To Use This Playbook

Before any new alpha search:

1. Choose one mechanism family from this file.
2. Confirm the proposal adds a new state variable, new cohort, or new field,
   not a nearby scalar retry.
3. Prefer allocation/routing experiments before entry/exit redesign.
4. Prefer production-visible fields over prompt-only heuristics.
5. If the branch is field-blocked, stop tuning thresholds and build the field.
6. Update this file only when a durable conclusion changed.

Good updates:

- "This family works only as allocation, not as entry."
- "This branch is blocked by missing PIT-safe fields."
- "A repeated failure now becomes an anti-repeat rule."
- "A new paper changes which field family should be built next."

Bad updates:

- appending every accepted scalar;
- copying full result tables already stored elsewhere;
- using the playbook as a date-by-date status log;
- writing narrative without a mechanism conclusion.

## System Doctrine

Ginger is an event-enhanced medium-horizon trend / breakout system. The core
engine is not trying to forecast everything. It is trying to:

1. identify already-good trend/breakout candidates;
2. allocate more capital to the best observable states inside that candidate
   set;
3. keep event ideas default-off until replacement value is proven;
4. use LLMs as structured semantic compilers, not portfolio managers.

The highest-confidence repo-wide lesson remains:

- broad filters usually destroy survival;
- broad capacity increases usually add noise;
- broad lifecycle retunes usually overfit;
- narrow state-conditioned allocation beats generic "safer" rules.

## Minimal Checkpoints

Keep only anchor states here. Full metrics live in `docs/backtesting.md` and
`docs/current_state.md`.

### Core

Current accepted core checkpoint is the 2026-05-15 stack ending at
`exp-20260515-018`.

Mechanism-level summary:

- alpha comes from shared sizing on already-qualified candidates;
- accepted positive states are mostly RS leadership, signal-day confirmation,
  sector-relative leadership, and narrow cap-room release on sleeves that were
  already winning;
- clean-SPY cap-only leaders are a real cap-bound sleeve, and the RS20-confirmed
  subset remained cap-bound after the broad 60% cap; `exp-20260515-013`
  promoted only that subset to a 70% cap;
- top-quartile price-vs-200MA extension is a small but robust allocation state
  on already-qualified stocks; `exp-20260515-018` promoted only the 1.025x
  top-up because nearby 1.05x+ values regressed `late_strong` or drawdown;
- the useful core edge is post-selection allocation, not broader filtering;
- small data/taxonomy fixes can matter when they change real routing.

Current practical interpretation:

- the candidate set is good enough that nearby cap/multiplier retunes are now
  a low-priority branch;
- 2026-05-15 nearby cap scouts on Healthcare clean-SPY leader and SLV
  trend-near-high did not create a new mechanism;
- after a sleeve-specific cap has already been accepted, the next valid step is
  a new production-visible discriminator or forward cap-room attribution, not
  another local cap sweep.
- do not retry nearby clean-SPY cap-only or clean-SPY cap-only RS20 cap values
  on the frozen windows without forward cap-room evidence or a different
  production-visible quality state.
- do not retry nearby price-vs-200MA extension scalars on the frozen windows
  without forward evidence or a materially different production-visible state.
- do not retry simple RS60 x price-vs-200MA overlap top-ups on the frozen
  windows; `exp-20260515-020` improved aggregate EV/PnL but every sweep
  regressed `late_strong`, so the overlap needs a new drawdown discriminator
  before it is worth revisiting.

### SEC Financial-Report Sleeve

Current checkpoint is the accepted default-off financial-report T+1 sleeve
ending at `exp-20260512-020`.

Mechanism-level summary:

- strong T+1 relative reaction matters more than raw filing presence;
- semantic notional sizing worked better than queue-order retuning;
- non-platform filtering improved observation quality;
- 10-Q / periodic-report distinctions are useful because they map to economic
  differences, not because they are more specific labels.

Current practical interpretation:

- the sleeve is useful as a replacement-value surface, not yet as promoted core
  alpha;
- the next valid branch is richer filing semantics;
- 2026-05-15 data audit evidence says fresh PIT directional filing-shock fields
  are still missing, so more queue-order or threshold retuning is invalid until
  those fields exist.

### Space Default-Off Sleeve

Current checkpoint is the accepted default-off Space stack through
`exp-20260514-053`.

Mechanism-level summary:

- repeated wins came from catalyst-quality allocation, not universe expansion;
- source quality, source diversity, peer-relative state, small-cap tape
  participation, and closed forward replacement strength all helped, but only
  as conservative incremental allocation inside a quarantined sleeve;
- forward outcome semantics were useful only after they touched a real runtime
  cohort.

Current practical interpretation:

- Space remains research infrastructure, not a live sleeve;
- nearby interaction retries are now sample-limited;
- 2026-05-15 confirmed that one mature forward row or one ticker-specific
  interaction is not enough to justify promotion;
- 2026-05-15 `exp-20260515-019` rejected promoting ARKX/UFO theme-beta
  benchmark ETFs into the Space trade candidate pool: all three standard
  windows lost EV and aggregate PnL fell by $180,752.89;
- the next valid Space step is either a broader mature cohort or a genuinely
  new production-visible catalyst-quality field.

## Durable Laws From Repository Evidence

### 1. Allocation Beats Filtering

This is the strongest repeated repo result.

What keeps working:

- modest post-sizing top-ups on already-qualified signals;
- narrow cap-room release on sleeves that already win;
- state-conditioned risk promotion;
- fixed candidate set plus better routing;
- default-off event sleeves with replacement-value accounting.

What keeps failing:

- broad "quality" filters;
- broad confidence/TQS overlays;
- generic slot or sector priority changes;
- capacity expansion for broad groups.

Default prior:

- if the idea says "trade fewer names" or "let more names in" across a broad
  class, it probably has low expected value in this system;
- if the idea says "on an already-good slice, allocate differently," it has a
  meaningfully better prior.

### 2. Candidate Quality Matters More Than Rule Cleverness

Trying to rescue a noisy candidate pool with extra logic usually failed.

Practical rule:

- keep the candidate set fixed when possible;
- add one ex-ante state variable before adding one more generic guardrail;
- if a proposal needs many caveats to work, it is usually already overfit.

### 3. Replacement Value Beats Narrative Quality

Event sleeves improved only when they improved replacement value versus the
next candidate or paper slot. Interesting stories alone did not help.

Practical rule:

- every event branch starts paper/default-off;
- every new field should answer "why this deserves capital instead of the next
  slot competitor";
- source quality, peer state, and post-event relative strength have been more
  useful than bare event labels.

### 4. Lifecycle Alpha Is Narrow

Broad exit redesigns have repeatedly failed.

Practical rule:

- do not widen targets because one winner felt early;
- do not assume a strong sizing state deserves a wider target;
- do not add runner logic without a new state variable and explicit lifecycle
  attribution.

Valid lifecycle work needs a new discriminator, not a nearby ATR retune.

### 5. Missing Fields Block More Alpha Than Bad Thresholds

Many stalled branches are not parameter problems. They are field problems.

Current blockers:

- PIT-safe SEC semantic surprise and guidance fields;
- richer same-accession filing-quality deltas;
- denser closed forward outcomes in Space and other event sleeves;
- better downstream attribution for LLM-produced semantics;
- richer insider / buyback / short-interest context before those sleeves can be
  taken seriously.

Practical rule:

- if the branch cannot yet be expressed as stable logged fields, it is not
  ready for promotion;
- when blocked by fields, stop sweeping scalars.

### 6. Production Visibility Is Part Of Alpha Quality

Backtester-only alpha does not count.

Practical rule:

- prefer shared features, shared sizing tags, and shared adapters;
- replay-only is acceptable only for unavoidable archive coverage gaps;
- default-off sleeves are valid only when they improve future decision quality
  without contaminating core metrics.

### 7. LLM Is A Semantic Compiler, Not A Risk Engine

The repo evidence and recent research agree on the boundary.

Use LLMs for:

- event classification;
- source-quality tagging;
- management-tone and semantic-change extraction;
- ontology growth;
- structured explanation fields for later replay.

Do not use LLMs for:

- hard sizing decisions;
- stop/target ownership;
- slot ownership;
- prompt-only numeric thresholds;
- opaque vetoes without structured attribution.

### 8. Mature-Cohort Coverage Is A Hard Gate

A theoretically good state is still invalid if it touches too few runtime rows.

Repeated pattern:

- nearby cap retries on already-accepted sleeves often touch one or two trades;
- mature forward Space interactions can look plausible but remain inert or
  fragile when only one ticker/cohort exists;
- positive intuition without runtime cohort breadth usually becomes null alpha.

Practical rule:

- do not promote a field or interaction that lacks nontrivial runtime-touch
  coverage;
- if a branch moves only one adjusted signal, demand forward evidence before
  spending more cycles on nearby scalars.

## Practical Technical Rules

These are implementation habits the system should keep.

### 1. New alpha ideas should first become fields

Preferred sequence:

1. define the field;
2. log it in production;
3. verify PIT safety and replayability;
4. measure replacement value or allocation value;
5. only then consider promotion.

### 2. Fields should be compact and interpretable

Preferred field shapes:

- direction: `up/down/neutral`;
- strength bucket: `low/med/high` or percentile;
- source bucket: `official/company/regulatory/secondary`;
- cohort flags: `true/false`;
- one or two scalar diagnostics only when unavoidable.

Avoid giant prompt prose or dozens of thin floats with no semantic meaning.

### 3. Every LLM field should carry evidence and provenance

Minimum desirable metadata:

- source document id;
- accession or event id;
- timestamp known to system;
- extracted span or chunk reference;
- confidence or consistency tag;
- ontology label version.

### 4. Closed-forward fields are useful only if they remain quarantined

Closed-forward outcome fields are valid for:

- default-off paper sleeves;
- replacement-value ranking;
- cohort research;
- future field selection.

They are not valid as hidden core lookahead features.

### 5. Research translation should end in one experimentable object

Every external paper should map to one of:

- a new field family;
- a new paper sleeve;
- a new allocation state on an existing sleeve;
- an anti-repeat rule that saves future time.

If a paper does not map cleanly to one of those, it is research noise for now.

## Anti-Repeat Rules

Do not retry the following without new evidence, a wider cohort, or a new
field:

- broad core filters and broad sector/strategy gates;
- global slot, heat, or capacity sweeps;
- broad lifecycle target-width, runner, or trailing-stop retunes;
- nearby RS20 / RS60 / own-candle / clean-SPY scalar tuning;
- nearby cap retries after a sleeve-specific cap has already been accepted,
  unless forward cap-room evidence exists;
- one-ticker cap scouts on already-accepted core sleeves;
- Space ticker-breadth expansion;
- Space theme-beta benchmark ETF admission as trade candidates, unless new
  evidence shows cross-window replacement value rather than benchmark utility;
- Space interaction retries supported by only one mature forward row or one
  ticker-level cohort;
- SEC sleeve retunes that do not add a new filing semantic field;
- public-archive buyback keyword ladders that do not add credibility,
  completion, or cash-support fields;
- LLM veto or ranking expansion without structured downstream attribution.

## What Recent Logs Mean At A Higher Level

Compressing recent daily experiments:

- accepted core changes kept adding small, production-visible allocation states
  on a fixed candidate set;
- accepted sleeve changes mostly came from catalyst-quality, source-quality,
  peer-relative, or closed-forward replacement states;
- rejected changes were usually broad overlays, nearby retunes, or sample-thin
  interactions;
- core cap-based alpha is still real, but the easy cap-room wins are getting
  exhausted;
- the next wave of alpha is more likely to come from better fields than from
  more scalar tuning.

Default search style should therefore be:

1. add one replayable state variable;
2. keep the candidate set fixed;
3. test allocation before entry/exit redesign;
4. keep event ideas default-off until replacement value closes;
5. convert repeated wins into shared fields, not more prompt prose.

## Research Refresh: 2024-2025 Ideas Worth Translating

This section is not acceptance evidence. It is a research filter. Each item
must translate into fields, sleeves, or attribution.

### 1. PEAD Is Stronger When Surprise Conflicts With Prior Belief

Research signal:

- McCarthy (2025) argues post-earnings drift is much stronger when the surprise
  conflicts with prior recommendation-implied belief.

Translation for Ginger:

- add `belief_conflict_flag`, `belief_prior_bucket`,
  `semantic_surprise_direction`, and `semantic_surprise_strength`;
- treat these as sleeve qualifiers or notional scalers inside SEC /
  earnings-related branches;
- do not turn them into a generic core filter.

### 2. Earnings-Call Information Quality Depends On Topic Misalignment

Research signal:

- Xiao (2025) shows topic attention divergence between management remarks and
  analyst questions is informative about information quality.
- Tabatabaei (2025) suggests tonal inconsistency can recover drift where
  communication is strategically mixed.

Translation for Ginger:

- add `topic_attention_divergence_bucket`,
  `manager_analyst_topic_gap_flag`, and `tone_consistency_bucket`;
- use them as paper-sleeve quality fields or allocation state, not as broad
  vetoes.

### 3. Forecast Completeness Matters More Than Revision Magnitude Alone

Research signal:

- Perotti and Windisch (2025) show underreaction to earnings forecast revisions
  is smaller when cash-flow forecasts accompany the revision.

Translation for Ginger:

- add `cash_flow_forecast_present`,
  `revision_completeness_bucket`, and `forecast_bundle_consistency`;
- use these only when the data source is PIT-safe;
- default use case is follow-through expectation, not a new standalone sleeve.

### 4. Buyback Alpha Is About Credibility And Commitment

Research signal:

- Bargeron et al. show repurchase status updates such as suspension, resumption,
  and completion are common and value-relevant.
- Kaplan et al. (2025) show buyback guidance is a commitment signal, not just a
  generic payout announcement.

Translation for Ginger:

- add `buyback_disclosure_type`, `buyback_status_update_type`,
  `buyback_guidance_present`, `buyback_completion_signal`,
  `buyback_remaining_capacity_signal`, and `cash_support_bucket`;
- keep this default-off first;
- combine credibility fields with post-event relative strength or replacement
  value before any promotion.

Repository interaction:

- the first public-archive buyback credibility ladder already failed;
- the next valid buyback branch requires richer fields, not a better keyword
  list.

### 5. Insider Buying Needs Options-Market And Trade-Quality Context

Research signal:

- Jeon and Sulaeman (2024) show insider purchase informativeness weakens in
  names with more active options trading.
- newer insider work still points to trade quality, trader identity, and market
  structure as the real edge rather than the raw filing itself.

Translation for Ginger:

- add `options_activity_bucket`, `cluster_buying_flag`,
  `open_market_only_flag`, `officer_seniority_bucket`,
  `non_10b5_1_flag`, and `dollar_size_bucket`;
- keep Form 4 branches as paper / replacement-value queues first.

### 6. Short-Squeeze Alpha Must Be Narrow And Catalyst-Conditioned

Research signal:

- Svoboda, Kapounek, and Albrecht (2025) show squeeze likelihood rises with
  elevated short interest and attention spikes, while institutional ownership
  stabilizes outcomes.

Translation for Ginger:

- add `short_interest_bucket`, `attention_spike_bucket`,
  `institutional_ownership_brake`, and `catalyst_officiality_bucket`;
- only test this as a narrow default-off sleeve when an official positive
  catalyst is already present;
- do not build a broad meme-stock branch.

### 7. Mechanical Index Events Are Attractive Because They Are Less Narrative

Research signal:

- index inclusion / assignment work continues to support mechanical event flow
  edges near index cutoffs.

Translation for Ginger:

- add `index_event_type`, `effective_date`, `pre_event_rank_distance`, and
  `rebalance_flow_window`;
- this belongs in a paper sleeve first because it is mechanically interpretable
  and easy to audit.

### 8. Accounting Quality Should Be Selective, Not A Global Factor

Research signal:

- recent accrual / information-quality work still supports conditional use in
  lower-attention or lower-quality settings rather than as a broad factor.

Translation for Ginger:

- treat accounting-quality or accrual quality as a targeted haircut / veto in
  weaker-information cohorts;
- do not add a broad accrual factor to the core.

### 9. Financial LLM Research Supports Schema-First Extraction

Research signal:

- `FinTagging` (2025) shows financial extraction should be evaluated as
  structured fact extraction plus taxonomy alignment across text and tables.
- `Agentic Retrieval of Topics and Insights from Earnings Calls` (2025) supports
  hierarchical topic ontology construction instead of flat keyword buckets.
- `QuantMind` (2025) emphasizes point-in-time correctness and evidence
  attribution for financial knowledge systems.

Translation for Ginger:

- every new LLM workflow should emit schema-bound JSON fields first;
- ontology growth should be versioned and replayable;
- text and table extraction should be treated as separate failure modes;
- evidence spans and source ids should be logged with the field, not added
  later by hand.

## Field-Building Roadmap

When new research becomes actionable, the first deliverable should be a field,
not a live rule.

Highest-priority field families:

1. SEC / earnings semantics:
   `semantic_surprise_direction`, `semantic_surprise_strength`,
   `belief_conflict_flag`, `guidance_delta_direction`,
   `topic_attention_divergence_bucket`, `tone_consistency_bucket`.
2. Filing completeness and quality:
   `cash_flow_forecast_present`, `revision_completeness_bucket`,
   `forecast_bundle_consistency`, `same_accession_financial_quality_delta`.
3. Buyback credibility:
   `buyback_status_update_type`, `buyback_guidance_present`,
   `buyback_completion_signal`, `buyback_remaining_capacity_signal`,
   `cash_support_bucket`.
4. Insider quality:
   `options_activity_bucket`, `cluster_buying_flag`,
   `officer_seniority_bucket`, `non_10b5_1_flag`, `dollar_size_bucket`.
5. Short-squeeze context:
   `short_interest_bucket`, `attention_spike_bucket`,
   `institutional_ownership_brake`, `catalyst_officiality_bucket`.
6. Event ontology:
   `event_family_v2`, `event_source_quality`, `event_novelty_bucket`,
   `topic_path`, `topic_conflict_flag`.

Field-building rule:

- if a new idea cannot yet be turned into stable, logged, PIT-safe fields, it
  is probably not ready for alpha work.

## Current Research Queue

Priority is ordered by expected value, replayability, and implementation
clarity.

1. SEC earnings semantic expansion.
   Build belief-conflict, guidance, topic-divergence, and same-accession
   quality fields before any more financial-report sleeve threshold work.
2. Buyback credibility sleeve v2.
   Resume only with status-update, guidance, completion, and cash-support
   fields.
3. Space mature-cohort expansion.
   Continue only when closed outcomes create broader catalyst/source/peer
   cohorts or a new production-visible catalyst-quality field.
4. High-quality insider buying.
   Resume only with options-activity and purchase-quality context.
5. Short-interest plus official catalyst sleeve.
   Build as a narrow default-off overlay with ownership braking.
6. Index inclusion / rebalance sleeve.
   Paper-only until replacement value closes.
7. LLM ontology and field quality.
   Improve extraction, provenance, and attribution before expanding LLM
   authority.

## Exploratory Backlog

Valid but lower-priority ideas:

- analyst revision momentum beyond earnings / SEC sleeves;
- spin-offs, asset sales, and capital-structure events;
- fundamental inflection surfaces;
- thematic second-order supply chains;
- volatility-state lifecycle allocation;
- market-breadth deployment state;
- accounting-quality downside filters;
- slow-moving profitability overlays;
- defensive / low-beta deployment overlays.

Backlog rule:

- prefer one new replayable field over one more retune of an already-accepted
  scalar.

## Measurement And Parity Reminders

Measurement work should outrank alpha search only when it unblocks a stronger
experiment. Valid blockers include:

- missing runtime fields;
- missing PIT-safe semantic features;
- production/backtest divergence;
- missing mature forward outcomes;
- missing prompt/log/replay fields for LLM-derived semantics.

If a branch is blocked by fields, say so explicitly and move to the next valid
family rather than sweeping nearby thresholds.

## Update Discipline

This file should remain much shorter than the experiment log. Update it only
when one of these changes:

- a new checkpoint changes the canonical stack at the mechanism level;
- a family changes from promising to blocked, rejected, or accepted;
- a new anti-repeat rule becomes durable;
- new research changes the field-building queue;
- a measurement blocker becomes the main constraint on a high-value idea.

Write synthesis first. Cite only the minimum experiment IDs needed to anchor a
durable conclusion.
