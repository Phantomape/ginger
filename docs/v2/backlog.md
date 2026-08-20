# V2 Backlog

> 依赖顺序：identity -> clock -> source contract -> universe -> shared policy -> validation -> forward wiring -> allocator -> activation review。
> 每轮取最靠前的一项可完成单元。完成后移入 current_state 或 decision log。

## M0（完成）

- [x] 建立 `docs/v2/current_state.md`、`backlog.md`、`decision_log.jsonl`、`data/v2/hourly_runs/` receipt（2026-08-18）
- [x] 建立专用 `automation/edge-v2` worktree，并固定已提交源基线（2026-08-19）
- [x] V1 资产清单：25 个功能资产组已机器校验并唯一归入五类（2026-08-19）
- [x] 偏差登记表：6 类 V1 偏差已绑定证据、对策、严重度、阻断范围与定量解除条件（2026-08-19）
- [x] T0 用户确认：`2026-08-18`，不追溯升级既有证据（2026-08-19 本地；见 `d-0005`）

## M1（下一里程碑）

- [ ] `SourceContract`、`EvidenceRecord`、`UniverseEvent` 初始 schema + 校验
- [ ] `ResearchClaim`、`HypothesisCandidate`、`CandidatePool` 初始 schema
- [ ] `DecisionRecord`、`OrderIntent`、`SettledOutcome`、`ReplacementValue` 初始 schema
- [ ] append-only 与幂等测试（schema 层）
- [ ] 时钟合同：交易日归属锚定数据日历 / 冻结 run date，禁止进程壁钟

## 待用户决定（不阻断 M1）

- [ ] V1 每小时 alpha 管线继续并行，或冻结为只结算 / 只读历史；决定前不启动 V2 forward 竞赛。

## 注意事项

- T0 真相源：`data/v2/t0.json`。T0 只是项目 / 前瞻分区边界，不授予 canonical PIT、策略资格或交易权限。
- 资产分类与偏差登记不会授予任何 V2 决策或交易资格。
- 原 V1 脏 checkout 的未提交证据不得静默进入 V2。
- 建设期只有直接阻断可信评估、forward 产出或 parity 的 measurement_repair 可以插队。
- 无安全有价值工作时以 no-op audit 收尾，不硬开实验。
