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
| Universe governance / pilot eligibility | `universe_manager.py`, `universe_adapter.py`, `pilot_sleeve.py` | point-in-time disclosure by default; `--include-pilot-sleeve` replays trade-enabled pilot eligibility day by day | daily run can emit separate `pilot_signals` for trade-enabled pilot records | pilot started on `2026-05-01`, so pre-activation historical windows cannot treat it as then-known production universe |
| Entry signal generation | `signal_engine.py` | required | required | none |
| Risk enrichment / targets | `risk_engine.py`, `regime_exit.py` | required | required | none |
| Sector-relative sizing features | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Position sizing | `portfolio_engine.py` | required | required | fill price may differ |
| SPY-relative leader position cap | `portfolio_engine.py` | required | required | none |
| RS20 entry-state sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | none |
| Pilot sleeve sizing and slot priority | `pilot_sleeve.py` after `portfolio_engine.size_signals` | default off; `--include-pilot-sleeve` applies the shared pilot scalar and `trade_quality_score -> confidence -> risk/reward` slot policy in PIT replay | required for `pilot_signals`; production metadata marks pilot sleeve candidate ranking as strategy-affecting | canonical core backtest stays core-only unless the flag is explicit |
| Pilot outcome attribution | `candidate_competition_logger.py`, `performance_engine.py`, `report_generator.py` | `--include-pilot-sleeve` computes in-memory direct PnL, cash-relative PnL, replacement value, and risk-adjusted replacement value | daily run reports direct PnL, cash-relative PnL, replacement value, and pending counterfactual coverage | backtester replay must not write `data/pilot_competition_decisions.jsonl`; production appends real decisions only |
| SEC negative-reaction event queue | `sec_event_queue.py`, `sec_negative_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical event-sleeve replays must use shared queue semantics before promotion | daily run emits default-off queue plus paper sleeve state/snapshots only | observe-only until forward replacement-value evidence and an explicit shared trade adapter exist |
| SEC governance/procedural event queue | `sec_event_queue.py`, `sec_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical event-sleeve replays must use shared queue semantics before promotion | daily run emits default-off queue plus paper sleeve state/snapshots only | observe-only until forward replacement-value evidence and an explicit shared trade adapter exist |
| SEC financial-report T+1 drift queue | `sec_event_queue.py`, `sec_financial_report_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical replays must use shared queue/sleeve semantics before promotion | daily run emits default-off non-platform financial-report positive T+1 excess queue plus paper sleeve state/snapshots only | observe-only until closed forward replacement-value evidence and an explicit shared trade adapter exist |
| Default-off external event overlay bundle | `event_sleeve_bundle.py`, `state_surface_sleeve.py`, `form4_event_sleeve.py`, `sec_negative_event_sleeve.py`, `sec_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical bundle replays must use shared source queues/sleeves, the shared state-surface add-on annotation, rotation-surface paper tilt, and the shared forward-gated trade-plan helper before promotion | daily run emits aggregate default-off bundle attribution, normalized candidate schema, source-priority dedupe, state-surface paper add-on eligibility, rotation-surface tilt counts, forward gate, kill-switch status, and default-blocked trade-plan status only | observe-only until closed forward outcomes pass the shared gate and the explicit trade adapter is enabled |
| Default-off state-surface satellite | `state_surface_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical state-surface replays must use the shared queue/sleeve scoring and benchmark-momentum participation gate before promotion | daily run emits default-off state-surface paper candidates, benchmark-momentum allow/block reason, pending/open/closed ledger state, and a forward paper gate only | observe-only until closed forward replacement-value outcomes pass the shared gate and an explicit trade adapter is enabled |
| Default-off low-deployment ETF overlay | `low_deployment_etf_overlay.py`, `report_generator.py` | default core backtests do not trade it; historical overlay replays must use the shared prior-close trend/momentum selector before promotion | daily run emits paper-only ETF overlay candidate/outcome attribution, low-deployment state, and a forward paper gate only | observe-only until closed forward outcomes, cash semantics, and an explicit trade adapter pass |
| Default-off space catalyst shadow universe | `space_catalyst_sleeve.py`, `universe_manager.py`, `pilot_sleeve.py` | default core backtests do not trade it; space records are research/quarantine with zero live slots; forward hypotheses must use shared Space metadata/helpers before promotion | daily run may surface observe-only candidate pool, LLM event fields, default-off sub-bucket risk/target-hypothesis metadata/helpers, and the Space event-state shadow ledger only | observe-only until closed forward replacement-value evidence and a separate pilot promotion create explicit live slots |
| Portfolio heat | `portfolio_engine.py` | required | required | simulated vs latest prices |
| Already-held handling | shared adapter policy | required | required | none |
| Entry candidate gates | `production_parity.py` | required | required | none |
| Regime risk sizing override | `production_parity.py` | required | required | none |
| Entry open cancel | `production_parity.py` / signal `entry_note` | simulated next open | instruction for next-session execution | production cannot know next open until execution |
| Scarce-slot routing | `production_parity.py` / backtester config | required | required | backtester records attribution; production emits plan |
| Follow-through add-ons | `production_parity.py` / backtester config | schedule/execute in simulation with shared effective-stop heat cap | emit explicit `addon_actions` with the same cap policy | fill price timing only |
| Production advisory exit context | `trend_signals.py`, `position_manager.py`, `llm_advisor.py` | disclosed as `known_biases.exit_policy_unreplayed`; not executed except explicit shared replay hooks | required for daily report / LLM prompt / pending action memory | advisory rules require shadow attribution before promotion |
| Backtest price exits | `backtester.py` execution model | full-position `stop_price` / `target_price` fills | manual/live execution from reported actions | `target_price` semantic gap disclosed |
| Trailing partial reductions | `production_parity.py` / backtester `REPLAY_PARTIAL_REDUCES` | replay container on by default; pure trailing trims disabled by shared policy unless explicitly enabled for comparison | disabled by shared policy | opt out only for diagnostics |
| Pending unexecuted actions | `pending_actions.py` | disclosed as `known_biases.pending_action_replay_unreplayed`; not replayed from current ledger | required | production-only execution memory without point-in-time ledger snapshots |
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
