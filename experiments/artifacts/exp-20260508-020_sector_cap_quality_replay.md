# exp-20260508-020 - Sector cap quality replay

## Decision

Rejected. The local quality replacement rule did not improve the canonical three-window replay.

## Hypothesis

When same-day sector cap has to drop candidates, preserving the top same-sector candidates by existing quality fields may improve local capital allocation without changing MAX_PER_SECTOR.

## Results

| Window | Baseline EV | Variant EV | EV delta | Baseline PnL | Variant PnL | PnL delta | Win-rate delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.7435 | 3.7435 | +0.0000 | $83,562.53 | $83,562.53 | $+0.00 | +0.0000 |
| mid_weak | 1.5478 | 1.4800 | -0.0678 | $57,542.74 | $56,062.37 | $-1,480.37 | -0.0238 |
| old_thin | 0.3359 | 0.3359 | +0.0000 | $26,242.68 | $26,242.68 | $+0.00 | +0.0000 |

## Mechanism Read

The only active window was `mid_weak`, where the quality replacement admitted one extra trade but lowered win rate and PnL. This suggests same-sector cap collisions are not misallocated by simple TQS/confidence/near-high ordering.

Do not retry nearby same-sector TQS, confidence, or quality-key variants without new event/news replacement evidence.

## Gate 4

Passed: `False`. Aggregate EV delta `-0.0678` (-1.20%); aggregate PnL delta `$-1,480.37` (-0.88%).
