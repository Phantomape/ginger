# Oracle Diagnostics

`quant/oracle_diagnostics.py` is an observation-only upper-bound diagnostic.
It intentionally uses future OHLCV data, so it must never be used as a
tradable strategy rule or as a direct Gate 4 acceptance metric.

## What It Measures

- `perfect_exit`: Given the trades the system actually entered, sell each trade
  at the best future intratrade high before the real exit date. This estimates
  exit/hold regret after entry quality is fixed.
- `candidate_forward`: Given saved candidate tickers by signal date, enter at
  the next trading day's open and sell at the best high within a fixed forward
  horizon. This estimates whether the candidate pool contained missed upside
  beyond the trades the system actually selected.

## Usage

```bash
python quant/oracle_diagnostics.py \
  --backtest data/backtest_results_20260426.json \
  --out data/oracle_diagnostics_20260426.json
```

Optional:

```bash
python quant/oracle_diagnostics.py \
  --backtest data/backtest_results_20260426.json \
  --candidate-horizon-days 20
```

## Interpretation Rules

- High `perfect_exit.capture_ratio` means the current exit logic already
  captured much of the available post-entry upside.
- Low `actual_trade_overlap_fraction` in `candidate_forward` means the saved
  candidate pool contained many opportunities that were not selected as trades.
- Top candidate opportunities are research leads, not proof. Any tradable rule
  inspired by them still needs normal backtest gates and multi-window checks.
