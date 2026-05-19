# exp-20260517-002 Core Misfit Paper Ledger Adapter

Decision: `accepted_production_visible_default_off_paper_adapter`.

Single variable: add a production-visible `CORE_MISFIT_PAPER` ledger/report
adapter for selected or slot-sliced `TSM` / `ISRG` / `V` / `DDOG` core long
signals. Core entries, exits, ranking, sizing, heat, slots, LLM/news, and live
orders are unchanged.

What the adapter tracks:

| Surface | Horizon | Live order impact |
|---|---|---|
| `no_trade_avoided_value` | 1/3/5/10 trading days | none |
| `fast_long` | 1/3/5/10 trading days | none |
| `inverse_short` | 1/3/5/10 trading days | none |

Validation:

- `quant/test_core_misfit_paper_sleeve.py`: 3 passed.
- Focused existing sizing tests: 3 passed, 321 deselected.
- Import check: `run`, `report_generator`, and `core_misfit_paper_sleeve` load.

Production impact: default-off paper-only daily tracking. No live shorting, no
core exclusion, no entry/exit/ranking/sizing change. The forward gate requires
at least 20 closed 10-day paper outcomes plus positive no-trade and inverse
evidence before any separate live exclusion/short experiment.
