# V2 Backlog

> 依赖顺序：identity -> clock -> source contract -> universe -> shared policy -> validation -> forward wiring -> allocator -> activation review。
> 每轮取最靠前的一项可完成单元。完成后移入 current_state 或 decision log。

## M0（进行中）

- [x] 建立 `docs/v2/current_state.md`、`backlog.md`、`decision_log.jsonl`、`data/v2/hourly_runs/` receipt（2026-08-18）
- [x] 建立专用 `automation/edge-v2` worktree，并固定已提交源基线（2026-08-19）
- [x] V1 资产清单：25 个功能资产组已机器校验并唯一归入五类（2026-08-19）
- [ ] T0 用户确认（提议 2026-08-18，见 d-0002）
- [x] 偏差登记表：6 类 V1 已知偏差已绑定证据、V2 对策、严重度、阻断范围与定量解除条件（2026-08-19）

## M1（M0 后）

- [ ] `SourceContract`、`EvidenceRecord`、`UniverseEvent` 初始 schema + 校验
- [ ] `ResearchClaim`、`HypothesisCandidate`、`CandidatePool` 初始 schema
- [ ] `DecisionRecord`、`OrderIntent`、`SettledOutcome`、`ReplacementValue` 初始 schema
- [ ] append-only 与幂等测试（schema 层）
- [ ] 时钟合同：交易日归属锚定数据日历 / 冻结 run date，禁止进程壁钟（V1 已有多次壁钟教训）

## 注意事项

- 资产分类真相源：`data/v2/v1_asset_inventory.json`；分类不授予任何 V2 决策或交易资格。
- V1 资产迁移不按历史收益排序，按机制覆盖 / 合同完整度 / 授权 / 可回放性 / 工程依赖。
- 原 V1 脏 checkout 的未提交证据不得静默进入 V2；只在其独立提交并完成身份审计后重新盘点。
- 建设期插队规则：只有直接阻断可信评估、forward 产出或 parity 的 measurement_repair 可以插队。
- 无安全有价值工作时以 no-op audit 收尾，不硬开实验。
