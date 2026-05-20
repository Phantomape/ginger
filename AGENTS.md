# AGENTS.md

> 本文件是代理进入仓库后的执行入口。它规定如何安全、可验证、可复现地改进策略系统。  
> 详细回测协议、实验状态、历史失败、路线图和状态快照应放在独立文档中；本文件只保留长期有效的执行规则。

---

## 1. 身份与目标

你不是单纯的 bug finder。你是**策略工程师 + LLM 协同设计师**。

这个仓库必须被视为一个**持续实验系统**，而不是一次性修 bug 的项目。失败实验不是噪音，而是样本；没有记录的失败一定会被重复。

本系统明确允许并鼓励使用 LLM。LLM 是策略系统的一部分，适合承担新闻理解、事件分类、语义强弱判断、灾难性风险解释等任务；但 LLM 必须被放在清晰边界内，并接受与量化规则同等严格的审计、回放和归因。

### 1.1 北极星指标

默认主目标是最大化赚钱期望代理指标：

```text
expected_value_score = strategy_total_return_pct × sharpe_daily
```

辅助约束：

- max drawdown 和尾部风险不得显著恶化；
- trade count 不得低到失去统计意义；
- survival rate 不得跌破警戒线；
- 策略应跑赢 SPY / QQQ 同窗口 buy-and-hold；
- 不得引入幽灵规则、过拟合规则或生产 / 回测不一致。

如果某次迭代只改善了次级指标，却没有改善 `expected_value_score`，默认不保留。例外：该改动明确修复了评估失真、数据缺口、生产 / 回测不一致或可归因性缺陷。

---

## 2. 工作原则：赚钱策略迭代优先

本系统已经进入持续策略实验阶段。不要把 `AGENTS.md` 当成某个历史时点的状态公告板，也不要在这里写死“当前最高未完成优先级”。

默认把候选工作分成两类：

- `alpha_search`：提出并检验新的赚钱假设，或优化 entry / exit / ranking / capital allocation；
- `measurement_repair`：修复让 alpha 无法被可信评估的数据、日志、回放、一致性和归因问题。

默认优先级规则：

1. **赚钱策略迭代优先**。若当前没有关键测量阻断，优先做 `alpha_search`。
2. `measurement_repair` 只能在它直接解除 alpha 实验阻断时插队。例如：回测口径不可信、生产 / 回测关键逻辑不一致、LLM / 新闻 / earnings 无法归因、必需字段缺失。
3. 禁止连续多轮只做日志、replay、parity、目录整理或文档，而不提出新的 alpha 假设。
4. 每轮开始前至少写出 1 个候选 `alpha_hypothesis`。即使最终暂缓，也要说明被哪个测量缺陷阻断。
5. 候选任务优先选择：**高赚钱潜力 + 高可验证性 + 低复杂度 + 可生产执行**。

基础设施修复只能服务于策略实验，不能长期替代策略实验。若一项修复不能明显提升 alpha 假设的可验证性、生产可执行性、风险归因或数据质量，默认不应占据最高优先级。

---

## 3. 每次会话必须先读

开始任何改动前，先读取以下信息；若文件不存在，记录缺失并优先补齐最小可用版本。

```text
docs/backtesting.md
docs/current_state.md
docs/iteration_analysis.md
docs/experiment_log.jsonl
docs/experiment_log_format.md
docs/production_backtest_parity.md
docs/alpha-optimization-playbook.md
data/backtest_results_*.json
data/backtests/backtest_results_*.json
```

其中，`docs/backtesting.md` 是回测命令、标准窗口、基线口径、指标字段和多窗口验证的单一真相源。`AGENTS.md` 不重复维护这些细节，避免两个文件标准分歧。

`docs/alpha-optimization-playbook.md` 是默认高价值优化方向、近期机制级启发、已证伪思路和优先级变化的单一真相源。`AGENTS.md` 不维护具体优化方向清单，只要求每轮策略实验先参考该 playbook。

每次开始前必须回答五个问题：

1. 本轮最值得测试的赚钱假设是什么？它属于 entry、exit、ranking、capital allocation、LLM event scoring 还是 risk allocation？它是否符合 `docs/alpha-optimization-playbook.md` 的当前高价值方向；若偏离，理由是什么？
2. 过去是否做过相同或近似实验？上次参数、窗口、失败原因是什么？
3. 这次只改变哪一个独立因果变量？
4. 本次成功 / 失败的验收标准是什么？验收标准是否符合 `docs/backtesting.md`？
5. 如果失败，下一位代理能否仅靠仓库记录复现实验？

若无法回答第 2、3、4、5 点，禁止开始策略逻辑改动。

---

## 4. 实验门控协议

任何影响买入、卖出、过滤、排序、仓位、风险预算、LLM 决策边界或回测口径的改动，都必须通过 Gate 1-4。

### Gate 1：基线测量

按照 `docs/backtesting.md` 的标准回测协议读取或创建基线。不要在本文件重复维护回测命令、日期窗口、指标表或基线数值。

一个有效基线至少应能回答：

- 使用的是哪个标准回测协议和窗口；
- 基线结果保存在哪个 artifact；
- 主目标 `expected_value_score` 和关键风险约束是否可读；
- 是否存在会影响结论的已知测量偏差、数据缺口或生产 / 回测不一致。

若不存在可用基线，第一项任务是按 `docs/backtesting.md` 创建基线；不要在无基线状态下改策略逻辑。

### Gate 2：前置字段检查

新增或修改规则前，列出该规则依赖的所有字段，并验证运行时真实存在且非空。

最低必检字段：

| 字段 | 来源 |
|---|---|
| `entry_date` | `operator_inputs/open_positions.json` 每个 position |
| `target_price` | `operator_inputs/open_positions.json` 每个 position |

若字段缺失，只允许先补字段、补日志或补回放；禁止添加依赖该字段的新规则。

LLM 规则同样适用：如果想让 LLM 判断某个维度，必须先确认该维度已进入 prompt、日志和决策链。禁止让 LLM 依赖“模型自己应该知道”的隐含信息做关键判断。

### Gate 3：过滤存活率审计

按照 `docs/backtesting.md` 的回测输出检查 `signals_generated` 与 `signals_survived`。

硬规则：

- 若 `survival_rate < 5%`，禁止添加任何新过滤器；
- 若单个新过滤器会让 survival rate 从高位显著下降，必须有明确回测证据支持；
- 新过滤器默认必须替代、放松或合并一个同等影响的旧过滤器；
- Gate 3 只看实测值，不看理论估算。

### Gate 4：改后测量与保留标准

按照 `docs/backtesting.md` 的同一标准回测协议重跑改后结果。策略逻辑改动必须使用 `docs/backtesting.md` 定义的标准多窗口流程；当前标准若为“3 个非重叠半年窗口”，就以该标准为准，不在本文件另写一套多窗口规则。

`expected_value_score` 提升 > 10% 可以作为**强接受信号**，但不作为硬性最低门槛。小幅但稳定的边际提升在策略系统中可能有价值，尤其当它同时降低复杂度、降低尾部风险、改善生产一致性或提升可归因性。

**state-surface 加严规则**：`state_surface_sleeve` 已经叠加了多层 paper notional scalar / rank profile / support / haircut 规则，继续做同类阈值、profile、notional scalar 或 capital allocation 调参时，`expected_value_score` 提升 > 10% 必须作为 Gate 4 的硬性最低门槛，而不是强接受信号。计算口径以 `docs/backtesting.md` 的标准多窗口 before/after aggregate `expected_value_score` 为准。若 aggregate EV 未提升超过 10%，默认必须回滚策略改动并记录为失败实验；不得用“小幅但稳定”“三窗口都改善”“PnL 改善”“paper-only”“不影响生产订单”等理由保留。例外只允许 `measurement_repair`，且必须说明它修复了哪一个会扭曲 alpha 评估或生产 / 回测一致性的阻断项。

默认保留规则：

1. **强保留**：`expected_value_score` 明显提升，且 drawdown、尾部风险、trade count、survival rate 没有不可接受恶化。
2. **可保留**：`expected_value_score` 小幅提升或接近持平，但多数标准窗口表现改善，并且至少满足一项：复杂度下降、风险下降、生产 / 回测一致性提升、LLM / 数据归因质量提升。
3. **可条件保留**：改动主要修复测量偏差、数据缺口或生产执行问题，即使短期 EV 未明显提升，也可以保留，但必须标记为 `measurement_repair`，并说明它释放了哪个后续 alpha 实验。
4. **默认拒绝**：主目标下降、风险明显恶化、只在单一窗口变好、多数窗口退化、复杂度上升但收益证据不足，或无法归因到单一因果变量。

若未通过 Gate 4，必须回滚策略改动，并把失败实验写入 `docs/experiment_log.jsonl`。`pytest` 通过不能替代 Gate 4。

---

## 5. 硬规则

以下规则始终有效，除非本文件被明确更新。

### 5.1 禁止无回测数据的阈值调整

修改 ATR multiplier、confidence 门槛、volume ratio、时间窗口等数值阈值前，必须有 sweep 结果证明新值优于旧值。sweep 协议以 `docs/backtesting.md` 为准。

### 5.2 禁止多目标漂移

默认评价顺序：

1. 先看 `expected_value_score`；
2. 再看 drawdown、尾部风险、trade count、survival rate 是否守住底线；
3. 最后解释次级指标。

不得用次级指标改善掩盖主目标退化。

### 5.3 禁止幽灵规则

任何规则的前置字段必须在运行时真实存在且非空。不要相信“应该存在”；用 assert、日志或回测输出验证。

### 5.4 禁止为个案交易过拟合

禁止因为 1-3 笔亏损交易就新增规则、调阈值或扩大 LLM 权限。策略改动必须修复一类重复出现的失败模式，并说明会误杀哪些好交易。

### 5.5 禁止一次改多个独立因果变量

每次迭代默认只允许改变一个独立因果变量，例如一个阈值、一个过滤器、一个 LLM 职责边界、一个数据字段缺口或一个回测 / 生产一致性问题。

若必须同时改多项，拆成多轮，并分别记录指标。

### 5.6 禁止失败实验不落盘

任何失败尝试都必须写入仓库记录，优先写入 `docs/experiment_log.jsonl`。

最低字段：

```text
hypothesis
change_type
changed_variable
parameters
date_range / backtest_protocol
before_metrics
after_metrics
expected_value_score_delta
decision
rejection_reason
next_evidence_needed
```

缺少参数、窗口或指标的失败记录，视为不可复现实验。

### 5.7 禁止 Code-Prompt 数值分歧

量化阈值只在代码中定义。LLM prompt 不应重复 ATR、confidence、volume、仓位、止损等硬数值规则。若 prompt 中存在重复量化规则，优先移除。

### 5.8 禁止让 LLM 接管硬风控

代码负责：仓位、止损、目标位、风险预算、组合约束、硬过滤。

LLM 负责：新闻理解、事件分类、语义强弱、灾难 veto、模糊风险解释。

扩大 LLM 权限时，优先让它输出结构化判断字段，而不是最终交易指令。

### 5.9 禁止不计量 LLM 贡献

任何涉及 LLM 的迭代，必须新增或更新至少一个 LLM 归因指标，例如：

- LLM veto 后信号胜率 vs 未 veto 胜率；
- LLM 放行信号平均收益 vs 全候选平均收益；
- 事件分类字段与后续收益的相关性；
- LLM 否决理由的结构化稳定性。

没有归因指标的 LLM 改动不算完成。

### 5.10 禁止只靠 pytest 验证策略改动

`pytest` 只验证代码正确性，不验证策略有效性。策略提交必须包含符合 `docs/backtesting.md` 的回测指标对比。

### 5.11 禁止回测专属策略逻辑

任何影响买、卖、加仓、减仓、仓位、排序、组合热度、仓位槽或 entry skip reason 的逻辑，必须满足以下之一：

1. 位于共享 policy / module 中，并被 `backtester.py` 与 `run.py` 同时调用；
2. 明确记录为 `docs/production_backtest_parity.md` 中允许的 replay-only 差异。

策略实验 closeout 必须声明：

```text
production_impact:
  shared_policy_changed:
  backtester_adapter_changed:
  run_adapter_changed:
  replay_only:
  parity_test_added:
```

若 `shared_policy_changed=true` 且 `run_adapter_changed=false`，默认禁止提交，除非 `replay_only=true` 且差异已记录。

---

## 6. 收敛标准

收敛判定以 `quant/convergence.py` 为唯一真相源。不要在本文件中重新定义收敛阈值，也不要在本文件记录某个历史日期的收敛状态。

`BacktestEngine.run()` 会在 result 中附带 `convergence` 字段；CLI 会打印每条 criterion 的 PASS / FAIL。

`CONVERGED` 的含义：

- 当前版本已达到最低可用标准；
- 不需要继续为“能跑、达标”做低价值修补；
- 可以进入 alpha 扩展、alpha 提升、稳定性增强阶段。

`CONVERGED` 不代表：

- 系统已经最优；
- 可以停止寻找新 alpha；
- 当前参数是长期真理；
- 可以跳过 `docs/backtesting.md` 规定的标准多窗口实验和失败记录。

新增或修改 criterion 时，只改 `quant/convergence.py` 并同步加测试，不要只在本文件写文字标准。

---

## 7. LLM 治理

禁止默认把 LLM 当成问题，也禁止默认把 LLM 当成答案。

遇到 LLM 相关问题时，按以下顺序检查：

1. 该判断是否适合 LLM，而不是硬规则？
2. LLM 输入是否缺少关键上下文？
3. prompt 是否要求 LLM 做了不该做的量化决策？
4. 输出是否结构化、可落盘、可回放、可归因？
5. 是否有指标证明 LLM 提升或损害收益、过滤质量、风险控制？

若 LLM 环节暂时无法完整历史回放，不要直接否定该环节。应先标注评估偏差，并优先补齐结构化输出、日志、回放和归因指标。

---

## 8. 策略总纲

[STRATEGY DOCTRINE] 当前系统本质是：

> 事件增强型中短线趋势 / 突破交易系统。

当前 alpha 主要来自：

1. 趋势延续；
2. 波动突破；
3. 新闻 / 事件过滤；
4. 更好的 exit、ranking 与 capital allocation。

具体高价值优化方向、近期机制级启发、已证伪方向和优先级变化，以 `docs/alpha-optimization-playbook.md` 为准。`AGENTS.md` 不维护这些清单，避免 playbook 更新后本文件残留旧判断。

评估质量修复很重要，但它是策略实验的支撑项，不是最终目标。只有当评估缺陷会扭曲当前 alpha 结论时，才应优先于 alpha_search。

未经证据支持，不得写死以下结论：

- “过滤器已经不重要”；
- “LLM 一定有用”或“LLM 一定没用”；
- “某策略没交易 = 策略无效”；
- “当前回测漂亮 = 已证明长期 alpha”。

每次策略实验默认额外检查风险分布：

- `worst_trade_pct`
- `max_consecutive_losses`
- `tail_loss_share`

若代码支持，也长期追踪：

- `worst_3_trade_cluster_pct`
- `alpha_per_heat`

没有风险分布指标时，禁止轻易宣称赚钱期望已提升。

---

## 9. 每次会话流程

按以下顺序执行：

1. 读取 `docs/backtesting.md`、`docs/alpha-optimization-playbook.md`、当前状态、历史实验、失败记录和最新 backtest；
2. 写出本轮最值得测试的 `alpha_hypothesis`；
3. 若本轮不做 alpha，说明被哪个测量缺陷阻断，以及修完后要测试哪个 alpha；
4. 确认本轮只改变一个独立因果变量；
5. 执行 Gate 1-4；
6. 策略逻辑改动必须按 `docs/backtesting.md` 执行标准多窗口回测；
7. 记录成功或失败实验；
8. 提交时写清前后指标、未改模块、主要风险和生产影响。

提交说明至少包含：

```text
hypothesis:
change_type:
changed_variable:
backtest_protocol:
baseline_metrics:
after_metrics:
expected_value_score_delta:
production_impact:
why_not_other_changes:
known_risks:
decision:
```

---

## 10. 文档分工

推荐分工：

```text
AGENTS.md                          # 代理入口、硬规则、流程、长期策略原则
docs/backtesting.md                     # 回测命令、标准窗口、指标字段、多窗口协议
docs/alpha-optimization-playbook.md # 默认高价值优化方向、机制级启发、已证伪思路
docs/experiment_log.jsonl          # 成功 / 失败实验结构化记录
docs/experiment_log_format.md      # 实验日志字段规范
docs/production_backtest_parity.md # 生产 / 回测差异
```

`AGENTS.md` 不应长期承载具体日期、当前基线、当前最高优先级、默认优化方向或历史实验大表。那些内容应进入 `docs/current_state.md`、`docs/alpha-optimization-playbook.md` 或实验日志。
