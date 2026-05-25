# exp-20260525-001 BTC Miner/HPC Scarce-Slot Paper Sleeve

Decision: `rejected_btc_miner_hpc_scarce_slot_paper_sleeve`.

Single variable: route governed BTC miner/HPC scarce-slot deferred events into an additive default-off paper sleeve instead of core slot competition.

## Trial Accounting

- trial_family: `governed_btc_miner_hpc_scarce_slot_paper_sleeve`
- changed_variable: `btc_miner_hpc_scarce_slot_no_displacement_paper_routing`
- prior_trial_count: `3`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `scarce_slot_deferred_candidate_no_displacement_replay`
- snapshot_note: The standard date windows are preserved. Target discovery uses the existing exp-20260519-029 observation-universe snapshots because canonical core snapshots do not reliably contain all governed BTC miner/HPC specialist tickers.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Candidate events | Paper trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.9354 | +0.0000 | $113,719.84 | $113,719.84 | $+0.00 | +0.0000 | 0 | 0 |
| mid_weak | 2.1386 | 2.1721 | +0.0335 | $78,050.31 | $78,703.36 | $+653.05 | +0.0000 | 2 | 1 |
| old_thin | 0.5805 | 0.5805 | +0.0000 | $40,307.27 | $40,307.27 | $+0.00 | +0.0000 | 0 | 0 |

## Aggregate

- EV delta: `0.0335` (`0.004377`)
- PnL delta: `$653.05` (`0.002814`)
- target trades: `1` across `1` windows
- max single positive share: `1.0`
- positive PnL HHI: `1.0`

## Simulation

```json
{
  "late_strong": {
    "candidate_event_count": 0,
    "simulated_trade_count": 0,
    "skip_reasons": {},
    "skipped_event_count": 0,
    "skipped_events_sample": []
  },
  "mid_weak": {
    "candidate_event_count": 2,
    "simulated_trade_count": 1,
    "skip_reasons": {
      "same_ticker_overlap": 1
    },
    "skipped_event_count": 1,
    "skipped_events_sample": [
      {
        "date": "2025-07-03",
        "prior_exit_date": "2025-07-21",
        "reason": "same_ticker_overlap",
        "strategy": "breakout_long",
        "ticker": "IREN"
      }
    ]
  },
  "old_thin": {
    "candidate_event_count": 0,
    "simulated_trade_count": 0,
    "skip_reasons": {},
    "skipped_event_count": 0,
    "skipped_events_sample": []
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 1.0,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 1.0,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 1,
  "target_trade_count_min": 4,
  "target_window_count_min": 2,
  "target_windows": [
    "mid_weak"
  ],
  "windows_ev_improved": 1,
  "windows_ev_improved_min": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
