# exp-20260507-910 Pilot Slot Quality Priority

## Classification

- `experiment_type`: alpha_search
- `change_type`: pilot_sleeve_slot_priority
- `single_causal_variable`: pilot_slot_selection_policy
- `decision`: accepted_forward_pilot

## Hypothesis

The pilot sleeve now has more eligible names than its single concurrent slot can hold. A pilot slot is scarce capital, so when two pilot signals are both tradeable, the slot should go to the signal with the highest scored quality rather than whichever candidate appears first in the signal list.

This is capital-allocation alpha. It does not add tickers, loosen filters, change core signal generation, or depend on undercovered LLM replay data.

## Historical Check

This intentionally avoids recent blocked directions:

- LLM soft-ranking and veto attribution remain undercovered.
- Earnings/C-sleeve revalidation regressed all canonical windows.
- Short-pressure, options, runner exits, RS20, gap-up, far-from-earnings, and event-source pruning either failed Gate 4 or remain default-off observation.
- Broad universe expansion was rejected; this uses existing pilot governance instead of adding noisy core candidates.

The closest old failure is broad candidate-quality ordering in the core stack. This is not a repeat: the scope here is only the already-scaled pilot sleeve after core sizing, and only when multiple pilot candidates compete for one pilot slot.

## Change

`select_pilot_entry_candidates` now ranks tradeable pilot signals by:

1. `trade_quality_score`
2. `confidence_score`
3. `risk_reward_ratio`
4. `shares_to_buy`
5. original input order as the final tie-breaker

The audit payload now includes:

- `selection_policy`: `trade_quality_score_then_confidence_then_risk_reward`

Production metadata now marks pilot candidate ranking as strategy-affecting, and the parity contract documents that the same shared policy is used by production and pilot replay.

## Three-Window Gate

The canonical fixed windows end before the pilot sleeve effective dates, so core metrics should not move. They did not move.

| Window | Before EV | After EV | Before PnL | After PnL | Sharpe daily | Max DD | Trades | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong 2025-10-23 to 2026-04-21 | 3.6257 | 3.6257 | 82030.12 | 82030.12 | 4.42 | 5.39% | 20 | 75.0% |
| mid_weak 2025-04-23 to 2025-10-22 | 1.5478 | 1.5478 | 57542.74 | 57542.74 | 2.69 | 8.79% | 21 | 52.4% |
| old_thin 2024-10-02 to 2025-04-22 | 0.3359 | 0.3359 | 26242.68 | 26242.68 | 1.28 | 9.05% | 22 | 40.9% |

`expected_value_score_delta` is `0.0` in all three windows. This is expected for a post-window pilot allocation policy and confirms no accidental core-path drift.

## Production Parity

- `shared_policy_changed`: true
- `backtester_adapter_changed`: false
- `run_adapter_changed`: true
- `replay_only`: false
- `parity_test_added`: true
- `alters_candidate_ranking`: true, pilot sleeve only
- `competes_for_core_slots`: false

The policy lives in `quant/pilot_sleeve.py`. `quant/run.py` and `quant/backtester.py` both call `select_pilot_entry_candidates`; no backtester-only strategy rule was added.

## Verification

Backtests:

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-10-23 --end 2026-04-21 --ohlcv-snapshot data\ohlcv_snapshot_20251023_20260421.json
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-04-23 --end 2025-10-22 --ohlcv-snapshot data\ohlcv_snapshot_20250423_20251022.json
.\.venv\Scripts\python.exe quant\backtester.py --start 2024-10-02 --end 2025-04-22 --ohlcv-snapshot data\ohlcv_snapshot_20241002_20250422.json
```

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest quant\test_pilot_sleeve.py quant\test_backtester_pilot_sleeve.py -q
```

Result: `10 passed`.

## Decision

Accepted as forward pilot alpha, not as historical core alpha improvement.

Next review should compare selected pilot trades against `pilot_slot_sliced_signals` and cash/core alternatives after enough closed pilot outcomes. The main risk is score calibration: a high `trade_quality_score` can still be stale or less appropriate for newer pilot tickers than the sliced alternative.
