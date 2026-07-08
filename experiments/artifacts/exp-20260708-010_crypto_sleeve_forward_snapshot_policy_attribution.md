# exp-20260708-010: BTC Crypto Sleeve Forward Snapshot Attribution

- Status: `observed_only`
- Decision: `observed_only_rejected_crypto_sleeve_policy_attribution`
- Hypothesis: Observed-only alpha: the existing production BTC/USD crypto sleeve daily EMA20/EMA100/SMA200 target policy may add risk-adjusted forward value versus BTC buy-and-hold over saved production snapshots without changing stock orders.
- Runner: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260708_010_crypto_sleeve_forward_snapshot_policy_attribution.py`

## Gate 4

| Metric | Crypto sleeve policy | BTC buy-and-hold | Delta policy - B&H |
|---|---:|---:|---:|
| Total return | -0.063834 | -0.19431 | 0.130476 |
| PnL on sleeve | -957.51 | -2914.65 | 1957.14 |
| Sharpe daily | -3.55949 | -3.334176 | -0.225314 |
| Expected value score | 0.227217 | 0.647864 | -0.420647 |
| Max drawdown | 0.088774 | 0.287075 | -0.198301 |

- Unique BTC candle dates: `61`
- Forward intervals: `60`
- Target switches: `6`
- Failed reasons: `policy_total_return_nonnegative, policy_sharpe_gt_buy_hold, policy_return_gt_cash`

## State Attribution

| State | Intervals | Avg target | Avg BTC next return | BTC positive share | Policy return sum | Fee cost sum |
|---|---:|---:|---:|---:|---:|---:|
| RISK_OFF | 39 | 0.0 | -0.003364 | 0.384615 | -0.01029 | 0.01029 |
| RISK_ON_PARTIAL | 21 | 0.7 | -0.003017 | 0.428571 | -0.054639 | 0.01029 |

## Closeout

- Production impact: Read-only offline attribution over saved production quant signal snapshots. The production crypto sleeve remains as-is.
- Why: The fixed crypto sleeve policy did not satisfy all predeclared observed-only checks versus fee-aware BTC buy-and-hold and cash.
- Forbidden retry: Do not retune EMA/SMA thresholds, target percentages, fee assumptions, benchmark liquidation convention, or sub-slices on this same saved snapshot surface.
- New evidence required: A legal retry needs materially more settled production crypto sleeve snapshot rows, a different BTC/crypto data source, or a new gate shape such as shared historical replay before policy changes.
