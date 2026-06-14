# exp-20260614-012 Nonrepeat Alpha Candidate Blocker

## Decision

- Decision: `blocked_no_valid_nonrepeat_alpha_candidate_after_latest_history_scan`
- Accepted alpha: `false`
- Strategy code changed: `false`
- Production/live impact: `none`

## Gate 1-4

- Gate 1 baseline: `docs/backtesting.md`, aggregate EV `7.8941`, PnL `$234850.99`.
- Gate 2 fields: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3 survival: no filter added; baseline min survival `0.7925`.
- Gate 4: no behavior changed; all three windows are identical before/after and the alpha launch is blocked.

| Window | EV Before | EV After | PnL Before | PnL After | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 5.1628 | 5.1628 | $117072.92 | $117072.92 | 18 |
| `mid_weak` | 2.1402 | 2.1402 | $78110.11 | $78110.11 | 21 |
| `old_thin` | 0.5911 | 0.5911 | $39667.96 | $39667.96 | 22 |

## Candidate Reviews

| Candidate | Decision | Why not run now |
| --- | --- | --- |
| `analyst_estimate_revision_pead` | `blocked_data_coverage_too_thin` | Only 53 usable prior-event rows, 1 up-revision row, and 0 matched candidate rows are present for the latest ledger; a three-window Gate 1-4 alpha would be mostly empty. |
| `accepted_default_off_forward_activation` | `blocked_no_activation_ready_sleeve` | The latest activation audit found 0 activation-ready sleeves; low-deployment ETF rows were off-trigger observations, not true-trigger closed rows. |
| `sec_financial_report_next_extension` | `blocked_near_neighbor_or_empty_forward_watch` | The accepted SEC RS20 helper should not be retuned, the allocator source extension regressed, and two obvious daily watches have 0 candidates. |
| `form4_insider_or_external_issuer_edge` | `blocked_frozen_near_neighbor` | The backfill has data, but recent Form4 direct, role, ownership, withholding, sale-pressure, and overlap variants have already been rejected or frozen. |
| `companyfacts_peer_or_quality_extension` | `blocked_frozen_companyfacts_neighborhood` | The broad Companyfacts family already has accepted low-liability/recency/low-volume helpers and rejected nearby peer/quality variants. |
| `accepted_allocator_source_arbitration` | `blocked_ex_ante_fields_failed` | The oracle gap is real but recent production-visible ex-ante fields failed to harvest it; another source-priority parameter sweep would be a duplicate. |

## Conclusion

Build a new production-visible free-data edge, with priority on PIT estimate breadth/dispersion or SEC evidence-span fields; do not optimize current price/allocator thresholds.

## Repro

- Runner: `quant/experiments/exp_20260614_012_nonrepeat_alpha_candidate_blocker.py`
- JSON artifact: `data/experiments/exp-20260614-012/nonrepeat_alpha_candidate_blocker.json`
- Log: `experiments/logs/exp-20260614-012.json`

No JavaScript was used.
