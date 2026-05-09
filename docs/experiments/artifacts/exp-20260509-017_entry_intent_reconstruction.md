# Entry Intent Reconstruction Audit

Generated at: `2026-05-09T10:19:48.761042`

This report is read-only. It does not modify `open_positions.json` and does not create orders.

## Summary

- Positions audited: `4`
- High-confidence candidates: `3`
- Ready for user confirmation: `2`
- Missing candidates: `1`
- Needs user confirmation: `4`

## Candidate Table

| Ticker | Current | Candidate | Confidence | Recommendation | Source | Notes |
|---|---:|---:|---|---|---|---|
| MSFT | 3 |  | none | needs_user_confirmation_no_candidate |  |  |
| SNXX | 12 | 20 | high | needs_user_confirmation_conflict_or_low_confidence | data/quant_signals_20260503.json | shortfall 8 shares; 2 reduce/exit actions after entry; 2 manual trades after entry |
| UNH | 3 | 15 | high | candidate_ready_for_user_confirmation | data/llm_prompt_resp_20260413.json | shortfall 12 shares; candidate conflict [15, 16, 17] |
| AMZN | 4 | 38 | high | candidate_ready_for_user_confirmation | data/llm_prompt_resp_20260414.json | shortfall 34 shares |

## Next Step

Populate `original_shares` only after reviewing the rows marked `candidate_ready_for_user_confirmation`.
Rows without a candidate need an external broker/order note or explicit user confirmation.
