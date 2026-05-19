# exp-20260518-014 SEC Neutral Market-Context Notional

Decision: `accepted_candidate_sec_neutral_market_context_notional`.

## Sweep

| Variant | Gate | dEV | dPnL | EV+ | EV- | Max DD d | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|
| spy_t1_return_gte_-0.0100_extra_scalar_1_50 | PASS | +0.6796 | $+16,836.11 | 3 | 0 | +0.3439% | 7 |
| spy_t1_return_gte_-0.0075_extra_scalar_1_50 | PASS | +0.6754 | $+16,748.28 | 3 | 0 | +0.3489% | 6 |
| spy_t1_return_gte_-0.0050_extra_scalar_1_50 | PASS | +0.6754 | $+16,748.28 | 3 | 0 | +0.3489% | 6 |
| spy_t1_return_gte_-0.0025_extra_scalar_1_50 | FAIL | +0.7579 | $+18,945.20 | 3 | 0 | +0.0000% | 5 |
| spy_t1_return_gte_+0.0000_extra_scalar_1_50 | FAIL | +0.5757 | $+15,492.45 | 3 | 0 | +0.0000% | 3 |

## Best Window Deltas

```json
{
  "late_strong": {
    "ev_delta": 0.09534,
    "max_drawdown_delta": 0.0,
    "neutral_language_closed_trade_count": 8,
    "neutral_language_pnl_delta": 127.65,
    "pnl_delta": 1397.32
  },
  "mid_weak": {
    "ev_delta": 0.279045,
    "max_drawdown_delta": -0.001691,
    "neutral_language_closed_trade_count": 4,
    "neutral_language_pnl_delta": 4982.82,
    "pnl_delta": 4293.3
  },
  "old_thin": {
    "ev_delta": 0.30105,
    "max_drawdown_delta": 0.003489,
    "neutral_language_closed_trade_count": 9,
    "neutral_language_pnl_delta": 14328.55,
    "pnl_delta": 11057.66
  }
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
  "default_off_paper_only": true,
  "parity_test_added": true,
  "parity_test_file": "quant/test_sec_financial_report_event_sleeve.py",
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "shared_policy_file": "quant/sec_financial_report_event_sleeve.py"
}
```

No JavaScript was used.
