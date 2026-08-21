# V2 Current State

> V2 状态导航入口。每轮结束时更新。真相源永远是 ticket / ledger / 已提交代码，本文件只负责导航。
> 最后更新：2026-08-21T04:20Z（M1 append-only 与幂等 schema 轮）

## 里程碑

**M0 已完成，M1 进行中**。M1 前四个最小工作单元已完成：基础数据合同、
研究候选合同、决策 / 订单意图 / 结果测量合同，以及 append-only / 幂等 schema 人口校验。

| 里程碑 | 状态 |
|---|---|
| M0 规则 / T0 / 状态文件 | 完成：状态文件、25 项 V1 资产清单、6 项偏差登记表与 T0 声明均已落地 |
| M1 身份、时钟、数据合同 schema | 进行中：三组初始合同与 append-only / 幂等人口校验已完成；下一项为时钟合同 |
| M2 动态 PIT 股票池 | 未开始 |
| M3 共享 SDK 与 Engine-0 干净基线 | 未开始 |
| M4-M9 | 未开始 |

## T0（已确认）

- 用户确认 `T0 = 2026-08-18`；机器真相源为 `data/v2/t0.json`，append-only 决策为 `d-0005`。
- T0 按 `America/Los_Angeles` 的日历日期记录，不倒填虚构的盘中精确时刻。
- 用户确认前及合同落地前的产物最高仍为 `research_pit`，不能追溯升级为 canonical forward 证据；历史数据仍可在明确记录时钟与来源后用于 `research_pit` 私有回放。
- `canonical_forward_eligibility_started_at` 仍为 `null`；具体来源和记录必须分别通过授权、时钟、映射、schema 与冻结 Gate。
- T0 确认不授予任何策略资格，不改变真钱权限，`trade_enabled=false`。

## M1 已完成单元

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
  因此它不关闭任何 V1 bias blocker，不提升 PIT / result ceiling，不建立 replay/daily/execution parity，也不占 experiment ID。

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
- `ReplacementValue` 每条绑定一个 outcome 和一个冻结 comparator；四行 panel 必须精确覆盖 cash/SPY/QQQ/V1，
  同资本基数、币种和 comparison rule，且 `replacement = strategy - comparator`。comparator evidence 同时绑定
  reference id/hash；SPY/QQQ 还需 exact instrument mapping，cash/V1 禁止 instrument evidence，防止跨 comparator 串线。
- 新后链同时绑定 semantic hash 与 record hash；更改上游 `recorded_at`、跨证券重封、结果回灌、修订降级、
  事后换 execution/cost/comparison 口径均 fail closed。独立负向复验未发现剩余 P0/P1。
- 决策 context 与 fill/position 当前仍只是 opaque snapshot，尚无自己的时钟/PIT schema；因此 V1 schema 的
  `DecisionRecord`、`SettledOutcome` 和 `ReplacementValue` 最高只能是 `research_pit / observed_only`，不能据此声称
  canonical Gate 或 execution parity。此单元不接 replay、daily、runtime、broker、ledger 或订单，不占 experiment ID。

### 研究候选合同

- `ResearchClaim` 只能表达由已验证 `EvidenceRecord` 支持的研究断言；冻结证据语义快照、证据 cutoff、
  生产者身份、PIT、置信度、反证、影响对象与下一步，自由文本没有 universe/ranking/risk/order 权限。
- `HypothesisCandidate` 冻结单一可归因机制、baseline/treatment 全套 policy 版本、期限、
  cash/SPY/QQQ/V1 替换对照、成功/失败/kill/promotion 条件、执行约束、novelty 轴和结果 ceiling；
  不绑定具体证券池，允许同一机制在不同 PIT 股票池上复用而不伪造新假设。
- `CandidatePool` 表示 `RankedCandidate` 之前的完整证券候选面，只绑定一个 hypothesis；每项保留
  `admitted/parked/rejected` 及原因，并绑定当时最新 `candidate_eligible` UniverseEvent、security/listing
  映射和候选证据。完整的零候选池也是合法记录，避免只在有赢家时留痕。
- 候选池冻结 generator/ranking 规则身份、完整 Evidence/Universe semantic snapshot、run date/session、
  data cutoff，以及 comparison-only 的 cash/SPY/QQQ/V1 身份；不保存 rank、score、未来收益或结算结果。
- 跨链为 `SourceContract -> EvidenceRecord -> ResearchClaim -> HypothesisCandidate -> CandidatePool`，
  并逐层传播 PIT ceiling、future-leakage 与 causal clocks；instrument evidence 必须匹配候选的
  security/listing，dataclass tamper、hash 重封串线和较旧 eligible 状态都 fail closed。
- 本单元仅验证调用者提交的冻结 universe event snapshot；全量 membership 的外部完备性仍需后续
  append-only ledger/manifest 证明。因此 V1 幸存者名单 blocker 仍 open，不能把 schema attestation
  当成已关闭偏差。
- 三类合同固定 `outcome_blind=true`、`authority=research_only`、`results_accessed=false`（适用处）和
  `trade_enabled=false`；不接 daily/replay/runtime/order，不占 alpha experiment ID。

### 基础数据合同

- `quant/v2_contracts.py`：独立于 V1 的不可变 `SourceContract`、`EvidenceRecord`、`UniverseEvent` 与嵌套 `SecurityMappingSnapshot`。
- 来源合同机器声明原始身份字段、真正参与决策的内容字段、发布时钟字段、修订字段、授权证据、可用性、映射政策、PIT ceiling 与 parity 状态。
- 证据同时绑定原始 artifact SHA-256 和标准化决策内容 SHA-256；所有瞬时时钟必须带时区，禁止日期值、naive timestamp 和进程壁钟回退。
- 跨合同校验强制 `SourceContract -> EvidenceRecord -> UniverseEvent` 完整链：字段和值一致、来源真实存在、等级不越权、映射在当时已知且覆盖生效时点、证据先落账再决策。
- Universe 事件携带显式冻结 run date / calendar session、前后状态、规则 hash、证据语义快照和 previous-event 引用；当前名单/当前映射不能倒灌为 PIT。
- 事件输入快照使用 evidence semantic hash，排除只改变 `recorded_at` 的操作噪声。UniverseEvent 的权威
  append-only ledger / manifest、全量 previous-event 链证明与原子写入仍属于后续 M2 / runtime 工作。
- 本单元只建立 schema/校验，不接 daily、replay、运行时或下单路径，不占 alpha 实验 ID；`trade_enabled=false`。

## M0 交付物

- `data/v2/v1_asset_inventory.json`：25 个 V1 功能资产组已唯一归入五类。
- `data/v2/v1_bias_register.json`：6 项偏差全部保持 open，18 条解除条件均未满足。
- `data/v2/t0.json`：确认项目日期边界、证据 ceiling、禁止追溯升级与 default-off。
- `docs/v2/backlog.md`、`docs/v2/decision_log.jsonl` 与每轮 receipt：状态和接力棒。

## 关键边界（当前生效）

- `trade_enabled=false`；V2 不继承 V1 股票名单、alpha 结论、资格、权重、晋级状态。
- `reuse_directly` 只允许复用工程原语或不可变历史证据，不等于复用 V1 决策结论。
- 6 项 V1 bias blocker 全部仍为 open；本轮只提供解除 blocker 所需的合同原语，不代表任何 blocker 已关闭。
- `canonical_forward_eligibility_started_at=null`；schema 允许表达 canonical 条件不等于当前记录已获 canonical 资格。
- M1 的 opaque decision-context 与 fill/position snapshot 仍把下游结果封顶在 `research_pit / observed_only`；
  初始 schema、人口分类器和 154 项测试不等于原子 ledger、runtime 或 execution parity 已完成。
- M3 Engine-0 建立前，V2 候选最高停在 research/shadow。
- V1 baseline 只做回归与机会成本对照，不是 V2 Gate-1 锚。
- 原 V1 脏 checkout 的未提交 ticket 与产物没有迁入 V2 基线。

## 待用户决定

1. **V1 自动化关系**：V1 每小时 alpha 管线继续与 V2 建设并行，还是冻结为只结算 / 只读历史。
   此决定不阻断 M1 合同建设，但在决定前不启动 V2 forward 竞赛。

## 下一步

继续 M1 的最后一项：建立交易日归属时钟合同，以数据日历 / 冻结 run date / broker session 为权威锚，
显式拒绝进程壁钟回退；保持 research ceiling 与 default-off，不接真钱路径，不占 alpha 实验 ID。
