# Production / Backtest Parity Contract

This document is the contract that prevents alpha experiments from creating a
backtester-only strategy. If a rule can change whether the system buys, sells,
adds, reduces, sizes, ranks, gates, or skips a trade, the rule must live in a
shared policy/module or be explicitly listed below as an allowed replay-only
difference.

## Core Rule

`quant/backtester.py` and `quant/run.py` are adapters.

They may load different data sources and handle different outputs, but they
must not each implement their own strategy decisions. Strategy decisions belong
in shared modules such as:

- `quant/signal_engine.py`
- `quant/risk_engine.py`
- `quant/portfolio_engine.py`
- `quant/regime_exit.py`
- `quant/production_parity.py`
- future `quant/policy/*.py` modules

## Live-Realistic Execution Envelope

An alpha is not live-ready merely because a default-off paper sleeve has
positive EV. The accepting experiment must also define and measure the
execution envelope that would be used with real capital:

- intended notional or sizing rule;
- capital cap and exposure limits;
- liquidity and slippage assumptions;
- portfolio displacement or slot interaction;
- order timing and order type semantics;
- kill switch and failure handling;
- production/backtest parity for all of the above.

If that envelope is measured and unchanged, a later `trade_enabled=true` release
can be treated as an operational release checklist/config change. If it was not
measured, activation requires a narrow activation-envelope Gate 1-4 that tests
the missing execution constraints; it must not search for a new alpha signal.

Legacy matrix rows that say "separate Gate 1-4 trade adapter" should be read
through this rule: the required work is a live-realistic execution-envelope
evaluation unless the accepted experiment already supplied it.

## Paper Evidence vs Executable Sizing

`quant/paper_sleeve_execution_contract.py` is the shared fail-closed boundary
between paper-ledger economics and an executable experiment size. A paper
notional measures one sleeve's evidence and PnL; it is not an order amount.
Daily paper surfaces must expose `execution_sizing_contract`, and `run.py` must
publish the aggregate `paper_sleeve_execution_contract` for every paper sleeve
it builds.

Pending event rows freeze `paper_notional_usd` when the signal is created.
Legacy pending rows are backfilled once before they can fill. Later config
changes must not resize those rows. `experiment_notional_usd` remains `null`
unless the snapshot declares a complete execution envelope, passes its forward
gate, and explicitly enables its trade adapter. Missing fields fail closed and
must never fall back to the paper notional. This contract is attribution-only:
it cannot change candidates, paper PnL, core sizing, or orders.

## Read-Only SEC Semantic Provenance

`quant/run.py` passes the daily `sec_filing_text` artifact into the shared SEC
financial-report T+1 queue builder. The queue may attach accession-matched
`language_bucket`, phrase-hit, guidance-hit, `text_event_type`, and
`sec_text_coverage_status` fields for paper-sleeve attribution.

These fields are production-visible context only. They must not affect entry,
ranking, sizing, exit, or orders until a separate Gate 1-4 experiment promotes a
shared policy and updates `docs/production_backtest_parity_matrix.md`.

## Default-Off OHLCV Paper Sleeve Stale-Price Guard

`broad_market_paper_sleeve.py`, `ai_optical_paper_sleeve.py`,
`volatility_contraction_paper_sleeve.py`, `volume_breadth_breakout_paper_sleeve.py`,
`fundamental_growth_rs_paper_sleeve.py`, and
`post_earnings_underpriced_drift_paper_sleeve.py`, and
`macro_relief_leadership_paper_sleeve.py`, and
`industry_relative_laggard_repair_paper_sleeve.py`, and
`industry_stable_core_flow_paper_sleeve.py` must only fill pending
entries, advance observed hold days, close paper positions, or accept
OHLCV-derived paper candidates when the relevant OHLCV data contains an exact
`as_of` row. Production weekend, holiday, and data-lag runs may report metadata,
but stale latest-prior prices must not mutate those paper ledgers.

## Default-Off Direct Price-Map Sleeve Price-As-Of Guard

`run.py` must pass ticker-level `open_price_dates` and `current_price_dates`
derived from the loaded OHLCV rows into the direct price-map paper sleeves.
`form4_event_sleeve.py`, `sec_negative_event_sleeve.py`,
`sec_event_sleeve.py`, `sec_leadership_event_sleeve.py`,
`sec_financial_report_event_sleeve.py`, `state_surface_sleeve.py`, and
`core_misfit_paper_sleeve.py` must ignore a ticker's open/current price when
the provided price date is not exactly the snapshot `as_of` date. Historical
fixtures may omit price-date maps for backward compatibility; production must
provide them so weekend, holiday, and data-lag runs cannot fill, advance, or
close paper ledgers with stale latest-prior prices.

## Operator Open-Position Group Schema

`operator_inputs/open_positions.json` may physically group real account
holdings under `positions`, `core_positions`, and `observations`. Production
readers must treat all three groups as real account exposure for portfolio
value, heat, current-position exits, already-held filtering, news/watchlist
coverage, LLM prompt context, and pending action reconciliation.

Core entry-slot accounting is narrower: only rows with
`slot_policy=consumes_core_slot`, a core sleeve, or a core strategy tag consume
core strategy capacity. Rows with `slot_policy=no_core_slot` still count toward
total account heat/cash/risk, but not toward core entry slots. Shared code
should use `quant/open_position_schema.py` instead of manually reading only
`payload["positions"]`.

The same ownership boundary applies to the program-layer `FIRE` lock used by
the LLM preflight surface: all real positions still appear in exit states,
warnings, current prices, news context, heat, and risk review, but only
core-slot positions may promote a `CRITICAL_EXIT` into account-level
`FIRE/new_trade_locked`. Legacy, manual, observation, FOMO, and other
`no_core_slot` rows remain visible as risk work but must not freeze core
strategy entry capacity by themselves.

## Adapter Matrix

Per-adapter shared-source, replay, production, allowed-difference, and promotion-state rows live in `docs/production_backtest_parity_matrix.md`.

Keep this file focused on the core contract. Add or update adapter rows in the matrix file when a shared default-off helper is accepted, retained for forward observation, or promoted toward live execution.

## Experiment Requirements

Every strategy-affecting experiment must state its production impact:

```json
{
  "production_impact": {
    "shared_policy_changed": true,
    "backtester_adapter_changed": true,
    "run_adapter_changed": true,
    "replay_only": false,
    "parity_test_added": true
  }
}
```

Use `replay_only: true` only when the difference is caused by data availability
that cannot exist in historical replay, such as LLM/news archives. Replay-only
does not allow duplicate business logic.

## Exit Advisory Replay Caveat

Production held-position exits have two layers:

- code computes context and advisory rules such as `SIGNAL_TARGET`,
  `PROFIT_LADDER_30`, `PROFIT_LADDER_50`, and `TIME_STOP`;
- the LLM / daily workflow can turn those rules into `REDUCE` or `EXIT`
  instructions, and `pending_actions.py` can keep unexecuted `REDUCE`/`EXIT`
  actions alive across days.

The canonical backtest does not execute that full advisory lifecycle. It
simulates full-position `stop_price` and `target_price` fills, plus only the
shared replay hooks that have been explicitly implemented and accepted. The
current gap is intentionally surfaced as
`result["known_biases"]["exit_policy_unreplayed"]`, with non-executing rule
counts and realized outcome grouping in
`result["exit_advisory_shadow_attribution"]`.

Do not close this gap by simply reinterpreting `target_price` as a
`SIGNAL_TARGET` partial reduce. `exp-20260429-032` tested that replay-only
variant and rejected it after EV and PnL regressed in all three fixed windows.
The next valid step is shadow attribution for advisory exit rules, followed by
a complete shared lifecycle policy only if the attribution supports it.

Legacy-basis positions are a separate production visibility case. When an
explicit `target_price` is reached on a legacy-basis holding, production may
surface `LEGACY_TARGET_REVIEW` so the operator can inspect stale or tactical
targets, but this rule must not map to `TARGET_EXIT`, `HIGH_REDUCE`, or any
automatic order.

## Merge Blockers

Block or roll back an experiment when any of the following is true:

- A strategy parameter is changed in `backtester.py` but not sourced from
  `quant/constants.py` or a shared policy module.
- `backtester.py` implements a buy/sell/add/reduce/size/rank/gate rule that
  `run.py` cannot call or expose.
- `run.py` presents a trade candidate that the backtester entry loop would skip
  for heat, slot, already-held, or no-shares reasons.
- A prompt/schema change asks the LLM to make a hard risk decision that code
  already owns.
- A measurement repair changes strategy behavior without a fixed-window check
  proving the backtest baseline did not move, unless the behavior change is the
  explicit experiment variable.

## Required Tests

When adding or changing shared policy behavior, add at least one focused test
that runs the same synthetic scenario through the shared helper. For adapter
parity, the test should prove the production artifact exposes the same action
that the backtester would schedule or execute.

Minimum coverage examples:

- Day-2 follow-through winner creates a backtest add-on and production
  `addon_actions`.
- Trailing stop rule computes the same reduce percentage and whole-share count
  for production prompts and backtest replay.
- One remaining slot defers `breakout_long` consistently.
- Heat-capped portfolios do not publish executable new-entry candidates.
- Prompt schema fields exist when production emits a new action type.

## Documentation Updates

If a decision point changes, update this file in the same commit as the code.
If the change is an accepted mechanism-level conclusion, also update
`docs/alpha-optimization-playbook.md`. If it is a single experiment result,
write the detailed record to `experiments/logs/<experiment_id>.json`.
