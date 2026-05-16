# exp-20260516-002 Core-Confirmed Slot Priority

Decision: `rejected_core_confirmed_slot_priority`.

Single variable: when survived core candidates are slot-sliced, sort the same-day post-deferral candidate list so `core_confirmed_quality_state=True` candidates fill scarce slots first. No entry filter, sizing scalar, exit, candidate pool, LLM/news, or event-sleeve behavior changed.

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Routing events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1064 | 4.3781 | -0.7283 | $116,319.10 | $104,488.57 | $-11,830.53 | 0.8039 | 1 |
| mid_weak | 2.0987 | 1.9896 | -0.1091 | $76,035.04 | $73,692.98 | $-2,342.06 | 0.7925 | 1 |
| old_thin | 0.5294 | 0.1312 | -0.3982 | $37,282.59 | $14,911.32 | $-22,371.27 | 0.8525 | 3 |

Production impact: replay-only scout. Positive promotion requires moving the same priority hook into shared `production_parity.plan_entry_candidates`, which both `backtester.py` and `run.py` already call, plus focused parity coverage.
