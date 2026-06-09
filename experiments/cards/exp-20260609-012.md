# exp-20260609-012 SEC Large Filing-Payload Price-Absorption Pool

- Trial family: `sec_large_filing_payload_price_absorption_candidate_pool`
- Changed variable: `sec_large_filing_payload_price_absorption_candidate_source_v1`
- Decision: `rejected_sec_large_filing_payload_price_absorption_candidate_pool`
- Aggregate EV delta: +0.0426
- Aggregate PnL delta: $+989.18
- Target trades: 0
- Production impact: `replay_only_no_live_adapter`

## Gate 1-4

| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 0 | $0.00 | 5.1628 | 5.2034 | +0.0406 | $+917.54 | +0.0000 |
| mid_weak | 0 | $0.00 | 2.1402 | 2.1422 | +0.0020 | $+71.64 | +0.0000 |
| old_thin | 0 | $0.00 | 0.5911 | 0.5911 | +0.0000 | $+0.00 | +0.0000 |

## Gate 4 Checks

- `aggregate_expected_value_positive`: True
- `aggregate_pnl_positive`: True
- `all_windows_expected_value_improved`: False
- `all_windows_pnl_improved`: False
- `target_trade_count_passed`: False
- `target_window_count_passed`: False
- `drawdown_drift_passed`: True
- `survival_floor_passed`: True
- `concentration_guard_passed`: True

## Candidate Diagnostics

```json
{
  "first_examples": {
    "char_count_rejected": {
      "text_char_count": 16745,
      "ticker": "MSFT"
    },
    "excluded_text_rejected": {
      "excluded_text_hits": 1,
      "form_type": "8-K",
      "ticker": "UNH"
    },
    "reaction_missing": {
      "signal_date": "2024-10-10",
      "ticker": "APLD"
    },
    "word_count_rejected": {
      "text_word_count": 2311,
      "ticker": "TSLA"
    }
  },
  "interpretation": "The fixed bundle produced no price-ready target trades because the large SEC text candidates did not map to the replay OHLCV price surface after the language/payload filters.",
  "stages": {
    "char_count_rejected": 2,
    "credible": 302,
    "excluded_text_rejected": 109,
    "language_passed": 164,
    "negative_language_rejected": 19,
    "outside_window": 4,
    "payload_passed": 292,
    "reaction_missing": 164,
    "rows_in_window": 302,
    "word_count_rejected": 8
  }
}
```

## Decision Rationale

One or more Gate 4 checks failed, so the standalone SEC large filing-payload price-absorption source is not retained.

## Reflection

Rejected because the fixed SEC filing-payload price-absorption bundle produced zero target trades. The filter audit found 164 large, credible, non-negative filing rows before OHLCV reaction checks, but 164 could not be mapped to the replay price map, leaving no price-ready candidates across the three canonical windows. The positive aggregate delta is an empty-event-curve artifact and is not alpha evidence. Do not retune payload size, close-location, volume, or credibility thresholds on this sample; this direction needs broader replay OHLCV coverage or a different free-data candidate source already inside the tradable universe.

## Lookahead / Parity Guard

The selector observes signal-date SEC text plus close-to-close OHLCV reaction, then shifts usable_trade_date to the next trading session before calling the existing next-open paper trade helper.

This experiment changes no production code. A retained result would need a shared default-off SEC filing-payload/price-absorption adapter with the same source fields, exclusions, signal-date OHLCV reaction, next-session entry shift, and parity tests before any daily report, candidate queue, or order surface could change.

## Reproducibility

.\.venv\Scripts\python.exe -B quant\experiments\exp_20260609_012_sec_large_filing_payload_price_absorption.py
