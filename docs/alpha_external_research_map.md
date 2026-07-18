# Alpha External Research Map

Last refreshed: 2026-07-18.

External research notes moved out of `docs/alpha-optimization-playbook.md`.
Use this file when converting research literature into replayable fields or bounded LLM infrastructure ideas.

This is an idea map, not an accepted-strategy source. The current operating
rules, readout, research queue, and anti-repeat rules remain in
`docs/alpha-optimization-playbook.md`; accepted/rejected experiment facts live
in raw experiment records and generated `docs/lessons/*.md`.

## External Research Mapped To Ginger

These are not authority to add models. They are design patterns that must be
converted into auditable fields and tested through Gate 1-4.

### Trading-Code LLMs Need Semantic Backtest Diffing

QuantCode-Bench is a direct warning for agent-generated trading code. The
benchmark checks whether generated Backtrader strategies compile, run, place
trades, and semantically match the requested rule; its main failure mode is not
syntax, but wrong operationalization of trading logic, API use, and task
semantics. Ginger should treat any LLM-authored runner or helper as untrusted
until its observable trade rows match a frozen behavioral spec.

Implementable fields:

- `strategy_spec_hash`
- `llm_generated_code_flag`
- `semantic_alignment_test_id`
- `expected_trade_row_fixture_hash`
- `actual_trade_row_fixture_hash`
- `entry_exit_event_diff_count`
- `api_semantics_mismatch_bucket`
- `llm_code_operationalization_passed`

Controls:

- require a tiny deterministic fixture proving crosses, lookbacks, entry
  timing, exits, sizing, and cooldowns match the written spec before any
  backtest metric is read;
- compare event rows, not only final PnL or test pass/fail;
- fail closed when the code compiles but changes the decision clock,
  repeated-entry semantics, or fill assumptions;
- keep LLM-generated research scripts out of `accepted` evidence until the
  same spec-diff harness passes.

Source: <https://arxiv.org/abs/2604.15151>

### Intraday Risk Shape Is A Screening Input, Not A Price Signal

Metric Dependence Screening preserves intraday risk curves instead of reducing
high-frequency information to scalar daily returns. The useful translation for
Ginger is not another intraday momentum rule; it is a candidate-pool and
activation-screening contract that records the shape of intraday risk before
allocation. This is especially relevant to daily/intraday sidecars and any
future capacity screen for default-off helpers.

Implementable fields:

- `intraday_risk_curve_hash`
- `intraday_curve_sampling_interval`
- `point_curve_metric_version`
- `frechet_dependence_score`
- `risk_adjusted_target_slice_hash`
- `intraday_shape_screen_rank`
- `scalar_return_screen_delta`
- `intraday_shape_replacement_value`

Controls:

- freeze the intraday sampling grid and risk target before selection;
- compare curve-aware screening against return-only, volatility-only, and
  current accepted-helper rankings on identical dates;
- record whether the field changes candidate selection, not just risk reports;
- require out-of-time replacement value before using intraday shape for entry,
  sizing, or capacity.

Source: <https://arxiv.org/abs/2605.02326>

### Market-Simulation Agents Need Variance Budgets

Persona-Trained Monte Carlo theory is useful as a governance pattern for
LLM/agent market simulations: simulated market outcomes need variance
decomposition, stability bounds, and an identifiability test before they can
inform policy. The local rule is that synthetic news-reaction or limit-order-
book simulations are stress tools unless they expose persona-draw variance,
within-run variance, and a fixed response family.

Implementable fields:

- `persona_distribution_hash`
- `persona_draw_variance`
- `within_run_variance`
- `variance_optimal_replication_plan`
- `policy_error_stability_bound`
- `response_family_fixed_flag`
- `heterogeneous_news_reaction_test`
- `simulation_identifiability_passed`

Controls:

- separate simulation stress evidence from historical/forward alpha evidence;
- predeclare the response nonlinearity before estimating heterogeneous
  reaction;
- require multiple persona draws and inner replications with stored seeds;
- do not use simulated PnL to override Gate 1-4 or forward replacement-value
  requirements.

Source: <https://arxiv.org/abs/2607.04627>

### LLM Verifiers Need Risk-Calibrated Alarms

Online LLM monitoring work supports a simple operational boundary: turn a
verifier score into an alarm using a threshold calibrated by risk control.
For Ginger, this belongs around LLM evidence construction, not direct trading
authority. A verifier can block stale, unsupported, or numerically inconsistent
LLM labels before they enter an observer or default-off helper.

Implementable fields:

- `llm_verifier_model_version`
- `verifier_score`
- `risk_calibrated_alarm_threshold`
- `llm_evidence_alarm_flag`
- `monitor_calibration_panel_hash`
- `false_alarm_budget`
- `miss_risk_budget`
- `llm_monitor_action`

Controls:

- calibrate thresholds on a frozen panel before using them in production;
- log both blocked and passed LLM rows with the same source evidence;
- treat monitor alarms as fail-closed data-quality gates, not alpha signals;
- retune thresholds only with a new calibration panel, not after observing
  trading outcomes.

Source: <https://arxiv.org/abs/2607.02510>

### Order-Book Reconstruction Is Measurement Infrastructure

MeatPy is a recent open-source, peer-reviewed framework for reconstructing and
analyzing market-by-order limit-order-book data. The Ginger takeaway is
infrastructure: if future intraday/microstructure work moves beyond OHLCV,
the first artifact should be a deterministic order-book reconstruction and
quality ledger, not a direct LOB alpha rule.

Implementable fields:

- `lob_reconstruction_tool_version`
- `mbo_source_schema_hash`
- `order_book_replay_quality_flag`
- `top_of_book_reconstruction_error`
- `message_sequence_gap_count`
- `quote_trade_alignment_hash`
- `lob_feature_publication_lag`
- `lob_measurement_ready_flag`

Controls:

- prove deterministic reconstruction on a small message fixture before
  computing features;
- store sequence gaps, quote/trade alignment, and top-of-book errors;
- keep LOB features read-only until latency, costs, and publication rights are
  explicit;
- benchmark any LOB-derived field against simpler spread/volume/volatility
  proxies before adding strategy logic.

Source: <https://joss.theoj.org/papers/10.21105/joss.10480>

### Learned Forecasts Need Base-Rate-Honest Benchmarks

A July 2026 TimesFM/LoRA equity-forecasting benchmark is directly useful as a
negative-control pattern. Raw directional accuracy can mostly measure the
market's unconditional up-rate; the paper's useful contribution is a frozen
walk-forward protocol with always-up, random-walk, persistence, AR(1), and
zero-shot model baselines plus paired significance tests and FDR control. For
Ginger, any learned ranking, LLM forecast, or foundation time-series model must
report incremental replacement value after this base-rate audit, not standalone
hit rate.

Implementable fields:

- `base_rate_benchmark_protocol_id`
- `always_up_accuracy_baseline`
- `excess_directional_accuracy_vs_base_rate`
- `walk_forward_fold_hash`
- `held_out_ticker_split_hash`
- `paired_significance_test_family`
- `forecast_fdr_adjusted_pvalue`
- `base_rate_honest_replacement_value`

Controls:

- compare every learned directional model against always-up, random-walk,
  persistence, AR(1), zero-shot model, cash, SPY/QQQ, and accepted-helper
  baselines on the same rows;
- report excess accuracy and after-cost replacement value, not raw directional
  accuracy;
- keep sector-specialized adapters out of production unless they beat the
  pooled adapter and the base-rate benchmark on held-out tickers;
- fail closed when the split, fold seed, or baseline panel is not reproducible.

Source: <https://arxiv.org/abs/2607.12248>

### Cost-Aware RL Allocation Belongs In Activation Envelopes

A July 2026 SciPhyRL portfolio paper shows the right infrastructure boundary:
the learned policy optimizes over an extended state that explicitly includes
cumulative costs, uses a discrete target-holding control for short horizons,
and evaluates against a microstructure-grounded quadratic impact model. The
local lesson is not to import RL as alpha. It is to require any learned
allocator or notional router to expose the same cost, turnover, volatility,
and target-holding state before it can challenge the accepted source allocator.

Implementable fields:

- `rl_allocator_protocol_id`
- `target_holding_control_bucket`
- `cumulative_cost_state_hash`
- `quadratic_impact_parameter_hash`
- `turnover_control_passed`
- `volatility_control_passed`
- `offline_signal_quality_source`
- `rl_allocator_vs_myopic_delta`

Controls:

- use RL only after the signal panel is frozen and leakage-checked;
- compare against static, myopic, equal-weight, cash, and current accepted
  source-priority allocation under identical impact assumptions;
- reject policies whose improvement comes from unmodeled leverage, turnover,
  or missing impact state;
- keep the learned allocator default-off until Gate 1-4 and Gate 5 evidence
  exists on a complete selection panel.

Source: <https://arxiv.org/abs/2607.15195>

### Filing Text Aggregation Level Is A Decision Variable

A July 2026 10-K sentiment paper finds that full filings work better at sector
or portfolio aggregation, while Item 1A risk factors work better at the
individual-firm level. The practical Ginger rule is to log the aggregation
level as part of the decision variable. A filing-text retry is not "new" merely
because it changes a sentiment model; it needs a predeclared entity level,
section scope, target label, evidence spans, and comparator.

Implementable fields:

- `filing_text_aggregation_level`
- `filing_section_scope`
- `filing_sentiment_target_label`
- `section_vs_full_text_delta`
- `filing_text_training_signal_count`
- `dictionary_baseline_correlation`
- `filing_text_replacement_value_delta`

Controls:

- predeclare whether the text field is issuer-level, portfolio-level, or
  sector-level before scoring outcomes;
- compare full-filing, Item 1A, and Loughran-McDonald-style baselines on the
  same accession/date panel;
- require accession timestamps, parser version, source spans, and deterministic
  numeric checks;
- do not retune SEC text classifiers on frozen windows without a new taxonomy,
  source, or settled forward evidence.

Source: <https://arxiv.org/abs/2607.14174>

### One-Switch Leakage Tests Before Learned Alpha

A May 2026 leakage benchmark gives Ginger a concrete preflight shape: hold the
data panel, split, model, horizon, portfolio rule, and costs fixed, then toggle
one decision-time convention around a clean `t+1` open reference. The important
finding is selective inflation: centered temporal features and same-day-open
execution using post-open daily-bar information create stable metric inflation,
while some other suspected leakages are weak. Ginger should use this as a
zero-ID diagnostic before any learned ranking, LLM forecast, or graph feature
claims alpha.

Implementable fields:

- `one_switch_leakage_protocol_id`
- `clean_tplus1_open_reference_hash`
- `leakage_toggle_name`
- `leakage_metric_inflation_ev`
- `leakage_metric_inflation_pnl`
- `same_day_bar_information_flag`
- `centered_temporal_feature_flag`
- `leakage_preflight_passed`

Controls:

- run the one-switch diagnostic before reserving an alpha ID when a learned
  field touches same-day bars, centered windows, graph structure, or model
  normalization;
- keep universe, split, horizon, portfolio rule, and costs identical across the
  clean and toggled runs;
- reject any signal whose apparent edge disappears under the clean `t+1` open
  reference;
- store the diagnostic as preflight evidence, not as an accepted strategy.

Source: <https://arxiv.org/abs/2605.23959>

### Impact Models Can Reorder The Algorithm Leaderboard

Recent trading-environment work shows that replacing fixed bps costs with
Almgren-Chriss / square-root impact can materially change absolute results,
turnover, and even which RL algorithm looks best. This maps to Ginger's
activation-envelope discipline: a sleeve that is positive under fixed paper
costs still needs a realistic impact and turnover envelope before notional or
live promotion. Cost modeling is a policy boundary, not a reporting footnote.

Implementable fields:

- `impact_model_family`
- `impact_model_parameter_hash`
- `square_root_impact_bucket`
- `permanent_impact_decay_bucket`
- `turnover_penalty_protocol_id`
- `cost_model_rank_stability_delta`
- `pathological_turnover_flag`
- `impact_adjusted_replacement_value`

Controls:

- compare fixed-bps, spread-aware, and square-root-impact scenarios on the same
  selected rows before increasing paper notional or live sizing;
- report whether a candidate's rank survives the cost-model change;
- fail closed when turnover or impact estimates are missing for a ticker/date;
- use Optuna or other tuning only inside a predeclared train window, never on
  the fixed Gate-4 evaluation rows.

Source: <https://arxiv.org/abs/2603.29086>

### LLM News Models Need Relevance Pooling And Coverage Accounting

A March 2026 multi-stock news-fusion paper uses stock-name embeddings and
attention pooling to filter news relevance before combining text embeddings
with price history. The useful Ginger lesson is not to train a black-box price
model; it is to make relevance selection auditable. Raw article sentiment and
headline matching should be replaced by source spans, entity relevance scores,
and coverage denominators before an LLM/news row can enter a candidate helper.

Implementable fields:

- `news_relevance_model_version`
- `issuer_name_embedding_hash`
- `article_entity_attention_score`
- `article_position_attention_score`
- `news_relevance_pooling_method`
- `news_source_coverage_denominator`
- `relevance_filtered_event_count`
- `news_fusion_replacement_value_delta`

Controls:

- keep relevance pooling separate from direction/sentiment scoring;
- persist article ids, source timestamps, entity spans, and attention/relevance
  scores before outcome evaluation;
- benchmark relevance-filtered rows against simple ticker mention, accepted
  structured-event, and current entity/theme observers;
- require after-cost replacement value, not prediction-loss improvement alone.

Source: <https://arxiv.org/abs/2603.19286>

### Constrained Portfolio Optimizers Are Benchmarks, Not Shortcut Alpha

Two 2026 constrained-portfolio papers are useful as infrastructure guidance.
Global-equity SAC with transaction costs, turnover penalties, diversification
constraints, and walk-forward folds found only partial cross-market success;
quantum annealing work similarly frames constrained allocation as a benchmarked
optimization problem with business and computational metrics. Ginger should
use these ideas to benchmark allocation tooling, not to reopen parked overlay
families without a new owner contract and leakage-free complete panel.

Implementable fields:

- `constrained_optimizer_protocol_id`
- `allocation_constraint_set_hash`
- `walk_forward_fold_id`
- `hac_robust_excess_return_pvalue`
- `turnover_penalty_weight`
- `diversification_constraint_passed`
- `class_exposure_bound_passed`
- `optimizer_compute_budget_bucket`
- `optimizer_vs_current_allocator_delta`

Controls:

- evaluate optimizers against equal weight, cash, and the current accepted
  source allocator under identical cost and turnover assumptions;
- report fold-level robustness and HAC-style inference before claiming excess
  return;
- separate business performance from solver novelty or computational
  performance;
- keep quantum or RL optimizers in research tooling until they beat the current
  allocator on a complete pre-frozen panel.

Sources:

- <https://arxiv.org/abs/2605.17307>
- <https://arxiv.org/abs/2607.03218>

### Correlation Structure Needs Denoising Before Portfolio Claims

Recent network-correlation work separates empirical correlation matrices into
structured eigenmodes above Marchenko-Pastur bounds and noise-dominated modes,
then shows more stable core-periphery networks and peripheral-asset portfolios.
This maps directly to Ginger's rejected portfolio-covariance lane: a portfolio
overlay is not valid because individual shards are positive. It needs a
predeclared denoising protocol, full candidate scope, and out-of-time replay.

Implementable fields:

- `correlation_denoising_protocol_id`
- `mp_structured_eigenmode_count`
- `random_matrix_noise_share`
- `core_periphery_membership_bucket`
- `network_peripheral_candidate_flag`
- `subsample_stability_score`
- `denoised_covariance_replacement_value`
- `portfolio_scope_completeness_flag`

Controls:

- estimate correlation structure only from training data available before the
  holdout window;
- compare denoised covariance weights against equal weight, the current
  accepted allocator, and cash/SPY/QQQ replacement paths;
- report Monte Carlo or rolling-subsample stability before claiming a joint
  overlay;
- reject any portfolio synthesis that omits losing candidate families or mixes
  baseline protocols.

Source: <https://arxiv.org/abs/2607.10297>

### Robust Optimizers Need Adaptive Ambiguity And Naive-Weight Diagnostics

Two July 2026 portfolio papers sharpen a practical rule. Learned predictive
ambiguity sets argue for state-dependent uncertainty radii instead of point
forecasts or fixed Wasserstein radii. A naive-diversification diagnostic argues
that equal weight is rational when forecast-error covariance has a uniform
eigenstructure, and optimized weights regain value only when that condition
breaks. Ginger's translation: learned allocation, source routing, and sleeve
capacity should expose uncertainty radius and a naive-weight diagnostic before
they beat the one-slot accepted allocator.

Implementable fields:

- `predictive_ambiguity_set_version`
- `state_dependent_wasserstein_radius`
- `scenario_distribution_hash`
- `ambiguity_radius_calibration_error`
- `forecast_error_uniform_eigenstructure_score`
- `naive_weight_diagnostic_bucket`
- `optimizer_vs_equal_weight_replacement_value`
- `robust_optimizer_tail_loss_delta`

Controls:

- compare learned or optimized weights against equal weight, current source
  priority, and accepted-helper comparators on the same rows;
- train uncertainty radii only on prior data and record calibration loss;
- require tail-loss and drawdown improvement, not just higher average PnL;
- default to equal weight or fixed accepted source priority when the diagnostic
  says forecast-error structure is too uniform or too unstable.

Sources:

- <https://arxiv.org/abs/2607.09820>
- <https://arxiv.org/abs/2607.11054>

### Tail And Benchmark-Relative Duration Are Activation Metrics

New tail-learning and drawdown-duration work is most useful as execution and
activation governance. SS-GEN learns rare-event laws by separating radial tail
size from angular dependence, while benchmark-relative drawdown-duration
penalizes time spent underperforming a benchmark. For Ginger, these are not
new entry signals. They are better stress and activation-envelope metrics for
accepted default-off helpers before notional or live capital increases.

Implementable fields:

- `tail_stress_protocol_id`
- `tail_radial_component_bucket`
- `tail_angular_dependence_hash`
- `rare_event_probability_estimate`
- `benchmark_relative_drawdown_duration`
- `occupation_time_under_benchmark`
- `stress_scenario_replacement_value`
- `activation_tail_guard_passed`

Controls:

- evaluate candidate activation envelopes under simulated multivariate tail
  scenarios and historical tail windows;
- report drawdown duration versus SPY/QQQ or the displaced helper, not only
  max drawdown;
- use tail/duration metrics as kill-switch and capacity evidence, not as a
  reason to retune entries on frozen rows;
- require the same stress protocol for before/after activation tests.

Sources:

- <https://arxiv.org/abs/2607.10700>
- <https://arxiv.org/abs/2607.11335>

### Liquidity Impact Is Matrix-Valued Capacity State

The latest multidimensional Kyle-model work treats liquidity depth and price
impact as matrix-valued, stochastic, cross-asset state. Combined with recent
order-flow impact lessons already in this map, the local rule is stricter:
flow and liquidity rows should estimate capacity, cross-asset impact, and
execution risk before they influence ranking or notional.

Implementable fields:

- `matrix_liquidity_depth_version`
- `cross_asset_impact_bucket`
- `stochastic_liquidity_state_bucket`
- `private_information_liquidation_speed_proxy`
- `impact_common_eigenbasis_bucket`
- `liquidity_capacity_notional_cap`
- `cross_impact_replacement_value_delta`

Controls:

- estimate liquidity and cross-impact from pre-decision data only;
- separate directional order-flow edge from capacity and cross-impact state;
- run notional/capacity changes through cost scenarios and accepted-helper
  displacement checks;
- fail closed when liquidity state is missing, stale, or vendor-specific.

Source: <https://arxiv.org/abs/2607.10934>

### Supply-Chain Macro Shocks Need Network Exposure Provenance

A July 2026 maritime chokepoint model shows that trade disruptions can hit
countries and sectors that do not directly transit the blocked passage because
intermediate inputs are complementary and re-matching is asymmetric. For
Ginger, macro supply shocks should not be traded as broad headlines. They need
issuer-level customer/supplier/route exposure provenance and matched
replacement value.

Implementable fields:

- `supply_chain_network_version`
- `maritime_chokepoint_exposure_bucket`
- `intermediate_input_complementarity_score`
- `buyer_resourcing_flexibility_bucket`
- `seller_market_concentration_bucket`
- `joint_closure_interaction_bucket`
- `issuer_supply_route_evidence_hash`
- `supply_shock_replacement_value_delta`

Controls:

- store the relation path from shock source to issuer before scoring outcomes;
- distinguish direct route exposure from second-order supplier/customer
  exposure;
- compare against commodity, sector ETF, and accepted relation helpers after
  costs;
- avoid broad macro proxy retunes unless a new PIT network-exposure source is
  present.

Source: <https://arxiv.org/abs/2607.09951>

### Useful Alphas Need Live-Cap And Cost Reality

Chen and Welch's July 2026 "What Useful Alphas?" is a direct warning against
mining published anomaly catalogs or small-cap effects as if they were deployable
Ginger edges. Their headline result is that long-short anomaly returns decay
sharply after 2005 and after excluding microcaps; modest luck and transaction
cost allowances can erase the remaining non-micro edge. The local translation:
every broad factor, universe expansion, and academic-anomaly-inspired source
must prove non-micro, after-cost replacement value against the displaced helper,
not just cross-sectional prediction quality.

Implementable fields:

- `published_alpha_family_id`
- `post_2005_non_micro_placebo_delta`
- `microcap_dependency_bucket`
- `capacity_feasible_universe_share`
- `transaction_cost_edge_buffer_bps`
- `luck_adjusted_t_stat_bucket`
- `accepted_helper_incremental_value`

Controls:

- report results separately for non-micro / liquid names before any broad
  source promotion;
- compare against simple recency, momentum, size/style, and accepted-helper
  baselines on the same PIT dates;
- require a positive after-cost buffer, not just nominal anomaly spread;
- treat academic-anomaly imports as hypothesis generators until Gate 1-4 clears
  with Ginger's capacity and displacement constraints.

Source: <https://arxiv.org/abs/2607.06502>

### LLM Research Is A Pipeline Checklist, Not A Trading Delegate

The 2025 survey "The New Quant" is useful because it organizes LLM work around
tasks that Ginger can audit: sentiment/event extraction, numeric reasoning,
retrieval, multimodal fusion, agentic research tooling, and portfolio
construction under exposure, turnover, capacity, latency, and cost controls.
The local conclusion is not "use an LLM to trade." It is that every LLM output
must become a timestamped, schema-bound evidence row with source coverage,
tool-verified numerics, and after-cost replacement value before it affects a
deterministic helper.

Implementable fields:

- `llm_task_taxonomy_bucket`
- `llm_retrieval_source_hash`
- `llm_tool_verified_numeric_flag`
- `llm_source_coverage_fraction`
- `llm_latency_bucket`
- `llm_capacity_constraint_bucket`
- `llm_costed_replacement_value`
- `llm_governance_failure_bucket`

Controls:

- separate event extraction, numeric extraction, forecast view, and execution
  suggestion into different schemas and ledgers;
- require deterministic recomputation for arithmetic, joins, and period
  matching;
- report coverage, latency, cost, turnover, and capacity in the same artifact
  as any LLM-derived signal;
- keep LLMs in evidence construction unless a shared helper passes Gate 1-4.

Source: <https://arxiv.org/abs/2510.05533>

### LLM Forecasts Need PIT Recall Diagnostics

Three recent LLM-finance papers sharpen one deployable rule for Ginger:
off-the-shelf LLM forecasts can look predictive because the model has memorized
firm/date outcomes, while time-aware pretraining and filing-grounded prompts
reduce but do not remove the need for validation. DatedGPT shows the clean
architecture pattern: annual model cutoffs and temporally filtered
instruction-tuning. The Lookahead Propensity test shows the cheap diagnostic:
ask a date-only recall question, then measure whether forecast accuracy loads
on the model's own probability of "knowing" the outcome. The stock-investing
human-factor study adds a production boundary: regulatory filing grounding and
human/structured supervision help, but autonomous recommendations still fail
through misconceptions, carryover errors, stale facts, and hallucinations.

Implementable fields:

- `llm_model_cutoff_date`
- `llm_prompt_information_cutoff`
- `llm_date_only_recall_probability`
- `llm_lookahead_propensity_bucket`
- `llm_signal_x_recall_interaction_tstat`
- `llm_filing_grounded_flag`
- `llm_human_supervision_mode`
- `llm_reasoning_failure_bucket`
- `llm_pit_forecast_replacement_value`

Controls:

- record model id, model knowledge cutoff, prompt timestamp, source timestamp,
  and evidence hashes for every LLM-derived forecast row;
- run a date-only recall probe before scoring any LLM forecast over historical
  firm/date outcomes;
- treat high recall probability as contamination risk unless the forecast still
  adds after-cost replacement value after recall controls;
- prefer official-filing grounded prompts with deterministic numeric checks and
  bounded human/schema supervision;
- never let an LLM forecast affect entry, ranking, sizing, exits, or orders
  until a shared helper passes Gate 1-4 with PIT recall diagnostics attached.

Sources:

- <https://arxiv.org/abs/2603.11838>
- <https://arxiv.org/abs/2512.23847>
- <https://arxiv.org/abs/2603.19944>

### Agentic Research Needs Tool Traces And Reproducible Panels

QRAFTI is useful as research-infrastructure guidance rather than a trading
model: multi-agent quant workflows should expose data access, factor
construction, code execution, report generation, and reflection as traceable
tool calls. Ginger already has experiment IDs, tickets, artifacts, and
generated dashboards; the missing benchmarkable surface is a compact trace
that says which data panel, factor transform, test, and comparator each agent
actually used.

Implementable fields:

- `research_agent_trace_id`
- `panel_dataset_version`
- `factor_construction_tool_call_hash`
- `agent_reflection_step_count`
- `research_report_artifact_hash`
- `comparator_panel_protocol_id`
- `tool_call_replay_passed`
- `agent_research_failure_bucket`

Controls:

- log every data, factor, and code tool call used to create a research claim;
- require the same panel version, universe, costs, and comparator for replay;
- treat narrative analysis as provenance, not evidence, until artifacts rerun;
- prefer small auditable helper functions over opaque generated notebooks.

Source: <https://arxiv.org/abs/2604.18500>

### Hedge-Fund LLM Forecasting Reviews Are Robustness Checklists

The April 2026 hedge-fund-oriented LLM forecasting review reinforces the same
local boundary from a practitioner angle: LLMs can help extract sentiment,
events, report context, transcripts, and agent research traces, but the common
failure modes are horizon leakage, fragile sentiment labels, illiquidity
premia, weak predictability, and evaluation metrics that do not survive costs.
For Ginger, this means an LLM score is not useful until its source set,
horizon, liquidity, cost, and displaced-candidate comparator are logged next to
the prediction.

Implementable fields:

- `llm_forecast_review_protocol_id`
- `llm_forecast_source_mix_bucket`
- `llm_prediction_horizon_lock`
- `llm_liquidity_premium_risk_bucket`
- `llm_temporal_leakage_audit_passed`
- `llm_eval_metric_family`
- `llm_after_cost_comparator_delta`
- `llm_robustness_failure_reason`

Controls:

- lock the prediction horizon before any LLM forecast row is scored;
- report liquidity, spread, and tradability alongside model accuracy;
- benchmark against simple momentum, sector, and accepted-helper comparators;
- treat agentic LLM traces as research provenance unless a deterministic
  helper converts them into PIT rows and passes Gate 1-4.

Source: <https://arxiv.org/abs/2605.05211>

### Complex ML Return Predictors Need Recency Placebos

The 2025 debate around very complex return predictors is a useful warning:
apparent ML complexity can collapse into recent-return similarity or
volatility-timed momentum. Ginger should add a placebo layer before trusting
high-dimensional models, graph embeddings, or LLM-produced score vectors: prove
that the model beats simple recency, momentum, and volatility-scaled momentum
baselines under the same PIT data, costs, and displacement comparator.

Implementable fields:

- `model_complexity_bucket`
- `recency_similarity_score`
- `momentum_placebo_delta`
- `vol_timed_momentum_placebo_delta`
- `feature_similarity_lookback_bucket`
- `complex_model_incremental_replacement_value`
- `simple_baseline_comparator_set`
- `overcomplexity_failure_reason`

Controls:

- compare any high-dimensional predictor against recency-weighted returns,
  cross-sectional momentum, and volatility-scaled momentum;
- run the placebo on the exact same decision dates, universe, costs, and
  candidate displacement path;
- require positive incremental replacement value, not only better prediction
  loss;
- treat "more parameters" as model-risk evidence until the placebo clears.

Source: <https://www.ft.com/content/89d88cbf-a92c-43d2-b8af-88ae26529be0>

### Prediction Uncertainty Belongs In Ranking And Admission

Recent ML asset-pricing work argues that point forecasts are the wrong object
to sort on when asset-specific estimation uncertainty differs across names.
Uncertainty-adjusted sorting and forecast-confidence intervals improve mainly
by reducing volatility and shrinking fragile model picks, not by discovering a
magic new signal. This maps directly to Ginger's repeated sparse-source and
single-window failures: candidate-pool and source-router scores should expose
confidence bounds, sample support, and lower-bound replacement value before
they can win scarce slots or receive larger paper notional.

Implementable fields:

- `forecast_point_score`
- `forecast_lower_bound_score`
- `forecast_uncertainty_width`
- `asset_specific_uncertainty_bucket`
- `model_sample_support_count`
- `uncertainty_adjusted_rank`
- `lower_bound_replacement_value_delta`
- `uncertainty_shrinkage_reason`

Controls:

- rank learned or meta-labeled candidates by a predeclared lower-bound score,
  not only by point expected return;
- report whether improvements come from lower return volatility, fewer tail
  losses, or higher gross PnL;
- compare uncertainty-adjusted ranking against the existing deterministic rank,
  simple momentum/recency baselines, and accepted helper comparators on the
  same PIT rows;
- keep low-sample or high-uncertainty names in default-off observation until
  closed replacement rows narrow the interval.

Sources:

- <https://arxiv.org/abs/2601.00593>
- <https://arxiv.org/abs/2503.00549>

### Financial Time-Series Foundation Models Need Contamination Audits

Recent financial time-series foundation-model work is useful mainly as a
benchmarking warning. FinCast reports zero-shot strength across financial
domains and resolutions, but companion TSFM evaluation work argues that large
pretraining corpora make train/test and temporal-overlap leakage hard to rule
out. FinTSB adds the practical benchmark shape Ginger should copy: movement
pattern diversity, standardized protocol, and market-structure constraints
such as fees. The local translation is not to import a foundation model into
selection; it is to add contamination, movement-pattern, and fee-scenario
metadata around any learned forecast or representation.

Implementable fields:

- `tsfm_model_id`
- `tsfm_pretraining_corpus_hash`
- `benchmark_overlap_audit_version`
- `temporal_overlap_group_id`
- `movement_pattern_bucket`
- `resolution_domain_bucket`
- `market_structure_constraint_version`
- `transaction_fee_scenario_id`
- `zero_shot_simple_baseline_delta`
- `tsfm_costed_replacement_value_delta`

Controls:

- require an overlap/leakage audit before comparing any pretrained model to
  local PIT rows;
- benchmark against simple momentum, volatility-scaled momentum, and accepted
  helper comparators on the exact same decision dates;
- report performance by movement-pattern bucket and market regime, not only
  aggregate prediction loss;
- include fees, tradability, and displacement replacement value before treating
  a forecast as alpha evidence.

Sources:

- <https://arxiv.org/abs/2508.19609>
- <https://arxiv.org/abs/2510.13654>
- <https://arxiv.org/abs/2502.18834>

### Event Graph RAG Belongs In The Relation Evidence Store

FinKario is useful because it treats evolving fundamentals, events, entities,
and relation triples as a graph-retrieval problem rather than raw sentiment.
That maps directly to Ginger's repeated relation-alpha boundary: relation
labels only matter when the actor, object, relation type, timestamp, source
span, and replacement outcome are stored as replayable rows. The graph should
feed candidate evidence and source memory; it should not become a discretionary
LLM trading layer.

Implementable fields:

- `event_graph_version`
- `event_graph_entity_id`
- `event_graph_relation_type`
- `event_graph_relation_confidence_bucket`
- `event_graph_source_span_hash`
- `event_graph_update_timestamp`
- `event_graph_retrieval_stage`
- `relation_triple_replacement_value_bucket`
- `graph_rag_missing_relation_reason`

Controls:

- store event and relation triples with source span, extraction prompt/schema,
  and accepted timestamp;
- separate issuer-self, peer, customer, supplier, counterparty, and theme
  propagation relations before scoring;
- compare graph-retrieved rows against accepted relation/allocator helpers
  after costs;
- update relation memory only from information available before the candidate
  date, and score outcomes only after the horizon matures.

Source: <https://arxiv.org/abs/2508.00961>

### Learned Portfolio Models Need Risk-Cost Significance Packages

Recent deep-learning and reinforcement-learning portfolio papers point to a
useful evaluation package: temporal state, position sizing, short/long
constraints, CVaR or drawdown risk, transaction-cost scenarios, statistical
significance, seed robustness, and breakeven-cost buffers. Ginger should copy
that package before trusting any learned allocator, source router, or sizing
overlay. A learned model that improves average return but fails cost, seed, or
tail checks is diagnostic only.

Implementable fields:

- `learned_allocator_model_id`
- `temporal_state_encoder_version`
- `position_sizing_action_space`
- `short_or_inverse_allowed_flag`
- `cvar_or_drawdown_constraint_id`
- `random_seed_robustness_bucket`
- `statistical_significance_bucket`
- `breakeven_transaction_cost_bps`
- `downside_tail_metric_delta`
- `learned_allocator_replacement_value_delta`

Controls:

- run learned allocators against linear/simple baselines, accepted helpers, and
  cash/SPY/QQQ displacement on the same rows;
- report seed sensitivity, tail risk, drawdown, turnover, and cost scenarios
  next to Sharpe or EV;
- keep learned output default-off until a deterministic shared helper or
  frozen model artifact passes Gate 1-4;
- reject models whose edge disappears under realistic fees or whose advantage
  is not statistically distinguishable from simple baselines.

Sources:

- <https://arxiv.org/abs/2503.04143>
- <https://arxiv.org/abs/2603.01820>

### Price-Driven LLM Agents Are Structured Signal Routers

QuantAgent's useful pattern is the decomposition into indicator, pattern,
trend, and risk specialists over short-horizon structured signals. For Ginger,
that supports a narrow LLM boundary: the model may summarize or classify
already-computed microstructure/trend evidence, but code must own entry,
ranking, sizing, exits, and risk. Any LLM agent output should be logged as a
traceable view over deterministic fields, then judged by replacement value.

Implementable fields:

- `price_agent_protocol_id`
- `indicator_view_hash`
- `pattern_view_hash`
- `trend_view_hash`
- `risk_view_hash`
- `short_horizon_signal_window`
- `agent_view_disagreement_bucket`
- `agent_risk_override_attempt_flag`
- `price_agent_replacement_value_delta`

Controls:

- compute indicators, pattern labels, and risk metrics deterministically before
  the LLM sees them;
- preserve the per-agent input/output, disagreement, and final view as
  replayable evidence rows;
- fail closed when the agent proposes sizing, exit, or risk changes outside the
  shared policy schema;
- compare any agent-assisted row against the same deterministic helper without
  the LLM view after costs.

Source: <https://arxiv.org/abs/2509.09995>

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

### Regime Volatility Forecasts Are Risk Gates, Not Alpha By Themselves

A June 2026 high-frequency equity study finds a familiar pattern: volatility
and regime forecasts are more reliable than unconditional return forecasts.
Naive predictive trading fails after realistic transaction costs, while
defensive implementations can improve only when low-volatility gating,
volatility scaling, walk-forward threshold calibration, and turnover controls
are fixed before evaluation. Ginger's translation: use regime-volatility
forecasts as an execution-envelope and capacity surface, not as a new entry
signal unless it beats accepted comparators after costs.

Implementable fields:

- `realized_vol_forecast_version`
- `vol_regime_probability_bucket`
- `low_volatility_gate_flag`
- `vol_scaled_notional_pct`
- `walk_forward_threshold_id`
- `turnover_control_reason`
- `defensive_allocation_delta_bucket`
- `vol_regime_after_cost_replacement_value`

Controls:

- estimate thresholds only with walk-forward / prior data;
- compare low-vol gates against cash, SPY/QQQ, and the exact displaced helper;
- report turnover saved and trades skipped as first-class evidence;
- treat broad return-prediction gains without costed implementation as
  diagnostic only.

Source: <https://arxiv.org/abs/2606.09478>

### Friction-Aware Regime Conditioning Requires Inaction Bands

FR-LUX is useful because it treats transaction costs and regimes as part of
the policy objective, not as an after-the-fact haircut. Its practical pattern is
directly compatible with Ginger's repeated allocator/capacity failures:
calibrate costs from liquidity proxies, condition on volatility-liquidity
states, constrain inventory-flow changes, and allow proportional costs to
create explicit no-trade / inaction bands. The local translation is not a new
reinforcement-learning allocator. It is a stricter activation-envelope surface
for default-off helpers before adding slots, scalars, or live capital.

Implementable fields:

- `friction_policy_version`
- `vol_liquidity_regime_bucket`
- `inventory_flow_change_budget`
- `inaction_band_reason`
- `cost_calibration_source_id`
- `turnover_bound_bucket`
- `regime_conditioned_capacity_delta`
- `cost_scenario_replacement_value`

Controls:

- evaluate capacity/scalar changes across cost scenarios, not only the base
  fill model;
- report no-trade decisions as intentional inaction, not missing coverage;
- compare candidate capacity against the current one-slot accepted allocator;
- require forward replacement rows before using regime labels to add slots.

Source: <https://arxiv.org/abs/2510.02986>

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

### Constrained LLM Alpha Search Needs Hard Financial Grammar

PandaAI's useful pattern is not the reported CSI 300 performance; it is the
system shape. LLM-guided alpha generation is bounded by a formal operator
grammar, forbidden-rule set, market-regime state, turnover/risk constraints,
and evidence feedback. Ginger's translation is a safer research loop: let LLMs
propose symbolic factor candidates only inside a predeclared grammar, reject
financially toxic factors before simulation, and store the constraint set with
the replay artifact.

Implementable fields:

- `symbolic_alpha_grammar_version`
- `llm_alpha_candidate_hash`
- `forbidden_operator_rule_set_id`
- `financial_toxicity_reject_reason`
- `latent_regime_state_id`
- `dynamic_constraint_penalty_bucket`
- `alpha_search_mcts_trace_hash`
- `constraint_feedback_update_id`

Controls:

- freeze grammar, forbidden operators, and cost/risk constraints before search;
- reject candidates with excessive turnover, leakage, dimensional mismatch, or
  unstable decay before Gate 1;
- compare any retained symbolic factor against recency, momentum, volatility,
  and accepted-helper comparators under the same PIT panel;
- record failed generated factors so later agents do not rediscover them.

Source: <https://arxiv.org/abs/2606.06823>

### Verifiable Forecast Actions For LLM Views

StockR1 is useful because it forces an LLM market view into a structured
forecast action before any time-series decoder or reward step can use it. The
local design lesson is not to deploy an LLM forecaster; it is to make every LLM
view schema-bound, numerically checkable, uncertainty-tagged, and comparable
to the subsequent realized trajectory. That fits Ginger's LLM boundary: the
LLM may produce a replayable evidence row, while deterministic code owns
orders, sizing, exits, and constraint handling.

Implementable fields:

- `llm_forecast_action_schema_version`
- `llm_forecast_action_direction_bucket`
- `llm_forecast_action_horizon`
- `llm_distributional_path_hash`
- `llm_forecast_uncertainty_bucket`
- `llm_action_realized_consistency_score`
- `llm_view_numeric_grounding_passed`
- `llm_forecast_replacement_value_bucket`

Controls:

- freeze the forecast-action schema before scoring;
- store model id, prompt, evidence set, action JSON, uncertainty, and timestamp;
- score consistency against realized 5/10/20-day paths before using the view;
- keep forecast actions default-off until a shared helper passes Gate 1-4.

Source: <https://arxiv.org/abs/2605.21975>

### Stratified LLM Strategy Alignment

Strat-LLM's May 2026 live-forward study is useful because it separates the LLM
scaffold from the market state. Its reported Free, Guided, and Strict modes
behave differently across trend and drawdown regimes; Strict mode is a risk
anchor for standard models, while reasoning-heavy models may need less rigid
control in uptrends. Ginger should not copy the agent. The implementable
lesson is to log the scaffold mode, regime, source set, and action constraints
before measuring whether LLM context improves an existing deterministic helper.

Implementable fields:

- `llm_strategy_alignment_mode`
- `llm_scaffold_regime_bucket`
- `llm_strict_mode_risk_anchor_flag`
- `llm_guided_mode_momentum_context_bucket`
- `llm_high_win_rate_trap_bucket`
- `llm_alignment_tax_bucket`
- `llm_mode_replacement_value_bucket`
- `llm_source_set_live_forward_hash`

Controls:

- predeclare whether the LLM is in Free, Guided, or Strict mode for a run;
- keep execution, sizing, exits, and hard constraints in deterministic code;
- compare each scaffold mode against the same displaced helper after costs;
- treat high win rate with weak total return as a failure mode, not success;
- evaluate mode x regime interactions before changing prompt or risk budgets.

Source: <https://arxiv.org/abs/2605.06024>

### Real-Time LLM Prediction Benchmarks Need Adversarial News Controls

PriceSeer is useful as an evaluation pattern for LLM market views because it is
live/dynamic, sector-balanced, horizon-aware, and explicitly tests vulnerability
to fake news. Ginger should copy the controls, not the direct prediction task:
every LLM-derived forecast or event label should carry a source set, horizon,
sector bucket, fake-news/adversarial-source flag, and realized path score before
it can condition a deterministic helper.

Implementable fields:

- `llm_live_benchmark_protocol_id`
- `llm_prediction_horizon_bucket`
- `llm_sector_context_bucket`
- `llm_external_info_source_hash`
- `llm_fake_news_susceptibility_flag`
- `llm_long_horizon_degradation_bucket`
- `llm_view_realized_path_score`
- `llm_sector_specific_error_bucket`

Controls:

- test LLM views under fixed horizons instead of mixing 5/10/20-day outcomes;
- include adversarial or low-credibility news flags in the evidence ledger;
- score sector-specific failures before promoting a generic text feature;
- keep LLM outputs schema-bound and default-off until replacement value clears
  accepted non-text comparators.

Source: <https://arxiv.org/abs/2601.06088>

### Adversarial Headline Sanitation Is A Data Contract

A 2026 adversarial-news trading study is a useful production warning because
the attack is upstream of the model: visually hidden text, Unicode homoglyphs,
or ticker-name misrouting can change LLM sentiment and then propagate into an
otherwise deterministic trading system. Ginger's compatible response is not a
new model. It is to treat every LLM-readable news item as hostile input until
source, text normalization, ticker mapping, and adversarial markers are logged
and replayable.

Implementable fields:

- `news_text_normalization_version`
- `news_unicode_homoglyph_flag`
- `news_hidden_text_flag`
- `news_ticker_entity_match_confidence`
- `news_source_sanitization_status`
- `news_adversarial_input_risk_bucket`
- `llm_sentiment_pre_sanitize_hash`
- `llm_sentiment_post_sanitize_hash`
- `adversarial_news_replacement_value_bucket`

Controls:

- normalize Unicode and strip or flag hidden/control text before LLM scoring;
- store pre- and post-sanitization hashes with source URL, publisher, and
  retrieval timestamp;
- fail closed when ticker/entity resolution changes after sanitization;
- run adversarial-source and low-credibility flags as attribution fields before
  they can affect ranking, sizing, exits, or vetoes.

Source: <https://arxiv.org/abs/2601.13082>

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

### Time-Series Foundation Models Are Priors, Not Alpha Engines

The late-June 2026 TSFM benchmark is directly useful because it is conservative:
pretrained models such as Moirai, TimesFM, Chronos, and TimeGPT can improve
rankings or lower development cost, but gains over a random-walk benchmark were
small and sparse on liquid U.S. equities. A related 2026 Chronos study found
multivariate inputs help when series are genuinely related, while noisy
cross-market mixing can degrade forecasts. Ginger should therefore treat TSFMs
as feature-construction priors and missing-data / low-sample helpers, not as
standalone candidate sources.

Implementable fields:

- `tsfm_model_family`
- `tsfm_pretraining_prior_id`
- `rolling_origin_protocol_id`
- `random_walk_placebo_delta`
- `local_supervised_baseline_delta`
- `related_series_context_set`
- `noisy_context_degradation_flag`
- `tsfm_after_cost_replacement_value`

Controls:

- require random-walk, local supervised, momentum, and volatility-scaled
  baselines on the same decision dates;
- separate forecast-loss improvement from after-cost replacement value;
- only mix related series with a predeclared relation graph or economic link;
- use TSFM outputs first as read-only state, imputation, or context fields
  until a shared helper beats accepted comparators.

Sources:

- <https://arxiv.org/abs/2606.27100>
- <https://arxiv.org/abs/2605.21504>

### Volatility TSFMs Must Beat Log-HAR And Calibration Baselines

A July 2026 realized-volatility benchmark is a useful check on TSFM enthusiasm:
pooled losses can favor foundation models, but the advantage concentrates in a
few outlier assets; asset-averaged comparisons leave only Tiny Time Mixers
narrowly ahead of a well-specified Log-HAR benchmark across horizons, and
Mincer-Zarnowitz recalibration shows much of the short-horizon gain is scale
calibration rather than new volatility information. Ginger should treat
volatility TSFMs as risk-state context only after they beat Log-HAR, equal-
weight ensemble, and calibration baselines on the same PIT assets.

Implementable fields:

- `vol_tsfm_model_family`
- `log_har_loss_ratio`
- `vol_forecast_calibration_delta`
- `mzm_recalibrated_gain_bucket`
- `asset_averaged_loss_rank`
- `tsfm_loghar_ensemble_flag`
- `vol_forecast_horizon_bucket`
- `vol_forecast_execution_context_value`

Controls:

- compare per asset, not only pooled loss across all names;
- report recalibrated and unrecalibrated loss separately;
- keep TSFM volatility forecasts as sizing/risk context until after-cost
  replacement value clears accepted helper comparators;
- prefer simple Log-HAR plus TSFM ensembles over single-model selection unless
  walk-forward evidence proves a stable architecture choice.

Source: <https://arxiv.org/abs/2607.05291>

### Look-Ahead Freedom Is A Type Contract

A July 2026 pipeline paper formalizes look-ahead freedom as temporal
non-interference over a time-indexed information lattice, separating a datum's
availability time from its reference time and giving a decidable checker for
value-independent operations such as windowing, joins, vintage reads, and
agentic retrieval. Ginger's translation is direct: every data surface should
record availability, reference period, and transformation effects so leakage is
caught before Gate 1-4, not inferred from suspiciously good results.

Implementable fields:

- `availability_timestamp`
- `reference_period_end`
- `temporal_effect_type`
- `pit_join_contract_id`
- `vintage_read_version`
- `agentic_retrieval_asof`
- `lookahead_typecheck_passed`
- `leakage_counterexample_id`

Controls:

- fail closed when availability time is missing or value-dependent;
- type-check joins, rolling windows, resampling, and retrieval before replay;
- preserve both reference time and availability time in artifacts;
- treat a silent empirical leak detector as insufficient proof of PIT safety.

Source: <https://arxiv.org/abs/2607.04958>

### Causal Separators Are Portfolio Covariance Inputs, Not Free Alpha

A July 2026 projected-Markowitz paper frames portfolio covariance around a
declared set of drivers: conditional on the realized path of those drivers,
returns are mutually independent, creating a diagonal-plus-low-rank conditional
covariance and a constrained projected Markowitz solution. Ginger's useful
translation is not to add an optimizer. It is to force portfolio-covariance
experiments to name the driver separator, report residual idiosyncratic floors,
and measure whether the projected covariance improves replacement value under
the existing one-row/day allocator constraints.

Implementable fields:

- `causal_separator_driver_set`
- `driver_availability_contract`
- `conditional_covariance_rank`
- `idiosyncratic_variance_floor`
- `projected_markowitz_constraint_id`
- `constraint_shadow_price_bucket`
- `separator_stability_delta`
- `projected_covariance_replacement_value`

Controls:

- predeclare drivers and availability timestamps before fitting covariance;
- compare against sample, shrinkage, PCA, and current accepted allocator
  baselines;
- report shadow prices and constraint gaps, not only optimized Sharpe;
- reject covariance gains that disappear under the actual slot/capital
  constraints or after turnover/costs.

Source: <https://arxiv.org/abs/2607.05320>

### Rotating Driver Manifolds Are Rebalance-Risk Context

Dynamic causal portfolio choice extends the separator idea: the relevant driver
geometry itself can rotate or jump, and that motion becomes a first-order
portfolio risk. Ginger should use this as a portfolio-covariance and allocator
diagnostic, not an optimizer mandate. A source router that works in one driver
state may fail when the common-driver manifold rotates, so experiments should
log driver-set stability and rebalance pressure before promoting allocation or
capacity changes.

Implementable fields:

- `driver_manifold_version`
- `driver_loading_rotation_bucket`
- `conditioning_set_change_flag`
- `geometry_jump_event_id`
- `rebalance_pressure_bucket`
- `unhedgeable_driver_change_risk`
- `driver_state_allocator_replacement_value`

Controls:

- predeclare the observable driver set and update cadence;
- score whether source/router performance is stable across driver rotations;
- report turnover and capacity impact from geometry changes;
- reject allocator gains that depend on hindsight driver-set changes.

Source: <https://arxiv.org/abs/2607.06702>

### Global Factor Detection Needs Eigenvector Breadth Checks

The July 2026 iterative global-factor paper combines adaptive
Marcenko-Pastur-edge recalibration with eigenvector participation-ratio filters
to avoid confusing weak global factors with high-dimensional noise near the BBP
transition. The Ginger use is a diagnostic around regime, covariance, and broad
source claims: a detected factor should have enough eigenvector breadth to be a
real common state, and source performance should be tested after removing or
conditioning on those global factors.

Implementable fields:

- `global_factor_detection_version`
- `mp_edge_recalibration_id`
- `eigenvector_participation_ratio`
- `bbp_near_edge_flag`
- `retained_global_factor_count`
- `factor_breadth_bucket`
- `source_residual_value_after_global_factors`

Controls:

- separate broad market/factor exposure from source-specific replacement value;
- block factor-conditioned policies when participation ratio is too localized
  or unstable;
- compare covariance and regime diagnostics with and without retained factors;
- use global-factor counts as context until Gate 1-4 proves a shared policy.

Source: <https://arxiv.org/abs/2607.06908>

### RL Manipulation Results Are Execution Safeguards

The July 2026 RL manipulation paper shows that a model-free agent can discover
profitable price-manipulative strategies in some nonlinear-impact settings when
model-based parameter estimates are noisy. Ginger should treat this as a
safety and market-impact lesson: learned allocators, execution policies, or
agentic tools need explicit manipulation, impact, and inventory-flow controls
before they touch live orders.

Implementable fields:

- `learning_execution_policy_id`
- `nonlinear_permanent_impact_bucket`
- `temporary_impact_cost_bucket`
- `manipulation_opportunity_flag`
- `impact_parameter_uncertainty_bucket`
- `inventory_roundtrip_constraint_passed`
- `execution_policy_safeguard_reason`

Controls:

- forbid learned policies from optimizing round-trip PnL without explicit
  impact and manipulation constraints;
- report impact-parameter uncertainty and inventory path shape;
- keep RL/agentic execution research sandboxed until compliance and
  production-order safeguards are machine-checkable;
- prefer deterministic no-trade / inaction bands when impact uncertainty is
  high.

Source: <https://arxiv.org/abs/2607.06121>

### Overnight And Intraday Tails Need Separate Risk States

Split-session Cluster GARCH work on U.S. equities finds material tail
heterogeneity between overnight and intraday returns, with sector-level tail
partitioning most useful in the overnight component and asset-level tail
heterogeneity improving out-of-sample likelihood and GMV portfolio performance.
Ginger should not translate this into a new entry signal. The implementable
surface is a risk/execution context that distinguishes overnight gap risk from
intraday continuation risk for sizing, stop interpretation, and live-drift
attribution.

Implementable fields:

- `session_tail_state_bucket`
- `overnight_tail_shape_bucket`
- `intraday_tail_shape_bucket`
- `sector_tail_partition_id`
- `asset_tail_heterogeneity_score`
- `gap_risk_execution_bucket`
- `session_conditional_correlation_bucket`
- `session_tail_replacement_value`

Controls:

- score overnight and intraday returns separately before using tail states;
- keep sector-tail partitions PIT and stable across windows;
- use session-tail fields as sizing/execution diagnostics before any entry or
  ranking change;
- compare session-aware risk changes against current drawdown, live-drift, and
  accepted default-off helper baselines.

Source: <https://arxiv.org/abs/2607.03669>

### Tail Dependence Diagnostics Are Sample-Limited

July 2026 local-Gaussian-correlation work is a useful anti-overfitting warning
for tail and contagion surfaces. Tail dependence estimates degrade exactly
where the system wants them most, and the binding constraint is often local
effective sample size rather than a smarter adaptive bandwidth. Ginger should
make `effective_n` a first-class field before using any tail-correlation,
sector-contagion, or cross-sleeve concentration result as a risk policy.

Implementable fields:

- `tail_dependence_protocol_id`
- `tail_local_effective_n`
- `tail_correlation_bandwidth_id`
- `tail_estimator_variance_floor`
- `tail_resample_stability_bucket`
- `tail_dependence_regime_bucket`
- `tail_surface_adaptivity_flag`
- `tail_policy_replacement_value`

Controls:

- block tail-policy promotion when local effective sample size is too small;
- report resampling dispersion next to any tail-correlation estimate;
- treat adaptive estimator gains as diagnostic unless they survive the same
  windows and replacement-value comparator;
- prefer forward-row accumulation over threshold or bandwidth retunes when the
  tail sample is sparse.

Source: <https://arxiv.org/abs/2607.03888>

### Semantic Retrieval Forecasting Needs Evidence Keys

Recent retrieval-augmented time-series work points to a useful middle ground
between raw nearest-neighbor pattern matching and black-box forecasting. FinSeer
uses financial-history retrieval tailored to stock forecasting; SERAF adds a
second semantic retrieval channel because numeric similarity alone can fail
under non-stationarity. Ginger's translation is narrow: retrieved analogs are
not trade signals unless the retrieval key is PIT, semantically explainable,
and scored against the displaced candidate after costs.

Implementable fields:

- `retrieval_forecast_protocol_id`
- `numeric_pattern_retrieval_key`
- `semantic_pattern_retrieval_key`
- `retrieved_analog_asof`
- `retrieved_analog_future_blind_flag`
- `retrieval_relation_explanation_bucket`
- `semantic_numeric_retrieval_agreement_bucket`
- `retrieval_after_cost_replacement_value`

Controls:

- persist retrieved analog ids, source windows, semantic labels, and as-of
  timestamps before scoring;
- compare numeric-only, semantic-only, and joint retrieval against momentum,
  random-walk, and accepted-helper comparators;
- forbid retrieval keys that smuggle future return paths or post-event labels;
- use semantic retrieval first to prioritize forward observation rows, not to
  change orders or sizing before Gate 1-4.

Sources:

- <https://arxiv.org/abs/2502.05878>
- <https://arxiv.org/abs/2606.14941>

### Continuous Style Allocation Beats Discrete Regime Rules

A May 2026 growth-versus-defensive allocation paper is most useful as a risk
allocation design pattern. It treats the relative trade as style exposure,
uses factor attribution before claiming alpha, replaces hard regime switches
with a smooth score, maps the score to bounded active tilts, and validates
against transaction costs plus static style benchmarks. Ginger's translation:
regime routers should prefer continuous, bounded, auditable exposure scores
over another if/then state label or scalar sweep.

Implementable fields:

- `style_allocation_score_version`
- `growth_defensive_style_exposure_bucket`
- `rate_relief_component_score`
- `spy_drawdown_relief_component_score`
- `vix_stress_relief_component_score`
- `growth_crowding_penalty_score`
- `bounded_active_tilt_pct`
- `style_timing_factor_attribution_bucket`
- `style_timing_static_benchmark_delta`

Controls:

- decompose any style router into market, value, momentum, and residual
  exposure before calling it alpha;
- map continuous scores to bounded tilts and smooth realized weights;
- compare against SPY/QQQ, static high-growth, static balanced, and
  volatility-matched benchmarks after turnover costs;
- do not retune discrete regime cells unless the continuous score adds
  forward replacement value under a fixed envelope.

Source: <https://arxiv.org/abs/2605.20636>

### Sectoral Regime Allocation Is An Envelope, Not A Signal Shortcut

RegimeFolio's useful engineering pattern is modular: an interpretable
volatility-regime classifier, sector-specific learners, and shrinkage-aware
allocation. This reinforces Ginger's rule that regimes should shape capacity,
risk, and comparator selection before they become entry filters. Sector/regime
conditioning is only useful if it is PIT, interpretable, and benchmarked
against static sector/style alternatives after turnover costs.

Implementable fields:

- `vix_regime_classifier_version`
- `sector_specific_forecast_bucket`
- `sector_regime_allocation_score`
- `shrinkage_covariance_version`
- `static_sector_benchmark_delta`
- `regime_sector_turnover_cost`
- `sector_capacity_cap_reason`
- `sector_regime_replacement_value`

Controls:

- keep the regime classifier interpretable and frozen before replay;
- separate sector beta, style exposure, and residual alpha;
- compare against static sector/style allocations and SPY/QQQ after costs;
- use the surface first for capacity/risk attribution unless Gate 1-4 proves
  an entry or allocation change.

Source: <https://arxiv.org/abs/2510.14986>

### Regime-HMM/RL Evidence Requires Lagged, Costed Envelopes

A May 2026 HMM/RL allocation study is useful because it evaluates regime
allocation with a 30% out-of-sample split and a one-day execution lag. The
local translation is not to add an RL allocator. It is to make any regime
capacity rule declare the latent-state model, lag, cost, and benchmark before
testing. A separate 2026 global-equity DRL study reinforces the guardrail:
even with transaction costs, turnover penalties, diversification constraints,
LSTM/Transformer encoders, and walk-forward folds, excess returns were not
statistically robust across all markets. Regime/RL should therefore be a
capacity and stress-envelope surface unless a fixed policy clears Ginger's
Gate 1-4.

Implementable fields:

- `regime_model_family`
- `hmm_state_probability_vector`
- `regime_policy_execution_lag_days`
- `regime_policy_cost_model_version`
- `regime_policy_walk_forward_fold_id`
- `regime_policy_benchmark_set`
- `rl_policy_turnover_penalty_bucket`
- `rl_policy_cross_market_robustness_bucket`
- `regime_policy_incremental_replacement_value`

Controls:

- freeze the regime classifier and action map before replay;
- require at least a one-session decision lag unless production truly acts
  before the next open;
- compare against static SPY/QQQ, static sector/style, and accepted allocator
  benchmarks after turnover and slippage;
- treat market-specific wins without cross-window robustness as diagnostics,
  not activation evidence.

Sources:

- <https://arxiv.org/abs/2605.27848>
- <https://arxiv.org/abs/2605.17307>

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

### Supply-Chain Text Propagation Needs PIT Relation Edges

Late-June 2026 research combines annual-report LLM embeddings with supply-chain
knowledge-graph propagation and reports cross-sectional return predictability
after momentum, volatility, size, sector-neutral, placebo, and out-of-sample
checks. The Ginger-compatible lesson is not to deploy a text embedding factor.
It is to make entity-relation edges first-class, timestamped evidence: a filing
or news label may matter more when it propagates through a verified
customer/supplier/economic-exposure graph than when scored only on the issuer.

Implementable fields:

- `supply_chain_edge_source_id`
- `supply_chain_edge_asof`
- `supply_chain_relation_type`
- `supplier_customer_exposure_bucket`
- `text_embedding_source_accession`
- `network_propagated_text_signal_bucket`
- `relation_propagation_placebo_delta`
- `sector_neutral_relation_delta`
- `relation_propagated_replacement_value`

Controls:

- use only relation edges known before the candidate decision date;
- separate issuer text, neighbor text, and propagated text effects;
- run sector, momentum, volatility, size, and random-edge placebos before
  counting a propagated signal as alpha;
- compare against accepted relation adapters and same-theme opportunity cost
  after costs, not against cash alone.

Source: <https://arxiv.org/abs/2606.29290>

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

### Cost-Aware Forecast-To-Trade Conversion

A May 2026 walk-forward trading study on BTC is not equity evidence, but its
engineering lesson is directly portable: weak forecasts become tradable only
when the decision rule is cost-aware. A magnitude threshold tied to transaction
cost reduced turnover and restored profitability in selected configurations,
where naive sign-based conversion failed after costs. For Ginger, this maps to
activation-envelope design and candidate displacement gates, not to another
predictive model.

Implementable fields:

- `forecast_magnitude_after_cost_bucket`
- `cost_aware_trade_filter_version`
- `expected_edge_to_cost_ratio`
- `turnover_suppression_reason`
- `forecast_to_trade_conversion_bucket`
- `cost_threshold_abstain_flag`
- `walk_forward_protocol_id`

Controls:

- require every forecast-like field to state the minimum edge needed to beat
  spread, slippage, borrow/fees, and the accepted displaced helper;
- report abstentions as evidence, not missing trades;
- evaluate walk-forward or forward rows before changing live sizing or slots;
- keep the conversion rule fixed before measuring after-cost replacement value.

Source: <https://arxiv.org/abs/2606.00060>

### Multi-Period Optimization Aligns Forecasts With Costs

Integrated Prediction and Multi-period Portfolio Optimization (IPMO) highlights
a local measurement problem: optimizing prediction error separately from the
portfolio decision can misalign the model with after-cost performance. The
paper's useful pattern is a multi-period objective with turnover penalties and
path-aware allocation, not another black-box predictor. Ginger can translate
this into allocator-envelope diagnostics: candidate sources should be judged by
the capital path, turnover, slot displacement, and net replacement value they
create over the intended holding horizon.

Implementable fields:

- `multi_period_allocation_horizon`
- `turnover_penalty_version`
- `path_dependent_risk_bucket`
- `forecast_decision_alignment_score`
- `allocation_path_coherence_bucket`
- `slot_displacement_cost_bucket`
- `multi_period_replacement_value_after_cost`
- `capacity_shadow_price_bucket`

Controls:

- evaluate the whole allocation path, not only next-trade PnL;
- include turnover and cooldown displacement in the after artifact;
- compare against the current accepted one-slot allocator and cash alternative;
- use this first for envelope design before changing live or paper capacity.

Source: <https://arxiv.org/abs/2512.11273>

### Exit Parameter Searches Need Full-Denominator Oracle Rows

Recent stop-loss / take-profit parameterization work is useful as a workflow
warning, not as a license to tune exits. Exit rules are path-dependent and can
look good when only selected winners, selected regret rows, or one market
state are inspected. Ginger's translation is to require full-denominator
fixed-entry oracle rows before designing a shared exit lifecycle, then test the
actual executable policy through Gate 1-4.

Implementable fields:

- `fixed_entry_oracle_row_id`
- `exit_oracle_denominator_coverage`
- `exit_regret_bucket`
- `max_favorable_excursion_pct`
- `max_adverse_excursion_pct`
- `giveback_pct`
- `candidate_exit_policy_version`
- `exit_policy_costed_replacement_value`

Controls:

- persist every completed trade row, not only top-regret examples;
- separate diagnostic oracle labels from executable exit inputs;
- freeze stop/target/time/confirmation semantics before after-measurement;
- compare against the current shared stop/target lifecycle across all standard
  windows and report drawdown, trade count, and window regressions.

Local June 30 check: `exp-20260630-009` was rejected because the artifact only
saved top-regret samples, `exp-20260630-011` repaired the full-row oracle
surface, and `exp-20260630-012` rejected close-confirmed static stops through
Gate 4. The next exit alpha needs a cohort-level oracle hypothesis plus shared
production/backtest policy, not a stop-distance or response-curve retune.

Source: <https://arxiv.org/abs/2604.27150>

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

### Explainable Zero-Shot News Is Reliability Context

A June 2026 zero-shot financial-news NLP study is a useful brake on raw
headline enthusiasm. Its key local lesson is that zero-shot news models can
fail simple baselines on short-horizon direction, especially negative moves,
while explanation signals can still separate more trustworthy from unreliable
predictions. For Ginger, explainability is therefore a reliability and
uncertainty field, not an entry signal by itself.

Implementable fields:

- `news_zero_shot_model_id`
- `news_prediction_horizon_bucket`
- `news_temporal_aggregation_version`
- `news_explanation_token_support_score`
- `news_article_level_evidence_score`
- `news_aggregate_evidence_consistency_bucket`
- `news_prediction_reliability_bucket`
- `news_explainability_replacement_value_bucket`

Controls:

- benchmark any zero-shot news field against simple recency, market, and
  sentiment baselines before paper use;
- score positive and negative movement predictions separately;
- store token/article/aggregate evidence with source timestamps and model id;
- use explanation quality first as an uncertainty and veto-attribution surface,
  not as a direct buy/sell rule.

Local June 30 check: `exp-20260630-002` rejected a fixed positive-event
taxonomy on daily clean-trade-news rows, while `exp-20260630-004..007` retained
structured event ledgers and daily snapshots as measurement surfaces. The
research-compatible next step is not another keyword list; it is a
schema-bound actor/relation/object/magnitude event row with source hashes,
explicit-ticker provenance, and closed replacement value.

Source: <https://arxiv.org/abs/2606.12210>

### Hedge-Fund LLM Forecasting Pitfall Checklist

An April 2026 hedge-fund-oriented review of LLM stock forecasting is useful as
a checklist, not as an alpha source. Its practical warnings map directly to
Ginger's repeated local failures: sentiment fragility, horizon mismatch,
leakage, weak metrics, illiquidity premia, and limited predictability can make
LLM results look better in papers than in a production-costed system.

Implementable fields:

- `llm_forecast_use_case_bucket`
- `llm_dataset_horizon_protocol_id`
- `llm_leakage_control_status`
- `llm_illiquidity_premium_bucket`
- `llm_metric_to_trade_gap_bucket`
- `llm_sentiment_fragility_bucket`
- `llm_costed_replacement_value_bucket`
- `llm_predictability_limit_reason`

Controls:

- declare the forecast horizon before scoring any text or agent output;
- compare the LLM feature against the displaced accepted helper after costs,
  not only against prediction accuracy or directional hit rate;
- report liquidity, universe, and timestamp controls before claiming alpha;
- keep the LLM as a field builder unless a shared helper passes Gate 1-4.

Source: <https://arxiv.org/abs/2605.05211>

### LLM As Conditional Feature For Existing Factors

Recent LLM systematic-investing papers are most useful when they condition an
existing factor or candidate source rather than asking the model to invent
orders. One study finds LLM-scored firm news can improve concentrated
cross-sectional momentum portfolios after costs; another shows quantitative
factors and LLM newsflow representations can be fused, but fusion architecture
and modality-specific training matter. Ginger should translate this into
schema-bound text fields attached to accepted helpers and measured by
replacement value.

Implementable fields:

- `llm_news_conditioning_model_id`
- `llm_news_supports_existing_factor_bucket`
- `factor_news_fusion_method`
- `single_modality_vs_fusion_delta_bucket`
- `llm_news_high_conviction_flag`
- `llm_news_factor_disagreement_bucket`
- `llm_conditioned_replacement_value_bucket`

Controls:

- predeclare whether the LLM conditions momentum, fundamentals, allocator
  source choice, or risk, rather than allowing broad discretionary scoring;
- preserve the exact news set, prompt/schema, model id, and factor state seen
  at decision time;
- compare conditioned rows against the unconditioned accepted helper after
  costs and concentration controls;
- treat low-coverage or model-disagreement cases as abstentions until forward
  evidence matures.

Sources:

- <https://arxiv.org/abs/2510.26228>
- <https://arxiv.org/abs/2510.15691>

### LLM Alpha Mining Requires A Trajectory Ledger

Recent LLM alpha-mining systems are useful because they make idea generation,
code generation, critique, and backtest feedback explicit. July 2026 XAlpha,
March 2026 FactorEngine, and February 2026 FactorMiner sharpen the engineering
lesson: the durable asset is a memory-controlled research loop that separates
hypothesis planning, executable factor/code generation, code/idea consistency
verification, hyperparameter search, empirical feedback, redundancy checks, and
failure distillation. The local lesson is not to outsource alpha discovery to an
agent; it is to persist every generated hypothesis, formula/code hash, critique,
repair, comparator, and backtest result as a replayable trajectory. This is the
missing audit layer between an LLM idea and Ginger's `experiment.py new`
contract.

Implementable fields:

- `llm_alpha_miner_model_id`
- `llm_alpha_hypothesis_hash`
- `llm_generated_factor_code_hash`
- `llm_factor_parse_status`
- `llm_factor_redundancy_bucket`
- `llm_backtest_feedback_iteration`
- `llm_hypothesis_to_code_consistency_score`
- `llm_alpha_miner_comparator_delta`
- `llm_alpha_miner_repair_reason`
- `llm_alpha_memory_cycle_id`
- `llm_factor_logic_revision_id`
- `llm_factor_hyperparameter_search_id`
- `llm_factor_redundancy_neighbor_ids`
- `llm_failure_distillation_card_id`

Controls:

- reserve a normal experiment ID before any LLM-generated factor affects a
  replay;
- store the natural-language hypothesis, executable code, tests, and backtest
  configuration as a single immutable trajectory;
- compare the generated factor against simple recency/momentum/volatility
  placebos and the accepted local comparator after costs;
- treat self-repair loops as multiple-testing exposure unless the full
  trajectory and rejected candidates are logged.
- separate logic revisions from parameter searches; a threshold sweep is not a
  new idea unless the factor logic or evidence surface changes;
- require a code-vs-hypothesis consistency check and redundancy check before a
  generated factor can reserve an alpha experiment.

Sources:

- <https://arxiv.org/abs/2607.08332>
- <https://arxiv.org/abs/2603.16365>
- <https://arxiv.org/abs/2602.14670>
- <https://arxiv.org/abs/2602.07085>
- <https://arxiv.org/abs/2511.18850>

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

### AI Agent Behavioral Bias Audit

Experimental-market evidence shows autonomous LLM traders can display classic
behavioral biases such as disposition effects and recency-weighted extrapolation;
agent disagreement and prompt interventions can change market-bubble dynamics.
For Ginger, this is a risk-audit surface for agent or LLM outputs, not a reason
to let agents place trades.

Implementable fields:

- `agent_disposition_effect_score`
- `agent_recency_extrapolation_score`
- `agent_excess_demand_bucket`
- `agent_disagreement_volume_bucket`
- `agent_reasoning_mechanism_bucket`
- `prompt_intervention_bias_delta`
- `agent_bubble_amplification_risk_bucket`
- `agent_behavioral_bias_audit_version`

Controls:

- score agent outputs for recency chasing, loss reluctance, and disagreement
  before using them as evidence rows;
- preserve prompts and reasoning text so bias scores are replayable;
- treat prompt changes as policy changes that require fixed pre/post evaluation;
- never let agent consensus override deterministic risk, sizing, or exit logic.

Source: <https://arxiv.org/abs/2604.18373>

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
- `rag_hard_negative_retriever_version`
- `rag_program_of_thought_code_hash`
- `rag_adaptive_complexity_bucket`
- `rag_cost_budget_bucket`

Controls:

- fail closed when source spans or numeric self-checks are missing;
- execute arithmetic and period matching through deterministic code, not LLM
  mental math;
- route expensive multi-step retrieval only when the task complexity requires
  it, and log the cost/latency tradeoff;
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

### SEC RAG Must Preserve Filing Structure And Outcome Labels

Recent SEC-specific retrieval work points to two concrete requirements: filing
chunks need semantic structure instead of arbitrary token windows, and
explainable stock-movement labels should preserve which disclosure section and
risk item produced the evidence. For Ginger, this maps directly to the SEC text
blockers: before another filing-text candidate pool, the archive should expose
accession-bounded section/table spans, retrieval metadata, risk-factor/event
labels, and realized 5/10/20-day outcome labels.

Implementable fields:

- `sec_rag_chunking_version`
- `sec_filing_section_span_hash`
- `sec_filing_table_span_hash`
- `sec_risk_item_label`
- `sec_disclosure_event_label`
- `sec_rag_retrieval_rank`
- `sec_rag_missing_section_reason`
- `sec_label_outcome_horizon`
- `sec_label_realized_path_bucket`

Controls:

- chunk SEC filings by section/table/document structure, not arbitrary text
  size alone;
- key every retrieved span by accession, accepted timestamp, form, section,
  and parser version;
- keep risk/event labels as observed evidence rows until they beat accepted
  SEC and non-text comparators after costs;
- score retrieval coverage and missing sections before using LLM labels for
  candidate-pool, ranking, or risk decisions.

Sources:

- <https://arxiv.org/abs/2508.06312>
- <https://arxiv.org/abs/2601.19189>

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

### Financial Tool Agents Need Domain-Alignment Ledgers

FinToolBench and the broader FinLLM / FinAgent evaluation-suite work are useful
because they evaluate finance agents as tool-using systems, not static text
classifiers. The Ginger translation is direct: any agent that retrieves prices,
filings, broker state, macro data, or order information must leave a runnable
tool trace with timestamp, intent, regulatory/domain alignment, and execution
status. A correct-looking answer is not enough if the tool call was stale,
misrouted, or outside the declared finance domain.

Implementable fields:

- `financial_tool_manifest_version`
- `tool_call_trace_hash`
- `tool_data_timestamp`
- `tool_intent_type`
- `tool_regulatory_domain_bucket`
- `tool_result_timeliness_bucket`
- `tool_retrieval_reasoning_failure`
- `tool_execution_status`
- `tool_output_replay_passed`
- `tool_assisted_replacement_value`

Controls:

- preserve every tool call, input, output hash, timestamp, and failure mode in
  the experiment artifact;
- separate retrieval failure, stale data, wrong-domain tool choice, and invalid
  execution from model reasoning failure;
- require deterministic replay of the tool trace before using agent-produced
  fields in candidate pools, ranking, sizing, exits, or risk;
- benchmark tool-assisted rows against cash, SPY/QQQ, and the exact displaced
  accepted helper after costs.

Sources:

- <https://arxiv.org/abs/2603.08262>
- <https://arxiv.org/abs/2602.19073>

### Trading-R1 Style Reasoning Traces Need Action-Level Attribution

Trading-R1 is useful as an LLM-agent engineering pattern because it trains and
evaluates long-chain trading reasoning over a decision history, but its local
translation is narrow: keep the reasoning trace as auditable evidence attached
to a frozen action schema. Do not let a richer chain-of-thought substitute for
PIT data, costs, universe controls, or a displaced-candidate comparator.

Implementable fields:

- `trading_rationale_trace_hash`
- `reasoning_step_count_bucket`
- `action_schema_violation_count`
- `position_state_memory_hash`
- `counterfactual_hold_cash_delta`
- `rationale_to_action_consistency_bucket`
- `reasoning_trace_costed_replacement_value`

Controls:

- freeze the observation set, action schema, and portfolio state before the
  model sees them;
- log every tool call, rationale summary, action, invalid action, and
  abstention as replayable rows;
- compare against cash, buy-and-hold, SPY/QQQ, and the exact default-off helper
  displaced by the action;
- treat the trace as diagnosis until the deterministic helper using derived
  fields passes Gate 1-4.

Source: <https://arxiv.org/abs/2509.11420>

### Live Prediction-Market LLM Benchmark Discipline

PolyBench is not an equity-alpha paper, but its benchmark design is useful for
Ginger: timestamp-locked market state, synchronized news, order-book execution,
confidence-weighted returns, APY, and Sharpe expose the gap between confident
LLM forecasts and actually tradable outcomes. The local translation is a
stricter evidence ledger for any LLM or agentic market view, not autonomous
trading.

Implementable fields:

- `live_market_state_snapshot_hash`
- `llm_forecast_timestamp_lock_id`
- `llm_confidence_weighted_return_bucket`
- `agent_order_book_execution_model`
- `agent_invalid_or_abstain_action_count`
- `agent_confidence_to_pnl_calibration_bucket`
- `agent_market_design_sensitivity_bucket`

Controls:

- freeze the market/news snapshot before the model sees it;
- report confidence calibration against realized PnL, not only direction;
- simulate execution against the available book/spread when a market has one;
- compare against cash, passive benchmarks, and the exact displaced helper.

Source: <https://arxiv.org/abs/2604.14199>

### Real-Market Agent Benchmarks Need Comparator Discipline

Recent real-market LLM-agent benchmarks are useful mainly as measurement
templates. StockBench evaluates multi-month daily buy/sell/hold agents with
prices, fundamentals, and news, and reports that most models still struggle
against buy-and-hold. Agent Market Arena adds live multi-market evaluation and
shows agent architecture and risk style can matter more than model backbone.
PredictionMarketBench adds a stricter execution-replay pattern: build episodes
from raw orderbooks/trades/lifecycle/settlement, simulate maker/taker fees, and
log reproducible tool-call trajectories. For Ginger, this reinforces
deterministic policy ownership: agent outputs are evidence rows unless they beat
a named displaced candidate after costs and executable market mechanics.

Implementable fields:

- `agent_benchmark_protocol_id`
- `agent_daily_observation_set_hash`
- `agent_action_schema_version`
- `agent_risk_style_bucket`
- `agent_buy_hold_delta_bucket`
- `agent_displaced_candidate_id`
- `agent_replacement_value_after_cost`
- `agent_action_turnover_bucket`
- `agent_execution_replay_protocol_id`
- `agent_maker_taker_fee_bps`
- `agent_settlement_risk_bucket`

Controls:

- evaluate against SPY/QQQ, cash, and the exact accepted helper displaced;
- log invalid actions, abstentions, turnover, drawdown, and cost sensitivity;
- when orderbook or quote data exists, replay executable actions through the
  relevant spread/fee/settlement model instead of close-to-close fills;
- separate model backbone, prompt/scaffold, and agent architecture effects;
- keep agent decisions default-off until Gate 1-4 and parity evidence exist.

Sources:

- <https://arxiv.org/abs/2510.02209>
- <https://arxiv.org/abs/2510.11695>
- <https://arxiv.org/abs/2602.00133>

### Memory-Controlled LLM Trading Evaluation

KTD-Fin, published in late May 2026, is a useful benchmark design pattern for
Ginger because it separates two failures that local experiments repeatedly
encounter: LLMs can rely on memorized ticker/date priors, and headline returns
can come from beta or style exposure rather than stock-selection skill. Its
data-side masking, de-anonymization probe, and Barra-style attribution map
directly to replayable controls for any LLM-assisted or agentic paper alpha.

Implementable fields:

- `agent_data_masking_protocol_id`
- `ticker_alias_map_hash`
- `date_alias_map_hash`
- `pretraining_memory_exposure_bucket`
- `deanonymization_probe_success_rate`
- `agent_style_exposure_bucket`
- `agent_market_beta_exposure_bucket`
- `agent_stock_selection_alpha_bucket`
- `agent_action_violation_count`
- `agent_abstention_rate`

Controls:

- evaluate LLM/agent signals under ticker/date masking or an equivalent
  post-cutoff protocol before trusting semantic rationales;
- decompose returns into market, style, and stock-specific residual components
  before calling an agent result alpha;
- keep invalid action/schema violations visible rather than silently fixing
  them;
- require replacement value versus the exact displaced accepted helper or cash,
  not just agent portfolio return.

Source: <https://arxiv.org/abs/2605.28359>

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

### Trading-Signal Reasoning Benchmarks

FinTradeBench (updated June 2026) stresses a practical limitation for LLM use:
retrieval helps textual fundamentals, but current models still struggle with
trading-signal and hybrid fundamentals-plus-OHLCV reasoning. For Ginger, this
argues against asking an LLM whether a pullback or breakout is actionable. The
LLM should instead fill bounded fields that can be audited against numeric
signals and replacement value.

Implementable fields:

- `financial_reasoning_benchmark_version`
- `fundamental_signal_conflict_bucket`
- `trading_signal_reasoning_failure_bucket`
- `llm_numeric_audit_passed`
- `hybrid_fundamental_ohlcv_reason_code`
- `retrieval_helped_text_not_price_flag`
- `llm_signal_reasoning_replay_hash`

Controls:

- store the exact numeric indicators shown to the model;
- separate textual-fundamental retrieval quality from OHLCV reasoning quality;
- never let a free-form LLM interpretation override deterministic breakout,
  pullback, volume, or risk fields without Gate 1-4 evidence.

Source: <https://arxiv.org/html/2603.19225v4>

### Anonymized LLM-GNN Signal Validation

BlindTrade proposes anonymizing daily S&P 500 constituents before LLM scoring,
combining specialized LLM perspectives with graph aggregation, and validating
signals with IC and negative controls. The usable lesson is not the RL policy;
it is the anti-memorization and signal-validation protocol. Ginger should use
anonymization, PIT constituents, random-shuffle controls, and per-agent score
attribution before trusting LLM text signals.

Implementable fields:

- `ticker_anonymization_protocol_id`
- `pit_constituent_source_id`
- `llm_perspective_agent_id`
- `agent_score_ic_bucket`
- `agent_score_shuffle_control_delta`
- `semantic_graph_encoder_version`
- `llm_reason_embedding_similarity_bucket`
- `llm_signal_memorization_risk_bucket`

Controls:

- score only securities that were PIT-eligible at the decision date;
- run negative controls such as shuffled scores or anonymized ticker aliases;
- keep specialized LLM perspectives separate before any ensemble or allocator;
- use IC and replacement-value attribution, not only portfolio PnL.

Source: <https://arxiv.org/html/2603.17692v1>

### Execution-Assumption Reproducibility Audit

The June 2026 review "Beyond Agent Architecture" finds that LLM trading papers
often describe architectures more clearly than the assumptions that decide
whether results are economically interpretable: data provenance, split timing,
execution semantics, turnover, costs, universe definition, and artifacts. This
directly maps to Ginger's Gate 1-4 and experiment closeout rules.

Implementable fields:

- `execution_assumption_matrix_version`
- `data_provenance_tier`
- `temporal_split_discipline_bucket`
- `order_timing_semantics_id`
- `turnover_cost_model_version`
- `universe_definition_pit_flag`
- `artifact_reproducibility_tier`
- `agent_result_protocol_comparability_bucket`

Controls:

- reject agent or LLM alpha records that lack PIT universe, cost, turnover,
  execution-timing, and artifact hashes;
- report result sensitivity to one-way cost and turnover when the strategy
  reallocates frequently;
- treat architecture novelty as irrelevant unless the measurement protocol is
  comparable to accepted local baselines.

Source: <https://arxiv.org/abs/2606.08285>

### Financial AI Determinism Is A Production Contract

A May 2026 financial-AI auditability survey reframes reproducibility as a
systems property: tabular explanations, graph embeddings, and LLM agent
trajectories can vary across identical inputs because of sampling,
asynchronous graph updates, batching, and hardware-level numerical effects.
For Ginger, this is not a reason to avoid LLMs or graph features. It is a rule
that any model-generated field used for attribution, ranking, exits, or
activation must carry a replay hash, model/runtime identity, and stability
measurement before it can influence a shared policy.

Implementable fields:

- `model_runtime_identity_hash`
- `agent_replay_trace_hash`
- `llm_output_stability_bucket`
- `graph_embedding_variance_bucket`
- `feature_attribution_rank_stability`
- `batching_nondeterminism_flag`
- `hardware_runtime_drift_bucket`
- `audit_replay_passed`

Controls:

- store prompt/input, model id, runtime version, decoding settings, and output
  JSON for every LLM-derived field;
- measure repeated-run agreement for borderline labels before promotion;
- prefer deterministic parsers / exact explainers for numeric and rule-owned
  fields;
- fail closed when a field cannot be reconstructed from committed artifacts.

Source: <https://arxiv.org/abs/2605.23955>

### Nonlinear Market Impact And Turnover Discipline

Recent RL trading-environment work shows that replacing fixed-cost assumptions
with Almgren-Chriss / square-root style market impact can change absolute
performance, algorithm ranking, turnover, and out-of-sample Sharpe. Ginger's
paper adapters currently use small default-off notionals, but any live-eligible
activation envelope should treat liquidity, participation, and nonlinear cost
as first-class fields rather than a post-hoc haircut.

A June 2026 AAPL market-impact micro-study is a useful calibration warning:
the square-root law can fit aggregated impact well, but estimation depends on
trade signing, horizon, volatility normalization, and liquidity regime. Ginger
should therefore log the calibration window and participation bucket used by
any live activation envelope instead of treating one impact coefficient as a
constant.

Implementable fields:

- `market_impact_model_version`
- `participation_rate_bucket`
- `square_root_impact_cost_bps`
- `permanent_impact_decay_bucket`
- `turnover_constraint_bucket`
- `cost_model_sensitivity_bucket`
- `impact_calibration_window_id`
- `impact_trade_signing_method`
- `capacity_adjusted_replacement_value`
- `live_activation_notional_capacity_bucket`

Controls:

- estimate one-way spread/slippage and nonlinear impact at the proposed live
  notional, not only the $4k paper notional;
- report replacement value net of costs at base, stressed, and capped
  participation assumptions;
- reject activation when profit comes mostly from high-turnover behavior that
  disappears under realistic impact;
- keep execution-envelope tests separate from new alpha searches.

Sources:

- <https://arxiv.org/abs/2603.29086>
- <https://arxiv.org/abs/2606.24019>

### Cost-Aware Optimization Is A Capacity Surface

FlashFolio is useful less as a dependency than as an engineering lesson:
single-period and multi-period portfolio optimization can include factor risk,
bid-offer costs, and nonlinear market impact at realistic scale. For Ginger,
the concrete takeaway is to keep alpha discovery separate from capacity
optimization. Once a helper is accepted, evaluate live eligibility through a
fixed execution envelope that reports factor exposure, turnover, spread cost,
impact cost, and displaced-row replacement value.

Implementable fields:

- `portfolio_optimization_solver_version`
- `factor_risk_model_version`
- `multi_period_horizon_days`
- `bid_offer_cost_bps`
- `nonlinear_impact_cost_bps`
- `capacity_solver_runtime_bucket`
- `capacity_constrained_replacement_value`
- `activation_envelope_feasible_flag`

Controls:

- use optimization only after the alpha source is fixed, not to search across
  signals and sizing rules simultaneously;
- compare capacity-constrained output against the accepted one-slot allocator
  and current paper notional envelope;
- report whether turnover/impact constraints change the selected rows, not only
  the final portfolio weights;
- keep solver changes as activation-envelope evidence unless they alter the
  underlying alpha decision hypothesis.

Source: <https://arxiv.org/abs/2604.22625>

### Anticipatory Optimization Needs A Control-Gap Ledger

Anticipatory portfolio optimization formalizes a trap Ginger has already seen:
an optimizer can act on a richer model than the estimator used to justify it,
through extra information, multi-horizon forecasts, or impact-aware deployment.
Correct anticipation can add value, but misspecified anticipation is harmful
when estimated structure is optimized as truth. The local control is to log the
gap between the restricted price-taking baseline and the enriched controller
before treating an allocation overlay as alpha.

Implementable fields:

- `anticipatory_controller_version`
- `restricted_estimator_version`
- `control_gap_protocol_id`
- `information_enrichment_hash`
- `forecast_stack_horizon_set`
- `impact_anticipation_model_version`
- `anticipation_misspecification_penalty`
- `restricted_vs_enriched_replacement_value`

Controls:

- compare enriched allocations against the restricted cash-feasible allocator on
  the same frozen rows and costs;
- separate information, forecast-horizon, and impact-deployment enrichment in
  the artifact rather than bundling them into one optimizer score;
- fail closed when the enriched model uses data unavailable at decision time or
  when the control gap is not reproducible;
- use the control-gap ledger as activation-envelope evidence unless the
  enriched controller is itself the predeclared single decision hypothesis.

Source: <https://arxiv.org/abs/2606.04258>

### LLM-Guided State And Reward Interfaces

GIFT uses an LLM to design state-enhancement and reward-shaping interfaces for
financial RL, then freezes the selected interface before evaluation. This is a
useful boundary for Ginger: the LLM may propose interpretable factor channels
or reward diagnostics offline, but the evaluated policy and feature interface
must be fixed before Gate 1 and must not call the LLM during the test window.

Implementable fields:

- `state_interface_version`
- `llm_generated_factor_channel_id`
- `reward_shaping_rule_set_id`
- `interface_freeze_timestamp`
- `state_reward_diagnostic_ic_bucket`
- `reward_stability_bucket`
- `rollout_diagnostic_revision_count`
- `test_time_llm_calls_flag`

Controls:

- freeze generated feature/reward code before evaluation;
- record diagnostic feedback used to revise the interface;
- forbid test-time LLM updates or hidden reward edits;
- compare against fixed-feature and fixed-reward controls, after costs.

Source: <https://arxiv.org/html/2606.08450v1>

### Correlation-Aware Portfolio Evaluation

PortBench emphasizes full-pipeline portfolio evaluation with explicit
correlation information, stress-regime tests, investor-profile constraints, and
standard risk metrics. For Ginger, the production translation is to score
paper candidates by portfolio displacement and correlation/crowding impact,
not standalone next-open PnL alone.

Implementable fields:

- `candidate_correlation_context_version`
- `intra_sleeve_correlation_bucket`
- `inter_sleeve_correlation_bucket`
- `correlation_adjusted_replacement_value`
- `profile_constraint_alignment_bucket`
- `stress_regime_performance_bucket`
- `portfolio_correlation_penalty_bucket`
- `diversification_budget_remaining`

Controls:

- evaluate candidate additions against the exact displaced candidate or cash;
- include correlation and exposure impact in forward paper ledgers;
- report stress-regime performance separately from normal-market averages;
- do not promote an alpha that wins only by adding crowded beta exposure.

Source: <https://arxiv.org/html/2605.27887v2>

### Constrained Macro-Prior LLM Agents

Recent commodity-related ETF allocation work uses fixed macro evidence tables,
zero-temperature cached outputs, explicit Hawkish/Dovish priors, stationary
bootstrap Sharpe tests, and transaction-cost sensitivity. The local lesson is
that LLMs can be bounded interpreters of a precomputed macro state, but the
prior, evidence table, prompt, output cache, cost model, and benchmark must all
be replayable.

Implementable fields:

- `macro_prior_agent_id`
- `macro_evidence_table_hash`
- `macro_prior_interpretation_bucket`
- `macro_agent_disagreement_bucket`
- `macro_agent_output_cache_hash`
- `macro_tilt_cost_sensitivity_bucket`
- `bootstrap_sharpe_difference_bucket`
- `macro_release_vintage_quality_bucket`

Controls:

- provide only release-aware macro features and no future returns;
- cache all model outputs by date and agent type;
- compare against deterministic rule and passive risk benchmarks;
- report one-way cost sensitivity and multiple-testing caveats.

Source: <https://arxiv.org/html/2606.08283v1>

### Domain-Trained Time-Series Foundation Models

2025-2026 time-series foundation-model papers are useful, but the practical
lesson is not zero-shot forecasting. The stronger pattern is sample-efficient
adaptation or pretraining on financial data, with off-the-shelf zero-shot
models often weaker than domain-specific baselines. For Ginger, this maps to
read-only state embeddings and volatility/risk fields before any ranking or
entry use.

Implementable fields:

- `tsfm_model_family`
- `tsfm_pretraining_domain`
- `tsfm_finetune_window_id`
- `tsfm_zero_shot_vs_domain_delta_bucket`
- `tsfm_volatility_forecast_bucket`
- `tsfm_equity_spread_forecast_bucket`
- `tsfm_embedding_replay_hash`
- `tsfm_after_cost_replacement_value_bucket`

Controls:

- compare zero-shot, fine-tuned, and simple benchmark models separately;
- freeze the model/version and feature window before Gate 1;
- use embeddings first for volatility, drawdown, and state diagnostics;
- require after-cost replacement value before any candidate-pool promotion.

Sources:

- <https://arxiv.org/abs/2507.07296>
- <https://arxiv.org/abs/2511.18578>
- <https://arxiv.org/abs/2505.11163>

### Related-Series Foundation Model Discipline

A May 2026 Chronos-2 finance study found multivariate inputs helped within
related panels such as Magnificent-7 equities or Treasury rates, while mixing
unrelated equity and rate series reduced forecast accuracy. For Ginger, the
implementable lesson is panel selection and noisy-context auditing, not a
zero-shot forecasting shortcut.

Implementable fields:

- `tsfm_related_series_panel_id`
- `tsfm_panel_membership_asof`
- `tsfm_cross_series_context_quality_bucket`
- `tsfm_noisy_context_penalty_bucket`
- `tsfm_rolling_eval_protocol_id`
- `tsfm_horizon_window_grid_id`
- `tsfm_series_level_error_dispersion_bucket`
- `tsfm_related_panel_embedding_hash`

Controls:

- define the related-series panel before evaluation and store membership as of
  each decision date;
- compare multivariate, univariate, and simple baseline forecasts under the
  same rolling protocol;
- reject mixed-context panels when unrelated series reduce accuracy or add beta
  exposure without replacement value;
- use the embedding first for state/risk attribution until after-cost
  candidate displacement is proven.

Source: <https://arxiv.org/abs/2605.21504>

### Limit-Order-Book And Microstructure Reality Check

Recent LOB work reinforces two local rules: market-microstructure features can
carry information, but predictability is fragile after spread, horizon, and
regime changes; realistic queue simulation matters for execution research.
Ginger should not map these papers to daily close-only entry rules. The usable
near-term form is a data-quality and execution-envelope surface around spread,
order-flow imbalance, and stale-price risk.

The June 2026 FastBiNLOB result adds an engineering angle: low-latency binary
network designs may preserve useful short-horizon LOB classification while
reducing inference cost. For Ginger this is only relevant after timestamped LOB
coverage exists; then model latency and stale-quote risk become execution
fields, not new daily ranking features.

Implementable fields:

- `lob_feature_source_id`
- `order_flow_imbalance_bucket`
- `spread_cost_bucket`
- `queue_depth_pressure_bucket`
- `microstructure_horizon_bucket`
- `microstructure_predictability_decay_bucket`
- `execution_queue_model_version`
- `microstructure_model_latency_bucket`
- `lob_snapshot_staleness_bucket`
- `microstructure_cost_adjusted_signal_flag`

Controls:

- use only timestamped intraday/LOB rows available before the intended order;
- define trend labels relative to spread and fees, not raw direction alone;
- keep LOB classifiers out of daily paper alpha until data coverage and
  execution semantics are replayable;
- use queue models first to stress-test fill assumptions and slippage.

Sources:

- <https://arxiv.org/abs/2501.08822>
- <https://arxiv.org/abs/2502.15757>
- <https://arxiv.org/abs/2505.22678>
- <https://arxiv.org/abs/2504.13521>
- <https://arxiv.org/abs/2606.25986>

### Dynamic Relation Graphs Need Edge Provenance

2025 dynamic stock-relationship transformer work again points to time-varying
edges, not static sectors. The useful implementation detail is to evaluate
edge-construction methods separately: Kendall/Spearman/Pearson/mutual
information, global/local scopes, decay, and stability can be fields. The
local anti-repeat remains: a graph model is not alpha if it only propagates
broad beta or stale momentum.

Implementable fields:

- `dynamic_graph_metric_id`
- `dynamic_graph_scope_bucket`
- `edge_metric_family`
- `edge_stability_lookback_bucket`
- `edge_update_timestamp`
- `edge_noise_suppression_method`
- `relation_cluster_volatility_bucket`
- `relation_edge_comparator_delta`

Controls:

- persist every edge matrix with an as-of timestamp and source universe;
- compare edge families by displacement value, not prediction loss alone;
- use relation clusters first for risk/concentration diagnostics;
- require accepted relation-comparator evidence before entry/ranking use.

Source: <https://arxiv.org/abs/2506.18717>

### Event-Aware LLM Labels Are Features, Not Decisions

Recent work using LLM-labeled tweet events supports schema-bound semantic
annotation, especially when labels are aligned to forward returns and published
with reproducible code. The Ginger-compatible version is event-family and
sentiment-intensity labeling with source coverage, timestamp, and comparator
discipline. It does not justify direct LLM buy/sell authority or raw sentiment
averages.

Implementable fields:

- `llm_event_label_schema_version`
- `llm_event_label_source_type`
- `llm_event_sentiment_intensity_bucket`
- `llm_event_label_multiclass_set`
- `llm_event_label_forward_horizon`
- `llm_event_label_ic_bucket`
- `llm_event_label_coverage_fraction`
- `llm_event_label_replacement_value_bucket`

Controls:

- archive source text, model id, schema, and extraction timestamp;
- separate event label, sentiment strength, and source credibility;
- require negative controls and after-cost comparator tests before paper use;
- treat social/news labels as noisy until forward replacement rows mature.

Source: <https://arxiv.org/abs/2508.07408>

### Financial ML Falsification Audit

April 2026 work on spurious predictability in financial ML is directly aligned
with Ginger's frozen-window failures: adaptive specification search can create
apparently significant backtests even when the data-generating process has no
true predictability. The local use is a falsification audit around broad scouts
and high-dimensional candidate generation, not a new alpha model.

Implementable fields:

- `falsification_audit_protocol_id`
- `induced_null_reference_class`
- `microstructure_placebo_passed`
- `workflow_effective_multiplicity`
- `backtest_inflation_factor`
- `walk_forward_gap_bucket`
- `null_environment_signal_rate`
- `selection_induced_inflation_bucket`

Controls:

- run induced-null and placebo checks before accepting broad ML/LLM candidate
  searches;
- report the effective number of tried specifications, not only the final
  winning replay;
- treat success under the null as pipeline invalidity, not as a robust signal;
- forbid threshold sweeps unless the retry adds a materially new
  production-visible field.

Source: <https://arxiv.org/abs/2604.15531>

### Executable Quant LLM Benchmarks

QuantEval's 2026 benchmark design is useful because it evaluates LLMs on
quantitative knowledge, reasoning, strategy coding, and deterministic strategy
backtests. The compatible Ginger lesson is that LLM strategy ideas should
become frozen code, test fixtures, and replay artifacts before any Gate 1-4
evidence is counted.

Implementable fields:

- `llm_strategy_code_hash`
- `llm_generated_strategy_test_protocol`
- `llm_backtest_config_hash`
- `llm_strategy_human_review_status`
- `llm_strategy_execution_cost_model`
- `llm_strategy_invalid_action_count`
- `llm_quant_reasoning_failure_bucket`

Controls:

- freeze LLM-generated code and configuration before the first after-run;
- compare against deterministic baselines and accepted local comparators after
  costs;
- log compile, schema, invalid-action, and reasoning failures instead of
  silently repairing them;
- keep the LLM in idea-generation or field-construction mode unless a shared
  policy helper passes Gate 1-4.

Source: <https://arxiv.org/abs/2601.08689>

### Deterministic Numeric Extraction Around LLMs

FinSheet-Bench shows that financial spreadsheet and table reasoning remains a
material failure mode for LLMs, especially when tasks move beyond simple
lookups. For Ginger's SEC, filings, and companyfacts work, the conclusion is
simple: LLMs may help locate or classify evidence, but arithmetic, joins,
period matching, and PIT fact validation must be deterministic.

Implementable fields:

- `numeric_extraction_parser_version`
- `numeric_source_table_hash`
- `llm_numeric_claim_self_check_passed`
- `deterministic_recompute_delta_bucket`
- `filing_fact_join_confidence_bucket`
- `table_layout_complexity_bucket`
- `spreadsheet_reasoning_risk_bucket`

Controls:

- archive the source table, filing span, fact taxonomy, and parser version;
- reject candidate rows when deterministic recomputation disagrees with the
  LLM-produced numeric claim;
- separate "span found" from "number computed" in all evidence ledgers;
- require PIT period matching before any extracted numeric field affects
  candidate pools, ranks, or risk.

Source: <https://arxiv.org/abs/2603.07316>

### SEC Multi-Document Reasoning Error Taxonomy

Fin-RATE benchmarks SEC filing workflows across single-disclosure reasoning,
cross-entity comparison, and longitudinal firm tracking, and reports material
accuracy drops when models move beyond one document. The actionable lesson is
to classify SEC semantic failures before using them as alpha fields: retrieval
miss, period mismatch, entity mismatch, comparison hallucination, and reasoning
failure are different defects with different fixes.

Implementable fields:

- `sec_reasoning_task_type`
- `sec_retrieval_failure_bucket`
- `sec_entity_match_confidence`
- `sec_period_alignment_confidence`
- `sec_cross_entity_comparison_id`
- `sec_longitudinal_tracking_version`
- `sec_comparison_hallucination_flag`
- `sec_reasoning_failure_bucket`

Controls:

- store accession, period, entity, and comparison peer ids for every semantic
  field;
- fail closed when the retrieved document set does not cover the requested
  entity-period pair;
- evaluate cross-entity and longitudinal labels separately from single-filing
  labels;
- compare any SEC semantic candidate against accepted SEC RS20 and non-text
  comparators after costs.

Source: <https://arxiv.org/abs/2602.07294>

### Financial Statement Verification Calibration

FinVerBench separates financial statement verification from answer generation:
models must detect cross-statement inconsistencies under controlled numeric
perturbations. Its calibration result is directly relevant to Companyfacts and
SEC text work: a model can be over-sensitive to clean statements or fragile to
rounding/rendering choices. Deterministic recomputation remains mandatory.

Implementable fields:

- `statement_verification_protocol_id`
- `cross_statement_constraint_id`
- `numeric_perturbation_magnitude_bucket`
- `observable_field_coverage_bucket`
- `llm_false_positive_clean_statement_rate`
- `rounding_rendering_sensitivity_bucket`
- `deterministic_constraint_check_passed`
- `verification_calibration_bucket`

Controls:

- let deterministic parsers own arithmetic, period matching, and constraints;
- use LLMs only to explain or classify verified inconsistencies;
- preserve clean-instance false positive rates before turning any
  inconsistency label into an alpha field;
- distinguish missing/hidden fields from true inconsistencies.

Source: <https://arxiv.org/abs/2605.29586>

### Layout-Faithful EDGAR Filing Data

The June 2026 Stanford EDGAR Filings Dataset reconstructs SEC filings into
layout-faithful, token-efficient MultiMarkdown and adds EDGAR-Forecast /
EDGAR-OCR benchmarks. For Ginger, this points to a concrete data-engineering
surface: store accession-bounded filing text with layout/table provenance so
LLM labels, deterministic parsers, and numeric joins can be replayed from the
same source artifact.

Implementable fields:

- `edgar_layout_source_version`
- `filing_multimarkdown_hash`
- `filing_table_layout_confidence_bucket`
- `filing_section_span_id`
- `filing_numeric_table_source_hash`
- `edgar_forecast_protocol_id`
- `edgar_ocr_risk_bucket`
- `filing_source_artifact_overlap_bucket`

Controls:

- key every filing artifact by accession, accepted timestamp, form, and source
  parser version;
- preserve table and section spans before any LLM classification or numeric
  extraction;
- use post-cutoff / PIT protocols for filing-grounded forecasts;
- treat layout/OCR uncertainty as a fail-closed field for candidate pools.

Source: <https://arxiv.org/abs/2606.18192>

### Enforcement-Grounded Misleading Narrative Signals

AuditFraudBench adds a useful SEC semantic target: misleading narratives can be
plausible and internally consistent while obscuring true performance drivers.
The local translation is not direct fraud trading; it is a high-risk context
field around source-of-profit attribution, narrative distortion, and
restatement/AAER-grounded mechanism labels.

Implementable fields:

- `fraud_narrative_schema_version`
- `profit_source_attribution_bucket`
- `management_explanation_mismatch_flag`
- `misleading_narrative_risk_bucket`
- `fraud_pattern_category`
- `aaer_mechanism_source_id`
- `restatement_pair_id`
- `disclosure_omission_context_bucket`

Controls:

- use enforcement/restatement data only with correct filing-time boundaries:
  ex-post AAER labels are training/benchmark labels, not live features;
- separate contemporaneous disclosure-risk scoring from future enforcement
  knowledge;
- start as risk/explanation attribution, not entry alpha;
- require archived evidence spans and deterministic numeric checks before any
  paper candidate use.

Source: <https://arxiv.org/abs/2606.08345>

### Structured Event Representation For Text Alpha

Recent structured-event stock-prediction work supports an important boundary:
text is more useful when converted into explicit event tuples than when treated
as raw sentiment. This matches Ginger's repeated SEC text failures. The next
valid text retry should encode actors, objects, relation type, magnitude,
horizon, and source provenance, then compare against accepted SEC/event
comparators.

Implementable fields:

- `structured_event_schema_version`
- `event_actor_type`
- `event_object_type`
- `event_relation_type`
- `event_magnitude_bucket`
- `event_horizon_bucket`
- `event_attention_attribution_bucket`
- `event_replacement_value_bucket`

Controls:

- store schema-bound event tuples with source id, timestamp, and evidence
  spans;
- separate semantic direction, magnitude, and uncertainty from raw positive or
  negative sentiment;
- benchmark structured text fields against accepted SEC RS20, relation, and
  allocator comparators after costs;
- reject text alphas whose event tuple cannot be replayed from archived source
  material.

Source: <https://arxiv.org/abs/2512.19484>

### Grounded 8-K Taxonomies Beat Item-Code Enumeration

A July 2026 grounded 8-K extraction paper is directly relevant to Ginger's
repeated SEC item-code failures. The useful result is not "use an LLM label";
it is the data contract: constrain labels to a fine taxonomy, anchor each label
to a source quote, validate the quote against the filing text, then score the
tag in a second pass. The paper reports that quality scores separate reliable
from unsupported tags and that a fine taxonomy separates economically different
events hidden under the same coarse 8-K item code. Ginger should treat this as
a replacement for item-code loops, not another SEC text threshold.

Implementable fields:

- `sec8k_event_taxonomy_version`
- `sec8k_event_tier1`
- `sec8k_event_tier2`
- `sec8k_event_tier3`
- `sec8k_evidence_quote_hash`
- `sec8k_quote_fuzzy_match_score`
- `sec8k_second_pass_quality_score`
- `sec8k_unsupported_tag_flag`
- `sec8k_unsigned_abnormal_return_bucket`

Controls:

- require accession, accepted timestamp, item code, source span, and quote hash
  before scoring outcomes;
- fail closed when the quoted evidence cannot be found in the archived filing;
- evaluate taxonomy buckets against accepted SEC/event comparators after costs;
- batch fine-grained event families instead of reserving one ID per 8-K item or
  event subtype.

Source: <https://arxiv.org/abs/2607.08346>

### SEC And Earnings-Call Target Stance Needs Metric-Level Labels

Recent SEC filing and earnings-call stance work argues for sentence-level
labels tied to explicit financial targets such as debt, EPS, and sales. That
maps better to Ginger than broad sentiment because each label can carry a
target metric, evidence span, filing/call timestamp, and stance direction. The
field should start as context and event-quality attribution; it becomes alpha
only if a shared helper can replay the same target-stance rows and beat
accepted SEC/event comparators after costs.

Implementable fields:

- `financial_target_stance_schema_version`
- `target_metric_family`
- `target_metric_value_context`
- `target_stance_direction`
- `target_stance_confidence_bucket`
- `target_stance_source_type`
- `target_stance_evidence_span_hash`
- `target_stance_llm_prompt_version`
- `target_stance_replacement_value_bucket`

Controls:

- label the target metric separately from generic positive/negative tone;
- require accepted filing/call timestamps and evidence spans;
- validate numeric context with deterministic extraction before scoring;
- benchmark target-stance rows against accepted SEC financial-report and
  structured-event comparators.

Source: <https://arxiv.org/abs/2510.23464>

### Options Surface As Risk And Execution Context

Recent options research still maps better to risk/execution context than to
daily equity alpha. A 2025 SPXW put-writing study emphasizes regime-aware
position sizing and drawdown control, while 2026 volatility-surface and
synthetic American-option work reinforces that skew/term-structure fitting is
model- and market-specific. Older option-volume imbalance evidence is still
useful because it points to participant class and high-IV contract slices as
the place where equity-return information may live. The synthetic-options
result is especially useful as a stress-test pattern: scheduled event distance
and same-sector coupling can dominate generalization error in option surfaces.
For Ginger, options rows should first become timestamped risk, crowding,
event-distance, participant/IV-slice, and execution-envelope fields. They
should not be accepted as fixed-window equity alpha until historical chain
coverage, stale-chain controls, participant/source provenance, and fill costs
are replayable.

Implementable fields:

- `options_surface_snapshot_asof`
- `iv_skew_model_version`
- `iv_term_structure_bucket`
- `option_liquidity_cost_bucket`
- `vol_regime_sizing_bucket`
- `options_chain_stale_flag`
- `options_event_distance_bucket`
- `same_sector_option_coupling_bucket`
- `option_volume_imbalance_bucket`
- `option_participant_class_bucket`
- `high_iv_option_flow_bucket`
- `option_signal_costed_replacement_value`
- `options_tail_risk_context_bucket`

Controls:

- store quote timestamp, expiration, strike/moneyness, bid/ask/mid, open
  interest, and stale-chain status before any signal use;
- start with risk sizing, tail context, and execution-envelope diagnostics;
- do not use put/call or volume-imbalance rows without source/participant
  provenance, IV bucket, stale-chain status, and fill-cost controls;
- require fixed-window or forward ledger coverage with publication/fill-cost
  controls before candidate-pool use;
- compare options-assisted rows against accepted non-options comparators after
  costs and drawdown.

Sources:

- <https://arxiv.org/abs/2508.16598>
- <https://arxiv.org/abs/2603.27501>
- <https://arxiv.org/abs/2605.13998>
- <https://arxiv.org/abs/2201.09319>

### 13F Is Delayed Ownership And Crowding Context

13F research and disclosure rules make the timing caveat explicit: filings are
quarterly and delayed, omit shorts, and can encode crowding or already-consumed
information rather than fresh sponsorship. This matches the June 13 local
failures for 13F sponsorship acceleration and new-holder initiation. The first
production use should be attribution, crowding, and overhang context; direct
entry alpha needs a new timing edge.

Implementable fields:

- `sec13f_report_period`
- `sec13f_filed_at`
- `sec13f_reporting_delay_days`
- `sec13f_holder_count_delta_bucket`
- `sec13f_position_imbalance_bucket`
- `sec13f_crowding_risk_bucket`
- `sec13f_contrarian_pressure_bucket`
- `sec13f_disclosure_timing_edge_bucket`

Controls:

- use filing timestamp, not report-period end, as the earliest decision time;
- never infer short exposure from 13F holdings;
- measure crowding/contrarian value separately from sponsorship narratives;
- require direct comparison against accepted relation/allocator sources before
  treating 13F as a candidate-pool source.

Sources:

- <https://arxiv.org/abs/2209.08825>
- <https://www.sec.gov/divisions/investment/13ffaq>

### 13D / 13G Beneficial Ownership Needs Structured Primary Text

The SEC's beneficial-ownership modernization shortened Schedule 13D timing,
accelerated Schedule 13G deadlines, clarified derivative-security disclosure,
and made Schedule 13D/G structured machine-readable filing mandatory from
December 18, 2024. This directly maps to Ginger's June 18 blocker: raw
submissions metadata has many 13D/13G accessions, but no local primary-text or
holder/stake/action table. The research/production opportunity is not another
form-code event replay; it is a PIT parser for ownership intent and action.

Implementable fields:

- `sec13dg_accession`
- `sec13dg_accepted_at`
- `sec13dg_form_type`
- `sec13dg_holder_identity_hash`
- `sec13dg_holder_entity_type`
- `sec13dg_beneficial_ownership_pct`
- `sec13dg_share_count`
- `sec13dg_active_passive_intent_bucket`
- `sec13dg_action_direction_bucket`
- `sec13dg_derivative_context_bucket`
- `sec13dg_structured_data_version`

Controls:

- use accepted timestamp and primary-document text as the decision-time bound;
- fail closed when holder identity, ownership percent, or action direction is
  missing;
- separate active 13D control intent from passive/institutional 13G reporting;
- compare against accepted relation/allocator/SEC comparators after costs;
- expose the same parser in historical replay and daily default-off snapshots.

Sources:

- <https://www.sec.gov/newsroom/press-releases/2023-219>
- <https://www.sec.gov/files/rules/final/2023/33-11253.pdf>

### 10-K Narrative Distress As Risk Context

Recent bankruptcy-prediction work finds that distress-specific 10-K narrative
language can add interpretable warning power beyond accounting variables. The
Ginger-compatible use is a risk/context field around liquidity, funding,
refinancing, restructuring, and business-fragility language. It should not be
used as a raw short/long entry label without archived filing text, period
alignment, and replacement-value evidence.

Implementable fields:

- `pb_stress_score_version`
- `liquidity_funding_stress_bucket`
- `debt_refinancing_stress_bucket`
- `covenant_pressure_bucket`
- `restructuring_legal_distress_bucket`
- `business_fragility_language_bucket`
- `distress_language_source_accession`
- `distress_context_replacement_value_bucket`

Controls:

- score only filings accepted before the candidate decision;
- separate bankruptcy/risk monitoring from entry alpha;
- require deterministic section extraction and evidence spans;
- compare distress-context filters against accepted SEC/event comparators after
  costs before any paper-sleeve use.

Source: <https://arxiv.org/abs/2606.05623>

### Intangible Investment And Advertising Efficiency Discipline

Recent asset-pricing work supports the idea that intangible investment matters
more in the modern market, especially for intangible-intensive firms. Ginger's
June 18 advertising-efficiency experiment shows the practical trap: raw
selling/marketing or advertising ratios can be directionally interesting but
still fail window, drawdown, concentration, and accepted-comparator gates. The
usable path is a richer PIT unit-economics surface, not another expense/revenue
threshold.

Implementable fields:

- `intangible_intensity_bucket`
- `advertising_intensity_bucket`
- `sales_marketing_efficiency_bucket`
- `customer_acquisition_efficiency_source`
- `gross_margin_supported_growth_bucket`
- `segment_sales_productivity_bucket`
- `unit_economics_evidence_bucket`
- `intangible_investment_replacement_value_bucket`

Controls:

- normalize by industry and business model before comparing candidates;
- distinguish R&D, advertising, and broader selling/marketing spend;
- require positive revenue/gross-margin context plus PIT filing freshness;
- demand accepted-comparator improvement after costs before treating the field
  as candidate-pool alpha.

Source: <https://arxiv.org/abs/2505.16336>

### Short-Trend Alpha Needs Microstructure Viability

A July 2026 q-fin study argues that short-horizon trend following degraded
after 2009 mostly where the volatility-normalized tick size is small: trend
PnL collapsed in small-tick contracts but survived better in large-tick
contracts. The Ginger translation is not another momentum threshold. It is to
treat short-trend, breakout, and compression continuations as execution
microstructure hypotheses: the same price pattern may be viable only when tick
size, spread, depth proxy, and impact costs support aggressive execution.

Implementable fields:

- `vol_normalized_tick_size_bucket`
- `spread_to_atr_bucket`
- `dollar_depth_proxy_bucket`
- `trend_signal_speed_bucket`
- `impact_reinforcement_viability_flag`
- `small_tick_trend_decay_risk_bucket`
- `microstructure_cost_scenario_id`
- `trend_after_cost_replacement_value`

Controls:

- stratify any short-trend or breakout replay by tick/spread/impact buckets;
- compare against the same accepted helper after realistic next-open and
  spread costs;
- treat small-tick positive gross momentum as execution-risk context until
  after-cost replacement value clears;
- avoid retuning momentum labels without a new PIT microstructure field.

Source: <https://arxiv.org/abs/2607.01550>

### Order-Flow Impact Is A Liquidity State, Not Raw Flow Alpha

A July 2026 paper estimates Kyle-style price impact from daily equity order
flow and reports that signed order flow predicts contemporaneous and
one-month-ahead returns, while volume volatility predicts weaker subsequent
returns. This is directly relevant to Ginger's Moomoo main-flow failures: raw
inflow labels are too blunt unless they are tied to a PIT impact estimate,
publication timing, horizon, and costed displacement comparator. A second July
2026 square-root-impact study adds an execution-control lesson: impact shape is
not just visible book depth or metaorder size, but the joint presence of order
splitting and liquidity replenishment. Flow rows therefore need an execution
mechanism tag before they can support sizing or entry changes.

Implementable fields:

- `signed_order_flow_bucket`
- `kyle_lambda_estimator_version`
- `amihud_impact_bucket`
- `volume_volatility_bucket`
- `impact_normalization_horizon`
- `flow_publication_lag_bucket`
- `order_splitting_proxy_bucket`
- `liquidity_replenishment_proxy_bucket`
- `flow_impact_reversion_context`
- `flow_after_cost_replacement_value`

Controls:

- estimate impact only from data available before the decision date;
- lock the horizon before scoring flow rows, especially 10d versus one-month;
- compare flow rows against cash, SPY/QQQ, and accepted allocator/distribution
  sources after costs;
- separate flow direction from impact capacity and replenishment context;
- do not retry raw main-flow thresholds without a new PIT impact or borrow /
  loan-availability field.

Sources:

- <https://arxiv.org/abs/2607.01377>
- <https://arxiv.org/abs/2607.04280>

### Learning-Agent Impact Cycles Are Stress Tests, Not Alpha

A July 2026 learning-agent market-impact study reports endogenous manipulation
cycles when an optimized institutional agent interacts with herding flow under
square-root impact. Ginger should not translate this into a trading target.
The useful lesson is adversarial: allocator, execution, and liquidity overlays
must be stress-tested for self-reinforcing flow, repeated same-direction
entries, and impact feedback before live capital grows.

Implementable fields:

- `impact_feedback_stress_protocol_id`
- `same_direction_entry_cycle_count`
- `self_excited_flow_risk_bucket`
- `herding_flow_proxy_bucket`
- `impact_cycle_drawdown_bucket`
- `allocator_flow_reversal_latency`
- `liquidity_feedback_kill_switch_flag`

Controls:

- treat square-root impact and flow feedback as execution-envelope stress, not
  candidate-pool alpha;
- check whether repeated helper entries create same-ticker or same-theme flow
  cycles before increasing notional;
- require kill-switch behavior under stressed impact scenarios, especially for
  accepted paper adapters moving toward activation;
- keep any agent-discovered execution policy default-off until a deterministic
  shared policy and Gate 1-4 / Gate 5 evidence exist.

Source: <https://arxiv.org/abs/2607.05141>

### MACD-Style Signals Need Latent-Drift And Cost Context

New mathematical-finance work derives MACD-like signals from filtered latent
drift with fast and slow factors. The useful local lesson is narrow: MACD is a
state estimator, not an independent alpha license. Any revival of trend
indicators should log the fast/slow factor spread, signal half-life, and
execution envelope, then prove incremental replacement value over existing
trend and accepted default-off helpers.

Implementable fields:

- `latent_drift_filter_version`
- `fast_slow_ema_spread_bucket`
- `signal_half_life_bucket`
- `volterra_correction_bucket`
- `trend_state_confidence_bucket`
- `macd_placebo_delta`
- `latent_drift_after_cost_replacement_value`

Controls:

- compare MACD-style features to simple momentum, current trend helpers, and
  accepted paper adapters on the same dates;
- predeclare fast/slow windows and cost assumptions before replay;
- use the signal first as state/risk context unless Gate 1-4 proves an entry,
  ranking, or sizing change;
- do not sweep EMA windows on frozen rows without a new evidence axis.

Source: <https://arxiv.org/abs/2607.01705>

### Factor Models Need Cap-Axis Diagnostics

A July 2026 factor-model diagnostic shows that a low-dimensional model can
improve the maximum-Sharpe frontier while still leaving pricing errors along
the market-cap rank axis. Ginger should apply the same idea to broad-universe
and factor-like candidate pools: a positive aggregate EV or Sharpe is not
enough if the result is just hidden large-cap / small-cap bridge alpha.

Implementable fields:

- `cap_rank_bucket`
- `cap_axis_bridge_alpha_curve`
- `cap_axis_norm`
- `lead_lag_corrected_cap_alpha`
- `factor_size_exposure_bucket`
- `cap_subspace_zero_alpha_passed`
- `cap_axis_replacement_value_delta`

Controls:

- report candidate performance by market-cap rank bucket before promoting
  broad factor or universe-expansion sources;
- compare cap-axis behavior against SPY/QQQ, static size/style alternatives,
  and accepted default-off comparators;
- distinguish Sharpe improvement from residual cap-subspace alpha;
- reject broad sources whose edge vanishes after cap-axis and lead-lag checks.

Source: <https://arxiv.org/abs/2607.01765>
