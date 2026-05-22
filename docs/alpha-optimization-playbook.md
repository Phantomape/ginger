# Alpha Optimization Playbook

本文件是 Ginger 的长期 alpha 研究手册。
它连接 [`AGENTS.md`](D:/Github/ginger/AGENTS.md)、
[`docs/backtesting.md`](D:/Github/ginger/docs/backtesting.md)、
[`docs/current_state.md`](D:/Github/ginger/docs/current_state.md) 和
[`docs/experiment_log.jsonl`](D:/Github/ginger/docs/experiment_log.jsonl)，但不重复充当实验日志。

它只回答四类问题：

1. 仓库证据已经证明了哪些机制更值得做；
2. 哪些方向已经进入“不要再近邻重试”的状态；
3. 未来 1-3 轮最值得投入的 alpha 研究队列是什么；
4. 最新研究能转化成哪些可回放、可归因、可生产可见的字段。

Last refreshed: 2026-05-22.
Research refresh cut: 2026-05-22.

## 使用方式

开始任何策略改动前，先回答：

1. 本轮属于 `allocation`、`field`、`entry`、`exit`、`candidate_pool` 还是 `measurement_repair`？
2. 这是不是同一家族的近邻重试？如果是，新证据是什么？
3. 这次能否只引入一个生产可见、回放安全的变量？
4. 如果不能，是被哪个字段、归因或 parity 缺口阻断？

默认决策顺序：

1. 优先 `alpha_search`，除非测量缺陷直接阻断高价值 alpha。
2. 优先“新增一个解释字段”，而不是“再扫一轮相邻 scalar”。
3. 优先 default-off sleeve / paper adapter，而不是直接扩 core。
4. 优先 replacement-value 与 concentration 治理，而不是只看 standalone PnL。
5. 优先共享生产可见逻辑，而不是 replay-only 的聪明规则。

## 一页结论

Ginger 仍然是“事件增强型中短线趋势 / 突破系统”，但仓库证据已经把可赚钱方向收敛得更窄：

1. **核心 live alpha 主要来自已入选信号上的小幅 allocation 改善。**
   广义 entry/filter 重写通常不如窄条件 post-sizing top-up 稳定。
2. **新字段比新阈值更值钱。**
   同一族 queue/profile/notional/scalar 在冻结窗口上反复扫参，边际价值正在快速下降。
3. **default-off sleeve 是新 alpha 的主孵化器。**
   broad-market、event、SEC、state-surface、suspect cohort 都应先在 sleeve 里成熟。
4. **replacement value 比 standalone PnL 更重要。**
   “它赚钱”不够；要回答“它是否优于 cash / 被替换掉的 core 机会 / 相邻 queue rank”。
5. **concentration 是 promotion blocker，不是二级备注。**
   单 ticker、单主题、单 source、单窗口驱动的 paper uplift，默认不该升级成 live capital。
6. **LLM 最有价值的职责是结构化解释，不是交易拍板。**
   适合做 event extraction、事实/语气拆分、topic gap、异常披露解释、灾难 veto 候选；不适合接管 sizing、硬风控、slot、exit。

## 仓库已经形成的稳定经验

## 1. Allocation 胜过 Filtering

强先验：

- 已合格信号上的小幅 post-sizing top-up；
- 窄状态下的 risk promotion / haircut；
- 固定 candidate set 上的 sleeve capital routing；
- 在不动 entry/exit 的前提下改善 replacement value。

弱先验：

- 再加一层 broad filter；
- broad slot reranking；
- mirror-image 惩罚规则；
- 大范围 quality overlay；
- 没有新字段支撑的 exit retune。

解释：
仓库近期最稳定的改善大多来自“对已经过关的交易分配更多/更少资本”，而不是“让更多规则决定谁能进门”。

## 2. 一个好字段胜过一串例外规则

噪声队列通常不会因为再叠一层 generic guard 而变好。
它们通常会因为一个更贴近机制的字段而变好，例如：

- source credibility；
- topic attention divergence；
- fact/tone disagreement；
- crowding / overlap；
- disclosure quality；
- state persistence vs extension。

如果一个想法需要很多 if/else 才成立，通常说明字段层还没建好。

## 3. Sleeve 是正确的试验边界

以下方向默认先做 sleeve，不直接做 core：

- broad-market 候选池；
- external event overlays；
- SEC event families；
- suspect ticker cohorts；
- passive/index mechanics；
- theme / pilot / AI infra 子组合。

原因不是保守，而是这些方向最需要：

- 明确的 candidate definition；
- replacement-value accounting；
- concentration 审计；
- forward closed outcomes；
- kill switch；
- 与 core 资本竞争时的可解释性。

## 4. Replacement Value 是硬门槛

任何新 sleeve 都应明确回答：

- 是否优于 cash？
- 是否优于同日被它挤掉的 core 候选？
- 是否优于相邻 queue rank？
- 是否只是把一个大赢家集中放大？

没有 replacement-value 证据的“高 paper PnL”只算研究线索，不算 promotion 证据。

## 5. Exit 改动要比 Entry 改动更谨慎

仓库历史和近期结果都表明：

- 简单地把 target 变宽、分批止盈、局部 target pool 化，常常破坏赢家；
- 即使 aggregate PnL 看起来变好，也容易带来旧窗口退化或 drawdown 漂移；
- exit 的 lookahead 诱惑很强，最容易把 oracle gap 误当作可交易 alpha。

默认结论：
先用 oracle / shadow attribution 解释“为什么当前 exit 没抓住利润”，再把证据转成共享字段或完整生命周期设计；不要直接把后视最优动作硬编码成规则。

## 6. LLM 的正确位置是“可审计解释层”

应该让 LLM 产出的对象：

- `event_family`
- `semantic_subcategory`
- `source_credibility_bucket`
- `fact_direction_bucket`
- `tone_direction_bucket`
- `fact_tone_gap_bucket`
- `manager_nonresponse_bucket`
- `topic_attention_divergence_bucket`
- `special_call_flag`

不应该直接让 LLM 决定：

- 仓位大小；
- 止损与目标；
- slot priority；
- portfolio heat；
- 是否绕开硬过滤；
- 最终交易指令。

## 当前最值得做的队列

以下是当前默认优先级，不是永远真理；若实验日志改变机制结论，再更新这里。

### 1. State-surface：从“调 profile”转向“解 concentration”

现状：

- `STATE_SURFACE_SATELLITE` 已有多轮 accepted paper uplift；
- 继续在 queue/profile/notional/scalar 上做近邻调参，已经进入高多重检验风险区；
- 现在真正阻断 promotion 的不是“paper edge 不存在”，而是 concentration、crowding 和 forward maturity。

接下来只优先：

- top-rank overlap / queue independence 字段；
- sector/theme crowding 字段；
- persistence-vs-extension 字段；
- paper trade replacement value；
- forward kill-gate 与 tail-aware concentration guard。

默认不做：

- 冻结样本上的相邻 queue-rank/profile/notional retune；
- 没有新字段的新 threshold sweep；
- 用 aggregate uplift 为同族小修小补找借口。

### 2. Event overlay：从“证明方向”转向“治理 source/context 质量”

现状：

- external event overlay 已经证明默认-off paper 方向有效；
- source quality、market-state context、front-rank rotation 等已有阶段性证据；
- 当前瓶颈是 closed forward replacement value，而不是更多 replay-only 局部强化。

接下来只优先：

- source overlap / source crowding；
- source credibility / disclosure quality；
- event-family x market-state 分解；
- same-day displacement accounting vs core；
- closed forward outcomes by source family。

默认不做：

- 相邻 source scalar、state scalar、capacity scalar 的重复开采；
- 没有新增 forward rows 的 semantic-cell 放大。

### 3. Broad-market leadership：从“paper queue 好不好”转向“能否安全拿资本”

现状：

- `BROAD_MARKET_LEADERSHIP_PAPER` 已有较强 paper 证据；
- 上限大，但也最容易引入 feed leakage、hidden beta 和 crowding；
- 现在缺的不是再调 low-extension / vol / persistence，而是治理与归因。

接下来只优先：

- 固定 production candidate feed；
- closed forward outcomes；
- replacement value vs core / cash；
- hidden beta / sector concentration / crowding；
- 明确的 sleeve slots、capital cap、kill criteria。

默认不做：

- 冻结样本上的相邻 trend / extension / volatility / persistence retune；
- 用 broad-market paper 胜率替代 capital competition 证据。

### 4. SEC / earnings semantics：高上限、低冲突、适合字段化

这是最符合 Ginger“事件增强型趋势”定位的研究线。
目前最大问题不是没有想法，而是字段层太薄。

最值得补的字段：

- `fact_tone_gap_bucket`
- `guidance_delta_direction`
- `topic_attention_divergence_bucket`
- `manager_nonresponse_bucket`
- `special_call_flag`
- `disclosure_quality_bucket`
- `attention_persistence_bucket`
- `in_call_information_timing_bucket`

这些字段适合先进入 paper queue / paper notional / event routing，不适合一上来进入 core hard filter。

### 5. Ticker governance / no-trade alpha

核心栈已经很密。
接下来更可能赚钱的是：

- 哪些 cohort 应被 sleeve 化；
- 哪些 cohort 只该 paper 跟踪；
- 哪些 cohort 的价值主要来自 no-trade avoided value；
- 哪些 ticker 应降权而不是加新过滤器。

优先证据：

- ticker / setup / regime contribution table；
- no-trade avoided value；
- closed forward paper outcomes；
- capital-routing 对比，而不是单纯删 ticker。

### 6. Execution leakage attribution

这条线经常被低估。
如果 live return 持续低于回测潜力，执行摩擦可能比再调阈值更值得研究。

优先项：

- gap erosion attribution；
- missed fill / delayed fill cohorts；
- next-open 假设与真实执行偏差；
- liquidity / spread / signal-time 的 drift 分层。

## 明确进入“反复重试禁区”的方向

若没有 `new_forward_rows`、`new_production_visible_field`、
`new_replacement_value_cohort` 或更广 PIT 样本，不要重试：

1. broad core filters；
2. broad slot / heat / capacity sweeps；
3. broad lifecycle target-width / runner / trailing-stop retunes；
4. broad slot-priority reranking；
5. broad positive/negative language scalar；
6. 没有 attribution 的 LLM veto / ranking 扩权；
7. state-surface 的相邻 queue/profile/notional 调参；
8. broad-market leadership 的相邻 extension/volatility/persistence 调参；
9. event overlay 的相邻 source-capacity / state-rank / source-scalar 重试；
10. buyback 方向里只增加关键词覆盖；
11. Form 4 方向里忽略 options-market context；
12. index / ETF 方向里只改 target ATR 或单一 exit pool；
13. 为 1-3 笔亏损交易新增专门例外。

## 研究到字段的落地地图

以下部分只保留“能直接转成 Ginger 字段或流程”的研究。
不是文献综述，不追求全。

### 1. Earnings call 的真正信息不是“平均情绪”，而是主题错位与信息释放时点

主要研究：

- Xiao & Zhang, *Measuring Information Quality by Topic Attention Divergence* (SSRN, 2024；2026-02-23 revised):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4723491>
- Oh, *Price Discovery Within Earnings Calls* (SSRN, 2026-01-20):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6105146>
- Brull, Marshall & Moss, *Sustained Investor Attention* (SSRN, 2025-06-24):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5318279>

对 Ginger 的含义：

- 不要把 call alpha 简化成一个总 sentiment；
- 更值得做的是“管理层在讲什么”和“分析师追问什么”之间的 gap；
- 信息释放发生在 call 内的哪个阶段，也可能影响后续 drift；
- 注意力持续时间本身可能是质量信号。

优先字段：

- `topic_attention_divergence_bucket`
- `manager_analyst_topic_gap_flag`
- `in_call_information_timing_bucket`
- `attention_persistence_bucket`

最低落地标准：

- transcript / audio chunk 有时间戳；
- topic 与 Q&A 分开；
- 字段必须能映射到 event queue，而不是只生成一段说明文字。

### 2. “怎么说”和“说了什么”要分开建模，但内容通常先于语调

主要研究：

- Oh, *Price Discovery Within Earnings Calls* (SSRN, 2026-01-20):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6105146>
- Beckmann et al., *Unusual Financial Communication: ChatGPT, Earnings Calls, and Financial Markets* (SSRN):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4699231>
- Guo & Lo, *Formal and Informal Language in Earnings Conference Calls* (SSRN, 2025):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5174884>

对 Ginger 的含义：

- 文本内容通常是第一层信号；
- delivery / abnormal style 更像风险解释、异常披露或 crowding 佐证；
- 语调不应直接替代事实字段。

优先字段：

- `unusual_communication_bucket`
- `formal_informal_gap_bucket`
- `mixed_message_strength_bucket`
- `text_voice_alignment_bucket`

### 3. Facts 与 Tone 必须显式拆分

主要研究：

- Gong, Li & Zhang, *Decrypting Corporate Speak: GPT-Assisted Measurement of Facts and Tones in Earnings Calls* (SSRN, 2024):
  <https://papers.ssrn.com/sol3/Delivery.cfm/4950924.pdf?abstractid=4950924&mirid=1>

对 Ginger 的含义：

- “正面”不等于“基本面在改善”；
- promotional language 与 operational facts 应分开；
- fact/tone disagreement 比单纯正负面更适合跨事件迁移。

优先字段：

- `fact_direction_bucket`
- `tone_direction_bucket`
- `fact_tone_gap_bucket`
- `operational_fact_density_bucket`

### 4. SEC / event extraction 要做成 span-grounded JSON，不要做自由文本结论

主要研究：

- *Harnessing Generative LLMs for Enhanced Financial Event Entity Extraction Performance* (arXiv:2504.14633, 2025-04-20):
  <https://arxiv.org/abs/2504.14633>
- *Agentic Retrieval of Topics and Insights from Earnings Calls* (arXiv:2507.07906, 2025-07-10):
  <https://arxiv.org/abs/2507.07906>

对 Ginger 的含义：

- 事件抽取应输出结构化 JSON；
- 每个字段都要绑定 evidence span；
- ontology 要允许版本化，避免 prompt 漂移导致历史不可比。

优先字段：

- `event_family_v2`
- `event_argument_json`
- `evidence_span_count`
- `ontology_version`
- `extraction_consistency_bucket`

最小工程规范：

- 每个字段附 `source_doc_id`、`event_timestamp`、`span_offsets`；
- extractor 输出与 rule 使用之间必须可回放；
- 允许 schema 升级，但必须保留版本字段。

### 5. LLM 在金融文档上的上线关键，不是更大模型，而是评估与编排

主要研究：

- *Fin-RATE* (arXiv:2602.07294, 2026-02-07):
  <https://arxiv.org/abs/2602.07294>
- *SECQUE* (arXiv:2504.04596, 2025-04-06):
  <https://arxiv.org/abs/2504.04596>
- *Benchmarking Multi-Agent LLM Architectures for Financial Document Processing* (arXiv:2603.22651, 2026-03-24):
  <https://arxiv.org/abs/2603.22651>

对 Ginger 的含义：

- 单次 extraction 准确率不够，要看 longitudinal consistency；
- 要分清 retrieval failure、parser failure、reasoning failure；
- 多 agent / 分阶段编排只有在字段复杂且可缓存时才值得；
- 生产上应优先 cost-accuracy Pareto，而不是盲目上 reflexive loops。

默认流程：

1. retrieval / segmentation；
2. field extraction；
3. validation / normalization；
4. consistency audit；
5. sleeve attribution。

### 6. Disclosure quality 是 event alpha 的主轴，不是附属标签

主要研究：

- Dechow et al., *Beyond Earnings Quality: Evaluating the Quality of Corporate Disclosure Practices* (SSRN, 2025；2026-02-27 revised):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5257154>
- Hu & Shohfi, *Special Conference Calls* (SSRN, 2025-09-10):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5598490>

对 Ginger 的含义：

- event alpha 不能只看 event family；
- 还要看披露是否主动、是否具体、是否在特殊 call 中补充、是否带来增量信息；
- governance / procedural / special-call 事件尤其适合做 disclosure-quality 路由。

优先字段：

- `disclosure_quality_bucket`
- `special_call_flag`
- `management_commitment_specificity_bucket`
- `source_credibility_bucket`
- `incremental_disclosure_flag`

### 7. Buyback 不是“看到 repurchase 就加分”，而是看承诺可信度与后续执行

主要研究：

- Bargeron et al., *Voluntary Disclosures Regarding Open Market Repurchase Programs* (SSRN / CAR, 2024-01-26):
  <https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4707512_code84189.pdf?abstractid=2486843>
- Andriosopoulos, *Does the daily reporting of share buybacks matter?* (SSRN, 2025):
  <https://papers.ssrn.com/sol3/Delivery.cfm/5287917.pdf?abstractid=5287917&mirid=1>

对 Ginger 的含义：

- buyback 关键词覆盖本身几乎肯定太弱；
- 更强的对象是透明度、暂停披露、剩余容量、后续执行一致性。

优先字段：

- `buyback_commitment_strength_bucket`
- `buyback_remaining_capacity_signal`
- `repurchase_transparency_flag`
- `repurchase_followthrough_bucket`

### 8. Form 4 不能脱离 options context

主要研究：

- Jeon & Sulaeman, *Corporate Insider Purchases and the Options Market* (Journal / SSRN, 2024-06-13):
  <https://papers.ssrn.com/sol3/Delivery.cfm/4864272.pdf?abstractid=4864272&mirid=1>

对 Ginger 的含义：

- raw insider buying 不是充分条件；
- options-market 活跃度可能解释“这笔 insider buy 是否仍有独立信息量”；
- 这和仓库里“单 owner / 单 queue 仍样本太薄”的现状一致。

优先字段：

- `options_activity_bucket`
- `options_competition_flag`
- `cluster_buying_flag`
- `insider_purchase_context_quality`

### 9. Passive flow / index mechanics 更适合机械 sleeve，而不是 LLM 判断

主要研究：

- Sammon & Shim, *Who Clears the Market When Passive Investors Trade?* (SSRN, 2024；2026-03-01 revised):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4777585>
- Kastenholz, *The Index Event Horizon* (SSRN, 2026-03-17):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6430698>
- Gufler, *Passive Investing, Diversification Risk and Financial Stability* (SSRN, 2026-03-29):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6487578>

对 Ginger 的含义：

- 被动资金和指数事件更像机械流量，不像语义理解任务；
- 适合做 deterministic sleeve，而不是让 LLM 自由解释；
- 对 broad-market、ETF、large-cap lower-tier / upper-mid-cap 队列都 relevant。

优先字段：

- `index_event_type`
- `effective_date`
- `passive_flow_pressure_bucket`
- `index_crowding_risk_bucket`

### 10. Daily-return pattern 可以作为 broad-market 机械特征库，但不要直接上核心

主要研究：

- Cakici et al., *A Unified Framework for Anomalies Based on Daily Returns* (SSRN, 2026-01-02):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6005614>

对 Ginger 的含义：

- broad-market 队列不一定需要更多叙事字段才能开始；
- 日收益路径本身可能提供统一、低泄漏、低解释负担的机械特征；
- 但应优先放入 broad-market paper sleeve，作为 ranking/support field，而不是直接改 core signal engine。

优先字段：

- `drif_bucket`
- `short_horizon_return_path_cluster`
- `max_daily_return_20_bucket`
- `reversal_vs_continuation_state`

## LLM 字段的最低工程标准

任何新 LLM 字段，默认都要满足：

1. **结构化输出**
   不是 prompt prose，而是 schema-bound JSON。
2. **证据绑定**
   每个字段至少有 document id、timestamp、span。
3. **版本化**
   有 `ontology_version` 或 `schema_version`。
4. **失败归因**
   能区分 retrieval miss、parse miss、reasoning miss。
5. **纵向一致性**
   能做 same-firm-over-time consistency audit。
6. **生产可见**
   `run.py` / 日报 / snapshot 中至少能看到最终字段值，不允许隐藏在 prompt 内部。
7. **回放安全**
   回测使用的字段必须来自当时可得文本，不得借未来文档补全。

## 新字段的默认落地顺序

除非明确不适用，否则按以下顺序推进：

1. 文档级字段抽取；
2. 生产日志落盘；
3. PIT / replay 检查；
4. 先做 paper queue 或 paper allocation；
5. 做 replacement-value / concentration / forward closed outcomes；
6. 只有通过 gate 后，才考虑 live sleeve 或 core allocation。

## 更新纪律

只有在以下情况才更新本文件：

1. 新实验改变了机制级先验；
2. 某一研究家族从“值得做”变成“被阻断 / 不要再试 / 已成熟”；
3. 新研究改变了字段建设优先级；
4. 某个 measurement blocker 成为高价值 alpha 的主阻断项；
5. 某条 anti-repeat rule 已经足够稳定，值得长期写死。

写法要求：

- 先写综合结论，再写例子；
- 少写实验编号，多写会长期成立的规律；
- 不把本文件写成状态公告板；
- 不把本文件写成论文书单；
- 每次更新都要让下一位代理更快知道“什么值得试，什么不该再试，什么需要先补字段”。
