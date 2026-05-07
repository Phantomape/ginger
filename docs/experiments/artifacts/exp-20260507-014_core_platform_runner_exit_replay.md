# exp-20260507-014 Core Platform Runner Exit Replay

Decision: `rejected`
Best variant: `target_67_runner_sma20_40d`

## Hypothesis

Core platform trades may be entering correctly but exiting target winners too early; a partial target plus simple SMA20 runner may improve upside capture without changing entries, ranking, sizing, or the production path.

## Baseline

| EV sum | PnL sum | Trades |
|---:|---:|---:|
| 5.6272 | 167347.95 | 62 |

## Variants

| Variant | Target fraction | Runner exit |
|---|---:|---|
| target_50_runner_sma20_40d | 0.5 | SMA20 close, original hard stop, 40d cap |
| target_67_runner_sma20_40d | 0.67 | SMA20 close, original hard stop, 40d cap |

## Aggregate Replay

| Variant | EV delta | PnL delta | Windows EV +/- | Touched | Changed | DD worsening | Single ticker share | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| target_50_runner_sma20_40d | -0.2437 | -141.48 | 1/2 | 11 | 5 | 0.0006 | 0.9032 | FAIL |
| target_67_runner_sma20_40d | -0.1457 | -45.81 | 1/2 | 11 | 5 | 0.0004 | 0.903 | FAIL |

## Guardrails

- Replay only; no production path changed.
- Single causal variable: post-target runner exit policy for treatment-pool trades.
- Entries, ranking, sizing, add-ons, universe, LLM/news, and earnings behavior are locked.
- This is not a repeat of broad pullback, pullback-RS ranking, consumer-platform universe promotion, or full-position ATR trailing exits.

## Rejection Reason

Best variant `target_67_runner_sma20_40d` failed the pre-registered proxy gate: EV delta -0.1457 (-0.017636), windows improved/regressed 1/2, changed target trades 5, max DD worsening 0.0004, single ticker positive share 0.903.
