# exp-20260513-027 Signal-Day Green Slot Priority

Decision: `rejected_signal_day_green_slot_priority`.

Single variable: when entry candidates compete for finite same-day slots, prioritize already-qualified signals whose own signal-day candle is green before slot slicing. Existing scarce-slot breakout deferral, entry filters, sizing, exits, universe, LLM/news, and add-ons are unchanged.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Trades | Reordered days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.2894 | 2.0211 | -2.2683 | $95,321.74 | $54,917.66 | $-40,404.08 | 0.8800 | 19 | 2 |
| mid_weak | 1.6747 | 1.6747 | +0.0000 | $62,490.66 | $62,490.66 | $+0.00 | 0.7925 | 21 | 0 |
| old_thin | 0.3867 | 0.3867 | +0.0000 | $28,855.61 | $28,855.61 | $+0.00 | 0.9167 | 22 | 1 |

Production impact: replay-only scout. A positive result would require changing the shared `production_parity.plan_entry_candidates` helper and adding parity tests because both `backtester.py` and `run.py` call that helper.
