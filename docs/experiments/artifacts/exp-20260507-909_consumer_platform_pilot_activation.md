# exp-20260507-909 Consumer Platform Pilot Activation

## Classification

- `experiment_type`: alpha_search
- `change_type`: candidate_pool_pilot_activation
- `single_causal_variable`: consumer_digital_platform_research_to_pilot_status
- `decision`: accepted_forward_pilot

## Hypothesis

HOOD, RBLX, and SOFI may add event-sensitive consumer digital platform alpha that the core A/B universe misses. Prior static tests were positive but unstable, so direct core promotion remains unjustified. The alpha search step with the best risk/reward is a bounded forward pilot sleeve activation that can measure replacement value without competing for core slots.

## Historical Check

This does not repeat the recent rejected directions:

- `exp-20260505-011`: consumer digital platform sub-basket was positive but unstable; direct static promotion rejected.
- `exp-20260505-020`: simple governance gates failed to make the basket robust; forward-governed observation remained the next valid path.
- `exp-20260507-904`: broad event-sensitive universe expansion did not beat core average PnL in any fixed window.
- Recent RS20 leader, gap-up, cluster-tail, runner, earnings, estimate-revision, options, and LLM soft-ranking paths either failed Gate 4 or still lack enough outcome rows.

## Change

Updated `data/universe_registry.json` and `data/universe_events.jsonl` so:

- HOOD, RBLX, and SOFI move from `research` to `pilot`.
- `first_trade_allowed_as_of` and `status_effective_as_of` are both `2026-05-08`.
- `competes_for_core_slots` remains `false`.
- `max_capital_scalar` remains `0.35`.
- `max_risk_scalar` remains `0.2`.
- `requires_event_guard` remains `true`.
- `event_guard_profile` remains `high_beta_consumer_platform_sensitive`.

No strategy code, ranking code, sizing code, or backtester adapter code changed.

## Three-Window Gate

The canonical fixed windows end before the 2026-05-08 pilot effective date, so core metrics should not move. They did not move.

| Window | Before EV | After EV | Before PnL | After PnL | Sharpe daily | Max DD | Trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong 2025-10-23 to 2026-04-21 | 3.6257 | 3.6257 | 82030.12 | 82030.12 | 4.42 | 5.39% | 20 | 75.0% |
| mid_weak 2025-04-23 to 2025-10-22 | 1.5478 | 1.5478 | 57542.74 | 57542.74 | 2.69 | 8.79% | 21 | 52.4% |
| old_thin 2024-10-02 to 2025-04-22 | 0.3359 | 0.3359 | 26242.68 | 26242.68 | 1.28 | 9.05% | 22 | 40.9% |

`expected_value_score_delta` is `0.0` in all three fixed windows. This is expected and required for PIT safety, not evidence of historical alpha.

## Production Parity

The pilot sleeve already has shared production/backtest plumbing:

- `run.py` consumes `pilot_records_as_of`, pilot signals, pilot sizing, and counterfactual snapshots.
- `backtester.py` uses the same pilot sleeve policy when `--include-pilot-sleeve` is enabled.
- This experiment changes only universe governance data and does not add a backtester-only rule.

`production_impact`:

- `shared_policy_changed`: false
- `backtester_adapter_changed`: false
- `run_adapter_changed`: false
- `replay_only`: false
- `core_universe_changed`: false
- `alters_pilot_sleeve_orders_after_effective_date`: true
- `competes_for_core_slots`: false

## Verification

Backtests:

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-10-23 --end 2026-04-21 --ohlcv-snapshot data\ohlcv_snapshot_20251023_20260421.json
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-04-23 --end 2025-10-22 --ohlcv-snapshot data\ohlcv_snapshot_20250423_20251022.json
.\.venv\Scripts\python.exe quant\backtester.py --start 2024-10-02 --end 2025-04-22 --ohlcv-snapshot data\ohlcv_snapshot_20241002_20250422.json
```

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest quant\test_universe_manager.py quant\test_universe_adapter.py quant\test_pilot_sleeve.py quant\test_backtester_pilot_sleeve.py -q
```

Result: `17 passed`.

## Decision

Accepted as a forward pilot alpha activation, not as a historical core alpha improvement.

The next review should compare closed pilot outcomes against recorded displaced core or cash alternatives after 30-60 trading days or enough closed pilot trades. The main risk is that a high-beta consumer platform candidate consumes the single pilot slot during a weak tape and blocks a better AI-infra pilot opportunity.
