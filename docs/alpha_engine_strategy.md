# Alpha Engine Strategy（独立收益引擎路线）

> 状态：研究方向合同，不是交易规则、实验验收记录或 live 授权。具体窗口、指标、
> novelty、生产一致性与实验留痕，分别以
> [backtesting.md](backtesting.md)、
> [agent_experiment_protocol.md](agent_experiment_protocol.md)、
> [production_backtest_parity.md](production_backtest_parity.md) 和
> [AGENTS.md](../AGENTS.md) 为准。

## 1. 目标与引擎定义

Ginger 当前已有 **Engine 0：趋势 / 大赢家引擎**。它以中期多头趋势、相对强势和
少数大赢家的延续为主要 PnL 来源。未来目标不是继续堆同类信号，而是在 Engine 0
之外建立三个可单独归因、可独立结算的净收益引擎：

1. **Engine 1：信息 / 事件驱动 alpha**；
2. **Engine 2：市场中性相对价值 / 错价收敛**；
3. **Engine 3：结构性流量 / carry**。

这里的“多样化”是 **独立的、扣除全部成本后仍为正的 PnL 机制**，不是：

- 接入了多少不同数据源；
- 创建了多少 observer、ledger 或 `trade_enabled=false` sleeve；
- 给同一趋势响应换了多少事件标签、字段或阈值；
- 得到低 beta / 低相关但 standalone EV 为负的收益序列。

引擎独立性有两层：首先，赚钱因果链必须不同；其次，才衡量与 core 的相关性、beta
和因子暴露。低相关不能挽救负 EV；同一数据源若支持不同且可证伪的赚钱机制，可以
服务多个引擎，但“数据不同”本身不构成新引擎。

北极星指标继续是：

```text
expected_value_score = strategy_total_return_pct * abs(sharpe_daily)
```

任何新引擎必须先证明 standalone after-cost economics，再讨论低相关和组合权重。

## 2. Engine 0：趋势 / 大赢家（现有基线）

- **机制**：价格趋势、相对强势和基本面/事件确认延续，使少数大赢家覆盖多数小亏损。
- **风险画像**：通常是净多头、正市场 beta，收益容易集中在风险偏好强和趋势清晰的
  窗口。
- **战略角色**：继续作为 core 与新引擎的机会成本比较器；不把 OHLCV top-N、阈值、
  hold 或 notional 的近邻 retune 误称为新引擎。
- **扩展条件**：仍须通过标准 Gate 1-4；现有方向与冻结区见
  [alpha-optimization-playbook.md](alpha-optimization-playbook.md) 和
  [alpha_context_pack.md](alpha_context_pack.md)。

## 3. Engine 1：信息 / 事件驱动 alpha

### 机制

可审计的新信息进入市场后，投资者存在理解、传播或预期调整迟滞。LLM 只负责把原始
文本映射为带证据跨度的结构化事实、事件类别和语义强度；确定性 policy 决定候选、
entry、ranking、sizing、exit 和订单。PnL 来自信息被逐步定价，不来自“模型知道内幕”
或无来源的情绪判断。

### 候选数据

- SEC EDGAR 的 8-K、10-Q、10-K、Form 4、XBRL / Companyfacts 与明确 accepted time；
- 公司正式披露和有初始发布时钟的监管/政府数据；
- FDA、Fed、BLS、BEA、Treasury 等官方发布的 hash-bound 初始版本；
- PIT analyst revision / expectation trajectory，可作为预期调整机制的补充输入。

这些只是候选面，不是“一源一 ID”的消费清单。源合同、身份映射、密度或 PIT
不合格时应先 park 或批量 preflight，不得以换 source 名称循环同一固定响应配方。

### 持有期

默认是公告后下一可交易时点至约 5–20 个交易日；具体 horizon 必须由事件的经济传导
速度预先声明，不能在看到结果后扫描最优持有期。

### 中性与执行

- 可以是方向性事件篮子，也可以做 sector / benchmark residual；方向性并不自动否定
  机制独立，但必须披露 beta 和与 Engine 0 的重叠。
- 严格使用 publication / received-at / usable-trade clock；禁止用同一开盘后才知道的
  信息回填同一开盘成交。
- 采用下一可执行价、真实费用与滑点、流动性/并发/冷却限制；高潜力方向默认
  shared-paper-first。
- LLM 必须记录输入来源、证据跨度、schema/model/runtime 版本和失败桶；解析失败
  fail closed，LLM 不拥有交易硬决策权。

### 主要失败模式

- 修订后的当前网页冒充历史初始版本、错误 publication clock 或实体映射；
- LLM 幻觉、schema 漂移、不可回放输出或语义标签没有增量信息；
- 事件样本稀疏、ticker/source 集中、市场已预期、反应窗口过短；
- gross edge 被开盘跳空、点差、滑点和组合挤出吞噬；
- 只是给 Engine 0 的趋势候选增加同义确认层，未形成独立 PnL。

### 晋级门

1. 源的初始版本、时钟、映射与许可可审计，LLM 输出可按证据跨度重放。
2. standalone 策略在全部成本后 aggregate EV/PnL 为正，且不是单窗口、单 ticker
   或未来函数结果；按标准多窗口 Gate 1-4 判定。
3. 同一 shared helper 同时驱动 historical replay 与 daily default-off snapshot，随后
   的已结算 forward 行可复现同一决策。
4. 资金守恒地加入 core 后改善组合 EV 与 PnL，且 drawdown、尾部和集中度可接受。
5. live-realistic envelope 覆盖 notional、流动性、滑点、订单时钟、暴露上限、失败处理
   和 kill switch；否则最多是 accepted default-off。

## 4. Engine 2：市场中性相对价值 / 错价收敛（第一优先）

### 为什么先做

在三个新引擎中，Engine 2 是第一研究优先级：Engine 0 的主要风险是方向性 long beta，
而一个 **自身净赚钱** 的慢速相对价值账本最有机会提供不同的 PnL 因果链和较低市场
暴露。这里优先的是日频/事件频率的经济错价收敛，不是高频统计套利。优先级不豁免
novelty、样本、成本、short feasibility 或 Gate 1-4；没有合法新证据轴时应等待或换机制，
而不是为了“优先”强行开票。

### 机制

在经济关系明确的两个资产或篮子之间，用交易前已知信息识别临时相对错价；同时建立
long/short 腿并控制系统性暴露，PnL 来自 spread 向可解释锚点收敛，而不是市场整体上涨。
锚点可以是基本面、事件、资产负债传导、持仓/NAV 或结构性供需关系，不能只因为历史
价格相关就假设必然均值回归。

### 候选数据

- PIT SEC fundamentals、revision 或 issuer-specific official event 与严格匹配的行业 peer；
- ETF/篮子持仓、NAV、成分或官方发布造成的相对估值/传导差；
- 企业行动、资本结构、双重证券或同一经济敞口的可交易价差；
- borrow fee、utilization、availability 和 broker locate/size；
- 仅使用 strictly-prior OHLCV 估计 beta、hedge ratio、波动与流动性。

### 持有期

默认约 5–20 个交易日或一个预先定义的周度/事件结算周期。分钟级噪声、收盘竞价延迟
和盘口排队优势不属于本引擎目标。

### 中性与执行

- 至少披露 dollar、beta、sector/factor 和 core-correlation 暴露；“美元中性”不等于
  经济中性。
- 两腿必须使用可实现的共同决策时钟与成交语义；计入双腿点差/滑点、borrow、dividend、
  financing、recall 和未同时成交风险。
- 不复用 short proceeds；设置 gross/net、单 pair、单行业、并发和资本上限，以及
  convergence/timeout/structural-break exit 和 kill switch。
- 没有真实 locate/availability/size 证据时，只能 default-off paper，不能声称 live-ready。

### 主要失败模式

- 相关性被误当因果，关系发生结构断裂或 hedge ratio 不稳定；
- spread 不是错价而是永久基本面分化，或进出方向写反；
- gross edge 太小，被两腿交易成本和 borrow 吞噬；
- short 无法 locate、被 recall、容量不足，或两腿成交不同步；
- pair/行业高度集中、样本重复、对同一有限 taxonomy 逐项挖掘；
- beta 很低但 standalone EV/PnL 为负。

### 晋级门

1. 配对、锚点、hedge 与退出规则在读 outcome 前冻结，全部估计只用 strictly-prior 数据。
2. standalone pair book 在双腿成本、borrow、dividend 和 financing 后为正，并跨多个标准
   窗口/足够多独立 pair 成立；低 beta 不是替代条件。
3. 实测 beta、core 相关性和因子残差符合预声明的中性目标，压力情景下 gross/net 与现金
   约束不破裂。
4. 资金守恒地挤出 core 资本后，组合 EV 与 PnL 均改善；若走组合贡献车道，严格复用
   [portfolio_covariance_lane.md](portfolio_covariance_lane.md) 的 Gate 4-P 合同。
5. shared historical/daily helper、forward settlement、broker shortability 与容量证据一致；
   通过这些门后才从 candidate 升为 paper engine。

### ORTEX 案例边界

[exp-20260718-004 实验卡](../experiments/cards/exp-20260718-004.md)（另见
[原始 log](../experiments/logs/exp-20260718-004.json)）拒绝的是 **ORTEX CTB-new ×
Moomoo short-volume 的固定 top-4 peer-pair 假设**，不是 Engine 2。该策略的 38 个 pair
在三窗口 standalone 都亏损；candidate EV 为 `-0.0909`、PnL 为 `-$584.28`，虽有近零
SPY beta，仍使组合 EV `6.2057 -> 5.4239`、PnL `$130,992.36 -> $114,688.52`。
这正说明“中性”不能替代正 expectancy。

在同一 ORTEX/Moomoo 行面上，禁止扫描 top-N、correlation floor/lookback、cluster、hold、
cooldown、direction、notional、成本/borrow 口径或 10% 权重。合法重开必须具有可机器核对的
新证据轴，例如：真正的新 signal/gate shape；可持续同日横截面带来的实质新增、已结算
prospective 行；或新的 PIT availability/utilization 加 broker locate 证据。**仅参数 retune
不构成新证据，禁止开票。** 实验的 production/backtest 边界亦记录在
[production_backtest_parity_matrix.md](production_backtest_parity_matrix.md)。

## 5. Engine 3：结构性流量 / carry

### 机制

PnL 来自可预见的非信息型被动买卖、资产负债约束、再平衡/结算需求，或持有某种风险所
获得的可兑现 carry。它不同于 Engine 1 的“新信息被缓慢理解”，也不同于 Engine 2 的
“两资产错价收敛”：这里的经济主体因为规则、日历、融资或 mandate 被迫交易/付费。

### 候选数据

- 指数/ETF 成分、持仓、再平衡、creation/redemption 与可审计的 NAV/premium；
- 企业行动、发行/回购、锁定期、股息与结算日历；
- 期货/ETF roll、期限结构、Treasury 拍卖与月末/季末资产负债流；
- options expiry/dealer positioning，仅限 PIT、许可和可实现的数据；
- borrow fee/rebate、availability 与真实可成交 short inventory。

### 持有期

约 1–20 个交易日、一个 roll 周期或预声明的结算窗口。carry 必须按实际可持有天数与
现金占用计提，不能把 quoted yield 当成已实现 PnL。

### 中性与执行

- 在机制允许时用 benchmark/sector/factor hedge 隔离 flow/carry；完整披露 residual beta、
  gap 和负凸性。
- 计入冲击、点差、roll、融资、borrow、股息、税费/扣缴和提前 recall；明确 auction、
  close 或 next-open 的真实订单语义。
- 容量上限由 ADV、盘口/竞价参与率、可借数量和 crowding 决定；预设 unwind 与 tail-risk
  kill switch。

### 主要失败模式

- 流量早已被 front-run 或当前成分表产生 survivorship/lookahead；
- 日历、时区、公告和生效时钟错配；
- carry 小于交易/融资/borrow 成本，或伴随未计价的 crash/recall 风险；
- 拥挤导致入场冲击和退出反转，容量随规模快速衰减；
- 只观察到“有流量”，却没有可交易、可结算的正 PnL。

### 晋级门

1. 规则/日历/初始版本在交易前可知，flow 或 carry 可以从 source row 到 trade row 完整归因。
2. standalone 结果在所有现金、冲击、融资、borrow、dividend/roll 成本与尾部损失后为正，
   并覆盖多个窗口和多个独立周期。
3. historical 与 forward 使用同一结算、日历和成本 helper；forward 已结算行能复现预声明
   的 carry/flow 账本。
4. 容量、crowding、liquidity、gross/net、gap/recall 与 kill switch 进入 after-measurement。
5. 资金守恒加入 core 后改善组合 EV/PnL，且 drawdown、尾部风险和集中度没有不可接受恶化。

## 6. 引擎级 Scorecard

只有下表全部满足，candidate 才能被称为“新增 PnL 引擎”；observer、正 gross lead、低相关
负 EV 或尚未结算的 default-off sleeve 都不计数。

| 维度 | 必须报告/通过 | 硬失败示例 |
|---|---|---|
| Standalone economics | 扣除 spread、slippage、fees、borrow、financing、dividend/roll 后 EV 与 PnL 为正 | 低 beta 但净亏损；只报 gross edge |
| 机制独立性 | 清楚的因果链；报告与 Engine 0/core 的日收益相关、SPY/QQQ beta 和主要因子暴露；中性型引擎还须低且稳定 | 同一趋势响应换数据源/标签；只凭低相关过门 |
| 组合贡献 | 资金守恒组合的 EV 与 PnL 同时改善，风险与机会成本可接受 | 相对 cash 为正但挤出 core 后变差 |
| 多窗口稳健性 | 标准 fixed windows、足够 trades/survival、非单 ticker/source 集中；按 Gate 1-4 判定 | 只赢一个窗口或样本过薄 |
| Forward 可复现 | shared replay/daily policy、PIT 时钟、hash/version、已结算 forward 行和失败桶一致 | private replay 正向但 daily 无法重放 |
| 容量与执行 | notional/capital cap、ADV/impact、gross/net、borrow/locate、订单语义、并发、kill switch | 假设无限容量、免费借券或同步成交 |

研究状态应按 `lead -> accepted default-off candidate -> forward-validated paper engine ->
capital-promoted engine` 递进。任何阶段失败都保留可复现记录，但不增加引擎数量。

## 7. 明确不做

- 不把 HFT、做市、queue position、跨 venue latency arbitrage 或微秒级 order-book alpha
  作为个人系统目标。Ginger 不具备 colocated feed、确定性低延迟路由、库存/清算和容量优势；
  盘口数据最多先用于执行成本与风险测量。
- 不把“低相关的负 EV”包装成 diversification。负 expectancy 以任何权重加入强 core，
  都可能只是稳定地支付成本；`exp-20260718-004` 已给出直接反例。
- 不为凑齐三个引擎而放宽 PIT、成本、forward、novelty、parity 或 live-realism 合同。

## 8. 研究顺序

1. **Engine 2 优先**：只选择有经济锚点、可实现 short、完整成本和合法新证据轴的慢速
   relative-value 假设；不得 retune ORTEX/Moomoo 已拒配方。
2. Engine 1 与 Engine 3 在源合同和样本先通过 preflight 时并行积累候选；不按数据源逐项
   烧 ID。
3. 每个严肃候选默认 shared-paper-first，并在同一实验内完成 replay、daily default-off、
   成本/执行包络与 Gate 1-4；组合贡献按正式 Gate 4-P 另行使用既有合同。
4. 若没有满足 novelty 的假设，正确动作是等待 forward 行、换机制或 park，而不是调参。

## 9. Engine 2 首次落地结果（2026-07-18）

`exp-20260718-007` 用官方 SEC same-CIK 身份锚点测试了五组双股类别普通股的
稳健溢价收敛。它是新的非价格 pair linkage，不是旧价格相关配对的参数变体；历史价格
只使用实验内保存、hash-bound 的 cold panel，GOOG/GOOGL 因两腿调整版本不一致而在
看结果前排除。

结论是 **rejected，不计为新引擎**：23 笔在双腿成本和 carry 后合计
`-$1,454.49`，standalone EV `-0.4463`，三个固定窗口均为负，20 笔超时且没有一笔
达到收敛退出；SPY beta 虽只有 `0.0105`，但 90% core + 10% candidate 仍把组合 EV
从 `6.2057` 降到 `5.3236`、PnL 从约 `$130,992` 降到 `$113,459`。这说明“结构关系
真实 + beta 很低”仍不能替代 after-cost 正收益。

本结果只拒绝 **same-CIK 双股类别 + 当前稳健锚点 + 十日收敛** 这一固定机制，不拒绝
Engine 2 整条主线。禁止在同一 cold panel 上扫描 lookback、z、退出、持有期、pair
子集或权重；下一次合法推进需要新的经济锚点/gate shape，或至少 35 条新 prospective
已结算 pair、有效期化身份和 broker locate/size。详见实验 card、artifact 和 parity
matrix。
