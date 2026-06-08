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
6. 对高潜力、生产可见的 default-off paper alpha，默认使用 **shared-paper-first**：第一次严肃实验就应实现共享 helper，同时覆盖 historical replay 和 daily default-off snapshot，再用它跑 Gate 1-4。private replay scout 只适合数据形态不确定或想法非常早期的低成本探索；即使结果正向，也只能记录为 lead，不能算 accepted alpha。

基础设施修复只能服务于策略实验，不能长期替代策略实验。若一项修复不能明显提升 alpha 假设的可验证性、生产可执行性、风险归因或数据质量，默认不应占据最高优先级。

---

## 3. 每次会话必须先读

开始任何改动前，先读取以下信息；若文件不存在，记录缺失并优先补齐最小可用版本。

```text
docs/backtesting.md
docs/alpha_context_pack.md
docs/current_state_snapshot.md
docs/agent_experiment_protocol.md
docs/iteration_analysis.md
docs/experiment_log.jsonl
docs/experiment_log_format.md
docs/production_backtest_parity.md
docs/alpha-optimization-playbook.md
docs/data_edge_context_layers.md
data/backtest_results_*.json
data/backtests/backtest_results_*.json
```

- `docs/backtesting.md` 是回测命令、标准窗口、基线口径、指标字段和多窗口验证的单一真相源。`AGENTS.md` 不重复维护这些细节，避免两个文件标准分歧。
- `docs/alpha_context_pack.md` 是默认短记忆入口：它压缩当前 alpha 优先级、冻结方向、近期高信号实验和 lesson-card 链接，避免每轮把冗长历史塞进 LLM 上下文。
- `docs/current_state_snapshot.md` 是默认短状态入口：它指向精确状态源，并总结最近 accepted/default-off 状态。冗长的 accepted-stack / experiment-consolidation 历史已归档到 `docs/archive/current_state_legacy.md`，仅在需要精确深档时按需读取，不再作为默认上下文；`docs/current_state.md` 现在只保留 dashboard 解析的 activation map 表。
- `docs/agent_experiment_protocol.md` 是 agent 做实验的操作入口和流程索引：先 reserve / claim 实验 ID，再按 Gate 1-4、parity、artifact、closeout 执行；它不替代本文件和各单一真相源。
- `docs/alpha-optimization-playbook.md` 是默认高价值优化方向、近期机制级启发、已证伪思路和优先级变化的单一真相源。`AGENTS.md` 不维护具体优化方向清单，只要求每轮策略实验先参考该 playbook。
- `docs/data_edge_context_layers.md` 是 passive intelligence、context accumulation、continuous ranking、tail diagnostics、meta research 与 attribution 工具的单一真相源。新增 context layer、ranking surface、diagnostics 或 attribution sidecar 时，必须同步更新该文档，而不是把工具说明散落在实验脚本里。
- `scripts/list_experiments.py`：看 registry 里的 proposed/claimed/running 实验
- `scripts/claim_experiment.py`：多代理并行时 claim ticket
- `scripts/judge_experiment.py`：before/after artifact 判定和生成日志草稿
- `quant/meta_research_engine.py`：研究历史/冻结方向/优先队列

每次开始前必须回答五个问题：

1. 本轮最值得测试的赚钱假设是什么？它属于 entry、exit、ranking、capital allocation、LLM event scoring 还是 risk allocation？它是否符合 `docs/alpha-optimization-playbook.md` 的当前高价值方向；若偏离，理由是什么？
2. 过去是否做过相同或近似实验？上次参数、窗口、失败原因是什么？
3. 这次只检验哪一个独立决策假设 / policy bundle？哪些只是为评估它所需的实现、parity、daily snapshot、ledger、live-realistic execution envelope 或测试？
4. 本次成功 / 失败的验收标准是什么？验收标准是否符合 `docs/backtesting.md`？
5. 如果失败，下一位代理能否仅靠仓库记录复现实验？

若无法回答第 2、3、4、5 点，禁止开始策略逻辑改动。

`single_causal_variable` / `changed_variable` 是历史字段名，真实含义应理解为**单一可归因决策假设**，不是“只能改一个代码参数”或“只能碰一个文件”。一个 accepted alpha 实验可以包含为了评估同一假设所必需的共享 helper、历史 replay、daily default-off snapshot、report/ledger wiring、parity 测试、live-realistic execution envelope 和 artifact/log 更新。禁止的是在同一实验里混入多个互相独立的 alpha 假设、事后调参、或用一个 ID 同时寻找 entry、exit、ranking、sizing 多个自由度。

实验规范默认走 **Lean Alpha Contract**：少填低价值表格，多写高价值判断。一次 alpha 实验最低只需要清楚留下四件事：

1. **假设推断**：为什么这个信息/机制应该赚钱，历史上相邻实验说明了什么，最可能失败在哪里；
2. **固定策略包**：本轮接受或拒绝的完整 policy bundle 是什么，哪些只是实现 / parity / daily output / execution envelope；
3. **可信测量**：使用哪些标准窗口、before/after 指标和生产一致性约束判断；
4. **复盘反思**：结果为什么发生，哪些近邻重试应禁止，下一步需要什么新证据。

不要为了补齐低价值字段而拆实验、延后 shared helper、延后 production-visible paper 输出或延后真钱执行包络；结构化字段能由工具默认时就默认，关键是推理和反思必须具体、可复现、可指导下一轮。

后续自动化应优先用 `scripts/experiment.py audit --lean-strict` 防回退：它检查高价值推断和复盘是否具体，而不是要求更多冗余字段；历史质量债只报告，不要求回填后再做新实验。`--lean` / `--lean-strict` 默认打印精简的 lean summary：唯一决定性字段是 `lean_quality_passed`（仅当某个 post-enforcement 实验存在 weak prediction quality 或 weak reflection 时才为 false，并触发 exit 2）。`missing_prediction` / `missing_calibration` 多为已关闭 ticket，仅作可见性提示，不阻断；legacy pre-enforcement 债务被折叠成计数。需要完整报告和顶层 `passed`（可能仅因历史债务为 false）时加 `--full`。

### 3.1 推荐启动工具

选择新的 `alpha_search` 方向前，优先运行或读取 meta research 报告：

```powershell
.\.venv\Scripts\python.exe quant\meta_research_engine.py --output data\meta_research_report_latest.json
```

该报告只用于研究队列排序，不是交易信号，也不能替代
`docs/backtesting.md`、`docs/current_state_snapshot.md`、必要时的
`docs/archive/current_state_legacy.md` 深档段落或 Gate 1-4。优先用它回答：

- 哪些 mechanism / trial family 历史上更值得继续；
- 哪些方向属于 `freeze_candidates`，重试前需要新证据；
- 本轮是否是近邻重复实验；
- 实验日志是否存在会降低结论可信度的数据质量警告。

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

对 high-potential default-off paper alpha，如果同一实验已经通过 shared helper 同时覆盖 historical replay 和 daily default-off snapshot，并且保持 `trade_enabled=False`、不改变 live/default orders、ranking、sizing 或 exits，可以在同一实验内保留为 accepted shared default-off helper；不必为了“paper 接入生产可见输出”再拆一轮。

真钱可执行性不是事后补丁。任何声称有机会进入 live 的 alpha 实验，都必须在本轮记录 live-realistic execution envelope：目标 notional / capital cap、流动性和滑点假设、组合挤出、最大持仓/行业/主题暴露、kill switch、订单语义、失败处理、以及这些约束是否已经进入 after-measurement。若这些约束已经在同一 accepted 实验里评估并保持不变，后续把 `trade_enabled` 从 `false` 切到 `true` 可以是 release checklist / config change，而不是新的 alpha 实验。若本轮没有评估真钱包络，则该结果只能算 accepted default-off，不算 live-ready；之后需要一个窄的 activation-envelope Gate 1-4 补足真钱约束，不能重新发明 alpha。

默认保留规则：

1. **强保留**：`expected_value_score` 明显提升，且 drawdown、尾部风险、trade count、survival rate 没有不可接受恶化。
2. **可保留**：`expected_value_score` 小幅提升或接近持平，但多数标准窗口表现改善，并且至少满足一项：复杂度下降、风险下降、生产 / 回测一致性提升、LLM / 数据归因质量提升。
3. **可条件保留**：改动主要修复测量偏差、数据缺口或生产执行问题，即使短期 EV 未明显提升，也可以保留，但必须标记为 `measurement_repair`，并说明它释放了哪个后续 alpha 实验。
4. **默认拒绝**：主目标下降、风险明显恶化、只在单一窗口变好、多数窗口退化、复杂度上升但收益证据不足，或无法归因到单一因果变量。

若未通过 Gate 4，必须回滚策略改动，并把失败实验写入 `docs/experiment_log.jsonl`。`pytest` 通过不能替代 Gate 4。
