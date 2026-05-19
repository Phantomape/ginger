# exp-20260508-007 Platform RS20 No-Gap Missed Feature Audit

## Decision

- decision: observed_only_underpowered
- primary feature: `no_gap_up_3pct`
- gate passed: False
- gate failures: matched_candidate_count_lt_8, single_ticker_positive_share_gt_50pct

## Primary Split

- matched no-gap rows: count=3, pnl=10353.51, win_rate=1.0, single_ticker_positive_share=0.8776
- complement gap-up rows: count=3, pnl=-2381.58, win_rate=0.0

## Supporting Splits

- gap_up_3pct: matched_count=3, matched_pnl=-2381.58, matched_win_rate=0.0
- breakout_long: matched_count=3, matched_pnl=10353.51, matched_win_rate=1.0
- scarce_slot_breakout_deferred: matched_count=2, matched_pnl=9509.72, matched_win_rate=1.0
- candidate_rank_missing: matched_count=2, matched_pnl=9509.72, matched_win_rate=1.0
- pre_earnings_0_21: matched_count=2, matched_pnl=9509.72, matched_win_rate=1.0
- pre_earnings_46_plus: matched_count=4, matched_pnl=-1537.79, matched_win_rate=0.25

## Notes

- Observed-only feature audit of exp-20260507-035 missed rows.
- Does not change production signals, ranking, sizing, exits, or orders.
- Strong sample split is not promoted because count and concentration fail the gate.
