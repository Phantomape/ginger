# Broker Execution Ledger

## 已知遗留

- 当前校验器会验证八条哈希链，并要求至少存在一条成功的 `collection_manifest`；它还没有逐行证明每个事实行的 `collection_id` 都属于一个已提交采集。若进程恰好在事实落盘后、manifest 提交前失败，下一次采集前仍可能留下 orphan collection 版本。后续修复应引入逐 collection 的 commit/visibility 校验，不能把“链有效”误解成“每次采集都完整提交”。
- 现金流水日更只滚动抓取最近七个清算日。停机超过七天时，仍需要基于 manifest cursor 的限速补采；当前系统不声称更早的现金流水完整。

## 前向决策与订单归因（2026-09-09）

`quant/execution_attribution.py` 从今后的机器建议开始，冻结完整建议、策略标识、代码文件哈希、账户作用域和本地记录时间，
保存到独立的 `data/live_pilot/execution_attribution/decisions.jsonl`。这个目录与券商原始账本一样不纳入 Git。
同内容重复运行保留首次时间和备注码；内容或版本变化生成新身份，旧记录不覆盖。

每日 Step 7 会在日报和 `quant_signals.execution_attribution` 提供 32 字节 `GNG-...` 备注码。
它标识 **machine advice**，不是 LLM 批准、下单许可或已提交的 OrderIntent。
若某条建议经独立批准并实际下单，可把对应码原样填入订单备注；已存在的挂单保持原码，不因新日报出现新码而重新下单。
订单备注字段来自券商接口原始返回，参见 [Moomoo 历史订单合同](https://openapi.moomoo.com/moomoo-api-doc/en/trade/get-history-order-list.html)。
本模块没有新增下单接口，也不会自动给既有订单补备注。

归因只接受同一账户、证券、买卖方向、计划数量全部相符，且每个已提交订单版本都带着同一个已冻结备注码的订单。
同码用于多单、后补备注、修改数量、缺失决策或采集证明，均不认领。只比较明确的 UTC **本地观察时间**，不伪造券商成交时区，
也不据此声称测到了下单延迟或成交滑点。新增建议必须绑定本轮成功查询；刷新失败、数据超过 24 小时或未提交完整持仓时不生成追踪码。
加仓与退出只继承完整、明确关联的开放成交路径，退出数量不得超过已核对的持仓；历史 `opened_by_strategy` 标签不能代替证明。

`broker_performance.strategy_attribution` 在原有完整生命周期及订单费用检查通过后，再要求每个买卖订单都明确归属同一策略。
混入人工单、其他策略或缺失任何一腿，整段不归因。收益仍只覆盖可核对的已平仓子集；不能据此推出完整策略收益率或因果 alpha。
零覆盖时策略净收益为 `null`，而不是 0。券商存在本系统格式的备注却找不到决策时，全部策略收益汇总不可用，防止删掉亏损决策后只剩赢家。

新采集的 `collection_manifest.surface_commit_anchors` 固定七张非 manifest 账本各自的提交行数与末尾哈希。
读取、追加和重放都会检查已提交前缀，合法未提交尾部仍可恢复；删除订单修订或费用尾行不能悄悄回退到旧版本。
旧 manifest 不倒填，继续明确标记 `legacy_unanchored`；新订单归因要求其观测版本具有提交证明。

验证范围包括合成的完整买卖闭环、费用只扣一次、人工交易拒绝认领、尾部丢失、旧采集重放和真实只读采集。
真实账户在启用前没有明确决策备注，历史策略覆盖仍为零；这项修复没有证明 Ginger 已经盈利。

`data/live_pilot/broker_execution/` 是 Moomoo 实盘账户的券商权威事实面。它回答：
真实发生了什么成交、属于哪个订单、券商报告了多少订单级费用、账户在采集时的现金与敞口是什么。
它只做测量，不下单，也不改变策略、排序、仓位或退出规则。

## 日常接线

`quant/run.py` 已在每天开始时调用 `moomoo_open_positions.generate(preview=False)`。
该函数现在复用同一个 OpenD 会话采集并持久化以下事实；不需要为例行增量另开实验 ID：

- 当前与历史成交；
- 当前与历史订单状态；
- 订单级费用；
- 最近 7 个清算日的账户现金流水；
- 完整账户资金快照与完整持仓快照。

预览调用与测试注入的 `state` 默认不写正式账本。设置
`GINGER_SKIP_BROKER_EXECUTION_LEDGER=1` 可显式跳过落账，但正常生产刷新默认开启。
若账本链损坏，canonical bytes 保持不变并写 `health.json=failed`；最新券商持仓仍会刷新，避免
测量故障让交易系统继续使用旧持仓。若 accinfo 单独失败，持仓照常刷新，但现金/总资产只沿用
prior 文件并标 `account_snapshot_status=stale_prior_account_values` 与原 `account_values_as_of`。

## 文件合同

| 文件 | 身份与语义 |
|---|---|
| `fills.jsonl` | 追加式 deal 版本；同一 `deal_id` 可由 OK 变为 CHANGED/CANCELLED，经济投影只取最新有效版本 |
| `order_snapshots.jsonl` | 会变化的订单状态版本；同一 `order_id` 可有多个内容版本 |
| `order_fee_snapshots.jsonl` | 会延迟或修订的订单级费用版本 |
| `cash_flows.jsonl` | 清算现金流水版本；按 currency + clearing date + `cashflow_id` 取最新版本，禁止跨版本直接求和 |
| `account_snapshots.jsonl` | 采集时账户资金、现金、margin、risk、gross/net exposure 与 leverage |
| `position_snapshots.jsonl` | 采集时完整持仓集合；空数组是明确的“账户已清仓”事实 |
| `fill_lifecycle_links.jsonl` | 从成交重放得到的派生生命周期链接，不冒充券商原始字段 |
| `collection_manifests.jsonl` | 每次成功采集的 SDK 版本、查询状态、窗口与各面输入行数 |
| `state.json` | 可覆盖的最新健康状态、覆盖范围、费用覆盖和数量对账摘要 |
| `health.json` | 即使 canonical chain 损坏也可写的最新采集健康告警 |

所有券商 ID 都保存为字符串，避免 64-bit ID 被 JavaScript 浮点数截断。原始 broker timestamp
完整保留，但 SDK 合同没有确认它的时区，因此账本写
`event_time_timezone_status=broker_local_unspecified`，不会擅自加 `Z` 或伪造 UTC 时间。
账户号只用于生成稳定 hash scope，不写入账本。

## 不可变与 fail-closed

每个 JSONL 文件都有连续的 `ledger_sequence`、`prev_record_hash` 和 `record_hash`。
写入前会在专用文件锁内完整验证旧链，再规划全部文件：

- 相同 deal/cashflow 版本与相同内容：幂等跳过；
- 同一 `deal_id` / `cashflow_id` 内容变化：追加新版本，旧版本字节永不覆盖；
- 同一固定 collection snapshot 身份却出现不同内容，或不同账户写进同一 root：拒绝整次写入；
- JSON 损坏、序号断裂、hash 不匹配或重复 identity：拒绝写入；
- 正常追加通过 fsync + atomic replace 写入，并保留旧前缀字节不变；
- `collection_manifests.jsonl` 最后提交；`state.json` 只在全部 ledger 写完后更新；失败另写 `health.json`。

正式 raw ledger 默认被 `.gitignore` 排除，因为包含真实订单号、成交号、费用、现金流和持仓；
只提交脱敏后的实验摘要与本合同。它是本机生产事实，不是可发布数据集。

验证命令：

```powershell
.\.venv\Scripts\python.exe -B -c "from quant.broker_execution_ledger import validate_broker_execution_ledger as v; print(v())"
```

## 费用与现金边界

Moomoo 返回的是订单级 `fee_amount`，不是逐 fill 费用。一单多次成交时，每个费用版本只保存一次；
v1 不把它复制到每一笔 fill，也不把按 notional 分摊的估算冒充 broker-reported fee。
`fee_amount=N/A` 保存为 `null + pending_or_unavailable`，绝不当成零。

现金有三层含义，不能混用：

1. fill 的 `gross_trade_cash_flow_before_order_fee` 是由数量和成交价推导的交易现金流；
2. `cash_flows.jsonl` 是券商报告的清算流水，可能已经包含费用、股息、利息、换汇或入出金；
3. `account_snapshots.jsonl` 的 `cash` 是采集时账户状态，不是每一笔旧成交后的余额。

因此交易成本汇总不能把 cashflow 和 order fee 再相加一次。历史成交可以回填，历史“成交后现金/杠杆”
无法从今天的账户快照还原，`state.json` 明确标为 `historical_post_fill_account_state=unavailable`。
从首个快照开始，真实负现金会原样保留，不截成零。

## 生命周期与数量对账

券商 deal API 不返回可靠的 position lifecycle。最新 `CANCELLED` deal 不参与经济投影，最新
`OK` / `CHANGED` deal 才进入 `fill_lifecycle_links.jsonl`。链接按完整 broker time，
再按 `deal_id` / `order_id` 确定性排序，识别 open / add / reduce / close / reopen。
同日全平再买会形成不同 lifecycle。重放先用当前券商数量反推历史窗口起点；非零起点视为
`baseline_unknown`，直到出现可验证 flat boundary 才链接后续生命周期。单笔成交跨过零轴时没有
足够信息拆成两个真实 fill，故从该行起持续 `ambiguous_until_flat`，不会生成 synthetic fill。

`state.json.position_qty_reconciliation` 将全部已保存成交重放净数量与最新券商持仓比较。
两年查询窗口之前的持仓、转仓、拆股和其他公司行动都可能造成差异；这些差异只进入
`mismatch_not_synthetic_fill`，不能通过伪造成交“修平”。

`fill_lifecycle_links.jsonl` 本身也是版本账本，不能直接数全部行。消费者必须按 deal 身份取最新
link 版本，并遵守 `state.json.lifecycle_replay.rule_version`；最新 CANCELLED deal 会有显式
`void_cancelled` tombstone。当前有效映射数看 `active_mapping_link_count`，可信闭环数只看
`trusted_closed_lifecycle_count`。

## 当前与后续边界

v1 已满足 `docs/live_drift_reconciliation.md` 中“物化 deal history 且至少 20 个已平仓生命周期”
的重开前提，但本实验不顺便改变 live-drift 阈值或控制门禁。后续消费者应另行做单一可归因验证：

首次 live proof：589 个 distinct deal，其中 588 个 latest-effective、1 个 latest-CANCELLED；
554 个有效成交订单与 order `dealt_qty` 完全一致且都有费用；87 个 closed lifecycle 通过当前数量锚定，
另有 6 个证券的窗口起点未知、103 条 lifecycle link 保持 unlinked/quarantined。

- exit-side realized-vs-modeled drift；
- 用首个 contributing `deal_id` 加固 pending-action lifecycle；
- 用真实订单库存区分“券商已挂单”和“人工指令”；
- 将订单级费用按明确方法分摊到已平仓 P&L（仅派生层）。

## 日报中的已平仓交易盈亏（exp-20260906-001）

`quant/broker_performance.py.compute_broker_performance()` 现在只读投影本机账本，
同一份 `broker_performance` 同时进入日常报告和 `quant_signals` JSON。缺失或损坏时
显示 `unavailable` 与空值，不会显示成赚亏零元。原交易日记和 paper gate 指标分别保留，
不会覆盖券商交易盈亏。此接线不改交易信号、排序、仓位、退出或权限。

消费者先验证全部八条链，再仅允许有成功 manifest 的 `(account_key, collection_id)`
进入最新版本投影。未提交采集中的事实和修订保持原字节，但对绩效不可见。
每笔有效成交必须精确连接当前规则的最新生命周期链接，并通过输入前缀、零仓位起点、
连续数量轨迹和完整平仓检查；只支持能按股数直接计算现金流的美元美股/ETF，期权等
缺乘数合同的证券不参与。未知历史起点、跨零但无法拆分的成交、未平仓和过期链接均排除。

`net_trading_pnl_after_order_fees` 是**同一批费用完整的闭环交易**的有符号成交现金流，
减去最新券商订单费用。一个订单全部有效成交必须都在同一个可信生命周期内，且合计数量
精确等于最新订单 `dealt_qty`；费用每单只扣一次，不分摊给跨生命周期订单。
成交、订单和费用的币种必须明确为 USD。费用缺失、待定或币种未知时整个生命周期不计入
该批毛额/净额，不能用零费用替代。各项排除原因可能重叠，不能把原因计数相加当成交数。

这个数字不包括融资、借券、分红、未平仓盯市、换汇和资金进出，也没有决策到订单的策略
归因，所以不能称为 Ginger 策略收益、整个账户回报率、Sharpe 或 replacement value。
报告同时列明有效覆盖范围、排除原因、来源时间及哈希。`trade_enabled=false`。
独立离线验证入口是
`quant/experiments/exp_20260906_001_broker_performance_reporting.py`；冻结输入后运行两遍，
核对汇总一致、源字节不变及真实输出语句接线，结果仅保留脱敏聚合。

同实验 revision 2 补上反向完整性检查：每条最新已提交生命周期链接所指的成交版本，
必须存在于全部可见成交版本中（包括旧版本及撤销版本）。链虽然合法，但尾部成交被整段
截掉时，会返回 `unavailable` / `source_integrity_status=source_incomplete`；不能悄悄丢掉
亏损闭环后继续公布剩余盈利。

`latest_collection_attempt_at` 只表示最近提交采集尝试的时间。`query_coverage` 分别记录
历史成交、历史订单、订单费用的最新查询状态及最后成功时间；error、partial、skipped
和旧 schema 缺失状态都会明确降低覆盖，缺失写 unknown。`source_as_of` 取三项最后
成功时间中的最早值，任一项无成功时间则为空，不再用一次失败刷新伪装经济数据已更新。
修订前 artifact 和冻结合同保留；当前验证证据在
`data/experiments/exp-20260906-001/revision_2/`。


## Full history range paging (exp-20260906-008)

The configured 730-day lookback is retained. The installed broker returned a
360-day maximum query-span error; this limit is local response evidence, not a
claim about wording in the public API documentation. SDK date arguments include
both endpoint dates. Each request therefore covers at most 360 calendar dates
(end = start + 359 days; next start = end + 1 day). Freeze UTC today once.

History deals and orders each have a parent query result plus separate
`history_deals:START..END` / `history_orders:START..END` child keys. All segments
must succeed for the parent to be `ok`; mixed outcomes are `partial`, complete
failure is `error`. Child keys preserve bounds and outcomes in the existing
collection-manifest contract. Current observations remain last; order-fee
batching, deduplication, cancellation and rate limits retain their contracts.

An observed A -> B -> A version transition appends the final exact observed fact
with a collection-specific `reobserved` identity when content deduplication would
otherwise leave B current. This changes the observation version, never the
economic deal identity or old ledger rows. A committed capture replay validates
all snapshot conflicts before returning zero appended rows. If a manifest commit
succeeded but state writing was interrupted, only the latest committed capture
may rebuild the derived state, and all raw append plans must remain empty. An
older capture cannot rebuild state from its stale position anchor.

The real 2024-09-06 through 2026-09-06 window used 360/360/11 inclusive-day
segments for each endpoint. All six succeeded. Only new rows were appended by
the existing ledger API; all eight old JSONL prefixes remained byte-for-byte
unchanged. Account identifiers and raw captures remain in gitignored local
storage. The public experiment proof contains counts and aggregate PnL only.
Repeat the frozen final-capture validation without new broker calls using:

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260906_008_broker_history_date_range_paging.py --verify-existing-capture
```

This is an engineering measurement repair. The evaluated 103-lifecycle subset
still loses USD 14,712.8662 after order fees. Of 105 groups carrying a close event,
two fail complete quantity-path validation and remain excluded. Open positions,
unknown baselines and unsupported instruments remain outside this PnL; it does
not establish Ginger strategy returns or total account returns.
