# V2 Backlog

> 2026-09-09 导航校正：下方是 root 历史待办，保留作档案，不再作为当前 alpha 工作队列。
> 当前 V2 alpha 待办在 [Edge backlog](../../.codex/worktrees/edge-v2/docs/v2/backlog.md)，
> source_ref 为 `refs/heads/automation/edge-v2`。root 生产维护与既有冻结观察的本轮记录在
> [本轮改动及固定验证队列](../../data/maintenance/ginger_followthrough_20260909.md)。本导航不复制或升级任何历史策略资格。

> 依赖顺序：identity -> clock -> source contract -> universe -> shared policy -> validation -> forward wiring -> allocator -> activation review。
> 每轮取最靠前的一项可完成单元。完成后移入 current_state 或 decision log。

## M0（进行中）

- [x] 建立 `docs/v2/current_state.md`、`backlog.md`、`decision_log.jsonl`、`data/v2/hourly_runs/` receipt（2026-08-18 本轮）
- [ ] T0 用户确认（提议 2026-08-18，见 d-0002）
- [ ] V1 资产清单（机器可读；每项归入 reuse_directly / reuse_after_contract_upgrade / migrate_as_zero_weight_challenger / legacy_diagnostic_only / retire 五类之一）
- [ ] 偏差登记表（V1 已知偏差：静态股票池、事后权重、只记赢家、幸存者名单等，逐条列出并标注 V2 对策）

## M1（M0 后）

- [ ] `SourceContract`、`EvidenceRecord`、`UniverseEvent` 初始 schema + 校验
- [ ] `ResearchClaim`、`HypothesisCandidate`、`CandidatePool` 初始 schema
- [ ] `DecisionRecord`、`OrderIntent`、`SettledOutcome`、`ReplacementValue` 初始 schema
- [ ] append-only 与幂等测试（schema 层）
- [ ] 时钟合同：交易日归属锚定数据日历 / 冻结 run date，禁止进程壁钟（V1 已有三次壁钟教训）

### 直接阻断 forward 的插队修复

- [x] iBorrowDesk 抓取管道 www 主机故障修复（exp-20260825-001, accepted）:裸域 /api 断连自 ~07-21 冻结 PIT 借券归档;已修复并验证 10/10 定向 + 89/150 shard;每日 run.py Step 1.65 自动续传补齐
- [x] readiness borrow 覆盖缺口修复（exp-20260826-001, accepted）：exposure observer 在 first_seen 冻结前对本轮新增 short 侧 ticker 定向预抓取（fail-open）;Step 1.65 预算 150→60 留限流余量;转化检查=下一个每日 batch 的 borrow_coverage
- [x] 转化确认后消耗 pair-build 资格（exp-20260827-001, observed_only, 2026-08-27）：首个 measurement_ready batch 当轮 admit 为 dollar-neutral basket；sleeve 默认关每日接线；验收=冻结 forward 合同（≥20 baskets / ≥10 dates），首结算 ~2026-09-10
- [x] pair sleeve 结算修复（exp-20260913-006, accepted, 2026-09-13）：过期仓库 frame 遮蔽 massive 回退 → 早于锚最后 bar 的 frame 整只回退；缺腿 45→15、被遮蔽 31→0；OTC/未上市/退市腿按合同仍 fail-closed
- [x] pair sleeve 腿可定价 contract review（exp-20260913-007, accepted, 2026-09-13）：准入需 first_seen 前 5 个 session 全有 bar（排除记录+权重重归一+空侧不准入）；窗口后 5 session 仍缺腿 → `unsettleable` 终态不计验收；5/5 历史记录修约下两侧非空全可定价；**验收计数从修约后首个 admit 的 batch 起算**
- [ ] （管理项）sic_peer_index 输出无价格源符号（BAO/DBIM/EVON/HWEP/GTIJF）与已退市名（AIEV/BINI/ECDA）；不阻塞研究，排队处理
- [x] entity_theme axis-C 第四次同面重开读（exp-20260914-001, rejected, 2026-09-14, d-0020）：208492 行（+82% vs 114541）字节相同规则下 QQQ row median −1.50 与 3/6 breadth 两 bar 失败；重停 ≥312738；streak 4；`scripts/build_reopen_readiness.py` 与 frozen families 已同步
- [ ] axis-C 稀释诊断（下一单元候选，analysis_only / loss_attribution 家族，1 ID）：把 208492 cohort 按 exp-20260810-001 读数前/后结算切分，区分新行 regime 稀释与整体无边际；不得改规则或作为新 alpha 计数
- [x] pair sleeve 准入侧 latest-session defer guard（exp-20261007-001, codex, accepted, 2026-10-07）：09-25 basket 把 34/32 流动票误标 excluded_unpriceable 的根因=hot 最新 session 未刷新即准入；今后 lag 时 defer 不消费 batch
- [x] pair sleeve 结算侧宽限期时钟修约（exp-20261007-002, accepted, 2026-10-07, d-0028）：机器 09-26..10-06 停机后 catch-up pass 里 sleeve 在 massive 09-25 bar 落库前 39 秒结算、SPY 锚已到 10-06 → 首个可计数 basket 39644ff3（AIOT/INSG 只在 massive）被误终态 unsettleable；现在终态化需锚日历与 massive 都到 exit+5；**误判行不改写（用户决定），验收计数从 basket f5b68e87（entry 09-24）重起**
- [ ] 负面侧 1508 再读（trigger 已触发 1609，reasoned park 于 d-0020）：仅当 pair sleeve 被 park/阻塞 ≥20 session 无可计数结算，或 forward 验收合同失败需归因时，先冻结与 exp-20260824-001 字节一致的 F1-F5+V1-V2 再读结果
- [ ] （管理项）`scripts/build_reopen_readiness.py` 无 run.py 接线，09-01→09-14 停更 13 天；每轮启动先手动重算或补接线（接线属 measurement_repair 登记）

- [x] structured-news exposure 新行冻结本地 `first_seen_at`，旧行不倒填；同批两侧密度/集中度/重叠与 PIT indicative borrow readiness 每日幂等落盘（exp-20260824-002）
- [x] 零 ID、outcome-blind 重建每日快照的保守历史 `known_at`：精确 Git 路径只有 5 个独立 entry-ready 时点 / 3 个 borrow-filtered；research-PIT EOD 路径有 20 个 entry-ready、16 个 H10、2 个 borrow-filtered，均未过预声明门槛（`data/alpha_search/news_pair_historical_reconstructability_20260824.json`）
- [ ] research-PIT EOD 路径达到 20 个 H10 后才允许一次冻结的延迟/成本快速否证；不得把 20 降到当前 16，也不得据此声称 short 可执行
- [ ] 仅在历史无法还原或作为最终确认时等待真实 `measurement_ready` batch；20 个 closed forward baskets / 10 个 decision dates 之前不做 forward alpha 接受判断
- [ ] 任何 live short review 前补真实 broker locate contract；iBorrowDesk 不得升级冒充 locate

### SEC selling-holder overhang 快速转化链

- [x] outcome-blind 建立 S-1/F-1 primary-document economics sidecar，并用交易前身份/流动性把 5,065 份资格压缩为 181 份候选；冻结 118 行 selling-holder roster（38/45/35）
- [x] `exp-20260824-003` 完成一次固定口径 H10 market-hedged 私有回放：三窗口、双倍成本、集中度与完整性全部通过；结果仅为 observed-only positive lead
- [x] outcome-blind 连接同一 registration 的 SEC `EFFECT`、424B3/424B4：118 行中 111 行有精确激活证据；重新按激活时点资格冻结 83 行（31/23/29）
- [ ] 定义并接入真实 broker locate / short-availability 合同；没有逐 ticker 决策时点 locate 就不得 paper/live
- [x] `exp-20260824-004` 只改 decision clock 做 EFFECT/424 独立确认并明确失败：三窗全负、合计 -$2,965.18、双成本 -$4,441.18；实际供给过hang 解释 rejected
- [ ] 建立 unchanged acceptance-time 实时 observer + 决策时点真实 locate 证据，累计 settled forward replacement value；在此之前不得将 exp-003 接入 paper/live
- [ ] 历史近邻回放线关闭：禁止 EFFECT-only/424-only 切片，以及 form/parser/clock/amount/liquidity/cooldown/cost/borrow/hold/hedge/sample 调参

### Phase-2 estimate-revision 重开链（已重开，2026-08-29）

- [x] 结算人口修复（exp-20260811-001）；h20 于 2026-08-19+ 日历成熟（08-28 实测 518/30）
- [x] cash-conflict bar 合同修约（exp-20260828-001, accepted）：不可达罕见事件计数 → trace 能力条件（ok sessions>=30 且终身结构化冲突>=1）；reopen_readiness phase2 lane 首次 ready，其余 lane 不变
- [x] conversion_debt 消费（2026-08-29, d-0012, 零 ID）：全新 outcome-blind D0-D3 scope `phase2-estimate-revision-20260829` 实际选出候选 → **Phase 2 重开**；3 候选全 pass、selector 选中 exploration breadth 候选
- [x] 被选候选 cand-c748224bb9bc0f6a9118 当轮 park：feed 日批时钟使孤立对照仅 8 决策（vs 1510 breadth 成员），对照腿结构性不可达；blocker+定量重开条件落 `data/alpha_search/phase2_estimate_revision_breadth_reachability_20260829.json`
- [x] exploitation 候选 quiet-tape 反证已执行并 REJECTED（exp-20260831-001, 2026-08-31, d-0013）：密度检查通过（802 conditioned / 656/427/142 settled）→ 单候选 scope 复验 → research_pit 升级（updated_at 保守重建 620/802）→ F1-F6 冻结反证 4 挂 2 过；already_priced 命中预测
- [x] adjacent 注册候选 `cand-68d2f5dad2f903488307`（事前 overshoot 部分回吐）：干净 forward 反证合同已冻结（d-0014, 2026-08-31, 零 ID）——到达率检查通过（冻结规则下干净 stock 已 57 个 / 20 up / 37 down），bars B1-B5 从 08-29 注册措辞逐条冻结，样本 gate ≥30/gated horizon + ≥10/腿；现为 blocked_watch_item 等结算，保守 ETA h5 ~09-08 / h10 ~09-11，trigger 到达即 reserve→claim→run（≤24h）。合同：`data/alpha_search/phase2_adjacent_overshoot_clean_forward_contract_20260831.json`
- [x] adjacent 合同 trigger 监视：09-12 recount h5 76/30（29 up / 47 down）、h10 55/30（20 up / 35 down）→ 触发；围栏 1352 ID 从 freeze commit 5967838ae 字节一致重算，条件价格 2307 行绑哈希（09-09 身份阻塞解除；82 文件集合哈希按构造不可复现，仅文档性）。当轮 reserve→claim→run→close：`exp-20260912-001 / expuid-afb826c754034d9f` **REJECTED**（B1 h5 −0.73%、B2 h10 对现金 −$1,744、B3 对 SPY −$698 / QQQ −$1,682、B5 shuffle p90 +2.18% > 实际 +0.59%；仅 B4 过，且只有 3 个 session；already_priced）。重开：不相交新 forward 窗口（09-11 后首次结算）每 gated horizon ≥60 且 ≥10 entry dates；或盘中逐条发布时钟；或非价格路径变换的 conditioning 变量。回执 `data/v2/hourly_runs/20260912T2100Z_d0014_adjacent_overshoot_clean_forward_falsification.json`
- [ ] 禁止：quiet-tape 包络阈值/窗口调参重试（重开条件见 d-0013）；在 daily-batch 时钟上重定义 breadth 阈值；动其余五项数值 bar

### 前台等待事件 trigger（d-0015，2026-09-01）

- [x] moomoo capital-flow DAY long-only preflight（d-0015, 零 ID）：全轴机器关闭，no_candidate close 落 `data/alpha_search/moomoo_capital_flow_day_longonly_preflight_20260901.json`；fallback prediction_market_postfix 同样 not_ready（指纹停滞）
- [ ] 展示污染围栏（第 3 例）：top1 main-inflow accumulation 机制只在 exit_date>2026-08-31 的 position 上评估；重开 trigger = 干净 closed ≥20 跨 ≥10 entry dates（sleeve state 身份字段常数时间计数，ETA ~11 月中）；期间禁读 sleeve PnL 字段
- [ ] 事件 trigger 队列（触发即 reserve→claim→run ≤24h）：~~d-0014 bar~~（09-12 已触发并消费，exp-20260912-001 rejected）；negative-side 1508 re-read（**09-13 已触发：1609/1508**，未消费）→ 下一单元冻结与 exp-20260824-001 字节一致的再读合同后再读，或记录有理由 park；pair 首结算（~09-10）→ 日常 observer 结算；prediction-market 计数（停滞）
- [ ] d-0014 / exp-20260912-001 重开条件 (a)（新窗口=h5 首次结算 >09-11；≥60/gated horizon、≥10 entry dates、腿 ≥10）：`quant/experiments/adjacent_overshoot_reopen_window_recount_20261006.py` 只读重计数；10-06 catch-up 后 h5 218（74/144，11 dates）过、h10 168（61/107，**7 dates**）未过；决策按 feed 日成批，h10 第 10 个 entry date 预计 10-09 夜批后 → 触发即从 0831 合同逐字冻结 B1-B5 于新窗口，reserve→claim→run ≤24h
- [ ] trigger 全 pending 期间：小时单元只做常数时间 recount，no-op suppressed 退出；不开新 surface / 修复 lane
- [ ] （管理单元候选，非插队）`daily_news_structured_event_observations_*.jsonl` 无结算消费者，退役/合并评估

## 注意事项

- V1 资产清单不按历史收益排序，按机制覆盖 / 合同完整度 / 授权 / 可回放性 / 工程依赖。
- 建设期插队规则：只有直接阻断可信评估、forward 产出或 parity 的 measurement_repair 可以插队。
- 无安全有价值工作时以 no-op audit 收尾，不硬开实验。
