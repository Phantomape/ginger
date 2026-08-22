# Alpha Mechanism Generator

状态：`exp-20260727-002` 实现首个版本化外部机制生成器合同。本文定义“怎样把一个
LLM/skill 的新机制启发接进 alpha search”，不定义交易策略，也不替代
[`alpha_search_architecture.md`](alpha_search_architecture.md)、
[`research_digest_pipeline.md`](research_digest_pipeline.md) 或 D0-D3。

## 1. 它在流水线中的位置

```text
外部事实与一手来源
  -> versioned mechanism generator（当前：ai_berkshire_bottleneck）
  -> staging scan JSON（0-2 个 lead；允许空）
  -> fail-closed validator / renderer
  -> 生成后才读取历史失败作 veto
  -> External Research Map + digest provenance
  -> Alpha Agent 挑选 / 放弃
  -> 已登记 surface 才能投影 HypothesisCandidate
  -> D0-D3 -> panel -> hash-bound promotion -> experiment.py
```

生成器只负责扩大 proposal distribution。它不读取候选 forward outcome，不给历史赢家加权，
不把一条产业叙事直接变成股票排名，也不调用 `experiment.py`、`quant/run.py` 或任何订单路径。
`bottleneck-hunter` 是分析方法，不是 `EvidenceSurface`，也不构成 novelty 的“新数据源”。

## 2. 当前登记实现

registry 位于 `data/reference/alpha_mechanism_generators.json`。首个实现固定为：

| 字段 | 合同 |
|---|---|
| `generator_id` | `ai_berkshire_bottleneck` |
| `skill_name` | `bottleneck-hunter` |
| 角色 | 发现物理供应链约束、反向证据和可能的传导链 |
| 日预算 | `0..2` leads；零输出是合法 abstain |
| 队列 | exploration / adjacent；不得因历史收益进入 exploitation |
| 结果权限 | 禁止 candidate-specific return、PnL、Sharpe、MFE/MAE、Gate 结果 |
| 写权限 | staging / research map / digest；无实验、策略、仓位或交易权限 |

registry 记录 skill 内容哈希。skill 更新后必须提升 generator version 或更新哈希；旧 scan 仍保留其
原版本，禁止静默用新 prompt 重解释旧 lead。

## 3. 两阶段顺序

顺序是安全合同的一部分：

1. 冻结 `generator_id`、版本/skill hash、`scan_run_id`、data cutoff、研究日期与 0-2 预算。
2. 在**未读取候选历史结果**的上下文中生成 staging lead；每个 lead 同时写支持证据和反证。
3. 机器校验 schema、outcome contamination、来源独立性、PIT/授权声明和零交易权限。
4. 草稿已冻结后，才读取 `frozen_families`、失败实验、recipe lanes 和 reopen 条件作 veto。
5. 通过或被 park 的研究条目可发布到 map；veto 只改变 disposition，不给其他 lead 排名。
6. 运行 digest builder；daily alpha pass 只消费带真实 scan marker 的当日条目。

禁止先读历史赢家/输家，再要求生成器“沿成功方向想两个”。这会把 mechanism generator 重新变成
已退役 meta search 的局部最优器。

## 4. Staging scan 最小合同

实际字段以 JSON template 和 validator 为准。语义上至少包括：

```yaml
schema_version: 1
generator_id: ai_berkshire_bottleneck
generator_version: bottleneck-hunter-v1
scan_run_id: mechanism-scan-YYYYMMDD-...
research_date: YYYY-MM-DD
timezone: America/Los_Angeles
generated_at: ISO8601
data_cutoff: ISO8601
outcome_blind: true
history_read_before_generation: false
history_policy: veto_after_generation
experiment_id_reserved: false
trade_enabled: false
security_ranking_enabled: false
leads: []  # 0-2
```

每个 lead 至少声明：

- 稳定 `mechanism_id`、标题与 exploration / adjacent 队列；
- 具体的 physical bottleneck、至少两步的 causal chain 和 transmission hypothesis；
- 至少两个不同 `independence_group` 的来源；每个来源有 publisher、URL、发布时间、PIT
  使用等级（`not_pit|research_pit|canonical_pit`）、可得时点、vintage caveat 和授权状态；
- 至少一条 counterevidence，不允许只有“风险很多”这种空话；
- `market_prior_status: observable|unidentified` 与对应 expectation proxy；
- `pit_feasibility`、聚类/独立决策口径和 source authorization 总结；
- baseline、treatment、expected horizon、replacement-value comparator 和 falsifier；
- 可能受影响 ticker 只能标作 transmission mapping，且显式声明不是投资建议；
- 生成后 historical veto 的时序和结论。

任意嵌套位置出现 realized return、PnL、Sharpe、win rate、MFE/MAE、Gate result 等结果字段均
fail closed。两条 URL 指向同一发布者或同一底层数据，只算一个 independence group。

## 5. 发布、digest 与 freshness

validator 入口是：

```powershell
.\.venv\Scripts\python.exe -B scripts\alpha_search.py build-mechanism-leads `
  data\alpha_search\staged_mechanism_scan.json `
  --output data\alpha_search\validated_mechanism_batch.json
```

validator 输出的是 deterministic map section、完整 scan manifest 与 provenance，不直接修改研究图。外部扫描任务只把
校验成功的 section 追加到 `docs/alpha_external_research_map.md`，并按现有 ledger 状态机记录
`fresh / proposed / parked / ...`。生成器 section 必须带：

```text
generator_id: ...
generator_version: ...
mechanism_id: ...
evidence_grade: lead
market_prior_status: observable|unidentified
source_authorization: ...
scan_run_id: ...
scan_completed_at: ...
entry_id: res-YYYYMMDD-...
```

`scripts/build_research_digest.py` 把这些字段保留到 Markdown / JSON，并单列
`latest_mechanism_scan`。发布顺序必须是：先把 `research_map_sections[].research_map_markdown`
写入 map，再用同一 staging scan 重跑 validator，把结果原子写到
`data/research_digest/latest_mechanism_scan.json`，最后运行 digest builder。非零 batch 的 entry_id
若尚未出现在 map，builder 会拒绝；零-lead batch 仍能用 hash-bound manifest 证明一次合法 abstain。

`latest_digest.json.generated_at` 只是 builder 的运行时钟；在 map 没有新增
section 时反复重建也会变化，不能作为扫描新鲜度。daily alpha pass 必须核对
`latest_mechanism_scan.research_date / timezone / scan_completed_at`、run id、generator version 和
skill hash。

## 6. 从 lead 到正式候选

- 无可观察市场 prior：只能保留 `plain_event_lead`、`evidence_grade=lead`，D1 应 park。
- prior 可观察但没有已登记 surface：仍只是 research lead；不得伪造 `surface_ids`。
- source 未授权、决策时间未知或有已知泄漏：research entry 必须 park/reject，不得进入 panel。
- source 为 `research_pit`：可投影为 `evidence_grade=lead`，进入 D0-D3、hash-bound promotion 和
  `private_replay_scout`；正向结果上限为 `observed_only`，不能获得 paper/live promotion。
- 只有显式引用 `data/reference/alpha_search_evidence_surfaces.json` 中已登记且在 data cutoff 前 ready
  的 surface，才可投影为现有 `HypothesisCandidate`。
- 投影不授予任何 guard 豁免；仍须经过 D0-D3、完整 pool、panel、hash-bound promotion 和正式实验协议。多模型讨论可选，不构成 admission 条件。

`source_preflight_only` 可以作为 generator 输出的解释性 disposition，但不是新的正式 candidate
状态；正式 D0-D3 closeout 仍使用现有闭集 failure reason 和 `park / reject`。

## 7. 每日调度合同

external scan 与 alpha pass 是两个有依赖的任务：

1. external scan 调用已登记 skill、写 staging、校验、做生成后 veto、发布 map，最后重建 digest；
2. 60-120 分钟后 alpha pass 核对 scan freshness，再决定挑选、放弃或自行生成候选；
3. mechanism scan 失败时不得发布伪 fresh marker，也不得影响 `quant/run.py`；记录失败并让当天该
   generator abstain；
4. scheduler prompt 存在仓库外时，它只是执行配置；本文件和 registry 才是版本化合同。README
   架构图不单独证明桌面 automation 已启用。

正确吞吐指标是：有效机制覆盖、独立来源合格率、expectation prior 可识别率、D0-D3 信息量和
重复机制下降，不是每天必须产出实验 ID，也不是 Gate-4 接受率。
