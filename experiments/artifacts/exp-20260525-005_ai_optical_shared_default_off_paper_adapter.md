# exp-20260525-005: AI optical shared default-off paper adapter

Decision: accepted shared default-off paper adapter.

Source alpha evidence: `exp-20260525-003` rerun on the three `docs/backtesting.md` standard windows.

- Aggregate EV: `+0.4482`
- Aggregate PnL: `$7,372.78`
- Windows EV-improved: `3/3`
- Target paper trades: `10` across `3` windows
- Max single positive share: `0.327971`
- Positive PnL HHI: `0.2785`

Implementation: `quant/ai_optical_paper_sleeve.py` plus `run.py`, report, attribution, data-path, docs, and focused tests. The path is default-off, paper-only, and cannot emit live orders.
