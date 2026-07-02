# 下一步方向决议 — 2026-07-01（24h 复盘 + 三个候选方向 + owner 偏好方向展开）

> 给执行 agent 的自含 brief。来源：2026-07-01 与 owner 的对话复盘，基于
> `docs/experiment_log.jsonl`（06-30 起 32 个 closeout）、
> `docs/alpha-optimization-playbook.md`（07-01 刷新版）、
> `docs/alpha_external_research_map.md`、`data/daily/news/*` 与
> `data/non_ohlcv/moomoo_*` 实况核对。开工前仍按 `AGENTS.md` §3-§7 走。

## 一、过去 24 小时实验结论（06-30 晚 ~ 07-01）

**0 个 accepted alpha**，延续成熟度墙。结构上分三类：

### 被拒 / 关闭

- `exp-20260701-002`：Kova SEC13F **sponsorship 水平**的 1d/3d/5d lead 没活到
  10d，rejected。13F 持仓水平继续留在 crowding context。
- 出场端两条路都关了：`exp-20260701-012` exit-lifecycle 高紧迫度 advisory 在新
  结算行上不持续；`exp-20260630-020`"高风险 × 第3日相对弱势"可执行子集失败；
  `exp-20260630-012` close-confirmed 静态止损 Gate 4 失败。
- `exp-20260630-016`：ATR-extension 入场去配置在大样本（n=2594）下方向反转，
  正式退休。`exp-20260630-017` 特征相似 peer-shock 归因无边际。
  `exp-20260630-010` 期权 put-demand 无 10d 分离。

### 存活的 observed-only 正向 lead（24h 里最重要的信息）

- **`exp-20260701-009`：Kova SEC13F 主动管理人 active-flow（季度增减仓流量）
  字段在新结算 10d cash/SPY/QQQ 替换价值上仍正向分离**。sponsorship 水平死了，
  流量方向活着。未晋级原因：缺历史 PIT 覆盖，无法跑三窗口 Gate 4。
- `exp-20260630-018`：高账户风险入场（`actual_risk_pct >= 2%`）在全部三个
  canonical 窗口留下更大的可避免出场 regret（全分母 oracle 行确认）。
- `exp-20260630-005`：结构化日新闻 relation-quality 前向 lead 正向，日频 + 盘中
  观察合同已落地（-006/-007/-013/-015/-019），但 closed rows≈0，日历绑定。

### 测量修复（不改任何交易行为）

estimate-revision 06-29 匹配行 h1 结果物化（仅 1 行非平，h3/h5/h10 待成熟）；
6-K 语义前向账本刷新；06-30 日新闻原子写恢复；paper sleeve 同日幂等修复
（`exp-20260701-004`）。

## 二、方向 0（owner 偏好，本文重点）：新闻/消息 + LLM 的事件→关联标的传导 alpha

Owner 原话意图：*"某一天流出 SpaceX 要上市，太空股估计都会涨一波"*——即
**事件发生在 A（可能不可交易），LLM 判断哪些上市标的 B/C/D 会被传导**。

### 为什么天真版已经死了，而这个版本没测过

已被拒/冻结的近邻（不要撞）：

- `exp-20260630-002`：**显式 ticker** 正面事件关键词分类 → 无前向边际，rejected。
- SEC 文本短语匹配家族：饱和（`sec_text_event` 0/43）。
- 固定主题篮子 breadth-thrust（半导体/AI 硬件篮）：rejected。
- 行业 ETF / 宏观代理 leadership、特征相似 peer（`exp-20260630-017`）：rejected。

**没测过的轴**：现有新闻摄取是逐 ticker 的 Google News RSS
（`data/daily/news/raw/`，~2,500 条/天，`tickers` 字段来自搜索关键词），
**非上市主体（SpaceX、OpenAI、监管机构、大客户/供应商）的事件只会顺带出现，
且从未被系统性映射到受影响的上市标的**。playbook 队列 #4 明确把
"customer/supplier or contract counterparties when source text supports it"
和"source-family propagation with explicit timestamp and provenance"列为候选
relation 来源；#6 把 LLM 限定为 schema 绑定的语义基础设施。External research
map 的对应条目：LLM Financial-Headline Alpha、Event-Aware LLM Labels Are
Features Not Decisions、Adversarial Headline Sanitation（已实现）、Relation
Score Gating。二者交集正是这个方向。

### 合规设计（shared-paper-first 可达）

1. **摄取扩展（新数据轴）**：在现有 per-ticker RSS 之外加一组
   **实体/主题级查询**（固定清单：头部私有公司、监管主体、主题关键词），走
   已接受的 sanitation contract。这是真正的新数据源轴，novelty gate 应可过。
2. **LLM 字段（schema 绑定，无交易权限）**：对每条事件输出
   `{event_type, primary_entity(可非上市), affected_tickers[]:
   {ticker, relation_type(theme|competitor|supplier|customer|proxy),
   direction, confidence, evidence_span}, magnitude, source, published_at,
   text_hash, ontology_version}`。prompt + 输出全量归档，可重放。
   禁止 LLM 直接给买卖/仓位指令（AGENTS.md §1、playbook §6）。
3. **回放面（关键优势：不用纯等 forward）**：新闻档案覆盖
   **2026-01-23 → 今天（82 个交易日）**，其中 ~3 个月落在第三 canonical 窗口
   内。可以立刻做一轮 observed-only 历史回放：事件 → 次日开盘 → 5d/10d
   替换价值，对照组用**同日显式 ticker 新闻行**（沿用 exp-20260630-002 的
   对照纪律）和 accepted relation comparator（rolling-corr peer shock）。
4. **前向埋点**：把 propagation 字段并入已落地的结构化事件观察合同
   （daily + intraday observer），forward 行自动累积。
5. **晋级路径**：回放 lead 正向 → `candidate_pool_full_stack` 一轮出
   paper-sleeve 结论；LLM 输出只作为候选池字段进 Gate 1-4。

### 诚实的风险（预登记，不要事后发现）

- **LLM 训练数据 look-ahead**：模型可能"记得"2026 年上半年事件的后续走势。
  缓解：schema 限定为对文本内容的分类（evidence span 绑定）、禁止输出结果性
  词汇；回放结论只记 observed-only lead，**确认性证据必须来自 forward 行**。
- **RSS 时间戳滞后 / PIT 污染**：`published_at` 是 RSS 声称时间，需按
  sanitation contract 的 provenance 检查；入场一律次日开盘。
- **拥挤与衰减**：headline alpha 衰减快（external research map），传导层
  （二阶标的）可能比直接标的衰减慢——这本身就是要测的假设。
- 事件稀疏：主题级大事件频率低，样本可能不足以过 Gate 4 的 trade count 约束；
  预先声明最小事件数阈值，不够就停在 observed-only，不做阈值挖矿。

### 现状摄取端的三个结构性缺口（2026-07-01 实测 `quant/sources.py` + 06-30 raw 档案）

1. **召回是查询驱动的**：只有 ~14 个手写 ticker 关键词 + 1 条宏观查询
   （`Federal Reserve rates`）+ per-ticker 生成查询。你没搜的主体永远不出现；
   Google 的相关性排序还叠加了一层不可重放的选择偏差。
2. **深度只有标题**：2026-06-30 raw 档案 2,531 条中 ~88% 的 `summary` 就是
   `title` 本身。LLM 事件抽取实际输入是每条 ~10 个词，谈不上
   actor/relation/magnitude。
3. **传闻不可见**："消息流出"类事件（owner 场景）先出现在社交/预测市场，
   Google News 只收编辑化媒体，滞后数小时到数天，且 RSS `published_at`
   是转载时间不是首见时间。

### 源栈分层设计（按 PIT 质量 × 工程量排序）

| 层 | 源 | 拿到什么 | PIT 质量 | 工程量 |
|---|---|---|---|---|
| L1 结构化一手 | SEC EDGAR **S-1/F-1**（IPO 注册）、8-K items、425（并购）、13D | "X 要上市/被收购"的**机器可读 ground truth**，不需要 NLP | 最高（accepted timestamp） | 低：EDGAR 管道已存在 |
| L2 通讯社全文 | GlobeNewswire / PR Newswire / Business Wire / Accesswire 免费 RSS | 公司自发事件**全文** + 精确时间戳（Google News 索引的就是它们） | 高 | 低-中 |
| L3 事件概率 | Polymarket / Kalshi 公开 API | **量化的传闻强度**：`P(SpaceX IPO by 2027)` 的跳变就是"消息流出"时刻，带时间戳、零 NLP | 高（逐笔可回放） | 低 |
| L4 全球实体流 | GDELT 2.0（免费，15 分钟更新，实体/主题/情绪标注） | 解决"未知的未知"——无法预枚举的实体事件召回 | 中（需首见去重） | 中 |
| L5 注意力/拥挤 | Reddit 公开 JSON、HN Algolia、Google Trends、Wikipedia pageviews | 拥挤度 context 字段，**不是信号**（repo 历史：注意力≈beta） | 中 | 低 |

L1 值得单独强调：owner 的例子"SpaceX 要上市"在监管世界里就是**一份 S-1**。
IPO/并购/分拆这类最大的主题传导事件有免费、精确、无传闻噪声的一手源，且本
仓库 EDGAR 摄取已建好——这一层几乎是零新供应商风险的纯增量。

### 架构升级：把 LLM 从热路径挪到图谱维护

比"每条新闻让 LLM 现场推断受影响标的"更可审计的两层结构：

- **慢层（LLM 离线维护）**：版本化的**实体→暴露图谱** artifact：
  私有公司/产品/高管/监管机构 → 上市标的，边带
  `relation_type / direction / confidence / evidence / version`。
  LLM 定期增量更新，人和 novelty gate 都能 review 一个静态文件。
- **快层（确定性 join）**：事件流（L1-L4）按实体名/别名确定性匹配图谱，
  产出传导候选行。回放时零 LLM 调用、零 look-ahead 争议。

这同时缓解了前述 LLM look-ahead 风险：图谱只描述"谁和谁有什么关系"（慢变、
可核对），不描述"这件事后来涨没涨"。

跨源确认复用已 accepted 的 `lagged_cross_source_consensus` 模式：同一事件元组
被 L2 全文 + L4 GDELT + L3 概率跳变独立确认，作为事件质量字段，而非各源
单独成信号。去重以 `text_hash` + 跨源最早 `published_at` 定义首见时刻。

### 落地优先级（每步独立可判）

1. L1：S-1/F-1/425 结构化事件流接入既有 EDGAR 管道（零新依赖）——
   **已建成 2026-07-02（exp-20260702-008，accepted_measurement_repair）**：
   `quant/sec_corporate_event_stream.py` 用 EDGAR quarterly full-index
   （8 请求覆盖全历史，绕开 daily-index 403 限流）物化
   `data/non_ohlcv/sec_corporate_event_stream/rows.jsonl`，17,335 行
   （fresh IPO 注册 2,540 / IPO 修订 4,517 / 425 并购通信 10,278），
   三个 canonical 窗口 + current 全覆盖；68% 行可解析 ticker，未解析行
   即私有/pre-IPO 主体（传导方向的主体侧）；425 同一 accession 保留
   收购方+标的方双行。`--daily` 模式单请求刷新当前季度，run.py 接线
   暂缓（避免与活跃 claim 冲突）。下一步 = 第 4 项实体→暴露图谱，
   然后跑分离 gate 的传导 alpha 实验；
2. L2：三大通讯社 RSS + 全文归档（升级 LLM 输入深度，走既有 sanitation contract）；
3. L3：Polymarket 探针（半天可判：市场清单覆盖率 + 历史逐笔可得性）；
4. 实体→暴露图谱 v1（LLM 离线生成 + 人工抽查，版本化入库）——
   **已建成 2026-07-02（exp-20260702-009，accepted_measurement_repair）**：
   `quant/entity_exposure_map.py` 三层结构——实体 CIK→SIC（确定性，
   1,917/1,958 实体有 SIC，98%）、SIC→上市同业索引（本地 submissions
   缓存，2,774 ticker / 329 SIC 桶）、`theme_overlay_v1_20260702`
   （18 主题，LLM 离线策展、构建时对上市侧校验剔除不可交易 peer）。
   SIC 6770 空白支票 SPAC（332 家）自动排除。确定性 join 覆盖
   fresh IPO 事件 82.6-90.4%/窗口，共 ~47k 暴露边（~5.3k 主题边），
   边**不带方向声明**——方向是下一个分离 gate 实验的问题。
   artifact：`data/non_ohlcv/entity_exposure_map/`。
   **传导归因第一读已完成（exp-20260702-017，observed_only 无边际）**：
   fresh 私有主体 S-1/F-1 → theme-peer 次开盘 10d SPY-excess vs 同 ticker
   无条件基线，449 settled 行，三窗口中位 delta -39.4 / -0.0 / -115.2bp，
   pooled -28bp——方向**偏负**（同主题 IPO 供给 ≈ 轻微利空 peer）但
   mid_weak 平，符号不一致，未过预登记判定。禁止在同一事件人群上换
   主题子集 / 关键词 / horizon / 密度切片重试；合规的下一步是**新事件
   类**（425 并购侧传导、S-1/A 定价区间轨迹、deal size vs 主题 float）
   或已上市增发（shelf/secondary）稀释信号——事件流里 ticker_status=
   resolved 的 S-1 行就是这个信号的现成面；
5. L4 GDELT 按图谱实体过滤接入（召回补全，工程量最大，放最后）。

警惕：源变多不等于 alpha 变多——每个源都要过自己的 PIT contract，最终判据
仍是替换价值 vs accepted comparator。不要一次全接；每层接完先跑一轮
observed-only 回放看事件密度和方向，再决定下一层。

## 三、其余三个候选方向（按原优先级保留）

### 1. Kova SEC13F active-flow → 补历史 PIT 覆盖，跑全栈 Gate 1-4

24h 内唯一活过 10d 的 lead（`exp-20260701-009`）。与冻结的
sponsorship/coownership 家族有真实区分：active-flow 是季度间主动管理人
**增减仓流量方向**，不是持仓水平。阻断项 = 历史 Gate-4 覆盖，而
"为 forward-only 面补历史 PIT 覆盖"是 playbook 明文合规轴。本地 13F holdings
summary + CUSIP 映射（2026-06-13，79% 覆盖）大概率可离线构建。第一步：用
filing-date（非 period-end）做 PIT join 铺三窗口，然后
`candidate_pool_full_stack` 一轮。风险：45 天披露滞后可能稀释边——这正是
Gate 4 要回答的。

### 2. moomoo OpenAPI 历史 capital-flow：把 forward-only 面变成可回放面

playbook 对 moomoo capital-flow 的 block 理由只有"forward-only、仅当前快照"。
moomoo OpenAPI `get_capital_flow(period_type=DAY)` 支持**历史日频**主力/大单
净流入序列——验证属实即杀掉阻断项，开出一个从未在 canonical 窗口测过的资金流
面（真正新历史数据源，不撞 saturation 闸门）。与已冻结的 `short_volume_ratio`
互补（主动买卖盘方向 vs 空头成交占比）。第一步是小时级数据探针：历史深度、
PIT 语义（是否回填/修订）、broad universe 覆盖；vendor-as-of 控制按期权账本
同等标准，过不了就 Gate 2 拦。

### 3. 入场端风险预算实验（risk allocation，非出场 reslice）

把 `exp-20260630-018` 的三窗口一致 regret lead 转到**入场决策面**：
`actual_risk_pct` 下单前已知、production-visible，"高 entry-risk 行降
notional / 收紧 risk-budget scalar"的固定 bundle 直接走三窗口 Gate 1-4，
不碰冻结的 stop/target/hold 参数，天然自带 execution envelope。注意 §5 硬
门槛：capital/risk allocation 调参需 aggregate EV 提升 >10%，预期上限有限，
但它是唯一不被日历/数据构建绑定、当周可判定的方向。出场端同人群 observed-only
探测已近饱和计数，**不要再切出场条件**。

## 四、排序与止损条件

- **方向 0（新闻+LLM 传导）**：owner 偏好 + 新数据轴 + 有 5 个月回放面，排第一。
  止损：若实体级摄取两周内累积可判事件 < 预登记阈值，或回放 lead 为负，停在
  observed-only，不做关键词/阈值挖矿（否则就是 exp-20260630-002 的复读）。
- **方向 1（Kova active-flow）**：最强纯 alpha 假设，与方向 0 并行不冲突。
  止损：历史 PIT join 若只能覆盖 <2 个窗口，降级为 forward-only 埋点，不硬跑。
- **方向 2（moomoo 历史资金流）**：期权价值最高的数据探针，半天可判。
  止损：无历史深度或非 PIT（回填/修订不可辨）→ 记 blocked + reopen_condition。
- **方向 3（入场风险预算）**：最快可判定、离 live 最近，作为填充任务。

不该占实验 ID 的事（§2 reopen 闸门）：结构化新闻成熟度审计、estimate-revision
再切片、短量 soft tilt（等每 quintile 行数）、forward 激活 readiness 复读、
Kova/13F 在同批 partial 行上的第 N 次条件切片。
