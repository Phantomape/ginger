# 下一步方向决议 — 2026-06-28(alpha 干涸一周后)

> 给执行 agent 的自含 brief。来源:A↔B 多 agent 文件信箱辩论,channel
> `alpha-next-direction-20260628`(本地、未跟踪,见 `docs/agent_mailbox.md`),
> 3 个来回后双方一致。本文件是可执行版;开工前仍按 `AGENTS.md` §3-§7 走。

## 问题与判断

**问题:alpha 一周没挖出东西,下一步方向怎么定?**

**判断:这周空手是 frozen-window 横截面饱和面的预期产出,不是点子荒。** 最近约
一周的 accept 几乎全是 EV+0.0000 的 allocator notional-scalar(增量资本套利,非
新选股 edge);排前的研究家族全挂 heavily-explored / diminishing-return 护栏。
正确响应是把 alpha_search **重定向**(不是暂停)到"产可结算 forward 行 + 开新
证据轴",并用预注册硬闸门防止滑成 measurement treadmill。

## 已核实的事实(执行前请信任这些,已逐条对账)

- `low_deployment_etf`:`data/paper_sleeves/low_deployment_etf/state.json` 有
  **17 条 `closed_positions`**(entry 2026-05-12→06-04,0 open,1 pending),
  每条已带 `entry_regime_*` / `entry_exhaustion_*` / `entry_short_volume_*` /
  `replacement_value_vs_spy|qqq|cash`。即已埋点、零新建,只差结算累积。
- `exp-20260628-014` `accepted_core_form4_selling_overhang_attribution`:
  **observed_only 正向** edge——entry 前 10 天高 PIT Form4 卖出 + 10b5-1 →
  更差 loss-tail / 更低 PnL。是 Form144 方向的依据。
- `exp-20260628-004` `ortex_borrow_fee_sidecar_readiness`:**blocked**(仅 AAPL、
  无 usable/publication date、无 daily ledger)。借券源本周只能是 ingestion
  contract,不是 alpha。
- **更正**:辩论中曾把"17 条 closed rows"挂到 `exp-20260628-007`——那其实是
  `forward_regime_scorecard_current_refresh`(blocked),与 low_deployment_etf
  无关。数字对、ID 错,执行时以本节为准。

## 现在做什么

### 唯一要 reserve 的实验:Form144 planned-sale/float 前瞻 context logger

- **lane**:alpha-enabling forward-row 埋点(`AGENTS.md` §2.3 豁免)。
- **硬约束**:`trade_enabled=False`,**只产 default-off context,不碰
  sizing/ranking/orders**;严禁先行 notional haircut / risk scalar。
- **在 exp-20260628-014 之上推进的新证据轴**:不是换 ledger,而是把 Form4 卖出
  overhang 推进到 **Form144 计划卖出**这个可交易因果维度。
- **build 三件**:
  1. Form144 PIT 解析:`planned_sale_shares`、`planned_sale_to_float`、
     `planned_sale_to_adv`、计划期起点、usable/publication date;
  2. 每日给 accepted-core / default-off 候选入场打 as-of-entry 的 Form144
     context 标签(PIT 安全),append-only,结算时写 cash/SPY/QQQ replacement
     value;
  3. outcome join schema(context 行 ↔ forward 结果)。
- **预注册接受闸门(写进 ticket 的 `reopen_condition`,THE gate = Form144
  planned-sale/float)**:
  - `planned_sale_to_float` 或 `planned_sale_to_adv` 可机器解析且带 usable date;
  - ≥ **25** 条前瞻闭合行(带 cash/SPY/QQQ replacement value);
  - 其中 ≥ **8** 条属预声明 high planned-sale/float bucket;
  - 单 ticker 闭合行占比 ≤ **40%**;
  - 连续 **3** 次只做 materialization / readiness 但无新增可闭合行 → **park**,
    `reopen_condition` 写清缺哪个计数。
- **novelty**:`experiment.py new` 会自动跑近邻闸门;大概率撞到
  exp-20260628-014 附近,需 `--novelty-override --new-evidence-axis "Form144
  planned-sale/float PIT field, 无前例"` 声明真新轴。**不得**用自由文本绕过;
  撞不过就换假设。
- **allowed_write_scope**:logger 脚本 + Form144 ingestion +
  `data/non_ohlcv/form144_*.jsonl` ledger + ticket/shard。**不**手写
  registry/log。

### 不该开实验的两块(纪律重点)

- **low_deployment_etf**:已埋点、正累积,17 条未到激活阈值。现在 reserve 任何
  readiness/activation 实验都**违反 §2 reopen-count 硬闸门**。正确动作:让它继续
  结算 + 一行 count 比对(对照本文件记录的 17),**不占实验 ID**。
- **ORTEX/borrow(exp-20260628-004)**:后台 ingestion contract;只验 ticker
  breadth / publication date / append-only ledger / settled join,不叫 alpha;
  breadth/date/ledger 物化前不重开。

## 之后(命中阈值才触发)的两个 Gate-1-4 实验

1. low_deployment_etf 闭合行数到预注册阈值 → reserve **一次** activation/Gate-1-4。
2. Form144 logger 命中 ≥25 / ≥8 / 单 ticker ≤40% → reserve **一次**
   risk-allocation Gate-1-4(此前禁止任何 notional haircut/scalar)。

判定本身才消费实验 ID;在那之前 producer 只 append/settle/count。

## 禁止 / 成功指标

- **禁止**:frozen-window 横截面扫描、同面 response retune、quick-monetization
  (现有 execution/exit/portfolio 全 frozen)、第三个 readiness 面。
- **成功指标**:净新增已结算 forward 行 + 净新增 PIT 证据轴 + 被 park 面数
  (**不是** accept 数)。
