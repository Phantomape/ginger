# exp-20260513-008 Legacy Target Lifecycle Replay

Decision: `rejected_no_full_exit_promotion_target_ratchet_preferred_for_next_policy_test`

Full EXIT on first silent legacy-suppressed target was negative versus holding on the saved production-position replay. The target-stop ratchet variant avoided that opportunity cost but was mostly inert over the short saved sample. This supports fixing target visibility, but not promoting blunt full exits for legacy winners.

## Variants

| Variant | Scope | Policy | Events | Realized | dUSD vs Hold | Tickers |
|---|---|---|---:|---:|---:|---|
| silent_full_exit_next_observed_close | silent | full_exit_next_observed_close | 4 | 3 | $-2,332.93 | AMD, NVDA, SNXX, TSLA |
| silent_target_stop_ratchet | silent | target_stop_ratchet | 4 | 0 | $+0.00 | AMD, NVDA, SNXX, TSLA |
| silent_intent_aware_exit_or_ratchet | silent | intent_aware_exit_or_ratchet | 4 | 3 | $-1,981.09 | AMD, NVDA, SNXX, TSLA |
| all_full_exit_next_observed_close | all | full_exit_next_observed_close | 4 | 4 | $-2,693.93 | AMD, NVDA, SNXX, TSLA |
| all_target_stop_ratchet | all | target_stop_ratchet | 4 | 0 | $+0.00 | AMD, NVDA, SNXX, TSLA |
| all_intent_aware_exit_or_ratchet | all | intent_aware_exit_or_ratchet | 4 | 4 | $-2,342.09 | AMD, NVDA, SNXX, TSLA |

## Primary Silent Events

| Variant | Ticker | Trigger | Fill | Final | Action | dUSD vs Hold |
|---|---|---|---|---|---|---:|
| silent_full_exit_next_observed_close | AMD | 2026-04-15 | 2026-04-16 | 2026-05-11 | EXIT_FULL | $-1,263.71 |
| silent_full_exit_next_observed_close | NVDA | 2026-04-21 | 2026-04-22 | 2026-05-11 | EXIT_FULL | $-525.14 |
| silent_full_exit_next_observed_close | SNXX | 2026-05-06 | 2026-05-07 | 2026-05-11 | EXIT_FULL | $-544.08 |
| silent_full_exit_next_observed_close | TSLA | 2026-05-11 | n/a | 2026-05-11 | EXIT_FULL | $+0.00 |
| silent_target_stop_ratchet | AMD | 2026-04-15 | 2026-04-16 | 2026-05-11 | RATCHET_STOP_HOLD | $+0.00 |
| silent_target_stop_ratchet | NVDA | 2026-04-21 | 2026-04-22 | 2026-05-11 | RATCHET_STOP_HOLD | $+0.00 |
| silent_target_stop_ratchet | SNXX | 2026-05-06 | 2026-05-07 | 2026-05-11 | RATCHET_STOP_HOLD | $+0.00 |
| silent_target_stop_ratchet | TSLA | 2026-05-11 | n/a | 2026-05-11 | RATCHET_STOP_HOLD | $+0.00 |
| silent_intent_aware_exit_or_ratchet | AMD | 2026-04-15 | 2026-04-16 | 2026-05-11 | INTENT_AWARE_EXIT_FULL | $-1,263.71 |
| silent_intent_aware_exit_or_ratchet | NVDA | 2026-04-21 | 2026-04-22 | 2026-05-11 | INTENT_AWARE_REDUCE_AND_RAISE_STOP | $-173.30 |
| silent_intent_aware_exit_or_ratchet | SNXX | 2026-05-06 | 2026-05-07 | 2026-05-11 | INTENT_AWARE_EXIT_FULL | $-544.08 |
| silent_intent_aware_exit_or_ratchet | TSLA | 2026-05-11 | n/a | 2026-05-11 | INTENT_AWARE_EXIT_FULL | $+0.00 |
