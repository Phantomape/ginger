# exp-20260716-005: PCAOB partner-change peer substitution

- Status: `rejected`
- Decision: `rejected_pcaob_partner_change_peer_substitution`
- Fixed policy: official hash-bound Form AP partner change, unaffected same-industry ADV60 peer, top1/day, strict next open, 20 sessions, $4k, 35bps, default-off

| Window | Settled | Standalone PnL | Cash replacement | QQQ replacement | EV delta | PnL delta | Max-DD delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| old_thin | 44 | -$2,228.47 | -$2,228.47 | +$5,237.76 | -0.0606 | -$2,228.48 | +0.0515 |
| mid_weak | 27 | +$4,780.77 | +$4,780.77 | -$21.60 | +0.2853 | +$4,780.78 | -0.0076 |
| late_strong | 44 | +$2,287.14 | +$2,287.14 | +$3,057.53 | -0.1558 | +$2,287.13 | +0.0013 |

- Aggregate EV delta: `+0.0689`; accepted comparator required `>+0.5286`.
- Aggregate PnL delta: `+$4,839.43`; accepted comparator required `>+$10,432.91`.
- Density passed: settled decisions `44/27/44`, target tickers `44/27/44`, peers `31/23/28`, and all target/peer top-one shares below 30%.
- Robustness failed: only one EV window improved, old-window drawdown worsened 5.15pp, old cash replacement was negative, and mid-window QQQ replacement was negative.
- Concentration failed: top-five positive-PnL share was 65.7283% versus a 60% cap.
- PIT failed: two selected peer trades mapped through CIKs `0001067983` and `0001652044`, whose share class was selected using all-window liquidity. One target trade also used multi-share CIK `0000046619`.
- DSR was `not_computable` because the declared selection panel was incomplete; that blocks live eligibility only.
- Production boundary: `trade_enabled=false`; no live orders, core rules, run adapter, or automatic forward collection changed.

## Boundary

Do not retune filing scope, partner definition, fiscal gap, share mapping, industry taxonomy, peer pool, ADV rank, daily top1, entry, hold, notional, costs, or issuer subsets on these frozen rows. Reopen only with a genuinely new source/gate shape, or at least 30 prospectively settled unchanged-policy decisions with positive replacement value and PIT industry/share-class mapping.

Tests: `169 passed`; final deterministic evaluator rerun exited `0` with unchanged decision metrics.
