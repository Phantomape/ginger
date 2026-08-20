# V2 Current State

> V2 状态导航入口。每轮结束时更新。真相源永远是 ticket / ledger / 已提交代码，本文件只负责导航。
> 最后更新：2026-08-20T02:13Z（M0 T0 确认轮）

## 里程碑

**M0 已完成**。下一里程碑为 **M1（身份、时钟、数据合同）**，尚未开始实现。

| 里程碑 | 状态 |
|---|---|
| M0 规则 / T0 / 状态文件 | 完成：状态文件、25 项 V1 资产清单、6 项偏差登记表与 T0 声明均已落地 |
| M1 身份、时钟、数据合同 schema | 待开始：先做 `SourceContract`、`EvidenceRecord`、`UniverseEvent` 初始 schema + 校验 |
| M2 动态 PIT 股票池 | 未开始 |
| M3 共享 SDK 与 Engine-0 干净基线 | 未开始 |
| M4-M9 | 未开始 |

## T0（已确认）

- 用户确认 `T0 = 2026-08-18`；机器真相源为 `data/v2/t0.json`，append-only 决策为 `d-0005`。
- T0 按 `America/Los_Angeles` 的日历日期记录，不倒填虚构的盘中精确时刻。
- 用户确认前，以及 M1 身份 / 时钟 / 来源合同完成前的产物，最高仍为 `research_pit`，不能追溯升级为 canonical forward 证据。
- `canonical_forward_eligibility_started_at` 仍为 `null`；具体来源和记录必须分别通过授权、时钟、映射、schema 与冻结 Gate。
- T0 确认不授予任何策略资格，不改变真钱权限，`trade_enabled=false`。

## M0 交付物

- `data/v2/v1_asset_inventory.json`：25 个 V1 功能资产组已唯一归入五类。
- `data/v2/v1_bias_register.json`：6 项偏差全部保持 open，18 条解除条件均未满足。
- `data/v2/t0.json`：确认项目日期边界、证据 ceiling、禁止追溯升级与 default-off。
- `docs/v2/backlog.md`、`docs/v2/decision_log.jsonl` 与每轮 receipt：状态和接力棒。

## 关键边界（当前生效）

- `trade_enabled=false`；V2 不继承 V1 股票名单、alpha 结论、资格、权重、晋级状态。
- `reuse_directly` 只允许复用工程原语或不可变历史证据，不等于复用 V1 决策结论。
- 6 项 V1 bias blocker 全部仍为 open；M3 Engine-0 建立前，V2 候选最高停在 research/shadow。
- V1 baseline 只做回归与机会成本对照，不是 V2 Gate-1 锚。
- 原 V1 脏 checkout 的未提交 ticket 与产物没有迁入 V2 基线。

## 待用户决定

1. **V1 自动化关系**：V1 每小时 alpha 管线继续与 V2 建设并行，还是冻结为只结算 / 只读历史。
   此决定不阻断 M1 合同建设，但在决定前不启动 V2 forward 竞赛。

## 下一步

进入 M1，完成第一个最小工作单元：`SourceContract`、`EvidenceRecord`、`UniverseEvent` 初始 schema 与校验；
继续保持 research-only、default-off，不占 alpha 实验 ID。
