# exp-20260528-014 Kova Sell-Side Lifecycle Taxonomy

Decision: `observed_only_taxonomy_candidate_for_later_lifecycle_replay`.

This is observed-only attribution on the accepted exp-20260526-007 VCP top-2 paper trades. It does not alter entries, exits, ranking, sizing, paper notional, LLM/news, production watchlists, or orders.

## Gate Questions

- 1_alpha_hypothesis: exit / lifecycle attribution: classify accepted VCP paper trades by Kova sell-side failure or profit-protection pathway.
- 1_playbook_alignment: Matches the Kova recommended next work: sell-side observed-only taxonomy before any executable lifecycle policy.
- 2_history_check: Nearby single-variable Kova exit/pyramid tests were rejected or insufficient: entry-day-low stop, fixed max-loss stop, pyramid, and high-volume weak-close support-break exit. No full taxonomy had been logged.
- 3_single_causal_variable: kova_sell_side_lifecycle_taxonomy_v1
- 4_acceptance_standard: Observed-only: taxonomy can only nominate a later Gate 1-4 shared lifecycle replay. It cannot promote an exit unless a separate strategy experiment passes docs/backtesting.md.
- 5_reproducibility: Script, source artifact, JSON output, ticket, log, and markdown artifact are written under exp-20260528-014.

## Coverage

- Target trades: `117`
- Classified trades: `117`
- Missing / unavailable rows: `0`

## Primary Bucket Summary

| Bucket | Trades | PnL | Avg PnL | Win Rate | Avg MFE | Avg MAE |
|---|---:|---:|---:|---:|---:|---:|
| orderly_or_unclassified_hold | 72 | 12821.84 | 178.08 | 68.06% | 5.12% | -2.63% |
| strong_followthrough_no_warning | 19 | 27299.45 | 1436.81 | 100.00% | 16.09% | -2.04% |
| failed_breakout_low_mfe | 14 | -3935.60 | -281.11 | 0.00% | 1.13% | -5.15% |
| max_loss_stop_touch | 7 | 264.47 | 37.78 | 42.86% | 3.78% | -10.66% |
| event_gap_down_proxy | 3 | -695.34 | -231.78 | 33.33% | 5.31% | -9.04% |
| climax_or_churning | 1 | 2486.90 | 2486.90 | 100.00% | 32.70% | -3.33% |
| support_break_high_volume_weak_close | 1 | -599.20 | -599.20 | 0.00% | 0.23% | -6.16% |

## Multi-Label Summary

| Label | Trades | PnL | Avg PnL | Win Rate |
|---|---:|---:|---:|---:|
| no_sell_side_label | 72 | 12821.84 | 178.08 | 68.06% |
| strong_followthrough_no_warning | 19 | 27299.45 | 1436.81 | 100.00% |
| failed_breakout_low_mfe | 18 | -6177.19 | -343.18 | 0.00% |
| max_loss_stop_touch | 9 | 234.14 | 26.02 | 44.44% |
| support_break_high_volume_weak_close | 4 | -948.81 | -237.20 | 25.00% |
| event_gap_down_proxy | 3 | -695.34 | -231.78 | 33.33% |
| climax_or_churning | 2 | 3631.51 | 1815.76 | 100.00% |

## Actionability Probe

- Gate status: `observed_taxonomy_has_negative_candidate_bucket`
- Reason: At least one lifecycle bucket has >=10 trades and negative total PnL; this can only justify a later shared lifecycle replay, not a rule now.

## Interpretation

The taxonomy found at least one sufficiently populated negative-PnL sell-side bucket. This is not an exit rule; the only valid next step would be a separate shared lifecycle replay with replacement-value, drawdown, survival, and production/backtest parity accounting.
