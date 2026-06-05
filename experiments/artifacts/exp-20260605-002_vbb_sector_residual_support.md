# exp-20260605-002: VBB Sector-Residual Support

- decision: `positive_replay_lead_vbb_sector_residual`
- aggregate EV: `7.022` -> `7.0353` (+0.0133)
- aggregate PnL: `$211,917.33` -> `$212,408.98` (+491.65)
- incremental target trades: `16`
- max single positive share: `0.341827`
- positive PnL HHI: `0.265482`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | incremental trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1465 | 5.1542 | +0.0077 | $+166.27 | 5 |
| mid_weak | 1.3302 | 1.3329 | +0.0027 | $+121.49 | 3 |
| old_thin | 0.5453 | 0.5482 | +0.0029 | $+203.89 | 8 |

## Baseline Context

The 'before' metric includes the VBB paper overlay on top of the core baseline, so it will be higher than the bare canonical docs/backtesting.md baseline. The before/after comparison uses one consistent code path.

## Production Parity

Replay-only and default-off paper only. Uses persisted `broad_market_sector_map` cache plus fixed OHLCV snapshots. No live orders, shared production adapter, core ranking, sizing, exits, LLM, or news behavior changed.

## Conclusion

VBB sector-residual support passed the three-window alpha gate as a replay-only lead; a shared adapter and parity tests are required before retention.
