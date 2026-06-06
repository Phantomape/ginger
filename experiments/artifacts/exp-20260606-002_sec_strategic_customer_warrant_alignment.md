# exp-20260606-002 SEC Strategic Customer Warrant Alignment

- Trial family: `sec_strategic_customer_warrant_alignment_candidate_pool`
- Changed variable: `sec_strategic_customer_warrant_alignment_candidate_source_v1`
- Decision: `rejected_sec_strategic_customer_warrant_alignment_candidate_pool`
- Aggregate EV delta: +0.0000
- Aggregate PnL delta: $+0.00
- Target trades: 0
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 0 | $0.00 | 5.1628 | 5.1628 | +0.0000 | $+0.00 | +0.0000 |
| mid_weak | 0 | $0.00 | 2.1402 | 2.1402 | +0.0000 | $+0.00 | +0.0000 |
| old_thin | 0 | $0.00 | 0.5911 | 0.5911 | +0.0000 | $+0.00 | +0.0000 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: False
- `aggregate_pnl_positive`: False
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: False
- `target_window_count_passed`: False
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Decision Rationale

One or more Gate 4 checks failed, so the strategic customer/partner warrant alignment source is not retained.

## Negative Reflection

If rejected, the likely reason is not that customer-aligned warrants are impossible alpha, but that the historical SEC text archive contains too few PIT rows and mixes strategic alignment with financing language. Do not retune nearby warrant phrase thresholds on this frozen sample; a valid retry needs broader forward rows or a richer source-span counterparty extraction.

## Production / Backtest Parity

This experiment changes no production code. A positive replay result would require a shared default-off SEC text adapter with the same warrant/alignment pattern set, PIT usable-date handling, financing audit fields, candidate ordering, and production/backtest parity tests before any daily report, candidate queue, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260606_002_sec_strategic_customer_warrant_alignment.py
