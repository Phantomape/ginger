# exp-20260604-003 SEC Text-Price Alignment Issuer Continuation

- Trial family: `sec_text_price_alignment_issuer_continuation_candidate_pool`
- Changed variable: `sec_text_price_alignment_issuer_continuation_candidate_source_v1`
- Decision: `rejected_sec_text_price_alignment_issuer_continuation`
- Aggregate EV delta: -0.1058
- Aggregate PnL delta: $+4,166.99
- Target trades: 57
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 16 | $-2,298.10 | 5.1628 | 4.8822 | -0.2806 | $-1,380.56 | +0.0008 |
| mid_weak | 17 | $398.16 | 2.1402 | 2.1767 | +0.0365 | $+469.79 | -0.0015 |
| old_thin | 24 | $5,077.77 | 0.5911 | 0.7294 | +0.1383 | $+5,077.76 | +0.0124 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: False
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: True
- `target_window_count_passed`: True
- `drawdown_drift_passed`: False
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Decision Rationale

One or more Gate 4 checks failed, so the standalone SEC text-price alignment issuer-continuation source is not retained.

## Lookahead / Parity Guard

The candidate selector observes signal-date close-to-close reaction, then shifts usable_trade_date to the next trading session before calling the existing next-open paper trade helper.

This experiment changes no production code. A retained result would need a shared default-off SEC text-price alignment adapter using the same filing credibility, language bucket, signal-day OHLCV reaction, next-session entry shift, and parity tests before any daily report, candidate queue, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260604_003_sec_text_price_alignment_issuer_continuation.py
