# Oracle Regret Compass

> 单页诊断盘点：把所有 upper-bound (perfect-foresight) oracle run 的 regret 结构汇成一张罗盘，
> 用来回答"当前策略离理想差多远、差在哪个 lever"。**纯诊断，未开新实验，只引用 in-repo 已有产出。**
> oracle 使用未来 OHLCV，永远不能当 tradable rule 或 Gate 4 指标（见 `docs/oracle_diagnostics.md`）。
> 盘点日期：2026-06-26。

## 1. 离理想有多远

固定入场 + 完美出场口径（[exp-20260623-003](../data/experiments/exp-20260623-003/exp_20260623_003_fixed_entry_exit_oracle_regret_cluster.json)，标准 3 窗口，60 笔）：

| | actual PnL | oracle PnL | capture | regret |
|---|---:|---:|---:|---:|
| 合计 | $234.9K | $300.4K | **0.78** | $65.5K |
| late_strong | $117.1K | $134.4K | 0.87 | $17.3K |
| mid_weak | $78.1K | $91.9K | 0.85 | $13.8K |
| **old_thin** | $39.7K | $74.1K | **0.54** | **$34.4K (52.5%)** |

一句话：**策略已经吃到固定入场理想出场的 ~78%，剩下的 $65.5K regret 高度集中在 old_thin 弱 tape。**

## 2. 哪些 lever 已经被 oracle 排除（不是 headroom）

> 🔧 **2026-06-27 重大更正**：本节早先版本有两处错误，已修。
> 1. **单位 bug（差 100×）**：oracle 的 `*_max_forward_return_pct` / `selection_regret_pct` 字段存的是
>    **小数**（`0.122` = 12.2%，不是 0.12%）。早先把 `avg 0.12` 读成 "0.1%"、`best 0.62` 读成 "0.6%"，
>    据此得出"候选/排序没价值"的结论 **不成立**。
> 2. **`needs_entry_skip_logging` 是接线 bug，不是测量缺口**：[oracle_no_entry_restriction.py](../quant/experiments/oracle_no_entry_restriction.py)
>    调 `build_no_trade_attribution_oracle` 时**没传** `entry_skip_oracle_data`，导致所有空仓日落到通用标签。
>    join 现成的 entry_skip_oracle 后，42 个空仓日里 **39 个（93%）当场归因**（已修，artifact 已重生成）。

来自 [oracle_no_entry_restriction_3window](../data/experiments/oracle_no_entry_restriction_3window/)（候选池/排序/无交易日 oracle，逐窗口），**修正后的真实数字**：

| lever | oracle 证据（修正单位后） | 结论 |
|---|---|---|
| 同日**排序** | selection regret 0.16–0.96%/天；top1 命中 0.50–0.53 | 排序仍近最优，**非主 headroom**（但不是 0.01%） |
| **候选池 / 无交易日** | ~42% 信号日空仓；join 后分解为 **no_shares 43% / gap_cancel+adverse_gap 31% / slot 竞争 19% / 真未知 7%** | **不是"无机会"，是三个已埋点的 policy 桶**，见下 |
| 　└ gap_cancel（31%，forward 价值最高 14–21%） | exp-20260428-021/022/023/024 + 507/508 Phase A/B 全扫过 | 重度**饱和/冻结家族** |
| 　└ no_shares（43%，最大桶） | entry_skip 里 no_shares forward 仅 3–5%，多由 risk-multiplier 置 0 | 价值最低，放开=加风险，慎 |
| 　└ slot 竞争（19%） | oracle 无法 net out 被挤出的持仓 | 真容量问题，未判定 |
| **出场机制** | exit-rule 重试（target-trim / fast-target / trailing / MFE-giveback / stop-loosening）多次 rejected；623-003 reflection 明确冻结 | lever 已试死，**冻结** |

> ⚠️ 所有 missed/forward return 都用 **未来 20 日最高点**，是 lookahead 天花板，不可达（按 capture ~0.78 折算 realized 更低）。
> `no_entry_restriction` 的 2.66–3.24× 还叠了完美出场+满仓部署，是上界的上界，**是诊断不是目标**。
>
> **扩 universe 已检验（2026-06-27 scout，3 窗口，负面）**：把 core(43) 扩到流动性 top300/top500
> liquid universe（warehouse broad OHLCV，earnings gate 统一关），core 在 **Sharpe(3/3)、maxDD(3/3)、
> survival(3/3)、合计 EV** 全胜（合计 EV 6.14 vs top300 3.41 vs top500 0.73）；survival 从 ~80% 崩到
> 10–21%。**edge 集中在精选大盘名，裸扩池摧毁风险调整收益。** 唯一 nuance：old_thin(弱 tape) 下 top300
> 裸 EV 更高(1.32 vs 0.37) 但回撤翻倍且 top500 转负——是 universe-aware ranking/risk 重调的（大）题目，
> 不是简单扩池。scout 见 scratchpad（未入库）；如要正式冻结需 reserve 实验 ID 留记录。

## 3. 剩下的唯一干净 headroom：弱 tape 里"进场即翻红"的入场

把 §1 的 regret 拆开（623-003 + [exp-20260511-102 loss taxonomy](../data/experiments/exp-20260511-102/exp_20260511_102_accepted_stack_oracle_loss_taxonomy.json)），两份独立 run 收敛到同一桶：

- **stop 出场吃掉 54.5% regret**，其中 78% 来自 old_thin；`actual_loss_with_positive_oracle` 20 笔、`day0_1` 桶 capture -3.2、`no_positive_oracle` 5 笔。
- 511-102：27 笔坏单共亏 $21K，win rate 0；归类为 **low-MFE stopout / failed-followthrough**——进场后立刻走弱，出场规则救不回来。

含义：**ideal gap ≈ "在弱 regime 里进了进场后就翻红的票"**，是 entry-quality × regime 问题，被记成了出场 regret 的假象。不是出场机制、不是排序、不是候选池。

## 4. oracle 给出的、合规的重开条件

511-102 的 `future_test_candidates` 自己写明：low-MFE stopout 桶 oracle 纯度高，但**路径-only 出场已 rejected，合规重试需要一个 ex-ante（进场前可得）的 event / news / state 标签**。

与 §2 饱和规则对齐：oracle 跑的是同一批 frozen 窗口、observed-only，**本身不产生新证据行**，不能 reshape 重开。合规推进只有两条：
1. 给 §3 的失败-followthrough 行接一个**进场前 PIT 标签**做归因（属 §2.3 豁免的 forward 埋点 / 缺失字段构建）；
2. 累积已结算 forward 行。

**in-repo 可得的 ex-ante 标签候选**（约束：只用现有数据）：
- `short_volume_ratio`（[exp-018 lead](../docs/alpha_context_pack.md)，进场日 informed-flow，已在仓）；
- PIT regime classifier（exp-019，chop-is-the-loss-axis）；
- 进场日 breadth / sector-cluster（511-102 候选 #2）。

> memory 点名的 keystone 缺失源是 PIT borrow-fee/utilization，但不在仓 —— 本盘点按"只用 in-repo"约束，不展开该方向。

## 5. 一句话给下一位代理

固定入场+完美出场口径离理想差 22%，几乎全是"弱 tape 进场即翻红"的入场质量问题（§3）。**注意 §2 已于 2026-06-27 更正**：早先"候选池/排序非 headroom"基于 100× 单位误读，已废；空仓日真实分解为 no_shares / gap_cancel(冻结) / slot 三桶。两条仍开放的推进：
> 1. 用 in-repo 进场前标签（首选 `short_volume_ratio`）**归因**（不是 gate）§3 失败行；
> 2. ~~**扩 universe**~~：2026-06-27 scout 已测（3 窗口，liquid top300/500），**负面**——core 在 Sharpe/maxDD/survival/合计 EV 全胜，裸扩池摧毁 edge（详见 §2 末）。此轴关闭；剩余的弱 tape nuance 属"universe-aware ranking/risk 重调"，是另一个大题目，不是扩池。
