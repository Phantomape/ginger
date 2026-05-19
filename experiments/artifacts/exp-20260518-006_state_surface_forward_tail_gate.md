# exp-20260518-006: State-Surface Forward Tail Gate

## Decision

- Decision: `accepted_measurement_repair_forward_tail_gate`
- Source: `data/experiments/exp-20260518-005/state_surface_regime_rank_notional.json`
- Legacy forward gate would pass: `True`
- Tail-aware forward gate passes: `False`

## Metrics

- Closed paper trades: `24`
- Realized paper PnL: `$48,529.40`
- Win rate: `0.7917`
- PnL top-five contribution: `0.6104`
- PnL HHI concentration: `0.0949`
- Tail hard failures: `['pnl_top5_concentration']`

## Interpretation

The accepted state-surface paper sleeve remains profitable and default-off, but promotion readiness should stay blocked until forward outcomes show less dependence on the top five winners.

## Production Impact

- Live/default orders: unchanged
- Candidate ranking, eligibility, notional profile, hold days: unchanged
- Production report and shared paper-sleeve snapshot now expose tail diagnostics
