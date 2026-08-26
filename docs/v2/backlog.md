# V2 Backlog

> Promotion 依赖顺序：identity -> clock -> source contract -> universe -> shared policy -> validation -> forward wiring -> allocator -> activation review。
> 这不是排他的小时队列；M1 scout kernel 就绪后，bounded research scout 与 M2-M5 并行。工作排序遵守
> `P0/P1 containment -> unaffected active experiment -> admission-ready scout -> direct scout blocker -> promotion construction`。

## M0（完成）

- [x] 建立 `docs/v2/current_state.md`、`backlog.md`、`decision_log.jsonl`、`data/v2/hourly_runs/` receipt（2026-08-18）
- [x] 建立专用 `automation/edge-v2` worktree，并固定已提交源基线（2026-08-19）
- [x] V1 资产清单：25 个功能资产组已机器校验并唯一归入五类（2026-08-19）
- [x] 偏差登记表：6 类 V1 偏差已绑定证据、对策、严重度、阻断范围与定量解除条件（2026-08-19）
- [x] T0 用户确认：`2026-08-18`，不追溯升级既有证据（2026-08-19 本地；见 `d-0005`）

## M1（完成）

- [x] `SourceContract`、`EvidenceRecord`、`UniverseEvent` 初始 schema + 校验（2026-08-19 本地）
- [x] `ResearchClaim`、`HypothesisCandidate`、`CandidatePool` 初始 schema（2026-08-19 本地）
- [x] `DecisionRecord`、`OrderIntent`、`SettledOutcome`、`ReplacementValue` 初始 schema（2026-08-20 本地）
- [x] append-only 与幂等测试（schema 层；2026-08-20 本地）
- [x] 时钟合同：以完整、证据绑定的数据日历冻结 run date / session，禁止进程壁钟；其余未建 typed evidence 的锚 fail closed（2026-08-20 本地）

## Research Scout Lane（当前最高优先级）

- [x] 协议解除 M0-M5 串行闸门：bounded `research_pit / private_replay_scout` 在 M1 kernel 后可运行，结论硬封顶 `observed_only`（2026-08-21）
- [x] 首个 V2 scout zero-ID preflight：2026-08-20 SEC exact-8-K complete frame 的 219 行 disposition、111 个 mapped-only CandidatePool、DecisionRecord、selection panel 与 promotion 已在 outcome-blind 状态冻结并通过 D0-D3（2026-08-21 本地）
- [x] 首个 V2 scout reserve/run/close：`exp-20260822-001` 按冻结 recipe 完整运行并关闭为 `rejected`；settled 指标只见 canonical log/artifact，不进入 outcome-blind 启动导航（2026-08-21 本地）
- [ ] 下一 scout：不得在 `exp-20260822-001` 的同一 frame 上做成本、持有分钟、item code、子集或 event-sign 阈值近邻搜索；只接受独立冻结的更晚 complete frame，或结果前可用的独立事件符号源，仍须 preflight/freeze/reserve 后才能读 outcome

## M2（并行 Promotion Construction）

- [x] 研究 ledger 人口核心：严格 append-only `UniverseEvent` + manifest、原子锁定提交、完整前缀恢复校验、显式 manifest/as-of 共享 daily/replay reader；外部覆盖固定 unverified，research-only（2026-08-21）
- [x] 外部 coverage/security surface：首个真实 SEC 8-K source bundle、219/219 行 `mapped / unmapped / excluded` disposition、111 个有效期映射/active membership、coverage evidence 与不可变 ledger/manifest 已冻结；范围仍是 research-only source frame，不是市场级完备性（2026-08-21）
- [x] SEC 8-K source-bounded runtime adapter v3：required explicit backend/storage location/manifest/as-of；legacy 与 segmented-hot 均验证同一 envelope/coverage graph，segmented 每次只加载一次同一 hot state 且禁止自动探测、cold traversal 与 silent fallback；冻结 backend/hot-tip/input/snapshot identity，source ceiling 不升级（2026-08-21）
- [x] 接入只读 pre-Engine-0/default-off universe observation v2：同一显式 backend/storage/manifest/as-of 经一次 adapter 调用进入 daily/replay 真 alias，精确保留 backend/membership/state/identity 并拒绝 ceiling、字段与语义 hash 漂移；不调用 Engine-0 policy、不建立 baseline 或市场决策时钟（2026-08-21）
- [x] 给 event-row prefix 校验建立 deterministic 规模回归并用 event/manifest/clock identity 索引移除额外 O(E²)/O(M²) 历史重扫；保留完整 manifest/population/chain、PIT 与 default-off 校验（2026-08-21）
- [x] 建立只读 checkpoint/segment sidecar 合同核心：常量 `HEAD` + 不可变 checkpoint + 单事务 hash-linked segments，严格重建 exact legacy view，referenced damage fail closed、orphan audit-only，future-effective/零事件 projection 与已提交 SEC 身份保持一致；明确保持 contract-only/unwired（2026-08-21）
- [x] 接入显式 bootstrap 与 segmented writer：复用 legacy M1 transaction planner、create-only immutable checkpoint/segment、合作 writer 锁定串行、`HEAD`-last atomic replace、predecessor identity check、crash orphan 精确重试与 missing-HEAD 防回退；保持 contract-only/unwired（2026-08-21）
- [x] 建立 compact checkpoint/rotation：热代只保留一份当前 events、一个 tip manifest、O(history) 身份胶囊和当前 generation tail；精确历史沿不可变 superseded 谱系冷回放，轮换与 audit 共用 writer 锁且不删除旧对象（2026-08-21）
- [x] 建立 aggregate storage capability/rollback 合同：full/compact `HEAD.storage_contract` 明确分流，marker 与 checkpoint 类型 fail-closed 绑定；部署固定 reader-first，compact 切换后禁止同 root 原地 HEAD rewind 或回滚到不支持 compact lineage 的 binary，rotation 继续显式且 unscheduled（2026-08-21）
- [x] 给 cold rotation/deep lineage 建立参数化结构回归：同一逻辑 tip 的 1/2/4 generation fixture 冻结 hot load 零 archive traversal、standalone exact pass 每个可达 record 单读、byte conservation 与保守 affine peak-memory guard；小型 fixture 不冒充真实 market-scale/SLO，elapsed 只记诊断，绝对 cadence 继续等待真实 population/churn/retention/SLO（2026-08-21）
- [x] 将 segmented hot-state reader 以显式 backend 接入 source-bounded runtime，并证明显式 hot-tip manifest/as-of 的 daily/replay 等价；单次加载同一 state，禁止 backend 自动探测、cold traversal 或 silent legacy fallback，rotation 保持显式且 unscheduled（2026-08-21）
- [x] 冻结仓库外 append anchor 的 target-independent decision/deployment contract：每次 HEAD transition、cutover/successor/receipt/retention/IAM/fail-closed 语义与 A1-A14 验收已机器绑定；target、owner、凭据边界和授权仍待用户选择（2026-08-21）
- [ ] 任何 canonical 候选前建立仓库外 append anchor；本地有效旧 `HEAD` 回滚仍无法由仓库内 sidecar 检出

## 注意事项

- T0 真相源：`data/v2/t0.json`。T0 只是项目 / 前瞻分区边界，不授予 canonical PIT、策略资格或交易权限。
- 资产分类与偏差登记不会授予任何 V2 决策或交易资格。
- 原 V1 脏 checkout 的未提交证据不得静默进入 V2。
- V2 不管理或等待 V1 自动化；V1 仅是可选只读历史参考，不阻塞 scout、forward 或晋级。
- pre-Engine-0 observation handoff 不等于 M3：动态 PIT 市场 universe、market decision clock 与共享 feature/policy/decision baseline 均未建立。
- M1 kernel 就绪后最多连续两个非阻断纯建设单元；存在 admission-ready scout 时，promotion-only P2 不得继续抢占。
- 没有合格 novelty/PIT/映射/触达时不硬开实验；失败 preflight 不烧 ID。只优先解除安全、有价值、可完成且预计能直接形成 admission-ready scout 的 blocker，否则继续 promotion backlog 或 no-op。
- Receipt 每轮必写；state/backlog/decision log 只在各自事实真正改变时更新，不复制实验 ticket/log/artifact 已记录的内容。
