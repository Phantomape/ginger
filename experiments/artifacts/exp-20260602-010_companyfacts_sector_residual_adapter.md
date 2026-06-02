# exp-20260602-010: Companyfacts Sector-Residual Adapter

- decision: `accepted_companyfacts_sector_residual_shared_adapter`
- source replay: `exp-20260602-009`
- aggregate EV: `15.7099` -> `16.1444` (+0.4345)
- aggregate PnL: `$353,364.63` -> `$359,253.44` (+5,888.81)
- shared adapter validation: `True`
- failed adapter checks: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | survival after |
|---|---:|---:|---:|---:|---:|
| late_strong | 7.2164 | 7.2995 | +0.0831 | $+1,065.87 | 0.8039 |
| mid_weak | 5.7284 | 5.9392 | +0.2108 | $+2,372.24 | 0.7925 |
| old_thin | 2.7651 | 2.9057 | +0.1406 | $+2,450.70 | 0.8667 |

## Production/Backtest Parity

The retained rule now lives in `quant/fundamental_growth_rs_paper_sleeve.py` as a shared default-off paper adapter. The adapter uses the same public sector cache, signal-day OHLCV close-to-close 20-day residual, 5-member sector floor, 3pp excess threshold, and 1.05x paper scalar as the positive replay lead. `trade_enabled` remains false and production orders are unchanged.

## Gate Conclusion

Retained: exp-20260602-009 passed the canonical three-window Gate 4, and this run promotes the exact sector-residual support into the shared default-off Fundamental Growth + RS paper adapter without changing live orders, core entry, ranking, sizing, exits, LLM, or news behavior.
