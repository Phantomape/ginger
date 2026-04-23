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
