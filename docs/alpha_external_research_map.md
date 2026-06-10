# Alpha External Research Map

External research notes moved out of `docs/alpha-optimization-playbook.md`.
Use this file when converting research literature into replayable fields or bounded LLM infrastructure ideas.

This is an idea map, not an accepted-strategy source. The current operating
rules, readout, research queue, and anti-repeat rules remain in
`docs/alpha-optimization-playbook.md`; accepted/rejected experiment facts live
in raw experiment records and generated `docs/lessons/*.md`.

## External Research Mapped To Ginger

These are not authority to add models. They are design patterns that must be
converted into auditable fields and tested through Gate 1-4.

### State-Dependent Predictability

NBER's 2026 "Mosaics of Predictability" argues that return predictability is
latent, asset-specific, and state-dependent. This matches Ginger's evidence:
generic broad signals often look positive in aggregate but fail by window,
drawdown, or tail.

Implementable fields:

- `predictability_mosaic_bucket`
- `asset_specific_predictability_score`
- `state_conditioned_signal_validity_bucket`
- `earnings_surprise_predictability_bucket`
- `liquidity_regime_predictability_bucket`

Source: <https://www.nber.org/papers/w35158>

### Agentic LLM Portfolio Control

Recent regime-aware LLM portfolio research supports a strict boundary: LLMs can
produce sentiment/uncertainty views, but execution should be governed by a
transparent state-action-controller with cost gates, turnover budgets, dynamic
caps, and deterministic constraints.

Implementable fields:

- `llm_view_expected_return_bucket`
- `llm_view_confidence_calibration_bucket`
- `state_action_controller_version`
- `dynamic_position_cap_reason`
- `turnover_budget_remaining`
- `friction_gate_passed`
- `constraint_shadow_price_bucket`

Source: <https://link.springer.com/article/10.1007/s41060-026-01066-0>

### Index-To-Equity Transfer Learning

Recent transformer work shows that pre-training on market-index behavior can
improve individual-stock prediction loss, but benchmark models may still beat
it on realized daily returns. For Ginger, this supports market-state transfer
features, not a black-box forecaster.

Implementable fields:

- `index_pretrained_state_embedding_id`
- `index_to_equity_transfer_score_bucket`
- `market_state_feature_source_id`
- `prediction_loss_vs_return_gap_bucket`
- `model_signal_after_cost_validity_bucket`

Source: <https://arxiv.org/abs/2605.23962>

### Graphs, Correlations, And Market Structure

2026 graph/transformer research emphasizes dynamic relations, stock-stock
correlations, industry links, and macro inputs. The local lesson is that edge
construction is the alpha hypothesis.

Implementable fields:

- `market_structure_graph_bucket`
- `graph_edge_construction_method`
- `forward_correlation_cluster_bucket`
- `stress_cluster_membership_bucket`
- `correlation_forecast_residual_bucket`
- `graph_neighbor_importance_bucket`

Use these first for risk, basket construction, and displacement accounting.
Direct alpha use needs separate evidence.

Sources:

- <https://arxiv.org/abs/2601.04602>
- <https://www.sciencedirect.com/science/article/pii/S0952197626010080>
- <https://arxiv.org/abs/2603.05917>

### Transaction-Cost Trap

Recent transaction-cost research reinforces Ginger's local rule: prediction
accuracy, IC, or paper PnL can be economically negative after frictions. Every
candidate pool must report net-of-cost replacement value against the exact
alternative it displaces.

Implementable fields:

- `expected_round_trip_cost_bucket`
- `spread_liquidity_cost_bucket`
- `turnover_pressure_bucket`
- `cost_adjusted_replacement_value_pnl`
- `accepted_comparator_net_cost_delta`
- `precision_trade_rate_floor_passed`
- `net_alpha_after_turnover_cost`
- `borrow_fee_cost_bucket`
- `hard_to_borrow_availability_bucket`

Source: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6422358>

### Agentic Nowcasting

Agentic AI nowcasting papers suggest that autonomous information gathering can
rank stocks, but the Ginger-compatible interpretation is narrower: persist what
was retrieved, why it mattered, and whether it beat the displaced candidate
after costs. Do not let the agent choose trades directly.

Implementable fields:

- `agentic_retrieval_query_id`
- `retrieved_source_set_hash`
- `nowcast_reason_code`
- `nowcast_confidence_bucket`
- `source_coverage_gap_bucket`
- `agentic_view_replay_hash`
- `nowcast_replacement_value_bucket`

Source: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6134446>

### LLM Financial-Headline Alpha

Recent headline-alpha work reports that LLM-derived financial-news sentiment
can produce positive alpha when the model is sufficiently capable and the output
is used as a rank-based portfolio signal. Ginger should treat this as support
for structured text fields, not direct LLM trading.

Implementable fields:

- `headline_llm_model_id`
- `headline_source_timestamp`
- `headline_sentiment_rank_bucket`
- `headline_event_family_bucket`
- `headline_signal_complexity_floor_passed`
- `headline_source_coverage_fraction`
- `headline_rank_replacement_value_bucket`
- `headline_model_disagreement_bucket`

Controls:

- archive the exact headline set and model/schema version;
- compare against accepted non-text comparators after costs;
- require model disagreement / calibration reporting before any paper adapter;
- do not use raw positive sentiment when the event family, timestamp, or source
  coverage is missing.

Source: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6597694>

### Human-Directed LLM Beats Autonomous LLM

New 2026 live-signal evidence argues for structured human direction and
game-theoretic scaffolding over autonomous LLM trading. This reinforces
Ginger's boundary: the LLM can classify, explain, and expose uncertainty, while
deterministic code owns execution, sizing, exits, and constraints.

Implementable fields:

- `llm_scaffold_id`
- `llm_game_type_bucket`
- `llm_independent_verdict_bucket`
- `llm_autonomous_vs_scaffold_delta_bucket`
- `llm_signal_frequency_budget_remaining`
- `llm_view_volatility_bucket`
- `human_direction_context_hash`

Controls:

- preserve the prompt/scaffold and source set as replay artifacts;
- measure whether the scaffold reduces weak buy frequency, turnover, and
  volatility, not just whether it increases bullish calls;
- never let consensus magnitude or autonomous LLM conviction override the
  shared policy gate.

Source: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6705178>

### Agentic Financial RAG Self-Verification

Agentic RAG research for financial document QA emphasizes iterative retrieval,
reasoning, and self-verification for numerical precision. For Ginger, the
tradable implication is not "ask an agent to trade"; it is to store retrieval
coverage, verification failures, and evidence-span confidence before any SEC,
earnings, or news semantic field can affect a paper sleeve.

Implementable fields:

- `rag_retrieval_loop_count`
- `rag_source_set_hash`
- `rag_numeric_self_check_passed`
- `rag_evidence_span_confidence_bucket`
- `rag_missing_source_reason`
- `rag_contradiction_bucket`
- `rag_verified_event_field_version`

Controls:

- fail closed when source spans or numeric self-checks are missing;
- keep retrieval and verification artifacts replayable by timestamp;
- promote only schema-bound fields with Gate 1-4 evidence.

Source: <https://arxiv.org/abs/2605.05409>

### Market-Feedback Adaptive Financial RAG

May 2026 work on market-feedback adaptive retrieval for frozen LLMs is directly
compatible with Ginger's default-off evidence model. The useful adaptation is
not fine-tuning the reader after every outcome; it is learning which source
families helped after residual-return labels mature, then using that
source-memory state only for future PIT retrieval.

Implementable fields:

- `event_rag_source_memory_version`
- `event_rag_anchor_timestamp`
- `event_rag_source_family`
- `event_rag_event_type_bucket`
- `event_rag_horizon_bucket`
- `event_rag_residual_label_version`
- `event_rag_source_utility_bucket`
- `event_rag_market_context_card_hash`
- `event_rag_feedback_matured_flag`
- `event_rag_reader_model_id`

Controls:

- update source memory only after the relevant 5/10/20-day residual label has
  matured;
- keep the LLM reader frozen or versioned so performance attribution belongs
  to retrieval/source memory, not hidden model drift;
- archive the anchor, retrieved evidence set, market-context card, schema, and
  output hash;
- compare any RAG-assisted candidate against the exact accepted helper or cash
  it displaces after costs.

Source: <https://arxiv.org/abs/2605.31201>

### Agentic Trading Evidence Ledger

A May 2026 survey of LLM trading-agent studies finds that evaluation protocols
are still not comparable: only a small minority of closed-loop studies report
time-consistent splits, transaction costs, survivorship/universe handling, or
full reproducibility. This directly supports Ginger's Gate 1-4 discipline: an
agent architecture is not alpha evidence unless it comes with execution timing,
costs, universe controls, and replay artifacts.

Implementable fields:

- `agentic_signal_protocol_id`
- `agentic_signal_universe_control_bucket`
- `agentic_signal_execution_semantics_bucket`
- `agentic_signal_cost_model_version`
- `agentic_signal_replay_artifact_hash`
- `agentic_signal_reproducibility_tier`
- `agentic_signal_closed_loop_eval_flag`

Controls:

- agent outputs must be logged as evidence rows before they affect paper
  adapters;
- every agent-produced candidate must report the exact comparator it would
  displace;
- reject any agent alpha claim that lacks costs, execution timing, universe
  controls, or replayable source artifacts.

Source: <https://arxiv.org/abs/2605.19337>

### Interaction-Native Agent Memory

Recent financial-agent memory work argues for passive context injection,
temporal graph memory, wiki-style audit surfaces, and write-time invalidation.
For Ginger, this maps cleanly to context packs, lesson cards, daily snapshots,
and anti-repeat rules: memory should reduce repeated bad experiments and stale
assumptions, not expand model discretion.

Implementable fields:

- `context_memory_snapshot_hash`
- `retrieved_lesson_card_ids`
- `stale_memory_invalidation_reason`
- `decision_context_buffer_version`
- `memory_maturity_bucket`
- `memory_decay_bucket`
- `audit_surface_link_id`

Controls:

- before alpha search, retrieve the relevant mechanism card and nearest
  rejected neighbors;
- invalidate memory when a shared adapter or parity contract supersedes a
  private replay lead;
- measure whether memory reduces near-neighbor duplicate experiments.

Source: <https://arxiv.org/abs/2606.01886>

### LLM News Sentiment As Modest Feature

2026 news-sentiment studies continue to find that LLM-derived sentiment can
improve some stock-movement prediction setups, but the reported benefit is
model- and architecture-dependent and often modest. This fits Ginger's local
evidence: raw positive text or headline sentiment is too weak; sentiment must
be tied to event family, timestamp, coverage, and replacement value.

Implementable fields:

- `news_sentiment_model_family`
- `news_sentiment_daily_aggregation_method`
- `news_sentiment_coverage_fraction`
- `news_sentiment_event_family_bucket`
- `news_sentiment_model_disagreement_bucket`
- `news_sentiment_incremental_feature_delta`
- `news_sentiment_replacement_value_bucket`

Controls:

- archive the exact headline/article set and timestamp;
- report coverage gaps before scoring results;
- compare sentiment-assisted candidates against accepted non-text comparators
  after costs;
- do not promote daily sentiment averages without event-family and source
  provenance.

Sources:

- <https://arxiv.org/abs/2602.00086>
- <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6597694>

### Adaptive Relation Graphs

New graph-learning stock-prediction work emphasizes adaptive correlations and
heterogeneous relations rather than static sector labels. This reinforces the
local lesson from rolling-correlation peer shock and industry-relative laggard
repair: edge construction is the hypothesis, and a static group label is rarely
enough.

Implementable fields:

- `adaptive_relation_graph_version`
- `dynamic_edge_method_id`
- `edge_asof_timestamp`
- `edge_decay_half_life_days`
- `heterogeneous_relation_type`
- `edge_stability_bucket`
- `edge_displacement_comparator_id`

Controls:

- start with attribution or default-off paper, not core ranking;
- require PIT-valid edge timestamps and no future membership leakage;
- compare directly against accepted relation adapters before promotion.

Source: <https://www.sciencedirect.com/science/article/pii/S0031320326005716>

### Relation Score Gating And Crosstalk Control

June 2026 cross-sectional stock-prediction work highlights two practical
failure modes that match Ginger's relation experiments: stale relation graphs
can mis-rank candidates, and graph propagation can leak stock-specific noise
across neighbors. The local implementation should be a transparent score
formation and crosstalk audit, not a black-box graph forecaster.

Implementable fields:

- `relation_score_head_version`
- `own_stock_score_component`
- `neighbor_relation_score_component`
- `relation_gate_weight_bucket`
- `relation_crosstalk_risk_bucket`
- `temporal_scale_component_bucket`
- `relation_graph_staleness_bucket`
- `relation_score_residual_bucket`
- `rank_ic_alignment_bucket`

Controls:

- report own-stock, neighbor, and residual score components separately before
  any relation field affects paper selection;
- require relation edges to have as-of timestamps and decay/staleness metadata;
- compare relation-score candidates against accepted relation helpers, not only
  against cash;
- use crosstalk diagnostics to reject static sector labels or broad beta
  relabels that merely propagate noisy momentum.

Sources:

- <https://arxiv.org/abs/2606.08930>
- <https://arxiv.org/abs/2604.20204>

### Dynamic Hypergraph And High-Order Relations

Recent 2026 dynamic-hypergraph stock-prediction research argues that static
graphs miss high-order and asynchronous market dependencies. Ginger's local
translation is narrow: do not add a black-box graph forecaster; persist richer
edge construction metadata so relation alphas can be compared against accepted
relation sleeves.

Implementable fields:

- `relation_hypergraph_version`
- `high_order_relation_cluster_id`
- `hyperedge_member_count_bucket`
- `hyperedge_asof_timestamp`
- `hyperedge_decay_weight_bucket`
- `asynchronous_relation_lag_bucket`
- `relation_cluster_displacement_value_bucket`

Controls:

- every edge or hyperedge must have an as-of timestamp and no future membership
  leakage;
- direct alpha use must beat accepted relation comparators after costs;
- use high-order clusters first for attribution, concentration, and stress
  diagnostics.

Source: <https://www.sciencedirect.com/science/article/pii/S156849462600400X>

### Causal Information-Channel Alignment

Recent causal-momentum work frames cross-sectional prediction as alignment
between information channels, using ideas such as Granger causality and
transfer entropy. Ginger should treat this as an edge-quality audit, not as a
license to mine correlations.

Implementable fields:

- `information_channel_id`
- `channel_alignment_method`
- `causal_edge_asof_timestamp`
- `causal_edge_strength_bucket`
- `channel_lead_lag_bucket`
- `transfer_entropy_bucket`
- `causal_relation_displacement_value_bucket`

Controls:

- compare causal edges against rolling-correlation peer shock before promotion;
- require stable lead/lag direction across windows;
- reject any channel whose economic story is only "correlation was high."

Source: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6397278>

### Logic-Constrained Alpha Synthesis

New neural-symbolic alpha-synthesis research emphasizes conditioning formulas
on market categories and adding logic constraints for robustness under regime
shifts. Ginger's compatible use is a candidate-generator audit surface: any
formula must be frozen before Gate 1, translated into named fields, and judged
after costs.

Implementable fields:

- `symbolic_alpha_formula_id`
- `formula_generation_prompt_hash`
- `formula_logic_constraint_set`
- `formula_market_category_bucket`
- `formula_component_source_ids`
- `formula_turnover_cost_bucket`
- `formula_after_cost_replacement_value_bucket`

Controls:

- no post-hoc formula edits after seeing frozen-window outcomes;
- require a simple human-readable formula and source fields;
- compare against accepted default-off adapters, not only against cash.

Source: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6819380>

### Disclosure Timing And Complexity As Event Context

Research on AI-audited regulatory filings argues that price discovery can be
slowed by the combination of dense language and irregular disclosure timing.
For Ginger, this maps to SEC event context and risk attribution: complexity and
timing surprise are candidate fields only when they are filing-time bounded and
measured against accepted SEC/event comparators.

Implementable fields:

- `filing_complexity_bucket`
- `filing_timing_surprise_bucket`
- `filing_cadence_irregularity_bucket`
- `filing_change_density_bucket`
- `disclosure_absorption_delay_bucket`
- `insider_timing_context_bucket`
- `sec_event_complexity_relation_bucket`

Controls:

- compute complexity and cadence using only filings available by the signal
  timestamp;
- separate routine business updates from structural deterioration or guidance
  changes;
- use the fields first for event-risk explanation and default-off attribution;
- require replacement value versus accepted SEC and non-text comparators before
  entry, ranking, or sizing use.

Source: <https://arxiv.org/abs/2602.17895>

### LLM Herding And Crowded AI Signals

LLM market experiments suggest AI traders may avoid some irrational cascades
while still participating in rational herding. For Ginger, this is a risk
surface: popular AI-readable narratives may crowd into the same liquid leaders,
so text/agent signals need crowding and displacement diagnostics.

Implementable fields:

- `ai_readable_narrative_density_bucket`
- `llm_herding_risk_bucket`
- `model_consensus_crowding_bucket`
- `same_source_signal_crowding_count`
- `crowded_signal_displacement_value_bucket`
- `narrative_unwind_risk_bucket`

Source: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6805805>
