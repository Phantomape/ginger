# exp-20260505-030 SEC Leadership Item-Code Semantics

- decision: `rejected_semantic_discriminator_not_promoted`
- best variant: `fd_other_context_only`
- delta vs all-leadership sleeve EV: 0.01443
- delta vs all-leadership sleeve PnL: 1061.89
- best variant trades: 3
- best variant PnL: 2347.04
- best variant max drawdown: 0.009375
- production impact: `replay_only_no_order_path_change`

## Window PnL

| variant | late_strong | mid_weak | old_thin | total |
|---|---:|---:|---:|---:|
| all_leadership_negative_reaction | 605.66 | 1137.55 | -458.06 | 1285.15 |
| pure_5_02_only | 493.85 | 632.72 | -58.34 | 1068.23 |
| exclude_governance_mix | 493.85 | 1137.55 | -58.34 | 1573.06 |
| fd_other_context_only | 1381.66 | 965.38 | 0.00 | 2347.04 |

## Interpretation

Rejected: the best item-code discriminator improved aggregate sleeve EV/PnL versus the rejected all-leadership sleeve, but it still failed promotion quality because the trade count stayed below 10 and the variant did not produce positive PnL in all three canonical windows.

This is alpha search on an event candidate-source discriminator. It does not alter production entries, ranking, sizing, exits, universe membership, or core backtest behavior.

## Repro

```powershell
.\.venv\Scripts\python.exe quant\experiments\exp_20260505_030_sec_leadership_item_code_semantics.py
```
