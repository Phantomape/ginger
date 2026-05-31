# Form 4 Purchase-Pressure Forward Queue

- experiment_id: `exp-20260531-002`
- timestamp: `2026-05-31T01:18:43+00:00`
- decision: `rejected_positive_not_promotable`

## Hypothesis

PIT-safe SEC Form 4 meaningful purchases with unusually high purchase value versus prior 20-day dollar volume may identify cleaner candidate-pool entries than the raw Form 4 queue.

## Three-Window Results

| Window | Core EV | Raw Form4 EV | Pressure EV | Delta vs raw | Delta vs core | Core PnL | Pressure PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.2947 | 0.0 | 0.1319 | $117,072.92 | $119,790.09 | $1,799.63 | 18 -> 21 |
| mid_weak | 2.1402 | 2.2689 | 2.1589 | -0.11 | 0.0187 | $78,110.11 | $78,506.82 | $325.07 | 21 -> 24 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,674.07 | $6.11 | 22 -> 23 |

## Aggregate vs Raw Form4

```json
{
  "after_ev_sum": 8.0447,
  "after_pnl_sum": 237970.98,
  "aggregate_ev_delta": -0.11,
  "aggregate_ev_delta_pct": -0.013489,
  "aggregate_pnl_delta": -1666.23,
  "aggregate_pnl_delta_pct": -0.006953,
  "before_ev_sum": 8.1547,
  "before_pnl_sum": 239637.21,
  "max_drawdown_drift": 0.0016,
  "windows_ev_improved": 0,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 1
}
```

## Aggregate vs Core

```json
{
  "after_ev_sum": 8.0447,
  "after_pnl_sum": 237970.98,
  "aggregate_ev_delta": 0.1506,
  "aggregate_ev_delta_pct": 0.019078,
  "aggregate_pnl_delta": 3119.99,
  "aggregate_pnl_delta_pct": 0.013285,
  "before_ev_sum": 7.8941,
  "before_pnl_sum": 234850.99,
  "max_drawdown_drift": 0.0001,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 3,
  "windows_pnl_regressed": 0
}
```

## Gate

```json
{
  "drawdown_guard_passed": true,
  "failed_reasons": [
    "does_not_improve_raw_form4_queue",
    "not_material_vs_core",
    "target_sample_too_small",
    "positive_pnl_hhi_concentration"
  ],
  "improves_core_cleanly": true,
  "improves_vs_raw_form4": false,
  "material_vs_core": false,
  "max_drawdown_drift_guard": "<= 0.005",
  "passed": false,
  "positive_pnl_by_ticker": {
    "LLY": 1277.77,
    "MSFT": 333.04,
    "MU": 1466.59,
    "UNH": 6.11
  },
  "positive_pnl_hhi": 0.409605,
  "positive_pnl_hhi_guard": "<= 0.35",
  "purchase_pressure_selected_event_trades": 7,
  "sample_guard_passed": false,
  "single_ticker_positive_share": 0.475624,
  "single_ticker_positive_share_guard": "<= 0.50",
  "target_trade_count_min": 8,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ]
}
```

## Event Diagnostics

```json
{
  "events_passing_purchase_pressure_floor": 12,
  "events_with_ownership_delta": 17,
  "events_with_purchase_pressure_ready": 13,
  "lookback_trading_days": 20,
  "min_lookback_trading_days": 10,
  "ownership_delta_floor": 0.1,
  "ownership_delta_floor_event_count": 11,
  "pressure_distribution_sample": [
    {
      "prior_20d_avg_dollar_volume": 29949602886.11,
      "purchase_value_to_prior_20d_dollar_volume": 0.03338806,
      "ticker": "TSLA",
      "total_purchase_value": 999959042.36,
      "usable_trade_date": "2025-09-16"
    },
    {
      "prior_20d_avg_dollar_volume": 7020958368.94,
      "purchase_value_to_prior_20d_dollar_volume": 0.00450191,
      "ticker": "UNH",
      "total_purchase_value": 31607700.31,
      "usable_trade_date": "2025-05-19"
    },
    {
      "prior_20d_avg_dollar_volume": 1215102151.34,
      "purchase_value_to_prior_20d_dollar_volume": 0.00165743,
      "ticker": "DIS",
      "total_purchase_value": 2013942.6,
      "usable_trade_date": "2025-12-16"
    },
    {
      "prior_20d_avg_dollar_volume": 10021133211.05,
      "purchase_value_to_prior_20d_dollar_volume": 0.00078052,
      "ticker": "MU",
      "total_purchase_value": 7821723.4,
      "usable_trade_date": "2026-01-19"
    },
    {
      "prior_20d_avg_dollar_volume": 4188708166.55,
      "purchase_value_to_prior_20d_dollar_volume": 0.00066057,
      "ticker": "LLY",
      "total_purchase_value": 2766928.65,
      "usable_trade_date": "2025-08-13"
    },
    {
      "prior_20d_avg_dollar_volume": 4558550173.48,
      "purchase_value_to_prior_20d_dollar_volume": 0.00021922,
      "ticker": "AMD",
      "total_purchase_value": 999328.0,
      "usable_trade_date": "2025-05-23"
    },
    {
      "prior_20d_avg_dollar_volume": 2480762180.84,
      "purchase_value_to_prior_20d_dollar_volume": 0.00020622,
      "ticker": "UNH",
      "total_purchase_value": 511575.0,
      "usable_trade_date": "2025-01-23"
    },
    {
      "prior_20d_avg_dollar_volume": 4268112730.66,
      "purchase_value_to_prior_20d_dollar_volume": 0.00015167,
      "ticker": "LLY",
      "total_purchase_value": 647360.0,
      "usable_trade_date": "2025-08-14"
    },
    {
      "prior_20d_avg_dollar_volume": 8338115297.29,
      "purchase_value_to_prior_20d_dollar_volume": 0.00014726,
      "ticker": "AVGO",
      "total_purchase_value": 1227870.27,
      "usable_trade_date": "2025-09-12"
    },
    {
      "prior_20d_avg_dollar_volume": 12266147251.75,
      "purchase_value_to_prior_20d_dollar_volume": 0.00011823,
      "ticker": "MSFT",
      "total_purchase_value": 1450220.53,
      "usable_trade_date": "2025-12-15"
    },
    {
      "prior_20d_avg_dollar_volume": 4398351672.4,
      "purchase_value_to_prior_20d_dollar_volume": 0.00011379,
      "ticker": "LLY",
      "total_purchase_value": 500472.53,
      "usable_trade_date": "2025-08-15"
    },
    {
      "prior_20d_avg_dollar_volume": 19385943177.73,
      "purchase_value_to_prior_20d_dollar_volume": 0.00010248,
      "ticker": "MSFT",
      "total_purchase_value": 1986750.0,
      "usable_trade_date": "2026-02-19"
    }
  ],
  "purchase_pressure_floor": 0.0001,
  "raw_forward_event_count": 17,
  "source_status": "loaded",
  "transaction_rows": 27879
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "live_slots_changed": false,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "promotion_blocker_if_positive": "A shared default-off Form 4 purchase-pressure queue/paper adapter must be wired through production and replay before any trade-enabled use.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
