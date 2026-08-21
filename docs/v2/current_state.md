# V2 Current State

> V2 状态导航入口。每轮结束时更新。真相源永远是 ticket / ledger / 已提交代码，本文件只负责导航。
> 最后更新：2026-08-21T10:31Z（M2 外部 coverage 合同核心）

## 里程碑

**M0、M1 已完成，M2 进行中；bounded research scout lane 现在开放**。M0-M9 改为
promotion-readiness 路线，不再是阻止研究测量的串行队列。M2 外部覆盖、M3 Engine-0 和 runtime parity
继续阻止 canonical/paper/promotion，但不再阻止 source-bounded、`research_pit / observed_only` 的 private replay。

| 里程碑 | 状态 |
|---|---|
| M0 规则 / T0 / 状态文件 | 完成：状态文件、25 项 V1 资产清单、6 项偏差登记表与 T0 声明均已落地 |
| M1 身份、时钟、数据合同 schema | 完成：三组初始合同、append-only / 幂等人口校验与证据绑定时钟合同均已落地 |
| M2 动态 PIT 股票池 | 进行中：研究 ledger 人口核心与 promotion-only 外部 coverage 合同核心完成；真实来源实例与 runtime parity 待完成 |
| Research scout lane | 已开放：首个 SEC contract-relation preflight 在 reserve 前拒绝；等待满足新证据轴与受理条件的输入 |
| M3 共享 SDK 与 Engine-0 干净基线 | 未开始 |
| M4-M9 | 未开始 |

## T0（已确认）

- 用户确认 `T0 = 2026-08-18`；机器真相源为 `data/v2/t0.json`，append-only 决策为 `d-0005`。
- T0 按 `America/Los_Angeles` 的日历日期记录，不倒填虚构的盘中精确时刻。
- 用户确认前及合同落地前的产物最高仍为 `research_pit`，不能追溯升级为 canonical forward 证据；历史数据仍可在明确记录时钟与来源后用于 `research_pit` 私有回放。
- `canonical_forward_eligibility_started_at` 仍为 `null`；具体来源和记录必须分别通过授权、时钟、映射、schema 与冻结 Gate。
- T0 确认不授予任何策略资格，不改变真钱权限，`trade_enabled=false`。

## Scout-first 协议修订

- 13 份 observed V2 hourly receipt、11 条 durable decision、0 个 experiment ID，证明旧问题是 M0-M5 串行调度，
  不是 PIT/default-off 底线。现在 research scout 与 promotion construction 并行；scout 只做 source-bounded、
  `research_pit / observed_only` 测量，仍保留完整 disposition、登记、反泄漏和 `trade_enabled=false`。
- 继续复用现有 promotion/claim/closeout，不新增 bridge 或证据标签；receipt/state/backlog/decision、测试和审阅按事实与结论风险缩放。
- 首次 cadence 条件已经满足。下一轮立即做一次最多 20 分钟 zero-ID preflight；通过即冻结 experiment-local disposition、
  CandidatePool/必要 DecisionRecord 和 promotion，并 reserve 首个 scout。以后只在输入变化、出现可信新轴或再次连续完成两个
  非阻断建设单元时重跑完整 preflight；失败且无安全有价值的直接修复时回 promotion backlog/no-op。

## M2 进行中单元

### 外部 coverage 合同核心

- `quant/v2_universe_coverage.py` 新增仅服务 promotion-construction 的 source-population coverage 合同；它冻结
  scope、完整稳定 row id/hash 面、`mapped / unmapped / excluded` 处置、exact coverage evidence、有效期 mapping evidence、
  universe definition 与目标 manifest 身份。coverage evidence 必须机器绑定 `enumeration_complete=true`、源报告行数和
  完整 row id/hash 集合，不能由 snapshot 自报零行或完整性。
- 每个 mapped row 必须绑定通过既有 `SourceContract -> EvidenceRecord` 校验的 effective-dated mapping；mapping 与其
  evidence 都必须在 `data_cutoff` 前 known、在 freeze 前 recorded，并覆盖 `membership_as_of`。稳定 mapping id 分叉、晚到/过期
  mapping、丢行、重复 row id/hash、count 不守恒和 default-on 均 fail closed。
- `validate_external_universe_coverage_against_manifest` 强制先组合执行上述输入校验，再把 mapped rows 归一去重后的
  `(security_id, listing_id, mapping_sha256)` 集合与目标 manifest 中全部非 retired membership 精确对齐；known-empty 只能绑定
  空 active membership。输出同时绑定 coverage input、snapshot 和 manifest hash，不能绕过 source/evidence 验证。
- 该合同不接 CandidatePool、Hypothesis、promotion request、scout admission、persistence 或 runtime；现有 ledger manifest 与
  daily/replay reader 继续固定 `external_universe_coverage_status=unverified`、`research_pit / observed_only`、
  `paper_live_eligible=false`、`trade_enabled=false`。14 项新对抗测试、44 项 coverage+ledger 聚焦测试和完整 232 项 V2
  测试通过；独立复核确认两个初版 P1（cross-validator 可绕过输入验证、mapping evidence 可晚于 cutoff）已关闭，最终 P0/P1=0。

### 首个 scout preflight 结果

- 2026-08-21 09:05Z 对 SEC contract-relation source frame 的 zero-ID preflight 在 reserve 前拒绝：虽有 294 行、30 个
  ticker 和非零 source-native reach，但缺 V2 Source/Evidence 实例、294/294 timezone-aware `accepted_at`、effective mapping，
  且没有满足既有 contract-relation reopen 条件。未读取 outcome、未占实验 ID。
- 本轮 outcome-blind 复核未发现其他 admission-ready committed source：Moomoo capital-flow 缺可靠 historical known-at、授权与
  frame provenance，FINRA weekly 缺 timezone/session-bound publication clock、授权、effective mapping 和新 novelty axis。
  SEC contract-relation 只有在上轮 receipt 的定量 reopen 条件满足后才可重试。

### Universe ledger 人口核心

- `quant/v2_universe_ledger.py` 建立严格 mixed-JSONL 研究 ledger：每批先校验完整既有前缀和新
  `UniverseEvent`，再在 OS advisory lock 内以同目录临时文件 + atomic replace 提交事件与一个 manifest；
  精确重试幂等，身份或语义冲突 fail closed，损坏、截断、尾随垃圾和跨 manifest 漂移均拒绝读取。
- manifest 冻结 universe 定义、run/effective 双时钟、data cutoff、membership projection、完整事件 / membership
  snapshot，以及累计 append-only 的 source-contract、evidence-record、clock、rule 和 mapping 身份绑定。
  Evidence 同时绑定 semantic hash 与 exact record hash；同一稳定 ID 的内容、记录时钟或规则 / 映射 hash 漂移
  不能通过本地重封绕过。
- 读取必须显式给出已提交 `manifest_id` 和带时区 `as_of`；daily 与 replay 暴露为同一函数的真实 alias，
  不能各自分叉 membership 逻辑。已知但未来生效的事件可先提交，只有 `effective_at <= as_of` 才进入投影；
  后续零事件 manifest 可推进 projection。UTC 等价 offset 得到同一 snapshot。
- `ledger_population_complete=true` **只表示该 ledger 已声明的人口前缀完整且通过校验**，不表示外部市场证券面完整。
  `external_universe_coverage_status` 固定为 `unverified`；manifest / snapshot 强制封顶
  `research_pit / observed_only`、`paper_live_eligible=false`、`parity_status=contract_only_unwired`、
  `authority=research_only` 与 `trade_enabled=false`，本轮没有创建生产 ledger 数据。
- 30 项 ledger 对抗测试、105 项受影响合同测试和完整 218 项 V2 套件通过；独立终审无 P0/P1。
  当前全历史人口校验为 O(n²)，且没有仓库外 append anchor；在全市场规模和任何 canonical 资格前必须优化并
  引入外部可验证锚。真实外部 coverage/security surface、mapped/unmapped/excluded disposition 证据、动态来源、
  runtime adapter 与 production/replay parity 仍是 M2 后续工作；旧资产的 V1 bias findings 仅保留为复用限制。

## M1 已完成单元

### 证据绑定交易日时钟合同

- `SessionClock` 只接受有授权 `SourceContract -> EvidenceRecord` 链的数据日历锚：日历内容必须是带版本、时区、
  覆盖起止和 `coverage_complete=true` 的完整开放 session 面；clock 同时绑定 evidence id、内容 hash 和 record hash。
  日历证据的有效区间必须同时覆盖 assignment cutoff 与所选 session open，且证据必须在 cutoff 前已记录。
- `run_date`、session id、开收盘边界和显式日历行必须一致；周末 / 休市日不会被推断为开放日，early close、
  special closure 与 DST 只服从冻结证据。进程壁钟回退、`trade_enabled=true`、交易 authority 和不完整日历均 fail closed。
- clock 冻结日历证据的 PIT tier；`UniverseEvent`、`CandidatePool`、`DecisionRecord` 不得超过它，
  research-PIT 日历不能为下游制造 canonical / gate-eligible 结论。受时钟约束的这四类记录已显式升为
  `CLOCK_BOUND_SCHEMA_VERSION=2`；仓库中未发现需迁移的持久化 v1 实例。
- Universe run / effective 时钟由联合 validator 强制同时校验：run 使用时刻必须落在日历本地 `run_date`，
  effective session 不能早于 run 且 `effective_at` 必须在其开收盘内，两只 clock 都必须在 event 决定前落账。
  CandidatePool / Decision 同样限制在本地 run date；OrderIntent 可绑定后续 execution session，但有效窗口必须完全在该
  session 内。多 session GTC 尚未建模，因此 fail closed。
- `session_clock_id`、semantic hash 与 exact record hash 已进入 Universe run/effective、CandidatePool、Decision 和
  OrderIntent 的输入快照；clock 自身也纳入 append-only 人口校验，同语义的 `recorded_at` 重试为 duplicate，
  同 ID 语义漂移为 conflict。29 项聚焦对抗测试与完整 183 项 V2 套件通过，独立终审无剩余 P0/P1/P2。
- 目前只启用可验证的数据日历锚；`frozen_run_date` / broker-session 在有各自 typed evidence 合同前明确拒绝，
  不接受自证 hash。该 M1 单元当时未实现 ledger writer；当前 M2 仅补上研究 ledger 人口核心，仍没有
  runtime adapter、daily/replay 运行接线、broker、fill/position 或 exit clock，不升级任何 legacy 时钟证据，
  也不提升 `research_pit / observed_only` ceiling，不占 experiment ID。

### Append-only 与幂等 schema 人口校验

- `validate_append_only_append` 是纯 schema 分类器，不做文件 I/O；新稳定身份返回 `append`，同 stable key 且
  `semantic_hash` 相同的重试返回 `duplicate`，精确下一版 outcome / replacement 返回 `correction`。
- 不可变 `DecisionRecord`、`OrderIntent` 分别明确以 `decision_id`、`order_intent_id` 为稳定键；
  `SettledOutcome`、`ReplacementValue` 继续使用已绑定上游身份与期限 / comparator 的显式 `stable_key`。
- `recorded_at` 改变但语义不变的重复运行不会追加；同键语义漂移、物理 ID 复用、修订缺口、旧前驱 fork、
  非精确 previous id / record hash、冻结身份漂移、状态回退与非单调记录时钟均 fail closed。
- 已有 outcome / replacement 前驱规则被抽成共享校验，跨输入 validator 与人口分类器不会维护两套修订语义；
  15 项新增合成测试覆盖 append / duplicate / conflict / correction 与损坏的既有链，完整 V2 套件共 154 项通过。
- 本单元不实现原子 JSONL/数据库写入、锁、runtime adapter 或 ledger 完备性；调用者仍须先通过对应跨输入校验。
  因此它不提升 PIT / result ceiling，不建立 replay/daily/execution parity，也不占 experiment ID。

### 决策、订单意图与结果测量合同

- `DecisionRecord` 用完整 `DecisionItem` 面板精确覆盖 `CandidatePool` 的每一项；零候选池也必须留下显式完整决定，
  admitted 项排名连续且唯一，parked/rejected 项不能获得信号、风险或尺寸。方向、XOR 数量/名义金额、policy arm、
  deterministic engine、决策 context、execution/cost/comparison rule、期限、session、cutoff 与上游 record hash 均在结果前冻结。
- `OrderIntent` 只能由 selected 且 risk-approved 的决定项产生；方向、证券映射、尺寸、币种、订单类型、价格字段、
  execution rule、显式 execution session 和有效窗口必须一致。它固定 `submitted=false`、`authority=research_only`、
  `trade_enabled=false`，不能表达 broker order、fill 或真钱提交；next-session 意图不会被错误绑回信号日 session。
- `SettledOutcome` 将 decision / intent / candidate-pool record hash、期限、币种、整数资本基数、fill/position 快照、
  record-bound settlement evidence 与精确 cost/comparison rule 连成不可变测量记录。`settled` 强制 `net = gross - cost`；
  缺测量必须保留 `unavailable` 行。修订只能追加到同一 stable key，不能复用 record id、回退 settled 状态或改写冻结身份。
- `ReplacementValue` 每条绑定一个 outcome 和一个冻结 comparator；当前 schema-v1 四行 panel 精确覆盖 cash/SPY/QQQ/V1，
  同资本基数、币种和 comparison rule，且 `replacement = strategy - comparator`。comparator evidence 同时绑定
  reference id/hash；SPY/QQQ 还需 exact instrument mapping，cash/V1 禁止 instrument evidence，防止跨 comparator 串线；
  没有同口径 V1 数据时，V1 行只是显式 `unavailable` 兼容占位，不读取、运行或等待 V1。
- 新后链同时绑定 semantic hash 与 record hash；更改上游 `recorded_at`、跨证券重封、结果回灌、修订降级、
  事后换 execution/cost/comparison 口径均 fail closed。独立负向复验未发现剩余 P0/P1。
- 决策 context 与 fill/position 当前仍只是 opaque snapshot，尚无自己的时钟/PIT schema；因此 schema-v1 的
  `DecisionRecord`、`SettledOutcome` 和 `ReplacementValue` 最高只能是 `research_pit / observed_only`，不能据此声称
  canonical Gate 或 execution parity。此单元不接 replay、daily、runtime、broker、ledger 或订单，不占 experiment ID。

### 研究候选合同

- `ResearchClaim` 只能表达由已验证 `EvidenceRecord` 支持的研究断言；冻结证据语义快照、证据 cutoff、
  生产者身份、PIT、置信度、反证、影响对象与下一步，自由文本没有 universe/ranking/risk/order 权限。
- `HypothesisCandidate` 冻结单一可归因机制、baseline/treatment 全套 policy 版本、期限、
  cash/SPY/QQQ 替换对照及当前 schema-v1 所需的 V1 兼容占位、成功/失败/kill/promotion 条件、执行约束、novelty 轴和结果 ceiling；
  不绑定具体证券池，允许同一机制在不同 PIT 股票池上复用而不伪造新假设。
- `CandidatePool` 表示 `RankedCandidate` 之前的完整证券候选面，只绑定一个 hypothesis；每项保留
  `admitted/parked/rejected` 及原因，并绑定当时最新 `candidate_eligible` UniverseEvent、security/listing
  映射和候选证据。完整的零候选池也是合法记录，避免只在有赢家时留痕。
- 候选池冻结 generator/ranking 规则身份、完整 Evidence/Universe semantic snapshot、run date/session、
  data cutoff，以及 comparison-only 的 cash/SPY/QQQ 身份和 V1 兼容占位；不保存 rank、score、未来收益或结算结果。
- 跨链为 `SourceContract -> EvidenceRecord -> ResearchClaim -> HypothesisCandidate -> CandidatePool`，
  并逐层传播 PIT ceiling、future-leakage 与 causal clocks；instrument evidence 必须匹配候选的
  security/listing，dataclass tamper、hash 重封串线和较旧 eligible 状态都 fail closed。
- 本单元仅验证调用者提交的冻结 universe event snapshot；全量 membership 的外部完备性仍需后续
  append-only ledger/manifest 证明。V1 幸存者名单仍不具备复用资格，不能把 schema attestation
  当成 V2 外部覆盖证明。
- 三类合同固定 `outcome_blind=true`、`authority=research_only`、`results_accessed=false`（适用处）和
  `trade_enabled=false`；不接 daily/replay/runtime/order，不占 alpha experiment ID。

### 基础数据合同

- `quant/v2_contracts.py`：独立于 V1 的不可变 `SourceContract`、`EvidenceRecord`、`UniverseEvent` 与嵌套 `SecurityMappingSnapshot`。
- 来源合同机器声明原始身份字段、真正参与决策的内容字段、发布时钟字段、修订字段、授权证据、可用性、映射政策、PIT ceiling 与 parity 状态。
- 证据同时绑定原始 artifact SHA-256 和标准化决策内容 SHA-256；所有瞬时时钟必须带时区，禁止日期值、naive timestamp 和进程壁钟回退。
- 跨合同校验强制 `SourceContract -> EvidenceRecord -> UniverseEvent` 完整链：字段和值一致、来源真实存在、等级不越权、映射在当时已知且覆盖生效时点、证据先落账再决策。
- Universe 事件携带显式冻结 run date / calendar session、前后状态、规则 hash、证据语义快照和 previous-event 引用；当前名单/当前映射不能倒灌为 PIT。
- 事件输入快照现在同时使用 evidence semantic hash 与 exact record hash，使真实落账时钟成为因果输入，
  不能通过只改 `recorded_at` 重封证据而维持同一快照。M2 已补上研究级 append-only ledger / manifest、
  全量 previous-event 链证明与原子写入；外部覆盖证明、仓库外 append anchor 和 runtime 接线仍待完成。
- 本单元只建立 schema/校验，不接 daily、replay、运行时或下单路径，不占 alpha 实验 ID；`trade_enabled=false`。

## M0 交付物

- `data/v2/v1_asset_inventory.json`：25 个 V1 功能资产组已唯一归入五类。
- `data/v2/v1_bias_register.json`：6 项偏差全部保持 open，18 条解除条件均未满足。
- `data/v2/t0.json`：确认项目日期边界、证据 ceiling、禁止追溯升级与 default-off。
- `docs/v2/backlog.md`、`docs/v2/decision_log.jsonl` 与每轮 receipt：状态和接力棒。

## 关键边界（当前生效）

- `trade_enabled=false`；V2 不继承 V1 股票名单、alpha 结论、资格、权重、晋级状态。
- V2 不管理、停止或等待 V1 自动化；V1 只在主动复用旧代码/证据时作为只读历史参考，V2 research、forward 和晋级只由 V2 条件决定。
- 只对共享 experiment registry 的 ID、write-scope、locked-variable 和 exact-duplicate 冲突 fail closed；这保护 V2 试验记账，不代表 V1 能参与调度。
- `reuse_directly` 只允许复用工程原语或不可变历史证据，不等于复用 V1 决策结论。
- 6 项 V1 bias finding 只限制相应旧资产能否复用，不是 V2 里程碑或 forward blocker。
- `canonical_forward_eligibility_started_at=null`；schema 允许表达 canonical 条件不等于当前记录已获 canonical 资格。
- M1 的 opaque decision-context 与 fill/position snapshot 仍把下游结果封顶在 `research_pit / observed_only`；
  初始 schema、M2 研究 ledger 人口核心和 218 项 V2 测试不等于外部 universe 完备、canonical provenance、
  runtime 或 execution parity 已完成。
- M3 Engine-0 建立前，bounded scout 最高只能是 `research / observed_only lead`，不能获得 shadow/paper/promotion 结论。
- 若主动使用 V1 baseline，它只做兼容性回归与机会成本对照，不是 V2 Gate-1 锚。
- 原 V1 脏 checkout 的未提交 ticket 与产物没有迁入 V2 基线。

## 下一步

在不抽取首个 scout 通用 disposition guard 的前提下，为一个真实、授权且具有 row-level clock 的动态来源物化首份
source-bound coverage snapshot、coverage EvidenceRecord 和 forward-only effective mapping，并与实际 universe manifest 交叉验证；
随后再接共享 runtime adapter 与 daily/replay parity。若期间出现满足 novelty/reopen、PIT、mapping 和非零触达条件的新 source axis，
立即回到 bounded scout lane 做 experiment-local preflight/freeze/reserve；不要无条件重试 SEC contract-relation。
