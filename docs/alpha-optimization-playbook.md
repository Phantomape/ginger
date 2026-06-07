# Alpha Optimization Playbook

Last refreshed: 2026-06-07.

This is Ginger's long-lived alpha research playbook. It is not an experiment
log. Detailed trial records belong in `docs/experiment_log.jsonl`,
`experiments/logs/*.json`, experiment cards, and artifacts. This file keeps the
durable mechanism lessons, frozen retry zones, research queue, and external
research ideas that can be converted into replayable fields.

For default LLM context, start with `docs/alpha_context_pack.md`, then
`docs/current_state_snapshot.md` when current-state orientation is needed.
These are generated short memory surfaces; this playbook remains the durable
policy and research-prior reference. Mechanism-specific short lessons live
under `docs/lessons/*.md` and should be refreshed with:

```powershell
.\.venv\Scripts\python.exe -B scripts\build_alpha_memory.py --git-ref HEAD
```

North-star metric:

```text
expected_value_score = strategy_total_return_pct * sharpe_daily
```

## Operating Rules

Before strategy-affecting work, answer:

1. What is the alpha hypothesis, and is it entry, exit, ranking, capital
   allocation, candidate-pool, LLM event scoring, or risk allocation?
2. Has the same or adjacent family been tried before, and what failed?
3. What is the one changed decision hypothesis or fixed policy bundle, and
   which edits are only implementation/parity/live-realism work needed to
   evaluate it?
4. What Gate 1-4 standard from `docs/backtesting.md` decides acceptance?
5. If it fails, can the next agent reproduce the trial from repository records?

Priority rules:

- Prefer `alpha_search` unless a measurement gap directly blocks a high-value
  alpha test.
- Prefer new production-visible fields over threshold/scalar sweeps.
- Prefer default-off paper adapters before core or live expansion.
- For any alpha that may become live-capital eligible, include the live-realistic
  execution envelope in the experiment rather than postponing it: notional,
  capital cap, liquidity/slippage, portfolio displacement, exposure limits,
  kill switch, and order semantics.
- Prefer replacement value against the displaced candidate over standalone PnL.
- Prefer shared-paper-first experiments for high-potential default-off paper
  alpha: the first serious test should use a shared historical replay plus daily
  snapshot helper, not private runner-only selection code.
- Prefer shared production/backtest policy over replay-only logic. A positive
  private replay scout is only a lead until a shared helper reproduces it.
- Treat high aggregate EV with window regression or drawdown drift as a rejected
  clue, not as a retained strategy.

## Current Readout

The strongest current pattern is not more filters. It is:

1. find broad, cheap, point-in-time candidate sources;
2. when the idea is credible, test it through a shared-paper-first helper that
   can drive both historical replay and daily default-off snapshots;
3. define the live-realistic execution envelope early, even while
   `trade_enabled=false`;
4. collect closed forward replacement-value rows under that envelope;
5. if the envelope was already measured and remains unchanged, live enablement
   is a release checklist/config change; otherwise run only a narrow
   activation-envelope Gate 1-4, not a new alpha search.

Private replay scouts should be reserved for uncertain data-shape discovery or
very speculative ideas. They should not be treated as accepted alpha even when
Gate 4 is positive; the next retained asset must be the shared helper or daily
default-off wiring that reproduces the lead.

Meta-research on 1,482 records continues to rank production-visible default-off
paper adapters above raw filters, ticker exceptions, and cap releases. The
research report is queue guidance only; it is not a trading signal.

The June 6-7 readout tightens the rule: relation-aware free-data candidate
sources can work, but only when the relation itself is the edge. Accepted
examples use macro-event relief, rolling-correlation peer shock with core-flow
confirmation, or industry-relative laggard repair. Rejected neighbors show what
does not count as a new relation: sector ETF laggards, core-selected anchor peer
lags with zero target trades, short-horizon reversal/reclaim, macro sector
confirmation that fails versus the accepted comparator, and SEC guidance/outlook
phrase matching with same-day price alignment. These are mostly weak
confirmers, not new information.

Default next question for any new broad candidate pool:

- what exact relation makes this ticker a better replacement than cash, ETF
  substitute, or the already accepted default-off comparator;
- whether the relation is point-in-time and production-visible;
- whether the candidate improves all windows against the accepted comparator,
  not only against the core baseline;
- whether the result survives costs, concentration, and drawdown before any
  notional, top-N, hold-day, or cooldown tuning.

## Accepted Mechanisms To Build Around

### Low-Deployment ETF Cash Substitute

This is the clearest current capital-allocation lead. When the core stack has
at most one active position, a narrow ETF basket can replace idle cash without
changing core entries.

Accepted shared adapter: `exp-20260606-001`.

Mechanism:

- state: `active_core_positions <= 1`;
- candidates: `QQQ`, `SPY`, `IWM`, `GLD`, `SLV`;
- gates: exact signal-date close above SMA200 and positive 20-session momentum;
- selection: top 20-session momentum candidate;
- lifecycle: one pending/open ETF paper position, next-open entry,
  10-trading-day exit, costs and slippage included;
- status: default-off paper only, no live orders.

Evidence:

- aggregate EV `7.8941 -> 10.9233` (`+38.37%`);
- PnL `$234,850.99 -> $279,157.90`;
- all three canonical windows improved;
- target paper trades: `19`;
- max drawdown delta `-0.0008`;
- concentration passed.

Next valid work:

- closed forward replacement-value rows under the shared ledger;
- explicit cash semantics and portfolio-level capital cap;
- kill switch based on drawdown, realized volatility, and ETF concentration;
- live enablement only after the same cash semantics, cap, and kill switch are
  measured under an activation envelope; if already measured, release can be a
  checklist/config change rather than a new alpha search.

Do not retune nearby ETF list, momentum threshold, SMA window, hold days,
notional, or scalar on the frozen sample.

### Macro Relief Stock Leadership

This is a free-data candidate-pool lead tied to official macro event days. When
official CPI/FOMC/NFP days produce broad risk relief, the strongest liquid stock
leaders can be tracked as default-off paper candidates.

Accepted shared adapter: `exp-20260606-020`, promoting the positive replay lead
from `exp-20260606-019`.

Mechanism:

- official event families: `CPI`, `FOMC`, `NFP`;
- macro relief gate: same-day `SPY` and `QQQ` rally and close high in range;
- source universe: broad-market, sector-known, liquid stock observation feed;
- selection: up to top-2 same-day stock leaders;
- lifecycle: next-open paper entry, 10-trading-day close exit, costs included;
- status: default-off paper only, no live orders.

Evidence:

- aggregate EV `7.8941 -> 8.0754` (`+0.1813`);
- PnL `$234,850.99 -> $237,913.77`;
- all three canonical windows improved;
- target paper trades: `20`;
- max drawdown drift: `0.0000`;
- concentration passed (`max_single_positive_pnl_share=0.160712`,
  `positive_pnl_hhi=0.10744`).

Next valid work:

- collect closed forward replacement-value rows from the shared adapter;
- audit production universe coverage versus the broad warehouse source;
- add a true point-in-time macro-surprise/consensus field if a free source is
  found;
- before live deployment, either measure the full execution envelope
  (notional/cap/liquidity/slippage/displacement/kill switch/order semantics) or
  release through checklist if that envelope has already been accepted.

Do not retune nearby top-N, SPY/QQQ relief thresholds, close-location
thresholds, hold days, same-ticker cooldown, or paper notional on the frozen
sample.

### Rolling-Correlation Peer-Shock Core Flow

This is a free-OHLCV candidate-pool lead. On days when the core A/B stack has
selected entries, a strong peer shock can identify a correlated liquid laggard
that has begun reacting but has not yet fully caught up.

Accepted shared adapter: `exp-20260606-025`, promoting the positive replay lead
from `exp-20260606-024`. Daily default-off forward wiring was accepted in
`exp-20260606-026`.

Mechanism:

- source universe: broad-market, sector-known, liquid stock observation feed;
- confirmation: same-day selected core A/B entry flow;
- peer event: strong signal-day peer return, relative return versus `SPY`,
  volume confirmation, and 20-day excess return;
- laggard pair: 60-prior-trading-day rolling return correlation to the shocked
  peer;
- candidate gate: positive signal-day laggard return, no selected-core
  same-ticker overlap;
- lifecycle: top-1/day, fixed `$4,000` paper notional, next-open paper entry,
  10-trading-day close exit, costs included;
- status: default-off paper only, no live orders.

Evidence:

- aggregate EV `7.8941 -> 8.2786` (`+0.3845`);
- PnL `$234,850.99 -> $240,958.65`;
- all three canonical windows improved;
- target paper trades: `48`;
- max drawdown drift: `0.0010`;
- concentration passed (`max_single_positive_pnl_share=0.12189`,
  `positive_pnl_hhi=0.056595`).

Next valid work:

- collect closed forward replacement-value rows from the daily default-off
  adapter;
- audit broad-market sector coverage and missing OHLCV rows;
- search for a genuinely point-in-time peer/industry classification or
  low-latency peer-news field if free data exists;
- before live deployment, either measure the full execution envelope
  (notional/cap/liquidity/slippage/displacement/kill switch/order semantics) or
  release through checklist if that envelope has already been accepted.

Do not retune nearby correlation thresholds, core-flow admission, top-N, hold
days, same-ticker cooldown, or paper notional on the frozen sample.

### Industry-Relative Laggard Repair

This is a free-OHLCV candidate-pool lead. In liquid industry groups that are
already showing 20-day relative strength, a stock that lagged the group but
reclaims relative strength on the signal day can be tracked as a catch-up
candidate without simply adding noisy broad-universe momentum names.

Accepted shared adapter: `exp-20260607-008`, promoting the positive replay lead
from `exp-20260607-007`.

Mechanism:

- source universe: broad-market, sector-known, liquid stock observation feed;
- grouping: persisted public industry label, falling back to sector;
- group gate: positive group 20-day excess return versus `SPY`, sufficient
  positive-member breadth, and non-broken 5-day group context;
- candidate gate: 20-day lag versus group, non-broken 60-day trend, positive
  same-day reclaim versus `SPY`, close-location, volume, and volatility guards;
- lifecycle: top-1/day, fixed `$4,000` paper notional, next-open paper entry,
  10-trading-day close exit, costs included, and 15-trading-day same-ticker
  cooldown;
- status: default-off paper only, no live orders.

Evidence:

- aggregate EV `7.8941 -> 8.1704` (`+0.2763`);
- PnL `$234,850.99 -> $241,059.98`;
- all three canonical windows improved;
- target paper trades: `306`;
- max drawdown drift: `0.0021`;
- shared adapter reproduced the private replay lead with zero EV/PnL/trade
  drift.

Next valid work:

- collect closed forward replacement-value rows from the shared adapter;
- audit industry/sector coverage and missing OHLCV rows in the broad-market
  feed;
- search for a genuinely point-in-time peer/industry classification or
  low-latency industry news/event field if free data exists;
- before live deployment, either measure the full execution envelope
  (notional/cap/liquidity/slippage/displacement/kill switch/order semantics) or
  release through checklist if that envelope has already been accepted.

Do not retune nearby industry lag, group-strength, signal-day reclaim, top-N,
hold days, same-ticker cooldown, or paper notional on the frozen sample.

### Lagged Independent Free-Data Consensus

The accepted consensus route is that a current accepted-source paper candidate
is cleaner when a different independent source family confirmed the same ticker
during the prior three trading days.

Accepted adapter: `exp-20260604-009`.

Mechanism:

- count independent source families, not raw source rows;
- collapse related FINRA/IWM and FINRA borrow-pressure signals into one
  `finra_short_pressure` family;
- require lagged independent-family confirmation within the prior three trading
  days;
- keep live/default orders disabled.

Evidence:

- aggregate EV `7.8941 -> 9.8890`;
- PnL `$234,850.99 -> $270,404.86`;
- beat the older same-day consensus comparator by `+0.6891` EV and
  `+$12,156.11`.

Next valid work:

- forward replacement value versus the accepted lagged comparator;
- replay-vs-forward parity audit;
- genuinely new independent data source or timing construction.

Do not retry broad-market leadership, SEC text-price alignment, Form 4,
theme-density, cost/liquidity, prior Companyfacts support, same-sector SEC
propagation, or VCP source expansion as nearby consensus variants on the frozen
windows.

### SEC FTD Plus FINRA Borrow Pressure

Publication-lagged SEC fails-to-deliver data becomes materially more useful
when confirmed by PIT-safe FINRA borrow-pressure state.

Accepted adapter: `exp-20260604-027`.

Mechanism:

- SEC FTD rows are usable only after publication-date gating;
- fixed FTD pressure gates: share count, notional, ADV-normalized pressure, and
  publication age;
- latest FINRA row must have `days_to_cover >= 3.0` and positive
  `short_interest_change_pct`;
- block same-day selected core ticker overlap;
- next-open paper entry, 10-trading-day exit, fixed paper notional.

Evidence:

- aggregate EV `+0.4420`;
- PnL `+$10,100.49`;
- `121` target paper trades;
- all canonical windows improved and concentration passed.

Next valid work:

- closed forward replacement-value rows;
- replay-vs-forward parity audit;
- a real PIT borrow-cost or loan-availability field.

Do not retune SEC FTD thresholds, FINRA thresholds, top-N, hold days, notional,
or cooldown on the frozen sample.

### FINRA/IWM Borrow-Pressure Paper Sleeve

Short-pressure breakouts are cleaner when market appetite and borrow pressure
both confirm.

Accepted adapter: `exp-20260603-007`.

Mechanism:

- FINRA/IWM confirmation plus seven-calendar-day same-ticker cooldown;
- latest PIT-safe FINRA row requires `days_to_cover >= 3.0` and positive
  `short_interest_change_pct`;
- cost/liquidity support remains metadata/paper support only.

Evidence:

- aggregate EV `+0.2585`;
- PnL `+$5,688.12`;
- `22` target paper trades;
- all windows improved.

Next valid work is forward replacement evidence or a true borrow-cost /
availability source, not nearby threshold retuning.

### Post-Earnings Underpriced Drift

The core baseline now uses explicit PIT-safe post-earnings continuation
semantics. Earnings alpha is useful only when the event timing is explicit and
the candidate is underpriced before the event, not as generic PEAD chasing.

Accepted core repair: `exp-20260602-003`.

Accepted default-off adapter: `exp-20260602-026`, with bounded support fields
from `exp-20260602-027`, `exp-20260603-004`, and `exp-20260603-022`.

Mechanism:

- same-day post-event state is valid only after actual EPS is known and a later
  future earnings date exists;
- positive-surprise drift candidates are admitted when pre-event 20-day return
  did not outperform SPY;
- support fields can use high liquidity, sector residual strength, and no
  same-day core overlap, but only as paper-notional metadata.

Evidence:

- continuation repair recovered core aggregate EV `6.3596 -> 7.8941`;
- adapter source improved aggregate EV by `+0.3547` and PnL by `+$3,557.15`;
- later support fields were positive but small.

Next valid work:

- forward replacement rows;
- materially richer event-quality fields such as expectation-adjustment
  trajectory, analyst-count persistence, guidance language, or surprise-history
  shape.

Do not retune post-earnings high-liquidity, sector-residual, core-overlap,
latest-surprise, pre-event RS, DTE, threshold, rank, or scalar variants on the
frozen sample.

### Fundamental Growth RS

Companyfacts plus OHLCV relative strength remains a useful default-off paper
source, but the nearby support surface is saturated.

Retained direction:

- realized growth or operating-profit quality;
- OHLCV relative strength;
- bounded paper support from filing recency, cost/liquidity, sector residual
  strength, and similar production-visible context.

Frozen direction:

- broad same-industry Companyfacts peer confirmation.

Reason: `exp-20260605-014` looked positive as replay-only evidence, but
`exp-20260605-015` failed as a production-realistic shared adapter because
chronological cooldown semantics exposed window regression and drawdown drift.
Production cannot use later-window selections to suppress earlier-window
historical candidates.

Next valid work:

- forward replacement rows for the accepted adapter;
- a materially new free-data relation;
- chronological replay semantics from the start.

Do not retune same-industry peer lookbacks, cooldowns, OHLCV confirmation,
fresh-underreaction, dual-growth, support scalars, sector residuals, or
Companyfacts thresholds on the frozen windows.

### Space Catalyst Observation

Space remains observe-only. Price-action and source-quality fields can separate
some candidates, but activation readiness is not present.

Useful retained fields:

- high close location on governed Space `trend_long`;
- intraday thrust;
- ARKX > UFO relative-momentum complement;
- selected-candidate cost/liquidity support;
- official source/customer and event-guard metadata as paper-only context.

Recent blocker: `exp-20260605-012` found no production-visible official Space
cohort passing the 10-day same-theme replacement-value gate.

Next valid work:

- forward replacement value by source, catalyst family, and peer bucket;
- activation only after nonzero closed outcomes and a separate pilot promotion.

Do not retune Space price-action, ETF, defense-budget, low-thrust absorption,
or theme-segment thresholds on the frozen sample.

## Rejected Mechanisms That Still Teach Something

### Broad 5-Day Winner Continuation

June 6 broad-stock continuation tests are useful as diagnostics but not
promotions.

Findings:

- `exp-20260606-004`: top 5-day SPY-relative winners improved aggregate EV and
  PnL but regressed `old_thin` and worsened drawdown.
- `exp-20260606-005`: adding SPY 5-day positive tape and candidate 20-day
  positive trend improved all three windows but failed drawdown drift
  (`+0.0297`, guard `0.005`).
- `exp-20260606-006`: low-deployment gating thinned the sample and still
  regressed `old_thin`.

Lesson:

- broad recent-winner continuation contains real beta/momentum, but the tail is
  not controlled enough for a default-off adapter;
- the problem is not top-N or a simple market gate; it is crash-state/tail
  classification and replacement value versus safer cash substitute overlays.

Next valid work:

- diagnostics only: identify tail-state features for the losing continuation
  rows;
- compare to low-deployment ETF cash substitute as the accepted capital
  allocation comparator;
- do not promote stock continuation unless it beats the ETF substitute after
  costs, drawdown, and exact displacement accounting.

### Weak Relation Confirmers

June 6-7 relation variants clarify the boundary between a real relation alpha
and a descriptive overlay.

Rejected neighbors:

- peer-shock lagged consensus did not beat the already accepted lagged
  independent-family comparator;
- sector ETF laggard and core-selected anchor peer-lag variants failed because
  the relation was too broad or produced too few real target trades;
- macro relief sector-confirmed leadership passed against the core baseline
  but failed the stricter accepted-comparator check;
- trend-quality short-horizon reversal had enough sample but was mostly a
  fragile rebound selector with old-window drawdown damage.

Lesson:

- a relation must identify a tradable displacement edge, not merely describe
  that a ticker belongs to a sector, peer group, or recent-reversal bucket;
- any relation family with an accepted comparator must beat that comparator,
  not just add positive standalone paper PnL;
- broad confirmation fields should become attribution fields first unless they
  create a materially different PIT edge.

Next valid work:

- orthogonal relation data such as PIT peer taxonomy, supplier/customer links,
  option/borrow structure, event-source propagation, or closed forward
  replacement rows;
- relation attribution that reports which accepted comparator each candidate
  would displace.

Do not retune peer lag, sector median, ETF laggard, macro sector-confirmation,
short-horizon selloff/reclaim, top-N, hold-day, cooldown, or notional thresholds
on the frozen sample.

### SEC Operational / Financing Event Pools

Recent SEC 8-K operational, leadership, shareholder-vote, strategic-warrant,
and non-dilutive credit/Item 2.03 absorption variants failed by thin sample,
window regression, or concentration. Positive language alone is not enough.

Lesson:

- SEC event alpha needs a stronger relation or semantic provenance than item
  code plus same-day price absorption;
- guidance/outlook raise phrase matching plus same-day price alignment is also
  insufficient when the event count is thin or the winners are large-cap
  continuation names already captured by momentum/consensus surfaces;
- the next useful SEC work is relation construction, source-span provenance,
  guidance/fact-tone gaps, or forward replacement rows, not phrase threshold
  retuning.

### Raw Cross-Sectional Alpha Score

Raw full-universe `alpha_score` is not a live ranking surface. Broad-universe
tests showed that the apparent narrow-watchlist edge was mostly curated
momentum and single-regime exposure. It lacks a robust monotonic ladder.

Retained route:

- default-off market-regime gated paper route only;
- source-consensus support as evidence bucket only.

Do not promote raw `alpha_score` top-N, score weights, or ranking replacement
without component-level monotonicity, regime stability, and cost-adjusted
replacement value.

## Research Queue

### 1. Forward Maturation Of Accepted Default-Off Adapters

Highest-value near-term work is not another replay sweep. It is forward
evidence on accepted paper adapters:

- low-deployment ETF cash substitute;
- lagged independent free-data consensus;
- SEC FTD + FINRA confirmation;
- FINRA/IWM borrow-pressure;
- post-earnings underpriced drift;
- Fundamental Growth RS;
- VBB / VCP / Space observe-only buckets where nonzero forward rows exist.

Minimum forward package:

- candidate id and source family;
- exact displaced candidate or cash alternative;
- cost-adjusted replacement value;
- closed 5/10/20-day outcome where relevant;
- concentration and top-contributor share;
- replay-vs-forward parity status;
- reason no live order was placed.

### 2. Tail-State Classifier For Momentum And Broad Candidate Pools

Broad recent-winner tests suggest a real continuation signal with unacceptable
tail risk. The next experiment should be diagnostic/field-building before
adapter promotion.

Candidate fields:

- `winner_continuation_tail_state_bucket`
- `momentum_crash_regime_bucket`
- `candidate_gap_chase_decay_bucket`
- `ret5_ret20_extension_ratio_bucket`
- `market_breadth_support_bucket`
- `same_day_displacement_candidate_type`
- `accepted_etf_substitute_comparator_delta`
- `cost_adjusted_drawdown_contribution_bucket`

Acceptance path:

- first read-only attribution;
- then default-off paper only if tail-state separation beats the low-deployment
  ETF comparator after costs and drawdown.

### 3. Relation-Aware Event / Peer Fields

Local same-ticker SEC recurrence and same-sector peer transfer have failed.
Future event graph work must improve the relation, not the event count.
Recent OHLCV relation work adds one positive template: industry-relative lag
plus same-day repair can work when the group is already strong and the candidate
shows a bounded reclaim. Recent failures add the negative template: sector/ETF
labels, core-selected anchors, and generic peer lag are not enough.

Candidate relation sources:

- characteristic-similarity peers built from sector, fundamentals, liquidity,
  momentum, analyst coverage, and event history;
- customer/supplier or contract counterparties when source text supports it;
- early peer earnings reaction;
- source-family propagation with explicit timestamp and source provenance;
- correlation-network stress clusters for risk, not direct alpha.

Minimum fields:

- `peer_relation_source_bucket`
- `peer_similarity_method_id`
- `peer_edge_weight`
- `peer_edge_asof_timestamp`
- `peer_relation_pit_valid_flag`
- `early_peer_event_age_trading_days`
- `peer_transfer_strength_score`
- `relation_displacement_value_bucket`
- `accepted_relation_comparator_id`
- `relation_edge_failure_mode`

Acceptance path:

- first compare against the closest accepted relation comparator, such as
  rolling-correlation peer shock, macro relief leadership, or industry-relative
  laggard repair;
- require displacement value after costs, not only standalone paper PnL;
- if the relation is production-visible and PIT-safe, use shared-paper-first
  instead of a private replay scout.

### 4. Expectation Revision With Real PIT Trajectory

Analyst/estimate revision remains promising but proxy-grade. Current frozen
snapshot evidence is not enough.

Needed fields:

- EPS and revenue revision velocity;
- analyst-count delta;
- estimate dispersion change;
- guidance raise/cut language;
- surprise-history adjustment;
- PEAD bucket with PIT `last_earnings_date`;
- source freshness and created-after-asof blockers.

Only promote after the PIT revision source and forward replacement rows are
available.

### 5. LLM As Bounded Semantic Infrastructure

LLM remains useful for event understanding, not direct trading authority.

Allowed roles:

- classify event type, source credibility, semantic direction, and uncertainty;
- bind evidence spans to source documents;
- produce structured, replayable fields for paper attribution;
- explain catastrophic risk cases for operator review.

Forbidden without separate Gate 1-4:

- direct buy/sell instructions;
- sizing, slot, exit, or risk-budget authority;
- hidden reliance on facts not present in prompt/log/archive.

Minimum LLM field standard:

1. schema-bound JSON;
2. source id, timestamp, and evidence span;
3. ontology/schema version;
4. retrieval/parse/reasoning failure buckets;
5. production artifact visibility;
6. PIT replay safety;
7. chronological evaluation before strategy use.

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

## Anti-Repeat Rules

Do not repeat these without forward rows or a materially different
production-visible field:

- broad filter/gate tightening on the core stack;
- simple risk scalar / top-up sweeps;
- state-surface rank/profile/notional retunes below the hard EV threshold;
- ticker-specific exceptions from one or two trades;
- simple target, stop, time-stop, or fixed max-loss exit changes;
- LLM direct buy/sell/sizing/exit authority;
- raw full-universe `alpha_score` top-N or weight tuning;
- broad OHLCV factor mining that only rediscovers momentum;
- broad 5-day winner continuation variants unless they solve drawdown/tail and
  beat the accepted low-deployment ETF comparator;
- low-deployment ETF threshold, ETF-list, hold-day, or notional retunes;
- lagged free-data consensus source-set/source-family/timing/notional retunes
  that do not beat the accepted lagged independent-family comparator;
- FINRA/IWM, SEC FTD, borrow-pressure, top-N, cooldown, hold, or notional
  retunes without a new PIT borrow-cost / availability source;
- Companyfacts support-scalar mining, same-industry peer confirmation,
  fresh-underreaction, or dual-growth threshold variants;
- post-earnings high-liquidity, sector-residual, core-overlap, DTE, latest
  surprise, average surprise, pre-event RS, score, rank, or scalar retunes;
- SEC item-code / phrase / same-day absorption retries without richer semantic
  provenance or relation structure;
- raw SEC same-family bursts, first/follow-on recurrence, same-ticker
  cross-family transitions, same-sector SEC peer transfer, or same-sector
  event breadth retries;
- Form 4 owner-count or liquidity-intensity retries without forward
  replacement value;
- Space price-action, ETF relative, defense-budget, low-thrust absorption, or
  theme-segment retunes on frozen windows;
- missing archive/text availability as an alpha field.

## Update Discipline

Update this file only when a result changes mechanism-level priors, freezes a
research family, changes the next 1-3 research queues, or adds external
research that maps to concrete replayable fields. Keep experiment details in
the logs.
