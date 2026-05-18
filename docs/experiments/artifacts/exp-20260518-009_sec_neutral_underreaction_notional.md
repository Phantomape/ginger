# exp-20260518-009 SEC Neutral Underreaction Notional

Decision: `accepted_default_off_sec_neutral_underreaction_notional`.

## Sweep

| Variant | Gate | dEV | dPnL | EV+ | EV- | Max DD d | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|
| neutral_underreaction_t1_lte_0.015_scalar_2_00 | FAIL | +0.2533 | $+3,528.82 | 3 | 0 | +0.0000% | 3 |
| neutral_underreaction_t1_lte_0.020_scalar_2_00 | PASS | +0.7177 | $+16,836.09 | 3 | 0 | +0.3957% | 7 |
| neutral_underreaction_t1_lte_0.025_scalar_2_00 | FAIL | +0.5517 | $+16,330.74 | 2 | 1 | +0.2339% | 12 |
| neutral_underreaction_t1_lte_0.030_scalar_2_00 | FAIL | +0.5517 | $+16,330.74 | 2 | 1 | +0.2339% | 12 |
| neutral_underreaction_t1_lte_0.035_scalar_2_00 | FAIL | +0.6367 | $+19,770.80 | 2 | 1 | +0.0899% | 15 |
| neutral_underreaction_t1_lte_0.040_scalar_2_00 | FAIL | +0.5431 | $+19,029.79 | 2 | 1 | +0.0899% | 17 |

## Best Window Deltas

```json
{
  "late_strong": {
    "ev_delta": 0.100858,
    "max_drawdown_delta": 0.0,
    "neutral_underreaction_closed_trade_count": 1,
    "neutral_underreaction_pnl_delta": 2721.1,
    "pnl_delta": 1397.31
  },
  "mid_weak": {
    "ev_delta": 0.285638,
    "max_drawdown_delta": -0.001748,
    "neutral_underreaction_closed_trade_count": 2,
    "neutral_underreaction_pnl_delta": 3603.77,
    "pnl_delta": 4293.29
  },
  "old_thin": {
    "ev_delta": 0.331162,
    "max_drawdown_delta": 0.003957,
    "neutral_underreaction_closed_trade_count": 4,
    "neutral_underreaction_pnl_delta": 7874.61,
    "pnl_delta": 11145.49
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
  "production_queue_field_file": "quant/sec_event_queue.py",
  "replay_only": false,
  "run_adapter_changed": true,
  "shared_policy_changed": true,
  "shared_policy_file": "quant/sec_financial_report_event_sleeve.py"
}
```

No JavaScript was used.
