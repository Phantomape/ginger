# exp-20260607-004 SEC Guidance/Outlook Raise Price-Aligned Pool

- Trial family: `sec_guidance_outlook_raise_price_aligned_candidate_pool`
- Changed variable: `sec_guidance_outlook_raise_price_aligned_candidate_source_v1`
- Decision: `rejected_sec_guidance_outlook_raise_price_aligned_candidate_pool`
- Aggregate EV delta: -0.0231
- Aggregate PnL delta: $+489.79
- Target trades: 10
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3 | $-906.42 | 5.1628 | 5.1283 | -0.0345 | $+11.12 | +0.0000 |
| mid_weak | 3 | $-45.86 | 2.1402 | 2.1409 | +0.0007 | $+25.77 | -0.0004 |
| old_thin | 4 | $452.90 | 0.5911 | 0.6018 | +0.0107 | $+452.90 | +0.0004 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: False
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: True
- `target_trade_count_passed`: False
- `target_window_count_passed`: True
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: False

## Decision Rationale

One or more Gate 4 checks failed, so the standalone SEC guidance/outlook raise price-aligned source is not retained.

## Failure Reflection

Rejected because the evidence-span guidance/outlook pool was too thin (10 target trades versus the 20 trade floor), reduced aggregate EV by -0.0231, and regressed late_strong EV despite all three windows showing small PnL gains. Positive PnL concentration also failed, with the largest positive ticker share at 0.609 and HHI at 0.501. The likely failure mode is that explicit guidance/outlook raise filings are sparse and mostly mega-cap continuation events already captured by existing accepted momentum/consensus surfaces, while the price-alignment filter does not add enough independent information to offset event drag. Do not retune the same guidance threshold/excess-return bundle on this sample; require forward SEC rows, richer semantic relation extraction, or a different free-data edge.

## Lookahead / Parity Guard

The candidate selector observes signal-date close-to-close reaction, then shifts usable_trade_date to the next trading session before calling the existing next-open paper trade helper.

This experiment changes no production code. A retained result would need a shared default-off SEC guidance/outlook adapter using the same filing credibility, evidence-span extraction, exclusion language, signal-day OHLCV reaction, next-session entry shift, and parity tests before any daily report, candidate queue, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260607_004_sec_guidance_outlook_raise_price_aligned.py
