# exp-20260505-018 breakout slot ranking

Decision: **rejected**
Best variant: `breakout_rank_rs_then_52w`

## Aggregate

- EV delta sum: -0.1157
- EV delta pct: -0.022342
- PnL delta sum: -2403.87
- PnL delta pct: -0.01519
- EV windows improved/regressed: 0/1
- Gate 4 passed: False

## Window Deltas

- late_strong: EV +0.0000, PnL +0.00, Sharpe daily +0.00, DD +0.0000, trades +0
- mid_weak: EV -0.1157, PnL -2403.87, Sharpe daily -0.10, DD +0.0000, trades +1
- old_thin: EV +0.0000, PnL +0.00, Sharpe daily +0.00, DD +0.0000, trades +0

## Repro

```powershell
.\.venv\Scripts\python.exe quant\experiments\exp_20260505_018_breakout_slot_ranking.py
```

## Production Parity

Change quant/signal_engine.py rank_signals_for_allocation and update quant/test_quant.py; the helper is already called by backtester.py, run.py, run_quant.py, and run_pipeline.py.

