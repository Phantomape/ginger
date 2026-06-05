# exp-20260605-006 SEC Business-Development Source-Span Candidate Pool

- Trial family: `sec_text_business_development_source_span_candidate_pool`
- Changed variable: `sec_business_development_ex99_non_dilutive_candidate_source_v1`
- Decision: `rejected_sec_business_development_source_span_candidate_pool`
- Aggregate EV delta: +0.1114
- Aggregate PnL delta: $+7,680.02
- Target trades: 33
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 10 | $-1,982.98 | 5.1628 | 4.9651 | -0.1977 | $-1,065.43 | +0.0010 |
| mid_weak | 10 | $2,029.60 | 2.1402 | 2.2517 | +0.1115 | $+2,021.35 | -0.0010 |
| old_thin | 13 | $6,724.10 | 0.5911 | 0.7887 | +0.1976 | $+6,724.10 | +0.0065 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: True
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: False
- `survival_floor_passed`: True
- `concentration_guard_passed`: False

## Decision Rationale

One or more Gate 4 checks failed, so the SEC business-development source-span candidate source is not retained.

## Production / Backtest Parity

This experiment changes no production code. A retained result would need a shared default-off SEC source-span adapter with the same document-section extraction, business-development pattern set, dilution exclusions, and backtest/live parity tests before any daily report, candidate queue, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260605_006_sec_business_development_ex99_candidate_pool.py
