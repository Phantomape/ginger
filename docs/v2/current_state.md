# V2 Current State

> 2026-10-06 root 生产维护（d-0028）：机器 09-26..10-06 停机 10 天（LastBootUpTime 10-06 17:35 local），codex 开机即启动 run.py catch-up（00:39Z，父子解释器非双写）。catch-up pass 中 pair sleeve 在 massive grouped:2026-09-25 落库前 39 秒结算，而 SPY 锚（core primary_batch）已到 10-06，`settle_pair_basket` 把 exp-20260913-007 宽限期量在锚日历上，首个可计数 basket 39644ff3（短腿 AIOT/INSG 只在 massive）被误终态 unsettleable。`exp-20261007-002 / expuid-9794c0252b834e45`（measurement_repair，accepted）：`load_pair_bars` 记 `__source_last_sessions__`，终态化需锚日历与 massive 都到 `calendar[exit_index+5]`；结算时刻状态 replay 由 unsettleable 变 missing_leg_bars blocker，全量 bar 为 settled（只读 status）；ledger/state 字节不变；误判行不改写（用户决定），验收计数从 basket f5b68e87（entry 09-24）重起。并发 codex `exp-20261007-001` 同小时在同模块落地准入侧 latest-session defer guard。d-0014 重开条件 (a) 的 outcome-blind 重计数脚本已建：数量早过 60，约束是 ≥10 entry dates（09-25 账本 h5 6 / h10 3），ETA ~10-09 夜批后。见 `data/v2/hourly_runs/20261007T0204Z_pair_sleeve_grace_clock_source_lag_repair_accepted.json`。
>
> 2026-09-24 root 生产维护（d-0026）：exp-20260923-004 故障恢复检查通过（09-24 夜批首条 v2 记录 measurement_ready、30/34 借券覆盖、sleeve 自动 admit basket 并把 BAO/DBIM/EVON/GST 记为 excluded_no_pit_borrow；exp-20260922-007 的 Form 4 折叠计数已可见 3 行=2 个经济决策）。身份字段普查发现 v2 规则下 cross_side_ticker_overlap 是 09-14 后 14 条 readiness 记录中 6 条的唯一剩余阻塞（终身 10/33），重叠内容是整组 sic_peer（半导体 23-33、汽车 17、中概/AI 软件 14-20 个 ticker）因同批同组一负一正事件被放到两侧；剔除重叠后两侧均非空、残余最大行权重 ≤0.087。`exp-20260924-004 / expuid-b986642a3afa4fac`（measurement_repair，accepted）：对 first_seen ≥ 2026-09-24T17:00Z 的 batch，重叠 ticker 从两侧/两腿剔除并记录（observer `overlap_exclusion`、sleeve 两腿 `excluded_cross_side_overlap`），40% 上限与 v2 借券覆盖按残余侧评估，仅在一侧被清空时阻塞；33/33 持久化记录字节一致重建；假设就绪 18/33→25/33（09-14 后 8/14→14/14）；验收合同、H10/45bp/$1000 不变；未读任何结果字段。下一单元：核对 09-25 夜批记录带 `overlap_exclusion.rule_version`。见 `data/v2/hourly_runs/20260924T1630Z_pair_readiness_cross_side_overlap_exclusion_accepted.json`。
>
> 2026-09-22 root 生产维护（d-0024）：exp-20260921-001 的故障恢复检查通过（09-21 夜间 coverage 行已带 `ticker_canonicalization_kind=instrument_master_variant_v1`）；其预登记的 reopen 计数人口修约由并发的 codex 会话以 `exp-20260922-006` 当轮执行并 accepted（本单元未碰其写域、未重算 readiness）。按身份字段排查其余 stalled lane 时发现第二个生产缺陷：候选决策训练账本以含日内价格的 observation_id 做幂等键，09-21 日内 18:13Z 一次 run.py 通过 + 夜间 03:06Z 通过把同一 META 计划入场写了两次；Form 4 sale-overhang 前瞻 lane 按决策行而非经济决策计数（7 行 = 5 个 ticker+入场日），冻结的 25 closed bar 会被重复行抬高。`exp-20260922-007 / expuid-d09b1ba2d1b94778`（measurement_repair，accepted）：追加时跳过已存在的 (as_of, ticker)，Form 4 进度先按 (ticker, entry_date) 折叠再计数并报告原始行数/剔除数；仅向前生效、不改写账本、gate/horizon/ID 派生不变；10+22+1 测试、lean-strict 绿。待用户决定：日内第二次 run.py 通过的来源（09-16..09-18 ~16:07Z、09-21 18:13Z，无 hook/计划任务可解释）；intraday triage 生产者自 08-04 停止。见 `data/v2/hourly_runs/20260922T1628Z_candidate_ledger_same_day_economic_identity_repair_accepted.json`。
>
> 2026-09-21 root 生产维护：accepted 的 dividend-restart 前瞻 lane 静默饥饿（7 周 status=ok、0 决策、54 次 date_resolution 全空池）
> 已诊断：v1 分红 feed 同一工具两种拼写（`XXXA`/`XXX.A`、`XXXPRY`/`XXXpY`）被按字面分组当成 gap/首次派息，486 候选中 332 为伪像
> （0 个 gate-eligible 受影响，历史 89 行 roster 不受影响）。`exp-20260921-001 / expuid-5392fc03d2784334`（measurement_repair，accepted）
> 在 gap 检测前按 instrument_master 规范化拼写（歧义即字面、fail closed），账本不改、仅向前生效，69/69 测试、lean-strict 绿。
> 伴随发现已预登记、未执行：reopen 计数只数 restart_after_observed_gap 的 CS 决策，历史速率约 5 个/17 个月、前瞻 7 周 0 个，
> ≥30 结构性不可达；冻结的 review 规则=按 exp-20260801-004 roster 人口（两种 gap 变体）重对齐、bar 仍为 30；
> 见 `data/v2/hourly_runs/20260921T1837Z_dividend_restart_observer_symbol_variant_identity_repair_accepted.json`、`d-0023`。
>
> 2026-09-09 导航校正：本文件以下正文保留 root 历史状态，不能作为当前 V2 alpha 调度入口。
> 当前 alpha 操作权威是 `refs/heads/automation/edge-v2`，状态见
> [Edge current_state](../../.codex/worktrees/edge-v2/docs/v2/current_state.md)，待办见
> [Edge backlog](../../.codex/worktrees/edge-v2/docs/v2/backlog.md)。不要再次按下方旧 M0/T0 待办执行。
> root 负责生产维护；本轮 `exp-20260909-002` / `expuid-1818c9a28a3342b6` 完成决策与订单归属修复，
> 工程验收通过、无新增 alpha 或实盘权限。改动及 root 既有冻结观察队列见
> [本轮记录](../../data/maintenance/ginger_followthrough_20260909.md)。跨 ref 仍按 source_ref 与 UID 分开记账。
> 2026-09-12：root 固定验证队列项 2（d-0014 adjacent overshoot 干净 forward 反证）trigger 触发并当轮消费：
> `exp-20260912-001 / expuid-afb826c754034d9f` **REJECTED**（B1/B2/B3/B5 失败，仅 B4 过；already_priced）。
> 身份阻塞已解：污染围栏 1352 ID 从 freeze commit 5967838ae 字节一致重算，条件价格 2307 行已绑哈希；82 文件集合哈希按构造不可复现（仅文档性）。
> 08-29 Phase-2 estimate-revision 注册池至此除 parked breadth 候选外全部终态；重开计数见 log。见 d-0018 与
> `data/v2/hourly_runs/20260912T2100Z_d0014_adjacent_overshoot_clean_forward_falsification.json`。队列项 1（新闻配对）仍由 root 日常 run 结算。

> 2026-09-13：root 生产缺陷当轮修复（d-0019，2 个 measurement_repair ID，均 accepted）：配对 sleeve 5/5 basket 结构性不可结算。
> `exp-20260913-006`：仓库过期 100 行 frame（止于 2026-04-24）遮蔽 massive 回退 → 早于 SPY 锚最后一根 bar 的 frame 视为缺失、整只 ticker 回退 massive（缺腿 45→15，被遮蔽 31→0）。
> `exp-20260913-007`（006 预登记的 contract review）：每个 basket 仍含无任何价格源的腿（sic_peer_index 的 OTC/未上市/已退市符号）→ 准入新增 outcome-blind 可定价条件（first_seen 当日及之前 5 个 session 全有 bar，排除记录在决策、权重重归一、空侧不准入），窗口结束后 5 个 session 仍缺腿的 basket 追加 `unsettleable` 终态且不计入验收；修约下 5/5 历史记录两侧非空且已知 session 全可定价。**forward 验收计数从修约后首个 admit 的 batch 重新开始**；5 个冻结旧 basket 不重写，~09-18/19 起由日常 run 终态化。
> 负面侧 1508 再读 trigger 已触发（1609≥1508，身份重算；`data/reopen_readiness.json` 停在 09-01 的 1222）但本单元未消费——下一单元须先冻结与 exp-20260824-001 字节一致的再读合同（F1-F5+V1-V2）再读结果，或记录有理由的 park。sic_peer_index 符号卫生为独立管理项。回执 `data/v2/hourly_runs/20260913T1740Z_news_pair_settlement_repair_and_leg_priceability_contract_review.json`。

> 2026-09-14：`data/reopen_readiness.json` 停更 13 天后重算（生成器无 run.py 接线，需手动跑），entity_theme_axis_c 越过 171812 bar（208492 settled，+82%）当轮消费为
> `exp-20260914-001 / expuid-1bc1858ea5104249`（d-0020）：字节相同 exp-20260719-004 规则、`--observed-only-override`（streak 3）、正则身份抽取的结果盲 cohort 冻结、D0-D3/panel/promotion、reserve→claim→单次 run，**REJECTED**——
> 三个 row mean 为正（cash/SPY/QQQ +48.44/+24.07/+20.87 USD per 4000-USD row）但 QQQ row median −1.50、且仍只有 3/6 query group 同时胜 SPY+QQQ（floor 4）；相对 08-10 读数是稀释而非收敛（cash median 16.83→8.01、QQQ median 13.30→−1.50、breadth 不变）。
> 该面重停在 ≥312738（未变 manifest；按 ~2.7k 行/日约 10 月下旬）、家族 trials 7/accept 0、observed-only streak 4（第五次同面需再次 override）；builder/frozen families 已同步，lean-strict 绿。
> 注意：runner 自动生成的 why_result 文本写成「QQQ mean 与 median 均为负」，准确表述是 mean 为正、median 为负（canonical 字节被 manifest 绑定不改，以回执为准）；本轮 scope 时间戳为模板标签、晚于实际 reserve 时钟（无泄漏，第 4 例壁钟教训）。
> 负面侧 1508 再读 trigger（1609）记为有理由 park：pair build 存活且 09-13 已 admit 首个可计数 basket，家族证据路径是 forward 验收合同；只有 build 被 park/阻塞 ≥20 session 或 forward 合同失败需归因时才冻结 F1-F5+V1-V2 再读。回执 `data/v2/hourly_runs/20260914T1640Z_entity_theme_axis_c4_reopen_read_rejected.json`。
> 下一单元候选：把 208492 cohort 按 08-10 读数前/后结算的行切分做 analysis_only 稀释诊断（零行情、1 ID、区分「源在衰退」与「仅被稀释」）；事件 trigger：pair 首个可计数结算 ~09-28、旧 basket ~09-18/19 终态化。

> 2026-09-15：09-14 锁定的稀释诊断当轮执行为 `exp-20260915-005 / expuid-792d6de6037d4663`（d-0021，loss_attribution / analysis_only）：exp-20260914-001 的 208492 行 cohort 字节一致复现（六项 delta 全 0），按身份键切成 OLD（当前 20260810 ledger 文件中 exit_date ≤ 08-07 的 114566 行，近似已被当晚 run 覆盖的 08-10 读数 114541）与 NEW（93926 行）。冻结的 C0 复现检查七项中一项未过（QQQ 行中位数 11.73 vs 已消费 13.30，delta −1.57 > 1.00 USD；计数 +25、全部均值与 cash/SPY 中位数在容差内）→ 按合同 **observed_only / identity_mismatch，不报告稀释分类**。根因：outcome ledger 同日文件被当晚 daily run 重写且不入 git，08-10 字节不可恢复；25 行身份缺口即可移动重尾 11 万行序列的离散中位数。不在本 ID 或新 ID 下放宽容差（结果后改阈值禁止）。合法再问：以日期已过、字节稳定的 20260913 ledger（sha 1593fa03…）为精确锚，切「≤09-13 cohort vs 之后增量」，规则从 005 冻结计划原样继承、C0 改为精确复现；待增量 ≥~30000 行（~10 月中）或与 312738 第五次读数预登记合并。父 alpha 家族不变（trials 7 / accept 0 / streak 4 / reopen 312738）。回执 `data/v2/hourly_runs/20260915T1625Z_entity_theme_cohort_split_dilution_diagnostic_identity_mismatch.json`。
> 2026-09-16：无在研可执行题目，按协议§1 做固定结果诊断 `exp-20260916-006 / expuid-c4d1e442ee054f27`（d-0022，loss_attribution / analysis_only）：exp-20260914-001 的 208492 行 cohort（字节一致复现）是「新闻条目 × ticker」行，按身份键折叠为 3490 个唯一 (ticker, entry, exit, horizon) 持仓（每持仓均 59.7 行，前十分位持仓占 40.7% 行）。C0 精确通过（九项 delta 全 0，持仓内取值零冲突）。等权持仓层：对 cash/SPY/QQQ 均值 +37.67/+9.31/+4.23 USD（行层 +48.44/+24.07/+20.87），中位数 +0.55/−12.65/−12.45（行层 8.01/3.12/−1.50），正向占比 ~0.48–0.50，Spearman(行数, 持仓值) ≈ 0 → **position_level_no_edge**：行层结论定性成立，但行加权把 ETF 相对均值放大 2.6–4.9×，有效样本是 289 个入场日 × 30 ticker 的 ~3.5k 持仓而非 20.8 万行；正均值是 AI capex 半导体（MU/CRDO/AMD）右尾，中位持仓 10 日跑输两 ETF ~0.31%。未保留任何持仓层/新闻强度 face，不改 312738 bar；仅建议第五次读数预登记同时报告等权持仓层统计与唯一持仓数（与 09-15 的增量切分建议并列）。父家族不变（trials 7 / accept 0 / streak 4 / reopen 312738）。回执 `data/v2/hourly_runs/20260916T1626Z_entity_theme_position_dedup_weighting_attribution_no_edge.json`。
> 陷阱：同日 ledger 文件会被当日晚间 run 覆盖，日内读数绑定的字节晚上就不存在；中位数容差须按 rank 位移或更宽 USD 带冻结；`build_reopen_readiness.py` 无 --help，任何调用都会重算。事件 trigger 不变（旧 basket ~09-18/19、pair 首结算 ~09-28、axis-C 312738 ~10 月下旬）。

> V2 状态导航入口。每轮结束时更新。真相源永远是 ticket / ledger / 已提交代码，本文件只负责导航。
> 最后更新：2026-09-01T16:45Z（d-0015：moomoo capital-flow preflight 全轴机器关闭 + fallback prediction-market 同样关闭 → no_candidate close；本单元一例展示污染（第 3 例）已围栏零 ID；全部前台等事件 trigger，最早 ~09-08）

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

## 最新可执行证据状态（2026-08-29）

- **d-0011 conversion debt 已消费**：预注册 scope `phase2-estimate-revision-20260829`（scope-2d453592cbe4b7b822ff9fdf）在 estimate-revision surface 上完成一轮全新 outcome-blind D0-D3。estimate surface 以 canonical_pit / gate_candidate / saturation open 入场（机器依据：reopen_readiness lane ready + source contract 6/6）。3 个候选（exploitation 延迟价格吸收 / adjacent 预期外抢跑回吐 / exploration 同 session breadth 冲击）全部 D0-D3 pass、零 legacy 近邻命中；冻结多样性选择器选中 exploration 候选 `cand-c748224bb9bc0f6a9118`（panel e9ca292b...，verify-panel valid）。**Phase 2 按 Phase-1.5 冻结合同正式重开**。
- **被选候选当轮 park（零 ID）**：falsifier 冻结前的 outcome-blind 可达性检查（只读身份字段）发现 consensus feed 按日批量落盘——1518 个合格决策集中在 21 个 session（单 session 最多 209 个），breadth(≥3 同向) 成员 1510 个 vs 孤立对照仅 8 个。冻结对照腿（breadth vs isolated）结构性不可达，按 08-28 协议"数值 bar 可达性"规则 park，机器 blocker + 定量重开条件见 `data/alpha_search/phase2_estimate_revision_breadth_reachability_20260829.json`。禁止在同一 daily-batch 时钟上重定义 breadth 阈值。
- **下一工作单元（已锁定）**：对 D0-D3 已通过、未被选中的 exploitation 注册候选 `cand-1a665d7350fd8d6349e8`（延迟价格吸收）先做 outcome-blind quiet-tape 条件密度检查（五日价格路径 vs 波动包络，仅 OHLCV 身份数据）；条件 cohort ≥30/horizon 则同单元跑单候选 scope 复验→冻结 falsifier→reserve→run 正式反证实验。
- pair sleeve 健康：5 个 lifetime batch，2 ready 已全部 admit（2 pending，~09-10 首结算），昨夜 batch 被 cross_side_ticker_overlap（数据决定、合法）fail-close；eligible_unadmitted=0、due_unsettled=0。

## 最新可执行证据状态（2026-08-31）

- exp-20260831-001（alpha_search / private_replay_scout, **rejected**）：08-29 receipt 锁定的 scope debt 当轮完整消费。outcome-blind quiet-tape 密度检查通过（1522 个合格非平映射决策 → 802 个 quiet-tape conditioned，settled h5/h10/h20 = 656/427/142，全部 gated leg ≥30）；exploitation 注册候选 cand-1a665d7350fd8d6349e8 经全新单候选 scope 字节不变复验（prior 快照锚定其注册之前以避免自命中；D0-D3 全过、零近邻）；OHLCV pre-event 上下文面以行级 updated_at 保守重建诚实升级 research_pit（620/802 决策全部 pre-entry 写入，fail-closed；h20 PIT 腿 26<30 仅报告不 gate）；falsifier F1-F6 冻结进 promotion 后 reserve→claim→run。
- 反证结果：F1 方向 spread 失败（h5 −0.017% / h10 +0.63% / h20 −0.27%，需 ≥2/3 horizon 含 h10 为正）；F3 失败（up 腿 h10 对 QQQ −$5,781）；F5 ticker shuffle 失败（真实 simple spread 0.21% 低于 shuffle p90 1.58%——表观 spread 是 session 漂移而非 issuer 特异）；F6 PIT 子集失败（h5 −0.26%）。F2（长腿对现金全 horizon 为正）与 F4（日期 placebo）通过但不能独立支撑。realized failure mode = already_priced（命中预测）。幅度单调性在 h10/h20 破裂。
- **污染围栏（重要）**：预登记的次要报告暴露了 non-quiet（overshoot）cohort 的方向 spread（h5 −1.11% / h10 −0.42% / h20 +6.48%），与已注册 adjacent 候选 cand-68d2f5dad2f903488307（事前 overshoot 部分回吐）机制重叠。该候选在现有已结算决策上的评估已污染：其反证只允许 gate 在 **2026-08-31 之后首次结算** 的干净 forward 切片上，falsifier 措辞须从其 08-29 注册冻结，不得向观测到的 contrast 调参。
- 家族重开条件（quiet-tape 延迟 repricing）：settled h5/h10/h20 ≥ 2704/2144/1400（2× 当前 closed）且资格规则不变，或来源合同新增真正的 intra-session 逐条发布时钟，或真正不同的条件变量；包络阈值/窗口调参一律禁止。
- pair sleeve 健康：2 baskets pending（~09-10 首结算），eligible_unadmitted=0、due_unsettled=0。

## 最新可执行证据状态（2026-08-31 第二单元：adjacent 干净 forward 合同冻结）

- **d-0014（零 ID）**：08-31 receipt 锁定动作当轮执行。outcome-blind 到达率检查（仅身份/状态字段）：干净池 = h5 未结算的 170 个合格映射决策（只会在 08-31 后首次结算，位于 d-0013 污染围栏之外）；按 08-29 注册措辞冻结的 conditioning 规则（常数倍数更新隐含 repricing：dir_sign·R5 > |ΔEPS/(EPS−ΔEPS)|，|prior EPS|≥0.10、delta 方向一致、fail-closed）下干净 conditioned stock 已 57（20 up / 37 down，entry 08-24..08-30）。零新增到达保守 ETA：h5 ≥30 于 ~09-08、h10 ≥30 于 ~09-11、双腿 ≥10。可达性通过 → **合同当场冻结**（任何干净切片结果访问之前）。
- 冻结合同要点：B1 残差衰减 spread（down−up）在 h5 与 h10 均 >0；B2 down-overshoot 可交易腿 h10 对现金 >0；B3 h10 对 SPY 与 QQQ 均 >0；B4/B5 日期 placebo 与同 session ticker shuffle（200 draws，seed 20260901，h10）；displaced-core 对照 reported-only（ledger 无逐决策序列）；h20 仅报告（注册 half-life=H5-H10）；样本 gate ≥30/gated horizon 且 ≥10/方向腿；结论上限 observed_only。合同与生成脚本：`data/alpha_search/phase2_adjacent_overshoot_clean_forward_contract_20260831.json`、`quant/experiments/adjacent_overshoot_clean_forward_contract_freeze_20260831.py`。
- 候选转为 blocked_watch_item：trigger = 每日 outcome append 使干净 conditioned settled 计数达 bar（常数时间重算）；到达后下一 alpha slot 内 reserve→claim→run（≤24h）。观测到的 08-31 non-quiet contrast 未塑造任何 bar——方向、horizon、腿与 falsifier 族均来自 08-29 注册原文。
- pair sleeve 健康（今日）：第 3 个 measurement_ready batch 昨夜无人值守自动 admit（appended_this_run=1），3 baskets pending，0 due_unsettled、0 eligible_unadmitted，首结算仍 ~09-10。
- **front lane 切换（下一单元已锁定）**：estimate-revision 家族等待期间，做 registered `moomoo_capital_flow_day_observer` surface 的 outcome-blind 低摩擦 long-only alpha preflight（本地 canonical DAY archive、07-21 起每日刷新、无借券/locate/付费源依赖、H1-H5 快结算可行）。

## 最新可执行证据状态（2026-09-01）

- **d-0015（零 ID）**：08-31 receipt 锁定的 moomoo capital-flow DAY long-only preflight 当轮执行，surface 全轴机器关闭：同规则 top1 forward 复测只有 11 个 closed（低于 materially-more bar）且本轮被展示污染围栏；H1-H5 变体 = 禁止的 hold-day 近邻；bucket/impact/response 重切被 exp-20260702-019 + exp-20260709-019 围栏禁止；flow×put-OI 在同 proxy 行禁止且 sleeve 结算轴 event-starved；intraday decomposition 需新管道非本单元可跑。fallback prediction_market_postfix 重建 readiness 后仍 not_ready 4/7（top_query 93.87%>50%、top_ticker 15.64%>15%、prob-change markets 17<20，unique markets 自 08-04 冻在 34，指纹停滞）。全 14 条已登记 readiness lane 机器关闭或已消费 → 按冻结 fallback 顺序产出 no_candidate artifact：`data/alpha_search/moomoo_capital_flow_day_longonly_preflight_20260901.json`。
- **展示污染第 3 例（2026-08-11、2026-08-18 之后）**：子串黑名单遮罩让 `realized_pnl_to_date`（含 'date'）打印，暴露 top1-accumulation sleeve 截至 08-31 的聚合已实现 PnL（~-1979 美元 / 11 closed）。围栏：该机制只能在 08-31 后首次结算的 position 上评估，冻结重开 trigger = 干净 closed ≥20 跨 ≥10 entry dates（ETA ~11 月中）；零 ID。**规则：含结果值的文件只允许 ALLOWED 身份白名单读取，禁止黑名单遮罩。**
- d-0014 recount（常数时间，与冻结合同字节对账 170/57/20/37）：h5 已结算 24/30（8 up/16 down）、h10 0/30，未触发；绑定 bar 是 h10，ETA ~09-08..09-11。
- 事件 trigger 集中窗口：d-0014 bar ~09-08..09-11；negative-side 1508 re-read（1222/1508，~40/日）~09-08；pair sleeve 首结算 ~09-10；moomoo 干净 forward ~11 月中。**在任一 trigger 触发前，后续小时单元只做常数时间 recount，no-op suppressed 退出（不建文件、不 commit）。**
- 备注：`daily_news_structured_event_observations_*.jsonl`（353 行全 pending_forward_close）无任何结算消费者，实际结算面在 entity_theme observers——退役/合并候选，留给未来管理单元；family-271 的 target_price 谓词在现行合同下结构性不可达（如需修约须预登记 contract review；当前无必要，因 exp-20260718-002 gate 独立失败）。

## 最新可执行证据状态（2026-09-23）

- **d-0025 / exp-20260923-004（measurement_repair，accepted）**：pair sleeve 自 09-14 起零准入的根因是 exp-20260826-001 readiness gate 对 short 腿**每一只**票要求 PIT 借券证据、任一缺失即整批阻塞，而实体映射持续吐出 iBorrowDesk 无页面的未上市/OTC sic_peer 符号（BAO/DBIM/EVON/HWEP/LILW/SBEV/BAGZ/BLTG/GRAY/MOT，预抓取当日已尝试、返回 not_found）——正是 exp-20260913-007 已在准入层排除的不可定价符号，因此该修约从未作用到任何新批次（09-14 后 13/13 blocked，7 条仅因借券，覆盖率 85–98%）。合同修约（forward-only，first_seen ≥ 2026-09-23T17:00:00Z）：无借券票记入 `borrow_coverage.uncovered_tickers` 并在准入时排除（`excluded_no_pit_borrow`，等权重归一化，腿空则不准入）；整批只因批级 blocker 或 `short_side_no_borrow_coverage` 阻塞。结果盲投影：冻结 6/32 ready → 假设 v2 17/32（09-14 后 1/13 → 7/13）；32 条历史记录被新代码逐字节复现；不追溯准入；H10/45bp/1000 美元/40%/≥20/≥10 不变。工件：`data/experiments/exp-20260923-004/`；receipt `data/v2/hourly_runs/20260923T1633Z_pair_readiness_borrow_coverage_exclusion_accepted.json`。
- 启动核对：exp-20260922-007 计数器已随 09-23 夜批落盘（ledger `rows_skipped_same_day_economic_duplicate=0`；form4 `closed_forward_row_records_current=1`）；readiness 重算（09-23T16:12Z）无 lane 过 bar；分红 lane 已显示 codex 修约后的人群计数 0/30。
- 零 ID 决定：成交滑点 parity 诊断不开（live_drift 已有告警；38 仓位 0 个 core 可归因；备注码 09-09 才启用）。
- 下一单元：核对 09-24 夜批首个 post-effective readiness 记录带 `coverage_rule_version=news_propagation_pair_borrow_coverage_v2` 且 sleeve 追加 basket；每周复算 ready 节奏（预期 ~3–4/周 vs 之前 ~1）；form4 DE 08-24 20d 折叠核对；pair 首个可计数结算 ~09-29。

## 现场事实（2026-08-18）

- V2 协议重构发生于 2026-08-17 22:47-22:52（本地 UTC-7），**未提交**：`AGENTS.md` 换为通用行为准则，V1 完整协议移至 `docs/quant_agent_protocol.md`（新文件），新增 `docs/quant_agent_protocol_v2.md` 与 `docs/v2_hourly_development_prompt.md`。是否提交待用户决定。
- V1 实验节奏截至 exp-20260817-003（allocator 面板测量修复链，accepted；分配结果仍为 100% core）。V1 ticket 体系继续作为历史档案与反重复证据。
- 2026-08-18 08:04 本地的 alpha 自动化留下 `data/alpha_search/alpha_automation_readiness_preflight_20260818.json`：outcome 字段暴露污染，park，0 实验 ID。该 park 属 V1 管线，不影响 V2 建设。
- V2 专属 schema、股票池、baseline 均不存在；`data/v2/hourly_runs/` 自本轮起记录 receipt。

## 待用户决定

1. **T0 确认**：提议 T0 = 2026-08-18（V2 干净 forward 起点）。确认前所有 V2 产物按 research-only 处理。
2. **V2 重构提交**：08-17 的 AGENTS.md/协议重构仍未提交，agent 不代为提交。
3. **V1 每小时 alpha 自动化与 V2 建设的关系**：V1 管线（readiness preflight / reopen 计数）仍在跑；是否继续并行、还是冻结 V1 只留结算，需要用户表态。
