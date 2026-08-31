# V2 Backlog

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
- [ ] adjacent 合同 trigger 监视：每日 outcome append 后常数时间重算干净 conditioned settled 计数；达 bar 前不得碰该候选，不得读干净切片结果值
- [ ] 禁止：quiet-tape 包络阈值/窗口调参重试（重开条件见 d-0013）；在 daily-batch 时钟上重定义 breadth 阈值；动其余五项数值 bar

## 注意事项

- V1 资产清单不按历史收益排序，按机制覆盖 / 合同完整度 / 授权 / 可回放性 / 工程依赖。
- 建设期插队规则：只有直接阻断可信评估、forward 产出或 parity 的 measurement_repair 可以插队。
- 无安全有价值工作时以 no-op audit 收尾，不硬开实验。
