# exp-20260716-011 历史实验现行口径重评

## 结论

本实验以 `accepted_measurement_repair` 收尾，不接受任何新 alpha，也不改写历史 verdict 或生产策略。

- 480 个可恢复、非空、已关闭且行为不重复的 long alpha surface 全部按当前现金可行 core 与 Gate 4-P 重放。
- 21/480 同时取得正的 formal aggregate EV delta 与 PnL delta。
- 其中 6 个没有经济或风险 hard failure，结论为 `portfolio_forward_watch`；474 个为 `portfolio_reject`。
- 0/480 的 90% simultaneous max-T lower bound 大于 0，因此没有 `accepted_portfolio_paper`。
- 所有正结果都受历史 selection panel 不完整和固定窗口自适应复用限制，不能解释成新的无偏泛化估计。

## 冻结证据面

- 2,374 张 ticket、2,570 份 log、3,301 份 JSON artifact 被逐文件读取和哈希。
- 554 份 artifact 含三窗口 `target_trades_by_window`；排除 25 个空面和 1 个无法合法 long 重放的 `inverse_short_proxy`。
- 48 份 exact behavior alias 被折叠为 33 个 alias group，最终保留 480 个 unique surface、53,909 条可重放交易。
- 89 条早期交易用 `shares * entry_price` 无歧义恢复 `paper_notional_usd`。
- 1 个 mixed surface 的 62 条 signal-only observer row 被显式排除，剩余交易标为 partial recovery。
- 99 份 artifact 含 229 条精确 dated daily-return series，可按当前 `return * abs(sharpe)` 口径重算。
- 62 个去重候选的历史 source `pnl` 与当前 notional/price/45bp 成本重建差异超过 $0.011；source `pnl` 只作诊断，未进入当前经济路径。

## Gate 4-P 固定合同

- active core：`exp-20260715-010` cash-feasible Gate-1。
- formal comparator：`90% core + 10% candidate` 对 `100% core`。
- 诊断 comparator：`90% core + 10% candidate` 对 `90% core + 10% cash`。
- candidate sleeve：每窗口 $10,000 初始现金、无负现金、无杠杆；45bp all-in round trip。
- 统计：3 个标准窗口，10,000 次 window-stratified circular block bootstrap，block length 20，单侧 90% simultaneous max-T lower bound。
- 480/480 现金账本非负、期末持仓结清、cash/MTM 对账一致；101,641 个潜在 OHLCV pair 与 65,884 个实际消费 pair 均无缺失。

## Forward-watch 候选

| candidate | historical status | trades | formal EV delta | formal PnL delta | simultaneous 90% LCB | 主要 blocker |
|---|---:|---:|---:|---:|---:|---|
| `exp-20260605-025` | rejected | 9 | +0.69476 | +$4,764.50 | -0.76805 | 样本不足、selection panel、max-T |
| `exp-20260603-019` | rejected | 6 | +0.51336 | +$3,172.47 | -0.98527 | 样本不足、selection panel、max-T |
| `exp-20260604-019` | rejected | 6 | +0.51336 | +$3,172.47 | -0.98527 | 样本不足、selection panel、max-T |
| `exp-20260602-024` | lead/accepted/rejected aliases | 6 | +0.48617 | +$2,792.49 | -0.98416 | 样本不足、selection panel、max-T |
| `exp-20260531-022` | accepted default-off | 6 | +0.46626 | +$2,518.69 | -0.97954 | 样本不足、selection panel、max-T |
| `exp-20260611-010` | rejected | 108 | +0.05401 | +$942.54 | -1.48652 | selection panel、max-T |

前五个候选只有 6–9 笔，点估计虽漂亮但没有统计判力；它们也高度集中在 governed Space 路径，不能当作五份独立确认。`exp-20260611-010` 是唯一达到 Gate 最低交易样本的 watch 候选，但 aggregate EV 改善很小，且 simultaneous lower bound 明显为负。若继续，优先为该候选建立全新的 prospective paper ledger，而不是再在固定历史窗口调参。

另外 15 个候选虽然 EV 与 PnL 同时为正，仍命中 hard failure：13 个 drawdown guardrail、3 个 ES95 guardrail、2 个 top-5 concentration cap，另有 1 个跨窗口 material-regression failure（同一候选可命中多项）。

## 可复现性

- evidence manifest SHA256：`ab1fceea636e1d3624c7ddbbd8ab40eb9b190760707ced313603932a80bf2007`
- OHLCV gzip SHA256：`b432672340b7dc2fdc05a08d561d6229c0c85827b05618cc9eeff3efb8ef4048`
- warehouse/main 与独立 frozen replay 的 economic projection SHA256 均为 `8b4298de27e7eca7dba061e8dcd706ecd24e51be4405679a871a4c4e6aa30eb6`。
- 两次 gate projection SHA256 均为 `08c21e7e0af0ad52d5fd3f5ce290dc569354f4f2298e65f207950a6ffc4bc71d`。
- 完整复现命令与两组 artifact hash 见 `data/experiments/exp-20260716-011/frozen_replay_verification.json`。

## 生产影响

无。没有改变 live/default orders、ranking、sizing、exits、risk budget 或 core policy。
