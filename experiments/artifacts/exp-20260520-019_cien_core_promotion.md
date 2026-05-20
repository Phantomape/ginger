# exp-20260520-019 CIEN-only core promotion scout

## Hypothesis
CIEN may be the narrowest viable broad-market leadership ticker promotion after the six-name core promotion batch failed; adding only CIEN to the shared core watchlist could improve replacement value without adding broad ticker noise.

## Gate 1 Baseline
- baseline artifact: `data\experiments\exp-20260517-009\ample_slot_stock_rank1_topup.json`
- aggregate EV before: `7.8941`
- aggregate PnL before: `234850.99`

## Gate 2 Field Check
- snapshot manifest: `data\experiments\exp-20260520-019\cien_only_ohlcv_snapshot_build.json`
- CIEN OHLCV is present in all three augmented snapshots.

## Gate 3 Survival
- min survival after: `0.8`
- no new filter was added.

## Gate 4 Three-Window Result
| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | 0.0000 | 0.00 | 0.0000 | 18 | 18 |
| mid_weak | 2.1402 | 2.3180 | 0.1778 | 7735.41 | 0.0000 | 21 | 22 |
| old_thin | 0.5911 | 0.6270 | 0.0359 | 2129.41 | 0.0001 | 22 | 22 |

## Candidate Trade Breadth
- CIEN primary-window trades: `1`
- CIEN primary-window PnL: `14604.59`

## Decision
- decision: `rejected_rolled_back`
- aggregate EV delta: `0.2137`
- aggregate PnL delta: `9864.82`
- rejection reason: Aggregate EV and PnL improved, but the direct live core promotion depended on only one executed CIEN trade across the primary fixed windows. That is not enough candidate-specific evidence for a production watchlist addition.

## Production Impact
```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  parity_test_added: false
  rolled_back: true
```
