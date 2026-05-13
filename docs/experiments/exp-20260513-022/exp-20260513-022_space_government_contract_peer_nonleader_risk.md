# exp-20260513-022 space_government_contract_peer_nonleader_risk

## Decision

- decision: `rejected`
- hypothesis: If government/defense Space catalysts only deserve top-up when peer momentum leads, then government-contract profile signals that are peer nonleaders should get a small risk haircut to reduce broad-theme drawdown while preserving official-catalyst coverage.
- single changed variable: `space_government_contract_peer_nonleader_risk_scalar`
- best scalar: `0.9`
- adjusted count: `9`
- EV delta: `0.575`
- PnL delta: `6726.24`

## Aggregate

| metric | before exp020 | after best | delta |
|---|---:|---:|---:|
| expected_value_score_sum | `17.0211` | `17.5961` | `0.575` |
| total_pnl_sum | `418278.3` | `425004.54` | `6726.24` |
| trade_count_sum | `69` | `70` | `1` |
| signals_generated_sum | `207` | `203` | `-4` |
| signals_survived_sum | `160` | `161` | `1` |
| min_survival_rate | `0.6533` | `0.7042` | `0.0509` |
| max_drawdown_pct_max | `0.161` | `0.161` | `0.0` |

## Window Checks

| window | EV delta | PnL delta | max DD delta | pass |
|---|---:|---:|---:|---|
| late_strong | `-0.1359` | `-4389.79` | `-0.0044` | `False` |
| mid_weak | `0.7109` | `11116.03` | `-0.0091` | `True` |
| old_thin | `0.0` | `0.0` | `0.0` | `True` |

## Sweep

| variant | scalar | EV delta | PnL delta | adjusted | passed |
|---|---:|---:|---:|---:|---|
| government_contract_peer_nonleader_scalar_0_5 | `0.5` | `-3.1828` | `-65182.95` | `9` | `False` |
| government_contract_peer_nonleader_scalar_0_75 | `0.75` | `-1.338` | `-30584.6` | `9` | `False` |
| government_contract_peer_nonleader_scalar_0_9 | `0.9` | `0.575` | `6726.24` | `9` | `False` |
| government_contract_peer_nonleader_scalar_1_0 | `1.0` | `0.0` | `0.0` | `9` | `False` |
