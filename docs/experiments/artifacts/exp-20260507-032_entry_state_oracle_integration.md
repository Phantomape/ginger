# exp-20260507-032 Entry-State Oracle Integration

## Decision

- decision: accepted_measurement_oracle
- production_impact: replay_only diagnostic; no trading logic changed
- next_action: use entry_state as a standing oracle feature, not a live entry rule

## Aggregate

- all candidate rows: 137
- platform candidate rows: 19
- seed candidate rows: 6

## Top Tags

- above_sma20: count=137, avg20d=0.032689, win_rate=0.5912, windows=3
- above_sma50: count=137, avg20d=0.032689, win_rate=0.5912, windows=3
- rs20_leader: count=110, avg20d=0.039296, win_rate=0.5818, windows=3
- pre_earnings_46_plus: count=68, avg20d=0.038265, win_rate=0.5588, windows=3
- gap_up_3pct: count=57, avg20d=0.029803, win_rate=0.5088, windows=3
- pre_earnings_8_21: count=23, avg20d=0.012979, win_rate=0.5218, windows=3
- pre_earnings_22_45: count=20, avg20d=0.012526, win_rate=0.55, windows=3
- sma20_reclaim: count=15, avg20d=0.017552, win_rate=0.7333, windows=3
- sma50_reclaim: count=10, avg20d=0.005117, win_rate=0.6, windows=3
- pre_earnings_0_7: count=4, avg20d=0.028262, win_rate=0.75, windows=3

## Notes

- This is oracle diagnostics only; future prices are used for attribution.
- META/NFLX remain underpowered as a standalone candidate replay sample.
- The useful outcome is a shared diagnostic surface for future entry work.
