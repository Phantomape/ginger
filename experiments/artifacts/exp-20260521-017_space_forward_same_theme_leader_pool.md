# exp-20260521-017 Space forward same-theme leader pool

- decision: rejected_space_forward_same_theme_leader_pool
- changed_variable: `space_forward_same_theme_leader_pool_membership`
- EV delta: `-17.0857`
- PnL delta: `$-343,355.74`
- passed tickers: `BKSY, LUNR, RDW, RKLB, VSAT`
- removed from base: `ASTS, PL`
- added to base: `VSAT`

## Gate 4

- `late_strong`: EV `+0.1882`, PnL `$+18,340.46`, DD `+0.0323`
- `mid_weak`: EV `-16.4633`, PnL `$-328,550.08`, DD `+0.0032`
- `old_thin`: EV `-0.8106`, PnL `$-33,146.12`, DD `+0.0000`

Rejected because the candidate-pool rule caused large EV regressions in `mid_weak` and `old_thin`; no shared Space policy was promoted.
