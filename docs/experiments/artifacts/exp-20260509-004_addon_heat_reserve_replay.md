# exp-20260509-004 Add-on Heat Reserve Replay

Decision: `rejected`
Best variant: `reserve_0_5pct_heat`

| Window | Before EV | After EV | EV Delta | Before PnL | After PnL | PnL Delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 4.0674 | 4.0674 | +0.0000 | $90,788.88 | $90,788.88 | $+0.00 |
| mid_weak | 1.6195 | 1.6195 | +0.0000 | $59,540.63 | $59,540.63 | $+0.00 |
| old_thin | 0.3583 | 0.3583 | +0.0000 | $27,347.42 | $27,347.42 | $+0.00 |

The hard 8% portfolio heat cap remains unchanged. Only new-entry
admission is shadow-lowered by the reserve amount; add-ons still use
the unchanged hard cap in the cap calculation.
