# V2 Current State

> V2 状态导航入口。每轮结束时更新。真相源永远是 ticket / ledger / 已提交代码，本文件只负责导航。
> 最后更新：2026-08-19T16:10Z（M0 V1 偏差登记表轮）

## 里程碑

当前处于 **M0（定规则 / T0）**。V1 资产清单已经落地；M0 尚未完成。

| 里程碑 | 状态 |
|---|---|
| M0 规则 / T0 / 状态文件 | 进行中：状态文件、25 项 V1 资产清单与 6 项偏差登记表已建；仅 T0 待用户确认 |
| M1 身份、时钟、数据合同 schema | 未开始 |
| M2 动态 PIT 股票池 | 未开始 |
| M3 共享 SDK 与 Engine-0 干净基线 | 未开始 |
| M4-M9 | 未开始 |

## 本轮完成

- 新增 `data/v2/v1_bias_register.json`，登记 M0 明确要求的 6 类 V1 偏差：静态 / 幸存者股票池、
  outcome-derived 权重、winner-only panel、可变 current-state replacement value、wall-clock 日期与
  AI 自由文本执行权限。
- 每项绑定现存证据 anchor、资产清单 ID、PIT 判断、严重度、阻断范围、V2 对策和 3 条机器可读
  解除条件；当前 5 项为 `critical`、1 项为 `high`，18 条条件全部保持 `met=false`。
- 新增机器校验，确保 6 项不能静默删除、证据 anchor 存在、解除门槛为结构化数值、summary 一致，
  且全局和逐项均为 `trade_enabled=false`、不直接取得 V2 决策资格。
- 本轮不占实验 ID，不改变策略、测量、parity、订单、真钱权限或 V1 资格。

## 关键边界（当前生效）

- `trade_enabled=false`；V2 不继承 V1 股票名单、alpha 结论、资格、权重、晋级状态。
- `reuse_directly` 只允许复用工程原语或不可变历史证据，不等于复用 V1 决策结论。
- M3 Engine-0 baseline 建立前，V2 候选最高停在 research/shadow。
- V1 的 `docs/backtesting.md` baseline 只做回归与机会成本对照，不是 V2 Gate-1 锚。

## 现场事实（2026-08-19）

- 专用 V2 worktree 的最近已提交 V1 ticket 是 `exp-20260815-001`（rejected）。
- 原 V1 脏 checkout 中观察到的 2026-08-16/17 未提交 ticket 与产物没有迁入 V2 基线，也没有用于资产分类证据。
- `python scripts/experiment.py audit` 正常执行但 `passed=false`：2481 tickets、2667 logs、10 个历史
  alpha-promotion 无效项、1 个 research result-ceiling 违规。因此 V1 aggregate status 不能作为 V2 资格证据；
  canonical per-ID shards 只作为历史和防重复证据复用。
- `data/v2/v1_bias_register.json` 的 6 项 blocker 全部仍为 `open`；偏差解除不会自动授予交易权限。
- T0 尚未确认；所有 V2 forward 产物继续按 research-only 处理。

## 待用户决定

1. **T0 确认**：是否确认 T0 = 2026-08-18（首次 V2 引导轮日期）。确认前不声称 canonical forward 证据。
2. **V1 自动化关系**：V1 每小时 alpha 管线是否继续与 V2 建设并行，还是冻结为只结算 / 只读历史。

## 下一步

等待用户确认或否决 T0 = 2026-08-18；确认后关闭 M0 并进入 M1 初始 schema。用户还需决定 V1 每小时
alpha 管线继续并行，还是冻结为只结算 / 只读历史；决定前不启动 V2 forward 竞赛。
