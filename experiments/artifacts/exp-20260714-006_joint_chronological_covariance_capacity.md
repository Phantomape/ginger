# exp-20260714-006 — joint chronological covariance/capacity preflight

Decision: `rejected_governance_and_temporal_leakage_preflight`.

No runner or backtest was executed. An independent pre-run audit found five
blocking defects, so producing performance numbers would have created false
evidence:

1. The parked lane requires an owner-level prospective contract revision. A
   revision created inside this experiment would let the experiment authorize
   its own reopen.
2. The parked contract names one batch re-judgment of all 31 representatives;
   this ticket fixed only the 11 historically materialized survivors.
3. Eight of the 11 `old_thin` trade sets exit after 2025-04-22. Their complete
   MTM paths therefore consume `mid_weak` prices/PnL before weights freeze.
4. The active 2026-07-12 post-MTM baseline explicitly prohibits cross-protocol
   EV/Sharpe/drawdown comparison; the old overlay summaries use the 2026-06-04
   core and source-dependent extended calendars.
5. The proposed 12-config DSR panel omitted core-only and did not cover the
   original 31-family selection set. Shifting overlapping dates would hide,
   rather than repair, the time-boundary problem.

The allocator contract also needs redesign before any future reservation:

- `sum(weights)=0.10` plus a 2.5% family cap becomes infeasible with fewer than
  four eligible families; residual cash and zero-score fallbacks were absent.
- The score uses marginal volatility and correlation to core, not the
  candidate-by-candidate covariance matrix. It is not yet a joint covariance
  allocator.
- Mixed source notionals and concurrent positions mean weights summing to 10%
  are not a 10% capital/risk budget. Common unit-capital or target-vol
  normalization and ticker-level overlap caps are required.
- Existing MTM residuals put all costs on exit; a training cutoff would omit
  entry costs unless costs are split causally.
- Since the family list was selected on all canonical windows, later windows
  are at best weight-fit pseudo-holdouts, not untouched out-of-sample data.

The attempted owner-doc, fingerprint, and test edits were reverted. No
strategy, production, paper, or order behavior changed.

One narrow classifier repair remains: frozen-family rebuilds only see the
family/variable/variant strings, so exact rejected-preflight terms now route to
the existing `portfolio_covariance_lane/portfolio_daily_equity_overlay` cell.
This prevents an `other`-source escape and does not register a new gate shape.

## Valid next evidence

- explicit owner authorization and a prospective lane contract independent of
  a performance experiment;
- the complete contractually required family scope replayed from raw rows on
  one active post-MTM calendar/cost contract;
- a real-calendar train/holdout state-transfer rule that stops all training
  information on 2025-04-22;
- a declared selection panel that includes core-only, all candidate
  configurations in scope, and the joint allocator, while disclosing the wider
  historical selection process.

Until those conditions exist, the portfolio-covariance lane remains parked.
