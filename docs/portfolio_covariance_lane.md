# Portfolio / Covariance Lane（组合车道：冠军挑战赛棘轮的对冲）

> 背景（2026-07-06 系统盲区评审）：Gate 4 是冠军挑战赛——挑战者必须在三个固定
> 窗口上正面击败当前最强组合或同族比较器。每次接受都抬高下一次的门槛，系统
> **必然**渐近收敛到 0-accept，与市场是否还有残余 edge 无关。截至 2026-07-06，
> 历史上有 **111 个实验**在聚合结果非负的情况下，仅因 `accepted_*_ev_not_beaten`
> 类比较器或单窗口噪声被拒（如 moomoo capital-flow exp-20260702-019：+EV，
> 仅输给 distribution 比较器）。冠军自身只有 ~61 笔、其 EV 是宽置信区间点估计，
> 头对头误拒率不可忽略。
>
> 核心命题："打不过冠军" ≠ "加进组合没价值"。与冠军相关性低、standalone EV
> 略逊的信号，组合意义上可能提高有效前沿。立项时系统没有这条评估车道；当前正式口径见
> 下文 Gate 4-P v1。

## 车道定义（历史立项口径；正式合同见下文 Gate 4-P v1）

本节保留 2026-07-06 的立项语境；2026-07-14 owner 已授权独立的
portfolio-contribution Gate，正式判定一律以下文 **Gate 4-P v1** 为准。该授权只修订
组合贡献车道，不修改原 champion-replacement Gate 4。

**准入对象**：被拒但满足全部三条的历史实验/信号——
1. 聚合 EV 与 PnL 非负（`aggregate_ev_not_positive`、`aggregate_pnl_not_positive` 均未命中）；
2. 拒绝理由只含比较器（`*_not_beaten`）或窗口噪声（`window_*_regression`、
   `fewer_than_two_ev_improved_windows`）类条目；
3. 有可回放的逐笔 trade 列表（artifact 内或可由 runner 复现）。

**评估口径（区别于 Gate 4）**：
- 不问"是否击败冠军"，问"以小权重（≤10% 风险预算）并入冠军后，组合
  aggregate EV / drawdown / 尾部是否改善"；
- 必须报告与冠军日收益序列的相关性（复用 exp-20260620-033 sleeve 独立性图的口径）；
- 多重检验现实：111 个候选里含大量同族阈值变体，先按 frozen family 去重，
  每族只取代表，预期真实独立候选是"个位数到十位数"，不是 111。

**验收**：组合级改善仍走 `docs/backtesting.md` 的多窗口 aggregate 口径
（EV 提升 >10% 的 state_surface 同类阈值同样适用）；单一低相关信号以
observed-only 并入 forward 观察，不直接给真钱权重。

## 第一步（可单实验完成）

一个 alpha-enabling 测量实验：扫描 111 个候选 → frozen-family 去重 → 对每个
代表回放逐笔序列 → 输出与冠军的相关矩阵 + 小权重并入的组合 delta 表。
产出物即本车道的第一份 candidate ranking，此后车道按该 ranking 消费候选，
不再重复扫描。

## 车道状态（2026-07-07）与消费协议

- ranking 已建：exp-20260706-022（31 个 admissible 候选，closed-trade cashflow
  proxy 口径，artifact 在 `data/experiments/exp-20260706-022/`）。
- 2026-07-06 → 07-07 已按"一名一 ID"消费 11 个代表（rank 1-13 区间，固定 10%
  日 mark-to-market equity overlay 配方），**全部 observed_only_rejected**：
  023/024/025、20260707-001/003/005/006/007/008/015/016。
- **消费协议（自 2026-07-07 起）**：配方固定后，剩余代表禁止继续一名一 ID
  枚举（见 AGENTS.md §2.4 排名清单消费通道）。合法出路二选一：
  1. 单个批量实验把剩余 admissible 代表全部跑完，输出一张 per-family delta 表
     一次性收尾；
  2. park 车道，`reopen_condition` = 出现新的 rejected-positive 候选家族（相对
     31 个基数明显新增），或冠军日收益序列结构变化使相关矩阵需要重算。
- 前 13 名全灭是对车道假设本身的强证据：小权重低相关 overlay 在当前冠军
  序列上没有可测组合增益；批量收尾后若仍全灭，车道整体 park，不做配方变体
  （改 overlay 权重 / 相关阈值属于被禁的 retune）。

## 2026-07-07 车道裁定（exp-20260707-017：PARKED，走上节出路 2）

exp-20260707-017 对 11 个已完成 overlay artifact 做只读联合综合（不重跑任何
overlay、不调任何源），结论是**执行 park，且不建议再花批量实验跑 rank 14-31**，
因为当前评估配方在车道自身口径下结构性 0-accept，批量收尾只会物化更多噪声门
拒绝。量化依据（全表见
`data/experiments/exp-20260707-017/exp_20260707_017_portfolio_lane_gate_calibration_joint_verdict.json`）：

1. **噪声门**：11 个 overlay 中 10 个聚合 EV delta 为正、11 个聚合 PnL delta
   为正、drawdown 漂移全部 ≤0.36pp、与冠军日收益相关性 0.06–0.23，但逐窗口
   零容忍 EV 回归把它们全部拒绝；其中 8 个的拒绝**仅**由噪声级回归触发
   （|delta| < 该窗口冠军 EV 的 1%，或该窗口 PnL 实际非负；最极端一例
   exp-20260707-016 old_thin EV delta = −0.0003 且该窗口 PnL +$57）。零容忍
   三窗口符号检验下，纯噪声 overlay 的通过率也只有 12.5%——所以"前 13 名
   全灭"**不能**读成对车道假设的强证据：全灭近乎是门保证的，与候选质量无关。
   这正是本车道立项时要对冲的棘轮，在车道内部被复刻了。
2. **验收条款联合不可满足**：≤10% 风险预算帽下，实测最好的候选聚合 EV 提升
   只有 +0.77%（rank-1 fixed-asset turnover），而验收条款要求 >10%。凡
   standalone EV 明显低于冠军（~10.6 daily-mtm proxy）的候选——即本车道全部
   准入对象——在 10% 权重下数学上不可能到达该门槛。批量跑完剩余 18 名不改变
   这个算术。

**reopen 条件**（满足其一才恢复消费；不允许在单实验里自造新口径）：

1. owner 级修订本文档验收条款：(a) 给组合级窗口回归设 materiality 阈值
   （例如忽略 |EV delta| < 冠军窗口 EV 1% 的回归），且 (b) 把 >10% 聚合 EV
   门槛换成 ≤10% 权重帽下可达的门槛（例如"聚合 EV delta > 0 且 ≥2/3 窗口
   非负且 drawdown 漂移 ≤0.5pp"级别）；修订后可用**单个批量实验**按新口径
   重判全部 31 名（已物化的 11 份 daily-equity 路径可直接复用）；
2. 出现 standalone 聚合 EV 与冠军同量级（~1x）的新 rejected-positive 候选族，
   使 ≤10% 权重在数学上可能清过 >10% 门槛；
3. 某个已有 default-off forward ledger 的排名候选（如 rank-23
   finra_otc_internalization_retreat）积累实质数量的已结算 forward
   replacement-value 行，走本文档 observed-only forward 条款评估。

## 2026-07-14 owner 授权：Gate 4-P v1（exp-20260715-002）

Owner 于 2026-07-14 明确授权按本节合同重开组合车道；本次授权由
`exp-20260715-002` 持有，并且只允许一次 31-family 完整批量判定。它满足上节
reopen 条件 1，但不是对既有 Gate 4 的放宽，也不授权逐项 retune 或恢复“一名一 ID”。

### 1. 两种问题、两道互不替代的门

- **Champion-replacement Gate 4 保持原样**：继续回答“挑战者能否替换当前冠军”，其
  before/after、窗口和通过条件仍只以 `docs/backtesting.md` 为准。
- **Portfolio-contribution Gate（简称 Gate 4-P）独立判定**：只回答“把候选以小权重、
  资金守恒地加入 core，是否改善组合”。Gate 4-P 的通过不能反向改写 Gate 4 结论，
  Gate 4 的拒绝也不能代替 Gate 4-P 的组合级测量。

### 2. 锁定的资金与比较合同

每个候选在同一交易日历上构造 `90% core + 10% candidate` 的 constant-mix 组合；
两条腿权重合计必须等于 100%，不得把 candidate 当成额外杠杆叠在完整 core 上。候选权重
上限锁定为 10%，正式判定的唯一比较器是 **100% core**：

```text
formal_delta = metric(90% core + 10% candidate) - metric(100% core)
```

批次还必须同时披露相对 `90% core + 10% cash` 的诊断 delta，用于区分“候选 sleeve
本身贡献为正”和“候选足以覆盖挤出 10% core 的机会成本”。该诊断值**不参与正式判定**；
即使相对 cash 为正，也不能挽救相对 100% core 的正式硬失败。

候选腿的单位资本合同同样锁定，避免把源行的 `$4,000` notional 先除以 `$100,000`、
再乘 10% 而二次缩成约 `$400`：每个窗口从 `$10,000` candidate cash 开始，入场本金与
entry fee 只能使用当时现金；同日多个 entry 按含 entry fee 的请求额 pro-rata，同日收盘
exit 的回款不能供当天早盘 entry 使用。退出按实际 shares、有效 exit price 与 exit fee
回款，已实现盈亏会改变后续可用现金；禁止负现金或隐含杠杆。candidate return 以该
`$10,000` NAV 为分母，再进入 `90/10` constant-mix。source entry/normal-exit fill 已各含
5bp slippage，窗口末强平也按 raw close 扣 5bp sell slippage；此外交易费按 funded
notional 双边各 17.5bp，因此 all-in round trip 为 45bp。

### 3. 固定批次与路径构造

- 输入锁定为 exp-20260706-022 ranking 的 **全部 31 个 frozen-family
  representatives**，在 `exp-20260715-002` 内一次跑完并输出完整 per-family 表；不得只挑
  已有 overlay、前若干名或“看起来最好”的代表。
- 三个标准窗口保持固定、互不延长；同一窗口内 core 与 candidate 使用完全相同的日期轴。
- 入场日晚于窗口末日的交易不进入该窗口；在窗口末日仍未退出的持仓按末日可得收盘价强平，
  不允许为等待原 exit date 而把窗口向后延伸或把收益泄漏进下一窗口。
- 价格行、交易成本、强平数量、缺失/排除行及输入 hash 必须随 artifact 保存，使 31 个候选
  能从同一冻结输入重放。

### 4. 联合统计合同

31 个候选必须共用一次 **paired、window-stratified circular block bootstrap**：各候选与
core 在每个窗口使用同一组重采样索引，窗口之间分别抽样后再聚合；block length 固定为
20 个交易日，重复 10,000 次，并把随机 seed 写入 artifact。候选之间用同一批 bootstrap
draw，以 max-T 构造 aggregate EV delta 的单侧 90% simultaneous lower bound。

`multiple_testing_passed` 只在候选的 simultaneous lower bound `> 0` 时成立。不得把逐候选
未校正 p-value、普通 bootstrap 区间或事后挑选最佳候选当成联合通过证据。

### 5. 经济/风险硬失败与证据阻塞必须分开

**硬失败（hard failure）**表示候选按已观测路径没有组合价值；命中任一条，结论直接为
`portfolio_reject`：

1. 相对 100% core 的 aggregate EV delta `<= 0`；
2. 相对 100% core 的 aggregate PnL delta `<= 0`；
3. 超过一个窗口发生 material regression；material regression 仅在该窗口
   `EV delta < -1% * abs(core window EV)` **且** `PnL delta < 0` 时成立；
4. max drawdown 恶化超过 0.5 个百分点，或 95% expected shortfall 恶化超过 5%；
5. 候选权重超过 10%，或组合集中度超过 single-name 50%、top-5 60%、HHI 0.35 中的任一帽。

**证据阻塞（evidence blocker）**表示经济路径尚未被充分证明，不等同于负 alpha。包括但
不限于：无法证明资金守恒；受影响交易少于 20 笔或覆盖少于两个窗口；风险/集中度字段缺失；
31-family 批次不完整；多重检验未通过或其输入 selection panel 不完整。证据 blocker 不得
伪装成 hard failure，也不得被普通点估计覆盖。

### 6. 三态 verdict 与权限边界

Gate 4-P 只能输出以下三态：

- `portfolio_reject`：至少命中一个 hard failure；
- `portfolio_forward_watch`：没有 hard failure，但存在一个或多个 evidence blocker；
- `accepted_portfolio_paper`：没有 hard failure、没有 evidence blocker，并且
  `multiple_testing_passed=true`。

`accepted_portfolio_paper` 的最高权限仍只是 **default-off paper**：不得据此改变 live/default
orders、core ranking、sizing、exit 或真钱风险预算，更不等于 live-ready。进入真钱前仍需独立的
prospective ledger、生产/回测 parity、live-realistic execution envelope、kill switch 和后续
live gate；这些证据不能由历史 Gate 4-P 回放替代。

### 7. 本批次已知的 selection-panel 上限

31 个代表构成 exp-20260706-022 已保存 ranking 的完整 family-representative 批次，但并不构成
历史搜索选择面的完整统计 panel：原始约 264 个 rejected-positive selection candidates 的完整
逐候选选择记录没有被保存，现有文件无法无损恢复。因此 `exp-20260715-002` 必须固定记录
`panel_complete=false`，把该缺口列为 evidence blocker。

这意味着本批次即使经济/风险硬条件与 31-family max-T 都通过，verdict 上限仍为
`portfolio_forward_watch`；若任何 hard failure 命中，则仍为 `portfolio_reject`，不能用
panel 不完整把负结果降格成“未知”。只有未来拿到预先冻结且完整的 selection panel，或积累不受
这段历史选择污染的 prospective ledger，才可能解除该 blocker 并获得
`accepted_portfolio_paper`。

### 8. exp-20260715-002 实测结论

完整批次已在 31/31 family representatives、三个固定窗口和同一 `$10,000` cash-ledger
sleeve 合同上跑完。2,230 个源交易中，1,030 个全额成交、625 个部分成交、559 个因当时
无可用现金而不成交，另有 16 个入场日晚于固定窗口末日而排除；所有 93 个
family-window cash ledger 均保持非负并与末日 MTM equity 对账。冻结 OHLCV replay 使用
13,590 行 potential-row superset，其中 10,319 个 ticker-date 行被实际 funded paths 消费，
缺失为 0。

正式比较的结果是 **31/31 `portfolio_reject`**：没有一个候选同时取得相对 100% core 的
正 aggregate EV delta 与正 aggregate PnL delta，也没有一个 90% simultaneous EV lower
bound 大于 0。最佳候选是 `exp-20260626-003`
`companyfacts_purchase_obligation_maturity_ladder_candidate_pool`：

- 相对 100% core：aggregate EV delta `-0.94934`，PnL delta `-$19,348.24`；
- 相对 `90% core + 10% cash` 的诊断：EV delta `+0.64143`，PnL delta `+$11,059.52`；
- 最坏窗口 drawdown 漂移 `+0.4718pp`，仍在 0.5pp 帽内；ES95 恶化 `+5.71%`，超过 5% 帽；
- simultaneous 90% EV lower bound `-2.49485`。

全 panel 中有 18/31 个候选相对 cash 的 EV 与 PnL 同时为正、28/31 的 PnL 为正，但这些
贡献都不足以覆盖被挤出的 10% 当前 core。结论因此不是“分散化不存在”，而是“在当前
强 core 和锁定资金成本下，这批历史候选还不值得获得 10% funded replacement budget”。
不得据此把诊断正值升级成 paper/live acceptance，也不得在这 31 个 frozen representatives
上逐项 retune；重开需要新的 prospective ledger、完整预冻结 selection panel，或真正新的
候选/风险预算 gate shape。

**observed-only forward 关注名单**（本文档验收节本就允许低相关信号
observed-only 并入 forward 观察；仅记录，不新建 sleeve、不给权重）：
`peer_earnings_reaction_transfer`（corr 0.060，ΔEV +0.021）、
`volatility_curve_relief_stock_leadership`（corr 0.178，ΔEV +0.034）、
`distribution_pressure_low_beta_defensive_leadership`（corr 0.178，ΔEV +0.027）。

## 顺带记录：研究节奏

结算行按周/月到达，实验按日强制生成——系统超频于自身信息到达率。若把
每日 alpha 调度降到每周（保留每日数据管道与 sleeve 日更），按近三周日志
推断信息损失接近零。这是 owner 的调度决策，记录在此供参考，不是硬规则。
