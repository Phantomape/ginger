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

## Decision Matrix

| Decision point | Shared source | Backtester use | Production use | Allowed difference |
| --- | --- | --- | --- | --- |
| Universe and features | `data_layer.py`, `feature_layer.py` | historical/snapshot OHLCV | latest OHLCV | data date only |
| Entry signal generation | `signal_engine.py` | required | required | none |
| Risk enrichment / targets | `risk_engine.py`, `regime_exit.py` | required | required | none |
| Position sizing | `portfolio_engine.py` | required | required | fill price may differ |
| Portfolio heat | `portfolio_engine.py` | required | required | simulated vs latest prices |
| Already-held handling | shared adapter policy | required | required | none |
| Entry candidate gates | `production_parity.py` | required | required | none |
| Regime risk sizing override | `production_parity.py` | required | required | none |
| Entry open cancel | `production_parity.py` / signal `entry_note` | simulated next open | instruction for next-session execution | production cannot know next open until execution |
| Scarce-slot routing | `production_parity.py` / backtester config | required | required | backtester records attribution; production emits plan |
| Follow-through add-ons | `production_parity.py` / backtester config | schedule/execute in simulation | emit explicit `addon_actions` | fill price timing only |
| Exit rule computation | `trend_signals.py`, related shared rules | required | required | backtester simulates fills |
| Trailing partial reductions | `production_parity.py` / backtester `REPLAY_PARTIAL_REDUCES` | opt-in schedule/execute in simulation; disabled by shared policy unless explicitly enabled for replay comparison | disabled by shared policy | default backtest keeps legacy exits unless replay flag is on |
| Pending unexecuted actions | `pending_actions.py` | normally not replayed | required | production-only execution memory |
| LLM veto / ranking | `llm_advisor.py`, `llm_replay` path | replay archive when enabled | live prompt/response | archive coverage disclosed |
| News veto | `filter.py`, `news_replay.py` | replay archive when enabled | live news files | archive coverage disclosed |
| Fill / slippage | fill/backtester execution model | simulated next open | manual/live execution | disclosed execution model |

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
write the detailed record to `docs/experiments/logs/<experiment_id>.json`.
