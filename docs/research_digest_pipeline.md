# Research Digest Pipeline（外部研究 → 假设生成的消费合同）

状态：合同规格，2026-07-21 由 fable-alpha-automation 起草，待 codex 实现。
实现完成后本文档即为该管道的单一真相源；实现细节偏差以实际代码为准并回写本文。

## 1. 动机

`docs/alpha_external_research_map.md`（天级扫描产出，133 条、146 篇 arXiv）从未被
任何实验票据引用过——只写不读。同时 2026-07-14..07-21 的 45 张 alpha 票 41 拒 0 收，
约 55% 是配方级重复。结论（与用户 2026-07-21 讨论确认）：搜索已存在，缺的是
**消费合同**和**条目状态机**。没有状态机，摘要层会复活刚在实验层堵住的重复循环
（多个 agent 挑同一条目、被拒条目换编号回归）。

## 2. 架构（两段式）

```text
天级扫描任务（codex 派发线，已存在，改造）
  → alpha_external_research_map.md（存档，全文，供深读）
  → data/research_digest/ledger.jsonl（消费账本，append-only）
  → scripts/build_research_digest.py
  → data/research_digest/latest_digest.md + latest_digest.json（小摘要，<8KB）

alpha 任务（synthesis pass 合同步骤）
  → 读 latest_digest（当日增量 + top-K fresh 条目）
  → 每条 fresh：挑中 / 放弃 + 一句理由 → 写回 ledger
  → 只对挑中条目深读原文 → 走发现层 / novelty / recipe / reopen guard 照常裁决
  → 票据可选 research_refs 字段；close 时回填条目 status
```

## 3. 交付物（codex 实现清单）

### A. 条目 ID

- `alpha_external_research_map.md` 每个 `###` 小节获得稳定 `entry_id`
  （格式 `res-YYYYMMDD-slug`，落款在小节末尾一行 `entry_id: ...`）。
- 一次性回填现有 133 条（按小节标题 slug 化；日期用 declared/refresh 日期或 20260721）。
- 扫描任务今后新增小节时必须带 entry_id。

### B. 消费账本 `data/research_digest/ledger.jsonl`

Append-only，一行一个状态事件：

```json
{"entry_id": "res-20260721-xxx", "status": "fresh|proposed|rejected|accepted|parked|lane_blocked|declined", "exp_id": null, "reason": "one line", "actor": "agent-name", "ts": "ISO8601"}
```

- 条目当前状态 = 该 entry_id 最后一行。禁止改写历史行。
- `lane_blocked`：扫描端预过滤命中已烧配方车道（见 D）。
- `declined`：alpha 任务读过但放弃（必须带 reason）——放弃不是终态，
  条目仍可被后续轮次以新理由挑中，但 digest 排序会降权。

### C. 摘要生成器 `scripts/build_research_digest.py`

- 输入：research map + ledger + `docs/recipe_lanes.jsonl` + `docs/frozen_families.jsonl`。
- 输出 `latest_digest.md`（人读）与 `latest_digest.json`（机读），内容 =
  当日新增条目 + top-K（默认 10）未消费 fresh 条目。
- 每条目字段：机制、**可观察的市场先验代理**、数据源 + PIT 可行性、
  拥挤度/发表衰减分级（`crowding: low|medium|high`）、预写反证、
  recipe-lane 预检结果、ledger 状态。
- **复用** `scripts/create_experiment_ticket.py::classify_recipe_lane_match`
  做车道预检，不要重新实现短语匹配。
- **实现偏差回写（2026-07-21 首跑发现）**：论文用学术词汇描述已烧车道的源域、
  不带交易配方应答词（8-K item-code 条目 source 命中 2 / response 命中 0），
  故 digest 端预检比 reservation guard 更严：单车道 source 簇命中 ≥2 即
  lane_blocked（`_digest_lane_matches`）。摘要层拦截成本低、宁严勿松；
  reservation guard 保持 response 命中要求不变（那里误拦成本高）。
- 排序：fresh 且 crowding=low 且有可观察先验代理的优先；declined 降权；
  lane_blocked / rejected / proposed 不进摘要。
- 总量硬上限 8KB——上下文预算是真约束。

### D. 扫描任务改造（codex 自己的定时任务 prompt）

- 提取模板从"方法论教训"扩展为候选 lead：每篇来源必须尝试抽取
  （机制 / 市场先验代理 / 数据源+PIT / 拥挤度分级 / 反证）；抽不出先验代理的
  仍可作为方法论条目保留，但标 `no_expectation_proxy`，digest 降权。
- 扫描端预过滤：对照 recipe_lanes.jsonl 与 frozen_families.jsonl，
  命中即在 ledger 写 `lane_blocked`（如"另类计数×篮子"类论文）。
- 扫描收尾必跑 `build_research_digest.py`。
- 若扫描任务 prompt 存放在仓库外，codex 更新后在 mailbox 回复中注明位置。

### E. AGENTS.md synthesis pass 消费步骤

在 §2 Alpha Synthesis Pass 的证据面盘点（第 2 步）中追加一句：
盘点必须包含读取 `data/research_digest/latest_digest.md` 当日增量，
对每条 fresh 条目给出挑中/放弃与一句理由（写回 ledger，不占实验 ID）；
挑中条目进入候选假设时在票据 `research_refs` 里引用 entry_id。

### F. 结果回填

- 实验 close 时若票据含 research_refs，向 ledger 追加对应
  proposed→rejected/accepted/parked 状态行。先作为文字规则（收尾清单一行），
  接入 close 工具自动化是后续可选项，不阻塞本次交付。

## 4. 硬约束

- 摘要与外部来源**不给任何 guard 豁免**：novelty / recipe-lane / reopen /
  saturation 照常裁决。外部研究只是候选生成器，不是权威。
- 不触碰 quant/run.py、任何策略路径、订单、trade_enabled。
- codex 按仓库协议自行 reserve 一个 measurement_repair ID（治理工具先例：
  exp-20260714-007、exp-20260721-004、exp-20260721-005），reserve 前查
  in-flight 票据。
- ledger 与 digest 文件提交进 git（digest 是派生物但小，便于审计消费历史）。

## 5. 验收标准

1. 现有 133 条全部有 entry_id，ledger 有初始 fresh 行。
2. digest 从当前 map 生成成功，<8KB，且**至少一条**被预过滤标为
   lane_blocked（map 里现存与已烧车道同形的条目应该不止一条——若为零，
   说明预检没接通，视为失败）。
3. AGENTS.md synthesis pass 步骤已更新。
4. 扫描任务 prompt 已更新（或在 mailbox 注明其位置与修改内容）。
5. 下一次天级扫描运行后 digest 自动刷新（本条可留待次日验证，
   在实验票 follow-up 中注明）。

## 6. 预期管理（写给未来读者）

本管道改善候选**质量与异质性**，不直接改善接受率——当前 0/41 的另一半原因
是 Gate-4 棘轮与 forward 行饥饿（日历问题）。判断本管道是否有效的正确指标：
研究引用票据的"被拒信息量"（新机制/新反证 vs 换皮重复），以及 digest 条目
被挑中后通过 D0-D3 preflight 的比率；不是 Gate-4 接受率。
