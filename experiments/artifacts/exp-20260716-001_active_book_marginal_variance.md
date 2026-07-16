# exp-20260716-001 — Active-book marginal-variance budget

## Decision

Rejected. The fixed post-selection, pre-cash-admission requested-risk scalar
reduced drawdown in all three canonical windows, but expected value and PnL
regressed in all three. No production or default trading behavior is changed.

## Fixed policy

- Decision clock: signal-day close, after that day's exits, before unchanged
  next-open cash admission.
- History: 60 raw close-to-close returns from 61 consecutive market sessions,
  ending on the signal date; missing history fails open to `1.0`.
- Active book: actual runtime positions marked at the signal-day close.
- Candidate notional: requested initial shares times signal entry price, before
  the existing cash scale-or-skip rule.
- `S = n0^2 * Var(candidate)` and
  `C = 2 * n0 * sum(ni * Cov(candidate, active_i))`.
- If net `C <= 0`, scalar is `1.0`; otherwise the scalar is the positive root
  `(-C + sqrt(C^2 + 4*S^2)) / (2*S)`.
- Candidate selection, ranking, entry/exit timing, cash admission, costs, and
  add-on rules are unchanged. Reduced initial shares naturally reduce the
  add-on share base and released cash is naturally available to later
  chronological candidates. Same-day candidates all see the same pre-entry
  active book.

## Gate evidence

The unpatched replay exactly reproduced the active cash-feasible Gate-1 anchor
for every window, including headline metrics, trade-row hash, dated-return
hash, inference contract, and cash ledger.

| Window | EV before | EV after | EV delta | PnL delta | MDD before | MDD after | Trades before → after | Touched executed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.1067 | 3.9706 | -0.1361 | -$2,087.92 | 3.94% | 3.86% | 13 → 14 | 8 |
| mid_weak | 1.9908 | 1.9008 | -0.0900 | -$1,559.54 | 6.61% | 5.97% | 13 → 20 | 14 |
| old_thin | 0.1082 | 0.0699 | -0.0383 | -$2,089.21 | 8.89% | 8.05% | 23 → 23 | 16 |
| **Aggregate** | **6.2057** | **5.9413** | **-0.2644** | **-$5,736.67** | **8.89% worst** | **8.05% worst** | **49 → 57** | **38** |

Gate 2 passed on the actual replay path: all policy histories ended on the
signal date; 150 executable selected-signal annotations had both the computed
next-session `entry_date` and generated `target_price`; and all 57 executed
trade rows matched those annotations with no missing entry date. One final-day
selection had no future fill session and was explicitly excluded from the
executable contract. Gate 3 passed with minimum survival `80.60%`. All three
after ledgers enforced cash,
had zero negative-cash events, nonnegative minimum cash, and exact cash
conservation. Materiality passed, but Gate 4 failed the >10% aggregate-EV,
nonnegative-PnL-delta, no-window-regression, two-improved-window, and
positive-PnL-concentration requirements.

## Attribution

The mechanism was economically active, not a static PnL rewrite: it changed 38
executed trades and released enough cash for the realized trade count to rise
from 49 to 57. That extra admission did not pay for winner clipping. Examples
of lost contribution include `IAU -$1,945.83`, `MU -$1,178.19`, and
`CAT -$878.39` in late; `SLV -$1,761.39` and `COIN -$640.76` in mid; and
`APP -$2,894.76`, `AMZN -$1,785.01`, and `JPM -$1,257.22` in old. Some losses
were reduced and some new cash-funded trades helped, but not enough in any
window. The realized scalar was also aggressive: median material scalars were
about `0.763`, `0.619`, and `0.598` in late/mid/old.

This supports a specific rejection: raw active-book covariance is useful as a
drawdown diagnostic, but it is not an alpha-positive initial-risk allocator on
these frozen windows. Do not rescue it by sweeping lookback, scalar floors,
cross-term thresholds, covariance estimators, residualization, or caps on the
same outcomes. Reopen only with an independently predeclared new covariance
gate shape plus an unseen window, or materially new forward decisions under a
fixed shared helper.

## Inference and production boundary

Full-precision dated returns, hashes, moments, and PSR remain in each raw
result. DSR is honestly `not_computable`: no complete aligned selection panel
was preregistered, and DSR is Gate 5 rather than Gate 1-4. The helper and replay
runner are default-off/replay-only; `run.py`, live orders, ranking, cash
semantics, and broker behavior are untouched. The result is not live-ready.

The reservation classifier mislabeled this surface as
`companyfacts_ratio/candidate_pool_top1_10d`. The true surface is active-book
covariance risk allocation; nearby covariance experiments were manually
checked before reservation and the override named the genuinely new gate
shape.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -B -m pytest quant\test_active_book_marginal_variance.py -q
.\.venv\Scripts\python.exe -u -B quant\experiments\exp_20260716_001_active_book_marginal_variance.py
```

Primary result:
`data/experiments/exp-20260716-001/active_book_marginal_variance.json`.
