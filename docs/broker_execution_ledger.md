# Broker Execution Ledger

## 已知遗留

- 当前校验器会验证八条哈希链，并要求至少存在一条成功的 `collection_manifest`；它还没有逐行证明每个事实行的 `collection_id` 都属于一个已提交采集。若进程恰好在事实落盘后、manifest 提交前失败，下一次采集前仍可能留下 orphan collection 版本。后续修复应引入逐 collection 的 commit/visibility 校验，不能把“链有效”误解成“每次采集都完整提交”。
- 现金流水日更只滚动抓取最近七个清算日。停机超过七天时，仍需要基于 manifest cursor 的限速补采；当前系统不声称更早的现金流水完整。

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
