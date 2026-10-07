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

### 1.1 近期经济目标

V2 的近期目标不是增加实验数，而是缩短一条可信 alpha 从想法到可执行收益证据的时间。研究北极星是**扣除交易成本、
借券/融资成本和机会成本后的 forward replacement value**；辅助指标是从候选冻结到首次结算、Gate 4、足量 forward
结算和 activation review 的耗时。回测 PnL、Sharpe、命中率或 `expected_value_score` 只能解释证据，不能替代这条北极星。

在用户批准真钱前，“产生实际收益”只能表述为 default-off paper / broker shadow 的已结算净 replacement value，不能把历史回测
利润写成已赚到的钱。系统要尽快把通过严格验证的候选送到 `limited_production_ready` 审核材料，而不是自行打开交易。

收益转化 SLA 分两级：数值/readiness gate 已开、但仍需 outcome-blind scope 选候选时记为
`scope_debt`，下一个可执行工作单元必须跑该 scope；候选、输入和反证合同都已冻结、可直接实验时才记为
`conversion_debt`，并在发现当轮直接 `reserve -> claim -> run/build`。shared-paper build 通过后，daily observer 必须在
下一个合格决策窗口前就位；产生决策后按冻结 horizon 结算。错过任一节点都不能用报告、修复数量或 proposal 冲销。

“下一个工作单元”还必须有墙钟约束。每笔可执行债务和每个冻结的 `next_alpha_action` 都记录 `action_due_at`：默认是下一个
有执行权限的 alpha slot，且不得晚于 opened/frozen 后 24 小时；只依赖已冻结本地数据的 replay、密度检查和 falsification 不因
周末或休市暂停。确实依赖新市场数据时才可顺延到下一个合格 session，并机器记录原因。逾期未启动是
`economic_incident=missed_alpha_execution_slot`，管理/Reflection 单元只能上报，不能滚动或重置截止时间。

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

仓库存在多个 worktree / branch 执行 V2 时，启动检查不能只看当前 checkout。先只读枚举自动化配置声明的执行 lane，
以及滚动窗口内含 post-T0 V2 lifecycle 活动的 refs；跨 ref 生命周期身份使用 `(source_ref, experiment_uid)`，不能只按
`experiment_id` 去重。相同 ID 对应不同 UID 时保留两份证据、冻结该 ID 不再复用，并在下一次 reserve 前选择所有可见 refs
都未占用的新 ID；不得覆盖、重编号或复制结果载荷。

每个自动化必须记录 `execution_lane`（worktree、branch、HEAD、upstream）和 `authoritative_state_ref`。旧配置尚未显式声明时，
自动化配置指定的专用 worktree 当前 branch 只作为**后续自动化写入的操作权威**；其他 ref 是只读证据 namespace。这不判定
哪段历史的科学结论更优，也不授权合并、rebase、清理 dirty checkout 或导入结果。只读 ref 的 protocol/state/terminal history
不同、或存在不重叠的用户 dirty 文件，本身不冻结权威 lane。

每份 receipt 还必须记录实际读取的 lane-local `protocol_path`、`protocol_source_ref` 和 `protocol_sha256`。Reflection 或其他管理单元
只有在新规则已安全写入实际执行 lane、或存在能让下一轮取到它的已提交/已授权同步路径时，才能声称“协议优化已生效”；只改非执行
worktree 的同名文件必须明确标成 `not_operational_in_execution_lane`。不同历史版本本身不阻塞 alpha，但执行任务必须以自己记录的
lane-local 协议为准，不能借另一个 worktree 的新规则或旧规则为本轮行为背书。

只有两个 ref 仍有 open/active lifecycle writer、同一 UID 的管理字段冲突、open debt 归属冲突，或声明写域实际重叠时，才记为
`economic_incident=divergent_execution_lane` 并停相关写域；无冲突的 observer 结算与独立 alpha lane 继续。确定性的 ref/UID 投影、
终态碰撞隔离和只读 namespace 标记属于启动对账，不能独占一个工作单元。只有确需追加一次 alias/authority mapping 时才允许一个
管理单元；若只是终态分叉，按上述默认值继续，不得等待用户选择。只有非终态冲突无法无损隔离、需要移动/覆盖证据，或两条 active
写路径都合理且互斥时才请用户决定，不能按提交时间静默猜测。

落后或只读 lane 不得把全局实验误报成零，也不得新开实验或重复审计旧 blocker。按 `(source_ref, experiment_uid)` 汇总
create / claim / run / close 的管理字段后再计算全局 24 小时脉冲，不读取结果值。脉冲在工作单元开始和收尾前各计算一次，
每份 receipt 记录 `pulse_as_of`、权威 ref 与 ledger 哈希；期间 observer 或其他 writer 追加事实时，收尾值必须重算，不能沿用
启动快照。提交前校验 staged union 只含本工作单元声明的文件，禁止把并发 writer 的 ledger/state 顺手纳入实验提交；需要引用其
新事实时只绑定独立提交或内容哈希。

发生冲突时，按“用户和系统指令 → `AGENTS.md` → 本协议 → 专项文档 → 摘要/历史说明”处理。
专项文档可以补细节，不能放宽 PIT、反泄漏、default-off 和真钱边界。

## 3. 不能破的规则

1. **不能事后挑名单。** `core` 是资金和风险政策，不是一张永久股票表。
2. **不能倒填资格。** 数据、股票、映射、策略、模型和 Skill 结论只能在 `known_at`、`eligible_as_of` 之后参与决策。
3. **不能只记赢家。** 结果出来前就冻结完整股票池、所有候选、入选和落选原因、被挤掉的替代项，以及 cash、SPY、QQQ 和 V1 对照。
4. **选候选时不能看答案。** 未来收益、PnL、MFE/MAE、结算结果和赢家标签不能进入候选生成或选择。发现阶段查看含已结算结果的 ledger / 报告时，只允许按预先声明的 ALLOWED 身份/状态字段白名单投影读取；黑名单、子串匹配或“掩码结果列”式过滤结构性不安全，一律禁止（2026-09-01 第 3 例：`realized_pnl_to_date` 命中子串 'date' 逃过遮罩）。把结果值打印进上下文即视为污染，本轮按 zero-ID containment 处理（2026-08-11、2026-08-18、2026-09-01 三例）。
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

为避免把晋级门槛误用成实验启动门槛，V2 另设 `fast_falsification_scout`。它仍是正式 `alpha_search` ticket，但只用于快速否证：

- 启动只要求一个已授权的本地 source、内容身份/哈希、保守 `known_at` 边界和诚实 PIT 标签；一个确定性 source-bounded frame；
  一个 outcome-blind 冻结的候选、treatment、primary horizon、cash 或一个明确 replacement comparator、保守固定成本与 falsifier；
  非空可复现 entrypoint、窄写域和 `trade_enabled=false`。
- reserve 前只需用身份/状态字段估计 primary horizon 至少有 10 个可评估决策，并确认 comparator 非空；不要求先达到
  `>=30/horizon`、每腿样本 bar、多 horizon、完整 cash/SPY/QQQ/V1 对照、Engine-0、shared daily、runtime parity、容量或 Gate 1-5。
- 它可以是单候选 panel；registry 仍使用现有 research-replay promotion/claim 封套来冻结身份和防止看答案，不另造旁路 ID。
- 样本不足 30、PIT 仅为 `research_pit`、缺完整 comparator/parity 或只在一个窗口为正时，正向结果一律
  `inconclusive_positive_scout`，不能写成 accepted alpha 或晋级；负向/不可区分结果可以直接 reject/park。只有补齐正常验证合同后，
  才能用新 ID 进入 canonical Gate 或 default-off paper。

买卖、过滤、排序、仓位和风险规则必须放在共享 policy/helper。研究建议、`OrderIntent`、已提交、成交、拒单、撤单和
当前持仓分开记录。重复运行要幂等；字段缺失、价格过期、数据陈旧或非交易时段要 fail closed。监控至少覆盖数据/observer
零产出、输入内容身份、现金预留、fill drift、position trajectory drift 和 replay/daily parity。

## 5. 怎么选工作、怎么做实验

先处理未完成、失败或冲突中的工作。V2 建设期按下面的依赖顺序推进：

```text
identity -> clock -> source contract -> universe -> shared policy
-> validation -> forward wiring -> allocator -> activation review
```

这条依赖链约束**单个候选可以声称的结论**，不是要求全系统完成 M0-M5 后才允许研究 alpha。需要 canonical 验证或 paper 的候选
仍按下面的“完整 alpha 内核”执行：

1. 本轮输入的身份、授权、决策时钟、PIT 等级和哈希已冻结；
2. 本轮股票池、security 映射和 eligibility 能按决策时点还原；
3. 完整选择 panel、同口径 baseline、成本模型、资本约束和 replacement comparator 已冻结；
4. 结果列在选择前不可见，replay / daily 边界和最高结论已写清；
5. 实验记录、回滚路径和 `trade_enabled=false` 边界可执行。

不满足完整内核、但满足第 4.4 节 `fast_falsification_scout` 最低启动条件的候选，也必须立即进入 `alpha_search`，结论按 scout
硬封顶；不得因为通用 schema、全市场 universe、完整 comparator 或后续 allocator 仍未完工而等待。满足完整内核后，默认下一项工作
同样是 `alpha_search`。
只有能点名所阻断候选、失败 Gate 和解除条件的 `measurement_repair` 可以插队；纯文档、泛化重构和“以后可能有用”的数据接入
不能占用一条已经 ready 的收益路径。

工作节奏遵守：

- outcome-blind readiness preflight 最多占一个工作单元；通过后，下一个工作单元必须 reserve 并执行冻结测试，不能停在 proposal；
- 连续两个已完成工作单元都不是 `alpha_search` 时，下一个单元必须做 outcome-blind alpha preflight 或 alpha 实验；只有对已登记
  surfaces 逐一给出量化 blocker 和 reopen 条件后，才能继续建设工作；
- forward 等待不独占研究 lane：不改变口径的 observer 后台积累时，主动切换到另一个 canonical-PIT 或可快速否证的 research-PIT
  候选；
- 同等因果质量下，优先 canonical-PIT、短结算周期、可共享 replay/daily、容量更高、执行摩擦更低的候选；需要真实 locate、
  复杂期权权限、付费源或长期事件等待的候选必须用更强的预期增量价值补偿这些延迟。
- 每个 selector 在 outcome-blind 阶段冻结 `predicted_success_probability`、`time_to_first_falsifier`、`eta_first_settlement`、
  仍缺的权限/工程依赖和保守净 replacement value 区间。候选按“可部署净价值 × 成功概率 ÷ 墙钟时间”做同质量排序；低先验但
  可在本地快速否证的候选仍可执行，低先验且还需跨日等待、新权限或新管道的候选不得仅因 readiness 已开就占据前台。

### 24 小时 alpha 脉冲和修复闭环

每个新工作单元启动时，先从 ticket、Gate artifact 和 append-only ledger 计算严格滚动 24 小时脉冲：`alpha_trials`、
`canonical_gate4_passes`、`forward_decisions`、`settled_outcomes`、`net_replacement_value`、`active_forward_sleeves`、
`observer_stale_sleeves`、`eligible_unadmitted`、`due_unsettled`，以及每条 sleeve 的 `eta_first_settlement` 和
`eta_contract_completion`。同时记录 `oldest_actionable_debt_age_hours`、`next_alpha_action_due_at` 和
`missed_alpha_execution_slots`。`measurement_repair`、抓取行数、测试数、schema 数和文档数不能计入 alpha 或收益进展。

`alpha_trials` 只衡量科学吞吐，不能购买 24 小时的空闲额度。脉冲还必须按独立机制记录 `positive_alpha_leads`、
`rejected_or_inconclusive_alpha_trials`、`hours_since_last_independent_alpha_start`、`hours_since_last_positive_lead` 和
`alpha_search_due_at`。只有正向 lead 正在走 `fastest_conversion_path`、canonical Gate 通过、default-off forward 新决策/结算，
或净 replacement value 更新，才算向收益转化推进；被拒绝/无结论/污染的 scout、measurement repair 和通用 M2-M5 建设仍是
`economic_progress=false`。

只要当前没有一个**未阻塞且正在转化**的正向 lead，系统就处于 `discovery_mode`，即使严格 24 小时内已有 alpha trial。
scout 以 rejected / inconclusive / invalid 关闭时，只关闭该 family，并把 `alpha_search_due_at` 设为下一个有权限的 alpha slot，
最迟不超过 2 小时。到期前最多允许一个非 alpha 单元插队，而且它必须点名一个已冻结候选、唯一失败 predicate 和本轮能直接把它
变成 runnable 的交付物；通用 M2-M5 建设、重复 audit 和不改变 blocker 的 hardening 不合格。到期后不得因 `alpha_trials>0` 或相同
blocker fingerprint 做 no-op：必须 outcome-blind 地转向独立 source/mechanism，达到 scout 最小内核就在同一单元
`freeze -> reserve -> claim -> run`。未达到时机器关闭该候选并继续冻结 fallback；只有一次新合成已证明当前全部已授权本地
source/mechanism 都耗尽，并记录逐项 blocker、未扫描数为 0 和事件 trigger，才允许等待。

一旦出现正向 lead，系统切到 `conversion_mode`：除 observer 到期结算和 P0/P1 外，后续单元优先补它的 canonical/default-off/
parity/执行缺口并尽快得到已结算净 replacement value。通用建设只有直接解除该 lead 的 `fastest_conversion_path` blocker 时才能
插队；若 lead 被量化 blocker park，则立即回到 `discovery_mode`，不能靠继续建设平台代替寻找独立 alpha。

若过去 24 小时 `alpha_trials=0` 且没有正在执行的冻结实验，本工作单元只能二选一：执行一个已通过 preflight 的 alpha 实验，
或完成一次 outcome-blind preflight 并把下一工作单元锁定为具体冻结实验。若现有 lead 都被真实 locate、付费数据、新权限或长期等待阻断，
默认切到已有 canonical-PIT、共享执行链和成本模型可覆盖的低摩擦候选；优先无需借券的 long-only / long-cash replacement，
不能继续用修同一条受阻数据链代替 alpha 搜索。

“所有已登记 surface 都关闭”不再足以结束零脉冲单元。只要仓库内仍有已授权、可做 `research_pit` 或 canonical-PIT 的本地
price/flow/event/positioning 数据，本轮还必须 outcome-blind 地合成一个**未登记的新 surface 或真正不同的决策机制**，按
`fast_falsification_scout` 做免费 preflight；达到 10 个 primary-horizon 决策的最低启动线就冻结并在同一单元 reserve/claim/run。
只有该新合成也因授权、PIT、非空映射、结果污染、exact duplicate 或零触达而机器关闭，才允许写一次 `no_candidate` 后等待 trigger。
历史 saturation、缺完整 Engine-0/parity、样本不足 30、缺 SPY/QQQ/V1 或尚未具备 daily adapter 不能单独阻止 scout 启动。

若 `settled_outcomes=0` 且最早预计结算仍超过 5 个交易日，或唯一 active sleeve 依赖尚未取得的 locate/权限，下一次 outcome-blind
合成必须包含至少一条**快速结算 lane**：现有权限与成本模型可覆盖、无需借券、H1-H5、canonical-PIT 或可保守重建的
long-only / long-cash replacement。它仍要过完整 falsifier 和 Gate，不能因“快”放宽标准；只有机器列出已登记 surface 及逐项 blocker
后才可宣称无此候选。质量相当时，优先首次结算更早、capital-day 效率更高者。

需要尚未获得的真实 locate、付费源或新权限的 paper sleeve 可以继续后台积累证据，但不能成为唯一 active monetization path。
在这些 blocker 解除前，前台 alpha lane 必须优先推进一条用现有数据、权限和执行链即可到 activation review 的候选；默认选择
无需借券的 long-only / long-cash replacement。这个优先级不改变 `trade_enabled=false`，也不替代最终用户批准。

### 可运行动作、阻塞监视项和 no-op 熔断

`next_alpha_action` 只能是当前可运行的动作：必须有具体 candidate/surface、非空 entrypoint 或复现命令、已冻结或可在结果访问前
确定性生成的 artifact、当前已具备的数据/PIT/权限，以及 success/failure gate、`action_due_at` 和不共享同一 blocker 的 fallback。
`entrypoint=null`、等待未来 session/结算、缺 source、账号、权限或 writer authority、只剩污染 cohort 的候选都记为
`blocked_watch_item`，不能占据前台 `next_alpha_action`，也不能把它们的未来窗口当作 alpha SLA 已被满足。

候选首次被阻塞时，receipt 冻结 `blocker_fingerprint`（surface、failed predicates、相关输入/代码哈希、权限状态和合法重查时钟）、
`blocked_until` 与事件型 `recheck_trigger`。在 trigger 未发生且 fingerprint 不变时，后续小时任务只做常数时间身份比较，以
`no-op suppressed` 退出：不重复跑相同测试/全量 audit，**不创建文件、不 commit、不 push**。首份 incident receipt 已封存该
fingerprint；后续“仍然不变”的 receipt 不具有信息增量。一个 blocker 在两个 trigger 之间最多消耗一个完整工作单元；随后必须
park 并切到不共享该 blocker 的可运行 fallback。若全部登记 surface 都机器关闭，保留一次 `no_candidate` artifact 并等 trigger，
不能靠每小时复制 no-op 制造进展。只含终态历史分叉、只读 dirty surface 或已隔离 ID 碰撞的 lane 对账不算 blocker；完成启动投影后
必须继续选择 alpha 工作。

当严格 24 小时 `alpha_trials=0` 时，管理/authority/namespace 对账最多消耗首次 incident 的一个工作单元；同一 fingerprint 的
下一次合格运行必须执行当前可运行的 alpha 或冻结 preflight。若 frozen surface sweep 证明全部候选关闭，才可无文件退出并等待
事件 trigger。不得让“等待用户选择历史权威”成为长期前台动作，除非确有未结束 writer 或重叠写域不能无损隔离。

alpha 被拒绝时，同一工作单元关闭该 family 的近邻重试并检查次要报告是否污染相邻候选。被污染、只等长期 forward 或缺新权限的
相邻项只能进入 `blocked_watch_item`；下一可执行单元必须从独立机制选一个当前可运行候选，除非 frozen surface sweep 已用逐项机器
blocker 证明没有候选。拒绝增加 `alpha_trials`，但 `economic_progress` 仍为 false，不能用一次干净失败抵消收益转化 SLA。

### Readiness 债务必须分类并立即消费

readiness 检查不是独立成果。机器 artifact 只证明前置数值/能力 bar 通过、但冻结合同仍要求 outcome-blind scope
和 source-contract 检查时，记为 `scope_debt`，不得宣称候选已就绪。下一个可执行工作单元必须运行冻结 scope：
选出候选时，同一工作单元冻结其 falsifier 并直接 `reserve -> claim -> run/build`；未选出时，以机器可查的
`no_candidate` artifact 关闭该债务，并把下一个工作单元锁定到已登记的低摩擦备用 surface。scope 本身不占 alpha ID；冻结
runner/build 实际开始后 `alpha_trials` 才加一。

scope 不能先选一个候选、再发现其反证对照结构性不可达后停到下一轮。promotion-bearing 候选必须在最终 selector 之前，用决策时点
可见的身份/密度字段完成 `pre_reserve_reachability`；结果值仍不可见。只有 treatment、control/placebo、各 horizon 样本数和必要
执行覆盖达到预声明下限的候选才能进入 selector，`execution_feasibility` 也只有此时才能记满分。scope manifest 同时冻结完整
fallback policy；候选生成和 reachability 完成后、任何结果访问前，selection panel 再冻结候选 ID、哈希和 outcome-blind fallback
顺序。若 primary 因选择前无法检查的机械 blocker 在 reserve 前失败，同一工作单元立即沿该顺序继续，
直到启动一个正式实验，或以逐候选机器 blocker 关闭整个 panel；只要同一冻结 panel 仍有未检查的 D0-D3 pass 候选，就不得新开
`scope_debt` 或以“下一轮复验”结束。

`fast_falsification_scout` 的 reachability 例外是：只检查 primary horizon 的预估决策数 `>=10`、非空 comparator 和 runner
确实可执行；样本充分性、placebo/多 horizon/每腿 bar 在实验内报告并限制 verdict，不在 reserve 前重复设成阻塞门。一个 scout
只能有一个冻结候选、一个 primary horizon 和一次运行；不得借此做参数 sweep 或看结果后追加 horizon。

候选、输入身份/PIT/授权和反证合同都已冻结、可执行时才是 `conversion_debt`。若本轮 artifact 让它从 closed 变为 open，
本轮必须沿既有合同直接 `reserve -> claim -> run/build`；不得重做 preflight、重写 proposal、扩展 scope，或以更新 state / backlog /
协议后结束。两类债务都优先于通用 M0-M5 建设和新的 measurement repair。只有输入身份/PIT/授权失效、冻结合同不可执行，或与
无法隔离的现场改动冲突时才可停止；receipt 必须给出机器可查的 blocker 和 reopen 条件。

receipt 对两类债务都至少记录 `debt_type`、`trigger_artifact`、内容哈希、`opened_at` 和冻结合同引用。`scope_debt`
另记 `consumed_at`、`selected_candidate` 或 `no_candidate_artifact`；`conversion_debt` 另记 `consumed_by_experiment_id`。仅
`measurement_ready`、scope 通过、reserve ID 或生成脚手架都不计 alpha。连续两个 24 小时脉冲都为零后，除非用户明确要求或发现新的
机器 blocker，不得再用纯协议/报告优化占用下一个执行单元；协议编辑本身也不能延期已有债务。

### 数值 bar 要可达，修约要预登记

冻结 reopen / acceptance 合同时，每条数值 bar 必须结构可达：它应衡量测量装置在正常运行下确实能产生的能力证据，
不能是与决策重合的罕见事件计数。冻结前对每条 bar 给出保守的期望到达路径；给不出的，改写成由持久化 artifact
机器可查、fail-closed 的能力条件（先例：exp-20260721-002 冻结的 `actual_cash_conflicts>=10` 在 32 个 ok trace
会话里只出现 1 次终身冲突、0 次决策重合，而其余 bar 全部 17-38 倍通过——冻结时做一次期望事件率检查即可避免）。

已冻结 bar 只能通过**预登记的一次性 contract review ticket** 修约（exp-20260811-001 预登记 → exp-20260828-001 执行）：
review 全程 outcome-blind、不读任何结果/PnL 值；其余 bar 字节不变；下游 readiness / reopen gate 在同一工作单元重跑并
记录 before/after。数值 gate 打开后若仍需 scope 选候选，只产生 `scope_debt`；只有冻结候选已可执行时才产生
`conversion_debt`。两者都不等于候选资格或 phase 重开。未预登记的 bar 修改一律
按放宽验收门槛处理。

### Observer 自动采证，真钱仍默认关闭

shared-paper / broker-shadow build 通过后，只要该路径不生成 `SignalDecision`、`OrderIntent` 或订单，observer 就必须随既有日常任务
自动运行；`trade_enabled=false` 保护的是资本和订单路径，不得被解释成关闭 paper 采证。每次合格运行必须按冻结规则依次完成：
admit 全部 eligible 决策、settle 全部到期 basket、更新成本后 replacement value 和 cash/SPY/QQQ 对照、幂等追加 ledger 与健康摘要。

`observer_stale_sleeves>0`、`eligible_unadmitted>0` 或 `due_unsettled>0` 任一成立，都记为 `economic_incident`；下一工作单元先恢复采证或
结算，再开新实验。若只修复调度、持久化或结算故障且不改变冻结决策合同，不另占 alpha ID；若改变 signal、entry、exit、成本、
候选准入或执行语义，则必须走实验流程。不得通过关闭 observer、漏记到期结果或放宽验收门槛来改善表面脉冲。

每个 `measurement_repair` 必须在登记时写明 `blocked_downstream_check`、冻结输入和修复前 gate 值；修复后在同一工作单元重跑
该下游检查，并记录修复后 gate 值。组件恢复但下游仍关闭时，可以技术上接受修复，但 receipt 必须写
`economic_progress=false`，不得表述为恢复了 alpha 或收益路径。下一工作单元只有在剩余项是该候选最后一个量化 blocker、且没有更低摩擦的
可测候选时，才允许继续修同一路径；否则立即 park 并换 surface。

promotion-bearing 新 alpha 实验至少要有一条机器可查的新证据轴：真正独立的新数据源、真正不同的决策面/gate shape、达到已登记
重开条件的新增 settled forward 决策，或未饱和来源上确实没用过的新字段。`fast_falsification_scout` 第一次测试一个未登记的
source-bounded surface 或真正不同的因果机制时，允许 novelty/saturation 仅作 warning，并在 ticket 里记录风险；exact duplicate、
已污染 cohort、同一窗口的阈值/持有期/响应 sweep 仍硬阻断。同一 family 的这项放松只允许一次，之后必须有新数据、未使用窗口或
新 gate shape。join、换阈值、换响应、换子类、同日刷新和重新讲旧机制仍不算。
当 D0-D3 已选中、唯一剩余 reserve 阻塞只是 registry near-neighbor warning 时，fast scout 可显式使用
`scripts/experiment.py new ... --no-enforce-novelty` 并把 warning 写入 ticket；不得用 override 绕过 exact duplicate、reopen、污染或
冻结 family 的同配方重试。

先免费检查授权、PIT、映射、密度、真实候选触达和 reopen 计数；不够就 park，不要烧实验 ID。例行 append、结算和摘要
刷新也不占新 ID；真正的管道故障修复才算 `measurement_repair`。纯文档整理不需要 ID；若同时改变机器 guard、测量口径
或策略行为，改变合同的部分必须走实验流程。

### 严谨与效率必须同时成立

PIT 纪律不能退化成“所有实验都从零等待 forward”。默认按证据可还原程度走最快合法路径：

1. 有 canonical PIT 历史快照、版本或可验证决策时钟的，立即做正式历史验证；
2. 能从不可变日快照、内容哈希、最早提交/归档时间保守重建 `known_at` 的，先重建独立证据表再验证，不能改写原 ledger；
3. 只有 research PIT 的，先用冻结的延迟、成本和缺失压力回放快速淘汰，结论上限保持 `observed_only`；
4. 只有真正无法历史还原的字段，或历史验证后的最终确认，才依赖干净 forward；
5. forward 采集优先建设共享证据总线，一批数据服务多个预登记假设，禁止每个实验重复造一条等待管线。

效率不能降低晋级标准：保守重建和压力回放可以加速发现、排序和否证，但不能把 research PIT 冒充 canonical PIT，
也不能绕过共享 policy、Gate、replacement value、执行现实和 `trade_enabled=false` 边界。目标是尽早杀掉坏想法、尽快把
少数好想法送进严格验证，而不是用等待代替研究，或用速度代替证据。

### Alpha 到收益的最短闭环

每个 lead 在登记时必须写一条 `fastest_conversion_path`：当前证据级别、下一项能推翻它的独立证据、到 default-off paper 的
缺口、到可执行 forward 的缺口、预计首次结算与合同样本充足时间，以及除最终用户批准外仍缺的 activation blocker。按下面的闭环推进：

```text
outcome-blind preflight -> frozen falsification -> canonical Gate 4
-> default-off daily observer -> settled net replacement value
-> Gate 5 / activation review -> 用户批准后才可能 limited production
```

- research-PIT 正结果应立即选择：补齐 canonical 证据，或用 unchanged observer 开始 forward；如果关键执行证据不可获得，就 park
  并切换 surface，不能在同一历史样本上继续扫邻近规则。
- canonical Gate 4 通过时，同一 full-stack 实验必须留下 default-off daily 输出、settlement 路径、parity 测试和 kill 条件；
  “回测 accepted、以后再接 forward”不是完成态。
- forward 结算必须报告净 PnL、replacement value、capital-day 效率、成本漂移、集中度和对 cash/SPY/QQQ/V1 的同资本比较；
  observer 启动后持续滚动更新 activation review 骨架，不能等样本达标后再补执行、权限、kill switch 和容量材料。
- 达到预登记的 Gate 5 与 forward 门槛后，下一工作单元优先生成 activation review 材料；协议本身不授权下单。

### Alpha 实验顺序

1. **Outcome-blind 合成：** 在同一 PIT 股票池比较机会成本；盘点 price、flow、derivatives、event、positioning、
   portfolio exposure 和 research digest；通常生成 1-3 个有经济因果链的假设再选一个；零脉冲的 fast scout 可以直接冻结
   一个新 surface 上的单候选，但必须先查 exact duplicate 和污染围栏。
2. **写反证：** 给 lead 写 baseline、treatment、horizon、replacement comparator、PIT 等级、成功条件和 falsifier。
3. **冻结和登记：** 先冻结完整候选池、选择面、规则、输入哈希和验收标准，再用 `scripts/experiment.py new` reserve ID。
   fast scout 的“完整候选池”可以是确定性生成的单候选 source-bounded panel，使用现有 research-replay promotion/claim 封套；
   不要求先建立全市场 candidate pool 或 promotion-bearing Gate 材料。
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

这些里程碑衡量平台完备度，不是 alpha 的串行 release train。具备第 5 节最小 alpha 内核的 vertical slice 可以跨越尚未完成的
通用里程碑立即实验；它只能复用已审核的合同和代码，不能借“加速”继承 V1 名单、结论、资格或权重。该 slice 验证后再把可复用
部分回填到 M1-M5，避免先造完整平台、后发现没有经济价值。

M0-M1 至少落下 V1 资产清单、偏差登记表、T0、V2 state/backlog/decision log/hourly receipt，以及
`SourceContract`、`EvidenceRecord`、`UniverseEvent`、`ResearchClaim`、`HypothesisCandidate`、`CandidatePool`、
`DecisionRecord`、`OrderIntent`、`SettledOutcome`、`ReplacementValue` 的初始 schema。先补 schema 校验、append-only 和
幂等测试，再进入 M2。

## 7. 每小时怎么执行

每轮只做一个能验证的工作单元：

用户明确要求的 Reflection、只读总结或协议复核属于管理单元，不计入 alpha 执行工作单元，不能满足或重置 24 小时
零脉冲 SLA，也不能消费或延期 `scope_debt` / `conversion_debt`。它们必须报告当前脉冲和下一个可运行 alpha 动作，但不用报告代替该动作。

1. 看执行 lane / 权威 ref、状态、backlog、上次 receipt、open experiment、测试失败和 git status；先完成跨 lane 管理字段对账；
2. 计算去重后的全局 24 小时 alpha 脉冲；优先处理到期结算或仍有效的未完成 alpha，其次消费 open `conversion_debt`，再消费 open
   `scope_debt`，然后按“已通过
   readiness 的 alpha → 本轮必须执行的冻结 preflight 转化 → 直接阻断候选且可闭环复查的 measurement repair → 当前里程碑
   通用建设”选择；artifact 在本轮把 gate 打开时，readiness 检查与 alpha 启动视为同一个工作单元；
3. 写清目标、文件范围、唯一假设（如有）、锁定变量、PIT、成败标准、回退办法和是否需要 ID；
4. 做最小完整改动，只补直接相关的 schema、测试和文档；
5. 跑与风险相称的测试、schema、replay、幂等、diff、Gate 和 parity 检查；
6. 更新 state、backlog、decision log、blocker/reopen 条件、24 小时脉冲、receipt 和复现命令；相同 `blocker_fingerprint`
   未触发重查时按 no-op 熔断不写重复 receipt；其余 receipt 必须给出
   `economic_progress`、open gate 的 `scope_debt` / `conversion_debt`、active sleeve 的 observer/decision/settlement 健康与两项 ETA，以及下一工作单元
   唯一且当前可运行的 `next_alpha_action`（具体候选、命令/入口、冻结 artifact、成败 gate、`action_due_at` 和冻结 fallback 顺序）；
   缺权限、缺入口或等待未来窗口的项目另列 `blocked_watch_item`，不能只写泛化方向；
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
