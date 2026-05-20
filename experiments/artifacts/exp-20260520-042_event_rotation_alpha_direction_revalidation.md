# exp-20260520-042 Event-Rotation Alpha Direction Revalidation

Decision: `accepted_replay_only_event_rotation_as_next_alpha_direction`

Alpha search, replay-only. This run compares the current accepted event-surface lead against the `rotation_breakout_leadership` paper notional tilt and records why the other high-level alpha lanes are not the next best search target.

## Best Variant Vs Current Lead

| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.9939 | 6.3077 | +0.3138 | $128,348.37 | $132,792.86 | $+4,444.49 |
| mid_weak | 2.8629 | 3.0800 | +0.2171 | $90,598.43 | $93,901.64 | $+3,303.21 |
| old_thin | 0.6645 | 0.6725 | +0.0080 | $42,325.56 | $42,565.76 | $+240.20 |

## Aggregate Gate

- EV delta vs current lead: +0.5389 (+5.66%)
- PnL delta vs current lead: $+7,987.90 (+3.06%)
- EV windows improved/regressed: 3/0
- Sample guard passed: `True`

## Blocked Or Recently Rejected Lanes

- `llm_soft_ranking`: blocked; Historical attribution is not yet strong enough to compare LLM soft ranks versus non-veto candidates without replay bias. (exp-20260520-034)
- `broad_market_forward_maturation`: blocked; Current forward feed produced zero candidates/outcomes. (exp-20260520-027)
- `state_surface_capital_allocation`: blocked; The strict state-surface rule now requires >10% aggregate EV uplift for same-family scalar/profile/notional retunes, and the latest support scout was below that bar. (exp-20260520-028, exp-20260520-033)
- `sec_fact_tone_and_buyback`: blocked; SEC phrase provenance and current-row samples are insufficient; the latest buyback capacity scout had zero event trades. (exp-20260520-029, exp-20260520-034, exp-20260520-039)
- `core_candidate_pool_promotion`: rejected_recently; The six-name pool, CIEN-only, and AGX-only attempts failed the standard multi-window/single-sample guard. (exp-20260520-007, exp-20260520-019, exp-20260520-040)
- `current_core_dte_or_payment_network_risk`: rejected_recently; Recent DTE and payment-network risk scouts improved only isolated windows or failed sample guards. (exp-20260520-037, exp-20260520-038, exp-20260520-041)
- `low_deployment_etf_selector`: rejected_recently; The risk-adjusted selector regressed old_thin versus the accepted raw-momentum paper overlay, so adjacent selector formulas need new forward replacement evidence first. (exp-20260520-016)

## Production Impact

Replay only. The default-off paper path is shared in `quant/event_sleeve_bundle.py`, and this run does not enable live/default orders. A live-capital version still needs closed forward replacement-value evidence and explicit enablement.
