# Alpha Search Architecture

本文定义 Ginger 的 alpha **发现层**：怎样在正式实验之前生成、审查、冻结和选择候选假设。它解决的是“搜索什么”，不是“怎样放宽 Gate 让更多策略通过”。

本文是长期架构合同，不记录单次实验数字、每日状态或当前队列排名。具体规则仍以以下单一真相源为准：

- 实验生命周期、novelty / saturation / reopen：[`agent_experiment_protocol.md`](agent_experiment_protocol.md)
- canonical 窗口、指标、Gate 1-4：[`backtesting.md`](backtesting.md)
- 生产 / 回测一致性与真钱执行边界：[`production_backtest_parity.md`](production_backtest_parity.md)
- 机制先验、frozen zones 和当前研究方向：[`alpha-optimization-playbook.md`](alpha-optimization-playbook.md)
- 当前短记忆：[`alpha_context_pack.md`](alpha_context_pack.md) 与 [`current_state_snapshot.md`](current_state_snapshot.md)
- 实验记录格式：[`experiment_log_format.md`](experiment_log_format.md)
- 完整试验面板、`selection_scope_id`、DSR 与 Gate 5：[`deflated_sharpe_protocol.md`](deflated_sharpe_protocol.md)
- 组合级增量价值：[`portfolio_covariance_lane.md`](portfolio_covariance_lane.md)

如果本文与上述更具体的 Gate、实验或生产合同冲突，以更具体的合同为准。

## 1. 当前诊断

现有 [`quant/meta_research_engine.py`](../quant/meta_research_engine.py) 有价值，但它本质上是**历史研究先验与家族排序器**，不是 hypothesis generator：

- 当前固定权重更奖励历史 evidence、reproducibility 和 production feasibility，novelty 权重较低；
- 自由文本会被压缩到较粗的 `mechanism_family` / `trial_family`，不同机制可能进入同一桶，同一机制也可能因命名漂移被拆开；
- 最高优先级容易集中在已成功、容易接入的 adapter / sleeve 家族，形成 exploitation 偏置；
- 失败记录主要用于拒绝近邻重试，尚未系统地改变下一轮的生成分布；
- 系统通常预测“事件好坏”或“未来涨跌”，没有统一表示“市场当前相信什么、我们为何不同、差异是否已被定价”；
- 候选往往逐个产生、逐个占用实验 ID，完整的候选池没有在读取结果前冻结，搜索选择偏差难以追溯；
- 单策略冠军挑战会正确拒绝许多弱策略，但不能单独回答一个低相关 sleeve 是否有组合增量价值。

因此，当前系统的强项是**可复现证伪**，短板是**产生足够异质、可识别的候选**。目标不是提高 LLM temperature，也不是降低 Gate，而是把搜索变成独立、结构化、可审计的上游流程。

## 2. 设计原则

1. **生成与裁决分离。** Agent 可以大胆生成非共识假设；确定性 preflight、实验协议和风险系统决定它是否留下。
2. **预期差优先。** 一个事件本身不是 edge。候选应尽量表示为 `our_posterior - market_prior`，并说明价格如何收敛。
3. **市场预期必须可观察。** LLM 不得凭叙事编造 `market_prior`。没有可观察代理的候选只能是普通 event lead，不能标为 expectation-gap alpha。
4. **LLM 是有边界的语义层。** LLM 可做事件分类、关系映射、证据抽取和反证搜索；概率校准、排序、Gate 与交易动作由可回放代码负责。
5. **PIT 与 outcome blindness 先于收益。** 在候选池冻结前只允许检查来源合同、时间戳、密度、缺失率、集中度、候选交集和执行可行性，不得读取该候选的 forward return、结算标签或 Gate 结果。
6. **独立经济决策才是样本。** 每日重复行、多个 horizon、多个 comparator、同一事件的重复抓取都不能冒充独立样本。
7. **join 不是新数据源。** `component_sources` 必须逐项审计。任何成员源已饱和、frozen 或 PIT 不合格时，不能用 join 名义声明新源。
8. **三种 readiness 分开。** `economic_alpha_evidence`、`measurement_readiness`、`production_adapter_readiness` 不可互相代替；工程接得好不代表有 alpha。
9. **失败改变搜索后验。** 不同失败原因应减少不同类型的后续搜索，而不是统一归结为“再换一个阈值”。
10. **发现层不拥有交易权限。** 候选、preflight 和 selection panel 均不改变 entry、exit、ranking、sizing、orders 或 live 配置。

## 3. 目标流水线

```text
EvidenceSurface registry
  -> 预注册 SelectionScopeManifest（数据截止、生成器、三队列预算、允许的数据面、历史指纹快照 hash）
  -> 多角色批量 synthesis
  -> HypothesisCandidate + ExpectationGap
  -> outcome-blind D0-D3 preflight
  -> exploration / adjacent / exploitation 三队列
  -> 多样性约束排序
  -> 冻结 SelectionPanel（selection_scope_id + panel_hash）
  -> 最多选择一个正式验证对象，或一个预声明的固定 batch
  -> reserve / claim 实验 ID
  -> canonical Gate 1-4；需要时走组合级 lane；Gate 5 独立处理
  -> closeout + FailureReason
  -> 更新下一轮搜索先验、park / reopen 条件和 surface readiness
```

发现阶段使用自己的 `candidate_id` 和 `selection_scope_id`，**不占实验 ID**。只有候选已被选中、证据等级达到相应门槛并准备改变或检验策略行为时，才进入 `experiment.py new`。这样既不烧 ID，也不绕过任何 novelty、saturation、in-flight duplicate 或 reopen guard。

候选的建议状态机：

```text
draft -> validated -> preflight_passed -> panel_frozen -> selected
             |              |                  |
             v              v                  v
          invalid       parked/rejected     not_selected

selected -> experiment_reserved -> accepted/rejected/observed_only
```

`parked` 必须带定量 `reopen_condition`；`rejected` 必须带闭集 failure reason。禁止通过编辑旧 ledger 行让候选“重新通过”，状态变化应作为新事件追加。

## 4. 核心合同

第一阶段的核心类型放在 `quant/alpha_search_contract.py`。默认采用 frozen dataclass，并提供 `from_dict()`、`to_dict()` 和 `validate()`；不为这层引入新的运行时 schema 框架。所有合同都有 `schema_version`，未知版本 fail closed。

### 4.1 机制指纹

`fingerprint` 取代以自由文本关键词作为新候选的主要身份。它至少包含：

```yaml
fingerprint:
  data_source: canonical_primary_source_key
  component_sources: []
  expectation_proxy: direct_implied_probability
  economic_mechanism: policy_probability_repricing
  decision_surface: candidate_pool
  payoff_shape: long_convex_event_drift
  horizon: H5_H20
  execution_dependency: liquid_cash_equity
  portfolio_role: orthogonal_event_sleeve
```

字段含义：

| 字段 | 合同 |
|---|---|
| `data_source` | 主证据面的 canonical key；不能用 join 名称掩盖成员源 |
| `component_sources` | 所有参与计算的独立源，排序后保存；每个源单独做 readiness / saturation 审计 |
| `expectation_proxy` | 市场预期如何被观察，而不是“事件类型” |
| `economic_mechanism` | 信息为何改变现金流、贴现率、风险承受或供需约束 |
| `decision_surface` | `entry`、`exit`、`ranking`、`candidate_pool`、`notional_scalar`、`allocator`、`observer` 等 |
| `payoff_shape` | 趋势、均值回归、相对价值、carry、event drift、convex / asymmetric 等 |
| `horizon` | 预声明的经济收敛窗口，不是看结果后选择的最佳窗口 |
| `execution_dependency` | 流动性、借券、期权、盘中时效、容量等关键依赖 |
| `portfolio_role` | core replacement、independent sleeve、hedge、tail reducer、observer 等 |

指纹是 novelty、相似度和多样性计算的主要输入；自由文本标题仅用于解释。对历史日志可保留兼容分类器，但不得继续把粗关键词 family 当作新搜索的唯一身份。

### 4.2 `EvidenceSurface`

`EvidenceSurface` 是可归因候选行 / forward 行及其生成器的注册合同。推荐最小结构：

```yaml
surface_id: prediction_market_event_observer
schema_version: 1
name: Prediction-market event probability observer
data_source: polymarket
component_sources: [polymarket]
artifact_locators: []
provenance:
  provider: polymarket
  license_or_permission: public_api_with_recorded_terms
  immutable_vintage_or_hash: null
clocks:
  observed_at_field: observed_at
  published_at_field: null
  effective_at_field: null
  timezone: UTC
pit_contract:
  status: partial
  issuer_mapping_effective_dated: false
  leakage_notes: []
coverage:
  raw_rows: 0
  candidate_rows: 0
  independent_decisions: 0
  settled_independent_decisions: 0
  candidate_overlap_count: 0
  concentration: {}
readiness:
  source_contract: pass|partial|fail
  market_expectation_identifiable: pass|partial|fail
  outcome_ledger: pass|partial|fail
  gate_ready: false
saturation:
  status: unknown|open|saturated|frozen|parked
  reopen_condition: null
last_refreshed_at: null
```

强制不变量：

- `surface_id` 稳定，不能随日期变化；日期属于 artifact 或 snapshot；
- `raw_rows`、`candidate_rows`、`independent_decisions`、`settled_independent_decisions` 分开；
- readiness 必须引用机器可查 artifact，而非 LLM 自述；
- `settled_independent_decisions` 的单位是独立经济冲击 / 决策，不是 ledger 行数；
- registry snapshot 是派生视图，来源仍是 append-only 事件或可重建 manifest；
- 任何 `component_sources` 变化都会产生新的合同版本或 surface 版本，不得静默修改历史含义。

### 4.3 `ExpectationGap`

`ExpectationGap` 可作为 `HypothesisCandidate` 内的结构化 value object。它回答五个问题：市场相信什么、我们的独立证据是什么、我们的后验是什么、差异多大、怎样变成可交易 payoff。

```yaml
market_prior:
  proxy_type: direct_implied|explicit_consensus|price_revealed|positioning_constraint
  surface_id: null
  as_of: null
  value: null
  unit: probability
  distribution: null
  uncertainty: null
  calibration_reference: null
  observability_grade: direct|strong_proxy|weak_proxy|missing

independent_evidence:
  - evidence_id: null
    surface_id: null
    known_at: null
    independence_from_prior: null
    extracted_state: null
    provenance_locator: null
    llm_trace: null

our_posterior:
  value: null
  unit: probability
  method: null
  calibration_reference: null
  confidence_interval: null
  as_of: null

expectation_gap:
  signed_value: null
  unit: probability_points
  pricing_map: null
  gross_expected_payoff: null
  costs_and_carry: null
  net_expected_payoff: null

transmission:
  affected_tickers: []  # lead / observer 可暂空，但 D2 会 park；observed_only / gate_candidate 必须已解析
  expected_direction: null
  catalyst: null
  half_life: null
  causal_steps: []

why_not_arbitraged: null
falsifier: null
```

市场预期代理按解释力分层：

1. 直接隐含概率：要约价差、期权、预测市场；
2. 显式共识：分析师预测、公司指引、修正轨迹；
3. 价格揭示代理：事件前价格路径、波动率、相关资产响应；
4. 仓位 / 约束代理：借券、拥挤、资金流、成交与流动性。

这些层级不是可互换的精度标签。弱代理必须明确不确定性，不能被 LLM 升格成“市场概率”。`our_posterior.value` 必须来自版本化、可回放的校准或确定性规则；LLM 只可产生 `extracted_state`、方向映射或结构化理由。若缺少校准，posterior 应为 `null`，候选保持 `lead`。

同一数据不得同时充当 prior 和“独立”证据。例如预测市场概率变化可以是 `market_prior`，但不能再作为证明该概率错误的唯一 `independent_evidence`。

### 4.4 `HypothesisCandidate`

建议的 v1 合同：

```yaml
candidate_id: cand-<stable-content-id>
schema_version: 1
created_at: null
created_by: null
search_queue: exploration|adjacent|exploitation
title: null
hypothesis: null
fingerprint: {}
surface_ids: []

market_prior: {}
independent_evidence: []
our_posterior: {}
expectation_gap: {}
transmission: {}
why_not_arbitraged: null
falsifier: null

baseline:
  universe: []
  policy: null
treatment:
  policy: null
replacement_value_comparator: null
expected_horizon: null

execution_envelope:
  intended_instrument: null
  liquidity_dependency: null
  costs_and_carry: null
  borrow_dependency: null
  capacity_constraint: null
  timing_constraint: null

evidence_grade: lead|observer|observed_only|gate_candidate
source_readiness_snapshot: []
prediction:
  success_probability: null
  main_failure_modes: []
  confidence_reason: null
reopen_condition: null
```

最小校验：

- ID、版本、时间、队列和完整机制指纹非空；
- `surface_ids` 与 `fingerprint.component_sources` 能在 registry 中解析；
- `falsifier`、baseline、treatment、horizon 和 replacement comparator 在看结果前存在；
- expectation-gap 候选必须有可观察 prior；否则降级为普通 `lead`；
- `gate_candidate` 必须达到 canonical PIT 覆盖，不能由文字声明提升；
- `prediction.success_probability` 是研究校准，不是仓位或真钱置信度；
- 未定义执行依赖时不能进入正式选择；
- 一个 candidate 只能表示一个可归因决策假设或一个预冻结 policy bundle。

### 4.5 `FailureReason` / `FailureTaxonomy`

失败类型使用闭集 key，细节保留在 `failure_detail`，不得用不断变化的自然语言作为统计主键。v1 至少覆盖：

| Key | 含义 | 对下一轮搜索的影响 |
|---|---|---|
| `no_gross_edge` | 成本前经济映射已无 edge | 下调该 source × mechanism；禁止用执行微调救援 |
| `already_priced` | 信息存在，但事件时点已被价格吸收 | 只有更早 PIT 时钟或新的 expectation proxy 才可重开 |
| `wrong_transmission_mapping` | 事实可能有效，但 ticker / 方向 / horizon 映射错误 | 可保留 surface；新映射必须有独立机制证据，不能只换阈值 |
| `no_candidate_overlap` | 来源与可交易池没有真实交集 | park，按交集计数设置 reopen condition |
| `market_expectation_unidentified` | 没有可观察 prior | 降级为普通 event lead，不得声称 expectation gap |
| `pit_or_source_failure` | publication clock、vintage、issuer map、权限或来源合同失败 | 转 measurement repair 或 park；不得读价格继续跑 |
| `cost_and_carry` | gross edge 被费用、持有期或资本占用吃掉 | 同一执行包络下禁止响应函数 retune |
| `borrow_or_capacity` | 借券、流动性或容量令交易不可执行 | 下调该 instrument mapping；信号本身与执行失败分开记录 |
| `core_opportunity_cost` | standalone 有收益但不值得挤出 core | 可转组合观察或独立资金来源；不得冒充 core replacement |
| `concentration` | 结果依赖少量 ticker / 事件 / 日期 | 等待独立广度或新 universe，禁止事后切片保 winner |
| `tail_risk` | 平均收益不能补偿尾部或 drawdown | 只有真正的新 payoff / risk gate shape 才可重开 |
| `insufficient_independent_rows` | settled 行多但独立决策不足，或样本未成熟 | 保持 observer；按独立 settled count 定量重开 |
| `duplicate_or_frozen` | 与已探索 / in-flight / parked family 冲突 | 不进入 panel；遵循现有 novelty / reopen 合同 |
| `incomplete_selection_panel` | 候选池、预期计数或 hash 不完整 | 研究流程失败；不得选择、reserve 或声称 DSR |
| `outcome_contamination` | 选择前读取了候选结果 | 整个 selection scope 作废并重新冻结新 scope |

一次 closeout 必须有一个 `primary_failure_reason`，可以有若干 `secondary_failure_reasons`。旧日志映射到 taxonomy 时保留原始文字与映射置信度；不得重写历史 source-of-truth。

失败后更新的是**生成与选择先验**，不是自动改变 Gate。聚合失败惩罚应至少按 `fingerprint` 的 source、mechanism、transmission、execution dependency 分解，避免“借券失败”错误地冻结底层信息源，也避免“无 gross edge”只惩罚 adapter 工程。

## 5. 三条搜索队列

三队列用于约束候选生成分布，不是三套 Gate。

| 队列 | 目的 | 合法候选 | 主要评分 |
|---|---|---|---|
| `exploration` | 进入新的信息或机制区域 | 新独立数据源、新 expectation proxy、新经济机制或真正不同的 payoff | 信息增益、机制独立性、可证伪性 |
| `adjacent` | 在已有证据旁做有因果解释的扩展 | 新 transmission、独立交叉证据、不同 portfolio role，但须满足 novelty 规则 | 与现有证据的连接强度、相似度惩罚、执行可行性 |
| `exploitation` | 把成熟证据转成可验证候选 | settled forward 增长、已接受 default-off surface、完整 PIT replay | 数据成熟度、replacement value、生产一致性 |

每个 synthesis scope 在生成前冻结各队列预算，并在 report 中记录计划与实际数量。默认应确保三条队列都有非零覆盖；具体比例是版本化研究配置，不在本文固化，也不得根据本轮结果回填比例。

多样性不能只靠随机采样。候选池至少对以下维度计算覆盖和相似度：

- `data_source` / `component_sources`
- `expectation_proxy`
- `economic_mechanism`
- `decision_surface`
- `payoff_shape`
- `horizon`
- `execution_dependency`
- `portfolio_role`
- `primary_failure_risk`

禁止一个高分 adapter family 占满面板。先在每条队列内选代表，再做跨队列排序；若某队列没有合法候选，必须记录空缺原因，而不是用 exploitation 自动填满。

## 6. 多 Agent synthesis 角色

LLM Agent 不直接输出买卖，而是各自提交有 provenance 的合同片段：

| 角色 | 产出 | 禁止 |
|---|---|---|
| 共识 Agent | `market_prior`、主流叙事、可观察代理和不确定性 | 用自身常识冒充市场概率 |
| 反共识 Agent | 与 prior 独立、时间可验证的矛盾证据 | 为了“非共识”而挑低概率故事 |
| 机制 Agent | 因果 transmission、catalyst、half-life、why-not-arbitraged | 只写相关性或主题相似性 |
| 执行 Agent | 成本、借券、容量、时效、资本与 instrument mapping | 把 paper notional 当真钱下单规模 |
| 反证 Agent | falsifier、替代解释、baseline、replacement comparator、失败分类 | 在看到 outcome 后改 falsifier |

建议顺序是独立草拟后再合并，避免首个叙事锚定所有角色。编排器只接受能解析为合同、引用 registry surface 并通过确定性校验的输出。角色冲突应保留在 candidate 中；不确定时 abstain，而不是由“多数 Agent”投票制造置信度。

## 7. Outcome-blind preflight

Preflight 在任何候选 forward outcome、收益路径或 Gate metric 被读取前运行。它是发现阶段的硬门，不占实验 ID。

### D0：Source / PIT readiness

- surface 与所有 component source 均已注册；
- immutable vintage / hash、publication clock、时区、有效日期和 issuer mapping 可追溯；
- 权限与 attribution 合同存在；
- raw density、candidate density、独立决策数、missingness、集中度和候选交集达到预声明最低值；
- join 成员逐项完成 saturation / frozen / parked 自查；
- 数据等级只能由机器证据决定。

### D1：Market expectation identifiability

- prior 来自可观察代理，含 `as_of`、单位、不确定性和 source locator；
- prior 与 independent evidence 没有循环引用；
- posterior 的数值方法和校准面可回放；
- 无可观察 prior 时，只能降级为 event lead。

### D2：Economic mechanism and executability

- transmission、方向、catalyst、half-life 与 why-not-arbitraged 完整；
- baseline、treatment、replacement comparator 和 falsifier 已冻结；
- 简单 gross mapping 有足够候选交集，复杂 plumbing 不先于机制证据；
- 成本、carry、借券、容量、时效和资本占用已声明；
- signal 与 instrument mapping 分离。

### D3：Search integrity

- 结构化指纹与历史、frozen、parked 和 in-flight 工作完成相似度审计；
- 候选属于预冻结的三队列预算，覆盖约束满足；
- 候选池预期数量、实际数量、缺失候选和拒绝理由完整；
- selection rule、score version 和 tie-breaker 已冻结；
- outcome access audit 明确为 clean。

建议 `PreflightDecision` 最小结构：

```yaml
candidate_id: null
schema_version: 1
evaluated_at: null
preflight_version: null
data_cutoff: null
outcome_blind: true
outcome_fields_excluded: []
source_snapshot_hashes: []
gates:
  D0: {status: pass|park|reject, reasons: []}
  D1: {status: pass|park|reject, reasons: []}
  D2: {status: pass|park|reject, reasons: []}
  D3: {status: pass|park|reject, reasons: []}
decision: pass|park|reject
failure_reasons: []
reopen_condition: null
```

Outcome-blind 阶段允许读：source metadata、时间戳、schema、缺失率、行密度、issuer / universe 交集、独立事件聚类、当时可知的交易约束。禁止读：候选 forward return、结算结果、最佳 horizon、候选特有 Gate 指标，或任何用于事后挑 winner 的 outcome label。若无法证明没有读结果，使用 `outcome_contamination` 令整个 scope 失效。

## 8. 排序与 Selection Panel

只有 D0-D3 通过的候选参与正向排序；park / reject 行仍保留在完整面板中。排序分数只使用 outcome-blind 特征，建议由下列版本化分量组成：

```text
+ expectation identifiability
+ information gain
+ mechanism independence
+ evidence maturity
+ execution feasibility
+ falsifiability
+ portfolio orthogonality proxy
- similarity to existing candidates
- matching historical failure posterior
- unresolved source/PIT risk
```

分数是研究优先级，不是交易信号、仓位或成功概率。权重必须固定、透明并记录版本；不得用本轮 forward outcome 调权。

`SelectionPanel` 至少保存：

```yaml
selection_scope_id: scope-<timestamp-or-stable-id>
schema_version: 1
created_at: null
data_cutoff: null
scope_manifest: {}
scope_manifest_hash: null
surface_registry_hash: null
prior_fingerprint_snapshot_hash: null
prior_fingerprint_count: 0
selector_version: null
score_version: null
queue_budgets: {}
expected_candidate_count: 0
candidate_pool_complete: true
candidate_ids: []
candidate_snapshot_hashes: {}
preflight_decision_hashes: {}
scores: {}
rejection_reasons: {}
selected_candidate_id: null
selection_reason: null
panel_hash: null
outcome_blind: true
```

关键约束：

- `candidate_ids` 是**排序前的完整候选池**，包括 preflight reject / park / not-selected；
- scope manifest 必须在候选生成前独立落盘，固定 `preregistered_at <= data_cutoff <= freeze_at`、允许的数据面、生成配置、候选数和队列预算；候选只能在 data cutoff 之后、freeze 之前生成；
- D3 使用的历史机制指纹集合必须由 `prior_fingerprint_snapshot_hash + count` 固定；build 与 verify 都必须提交同一外部快照，禁止用空历史绕过 duplicate / frozen 检查；
- 一个 scope 最多有一个 `selected_candidate_id`，除非 scope 在生成前声明为固定 batch，并把整个 batch 视为一个可归因 selection policy；
- `panel_hash` 对除自身外的 canonical JSON 做 SHA-256；canonicalization 由共享代码唯一实现；
- hash 在读取 outcome、reserve 实验 ID 或运行回测前计算并冻结；
- 任何 candidate、分数、拒绝理由或选择变化都会产生新 scope / 新 hash，不能覆盖旧行；
- `candidate_id` 是跨 scope 稳定的机制语义 ID；ledger 中的 `candidate_snapshot` 自然键是 `(selection_scope_id, candidate_id)`，使新 scope 可以冻结新的 readiness / 时间快照，同时保证同一 scope 内的内容不可改写；
- 第一阶段 ledger 只追加 `candidate_snapshot`、`preflight_decision`、`panel_selection`；outcome link 属于后续阶段，必须使用独立记录类型追加，不能改写 selection 事件；派生 latest report 可重建。
- 可信复核必须同时提供独立保存的 scope manifest、证据面 registry 和历史指纹快照，重新计算每个 D0-D3；只检查面板内部 hash 只能证明结构自洽，不能充当外部锚。

### 与 Gate 5 selection panel 的关系

发现层 `SelectionPanel` 证明“研究者从哪些候选中选了谁”。它**不会自动成为 DSR 证据**。Gate 5 仍要求 [`deflated_sharpe_protocol.md`](deflated_sharpe_protocol.md) 定义的完整、可比 return-stream trial panel：同一窗口、周期、日期、成本、协议和 PIT 版本，且含所有尝试配置。

二者应共享 `selection_scope_id` 并互相引用 hash；只有发现候选恰好构成完整可比试验池时，才可显式升级为 Gate 5 panel。发现层 `panel_hash`、历史 `prior_trial_count` 或候选摘要都不能替代 DSR recomputation。

## 9. Gate 与组合边界

发现层不修改现有 Gate：

- `lead`：只有 snapshot 或机制草案；不得改变策略或声称 alpha；
- `observer`：PIT forward 尚未结算；固定公式、schema 和 reopen count，继续观察；
- `observed_only`：有足够 settled attribution，但还没有 canonical PIT Gate 证据；
- `gate_candidate`：source、PIT、独立样本与 replay 条件满足，才可 reserve 正式实验；
- 任何影响交易行为的候选随后仍须按实验协议执行 Gate 1-4 和生产 parity；
- standalone 未击败 core 不自动等于组合无价值；符合条件时按 [`portfolio_covariance_lane.md`](portfolio_covariance_lane.md) 走既有组合级口径，不能在发现层自创豁免；
- Gate 5 只控制 `live_eligible` 的 trial-adjusted 证据，不推翻 Gate 4 的 default-off paper 结论；
- 发现分数、Agent 共识、market probability 或 LLM confidence 都不能直接驱动 sizing、slots、exits 或 orders。

## 10. 失败反馈如何改变搜索分布

每轮 closeout 将结构化 failure 写回研究 ledger，并更新下轮候选生成的先验：

```text
FailureReason
  -> 定位失败层（source / prior / evidence / transmission / execution / portfolio）
  -> 更新对应 fingerprint 维度的惩罚
  -> 写入 forbidden-neighbor 或定量 reopen condition
  -> 保留未被证伪的层
  -> 下一轮三队列预算与候选排序读取该后验
```

示例：

- `cost_and_carry` 否定当前执行包络，不自动否定原始信息；
- `wrong_transmission_mapping` 不应把数据源整体冻结，但也不允许无依据逐 ticker 试错；
- `no_gross_edge` 优先否定 source × mechanism，不能靠 adapter 或阈值包装继续搜索；
- `already_priced` 要求更早的 timestamp 或不同 prior，而非改 hold days；
- `core_opportunity_cost` 可以保留为独立 sleeve lead，但必须证明资金来源和组合增量；
- `insufficient_independent_rows` 只推进 observer，不消耗实验 ID。

惩罚应有衰减或明确 reopen 证据，但不能因时间经过自动解除硬 frozen / parked 规则。机器 guard 仍由既有实验协议负责。

## 11. 研究节奏

建议把“采集”“合成”“实验”分离：

- **每日**：刷新注册 surface、追加 observer、更新 outcome settlement、独立事件聚类与 readiness 计数；例行物化不占实验 ID。
- **每周或证据显著变化时**：创建一个 selection scope，运行多角色 batch synthesis、D0-D3、三队列覆盖和 panel freeze；未成熟候选留在 ledger。
- **触发式正式实验**：只有选中候选达到 `gate_candidate`，或预冻结的 observed-only attribution 达到其 reopen count，才 reserve 一个实验 ID。
- **每月或足够 closeout 后**：检查 FailureReason 分布、三队列命中与校准、source / mechanism 覆盖、panel completeness 和 Agent 的 Brier / failure-mode calibration；不得据同一批 outcome 反复调权再重选。

研究吞吐不以实验 ID 数量衡量。更有意义的指标包括：合法候选率、expectation prior 可识别率、独立 settled decision 增长、不同 mechanism 覆盖、panel 完整率、outcome contamination 次数、每类 failure 对后续重复率的下降，以及最终进入 Gate 的候选质量。

## 12. 第一阶段交付

第一阶段只建设发现基础设施，不改策略、订单或 Gate。

### 必须交付

1. `quant/alpha_search_contract.py`
   - frozen `HypothesisCandidate`、`EvidenceSurface`、`PreflightDecision`、`SelectionPanel`；
   - 闭集 `FailureReason`；
   - `from_dict()` / `to_dict()` / `validate()`；
   - canonical serialization 与 deterministic `panel_hash`。
2. `quant/alpha_search_registry.py`
   - surface 注册、查询与 readiness snapshot；
   - component-source 展开和 settled / independent count；
   - 只读暴露 saturation、frozen、parked 与 reopen condition。
3. `quant/alpha_search_ledger.py`
   - append-only `candidate_snapshot`、`preflight_decision`、`panel_selection` 事件；
   - 原子写入、scope-aware 幂等 event identity、派生 report 可重建；
   - 第一阶段不写 outcome link；后续如增加，只能追加独立事件，不能改写 selection 事件。
4. `scripts/alpha_search.py`
   - CLI：`validate-candidate`、`preflight`、`build-scope`、`build-panel`、`verify-panel`、`report`、`failure-map`；
   - `build-panel` / `verify-panel` / `report` 强制读取外部 scope manifest、surface registry 与 prior-fingerprint snapshot；仍不得自动 reserve 实验。
5. focused tests
   - schema round-trip；
   - 缺 prior、缺 falsifier、非法 evidence-grade transition fail closed；
   - 输入顺序变化不改变 canonical hash；
   - 任一候选、分数或拒绝理由变化会改变 hash；
   - panel 缺行、重复 candidate、多个 winner、outcome contamination 被拒；
   - join component source 不能被折叠成“新源”。
6. 兼容输出
   - 保留现有 meta report 和历史 family 排序；
   - 新 discovery report 与 legacy report 并行，不重解释或重写历史日志；
   - 对旧自然语言 failure 的映射保留 raw text 与 mapping confidence。

### 第一阶段非目标

- 不实现 Agent 自动调用或 prompt orchestration；
- 不把 prediction-market observer 变成交易信号；
- 不改变 `quant/run.py`、backtester、ranking、sizing、orders 或 live 配置；
- 不放宽 novelty、saturation、Gate 1-4、Gate 4-P 或 Gate 5；
- 不自动 reserve / claim / close 实验；
- 不用历史收益拟合 discovery score 权重；
- 不补写、覆盖或“清洗”既有实验 source-of-truth；
- 不把 schema / adapter 完成度计作经济 alpha evidence。

第一阶段完成的验收标准是：系统能够在不读取 outcome 的情况下，验证一批结构化候选、保留全部拒绝原因、冻结唯一可重算的 panel hash，并生成下一位 Agent 可继续的 report。它不需要、也不应声称已经找到 alpha。

## 13. Prediction-market 后续校准样板

[`quant/prediction_market_event_observer.py`](../quant/prediction_market_event_observer.py) 适合做第一块 expectation-gap 校准样板，因为概率本身是可观察 prior，且现有路径已保持 observer-only。但它进入验证前仍需补齐：

1. **稳定市场身份**
   - provider 的 `market_id` / condition / outcome token；
   - 问题文本变化不产生新市场；
   - resolution rule、close time、resolved outcome 和 source timestamp 可追溯。
2. **概率冲击而非每日行**
   - 固定窗口 `delta_probability`、velocity、acceleration；
   - volume、liquidity、spread 或可得的质量代理；
   - 同一市场的连续日行按独立概率 shock 聚类；重复抓取和多 horizon 不增加样本数。
3. **独立证据与语义映射**
   - prior 是预测市场概率；独立证据来自官方事实、SEC、新闻原文或其他非循环来源；
   - LLM 输出事件 taxonomy、影响路径、ticker 方向、证据 span、版本、置信与 abstention；
   - ticker relation 必须是 PIT、可回放映射，不靠模型常识隐藏补全。
4. **价格与约束响应**
   - Moomoo 精确时间的价格 / 成交 / 资金流用于判断 public ticker 是否同步反应；
   - ORTEX / borrow 用于判断拥挤、借券或仓位约束是否延迟传导；
   - 这些连接是机制证据，不构成“新数据源 join”豁免。
5. **结算与校准**
   - 保存 market probability calibration、事件 outcome 与 ticker H5/H10/H20 replacement value；
   - 按市场 / 事件 shock 聚类独立样本；
   - 在 settled shocks 达到预声明门槛前保持 `observer`；
   - 达标后先冻结完整 selection scope，再做一次固定 batch 验证，禁止主题逐项一 ID 或逐项调阈值。

样板的最小候选表达应是：

```text
market_prior = 某事件在 t 时刻的可交易隐含概率
independent_evidence = t 时刻已发布、与该市场报价独立的事实变化
our_posterior = 用历史已结算事件校准后的概率
expectation_gap = posterior - prior
transmission = 事件 -> 现金流/风险 -> public ticker -> 预期收敛窗口
constraint = 价格是否已反应，以及拥挤/借券/流动性是否延迟传导
```

在完成稳定 ID、独立 shock、PIT 映射和结算校准前，这个 surface 仍是 observer，不是 alpha。它的价值首先是验证本文合同能否区分“有市场预期的事件”“只有叙事的事件”和“重复行制造的伪样本”。

## 14. 审计与演进

发现层每次 schema 或 score version 变化都应回答：

- 是否改变了候选身份、novelty 或 queue 路由？
- 是否改变了 preflight 可见字段，从而破坏 outcome blindness？
- 是否改变了 panel canonicalization 或历史 hash 可重算性？
- 是否把某种 readiness 错当成 alpha evidence？
- 是否需要迁移派生 snapshot，而非改写 append-only ledger？

新字段默认先做可选、read-only attribution。只有它改变候选选择或搜索后验时，才需要版本化 selector / preflight；只有它改变交易行为时，才进入正式实验与 Gate。发现层的成功标准不是“让更多候选通过”，而是让每个被选择、被拒绝和被 park 的候选都有可追溯理由，并让失败真正改变下一次搜索的位置。
