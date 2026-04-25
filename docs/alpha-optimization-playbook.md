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

### 1.3 earnings_event_long 不是长期被否定，但也不再是“只差补数据”

长期判断：

- PEAD 作为大类 alpha 仍然成立
- `earnings_snapshot` 覆盖已经足够让仓库对 C 策略做真实历史检验
- 当前问题已从“纯数据阻塞”转成“机制仍然不够好”：
  repaired-data 之后，单字段 gate、小型 checklist、共享质量分数 gate、
  standalone-day gate 都只能减轻拖累，仍不能稳定让 `A+B+C` 跑赢 accepted `A+B`
- 因此，`C strategy revival` 现在默认需要“更丰富的事件分级或更强的边际槽位价值机制”，
  而不是继续把“再补一点数据”当成主线

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

### A2. C 策略当前差，已经不能再默认归因于数据差

- 证据级别：Tier 1 + Tier 3
- 当前状态：needs a new mechanism
- 依据：
- PEAD 大类成立
- repaired-data 之后，`earnings_event_long` 已经通过多轮真实机制检验
- 目前被证伪的是“低复杂度复活路线”：
  单字段 surprise gate、技术 gate、小型复合 checklist、
  standalone-day gate、共享 `trade_quality_score` gate 都不足以稳定胜过 accepted `A+B`
- 因此，后续若重启 C，不应再默认从 scalar threshold / checklist 家族继续扫

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
  - 原因：仍被 candidate-level replay coverage 阻塞
  - 当前真正 go/no-go 指标不是日覆盖率，而是
    `candidate_day_coverage_fraction` / `candidate_signal_coverage_fraction`
  - 截至 `exp-20260422-003`，固定主窗口仍只有 `3/31` candidate days、
    `3/44` candidate signals 被覆盖，缺口是明确的 missing-date backlog，
    不是抽象的“样本偏少”

- `C strategy revival`
  - 原因：不再是数据不足，而是缺少 genuinely richer mechanism
  - repaired-data 已经把 C 从“测不准”推进到“能测但当前机制不够强”
  - 默认不要再做另一轮 scalar gate / checklist / standalone-day 变体

- `PEAD quality scoring`
  - 原因：简单 quality scoring 家族已经基本被证伪
  - 若重启，应从 richer event grading 或 marginal-slot evidence 出发

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

1. `NEW-A2 / LLM soft ranking`
   原因：仍是当前最高上限的 alpha 方向，且已明确知道阻断项是 candidate-level replay coverage，
   不是方向不清楚

2. `NEW-A3 / C strategy revival`
   原因：PEAD 大类仍成立，但仓库里的低复杂度复活路线已经基本证伪；
   只有出现 genuinely richer event-grading / marginal-slot mechanism 时才值得重启

3. 仅在出现 genuinely new mechanism 时，才重开 unblocked A+B alpha work
   原因：当前 accepted A+B stack 周围的 ranking / scalar / coarse cohort / fast-confirm
   continuation 分支已经高度饱和，不应默认再做另一轮微调

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

- `exp-20260420-016` tested a different unblocked allocation idea: change the whole-system slot count (`MAX_POSITIONS`) instead of another entry/exit/ranking tweak.
- The result was unstable across three non-overlapping windows. `MAX_POSITIONS=5` stayed best in the primary slow-melt window, `8` won only in the ripping-bull comparison window, and `3` was merely less bad in the older weak window.
- Mechanism implication:
  static global slot-count changes are too blunt. The useful signal, if any, is not "always concentrate more" or "always diversify more"; it is likely conditional on regime or on which strategy is consuming the marginal slot.
- Priority implication:
  do not keep permuting global portfolio-slot counts by default. If allocation alpha is revisited, it should be strategy-specific or context-conditioned, not another whole-system `MAX_POSITIONS` dial.

- `exp-20260420-017` tested the simplest strategy-specific allocation tilt: when slots are scarce, prefer `breakout_long` candidates ahead of `trend_long`.
- The result failed immediately in the primary window (`EV 0.5981 -> 0.5226`) even before multi-window validation.
- Mechanism implication:
  higher average strategy attribution does not mean higher marginal slot value. The breakout-priority tilt removed three trend trades (`13 -> 10`) but did not improve breakout quality; instead breakout profit factor degraded materially (`4.607 -> 2.544`) as lower-quality breakout candidates consumed the extra slots.
- Priority implication:
  do not retry naive strategy-priority allocation rules driven only by average `by_strategy` performance. Any future allocation-alpha work now needs explicit same-day collision evidence and a richer marginal-value signal than "breakout has the better average PF."

- `exp-20260421-001` tested the first trade-specific hold-quality exit idea after the regime-only and entry-conditioned trend-exit failures: if an already-profitable `trend_long` closed in a weak state (`trend_score <= 0.4` and `momentum_10d_pct <= 0`), raise the next-session stop to breakeven.
- The best screen (`0.5 ATR` trigger) improved only the ripping-bull comparison window, was a strict null in the primary window, and regressed the older weak window (`EV 0.0036 -> 0.0029`, win rate `27.8% -> 22.2%`).
- Mechanism implication:
  trade-specific hold-quality context is still the right class of idea, but a one-day weak-close snapshot plus a breakeven lock is too blunt. It protects some bull-window giveback but worsens weaker tapes and does not create stable edge.
- Priority implication:
  downgrade "weak close -> breakeven lock" alongside regime-only profit locks and entry-conditioned target widening. If `trend_long` exit work is revisited, it needs richer hold-quality evidence than a single end-of-day deterioration flag.

- `exp-20260421-003` added a real historical P-ERN backfill path and wrote snapshot coverage across the current primary window (`2025-10-23 -> 2026-04-20`).
- `exp-20260421-004` then re-ran `earnings_event_long` with the repaired archive against the same A+B baseline across three non-overlapping windows.
- Result summary:
  - primary slow-melt window: `A+B EV 0.5329 > A+B+C EV 0.4498`
  - ripping-bull window: `A+B+C EV 0.1417 > A+B EV 0.0193`
  - older weak window: `A+B EV 0.0030 > A+B+C EV 0.0802`, but `A+B+C` got there via both negative return and negative sharpe (`return -9.66%`, `sharpe_daily -0.83`), so it still failed the guardrail test materially
- Mechanism implication:
  fixing snapshot coverage was necessary to measure C credibly, but it was not sufficient to revive C. The old thesis "once P-ERN data is present, C should naturally recover" is now falsified. Whatever alpha exists in PEAD for this repo will require additional event grading or slot interaction logic, not just restored earnings fields.
- Priority implication:
  downgrade `C strategy revival` from "best blocked alpha" to "needs a new mechanism." The highest-value direction is now `LLM soft ranking`, but it remains blocked by replay coverage. Do not spend the next round merely extending earnings snapshot coverage or re-enabling C by default.

- `exp-20260421-005` tested whether the latest `--replay-llm` uplift is already large enough to treat `LLM soft ranking` as an active alpha track rather than a still-blocked one.
- Result summary:
  - primary window (`2025-10-23 -> 2026-04-20`): `EV 0.3572 -> 0.3775`, but replay covered only `5/122` trading days and only `3` presented signals
  - covered micro window (`2026-04-10 -> 2026-04-20`): the same `3` presented signals became `1` trade after `2` vetoes; sample remains too small for inference
  - older comparison window (`2025-04-23 -> 2025-10-22`): `0` covered days, so no non-overlapping validation window exists yet
- Mechanism implication:
  the current LLM archive is large enough to produce tempting one-window deltas, but still far too small to identify stable edge. A single avoided loser in a covered tail can move the headline EV without proving that LLM ranking or veto logic generalizes.
- Priority implication:
  keep `LLM soft ranking` as the highest-value conceptual direction, but explicitly classify it as measurement-blocked until replay coverage spans multiple non-overlapping windows. Do not treat the current `EV` uplift as permission to resume LLM-boundary optimization or to claim that LLM alpha is already unlocked.

- `exp-20260421-006` tested the simplest repaired-data `C strategy revival` mechanism: require `positive_surprise_history` to be explicitly positive before `earnings_event_long` can fire.
- Result summary:
  - primary window (`2025-10-23 -> 2026-04-20`): `A+B EV 0.5329 > gated A+B+C EV 0.3977`
  - ripping-bull window (`2025-04-22 -> 2025-10-21`): strict null because gated `C` produced `0` trades
  - older weak window (`2024-10-01 -> 2025-04-30`): strict null because gated `C` produced `0` trades
- Mechanism implication:
  sign-only surprise history is too blunt to count as usable event grading. It removes many C opportunities, but the subset it leaves is still poor in the primary window, so "historical beats exist" is not enough to identify profitable PEAD candidates in this repo.
- Priority implication:
  downgrade any follow-up idea that just hard-gates C on boolean surprise sign. If `C strategy revival` is revisited, it now needs richer event grading or slot interaction logic, not another binary surprise-history selector.

- `exp-20260421-007` tested the simplest technical-context follow-up for `C strategy revival`: require `earnings_event_long` setups to already be above the 200-day moving average.
- Result summary:
  - primary window (`2025-10-23 -> 2026-04-20`): `A+B EV 0.5329 > above200-gated A+B+C EV 0.4977`
  - ripping-bull window (`2025-04-23 -> 2025-10-22`): `above200-gated A+B+C EV 0.1369 > A+B EV 0.0180`
  - older weak window (`2024-10-02 -> 2025-04-22`): `above200-gated A+B+C` still failed hard guardrails (`return -9.64%`, `sharpe_daily -0.84`)
- Mechanism implication:
  a one-dimensional technical trend gate improves C only in strong tapes. It does not rescue the mechanism in mixed or weak tapes, so "C just needs stronger trend context" is now falsified as a standalone explanation.
- Priority implication:
  do not keep trying single-field technical gates for C by default. Any future C work now needs either multi-field event scoring or explicit slot-interaction evidence, not just another trend-context selector.

- `exp-20260421-008` tested the obvious surprise-magnitude follow-up after the boolean-sign failure: require `avg_historical_surprise_pct >= 4.0` for `earnings_event_long`.
- Result summary:
  - primary window (`2025-10-23 -> 2026-04-20`): `A+B EV 0.5329 > surprise-gated A+B+C EV 0.4763`
  - ripping-bull and older weak windows: strict null because the gate removed all C trades
- Mechanism implication:
  replacing surprise sign with surprise magnitude is still too weak when used as a single-field gate. It makes the surviving C cohort slightly less bad in the primary window, but it does not create broad enough opportunity flow or stable edge across windows.
- Priority implication:
  downgrade another whole class of "simple C revival" ideas: not just sign-only surprise gates, but one-dimensional surprise-magnitude thresholds too. If C is revisited, the mechanism now needs a genuinely richer event score or slot-allocation interaction, not another scalar cutoff.

- `exp-20260421-009` tested the first pure sizing-alpha idea after the ranking and trend-exit dead ends: keep the current A+B entries intact, but cut risk only for signals whose `confidence_score < 1.0`.
- Result summary:
  - primary slow-melt window: reducing sub-1.0 risk helped materially (`EV 0.5329 -> 0.6197` at factor `0.25`)
  - ripping-bull window: the same haircut hurt materially (`EV 0.0180 -> 0.0043` at factor `0.25`)
  - older weak window: small improvement (`EV 0.0030 -> 0.0059` at factor `0.25`)
  - attribution check: sub-1.0 trades lost money in the primary and weak windows, but added positive dollars in the ripping-bull window
- Mechanism implication:
  static confidence metadata does contain information, but not in a regime-invariant way. A global low-confidence de-risking rule is too blunt: in slower or weaker tapes it suppresses bad A+B trades, while in ripping bull tapes it cuts exposure to still-valuable convexity.
- Priority implication:
  downgrade another class of static allocation ideas alongside global slot-count changes and naive strategy tilts. If allocation alpha is revisited, it should now be explicitly context-conditioned (regime or strategy specific), not another whole-system confidence haircut.

- `exp-20260421-010` tested the next allocation-alpha hypothesis after the confidence-sizing failure: keep the current A+B entries intact, but de-risk only lower-`trade_quality_score` signals, since `confidence_score` is now largely saturated at `1.0` on the accepted stack while TQS still carries cross-sectional quality variation.
- Result summary:
  - primary slow-melt window: `EV 0.5329 -> 0.5910`, `sharpe_daily 2.51 -> 2.73`, `max_drawdown 4.47% -> 2.75%`
  - ripping-bull window: `EV 0.0180 -> 0.0304`, `sharpe_daily 0.48 -> 0.61`, `max_drawdown 8.69% -> 8.28%`
  - older weak window: strict null (`EV 0.0030 -> 0.0030`)
- Mechanism implication:
  the earlier allocation dead end was the wrong proxy, not the whole alpha class. Once the current entry stack saturates raw confidence, `trade_quality_score` still preserves enough marginal information to improve capital allocation without changing trade count.
- Priority implication:
  upgrade TQS-conditioned sizing from hypothesis to part of the accepted A+B stack. If allocation alpha is revisited again, start from richer marginal-quality fields like TQS or similarly structured context, not from `confidence_score < 1.0`, global slot-count dials, or naive strategy-priority tilts.

- `exp-20260421-011` tested whether the accepted TQS sizing rule still had easy follow-on alpha in the simplest place: the scalar trigger itself. It swept `LOW_TQS_RISK_THRESHOLD` across `0.80, 0.825, 0.85, 0.875, 0.90` while holding the `0.25x` risk multiplier fixed.
- Result summary:
  - `0.85` stayed best in the primary slow-melt window (`EV 0.5910`), ahead of both looser thresholds (`0.5353` at `0.80/0.825`) and tighter thresholds (`0.5010` at `0.875`, `0.4068` at `0.90`)
  - tighter thresholds helped only the ripping-bull comparison window (`EV 0.0304 -> 0.0369 -> 0.0405`) by cutting more breakout convexity
  - the older weak window regressed when the threshold was tightened (`EV 0.0030 -> 0.0008`) and showed no benefit when it was loosened
- Mechanism implication:
  the accepted TQS sizing rule is real, but the easy scalar-tuning frontier is already largely exhausted. In the current stack, almost every de-risked trade is a low-TQS `breakout_long`, so moving the threshold mainly reclassifies the same breakout cohort rather than unlocking a new source of edge.
- Priority implication:
  do not keep permuting `LOW_TQS_RISK_THRESHOLD` around `0.85` by default. If allocation alpha is revisited, the next credible step must add a new conditioning variable or a richer continuous sizing map, not another nearby cutoff on the same TQS signal.

- `exp-20260421-012` tested the most obvious new conditioning variable after the failed threshold and continuous-map ideas: activate the accepted low-TQS haircut only on same-day candidate-collision sessions instead of all days.
- Result summary:
  - `candidate_count > 1` materially regressed the primary window (`EV 0.5910 -> 0.5058`) and fully gave back the ripping-bull improvement (`EV 0.0304 -> 0.0180`)
  - `candidate_count > 2` merely reverted the primary window to the old pre-TQS baseline (`EV 0.5910 -> 0.5329`) and also lost the bull-window uplift
  - the weak window stayed a strict null in every variant (`EV 0.0030 -> 0.0030`)
- Mechanism implication:
  the accepted TQS sizing edge is not just slot-collision triage. Low-TQS trades are weak enough that de-risking them on all days still matters; restricting the haircut to explicit same-day competition removes too much real edge.
- Priority implication:
  downgrade the whole class of "only fire the TQS haircut on collision days" follow-ups. Future allocation work should not narrow the accepted TQS rule's activation scope unless new evidence shows lone low-TQS trades are additive; the next credible direction still needs a genuinely new conditioning variable or a richer marginal-value signal.

- `exp-20260421-013` tested another post-TQS scalar allocation follow-up: add a second haircut for explicit `gap_vulnerability_pct` exposure.
- Result summary:
  - even the best screen (`gap_vulnerability_pct < 0.025` with `0.5x` risk) regressed the primary window (`EV 0.5910 -> 0.5797`) and the ripping-bull window (`EV 0.0304 -> 0.0287`)
  - wider coverage (`< 0.03`) reduced drawdown a bit more, but only by sacrificing too much return and EV
- Mechanism implication:
  tight-stop gap risk is a useful warning field, but it is not a stable standalone sizing signal once the accepted TQS haircut is already in place. The remaining affected cohort still contains enough good convexity that a second scalar haircut removes more upside than downside.
- Priority implication:
  downgrade the whole class of "add one more pre-entry scalar risk haircut" follow-ups on top of TQS. `gap_vulnerability_pct` should remain diagnostic context unless a genuinely richer conditioning source arrives.

- `exp-20260421-014` tested the opposite allocation tail: boost only the highest-TQS `trend_long` entries.
- Result summary:
  - modest bonuses (`1.25x`) improved only the ripping-bull comparison window (`EV 0.0304 -> 0.0354`) while hurting the primary window (`EV 0.5910 -> 0.5692`) and the weak window (`EV 0.0030 -> 0.0014`)
  - larger bonuses (`1.5x`) amplified the same regime split instead of fixing it
- Mechanism implication:
  the current stack does not have an easy "just size the best trend entries bigger" leak left in pure entry sizing. Trend convexity concentration is regime-dependent and becomes unstable as soon as the tape weakens.
- Priority implication:
  downgrade another class of unblocked A+B allocation ideas: static high-TQS `trend_long` bonuses. If trend alpha is revisited, it needs richer hold-quality or semantic context, not another entry-sizing concentration rule.

- `exp-20260421-015` tested the most obvious context-conditioned follow-up after the static allocation failures: keep the accepted low-TQS haircut, but relax it only in entry-day contexts that the shared `regime_exit` map already classifies as more risk-on.
- Result summary:
  - binary gating by implied `target_mult <= 3.5` or `<= 3.75` fully reverted to the pre-TQS baseline (`EV 0.5910 -> 0.5329` primary, `0.0304 -> 0.0180` ripping-bull)
  - partial relaxation (`0.5x` instead of `0.25x` in risk-on) still regressed both the primary and ripping-bull windows (`EV 0.5910 -> 0.5806`, `0.0304 -> 0.0227`)
  - audit: all 11 low-TQS entries across the three windows already sat inside the same `risk_on` target-width band (`implied_target_mult` 4.479-4.5088)
- Mechanism implication:
  the current shared regime map is too saturated to drive the next sizing-alpha branch. It helps exits, but it does not separate the low-TQS cohort, because the de-risked trades already occur almost entirely in the strongest entry-day market bucket.
- Priority implication:
  downgrade the whole class of "make TQS sizing regime-aware via the current market-level regime map" follow-ups. If allocation alpha is revisited, it now needs a genuinely new context source that overlaps the low-TQS cohort, not another repackaging of `regime_exit` or index-state strength.

- `exp-20260421-016` tested the first genuinely new low-TQS conditioning source after the failed regime and scalar follow-ups: keep the accepted haircut everywhere except the defensive `Commodities` breakout pocket.
- Result summary:
  - primary slow-melt window improved materially (`EV 0.5910 -> 0.6426`, `return 21.65% -> 23.20%`, `PnL +$1.54k`) while trade count and win rate stayed unchanged
  - ripping-bull and older weak windows were strict nulls because neither window contained a profitable low-TQS commodity cohort to rescale
  - cohort audit: in the primary window, the only profitable low-TQS trades were `IAU` and `GLD` breakouts, while low-TQS `Consumer Discretionary` and `Financials` breakouts remained losers
- Mechanism implication:
  the accepted TQS sizing rule was not wrong, but it was over-grouping two different low-TQS populations. Commodity breakouts can carry lower raw TQS because they often have milder momentum and volume expansion than cyclicals, yet still produce valid defensive continuation edge.
- Priority implication:
  upgrade the commodity exemption into the accepted A+B stack. Future low-TQS sizing work should look for similarly well-separated cohort structure, not revert to another whole-system threshold tweak or another regime-proxy relaxation.

- `exp-20260421-017` tested the next cohort split after the commodity exemption: keep the accepted commodity pocket at full size, but stop allocating any risk at all to the remaining low-TQS non-commodity `breakout_long` cohort.
- Result summary:
  - primary slow-melt window: `EV 0.6426 -> 0.8335`, `sharpe_daily 2.77 -> 3.45`, `return 23.20% -> 24.16%`, `trade_count 28 -> 25`
  - ripping-bull window: `EV 0.0304 -> 0.0414`, `sharpe_daily 0.61 -> 0.70`, `return 4.99% -> 5.91%`
  - older weak window: strict null (`EV 0.0030 -> 0.0030`)
- Mechanism implication:
  after separating out the defensive commodity pocket, the remaining low-TQS breakout cohort is not merely "lower size" quality; it is negative enough that even the accepted `0.25x` haircut still leaves avoidable drag. The next stable edge was not a new scalar, regime proxy, or slot heuristic, but a cleaner cohort split inside the existing breakout-quality bucket.
- Priority implication:
  upgrade "low-TQS non-commodity breakout = zero risk" into the accepted A+B stack. Future allocation work should start from similarly sharp cohort separation evidence, not from re-opening the old `0.25x` debate for the whole low-TQS population.

- `exp-20260421-018` tested the first post-breakout cohort split inside the current repo-state `trend_long` book: keep the accepted breakout sizing stack unchanged, but allocate zero risk to `trend_long` signals in `Industrials`.
- Result summary:
  - primary slow-melt window: `EV 0.5027 -> 0.5382`, `sharpe_daily 3.09 -> 3.28`, `return 16.27% -> 16.41%`
  - ripping-bull window: `EV 0.0944 -> 0.1489`, `sharpe_daily 1.09 -> 1.29`, `return 8.66% -> 11.54%`
  - older weak window: `EV 0.0013 -> 0.0108`, `sharpe_daily -0.08 -> 0.38`, `return -1.61% -> 2.84%`, `max_drawdown 9.84% -> 8.21%`
- Mechanism implication:
  current trend weakness is not uniform. In the live repo state, `trend_long` Industrials are the repeated drag cohort, so the next useful allocation edge came from strategy+sector cohort separation inside trend rather than another exit permutation or another whole-system sizing dial.
- Priority implication:
  upgrade "zero-risk `trend_long` Industrials" into the accepted A+B stack for the current repo state. Future trend allocation work should start from similarly repeated cohort evidence, not from another blanket trend haircut or another exit-width tweak.

- `exp-20260421-019` tested the obvious continuation after the accepted `trend_long` Industrials split: check whether one more coarse strategy+sector bucket could be zeroed cleanly.
- Result summary:
  - `trend_long` Technology improved only the ripping-bull window (`EV 0.0841 -> 0.1468`) but regressed the primary window (`0.8299 -> 0.7434`) and flipped the weak window slightly negative (`0.0084 -> -0.0001`)
  - `trend_long` Healthcare improved only the primary window (`0.8299 -> 0.8563`), left the bull window unchanged, and slightly regressed the weak window (`0.0084 -> 0.0076`)
  - `breakout_long` Financials improved only the bull window (`0.0841 -> 0.1081`) while regressing the primary (`0.8299 -> 0.6953`) and weak (`0.0084 -> 0.0015`) windows
- Mechanism implication:
  after removing `trend_long` Industrials, the remaining A+B weakness is not another clean sector-only drag bucket. The next residual losses are regime- or sample-dependent; coarse strategy+sector suppressions now overfit one window while damaging another.
- Priority implication:
  downgrade further "zero one more strategy+sector bucket" sweeps. If allocation alpha is revisited again, it needs a richer conditioning source than sector alone. In practical priority terms, the easy unblocked A+B allocation branch is close to saturation, so `LLM soft ranking` remains the highest-upside direction once replay coverage is large enough to make that experiment credible.

- `exp-20260421-020` tested the first narrower post-sector split inside the current `trend_long` drag pocket: keep the accepted stack intact, but de-risk only `trend_long` Technology entries whose `gap_vulnerability_pct` sits in the moderate 4%-6% band.
- Result summary:
  - primary slow-melt window: strict null (`EV 0.8299 -> 0.8299`), because no qualifying cohort appeared
  - ripping-bull window: improved materially (`EV 0.0841 -> 0.1255`, `sharpe_daily 0.89 -> 1.21`, `max_drawdown 8.87% -> 5.11%`)
  - older weak window: improved materially (`EV 0.0084 -> 0.0257`, `sharpe_daily 0.32 -> 0.51`, `return 2.63% -> 5.04%`)
- Mechanism implication:
  the residual trend leak was not "Technology is bad" and not "high gap vulnerability is bad" in isolation. The useful separation came from a narrower risk-shape cohort: moderate-gap tech trends repeatedly underperformed, while wider-gap and sub-4% tech trends were not the same drag.
- Priority implication:
  upgrade "moderate-gap `trend_long` Technology -> 0.25x risk" into the accepted A+B stack for the current repo state. Future allocation work should start from similarly narrow intersections of strategy, sector, and risk-shape context, not from reopening sector-only zero-risk sweeps or global gap-vulnerability haircuts.

Mechanism card:
- Rule target: `strategy == trend_long` AND `sector == Technology` AND `0.04 <= gap_vulnerability_pct < 0.06`
- Rule action: keep the signal live, but scale risk from `1.0x` to `0.25x`
- Layer changed: sizing only; no entry veto, no ranking rewrite, no exit rewrite
- Financial logic: this cohort behaved like a repeated overnight-fragility pocket. It was too fragile for full-size exposure, but not weak enough to justify a full ban.
- Why it is not a black box: the cohort is explicit, the action is explicit, and every affected trade is replayable from logged signal fields
- What it does not mean: it does not prove "Technology is bad", and it does not prove the cohort has zero alpha
- Follow-up constraint: `exp-20260421-024` already showed that tightening the same cohort from `0.25x` to `0.0x` made the comparison windows worse, so do not keep pushing this multiplier toward zero by default

- `exp-20260421-021` re-tested the most tempting coarse post-020 retry under the new accepted repo state: zero only `trend_long` Healthcare.
- Result summary:
  - primary slow-melt window improved (`EV 0.8299 -> 0.8563`)
  - ripping-bull window stayed a strict null because no Healthcare trend cohort appeared
  - older weak window regressed slightly on the north-star metric (`EV 0.0084 -> 0.0076`) even though drawdown improved
- Mechanism implication:
  even after the accepted moderate-gap tech haircut reshaped the trend book, the next residual leak still does not collapse into another clean sector-only trend bucket. A current-state loser audit is not enough on its own; slot interaction and cohort scarcity still make coarse sector suppressions unstable.
- Priority implication:
  strengthen the existing ban on reopening "one more sector bucket" ideas by default. If trend allocation alpha is revisited again, it must add a genuinely richer conditioning source inside the residual cohort, not another strategy+sector zero-risk retry.

- `exp-20260421-022` tested the first genuinely repaired-data composite `C strategy revival` mechanism after the one-dimensional surprise and technical gates failed: fire `earnings_event_long` only when snapshot coverage exists and the setup also clears a small composite quality bar (`avg_historical_surprise_pct >= 4`, `atr_pct <= 3.5%`, `pct_from_52w_high >= -8%`, `trend_score >= 0.6`).
- Result summary:
  - full primary window: C drag improved materially versus ungated C, but `A+B+C` still trailed `A+B` (`EV 0.8299 -> 0.7019`)
  - older bull and weak comparison windows: strict null because they predate the repaired snapshot archive, so the gate suppressed C entirely
  - repaired-snapshot subwindows: early and late subwindows improved slightly (`EV 0.1734 -> 0.1757`, `0.1014 -> 0.1367`), but the middle subwindow regressed materially (`0.2954 -> 0.2011`)
- Mechanism implication:
  repaired P-ERN data has moved `C strategy revival` out of the pure "data blocker" bucket and into the real mechanism-testing bucket. The first composite quality gate reduces obviously bad C trades, but it still does not create a stable PEAD edge strong enough to beat the accepted A+B stack.
- Priority implication:
  downgrade another whole class of low-complexity C-revival ideas: not just single-field surprise/technical gates, but also small repaired-data composite cutoffs. If C is revisited again, it now needs richer event grading or explicit slot-interaction logic, not another scalar checklist built from the same snapshot fields.

- `exp-20260421-023` tested the most credible remaining scalar A+B event-risk knob that had not yet been logged: the shared `days_to_earnings` entry guard for `trend_long` and `breakout_long`.
- Result summary:
  - `<=2` and `<=4` were strict nulls versus the accepted-stack baseline across the primary, bull, and weak windows (`EV 0.8299 / 0.1255 / 0.0257` unchanged)
  - `<=5` removed one additional bull-window trade and regressed that window (`EV 0.1255 -> 0.1185`, `sharpe_daily 1.21 -> 1.18`)
- Mechanism implication:
  the A+B earnings-proximity axis is now locally saturated. The current `dte <= 3` rejection rule is not the missing lever; nearby threshold permutations do not unlock new edge, which means any future earnings-related A+B work needs richer event context than another scalar cutoff.
- Priority implication:
  downgrade another tempting micro-tuning branch alongside nearby TQS and sector retries. The practical ordering does not change: `LLM soft ranking` remains the highest-upside direction once replay coverage is credible, while `C strategy revival` needs richer event grading or slot-interaction logic rather than another checklist or threshold.

- `exp-20260421-024` tested the most tempting direct continuation of the accepted moderate-gap trend-tech sizing rule: keep the exact same cohort (`trend_long` + `Technology` + `0.04 <= gap_vulnerability_pct < 0.06`) but tighten it from `0.25x` risk to `0.0x`.
- Result summary:
  - primary slow-melt window: strict null (`EV 0.8299 -> 0.8299`) because the current primary tape had no qualifying surviving trades
  - ripping-bull window: regressed materially (`EV 0.1255 -> 0.0861`, `sharpe_daily 1.21 -> 1.06`, `return 10.37% -> 8.12%`)
  - older weak window: regressed materially (`EV 0.0257 -> 0.0130`, `sharpe_daily 0.51 -> 0.38`, `return 5.04% -> 3.41%`)
- Mechanism implication:
  the accepted `0.25x` moderate-gap tech haircut is not an obviously under-tightened leak. Even when the executed cohort audit shows only losers, removing that cohort entirely can still worsen the portfolio through replacement-flow and slot-allocation effects. Current residual A+B leaks are not recoverable by simply turning already-accepted cohort multipliers further toward zero.
- Priority implication:
  downgrade another seductive continuation pattern: "same accepted cohort, just tighten the multiplier again." If allocation alpha is revisited, it now needs a genuinely new interaction source rather than more intensity tuning on the current accepted cohort rules. This strengthens the practical conclusion that the unblocked A+B allocation branch is near saturation, so `LLM soft ranking` remains the highest-upside direction once replay coverage becomes credible.

- `exp-20260421-025` tested the first repaired-data `C strategy revival` idea that was explicitly about marginal slot interaction rather than event checklists: allow `earnings_event_long` only on days with no same-day `trend_long` or `breakout_long` candidates.
- Result summary:
  - primary slow-melt window: regressed materially (`EV 0.8299 -> 0.6443`, `sharpe_daily 3.49 -> 2.91`)
  - ripping-bull window: improved (`EV 0.1255 -> 0.1574`, `sharpe_daily 1.21 -> 1.35`)
  - older weak window: regressed materially (`EV 0.0257 -> 0.0091`, `sharpe_daily 0.51 -> 0.33`)
- Mechanism implication:
  repaired-data C drag is not just "C steals slots from A+B on crowded days." Even when C is isolated to standalone days, it still fails the north-star metric in the primary and weak tapes. That means the missing edge is not merely slot separation; C still needs better event quality discrimination or a richer marginal-value test than "no A/B candidate today."
- Priority implication:
  downgrade the whole class of standalone-day or "only when no same-day A/B exists" C gates. If `C strategy revival` is revisited again, it must combine richer event grading with explicit marginal-slot evidence, not merely isolate C from A+B competition. This further strengthens the practical ordering: `LLM soft ranking` remains the highest-upside direction once replay coverage is credible, while repaired-data C remains secondary until a stronger mechanism appears.

- `exp-20260421-029` tested the first explicit `breakout_long` fast-confirm exit idea after the repo had already saturated the easier breakout quality / ranking branch: if a breakout is still below entry after 2 trading days and has never reached even `0.5R` best excursion, force an early close.
- Result summary:
  - first validation pass looked mildly constructive (`primary EV 0.8299 -> 0.8321`, `bull EV 0.1255 -> 0.1798`, `weak EV 0.0144 -> 0.0163`)
  - immediate rerun of the exact same config flipped the primary verdict negative (`primary EV 0.8299 -> 0.7241`) while the comparison windows stayed positive
  - the difference was not mechanism drift but data-path drift: different yfinance rate-limit failures removed different tickers across reruns (`NFLX` / `JPM` first, `COIN` later)
- Mechanism implication:
  breakout early follow-through is still a plausible alpha carrier, and a fast-confirm exit is the right mechanism class to test next rather than another broad filter or another coarse allocation dial. But a small edge in this branch is not promotable unless the same-data rerun is deterministic.
- Priority implication:
  keep `breakout fast-confirm exit` in the "plausible but unaccepted" bucket. Do not promote it from small unstable deltas, and do not revisit it on the current live-download path without pinned local OHLCV snapshots or another deterministic cache. This is now a doctrine-level warning: when a mechanism's sign flips across immediate reruns because vendor downloads changed, the right conclusion is "measurement instability", not "new alpha" and not "mechanism falsified".

- `exp-20260422-001` converted that doctrine warning into a usable measurement tool: `quant/backtester.py` can now save and reload OHLCV snapshots for a named window.
- Result summary:
  - live primary-window save run (`2025-10-23 -> 2026-04-21`, `--regime-aware-exit`) produced `EV 0.8470`, `sharpe_daily 3.51`, `return 24.13%`, `trade_count 23`
  - replaying the same window from `data/ohlcv_snapshot_20251023_20260421.json` reproduced those metrics exactly
  - targeted regression tests now prove the snapshot path round-trips OHLCV and bypasses `yf.download(...)`
- Mechanism implication:
  for small-delta A+B work, OHLCV download drift is no longer an acceptable excuse. The repository now has a fixed-price replay path, so future fast-confirm / post-entry / allocation experiments can be judged on identical price history instead of vendor noise.
- Priority implication:
  this does not change the top strategic ordering: `LLM soft ranking` is still the highest-upside branch and still blocked by coverage. But it upgrades `breakout fast-confirm exit` from "plausible but currently untestable" to "plausible and now credibly testable on a fixed snapshot." If a snapshot-backed rerun still drifts, the next suspect is the earnings-calendar path, not OHLCV.

- `exp-20260422-002` ran that promised fixed-snapshot rerun of `breakout fast-confirm exit` on `data/ohlcv_snapshot_20251023_20260421.json`.
- Result summary:
  - deterministic primary window regressed materially (`EV 0.8470 -> 0.4767`, `sharpe_daily 3.51 -> 3.23`, `return 24.13% -> 14.76%`, `max_drawdown 2.60% -> 3.32%`)
  - six `breakout_no_confirm` exits fired, and the rule increased trade count (`23 -> 26`) while collapsing win rate (`65.2% -> 42.3%`)
  - because the same-data primary verdict was strongly negative, there was no need for additional multi-window spend
- Mechanism implication:
  the old uncertainty is gone. Early breakout under-confirmation by itself is not a useful exit signal in the current accepted A+B stack; the rule cuts too many valid continuations before they get time to work.
- Priority implication:
  remove `breakout fast-confirm exit` from the short list of plausible unblocked A+B retries. The practical ordering tightens again:
  1. `LLM soft ranking` remains the highest-upside direction, still blocked by candidate-level replay coverage.
  2. `C strategy revival` remains secondary until a genuinely richer event-grading mechanism appears.
  3. Any future breakout exit work must start from a genuinely different post-entry mechanism, not another "failed to confirm quickly" variant on the same idea.

- `exp-20260421-027` clarified the remaining `LLM soft ranking` blocker: calendar-day coverage is not the right readiness gauge.
- Result summary:
  - current primary replay window (`2025-10-23 -> 2026-04-21`) shows `6/123` archived trading days, but only `3/34` candidate days and `4/51` candidate signals were actually covered by LLM archives
  - replay metrics stayed unchanged (`EV 0.8676`, `sharpe_daily 3.55`) because this was a measurement-only change
- Mechanism implication:
  the real blocker is candidate-level sample size, not raw day count. A superficially non-zero day-coverage number can still hide an underpowered LLM experiment when almost all uncovered days had no candidates anyway.
- Priority implication:
  keep `LLM soft ranking` as the top strategic direction, but do not treat `~5%` calendar coverage as progress enough on its own. Future go/no-go checks for LLM alpha should read `candidate_day_coverage_fraction` and `candidate_signal_coverage_fraction` first.

- `exp-20260422-003` turned that readiness rule into an actionable backlog: the backtester now surfaces the exact missing candidate dates and the per-date candidate counts, not just aggregate fractions.
- Result summary:
  - fixed-snapshot primary replay (`2025-10-23 -> 2026-04-21`) stayed bit-identical on strategy metrics (`EV 0.8369`, `sharpe_daily 3.49`)
  - the blocker is now explicit: only `3/31` candidate days and `3/44` candidate signals are covered, leaving `28` missing candidate dates in the primary window
  - CLI output now previews the uncovered dates directly (starting with `20251028`, `20251029`, `20251030`, `20251031`, `20251103`)
- Mechanism implication:
  the remaining LLM blocker is no longer just "small sample." It is a concrete archive backlog on specific candidate-bearing dates. That makes the next replay-coverage push operational rather than conceptual.
- Priority implication:
  do not spend another round merely re-proving that LLM coverage is low. Use the explicit missing candidate-date inventory as the go-forward target list, and keep `LLM soft ranking` as the top strategy branch until that inventory is materially reduced.

- `exp-20260422-007` showed that "prompt-ready" is still too coarse a label for the LLM backlog.
- Result summary:
  - `20260219` was not a true missing-response day; it already had a real saved model reply in `llm_output_20260219.json`, which was recoverable into `llm_prompt_resp_20260219.json`
  - deterministic primary replay stayed bit-identical on trading metrics (`EV 0.8369`, `sharpe_daily 3.49`), but candidate coverage improved from `3/31` to `4/31` days and from `3/44` to `4/44` signals
  - `20260312` still has only a prompt/report pair, so it remains a real response gap inside the repo
- Mechanism implication:
  some backlog dates can hide recoverable raw-response artifacts outside the canonical replay filename. The real distinction is now:
  1. recoverable from a saved raw model response
  2. prompt-only, still missing a response
  3. true archive hole with neither prompt nor response
- Priority implication:
  before asking for more forward sample, inspect backlog dates for `llm_output_YYYYMMDD.json` or other real saved response artifacts and backfill those first. But do not overclaim progress: even after this recovery, `LLM soft ranking` remains measurement-blocked because `4/31` candidate days is still too small for a ranking experiment.

- `exp-20260422-008` showed that even "prompt-only vs missing" is still too coarse for the remaining LLM blocker.
- Result summary:
  - deterministic primary replay again stayed bit-identical (`EV 0.8369`, `sharpe_daily 3.49`)
  - backlog classification tightened to four practical tiers: `raw_response_recoverable`, `prompt_only`, `context_only`, `archive_hole`
  - in the current primary window there are `0` remaining raw-response recoveries, `1` prompt-only day (`20260312`), and `26` context-only days; `earnings_snapshot_YYYYMMDD.json` exists on all `27` missing candidate days, but `quant_signals` / `trend_signals` survive on only `1` day each
- Mechanism implication:
  the remaining LLM blocker is no longer "maybe there are still hidden replies somewhere." That branch is locally exhausted for the current primary backlog. The dominant missing mass is now partial daily context without a replayable LLM decision.
- Priority implication:
  stop spending cycles re-auditing the same backlog for hidden `llm_output` files unless new artifacts appear. The next meaningful unblock path is either:
  1. regenerate prompt/response archives for historical candidate days from richer saved pipeline context, or
  2. accumulate more forward candidate-day archives.
  Until one of those happens, `LLM soft ranking` remains the highest-upside branch but still measurement-blocked.

- `exp-20260422-010` showed that even candidate-level replay coverage is still too optimistic if it ignores production-context alignment.
- Result summary:
  - deterministic primary replay stayed bit-identical (`EV 0.8369`, `sharpe_daily 3.49`)
  - the old headline blocker was `4/31` covered candidate days and `4/44` covered candidate signals
  - after comparing covered backtest candidate dates against saved production `quant_signals_YYYYMMDD.json`, only `1/31` candidate days and `1/44` candidate signals were actually production-context aligned
  - two of the four covered days (`20260416`, `20260421`) had replay files but production `quant_signals=[]`, while one covered day (`20260219`) lacked a saved production quant-signals file entirely
- Mechanism implication:
  a dated LLM response file is not automatically a usable soft-ranking sample. The replay archive and the production-side candidate set must refer to the same practical trade opportunity set; otherwise "covered day" can still be a context-mismatched sample that should not count toward LLM alpha readiness.
- Priority implication:
  upgrade the LLM blocker definition again. Future go/no-go checks for `LLM soft ranking` should read `production_aligned_candidate_day_fraction` and `production_aligned_candidate_signal_fraction` before the older raw candidate-coverage metrics. Do not treat `production_quant_empty` covered days as progress toward ranking readiness.

- `exp-20260422-011` showed that even production-aligned covered days can still overstate `LLM soft ranking` readiness if the prompt itself was program-locked before the model could make a real new-trade decision.
- Result summary:
  - deterministic primary replay again stayed bit-identical (`EV 0.8369`, `sharpe_daily 3.49`)
  - replay archives can now carry prompt-time context (`signals_presented`, `new_trade_locked`, `account_state`) automatically via dated advice saves, and alignment can fall back to `llm_decision_log_YYYYMMDD.json` for older archives
  - the practical go/no-go metric is now `ranking_eligible_candidate_day_fraction`, not just `production_aligned_candidate_day_fraction`; in the current primary window that still sits at only `1/31` days and `1/44` signals
- Mechanism implication:
  "dated reply exists" and even "production candidates overlap" are still not enough by themselves. A covered day only counts toward soft-ranking readiness when Task A was actually eligible for a new-trade choice and the prompt-time candidate set overlaps the backtest pre-LLM candidate set.
- Priority implication:
  tighten the blocker definition one more time. Future `LLM soft ranking` work should read `ranking_eligible_candidate_day_fraction_of_total` and `ranking_eligible_candidate_signal_fraction_of_total` first. Do not promote covered days from heat-locked / rule-locked prompts to alpha-readiness progress.

- `exp-20260422-004` tested the cleanest remaining low-complexity repaired-data `C strategy revival` that had not yet been logged: use the existing cross-strategy `trade_quality_score` as a single gate for `earnings_event_long`, instead of adding another bespoke event checklist.
- Result summary:
  - ungated `A+B+C` remained materially worse than the accepted `A+B` stack on the deterministic primary snapshot (`EV 0.6229` vs `0.8470`)
  - sweeping `C`-only `trade_quality_score` thresholds from `0.65` to `0.85` improved on ungated `A+B+C`, but the best threshold (`0.85`) still failed to beat `A+B` (`primary EV 0.8122 < 0.8470`, middle covered subwindow `0.2230 < 0.2383`)
  - at that best threshold, the mechanism left only `1` surviving primary-window `earnings_event_long` trade, effectively approximating "disable C again" rather than creating a positive repaired-data C edge
- Mechanism implication:
  repaired-data `C strategy revival` is now downgraded beyond just event-specific checklists. Even a shared cross-strategy quality metric is not enough to rescue C with a simple scalar gate. The missing edge is not merely "filter out the low-quality C names"; it still requires richer event grading or a stronger marginal-value mechanism than a one-number threshold.
- Priority implication:
  downgrade the broader class of low-complexity `C` revival attempts built from scalar gates, even when the scalar is a reused cross-strategy score rather than a bespoke earnings rule. Practically, this strengthens the current ordering:
  1. `LLM soft ranking` remains the highest-upside direction, still blocked by candidate-level replay coverage.
  2. `C strategy revival` should not be revisited through another simple threshold/checklist family by default.
  3. Unblocked A+B micro-tuning remains secondary to clearing the LLM blocker or finding a genuinely richer C event-grading mechanism.

- `exp-20260422-005` tested the cleanest remaining low-complexity same-day slot-interaction variant for repaired-data `C strategy revival`: keep the accepted A+B stack unchanged, but when multiple `earnings_event_long` candidates appear on the same day, keep only the single highest-`trade_quality_score` C candidate and zero the rest.
- Result summary:
  - deterministic primary snapshot improved only trivially versus ungated `A+B+C` (`EV 0.6316 -> 0.6366`) and still remained far below accepted `A+B` (`0.6366 < 0.8470`)
  - late-2025 bull subwindow was a near-null/slight regression (`0.2280 -> 0.2276`)
  - early-2026 continuation subwindow was a strict null (`0.1482 -> 0.1482`)
  - Feb-Apr stress subwindow regressed materially (`0.1073 -> 0.0807`)
- Mechanism implication:
  the current C drag is not primarily caused by issuing too many same-day earnings candidates. Even after reducing daily C multiplicity to a single top-ranked event, the surviving candidate is still too weak to create a positive marginal edge. That means the missing mechanism is not just slot crowding; it is single-name event quality discrimination.
- Priority implication:
  downgrade another tempting C continuation family alongside scalar gates and standalone-day rules. Do not reopen repaired-data `C strategy revival` with another light same-day crowding tweak unless the ranking source itself becomes materially richer than current `trade_quality_score`. Practically:
  1. `LLM soft ranking` remains the highest-upside direction, still blocked by candidate-level replay coverage.
  2. `C strategy revival` now needs genuinely richer event grading, not another minimal slot-management variant.
  3. Unblocked A+B micro-tuning remains secondary while the top branch is still measurement-blocked.

- `exp-20260422-009` tested the first deterministic `trend_long` exit idea built from a seemingly strong trade-level loser marker: severe early adverse excursion.
- Result summary:
  - the screening audit looked promising: across the accepted-stack trade logs, `trend_long` names that took `>=0.75R` adverse excursion inside the first 3 trading days were usually losers
  - but the portfolio-level rule still failed on all three fixed snapshots: primary `EV 0.8470 -> 0.7063`, bull `0.1255 -> 0.0568`, weak `0.0109 -> 0.0071`
  - the rule cut at least one important slow-burn winner in the primary window (`GOOG`) and also changed downstream slot usage, increasing trade count in the older windows without improving the north-star metric
- Mechanism implication:
  trade-level separation is not enough. A pattern that tags many losing trend trades can still be a bad portfolio rule once replacement-flow and slow-burn winners are included. For `trend_long`, pure early-path OHLCV damage still does not provide enough context to distinguish "broken trade" from "slow winner."
- Priority implication:
  downgrade another appealing unblocked A+B retry family: early-damage / early-pain `trend_long` exits built only from first-few-day price path statistics. If trend exit alpha is revisited again, it should require richer hold-quality context than raw early excursion against the original stop.

- `exp-20260422-012` ran the first deterministic cross-era health audit of the current accepted A+B stack on three fixed OHLCV snapshots instead of relying on a single recent window.
- Result summary:
  - recent window (`2025-10-23 -> 2026-04-21`) stayed strong: `EV 0.8470`, `sharpe_daily 3.51`, with `breakout_long` dominating (`PF 13.74`, `10/12` wins)
  - earlier bull window (`2025-04-23 -> 2025-10-22`) weakened sharply: `EV 0.1255`, strategy return only `10.37%` vs `SPY +25.44%` / `QQQ +33.51%`
  - older mixed-to-weak window (`2024-10-02 -> 2025-04-22`) thinned further: `EV 0.0109`, with `breakout_long` nearly fully broken (`1/7` wins, `PF 0.27`, `-$3.44k`) while `trend_long` remained modestly positive (`PF 1.50`, `+$6.48k`)
  - the snapshot replays reproduced the same headline metrics, so this is now fixed-data evidence rather than vendor-download drift
- Mechanism implication:
  the current system is not driven by one stationary alpha source. `trend_long` is the more persistent but lower-powered carrier; `breakout_long` is the convex, high-upside carrier that can dominate in the right tape and become the main drag in the wrong tape. In other words, breakout should now be treated as a regime-sensitive module, not as an always-on peer that deserves the same default trust in every market phase.
- Failure-response doctrine:
  when this mechanism weakens, the correct response is not "add one more scalar filter" and not "keep assuming breakout is the core engine." The next research branch should study conditional breakout participation: either context-aware de-risking, explicit breakout-health gating, or dynamic capital-allocation shifts toward the more persistent trend sleeve. If the breakout module is unhealthy, the system should be able to trade smaller, rarer, or not at all in that sleeve rather than forcing equal participation.
- Priority implication:
  upgrade a new top unblocked A+B research question: identify observable same-day or recent-history context that predicts `breakout_long` health before entry. At the same time, downgrade further unconditional breakout micro-tuning. Future breakout work should begin from "when should breakout get less capital?" rather than "what extra static rule makes all breakouts better?"

- `exp-20260422-014` tested the first direct runtime answer to that doctrine question: if the breakout sleeve has already closed several consecutive losers, de-risk new `breakout_long` entries until the sleeve recovers.
- Result summary:
  - deterministic sweeps tested a minimal cooldown family on the fixed late / mid / old snapshots: recent closed breakout lookback `2/3/4`, loss threshold equal to the lookback, and breakout multipliers `0.0 / 0.25 / 0.5`
  - the rule never helped the strong recent window because the breakout sleeve did not enter the required losing streak there; that part was a harmless null
  - in the older weak window, the harshest variants did improve the north-star slightly (`EV 0.0109 -> 0.0198` for `lookback=2`, `multiplier=0.0`)
  - but the same variants materially damaged the mid window (`EV 0.1255 -> 0.0285` for `lookback=2`, `multiplier=0.0`), and every tested variant failed to produce a majority-window gain
- Mechanism implication:
  breakout weakness is not well captured by a lagging self-referential PnL cooldown. By the time a short realized-loss streak is visible, the rule is often too late: it de-risks after damage but before the next valid recovery leg, so it cuts convexity in windows where breakout participation is still valuable. In other words, "recent breakout losses" is not yet a rich enough state variable for pre-entry breakout health.
- Priority implication:
  downgrade the family of breakout self-cooldown rules built only from the sleeve's own last-few-trades PnL. Future breakout-health work should prefer forward-looking context sources that exist before entry, such as market-breadth / participation structure, breakout cohort composition, or another observable tape-quality proxy, rather than relying on lagging realized-loss feedback from the breakout module itself.

- `exp-20260422-015` tested the first minimal non-breakout D-strategy candidate: `pullback_long`, defined as a strong uptrend that is still above the 200MA, still carrying positive momentum, and sitting modestly below the prior 20-day high instead of printing a fresh breakout.
- Result summary:
  - deterministic A+B+pullback runs failed the majority-window test:
    - late strong window: `EV 0.8470 -> 0.6654`
    - mid weak window: `EV 0.1255 -> 0.0666`
    - old thin window: `EV 0.0109 -> 0.0321`
  - standalone pullback was also weak rather than merely crowded out:
    - late strong window: `EV 0.0875`, `PF 1.43`, `32` trades
    - mid weak window: `EV 0.0186`, negative return, `PF 1.00`
    - old thin window: `EV 0.0319`, negative return, `PF 0.92`
  - the trial generated too many low-quality candidates and mostly behaved like diluted trend-chasing rather than a distinct high-R multiple continuation edge
- Mechanism implication:
  this first pullback definition is not a true independent alpha carrier. It is too broad and too static: "2-8% below the 20-day high while trend is still positive" mostly captures noisy continuation clutter, not a well-timed re-entry into institutional pullbacks. In practical terms, it produced replacement flow and slot competition without enough standalone expectancy.
- Priority implication:
  downgrade this first family of simple OHLCV-only pullback definitions. Do not keep micro-tuning the same recipe with nearby percentages by default. If pullback continuation is revisited again, it should require a genuinely richer trigger for "pullback has ended and trend has re-asserted" rather than another broad near-high dip template.

- Updated practical ordering after `exp-20260421-014`:
  1. `LLM soft ranking` remains the highest-value strategy direction, but still measurement-blocked by replay coverage.
  2. `C strategy revival` stays downgraded until a genuinely new event-grading or slot-interaction mechanism exists; repaired snapshot coverage alone was not enough.
  3. The current accepted A+B stack now includes the low-TQS commodity exemption, zero risk for the remaining low-TQS non-commodity breakouts, zero risk for `trend_long` Industrials, and a `0.25x` haircut for moderate-gap `trend_long` Technology in the live repo state; further allocation work should start from genuinely new context sources, not more scalar or multiplier tuning on the existing accepted cohorts.

## Recording Standard For Narrow Alpha Rules

When a future alpha rule is accepted, do not leave only a raw multiplier or threshold in code. Record each narrow rule in this shape:

- Rule target:
  which intersection of strategy / sector / shape / regime / event context is affected
- Rule action:
  entry veto, sizing change, ranking lift, or exit mutation
- Layer changed:
  what stayed intentionally unchanged
- Financial logic:
  the plain-English market reason this cohort should behave differently
- Evidence:
  which windows improved, which stayed null, which regressed
- Anti-overclaim:
  what the rule does not prove
- Removal condition:
  what future evidence should cause deletion instead of more micro-tuning

This keeps narrow alpha rules auditable and prevents accepted cohort edges from degrading into unexplained black-box constants.

## 10. 2026-04-22 Addendum

- `exp-20260422-012` showed that even the remaining `prompt_ready` backlog count was still too optimistic for `LLM soft ranking`.
- Result summary:
  - deterministic primary replay stayed bit-identical again (`EV 0.8369`, `sharpe_daily 3.49`, `return 23.98%`)
  - the lone remaining prompt-only missing candidate day, `20260312`, already contains enough saved production context to prove it was not a usable soft-ranking sample: `quant_signals=[]` and `portfolio_heat.can_add_new_positions=false`
  - after tightening backlog classification, the primary-window backlog moved from `prompt_ready 1/27` to `prompt_ready 0/27`, with `prompt_ineligible 1/27`
- Mechanism implication:
  a saved prompt file is still not enough. For missing-response days, the backlog should only count a prompt as actionable when prompt-time context still indicates a genuine ranking-eligible new-trade opportunity; otherwise it belongs with context-only archive gaps, not near-term recoveries.
- Priority implication:
  stop treating `20260312`-style prompt leftovers as meaningful progress toward `LLM soft ranking`. The top strategic direction remains unchanged, but the blocker is now stricter: there are zero ranking-eligible prompt-only recoveries left in the current primary window, so the next real unblock path is fresh forward accumulation or historically regenerated prompt/response archives with preserved prompt-time eligibility.

- `exp-20260422-013` tested the cleanest same-day cross-strategy allocation idea that remained after the breakout-health doctrine shift: de-risk `breakout_long` only when a same-day `trend_long` candidate had a higher `trade_quality_score`.
- Result summary:
  - screened `0.75x`, `0.5x`, `0.25x`, and `0.0x` runtime-only risk multipliers for those breakout candidates across the deterministic late / mid / old A+B snapshots
  - every mild version regressed `expected_value_score` in all three windows (`0.75x`: `0.847 -> 0.8163`, `0.1255 -> 0.1128`, `0.0109 -> 0.0096`)
  - the only primary-window winner (`0.0x`) was a clear multi-window loser (`0.1255 -> 0.0798`, `0.0109 -> 0.0081`)
- Mechanism implication:
  breakout weakness is not just a same-day slot-allocation mistake where trend "deserved the heat more." Relative pre-entry TQS ordering between same-day trend and breakout candidates is too weak a context source; it cuts useful convexity faster than it removes bad breakout exposure.
- Priority implication:
  downgrade the broader family of breakout-vs-trend same-day competition haircuts. Future breakout-health work should not keep permuting same-day relative-score allocation rules by default; it needs a genuinely richer state variable or a narrower repeatedly observed cohort.

- `exp-20260422-014` audited the remaining repo-visible breakout-local field family directly before launching another rule experiment.
- Result summary:
  - matched `100%` of executed trades back to their signal-day attributes across the deterministic late / mid / old A+B snapshots
  - audited the currently available pre-entry fields: `trade_quality_score`, `volume_spike_ratio`, `daily_range_vs_atr`, `pct_from_52w_high`, `gap_vulnerability_pct`, `rs_vs_spy`, sector, and `above_200ma`
  - all matched breakout trades were already `above_200ma`, and several of the worst old-window losers still had high-TQS / high-RS / near-high profiles
  - `rs_vs_spy` stayed strongly positive in the latest strong window but flipped into a loser marker in the older weak windows; `daily_range_vs_atr` improved directionally in weaker eras but still did not justify another unconditional scalar threshold permutation
- Mechanism implication:
  the currently exposed breakout-local state variables are locally exhausted as a family. The missing `breakout health` signal is not another repackaging of the existing quality checklist; it is a different context source that the repo does not currently encode in a stable, reusable way.
- Priority implication:
  stop reopening breakout alpha with another rule built from the same `TQS / 52w-high / range / gap / RS / sector` variable family by default. The next credible A+B branch needs a genuinely richer state variable, such as strategy-local recent breakout health, sector-relative breadth/leadership context, or a future LLM/event-derived ranking signal once replay coverage is real.

- `exp-20260422-015` tested the first direct implementation of one of those candidate richer context families: simple sector participation breadth used only as a breakout ranking scalar.
- Result summary:
  - runtime-only ranking variants added `sector_breakout_breadth`, `sector_mom_breadth`, and `sector_above200_breadth` to breakout candidates, then re-sorted only the breakout subsequence before slot competition
  - `sector_breakout_then_52w` and `sector_mom_then_52w` were strict nulls in the late and mid windows and only changed the oldest weak window by `EV 0.0109 -> 0.0108`
  - `sector_above200_then_52w` was bit-identical to baseline across all three windows
- Mechanism implication:
  sector breadth may describe background tape quality, but in the narrow form "one scalar ranking key inside the current breakout stack" it is too weak to alter the real opportunity set. This branch does not unlock breakout alpha by itself.
- Priority implication:
  downgrade the family `simple breadth-only breakout ranking permutations`. If breadth is revisited, it should not come back as another reorder-only tweak; it needs a richer deployment shape than "sort breakouts by breadth," or a narrower repeatedly observed cohort with stronger evidence. Until then, do not let this branch displace the higher-upside but blocked `LLM soft ranking` direction.

## 11. 2026-04-23 Addendum

- `exp-20260423-001` tested the first pullback-continuation retry that actually followed the `exp-20260422-015` doctrine update instead of just nudging dip percentages: wait for an explicit re-assertion signal after the pullback.
- Result summary:
  - runtime-only `pullback_reclaim_long` required a recent `3-12%` pullback from the prior 20-day high, a same-day reclaim of the prior 5-day high, above-50MA/200MA structure, positive 10-day momentum, supportive volume (`>1.2x`), and no fresh 20-day breakout
  - added to the accepted A+B stack, the new sleeve still failed the majority-window test:
    - late strong window: `EV 0.8470 -> 0.7646`
    - mid weak window: `EV 0.1255 -> 0.1232`
    - old thin window: `EV 0.0109 -> -0.0002`
  - standalone quality also stayed weak:
    - late strong window: `EV 0.0005`, `PF 0.859`, `11` trades
    - mid weak window: `EV 0.0204`, `PF 1.081`, `12` trades
    - old thin window: `EV 0.0046`, `PF 0.712`, `20` trades
- Mechanism implication:
  the problem with pullback continuation is not just that the first template was too broad. Even after forcing an explicit "trend has re-asserted" trigger using only deterministic OHLCV structure, the sleeve still behaved like noisy continuation clutter and weak replacement flow rather than a distinct high-expectancy carrier.
- Priority implication:
  downgrade another tempting retry family: nearby OHLCV-only `pullback reclaim / rebound / re-assertion` variants. If pullback continuation is revisited again, it should require a genuinely different context source than pure price/volume structure alone, such as event context, richer regime state, or an execution shape that does not simply compete with A+B for the same slots.

- `exp-20260422-016` tested the first pure OHLCV-only `relative-strength leadership` D-strategy family.
- Result summary:
  - runtime-only `leadership_long` candidates targeted stocks that stayed above the 200MA, remained close to their highs, materially outperformed SPY, and had not yet printed a fresh 20-day breakout
  - the strict deployment shape was too sparse to matter:
    - `A+B+leadership` moved `EV 0.847 -> 0.8337`, `0.1255 -> 0.1255`, `0.0109 -> 0.0192`
    - incremental leadership trades were only `1 / 0 / 3` across the late / mid / old windows
    - standalone leadership stayed effectively zero-ev (`0.004`, `0.0019`, `0.0007`)
  - the loose deployment shape generated enough sample, but it clearly diluted the accepted stack:
    - `A+B+leadership` moved `EV 0.847 -> 0.6981`, `0.1255 -> 0.0453`, `0.0109 -> 0.0011`
    - standalone leadership looked superficially alive in the late / mid windows (`EV 0.0836`, `0.1071`) but flipped to negative return and negative `sharpe_daily` in the old window
- Mechanism implication:
  this first leadership family bifurcates into two bad modes. A strict below-breakout leader definition is too sample-starved to become a meaningful sleeve, while a looser one simply turns into diluted continuation flow that competes with A+B without a clean independent edge. In other words, "strong stock near highs but not yet breaking out" is not enough by itself to define a robust new strategy in the current repo state.
- Priority implication:
  downgrade this first family of stock-local OHLCV-only leadership templates. If `relative-strength leadership` is revisited, it should require a richer activation context than near-high shape plus RS alone, such as market-leadership regime context, explicit sector-relative persistence, or a cleaner event-linked trigger. Do not keep sweeping nearby thresholds on this recipe by default.

---

## 11. Meta-Layer Upgrade Plan (2026-04-23)

### 11.1 New strategic framing

The current repo state increasingly suggests that the main bottleneck is not "find one more alpha entry pattern," but "route risk to the right alpha sleeve for the current market state."

Practical interpretation:

- the system already has at least two real alpha sleeves:
  - `trend_long`: steadier continuation / hold-management sleeve
  - `breakout_long`: more convex, more phase-sensitive sleeve
- some defensive / commodity behavior already appears in the accepted stack and in prior cohort work, but it is not yet promoted to a standalone sleeve
- therefore the next high-value branch is a `meta layer`, not another round of local breakout parameter churn

Default doctrine update:

1. treat `alpha orchestration` as a first-class research branch
2. do not frame the next stage as "replace all sleeves with one best strategy"
3. default objective becomes: detect which sleeve should receive more risk now

### 11.2 Four-phase plan

#### Phase 1: Alpha Map

Goal:
build a historical map of which sleeve actually generated the edge in each market segment.

Questions:

- when did `trend_long` drive the PnL?
- when did `breakout_long` help or hurt?
- when did defensive / commodity-like exposure matter?
- where did the system become hard because of crowding / rotation / false follow-through?

Required outputs:

- window-by-window strategy attribution
- sector / sleeve contribution map
- first-pass labels for market states that matter to allocation

#### Phase 2: Minimal Meta Features

Goal:
define a small set of replayable state variables that can explain sleeve rotation.

Priority feature families:

- `regime classifier`
  not just bull / bear / neutral, but sleeve-relevant states like trend-friendly, breakout-friendly, crowded-chop, macro-defensive
- `crowding proxy`
  a flow / positioning / leadership concentration proxy
- `volatility state`
  whether the current tape is high-vol / fake-breakout prone
- `defensive leadership`
  whether commodity / healthcare / defensive groups are taking over leadership

Constraint:
start with a small, auditable feature set; do not jump straight to a black-box classifier.

#### Phase 3: Meta Allocation

Goal:
use the meta state to change sleeve weights before adding more new strategies.

Target outputs:

- `breakout_weight`
- `trend_weight`
- `defensive_weight`
- `gross_risk_multiplier`

Preferred first deployment shape:

- sleeve-level allocation or gating
- not a complex prediction model
- not a rewrite of every signal rule

#### Phase 4: New Sleeves

Only after the meta layer begins to work should the repo spend more cycles on new sleeves such as:

- `reversal alpha`
- more explicit `macro alpha`
- richer `leadership alpha`

Doctrine:
first decide **when to use which alpha**, then expand **what alpha exists**.

### 11.3 Phase 1 first cut: alpha map from the old fixed snapshot

Research setup:

- data source: `data/ohlcv_snapshot_20241002_20250422.json`
- stack: current accepted deterministic A+B stack
- subwindows:
  - `2024-10-02 -> 2024-12-31`
  - `2025-01-02 -> 2025-02-28`
  - `2025-03-03 -> 2025-04-22`

First-cut findings:

#### Window A: 2024-10 -> 2024-12

- total result: `EV 0.0770`, `sharpe_daily 1.15`, `return +6.70%`
- `trend_long` drove the window:
  - `12` trades
  - `+$8.79k`
  - `profit_factor 2.65`
- `breakout_long` was the drag:
  - `4` trades
  - `-$2.10k`
  - `win_rate 25%`
- technology was not a clean "AI beta breakout" win inside the current implementation:
  - `trend_long | Technology` was positive
  - `breakout_long | Technology` lost money

Interpretation:
this window was much more "trend continuation alpha with some tech exposure" than "current breakout sleeve dominates."

#### Window B: 2025-01 -> 2025-02

- total result: `EV 0.0553`, `sharpe_daily 1.20`, `return +4.61%`
- the edge rotated:
  - `breakout_long`: `4` trades, `+$4.45k`, `win_rate 75%`, `profit_factor 8.95`
  - `trend_long`: `6` trades, only `+$0.16k`, weak expectancy
- best areas were more mixed than a pure AI trend story:
  - Financials
  - Communication Services
  - some Healthcare contribution
- trend exposure in Technology lost money in this slice

Interpretation:
in the current repo implementation this was not "trend strongest"; it looked more like a selective breakout / rotation-friendly window where the trend sleeve lagged.

#### Window C: 2025-03 -> 2025-04

- total result: `return -1.13%`, but still beat `SPY` and `QQQ` because the tape was weak
- only `2` trades fired, both `trend_long`, both losers
- one trade was in `Commodities`, one in `Consumer Discretionary`
- sample is too small to claim a true defensive sleeve win

Interpretation:
the repo evidence supports "hard macro / defensive tape" as a context shift, but not yet a robust standalone defensive alpha claim. What it clearly shows is that the current A+B stack becomes low-activity and underpowered here.

### 11.4 Mechanism implication from Phase 1

Current best interpretation:

- the repo does not have a single stable dominant sleeve across these sub-periods
- `trend_long` and `breakout_long` take turns carrying the system
- the "hard period" is not just low Sharpe; it is also sleeve mismatch
- therefore the next high-value branch should be a `meta allocation` layer, not another attempt to force one sleeve to fit all tapes

### 11.5 Next concrete step after Phase 1

Do next:

1. extend the alpha map to the later strong snapshot windows as the comparison anchor
2. define the first tiny set of meta features for sleeve selection
3. test a simple sleeve-level rule before any complex model:
   - when to de-weight `breakout_long`
   - when to let `trend_long` dominate
   - when overall risk should fall because neither sleeve is in its best state

Do not do next by default:

- do not reopen another local breakout scalar sweep
- do not reopen the first `leadership_long` or `pullback_long` templates with nearby thresholds
- do not treat this phase-1 map as permission to invent a broad black-box regime classifier yet

### 11.6 Phase 2 first cut: minimal meta features

Research setup:

- data sources:
  - `data/ohlcv_snapshot_20241002_20250422.json`
  - `data/ohlcv_snapshot_20251023_20260421.json`
- windows compared:
  - `trend_ai_beta`: `2024-10-02 -> 2024-12-31`
  - `crowded_rotation`: `2025-01-02 -> 2025-02-28`
  - `macro_defensive`: `2025-03-03 -> 2025-04-22`
  - `late_strong_anchor`: `2025-10-23 -> 2026-04-21`
- candidate daily state variables were averaged within each window:
  - `breadth_above_200`
  - `breadth_positive_mom`
  - `breakout_breadth`
  - `offense_minus_defense_breadth`
  - `leadership_concentration_pos`
  - `leadership_concentration_breakout`
  - `momentum_dispersion_10d`
  - `spy_pct_from_ma`
  - `qqq_pct_from_ma`
  - `qqq_minus_spy_mom10`
  - `spy_realized_vol_20d`

First-cut findings:

- the weak macro window is easy to separate from the healthier windows:
  - `breadth_above_200`: `0.4713` vs `0.6262` to `0.8311`
  - `breadth_positive_mom`: `0.3349` vs `0.4997` to `0.5794`
  - `spy_pct_from_ma`: `-0.0343`
  - `qqq_pct_from_ma`: `-0.0508`
  - `spy_realized_vol_20d`: `0.0183` vs `0.0072` to `0.0087`
- therefore a first meta layer should almost certainly include:
  - market pressure / breadth
  - volatility stress
- the harder problem is not "healthy vs stressed"; it is "which sleeve inside a healthy tape":
  - `trend_ai_beta` and `crowded_rotation` both had high breadth and low vol
  - yet `trend_long` led one and `breakout_long` led the other
- the most promising differentiators inside healthy windows are weaker and should be treated as candidates, not truths:
  - `offense_minus_defense_breadth`
    - `trend_ai_beta`: `+0.2114`
    - `crowded_rotation`: `-0.2160`
    - `late_strong_anchor`: `-0.1585`
  - `leadership_concentration_pos`
    - `trend_ai_beta`: `0.4186`
    - `crowded_rotation`: `0.2982`
    - `late_strong_anchor`: `0.3423`
  - `qqq_minus_spy_mom10`
    - positive in `trend_ai_beta`
    - flat to negative in the breakout-led windows

Mechanism implication:

- do not jump straight to one multi-class meta classifier
- the current evidence supports a two-layer interpretation:
  1. first detect `stress / weak-tape` using broad pressure + volatility
  2. only inside healthier tapes, try to separate `trend-led` from `breakout-led`
- that second problem is still subtle; the current repo-visible candidates are suggestive, not decisive

Priority implication:

the first implementation of the meta layer should be deliberately narrow:

1. build a `risk-state` layer first
   - broad pressure
   - breadth
   - volatility stress
2. only then test a tiny healthy-tape sleeve switch
   - candidate inputs: offense-vs-defense breadth, leadership concentration, QQQ-vs-SPY momentum
3. do not start with a large feature set or opaque classifier

### 11.7 Three-layer meta doctrine

The analyst framing is directionally right, but the repo should not implement it as one flat "regime classifier." The cleaner architecture is a three-layer meta stack with different responsibilities:

#### Layer 1: Market Structure

Primary question:
is this a broad, healthy environment where long alpha can express, or a narrow / fragmented tape where only parts of the market are really working?

Most relevant inputs:

- `breadth_above_200`
- `breadth_positive_mom`
- `breakout_breadth`
- equal-weight vs cap-weight style proxies
- sector dispersion / participation spread

Why this layer matters:

- it answers whether the system is operating in a generally supportive structure
- it prevents the repo from confusing "index is up" with "the opportunity set is broad"
- it should be the top-level gate for whether the system is in a healthy tape at all

#### Layer 2: Volatility & Correlation

Primary question:
even if the tape is not fully broken, is current volatility / cross-asset stress high enough that the system should de-risk?

Most relevant inputs:

- `spy_realized_vol_20d`
- intraday range abnormality proxies
- market stress vs calm
- future cross-asset correlation proxies when available

Why this layer matters:

- it is more about `risk overlay` than sleeve choice
- it tells the system how hard to lean, not only whether to participate
- current repo evidence already supports this layer strongly: the weak macro window is easy to separate using breadth + index pressure + volatility

#### Layer 3: Flow / Positioning

Primary question:
inside a still-tradable tape, is current behavior supportive of convex breakout follow-through, or does the tape look crowded / fake-breakout prone?

Most relevant inputs:

- leader failure proxies
- fake-breakout / gap-fade behavior
- leadership concentration
- offense-vs-defense participation spread
- cohort-composition proxies richer than raw count

Why this layer matters:

- this is the layer most likely to improve sleeve routing between `trend_long` and `breakout_long`
- it is also the layer with the highest overfitting risk
- therefore it should be added last and with the smallest number of interpretable proxies first

### 11.8 First batch of six meta features

Default first batch for implementation research:

1. `breadth_above_200`
   broad structure / market health
2. `breadth_positive_mom`
   short-horizon participation breadth
3. `spy_pct_from_ma`
   broad market pressure / distance from long-term support
4. `qqq_pct_from_ma`
   growth / leadership pressure
5. `spy_realized_vol_20d`
   stress / volatility overlay
6. `offense_minus_defense_breadth`
   early sleeve-routing candidate inside healthy tapes

Reason for this batch:

- all six are replayable now
- the first five already have a clear mechanism story in the existing snapshot research
- the sixth is the cheapest first step toward `trend vs breakout` routing without introducing a broad black-box flow model

### 11.9 What is intentionally deferred

Do not implement these in the first meta pass by default:

- a large multi-class regime classifier
- many flow proxies at once
- opaque model-weighted feature combinations
- institution-only positioning ideas that the repo cannot replay

Deferred but promising families:

- equal-weight vs cap-weight proxy
- sector dispersion as a formal daily metric
- gap-up fade / close-off-high leader behavior
- breakout failure-rate proxies
- cross-asset correlation proxies involving rates / gold / equities

### 11.10 Practical next experiment shape

The first true meta-allocation experiment should likely be:

1. a narrow `risk-state` layer using:
   - `breadth_above_200`
   - `breadth_positive_mom`
   - `spy_pct_from_ma`
   - `qqq_pct_from_ma`
   - `spy_realized_vol_20d`
2. deployment shape:
   - reduce gross risk or suppress the more convex sleeve when the tape is clearly stressed
3. keep the healthy-tape sleeve-routing problem separate:
   - use `offense_minus_defense_breadth` as the first lightweight candidate
   - do not merge it into the stress classifier on day one

### 11.11 First risk-state allocation attempt: rejected broad stress template

- `exp-20260423-013` tested the first actual `risk-state` deployment implied by the meta-layer plan.
- Result summary:
  - runtime-only sizing variants attached a broad stress flag to each signal using replayable structure / pressure proxies:
    - `breadth_above_200 <= 0.55`
    - `breadth_positive_mom <= 0.40`
    - `spy_pct_from_ma <= -3%`
    - `qqq_pct_from_ma <= -4%`
    - or a large `QQQ-SPY` momentum gap combined with weak breadth
  - screened two deployment shapes across the deterministic late / mid / old windows:
    - gross risk haircut: `0.5x`, `0.25x`
    - breakout-only haircut: `0.25x`, `0.0x`
  - every screened variant failed the majority-window test:
    - `stress_gross_0.5x`: late `0.8470 -> 0.7777`, mid `0.1255 -> 0.1281`, old `0.0109 -> 0.0073`
    - `stress_gross_0.25x`: late `0.8470 -> 0.7135`, mid `0.1255 -> 0.1287`, old `0.0109 -> 0.0059`
    - `stress_breakout_0.25x`: late `0.8470 -> 0.7804`, middle / old strict null
    - `stress_breakout_0x`: late `0.8470 -> 0.7579`, middle / old strict null
  - trigger audit explained why:
    - late strong window: stress fired on `65 / 129` trading days (`50.4%`)
    - mid weak window: `11 / 131` (`8.4%`)
    - old thin window: `59 / 145` (`40.7%`)
- Mechanism implication:
  the meta-layer direction still looks right, but this first `risk-state` definition was too broad and too OR-heavy. It confused volatile-yet-healthy breakout conditions with genuine weak-tape stress, especially in the dominant recent window. That means the first live risk-state layer should not be "any single warning sign means stress."
- Priority implication:
  narrow the doctrine for the next attempt. If the risk-state branch continues, require a more hierarchical state definition, for example:
  1. simultaneous breadth weakness **and** negative index pressure, or
  2. explicit two-stage logic: first detect weak tape, then separately decide whether breakout should be de-risked

Do not do next:

- do not retry the same broad OR-combined stress template with nearby multipliers
- do not merge `risk-state` and healthy-tape sleeve routing into one classifier just to rescue this failure

- `exp-20260423-002` tested the first breakout-health sizing rule that actually used a richer forward-looking participation state instead of another stock-local breakout field or scalar ranking key.
- Result summary:
  - runtime-only breadth-aware sizing variants tagged a `narrow-leadership bull` day when whole-universe participation still looked structurally healthy on the long horizon (`above200_breadth >= 0.80`) but short-term participation had thinned (`positive_momentum_breadth <= 0.55`), then reduced only `breakout_long` risk on those days
  - the best strict variant (`breakout 0.0x`) produced the first encouraging cross-window breakout-health shape after the doctrine shift:
    - late strong window: strict null (`EV 0.8470 -> 0.8470`)
    - mid weak window: improved (`EV 0.1255 -> 0.1366`, `maxDD 5.11% -> 3.73%`)
    - old thin window: improved (`EV 0.0109 -> 0.0202`, `maxDD 9.03% -> 8.23%`)
  - a milder `0.25x` version showed the same qualitative direction but still stayed primary-window null
- Mechanism implication:
  this is the first concrete evidence that the missing breakout-health state may indeed live in a forward-looking participation regime, not in another stock-local quality checklist. Narrow leadership appears directionally useful as a *context* for breakout risk, especially in weaker eras. But the evidence is still incomplete: the current strongest window did not improve at all, so the mechanism is not yet promotable as an always-on accepted rule.
- Priority implication:
  upgrade `forward-looking participation-state breakout health` into the small `promising but unaccepted` bucket. That is different from both "rejected breadth ranking" and "accepted rule." Future work may revisit this branch, but only with one of:
  1. more forward data or another fixed primary window where the state occurs often enough to test present-tense value,
  2. a richer deployment of the same idea (for example graduated sizing instead of binary 0x),
  3. another participation proxy that stays in the same mechanism family.
  Do not misread this as permission to reopen generic breakout discounts or the exhausted stock-local breakout field family.

- `exp-20260423-003` tested the most obvious follow-up to that doctrine update: keep the same whole-universe participation-state mechanism, but replace the binary haircut with richer deployment shapes and one extra participation proxy.
- Result summary:
  - runtime-only variants attached `above200_breadth`, `positive_momentum_breadth`, `breakout_breadth`, and `breadth_gap` to breakout candidates, then screened five graduated sizing families instead of just `0.0x / 0.25x`
  - the best primary-safe variant (`nlb_gap2_bk008`) kept the late strong window as a strict null while still helping the weak windows:
    - late strong: `EV 0.8470 -> 0.8470`
    - mid weak: `EV 0.1255 -> 0.1356`
    - old thin: `EV 0.0109 -> 0.0165`
  - the strongest weak-window rescue (`nlb_gap_only_gradual`) pushed the weaker eras further:
    - mid weak: `EV 0.1255 -> 0.1442`
    - old thin: `EV 0.0109 -> 0.0267`
    - but it regressed the late strong window: `EV 0.8470 -> 0.8289`
- Mechanism implication:
  the useful information in this branch is still the same forward-looking participation state, not the deployment shape. Switching from binary to graduated sizing, and even adding a simple `breakout_breadth` proxy, still does not create present-tense edge in the current dominant window. So the remaining blocker is no longer "maybe the haircut is too blunt"; it is that this mechanism still lacks current-window evidence on present data.
- Priority implication:
  tighten the doctrine for this branch. `forward-looking participation-state breakout health` remains `promising but unaccepted`, but stop defaulting to more `binary vs graduated` deployment sweeps inside the same whole-universe narrow-leadership family. If the branch is revisited, it should require either:
  1. fresh forward data or another fixed primary window where the state actually occurs often enough to test current value, or
  2. a genuinely different participation proxy in the same mechanism family, not another small sizing-shape permutation.
  Until then, do not let this branch consume repeated alpha-search cycles.

- `exp-20260423-004` tested that requested next step directly: keep the breakout-health mechanism class, but swap the whole-universe participation proxy for sector-relative participation context.
- Result summary:
  - runtime-only sizing variants attached `sector_above200_breadth`, `sector_positive_momentum_breadth`, `sector_breakout_breadth`, plus market breadth references, to each candidate day
  - screened six breakout-only variants: sector narrow-leadership states (`sector above200 high + sector momentum low + sector breakout scarce`) at `0.0x/0.25x`, plus market-vs-sector relative-momentum-gap states at `0.0x/0.25x`
  - every screened variant stayed a strict null in the late strong window (`EV 0.8470 -> 0.8470`)
  - every screened variant also stayed a strict null in the mid weak window (`EV 0.1255 -> 0.1255`)
  - only the oldest weak window improved modestly in the best sector-narrow-leadership form (`EV 0.0109 -> 0.0165`, `maxDD 9.03% -> 8.00%`)
- Mechanism implication:
  replacing whole-universe breadth with sector-relative breadth is not enough by itself. The participation family still fails to produce present-tense value in the current dominant tape, and now also fails to improve the intermediate weak-bull tape. That means the missing breakout-health signal is not simply "look at the sector instead of the whole market" if the information remains a static same-day breadth snapshot.
- Priority implication:
  pause the broader family of participation-breadth-only breakout sizing retries, not just the whole-universe sub-branch. If breakout-health work is revisited again, it should require a richer context source than breadth alone, such as sector-relative leadership persistence over time, event context, or fresh forward data that creates a new primary-window test. Do not keep sweeping nearby sector breadth thresholds by default.

- `exp-20260423-005` tested the next richer proxy that the doctrine itself pointed to: replace same-day sector breadth with 5-day sector-relative leadership persistence, but keep the deployment shape modest by changing only `breakout_long` risk budget.
- Result summary:
  - runtime-only sizing variants attached `sector_above200_breadth_5d`, `sector_posmom_breadth_5d`, `sector_breakout_breadth_5d`, and `market_posmom_breadth_5d` to breakout candidates, then screened a small family of breakout-only haircuts keyed off persistent sector weakness relative to the market
  - the best strict form (`spersist_strict_0`) materially improved only the middle window:
    - late strong: strict null (`EV 0.8470 -> 0.8470`)
    - mid weak: improved (`EV 0.1255 -> 0.1570`, `maxDD 5.11% -> 4.20%`)
    - old thin: strict null (`EV 0.0109 -> 0.0109`)
  - even the looser 0x form only nudged the late window by noise (`EV 0.8470 -> 0.8500`) while still staying old-window null
- Mechanism implication:
  sector-relative persistence is genuinely richer than the rejected same-day breadth snapshots, but in the breakout-haircut deployment it still behaves like a one-window failure-mode detector, not a stable current-stack edge. The branch moved from "same-day breadth is too weak" to "persistence still does not generalize enough as a breakout-only risk overlay."
- Priority implication:
  stop defaulting to more breakout-haircut retries inside this family. If sector-relative persistence returns, it should do so in a different deployment shape or with fresh forward data that creates a real primary-window test.

- `exp-20260423-006` tested that different deployment shape directly: use the same sector-persistence context not as a breakout haircut, but as a new non-overlapping continuation sleeve, `leadership_persist_long`, added only when A+B had not already taken the ticker.
- Result summary:
  - the strict sleeve finally produced meaningful primary-window sample and improved the late strong window:
    - late strong: `EV 0.8470 -> 0.9831`
    - mid weak: regressed (`EV 0.1255 -> 0.1097`)
    - old thin: strict null (`EV 0.0109 -> 0.0109`)
  - the loose sleeve still improved the late strong window, but damaged the middle window much more (`EV 0.1255 -> 0.0546`) while also leaving the old window unchanged
- Mechanism implication:
  sector-persistence continuation is not sample-starved anymore, so the failure is no longer "not enough data." The clearer lesson is that this context currently concentrates into the strongest tape only. It can add continuation in a specific regime, but it does not yet define a stable repo-level D sleeve across adjacent windows.
- Priority implication:
  downgrade the broader family `OHLCV-only sector-persistence continuation sleeves`. Do not keep sweeping nearby thresholds on `leadership_persist_long` by default. If this family is revisited, it should require either fresh forward evidence for a regime-conditioned deployment or a genuinely different context source, such as event information.

- `exp-20260423-007` tested the first explicit A+B earnings-risk exit idea: if the system already knows a held `trend_long` / `breakout_long` position is approaching earnings, force a deterministic exit `1/2/3` trading days before the event instead of carrying the position through the gap-risk zone.
- Result summary:
  - runtime-only backtester variants attached a single new exit rule, `pre_earnings_exit_days`, and screened `1d / 2d / 3d` across the deterministic late / mid / old snapshot windows
  - every tested variant improved the weaker windows but failed the majority-window promotion gate because the dominant late-strong window regressed materially:
    - `1d`: late `EV 0.8470 -> 0.7453`, mid `0.1255 -> 0.1426`, old `0.0109 -> 0.0341`
    - `2d`: late `EV 0.8470 -> 0.7192`, mid `0.1255 -> 0.1472`, old `0.0109 -> 0.0329`
    - `3d`: late `EV 0.8470 -> 0.7370`, mid `0.1255 -> 0.1215`, old `0.0109 -> 0.0333`
  - the rule fired only a few times per window, and the forced exits were usually not disaster avoidance; they mostly clipped still-profitable continuation trades (`XOM`, `ISRG`, `SPOT`, `DIS`) before the move had finished
- Mechanism implication:
  the missing A+B edge is not solved by a blanket "never hold through earnings" rule. In the current repo state, this deterministic exit behaves like premature profit clipping: it does help some weaker tapes, but it sacrifices too much of the main-window continuation convexity to qualify as a stable repo-level improvement. The problem is not that earnings-risk is imaginary; it is that a coarse always-on pre-event exit is too blunt relative to the actual winner distribution.
- Priority implication:
  downgrade the family of unconditional pre-earnings exits for A+B positions. If earnings-aware exit work returns, it should not come back as another fixed `1/2/3-day` blanket rule. It would need either a richer selector for which positions should be de-risked before earnings, or stronger production/backtest exit-parity evidence so exit alpha can be measured on the right ruler.

- `exp-20260423-008` tested a different forward-looking breakout-health proxy than breadth, persistence, or lagging realized-PnL cooldown: use the same-day breakout cohort size itself as the state variable, and de-risk `breakout_long` whenever the accepted stack surfaces multiple breakout candidates on the same session.
- Result summary:
  - runtime-only sizing variants kept the accepted A+B stack unchanged except for one breakout-only rule: when same-day breakout candidate count met a threshold, apply a breakout risk multiplier
  - screened `count >= 2` with `0.5x / 0.25x / 0.0x`, plus a stricter `count >= 3` family, across the deterministic late / mid / old snapshot windows
  - every `count >= 2` variant failed the majority-window test:
    - `0.5x`: late `EV 0.8470 -> 0.8180`, mid `0.1255 -> 0.0969`, old `0.0109 -> 0.0146`
    - `0.25x`: late `EV 0.8470 -> 0.8266`, mid `0.1255 -> 0.0752`, old `0.0109 -> 0.0165`
    - `0.0x`: late `EV 0.8470 -> 0.7124`, mid `0.1255 -> 0.0615`, old `0.0109 -> 0.0144`
  - the stricter `count >= 3` family was a strict null across all three windows, meaning the state was too rare to matter in the current replayed eras
- Mechanism implication:
  raw same-day breakout crowding is not a rich enough breakout-health proxy. It behaves like a blunt anti-convexity rule: mild versions still cut too much useful breakout participation in the strong and middle windows, while harsh versions simply over-suppress the sleeve. Unlike the earlier lagging self-cooldown rule, this proxy is forward-looking, but it still lacks the information content needed to separate "too many breakouts because the tape is unhealthy" from "multiple valid convex opportunities arrived together."
- Priority implication:
  downgrade the family of breakout-health rules built only from same-day breakout candidate count or nearby count thresholds. If breakout cohort-composition work is revisited, it should not come back as another raw-count trigger; it would need a richer forward-looking composition proxy, such as cohort quality dispersion, stronger concentration evidence, or event-linked context. For now, this branch should not displace other unblocked alpha searches.

- `exp-20260423-009` tested the most literal follow-up to that doctrine note: keep the same breakout-health problem class, but replace raw cohort size with same-day cohort quality concentration measured by post-enrichment `trade_quality_score` gaps inside the breakout set.
- Result summary:
  - runtime-only sizing variants kept the accepted A+B stack unchanged except for one breakout-only rule: when at least two enriched `breakout_long` candidates survived to sizing, compare each breakout's `trade_quality_score` to the day's best breakout and haircut only the lower-tail names when the gap to the leader reached `0.05` or `0.08`
  - screened `0.25x` and `0.0x` lower-tail multipliers across the deterministic late / mid / old snapshot windows
  - every screened variant was a strict null across all three windows:
    - late strong: `EV 0.8470 -> 0.8470`
    - mid weak: `EV 0.1531 -> 0.1531`
    - old thin: `EV 0.0088 -> 0.0088`
  - the trigger audit explains the null:
    - late strong window: only `1` qualifying lower-tail breakout signal across `35` candidate days
    - mid weak window: `0` qualifying signals across `53` candidate days
    - old thin window: `0` qualifying signals across `47` candidate days
- Mechanism implication:
  same-day breakout cohort composition is still not the missing edge if it is expressed only as `trade_quality_score` concentration. After the accepted breakout ranking, sector cap, and current sizing stack are applied, the TQS-gap state is too sparse to explain the remaining breakout instability. This is not a “good idea with weak effect”; it is another family that currently does not occur often enough to matter.
- Priority implication:
  pause the sub-family `same-day breakout lower-tail haircuts keyed only off TQS gap to the best breakout`. If breakout cohort composition is revisited again, it should not return as another nearby `0.05/0.08` concentration tweak. The next credible cohort-composition branch would need a more frequent and information-rich proxy than TQS-gap concentration alone, or genuinely fresh forward data that creates new present-tense breakout collisions.

- `exp-20260423-010` tested the obvious narrower follow-up to the rejected blanket A+B pre-earnings exit: keep the earnings-risk family, but de-risk only positions that are already weak instead of clipping profitable continuation names.
- Result summary:
  - runtime-only exit variants left the accepted A+B stack unchanged except for one holding-period rule: if an open `trend_long` or `breakout_long` position had `close <= entry_price` and the next earnings date was within `1/2/3` trading days, force a same-day close exit
  - the best variant (`3d`) still failed the majority-window test:
    - late strong window: `EV 0.8470 -> 0.7857`
    - mid weak window: `EV 0.1255 -> 0.1358`
    - old thin window: `EV 0.0109 -> 0.0109`
  - the trigger audit showed why the effect stayed weak:
    - late strong window: only `1` affected trade (`GS breakout_long`)
    - mid weak window: only `1` affected trade (`DIS breakout_long`)
    - old thin window: `0` affected trades
- Mechanism implication:
  narrowing the selector removes the worst part of the blanket rule, but it still does not unlock a stable A+B edge. The family has now degenerated into sparse loser patching: it occasionally rescues an already-weak pre-earnings position, but it is too rare and too local to explain the remaining portfolio-level alpha leak.
- Priority implication:
  downgrade the broader family `pre-earnings loser-only escape hatches` alongside the already rejected blanket pre-earnings exits. If earnings-aware A+B exits are revisited again, they should not come back as nearby `close <= entry`, unrealized-loss, or similarly narrow price-only selectors. The next credible branch would need a richer event-risk discriminator or new evidence that earnings-gap exposure is being measured on the right ruler.

- `exp-20260423-011` tested the first multi-day `trend_long` hold-quality exit that was genuinely richer than the already-rejected one-day weak-close / breakeven-lock family.
- Result summary:
  - runtime-only backtester variants left the accepted A+B stack unchanged except for one `trend_long` exit rule: after a position was already profitable, force a same-day close exit only when it accumulated `2/3` consecutive weak hold days defined by low `trend_score`, non-positive `momentum_10d_pct`, and a `2-3%` close-from-peak drawdown
  - across the deterministic late / mid / old snapshot windows, every screened variant stayed a strict null in the dominant late-strong window
  - every screened variant also regressed the middle window (`EV 0.1344 -> 0.1301`, `0.1073`, `0.1317`, `0.1301`)
  - the oldest weak window improved only marginally in the best form (`EV 0.0075 -> 0.0085`) while acting mostly as drawdown reduction rather than a material EV unlock
- Mechanism implication:
  even a repeated-deterioration selector is still not rich enough when it is built only from deterministic price-state fields. The family is no longer blocked by sample size or by a one-day trigger being too noisy; it actually fires, but it behaves like weak-tape damage control instead of a stable repo-level source of exit alpha. In other words, the missing `trend_long` hold-quality signal is not simply "wait for two weak days instead of one" if the information still comes from the same `trend_score / momentum / drawdown-from-peak` price-only family.
- Priority implication:
  pause the sub-family `multi-day deterministic trend hold-quality exits` built only from `trend_score`, `momentum_10d_pct`, and close-from-peak deterioration. If `trend_long` exit work is revisited again, it should require a genuinely different context source, such as event / semantic information or another trade-specific state variable, rather than more nearby `2-day vs 3-day` permutations on the same price-only deterioration recipe.

- `exp-20260423-012` tested the strongest unblocked follow-up to the still-promising participation-state breakout-health branch: do not just haircut `breakout_long` on narrow-leadership days, rotate budget across sleeves by cutting breakout risk and modestly boosting `trend_long`.
- Result summary:
  - runtime-only sizing variants derived the same whole-universe participation state from existing feature fields (`above_200ma`, `momentum_10d_pct`, `breakout_20d`): `above200_breadth >= 0.80` plus `positive_momentum_breadth <= 0.55`
  - screened two cross-sleeve deployment shapes across the deterministic late / mid / old snapshots:
    - `rot_bk025_tr125`: late `EV 0.8470 -> 0.8470`, mid `0.1255 -> 0.1308`, old `0.0109 -> 0.0206`
    - `rot_bk000_tr125`: late `EV 0.8470 -> 0.8470`, mid `0.1255 -> 0.1372`, old `0.0109 -> 0.0199`
  - the best variant also reduced drawdown in both weaker windows (`5.11% -> 3.85%`, `9.03% -> 8.34%`)
  - but the dominant late-strong window had `0` triggered state days, so the branch still could not prove present-tense value on the current primary tape
- Mechanism implication:
  this is a better deployment shape than the earlier breakout-only narrow-leadership haircuts. The useful information in the participation state may be about *which sleeve should own the risk budget*, not only whether breakout should be de-risked. But the mechanism is still blocked by trigger scarcity in the dominant recent window, so this is not yet accepted repo logic.
- Priority implication:
  keep `participation-state cross-sleeve rotation` in the small `promising but unaccepted` bucket. If revisited, do not keep sweeping nearby thresholds or small multiplier permutations. The next legitimate retry needs either:
  1. fresh forward data where the state actually appears in the primary window, or
  2. a genuinely different participation proxy that triggers on present-tense data.

- `exp-20260423-013` tested the first repaired-data `C strategy revival` branch that explicitly used marginal slot evidence instead of another standalone gate or scalar quality filter: isolate `earnings_event_long` from A+B generation side effects, then allow only the single best same-day C candidate to replace the weakest live A/B slot when `positive_surprise_history=True` and its event score (`trade_quality_score + confidence + surprise-history + above_200ma`) is at least as strong as that weakest A/B candidate.
- Result summary:
  - deterministic late / mid / old snapshots against the accepted A+B stack:
    - late strong: `EV 0.8470 -> 0.9814`
    - mid weak: strict null `0.1255 -> 0.1255`
    - old thin: strict null `0.0109 -> 0.0109`
  - trigger audit:
    - exactly `1` replacement across the three windows
    - chosen C: `DE earnings_event_long`
    - replaced A/B slot: `MCD trend_long`
    - middle and old windows had `0` replacements
- Mechanism implication:
  repaired earnings metadata plus same-day marginal-slot comparison can occasionally identify a C trade that is better than the weakest live A/B slot, so this branch is cleaner than the already-rejected scalar PEAD gates. But the state is still far too sparse to define a stable repo-level deployment rule. The blocker has shifted again: not data quality, not measurement parity, but collision frequency and event-score richness.
- Priority implication:
  pause nearby `C replaces weakest A/B` retries built from the current `trade_quality_score / confidence / positive_surprise_history / above_200ma` score family. If `C strategy revival` returns, it should do so with a genuinely richer event-grading source or fresh forward evidence showing that same-day C-vs-A/B slot collisions occur often enough to matter. Do not treat this result as permission to sweep more tiny score-margin variants.

### 11.12 Strict AND-combined risk-state gross haircut: rejected

- `exp-20260423-014` tested the most direct doctrine-authorized follow-up to the rejected broad OR-based stress template: keep the deployment shape simple, but replace the over-firing disjunctive state with a narrow conjunctive weak-tape state.
- Result summary:
  - runtime-only sizing variants left the accepted deterministic A+B stack unchanged except for one day-level allocation rule:
    - define `stress_strict = breadth_above_200 <= 0.55 AND spy_pct_from_ma <= -0.02`
    - on `stress_strict` days only, multiply gross `risk_pct` by `0.5x` or `0.25x`
  - the trigger audit confirmed that the AND semantics fixed the over-fire problem from `exp-20260423-013`:
    - late strong: `2 / 123` days (`1.6%`)
    - mid weak: `8 / 127` (`6.3%`)
    - old thin: `17 / 138` (`12.3%`)
  - deterministic late / mid / old snapshot replay then showed:
    - `0.5x`:
      - late strong: strict null `EV 0.8470 -> 0.8470`
      - mid weak: strict null `EV 0.1255 -> 0.1255`
      - old thin: mild improvement `EV 0.0109 -> 0.0126`, `maxDD 9.03% -> 8.79%`
    - `0.25x`:
      - late strong: strict null `EV 0.8470 -> 0.8470`
      - mid weak: strict null `EV 0.1255 -> 0.1255`
      - old thin: mild improvement `EV 0.0109 -> 0.0135`, `maxDD 9.03% -> 8.67%`
- Mechanism implication:
  the missing edge was not merely "use AND instead of OR." Conjunctive breadth-plus-index-pressure semantics do seem better at isolating true weak tape, but a one-layer gross haircut is still too blunt to turn that detection into stable portfolio alpha. In the stronger and middle windows the state either occurs too rarely or does not alter the marginal trades that matter; in the oldest weak window it helps a little, but not enough to qualify as a general repo-level improvement.
- Priority implication:
  upgrade the doctrine from "broad OR stress is too wide" to a more precise constraint:
  1. `risk-state detection` and `risk-state action` are separate questions,
  2. the simple action family `single-stage gross haircut on weak-tape days` is now exhausted for the current breadth-plus-SPY-pressure state.

Do not do next:

- do not reopen nearby `0.5x / 0.25x / 0.0x` gross-risk sweeps on the same `breadth_above_200 + spy_pct_from_ma` state
- do not treat the old-window-only improvement as permission to promote a repo-level always-on stress haircut

If this branch returns, it should do so only in one of two sanctioned forms:

1. an explicit two-stage design: use the strict weak-tape detector only as stage one, then apply a sleeve-specific action (for example breakout-only de-risking) as stage two
2. a genuinely richer weak-tape state that adds a third independent context source such as volatility or flow, rather than another nearby breadth / SPY threshold permutation

### 11.13 Strict weak-tape detector -> breakout-only action: rejected as vacuous

- `exp-20260424-002` tested the first sanctioned follow-up from `11.12`: keep the strict weak-tape detector unchanged, but replace the blunt gross haircut with a sleeve-specific stage-two action that only de-risked `breakout_long`.
- Result summary:
  - runtime-only sizing variants used the same `stress_strict` detector from `exp-20260423-014`:
    - `breadth_above_200 <= 0.55 AND spy_pct_from_ma <= -0.02`
  - on `stress_strict` days only, screened two breakout-only actions:
    - `breakout 0.25x`
    - `breakout 0.0x`
  - deterministic late / mid / old snapshot replay was a complete null:
    - late strong: `EV 0.8470 -> 0.8470`
    - mid weak: `EV 0.1255 -> 0.1255`
    - old thin: `EV 0.0109 -> 0.0109`
  - the reason was structural, not another multiplier miss:
    - `stress_days_hit_during_sizing = 0` in all three windows
    - `breakout_signals_haircut = 0` in all three windows
- Mechanism implication:
  the problem is no longer just "what action should weak-tape detection trigger?" For this specific `breadth + SPY-pressure` state, the detector does not overlap with actual breakout sizing opportunities in the fixed replay eras. So even a sleeve-specific second stage remains vacuous. This is a different failure mode from the earlier broad OR stress template: not over-firing, but zero useful intersection with the target sleeve.
- Priority implication:
  tighten the doctrine again:
  1. a meta-state can be statistically clean at the day level and still be useless for allocation if it almost never intersects the candidate sleeve it is meant to control
  2. future meta-allocation work should prefer states measured on candidate days or tied directly to the active cohort, not only broad market days

Do not do next:

- do not keep trying nearby breakout multipliers on the same `stress_strict` detector
- do not assume every weak-tape day-level state is a useful allocation key for breakout if the candidate-day overlap is zero

If this branch returns, it should require either:

1. a state defined on candidate days or candidate cohorts, not just broad market days, or
2. a different sleeve target whose candidate days actually overlap with this strict weak-tape regime

### 11.14 Strict weak-tape detector -> trend-only action: rejected as vacuous

- `exp-20260424-003` tested the other sanctioned follow-up after `11.13`: if the strict weak-tape detector had zero overlap with breakout sizing, maybe the useful sleeve target was `trend_long` instead.
- Result summary:
  - kept the same day-level detector fixed:
    - `breadth_above_200 <= 0.55 AND spy_pct_from_ma <= -0.02`
  - screened trend-only stress-day actions:
    - `trend 0.5x`
    - `trend 0.25x`
  - deterministic replay again stayed a complete null:
    - late strong: `EV 0.8470 -> 0.8470`
    - mid weak: `EV 0.1255 -> 0.1255`
    - old thin: `EV 0.0109 -> 0.0109`
  - overlap audit matched the outcome:
    - `stress_days_hit_during_sizing = 0` in all three windows
    - `trend_signals_haircut = 0` in all three windows
- Mechanism implication:
  the failure is now broader than one sleeve choice. In the current fixed replay eras, this strict day-level weak-tape detector does not intersect the actual A+B sizing surface at all. So the problem is not "maybe use trend instead of breakout"; it is that this whole family of broad market-day stress states is too detached from candidate formation to be useful as a meta-allocation key for the accepted stack.
- Priority implication:
  consider the family `broad day-level weak-tape states keyed only off market breadth + index pressure` exhausted for current A+B allocation work. If meta-allocation continues, it should shift toward:
  1. candidate-day or candidate-cohort states, or
  2. richer event / flow / composition context tied directly to when signals actually exist.

Do not do next:

- do not keep swapping sleeve targets (`breakout`, `trend`, gross) on the same strict day-level detector
- do not interpret the clean detector as useful just because it matches macro-stress intuition; if it never touches the decision surface, it has no allocation value

### 11.15 Candidate-day healthy-tape breadth proxy -> one-way trend boost: rejected

- `exp-20260424-004` tested the first doctrine-compliant follow-up after `11.14`: move off broad market-day states and onto a real candidate-day state, but keep the deployment shape deliberately simple.
- Result summary:
  - runtime-only sizing variants derived `offense_minus_defense_breadth` directly from replayable sector-group momentum breadth inside the fixed snapshots:
    - offense sectors: `Technology`, `Communication Services`, `Consumer Discretionary`, `Industrials`, `Financials`
    - defense sectors: `Commodities`, `Healthcare`, `Energy`, `Consumer Staples`, `Utilities`
    - state: `offense_minus_defense_breadth >= 0.15`
  - on those candidate days only, screened `trend_long` boosts of `1.25x` and `1.5x`
  - the state was active enough to be informative, not vacuous:
    - late strong: `17` boost-eligible days, `5` actual sizing hits
    - mid weak: `48` boost-eligible days, `11` sizing hits
    - old thin: `40` boost-eligible days, `9` sizing hits
  - but the deployment shape still failed:
    - `1.25x`: late `EV 0.8470 -> 0.8304`, mid `0.1255 -> 0.1252`, old `0.0109 -> 0.0065`
    - `1.5x`: late `EV 0.8470 -> 0.8205`, mid `0.1255 -> 0.1433`, old `0.0109 -> 0.0061`
- Mechanism implication:
  candidate-day state alignment alone is not enough if the action is still a monotone one-way trend bonus. This proxy does identify a real subset of decision days, but boosting trend on that subset either stays null or borrows too much from the strong / old windows to qualify as stable allocation alpha.
- Priority implication:
  downgrade the family `cheap candidate-day healthy-tape breadth proxy -> one-way trend boost`. If healthy-tape routing returns, it should not come back as another nearby threshold or multiplier sweep on the same monotone action shape.

### 11.16 Candidate-day QQQ-vs-SPY relative momentum -> one-way trend boost: rejected

- `exp-20260424-005` tested a second lightweight candidate-day routing proxy from the same doctrine bucket, but with a simpler and more replayable state:
  - `qqq_minus_spy_mom10 > 0`
- Result summary:
  - again screened `trend_long` boosts of `1.25x` and `1.5x` on candidate days only
  - the state was frequent enough to be meaningful:
    - late strong: `59` boost-eligible days, `11` sizing hits
    - mid weak: `99` boost-eligible days, `15` sizing hits
    - old thin: `65` boost-eligible days, `13` sizing hits
  - but the cross-window shape was still wrong:
    - `1.25x`: late `EV 0.8470 -> 0.8318`, mid `0.1255 -> 0.1420`, old `0.0109 -> -0.0003`
    - `1.5x`: late `EV 0.8470 -> 0.8222`, mid `0.1255 -> 0.1773`, old `0.0109 -> 0.0004`
  - the middle window improved more strongly than in `11.15`, but only by turning the old thin window negative on return and worsening the dominant late-strong tape
- Mechanism implication:
  the problem is not just that `offense_minus_defense_breadth` was too bespoke. Even a simpler healthy-tape proxy with much higher activation frequency fails when expressed as "trend gets more risk." The bottleneck is now the action family, not only the state family.
- Priority implication:
  upgrade the doctrine again:
  1. `candidate-day state exists` is necessary but not sufficient,
  2. the action family `single-proxy -> one-way trend boost` is now locally exhausted for current A+B meta-allocation work.

Do not do next:

- do not keep sweeping nearby `offense_minus_defense_breadth` thresholds for more `trend_long` bonus variants
- do not keep sweeping nearby `qqq_minus_spy_mom10` thresholds or stronger `trend_long` bonus multipliers
- do not treat the middle-window improvement as permission to promote a repo-level healthy-tape trend bonus

If healthy-tape routing returns, it should require one of:

1. an explicit two-sided sleeve-routing rule rather than another monotone trend-only action
2. a richer candidate-cohort discriminator tied to actual same-day opportunity composition, not only a cheap day-state proxy
3. fresh forward evidence showing a new present-tense routing problem that the current fixed windows do not expose

### 11.17 Candidate-day OMDB -> two-sided breakout-to-trend routing: rejected

- `exp-20260424-006` tested the first direct follow-up authorized by `11.16`: keep the replayable healthy-tape OMDB proxy fixed, but replace the rejected one-way trend bonus with explicit cross-sleeve routing.
- Result summary:
  - reused the same candidate-day state from `11.15`:
    - `offense_minus_defense_breadth >= 0.15`
  - on those candidate days only, screened three explicit sleeve-routing actions:
    - `rot_bk025_tr125`
    - `rot_bk000_tr125`
    - `rot_bk025_tr150`
  - this time the state was not blocked by present-tense scarcity:
    - late strong: `17` trigger days, `7` sizing hits
    - mid weak: `48` trigger days, `16` sizing hits
    - old thin: `40` trigger days, `15` sizing hits
  - but the cross-window shape was decisively wrong:
    - late strong baseline `EV 0.8463`
      - `rot_bk025_tr125 -> 0.7092`
      - `rot_bk000_tr125 -> 0.6777`
      - `rot_bk025_tr150 -> 0.7007`
    - mid weak baseline `EV 0.0898`
      - improved to `0.1031 / 0.1036 / 0.1187`
    - old thin baseline `EV 0.0077`
      - improved to `0.0371 / 0.0542 / 0.0367`
- Mechanism implication:
  the earlier excuse "maybe the promising two-sided action just lacked primary-window triggers" is now gone. This cheap healthy-tape day-state does trigger in the dominant late-strong tape, and when it does, the two-sided breakout-to-trend rotation materially damages EV. That means the failure is not only the old monotone action family; it is also that this day-state proxy is too crude for sleeve routing and steals capital from valuable breakout continuation in the current tape.
- Priority implication:
  upgrade the doctrine again:
  1. `cheap candidate-day healthy proxy -> one-way trend boost` is exhausted,
  2. `cheap candidate-day healthy proxy -> two-sided breakout-to-trend routing` is now also locally exhausted.

Do not do next:

- do not keep sweeping nearby OMDB thresholds for more breakout/trend routing pairs
- do not treat the weaker-window improvement as permission to promote repo logic while the late-strong tape loses `16-20%` of EV
- do not assume "two-sided action" is the missing ingredient if the state itself is still a cheap day-state proxy

If meta-allocation returns, it should require one of:

1. a richer candidate-cohort discriminator tied to same-day opportunity composition rather than a cheap day-state breadth proxy
2. a new present-tense routing problem observed in forward data
3. a different alpha branch entirely, rather than another local retry inside the OMDB / QQQ-SPY healthy-tape router family

### 11.18 Residual breakout Industrials cohort cut: rejected

- `exp-20260424-007` tested the next genuinely new unblocked branch after the cheap candidate-day router family was exhausted: stop searching for another market/day proxy, audit the *current accepted stack* directly, and see whether one narrow residual strategy+sector pocket still explains the remaining weak-window drag.
- Result summary:
  - a post-stack deterministic residual-cohort audit singled out `breakout_long | Industrials` as the only remaining sector-only pocket with at least `4` trades across the fixed late / mid / old windows and losses in `2/3` windows
  - runtime-only sizing variants then screened the obvious minimal actions on that pocket alone:
    - `0.25x`: late `EV 0.8470 -> 0.7155`, mid `0.1255 -> 0.1304`, old `0.0109 -> 0.0140`
    - `0.0x`: late `EV 0.8470 -> 0.6729`, mid `0.1255 -> 0.1711`, old `0.0109 -> 0.0155`
  - trigger counts confirmed the state was real rather than vacuous:
    - late strong: `1` eligible breakout-Industrials signal
    - mid weak: `3`
    - old thin: `1`
- Mechanism implication:
  the residual-cohort audit was directionally right about *where* some weak-window pain still lives, but another coarse strategy+sector haircut is still too blunt a deployment shape. The single late-strong Industrial breakout carries enough convexity that removing the whole pocket costs more present-tense EV than the weak-window repair earns back. In other words, even after the accepted stack changed, the remaining breakout leak is not recoverable by "one more sector bucket" alone.
- Priority implication:
  tighten the doctrine again:
  1. do not reopen nearby `breakout_long | Industrials` multiplier sweeps by default
  2. do not treat a post-stack residual sector audit as automatic permission for another sector-only cohort cut
  3. if allocation alpha continues, the next credible branch must add a richer conditioning source inside the remaining breakout pockets rather than re-running coarse sector-only pruning

### 11.19 Residual breakout Industrials 3%-4% gap pocket: accepted

- `exp-20260424-008` tested the doctrine-authorized richer follow-up to `11.18`: keep the same residual breakout pocket in focus, but add one explicit conditioning source inside it instead of retrying another sector-only haircut.
- Result summary:
  - runtime-only sizing variants kept the accepted A+B stack unchanged except for one narrower cohort rule:
    - `strategy == breakout_long`
    - `sector == Industrials`
    - `0.03 <= gap_vulnerability_pct < 0.04`
  - screened `0.25x` and `0.0x` only for that pocket across the deterministic late / mid / old snapshot trio
  - the accepted `0.0x` rule produced the right cross-window shape:
    - late strong: strict null `EV 0.8470 -> 0.8470`
    - mid weak: improved `0.1255 -> 0.1711`
    - old thin: improved `0.0109 -> 0.0155`
  - the weaker `0.25x` follow-up confirmed this was not another under-tightened cohort:
    - mid weak only `0.1255 -> 0.1309`
    - old thin `0.0109 -> 0.0150`
  - live-window sanity check after promotion matched the mechanism:
    - current primary window stayed unchanged (`EV 0.5725 -> 0.5725`)
    - the automatic secondary diagnostic improved (`EV 0.1300 -> 0.1802`, `sharpe_daily 1.37 -> 1.57`)

- Mechanism implication:
  the rejected sector-only Industrials cut was pointing at a real leak, but the leak lived in risk shape, not in the whole sector bucket. The surviving late-strong winner sat just outside the 3%-4% gap band, while the repeated weak-window losers clustered inside it. This is the same pattern that previously made the accepted `trend_long` moderate-gap Technology rule work: a narrow explicit cohort separation beats a coarser sector rule.

- Priority implication:
  upgrade `breakout_long | Industrials | 3%-4% gap_vulnerability -> 0x risk` into the accepted A+B stack. This also tightens the doctrine for the next breakout-allocation round:
  1. do not reopen `0.25x` vs `0.0x` inside this same pocket by default
  2. do not widen the lesson back into another sector-only Industrials haircut
  3. if breakout residual allocation work continues, require a genuinely new conditioning source beyond sector+gap rather than another nearby gap-band sweep

### 11.20 Residual trend Technology near-high pocket: accepted

- `exp-20260424-009` tested the next doctrine-compliant residual branch after `11.19`: stop retrying the rejected trend-ranking template, audit the surviving `trend_long` Technology trades directly, and ask whether the remaining drag now lives in a narrower entry-shape pocket rather than another stop-gap family.
- Result summary:
  - runtime-only sizing variants kept the accepted A+B stack unchanged except for one residual cohort rule:
    - `strategy == trend_long`
    - `sector == Technology`
    - `pct_from_52w_high >= -0.03`
  - screened `0.25x` and `0.0x` only for that near-high pocket across the deterministic late / mid / old snapshot trio
  - the accepted `0.25x` rule improved all three windows:
    - late strong: `EV 0.8470 -> 0.9195`
    - mid weak: `0.1711 -> 0.1933`
    - old thin: `0.0155 -> 0.0158`
  - the harsher `0.0x` follow-up confirmed that the pocket is real but less stable:
    - late strong: `0.8470 -> 0.9387`
    - mid weak: `0.1711 -> 0.2326`
    - old thin: `0.0155 -> 0.0148`
  - post-promotion live-window rerun stayed positive on the current primary window:
    - `EV 0.5725 -> 0.6419`
    - `sharpe_daily 3.17 -> 3.42`
    - `maxDD 3.29% -> 2.40%`

- Mechanism implication:
  the failed `trend_long` ranking work was pointing at a real shape issue, but not in the form "rank all trend candidates by pullback depth." After the accepted stack, the residual drag sits in near-high Technology trend entries, while the deeper-pullback Technology winners still carry the sleeve. This is a residual cohort allocation edge, not a revival of the rejected trend-ranking family.

- Priority implication:
  upgrade `trend_long | Technology | pct_from_52w_high >= -3% -> 0.25x risk` into the accepted A+B stack. This also tightens the doctrine for future trend residual work:
  1. do not reopen `0.25x` vs `0.0x` inside this same pocket by default
  2. do not reinterpret this as permission to restart global `trend_long` ranking by `pct_from_52w_high`
  3. if trend residual allocation work continues, require another conditioning source beyond `Technology + near-high` rather than another nearby pullback-threshold sweep

### 11.21 Candidate-cohort sleeve-average gap-difference router: rejected as vacuous

- `exp-20260424-010` tested the next doctrine-compliant meta-allocation branch after the cheap market/day-state family was exhausted: move the state all the way onto actual same-day candidate composition instead of broad market context.
- Result summary:
  - runtime-only sizing variants kept the accepted A+B stack unchanged except for one candidate-day breakout action:
    - compute `avg_gap_vulnerability(breakout candidates) - avg_gap_vulnerability(trend candidates)` from the same-day post-filter signal set
    - if that gap spread exceeded `0.01` or `0.02`, de-risk only `breakout_long` to `0.25x` or `0.0x`
  - the branch was replayable but effectively vacuous:
    - `0.01` threshold fired on only `1` late-strong sizing day and `0` mid/old days
    - `0.02` threshold fired on `0` sizing days in all three windows
  - every screened variant was a strict null:
    - late strong: `EV 0.9195 -> 0.9195`
    - mid weak: `EV 0.1933 -> 0.1933`
    - old thin: `EV 0.0158 -> 0.0158`

- Mechanism implication:
  candidate-day alignment alone is not enough if the discriminator is too weak to carve out a real decision surface. A sleeve-average gap spread sounds structurally cleaner than a broad day-state, but in the accepted A+B stack it barely intersects actual sizing days and therefore creates no allocation leverage. This is a different failure mode from the earlier over-broad healthy-tape proxies: not wrong-way routing, but almost no usable state.

- Priority implication:
  tighten the doctrine again:
  1. do not keep sweeping nearby sleeve-average gap-difference thresholds or breakout-only multipliers on this same state by default
  2. if candidate-cohort routing continues, require a richer discriminator tied to same-day opportunity composition than one cheap sleeve-average scalar
  3. the next credible unblocked branch should prefer either another residual cohort leak with a new conditioning source, or a genuinely richer candidate-cohort state rather than another vacuous scalar router

### 11.22 Residual trend Technology 2%-3% gap pocket: accepted

- `exp-20260425-001` tested the next doctrine-compliant residual branch after `11.20`: keep working inside the accepted A+B stack, but look for a different risk-shape leak inside `trend_long | Technology` rather than retrying near-high or ranking logic.
- Result summary:
  - runtime-only sizing variants kept the accepted A+B stack unchanged except for one narrower cohort rule:
    - `strategy == trend_long`
    - `sector == Technology`
    - `0.02 <= gap_vulnerability_pct < 0.03`
  - screened `0.25x` and `0.0x` only for that pocket across the deterministic late / mid / old snapshot trio
  - the accepted `0.0x` rule produced the right cross-window shape:
    - late strong: strict null `EV 0.9195 -> 0.9195`
    - mid weak: improved `0.1933 -> 0.2173`
    - old thin: improved `0.0158 -> 0.0179`
  - the softer `0.25x` follow-up confirmed the pocket was real but not fully fixed:
    - mid weak only `0.1933 -> 0.2094`
    - old thin `0.0158 -> 0.0173`
  - live-window sanity check after promotion stayed unchanged:
    - current primary window remained `EV 0.8102`
    - the null is acceptable because no qualifying present-tense trade reached sizing in that replay

- Mechanism implication:
  the accepted `near_high` rule did not exhaust the residual trend-Tech leak. A second risk-shape pocket remained in tighter-gap entries: the dominant strong tape carried at most one harmless qualifier, while the weaker tapes repeatedly lost money there. This is not a revival of the rejected trend-ranking family and not a reopen of the earlier 4%-6% gap pocket; it is another residual cohort allocation edge inside the same sleeve.

- Priority implication:
  upgrade `trend_long | Technology | 2%-3% gap_vulnerability -> 0x risk` into the accepted A+B stack. This also tightens the doctrine for future trend residual work:
  1. do not reopen `0.25x` vs `0.0x` inside this same `2%-3% gap` pocket by default
  2. do not resume broad nearby `Technology + gap` band sweeping as if this result re-authorized that family
  3. if trend residual allocation work continues, require a genuinely new conditioning source beyond the current near-high + gap pocket family

### 11.23 Residual breakout Communication Services near-high pocket: accepted

- `exp-20260425-002` tested the next doctrine-compliant breakout residual branch after `11.22`: stay inside the accepted A+B stack, but move away from the exhausted breakout `sector+gap` family and instead test a new entry-shape condition inside the remaining weak breakout sleeve.
- Result summary:
  - runtime-only sizing variants kept the accepted A+B stack unchanged except for one narrower breakout cohort rule:
    - `strategy == breakout_long`
    - `sector == Communication Services`
    - `pct_from_52w_high >= -0.03`
  - screened `0.25x` and `0.0x` only for that near-high pocket across the deterministic late / mid / old snapshot trio, plus current live primary/secondary sanity checks
  - the accepted `0.25x` rule produced the right cross-window shape:
    - late strong: strict null `EV 0.9195 -> 0.9195`
    - mid weak: improved `0.2173 -> 0.2405`, `sharpe_daily 1.73 -> 1.84`, `maxDD 2.80% -> 2.31%`
    - old thin: improved `0.0179 -> 0.0227`, `sharpe_daily 0.46 -> 0.51`, `maxDD 8.29% -> 8.28%`
  - live-window sanity checks matched the fixed-window shape:
    - current primary window stayed unchanged (`EV 1.2383 -> 1.2383`)
    - live secondary improved (`EV 0.2524 -> 0.2774`, `sharpe_daily 1.86 -> 1.97`, `maxDD 2.80% -> 2.31%`)
  - the harsher `0.0x` follow-up improved EV more, but degraded drawdown and failed to improve sharpe in the weak/live-secondary comparisons:
    - mid weak `maxDD 2.80% -> 3.03%`
    - live secondary `sharpe_daily 1.86 -> 1.85`, `maxDD 2.80% -> 3.03%`

- Mechanism implication:
  the remaining breakout leak was not asking for another coarse sector cut and not for another breakout gap-band retry. Inside the post-accepted stack, the weak names clustered in near-high Communication Services breakouts, while the dominant late-strong tape had zero qualifying names. This is a sector-plus-entry-shape allocation edge, not a reopen of the earlier breakout ranking or Industrials gap family.

- Priority implication:
  upgrade `breakout_long | Communication Services | pct_from_52w_high >= -3% -> 0.25x risk` into the accepted A+B stack. This also tightens the doctrine for future breakout residual work:
  1. do not reopen `0.25x` vs `0.0x` inside this same pocket by default
  2. do not reinterpret this as permission to restart broad breakout pullback ranking
  3. if breakout residual allocation work continues, require another genuinely new conditioning source beyond the current sector-plus-entry-shape pocket family

### 11.24 Residual breakout Financials 8-14 DTE pocket: accepted

- `exp-20260425-003` tested the next doctrine-compliant breakout residual branch after `11.23`: keep the accepted A+B stack intact, but move to a genuinely new conditioning source instead of another price-shape retry.
- Result summary:
  - residual audit matched executed trades back to signal-day fields and found the remaining breakout Financials drag was event-proximity:
    - late strong loser: `GS`, `days_to_earnings = 8`
    - mid weak loser: `COIN`, `days_to_earnings = 9`
    - old thin winner: `JPM`, `days_to_earnings = 62`
  - runtime-only sizing variants then screened one narrower cohort rule:
    - `strategy == breakout_long`
    - `sector == Financials`
    - `8 <= days_to_earnings <= 14`
  - the accepted `0.25x` rule produced the right cross-window shape:
    - late strong: `EV 0.9195 -> 0.9534`, `sharpe_daily 3.69 -> 3.73`, `maxDD 2.60% -> 2.38%`
    - mid weak: `EV 0.2405 -> 0.2774`, `sharpe_daily 1.84 -> 1.97`
    - old thin: strict null `EV 0.0227 -> 0.0227`
  - live and standard backtester sanity checks also stayed positive:
    - live primary runner: `EV 1.2383 -> 1.2748`
    - live secondary runner: `EV 0.2774 -> 0.3173`
    - standard backtester primary: `EV 0.8102 -> 0.8427`, `sharpe_daily 3.84 -> 3.88`, `maxDD 2.39% -> 2.35%`
    - standard backtester secondary: `EV 0.1998 -> 0.2318`, `sharpe_daily 1.82 -> 1.94`
  - the harsher `0.0x` follow-up improved the weak windows more, but failed stability by damaging the strong/live tapes:
    - late strong: `EV 0.9195 -> 0.8617`
    - live primary: `EV 1.2383 -> 1.1689`

- Mechanism implication:
  the remaining breakout Financials leak was not another coarse sector pocket and not another `gap / pct_from_52w_high` price-shape family. It was event-proximity risk: the weak breakouts sat inside the 8-14 DTE zone, while the old winner was far from earnings. This creates a new doctrine-approved breakout conditioning source that is still deterministic and replayable.

- Priority implication:
  upgrade `breakout_long | Financials | 8-14 DTE -> 0.25x risk` into the accepted A+B stack. This also tightens the doctrine for future breakout residual work:
  1. do not reopen `0.25x` vs `0.0x` inside this same pocket by default
  2. do not widen the lesson back into a sector-only Financials breakout cut
  3. if breakout residual allocation work continues, require another genuinely new conditioning source beyond the current price-shape and event-proximity pockets

### 11.25 Residual breakout Communication Services 3%-4% gap pocket: accepted

- `exp-20260425-004` tested the next doctrine-compliant breakout residual branch after `11.24`: stay inside the accepted A+B stack, keep the earlier Communication Services near-high rule intact, but switch to a new conditioning source instead of widening the existing entry-shape family.
- Result summary:
  - runtime-only sizing variants kept the accepted A+B stack unchanged except for one narrower breakout cohort rule:
    - `strategy == breakout_long`
    - `sector == Communication Services`
    - `0.03 <= gap_vulnerability_pct < 0.04`
  - screened `0.25x` and `0.0x` across the deterministic late / mid / old snapshot trio plus current live primary/secondary sanity checks
  - the accepted `0.25x` rule produced the right cross-window shape:
    - late strong: strict null `EV 0.9534 -> 0.9534`
    - mid weak: improved `0.2774 -> 0.2860`, `sharpe_daily 1.97 -> 2.01`, `maxDD 2.32% -> 2.32%`
    - old thin: improved `0.0227 -> 0.0322`, `sharpe_daily 0.51 -> 0.60`, `maxDD 8.28% -> 7.66%`
    - live primary: strict null `EV 1.2744 -> 1.2744`
    - live secondary: improved `0.3173 -> 0.3266`, `sharpe_daily 2.10 -> 2.14`, `maxDD 2.32% -> 2.32%`
  - the harsher `0.0x` follow-up improved return more in weaker windows, but failed stability by degrading sharpe and drawdown shape:
    - mid weak `sharpe_daily 1.97 -> 1.84`, `maxDD 2.32% -> 3.03%`
    - live secondary `sharpe_daily 2.10 -> 1.95`, `maxDD 2.32% -> 3.03%`
  - standard backtester sanity check after promotion matched the weak-window improvement:
    - primary window stayed unchanged at `EV 0.8427`
    - secondary diagnostic improved `EV 0.2318 -> 0.2410`, `sharpe_daily 1.94 -> 1.99`

- Mechanism implication:
  the earlier Communication Services near-high haircut did not exhaust the sleeve. A second leak remained in moderate-gap breakouts: weak tapes kept losing there, while the dominant strong/live-primary tapes still had zero qualifying names. This is a new sector-plus-risk-shape allocation edge, not a reopen of the earlier near-high pocket and not a permission slip for another coarse Communication Services cut.

- Priority implication:
  upgrade `breakout_long | Communication Services | 3%-4% gap_vulnerability -> 0.25x risk` into the accepted A+B stack. This also tightens the doctrine for future breakout residual work:
  1. do not reopen `0.25x` vs `0.0x` inside this same pocket by default
  2. do not widen this lesson back into another Communication Services sector-only haircut
  3. if breakout residual allocation work continues, require another genuinely new conditioning source beyond the current entry-shape, event-proximity, and Communication Services gap pockets

### 11.26 Macro defensive sleeve v1: rejected, but not falsified as a class

- `exp-20260425-005` intentionally moved away from narrow residual A+B mining and tested a genuinely different alpha class: a defensive/macro continuation sleeve.
- Result summary:
  - runtime-only experiment added `macro_defensive_long` candidates without changing production trading logic
  - eligible sectors: `Commodities`, `Healthcare`, `Energy`
  - activation required index pressure plus stock-level continuation:
    - SPY or QQQ below its 200-day moving average, or regime `NEUTRAL` / `BEAR`
    - stock above its 200-day moving average
    - positive 10-day momentum
    - positive 10-day relative strength vs SPY
    - `trend_score >= 0.55`
    - not within 3 days of earnings
  - tested three variants across the deterministic late / mid / old snapshot trio:
    - accepted A+B baseline
    - macro-only
    - A+B plus macro
  - the sleeve was not vacuous:
    - late strong generated 33 macro candidates / 3 executed macro trades
    - mid weak generated 19 macro candidates / 4 executed macro trades
    - old thin generated 96 macro candidates / 12-13 executed macro trades
  - however, the cross-window shape failed:
    - late strong: A+B plus macro regressed `EV 0.9534 -> 0.8967`
    - mid weak: A+B plus macro regressed `EV 0.2860 -> 0.2011`
    - old thin: A+B plus macro improved `EV 0.0322 -> 0.0631`
    - macro-only had negative total return in late strong and mid weak

- Mechanism implication:
  the intuition that macro / defensive continuation can matter is not dead. The old-thin window shows a real, replayable pocket where defensive/macro trades added return. The problem is that the first activation state was too blunt: `index_pressure + defensive sector + above200 + positive RS` fires in tapes where the existing A+B stack is still the better expression of risk. In those windows, macro becomes slot competition and performance drag, not diversification alpha.

- Priority implication:
  do not promote this first macro sleeve, and do not keep sweeping nearby `trend_score`, momentum, or 200-day thresholds inside the same static form. If macro alpha returns, it needs a more distinctive state definition, for example:
  1. explicit commodity / defensive leadership versus both SPY and QQQ
  2. weak or sparse A+B opportunity quality before macro is allowed to compete for slots
  3. macro exposure only when the existing trend / breakout sleeves are structurally unattractive, not merely when the index is under pressure
  4. a lower-risk overlay or separate sleeve budget so macro is not forced to win the same ranking contest as normal equity momentum

- Doctrine update:
  the user's overfitting concern is valid. New broad alpha classes are worth testing, but a broad label is not enough; it still needs a crisp, economically motivated activation state. This experiment rejects the first static defensive-continuation implementation, not the entire macro alpha family.

### 11.27 Macro defensive gating v2: rejected

- `exp-20260425-006` tested the direct follow-up to `11.26`: keep the same macro defensive entries, but only activate them when the normal A+B opportunity set looks weak and defensive-sector leadership is visible.
- Result summary:
  - runtime-only variants compared:
    - accepted A+B baseline
    - static macro v1 reference
    - loose gated macro v2
    - one strict gated macro v2 point
  - loose v2 state:
    - at least 2 defensive-sector leaders above 200MA and outperforming SPY over 10 days
    - same-day A+B opportunity weak by candidate count / confidence
  - strict v2 state:
    - at least 4 defensive leaders
    - average 10-day momentum > SPY 10-day return + 2%
    - same A+B weakness condition
  - first implementation briefly exposed a would-be ghost field: `above_50ma` is not currently produced by `feature_layer`; final measurement used only replayable fields
  - loose v2 was still too broad:
    - late strong regressed `EV 0.9534 -> 0.8967`
    - mid weak regressed `0.2860 -> 0.2052`
    - old thin improved `0.0322 -> 0.0631`
  - strict v2 avoided late/mid execution damage, but selected the wrong old-thin subset:
    - late strong: strict null `0.9534 -> 0.9534`
    - mid weak: strict null `0.2860 -> 0.2860`
    - old thin: damaged `0.0322 -> 0.0079`, with max drawdown rising `7.66% -> 10.70%`

- Mechanism implication:
  `A+B weak + defensive stock-local 10-day leadership` is not a sufficient macro regime switch. In loose form it is basically v1 wearing a nicer coat; in strict form it avoids bad eras but cuts the profitable old-thin macro subset. The missing ingredient is probably not another small threshold on leader count or 10-day relative strength.

- Priority implication:
  downgrade the family of macro gates based only on defensive-sector stock-local 10-day leadership plus A+B opportunity weakness. If macro is revisited, require a different information source or deployment shape:
  1. explicit commodity ETF / gold / rates / dollar leadership rather than only individual defensive-stock momentum
  2. cross-asset pressure that explains why macro should be paid, not just equity index pressure
  3. a separate macro budget or overlay so macro does not have to win the same slot contest as equity trend/breakout
  4. a post-entry/execution design for macro assets if the edge is lower Sharpe but diversifying

- Doctrine update:
  two consecutive macro-defensive experiments show the direction is interesting but not ready for production. Macro should not be abandoned, but the next valid macro experiment must change the information source or allocation shape. Do not keep sweeping nearby defensive leader counts, 10-day RS margins, or A+B weakness thresholds around this same gate.

### 11.28 Macro defensive overlay budget: rejected

- `exp-20260425-007` tested whether the macro sleeve's failure was mainly caused by slot competition with A+B.
- Result summary:
  - macro entry recipe stayed unchanged from `exp-20260425-005`
  - A+B signals kept priority
  - at most one macro signal was appended after A+B
  - overlay variants temporarily expanded `MAX_POSITIONS` by one in the experiment runner
  - macro risk was reduced after sizing:
    - `overlay_025`
    - `overlay_050`
  - the existing backtester has no native dual slot ledger, so this was an expanded-spare-slot approximation rather than a full production overlay engine
  - both variants failed multi-window stability:
    - `overlay_025`:
      - late strong `EV 0.9534 -> 0.9023`
      - mid weak `0.2860 -> 0.2231`
      - old thin `0.0322 -> 0.0258`
    - `overlay_050`:
      - late strong `0.9534 -> 0.8887`
      - mid weak `0.2860 -> 0.2152`
      - old thin only slightly improved `0.0322 -> 0.0335`

- Mechanism implication:
  slot competition was not the sole failure mode. Even when macro is small, capped to at most one appended candidate, and given an extra experimental slot, the current OHLCV-only defensive-stock continuation recipe still hurts the strong and rotation windows. The old-thin improvement at 0.5x is too small to pay for that instability.

- Priority implication:
  downgrade this entire macro implementation family:
  1. do not retry the same defensive-stock macro entry with another nearby risk multiplier
  2. do not retry the same recipe with another one-slot overlay variant by default
  3. do not treat the old-thin v1 improvement as proof that macro only needed a separate budget
  4. if macro returns, change the information source to explicit cross-asset context: GLD / SLV / commodity ETF leadership, rates / dollar proxies, or macro/news event context

- Doctrine update:
  after v1 static activation, v2 stock-local gating, and v3 overlay budget all failed, the current conclusion is stronger: the repo-visible OHLCV defensive-stock continuation recipe is not robust enough. The macro branch should pause unless the next experiment changes the input information source, not merely the gate or budget.

### 11.29 Cross-asset macro state audit: partial signal, insufficient alone

- `exp-20260425-008` tested the next doctrine-approved macro step: change the information source before trying another macro rule.
- Result summary:
  - this was an observed-only audit, not a strategy promotion test
  - available fixed snapshots already contain:
    - `GLD`
    - `SLV`
    - `SPY`
    - `QQQ`
  - desired but missing cross-asset proxies:
    - `TLT`, `IEF`
    - `UUP`
    - `USO`, `XLE`
    - `XLU`, `XLP`, `XLV`
  - the audit reran the static macro sleeve and annotated each macro trade with 20-day GLD / SLV / SPY / QQQ states
  - macro trade outcomes:
    - late strong: `3` macro trades, `-$782.49`, profit factor `0.0`
    - mid weak: `4` macro trades, `-$2,121.76`, profit factor `0.0`
    - old thin: `11` macro trades, `+$2,586.32`, profit factor `1.92`
  - cross-asset state finding:
    - late strong losers had GLD / SLV lagging SPY / QQQ, so a precious-metals leadership filter would likely block them
    - old thin winners occurred under stock pressure plus GLD / precious leadership
    - mid weak losers also often occurred under GLD leadership, so GLD / SLV alone cannot separate good macro from bad macro

- Mechanism implication:
  changing information source is directionally correct, but the currently available source is incomplete. Gold leadership helps distinguish late-strong false macro stress from real old-thin macro stress, but it does not distinguish mid-weak failed macro trades from old-thin successful ones. That difference likely needs rates, dollar, energy, and sector-ETF context, or a timing / overextension dimension.

- Priority implication:
  do not promote a `GLD leads SPY/QQQ` macro gate. The next credible macro experiment should first expand the snapshot information set, specifically:
  1. rates / duration: `TLT` or `IEF`
  2. dollar: `UUP`
  3. energy / commodity: `XLE` or `USO`
  4. defensive sector ETFs: `XLU`, `XLP`, `XLV`

- Doctrine update:
  this is an alpha-enabling data expansion, not generic infrastructure work. It directly addresses the now-demonstrated blocker: the repo cannot credibly test macro state with only stock-local defensive momentum plus GLD / SLV. If the missing ETF histories cannot be added, pause macro promotion and move to another independent alpha class.

### 11.30 Cross-asset proxy expansion and first macro gate: rejected, but mechanism improved

- `exp-20260425-009` filled the missing cross-asset sensor history in all three fixed snapshots:
  - rates: `TLT`, `IEF`
  - dollar: `UUP`
  - energy / commodity: `USO`, `XLE`
  - defensive sector ETFs: `XLU`, `XLP`, `XLV`
  - all downloads succeeded and existing ticker histories were not rewritten

- `exp-20260425-010` then tested the first full cross-asset macro gate:
  - macro entry recipe unchanged from `exp-20260425-005`
  - ETF proxies used as sensors only
  - A+B base signals generated from the original trading universe
  - gate:
    - `GLD_20d > SPY_20d`
    - `GLD_20d > QQQ_20d`
    - `min(SPY_20d, QQQ_20d) < 0`
    - `avg(TLT_20d, IEF_20d) <= 0`

- Result summary:
  - late strong:
    - baseline `EV 1.0402`
    - static macro reference `0.9805`
    - cross-asset gate `1.0402`
    - interpretation: gate successfully blocked all late-strong macro losers
  - mid weak:
    - baseline `0.3924`
    - static macro reference `0.2767`
    - cross-asset gate `0.2847`
    - interpretation: gate improved over static macro but still admitted damaging macro exposure
  - old thin:
    - baseline `0.0863`
    - static macro reference `0.1377`
    - cross-asset gate `0.1173`
    - interpretation: gate retained part of the old-thin macro benefit, but less than static macro

- Mechanism implication:
  cross-asset information is meaningfully better than stock-local defensive leadership. It completely fixed the late-strong false-positive problem and preserved some old-thin benefit. But it is still not sufficient: the gate admitted two mid-weak macro trades that kept the overall result below A+B baseline. The problem has narrowed from "macro state is invisible" to "mid-weak false positives need a second discriminator."

- Priority implication:
  do not promote this gate as-is, and do not start sweeping tiny `TLT/IEF` thresholds by default. The next macro step, if any, should be a trade-level false-positive audit:
  1. compare the two admitted mid-weak losers against the retained old-thin winners
  2. inspect whether the missing discriminator is timing / overextension, dollar behavior, energy vs gold split, or ETF-specific execution
  3. only then test one new condition

- Doctrine update:
  the macro branch is no longer blocked by missing cross-asset data. It is now blocked by false-positive discrimination. The next valid macro experiment must explain the remaining mid-weak false positives; otherwise pause macro and move to a different independent alpha class.

### 11.29 Residual trend Healthcare 6-12 DTE pocket: accepted

- `exp-20260425-008` returned to deterministic A+B residual allocation after the macro branch was downgraded. It did not revive C, did not touch LLM, and did not change entry/exit logic.
- Result summary:
  - runtime-only sizing variants tested one narrow cohort:
    - `strategy == trend_long`
    - `sector == Healthcare`
    - `6 <= days_to_earnings <= 12`
  - the accepted `0.0x` rule improved or preserved all fixed windows:
    - late strong: `EV 0.9534 -> 0.9831`, `sharpe_daily 3.73 -> 3.79`
    - mid weak: strict null `EV 0.2860 -> 0.2860`
    - old thin: `EV 0.0322 -> 0.0483`, `sharpe_daily 0.60 -> 0.72`, `maxDD 7.66% -> 5.60%`
  - standard post-promotion backtests reproduced the runtime result, and live sanity checks remained positive:
    - live primary: `EV 1.3109`, `sharpe_daily 4.23`
    - live secondary: `EV 0.3266`, `sharpe_daily 2.14`

- Mechanism implication:
  the existing `dte <= 3` hard block avoids immediate earnings-gap entries, but it did not exhaust event-proximity risk for Healthcare trend trades. A wider 6-12 trading-day pocket still carried unstable pre-event exposure after the accepted residual stack. This is an A+B sizing leak, not evidence that `earnings_event_long` is ready to return.

- Priority implication:
  upgrade `trend_long | Healthcare | 6-12 DTE -> 0x risk` into the accepted stack. Do not widen this into broad Healthcare DTE scans or sector+DTE grid searching by default; future residual allocation work still needs a clearly audited remaining loss cluster or a genuinely new conditioning source.

### 11.30 Residual Consumer Discretionary near-high 30-65 DTE pocket: accepted

- `exp-20260425-011` continued deterministic A+B residual allocation work after confirming that LLM soft ranking remains blocked by candidate-level replay coverage, C strategy revival remains mechanism-blocked, and the current macro defensive family should not be retried without new cross-asset inputs.
- Two probes were rejected before promotion:
  - `trend_long | Technology | 59-69 DTE | gap_vulnerability >= 4%` improved late/mid but damaged old_thin badly. It is a disguised retry of saturated Technology gap logic because it still cuts old Technology winners.
  - `breakout_long | Healthcare | pct_from_52w_high <= -10%` improved old_thin but slightly regressed mid_weak and had no late exposure. One-window improvement was not enough to promote.
- Accepted rule:
  - `strategy == trend_long`
  - `sector == Consumer Discretionary`
  - `30 <= days_to_earnings <= 65`
  - `pct_from_52w_high >= -0.01`
  - `risk_multiplier = 0.0`
- Fixed snapshot result:
  - late strong: `EV 0.9831 -> 1.0356`, `sharpe_daily 3.79 -> 3.88`
  - mid weak: strict null `EV 0.2860 -> 0.2860`
  - old thin: `EV 0.0483 -> 0.0567`, `sharpe_daily 0.72 -> 0.77`, `maxDD 5.60% -> 5.02%`
- Standard live-download sanity:
  - primary improved `EV 0.5953 -> 0.6432`, `sharpe_daily 3.40 -> 3.53`, `win_rate 62.5% -> 65.2%`
  - secondary stayed unchanged at `EV 0.2052`

- Mechanism implication:
  this pocket is not another broad sector cut and not another generic near-high rule. The residual leak appeared specifically in MCD-like Consumer Discretionary trend entries that were close to highs while still far enough from earnings that the existing immediate DTE block did nothing. The rule is a narrow capital-allocation haircut on a replayable cross-state sleeve.

- Priority implication:
  upgrade `trend_long | Consumer Discretionary | near-high | 30-65 DTE -> 0x risk` into the accepted stack. Do not widen it into all Consumer Discretionary trends, all near-high trend trades, or a sector+DTE grid search. If residual allocation work continues, require a genuinely new conditioning source or a fresh audited loss cluster; do not retry the rejected Technology DTE+gap or Healthcare deep-breakout probes.

### 11.31 Comms breakout DTE and Commodity near-high probes: rejected/deferred

- `exp-20260425-012` tested `breakout_long | Communication Services | 40-60 DTE` as a new event-proximity residual sleeve after the accepted near-high and moderate-gap Comms rules.
  - The 0.25x variant was directionally positive but too small: late strong was null, mid weak improved only `EV 0.2860 -> 0.2883`, and old thin improved `0.0567 -> 0.0618`.
  - The 0x variant damaged mid/old quality (`mid_weak sharpe_daily 2.01 -> 1.84`, `old_thin EV 0.0567 -> 0.0426`).
  - Mechanism implication: after the accepted Comms near-high and 3%-4% gap haircuts, this DTE sleeve is not a large enough remaining leak to justify another rule.

- `exp-20260425-013` tested `trend_long | Commodities | pct_from_52w_high >= -0.5%` as a different no-earnings exhaustion-risk sleeve.
  - The 0x point improved EV in late/mid and was null in old thin, including live sanity checks, but did not clear primary-window Gate 4 strength and reduced mid-window total return (`14.23% -> 13.05%`) while improving Sharpe.
  - Mechanism implication: Commodity near-high exhaustion is a watchlist idea, not an accepted production rule. It is especially risky to promote because earlier evidence justified exempting Commodities from the low-TQS haircut.

- Priority implication:
  1. do not retry the exact Comms breakout 40-60 DTE sleeve without a stronger independent discriminator
  2. do not sweep nearby Commodity near-high thresholds by default
  3. if Commodity residual work returns, require an explicit cross-asset/context reason rather than just proximity to highs
  4. the next A+B residual allocation experiment should start from a fresh audited loss cluster, not from another adjacent threshold around these two rejected/deferred pockets

### 11.32 Residual Technology breakout 26-40 DTE pocket: accepted

- `exp-20260425-014` started from a fresh residual loss audit after `11.31`, rather than retrying Comms DTE or Commodity near-high adjacent thresholds.
- Accepted rule:
  - `strategy == breakout_long`
  - `sector == Technology`
  - `26 <= days_to_earnings <= 40`
  - `risk_multiplier = 0.0`
- Fixed snapshot result:
  - late strong: strict null `EV 1.0356 -> 1.0356`
  - mid weak: `EV 0.2860 -> 0.3387`, `sharpe_daily 2.01 -> 2.38`, `maxDD 2.32% -> 2.06%`
  - old thin: `EV 0.0567 -> 0.0659`, `sharpe_daily 0.77 -> 0.83`
- Standard live-download sanity:
  - primary stayed unchanged at `EV 1.3593`, `sharpe_daily 4.28`
  - secondary reproduced the improvement at `EV 0.3387`, `sharpe_daily 2.38`

- Mechanism implication:
  this is not the rejected `trend_long | Technology | 59-69 DTE | gap >= 4%` family. The new pocket is breakout-only and event-proximity-only: it removed a mid/old Technology breakout leak while having zero exposure in the dominant late-strong tape.

- Priority implication:
  upgrade `breakout_long | Technology | 26-40 DTE -> 0x risk` into the accepted A+B stack. Do not widen this into all Technology breakouts, all Technology DTE sleeves, or another Technology gap/DTE scan. Future residual allocation work still needs a fresh audited loss cluster or a genuinely new conditioning source.

### 11.33 Residual Technology trend 44-64 DTE pocket: accepted

- `exp-20260425-015` tested the next residual Technology branch after the accepted breakout-only 26-40 DTE rule.
- Accepted rule:
  - `strategy == trend_long`
  - `sector == Technology`
  - `44 <= days_to_earnings <= 64`
  - `risk_multiplier = 0.25`
- Fixed snapshot result:
  - late strong: `EV 1.0356 -> 1.0402`, `sharpe_daily 3.88 -> 3.89`
  - mid weak: `EV 0.3387 -> 0.3548`, `sharpe_daily 2.38 -> 2.44`, `maxDD 2.06% -> 2.05%`
  - old thin: `EV 0.0659 -> 0.0716`, `sharpe_daily 0.83 -> 0.87`, `maxDD 5.02% -> 4.79%`
- Paired live-download sanity:
  - primary improved `EV 1.3593 -> 1.3646`, `sharpe_daily 4.28 -> 4.29`
  - secondary improved `EV 0.3387 -> 0.3555`, `sharpe_daily 2.38 -> 2.44`
- The `0x` variant was rejected despite improving late/mid because it damaged old_thin (`EV 0.0659 -> 0.0377`, `maxDD 5.02% -> 6.68%`).

- Mechanism implication:
  this is adjacent to, but not the same as, the rejected `trend_long | Technology | 59-69 DTE | gap >= 4%` idea. The rejected rule cut the 69-DTE APP winner and behaved like another saturated gap-family retry. The accepted sleeve is DTE-only, capped at 64 DTE, and stays partial-size because a full ban broke old_thin.

- Priority implication:
  upgrade `trend_long | Technology | 44-64 DTE -> 0.25x risk` into the accepted A+B stack. Do not widen this into all Technology trends, all Technology DTE sleeves, or another nearby DTE/gap scan. Future Technology residual work needs a fresh audited cluster outside the current accepted gap, near-high, breakout-DTE, and trend-DTE pockets.

### 11.34 Energy near-high probes: broad rejected, narrow deferred

- `exp-20260425-018` tested broad `Energy | trend/breakout | pct_from_52w_high >= -2%` residual sizing.
  - Result: rejected. The only exposed fixed window was late_strong, and both `0.25x` and `0x` damaged it materially (`EV 1.0402 -> 0.8043 / 0.6632`).
  - Mechanism implication: the CVX/XOM loss pair cannot be widened into a broad Energy near-high exhaustion rule; later Energy near-high exposure contains winners.

- `exp-20260425-019` narrowed the same idea to `Energy | trend/breakout | 15-25 DTE | pct_from_52w_high >= -2%`.
  - Result: promising but not promotable. The `0x` point improved late_strong (`EV 1.0402 -> 1.1603`, `sharpe_daily 3.89 -> 4.09`) but mid_weak and old_thin had zero qualifying exposure.
  - Mechanism implication: this may be a real event-proximity leak, but current evidence is only a two-trade same-day CVX/XOM cluster. That is not enough for production.

- Priority implication:
  1. do not retry broad Energy near-high de-risking
  2. do not promote the Energy 15-25 DTE near-high pocket until another non-overlapping or forward sample has qualifying exposure
  3. if Energy residual work returns, require either a fresh audited cluster or an independent discriminator beyond the same CVX/XOM 19-DTE pair
  4. sizing probes that depend on near-high state must read `conditions_met.pct_from_52w_high`, matching production `portfolio_engine`

### 11.35 Broad residual sector probes: rejected

- `exp-20260425-020` moved away from the rejected Energy near-high branch and tested fresh A+B residual cohorts visible in the post-stack trade log.
- Runtime-only probes:
  - `trend_long | Communication Services -> 0.25x / 0x`
  - `trend_long | Consumer Discretionary -> 0.25x / 0x`
  - combined `trend_long | Communication Services or Consumer Discretionary -> 0.25x`
  - TRIP sector completion from `Unknown` to `Consumer Discretionary`
- Result:
  - `trend_long | Communication Services -> 0.25x` improved only old_thin (`EV 0.0716 -> 0.0864`) and had zero late/mid exposure.
  - `trend_long | Consumer Discretionary` damaged old_thin materially (`EV 0.0716 -> 0.0392 / 0.0214`) and slightly hurt late at 0.25x.
  - the combined sleeve damaged old_thin versus baseline (`EV 0.0716 -> 0.0487`).
  - TRIP sector completion was a strict null on EV/trades across all fixed windows; it only changed attribution from `Unknown` to `Consumer Discretionary`.
- Healthcare breakout audit found a tempting deep-pullback discriminator, but it overlaps the already rejected `breakout_long | Healthcare | pct_from_52w_high <= -10%` family and was not promoted.

- Mechanism implication:
  the accepted residual stack is now resistant to broad sector-level trend cuts. Communication Services may still contain an old-thin weakness, but current evidence is one-window-only. Consumer Discretionary trend exposure is explicitly not a broad leak; widening from the accepted MCD-like near-high DTE pocket destroys surviving winners.

- Priority implication:
  1. do not retry broad `trend_long | Communication Services` or `trend_long | Consumer Discretionary` risk cuts
  2. do not treat TRIP's missing sector map entry as an alpha unlock without a separate reason; it was attribution-only in this run
  3. do not reopen Healthcare deep-breakout pullback without a genuinely new discriminator beyond `pct_from_52w_high <= -10%`
  4. the next deterministic A+B residual search needs a new information source or a truly fresh audited cluster, not another broad sector sleeve

### 11.36 Residual Healthcare breakout 20-65 DTE pocket: accepted

- `exp-20260425-021` tested a fresh Healthcare breakout event-distance residual sleeve after broad sector probes failed and after confirming that the old Healthcare deep-pullback idea should not be retried on `pct_from_52w_high` alone.
- Accepted rule:
  - `strategy == breakout_long`
  - `sector == Healthcare`
  - `20 <= days_to_earnings <= 65`
  - `risk_multiplier = 0.25`
- Fixed snapshot result:
  - late strong: strict null `EV 1.0402 -> 1.0402`
  - mid weak: `EV 0.3555 -> 0.3924`, `sharpe_daily 2.44 -> 2.59`
  - old thin: `EV 0.0716 -> 0.0863`, `sharpe_daily 0.87 -> 0.95`, `maxDD 4.79% -> 4.44%`
- Rejected variants:
  - `20-65 DTE -> 0x` improved less than 0.25x.
  - `20-70 DTE -> 0.25x` damaged late strong by cutting the 67-DTE LLY winner (`EV 1.0402 -> 0.8929`).
  - `50-65 DTE` had no mid-window exposure and was weaker evidence than 20-65.
- Mechanism implication:
  this is not the rejected Healthcare deep-breakout pullback family. The accepted rule uses event distance, not price distance, and stays partial-size because the adjacent 20-70 test shows Healthcare breakout winners still exist near the boundary.
- Priority implication:
  upgrade `breakout_long | Healthcare | 20-65 DTE -> 0.25x risk` into the accepted A+B residual allocation stack. Do not widen it into all Healthcare breakouts, `20-70 DTE`, or a sector+DTE grid search; future Healthcare residual work needs a fresh audited cluster or a genuinely new discriminator.

### 11.37 Commodity trend and Financials breakout broad probes: rejected

- `exp-20260425-022` tested whether the repeated SLV/IAU losses after the accepted stack meant `trend_long | Commodities` should be de-risked.
  - Result: rejected. `0.25x` improved only old_thin (`EV 0.0863 -> 0.0942`) but damaged late_strong (`1.0402 -> 0.8764`) and mid_weak (`0.3924 -> 0.3737`). `0x` improved old_thin more but still cut late/mid return materially.
  - Mechanism implication: commodity trend exposure still carries valuable convexity. The accepted commodity exception remains breakout-specific; trend losses are not enough evidence for a broad trend commodity haircut.

- `exp-20260425-023` tested whether the remaining `breakout_long | Financials` sleeve should be broadly de-risked after the accepted narrow Financials DTE haircut.
  - Result: rejected. `0x` improved mid_weak (`EV 0.3924 -> 0.4079`) but damaged old_thin (`0.0863 -> 0.0564`) and did not improve late_strong (`1.0402 -> 1.0289`).
  - Mechanism implication: broad Financials breakout de-risking mixes remaining losers with an old-thin winner; the already accepted event-distance rule should not be widened into a sector-wide breakout cut.

- Priority implication:
  1. do not retry broad `trend_long | Commodities` de-risking without a new discriminator that preserves late/mid convexity
  2. do not widen Financials breakout sizing beyond the accepted DTE sleeve
  3. future residual allocation work needs a genuinely new conditioning source or a fresh audited cluster, not another broad strategy+sector haircut

### 11.38 Healthcare trend late-DTE near-high probe: rejected

- `exp-20260425-024` tested a narrow leftover Healthcare trend pocket after the accepted Healthcare breakout 20-65 DTE rule:
  - `strategy == trend_long`
  - `sector == Healthcare`
  - `60 <= days_to_earnings <= 75`
  - `pct_from_52w_high >= -1%`
- Result:
  - `0.25x` was strict null in late_strong and mid_weak because there were zero qualifying signals.
  - `0.25x` improved only old_thin (`EV 0.0863 -> 0.0956`, `sharpe_daily 0.95 -> 1.00`).
  - `0x` damaged old_thin (`EV 0.0863 -> 0.0810`).

- Mechanism implication:
  the remaining Healthcare trend near-high late-DTE idea is not broad enough to promote. It is currently a one-window, one-qualifier observation, not a stable residual allocation edge.

- Priority implication:
  1. do not retry Healthcare trend late-DTE near-high de-risking without another non-overlapping or forward qualifying sample
  2. do not widen this into broad Healthcare trend or broad Healthcare DTE sizing
  3. accepted Healthcare residual allocation remains limited to `trend_long | 6-12 DTE -> 0x` and `breakout_long | 20-65 DTE -> 0.25x`
  4. the next residual allocation search needs a fresh audited cluster with exposure in at least two windows, or a genuinely new information source

### 11.39 QQQ beta sleeve failed; Technology trend exit width promising

- `exp-20260425-025` tested a new QQQ idle-slot sleeve that appended QQQ behind A+B signals and let it trade with the normal ATR target/stop model.
  - Result: rejected. Every QQQ trade-style variant damaged mid_weak, the window it was meant to help. Best mid_weak point still regressed `EV 0.3924 -> 0.2786`.
  - Mechanism implication: treating QQQ as just another ATR-bounded trade is not a solution. It adds exposure but cuts the beta sleeve into bad entries/exits.

- `exp-20260425-026` tested a research-only passive QQQ idle-cash overlay with no target/stop.
  - Result: rejected as a mid_weak solution. Some high-momentum overlay points improved late_strong and old_thin, but all tested variants damaged mid_weak.
  - Mechanism implication: current accepted stack is no longer under-exposed in mid_weak (`gross_slot_day_fraction` around `0.80`). The benchmark gap is not mainly idle cash.

- `exp-20260425-027` tested a different exit-alpha mechanism: widen only `trend_long | Technology` targets.
  - Result: promising but not promoted in this run.
  - `6.0 ATR` improved all three windows cleanly:
    - late_strong: `EV 1.0402 -> 1.1108`, return `26.74% -> 27.84%`
    - mid_weak: `EV 0.3924 -> 0.4030`, return `15.15% -> 15.38%`
    - old_thin: `EV 0.0863 -> 0.1121`, return `9.08% -> 10.01%`
  - `7.0 ATR` was best for mid_weak (`EV 0.4189`) and old_thin (`0.1272`) but slightly reduced late_strong return, so it is less clean as a promotion candidate.
  - `8.0 ATR` improved old_thin most but lost the mid_weak benefit, suggesting the useful range is around `6-7 ATR`, not "remove targets entirely".

- Priority implication:
  1. do not retry QQQ beta sleeves by merely changing the momentum threshold or risk multiplier
  2. secondary underperformance should now be framed as selective winner-truncation, especially Technology trend exits, not idle-cash beta starvation
  3. the next actionable experiment should implement `trend_long | Technology` target-width as a real single-causal-variable patch, probably starting at `6.0 ATR`, then rerun fixed snapshots and live sanity
  4. keep this separate from broad trend target widening, which was already rejected; the new evidence is sector-and-strategy-specific

### 11.40 Technology trend 6.0 ATR target: accepted

- `exp-20260425-030` promoted the deferred-positive Technology trend target-width idea into the production risk-enrichment path.
- Accepted rule:
  - `strategy == trend_long`
  - `sector == Technology`
  - `target_atr_mult = 6.0`
- Fixed snapshot result:
  - late_strong: `EV 1.0402 -> 1.1108`, `sharpe_daily 3.89 -> 3.99`, return `26.74% -> 27.84%`
  - mid_weak: `EV 0.3924 -> 0.4030`, `sharpe_daily 2.59 -> 2.62`, return `15.15% -> 15.38%`
  - old_thin: `EV 0.0863 -> 0.1121`, `sharpe_daily 0.95 -> 1.12`, return `9.08% -> 10.01%`
- Drawdown, trade count, and win rate did not deteriorate in the fixed windows.

- Two non-promoted probes were also recorded:
  - `exp-20260425-028`: high `regime_exit_score` de-risking was rejected because it helped at most one window and cut late_strong winners.
  - `exp-20260425-029`: generic ATR trailing stops were rejected because every trigger/offset variant regressed EV in all fixed windows.

- Mechanism implication:
  selective winner-truncation repair is currently more promising than more residual sector/DTE haircuts or generic trailing stops. The useful exit change is not "let every trend run"; it is specifically that Technology trend winners needed more target room after the accepted sizing stack.

- Priority implication:
  1. keep `trend_long | Technology | 6.0 ATR target` in the accepted stack
  2. do not widen this into broad trend target widening
  3. do not keep sweeping generic ATR trailing-stop trigger/offset pairs
  4. future exit work should start from another strategy/sector-specific winner-truncation audit or a fresh loss cluster, not from global exit mutations

### 11.40 Technology trend 6.0 ATR target: accepted

- `exp-20260425-028` promoted the strongest deferred-positive branch from `exp-20260425-027` into the production risk-enrichment path.
- Accepted rule:
  - `strategy == trend_long`
  - `sector == Technology`
  - `target_mult_used = 6.0 ATR`
  - all non-Technology trend exits and all breakout exits remain on the normal regime-aware profile
- Production-path fixed snapshot result:
  - late strong: `EV 1.0402 -> 1.1108`, `sharpe_daily 3.89 -> 3.99`, return `26.74% -> 27.84%`
  - mid weak: `EV 0.3924 -> 0.4030`, `sharpe_daily 2.59 -> 2.62`, return `15.15% -> 15.38%`
  - old thin: `EV 0.0863 -> 0.1121`, `sharpe_daily 0.95 -> 1.12`, return `9.08% -> 10.01%`
- Validation:
  - `python -m pytest quant/test_quant.py -q` passed: `284 passed`
  - production `quant/backtester.py` reproduced the runtime-screened `6.0 ATR` metrics on the fixed snapshots
- Mechanism implication:
  this confirms the prior QQQ beta sleeve failures were pointing at winner truncation, not idle-cash starvation. The edge is narrow: Technology trend winners needed more room, but broad trend target widening and entry-conditioned trend target widening remain rejected.
- Priority implication:
  keep `trend_long | Technology -> 6.0 ATR target` in the accepted stack. Do not widen this into all trend targets, do not continue sweeping 6-8 ATR by default, and do not treat it as evidence for another QQQ overlay. The next alpha search should look for a fresh mechanism or a fresh loss/winner-truncation audit outside this now-accepted sleeve.

### 11.41 Remaining trend-sector target-width extrapolation: rejected

- `exp-20260425-031` accepted one additional selective winner-truncation repair:
  - `trend_long | Commodities -> 7.0 ATR target`
  - late_strong improved `EV 1.1108 -> 1.3382`
  - mid_weak improved `EV 0.4030 -> 0.4182`
  - old_thin was strict null
  - Mechanism implication: Commodity trend exposure carried useful convexity; this was not the rejected Commodity trend de-risking family.

- `exp-20260425-032` then tested whether the same target-width idea should be extrapolated to the remaining trend sectors.
  - Consumer Discretionary 7.0 ATR improved only old_thin (`EV +0.0668`) and was null in late/mid.
  - Communication Services 7.0 ATR improved only old_thin (`EV +0.0261`) and was null in late/mid.
  - Financials target widening damaged both mid_weak and old_thin.
  - Energy target widening damaged late_strong.
  - Healthcare target widening was strict null.

- Mechanism implication:
  Technology and Commodities are currently the only accepted sector-specific trend target-width sleeves. The useful mechanism is not "all trend sectors need more room"; it is selective winner truncation in specific convex sleeves.

- Priority implication:
  1. do not keep sweeping sector-by-sector trend target widths by default
  2. do not promote Consumer Discretionary or Communication Services trend target widening from one-window old_thin evidence
  3. do not retry Financials or Energy trend target widening by only nudging 5-7 ATR values
  4. the next exit-alpha search needs either a fresh winner-truncation audit with exposure in at least two windows, or a genuinely new trade-specific hold-quality source

### 11.41 Commodity trend 7.0 ATR target: accepted

- `exp-20260425-031` continued the selective winner-truncation line outside Technology, after confirming LLM soft ranking remains blocked by candidate-level replay coverage.
- Accepted rule:
  - `strategy == trend_long`
  - `sector == Commodities`
  - `target_atr_mult = 7.0`
- Fixed snapshot result:
  - late_strong: `EV 1.1108 -> 1.3382`, `sharpe_daily 3.99 -> 4.30`, return `27.84% -> 31.12%`
  - mid_weak: `EV 0.4030 -> 0.4182`, return `15.38% -> 17.57%`, maxDD unchanged at `2.05%`
  - old_thin: strict null `EV 0.1121 -> 0.1121`
- Validation:
  - `python -m pytest quant/test_quant.py -q` passed: `285 passed`
  - production `quant/backtester.py` reproduced the fixed snapshot improvements after the real risk-enrichment patch
- Mechanism implication:
  the earlier rejected `trend_long | Commodities` de-risking branch should not be retried as a broad haircut. Commodity trend exposure is a convex sleeve; the leak was clipping winners, not allocating too much risk to the sleeve.
- Priority implication:
  keep `trend_long | Commodities -> 7.0 ATR target` in the accepted stack. Do not generalize this into all trend targets or another generic trailing-stop family, both of which remain rejected. The next exit-alpha search should start from a fresh winner-truncation audit outside Technology trend and Commodity trend.

### 11.42 Single-position cap 25%: accepted

- `exp-20260425-033` tested a capital-allocation hypothesis after the target-width branch stopped generalizing: the accepted A+B stack may be under-allocating to tight-stop winners because the 20% single-position cap binds before the intended risk budget is deployed.
- Accepted rule:
  - `MAX_POSITION_PCT = 0.25`
  - entries, exits, ranking, LLM responsibilities, C strategy, and existing cohort sizing multipliers remain unchanged
- Fixed snapshot result:
  - late_strong: `EV 1.3382 -> 1.5039`, return `31.12% -> 35.47%`, maxDD `2.37% -> 2.81%`
  - mid_weak: `EV 0.4182 -> 0.4773`, return `17.57% -> 20.31%`, maxDD `2.05% -> 2.47%`
  - old_thin: `EV 0.1121 -> 0.1310`, return `10.01% -> 11.39%`, maxDD `4.44% -> 4.56%`
- Rejected/deferred variants:
  - `15%` damaged all windows.
  - `30%` and `35%` improved late/mid further but gave back part of the old_thin improvement, so they were not promoted.
- Mechanism implication:
  the next useful allocation lever was not another slot-count experiment. It was the per-position cap binding on high-convexity tight-stop trades after the accepted sizing stack. The conservative 25% cap improves EV in all fixed windows while preserving trade count and win rate.
- Priority implication:
  keep `MAX_POSITION_PCT = 0.25` in the accepted stack. Do not keep sweeping 30-35% by default, and do not reinterpret this as permission to reopen global `MAX_POSITIONS` changes. Future capital-allocation work should look for another distinct binding constraint or a fresh residual audit.

### 11.43 Post-target continuation audit and breakout target-width screen: rejected

- `exp-20260425-034` audited all accepted-stack `exit_reason == target` trades after the 25% single-position cap.
  - All target exits combined did not justify a broad continuation rule:
    - late_strong: 13 target exits, post-10d avg `+2.03%`
    - mid_weak: 10 target exits, post-10d avg `-0.97%`
    - old_thin: 9 target exits, post-10d avg `+0.16%`
  - The strongest-looking pockets were `breakout_long | Energy` and `breakout_long | Commodities`, but they had thin and uneven window exposure.
  - `trend_long | Financials` target exits were consistently poor after exit, reinforcing that winner-continuation is not a universal target-exit property.

- `exp-20260425-035` converted the audit insight into a runtime-only target-width screen for breakout Energy and breakout Commodities.
  - `breakout_long | Energy | 5.0 ATR target` improved only late_strong (`EV 1.5039 -> 1.5346`) and had zero mid/old exposure.
  - `breakout_long | Commodities | 7.0 ATR target` improved mid_weak (`EV 0.4773 -> 0.5002`) but damaged late_strong (`EV 1.5039 -> 1.4242`) and increased late drawdown (`2.81% -> 3.85%`).
  - Combined Energy+Commodities widening damaged late_strong and was rejected.

- Mechanism implication:
  post-target continuation exists, but it is not stable enough to become a broad re-entry, hold-extension, or breakout target-width rule. The accepted winner-truncation repairs remain narrow: Technology trend, Commodity trend, and the 25% cap. Breakout target widening needs stronger evidence than a few target-exit continuation observations.

- Priority implication:
  1. do not promote post-target continuation or re-entry as a generic rule
  2. do not retry `breakout_long | Energy` target widening without a non-overlapping or forward sample with qualifying exposure
  3. do not retry `breakout_long | Commodities` target widening by only nudging 5-7 ATR values; it already trades off late vs mid
  4. the next alpha search should pivot to a fresh mechanism, or use post-target audit only as a diagnostic input, not as a direct rule template
