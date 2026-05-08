# exp-20260507-034 Platform RS20 Entry Gate

## Decision

- decision: rejected
- gate4_passed: False
- skipped_signal_count: 4
- EV delta sum: 0.1566
- PnL delta: -1925.31

## By Window

- late_strong: EV 0.0, PnL 0.0, DD 0.0, skipped 0
- mid_weak: EV 0.0465, PnL -5608.69, DD -0.0419, skipped 2
- old_thin: EV 0.1101, PnL 3683.38, DD -0.0209, skipped 2

## Notes

- Runtime monkeypatch only; no production path changed.
- Same-day backfill is disabled to isolate the entry-gate variable.
- The gate uses signal-date ticker_ret20_minus_spy_pct >= 0.05.
