# Alpha Optimization Playbook

## 文档职责

本文件是“长期 alpha 手册”，负责沉淀在多轮实验之后依然成立的内容：

- 当前系统最值得优先研究的 alpha 地图
- 各类方向的证据级别与阻塞条件
- 已证伪的思路模式
- 机制级启发
- 当前默认优先级

它不负责记录单次实验参数，也不应按日期保存过程性研究笔记。

文档分工：

- `AGENTS.md`：门控、优先级约束、会话协议、实验纪律
- `docs/experiment_log.jsonl`：单次实验记录
- `docs/daily_alpha_optimization_*.md`：某一天的增量研究快照
- 本文件：把日增量中已经稳定成立的结论上收为长期 doctrine

若本文档与 `AGENTS.md` 冲突，以 `AGENTS.md` 为准。

---

## 1. 当前长期结论

以下内容已不再是“当日观察”，而是当前默认应遵守的长期判断。

### 1.1 当前最有价值的 alpha 不是“加更多策略”，而是提纯已有 alpha

当前系统的真实 alpha 更像来自：

- 信号质量提升
- exit 质量提升
- 结构化排序
- 风险预算向高期望机会倾斜

默认不优先做：

- 大量增加新策略
- 围绕少数亏损样本加规则
- 为了好看去孤立优化 Sharpe
- 让 LLM 接管硬风控

### 1.2 breakout 和 trend 的 alpha 载体不同

- `breakout_long`
  更偏：
  - 标的质量筛选
  - bucket 内排序
  - scarce-slot competition

- `trend_long`
  更偏：
  - 持仓期管理
  - exit 质量
  - regime-aware hold management

这意味着：

- breakout 上成功的排序优化，不应默认迁移到 trend
- trend 的下一步主线应是 `exit alpha`，不是继续排列 ranking key

### 1.3 earnings_event_long 不是长期被否定，而是当前被数据阻塞

长期判断：

- PEAD 作为大类 alpha 仍然成立
- 但当前仓库里的 `earnings_event_long` 仍被 P-ERN 数据质量阻塞
- 在 `earnings_snapshot` 覆盖不足前，默认禁用 C 策略

### 1.4 LLM 更适合做 ranking / grading，不适合做硬风控

当前默认职责边界：

- 代码负责：
  - 仓位
  - 止损
  - 目标位
  - 风险预算
  - 组合约束
  - 硬过滤

- LLM 负责：
  - 新闻理解
  - 事件分类
  - 语义强弱
  - 灾难 veto
  - ranking / grading

因此，LLM 的长期主线方向是：

- 从纯 veto 走向结构化 ranking
- 但前提仍是 P-LLM 覆盖率足够，能独立归因

---

## 2. 为什么个人量化系统仍可能有 alpha

个人系统不太可能在以下地方稳定获胜：

- 超高频
- 纯速度套利
- 跟大型机构争抢同类拥挤因子执行优势

但仍可能在以下地方形成真实优势：

### 2.1 事件解释速度优势

- 个人系统覆盖标的不多、流程短、约束少
- 能更快把新闻、财报、指引、监管事件转成结构化判断
- LLM 适合做事件分类、语义强弱与风险解释

### 2.2 中短线趋势 / 突破延续

- 趋势与动量是最稳健的市场异象之一
- 个人系统的关键不是拼毫秒，而是更稳定地挑出高质量延续机会

### 2.3 组合排序与资本分配

- 很多个体系统的问题不是“没有信号”，而是“没有把钱压到最值钱的信号上”
- scarce-slot competition 往往比继续加 entry 模式更值得优化

### 2.4 Exit 质量优势

- 很多 alpha 毁在 exit，不毁在 entry
- 持仓中的 regime-aware 处理，往往比继续堆新信号更有 EV 杠杆

### 2.5 低覆盖、非标准化信息的结构化利用

- 低覆盖事件
- earnings 质量分级
- 新闻强度分级
- 多候选冲突时的语义排序

关键不是“学术上是否最纯”，而是：

- 能否被回放
- 能否被归因
- 能否在当前仓库里被稳定验证

---

## 3. 当前仓库已具备的 alpha 研究基础

当前仓库并不是从零开始，已经具备以下研究基础：

- 趋势 / 突破信号引擎
- 风险引擎与头寸 sizing
- 回测器与策略归因
- `expected_value_score`
- LLM replay / news replay / attribution
- earnings snapshot replay 基础设施
- 风险分布指标
  - `worst_trade_pct`
  - `max_consecutive_losses`
  - `tail_loss_share`

因此，当前最值得探索的不是“凭空发明很多新策略”，而是：

1. 从现有 alpha 源里减少泄漏
2. 对已有候选做更强排序
3. 让 LLM 在合适边界上创造增益
4. 让风险预算流向更高期望值机会

---

## 4. 证据级别

为了避免把“外部文献支持”和“仓库内推断”混在一起，统一使用以下证据级别：

- `Tier 1: literature-backed`
  外部文献支持较强、长期被反复研究的 alpha 大类

- `Tier 2: literature-inspired but implementation-dependent`
  有研究启发，但是否在当前仓库有效，强依赖具体实现

- `Tier 3: repo-specific hypothesis`
  主要依据当前仓库结构、回测输出、组合约束、数据条件提出的内部假设

---

## 5. 当前主线 alpha 假设

### A1. Exit alpha 泄漏可能大于 entry alpha 泄漏

- 证据级别：Tier 3
- 当前状态：有效主线
- 依据：
  - 仓库已有成熟 entry 框架
  - `regime-aware exit` 已经带来正向提升
  - exit 对收益分布的影响通常大于 entry 微调

### A2. C 策略当前差，不一定是策略差，可能是数据差

- 证据级别：Tier 1 + Tier 3
- 当前状态：blocked by P-ERN
- 依据：
  - PEAD 大类成立
  - 当前实现缺少关键历史快照，无法正确过滤低质量 earnings 信号

### A3. LLM 的最优角色更可能是 ranking，而不是只做 veto

- 证据级别：Tier 2 + Tier 3
- 当前状态：blocked by P-LLM
- 依据：
  - LLM 更擅长语义比较 than 二元硬判定
  - 但覆盖率不足前不能得出强结论

### A4. 当前系统缺的常常不是更多信号，而是更强排序

- 证据级别：Tier 3
- 当前状态：部分成立
- 已验证：
  - breakout ranking 有效
- 未成立：
  - trend ranking 不成立于当前已测 key

### A5. trend_long 的下一主线应是 in-trade regime update

- 证据级别：Tier 3
- 当前状态：next best actionable
- 依据：
  - breakout ranking 成功但 trend ranking 失败
  - trend 的 alpha 载体更像 hold management / exit quality

---

## 6. 已证伪或应暂缓的方向

以下不是“永远不可能”，但在当前证据下不应简单重试：

### 6.1 已证伪方向

- 宏观压力环境下关闭 breakout
  - 结论：无效
  - 原因：breakout weakness 更像标的质量问题，不是 broad pressure 问题

- 全局 breakout 风险折扣
  - 结论：无效
  - 原因：质量筛选后剩余 breakout 暴露是有价值的，钝化会削弱好交易

- breakout tie-breaker `above_200ma`
  - 结论：无增量信息

- `trend_long` 的 `momentum_10d_pct + pct_from_52w_high` 排序
  - 结论：无效且在一个窗口恶化

### 6.2 暂缓方向

- `LLM soft ranking`
  - 原因：P-LLM 覆盖不足

- `C strategy revival`
  - 原因：P-ERN 数据不足

- `PEAD quality scoring`
  - 原因：依赖 C 策略先完成基本数据修复

---

## 7. 机制级启发与防重复规则

本节不记录单次参数输赢，而记录“这轮实验让我们对系统结构学到了什么”。
目的不是复述 `experiment_log.jsonl`，而是防止后续代理反复提出同一种已经被证伪的思路。

### 7.1 breakout 的排序 alpha 不自动迁移到 trend

- 已证据：
  - `exp-20260419-008`：`breakout_long` bucket 内排序提升 EV
  - `exp-20260420-002`：`trend_long` 排序无效且一个窗口恶化

- 结论：
  - 不能再用“breakout ranking 有效，所以 trend ranking 也应该有效”作为默认出发点

### 7.2 trend_long 的主要 alpha 载体更可能在持仓管理

- 已证据：
  - trend ranking 失败，说明“谁排前面”不是当前主要问题

- 结论：
  - trend 方向的下一优先级应转向 `exit`
  - 默认优先测试 `in-trade regime update`

### 7.3 以后要按“alpha 载体”而不是“策略名字”来组织思考

- `breakout_long`：entry selection / quality filtering / slot allocation
- `trend_long`：hold management / exit alpha
- `earnings_event_long`：data quality + event grading
- `LLM`：semantic ranking / event interpretation

### 7.4 已证伪的思维模式

- `Symmetry Fallacy`
  - A 策略有效的优化，不代表 B 策略上的同构优化也有效

- `Bucket-Local Success -> System-Wide Template`
  - 某个 bucket 内部成功的提纯方式，不等于全系统通用模板

- `Ranking Addiction`
  - 某次 ranking 成功后，多轮都继续围绕 ranking 微调，容易进入低斜率区域

### 7.5 记录规则

以后每次实验结束后，若它改变的不是参数结论，而是“我们理解 alpha 在哪里”的结论，需要同步写入本节。

满足以下任一条件时，应追加机制级启发，而不只写实验日志：

- 一个实验证伪了一整类看似合理的迁移思路
- 一个实验明确指出某子策略的 alpha 载体发生变化判断
- 一个实验改变了未来 3 轮的默认优先级排序

---

## 8. 当前默认优先级

在 `exp-20260420-002` 之后，默认优先级为：

1. `NEW-A4 / in-trade regime update`
   原因：最符合当前机制启发，且不依赖新外部数据

2. `NEW-A2 / LLM soft ranking`
   原因：LLM 更合理的职责边界是 ranking，但受 P-LLM 阻塞

3. `NEW-A3 / C strategy revival`
   原因：PEAD 大类成立，但受 P-ERN 阻塞

4. 暂缓新的 `trend_long ranking`
   原因：已有明确失败证据；除非出现新的 slot collision 证据，否则不应重复
## 9. 2026-04-20 Addendum

- `exp-20260420-005` falsified the specific idea "carry the same entry-day regime map forward into open trend targets".
- The result was a strict null effect across the primary window and the measurable secondary window when run as a paired same-data comparison against the accepted A+B stack (`EV 0.7531 -> 0.7531` in the primary window).
- Mechanism implication:
  The current `regime-aware exit` already captures the usable signal from that regime map at entry. Reapplying the same map later in the trade does not add edge.
- Priority implication:
  `NEW-A4 / in-trade regime update` should no longer be treated as the best unblocked alpha candidate unless a genuinely different in-trade mechanism is proposed.
- `exp-20260420-007` tested a different breakout allocation idea: rerank only enriched `breakout_long` signals by `trade_quality_score`.
- The result was a one-trade improvement in the full primary window (`EV 0.7531 -> 0.9131`) but a strict null across five non-overlapping comparison windows.
- Mechanism implication:
  the current breakout ranking stack (`pct_from_52w_high` filter + breakout-local ranking) is already close to local saturation. Post-enrichment TQS reranking does not currently affect enough real slot collisions to count as stable edge.
- `exp-20260420-008` tested a different trend exit idea: widen only `trend_long` targets beyond the shared `regime-aware exit` profile.
- The result was a positive primary-window screen (`EV 0.7531 -> 0.8255` at `+0.5 ATR`) but mixed validation: one large comparison window and one key subwindow regressed materially.
- Mechanism implication:
  trend exit alpha is not unlocked by a blanket "just give trend more room" rule. Wider targets help in some tapes and hurt in others, so future trend-exit work must be conditional rather than another global target-width permutation.
- Updated practical ordering:
  1. `NEW-A2 / LLM soft ranking` remains high-value but blocked by P-LLM coverage.
  2. `NEW-A3 / C strategy revival` remains high-value but blocked by P-ERN data quality.
  3. Any future `trend_long` exit work must be selective or context-conditioned, not another blanket widening or reuse of the current regime map.
  4. Any future breakout allocation work must first show repeated slot-collision evidence; do not keep permuting ranking keys inside the already-accepted breakout stack by default.

- `exp-20260420-012` tested a genuinely different trend exit idea: activate a BEAR-only profit lock for already-profitable `trend_long` positions.
- The result was a strict null across a 3x3 primary-window screen (`EV 0.7531 -> 0.7531` for every tested trigger/offset pair).
- Mechanism implication:
  even a selective post-entry rule tied only to market-regime deterioration is not enough. Trend exit alpha is not currently unlocked by another index-state-triggered target/stop mutation; future work needs richer trade-specific hold-quality context.
- Priority implication:
  the practical ordering does not change. `LLM soft ranking` and `C strategy revival` remain the highest-value directions once their data blockers actually move; avoid continuing to mine small `trend_long` exit permutations by default.

- `exp-20260420-014` tested a more selective variant of the rejected trend-widening idea: widen only `trend_long` targets whose entry had perfect confidence (`confidence_score == 1.0`).
- The result still failed stability. The primary window improved (`EV 0.7531 -> 0.8255` at `+0.5 ATR`), but the large ripping-bull comparison window and the key continuation subwindow both regressed materially.
- Mechanism implication:
  static entry-quality metadata is not enough to unlock `trend_long` exit alpha. A better entry does not automatically imply that the position should be given more room after entry; the missing signal is still something about in-trade hold quality, not another target-width rule keyed off entry-time attributes.
- Priority implication:
  downgrade "entry-conditioned trend target widening" alongside blanket widening and regime-only post-entry mutations. The remaining credible trend-exit direction, if revisited at all, must use richer in-trade context rather than another static selector layered on the same target model.
