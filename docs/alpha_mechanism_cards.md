# Alpha Mechanism Cards

Accepted and rejected mechanism details moved out of `docs/alpha-optimization-playbook.md`.
Use this file when checking exact evidence, nearby rejected variants, or next-valid-work notes for a mechanism family.

The current operating rules, readout, research queue, and anti-repeat rules remain in `docs/alpha-optimization-playbook.md`.

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

### Volatility Relief Stock Leadership

This is a free-data candidate-pool lead tied to volatility-product relief. When
`VIXY` sells off and closes weak while `SPY` and `QQQ` confirm risk relief, the
strongest liquid stock leaders can be tracked as default-off paper candidates.

Accepted shared adapter: `exp-20260607-019`, promoting the positive replay lead
from `exp-20260607-018`.

Mechanism:

- volatility relief gate: same-day `VIXY` selloff and low close-location;
- confirmation: same-day `SPY` and `QQQ` rally and close high in range;
- source universe: broad-market, sector-known, liquid stock observation feed;
- selection: up to top-2 same-day stock leaders;
- lifecycle: next-open paper entry, 10-trading-day close exit, costs included;
- status: default-off paper only, no live orders.

Evidence:

- aggregate EV `7.8941 -> 8.4673` (`+0.5732`);
- PnL `$234,850.99 -> $246,785.79`;
- all three canonical windows improved;
- target paper trades: `88`;
- max drawdown drift: `0.0003`;
- concentration passed (`max_single_positive_pnl_share=0.142323`,
  `positive_pnl_hhi=0.060267`).

Next valid work:

- collect closed forward replacement-value rows from the shared adapter;
- audit broad-market universe coverage on volatility-relief days;
- search for truly point-in-time vol-flow, option-volume, or volatility-event
  fields if free data exists;
- before live deployment, either measure the full execution envelope
  (notional/cap/liquidity/slippage/displacement/kill switch/order semantics) or
  release through checklist if that envelope has already been accepted.

Do not retune nearby VIXY relief thresholds, SPY/QQQ confirmation thresholds,
close-location thresholds, top-N, hold days, same-ticker cooldown, or paper
notional on the frozen sample.

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

### Industry-Stable Core-Flow Confirmation

This is a free-OHLCV relation alpha. The plain industry-stable leadership
source had positive EV/PnL in all windows but failed the drawdown guard.
Same-day core A/B entry flow plus same-ticker overlap exclusion repaired enough
tail risk, and the shared adapter reproduced the fixed bundle.

Accepted shared adapter: `exp-20260608-008`, promoting the positive replay lead
from `exp-20260608-007` after rejected `exp-20260608-004` and
`exp-20260608-005`.

Mechanism:

- source: broad-market liquid stocks grouped by persisted industry or sector;
- base relation: stable low-volatility leaders inside strong industries;
- confirmation: same signal date must have selected core A/B entry flow;
- overlap rule: exclude same-ticker core overlap so the row tests independent
  replacement value;
- lifecycle: top-1/day, fixed `$4,000` paper notional, 15-trading-day
  same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs
  included;
- status: default-off paper only, no live orders.

Evidence:

- aggregate EV `+0.1459`;
- PnL `+$3,731.54`;
- all three canonical windows improved;
- target paper trades: `47`;
- max drawdown drift `0.0007`, within the `0.005` guard.
- shared adapter reproduced the private replay lead.

Next valid work:

- compare against `industry_relative_laggard_repair`, `rolling_corr_peer_shock`,
  and volatility/macro relief accepted comparators;
- collect forward replacement-value rows before any activation discussion.

Do not retune industry stability, low-volatility, core-flow count, overlap,
top-N, hold-day, cooldown, or notional thresholds on the frozen sample.

### Narrow-Range Compression Breakout

This is a free-OHLCV price-formation candidate-pool lead. Compression alone is
not enough; the accepted edge is the complete fixed bundle that demands prior
range contraction, signal-day expansion, high close-location, volume
confirmation, and SPY-relative trend before next-open entry.

Accepted shared adapter: `exp-20260608-013`, promoting the positive replay lead
from `exp-20260608-012`.

Mechanism:

- source universe: broad-market, sector-known, liquid stock observation feed;
- setup: prior 10-day range compression versus 40-day reference range;
- trigger: signal-day range expansion, positive signal-day return, high
  close-location, and volume confirmation;
- trend guards: SPY-relative 20-day and 60-day trend, plus extension guards;
- lifecycle: top-1/day, fixed `$4,000` paper notional, 10-trading-day
  same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs
  included;
- status: default-off paper only, no live orders.

Evidence:

- aggregate EV `+0.1608`;
- PnL `+$2,248.98`;
- all three canonical windows improved;
- target paper trades: `44`;
- shared adapter reproduced the replay lead.

Next valid work:

- collect forward replacement-value rows from the shared adapter;
- compare directly against accepted low-deployment ETF and relation adapters;
- study drawdown/tail state as read-only attribution before any activation
  envelope.

Do not retune compression windows, expansion thresholds, close-location,
volume, SPY-relative trend, extension guard, top-N, hold-day, cooldown, or
notional thresholds on the frozen sample.

### Turn-of-Month Liquid Leadership

This is a free-calendar plus free-OHLCV candidate-pool lead. The edge is not
generic month-start momentum; the accepted bundle requires a liquid
sector-known stock to show SPY-relative leadership and strong signal-day
quality inside the last-trading-day through first-three-trading-days window.

Accepted shared adapter: `exp-20260609-027`, promoting the positive replay lead
from `exp-20260609-026`.

Mechanism:

- calendar route: last trading day through first three trading days of each
  month;
- source universe: broad-market, sector-known, liquid stock observation feed;
- leadership gates: 20-day and 60-day excess return versus `SPY`;
- quality guards: positive signal-day return, high close-location, bounded
  volume ratio, bounded realized volatility, and bounded 5-day/20-day
  extension;
- lifecycle: top-1/day, fixed `$4,000` paper notional, 10-trading-day
  same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs
  included;
- status: default-off paper only, no live orders.

Evidence:

- aggregate EV `+0.2774`;
- PnL `+$5,287.69`;
- all three canonical windows improved;
- target paper trades: `73`;
- max drawdown drift `-0.0001`;
- concentration passed (`max_single_positive_pnl_share=0.118149`,
  `positive_pnl_hhi=0.052302`);
- shared adapter reproduced the replay lead with zero EV/PnL/trade drift.

Production parity note:

- historical replay must pass the full loaded trading calendar into the helper;
- daily snapshots must not infer month-end from truncated OHLCV;
- month-end candidates require explicit `calendar_dates` or
  `known_month_end_dates`, otherwise the month-end route fails closed.

Next valid work:

- collect closed forward replacement-value rows from the shared adapter;
- look for a genuinely point-in-time flow-beneficiary data edge, such as ETF
  rebalance constituents or other free flow proxies;
- before live deployment, measure the full activation envelope
  (notional/cap/liquidity/slippage/displacement/kill switch/order semantics).

Do not retune turn-window day counts, ret20/ret60 leadership thresholds,
close-location, volume, volatility, top-N, hold-day, cooldown, or notional
thresholds on the frozen sample.

### Accepted-Helper Source-Priority Allocator

This is a free-OHLCV capital-allocation/candidate-pool conflict policy. The
edge is not another helper threshold; it is treating accepted helper families as
competing sensors and keeping the highest-priority same-day paper row.

Accepted shared adapter: `exp-20260610-005`, promoting the positive replay lead
from `exp-20260610-004`.

Mechanism:

- source priority: `volatility_relief`, `rolling_peer_shock`, `turn_of_month`,
  `industry_laggard_repair`, `compression`, `industry_stable_core_flow`;
- lifecycle: top-1 selected source row per signal date, fixed `$4,000` paper
  notional, 12-trading-day same-ticker cooldown, underlying helper
  next-open/10-trading-day paper outcome semantics, costs included;
- status: shared default-off paper only, no live orders.

Evidence:

- aggregate EV `+0.8971`;
- PnL `+$14,502.52`;
- all three canonical windows improved;
- target paper trades: `327`;
- max drawdown drift `+0.0024`, within the `0.005` guard;
- concentration passed (`max_single_positive_pnl_share=0.045022`,
  `positive_pnl_hhi=0.017164`);
- shared helper reproduced the replay lead and daily run exposes the same
  default-off source-priority surface.

Next valid work:

- collect closed forward replacement-value rows from the shared allocator;
- before live deployment, run a separate activation-envelope Gate 1-4 with
  notional/cap/liquidity/slippage/displacement/kill switch/order semantics;
- prefer a materially new independent data edge over another helper-order or
  threshold search.

Do not retune source priority order, source top-N, paper notional, hold-day,
cooldown, or underlying accepted helper thresholds on the frozen sample.

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

June 6-8 relation variants clarify the boundary between a real relation alpha
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
- copper-growth, oil-cost-relief, IWM breadth-thrust, DIA/MDY real-economy, and
  defensive/rates sector variants mostly relabeled broad risk beta or cyclical
  beta without durable next-open replacement value;
- industry-stable leadership had real continuation signal, but simple
  SPY/QQQ-down plus VIXY-up tail exclusion did not isolate the drawdown problem.

Lesson:

- a relation must identify a tradable displacement edge, not merely describe
  that a ticker belongs to a sector, peer group, or recent-reversal bucket;
- any relation family with an accepted comparator must beat that comparator,
  not just add positive standalone paper PnL;
- broad confirmation fields should become attribution fields first unless they
  create a materially different PIT edge.
- broad ETF/commodity/macro proxies should be presumed to be beta labels unless
  they explain which ticker they displace and why the edge survives next-open
  costs and the closest accepted comparator.

Next valid work:

- orthogonal relation data such as PIT peer taxonomy, supplier/customer links,
  option/borrow structure, event-source propagation, or closed forward
  replacement rows;
- relation attribution that reports which accepted comparator each candidate
  would displace.

Do not retune peer lag, sector median, ETF laggard, macro sector-confirmation,
short-horizon selloff/reclaim, commodity/ETF proxy thresholds, broad
real-economy proxy thresholds, top-N, hold-day, cooldown, or notional thresholds
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
