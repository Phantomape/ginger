# V2 Current State

> V2 状态导航入口。每轮结束时更新。真相源永远是 ticket / ledger / 已提交代码，本文件只负责导航。
> 最后更新：2026-08-20T02:54Z（M1 基础数据合同轮）

## 里程碑

**M0 已完成，M1 进行中**。M1 第一个最小工作单元已完成：
`SourceContract`、`EvidenceRecord`、`UniverseEvent` 初始 schema 与 fail-closed 校验。

| 里程碑 | 状态 |
|---|---|
| M0 规则 / T0 / 状态文件 | 完成：状态文件、25 项 V1 资产清单、6 项偏差登记表与 T0 声明均已落地 |
| M1 身份、时钟、数据合同 schema | 进行中：首批三个基础合同与跨合同校验已完成；下一项为研究候选合同 |
| M2 动态 PIT 股票池 | 未开始 |
| M3 共享 SDK 与 Engine-0 干净基线 | 未开始 |
| M4-M9 | 未开始 |

## T0（已确认）

- 用户确认 `T0 = 2026-08-18`；机器真相源为 `data/v2/t0.json`，append-only 决策为 `d-0005`。
- T0 按 `America/Los_Angeles` 的日历日期记录，不倒填虚构的盘中精确时刻。
- 用户确认前及合同落地前的产物最高仍为 `research_pit`，不能追溯升级为 canonical forward 证据；历史数据仍可在明确记录时钟与来源后用于 `research_pit` 私有回放。
- `canonical_forward_eligibility_started_at` 仍为 `null`；具体来源和记录必须分别通过授权、时钟、映射、schema 与冻结 Gate。
- T0 确认不授予任何策略资格，不改变真钱权限，`trade_enabled=false`。

## M1 已完成单元

- `quant/v2_contracts.py`：独立于 V1 的不可变 `SourceContract`、`EvidenceRecord`、`UniverseEvent` 与嵌套 `SecurityMappingSnapshot`。
- 来源合同机器声明原始身份字段、真正参与决策的内容字段、发布时钟字段、修订字段、授权证据、可用性、映射政策、PIT ceiling 与 parity 状态。
- 证据同时绑定原始 artifact SHA-256 和标准化决策内容 SHA-256；所有瞬时时钟必须带时区，禁止日期值、naive timestamp 和进程壁钟回退。
- 跨合同校验强制 `SourceContract -> EvidenceRecord -> UniverseEvent` 完整链：字段和值一致、来源真实存在、等级不越权、映射在当时已知且覆盖生效时点、证据先落账再决策。
- Universe 事件携带显式冻结 run date / calendar session、前后状态、规则 hash、证据语义快照和 previous-event 引用；当前名单/当前映射不能倒灌为 PIT。
- 事件输入快照使用 evidence semantic hash，排除只改变 `recorded_at` 的操作噪声。append-only ledger、previous-event 链验证及写入幂等仍属于后续 M1 单元。
- 本单元只建立 schema/校验，不接 daily、replay、运行时或下单路径，不占 alpha 实验 ID；`trade_enabled=false`。

## M0 交付物

- `data/v2/v1_asset_inventory.json`：25 个 V1 功能资产组已唯一归入五类。
- `data/v2/v1_bias_register.json`：6 项偏差全部保持 open，18 条解除条件均未满足。
- `data/v2/t0.json`：确认项目日期边界、证据 ceiling、禁止追溯升级与 default-off。
- `docs/v2/backlog.md`、`docs/v2/decision_log.jsonl` 与每轮 receipt：状态和接力棒。

## 关键边界（当前生效）

- `trade_enabled=false`；V2 不继承 V1 股票名单、alpha 结论、资格、权重、晋级状态。
- `reuse_directly` 只允许复用工程原语或不可变历史证据，不等于复用 V1 决策结论。
- 6 项 V1 bias blocker 全部仍为 open；本轮只提供解除 blocker 所需的合同原语，不代表任何 blocker 已关闭。
- `canonical_forward_eligibility_started_at=null`；schema 允许表达 canonical 条件不等于当前记录已获 canonical 资格。
- M3 Engine-0 建立前，V2 候选最高停在 research/shadow。
- V1 baseline 只做回归与机会成本对照，不是 V2 Gate-1 锚。
- 原 V1 脏 checkout 的未提交 ticket 与产物没有迁入 V2 基线。

## 待用户决定

1. **V1 自动化关系**：V1 每小时 alpha 管线继续与 V2 建设并行，还是冻结为只结算 / 只读历史。
   此决定不阻断 M1 合同建设，但在决定前不启动 V2 forward 竞赛。

## 下一步

继续 M1 的下一项：`ResearchClaim`、`HypothesisCandidate`、`CandidatePool` 初始 schema；
复用本轮严格时钟、哈希、来源绑定与 default-off 原语，不接运行时，不占 alpha 实验 ID。
