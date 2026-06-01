# exp-20260601-014 Sleeve Capacity Accounting

## Decision

Accepted as `measurement_repair`.

This fixes a production capacity-accounting mismatch: live entry planning counted every positive broker-account position as a core strategy slot, so legacy, fomo, and pilot holdings could silently block core strategy candidates even though canonical backtests count only core-strategy positions.

## Change

- Added sleeve/slot-policy-aware core slot helpers in `quant/production_parity.py`.
- Changed `quant/run.py` so executable core entry planning uses `core_strategy_slot_accounting`.
- Kept total account positions visible as `total_account_positive_positions_shadow`.
- Updated the human report to show production core slots and total-account shadow slots separately.
- Added regression tests for explicit `sleeve` / `slot_policy`, the 10 legacy + 1 core fixture, shadow total-account blockers, and report rendering.

## 2026-05-31 Fixture Result

Before:

- total active positions: 11
- max positions: 5
- available slots: 0
- SNOW was slot-sliced
- MSFT was deferred as a scarce-slot breakout
- official selected signals after entry planning: 0

After:

- core strategy active positions: 1
- core available slots: 4
- selected core candidates: SNOW, MSFT
- total-account shadow still shows 11 active / 0 available
- SNOW shadow reason: `slot_sliced`
- MSFT shadow reason: `scarce_slot_breakout_deferred`

All real positions still count toward portfolio heat/cash/risk; they just no longer consume core strategy entry slots unless explicitly configured to do so.

## Verification

- `.\.venv\Scripts\python.exe -m pytest quant\test_production_parity.py -q`
  - `50 passed in 0.92s`
- `.\.venv\Scripts\python.exe -m pytest quant -q`
  - `1074 passed in 43.56s`

## Notes

This does not tune entry signals, ranking, sizing, exits, or LLM/news behavior. It changes production execution capacity accounting to align live core slot policy with the backtest/core-strategy book while preserving total-account shadow visibility.
