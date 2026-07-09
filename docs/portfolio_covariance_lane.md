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
> 略逊的信号，组合意义上可能提高有效前沿。系统目前完全没有这条评估车道。

## 车道定义（未实现——本文档先固定口径，防止各实验自造标准）

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

**observed-only forward 关注名单**（本文档验收节本就允许低相关信号
observed-only 并入 forward 观察；仅记录，不新建 sleeve、不给权重）：
`peer_earnings_reaction_transfer`（corr 0.060，ΔEV +0.021）、
`volatility_curve_relief_stock_leadership`（corr 0.178，ΔEV +0.034）、
`distribution_pressure_low_beta_defensive_leadership`（corr 0.178，ΔEV +0.027）。

## 顺带记录：研究节奏

结算行按周/月到达，实验按日强制生成——系统超频于自身信息到达率。若把
每日 alpha 调度降到每周（保留每日数据管道与 sleeve 日更），按近三周日志
推断信息损失接近零。这是 owner 的调度决策，记录在此供参考，不是硬规则。
