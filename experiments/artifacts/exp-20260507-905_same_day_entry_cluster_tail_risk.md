# exp-20260507-905 Same-Day Entry-Cluster Tail Risk

Decision: `rejected`
Best variant: `cluster3_rank3plus_0_00x`

## Hypothesis

Same signal-date accepted A/B clusters may represent correlated late-cycle exposure; preserving the first planner-ranked trade while reducing later-ranked cluster tail risk may improve EV without adding a new ticker universe or LLM dependency.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 5.5094 | 165815.54 | 63 |

## Aggregate Replay

| Variant | EV delta | PnL delta | PnL delta % | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| cluster2_rank2plus_0_50x | -0.3358 | -8643.48 | -0.052127 | 0/2 | 6 | 6 | 0.0033 | 0.8597 | FAIL |
| cluster2_rank2plus_0_00x | -0.7258 | -17279.04 | -0.104206 | 0/2 | 6 | 6 | 0.0068 | 0.8748 | FAIL |
| cluster3_rank3plus_0_50x | 0.0184 | 149.4 | 0.000901 | 1/0 | 1 | 1 | 0.0 | 1.0 | FAIL |
| cluster3_rank3plus_0_00x | 0.0316 | 261.45 | 0.001577 | 1/0 | 1 | 1 | 0.0 | 1.0 | FAIL |

## Window Deltas

| Variant | Window | EV delta | PnL delta | Sharpe delta | DD delta | Trade delta |
|---|---|---:|---:|---:|---:|---:|
| cluster2_rank2plus_0_50x | late_strong | -0.1604 | -4057.29 | 0.09 | -0.0102 | 0 |
| cluster2_rank2plus_0_50x | mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| cluster2_rank2plus_0_50x | old_thin | -0.1754 | -4586.19 | -0.29 | 0.0033 | 0 |
| cluster2_rank2plus_0_00x | late_strong | -0.3922 | -8133.8 | 0.11 | -0.0117 | -4 |
| cluster2_rank2plus_0_00x | mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| cluster2_rank2plus_0_00x | old_thin | -0.3336 | -9145.24 | -0.64 | 0.0068 | -2 |
| cluster3_rank3plus_0_50x | late_strong | 0.0184 | 149.4 | 0.01 | -0.0005 | 0 |
| cluster3_rank3plus_0_50x | mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| cluster3_rank3plus_0_50x | old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| cluster3_rank3plus_0_00x | late_strong | 0.0316 | 261.45 | 0.02 | -0.0009 | -1 |
| cluster3_rank3plus_0_00x | mid_weak | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| cluster3_rank3plus_0_00x | old_thin | 0.0 | 0.0 | 0.0 | 0.0 | 0 |

## Cluster Coverage

| Window | Cluster size counts | Cluster PnL by size |
|---|---|---|
| late_strong | `{"1": 13, "2": 2, "3": 1}` | `{"1": 65935.51, "2": 20425.71, "3": -4331.1}` |
| mid_weak | `{"1": 21}` | `{"1": 57542.74}` |
| old_thin | `{"1": 18, "2": 2}` | `{"1": 13050.54, "2": 13192.14}` |

## Rejection Reason

Best variant `cluster3_rank3plus_0_00x` failed Gate 4: EV delta 0.0316 (0.003896), PnL delta 261.45 (0.001577), windows improved/regressed 1/0, changed trades 1 of 1 touched, max DD worsening 0.0, single ticker positive share 1.0.

## Production Impact

No live or default-backtest strategy changed. Any future promotion would need a shared cluster-tail entry/risk policy consumed by `run.py` and `backtester.py`, plus parity tests.
