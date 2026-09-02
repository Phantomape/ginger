# V2 Current State

> V2 状态导航入口。每轮结束时更新。真相源永远是 ticket / ledger / 已提交代码，本文件只负责导航。
> 最后更新：2026-09-02T01:49Z（M3 research-only dynamic PIT market-universe snapshot）
> Outcome hygiene：本导航只记录 terminal 状态、证据位置和重开条件；settled 指标只保留在 canonical
> ticket / log / artifact 中，outcome-blind 启动阶段不得读取。

## 里程碑

**M0、M1 已完成，M2 进行中；bounded research scout lane 现在开放**。M0-M9 改为
promotion-readiness 路线，不再是阻止研究测量的串行队列。M2 外部覆盖、M3 Engine-0 和 runtime parity
继续阻止 canonical/paper/promotion，但不再阻止 source-bounded、`research_pit / observed_only` 的 private replay。

| 里程碑 | 状态 |
|---|---|
| M0 规则 / T0 / 状态文件 | 完成：状态文件、25 项 V1 资产清单、6 项偏差登记表与 T0 声明均已落地 |
| M1 身份、时钟、数据合同 schema | 完成：三组初始合同、append-only / 幂等人口校验与证据绑定时钟合同均已落地 |
| M2 动态 PIT 股票池 | 进行中：研究 ledger、外部 coverage/SEC 8-K 实例、显式 legacy/segmented-hot runtime/observation handoff、event-prefix 索引、checkpoint/segment sidecar publisher/writer、compact rotation、storage capability/rollback、cold-lineage 结构回归及外部 anchor 的 target-independent 决策合同完成；市场级扩展与获批外部 target 实现待完成 |
| Research scout lane | 已运行 2 个：`exp-20260822-001` SEC exact-8-K H1 与 `exp-20260901-001` PCAOB audit-amendment stress H5 均以 `rejected` 关闭；完整结果只见 canonical log/artifact |
| M3 共享 SDK 与 Engine-0 干净基线 | 进行中：research-only market decision clock、source-bounded dynamic PIT market-universe snapshot、Engine-0 cash/no-signal baseline 与完整逐行 lineage 已绑定；共享 predictive feature/policy、scheduler 与 runtime/production parity 仍未建立 |
| M4-M9 | 未开始 |

## T0（已确认）

- 用户确认 `T0 = 2026-08-18`；机器真相源为 `data/v2/t0.json`，append-only 决策为 `d-0005`。
- T0 按 `America/Los_Angeles` 的日历日期记录，不倒填虚构的盘中精确时刻。
- 用户确认前及合同落地前的产物最高仍为 `research_pit`，不能追溯升级为 canonical forward 证据；历史数据仍可在明确记录时钟与来源后用于 `research_pit` 私有回放。
- `canonical_forward_eligibility_started_at` 仍为 `null`；具体来源和记录必须分别通过授权、时钟、映射、schema 与冻结 Gate。
- T0 确认不授予任何策略资格，不改变真钱权限，`trade_enabled=false`。

## Scout-first 协议修订

- 先前连续建设而无 experiment ID 证明旧问题是 M0-M5 串行调度，不是 PIT/default-off 底线。现在 research scout
  与 promotion construction 并行；首个 scout 已以 `exp-20260822-001` 完成；scout 只做 source-bounded、
  `research_pit / observed_only` 测量，仍保留完整 disposition、登记、反泄漏和 `trade_enabled=false`。
- 继续复用现有 promotion/claim/closeout，不新增 bridge 或证据标签；receipt/state/backlog/decision、测试和审阅按事实与结论风险缩放。
- 首次 cadence 已执行：官方 SEC 2026-08-20 exact-8-K complete frame 通过 zero-ID preflight，冻结 experiment-local disposition、
  CandidatePool、DecisionRecord 和 promotion 后 reserve/run/close `exp-20260822-001`。以后只在输入变化、出现可信新轴或再次连续完成两个
  非阻断建设单元时重跑完整 preflight；失败且无安全有价值的直接修复时回 promotion backlog/no-op。

## M2 进行中单元

### 首个真实 SEC 8-K coverage 实例

- `data/v2/source_bundles/sec_edgar_8k/20260820/20260821T125627Z/` 冻结首个仅前向、不可变的
  source-bounded 输入：SEC 官方 access/复用说明、2026 EDGAR 日历、完整 2026-08-20 daily form index 和
  同次抓取的 company/exchange association。五个物理 artifact 的请求 User-Agent、identity encoding、HTTP 状态、
  响应元数据、字节数与 SHA-256 均进入 `bundle.json`；bundle semantic hash 为
  `5d94cc360a607d2824ddf523340a6b8f94dd5d560f1216644296db7cb7146613`。
- 严格 header/count 校验得到 4,183 个 index row 和 219 个 exact-case `8-K` row；冻结日必须严格晚于 index date，
  防止同日 partial index 冒充完整人口。10,387 行 association 经过 exactly-one CIK 与 NYSE/Nasdaq allowlist 后，
  219 行守恒为 116 mapped、91 unmapped（42 missing + 49 ambiguous）和 12 excluded；去重后形成 111 个
  research-only security/listing mapping、UniverseEvent 与 active membership。
- 每个 Evidence locator 使用可移植的 `bundle:<bundle_id>/<member>` 逻辑地址，并解析到真实 member bytes 的 SHA-256；
  row hash 只绑定解析后的 source row 与原始行号，不受重新抓取时刻或 mapping 元数据变化污染。mapping 从 association
  artifact 的抓取时刻起仅前向生效；EDGAR session clock 绑定官方 06:00-22:00 ET 窗口和 2026 年 11 个关闭日。
- source bundle 以 member-first/manifest-last 发布；ledger 先以锁与 atomic replace 提交完整验证前缀，再严格重载并
  交叉校验 coverage snapshot/manifest，最后写不可变 envelope。ledger 与 envelope 是可恢复的 staged publication，
  不声称跨文件原子性；冲突、并发、崩溃后重试、路径碰撞和 raw-byte tamper 均 fail closed，精确重试返回 duplicate。
- 真实实例仍固定 `external_universe_coverage_status=unverified`、`research_pit / observed_only`、
  `paper_live_eligible=false`、`parity_status=contract_only_unwired`、`authority=research_only` 与
  `trade_enabled=false`。它证明这一个 SEC 8-K source frame 的处置完整性，不证明市场级股票池覆盖；12 项专项对抗测试、
  完整 248 项 V2 测试与 persisted-graph CLI 校验通过，独立终审 P0=0/P1=0。

### SEC 8-K runtime adapter parity fixture

- `quant/v2_sec_8k_runtime_adapter.py` 的只读 v3 adapter 要求调用者同时显式提供 backend、storage location、已提交
  `manifest_id` 和 timezone-aware `as_of`；只接受 `legacy_jsonl_v1` 或 `segmented_hot_v1`，没有默认 backend、路径探测、
  hot-to-exact 降级或 silent legacy fallback。daily/replay 导出仍是同一函数对象，禁止 latest-manifest、manifest 自选和
  进程时钟回退。
- segmented 路径每次 adapter 调用只执行一次 `load_segmented_v2_universe_state`，把同一份已验证 hot state 同时交给
  materialization graph validator 与共享 membership resolver；只允许当前 tip manifest，不遍历 superseded lineage。
  legacy path wrapper 保留显式兼容，但不会被 segmented 失败触发。
- adapter 在 graph validator 前读取并本地校验 envelope canonical hash，随后要求 validator 返回同一 envelope、manifest
  与 coverage 身份，避免验证后再次消费未校验副本。输出冻结 bundle/envelope/coverage/manifest/universe/as-of/reader
  完整 identity hash、共享 reader snapshot hash 与 adapter snapshot hash；v3 另绑定 backend 及 segmented checkpoint/tail/tip
  身份，绝对路径和 consumer 标签不进入身份。membership semantic snapshot 在 legacy/segmented 间保持相同。
- `adapter_parity_status=daily_replay_verified_research_only` 只描述这个 source-bounded membership adapter；不可变 source/
  manifest 的 `parity_status=contract_only_unwired` 保持不变，因为尚未建立 Engine-0 policy/baseline、全市场 universe、daily scheduler
  或 production policy。tamper、错 manifest、naive/越界 as-of、boundary escalation、`trade_enabled=true` 和 paper/live
  提升与非有限 JSON（含数值溢出）均以稳定错误拒绝；49 项 SEC 专项测试、完整 347 项 V2 测试与真实 111-membership graph 的
  offset-equivalent parity 检查通过。

### Pre-Engine-0 universe observation handoff

- `quant/v2_universe_observation.py` 的 v2 observation 用调用者显式提供的 backend/storage location/`manifest_id + as_of`
  调用一次 SEC adapter，并把已验证的
  membership rows 交给同一个 daily/replay 真 alias；路径和 consumer 标签不进入观察身份。输出绑定 adapter/input/reader/
  backend/hot-state/manifest/universe/membership hash，逐行精确保留 mapping、state、event 与 effective clock，不读取或产生 outcome。
- consumer 再次校验 adapter、input identity、shared-reader snapshot、ledger-equivalent membership semantic hash、精确 row schema、
  canonical order、security/listing 唯一性及完整 research-only ceiling；重封后的 ceiling 提升、矛盾身份、额外 rank/signal/outcome
  字段、非法 hash/state/clock、行值漂移、乱序与重复身份均 fail closed。
- `observation_parity_status=daily_replay_alias_verified_research_only` 只证明这一个 source frame 的 membership/state/identity/default-off
  handoff。原 observation 仍固定 `engine0_policy_invoked=false`、`engine0_baseline_established=false` 和
  `market_decision_clock_status=unwired`；后续 clock consumer 不会回写或提升它。

### Research-only market decision clock boundary

- `quant/v2_market_decision_clock.py` 对同一显式 SEC observation 只调用一次既有 adapter，并用已建立的
  `SessionClock -> complete calendar sessions -> EvidenceRecord -> SourceContract` 链验证市场决策时钟。observation
  `as_of` 必须与 `assignment_cutoff` 为同一 UTC instant，clock 的 freeze 与 record 必须严格早于 session open；
  process wall clock、未来/迟到时钟、PIT/authority/default-off 或身份重封漂移均 fail closed。
- v2 输出同时绑定 observation/adapter/backend/hot-tip/manifest/universe/membership 与 clock/calendar/session/cutoff 身份，
  并保留该次 observation 已验证的完整 membership rows；consumer 复验逐行 schema、顺序、唯一性、cutoff、count 与
  semantic hash。daily/replay 是同一 callable，`market_decision_clock_status=bound_research_only`。它不生成 candidate、
  signal、decision、outcome 或 order。
- 该合同仅关闭了 M3 的 research-only clock-binding 结构缺口；`engine0_policy_invoked=false`、
  `engine0_baseline_established=false`、`parity_status=contract_only_unwired`、`paper_live_eligible=false` 且
  `trade_enabled=false`。不声称 scheduler、production/backtest、execution、canonical 或 paper/live parity。

### Research-only dynamic PIT market-universe snapshot

- `quant/v2_dynamic_market_universe.py` 是 post-CandidatePool、pre-predictive-policy 的 reconciliation boundary：在同一 separately frozen market-clock hash 与 CandidatePool/Hypothesis
  identity 上重验关联研究图的因果、身份与时钟约束，并以 assignment cutoff 投影 CandidatePool 冻结的全部 UniverseEvent。投影必须与
  market-clock 的 exact membership rows 逐行相等，保留 non-candidate state、mapping、latest event semantic/record hash
  与 effective time；删行、换行、重排或自洽重封不同人口均 fail closed。
- 它不生成 CandidatePool；v1 snapshot 同时冻结完整 event semantic/record population、membership semantic/exact snapshots、每行 lineage hash、
  state counts 和 CandidatePool 完整 candidate-eligible surface。daily/replay 是同一 callable；Engine-0 v3 必须重验该
  snapshot 的独立冻结 hash，并把 identity 写入 DecisionContext，不能跳过该边界直接接受替换人口。
- `dynamic_market_universe_status=verified_exact_rows_research_only` 只表示这一个 source-bounded、调用者已冻结的完整人口在
  该 cutoff 的 PIT 投影，不表示 market-wide coverage。输出仍为 `external_universe_coverage_status=unverified`、
  `research_pit / observed_only`、runtime/production unwired、paper/promotion ineligible，且没有 predictive feature、score、
  rank、signal、size、outcome 或 order；`trade_enabled=false`。

### Research-only Engine-0 cash/no-signal baseline

- `quant/v2_engine0_baseline.py` v3 只消费独立冻结的 market-clock、dynamic market-universe snapshot 与 CandidatePool/Hypothesis
  identity，并对 `SourceContract -> EvidenceRecord -> ResearchClaim -> HypothesisCandidate -> CandidatePool ->
  UniverseEvent` 已引用依赖的因果、身份与时钟约束再次交叉验证。Hypothesis 必须在 assignment cutoff 前 recorded，pool 必须绑定同一
  session clock、market-universe hash 与 cutoff；改变已绑定语义/身份的自洽重封、残缺依赖图或迟到输入均 fail closed。
- 固定 cash/no-signal policy 无可调参数。identity-only feature rows 保留候选输入与 admission 身份；完整
  DecisionRecord 仅把 admitted rank 当审计顺序，所有 admitted 行均为 `not_selected`，inactive 行不产生 decision，
  side/risk/size/currency 全空且 `order_intent_count=0`。daily/replay 是同一 callable。
- dynamic snapshot validator 是关联研究图约束、universe population 与 exact-row reconciliation 的单一通用路径；Engine-0 v3
  只在其上增加 immutable cash-baseline 专属检查，再把 separately frozen snapshot hash 与 hash-sealed lineage 写入
  DecisionContext，`membership_lineage_status=verified_exact_rows`。
- 输出仅在上述冻结身份、关联依赖图约束与逐行 lineage 全部通过后声明 `engine0_baseline_established=true`，scope 仍只为
  `validated_candidate_pool`。外部市场覆盖继续是 unverified；ceiling 保持 `research_pit / observed_only`，runtime/production
  parity 为 unwired，canonical/promotion、paper/live 均不合格，`trade_enabled=false`。

### 外部 coverage 逐行因果时钟

- coverage row / snapshot schema 升为 v2；每个 source row 必须携带 timezone-aware `known_at`。完整人口的
  `row_snapshot_sha256` 与 coverage EvidenceRecord 的 `decision_content.source_rows` 都精确绑定
  `(source_row_id, source_row_sha256, known_at)`，所以改写逐行可用时刻不能只靠重封 snapshot 绕过证据。
- 每个 row 必须在 `data_cutoff` 前已知，且不晚于完整 coverage evidence 的 `known_at`；带 mapping 的 row 还要求
  mapping 与 mapping evidence 在该 row 的因果处置时钟前已知。原有 mapping cutoff、freeze、effective interval、
  exact evidence/hash 与 manifest reconciliation 约束继续生效。
- outcome-blind 临时 SEC 官方源 preflight 曾验证下一真实输入具有非零触达：前一完整日 `8-K` index 为 219 行、208 个
  CIK；同次冻结的 10,387 行 company/exchange association 中，保守规则得到 116 mapped、42 missing、49 ambiguous、
  12 unsupported-exchange dispositions。它本身只验证 source readiness；后续上述独立 materialization 单元才冻结新的
  官方 artifact、SourceContract、EvidenceRecord、coverage snapshot、ledger 与 manifest，仍未创建 experiment ID。
- 仓库不存在 coverage v1 持久化实例，因此本次 schema 升级不需要迁移。18 项 coverage 对抗测试、48 项
  coverage+ledger 聚焦测试和完整 236 项 V2 测试通过；独立终审为 P0=0/P1=0。所有 ceiling 保持
  `research_pit / observed_only`、`paper_live_eligible=false`、`trade_enabled=false`，runtime parity 未改变。

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

### 首个 bounded scout 运行结果

- 用户明确要求优先做实验并临时放松 scout 标准；本次只放宽单横截面、弱 fixed-zero-excess prior 以及不要求 Engine-0/
  市场级 coverage，不放宽 outcome-blind freeze、完整 source disposition、hash-bound promotion/claim、预先冻结验收规则或
  `trade_enabled=false`。这不是全局协议降级。
- `exp-20260822-001` 使用已冻结的 2026-08-20 SEC exact-8-K complete frame：219 个 source row 守恒处置后得到
  111 个去重 mapped issuer，全部等权在 2026-08-21 RTH open-to-close 测量，成本固定 10 bps，对照 cash/SPY/QQQ；
  outcome 只在 promotion freeze 和 claim 完成后读取。
- 预先冻结的受理条件未全部通过，因此 registry 与 ticket 以 `rejected` 关闭，不产生 observed-only lead，
  不晋级、不改共享 policy/order/paper/live；完整 settled 指标只保留在 canonical log/artifact 中。
- 该 frame 已消费。禁止在同一 frame 上事后扫成本、持有分钟、item code、子集或 event-sign 阈值；
  下一次同类尝试需要独立冻结的更晚 complete frame，或结果前可用的独立事件符号源。

### PCAOB amendment-stress scout 运行结果

- `exp-20260901-001` 在任何价格 outcome 读取前冻结完整 942 行 PCAOB audit-report amendment frame、周度
  `count>=3` stress gate、count-one negative control、next-Tuesday-or-later entry、SPY H5 comparator、10 bps cost、
  2023-09-01 至 2026-06-01 窗口及 `research_pit / observed_only` ceiling，并经 promotion reserve/claim 快照绑定。
- 48 个 stress 与 29 个 negative-control 决策均可评估，但两个预注册 primary comparison 均失败；ticket、log 与
  artifact 原子关闭为 `rejected`，evidence 未污染。该 source/gate/window 已消费，不得基于已见结果改 count/H5/window/cost。
- 该 scout 不建立 Engine-0、runtime 或 execution parity，不改变 policy/ranking/sizing/exit/order/paper/live，
  `trade_enabled=false`。重开只接受 as-published PCAOB vintage 或前瞻冻结的新 filing rows，并保持原规则。
- 首次 lean audit 因 canonical log 有意只保留 compact result、完整 reflection 位于 SHA-256 绑定 artifact 而误报
  `weak_reflection`。`exp-20260901-002` 增加严格 artifact path/hash/terminal/scope/authority 复验及结构化 boolean-check
  归因后关闭为 `accepted`；未绑定或 hash 不符仍 fail closed，且 `exp-20260901-001` 终态 ticket/log/artifact 未改写。

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
- 30 项初始 ledger 对抗测试、105 项受影响合同测试和当时完整 218 项 V2 套件通过；独立终审无 P0/P1。
  后续 scale-containment 单元移除了 loader/writer 对每条新 `UniverseEvent` 反复调用通用 append-only 全前缀校验的
  O(E²) 路径，并把 manifest id 与 clock identity 历史查重改成增量索引。已提交 111-event SEC ledger 的严格 load
  `validate_universe_event` 调用从 6,437 降到 222；deterministic 3→6 event 测试同时覆盖 load 与 empty-ledger write，
  保留 duplicate/conflict taxonomy、完整 manifest/population/chain、PIT 与 default-off 校验。
- 这不表示长期 ledger 按逻辑事件数整体线性：每个 manifest 仍累计携带并验证完整 event IDs、registries 与 memberships，
  writer 仍原子重写全文件。多 manifest checkpoint/segmentation 与仓库外 append anchor 仍分别是市场级扩展和任何
  canonical 资格前的 blocker。首个 source-bounded SEC 8-K coverage/security surface、runtime adapter 与 observation
  handoff 已由后续单元补齐；旧资产的 V1 bias findings 仅保留为复用限制。

### Universe checkpoint/segment sidecar 与 publisher/writer

- `quant/v2_universe_ledger_segments.py` 新增 opt-in、只读的物理存储合同：常量大小的显式 `HEAD` 是唯一提交权威，
  绑定一个不可变 checkpoint 和可选的反向 hash-linked segment tail；每个 segment 只保存一笔原样 v1 event/manifest
  transaction，`HEAD` 不保存增长的 segment 数组。checkpoint 冻结严格验证后的完整前缀以及 event、manifest/batch、
  source/evidence、clock、rule、mapping、chain-head、membership 与 pending future-event 身份状态。
- loader 只沿 `HEAD` 可达链读取，要求 exact canonical UTF-8 bytes，拒绝缺失、截断、非有限 JSON、内容篡改、乱序/
  断链、跨 checkpoint 身份漂移、物理 event 漏记/重复与任何 PIT/default-off 提升；未被 `HEAD` 引用的完整 orphan
  保持不可见，只由只读 audit 报告。重建结果最后仍交给现有 strict legacy validator，并返回完全相同的
  `{"events": ..., "manifests": ...}` 逻辑视图。
- future-effective 事件在 checkpoint 中保留为 pending，后续零事件 manifest 推进 `membership_as_of` 后可得到与 legacy
  相同的激活结果。已提交 SEC 111-event fixture 的 manifest、event semantic/record 与 membership hashes 完全不变。
  15 项 focused 对抗测试、106 项 ledger/coverage/SEC/sidecar 测试和完整 294 项 V2 测试通过；独立终审 P0=0/P1=0。
- 显式 bootstrap 与 segmented append 现在和 legacy writer 共用同一 request/M1 preparation 与 locked-history
  classification；首笔及后续每笔都必须通过 source/evidence、calendar/clock、event/manifest/batch、PIT 与 default-off
  校验，不能用结构合法的 legacy view 绕过输入合同。bootstrap 只在 virgin root 或“唯一 exact planned checkpoint、零
  segment”的首笔崩溃恢复面上工作；`HEAD` 缺失且已有 segment 时 fail closed，不能回退已提交历史。
- checkpoint/segment 以 exact canonical LF bytes 经 temp+fsync 和 create-only hard link 发布，路径碰撞绝不覆盖；合作
  writer 在同一 OS advisory lock 下串行化，完整 immutable 对象先落盘，最后才以 atomic replace 更新固定 `HEAD`，并在替换前
  复核 predecessor bytes。`HEAD` 前失败只留下不可达 orphan，精确重试复用；`HEAD` 已替换但调用方未收到成功时，重试返回
  duplicate。零事件 manifest 仍恰好占一个 segment；58 项 focused 与完整 305 项 V2 测试通过，独立终审 P0=0/P1=0。
- compact rotation 在同一 `HEAD.json.lock` 下先严格重建 exact 历史，再发布只含一份当前 events、一个 exact tip manifest、
  O(history) manifest/clock/input 身份胶囊和 predecessor `HEAD` 的新 checkpoint，最后原子切换 `HEAD`。当前 generation 的
  state load、fresh append、历史精确/recorded-at-noise 幂等重试和语义冲突判定都不读取 superseded 代；checkpoint head 与
  tail 的历史 manifest/batch 身份重复会在热加载时拒绝。
- 显式 exact legacy load、rotation 和 snapshot-consistent orphan/superseded audit 是低频冷路径：它们迭代追随不可变 predecessor
  谱系，逐代对账完整 events、物理顺序、全部 manifests、身份胶囊与 clocks。成功轮换不删除旧 checkpoint/segment；它们标为
  superseded 而非 orphan，引用损坏、重封身份漂移、谱系断裂/循环均 fail closed。轮换与 append 并发串行，`HEAD` 前失败只留下
  不可达 orphan，commit 后不确定重试返回 `already_compact`；audit 与 rotation 共用锁，symlink 条目单独标为 invalid。
- `HEAD.storage_contract` 现在是 HEAD 内 self-hash-bound 的 aggregate format marker：full-checkpoint head 保留
  `v2_universe_checkpoint_segment_sidecar_v1`，compact head 使用
  `v2_universe_checkpoint_segment_sidecar_compact_v1`。checkpoint、compact checkpoint 与 segment 的 immutable record contract
  不变；loader 强制 marker 与 checkpoint 类型一致，并在打开 compact checkpoint 前拒绝未知 marker。hot state 同时暴露
  `legacy_full_reader_compatible`。仓库没有持久化 segmented `HEAD.json`，因此没有 tracked migration。
- 部署合同固定为 reader-first：旧进程全部 quiesce/restart 并部署支持 compact marker 的 reader 后，才允许显式 rotation；marker
  切换后禁止在同一 root 原地恢复旧 `HEAD`，应用回滚也只能回到支持 compact lineage 的 binary。更旧 reader 的 cutback 目前
  不受支持；若将来需要，只能停写后由新 reader exact-load，在**新 root**做离线 full-v1 export 与 event/manifest/membership
  identity 校验后切换，绝不能原地 rewind。self-hash 不提供认证或仓库外 rollback 检测；rotation 仍无自动 cadence，本合同
  不是仓库外 append anchor。
- compact 消除了热 checkpoint 的累计 manifest payload，但**没有**让整个 store 只物理保存一次 events：每代不可变 checkpoint
  都保留当时完整事件人口及 O(history) 身份胶囊，exact/rotation 仍按归档总量工作。因此只声称 hot-generation containment，
  不声称 cold maintenance 已达到市场规模。
- exact lineage loader 现在从当前代向前逐代读取一次，只保留 compact 基线 hash 摘要和最终 exact 输出需要的 tail rows，再按
  oldest-to-newest 重建并通过完整 canonical legacy validator；不会把所有 decoded checkpoint 缓存在内存。配对回归把同一
  5-manifest 逻辑 tip 按 1/2/4 个 rotation generation 持久化：hot load 始终只读 `HEAD + current checkpoint` 两个文件，exact
  load 对全部 7/8/10 个可达 JSON 各读一次，读取字节分别为 81,933/111,086/169,530，且 exact logical view 完全相同。
- `tracemalloc` 仅提供平台诊断：本轮 hot peak 约 0.284 MB，exact peak 约 0.690-0.724 MB，并由基于读取与输出字节的保守 affine
  envelope 防止明显的非线性回归；elapsed 不设门槛。该小型结构 fixture 不证明真实市场规模、RSS、cadence 或 SLO，整次 rotation
  仍包含独立的提交前/后验证阶段并保持显式、unscheduled，绝不能把 standalone exact pass 的单读事实扩写成整个 rotation 单遍。
- source-bounded runtime 现已能显式选择 segmented-hot reader，但 source/manifest ceiling 仍是 `contract_only_unwired`：没有 scheduler、
  Engine-0 policy/baseline、仓库外 append anchor、canonical/PIT 提升或生产权限。advisory lock 只约束合作 writer，不声称抵抗绕锁
  写入、断电级目录持久性或本地有效旧 `HEAD` 回滚；动态 PIT 市场 universe、market decision clock 与适用的
  production/backtest parity 仍是后续 blocker。

### Repository-external append anchor 决策合同（待用户选择）

- `data/v2/repository_external_append_anchor_decision_packet.json` 冻结 target-independent 合同与自哈希：一个获批
  anchor-genesis cutover 后，append/零事件 manifest/rotation 的每次 `HEAD.json` 迁移都必须在下一迁移或任何
  canonical 消费前外部追加并独立读回；仅 sequence 连续不够，append/rotation 必须证明从前一 external anchor 合法延伸。
- decision packet 本身不可原地回填；用户授权后要在 sequence-1 前新建 content-addressed selected-contract artifact 引用本
  packet。实际 cutover/anchor-gate 时钟不能回填进这份 pre-cutover contract，而要在 sequence-1 外部 commit 与独立 read-back
  后另写不可变 activation receipt；该 receipt 必须绑定获批且与 writer 分离的 read principal、target/locator、raw read evidence
  与 exact anchor-object hash，不能只记自报时间。`canonical_forward_eligibility_started_at` 继续为 null，等待另一次 canonical review。
- target 必须位于独立管理边界，提供 immutable retention、ordered append 或 predecessor CAS、strong latest/read-after-write、
  idempotent create 与 provider receipt。append/read/retention-admin principal ID 与 owner 分离；tracked contract 只保存 non-secret
  IAM/secret-store reference。
- A1-A14 冻结旧 HEAD、rollback-then-append、rotation、lost ack、gap/fork、cross-stream replay、remote ahead/behind、错误 target/
  retention receipt 与 outage fail-closed。anchor 只满足一个独立 promotion gate，不授予 source PIT、coverage、Engine-0、paper/live
  或交易资格，也不是 bounded scout 前置；cutover 只 prospective 生效，禁止追溯升级。
- 当前没有 provider/account/namespace、locked retention、principal ID/owner、secret reference、deployment owner 或显式实现授权，
  所以 `external_append_anchor_status=absent`、`canonical_reads_allowed=false`、`trade_enabled=false`；没有 connector、账号或凭据变更。

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
  全量 previous-event 链证明与原子写入；市场级外部覆盖、仓库外 append anchor 和 Engine-0/production runtime 接线仍待完成。
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
  初始 schema、M2 研究 ledger 与首个 SEC source-bounded coverage 实例不等于市场级 universe 完备、canonical provenance、
  runtime 或 execution parity 已完成。
- 当前 dynamic market-universe 与 Engine-0 都仅是 source-bounded research-only 合同；bounded scout 最高仍只能是 `research / observed_only lead`，不能获得 shadow/paper/promotion 结论。
- 若主动使用 V1 baseline，它只做兼容性回归与机会成本对照，不是 V2 Gate-1 锚。
- 原 V1 脏 checkout 的未提交 ticket 与产物没有迁入 V2 基线。

## 下一步

两个已运行 scout 均已关闭为 rejected；其 compact-log reflection 与 runner 单次执行完整性分别由
`exp-20260901-002/003` 修复并关闭为 accepted，未改写 `exp-20260901-001` 的终态证据。不得在已消费的 SEC frame 或
PCAOB count/H5/window/cost 上做近邻参数搜索。下一实验只接受
独立、outcome-blind 冻结且满足 fast-scout kernel 的新 surface/机制；若本地 surface 无合格候选，则回到 M2/M3 promotion construction。
并行的仓库外 append anchor 仍为 absent；其 connector、
A1-A14 和 shadow outage/rollback 演练继续等待用户选择并授权 provider/product、account/namespace、retention、principal、secret
reference、deployment owner、threat model、网络/成本与 cutover。真实 population/churn/retention/SLO 仍是自动 cadence 前提；
连续两个非阻断 M3 construction 单元后的 bounded、zero-ID、outcome-blind scout readiness preflight 已完成；已登记的
SEC/PCAOB/Moomoo/FINRA surface 均因 frozen input、PIT/授权/映射、重复/污染或新证据轴条件未满足而 fail closed，没有占用
experiment ID。输入身份与 reopen trigger 不变时复用本次结论，不重复完整 preflight。
source-bounded dynamic PIT market-universe snapshot 与 Engine-0 v3 的独立 hash/逐行 lineage 接线已完成。本轮成为最近一次
zero-ID preflight 后第二个非阻断 construction 单元；下一轮先常数时间比较冻结 blocker fingerprint，输入不变则复用
no-candidate 结论并建立共享 predictive feature/policy chain，不得借此升级 coverage、runtime/production 或 paper/live 权限。
仓库外 append anchor 仍由用户选择与授权。
