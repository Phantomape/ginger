# exp-20260529-009 Default-Off Candidate-Pool Forward Maturity Direction

Decision: `accepted_direction_candidate_pool_forward_maturation`.

Single variable: `default_off_candidate_pool_forward_maturity_direction_rank_v1`.

## Gate Questions

- alpha_hypothesis: candidate_pool / capital allocation direction: optimize the accepted default-off candidate-pool sleeve with the strongest historical EV and forward maturity.
- history_check: Nearby historical candidates include exp-20260529-004 VBB, exp-20260529-008 Fundamental/VBB source agreement, exp-20260528-017 Fundamental low-liability support, and exp-20260526-007 VCP rank-notional profile. The playbook freezes nearby VCP/VBB/Companyfacts scalar and shape retunes.
- single_causal_variable: default_off_candidate_pool_forward_maturity_direction_rank_v1
- acceptance_standard: Read-only direction decision. Strategy changes still require docs/backtesting.md three-window before/after Gate 1-4. This run uses only accepted three-window artifacts and current forward state to choose the next lane.
- reproducibility: .\.venv\Scripts\python.exe -B quant\experiments\exp_20260529_009_default_off_candidate_pool_forward_maturity_direction.py

## Direction Rank

| Rank | Sleeve | Current EV vs core | Latest EV d | Latest PnL d | Trades | Closed/Open/Pending forward | Score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | Fundamental Growth + RS | +8.5419 | +8.5419 | $+127,144.15 | 336 | 0/0/1 | 0.9507 |
| 2 | QQQ-Confirmed VCP | +2.2913 | +2.2913 | $+37,642.52 | 117 | 0/0/0 | 0.4713 |
| 3 | Broad-Market Leadership | +8.9457 | +0.1197 | $+3,502.29 | 79 | 0/5/0 | 0.4681 |
| 4 | Volume-Breadth Breakout | +0.8205 | +0.0285 | $+456.30 | 41 | 0/0/1 | 0.3399 |
| 5 | AI Optical IWM-Confirmed | +0.4459 | +0.4482 | $+7,372.78 | 10 | 0/0/0 | 0.2873 |

## Next Actions By Sleeve

1. Fundamental Growth + RS: Use forward closed rows for cost-adjusted replacement value, ticker/sector concentration, and cash/core displacement tests.
2. QQQ-Confirmed VCP: Wait for new VCP forward rows, then test replacement value and lifecycle decay rather than entry-shape thresholds.
3. Broad-Market Leadership: Let current open rows mature, then evaluate replacement value by sector and hidden beta before any allocation change.
4. Volume-Breadth Breakout: Track the accepted VBB candidates through forward closeout and compare replacement value by breadth, cost, regime, and core overlap.
5. AI Optical IWM-Confirmed: Observe only until fresh forward outcomes arrive; the current closed sample is too small for promotion or another low-close support.

## Conclusion

- Optimize now: `Fundamental Growth + RS`.
- Rationale:
  - It scores highest after combining current EV versus core, latest three-window delta, trade breadth, no-regression Gate 4 status, playbook priority, and current forward state.
  - Its latest accepted three-window delta is the strongest; Broad-Market has a slightly higher current EV versus core but still lacks closed forward rows and recently failed nearby sector-crowding retry evidence.
  - It is already production-visible and default-off, which avoids a backtester-only rule.
  - The valid next step is forward replacement-value and concentration analysis, not another frozen-window scalar retune.

## Blockers

- fundamental_growth_rs: needs at least 10 closed forward rows; has 0
- volatility_contraction: needs at least 10 closed forward rows; has 0
- broad_market: needs at least 10 closed forward rows; has 0
- volume_breadth_breakout: needs at least 10 closed forward rows; has 0
- ai_optical: needs at least 10 closed forward rows; has 0

## Do Not Do Next

- Do not rename another OHLCV breakout/pullback shape on the same frozen sample.
- Do not mine another Companyfacts/VBB/VCP support scalar without new closed forward rows.
- Do not promote any sleeve into live/default capital before shared adapter activation evidence passes Gate 1-4.

## Production Impact

Read-only alpha direction decision. No shared policy, backtester adapter, run adapter, candidate ranking, sizing, exit, watchlist, LLM/news, or order behavior changed.

No JavaScript was used.
