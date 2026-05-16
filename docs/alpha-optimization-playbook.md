# Alpha Optimization Playbook

This file is not an experiment log. It is the durable synthesis layer that sits
between `AGENTS.md` and `docs/experiment_log.jsonl`.

Use it to decide what kinds of ideas deserve the next experiment, what kinds of
ideas have repeatedly failed, and which external research themes are worth
translating into replayable fields.

Last refreshed: 2026-05-16.

## How To Use This Playbook

Before changing strategy logic, answer:

1. What is the highest-EV hypothesis available right now?
2. Is it a field problem, an allocation problem, an entry problem, an exit
   problem, or a candidate-pool problem?
3. Has a nearby version already failed on the canonical windows?
4. Can the idea be expressed as one production-visible, replayable variable?
5. If not, what data/logging gap blocks it?

Default workflow:

1. Prefer `alpha_search` over `measurement_repair` unless measurement is the
   direct blocker.
2. Prefer fixed candidate set + better allocation over broad candidate-pool or
   filter changes.
3. Prefer one new field over one more scalar retune.
4. Prefer shared production-visible policy over backtest-only logic.
5. Prefer paper/default-off event sleeves before live promotion.

## System Doctrine

Ginger is an event-enhanced medium-term trend / breakout system.

The practical alpha stack is:

1. Core trend and breakout continuation.
2. State-conditioned capital allocation on already-qualified signals.
3. Event sleeves that earn capital only when they beat replacement value.
4. LLM-generated semantics only when they become structured, PIT-safe, logged,
   replayable fields.

The system's repeated mistake has not been "too little complexity." It has been
"complexity attached to weak candidate pools or thin cohorts."

## Mechanism Checkpoints

These checkpoints anchor the current playbook. They are not daily notes.

### Core

- The accepted core stack through `exp-20260516-009` still says the same thing:
  modest, cap-aware, state-conditioned top-ups on an already-good candidate set
  have a much better prior than new broad filters or broad routing changes.
- Recent accepted states were all small allocation refinements on production-
  visible fields already present on qualified signals:
  `clean_spy` leadership, `rs20` leadership, `rs60` strength,
  `price_vs_200ma` extension, confirmed-quality state, and restricted
  green-momentum deceleration.
- Recent rejected core ideas were mostly broad or sample-fragile:
  sector-thrust overlays, close-location / gap-absorption overlays,
  slot-priority reroutes, nearby `exec_lag_adj_net_rr` scalars, and pullback
  re-entry designs.
- The current `trend_long` / Industrials zero-risk rule is not an obvious
  overkill after `exp-20260516-011`: restoring even `0.10x` risk improved only
  `late_strong`, regressed both weaker validation windows, cut aggregate EV by
  `0.8913`, and worsened the drawdown ceiling by `1.84 pp`.
- Semiconductor false-trend work has a small positive clue but not a tradable
  rule after `exp-20260516-012`: zeroing non-green `trend_long` semiconductor
  signals improved EV by `0.0044` with no regressed window, but it touched only
  two `TSM` signals. Treat this as forward attribution, not a promoted alpha.

Current interpretation:

- Core alpha is still in allocation, not in new broad filtering.
- The fixed candidate set is mostly good enough; the remaining easy wins are
  smaller and more conditional.
- Nearby scalar tuning is becoming exhausted. New core alpha likely needs a new
  production-visible discriminator, not another `+/- 0.025x` sweep.

### Event / Sleeve Work

- Default-off sleeves remain valid only when they improve replacement value
  relative to the next core slot.
- Space experiments confirmed a narrow rule:
  source quality, peer-relative state, and mature forward replacement evidence
  can help as quarantined allocation states, but broad ticker admission and
  sample-thin interaction retries usually fail.
- `exp-20260516-014` adds one accepted Space exception to the "sample-thin
  interactions usually fail" rule: source-diverse `trend_long` profiles with
  both `customer_win` and `government_space_contract` improved two windows,
  left `old_thin` unchanged, and stayed inside drawdown with only a `1.025x`
  default-off scalar. Treat this as a catalyst-quality field, not permission to
  broaden the Space pool.
- The default-off event bundle remains the strongest non-core replay family
  after `exp-20260516-013`: `rotation_breakout_leadership` at a bounded `3.0x`
  paper notional improved all three current-stack windows versus the `2.0x`
  non-generic positive event-surface lead, with 7 rotation-surface trades and a
  passing sample-concentration guard. This is still paper-only until a shared
  trade-enabled adapter and forward replacement-value evidence exist.
- Recent Space accepts were still allocation-only. Recent Space rejects were
  mostly pool-expansion, ticker-expansion, slot-compression, or one-ticker
  interaction stories.
- SEC / filing ideas remain high potential but still field-blocked. The
  highest-value next step is richer PIT-safe semantic and completeness fields,
  not another threshold retune on the current sparse filing features.

Current interpretation:

- Event sleeves should stay paper/default-off until they prove replacement
  value.
- Event alpha improves when the field explains "why this deserves capital over
  the next slot competitor," not when it merely describes a story better.

## Durable Laws From Repository Evidence

### 1. Allocation Beats Filtering

This is still the strongest repeated result.

What keeps working:

- small post-sizing top-ups on already-qualified signals;
- narrow cap release on sleeves that already win;
- state-conditioned risk promotion with unchanged candidate set;
- fixed candidate set plus better replacement routing in paper sleeves.

What keeps failing:

- broad quality filters;
- broad confidence / TQS overlays;
- generic sector or slot routing changes;
- broad universe or capacity expansion.

Default prior:

- if the idea changes who is allowed to trade across a broad class, it starts
  with a weak prior;
- if the idea changes how already-good signals are sized, it starts with a much
  better prior.

### 2. Candidate Quality Matters More Than Rule Cleverness

Trying to rescue a noisy pool with extra logic usually failed.

Practical rule:

- hold the candidate set fixed when possible;
- add one ex-ante state variable before adding one more generic guardrail;
- if the proposal needs many caveats, it is probably overfit already.

### 3. Replacement Value Beats Narrative Quality

Interesting stories do not earn capital by themselves. Event sleeves improved
only when they improved replacement value versus the next slot or paper
competitor.

Practical rule:

- every new event family starts paper/default-off;
- every new event field must answer "what does this beat?";
- source quality, peer state, and post-event relative strength have been more
  useful than raw event labels.

### 4. Lifecycle Alpha Is Narrow

Broad exit redesigns and nearby target-width retunes have repeatedly failed.

Practical rule:

- do not widen targets because one winner felt early;
- do not assume a strong sizing state deserves a wider target;
- do not add runner logic without a new state variable and explicit lifecycle
  attribution.

### 5. Missing Fields Block More Alpha Than Bad Thresholds

Many stalled branches are not parameter problems. They are field problems.

Current blockers:

- PIT-safe SEC semantic surprise and guidance fields;
- same-accession filing completeness / quality deltas;
- denser mature forward outcomes in event sleeves;
- richer downstream attribution for LLM-produced semantics;
- better insider / buyback / short-interest context.

Practical rule:

- if the branch cannot be expressed as stable logged fields, stop sweeping
  scalars;
- field work outranks threshold work when the current field set cannot test the
  mechanism honestly.

### 6. Production Visibility Is Part Of Alpha Quality

Backtest-only alpha does not count.

Practical rule:

- prefer shared features, shared sizing tags, and shared policy modules;
- use replay-only logic only when archive gaps make it unavoidable;
- keep event sleeves default-off until the live decision surface can observe the
  same state variables.

### 7. LLM Is A Semantic Compiler, Not A Risk Engine

The repo evidence and the better external work point to the same boundary.

Use LLMs for:

- event classification;
- source-quality tagging;
- guidance / surprise / topic-change extraction;
- ontology growth;
- structured explanation fields for replay and attribution.

Do not use LLMs for:

- hard sizing decisions;
- stop / target ownership;
- slot ownership;
- prompt-only numeric thresholds;
- opaque vetoes without structured attribution.

### 8. Mature-Cohort Coverage Is A Hard Gate

A plausible mechanism is still invalid if it touches too few real rows.

Practical rule:

- do not promote a field or interaction that only changes one or two runtime
  rows;
- if a branch is sample-thin, require new forward evidence or a genuinely new
  field before retrying nearby scalars.

## Practical Build Rules

### 1. New alpha ideas should become fields first

Preferred sequence:

1. define the field;
2. log it in production;
3. verify PIT safety and replayability;
4. measure replacement value or allocation value;
5. only then consider promotion.

### 2. Fields should stay compact and interpretable

Preferred shapes:

- direction buckets such as `up/down/neutral`;
- strength buckets such as `low/med/high` or percentile;
- provenance buckets such as `official/company/regulatory/secondary`;
- cohort flags such as `true/false`;
- one or two scalar diagnostics only when unavoidable.

Avoid giant prompt prose and float spam with no mechanism meaning.

### 3. Every LLM field needs provenance

Minimum desirable metadata:

- source document id;
- event id or accession id;
- system-known timestamp;
- evidence span or chunk reference;
- confidence / consistency tag;
- ontology version.

### 4. Closed-forward fields must remain quarantined

Closed-forward outcomes are valid for:

- default-off paper sleeves;
- replacement-value ranking;
- cohort research;
- future field selection.

They are not valid hidden lookahead inputs for the core live stack.

### 5. External research must translate into one experimentable object

Every paper should map to one of:

- a new field family;
- a new paper sleeve;
- a new allocation state on an existing sleeve;
- an anti-repeat rule that saves future cycles.

If it does not map cleanly, it is background reading, not strategy work.

## Anti-Repeat Rules

Do not retry the following without new evidence, a wider cohort, or a new
production-visible field:

- broad core filters and broad sector/strategy gates;
- global slot, heat, or capacity sweeps;
- broad lifecycle target-width, runner, or trailing-stop retunes;
- nearby `RS20` / `RS60` / own-candle / `clean_spy` scalar tuning;
- nearby `price_vs_200ma` extension and green-deceleration scalar tuning;
- nearby `trend_long` Industrials zero-risk restoration scalars; future work
  needs a new production-visible discriminator, not another partial restore;
- nearby hand-bounded semiconductor non-green trend haircuts; future work needs
  a broader industry field or forward ticker-level contribution evidence;
- simple `exec_lag_adj_net_rr` allocation scalars without a new drawdown or
  catalyst-quality discriminator;
- nearby cap retries after a sleeve-specific cap was already accepted;
- one-ticker cap scouts on accepted sleeves;
- Space ticker-breadth expansion;
- Space theme-beta benchmark ETF admission as trade candidates;
- Space interaction retries supported by only one mature row or one ticker-level
  cohort;
- SEC sleeve retunes that do not add a new filing semantic field;
- public-archive buyback keyword ladders that do not add credibility,
  completion, or cash-support fields;
- LLM veto or ranking expansion without downstream attribution fields.

## What Recent Logs Mean At A Higher Level

Compressing the recent daily runs:

- accepted core changes kept adding small, production-visible allocation states
  on a fixed candidate set;
- accepted sleeve changes mostly came from catalyst quality, source quality,
  peer-relative state, or mature replacement evidence;
- rejected changes were usually broad overlays, nearby retunes, pool expansion,
  slot routing, or sample-thin interactions;
- core cap-based alpha is still real, but the easy cap-room wins are thinning;
- the next wave of alpha is more likely to come from better fields than from
  more scalar tuning.

Default search style should therefore be:

1. add one replayable state variable;
2. keep the candidate set fixed;
3. test allocation before entry/exit redesign;
4. keep event ideas default-off until replacement value closes;
5. convert repeated wins into shared fields, not more prompt prose.

## Research Refresh: Latest Actionable Themes

This section is a research filter, not acceptance evidence. Each item below was
verified against primary sources on 2026-05-16 and must still translate into
fields, sleeves, or attribution.

### 1. PEAD is stronger when the surprise conflicts with prior belief

Source:
[McCarthy 2025, SSRN](https://ssrn.com/abstract=5311906)

Signal:

- recommendation-inconsistent earnings surprises show materially stronger
  post-announcement drift than recommendation-consistent surprises.

Translation:

- add `belief_prior_bucket`, `belief_conflict_flag`,
  `semantic_surprise_direction`, and `semantic_surprise_strength`;
- use inside SEC / earnings sleeves as a quality or allocation state;
- do not turn this into a broad core filter.

### 2. Earnings-call information quality depends on topic divergence and mixed messaging

Sources:
[Xiao 2024, SSRN](https://ssrn.com/abstract=4723491)
[Tabatabaei 2025, SSRN](https://ssrn.com/abstract=5381754)
[Liang and Carrasco Kind 2025, arXiv](https://arxiv.org/abs/2505.18419)

Signal:

- divergence between management topics and analyst-question topics is
  informative;
- inconsistency across management communication channels can recover drift;
- managerial non-responses are associated with worse information environments
  and stronger post-event uncertainty.

Translation:

- add `topic_attention_divergence_bucket`,
  `manager_analyst_topic_gap_flag`, `tone_consistency_bucket`,
  `manager_nonresponse_bucket`, and `cross_channel_tone_gap_flag`;
- use as paper-sleeve quality fields or allocation states;
- do not make them broad vetoes.

### 3. Forecast completeness matters, not just revision direction

Source:
[Perotti and Windisch 2025, Applied Economics abstract](https://www.tandfonline.com/doi/abs/10.1080/00014788.2025.2545847)

Signal:

- market underreaction to forecast revisions changes when cash-flow forecast
  context is present.

Translation:

- add `cash_flow_forecast_present`, `revision_completeness_bucket`, and
  `forecast_bundle_consistency`;
- use only if the underlying filing / guidance source is PIT-safe.

### 4. Buyback alpha is about credibility and commitment, not announcement count

Sources:
[Kaplan et al. 2025, SSRN](https://ssrn.com/abstract=5023151)
[Dechow et al. 2025, SSRN](https://ssrn.com/abstract=5257154)

Signal:

- buyback guidance behaves like a commitment signal;
- disclosure quality around guidance and conference-call communication matters
  more than keyword presence alone.

Translation:

- add `buyback_disclosure_type`, `buyback_guidance_present`,
  `buyback_status_update_type`, `buyback_completion_signal`,
  `buyback_remaining_capacity_signal`, and `cash_support_bucket`;
- keep buyback work default-off first;
- the next buyback branch must be a credibility-field branch, not a better
  keyword ladder.

### 5. Insider buying needs market-structure context

Source:
[Jeon and Sulaeman 2024, Journal of Corporate Finance / SSRN](https://ssrn.com/abstract=4864272)

Signal:

- insider purchase informativeness weakens where options trading activity is
  high; raw filing presence is not enough.

Translation:

- add `options_activity_bucket`, `cluster_buying_flag`,
  `open_market_only_flag`, `officer_seniority_bucket`,
  `non_10b5_1_flag`, and `dollar_size_bucket`;
- keep Form 4 ideas paper/default-off until these context fields exist.

### 6. Short-squeeze alpha must stay narrow and catalyst-conditioned

Sources:
[Bhojraj, Yu, Zhao 2025, SSRN](https://papers.ssrn.com/sol3/Delivery.cfm/3811104.pdf?abstractid=3811104&mirid=1)
[NBER 2025 institutional ownership and short-sale constraints](https://www.nber.org/papers/w22520.pdf)

Signal:

- ownership structure and short-covering constraints matter, but the signal is
  about share scarcity and market structure, not a generic meme-stock branch.

Translation:

- add `short_interest_bucket`, `days_to_cover_bucket`,
  `institutional_ownership_brake`, `borrow_scarcity_flag`, and
  `catalyst_officiality_bucket`;
- only test this as a narrow default-off sleeve when an official positive
  catalyst is already present.

### 7. Mechanical index events remain attractive because they are interpretable

Sources:
[Sammon and Shim 2025, SSRN / JFE](https://ssrn.com/abstract=5080459)
[Chang et al. 2025, SSRN](https://ssrn.com/abstract=4476422)

Signal:

- predictable rebalancing flows and index-tracking rigidity still create
  mechanical event pressure, though the broad "index effect" is more crowded
  than before.

Translation:

- add `index_event_type`, `effective_date`, `pre_event_rank_distance`,
  `rebalance_flow_window`, and `passive_flow_pressure_bucket`;
- this belongs in a paper sleeve first because it is easy to audit and does not
  need LLM ambiguity.

### 8. Financial LLM work supports schema-first extraction, taxonomy alignment, and PIT evidence

Sources:
[FinTagging 2025, arXiv](https://arxiv.org/abs/2505.20650)
[Agentic Retrieval of Topics and Insights from Earnings Calls 2025, arXiv](https://arxiv.org/abs/2507.07906)
[QuantMind 2025, arXiv](https://arxiv.org/abs/2509.21507)

Signal:

- financial extraction quality improves when text extraction, table extraction,
  taxonomy alignment, and evidence attribution are treated as distinct tasks;
- topic ontology should be hierarchical and replayable, not flat keyword bags;
- PIT correctness and provenance are core system requirements, not polish.

Translation:

- every new LLM workflow should emit schema-bound JSON first;
- text and table extraction should be logged as separate failure modes;
- ontology growth must be versioned and replayable;
- evidence spans and source ids must be logged with the field.

## Field-Building Roadmap

When new research becomes actionable, the first deliverable should be a field,
not a live rule.

Highest-priority field families:

1. SEC / earnings semantics:
   `semantic_surprise_direction`, `semantic_surprise_strength`,
   `belief_conflict_flag`, `guidance_delta_direction`,
   `topic_attention_divergence_bucket`, `tone_consistency_bucket`,
   `manager_nonresponse_bucket`.
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
   `short_interest_bucket`, `days_to_cover_bucket`,
   `institutional_ownership_brake`, `borrow_scarcity_flag`,
   `catalyst_officiality_bucket`.
6. Event ontology:
   `event_family_v2`, `event_source_quality`, `event_novelty_bucket`,
   `topic_path`, `topic_conflict_flag`.

Field-building rule:

- if the idea cannot yet be turned into stable, logged, PIT-safe fields, it is
  probably not ready for alpha work.

## Current Research Queue

Priority is ordered by expected value, replayability, and implementation
clarity.

1. SEC earnings semantic expansion.
   Build belief-conflict, guidance, topic-divergence, non-response, and same-
   accession quality fields before any more SEC sleeve threshold work.
2. Buyback credibility sleeve v2.
   Resume only with status, guidance, completion, and cash-support fields.
3. High-quality insider buying.
   Resume only with options-activity and purchase-quality context.
4. Mechanical index-event paper sleeve.
   Attractive because it is interpretable, PIT-manageable, and does not depend
   on prompt-heavy semantics.
5. Short-interest plus official catalyst sleeve.
   Build as a narrow default-off overlay with ownership / borrow braking.
6. Space mature-cohort expansion.
   Continue only when broader mature outcome cohorts or new production-visible
   catalyst-quality fields exist.
7. LLM ontology and field quality.
   Improve extraction, provenance, and attribution before expanding LLM
   authority.

## Exploratory Backlog

Valid but lower-priority ideas:

- analyst revision momentum outside SEC sleeves;
- spin-offs, asset sales, and capital-structure events;
- thematic second-order supply-chain events;
- volatility-state lifecycle allocation;
- market-breadth deployment state;
- accounting-quality downside filters;
- slow profitability / quality overlays;
- defensive deployment overlays.

Backlog rule:

- prefer one new replayable field over one more retune of an accepted scalar.

## Measurement And Parity Reminders

Measurement work should outrank alpha search only when it unblocks a stronger
experiment. Valid blockers include:

- missing runtime fields;
- missing PIT-safe semantic features;
- production / backtest divergence;
- missing mature forward outcomes;
- missing prompt/log/replay fields for LLM-derived semantics.

If a branch is blocked by fields, say so explicitly and move to the next valid
family rather than sweeping nearby thresholds.

## Update Discipline

Update this file only when one of these changes:

- a new checkpoint changes the canonical mechanism-level stack;
- a family changes from promising to blocked, rejected, or accepted;
- a new anti-repeat rule becomes durable;
- new research changes the field-building queue;
- a measurement blocker becomes the main constraint on a high-value idea.

Write synthesis first. Keep experiment IDs sparse and only as anchors for
durable conclusions.
