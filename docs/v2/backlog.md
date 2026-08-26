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
- [ ] 转化确认后消耗 pair-build 资格：measurement_ready_batches ≥ 1 时 reserve 单次 shared-paper-first pair-build 实验（见 current_state 2026-08-26 节与 receipt next_alpha_action）

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

## 注意事项

- V1 资产清单不按历史收益排序，按机制覆盖 / 合同完整度 / 授权 / 可回放性 / 工程依赖。
- 建设期插队规则：只有直接阻断可信评估、forward 产出或 parity 的 measurement_repair 可以插队。
- 无安全有价值工作时以 no-op audit 收尾，不硬开实验。
