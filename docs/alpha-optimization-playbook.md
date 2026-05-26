# Alpha Optimization Playbook

本文件是 Ginger 的长期 alpha 研究手册。它连接
[`AGENTS.md`](D:/Github/ginger/AGENTS.md)、
[`docs/backtesting.md`](D:/Github/ginger/docs/backtesting.md)、
[`docs/current_state.md`](D:/Github/ginger/docs/current_state.md) 和
[`docs/experiment_log.jsonl`](D:/Github/ginger/docs/experiment_log.jsonl)，但不充当实验日志。

它只保留四类内容：

1. 仓库证据已经证明的机制级先验；
2. 不应再近邻重试的方向；
3. 未来 1-3 轮更值得投入的 alpha / 字段队列；
4. 最新研究能转成哪些可回放、可归因、可生产可见字段。

Last refreshed: 2026-05-26.
Research refresh cut: 2026-05-26.

## 使用方式

开始任何策略改动前，先回答：

1. 本轮属于 `allocation`、`field`、`entry`、`exit`、`candidate_pool` 还是 `measurement_repair`？
2. 这是不是同一家族的近邻重试？如果是，新证据是什么？
3. 这次能否只引入一个生产可见、回放安全的变量？
4. 如果不能，是被哪个字段、归因或 parity 缺口阻断？

默认决策顺序：

1. 优先 `alpha_search`，除非测量缺陷直接阻断高价值 alpha。
2. 优先新增解释字段，而不是再扫相邻 scalar。
3. 优先 default-off sleeve / paper adapter，而不是直接扩 core。
4. 优先 replacement value 与 concentration 治理，而不是只看 standalone PnL。
5. 优先共享生产可见逻辑，而不是 replay-only 的聪明规则。

## 一页结论

Ginger 仍然是事件增强型中短线趋势 / 突破系统。仓库证据和最新研究共同指向一个更窄的赚钱路径：

1. **核心 live alpha 主要来自已入选信号上的小幅 allocation 改善。**
   广义 entry/filter 重写通常不如窄条件 post-sizing top-up 稳定。
2. **新字段比新阈值更值钱。**
   同一族 queue/profile/notional/scalar 在冻结窗口上反复扫参，边际价值已经很低。
3. **default-off sleeve 是新 alpha 的主孵化器。**
   broad-market、event、SEC、state-surface、AI infra、suspect cohort 都应先在 sleeve 里成熟。
4. **replacement value 比 standalone PnL 更重要。**
   “它赚钱”不够；必须回答“它是否优于 cash / 被替换掉的 core 机会 / 相邻 queue rank”。
5. **concentration 是 promotion blocker。**
   单 ticker、单主题、单 source、单窗口驱动的 uplift，默认不该升级成 live capital。
6. **LLM 最有价值的职责是结构化解释，不是交易拍板。**
   适合做 event extraction、事实/语气拆分、topic gap、异常披露解释、灾难 veto 候选；不适合接管 sizing、硬风控、slot、exit。

## 仓库稳定经验

### 1. Allocation 胜过 Filtering

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

解释：近期最稳定的改善来自“对已经过关的交易分配更多/更少资本”，而不是“让更多规则决定谁能进门”。但 2026-05-24 至 2026-05-25 的实验继续提醒：即使是 allocation，若只是 ticker/cohort/固定 notional 的近邻复用，也会被窗口回归和 concentration 拦下。

### 2. 一个好字段胜过一串例外规则

噪声队列通常不会因为再叠一层 generic guard 而变好。它们通常会因为更贴近机制的字段而变好，例如：

- source credibility；
- topic attention divergence；
- fact/tone disagreement；
- crowding / overlap；
- disclosure quality；
- state persistence vs extension；
- segment / KPI revision；
- policy or macro exposure label。

如果一个想法需要很多 if/else 才成立，通常说明字段层还没建好。

### 3. Sleeve 是正确的试验边界

以下方向默认先做 sleeve，不直接做 core：

- broad-market 候选池；
- external event overlays；
- SEC event families；
- suspect ticker cohorts；
- passive/index mechanics；
- theme / pilot / AI infra 子组合；
- microstructure / policy-uncertainty 外部数据。

这些方向最需要：

- 明确的 candidate definition；
- replacement-value accounting；
- concentration 审计；
- closed forward outcomes；
- kill switch；
- 与 core 资本竞争时的可解释性。

### 4. Replacement Value 是硬门槛

任何新 sleeve 都应明确回答：

- 是否优于 cash？
- 是否优于同日被它挤掉的 core 候选？
- 是否优于相邻 queue rank？
- 是否只是把一个大赢家集中放大？

没有 replacement-value 证据的高 paper PnL 只算研究线索，不算 promotion 证据。

### 5. Exit 改动要比 Entry 改动更谨慎

仓库历史和近期结果都表明：

- 简单把 target 变宽、分批止盈、局部 target pool 化，常常破坏赢家；
- 即使 aggregate PnL 看起来变好，也容易带来旧窗口退化或 drawdown 漂移；
- exit 的 lookahead 诱惑很强，最容易把 oracle gap 误当作可交易 alpha。

默认结论：先用 oracle / shadow attribution 解释“为什么当前 exit 没抓住利润”，再把证据转成共享字段或完整生命周期设计；不要直接把后视最优动作硬编码成规则。

### 6. LLM 的正确位置是可审计解释层

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
- `segment_change_bucket`
- `kpi_revision_direction`
- `regulatory_exposure_bucket`

不应该直接让 LLM 决定：

- 仓位大小；
- 止损与目标；
- slot priority；
- portfolio heat；
- 是否绕开硬过滤；
- 最终交易指令。

## 当前研究队列

以下是当前默认优先级，不是永久真理。若实验日志改变机制结论，再更新这里。

### 1. Default-off attribution 与 promotion readiness

`meta_research_engine.py` 最新报告把 default-off attribution report surface 放在最高优先级附近。原因不是它直接交易，而是它能把已有 paper alpha 的 blockers 统一成可行动队列。

优先做：

- 每个 sleeve 的 closed forward outcome、replacement value、concentration、drawdown、kill-gate 状态；
- paper sleeve 与 core/cash/相邻 rank 的同日替代价值；
- activation blocker 的稳定分类，而不是继续堆局部 scalar；
- 把“可单独 activation review”的候选输出成生产可见报告字段。

默认不做：

- 用 dashboard 分数直接改变 live sizing；
- 把 default-off sleeve 的 paper PnL 直接并入 core metrics；
- 在没有 closed forward rows 时为 paper uplift 找 promotion 借口。

### 1.1 Volatility-contraction + QQQ confirmation lead

机制结论：

- VCP 的有效增量来自一个正交、生产可见的市场确认字段：
  `QQQ 20d return > SPY 20d return`。这类字段比继续调压缩、突破、ATR、
  sector 或 QQQ/SPY 阈值更有价值。
- top-2 candidate depth 可以作为 default-off paper adapter 的观察路径；它
  不是 live capital，也不是继续扫 top-N 的许可。
- 在已固定 top-2 candidate set 上，rank-2 可以小幅高配。当前共享
  default-off paper adapter 使用 `[1.0, 1.25]` rank-notional profile；它
  通过的是 paper allocation gate，不是 core sizing gate。
- pocket-pivot、pre-signal event presence、prior catalyst / volume-support
  dossier 都更适合做 read-only context 和 forward diagnostics。它们在冻结样本
  上没有证明自己能替代 QQQ-confirmed VCP allocation gate。
- late_strong 的弱点更像 rank-depth scarcity / underparticipation，而不是
  QQQ gate 过严。不要用单窗口低参与度当作放松 gate 的理由。
- post-entry 3-session follow-through 能解释结果，但不是入场前可知字段；不能
  直接变成冻结样本上的 exit / risk rule。

保留规则：

- 当前固定对象是 QQQ-confirmed VCP top-2 default-off paper adapter，rank
  profile 固定为 `[1.0, 1.25]`。
- 下一步只能收集 closed forward replacement-value rows、concentration、
  kill-gate、core displacement 证据，或引入真正新的生产可见字段。
- 禁止在同一冻结样本上继续 retune QQQ/SPY、ATR、breakout、pocket-pivot、
  event-presence、catalyst-quality、top-N、rank-notional profile 或 post-entry
  follow-through 阈值。

### 1.2 Volume-breadth breakout lead

机制结论：

- `exp-20260526-013` 显示，免费 OHLCV 的市场内部结构字段可以改善候选池：
  same-date up-volume breadth thrust + liquid breakout top-1 在三窗口里都提高
  EV/PnL，且 drawdown 与集中度通过。
- `exp-20260526-014` 后，该方向的正确边界是 shared default-off paper adapter，
  用生产可见的 daily OHLCV + `SPY` 生成 forward ledger，而不是继续在冻结样本上
  重扫 breadth / breakout / volume threshold。
- 这条线索更像“候选池质量 + 市场参与度确认”，不同于已经冻结的 gap-and-hold、
  smooth momentum、undercut reclaim、long-base、pocket-pivot、pullback-reclaim
  机械形态 retread。
- `exp-20260526-021` 显示，动态 breadth recovery（从较弱的 5 日前
  above-50d 状态恢复）是方向性线索而不是可提升规则：三窗口 EV/PnL
  全部改善，aggregate EV `+0.2002` / PnL `+$2,796.77`，drawdown 与
  concentration 通过，但只有 12 笔 paper trade，低于 20 笔样本门槛。
  这应被视为 forward watch / 新字段候选，不是冻结样本上继续调 recovery
  lookback、above-50d 或 volume 阈值的许可。

保留规则：

- 当前固定对象是 `VOLUME_BREADTH_BREAKOUT_PAPER` default-off paper adapter：
  top-1/day、固定 `$10k` paper notional、next-open entry、10-trading-day close
  exit、trade_enabled=false。
- 下一步只能收集 closed forward replacement-value rows、concentration、
  same-day core displacement / cash-relative value 和 kill-gate 状态。
- 禁止在同一冻结样本上继续 retune up-volume breadth、market-up fraction、
  above-50d fraction、candidate volume ratio、breakout lookback、top-1/top-N 或
  fixed notional，除非有 forward rows 或一个真正新的生产可见确认字段。
- 动态 breadth recovery 只能用 forward rows 或正交 source-quality 字段继续；
  不要把 exp-021 的小样本正向结果改写成新阈值搜索。

### 2. State-surface：从调 profile 转向解 concentration

现状：

- `STATE_SURFACE_SATELLITE` 已有多轮 accepted paper uplift；
- 继续在 queue/profile/notional/scalar 上做近邻调参，已经进入高多重检验风险区；
- state-surface 加严规则要求同类调参必须有 >10% aggregate EV 提升，否则默认回滚。

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

### 3. Event overlay：从证明方向转向治理 source/context 质量

现状：

- external event overlay 已经证明 default-off paper 方向有效；
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
- 没有新增 forward rows 的 semantic-cell 放大；
- 只因某个 state bucket 在冻结样本负 PnL 就不断加 haircut。

### 4. Broad-market leadership：从 paper queue 转向资本安全

现状：

- `BROAD_MARKET_LEADERSHIP_PAPER` 已有较强 paper 证据；
- 上限大，但也最容易引入 feed leakage、hidden beta 和 crowding；
- 最近 broad-market identity drift 说明候选 feed 必须先固定和版本化。

接下来只优先：

- 固定 production candidate feed；
- closed forward outcomes；
- replacement value vs core / cash；
- hidden beta / sector concentration / crowding；
- 明确 sleeve slots、capital cap、kill criteria。

默认不做：

- 冻结样本上的相邻 trend / extension / volatility / persistence retune；
- 用 broad-market paper 胜率替代 capital competition 证据。

### 5. SEC / earnings semantics：最高价值字段化路线

这是最符合 Ginger 事件增强型趋势定位的研究线。最新研究继续支持一个结论：earnings-call alpha 不能只做 sentiment，而应做时间一致、可 walk-forward 的结构化字段。

最值得补的字段：

- `fact_tone_gap_bucket`
- `guidance_delta_direction`
- `topic_attention_divergence_bucket`
- `manager_nonresponse_bucket`
- `special_call_flag`
- `disclosure_quality_bucket`
- `attention_persistence_bucket`
- `in_call_information_timing_bucket`
- `ear_ai_bucket`
- `analyst_belief_revision_pressure`
- `segment_change_bucket`
- `segment_kpi_revision_direction`
- `regulatory_exposure_bucket`

这些字段适合先进入 paper queue / paper notional / event routing，不适合一上来进入 core hard filter。

### 6. Ticker governance / no-trade alpha

核心栈已经很密。接下来更可能赚钱的是：

- 哪些 cohort 应被 sleeve 化；
- 哪些 cohort 只该 paper 跟踪；
- 哪些 cohort 的价值主要来自 no-trade avoided value；
- 哪些 ticker 应降权而不是加新过滤器。

优先证据：

- ticker / setup / regime contribution table；
- no-trade avoided value；
- closed forward paper outcomes；
- capital-routing 对比，而不是单纯删 ticker。

近期经验：core-misfit 与 AI infra / compute-memory 一类方向已经多次被 concentration、窗口回归或样本太薄拦下；下一步需要 forward replacement-value rows 或新的质量字段，不要在同一冻结样本上继续换固定 notional。

### 7. Execution leakage attribution

如果 live return 持续低于回测潜力，执行摩擦可能比再调阈值更值得研究。

优先项：

- gap erosion attribution；
- missed fill / delayed fill cohorts；
- next-open 假设与真实执行偏差；
- liquidity / spread / signal-time 的 drift 分层。

### 8. Expectation revision：先证伪“强者更强”，再做 PEAD sleeve

近期 expectation-revision attribution 的主要价值不是已经产生可交易规则，而是纠正了一个直觉：
正向 EPS revision 叠加 residual leadership 不一定是更强确认，可能是短线 overextension。

当前先验：

- 严格 PIT-positive 7d EPS revision 是值得继续积累的 event state；
- `neutral` / `beta_lagging` 的非过度延伸状态，比 `overextended_residual_leader`
  更像下一轮 PEAD watchlist 的候选方向；
- 当前样本仍被 closed 10d/20d outcome 成熟度和单 ticker 正贡献集中度阻断；
- wide watchlist 只能用于覆盖率和候选发现，不能替代严格 PIT primary bucket。

下一步只优先：

- 继续收集 PIT 7d/30d revision ledger 和 closed 5/10/20d outcomes；
- 把 `non_overextended_revision_positive` 做成 read-only watchlist bucket；
- 报告 concentration、candidate-hit lag、current-position overlap；
- 等成熟后再考虑 default-off PEAD paper sleeve。

默认不做：

- 把缺失 revision delta 当作正向 revision；
- 用 reconstructed / non-PIT scout rows 满足 promotion gate；
- 把 residual leadership 直接当作确认 top-up；
- 在 concentration 未过关前做 core ranking 或 sizing 改动。

## 反复重试禁区

若没有 `new_forward_rows`、`new_production_visible_field`、`new_replacement_value_cohort` 或更广 PIT 样本，不要重试：

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
13. 为 1-3 笔亏损交易新增专门例外；
14. AI infra / compute-memory / optical 子主题在同一冻结样本上继续换 fixed-notional sleeve；
15. core-misfit cohort 在没有 forward closed outcomes 时继续做硬 no-entry 或长仓 haircut；
16. SEC text archive missingness 作为 allocation signal；
17. raw ranking component threshold / scalar，尤其是字段近似常量或覆盖不足时；
18. expectation-revision 方向里把 residual leadership 当作默认确认信号；
19. VCP top-2 方向里继续扫 rank-notional、top-N 或 post-entry follow-through 阈值。

## 研究到字段的落地地图

以下部分只保留能直接转成 Ginger 字段或流程的研究。

### 1. Earnings-call LLM alpha 必须时间一致、可 walk-forward

主要研究：

- Zhang & Zhou, *Large Language Models for Asset Pricing: Learning from Earnings Calls* (SSRN, 2026-05-04; revised 2026-05-10):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6712298>
- Molinaro, *Do earnings call transcripts predict post-announcement returns?* (SSRN, 2026-05-02):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6695758>
- Ghosal, *LLM-Driven Investment Models: Can Large Language Models Extract Alpha from Earnings Call Transcripts?* (SSRN, 2026-04-22):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6351439>

对 Ginger 的含义：

- LLM call 信号可以有 cross-sectional alpha，但必须做 chronological consistency / walk-forward；
- 不要把 embedding 或模型分数直接变成 live trade，先落成 bucket、coverage、lag、成本和稳定性字段；
- call 信号应与 PEAD、guidance、revision、event family 做归因对比，证明增量信息。

优先字段：

- `ear_ai_bucket`
- `call_embedding_return_rank_bucket`
- `post_call_idiosyncratic_return_forecast_bucket`
- `call_signal_lag_days`
- `walk_forward_fold_id`
- `call_signal_subsumes_pead_flag`

最低落地标准：

- 训练/评分按时间切分，不混未来 call；
- 字段落盘到 daily snapshot；
- 与 earnings surprise、revision、PEAD 的增量解释单独报告。

### 2. Earnings call 的信息不是平均情绪，而是主题错位与释放时点

主要研究：

- Xiao & Zhang, *Measuring Information Quality by Topic Attention Divergence* (SSRN, 2024; revised 2026-02-23):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4723491>
- Oh, *Price Discovery Within Earnings Calls* (SSRN, 2026-01-20):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6105146>
- Brull, Marshall & Moss, *Sustained Investor Attention* (SSRN, 2025-06-24):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5318279>

对 Ginger 的含义：

- 不要把 call alpha 简化成一个总 sentiment；
- 更值得做的是管理层主题、分析师追问、Q&A 追问强度之间的 gap；
- 信息释放发生在 call 内哪个阶段，可能影响后续 drift。

优先字段：

- `topic_attention_divergence_bucket`
- `manager_analyst_topic_gap_flag`
- `in_call_information_timing_bucket`
- `attention_persistence_bucket`

### 3. 怎么说和说了什么要分开，内容通常先于语调

主要研究：

- Matera, *Corporate Earnings Calls and Analyst Beliefs* (SSRN, revised 2026-04-01):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5763085>
- Beckmann et al., *Unusual Financial Communication: ChatGPT, Earnings Calls, and Financial Markets* (SSRN):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4699231>
- Guo & Lo, *Formal and Informal Language in Earnings Conference Calls* (SSRN, 2025):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5174884>

对 Ginger 的含义：

- 语言特征可影响 analyst belief revision，但不能替代事实字段；
- confidence、uncertainty、forward guidance、macro focus 应被拆成字段；
- delivery / abnormal style 更像风险解释、异常披露或 crowding 佐证。

优先字段：

- `analyst_belief_revision_pressure`
- `forward_guidance_language_bucket`
- `uncertainty_language_bucket`
- `macro_focus_bucket`
- `unusual_communication_bucket`
- `formal_informal_gap_bucket`

### 4. Facts 与 Tone 必须显式拆分

主要研究：

- Gong, Li & Zhang, *Decrypting Corporate Speak: GPT-Assisted Measurement of Facts and Tones in Earnings Calls* (SSRN, 2024):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4950924>

对 Ginger 的含义：

- 正面语气不等于基本面改善；
- promotional language 与 operational facts 应分开；
- fact/tone disagreement 比单纯正负面更适合跨事件迁移。

优先字段：

- `fact_direction_bucket`
- `tone_direction_bucket`
- `fact_tone_gap_bucket`
- `operational_fact_density_bucket`

### 5. SEC / filing extraction 要做 bitemporal structured state

主要研究：

- Liu, Cheng & Lai, *Improving the Completeness and Comparability of Segment Disclosures: A Large Language Model Approach* (SSRN, 2026-03-28):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6720239>
- *Just-in-Time Historical State Reconstruction for Low-Latency Financial Trading with Large Language Models* (MDPI, 2026):
  <https://www.mdpi.com/2673-2688/7/4/117>
- *Harnessing Generative LLMs for Enhanced Financial Event Entity Extraction Performance* (arXiv:2504.14633):
  <https://arxiv.org/abs/2504.14633>

对 Ginger 的含义：

- 事件抽取应输出结构化 JSON，不是自由文本结论；
- segment/KPI/filing facets 要可回放到任意历史交易日；
- 每个字段要绑定 source doc、filing time、span offsets、schema version。

优先字段：

- `event_family_v2`
- `event_argument_json`
- `segment_change_bucket`
- `segment_kpi_revision_direction`
- `source_doc_id`
- `filing_available_at`
- `span_offsets`
- `ontology_version`
- `extraction_consistency_bucket`

### 6. LLM 金融文档上线关键是评估与编排，不是模型更大

主要研究：

- *Fin-RATE* (arXiv:2602.07294, 2026-02-07):
  <https://arxiv.org/abs/2602.07294>
- *SECQUE* (arXiv:2504.04596):
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

### 7. Disclosure quality 是 event alpha 的主轴

主要研究：

- Dechow et al., *Beyond Earnings Quality: Evaluating the Quality of Corporate Disclosure Practices* (SSRN, 2025; revised 2026-02-27):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5257154>
- Hu & Shohfi, *Special Conference Calls* (SSRN, 2025-09-10):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5598490>

对 Ginger 的含义：

- event alpha 不能只看 event family；
- 还要看披露是否主动、具体、在特殊 call 中补充、并带来增量信息；
- governance / procedural / special-call 事件尤其适合做 disclosure-quality 路由。

优先字段：

- `disclosure_quality_bucket`
- `special_call_flag`
- `management_commitment_specificity_bucket`
- `source_credibility_bucket`
- `incremental_disclosure_flag`

### 8. Policy / regulatory exposure 可作为事件状态字段

主要研究：

- JFQA, *Measuring the Cost of Regulation: A Text-Based Approach* (2026-05-12):
  <https://jfqa.org/2026/05/12/measuring-the-cost-of-regulation-a-text-based-approach/>
- Byerly, *AURA Policy Uncertainty Index* (SSRN, 2026-04-22 revision):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6239958>
- Calomiris, Mamaysky & Yang, *Measuring the Cost of Regulation: A Text-Based Approach* (SSRN, last revised 2026-05-13):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3550922>
- Baz et al., *Climate Regulatory Exposure and the Stock Market: Evidence from the Trump Elections* (SSRN, 2026):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6106614>
- Ran, *Managerial Attention to Financial Markets: Evidence from Managers' Own Discussion* (SSRN, revised 2026-04-23):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5241047>

对 Ginger 的含义：

- regulatory / policy exposure 不是简单负面新闻；它可能同时代表成本、风险、放松监管后的重估和管理层对融资条件的关注；
- prediction-market implied uncertainty 更适合作为 market-state / risk-allocation context，而不是单票 entry 信号；
- 先做 read-only event state 与 market-state attribution，再分行业、规模、融资需求和政策事件窗口判断。

优先字段：

- `regulatory_exposure_bucket`
- `regulatory_exposure_direction_bucket`
- `regulatory_relief_sensitivity_bucket`
- `climate_regulatory_exposure_bucket`
- `manager_market_attention_bucket`
- `financing_need_context_bucket`
- `policy_uncertainty_pressure_bucket`
- `policy_repricing_intensity_bucket`
- `event_contract_dispersion_bucket`
- `policy_event_window_id`

### 9. Buyback 不是看到 repurchase 就加分

主要研究：

- Bargeron et al., *Voluntary Disclosures Regarding Open Market Repurchase Programs* (SSRN / CAR, 2024-01-26):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2486843>
- Andriosopoulos, *Does the daily reporting of share buybacks matter?* (SSRN, 2025):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5287917>

对 Ginger 的含义：

- buyback 关键词覆盖本身几乎肯定太弱；
- 更强的对象是透明度、暂停披露、剩余容量、后续执行一致性。

优先字段：

- `buyback_commitment_strength_bucket`
- `buyback_remaining_capacity_signal`
- `repurchase_transparency_flag`
- `repurchase_followthrough_bucket`

### 10. Form 4 不能脱离 options context

主要研究：

- Jeon & Sulaeman, *Corporate Insider Purchases and the Options Market* (Journal / SSRN, 2024-06-13):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4864272>

对 Ginger 的含义：

- raw insider buying 不是充分条件；
- options-market 活跃度可能解释这笔 insider buy 是否仍有独立信息量；
- 这和仓库里单 owner / 单 queue 样本太薄的现状一致。

优先字段：

- `options_activity_bucket`
- `options_competition_flag`
- `cluster_buying_flag`
- `insider_purchase_context_quality`

### 11. Passive flow / index mechanics 更适合机械 sleeve

主要研究：

- Sammon & Shim, *Who Clears the Market When Passive Investors Trade?* (SSRN, revised 2026-03-01):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4777585>
- Kastenholz, *The Index Event Horizon* (SSRN, 2026-03-17):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6430698>
- Gufler, *Passive Investing, Diversification Risk and Financial Stability* (SSRN, 2026-03-29):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6487578>

对 Ginger 的含义：

- 被动资金和指数事件更像机械流量，不像语义理解任务；
- 适合 deterministic sleeve，而不是让 LLM 自由解释；
- 对 broad-market、ETF、large-cap lower-tier / upper-mid-cap 队列都 relevant。

优先字段：

- `index_event_type`
- `effective_date`
- `passive_flow_pressure_bucket`
- `index_crowding_risk_bucket`
- `firm_issuance_absorption_bucket`

### 12. Daily-return pattern 可做 broad-market 机械特征库

主要研究：

- Cakici et al., *A Unified Framework for Anomalies Based on Daily Returns* (SSRN, 2026-01-02):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6005614>

对 Ginger 的含义：

- broad-market 队列不一定需要更多叙事字段才能开始；
- 日收益路径可能提供统一、低泄漏、低解释负担的机械特征；
- 先放入 broad-market paper sleeve，作为 ranking/support field，不直接改 core signal engine。

优先字段：

- `drif_bucket`
- `short_horizon_return_path_cluster`
- `max_daily_return_20_bucket`
- `reversal_vs_continuation_state`

### 13. Microstructure / public-narrative divergence 只能先做 diagnostics

主要研究：

- Khan & Messaoudi, *Latent Information Reconstruction via Vector Divergence in Market Microstructure* (SSRN, 2026-02-01):
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6272018>
- *TradeFM: A Generative Foundation Model for Trade-flow and Market Microstructure* (arXiv:2602.23784, 2026-02-27):
  <https://arxiv.org/abs/2602.23784>

对 Ginger 的含义：

- order-flow 与 public narrative 的背离可能解释事件前后的 price discovery；
- Ginger 目前没有稳定 order-book feed，因此不能把它做成 live rule；
- 可先用可得代理变量做 read-only attribution：gap、volume acceleration、spread/liquidity、news lag。

优先字段：

- `market_narrative_divergence_proxy`
- `pre_news_price_pressure_bucket`
- `volume_acceleration_pre_event_bucket`
- `public_information_lag_bucket`

### 14. Financial retrieval 比一次性长上下文更重要

主要研究：

- *FinRetrieval: A Benchmark for Financial Data Retrieval by AI Agents* (arXiv:2603.04403, 2026-03):
  <https://arxiv.org/abs/2603.04403>
- *Fin-RATE* (arXiv:2602.07294, 2026-02-07):
  <https://arxiv.org/abs/2602.07294>
- *SECQUE* (ACL Anthology / GEM 2025):
  <https://aclanthology.org/2025.gem-1.16/>

对 Ginger 的含义：

- LLM 金融系统的瓶颈通常不是“模型是否聪明”，而是能否检索到正确
  filing、section、period、numeric value 和历史版本；
- 对 SEC / earnings 字段，必须把 retrieval miss 与 reasoning miss 分开记录；
- 不能把长上下文整份塞给模型后直接相信输出。先做 section routing、numeric
  evidence binding、cross-period consistency，再让 LLM 生成 bucket。

优先字段 / 流程：

- `retrieval_source_doc_id`
- `retrieval_section_id`
- `retrieval_period_end`
- `retrieval_value_evidence_json`
- `retrieval_failure_bucket`
- `cross_period_consistency_bucket`

### 15. 机械路径 alpha 必须先证明 replacement value

最新 daily-return、gap-and-hold、smooth-momentum、undercut-reclaim、long-base
breakout 等 candidate-pool scout 的共同教训是：机械价格形态可以产生漂亮局部
PnL，但很容易被 hidden beta、single-window uplift、candidate displacement 或
thin breadth 吃掉。

对 Ginger 的含义：

- 机械形态先进入 default-off candidate source，不直接扩 core；
- 必须报告同日 core displacement、cash-relative PnL、rank-depth breadth、
  hidden beta、single-ticker / sector HHI；
- 如果一个形态需要连续叠加 QQQ gate、sector gate、quality gate、cooldown 才看起来
  成立，通常说明它不是当前最优 alpha 搜索方向。

优先字段：

- `mechanical_pattern_family`
- `pattern_rank_depth`
- `same_day_core_displacement_pnl`
- `hidden_beta_bucket`
- `pattern_breadth_bucket`
- `pattern_decay_after_first_hit_bucket`

## LLM 字段的最低工程标准

任何新 LLM 字段，默认都要满足：

1. **结构化输出**：不是 prompt prose，而是 schema-bound JSON。
2. **证据绑定**：每个字段至少有 document id、timestamp、span。
3. **版本化**：有 `ontology_version` 或 `schema_version`。
4. **失败归因**：能区分 retrieval miss、parse miss、reasoning miss。
5. **纵向一致性**：能做 same-firm-over-time consistency audit。
6. **生产可见**：`run.py` / 日报 / snapshot 中至少能看到最终字段值。
7. **回放安全**：回测字段必须来自当时可得文本，不得借未来文档补全。
8. **时间切分评估**：任何 predictive score 必须有 walk-forward / chronological split。

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
