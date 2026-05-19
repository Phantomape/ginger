# exp-20260517-004 Scarce-Slot Rank-1 Top-Up

Hypothesis: if the shared entry planner has exactly one remaining slot, the
already selected rank-1 core signal represents scarce-slot conviction and can
carry a small cap-aware post-sizing top-up.

Single variable: `SCARCE_SLOT_RANK1_RISK_MULTIPLIER`.

Sweep:

| Variant | Aggregate EV | Aggregate PnL | late EV | mid EV | old EV |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 7.8348 | $233,008.22 | 5.1361 | 2.1084 | 0.5903 |
| 1.025x | 7.8530 | $233,391.57 | 5.1361 | 2.1266 | 0.5903 |
| 1.050x | 7.8580 | $233,591.20 | 5.1361 | 2.1313 | 0.5906 |
| 1.075x | 7.8585 | $233,618.09 | 5.1361 | 2.1313 | 0.5911 |

Decision: accept `1.075x`.

Risk check: trade count, survival, max drawdown, worst trade, and max consecutive
losses did not worsen in any canonical window; `mid_weak` tail loss share rose
slightly from `0.5421` to `0.5495`. The rule is
shared in `production_parity.py`, used by both `backtester.py` and `run.py`, and
does not change candidate generation, filters, ranking, slot slicing, exits,
LLM/news, heat, or orders beyond selected-signal sizing.
