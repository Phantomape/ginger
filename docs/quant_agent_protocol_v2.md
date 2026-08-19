# Ginger V2 Quant Agent Protocol

> `AGENTS.md` 管通用做事方式，本文件管 V2 量化研究、实验和系统建设。
> 具体命令、阈值、当前状态和历史案例放在专项文档里，不在这里重复。

## 1. 目标和边界

V2 要做的不是一张好看的回测图，而是一套能还原决策现场的研究系统。它必须说清：当时知道什么、
看过哪些候选、为什么这样选、用了哪版数据和规则、承担了什么风险、实际执行了什么，以及后来学到了什么。

最重要的重置规则：

```text
V2 可以复用 V1 的代码、数据和失败教训，
但不能继承 V1 的股票名单、alpha 结论、策略资格、组合权重或晋级状态。
```

V1 是历史档案、代码仓库和回归对照，不是 V2 的无偏基准。V1 赢家进入 V2 时也只能是零权重、
`trade_enabled=false` 的挑战者。V2 先与 V1 并行，经过独立审核后才讨论切换。

## 2. 每轮从哪里开始

真实记录的优先级是：已提交代码和 schema、原始输入及哈希、实验 ticket/log shard/manifest/artifact、
append-only ledger，高于任何摘要和报告。派生 snapshot、dashboard 和大模型总结只负责导航。

每轮先读最小入口：

1. `AGENTS.md` 和本协议；
2. `git status`、未完成实验、最近一次 V2 运行结果；
3. `docs/v2/current_state.md`、`docs/v2/backlog.md`、`docs/v2/decision_log.jsonl` 和最近一份
   `data/v2/hourly_runs/` receipt；这些文件尚未建立时，由 M0 建立；
4. 当前任务直接涉及的专项文档、代码、schema 和证据文件。

不要每小时重读整个 V1 历史。查具体实验时读 `experiments/logs/<id>.json` 等分片，不要把 100MB 级派生总日志
整份塞进上下文。

发生冲突时，按“用户和系统指令 → `AGENTS.md` → 本协议 → 专项文档 → 摘要/历史说明”处理。
专项文档可以补细节，不能放宽 PIT、反泄漏、default-off 和真钱边界。

## 3. 不能破的规则

1. **不能事后挑名单。** `core` 是资金和风险政策，不是一张永久股票表。
2. **不能倒填资格。** 数据、股票、映射、策略、模型和 Skill 结论只能在 `known_at`、`eligible_as_of` 之后参与决策。
3. **不能只记赢家。** 结果出来前就冻结完整股票池、所有候选、入选和落选原因、被挤掉的替代项，以及 cash、SPY、QQQ 和 V1 对照。
4. **选候选时不能看答案。** 未来收益、PnL、MFE/MAE、结算结果和赢家标签不能进入候选生成或选择。
5. **不能一边考试一边改答案。** discovery、锁定 validation 和干净 forward 要分开；用过的评估窗口不能再修改同一个候选。
6. **数据接得上，不等于数据能用。** adapter、Skill 或官方来源都不能替代授权、时钟、修订和 PIT 审核。
7. **一次只验证一个可归因的决策假设。** 同一假设所需的 helper、replay、daily、parity 和测试可以一起做；不相关的 alpha 不能打包。
8. **换皮不算新证据。** 换阈值、字段、事件子类、表单编号、持有期或把旧源做 join，不能自动获得新实验。
9. **回放和日常运行共用决策逻辑。** 不能保留只在 backtester 里赚钱的规则。
10. **AI 自由文本不能直接交易。** AI 可以找线索、做语义判断和提假设，不能直接改订单、仓位、风险上限或可交易股票池。
11. **默认永远是关着的。** 用户单独批准前，V2 必须保持 `trade_enabled=false`，不得下单或调整真钱权限。
12. **没有好工作就不要硬做。** 做只读检查，记下 blocker 和定量重开条件，以 `no-op audit` 结束即可。

## 4. V2 的核心合同

### 4.1 数据和 PIT

每条决策数据至少记录：来源、原始身份和哈希、真正参与决策的标准化内容、时区、`observed_at`、
`published_at`、`known_at`、生效区间、修订版本、当时有效的 security 映射、使用授权和 schema 版本。

新鲜度看“决策会用到的内容”是否变化，不能只看抓取时间或带随机字段的原始响应哈希。交易日归属锚定
数据日历、冻结的 run date 或 broker session，不能拿进程壁钟日期代替。

| PIT 等级 | 可以做什么 | 最高结论 |
|---|---|---|
| `not_pit` | 不声称收益证据的诊断 | 无效 / reject |
| `research_pit` | outcome-blind 发现、冻结候选、private replay | `observed_only` lead |
| `canonical_pit` | 正式 Gate、default-off paper、晋级评估 | 按 Gate 结果决定 |

已知未来修订、幸存者名单、当前映射倒灌或未来复权进入决策输入时，必须标成 `not_pit`。本地哈希只能证明
测了哪份文件，不能证明历史当时真的拿得到它。详细口径看 `docs/research_pit_policy.md`。

### 4.2 股票池和策略

V2 股票池必须按当时信息生成，并用 append-only `UniverseEvent` 记录发现、准入、状态变化、原因、规则版本和
输入快照。系统要能回放任意一天的研究池、可交易池和 quarantine/retired 状态。没有可信历史 PIT 股票池时，
诚实标成 research-only，并从干净的 forward T0 开始。

所有环境共用一条决策链：

```text
EvidenceSnapshot -> CandidatePool -> RankedCandidate -> SignalDecision
-> RiskDecision -> OrderIntent -> Fill/Reject -> PositionState
-> SettledOutcome + ReplacementValue
```

每个策略提前冻结赚钱机制、数据面和 PIT 等级、entry/ranking/sizing/exit/cost 版本、持有期、容量、流动性、
反事实对照、重叠和集中度、失败条件、kill switch 与晋级条件。

### 4.3 AI Berkshire 和 Skill 路由

AI Berkshire 负责找机会、做研究、提出反证和持续跟踪，不负责直接交易。按当前问题选择最小够用的 Skill 组合：

| 任务 | 优先 Skill |
|---|---|
| 行业漏斗、质量初筛、供应链瓶颈 | `industry-funnel`、`quality-screen`、`bottleneck-hunter` |
| 公司、行业和管理层深研 | `investment-research`、`industry-research`、`management-deep-dive` |
| 财报、新闻和股价异动归因 | `earnings-review`、`news-pulse` |
| 组合复盘和买入后论文跟踪 | `portfolio-review`、`thesis-tracker`、`thesis-drift` |
| 美股/港股行情、期权、FINRA、SEC、宏观和日历数据 | `global-stock-data` |
| 财务数据获取和交叉验证 | `financial-data` |

执行时遵守：

- 不要把所有 Skill 都跑一遍；每轮最多一个**研究 Skill**，而且必须由当前 backlog 触发。
- `global-stock-data` 和 `financial-data` 属于取数/核验工具，不占研究 Skill 名额；只在本轮证据确实需要时调用。
- Skill 结论要落成结构化 `ResearchClaim`，至少包含来源、`as_of/known_at`、PIT 等级、置信度、反证条件、影响对象和下一步，不能只留散文。
- `global-stock-data` 优先取官方或一手来源，并对关键数字交叉验证；它能帮助接入数据，但不能证明使用授权、`canonical_pit`、历史可得性或 replay/daily parity。
- 当前行情不能倒填成历史证据，Skill 自带 adapter 也不能绕过候选冻结、novelty、Gate 或 default-off 边界。
- 指定 Skill 不可用时，记录缺失和替代方案；不得假装已经运行或编造输出。

发现阶段看不到候选结果；评估阶段可以解释已锁定结果，但不能改写实验或把赢家塞回同一候选池。

### 4.4 验证、晋级和执行

候选必须先登记、后看结果。冻结完整 trial panel，按时间分 discovery、validation 和未使用的 forward；
计算完整成本、现金约束、每日 MTM、强平、容量和滑点；同日期、同资本比较 cash、SPY、QQQ、V1 和被挤掉的候选。
同时检查集中度、beta/factor、相关性、回撤、expected shortfall、换手和机会成本。有完整选择面时计算 PSR/DSR，
合适时检查 PBO；语义或事件信号要做 placebo、permutation 或 negative control。

`expected_value_score = strategy_total_return_pct * abs(sharpe_daily)` 只保留为 V1 兼容指标。策略晋级前必须同时证明：

1. 扣除成本后，策略自己有正价值；
2. 资本不增加时，替换进组合后仍有增量价值。

`docs/backtesting.md` 当前的 V1 baseline 只做回归和机会成本对照，不能直接成为 V2 Gate-1 晋级锚。M3 要在 V2 动态
PIT 股票池和共享决策链上建立独立 Engine-0 baseline；在此之前，V2 候选最多停在 research/shadow。

晋级标签是 `research -> shadow -> qualified_paper -> pilot_ready -> limited_production_ready -> core_policy_eligible`，
旁路是 `quarantine / retired`。标签只表示证据成熟度，不会自动打开交易。

买卖、过滤、排序、仓位和风险规则必须放在共享 policy/helper。研究建议、`OrderIntent`、已提交、成交、拒单、撤单和
当前持仓分开记录。重复运行要幂等；字段缺失、价格过期、数据陈旧或非交易时段要 fail closed。监控至少覆盖数据/observer
零产出、输入内容身份、现金预留、fill drift、position trajectory drift 和 replay/daily parity。

## 5. 怎么选工作、怎么做实验

先处理未完成、失败或冲突中的工作。V2 建设期按下面的依赖顺序推进：

```text
identity -> clock -> source contract -> universe -> shared policy
-> validation -> forward wiring -> allocator -> activation review
```

M0-M5 先补当前里程碑的前置合同。干净基线和实验框架就绪后，默认优先 `alpha_search`；只有直接阻断可信评估、
forward 产出或 parity 的 `measurement_repair` 可以插队。

新 alpha 实验至少要有一条机器可查的新证据轴：真正独立的新数据源、真正不同的决策面/gate shape、达到已登记
重开条件的新增 settled forward 决策，或未饱和来源上确实没用过的新字段。join、换阈值、换响应、换子类、同日刷新和
重新讲旧机制都不算。

先免费检查授权、PIT、映射、密度、真实候选触达和 reopen 计数；不够就 park，不要烧实验 ID。例行 append、结算和摘要
刷新也不占新 ID；真正的管道故障修复才算 `measurement_repair`。纯文档整理不需要 ID；若同时改变机器 guard、测量口径
或策略行为，改变合同的部分必须走实验流程。

### Alpha 实验顺序

1. **Outcome-blind 合成：** 在同一 PIT 股票池比较机会成本；盘点 price、flow、derivatives、event、positioning、
   portfolio exposure 和 research digest；生成 1-3 个有经济因果链的假设，再选一个。
2. **写反证：** 给 lead 写 baseline、treatment、horizon、replacement comparator、PIT 等级、成功条件和 falsifier。
3. **冻结和登记：** 先冻结完整候选池、选择面、规则、输入哈希和验收标准，再用 `scripts/experiment.py new` reserve ID。
   不要手写 ID，也不要在 reserve 前创建 runner/artifact/实验 data。有并行工作时先 claim；疑似超时先查 open ticket，不能盲重试。
4. **完整实现：** 能同时用于 replay 和 daily 的信号默认 shared-paper-first。private replay 只适合 `research_pit`、数据形态
   不清楚或早期 scout；正向结果也只能是 lead。
5. **过 Gate：** Gate 1 锁定 baseline；Gate 2 查真实运行时字段；Gate 3 查生成数、存活数和存活率；Gate 4 用相同输入和窗口
   做 before/after。只有讨论 live eligibility 时才做 Gate 5。精确命令和阈值看 `docs/backtesting.md`。
6. **收尾：** 记录输入/代码身份、before/after 或 observed-only artifact、PIT、production impact、parity、结论、prediction
   calibration、禁止的近邻重试、定量重开条件、改动文件和复现命令。失败实验也要完整关闭。

单元测试通过不等于 alpha 成立。策略未过 Gate 4，就回滚本实验的策略改动并保留失败记录。每个实验的
`experiments/logs/<id>.json` 是真相源；`docs/experiment_log.jsonl` 是可重建派生视图，不能直接写。

## 6. V1 迁移和 V2 建设顺序

先做机器可读的 V1 资产清单，每项只能进一类：

| 分类 | 处理方式 |
|---|---|
| `reuse_directly` | 复用可靠的 PIT ledger、哈希、现金/MTM/成本修复、实验历史、parity helper 和测试 |
| `reuse_after_contract_upgrade` | 代码可用，但先补 V2 schema、授权、时钟、映射、失败语义或 parity |
| `migrate_as_zero_weight_challenger` | V1 策略和 sleeve 以零权重、default-off 挑战者重新参赛 |
| `legacy_diagnostic_only` | 静态股票池、事后权重、不完整 PIT 和只记赢家的结果只做诊断 |
| `retire` | 重复、失效、无法复现或不再支持的路径停止使用 |

迁移顺序看机制覆盖、合同完整度、授权、可回放性和工程依赖，不能按 V1 历史收益排名。

建设顺序：M0 定规则/T0；M1 身份、时钟、数据合同；M2 动态 PIT 股票池；M3 共享 SDK 和干净基线；M4 AI 研究系统；
M5 科学实验框架；M6 零权重迁移 V1；M7 forward 竞赛；M8 组合分配器；M9 提交 pilot 审核材料。完成 M9 也不自动交易。

M0-M1 至少落下 V1 资产清单、偏差登记表、T0、V2 state/backlog/decision log/hourly receipt，以及
`SourceContract`、`EvidenceRecord`、`UniverseEvent`、`ResearchClaim`、`HypothesisCandidate`、`CandidatePool`、
`DecisionRecord`、`OrderIntent`、`SettledOutcome`、`ReplacementValue` 的初始 schema。先补 schema 校验、append-only 和
幂等测试，再进入 M2。

## 7. 每小时怎么执行

每轮只做一个能验证的工作单元：

1. 看状态、backlog、上次 receipt、open experiment、测试失败和 git status；
2. 继续未完成工作，否则选当前里程碑里依赖最靠前的一项；
3. 写清目标、文件范围、唯一假设（如有）、锁定变量、PIT、成败标准、回退办法和是否需要 ID；
4. 做最小完整改动，只补直接相关的 schema、测试和文档；
5. 跑与风险相称的测试、schema、replay、幂等、diff、Gate 和 parity 检查；
6. 更新 state、backlog、decision log、blocker/reopen 条件、receipt 和复现命令；
7. 以 `completed`、`no-op audit` 或 `blocked` 收尾，报告改动、验证、影响、风险和下一步。

只在任务或自动化明确要求时创建本地 commit。未经用户授权，不 push、不建 PR、不合并、不发布、不传输仓库数据。

以下情况必须停下来问用户：会改变真钱或默认启用状态；需要删除、覆盖或移动证据；数据授权不清；两条重大架构路线
互不兼容；dirty worktree 与目标重叠且无法隔离；无法建立 canonical PIT 却会把等级写错；需要账号、密钥、付费数据、
外部协作或新权限。先做完范围内的只读检查和可逆尝试；难不等于被阻塞。

## 8. 专项文档索引

| 问题 | 单一入口 |
|---|---|
| 回测命令、窗口、baseline、Gate | `docs/backtesting.md` |
| reserve / claim / close / audit | `docs/agent_experiment_protocol.md` |
| PIT 分级和 research replay | `docs/research_pit_policy.md` |
| replay / daily / production parity | `docs/production_backtest_parity.md` |
| adapter parity 状态 | `docs/production_backtest_parity_matrix.md` |
| 实验字段和日志格式 | `docs/experiment_log_format.md` |
| DSR、trial panel、Gate 5 | `docs/deflated_sharpe_protocol.md` |
| 组合级增量价值 | `docs/portfolio_covariance_lane.md` |
| research digest 消费 | `docs/research_digest_pipeline.md` |
| V1 状态导航 | `docs/alpha_context_pack.md`、`docs/current_state_snapshot.md` |
| V1 机制记忆和防重复 | `docs/alpha-optimization-playbook.md`、`docs/frozen_families.jsonl`、`docs/lessons/*.md` |
| V1 股票池生命周期参考 | `docs/universe_promotion_protocol.md` |
| V1 完整旧协议 | `docs/quant_agent_protocol.md` |

V1 文档只提供代码事实、历史教训和反重复证据，不能直接给 V2 候选、权重或晋级资格。
