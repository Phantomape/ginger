# exp-20260517-024 APP Trend Positive Governance

Decision: `rejected_app_trend_positive_governance_underpowered`.

Single variable: cap-aware post-sizing top-up for already-qualified APP trend_long signals. No production policy changed.

## Sweep

| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Adjusted | Candidate rows | Cap-bound | Windows |
|---:|:---:|:---:|---:|---:|---|---|---:|---:|---:|---|
| 1.00 | yes | FAIL | +0.0000 | $+0.00 | - | - | 0 | 2 | 1 | - |
| 1.25 | no | FAIL | +0.0091 | $+330.28 | mid_weak | - | 1 | 2 | 1 | mid_weak |
| 1.50 | no | FAIL | +0.0416 | $+1,227.76 | mid_weak | - | 1 | 2 | 1 | mid_weak |
| 2.00 | no | FAIL | +0.0866 | $+2,573.34 | mid_weak | - | 1 | 2 | 1 | mid_weak |

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | 0.8039 | 0 |
| mid_weak | 2.1402 | 2.2268 | +0.0866 | $78,110.11 | $80,683.45 | $+2,573.34 | 0.7925 | 1 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | 0.8667 | 0 |
