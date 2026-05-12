# Alpha Optimization Playbook

Last reviewed: 2026-05-12.

This file is a mechanism playbook, not an experiment diary. It should tell the
next agent what to test, what not to retest, and where the current alpha seems
to come from. Individual dated experiments belong in:

- `docs/experiment_log.jsonl`
- `docs/experiments/logs/*.json`
- `docs/experiments/artifacts/*.md`
- `data/experiments/**`

Use `docs/backtesting.md` as the single source of truth for commands, standard
windows, metrics, and acceptance protocol. If this file conflicts with
`AGENTS.md`, `AGENTS.md` wins.

## Current Strategy Shape

The system is an event-enhanced intermediate-term trend / breakout strategy.
The durable alpha map is:

1. Core stack: trend continuation, breakout follow-through, lifecycle sizing,
   and capital allocation.
2. Event overlays: production-visible event semantics and replacement-value
   paper sleeves.
3. Space sleeve: default-off official-catalyst risk allocation, not live
   routing yet.
4. SEC financial-report sleeve: default-off T+1 drift paper queue with semantic
   notional allocation.
5. LLM: useful for event understanding and risk explanation, but not for hard
   sizing, stops, or live routing.

## Accepted Checkpoints

### Core Stack

Accepted checkpoint: `exp-20260510-015` with the shared TRIP sector taxonomy
repair, layered on the lifecycle allocation core from `exp-20260502-022` and
the RS20 entry-state sizing promotion from `exp-20260510-012`.

Accepted three-window metrics:

| Window | EV | Return | Sharpe | Max DD | Win rate | Trades |
|---|---:|---:|---:|---:|---:|---:|
| `late_strong` | 4.2340 | +94.09% | 4.50 | 5.48% | 78.95% | 19 |
| `mid_weak` | 1.6689 | +61.81% | 2.70 | 9.41% | 52.38% | 21 |
| `old_thin` | 0.3853 | +28.54% | 1.35 | 8.15% | 40.91% | 22 |

Aggregate accepted-stack EV is `6.2882`; aggregate PnL is `+$184,444.42`;
convergence is `8/8`. Treat
`data/experiments/exp-20260510-015/trip_sector_taxonomy.json` as the current
three-window source of truth for the core stack.

Mechanism conclusion: core work should favor modest shared allocation edges and
state-aware lifecycle controls. Do not reopen broad entry filters, capacity
counts, or target/stop sweeps unless a new independent state variable explains
why the old attempts failed.

### SEC Financial-Report Paper Sleeve

Accepted checkpoint: `exp-20260512-020`, after the accepted sequence
`exp-20260511-112`, `exp-20260512-001`, `exp-20260512-006`,
`exp-20260512-007`, and `exp-20260512-020`.

Current default-off sleeve:

- Non-platform `earnings_8k` and `periodic_report` rows only.
- `max_positions=3`.
- `t1_excess_return_vs_spy >= 1%`.
- Hold for 10 trading days.
- Base paper notional `$15,000`.
- `periodic_report` default scalar `1.25x`.
- `10-Q periodic_report` scalar `2.00x`.
- `earnings_8k` scalar `1.00x`.

Accepted aggregate metrics after `exp-20260512-020`: EV `8.558004`, total PnL
`$234,762.79`, sleeve PnL `$48,332.18`, max drawdown ceiling `10.0721%`, 52
closed sleeve trades.

Mechanism conclusion: the SEC edge is event-quality and semantic risk
allocation after a strong T+1 relative reaction. The useful surface is not more
raw capacity, hold-day retuning, paired-filing dedupe, or local item-code
notional tweaks on the same sample.

### Space Default-Off Sleeve

Accepted checkpoint: official-catalyst Space stack through `exp-20260512-041`.
`exp-20260512-043` tested `mission_binary` and produced no executable delta.

Current default-off Space helpers:

- Perfect official Space TQS: `1.50x` risk top-up.
- Near-perfect official Space `trend_long` TQS: `1.10x` top-up.
- Peer-nonleader official Space `breakout_long`: `0.00x` extra risk.
- IWM 20d momentum above SPY 20d momentum: `1.10x` top-up.
- `theme_segment=launch_lunar`: `1.10x` top-up.
- `liquidity_tier=ok`: `1.10x` top-up.
- Primary-source `customer_win`: `1.10x` top-up.
- `event_guard_profile` containing financing or dilution: `1.075x` top-up.
- RKLB/ASTS launch-connectivity `trend_long` target extension: 7 ATR in the
  default-off Space context.

Accepted aggregate metrics after `exp-20260512-041`: EV `14.0087`, total PnL
`$340,127.26`, max drawdown ceiling `12.43%`, min survival `77.46%`, 70 trades.

Live Space slots remain zero. The accepted Space stack is production-visible
metadata/helper policy, not a live order path.

Mechanism conclusion: the next Space alpha direction is production-visible
catalyst-quality and forward replacement value, not LLM soft-ranking on thin
data, noisy ticker expansion, or another same-sample stop/target/risk scalar.
Candidate-pool work is valid only if it improves official-catalyst coverage or
forward attribution quality without adding noise tickers.

### Event Paper Stack

Accepted paper direction: event-specific state-surface allocation, especially
rotation-breakout leadership plus benchmark-gated state-surface replacement
value.

Key evidence:

- `exp-20260510-003`: rotation-surface event tilt accepted as a shared
  production-visible default-off adapter.
- `exp-20260510-005`: rotation-event plus benchmark-gated state-surface stack
  remained strongly additive in all three windows.

Mechanism conclusion: the current event-paper edge is not a broad benchmark
gate or generic source-pruning rule. It is a narrow replacement-value surface
that needs forward paper outcomes before live/default routing.

## Research Queue

1. Space forward replacement value. Measure closed forward outcomes for the
   current official-catalyst helpers, especially leader versus nonleader
   breakouts and primary-source customer wins. Do not spend more loops on Space
   LLM soft-ranking while the labeled forward set is thin.
2. SEC semantic quality fields. Add genuinely new PIT-safe earnings/filing
   quality fields, such as same-accession surprise, guidance, or management
   language structure. Avoid nearby hold-day, capacity, floor, form-exclusion,
   paired-filing, or item-code notional retunes.
3. Event paper replacement value. Keep the rotation/state-surface stack
   default-off while collecting forward closed outcomes and concentration risk.
4. Core allocation edges. Search for one independent state variable at a time:
   relative strength, dispersion, event quality, or heat capacity. Avoid new
   filters unless survival remains healthy and the field is production-visible.
5. Measurement repair only when it blocks alpha. Valid blockers include
   production/backtest divergence, missing runtime fields, incomplete forward
   attribution, or a data join gap that makes the candidate alpha unreplayable.

## Do Not Retry Without New Evidence

### Core

- Global position slot count and broad capacity sweeps.
- Same-day global trend-first ordering.
- Broad sector caps, simple sector-persistence entries, and same-sector caps.
- Commodity breakout target widening and mechanical target-width generalization.
- Financials trend wider targets without a new state discriminator.
- Nearby add-on fraction/cap retries around already accepted add-on rules.
- Simple gap-cancel exceptions based only on sector or accepted target-width
  evidence.

### SEC

- Companyfacts or filing-shock weighting without same-accession directional
  surprise/guidance fields.
- Raw capacity above the accepted max-3 sleeve on the same frozen sample.
- Nearby T+1 excess floors around 1%.
- Fixed hold-day sweeps around 10 trading days.
- Paired-filing dedupe and auxiliary earnings 8-K notional scalars on the same
  snapshots.
- Form exclusion or 10-K/10-Q retunes unless the new variable is semantic and
  production-visible.

### Space

- Noisy ticker additions, static pool expansion, or theme ETF timing as a proxy
  for Space quality.
- LLM soft-ranking until there are enough labeled Space forward outcomes.
- Nearby perfect/near-perfect TQS scalar or threshold sweeps.
- Space breakout stop-width, breakout target-width, and generic trend target
  retunes on the same snapshots.
- Data-vendor trend target/risk retunes.
- Lunar/manufacturing target broadening from the RKLB/ASTS launch-connectivity
  result.
- Defense-budget/government-contract broad source scalars; raw EV was high but
  drawdown was too expensive.
- Mission-binary profile scalars until the profile has enough executed outcome
  coverage to matter.

### Event / LLM

- Broad event-source pruning.
- Generic event benchmark gates that are not tied to the state-surface sleeve.
- Prompt-only changes that duplicate quantitative thresholds already defined in
  code.
- Any LLM expansion without an attribution metric.

## Update Rules

Do not append per-experiment diary entries here.

Promote an experiment into this playbook only when it changes a durable
mechanism-level conclusion:

- accepted checkpoint,
- current research priority,
- rejected family / anti-repeat rule,
- production/backtest parity constraint,
- LLM governance boundary,
- or measurement blocker that changes what alpha can be trusted.

When updating this file, write a short synthesis and cite experiment IDs. Keep
the reproduction details, parameters, windows, and full metrics in the
structured experiment logs.

Every new alpha session should still answer the five AGENTS.md questions, use
`docs/backtesting.md` for the three-window protocol, change one independent
causal variable, and declare production/backtest impact before commit.
