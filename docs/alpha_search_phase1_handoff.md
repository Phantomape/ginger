# Alpha Search Phase 1 Handoff — 2026-07-21

## 1. 结论先行

第一阶段已经完成一轮真实、冻结、outcome-blind 的候选搜索，但**没有发现可以进入收益验证的候选**：预注册的 3 个候选中，2 个被拒绝，1 个被停放，最终选择数为 0。

这不是 alpha 成功，也不是策略失败；它证明新的发现层开始发挥作用：在读取候选 forward return、占用实验 ID 或改变交易逻辑以前，就识别出来源合同、候选交集、实体映射和 frozen / parked 状态不满足要求。

本轮没有：

- 读取候选收益或 Gate 结果；
- reserve 实验 ID；
- 修改 entry、exit、ranking、sizing 或订单；
- 启用 paper / live 交易；
- 声称已经找到 alpha。

## 2. 与三条 Alpha 主线的关系

长期赚钱方向仍以 [`alpha_engine_strategy.md`](alpha_engine_strategy.md) 为准：

1. 市场预期差 / 语义事件；
2. 相对价值与错误定价收敛；
3. 组合级低相关 sleeve 与风险预算。

本轮不是新增第四条主线，而是为三条主线共同建设上游的**搜索与选择机制**。错误定价收敛仍是优先落地方向；但任何候选都必须先回答“市场预期是什么、独立证据是什么、为什么会收敛、与现有策略的机会成本是什么”，再进入收益实验。

长期架构和字段合同见 [`alpha_search_architecture.md`](alpha_search_architecture.md)。

## 3. 冻结范围

```yaml
scope_name: phase1-alpha-search-20260721
selection_scope_id: scope-8ce58d769661245b96dcfdbf
data_cutoff: 2026-07-21T08:01:00Z
freeze_at: 2026-07-21T08:04:00Z
candidate_count: 3
queue_budget:
  exploration: 1
  adjacent: 1
  exploitation: 1
selection_limit: 1
outcome_blind: true
trade_enabled: false
experiment_id_reserved: false
panel_hash: 729cf34a5675e1428d72b378c5f28eddb9b32f710855c0ce0cc517df46363fe8
```

候选生成配置、允许使用的 evidence surfaces、历史 fingerprint 快照、候选数量和冻结时间都在结果出现以前绑定。验证器必须从外部重新载入这些锚点并重跑 D0-D3，不能只相信 panel 自己携带的副本。

## 4. 第一轮候选与裁决

| 队列 | 候选 | 裁决 | 主要原因 | 当前允许的动作 |
|---|---|---|---|---|
| exploitation | `cand-c0da7d6c3657fd93d4c6`：一致预期修订后的价格反应不足 | park | estimate-revision 来源合同未 ready；issuer / ticker 映射未解决 | 只做 outcome-blind 时钟、实体映射和独立 overlap 审计；不得读收益或 reserve ID |
| adjacent | `cand-ecb99b450542c0cdc11c`：一致预期修订与 Moomoo 资金流分歧 | reject | Moomoo 面已 parked、无候选交集；estimate 来源合同未 ready；实体映射未解决 | 停止 join/阈值 retune；只有满足既定 reopen count 或引入真正独立的新证据面才可重开 |
| exploration | `cand-fb98566f716d882e09a7`：预测市场先验与官方确认的概率差 | reject | prediction-market 面已 parked、SEC 面已 saturated、无 issuer overlap；实体映射未解决 | 停止 SEC × prediction-market 的近邻拼接；只有满足原 reopen 条件才重开 |

聚合失败原因：

- `no_candidate_overlap`: 3
- `duplicate_or_frozen`: 2
- `pit_or_source_failure`: 2

因此 `selected_candidate_ids=[]`。固定选择器没有为了“必须产出一个策略”而放宽门槛。

## 5. Alpha Synthesis Pass

```yaml
baseline_universe:
  - current eligible cash-equity candidate pool
  - cash
  - SPY
  - QQQ
opportunity_cost_winner: null
evidence_surfaces_used:
  - estimate_revision_consensus_observer
  - moomoo_capital_flow_day_observer
  - ohlcv_price_revealed_context
  - prediction_market_event_probability_observer
  - sec_official_event_evidence
evidence_surfaces_missing:
  - gate-ready explicit expectation surface with point-in-time issuer overlap
  - resolved issuer/ticker transmission map
  - sufficient independent cash-conflict decisions
hypothesis_candidates:
  - muted price response after consensus revision
  - consensus revision versus positioning disagreement
  - prediction-market prior versus official confirmation
selected_hypothesis: null
economic_mechanism: expectation gap followed by delayed information transmission and repricing
falsifier: exact-clock placebo, ticker shuffle, absent overlap, or failure versus displaced core candidate and cash
evidence_grade: lead
next_machine_action: complete only the outcome-blind source-contract and issuer-overlap audit for the exploitation candidate; do not read returns or reserve an experiment
```

`opportunity_cost_winner` 为 `null`，因为 outcome-blind 阶段不能读取候选收益；机会成本比较已经预先写入每个候选的 replacement-value comparator，只有候选先通过发现层才执行。

## 6. 第一阶段实现

- 冻结合同：`EvidenceSurface`、`ExpectationGap`、`HypothesisCandidate`、`PreflightDecision`、`SelectionPanel` 和闭集 `FailureReason`；
- D0-D3：来源/PIT、预期可识别性、传导映射、novelty/saturation/reopen；
- 三队列候选预算与多样性选择器；
- 语义候选 ID、source readiness 快照、scope / registry / prior-fingerprint 外部锚点；
- 全递归 outcome 字段拒绝；
- append-only 发现账本，整批原子写入、自然键去重和冲突回滚；
- CLI：候选校验、preflight、scope 构建、panel 构建与复核、报告和 failure map；
- 发现层与交易层硬隔离。

## 7. 机器产物与复核

- Evidence registry：[`../data/reference/alpha_search_evidence_surfaces.json`](../data/reference/alpha_search_evidence_surfaces.json)
- 预注册 scope：[`../data/alpha_search/phase1_scope_manifest_20260721.json`](../data/alpha_search/phase1_scope_manifest_20260721.json)
- 候选池：[`../data/alpha_search/phase1_candidate_pool_20260721.json`](../data/alpha_search/phase1_candidate_pool_20260721.json)
- 冻结 panel：[`../data/alpha_search/phase1_selection_panel_20260721.json`](../data/alpha_search/phase1_selection_panel_20260721.json)
- 发现账本：[`../data/alpha_search/events.jsonl`](../data/alpha_search/events.jsonl)
- 可读报告：[`../data/alpha_search/latest_report.json`](../data/alpha_search/latest_report.json)

复核结果：

- 严格外部锚点验证：`valid=true`；
- panel：3 candidates、0 selected、`outcome_blind=true`、`trade_enabled=false`；
- ledger：7 records（3 candidate snapshots + 3 preflights + 1 panel）；
- 同一 scope 重跑后仍为 7 records，证明 append 幂等；
- 聚焦测试：104 passed；独立 consistency review 的 2 个 P1 已修复，无未解决 P0/P1。

## 8. 下一步边界

下一步只推进最接近可检验状态的 exploitation 候选：把 estimate-revision 的来源合同、决策时钟和 issuer/ticker overlap 做成机器可核对的 readiness 证据。只有当预声明 reopen 条件得到满足，且 D0-D3 全部通过，才允许进入 `experiment.py new` 和 canonical Gate 1-4。

若 overlap 仍不足，正确动作是继续停放并寻找真正独立的新 expectation surface，而不是换阈值、继续做 Moomoo/SEC join，或让 LLM 猜一个市场先验。
