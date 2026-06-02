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
- `candidate_selection`: Rank each candidate day by future return and compare
  the oracle top candidates with the trades the system actually selected. This
  estimates whether headroom is coming from same-day ranking errors or from
  candidate days where the system made no trade.
- `no_trade_attribution`: Reconstruct open-position occupancy on missed
  candidate days. This conservatively separates obvious capacity / already-held
  cases from rows that need explicit entry skip-reason logging.

## Usage

```bash
python quant/oracle_diagnostics.py \
  --backtest data/backtests/backtest_results_20260426.json \
  --out data/diagnostics/oracle_diagnostics_20260426.json
```

### Resolving `needs_entry_skip_logging` with entry_skip_oracle

By default, `no_trade_attribution` rows where the system had empty slots but
still made no trade are labelled `needs_entry_skip_logging`.  To replace those
labels with the **actual backtester skip reason**, pass the companion
`entry_skip_oracle_*.json` produced by `quant/entry_skip_oracle.py`:

```bash
# Step 1 — generate the entry skip oracle (requires same backtest + snapshot)
python quant/entry_skip_oracle.py \
  --backtest data/backtests/backtest_results_20260426.json \
  --out data/diagnostics/entry_skip_oracle_20260426.json

# Step 2 — generate oracle diagnostics with skip reasons joined in
python quant/oracle_diagnostics.py \
  --backtest data/backtests/backtest_results_20260426.json \
  --entry-skip-oracle data/diagnostics/entry_skip_oracle_20260426.json \
  --out data/diagnostics/oracle_diagnostics_20260426.json
```

When `--entry-skip-oracle` is provided:

- Each `no_trade_attribution` row that previously showed
  `"attribution": "needs_entry_skip_logging"` is updated to the real reason
  (`gap_cancel`, `no_shares`, `stop_breach_cancel`, or `slot_sliced`).
- A `skip_details` array is added to each resolved row with mechanism-specific
  context (e.g. which zero-multiplier rule fired for `no_shares`, the gap
  percentage for `gap_cancel`, or the fill vs. stop prices for
  `stop_breach_cancel`).
- A `skip_resolution` summary block at the top of `no_trade_attribution`
  reports how many rows were resolved vs. still unresolved.
- `source_entry_skip_oracle` in the top-level output records the file path for
  reproducibility.
- Rows with **no matching skip event** keep the `needs_entry_skip_logging` label
  so genuine gaps remain visible.

Optional (horizon only):

```bash
python quant/oracle_diagnostics.py \
  --backtest data/backtests/backtest_results_20260426.json \
  --candidate-horizon-days 20
```

## Interpretation Rules

- High `perfect_exit.capture_ratio` means the current exit logic already
  captured much of the available post-entry upside.
- Low `actual_trade_overlap_fraction` in `candidate_forward` means the saved
  candidate pool contained many opportunities that were not selected as trades.
- If `candidate_selection.avg_top1_vs_actual_selection_regret_pct` is low but
  `days_without_actual_selection` is high, the next research question is
  capacity / gating / no-trade attribution rather than same-day ranking quality.
- If `no_trade_attribution.reason_counts.needs_entry_skip_logging` dominates
  **and** no `--entry-skip-oracle` was provided, run `entry_skip_oracle.py`
  first and re-run with `--entry-skip-oracle` before drawing any conclusions.
  The label means "the oracle could not see the skip reason", not "the skip
  reason is unknown" — the backtester always has one.
- After joining with `--entry-skip-oracle`, residual `needs_entry_skip_logging`
  rows indicate signal dates where the backtester generated a candidate but
  produced no skip event (e.g. already-held ticker treated as a hold, not a
  fresh skip).  These are the only rows that warrant further investigation.
- Top candidate opportunities are research leads, not proof. Any tradable rule
  inspired by them still needs normal backtest gates and multi-window checks.
