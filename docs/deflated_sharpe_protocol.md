# Probabilistic and Deflated Sharpe Protocol

This protocol prevents a strategy selected from many attempts from being
treated as if it were the only strategy tested.  It is a research-measurement
and live-readiness control.  It does not change entries, exits, ranking,
sizing, orders, or Gate 1-4 alpha acceptance.

## What the numbers mean

For an observed periodic Sharpe `SR_hat`, benchmark Sharpe `SR_star`, return
count `T`, sample skewness `skew`, and Pearson kurtosis `kurtosis`:

```text
q = 1 - skew * SR_hat + ((kurtosis - 1) / 4) * SR_hat^2
PSR(SR_star) = Phi((SR_hat - SR_star) * sqrt(T - 1) / sqrt(q))
```

The Deflated Sharpe Ratio is that same probability evaluated against the
expected best Sharpe produced by the declared trial pool under the null:

```text
SR0 = sigma_trials * [
    (1 - EulerGamma) * Phi^-1(1 - 1 / N_eff)
    + EulerGamma * Phi^-1(1 - 1 / (N_eff * e))
]
DSR = PSR(SR0)
```

`DSR` is a probability-like statistic in `[0, 1]`, not a Sharpe value.  It is
not the probability of future profit, a Bayesian posterior, or PBO.

All Sharpe inputs to these formulas are periodic and unannualized.  A daily
annualized Sharpe is divided by `sqrt(252)` before use.  `kurtosis` is Pearson
kurtosis, whose normal-distribution value is `3`, not excess kurtosis.

## Backtest evidence contract

Every saved backtest must retain a `sharpe_inference` block containing:

- the dated, full-precision daily strategy-equity return series;
- a deterministic hash of that series;
- the observation count, periodic and annualized Sharpe, skewness, and Pearson
  kurtosis;
- PSR against a zero periodic Sharpe benchmark;
- the return basis and the zero-risk-free-rate assumption;
- a DSR state.

Daily equity must be marked to market exactly once for every simulated trading
day, including days when all core slots are occupied.  The final observation
must include forced-liquidation costs.  Flat days remain observations; they
must not be dropped.

A single backtest can compute PSR, but it cannot honestly compute DSR.  Its DSR
state therefore remains `not_computable` until a complete selection panel is
supplied.  Rounded legacy `sharpe_daily` values are not valid substitutes for
the retained return stream.

The persisted field names are `return_series`, `return_series_sha256`,
`periodic_sharpe`, `annualized_sharpe`, `moments`, `psr`, and `dsr` inside
`sharpe_inference`.

## Complete selection-panel contract

One panel represents one explicitly declared selection decision.  Every row
must share the same:

- `selection_scope` (normalized to `selection_scope_id` in the Gate-5 report);
- evaluation window and periodicity;
- return basis and risk-free-rate assumption;
- protocol, point-in-time data version, and cost model;
- ordered return dates.

The panel must contain every attempted configuration in that scope, winners
and losers, with a unique `config_id`.  The declaration must state the expected
configuration count and affirm that the pool is complete.  Post-hoc subsets,
only the winner, only saved survivors, or trials from incomparable windows are
invalid.

For `M >= 2` aligned return streams, the implementation computes each trial's
periodic Sharpe and their sample cross-sectional standard deviation
(`ddof = 1`).  It estimates the effective number of independent trials as:

```text
N_eff = average_correlation + (1 - average_correlation) * M
```

Negative average correlation is retained in the paper's interpolation and may
make `N_eff` slightly greater than `M`, increasing the selection penalty; the
report emits an explicit warning.  The panel requires `T >= M`; otherwise
correlation evidence is too ill-conditioned for this proxy.  Small
`N_eff < 50` receives the paper's large-sample approximation warning.

Missing trial dispersion, missing effective-trial evidence, incomplete pools,
unaligned dates, duplicate configurations, non-finite values, or invalid
formula denominators all produce `status = not_computable`.  The system never
fills these gaps with `prior_trial_count`, `1/sqrt(T)`, a selected strategy's
standard error, or a constant.

Run an explicit panel with:

```powershell
.\.venv\Scripts\python.exe -B scripts\deflated_sharpe.py `
  --input <complete-trial-panel.json> `
  --output <dsr-report.json>
```

The input object contains `selected_config_id`, `expected_attempt_count`,
`selection_pool_complete=true`, a declared `expected_return_dates` vector that
the caller attests is authoritative, `periods_per_year`, and `trials`. Every
trial also carries the
`return_series_sha256` persisted by its backtest and a
`return_series_source` locator.  A computed output retains the panel input and
includes both the detailed recomputation and a normalized `gate5_dsr_report`.
The command exits nonzero when evidence is incomplete.

## Decision boundary

- Gate 1-4 and default-off paper acceptance remain governed by
  `docs/backtesting.md`.
- The codified `full_stack_candidate_pool` Gate 5 requires a computed DSR, a
  complete selection pool, non-empty panel hash and selection-scope ID, and
  `DSR >= 0.95` before its `live_eligible` verdict can be true.
- That Gate 5 consumes the full CLI report, re-evaluates its retained `panel_input`,
  and checks the claimed probability, scope, and panel hash against that
  recomputation. A hand-written five-field summary fails closed.
- Missing or sub-threshold DSR leaves a Gate-4 winner at
  `accepted_paper_pending_forward`; it does not retroactively reject the alpha.
- Historical champions without reconstructable trial panels must be labelled
  `not_computable`, not assigned a synthetic DSR.
- Legacy/manual activation paths are not yet centrally wired to this helper.
  They must not claim system-wide DSR enforcement merely because the full-stack
  candidate-pool verdict is protected.

## Known limits

DSR addresses selection bias from a declared, comparable trial pool.  It does
not repair point-in-time leakage, survivorship bias, stale marks, cash or
exposure errors, omitted costs, regime change, or production/backtest drift.
It also does not explicitly correct serial conditionality in returns and does
not prove outperformance versus SPY or QQQ.  Those remain separate gates and
diagnostics.

The panel checker recomputes each submitted row's hash, requires a source
locator, compares every row with the declared expected date vector, and Gate 5
recomputes the embedded panel. It does **not** load the locator, verify the
source file's artifact hash, or bind the declared selection pool/date vector to
a preregistered selection manifest or exact Gate-4 artifact. It therefore
detects missing fields and internally inconsistent edits, not a self-consistent
fabrication, common date deletion with a rewritten declaration, or omitted
losing trials paired with a smaller declared attempt count. Those remain
governance/provenance risks and must be visible in review.

Primary references:

- Bailey and Lopez de Prado, *The Deflated Sharpe Ratio: Correcting for
  Selection Bias, Backtest Overfitting and Non-Normality*.
- Bailey and Lopez de Prado, *The Sharpe Ratio Efficient Frontier*.
