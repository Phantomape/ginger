# exp-20260510-005 Rotation Tilt Plus Benchmark State Surface Stack

Decision: `promising_replay_only_rotation_plus_benchmark_state_surface_stack`

Alpha search, replay-only. Single variable: add the frozen benchmark-gated state-surface sleeve on top of the current rotation-tilted event-bundle paper baseline.

## Three-Window Result

| Window | Core EV | Rotation Event EV | Rotation+Gated Surface EV | vs Rotation EV | vs Rotation PnL | vs Rotation Sharpe | vs Rotation DD | Gated Surface Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 5.2074 | 6.2041 | +0.9967 | $+12,580.11 | +0.32 | -0.04% | 12 |
| mid_weak | 1.6195 | 2.5742 | 3.2588 | +0.6846 | $+13,064.74 | +0.27 | -0.36% | 18 |
| old_thin | 0.3583 | 0.4295 | 0.8024 | +0.3729 | $+14,084.37 | +0.39 | +3.98% | 12 |

## Aggregate

- Versus core: EV +4.2201 (+69.81%), PnL $+74,060.98 (+41.68%).
- Versus rotation-event baseline: EV +2.0542 (+25.02%), PnL $+39,729.22 (+18.74%), EV windows 3/0.
- Versus ungated rotation+state-surface context: EV +0.7044 (+7.37%), PnL $+4,519.93 (+1.83%), EV windows 1/2.

## Gate 4

```json
{
  "aggregate_vs_ungated_context_positive": true,
  "concentration_ok": true,
  "drawdown_cap_ok": true,
  "passed": true,
  "passed_vs_rotation_event_baseline": true,
  "rule": "Primary read is versus the current rotation-event paper baseline: require 3/3 EV improvement, zero EV regression, material aggregate EV or PnL lift, max drawdown <= 20%, and single-ticker positive Pnl share <= 50%. Ungated state-surface stack is context, not the promotion baseline.",
  "single_ticker_positive_share": 0.2984
}
```

## Decision Rationale

Promising replay-only: adding the frozen benchmark-gated state-surface sleeve on top of the current rotation-tilted event bundle improved EV in all three canonical windows versus the rotation-event baseline and cleared materiality without breaching drawdown or concentration guards. It remains default-off/paper because live routing still requires closed forward replacement-value outcomes and explicit shared trade adapters.

## Production Impact

Replay-only. Both sleeves are already default-off paper adapters, and this experiment does not enable live/default orders. Any trade-enabled version still needs closed forward outcomes plus shared run/backtester trade adapters and parity tests.
