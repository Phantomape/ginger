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
| Financials sector-leader trend position cap | `portfolio_engine.py` | required | required | none |
| Financials mid-dispersion sector-leader trend position cap | `portfolio_engine.py` | required | required | none |
| Commodity near-high trend position cap | `portfolio_engine.py` | required | required | none |
| RS20 entry-state sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | none |
| Signal-day own-green-candle sizing top-up | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| RS60 top-quintile stock sizing top-up | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Price-vs-200MA extension sizing top-up | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Trend-only price-vs-200MA extension sizing top-up | `feature_layer.py`, `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Core confirmed-quality sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Green-deceleration quality non-consumer sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Technology trend DTE residual risk sizing | `portfolio_engine.py` / `constants.py` | required | required | none |
| TSM core long risk sizing | `portfolio_engine.py` / `constants.py` | required; `tsm_core_risk_multiplier_applied` is captured in sizing attribution | required through the same `portfolio_engine.size_signals` path used by production | ticker-specific only; do not generalize to semiconductors without a separate experiment |
| ISRG core long risk sizing | `portfolio_engine.py` / `constants.py` | required; `isrg_core_risk_multiplier_applied` is captured in sizing attribution | required through the same `portfolio_engine.size_signals` path used by production | ticker-specific only; do not generalize to Healthcare without a separate experiment |
| Clean SPY-relative signal-day sizing top-up | `risk_engine.py`, `portfolio_engine.py` | required | required | data date only |
| Clean SPY-relative signal-day position cap | `portfolio_engine.py` | required | required | data date only |
| Clean SPY cap-only leader position cap | `portfolio_engine.py` | required | required | data date only |
| Clean SPY cap-only RS20 leader position cap | `portfolio_engine.py` | required | required | data date only |
| Pilot sleeve sizing and slot priority | `pilot_sleeve.py` after `portfolio_engine.size_signals` | default off; `--include-pilot-sleeve` applies the shared pilot scalar and `trade_quality_score -> confidence -> risk/reward` slot policy in PIT replay | required for `pilot_signals`; production metadata marks pilot sleeve candidate ranking as strategy-affecting | canonical core backtest stays core-only unless the flag is explicit |
| Pilot outcome attribution | `candidate_competition_logger.py`, `performance_engine.py`, `report_generator.py` | `--include-pilot-sleeve` computes in-memory direct PnL, cash-relative PnL, replacement value, and risk-adjusted replacement value | daily run reports direct PnL, cash-relative PnL, replacement value, and pending counterfactual coverage | backtester replay must not write `data/ledgers/pilot_competition_decisions.jsonl`; production appends real decisions only |
| SEC negative-reaction event queue | `sec_event_queue.py`, `sec_negative_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical event-sleeve replays must use shared queue semantics before promotion | daily run emits default-off queue plus paper sleeve state/snapshots only | observe-only until forward replacement-value evidence and an explicit shared trade adapter exist |
| SEC governance/procedural event queue | `sec_event_queue.py`, `sec_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical event-sleeve replays must use shared queue semantics before promotion | daily run emits default-off queue plus paper sleeve state/snapshots only | observe-only until forward replacement-value evidence and an explicit shared trade adapter exist |
| SEC financial-report T+1 drift queue | `sec_event_queue.py`, `sec_financial_report_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical replays must use shared queue/sleeve semantics before promotion | daily run emits default-off non-platform financial-report positive T+1 excess >= 1% queue plus paper sleeve state/snapshots at the accepted $15k base notional, with non-10-Q `periodic_report` rows tracked at 1.25x paper notional, 10-Q `periodic_report` rows tracked at 2.00x paper notional, covered `neutral_or_mixed_language` rows with `t1_excess_return_vs_spy <= 2%` tracked with an additional 2.00x neutral-underreaction paper notional scalar, those accepted neutral-underreaction rows with `spy_t1_return >= -0.5%` tracked with an additional 1.50x market-context paper notional scalar, and covered `earnings_release_text` rows with `spy_t1_return >= -0.5%` tracked with an additional 1.10x earnings-release market-context paper notional scalar | observe-only until closed forward replacement-value evidence and an explicit shared trade adapter exist |
| Default-off external event overlay bundle | `event_sleeve_bundle.py`, `state_surface_sleeve.py`, `form4_event_sleeve.py`, `sec_negative_event_sleeve.py`, `sec_event_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical bundle replays must use shared source queues/sleeves, the shared state-surface add-on annotation, rotation-surface paper tilt, front-rank rotation paper tilt, broad-breadth event paper tilt, sec-governance source-quality paper tilt, negative-reaction event paper tilt, and the shared forward-gated trade-plan helper before promotion | daily run emits aggregate default-off bundle attribution, normalized candidate schema, source-priority dedupe, state-surface paper add-on eligibility, rotation-surface, front-rank rotation, broad-breadth, sec-governance source-quality, and negative-reaction tilt counts, forward gate, kill-switch status, and default-blocked trade-plan status only | observe-only until closed forward outcomes pass the shared gate and the explicit trade adapter is enabled |
| Default-off broad-market leadership paper sleeve | `broad_market_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical broad-market replays must use the shared `price_floor_40` feature/filter helper, candidate exclusion semantics, `[1.20, 1.00, 0.80]` source-rank paper-notional profile, the shared `ret5 <= 0.02` low-extension `1.15x` paper-notional scalar, the shared `realized_volatility_20 >= 0.055` high-volatility `1.15x` paper-notional scalar, the shared `positive_day_ratio_20 >= 0.55` trend-persistence `1.15x` paper-notional scalar, 20-trading-day paper hold, and concentration guard before promotion | daily run emits the default-off `BROAD_MARKET_LEADERSHIP_PAPER` candidate queue with the shared `[1.20, 1.00, 0.80]` source-rank paper-notional profile, the shared low-extension, high-volatility, and trend-persistence paper-notional metadata/scalars, pending/open/closed paper ledger state, source coverage metadata, forward paper gate, and report block only when a candidate universe feed is present | observe-only until closed forward replacement-value outcomes pass a separate gate and an explicit trade adapter is enabled |
| Default-off state-surface satellite | `state_surface_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical state-surface replays must use the shared queue/sleeve scoring, rotation-only surface eligibility, benchmark-momentum participation gate, ret20_excess_spy candidate floor, top-five daily candidate count, shared market-regime classifier, regime-aware queue-rank paper-notional profile, candidate-breadth rank-notional override, score-compression rank-notional override, rank-2 ret20-excess leadership rank-notional override, rank-2 ret20 plus score-gap rank-notional override, rank-1 ret20 dominance plus score-gap rank-notional override, top-2 Technology sector-cohesion rank-notional override, residual rank-1 60-day return rank-notional override, residual score-expansion rank-notional override, residual rank-1 score-isolation rank-notional override, recent same-ticker repeat notional scalar, rank-3 near-high support notional scalar, rank-2 near-high support notional scalar, rank-2 volume-confirmation notional scalar, rank-3 volume-confirmation notional scalar, top-3 positive ret5 follow-through notional scalar, broad-breadth market-state notional scalar, rank-queue alignment notional scalar, sleeve-capacity notional scalar, queue-lag support notional scalar, absolute-score support notional scalar, rank-depth score-volume support notional scalar, low-extension support notional scalar, and tail-aware forward promotion gate before promotion | daily run emits full scored-candidate audit, top-five rotation_breakout_leadership-only default-off paper candidates with the shared `[1.5, 1.25, 1.0, 0.75, 0.5]` default queue-rank paper notional profile, the accepted `chop` override `[1.625, 1.3, 1.0, 0.7, 0.375]`, the accepted candidate-breadth `>= 4` override `[1.6625, 1.315, 1.0, 0.675, 0.35]`, the accepted top-three score-compression `<= 0.40` override `[1.35, 1.45, 1.05, 0.675, 0.35]`, the accepted rank-2 ret20-excess leadership `>= 0.005` override `[1.3, 1.55, 1.1, 0.675, 0.35]`, the accepted rank-2 ret20-excess plus rank-1 score-gap `>= 0.30` override `[1.0, 1.85, 1.1, 0.675, 0.35]`, the accepted rank-1 ret20-excess dominance `>= 0.15` plus score-gap `>= 0.45` override `[1.6, 1.4, 1.0, 0.675, 0.35]`, the accepted top-2 Technology sector-cohesion override `[1.45, 1.7, 1.15, 0.675, 0.35]`, the accepted residual rank-1 60-day return `>= 0.50` override `[1.2, 1.85, 1.1, 0.675, 0.35]`, the accepted residual score-expansion `score_top3_spread >= 0.40` plus candidate-breadth `>= 4` override `[1.85, 1.25, 1.0, 0.675, 0.35]`, the accepted residual rank-1 score-isolation `score_top_to_second_gap >= 0.20` within the score-expansion branch override `[2.2, 1.0, 0.7, 0.675, 0.35]`, the accepted recent same-ticker repeat rule that scales a repeat paper entry by `1.50` when the ticker appeared in sleeve state within `60` calendar days, the accepted rank-3 near-high support rule that scales only rank 3 by `1.50` when `rank3_near_high_60 >= 0.98`, the accepted rank-2 near-high support rule that scales only rank 2 by `1.50` when the candidate's own `features.near_high_60 >= 0.975`, the accepted rank-2 volume-confirmation rule that scales only rank 2 by `1.10` when the candidate's own `features.volume_ratio_20 >= 1.10`, the accepted rank-3 volume-confirmation rule that scales only rank 3 by `1.50` when the candidate's own `features.volume_ratio_20 >= 1.10`, the accepted top-3 positive ret5 follow-through rule that scales only ranks 1-3 by `1.25` when the candidate's own `features.ret5 > 0.0`, the accepted broad-breadth support rule that scales candidates by `1.10` when `breadth_bucket == broad_breadth`, the accepted rank-queue alignment rule that scales candidates by `1.15` when `rank == queue_rank`, the accepted sleeve-capacity rule that scales all selected paper candidates by `1.15`, the accepted queue-lag support rule that scales candidates by `1.25` when `rank > queue_rank`, the accepted absolute-score support rule that scales candidates by `1.15` when `score >= 0.90`, the accepted rank-depth score-volume support rule that scales queue-rank 2-3 candidates by `1.075` when `score >= 0.90` and `features.volume_ratio_20 >= 1.10`, the accepted low-extension support rule that scales candidates by `1.05` when `features.ret5 <= 0.02`, plus market-regime/profile/candidate-breadth/score-dispersion/rank2-ret20-lead/rank1-ret20-dominance/top2-sector-cohesion/rank1-ret60-residual/score-expansion/rank1-score-isolation/recent-repeat/rank3-near-high-support/rank2-near-high-support/rank2-volume-confirmation/rank3-volume-confirmation/top3-ret5-followthrough/broad-breadth-support/rank-queue-alignment/sleeve-capacity/queue-lag-support/absolute-score-support/rank-depth-score-volume/low-extension-support metadata, surface-blocked audit rows, benchmark-momentum allow/block reason, ret20_excess_spy allow/block reason, pending/open/closed ledger state, a forward paper gate, and read-only tail diagnostics for closed paper outcomes only | observe-only until closed forward replacement-value outcomes pass the shared tail-aware gate and an explicit trade adapter is enabled |
| Default-off low-deployment ETF overlay | `low_deployment_etf_overlay.py`, `report_generator.py` | default core backtests do not trade it; historical overlay replays must use the shared prior-close trend/momentum selector before promotion | daily run emits paper-only ETF overlay candidate/outcome attribution, low-deployment state, and a forward paper gate only | observe-only until closed forward outcomes, cash semantics, and an explicit trade adapter pass |
| Default-off core-misfit paper sleeve | `core_misfit_paper_sleeve.py`, `report_generator.py` | default core backtests do not trade it; historical evidence is replay-only attribution until a separate adapter exists | daily run copies only `trend_long` `TSM` / `ISRG` / `V` / `DDOG` selected or slot-sliced core long signals into a no-trade / fast-long / inverse-short paper ledger only, per `exp-20260518-022` | observe-only; no live shorting, no core exclusion, no order/ranking/sizing changes until closed forward paper outcomes pass a separate gate |
| Default-off space catalyst shadow universe | `space_catalyst_sleeve.py`, `universe_manager.py`, `pilot_sleeve.py` | default core backtests do not trade it; space records are research/quarantine with zero live slots; forward hypotheses must use shared Space metadata/helpers before promotion | daily run may surface observe-only candidate pool, LLM event fields, default-off sub-bucket risk/target-hypothesis metadata/helpers, perfect-TQS, near-perfect trend TQS, peer-nonleader breakout risk, IWM-relative small-cap appetite risk, IWM-plus-peer-leader trend risk, launch/lunar theme-segment risk, liquidity-tier anchor/watch risk, official customer-source risk, customer-source peer-leader risk, government-contract peer-leader risk, financing/dilution event-guard profile risk, multi-event official catalyst-depth risk, single-event defense-only risk, attention-overlay-with-official-catalyst risk, source-diversity risk, source-diversity peer-leader risk, source-diversity IWM-leader risk, source-diversity peer+IWM-leader risk, source-diversity trend risk, source-diversity peer-nonleader trend risk, source-diversity peer-nonleader near-perfect trend risk, source-diversity dual-catalyst trend risk, source-diversity dual-catalyst IWM-leader trend risk, source-diversity dual-catalyst same-theme winner trend risk, source-diversity dual-catalyst near-perfect trend risk, source-diversity dual-catalyst financing-profile trend risk, source-diversity dual-catalyst benchmark-breadth trend risk, forward replacement-positive 10d risk metadata/helpers, forward same-theme replacement-strength metadata/helpers, forward same-theme replacement-strength trend-only metadata/helpers, forward same-theme replacement-strength IWM-leader trend metadata/helpers, forward same-theme replacement-strength company-source trend metadata/helpers, delayed-absorption trend metadata/helpers, benchmark-breadth trend metadata/helpers, benchmark-breadth same-theme strength trend metadata/helpers, benchmark-breadth peer-nonleader trend metadata/helpers, benchmark-breadth IWM-leader trend metadata/helpers, defense-budget delayed benchmark trend metadata/helpers, the one-slot blocked Space production observation plan, and the Space event-state shadow ledger only | observe-only until closed forward replacement-value evidence and a separate pilot promotion create explicit live slots |
| Portfolio heat | `portfolio_engine.py` | required | required | simulated vs latest prices |
| Already-held handling | shared adapter policy | required | required | none |
| Entry candidate gates | `production_parity.py` | required | required | none |
| Regime risk sizing override | `production_parity.py` | required | required | none |
| Scarce-slot rank-1 post-sizing top-up | `production_parity.py` / `constants.py` | required; `scarce_slot_rank1_risk_multiplier_applied` is captured in trade sizing attribution | required through the same `plan_entry_candidates` path used by production | none; applies only after slot slicing when exactly one slot remains |
| Ample-slot stock rank-1 post-sizing top-up | `production_parity.py` / `constants.py` | required; `ample_slot_stock_rank1_risk_multiplier_applied` is captured in trade sizing attribution | required through the same `plan_entry_candidates` path used by production | none; applies only after slot slicing when at least four slots remain and sector is known and not ETF / Commodities |
| Entry open cancel | `production_parity.py` / signal `entry_note` | simulated next open | instruction for next-session execution | production cannot know next open until execution |
| Scarce-slot routing | `production_parity.py` / backtester config | required | required | backtester records attribution; production emits plan |
| Follow-through add-ons | `production_parity.py` / backtester config | schedule/execute in simulation with shared effective-stop heat cap | emit explicit `addon_actions` with the same cap policy | fill price timing only |
| Rejected early relative-weakness exit scout | `production_parity.py` / explicit experiment config | disabled by default; used only by `exp-20260513-112` replay | not emitted in daily production because Gate 4 failed | rejected replay-only experiment; promotion would require `run.py` wiring and parity tests |
| Production advisory exit context | `trend_signals.py`, `position_manager.py`, `llm_advisor.py` | disclosed as `known_biases.exit_policy_unreplayed`; not executed except explicit shared replay hooks | required for daily report / LLM prompt / pending action memory; `LEGACY_TARGET_REVIEW` is surfaced as non-executable manual review only | advisory rules require shadow attribution before promotion |
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
