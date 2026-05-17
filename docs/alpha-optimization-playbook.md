# Alpha Optimization Playbook

This file is the durable synthesis layer between [`AGENTS.md`](D:/Github/ginger/AGENTS.md),
[`docs/backtesting.md`](D:/Github/ginger/docs/backtesting.md), and
[`docs/experiment_log.jsonl`](D:/Github/ginger/docs/experiment_log.jsonl).

It is not an experiment diary. Its job is to compress repository evidence into:

- default search priors;
- durable anti-repeat rules;
- research themes that can be translated into replayable fields;
- the current highest-value experimental directions.

Last refreshed: 2026-05-17.

## How To Use This Playbook

Before any strategy change, answer:

1. Is the next best idea an allocation idea, a field idea, an entry idea, an
   exit idea, or a candidate-pool idea?
2. Has a nearby version already failed on the canonical windows?
3. Can the idea be expressed as one production-visible, replayable variable?
4. If not, which field/log/parity gap blocks it?

Default workflow:

1. Prefer `alpha_search` over `measurement_repair` unless measurement is the
   direct blocker.
2. Prefer fixed candidate set + better capital allocation over broader entry
   filtering.
3. Prefer one new field over one more scalar retune.
4. Prefer shared production-visible policy over backtest-only logic.
5. Prefer default-off paper sleeves before live promotion.

## Current Mechanism View

Ginger remains an event-enhanced medium-term trend / breakout system.

Current evidence says the stack works best when it is split this way:

1. Core trend / breakout candidate generation stays relatively stable.
2. Most incremental alpha comes from small, state-conditioned, cap-aware
   allocation changes on already-qualified signals.
3. Event sleeves earn attention only when they prove replacement value against
   the next core slot.
4. LLMs are most useful as structured field builders, not as final risk or
   execution owners.

The latest accepted core stack still reinforces the same message:

- the accepted scarce-slot rank-1 top-up (`available_slots == 1`) is an
  allocation edge, not a reranking edge;
- the accepted stock-only ample-slot rank-1 top-up (`available_slots >= 4`,
  excluding ETF / Commodity sectors) shows that broad ample-slot promotion was
  too noisy, but a production-visible sector boundary can preserve the useful
  allocation state;
- recent accepts are mostly small post-sizing promotions on fields already
  known at signal time;
- adjacent two-slot and broad ample-slot generalizations failed, which implies
  that the easy capacity-routing gains are thinning and state definitions now
  matter more than raw multiplier mining.

The latest accepted default-off state-surface evidence adds one durable paper
candidate-pool rule: after restricting the paper satellite to
`rotation_breakout_leadership`, candidate-level `ret20_excess_spy >= 0.0`
improved the three-window paper overlay (`exp-20260517-016`: aggregate EV
`+0.2234`, PnL `+$2,449.90`) without reducing selected trade count or raising
single-ticker concentration. Treat this as a shared default-off audit/paper
queue quality gate, not live capital permission; forward closed paper outcomes
are still required before any trade adapter can be enabled.

## Durable Laws From Repository Evidence

### 1. Allocation Beats Filtering

This is the strongest repeated result in the repo.

What keeps working:

- small post-sizing top-ups on already-qualified signals;
- sleeve-specific cap release on already-strong cohorts;
- narrow state-conditioned risk promotion with unchanged entry logic;
- paper replacement routing before live admission.

What keeps failing:

- broad new filters;
- broad quality overlays;
- broad slot reranking;
- broad candidate-pool expansion;
- nearby scalar retunes after a state has already been accepted.

Default prior:

- if the proposal changes who is allowed to trade across a broad class, it
  starts with a weak prior;
- if the proposal changes how already-good signals are sized, it starts with a
  stronger prior.

### 2. Candidate Quality Matters More Than Rule Cleverness

The repo repeatedly shows that extra logic does not rescue a noisy cohort.

Practical rule:

- keep the candidate set fixed when possible;
- add one ex-ante state variable before adding another generic guardrail;
- if the idea needs many exceptions, it is probably overfit already.

### 3. Replacement Value Beats Narrative Quality

Event stories are not enough. The event branch improves only when the system
can answer: why does this deserve capital over the next slot competitor?

Practical rule:

- every event family must eventually produce replacement-value evidence;
- if a sleeve cannot beat the next core competitor in paper form, do not route
  live capital there;
- better story labeling without capital-routing evidence is research, not alpha.

### 4. Small, Capped, Conditional Changes Dominate Big Rewrites

Recent accepted changes are generally narrow:

- small multipliers;
- narrow state buckets;
- shared production-visible fields;
- no change to trade count or survival;
- limited drawdown drift.

Recent rejected changes are generally broad:

- pool expansion;
- broad slot priority changes;
- generic target-width rewrites;
- mirror-image penalties without independent evidence.

Practical rule:

- look for the smallest intervention that isolates one mechanism;
- avoid global parameter motions unless they are backed by a genuinely new
  field or a strong forward cohort.

### 5. Ticker-Specific Exceptions Are Valid but Dangerous

The accepted `TSM` and `ISRG` haircuts show that some residual losses are real,
but they also show why nearby generalization is dangerous.

Practical rule:

- a ticker exception is acceptable only when it improves multiple windows,
  remains production-visible, and resists simple nearby alternatives;
- a ticker exception does not automatically justify a sector rule;
- after one exception is accepted, nearby retries should be frozen until new
  forward evidence appears.

### 6. Bad Longs Are Not Automatically Good Shorts

The core-misfit work produced real no-trade and inverse-paper evidence, but not
enough to justify live shorting.

Practical rule:

- separate three questions:
  no-trade avoided loss, fast-exit rescue, inverse-paper outcome;
- require closed forward paper outcomes before converting a bad long cohort
  into a live exclusion or short rule;
- treat inverse evidence as a paper research queue until it clears multi-window
  and execution-friction gates.

### 7. LLM Value Comes From Structure, Not Authority

The repo's repeated failure mode was never "too little prompt text." It was
weak structure, weak provenance, and weak replayability.

Practical rule:

- code owns position sizing, hard exits, risk budgets, slots, and gates;
- LLM owns event understanding, topic extraction, semantic conflict detection,
  credibility tagging, and disaster-style veto candidates;
- every LLM output should become schema-bound fields with provenance and
  attribution, not free-form execution judgment.

### 8. Mature-Cohort Coverage Is A Hard Gate

A plausible mechanism is still invalid if it touches too few rows.

Practical rule:

- do not promote a rule that only changes one or two historical rows;
- if the sample is thin, wait for forward evidence or introduce a materially
  new field rather than retuning the same scalar;
- a directionally positive micro-cohort is a research clue, not acceptance
  evidence.
- the 2026-05-17 Financials breakout DTE haircut was directionally positive
  but only touched two signals, so nearby DTE scalar sweeps should stay frozen
  until forward evidence or a new quality field appears.

## What The Recent Logs Mean At A Higher Level

Compressing the recent accepted and rejected runs:

- accepted core changes mostly improved allocation on a fixed candidate set;
- accepted sleeve changes mostly came from catalyst quality, source quality,
  peer-relative state, or mature replacement evidence;
- rejected changes were usually broad overlays, pool expansion, slot routing,
  lifecycle retunes, or sample-thin interactions;
- the easy cap-room wins are becoming thinner, including adjacent scarce-slot
  and broad ample-slot top-up attempts; the stock-only ample-slot accept is a
  discriminator lesson, not permission for nearby raw scalar sweeps;
- the post-exp009 event rotation revalidation (`exp-20260517-010`) is now the
  strongest near-term replay-only alpha evidence: it improved all three
  standard windows versus the current paper lead without changing the core
  candidate set or live/default orders;
- the state-surface rotation-only replay (`exp-20260517-014`) converted the
  same rotation leadership idea into default-off paper candidate eligibility:
  `rotation_breakout_leadership` only, full scored-candidate audit retained,
  and no live/default orders;
- the next wave of alpha is more likely to come from better fields than from
  another round of neighboring scalar sweeps.

Default search style should therefore be:

1. add one replayable state variable;
2. keep the candidate set fixed;
3. test allocation before entry/exit redesign;
4. keep event ideas default-off until replacement value closes;
5. convert repeated wins into shared fields, not more prompt prose.

## Current High-Value Search Priorities

Priority is ordered by expected value, replayability, implementation clarity,
and consistency with recent repo evidence.

### 1. Event Rotation Replacement-Value Maturation

This is the strongest near-term alpha lane after `exp-20260517-010` because:

- it has repeated three-window evidence after the latest accepted core stack;
- it keeps the core candidate set fixed and changes only default-off event
  paper allocation;
- it already uses a shared paper attribution path, so production/backtest
  consistency risk is lower than a new backtest-only sleeve.

Default use:

- keep `rotation_breakout_leadership` paper allocation default-off until closed
  forward replacement-value evidence exists;
- do not keep sweeping nearby notional scalars on the frozen sample;
- next useful work is forward maturation, trade-enabled adapter design, and
  parity tests for any future live/default promotion.

### 2. SEC / Earnings Semantic Expansion

This remains the highest-value field-building research lane because:

- it fits the event-enhanced doctrine;
- it is still field-limited rather than obviously alpha-empty;
- it can improve allocation and replacement ranking without broadening core
  discretion.

Preferred deliverables:

- `semantic_surprise_direction`
- `semantic_surprise_strength`
- `belief_conflict_flag`
- `guidance_delta_direction`
- `topic_attention_divergence_bucket`
- `manager_nonresponse_bucket`
- `tone_consistency_bucket`
- `cross_channel_tone_gap_flag`

Default use:

- SEC / earnings paper sleeves first;
- allocation states second;
- never a broad core veto first.

### 3. Buyback Credibility Sleeve v2

Buyback work should resume only as a credibility-field branch, not as a
keyword-coverage branch.

Preferred deliverables:

- `buyback_disclosure_type`
- `buyback_guidance_present`
- `buyback_status_update_type`
- `buyback_completion_signal`
- `buyback_remaining_capacity_signal`
- `cash_support_bucket`

Default use:

- default-off paper sleeve first;
- promote only after replacement-value evidence closes.

### 4. High-Quality Insider Buying

Form 4 ideas remain attractive, but current evidence says raw filing presence
is not enough.

Preferred deliverables:

- `options_activity_bucket`
- `cluster_buying_flag`
- `open_market_only_flag`
- `officer_seniority_bucket`
- `non_10b5_1_flag`
- `dollar_size_bucket`

Default use:

- default-off queue or paper sleeve first;
- do not resume scalar tuning on sparse filing fields.

### 5. Mechanical Index / Passive Flow Event Sleeve

This is attractive because it is interpretable, easy to audit, and less
dependent on LLM ambiguity.

Preferred deliverables:

- `index_event_type`
- `effective_date`
- `pre_event_rank_distance`
- `rebalance_flow_window`
- `passive_flow_pressure_bucket`

Default use:

- paper sleeve first;
- use deterministic sources and PIT timestamps.

### 6. Core-Misfit Paper Maturation

This is not a new live rule search yet. It is a forward evidence program.

What matters next:

- mature no-trade avoided value;
- mature inverse-paper value;
- segment-level clustering by ticker, setup family, and market state;
- proof that any future exclusion or short rule is not just one bad window.

### 7. Event Taxonomy / Ontology Quality

The repo is increasingly constrained by ontology quality, not just by missing
news text.

Preferred deliverables:

- `event_family_v2`
- `event_source_quality`
- `event_novelty_bucket`
- `topic_path`
- `topic_conflict_flag`
- ontology versioning and evidence spans

## Research Refresh: Latest Actionable Themes

This section is a research filter, not acceptance evidence. These themes were
reviewed on 2026-05-17 and should be translated only into fields, paper
sleeves, or anti-repeat rules.

### 1. Peer earnings spillovers look more tradable when relatedness is explicit

Recent source:

- Eli Bartov, Greg Clinch, Wei Li, "Information Spillovers from Earnings
  Announcements: Evidence from Economically Related Firms," SSRN, dated
  January 3, 2026.

Repository implication:

- peer effects should not be modeled with crude industry buckets alone;
- the better translation is a relatedness field around shared analyst coverage
  or other explicit economic linkage.

Candidate fields:

- `peer_event_relatedness_bucket`
- `shared_analyst_coverage_flag`
- `peer_earnings_spillover_window`
- `peer_reaction_strength_bucket`

Why it fits Ginger:

- it upgrades earnings/event replacement ranking without broadening LLM
  discretion;
- it can remain paper-only until replacement value is proven.

### 2. Earnings-call reaction bias is about information type, not just tone

Recent source:

- Zhenzhen Fan and Fred Liu, "Do Investors Get It Right? Reaction Bias to
  Earnings Calls?" SSRN, dated October 3, 2025.

Repository implication:

- investors and analysts appear to react differently to tangible operational
  facts versus vague or affective narrative;
- the useful output is not raw sentiment, but a split between verifiable and
  narrative-heavy content.

Candidate fields:

- `operational_fact_density_bucket`
- `narrative_vagueness_bucket`
- `reaction_bias_flag`
- `analyst_tangible_vs_affective_gap`

Practical use:

- apply as event-sleeve quality or earnings allocation state;
- do not convert directly into a broad core filter.

### 3. Topic divergence and non-response remain strong call-quality signals

Recent sources:

- Zicheng Xiao, "Measuring Information Quality by Topic Attention Divergence:
  Evidence from Earnings Calls," SSRN, dated February 12, 2024.
- Qingwen Liang and Matias Carrasco Kind, "How do managers' non-responses
  during earnings calls affect analyst forecasts," arXiv, submitted May 23,
  2025.

Repository implication:

- call quality is not one scalar;
- divergence between management emphasis and analyst questioning, plus explicit
  managerial non-responses, should be logged separately.

Candidate fields:

- `topic_attention_divergence_bucket`
- `manager_analyst_topic_gap_flag`
- `manager_nonresponse_bucket`
- `uncertainty_escalation_flag`

Practical use:

- use as quality state inside earnings sleeves;
- combine with existing replacement-value logic before any live promotion.

### 4. Cross-channel inconsistency may recover narrative PEAD where classic SUE drifts fade

Recent source:

- Elham Tabatabaei, "Mixed Messages: Strategic Tonal Inconsistency and Recovery
  of the PEAD Anomaly," SSRN, dated July 31, 2025.

Repository implication:

- conference-call tone and contemporaneous press-release tone should not be
  collapsed into one label;
- inconsistency itself may be the field.

Candidate fields:

- `cross_channel_tone_gap_flag`
- `call_release_consistency_bucket`
- `mixed_message_strength_bucket`

Practical use:

- sleeve quality and ranking state;
- not a universal veto.

### 5. KPI extraction work strengthens the case for schema-first earnings-call pipelines

Recent source:

- Rasmus T. Aavang et al., "Effective Performance Measurement: Challenges and
  Opportunities in KPI Extraction from Earnings Calls," arXiv, submitted
  May 4, 2026.

Repository implication:

- earnings calls should be treated as a separate extraction domain, not as SEC
  filings with weaker labels;
- schema-bound KPI extraction can become a reusable field source for both
  direction and credibility.

Candidate fields:

- `kpi_delta_direction`
- `kpi_guidance_change_bucket`
- `kpi_surprise_vs_prior_bucket`
- `kpi_extraction_coverage_flag`
- `kpi_evidence_span_count`

Practical use:

- build extraction QA before using KPI fields in alpha;
- track text extraction failures and missing-evidence failures separately.

### 6. Event-centric model design supports hierarchical event schemas, not end-to-end black boxes

Recent source:

- Xiang Li et al., "Janus-Q: End-to-End Event-Driven Trading via
  Hierarchical-Gated Reward Modeling," arXiv, submitted February 23, 2026.

Repository implication:

- the useful lesson is not "replace the stack with RL";
- the useful lesson is that event units, typed reward trade-offs, and
  hierarchical gating should be explicit.

Candidate translations:

- use hierarchical event labels instead of flat keyword bags;
- separate reward dimensions in attribution:
  return, drawdown, hit rate, holding time, replacement value;
- keep any learned event scorer inside a paper/default-off branch until it is
  auditable.

### 7. Buyback guidance is a commitment signal, not just a repurchase mention

Recent source:

- Zachary Kaplan, Adriano Salerno, Lauren Vollon, Xiaoxi Wu,
  "Commitment through forecasting: Managerial buyback guidance and payout
  policy," SSRN, revised July 15, 2025.

Repository implication:

- buyback alpha likely depends on disclosed commitment quality and remaining
  flexibility, not just announcement count.

Candidate fields:

- `buyback_guidance_present`
- `guidance_as_lower_bound_flag`
- `buyback_commitment_strength_bucket`
- `repurchase_consistency_bucket`

Practical use:

- default-off buyback sleeve only;
- do not build another keyword ladder first.

### 8. Insider buying needs options-market context

Recent source:

- Byounghyun Jeon and Johan Sulaeman, "Corporate Insider Purchases and the
  Options Market: Competition among Informed Investors," Journal of Corporate
  Finance / SSRN, dated June 13, 2024.

Repository implication:

- insider purchases in high-options-activity names appear less informative;
- Form 4 logic should incorporate market-structure context before any new
  allocation or ranking attempt.

Candidate fields:

- `options_activity_bucket`
- `options_competition_flag`
- `insider_purchase_context_quality`

### 9. Firm-level geopolitical exposure is becoming easier to operationalize from earnings text

Recent source:

- Dongxu Li, Xiaoran Ni, Ruiyang Zou, "An Earnings-based Measure of Firm-level
  Geopolitical Risk," SSRN, dated January 23, 2026.

Repository implication:

- geopolitical risk should be represented as firm-level event exposure fields,
  not only macro regime labels;
- this is especially relevant for AI infra, semis, defense, and supply-chain
  event cohorts.

Candidate fields:

- `firm_geopolitical_risk_bucket`
- `geopolitical_topic_path`
- `geopolitical_exposure_change_flag`
- `call_level_geopolitical_intensity`

Practical use:

- first as attribution and sleeve-quality metadata;
- later as allocation state if replacement value appears.

### 10. Topic ontology management itself is now a measurable edge in financial LLM pipelines

Recent source:

- Anant Gupta, Rajarshi Bhowmik, Geoffrey Gunow, "Agentic Retrieval of Topics
  and Insights from Earnings Calls," arXiv, submitted July 10, 2025.

Repository implication:

- topic systems should support emergence, hierarchy, and mapping from new to
  old concepts;
- flat event tags will increasingly miss where new alpha first appears.

Candidate fields:

- `topic_path`
- `emerging_topic_flag`
- `topic_shift_vs_prior_call`
- `ontology_version`

## Practical Field-Building Rules

### 1. New Alpha Ideas Should Become Fields First

Preferred sequence:

1. define the field;
2. log it in production;
3. verify PIT safety and replayability;
4. measure replacement value or allocation value;
5. only then consider promotion.

### 2. Fields Should Stay Compact and Interpretable

Preferred shapes:

- direction buckets such as `up/down/neutral`;
- strength buckets such as `low/med/high` or percentile;
- provenance buckets such as `official/company/regulatory/secondary`;
- cohort flags such as `true/false`;
- one or two scalar diagnostics only when unavoidable.

Avoid:

- giant prompt prose as implicit logic;
- dense float spam without mechanism meaning;
- mixed hard-risk and soft-semantic outputs in one field.

### 3. Every LLM Field Needs Provenance

Minimum metadata:

- source document id;
- event id or accession id;
- system-known timestamp;
- evidence span or chunk reference;
- confidence / consistency tag;
- ontology version.

### 4. Closed-Forward Outcomes Stay Quarantined

Closed-forward outcomes are valid for:

- default-off paper sleeves;
- replacement-value ranking;
- cohort research;
- future field selection.

They are not valid hidden lookahead inputs for the live core stack.

## Anti-Repeat Rules

Do not retry the following without new evidence, a wider cohort, or a new
production-visible field:

- broad core filters and broad sector/strategy gates;
- broad slot, heat, or capacity sweeps;
- nearby two-slot scarce-slot top-ups;
- broad ample-slot rank-1 top-ups, or nearby stock-only ample-slot scalar /
  sector-boundary retries without a new production-visible discriminator;
- rotation-only state-surface benchmark momentum gate threshold retunes on the
  frozen windows; `exp-20260517-015` showed `0.5%` was identical to the current
  `0.0` threshold and `1.0%+` removed useful old-window paper trades;
- nearby state-surface `ret20_excess_spy` floor retunes above the accepted
  `0.0` gate on frozen windows; `exp-20260517-016` showed `5%` was identical
  and `10%+` started removing useful paper trades;
- nearby Financials breakout DTE risk scalars on the current two-signal
  frozen-window sample;
- broad lifecycle target-width, runner, or trailing-stop retunes;
- nearby `RS20` / `RS60` / own-candle / `clean_spy` scalar retunes;
- nearby `price_vs_200ma` and green-deceleration scalar retunes;
- nearby Industrials zero-risk restoration without a new discriminator;
- nearby semiconductor non-green haircuts without a broader cohort;
- nearby `TSM` and `ISRG` residual retunes without new forward evidence;
- broad Space ticker-breadth expansion;
- Space interaction retries supported by one ticker or one mature row;
- SEC sleeve retunes that do not add new filing or call semantics;
- buyback work that only adds keyword coverage;
- Form 4 work that ignores options-market context;
- LLM veto/ranking expansion without attribution fields.

## Update Discipline

Update this file only when one of these changes:

- a new result changes the mechanism-level prior;
- a family moves from promising to blocked, rejected, or accepted;
- a new anti-repeat rule becomes durable;
- a new research theme changes the field-building queue;
- a measurement blocker becomes the main constraint on a high-value idea.

Write synthesis first. Keep experiment IDs sparse and only as anchors for
durable conclusions.
