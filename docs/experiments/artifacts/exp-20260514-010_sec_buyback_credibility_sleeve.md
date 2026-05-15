# exp-20260514-010 SEC Buyback Credibility Sleeve

- decision: `rejected_no_stable_alpha`
- status: `rejected`
- expected_value_score_delta: `-0.2431`
- total_pnl_delta: `-1623.33`
- qualified_events: `16`

## Hypothesis

SEC text disclosures that show buyback credibility through actual execution, cash-supported authorization increases, or accelerated share repurchase language may carry a higher-quality capital-return signal than generic repurchase keywords.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | Event PnL | Event Trades | Win Rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.3768 | 4.1264 | -0.2504 | 99695.99 | 97551.98 | -2961.29 | 4 | 0.6522 |
| mid_weak | 1.6788 | 1.6791 | 0.0003 | 62644.67 | 62888.55 | 542.98 | 4 | 0.56 |
| old_thin | 0.4292 | 0.4362 | 0.007 | 31563.29 | 31840.09 | 916.29 | 3 | 0.44 |

## Aggregate

```json
{
  "baseline_ev_sum": 6.4848,
  "baseline_pnl_sum": 193903.95,
  "ev_delta_pct": -0.037488,
  "ev_delta_sum": -0.2431,
  "max_drawdown_delta_max": 0.0022,
  "overlay_ev_sum": 6.2417,
  "overlay_pnl_sum": 192280.62,
  "pnl_delta": -1623.33,
  "pnl_delta_pct": -0.008372,
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_material_ev_or_pnl": 0,
  "windows_trade_count_win_rate_gate": 2
}
```

## Data Availability

```json
{
  "evaluated_rows_in_windows": 302,
  "pit_status": "Uses SEC accepted_at/usable_trade_date and fixed OHLCV snapshots. Public archive text is replayable PIT proxy, not proof the production pipeline observed it live.",
  "qualified_bucket_counts": {
    "accelerated_share_repurchase": 1,
    "actual_execution_update": 15
  },
  "qualified_event_count": 16,
  "qualified_tickers": [
    "APP",
    "AVGO",
    "GS",
    "NFLX",
    "NOW",
    "TRIP"
  ],
  "raw_rows": 306,
  "skipped_counts": {
    "buyback_keyword_not_credible": 15,
    "no_buyback_term": 270,
    "price_missing_ticker_spy_or_usable_date": 1
  }
}
```

## Decision

The buyback credibility overlay did not improve the fixed three windows without regression.

## Production Impact

No default backtest strategy path or live order path changed. Any positive result requires a shared default-off buyback queue/sleeve before promotion.

## Next Action

Do not promote this SEC buyback credibility sleeve on the frozen sample; next buyback work needs richer credibility fields or forward evidence.
