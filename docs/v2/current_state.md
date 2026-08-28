# V2 Current State

> V2 状态导航入口。每轮结束时更新。真相源永远是 ticket / ledger / 已提交代码，本文件只负责导航。
> 最后更新：2026-08-28T16:55Z（exp-20260828-001 phase2 estimate-revision cash bar 合同修约，数值 gate 首次打开）

## 里程碑

当前处于 **M0（定规则 / T0）**，本轮刚建立 V2 状态文件。M0 尚未完成。

| 里程碑 | 状态 |
|---|---|
| M0 规则 / T0 / 状态文件 | 进行中：状态文件已建；T0 已提议待用户确认（见 decision log d-0002）；V1 资产清单、偏差登记表未开始 |
| M1 身份、时钟、数据合同 schema | 未开始；但直接阻断 forward 证据的 structured-news 首见时钟已由 exp-20260824-002 插队修复，不代表通用 M1 schema 完成 |
| M2 动态 PIT 股票池 | 未开始 |
| M3 共享 SDK 与 Engine-0 干净基线 | 未开始 |
| M4-M9 | 未开始 |

## 关键边界（当前生效）

- `trade_enabled=false`；V2 不继承 V1 股票名单、alpha 结论、资格、权重、晋级状态。
- M3 Engine-0 baseline 建立前，V2 候选最高停在 research/shadow。
- V1 的 `docs/backtesting.md` baseline 只做回归与机会成本对照，不是 V2 Gate-1 锚。
- `exp-20260824-002` 只接受 measurement repair，不接受 alpha；structured-news pair 不产生 signal、paper fill、OrderIntent 或订单。

## 最新可执行证据状态（2026-08-24）

- 新 structured-news exposure 行冻结不可变本地 `first_seen_at`；旧 v1 行不倒填、不准入。
- forward readiness 只检查同批负面/正面两侧、ticker 不重叠、单侧 ticker 行权重不超过 40%，以及 first-seen 时点已经归档且不超过 3 个日历日的 iBorrowDesk 正可用量/有效费率。
- iBorrowDesk 明确只是 indicative research evidence，不是 broker locate；`trade_enabled=false`。
- 97 个 focused tests 与 lean-strict experiment audit 通过；canonical baseline SHA-256 仍为 `4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731`。
- 不再把 forward 当唯一入口：先 outcome-blind 审计每日快照哈希、最早 Git/归档时间、映射版本、价格和借券的历史交集。若能保守重建足量 `known_at`，可立即开独立历史验证；只有无法还原时才等待真实 `measurement_ready` batch。forward 接受仍需 20 个 closed baskets、至少 10 个 decision dates、成本后净 spread 为正、前后半段均为正、单 ticker 绝对毛贡献不超过 40%。
- `exp-20260824-003` 已把上述原则落到一次完整 alpha 回放：先从 5,065 份 S-1/F-1 解析资格中 outcome-blind 预筛到 181 份可交易候选，再冻结 118 个明确含 selling-holder resale 证据的决策（38/45/35，84 tickers），最后才占号读取结果。
- 冻结的 short-stock + equal-notional long-SPY H10 pair 在 90bp 两腿总成本和 20% 年化借券假设后，三个窗口分别为 `+$1,543.16 / +$6,770.53 / +$1,787.26`，合计 `+$10,100.94`；180bp 双倍成本压力后仍为 `+$7,976.94`，重叠持有期 cluster bootstrap 90% 区间为 `+$5,456.32 ~ +$15,398.18`。118/118 行完整，集中度门槛全部通过。
- 该结果严格停在 `observed_only_positive_lead`：历史身份为 research-PIT，SEC acceptance 不等于 EFFECT/实际出售，且没有历史 broker locate。当前最快路径是补 EFFECT/424B3/takedown 时钟与可执行借券证据，不是继续在同一 118 行上扫规则。
- `exp-20260824-004` 已完成最关键的独立时钟否证：118 行中 111 行可精确关联 EFFECT 或 424B3/424B4，重新按激活时点身份/流动性/去重后冻结 83 行（31/23/29）。只把 entry clock 从 acceptance 改为法律激活，其他成本、借券、H10、SPY hedge 全不变。
- 激活时钟结果三窗全部为负：`-$1,728.07 / -$650.85 / -$586.26`，合计 `-$2,965.18`，双成本 `-$4,441.18`，cluster bootstrap 90% 区间 `-$7,046.61 ~ +$1,017.08`；82/83 行可执行，EFTY 缺价。该结果拒绝“EFFECT 后实际供给压制”解释，也禁止再切 EFFECT-only/424-only 或扫 clock/hold/cost。
- 当前可保留的只是 **acceptance 时点公告/预期冲击 lead**，不是已证实的实际供给 alpha。历史近邻回放线到此关闭；若要向赚钱靠近，下一步只能做不改口径的实时 SEC acceptance observer，并在每个决策时点接真实 broker locate/short availability，积累 settled forward replacement value。

## 最新可执行证据状态（2026-08-25）

- exp-20260825-001（measurement_repair, accepted）：iBorrowDesk 抓取管道自 ~07-21 起全死——上游迁移到 www.iborrowdesk.com,裸域 /api 直接断连（RemoteDisconnected）,每日刷新连挂 5 次即中止,PIT 借券归档冻结,pair forward readiness 每个 batch 都被 stale_pit_borrow 永久 fail-close。单行 API_URL 修复;10/10 被阻塞 short 侧 ticker 归档已到 2026-08-24(满足 3 日历日新鲜度),补齐 shard +2580 行(www 限流 http_444 于 ~90 请求/1 req/s 后触发,abort-early 可续传)。
- readiness 剩余阻塞（未动,归 readiness lane 所有者决策）：(1) batch microcap ticker 不在 build_default_refresh_universe,missing_pit_borrow 持续;(2) 轮转节奏无法保证任意 batch ticker 的 3 日新鲜度,需要对活跃 batch short 侧 ticker 定向抓取或改合同;(3) cross_side_ticker_overlap 由数据决定。
- d-0003 gate 不变：≥1 个真实 measurement_ready batch 之前不开 shared paper-policy pair alpha 实验;exp-20260824-001 的单次 pair-build 资格未消耗。

## 最新可执行证据状态（2026-08-26）

- exp-20260826-001（measurement_repair, accepted）：readiness 借券 PIT 规则（archived_at ≤ first_seen_at 且 ≤3 日历日）只有在抓取先于 first_seen 冻结时才可能满足——盲目 stalest-first 轮转结构性做不到且跳过 universe 外 microcap,导致每个 batch 永久 fail-close。修复：`news_event_exposure_observer.run` 在 stamp first_seen 之前对本轮**新增**正极性（short 侧）exposure ticker 定向 refresh_archive（仅生产路径、fail-open、共用 IBORROWDESK_REFRESH_DISABLED 开关）;run.py Step 1.65 shard 预算 150→60,在 ~90 请求 www 限流下给预抓取留余量。闭环验证：27 测试通过;当前受阻 batch 的 23/23 stale/missing short 侧 ticker 实抓成功（+1328 行,含 microcap ALMU/AMBQ/ASTI,未触限流）;生产 rollout smoke 干净。已冻结 batch 不倒填,今日 measurement_ready 仍为 0（by design）;economic_progress=false。
- **转化检查（下一轮第一件事）**：下一个每日 run 产出新 first-seen batch 后看 `data/non_ohlcv/news_propagation_pair_forward_readiness/latest_snapshot.json`——若 measurement_ready_batches ≥ 1,d-0003 gate 打开,立即 reserve 单次 shared-paper-first dollar-neutral pair-build 实验（exp-20260824-001 资格）;若新 batch 仍有 stale/missing_pit_borrow,说明 prefetch 失败,查 exposure manifest 的 short_side_borrow_prefetch 摘要,不得 park。合法残余 blocker 只有 cross_side_ticker_overlap（数据决定）和个别 microcap 经验性无覆盖。

## 最新可执行证据状态（2026-08-27）

- exp-20260827-001（alpha_search / observed_only, 已关闭）：**d-0003 conversion gate 打开当轮即消费**。exp-20260826-001 的 prefetch 生效——2026-08-27T03:07:27Z 的新 first-seen batch（news-first-seen-845025fae409b81adeb3）成为首个真实 measurement_ready batch（29/29 借券覆盖、无跨侧重叠、集中度合规），exp-20260824-001 的单次 pair-build 资格已花在 shared-paper-first build 上：`quant/news_propagation_pair_paper_sleeve.py` 机械 admit 每个 measurement_ready batch 为一个 dollar-neutral basket（负极性做多 / 正极性做空、侧内等行权重、$1000/腿、双腿同步次日开盘入场、缺腿 fail-closed、H10 收盘退出、45bp/腿冻结成本、cash/SPY/QQQ 对照），默认关、接线在 run.py readiness observer 之后。replay/daily parity、同日幂等、default-off 边界全部验证（8/8 build checks、9 sleeve tests、4 wiring tests、lean-strict audit）。
- 首个 basket 已 admit（41 long / 29 short ticker），pending，入场即 2026-08-27 开盘，预计 ~2026-09-10 结算。08-25 / 08-26 两个 blocked batch 永不回填 admit。
- 冻结 forward 验收合同（唯一评判标准，不得中途放宽）：≥20 closed baskets 跨 ≥10 decision dates、45bp/腿成本后净总 PnL 为正、前后两半均为正、单 ticker 绝对毛贡献 ≤40%。
- 边界不变：iBorrowDesk 仅 indicative，非 broker locate——无论 forward 结果如何 sleeve 封顶 default-off paper；live short 讨论需真实 locate 合同。新闻族 attribution 再读仍 park 在 ≥1508 行；d-0005 历史回放 park 不变。

## 最新可执行证据状态（2026-08-28）

- pair sleeve 采证健康：昨夜 daily run 自动 admit 第 2 个 measurement_ready batch（news-first-seen-0d1d4dcda48056d673f7，58 long / 30 short ticker），接线首次无人值守生效；2 baskets pending，0 due_unsettled，首结算 ~2026-09-10。move_relief sleeve 仍 0 行（事件饥饿，30 行 bar 遥远）。
- exp-20260828-001（measurement_repair / contract review, accepted）：执行 exp-20260811-001 预登记的单次 contract review——phase2_estimate_revision 的 `actual_cash_conflicts>=10` bar 是结构性不可达的决策重合罕见事件计数（trace 32 session 全 ok、终身仅 1 次结构化冲突、0 次与 1972 个合格决策重合，其余 bar 全部超阈 17-38 倍）。修约为能力条件：`cash_admission_trace_ok_sessions>=30` 且 `structured_cash_conflict_observations_lifetime>=1`（从持久化 quant_signals 工件 fail-closed 重算，0.92s/日）。其余五项数值 bar、source-contract 与 D0-D3 要求不变。
- **phase2_estimate_revision 数值 gate 首次 ready**（reopen_readiness 2026-08-28T16:47Z，其余 lane 状态全部不变）。这是一笔未消费 conversion_debt：下一工作单元必须跑冻结的 outcome-blind D0-D3 discovery scope（估计修订 surface，发现层，不读结果）；只有 scope 实际选出候选，Phase 2 才算重开。禁止：动其余数值 bar、按决策重合冲突数重新设 gate、把 gate-open 当作候选资格。

## 现场事实（2026-08-18）

- V2 协议重构发生于 2026-08-17 22:47-22:52（本地 UTC-7），**未提交**：`AGENTS.md` 换为通用行为准则，V1 完整协议移至 `docs/quant_agent_protocol.md`（新文件），新增 `docs/quant_agent_protocol_v2.md` 与 `docs/v2_hourly_development_prompt.md`。是否提交待用户决定。
- V1 实验节奏截至 exp-20260817-003（allocator 面板测量修复链，accepted；分配结果仍为 100% core）。V1 ticket 体系继续作为历史档案与反重复证据。
- 2026-08-18 08:04 本地的 alpha 自动化留下 `data/alpha_search/alpha_automation_readiness_preflight_20260818.json`：outcome 字段暴露污染，park，0 实验 ID。该 park 属 V1 管线，不影响 V2 建设。
- V2 专属 schema、股票池、baseline 均不存在；`data/v2/hourly_runs/` 自本轮起记录 receipt。

## 待用户决定

1. **T0 确认**：提议 T0 = 2026-08-18（V2 干净 forward 起点）。确认前所有 V2 产物按 research-only 处理。
2. **V2 重构提交**：08-17 的 AGENTS.md/协议重构仍未提交，agent 不代为提交。
3. **V1 每小时 alpha 自动化与 V2 建设的关系**：V1 管线（readiness preflight / reopen 计数）仍在跑；是否继续并行、还是冻结 V1 只留结算，需要用户表态。
