# Alpha Optimization Playbook

Last reviewed: 2026-05-14.

This file is the durable alpha synthesis for Ginger. It is not an experiment
diary. It should compress many runs into a smaller set of mechanism rules:

- where alpha currently comes from;
- which idea families deserve more cycles;
- which families are structurally weak on this system;
- which fields are missing and therefore block valid experiments;
- which external research is worth translating into replayable fields.

Detailed sweeps, per-window artifacts, and date-by-date records belong in:

- `docs/experiment_log.jsonl`
- `docs/experiments/logs/*.json`
- `data/experiments/**`
- `docs/current_state.md`

Use `docs/backtesting.md` as the source of truth for windows, commands, and
acceptance protocol. If this file conflicts with `AGENTS.md`, `AGENTS.md`
wins.

## How To Use This Playbook

Before starting a new alpha search:

1. Pick one mechanism family below.
2. Check whether the proposed change adds a genuinely new state variable, not a
   nearby retry.
3. Prefer allocation/routing tests before entry/exit redesign.
4. Prefer production-visible fields over prompt-only heuristics.
5. Update this file only if the result changes a durable conclusion.

Good updates:

- "This branch is blocked by missing PIT-safe fields."
- "This family works only as allocation, not as entry."
- "This research direction moved into the top queue."
- "This repeated failure now becomes an anti-repeat rule."

Bad updates:

- appending every accepted scalar;
- pasting full before/after tables already logged elsewhere;
- turning this file into a dated status log;
- restating single-run details without a mechanism-level conclusion.

## Current Doctrine

Ginger remains an event-enhanced intermediate-term trend / breakout system.
Current alpha is not broad stock picking. It is mostly:

1. Better sizing on already-qualified trend/breakout candidates.
2. Better slot/risk routing on scarce capital.
3. Default-off event sleeves that first prove replacement value.
4. Semantic allocation inside narrow sleeves using production-visible fields.
5. Measurement repairs that unlock trustworthy future alpha tests.

The most stable repo-wide lesson is unchanged:

- broad filters usually destroy survival;
- broad capacity increases usually add noise, not alpha;
- broad lifecycle retunes usually fail to generalize;
- narrow state-conditioned allocation beats intuitive but generic "safer"
  rules.

## Canonical Checkpoints

Keep only the minimal anchor points here. Full metrics stay in
`docs/backtesting.md` and the experiment log.

### Core Stack

Current core checkpoint is the 2026-05-14 accepted stack ending at core
`exp-20260514-030` (`financials_mid_dispersion_leader_cap`).

Mechanism summary:

- RS20 leader state helps as a modest sizing top-up.
- Signal-day own-green state helps as a modest sizing top-up.
- RS60 top-quintile stock state helps as a modest sizing top-up.
- Clean SPY-relative signal-day confirmation helps as a final top-up.
- The same clean SPY-relative signal-day sleeve is modestly cap-bound; a
  sleeve-specific 52.5% position cap worked, while nearby 55%+ caps regressed
  the old window.
- The accepted commodity near-high trend sleeve is cap-bound alpha; a
  sleeve-specific 50% position cap worked better than more raw commodity
  multiplier tuning.
- The accepted Financials sector-leader trend sleeve is also cap-bound alpha;
  a sleeve-specific 50% position cap improved weak and old windows without
  changing the raw Financials multipliers.
- The narrower Financials sector-leader plus mid-sector-dispersion
  intersection is modestly cap-bound; a 55% cap improved weak and old windows
  without changing entries, ranking, or raw Financials multipliers, but only 3
  signals adjusted.
- Small taxonomy/data repairs can matter when they change real routing.

Core interpretation:

- the edge lives in shared allocation on already-qualified signals;
- the edge does not justify new broad entry filters;
- the edge does not justify broad slot expansion;
- commodity, Financials, or clean-SPY signal-day cap follow-up should require
  a new production-visible state and forward cap-room attribution, not another
  raw multiplier/cap retry after the accepted sleeve caps;
- the edge does not justify broad lifecycle redesign.

### SEC Financial-Report Default-Off Sleeve

Current checkpoint is the accepted financial-report T+1 paper sleeve ending at
`exp-20260512-020`.

Mechanism summary:

- useful edge appears after strong T+1 relative reaction;
- semantic notional sizing is better than queue-order retuning;
- non-platform filtering improved observation quality;
- 10-Q / periodic-report distinctions can matter when they map to a cleaner
  economic interpretation.

SEC interpretation:

- the sleeve is useful as a paper replacement-value surface;
- further progress needs richer semantic fields, not nearby threshold sweeps;
- filing-shock alpha remains blocked by missing PIT-safe same-accession
  surprise/guidance fields.

### Space Default-Off Sleeve

Current checkpoint is the accepted official-catalyst Space stack through
`exp-20260514-041`.

Mechanism summary:

- catalyst-quality fields matter;
- peer-relative strength matters;
- small-cap tape participation matters;
- source diversity and forward replacement-strength matter;
- the latest accepted forward-strength interactions are `trend_long` plus
  IWM-leader tape at a conservative `1.025x`, then `trend_long` plus
  company-release customer-win confirmation at a conservative `1.025x`;
- source-diverse official Space catalysts also work best when the executed
  setup is `trend_long`, but only at a conservative `1.025x`;
  stronger nearby or ticker-only retries require new closed forward evidence;
- closed forward-outcome timing matters: the first useful new state after
  source diversity was delayed absorption, defined as weak average 5d cash
  reaction but strong 10d same-theme replacement value, again only as a
  conservative `trend_long` allocation helper;
- broad closed-forward benchmark confirmation now matters too: `exp-20260514-041`
  accepted a conservative `1.025x` `trend_long` helper when 10d event-state
  profiles are positive versus cash, SPY, QQQ, UFO, and ARKX;
- the best use is semantic risk allocation inside a quarantined sleeve.

Space interpretation:

- this is a research/default-off sleeve, not a live universe expansion;
- repeated wins came from stacking production-visible quality states, not from
  adding more tickers;
- future progress should come from closed forward outcomes and better catalyst
  semantics, not from nearby scalar retunes on the frozen snapshots.
- do not retry nearby source-diversity, company-source, delayed-absorption, or
  broad benchmark-breadth scalars without new closed forward rows or a new
  production-visible catalyst-quality field.

## Durable Laws From Repository Evidence

### 1. Allocation Beats Filtering

This is the strongest repeated result in the repository.

What keeps working:

- modest post-sizing top-ups on already-qualified signals;
- narrow state-conditioned risk promotion;
- scarce-slot routing on a fixed candidate set;
- default-off sleeves that do not contaminate core slots.

What keeps failing:

- broad "quality" filters;
- broad confidence/TQS/ranking overlays;
- broad capacity/heat increases;
- broad sector or strategy priority rules.

Operational rule: if the idea can be phrased as "trade fewer things" or
"expand capacity for a broad group," assume low prior unless the new rule is
backed by a production-visible field and multi-window evidence.

### 2. Candidate Set Quality Matters More Than Rule Cleverness

Many failed experiments were trying to rescue a noisy candidate pool with more
logic. That is usually the wrong direction.

Implications:

- keep the candidate set fixed when possible;
- add one ex-ante state variable instead of one more generic filter;
- prefer better ranking/allocation on proven candidates over new low-quality
  entries.

### 3. Replacement Value Matters More Than Narrative Quality

Event sleeves improved only when the event changed replacement value versus the
next best candidate or paper slot. "Interesting story" alone was not enough.

Implications:

- every event branch should begin as paper/default-off;
- event fields should explain why this candidate deserves capital over the next
  alternative;
- source quality, peer state, and post-event relative strength are usually more
  useful than a bare event label.

### 4. Lifecycle Alpha Is Narrow And Fragile

Broad exit retunes repeatedly failed in core and sleeve experiments.

Implications:

- do not widen targets broadly because one trade felt early;
- do not treat stronger sizing states as automatic wider-target states;
- do not add runner logic without a new state variable and lifecycle
  attribution.

Valid lifecycle work needs a new discriminator, not a nearby ATR retune.

### 5. Semantic Fields Block More Alpha Than Threshold Choice

Several branches are not parameter problems. They are missing-field problems.

Current blockers:

- SEC filing shock lacks PIT-safe same-accession surprise and guidance fields;
- earnings/call branches still lack richer structured text fields;
- some event sleeves lack enough closed forward outcomes for promotion;
- LLM branches still need denser downstream attribution on produced fields.

Operational rule: when a branch is field-blocked, stop sweeping nearby
parameters and go build the missing field.

### 6. Production Visibility Is Part Of Alpha Quality

Backtester-only alpha does not count.

Implications:

- prefer shared features and shared sizing markers;
- use replay-only logic only for unavoidable archive gaps;
- default-off sleeves are valid only when they improve future decision quality
  without distorting core metrics.

### 7. LLM Is A Semantic Compiler, Not A Portfolio Manager

The repo evidence and current research point to the same boundary.

LLM is well-suited for:

- event classification;
- source-quality tagging;
- management-tone and narrative-change extraction;
- ontology growth;
- structured reason fields for later replay.

LLM is not suited for:

- hard sizing decisions;
- stop/target ownership;
- slot ownership;
- prompt-only numeric rules;
- opaque vetoes without attribution.

## Anti-Repeat Rules

Do not retry these without new evidence or a genuinely new field:

- broad core filters and broad sector/strategy gates;
- global slot/heat/capacity sweeps;
- broad lifecycle target-width, runner, or trailing-stop retunes;
- nearby RS20 / RS60 / own-candle / clean-SPY-leader scalar tuning;
- generic event-source pruning;
- Space ticker-breadth expansion;
- SEC sleeve retunes that do not add a new semantic field;
- public-archive buyback keyword ladders that do not add credibility/completion
  fields;
- LLM ranking or veto expansion without structured attribution.

## What Recent Logs Say At A Higher Level

Compressing the recent high-frequency experiment set:

- accepted core changes were mostly modest, production-visible allocation
  states layered on a fixed candidate set;
- accepted sleeve changes were mostly catalyst-quality, source-quality,
  peer-relative, or forward-replacement allocation states;
- rejected changes were usually broad entry/exit changes, broad quality
  overlays, or retries of a nearby accepted scalar;
- once a family starts requiring multiple interacting caveats to work, it is
  usually already overfit.

Default search style should therefore be:

1. add one replayable state variable;
2. keep the candidate set fixed;
3. test allocation before entry/exit redesign;
4. keep event ideas default-off until replacement value closes;
5. convert repeated wins into shared fields, not prompt prose.

## Research Refresh: 2024-2025 Ideas Worth Translating

This section is not acceptance evidence. It is a filter for implementation
effort. Each idea should map to fields, sleeves, and attribution.

### 1. Earnings Drift Needs Semantic Surprise, Not Another Numeric Threshold

Recent work suggests the drift edge is stronger when the system captures the
meaning of the announcement, not just the raw number.

Research signal:

- `PEAD.txt` shows transcript-derived surprise can produce stronger drift than
  classic numeric surprise, including in more recent periods.
- McCarthy (2025) shows drift is much stronger when the surprise conflicts with
  prior market belief.
- Xiao (2024) shows topic-attention divergence in earnings calls predicts worse
  information quality and higher future friction.

Translation for Ginger:

- add `semantic_surprise_direction`, `semantic_surprise_strength`,
  `belief_conflict_flag`, and `topic_attention_divergence_bucket`;
- treat these as sleeve qualifiers or notional scalers, not as standalone core
  entry signals;
- prefer a small set of interpretable text fields over a giant feature zoo.

### 2. Forecast Completeness Is A Field, Not A Narrative Detail

Research signal:

- Perotti and Windisch (2025) show the drift after forecast revisions is
  smaller when cash-flow forecasts accompany earnings forecast revisions.

Translation for Ginger:

- if revision data becomes available, add fields such as
  `cash_flow_forecast_present`, `revision_completeness_bucket`, and
  `forecast_bundle_consistency`;
- use them to scale follow-through expectations, not to create a raw analyst
  sleeve immediately.

### 3. Buyback Alpha Is About Credibility Ladders

Research signal:

- Bargeron et al. (2024) show voluntary repurchase status updates are common
  and value-relevant, and relate to later completion behavior.
- recent buyback work points toward credibility, completion, and disclosure
  quality, not generic authorization announcements.

Translation for Ginger:

- build fields such as `buyback_disclosure_type`,
  `buyback_completion_signal`, `buyback_remaining_capacity_signal`,
  `cash_support_bucket`, and `buyback_history_credibility`;
- use a default-off sleeve first;
- combine buyback credibility with post-event relative strength rather than
  treating every authorization as drift-positive.

Repository interaction:

- the 2026-05-14 buyback credibility replay rejected the first keyword ladder;
- do not retry that public-archive ladder without richer credibility fields or
  forward closed evidence.

### 4. Insider Buying Needs Market-Structure Context

Research signal:

- Jeon and Sulaeman (2024) show insider purchase informativeness is much weaker
  in names with more active options trading.

Translation for Ginger:

- if Form 4 resumes, add `options_activity_bucket`,
  `cluster_buying_flag`, `open_market_only_flag`,
  `officer_seniority_bucket`, `non_10b5_1_flag`, and
  `dollar_size_bucket`;
- default experiment should be a paper queue plus replacement-value tracking,
  not direct promotion.

### 5. Short Squeeze Alpha Should Be Narrow And Catalyst-Conditioned

Research signal:

- Svoboda, Kapounek, and Albrecht (2025) show squeeze likelihood rises with
  high short interest and attention spikes, while institutional ownership
  stabilizes outcomes.

Translation for Ginger:

- build a default-off sleeve only when there is an official positive catalyst,
  crowded shorting, and attention acceleration;
- add `short_interest_bucket`, `attention_spike_bucket`, and
  `institutional_ownership_brake`;
- treat it as a conservative overlay, not a meme-stock sleeve.

### 6. Index Inclusion / Rebalance Is Attractive Because It Is Mechanical

Research signal:

- Limburg (2024) finds Russell 1000/2000 assignment is effectively random near
  the cutoff.

Translation for Ginger:

- this supports a paper sleeve around official announce-to-effective index
  flows;
- required fields are `index_event_type`, `effective_date`,
  `pre_event_rank_distance`, and `rebalance_flow_window`;
- this should remain event-mechanical, not story-driven.

### 7. Accounting/Accrual Signals Should Be Used Selectively

Research signal:

- Oler, Coyne, and Talakai (2024) show the accrual anomaly survives more in
  neglected, lower-attention settings.

Translation for Ginger:

- do not add a broad accrual factor to the core;
- treat accounting-quality as a targeted risk haircut or paper-only veto in
  lower-attention names;
- this fits Ginger's targeted allocation style better than a standalone factor
  sleeve.

### 8. LLM Research Supports Structured Extraction And Ontology Growth

Research signal:

- recent extraction work shows generative LLMs are useful when forced into
  schema-like structured output;
- recent earnings-call topic work shows LLM agents can maintain a hierarchical
  ontology of emerging topics.

Translation for Ginger:

- every new LLM workflow should emit JSON fields first;
- store topic/entity outputs as replayable artifacts;
- grow a stable event/topic ontology rather than repeatedly changing prompt
  prose;
- evaluate each field on downstream replacement value, routing value, or drift
  attribution.

## Field-Building Roadmap

When new research becomes actionable, the first deliverable should be a field,
not a live rule.

Highest-priority field families:

1. Earnings semantics:
   `semantic_surprise_direction`, `semantic_surprise_strength`,
   `belief_conflict_flag`, `topic_attention_divergence_bucket`,
   `guidance_delta_direction`.
2. Buyback credibility:
   `buyback_disclosure_type`, `buyback_completion_signal`,
   `buyback_remaining_capacity_signal`, `cash_support_bucket`,
   `buyback_history_credibility`.
3. Insider quality:
   `options_activity_bucket`, `cluster_buying_flag`,
   `officer_seniority_bucket`, `non_10b5_1_flag`, `dollar_size_bucket`.
4. Short-squeeze context:
   `short_interest_bucket`, `attention_spike_bucket`,
   `institutional_ownership_brake`, `catalyst_officiality_bucket`.
5. Event ontology:
   `event_family_v2`, `event_source_quality`, `event_novelty_bucket`,
   `topic_path`, `topic_conflict_flag`.

Field-building rule:

- if a new idea cannot yet be expressed as a stable, logged, replayable field,
  it is probably not ready for alpha promotion.

## Current Research Queue

Priority is ordered by expected value, replayability, and implementation
clarity.

1. SEC earnings semantic expansion.
   Build transcript/guidance/belief-conflict fields before any more
   financial-report sleeve threshold tuning.
2. Buyback credibility sleeve v2.
   Resume only with completion/status/cash-support fields, not another keyword
   ladder.
3. Space forward replacement cohorts.
   Continue only when new closed outcomes add evidence on catalyst/source/peer
   interactions.
4. High-quality insider buying.
   Resume only with options-activity and purchase-quality context fields.
5. Short-interest plus official catalyst sleeve.
   Build as a narrow default-off event overlay with ownership braking.
6. Index inclusion / rebalance flow sleeve.
   Paper-only until replacement value closes.
7. LLM ontology and event extraction.
   Improve field quality first; do not expand LLM authority first.

## Exploratory Backlog

These remain valid ideas, but not the top queue:

- analyst estimate revision momentum;
- fundamental inflection surfaces;
- spin-offs, asset sales, and capital-structure events;
- second-order thematic supply chains;
- volatility-state lifecycle allocation;
- market-breadth deployment state;
- accounting-quality downside filters;
- slow-moving profitability overlays;
- defensive/low-beta portfolio state.

Backlog rule: prefer a new replayable behavioral field over a nearby retune of
an already-accepted scalar.

## Measurement And Parity Reminders

Measurement work should outrank alpha search only when it unblocks a better
experiment. Valid blockers include:

- missing runtime fields;
- missing PIT-safe semantic features;
- production/backtest divergence;
- missing forward closed outcomes;
- missing prompt/log/replay fields for LLM-derived semantics.

If a branch is blocked by fields, say so explicitly and move to the next valid
alpha family rather than sweeping nearby thresholds.

## Update Discipline

This file should stay much shorter than the experiment log. Update it only when
one of these changes:

- a new checkpoint changes the canonical stack at the mechanism level;
- a family changes from promising to blocked/rejected/accepted;
- a new anti-repeat rule becomes durable;
- new research changes the field-building queue;
- a measurement blocker becomes the main constraint on a high-value alpha idea.

Write synthesis first. Cite only the minimum experiment IDs needed to anchor
the conclusion.
