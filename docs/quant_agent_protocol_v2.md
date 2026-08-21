# Ginger V2 Quant Agent Protocol

> `AGENTS.md` 管通用做事方式，本文件管 V2 量化研究、实验和系统建设。
> 具体命令、阈值、当前状态和历史案例放在专项文档里，不在这里重复。

## 1. 目标和边界

V2 要做的不是一张好看的回测图，而是一套能还原决策现场的研究系统。它必须说清：当时知道什么、
看过哪些候选、为什么这样选、用了哪版数据和规则、承担了什么风险、实际执行了什么，以及后来学到了什么。

可信度必须和**本轮声称的结论**匹配。`observed_only` 的 bounded research scout 不需要先支付 paper/live 级
全市场覆盖、runtime parity、执行状态和外部不可篡改锚成本；一旦要声称 canonical、paper、晋级或生产资格，
这些条件立即恢复为硬门槛。不能用未来的生产完备性阻止今天提出一个可证伪问题，也不能用“只是 scout”绕过
PIT、反泄漏、完整选择面、实验登记或 default-off。

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
3. `docs/v2/current_state.md`、`docs/v2/backlog.md`、最近一份 `data/v2/hourly_runs/` receipt，以及
   `docs/v2/decision_log.jsonl` 中被 state/receipt 引用、尚未解决或上轮之后新增的行；这些文件尚未建立时，由 M0 建立；
4. 当前任务直接涉及的专项文档、代码、schema 和证据文件。

不要每小时重读整个 V1 历史。查具体实验时读 `experiments/logs/<id>.json` 等分片，不要把 100MB 级派生总日志
整份塞进上下文。M1 scout kernel 就绪后，还要看最近的 V2 receipt 是否已经连续完成两个非阻断纯建设单元；
这只用于防止 admission-ready scout 被长期饿死，不是常驻指标或实验产量 KPI。

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
9. **晋级路径的回放和日常运行共用决策逻辑。** 不能把只在 backtester 里赚钱的规则晋级。`private_replay_scout`
   可以暂时 replay-only，但只能形成 `observed_only` lead；进入 validation/paper 前必须改成共享逻辑并证明 parity。
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

“完整股票池”是对**本轮声称的 eligible surface** 完整，不总等于先证明全市场完整。M2 外部 coverage 完成前，
`private_replay_scout` 可以使用 outcome-blind、确定性生成并在结果前冻结的 source-bounded frame。单独的 source
disposition manifest 必须保存 frame 定义、cutoff、输入哈希，以及每个 source row 的稳定身份/哈希、
`mapped / excluded / unmapped` disposition 和原因；不得只留赢家。`CandidatePool` 只接收成功映射的证券，不能用它伪装
unmapped row 已被保存。
首个 scout 使用 experiment-local manifest，不先建共享 schema；source-specific check 至少机器验证 row count 守恒、稳定
row hash 唯一、三种 disposition 互斥，以及 CandidatePool security 集合恰好等于 mapped rows 归一去重后的集合。第二个真实
scout 再次需要同一形状时才抽取共享 guard。
这种 frame 必须固定 `external_universe_coverage_status=unverified`、`result_ceiling=observed_only` 和
`paper_live_eligible=false`，只能声称“在该冻结来源面内的 lead”，不能声称全市场搜索、动态 V2 universe 完备或晋级资格。
V1 赢家、当前幸存者名单、settled return/PnL 和事后挑出的 ticker 不能用来定义 frame。

所有 promotion-bearing 环境共用一条决策链：

```text
EvidenceSnapshot -> CandidatePool -> RankedCandidate -> SignalDecision
-> RiskDecision -> OrderIntent -> Fill/Reject -> PositionState
-> SettledOutcome + ReplacementValue
```

bounded scout 至少冻结到 `CandidatePool`；若测量证券级信号、排序或收益，还必须在读取 outcome 前冻结覆盖该池的
research-only `DecisionRecord`。只冻结 CandidatePool 的 coverage scout 不能声称交易信号收益。scout 不创建
OrderIntent/Fill/Position。promotion-bearing 策略再完整冻结赚钱机制、数据面和 PIT 等级、
entry/ranking/sizing/exit/cost 版本、持有期、容量、流动性、反事实对照、重叠和集中度、失败条件、kill switch 与晋级条件。

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

候选必须先登记、后看结果，但验证深度按结论分层：

| 通道 | 最低前置 | 最高结论 | 此阶段不前置 |
|---|---|---|---|
| bounded research scout | M1 scout kernel、source-bounded 完整 frame、D0-D3、冻结假设/窗口/成本/对照/反证、正常实验 ID | `observed_only` / `positive_replay_lead_not_promoted` | 全市场 coverage、Engine-0、shared daily adapter、runtime parity、Gate 1-5、broker/execution envelope、外部 append anchor |
| canonical validation | immutable/as-published 或 append-only 的 canonical PIT、对所声称 surface 的完整覆盖、独立未使用窗口、V2 Engine-0、共享 policy/replay、适用成本与风险 | `validation_passed_not_promoted`，不进入晋级标签链 | daily/runtime parity、执行/容量、forward 和 activation |
| paper / promotion / production review | 上述全部，加 daily/runtime parity、完整执行/容量/风险、forward 与 activation checklist；本地 observer 还需仓库外 append anchor | `shadow` 或相应更高晋级标签；仍不自动交易 | 无 |

research scout 仍须冻结完整 outcome-blind candidate/selection panel，在结果前声明 baseline、一个 treatment、primary horizon、保守成本、
cash/SPY/QQQ/V1/被替代项对照、成功阈值和 falsifier/negative control；缺失对照要留 `unavailable`，不能静默删除。
它不运行尚无 V2 Engine-0 的 canonical Gate 1-4；已有 Gate 输出只能作为诊断，不能写成 Gate 通过或晋级。

以下完整评估要求适用于 promotion-bearing validation：按时间分 discovery、validation 和未使用的 forward；计算完整成本、
现金约束、每日 MTM、强平、容量和滑点；同日期、同资本比较对照，同时检查集中度、beta/factor、相关性、回撤、
expected shortfall、换手和机会成本。有完整选择面时计算 PSR/DSR，合适时检查 PBO；语义或事件信号要做 placebo、
permutation 或 negative control。

`expected_value_score = strategy_total_return_pct * abs(sharpe_daily)` 只保留为 V1 兼容指标。策略晋级前必须同时证明：

1. 扣除成本后，策略自己有正价值；
2. 资本不增加时，替换进组合后仍有增量价值。

`docs/backtesting.md` 当前的 V1 baseline 只做回归和机会成本对照，不能直接成为 V2 Gate-1 晋级锚。M3 要在 V2 动态
PIT 股票池和共享决策链上建立独立 Engine-0 baseline；在此之前，V2 候选最多停在 `research / observed_only lead`。

晋级标签是 `research -> shadow -> qualified_paper -> pilot_ready -> limited_production_ready -> core_policy_eligible`，
旁路是 `quarantine / retired`。标签只表示证据成熟度，不会自动打开交易。

买卖、过滤、排序、仓位和风险规则必须放在共享 policy/helper。研究建议、`OrderIntent`、已提交、成交、拒单、撤单和
当前持仓分开记录。重复运行要幂等；字段缺失、价格过期、数据陈旧或非交易时段要 fail closed。监控至少覆盖数据/observer
零产出、输入内容身份、现金预留、fill drift、position trajectory drift 和 replay/daily parity。

## 5. 怎么选工作、怎么做实验

先处理与 V2 当前范围重叠的未完成实验、失败或冲突；不重叠的 V1 legacy open ticket 不会自动阻塞 V2。下面的依赖链
约束的是**可以声称的结论和晋级资格**，不是所有研究工作的全局串行队列：

```text
identity -> clock -> source contract -> universe -> shared policy
-> validation -> forward wiring -> allocator -> activation review
```

### 双通道与最小 Scout Kernel

- **Research scout lane：** M1 最小 kernel 就绪后即可与 M2-M5 并行运行 `research_pit`、
  `private_replay_scout`。kernel 只要求 T0/default-off；授权通过且 hash-bound 的 Source/Evidence；可用的 row-level
  `known_at` 与 evidence-bound session clock；frame 内 effective-dated mapping；outcome-blind 冻结的完整 source-bounded
  candidate panel；单一机制、treatment、horizon、对照、成本与反证；以及 experiment registry/D0-D3。
- **Promotion construction lane：** 继续按 identity -> clock -> source -> universe -> shared policy -> validation -> forward
  推进外部覆盖、Engine-0、共享 runtime、测量、allocator 和 activation。缺这些会阻止 canonical/paper/promotion，
  但只要没有破坏 scout 的最低声明，就不阻止 bounded `observed_only` 测量。

现有 alpha promotion / claim / closeout 是 V2 scout 的唯一登记封套，不再新建 bridge schema 或证据标签。reserve 前，
stage-required V2 records、source disposition 和 evaluation-input manifest 必须通过相关 individual/cross checks，列入所选
`research_pit` surface 的 `artifact_snapshot_hashes`，并由 promotion request 冻结完整 decision/evaluation recipe。读取 outcome
前必须 claim，让现有 `alpha_promotion_claim_receipt` 复验 promotion 并生成 content-addressed snapshots。若 runner 含冻结 spec 未表达的自由度，
其 code/config hash 也必须在 outcome 前锁定；否则 code hash 可在 closeout 作为复现身份补记。closeout 要证明实际输入等于
预冻结值并记录 code/result identity；缺失、漂移或事后替换一律 `invalid_contaminated` + registry `rejected`。通用 registry
cross-hook 是 scout P2；同类人工 binding 连续出现两次再提升为共享 guard，不能因此重新前置 M2-M5。

### 工作优先级和防饥饿

默认排序是：P0/P1 containment -> 不受该问题影响的正在运行/未收尾 V2 experiment -> 已通过免费 preflight 的 scout
-> 安全、有价值且可完成的直接 scout blocker -> promotion construction backlog。M1 kernel 就绪后：

- 只有最近已连续完成两个非阻断纯建设单元、候选输入哈希发生变化，或已有可信的新证据轴时，才给 candidate readiness
  做最多 20 分钟的 zero-ID 免费检查：授权、PIT、映射、非零触达、novelty/saturation、reopen 和并发；未通过就 park，
  不烧 ID。失败输入未变时复用上次结论，不重复完整检查。
- 连续完成两个非阻断纯建设单元后，只要存在 admission-ready scout，下一个完整单元必须 reserve/run/continue 该 scout，
  promotion-only P2 基建不能继续抢占。没有合格新证据轴时不为了节奏硬开实验。
- 一个 scout 只允许一个 hypothesis、一个 treatment 和一个 primary horizon，默认最多跨两个小时单元（freeze/reserve；run/close）。
  超时只能继续或 park，不能放宽 PIT、反泄漏或 closeout。
- 免费 preflight 全部失败时，receipt 记录 exact failed predicate、输入 hash 和定量 reopen trigger。只有存在安全、有价值、
  可完成且预计能直接形成 admission-ready scout 的 blocker 时才优先修；否则回到 promotion backlog 或 no-op，不让节奏规则制造工作。

scout 按 §3 和 §4.4 判级：PIT/反泄漏/完整 source frame/登记/`observed_only` ceiling 是硬边界；全市场 coverage、
Engine-0、runtime parity、正式 Gate 和 execution/append-anchor 完整性是 scout P2、晋级硬门槛，不能扩张当前 scout。

新 alpha 实验至少要有一条机器可查的新证据轴：真正独立的新数据源、真正不同的决策面/gate shape、达到已登记
重开条件的新增 settled forward 决策，或未饱和来源上确实没用过的新字段。join、换阈值、换响应、换子类、同日刷新和
重新讲旧机制都不算。

例行 append、结算和摘要刷新不占新 ID；真正的管道故障修复才算 `measurement_repair`。纯文档整理不需要 ID；若同时
改变机器 guard、测量口径或策略行为，改变合同的部分必须走实验流程。

### Research Scout 顺序

1. **Outcome-blind 合成：** 在同一 PIT 股票池比较机会成本；盘点 price、flow、derivatives、event、positioning、
   portfolio exposure 和 research digest；生成 1-3 个有经济因果链的假设，再选一个。
2. **写反证：** 给 lead 写 baseline、treatment、horizon、replacement comparator、PIT 等级、成功条件和 falsifier。
3. **冻结和登记：** 先冻结 source disposition manifest、mapped-only CandidatePool、必要的 DecisionRecord、选择面、规则、
   输入哈希、窗口和验收标准，
   通过 D0-D3 并生成 tracked promotion request，再用 `scripts/experiment.py new --change-type private_replay_scout` reserve ID。
   不要手写 ID，也不要在 reserve 前创建 experiment runner、outcome result 或 evaluation artifact；D0-D3、source/frame
   和 promotion 等 admission artifacts 必须先冻结。有并行工作时先 claim；疑似超时先查 open ticket，不能盲重试。
4. **锁定回放：** 只运行预注册政策和窗口；结果读取后，该窗口永久记为 consumed discovery。报告 gross、保守成本后结果、
   简单 comparator、falsifier、样本量和 missing/exclusion，不在同一 ID 内看结果调阈值。
5. **硬封顶收尾：** 只有通过全部完整性检查的正向 lead 才可把 registry 顶层状态写成 `observed_only`，并把
   `artifact.disposition` 写成 `positive_replay_lead_not_promoted`。negative、样本不足或污染一律把 registry 顶层状态写成
   `rejected`，artifact disposition 分别写 `rejected`、`inconclusive_insufficient_sample` 或 `invalid_contaminated`；污染结果还要
   标记 `evidence_invalid=true` 并 containment。后续 validation 必须使用新 ID 和未使用窗口/forward。

### Promotion-bearing 实验顺序

能同时用于 replay 和 daily 的信号使用 shared-paper-first。Gate 1 锁定 V2 Engine-0 baseline；Gate 2 查真实运行时字段；
Gate 3 查生成数、存活数和存活率；Gate 4 用相同输入和窗口做 before/after。只有讨论 live eligibility 时才做 Gate 5。
精确命令和阈值看 `docs/backtesting.md`。未过 Gate 4 就回滚策略改动并保留失败记录。

所有实验都要记录输入/代码身份、artifact、PIT、production impact、parity、prediction calibration、禁止的近邻重试、
定量重开条件和复现命令。失败、污染和样本不足也要完整关闭；每个 trial 都进入多重检验账本。

单元测试通过不等于 alpha 成立。每个实验的
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

M0-M9 是 promotion-readiness 路线，不是排他的小时工作队列：M0 定规则/T0；M1 scout safety kernel 与基础合同；
M2 动态 PIT 股票池；M3 共享 SDK 和干净基线；M4 AI 研究系统；M5 科学实验框架；M6 零权重迁移 V1；M7 forward 竞赛；
M8 组合分配器；M9 提交 pilot 审核材料。M1 kernel 就绪后，bounded research scouts 与 M2-M5 并行；M6-M9 和任何
promotion-bearing validation 仍必须满足各自前置。完成 M9 也不自动交易。

## 7. 每小时怎么执行

每轮只做一个能验证的工作单元：

1. 看状态、backlog、上次 receipt、相关 open experiment、测试失败、git status 和最近连续非 scout completed receipt 数；
2. 按 §5 的优先级选 active experiment、P0/P1、admission-ready scout 或最小直接 blocker，不再机械选择最早里程碑；
3. 写清目标、文件范围、唯一假设（如有）、锁定变量、PIT、成败标准、回退办法和是否需要 ID；
4. 做最小完整改动，只补直接相关的 schema、测试和文档；
5. 只跑本阶段适用、与风险相称的检查；
6. 每轮写 receipt；experiment ticket/log/artifact 已是实验真相源时 receipt 只引用它。只有 milestone/ceiling/blocker/next priority
   改变才更新 current_state，只有排序/checkbox 改变才更新 backlog，只有架构、证据等级、晋级或生产边界形成耐久决策才写
   decision log；不要把同一段散文复制四遍；
7. 以 `completed`、`no-op audit` 或 `blocked` 收尾，报告改动、验证、影响、风险和下一步。

小时预算默认把前 40 分钟用于 preflight/实现，之后冻结 scope，只做验证、closeout、receipt 和接力；发现新 P0/P1 时可修复或
安全 park，P2 进入 backlog，不在本轮递归 hardening。任何新增必填字段或 Gate 必须写明它防止的具体失败、适用阶段和
机器 enforcement；只影响 promotion 的风险不能升级成全局 scout 前置。聚焦测试是默认；只有共享核心合同变化或里程碑关闭
才跑完整 V2 套件，只有跨 V1/shared runtime 或发布边界才跑 full quant。research scout 不强制多重独立终审；共享合同默认一次
stage-fit 对抗审阅，canonical/paper/promotion/production 边界再做更强复核。

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
