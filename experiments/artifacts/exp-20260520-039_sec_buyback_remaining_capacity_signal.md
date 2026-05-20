# exp-20260520-039 SEC Buyback Remaining Capacity Signal

- decision: `rejected_buyback_remaining_capacity_signal`
- status: `rejected`
- aggregate EV delta vs core: `0.0`
- aggregate PnL delta vs core: `0.0`
- aggregate EV delta vs full buyback: `0.0`
- selected capacity trades: `0`

## Hypothesis

SEC buyback disclosures with explicit remaining or available repurchase authorization capacity may be a cleaner capital-return alpha than broad buyback credibility, because remaining capacity can represent continuing corporate demand rather than only stale historical execution.

## Three-Window Result

| Window | Core EV | Full buyback EV | Capacity EV | dEV vs core | dEV vs full | Core PnL | Capacity PnL | Event PnL | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | 5.1628 | 0.0 | 0.0 | $117,072.92 | $117,072.92 | $0.00 | 18 -> 18 |
| mid_weak | 2.1402 | 2.1402 | 2.1402 | 0.0 | 0.0 | $78,110.11 | $78,110.11 | $0.00 | 21 -> 21 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | 0.0 | 0.0 | $39,667.96 | $39,667.96 | $0.00 | 22 -> 22 |

## Gate 4

```json
{
  "capacity_selected_event_trades": 0,
  "drawdown_guard_passed": true,
  "improves_vs_full_buyback_credibility": false,
  "material_vs_core": false,
  "no_core_ev_regression": true,
  "passed": false,
  "sample_guard_min_trades": 5,
  "sample_guard_passed": false,
  "single_ticker_positive_share": null,
  "single_ticker_positive_share_guard": "<= 0.60"
}
```

## Data Availability

```json
{
  "evaluated_rows_in_windows": 302,
  "full_credibility_bucket_counts": {},
  "full_credibility_event_count": 0,
  "pit_status": "Uses SEC accepted_at/usable_trade_date and fixed OHLCV snapshots; archive text is a replayable public-PIT proxy, not proof production saw it live.",
  "raw_rows": 306,
  "remaining_capacity_bucket_counts": {},
  "remaining_capacity_event_count": 0,
  "remaining_capacity_tickers": [],
  "skipped_counts": {
    "buyback_keyword_not_credible": 15,
    "no_buyback_term": 270,
    "price_missing_ticker_spy_or_usable_date": 17
  }
}
```

## Decision

Remaining-capacity buyback disclosures did not improve the canonical three-window evidence enough to justify a new default-off sleeve branch.

## Production Impact

No shared policy, backtester adapter, run adapter, order path, or live/default strategy behavior changed.

