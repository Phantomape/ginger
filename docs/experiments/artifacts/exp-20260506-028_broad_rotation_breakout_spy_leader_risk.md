# exp-20260506-028 Broad Rotation Breakout SPY Leader Risk

Decision: rejected and rolled back.

Hypothesis: when IWM 20-day return beats SPY by more than 2 percentage points, broad market rotation may justify raising risk-on `breakout_long` signals that are also 20-day leaders versus SPY from the accepted 2.0x total risk budget to 2.5x.

Why this was worth testing: `exp-20260506-024` found the broad-rotation + SPY-relative-leader sizing family was positive across the fixed windows. This was a capital allocation test on existing signals, not a new universe expansion or a new filter.

Three-window result:

| Window | EV before | EV after | EV delta | Sharpe daily delta | PnL delta | Gate 4 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| late_strong | 3.4078 | 3.5558 | +4.34% | +0.07 | +2.68% | fail |
| mid_weak | 1.2993 | 1.3033 | +0.31% | +0.00 | +0.32% | fail |
| old_thin | 0.3179 | 0.3179 | +0.00% | +0.00 | +0.00% | fail |

The direction was weakly positive in two windows and unchanged in one, but it did not clear any acceptance threshold: no >10% EV lift, no >0.1 Sharpe lift, no >1 percentage-point drawdown reduction, no >5% PnL lift, and no trade-count increase with stable win rate.

Parity note: the candidate was tested through shared `risk_engine` enrichment and shared `portfolio_engine` sizing, so an accepted version would not have been backtester-only. Because Gate 4 rejected it, all strategy code was rolled back and only this experiment record remains.

Do not repeat: avoid nearby 2.25x/2.75x broad-rotation SPY-leader multiplier probes unless there is new forward evidence or an orthogonal discriminator stronger than IWM-vs-SPY 20-day relative return.
