# Alpha Optimization Playbook

Last reviewed: 2026-05-13.

This file is the long-run alpha synthesis for the strategy system. It is not a
single-session action card and it is not a chronological experiment diary. Its
job is to compress many experiments into durable mechanism conclusions:

- where the current alpha appears to come from;
- which experiment families have been accepted, rejected, blocked, or deferred;
- what patterns repeated across windows and strategy sleeves;
- what should be tested next, and what should not be retried without new
  evidence.

Individual experiment parameters, exact commands, window metrics, artifacts,
and reproduction details belong in:

- `docs/experiment_log.jsonl`
- `docs/experiments/logs/*.json`
- `docs/experiments/artifacts/*.md`
- `data/experiments/**`

Use `docs/backtesting.md` as the single source of truth for standard windows,
commands, metrics, and acceptance protocol. If this file conflicts with
`AGENTS.md`, `AGENTS.md` wins.

## How To Use This Playbook

Before starting a new alpha search:

1. Identify the mechanism family below.
2. Read its accepted laws and rejected patterns.
3. Check whether the proposed variable is genuinely new or only a nearby retry.
4. Follow `docs/backtesting.md` for the three-window protocol.
5. Record the experiment in structured logs, then update this playbook only if
   the result changes a durable conclusion.

Good updates to this file look like:

- "This mechanism is now accepted, with these evidence IDs."
- "This family is now rejected unless new evidence appears."
- "The bottleneck is measurement/data, not parameter choice."
- "The next valid alpha variable should move from X to Y."

Bad updates look like:

- appending every experiment result as a dated note;
- copying full metric dumps already stored in logs;
- recording one-off parameter sweeps without a mechanism conclusion;
- using this file as a replacement for `experiment_log.jsonl`.

## Current Strategy Doctrine

The system is an event-enhanced intermediate-term trend / breakout strategy.

Current alpha sources, in descending practical importance:

1. Trend continuation and breakout follow-through.
2. Lifecycle and capital allocation around already-selected positions.
3. Production-visible event semantics.
4. Default-off paper replacement-value sleeves.
5. Narrow risk allocation by state, sector, catalyst quality, and relative
   strength.

The main lesson from the experiment history is that the system rarely improves
from broad filters or broad capacity changes. The durable wins tend to be
small, production-visible allocation changes that preserve candidate survival
and do not invent a new backtest-only decision path.

## Current Accepted Checkpoints

### Core Stack

Accepted checkpoint: `exp-20260513-007`, layered on the lifecycle allocation
core from `exp-20260502-022`, the RS20 entry-state sizing promotion from
`exp-20260510-012`, and the TRIP sector taxonomy completion from
`exp-20260510-015`.

Accepted three-window metrics:

| Window | EV | Return | Sharpe | Max DD | Win rate | Trades |
|---|---:|---:|---:|---:|---:|---:|
| `late_strong` | 4.2894 | +95.32% | 4.50 | 5.52% | 78.95% | 19 |
| `mid_weak` | 1.6747 | +62.49% | 2.68 | 9.70% | 52.38% | 21 |
| `old_thin` | 0.3867 | +28.86% | 1.34 | 8.21% | 40.91% | 22 |

Aggregate accepted-stack EV is `6.3508`; aggregate PnL is `+$186,668.01`;
convergence is `8/8`.

Source of truth: `data/experiments/exp-20260513-007/signal_day_ticker_green_risk.json`.

Core conclusion: the accepted core is a capital-allocation and lifecycle
baseline. It is not evidence for new broad entry filters, broad universe
expansion, global sector priority, or global capacity changes.
`exp-20260513-007` reinforces the current best core-alpha direction: small,
production-visible state allocation on already-selected signals. Do not retry
nearby own-candle scalars on the frozen windows without forward evidence or a
materially narrower discriminator.

### SEC Financial-Report Paper Sleeve

Accepted checkpoint: `exp-20260512-020`, after the accepted sequence
`exp-20260511-112`, `exp-20260512-001`, `exp-20260512-006`,
`exp-20260512-007`, and `exp-20260512-020`.

Current default-off sleeve:

- non-platform `earnings_8k` and `periodic_report` rows only;
- `max_positions=3`;
- `t1_excess_return_vs_spy >= 1%`;
- 10-trading-day hold;
- `$15,000` base paper notional;
- `periodic_report` default scalar `1.25x`;
- `10-Q periodic_report` scalar `2.00x`;
- `earnings_8k` scalar `1.00x`.

Accepted aggregate metrics after `exp-20260512-020`: EV `8.558004`, total PnL
`$234,762.79`, sleeve PnL `$48,332.18`, max drawdown ceiling `10.0721%`, and
52 closed sleeve trades.

SEC conclusion: this sleeve is a T+1 relative-reaction and semantic
risk-allocation surface. It should stay default-off until forward replacement
value supports live scope.

### Space Default-Off Sleeve

Accepted checkpoint: official-catalyst Space stack through `exp-20260512-041`.
`exp-20260512-043` tested `mission_binary` profile membership and produced no
executable delta.

Current default-off Space helpers:

- perfect official Space TQS: `1.50x` risk top-up;
- near-perfect official Space `trend_long` TQS: `1.10x` top-up;
- peer-nonleader official Space `breakout_long`: `0.00x` extra risk;
- IWM 20d momentum above SPY 20d momentum: `1.10x` top-up;
- `theme_segment=launch_lunar`: `1.10x` top-up;
- `liquidity_tier=ok`: `1.10x` top-up;
- primary-source `customer_win`: `1.10x` top-up;
- `event_guard_profile` containing financing or dilution: `1.075x` top-up;
- RKLB/ASTS launch-connectivity `trend_long` target extension: 7 ATR in the
  default-off Space context.

Accepted aggregate metrics after `exp-20260512-041`: EV `14.0087`, total PnL
`$340,127.26`, max drawdown ceiling `12.43%`, min survival `77.46%`, and 70
trades.

Space conclusion: the supported Space alpha is production-visible
catalyst-quality risk allocation, not live routing. Live Space slots remain
zero, and forward replacement value is still the promotion gate.

## Long-Run Mechanism Laws

### 1. Broad Filters Usually Fail

Repeated experiments show that broad entry filters, global ranking filters, and
simple sector/strategy gates often remove good trades along with bad ones.
Survival pressure matters more than intuitive cleanliness.

Accepted implications:

- New filters need measured survival and three-window evidence.
- Prefer replacing or refining an existing filter over adding another one.
- Avoid broad "looks safer" rules unless they improve EV and risk distribution
  across the canonical windows.

Evidence families:

- global TQS ordering and confidence ordering: rejected;
- same-day trend-first ordering: rejected;
- sector cap / sector priority shortcuts: rejected;
- broad ETF/universe expansion as direct core alpha: rejected;
- simple gap-cancel exceptions by sector/strategy/TQS: rejected.

### 2. Allocation Beats New Entry More Often Than New Entry Beats Allocation

The strongest durable changes usually resize or route already-qualified
signals. They do not invent a new entry source.

Accepted or useful allocation mechanisms:

- strict follow-through add-on production default;
- follow-through add-on fraction increase after confirmation;
- 40% initial cap allocation;
- one-slot scarce-capacity breakout deferral;
- risk-on unmodified sizing lift;
- low/mid-score plain risk-on sizing;
- RS20 shared entry-state sizing top-up;
- selected sector/state risk boosts when they survive all windows.

Rejected nearby patterns:

- global `MAX_POSITIONS` / slot-count sweeps;
- raw portfolio heat budget expansion;
- simple sector caps;
- second add-on timing/size/cap retries after materiality failed;
- add-on cap/headroom retunes without new forward concentration evidence.

Rule: if a proposed change can be phrased as "more slots, more heat, more size
for a broad group," assume it is low-quality until proven otherwise.

### 3. Lifecycle Edges Are Narrow

Winner capture and stop/target geometry have produced selective wins, but
generalization has repeatedly failed.

Durable pattern:

- lifecycle changes work only for a narrow strategy/sector/state cohort;
- broad target widening usually delays exits in weaker windows;
- trailing-stop and runner logic often looks appealing in diagnostics but fails
  fixed-entry replay.

Accepted or supported context:

- selected trend cohorts can justify wider target geometry;
- RKLB/ASTS launch-connectivity Space trends can use wider default-off target
  semantics;
- adverse next-open cancel at 2% is accepted and should not be weakened by
  simple exceptions.

Rejected patterns:

- broad Commodity breakout target widening;
- Financials trend wider target without a new discriminator;
- Commodity trend target extension beyond accepted width;
- simple target-exit re-entry;
- ATR trailing full exits;
- target-half or target-third runner splits;
- early MFE breakeven/profit-protective stops without stronger state evidence.

Rule: any new lifecycle alpha needs a state or catalyst discriminator, not just
a nearby ATR multiple.

### 4. Event Alpha Needs Replacement Value, Not Just Event Labels

Event overlays help when the event label changes the replacement value of a
candidate or paper sleeve. Generic event optimism has not been enough.

Supported event surfaces:

- rotation-breakout leadership inside the event bundle;
- benchmark-gated state-surface paper replacement value;
- default-off SEC financial-report T+1 drift;
- production-visible Space official-catalyst metadata.

Rejected or weak event surfaces:

- broad event-source pruning;
- generic event benchmark gates applied directly to the event bundle;
- simple post-news PEAD-style entry thresholds after materiality/risk failed;
- item-composition gates without better earnings-quality fields;
- shadow-only short-pressure and options overlays without promotion-grade
  replay evidence.

Rule: an event variable should explain why this candidate has better expected
replacement value than the next available candidate. If it only explains why
the story sounds interesting, keep it in audit/paper mode.

### 5. SEC Alpha Is Blocked By Semantic Data Quality, Not More Retunes

SEC experiments split into two families:

- financial-report T+1 drift paper sleeve, which is currently useful;
- filing-shock / earnings-quality grading, which remains blocked by missing
  same-accession directional fields.

Accepted financial-report paper mechanism:

- strong T+1 excess reaction versus SPY;
- non-platform filtering;
- modest max-3 capacity;
- 10-trading-day lifecycle;
- semantic notional allocation by report family and 10-Q subtype.

Blocked filing-shock mechanism:

- no reliable same-accession EPS/revenue surprise fields;
- no reliable guidance raise/cut fields;
- Companyfacts joins alone do not provide directional shock;
- PIT timestamp plumbing is less of a blocker than semantic feature absence.

Rejected SEC retunes:

- nearby T+1 floor sweeps around the accepted 1%;
- fixed hold-day sweeps around 10 trading days;
- capacity above max-3 on the frozen sample;
- paired-filing dedupe;
- auxiliary earnings 8-K item-code notional scalar;
- 10-K/10-Q form exclusion without a new semantic field.

Next valid SEC alpha: add PIT-safe same-accession earnings/guidance/language
quality fields or collect forward replacement value. Do not keep retuning the
accepted paper sleeve on the same frozen sample.

### 6. Space Alpha Is Catalyst-Quality Risk Allocation

Space became useful only after the experiments moved away from noisy ticker
expansion and toward production-visible catalyst metadata.

Supported Space pattern:

- official catalyst context matters;
- peer leadership matters for breakouts;
- trend quality ladders are more reliable than breakout TQS ladders;
- source quality and registry quality fields can support conservative top-ups;
- broad small-cap appetite helps modestly when IWM leads SPY;
- launch/lunar and liquidity anchor metadata are useful but should stay small.

Accepted Space evidence:

- perfect TQS risk top-up: `exp-20260512-004`;
- near-perfect trend TQS top-up: `exp-20260512-008`;
- peer-nonleader breakout zero extra risk: `exp-20260512-013`;
- IWM-relative small-cap state: `exp-20260512-031`;
- launch/lunar theme segment: `exp-20260512-032`;
- liquidity-tier risk: `exp-20260512-037`;
- official customer-source risk: `exp-20260512-038`;
- financing/dilution profile risk: `exp-20260512-041`;
- watch-liquidity risk: `exp-20260512-112`.

Rejected Space patterns:

- noisy static pool expansion;
- mature satcom breadth;
- Space ETF timing;
- data-vendor trend target/risk retunes;
- launch/connectivity breakout risk haircuts;
- Space breakout stop-width and target-width sweeps;
- lunar/manufacturing target broadening;
- data/defense theme scalar;
- broad defense-budget source scalar due to drawdown cost;
- mission-binary profile scalar due to immaterial coverage;
- watch-liquidity peer-state narrowing. `exp-20260513-003` found both
  leader-only and nonleader-only scopes worse than the accepted all-peer-state
  watch-liquidity helper.

Next valid Space alpha: forward replacement value by catalyst family, source
quality, peer leadership, and production registry profile. Do not keep slicing
the accepted watch-liquidity helper by peer state on frozen snapshots.
Candidate-pool work is valid only if it improves official-catalyst coverage or
attribution quality; do not add noise tickers just to get more trades.

### 7. LLM Is A Semantic Layer, Not A Risk Engine

The LLM can be part of the alpha system, but only inside auditable boundaries.

Valid LLM jobs:

- event classification;
- semantic strength;
- catastrophe/risk explanation;
- source-quality summaries;
- structured candidate annotations for later attribution.

Invalid LLM jobs:

- position sizing;
- stops and targets;
- portfolio heat;
- hard entry/exit decisions without replayable fields;
- prompt-only numeric threshold duplication.

Current limitation: LLM soft-ranking is not the best near-term alpha search for
Space because the labeled forward set is thin. If LLM work resumes, it should
add attribution metrics such as pass/veto return, event-class return, or
structured reason stability.

## Family Index

| Family | Current conclusion | Evidence index |
|---|---|---|
| Core allocation | Modest shared sizing/routing edges work better than broad filters | `exp-20260428-005`, `exp-20260428-025`, `exp-20260429-025`, `exp-20260510-012` |
| Core capacity | Global slots, heat, broad sector caps usually fail | `exp-20260427-014`, `exp-20260428-028`, `exp-20260429-001`, `exp-20260430-002` |
| Lifecycle exits | Narrow cohort geometry only; broad runner/trailing rules fail | `exp-20260429-007`, `exp-20260429-012`, `exp-20260507-013`, `exp-20260507-014` |
| Event paper | Replacement-value state surfaces beat broad event gates | `exp-20260510-003`, `exp-20260510-005` |
| SEC T+1 | Useful default-off paper sleeve; semantic risk allocation is current edge | `exp-20260511-112`, `exp-20260512-001`, `exp-20260512-006`, `exp-20260512-007`, `exp-20260512-020` |
| SEC filing shock | Blocked by missing directional same-accession fields | `exp-20260510-002` |
| Space | Official-catalyst risk allocation works; live slots remain blocked | `exp-20260512-004`, `008`, `013`, `031`, `032`, `037`, `038`, `041`, `112`, `exp-20260513-003` |
| Post-news PEAD | Directionally interesting but not promotion-grade yet | `exp-20260509-020`, `exp-20260511-104`, `exp-20260511-027`, `exp-20260511-029` |
| LLM | Keep semantic and attributable; no hard risk delegation | governance rule plus LLM attribution requirements in `AGENTS.md` |

## Current Research Queue

1. Space forward replacement value. Close the loop on official-catalyst helpers:
   peer leader versus nonleader breakouts, customer-source quality,
   financing/dilution profile, and launch/lunar versus data/defense buckets.
2. SEC semantic feature expansion. Add PIT-safe same-accession surprise,
   guidance, or language-quality fields before more sleeve retunes.
3. Event replacement-value paper outcomes. Track the rotation/state-surface
   paper stack forward and measure concentration risk.
4. Core state allocation. Search for one new production-visible state variable
   at a time: relative strength, dispersion, heat pressure, event quality, or
   deployment context.
5. LLM attribution. Only resume LLM scoring when structured labels and forward
   outcomes can show pass/veto or event-class value.

## Do Not Retry Without New Evidence

### Core

- Global position slot count and broad capacity sweeps.
- Global TQS/confidence candidate sorting.
- Same-day trend-first ordering.
- Broad sector caps or sector priority ordering.
- Commodity breakout target widening.
- Financials trend target widening without a new discriminator.
- Nearby add-on trigger, fraction, cap, and second-add-on retries.
- Simple gap-cancel exceptions by sector, strategy, full-risk status, or TQS.
- Broad ETF or static universe expansion as direct core alpha.
- Adjacent low-deployment ETF overlay candidate-pool variants around the
  accepted `QQQ` / `SPY` / `IWM` / `GLD` / `SLV` v1 pool, unless forward paper
  replacement-value evidence changes the prior. `exp-20260512-777` found that
  equity-only, bond-added, energy-added, cross-asset-plus, and defensive-plus
  pools failed the three-window gate versus v1.
- Fixed signal-day sector-proxy tape scalars at +/-1% without a stronger
  discriminator. `exp-20260512-106` rejected the adverse-tape 0.5x haircut, and
  `exp-20260512-107` found the positive-tape 1.10x top-up was aggregate-positive
  but only moved `old_thin`.
- Fixed core breakout strong-volume scalars using the existing
  `conditions_met.volume_spike_ratio > 2.0` boundary. `exp-20260513-001`
  found the best scalar was only `1.05x`, with aggregate EV `+0.0002` and PnL
  `+$2.62`, improving only `mid_weak`.

### SEC

- Companyfacts weighting without directional surprise/guidance fields.
- Raw capacity above max-3 on the frozen SEC sleeve sample.
- Nearby T+1 excess floors around the accepted 1%.
- Fixed hold-day sweeps around 10 trading days.
- Paired-filing dedupe variants.
- Auxiliary earnings 8-K item-code notional scalars.
- Form exclusion or 10-K/10-Q retunes unless the new variable is semantic and
  production-visible.

### Space

- Noisy ticker additions or static pool expansion.
- Theme ETF timing gates.
- LLM soft-ranking while labeled Space outcomes remain thin.
- Nearby perfect/near-perfect TQS scalars.
- Space breakout stop-width or target-width sweeps.
- Data-vendor trend target/risk retunes.
- Lunar/manufacturing target broadening from RKLB/ASTS evidence.
- Defense-budget/government-contract broad source scalars.
- Mission-binary profile scalars until outcome coverage is material.
- Watch-liquidity peer-state scope splits on the frozen Space replay.
  `exp-20260513-003` found leader-only and nonleader-only scopes both regressed
  the accepted all-peer-state helper.

### Event / LLM

- Broad event-source pruning.
- Generic event benchmark gates not tied to a state-surface sleeve.
- Form 4 single-owner queue pre-entry relative-strength confirmation on the
  frozen sample. `exp-20260512-108` stayed positive versus core but regressed
  the single-owner baseline in all three windows and failed the sample guard.
- Prompt-only numeric threshold changes.
- Any LLM expansion without a replayable attribution metric.

## Measurement And Parity Rules

Strategy changes are not accepted because they pass `pytest`; they need the
standard backtest protocol.

For any positive alpha change, record production/backtest impact:

- shared policy changed;
- backtester adapter changed;
- run adapter changed;
- replay-only status;
- parity test added or not;
- default-off paper status if applicable.

Measurement repair can outrank alpha search only when it blocks a trustworthy
experiment. Valid blockers include:

- production/backtest divergence;
- missing runtime fields;
- missing prompt/log/replay fields for an LLM judgment;
- missing forward attribution;
- data joins that make a candidate alpha unreplayable.

## Update Discipline

This file should grow slowly. A new experiment should update this playbook only
when it changes one of the following:

- an accepted checkpoint;
- a durable mechanism law;
- a rejected family or anti-repeat rule;
- the current research queue;
- a measurement blocker;
- an LLM governance boundary;
- a production/backtest parity constraint.

When updating, write synthesis first and cite experiment IDs as evidence. Do not
paste full artifacts or every window table unless the table defines the current
checkpoint.
