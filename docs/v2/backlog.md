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
- [ ] 首个 V2 scout zero-ID preflight：立即选择一个授权、row-level 时钟可用、effective mapping、非零 source-native 触达且 novelty/reopen 通过的 evidence axis；20 分钟内通过则冻结 experiment-local disposition manifest、mapped-only CandidatePool 和必要的 DecisionRecord，仅机器校验 row-count 守恒、row-hash 唯一/互斥和 mapped-set 一致性，不先建共享 schema；失败则记录 exact predicate/hash/reopen 而不烧 ID
- [ ] 首个 V2 scout reserve/run/close：用现有 hash-bound promotion / claim / experiment closeout 原语绑定 V2 admission 与结果身份；一个 hypothesis、一个 treatment、一个 primary horizon；registry 只允许正向完整 lead=`observed_only`，其余=`rejected`，最多跨两个小时单元

## M2（并行 Promotion Construction）

- [x] 研究 ledger 人口核心：严格 append-only `UniverseEvent` + manifest、原子锁定提交、完整前缀恢复校验、显式 manifest/as-of 共享 daily/replay reader；外部覆盖固定 unverified，research-only（2026-08-21）
- [x] 外部 coverage/security surface：首个真实 SEC 8-K source bundle、219/219 行 `mapped / unmapped / excluded` disposition、111 个有效期映射/active membership、coverage evidence 与不可变 ledger/manifest 已冻结；范围仍是 research-only source frame，不是市场级完备性（2026-08-21）
- [x] SEC 8-K source-bounded runtime adapter v2：强制显式 manifest/as-of，验证同一 envelope/ledger/coverage graph，daily/replay 走唯一共享 reader，冻结规范化 input/snapshot hash 与独立 research-only adapter parity 状态；source ceiling 不升级（2026-08-21）
- [x] 接入只读 pre-Engine-0/default-off universe observation boundary：同一显式 manifest/as-of 经一次 adapter 调用进入 daily/replay 真 alias，精确保留 membership/state/identity 并拒绝 ceiling、字段与语义 hash 漂移；不调用 Engine-0 policy、不建立 baseline 或市场决策时钟（2026-08-21）
- [x] 给 event-row prefix 校验建立 deterministic 规模回归并用 event/manifest/clock identity 索引移除额外 O(E²)/O(M²) 历史重扫；保留完整 manifest/population/chain、PIT 与 default-off 校验（2026-08-21）
- [ ] 全市场长期使用前为累计 multi-manifest event/registry/membership surface 与 whole-file atomic rewrite 建立 checkpoint/segmentation；任何 canonical 候选前建立仓库外 append anchor

## 注意事项

- T0 真相源：`data/v2/t0.json`。T0 只是项目 / 前瞻分区边界，不授予 canonical PIT、策略资格或交易权限。
- 资产分类与偏差登记不会授予任何 V2 决策或交易资格。
- 原 V1 脏 checkout 的未提交证据不得静默进入 V2。
- V2 不管理或等待 V1 自动化；V1 仅是可选只读历史参考，不阻塞 scout、forward 或晋级。
- pre-Engine-0 observation handoff 不等于 M3：动态 PIT 市场 universe、market decision clock 与共享 feature/policy/decision baseline 均未建立。
- M1 kernel 就绪后最多连续两个非阻断纯建设单元；存在 admission-ready scout 时，promotion-only P2 不得继续抢占。
- 没有合格 novelty/PIT/映射/触达时不硬开实验；失败 preflight 不烧 ID。只优先解除安全、有价值、可完成且预计能直接形成 admission-ready scout 的 blocker，否则继续 promotion backlog 或 no-op。
- Receipt 每轮必写；state/backlog/decision log 只在各自事实真正改变时更新，不复制实验 ticket/log/artifact 已记录的内容。
