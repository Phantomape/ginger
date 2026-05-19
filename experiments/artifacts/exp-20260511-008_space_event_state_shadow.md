# exp-20260511-008 SPACE_CATALYST Event-State Shadow

Status: observed only.

This starts the valid forward attribution path for the space theme. It does not enable live slots, change ranking, change sizing, or route orders.

## Seed Events

| Event | Date | Bucket | Tickers | Status | 5d return | 5d vs UFO |
| --- | --- | --- | --- | ---: | ---: | ---: |
| lunr_nasa_clps_20260324 | 2026-03-24 | fundamental_contract_regulatory | LUNR | partially_mature | -1.51% | $195.56 |
| asts_fcc_d2d_authorization_20260421 | 2026-04-21 | fundamental_contract_regulatory | ASTS | pending |  |  |
| golden_dome_sbi_awards_20260424 | 2026-04-24 | defense_budget_theme | RKLB, ASTS, LUNR, PL, RDW, BKSY, IRDM, VSAT, GSAT, SATS | pending |  |  |
| rklb_record_backlog_launch_deal_20260507 | 2026-05-07 | fundamental_contract_regulatory | RKLB | pending |  |  |
| uap_release_attention_20260508 | 2026-05-08 | attention_only | ARKX, UFO | pending |  |  |
| spacex_ipo_attention_20260507 | 2026-05-07 | attention_only | ARKX, UFO, RKLB | pending |  |  |

## Decision

Do not promote. The ledger is now running, but only 1 seed events have any mature outcome versus the 10 closed-decision gate. Use this harness for forward collection and require fundamental/regulatory/contract events to beat cash, UFO/ARKX, and same-theme alternatives before specialist promotion.

## Production Impact

```text
production_impact:
  shared_policy_changed: false
  backtester_adapter_changed: false
  run_adapter_changed: false
  replay_only: true
  alters_orders: false
  alters_signal_generation: false
  alters_candidate_ranking: false
  alters_sizing: false
```
