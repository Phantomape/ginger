# exp-20260510-019 Mid-Dispersion Sector-Leader Top-Up

Decision: `rejected`

## Hypothesis

Within the accepted mid-sector-dispersion trend sleeve, known-sector non-Financials names that lead their own sector on 20-day momentum but do not already qualify for the RS20 top-up may deserve a small cap-aware allocation increase.

## Aggregate

- EV delta sum: `+0.0000` (+0.00%)
- PnL delta sum: `$+0.00` (+0.00%)
- EV windows improved/regressed: `0` / `0`
- PnL windows improved/regressed: `0` / `0`
- max DD worsening: `+0.0000`
- touched trades: `0`

## Three-Window Deltas

| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Touched |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 0 |
| `mid_weak` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 0 |
| `old_thin` | +0.0000 | +0.00 | +0.00 | +0.0000 | +0.0000 | +0 | 0 |

## Production Impact

No production/shared policy was changed by this replay. A positive replay candidate must still be promoted into shared `risk_engine` / `portfolio_engine` logic and exposed through both `run.py` and `backtester.py` attribution before live orders change.

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: true
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
```
