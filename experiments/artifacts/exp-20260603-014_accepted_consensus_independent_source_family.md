# exp-20260603-014 accepted free-data cross-source consensus

- Trial family: `accepted_free_data_cross_source_consensus_source_family_count`
- Changed variable: `independent_source_family_count_min_2_with_finra_family_collapsed`
- Decision: `positive_replay_lead_not_promoted_requires_shared_cross_source_adapter`
- Aggregate EV delta: +1.3058
- Aggregate PnL delta: $+23,397.76
- Target trades: 47
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 9 | $7,368.07 | 5.1628 | 5.8860 | +0.7232 | $+7,368.07 | -0.0025 |
| mid_weak | 22 | $4,817.45 | 2.1402 | 2.4133 | +0.2731 | $+4,817.45 | -0.0020 |
| old_thin | 16 | $11,212.24 | 0.5911 | 0.9006 | +0.3095 | $+11,212.24 | -0.0127 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: True
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: True
- `all_windows_pnl_improved`: True
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True
- `source_family_min_count_passed`: True

## Production / Backtest Parity

This experiment changes no production code. A retained result would need a shared default-off adapter that uses the same source-family mapping and parity tests before any daily report, candidate queue, or order surface could change.

## Source Artifacts

- `FUNDAMENTAL_GROWTH_RS_PAPER`: `data/experiments/exp-20260528-017/fundamental_growth_rs_low_liability_support.json`
- `VOLUME_BREADTH_BREAKOUT_PAPER`: `data/experiments/exp-20260529-004/exp_20260529_004_vbb_cost_liquidity_support.json`
- `FINRA_IWM_CONFIRMED_PAPER`: `data/experiments/exp-20260530-007/exp_20260530_007_finra_iwm_same_ticker_cooldown_candidate_pool.json`
- `ALPHA_SCORE_MARKET_REGIME_PAPER`: `data/experiments/exp-20260531-021/exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional.json`
- `FINRA_BORROW_PRESSURE_PAPER`: `data/experiments/exp-20260603-006/exp_20260603_006_finra_borrow_pressure_candidate_pool.json`


## Independent Source-Family Admission

- Min source families: `2`
- FINRA-only selected trades: `0`
- FINRA with non-FINRA selected trades: `9`
- All selected trades pass family count: `True`

```json
{
  "all_selected_have_min_family_count": true,
  "finra_only_trade_count": 0,
  "finra_with_non_finra_trade_count": 9,
  "min_source_family_count": 2,
  "selected_family_combo_counts": {
    "alpha_score_market_regime+companyfacts_growth_quality": 22,
    "alpha_score_market_regime+companyfacts_growth_quality+finra_short_pressure": 1,
    "alpha_score_market_regime+companyfacts_growth_quality+volume_breadth_breakout": 4,
    "alpha_score_market_regime+finra_short_pressure": 7,
    "alpha_score_market_regime+volume_breadth_breakout": 10,
    "companyfacts_growth_quality+volume_breadth_breakout": 2,
    "finra_short_pressure+volume_breadth_breakout": 1
  },
  "selected_raw_source_combo_counts": {
    "ALPHA_SCORE_MARKET_REGIME_PAPER+FINRA_BORROW_PRESSURE_PAPER+FINRA_IWM_CONFIRMED_PAPER": 2,
    "ALPHA_SCORE_MARKET_REGIME_PAPER+FINRA_BORROW_PRESSURE_PAPER+FINRA_IWM_CONFIRMED_PAPER+FUNDAMENTAL_GROWTH_RS_PAPER": 1,
    "ALPHA_SCORE_MARKET_REGIME_PAPER+FINRA_IWM_CONFIRMED_PAPER": 5,
    "ALPHA_SCORE_MARKET_REGIME_PAPER+FUNDAMENTAL_GROWTH_RS_PAPER": 22,
    "ALPHA_SCORE_MARKET_REGIME_PAPER+FUNDAMENTAL_GROWTH_RS_PAPER+VOLUME_BREADTH_BREAKOUT_PAPER": 4,
    "ALPHA_SCORE_MARKET_REGIME_PAPER+VOLUME_BREADTH_BREAKOUT_PAPER": 10,
    "FINRA_BORROW_PRESSURE_PAPER+FINRA_IWM_CONFIRMED_PAPER+VOLUME_BREADTH_BREAKOUT_PAPER": 1,
    "FUNDAMENTAL_GROWTH_RS_PAPER+VOLUME_BREADTH_BREAKOUT_PAPER": 2
  },
  "source_families": {
    "ALPHA_SCORE_MARKET_REGIME_PAPER": "alpha_score_market_regime",
    "FINRA_BORROW_PRESSURE_PAPER": "finra_short_pressure",
    "FINRA_IWM_CONFIRMED_PAPER": "finra_short_pressure",
    "FUNDAMENTAL_GROWTH_RS_PAPER": "companyfacts_growth_quality",
    "VOLUME_BREADTH_BREAKOUT_PAPER": "volume_breadth_breakout"
  },
  "total_trade_count": 47
}
```

No JavaScript was used.
