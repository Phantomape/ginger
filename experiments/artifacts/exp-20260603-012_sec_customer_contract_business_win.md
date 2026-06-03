# exp-20260603-012 SEC Customer-Contract Business-Win Candidate Pool

- Trial family: `sec_customer_contract_business_win_candidate_pool`
- Changed variable: `sec_customer_contract_business_win_candidate_source_v1`
- Decision: `rejected_sec_customer_contract_business_win_candidate_pool`
- Aggregate EV delta: -0.1138
- Aggregate PnL delta: $-966.22
- Target trades: 23
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 6 | $-1,433.26 | 5.1628 | 5.0702 | -0.0926 | $-515.72 | +0.0006 |
| mid_weak | 5 | $-77.58 | 2.1402 | 2.1351 | -0.0051 | $+99.30 | +0.0002 |
| old_thin | 12 | $-624.41 | 0.5911 | 0.5750 | -0.0161 | $-549.80 | +0.0010 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: False
- `aggregate_pnl_positive`: False
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Decision Rationale

One or more Gate 4 checks failed, so the SEC customer-contract / demand-backlog candidate source is not retained.

## Production / Backtest Parity

This experiment changes no production code. A retained result would need a shared default-off SEC text adapter with the same semantic field and parity tests before any daily report, candidate queue, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260603_012_sec_customer_contract_business_win.py
